#!/usr/bin/env python3
"""Check internal links/assets and catalogue invariants without network or dependencies."""
import importlib.util
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
ROOT = Path(__file__).resolve().parents[1]
class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.cards=[]; self.h1=0; self.headers=0; self.footers=0; self.mains=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='h1': self.h1+=1
        if tag=='header' and 'header' in attrs.get('class','').split(): self.headers+=1
        if tag=='footer' and 'footer' in attrs.get('class','').split(): self.footers+=1
        if tag=='main' and attrs.get('id')=='main': self.mains+=1
        if tag=='a' and 'card' in attrs.get('class','').split(): self.cards.append(attrs.get('href',''))
        for attr in ['href','src','poster']:
            if attr in attrs: self.links.append(attrs[attr])
errors=[]
for p in ROOT.rglob('*.html'):
    if '.git' in p.parts: continue
    source=p.read_text()
    parsed=Links();parsed.feed(source)
    relative=p.relative_to(ROOT).as_posix()
    is_runtime=relative.startswith('small-games/') and '/play/' in relative
    if not is_runtime and 'http-equiv="refresh"' not in source:
        if (parsed.headers,parsed.footers,parsed.mains)!=(1,1,1) or '/theme.js' not in source or '/hub.css' not in source:
            errors.append(f'{relative}: shared site shell/theme missing or duplicated')
    for value in parsed.links:
        link=urlsplit(value)
        if link.scheme or link.netloc or not link.path: continue
        target=(ROOT/link.path.lstrip('/') if link.path.startswith('/') else p.parent/link.path)
        target=Path(unquote(str(target)))
        if target.is_dir(): target=target/'index.html'
        if not target.exists(): errors.append(f'{p.relative_to(ROOT)}: missing {value}')
items=json.loads((ROOT/'content/prints.json').read_text())['items']
assert len({i['id'] for i in items})==len(items)
taxonomy=json.loads((ROOT/'content/print-collections.json').read_text())
for item in items:
    assert item['links']
    assert (ROOT/'prints'/taxonomy.get('modelPaths',{}).get(item['id'],item['id'])/'index.html').exists()
    for link in item['links']:
        assert not any(word in link['url'] for word in ['/verifying','/edit','/create','developer.','studio.youtube.'])
# Every model must be discoverable by descending category cards, without search.
visited=set()
pending=['/prints/']
while pending:
    route=pending.pop()
    if route in visited: continue
    visited.add(route)
    path=ROOT/route.strip('/')/'index.html'
    if not path.exists(): continue
    parsed=Links();parsed.feed(path.read_text())
    pending.extend(url for url in parsed.cards if url.startswith('/prints/'))
for item in items:
    route='/prints/'+taxonomy.get('modelPaths',{}).get(item['id'],item['id'])+'/'
    if route not in visited: errors.append(f'Model unreachable through category cards: {route}')
print(f'Checked internal HTML links and {len(items)} catalogue leaves')
if errors:
    print('\n'.join(errors));raise SystemExit(1)
