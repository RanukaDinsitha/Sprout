import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
import torchvision.transforms as T
from tqdm import tqdm
import timm
import torch_directml

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
        grid_y, grid_x = torch.meshgrid(
            torch.linspace(-1, 1, H * self.scale, device=x.device),
            torch.linspace(-1, 1, W * self.scale, device=x.device),
            indexing='ij'
        )
        base_grid = torch.stack([grid_x, grid_y], dim=-1).unsqueeze(0).repeat(B, 1, 1, 1)
        return F.grid_sample(x, torch.clamp(base_grid + offset, -1, 1), mode='bilinear', padding_mode='zeros', align_corners=False)

# =======================================================
# 2. SURGICAL HYBRID COUPLING INJECTION MODEL
# =======================================================
class HybridWeedNetwork(nn.Module):
    def __init__(self, num_classes=77):
        super().__init__()
        print("Extracting pretrained backbone layers from timm...")
        # Instantiating pretrained foundations to anchor early edge recognition paths
        base_net = timm.create_model('convnextv2_tiny', pretrained=True)
        
        # Pull apart the 4 separate operational block stages of ConvNeXt V2
        self.stem = base_net.stem
        self.stage0 = base_net.stages[0]  # Outputs 96 channels
        self.stage1 = base_net.stages[1]  # Outputs 192 channels
        self.stage2 = base_net.stages[2]  # Outputs 384 channels
        self.stage3 = base_net.stages[3]  # Outputs 768 channels
        
        # Inject Custom Modular Operations array at the 192-channel boundary (Stage 1 Output)
        self.star_block = StarNetBlock(dim=192) 
        self.lsk_block = LSKBlock(dim=192)
        
        # Inject DySample Dynamic Upsampling at the final 768-channel boundary (Stage 3 Output)
        self.dysample = DySample(in_channels=768, scale=2) 
        
        # New Output classification pooling head
        self.global_pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Linear(768, num_classes)

    def forward(self, x):
        # Phase 1: Pretrained deep feature passes (Stages 0 & 1)
        x = self.stem(x)       # Input 224x224 -> 56x56
        x = self.stage0(x)     # 96 Channels
        x = self.stage1(x)     # 192 Channels

        # Phase 2: Inject Custom Attention Array Blocks at 192 channels
        x = self.star_block(x)
        x = self.lsk_block(x)
        
        # Phase 3: Final Pretrained Deep Blocks (Stages 2 & 3)
        x = self.stage2(x)     # 384 Channels
        x = self.stage3(x)     # 768 Channels
        
        # Phase 4: Dynamic Detail Reconstruction Upsampling 
        x = self.dysample(x)   # Dynamic upsampling logic
        
        # Final head pooling aggregation outputs
        x = self.global_pool(x)
        return self.classifier(torch.flatten(x, 1))

# =======================================================
# 3. ENVIRONMENT LOGISTICS ENGINE ENTRY POINT
# =======================================================
if __name__ == '__main__':
    DATASET_ROOT = "C:/Users/ranuk/Downloads/Sprout/data/yolo/images"
    NUM_CLASSES = 77
    BATCH_SIZE = 32
    EPOCHS = 30

    TRAIN_ROOT = os.path.join(DATASET_ROOT, "train")
    VAL_ROOT = os.path.join(DATASET_ROOT, "val")

    DEVICE = torch_directml.device()
    print(f"\n[AMD ACCELERATION RUNNING] Interface Hooked to: {DEVICE}")

    # Advanced Transforms arrays to maximize data density variations
    train_transform = T.Compose([
        T.Resize((224, 224)),
        T.RandomHorizontalFlip(p=0.5),
        T.RandomVerticalFlip(p=0.5),
        T.RandomRotation(degrees=30),
        T.ColorJitter(brightness=0.2, contrast=0.2),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    val_transform = T.Compose([
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    train_dataset = ImageFolder(root=TRAIN_ROOT, transform=train_transform)
    val_dataset = ImageFolder(root=VAL_ROOT, transform=val_transform)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=2, pin_memory=True)

    model = HybridWeedNetwork(num_classes=NUM_CLASSES).to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=0.05)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    print("\n--- Training Custom StarNet-LSK-DySample Array (Hybrid Pretrained Foundation) ---")
    best_acc = 0.0
    for epoch in range(EPOCHS):
        model.train()
        loop = tqdm(train_loader, desc=f"Epoch [{epoch+1}/{EPOCHS}]")
        for images, labels in loop:
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            optimizer.zero_grad(set_to_none=True)
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            loop.set_postfix(loss=loss.item())

        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            loop_val = tqdm(val_loader, desc="Validating")
            for images, labels in loop_val:
                images, labels = images.to(DEVICE), labels.to(DEVICE)
                outputs = model(images)
                _, predicted = outputs.max(1)
                total += labels.size(0)
                correct += predicted.eq(labels).sum().item()
        
        val_acc = 100.0 * correct / total
        print(f"--> Epoch [{epoch+1}/{EPOCHS}] Complete. Accuracy Match: {val_acc:.2f}%\n")
        scheduler.step()
        
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), "best_hybrid_weed_model.pth")

    # =======================================================
    # 4. INSTANT DIRECT AUTOMATIC ONNX MODEL EXPORT
    # =======================================================
    print("\n--- Model Saved. Processing Conversion to Open-Source ONNX Engine Matrix ---")
    onnx_model = HybridWeedNetwork(num_classes=NUM_CLASSES)
    onnx_model.load_state_dict(torch.load("best_hybrid_weed_model.pth", map_location="cpu"))
    onnx_model.eval()

    dummy_input = torch.randn(1, 3, 224, 224)
    output_filename = "custom_star_lsk_dysample_weed_model.onnx"

    torch.onnx.export(
        onnx_model, dummy_input, output_filename,
        export_params=True, opset_version=14, do_constant_folding=True,
        input_names=['input_image'], output_names=['class_logits'],
        dynamic_axes={'input_image': {0: 'batch_size'}, 'class_logits': {0: 'batch_size'}}
    )
    print(f"[SUCCESS] ONNX runtime target module written cleanly to: {os.path.abspath(output_filename)}")
