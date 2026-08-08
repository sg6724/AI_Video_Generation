#!/usr/bin/env python3
"""
Batch shot generator for HeyGen - Stage 5 of the ai-video-pipeline skill.

Reads shotlist.json, submits every shot tagged "backend": "heygen" to the HeyGen REST API,
polls until each finishes, downloads the result, and updates shots/manifest.json so the run
is resumable.

Usage:
    $env:HEYGEN_API_KEY="your-key"  # PowerShell
    python scripts/generate_shots_heygen.py --project-dir ./my-video-project

Validation without spending credits:
    python scripts/generate_shots_heygen.py --project-dir ./my-video-project --dry-run
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API_BASE = "https://api.heygen.com"
POLL_INTERVAL_SEC = 10
POLL_TIMEOUT_SEC = 20 * 60
MAX_RETRIES = 2


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def request_json(method: str, url: str, api_key: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HeyGen API {exc.code}: {detail}") from exc


def submit_shot(shot: dict[str, Any], api_key: str) -> str:
    voice_id = shot.get("voice_id")
    if not voice_id:
        raise ValueError(f"{shot['id']} is a HeyGen shot but has no voice_id")

    narration = shot.get("narration_line") or ""
    if not narration:
        raise ValueError(f"{shot['id']} is a HeyGen shot but has no narration_line")

    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": shot["model"],
                    "avatar_style": shot.get("avatar_style", "normal"),
                },
                "voice": {
                    "type": "text",
                    "input_text": narration,
                    "voice_id": voice_id,
                },
                "background": {
                    "type": "color",
                    "value": shot.get("background_color", "#000000"),
                },
            }
        ],
        "dimension": {
            "width": int(shot.get("width", 1280)),
            "height": int(shot.get("height", 720)),
        },
    }

    data = request_json("POST", f"{API_BASE}/v2/video/generate", api_key, payload)
    video_id = data.get("data", {}).get("video_id") or data.get("video_id")
    if not video_id:
        raise RuntimeError(f"No video_id in HeyGen response: {data}")
    return video_id


def poll_shot(video_id: str, api_key: str) -> dict[str, Any]:
    deadline = time.time() + POLL_TIMEOUT_SEC
    while time.time() < deadline:
        data = request_json("GET", f"{API_BASE}/v2/videos/{video_id}", api_key)
        status_payload = data.get("data", data)
        status = status_payload.get("status")
        if status in {"completed", "failed"}:
            return status_payload
        time.sleep(POLL_INTERVAL_SEC)
    raise TimeoutError(f"video_id {video_id} did not finish within {POLL_TIMEOUT_SEC}s")


def download(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, out_path)


def run(project_dir: Path, dry_run: bool) -> None:
    api_key = os.environ.get("HEYGEN_API_KEY")
    if not api_key and not dry_run:
        sys.exit("Set HEYGEN_API_KEY before running, or pass --dry-run.")

    shotlist_path = project_dir / "shotlist.json"
    manifest_path = project_dir / "shots" / "manifest.json"

    shotlist = load_json(shotlist_path)
    manifest = load_json(manifest_path) if manifest_path.exists() else {"shots": {}}

    for shot in sorted(shotlist["shots"], key=lambda item: item["sequence"]):
        if shot.get("backend") != "heygen":
            continue

        sid = shot["id"]
        entry = manifest["shots"].get(sid, {"status": "pending", "retries": 0})
        if entry.get("status") == "done":
            print(f"[skip] {sid} already done")
            continue

        out_path = project_dir / "shots" / "raw" / f"{sid}.mp4"

        if dry_run:
            missing = [key for key in ("model", "voice_id", "narration_line") if not shot.get(key)]
            if missing:
                print(f"[dry-run:error] {sid} missing {', '.join(missing)}")
                entry.update({"status": "failed", "missing": missing})
            else:
                print(f"[dry-run] {sid}: POST /v2/video/generate avatar={shot['model']} voice={shot['voice_id']}")
                entry.update({"status": "dry_run", "output_path": str(out_path)})
            manifest["shots"][sid] = entry
            save_json(manifest_path, manifest)
            continue

        for attempt in range(MAX_RETRIES + 1):
            try:
                print(f"[submit] {sid} (attempt {attempt + 1})")
                video_id = submit_shot(shot, api_key or "")
                entry.update({"status": "processing", "job_id": video_id, "retries": attempt})
                manifest["shots"][sid] = entry
                save_json(manifest_path, manifest)

                result = poll_shot(video_id, api_key or "")
                if result.get("status") != "completed":
                    raise RuntimeError(f"HeyGen reported failure: {result}")

                video_url = result.get("video_url") or result.get("video_url_caption")
                if not video_url:
                    raise RuntimeError(f"No video URL in HeyGen response: {result}")

                download(video_url, out_path)
                entry.update({"status": "done", "output_path": str(out_path)})
                manifest["shots"][sid] = entry
                save_json(manifest_path, manifest)
                print(f"[done] {sid} -> {out_path}")
                break
            except Exception as exc:
                print(f"[error] {sid}: {exc}", file=sys.stderr)
                entry["retries"] = attempt + 1
                if attempt == MAX_RETRIES:
                    entry["status"] = "failed"
                    manifest["shots"][sid] = entry
                    save_json(manifest_path, manifest)
                    print(f"[failed] {sid} needs manual review")

    print("Batch run complete. Check shots/manifest.json for any failed entries.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.project_dir, args.dry_run)
