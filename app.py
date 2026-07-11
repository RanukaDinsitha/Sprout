import io
import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array
from PIL import Image, ImageOps
import numpy as np
import torch
import torchvision.transforms as transforms
import timm

app = Flask(__name__)

# CONFIGURATION
APP_DIR = Path(__file__).parent
MODELS_DIR = APP_DIR / "models"
IMAGE_SIZE = 224
MODEL_CANDIDATES = [
    MODELS_DIR / "pesti.pt",
    MODELS_DIR / "plight.keras",
]

CLASS_LABELS = [
    'Annual poa', 'Black nightshade', 'Blackberry', 'Bracken', 'Broad-leaved dock',
    'Broad-leaved fleabane', 'Broad-leaved plantain', 'Broom', 'Californian thistle',
    'Cape weed', 'Catsear', 'Chickweed', 'Cleavers', 'Clustered dock', 'Couch',
    'Creeping buttercup', 'Creeping oxalis', 'Creeping speedwell', 'Daisy', 'Dandelion',
    'Fiddle dock', 'Field speedwell', 'Galinsoga', 'Giant buttercup', 'Gorse',
    'Great bindweed', 'Groundsel', 'Hairy buttercup', 'Hawkbit', 'Hawksbeard',
    'Hedge mustard', 'Hemlock', 'Hydrocotyle', 'Ivy', 'Mallow', 'Manuka',
    'Mouse-ear hawkweed', 'Musky storksbill', 'Narrow-leaved plantain', 'Nettle',
    'Nodding thistle', 'Old man’s beard', 'Onehunga weed', 'Oxeye daisy',
    'Parsley dropwort', 'Parsley piert', 'Paspalum', 'Pennyroyal', 'Pink shamrock',
    'Ragwort', 'Red dead-nettle', 'Redroot', 'Scarlet pimpernel', 'Scotch thistle',
    'Scrambling fumitory', 'Scrambling speedwell', 'Selfheal', "Sheep's sorrel",
    "Shepherd's purse", 'Sow thistle', 'Spurrey', 'Staggerweed', 'Stinking mayweed',
    'Suckling clover', 'Sweet brier', 'Tauhinu', 'Tradescantia', 'Turf speedwell',
    'Twin cress', 'Water pepper', 'White clover', 'Wild radish', 'Wild turnip',
    'Willow weed', 'Winged thistle', 'Wireweed', 'Yarrow'
]

# PyTorch Image Transform (Standard ImageNet Normalization)
torch_transforms = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])

def load_model_from_path(model_path: Path):
    if not model_path.exists():
        return None, None

    suffix = model_path.suffix.lower()

    # --- PYTORCH LOADING ---
    if suffix in {'.pt', '.pth'}:
        try:
            state = torch.load(model_path, map_location='cpu')
            model = timm.create_model('efficientnet_b0', pretrained=False, num_classes=len(CLASS_LABELS))
            
            # Extract state dict if nested inside a checkpoint wrapper
            if isinstance(state, dict):
                if 'state_dict' in state:
                    state = state['state_dict']
                elif 'model' in state:
                    state = state['model']

            # Handle DataParallel prefix ('module.')
            if isinstance(state, dict) and any(k.startswith('module.') for k in state.keys()):
                state = {k.replace('module.', '', 1): v for k, v in state.items()}

            model.load_state_dict(state, strict=False)
            model.eval()
            print(f"✓ PyTorch model loaded successfully from {model_path}")
            return model, 'pt'
        except Exception as e:
            print(f"⚠️ Failed to load PyTorch model {model_path}: {e}")
            return None, None

    # --- KERAS LOADING ---
    if suffix in {'.keras', '.h5', '.hdf5'}:
        try:
            model = load_model(model_path)
            print(f"✓ Keras model loaded successfully from {model_path}")
            return model, 'keras'
        except Exception as e:
            print(f"⚠️ Failed to load Keras model {model_path}: {e}")
            return None, None

    return None, None


# Initialize Model
model = None
model_type = None

for candidate in MODEL_CANDIDATES:
    model, model_type = load_model_from_path(candidate)
    if model is not None:
        MODEL_NAME = candidate.name
        break

if model is None:
    print("⚠️ No supported model could be loaded from the models folder.")


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/predict', methods=['POST'])
def predict():
    if model is None:
        return jsonify({"error": "AI Model file is missing or misconfigured on the server."}), 500

    if 'file' not in request.files:
        return jsonify({"error": "No image payload found in request."}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected."}), 400

    try:
        # Load and fix EXIF orientation
        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes))
        image = ImageOps.exif_transpose(image).convert('RGB')

        # --- PYTORCH INFERENCE ---
        if model_type == 'pt':
            input_tensor = torch_transforms(image).unsqueeze(0)  # Shape: [1, 3, 224, 224]
            with torch.no_grad():
                outputs = model(input_tensor)
                # Apply Softmax to get probabilities
                probabilities = torch.nn.functional.softmax(outputs[0], dim=0)
                top_idx = torch.argmax(probabilities).item()
                confidence = probabilities[top_idx].item() * 100

        # --- KERAS INFERENCE ---
        elif model_type == 'keras':
            resized_image = image.resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.LANCZOS)
            img_array = img_to_array(resized_image)
            img_array = np.expand_dims(img_array, axis=0) / 255.0  # Normalization [0, 1]
            
            predictions = model.predict(img_array, verbose=0)[0]
            top_idx = int(np.argmax(predictions))
            confidence = float(predictions[top_idx] * 100)

        return jsonify({
            "class": CLASS_LABELS[top_idx],
            "confidence": f"{confidence:.1f}%"
        })

    except Exception as e:
        return jsonify({"error": f"Inference engine failure: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)