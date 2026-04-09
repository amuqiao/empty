# Style Rules

Authoritative reference for all generated content. Read this file in full when building the system message.

---

## Dialogue rules

- **Short, spoken sentences.** Real people don't soliloquize. If a line needs more than one breath to say aloud, split or cut it.
- **Distinct voice per character.** Study how each character speaks in the completed sample — word choice, sentence length, register, favorite phrases — and carry that forward consistently. Never let characters sound interchangeable.
- **No narration inside dialogue.** If something must be described, give it its own Narration row; do not embed scene description into a speech line.
- **Emotion tags** — pick from this list only, one per line; leave blank for Narration and Choice rows:
  - `angry`, `smile`, `laughing`, `flirty`, `neutral`, `sad`, `shocked`, `confused`, `eyesclosed`, `shy`
- Never invent new emotion tags.

---

## Narration rules

- **Present tense, active verbs.** Not "The door was opened" — "She shoves the door open."
- **One to two sentences maximum** per Narration row. Tight and cinematic — describe what the camera would show, not what a novelist would explain.
- **No 4+ consecutive Narration rows.** If you have a long action sequence, break it with a short dialogue beat. Count your Narration rows as you write.

---

## Choice branch rules

- **Preserve the choice label exactly.** The header row (`speaker = "Choice"`, `row_type = "Choice N"`, `choice_letter` has a letter) is usually already written in the skeleton — copy it verbatim.
- **Branch body: 2–3 lines.** Typically: MC's committed response → other character's reaction. Keep it brief; branches converge quickly.
- **Don't echo the label.** The MC's first branch line should pick up the thought mid-stride, not repeat the choice wording back.
- All branches must converge at a common continuation point — the script structure enforces this, do not add extra rows after the final branch.
- **Determine `speaker` for every slot.** Branch slot rows have no speaker pre-filled — choose the most dramatically appropriate speaker (MC response first, then other character's reaction, then a Narration beat if the branch needs physical description).
- **Keep branches distinct.** Each branch should have a different emotional register — don't generate near-identical lines across Choice 1/2/3. The player's choice must feel consequential.

### Branch content slot rules

When filling branch content slots (`speaker` empty, `content` empty):

- **Determine the speaker for each slot.** Typical pattern for a 2-3 slot branch:
  1. First slot: MC's committed response (`speaker` = MC's name)
  2. Second slot: Other character's reaction (`speaker` = their name)
  3. Third slot (if present): Narration beat for physical description (`speaker` = `Narration`)
- **Keep the slot count constant.** The skeleton defines exactly how many slots each branch has — fill every slot, but never add extra rows beyond what the skeleton provides.
- **Each branch must be emotionally distinct from its siblings.** If Choice 1 is defiant, Choice 2 might be sympathetic, Choice 3 might be deflecting. Different emotional register, different speaker choices where appropriate.
- **Never output extra rows beyond the slot count.** If the skeleton has 2 slots per branch, output exactly 2 rows per branch.

---

## Content (Column E) rule

| Condition | Action |
|-----------|--------|
| Col E ends with `.`, `!`, or `?` — or is a structural/technical label | **`PASS_THROUGH`** — copy exactly as-is, no edits |
| Col E is empty **or** contains a direction without terminal punctuation (e.g., "sarcastic line here", "MC sympathetic comment") | **`GENERATE`** — write new content following the direction as a tone instruction |
| Row is a Choice header, Object, or Callback row | **`STRUCTURAL`** — preserve structure exactly |
| `speaker` empty AND `content` empty AND `row_type` = branch label (e.g. `Choice 1`) | **`GENERATE` (branch slot)** — also determine `speaker` |

When a direction says "flirty response" or "sarcastic line here," treat it as a tone/attitude instruction, not literal text to include.

---

## POV switch rules

- When filling rows with "now playing from X POV" directions, set `speaker` = `Narration_Prompt`
- Vary the wording across multiple POV switches — avoid identical text
- Examples: "You are now playing from Reese's POV." / "Switching to Reese's perspective." / "Now playing as Reese."

---

## Output format

The model must return a **JSON array** — no preamble, no markdown fences, no trailing commentary:

```json
[
  {"row_index": 5, "content": "She crosses her arms.", "emotion": ""},
  {"row_index": 6, "content": "Don't look at me like that.", "emotion": "angry"},
  {"row_index": 11, "speaker": "Kristi", "content": "That's… great. Really.", "emotion": "eyesclosed"},
  {"row_index": 12, "speaker": "Narration", "content": "She digs her nails into her palms.", "emotion": ""}
]
```

- `row_index` — 0-based index matching the skeleton input
- `content` — the generated or passed-through content (string)
- `emotion` — emotion tag (string, or empty string `""`)
- `speaker` — **required when the skeleton row has no speaker (branch content slots)**. Omit it for rows that already have a speaker in the skeleton.
- Include **only** rows that were `GENERATE`; `PASS_THROUGH` and `STRUCTURAL` rows are handled by the write step automatically
- Any response that is not a valid JSON array will be rejected and retried
