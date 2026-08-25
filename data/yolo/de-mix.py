import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import open_clip

OUTPUT_ONNX = "sproutx.onnx"
NUM_CLASSES = 77  

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



# =====================================================================
# CLEAN EXPORT ROUTINE
# =====================================================================
print("🌱 Initializing architecture...")
model = BioCLIPClassifier(num_classes=NUM_CLASSES)

# 👇 FIX 1: Point to the actual .pth weights file, NOT the .onnx file
PTH_WEIGHTS = "sprout.pth" 

print(f"📥 Loading checkpoints from {PTH_WEIGHTS}...")
# 👇 FIX 2: Added weights_only=False to bypass the PyTorch unpickling restriction safely
checkpoint = torch.load(PTH_WEIGHTS, map_location=torch.device('cpu'), weights_only=False)
model.load_state_dict(checkpoint)

print("✨ Stripping all Float16 parameters and converting to standard Float32...")
model = model.float()  # Concurrently upcasts every sub-tensor to FP32
model.eval()           # Freezes BatchNorm dynamics to guarantee static export execution

# Build a standard pure float32 tracking canvas
dummy_input = torch.randn(1, 3, 224, 224, dtype=torch.float32)

print("🚀 Exporting model graph to ONNX...")
torch.onnx.export(
    model, 
    dummy_input, 
    OUTPUT_ONNX,
    export_params=True,
    opset_version=14,  # Opset 14 natively flattens data structures to eliminate Cast nodes
    input_names=['input'],
    output_names=['output'],
    dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
)

print(f"🎉 Complete! Pure Float32 model successfully generated at:\n👉 {OUTPUT_ONNX}")
