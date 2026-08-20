
import torch, torchvision.transforms as T, torch.nn as nn, torch.nn.functional as F
from PIL import Image
import sys

# --- CONFIGURATION ---
NUM_CLASSES = 77        # ⚠️ Set to your exact number of training classes
MODEL_PATH = 'sprout.pth' 
IMAGE_PATH = 'yarrow.webp'  

# --- ARCHITECTURE MATCHING YOUR SCRIPT ---
class OptimizedArcFace(nn.Module):
    def __init__(self, in_features, out_classes, s=30.0, m=0.50):
        super().__init__()
        self.s = s
        self.weight = nn.Parameter(torch.FloatTensor(out_classes, in_features))
    def forward(self, features, labels=None):
        return F.linear(F.normalize(features), F.normalize(self.weight)) * self.s

class BioCLIPClassifier(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        import open_clip
        model, _, _ = open_clip.create_model_and_transforms('hf-hub:imageomics/bioclip')
        self.backbone = model.visual
        self.neck = nn.Sequential(nn.BatchNorm1d(512), nn.Linear(512, 512), nn.ReLU())
        self.head = OptimizedArcFace(in_features=512, out_classes=num_classes)
    def forward(self, x):
        return self.head(self.neck(self.backbone(x)))

# --- FIXED LOAD LOGIC FOR DIRECTML (PrivateUse1) ---
model = BioCLIPClassifier(NUM_CLASSES)

# This forcing function strips away the 'PrivateUse1' storage device tag completely
def force_cpu(storage, loc):
    return storage.cpu()

state_dict = torch.load(MODEL_PATH, map_location=force_cpu)
model.load_state_dict(state_dict)
model.eval()

# --- PREDICT ---
transform = T.Compose([
    T.Resize((224, 224)),
    T.ToTensor(),
    T.Normalize([0.481, 0.457, 0.408], [0.268, 0.261, 0.275])
])

img = transform(Image.open(IMAGE_PATH).convert('RGB')).unsqueeze(0)

with torch.no_grad():
    outputs = model(img)
    confidence, predicted_idx = torch.max(F.softmax(outputs, dim=1), dim=1)

print(f'\n🎯 Predicted Class Index: {predicted_idx.item()}')
print(f'📈 Confidence Score: {confidence.item() * 100:.2f}%')

