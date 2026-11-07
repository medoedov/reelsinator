"""Media contracts exercised against real FFmpeg; no Remotion stub is needed here."""
from __future__ import annotations

from array import array
import importlib.util
from itertools import groupby
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("media_ops", ROOT / "video/scripts/media_ops.py")
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)


class CaptionTests(unittest.TestCase):
    def test_edits_remap_corrected_words_and_keep_last_word(self):
        words = [{"w": "Первое", "s": .1, "e": .4, "accent": 1},
                 {"w": "лишнее", "s": 1.1, "e": 1.5},
                 {"w": "последнее.", "s": 2.4, "e": 3.0, "em": 2}]
        result = media.map_captions(words, [[0, 1], [2, 3]], 1.25)
        self.assertEqual([w["w"] for w in result], ["Первое", "последнее."])
        self.assertEqual(result[0]["s"], .08)
        self.assertEqual(result[-1]["e"], 1.6)
        self.assertEqual(result[-1]["em"], 2)
        self.assertEqual(result[0]["accent"], 1)

    def test_partial_spoken_word_requires_editorial_correction(self):
        with self.assertRaisesRegex(ValueError, "Cut crosses spoken word"):
            media.map_captions([{"w": "word", "s": .8, "e": 1.3}], [[0, 1]], 1)

    def test_invalid_edit_and_transcript_are_rejected(self):
        for edit in ({"keeps": []}, {"keeps": [[0, 4]]}, {"keeps": [[0, 2], [1, 3]]},
                     {"keeps": [[-1, 1]]}, {"speed": 0}, {"speed": float("nan")},
                     {"keeps": [[0, float("inf")]]}, {"fit": "stretch"}):
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                media.validate_edit(edit, 3)
        for words in ({}, [{"w": "", "s": 0, "e": 1}], [{"w": "word", "s": 0, "e": 0}]):
            with self.subTest(words=words), self.assertRaises(ValueError):
                media.map_captions(words, [[0, 1]], 1)


class MediaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="reelinator media ")
        cls.root = Path(cls.temp.name)
        try:
            cls.ffmpeg = media.tool("ffmpeg")
            media.tool("ffprobe")
        except FileNotFoundError as exc:
            raise unittest.SkipTest(str(exc))
        cls.source = cls.root / "source.mp4"
        media.run([cls.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=30",
                   "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "3",
                   "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                   "-c:a", "pcm_s16le", "-y", cls.root / "source.mkv"])
        # Keep the input PCM so the single master AAC assertion covers the whole pipeline.
        cls.source = cls.root / "source.mkv"
        cls.silent = cls.root / "silent.wav"
        media.run([cls.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                   "-t", "3", "-c:a", "pcm_s16le", "-y", cls.silent])
        cls.picture = cls.root / "picture.mp4"
        media.run([cls.ffmpeg, "-v", "error", "-i", cls.source, "-an", "-c:v", "copy",
                   "-movflags", "+faststart", "-y", cls.picture])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.temp_project = tempfile.TemporaryDirectory(prefix="проект с пробелами ", dir=self.root)
        self.addCleanup(self.temp_project.cleanup)
        self.project = Path(self.temp_project.name)
        (self.project / "public/assets").mkdir(parents=True)
        self.config = {"width": 160, "height": 90, "fps": 30, "durationInFrames": 90}

    def source_edit(self, source=None, **edit):
        source = source or self.source
        relative = "assets/source" + source.suffix
        shutil.copyfile(source, self.project / "public" / relative)
        media.atomic_json(self.project / "edit.json", {"source": relative, **edit})

    def test_empty_graphics_project_needs_no_footage_or_captions(self):
        prepared = media.prepare(self.project, self.config)
        self.assertEqual(prepared["durationInFrames"], 90)
        self.assertEqual(prepared["captions"], [])
        self.assertIsNone(prepared["video"])
        self.assertIsNone(prepared["audio"])

    def test_prepare_cut_speed_and_final_master_preserve_sync_and_last_frame(self):
        self.source_edit(keeps=[[0, 1], [2, 3]], speed=1.25)
        media.atomic_json(self.project / "transcript.json",
                          [{"w": "конец", "s": 2.4, "e": 3, "em": 2}])
        with patch.object(media, "run", wraps=media.run) as calls:
            prepared = media.prepare(self.project, self.config)
            picture = self.project / "public" / prepared["video"]
            audio = self.project / "public" / prepared["audio"]
            master = self.project / "master.mp4"
            media.normalize_mux(picture, audio, master)
        report = media.verify(master, expected_frames=48, fps=30)
        self.assertEqual(prepared["splices"], [24])
        self.assertEqual(prepared["captions"][-1]["e"], 1.6)
        self.assertEqual(report["sampleRate"], 48000)
        self.assertEqual(report["audioCodec"], "aac")
        self.assertTrue(report["faststart"] and report["decoded"])
        self.assertLess(abs(float(report["loudness"]["input_i"]) + 14), 1)
        self.assertLessEqual(float(report["loudness"]["input_tp"]), -1)
        aac_commands = [c.args[0] for c in calls.call_args_list
                        if "-c:a" in c.args[0] and c.args[0][c.args[0].index("-c:a") + 1] == "aac"]
        self.assertEqual(len(aac_commands), 1)
        self.assertNotIn("-shortest", aac_commands[0])

    def test_audio_only_silence_and_video_without_audio(self):
        self.source_edit(self.silent)
        prepared = media.prepare(self.project, self.config)
        self.assertIsNone(prepared["video"])
        self.assertIsNotNone(prepared["audio"])
        master = self.project / "silence.mp4"
        media.normalize_mux(self.picture, self.project / "public" / prepared["audio"], master)
        report = media.verify(master, 90, 30)
        self.assertEqual(report["loudness"]["input_i"], "-inf")
        decoded = subprocess.run([self.ffmpeg, "-v", "error", "-i", str(master), "-vn",
                                  "-f", "s16le", "-"], capture_output=True, check=True)
        self.assertTrue(decoded.stdout)
        self.assertEqual(set(decoded.stdout), {0})
        self.source_edit(self.picture)
        prepared = media.prepare(self.project, self.config)
        self.assertIsNone(prepared["audio"])
        media.normalize_mux(self.project / "public" / prepared["video"], None, master)
        self.assertIsNone(media.verify(master, 90, 30)["audioCodec"])

    def test_cache_tracks_content_transcript_and_project_isolation(self):
        self.source_edit()
        first = media.prepare(self.project, self.config)
        picture = self.project / "public" / first["video"]
        timestamp = picture.stat().st_mtime_ns
        self.assertEqual(media.prepare(self.project, self.config), first)
        self.assertEqual(picture.stat().st_mtime_ns, timestamp)
        media.atomic_json(self.project / "transcript.json", [{"w": "исправлено", "s": .1, "e": .4}])
        corrected = media.prepare(self.project, self.config)
        self.assertNotEqual(first["fingerprint"], corrected["fingerprint"])
        self.assertEqual(corrected["captions"][0]["w"], "исправлено")
        other = self.project / "other"
        (other / "public/assets").mkdir(parents=True)
        shutil.copyfile(self.source, other / "public/assets/source.mkv")
        media.atomic_json(other / "edit.json", {"source": "assets/source.mkv", "keeps": [[0, 1]]})
        other_prepared = media.prepare(other, self.config)
        self.assertEqual(other_prepared["durationInFrames"], 30)
        self.assertEqual(json.loads((self.project / "media.json").read_text(encoding="utf-8")), corrected)
        # Same filename, different source bytes must not reuse masks/cuts/metadata from the old input.
        media.run([self.ffmpeg, "-v", "error", "-i", self.source, "-vf", "hflip",
                   "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy", "-y",
                   self.project / "public/assets/source.mkv"])
        changed = media.prepare(self.project, self.config)
        self.assertNotEqual(corrected["fingerprint"], changed["fingerprint"])

    def test_invalid_prepare_preserves_accepted_metadata(self):
        self.source_edit()
        first = media.prepare(self.project, self.config)
        media.atomic_json(self.project / "edit.json", {"source": "../source.mkv"})
        with self.assertRaisesRegex(ValueError, "inside this project's public"):
            media.prepare(self.project, self.config)
        self.assertEqual(json.loads((self.project / "media.json").read_text(encoding="utf-8")), first)
        self.source_edit(keeps=[[0, 1]])
        media.atomic_json(self.project / "transcript.json", [{"w": "crossing", "s": .9, "e": 1.2}])
        with self.assertRaisesRegex(ValueError, "Cut crosses"):
            media.prepare(self.project, self.config)
        self.assertEqual(json.loads((self.project / "media.json").read_text(encoding="utf-8")), first)

    def test_failed_normalization_preserves_accepted_master(self):
        dest = self.project / "accepted.mp4"
        shutil.copyfile(self.picture, dest)
        original = media.digest(dest)
        for measured in ({"input_i": "NaN", "input_tp": "-20"},
                         {"input_i": "-14", "input_tp": "-20"},
                         {"input_i": "-14", "input_lra": "1", "input_tp": "-20",
                          "input_thresh": "-24", "target_offset": "inf"}):
            with self.subTest(measured=measured), patch.object(media, "_measure", return_value=measured):
                with self.assertRaises(ValueError):
                    media.normalize_mux(self.picture, self.silent, dest)
            self.assertEqual(media.digest(dest), original)
        with self.assertRaises(subprocess.CalledProcessError):
            media.normalize_mux(self.root / "missing.mp4", None, dest)
        self.assertEqual(media.digest(dest), original)

    def test_silence_draft_preserves_quiet_consonant_and_recording_end(self):
        source = self.project / "tails.wav"
        oscillator = "sin(2*PI*440*t)"
        expression = f"if(lt(t\\,0.9)\\,0.1*{oscillator}\\,if(lt(t\\,1.1)\\,0.005*{oscillator}\\,if(lt(t\\,2.5)\\,0\\,0.1*{oscillator})))"
        media.run([self.ffmpeg, "-v", "error", "-f", "lavfi", "-i", f"aevalsrc={expression}:s=16000",
                   "-t", "4", "-c:a", "pcm_s16le", "-y", source])
        keeps = media.suggest_keeps(source, self.project / "cache")
        self.assertEqual(len(keeps), 2)
        self.assertGreaterEqual(keeps[0][1], 1.3)
        self.assertLessEqual(keeps[1][0], 2.3)
        self.assertEqual(keeps[-1][1], 4)
        self.assertEqual(media.suggest_keeps(self.silent, self.project / "cache"), [[0, 3]])

    def test_many_fractional_cuts_keep_each_scene_at_its_audio_time(self):
        source = self.project / "numbered-scenes.mkv"
        media.run([self.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "nullsrc=s=64x36:r=30:d=25",
                   "-vf", "geq=lum='16+8*floor(N/30)':cb=128:cr=128", "-c:v", "ffv1", "-y", source])
        keeps = [[i + .1, i + .61] for i in range(25)]
        config = {"width": 64, "height": 36, "fps": 30, "durationInFrames": 750}
        media.atomic_json(self.project / "transcript.json",
                          [{"w": f"scene {i}", "s": i + .2, "e": i + .5} for i in range(25)])
        for speed in (1, 1.25):
            with self.subTest(speed=speed):
                self.source_edit(source, keeps=keeps, speed=speed)
                prepared = media.prepare(self.project, config)
                picture = self.project / "public" / prepared["video"]
                decoded = subprocess.run([self.ffmpeg, "-v", "error", "-i", str(picture),
                                          "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"],
                                         capture_output=True, check=True).stdout
                frame_size = 64 * 36 * 3 // 2
                self.assertEqual(len(decoded) % frame_size, 0)
                self.assertEqual(len(decoded) // frame_size, math.ceil(25 * .51 / speed * 30 - 1e-7))
                luminances = decoded[::frame_size]
                labels = [round((value - 16) / 8) for value in luminances]
                runs = [(label, len(list(group))) for label, group in groupby(labels)]
                self.assertEqual([label for label, _ in runs], list(range(25)), "Selected scene lost or reordered")
                boundary = 0
                for label, length in runs:
                    ideal_frame = label * .51 / speed * 30
                    self.assertLessEqual(abs(boundary - ideal_frame), .50001,
                                         f"Scene {label} drifted from the continuous audio timeline")
                    if label:
                        self.assertEqual(prepared["splices"][label - 1], boundary)
                    boundary += length
                self.assertLessEqual(abs(luminances[-1] - (16 + 8 * 24)), 2,
                                     "Final frame must belong to the last selected source scene")
                self.assertAlmostEqual(prepared["captions"][-1]["e"], (24 * .51 + .4) / speed, places=5)

    def test_audio_speed_moves_time_local_marker_with_video_timeline(self):
        source = self.project / "audio-marker.wav"
        expression = "if(between(t\\,0.8\\,1.2)\\,0.5*sin(2*PI*440*t)\\,0)"
        media.run([self.ffmpeg, "-v", "error", "-f", "lavfi", "-i", f"aevalsrc={expression}:s=48000",
                   "-t", "2", "-c:a", "pcm_s16le", "-y", source])
        self.source_edit(source, speed=2)
        prepared = media.prepare(self.project, self.config)
        decoded = subprocess.run([self.ffmpeg, "-v", "error", "-i",
                                  str(self.project / "public" / prepared["audio"]), "-ac", "1",
                                  "-f", "s16le", "-"], capture_output=True, check=True).stdout
        samples = array("h", decoded)
        if sys.byteorder != "little":
            samples.byteswap()

        def rms(start, end):
            window = samples[round(start * 48000):round(end * 48000)]
            return math.sqrt(sum(value * value for value in window) / len(window)) / 32768

        self.assertEqual(len(samples), 48000)
        self.assertGreater(rms(.44, .56), .1, "The sped-up marker should sound near 0.4–0.6s")
        self.assertLess(rms(.82, .95), .001, "Original-time marker must not remain near 0.9s")
        active = [index / 100 for index in range(100) if rms(index / 100, (index + 1) / 100) > .01]
        self.assertAlmostEqual(active[0], .4, delta=.05)
        self.assertAlmostEqual(active[-1] + .01, .6, delta=.05)

    def test_zero_frame_video_interval_fails_without_publishing_new_metadata(self):
        self.source_edit()
        accepted = media.prepare(self.project, self.config)
        self.source_edit(keeps=[[0, .001], [1, 2]])
        with self.assertRaisesRegex(ValueError, "zero output frames"):
            media.prepare(self.project, self.config)
        self.assertEqual(json.loads((self.project / "media.json").read_text(encoding="utf-8")), accepted)

    def audio_samples(self, path):
        decoded = subprocess.run([self.ffmpeg, "-v", "error", "-i", str(path), "-vn", "-ac", "1",
                                  "-ar", "48000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
        samples = array("h", decoded)
        if sys.byteorder != "little":
            samples.byteswap()
        return samples

    @staticmethod
    def rms(samples, start, end):
        window = samples[round(start * 48000):round(end * 48000)]
        return math.sqrt(sum(value * value for value in window) / len(window)) / 32768

    def test_audio_cuts_keep_selected_events_in_order_and_remove_discarded_event(self):
        source = self.project / "distinct-events.wav"
        events = [(.2, .4, 440), (1.2, 1.4, 880), (2.3, 2.5, 1320), (3.6, 3.8, 1760)]
        expression = "+".join(f"if(between(t\\,{a}\\,{b})\\,0.5*sin(2*PI*{hz}*t)\\,0)"
                              for a, b, hz in events)
        media.run([self.ffmpeg, "-v", "error", "-f", "lavfi", "-i", f"aevalsrc={expression}:s=48000",
                   "-t", "4", "-c:a", "pcm_s16le", "-y", source])
        self.source_edit(source, keeps=[[0, 1], [2, 3], [3.4, 4]])
        prepared = media.prepare(self.project, self.config)
        samples = self.audio_samples(self.project / "public" / prepared["audio"])
        self.assertEqual(len(samples), 124800)
        # Identify each event by both its output time and pitch, including the last keep.
        for start, end, hz in ((.24, .36, 440), (1.34, 1.46, 1320), (2.24, 2.36, 1760)):
            with self.subTest(event=hz):
                self.assertGreater(self.rms(samples, start, end), .2)
                window = samples[round(start * 48000):round(end * 48000)]
                crossings = sum(a <= 0 < b for a, b in zip(window, window[1:]))
                self.assertAlmostEqual(crossings / (end - start), hz, delta=15)
        for start, end in ((.5, .9), (1.05, 1.15), (1.6, 2.1), (2.45, 2.55)):
            self.assertLess(self.rms(samples, start, end), .001, "Discarded audio leaked into the cut")

    def test_different_stream_starts_preserve_shared_marker_and_caption_time(self):
        expression = "if(between(t\\,0.8\\,1.0)\\,0.5*sin(2*PI*440*t)\\,0)"
        for delayed in ("audio", "video"):
            source = self.project / f"delayed-{delayed}.mkv"
            video_trim = "trim=start=0.5" if delayed == "video" else "null"
            audio_trim = "atrim=start=0.5" if delayed == "audio" else "anull"
            media.run([self.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=black:s=160x90:r=30:d=3",
                       "-f", "lavfi", "-i", f"aevalsrc={expression}:s=48000:d=3", "-filter_complex",
                       f"[0:v]drawbox=c=white:t=fill:enable='between(t,0.8,1.0)',{video_trim}[v];[1:a]{audio_trim}[a]",
                       "-map", "[v]", "-map", "[a]", "-fps_mode", "passthrough", "-c:v", "ffv1",
                       "-c:a", "pcm_s16le", "-y", source])
            starts = {stream["codec_type"]: float(stream["start_time"]) for stream in media.probe(source)["streams"]}
            self.assertAlmostEqual(starts[delayed], .5, places=3)
            self.assertAlmostEqual(starts["video" if delayed == "audio" else "audio"], 0, places=3)
            for keeps, speed in (([[0, 3]], 1), ([[.2, 1.5], [2, 2.5]], 1.25)):
                with self.subTest(delayed=delayed, keeps=keeps, speed=speed):
                    self.source_edit(source, keeps=keeps, speed=speed)
                    media.atomic_json(self.project / "transcript.json", [{"w": "marker", "s": .8, "e": 1.0}])
                    prepared = media.prepare(self.project, self.config)
                    master = self.project / "offset-master.mp4"
                    media.normalize_mux(self.project / "public" / prepared["video"],
                                        self.project / "public" / prepared["audio"], master)
                    media.verify(master, prepared["durationInFrames"], 30)
                    samples = self.audio_samples(master)
                    expected_start, expected_end = (.8 - keeps[0][0]) / speed, (1 - keeps[0][0]) / speed
                    active = [i / 100 for i in range(len(samples) // 480)
                              if self.rms(samples, i / 100, (i + 1) / 100) > .01]
                    self.assertAlmostEqual(active[0], expected_start, delta=.05)
                    self.assertAlmostEqual(active[-1] + .01, expected_end, delta=.05)
                    decoded = subprocess.run([self.ffmpeg, "-v", "error", "-i", str(master), "-an",
                                              "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                                             capture_output=True, check=True).stdout
                    lit = [i for i, value in enumerate(decoded[::160 * 90]) if value > 150]
                    self.assertAlmostEqual(lit[0] / 30, expected_start, delta=1 / 30 + .001)
                    self.assertAlmostEqual((lit[-1] + 1) / 30, expected_end, delta=1 / 30 + .001)
                    self.assertAlmostEqual(prepared["captions"][0]["s"], expected_start, places=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
