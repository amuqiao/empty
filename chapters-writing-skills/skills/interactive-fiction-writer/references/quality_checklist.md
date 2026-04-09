# Quality Checklist

Review before delivering output:

## GENERATE row validation
- [ ] All direction rows (speaker present in skeleton) have content filled with generated text
- [ ] All branch content slots have BOTH speaker and content filled
- [ ] Branch slot count per choice block matches skeleton exactly — no added or missing rows
- [ ] No orphaned branch slots outside choice blocks (every branch slot belongs to a Choice N group)

## Content quality
- [ ] Emotion tags only from the allowed list; blank on Narration/Choice rows
- [ ] No 4+ consecutive Narration rows
- [ ] No repeated lines anywhere in the script
- [ ] Choice branch structure intact: all slots filled, branches distinct (different emotional register per branch), no branch accidentally contradicts the convergence state
- [ ] POV switch lines (Narration_Prompt) use varied wording — no identical duplicates
- [ ] NSFW/explicit rows written (not skipped) unless user specified otherwise upfront

## Structural integrity
- [ ] All PASS_THROUGH content is bit-for-bit identical to the skeleton
- [ ] Column order preserved: A (Text), B (Choice letter), C (Object marker), D (Narration), E (Content), F (Emotion)
- [ ] Output saved as new file, source xlsx untouched

## Validation step
- [ ] Run `write_skeleton.py --dry-run` to check for warnings before final write
- [ ] Compare total GENERATE row count from skeleton against accumulated.json entry count — they should match
