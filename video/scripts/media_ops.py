"""FFmpeg operations shared by the REELINATOR CLI and its integration tests."""
from __future__ import annotations

from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave


REPO = Path(__file__).resolve().parents[2]
PREPARE_VERSION = 3


def tool(name: str) -> str:
    override = os.environ.get(name.upper().replace("-", "_"))
    if override:
        candidate = shutil.which(override) or override
        if not Path(candidate).is_file():
            raise FileNotFoundError(f"{name.upper()} does not point to a file: {candidate}")
        return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    suffix = ".exe" if os.name == "nt" else ""
    candidates = sorted((REPO / ".tools" / "ffmpeg").glob(f"**/bin/{name}{suffix}"))
    if candidates:
        return str(candidates[-1])
    raise FileNotFoundError(f"Install {name} on PATH or set {name.upper()} to its executable")


def run(args, **kwargs) -> subprocess.CompletedProcess:
    options = {"check": True, "capture_output": True, "text": True,
               "encoding": "utf-8", "errors": "replace"}
    options.update(kwargs)
    return subprocess.run([str(a) for a in args], **options)


def probe(path) -> dict:
    return json.loads(run([tool("ffprobe"), "-v", "error", "-show_streams",
                           "-show_format", "-of", "json", path]).stdout)


def digest(path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     suffix=".tmp", delete=False) as stream:
        tmp = Path(stream.name)
        try:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        except BaseException:
            stream.close()
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return float(value)


def validate_edit(edit: dict, source_duration: float) -> list[list[float]]:
    if not isinstance(edit, dict):
        raise ValueError("edit.json must be an object")
    source_duration = _number(source_duration, "source duration", positive=True)
    _number(edit.get("speed", 1), "speed", positive=True)
    if edit.get("fit", "contain") not in ("contain", "cover"):
        raise ValueError("fit must be contain or cover")
    keeps = edit.get("keeps", [[0, source_duration]])
    if not isinstance(keeps, list) or not keeps:
        raise ValueError("keeps must contain at least one source interval")
    out = []
    previous = 0.0
    for pair in keeps:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("Each keep must be [start_seconds, end_seconds]")
        a, b = (_number(v, "keep boundary") for v in pair)
        if a < 0 or a < previous or b <= a or b > source_duration + 0.001:
            raise ValueError("Keep intervals must be ordered, non-overlapping and inside the source")
        b = min(b, source_duration)
        out.append([a, b])
        previous = b
    return out


def _words(words):
    if not isinstance(words, list):
        raise ValueError("transcript.json must be a list of words")
    previous = -1.0
    for word in words:
        if not isinstance(word, dict) or not isinstance(word.get("w"), str) or not word["w"].strip():
            raise ValueError("Each transcript word needs nonempty w text")
        a = _number(word.get("s"), "word start")
        b = _number(word.get("e"), "word end")
        if a < 0 or b <= a or a < previous:
            raise ValueError("Transcript words must have ordered, positive time intervals")
        if word.get("em", 1) not in (0, 1, 2):
            raise ValueError("Word emphasis em must be 0, 1 or 2")
        previous = a
    return words


def map_captions(words, keeps, speed) -> list[dict]:
    """Retain complete words; a cut through a word needs an editorial correction."""
    speed = _number(speed, "speed", positive=True)
    words = _words(words)
    result, elapsed = [], 0.0
    for a, b in keeps:
        for word in words:
            start, end = word["s"], word["e"]
            if start >= b or end <= a:
                continue
            if start < a - 0.001 or end > b + 0.001:
                raise ValueError(f"Cut crosses spoken word {word['w']!r} ({start}-{end}s); move the cut or correct transcript")
            result.append({**word, "em": word.get("em", 1),
                           "s": round((elapsed + max(a, start) - a) / speed, 6),
                           "e": round((elapsed + min(b, end) - a) / speed, 6)})
        elapsed += b - a
    return result


def _duration(info):
    value = info.get("format", {}).get("duration")
    if value is None:
        values = [float(s["duration"]) for s in info.get("streams", []) if s.get("duration")]
        value = max(values) if values else 0
    return _number(float(value), "source duration", positive=True)


def suggest_keeps(source, cache, squeeze_over=.65, keep_pause=.30) -> list[list[float]]:
    """Draft silence cuts using upstream's low-threshold consonant-tail refinement."""
    _number(squeeze_over, "squeeze_over", positive=True)
    _number(keep_pause, "keep_pause", positive=True)
    info = probe(source)
    duration = _duration(info)
    if not any(s["codec_type"] == "audio" for s in info["streams"]):
        return [[0.0, duration]]
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="silence-", dir=cache) as temp:
        wav = Path(temp) / "source.wav"
        run([tool("ffmpeg"), "-v", "error", "-i", source, "-vn", "-ac", "1", "-ar", "16000",
             "-af", "aresample=16000:async=1:first_pts=0",
             "-c:a", "pcm_s16le", "-y", wav])
        with wave.open(str(wav), "rb") as audio:
            samples = array("h", audio.readframes(audio.getnframes()))
            if sys.byteorder != "little":
                samples.byteswap()
        window = .02
        envelope = []
        for start in range(0, len(samples), 320):
            part = samples[start:start + 320]
            rms = math.sqrt(sum(v * v for v in part) / len(part)) / 32768
            envelope.append(20 * math.log10(rms) if rms > 1e-9 else -120)
        # Full silence has no editorial signal. Preserve it instead of inventing a tiny clip.
        if not envelope or max(envelope) < -55:
            return [[0.0, duration]]
        stderr = run([tool("ffmpeg"), "-hide_banner", "-nostats", "-i", wav,
                      "-af", "silencedetect=n=-34dB:d=0.3", "-f", "null", "-"]).stderr
    gaps, opening = [], None
    for match in re.finditer(r"silence_(start|end): ([\d.]+)", stderr):
        if match[1] == "start":
            opening = float(match[2])
        elif opening is not None:
            gaps.append((opening, min(float(match[2]), duration)))
            opening = None
    if opening is not None:
        gaps.append((opening, duration))

    def quiet(t):
        index = int(t / window)
        return 0 <= index < len(envelope) and envelope[index] < -55

    def true_start(a, b):
        while a < b and not quiet(a):
            a += window
        return min(a, b)

    def true_end(a, b):
        while b > a and not quiet(b - window):
            b -= window
        return max(a, b)

    head = max(0, true_end(*gaps[0]) - .25) if gaps and gaps[0][0] < .05 else 0
    tail = min(duration, true_start(*gaps[-1]) + .25) if gaps and gaps[-1][1] > duration - .05 else duration
    drops = [(0, head), (tail, duration)]
    for a, b in gaps:
        if a < head or b > tail:
            continue
        a, b = true_start(a, b), true_end(a, b)
        if b - a > squeeze_over:
            lo, hi = a + .08 + keep_pause / 2, b - .08 - keep_pause / 2
            if hi - lo > .05:
                drops.append((lo, hi))
    keeps, cursor = [], 0.0
    for a, b in sorted(drops):
        if a > cursor:
            keeps.append([round(cursor, 6), round(a, 6)])
        cursor = max(cursor, b)
    if cursor < duration:
        keeps.append([round(cursor, 6), duration])
    return keeps or [[0.0, duration]]


def _tempo(speed):
    filters = []
    while speed < .5:
        filters.append("atempo=0.5")
        speed *= 2
    while speed > 2:
        filters.append("atempo=2")
        speed /= 2
    filters.append(f"atempo={speed:.12g}")
    return ",".join(filters)


def _config(config):
    fps = _number(config.get("fps"), "fps", positive=True)
    for key in ("width", "height"):
        value = config.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value % 2:
            raise ValueError(f"{key} must be a positive even integer for H264")
    return fps, config["width"], config["height"]


def prepare(project_dir, config) -> dict:
    project = Path(project_dir).resolve()
    fps, width, height = _config(config)
    edit_file = project / "edit.json"
    if not edit_file.exists():
        frames = config.get("durationInFrames")
        if isinstance(frames, bool) or not isinstance(frames, int) or frames < 1:
            raise ValueError("durationInFrames must be a positive integer")
        media = {"durationInFrames": frames, "video": None, "audio": None,
                 "captions": [], "splices": [], "fingerprint": None}
        atomic_json(project / "media.json", media)
        return media
    edit = json.loads(edit_file.read_text(encoding="utf-8"))
    if not isinstance(edit, dict) or not isinstance(edit.get("source"), str):
        raise ValueError("edit.json needs a relative source path under public/")
    public = (project / "public").resolve()
    source = (public / edit["source"]).resolve()
    if not source.is_relative_to(public) or not source.is_file():
        raise ValueError("Source must be an existing file inside this project's public directory")
    info = probe(source)
    keeps = validate_edit(edit, _duration(info))
    speed = float(edit.get("speed", 1))
    transcript_file = project / "transcript.json"
    transcript = json.loads(transcript_file.read_text(encoding="utf-8")) if transcript_file.exists() else []
    captions = map_captions(transcript, keeps, speed)
    seconds = sum(b - a for a, b in keeps) / speed
    frames = max(1, math.ceil(seconds * fps - 1e-7))
    duration = frames / fps
    elapsed, splices = 0.0, []
    for a, b in keeps[:-1]:
        elapsed += (b - a) / speed
        splices.append(round(elapsed * fps))
    edges = [0, *splices, frames]
    budgets = [end - start for start, end in zip(edges, edges[1:])]
    has_video = any(s["codec_type"] == "video" for s in info["streams"])
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    if not has_video and not has_audio:
        raise ValueError("Source contains neither video nor audio")
    if has_video and any(budget < 1 for budget in budgets):
        raise ValueError("A selected video interval has zero output frames; lengthen it or reduce speed")
    identity = {"version": PREPARE_VERSION, "source": digest(source), "edit": edit,
                "format": [fps, width, height], "transcript": transcript}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()
    relative = Path("prepared") / fingerprint
    destination = public / relative
    cache_manifest = destination / "ready.json"
    if cache_manifest.exists():
        saved = json.loads(cache_manifest.read_text(encoding="utf-8"))
        outputs = saved.get("outputs", {})
        if outputs and all((destination / p).is_file() and digest(destination / p) == sha
                           for p, sha in outputs.items()):
            atomic_json(project / "media.json", saved["media"])
            return saved["media"]
    cache = project / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="prepare-", dir=cache) as temp:
        temp = Path(temp)
        outputs = []
        if has_video:
            # Budget against cumulative output time: rounding every source trim independently
            # accumulates drift and lets the final global trim remove the last selected scene.
            # Keep source timestamps relative to the cut, including a later stream start.
            # fps pads the missing beginning with the first picture, without moving it earlier.
            filters = [f"[0:v:0]trim=start={a:.9f}:end={b:.9f},setpts=(PTS-{a:.9f}/TB)/{speed:.12g},"
                       f"fps={fps:.12g}:start_time=0,tpad=stop_mode=clone:stop={budgets[i]},"
                       f"trim=end_frame={budgets[i]},setpts=PTS-STARTPTS[v{i}]"
                       for i, (a, b) in enumerate(keeps)]
            concat = "".join(f"[v{i}]" for i in range(len(keeps)))
            fit = (f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
                   if edit.get("fit", "contain") == "cover" else
                   f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2")
            filters.append(f"{concat}concat=n={len(keeps)}:v=1:a=0,{fit},setsar=1[v]")
            graph = temp / "video-filter.txt"
            graph.write_text(";".join(filters), encoding="utf-8")
            picture = temp / "picture.mp4"
            run([tool("ffmpeg"), "-v", "error", "-i", source, "-/filter_complex", graph,
                 "-map", "[v]", "-an", "-frames:v", frames, "-c:v", "libx264", "-preset", "fast",
                 "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", picture])
            outputs.append(picture)
        if has_audio:
            # Materialize source-time gaps as silence before cutting. Resetting each stream's
            # first PTS independently would erase their original synchronization.
            filters = [f"[0:a:0]aresample=48000:async=1:first_pts=0,apad=whole_dur={_duration(info):.9f},"
                       f"atrim=start={a:.9f}:end={b:.9f},asetpts=PTS-STARTPTS[a{i}]"
                       for i, (a, b) in enumerate(keeps)]
            concat = "".join(f"[a{i}]" for i in range(len(keeps)))
            filters.append(f"{concat}concat=n={len(keeps)}:v=0:a=1,{_tempo(speed)},"
                           f"aresample=48000,apad,atrim=duration={duration:.9f}[a]")
            graph = temp / "audio-filter.txt"
            graph.write_text(";".join(filters), encoding="utf-8")
            sound = temp / "sound.wav"
            run([tool("ffmpeg"), "-v", "error", "-i", source, "-/filter_complex", graph,
                 "-map", "[a]", "-vn", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", "-y", sound])
            outputs.append(sound)
        media = {"durationInFrames": frames,
                 "video": (relative / "picture.mp4").as_posix() if has_video else None,
                 "audio": (relative / "sound.wav").as_posix() if has_audio else None,
                 "captions": captions, "splices": splices, "fingerprint": fingerprint}
        hashes = {p.name: digest(p) for p in outputs}
        destination.mkdir(parents=True, exist_ok=True)
        for path in outputs:
            os.replace(path, destination / path.name)
        atomic_json(cache_manifest, {"media": media, "outputs": hashes})
    atomic_json(project / "media.json", media)
    return media


def _measure(path, target=-14):
    stderr = run([tool("ffmpeg"), "-hide_banner", "-nostats", "-i", path, "-vn",
                  "-af", f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    matches = re.findall(r'\{\s*"input_i".*?\}', stderr, re.S)
    if not matches:
        raise ValueError("FFmpeg returned no loudnorm measurement")
    return json.loads(matches[-1])


def _loudnorm_filter(measured, target):
    target = _number(target, "loudness target")
    if not -70 <= target <= -5:
        raise ValueError("loudness target must be between -70 and -5 LUFS")
    if measured.get("input_i") == "-inf" and measured.get("input_tp") == "-inf":
        return "anull"
    keys = ("input_i", "input_lra", "input_tp", "input_thresh", "target_offset")
    try:
        values = {key: float(measured[key]) for key in keys}
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("Incomplete loudnorm measurement") from exc
    if not all(math.isfinite(v) for v in values.values()):
        raise ValueError("Non-finite loudnorm measurement")
    return (f"loudnorm=I={target}:TP=-1.5:LRA=11:linear=true:measured_I={values['input_i']}:"
            f"measured_LRA={values['input_lra']}:measured_TP={values['input_tp']}:"
            f"measured_thresh={values['input_thresh']}:offset={values['target_offset']}")


def normalize_mux(picture, wav_or_none, dest, target=-14):
    """Publish only a successful faststart master, with exactly one AAC encode."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Validate before measuring: invalid targets should not launch an FFmpeg process.
    _loudnorm_filter({"input_i": "-inf", "input_tp": "-inf"}, target)
    with tempfile.TemporaryDirectory(prefix="master-", dir=dest.parent) as temp:
        candidate = Path(temp) / "master.mp4"
        args = [tool("ffmpeg"), "-v", "error", "-i", picture]
        if wav_or_none is not None:
            audio_filter = _loudnorm_filter(_measure(wav_or_none, target), target)
            args += ["-i", wav_or_none, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                     "-af", audio_filter, "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        else:
            args += ["-map", "0:v:0", "-an", "-c:v", "copy"]
        run([*args, "-movflags", "+faststart", "-y", candidate])
        os.replace(candidate, dest)


def _atoms(path):
    atoms = []
    size = Path(path).stat().st_size
    with Path(path).open("rb") as stream:
        while stream.tell() < size:
            offset = stream.tell()
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError("Truncated MP4 atom")
            length, kind = struct.unpack(">I4s", header)
            header_size = 8
            if length == 1:
                extended = stream.read(8)
                if len(extended) != 8:
                    raise ValueError("Truncated extended MP4 atom")
                length = struct.unpack(">Q", extended)[0]
                header_size = 16
            if length == 0:
                length = size - offset
            if length < header_size or offset + length > size:
                raise ValueError("Invalid MP4 atom length")
            atoms.append(kind.decode("ascii"))
            stream.seek(offset + length)
    return atoms


def verify(path, expected_frames=None, fps=None) -> dict:
    info = json.loads(run([tool("ffprobe"), "-v", "error", "-count_frames", "-show_streams",
                           "-show_format", "-of", "json", path]).stdout)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise ValueError("Master has no video stream")
    frames = int(video["nb_read_frames"])
    if expected_frames is not None and frames != expected_frames:
        raise ValueError(f"Frame count {frames} does not match expected {expected_frames}")
    actual_fps = float(video["avg_frame_rate"].split("/")[0]) / float(video["avg_frame_rate"].split("/")[1])
    if fps is not None and abs(actual_fps - fps) > .001:
        raise ValueError(f"Frame rate {actual_fps} does not match expected {fps}")
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    duration = float(video.get("duration", frames / actual_fps))
    audio_duration = float(audio["duration"]) if audio and audio.get("duration") else None
    if audio_duration is not None and abs(duration - audio_duration) > max(.05, 1 / actual_fps):
        raise ValueError(f"Audio/video duration mismatch: {audio_duration}s / {duration}s")
    atoms = _atoms(path)
    faststart = "moov" in atoms and "mdat" in atoms and atoms.index("moov") < atoms.index("mdat")
    if not faststart:
        raise ValueError("MP4 is missing faststart")
    run([tool("ffmpeg"), "-v", "error", "-xerror", "-i", path, "-f", "null", "-"])
    loudness = _measure(path) if audio else None
    return {"frames": frames, "fps": actual_fps, "width": video["width"], "height": video["height"],
            "duration": duration, "audioDuration": audio_duration, "videoCodec": video["codec_name"],
            "audioCodec": audio["codec_name"] if audio else None,
            "sampleRate": int(audio["sample_rate"]) if audio else None,
            "faststart": faststart, "decoded": True, "loudness": loudness}
