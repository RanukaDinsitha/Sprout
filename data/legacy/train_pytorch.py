#!/usr/bin/env python3
"""
PyTorch-based training script for weed classification with better transfer learning approach.
Much more reliable than TensorFlow for this use case.
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import torchvision.transforms as transforms
from torchvision.datasets import ImageFolder
import timm
from tqdm import tqdm

# GPU detection: CUDA (NVIDIA) -> DirectML (AMD on Windows) -> CPU
if torch.cuda.is_available():
    device = torch.device('cuda')
    print(f"[NVIDIA GPU] Using NVIDIA GPU: {torch.cuda.get_device_name(0)}")
    print(f"  CUDA Version: {torch.version.cuda}")
    print(f"  GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")
else:
    # Try DirectML for AMD GPUs on Windows
    try:
        import onnxruntime as rt
        providers = rt.get_available_providers()
        if 'DmlExecutionProvider' in providers:
            print("[AMD GPU] Using AMD GPU with DirectML acceleration")
            device = torch.device('cpu')  # Use CPU tensor operations, GPU for inference
            directml_available = True
        else:
            device = torch.device('cpu')
            directml_available = False
            print("[CPU] Using CPU (no GPU acceleration available)")
    except:
        device = torch.device('cpu')
        directml_available = False
        print("[CPU] Using CPU (no GPU acceleration available)")


class EarlyStopping:
    def __init__(self, patience=5, min_delta=0):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = None

    def __call__(self, val_loss):
        if self.best_loss is None:
            self.best_loss = val_loss
        elif val_loss > self.best_loss - self.min_delta:
            self.counter += 1
            if self.counter >= self.patience:
                return True
        else:
            self.best_loss = val_loss
            self.counter = 0
        return False


def get_transforms(img_size=224, augment=True):
    """Get data transforms. Augmentation happens BEFORE normalization for correctness."""
    if augment:
        train_transform = transforms.Compose([
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.3),
            transforms.RandomRotation(degrees=15),
            transforms.RandomAffine(degrees=0, translate=(0.1, 0.1)),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.RandomResizedCrop(img_size, scale=(0.8, 1.0)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                               std=[0.229, 0.224, 0.225])
        ])
    else:
        train_transform = transforms.Compose([
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                               std=[0.229, 0.224, 0.225])
        ])

    val_transform = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                           std=[0.229, 0.224, 0.225])
    ])

    return train_transform, val_transform


def build_model(num_classes, model_name='efficientnet_b0', pretrained=True):
    """Build model using timm library (better than torchvision for this)."""
    print(f"Building {model_name} with {num_classes} classes...")
    model = timm.create_model(model_name, pretrained=pretrained, num_classes=num_classes)
    return model


def train_epoch(model, train_loader, criterion, optimizer, device, scaler=None):
    """Train for one epoch."""
    model.train()
    total_loss = 0
    correct = 0
    total = 0

    pbar = tqdm(train_loader, desc="Training", leave=False)
    for images, labels in pbar:
        images = images.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()

        if scaler:
            with torch.autocast(device_type='cuda' if device.type == 'cuda' else 'cpu'):
                outputs = model(images)
                loss = criterion(outputs, labels)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
        else:
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        total_loss += loss.item()
        _, predicted = torch.max(outputs.data, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

        pbar.set_postfix({'loss': loss.item()})

    avg_loss = total_loss / len(train_loader)
    accuracy = 100 * correct / total
    return avg_loss, accuracy


def validate(model, val_loader, criterion, device):
    """Validate the model."""
    model.eval()
    total_loss = 0
    correct = 0
    total = 0

    with torch.no_grad():
        pbar = tqdm(val_loader, desc="Validating", leave=False)
        for images, labels in pbar:
            images = images.to(device)
            labels = labels.to(device)

            outputs = model(images)
            loss = criterion(outputs, labels)

            total_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

    avg_loss = total_loss / len(val_loader)
    accuracy = 100 * correct / total
    return avg_loss, accuracy


def train_model(args):
    """Main training loop."""
    os.makedirs(args.output_dir, exist_ok=True)

    # Load data
    train_transform, val_transform = get_transforms(args.img_size, augment=True)

    train_dataset = ImageFolder(
        root=os.path.join(args.data_dir, 'train'),
        transform=train_transform
    )
    val_dataset = ImageFolder(
        root=os.path.join(args.data_dir, 'val'),
        transform=val_transform
    )

    num_classes = len(train_dataset.classes)
    print(f"Found {num_classes} classes")
    print(f"Training samples: {len(train_dataset)}")
    print(f"Validation samples: {len(val_dataset)}")

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=8 if device.type == 'cuda' else 2,
        pin_memory=True if device.type == 'cuda' else False,
        persistent_workers=True if device.type == 'cuda' else False
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=8 if device.type == 'cuda' else 2,
        pin_memory=True if device.type == 'cuda' else False,
        persistent_workers=True if device.type == 'cuda' else False
    )

    # Build model
    model = build_model(num_classes, model_name='efficientnet_b0', pretrained=True)
    model = model.to(device)

    # Optimizer and loss
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=10, T_mult=2, eta_min=1e-6
    )

    scaler = torch.cuda.amp.GradScaler() if device.type == 'cuda' else None
    early_stop = EarlyStopping(patience=args.early_stopping_patience, min_delta=0.001)

    best_acc = 0
    best_model_path = os.path.join(args.output_dir, 'best_model.pt')

    print(f"\nStarting training for {args.epochs} epochs...")
    print(f"Learning rate: {args.learning_rate}")
    print(f"Batch size: {args.batch_size}")

    for epoch in range(args.epochs):
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device, scaler)
        val_loss, val_acc = validate(model, val_loader, criterion, device)
        scheduler.step(epoch + val_loss / 100)  # Smoother scheduling

        print(f"Epoch {epoch + 1}/{args.epochs} | "
              f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.2f}% | "
              f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.2f}%")

        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), best_model_path)
            print(f"  [BEST] Best model saved (val_acc: {val_acc:.2f}%)")

        if early_stop(val_loss):
            print(f"\nEarly stopping triggered after {epoch + 1} epochs")
            break

    # Load best model and save final checkpoint
    model.load_state_dict(torch.load(best_model_path))
    final_model_path = os.path.join(args.output_dir, 'final_model.pt')
    torch.save(model.state_dict(), final_model_path)

    print(f"\n[DONE] Training complete!")
    print(f"Best model saved to: {best_model_path}")
    print(f"Final model saved to: {final_model_path}")
    print(f"Best validation accuracy: {best_acc:.2f}%")

    return best_model_path, final_model_path


def main():
    parser = argparse.ArgumentParser(description='Train weed classifier with PyTorch')
    parser.add_argument('--data_dir', default='dataset_prepared', help='Path to dataset root (train/val split)')
    parser.add_argument('--output_dir', default='outputs_pytorch', help='Output directory for models')
    parser.add_argument('--img_size', type=int, default=224)
    parser.add_argument('--batch_size', type=int, default=64, help='Batch size (use larger on GPU)')
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--learning_rate', type=float, default=1e-3)
    parser.add_argument('--early_stopping_patience', type=int, default=8)

    args = parser.parse_args()

    # Verify data directory exists
    if not os.path.exists(args.data_dir):
        print(f"Error: Data directory '{args.data_dir}' not found!")
        sys.exit(1)

    train_model(args)


if __name__ == '__main__':
    main()
