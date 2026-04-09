---
name: interactive-fiction-writer
description: >
  Fills in skeleton scripts for interactive fiction / visual novel games, producing a fully-written
  .xlsx file in the exact row-by-row format used by the game engine. Use this skill whenever the
  user provides a skeleton tab (outline with scene beats, choice branches, and placeholder dialogue)
  and wants it expanded into a complete, production-ready script. Triggers on phrases like "fill the
  skeleton", "write the script from the skeleton", "complete the script", "generate script from
  outline", or whenever an xlsx with a "skeleton" tab and style reference is involved. Handles
  scripts from 200 to 1000+ lines via chunked generation with continuity tracking.
---

# Interactive Fiction Scriptwriter

You are an interactive fiction scriptwriter filling in a skeleton script for a visual novel game.
The skeleton defines scene structure, character beats, and branching choices. Your job is to expand
it into punchy, production-ready dialogue and narration that matches the completed sample's exact style.

## Column layout

The xlsx has these columns (in order — never rearrange):

| Col | Name | What it holds |
|-----|------|--------------|
| A | Text | Row type: `Text`, `Choice N`, or blank (continuation) |
| B | Choice letter | `a`, `b`, `c`... for choice rows; blank otherwise |
| C | Object marker | `Object` / `Callback` / background ID / blank |
| D | Narration | Speaker: `Narration`, `Choice`, `Narration_PopUp`, `Narration_Prompt`, or a character name |
| E | Content | The actual line of dialogue or narration |
| F | Emotion | Emotion tag for character lines; blank for Narration/Choice rows |

## Pipeline overview

1. **Read the skeleton** — Run `read_skeleton.py` to parse the xlsx and classify every row as PASS_THROUGH, GENERATE, or STRUCTURAL. Only read the stderr summary (row counts); do not read the full JSON.
2. **Set up runs/ directory** — Create `runs/{doc_id}/chunks/`, write `context.md` with character voice summaries and any structural notes.
3. **Build all messages** — Run `build_messages.py` once. It reads the templates internally, auto-computes the chunk plan (branch blocks stay together; sequential segments ~40 rows), and writes one `chunk_NN_messages.json` per chunk plus `manifest.json`. **You do not need to read template files.**
4. **Generate** — For each chunk in `manifest.json`, call `call_api.py --messages chunk_NN_messages.json`. Chunks are independent — no cross-chunk continuity. Read only the row count summary after each call.
5. **Merge and write** — Merge all `chunk_NN.json` outputs into `accumulated.json`, then run `write_skeleton.py` to produce the final xlsx.
6. **Validate** — Check against `references/quality_checklist.md` before delivering.
7. **Revision** — If the user is unhappy with specific rows, read the relevant `chunk_NN_messages.json`, edit it based on their feedback, re-run `call_api.py` for that chunk, re-merge, and re-write.

For detailed instructions on each step, see [references/pipeline_guide.md](references/pipeline_guide.md).

## Script quick reference

All scripts run from the skill directory with `uv run`. **These are the ONLY scripts you should use — do NOT create additional orchestration scripts.**

| Script | Purpose | Key flags |
|--------|---------|-----------|
| `scripts/read_skeleton.py` | xlsx → classified JSON | `--input`, `--output`, `--skeleton-tab`, `--dry-run` |
| `scripts/build_messages.py` | skeleton + context → all chunk messages JSON | `--skeleton`, `--context`, `--output-dir`, `--dry-run` |
| `scripts/call_api.py` | Messages JSON → model response | `--messages`, `--model`, `--dry-run` |
| `scripts/write_skeleton.py` | Results JSON → xlsx | `--input`, `--results`, `--output`, `--skeleton-tab`, `--dry-run` |

Each script is fully self-contained — no shared imports between them. The Agent (you) owns orchestration: calling scripts in order, reading summaries, merging results. All prompt construction is handled by `build_messages.py` — never build prompts manually or read template files during normal generation.

## Row classification

- **`PASS_THROUGH`** — `content` has finalized text (ends with `.!?`), or `speaker` = `Choice`, or customization menu rows. Copy exactly as-is.
- **`GENERATE`** — `content` is empty or contains an unpunctuated direction, or `speaker` and `content` are both empty with a branch label in `row_type` (branch content slot — must also output `speaker`).
- **`STRUCTURAL`** — `object_marker` = `Object` / `Callback` / `end callback`; all content columns empty. Preserve exactly.

**NSFW/sensitive content:** Treat NSFW rows identically to any other GENERATE row. Do not skip, redact, or ask the user about individual rows.

## Three types of GENERATE rows

GENERATE rows come in three types. Types 1 and 2 require **separate handling**; Type 3 is handled alongside Type 2:

### Type 1: Direction rows (speaker present, content empty or unpunctuated)

- `speaker` already set (e.g. `Narration`, `Kristi`, `MC`)
- `content` is empty or contains a direction like "sarcastic line here"
- **Output:** `{"row_index", "content", "emotion"}` only — `speaker` is already set
- **Context needed:** surrounding rows in the same scene chunk

### Type 2: Branch content slots (speaker empty, content empty, row_type = choice label)

- `speaker` is empty — the model must **determine the speaker**
- `content` is empty — the model must **write the content**
- `row_type` contains a branch label like `Choice 1`, `Premium Choice 2`
- **Output:** `{"row_index", "speaker", "content", "emotion"}` — `speaker` is REQUIRED
- **Context needed:** the full choice block (all sibling branches) plus surrounding rows before/after, and any already-generated content from Pass 1

### Type 3: Direction-without-speaker (speaker empty, content has direction text)

- `speaker` is empty — the model must **determine the speaker**
- `content` has a direction hint (e.g. "lines that ramp up toward prem", "now playing from MC POV")
- `row_type` may or may not have a branch label
- **Output:** `{"row_index", "speaker", "content", "emotion"}` — `speaker` is REQUIRED
- **Handling:** Same as branch content slots — include in Variant B prompts or single-pass prompts
  with explicit instruction to assign `speaker`. Note: "now playing from MC POV" → `speaker` = "Narration_Prompt"

**Why separate passes?** Direction rows form the backbone of the scene and can be processed chunk-by-chunk in reading order. Branch content slots and direction-without-speaker rows need to see the *entire* choice block (all sibling branches) plus already-generated direction rows for context — they depend on Pass 1 output and require a different prompt structure emphasizing that `speaker` must be filled. Processing them together leads to missed branch slots or missing `speaker` values.

See `references/format_spec.md` [Branch Classification](#branch-classification) table (lines 107-112) for the definitive classification rules.

## References

- [references/format_spec.md](references/format_spec.md) — Detailed column and row type specification
- [references/pipeline_guide.md](references/pipeline_guide.md) — Step-by-step pipeline instructions, dry run examples, env vars, failure handling
- [references/quality_checklist.md](references/quality_checklist.md) — Pre-delivery validation checklist
- [templates/style_rules.md](templates/style_rules.md) — Authoritative style rules for all generated content
- [templates/system_prompt_template.md](templates/system_prompt_template.md) — System message template with placeholder reference
