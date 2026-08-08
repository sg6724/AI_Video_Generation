# Backend-Flexible AI Video Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the code and skill documentation for a backend-flexible AI video pipeline — a manifest-driven system where each "beat" of a video can be rendered by HeyGen, Higgsfield, or Imagine Art, assembled locally with ffmpeg into a finished video.

**Architecture:** MCP-based backends (HeyGen, Imagine Art) can only be driven by the agent itself in-session (MCP tools aren't callable from a subprocess script), so the agent handles Stage 1-5 directly, dispatching each beat to either an MCP tool call (HeyGen/Imagine Art) or a CLI subprocess (Higgsfield via `scripts/pipeline/higgsfield_adapter.py`). Stage 6 (assembly) is a fully deterministic local script (`scripts/pipeline/assemble.py`) needing no network access. A shared `scripts/pipeline/manifest.py` module keeps beat status/job-id/output-path bookkeeping consistent across every code path that touches `shots/manifest.json`.

**Tech Stack:** Python 3.14 (stdlib only — `unittest`, `subprocess`, `json`, `pathlib`; no new pip dependencies), ffmpeg 9.0 (already installed via winget), Higgsfield CLI (`higgsfield generate create/get`, already installed+authenticated), HeyGen MCP tools, Imagine Art MCP tools.

## Global Constraints

- Character/reference assets used anywhere in this pipeline must be original work — never a copyrighted third-party character redesign or a real person's likeness (spec §3).
- Every beat defaults to the cheapest capable model on its assigned backend; no automatic upgrades (spec §9).
- Never assume success from a submit call — always poll to a terminal state before marking a beat `done` (spec §10).
- Retry a failed beat generation at most 2 times with the same prompt, then mark `failed` and stop — never silently skip a beat (spec §10).
- Assembly must refuse to run (with a clear error listing which beats) if any beat in the manifest is not `status: done` (spec §10).
- `ffmpeg`/`ffprobe` must be resolved defensively (PATH first, then the known winget install path) since shell PATH state is not reliable in this environment — never assume `ffmpeg` is bare-callable.
- No new pip packages — stdlib only, to avoid virtualenv/dependency setup friction mid-hackathon.

---

## File structure

```
D:/Hackathon/
├── SKILLS.md                              # MODIFY — rewrite to document the backend-flexible pipeline
├── references/
│   ├── imagine-art-setup.md               # CREATE — verified tool names, org_id flow, known generate_image bug
│   └── shot-list-schema.md                # MODIFY — add "imagine-art" as a valid backend value
├── scripts/
│   ├── validate_shotlist.py               # CREATE
│   └── pipeline/
│       ├── __init__.py                    # CREATE
│       ├── manifest.py                    # CREATE
│       ├── ffmpeg_utils.py                # CREATE
│       ├── higgsfield_adapter.py          # CREATE
│       └── assemble.py                    # CREATE
└── tests/
    ├── __init__.py                        # CREATE
    ├── test_manifest.py                   # CREATE
    ├── test_ffmpeg_utils.py               # CREATE
    ├── test_validate_shotlist.py          # CREATE
    ├── test_higgsfield_adapter.py         # CREATE
    └── test_assemble.py                   # CREATE
```

---

### Task 1: `scripts/pipeline/manifest.py` — shared manifest bookkeeping

**Files:**
- Create: `scripts/pipeline/__init__.py` (empty file, makes `pipeline` importable)
- Create: `scripts/pipeline/manifest.py`
- Test: `tests/test_manifest.py`
- Create: `tests/__init__.py` (empty file)

**Interfaces:**
- Consumes: nothing (first task)
- Produces (used by Tasks 4 and 5, and directly by the agent during MCP-driven beats):
  - `load_manifest(path: str) -> dict`
  - `save_manifest(path: str, manifest: dict) -> None`
  - `set_beat_status(manifest: dict, beat_id: str, status: str, job_id: str = None, output_path: str = None, retries: int = None) -> dict`
  - `all_beats_done(manifest: dict, beat_ids: list) -> bool`
  - `failed_beat_ids(manifest: dict) -> list`

Manifest on-disk shape (`shots/manifest.json`):
```json
{
  "shots": {
    "beat_001": {"status": "pending", "job_id": null, "output_path": null, "retries": 0}
  }
}
```

- [ ] **Step 1: Write the failing tests**

Create `tests/__init__.py` as an empty file, and `scripts/pipeline/__init__.py` as an empty file.

Create `tests/test_manifest.py`:
```python
import json
import os
import tempfile
import unittest

from scripts.pipeline.manifest import (
    load_manifest,
    save_manifest,
    set_beat_status,
    all_beats_done,
    failed_beat_ids,
)


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "manifest.json")

    def test_load_manifest_missing_file_returns_empty_shots(self):
        manifest = load_manifest(self.path)
        self.assertEqual(manifest, {"shots": {}})

    def test_save_then_load_roundtrip(self):
        data = {"shots": {"beat_001": {"status": "pending", "job_id": None,
                                        "output_path": None, "retries": 0}}}
        save_manifest(self.path, data)
        loaded = load_manifest(self.path)
        self.assertEqual(loaded, data)

    def test_set_beat_status_creates_new_entry(self):
        manifest = {"shots": {}}
        set_beat_status(manifest, "beat_001", "processing", job_id="job-abc")
        self.assertEqual(manifest["shots"]["beat_001"]["status"], "processing")
        self.assertEqual(manifest["shots"]["beat_001"]["job_id"], "job-abc")
        self.assertEqual(manifest["shots"]["beat_001"]["retries"], 0)

    def test_set_beat_status_updates_existing_entry_without_clobbering_fields(self):
        manifest = {"shots": {"beat_001": {"status": "processing", "job_id": "job-abc",
                                            "output_path": None, "retries": 0}}}
        set_beat_status(manifest, "beat_001", "done", output_path="shots/raw/beat_001.mp4")
        entry = manifest["shots"]["beat_001"]
        self.assertEqual(entry["status"], "done")
        self.assertEqual(entry["job_id"], "job-abc")  # preserved, not overwritten with None
        self.assertEqual(entry["output_path"], "shots/raw/beat_001.mp4")

    def test_all_beats_done_true_when_every_listed_beat_is_done(self):
        manifest = {"shots": {
            "beat_001": {"status": "done"},
            "beat_002": {"status": "done"},
        }}
        self.assertTrue(all_beats_done(manifest, ["beat_001", "beat_002"]))

    def test_all_beats_done_false_when_one_beat_missing_or_not_done(self):
        manifest = {"shots": {"beat_001": {"status": "done"}}}
        self.assertFalse(all_beats_done(manifest, ["beat_001", "beat_002"]))

    def test_failed_beat_ids_returns_only_failed(self):
        manifest = {"shots": {
            "beat_001": {"status": "done"},
            "beat_002": {"status": "failed"},
            "beat_003": {"status": "failed"},
        }}
        self.assertEqual(sorted(failed_beat_ids(manifest)), ["beat_002", "beat_003"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "D:/Hackathon" && python -m unittest tests.test_manifest -v`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'scripts.pipeline.manifest'` (module doesn't exist yet).

- [ ] **Step 3: Write the implementation**

Create `scripts/pipeline/manifest.py`:
```python
"""Shared load/save/status bookkeeping for shots/manifest.json."""
import json
import os


def load_manifest(path: str) -> dict:
    if not os.path.exists(path):
        return {"shots": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(path: str, manifest: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def set_beat_status(manifest: dict, beat_id: str, status: str, job_id: str = None,
                     output_path: str = None, retries: int = None) -> dict:
    shots = manifest.setdefault("shots", {})
    entry = shots.setdefault(beat_id, {"status": "pending", "job_id": None,
                                        "output_path": None, "retries": 0})
    entry["status"] = status
    if job_id is not None:
        entry["job_id"] = job_id
    if output_path is not None:
        entry["output_path"] = output_path
    if retries is not None:
        entry["retries"] = retries
    return manifest


def all_beats_done(manifest: dict, beat_ids: list) -> bool:
    shots = manifest.get("shots", {})
    return all(shots.get(bid, {}).get("status") == "done" for bid in beat_ids)


def failed_beat_ids(manifest: dict) -> list:
    shots = manifest.get("shots", {})
    return [bid for bid, entry in shots.items() if entry.get("status") == "failed"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "D:/Hackathon" && python -m unittest tests.test_manifest -v`
Expected: `OK` — all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/__init__.py scripts/pipeline/manifest.py tests/__init__.py tests/test_manifest.py
git commit -m "feat: add shared manifest bookkeeping module for the video pipeline"
```

---

### Task 2: `scripts/pipeline/ffmpeg_utils.py` — resolve and invoke ffmpeg/ffprobe defensively

**Files:**
- Create: `scripts/pipeline/ffmpeg_utils.py`
- Test: `tests/test_ffmpeg_utils.py`

**Interfaces:**
- Consumes: nothing
- Produces (used by Task 5):
  - `resolve_ffmpeg() -> str` (raises `FileNotFoundError` with a clear message if not found anywhere)
  - `resolve_ffprobe() -> str`
  - `run(args: list) -> subprocess.CompletedProcess` — `args[0]` must already be a resolved binary path; runs with `capture_output=True, text=True`, raises `RuntimeError` with stderr included if the process exits non-zero.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ffmpeg_utils.py`:
```python
import unittest
from unittest.mock import patch

from scripts.pipeline.ffmpeg_utils import resolve_ffmpeg, resolve_ffprobe, run


class TestFfmpegUtils(unittest.TestCase):
    def test_resolve_ffmpeg_returns_a_path_that_exists(self):
        path = resolve_ffmpeg()
        self.assertTrue(path)
        import os
        self.assertTrue(os.path.exists(path) or path == "ffmpeg")

    def test_resolve_ffmpeg_raises_when_not_found_anywhere(self):
        with patch("shutil.which", return_value=None), \
             patch("os.path.exists", return_value=False):
            with self.assertRaises(FileNotFoundError):
                resolve_ffmpeg()

    def test_resolve_ffprobe_returns_a_path_that_exists(self):
        path = resolve_ffprobe()
        self.assertTrue(path)

    def test_run_success_returns_completed_process(self):
        ffmpeg = resolve_ffmpeg()
        result = run([ffmpeg, "-version"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("ffmpeg version", result.stdout.lower() + result.stderr.lower())

    def test_run_failure_raises_runtime_error_with_stderr(self):
        ffmpeg = resolve_ffmpeg()
        with self.assertRaises(RuntimeError) as ctx:
            run([ffmpeg, "-i", "definitely_does_not_exist.mp4", "out.mp4"])
        self.assertIn("definitely_does_not_exist", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "D:/Hackathon" && python -m unittest tests.test_ffmpeg_utils -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.pipeline.ffmpeg_utils'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/pipeline/ffmpeg_utils.py`:
```python
"""Defensive ffmpeg/ffprobe resolution — never assume the shell's PATH is current."""
import os
import shutil
import subprocess

_WINGET_FFMPEG_DIR = (
    r"C:\Users\Dell\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin"
)


def _resolve(binary_name: str) -> str:
    on_path = shutil.which(binary_name)
    if on_path:
        return on_path
    fallback = os.path.join(_WINGET_FFMPEG_DIR, binary_name + ".exe")
    if os.path.exists(fallback):
        return fallback
    raise FileNotFoundError(
        f"{binary_name} not found on PATH or at {fallback}. "
        f"Install it (winget install Gyan.FFmpeg) or add it to PATH."
    )


def resolve_ffmpeg() -> str:
    return _resolve("ffmpeg")


def resolve_ffprobe() -> str:
    return _resolve("ffprobe")


def run(args: list) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stderr}"
        )
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "D:/Hackathon" && python -m unittest tests.test_ffmpeg_utils -v`
Expected: `OK` — all 5 tests pass (requires the real `ffmpeg` binary to be present, which it already is).

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/ffmpeg_utils.py tests/test_ffmpeg_utils.py
git commit -m "feat: add defensive ffmpeg/ffprobe binary resolution"
```

---

### Task 3: `scripts/validate_shotlist.py` — validate `shotlist.json` before any generation runs

**Files:**
- Create: `scripts/validate_shotlist.py`
- Test: `tests/test_validate_shotlist.py`

**Interfaces:**
- Consumes: nothing
- Produces (used by the agent/skill before starting Stage 4, and available as a standalone CLI check):
  - `VALID_BACKENDS = {"heygen", "higgsfield", "imagine-art"}`
  - `validate(shotlist: dict) -> list` — list of human-readable error strings; empty list means valid.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_validate_shotlist.py`:
```python
import unittest

from scripts.validate_shotlist import validate


def _valid_shotlist():
    return {
        "project": "demo",
        "target_duration_sec": 60,
        "visual_bible_ref": "visual-bible.md",
        "character_ref": None,
        "beats": [
            {
                "id": "beat_001", "sequence": 1, "narration_line": "Hello",
                "visual_prompt": "a calm harbor at dawn", "has_character": False,
                "is_title_card": False, "caption_text": "Hello",
                "duration_sec": 6, "backend": "higgsfield", "model": "seedance-2.0",
                "status": "pending", "job_id": None, "output_path": None, "retries": 0,
            },
            {
                "id": "beat_002", "sequence": 2, "narration_line": "World",
                "visual_prompt": "a bustling port", "has_character": False,
                "is_title_card": False, "caption_text": "World",
                "duration_sec": 6, "backend": "imagine-art", "model": "seedance-2.0",
                "status": "pending", "job_id": None, "output_path": None, "retries": 0,
            },
        ],
    }


class TestValidateShotlist(unittest.TestCase):
    def test_valid_shotlist_has_no_errors(self):
        self.assertEqual(validate(_valid_shotlist()), [])

    def test_missing_top_level_key_is_reported(self):
        shotlist = _valid_shotlist()
        del shotlist["target_duration_sec"]
        errors = validate(shotlist)
        self.assertTrue(any("target_duration_sec" in e for e in errors))

    def test_invalid_backend_is_reported(self):
        shotlist = _valid_shotlist()
        shotlist["beats"][0]["backend"] = "kling"
        errors = validate(shotlist)
        self.assertTrue(any("backend" in e and "beat_001" in e for e in errors))

    def test_non_contiguous_sequence_is_reported(self):
        shotlist = _valid_shotlist()
        shotlist["beats"][1]["sequence"] = 5
        errors = validate(shotlist)
        self.assertTrue(any("sequence" in e for e in errors))

    def test_duplicate_beat_id_is_reported(self):
        shotlist = _valid_shotlist()
        shotlist["beats"][1]["id"] = "beat_001"
        errors = validate(shotlist)
        self.assertTrue(any("duplicate" in e.lower() for e in errors))

    def test_non_positive_duration_is_reported(self):
        shotlist = _valid_shotlist()
        shotlist["beats"][0]["duration_sec"] = 0
        errors = validate(shotlist)
        self.assertTrue(any("duration_sec" in e and "beat_001" in e for e in errors))

    def test_missing_beat_field_is_reported(self):
        shotlist = _valid_shotlist()
        del shotlist["beats"][0]["visual_prompt"]
        errors = validate(shotlist)
        self.assertTrue(any("visual_prompt" in e and "beat_001" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "D:/Hackathon" && python -m unittest tests.test_validate_shotlist -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.validate_shotlist'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/validate_shotlist.py`:
```python
"""Validate a shotlist.json before Stage 4 generation starts."""
import json
import sys

VALID_BACKENDS = {"heygen", "higgsfield", "imagine-art"}

REQUIRED_TOP_LEVEL = ["project", "target_duration_sec", "visual_bible_ref", "beats"]
REQUIRED_BEAT_FIELDS = [
    "id", "sequence", "narration_line", "visual_prompt", "has_character",
    "is_title_card", "caption_text", "duration_sec", "backend", "model",
    "status", "job_id", "output_path", "retries",
]


def validate(shotlist: dict) -> list:
    errors = []

    for key in REQUIRED_TOP_LEVEL:
        if key not in shotlist:
            errors.append(f"missing top-level key: {key}")

    beats = shotlist.get("beats", [])
    seen_ids = set()
    sequences = []

    for beat in beats:
        beat_id = beat.get("id", "<unknown>")

        for field in REQUIRED_BEAT_FIELDS:
            if field not in beat:
                errors.append(f"{beat_id}: missing field {field}")

        if beat_id in seen_ids:
            errors.append(f"duplicate beat id: {beat_id}")
        seen_ids.add(beat_id)

        if "backend" in beat and beat["backend"] not in VALID_BACKENDS:
            errors.append(
                f"{beat_id}: invalid backend {beat['backend']!r}, "
                f"must be one of {sorted(VALID_BACKENDS)}"
            )

        if "duration_sec" in beat and not (isinstance(beat["duration_sec"], (int, float))
                                            and beat["duration_sec"] > 0):
            errors.append(f"{beat_id}: duration_sec must be a positive number")

        if "sequence" in beat:
            sequences.append(beat["sequence"])

    if sequences:
        expected = list(range(1, len(sequences) + 1))
        if sorted(sequences) != expected:
            errors.append(
                f"sequence values are not contiguous starting at 1: {sorted(sequences)}"
            )

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python validate_shotlist.py <path-to-shotlist.json>")
        return 2
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        shotlist = json.load(f)
    errors = validate(shotlist)
    if errors:
        print(f"{len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("shotlist.json is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "D:/Hackathon" && python -m unittest tests.test_validate_shotlist -v`
Expected: `OK` — all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_shotlist.py tests/test_validate_shotlist.py
git commit -m "feat: add shotlist.json validator"
```

---

### Task 4: `scripts/pipeline/higgsfield_adapter.py` — CLI-driven backend for Higgsfield beats

**Files:**
- Create: `scripts/pipeline/higgsfield_adapter.py`
- Test: `tests/test_higgsfield_adapter.py`
- Reference (read, don't modify): `references/higgsfield-setup.md` — confirms the real CLI surface: `higgsfield generate create <model> --prompt "..." [--image-references <path>] [--wait]`, `higgsfield generate get <job_id>`

**Interfaces:**
- Consumes: `scripts.pipeline.manifest.{load_manifest, save_manifest, set_beat_status}` (Task 1)
- Produces (used by the SKILLS.md orchestration procedure, Task 8):
  - `build_create_command(model: str, prompt: str, reference_image: str = None) -> list`
  - `build_get_command(job_id: str) -> list`
  - `parse_job_id(response: dict) -> str` (raises `KeyError` with clear message if absent)
  - `is_terminal_status(status: str) -> bool`
  - `run_higgsfield_backend(project_dir: str) -> None` — main loop: reads `shotlist.json` + `visual-bible.md` from `project_dir`, filters beats with `backend == "higgsfield"`, submits/polls/downloads each via subprocess, updates `shots/manifest.json` via Task 1's helpers, retries up to 2x per spec, stops and leaves the beat `failed` on exhausted retries (never auto-continues past a failure).

**Note on the known CLI bug found earlier in this project:** the *previous* `scripts/generate_shots_higgsfield.py` template assumed `higgsfield video create` / `higgsfield video status`, which do not exist on the installed CLI. This task uses the verified real subcommands (`higgsfield generate create`, `higgsfield generate get`) — do not reintroduce the old, wrong command names.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_higgsfield_adapter.py`:
```python
import unittest

from scripts.pipeline.higgsfield_adapter import (
    build_create_command,
    build_get_command,
    parse_job_id,
    is_terminal_status,
)


class TestHiggsfieldAdapter(unittest.TestCase):
    def test_build_create_command_without_reference_image(self):
        cmd = build_create_command("seedance-2.0", "a calm harbor at dawn")
        self.assertEqual(cmd, [
            "higgsfield", "generate", "create", "seedance-2.0",
            "--prompt", "a calm harbor at dawn", "--json",
        ])

    def test_build_create_command_with_reference_image(self):
        cmd = build_create_command("soul", "the explorer looks out",
                                    reference_image="assets/characters/compass.png")
        self.assertEqual(cmd, [
            "higgsfield", "generate", "create", "soul",
            "--prompt", "the explorer looks out",
            "--image-references", "assets/characters/compass.png",
            "--json",
        ])

    def test_build_get_command(self):
        cmd = build_get_command("job-123")
        self.assertEqual(cmd, ["higgsfield", "generate", "get", "job-123", "--json"])

    def test_parse_job_id_from_id_field(self):
        self.assertEqual(parse_job_id({"id": "job-123"}), "job-123")

    def test_parse_job_id_from_job_id_field(self):
        self.assertEqual(parse_job_id({"job_id": "job-456"}), "job-456")

    def test_parse_job_id_raises_when_absent(self):
        with self.assertRaises(KeyError):
            parse_job_id({"status": "queued"})

    def test_is_terminal_status_true_for_completed_and_failed(self):
        self.assertTrue(is_terminal_status("completed"))
        self.assertTrue(is_terminal_status("failed"))
        self.assertTrue(is_terminal_status("error"))

    def test_is_terminal_status_false_for_in_progress_states(self):
        self.assertFalse(is_terminal_status("queued"))
        self.assertFalse(is_terminal_status("processing"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "D:/Hackathon" && python -m unittest tests.test_higgsfield_adapter -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.pipeline.higgsfield_adapter'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/pipeline/higgsfield_adapter.py`:
```python
"""Higgsfield CLI backend adapter — the one backend that runs as a subprocess
rather than an agent-driven MCP call, since Higgsfield only exposes a CLI here."""
import json
import os
import subprocess
import time

from scripts.pipeline.manifest import load_manifest, save_manifest, set_beat_status

POLL_INTERVAL_SEC = 10
POLL_TIMEOUT_SEC = 600
MAX_RETRIES = 2

_TERMINAL_STATUSES = {"completed", "failed", "error"}


def build_create_command(model: str, prompt: str, reference_image: str = None) -> list:
    cmd = ["higgsfield", "generate", "create", model, "--prompt", prompt]
    if reference_image:
        cmd += ["--image-references", reference_image]
    cmd.append("--json")
    return cmd


def build_get_command(job_id: str) -> list:
    return ["higgsfield", "generate", "get", job_id, "--json"]


def parse_job_id(response: dict) -> str:
    job_id = response.get("id") or response.get("job_id")
    if not job_id:
        raise KeyError(f"no id/job_id field in response: {response}")
    return job_id


def is_terminal_status(status: str) -> bool:
    return status in _TERMINAL_STATUSES


def _run_cli(cmd: list) -> dict:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"higgsfield CLI exited {result.returncode}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _submit(beat: dict, visual_bible: str) -> str:
    full_prompt = f"{visual_bible}\n\n{beat['visual_prompt']}"
    reference_image = beat.get("character_ref") if beat.get("has_character") else None
    cmd = build_create_command(beat["model"], full_prompt, reference_image)
    response = _run_cli(cmd)
    return parse_job_id(response)


def _poll(job_id: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT_SEC
    while time.time() < deadline:
        response = _run_cli(build_get_command(job_id))
        if is_terminal_status(response.get("status", "")):
            return response
        time.sleep(POLL_INTERVAL_SEC)
    raise TimeoutError(f"job {job_id} did not finish within {POLL_TIMEOUT_SEC}s")


def _download(result: dict, out_path: str) -> None:
    import urllib.request
    url = result.get("output_url") or result.get("url")
    if not url:
        raise RuntimeError(f"no output url in completed response: {result}")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    urllib.request.urlretrieve(url, out_path)


def run_higgsfield_backend(project_dir: str) -> None:
    shotlist_path = os.path.join(project_dir, "shotlist.json")
    manifest_path = os.path.join(project_dir, "shots", "manifest.json")
    visual_bible_path = os.path.join(project_dir, "visual-bible.md")

    with open(shotlist_path, "r", encoding="utf-8") as f:
        shotlist = json.load(f)
    visual_bible = ""
    if os.path.exists(visual_bible_path):
        with open(visual_bible_path, "r", encoding="utf-8") as f:
            visual_bible = f.read()

    manifest = load_manifest(manifest_path)

    for beat in shotlist["beats"]:
        if beat.get("backend") != "higgsfield" or beat.get("is_title_card"):
            continue
        beat_id = beat["id"]
        existing = manifest.get("shots", {}).get(beat_id, {})
        if existing.get("status") == "done":
            print(f"[skip] {beat_id} already done")
            continue

        retries = existing.get("retries", 0)
        for attempt in range(retries, MAX_RETRIES + 1):
            try:
                print(f"[submit] {beat_id} (attempt {attempt + 1})")
                job_id = _submit(beat, visual_bible)
                set_beat_status(manifest, beat_id, "processing", job_id=job_id)
                save_manifest(manifest_path, manifest)

                result = _poll(job_id)
                if result.get("status") == "completed":
                    out_path = os.path.join(project_dir, "shots", "raw", f"{beat_id}.mp4")
                    _download(result, out_path)
                    set_beat_status(manifest, beat_id, "done",
                                     output_path=os.path.relpath(out_path, project_dir))
                    save_manifest(manifest_path, manifest)
                    print(f"[done] {beat_id} -> {out_path}")
                    break
                raise RuntimeError(f"higgsfield reported failure: {result}")
            except Exception as e:
                print(f"[error] {beat_id}: {e}")
                set_beat_status(manifest, beat_id, "processing", retries=attempt + 1)
                save_manifest(manifest_path, manifest)
                if attempt == MAX_RETRIES:
                    set_beat_status(manifest, beat_id, "failed")
                    save_manifest(manifest_path, manifest)
                    print(f"[failed] {beat_id} — needs manual review, stopping this beat")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "D:/Hackathon" && python -m unittest tests.test_higgsfield_adapter -v`
Expected: `OK` — all 8 tests pass. (These test the pure command-building/parsing functions only — `run_higgsfield_backend` itself is exercised in real usage, not unit tests, since it needs the paid CLI.)

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/higgsfield_adapter.py tests/test_higgsfield_adapter.py
git commit -m "feat: add Higgsfield CLI backend adapter with verified command syntax"
```

---

### Task 5: `scripts/pipeline/assemble.py` — Stage 6 deterministic ffmpeg assembly

**Files:**
- Create: `scripts/pipeline/assemble.py`
- Test: `tests/test_assemble.py`
- Reference (read, don't modify): `references/assembly-ffmpeg.md` — the command reference this implements

**Interfaces:**
- Consumes:
  - `scripts.pipeline.manifest.{load_manifest, all_beats_done, failed_beat_ids}` (Task 1)
  - `scripts.pipeline.ffmpeg_utils.{resolve_ffmpeg, run}` (Task 2)
- Produces:
  - `build_concat_list(beats: list, raw_dir: str, workdir: str) -> str` (path to written `concat_list.txt`, beats sorted by `sequence`)
  - `render_title_card(text: str, duration_sec: float, dst_path: str, size: tuple = (1920, 1080)) -> None`
  - `normalize_clip(src_path: str, dst_path: str, size: tuple = (1920, 1080), fps: int = 30) -> None`
  - `concatenate(concat_list_path: str, dst_path: str) -> None`
  - `mux_narration(video_path: str, narration_path: str, dst_path: str) -> None`
  - `assemble(project_dir: str) -> str` (returns path to `output/final.mp4`; raises `RuntimeError` listing incomplete/failed beats if the manifest isn't all `done`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_assemble.py`:
```python
import json
import os
import shutil
import tempfile
import unittest

from scripts.pipeline.ffmpeg_utils import resolve_ffmpeg, resolve_ffprobe, run
from scripts.pipeline.assemble import (
    build_concat_list,
    render_title_card,
    normalize_clip,
    concatenate,
    mux_narration,
    assemble,
)


def _make_test_clip(path: str, color: str, duration: float, size=(320, 240)):
    ffmpeg = resolve_ffmpeg()
    run([
        ffmpeg, "-y", "-f", "lavfi",
        "-i", f"color=c={color}:s={size[0]}x{size[1]}:d={duration}",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-shortest", "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        path,
    ])


def _probe_duration(path: str) -> float:
    ffprobe = resolve_ffprobe()
    result = run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                  "-of", "default=noprint_wrappers=1:nokey=1", path])
    return float(result.stdout.strip())


class TestAssembleUnits(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_build_concat_list_orders_by_sequence(self):
        raw_dir = os.path.join(self.tmpdir, "raw")
        os.makedirs(raw_dir)
        for name in ["beat_002.mp4", "beat_001.mp4"]:
            open(os.path.join(raw_dir, name), "w").close()
        beats = [
            {"id": "beat_002", "sequence": 2},
            {"id": "beat_001", "sequence": 1},
        ]
        list_path = build_concat_list(beats, raw_dir, self.tmpdir)
        with open(list_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertTrue(lines[0].endswith("beat_001.mp4'"))
        self.assertTrue(lines[1].endswith("beat_002.mp4'"))

    def test_render_title_card_produces_video_of_requested_duration(self):
        dst = os.path.join(self.tmpdir, "title.mp4")
        render_title_card("Hello NestGen", 2.0, dst)
        self.assertTrue(os.path.exists(dst))
        self.assertAlmostEqual(_probe_duration(dst), 2.0, delta=0.3)

    def test_normalize_clip_produces_requested_resolution(self):
        src = os.path.join(self.tmpdir, "src.mp4")
        dst = os.path.join(self.tmpdir, "norm.mp4")
        _make_test_clip(src, "blue", 1.0, size=(640, 480))
        normalize_clip(src, dst, size=(1280, 720), fps=30)
        ffprobe = resolve_ffprobe()
        result = run([ffprobe, "-v", "error", "-select_streams", "v:0",
                      "-show_entries", "stream=width,height",
                      "-of", "csv=s=x:p=0", dst])
        self.assertEqual(result.stdout.strip(), "1280x720")

    def test_concatenate_two_clips_sums_durations(self):
        clip_a = os.path.join(self.tmpdir, "a.mp4")
        clip_b = os.path.join(self.tmpdir, "b.mp4")
        _make_test_clip(clip_a, "red", 1.0)
        _make_test_clip(clip_b, "green", 1.0)
        beats = [{"id": "a", "sequence": 1}, {"id": "b", "sequence": 2}]
        raw_dir = self.tmpdir
        shutil.copy(clip_a, os.path.join(raw_dir, "a.mp4"))
        shutil.copy(clip_b, os.path.join(raw_dir, "b.mp4"))
        list_path = build_concat_list(beats, raw_dir, self.tmpdir)
        out = os.path.join(self.tmpdir, "concat.mp4")
        concatenate(list_path, out)
        self.assertAlmostEqual(_probe_duration(out), 2.0, delta=0.3)

    def test_mux_narration_replaces_audio_with_narration_track(self):
        video = os.path.join(self.tmpdir, "video.mp4")
        _make_test_clip(video, "yellow", 2.0)
        narration = os.path.join(self.tmpdir, "narration.mp3")
        ffmpeg = resolve_ffmpeg()
        run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
             narration])
        out = os.path.join(self.tmpdir, "with_narration.mp4")
        mux_narration(video, narration, out)
        self.assertTrue(os.path.exists(out))
        self.assertAlmostEqual(_probe_duration(out), 2.0, delta=0.3)


class TestAssembleEndToEnd(unittest.TestCase):
    def setUp(self):
        self.project_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.project_dir, "shots", "raw"))
        os.makedirs(os.path.join(self.project_dir, "audio"))
        os.makedirs(os.path.join(self.project_dir, "output"))

        for beat_id, color in [("beat_001", "red"), ("beat_002", "blue")]:
            _make_test_clip(
                os.path.join(self.project_dir, "shots", "raw", f"{beat_id}.mp4"),
                color, 1.0,
            )

        ffmpeg = resolve_ffmpeg()
        run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
             os.path.join(self.project_dir, "audio", "narration.mp3")])

        shotlist = {
            "project": "test", "target_duration_sec": 2,
            "visual_bible_ref": "visual-bible.md", "character_ref": None,
            "beats": [
                {"id": "beat_001", "sequence": 1, "narration_line": None,
                 "visual_prompt": "x", "has_character": False, "is_title_card": False,
                 "caption_text": None, "duration_sec": 1, "backend": "higgsfield",
                 "model": "x", "status": "done", "job_id": "j1",
                 "output_path": "shots/raw/beat_001.mp4", "retries": 0},
                {"id": "beat_002", "sequence": 2, "narration_line": None,
                 "visual_prompt": "x", "has_character": False, "is_title_card": False,
                 "caption_text": None, "duration_sec": 1, "backend": "higgsfield",
                 "model": "x", "status": "done", "job_id": "j2",
                 "output_path": "shots/raw/beat_002.mp4", "retries": 0},
            ],
        }
        with open(os.path.join(self.project_dir, "shotlist.json"), "w") as f:
            json.dump(shotlist, f)

        manifest = {"shots": {
            "beat_001": {"status": "done", "job_id": "j1",
                         "output_path": "shots/raw/beat_001.mp4", "retries": 0},
            "beat_002": {"status": "done", "job_id": "j2",
                         "output_path": "shots/raw/beat_002.mp4", "retries": 0},
        }}
        with open(os.path.join(self.project_dir, "shots", "manifest.json"), "w") as f:
            json.dump(manifest, f)

    def tearDown(self):
        shutil.rmtree(self.project_dir, ignore_errors=True)

    def test_assemble_produces_final_video_with_narration_length(self):
        output_path = assemble(self.project_dir)
        self.assertTrue(os.path.exists(output_path))
        self.assertAlmostEqual(_probe_duration(output_path), 2.0, delta=0.5)

    def test_assemble_raises_when_a_beat_is_not_done(self):
        manifest_path = os.path.join(self.project_dir, "shots", "manifest.json")
        with open(manifest_path) as f:
            manifest = json.load(f)
        manifest["shots"]["beat_002"]["status"] = "failed"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        with self.assertRaises(RuntimeError) as ctx:
            assemble(self.project_dir)
        self.assertIn("beat_002", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "D:/Hackathon" && python -m unittest tests.test_assemble -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.pipeline.assemble'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/pipeline/assemble.py`:
```python
"""Stage 6 — deterministic local ffmpeg assembly. No network access."""
import json
import os

from scripts.pipeline.ffmpeg_utils import resolve_ffmpeg, resolve_ffprobe, run
from scripts.pipeline.manifest import load_manifest, all_beats_done, failed_beat_ids

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
]


def _resolve_font() -> str:
    for candidate in _FONT_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(
        f"No usable font found among {_FONT_CANDIDATES}; title cards need a fontfile."
    )


def build_concat_list(beats: list, raw_dir: str, workdir: str) -> str:
    ordered = sorted(beats, key=lambda b: b["sequence"])
    list_path = os.path.join(workdir, "concat_list.txt")
    os.makedirs(workdir, exist_ok=True)
    with open(list_path, "w", encoding="utf-8") as f:
        for beat in ordered:
            clip_path = os.path.join(raw_dir, f"{beat['id']}.mp4").replace("\\", "/")
            f.write(f"file '{clip_path}'\n")
    return list_path


def render_title_card(text: str, duration_sec: float, dst_path: str,
                       size: tuple = (1920, 1080)) -> None:
    ffmpeg = resolve_ffmpeg()
    font = _resolve_font()
    escaped_text = text.replace(":", r"\:").replace("'", r"\'")
    os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
    run([
        ffmpeg, "-y", "-f", "lavfi",
        "-i", f"color=c=black:s={size[0]}x{size[1]}:d={duration_sec}",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-shortest",
        "-vf", (f"drawtext=fontfile='{font}':text='{escaped_text}':"
                f"fontcolor=white:fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2"),
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        dst_path,
    ])


def normalize_clip(src_path: str, dst_path: str, size: tuple = (1920, 1080),
                    fps: int = 30) -> None:
    ffmpeg = resolve_ffmpeg()
    os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
    run([
        ffmpeg, "-y", "-i", src_path,
        "-vf", f"scale={size[0]}:{size[1]},fps={fps}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        dst_path,
    ])


def concatenate(concat_list_path: str, dst_path: str) -> None:
    ffmpeg = resolve_ffmpeg()
    os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
    run([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path,
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        dst_path,
    ])


def mux_narration(video_path: str, narration_path: str, dst_path: str) -> None:
    ffmpeg = resolve_ffmpeg()
    os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
    run([
        ffmpeg, "-y", "-i", video_path, "-i", narration_path,
        "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", "-shortest",
        dst_path,
    ])


def assemble(project_dir: str) -> str:
    shotlist_path = os.path.join(project_dir, "shotlist.json")
    manifest_path = os.path.join(project_dir, "shots", "manifest.json")

    with open(shotlist_path, "r", encoding="utf-8") as f:
        shotlist = json.load(f)
    manifest = load_manifest(manifest_path)

    beat_ids = [b["id"] for b in shotlist["beats"] if not b.get("is_title_card")]
    if not all_beats_done(manifest, beat_ids):
        failed = failed_beat_ids(manifest)
        incomplete = [bid for bid in beat_ids
                      if manifest.get("shots", {}).get(bid, {}).get("status") != "done"]
        raise RuntimeError(
            f"Cannot assemble — not all beats are done. "
            f"Failed: {failed}. Incomplete: {incomplete}."
        )

    raw_dir = os.path.join(project_dir, "shots", "raw")
    work_dir = os.path.join(project_dir, "shots", "_work")
    os.makedirs(work_dir, exist_ok=True)

    beats_for_concat = [b for b in shotlist["beats"] if not b.get("is_title_card")]
    concat_list_path = build_concat_list(beats_for_concat, raw_dir, work_dir)

    concatenated_path = os.path.join(work_dir, "concatenated.mp4")
    concatenate(concat_list_path, concatenated_path)

    output_dir = os.path.join(project_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    final_path = os.path.join(output_dir, "final.mp4")

    narration_path = os.path.join(project_dir, "audio", "narration.mp3")
    if os.path.exists(narration_path):
        mux_narration(concatenated_path, narration_path, final_path)
    else:
        import shutil as _shutil
        _shutil.copy(concatenated_path, final_path)

    return final_path


def main() -> int:
    import sys
    if len(sys.argv) != 2:
        print("Usage: python assemble.py <project-dir>")
        return 2
    output_path = assemble(sys.argv[1])
    print(f"Assembled: {output_path}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "D:/Hackathon" && python -m unittest tests.test_assemble -v`
Expected: `OK` — all 7 tests pass. (This is the slowest test file since it shells out to real ffmpeg several times — allow it to take up to a minute.)

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/assemble.py tests/test_assemble.py
git commit -m "feat: add deterministic ffmpeg assembly stage (Stage 6)"
```

---

### Task 6: `references/imagine-art-setup.md` — document the verified Imagine Art integration

**Files:**
- Create: `references/imagine-art-setup.md`

**Interfaces:**
- Consumes: nothing (documentation)
- Produces: read by the agent (via Task 8's SKILLS.md) before driving any Imagine Art beat

- [ ] **Step 1: Write the reference doc**

Create `references/imagine-art-setup.md`:
```markdown
# Imagine Art setup (Claude Code)

Imagine Art connects via MCP only in this project (`https://mcp.imagine.art`, already
added and OAuth-authenticated as of this session). There is no CLI and no verified
direct-REST-API path set up — do not add `VYRO_API_KEY`-based code without the user
first generating that key themselves from their dashboard (Settings → API); this agent
cannot generate API keys on the user's behalf.

## Required first call: organization

Every generation/balance tool requires `org_id`. Call `select_organization` once per
session and reuse the returned id for every subsequent call — the server is stateless
and does not remember your selection. Never guess or hardcode an org_id from a prior
session; orgs can differ per account.

## Known bug: `generate_image` plan-gating (verified this session)

As of this session, every model passed to `generate_image` — including the account's
own nominal free-tier default (`nano-banana-pro`) — returns a
"model is inaccessible in your current plan" or "Free accounts can only use
nano-banana-pro" error, contradicting each other. This reproduced consistently across
`nano-banana-pro` (explicit and default), `imagine-art-2.0`, and `seedream-v5-lite`,
despite the account's own web UI (imagine.art) showing `ImagineArt 2.0` as unlocked and
available for 25 credits. This is a server-side bug in the MCP tool's plan-gating logic,
not something fixable from this codebase. **Before relying on `generate_image` for any
real beat, run one test call and confirm it actually succeeds** — do not assume the bug
is fixed just because time has passed.

## `generate_video` — untested, may not share the same bug

`generate_video` has not been called in this project yet. It's a different tool/code
path than `generate_image`, so the plan-gating bug above may or may not apply. **Run one
test call before committing a real beat to this backend.**

## Balance check before a batch

Call `get_balance` with the selected `org_id` before any multi-beat batch that uses this
backend. Confirmed working this session (returned `{"current": 100, "unit": "credits"}`
for the connected account) — but credits are consumed by every generation, so re-check
before a large run, not just once at the start of a session.

## Relevant tools (verified present as of this session)

- `select_organization` — call first, every session
- `get_balance(org_id)` — check credits before a batch
- `generate_image(org_id, prompt, aspect_ratio, model, ...)` — see bug note above
- `generate_video(org_id, prompt, ...)` — untested, verify with one call first
- `generate_music(org_id, ...)` — background music, if needed for Stage 6
- `fetch_status(id, sync=True)` — poll a queued generation; in a text-only (non-widget)
  context, pass `sync: true` to block server-side for up to ~45s rather than polling
  yourself in a loop
- `create_avatar` / `generate_avatar` — **do not call directly**; these are widget
  back-channel tools locked to the Ad Studio flow (their own descriptions say
  "do NOT call this yourself"). Use plain `generate_image` for a standalone character
  reference instead.

Full tool list is available via `ToolSearch` with a query like `select:mcp__imagine-art__generate_video,mcp__imagine-art__generate_image` if schemas need re-checking — the tool surface may change over time.
```

- [ ] **Step 2: Commit**

```bash
git add references/imagine-art-setup.md
git commit -m "docs: document verified Imagine Art MCP integration and known bugs"
```

---

### Task 7: `references/shot-list-schema.md` — add Imagine Art as a valid backend

**Files:**
- Modify: `references/shot-list-schema.md`

**Interfaces:**
- Consumes: nothing
- Produces: read by the agent when drafting `shotlist.json` in Stage 1/2

- [ ] **Step 1: Read the current file**

Run: view `references/shot-list-schema.md` to find the `"backend"` field description (it currently documents `"heygen" | "higgsfield"` only, from the original pipeline design).

- [ ] **Step 2: Update the backend field description**

Find the line describing the `backend` field in the schema section and the worked example, and update the allowed values to include `imagine-art`, e.g. change:
```
"backend": "heygen | higgsfield",
```
to:
```
"backend": "heygen | higgsfield | imagine-art",
```
And in the prose rules list, update any sentence naming only two backends to name all three, referencing `references/imagine-art-setup.md` alongside the existing `heygen-setup.md`/`higgsfield-setup.md` references.

- [ ] **Step 3: Commit**

```bash
git add references/shot-list-schema.md
git commit -m "docs: add imagine-art as a valid shotlist.json backend value"
```

---

### Task 8: `SKILLS.md` — rewrite as the backend-flexible orchestration procedure

**Files:**
- Modify: `SKILLS.md`

**Interfaces:**
- Consumes: everything from Tasks 1-7 (this is the document that ties the whole pipeline together for the agent to follow)
- Produces: nothing further downstream — this is the top-level skill entry point

- [ ] **Step 1: Rewrite the "Choosing a backend" and Stage 4/5 sections**

Edit `SKILLS.md`'s existing structure (keep the frontmatter, Stage 0-3 and Stage 6-8 content largely as-is) and replace the backend-selection guidance and Stage 4/5 content with:

```markdown
## Choosing a backend per beat

Three backends are available, each with a different integration shape — pick per beat,
not per project:

| Backend | Integration | Best for | Status this session |
|---|---|---|---|
| Higgsfield | CLI subprocess (`scripts/pipeline/higgsfield_adapter.py`) | Cinematic B-roll, many models | Installed + authenticated. User is cost-sensitive — use only when worth it. |
| HeyGen | Agent-driven MCP (`mcp__heygen__*`) | Presenter/avatar segments | MCP connected. |
| Imagine Art | Agent-driven MCP (`mcp__imagine-art__*`) | Multi-model image/video, captions, music | MCP connected. `generate_image` has a known plan-gating bug — see `references/imagine-art-setup.md` before using it. |

Character/reference images must be original work — never a copyrighted third-party
character or a real person's likeness (non-negotiable, not a style preference).

Before drafting `shotlist.json`, run `python scripts/validate_shotlist.py <path>` after
writing it, and fix every reported error before Stage 4 starts.

## Stage 4 — Beat generation loop (backend-dispatched)

For beats with `"backend": "higgsfield"`: run
`python -m scripts.pipeline.higgsfield_adapter <project-dir>` (or call
`run_higgsfield_backend(project_dir)` directly) — this is unattended, it submits,
polls, downloads, and updates `shots/manifest.json` for every higgsfield-tagged beat,
retrying up to 2x per beat before marking it `failed` and stopping that beat (never
silently skipping one).

For beats with `"backend": "heygen"` or `"backend": "imagine-art"`: these cannot run as
a background script — MCP tools are only callable by the agent in this session. For
each such beat, in order:
1. Call the appropriate MCP tool directly (e.g. `mcp__heygen__create_video_from_avatar`,
   or `mcp__imagine-art__generate_video` after confirming `org_id` via
   `select_organization`).
2. Immediately record the returned job/generation id into `shots/manifest.json` using
   `scripts.pipeline.manifest.set_beat_status(manifest, beat_id, "processing", job_id=...)`
   then `save_manifest(...)` — do this before polling, so a crash mid-poll is still
   resumable.
3. Poll to a terminal state (`fetch_status(id, sync=True)` for Imagine Art;
   `get_video_agent_session` / `get_video` for HeyGen) — never assume success from the
   submit call alone.
4. Download the result to `shots/raw/<beat_id>.mp4`, then
   `set_beat_status(manifest, beat_id, "done", output_path=...)` and save.
5. On failure, retry the same beat up to 2 times total before marking it `failed` in the
   manifest and stopping — surface the error, don't continue past a failed beat.

## Stage 5 — Narration voiceover

Generate TTS for the full `script.md` narration via whichever connected backend offers
it (HeyGen `create_speech`, or Imagine Art's TTS/voice tools if available — verify the
current tool list first) → save as `audio/narration.mp3`.

## Stage 6 — Assembly

Run `python -m scripts.pipeline.assemble <project-dir>` (or call `assemble(project_dir)`
directly). This is fully local and deterministic — no network calls, so it never spends
credits. It refuses to run (raising a clear error naming the beats) if any beat in
`shots/manifest.json` isn't `status: done`. Output: `output/final.mp4`.
```

Keep the rest of `SKILLS.md` (Stage 0 intake, Stage 1-3, project structure, Stage 7-8,
error handling/credits, reference file list) as-is except: update the "Reference files"
list at the bottom to include `references/imagine-art-setup.md`, and update the
top-of-file description/frontmatter's backend list to say "HeyGen, Higgsfield, or
Imagine Art" wherever it currently names only two.

- [ ] **Step 2: Commit**

```bash
git add SKILLS.md
git commit -m "docs: rewrite SKILLS.md orchestration for the backend-flexible pipeline"
```

---

## Self-review notes (already applied above)

- **Spec coverage:** §5 backend status table → Task 6/8; §6 Stage 1-7 architecture →
  Tasks 4/5/8; §7 project structure → matches Tasks 4/5's path assumptions; §8 manifest
  schema → Task 1 + Task 3 validator; §9 cost policy (cheapest default, no
  auto-upgrade, check balance first) → documented in Task 8, enforced by human judgment
  at shotlist-drafting time (not automatable without live pricing data, per spec §11);
  §10 error handling (poll to terminal, persist progress, retry 2x then stop, assembly
  checks all-done) → Tasks 1/4/5 directly implement this; §12 QA approach → Task 8's
  Stage 7 text (unchanged from existing SKILLS.md, already covers this).
- **Placeholder scan:** no TBD/TODO in any task; every code block is complete,
  runnable code, not a sketch.
- **Type consistency:** `manifest.py`'s `set_beat_status` signature is used identically
  in Task 4 (`higgsfield_adapter.py`) and referenced identically in Task 8's SKILLS.md
  instructions for the MCP-driven path. `assemble.py`'s `assemble(project_dir: str) -> str`
  return type matches Task 8's usage. Beat dict field names (`id`, `sequence`, `backend`,
  `model`, `has_character`, `is_title_card`, `duration_sec`) are identical across Tasks
  1, 3, 4, 5, and the spec's §8 schema.
