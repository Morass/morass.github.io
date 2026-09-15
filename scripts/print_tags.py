"""Fold the marketplace tags of every print into one curated vocabulary.

Platform tags are written per platform (Printables accepts only [a-z0-9]), so
the same idea arrives as `nosupports`, `no-supports` and `no supports`. Every
spelling folds to a compact key of letters and digits; `content/print-tags.json`
then drops workflow keys, maps synonyms to a canonical kebab-case tag and names
acronyms. Anything left keeps the most-hyphenated spelling seen in the data.
"""
import json
import re
from collections import Counter
from pathlib import Path

TAG_RE = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')

def slugify(raw):
    return re.sub(r'[^a-z0-9]+', '-', str(raw).strip().lower()).strip('-')

def compact(raw):
    return re.sub(r'[^a-z0-9]', '', str(raw).lower())

class Vocabulary:
    def __init__(self, config, corpus=()):
        self.drop = {compact(k) for k in config.get('drop', [])}
        self.aliases = {compact(k): v for k, v in config.get('aliases', {}).items()}
        self.labels = dict(config.get('labels', {}))
        for key, target in self.aliases.items():
            if not TAG_RE.fullmatch(target):
                raise ValueError(f'Alias target is not kebab-case: {key} -> {target}')
            if key in self.drop:
                raise ValueError(f'Tag is both dropped and aliased: {key}')
        for tag in self.labels:
            if not TAG_RE.fullmatch(tag):
                raise ValueError(f'Label key is not kebab-case: {tag}')
        # Prefer the spelling with the most word breaks, then the shortest, then alphabetical.
        spellings = {}
        for raw in corpus:
            s = slugify(raw)
            if s:
                spellings.setdefault(compact(s), set()).add(s)
        self.spelling = {k: sorted(v, key=lambda s: (-s.count('-'), len(s), s))[0] for k, v in spellings.items()}

    def canonical(self, raw):
        key = compact(raw)
        if not key or key in self.drop:
            return None
        if key in self.aliases:
            return self.aliases[key]
        return self.spelling.get(key, slugify(raw))

    def tags(self, raw_tags):
        out = []
        for raw in raw_tags:
            tag = self.canonical(raw)
            if tag and tag not in out:
                out.append(tag)
        return out

    def label(self, tag):
        if tag in self.labels:
            return self.labels[tag]
        words = tag.replace('-', ' ')
        return words[:1].upper() + words[1:]

def load(path, corpus=()):
    return Vocabulary(json.loads(Path(path).read_text()), corpus)

def counts(items, vocabulary):
    """Canonical tag -> number of prints carrying it."""
    c = Counter()
    for item in items:
        c.update(vocabulary.tags(item.get('tags', [])))
    return c
