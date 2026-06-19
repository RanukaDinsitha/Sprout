""" import requests

url = "https://lens.google.com/v3/upload"
proxy_url = "http://brd-customer-CUSTOMER_USERNAME-zone-ZONE-NAME:CUSTOMER_PASSWORD@brd.superproxy.io:33335"

proxies = {
    "http": proxy_url,
    "https": proxy_url,
}

# Opening the local file 'cat.jpg'
files = {
    'encoded_image': ('images/image.jpg', open('images/image.jpg', 'rb'), 'image/jpeg')
}

# verify=False mimics the -k (insecure) flag in curl
response = requests.post(url, proxies=proxies, files=files, verify=False)

# Save the JSON response
with open("response-2.json", "w", encoding="utf-8") as f:
    f.write(response.text) """

from flask import Flask, request, jsonify
import os
import tempfile
import requests

app = Flask(__name__)

API_TOKEN = os.getenv("16f6dd0b-c6b4-4114-ac60-eee5b5be335d")
BRIGHTDATA_URL = "https://api.brightdata.com/request"

def identify_plant_with_brightdata(image_path: str):
    # Bright Data docs show the Google Lens file upload flow:
    # https://docs.brightdata.com/api-reference/serp/google-lens/upload-file
    #
    # If your Bright Data Python package exposes a helper, use it here.
    # Otherwise, use the documented HTTP flow.

    with open(image_path, "rb") as f:
        files = {
            "encoded_image": ("images/plant.jpg", f, "image/jpeg")
        }

        response = requests.post(
            "https://lens.google.com/v3/upload",
            files=files,
            verify=False
        )

    response.raise_for_status()
    return response.json()

def pick_best_plant(lens_data):
    candidates = []

    for item in lens_data.get("related_search", []):
        title = item.get("title")
        if title:
            candidates.append(title)

    for item in lens_data.get("images", []):
        title = item.get("title")
        if title:
            candidates.append(title)

    best = candidates[0] if candidates else None
    return best, candidates[:5]

@app.route("/identify-plant", methods=["POST"])
def identify_plant():
    if "image" not in request.files:
        return jsonify({"error": "Missing image file"}), 400

    image = request.files["image"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        image.save(tmp.name)
        tmp_path = tmp.name

    try:
        lens_data = identify_plant_with_brightdata(tmp_path)
        best_plant, candidates = pick_best_plant(lens_data)

        return jsonify({
            "identified_name": best_plant,
            "confidence": "medium" if best_plant else "low",
            "candidates": candidates,
            "source": "Google Lens via Bright Data",
            "raw_summary": {
                "tabs": lens_data.get("tabs", []),
                "related_search_count": len(lens_data.get("related_search", [])),
                "images_count": len(lens_data.get("images", []))
            }
        })

    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

if __name__ == "__main__":
    app.run(debug=True)


