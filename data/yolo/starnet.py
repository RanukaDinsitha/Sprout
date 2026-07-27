from ultralytics import YOLO

# This triggers an automatic background download of the StarNet weights
model = YOLO("openvision/yolo26m-cls") 