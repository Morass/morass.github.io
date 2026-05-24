# morass.github.io

Public website for [Morass Games](https://morass.github.io/) — indie game studio.

Served live at: <https://morass.github.io/>

## Layout
- `index.html` — studio landing page
- `style.css` — shared styling
- `<game>/` — one directory per game, each with its own `index.html` + `assets/`

## Editing
Direct push to `main` deploys automatically via GitHub Pages.

## Adding a new game
1. `mkdir <game-name> && touch <game-name>/index.html`
2. Drop assets in `<game-name>/assets/`
3. Add a `.game-card` entry to the root `index.html` games grid.
