# Shot list schema (`shotlist.json`)

`shotlist.json` is the source of truth for HeyGen + Imagine Art generation and ffmpeg
assembly. The validator sorts by `sequence`, checks that only allowed backends are used,
and verifies each shot has enough metadata to run a clean first test.

## Schema

```json
{
  "project": "short-project-name",
  "target_duration_sec": 60,
  "visual_bible_ref": "visual-bible.md",
  "shots": [
    {
      "id": "shot_001",
      "sequence": 1,
      "narration_line": "Exact narration covered by this shot, or null for silent B-roll.",
      "visual_prompt": "Subject, action, environment, and continuity constraints.",
      "camera": "slow dolly-in, 50mm, shallow depth of field",
      "duration_sec": 5,
      "backend": "imagine-art",
      "mode": "text_to_video",
      "model": "veo-3.1-fast",
      "reference_image": null,
      "aspect_ratio": "16:9",
      "resolution": "720p",
      "transition_in": "cut",
      "status": "pending",
      "job_id": null,
      "output_path": null,
      "retries": 0
    }
  ]
}
```

## Required fields

- `id`: Stable filename base. Use zero-padded IDs such as `shot_001`.
- `sequence`: Final assembly order. Keep it contiguous.
- `visual_prompt`: Shot-specific prompt only.
- `camera`: Camera direction appended to the full prompt.
- `duration_sec`: Planned clip length. Keep generated clips short, usually 3-8 seconds.
- `backend`: Must be `imagine-art` or `heygen`.
- `mode`: Generation mode for the backend.
- `transition_in`: `cut` or `crossfade`.

## Imagine Art shot fields

Use `"backend": "imagine-art"` for generated visuals.

- `mode`: `text_to_image`, `image_to_image`, `text_to_video`, `image_to_video`, or `drone_video`.
- `model`: Optional but recommended. Use a model supported by the live Imagine Art MCP tool.
- `reference_image`: Optional local path, attached image, or URL for image/reference workflows.
- `aspect_ratio`: Use `16:9` for the main hackathon video.
- `resolution`: Optional. Use only values supported by the selected model.

## HeyGen shot fields

Use `"backend": "heygen"` for presenter/avatar shots.

- `mode`: `avatar_video` for lip-synced presenter shots.
- `model`: HeyGen `avatar_id` when using the REST batch script.
- `voice_id`: HeyGen voice ID when using the REST batch script.
- `narration_line`: Required spoken text.
- `background_color`: Optional hex color, defaults to `#000000`.
- `width` / `height`: Optional, defaults to `1280` x `720`.

When using HeyGen MCP interactively, select the avatar and voice through live tools instead
of hard-coding IDs until the final batch run is ready.

## Script-written fields

Start these as empty/default values. The generator scripts or agent-driven MCP run update them:

- `status`: `pending`, `queued`, `processing`, `done`, `failed`, or `dry_run`.
- `job_id`: Provider job ID.
- `output_path`: Downloaded clip path, usually `shots/raw/shot_001.mp4`.
- `retries`: Number of failed attempts.

## Rules

- Sort final assembly by `sequence`, not filename glob order.
- Keep one distinct visual beat per shot.
- Keep style constants in `visual-bible.md`, not every `visual_prompt`.
- Use the same approved reference image every time a character or location recurs.
- Run `python scripts/validate_pipeline.py --project-dir <project>` before generation.
- Do not include API keys, bearer tokens, internal org IDs, or folder IDs in `shotlist.json`.

See `assets/shotlist.example.json` and `assets/visual_bible.example.md` for a complete small
example.
