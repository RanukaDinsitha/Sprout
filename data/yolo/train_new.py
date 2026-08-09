import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
import torchvision.transforms as T
from tqdm import tqdm
import torch_directml

# =======================================================
# 1. CORE CUSTOM ARCHITECTURE MATHEMATICS
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
        x1 = self.f1(x_mapped)
        x2 = self.f2(x_mapped)
        return shortcut + self.g(self.act(x1 * x2))

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
        sampling_grid = torch.clamp(base_grid + offset, -1, 1)
        return F.grid_sample(x, sampling_grid, mode='bilinear', padding_mode='zeros', align_corners=False)

class CustomWeedClassifier(nn.Module):
    def __init__(self, num_classes=77):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv2d(3, 64, kernel_size=4, stride=4), nn.BatchNorm2d(64))
        self.backbone_stage = nn.Sequential(StarNetBlock(dim=64), LSKBlock(dim=64), StarNetBlock(dim=64))
        self.upsampler = DySample(in_channels=64, scale=2)
        self.head_conv = nn.Conv2d(64, 256, kernel_size=3, stride=2, padding=1)
        self.global_pool = nn.AdaptiveAvgPool2d(1)
        self.fc_classifier = nn.Linear(256, num_classes)

    def forward(self, x):
        x = self.stem(x)
        x = self.backbone_stage(x)
        x = self.upsampler(x)
        x = self.head_conv(x)
        x = self.global_pool(x)
        return self.fc_classifier(torch.flatten(x, 1))

# =======================================================
# 2. SEPARATED RUNTIME WORKER FUNCTIONS
# =======================================================
def train_one_epoch(model, loader, criterion, optimizer, device, epoch):
    model.train()
    loop = tqdm(loader, desc=f"Epoch [{epoch+1}/30]")
    for images, labels in loop:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad(set_to_none=True)
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        loop.set_postfix(loss=loss.item())

def evaluate(model, loader, device):
    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        loop_val = tqdm(loader, desc="Validating")
        for images, labels in loop_val:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
    acc = 100.0 * correct / total
    print(f"--> Current Local Validation Accuracy: {acc:.2f}%\n")
    return acc

# =======================================================
# 3. PROTECTED MULTIPROCESSING MAIN EXECUTOR ENTRY POINT
# =======================================================
if __name__ == '__main__':
    # Environmental configuration Variables - Points directly to your pre-extracted yolo path
    DATASET_ROOT = "C:/Users/ranuk/Downloads/Sprout/data/yolo/images"
    NUM_CLASSES = 77
    BATCH_SIZE = 32
    EPOCHS = 30

    TRAIN_ROOT = os.path.join(DATASET_ROOT, "train")
    VAL_ROOT = os.path.join(DATASET_ROOT, "val")

    # Map the DirectML Compute Engine Device Context safely
    DEVICE = torch_directml.device()
    print(f"\n[AMD PROCESSOR INITIALIZED] Target Allocation: {DEVICE}")

    # Transforms processing arrays
    train_transform = T.Compose([
        T.Resize((224, 224)),
        T.RandomHorizontalFlip(p=0.5),
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

    # Windows handles Multi-Processing loaders cleanly when locked within entry block safely
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=2, pin_memory=True)

    model = CustomWeedClassifier(num_classes=NUM_CLASSES).to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.05)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    print("\n--- Training Custom StarNet-LSK-DySample Array On Local AMD Compute Shaders ---")
    best_acc = 0.0
    for epoch in range(EPOCHS):
        train_one_epoch(model, train_loader, criterion, optimizer, DEVICE, epoch)
        val_acc = evaluate(model, val_loader, DEVICE)
        scheduler.step()
        
        if val_acc > best_acc:
            best_acc = val_acc
            # Save local high precision checkpoint tracking layer parameter matrices
            torch.save(model.state_dict(), "best_local_weed_model.pth")

    # =======================================================
    # 4. INSTANT DIRECT AUTOMATIC ONNX MODEL EXPORT
    # =======================================================
    print("\n--- Training Pipeline Concluded. Compiling Deployment ONNX Target Engine ---")
    
    # Re-instantiate a pure evaluation structure on standard CPU context for ONNX tracing
    onnx_export_model = CustomWeedClassifier(num_classes=NUM_CLASSES)
    onnx_export_model.load_state_dict(torch.load("best_local_weed_model.pth", map_location="cpu"))
    onnx_export_model.eval()

    # Create a dummy image tensor tracking sample input sizes (1 Image, 3 Color Layers, 224x224 Resolution)
    dummy_input = torch.randn(1, 3, 224, 224)
    onnx_output_filename = "custom_star_lsk_dysample_weed_model.onnx"

    # Export structural execution path layers into uniform open-source neural network exchange formats
    torch.onnx.export(
        onnx_export_model,              # The active parameter architecture model
        dummy_input,                    # Frame dimensions blueprint trace parameter
        onnx_output_filename,           # Targeted output path layout file 
        export_params=True,             # Embed trained parameter weights internally inside output matrix
        opset_version=17,               # Opset version supporting specialized mesh functions
        do_constant_folding=True,       # Optimize structural execution layers mathematically
        input_names=['input_image'],    # Define clear entry point string mappings for app tracking
        output_names=['class_logits'],  # Output vector identification index
        dynamic_axes={
            'input_image': {0: 'batch_size'}, # Allow app calls to process dynamic image array batches 
            'class_logits': {0: 'batch_size'}
        }
    )
    
    print(f"[ONNX EXPORT SUCCESSFUL] Engine compiled cleanly as: {os.path.abspath(onnx_output_filename)}")
