"""Project CLI integration checks; only the Remotion render boundary is substituted."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "video/scripts"))
spec = importlib.util.spec_from_file_location("reel_cli_under_test", REPO / "video/scripts/reel_cli.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class ProjectCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory(prefix="reelinator cli media ")
        cls.fixture_root = Path(cls.fixtures.name)
        try:
            cls.ffmpeg = cli.tool("ffmpeg")
            cli.tool("ffprobe")
        except FileNotFoundError as exc:
            raise unittest.SkipTest(str(exc))
        cls.source = cls.fixture_root / "recording.mkv"
        cli.run([cls.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=30",
                 "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "3",
                 "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "pcm_s16le", "-y", cls.source])
        cls.other_source = cls.fixture_root / "other.wav"
        cli.run([cls.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000",
                 "-t", "3", "-c:a", "pcm_s16le", "-y", cls.other_source])
        cls.short_picture = cls.fixture_root / "short.mp4"
        cli.run([cls.ffmpeg, "-v", "error", "-i", cls.source, "-t", "1", "-an", "-c:v", "libx264",
                 "-preset", "ultrafast", "-movflags", "+faststart", "-y", cls.short_picture])
        cls.short_audio = cls.fixture_root / "short.wav"
        cli.run([cls.ffmpeg, "-v", "error", "-i", cls.source, "-t", "1", "-vn", "-c:a", "pcm_s16le",
                 "-y", cls.short_audio])

    @classmethod
    def tearDownClass(cls):
        cls.fixtures.cleanup()

    def setUp(self):
        # FFmpeg concat treats '#' in the Windows sandbox TEMP parent as a URL fragment.
        temp_root = REPO / "video/out"
        temp_root.mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="test cli projects ", dir=temp_root)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.video = self.root / "video"
        self.projects = self.video / "projects"
        shutil.copytree(REPO / "video/templates/project", self.video / "templates/project")
        (self.video / "src").mkdir()
        (self.video / "src/index.css").write_text("/* fixture shared source */\n", encoding="utf-8")
        replacements = patch.multiple(cli, ROOT=self.root, VIDEO=self.video, PROJECTS=self.projects)
        replacements.start()
        self.addCleanup(replacements.stop)

    def command(self, *args, expected=0):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = cli.main(list(map(str, args)))
        self.assertEqual(result, expected, out.getvalue() + err.getvalue())
        return out.getvalue(), err.getvalue()

    def new(self, name):
        self.command("new", name, "--width", "160", "--height", "90", "--seconds", "3")
        return self.projects / name

    def accepted(self, project):
        out = project / "out"
        out.mkdir(exist_ok=True)
        (out / "accepted.mp4").write_bytes(b"previous accepted master")
        cli.atomic_json(out / "latest.json", {"run": "accepted", "master": "accepted.mp4"})

    def snapshot(self, project):
        names = ("edit.json", "media.json", "transcript.json", "out/latest.json", "out/accepted.mp4")
        return {name: (project / name).read_bytes() for name in names if (project / name).exists()}

    def assert_preserved(self, project, before):
        for name, content in before.items():
            self.assertEqual((project / name).read_bytes(), content, f"Accepted {name} changed after failure")
        self.assertFalse((project / "cache/operation.lock").exists())

    def test_two_projects_import_cut_and_prepare_remain_isolated(self):
        alpha, beta = self.new("alpha"), self.new("beta")
        imported, _ = self.command("import", "alpha", self.source)
        asset = imported.strip()
        self.assertEqual(cli.digest(alpha / "public" / asset), cli.digest(self.source))
        self.command("cut", "alpha", "--source", self.source, "--keep", "0:1")
        self.command("cut", "beta", "--source", self.source, "--keep", "1:3")
        alpha_media = cli.read_json(alpha / "media.json")
        self.assertEqual(alpha_media["durationInFrames"], 30)
        self.assertEqual(cli.read_json(beta / "media.json")["durationInFrames"], 60)
        before = self.snapshot(alpha)
        cli.atomic_json(beta / "transcript.json", [{"w": "исправление", "s": 1.2, "e": 1.5}])
        self.command("prepare", "beta")
        self.assertEqual(cli.read_json(beta / "media.json")["captions"][0]["w"], "исправление")
        self.assertEqual(self.snapshot(alpha), before)
        self.assertTrue((alpha / "public" / alpha_media["video"]).is_file())
        self.assertFalse((beta / "public" / alpha_media["video"]).exists())

    def test_replacing_source_does_not_inherit_corrected_captions(self):
        project = self.new("replace")
        self.command("cut", "replace", "--source", self.source)
        cli.atomic_json(project / "transcript.json", [{"w": "old corrected words", "s": .1, "e": .5}])
        self.command("prepare", "replace")
        before = self.snapshot(project)
        _, error = self.command("cut", "replace", "--source", self.other_source, expected=1)
        self.assertIn("cannot inherit existing transcript", error)
        self.assert_preserved(project, before)
        cli.atomic_json(project / "transcript.json", [])
        self.command("cut", "replace", "--source", self.other_source)
        self.assertEqual(cli.read_json(project / "transcript.json"), [])
        current = cli.read_json(project / "media.json")
        self.assertEqual(current["captions"], [])
        self.assertIsNone(current["video"])
        self.assertIsNotNone(current["audio"])

    def test_failed_cut_preserves_edit_media_and_latest(self):
        project = self.new("preserve")
        self.command("cut", "preserve", "--source", self.source)
        cli.atomic_json(project / "transcript.json", [{"w": "whole word", "s": .9, "e": 1.2}])
        self.command("prepare", "preserve")
        self.accepted(project)
        before = self.snapshot(project)
        _, error = self.command("cut", "preserve", "--keep", "0:1", expected=1)
        self.assertIn("Cut crosses spoken word", error)
        self.assert_preserved(project, before)

    def test_failed_new_source_cut_keeps_existing_corrections(self):
        project = self.new("bad-source")
        self.command("cut", "bad-source", "--source", self.source)
        cli.atomic_json(project / "transcript.json", [{"w": "corrected", "s": .1, "e": .5}])
        self.command("prepare", "bad-source")
        self.accepted(project)
        before = self.snapshot(project)
        invalid = self.root / "broken.mp4"
        invalid.write_bytes(b"not a media file")
        self.command("cut", "bad-source", "--source", invalid, expected=1)
        self.assert_preserved(project, before)

    def test_invalid_project_id_and_format_do_not_leave_projects(self):
        for name in ("../escape", "Capital", "", "a" * 65):
            with self.subTest(name=name):
                self.command("new", name, expected=1)
        for flags in (("--width", "161"), ("--height", "0"), ("--seconds", "0"),
                      ("--fps", "nan"), ("--fps", "inf")):
            with self.subTest(flags=flags):
                self.command("new", "invalid", *flags, expected=1)
        self.assertFalse((self.projects / "invalid").exists())
        self.assertEqual(list(self.projects.glob(".new-*")), [])
        self.assertFalse((self.video / "escape").exists())

    def test_remotion_failure_preserves_accepted_export(self):
        project = self.new("render-failure")
        self.command("prepare", "render-failure")
        self.accepted(project)
        before = self.snapshot(project)
        with patch.object(cli, "check_project"), patch.object(
                cli, "render_node", side_effect=RuntimeError("fixture renderer failed")):
            _, error = self.command("render", "render-failure", expected=1)
        self.assertIn("fixture renderer failed", error)
        self.assert_preserved(project, before)

    def test_open_studio_allows_preparation_and_releases_lock_on_exit(self):
        project = self.new("studio-edit")

        def studio_process(args, **_kwargs):
            self.assertIn("studio", args)
            self.assertTrue((project / "media.json").is_file())
            self.assertFalse((project / "cache/operation.lock").exists())
            self.command("prepare", "studio-edit")

        with patch.object(cli.subprocess, "run", side_effect=studio_process) as launched:
            self.command("studio", "studio-edit", "--port", "3111")
        launched.assert_called_once()
        self.assertFalse((project / "cache/operation.lock").exists())

    def test_wrong_render_frame_count_is_rejected_before_publication(self):
        project = self.new("wrong-frames")
        self.command("prepare", "wrong-frames")
        self.accepted(project)
        before = self.snapshot(project)

        def short_render(_project, stage, **_kwargs):
            shutil.copyfile(self.short_picture, stage / "part-0.mp4")
            shutil.copyfile(self.short_audio, stage / "sound.wav")
            (stage / "parts.txt").write_text("file 'part-0.mp4'\n", encoding="utf-8")
            (stage / "render.log").write_text("fixture renderer\n", encoding="utf-8")
            cli.atomic_json(stage / "composition.json", {"durationInFrames": 90, "fps": 30})

        with patch.object(cli, "check_project"), patch.object(cli, "render_node", side_effect=short_render):
            _, error = self.command("render", "wrong-frames", expected=1)
        self.assertIn("Frame count", error)
        self.assert_preserved(project, before)

    def test_source_change_during_render_rejects_stale_export(self):
        project = self.new("changed")
        self.command("prepare", "changed")
        self.accepted(project)
        before = self.snapshot(project)
        scene = project / "scenes/Closing.tsx"
        scene.parent.mkdir()
        scene.write_text("export const Closing = () => null;\n", encoding="utf-8")
        composition = project / "Composition.tsx"
        composition.write_text(composition.read_text(encoding="utf-8") + '\nimport "./scenes/Closing";\n',
                               encoding="utf-8")
        fingerprints = cli.source_fingerprint(project)
        self.assertIn("video/projects/changed/scenes/Closing.tsx", fingerprints)
        mutation = scene.read_text(encoding="utf-8") + "\n// edit made while rendering\n"

        def changing_render(_project, _stage, **_kwargs):
            cli.atomic_json(project / "cache/generated.json", {"temporary": True})
            cli.atomic_json(project / "out/generated.json", {"temporary": True})
            self.assertEqual(cli.source_fingerprint(project), fingerprints,
                             "Generated cache/output files must not look like authored source changes")
            scene.write_text(mutation, encoding="utf-8")

        with patch.object(cli, "check_project"), patch.object(cli, "render_node", side_effect=changing_render):
            _, error = self.command("render", "changed", expected=1)
        self.assertIn("changed during rendering", error)
        self.assert_preserved(project, before)
        self.assertEqual(scene.read_text(encoding="utf-8"), mutation)


if __name__ == "__main__":
    unittest.main(verbosity=2)
