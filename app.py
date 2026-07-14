import base64
import io
from pathlib import Path
import requests
from flask import Flask, render_template, request, jsonify
from PIL import Image, ImageOps
from ultralytics import YOLO

app = Flask(__name__)

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------
# Toggle CORS support: Set to True when serving external mobile apps or tunnels
CORS_ENABLED = False

if CORS_ENABLED:
    try:
        from flask_cors import CORS
        CORS(app)
        print("Sprout: CORS activated.")
    except ImportError:
        print("Sprout warning: flask_cors module not found. Run 'pip install flask-cors' to enable.")

APP_DIR = Path(__file__).parent
MODELS_DIR = APP_DIR / "models"
MODEL_PATH = MODELS_DIR / "best.pt"
KEY_FILE_PATH = APP_DIR / "key"  # Path to Plant.id API key file


def load_api_key(key_path: Path) -> str:
    """Helper function to load the API key from a local file or txt file."""
    if not key_path.exists():
        key_path_txt = key_path.with_suffix(".txt")
        if key_path_txt.exists():
            key_path = key_path_txt
        else:
            print(f"Sprout warning: Key file not found at {key_path}. Skipping Plant.id setup.")
            return ""

    try:
        with open(key_path, "r", encoding="utf-8") as f:
            key = f.read().strip()
            if key:
                print(f"Sprout has detected and loaded Plant.id API key from {key_path.name}")
                return key
    except Exception as e:
        print(f"Sprout error reading key file {key_path.name}: {e}")

    return ""


# Load Plant.id API Key
PLANT_ID_API_KEY = load_api_key(KEY_FILE_PATH)
PLANT_ID_URL = "https://api.plant.id/v3/identification"


def load_yolo_model(model_path: Path):
    if not model_path.exists():
        print(f"Sprout was unable to locate the model file: {model_path}")
        return None
    try:
        model = YOLO(str(model_path))
        print(f"Sprout has detected and imported model from: {model_path}")
        return model
    except Exception as e:
        print(f"Sprout error loading model at {model_path}: {e}")
        return None


# Initialize Model
model = load_yolo_model(MODEL_PATH)


# ------------------------------------------------------------------------------
# PLANT.ID API HELPER
# ------------------------------------------------------------------------------
def query_plant_id(image_bytes: bytes) -> dict | None:
    """Sends encoded image bytes to Plant.id API v3 as a secondary fallback."""
    if not PLANT_ID_API_KEY:
        print("Sprout warning: Plant.id API key not provided. Skipping web verification.")
        return None

    try:
        encoded_img = base64.b64encode(image_bytes).decode("utf-8")

        headers = {
            "Api-Key": PLANT_ID_API_KEY,
            "Content-Type": "application/json",
        }

        params = {"details": "common_names,description"}

        payload = {
            "images": [f"data:image/jpeg;base64,{encoded_img}"],
            "latitude": None,
            "longitude": None,
            "similar_images": True,
        }

        response = requests.post(
            PLANT_ID_URL, headers=headers, params=params, json=payload, timeout=10
        )

        if response.status_code in (200, 201):
            data = response.json()
            suggestions = (
                data.get("result", {})
                .get("classification", {})
                .get("suggestions", [])
            )
            if suggestions:
                top_suggestion = suggestions[0]
                details = top_suggestion.get("details", {})
                common_names = details.get("common_names", [])

                # Prefer common name, fallback to scientific name
                if common_names:
                    match_name = str(common_names[0]).title()
                else:
                    match_name = str(top_suggestion.get("name", "Unknown Species")).title()

                prob = float(top_suggestion.get("probability", 0.0)) * 100
                print(f"Sprout Plant.id returned: '{match_name}' with {prob:.1f}% certainty")

                return {
                    "class": match_name,
                    "confidence": f"{prob:.1f}%",
                    "model_used": "Plant.id Cloud Verification Engine"
                }
        else:
            print(f"Sprout Plant.id API HTTP error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"Sprout's web verification system encountered an issue: {e}")

    return None


# ------------------------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    if model is None:
        return (
            jsonify({"error": "Sprout has detected that the model file is missing or misconfigured."}),
            500,
        )

    if "file" not in request.files:
        return (
            jsonify({"error": "Sprout has not detected an image payload in the request."}),
            400,
        )

    file = request.files["file"]
    if file.filename == "":
        return (
            jsonify({"error": "Sprout detected no uploaded file."}),
            400,
        )

    try:
        # Read image & fix EXIF orientation
        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")

        # ----------------------------------------------------------------------
        # STEP 1: Run Local 76-Class YOLO Model Inference
        # ----------------------------------------------------------------------
        results = model.predict(source=image, verbose=False)
        result = results[0]

        if result.probs is None:
            print("Sprout: Model returned no probability scores. Requesting Plant.id...")
            plant_id_resp = query_plant_id(img_bytes)
            if plant_id_resp:
                return jsonify(plant_id_resp), 200
            return jsonify({"error": "Sprout was unable to generate classification probabilities."}), 500

        # Pylance-safe PyTorch Tensor parsing for Top-1 and Top-2
        probs = result.probs.data
        top2_values, top2_indices = probs.topk(2)

        top1_idx = int(top2_indices[0].item())
        top1_conf = float(top2_values[0].item())

        top2_conf = float(top2_values[1].item()) if len(top2_values) > 1 else 0.0

        # Calculate dominance margin over 2nd place
        margin = top1_conf - top2_conf

        # Dynamic name lookup & remap
        raw_class = str(result.names[top1_idx])
        class_remap = {
            "Wireweed": "Wireweed"
        }
        predicted_class = class_remap.get(raw_class, raw_class.replace("_", " ")).title()

        # ----------------------------------------------------------------------
        # STEP 2: Apply 76-Class Dynamic Decision Matrix
        # ----------------------------------------------------------------------
        # Rule A: High local conviction (>= 60%)
        if top1_conf >= 0.60:
            return jsonify({
                "class": predicted_class,
                "confidence": f"{top1_conf * 100:.1f}%",
                "model_used": "Sprout Local Engine (High Conviction)"
            }), 200

        # Rule B: Moderate conviction (30%–59%) with dominant margin over #2 (>= 0.12)
        elif top1_conf >= 0.30 and margin >= 0.12:
            return jsonify({
                "class": predicted_class,
                "confidence": f"{top1_conf * 100:.1f}% (Margin: +{margin * 100:.1f}%)",
                "model_used": "Sprout Local Engine (Margin Dominance)"
            }), 200

        # Rule C: Low conviction (< 30%) or tight margin (< 12%) -> Fallback to Plant.id
        else:
            print(f"Sprout: Local model uncertain on '{predicted_class}' ({top1_conf * 100:.1f}%, margin: {margin * 100:.1f}%). Triggering Plant.id...")
            plant_id_resp = query_plant_id(img_bytes)

            if plant_id_resp:
                return jsonify(plant_id_resp), 200

            # Fallback to local prediction if Plant.id call/key fails
            return jsonify({
                "class": predicted_class,
                "confidence": f"{top1_conf * 100:.1f}%",
                "model_used": "Sprout Local Engine (Fallback)"
            }), 200

    except Exception as e:
        return (
            jsonify({"error": f"Sprout's engine had an inference failure: {str(e)}"}),
            500,
        )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "model_loaded": model is not None,
        "cors_enabled": CORS_ENABLED,
        "api_key_loaded": bool(PLANT_ID_API_KEY)
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)