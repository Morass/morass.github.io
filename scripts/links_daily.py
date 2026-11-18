#!/usr/bin/env python3
"""Collect store links in owned candidates, retry publication, and retain receipts."""
import argparse
import concurrent.futures
import fcntl
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

SITE_PATHS = ('content/music.json', 'content/prints.json', 'content/generated-pages.json',
              'assets/music/', 'assets/prints/', 'music/', 'prints/', 'index.html', 'sitemap.xml')
class BudgetExceeded(BaseException):
    pass


SPARSE = ('/*', '!*.stl', '!*.3mf', '!*.blend', '!*.glb', '!*.mp4', '!*.zip')


def command(args, cwd=None, timeout=90, env=None, data=None):
    process = subprocess.Popen([str(a) for a in args], cwd=cwd, env=env,
                               stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        output, _ = process.communicate(data.encode() if data is not None else None, timeout=timeout)
    except BaseException:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    output = output.decode(errors='replace')
    if process.returncode:
        raise RuntimeError(f'{args[0]} exit {process.returncode}: {output[-4000:]}')
    return output.rstrip('\n')


def git(root, *args, **kwargs):
    return command(['git', '-C', root, *args], **kwargs)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class Journal:
    def __init__(self, path):
        self.path = path
        self.data = json.loads(path.read_text()) if path.exists() else {'candidates': {}, 'receipts': []}

    def save(self):
        atomic_json(self.path, self.data)

    def record(self, phase, status, **detail):
        receipt = dict(at=time.strftime('%Y-%m-%dT%H:%M:%S%z'), phase=phase, status=status, **detail)
        self.data['receipts'] = (self.data['receipts'] + [receipt])[-500:]
        self.save()
        print(json.dumps(receipt), flush=True)


def allowed(kind, path):
    if kind == 'music':
        return fnmatch.fnmatchcase(path, 'releases/*/links.json') and len(Path(path).parts) == 3
    if kind == 'prints':
        return path.endswith('/published_urls.json') and not path.startswith('.')
    return any(path == p or (p.endswith('/') and path.startswith(p)) for p in SITE_PATHS)


class Candidate:
    def __init__(self, kind, repo, worktrees, journal, checker, review_file=None):
        self.kind, self.repo, self.journal, self.checker = kind, repo.resolve(), journal, checker
        self.path = worktrees / ('pages-links-' + kind)
        self.branch = 'bot/pages-links-' + kind
        self.ref = 'refs/heads/' + self.branch
        self.remote = None
        self.review_file = review_file

    def note(self, status, reason):
        command([sys.executable, self.checker, 'note', '--repo', self.repo,
                 '--ref', self.ref, '--status', status, '--reason', reason])

    def prepare(self):
        git(self.repo, 'fetch', '-q', 'origin')
        self.remote = git(self.repo, 'symbolic-ref', 'refs/remotes/origin/HEAD')
        self.default = self.remote.removeprefix('refs/remotes/origin/')
        existing = self.journal.data['candidates'].get(self.kind)
        if existing and existing.get('phase') == 'creating' and not self.path.exists() and not git(self.repo, 'for-each-ref', '--format=%(refname)', self.ref):
            del self.journal.data['candidates'][self.kind]
            self.journal.save()
            existing = None
        if existing and (existing['path'] != str(self.path) or existing['repo'] != str(self.repo)):
            raise RuntimeError('Candidate ownership/path mismatch')
        if existing and existing.get('phase') != 'cleanup' and self.review_file and self.review_file.exists():
            reviews = json.loads(self.review_file.read_text())
            review = reviews.get(str(self.repo) + '|' + self.ref, {})
            if review.get('state') in {'superseded', 'discarded'}:
                raise RuntimeError('Retained candidate was released externally; inspect ownership before resuming')
        if existing and existing.get('phase') == 'cleanup':
            command([sys.executable, self.checker, 'check', '--repo', self.repo, '--commit', existing['commit']], timeout=120)
            if self.path.exists():
                if git(self.path, 'symbolic-ref', 'HEAD') != self.ref:
                    raise RuntimeError('Cleanup candidate branch mismatch')
                self.release()
            else:
                if git(self.repo, 'for-each-ref', '--format=%(refname)', self.ref):
                    if git(self.repo, 'rev-parse', self.ref) != existing['commit']:
                        raise RuntimeError('Cleanup branch changed after verified publication')
                    self.note('superseded', 'pages-links completing interrupted verified cleanup')
                    git(self.repo, 'branch', '-d', self.branch)
                del self.journal.data['candidates'][self.kind]
                self.journal.save()
            existing = None
        if existing:
            if existing['path'] != str(self.path) or existing['repo'] != str(self.repo):
                raise RuntimeError('Candidate ownership/path mismatch')
            if not self.path.exists():
                raise RuntimeError(f'Retained candidate missing: {self.path}; inspect {self.ref}')
            if git(self.path, 'symbolic-ref', 'HEAD') != self.ref:
                raise RuntimeError('Candidate branch mismatch')
            if existing.get('phase') == 'creating':
                if git(self.path, 'ls-files', '--others', '--exclude-standard'):
                    raise RuntimeError('Unexpected loose files in interrupted candidate initialization')
                if self.kind == 'prints':
                    git(self.path, 'sparse-checkout', 'set', '--no-cone', *SPARSE)
                # No collector runs before ready; these are exclusively our incomplete checkout files.
                git(self.path, 'checkout', 'HEAD', '--', '.', timeout=180)
                existing['phase'] = 'ready'
                self.journal.save()
            self.note('active', 'pages-links recovery; resume retained candidate before discovery; gate scoped JSON/build and remote/live delivery')
            return
        refs = git(self.repo, 'for-each-ref', '--format=%(refname)', self.ref)
        if self.path.exists() or refs:
            raise RuntimeError(f'Untracked existing candidate {self.path} / {self.ref}; recover ownership before new work')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Register intent before checkout, so interruption cannot hide a new branch.
        self.journal.data['candidates'][self.kind] = dict(path=str(self.path), repo=str(self.repo), ref=self.ref,
                                                         base=git(self.repo, 'rev-parse', self.remote), phase='creating')
        self.journal.save()
        git(self.repo, 'worktree', 'add', '--no-checkout', '-b', self.branch, self.path, self.remote)
        self.note('active', 'pages-links owned data candidate; gate scoped JSON/build and remote/live delivery; next collect or recover')
        if self.kind == 'prints':
            git(self.path, 'sparse-checkout', 'set', '--no-cone', *SPARSE)
        git(self.path, 'checkout', timeout=180)
        self.journal.data['candidates'][self.kind]['phase'] = 'ready'
        self.journal.save()

    def changes(self):
        tracked = git(self.path, 'diff', '--name-only', '-z', 'HEAD').split('\0')
        untracked = git(self.path, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')
        paths = sorted(set(filter(None, tracked + untracked)))
        for name in list(paths):
            target = name.removesuffix('.tmp') if self.kind == 'prints' else str(Path(name).with_suffix('.json'))
            owned_scratch = name in untracked and ((self.kind == 'music' and Path(name).name == 'links.tmp') or
                             (self.kind == 'prints' and Path(name).name == 'published_urls.json.tmp'))
            if owned_scratch and allowed(self.kind, target):
                # An interrupted atomic write is not a completed checkpoint; preserve the last record and retry discovery.
                (self.path / name).unlink()
                paths.remove(name)
                self.journal.record(self.kind + '-checkpoint', 'retry', path=target,
                                    next_action='Repeat interrupted observation; prior atomic record preserved')
        invalid = [p for p in paths if not allowed(self.kind, p)]
        if invalid:
            raise RuntimeError(f'Unexpected candidate paths: {invalid[:10]}')
        return paths

    def validate(self):
        paths = self.changes()
        for name in paths:
            path = self.path / name
            if name.endswith('.json'):
                if not path.exists():
                    if self.kind != 'site':
                        raise RuntimeError(f'Cannot delete source record {name}')
                    continue
                value = json.loads(path.read_text())
                if not isinstance(value, (dict, list)):
                    raise RuntimeError(f'Invalid JSON record {name}')
        if self.kind == 'site' and (paths or git(self.path, 'rev-parse', 'HEAD') != git(self.path, 'rev-parse', self.remote)):
            command([sys.executable, 'scripts/build.py'], cwd=self.path, timeout=180)
            command([sys.executable, 'scripts/check.py'], cwd=self.path, timeout=120)
            paths = self.changes()
        return paths

    def checkpoint(self):
        paths = self.validate()
        if paths:
            git(self.path, 'add', '--', *paths)
            git(self.path, 'commit', '-F', '-', '--', *paths,
                data='fix(links): refresh verified public store links\n')
        sha = git(self.path, 'rev-parse', 'HEAD')
        self.journal.data['candidates'][self.kind]['commit'] = sha
        self.journal.save()
        self.note('active', f'pages-links candidate {sha}; next merge latest default, gate and push, then verify delivery')
        return sha

    def publish(self):
        self.checkpoint()
        git(self.path, 'fetch', '-q', 'origin')
        base = self.journal.data['candidates'][self.kind]['base']
        candidate_paths = git(self.path, 'diff', '--name-only', '-z', base, 'HEAD').split('\0')
        if any(p and not allowed(self.kind, p) for p in candidate_paths):
            # Default may advance with unrelated work; only our commits must stay scoped.
            own = git(self.path, 'log', '--format=', '--name-only', self.remote + '..HEAD').splitlines()
            if any(p and not allowed(self.kind, p) for p in own):
                raise RuntimeError('Retained commits contain paths outside this job scope')
        git(self.path, 'merge', '-q', '--no-edit', self.remote)
        sha = self.checkpoint()
        ahead = git(self.path, 'rev-list', '--count', self.remote + '..HEAD')
        if ahead != '0':
            git(self.path, 'push', 'origin', 'HEAD:refs/heads/' + self.default, timeout=90)
        command([sys.executable, self.checker, 'check', '--repo', self.repo, '--commit', sha], timeout=120)
        self.journal.record(self.kind + '-publication', 'remote-verified', commit=sha)
        return sha

    def release(self):
        if self.changes():
            raise RuntimeError('Cannot release dirty candidate')
        self.journal.data['candidates'][self.kind].update(phase='cleanup', commit=git(self.path, 'rev-parse', 'HEAD'))
        self.journal.save()
        self.note('superseded', 'pages-links remote-default delivery verified; no loose files; removing owned candidate')
        git(self.repo, 'worktree', 'remove', self.path, timeout=120)
        git(self.repo, 'branch', '-d', self.branch)
        del self.journal.data['candidates'][self.kind]
        self.journal.save()


def verify_live(candidate, base_url, timeout=180):
    base = candidate.journal.data['candidates'][candidate.kind]['base']
    paths = git(candidate.path, 'diff', '--name-only', '-z', base, 'HEAD').split('\0')
    pages = [p for p in paths if p.endswith('.html') and (candidate.path / p).is_file()]
    deadline = time.monotonic() + timeout
    pending = {p: hashlib.sha256((candidate.path / p).read_bytes()).digest() for p in pages}
    def check(item):
        path, expected = item
        route = path.removesuffix('index.html') if path.endswith('/index.html') or path == 'index.html' else path
        url = base_url.rstrip('/') + '/' + route
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Cache-Control': 'no-cache'}), timeout=8) as response:
                return path, response.status == 200 and hashlib.sha256(response.read()).digest() == expected
        except Exception:
            return path, False
    while pending:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            for path, matches in pool.map(check, list(pending.items())):
                if matches:
                    pending.pop(path, None)
        if not pending:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f'Live deployment unverified for {len(pending)} pages: {list(pending)[:5]}')
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    candidate.journal.record('live-publication', 'verified', commit=git(candidate.path, 'rev-parse', 'HEAD'), pages=len(pages))


def run(args, journal):
    candidates, failed = {}, False
    for kind in ('site', 'music', 'prints'):
        c = Candidate(kind, getattr(args, kind), args.worktrees, journal, args.checker, getattr(args, 'integrity_reviews', None))
        try:
            c.prepare()
            # Recovery always precedes fresh discovery, even on a clean checkout with an unpushed commit.
            c.publish()
            if kind == 'site':
                verify_live(c, args.live_url, args.live_timeout)
            candidates[kind] = c
        except Exception as error:
            failed = True
            journal.record(kind + '-recovery', 'blocked', error=str(error), next_action='Resume retained candidate; do not start new work in this repository')
            if c.path.exists():
                c.note('blocked', f'pages-links {git(c.path, "rev-parse", "HEAD")}; {str(error)[:800]}; next resume and repeat scoped gates/remote/live verification')
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parent), STORE_BROWSER_TOOLS=str(Path(__file__).resolve().parent), PYTHONDONTWRITEBYTECODE='1')
    for kind in ('music', 'prints'):
        if 'site' not in candidates:
            journal.record(kind + '-scan', 'deferred', next_action='Finish retained site publication before new discovery')
            continue
        if kind not in candidates:
            continue
        c = candidates[kind]
        receipt = args.state.parent / (kind + '-scan.json')
        script = ['tools/release_links.py'] if kind == 'music' else ['publisher/audit_makerworld.py', '--only-missing', '--write-urls', '--list']
        try:
            receipt.unlink(missing_ok=True)
            output = command([sys.executable, *script, '--receipt', receipt], cwd=c.path,
                             env=env, timeout=300 if kind == 'music' else 180)
            print(output, flush=True)
            observation = json.loads(receipt.read_text())
            journal.record(kind + '-scan', observation['status'], items=observation.get('items', []))
            if observation['status'] != 'complete':
                failed = True
        except Exception as error:
            failed = True
            observation = json.loads(receipt.read_text()) if receipt.exists() else {}
            journal.record(kind + '-scan', 'error', error=str(error), items=observation.get('items', []), next_action='Retry failed observations at next daily run; known links preserved')
        try:
            c.publish()
        except Exception as error:
            failed = True
            candidates.pop(kind)
            journal.record(kind + '-publication', 'blocked', error=str(error), next_action='Retry existing candidate before discovery')
            c.note('blocked', f'pages-links publication blocked: {str(error)[:900]}; next integrate retained candidate')
    if 'site' in candidates:
        site = candidates['site']
        try:
            # Independent repositories can deliver without enlarging a blocked source candidate.
            if 'music' in candidates:
                command([sys.executable, 'tools/release_links.py', '--export-only', '--preserve-existing', '--hub', site.path],
                        cwd=candidates['music'].path, env=env, timeout=120)
            if 'prints' in candidates:
                command([sys.executable, site.path / 'scripts/import-prints.py', '--source', candidates['prints'].path,
                         '--destination', site.path, '--refresh-links', '--receipt', args.state.parent / 'prints-export.json'], cwd=site.path, timeout=180)
                export_receipt = json.loads((args.state.parent / 'prints-export.json').read_text())
                journal.record('prints-export', 'observed', **export_receipt,
                               next_action='Retain missing-source publications; publisher owns source metadata and explicit withdrawals')
            site.publish()
            verify_live(site, args.live_url, args.live_timeout)
        except Exception as error:
            failed = True
            candidates.pop('site')
            journal.record('site-publication', 'blocked', error=str(error), next_action='Resume retained site candidate; gate, integrate and verify live before more discovery')
            site.note('blocked', f'pages-links {git(site.path, "rev-parse", "HEAD")}; {str(error)[:800]}; next resume site candidate')
    for c in candidates.values():
        try:
            c.release()
        except Exception as error:
            failed = True
            journal.record(c.kind + '-cleanup', 'blocked', error=str(error), next_action='Release verified owned candidate without deleting loose files')
    journal.record('run', 'failed' if failed else 'complete', retained=list(journal.data['candidates']))
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=Path.home() / 'programs/morass.github.io')
    parser.add_argument('--music', type=Path, default=Path('/Volumes/BACKUP-1/programs/ambient-music'))
    parser.add_argument('--prints', type=Path, default=Path.home() / 'programs/prints')
    parser.add_argument('--state', type=Path, default=Path.home() / '.local/state/pages-links/state.json')
    parser.add_argument('--worktrees', type=Path, default=Path('/Volumes/BACKUP-1/worktrees/pages-links'))
    parser.add_argument('--checker', type=Path, default=Path.home() / 'programs/gamedev-knowledge/tools/git-integrity/git_integrity.py')
    parser.add_argument('--integrity-reviews', type=Path, default=Path.home() / '.local/state/fleet-git/reviews.json')
    parser.add_argument('--live-url', default='https://morass.github.io')
    parser.add_argument('--live-timeout', type=float, default=180)
    parser.add_argument('--budget-seconds', type=int, default=1200)
    args = parser.parse_args()
    if not 0 < args.budget_seconds <= 1200:
        parser.error('budget must be between 1 and 1200 seconds')
    args.state.parent.mkdir(parents=True, exist_ok=True)
    with args.state.with_suffix('.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('pages-links already running; no second collector started', file=sys.stderr)
            return 1
        journal = Journal(args.state)
        def deadline(signum, frame):
            raise BudgetExceeded('pages-links whole-run deadline or termination')
        signal.signal(signal.SIGALRM, deadline)
        signal.signal(signal.SIGTERM, deadline)
        signal.alarm(args.budget_seconds)
        try:
            return run(args, journal)
        except (BudgetExceeded, Exception) as error:
            signal.alarm(0)
            for kind, retained in journal.data['candidates'].items():
                try:
                    candidate = Candidate(kind, Path(retained['repo']), args.worktrees, journal, args.checker)
                    candidate.note('blocked', f'pages-links interrupted: {str(error)[:600]}; candidate {retained.get("commit", retained.get("base"))}; next resume retained scoped gate and remote/live delivery')
                except Exception:
                    pass
            journal.record('run', 'failed', error=str(error), retained=journal.data['candidates'],
                           next_action='Resume retained candidates before discovery; no completion claim')
            return 1
        finally:
            signal.alarm(0)


if __name__ == '__main__':
    raise SystemExit(main())
