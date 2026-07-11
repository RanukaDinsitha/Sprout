#!/usr/bin/env python3
from pathlib import Path
import os
import sys

direct_path = r'C:\Users\ranuk\Downloads\Sprout\model\ai.keras'
print(f'File exists: {Path(direct_path).exists()}')
if Path(direct_path).exists():
    print(f'File size: {Path(direct_path).stat().st_size}')

# Try to load it
try:
    import tensorflow as tf
    from tensorflow.keras.models import load_model
    print(f'Loading from: {direct_path}')
    model = load_model(direct_path)
    print(f'✓ Model loaded successfully!')
    print(f'Output shape: {model.output_shape}')
except Exception as e:
    print(f'✗ Error loading model: {e}')
    import traceback
    traceback.print_exc()
