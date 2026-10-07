# OLIØN Video Toolkit

```
══════════════════════════════════
        ╔═╗ ╦   ╦ ╔═╗ ╔╗╔
        ║ ║ ║   ║ ║/║ ║║║
        ╚═╝ ╩═╝ ╩ ╚═╝ ╝╚╝
    V I D E O   T O O L K I T
   v1.0 · FFmpeg on your phone
══════════════════════════════════
```

A menu-driven video and audio toolkit for **Termux (Android)**, built on FFmpeg. It runs fully on your phone, with no PC needed.

## Quick start

```
pkg update -y
pkg install python git ffmpeg yt-dlp termux-api -y
termux-setup-storage
git clone https://github.com/princeoken4-create/OLION-VIDEO-TOOLKIT.git
cd OLION-VIDEO-TOOLKIT
python videotoolkit.py
```

Tap **Allow** when Android asks for storage permission.

## Features

| # | Feature |
|---|---------|
| 1 | Video information (duration, size, resolution, FPS, codecs) |
| 2 | Trim video (fast, or frame-accurate) |
| 3 | Extract audio (MP3, WAV, AAC, FLAC) |
| 4 | Change video speed |
| 5 | Reverse video |
| 6 | Video interpolation (60 / 120 fps) |
| 7 | Upscale (2x, 1080p, 1440p, 4K with Lanczos resizing) |
| 8 | Audio changer (speed, pitch, format conversion) |
| 9 | Download + process (yt-dlp) |
| 10 | Batch compress a folder |
| 11 | Watch folder mode (auto-compress new videos) |
| 12 | Fix variable frame rate (fixes audio drift from phone recordings) |

Every FFmpeg job shows a live progress bar, and long jobs keep your phone awake until they finish.

## Requirements

- Android phone with **Termux** from [F-Droid](https://f-droid.org/packages/com.termux/) or GitHub. The Play Store version is outdated.
- About 1 GB of free storage, plus space for your videos
- **Termux:API** app (optional, only for notifications)

You can also run `bash setup.sh` after cloning to install everything in one go.

## Usage

```
python videotoolkit.py
```

Type the number of the option you want and follow the prompts.

- Use full paths, for example `~/storage/downloads/video.mp4`
- Output names must include the extension, for example `output.mp4`
- Files are saved to `~/storage/downloads` unless you pick another folder
- To change the default folder, edit the `SAVE_DIR` line at the top of `videotoolkit.py`
- Press `Ctrl+C` to cancel a running job and return to the menu

## Warnings

- **Storage permission:** if you see "No such file or directory" for `~/storage/...`, run `termux-setup-storage` again.
- **Battery:** processing is heavy on a phone. Plug in your charger for long jobs.
- **Keep Termux open:** Android may stop Termux in the background. Keep it on screen (or use Termux:Float) during long jobs.
- **Speed:** budget phones can be slow, especially for reverse, interpolation, batch compress and fix VFR. Test on short clips first.
- **Quality loss:** re-encoding lowers quality a little each time. Keep your original files.
- **Reverse video** loads the clip into memory. Long clips can crash low-RAM phones.
- **Upscale** resizes with a standard filter. It is not AI upscaling and does not add real detail.
- **Fast trim** snaps to the nearest keyframe, so the cut can be slightly off. Use frame-accurate mode when precision matters.
- **Watch folder mode** checks the folder every 5 seconds and drains battery. Stop it with `Ctrl+C`.
- **Download feature (yt-dlp):** only download content you own or have permission to use. You are responsible for following copyright law and each platform's terms of service.
- **Notifications** need the Termux:API app. Without it, messages print in the terminal instead.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ffmpeg not found` | `pkg install ffmpeg` |
| `yt-dlp not found` | `pkg install yt-dlp` |
| Notifications not showing | Install the Termux:API app, then `pkg install termux-api` |
| Output file not created | Include the extension in the name (`.mp4`, `.mp3`) |
| `fatal: detected dubious ownership` | Keep the repo in Termux's home folder, not in `/storage/...` |
| Colors look wrong | Run `NO_COLOR=1 python videotoolkit.py` |
| Clone is slow or drops | `git clone --depth=1 <repo-url>` |

## Contributing

Bug reports and pull requests are welcome. Please test on a real Termux install before submitting.

## License

MIT. See the `LICENSE` file.

---

Built by OLIØN.
