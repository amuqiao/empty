#!/usr/bin/env python3
"""
read_skeleton.py — Read xlsx skeleton tab and output structured JSON.

Standalone CLI: classifies each row as PASS_THROUGH / GENERATE / STRUCTURAL.
No dependencies on other scripts in this directory.

Column mapping (0-indexed):
  0=Text(row type)  1=Choice letter  2=Object marker
  3=Narration/Speaker  4=Content  5=Emotion
"""

import argparse
import json
import re
import sys

import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EMOTIONS = {
    "angry", "smile", "laughing", "flirty", "neutral",
    "sad", "shocked", "confused", "eyesclosed", "shy",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_tab(path: str, tab: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=tab, header=None)


def get_cell(row: pd.Series, col: int) -> str:
    v = row.iloc[col] if col < len(row) else None
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def is_finalized(text: str) -> bool:
    if not text:
        return False
    return text[-1] in ".!?…" or text.endswith('."') or text.endswith('!"') or text.endswith('?"')


def classify_row(row: pd.Series) -> str:
    """
    Classify a skeleton row as PASS_THROUGH / GENERATE / STRUCTURAL.
    NSFW detection is deliberately omitted — the Agent decides how to handle sensitive content.

    Branch content slots: rows where col_A has a branch label (e.g. "Choice 1",
    "Premium Choice 1", "Sub Choice 2") but col_D and col_E are both empty.
    These are content slots to be filled — NOT structural no-ops.
    """
    col_a = get_cell(row, 0)
    col_c = get_cell(row, 2)
    col_d = get_cell(row, 3)
    col_e = get_cell(row, 4)

    if col_c in ("Object", "Callback", "end callback"):
        return "STRUCTURAL"
    if not col_d and not col_e:
        # A branch label in col_A means this is a content slot for that branch
        if col_a and re.match(r"(Premium\s+)?(Sub\s+)?Choice", col_a, re.IGNORECASE):
            return "GENERATE"
        return "STRUCTURAL"
    if col_d == "Choice":
        return "PASS_THROUGH"
    if col_d in ("Narration_PopUp", "Narration_Prompt"):
        return "PASS_THROUGH" if col_e else "GENERATE"
    if is_finalized(col_e):
        return "PASS_THROUGH"
    return "GENERATE"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Read xlsx skeleton tab and output structured JSON with row classifications."
    )
    parser.add_argument("--input", required=True, help="Path to input xlsx")
    parser.add_argument("--output", help="Output path for JSON file (default: stdout)")
    parser.add_argument("--skeleton-tab", default="Skeleton", help="Tab name for skeleton")
    parser.add_argument("--dry-run", action="store_true", help="Parse and classify without writing output file")
    args = parser.parse_args()

    skeleton_df = load_tab(args.input, args.skeleton_tab)

    rows_json = []
    for _, row in skeleton_df.iterrows():
        cls = classify_row(row)
        rows_json.append({
            "row_index": int(row.name),
            "col_A": get_cell(row, 0),
            "col_B": get_cell(row, 1),
            "col_C": get_cell(row, 2),
            "col_D": get_cell(row, 3),
            "col_E": get_cell(row, 4),
            "col_F": get_cell(row, 5),
            "classification": cls,
        })

    if args.dry_run:
        counts = {}
        for r in rows_json:
            counts[r["classification"]] = counts.get(r["classification"], 0) + 1
        print(f"[read] DRY RUN — {len(rows_json)} rows: {counts}", file=sys.stderr)
        return

    output = json.dumps(rows_json, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[read] Wrote {len(rows_json)} rows to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
