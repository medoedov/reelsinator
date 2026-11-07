#!/usr/bin/env python3
"""Exercise master.sh with real FFmpeg/ffprobe and a fixture-only Remotion stub.

Run after applying the patch:
    python3 /path/to/prework/tests/test_master.py --repo /path/to/harness
This does not test React, Chromium, GPU rendering, ASR, or macOS/BB integration.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

PARSER = argparse.ArgumentParser(description=__doc__)
PARSER.add_argument('--repo', type=Path, default=Path.cwd())
ARGS, TEST_ARGS = PARSER.parse_known_args()
MASTER = ARGS.repo.resolve() / 'video/scripts/master.sh'
TOOLS = {name: shutil.which(name) for name in ('ffmpeg', 'ffprobe', 'node', 'bash')}

NPX_STUB = r'''import os, pathlib, subprocess, sys
args = sys.argv[1:]
if os.environ.get('FAIL_RENDER') == '1':
    sys.exit(23)
if args[:3] != ['remotion', 'render', 'MyComp']:
    sys.exit('Unexpected npx invocation: ' + repr(args))
out = args[3]
ff = os.environ['REAL_FFMPEG']
if out.endswith('.wav'):
    src = 'anullsrc=r=48000:cl=stereo' if os.environ.get('SILENT') == '1' else 'sine=frequency=440:sample_rate=48000'
    cmd = [ff, '-v', 'error', '-f', 'lavfi', '-i', src,
           '-t', str(int(os.environ['TEST_FRAMES']) / 30), '-ac', '2', '-c:a', 'pcm_s16le', '-y', out]
else:
    flag = next(a for a in args if a.startswith('--frames='))
    start, end = map(int, flag.split('=', 1)[1].split('-'))
    cmd = [ff, '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=30',
           '-frames:v', str(end-start+1), '-an', '-c:v', 'libx264', '-preset', 'ultrafast',
           '-pix_fmt', 'yuv420p', '-y', out]
subprocess.run(cmd, check=True, timeout=60)
'''

FFMPEG_WRAPPER = r'''import json, os, subprocess, sys
args = sys.argv[1:]
with open(os.environ['COMMAND_LOG'], 'a') as f:
    f.write(json.dumps(args) + '\n')
if os.environ.get('BAD_MEASUREMENT') == '1' and any('print_format=json' in a for a in args):
    print('{\n"input_i": "NaN",\n"input_tp": "-20"\n}', file=sys.stderr)
    sys.exit(0)
sys.exit(subprocess.run([os.environ['REAL_FFMPEG'], *args], timeout=120).returncode)
'''


def run(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, text=True, capture_output=True, timeout=120, **kwargs)


def mp4_atoms(path: Path) -> list[str]:
    data = path.read_bytes()
    out, offset = [], 0
    while offset + 8 <= len(data):
        size, kind = struct.unpack_from('>I4s', data, offset)
        header = 8
        if size == 1:
            size = struct.unpack_from('>Q', data, offset + 8)[0]
            header = 16
        elif size == 0:
            size = len(data) - offset
        if size < header or offset + size > len(data):
            raise ValueError('Invalid MP4 atom')
        out.append(kind.decode('ascii'))
        offset += size
    return out


@unittest.skipUnless(all(TOOLS.values()), 'ffmpeg, ffprobe, node and bash required')
class MasterPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='video smoke ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'проект с пробелами'
        self.video = self.root / 'video'
        for p in ('scripts', 'src', 'public'):
            (self.video / p).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(MASTER, self.video / 'scripts/master.sh')
        (self.root / 'harness.config.json').write_text(json.dumps({
            'audio': {'lufs': -14}, 'style': {'poster': {'enabled': False}}}))
        self.set_frames(90)
        # A genuine input file satisfies the legacy preflight. The rendering stub
        # creates independent disposable fixtures and never reads user media.
        r = run(TOOLS['ffmpeg'], '-v', 'error', '-f', 'lavfi', '-i',
                'testsrc2=size=160x90:rate=30', '-frames:v', '1', '-c:v',
                'libx264', '-y', str(self.video / 'public/footage.mp4'))
        self.assertEqual(r.returncode, 0, r.stderr)
        bindir = self.root / 'bin'
        bindir.mkdir()
        for name, content in (('npx', NPX_STUB), ('ffmpeg', FFMPEG_WRAPPER)):
            p = bindir / name
            p.write_text('#!' + sys.executable + '\n' + content)
            p.chmod(0o755)
        self.log = self.root / 'commands.jsonl'
        self.env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'],
                        REAL_FFMPEG=TOOLS['ffmpeg'], COMMAND_LOG=str(self.log), TEST_FRAMES='90')

    def set_frames(self, frames: int):
        (self.video / 'src/Composition.tsx').write_text(
            f'export const DURATION = {frames};\nconst TITLE_OUT = 0;\n')

    def execute(self, **env):
        return run(TOOLS['bash'], str(self.video / 'scripts/master.sh'),
                   env={**self.env, **env})

    def assert_master(self, frames: int):
        path = self.video / 'out/final-master.mp4'
        r = run(TOOLS['ffprobe'], '-v', 'error', '-count_frames', '-show_streams',
                '-show_format', '-of', 'json', str(path))
        self.assertEqual(r.returncode, 0, r.stderr)
        probe = json.loads(r.stdout)
        video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        audio = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
        self.assertEqual(int(video['nb_read_frames']), frames)
        self.assertEqual(audio['codec_name'], 'aac')
        self.assertEqual(audio['sample_rate'], '48000')
        self.assertLessEqual(abs(float(video['duration']) - float(audio['duration'])), 0.05)
        atoms = mp4_atoms(path)
        self.assertLess(atoms.index('moov'), atoms.index('mdat'), 'faststart missing')
        r = run(TOOLS['ffmpeg'], '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.video / 'out/preview.mp4').exists())
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        encoded = [c for c in calls if '-c:a' in c and c[c.index('-c:a') + 1] == 'aac']
        # One master encode and a distinct lower-quality preview encode.
        self.assertEqual(len(encoded), 2)
        self.assertEqual({c[-1] for c in encoded}, {'out/final-master.mp4', 'out/preview.mp4'})
        measured = next(c for c in calls if any('print_format=json' in a for a in c))
        self.assertEqual(measured[measured.index('-i') + 1], 'out/sound.wav')
        return path

    def test_tone_master(self):
        r = self.execute()
        self.assertEqual(r.returncode, 0, r.stderr)
        path = self.assert_master(90)
        r = run(TOOLS['ffmpeg'], '-hide_banner', '-nostats', '-i', str(path),
                '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-')
        measurement = json.loads(re.search(r'\{\s*"input_i".*?\}', r.stderr, re.S).group(0))
        self.assertLess(abs(float(measurement['input_i']) + 14), 1.0)
        self.assertLessEqual(float(measurement['input_tp']), -1.0)

    def test_silent_audio(self):
        r = self.execute(SILENT='1')
        self.assertEqual(r.returncode, 0, r.stderr)
        path = self.assert_master(90)
        decoded = subprocess.run([TOOLS['ffmpeg'], '-v', 'error', '-i', str(path),
                                  '-vn', '-f', 's16le', '-'], capture_output=True, timeout=30)
        self.assertEqual(decoded.returncode, 0)
        self.assertTrue(decoded.stdout)
        self.assertEqual(set(decoded.stdout), {0}, 'Silence was changed')

    def test_multiple_chunks_keep_last_frame(self):
        self.set_frames(810)
        r = self.execute(TEST_FRAMES='810')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assert_master(810)

    def test_render_failure_stops(self):
        r = self.execute(FAIL_RENDER='1')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.video / 'out/final-master.mp4').exists())

    def test_missing_input_stops(self):
        (self.video / 'public/footage.mp4').unlink()
        r = self.execute()
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.video / 'out/final-master.mp4').exists())

    def test_bad_loudnorm_measurement_stops(self):
        r = self.execute(BAD_MEASUREMENT='1')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.video / 'out/final-master.mp4').exists())


if __name__ == '__main__':
    if not MASTER.is_file():
        PARSER.error(f'Missing file: {MASTER}')
    unittest.main(argv=[sys.argv[0], *TEST_ARGS], verbosity=2)
