import base64
import io
from pathlib import Path
import requests
from flask import Flask, render_template, request, jsonify
from PIL import Image, ImageOps
from ultralytics import YOLO

app = Flask(__name__)

# CONFIGURATION
APP_DIR = Path(__file__).parent
MODELS_DIR = APP_DIR / "models"
MODEL_PATH = MODELS_DIR / "best.pt"
KEY_FILE_PATH = APP_DIR / "key"  # Path to your Plant.id API key file


def load_api_key(key_path: Path) -> str:
    """Helper function to load the API key from a local file."""
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
PLANT_ID_URL = "https://plant.id/api/v3/identification"

# Confidence threshold to trigger web verification (85%)
CONFIDENCE_THRESHOLD = 85.0


def load_yolo_model(model_path: Path):
    if not model_path.exists():
        print(f"Sprout was unable to locate the model's file. Please check file directory as specified: {model_path}")
        return None
    try:
        model = YOLO(str(model_path))
        print(f"Sprout has detected model and has been imported; the path is: {model_path}")
        return model
    except Exception as e:
        print(f"Sprout was unable to load the model due to an error, please view: {model_path}: {e}")
        return None


# Initialize Model
model = load_yolo_model(MODEL_PATH)


def query_plant_id(image_bytes: bytes) -> str | None:
    """Sends the image to Plant.id API for botanical double-check."""
    if not PLANT_ID_API_KEY:
        print("Sprout warning: Plant.id API key not provided. Skipping web verification.")
        return None

    try:
        # Encode image to Base64 format expected by Plant.id v3
        encoded_img = base64.b64encode(image_bytes).decode("utf-8")

        headers = {
            "Api-Key": PLANT_ID_API_KEY,
            "Content-Type": "application/json",
        }

        # Crucial: details parameter tells Plant.id to return common names
        params = {
            "details": "common_names,description"
        }

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

                # Extract top common name or fallback to scientific name
                if common_names:
                    match_name = str(common_names[0]).title()
                else:
                    match_name = str(top_suggestion.get("name", "Unknown Species"))

                prob = top_suggestion.get("probability", 0) * 100
                print(f"Sprout Plant.id returned: '{match_name}' with {prob:.1f}% certainty")
                return match_name
        else:
            print(f"Sprout Plant.id API HTTP error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"Sprout's web verification system encountered an issue: {e}")

    return None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    if model is None:
        return (
            jsonify(
                {"error": "Sprout has detected that the model file is missing or misconfigured on the server."}
            ),
            500,
        )

    if "file" not in request.files:
        return (
            jsonify({"error": "Sprout has not detected an image payload found in request."}),
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

        # Run local YOLO inference
        results = model.predict(source=image, verbose=False)
        result = results[0]

        # Guard check to satisfy static analysis
        if result.probs is None:
            return (
                jsonify(
                    {"error": "Sprout was unable to generate classification probabilities."}
                ),
                500,
            )

        # PyTorch Tensor operations avoid Pylance attribute access errors
        probs = result.probs
        top_idx = int(probs.data.argmax().item())
        confidence = float(probs.data.max().item()) * 100

        # Dynamic name lookup from YOLO metadata
        raw_class = str(result.names[top_idx])

        # REMAP TABLE FOR LOCAL MODEL
        class_remap = {
            "Annual_poa": "Wireweed",
            "Annual poa": "Wireweed",
            "Wireweed": "Annual Poa",
        }

        predicted_class = class_remap.get(raw_class, raw_class.replace("_", " "))
        verification_source = "Sprout Local Engine"

        # Verification fallback if confidence is below threshold
        if confidence < CONFIDENCE_THRESHOLD:
            print(f"Sprout detected low confidence ({confidence:.1f}%). Requesting Plant.id web verification...")
            plant_id_prediction = query_plant_id(img_bytes)

            if plant_id_prediction:
                predicted_class = plant_id_prediction
                verification_source = "Sprout Plant.id Verification Engine"

        # Send successful JSON response back to web client
        return jsonify(
            {
                "class": predicted_class,
                "confidence": f"{confidence:.1f}%",
                "source": verification_source,
            }
        )

    except Exception as e:
        return (
            jsonify({"error": f"Sprout's engine has had an Inference failure: {str(e)}"}),
            500,
        )


if __name__ == "__main__":
    app.run(debug=True, port=5000)