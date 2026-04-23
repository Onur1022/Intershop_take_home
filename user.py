"""
user.py — CLI client for the Intershop Reference Matcher server
===============================================================
Usage examples:
    python user.py new "We want to sell in 20 countries"
    python user.py search "We want to sell in 20 countries"
    python user.py visualize
    python user.py recommend "We want to sell in 20 countries"
    python user.py challenges
    python user.py endpoints
"""

import argparse
import json
import sys

import requests

SERVER = "http://localhost:8000"


# ── Pretty printers ───────────────────────────────────────────────────────────

def print_json(data: dict) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def print_search_results(data: dict) -> None:
    challenge = data.get("challenge", "")
    results   = data.get("results", [])

    print(f"\nChallenge : {challenge}")
    print(f"Matches   : {len(results)}\n")
    print("─" * 60)

    for i, r in enumerate(results, 1):
        print(f"#{i}  {r['customer']}  (similarity: {r['similarity']})")
        print(f"    {r['page_content']}")
        link = r.get("read_more") or r.get("visit_shop", "")
        if link:
            print(f"    → {link}")
        print()


def print_bar_chart(data: list[dict]) -> None:
    if not data:
        print("No challenges yet.")
        return

    max_count = max(d["reference_count"] for d in data) or 1
    max_label = max(len(d["challenge"]) for d in data)
    bar_width  = 40

    print(f"\n{'Challenge':<{max_label}}  {'References':>10}  Chart")
    print("─" * (max_label + bar_width + 16))

    for d in data:
        label  = d["challenge"]
        count  = d["reference_count"]
        filled = int(count / max_count * bar_width)
        bar    = "█" * filled + "░" * (bar_width - filled)
        print(f"{label:<{max_label}}  {count:>10}  {bar}")

    print()


def print_new_challenge_result(data: dict) -> None:
    if not data.get("accepted"):
        print(f"\n✗  {data['message']}\n")
        return

    print(f"\n✓  {data['message']}\n")

    results = data.get("search_results", [])
    if results:
        print(f"Top matching references for this challenge:\n")
        print("─" * 60)
        for i, r in enumerate(results, 1):
            print(f"#{i}  {r['customer']}  (similarity: {r['similarity']})")
            print(f"    {r['page_content']}")
            link = r.get("read_more") or r.get("visit_shop", "")
            if link:
                print(f"    → {link}")
            print()
    else:
        print("No matching references found for this challenge.")


def print_recommendation(data: dict) -> None:
    print(f"\nChallenge : {data['challenge']}\n")
    print("Product Recommendation")
    print("─" * 60)
    print(data["recommendation"])
    print()


def print_challenges(data: dict) -> None:
    names = data.get("challenges", [])
    count = data.get("count", 0)
    print(f"\nSaved challenges ({count}):\n")
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")
    print()


def print_endpoints(data: dict) -> None:
    print("\nAvailable endpoints:\n")
    for ep in data.get("endpoints", []):
        print(f"  {ep['method']:<6} {ep['path']}")
        print(f"         {ep['description']}")
        if ep.get("params"):
            print(f"         Params: {ep['params']}")
        print()


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def post(path: str, body: dict) -> dict:
    try:
        r = requests.post(f"{SERVER}{path}", json=body, timeout=60)
    except requests.ConnectionError:
        print(f"✗  Cannot connect to server at {SERVER}. Is uvicorn running?")
        sys.exit(1)
    return r.json()


def get(path: str, params: dict | None = None) -> dict:
    try:
        r = requests.get(f"{SERVER}{path}", params=params, timeout=60)
    except requests.ConnectionError:
        print(f"✗  Cannot connect to server at {SERVER}. Is uvicorn running?")
        sys.exit(1)
    try:
        return r.json()
    except requests.exceptions.JSONDecodeError:
        print(f"✗  Server returned status {r.status_code} with non-JSON body:")
        print(r.text or "(empty response)")
        sys.exit(1)
# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_new(args):
    challenge = " ".join(args.text)
    print(f"Submitting challenge: \"{challenge}\" ...")
    data = post("/challenge/new", {"challenge": challenge})
    print_new_challenge_result(data)


def cmd_search(args):
    challenge = " ".join(args.text)
    print(f"Searching for: \"{challenge}\" ...")
    data = get("/search", {"challenge": challenge})
    if "detail" in data:
        print(f"\n✗  {data['detail']}\n")
    else:
        print_search_results(data)


def cmd_visualize(_args):
    data = get("/visualization")
    if "message" in data and not data.get("data"):
        print(f"\n{data['message']}\n")
    else:
        print_bar_chart(data.get("data", []))


def cmd_recommend(args):
    challenge = " ".join(args.text)
    print(f"Getting recommendation for: \"{challenge}\" ...")
    data = get("/product-recommendation", {"challenge": challenge})
    if "detail" in data:
        print(f"\n✗  {data['detail']}\n")
    else:
        print_recommendation(data)


def cmd_challenges(_args):
    data = get("/challenges")
    print_challenges(data)


def cmd_endpoints(_args):
    data = get("/endpoints")
    print_endpoints(data)


# ── Argument parser ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="user.py",
        description="CLI client for the Intershop Reference Matcher",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Submit a new challenge")
    p_new.add_argument("text", nargs="+", help="Challenge text (quote it or use multiple words)")
    p_new.set_defaults(func=cmd_new)

    p_search = sub.add_parser("search", help="Search references for an existing challenge")
    p_search.add_argument("text", nargs="+", help="Challenge name")
    p_search.set_defaults(func=cmd_search)

    p_vis = sub.add_parser("visualize", help="Show challenge → reference count bar chart")
    p_vis.set_defaults(func=cmd_visualize)

    p_rec = sub.add_parser("recommend", help="Get product recommendation for a challenge")
    p_rec.add_argument("text", nargs="+", help="Challenge name")
    p_rec.set_defaults(func=cmd_recommend)

    p_ch = sub.add_parser("challenges", help="List all saved challenges")
    p_ch.set_defaults(func=cmd_challenges)

    p_ep = sub.add_parser("endpoints", help="List all server endpoints")
    p_ep.set_defaults(func=cmd_endpoints)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
