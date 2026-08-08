# HeyGen + Imagine Art Pipeline Plan

Date: 2026-08-08
Status: Active replacement for the old backend-flexible plan

## Scope

Use only HeyGen and Imagine Art for generation. Local ffmpeg/ffprobe handles assembly.

## Done

- HeyGen MCP corrected from broken stdio URL command to URL transport.
- HeyGen OAuth completed with `codex mcp login heygen`.
- Imagine Art MCP verified as URL transport and its tools are visible in the current session.
- ffmpeg and ffprobe installed through Winget and added to the user PATH.
- Active `SKILL.md`, `SKILLS.md`, and `references/shot-list-schema.md` rewritten for
  HeyGen + Imagine Art only.
- Added `references/imagine-art-setup.md`.
- Updated `references/heygen-setup.md`.
- Added `scripts/validate_pipeline.py`.
- Added `projects/nestgen-heygen-imagine` as the canonical working project.

## Remaining Before Paid Batch

1. Restart Codex if HeyGen tools still do not appear in tool search after OAuth.
2. Select an Imagine Art organization before the first real Imagine Art generation.
3. Select or create the HeyGen avatar/voice to replace `AVATAR_ID` and `VOICE_ID` in the
   working shot list if using REST batch generation.
4. Generate one Imagine Art test clip and one HeyGen test presenter clip.
5. Assemble the two clips with ffmpeg and verify duration with ffprobe.
6. Run the full shot list only after the two-clip test passes.

## Validation Command

```bash
python scripts/validate_pipeline.py --project-dir projects/nestgen-heygen-imagine --allow-placeholders
```

For a real REST batch, remove `--allow-placeholders` after replacing HeyGen avatar and voice
IDs:

```bash
python scripts/validate_pipeline.py --project-dir projects/nestgen-heygen-imagine
```
