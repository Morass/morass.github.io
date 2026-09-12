# Morass project hub

[website] [publishing] [static]

Public crossroads at <https://morass.github.io/>: **Morass Games** (Steam),
**Small Games** (browser), **Mobile**, **YouTube**, and **Prints**. Pushing `main`
deploys GitHub Pages. The homepage opens directly on the five project cards,
without a featured-game hero. Existing game routes and `app-ads.txt` remain stable.

## Sources and build

- `content/projects.json`: curated game/project cards, public channels and profiles.
- `content/prints.json`: exported listing metadata; do not hand-maintain a second catalogue.
- `scripts/build.py`: hub, category and print leaf pages, sitemap and generated-page manifest.
- `hub.css`, `hub.js`: responsive hub UI and progressive search, without runtime dependencies.
- `theme.js`: dark by default; the header toggle remembers a light/dark choice in
  local storage and restores it before styles load. Storage-disabled and no-JS
  browsers retain a usable dark default. Game runtimes keep their own artwork/UI.
- Existing `<game>/index.html`: authored game pages, using `style.css`.
- `assets/ui/manifest.json`: reused warehouse printshop icons and paper texture provenance.
- `small-games/borrowed-ink/play/`: released standalone bundle with its license and version receipt.

```bash
python3.13 scripts/import-prints.py --source ../prints
python3.13 scripts/build.py
python3.13 scripts/test-import-prints.py
python3.13 scripts/check.py
```

The importer requires Python 3.11+ and Pillow, already installed in the fleet's
`python3.13`. The builder/checker use only the standard library. No Node build,
package download, browser install or hosted search service is needed.

## Publishing updates

After an authorized print upload, verify the public listing and record it in the
model's `published_urls.json`. Then run the commands above, inspect the changed
leaf and its category, stage **only the resulting site paths**, commit and push.
For an all-platform upload, run this once after the completed platform audits.
If a platform is still reviewing, export its public model URL only after it is
actually public; editor, profile/verifying and signed preview URLs are rejected.
Website publication never authorizes uploading an unpublished model elsewhere.

The importer preserves the prints repo's directory hierarchy, converts underscores
to kebab-case routes, uses only explicitly selected public metadata, and makes
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
# hidden = true  # Remove the item from the next export.
```

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

## Validation and release

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
