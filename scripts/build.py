#!/usr/bin/env python3
"""Build the public hub from curated projects and the prints export. No dependencies."""
import html
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import print_tags

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://morass.github.io'
P = json.loads((ROOT / 'content/projects.json').read_text())
PRINTS = json.loads((ROOT / 'content/prints.json').read_text())['items']
TAXONOMY = json.loads((ROOT / 'content/print-collections.json').read_text())
VOCAB = print_tags.load(ROOT / 'content/print-tags.json', [t for i in PRINTS for t in i.get('tags', [])])
for item in PRINTS:
    item['tags'] = VOCAB.tags(item.get('tags', []))
TAG_COUNTS = print_tags.counts(PRINTS, VOCAB)
# A tag page needs company; a tag carried by one print links to the search instead.
TAG_PAGES = sorted((t for t, n in TAG_COUNTS.items() if n >= 2), key=lambda t: (-TAG_COUNTS[t], t))
assignments = {}
for collection, identifiers in TAXONOMY['collections'].items():
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*', collection):
        raise ValueError(f'Invalid collection path: {collection}')
    for identifier in identifiers:
        if identifier in assignments:
            raise ValueError(f'Print assigned twice: {identifier}')
        assignments[identifier] = collection
for item in PRINTS:
    collection = item.get('collection') or assignments.get(item['id'])
    if not collection:
        raise ValueError(f"Choose a collection for {item['id']} in content/print-collections.json or model.toml [website].category")
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*', collection):
        raise ValueError(f'Invalid collection path: {collection}')
    item['collection'] = collection
    item['path'] = TAXONOMY.get('modelPaths', {}).get(item['id'], item['id'])
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*', item['path']):
        raise ValueError(f"Invalid model route: {item['path']}")
    if item['path'].split('/')[0] in {'search', 'tags'} or item['collection'].split('/')[0] in {'search', 'tags'}:
        raise ValueError(f"Route reserved for the catalogue itself: {item['path']}")
# A category must never overwrite an existing model page.
leaf_ids = {i['path'] for i in PRINTS}
if len(leaf_ids) != len(PRINTS):
    raise ValueError('Duplicate model URLs')
for item in PRINTS:
    parts = item['collection'].split('/')
    for depth in range(1, len(parts) + 1):
        if '/'.join(parts[:depth]) in leaf_ids:
            raise ValueError(f"Collection collides with a model URL: {item['collection']}")
GENERATED = set()
NAV = [('games', 'Games'), ('small-games', 'Small Games'), ('mobile', 'Mobile'), ('youtube', 'YouTube'), ('prints', 'Prints')]
LABELS = {'boardgames': 'Board games', 'desk': 'Desk & office', 'decorations': 'Decorations', 'containers': 'Boxes & storage', 'bathroom': 'Bathroom', 'kitchen': 'Kitchen', 'home': 'Around the home', 'outdoor': 'Outdoors', 'footwear': 'Footwear', 'general': 'Original & general', 'mtg': 'Magic: The Gathering', 'spirit-island': 'Spirit Island', 'frosthaven': 'Frosthaven'}
LABELS.update({'jewelry':'Jewelry & accessories', 'earrings':'Earrings', 'brooches':'Brooches', 'pendants':'Pendants', 'displays':'Jewelry displays', 'buttons':'Sewing buttons', 'by-game':'Find your game', 'dnd':'Dungeons & Dragons', 'mtg':'Magic: The Gathering', 'original-games':'Original games', 'classic-games':'Classic games', 'dice':'Dice', 'terrain':'Terrain & dungeon tiles', 'tokens-stands':'Tokens & stands', 'card-care':'Deck boxes & card care', 'keepsake-boxes':'Keepsake boxes', 'tools-parts':'Tools & small parts', 'trays-banks':'Catch-alls & coin banks', 'reading-writing':'Reading & writing', 'washing-care':'Washing & personal care', 'toys':'Toys & mechanisms', 'coasters':'Coasters', 'makeup-organizers':'Makeup organizers'})
E = lambda value: html.escape(str(value), quote=True)

def name(part):
    return LABELS.get(part, part.replace('-', ' ').title())

def icon(which):
    return f'<img class="ui-icon" src="/assets/ui/{which}.svg" alt="" width="24" height="24">'

def button(label, url, secondary=False):
    return f'<a class="button{" secondary" if secondary else ""}" href="{E(url)}">{E(label)} <span aria-hidden="true">↗</span></a>'

def site_header(active=""):
    nav = ''.join(f'<a href="/{key}/"'+ (' aria-current="page"' if key == active else '') + f'>{label}</a>' for key, label in NAV)
    return f'<a class="skip" href="#main">Skip to content</a><header class="header"><div class="shell header-inner"><a class="brand" href="/" aria-label="Morass home"><span class="brand-mark" aria-hidden="true">m.</span>MORASS<span class="brand-note">PLAY · MAKE · EXPLORE</span></a><nav aria-label="Main">{nav}</nav><button class="theme-toggle" type="button" aria-label="Switch to light mode" title="Switch to light mode" hidden><svg class="icon-sun" viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.6M12 18.9v2.6M2.5 12h2.6M18.9 12h2.6M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8"/></g></svg><svg class="icon-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 14.6A7.8 7.8 0 0 1 9.4 4.5a7.8 7.8 0 1 0 10.1 10.1Z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M17 4.5l.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6Z" fill="currentColor"/></svg></button></div></header>'

def site_footer():
    return '<footer class="footer shell"><a class="brand" href="/">morass<span class="accent">.</span></a><p>Games, objects and other curiosities.<br>Made with care. Made to be explored.</p><nav aria-label="Footer"><a href="/prints/">Prints</a><a href="/games/">Games</a><a href="/tools/">Tools</a><a href="'+E(P['community']['url'])+'" rel="noopener">Discord</a><a href="/privacy.html">Privacy</a></nav><small>© 2026 Morass</small></footer>'

def page(path, title, description, body, active='', crumbs=None, image='/assets/projects/pyrewarden.webp'):
    target = ROOT / path.strip('/') / 'index.html' if path != '/' else ROOT / 'index.html'
    target.parent.mkdir(parents=True, exist_ok=True)
    breadcrumb = ''
    if crumbs:
        breadcrumb = '<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">Home</a>' + ''.join(f'<span aria-hidden="true">/</span><a href="{E(url)}">{E(label)}</a>' for label, url in crumbs) + '</nav>'
    target.write_text(f'''<!doctype html>
<html lang="en" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)} — Morass</title><meta name="description" content="{E(description)}">
<link rel="canonical" href="{SITE}{path}"><meta property="og:title" content="{E(title)} — Morass"><meta property="og:description" content="{E(description)}"><meta property="og:type" content="website"><meta property="og:url" content="{SITE}{path}"><meta property="og:image" content="{SITE}{image}">
<meta name="theme-color" content="#101713"><script src="/theme.js"></script><link rel="icon" href="/favicon.png"><link rel="stylesheet" href="/hub.css"><script src="/hub.js" defer></script></head>
<body>{site_header(active)}
<main id="main" class="shell">{breadcrumb}{body}</main>{site_footer()}</body></html>''')
    GENERATED.add(str(target.relative_to(ROOT)))

def heading(eyebrow, title, description):
    return f'<header class="page-heading"><p class="eyebrow">{E(eyebrow)}</p><h1>{E(title)}</h1><p class="lede">{E(description)}</p></header>'

def channel_mark(channel, size=96):
    return f'<img class="channel-mark" src="{E(channel["icon"])}" alt="" loading="lazy" width="{size}" height="{size}">'

def card(title, url, summary, image=None, label='', feature=False, art=None):
    if art is None:
        art = f'<img src="{E(image)}" alt="" loading="lazy" width="960" height="600">' if image else f'<div class="art-placeholder">{icon("stamp")}</div>'
    return f'<a class="card{" featured" if feature else ""}" href="{E(url)}"><div class="card-art">{art}<span class="card-arrow" aria-hidden="true">↗</span></div><div class="card-copy"><p class="eyebrow">{E(label)}</p><h2>{E(title)}</h2><p>{E(summary)}</p></div></a>'

def project_cards(key):
    return '<div class="cards">'+''.join(card(p['title'], p['path'], p['summary'], p['image'], p['label']) for p in P[key])+'</div>'

# Small games are bucketed by type; buckets and the games in each are A-Z by title,
# so a new game only needs its entry and its type, never a hand-picked position.
def small_game_sections():
    types = {t['slug']: t for t in P['smallGameTypes']}
    unknown = {g.get('type') for g in P['small-games']} - set(types)
    if unknown:
        raise ValueError(f'Small games reference unknown types: {sorted(map(str, unknown))}')
    out = ''
    for kind in sorted(types.values(), key=lambda t: t['title'].casefold()):
        games = sorted((g for g in P['small-games'] if g['type'] == kind['slug']), key=lambda g: g['title'].casefold())
        if not games:
            continue
        count = f"{len(games)} {'game' if len(games) == 1 else 'games'}"
        out += f'<section id="{E(kind["slug"])}" class="collection"><div class="section-title"><h2>{E(kind["title"])}</h2><span class="section-note">{count}</span></div>'
        out += '<div class="cards">'+''.join(card(g['title'], g['path'], g['summary'], g['image'], kind['label']+' · Play in your browser') for g in games)+'</div></section>'
    return out

def print_image(item):
    return item.get('image')

def tag_url(tag):
    return f'/prints/tags/{tag}/' if TAG_COUNTS.get(tag, 0) >= 2 else f'/prints/search/?tag={tag}'

def tag_chip(tag, count=False):
    label = VOCAB.label(tag)
    extra = f' <span class="tag-count">{TAG_COUNTS[tag]}</span>' if count else ''
    return f'<a class="tag" href="{E(tag_url(tag))}">{E(label)}{extra}</a>'

def tag_list(tags, lead='Tagged', count=False):
    if not tags:
        return ''
    return f'<div class="tag-list"><span>{E(lead)}</span>' + ''.join(tag_chip(t, count) for t in tags) + '</div>'

def sync_authored_page(relative, active):
    target = ROOT / relative
    source = target.read_text()
    start, end = '<!-- shared-header:start -->', '<!-- shared-header:end -->'
    shared_header = start + site_header(active) + end
    shared_footer = '<!-- shared-footer:start -->' + site_footer() + '<!-- shared-footer:end -->'
    if start in source:
        source = re.sub(r'<!-- shared-header:start -->.*?<!-- shared-header:end -->', lambda _: shared_header, source, flags=re.S)
        source = re.sub(r'<!-- shared-footer:start -->.*?<!-- shared-footer:end -->', lambda _: shared_footer, source, flags=re.S)
    else:
        source = source.replace('<html lang="en">', '<html lang="en" data-theme="dark">')
        source = source.replace('<body>', '<body class="game-site">')
        source = source.replace('<link rel="stylesheet"', '<meta name="theme-color" content="#101713"><script src="/theme.js"></script>\n<link rel="stylesheet"', 1)
        source = source.replace('</head>', '<link rel="stylesheet" href="/hub.css"><script src="/hub.js" defer></script>\n</head>')
        if relative == 'privacy.html':
            source = source.replace('<body class="game-site">', '<body class="game-site">' + shared_header)
            source = source.replace('<main class="container game-section" style="max-width:800px">', '<main id="main" class="shell legal-page">')
            source = source.replace('</body>', shared_footer + '</body>')
        else:
            source = re.sub(r'<nav class="site-nav">.*?</nav>', lambda _: shared_header, source, count=1, flags=re.S)
            label = dict(NAV)[active]
            trail = '<main id="main" class="game-detail"><nav class="breadcrumbs shell" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true">/</span><a href="/' + active + '/">' + label + '</a></nav>'
            source = re.sub(r'<div class="container project-trail">.*?</div>', lambda _: trail, source, count=1, flags=re.S)
            if '<h1' not in source:
                title = next(project['title'] for project in P[active] if project['path'].strip('/') == relative.split('/')[0])
                source = source.replace('<section class="game-hero">', '<h1 class="visually-hidden">' + E(title) + '</h1><section class="game-hero">', 1)
            source = re.sub(r'<footer class="site-footer">.*?</footer>', lambda _: '</main>' + shared_footer, source, count=1, flags=re.S)
    target.write_text(source)

for group in ['games', 'mobile']:
    for project in P[group]:
        sync_authored_page(project['path'].strip('/') + '/index.html', group)
sync_authored_page('privacy.html', 'mobile')

# Homepage: five distinct destinations, each with its own collection.
print_cover = next((i for i in PRINTS if i['id'] == 'containers/pirate-chest'), PRINTS[0])
home = '<section id="explore" class="collection home-crossroads"><div class="section-title"><div><p class="eyebrow">THE MORASS COLLECTION</p><h1>Explore the projects.</h1></div><span class="section-note">Games. Prints. Stories.</span></div><div class="crossroads">'
home += card('Games', '/games/', 'Strategy, strange worlds and stories worth getting lost in. Explore the Steam collection.', '/assets/projects/pyrewarden.webp', 'I · GAMES ON STEAM', True)
home += card('Prints', '/prints/', 'Useful objects, playful mechanisms and tabletop companions. Find something to make.', print_image(print_cover), 'II · PRINTS', True)
home += card('Small Games', '/small-games/', 'A little play, straight from your browser.', '/assets/projects/borrowed-ink.webp', 'III · NO INSTALL NEEDED')
home += card('Mobile', '/mobile/', 'Games and projects made for your pocket.', '/assets/projects/lanternward.webp', 'IV · ANDROID')
home += card('YouTube', '/youtube/', 'Stories, objects and a look behind the projects.', label='V · WATCH & DISCOVER', art='<div class="channel-marks">'+''.join(channel_mark(c) for c in P['channels'])+'</div>')
home += '</div></section>'
# A quiet sixth destination: free tools are not a project family, so a band, not a card.
home += '<section class="home-tools"><div><p class="eyebrow">VI · FREE TOOLS</p><h2>Small tools, free to use.</h2><p>A command-line tool and a handful of Neovim plugins, all open source.</p></div><a class="button secondary" href="/tools/">See the tools <span aria-hidden="true">→</span></a></section>'
page('/', 'Games, prints & curious projects', 'Explore Morass: Steam games, free browser puzzles, Android projects, YouTube and an organized catalogue of 3D prints.', home)
for key, title, description in [
    ('games', 'Worlds worth getting lost in.', 'The Morass Games collection. Strategy, survival and stories on Steam.'),
    ('small-games', 'Small games. Good company.', 'Thoughtful little games you can play right here, in your browser.'),
    ('mobile', 'A little wonder, to go.', 'Games and projects for Android. Explore what is taking shape.')]:
    body = heading(dict(NAV)[key], title, description) + (small_game_sections() if key == 'small-games' else project_cards(key))
    if key == 'games': body += '<div class="section-end">'+button('Explore Morass on Steam', 'https://store.steampowered.com/search/?developer=Morass', True)+'<p class="small-note">Playing one of them? Come say hello in the <a href="'+E(P['community']['url'])+'" rel="noopener">'+E(P['community']['label'])+'</a>.</p></div>'
    page('/'+key+'/', dict(NAV)[key], description, body, key, [(dict(NAV)[key], '/'+key+'/')])

body = heading('YOUTUBE', 'A closer look.', 'Stories and making, from the Morass collection.')
body += '<div class="channel-list">'
for channel in P['channels']:
    body += f'<article class="channel">{channel_mark(channel)}<div><p class="eyebrow">{E(channel["label"])}</p><h2>{E(channel["title"])}</h2><p>{E(channel["summary"])}</p></div>{button("Visit the channel",channel["url"])}</article>'
body += '</div>'
page('/youtube/', 'YouTube', 'Watch stories and making from Morass.', body, 'youtube', [('YouTube','/youtube/')])

# Free tools: one section, split into groups like the print collection.
unknown = {t['group'] for t in P['tools']} - {g['slug'] for g in P['toolGroups']}
if unknown:
    raise ValueError(f'Tools reference unknown groups: {sorted(unknown)}')
def tool_mark(group):
    return f'<div class="tool-mark-art"><span class="tool-mark">{E(group["mark"])}</span></div>'
def tool_inline_mark(tool, group):
    if icon_path := tool.get('icon'):
        return f'<div class="tool-mark-inline"><img class="tool-app-icon" src="{E(icon_path)}" alt="" loading="lazy" width="64" height="64"></div>'
    return tool_mark(group).replace('tool-mark-art', 'tool-mark-inline')
body = heading('FREE TOOLS', 'Small tools, free to use.', 'Open-source apps, command-line tools and Neovim plugins. Use them, change them, share them.')
body += '<div class="cards tool-cards">'
for group in P['toolGroups']:
    count = sum(t['group'] == group['slug'] for t in P['tools'])
    body += card(group['title'], f"/tools/{group['slug']}/", group['summary'], label=f"{count} {'tool' if count == 1 else 'tools'}", art=tool_mark(group))
body += '</div>'
page('/tools/', 'Free tools', 'Free, open-source command-line tools and Neovim plugins by Morass.', body, 'tools', [('Free tools','/tools/')])
for group in P['toolGroups']:
    body = heading('FREE TOOLS · ' + group['title'], group['title'] + '.', group['summary']) + '<div class="channel-list">'
    for tool in (t for t in P['tools'] if t['group'] == group['slug']):
        body += f'<article class="channel tool">{tool_inline_mark(tool, group)}<div><p class="eyebrow">{E(tool["label"])}</p><h2>{E(tool["title"])}</h2><p>{E(tool["summary"])}</p></div>{button("View on GitHub", tool["url"], True)}</article>'
    body += '</div>'
    page(f"/tools/{group['slug']}/", group['title'] + ' — Free tools', group['summary'], body, 'tools', [('Free tools','/tools/'), (group['title'], f"/tools/{group['slug']}/")])

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Minesweeper', 'The first stone is always safe. Never a 50/50.')+button('Play now', 'https://morassgames.com/games/minesweeper/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/minesweeper.webp" width="1200" height="675" alt="A minesweeper board in a lamplit stone gallery"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Read the floor.</h2><ol><li>Open every safe stone. A number is how many charges touch it.</li><li>The first stone is always a blank opening. Flag the charges and clear the rest.</li></ol><p>Three classic sizes. Every floor is proven finishable without a guess.</p></section>'
page('/small-games/minesweeper/', 'Minesweeper', 'Free minesweeper: first click always safe, never a 50/50. Field, Vault and Deep.', body, 'small-games', [('Small Games','/small-games/'),('Minesweeper','/small-games/minesweeper/')], '/assets/projects/minesweeper.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Sliding Puzzle', 'Every board tells you exactly how deep it is.')+button('Play now', 'https://morassgames.com/games/sliding-puzzle/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/sliding-puzzle.webp" width="1200" height="675" alt="A sliding puzzle of slate rune-stones mid-scramble on a candlelit archive desk"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Set the stones home.</h2><ol><li>Tap any stone in the gap\'s row or column — it and the stones between slide.</li><li>Order the tablet 1, 2, 3… ending at the empty socket.</li></ol><p>Thirty fixed boards across Slate 3×3, Tablet 4×4 and Gate 5×5, plus a daily. Every board is solver-verified and tells you its measured shortest solution.</p></section>'
page('/small-games/sliding-puzzle/', 'Sliding Puzzle', 'Free sliding tile puzzle (15 puzzle) with 30 measured boards and a daily. Every board solver-verified.', body, 'small-games', [('Small Games','/small-games/'),('Sliding Puzzle','/small-games/sliding-puzzle/')], '/assets/projects/sliding-puzzle.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Nonogram', 'Fill the grid, find the picture. Never a guess.')+button('Play now', 'https://morassgames.com/games/nonogram/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/nonogram.webp" width="1200" height="675" alt="A parchment nonogram revealing a howling wolf, beside a candlelit writing desk"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Find the picture.</h2><ol><li>The numbers are the runs of filled cells in each row and column.</li><li>Tap or drag to fill; cross cells you know are empty.</li></ol><p>240 pictures in eight folios plus a daily. One folio is drawn from The Cistern Heresy.</p></section>'
page('/small-games/nonogram/', 'Nonogram', 'Free nonograms: 240 hand-drawn fantasy pictures and a daily. Every board solvable by logic.', body, 'small-games', [('Small Games','/small-games/'),('Nonogram','/small-games/nonogram/')], '/assets/projects/nonogram.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Sudoku', 'One answer to every board. Never a guess.')+button('Play now', 'https://morassgames.com/games/sudoku/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/sudoku.webp" width="1200" height="675" alt="A parchment sudoku board before glowing standing stones under two moons"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Fill the grid.</h2><ol><li>Every row, column and 3×3 box holds 1–9 once.</li><li>Tap a cell, then a number.</li></ol><p>480 boards in four tiers plus a daily.</p></section>'
page('/small-games/sudoku/', 'Sudoku', 'Free sudoku with 480 boards and a daily. One answer each, never a guess.', body, 'small-games', [('Small Games','/small-games/'),('Sudoku','/small-games/sudoku/')], '/assets/projects/sudoku.webp')
body = '<p>Ninefold is now <a href="/small-games/sudoku/">Sudoku</a>.</p><meta http-equiv="refresh" content="0;url=/small-games/sudoku/">'
page('/small-games/ninefold/', 'Sudoku', 'Ninefold is now Sudoku.', body, 'small-games', [('Small Games','/small-games/'),('Sudoku','/small-games/sudoku/')], '/assets/projects/sudoku.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Borrowed Ink', 'A little stamp. A sheet of paper. Thirty gentle puzzles about moving ink.')+button('Play now', 'https://morassgames.com/games/borrowed-ink/')+' <a class="button secondary" href="https://www.crazygames.com/game/borrowed-ink" rel="noopener">Play on CrazyGames <span aria-hidden="true">↗</span></a><p class="small-note">Free to play · No account · Plays on morassgames.com and CrazyGames</p></div><img src="/assets/projects/borrowed-ink.webp" width="960" height="600" alt="The Borrowed Ink puzzle desk"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Make an impression.</h2><ol><li>Select two neighboring cells on the paper.</li><li>Press <strong>Make impression</strong> to exchange the ink in those cells with the stamp.</li><li>Match the target picture and leave the stamp empty.</li></ol><p>Turn the stamp to switch between horizontal and vertical pairs. Undo, restart and hints are always free. Your progress is saved in this browser.</p><p class="small-note">Keyboard: arrows to move, Enter to select, Space to press, R to turn, Z to undo, H for a hint.</p></section>'
page('/small-games/borrowed-ink/', 'Borrowed Ink', 'Play a gentle, free ink-exchange puzzle with thirty levels. No download, account or ads.', body, 'small-games', [('Small Games','/small-games/'),('Borrowed Ink','/small-games/borrowed-ink/')], '/assets/projects/borrowed-ink.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Block Fit', 'Every tablet fits back together exactly one way.')+button('Play now', 'https://morassgames.com/games/block-fit/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/block-fit.webp" width="1200" height="675" alt="A broken warding tablet of stone shards being fitted back together in a candlelit ritual chamber"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Mend the broken ward.</h2><ol><li>Drag a shard onto the tablet — the outline shows the slot it will drop into.</li><li>Fill every square with no gaps and no overlaps. Shards never turn.</li></ol><p>Forty-eight tablets across four sizes plus a daily. Every board is proved to fit together exactly one way, and each keeps a public best time.</p></section>'
page('/small-games/block-fit/', 'Block Fit', 'Free shape-packing puzzle: 48 tablets and a daily, every one proved to fit together exactly one way.', body, 'small-games', [('Small Games','/small-games/'),('Block Fit','/small-games/block-fit/')], '/assets/projects/block-fit.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Tetromino', 'The falling-block puzzle, cut in stone.')+button('Play now', 'https://morassgames.com/games/tetromino/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/tetromino.webp" width="1200" height="675" alt="Seven coloured stone shapes stacked in a runed descent shaft, one falling above its ghost outline"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Fill a course and it goes.</h2><ol><li>Slide, turn and drop the seven shapes into the shaft.</li><li>Fill a row across and it settles and clears; four at once pays the most.</li><li>The run ends when a shape has nowhere left to arrive.</li></ol><p>It plays by the published rules — seven-bag, SRS wall kicks, hold, ghost and a lock delay you can wiggle in. Three modes: Marathon, Sprint over forty lines, and two-minute Ultra. Each keeps the ten best runs, with the name of whoever set them, and every one of those ten is a replay you can watch.</p></section>'
page('/small-games/tetromino/', 'Tetromino', 'Free falling-block puzzle by the published rules: Marathon, Sprint and Ultra, with a watchable top ten.', body, 'small-games', [('Small Games','/small-games/'),('Tetromino','/small-games/tetromino/')], '/assets/projects/tetromino.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Mahjong', 'Thirty tables of wardstones, and every deal can be cleared.')+button('Play now', 'https://morassgames.com/games/mahjong/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/mahjong.webp" width="1200" height="675" alt="A stack of carved wardstone tiles laid out on a lamplit counting table, one tile lifted and its matches glowing"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Take two stones that match.</h2><ol><li>A stone can be taken when nothing rests on it and its left or right side is clear.</li><li>Pick one and every stone that would match it glows. Take the pair and they lift off.</li><li>Clear the whole table. There is no clock against you and no way to lose.</li></ol><p>Thirty hand-built layouts from a thirty-six-stone cairn to the hundred-and-forty-four-stone Shell, plus a new table every day, each with a public best time. Every deal is built backwards from a finish and replayed through the rules to prove it empties — so there is no shuffle button, and undo is free and unlimited.</p></section>'
page('/small-games/mahjong/', 'Mahjong', 'Free mahjong solitaire: 30 layouts and a daily, every deal proved solvable. No shuffle, unlimited undo.', body, 'small-games', [('Small Games','/small-games/'),('Mahjong','/small-games/mahjong/')], '/assets/projects/mahjong.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Match Three', 'The chutes show what falls next, so a cascade is something you build.')+button('Play now', 'https://morassgames.com/games/match-three/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/match-three.webp" width="1200" height="675" alt="Seven kinds of cut gem in an eight-by-eight frame on a lamplit workshop bench, with the next stones for each column shown in chutes above it"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Line up three of a kind.</h2><ol><li>Tap a stone and then its neighbour, or drag one at the other, to swap them.</li><li>Three or more in a row or a column flare and go; the column falls and the chutes feed it.</li><li>Read the chutes — the stone you can see coming is the one that finishes the line you are about to open.</li></ol><p>Four in a line leaves a Burst, an L or a T leaves a Star, and five leaves a Prism that takes a whole colour off the bench. Four ways to play: Endless (with three free shuffles when the bench runs out of swaps), a sixty-second run, thirty swaps with no clock, and one daily bench everybody shares. Each keeps the ten best runs with the name of whoever set them, and every one of those ten is a replay you can watch.</p></section>'
page('/small-games/match-three/', 'Match Three', 'Free match-three gem puzzle with a visible refill queue: Endless, One Minute, Thirty Moves and a daily bench.', body, 'small-games', [('Small Games','/small-games/'),('Match Three','/small-games/match-three/')], '/assets/projects/match-three.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / CARD GAME', 'Solitaire', 'A warden\'s Klondike table, dealt fairly and proved finishable.')+button('Play now', 'https://morassgames.com/games/solitaire/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/solitaire.webp" width="1200" height="675" alt="A fantasy Klondike solitaire table of parchment cards, brass fittings and blue wardlight in a stone counting room"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Set every suit home.</h2><ol><li>Build the seven columns downward, alternating red and black.</li><li>Turn the stock and send each suit home from ace through king.</li><li>Open every covered card; an empty column takes a king.</li></ol><p>Choose Draw 1 or Draw 3 across 120 shuffled tables. Every deal is solver-proved from its opening layout. Undo is unlimited, and a hint is always close at hand.</p></section>'
page('/small-games/solitaire/', 'Solitaire', 'Free Klondike solitaire with 120 shuffled, solver-proved deals in Draw 1 and Draw 3.', body, 'small-games', [('Small Games','/small-games/'),('Solitaire','/small-games/solitaire/')], '/assets/projects/solitaire.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / CARD GAME', 'FreeCell', 'Every card face up. Four cells for what will not fit yet.')+button('Play now', 'https://morassgames.com/games/freecell/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/freecell.webp" width="1200" height="675" alt="A FreeCell table in a stone warden\'s room: eight columns of face-up parchment cards, four empty cells and four suit foundations along the top, one card lifted and outlined in gold"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Send every suit home, ace to king.</h2><ol><li>Columns pack downward in alternating colours, and an empty column takes any card.</li><li>The four cells each hold one card \u2014 deciding what goes in them is the whole game.</li><li>An ordered run travels as one, as far as the free cells and empty columns can carry it.</li></ol><p>A thousand of the real numbered deals, so deal 617 here is deal 617 anywhere else \u2014 and every one of them solved before it shipped. Four difficulty tiers, a new deal each day, and a best time and fewest moves kept on every deal.</p></section>'
page('/small-games/freecell/', 'FreeCell', 'Free FreeCell solitaire with 1,000 of the real numbered Microsoft deals, every one proved winnable.', body, 'small-games', [('Small Games','/small-games/'),('FreeCell','/small-games/freecell/')], '/assets/projects/freecell.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / CARD GAME', 'Hearts', 'Three opponents that cannot see your cards.')+button('Play now', 'https://morassgames.com/games/hearts/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/hearts.webp" width="1200" height="675" alt="A Hearts table in a stone warden\'s room: three parchment cards played into the middle of a lamplit table, the player\'s thirteen cards fanned below with the clubs bright and the rest dimmed"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Take as few points as you can.</h2><ol><li>Pass three cards \u2014 left, then right, then across, then none \u2014 and then follow suit if you can.</li><li>Every heart costs 1 and the queen of spades costs 13. Lowest score wins.</li><li>Take all twenty-six in one hand and you shoot the moon: everybody else takes them instead.</li></ol><p>Every Hearts game is accused of cheating, so this one can be checked. The three opponents are given their own thirteen cards and the cards already played, and nothing else \u2014 not your hand, and not each other\'s. When a hand ends you can open the table, turn all four hands face up and read the reason each seat recorded for every card it played. Three strengths to beat, and a Deal of the Day that gives everybody the same cards and the same opponents, so the ten best scores are ten ways of playing it.</p></section>'
page('/small-games/hearts/', 'Hearts', 'Free Hearts card game against three opponents that cannot see your hand, with a shared daily deal and a top ten.', body, 'small-games', [('Small Games','/small-games/'),('Hearts','/small-games/hearts/')], '/assets/projects/hearts.webp')
body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Bubble Shooter', 'Read the ricochet. Break the anchor. Drop the vault.')+button('Play now', 'https://morassgames.com/games/bubble-shooter/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/bubble-shooter.webp" width="1200" height="675" alt="Jewel-like glass wards with distinct engraved sigils hanging in an Aurensh observatory above a brass launcher and a reflected aiming path"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Bring the hanging vault down.</h2><ol><li>Drag to aim and release to fire; the complete reflected path and landing socket are shown first.</li><li>Join three wards with the same colour and sigil. Anything cut away from the ceiling falls.</li><li>Five misses lower the vault. Clear it before the glass reaches the brass line.</li></ol><p>Thirty-six deterministic chambers across three observatory books plus a daily vault. Every board is replay-cleared before it ships and keeps fastest time and fewest shots.</p></section>'
page('/small-games/bubble-shooter/', 'Bubble Shooter', 'Free fantasy bubble shooter with 36 proved chambers, real bank-shot previews and a daily vault.', body, 'small-games', [('Small Games','/small-games/'),('Bubble Shooter','/small-games/bubble-shooter/')], '/assets/projects/bubble-shooter.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Marble Shooter', 'Break the rune-chain. Close the gap. Pull it back from the breach.')+button('Play now', 'https://morassgames.com/games/marble-shooter/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/marble-shooter.webp" width="1200" height="675" alt="A moving chain of colourful engraved rune-stones winding around a dark brass Aurensh circuit-table, with a central launcher aimed at one stone and a red breach at the end"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Break the chain before it reaches the breach.</h2><ol><li>Point at the moving chain and fire the loaded rune into it.</li><li>Join three runes with the same colour and engraving. Matching ends across the gap snap together, recoil and may break again.</li><li>Swap the loaded and next rune when the next shot makes a better chain. Clear every rune before the leader enters the red seal.</li></ol><p>Twelve authored circuits are open from the start, each solver-checked and each keeping independent records for fastest time and fewest shots. Every colour carries a different engraved shape.</p></section>'
page('/small-games/marble-shooter/', 'Marble Shooter', 'Free fantasy marble-chain shooter with twelve open, solver-checked circuits and separate time and shots records.', body, 'small-games', [('Small Games','/small-games/'),('Marble Shooter','/small-games/marble-shooter/')], '/assets/projects/marble-shooter.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / ARCADE', 'Snake', 'Gather the motes. The floor you have crossed is the only thing that can stop you.')+button('Play now', 'https://morassgames.com/games/snake/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/snake.webp" width="1200" height="675" alt="A glowing green ward-serpent coiled across a dark stone chamber floor, with a burning mote of light ahead of it and lit seams in the walls"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Grow without crossing yourself.</h2><ol><li>Arrows, WASD, a swipe or the four ward-stones turn the serpent; it never stops on its own.</li><li>Every mote makes it one segment longer and a little quicker.</li><li>Sealed walls end the run. Seamed walls carry the light out of the opposite side.</li></ol><p>Three chamber sizes \u2014 11\u00d711, 17\u00d717 and 23\u00d723 \u2014 each played sealed or seamed, and each of the six keeps its own board of the ten best runs. The record is the number of motes, and a tie keeps the older holder.</p></section>'
page('/small-games/snake/', 'Snake', 'Free fantasy snake with three chamber sizes, walls or wrapping seams, and six public boards of ten.', body, 'small-games', [('Small Games','/small-games/'),('Snake','/small-games/snake/')], '/assets/projects/snake.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / ARCADE', 'Brick Breaker', 'The shield never breaks anything. It only holds \u2014 and the spark does the rest.')+button('Play now', 'https://morassgames.com/games/brick-breaker/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/brick-breaker.webp" width="1200" height="675" alt="A lamplit armoury of plate harnesses and spears, with a tall warded vault cut into it: courses of copper and steel plates part-broken, a white forge-spark among them, and a glowing shield held at the foot of the field"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Break every ward and the vault opens.</h2><ol><li>Slide the shield with the mouse, the arrow keys or a finger anywhere on the field; click, tap or press Space to send the spark.</li><li>Where you catch it is how you aim it: the middle sends it up, the edges send it out.</li><li>Every ward broken before the spark comes home is worth one more multiple, to nine. Touch the shield and the heat is back to one.</li></ol><p>Sixteen hand-cut vaults in four tiers, a vault of the day and an endless Deepening on a single spark. No power-downs \u2014 every sigil is good. Nineteen public boards of ten, and nothing sends a score: a finished run is sent as its replay and played again on the server, so any place can be watched.</p></section>'
page('/small-games/brick-breaker/', 'Brick Breaker', 'Free fantasy brick breaker with sixteen hand-cut vaults, no power-downs, a heat multiplier and nineteen public boards of ten.', body, 'small-games', [('Small Games','/small-games/'),('Brick Breaker','/small-games/brick-breaker/')], '/assets/projects/brick-breaker.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / ARCADE', 'Space Shooter', 'The two moons are not empty. Take the moonwing into the storm lanes.')+button('Play now', 'https://morassgames.com/games/space-shooter/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/space-shooter.webp" width="1200" height="675" alt="A gold and cyan winged moon instrument firing through violet spellfire beneath two moons and a lightning storm"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Break every flock. Bring down its captain.</h2><ol><li>Move the moonwing with a mouse, finger, arrow keys or WASD; it fires by itself.</li><li>Dodge violet spells. Near misses charge Ward Burst — unleash it at 100% with Space or its plate.</li><li>Keep one of five hearts and destroy the captain to hold the skyroad.</li></ol><p>Twenty-four short, deterministic sorties cross Harbour Crown, Aevir Reach, Mareth Gale and the Wrong Sky. Each keeps its own fastest time. No upgrades, bought power or grind: every victory is flown with the same moonwing.</p></section>'
page('/small-games/space-shooter/', 'Space Shooter', 'Free fantasy space shooter with twenty-four finite sorties, keyboard, mouse and touch controls, and a fastest-time record on each.', body, 'small-games', [('Small Games','/small-games/'),('Space Shooter','/small-games/space-shooter/')], '/assets/projects/space-shooter.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', '2048', 'Slide the forge. Join equal embers. Wake the Phoenix.')+button('Play now', 'https://morassgames.com/games/2048/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/2048.webp" width="1200" height="675" alt="A firelit four-by-four 2048 board holding glowing numbered embers, coal and flame on an artisan workshop table"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Forge 2048.</h2><ol><li>Swipe, press an arrow or WASD, or tap a direction plate to slide every tile together.</li><li>Equal values fuse once during a move, and every accepted move raises one new ember.</li><li>Climb from Ember through Flame, Beacon and Starfire to forge the Phoenix at 2048 — then keep going if you wish.</li></ol><p>The exact classic four-by-four rules, rebuilt as a physical ember forge with carved sigils, moving tiles, impact sounds and a personal best that stays in this browser. No timer and no public board.</p></section>'
page('/small-games/2048/', '2048', 'Free fantasy 2048 with exact classic rules, keyboard, touch and mouse controls, and a personal best saved in this browser.', body, 'small-games', [('Small Games','/small-games/'),('2048','/small-games/2048/')], '/assets/projects/2048.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Water Sort', 'Separate the reagents. Leave every phial pure.')+button('Play now', 'https://morassgames.com/games/water-sort/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/water-sort.webp" width="1200" height="675" alt="A lamplit alchemist table holding glass phials layered with bright coloured reagents"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Purify every phial.</h2><ol><li>Choose a phial, then an empty one or one whose top colour matches.</li><li>The whole matching band pours, up to the free space. Use the empty glass as room to rearrange the layers.</li><li>Finish with every filled phial holding one colour from top to bottom.</li></ol><p>All 120 formulae are open from the beginning, in six shelves from three to eight reagents. Every opening was made backwards from a solved rack and its route home replayed through the shipped rules. Each formula keeps separate public records for fastest time and fewest moves.</p></section>'
page('/small-games/water-sort/', 'Water Sort', 'Free fantasy Water Sort with 120 open, proven-completable levels, animated alchemical pours, and public time and move records.', body, 'small-games', [('Small Games','/small-games/'),('Water Sort','/small-games/water-sort/')], '/assets/projects/water-sort.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Sokoban', 'Enter the Compact Vaults. Restore every broken seal.')+button('Play now', 'https://morassgames.com/games/sokoban/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/sokoban.webp" width="1200" height="675" alt="A fantasy Sokoban vault with a Warden, two green rune stones and two glowing violet binding circles"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Bind every reliquary.</h2><ol><li>Walk with arrows or WASD, tap a reachable floor square, or use the touch direction plates.</li><li>Push each green reliquary onto a violet binding circle. You may push one stone into an empty square, but never pull it.</li><li>Choose any of the seventy-two open chambers. Undo and restart freely when a stone is trapped.</li></ol><p>Six vault tiers rise from the Threshold to the Last Binding. Every chamber was generated backwards from a solved seal and independently solved forwards through the shipped rules. Each keeps separate public records for fastest time and fewest steps, with the holder’s name beside the trophy.</p></section>'
page('/small-games/sokoban/', 'Sokoban', 'Free fantasy Sokoban with 72 open, solver-proven chambers, keyboard and touch play, and public time and step records.', body, 'small-games', [('Small Games','/small-games/'),('Sokoban','/small-games/sokoban/')], '/assets/projects/sokoban.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Pairs', 'Turn two marks. If they are the same ward they stay; if not, they wait for you.')+button('Play now', 'https://morassgames.com/games/pairs/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/pairs.webp" width="1200" height="675" alt="A dark lamplit sorting table holding a grid of carved wardstones: several turned face up and ringed in gold, two just turned in the middle of a move, the rest face down and marked with a single incised letter"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Pair every mark on the table.</h2><ol><li>Click, tap or arrow to a mark and turn it, then turn another.</li><li>The same ward and the pair seals and stays face up, so the map in your head is never taken away.</li><li>Different, and they stay up until you turn your next mark \u2014 there is no flip-back timer to sit through, and nothing on this table ever waits for you.</li></ol><p>Six trays, from twelve marks to seventy-two. No score and no way to lose: two numbers, moves and time, and on both of them lower is better. Each tray keeps a public board of ten for each, and nothing sends a number \u2014 a finished run is sent as its replay and played again on the server. Afterwards the game replays your own deal against a reader who never forgets, and tells you what it cost them.</p></section>'
page('/small-games/pairs/', 'Pairs', 'Free fantasy memory matching game with six tray sizes, no flip-back timer, and twelve public boards of ten.', body, 'small-games', [('Small Games','/small-games/'),('Pairs','/small-games/pairs/')], '/assets/projects/pairs.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Jigsaw', 'Set the shards of a broken pane back into the lead. Drop one near its place and it takes.')+button('Play now', 'https://morassgames.com/games/jigsaw/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/jigsaw.webp" width="1200" height="675" alt="A glazier\u2019s bench in lamplight: a leaded frame two-thirds filled with a painted spice bazaar, the lead lines still showing between the shards, and the remaining shards lying loose on the bench beside it"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Make the pane whole again.</h2><ol><li>Pick a picture and a cut, and drag a shard towards where it belongs.</li><li>Near is near enough: let it go anywhere close and it takes, with a click, and nothing you do afterwards can knock it out.</li><li>A shard dropped anywhere else stays exactly where you put it, so you can sort the bench into colours and it will keep.</li></ol><p>Two hundred and twenty-eight painted places on nine shelves, at four leaded cuts \u2014 six shards to ninety-six \u2014 and a fresh scramble and a fresh cut every time. No rotation, no zoom and nothing too small to grab; no advertisement between you and the piece you were placing. Leave, reload, or lose the tab and the pane is waiting with every shard where you left it. Nine hundred and twelve public boards of ten, and nothing sends a number: a finished pane is sent as its replay and set again on the server.</p></section>'
page('/small-games/jigsaw/', 'Jigsaw', 'Free fantasy jigsaw puzzle: 228 painted panes, four cuts to ninety-six shards, pieces that stick, and a board that survives a closed tab.', body, 'small-games', [('Small Games','/small-games/'),('Jigsaw','/small-games/jigsaw/')], '/assets/projects/jigsaw.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Kakuro', 'A crossword of sums: every run adds up to the figure at its head, and never repeats a digit.')+button('Play now', 'https://morassgames.com/games/kakuro/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/kakuro.webp" width="1200" height="675" alt="A kakuro page on a scrivener\u2019s desk by candlelight: a grid of pale paper cells part-filled with digits, grey clue cells carrying two figures each side of a diagonal, and the entries that already add up marked in green"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Make every run add up.</h2><ol><li>Every white cell takes a digit from 1 to 9.</li><li>A run of white cells adds up to the figure at its head \u2014 above the diagonal for the run going right, below it for the run going down.</li><li>No digit appears twice in one run. That is what makes a sum a short list: a 3-in-two can only be 1 and 2, a 16-in-two only 7 and 9.</li></ol><p>Three hundred and twenty pages in five sizes, from a three-minute Tally to a half-hour Reckoning, plus one shared page a day. Every page has exactly one answer and can be finished by reasoning alone \u2014 no page here ever needs a guess. Tap a clue and it prints every combination it can be, straight out of the back of the book; a digit already spent in a run is struck through on the keypad; and a run that is full and is not right says so in its own figure. Nothing else is told to you: the page does not hold the answer to itself. Each page keeps a public best time, and the one you are in the middle of is still there when you come back.</p></section>'
page('/small-games/kakuro/', 'Kakuro', 'Free kakuro (cross sums): 320 pages in five sizes plus a daily, every one solvable with no guessing, and a public best time on every page.', body, 'small-games', [('Small Games','/small-games/'),('Kakuro','/small-games/kakuro/')], '/assets/projects/kakuro.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / WORD', 'Word Search', 'Trace the hidden words. Illuminate every page.')+button('Play now', 'https://morassgames.com/games/word-search/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/word-search.webp" width="1200" height="675" alt="A fantasy word-search manuscript glowing on a desk inside an immense enchanted library"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Illuminate the archive.</h2><ol><li>Choose any page and read its themed word list.</li><li>Drag from the first letter to the last in a straight horizontal, vertical or diagonal line.</li><li>Find every word to complete the page; later folios hide words forwards and backwards in all eight directions.</li></ol><p>Forty-eight open English-themed pages grow from 9 by 9 with five words to 14 by 14 with fourteen. Every page is regenerated and independently scanned during the build: every listed word must appear exactly once, and every stored placement must finish through the shipping rules. Each page keeps a public fastest time and top ten.</p></section>'
page('/small-games/word-search/', 'Word Search', 'Free fantasy Word Search with 48 open English-themed pages, all algorithmically verified, and a public fastest time on every page.', body, 'small-games', [('Small Games','/small-games/'),('Word Search','/small-games/word-search/')], '/assets/projects/word-search.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / CARD', 'Pyramid Solitaire', 'Pair to thirteen. Unbind the pyramid.')+button('Play now', 'https://morassgames.com/games/pyramid-solitaire/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/pyramid-solitaire.webp" width="1200" height="675" alt="A fantasy Pyramid Solitaire table with seven overlapping rows of cards inside a brass constellation frame"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Clear the Moon Archivist’s table.</h2><ol><li>Select two exposed cards whose ranks total thirteen: Ace and Queen, Two and Jack, through Six and Seven.</li><li>An exposed King clears alone. Draw one card at a time when the pyramid has no useful pair; only the top waste card is available.</li><li>Clear all twenty-eight pyramid cards to win. Undo or restart whenever the route closes.</li></ol><p>One hundred and twenty full-deck deals are open from the beginning. Every deal was built from a legal clear and its complete route is replayed through the shipping rules before release. Each pyramid keeps named public records for fastest time and fewest moves.</p></section>'
page('/small-games/pyramid-solitaire/', 'Pyramid Solitaire', 'Free fantasy Pyramid Solitaire with 120 open replay-proven deals and named public records for time and moves.', body, 'small-games', [('Small Games','/small-games/'),('Pyramid Solitaire','/small-games/pyramid-solitaire/')], '/assets/projects/pyramid-solitaire.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Reversi', 'Turn the moonwell. Claim the last light.')+button('Play now', 'https://morassgames.com/games/reversi/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/reversi.webp" width="1200" height="675" alt="A fantasy Reversi board of glowing sun and moon seals inside a brass observatory"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Outflank the rival constellation.</h2><ol><li>Place a seal so one or more straight lines of rival seals lie between your new seal and one already yours.</li><li>Every enclosed seal turns to your side. If you have no legal placement, the turn passes; the fuller side wins when neither can move.</li><li>Choose any observatory trial, or play a full board against one of three rivals or a companion beside you.</li></ol><p>All 120 trials are open from the beginning. The release build reconstructs each position from the canonical opening, proves it has exactly one winning first move against exact resistance, and replays a complete winning witness. Each trial keeps a named public fastest time and top ten.</p></section>'
page('/small-games/reversi/', 'Reversi', 'Free fantasy Reversi with 120 open, exact-solver-proven trials, three computer rivals and same-device play.', body, 'small-games', [('Small Games','/small-games/'),('Reversi','/small-games/reversi/')], '/assets/projects/reversi.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Mastermind', 'Read the assay. Restore the sealed recipe.')+button('Play now', 'https://morassgames.com/games/mastermind/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/mastermind.webp" width="1200" height="675" alt="A fantasy alchemist bench with coloured potion vials, a brass assay ledger and gold and silver feedback marks"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Crack the apothecary’s formula.</h2><ol><li>Choose a reagent, fill every vial in the current row, then Brew the guess.</li><li>A gold drop means one reagent has the right colour and position. A silver wisp means one is present but belongs in another vial; marks never point at individual vials.</li><li>Match the whole sealed recipe before its rows run out. Formulae marked “repeats” may use one reagent more than once.</li></ol><p>All 120 formulae are open across six shelves, from three-vial first distillations to five-vial grand elixirs. Their code spaces rise from twenty-four to 7,776 possibilities, and every fixed formula carries a deterministic solver witness replayed through the shipping scorer during every build. Each formula keeps named public records for fastest time and fewest guesses.</p></section>'
page('/small-games/mastermind/', 'Mastermind', 'Free fantasy Mastermind with 120 open solver-proven potion formulae and named public records for time and guesses.', body, 'small-games', [('Small Games','/small-games/'),('Mastermind','/small-games/mastermind/')], '/assets/projects/mastermind.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Pipe Connect', 'Turn the stones. Wake every moonwell shrine.')+button('Play now', 'https://morassgames.com/games/pipe-connect/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/pipe-connect.webp" width="1200" height="675" alt="A fantasy moonwell conduit made from rune-cut channel stones glowing with living blue aether"></section>'
body += '<section class="prose"><h2>Restore the Moonwell Conduit</h2><p>Rotate every carved stone until its channels meet cleanly and living aether travels from the dragonwell to every flower shrine. The glow follows only the network you have already connected, so every turn gives immediate feedback.</p><p>All 120 chambers are open, grow from 4×4 lessons to 8×7 masterworks, and are checked to have exactly one solution. Each keeps named public records for fastest time and fewest quarter-turns.</p></section>'
page('/small-games/pipe-connect/', 'Pipe Connect', 'Free fantasy Pipe Connect with 120 open unique-solution chambers and named public records for time and turns.', body, 'small-games', [('Small Games','/small-games/'),('Pipe Connect','/small-games/pipe-connect/')], '/assets/projects/pipe-connect.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Slitherlink', 'Read the seals. Ink one unbroken ward.')+button('Play now', 'https://morassgames.com/games/slitherlink/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/slitherlink.webp" width="1200" height="675" alt="A luminous Slitherlink ward drawn across brass pins on vellum inside a fantasy observatory"></section>'
body += '<section class="prose"><h2>Chart the Cartographer’s Ward</h2><p>Draw one closed loop along the brass pins. Each numbered seal says exactly how many of its four sides belong to the loop; the ward cannot branch, cross, or close into a second smaller loop.</p><p>All 120 maps are open, grow from 4×4 introductions to 9×9 master charts, and are independently proved to have one deduction-solvable answer during every build. Each map keeps a named public fastest time and top ten.</p></section>'
page('/small-games/slitherlink/', 'Slitherlink', 'Free fantasy Slitherlink with 120 open, unique and deduction-solved maps plus a named public fastest time on every map.', body, 'small-games', [('Small Games','/small-games/'),('Slitherlink','/small-games/slitherlink/')], '/assets/projects/slitherlink.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Nurikabe', 'Raise the sanctuaries. Bind the living flood.')+button('Play now', 'https://morassgames.com/games/nurikabe/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/nurikabe.webp" width="1200" height="675" alt="A fantasy Nurikabe tidal chart with ivory sanctuary beacons rising from a luminous indigo flood"></section>'
body += '<section class="prose"><h2>Restore the Tidal Archive</h2><p>Mark every cell as sanctuary island or flood. Each numbered beacon belongs to one island of exactly that size; every island holds one beacon, while the flood stays connected and never forms a solid 2×2 pool.</p><p>All 120 charts are open, from gentle 5×5 lessons to 8×8 archive charts. Every chart has exactly one enumerated answer, replayed and checked against all four rules during every build. Each keeps a named public fastest time and top ten.</p></section>'
page('/small-games/nurikabe/', 'Nurikabe', 'Free fantasy Nurikabe with 120 open, uniquely proven charts and a named public fastest time on every chart.', body, 'small-games', [('Small Games','/small-games/'),('Nurikabe','/small-games/nurikabe/')], '/assets/projects/nurikabe.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Numberlink', 'Join the springs. Awaken every stone.')+button('Play now', 'https://morassgames.com/games/numberlink/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/numberlink.webp" width="1200" height="675" alt="Luminous coloured mana channels joining shaped springs on a fantasy stone ward"></section>'
body += '<section class="prose"><h2>Awaken the Moonspring Wards</h2><p>Draw a channel between every pair of matching coloured and shaped mana springs. Channels travel only across adjacent stones, cannot cross or overlap, and the ward wakes only when every stone is filled.</p><p>All 120 wards are open from the beginning. Every fixed ward is exact-enumerated to one full-cover answer and replayed through the shipping rules during every build. Each keeps separate named public records and top tens for fastest time and fewest moves.</p></section>'
page('/small-games/numberlink/', 'Numberlink', 'Free fantasy Numberlink with 120 open exact-unique wards and named public records for time and moves.', body, 'small-games', [('Small Games','/small-games/'),('Numberlink','/small-games/numberlink/')], '/assets/projects/numberlink.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Peg Solitaire', 'Leap the stars. Kindle the final shrine.')+button('Play now', 'https://morassgames.com/games/peg-solitaire/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/peg-solitaire.webp" width="1200" height="675" alt="Faceted cyan star-jewels on a brass celestial Peg Solitaire board inside a fantasy observatory"></section>'
body += '<section class="prose"><h2>Restore the Crown Constellations</h2><p>Leap one star-jewel horizontally or vertically over its neighbour into an empty celestial socket. The eclipsed jewel vanishes; win by leaving one last light on the marked golden shrine.</p><p>All 120 charts are open across four observatory wings. Every position is built backwards from its exact finish, witness-replayed through the browser rules, and solved again by a structurally independent verifier. Each chart keeps a named public fastest time and top ten.</p></section>'
page('/small-games/peg-solitaire/', 'Peg Solitaire', 'Free fantasy Peg Solitaire with 120 open solver-proven constellation challenges and a named public fastest time on every chart.', body, 'small-games', [('Small Games','/small-games/'),('Peg Solitaire','/small-games/peg-solitaire/')], '/assets/projects/peg-solitaire.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Shikaku', 'Chart the landmarks. Leave no corner unclaimed.')+button('Play now', 'https://morassgames.com/games/shikaku/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/shikaku.webp" width="1200" height="675" alt="A fantasy Shikaku parchment survey divided into glowing rectangular provinces inside a moonlit observatory"></section>'
body += '<section class="prose"><h2>Charter the Enchanted Provinces</h2><p>Draw a rectangle around each numbered landmark. Its number is the exact area of its province, and the finished charter must cover the whole map without gaps or overlaps.</p><p>All 120 surveys are open across six atlas folios, from 5×5 lessons to 10×10 grand surveys. Every map is exact-enumerated to one solution, independently verified and witness-replayed during every build. Each survey keeps a named public fastest time and top ten.</p></section>'
page('/small-games/shikaku/', 'Shikaku', 'Free fantasy Shikaku with 120 open, uniquely proven surveys and a named public fastest time on every map.', body, 'small-games', [('Small Games','/small-games/'),('Shikaku','/small-games/shikaku/')], '/assets/projects/shikaku.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Hitori', 'Sink the stones that echo. Keep the causeway whole.')+button('Play now', 'https://morassgames.com/games/hitori/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/hitori.webp" width="1200" height="675" alt="Granite stepping-stones carved with numbers on a moonlit lake, some sunk under the water and others ringed in silver light"></section>'
body += '<section class="prose"><h2>Raise the Causeway on the Mirelight Mere</h2><p>Two stones carved with the same number in one row or column echo. Sink stones until no number stands twice, never two sunk stones side by side, and keep every standing stone joined in one unbroken causeway.</p><p>All 120 crossings are open across six reaches, from 6×6 shallows to 11×11 deep water. Every one has exactly one answer, reached by reasoning with no guess, and keeps a named public fastest time.</p></section>'
page('/small-games/hitori/', 'Hitori', 'Free fantasy Hitori with 120 open, uniquely proven no-guess crossings and a named public fastest time on every one.', body, 'small-games', [('Small Games','/small-games/'),('Hitori','/small-games/hitori/')], '/assets/projects/hitori.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Star Battle', 'Set the stars. None may touch.')+button('Play now', 'https://morassgames.com/games/star-battle/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/star-battle.webp" width="1200" height="675" alt="A star chart of gold-walled coloured constellations on indigo vellum, with gilded eight-pointed stars set in some cells and small silver dots around them"></section>'
body += '<section class="prose"><h2>Chart the Stars in the Star-Hall of Veldrenmar</h2><p>Put stars on the chart so that every row, every column and every gold-walled constellation holds the same number: one on the one-star charts, two on the two-star charts. No two stars may touch, not even at a corner. It is the puzzle LinkedIn plays as Queens.</p><p>All 160 charts are open across eight rooms, from 5×5 one-star charts to 11×11 two-star charts. Every one has exactly one answer, reached by reasoning, and keeps a named public fastest time.</p></section>'
page('/small-games/star-battle/', 'Star Battle', 'Free fantasy Star Battle (Queens) with 160 open, uniquely proven star-charts and a named public fastest time on every one.', body, 'small-games', [('Small Games','/small-games/'),('Star Battle','/small-games/star-battle/')], '/assets/projects/star-battle.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / WORD', 'Word Guess', 'Six tries. One word. A new lock every day.')+button('Play now', 'https://morassgames.com/games/word-guess/')+'<p class="small-note">Free · No account · Plays on morassgames.com</p></div><img src="/assets/projects/word-guess.webp" width="1200" height="675" alt="A brass-framed board of carved letter tiles, some gold with a notch, some blue with a ring, three guesses into a seven-letter word"></section>'
body += '<section class="prose"><h2>Open the Word-Locks of Veldrenmar</h2><p>Guess the hidden word in six tries. Gold with a notch is the right letter in the right place; blue with a ring is in the word somewhere else. A word the dictionary does not know costs nothing.</p><p>The city gate has a new five-letter lock every day, the same for everyone, with an archive and a streak. The twelve houses hold 240 hand-picked locks of four to seven letters, each house its own theme. Fewest guesses and fastest time are public records, on your first attempt only. No ads, no coins, no hints.</p></section>'
page('/small-games/word-guess/', 'Word Guess', 'Free fantasy word-guessing game: a daily word for everyone and 240 themed levels of 4 to 7 letters, with named records.', body, 'small-games', [('Small Games','/small-games/'),('Word Guess','/small-games/word-guess/')], '/assets/projects/word-guess.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / CARD GAME', 'Spider Solitaire', 'Build king to ace in one suit and the run lifts off.')+button('Play now', 'https://morassgames.com/games/spider-solitaire/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/spider-solitaire.webp" width="1200" height="675" alt="A Spider Solitaire table on green baize: ten columns of cards, two finished king runs in their slots, the stock with three deals left, and a run of spades picked up with the columns it may go to outlined in gold"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Build king to ace in one suit.</h2><ol><li>Any card goes on a card one rank higher, of any suit \u2014 but only a run of one suit moves together.</li><li>A king-to-ace run of one suit lifts off the table by itself. Eight runs clear it.</li><li>Tap the stock to deal a card onto every column, never while a column is empty.</li></ol><p>One suit, two or four: 1,454 deals, every one won by our solver before it shipped, and a Day\u2019s Deal in two suits that is the same for everyone. Undo costs a move and can never be used to peek under a card, so the best time and fewest moves on each deal mean what they say.</p></section>'
page('/small-games/spider-solitaire/', 'Spider Solitaire', 'Free Spider Solitaire in 1, 2 or 4 suits: 1,454 deals, every one proved winnable, with named records on each.', body, 'small-games', [('Small Games','/small-games/'),('Spider Solitaire','/small-games/spider-solitaire/')], '/assets/projects/spider-solitaire.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Tents and Trees', 'One pavilion for every elder. None may touch.')+button('Play now', 'https://morassgames.com/games/tents-and-trees/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/tents-and-trees.webp" width="1200" height="675" alt="Silk pavilions pitched beside glowing heartwood trees on a moonlit forest grid, with carved rune cairns counting each row"></section>'
body += '<section class="prose"><h2>Billet the Watch in the Emberwood</h2><p>Every heartwood elder takes exactly one pavilion beside it \u2014 its own, never shared \u2014 and no two pavilions may touch, not even at a corner. The rune cairns along the grove\'s edge say how many each row and column must hold.</p><p>All 120 groves are open across six reaches, from 6\u00d76 clearings to 11\u00d711 deep wood. Every one is solvable by named reasoning with no guess anywhere, and independently counted to exactly one answer before it ships. Each grove keeps a named public fastest time and top ten.</p></section>'
page('/small-games/tents-and-trees/', 'Tents and Trees', 'Free fantasy Tents and Trees with 120 open no-guess groves and a named public fastest time on every one.', body, 'small-games', [('Small Games','/small-games/'),('Tents and Trees','/small-games/tents-and-trees/')], '/assets/projects/tents-and-trees.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / ARCADE', 'Tower Stack', 'One tap. One course of stone. How high?')+button('Play now', 'https://morassgames.com/games/tower-stack/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/tower-stack.webp" width="1200" height="675" alt="A rising stone watchtower with a crane beam above it and a course of dressed stone swinging over the gorge"></section>'
body += '<section class="prose"><h2>Raise the Skyward Watch</h2><p>The crane swings a course of stone across the wall and one tap sets it. Anything that overhangs the course below crumbles into the gorge and the wall is narrower from then on \u2014 but a course that loses nothing is laid <b>true</b>, the crane sends another stone up, and the next course may oversail the one below. A badly climbed wall can still be won back.</p><p>Forty walls across seven marches, each with its own width, load and swing table. Three of the marches carry a rule of their own: a <b>plinth</b> too narrow to be careless on, a <b>buttress</b> course that braces the wall wider \u2014 but only if you lay it true \u2014 and a <b>battlement</b> that is not crowned until the last course lands clean. Three Open walls have no top at all.</p><p>A crowned wall keeps the <b>ten fastest crowns</b>; the Open walls keep the ten tallest climbs. Every row carries its replay, so any of the ten can be watched \u2014 nothing sends a score, a climb sends the climb and it is re-run to work the height out.</p></section>'
page('/small-games/tower-stack/', 'Tower Stack', 'Free one-button stacking game: forty stone walls across seven marches, and a public ten fastest crowns on each, kept with replays.', body, 'small-games', [('Small Games','/small-games/'),('Tower Stack','/small-games/tower-stack/')], '/assets/projects/tower-stack.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / BOARD', 'Checkers', 'Cross the oath-table. Every offered jump must be taken.')+button('Play now', 'https://morassgames.com/games/checkers/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/checkers.webp" width="1200" height="675" alt="An enchanted eight by eight checkers board with carved orange Ember pieces and pale Frost pieces, each marked by its own seal"></section>'
body += '<section class="prose"><h2>Play the oath-table</h2><p>Standard American and English checkers: diagonal moves, compulsory captures, complete jump chains and kings on the far row. Face four keepers from forgiving to deep-searching, or share the board with a friend.</p><p>All 120 tactical Trials are open. Each comes from a legal full game and has one opening that preserves its verified winning line. Every Trial shows named public records for fastest time and fewest moves; keeper wins keep your personal best on both measures.</p></section>'
page('/small-games/checkers/', 'Checkers', 'Free fantasy Checkers with four computer keepers, same-device play and 120 tactical Trials with public time and move records.', body, 'small-games', [('Small Games','/small-games/'),('Checkers','/small-games/checkers/')], '/assets/projects/checkers.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / BOARD', "Nine Men's Morris", 'Place nine stones. Close a mill. Break the rival line.')+button('Play now', 'https://morassgames.com/games/nine-mens-morris/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/nine-mens-morris.webp" width="1200" height="675" alt="A brass-lined Nine Men’s Morris board with carved orange Ember stones and pale Frost stones on a dark ward-table"></section>'
body += '<section class="prose"><h2>Bind the ward-table</h2><p>Place nine stones on the twenty-four crossings. A straight board line of three closes a mill and removes a rival stone. After placement, slide along the brass paths; with only three stones left, fly to any open crossing.</p><p>Face Kindler, Wayfinder, Gate Warden or Oathkeeper, or share the board with a nearby friend. The 120 always-open Mill Trials each come from a legal game and have exactly one move that closes a mill. Each keeps a named public fastest first-solve time; keeper wins remember your fewest turns and best time.</p></section>'
page('/small-games/nine-mens-morris/', "Nine Men's Morris", "Free fantasy Nine Men's Morris with four computer keepers, same-device play and 120 Mill Trials with public time records.", body, 'small-games', [('Small Games','/small-games/'),("Nine Men's Morris",'/small-games/nine-mens-morris/')], '/assets/projects/nine-mens-morris.webp')
body = '<section class="product-hero"><div>'+heading('SMALL GAMES / ARCADE', 'Pinball', 'Ten tables, two flippers, one ball \u2014 and a quest on every table.')+button('Play now', 'https://morassgames.com/games/pinball/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/pinball.webp" width="1200" height="675" alt="A fantasy pinball table in a dragon forge: brass rails, two crossing wireform ramps, glowing ember bumpers, a steel ball in flight and the score glowing on the backglass beside it"></section>'
body += '<section class="prose"><h2>Ten machines, not ten skins</h2><p>Classic pinball the way the old desktop tables played it: a plunger, two flippers, bumpers, slings, ramps, saucers and spinners, on ten tables built from the places of Orenvalt. Each has its own layout and its own quest; finish it and the multiplier climbs.</p><p>Score is the only measure. Every table keeps a Top 10, and each run on it is played again on the server from the presses you made, so any place can be watched.</p></section>'
page('/small-games/pinball/', 'Pinball', 'Free fantasy pinball: ten different tables, a quest on each and a replay-verified Top 10 per table.', body, 'small-games', [('Small Games','/small-games/'),('Pinball','/small-games/pinball/')], '/assets/projects/pinball.webp')
body = '<section class="product-hero"><div>'+heading('SMALL GAMES / BOARD', 'Chess', 'Ten keepers from Page to Oracle, and 220 Trials against the clock.')+button('Play now', 'https://morassgames.com/games/chess/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/chess.webp" width="1200" height="675" alt="A chess game some moves into a Giuoco Piano on a wooden board in a candlelit war room, a knight lifted with its moves marked and the score sheet beside the board"></section>'
body += '<section class="prose"><h2>A keeper for every step</h2><p>Full chess rules: castling, en passant, promotion, and draws by stalemate, repetition, fifty moves and too little material. Play one of ten computer keepers, from Page, who is just learning the moves, to Oracle, the strongest this table holds. Every step up the ladder was measured in a tournament to beat the one below clearly, never by a cliff. Or share the board with a friend.</p><p>The Trials are 200 checkmates in one to five moves and 20 endgame drills with king and queen or king and rook. Every answer was proved by a solver. The clock starts when a Trial is dealt; the fastest first solve on each Trial goes on the board.</p></section>'
page('/small-games/chess/', 'Chess', 'Free fantasy Chess with ten measured computer keepers, same-device play and 220 Trials with public time records.', body, 'small-games', [('Small Games','/small-games/'),('Chess','/small-games/chess/')], '/assets/projects/chess.webp')
body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Calcudoku', 'Strike the numbers into iron. Every mould makes its target.')+button('Play now', 'https://morassgames.com/games/calcudoku/')+'<p class="small-note">Free \u00b7 No account \u00b7 Plays on morassgames.com</p></div><img src="/assets/projects/calcudoku.webp" width="1200" height="675" alt="A seven by seven Calcudoku plate cast in iron on a foundry floor: raised ridges fence the moulds, bronze tags carry their targets and signs, two numbers are cast in and chalk notes run along the top row"></section>'
body += '<section class="prose"><h2>Proving-plates of the Iron-Founders</h2><p>The number puzzle the newspapers call KenKen. Fill the plate so every row and every column holds each number once. Iron ridges cut it into moulds, and each mould\'s tag is its target and sign: its numbers must add, multiply, differ or divide to it. When a mould is full and true, molten iron runs through it.</p><p>There are 240 plates, all open, in six works from the 4\u00d74 Nail to the 9\u00d79 Cannon. Every one has exactly one answer, found by reasoning alone with no guess, and inside each work they run from gentle to hard. The clock starts when a plate is dealt, and the fastest first solve of each plate goes on the board with its holder\'s name.</p></section>'
page('/small-games/calcudoku/', 'Calcudoku', 'Free fantasy Calcudoku (KenKen-style): 240 no-guess plates from 4\u00d74 to 9\u00d79 with public time records.', body, 'small-games', [('Small Games','/small-games/'),('Calcudoku','/small-games/calcudoku/')], '/assets/projects/calcudoku.webp')

# Category pages only show the next level

# Category pages only show the next level; listing links live on model leaves.
def category(prefix=''):
    depth = len(prefix.split('/')) if prefix else 0
    items = [i for i in PRINTS if not prefix or i['collection'] == prefix or i['collection'].startswith(prefix+'/')]
    children = sorted({i['collection'].split('/')[depth] for i in items if len(i['collection'].split('/')) > depth})
    direct = [i for i in items if i['collection'] == prefix]
    title = name(prefix.split('/')[-1]) if prefix else 'Things worth making.'
    body = heading('THE PRINT COLLECTION', title, f'{len(items)} designs to explore. Find your next object, tabletop companion or useful little invention.')
    if not prefix:
        body += '<div class="profile-links"><span>Find Morass on</span>'+''.join(f'<a href="{E(p["url"])}">{E(p["title"])} ↗</a>' for p in P['profiles'])+'</div>'
        body += '<form class="search-form" action="/prints/search/" role="search"><label for="q">Looking for something?</label><div><input id="q" name="q" type="search" placeholder="Try a dice tower, a box, a dragon…" maxlength="120"><button class="button" type="submit">Search prints</button></div></form>'
    body += '<div class="cards print-cards">'
    for child in children:
        child_prefix = '/'.join(filter(None, [prefix, child]))
        subset = [i for i in items if i['collection'] == child_prefix or i['collection'].startswith(child_prefix+'/')]
        representative = next((i for i in subset if i.get('image')), subset[0])
        body += card(name(child), '/prints/'+child_prefix+'/', 'Explore the collection', print_image(representative), f'{len(subset)} designs')
    for item in direct:
        body += card(item['title'], '/prints/'+item['path']+'/', item['summary'], print_image(item), ' / '.join(name(p) for p in item['collection'].split('/')))
    body += '</div>'
    crumbs = [('Prints','/prints/')]+[(name(p), '/prints/'+'/'.join(prefix.split('/')[:i+1])+'/') for i,p in enumerate(prefix.split('/')) if p]
    page('/prints/'+(prefix+'/' if prefix else ''), title if prefix else 'Prints', f'Explore {len(items)} Morass print designs'+(f' in {title}.' if prefix else '.'), body, 'prints', crumbs, print_image(items[0]) or '/assets/projects/pyrewarden.webp')
    for child in children: category('/'.join(filter(None, [prefix, child])))
category()
for item in PRINTS:
    parts = item['collection'].split('/') + [item['id'].split('/')[-1]]
    crumbs = [('Prints', '/prints/')]+[(name(p), '/prints/'+'/'.join(parts[:i+1])+'/') for i,p in enumerate(parts[:-1])]
    art = f'<img class="print-hero-art" src="{E(item["image"])}" width="960" height="720" alt="{E(item["title"])}">' if item.get('image') else '<div class="art-placeholder">'+icon('stamp')+'</div>'
    links = ''.join(button({'cults3d':'View on Cults','printables':'View on Printables','makerworld':'View on MakerWorld','snapmaker':'View on Snapmaker'}[l['platform']],l['url'], True) for l in item['links'])
    body = '<section class="product-hero print-product">'+art+'<div>'+heading(name(parts[0]), item['title'], item['summary'])+'<div class="listing-links">'+links+'</div><p class="small-note">Files, assembly instructions, licenses and print settings are available on the model listings.</p>'+tag_list(item['tags'])+'</div></section>'
    body += '<section class="related"><div class="section-title"><h2>More in '+E(name(parts[-2]))+'</h2><a class="text-link" href="/prints/'+'/'.join(parts[:-1])+'/">View collection ↗</a></div><div class="cards">'
    siblings = [i for i in PRINTS if i['collection'] == item['collection'] and i != item][:3]
    body += ''.join(card(i['title'], '/prints/'+i['path']+'/', '', print_image(i), name(parts[-2])) for i in siblings)+'</div></section>'
    page('/prints/'+item['path']+'/', item['title'], item['summary'] or item['title'], body, 'prints', crumbs, item.get('image') or '/assets/projects/pyrewarden.webp')

body = heading('THE PRINT COLLECTION', 'Find your next print.', 'Search titles, categories and tags across the collection.')
body += '<form class="search-form" role="search"><label for="q">Search prints</label><div><input id="q" name="q" type="search" placeholder="What would you like to make?" maxlength="120"><button class="button" type="submit">Search</button></div></form>'
body += tag_list(TAG_PAGES[:24], 'Popular tags') + '<p class="small-note tag-note"><a href="/prints/tags/">Browse every tag ↗</a></p>'
body += '<p id="search-status" role="status" class="small-note">All designs are shown below. Enable JavaScript to filter them.</p><p id="search-tag" class="small-note" hidden>Showing prints tagged <strong id="search-tag-label"></strong>. <a href="/prints/search/">Clear the tag</a></p><div class="cards print-cards" id="search-results">'
for i in PRINTS:
    text = ' '.join([i['title'],i['summary'],i['id'].replace('-',' '), i['collection'].replace('-', ' ')]+[VOCAB.label(t) for t in i['tags']])
    body += '<div class="search-item" data-search="'+E(text.lower())+'" data-tags="'+E(' '.join(i['tags']))+'">'+card(i['title'],'/prints/'+i['path']+'/', '', print_image(i), ' / '.join(name(part) for part in i['collection'].split('/')))+'</div>'
body += '</div><p id="search-empty" hidden>No prints match that search. Try a shorter word, or <a href="/prints/">browse the categories</a>.</p>'
page('/prints/search/','Search prints','Find Morass print designs by name, category or tag.',body,'prints',[('Prints','/prints/'),('Search','/prints/search/')])
# Tag pages: one index of every shared tag, one page per tag carried by two or more prints.
body = heading('THE PRINT COLLECTION', 'Browse by tag.', f'{len(TAG_PAGES)} tags shared by two or more designs. Sorted by how many prints carry each tag.')
body += tag_list(TAG_PAGES, 'Every tag', count=True)
page('/prints/tags/', 'Tags', 'Browse Morass print designs by tag: features like no supports or print-in-place, games, themes and rooms.', body, 'prints', [('Prints','/prints/'),('Tags','/prints/tags/')])
for tag in TAG_PAGES:
    tagged = [i for i in PRINTS if tag in i['tags']]
    label = VOCAB.label(tag)
    body = heading('TAGGED', label, f'{len(tagged)} designs tagged “{label}”.')
    body += '<div class="cards print-cards">' + ''.join(card(i['title'], '/prints/'+i['path']+'/', i['summary'], print_image(i), ' / '.join(name(p) for p in i['collection'].split('/'))) for i in tagged) + '</div>'
    related = [t for t in TAG_PAGES if t != tag and any(t in i['tags'] for i in tagged)][:16]
    body += tag_list(related, 'Related tags', count=True)
    page(f'/prints/tags/{tag}/', label + ' — Tags', f'{len(tagged)} Morass print designs tagged {label}.', body, 'prints', [('Prints','/prints/'),('Tags','/prints/tags/'),(label, f'/prints/tags/{tag}/')], next((i['image'] for i in tagged if i.get('image')), '/assets/projects/pyrewarden.webp'))
# Keep earlier category bookmarks working as the public taxonomy becomes deeper.
REDIRECTS = set()
for old, new in TAXONOMY.get('redirects', {}).items():
    relative = 'prints/' + old + '/index.html'
    destination = '/prints/' + new + '/'
    if relative in GENERATED:
        continue
    if 'prints/' + new + '/index.html' not in GENERATED:
        raise ValueError(f'Redirect target is missing: {destination}')
    target = ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Collection moved — Morass</title><link rel="canonical" href="' + SITE + destination + '"><meta http-equiv="refresh" content="0;url=' + destination + '"></head><body><p>This collection has moved. <a href="' + destination + '">Browse the collection</a>.</p></body></html>')
    GENERATED.add(relative)
    REDIRECTS.add(relative)
# Only delete paths this builder previously owned; leave hand-authored game pages alone.
manifest = ROOT / 'content/generated-pages.json'
previous = json.loads(manifest.read_text()) if manifest.exists() else []
for old in set(previous)-GENERATED:
    p = ROOT / old
    if p.is_relative_to(ROOT) and '..' not in Path(old).parts and p.name == 'index.html': p.unlink(missing_ok=True)
manifest.write_text(json.dumps(sorted(GENERATED),indent=2)+'\n')
urls = sorted({SITE+'/'+p.removesuffix('index.html') for p in GENERATED-REDIRECTS} | {SITE+p['path'] for key in ['games','mobile'] for p in P[key]})
(ROOT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+E(u)+'</loc></url>' for u in urls)+'</urlset>\n')
(ROOT/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+SITE+'/sitemap.xml\n')
print(f'Built {len(GENERATED)} pages, {len(PRINTS)} prints')
