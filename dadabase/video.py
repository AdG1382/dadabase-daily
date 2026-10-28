"""Builds the Short / Reel: voiceover of setup, pause, punchline, then a ba-dum-tss."""
import asyncio
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

from . import config, render
from .queue import Joke

SR = 44100


def _write_wav(path: Path, samples: np.ndarray) -> None:
    samples = np.clip(samples, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((samples * 32767).astype(np.int16).tobytes())


def rimshot(path: Path) -> Path:
    """Synthesised ba-dum-tss (no samples, so nothing to license)."""
    if path.exists():
        return path
    rng = np.random.default_rng(7)
    total = np.zeros(int(SR * 1.6))

    def place(sig, at):
        i = int(at * SR)
        total[i:i + len(sig)] += sig[: len(total) - i]

    t = np.arange(int(SR * 0.25)) / SR
    snare = (rng.normal(0, 1, len(t)) * 0.55 + np.sin(2 * np.pi * 190 * t) * 0.6) * np.exp(-t * 28)
    t2 = np.arange(int(SR * 0.35)) / SR
    tom = np.sin(2 * np.pi * (140 - 60 * t2) * t2) * np.exp(-t2 * 11)
    t3 = np.arange(int(SR * 1.2)) / SR
    noise = rng.normal(0, 1, len(t3))
    hiss = np.diff(np.diff(noise, prepend=0), prepend=0) * 0.25   # crude high-pass for a cymbal
    cymbal = hiss * np.exp(-t3 * 3.2)
    place(snare * 0.8, 0.0)
    place(tom * 0.9, 0.17)
    place(cymbal * 0.9, 0.36)
    place(snare * 0.5, 0.36)
    _write_wav(path, total / np.max(np.abs(total)) * 0.85)
    return path


def silence(path: Path, seconds: float) -> Path:
    _write_wav(path, np.zeros(int(SR * seconds)))
    return path


async def _tts(text: str, path: Path, voice: str) -> None:
    import edge_tts  # installed in GitHub Actions; optional locally
    await edge_tts.Communicate(text, voice, rate="-5%").save(str(path))


def tts(text: str, path: Path) -> Path | None:
    """Neural voiceover. Returns None if the voice service is unavailable (video still works)."""
    try:
        asyncio.run(_tts(text, path, config.TTS_VOICE))
        return path if path.exists() and path.stat().st_size > 1000 else None
    except Exception as e:  # noqa: BLE001
        print(f"  voiceover unavailable ({type(e).__name__}); making a silent-voice video")
        return None


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def make_short(joke: Joke, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    work = config.WORK / joke.id
    work.mkdir(parents=True, exist_ok=True)
    f1, f2 = render.video_frames(joke, work)

    setup_audio = tts(joke.setup, work / "setup.mp3") or silence(work / "setup.wav", 3.2)
    punch_audio = tts(joke.punchline, work / "punch.mp3") or silence(work / "punch.wav", 1.8)
    pause = silence(work / "pause.wav", 0.9)
    gap = silence(work / "gap.wav", 0.15)
    tail = silence(work / "tail.wav", 1.0)
    drum = rimshot(config.WORK / "rimshot.wav")

    d_setup = duration(setup_audio) + 0.9
    d_rest = duration(punch_audio) + 0.15 + duration(drum) + 1.0

    out = out_dir / f"{joke.id}.mp4"
    audio_parts = [setup_audio, pause, punch_audio, gap, drum, tail]
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-loop", "1", "-t", f"{d_setup:.2f}", "-i", str(f1),
           "-loop", "1", "-t", f"{d_rest:.2f}", "-i", str(f2)]
    for a in audio_parts:
        cmd += ["-i", str(a)]
    n = len(audio_parts)
    audio_in = "".join(f"[{i + 2}:a]aresample={SR},aformat=channel_layouts=mono[a{i}];" for i in range(n))
    filt = (
        "[0:v]scale=1080:1920,setsar=1,fps=30[v0];[1:v]scale=1080:1920,setsar=1,fps=30[v1];"
        "[v0][v1]concat=n=2:v=1:a=0,format=yuv420p[v];"
        + audio_in + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    )
    cmd += ["-filter_complex", filt, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-ar", str(SR), "-ac", "2",
            "-movflags", "+faststart", "-shortest", str(out)]
    subprocess.run(cmd, check=True)
    return out
