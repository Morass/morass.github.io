# Release sync

Two hub jobs keep the hub in step with the stores. Only **final products** appear:
a released Steam game, a production mobile release, a live Chrome Web Store listing,
an album that is out, a print listing that is public. Never add anything in review,
in closed testing, pre-save or "coming soon"; never remove an existing card.

| Job | Kind | What |
|---|---|---|
| `pages-links` | command, daily 12:20, no model | [`scripts/links_daily.sh`](../scripts/links_daily.sh): music store links (`ambient-music/tools/release_links.py`), MakerWorld URLs of listings that left review (`prints/publisher/audit_makerworld.py --only-missing --write-urls`), prints re-import, build, check, commit, push. |
| `pages-sync` | Sonnet agent, any seat, daily 05:25 | Gate `scripts/release_watch.py gate` skips it unless there is new work. The agent follows the section below. |

`release_watch.py scan` prints the open items as JSON. The gate fires on a new set of
items, again after 7 days if the same items stay open, and after 3 days of scan errors.
Sources: the Steam developer search and `appdetails` (public), the hub's distribution
snapshot (`claude_server/data/distribution.json`, collected 03:40; production-only
public URLs), a `chromewebstore.google.com/detail/...` URL in an extension repo's
README or `store/` that answers 200, and `content/music.json` against
`content/music-artists.json`.

## The agent, per item

Read the item list with `python3 scripts/release_watch.py scan`. For each item:

- **steam / release**: the page exists. Replace the coming-soon CTA and "Coming soon"
  text (body and meta descriptions) with the released form used by
  [`wardenmark/index.html`](../wardenmark/index.html) (`steam-cta` "Get it on Steam",
  the feature link), linking the item's store URL. The card label in
  `content/projects.json` becomes `<genre> · Steam`.
- **steam / create**: add `/<slug>/index.html` in the same structure as the newest
  released game page, a card in `content/projects.json` `games`, and
  `/<slug>/assets/capsule.png` from Steam's header capsule. Facts come from Steam
  `appdetails` (`short_description`, genres) and the game repo
  (`~/programs/<slug>`, its `AIM.md`/`README.md`, `store/` files); never invent a
  feature.
- **mobile / release or create**: as above with [`wardfall/index.html`](../wardfall/index.html)
  and the `mobile` section; link only the store URLs in the item. One live store makes
  the label `Android` or `iOS`; both make `Android & iOS · Google Play & App Store`.
- **extension / release**: set that tool's `url` in `content/projects.json` to the store URL.
- **music / create-artist**: an album is out under an artist the build does not know.
  Add the artist to `content/music-artists.json` (name, slug, one-sentence summary
  from `ambient-music`'s releases and docs), then run
  `/opt/homebrew/bin/python3 /Volumes/BACKUP-1/programs/ambient-music/tools/release_links.py --hub .`
  (needs the CDP Chrome; run it over `ssh -o BatchMode=yes localhost` on a TCC refusal).

Then `python3.13 scripts/build.py && python3.13 scripts/check.py`, stage only the paths
you changed, commit, push, and verify the live page with `curl` once Pages deploys
(about a minute). `release_watch.py scan` must no longer list the item. An item you
cannot finish (missing art or facts) stays open; report what is missing instead of
guessing. Finish with one line per item: done with its live URL, or why not.
