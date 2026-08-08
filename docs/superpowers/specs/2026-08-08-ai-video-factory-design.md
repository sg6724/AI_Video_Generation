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
- **Backend-flexible**: the pipeline is not locked to one generation platform. Each beat
  in the manifest is tagged with the backend that renders it
  (`"backend": "heygen" | "higgsfield" | "imagine-art"`), so a project can mix backends
  by strength (e.g. HeyGen for a presenter segment, Higgsfield for cinematic B-roll) or
  use only whichever backend(s) are actually connected and affordable that day.
- Flexible per-beat: some beats show a recurring character, some are pure
  environment/product B-roll — same mechanism either way, no special-casing.
- Minimum cost by default: cheapest capable model/backend per beat unless manually
  overridden.
- Resumable: a crashed/interrupted run can pick back up without regenerating
  already-completed beats.
- Visual consistency across the whole video (one style, one recurring character look)
  achieved via a shared visual bible and a reusable character reference image, not a
  platform-specific "character training" feature.

## 3. Non-goals

- Not a standalone CLI/binary — this runs agent-orchestrated inside a Claude Code
  session (MCP tool calls + a deterministic local assembly script), not unattended from
  a plain terminal command.
- Not locked to a single backend — see Goals. Kling and OpenAI Sora were evaluated and
  dropped: Kling has no working MCP/CLI integration available in this environment
  (verified: the `kling.ai/mcp` endpoint exposes zero tools despite showing
  "connected"), and Sora was never connected or tested (no `OPENAI_API_KEY`, no tool
  calls made). Neither is included in this implementation; the architecture doesn't
  preclude adding a fourth backend adapter later if one becomes genuinely available.
- Not lip-synced talking-head narration by default — the two real reference videos
  examined (see §4) use narrator-voiceover-over-illustrative-footage, not to-camera
  lip-synced dialogue. HeyGen's avatar/presenter capability remains available as one
  backend option for a beat that specifically wants a presenter, but it's not the
  pipeline's default narration mechanism.
- Not building new ffmpeg/video-editing UI — assembly is a script, not a product.
- Character/reference assets must be original — not a copyrighted third-party character
  design (e.g. an existing film/anime character, reskinned or renamed) and not a real
  person's likeness. This is a hard constraint on what the pipeline will generate or
  assemble, not a style preference.

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
mechanism the design below replicates, backend-agnostically.

## 5. Backends

| Backend | Status this session | Best for | Notes |
|---|---|---|---|
| **Higgsfield** | CLI installed + authenticated (`higgsfield auth status` OK) | Cinematic B-roll, many models (Kling 3, Veo 3.1, Seedance 2.0, Soul) | Real CLI surface verified: `higgsfield generate create <model> --prompt "..." [--image-references <path>] [--wait]`, `higgsfield generate get <job_id>`. User flagged cost concerns — use as an opt-in backend per beat, not the default. |
| **HeyGen** | MCP connected | Presenter/avatar narrating a beat, digital twin/photo avatar | Full `mcp__heygen__*` tool set available (create_video_agent, create_video_from_avatar, create_video_from_image, list_video_agent_styles, get_video_agent_session, etc.) |
| **Imagine Art** | MCP connected, org selected | Multi-model image/video (Kling 3.0, Veo 3.1, Seedance, etc. per their catalog), captions, music | `generate_image` is currently blocked by a real plan-gating bug on Imagine Art's side (every model, including the account's nominal free default, returns a paid-plan-required error). `generate_video` has not yet been tested and may not be affected by the same bug — verify before relying on it. Requires `org_id` (fetched via `select_organization`) on every call. |
| Kling (direct) | Not usable | — | `kling.ai/mcp` connects but exposes zero tools. No official hosted MCP found; only unverified third-party self-hosted wrappers exist. Not implemented. |
| OpenAI Sora | Not connected | — | No `OPENAI_API_KEY` configured, no tool calls attempted this session. Not implemented; could be added as a fourth adapter later following the same interface if the user sets up real access. |

## 6. Architecture

```
User: "make a video about <description>"
  │
  ▼
Stage 1 — Script & beats (agent, in-session)
  Write script.md: hook + narrative arc, as narration prose.
  Break into beats (6-12 for a 60-90s video). Each beat tagged with:
  visual description, tone, has_character (bool), backend, model,
  is_title_card (bool, for tonal-pivot text cards).
  │
  ▼
Stage 2 — Visual bible (agent, once per project)
  visual-bible.md: short style-consistency spec (format, palette, lighting,
  camera language) prepended to every beat's generation prompt so the video
  doesn't drift stylistically beat to beat, regardless of which backend
  renders a given beat.
  │
  ▼
Stage 3 — Character reference (agent, once per project, optional)
  Only if the script uses a recurring character. Must be an original design
  (see §3). Generated once (via whichever backend's image tool is actually
  working) -> assets/characters/<name>.png, reused across every beat that
  needs it regardless of which backend renders that beat.
  │
  ▼
Stage 4 — Beat generation loop (agent + backend adapters, per beat)
  For each non-title-card beat:
    prompt = visual-bible + beat visual_prompt
    if has_character: attach character reference image (backend-appropriate form)
    dispatch to the beat's assigned backend adapter (heygen | higgsfield | imagine-art)
    adapter submits -> records job_id, status "processing"
    poll to terminal state → download → shots/raw/beat_NN.mp4
    update manifest.json (status "done" + output_path)
  On failure: retry up to 2x same prompt, then mark "failed" and stop for that beat
  — never silently skip a beat (leaves a gap at assembly).
  │
  ▼
Stage 5 — Narration voiceover (agent, once per project)
  TTS on the full script.md narration, via whichever connected backend offers
  it (HeyGen create_speech, Imagine Art TTS if available) -> audio/narration.mp3
  │
  ▼
Stage 6 — Assembly (assemble.py, deterministic, local ffmpeg)
  - Normalize clips (resolution/fps/codec) — different backends may return
    different resolutions/frame rates, so this step is not optional here
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
  to beat (this matters more with multiple backends in play), narration/caption
  sync. Fix a bad beat by re-running just that beat through Stage 4 — never
  regenerate the whole project for one bad shot.
```

## 7. Project structure

```
<project-name>/
├── script.md                # Stage 1 — narration prose
├── visual-bible.md           # Stage 2 — style constants
├── shotlist.json              # Stage 1/4 — the manifest (see §8)
├── assets/
│   └── characters/<name>.png  # Stage 3 — optional, one reusable reference image
├── shots/
│   ├── raw/                    # Stage 4 output — beat_001.mp4, beat_002.mp4, ...
│   └── manifest.json            # Stage 4 — generation log (status/job_id/retries)
├── audio/
│   └── narration.mp3            # Stage 5 output
└── output/
    └── final.mp4                 # Stage 6 output
```

## 8. Manifest schema (`shotlist.json`)

```json
{
  "project": "string",
  "target_duration_sec": "number",
  "visual_bible_ref": "visual-bible.md",
  "character_ref": "assets/characters/<name>.png | null",
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
      "backend": "heygen | higgsfield | imagine-art",
      "model": "string — explicit model/avatar id for the chosen backend",
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
- `has_character: true` beats attach `character_ref` to the generation call in
  whatever form the beat's `backend` expects (reference image param); all other beats
  omit it — same manifest shape either way, the adapter handles the backend-specific
  mechanics.
- `backend` + `model` together fully determine which adapter and which
  model/avatar id are used — set when the beat is drafted, based on what's actually
  connected and working that day (see §5 status table) and cost.
- `model` defaults to the cheapest capable option for the chosen backend; upgrading a
  specific beat is a manual manifest edit, never automatic.
- `status`/`job_id`/`output_path`/`retries` are written by the generation loop, not by
  hand when first drafting beats — every beat starts `"status": "pending"`.

## 9. Cost policy

- Every beat defaults to the cheapest capable model on its assigned backend. No
  auto-upgrades.
- Before any real batch run: check Higgsfield credits (`higgsfield account` /
  dashboard) and/or Imagine Art balance (`get_balance` via MCP) for whichever
  backend(s) the batch actually uses. Never fire a multi-beat batch blind.
- Per-beat model is manually overridable in `shotlist.json` if a specific shot (e.g.
  the opening hook) is worth spending more on — decided by the user, not automated.
- Do not silently resubmit paid generations after failure. Mark the beat `failed`, stop
  the batch, review the error, then resume after the user approves any retry or
  parameter change.

## 10. Error handling

- Always poll to a terminal state — never assume success from a submit call.
- Persist progress to `shots/manifest.json` after every state change, so a crashed or
  interrupted run resumes from where it left off instead of regenerating completed
  beats.
- Retry a failed beat up to 2 times with the same prompt before marking it `failed` and
  stopping for manual review — never silently skip a beat.
- Assembly (`assemble.py`) checks that every beat in the manifest is `status: done`
  before running; if any beat is `failed`, it stops and reports which ones, rather than
  assembling a video with a missing shot.

## 11. Open risks / unverified assumptions

- **Imagine Art `generate_video`** has not been tested — unknown whether it's affected
  by the same plan-gating bug as `generate_image`. Verify with one test call before
  relying on it for real beats.
- **Higgsfield cost** — user is cost-sensitive about this backend specifically; use only
  when explicitly worth it for a given beat, check credits first.
- **Character consistency across backends** — a character rendered via Higgsfield's
  image-reference conditioning and one rendered via HeyGen's photo avatar will not
  necessarily look identical. If a project uses the character on multiple backends,
  visually compare the first beat from each backend against the reference image before
  continuing the batch.
- **ffmpeg** is installed and confirmed working locally (`winget install
  Gyan.FFmpeg`), so Stage 6 is unblocked.
- **Any previously-exposed API keys must be rotated** before being used in this
  pipeline — never paste a key into a chat session; set it via `setx` in a terminal.

## 12. Testing / QA approach

- Stage 4: after the first character beat generates (on any backend), visually compare
  it against the character reference image before continuing the batch — catch
  consistency drift early rather than after spending on 10+ beats.
- Stage 6: `assemble.py` run against a manifest with all beats `done` should produce a
  runtime within a few seconds of `target_duration_sec`; if it's off, check per-beat
  `duration_sec` vs. actual rendered clip length in the manifest before re-cutting.
- Stage 7: human QA pass is mandatory before calling the video final — watch it, don't
  just trust that assembly succeeded.
