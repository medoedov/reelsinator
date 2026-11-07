#!/usr/bin/env python3
"""Shared entry point for Codex, Claude Code and a terminal."""
from pathlib import Path
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent / 'video' / 'scripts'))
from reel_cli import main

if __name__ == '__main__':
    raise SystemExit(main())
