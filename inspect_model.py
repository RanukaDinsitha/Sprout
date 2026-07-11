from pathlib import Path
import torch
p = Path('models/pesti.pt')
print('exists', p.exists(), 'size', p.stat().st_size)
data = torch.load(p, map_location='cpu')
print('type', type(data))
if hasattr(data, 'keys'):
    print('keys', list(data.keys())[:20])
    if isinstance(data, dict) and 'state_dict' in data:
        print('state_dict keys', list(data['state_dict'].keys())[:10])
else:
    print('no keys')
