"""
Download Piper voice models from Hugging Face.

Usage:
    python download_voice.py [voice_name]
    
Examples:
    python download_voice.py en_US-lessac-medium
    python download_voice.py en_US-amy-medium
"""

import argparse
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "httpx"], check=True)
    import httpx


# Common voice models
VOICE_CATALOG = {
    "en_US-lessac-medium": "en/en_US/lessac/medium",
    "en_US-lessac-high": "en/en_US/lessac/high",
    "en_US-amy-medium": "en/en_US/amy/medium",
    "en_US-ryan-medium": "en/en_US/ryan/medium",
    "en_GB-alan-medium": "en/en_GB/alan/medium",
    "en_GB-alba-medium": "en/en_GB/alba/medium",
}

BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def download_voice(voice_name: str, models_dir: Path):
    """Download a Piper voice model."""
    
    # Get voice path
    if voice_name in VOICE_CATALOG:
        voice_path = VOICE_CATALOG[voice_name]
    else:
        # Try to construct path from voice name
        parts = voice_name.split("-")
        if len(parts) >= 3:
            lang_region = parts[0]
            name = parts[1]
            quality = parts[2]
            lang = lang_region.split("_")[0]
            voice_path = f"{lang}/{lang_region}/{name}/{quality}"
        else:
            print(f"Unknown voice: {voice_name}")
            print(f"Available voices: {', '.join(VOICE_CATALOG.keys())}")
            return False

    models_dir.mkdir(parents=True, exist_ok=True)
    
    files = [
        f"{voice_name}.onnx",
        f"{voice_name}.onnx.json",
    ]
    
    print(f"Downloading voice: {voice_name}")
    print(f"From: {BASE_URL}/{voice_path}/")
    print(f"To: {models_dir}/")
    print()
    
    with httpx.Client(follow_redirects=True, timeout=60.0) as client:
        for filename in files:
            url = f"{BASE_URL}/{voice_path}/{filename}"
            dest = models_dir / filename
            
            if dest.exists():
                print(f"  ✓ {filename} (already exists)")
                continue
            
            print(f"  ↓ Downloading {filename}...", end=" ", flush=True)
            
            try:
                response = client.get(url)
                response.raise_for_status()
                
                dest.write_bytes(response.content)
                size_mb = len(response.content) / 1024 / 1024
                print(f"({size_mb:.1f} MB)")
                
            except Exception as e:
                print(f"FAILED: {e}")
                return False
    
    print()
    print(f"✓ Voice '{voice_name}' downloaded successfully!")
    print(f"  Set PIPER_VOICE={voice_name} in your .env file")
    return True


def list_voices():
    """List available voices."""
    print("Available voices:")
    print()
    for name, path in VOICE_CATALOG.items():
        print(f"  • {name}")
    print()
    print("More voices at: https://huggingface.co/rhasspy/piper-voices")


def main():
    parser = argparse.ArgumentParser(
        description="Download Piper TTS voice models"
    )
    parser.add_argument(
        "voice",
        nargs="?",
        default="en_US-lessac-medium",
        help="Voice name to download (default: en_US-lessac-medium)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available voices",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="./models/piper",
        help="Models directory (default: ./models/piper)",
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_voices()
        return
    
    models_dir = Path(args.dir)
    success = download_voice(args.voice, models_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
