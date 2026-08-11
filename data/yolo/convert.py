import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import timm

# =======================================================
# 1. ARCHITECTURE DEFINITIONS (Must match training exactly)
# =======================================================

class StarNetBlock(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.dwconv = nn.Conv2d(dim, dim, kernel_size=3, padding=1, groups=dim)
        self.f1 = nn.Conv2d(dim, dim, kernel_size=1)
        self.f2 = nn.Conv2d(dim, dim, kernel_size=1)
        self.g = nn.Conv2d(dim, dim, kernel_size=1)
        self.act = nn.GELU()

    def forward(self, x):
        shortcut = x
        x_mapped = self.dwconv(x)
        return shortcut + self.g(self.act(self.f1(x_mapped) * self.f2(x_mapped)))


class DySample(nn.Module):
    def __init__(self, in_channels, scale=2):
        super().__init__()
        self.scale = scale
        self.offset_generator = nn.Conv2d(in_channels, 2 * scale * scale, kernel_size=1)
        nn.init.zeros_(self.offset_generator.weight)
        nn.init.zeros_(self.offset_generator.bias)

    def forward(self, x):
        B, C, H, W = x.shape
        offset = self.offset_generator(x)
        
        # Reshape and permute offsets to match dynamic sampling format
        offset = offset.view(B, self.scale, self.scale, 2, H, W).permute(0, 4, 1, 5, 2, 3)
        offset = offset.reshape(B, H * self.scale, W * self.scale, 2)
        
        # ONNX-friendly grid generation
        grid_y, grid_x = torch.meshgrid(
            torch.linspace(-1, 1, H * self.scale, device=x.device),
            torch.linspace(-1, 1, W * self.scale, device=x.device),
            indexing='ij'
        )
        
        # Enforce float typecast to avoid tensor mismatch warnings during extraction
        base_grid = torch.stack([grid_x, grid_y], dim=-1).unsqueeze(0).repeat(B, 1, 1, 1).to(x.dtype)
        
        # F.grid_sample requires Opset 16+ for proper ONNX conversion
        return F.grid_sample(x, torch.clamp(base_grid + offset, -1, 1), mode='bilinear', padding_mode='zeros', align_corners=False)


class StarDySampleNetwork(nn.Module):
    def __init__(self, num_classes=77):
        super().__init__()
        # Load the shell structure without downloading heavy pretrained weights again
        base_net = timm.create_model('convnextv2_tiny', pretrained=False) 
        self.stem = base_net.stem
        self.stages = base_net.stages
        self.star_block = StarNetBlock(dim=384)
        self.dysample = DySample(in_channels=768, scale=2)
        self.global_pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Linear(768, num_classes)

    def forward(self, x):
        x = self.stem(x)
        x = self.stages[0](x)
        x = self.stages[1](x)
        x = self.stages[2](x)
        x = self.star_block(x)
        x = self.stages[3](x)
        x = self.dysample(x)
        x = self.global_pool(x)
        return self.classifier(torch.flatten(x, 1))

# =======================================================
# 2. RUN EXTRACTION PIPELINE
# =======================================================
if __name__ == '__main__':
    NUM_CLASSES = 77
    WEIGHTS_PATH = "best_star_dysample_model.pth"
    OUTPUT_ONNX = "custom_star_dysample_weed_model.onnx"

    print("--- Reassembling Model Architecture ---")
    model = StarDySampleNetwork(num_classes=NUM_CLASSES)

    print(f"--- Loading Trained Weights from: {WEIGHTS_PATH} ---")
    if os.path.exists(WEIGHTS_PATH):
        # Always map to CPU for standard graph tracing stability
        state_dict = torch.load(WEIGHTS_PATH, map_location="cpu")
        model.load_state_dict(state_dict)
        print("Successfully loaded trained weights!")
    else:
        raise FileNotFoundError(f"Could not find '{WEIGHTS_PATH}' in the current folder. Please check the file path.")

    # Explicitly set to evaluation mode (turns off dropout/batchnorm updates)
    model.eval()

    # Generate standard dummy tensor representing [Batch=1, Channels=3, H=224, W=224]
    dummy_input = torch.randn(1, 3, 224, 224)

    print(f"--- Tracing Graph (Compiling to ONNX format) ---")
    torch.onnx.export(
        model, 
        dummy_input, 
        OUTPUT_ONNX, 
        export_params=True, 
        opset_version=16,          # CRITICAL: Bounded at 16+ to natively support F.grid_sample
        do_constant_folding=True, 
        input_names=['input_image'], 
        output_names=['class_logits'], 
        dynamic_axes={
            'input_image': {0: 'batch_size'}, 
            'class_logits': {0: 'batch_size'}
        }
    )
    
    print(f"\n[ONNX EXPORT SUCCESSFUL] Saved to: {os.path.abspath(OUTPUT_ONNX)}")
