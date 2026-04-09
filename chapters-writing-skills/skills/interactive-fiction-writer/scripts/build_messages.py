#!/usr/bin/env python3
"""
build_messages.py — Pre-render API messages for all chunks.

Reads skeleton_rows.json + context.md, auto-computes chunk plan from the
skeleton structure, and writes one messages JSON per chunk (OpenAI format)
plus a manifest.json index.

The agent does NOT need to read template files or build prompts manually.
All prompt construction happens here, invisibly to the agent.

Usage:
    uv run python scripts/build_messages.py \\
        --skeleton runs/{doc_id}/skeleton_rows.json \\
        --context  runs/{doc_id}/context.md \\
        --output-dir runs/{doc_id}/chunks/

Outputs:
    runs/{doc_id}/chunks/chunk_01_messages.json
    runs/{doc_id}/chunks/chunk_02_messages.json
    ...
    runs/{doc_id}/chunks/manifest.json
"""

import argparse
import json
import os
import re
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Patterns / constants
# ---------------------------------------------------------------------------

BRANCH_LABEL_RE = re.compile(
    r"^(Premium\s+|Sub\s+)?Choice\s+\d+", re.IGNORECASE
)

SPEAKER_TYPES = {"Narration", "Narration_PopUp", "Narration_Prompt", "Choice"}

PRE_CONTEXT_SEQUENTIAL = 3
POST_CONTEXT_SEQUENTIAL = 3
PRE_CONTEXT_BRANCH = 6
POST_CONTEXT_BRANCH = 6


# ---------------------------------------------------------------------------
# Chunking algorithm
# ---------------------------------------------------------------------------

def is_branch_header(row: dict) -> bool:
    """Choice block header: col_A has branch label AND col_B has a letter."""
    return (
        bool(BRANCH_LABEL_RE.match(row.get("col_A", "")))
        and bool(row.get("col_B", "").strip())
    )


def is_branch_row(row: dict) -> bool:
    """Any row belonging to a branch (col_A has branch label, with or without col_B)."""
    return bool(BRANCH_LABEL_RE.match(row.get("col_A", "")))


def compute_chunks(rows: list, sequential_size: int = 40) -> list:
    """
    Divide rows into self-contained chunks:
    - 'branch': a complete choice block (all parallel branches up to convergence)
    - 'sequential': up to sequential_size non-branch rows

    Rules:
    - Never split a choice block across chunks.
    - Prefer scene breaks (background change, POV switch) as sequential boundaries.
    - Each chunk is independent — no cross-chunk continuity dependency.
    """
    chunks = []
    i = 0
    n = len(rows)

    while i < n:
        row = rows[i]
        if is_branch_header(row):
            # Collect all consecutive branch rows
            j = i + 1
            while j < n and is_branch_row(rows[j]):
                j += 1
            # j = convergence point (first non-branch row)
            chunks.append({
                "type": "branch",
                "start": i,
                "end": j - 1,
                "convergence_start": j,
            })
            i = j
        else:
            # Sequential segment
            end = min(i + sequential_size, n)
            # Do not enter a branch block mid-chunk
            for k in range(i, end):
                if is_branch_header(rows[k]) and k > i:
                    end = k
                    break
            if end <= i:
                end = i + 1  # safety: always advance
            chunks.append({
                "type": "sequential",
                "start": i,
                "end": end - 1,
            })
            i = end

    return chunks


# ---------------------------------------------------------------------------
# Style reference selection
# ---------------------------------------------------------------------------

def select_style_ref(rows: list, max_count: int = 6) -> list:
    """
    Pick representative PASS_THROUGH rows for the STYLE_REFERENCE section.
    Strategy: at most 2 rows per named character, 1 narration, 1 choice label.
    """
    char_seen: dict = {}
    selected = []
    narration_added = False
    choice_added = False

    for row in rows:
        if row.get("classification") != "PASS_THROUGH":
            continue
        col_d = row.get("col_D", "")
        col_e = row.get("col_E", "")
        if not col_e:
            continue

        if col_d == "Choice" and not choice_added:
            selected.append(row)
            choice_added = True
        elif col_d == "Narration" and not narration_added:
            selected.append(row)
            narration_added = True
        elif col_d and col_d not in SPEAKER_TYPES:
            if char_seen.get(col_d, 0) < 2:
                selected.append(row)
                char_seen[col_d] = char_seen.get(col_d, 0) + 1

        if len(selected) >= max_count:
            break

    return selected


# ---------------------------------------------------------------------------
# Row serialization
# ---------------------------------------------------------------------------

# Maps internal col_X keys (used in skeleton_rows.json) to semantic names
# sent to the model. Internal pipeline logic continues to use col_X.
COL_ALIAS = {
    "col_A": "row_type",
    "col_B": "choice_letter",
    "col_C": "object_marker",
    "col_D": "speaker",
    "col_E": "content",
    "col_F": "emotion",
}


def _row_to_dict(row: dict) -> dict:
    """Compact row dict: omit empty-string fields, keep row_index always.
    Field names are translated to semantic aliases for clarity in model prompts."""
    d: dict = {"row_index": row["row_index"]}
    for field in ("col_A", "col_B", "col_C", "col_D", "col_E", "col_F", "classification"):
        val = row.get(field, "")
        if val:
            d[COL_ALIAS.get(field, field)] = val
    return d


def format_rows(rows: list) -> str:
    """Render rows as a compact JSON array (one object per line)."""
    if not rows:
        return "[]"
    lines = [json.dumps(_row_to_dict(r), ensure_ascii=False) for r in rows]
    return "[\n" + ",\n".join(lines) + "\n]"


# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------

def _load_variant(template_dir: str, variant_letter: str) -> str:
    """Load a prompt template from templates/system_prompt_variant_<letter>.md."""
    filename = f"system_prompt_variant_{variant_letter.lower()}.md"
    path = os.path.join(template_dir, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


# ---------------------------------------------------------------------------
# Context.md parsing
# ---------------------------------------------------------------------------

def _parse_characters(context_md: str) -> str:
    """Extract the ## Characters bullet list from context.md."""
    m = re.search(r"## Characters\n(.*?)(?:\n##|\Z)", context_md, re.DOTALL)
    if m:
        return m.group(1).strip()
    return "(no character data found in context.md)"


# ---------------------------------------------------------------------------
# Prompt construction helpers
# ---------------------------------------------------------------------------

def _strip_section(text: str, header: str, placeholder: str) -> str:
    """
    Remove a complete section block from the template text.
    Handles the '---\\n\\nHEADER\\n{{PLACEHOLDER}}' pattern and the trailing '---'.
    """
    # Pattern: optional leading ---, blank line, header, placeholder, optional trailing ---
    pattern = (
        rf"---\s*\n\s*\n{re.escape(header)}\s*\n\s*"
        rf"{re.escape(placeholder)}\s*\n\s*(?=---)"
    )
    result = re.sub(pattern, "---\n\n", text, count=1)
    if result == text:
        # Fallback: just remove header + placeholder line
        result = text.replace(f"{header}\n{placeholder}", "")
    return result


def _fill_variant_a(
    template: str,
    style_rules: str,
    characters: str,
    style_ref_rows: list,
    chunk_rows: list,
    convergence_rows: Optional[list],
) -> str:
    """Fill Variant A (sequential / direction rows). Removes CONTINUITY always."""
    prompt = template
    prompt = prompt.replace("{{STYLE_RULES_CONTENT}}", style_rules)
    prompt = prompt.replace("{{CHARACTERS}}", characters)
    prompt = prompt.replace("{{STYLE_REFERENCE}}", format_rows(style_ref_rows))

    # Remove CONTINUITY section (chunks are independent)
    prompt = _strip_section(prompt, "CONTINUITY", "{{CONTINUITY}}")

    if convergence_rows:
        prompt = prompt.replace("{{CONVERGENCE_CONTEXT}}", format_rows(convergence_rows))
    else:
        prompt = _strip_section(prompt, "CONVERGENCE CONTEXT", "{{CONVERGENCE_CONTEXT}}")

    prompt = prompt.replace("{{ROWS}}", format_rows(chunk_rows))

    # Check for any remaining unfilled placeholders and warn
    unfilled = re.findall(r"\{\{[A-Z_]+\}\}", prompt)
    if unfilled:
        print(
            f"[build] WARNING: unfilled placeholders in Variant A: {unfilled}",
            file=sys.stderr,
        )

    return prompt


def _fill_variant_b(
    template: str,
    style_rules: str,
    characters: str,
    style_ref_rows: list,
    pre_context_rows: list,
    branch_rows: list,
    convergence_rows: list,
    post_context_rows: list,
) -> str:
    """Fill Variant B (branch choice block: direction rows + branch slots combined)."""
    prompt = template
    prompt = prompt.replace("{{STYLE_RULES_CONTENT}}", style_rules)
    prompt = prompt.replace("{{CHARACTERS}}", characters)
    prompt = prompt.replace("{{STYLE_REFERENCE}}", format_rows(style_ref_rows))
    prompt = prompt.replace("{{CONVERGENCE_CONTEXT}}", format_rows(convergence_rows))
    prompt = prompt.replace("{{PRE_CONTEXT}}", format_rows(pre_context_rows))
    prompt = prompt.replace("{{ROWS}}", format_rows(branch_rows))
    prompt = prompt.replace("{{POST_CONTEXT}}", format_rows(post_context_rows))

    unfilled = re.findall(r"\{\{[A-Z_]+\}\}", prompt)
    if unfilled:
        print(
            f"[build] WARNING: unfilled placeholders in Variant B: {unfilled}",
            file=sys.stderr,
        )

    return prompt


# ---------------------------------------------------------------------------
# Messages builders
# ---------------------------------------------------------------------------

def build_sequential_messages(
    chunk: dict,
    all_rows: list,
    style_rules: str,
    characters: str,
    style_ref_rows: list,
    variant_a: str,
) -> list:
    """Build OpenAI-format messages for a sequential chunk."""
    start = chunk["start"]
    end = chunk["end"]

    pre = all_rows[max(0, start - PRE_CONTEXT_SEQUENTIAL) : start]
    main = all_rows[start : end + 1]
    post = all_rows[end + 1 : end + 1 + POST_CONTEXT_SEQUENTIAL]
    chunk_rows = pre + main + post

    # Check for branch slots that snuck into a sequential chunk
    has_branch_slots = any(
        r.get("classification") == "GENERATE" and not r.get("col_D")
        for r in main
    )

    system = _fill_variant_a(
        variant_a,
        style_rules,
        characters,
        style_ref_rows,
        chunk_rows,
        convergence_rows=None,
    )

    if has_branch_slots:
        system += (
            "\n\nNOTE: This chunk contains branch content slots "
            "(speaker empty, content empty). For those rows you MUST also "
            "determine speaker and include it in the output."
        )

    user = (
        "Generate content for the GENERATE rows in this chunk. "
        "Return ONLY a JSON array, no preamble, no markdown fences."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_branch_messages(
    chunk: dict,
    all_rows: list,
    style_rules: str,
    characters: str,
    style_ref_rows: list,
    variant_b: str,
) -> list:
    """Build OpenAI-format messages for a branch (choice block) chunk."""
    start = chunk["start"]
    end = chunk["end"]
    conv_start = chunk.get("convergence_start", end + 1)

    pre = all_rows[max(0, start - PRE_CONTEXT_BRANCH) : start]
    branch = all_rows[start : end + 1]
    convergence = all_rows[conv_start : conv_start + 3]
    post = all_rows[conv_start : conv_start + POST_CONTEXT_BRANCH]

    system = _fill_variant_b(
        variant_b,
        style_rules,
        characters,
        style_ref_rows,
        pre_context_rows=pre,
        branch_rows=branch,
        convergence_rows=convergence,
        post_context_rows=post,
    )

    user = (
        "Generate content for ALL GENERATE rows in this choice block. "
        "For branch content slots (speaker empty), you MUST include speaker. "
        "For direction rows (speaker present), output content and emotion only. "
        "Return ONLY a JSON array, no preamble, no markdown fences."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Pre-render API messages for all chunks from skeleton_rows.json. "
            "Writes one messages JSON per chunk + manifest.json."
        )
    )
    parser.add_argument(
        "--skeleton", required=True, help="Path to skeleton_rows.json"
    )
    parser.add_argument(
        "--context", required=True, help="Path to context.md (characters + notes)"
    )
    parser.add_argument(
        "--output-dir", required=True, help="Directory for output messages files"
    )
    parser.add_argument(
        "--style-rules",
        default=os.path.join(os.path.dirname(__file__), "../templates/style_rules.md"),
        help="Path to style_rules.md (default: ../templates/style_rules.md)",
    )
    parser.add_argument(
        "--template-dir",
        default=os.path.join(os.path.dirname(__file__), "../templates"),
        help="Directory containing system_prompt_variant_a.md and system_prompt_variant_b.md",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=40,
        help="Target rows per sequential chunk (default: 40)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print chunk plan without writing any files",
    )
    args = parser.parse_args()

    # --- Load inputs ---
    with open(args.skeleton, "r", encoding="utf-8") as f:
        rows: list = json.load(f)

    with open(args.context, "r", encoding="utf-8") as f:
        context_md: str = f.read()

    with open(args.style_rules, "r", encoding="utf-8") as f:
        style_rules: str = f.read().strip()

    variant_a = _load_variant(args.template_dir, "A")
    variant_b = _load_variant(args.template_dir, "B")

    characters = _parse_characters(context_md)
    style_ref_rows = select_style_ref(rows)
    chunks = compute_chunks(rows, sequential_size=args.chunk_size)

    # --- Dry run ---
    if args.dry_run:
        total_gen = sum(1 for r in rows if r.get("classification") == "GENERATE")
        active = sum(
            1 for c in chunks
            if sum(1 for r in rows[c["start"]:c["end"]+1] if r.get("classification") == "GENERATE") > 0
        )
        print(
            f"[build] DRY RUN — {len(rows)} rows ({total_gen} GENERATE) → "
            f"{len(chunks)} chunks ({active} active), {len(style_ref_rows)} style-ref rows"
        )
        for i, c in enumerate(chunks, 1):
            chunk_rows = rows[c["start"] : c["end"] + 1]
            n_gen = sum(1 for r in chunk_rows if r.get("classification") == "GENERATE")
            skip = " [SKIP]" if n_gen == 0 else ""
            print(
                f"  Chunk {i:02d}: rows {c['start']}-{c['end']} "
                f"({c['type']}, {len(chunk_rows)} rows, {n_gen} GENERATE){skip}"
            )
        return

    # --- Build and write ---
    os.makedirs(args.output_dir, exist_ok=True)

    manifest: dict = {"chunks": []}

    for i, chunk in enumerate(chunks, 1):
        chunk_rows = rows[chunk["start"] : chunk["end"] + 1]
        n_gen = sum(1 for r in chunk_rows if r.get("classification") == "GENERATE")

        # Skip chunks with nothing to generate
        if n_gen == 0:
            print(
                f"[build] chunk_{i:02d}: rows {rows[chunk['start']]['row_index']}-"
                f"{rows[chunk['end']]['row_index']} — skipped (0 GENERATE rows)",
                file=sys.stderr,
            )
            continue

        chunk_id = f"chunk_{i:02d}"
        messages_file = os.path.join(args.output_dir, f"{chunk_id}_messages.json")

        if chunk["type"] == "branch":
            messages = build_branch_messages(
                chunk=chunk,
                all_rows=rows,
                style_rules=style_rules,
                characters=characters,
                style_ref_rows=style_ref_rows,
                variant_b=variant_b,
            )
        else:
            messages = build_sequential_messages(
                chunk=chunk,
                all_rows=rows,
                style_rules=style_rules,
                characters=characters,
                style_ref_rows=style_ref_rows,
                variant_a=variant_a,
            )

        with open(messages_file, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

        row_start = rows[chunk["start"]]["row_index"]
        row_end = rows[chunk["end"]]["row_index"]

        manifest["chunks"].append({
            "id": chunk_id,
            "messages_file": f"{chunk_id}_messages.json",
            "row_range": [row_start, row_end],
            "type": chunk["type"],
            "generate_count": n_gen,
        })

        print(
            f"[build] {chunk_id}: rows {row_start}-{row_end} "
            f"({chunk['type']}, {n_gen} GENERATE) → {messages_file}",
            file=sys.stderr,
        )

    manifest_file = os.path.join(args.output_dir, "manifest.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(
        f"[build] Done — {len(chunks)} chunks written to {args.output_dir}/ "
        f"(manifest: {manifest_file})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
