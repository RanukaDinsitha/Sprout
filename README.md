# Image training with TensorFlow (transfer learning)

This workspace provides a training pipeline using TensorFlow and transfer learning (EfficientNetB0). It supports training on CIFAR-10 (default) or a directory of images organized by class.

Quick start:

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Train on CIFAR-10 (default):

```bash
python train.py --dataset cifar10 --epochs 30 --batch_size 64 --img_size 224 --output_dir outputs
```

3. Train on a directory dataset (structured as class subfolders):

```bash
python train.py --dataset dir --data_dir path/to/images --epochs 30
```

Notes:
- The pipeline uses transfer learning with EfficientNetB0, data augmentation, and fine-tuning. Typical modern image datasets can reach >90% depending on difficulty and class count.
- For best results: increase `--epochs`, experiment with `--fine_tune_at`, and provide a clean balanced dataset.

Preparing a plant dataset (79 classes, ~100 images/class):

If you have a parent folder where each subfolder is a plant class containing images, run:

```bash
python prepare_dataset.py --source_dir raw_plants --dest_dir dataset_prepared \
	--num_classes 79 --images_per_class 100 --val_split 0.2
```

This creates `dataset_prepared/train/<class>` and `dataset_prepared/val/<class>` folders ready for training with `--dataset dir --data_dir dataset_prepared`.
# Sprout

[!Image of a sprout][(https://www.flaticon.com/free-icon/sprout_628297](https://cdn.vectorstock.com/i/500p/24/71/plant-sprout-icon-image-vector-17642471.jpg)

Sprout is a handy litte--and lite--app which determines plant species based on photos.

![Google Drive](https://img.shields.io/badge/Google%20Drive-4285F4?style=for-the-badge&logo=googledrive&logoColor=white) 
![HTML5](https://img.shields.io/badge/html5-%23E34F26.svg?style=for-the-badge&logo=html5&logoColor=white) 
![Bootstrap](https://img.shields.io/badge/bootstrap-%238511FA.svg?style=for-the-badge&logo=bootstrap&logoColor=white) 
![JavaScript](https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E) 
![Cloudflare](https://img.shields.io/badge/Cloudflare-F38020?style=for-the-badge&logo=Cloudflare&logoColor=white)
