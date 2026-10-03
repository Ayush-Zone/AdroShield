from huggingface_hub import hf_hub_download

print("Starting model download...")

model_path = hf_hub_download(
    repo_id="husseinelsaadi/aidetect-vit-b16",
    filename="runC/checkpoints/best.pt"
)

print("Download complete!")
print("Model saved at:")
print(model_path)