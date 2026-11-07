#!/usr/bin/env python3
"""Copy repository-owned skills to both runtimes, or check their byte equality."""
from pathlib import Path
import argparse
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'skills'
TARGETS = (ROOT / '.claude/skills', ROOT / '.agents/skills')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Report missing or different generated files without writing')
    args = parser.parse_args()
    different = []
    for skill in sorted(SOURCE.iterdir()):
        if not skill.is_dir() or not (skill / 'SKILL.md').is_file():
            continue
        for source in sorted(skill.rglob('*')):
            if not source.is_file():
                continue
            relative = source.relative_to(SOURCE)
            content = source.read_bytes()
            for target in TARGETS:
                destination = target / relative
                if destination.is_file() and destination.read_bytes() == content:
                    continue
                different.append(destination.relative_to(ROOT).as_posix())
                if not args.check:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(content)
    if args.check and different:
        print('Out of sync:\n' + '\n'.join(different), file=sys.stderr)
        return 1
    print(f'{len(different)} files updated' if not args.check else 'Skill copies match both runtimes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
