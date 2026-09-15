#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import print_tags as pt
ROOT = Path(__file__).resolve().parents[1]
class TagTests(unittest.TestCase):
    def setUp(self):
        self.v = pt.Vocabulary({'drop': ['openscad'], 'aliases': {'nosupports': 'no-supports', 'earrings': 'earring'}, 'labels': {'mtg': 'Magic: The Gathering'}},
                               ['makeuporganizer', 'makeup-organizer', 'Makeup Organizer', 'trinket_box', 'trinketbox'])
    def test_spellings_fold_to_one_tag(self):
        self.assertEqual(self.v.tags(['nosupports', 'no-supports', 'No Supports', 'no_supports']), ['no-supports'])
        self.assertEqual(self.v.tags(['makeuporganizer', 'Makeup Organizer']), ['makeup-organizer'])
        self.assertEqual(self.v.canonical('trinket_box'), 'trinket-box')
    def test_drop_alias_and_unknown(self):
        self.assertEqual(self.v.tags(['openscad', 'OpenSCAD', 'earrings', 'earring', 'dragon', '', '  ']), ['earring', 'dragon'])
    def test_labels(self):
        self.assertEqual(self.v.label('mtg'), 'Magic: The Gathering')
        self.assertEqual(self.v.label('no-supports'), 'No supports')
    def test_bad_config_rejected(self):
        with self.assertRaises(ValueError): pt.Vocabulary({'aliases': {'a': 'Not Kebab'}})
        with self.assertRaises(ValueError): pt.Vocabulary({'drop': ['a'], 'aliases': {'a': 'b'}})
    def test_site_vocabulary_is_consistent(self):
        config = json.loads((ROOT / 'content/print-tags.json').read_text())
        items = json.loads((ROOT / 'content/prints.json').read_text())['items']
        v = pt.Vocabulary(config, [t for i in items for t in i['tags']])
        for target in set(v.aliases.values()):
            self.assertEqual(v.aliases.get(pt.compact(target), target), target, f'alias chain: {target}')
            self.assertNotIn(pt.compact(target), v.drop, f'alias target dropped: {target}')
        for tag in v.labels:
            self.assertTrue(tag in set(v.aliases.values()) or pt.compact(tag) in v.spelling, f'label for unused tag: {tag}')
unittest.main()
