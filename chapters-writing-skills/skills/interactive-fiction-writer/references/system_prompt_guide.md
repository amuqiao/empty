# System Prompt Guide

`build_messages.py` constructs all prompts automatically. You do not need to fill or read the
template files manually during normal generation — run `build_messages.py` instead.

Read this file when you need to understand or edit a system prompt (e.g., a chunk's output is
wrong and you want to tweak the instructions).

---

## Template files

The actual prompt templates live in `templates/`:

- `templates/system_prompt_variant_a.md` — for sequential chunks (direction rows where speaker is
  already present)
- `templates/system_prompt_variant_b.md` — for branch chunks (complete choice block — direction
  rows + branch slots combined)

Each file contains only the prompt text with `{{PLACEHOLDER}}` markers. No comments, no fences.

---

## How `build_messages.py` builds prompts

1. Loads the variant file for each chunk type
2. Fills all `{{PLACEHOLDER}}` markers (see table below)
3. Prepends the system prompt + appends a user turn
4. Writes the result to `chunk_NN_messages.json`

### Placeholder reference

| Placeholder | Source | Variant | Notes |
|---|---|---|---|
| `{{STYLE_RULES_CONTENT}}` | `templates/style_rules.md` (full text) | A & B | Same for all chunks |
| `{{CHARACTERS}}` | `## Characters` section of `runs/{doc_id}/context.md` | A & B | Written by agent during setup |
| `{{STYLE_REFERENCE}}` | Up to 6 representative PASS_THROUGH rows from skeleton | A & B | Auto-selected by `build_messages.py` |
| `{{CONVERGENCE_CONTEXT}}` | 1-3 rows after the last branch in the chunk | A (branch chunks only) | Omitted for sequential chunks |
| `{{ROWS}}` | All rows in this chunk from skeleton | A | Full chunk with surrounding context |
| `{{PRE_CONTEXT}}` | 5-6 rows before the choice block | B only | Scene setup leading into choice |
| `{{ROWS}}` | Complete choice block (all sibling branches) | B | Direction rows + branch slots together |
| `{{POST_CONTEXT}}` | 5-6 rows after convergence point | B only | Shows where branches merge |
| `{{CONVERGENCE_CONTEXT}}` | 1-3 rows immediately after choice block | B | Required — shows where branches converge |

---

## Editing a prompt for a single chunk

If a specific chunk produced bad output and you want to tweak its prompt before re-running:

1. Open the relevant `chunk_NN_messages.json` in `runs/{doc_id}/messages/`
2. Edit the `content` field of the `system` message directly
3. Re-run `call_api.py` on that chunk only
