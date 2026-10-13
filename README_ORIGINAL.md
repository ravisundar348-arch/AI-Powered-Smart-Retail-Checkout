# AI-Powered Object Detection and Smart Billing System

This project is an smart retail checkout system that automates product detection, classification, pricing, and billing using computer vision and deep learning. It eliminates manual barcode scanning by detecting products directly from images and integrates dynamic festival pricing, combo offers, and confidence-based validation for reliable automated billing.

## Open in Google Colab

- **Data Augmentation**
  [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/SivaRohithReddy07/AI-Powered-Object-Detection-and-Smart-Billing-System/blob/main/Data_Augmentation.ipynb)

- **Model Training**
  [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/SivaRohithReddy07/AI-Powered-Object-Detection-and-Smart-Billing-System/blob/main/Model_Training.ipynb)

- **Detection, Classification & Billing**
  [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/SivaRohithReddy07/AI-Powered-Object-Detection-and-Smart-Billing-System/blob/main/Detect_Classify_Bill.ipynb)

## Features

- Automated product detection using pretrained YOLOv8m
- Product classification using MobileNetV2 (transfer learning)
- Two-stage YOLO + CNN pipeline: YOLO localizes product regions, MobileNetV2 identifies the product
- Confidence-based human-in-the-loop validation for low-confidence predictions
- IoU-based filtering to remove redundant / nested bounding boxes
- Dynamic festival-based pricing (5%–25% discounts across 9 festival seasons)
- Seasonal pricing adjustment for cold items during summer
- Combo offer detection with a prompt to complete a partial combo (and choose quantities) before billing
- Automated itemized bill generation

## Project Structure

- `Data_Augmentation.ipynb` – dataset augmentation pipeline, splits data into Train / Validation / Test (70% / 15% / 15%)
- `Model_Training.ipynb` – MobileNetV2-based classifier training and evaluation
- `Detect_Classify_Bill.ipynb` – product detection, classification, pricing, and billing pipeline
- `Dataset/` – original product images, organized by class
- `Aug_Dataset/` – augmented Train / Validation / Test splits generated from `Dataset/`
- `Sample_Images/` – sample images used for testing the end-to-end pipeline
- `full_model.keras` – trained MobileNetV2 classifier (full model)
- `custom_model.weights.h5` – trained classifier weights only
- `yolov8m.pt` – pretrained YOLOv8m checkpoint used for product localization

## Dataset

The dataset used in this project was **created manually by capturing images using a camera**.
It consists of real retail product images across 8 product classes, taken under different lighting conditions and angles.
The dataset is included in this repository to ensure reproducibility of results.

## Requirements

- Python 3.x
- Google Colab (recommended) or local GPU environment
- Libraries:
  - `ultralytics` (YOLOv8)
  - `tensorflow`, `keras`
  - `opencv-python`
  - `numpy`, `pillow`
  - `scikit-learn` (evaluation metrics)
  - `seaborn`, `matplotlib` (plots and confusion matrix)

Install Python packages:

    pip install ultralytics tensorflow keras opencv-python numpy pillow scikit-learn seaborn matplotlib

## Setup

1. **Prepare dataset**
   Organize product images into class-wise folders under `Dataset/` (one folder per product class).

2. **Data augmentation**
   Run:

       Data_Augmentation.ipynb

   This augments each class up to a balanced target size, then splits the images into Train (70%), Validation (15%), and Test (15%) sets under `Aug_Dataset/`.

3. **Train the classification model**
   Run:

       Model_Training.ipynb

   This trains a MobileNetV2-based classifier using the Train split, validates on the Validation split, evaluates on the held-out Test split, and saves the trained model (`full_model.keras`).

4. **Detection, pricing, and billing**
   Run:

       Detect_Classify_Bill.ipynb

   This detects product regions with pretrained YOLOv8m, classifies each detected region with the trained MobileNetV2 model, applies festival and combo pricing, and generates the final itemized bill.

## Results

- **92.45% classification accuracy** on the held-out test set
- High-confidence predictions (≥0.8) handled automatically
- Low-confidence predictions flagged and validated via human input
- IoU-based filtering removes redundant/nested detections before classification

## Notes

- Datasets and trained model weights are not included in the GitHub repository due to size limitations; they are stored in the linked Google Drive project folder instead.
- This project is a prototype and can be extended to real-time video streams and large-scale retail deployment.
