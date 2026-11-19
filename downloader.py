import os
import re
import shutil
from email.message import Message
from urllib.parse import unquote, urlparse

import requests
import yt_dlp


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp",
    ".tif", ".tiff", ".avif", ".heic",
}

IMAGE_MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/avif": ".avif",
    "image/heic": ".heic",
}

VIDEO_QUALITIES = [
    "Best",
    "2160p (4K)",
    "1440p (2K)",
    "1080p",
    "720p",
    "480p",
    "360p",
    "240p",
    "144p",
    "118p",
]

# Approximate combined bitrates (MB per second) for fallback size calculation
_FALLBACK_MB_PER_SEC = {
    2160: 4.5,
    1440: 2.2,
    1080: 0.95,
    720: 0.55,
    480: 0.28,
    360: 0.16,
    240: 0.09,
    144: 0.05,
    118: 0.04,
}


def find_ffmpeg():
    """Find FFmpeg installed on the user's system."""
    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg:
        return os.path.dirname(ffmpeg)

    common_paths = [
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg",
    ]

    for path in common_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return os.path.dirname(path)

    return None


def is_direct_image_url(url):
    """Identify direct image URLs by their URL path extension."""
    path = urlparse(url).path.lower()
    return os.path.splitext(path)[1] in IMAGE_EXTENSIONS


def detect_platform_label(url):
    """Return a clean source badge label from a URL."""
    host = (urlparse(url).netloc or "").lower()
    if is_direct_image_url(url):
        return "Image detected"
    if "youtube.com" in host or "youtu.be" in host:
        return "YouTube detected"
    if "instagram.com" in host:
        return "Instagram detected"
    if host:
        return f"{host.removeprefix('www.')} detected"
    return "Media URL"


def format_duration(seconds):
    """Format seconds into MM:SS or HH:MM:SS."""
    if not seconds or seconds <= 0:
        return ""
    total = int(seconds)
    hrs, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    if hrs:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def _format_bytes_to_mb(num_bytes):
    if not num_bytes or num_bytes <= 0:
        return None
    mb = num_bytes / (1024 * 1024)
    if mb >= 100:
        return f"{mb:.0f} MB"
    return f"{mb:.1f} MB"


def estimate_size_label(media_type, quality, metadata=None, url=""):
    """
    Calculate or estimate file size in MB for the selected media type and quality.
    Uses format metadata when available, falling back to duration/bitrate estimates.
    """
    metadata = metadata or {}

    if media_type == "image":
        size_bytes = metadata.get("filesize_bytes") or 0
        if size_bytes > 0:
            return _format_bytes_to_mb(size_bytes)
        if is_direct_image_url(url):
            try:
                resp = requests.head(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5, allow_redirects=True)
                cl = int(resp.headers.get("Content-Length") or 0)
                if cl > 0:
                    return _format_bytes_to_mb(cl)
            except Exception:
                pass
        return "~2.4 MB"

    duration = metadata.get("duration") or 0

    if media_type == "audio":
        if duration > 0:
            # 192 kbps MP3 ~= 0.024 MB/s
            return _format_bytes_to_mb(duration * 192 * 1000 / 8)
        return "~4.5 MB"

    # Video resolution size calculation
    formats = metadata.get("formats") or []
    target_height = None
    if quality and quality != "Best":
        match = re.search(r"(\d+)p", quality)
        if match:
            target_height = int(match.group(1))

    # Try exact or closest available format sizes from yt-dlp metadata
    best_audio_bytes = 0
    for fmt in formats:
        if fmt.get("vcodec") == "none" and fmt.get("acodec") != "none":
            sz = fmt.get("filesize") or fmt.get("filesize_approx") or 0
            if sz > best_audio_bytes:
                best_audio_bytes = sz

    candidate_video_bytes = 0
    candidate_height = 0
    for fmt in formats:
        h = fmt.get("height") or 0
        vcodec = fmt.get("vcodec") or "none"
        if vcodec == "none" or h <= 0:
            continue
        sz = fmt.get("filesize") or fmt.get("filesize_approx") or 0
        if sz <= 0 and duration > 0 and fmt.get("tbr"):
            sz = int(duration * fmt["tbr"] * 1000 / 8)
        if sz <= 0:
            continue

        if target_height is None:
            if h >= candidate_height:
                candidate_height = h
                candidate_video_bytes = sz
        else:
            if h <= target_height and h >= candidate_height:
                candidate_height = h
                candidate_video_bytes = sz

    if candidate_video_bytes > 0:
        has_audio_already = any(
            (f.get("height") == candidate_height)
            and (f.get("vcodec") != "none")
            and (f.get("acodec") != "none")
            and ((f.get("filesize") or f.get("filesize_approx") or 0) == candidate_video_bytes)
            for f in formats
        )
        total_bytes = candidate_video_bytes + (0 if has_audio_already else best_audio_bytes)
        formatted = _format_bytes_to_mb(total_bytes)
        if formatted:
            return formatted

    # Fallback calculation using duration and resolution bitrate
    if duration > 0:
        if target_height is None:
            rate = _FALLBACK_MB_PER_SEC[1080]
        else:
            closest_h = min(
                _FALLBACK_MB_PER_SEC.keys(),
                key=lambda k: abs(k - target_height),
            )
            rate = _FALLBACK_MB_PER_SEC[closest_h]
        return f"~{duration * rate:.0f} MB" if duration * rate >= 100 else f"~{duration * rate:.1f} MB"

    defaults = {
        "Best": "~320 MB",
        "2160p (4K)": "~680 MB",
        "1440p (2K)": "~390 MB",
        "1080p": "~240 MB",
        "720p": "~130 MB",
        "480p": "~65 MB",
        "360p": "~38 MB",
        "240p": "~22 MB",
        "144p": "~12 MB",
        "118p": "~10 MB",
    }
    return defaults.get(quality, "~240 MB")


def get_video_info(url):
    """Fetch media metadata without downloading it (excludes channel/uploader)."""
    if is_direct_image_url(url):
        title = _safe_filename(os.path.basename(urlparse(url).path)) or "Sample image title"
        return {
            "title": title,
            "duration": 0,
            "thumbnail": url,
            "formats": [],
            "filesize_bytes": 0,
        }

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

    thumbnail = info.get("thumbnail")
    if not thumbnail:
        thumbnails = info.get("thumbnails") or []
        if thumbnails:
            thumbnail = thumbnails[-1].get("url")

    return {
        "title": info.get("title", "Sample video title"),
        "duration": info.get("duration", 0),
        "thumbnail": thumbnail,
        "formats": info.get("formats") or [],
        "filesize_bytes": info.get("filesize") or info.get("filesize_approx") or 0,
    }


def _safe_filename(name):
    """Remove characters that are unsafe in a local filename."""
    name = unquote(name or "").strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip(" .")
    return name or "downloaded_image"


def _unique_path(folder, filename):
    """Avoid overwriting a file that already exists."""
    stem, extension = os.path.splitext(filename)
    candidate = os.path.join(folder, filename)
    counter = 1

    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{stem}_{counter}{extension}")
        counter += 1

    return candidate


def _download_image(url, output_path, progress_callback):
    """Stream a direct image URL to disk and report progress."""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(
        url,
        headers=headers,
        stream=True,
        timeout=(20, 90),
    )
    response.raise_for_status()

    try:
        content_type = response.headers.get("Content-Type", "")
        mime_type = content_type.split(";", 1)[0].strip().lower()

        if not mime_type.startswith("image/"):
            raise ValueError(
                "The URL did not return an image. "
                f"Server Content-Type: {content_type or 'not provided'}"
            )

        parsed = urlparse(response.url)
        url_name = os.path.basename(parsed.path)
        filename = ""

        content_disposition = response.headers.get("Content-Disposition")
        if content_disposition:
            message = Message()
            message["content-disposition"] = content_disposition
            filename = message.get_filename() or ""

        if not filename:
            filename = url_name

        extension = os.path.splitext(filename)[1].lower()
        if extension not in IMAGE_EXTENSIONS:
            extension = IMAGE_MIME_EXTENSIONS.get(mime_type, ".img")
            filename = os.path.splitext(filename)[0] + extension

        filename = _safe_filename(filename)
        destination = _unique_path(output_path, filename)

        total = int(response.headers.get("Content-Length", 0) or 0)
        downloaded = 0

        with open(destination, "wb") as image_file:
            for chunk in response.iter_content(chunk_size=1024 * 128):
                if not chunk:
                    continue

                image_file.write(chunk)
                downloaded += len(chunk)

                if progress_callback:
                    progress_callback({
                        "status": "downloading",
                        "total_bytes": total,
                        "downloaded_bytes": downloaded,
                    })

        if progress_callback:
            progress_callback({
                "status": "finished",
                "total_bytes": total or downloaded,
                "downloaded_bytes": downloaded,
            })

        return destination
    except Exception:
        if "destination" in locals() and os.path.exists(destination):
            os.remove(destination)
        raise
    finally:
        response.close()


def download_media(
    url,
    output_path,
    media_type,
    quality,
    progress_callback,
):
    """
    Download YouTube media, public Instagram Reels, or direct image URLs.
    """
    os.makedirs(output_path, exist_ok=True)

    if media_type == "image" or is_direct_image_url(url):
        return _download_image(url, output_path, progress_callback)

    ffmpeg_location = find_ffmpeg()

    options = {
        "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
        "progress_hooks": [progress_callback] if progress_callback else [],
        "noplaylist": True,
    }

    if ffmpeg_location:
        options["ffmpeg_location"] = ffmpeg_location

    if media_type == "video":
        if quality == "Best":
            format_selector = "bv*+ba/b"
        else:
            match = re.search(r"(\d+)p", quality)
            if not match:
                raise ValueError(f"Unsupported video quality: {quality}")

            height = int(match.group(1))
            format_selector = (
                f"bv*[height<={height}]+ba/"
                f"b[height<={height}]/best"
            )

        options["format"] = format_selector
        options["merge_output_format"] = "mp4"
    else:
        options["format"] = "bestaudio/best"
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
        ydl.download([url])

        filename = ydl.prepare_filename(info)

        if media_type == "video":
            filename = os.path.splitext(filename)[0] + ".mp4"
        else:
            filename = os.path.splitext(filename)[0] + ".mp3"

        return filename