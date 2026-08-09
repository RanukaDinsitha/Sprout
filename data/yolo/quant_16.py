import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import timm

# =======================================================
# 1. CORE ARCHITECTURE DEFINITIONS 
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

class LSKBlock(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.conv0 = nn.Conv2d(dim, dim, kernel_size=5, padding=2, groups=dim)
        self.conv1 = nn.Conv2d(dim, dim, kernel_size=7, padding=3, groups=dim)
        self.conv_spatial = nn.Conv2d(2, 1, kernel_size=7, padding=3)
        self.proj = nn.Conv2d(dim, dim, kernel_size=1)

    def forward(self, x):
        shortcut = x
        attn0 = self.conv0(x)
        attn1 = self.conv1(x)
        avg_attn = torch.mean(torch.stack([attn0, attn1]), dim=0)
        spatial_avg = torch.mean(avg_attn, dim=1, keepdim=True)
        spatial_max, _ = torch.max(avg_attn, dim=1, keepdim=True)
        spatial_attn = torch.cat([spatial_avg, spatial_max], dim=1)
        spatial_attention_map = torch.sigmoid(self.conv_spatial(spatial_attn))
        return shortcut + self.proj(x * spatial_attention_map)

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
        offset = offset.view(B, self.scale, self.scale, 2, H, W).permute(0, 4, 1, 5, 2, 3).reshape(B, H * self.scale, W * self.scale, 2)
        
        # --- FIXED FOR ONNX EXPORT ---
        target_h = H * self.scale
        target_w = W * self.scale
        
        grid_y = torch.linspace(-1, 1, target_h, device=x.device).view(target_h, 1).expand(target_h, target_w)
        grid_x = torch.linspace(-1, 1, target_w, device=x.device).view(1, target_w).expand(target_h, target_w)
        
        base_grid = torch.stack([grid_x, grid_y], dim=-1).unsqueeze(0).expand(B, -1, -1, -1)
        # -----------------------------
        
        return F.grid_sample(x, torch.clamp(base_grid + offset, -1, 1), mode='bilinear', padding_mode='zeros', align_corners=False)

class HybridWeedNetwork(nn.Module):
    def __init__(self, num_classes=77):
        super().__init__()
        base_net = timm.create_model('convnextv2_tiny', pretrained=False)
        
        # --- FIXED STAGE INDICES TO ALIGN KEY MATCHING ---
        self.stem = base_net.stem
        self.stage0 = base_net.stages[0]  # Outputs 96 channels
        self.stage1 = base_net.stages[1]  # Outputs 192 channels
        
        self.star_block = StarNetBlock(dim=192) 
        self.lsk_block = LSKBlock(dim=192)
        
        self.stage2 = base_net.stages[2]  # Outputs 384 channels
        self.stage3 = base_net.stages[3]  # Outputs 768 channels
        
        self.dysample = DySample(in_channels=768, scale=2) 
        self.global_pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Linear(768, num_classes)

    def forward(self, x):
        x = self.stem(x)       
        x = self.stage0(x)     
        x = self.stage1(x)     
        x = self.star_block(x)
        x = self.lsk_block(x)
        x = self.stage2(x)     
        x = self.stage3(x)     
        x = self.dysample(x)   
        x = self.global_pool(x)
        return self.classifier(torch.flatten(x, 1))

# =======================================================
# 2. RUN DIRECT PYTORCH NATIVE FP16 EXPORT
# =======================================================
if __name__ == '__main__':
    NUM_CLASSES = 77
    WEIGHTS_PATH = "best_hybrid_weed_model.pth"
    FP16_ONNX_PATH = "custom_star_lsk_dysample_weed_model_fp16.onnx"

    print("\n[1/2] Loading trained model weights into memory...")
    model = HybridWeedNetwork(num_classes=NUM_CLASSES)
    
    # This will now load cleanly without any unexpected key flags!
    model.load_state_dict(torch.load(WEIGHTS_PATH, map_location="cpu"))
    model.eval()

    print("Converting model mathematical arrays to Half Precision (FP16)...")
    model = model.half()

    dummy_input_fp16 = torch.randn(1, 3, 224, 224).half()

    print("\n[2/2] Exporting directly to 16-bit ONNX structure (Opset 16)...")
    torch.onnx.export(
        model, 
        dummy_input_fp16, 
        FP16_ONNX_PATH,
        export_params=True, 
        opset_version=16, 
        do_constant_folding=True,
        input_names=['input_image'], 
        output_names=['class_logits'],
        dynamic_axes={
            'input_image': {0: 'batch_size'}, 
            'class_logits': {0: 'batch_size'}
        }
    )
    
    fp16_size = os.path.getsize(FP16_ONNX_PATH) / (1024 * 1024)
    print("\n" + "="*50)
    print("[SUCCESS] Direct FP16 Model Compiled Successfully!")
    print(f"--> Saved Engine File: {os.path.abspath(FP16_ONNX_PATH)}")
    print(f"--> Optimized Model Size: {fp16_size:.2f} MB")
    print("="*50)
