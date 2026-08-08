# AI Video Factory — Design Spec

Date: 2026-08-08
Status: Approved for planning
Context: AI Creators Hackathon (FlytBase), Option 1 — NestGen track

## 1. Problem

Manually driving an AI video pipeline shot-by-shot (write a prompt, submit, wait,
download, repeat, then hand-edit in ffmpeg) is slow and doesn't scale past a couple of
clips. The goal is a repeatable, agent-orchestrated pipeline: give it a topic
description, it writes the script, generates every visual beat, generates narration,
assembles the final cut, and hands back `output/final.mp4` — with minimal manual
babysitting per shot.

Today's concrete use case is a NestGen '26 marketing video (the hackathon's Option 1,
chosen for its stated hiring value at FlytBase), but the pipeline itself must be
general-purpose — reusable on the next topic, not hardcoded to NestGen.

## 2. Goals

- One entry point: describe a topic in conversation, get a finished video.
- Reusable across topics — NestGen today, anything else later.
- Flexible per-beat: some beats show a recurring character, some are pure
  environment/product B-roll — same mechanism either way, no special-casing.
- Minimum cost by default: cheapest capable model per beat unless manually overridden.
- Resumable: a crashed/interrupted run can pick back up without regenerating
  already-completed beats.
- Visual consistency across the whole video (one style, one recurring character look)
  without needing per-platform "character training" features.

## 3. Non-goals

- Not a standalone CLI/binary — this runs agent-orchestrated inside a Claude Code
  session, not unattended from a plain terminal command.
- Not multi-backend — Higgsfield and HeyGen are explicitly out of scope for generation
  (cost and format-fit reasons, see §9). Imagine Art is the only generation platform.
- Not lip-synced talking-head narration — reference videos for this project use
  narrator-voiceover-over-illustrative-footage, not to-camera lip-synced dialogue, so
  the pipeline doesn't need (and doesn't use) a lipsync tool.
- Not building new ffmpeg/video-editing UI — assembly is a script, not a product.

## 4. Reference material examined

Two real reference videos from the hackathon's shared Drive folder were downloaded and
sampled (frames every 5s via ffmpeg) to ground the design in what "good" actually looks
like for this brief, rather than assuming:

- **Reference Video D** (~50s): a single continuous visual style (isometric
  paper-craft/low-poly diorama) across ~8 vignettes — oil & gas plant, mine, port, city
  emergency response, smart highway camera — cut together with a narrator voiceover,
  burned-in captions, ending on a branded NestGen'26 end card. No on-screen character.
- **Reference Video F** (~96s): opens comedic — a costumed caveman-style character
  absurdly operating a modern drone, then ancient laborers hand-building a solar farm
  ("Finished sometime around the next century") — pivots via full-screen typographic
  title cards ("And yet, much of the physical world still operates this way") into
  serious real-product B-roll (a quadruped robot), continuing into a
  transforming-industries narration line. Character present, but performing an action
  on screen, not speaking to camera — voiceover carries the narration throughout.

Neither video uses a talking-head/lip-synced format. Both use: one consistent visual
style, short generated vignettes, a continuous narrator voiceover independent of the
visuals, burned-in captions, and full-screen title cards for tonal pivots. This is the
mechanism the design below replicates.

## 5. Architecture

```
User: "make a video about <description>"
  │
  ▼
Stage 1 — Script & beats (agent, in-session)
  Write script.md: hook + narrative arc, as narration prose.
  Break into beats (6-12 for a 60-90s video). Each beat tagged with:
  visual description, tone, has_character (bool), target model tier,
  is_title_card (bool, for tonal-pivot text cards).
  │
  ▼
Stage 2 — Visual bible (agent, once per project)
  visual-bible.md: short style-consistency spec (format, palette, lighting,
  camera language) prepended to every beat's generation prompt so the video
  doesn't drift stylistically beat to beat.
  │
  ▼
Stage 3 — Character reference (agent, once per project, optional)
  Only if the script uses a recurring character.
  Imagine Art text-to-image → assets/character.png
  │
  ▼
Stage 4 — Beat generation loop (agent, per beat)
  For each non-title-card beat:
    prompt = visual-bible + beat visual_prompt
    if has_character: attach assets/character.png as reference
    submit via Imagine Art text-to-video (cheapest capable model, unless
      manifest overrides) → record job_id, status "processing"
    poll to terminal state → download → shots/raw/beat_NN.mp4
    update manifest.json (status "done" + output_path)
  Retry up to 2x on failure before flagging "failed" for manual review.
  │
  ▼
Stage 5 — Narration voiceover (agent, once per project)
  Imagine Art TTS on the full script.md narration → audio/narration.mp3
  │
  ▼
Stage 6 — Assembly (assemble.py, deterministic, local ffmpeg)
  - Normalize clips (resolution/fps/codec) if needed
  - Burn in captions per beat (from manifest caption_text)
  - Render title-card beats as full-screen typographic clips
  - Concatenate in sequence order
  - Lay narration.mp3 under the assembled cut
  - Optional background music mix
  - Append end card (branded if the topic has one, e.g. NestGen; generic sign-off
    otherwise)
  → output/final.mp4
  │
  ▼
Stage 7 — QA pass (agent + user)
  Watch the cut. Check: runtime vs. target_duration_sec, style consistency beat
  to beat, narration/caption sync. Fix a bad beat by re-running just that beat
  through Stage 4 — never regenerate the whole project for one bad shot.
```

## 6. Project structure

```
<project-name>/
├── script.md                # Stage 1 — narration prose
├── visual-bible.md           # Stage 2 — style constants
├── shotlist.json              # Stage 1/4 — the manifest (see §7)
├── assets/
│   └── character.png          # Stage 3 — optional, one reusable reference image
├── shots/
│   ├── raw/                    # Stage 4 output — beat_001.mp4, beat_002.mp4, ...
│   └── manifest.json            # Stage 4 — generation log (status/job_id/retries)
├── audio/
│   └── narration.mp3            # Stage 5 output
└── output/
    └── final.mp4                 # Stage 6 output
```

## 7. Manifest schema (`shotlist.json`)

```json
{
  "project": "string",
  "target_duration_sec": "number",
  "visual_bible_ref": "visual-bible.md",
  "character_ref": "assets/character.png | null",
  "beats": [
    {
      "id": "beat_001",
      "sequence": 1,
      "narration_line": "string | null — the narration this beat covers",
      "visual_prompt": "string — subject, action, environment (bible not repeated here)",
      "has_character": false,
      "is_title_card": false,
      "caption_text": "string | null",
      "duration_sec": 6,
      "model": "string — cheapest capable Imagine Art model by default",
      "status": "pending | queued | processing | done | failed",
      "job_id": "string | null",
      "output_path": "shots/raw/beat_001.mp4 | null",
      "retries": 0
    }
  ]
}
```

Rules:
- `sequence` determines final assembly order.
- `has_character: true` beats attach `character_ref` to the generation call; all other
  beats omit it — same code path either way, just a conditional attachment.
- `model` defaults to the cheapest model capable of the shot; upgrading a specific beat
  (e.g. the hook) to a premium model is a manual manifest edit, never automatic.
- `status`/`job_id`/`output_path`/`retries` are written by the generation loop, not by
  hand when first drafting beats — every beat starts `"status": "pending"`.

## 8. Cost policy

- Every beat defaults to the cheapest capable Imagine Art model. No auto-upgrades.
- Before any real batch run, check Imagine Art account balance/cost via the MCP —
  confirmed available via the connector's balance-inquiry tool once authenticated.
  Never fire a multi-beat batch blind.
- Per-beat model is manually overridable in `shotlist.json` if a specific shot
  (e.g. the opening hook) is worth spending more on — decided by the user, not
  automated.

## 9. Why not Higgsfield or HeyGen

- **Higgsfield**: ruled out on cost — user does not want to spend Higgsfield credits
  for this pipeline, despite it being already installed/authenticated from earlier
  setup in this session.
- **HeyGen**: initially designed around (Photo Avatar + Lipsync-style narration via
  HeyGen MCP), but dropped once the actual reference videos showed neither uses a
  lip-synced talking head. HeyGen's core strength (avatar narrating to camera) doesn't
  match the target format, and Imagine Art already covers image generation, video
  generation (including Kling/Veo/Seedance/etc.), and TTS on one account — no reason to
  split generation across two billed platforms.

## 10. Error handling

Same resumability principles as a standard batch pipeline:
- Always poll to a terminal state — never assume success from a submit call.
- Persist progress to `shots/manifest.json` after every state change, so a crashed or
  interrupted run resumes from where it left off instead of regenerating completed
  beats.
- Retry a failed beat up to 2 times with the same prompt before marking it `failed` and
  flagging it for manual review — never silently skip a beat (leaves a gap at
  assembly).
- Assembly (`assemble.py`) checks that every beat in the manifest is `status: done`
  before running; if any beat is `failed`, it stops and reports which ones, rather than
  assembling a video with a missing shot.

## 11. Open risks / unverified assumptions

These need to be confirmed once Imagine Art MCP authentication is completed
(`claude mcp login imagine-art`, still outstanding as of this spec) and the first real
tool calls are made — flagged here rather than assumed silently:

- **Exact MCP tool names/schemas** for Imagine Art's text-to-image, text-to-video, and
  TTS tools are not yet confirmed — the web-search-derived capability list (§ prior
  conversation) is a product description, not a verified API contract. Must inspect the
  live tool list before wiring the generation loop.
- **Character consistency via reference-image-conditioned text-to-video** is assumed
  strong (same mechanism family as other image-to-video reference tools) but not
  empirically verified for Imagine Art specifically — unlike the earlier
  same-static-image Lipsync approach, text-to-video generates new motion each call, so
  minor drift is possible. First character beat should be visually checked against
  `assets/character.png` before running the rest of the batch.
- **Per-model cost/pricing** is unknown until the account is authenticated and a
  balance/cost check is run — the "cheapest capable model" default needs a real model
  list with pricing to be meaningful, not just a guess.
- **ffmpeg** is now installed and confirmed working locally (`winget install
  Gyan.FFmpeg`), so Stage 6 is unblocked.

## 12. Testing / QA approach

- Stage 4: after the first character beat (if any) generates, visually diff it against
  `assets/character.png` before continuing the batch — catch consistency drift early
  rather than after spending on 10+ beats.
- Stage 6: `assemble.py` run against a manifest with all beats `done` should produce a
  runtime within a few seconds of `target_duration_sec`; if it's off, check per-beat
  `duration_sec` vs. actual rendered clip length in the manifest before re-cutting.
- Stage 7: human QA pass is mandatory before calling the video final — watch it,
  don't just trust that assembly succeeded.
