import torch
from huggingface_hub import hf_hub_download

print("Finding downloaded model...")

model_path = hf_hub_download(
    repo_id="husseinelsaadi/aidetect-vit-b16",
    filename="runC/checkpoints/best.pt"
)

print("Model found!")
print("Loading checkpoint...")

checkpoint = torch.load(
    model_path,
    map_location="cpu",
    weights_only=False
)

print("\nCheckpoint loaded successfully!")
print("Checkpoint type:", type(checkpoint))

if isinstance(checkpoint, dict):
    print("\nItems inside checkpoint:")

    for key in checkpoint.keys():
        print(" -", key)