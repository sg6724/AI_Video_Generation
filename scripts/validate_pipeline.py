#!/usr/bin/env python3
"""
Validate a HeyGen + Imagine Art shotlist before any paid generation.

Usage:
    python scripts/validate_pipeline.py --project-dir projects/nestgen-heygen-imagine
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ALLOWED_BACKENDS = {"heygen", "imagine-art"}
ALLOWED_TRANSITIONS = {"cut", "crossfade"}
IMAGINE_ART_MODES = {"text_to_image", "image_to_image", "text_to_video", "image_to_video", "drone_video"}
HEYGEN_MODES = {"avatar_video"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def is_placeholder(value: Any) -> bool:
    return isinstance(value, str) and value.strip().upper() in {"AVATAR_ID", "VOICE_ID", "TODO", "TBD"}


def require_string(errors: list[str], shot: dict[str, Any], field: str) -> None:
    value = shot.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{shot.get('id', '<unknown>')}: missing non-empty `{field}`")


def validate(project_dir: Path, allow_placeholders: bool) -> list[str]:
    errors: list[str] = []
    shotlist_path = project_dir / "shotlist.json"

    if not shotlist_path.exists():
        return [f"missing shotlist: {shotlist_path}"]

    try:
        data = load_json(shotlist_path)
    except json.JSONDecodeError as exc:
        return [f"invalid JSON in {shotlist_path}: {exc}"]

    shots = data.get("shots")
    if not isinstance(shots, list) or not shots:
        return ["`shots` must be a non-empty array"]

    visual_bible_ref = data.get("visual_bible_ref")
    if isinstance(visual_bible_ref, str) and visual_bible_ref:
        if not (project_dir / visual_bible_ref).exists():
            errors.append(f"missing visual bible: {project_dir / visual_bible_ref}")
    else:
        errors.append("missing `visual_bible_ref`")

    seen_ids: set[str] = set()
    sequences: list[int] = []

    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            errors.append(f"shot #{index}: must be an object")
            continue

        sid = shot.get("id")
        if not isinstance(sid, str) or not sid.strip():
            errors.append(f"shot #{index}: missing non-empty `id`")
            sid = f"shot #{index}"
        elif sid in seen_ids:
            errors.append(f"{sid}: duplicate shot id")
        else:
            seen_ids.add(sid)

        sequence = shot.get("sequence")
        if not isinstance(sequence, int):
            errors.append(f"{sid}: `sequence` must be an integer")
        else:
            sequences.append(sequence)

        backend = shot.get("backend")
        if backend not in ALLOWED_BACKENDS:
            errors.append(f"{sid}: backend must be one of {sorted(ALLOWED_BACKENDS)}, got {backend!r}")

        duration = shot.get("duration_sec")
        if not isinstance(duration, (int, float)) or duration <= 0:
            errors.append(f"{sid}: `duration_sec` must be a positive number")

        if shot.get("transition_in") not in ALLOWED_TRANSITIONS:
            errors.append(f"{sid}: `transition_in` must be one of {sorted(ALLOWED_TRANSITIONS)}")

        require_string(errors, shot, "visual_prompt")
        require_string(errors, shot, "camera")

        if backend == "imagine-art":
            if shot.get("mode") not in IMAGINE_ART_MODES:
                errors.append(f"{sid}: Imagine Art mode must be one of {sorted(IMAGINE_ART_MODES)}")
            aspect_ratio = shot.get("aspect_ratio")
            if aspect_ratio != "16:9":
                errors.append(f"{sid}: expected `aspect_ratio` to be `16:9` for the main video")

        if backend == "heygen":
            if shot.get("mode") not in HEYGEN_MODES:
                errors.append(f"{sid}: HeyGen mode must be `avatar_video`")
            narration = shot.get("narration_line")
            if not isinstance(narration, str) or not narration.strip():
                errors.append(f"{sid}: HeyGen shots require spoken `narration_line`")
            for field in ("model", "voice_id"):
                value = shot.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{sid}: HeyGen REST batches require `{field}`")
                elif is_placeholder(value) and not allow_placeholders:
                    errors.append(f"{sid}: replace placeholder `{field}` before a real run")

    if sorted(sequences) != list(range(1, len(shots) + 1)):
        errors.append("shot `sequence` values must be contiguous starting at 1")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()

    errors = validate(args.project_dir, args.allow_placeholders)
    if errors:
        for error in errors:
            print(f"[error] {error}", file=sys.stderr)
        return 1

    print(f"[ok] {args.project_dir / 'shotlist.json'} is valid for the HeyGen + Imagine Art pipeline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
