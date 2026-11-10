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
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT.parent
DISTRIBUTION = PROGRAMS / 'claude_server/data/distribution.json'
STATE = Path.home() / '.local/state/pages-sync/gate.json'
STEAM_DEVELOPER = 'Morass'
RETRY_DAYS = 7
ERROR_DAYS = 3
UA = {'User-Agent': 'Mozilla/5.0 (release-watch)'}
CWS = re.compile(r'https://chromewebstore\.google\.com/detail/[A-Za-z0-9_%-]+/[a-p]{32}')
NOT_PAGES = {'assets', 'content', 'scripts', 'docs', 'music', 'prints', 'tools',
             'small-games', 'games', 'mobile', 'youtube'}


def norm(name):
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'^the\s+', '', s)
    return re.sub(r'[^a-z0-9]+', '', s)


def fetch(url, timeout=20):
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


def steam_released():
    """[(appid, name, date)] of every released Morass game on Steam."""
    _, body = fetch('https://store.steampowered.com/search/results/?term=&developer='
                    f'{STEAM_DEVELOPER}&json=1&count=100&ignore_preferences=1')
    out = []
    for hit in json.loads(body).get('items', []):
        m = re.search(r'/apps/(\d+)/', hit.get('logo', ''))
        if not m:
            continue
        appid = m.group(1)
        _, raw = fetch(f'https://store.steampowered.com/api/appdetails?appids={appid}'
                       '&filters=basic,release_date,developers')
        data = (json.loads(raw).get(appid) or {}).get('data') or {}
        if data.get('type') != 'game' or STEAM_DEVELOPER not in (data.get('developers') or []):
            continue
        if not (data.get('release_date') or {}).get('coming_soon', True):
            out.append((appid, data['name'], data['release_date'].get('date')))
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


def mobile_live(distribution=DISTRIBUTION):
    """{title: {channel: (public url, needle)}} for production mobile releases only."""
    live = {}
    for g in json.loads(Path(distribution).read_text()).get('games', []):
        for ch, host, key in (('google_play', 'play.google.com/store/apps/details', r'id=([\w.]+)'),
                              ('app_store', 'apps.apple.com/', r'id(\d+)')):
            c = g.get('channels', {}).get(ch) or {}
            url = c.get('url') or ''
            if c.get('state') == 'published' and host in url:
                live.setdefault(g['title'], {})[ch] = (url, re.search(key, url).group(0))
    return live


def mobile_items(pages, projects, live):
    items = []
    for title, chans in live.items():
        needles = [n for _, n in chans.values()]
        page = next((d for d, h in pages.items() if any(n in h for n in needles)), None)
        page = page or find_page(pages, projects, 'mobile', title, None)
        card = card_for(projects, 'mobile', title, page)
        missing = [ch for ch, (_, n) in chans.items() if page is None or n not in pages[page]]
        if page is None or card is None:
            action = 'create'
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


def stale_items(pages, projects, released=None, live=None):
    """Cards for products that are not final yet: testing, review, coming soon.

    A section is judged only when its source was read (None = fetch failed), so a
    Steam or collector outage never takes a released game down."""
    items = []
    if released is not None:
        ids = {a for a, _, _ in released}
        names = {norm(n) for _, n, _ in released}
        for card in projects.get('games', []):
            html = pages.get(card.get('path', '').strip('/'), '')
            linked = set(re.findall(r'store\.steampowered\.com/app/(\d+)', html))
            if not (linked & ids or norm(card['title']) in names):
                items.append({'kind': 'steam', 'action': 'remove', 'title': card['title'],
                              'page': card.get('path', '').strip('/') or None})
    if live is not None:
        needles = [n for chans in live.values() for _, n in chans.values()]
        titles = {norm(t) for t in live}
        for card in projects.get('mobile', []):
            html = pages.get(card.get('path', '').strip('/'), '')
            if not (any(n in html for n in needles) or norm(card['title']) in titles):
                items.append({'kind': 'mobile', 'action': 'remove', 'title': card['title'],
                              'page': card.get('path', '').strip('/') or None})
    return items


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
            try:
                status, _ = fetch(m.group(0))
            except Exception:
                continue
            if status != 200:
                continue
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

    def run(name, fn):
        try:
            return fn()
        except Exception as e:
            errors.append(f'{name}: {type(e).__name__}: {e}'[:300])
            return None

    released = run('steam', steam_released)
    live = run('mobile', mobile_live)
    items += steam_items(pages, projects, released) if released is not None else []
    items += mobile_items(pages, projects, live) if live is not None else []
    for item in stale_items(pages, projects, released, live):
        item['store_refs'] = store_refs(item['page']) if item['page'] else []
        items.append(item)
    items += run('extension', lambda: extension_items(projects)) or []
    items += run('music', music_items) or []
    return items, errors


def key(item):
    return f"{item['kind']}:{item['action']}:{norm(item['title'])}"


def decide(items, errors, state, now):
    """(run?, reason, new_state). Pure, so the retry and error rules are testable."""
    fp = hashlib.sha256('\n'.join(sorted(map(key, items))).encode()).hexdigest()[:16]
    err_days = state.get('error_days', 0) + 1 if errors and not items else 0
    new = dict(state, error_days=err_days)
    if not items:
        if err_days >= ERROR_DAYS:
            new.update(error_days=0, fired_at=now)
            return True, f'scan failing {err_days} days: {"; ".join(errors)}', new
        return False, 'nothing new to publish' + (f' (errors: {"; ".join(errors)})' if errors else ''), new
    age = now - state.get('fired_at', 0)
    if fp == state.get('fingerprint') and age < RETRY_DAYS * 86400:
        return False, f'same {len(items)} item(s) as {int(age // 3600)} h ago; retry after {RETRY_DAYS} d', new
    new.update(fingerprint=fp, fired_at=now)
    return True, f'{len(items)} item(s): ' + ', '.join(map(key, items)), new


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['scan', 'gate'])
    args = ap.parse_args()
    items, errors = scan()
    if args.cmd == 'scan':
        print(json.dumps({'items': items, 'errors': errors}, indent=1, ensure_ascii=False))
        return 1 if errors else 0
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    run, reason, new = decide(items, errors, state, time.time())
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(new) + '\n')
    print(reason)
    return 0 if run else 100


if __name__ == '__main__':
    sys.exit(main())
