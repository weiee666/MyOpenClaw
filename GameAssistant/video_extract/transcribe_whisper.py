# ============================================================
# Step 2: Transcribe audio via OpenAI Whisper API
# Groups timestamped segments into 30-second chunks
# Output: transcripts/{video_id}_chunks.json
# ============================================================

import os
import json

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TRANSCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "transcripts")
CHUNK_SECONDS   = 30   # configurable chunk window


def transcribe_audio(audio_path: str, language: str = None) -> list[dict]:
    """
    Call Whisper API with verbose_json to get timestamped segments.
    Returns list of raw segment dicts from Whisper.
    """
    client = OpenAI(api_key=OPENAI_API_KEY)

    kwargs = {
        "model":           "whisper-1",
        "response_format": "verbose_json",
        "timestamp_granularities": ["segment"],
    }
    if language:
        kwargs["language"] = language

    print(f"[transcribe] Sending to Whisper API: {os.path.basename(audio_path)}")
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(file=f, **kwargs)

    segments = [
        {
            "start": seg.start,
            "end":   seg.end,
            "text":  seg.text.strip(),
        }
        for seg in response.segments
    ]
    print(f"[transcribe] Got {len(segments)} raw segments")
    return segments


def group_into_chunks(segments: list[dict], chunk_seconds: int = CHUNK_SECONDS) -> list[dict]:
    """
    Merge consecutive Whisper segments into fixed-length chunks.
    Each chunk: {chunk_index, start_time, end_time, text}
    """
    if not segments:
        return []

    chunks = []
    chunk_idx    = 0
    chunk_start  = segments[0]["start"]
    chunk_texts  = []
    chunk_end    = chunk_start

    for seg in segments:
        chunk_texts.append(seg["text"])
        chunk_end = seg["end"]

        if chunk_end - chunk_start >= chunk_seconds:
            chunks.append({
                "chunk_index": chunk_idx,
                "start_time":  round(chunk_start, 2),
                "end_time":    round(chunk_end, 2),
                "text":        " ".join(chunk_texts).strip(),
            })
            chunk_idx   += 1
            # start fresh from next segment
            chunk_start  = seg["end"]
            chunk_texts  = []

    # flush remaining
    if chunk_texts:
        chunks.append({
            "chunk_index": chunk_idx,
            "start_time":  round(chunk_start, 2),
            "end_time":    round(chunk_end, 2),
            "text":        " ".join(chunk_texts).strip(),
        })

    return chunks


def transcribe_and_chunk(
    audio_path:    str,
    video_id:      str,
    chunk_seconds: int = CHUNK_SECONDS,
    output_dir:    str = TRANSCRIPTS_DIR,
) -> list[dict]:
    """
    Full pipeline: Whisper → chunks → save JSON.
    Skips transcription if output file already exists.
    Returns list of chunk dicts.
    """
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{video_id}_chunks.json")

    if os.path.exists(out_path):
        print(f"[transcribe] Already exists, skipping: {out_path}")
        with open(out_path, encoding="utf-8") as f:
            return json.load(f)

    segments = transcribe_audio(audio_path)
    chunks   = group_into_chunks(segments, chunk_seconds=chunk_seconds)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"[transcribe] Saved {len(chunks)} chunks → {out_path}")
    return chunks


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python transcribe_whisper.py <audio_path> <video_id>")
        sys.exit(1)
    result = transcribe_and_chunk(sys.argv[1], sys.argv[2])
    print(f"Chunks: {len(result)}")
