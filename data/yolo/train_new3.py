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
# 1. CLEAN CUSTOM MODULE ARRAYS
# =======================================================

# --- STARNET MODULE (CVPR 2024 Non-linear Star Product) ---
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
        # Element-wise kernel trick simulation without widening dimensions
        return shortcut + self.g(self.act(self.f1(x_mapped) * self.f2(x_mapped)))

# --- DYSAMPLE MODULE (ICCV 2023 Dynamic Point-Sampling Upsampler) ---
class DySample(nn.Module):
    def __init__(self, in_channels, scale=2):
        super().__init__()
        self.scale = scale
        # Ultra-lightpoint generation avoiding heavy convolutions or custom CUDA
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
# 2. HYBRID NETWORK STRUCTURAL INJECTION DEFINITION
# =======================================================
class StarDySampleNetwork(nn.Module):
    def __init__(self, num_classes=77):
        super().__init__()
        print("Extracting pretrained backbone parameters...")
        base_net = timm.create_model('convnextv2_tiny', pretrained=True)
        
        # Splicing custom modules securely into internal features
        self.stem = base_net.stem
        self.stages = base_net.stages  # Master layer collection module array
        
        # Inject StarNet safely right at the 384-channel block marker boundary
        self.star_block = StarNetBlock(dim=384)
        
        # Inject DySample at the final 768-channel feature map intersection 
        self.dysample = DySample(in_channels=768, scale=2)
        
        self.global_pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Linear(768, num_classes)

    def forward(self, x):
        x = self.stem(x)
        
        # Run through first two structural layers natively (96 -> 192 channels)
        x = self.stages[0](x)
        x = self.stages[1](x)
        
        # Run Stage 2 (384 channels) then immediately refine with StarNet feature product mapping
        x = self.stages[2](x)
        x = self.star_block(x)
        
        # Run Stage 3 (768 channels) then upscale feature resolutions cleanly using DySample
        x = self.stages[3](x)
        x = self.dysample(x)
        
        x = self.global_pool(x)
        return self.classifier(torch.flatten(x, 1))

# =======================================================
# 3. RUNTIME PIPELINE EXECUTOR ENTRY POINT
# =======================================================
if __name__ == '__main__':
    DATASET_ROOT = "C:/Users/ranuk/Downloads/Sprout/data/yolo/images"
    NUM_CLASSES = 77
    BATCH_SIZE = 32
    EPOCHS = 30

    TRAIN_ROOT = os.path.join(DATASET_ROOT, "train")
    VAL_ROOT = os.path.join(DATASET_ROOT, "val")

    DEVICE = torch_directml.device()
    print(f"\n[AMD ACCELERATION ENGAGED] Using DirectML Device: {DEVICE}")

    # Standard augmentations for classification tasks
    train_transform = T.Compose([
        T.Resize((224, 224)),
        T.RandomHorizontalFlip(p=0.5),
        T.RandomVerticalFlip(p=0.5),
        T.RandomRotation(degrees=15),
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

    model = StarDySampleNetwork(num_classes=NUM_CLASSES).to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=0.05)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    print("\n--- Fine-Tuning StarNet + DySample Hybrid Network ---")
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
            for images, labels in tqdm(val_loader, desc="Validating"):
                images, labels = images.to(DEVICE), labels.to(DEVICE)
                outputs = model(images)
                _, predicted = outputs.max(1)
                total += labels.size(0)
                correct += predicted.eq(labels).sum().item()
        
        val_acc = 100.0 * correct / total
        print(f"--> Epoch [{epoch+1}/{EPOCHS}] Complete. Validation Accuracy: {val_acc:.2f}%\n")
        scheduler.step()
        
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), "best_star_dysample_model.pth")

    # =======================================================
    # 4. EXPORT TO DEPLOYABLE ONNX MATRIX
    # =======================================================
    print("\n--- Compiling Production ONNX Runtime Package ---")
    onnx_model = StarDySampleNetwork(num_classes=NUM_CLASSES)
    onnx_model.load_state_dict(torch.load("best_star_dysample_model.pth", map_location="cpu"))
    onnx_model.eval()

    dummy_input = torch.randn(1, 3, 224, 224)
    output_filename = "custom_star_dysample_weed_model.onnx"

    torch.onnx.export(
        onnx_model, dummy_input, output_filename,
        export_params=True, opset_version=14, do_constant_folding=True,
        input_names=['input_image'], output_names=['class_logits'],
        dynamic_axes={'input_image': {0: 'batch_size'}, 'class_logits': {0: 'batch_size'}}
    )
    print(f"[ONNX EXPORT SUCCESSFUL] Engine compiled cleanly as: {os.path.abspath(output_filename)}")
