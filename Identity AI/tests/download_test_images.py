import os
import urllib.request

def download_images():
    output_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(output_dir, exist_ok=True)
    
    # Configure custom User-Agent to avoid Wikipedia blocking
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-Agent', 'AdroshieldTest/1.0')]
    urllib.request.install_opener(opener)
    
    images = {
        "obama_id.jpg": "https://upload.wikimedia.org/wikipedia/commons/8/8d/President_Barack_Obama.jpg",
        "obama_selfie.jpg": "https://upload.wikimedia.org/wikipedia/commons/e/e9/Official_portrait_of_Barack_Obama.jpg",
        "jordan_selfie.jpg": "https://upload.wikimedia.org/wikipedia/commons/a/ae/Michael_Jordan_in_2014.jpg"
    }
    
    for filename, url in images.items():
        filepath = os.path.join(output_dir, filename)
        print(f"Downloading {filename}...")
        try:
            urllib.request.urlretrieve(url, filepath)
            print(f"Successfully downloaded to {filepath}")
        except Exception as e:
            print(f"Failed to download {filename}: {e}")

if __name__ == "__main__":
    download_images()
