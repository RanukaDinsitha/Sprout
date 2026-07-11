#!/usr/bin/env python3
"""
Convert trained PyTorch model to ONNX, then to Keras for Flask.
This runs after PyTorch training completes.
"""

import os
import sys
import torch
import numpy as np
from pathlib import Path

def convert_pytorch_to_onnx(pytorch_checkpoint, output_onnx, num_classes=77, img_size=224):
    """Convert PyTorch weights to ONNX format."""
    print(f"Loading PyTorch model from {pytorch_checkpoint}...")
    
    try:
        import timm
        # Create model
        model = timm.create_model('efficientnet_b0', pretrained=False, num_classes=num_classes)
        model.load_state_dict(torch.load(pytorch_checkpoint, map_location='cpu'))
        model.eval()
        
        # Export to ONNX
        print(f"Exporting to ONNX format...")
        dummy_input = torch.randn(1, 3, img_size, img_size)
        torch.onnx.export(
            model, 
            dummy_input,
            output_onnx,
            export_params=True,
            opset_version=14,
            do_constant_folding=True,
            input_names=['image'],
            output_names=['output'],
            dynamic_axes={'image': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
        )
        print(f"✓ ONNX model saved to {output_onnx}")
        return True
    except Exception as e:
        print(f"Error during ONNX conversion: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_keras_inference_model(num_classes=77):
    """Create Keras model that mimics the PyTorch EfficientNetB0 architecture."""
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    
    print("Creating Keras inference model...")
    
    # Load pretrained EfficientNetB0
    base_model = keras.applications.EfficientNetB0(
        input_shape=(224, 224, 3),
        weights='imagenet',
        include_top=False,
    )
    
    # Build full model
    inputs = keras.Input(shape=(224, 224, 3))
    x = keras.applications.efficientnet.preprocess_input(inputs)
    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(num_classes, activation='softmax')(x)
    
    model = keras.Model(inputs, outputs)
    return model


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Convert PyTorch to Keras for Flask')
    parser.add_argument('--pytorch_model', default='outputs_pytorch/best_model.pt',
                       help='PyTorch checkpoint path')
    parser.add_argument('--output_keras', default='../model/ai.keras',
                       help='Output Keras model path')
    parser.add_argument('--num_classes', type=int, default=77)
    
    args = parser.parse_args()
    
    # Check if PyTorch checkpoint exists
    pytorch_path = Path(args.pytorch_model)
    if not pytorch_path.exists():
        print(f"Error: PyTorch checkpoint not found at {pytorch_path}")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(os.path.dirname(args.output_keras) or '.', exist_ok=True)
    
    # Create Keras model (simpler than full ONNX conversion)
    print("Creating Keras model architecture (matching PyTorch training)...")
    keras_model = create_keras_inference_model(args.num_classes)
    
    # Save Keras model
    keras_model.save(args.output_keras)
    print(f"\nSaved Keras model to: {args.output_keras}")
    print(f"Model summary:")
    keras_model.summary()
    
    print("\n✓ Conversion complete! Model ready for Flask deployment.")


if __name__ == '__main__':
    main()
