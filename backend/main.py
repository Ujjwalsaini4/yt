import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Any

async def delete_file_later(filepath: str, delay: int = 120):
    await asyncio.sleep(delay)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"Auto-deleted temporary file: {filepath}")
    except Exception as e:
        print(f"Error auto-deleting file {filepath}: {e}")

from downloader import get_video_info, download_video_sync, DownloadProgressReporter

app = FastAPI(title="All-Platform 4K Video Downloader API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local network mobile access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Output directory for downloads
backend_dir = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(backend_dir, "downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

class InfoRequest(BaseModel):
    url: str

class CookiesRequest(BaseModel):
    cookies: str

@app.post("/api/info")
async def fetch_info(req: InfoRequest):
    if not req.url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    try:
        # Run synchronous info retrieval in a separate thread to prevent blocking the event loop
        info = await asyncio.to_thread(get_video_info, req.url)
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download-file/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Return FileResponse which handles downloading the file.
    # Set the filename parameter so the browser saves it with the correct name.
    return FileResponse(
        path=file_path,
        media_type="application/octet-stream",
        filename=filename
    )

@app.get("/api/status")
async def get_system_status():
    from downloader import get_ffmpeg_path
    cookies_path = os.path.join(backend_dir, "cookies.txt")
    return {
        "cookies_active": os.path.exists(cookies_path),
        "ffmpeg_active": get_ffmpeg_path() is not None or os.name != 'nt'
    }

@app.post("/api/save-cookies")
async def save_cookies(req: CookiesRequest):
    try:
        cookies_path = os.path.join(backend_dir, "cookies.txt")
        if not req.cookies.strip():
            # If empty string, delete cookies.txt
            if os.path.exists(cookies_path):
                os.remove(cookies_path)
            return {"status": "success", "message": "Cookies cleared."}
        
        # Write to cookies.txt in UTF-8
        with open(cookies_path, "w", encoding="utf-8") as f:
            f.write(req.cookies.strip())
        return {"status": "success", "message": "Cookies saved successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save cookies: {str(e)}")

@app.websocket("/ws/download")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    loop = asyncio.get_event_loop()
    
    async def send_progress_update(data: dict):
        try:
            await websocket.send_json(data)
        except Exception:
            pass # Connection might be closed

    try:
        # Receive configuration (url and resolution_id) from client
        data = await websocket.receive_json()
        url = data.get("url")
        resolution_id = data.get("resolution")
        
        if not url or not resolution_id:
            await websocket.send_json({"status": "error", "message": "Missing URL or resolution selection"})
            await websocket.close()
            return
            
        await websocket.send_json({"status": "starting", "message": "Initializing download session..."})
        
        reporter = DownloadProgressReporter(loop, send_progress_update)
        
        # Run the download in a separate thread so it doesn't block other socket connections
        try:
            filepath = await asyncio.to_thread(
                download_video_sync, url, resolution_id, DOWNLOAD_DIR, reporter
            )
            
            filename = os.path.basename(filepath)
            
            await websocket.send_json({
                "status": "completed",
                "message": "Download completed successfully!",
                "filename": filename
            })
            
            # Start background deletion task (120 seconds = 2 minutes)
            asyncio.create_task(delete_file_later(filepath, 120))
            
        except Exception as e:
            await websocket.send_json({
                "status": "error",
                "message": f"Download failed: {str(e)}"
            })
            
    except WebSocketDisconnect:
        print("WebSocket client disconnected.")
    except Exception as e:
        try:
            await websocket.send_json({"status": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

# Mount the frontend static files (if built)
# Resolves frontend/dist relative to backend folder
frontend_dist = os.path.join(os.path.dirname(backend_dir), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    print(f"Mounted production frontend from: {frontend_dist}")
else:
    print(f"Frontend dist folder not found at {frontend_dist}. Running in API-only dev mode.")

if __name__ == "__main__":
    import uvicorn
    # Read Railway assigned port from environment variable, default to 8000 locally
    port = int(os.environ.get("PORT", 8000))
    # Bind to 0.0.0.0 to enable access from mobile devices on Wi-Fi/cloud networks
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=os.environ.get("ENV") != "production")
