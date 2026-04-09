# Pipeline Guide

Step-by-step instructions for running the interactive fiction writing pipeline.

The four scripts are thin tools — you own orchestration (calling scripts, merging results).
**Do NOT read template files during generation; `build_messages.py` handles that.**
**Do NOT create additional Python scripts.**

Always run with `uv run` from the skill directory:

```bash
cd .claude/skills/interactive-fiction-writer
```

---

## Step 0 — Validate file structure

```python
import pandas as pd
xl = pd.read_excel('input.xlsx', sheet_name=None, header=None)
print(list(xl.keys()))          # list all tab names
print(xl['Skeleton'].iloc[:3])  # preview first 3 rows
```

Expected column order: A=row type, B=choice letter, C=object marker, D=speaker, E=content, F=emotion.

---

## Step 1 — Read the skeleton

```bash
uv run python scripts/read_skeleton.py \
  --input path/to/script.xlsx \
  --skeleton-tab "Skeleton" \
  --output runs/{doc_id}/skeleton_rows.json
```

Only look at the **stderr summary** (row counts by classification). Do not read the full JSON into context.

---

## Step 1.5 — Set up runs/ directory and context.md

Derive `{doc_id}` from the xlsx filename: strip extension, replace spaces with `_`.

```bash
mkdir -p runs/{doc_id}/chunks
```

Write `runs/{doc_id}/context.md` with:

```markdown
# Context: {doc_id}

## Characters
- CharA: voice summary (tone, sentence length, favorite patterns)
- CharB: voice summary

## Special notes
- Any structural quirks, unusual patterns, or deviations from standard format
```

**Resume detection:** if `runs/{doc_id}/skeleton_rows.json` already exists, skip Step 1.
If `runs/{doc_id}/chunks/manifest.json` exists, skip Step 2 (messages already built).

---

## Step 2 — Build all chunk messages (do this ONCE)

```bash
uv run python scripts/build_messages.py \
  --skeleton runs/{doc_id}/skeleton_rows.json \
  --context  runs/{doc_id}/context.md \
  --output-dir runs/{doc_id}/chunks/
```

This script reads `templates/style_rules.md` and `templates/system_prompt_template.md`
internally. **You do not need to read those files.** It auto-computes the chunk plan
from the skeleton structure (branch blocks stay together; sequential segments ~40 rows each)
and writes one `chunk_NN_messages.json` per chunk plus `manifest.json`.

Check the output with a dry run first:

```bash
uv run python scripts/build_messages.py \
  --skeleton runs/{doc_id}/skeleton_rows.json \
  --context  runs/{doc_id}/context.md \
  --output-dir runs/{doc_id}/chunks/ \
  --dry-run
```

---

## Step 3 — Generate: call API for each chunk

Read `manifest.json` to get the list of chunks, then call the API for each:

```bash
# For each chunk_id in manifest["chunks"]:
uv run python scripts/call_api.py \
  --messages runs/{doc_id}/chunks/chunk_NN_messages.json \
  --model deepseek/deepseek-chat-v3-0324 \
  > runs/{doc_id}/chunks/chunk_NN.json
```

After each call, read only the **row count summary** — not the full response:

```bash
uv run python -c "
import json
data = json.load(open('runs/{doc_id}/chunks/chunk_NN.json'))
print(f'chunk_NN: {len(data)} rows generated, indices {[x[\"row_index\"] for x in data]}')
"
```

Chunks are **independent** — each chunk contains a complete self-contained unit
(a full choice block, or a sequential segment). There is no continuity dependency
between chunks; you can process them in any order.

### Failure handling

**JSON parse failure:** `call_api.py` auto-repairs via `json_repair`. If still invalid:

```bash
# Append corrective user message and retry:
uv run python -c "
import json
msgs = json.load(open('runs/{doc_id}/chunks/chunk_NN_messages.json'))
msgs.append({'role': 'assistant', 'content': open('runs/{doc_id}/chunks/chunk_NN.json').read()})
msgs.append({'role': 'user', 'content': 'Your response was not valid JSON. Return ONLY a JSON array, no preamble, no markdown fences.'})
json.dump(msgs, open('runs/{doc_id}/chunks/chunk_NN_messages.json', 'w'), ensure_ascii=False, indent=2)
"
uv run python scripts/call_api.py \
  --messages runs/{doc_id}/chunks/chunk_NN_messages.json \
  > runs/{doc_id}/chunks/chunk_NN.json
```

**Partial response (missing rows):** retry with the same messages file. After 3 failures, log the missing row indices and move on — they will be caught in Step 3.5.

---

## Step 3.5 — Retry missing rows

After all chunks complete, check for any GENERATE rows not in any chunk output:

```bash
uv run python -c "
import json, glob
skel = json.load(open('runs/{doc_id}/skeleton_rows.json'))
gen_indices = {r['row_index'] for r in skel if r.get('classification') == 'GENERATE'}
done_indices = set()
for f in glob.glob('runs/{doc_id}/chunks/chunk_*.json'):
    if '_messages' not in f:
        done_indices |= {r['row_index'] for r in json.load(open(f))}
missing = sorted(gen_indices - done_indices)
print(f'Missing {len(missing)} rows: {missing}')
"
```

For each missing row (or small group), edit the relevant `chunk_NN_messages.json` to add a
focused retry instruction, then re-run `call_api.py`.

---

## Step 4 — Merge results and write xlsx

Merge all chunk outputs into a single results file:

```bash
uv run python -c "
import json, glob
all_results = []
for f in sorted(glob.glob('runs/{doc_id}/chunks/chunk_*.json')):
    if '_messages' not in f and 'manifest' not in f:
        all_results.extend(json.load(open(f)))
# Deduplicate by row_index (last write wins)
seen = {}
for r in all_results:
    seen[r['row_index']] = r
json.dump(list(seen.values()), open('runs/{doc_id}/chunks/accumulated.json', 'w'), ensure_ascii=False, indent=2)
print(f'Merged {len(seen)} rows')
"
```

Then write the output xlsx:

```bash
uv run python scripts/write_skeleton.py \
  --input path/to/script.xlsx \
  --results runs/{doc_id}/chunks/accumulated.json \
  --output runs/{doc_id}/final_completed.xlsx \
  --skeleton-tab "Skeleton"
```

Validate with dry run first:

```bash
uv run python scripts/write_skeleton.py \
  --input path/to/script.xlsx \
  --results runs/{doc_id}/chunks/accumulated.json \
  --output runs/{doc_id}/final_completed.xlsx \
  --skeleton-tab "Skeleton" \
  --dry-run
```

After writing, validate against `references/quality_checklist.md`.

---

## Revision workflow (user unhappy with a chunk)

When the user wants different output for specific rows:

1. Read the relevant `chunk_NN_messages.json` to understand the current prompt
2. Edit the system message or user message as needed (e.g., add character-specific feedback)
3. Re-run `call_api.py` for that chunk
4. Re-merge and re-run `write_skeleton.py`

```bash
# After editing chunk_NN_messages.json:
uv run python scripts/call_api.py \
  --messages runs/{doc_id}/chunks/chunk_NN_messages.json \
  > runs/{doc_id}/chunks/chunk_NN.json
# Then re-merge (Step 4) and re-write xlsx
```

---

## Environment variables & defaults

- **Required:** `OPENROUTER_API_KEY`
- **Default model:** `deepseek/deepseek-chat-v3-0324`

---

## NSFW / sensitive content handling

NSFW and sexually explicit rows **must be written** — treat them identically to any other GENERATE row.

---

## Full pipeline summary

```
1. read_skeleton.py → skeleton_rows.json          (read stderr summary only)
2. Write context.md with characters               (agent writes this)
3. build_messages.py → chunk_NN_messages.json     (do not read templates manually)
4. call_api.py for each chunk → chunk_NN.json     (read row count summary only)
5. Merge chunk outputs → accumulated.json          (one-liner Python)
6. write_skeleton.py → final_completed.xlsx
7. Validate quality_checklist.md
```
