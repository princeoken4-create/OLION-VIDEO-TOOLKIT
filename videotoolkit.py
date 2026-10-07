#!/usr/bin/env python3
"""OLIØN Video Toolkit - a menu-driven FFmpeg toolkit for Termux (Android)."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time

# Change this one line if your phone's storage path is different.
SAVE_DIR = os.path.expanduser("~/storage/downloads")

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".avi", ".webm")

AUDIO_FORMATS = {
    "1": {"name": "MP3", "ext": "mp3", "args": ["-c:a", "libmp3lame", "-q:a", "2"]},
    "2": {"name": "WAV", "ext": "wav", "args": ["-c:a", "pcm_s16le"]},
    "3": {"name": "AAC", "ext": "aac", "args": ["-c:a", "aac", "-b:a", "192k"]},
    "4": {"name": "FLAC", "ext": "flac", "args": ["-c:a", "flac"]},
}

PROGRESS_RE = re.compile(r"^[A-Za-z_0-9]+=\S*$")
_filter_cache = {}


# ═══════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════

def check_tools():
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            print(f"❌ {tool} not found. Run: pkg install ffmpeg")
            raise SystemExit(1)


def notify(title, message):
    """Send an Android notification (needs termux-api), else just print."""
    if shutil.which("termux-notification"):
        try:
            subprocess.run(
                ["termux-notification", "--title", title, "--content", message],
                capture_output=True, timeout=5
            )
            return
        except (subprocess.TimeoutExpired, OSError):
            pass
    print(f"[{title}] {message}")


def wake_lock(on=True):
    """Keep the CPU awake during long jobs."""
    cmd = "termux-wake-lock" if on else "termux-wake-unlock"
    if shutil.which(cmd):
        subprocess.run([cmd], capture_output=True)


def probe(path):
    """Return (data, error). data is ffprobe's JSON as a dict."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", path],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        return None, r.stderr
    return json.loads(r.stdout), ""


def get_duration(path):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True
        )
        return float(r.stdout.strip())
    except (ValueError, OSError):
        return None


def has_audio(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
        capture_output=True, text=True
    )
    return bool(r.stdout.strip())


def get_sample_rate(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate", "-of", "csv=p=0", path],
        capture_output=True, text=True
    )
    try:
        return int(r.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return 44100


def has_filter(name):
    if name not in _filter_cache:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True, text=True
        )
        _filter_cache[name] = bool(re.search(rf"\b{name}\b", r.stdout))
    return _filter_cache[name]


def parse_time(text):
    """'00:01:30' or '90' -> seconds (float), or None if invalid."""
    try:
        parts = [float(p) for p in text.split(":")]
    except ValueError:
        return None
    seconds = 0.0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


def atempo_chain(tempo):
    """atempo only accepts 0.5-2.0, so chain several for bigger changes."""
    parts = []
    while tempo > 2.0:
        parts.append("atempo=2.0")
        tempo /= 2.0
    while tempo < 0.5:
        parts.append("atempo=0.5")
        tempo *= 2.0
    parts.append(f"atempo={tempo:.5f}")
    return ",".join(parts)


def input_of(cmd):
    try:
        return cmd[cmd.index("-i") + 1]
    except (ValueError, IndexError):
        return None


def run_ffmpeg(cmd, label="Processing", total=None):
    """Run ffmpeg with a live progress bar. Returns True on success."""
    if total is None:
        src = input_of(cmd)
        total = get_duration(src) if src else None

    full = [cmd[0], "-hide_banner", "-loglevel", "error",
            "-progress", "pipe:1", "-nostats"] + cmd[1:]

    print(f"\n🎬 {label}....")
    errors = []
    try:
        proc = subprocess.Popen(
            full, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
    except FileNotFoundError:
        print("❌ ffmpeg not found. Run: pkg install ffmpeg")
        return False

    try:
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("out_time_ms="):
                try:
                    us = int(line.split("=")[1])
                except ValueError:
                    continue
                if total:
                    pct = max(0.0, min(100.0, us / (total * 10000)))
                    filled = int(pct / 5)
                    bar = "🟩" * filled + "⬛" * (20 - filled)
                    print(f"\r[{bar}] {pct:5.1f}%", end="", flush=True)
            elif line and not PROGRESS_RE.match(line):
                errors.append(line)
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()
        print("\n⛔ Cancelled.")
        return False

    print()
    if proc.returncode != 0:
        print("❌ FFmpeg error:")
        for line in errors[-8:]:
            print("  ", line)
        return False
    return True


def ask_path(prompt="Enter video path: "):
    path = input(prompt).strip().strip("'\"")
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        print("❌ File not found")
        return None
    return path


def ask_filename(default, ext):
    """Ask for an output name; keep asking until it has the right extension."""
    ext = "." + ext.lstrip(".")
    name = input(f"Output filename [{default}]: ").strip()
    if not name:
        return default
    while not name.lower().endswith(ext):
        name = input(f"Please include '{ext}' (e.g. {default}): ").strip() or default
    return name


def ask_save_dir():
    folder = input(f"Save folder (blank = {SAVE_DIR}): ").strip()
    folder = os.path.expanduser(folder) if folder else SAVE_DIR
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as error:
        print("❌ Cannot use that folder:", error)
        return None
    return folder


def ask_number(prompt, positive=True):
    try:
        value = float(input(prompt).strip())
    except ValueError:
        print("❌ Please enter a number")
        return None
    if positive and value <= 0:
        print("❌ The number must be greater than 0")
        return None
    return value


def finish(ok, output, success_text="Done!"):
    if ok:
        print(f"\n✅ {success_text}")
        print("Saved as:", output)
    else:
        print("\n❌ Failed")


def fps_text(rate):
    try:
        num, den = rate.split("/")
        return f"{float(num) / float(den):.2f}"
    except (ValueError, ZeroDivisionError, AttributeError):
        return str(rate)


# ═══════════════════════════════════════════
#  FEATURES 1-8
# ═══════════════════════════════════════════

def video_info():
    video = ask_path()
    if not video:
        return
    data, error = probe(video)
    if data is None:
        print("❌ ffprobe error:")
        print(error)
        return

    video_stream = audio_stream = None
    for stream in data.get("streams", []):
        kind = stream.get("codec_type")
        if kind == "video" and video_stream is None:
            video_stream = stream
        elif kind == "audio" and audio_stream is None:
            audio_stream = stream

    fmt = data.get("format", {})
    print("\n======= VIDEO INFORMATION =======")
    try:
        print("Duration:", round(float(fmt["duration"]), 2), "seconds")
    except (KeyError, ValueError):
        print("Duration: unknown")
    try:
        print("File size:", round(int(fmt["size"]) / (1024 * 1024), 2), "MB")
    except (KeyError, ValueError):
        pass

    if video_stream:
        print("Resolution:", video_stream.get("width"), "x", video_stream.get("height"))
        print("FPS:", fps_text(video_stream.get("r_frame_rate")))
        print("Video codec:", video_stream.get("codec_name"))
    else:
        print("Video: None")

    if audio_stream:
        print("Audio codec:", audio_stream.get("codec_name"))
    else:
        print("Audio: None")


def trim_video():
    video = ask_path()
    if not video:
        return
    start = input("Start time (e.g. 00:00:10): ").strip()
    end = input("End time (e.g. 00:00:20): ").strip()
    start_s, end_s = parse_time(start), parse_time(end)
    if start_s is None or end_s is None or end_s <= start_s:
        print("❌ Invalid times. End must be after start.")
        return

    name = ask_filename("trimmed.mp4", "mp4")
    out_dir = ask_save_dir()
    if not out_dir:
        return
    output = os.path.join(out_dir, name)

    precise = input("Frame-accurate cut? Slower (y/n) [n]: ").strip().lower() == "y"
    if precise:
        codec = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                 "-c:a", "aac", "-b:a", "192k"]
    else:
        codec = ["-c", "copy"]

    cmd = ["ffmpeg", "-y", "-ss", start, "-to", end, "-i", video, *codec, output]
    ok = run_ffmpeg(cmd, "Trimming", total=end_s - start_s)
    finish(ok, output, "Video trimmed successfully!")
    if ok and not precise:
        print("Tip: fast mode snaps to the nearest keyframe, so the cut can be a bit off.")


def extract_audio():
    video = ask_path()
    if not video:
        return
    print("\nAUDIO FORMAT")
    print("==============")
    for key, fmt in AUDIO_FORMATS.items():
        print(f"{key}. {fmt['name']}")
    choice = input("\nChoose an option: ").strip()
    if choice not in AUDIO_FORMATS:
        print("❌ Invalid audio format")
        return
    fmt = AUDIO_FORMATS[choice]

    name = ask_filename(f"extracted_audio.{fmt['ext']}", fmt["ext"])
    out_dir = ask_save_dir()
    if not out_dir:
        return
    output = os.path.join(out_dir, name)

    cmd = ["ffmpeg", "-y", "-i", video, "-vn", *fmt["args"], output]
    ok = run_ffmpeg(cmd, "Extracting audio")
    finish(ok, output, "Audio extracted successfully!")


def change_speed():
    video = ask_path()
    if not video:
        return
    speed = ask_number("Speed factor (2 = twice as fast, 0.5 = half speed): ")
    if speed is None:
        return
    name = ask_filename("speed_changed.mp4", "mp4")
    out_dir = ask_save_dir()
    if not out_dir:
        return
    output = os.path.join(out_dir, name)

    pts = f"setpts={1 / speed:.6f}*PTS"
    encode = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    if has_audio(video):
        cmd = ["ffmpeg", "-y", "-i", video,
               "-filter_complex", f"[0:v]{pts}[v];[0:a]{atempo_chain(speed)}[a]",
               "-map", "[v]", "-map", "[a]", *encode, "-c:a", "aac", output]
    else:
        cmd = ["ffmpeg", "-y", "-i", video, "-vf", pts, *encode, "-an", output]

    duration = get_duration(video)
    total = duration / speed if duration else None
    ok = run_ffmpeg(cmd, "Changing speed", total=total)
    finish(ok, output, "Speed changed successfully!")


def reverse_video():
    video = ask_path()
    if not video:
        return
    name = ask_filename("reversed_video.mp4", "mp4")
    out_dir = ask_save_dir()
    if not out_dir:
        return
    output = os.path.join(out_dir, name)

    print("⚠️ Reverse loads the whole clip into memory. Use short clips on a phone.")
    encode = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    if has_audio(video):
        cmd = ["ffmpeg", "-y", "-i", video, "-vf", "reverse", "-af", "areverse",
               *encode, "-c:a", "aac", output]
    else:
        cmd = ["ffmpeg", "-y", "-i", video, "-vf", "reverse", *encode, "-an", output]

    ok = run_ffmpeg(cmd, "Reversing video")
    finish(ok, output, "Video reversed successfully!")


def interpolate_video():
    video = ask_path()
    if not video:
        return
    print("\nVIDEO INTERPOLATION")
    print("=====================")
    print("1. 60 fps")
    print("2. 120 fps")
    choice = input("\nChoose an option: ").strip()
    if choice == "1":
        target_fps = 60
    elif choice == "2":
        target_fps = 120
    else:
        print("❌ Invalid interpolation option")
        return

    name = ask_filename("interpolated.mp4", "mp4")
    out_dir = ask_save_dir()
    if not out_dir:
        return
    output = os.path.join(out_dir, name)

    print("⚠️ This is very heavy on a phone. Try a short clip first.")
    cmd = ["ffmpeg", "-y", "-i", video,
           "-vf", (f"minterpolate=fps={target_fps}:mi_mode=mci:"
                   "mc_mode=aobmc:me_mode=bidir:vsbmc=1"),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-c:a", "copy", output]
    ok = run_ffmpeg(cmd, f"Interpolating to {target_fps} FPS")
    finish(ok, output, "Interpolation complete!")


def upscale_video():
    video = ask_path()
    if not video:
        return
    print("\nUPSCALE VIDEO")
    print("===============")
    print("1. 2x size")
    print("2. 1080p")
    print("3. 1440p (2K)")
    print("4. 2160p (4K)")
    choice = input("\nChoose an option: ").strip()
    filters = {
        "1": "scale=iw*2:ih*2:flags=lanczos",
        "2": "scale=-2:1080:flags=lanczos",
        "3": "scale=-2:1440:flags=lanczos",
        "4": "scale=-2:2160:flags=lanczos",
    }
    if choice not in filters:
        print("❌ Invalid option")
        return

    name = ask_filename("upscaled.mp4", "mp4")
    out_dir = ask_save_dir()
    if not out_dir:
        return
    output = os.path.join(out_dir, name)

    print("ℹ️ This resizes with the Lanczos filter. It is not AI upscaling.")
    cmd = ["ffmpeg", "-y", "-i", video, "-vf", filters[choice],
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-c:a", "copy", output]
    ok = run_ffmpeg(cmd, "Upscaling")
    finish(ok, output, "Upscale complete!")


def audio_changer():
    src = ask_path("Enter audio or video path: ")
    if not src:
        return
    if not has_audio(src):
        print("❌ No audio found in that file")
        return

    print("\nOUTPUT FORMAT")
    print("===============")
    for key, fmt in AUDIO_FORMATS.items():
        print(f"{key}. {fmt['name']}")
    choice = input("\nChoose an option: ").strip()
    if choice not in AUDIO_FORMATS:
        print("❌ Invalid output format")
        return
    fmt = AUDIO_FORMATS[choice]

    print("\nAUDIO CHANGER")
    print("===============")
    print("1. Change speed, keep the pitch")
    print("2. Change speed, pitch follows speed (vinyl style)")
    print("3. Change pitch only (semitones)")
    mode = input("\nChoose an option: ").strip()

    sample_rate = get_sample_rate(src)
    duration = get_duration(src)
    total = duration

    if mode in ("1", "2"):
        speed = ask_number("Speed factor (e.g. 1.25 or 0.8): ")
        if speed is None:
            return
        if duration:
            total = duration / speed
        if mode == "1":
            if has_filter("rubberband"):
                audio_filter = f"rubberband=tempo={speed}"
            else:
                audio_filter = atempo_chain(speed)
        else:
            audio_filter = f"asetrate={int(sample_rate * speed)},aresample={sample_rate}"
    elif mode == "3":
        semitones = ask_number("Pitch shift in semitones (e.g. 2 or -3): ", positive=False)
        if semitones is None:
            return
        ratio = 2 ** (semitones / 12)
        if has_filter("rubberband"):
            audio_filter = f"rubberband=pitch={ratio:.5f}"
        else:
            audio_filter = (f"asetrate={int(sample_rate * ratio)},"
                            f"aresample={sample_rate},{atempo_chain(1 / ratio)}")
    else:
        print("❌ Invalid option")
        return

    name = ask_filename(f"audio_changed.{fmt['ext']}", fmt["ext"])
    out_dir = ask_save_dir()
    if not out_dir:
        return
    output = os.path.join(out_dir, name)

    # -vn drops embedded cover art, which otherwise confuses ffmpeg.
    cmd = ["ffmpeg", "-y", "-i", src, "-vn", "-map", "0:a:0",
           "-af", audio_filter, *fmt["args"], output]
    ok = run_ffmpeg(cmd, "Changing audio", total=total)
    finish(ok, output, "Audio changed successfully!")


# ═══════════════════════════════════════════
#  FEATURE 9 - Download + process (yt-dlp)
# ═══════════════════════════════════════════

def download_and_process():
    if not shutil.which("yt-dlp"):
        print("❌ yt-dlp not found. Run: pkg install yt-dlp")
        return

    print("\n📥 DOWNLOAD + PROCESS")
    print("Only download content you own or have permission to use.")
    url = input("Paste URL: ").strip()
    if not url:
        return

    print("\nWhat next?")
    print("1. Just download")
    print("2. Download + extract audio (mp3)")
    print("3. Download + compress video")
    mode = input("Choose: ").strip()
    if mode not in ("1", "2", "3"):
        print("❌ Invalid option")
        return

    os.makedirs(SAVE_DIR, exist_ok=True)
    template = os.path.join(SAVE_DIR, "%(title)s.%(ext)s")

    # yt-dlp writes the final file path here, so we never guess "latest file".
    handle, path_file = tempfile.mkstemp(suffix=".txt")
    os.close(handle)

    dl = ["yt-dlp", "-o", template, "--print-to-file", "after_move:filepath", path_file]
    if mode == "2":
        dl += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]

    print("\n⬇️ Downloading....")
    wake_lock(True)
    try:
        code = subprocess.run(dl + [url]).returncode
    except KeyboardInterrupt:
        print("\n⛔ Cancelled.")
        code = 1
    finally:
        wake_lock(False)

    downloaded = None
    try:
        with open(path_file) as f:
            lines = [line.strip() for line in f if line.strip()]
        if lines:
            downloaded = lines[-1]
    except OSError:
        pass
    finally:
        try:
            os.remove(path_file)
        except OSError:
            pass

    if code != 0:
        print("❌ Download failed")
        return
    if not downloaded or not os.path.isfile(downloaded):
        print("✅ Downloaded to:", SAVE_DIR)
        notify("OLIØN", "Download complete")
        return

    print("✅ Downloaded:", downloaded)
    if mode in ("1", "2"):
        notify("OLIØN", "Download complete")
        return

    crf = input("CRF (18=high quality, 28=small) [23]: ").strip() or "23"
    out = os.path.splitext(downloaded)[0] + "_compressed.mp4"
    cmd = ["ffmpeg", "-y", "-i", downloaded,
           "-c:v", "libx264", "-crf", crf, "-preset", "veryfast",
           "-c:a", "aac", "-b:a", "128k", out]
    wake_lock(True)
    ok = run_ffmpeg(cmd, "Compressing")
    wake_lock(False)
    finish(ok, out, "Compressed!")
    if ok:
        notify("OLIØN", "Job complete")


# ═══════════════════════════════════════════
#  FEATURE 10 - Batch compress folder
# ═══════════════════════════════════════════

def batch_compress():
    print("\n📦 BATCH COMPRESS")
    folder = input("Folder path (e.g. ~/storage/downloads): ").strip().strip("'\"")
    folder = os.path.expanduser(folder)
    if not os.path.isdir(folder):
        print("❌ Folder not found")
        return

    crf = input("CRF (18-28, higher = smaller) [23]: ").strip() or "23"

    videos = sorted(f for f in os.listdir(folder) if f.lower().endswith(VIDEO_EXTS))
    if not videos:
        print("No videos in that folder.")
        return

    print(f"\nFound {len(videos)} videos.")
    if input("Continue? (y/n): ").strip().lower() != "y":
        return

    out_dir = os.path.join(folder, "compressed")
    os.makedirs(out_dir, exist_ok=True)

    done = failed = 0
    wake_lock(True)
    try:
        for i, name in enumerate(videos, 1):
            src = os.path.join(folder, name)
            dst = os.path.join(out_dir, os.path.splitext(name)[0] + ".mp4")

            if os.path.exists(dst):
                print(f"[{i}/{len(videos)}] ⏩ Skipping (exists): {name}")
                continue

            print(f"\n[{i}/{len(videos)}] {name}")
            cmd = ["ffmpeg", "-y", "-i", src,
                   "-c:v", "libx264", "-crf", crf, "-preset", "veryfast",
                   "-c:a", "aac", "-b:a", "128k", dst]
            if run_ffmpeg(cmd, "Compressing"):
                done += 1
            else:
                failed += 1
    finally:
        wake_lock(False)

    print(f"\n🎉 All done. {done} compressed, {failed} failed.")
    print("Output:", out_dir)
    notify("OLIØN", f"Batch done: {done} compressed")


# ═══════════════════════════════════════════
#  FEATURE 11 - Watch folder mode
# ═══════════════════════════════════════════

def wait_until_stable(path, tries=60):
    """Wait until a file stops growing, so we don't touch half-copied files."""
    last = -1
    for _ in range(tries):
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size == last and size > 0:
            return True
        last = size
        time.sleep(2)
    return False


def watch_folder():
    print("\n👀 WATCH FOLDER MODE")
    src = input("Watch folder: ").strip().strip("'\"")
    src = os.path.expanduser(src)
    if not os.path.isdir(src):
        print("❌ Not a folder")
        return

    dst = os.path.join(src, "processed")
    os.makedirs(dst, exist_ok=True)
    crf = input("CRF [23]: ").strip() or "23"

    print(f"\n👀 Watching {src}")
    print("   New videos get compressed into /processed")
    print("   Press Ctrl+C to stop.\n")

    seen = set(os.listdir(src))
    wake_lock(True)
    try:
        while True:
            time.sleep(5)
            current = set(os.listdir(src))
            new = current - seen
            seen = current

            for name in sorted(new):
                if not name.lower().endswith(VIDEO_EXTS):
                    continue
                src_file = os.path.join(src, name)
                dst_file = os.path.join(dst, os.path.splitext(name)[0] + ".mp4")

                if not wait_until_stable(src_file):
                    print(f"⚠️ Skipped (file not ready): {name}")
                    continue

                print(f"⚙️ Processing: {name}")
                cmd = ["ffmpeg", "-y", "-i", src_file,
                       "-c:v", "libx264", "-crf", crf, "-preset", "veryfast",
                       "-c:a", "aac", dst_file]
                if run_ffmpeg(cmd, "Compressing"):
                    print(f"   ✅ {name}")
                    notify("OLIØN", f"Done: {name}")
                else:
                    print(f"   ❌ Failed: {name}")
    except KeyboardInterrupt:
        print("\n👋 Watch mode stopped.")
    finally:
        wake_lock(False)


# ═══════════════════════════════════════════
#  FEATURE 12 - Fix VFR (audio sync)
# ═══════════════════════════════════════════

def fix_vfr():
    print("\n🔧 FIX VARIABLE FRAME RATE")
    print("(Fixes audio drift / desync from phone recordings)")
    video = ask_path("Video path: ")
    if not video:
        return

    fps = input("Target FPS [30]: ").strip() or "30"
    try:
        if float(fps) <= 0:
            raise ValueError
    except ValueError:
        print("❌ FPS must be a positive number")
        return

    name = ask_filename("fixed.mp4", "mp4")
    out_dir = ask_save_dir()
    if not out_dir:
        return
    output = os.path.join(out_dir, name)

    cmd = ["ffmpeg", "-y", "-i", video,
           "-fps_mode", "cfr", "-r", fps,
           "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
           "-c:a", "aac", "-b:a", "192k", output]
    wake_lock(True)
    ok = run_ffmpeg(cmd, "Re-encoding to constant frame rate")
    wake_lock(False)
    finish(ok, output, "VFR fixed!")
    if ok:
        notify("OLIØN", "VFR fixed")


# ═══════════════════════════════════════════
#  MENU
# ═══════════════════════════════════════════

MENU = [
    ("1", "Get video information ℹ️", video_info),
    ("2", "Trim video ✂️", trim_video),
    ("3", "Extract audio 🎵", extract_audio),
    ("4", "Change video speed 🚄", change_speed),
    ("5", "Reverse video ⏪", reverse_video),
    ("6", "Video interpolation 🎞️", interpolate_video),
    ("7", "Upscale quality 📈", upscale_video),
    ("8", "Audio changer 🎧", audio_changer),
    ("9", "Download + process (yt-dlp) 📥", download_and_process),
    ("10", "Batch compress folder 📦", batch_compress),
    ("11", "Watch folder mode 👀", watch_folder),
    ("12", "Fix VFR (audio sync) 🔧", fix_vfr),
]
ACTIONS = {key: action for key, _, action in MENU}


def main():
    check_tools()
    while True:
        print("\nOLIØN VIDEO TOOLKIT")
        print("=====================")
        for key, label, _ in MENU:
            print(f"{key}. {label}")
        print("0. Exit")

        choice = input("\nPut your option: ").strip()
        if choice == "0":
            print("Goodbye 👋")
            break
        action = ACTIONS.get(choice)
        if action is None:
            print("❌ Invalid option")
            continue
        try:
            action()
        except KeyboardInterrupt:
            print("\n⛔ Cancelled.")


if __name__ == "__main__":
    main()
