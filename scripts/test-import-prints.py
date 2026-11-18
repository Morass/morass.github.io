#!/usr/bin/env python3
import importlib.util
import unittest
import json
import tempfile
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
    def test_snapmaker_live_only(self):
        # A submitted Space listing is recorded at once but is public only after review.
        rows={'snapmaker':[{'url':'https://space.snapmaker.com/en/model/35773'},{'url':'https://space.snapmaker.com/en/model/35785','status':'review'},{'url':'https://space.snapmaker.com/en/model/35786','status':'rejected'}]}
        self.assertEqual(m.links_for(rows),[{'platform':'snapmaker','url':'https://space.snapmaker.com/en/model/35773'}])
        self.assertIsNone(m.public_url('snapmaker','https://space.snapmaker.com/en/creator/upload'))
    def test_hierarchy(self):
        self.assertEqual(m.slug(Path('boardgames/spirit_island/token_set')),'boardgames/spirit-island/token-set')

class RefreshTests(unittest.TestCase):
    def test_source_gap_keeps_published_entry_links_photo_and_description(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';target=root/'site';(source/'present').mkdir(parents=True);(target/'content').mkdir(parents=True)
            old={'id':'present','title':'Published title','summary':'Published description','image':'/published.webp','links':[{'platform':'printables','url':'https://www.printables.com/model/11'}]}
            missing={'id':'missing','title':'Still public','links':[{'platform':'makerworld','url':'https://makerworld.com/en/models/12'}]}
            (target/'content/prints.json').write_text(json.dumps({'items':[missing,old]}))
            (source/'present/model.toml').write_text('title="Work in progress title"\nsummary="Work in progress description"\n')
            (source/'present/published_urls.json').write_text(json.dumps({'makerworld':[{'url':'https://makerworld.com/en/models/13'}]}))
            (source/'present/photo.jpg').write_bytes(b'Unrelated unfinished photo: never import this in link refresh')
            receipt=m.export(source,target,refresh_links=True)
            actual={i['id']:i for i in json.loads((target/'content/prints.json').read_text())['items']}
            self.assertEqual(list(actual),['missing','present'])
            self.assertEqual(actual['missing'],missing)
            self.assertEqual(actual['present']['title'],'Published title')
            self.assertEqual(actual['present']['summary'],'Published description')
            self.assertEqual(actual['present']['image'],'/published.webp')
            self.assertEqual(actual['present']['links'],old['links']+[{'platform':'makerworld','url':'https://makerworld.com/en/models/13'}])
            self.assertEqual(receipt['retained_missing'],['missing'])

    def test_empty_observation_does_not_remove_known_publications(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';source.mkdir();target=root/'site';(target/'content').mkdir(parents=True)
            known={'items':[{'id':'known','title':'Known','links':[]}]}
            (target/'content/prints.json').write_text(json.dumps(known))
            m.export(source,target,refresh_links=True)
            self.assertEqual(json.loads((target/'content/prints.json').read_text()),known)

unittest.main()
