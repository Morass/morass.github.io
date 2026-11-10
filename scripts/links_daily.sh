#!/bin/bash
# Daily store-link refresh for the hub; run by the hub job "pages-links" over ssh localhost
# (the music repo is on /Volumes, which launchd's binary cannot read). docs/release-sync.md
set -uo pipefail
export PATH=/opt/homebrew/bin:/usr/bin:/bin
HUB=$HOME/programs/morass.github.io
MUSIC=/Volumes/BACKUP-1/programs/ambient-music
PRINTS=$HOME/programs/prints
HUB_PATHS=(content/music.json content/prints.json content/generated-pages.json
           assets/music assets/prints music prints index.html sitemap.xml)
fail=0

sync() { git -C "$1" fetch -q && git -C "$1" merge -q --no-edit '@{u}'; }

sync "$HUB" || { echo "hub: cannot sync with origin" >&2; exit 1; }
# Another agent's uncommitted edit in a page the build rewrites would ride along in our commit.
if [ -n "$(git -C "$HUB" status --porcelain -- "${HUB_PATHS[@]}")" ]; then
    echo "hub has uncommitted changes in the generated paths; skipped" >&2
    exit 1
fi

# connect_over_cdp waits forever on a frozen tab in the shared Chrome, hence the timeouts.
if sync "$MUSIC" && (cd "$MUSIC" && timeout 900 python3 tools/release_links.py --hub "$HUB"); then
    if [ -n "$(git -C "$MUSIC" status --porcelain -- releases)" ]; then
        git -C "$MUSIC" add releases/*/links.json
        git -C "$MUSIC" commit -q -m "Store links: daily update" -- releases/*/links.json
        git -C "$MUSIC" push -q && echo "ambient-music: links.json updated"
    fi
else
    echo "music: store links refresh failed" >&2; fail=1
fi

# Only records this run changed are ours; a publisher run may have others open.
before=$(git -C "$PRINTS" status --porcelain -- '*published_urls.json' | sort)
if sync "$PRINTS" && (cd "$PRINTS" && timeout 900 python3 publisher/audit_makerworld.py --only-missing --write-urls); then
    mine=$(comm -13 <(echo "$before") <(git -C "$PRINTS" status --porcelain -- '*published_urls.json' | sort) | awk '{print $2}')
    if [ -n "$mine" ]; then
        # shellcheck disable=SC2086
        git -C "$PRINTS" commit -q -m "Record MakerWorld URLs of listings out of review" -- $mine
        git -C "$PRINTS" push -q && echo "prints: MakerWorld URLs recorded: $(echo $mine | wc -w)"
    fi
else
    echo "prints: MakerWorld URL repair failed" >&2; fail=1
fi
(cd "$HUB" && python3.13 scripts/import-prints.py --source "$PRINTS") || { echo "prints: import failed" >&2; fail=1; }

cd "$HUB"
if [ -n "$(git status --porcelain -- content/music.json content/prints.json assets/music assets/prints)" ]; then
    python3.13 scripts/build.py && python3.13 scripts/check.py || { echo "hub: build/check failed; nothing committed" >&2; exit 1; }
    git add -- "${HUB_PATHS[@]}"
    git commit -q -m "Store links update (music, prints)" -- "${HUB_PATHS[@]}"
    git push -q && echo "hub: pages updated"
else
    echo "no new store links"
fi
exit $fail
