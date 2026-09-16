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
    body = heading(dict(NAV)[key], title, description) + project_cards(key)
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
body = heading('FREE TOOLS', 'Small tools, free to use.', 'Open-source command-line tools and Neovim plugins, made along the way. Use them, change them, share them.')
body += '<div class="cards tool-cards">'
for group in P['toolGroups']:
    count = sum(t['group'] == group['slug'] for t in P['tools'])
    body += card(group['title'], f"/tools/{group['slug']}/", group['summary'], label=f"{count} {'tool' if count == 1 else 'tools'}", art=tool_mark(group))
body += '</div>'
page('/tools/', 'Free tools', 'Free, open-source command-line tools and Neovim plugins by Morass.', body, 'tools', [('Free tools','/tools/')])
for group in P['toolGroups']:
    body = heading('FREE TOOLS · ' + group['title'], group['title'] + '.', group['summary']) + '<div class="channel-list">'
    for tool in (t for t in P['tools'] if t['group'] == group['slug']):
        body += f'<article class="channel tool">{tool_mark(group).replace("tool-mark-art", "tool-mark-inline")}<div><p class="eyebrow">{E(tool["label"])}</p><h2>{E(tool["title"])}</h2><p>{E(tool["summary"])}</p></div>{button("View on GitHub", tool["url"], True)}</article>'
    body += '</div>'
    page(f"/tools/{group['slug']}/", group['title'] + ' — Free tools', group['summary'], body, 'tools', [('Free tools','/tools/'), (group['title'], f"/tools/{group['slug']}/")])

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Ninefold', 'Sudoku under two moons. One answer to every board, never a guess.')+button('Play now', 'https://morassgames.com/games/ninefold/')+'<p class="small-note">Free to play · No account · Plays on morassgames.com</p></div><img src="/assets/projects/ninefold.webp" width="1200" height="675" alt="A parchment sudoku board before nine glowing standing stones under two moons"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Seal the ward.</h2><ol><li>Fill the grid so every row, column and 3×3 box holds 1 to 9 exactly once.</li><li>Tap a cell, then a number. Turn on <strong>Notes</strong> to pencil in candidates.</li><li>Stuck? <strong>Hint</strong> first shows where to look, then explains the step.</li></ol><p>480 boards in four tiers named by the techniques they need — from singles to X-Wings and Swordfish — plus a daily ward. Every board is proven to have exactly one solution that can be reached without guessing. No mistake limit, no countdown. Your progress is saved in this browser.</p><p class="small-note">Keyboard: arrows to move, 1–9 to place, Shift+1–9 for notes, N notes mode, Backspace to clear, Z undo, Y redo, H hint.</p></section>'
page('/small-games/ninefold/', 'Ninefold', 'Play a free sudoku with 480 proven-unique boards, a daily ward and hints that explain every step. No download and no account.', body, 'small-games', [('Small Games','/small-games/'),('Ninefold','/small-games/ninefold/')], '/assets/projects/ninefold.webp')

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Borrowed Ink', 'A little stamp. A sheet of paper. Thirty gentle puzzles about moving ink.')+button('Play now', 'https://morassgames.com/games/borrowed-ink/')+'<p class="small-note">Free to play · No account · Plays on morassgames.com</p></div><img src="/assets/projects/borrowed-ink.webp" width="960" height="600" alt="The Borrowed Ink puzzle desk"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Make an impression.</h2><ol><li>Select two neighboring cells on the paper.</li><li>Press <strong>Make impression</strong> to exchange the ink in those cells with the stamp.</li><li>Match the target picture and leave the stamp empty.</li></ol><p>Turn the stamp to switch between horizontal and vertical pairs. Undo, restart and hints are always free. Your progress is saved in this browser.</p><p class="small-note">Keyboard: arrows to move, Enter to select, Space to press, R to turn, Z to undo, H for a hint.</p></section>'
page('/small-games/borrowed-ink/', 'Borrowed Ink', 'Play a gentle, free ink-exchange puzzle with thirty levels. No download, account or ads.', body, 'small-games', [('Small Games','/small-games/'),('Borrowed Ink','/small-games/borrowed-ink/')], '/assets/projects/borrowed-ink.webp')

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
    links = ''.join(button({'cults3d':'View on Cults','printables':'View on Printables','makerworld':'View on MakerWorld'}[l['platform']],l['url'], True) for l in item['links'])
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
