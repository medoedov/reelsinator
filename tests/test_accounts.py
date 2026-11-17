"""Account isolation through the real CLI and filesystem, without a renderer."""
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'video/scripts'))
import reel_cli as cli


class AccountTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='reelinator-accounts-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.video = self.root / 'video'
        self.projects = self.video / 'projects'
        shutil.copytree(REPO / 'video/templates/project', self.video / 'templates/project')
        shutil.copytree(REPO / 'video/templates/account', self.video / 'templates/account')
        replacements = patch.multiple(cli, ROOT=self.root, VIDEO=self.video, PROJECTS=self.projects)
        replacements.start()
        self.addCleanup(replacements.stop)
        self.profile('cartoon', {'width': 1080, 'height': 1920, 'fps': 24,
                                 'colors': {'accent': '#112233'}})
        self.profile('personal', {'width': 720, 'height': 1280, 'fps': 30,
                                  'fontFamily': 'Example Font', 'audio': {'lufs': -18},
                                  'colors': {'accent': '#ee0000'}})

    def profile(self, name, defaults):
        path = self.video / 'accounts' / name
        path.mkdir(parents=True, exist_ok=True)
        cli.atomic_json(path / 'account.json', {'title': name, 'handle': '@' + name, 'defaults': defaults})
        (path / 'SOURCE.md').write_text(f'# {name}\n', encoding='utf-8')
        return path

    def command(self, *args, expected=0):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = cli.main(list(map(str, args)))
        self.assertEqual(result, expected, out.getvalue() + err.getvalue())
        return out.getvalue(), err.getvalue()

    def config(self, name):
        return cli.read_json(self.projects / name / 'project.json')

    def test_new_account_passport_and_first_episode_work_without_existing_profiles(self):
        with patch.object(cli, 'VIDEO', self.root / 'fresh-video'), patch.object(
                cli, 'PROJECTS', self.root / 'fresh-video/projects'):
            shutil.copytree(self.video / 'templates', cli.VIDEO / 'templates')
            self.assertEqual(self.command('accounts')[0], '')
            self.command('account-new', 'new-channel', '--title', 'Example series', '--platform', 'instagram',
                         '--handle', '@example-channel', '--brief', 'Two characters talk about science.',
                         '--width', '1080', '--height', '1920', '--fps', '24')
            account = cli.VIDEO / 'accounts/new-channel'
            profile = cli.read_json(account / 'account.json')
            self.assertEqual(profile, {'title': 'Example series', 'platform': 'instagram',
                                      'handle': '@example-channel', 'defaults': {'width': 1080, 'height': 1920, 'fps': 24}})
            source = (account / 'SOURCE.md').read_text(encoding='utf-8')
            for value in ('Example series', 'instagram', '@example-channel', 'Two characters talk about science.'):
                self.assertIn(value, source)
            self.assertEqual(list((account / 'assets').iterdir()), [account / 'assets/.gitkeep'])
            self.command('new', 'first', '--account', 'new-channel', '--seconds', '20')
            config = cli.read_json(cli.PROJECTS / 'first/project.json')
            self.assertEqual((config['account'], config['width'], config['height'], config['durationInFrames']),
                             ('new-channel', 1080, 1920, 480))
            self.assertEqual(self.command('list', '--account', 'new-channel')[0].splitlines(), ['first'])

    def test_new_account_does_not_invent_settings_or_overwrite_existing_work(self):
        self.command('account-new', 'minimal')
        account = self.video / 'accounts/minimal'
        before = {p.relative_to(account): p.read_bytes() for p in account.rglob('*') if p.is_file()}
        profile = cli.read_json(account / 'account.json')
        self.assertEqual(profile, {'title': 'minimal', 'platform': None, 'handle': None, 'defaults': {}})
        self.command('account-new', 'minimal', '--brief', 'replacement', expected=1)
        self.assertEqual({p.relative_to(account): p.read_bytes() for p in account.rglob('*') if p.is_file()}, before)
        for flags in (('--width', '17'), ('--height', '0'), ('--fps', 'nan'), ('--fps', '-1')):
            with self.subTest(flags=flags):
                self.command('account-new', 'invalid-new', *flags, expected=1)
                self.assertFalse((self.video / 'accounts/invalid-new').exists())
        self.command('account-new', '../outside', expected=1)
        self.assertFalse((self.video / 'outside').exists())
        self.assertEqual(list((self.video / 'accounts').glob('.new-*')), [])

    def test_creation_inherits_only_selected_account_and_partial_defaults(self):
        self.command('new', 'cartoon-one', '--account', 'cartoon', '--seconds', '20')
        self.command('new', 'personal-one', '--account', 'personal')
        cartoon, personal = self.config('cartoon-one'), self.config('personal-one')
        self.assertEqual((cartoon['account'], cartoon['width'], cartoon['height'], cartoon['fps'],
                          cartoon['durationInFrames']), ('cartoon', 1080, 1920, 24, 480))
        self.assertEqual((personal['account'], personal['width'], personal['height'], personal['fontFamily'],
                          personal['audio']['lufs']), ('personal', 720, 1280, 'Example Font', -18))
        self.assertEqual(cartoon['colors']['accent'], '#112233')
        self.assertEqual(personal['colors']['accent'], '#ee0000')
        template = cli.read_json(self.video / 'templates/project/project.json')
        self.assertEqual(cartoon['colors']['background'], template['colors']['background'])
        self.assertEqual(cartoon['fontFamily'], template['fontFamily'])
        self.assertEqual(cartoon['audio'], template['audio'])
        source = self.projects / 'cartoon-one/SOURCE.md'
        self.assertIn('../../accounts/cartoon/SOURCE.md', source.read_text(encoding='utf-8'))
        self.assertNotIn('personal', source.read_text(encoding='utf-8'))

    def test_explicit_format_overrides_profile_and_standalone_never_inherits_last_account(self):
        self.command('new', 'override', '--account', 'cartoon', '--width', '640', '--height', '360',
                     '--fps', '25', '--seconds', '2')
        config = self.config('override')
        self.assertEqual((config['width'], config['height'], config['fps'], config['durationInFrames']),
                         (640, 360, 25, 50))
        self.assertEqual(config['colors']['accent'], '#112233')
        self.command('new', 'standalone')
        plain = self.config('standalone')
        self.assertNotIn('account', plain)
        self.assertEqual((plain['width'], plain['height'], plain['fps'], plain['durationInFrames']),
                         (1280, 720, 30, 360))

    def test_profile_changes_affect_only_new_projects_and_old_project_survives_missing_profile(self):
        self.command('new', 'old', '--account', 'cartoon')
        old = self.config('old')
        self.profile('cartoon', {'width': 640, 'height': 360, 'colors': {'accent': '#445566'}})
        self.command('new', 'new', '--account', 'cartoon')
        self.assertEqual(self.config('old'), old)
        self.assertEqual(self.config('new')['width'], 640)
        self.assertEqual(self.config('new')['colors']['accent'], '#445566')
        (self.video / 'accounts/cartoon/account.json').unlink()
        self.command('prepare', 'old')
        self.assertEqual(cli.config_for(self.projects / 'old'), old)

    def test_list_filters_account_without_including_standalone_and_profiles_are_discoverable(self):
        self.command('new', 'first', '--account', 'cartoon')
        self.command('new', 'second', '--account', 'personal')
        self.command('new', 'unbound')
        self.assertEqual(self.command('list', '--account', 'cartoon')[0].splitlines(), ['first'])
        self.assertEqual(self.command('list', '--account', 'personal')[0].splitlines(), ['second'])
        self.assertEqual(self.command('list')[0].splitlines(), ['first', 'second', 'unbound'])
        accounts = self.command('accounts')[0]
        self.assertEqual([line.split('\t')[0] for line in accounts.splitlines()], ['cartoon', 'personal'])
        self.command('list', '--account', 'typo', expected=1)

    def test_invalid_account_and_defaults_leave_no_project_or_staging_directory(self):
        for account in ('../personal', 'Bad ID', 'missing'):
            with self.subTest(account=account):
                self.command('new', 'bad', '--account', account, expected=1)
        for defaults in ([], {'account': 'personal'}, {'width': 17}, {'fps': 'fast'},
                         {'fps': True}, {'colors': []}, {'colors': {'accnet': '#fff'}},
                         {'fontFamily': None}, {'audio': {'lufs': -90}}):
            with self.subTest(defaults=defaults):
                self.profile('invalid', defaults)
                self.command('new', 'bad', '--account', 'invalid', expected=1)
                self.assertFalse((self.projects / 'bad').exists())
                self.assertEqual(list(self.projects.glob('.new-*')), [])

    def test_asset_uses_project_account_and_copies_only_requested_file(self):
        for name, data in (('cartoon', b'whale model'), ('personal', b'personal mascot')):
            assets = self.video / 'accounts' / name / 'assets/characters'
            assets.mkdir(parents=True)
            (assets / 'hero.glb').write_bytes(data)
            (assets / 'unused.glb').write_bytes(b'unused')
        self.command('new', 'episode', '--account', 'cartoon')
        self.command('new', 'other', '--account', 'personal')
        imported = self.command('asset', 'episode', 'characters/hero.glb')[0].strip()
        local = self.projects / 'episode/public' / imported
        self.assertEqual(local.read_bytes(), b'whale model')
        self.assertEqual(list((self.projects / 'episode/public/assets').iterdir()), [local])
        self.assertFalse((self.projects / 'other/public/assets').exists())
        personal_import = self.command('asset', 'other', 'characters/hero.glb')[0].strip()
        personal_local = self.projects / 'other/public' / personal_import
        self.assertEqual(personal_local.read_bytes(), b'personal mascot')
        self.assertNotEqual(personal_import, imported)
        self.assertEqual(local.read_bytes(), b'whale model')
        (self.video / 'accounts/cartoon/assets/characters/hero.glb').write_bytes(b'updated whale')
        self.assertEqual(local.read_bytes(), b'whale model')
        newer = self.command('asset', 'episode', 'characters/hero.glb')[0].strip()
        self.assertNotEqual(newer, imported)
        self.assertEqual((self.projects / 'episode/public' / newer).read_bytes(), b'updated whale')

    def test_asset_rejects_other_accounts_absolute_paths_missing_files_and_unbound_projects(self):
        assets = self.video / 'accounts/cartoon/assets'
        assets.mkdir()
        other = self.video / 'accounts/personal/assets'
        other.mkdir()
        (other / 'private.glb').write_bytes(b'other account material')
        self.command('new', 'episode', '--account', 'cartoon')
        for path in ('../../personal/assets/private.glb', other / 'private.glb', '../account.json', 'missing.glb'):
            with self.subTest(path=path):
                self.command('asset', 'episode', path, expected=1)
                self.assertFalse((self.projects / 'episode/public/assets').exists())
                self.assertFalse((self.projects / 'episode/cache/operation.lock').exists())
        self.command('new', 'unbound')
        self.command('asset', 'unbound', 'hero.glb', expected=1)


if __name__ == '__main__':
    unittest.main()
