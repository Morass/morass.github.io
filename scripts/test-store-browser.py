import contextlib
import unittest
from unittest.mock import Mock, patch
import store_browser as browser


class OwnedTab(unittest.TestCase):
    def test_seed_precedes_attach_and_only_owned_tab_is_closed_on_error(self):
        calls=[]
        page=Mock();peer=Mock(url='https://peer.example')
        chromium=Mock()
        def seed(endpoint,route,method):
            calls.append('seed')
            page.url=route.removeprefix('/json/new?')
            return {'id':'owned-tab'}
        def attach(*args,**kwargs):
            calls.append('attach')
            return Mock(contexts=[Mock(pages=[peer,page])])
        chromium.connect_over_cdp.side_effect=attach
        runtime=Mock(chromium=chromium)
        with patch('playwright.sync_api.sync_playwright',return_value=contextlib.nullcontext(runtime)), patch.object(browser,'devtools',side_effect=seed), patch('urllib.request.urlopen',return_value=contextlib.nullcontext(Mock())) as close:
            with self.assertRaisesRegex(RuntimeError,'read failed'):
                with browser.open_page() as actual:
                    self.assertIs(actual,page)
                    raise RuntimeError('read failed')
        self.assertEqual(calls,['seed','attach'])
        page.close.assert_called_once()
        peer.close.assert_not_called()
        close.assert_called_once()
        self.assertTrue(close.call_args.args[0].endswith('/json/close/owned-tab'))

    def test_failed_attach_has_two_attempts_and_releases_seed(self):
        chromium=Mock();chromium.connect_over_cdp.side_effect=RuntimeError('timeout')
        with patch('playwright.sync_api.sync_playwright',return_value=contextlib.nullcontext(Mock(chromium=chromium))), patch.object(browser,'devtools',return_value={'id':'owned'}), patch.object(browser.time,'sleep'), patch('urllib.request.urlopen',return_value=contextlib.nullcontext(Mock())) as close:
            with self.assertRaisesRegex(RuntimeError,'timeout'):
                with browser.open_page():self.fail('unreachable')
        self.assertEqual(chromium.connect_over_cdp.call_count,2)
        self.assertTrue(close.call_args.args[0].endswith('/json/close/owned'))

    def test_navigation_retries_once_then_surfaces_failure(self):
        page=Mock();page.goto.side_effect=RuntimeError('navigation timeout')
        with self.assertRaisesRegex(RuntimeError,'navigation timeout'):browser.goto(page,'https://example.com')
        self.assertEqual(page.goto.call_count,2)

    def test_http_block_is_not_empty_success(self):
        page=Mock();page.goto.return_value=Mock(status=403)
        with self.assertRaisesRegex(RuntimeError,'HTTP 403'):browser.goto(page,'https://example.com')


if __name__=='__main__':unittest.main()
