"""
challenges.py — challenge persistence, dedup, and reference tagging

Responsibilities:
  - Load/save challenges.json
  - Check new challenge similarity against existing ones
  - Tag matching reference JSON files with the accepted challenge
  - Find which references match a challenge (for /search pre-filter)
"""

import json
import numpy as np
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity

from embedder import get_embedder

CHALLENGES_FILE = Path("challenges.json")
REFERENCES_DIR  = Path("references")

# Similarity threshold: above this → "too similar, already exists"
DEDUP_THRESHOLD = 0.85

# Threshold for tagging a reference as relevant to the challenge
RELEVANCE_THRESHOLD = 0.30


# ── Persistence ───────────────────────────────────────────────────────────────

def load_challenges() -> list[dict]:
    """Return list of {name, embedding} dicts. Embeddings stored as lists."""
    if not CHALLENGES_FILE.exists():
        return []
    return json.loads(CHALLENGES_FILE.read_text(encoding="utf-8"))


def save_challenges(challenges: list[dict]) -> None:
    CHALLENGES_FILE.write_text(
        json.dumps(challenges, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_challenge_names() -> list[str]:
    return [c["name"] for c in load_challenges()]


def challenge_exists(name: str) -> bool:
    return name.lower() in [c["name"].lower() for c in load_challenges()]


# ── Deduplication ─────────────────────────────────────────────────────────────

def check_similarity(new_text: str) -> tuple[bool, str | None, float]:
    """
    Compare new_text against all saved challenges.

    Returns:
        (is_duplicate, most_similar_name, highest_score)
        is_duplicate=True means the challenge is too similar to an existing one.
    """
    challenges = load_challenges()
    if not challenges:
        return False, None, 0.0

    embedder = get_embedder()
    new_vec = np.array(embedder.embed_query(new_text)).reshape(1, -1)

    best_score = 0.0
    best_name  = None

    for ch in challenges:
        existing_vec = np.array(ch["embedding"]).reshape(1, -1)
        score = float(cosine_similarity(new_vec, existing_vec)[0][0])
        if score > best_score:
            best_score = score
            best_name  = ch["name"]

    is_duplicate = best_score >= DEDUP_THRESHOLD
    return is_duplicate, best_name, best_score


# ── Reference tagging ─────────────────────────────────────────────────────────

def _load_reference_texts() -> list[tuple[Path, str]]:
    """Return (path, page_content) for every reference JSON."""
    results = []
    for path in sorted(REFERENCES_DIR.glob("*.json")):
        if path.name == "_all.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            content = data.get("page_content", "").strip()
            if content:
                results.append((path, content))
        except Exception:
            continue
    return results


def tag_references_with_challenge(challenge_name: str) -> list[str]:
    """
    Embed challenge_name, compare against every reference's page_content,
    and write challenge_name into the metadata.challenges list of matching files.

    Returns list of customer names that were tagged.
    """
    embedder   = get_embedder()
    refs       = _load_reference_texts()
    challenge_vec = np.array(embedder.embed_query(challenge_name)).reshape(1, -1)

    tagged = []

    for path, content in refs:
        ref_vec = np.array(embedder.embed_query(content)).reshape(1, -1)
        score   = float(cosine_similarity(challenge_vec, ref_vec)[0][0])

        if score >= RELEVANCE_THRESHOLD:
            data = json.loads(path.read_text(encoding="utf-8"))
            existing = json.loads(data["metadata"].get("challenges", "[]")) \
                       if isinstance(data["metadata"].get("challenges"), str) \
                       else data["metadata"].get("challenges", [])

            if challenge_name not in existing:
                existing.append(challenge_name)
                data["metadata"]["challenges"] = existing
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            tagged.append(data["metadata"].get("customer", path.stem))

    return tagged


# ── Accept new challenge ──────────────────────────────────────────────────────

def accept_challenge(challenge_text: str) -> dict:
    """
    Full pipeline for a new challenge:
      1. Check for near-duplicates.
      2. If unique, embed + save to challenges.json.
      3. Tag matching references.

    Returns a result dict consumed by the FastAPI endpoint.
    """
    is_dup, similar_to, score = check_similarity(challenge_text)

    if is_dup:
        return {
            "accepted": False,
            "reason": "similar_exists",
            "similar_to": similar_to,
            "similarity_score": round(score, 4),
            "message": (
                f'A similar challenge already exists: "{similar_to}" '
                f"(similarity {score:.0%}). Use that one or rephrase."
            ),
        }

    # Embed and persist
    embedder  = get_embedder()
    embedding = embedder.embed_query(challenge_text)
    challenges = load_challenges()
    challenges.append({"name": challenge_text, "embedding": embedding})
    save_challenges(challenges)

    # Tag relevant references
    tagged = tag_references_with_challenge(challenge_text)

    return {
        "accepted": True,
        "challenge": challenge_text,
        "tagged_references": tagged,
        "tagged_count": len(tagged),
        "message": (
            f'Challenge accepted. '
            f"{len(tagged)} reference(s) tagged: {', '.join(tagged) or 'none'}."
        ),
    }


# ── Visualization data ────────────────────────────────────────────────────────

def challenge_reference_counts() -> list[dict]:
    """
    For each challenge, count how many reference files have it in their metadata.
    Used by the /visualization endpoint.
    """
    names = get_challenge_names()
    counts = []

    for name in names:
        count = 0
        for path in REFERENCES_DIR.glob("*.json"):
            if path.name == "_all.json":
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                ch_raw = data["metadata"].get("challenges", [])
                ch_list = json.loads(ch_raw) if isinstance(ch_raw, str) else ch_raw
                if name in ch_list:
                    count += 1
            except Exception:
                continue
        counts.append({"challenge": name, "reference_count": count})

    return sorted(counts, key=lambda x: x["reference_count"], reverse=True)
