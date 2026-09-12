#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('exporter',Path(__file__).with_name('import-prints.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ExportTests(unittest.TestCase):
    def test_private_routes_and_untrusted_hosts(self):
        for platform,url in [('makerworld','https://makerworld.com/en/@Morass/verifying'),('printables','https://www.printables.com/model/123/edit'),('cults3d','https://evil.test/en/3d-model/home/thing'),('makerworld','https://makerworld.com/en/models/123?token=private'),('makerworld','https://makerworld.com.evil.test/en/models/123')]:
            self.assertIsNone(m.public_url(platform,url))
    def test_mixed_legacy_records_and_deduplication(self):
        rows={'printables':'https://www.printables.com/model/123-thing','makerworld':[{'url':'https://makerworld.com/en/models/456','draft':'123'},{'url':'https://makerworld.com/en/models/456'},{'url':'https://makerworld.com/en/models/789','status':'private'}]}
        self.assertEqual(len(m.links_for(rows)),2)
    def test_hierarchy(self):
        self.assertEqual(m.slug(Path('boardgames/spirit_island/token_set')),'boardgames/spirit-island/token-set')
unittest.main()
