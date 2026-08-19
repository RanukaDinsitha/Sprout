import os
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets, transforms
import torch_directml
import pyjokes
from tqdm import tqdm
import shutil
from PIL import Image

# --- THE VERSION TRICK ---
torch.__version__ = "2.5.0" 

try:
    import open_clip
except ImportError:
    print("❌ Missing open_clip. Run: pip install open-clip-torch")
    sys.exit()

# --- CONFIGURATION ---
DATA_DIR = "Dataset"
BATCH_SIZE = 4          
ACCUMULATION_STEPS = 16 
EPOCHS = 20
SAVE_NAME = "sprout.pth"

device = torch_directml.device()
print(f"🌱 Sprout initialized on: {device}")

# --- FAULT TOLERANT DATASET ---
class SafeDataset(Dataset):
    def __init__(self, dataset):
        self.dataset = dataset

    def __getitem__(self, index):
        try:
            return self.dataset[index]
        except Exception as e:
            path, _ = self.dataset.samples[index]
            print(f"\n⚠️ Skipping corrupt image: {path}")
            # Try to return the next image instead
            return self.__getitem__((index + 1) % len(self.dataset))

    def __len__(self):
        return len(self.dataset)

# --- MODEL ARCHITECTURE ---
class OptimizedArcFace(nn.Module):
    def __init__(self, in_features, out_classes, s=30.0, m=0.50):
        super().__init__()
        self.s = s
        self.m = m
        self.cos_m = torch.cos(torch.tensor(m))
        self.sin_m = torch.sin(torch.tensor(m))
        self.th = torch.cos(torch.tensor(3.14159265 - m))
        self.mm = torch.sin(torch.tensor(3.14159265 - m)) * m
        self.weight = nn.Parameter(torch.FloatTensor(out_classes, in_features))
        nn.init.kaiming_uniform_(self.weight, a=1)

    def forward(self, features, labels=None):
        cosine = F.linear(F.normalize(features), F.normalize(self.weight))
        if labels is None: return cosine * self.s
        cosine = cosine.clamp(-1.0 + 1e-7, 1.0 - 1e-7)
        sine = torch.sqrt(1.0 - torch.pow(cosine, 2))
        phi = cosine * self.cos_m - sine * self.sin_m
        phi = torch.where(cosine > self.th, phi, cosine - self.mm)
        one_hot = torch.zeros_like(cosine)
        one_hot.scatter_(1, labels.view(-1, 1).long(), 1.0)
        return ((one_hot * phi) + ((1.0 - one_hot) * cosine)) * self.s

class BioCLIPClassifier(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        model, _, _ = open_clip.create_model_and_transforms('hf-hub:imageomics/bioclip')
        self.backbone = model.visual
        for param in self.backbone.parameters():
            param.requires_grad = False
        
        self.neck = nn.Sequential(
            nn.BatchNorm1d(512),
            nn.Linear(512, 512),
            nn.ReLU()
        )
        self.head = OptimizedArcFace(in_features=512, out_classes=num_classes)

    def forward(self, x, labels=None):
        with torch.no_grad():
            feat = self.backbone(x)
        return self.head(self.neck(feat), labels)

# --- TRAINING ---
def train():
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.481, 0.457, 0.408], [0.268, 0.261, 0.275])
    ])

    # Wrap standard ImageFolder in our SafeDataset
    raw_train = datasets.ImageFolder(os.path.join(DATA_DIR, "train"), transform=transform)
    raw_val = datasets.ImageFolder(os.path.join(DATA_DIR, "val"), transform=transform)
    
    train_ds = SafeDataset(raw_train)
    val_ds = SafeDataset(raw_val)
    
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    model = BioCLIPClassifier(len(raw_train.classes)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)

    print(f"\n🚀 Starting training on {len(raw_train.classes)} classes.")

    for epoch in range(1, EPOCHS + 1):
        model.train()
        optimizer.zero_grad()
        
        pbar = tqdm(train_loader, desc=f"Epoch {epoch}", dynamic_ncols=True)
        for i, (imgs, labels) in enumerate(pbar):
            imgs, labels = imgs.to(device), labels.to(device)
            
            outputs = model(imgs, labels)
            loss = criterion(outputs, labels)
            
            loss = loss / ACCUMULATION_STEPS
            loss.backward()
            
            if (i + 1) % ACCUMULATION_STEPS == 0:
                optimizer.step()
                optimizer.zero_grad()
            
            pbar.set_postfix(loss=f"{loss.item() * ACCUMULATION_STEPS:.4f}")

        # Validation
        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for imgs, labels in val_loader:
                imgs, labels = imgs.to(device), labels.to(device)
                outputs = model(imgs)
                _, pred = outputs.max(1)
                total += labels.size(0)
                correct += pred.eq(labels).sum().item()
        
        print(f"\n✅ Epoch {epoch} Acc: {100.*correct/total:.2f}%")
        print(f"💬 Joke: {pyjokes.get_joke()}")
        torch.save(model.state_dict(), SAVE_NAME)

if __name__ == "__main__":
    train()