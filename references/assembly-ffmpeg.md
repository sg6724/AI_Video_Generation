# Assembly - ffmpeg commands

Everything here runs locally. It requires `ffmpeg` and `ffprobe`.

On this machine, FFmpeg is installed at:

```text
C:\Users\Dell\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin
```

That directory has been added to the user PATH. A running Codex/session process may still
inherit the old PATH until restart; in that case, call `ffmpeg.exe` and `ffprobe.exe` by the
absolute path above.

## 1. Normalize clips

Normalize clips if shots came from different models, resolutions, frame rates, or codecs:

```powershell
New-Item -ItemType Directory -Force shots/normalized
Get-ChildItem shots/raw/*.mp4 | ForEach-Object {
  ffmpeg -i $_.FullName -vf "scale=1920:1080,fps=30" -c:v libx264 -pix_fmt yuv420p -c:a aac "shots/normalized/$($_.Name)"
}
```

If `ffmpeg` is not visible in the current shell, replace `ffmpeg` with the absolute
`ffmpeg.exe` path from above.

## 2. Concatenate in shot order

Build `concat_list.txt` from `shotlist.json` sequence order:

```text
file 'shots/normalized/shot_001.mp4'
file 'shots/normalized/shot_002.mp4'
```

Then concatenate:

```powershell
ffmpeg -f concat -safe 0 -i concat_list.txt -c copy shots/assembled_silent.mp4
```

If copy-mode concat fails, re-encode:

```powershell
ffmpeg -f concat -safe 0 -i concat_list.txt -c:v libx264 -c:a aac -pix_fmt yuv420p shots/assembled_silent.mp4
```

## 3. Add narration

```powershell
ffmpeg -i shots/assembled_silent.mp4 -i audio/narration.mp3 -c:v copy -map 0:v:0 -map 1:a:0 -shortest shots/assembled_narrated.mp4
```

## 4. Layer background music

```powershell
ffmpeg -i shots/assembled_narrated.mp4 -i audio/music.mp3 -filter_complex "[1:a]volume=0.12[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]" -map 0:v -map "[a]" -c:v copy output/final.mp4
```

## 5. Burn captions

```powershell
ffmpeg -i output/final.mp4 -vf "subtitles=captions.srt:force_style='FontSize=22'" output/final_captioned.mp4
```

## 6. Sanity check

```powershell
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 output/final.mp4
```

Confirm runtime matches `target_duration_sec` from `shotlist.json` within a few seconds.
