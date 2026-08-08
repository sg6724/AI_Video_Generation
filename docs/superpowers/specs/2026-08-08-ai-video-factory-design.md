# AI Video Factory Design - HeyGen + Imagine Art

Date: 2026-08-08
Status: Active

## Decision

The active NestGen video pipeline uses only:

- HeyGen for presenter/avatar/lip-sync shots.
- Imagine Art for image generation, cinematic B-roll, image-to-video, drone/aerial shots,
  title cards, and optional captions.
- Local ffmpeg/ffprobe for assembly and QA.

Kling, Higgsfield, Sora, Runway, Pika, and other generation backends are out of scope for
this pipeline unless the user explicitly changes the backend policy later.

## Goal

Build a repeatable shot-by-shot workflow for a hiring-focused NestGen '26 video. The output
should show understanding of FlytBase's market: physical AI, autonomous drone operations,
BVLOS, scaling from pilot to production, ROI, and the operational playbooks that NestGen
surfaces.

## Content Positioning

The video should not be "drones are cool." It should argue:

NestGen '26 is valuable because operators from public safety, mining, ports, railways,
utilities, oil and gas, security, solar, and data centers share how real physical-AI programs
move from pilots to approved, repeatable production systems.

Use these proof points from the context file:

- SQM mining leak detection compressed from days to under 90 minutes.
- Solar inspections scaled from 150 MW to 1 GW.
- Security costs cut by 60 percent.
- Port surveillance response stretched from hundreds of meters to kilometers.
- Public safety drones can arrive before ground responders.

## Creative Direction

The chosen theme is an original pirate-style host, not a copied franchise character. The
visual world is a pirate command ship upgraded into a physical-AI operations vessel:

- weathered deck and brass instruments,
- blue holographic route maps,
- drone docks hidden in the ship,
- industrial islands representing mines, ports, solar farms, railways, utilities, and
  public safety,
- consistent cyan "NestGen signal" visual language.

Prompts must not use copyrighted character names, franchise logos, or exact protected
character descriptions. Use "original straw-hat pirate host" style language instead.

## Pipeline Stages

1. Script: write narration in `script.md`.
2. Visual bible: define reusable visual constants in `visual-bible.md`.
3. Shot list: store every beat in `shotlist.json`.
4. Preflight: run `python scripts/validate_pipeline.py --project-dir <project>`.
5. References: create/approve original character and location stills in Imagine Art.
6. Visual shots: submit Imagine Art text-to-video, image-to-video, and drone_video shots.
7. Presenter shots: submit HeyGen avatar_video shots after selecting avatar and voice.
8. Download: save completed clips to `shots/raw/` and update `shots/manifest.json`.
9. Assembly: normalize/concat/mix with ffmpeg and verify runtime with ffprobe.
10. QA: fix weak shots individually, never regenerate the whole video blindly.

## Data Contract

The current schema is documented in `references/shot-list-schema.md`.

Required backends:

```json
"backend": "heygen | imagine-art"
```

Required project files:

```text
script.md
visual-bible.md
shotlist.json
shots/manifest.json
```

Do not store provider secrets, bearer tokens, internal org IDs, or folder IDs in project
files.

## Runtime Setup

MCP setup:

```bash
codex mcp add imagine-art --url https://mcp.imagine.art
codex mcp add heygen --url https://mcp.heygen.com/mcp/v1/
codex mcp login heygen
```

Current verified local dependencies:

- HeyGen MCP configured with URL transport and OAuth completed.
- Imagine Art MCP configured with URL transport and tools visible.
- ffmpeg 9.0 and ffprobe 9.0 installed through Winget and added to the user PATH.

Current session limitation:

HeyGen OAuth succeeded, but HeyGen tools may require a Codex session restart before they
appear in the live tool registry. Imagine Art tools are already visible in this session.

## First Test Standard

A valid first test is not a full expensive batch. It is:

1. Run the validator on `projects/nestgen-heygen-imagine`.
2. Confirm Imagine Art organization selection works.
3. Generate one 4-6 second Imagine Art visual shot.
4. After restart exposes HeyGen tools, generate one short HeyGen presenter shot.
5. Download both clips to `shots/raw/`.
6. Assemble those two clips locally with ffmpeg and check duration with ffprobe.

Only after that should the full shot list be submitted.
