#!/usr/bin/env python3
"""
Script to download the Vosk voice recognition model
"""

import os
import urllib.request
import zipfile
import shutil

def download_vosk_model():
    """Download and extract the Vosk model"""
    
    # Create models directory if it doesn't exist
    os.makedirs("models", exist_ok=True)
    
    model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
    model_zip = "models/vosk-model-small-en-us-0.15.zip"
    model_dir = "models/vosk-model-small-en-us-0.15"
    
    print("Downloading Vosk model...")
    print(f"URL: {model_url}")
    
    try:
        # Download the model
        urllib.request.urlretrieve(model_url, model_zip)
        print("Download completed!")
        
        # Extract the zip file
        print("Extracting model...")
        with zipfile.ZipFile(model_zip, 'r') as zip_ref:
            zip_ref.extractall("models")
        
        # Clean up the zip file
        os.remove(model_zip)
        print("Model extraction completed!")
        print(f"Model available at: {model_dir}")
        
    except Exception as e:
        print(f"Error downloading model: {e}")
        print("Please download manually from: https://alphacephei.com/vosk/models")
        print("And extract to: models/vosk-model-small-en-us-0.15")

if __name__ == "__main__":
    download_vosk_model() 