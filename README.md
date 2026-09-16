# Morass project hub

[website] [publishing] [static]

Public crossroads at <https://morass.github.io/>: **Games** (Steam),
**Small Games** (browser), **Mobile**, **YouTube**, and **Prints**. Pushing `main`
deploys GitHub Pages (the repo's only Actions run is GitHub's own
`pages-build-deployment`; `.nojekyll` makes it copy files as-is, no Jekyll). The homepage opens directly on the five project cards,
without a featured-game hero. The visual direction is fantasy, because most
projects come from fantasy worlds: EB Garamond throughout (small caps for nav,
labels and buttons), a wax-seal brand mark, lamplit grained parchment/leather
grounds, gilt card frames with brass book-corners, scroll dividers, Roman-numeral
card labels and a sun/moon theme toggle. The ornaments are inline SVG data URIs
in the "Fantasy pass" block of `hub.css`, masked so they follow the theme colours.
Existing game routes and `app-ads.txt` remain stable.

## Sources and build

- `content/projects.json`: curated game/project cards, public channels and profiles.
  Small games are **never ordered by hand**: each `small-games` entry names a `type`
  from `smallGameTypes` (slug, bucket title, card label). `/small-games/` shows one
  section per type, buckets A–Z by title and games A–Z within each; an unknown type
  fails the build. A new kind of game (arcade, word, card…) adds its type there.
- `content/prints.json`: exported listing metadata; do not hand-maintain a second catalogue.
- `content/print-collections.json`: curated browsing hierarchy, model-to-collection
  assignments, category redirects and exceptional model routes.
- `content/print-tags.json`: the tag vocabulary. Marketplace tags arrive in every
  spelling (`nosupports`, `no-supports`, `no supports`); the builder folds them to one
  kebab-case tag per idea via this file's `drop` (workflow words such as `openscad`),
  `aliases` (synonyms and plurals) and `labels` (acronyms and brands). Leaves show
  their tags as chips, `/prints/tags/` lists every tag two or more prints share, and a
  tag carried by one print links to `/prints/search/?tag=<tag>` instead.
- `scripts/build.py`: hub, category and print leaf pages, sitemap and generated-page manifest.
- `hub.css`, `hub.js`: responsive hub UI and progressive search, without runtime dependencies.
- `theme.js`: dark by default; the header toggle remembers a light/dark choice in
  local storage and restores it before styles load. Storage-disabled and no-JS
  browsers retain a usable dark default. Game runtimes keep their own artwork/UI.
- Existing `<game>/index.html`: authored game content; the builder refreshes
  marked shared header/footer blocks. `style.css` supplies game-specific layout,
  and `hub.css` supplies the same typography, colors, controls and theme as the hub.
  `privacy.html` uses the same shell. The playable minigame bundle is excluded.
- `assets/ui/channel-*.svg`: vector redraws of each YouTube channel's avatar, named by
  `icon` in `content/projects.json`; redraw one when a channel changes its avatar.
- `assets/ui/manifest.json`: warehouse printshop icons, paper texture and
  subset EB Garamond provenance; font license is `assets/ui/OFL.txt`.
- `small-games/borrowed-ink/play/`: released standalone bundle with its license and version receipt.
  Lanternward has no bundle here (owner, 2026-09-15): a 45 MB Godot runtime would grow the repo
  on every update, and the portals pay; its page links the approved portals instead.

```bash
python3.13 scripts/import-prints.py --source ../prints
python3.13 scripts/build.py
python3.13 scripts/test-import-prints.py
python3.13 scripts/test-print-tags.py
python3.13 scripts/check.py
```

The importer requires Python 3.11+ and Pillow, already installed in the fleet's
`python3.13`. The builder/checker use only the standard library. No Node build,
package download, browser install or hosted search service is needed.

## Publishing updates

**Every** print deployment ends here (owner rule, 2026-09-15): one platform, all
three, a re-upload or a listing edit that changes what a leaf shows. It is not done
until `https://morass.github.io/prints/<id>/` is live with every confirmed link;
the full procedure is in [PUBLISHING.md](../prints/publisher/PUBLISHING.md#keep-the-public-project-hub-current).
After an authorized print upload, verify the public listing and record it in the
model's `published_urls.json`. Choose its deepest useful collection in
`content/print-collections.json` (or set `[website].category` in model.toml).
Then run the commands above, inspect the changed
leaf and its category, stage **only the resulting site paths**, commit and push.
For an all-platform upload, run this once after the completed platform audits.
If a platform is still reviewing, export its public model URL only after it is
actually public; editor, profile/verifying and signed preview URLs are rejected.
Website publication never authorizes uploading an unpublished model elsewhere.

The importer uses the prints repo's directory path as the stable model identity,
converts underscores to kebab-case, exports selected public metadata, and makes
960×720-or-smaller WebP derivatives. It exports no STL, source, private notes or
EXIF. Multiple published variants keep all their distinct links. Catalogue cards
link inward; marketplace model links appear on leaves. Profile links live on the
Prints landing page. Existing records are source evidence, not a fresh audit of
hundreds of external listings.

Optional overrides in a model's `model.toml`:

```toml
[website]
title = "A short display title"
summary = "A short introduction for the catalogue."
image = "photo_closed.jpg"
category = "jewelry/earrings"  # Optional override of the curated collection.
tags = ["himeji", "castle"]     # Extra site tags, added to the marketplace tags.
# hidden = true  # Remove the item from the next export.
```

Search matches words anywhere in a title, summary, collection or tag; `tag:no-supports`
in the box (or `?tag=`) filters by exact tag. When a new spelling of an existing tag
appears, add it to `aliases` rather than a second tag page; the tag test fails on an
alias that points at a dropped or re-aliased tag.

Browsing categories are independent of source folders and can be as deep as useful:
`jewelry/earrings`, `decorations/coasters`, `containers/keepsake-boxes/fantasy`,
`boardgames/by-game/mtg/counters`. Existing prints are explicitly assigned in
`print-collections.json`; a new unassigned print stops the build with its ID so the
publisher chooses its proper collection rather than silently filing it elsewhere.
Create subcategories for a useful distinction, not merely to add another level.
Use kebab-case paths. Each print has one primary collection; search also uses its
other tags and full collection path. Cards, breadcrumbs and related items all
follow this hierarchy. Folder names in the prints repo need not move.

Model URLs normally remain stable when their collection changes. The old
`decorations/coasters` model URL now serves the requested Coasters collection;
Mandala Coasters lives at `decorations/coasters/mandala-coasters`, explicitly
recorded in `modelPaths`. Preserve category redirects when reshaping the tree.
The builder rejects duplicate assignments or category/model route collisions.

Otherwise the importer uses title/summary, the first photo, then a preview.
A renamed source directory changes the route: keep a redirect at the old public
URL. The builder removes only obsolete pages named in its own previous manifest;
it never removes authored game pages. Old image derivatives remain until an
explicit unreferenced-asset cleanup.

## Adding games, mobile projects or channels

Add the public card to `content/projects.json`, create its detail page and reduced
art, and rebuild. Categories already appear on the home crossroads; do not add
cards manually to generated HTML. Keep unreleased Android entries marked coming
soon; link a public Play listing only when verified. YouTube channels use public
handles/IDs, never Studio URLs. Orenvalt Archive (`@orenvaltarchive`) is the books channel; Morass Prints
(`@morass_prints`) is the making channel.

For browser games, copy only the tested **standalone** release into a `play/`
subdirectory, including its license and release receipt. Keep it ad-free unless
that release explicitly implements ads; portal SDK builds belong on portals.
Keep saved-game origins/routes stable. Portal links are added when their recorded
`publicUrl` is verified, never while only a developer preview is available.

## Adding free tools

Free tools is one section, split into groups like the print collection: `/tools/`
shows a card per group and `/tools/<group>/` lists that group's tools. The band under
the home crossroads links to it. Groups live in `toolGroups` in
`content/projects.json` (`slug`, `title`, a short monospace `mark`, `summary`); add a
tool to `tools` with `title`, public GitHub `url`, `group` (a group slug), a short
`label` and a one-sentence `summary`, then rebuild. The builder rejects a tool whose
group does not exist. List only public repositories, never private or archived ones.

## Validation and release

Every public page family uses the shared shell and light/dark preference,
including Steam game leaves, Android leaves and the privacy page. Keep game art
and game-specific content layouts; do not style the playable minigame runtime.
The builder refreshes marked chrome blocks in authored pages, preserving their
body content. Avoid independent copies of site navigation or theme CSS.

Run the importer tests and link checker, then inspect changed layouts in the
installed Chrome at desktop and phone widths. Test search, empty results, keyboard
focus and the direct play page. Reuse one browser/page for QA and stop your local
server and isolated browser afterward. Check `git diff --check`, stage exact
paths, commit, push, and confirm the Pages deployment is live. Other agents may
have unrelated work in either repo; do not stage or stash it.

## See also

- [Print publishing workflow](../prints/publisher/PUBLISHING.md)
- [Fleet public catalogue pattern](../gamedev-knowledge/topics/public-project-catalogues.md)
- [Portal distribution](../gamedev-knowledge/topics/web-portal-distribution.md)
- [Warehouse printshop kit](../gamedev-knowledge/snippets/printshop-touch-ui-kit.md)
