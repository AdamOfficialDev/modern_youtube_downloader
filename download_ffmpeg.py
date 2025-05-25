import requests
from tqdm import tqdm
import sys
import os
import zipfile
import shutil
import json
from pathlib import Path

def download_ffmpeg():
    url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
    bundled_dir = Path('bundled')
    output_path = bundled_dir / 'ffmpeg.zip'
    extract_path = bundled_dir / 'ffmpeg_temp'

    # Create bundled directory if it doesn't exist
    bundled_dir.mkdir(exist_ok=True)

    try:
        print("Downloading FFmpeg...")
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))

        with tqdm(
            desc='Downloading FFmpeg',
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
            bar_format='{desc}: {percentage:3.0f}%|{bar:50}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
        ) as pbar:
            with open(output_path, 'wb') as f:
                for data in response.iter_content(chunk_size=1024):
                    size = f.write(data)
                    pbar.update(size)

        print("\nExtracting FFmpeg...")
        # Create temporary extraction directory
        extract_path.mkdir(exist_ok=True)

        # Extract the zip file
        with zipfile.ZipFile(output_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # Find the bin directory in the extracted files
        bin_dir = None
        for root, dirs, files in os.walk(extract_path):
            if 'bin' in dirs:
                bin_dir = os.path.join(root, 'bin')
                break

        if not bin_dir:
            raise Exception("Could not find bin directory in FFmpeg archive")

        # Create ffmpeg directory if it doesn't exist
        ffmpeg_dir = Path('ffmpeg')
        ffmpeg_dir.mkdir(exist_ok=True)

        # Copy ffmpeg executables to the ffmpeg directory
        print("Installing FFmpeg executables...")
        executables = ['ffmpeg.exe', 'ffprobe.exe', 'ffplay.exe']
        ffmpeg_exe_path = None

        for exe in executables:
            src = os.path.join(bin_dir, exe)
            dst = ffmpeg_dir / exe  # Copy to ffmpeg directory
            if os.path.exists(src):
                shutil.copy2(src, dst)
                print(f"Installed {exe} to ffmpeg directory")

                # Save the path to ffmpeg.exe for config
                if exe == 'ffmpeg.exe':
                    ffmpeg_exe_path = str(dst.absolute())

        # Update config.json with the FFmpeg path
        if ffmpeg_exe_path:
            print(f"Updating config.json with FFmpeg path: {ffmpeg_exe_path}")
            config_path = 'config.json'  # Use root directory config

            # Load existing config or create new one
            config = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                except Exception as e:
                    print(f"Error loading config: {e}")

            # Update FFmpeg path
            config['ffmpeg_path'] = ffmpeg_exe_path

            # Save config
            try:
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=4)
                print("Config updated successfully")
            except Exception as e:
                print(f"Error saving config: {e}")

        # Clean up
        print("Cleaning up...")
        if output_path.exists():
            output_path.unlink()  # Delete zip file
        if extract_path.exists():
            shutil.rmtree(extract_path)  # Delete temporary extraction directory

        print("\nFFmpeg installation completed successfully!")
        return True

    except Exception as e:
        print(f"\nError: {str(e)}")
        return False

if __name__ == "__main__":
    success = download_ffmpeg()
    sys.exit(0 if success else 1)
