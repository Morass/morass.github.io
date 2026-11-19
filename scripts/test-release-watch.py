#!/usr/bin/env python3
"""Offline checks for release_watch: page matching, mobile, music and the gate rules."""
import importlib.util
import json
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('rw', Path(__file__).with_name('release_watch.py'))
rw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rw)

PROJECTS = {
    'games': [{'title': 'Bressnath', 'path': '/bressnath/', 'label': 'Settlement builder · Coming soon'},
              {'title': 'The Concord Quarter', 'path': '/concord/', 'label': 'City-life sim · Steam'}],
    'mobile': [{'title': 'Wardfall', 'path': '/wardfall/', 'label': 'Android & iOS · Google Play & App Store'}],
    'tools': [],
}
PAGES = {
    'bressnath': '<a class="cta"><svg></svg>Coming Soon</a>',
    'concord': '<a href="https://store.steampowered.com/app/4893010/">Get it on Steam</a>',
    'wardfall': 'details?id=games.morass.wardfall',
}

# Steam name differs from the card ("Concord Quarter"): the appid link still finds the page.
assert rw.find_page(PAGES, PROJECTS, 'games', 'Concord Quarter', 'store.steampowered.com/app/4893010') == 'concord'
# A coming-soon page without a store link is found by its card title.
assert rw.find_page(PAGES, PROJECTS, 'games', 'Bressnath', 'store.steampowered.com/app/5268700') == 'bressnath'
assert rw.looks_unreleased(PAGES['bressnath'], PROJECTS['games'][0])
assert not rw.looks_unreleased(PAGES['concord'], PROJECTS['games'][1])
assert rw.find_page(PAGES, PROJECTS, 'games', 'Morrowvane', 'store.steampowered.com/app/1') is None

with tempfile.TemporaryDirectory() as tmp:
    dist = Path(tmp) / 'distribution.json'
    pub = lambda url: {'state': 'published', 'url': url, 'check': {'status': 'ok', 'checked_at': rw.dt.datetime.now(rw.dt.timezone.utc).isoformat()}}
    dist.write_text(json.dumps({'generated_at': rw.dt.datetime.now(rw.dt.timezone.utc).isoformat(), 'sources': {ch: {'status': 'ok'} for ch in ('google_play', 'app_store')}, 'games': [
        {'id': 'wardfall', 'title': 'Wardfall', 'channels': {
            'google_play': pub('https://play.google.com/store/apps/details?id=games.morass.wardfall'),
            'app_store': pub('https://apps.apple.com/app/id6819553168')}},
        {'id': 'curio', 'title': 'Curio Cabinet', 'channels': {
            'google_play': {'state': 'accepted', 'url': 'https://play.google.com/console/', 'check': {'status': 'ok', 'checked_at': rw.dt.datetime.now(rw.dt.timezone.utc).isoformat()}}}},
        {'id': 'hearth', 'title': 'Hearthfields', 'channels': {
            'google_play': pub('https://play.google.com/store/apps/details?id=games.morass.hearthfields')}},
    ]}))
    live = rw.mobile_live(dist)
    got = {i['title']: i['action'] for i in rw.mobile_items(PAGES, PROJECTS, live)}
    # Wardfall lacks its App Store link; a closed test is never listed; a new production app is created.
    assert got == {'Wardfall': 'release', 'Hearthfields': 'create'}, got

    root = Path(tmp)
    (root / 'content').mkdir()
    (root / 'content/music.json').write_text(json.dumps({'albums': [
        {'artist': 'Skralvoss', 'album': 'The Wrack', 'release_date': '2026-11-13'},
        {'artist': 'New Hall', 'album': 'Later', 'release_date': '2026-12-01'},
        {'artist': 'New Hall', 'album': 'Out', 'release_date': '2026-11-01'}]}))
    (root / 'content/music-artists.json').write_text(json.dumps({'artists': [{'name': 'Skralvoss'}]}))
    got = rw.music_items(root, today='2026-11-10')
    assert [(i['title'], i['album']) for i in got] == [('New Hall', 'Out')], got

released = [('4893010', 'Concord Quarter', '27 Jul, 2026')]
got = {(i['kind'], i['title']) for i in rw.stale_items(PAGES, PROJECTS, released, {'Lanternward': {}})}
# Missing discovery evidence must preserve existing pages.
assert got == set(), got
proof = {('steam', 'Bressnath'): [{'appid': '1', 'status': 'coming_soon', 'public_confirmation': True}]}
assert rw.stale_items(PAGES, PROJECTS, confirmations=proof)[0]['title'] == 'Bressnath'
assert rw.stale_items(PAGES, PROJECTS, None, None) == [], 'an unread source never removes a card'

# itch: profile cells become link/create items; a linked page is done; an empty profile is an error.
ITCH_HTML = (
    '<a href="https://morassgames.itch.io/the-concord-quarter" data-label="game:1:title" class="title game_link">The Concord Quarter</a>'
    '<a href="https://morassgames.itch.io/one-more-take" data-label="game:2:title" class="title game_link">One More Take</a>')
real_fetch = rw.fetch
rw.fetch = lambda url, timeout=10: (200, ITCH_HTML)
found = rw.itch_released()
assert found == [('https://morassgames.itch.io/the-concord-quarter', 'The Concord Quarter'),
                 ('https://morassgames.itch.io/one-more-take', 'One More Take')], found
got = {i['title']: i for i in rw.itch_items(PAGES, PROJECTS, found)}
assert got['The Concord Quarter']['action'] == 'link' and got['The Concord Quarter']['page'] == 'concord'
assert got['One More Take']['action'] == 'create' and got['One More Take']['page'] is None
linked = dict(PAGES, concord=PAGES['concord'] + '<a href="https://morassgames.itch.io/the-concord-quarter">itch.io</a>')
assert 'The Concord Quarter' not in {i['title'] for i in rw.itch_items(linked, PROJECTS, found)}
rw.fetch = lambda url, timeout=10: (200, '<html>maintenance</html>')
try:
    rw.itch_released()
    raise AssertionError('an itch page with no games must be an error, not an empty catalogue')
except ValueError:
    pass
rw.fetch = real_fetch

item = [{'kind': 'steam', 'action': 'create', 'title': 'Morrowvane'}]
run, _, st = rw.decide(item, [], {}, 1000)
assert run and any(row['item']['title'] == 'Morrowvane' and row['attempts'] == 1 for row in st['items'].values())
run, why, _ = rw.decide(item, [], st, 1000 + 3600)
assert not run and 'due' in why
run, _, _ = rw.decide(item, [], st, 1000 + 8 * 86400)
assert run, 'unresolved work is retried after RETRY_DAYS'
run, _, st = rw.decide([], [], st, 2000)
assert not run
state = {}
for day in range(rw.ERROR_DAYS):
    run, why, state = rw.decide([], ['steam: URLError'], state, day * 86400)
assert run and 'partial' in why, 'a scan that keeps failing wakes the agent instead of staying silent'
print('release_watch: ok')
