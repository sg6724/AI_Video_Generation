# Imagine Art setup

Imagine Art is the visual generation backend for this pipeline. Use it for cinematic B-roll,
reference images, image-to-video, drone/aerial shots, title-card motion, and captions when a
finished Imagine Art video needs burned subtitles.

## MCP setup

Hosted MCP endpoint:

```bash
codex mcp add imagine-art --url https://mcp.imagine.art
```

Verify:

```bash
codex mcp get imagine-art
```

Expected shape:

```text
transport: streamable_http
url: https://mcp.imagine.art
```

If tools are not visible after adding the MCP server, restart the Codex session so the tool
registry reloads.

## Runtime flow

1. Call `select_organization` once at the start of generation.
2. Optionally call `select_folder` if the run should be organized in a folder.
3. For visual shots:
   - `generate_image` for reference stills, style frames, and title stills.
   - `generate_video` for normal text-to-video or image-to-video shots.
   - `generate_drone_video` for aerial, overhead, orbit, reveal, or flyover shots.
4. Let the returned widget poll status. Do not manually poll `fetch_status` when the widget is
   mounted.
5. Download finished assets into `shots/raw/` and record provider IDs/paths in
   `shots/manifest.json`.

## Recommended defaults for NestGen

- Main aspect ratio: `16:9`.
- Fast visual test model: `veo-3.1-fast`, `duration: "4"` or `"6"`, `resolution: "720p"`.
- Higher-quality hero visuals: `veo-3.1`, `duration: "6"` or `"8"`, `resolution: "1080p"`.
- Image references: `nano-banana-pro`, `aspect_ratio: "16:9"`, `resolution: "1K"`.

## Prompting rules

- Start every prompt with the visual bible style block.
- Use original character language, for example "young straw-hat pirate host in a red open
  jacket and blue cropped trousers" instead of naming a copyrighted character.
- Keep continuity anchors explicit: same ship, same blue holographic sea map, same NestGen
  signal color, same enterprise drone fleet.
- Keep text minimal. If exact readable title text is required, prefer a separate title-card
  shot and check the output manually.
