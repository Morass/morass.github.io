# Release sync

Two hub jobs keep the hub in step with the stores. Only **final products** appear:
a released Steam game, a production mobile release, a live Chrome Web Store listing,
an album that is out, a print listing that is public. Never add anything in review,
in closed testing, pre-save or "coming soon". A card for something not final is taken
down (owner, 2026-11-10: no future projects shown while in testing).

| Job | Kind | What |
|---|---|---|
| `pages-links` | command, daily 12:20, no model | [`scripts/links_daily.sh`](../scripts/links_daily.sh): music store links (`ambient-music/tools/release_links.py`), MakerWorld URLs of listings that left review (`prints/publisher/audit_makerworld.py --only-missing --write-urls`), prints re-import, build, check, commit, push. |
| `pages-sync` | Sonnet agent, any seat, daily 05:25 | Gate `scripts/release_watch.py gate` skips it unless there is new work. The agent follows the section below. |

## Store-link command

`pages-links` uses `scripts/links_daily.py` through the shell entrypoint. It makes no AI
calls; zero tokens describes its implementation, not whether it found work. The daily
12:20 cadence and one-hour scheduler ceiling remain; the coordinator has its own
20-minute wall budget and bounded subprocess groups. Browser collectors use
`scripts/store_browser.py` with a dedicated seed tab, bounded attachment/navigation,
and cleanup of that tab only. Chrome must already be running; the job never restarts it.

The coordinator uses three owned candidates under
`/Volumes/BACKUP-1/worktrees/pages-links/`, one per source/site repository. It never stages
from shared canonical checkouts. Prints candidates omit large CAD/video/archive files.
The existing Git integrity checker records ownership and verifies remote-default ancestry.
Commit, merge, push, gate and live-check failures return nonzero and retain the candidate
with the exact commit/blocker. Every run first recovers existing candidates; a blocked site
publication defers fresh discovery. Independent source work cannot change a blocked source
candidate. No force push, stash, automatic conflict resolution or gate weakening is allowed.
Successful candidates are released and removed with their branches in the same run.

`~/.local/state/pages-links/state.json` is locked and atomic; it retains candidate ownership
and the latest 500 phase receipts. `music-scan.json` and `prints-scan.json` checkpoint item
outcomes. Known music links survive incomplete discovery; one failed album does not stop
later albums. MakerWorld request/schema failures are errors, while no verified match is
`unknown` with a next action. A known-public search control must work before URL recovery;
only unique creator/title or slug identity qualifies, never a sole unrelated hit. Variant
ambiguity stays unresolved. `--list` avoids unrelated description audits in the daily job.

Daily exports are additive: missing source records preserve existing albums, print entries
and store links. Print link refresh retains existing photos/descriptions; only a genuinely
new public item imports full metadata. An empty snapshot cannot withdraw a published item.
`prints-export.json` records retained IDs whose committed source metadata is absent.
Explicit catalogue removal remains the publisher's separate reviewed export operation.

Sources publish before site export. The site is built and checked on the integrated
candidate before push, then each changed HTML page must match the live bytes within a
bounded deadline. HTTP 200 alone is insufficient. A failed push retries even when the
candidate checkout is clean. Source collectors and the coordinator write partial diagnostics
on failure; a successful observation with unknown MakerWorld rows is not a recovered URL.

Tests: `python3.13 scripts/test-links-daily.py`, `scripts/test-store-browser.py`,
`ambient-music/tools/test_release_links.py`, and `prints/publisher/test_makerworld_links.py`.
When deploying immutable runner/helper files, use a verified remote-default site commit and
keep their paths together; `STORE_BROWSER_TOOLS` points collectors at that pinned helper.
The data collectors themselves run from their freshly fetched source candidate.

## Release watcher

`release_watch.py scan` prints open items with stable IDs and explicit errors. The gate
records at most five due item IDs in `~/.local/state/pages-sync/state.json`; unresolved
items retry after 20 hours, so they are eligible at the next daily slot. New URL/channel
payloads get their own identity. Dispatch is an attempt, never completion. Error-only and
partial scans can wake a diagnostic pass immediately, then at most once per 20 hours for
the same errors, independently of publication items.

Every CLI scan has a 70-second whole-scan wall budget (POSIX timer) and each request has a
10-second maximum timeout, below the Hub's 120-second gate limit. Completed source results
survive a later source timeout; errors stay visible. Steam API `success:false`, truncated
searches, unhealthy/stale mobile observations and extension request failures are not empty
successes. A source failure never establishes withdrawal. Mobile input must be generated
within 36 hours and each accepted cell must have a fresh successful check.

Sources: public Steam developer search and product details; the public itch.io profile
(`morassgames.itch.io`, which lists only published games); the Hub distribution snapshot;
store links in known extension repos; released albums and the artist registry. Discovery
is intentionally scoped. Missing inventory rows cannot prove that a product is unreleased.
A Steam removal needs positive `coming_soon` product metadata and public-page corroboration.
A mobile removal needs fresh, identity-matched explicit `removed` status and independent
public absence for every linked store; a live store on either platform preserves the page.
Unknown, missing, not-submitted, rejected or unreadable status preserves existing content
and reports the unresolved evidence. Public Apple lookup must explicitly return zero results;
Play must return HTTP 404. Timeouts, HTTP 200 shells and other failures do not prove absence.

State writes are locked and atomic. `scan.json` is the gate's observation receipt;
`state.json` retains attempts, blocked work and up to 1000 completion/blocker receipts.
A clean scan only changes unseen entries to `not-observed`, never `verified`; partial scans
retain unseen work. Legacy `gate.json` is not used for the new per-item queue and is preserved.
Tests: `scripts/test-release-watch.py` and `scripts/test-release-reliability.py`.

Deployment may pin a verified script and this policy outside the checkout. In that case
use the deployed command from the live job prompt, with `PAGES_SYNC_ROOT` pointing at the
site checkout and `PAGES_SYNC_PROGRAMS` at the actual fleet root. Never use the deployment
directory or an external task worktree as the fleet root.

## The agent, per item

Read the gate's `scan.json` and `state.json` dispatch first. Revalidate the dispatched
items with the deployed `scan` command before edits; work only its due IDs, at most five.
When the dispatch is diagnostic-only, report the exact upstream failure without inventing
content changes. Inspect existing branches/worktrees and retained receipts first; resume
an existing valid publication candidate before starting unrelated items. Respect live owners.
If a candidate is blocked, retain its exact tip, gate and next action in the receipt and Git
integrity note. Never hide or discard another agent's work. For each due item:

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
- **itch / link**: the game's page and card exist but do not link its itch.io URL. Add a
  secondary CTA "Get it on itch.io" (`cta cta-secondary`, `target="_blank" rel="noopener"`)
  right after the Steam CTA, linking the item's store URL; keep every Steam link. The card
  label in `content/projects.json` becomes `<genre> · Steam & itch.io`.
- **itch / create**: a public itch game with no page or card. Build it like **steam / create**
  with the itch CTA as the primary one and label `<genre> · itch.io`. Facts come from the itch
  page and the game repo; the capsule is the itch cover image. If no repo or verifiable
  description exists, record the item blocked with that reason rather than inventing copy.
  Itch absence never removes a card or a link.
- **mobile / release, create or merge**: as above with [`wardfall/index.html`](../wardfall/index.html)
  and the `mobile` section; link only the store URLs in the item. One live store makes
  the label `Android` or `iOS`; both make `Android & iOS · Google Play & App Store`.
  `merge` means a page already exists, possibly in the Steam section: preserve its content,
  Steam card/CTA and art, then add the confirmed mobile links and mobile card to that same
  route. Never replace a page just because one platform card is missing. Existing store
  links are preserved unless their withdrawal is independently confirmed.
- **extension / release**: set that tool's `url` in `content/projects.json` to the store URL.
- **steam or mobile / remove**: only items carrying the watcher’s product-specific
  `evidence` are eligible. Recheck that evidence immediately before editing; never infer
  withdrawal from inventory absence, a source error or testing/rejected status alone.
  Remove the card and generated listing links. Preserve the authored page and support URL;
  keep an active platform's page/indexing unchanged. If all platforms are corroborated as
  nonfinal, retain the page with `noindex` and remove misleading release text. Do not delete
  a product directory: store-config discovery cannot prove a support URL has no consumers.
  A malformed or missing evidence object means blocked, not permission to remove.
- **music / create-artist**: an album is out under an artist the build does not know.
  Add the artist to `content/music-artists.json` (name, slug, one-sentence summary
  from `ambient-music`'s releases and docs), then run
  `/opt/homebrew/bin/python3 /Volumes/BACKUP-1/programs/ambient-music/tools/release_links.py --hub .`
  (needs the CDP Chrome; run it over `ssh -o BatchMode=yes localhost` on a TCC refusal).

Then `python3.13 scripts/build.py && python3.13 scripts/check.py`, stage exact paths,
commit and push. Verify the commit on remote default with the shared Git integrity checker.
Poll live deployment with a bounded deadline; do not launch an unbounded background wait.
Re-scan: the item must no longer be open. Then record its actual disposition using the
same deployed script and state path:

```bash
python3 <deployed-script> record <id> blocked '<exact blocker; candidate tip; next acceptance check>'
python3 <deployed-script> record <id> verified '<what changed and live check>' --commit <full-sha> --path <relative-page-directory>
```

The verified helper fetches remote default, verifies commit ancestry, checks the item's
page/card identity, and compares the live HTML with the integrated page bytes. Publication
is not verified on HTTP 200 alone. It rejects a wrong page, unlanded SHA or stale deployment.
For extension items use the public tools group page; for artist items use `music/<slug>`.
Failures remain blocked with concrete next action; do not call an attempted update done.
A genuine complete scan with no work skips the model. Finish one line per item: verified
live URL and remote-default SHA, or retained candidate/blocker and next acceptance check.
