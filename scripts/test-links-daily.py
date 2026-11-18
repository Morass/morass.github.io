"""Failure regressions: publication, restart ownership, concurrent default and live proof."""
import contextlib
import argparse
import http.server
import importlib.util
import json
import os
import time
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('links_daily', Path(__file__).with_name('links_daily.py'))
links = importlib.util.module_from_spec(spec)
spec.loader.exec_module(links)


class Publication(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root/'remote.git'
        links.command(['git','init','--bare','-b','main',self.remote])
        self.repo = self.root/'shared'
        links.command(['git','clone',self.remote,self.repo])
        (self.repo/'releases/a').mkdir(parents=True)
        (self.repo/'releases/a/links.json').write_text('{"spotify":"old"}\n')
        links.git(self.repo,'add','releases/a/links.json')
        links.git(self.repo,'commit','-F','-',data='test fixture\n')
        links.git(self.repo,'push','origin','main')
        links.git(self.repo,'remote','set-head','origin','-a')
        self.checker=self.root/'checker.py'
        self.checker.write_text('''import subprocess,sys
args=sys.argv
repo=args[args.index('--repo')+1]
if args[1]=='check':
 sha=args[args.index('--commit')+1]
 subprocess.run(['git','-C',repo,'fetch','-q','origin'],check=True)
 subprocess.run(['git','-C',repo,'merge-base','--is-ancestor',sha,'origin/main'],check=True)
''')
        self.journal=links.Journal(self.root/'state.json')
        self.candidate=self.make_candidate()
        self.candidate.prepare()

    def make_candidate(self):
        return links.Candidate('music',self.repo,self.root/'worktrees',links.Journal(self.root/'state.json'),self.checker)

    def change(self):
        (self.candidate.path/'releases/a/links.json').write_text('{"spotify":"new"}\n')

    def remote_record(self):
        return links.git(self.remote,'show','main:releases/a/links.json')

    def test_commit_failure_is_visible_and_retains_loose_candidate(self):
        self.change()
        hook=self.remote.parent/'shared/.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 1\n');hook.chmod(0o755)
        with self.assertRaises(RuntimeError):self.candidate.publish()
        self.assertEqual(json.loads(self.remote_record()),{'spotify':'old'})
        self.assertEqual(json.loads((self.candidate.path/'releases/a/links.json').read_text()),{'spotify':'new'})
        self.assertFalse(any(r['status']=='remote-verified' for r in self.candidate.journal.data['receipts']))

    def test_failed_push_is_retried_after_restart_without_new_discovery(self):
        self.change()
        hook=self.remote/'hooks/pre-receive';hook.write_text('#!/bin/sh\nexit 1\n');hook.chmod(0o755)
        with self.assertRaises(RuntimeError):self.candidate.publish()
        retained=links.git(self.candidate.path,'rev-parse','HEAD')
        self.assertEqual(json.loads(self.remote_record()),{'spotify':'old'})
        self.assertEqual(self.candidate.changes(),[])
        hook.unlink()
        resumed=self.make_candidate();resumed.prepare();sha=resumed.publish()
        self.assertEqual(sha,retained)
        self.assertEqual(json.loads(self.remote_record()),{'spotify':'new'})
        resumed.release()
        self.assertFalse(resumed.path.exists())
        self.assertEqual(links.git(self.repo,'for-each-ref','--format=%(refname)',resumed.ref),'')
        self.assertEqual(links.Journal(self.root/'state.json').data['candidates'],{})

    def test_shared_uncommitted_edit_is_never_staged(self):
        (self.repo/'releases/a/links.json').write_text('{"spotify":"peer-wip"}')
        self.change();self.candidate.publish()
        self.assertEqual(json.loads(self.remote_record()),{'spotify':'new'})
        self.assertEqual(json.loads((self.repo/'releases/a/links.json').read_text()),{'spotify':'peer-wip'})
        self.assertIn(' M releases/a/links.json',links.git(self.repo,'status','--porcelain'))

    def test_concurrent_unrelated_default_commit_is_preserved(self):
        self.change()
        (self.repo/'peer.txt').write_text('peer')
        links.git(self.repo,'add','peer.txt');links.git(self.repo,'commit','-F','-',data='peer fixture\n')
        links.git(self.repo,'push','origin','main')
        self.candidate.publish()
        self.assertEqual(links.git(self.remote,'show','main:peer.txt'),'peer')
        self.assertEqual(json.loads(self.remote_record()),{'spotify':'new'})

    def test_out_of_scope_candidate_change_blocks_publication(self):
        (self.candidate.path/'unrelated.txt').write_text('never publish')
        with self.assertRaisesRegex(RuntimeError,'Unexpected candidate paths'):self.candidate.publish()
        self.assertEqual(json.loads(self.remote_record()),{'spotify':'old'})

    def test_missing_retained_worktree_blocks_replacement(self):
        links.git(self.repo,'worktree','remove',self.candidate.path)
        with self.assertRaisesRegex(RuntimeError,'Retained candidate missing'):self.make_candidate().prepare()

    def test_interrupted_initial_checkout_resumes_before_collection(self):
        (self.candidate.path/'releases/a/links.json').unlink()
        self.candidate.journal.data['candidates']['music']['phase']='creating'
        self.candidate.journal.save()
        resumed=self.make_candidate();resumed.prepare()
        self.assertEqual(json.loads((resumed.path/'releases/a/links.json').read_text()),{'spotify':'old'})
        self.assertEqual(resumed.journal.data['candidates']['music']['phase'],'ready')

    def test_interrupted_initialization_does_not_erase_unknown_loose_files(self):
        (self.candidate.path/'peer.txt').write_text('preserve')
        self.candidate.journal.data['candidates']['music']['phase']='creating'
        self.candidate.journal.save()
        resumed=self.make_candidate()
        with self.assertRaisesRegex(RuntimeError,'Unexpected loose files'):resumed.prepare()
        self.assertEqual((resumed.path/'peer.txt').read_text(),'preserve')

    def test_externally_released_candidate_is_not_reactivated(self):
        reviews=self.root/'reviews.json'
        reviews.write_text(json.dumps({str(self.repo.resolve())+'|'+self.candidate.ref:{'state':'discarded'}}))
        resumed=self.make_candidate();resumed.review_file=reviews
        with self.assertRaisesRegex(RuntimeError,'released externally'):resumed.prepare()
        self.assertTrue(resumed.path.exists())

    def test_interrupted_verified_cleanup_finishes_before_new_work(self):
        self.change();self.candidate.publish()
        original_git=links.git
        def fail_delete(root,*args,**kwargs):
            if args[:2]==('branch','-d'):raise RuntimeError('interrupted branch cleanup')
            return original_git(root,*args,**kwargs)
        with patch.object(links,'git',side_effect=fail_delete),self.assertRaisesRegex(RuntimeError,'interrupted branch cleanup'):
            self.candidate.release()
        self.assertFalse(self.candidate.path.exists())
        resumed=self.make_candidate();resumed.prepare()
        self.assertTrue(resumed.path.exists())
        self.assertEqual(json.loads((resumed.path/'releases/a/links.json').read_text()),{'spotify':'new'})
        self.assertNotEqual(resumed.journal.data['candidates']['music'].get('phase'),'cleanup')

    def test_interrupted_atomic_scratch_retries_without_losing_last_record(self):
        (self.candidate.path/'releases/a/links.tmp').write_text('{broken')
        self.candidate.publish()
        self.assertEqual(json.loads(self.remote_record()),{'spotify':'old'})
        self.assertFalse((self.candidate.path/'releases/a/links.tmp').exists())
        self.assertTrue(any(r['status']=='retry' for r in self.candidate.journal.data['receipts']))

    def test_live_http_200_requires_exact_integrated_bytes(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            body=b'wrong page'
            def do_GET(self):
                self.send_response(200);self.end_headers();self.wfile.write(self.body)
            def log_message(self,*args):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            (self.candidate.path/'index.html').write_bytes(b'correct page')
            links.git(self.candidate.path,'add','index.html')
            links.git(self.candidate.path,'commit','-F','-',data='live verification fixture\n')
            url=f'http://127.0.0.1:{server.server_port}'
            with self.assertRaisesRegex(RuntimeError,'Live deployment unverified'):
                links.verify_live(self.candidate,url,timeout=0)
            Handler.body=b'correct page'
            links.verify_live(self.candidate,url,timeout=0)
            receipt=self.candidate.journal.data['receipts'][-1]
            self.assertEqual(receipt['status'],'verified');self.assertEqual(receipt['pages'],1)
        finally:
            server.shutdown();server.server_close();thread.join()


class Budget(unittest.TestCase):
    def test_whole_run_deadline_retains_diagnostic_and_kills_subprocess(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);binary=root/'bin';binary.mkdir();state=root/'state.json'
            shim=binary/'git'
            shim.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(30)\n')
            shim.chmod(0o755)
            started=time.monotonic()
            result=subprocess.run([sys.executable, str(Path(links.__file__)), '--site',str(root/'site'),
                '--state',str(state),'--worktrees',str(root/'worktrees'),'--budget-seconds','1'],
                env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ.get('PATH','')),capture_output=True,timeout=8)
            self.assertEqual(result.returncode,1)
            self.assertLess(time.monotonic()-started,8)
            receipt=json.loads(state.read_text())['receipts'][-1]
            self.assertEqual(receipt['status'],'failed')
            self.assertIn('deadline',receipt['error'])


class Pipeline(unittest.TestCase):
    def exercise(self, partial):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            checker=root/'checker.py'
            checker.write_text("import sys,subprocess\na=sys.argv\nr=a[a.index('--repo')+1]\nif a[1]=='check':\n s=a[a.index('--commit')+1]\n subprocess.run(['git','-C',r,'fetch','-q','origin'],check=True)\n subprocess.run(['git','-C',r,'merge-base','--is-ancestor',s,'origin/main'],check=True)\n")
            repos={}; remotes={}
            source=r"""import argparse,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path);p.add_argument('--export-only',action='store_true');p.add_argument('--hub',type=Path);a=p.parse_args()
if a.export_only:
 (a.hub/'content/music.json').write_text((Path('releases/a/links.json')).read_text())
else:
 Path('releases/a/links.json').write_text('{"label":"new"}')
 a.receipt.write_text(json.dumps({'status':STATUS,'items':[{'release':'a','status':STATUS}]}))
 sys.exit(CODE)
""".replace('STATUS',repr('error' if partial else 'complete')).replace('CODE','1' if partial else '0')
            for kind in ['site','music','prints']:
                repo=root/kind;remote=root/(kind+'.git');repos[kind]=repo;remotes[kind]=remote
                links.command(['git','init','--bare','-b','main',remote]);links.command(['git','clone',remote,repo])
                files={'site':{'content/music.json':'{"label":"old"}', 'content/prints.json':'{}', 'index.html':'<html>old</html>',
                    'scripts/build.py':"import json\nfrom pathlib import Path\nx=json.loads(Path('content/music.json').read_text())\nPath('index.html').write_text('<html>'+x['label']+'</html>')\n",
                    'scripts/check.py':'pass\n',
                    'scripts/import-prints.py':"import argparse\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--source');p.add_argument('--destination',type=Path);a=p.parse_args();(a.destination/'content/prints.json').write_text('{}')\n"},
                    'music':{'releases/a/links.json':'{"label":"old"}', 'tools/release_links.py':source},
                    'prints':{'publisher/audit_makerworld.py':"import argparse,json\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--only-missing',action='store_true');p.add_argument('--write-urls',action='store_true');p.add_argument('--list',action='store_true');p.add_argument('--receipt',type=Path);a=p.parse_args();a.receipt.write_text(json.dumps({'status':'complete','items':[]}))\n"}}[kind]
                for name,value in files.items():
                    path=repo/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value)
                links.git(repo,'add','--',*files)
                links.git(repo,'commit','-F','-',data='pipeline fixture\n');links.git(repo,'push','origin','main');links.git(repo,'remote','set-head','origin','-a')
            peer=repos['music']/'releases/a/links.json';peer.write_text('{"peer":"wip"}')
            site_remote=remotes['site']
            class Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    data=links.git(site_remote,'show','main:index.html').encode()
                    self.send_response(200);self.end_headers();self.wfile.write(data)
                def log_message(self,*args):pass
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                args=argparse.Namespace(**repos,worktrees=root/'candidates',state=root/'state/state.json',checker=checker,
                    live_url=f'http://127.0.0.1:{server.server_port}',live_timeout=0)
                journal=links.Journal(args.state)
                code=links.run(args,journal)
                self.assertEqual(code,1 if partial else 0)
                self.assertEqual(journal.data['receipts'][-1]['status'],'failed' if partial else 'complete')
                self.assertEqual(journal.data['candidates'],{})
                self.assertEqual(links.git(site_remote,'show','main:index.html'),'<html>new</html>')
                self.assertEqual(links.git(remotes['music'],'show','main:releases/a/links.json'),'{"label":"new"}')
                self.assertEqual(peer.read_text(),'{"peer":"wip"}')
                scan=[r for r in journal.data['receipts'] if r['phase']=='music-scan'][-1]
                self.assertEqual(scan['items'][0]['status'],'error' if partial else 'complete')
            finally:
                server.shutdown();server.server_close();thread.join()

    def test_full_delivery_cleans_all_candidates(self):
        self.exercise(False)

    def test_partial_source_progress_delivers_but_run_reports_failure(self):
        self.exercise(True)


if __name__=='__main__':
    unittest.main()
