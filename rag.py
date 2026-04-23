"""
rag.py — vector search with challenge metadata filtering

Pipeline:
  1. Load (or build) ChromaDB vectorstore from references/
  2. Retrieve top-N candidates by embedding similarity
  3. Filter: only keep results whose JSON metadata.challenges includes the query challenge
  4. Return top K of the filtered set
"""

import json
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma

from embedder import get_embedder

REFERENCES_DIR = Path("references")
CHROMA_DIR     = Path("chroma_db")
COLLECTION     = "intershop_references"

CANDIDATE_K  = 15   # how many chunks to pull from vector DB before filtering
FINAL_TOP_K  = 5    # max results returned to the user


# ── Vectorstore build / load ──────────────────────────────────────────────────

def _load_documents() -> list[Document]:
    docs = []
    for path in sorted(REFERENCES_DIR.glob("*.json")):
        if path.name == "_all.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        content = data.get("page_content", "").strip()
        if not content:
            continue

        meta = {}
        for k, v in data.get("metadata", {}).items():
            if isinstance(v, list):
                meta[k] = json.dumps(v, ensure_ascii=False)
            elif v is None:
                meta[k] = ""
            else:
                meta[k] = v

        docs.append(Document(page_content=content, metadata=meta))
    return docs


def get_vectorstore(rebuild: bool = False) -> Chroma:
    embedder = get_embedder()

    if CHROMA_DIR.exists() and not rebuild:
        return Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=embedder,
            collection_name=COLLECTION,
        )

    docs = _load_documents()
    if not docs:
        raise RuntimeError(
            "No documents found in references/. Run scrape_references.py first."
        )

    vs = Chroma.from_documents(
        documents=docs,
        embedding=embedder,
        persist_directory=str(CHROMA_DIR),
        collection_name=COLLECTION,
    )
    print(f"[rag] Built vectorstore with {vs._collection.count()} vectors.")
    return vs


# ── Search ────────────────────────────────────────────────────────────────────

def search(challenge: str, rebuild: bool = False) -> list[dict]:
    """
    Search the vectorstore for references relevant to `challenge`.

    Steps:
      1. Pull CANDIDATE_K results from ChromaDB.
      2. For each result, open the original JSON and check if `challenge`
         is listed in metadata.challenges.
      3. Return up to FINAL_TOP_K of the ones that pass the filter.

    Returns list of dicts ready to serialize as JSON.
    """
    vs = get_vectorstore(rebuild=rebuild)
    raw_results = vs.similarity_search_with_score(challenge, k=CANDIDATE_K)

    filtered = []

    for doc, score in raw_results:
        customer = doc.metadata.get("customer", "")
        if not customer:
            continue

        # Re-open the source JSON to read current metadata.challenges
        slug = customer.lower().replace(" ", "_")
        candidate_paths = list(REFERENCES_DIR.glob(f"{slug}.json"))
        if not candidate_paths:
            # fallback: scan all files for matching customer name
            candidate_paths = [
                p for p in REFERENCES_DIR.glob("*.json")
                if p.name != "_all.json" and
                json.loads(p.read_text()).get("metadata", {}).get("customer", "") == customer
            ]

        if not candidate_paths:
            continue

        data   = json.loads(candidate_paths[0].read_text(encoding="utf-8"))
        ch_raw = data["metadata"].get("challenges", [])
        ch_list = json.loads(ch_raw) if isinstance(ch_raw, str) else ch_raw

        if challenge not in ch_list:
            continue  # this reference was not tagged for this challenge

        meta = data["metadata"]
        result = {
            "customer":    customer,
            "page_content": doc.page_content,
            "similarity":  round(1 - score, 4),   # Chroma returns distance
            "challenges":  ch_list,
        }
        if "read_more"  in meta: result["read_more"]  = meta["read_more"]
        if "visit_shop" in meta: result["visit_shop"] = meta["visit_shop"]
        if "logo_url"   in meta: result["logo_url"]   = meta["logo_url"]

        filtered.append(result)

        if len(filtered) >= FINAL_TOP_K:
            break

    return filtered
