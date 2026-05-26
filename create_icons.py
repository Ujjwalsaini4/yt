import os
import sys
import subprocess

def install_and_import(package):
    try:
        import PIL
    except ImportError:
        print(f"Pillow not found. Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        
def main():
    install_and_import('pillow')
    from PIL import Image

    src_image = r"C:\Users\ujjwa\.gemini\antigravity\brain\cbac3d12-7829-4216-afda-c061ba81bbb2\stream_vault_logo_1779756311387.png"
    public_dir = r"c:\Users\ujjwa\OneDrive\Desktop\yt\frontend\public"
    
    if not os.path.exists(public_dir):
        os.makedirs(public_dir)
        print(f"Created public directory: {public_dir}")
        
    icon_192_path = os.path.join(public_dir, "icon-192.png")
    icon_512_path = os.path.join(public_dir, "icon-512.png")
    
    if os.path.exists(src_image):
        with Image.open(src_image) as img:
            # Generate 192x192
            img_192 = img.resize((192, 192), Image.Resampling.LANCZOS)
            img_192.save(icon_192_path, "PNG")
            print(f"Generated: {icon_192_path}")
            
            # Generate 512x512
            img_512 = img.resize((512, 512), Image.Resampling.LANCZOS)
            img_512.save(icon_512_path, "PNG")
            print(f"Generated: {icon_512_path}")
            
            # Copy source as favicon.png too
            favicon_path = os.path.join(public_dir, "favicon.png")
            img_32 = img.resize((32, 32), Image.Resampling.LANCZOS)
            img_32.save(favicon_path, "PNG")
            print(f"Generated favicon: {favicon_path}")
    else:
        print(f"Source image not found at: {src_image}")

if __name__ == "__main__":
    main()
