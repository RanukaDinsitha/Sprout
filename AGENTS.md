# AI Plant & Weed Detection Project or a.k.a Sprout

- For humans that are viewing this file, please note that this is for AI agents and not human beings. 

## Project Context
This application detects plants and weeds using an Ultralytics YOLO model exported to ONNX format. The backend is powered by Python and Flask, which serves both the API endpoints and a lightweight HTML frontend.

## Tech Stack
- **Backend:** Python 3.10, Flask (API & routing)
- **AI/ML:** Ultralytics (YOLO), ONNX Runtime (inference), Pillow (image handling)
- **Frontend:** HTML5, CSS, Vanilla JavaScript (Fetch API)

## Commands
- **Install Dependencies:** `pip install flask ultralytics onnxruntime pillow`
- **Run Flask Server:** `python app.py`
- **Export YOLO to ONNX:** `yolo export model=best.pt format=onnx`

## Code Guidelines
- **Image Processing:** Use Pillow (`Image.open`) to load images before passing them to the ONNX model.
- **Flask Routes:** Separate the frontend route (`/`) from the prediction API endpoint (`/predict`).
- **Response Format:** Return predictions as JSON containing labels, confidence scores, and bounding box coordinates.

## Boundaries
### Always Do
- Validate that the incoming file is a valid image using Pillow inside a `try/except` block.
- Close image file streams immediately after inference to prevent memory leaks.

### Ask First
- Upgrading Python past 3.10 or introducing heavy JavaScript frameworks.

### Never Do
- Do not save uploaded images to the server disk; process them directly from the memory stream.
- Do not run inference using the `.pt` file in production; strictly use the ONNX Runtime session. (unless told so)
