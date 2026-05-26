# StreamVault - Premium All-Platform 4K Video Downloader

StreamVault is a high-performance, single-container web application for downloading videos from almost any platform (YouTube, Instagram, TikTok, Facebook, Twitter, etc.) in resolutions up to 4K.

## Features
- **All-Platform Downloads**: Powered by `yt-dlp`.
- **4K Support**: Automatically merges separate video and audio tracks into a single `.mp4` file.
- **Progress Tracking**: Real-time progress bar (speed, ETA, total size) using WebSockets.
- **Auto-Deletion**: Automatically deletes downloads from the server after 2 minutes to save space.
- **Progressive Web App (PWA)**: Installable on mobile devices with an icon, full-screen mode, and offline cache.
- **Railway Ready**: Configured with a `Dockerfile` for single-container cloud hosting.

---

## 💻 Local Setup (Windows/Mac/Linux)

### 1. Pre-requisites
- **Python 3.9+**
- **Node.js 18+**

### 2. Download FFmpeg Binaries (Windows only)
Run the helper script to download and extract FFmpeg static binaries automatically:
```bash
python download_binaries.py
```
*(On Linux/Mac, install ffmpeg via your package manager, e.g., `sudo apt install ffmpeg` or `brew install ffmpeg`)*

### 3. Install Dependencies & Start
**Backend (FastAPI)**:
```bash
# Install packages
pip install -r backend/requirements.txt

# Start backend (Port 8000)
python backend/main.py
```

**Frontend (React/Vite)**:
```bash
cd frontend

# Install packages
npm install

# Start frontend (Port 5173, host visible to network)
npm run dev
```

Open `http://localhost:5173` on your PC, or `http://<your-ip>:5173` on your mobile browser (make sure they are on the same Wi-Fi).

---

## 🚂 Railway Cloud Deployment

1. Create a repository on GitHub and push the code.
2. In Railway, click **New Project** -> **Deploy from GitHub repo**.
3. Choose this repository. Railway will detect the `Dockerfile` and compile the app into a single Linux container (installing Node, Python, and system `ffmpeg` automatically).
4. Assign a public domain under your Railway service settings, and you are live!
