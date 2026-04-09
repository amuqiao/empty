# Interactive Fiction Script Format Specification

> **Cross-reference:** For how branch slots affect the generation pipeline, see SKILL.md "Two Types of GENERATE Rows" and pipeline_guide.md "Step 2.5 — Pass 2: Generate Branch Content Slots".

## Script Structure

The script is **globally sequential**: rows execute top-to-bottom. The player experiences a linear story with embedded choice points.

**Branches are parallel**: all branches of a choice set exist simultaneously in the file, but the player experiences only one per playthrough.

**Inside a branch, content is sequential**: rows execute in order within that branch.

**Branch duration**: typically a few lines to ~20 rows.

**Branch end condition** — two cases:
1. The next parallel branch of the same choice set begins (a new `Choice N` header with a different letter appears in col_B) — the current branch ends.
2. A non-branch row appears (a `Text` row, blank-col-A row, background ID change in col_C, or other structural row not belonging to any branch) — this is the **convergence point**; all branches merge here.

**Convergence**: after the last parallel branch in a group, execution returns to the parent branch level (if nested) or the main story (if top-level).

**Sub-branches**: a branch can contain a nested choice set. Sub-branches converge before their parent branch closes. The sub-branch convergence point is still inside the parent branch. All levels resolve before reaching the top-level convergence row.

See [Nested Branch Pattern](#nested-branch-pattern) section for an annotated example.

---

## Column Layout (always 6 columns, A–F)

| Col | Index | Name | Values |
|-----|-------|------|--------|
| A | 0 | Text / Row type | `Text`, `Choice 1`, `Choice 2`, ... `Choice N`, or blank |
| B | 1 | Choice letter | `a`, `b`, `c`, ... for choice option rows; blank otherwise |
| C | 2 | Object marker | `Object`, `Callback`, `end callback`, a background asset ID (e.g. `cole_addison_house_i_d`), or blank |
| D | 3 | Narration / Speaker | `Narration`, `Choice`, `Narration_PopUp`, `Narration_Prompt`, or a character name |
| E | 4 | Content | The actual text of the line |
| F | 5 | Emotion | One of the allowed emotions, or blank |

## Row Types (Col A)

### `Text` row
A standalone beat — narration, character dialogue, or a special structural row. Col B and C may be blank.

### `Choice N` row (with letter in Col B)
A choice option the player can pick. Col D = `Choice`. Col E = the choice label text. Col F = blank.

### `Choice N` row (without letter in Col B)
A **branch content slot** — a line of dialogue or narration that plays when the player picks this branch. Col D and Col E are both **empty in the skeleton**; the model must assign a speaker and write the content. Classification: `GENERATE`.

### Blank Col A row
A continuation of the current scene — no special structure. Commonly used for flowing dialogue.

## Speaker Values (Col D)

| Value | Meaning |
|-------|---------|
| `Narration` | Scene description / action (no speaker, no emotion) |
| `Narration_PopUp` | Floating reward pop-up text (short, praising the player's choice) |
| `Narration_Prompt` | POV-switch announcement, e.g. "You are now playing from Reese's POV." |
| `Choice` | Choice option row (player-facing label) |
| Character name | A named character speaking a dialogue line |

## Object / Callback rows (Col C)

- `Object` in Col C → an interactive object menu will be inserted here. Col E = object name/description.
- `Callback` in Col C → the result of a previous object choice plays out here. Col E = the callback label.
- `end callback` → closes a callback block.
- A background asset ID (e.g. `cole_addison_house_i_d`, `ava's_kitchen_int_d`) → sets scene background for subsequent rows.

## Allowed Emotion Tags

`angry` | `smile` | `laughing` | `flirty` | `neutral` | `sad` | `shocked` | `confused` | `eyesclosed` | `shy`

Emotion is blank for `Narration`, `Choice`, and structural rows.

## Choice Branch Pattern

Each blank-body row is a **branch content slot** — speaker and content are both empty in the skeleton, and the model must fill both.

```
Skeleton (before generation):
Col A       Col B   Col D     Col E
--------    -----   ------    -----
(speaker)   (blank) Char      "here is my problem"       ← setup line
Choice 1    a       Choice    "you're a bully"           ← choice label (PASS_THROUGH)
Choice 1    (blank) (blank)   (blank)                    ← branch slot: GENERATE speaker + content
Choice 1    (blank) (blank)   (blank)                    ← branch slot: GENERATE speaker + content
Choice 2    b       Choice    "you're totally fake"      ← choice label (PASS_THROUGH)
Choice 2    (blank) (blank)   (blank)                    ← branch slot: GENERATE speaker + content
Choice 2    (blank) (blank)   (blank)                    ← branch slot: GENERATE speaker + content
Choice 3    c       Choice    "third option"             ← choice label (PASS_THROUGH)
Choice 3    (blank) (blank)   (blank)                    ← branch slot: GENERATE speaker + content
Choice 3    (blank) (blank)   (blank)                    ← branch slot: GENERATE speaker + content
(converge)  (blank) Speaker   (content)                  ← scene continues
```

**Generation context window:** When generating branch slot content in Pass 2, include the full choice block (all sibling branches) plus 5-6 rows before and 5-6 rows after the convergence point as context for the model. Annotate any rows already generated in Pass 1 with their content.

After generation — branch slots have speaker and content filled:

```
Choice 1    (blank) MC        "You think I'm a bully?"           eyesclosed
Choice 1    (blank) Kristi    "That's… great. Really."           eyesclosed
Choice 2    (blank) MC        "Fake? Look who's talking."        angry
Choice 2    (blank) Narration "She digs her nails into her palms." (blank)
Choice 3    (blank) MC        "Okay. Sure. Third option."        neutral
Choice 3    (blank) Kristi    "Right. Obviously."                confused
```

## Branch Classification

> **Two kinds of "Choice N (no letter in col B)" rows — do not confuse them:**
>
> | speaker value | content value | Meaning | Classification |
> |---------------|---------------|---------|----------------|
> | `Choice`      | text present  | Choice header (player-facing label) | **PASS_THROUGH** |
> | empty         | empty         | Branch content slot — model must assign speaker and write content | **GENERATE** (must output speaker) |

## Nested Branch Pattern

Premium choices and sub-choices nest inside a parent branch. Sub-branches converge before their parent branch closes; all parent branches converge at the next blank-col-A row.

```
Col A              Col B   Col D     Col E
-----------------  -----   ------    -----
Choice 1           a       Choice    "free option"          ← parent choice label
Choice 1           (blank) (blank)   (blank)                ← branch slot
Premium Choice 1   a       Choice    "premium sub-option A" ← sub-choice label
Premium Choice 1   (blank) (blank)   (blank)                ← sub-branch slot
Sub Choice 1       a       Choice    "sub-sub option A"     ← nested sub-choice label
Sub Choice 1       (blank) (blank)   (blank)                ← nested slot
Sub Choice 2       b       Choice    "sub-sub option B"     ← nested sub-choice label
Sub Choice 2       (blank) (blank)   (blank)                ← nested slot
                                                            ← sub-choices converge here
Premium Choice 2   b       Choice    "premium sub-option B" ← sub-choice label
Premium Choice 2   (blank) (blank)   (blank)                ← sub-branch slot
                                                            ← premium sub-choices converge
Choice 2           b       Choice    "second parent option" ← parent choice label
Choice 2           (blank) (blank)   (blank)                ← branch slot
                                                            ← all parent branches converge here (blank col A)
```

Rules:
- Sub-branches always converge before their parent branch closes.
- All parent branches converge at the first blank-col-A row after the last parent branch.
- Never split a nested block across chunks.

See [Script Structure](#script-structure) above for the conceptual explanation of why sub-branches must converge first.

## Customization Menu Pattern (avatar builder)

These rows appear when the player customizes a character's appearance. All are PASS_THROUGH — preserve exactly.

```
Col D        Col E
--------     -----
Character    "Choose his look."
Choice       "Choose his look."     ← Choice 1 through N
Choice       "Choose his look."
...
Character    "Choose his hair."
Choice       "Choose his hair."     ← Choice 1 through N
...
Narration    "His look is..."
Choice       "Great— let's go!"
Choice       "Not quite right— let's change it."
```

## Narration Rhythm Rules

- Max 3 consecutive Narration rows before a dialogue beat interrupts.
- Narration lines: 1-2 sentences, present tense, active verbs.
- Narration describing physical action or setting should be cinematic, not explanatory.

## Skeleton Placeholder Patterns (common Col E values to GENERATE from)

| Placeholder | What to write |
|-------------|--------------|
| `beats to establish chemistry and character or show vital motion` | 3-4 vivid narration/dialogue beats showing physical proximity, tension, or banter |
| `behind the scenes touching, bullying` | Brief narration + dialogue showing the dynamic without being explicit |
| `sarcastic line here` | One short sarcastic comeback in the character's voice |
| `MC sympathetic comment` | MC's brief, genuine sympathetic response |
| `flirty response` | A flirty but not explicit line |
| `wrap up line` | A short closing line for the current exchange |
| `[character]: [brief description]` | Expand into natural spoken dialogue following that direction |

## POV Switch Structure

When Col D = `Narration_Prompt`, the script switches to a different character's POV. The pattern:

```
Narration_Prompt: "You are now playing from Reese's POV."  ← preserve
background ID in Col C                                       ← new scene location
Reese: [dialogue]
...
```

## Generated Script Tab

The `Generated Script` tab in the workbook is an example of a previously filled skeleton. Its column headers are:
- Text | Choice letter | Object marker | Narration | Content | Emotion

This is the gold standard output format.
