import os
import yt_dlp
import asyncio


def _ensure_cookies_file():
    """Write cookies from YT_COOKIES env var to disk if file doesn't exist."""
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    cookies_path = os.path.join(backend_dir, "cookies.txt")
    if not os.path.exists(cookies_path):
        cookies_env = os.environ.get("YT_COOKIES", "").strip()
        if cookies_env:
            with open(cookies_path, "w", encoding="utf-8") as f:
                f.write(cookies_env)
            print("[cookies] Wrote cookies.txt from YT_COOKIES environment variable.")
    return cookies_path


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
    """Return path to ffmpeg bin dir if on Windows with local binaries, else None."""
    if os.name == 'nt':
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        workspace_dir = os.path.dirname(backend_dir)
        ffmpeg_bin_dir = os.path.join(workspace_dir, "bin")
        ffmpeg_path = os.path.join(ffmpeg_bin_dir, "ffmpeg.exe")
        if os.path.exists(ffmpeg_path):
            return ffmpeg_bin_dir
    return None


def parse_info_response(info, url):
    title = info.get('title', 'Unknown Title')
    thumbnail = info.get('thumbnail', '')
    duration = info.get('duration', 0)
    uploader = info.get('uploader', 'Unknown Creator')
    description = info.get('description', '')
    extractor_key = info.get('extractor_key', '')

    formats = info.get('formats', [])
    heights = set()
    for fmt in formats:
        h = fmt.get('height')
        if h:
            heights.add(h)

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

    if not resolutions:
        resolutions = [
            {'id': 'best', 'label': 'Best Quality', 'height': 1080},
            {'id': '720p', 'label': '720p HD', 'height': 720},
            {'id': '360p', 'label': '360p Low', 'height': 360}
        ]

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


# YouTube client strategies to try in order (to bypass bot detection)
_YT_CLIENT_STRATEGIES = [
    {'extractor_args': {'youtube': {'player_client': ['tv_embedded']}}},
    {'extractor_args': {'youtube': {'player_client': ['web_creator']}}},
    {'extractor_args': {'youtube': {'player_client': ['mweb']}}},
    {'extractor_args': {'youtube': {'player_client': ['ios']}}},
    {},  # default client as final fallback
]


def _is_bot_error(error_msg):
    return ("Sign in" in error_msg or
            "bot" in error_msg.lower() or
            "nsig" in error_msg or
            "confirm" in error_msg.lower())


def get_video_info(url):
    cookies_path = _ensure_cookies_file()
    ffmpeg_dir = get_ffmpeg_path()
    last_error = None

    for strategy in _YT_CLIENT_STRATEGIES:
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
        }
        ydl_opts.update(strategy)

        if os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
        if ffmpeg_dir:
            ydl_opts['ffmpeg_location'] = ffmpeg_dir

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return parse_info_response(info, url)
        except Exception as e:
            last_error = e
            error_msg = str(e)
            if not _is_bot_error(error_msg):
                # Non-bot error (e.g. private video, invalid URL) — fail fast
                raise e
            print(f"[info] Strategy {strategy} failed (bot check): {error_msg[:120]}. Trying next...")
            continue

    raise Exception(f"All fetch strategies failed. Last error: {str(last_error)[:400]}")


def download_video_sync(url, resolution_id, output_dir, reporter):
    # Build format selector
    if resolution_id == 'audio':
        format_selector = 'bestaudio/best'
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        height_map = {
            '2160p': 2160, '1440p': 1440, '1080p': 1080,
            '720p': 720, '480p': 480, '360p': 360
        }
        height = height_map.get(resolution_id)
        format_selector = (f'bestvideo[height<={height}]+bestaudio/best'
                           if height else 'bestvideo+bestaudio/best')
        postprocessors = []

    cookies_path = _ensure_cookies_file()
    ffmpeg_dir = get_ffmpeg_path()

    base_opts = {
        'format': format_selector,
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'progress_hooks': [reporter.hook],
        'postprocessor_hooks': [reporter.postprocessor_hook],
        'quiet': True,
        'no_warnings': True,
    }
    if resolution_id != 'audio':
        base_opts['merge_output_format'] = 'mp4'
    if postprocessors:
        base_opts['postprocessors'] = postprocessors
    if os.path.exists(cookies_path):
        base_opts['cookiefile'] = cookies_path
    if ffmpeg_dir:
        base_opts['ffmpeg_location'] = ffmpeg_dir

    last_error = None
    for strategy in _YT_CLIENT_STRATEGIES:
        ydl_opts = {**base_opts}
        if strategy:
            ydl_opts['extractor_args'] = strategy.get('extractor_args', {})

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if resolution_id == 'audio':
                    base, _ = os.path.splitext(filename)
                    filename = base + ".mp3"
                return filename
        except Exception as e:
            last_error = e
            error_msg = str(e)
            if not _is_bot_error(error_msg):
                raise e
            print(f"[download] Strategy {strategy} failed (bot check): {error_msg[:120]}. Trying next...")
            continue

    raise Exception(f"All download strategies failed. Last error: {str(last_error)[:400]}")
