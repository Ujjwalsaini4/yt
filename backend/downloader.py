import os
import yt_dlp
import asyncio

class DownloadProgressReporter:
    def __init__(self, loop, callback):
        self.loop = loop
        self.callback = callback

    def hook(self, d):
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded_bytes = d.get('downloaded_bytes') or 0
            
            percent = 0.0
            if total_bytes > 0:
                percent = (downloaded_bytes / total_bytes) * 100
                
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0
            
            # Send updates through the asyncio event loop to ensure thread-safety
            asyncio.run_coroutine_threadsafe(
                self.callback({
                    'status': 'downloading',
                    'downloaded_bytes': downloaded_bytes,
                    'total_bytes': total_bytes,
                    'percent': round(percent, 2),
                    'speed': speed,
                    'eta': eta,
                    'filename': os.path.basename(d.get('filename', ''))
                }),
                self.loop
            )
        elif d['status'] == 'finished':
            asyncio.run_coroutine_threadsafe(
                self.callback({
                    'status': 'finished',
                    'filename': os.path.basename(d.get('filename', ''))
                }),
                self.loop
            )

    def postprocessor_hook(self, d):
        if d['status'] == 'started':
            asyncio.run_coroutine_threadsafe(
                self.callback({
                    'status': 'merging',
                    'msg': 'Merging video and audio formats (this may take a few seconds)...'
                }),
                self.loop
            )
        elif d['status'] == 'finished':
            asyncio.run_coroutine_threadsafe(
                self.callback({
                    'status': 'merging_finished',
                    'msg': 'Finalizing download...'
                }),
                self.loop
            )

def get_ffmpeg_path():
    # Bin directory is at the root level of the workspace, only check on Windows
    if os.name == 'nt':
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        workspace_dir = os.path.dirname(backend_dir)
        ffmpeg_bin_dir = os.path.join(workspace_dir, "bin")
        
        # Check if binaries exist in the bin directory
        ffmpeg_path = os.path.join(ffmpeg_bin_dir, "ffmpeg.exe")
        if os.path.exists(ffmpeg_path):
            return ffmpeg_bin_dir
    
    # Fallback to system path (returns None, let yt-dlp search PATH)
    return None

def get_video_info(url):
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
    }
    
    ffmpeg_dir = get_ffmpeg_path()
    if ffmpeg_dir:
        ydl_opts['ffmpeg_location'] = ffmpeg_dir
        
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            
            # Format outputs
            title = info.get('title', 'Unknown Title')
            thumbnail = info.get('thumbnail', '')
            duration = info.get('duration', 0)
            uploader = info.get('uploader', 'Unknown Creator')
            description = info.get('description', '')
            extractor_key = info.get('extractor_key', '')
            
            # Determine available resolutions
            formats = info.get('formats', [])
            heights = set()
            
            for fmt in formats:
                h = fmt.get('height')
                if h:
                    heights.add(h)
            
            # Standard resolution configurations
            resolutions = []
            if any(h >= 2160 for h in heights):
                resolutions.append({'id': '2160p', 'label': '4K (2160p)', 'height': 2160})
            if any(h >= 1440 for h in heights):
                resolutions.append({'id': '1440p', 'label': '2K (1440p)', 'height': 1440})
            if any(h >= 1080 for h in heights):
                resolutions.append({'id': '1080p', 'label': '1080p Full HD', 'height': 1080})
            if any(h >= 720 for h in heights):
                resolutions.append({'id': '720p', 'label': '720p HD', 'height': 720})
            if any(h >= 480 for h in heights):
                resolutions.append({'id': '480p', 'label': '480p SD', 'height': 480})
            if any(h >= 360 for h in heights):
                resolutions.append({'id': '360p', 'label': '360p Low', 'height': 360})
                
            # If no height is found (e.g. on Instagram/TikTok where formats might not report heights clearly),
            # or if resolutions list is empty, default to standard options
            if not resolutions:
                resolutions = [
                    {'id': 'best', 'label': 'Best Quality', 'height': 1080},
                    {'id': '720p', 'label': '720p HD', 'height': 720},
                    {'id': '360p', 'label': '360p Low', 'height': 360}
                ]
                
            # Add audio option to the front or back
            resolutions.append({'id': 'audio', 'label': 'Audio Only (MP3)', 'height': 0})
            
            return {
                'title': title,
                'thumbnail': thumbnail,
                'duration': duration,
                'uploader': uploader,
                'description': description[:300] + '...' if description and len(description) > 300 else description,
                'platform': extractor_key,
                'resolutions': resolutions,
                'original_url': url
            }
        except Exception as e:
            raise Exception(f"Failed to fetch video info: {str(e)}")

def download_video_sync(url, resolution_id, output_dir, reporter):
    # Formulate format selector
    if resolution_id == 'audio':
        # Download best audio and convert to mp3
        format_selector = 'bestaudio/best'
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        # Determine height constraint
        height_map = {
            '2160p': 2160,
            '1440p': 1440,
            '1080p': 1080,
            '720p': 720,
            '480p': 480,
            '360p': 360
        }
        height = height_map.get(resolution_id)
        
        if height:
            # yt-dlp format selection: get best video that matches/is under height + best audio
            # and merge them.
            format_selector = f'bestvideo[height<={height}]+bestaudio/best'
        else:
            format_selector = 'bestvideo+bestaudio/best'
            
        postprocessors = []

    ydl_opts = {
        'format': format_selector,
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'progress_hooks': [reporter.hook],
        'postprocessor_hooks': [reporter.postprocessor_hook],
        'quiet': True,
        'no_warnings': True,
    }
    
    if resolution_id != 'audio':
        ydl_opts['merge_output_format'] = 'mp4'
    
    if postprocessors:
        ydl_opts['postprocessors'] = postprocessors

    ffmpeg_dir = get_ffmpeg_path()
    if ffmpeg_dir:
        ydl_opts['ffmpeg_location'] = ffmpeg_dir
        
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        
        # If we downloaded audio, the extension changes to .mp3 due to post-processing
        if resolution_id == 'audio':
            base, _ = os.path.splitext(filename)
            filename = base + ".mp3"
            
        return filename
