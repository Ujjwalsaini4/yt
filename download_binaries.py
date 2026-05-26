import os
import sys
import urllib.request
import zipfile
import shutil

def download_progress(block_num, block_size, total_size):
    read_so_far = block_num * block_size
    if total_size > 0:
        percent = min(100.0, read_so_far * 100 / total_size)
        sys.stdout.write(f"\rDownloading FFmpeg: {percent:.2f}% ({read_so_far / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB)")
    else:
        sys.stdout.write(f"\rDownloading FFmpeg: {read_so_far / (1024*1024):.2f} MB")
    sys.stdout.flush()

def main():
    workspace = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(workspace, "bin")
    zip_path = os.path.join(workspace, "ffmpeg.zip")
    
    if not os.path.exists(bin_dir):
        os.makedirs(bin_dir)
        print(f"Created directory: {bin_dir}")

    ffmpeg_exe = os.path.join(bin_dir, "ffmpeg.exe")
    ffprobe_exe = os.path.join(bin_dir, "ffprobe.exe")

    # If already exists, skip
    if os.path.exists(ffmpeg_exe) and os.path.exists(ffprobe_exe):
        print("FFmpeg and FFprobe binaries are already present in bin/ directory.")
        return

    # URL for static build of FFmpeg for Windows
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    
    print(f"Downloading FFmpeg from {url}...")
    try:
        urllib.request.urlretrieve(url, zip_path, download_progress)
        print("\nDownload complete. Extracting binaries...")
        
        extracted_ffmpeg = False
        extracted_ffprobe = False
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                filename = os.path.basename(member)
                if filename == "ffmpeg.exe":
                    with zip_ref.open(member) as source, open(ffmpeg_exe, 'wb') as target:
                        shutil.copyfileobj(source, target)
                    extracted_ffmpeg = True
                    print("Extracted ffmpeg.exe to bin/")
                elif filename == "ffprobe.exe":
                    with zip_ref.open(member) as source, open(ffprobe_exe, 'wb') as target:
                        shutil.copyfileobj(source, target)
                    extracted_ffprobe = True
                    print("Extracted ffprobe.exe to bin/")
        
        if not extracted_ffmpeg or not extracted_ffprobe:
            print("Error: Could not find ffmpeg.exe or ffprobe.exe inside the zip file.")
        else:
            print("FFmpeg setup completed successfully!")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            print("Cleaned up zip file.")

if __name__ == "__main__":
    main()
