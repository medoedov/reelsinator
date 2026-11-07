"""Create technical media locally. This is not a human-speech acceptance sample."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'video/scripts'))
from media_ops import atomic_json, run, tool

source = ROOT / 'video/out/technical-source.mp4'
source.parent.mkdir(parents=True, exist_ok=True)
run([tool('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30',
     '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=6',
     '-t', '6', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le',
     '-y', source.with_suffix('.mov')])
reel = [sys.executable, str(ROOT / 'reel.py')]
project = ROOT / 'video/projects/media-check'
if not project.exists():
    subprocess.run([*reel, 'new', 'media-check', '--width', '640', '--height', '360',
                    '--seconds', '6', '--title', 'Техническая проверка'], check=True)
atomic_json(project / 'transcript.json', [])
subprocess.run([*reel, 'cut', 'media-check', '--source', str(source.with_suffix('.mov')),
                '--keep', '0:2,4:6'], check=True)
atomic_json(project / 'transcript.json', [
    {'w': 'Начало', 's': .2, 'e': .8, 'em': 1},
    {'w': 'первого', 's': .8, 'e': 1.3, 'em': 1},
    {'w': 'фрагмента.', 's': 1.3, 'e': 1.9, 'em': 1},
    {'w': 'Второй', 's': 4.1, 'e': 4.8, 'em': 1},
    {'w': 'фрагмент.', 's': 4.8, 'e': 5.9, 'em': 1},
])
(project / 'SOURCE.md').write_text(
    '# Technical media check\n\nGenerated with FFmpeg testsrc2 and a 440 Hz tone. '
    'Caption text is a synthetic timing fixture, not a transcription of speech. '
    'Source keeps: 0–2 and 4–6 seconds. Regenerate with `python scripts/make-fixtures.py`.\n', encoding='utf-8')
subprocess.run([*reel, 'prepare', 'media-check'], check=True)
