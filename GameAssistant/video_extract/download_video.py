# ============================================================
# Step 1: Download Bilibili video audio via yt-dlp
# Output: downloads/{video_id}.m4a + {video_id}_meta.json
# ============================================================

import os
import json
import re

try:
    import yt_dlp
except ImportError:
    raise ImportError("Run: pip install yt-dlp")

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")


def _extract_video_id(url: str) -> str:
    """Extract BV or av ID from Bilibili URL."""
    m = re.search(r"(BV\w+|av\d+)", url)
    if m:
        return m.group(1)
    # fallback: use last path segment
    return url.rstrip("/").split("/")[-1].split("?")[0]


def download_audio(url: str, output_dir: str = DOWNLOADS_DIR) -> dict:
    """
    Download audio-only from Bilibili URL.
    Returns metadata dict with keys: video_id, title, uploader, upload_date,
                                      audio_path, url
    """
    os.makedirs(output_dir, exist_ok=True)

    video_id = _extract_video_id(url)
    audio_path = os.path.join(output_dir, f"{video_id}.m4a")
    meta_path  = os.path.join(output_dir, f"{video_id}_meta.json")

    # Skip if already downloaded
    if os.path.exists(audio_path) and os.path.exists(meta_path):
        print(f"[download] Already exists, skipping: {audio_path}")
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, f"{video_id}.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
        }],
        "quiet": False,
        "no_warnings": False,
    }

    print(f"[download] Downloading audio from: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    metadata = {
        "video_id":    video_id,
        "title":       info.get("title", ""),
        "uploader":    info.get("uploader", ""),
        "upload_date": info.get("upload_date", ""),
        "duration":    info.get("duration", 0),
        "url":         url,
        "audio_path":  audio_path,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"[download] Saved: {audio_path}")
    print(f"[download] Metadata: {meta_path}")
    return metadata


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python download_video.py <bilibili_url>")
        sys.exit(1)
    result = download_audio(sys.argv[1])
    print(result)
