---
name: ai-video-pipeline
description: Automates end-to-end AI cinematic video production for Codex using HeyGen for presenter/narration shots, Imagine Art for generated images/videos, and local ffmpeg for assembly. Use when the user asks to generate an AI video, build a hackathon/demo/pitch video, automate shot-by-shot AI video production, or run the NestGen/FlytBase video factory.
---

# AI Video Pipeline

This pipeline turns a topic into a finished short video by directing one shot at a time,
not by asking a model for one long clip. The source of truth is `shotlist.json`; the
resumability log is `shots/manifest.json`.

## Backend Policy

Use only HeyGen and Imagine Art for this project:

- HeyGen: presenter/avatar segments, spoken delivery, lip-synced narration, host cutaways.
- Imagine Art: cinematic B-roll, image generation, image-to-video, drone/aerial shots,
  title-card motion, and visual continuity passes.
- Local ffmpeg/ffprobe: assembly, normalization, narration/music mix, captions, QA checks.

Do not use Kling, Higgsfield, Sora, Runway, Pika, or any other generation backend for the
active pipeline unless the user explicitly changes this backend policy.

## Required Runtime Rules

- Treat every real generation as paid. Run preflight validation before submitting jobs.
- Use the live MCP tools for Imagine Art generation; select an organization before the
  first Imagine Art generation and reuse it for the whole chat.
- Use HeyGen MCP when its tools are exposed for avatar/voice selection and test presenter
  shots. Use `scripts/generate_shots_heygen.py` only when `HEYGEN_API_KEY` is available for
  unattended REST batches.
- Never paste or store API keys in project files, manifests, or prompts.
- Keep character designs original for public hackathon output. Do not reference copyrighted
  character names or franchise-specific designs in generation prompts.
- On paid generation failure, stop and inspect the failed shot before changing prompts,
  parameters, or backends.

## Project Structure

```text
<project-name>/
  script.md
  visual-bible.md
  shotlist.json
  assets/
    characters/
    locations/
  shots/
    raw/
    manifest.json
  audio/
    narration.mp3
    music.mp3
  output/
    final.mp4
```

## Pipeline

1. Intake: confirm topic, target length, audience, format, and style.
2. Script: write narration with a strong hook and clear arc.
3. Shot list: break narration into 3-8 second shots in `shotlist.json`.
4. Visual bible: define style constants prepended to every Imagine Art prompt.
5. References: generate/approve original character and location stills before animation.
6. Generation: use Imagine Art MCP for visual shots and HeyGen MCP/REST for presenter shots.
7. Narration: create or export `audio/narration.mp3`.
8. Assembly: use local ffmpeg per `references/assembly-ffmpeg.md`.
9. QA: watch the cut, fix individual failed/weak shots only.

## References

- `references/imagine-art-setup.md`
- `references/heygen-setup.md`
- `references/shot-list-schema.md`
- `references/assembly-ffmpeg.md`
- `scripts/generate_shots_heygen.py`
- `scripts/validate_pipeline.py`
- `assets/shotlist.example.json`
- `assets/visual_bible.example.md`
