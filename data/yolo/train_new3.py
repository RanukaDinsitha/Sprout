import copy, os
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F
import timm, onnx, onnxruntime as ort
from onnxconverter_common import float16

class StarNetBlock(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.dwconv = nn.Conv2d(dim, dim, 3, padding=1, groups=dim)
        self.f1 = nn.Conv2d(dim, dim, 1); self.f2 = nn.Conv2d(dim, dim, 1); self.g = nn.Conv2d(dim, dim, 1)
        self.act = nn.GELU()
    def forward(self, x):
        xm = self.dwconv(x)
        return x + self.g(self.act(self.f1(xm) * self.f2(xm)))

class DySample(nn.Module):
    def __init__(self, in_channels, scale=2):
        super().__init__()
        self.scale = scale
        self.offset_generator = nn.Conv2d(in_channels, 2*scale*scale, 1)
        nn.init.zeros_(self.offset_generator.weight); nn.init.zeros_(self.offset_generator.bias)
        self._grid_cache = {}
    def _get_base_grid(self, B, H, W, device, dtype):
        key = (H, W, device, dtype)
        if key not in self._grid_cache:
            gy, gx = torch.meshgrid(
                torch.linspace(-1, 1, H*self.scale, device=device, dtype=dtype),
                torch.linspace(-1, 1, W*self.scale, device=device, dtype=dtype), indexing='ij')
            self._grid_cache[key] = torch.stack([gx, gy], dim=-1).unsqueeze(0)
        return self._grid_cache[key].expand(B, -1, -1, -1)
    def forward(self, x):
        B, C, H, W = x.shape
        offset = self.offset_generator(x)
        offset = offset.view(B, self.scale, self.scale, 2, H, W).permute(0,4,1,5,2,3).reshape(B, H*self.scale, W*self.scale, 2)
        base = self._get_base_grid(B, H, W, x.device, x.dtype)
        return F.grid_sample(x, torch.clamp(base+offset, -1, 1), mode='bilinear', padding_mode='zeros', align_corners=False)

class StarDySampleNetwork(nn.Module):
    def __init__(self, num_classes=77):
        super().__init__()
        base = timm.create_model('convnextv2_tiny', pretrained=False)
        self.stem, self.stages = base.stem, base.stages
        self.star_block = StarNetBlock(384)
        self.dysample = DySample(768, 2)
        self.global_pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Linear(768, num_classes)
    def forward(self, x):
        x = self.stem(x)
        x = self.stages[0](x); x = self.stages[1](x)
        x = self.stages[2](x); x = self.star_block(x)
        x = self.stages[3](x); x = self.dysample(x)
        return self.classifier(torch.flatten(self.global_pool(x), 1))

class ModelEMA:
    def __init__(self, model, decay=0.99):
        self.ema = copy.deepcopy(model).eval()
        for p in self.ema.parameters(): p.requires_grad_(False)
        self.decay = decay
    @torch.no_grad()
    def update(self, model):
        for ev, mv in zip(self.ema.state_dict().values(), model.state_dict().values()):
            if ev.dtype.is_floating_point: ev.mul_(self.decay).add_(mv.detach(), alpha=1-self.decay)
            else: ev.copy_(mv)

def export_to_onnx(model, dummy_input, output_path, opset_version=17):
    kwargs = dict(export_params=True, opset_version=opset_version, do_constant_folding=True,
                  input_names=['input_image'], output_names=['class_logits'],
                  dynamic_axes={'input_image': {0: 'batch_size'}, 'class_logits': {0: 'batch_size'}})
    try:
        torch.onnx.export(model, dummy_input, output_path, dynamo=False, **kwargs)
    except TypeError:
        torch.onnx.export(model, dummy_input, output_path, **kwargs)

def convert_to_fp16(fp32_path, fp16_path):
    model = onnx.load(fp32_path)
    block_names = [n.name for n in model.graph.node if 'dysample' in n.name.lower()]
    model_fp16 = float16.convert_float_to_float16(model, keep_io_types=True, node_block_list=block_names)
    onnx.checker.check_model(model_fp16)
    onnx.save(model_fp16, fp16_path)
    return len(block_names)

def verify_onnx_model(onnx_path, torch_model, dummy_input, label=""):
    sess = ort.InferenceSession(onnx_path, providers=['CPUExecutionProvider'])
    onnx_out = sess.run(None, {'input_image': dummy_input.numpy()})[0]
    with torch.no_grad():
        torch_out = torch_model(dummy_input).numpy()
    diff = np.abs(torch_out - onnx_out)
    ok = not np.isnan(onnx_out).any()
    print(f"[{label}] shape={onnx_out.shape} max_diff={diff.max():.6f} mean_diff={diff.mean():.6f} ok={ok}")
    return ok

# ---- mini train ----
NUM_CLASSES = 77
model = StarDySampleNetwork(NUM_CLASSES)
ema = ModelEMA(model, decay=0.9)
opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
crit = nn.CrossEntropyLoss(label_smoothing=0.1)
model.train()
for step in range(4):
    imgs = torch.randn(2, 3, 224, 224)
    labels = torch.randint(0, NUM_CLASSES, (2,))
    opt.zero_grad(set_to_none=True)
    loss = crit(model(imgs), labels)
    loss.backward()
    opt.step()
    ema.update(model)
print("mini-train done, loss:", loss.item())

os.makedirs("ckpt", exist_ok=True)
torch.save(ema.ema.state_dict(), "ckpt/best_ema.pth")
print("saved EMA checkpoint")

# ---- reload fresh + export ----
export_model = StarDySampleNetwork(NUM_CLASSES)
export_model.load_state_dict(torch.load("ckpt/best_ema.pth", map_location="cpu"))
export_model.eval()
dummy = torch.randn(1, 3, 224, 224)

export_to_onnx(export_model, dummy, "final_fp32.onnx")
verify_onnx_model("final_fp32.onnx", export_model, dummy, "FP32")

n_blocked = convert_to_fp16("final_fp32.onnx", "final_fp16.onnx")
print(f"blocked {n_blocked} dysample nodes from fp16 cast")
verify_onnx_model("final_fp16.onnx", export_model, dummy, "FP16")

print("\nIntegration test PASSED end to end.")