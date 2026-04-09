#!/usr/bin/env python3
"""
call_api.py — Single stateless API call: read messages JSON, output model response.

Standalone CLI. No dependencies on other scripts in this directory.
"""

import argparse
import json
import os
import re
import sys
import dotenv
from json_repair import repair_json

dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), "../", ".env"))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "deepseek/deepseek-chat-v3-0324"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

def get_client():
    from openai import OpenAI
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("[ERROR] OPENROUTER_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)
    return OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Single stateless API call: read messages JSON, output model response to stdout."
    )
    parser.add_argument("--messages", required=True, help="Path to messages JSON file (OpenAI format)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenRouter model ID (default: {DEFAULT_MODEL})")
    parser.add_argument("--dry-run", action="store_true", help="Print request summary without calling API")
    args = parser.parse_args()

    with open(args.messages, "r", encoding="utf-8") as f:
        messages = json.load(f)

    if args.dry_run:
        print(json.dumps({"dry_run": True, "model": args.model, "message_count": len(messages)}))
        return

    client = get_client()
    response = client.chat.completions.create(
        model=args.model,
        messages=messages,
        max_tokens=8192,
        temperature=0.85,
    )
    raw = response.choices[0].message.content.strip()
    # Strip markdown fences if present
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    # Attempt JSON repair (handles trailing commas, missing quotes, etc.)
    repaired = repair_json(raw, return_objects=False)
    print(repaired)


if __name__ == "__main__":
    main()
