#!/usr/bin/env python3
"""Export public listing metadata and small images; never publish to a marketplace."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
import tomllib
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = {
    'cults3d': ('cults3d.com', r'/[a-z]{2}/3d-model/[^/]+/[^/]+/?'),
    'printables': ('www.printables.com', r'/(?:[a-z]{2}/)?model/[0-9]+(?:-[^/]+)?/?'),
    'makerworld': ('makerworld.com', r'/[a-z]{2}/models/[0-9]+(?:-[^/]+)?/?'),
}

def public_url(platform, value):
    if not isinstance(value, str):
        return None
    p = urlsplit(value)
    host, pattern = PLATFORMS[platform]
    if (p.scheme != 'https' or p.netloc not in {host, host.removeprefix('www.')} or
            p.query or p.username or not re.fullmatch(pattern, p.path)):
        return None
    return f'https://{host}{p.path.rstrip("/")}'

def links_for(record):
    links = []
    for platform in PLATFORMS:
        rows = record.get(platform, [])
        if not isinstance(rows, list):
            rows = [rows]
        for row in rows:
            if isinstance(row, dict):
                if row.get('deleted') or row.get('withdrawn') or row.get('status') in {'draft', 'private', 'deleted'}:
                    continue
                row = row.get('url')
            url = public_url(platform, row)
            entry = {'platform': platform, 'url': url}
            if url and entry not in links:
                links.append(entry)
    return links

def slug(path):
    return '/'.join(re.sub(r'[^a-z0-9]+', '-', part.lower()).strip('-') for part in path.parts)

def export(source, destination):
    source = source.resolve()
    items, skipped, seen = [], [], set()
    for record in sorted(source.rglob('published_urls.json')):
        if any(part.startswith('.') for part in record.relative_to(source).parts):
            continue
        folder = record.parent
        if not folder.is_relative_to(source) or not record.resolve().is_relative_to(source):
            raise ValueError(f'Outside source: {record}')
        model = folder / 'model.toml'
        if not model.exists():
            skipped.append(str(record.relative_to(source))); continue
        meta = tomllib.loads(model.read_text())
        if meta.get('website', {}).get('hidden'):
            continue
        links = links_for(json.loads(record.read_text()))
        if not links:
            skipped.append(str(record.relative_to(source))); continue
        identifier = slug(folder.relative_to(source))
        if identifier in seen or not identifier or '..' in identifier:
            raise ValueError(f'Ambiguous catalogue route: {identifier}')
        seen.add(identifier)
        config = meta.get('website', {})
        item = {'id': identifier, 'title': config.get('title') or meta.get('title') or folder.name.replace('_', ' ').title(),
                'summary': config.get('summary') or meta.get('summary', ''),
                'tags': meta.get('tags', []), 'links': links}
        if config.get('category'):
            item['collection'] = config['category']
        custom = config.get('image')
        images = [folder / custom] if custom else []
        images += sorted(folder.glob('photo*.jpg')) + sorted(folder.glob('photo*.png'))
        images += [folder / 'preview.png'] + sorted(folder.glob('preview_*.png'))
        image = next((p for p in images if p.is_file()), None)
        if image:
            if not image.resolve().is_relative_to(folder.resolve()):
                raise ValueError(f'Image escapes model: {image}')
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            relative = f'assets/prints/{identifier}/{digest[:16]}.webp'
            target = destination / relative
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(image) as im:
                    im = ImageOps.exif_transpose(im).convert('RGB')
                    im.thumbnail((960, 720), Image.Resampling.LANCZOS)
                    im.save(target, 'WEBP', quality=82, method=4)
            item['image'] = '/' + relative
        items.append(item)
    if not items:
        raise ValueError('No public prints found; refusing to replace the catalogue')
    target = destination / 'content/prints.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'items': items}, ensure_ascii=False, indent=2) + '\n')
    print(f'Exported {len(items)} prints; skipped {len(skipped)} records without metadata/public links')
    for path in skipped: print('  skipped:', path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT.parent / 'prints')
    parser.add_argument('--destination', type=Path, default=ROOT)
    args = parser.parse_args()
    export(args.source, args.destination)
