"""Check a freshly generated graphics project against the real TypeScript consumer."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'video/scripts'))
from reel_cli import check_project, config_for
from media_ops import prepare


class ProjectTypeTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / 'video/node_modules/typescript/bin/tsc').is_file(), 'Run npm ci --prefix video')
    def test_fresh_graphics_project_with_no_media_typechecks(self):
        projects = ROOT / 'video/projects'
        projects.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='typecheck-', dir=projects) as temp:
            project = Path(temp)
            shutil.copytree(ROOT / 'video/templates/project', project, dirs_exist_ok=True)
            media = prepare(project, config_for(project))
            self.assertIsNone(media['video'])
            self.assertIsNone(media['audio'])
            try:
                check_project(project)
            except subprocess.CalledProcessError as error:
                self.fail((error.stdout or '') + (error.stderr or ''))


if __name__ == '__main__':
    unittest.main()
