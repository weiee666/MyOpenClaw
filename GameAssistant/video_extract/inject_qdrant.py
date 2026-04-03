# ============================================================
# Step 3: Embed transcript chunks and upsert to Qdrant
# Collection: GameVideo_Guides (1536-dim COSINE, separate from STS2_GameData)
# ============================================================

import os
import time
import uuid
import json

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient, models

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
QDRANT_URL     = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

COLLECTION_NAME = "GameVideo_Guides"
EMBED_MODEL     = "text-embedding-3-small"
EMBED_DIM       = 1536
BATCH_SIZE      = 5

openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)


def _ensure_collection():
    existing = [c.name for c in qdrant_client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=EMBED_DIM,
                distance=models.Distance.COSINE,
            ),
        )
        print(f"[inject] Created collection: {COLLECTION_NAME}")
    else:
        print(f"[inject] Collection already exists: {COLLECTION_NAME}")


def _get_embeddings(texts: list[str]) -> list[list[float]]:
    resp = openai_client.embeddings.create(input=texts, model=EMBED_MODEL)
    return [item.embedding for item in resp.data]


def inject_chunks(
    chunks:      list[dict],
    video_id:    str,
    video_title: str,
    video_url:   str,
    collection:  str = COLLECTION_NAME,
) -> int:
    """
    Embed and upsert all chunks into Qdrant.
    Returns total number of points upserted.
    """
    _ensure_collection()

    total = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [c["text"] for c in batch]

        embeddings = _get_embeddings(texts)

        points = []
        for chunk, emb in zip(batch, embeddings):
            points.append(models.PointStruct(
                id=str(uuid.uuid4()),
                vector=emb,
                payload={
                    "text":        chunk["text"],
                    "video_id":    video_id,
                    "video_title": video_title,
                    "video_url":   video_url,
                    "start_time":  chunk["start_time"],
                    "end_time":    chunk["end_time"],
                    "chunk_index": chunk["chunk_index"],
                },
            ))

        for attempt in range(3):
            try:
                qdrant_client.upsert(collection_name=collection, points=points)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                print(f"  [inject] Retry {attempt+1}/3 ({e.__class__.__name__})", flush=True)
                time.sleep(2)

        total += len(points)
        print(f"[inject] Upserted {i + len(batch)}/{len(chunks)}", flush=True)
        time.sleep(0.3)

    print(f"[inject] Done. Total points upserted: {total}")
    return total


def inject_video(enriched: dict, collection: str = COLLECTION_NAME) -> None:
    """
    Embed full_text and upsert a single PointStruct for an enriched video dict.
    """
    _ensure_collection()

    video_id = enriched["video_id"]
    full_text = enriched["full_text"]

    embeddings = _get_embeddings([full_text])
    emb = embeddings[0]

    point = models.PointStruct(
        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, video_id)),
        vector=emb,
        payload={
            "text":        full_text,
            "video_id":    video_id,
            "video_title": enriched.get("video_title", ""),
            "video_url":   enriched.get("video_url", ""),
            "characters":  enriched.get("characters", []),
            "cards":       enriched.get("cards", []),
            "relics":      enriched.get("relics", []),
            "potions":     enriched.get("potions", []),
        },
    )

    for attempt in range(3):
        try:
            qdrant_client.upsert(collection_name=collection, points=[point])
            break
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  [inject] Retry {attempt+1}/3 ({e.__class__.__name__})", flush=True)
            time.sleep(2)

    print(f"[inject] Upserted video: {video_id}", flush=True)


def query_video(query: str, top_k: int = 5, collection: str = COLLECTION_NAME) -> list[dict]:
    """Search GameVideo_Guides collection and return matching chunks."""
    resp = openai_client.embeddings.create(input=[query], model=EMBED_MODEL)
    query_vec = resp.data[0].embedding

    hits = qdrant_client.query_points(
        collection_name=collection,
        query=query_vec,
        limit=top_k,
    ).points

    return [{"score": round(h.score, 4), **h.payload} for h in hits]


def reinject_all(transcripts_dir: str = None):
    """Clear GameVideo_Guides collection and reinject all enriched videos."""
    if transcripts_dir is None:
        transcripts_dir = os.path.join(os.path.dirname(__file__), "transcripts")

    # Clear existing collection
    existing = [c.name for c in qdrant_client.get_collections().collections]
    if COLLECTION_NAME in existing:
        qdrant_client.delete_collection(COLLECTION_NAME)
        print(f"[inject] Deleted collection: {COLLECTION_NAME}")

    _ensure_collection()

    enriched_files = sorted(
        f for f in os.listdir(transcripts_dir) if f.endswith("_enriched.json")
    )
    print(f"[inject] Found {len(enriched_files)} enriched files")

    for fname in enriched_files:
        path = os.path.join(transcripts_dir, fname)
        with open(path, encoding="utf-8") as f:
            enriched = json.load(f)
        inject_video(enriched)

    # Verify
    info = qdrant_client.get_collection(COLLECTION_NAME)
    print(f"[inject] Done. Collection now has {info.points_count} points.")

    # Quick test query
    print("\n[inject] Test query: 铁甲战士毒伤打法")
    results = query_video("铁甲战士毒伤打法", top_k=3)
    for r in results:
        print(f"  score={r['score']} | {r.get('video_title', '')} | "
              f"chars={r.get('characters', [])} | cards={r.get('cards', [])[:3]}")


if __name__ == "__main__":
    reinject_all()
