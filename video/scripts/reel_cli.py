"""Project operations; edit ordinary TSX and JSON, then rebuild with the same command."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

from media_ops import atomic_json, digest, normalize_mux, prepare, probe, run, suggest_keeps, tool, validate_edit, verify

ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / 'video'
PROJECTS = VIDEO / 'projects'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def project_path(name):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', name):
        raise ValueError('Project ID: 1–64 lowercase letters, digits, hyphen or underscore')
    path = PROJECTS / name
    if not path.resolve().is_relative_to(PROJECTS.resolve()):
        raise ValueError('Project must stay within video/projects')
    return path


def config_for(project):
    config = read_json(project / 'project.json')
    for key in ('width', 'height', 'fps', 'durationInFrames'):
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{key} must be a positive finite number')
        if key != 'fps' and (value != int(value) or (key in ('width', 'height') and value % 2)):
            raise ValueError(f'{key} must be an integer; H264 dimensions must be even')
    target = config.get('audio', {}).get('lufs', -14)
    if not isinstance(target, (int, float)) or not math.isfinite(target) or not -70 <= target <= -5:
        raise ValueError('audio.lufs must be between -70 and -5')
    return config


@contextmanager
def operation(project):
    cache = project / 'cache'
    cache.mkdir(parents=True, exist_ok=True)
    lock = cache / 'operation.lock'
    try:
        handle = lock.open('x', encoding='utf-8')
    except FileExistsError:
        raise ValueError(f'Another operation owns {lock}. If interrupted, check its PID before removing this lock.') from None
    try:
        with handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def import_asset(project, source):
    source = Path(source).resolve(strict=True)
    if not source.is_file():
        raise ValueError('Source must be a file')
    suffix = source.suffix.lower()
    if not re.fullmatch(r'\.[a-z0-9]{1,10}', suffix):
        raise ValueError('Source needs a media extension')
    relative = Path('assets') / (digest(source) + suffix)
    dest = project / 'public' / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(source, dest)
    return relative.as_posix()


def create(args):
    project = project_path(args.project)
    if project.exists():
        raise ValueError(f'Project already exists: {project}')
    if not math.isfinite(args.fps) or not math.isfinite(args.seconds) or args.fps <= 0 or args.seconds <= 0:
        raise ValueError('fps and seconds must be positive finite numbers')
    config = read_json(VIDEO / 'templates/project/project.json')
    config.update(title=args.title or args.project, idea=args.idea or '', width=args.width,
                  height=args.height, fps=args.fps, durationInFrames=round(args.seconds * args.fps))
    # Build outside the final name so failed validation never leaves a half-created project.
    PROJECTS.mkdir(parents=True, exist_ok=True)
    stage = PROJECTS / f'.new-{uuid.uuid4().hex}'
    shutil.copytree(VIDEO / 'templates/project', stage)
    atomic_json(stage / 'project.json', config)
    try:
        config_for(stage)
        (stage / 'public').mkdir(exist_ok=True)
        (stage / 'public/.gitkeep').touch()
        stage.rename(project)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print(project)


def source_fingerprint(project):
    extensions = {'.tsx', '.ts', '.jsx', '.js', '.mjs', '.json', '.css'}
    paths = [p for p in project.rglob('*') if p.is_file() and p.suffix in extensions
             and p.relative_to(project).parts[0] not in {'cache', 'out', 'public'}]
    paths += list((VIDEO / 'src').rglob('*.tsx')) + list((VIDEO / 'src').rglob('*.ts'))
    paths += [ROOT / 'harness.config.json', VIDEO / 'package-lock.json', VIDEO / 'package.json', VIDEO / 'src/index.css']
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths) if p.is_file()}


def update_and_prepare(project, filename, value, config):
    path = project / filename
    old = path.read_bytes() if path.exists() else None
    atomic_json(path, value)
    try:
        return prepare(project, config)
    except BaseException:
        if old is None:
            path.unlink(missing_ok=True)
        else:
            temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
            temporary.write_bytes(old)
            os.replace(temporary, path)
        raise


def check_project(project):
    run([tool('node'), VIDEO / 'node_modules/typescript/bin/tsc', '--project', project / 'tsconfig.json'])


def remotion_env(project):
    # Webpack rejects '!' in Windows sandbox TEMP paths. Keep its temporary files in this project.
    temp = project / 'cache/tmp'
    temp.mkdir(parents=True, exist_ok=True)
    return dict(os.environ, TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))


def render_node(project, stage, mode='render', value=2):
    env = remotion_env(project)
    command = [tool('node'), VIDEO / 'scripts/render-project.mjs', project, stage, mode, str(value)]
    with (stage / 'render.log').open('w', encoding='utf-8') as log:
        result = subprocess.run([str(x) for x in command], cwd=VIDEO, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'Remotion failed; see {stage / "render.log"}')


def export(project, args):
    config = config_for(project)
    prepare(project, config)
    check_project(project)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    stage = project / 'cache' / f'render-{run_id}'
    stage.mkdir(parents=True)
    before = source_fingerprint(project)
    started = time.monotonic()
    render_node(project, stage, value=args.concurrency)
    if source_fingerprint(project) != before:
        raise ValueError('Project changed during rendering; accepted export was preserved. Rebuild the new revision.')
    composition = read_json(stage / 'composition.json')
    run([tool('ffmpeg'), '-v', 'error', '-f', 'concat', '-safe', '0', '-i', stage / 'parts.txt',
         '-c', 'copy', '-y', stage / 'picture.mp4'])
    normalize_mux(stage / 'picture.mp4', stage / 'sound.wav', stage / 'final-master.mp4',
                  config.get('audio', {}).get('lufs', -14))
    report = verify(stage / 'final-master.mp4', composition['durationInFrames'], composition['fps'])
    if (report['width'], report['height']) != (config['width'], config['height']):
        raise ValueError('Rendered dimensions disagree with project.json')
    run([tool('ffmpeg'), '-v', 'error', '-i', stage / 'final-master.mp4', '-vf',
         "scale='min(960,iw)':-2", '-c:v', 'libx264', '-crf', '26', '-preset', 'fast',
         '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-y', stage / 'preview.mp4'])
    verify(stage / 'preview.mp4', composition['durationInFrames'], composition['fps'])
    report.update(project=project.name, run=run_id, seconds=round(time.monotonic() - started, 2),
                  concurrency=args.concurrency, sourceHashes=before, visualReview='pending', speechReview='pending')
    atomic_json(stage / 'checks.json', report)
    snapshot = stage / 'source'
    for relative in before:
        dest = snapshot / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, dest)
    if source_fingerprint(project) != before:
        raise ValueError('Project changed during verification; accepted export was preserved. Rebuild the new revision.')
    runs = project / 'out/runs'
    runs.mkdir(parents=True, exist_ok=True)
    final = runs / run_id
    final.mkdir()
    for name in ('final-master.mp4', 'preview.mp4', 'checks.json', 'composition.json', 'render.log', 'source'):
        shutil.move(str(stage / name), final / name)
    atomic_json(project / 'out/latest.json', {'run': run_id, 'master': f'runs/{run_id}/final-master.mp4',
                                            'preview': f'runs/{run_id}/preview.mp4', 'checks': f'runs/{run_id}/checks.json'})
    print(final / 'final-master.mp4')


def transcribe(project, args):
    if (project / 'transcript.json').exists() and read_json(project / 'transcript.json') and not args.replace:
        raise ValueError('transcript.json already has corrections; use --replace explicitly to replace it')
    edit = read_json(project / 'edit.json')
    source = (project / 'public' / edit['source']).resolve(strict=True)
    if not source.is_relative_to((project / 'public').resolve()):
        raise ValueError('Source must be inside project/public')
    model_value = args.model or os.environ.get('WHISPER_MODEL')
    if not model_value:
        raise ValueError('Set WHISPER_MODEL or pass --model path/to/ggml-model.bin')
    model = Path(model_value).expanduser().resolve(strict=True)
    asr = tool('whisper-cli')
    cache = project / 'cache' / ('asr-' + uuid.uuid4().hex)
    cache.mkdir()
    wav = cache / 'source.wav'
    run([tool('ffmpeg'), '-v', 'error', '-i', source, '-vn', '-ar', '16000', '-ac', '1',
         '-af', 'aresample=16000:async=1:first_pts=0', '-y', wav])
    result = run([asr, '-m', model, '-f', wav, '-l', args.language, '-ml', '1', '-oj', '-of', cache / 'words'])
    (cache / 'asr.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    words = []
    for token in read_json(cache / 'words.json')['transcription']:
        text = token['text']
        if not text.strip():
            continue
        start, end = token['offsets']['from'] / 1000, token['offsets']['to'] / 1000
        if text.startswith(' ') or not words:
            words.append({'w': text.strip(), 's': start, 'e': end, 'em': 1})
        else:
            words[-1]['w'] += text.strip()
            words[-1]['e'] = end
    if not words:
        raise ValueError('No speech recognized; existing transcript was preserved')
    update_and_prepare(project, 'transcript.json', words, config_for(project))
    print(f'{len(words)} words; review transcript.json against the source audio')


def reference(project, source):
    cache = project / 'cache/references'
    cache.mkdir(parents=True, exist_ok=True)
    if source.startswith(('https://', 'http://')):
        url_key = hashlib.sha256(source.encode()).hexdigest()
        download = cache / url_key
        download.mkdir(exist_ok=True)
        result = run([tool('yt-dlp'), '--no-playlist', '--no-progress', '--print', 'after_move:filepath',
                      '-o', str(download / '%(id)s.%(ext)s'), '--', source])
        local = Path(result.stdout.strip().splitlines()[-1]).resolve(strict=True)
        if not local.is_relative_to(download.resolve()):
            raise ValueError('Downloader returned a path outside reference cache')
    else:
        local = Path(source).resolve(strict=True)
    identity = digest(local)
    dest = cache / identity
    dest.mkdir(exist_ok=True)
    info = probe(local)
    duration = float(info['format']['duration'])
    if not any(s['codec_type'] == 'video' for s in info['streams']):
        raise ValueError('Visual reference requires a video stream')
    measured = run([tool('ffmpeg'), '-hide_banner', '-i', local, '-vf', "select='gt(scene,0.1)',showinfo",
                    '-an', '-f', 'null', '-'])
    cuts = [float(v) for v in re.findall(r'pts_time:([\d.]+)', measured.stderr)]
    run([tool('ffmpeg'), '-v', 'error', '-i', local, '-vf', f'fps=12/{duration},scale=320:-2,tile=4x3',
         '-frames:v', '1', '-y', dest / 'contact-sheet.jpg'])
    atomic_json(dest / 'analysis.json', {'source': source, 'sha256': identity, 'duration': duration,
                'cutCandidates': cuts, 'note': 'Scene threshold is a measurement, not an editorial decision.'})
    print(dest)


def doctor():
    missing = []
    for name in ('python', 'node', 'ffmpeg', 'ffprobe'):
        try:
            executable = sys.executable if name == 'python' else tool(name)
            flag = '-version' if name.startswith('ff') else '--version'
            result = run([executable, flag])
            print(f'{name}: {(result.stdout or result.stderr).splitlines()[0]}')
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            missing.append(name)
            print(f'{name}: MISSING or failed ({error})')
    installed = (VIDEO / 'node_modules/@remotion/cli/remotion-cli.js').is_file()
    print('Remotion: installed' if installed else 'Remotion: run npm ci --prefix video')
    if not installed:
        missing.append('Remotion')
    print('Optional: whisper-cli + WHISPER_MODEL for ASR; yt-dlp for remote references; rembg for person matting')
    return 1 if missing else 0


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor', help='Check local required tools without touching credentials')
    commands.add_parser('list', help='List editable projects')
    new = commands.add_parser('new', help='Create an isolated editable project')
    new.add_argument('project'); new.add_argument('--idea'); new.add_argument('--title')
    new.add_argument('--width', type=int, default=1280); new.add_argument('--height', type=int, default=720)
    new.add_argument('--fps', type=float, default=30); new.add_argument('--seconds', type=float, default=12)
    for command in ('import', 'cut', 'prepare', 'transcribe', 'check', 'render', 'preview', 'still', 'studio', 'verify', 'reference'):
        sub = commands.add_parser(command)
        sub.add_argument('project')
        if command in ('import', 'reference'):
            sub.add_argument('source')
        if command == 'cut':
            sub.add_argument('--source', help='Local source to import, or use current edit.json source')
            sub.add_argument('--keep', help='Source seconds, e.g. 0.2:5.1,7.0:12.4; omitted = whole source')
            sub.add_argument('--auto', action='store_true', help='Write a pause-squeeze draft for review')
            sub.add_argument('--speed', type=float, default=1)
            sub.add_argument('--fit', choices=['contain', 'cover'], default='contain')
        if command == 'transcribe':
            sub.add_argument('--model'); sub.add_argument('--language', default='auto')
            sub.add_argument('--replace', action='store_true')
        if command in ('render', 'preview'):
            sub.add_argument('--concurrency', type=int, default=2)
        if command == 'still':
            sub.add_argument('--frame', type=int, default=0)
        if command == 'studio':
            sub.add_argument('--port', type=int, default=3000)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'doctor':
            return doctor()
        if args.command == 'list':
            for path in sorted(PROJECTS.glob('*/project.json')):
                print(path.parent.name)
            return 0
        if args.command == 'new':
            create(args)
            return 0
        project = project_path(args.project)
        config = config_for(project)
        if args.command == 'studio':
            with operation(project):
                prepare(project, config)
            # Studio watches project files; editing and exporting must remain available.
            subprocess.run([tool('node'), str(VIDEO / 'node_modules/@remotion/cli/remotion-cli.js'),
                            'studio', str(project / 'index.tsx'), '--public-dir', str(project / 'public'),
                            '--port', str(args.port)], cwd=VIDEO, env=remotion_env(project), check=True)
            return 0
        with operation(project):
            if args.command == 'import':
                print(import_asset(project, args.source))
            elif args.command == 'cut':
                if args.keep and args.auto:
                    raise ValueError('Use either --keep or --auto')
                source = import_asset(project, args.source) if args.source else read_json(project / 'edit.json')['source']
                path = (project / 'public' / source).resolve(strict=True)
                if not path.is_relative_to((project / 'public').resolve()):
                    raise ValueError('Source escapes the project')
                duration = float(probe(path)['format']['duration'])
                keeps = ([list(map(float, item.split(':'))) for item in args.keep.split(',')] if args.keep
                         else suggest_keeps(path, project / 'cache') if args.auto else [[0, duration]])
                edit = {'source': source, 'keeps': keeps, 'speed': args.speed, 'fit': args.fit}
                validate_edit(edit, duration)
                old_edit = read_json(project / 'edit.json') if (project / 'edit.json').exists() else None
                words = read_json(project / 'transcript.json') if (project / 'transcript.json').exists() else []
                if old_edit and old_edit['source'] != source and words:
                    raise ValueError('New source cannot inherit existing transcript; use a new project or explicitly clear transcript.json')
                update_and_prepare(project, 'edit.json', edit, config)
                print(project / 'edit.json')
            elif args.command == 'prepare':
                print(json.dumps(prepare(project, config), ensure_ascii=False))
            elif args.command == 'transcribe':
                transcribe(project, args)
            elif args.command == 'check':
                prepare(project, config)
                check_project(project)
                print('Project TypeScript OK')
            elif args.command == 'render':
                export(project, args)
            elif args.command == 'preview':
                prepare(project, config)
                check_project(project)
                stage = project / 'cache' / ('preview-' + uuid.uuid4().hex)
                stage.mkdir()
                render_node(project, stage, 'preview', args.concurrency)
                print(stage / 'preview.mp4')
            elif args.command == 'still':
                prepare(project, config)
                stage = project / 'cache' / ('still-' + uuid.uuid4().hex)
                stage.mkdir()
                render_node(project, stage, 'still', args.frame)
                print(stage / 'frame.png')
            elif args.command == 'verify':
                latest = read_json(project / 'out/latest.json')
                result = verify(project / 'out' / latest['master'])
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif args.command == 'reference':
                reference(project, args.source)
        return 0
    except (ValueError, KeyError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            detail = (error.stdout or '') + (error.stderr or '')
            if detail:
                print(detail[-4000:], file=sys.stderr)
        return 1
