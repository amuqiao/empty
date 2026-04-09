# Skills Index

## interactive-fiction-writer

**Location:** `skills/interactive-fiction-writer/`

**Description:** Fills in skeleton scripts for interactive fiction / visual novel games, producing a fully-written .xlsx file in the exact row-by-row format used by the game engine.

**Triggers:**
- "fill the skeleton"
- "write the script from the skeleton"
- "complete the script"
- "generate script from outline"
- When an xlsx with a "skeleton" tab and style reference is provided

**Capabilities:**
- Parses skeleton xlsx files with scene structure and branching choices
- Two-pass generation: direction rows first, then branch content slots
- Handles scripts from 200 to 1000+ lines via chunked generation
- Maintains continuity tracking across chunks
- Outputs production-ready dialogue matching game engine format
