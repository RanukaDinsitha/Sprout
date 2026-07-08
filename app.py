from flask import Flask, render_template, request, jsonify
import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array
from tensorflow.keras.applications.efficientnet import preprocess_input
from PIL import Image, ImageOps
from os.path import join
import numpy as np
import io

app = Flask(__name__)

# CONFIGURATION: Change these to match your model's parameters
MODEL_PATH = join("model", "ai.keras")
IMAGE_SIZE = 224 

# 1. MANUALLY DEFINE YOUR NAMES HERE
# CRITICAL: They must be in the exact alphabetical/index order they were trained in!
CLASS_LABELS = [
    'Annual poa',
     'Black nightshade',
     'Blackberry',
     'Bracken',
     'Broad-leaved dock',
     'Broad-leaved fleabane',
     'Broad-leaved plantain',
     'Broom',
     'Californian thistle',
     'Cape weed',
     'Catsear',
     'Chickweed',
     'Cleavers',
     'Clustered dock',
     'Couch',
     'Creeping buttercup',
     'Creeping oxalis',
     'Creeping speedwell',
     'Daisy',
     'Dandelion',
     'Fiddle dock',
     'Field speedwell',
     'Galinsoga',
     'Giant buttercup',
     'Gorse',
     'Great bindweed',
     'Groundsel',
     'Hairy buttercup',
     'Hawkbit',
     'Hawksbeard',
     'Hedge mustard',
     'Hemlock',
     'Hydrocotyle',
     'Ivy',
     'Mallow',
     'Manuka',
     'Mouse-ear hawkweed',
     'Musky storksbill',
     'Narrow-leaved plantain',
     'Nettle',
     'Nodding thistle',
     'Old man’s beard',
     'Onehunga weed',
     'Oxeye daisy',
     'Parsley dropwort',
     'Parsley piert',
     'Paspalum',
     'Pennyroyal',
     'Pink shamrock',
     'Ragwort',
     'Red dead-nettle',
     'Redroot',
     'Scarlet pimpernel',
     'Scotch thistle',
     'Scrambling fumitory',
     'Scrambling speedwell',
     'Selfheal',
     "Sheep's sorrel",
     "Shepherd's purse",
     'Sow thistle',
     'Spurrey',
     'Staggerweed',
     'Stinking mayweed',
     'Suckling clover',
     'Sweet brier',
     'Tauhinu',
     'Tradescantia',
     'Turf speedwell',
     'Twin cress',
     'Water pepper',
     'White clover',
     'Wild radish',
     'Wild turnip',
     'Willow weed',
     'Winged thistle',
     'Wireweed',
     'Yarrow'
]


try:
    model = load_model(MODEL_PATH)
    print("✓ Keras AI Engine successfully loaded into memory.")
    
    NUM_CLASSES = model.output_shape[-1]
    if len(CLASS_LABELS) != NUM_CLASSES:
        print(f"⚠️ WARNING: Your model expects {NUM_CLASSES} classes, but you only provided {len(CLASS_LABELS)} text names in your list!")
        
except Exception as e:
    print(f"⚠️ Critical Error loading model: {e}")
    model = None
    
@app.route('/')
def home():
    # Renders your exact HTML UI
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
        # 1. Read the image stream natively
        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes))
        image = ImageOps.exif_transpose(image).convert('RGB')
        
        # 2. Resize to match your network geometry and preserve quality
        resized_image = image.resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.LANCZOS)
        img_array = img_to_array(resized_image)
        img_array = np.expand_dims(img_array, axis=0)
        
        # 3. Apply the same preprocessing used during training
        img_array = preprocess_input(img_array)

        # 4. Run inference
        predictions = model.predict(img_array, verbose=0)[0]
        top_idx = int(np.argmax(predictions))
        
        return jsonify({
            "class": CLASS_LABELS[top_idx],
            "confidence": f"{predictions[top_idx] * 100:.1f}%"
        })

    except Exception as e:
        return jsonify({"error": f"Inference engine failure: {str(e)}"}), 500

if __name__ == '__main__':
    # Runs a local development server
    app.run(debug=True, port=5000)