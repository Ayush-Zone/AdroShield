---
license: apache-2.0
tags: [image-classification, deepfake-detection, ai-generated-detection,
       insurance, claims, photo-integrity, vision-transformer]
datasets: [Rajarshi-Roy-research/Defactify_Image_Dataset]
---

# Claim Photo Integrity Detector

Detects whether a photo is an **authentic camera photograph** or an **AI-generated synthetic image**.
Built for insurance claim workflows: verify photo integrity *before* damage severity assessment
or total-loss prediction (trust-first FNOL triage).

## Usage

```python
from transformers import pipeline
pipe = pipeline("image-classification",
                model="obuladinnesai/claim-photo-integrity-detector")
pipe("path/to/claim_photo.jpg")
# -> [{'label': 'real', 'score': 0.97}, {'label': 'ai_generated', 'score': 0.03}]
```

## Training
- Base model: `google/vit-base-patch16-224`, fine-tuned with a 2-class head
- Data: balanced subset of the Defactify image dataset
  (real MS-COCO photos vs images from SD 2.1, SDXL, SD 3, DALL-E 3, Midjourney v6)
- See training script for exact config and metrics

## Limitations
- v1 is trained on general scenes, not damage photos specifically.
  A damage-specialized v2 (fine-tuned on real vs manipulated claim photos) is planned.
- Like all AI-image detectors, accuracy degrades on generators newer than the training data.
- Not a legal proof of fraud — a triage signal for human adjusters.
