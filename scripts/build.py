#!/usr/bin/env python3
"""Build the public hub from curated projects and the prints export. No dependencies."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://morass.github.io'
P = json.loads((ROOT / 'content/projects.json').read_text())
PRINTS = json.loads((ROOT / 'content/prints.json').read_text())['items']
GENERATED = set()
NAV = [('games', 'Morass Games'), ('small-games', 'Small Games'), ('mobile', 'Mobile'), ('youtube', 'YouTube'), ('prints', 'Prints')]
LABELS = {'boardgames': 'Board games', 'desk': 'Desk & office', 'decorations': 'Decorations', 'containers': 'Boxes & storage', 'bathroom': 'Bathroom', 'kitchen': 'Kitchen', 'home': 'Around the home', 'outdoor': 'Outdoors', 'footwear': 'Footwear', 'general': 'Original & general', 'mtg': 'Magic: The Gathering', 'spirit-island': 'Spirit Island', 'frosthaven': 'Frosthaven'}
E = lambda value: html.escape(str(value), quote=True)

def name(part):
    return LABELS.get(part, part.replace('-', ' ').title())

def icon(which):
    return f'<img class="ui-icon" src="/assets/ui/{which}.svg" alt="" width="24" height="24">'

def button(label, url, secondary=False):
    return f'<a class="button{" secondary" if secondary else ""}" href="{E(url)}">{E(label)} <span aria-hidden="true">↗</span></a>'

def page(path, title, description, body, active='', crumbs=None, image='/assets/projects/pyrewarden.webp'):
    target = ROOT / path.strip('/') / 'index.html' if path != '/' else ROOT / 'index.html'
    target.parent.mkdir(parents=True, exist_ok=True)
    nav = ''.join(f'<a href="/{key}/"'+ (' aria-current="page"' if key == active else '') + f'>{label}</a>' for key, label in NAV)
    breadcrumb = ''
    if crumbs:
        breadcrumb = '<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">Home</a>' + ''.join(f'<span aria-hidden="true">/</span><a href="{E(url)}">{E(label)}</a>' for label, url in crumbs) + '</nav>'
    target.write_text(f'''<!doctype html>
<html lang="en" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)} — Morass</title><meta name="description" content="{E(description)}">
<link rel="canonical" href="{SITE}{path}"><meta property="og:title" content="{E(title)} — Morass"><meta property="og:description" content="{E(description)}"><meta property="og:type" content="website"><meta property="og:url" content="{SITE}{path}"><meta property="og:image" content="{SITE}{image}">
<meta name="theme-color" content="#111917"><script src="/theme.js"></script><link rel="icon" href="/favicon.png"><link rel="stylesheet" href="/hub.css"><script src="/hub.js" defer></script></head>
<body><a class="skip" href="#main">Skip to content</a><header class="header"><div class="shell header-inner"><a class="brand" href="/" aria-label="Morass home"><span class="brand-mark" aria-hidden="true">m.</span>MORASS<span class="brand-note">PLAY · MAKE · EXPLORE</span></a><nav aria-label="Main">{nav}</nav><button class="theme-toggle" type="button" aria-label="Switch to light mode" hidden>Light mode</button></div></header>
<main id="main" class="shell">{breadcrumb}{body}</main><footer class="footer shell"><a class="brand" href="/">morass<span class="accent">.</span></a><p>Games, objects and other curiosities.<br>Made with care. Made to be explored.</p><nav aria-label="Footer"><a href="/prints/">Prints</a><a href="/games/">Games</a><a href="/privacy.html">Privacy</a></nav><small>© 2026 Morass</small></footer></body></html>''')
    GENERATED.add(str(target.relative_to(ROOT)))

def heading(eyebrow, title, description):
    return f'<header class="page-heading"><p class="eyebrow">{E(eyebrow)}</p><h1>{E(title)}</h1><p class="lede">{E(description)}</p></header>'

def card(title, url, summary, image=None, label='', feature=False):
    art = f'<img src="{E(image)}" alt="" loading="lazy" width="960" height="600">' if image else f'<div class="art-placeholder">{icon("stamp")}</div>'
    return f'<a class="card{" featured" if feature else ""}" href="{E(url)}"><div class="card-art">{art}<span class="card-arrow" aria-hidden="true">↗</span></div><div class="card-copy"><p class="eyebrow">{E(label)}</p><h2>{E(title)}</h2><p>{E(summary)}</p></div></a>'

def project_cards(key):
    return '<div class="cards">'+''.join(card(p['title'], p['path'], p['summary'], p['image'], p['label']) for p in P[key])+'</div>'

def print_image(item):
    return item.get('image')

# Homepage: five distinct destinations, each with its own collection.
print_cover = next((i for i in PRINTS if i['id'] == 'containers/pirate-chest'), PRINTS[0])
home = '<section id="explore" class="collection home-crossroads"><div class="section-title"><div><p class="eyebrow">THE MORASS COLLECTION</p><h1>Explore the projects.</h1></div><span class="section-note">Games. Prints. Stories.</span></div><div class="crossroads">'
home += card('Morass Games', '/games/', 'Strategy, strange worlds and stories worth getting lost in. Explore the Steam collection.', '/assets/projects/pyrewarden.webp', '01 / GAMES ON STEAM', True)
home += card('Prints', '/prints/', 'Useful objects, playful mechanisms and tabletop companions. Find something to make.', print_image(print_cover), f'02 / {len(PRINTS)} DESIGNS', True)
home += card('Small Games', '/small-games/', 'A little play, straight from your browser.', '/assets/projects/borrowed-ink.webp', '03 / NO INSTALL NEEDED')
home += card('Mobile', '/mobile/', 'Games and projects made for your pocket.', '/assets/projects/lanternward.webp', '04 / ANDROID')
home += card('YouTube', '/youtube/', 'Stories, objects and a look behind the projects.', '/assets/ui/album.svg', '05 / WATCH & DISCOVER')
home += '</div></section><section class="closing-note">'+icon('leaf')+'<p>Different projects.<br><strong>The same curious spirit.</strong></p><a class="text-link" href="/prints/">Take a look around ↗</a></section>'
page('/', 'Games, prints & curious projects', 'Explore Morass: Steam games, free browser puzzles, Android projects, YouTube and an organized catalogue of 3D prints.', home)
for key, title, description in [
    ('games', 'Worlds worth getting lost in.', 'The Morass Games collection. Strategy, survival and stories on Steam.'),
    ('small-games', 'Small games. Good company.', 'Thoughtful little games you can play right here, in your browser.'),
    ('mobile', 'A little wonder, to go.', 'Games and projects for Android. Explore what is taking shape.')]:
    body = heading(dict(NAV)[key], title, description) + project_cards(key)
    if key == 'games': body += '<div class="section-end">'+button('Explore Morass on Steam', 'https://store.steampowered.com/search/?developer=Morass', True)+'</div>'
    page('/'+key+'/', dict(NAV)[key], description, body, key, [(dict(NAV)[key], '/'+key+'/')])

body = heading('YOUTUBE', 'A closer look.', 'Stories and making, from the Morass collection.')
body += '<div class="channel-list">'
for channel in P['channels']:
    body += f'<article class="channel">{icon("album")}<div><p class="eyebrow">{E(channel["label"])}</p><h2>{E(channel["title"])}</h2><p>{E(channel["summary"])}</p></div>{button("Visit the channel",channel["url"])}</article>'
body += '</div>'
page('/youtube/', 'YouTube', 'Watch stories and making from Morass.', body, 'youtube', [('YouTube','/youtube/')])

body = '<section class="product-hero"><div>'+heading('SMALL GAMES / PUZZLE', 'Borrowed Ink', 'A little stamp. A sheet of paper. Thirty gentle puzzles about moving ink.')+button('Play now', '/small-games/borrowed-ink/play/')+'<p class="small-note">Free to play · No account · No ads in this edition</p></div><img src="/assets/projects/borrowed-ink.webp" width="960" height="600" alt="The Borrowed Ink puzzle desk"></section>'
body += '<section class="rules"><p class="eyebrow">HOW TO PLAY</p><h2>Make an impression.</h2><ol><li>Select two neighboring cells on the paper.</li><li>Press <strong>Make impression</strong> to exchange the ink in those cells with the stamp.</li><li>Match the target picture and leave the stamp empty.</li></ol><p>Turn the stamp to switch between horizontal and vertical pairs. Undo, restart and hints are always free. Your progress is saved in this browser.</p><p class="small-note">Keyboard: arrows to move, Enter to select, Space to press, R to turn, Z to undo, H for a hint.</p></section>'
page('/small-games/borrowed-ink/', 'Borrowed Ink', 'Play a gentle, free ink-exchange puzzle with thirty levels. No download, account or ads.', body, 'small-games', [('Small Games','/small-games/'),('Borrowed Ink','/small-games/borrowed-ink/')], '/assets/projects/borrowed-ink.webp')

# Category pages only show the next level; listing links live on model leaves.
def category(prefix=''):
    depth = len(prefix.split('/')) if prefix else 0
    items = [i for i in PRINTS if not prefix or i['id'].startswith(prefix+'/')]
    children = sorted({i['id'].split('/')[depth] for i in items if len(i['id'].split('/')) > depth+1})
    direct = [i for i in items if len(i['id'].split('/')) == depth+1]
    title = name(prefix.split('/')[-1]) if prefix else 'Things worth making.'
    body = heading('THE PRINT COLLECTION', title, f'{len(items)} designs to explore. Find your next object, tabletop companion or useful little invention.')
    if not prefix:
        body += '<div class="profile-links"><span>Find Morass on</span>'+''.join(f'<a href="{E(p["url"])}">{E(p["title"])} ↗</a>' for p in P['profiles'])+'</div>'
        body += '<form class="search-form" action="/prints/search/" role="search"><label for="q">Looking for something?</label><div><input id="q" name="q" type="search" placeholder="Try a dice tower, a box, a dragon…" maxlength="120"><button class="button" type="submit">Search prints</button></div></form>'
    body += '<div class="cards print-cards">'
    for child in children:
        child_prefix = '/'.join(filter(None, [prefix, child]))
        subset = [i for i in items if i['id'].startswith(child_prefix+'/')]
        representative = next((i for i in subset if i.get('image')), subset[0])
        body += card(name(child), '/prints/'+child_prefix+'/', 'Explore the collection', print_image(representative), f'{len(subset)} designs')
    for item in direct:
        body += card(item['title'], '/prints/'+item['id']+'/', item['summary'], print_image(item), ' / '.join(name(p) for p in item['id'].split('/')[:-1]))
    body += '</div>'
    crumbs = [('Prints','/prints/')]+[(name(p), '/prints/'+'/'.join(prefix.split('/')[:i+1])+'/') for i,p in enumerate(prefix.split('/')) if p]
    page('/prints/'+(prefix+'/' if prefix else ''), title if prefix else 'Prints', f'Explore {len(items)} Morass print designs'+(f' in {title}.' if prefix else '.'), body, 'prints', crumbs, print_image(items[0]) or '/assets/projects/pyrewarden.webp')
    for child in children: category('/'.join(filter(None, [prefix, child])))
category()
for item in PRINTS:
    parts = item['id'].split('/')
    crumbs = [('Prints', '/prints/')]+[(name(p), '/prints/'+'/'.join(parts[:i+1])+'/') for i,p in enumerate(parts[:-1])]
    art = f'<img class="print-hero-art" src="{E(item["image"])}" width="960" height="720" alt="{E(item["title"])}">' if item.get('image') else '<div class="art-placeholder">'+icon('stamp')+'</div>'
    links = ''.join(button({'cults3d':'View on Cults','printables':'View on Printables','makerworld':'View on MakerWorld'}[l['platform']],l['url'], True) for l in item['links'])
    body = '<section class="product-hero print-product">'+art+'<div>'+heading(name(parts[0]), item['title'], item['summary'])+'<div class="listing-links">'+links+'</div><p class="small-note">Files, assembly instructions, licenses and print settings are available on the model listings.</p></div></section>'
    body += '<section class="related"><div class="section-title"><h2>More in '+E(name(parts[-2]))+'</h2><a class="text-link" href="/prints/'+'/'.join(parts[:-1])+'/">View collection ↗</a></div><div class="cards">'
    siblings = [i for i in PRINTS if i['id'].rsplit('/',1)[0] == item['id'].rsplit('/',1)[0] and i != item][:3]
    body += ''.join(card(i['title'], '/prints/'+i['id']+'/', '', print_image(i), name(parts[-2])) for i in siblings)+'</div></section>'
    page('/prints/'+item['id']+'/', item['title'], item['summary'] or item['title'], body, 'prints', crumbs, item.get('image') or '/assets/projects/pyrewarden.webp')

body = heading('THE PRINT COLLECTION', 'Find your next print.', 'Search titles, categories and tags across the collection.')
body += '<form class="search-form" role="search"><label for="q">Search prints</label><div><input id="q" name="q" type="search" placeholder="What would you like to make?" maxlength="120"><button class="button" type="submit">Search</button></div></form><p id="search-status" role="status" class="small-note">All designs are shown below. Enable JavaScript to filter them.</p><div class="cards print-cards" id="search-results">'
for i in PRINTS:
    text = ' '.join([i['title'],i['summary'],i['id'].replace('-',' ')]+[str(t).replace('_',' ') for t in i['tags']])
    body += '<div class="search-item" data-search="'+E(text.lower())+'">'+card(i['title'],'/prints/'+i['id']+'/', '', print_image(i), name(i['id'].split('/')[0]))+'</div>'
body += '</div><p id="search-empty" hidden>No prints match that search. Try a shorter word, or <a href="/prints/">browse the categories</a>.</p>'
page('/prints/search/','Search prints','Find Morass print designs by name, category or tag.',body,'prints',[('Prints','/prints/'),('Search','/prints/search/')])
# Only delete paths this builder previously owned; leave hand-authored game pages alone.
manifest = ROOT / 'content/generated-pages.json'
previous = json.loads(manifest.read_text()) if manifest.exists() else []
for old in set(previous)-GENERATED:
    p = ROOT / old
    if p.is_relative_to(ROOT) and '..' not in Path(old).parts and p.name == 'index.html': p.unlink(missing_ok=True)
manifest.write_text(json.dumps(sorted(GENERATED),indent=2)+'\n')
urls = sorted({SITE+'/'+p.removesuffix('index.html') for p in GENERATED} | {SITE+p['path'] for key in ['games','mobile'] for p in P[key]})
(ROOT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+E(u)+'</loc></url>' for u in urls)+'</urlset>\n')
(ROOT/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+SITE+'/sitemap.xml\n')
print(f'Built {len(GENERATED)} pages, {len(PRINTS)} prints')
