# HeyGen setup

HeyGen is the presenter backend for this pipeline: talking-to-camera host shots, avatar
cutaways, voice/lip-sync segments, and narration-facing clips. Imagine Art remains the visual
B-roll backend.

## MCP setup

Hosted MCP endpoint:

```bash
codex mcp add heygen --url https://mcp.heygen.com/mcp/v1/
```

Authenticate:

```bash
codex mcp login heygen
```

Verify:

```bash
codex mcp get heygen
```

Expected shape:

```text
transport: streamable_http
url: https://mcp.heygen.com/mcp/v1/
```

If login succeeds but HeyGen tools are not visible in the current Codex tool registry, restart
the Codex session. MCP tool schemas are loaded at session start.

## MCP usage

Use HeyGen MCP for interactive setup:

- Check the authenticated account.
- List/select avatars.
- List/select voices.
- Create one short test presenter clip.
- Retrieve the finished video URL and save it under `shots/raw/`.

Tool names and schemas can change, so inspect the live MCP tool list before calling them.

## REST API for unattended batches

The bundled script `scripts/generate_shots_heygen.py` uses the REST API directly so it can run
without an interactive MCP session.

Set an API key only in the shell environment:

```powershell
$env:HEYGEN_API_KEY="your-key"
```

Run a dry run first:

```bash
python scripts/generate_shots_heygen.py --project-dir ./my-video-project --dry-run
```

Run the real batch:

```bash
python scripts/generate_shots_heygen.py --project-dir ./my-video-project
```

## Required shot fields

For every `"backend": "heygen"` shot in `shotlist.json`:

- `mode`: `avatar_video`
- `model`: HeyGen `avatar_id` for REST batches
- `voice_id`: HeyGen voice ID for REST batches
- `narration_line`: spoken text for that shot
- optional `background_color`: hex color, defaults to `#000000`
- optional `width` / `height`: defaults to `1280` x `720`

Example:

```json
{
  "id": "shot_005",
  "sequence": 5,
  "narration_line": "That is why NestGen '26 matters.",
  "visual_prompt": "Presenter delivering a confident host line to camera",
  "camera": "static medium close-up, 50mm",
  "duration_sec": 5,
  "backend": "heygen",
  "mode": "avatar_video",
  "model": "AVATAR_ID",
  "voice_id": "VOICE_ID",
  "background_color": "#071013",
  "transition_in": "crossfade",
  "status": "pending",
  "job_id": null,
  "output_path": null,
  "retries": 0
}
```

## Notes

- HeyGen generated video URLs can expire; download them immediately into `shots/raw/`.
- Check account credits before a large batch.
- Reuse the same avatar and voice across presenter shots for continuity.
- Do not store API keys in repo files.
