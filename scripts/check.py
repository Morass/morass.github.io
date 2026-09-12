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
        super().__init__(); self.links=[]; self.h1=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='h1': self.h1+=1
        for attr in ['href','src','poster']:
            if attr in attrs: self.links.append(attrs[attr])
errors=[]
for p in ROOT.rglob('*.html'):
    if '.git' in p.parts: continue
    parsed=Links();parsed.feed(p.read_text())
    for value in parsed.links:
        link=urlsplit(value)
        if link.scheme or link.netloc or not link.path: continue
        target=(ROOT/link.path.lstrip('/') if link.path.startswith('/') else p.parent/link.path)
        target=Path(unquote(str(target)))
        if target.is_dir(): target=target/'index.html'
        if not target.exists(): errors.append(f'{p.relative_to(ROOT)}: missing {value}')
items=json.loads((ROOT/'content/prints.json').read_text())['items']
assert len({i['id'] for i in items})==len(items)
for item in items:
    assert item['links']
    assert (ROOT/'prints'/item['id']/'index.html').exists()
    for link in item['links']:
        assert not any(word in link['url'] for word in ['/verifying','/edit','/create','developer.','studio.youtube.'])
print(f'Checked internal HTML links and {len(items)} catalogue leaves')
if errors:
    print('\n'.join(errors));raise SystemExit(1)
