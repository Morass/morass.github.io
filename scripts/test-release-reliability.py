#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import subprocess
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('release_watch', Path(__file__).with_name('release_watch.py'))
rw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rw)


class Reliability(unittest.TestCase):
    def test_absence_is_not_withdrawal(self):
        self.assertEqual(rw.stale_items({'released': 'store'}, {'games': [{'title': 'Released', 'path': '/released/'}]}, [], {}), [])

    def test_http_success_with_failed_steam_observation_is_error(self):
        search = json.dumps({'items': [{'logo': 'https://cdn/apps/123/header.jpg'}]})
        with patch.object(rw, 'fetch', side_effect=[(200, search), (200, '{"123":{"success":false}}')]):
            with self.assertRaises(ValueError):
                rw.steam_released()

    def test_stale_failed_or_incomplete_mobile_inventory_is_unknown(self):
        for data in [{'games': []}, {'generated_at': '2000-01-01T00:00:00Z', 'games': []},
                     {'generated_at': rw.dt.datetime.now(rw.dt.timezone.utc).isoformat(), 'sources': {'google_play': {'status': 'error'}}, 'games': []}]:
            with self.subTest(data=data), tempfile.TemporaryDirectory() as d:
                p = Path(d) / 'distribution.json'
                p.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    rw.mobile_live(p)

    def test_unresolved_work_retries_next_daily_slot(self):
        items = [{'kind': 'steam', 'action': 'create', 'title': 'Game', 'store': 'https://store/1'}]
        run, _, state = rw.decide(items, [], {}, 1000)
        self.assertTrue(run)
        self.assertFalse(rw.decide(items, [], state, 1001)[0])
        self.assertTrue(rw.decide(items, [], state, 1000 + 86400)[0])

    def test_url_change_reopens_item_without_waiting_for_old_set(self):
        item = {'kind': 'mobile', 'action': 'create', 'title': 'Game', 'store': {'app_store': 'https://apps/1'}}
        _, _, state = rw.decide([item], [], {}, 1000)
        changed = dict(item, store={'app_store': 'https://apps/2'})
        self.assertTrue(rw.decide([changed], [], state, 1001)[0])

    def test_error_visibility_does_not_depend_on_pending_items(self):
        item = {'kind': 'steam', 'action': 'create', 'title': 'Game'}
        _, _, state = rw.decide([item], [], {}, 1000)
        run, reason, _ = rw.decide([item], ['extension: unavailable'], state, 1001)
        self.assertTrue(run)
        self.assertIn('extension', reason)

    def test_existing_steam_page_gets_mobile_merge(self):
        pages = {'game': 'https://store.steampowered.com/app/123/'}
        items = rw.mobile_items(pages, {'mobile': []}, {'Game': {'google_play': ('https://play.google.com/store/apps/details?id=game', 'id=game')}})
        self.assertEqual(items[0]['action'], 'merge')
        self.assertEqual(items[0]['page'], 'game')

    def test_scan_has_enforced_wall_budget_and_retains_partial_errors(self):
        with patch.object(rw, 'steam_released', side_effect=lambda **kw: time.sleep(1)):
            start = time.monotonic()
            _, errors = rw.bounded_scan(budget=0.03)
            self.assertLess(time.monotonic() - start, 0.5)
            self.assertTrue(any('budget' in e.lower() for e in errors))

    def test_mobile_removal_requires_fresh_withdrawal_and_public_absence(self):
        now = rw.dt.datetime.now(rw.dt.timezone.utc).isoformat()
        title = 'Released Game'
        url = 'https://apps.apple.com/us/app/released/id123'
        projects = {'mobile': [{'title': title, 'path': '/released/'}]}
        pages = {'released': url}
        cell = {'state': 'removed', 'url': url, 'check': {'status': 'ok', 'checked_at': now}}
        data = {'generated_at': now, 'sources': {'app_store': {'status': 'ok'}},
                'games': [{'title': title, 'channels': {'app_store': cell}}]}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'dist.json'
            path.write_text(json.dumps(data))
            errors = []
            with patch.object(rw, 'fetch', return_value=(200, '{"resultCount":1}')):
                proof = rw.removal_confirmations(pages, projects, [], {}, {}, path, errors)
            self.assertFalse(proof)
            self.assertTrue(errors)
            with patch.object(rw, 'fetch', return_value=(200, '{"resultCount":0}')):
                proof = rw.removal_confirmations(pages, projects, [], {}, {}, path, [])
            self.assertEqual(rw.stale_items(pages, projects, confirmations=proof)[0]['action'], 'remove')
            cell['state'] = 'not-submitted'
            path.write_text(json.dumps(data))
            with patch.object(rw, 'fetch', side_effect=AssertionError('unknown is not withdrawal')):
                self.assertFalse(rw.removal_confirmations(pages, projects, [], {}, {}, path, []))

    def test_mobile_store_still_live_on_other_channel_preserves_page(self):
        now = rw.dt.datetime.now(rw.dt.timezone.utc).isoformat()
        title = 'Game'
        projects = {'mobile': [{'title': title, 'path': '/game/'}]}
        self.assertFalse(rw.removal_confirmations({}, projects, [], {title: {'app_store': ('url', 'id1')}}, {}, Path('absent'), []))

    def test_steam_removal_requires_positive_status_and_public_corroboration(self):
        projects = {'games': [{'title': 'Game', 'path': '/game/'}]}
        pages = {'game': 'https://store.steampowered.com/app/123/'}
        observed = {'123': {'type': 'game', 'developers': ['Morass'], 'release_date': {'coming_soon': True}}}
        with patch.object(rw, 'fetch', return_value=(200, 'Planned Release Date')):
            proof = rw.removal_confirmations(pages, projects, [], {}, observed, Path('absent'), [])
            self.assertTrue(proof)
        with patch.object(rw, 'fetch', return_value=(200, 'Unable to load store')):
            self.assertFalse(rw.removal_confirmations(pages, projects, [], {}, observed, Path('absent'), []))
        observed['123']['release_date']['coming_soon'] = False
        with patch.object(rw, 'fetch', side_effect=AssertionError('published game must stay')):
            self.assertFalse(rw.removal_confirmations(pages, projects, [], {}, observed, Path('absent'), []))

    def test_individual_retry_and_five_item_dispatch_limit(self):
        items = [{'kind': 'steam', 'action': 'create', 'title': str(i)} for i in range(7)]
        run, _, state = rw.decide(items, [], {}, 1000)
        self.assertEqual(len(state['dispatch']['ids']), 5)
        run, _, state = rw.decide(items, [], state, 1001)
        self.assertTrue(run)
        self.assertEqual(len(state['dispatch']['ids']), 2)
        self.assertFalse(rw.decide(items, [], state, 1002)[0])

    def test_blocked_receipt_persists_through_real_cli(self):
        item = {'kind': 'steam', 'action': 'create', 'title': 'Game'}
        with tempfile.TemporaryDirectory() as d:
            state = Path(d) / 'state.json'
            state.write_text(json.dumps(rw.decide([item], [], {}, 1000)[2]))
            subprocess.run([sys.executable, str(Path(rw.__file__)), '--state', str(state), 'record', rw.key(item), 'blocked', 'missing art; next obtain licensed capsule'], check=True, capture_output=True)
            data = json.loads(state.read_text())
            self.assertEqual(data['items'][rw.key(item)]['status'], 'blocked')
            self.assertEqual(data['receipts'][-1]['outcome'], 'blocked')
            self.assertFalse(rw.decide([item], [], data, time.time())[0])

    def test_verified_receipt_requires_integrated_matching_live_page(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            origin = root / 'origin.git'
            repo = root / 'site'
            subprocess.run(['git', 'init', '-q', '--bare', str(origin)], check=True)
            subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
            (repo / 'content').mkdir()
            (repo / 'game').mkdir()
            (repo / 'game/index.html').write_text('<h1>Released Game</h1>')
            (repo / 'content/projects.json').write_text(json.dumps({'games': [{'title': 'Game', 'path': '/game/'}]}))
            subprocess.run(['git', '-C', str(repo), 'add', 'content/projects.json', 'game/index.html'], check=True)
            subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'fixture publication'], check=True)
            sha = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
            subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', str(origin)], check=True)
            subprocess.run(['git', '-C', str(repo), 'push', '-q', 'origin', 'main'], check=True)
            subprocess.run(['git', '-C', str(repo), 'remote', 'set-head', 'origin', 'main'], check=True)
            item = {'kind': 'steam', 'action': 'create', 'title': 'Game'}
            state = root / 'state.json'
            missing_link = dict(item, store='https://store.steampowered.com/app/123/')
            state.write_text(json.dumps(rw.decide([item, missing_link], [], {}, 1000)[2]))
            with patch.object(rw, 'ROOT', repo), patch.object(rw, 'fetch', return_value=(200, '<h1>Released Game</h1>')):
                with self.assertRaisesRegex(ValueError, 'lacks an offered store link'):
                    rw.record(state, rw.key(missing_link), 'verified', 'store omitted', sha, 'game')
            with patch.object(rw, 'ROOT', repo), patch.object(rw, 'fetch', return_value=(200, '<h1>Old Page</h1>')):
                with self.assertRaises(ValueError):
                    rw.record(state, rw.key(item), 'verified', 'published', sha, 'game')
                with self.assertRaises(ValueError):
                    rw.record(state, rw.key(item), 'verified', 'wrong item page', sha, 'other')
            with patch.object(rw, 'ROOT', repo), patch.object(rw, 'fetch', return_value=(200, '<h1>Released Game</h1>')):
                rw.record(state, rw.key(item), 'verified', 'matching deployed page', sha, 'game')
            self.assertEqual(json.loads(state.read_text())['items'][rw.key(item)]['evidence']['commit'], sha)
            (repo / 'game/index.html').write_text('<h1>Unlanded</h1>')
            subprocess.run(['git', '-C', str(repo), 'add', 'game/index.html'], check=True)
            subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'unlanded fixture'], check=True)
            unlanded = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
            with patch.object(rw, 'ROOT', repo):
                with self.assertRaises(subprocess.CalledProcessError):
                    rw.record(state, rw.key(item), 'verified', 'not integrated', unlanded, 'game')

    def test_repeated_diagnostic_is_bounded_but_retried_daily(self):
        _, _, state = rw.decide([], ['steam: unavailable'], {}, 1000)
        self.assertFalse(rw.decide([], ['steam: unavailable'], state, 1001)[0])
        self.assertTrue(rw.decide([], ['steam: unavailable'], state, 1000 + 86400)[0])

    def test_partial_or_absent_observation_is_not_a_verified_receipt(self):
        item = {'kind': 'steam', 'action': 'create', 'title': 'Game'}
        _, _, state = rw.decide([item], [], {}, 1000)
        self.assertEqual(state['items'][rw.key(item)]['status'], 'attempted')
        _, _, partial = rw.decide([], ['steam: unavailable'], state, 1001)
        self.assertEqual(partial['items'][rw.key(item)]['status'], 'attempted')
        _, _, clean = rw.decide([], [], state, 1001)
        self.assertEqual(clean['items'][rw.key(item)]['status'], 'not-observed')
        self.assertNotIn('receipts', clean)

    def test_extension_failure_is_visible(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / 'extension'
            repo.mkdir()
            (repo / 'README.md').write_text('https://chromewebstore.google.com/detail/tool/' + 'a' * 32)
            projects = {'tools': [{'title': 'Tool', 'label': 'Extension', 'url': 'https://github.com/owner/extension'}]}
            with patch.object(rw, 'fetch', side_effect=OSError('network')):
                with self.assertRaises(OSError):
                    rw.extension_items(projects, Path(d))


if __name__ == '__main__':
    unittest.main()
