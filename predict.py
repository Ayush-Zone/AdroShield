import sys
import json

import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms
from transformers import CLIPVisionModel
from huggingface_hub import hf_hub_download


# -----------------------------
# Settings
# -----------------------------

MODEL_REPO = "husseinelsaadi/aidetect-vit-b16"
CHECKPOINT_FILE = "runC/checkpoints/best.pt"
SUMMARY_FILE = "runC/summary.json"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# -----------------------------
# Model
# -----------------------------

class AIImageDetector(nn.Module):
    def __init__(self):
        super().__init__()

        self.backbone = CLIPVisionModel.from_pretrained(
            "openai/clip-vit-base-patch16"
        )

        self.head = nn.Sequential(
            nn.LayerNorm(768),
            nn.Dropout(0.1),
            nn.Linear(768, 1),
        )

    def forward(self, x):
        output = self.backbone(pixel_values=x)

        # CLS token
        features = output.last_hidden_state[:, 0]

        return self.head(features)


# -----------------------------
# Load trained weights
# -----------------------------

print("Loading AI detector...")

checkpoint_path = hf_hub_download(
    repo_id=MODEL_REPO,
    filename=CHECKPOINT_FILE,
)

summary_path = hf_hub_download(
    repo_id=MODEL_REPO,
    filename=SUMMARY_FILE,
)

checkpoint = torch.load(
    checkpoint_path,
    map_location="cpu",
    weights_only=False,
)

model = AIImageDetector()

model.load_state_dict(
    checkpoint["model"],
    strict=True,
)

model.to(device)
model.eval()


# -----------------------------
# Calibration
# -----------------------------

with open(summary_path, "r") as f:
    summary = json.load(f)

temperature = summary.get("temperature", 1.0)

# Official demo uses 0.71 for general uploaded images.
threshold = 0.71


# -----------------------------
# Image preprocessing
# -----------------------------

preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),

    transforms.Normalize(
        mean=[0.48145466, 0.4578275, 0.40821073],
        std=[0.26862954, 0.26130258, 0.27577711],
    ),
])


# -----------------------------
# Prediction
# -----------------------------

def predict(image_path):

    image = Image.open(image_path).convert("RGB")

    image_tensor = preprocess(image)
    image_tensor = image_tensor.unsqueeze(0).to(device)

    with torch.no_grad():

        logit = model(image_tensor)

        logit = logit / temperature

        ai_probability = torch.sigmoid(logit).item()

    if ai_probability >= threshold:
        prediction = "AI-GENERATED"
        confidence = ai_probability
    else:
        prediction = "REAL"
        confidence = 1 - ai_probability

    print()
    print("Image:", image_path)
    print("Prediction:", prediction)
    print(f"AI probability: {ai_probability * 100:.2f}%")
    print(f"Confidence: {confidence * 100:.2f}%")
    print("Device:", device)


# -----------------------------
# Run from command line
# -----------------------------

if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Usage:")
        print("python predict.py path_to_image")
        sys.exit(1)

    predict(sys.argv[1])