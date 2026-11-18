#!/usr/bin/env python3
"""Find released products the hub does not show yet; gate for the pages-sync job.

    release_watch.py scan        # print what is released but missing or stale here
    release_watch.py gate        # exit 100 (skip the agent) unless there is new work

Only final products count: a released Steam game, a production mobile release, a
live Chrome Web Store listing, an album that is out. Contract: docs/release-sync.md.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import signal
import contextlib
import fcntl
import subprocess
import urllib.error
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get('PAGES_SYNC_ROOT', Path(__file__).resolve().parents[1]))
PROGRAMS = Path(os.environ.get('PAGES_SYNC_PROGRAMS', ROOT.parent))
DISTRIBUTION = PROGRAMS / 'claude_server/data/distribution.json'
STATE = Path.home() / '.local/state/pages-sync/state.json'
STEAM_DEVELOPER = 'Morass'
RETRY_DAYS = 1
ERROR_DAYS = 1
DEADLINE = None
SCAN_SECONDS = 70
UA = {'User-Agent': 'Mozilla/5.0 (release-watch)'}
CWS = re.compile(r'https://chromewebstore\.google\.com/detail/[A-Za-z0-9_%-]+/[a-p]{32}')
NOT_PAGES = {'assets', 'content', 'scripts', 'docs', 'music', 'prints', 'tools',
             'small-games', 'games', 'mobile', 'youtube'}


def norm(name):
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'^the\s+', '', s)
    return re.sub(r'[^a-z0-9]+', '', s)


def remaining():
    value = DEADLINE - time.monotonic() if DEADLINE is not None else SCAN_SECONDS
    if value <= 0:
        raise TimeoutError('whole-scan budget exhausted')
    return value


def fetch(url, timeout=10):
    timeout = min(timeout, remaining())
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', 'replace')


def hub_pages(root=ROOT):
    """{dir: html} for authored product pages such as /wardenmark/."""
    out = {}
    for p in sorted(root.glob('*/index.html')):
        if p.parent.name not in NOT_PAGES and not p.parent.name.startswith('.'):
            out[p.parent.name] = p.read_text(errors='replace')
    return out


def card_for(projects, section, title, page):
    for c in projects.get(section, []):
        if norm(c['title']) == norm(title) or c.get('path', '').strip('/') == page:
            return c
    return None


def find_page(pages, projects, section, title, needle):
    for d, html in pages.items():
        if needle and needle in html:
            return d
    card = card_for(projects, section, title, None)
    if card and card.get('path', '').strip('/') in pages:
        return card['path'].strip('/')
    return next((d for d in pages if norm(d) == norm(title)), None)


def looks_unreleased(html, card):
    label = (card or {}).get('label', '')
    return bool(re.search(r'coming soon', label, re.I) or re.search(r'>\s*Coming Soon\s*<', html))


def steam_details(appid):
    _, raw = fetch(f'https://store.steampowered.com/api/appdetails?appids={appid}'
                   '&filters=basic,release_date,developers')
    result = json.loads(raw).get(appid) or {}
    data = result.get('data') or {}
    if result.get('success') is not True or not isinstance((data.get('release_date') or {}).get('coming_soon'), bool):
        raise ValueError(f'Steam {appid}: incomplete product observation')
    return data


def steam_released(errors=None, observed=None):
    errors = errors if errors is not None else []
    observed = observed if observed is not None else {}
    _, body = fetch('https://store.steampowered.com/search/results/?term=&developer='
                    f'{STEAM_DEVELOPER}&json=1&count=100&ignore_preferences=1')
    search = json.loads(body)
    if not isinstance(search.get('items'), list):
        raise ValueError('Steam search missing items')
    out = []
    if int(search.get('total_count', len(search['items']))) > len(search['items']):
        errors.append('steam: search exceeds first 100 results; incomplete discovery')
    for hit in search['items']:
        remaining()
        m = re.search(r'/apps/(\d+)/', hit.get('logo', ''))
        if not m:
            errors.append('steam: search item missing app identity')
            continue
        appid = m.group(1)
        try:
            data = steam_details(appid)
        except Exception as exc:
            errors.append(f'steam {appid}: {type(exc).__name__}: {exc}')
            continue
        observed[appid] = data
        if data.get('type') == 'game' and STEAM_DEVELOPER in (data.get('developers') or []):
            if data['release_date']['coming_soon'] is False:
                out.append((appid, data['name'], data['release_date'].get('date')))
    if errors and not out:
        raise ValueError('; '.join(errors))
    return out


def steam_items(pages, projects, released):
    items = []
    for appid, name, date in released:
        store = f'https://store.steampowered.com/app/{appid}/'
        page = find_page(pages, projects, 'games', name, f'store.steampowered.com/app/{appid}')
        card = card_for(projects, 'games', name, page)
        if page is None or card is None:
            action = 'create'
        elif looks_unreleased(pages[page], card) or f'app/{appid}' not in pages[page]:
            action = 'release'
        else:
            continue
        items.append({'kind': 'steam', 'action': action, 'title': name, 'store': store,
                      'page': page, 'released': date})
    return items


def distribution_data(distribution):
    data = json.loads(Path(distribution).read_text())
    try:
        generated = dt.datetime.fromisoformat(data['generated_at'].replace('Z', '+00:00'))
        age = (dt.datetime.now(dt.timezone.utc) - generated).total_seconds()
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError('mobile: missing valid inventory timestamp') from exc
    if not -300 <= age <= 36 * 3600:
        raise ValueError('mobile: stale or future inventory')
    if not isinstance(data.get('games'), list):
        raise ValueError('mobile: missing game coverage')
    return data


def mobile_live(distribution=DISTRIBUTION, errors=None):
    local_errors = []
    data = distribution_data(distribution)
    live = {}
    for ch in ('google_play', 'app_store'):
        if (data.get('sources', {}).get(ch) or {}).get('status') != 'ok':
            local_errors.append(f'mobile {ch}: inventory source unhealthy or missing')
            continue
        for game in data['games']:
            c = game.get('channels', {}).get(ch) or {}
            if (c.get('check') or {}).get('status') != 'ok':
                if c:
                    local_errors.append(f'mobile {game.get("title")} {ch}: product observation unhealthy')
                continue
            try:
                checked = dt.datetime.fromisoformat(c['check']['checked_at'].replace('Z', '+00:00'))
                age = (dt.datetime.now(dt.timezone.utc) - checked).total_seconds()
                if not -300 <= age <= 36 * 3600:
                    raise ValueError('stale cell')
            except (KeyError, TypeError, ValueError):
                local_errors.append(f'mobile {game.get("title")} {ch}: stale or missing product timestamp')
                continue
            url = c.get('url') or ''
            pattern = (r'https://play\.google\.com/store/apps/details\?id=([\w.]+)' if ch == 'google_play'
                       else r'https://apps\.apple\.com/[^\s]*?/id(\d+)')
            match = re.search(pattern, url)
            if c.get('state') == 'published':
                if not match:
                    local_errors.append(f'mobile {game.get("title")} {ch}: invalid published URL')
                    continue
                needle = ('id=' if ch == 'google_play' else 'id') + match.group(1)
                live.setdefault(game['title'], {})[ch] = (url, needle)
    if errors is None and local_errors:
        raise ValueError('; '.join(local_errors))
    if errors is not None:
        errors.extend(local_errors)
    return live


def mobile_items(pages, projects, live):
    items = []
    for title, chans in live.items():
        needles = [n for _, n in chans.values()]
        page = next((d for d, h in pages.items() if any(n in h for n in needles)), None)
        page = page or find_page(pages, projects, 'mobile', title, None)
        card = card_for(projects, 'mobile', title, page)
        missing = [ch for ch, (_, n) in chans.items() if page is None or n not in pages[page]]
        if page is None:
            action = 'create'
        elif card is None:
            action = 'merge'
        elif missing or looks_unreleased(pages[page], card):
            action = 'release'
        else:
            continue
        items.append({'kind': 'mobile', 'action': action, 'title': title, 'page': page,
                      'store': {ch: u for ch, (u, _) in chans.items()}})
    return items


def store_refs(page, programs=PROGRAMS):
    """Store configs naming this hub page (an App Store support URL must keep loading)."""
    needle = f'morass.github.io/{page}/'
    found = []
    for f in [*programs.glob('*/store/*.json'), *programs.glob('*/games/*/store/*.json')]:
        try:
            if needle in f.read_text(errors='replace'):
                found.append(str(f.relative_to(programs)))
        except OSError:
            pass
    return found


def stale_items(pages, projects, released=None, live=None, confirmations=None):
    # Discovery absence is not a withdrawal; only product-specific corroboration can remove.
    items = []
    for section, kind in (('games', 'steam'), ('mobile', 'mobile')):
        for card in projects.get(section, []):
            proof = (confirmations or {}).get((kind, card['title']))
            if proof:
                items.append({'kind': kind, 'action': 'remove', 'title': card['title'],
                              'page': card.get('path', '').strip('/') or None, 'evidence': proof})
    return items


def removal_confirmations(pages, projects, released, live, observed, distribution, errors):
    confirmed = {}
    released_ids = {row[0] for row in released or []}
    for card in projects.get('games', []):
        html = pages.get(card.get('path', '').strip('/'), '')
        ids = set(re.findall(r'store\.steampowered\.com/app/(\d+)', html))
        if not ids or ids & released_ids:
            continue
        proofs = []
        try:
            for appid in sorted(ids):
                data = observed.get(appid) or steam_details(appid)
                if data.get('type') != 'game' or STEAM_DEVELOPER not in data.get('developers', []):
                    raise ValueError('wrong product owner/type')
                if data['release_date']['coming_soon'] is not True:
                    raise ValueError('store still reports a released game')
                _, body = fetch(f'https://store.steampowered.com/app/{appid}/')
                if not re.search(r'coming soon|planned release date', body, re.I):
                    raise ValueError('public page does not corroborate unreleased status')
                proofs.append({'appid': appid, 'status': 'coming_soon', 'public_confirmation': True})
            confirmed[('steam', card['title'])] = proofs
        except Exception as exc:
            errors.append(f'steam retain {card["title"]}: {exc}')
    try:
        data = distribution_data(distribution)
    except Exception:
        return confirmed
    for card in projects.get('mobile', []):
        if card['title'] in (live or {}):
            continue
        game = next((g for g in data['games'] if norm(g['title']) == norm(card['title'])), None)
        html = pages.get(card.get('path', '').strip('/'), '')
        links = sorted(set(re.findall(r'https://(?:play\.google\.com|apps\.apple\.com)[^\s"<>]+', html)))
        proofs = []
        try:
            if not game or not links:
                raise ValueError('missing per-product inventory or public store identity')
            for url in links:
                remaining()
                channel = 'google_play' if 'play.google.com/' in url else 'app_store'
                cell = game.get('channels', {}).get(channel) or {}
                check = cell.get('check') or {}
                stamp = dt.datetime.fromisoformat(check.get('checked_at', '').replace('Z', '+00:00'))
                age = (dt.datetime.now(dt.timezone.utc) - stamp).total_seconds()
                if ((data.get('sources', {}).get(channel) or {}).get('status') != 'ok'
                        or check.get('status') != 'ok' or not -300 <= age <= 36 * 3600
                        or cell.get('state') != 'removed'):
                    raise ValueError(f'{channel}: no fresh authoritative withdrawn status')
                if channel == 'app_store':
                    appid = re.search(r'id(\d+)', url).group(1)
                    identifier = re.search(r'id(\d+)', cell.get('url') or '')
                    if not identifier or identifier.group(1) != appid:
                        raise ValueError('withdrawal identity does not match public app')
                    _, raw = fetch('https://itunes.apple.com/lookup?id=' + appid + '&country=us')
                    if json.loads(raw).get('resultCount') != 0:
                        raise ValueError('public Apple catalogue still lists app')
                else:
                    package = re.search(r'[?&]id=([\w.]+)', url).group(1)
                    if cell.get('identifier') != package:
                        raise ValueError('withdrawal identity does not match public package')
                    try:
                        fetch(url)
                    except urllib.error.HTTPError as exc:
                        if exc.code != 404:
                            raise
                    else:
                        raise ValueError('public Play listing is still reachable')
                proofs.append({'store': url, 'status': 'removed', 'public_confirmation': True})
            confirmed[('mobile', card['title'])] = proofs
        except Exception as exc:
            errors.append(f'mobile retain {card["title"]}: {exc}')
    return confirmed


def extension_items(projects, programs=PROGRAMS, check=True):
    items = []
    for tool in projects.get('tools', []):
        if 'extension' not in tool.get('label', '').lower():
            continue
        repo = programs / tool.get('url', '').rstrip('/').rsplit('/', 1)[-1]
        if 'chromewebstore.google.com' in tool.get('url', '') or not repo.is_dir():
            continue
        text = ''
        for f in [repo / 'README.md', *repo.glob('store/*'), *repo.glob('docs/*.md')]:
            if f.is_file() and f.stat().st_size < 2_000_000:
                text += f.read_text(errors='replace')
        m = CWS.search(text)
        if not m:
            continue
        if check:
            status, _ = fetch(m.group(0))
            if status != 200:
                raise ValueError(f'extension {tool["title"]}: HTTP {status}')
        items.append({'kind': 'extension', 'action': 'release', 'title': tool['title'],
                      'store': m.group(0), 'repo': str(repo)})
    return items


def music_items(root=ROOT, today=None):
    today = today or dt.date.today().isoformat()
    albums = json.loads((root / 'content/music.json').read_text()).get('albums', [])
    known = {a['name'] for a in
             json.loads((root / 'content/music-artists.json').read_text())['artists']}
    items = []
    for a in albums:
        out = a.get('release_date', '9999') <= today
        if out and a['artist'] not in known:
            items.append({'kind': 'music', 'action': 'create-artist', 'title': a['artist'],
                          'album': a['album']})
    return items


def scan():
    projects = json.loads((ROOT / 'content/projects.json').read_text())
    pages = hub_pages()
    items, errors = [], []
    released = live = None
    observed = {}

    def run(name, fn):
        try:
            remaining()
            return fn()
        except Exception as e:
            errors.append(f'{name}: {type(e).__name__}: {e}'[:300])
            return None

    released = run('steam', lambda: steam_released(errors=errors, observed=observed))
    live = run('mobile', lambda: mobile_live(errors=errors))
    items += steam_items(pages, projects, released) if released is not None else []
    items += mobile_items(pages, projects, live) if live is not None else []
    confirmations = run('withdrawal-check', lambda: removal_confirmations(pages, projects, released, live, observed, DISTRIBUTION, errors))
    for item in stale_items(pages, projects, released, live, confirmations):
        item['store_refs'] = store_refs(item['page']) if item['page'] else []
        items.append(item)
    items += run('extension', lambda: extension_items(projects)) or []
    items += run('music', music_items) or []
    return items, errors


def bounded_scan(budget=SCAN_SECONDS):
    global DEADLINE
    def expired(signum, frame):
        raise TimeoutError('whole-scan budget exhausted')
    old_handler = signal.signal(signal.SIGALRM, expired)
    old_timer = signal.setitimer(signal.ITIMER_REAL, budget)
    DEADLINE = time.monotonic() + budget
    try:
        try:
            return scan()
        except TimeoutError as exc:
            return [], [str(exc)]
    finally:
        signal.setitimer(signal.ITIMER_REAL, *old_timer)
        signal.signal(signal.SIGALRM, old_handler)
        DEADLINE = None


def key(item):
    identity = {k: item.get(k) for k in ('kind', 'action', 'title', 'page', 'store', 'album', 'evidence')}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]


def decide(items, errors, state, now):
    new = json.loads(json.dumps(state))
    ledger = new.setdefault('items', {})
    offered = []
    seen = set()
    for item in items:
        ident = key(item)
        seen.add(ident)
        entry = ledger.setdefault(ident, {'attempts': 0, 'status': 'discovered'})
        entry['item'] = item
        entry['last_seen'] = now
        if now >= entry.get('retry_at', 0) and len(offered) < 5:
            entry.update(status='attempted', attempts=entry['attempts'] + 1, attempted_at=now, retry_at=now + 20 * 3600)
            offered.append(ident)
    for ident, entry in ledger.items():
        if ident not in seen and entry.get('status') not in ('verified', 'resolved'):
            # Partial coverage cannot prove that unseen work was completed.
            if not errors:
                entry['status'] = 'not-observed'
    error_key = hashlib.sha256('\n'.join(sorted(set(errors))).encode()).hexdigest() if errors else None
    diagnostic = bool(errors) and (error_key != new.get('error_key') or now >= new.get('error_retry_at', 0))
    if diagnostic:
        new.update(error_key=error_key, error_retry_at=now + 20 * 3600)
    elif not errors:
        new.pop('error_key', None)
        new.pop('error_retry_at', None)
    new['dispatch'] = {'time': now, 'ids': offered, 'diagnostic': diagnostic, 'errors': errors}
    new['items'] = {k: v for k, v in ledger.items() if v.get('status') != 'not-observed' or now - v['last_seen'] < 90 * 86400}
    reason = f'{len(offered)} due item(s)' if offered else 'no due publication items'
    if errors:
        reason += '; partial scan: ' + '; '.join(errors)
    return bool(offered or diagnostic), reason, new


@contextlib.contextmanager
def locked(state):
    state.parent.mkdir(parents=True, exist_ok=True)
    with state.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def read_state(state):
    return json.loads(state.read_text()) if state.exists() else {}


def atomic_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    temp.replace(path)


def record(state, ident, outcome, reason, commit=None, path=None):
    with locked(state):
        data = read_state(state)
        entry = data.get('items', {}).get(ident)
        if entry is None or outcome not in ('blocked', 'verified') or not reason.strip():
            raise ValueError('known item, blocked/verified disposition and evidence required')
        evidence = {'reason': reason}
        if outcome == 'verified':
            if not commit or not re.fullmatch(r'[0-9a-f]{40}', commit) or not path:
                raise ValueError('verified requires full remote-default SHA and public relative page path')
            relative = Path(path)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('public path must stay within the site')
            subprocess.run(['git', '-C', str(ROOT), 'fetch', '-q', 'origin'], check=True, timeout=15)
            base = subprocess.check_output(['git', '-C', str(ROOT), 'symbolic-ref', 'refs/remotes/origin/HEAD'], text=True).strip()
            subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', commit, base], check=True, timeout=5)
            item = entry['item']
            if item.get('page'):
                if relative.as_posix().strip('/') != item['page']:
                    raise ValueError('receipt path does not match item')
            elif item['kind'] in ('steam', 'mobile'):
                catalog = json.loads(subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:content/projects.json']))
                section = 'games' if item['kind'] == 'steam' else 'mobile'
                card = card_for(catalog, section, item['title'], None)
                if not card or card.get('path', '').strip('/') != relative.as_posix().strip('/'):
                    raise ValueError('integrated card does not match receipt path')
            elif item['kind'] == 'extension':
                catalog = json.loads(subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:content/projects.json']))
                tool = next((row for row in catalog.get('tools', []) if row['title'] == item['title']), None)
                if not tool or tool.get('url') != item['store'] or relative.parts[0] != 'tools':
                    raise ValueError('integrated extension URL/path mismatch')
            elif item['kind'] == 'music':
                catalog = json.loads(subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:content/music-artists.json']))
                artist = next((row for row in catalog.get('artists', []) if row['name'] == item['title']), None)
                if not artist or relative.as_posix().strip('/') != 'music/' + artist['slug']:
                    raise ValueError('integrated artist/path mismatch')
            source_path = str(relative / 'index.html')
            expected = subprocess.run(['git', '-C', str(ROOT), 'show', f'{commit}:{source_path}'], capture_output=True)
            url = 'https://morass.github.io/' + relative.as_posix().strip('/') + '/'
            try:
                _, body = fetch(url)
            except urllib.error.HTTPError as exc:
                if exc.code != 404 or expected.returncode == 0 or entry['item']['action'] != 'remove':
                    raise
                body = None
            if expected.returncode == 0:
                if body is None or hashlib.sha256(body.encode()).digest() != hashlib.sha256(expected.stdout).digest():
                    raise ValueError('live page does not match integrated source')
            elif entry['item']['action'] != 'remove' or body is not None:
                raise ValueError('missing integrated page is not verified publication')
            evidence.update(commit=commit, url=url)
        now = time.time()
        entry.update(status=outcome, evidence=evidence, retry_at=now + 20 * 3600)
        data['receipts'] = (data.get('receipts', []) + [{'id': ident, 'outcome': outcome, 'time': now, **evidence}])[-1000:]
        atomic_json(state, data)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--state', type=Path, default=STATE)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('scan')
    sub.add_parser('gate')
    receipt = sub.add_parser('record')
    receipt.add_argument('id')
    receipt.add_argument('outcome', choices=['blocked', 'verified'])
    receipt.add_argument('reason')
    receipt.add_argument('--commit')
    receipt.add_argument('--path')
    args = ap.parse_args()
    if args.cmd == 'record':
        record(args.state, args.id, args.outcome, args.reason, args.commit, args.path)
        return 0
    try:
        with locked(args.state):
            items, errors = bounded_scan()
            if args.cmd == 'scan':
                print(json.dumps({'items': [dict(item, id=key(item)) for item in items], 'errors': errors}, indent=1, ensure_ascii=False))
                return 1 if errors else 0
            state = read_state(args.state)
            run, reason, new = decide(items, errors, state, time.time())
            atomic_json(args.state, new)
            atomic_json(args.state.with_name('scan.json'), {'time': time.time(), 'items': [dict(item, id=key(item)) for item in items], 'errors': errors})
            print(reason)
            return 0 if run else 100
    except BlockingIOError:
        print('release watcher already active; skip duplicate slot')
        return 100


if __name__ == '__main__':
    sys.exit(main())
