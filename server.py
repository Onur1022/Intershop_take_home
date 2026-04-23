"""
server.py — FastAPI server
==========================
6 endpoints:
  POST /challenge/new        → accept + deduplicate a new challenge
  GET  /search               → RAG search filtered by challenge metadata
  GET  /visualization        → challenge → reference count (terminal bar chart)
  GET  /product-recommendation → LLM-based product suggestion via Azure AI
  GET  /challenges           → list all saved challenges
  GET  /endpoints            → list all available endpoints

Run:
    uvicorn server:app --reload --port 8000
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import challenges as ch_module
import rag as rag_module


PRODUCTS_FILE = Path("products.txt")

app = FastAPI(
    title="Intershop Reference Matcher",
    description="Match customer challenges to Intershop customer references.",
    version="1.0.0",
)


# ── 1. POST /challenge/new ────────────────────────────────────────────────────

class ChallengeRequest(BaseModel):
    challenge: str

@app.post("/challenge/new", summary="Submit a new customer challenge")
def new_challenge(body: ChallengeRequest):
    """
    Accepts a new challenge text.
    - Checks for near-duplicates (cosine similarity >= 0.85).
    - If unique: saves it, tags relevant reference JSONs, then runs /search.
    - Returns dedup result + search results if accepted.
    """
    text = body.challenge.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Challenge text cannot be empty.")

    result = ch_module.accept_challenge(text)

    if not result["accepted"]:
        return JSONResponse(status_code=409, content=result)

    # Auto-trigger search for the accepted challenge
    search_results = rag_module.search(text)
    result["search_results"] = search_results
    return result


# ── 2. GET /search ────────────────────────────────────────────────────────────

@app.get("/search", summary="Search references for a known challenge")
def search(
    challenge: str = Query(..., description="An existing challenge name to search for"),
    rebuild:   bool = Query(False, description="Force rebuild of the vector DB"),
):
    """
    Runs the RAG pipeline for an existing challenge.
    Only returns references that have the challenge tagged in their metadata.
    """
    if not ch_module.challenge_exists(challenge):
        raise HTTPException(
            status_code=404,
            detail=f'Challenge "{challenge}" not found. '
                   f"Add it first via POST /challenge/new.",
        )

    results = rag_module.search(challenge, rebuild=rebuild)

    if not results:
        return {
            "challenge": challenge,
            "results": [],
            "message": "No tagged references found for this challenge.",
        }

    return {"challenge": challenge, "count": len(results), "results": results}


# ── 3. GET /visualization ─────────────────────────────────────────────────────

@app.get("/visualization", summary="Challenge → reference count bar chart")
def visualization():
    """
    Returns each challenge with the number of references tagged to it.
    The CLI client renders this as a terminal bar chart.
    """
    counts = ch_module.challenge_reference_counts()
    if not counts:
        return {"message": "No challenges saved yet.", "data": []}
    return {"data": counts}


# ── 4. GET /product-recommendation ───────────────────────────────────────────

@app.get("/product-recommendation", summary="Recommend Intershop products for a challenge")
def product_recommendation(
    challenge: str = Query(..., description="An existing challenge to get recommendations for"),
):
    """
    Loads products.txt, sends challenge + products to Azure AI Foundry LLM,
    returns a product recommendation.
    """
    if not ch_module.challenge_exists(challenge):
        raise HTTPException(
            status_code=404,
            detail=f'Challenge "{challenge}" not found.',
        )

    if not PRODUCTS_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail="products.txt not found. Create it with Intershop product descriptions.",
        )

    products_text = PRODUCTS_FILE.read_text(encoding="utf-8").strip()
    if not products_text:
        raise HTTPException(status_code=503, detail="products.txt is empty.")

    recommendation = _call_azure_llm(challenge, products_text)
    return {"challenge": challenge, "recommendation": recommendation}


def _call_azure_llm(challenge: str, products_text: str) -> str:
    """
    Calls Azure AI Foundry (Azure OpenAI-compatible endpoint).
    Set these environment variables before starting the server:
        AZURE_OPENAI_ENDPOINT   e.g. https://your-resource.openai.azure.com/
        AZURE_OPENAI_API_KEY
        AZURE_OPENAI_DEPLOYMENT e.g. gpt-4o
        AZURE_OPENAI_API_VERSION e.g. 2024-02-01
    """
    try:
        from openai import AzureOpenAI
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="openai package not installed. Run: pip install openai",
        )

    endpoint   = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key    = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")

    if not endpoint or not api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "Azure credentials not set. "
                "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY env vars."
            ),
        )

    client = AzureOpenAI(
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=api_key,
    )

    prompt = f"""You are a sales advisor for Intershop Communications AG.

A prospect has the following business challenge:
"{challenge}"

Below are Intershop's available products and their descriptions:
---
{products_text}
---

Based on the challenge, recommend the most relevant Intershop product(s).
Explain in 2-3 sentences why each recommended product fits the challenge.
Be specific and concise."""

    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a sales advisor for Intershop Communications AG. Use only the given context",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        max_completion_tokens=16384,
        model=deployment,
    )
 
    return response.choices[0].message.content.strip()


# ── 5. GET /challenges ────────────────────────────────────────────────────────

@app.get("/challenges", summary="List all saved challenges")
def list_challenges():
    """Returns all challenge names currently stored in challenges.json."""
    names = ch_module.get_challenge_names()
    return {"count": len(names), "challenges": names}


# ── 6. GET /endpoints ─────────────────────────────────────────────────────────

@app.get("/endpoints", summary="List all available API endpoints")
def list_endpoints():
    """Returns a summary of all available endpoints."""
    return {
        "endpoints": [
            {
                "method": "POST",
                "path": "/challenge/new",
                "description": "Submit a new challenge. Deduplicates, tags references, auto-searches.",
                "body": {"challenge": "string"},
            },
            {
                "method": "GET",
                "path": "/search",
                "description": "Search references for an existing challenge.",
                "params": {"challenge": "string", "rebuild": "bool (optional)"},
            },
            {
                "method": "GET",
                "path": "/visualization",
                "description": "Returns challenge → reference counts for terminal bar chart.",
                "params": {},
            },
            {
                "method": "GET",
                "path": "/product-recommendation",
                "description": "Recommends Intershop products for a challenge via Azure LLM.",
                "params": {"challenge": "string"},
            },
            {
                "method": "GET",
                "path": "/challenges",
                "description": "Lists all saved challenge names.",
                "params": {},
            },
            {
                "method": "GET",
                "path": "/endpoints",
                "description": "Lists all available endpoints (this response).",
                "params": {},
            },
        ]
    }
