# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Telluris is a browser-based medieval-fantasy RPG. The backend is a FastAPI server serving Jinja2 HTML templates; the database is CouchDB. There is no separate JS framework — all interactivity is vanilla JavaScript embedded in the templates.

## Running the app

```bash
docker compose up
```

FastAPI listens on `http://localhost:8000`. CouchDB listens on `http://localhost:5984`. The compose file installs Python dependencies at container start (no pre-built image).

## Running tests

```bash
pytest tests/
```

Tests only cover pure-Python stat computation (`models/character_stats.py`) and have no DB dependency.

## Architecture

```
main.py                  # FastAPI app, page routes, static mounts
routers/
  user.py                # /api/* endpoints: auth, character CRUD, movement
  stats.py               # /api/stats/* endpoints (defined but NOT mounted in main.py yet)
utils/
  auth.py                # JWT creation + get_current_user() FastAPI dependency
  characters.py          # get_user_characters(), get_selected_character()
  lieux.py               # lieu_router, movement logic, navigation bitmask
db/
  config.py              # CouchDB connection, get_doc / save_doc / find_docs helpers
models/
  character_stats.py     # BaseStats, DerivedStats, compute_derived_stats(), VOCATION_BONUS
  character_document.py  # Pydantic spec for a character document (reference only — see note below)
templates/
  *.html                 # Jinja2 pages
  part-*.html            # Shared CSS fragments included via {% include %}
  scripts/               # JS files (battle_map.js)
  resources/             # Static assets (characters, towns, maps, icons)
tests/
  test_character_stats.py
```

## Key design patterns

### CouchDB document IDs
Documents follow the pattern `type:identifier` — e.g. `user:email@example.com`, `lieu:lutecia`, `rules:races`, `rules:vocations`. Characters use `character:<user_id>_<uuid>`.

### Derived stats are never stored
`DerivedStats` (PV max, initiative, etc.) are always recalculated by `compute_derived_stats()` at request time. Never write derived values to the DB.

### Character document vs. Pydantic model
`models/character_document.py` is a reference spec. The actual documents created by `routers/user.py` use different field names: `voc` (not `vocation`), `sex` (not `sexe`), `caracteristiques_standard` / `caracteristiques_current` (not `base_stats`), `cite` for starting city. Always check the `routers/user.py` creation code as the ground truth for stored field names.

### Navigation bitmask
Movement on grid maps uses an 8-direction bitmask (bit 1 = HAUT, 2 = HAUT_DROITE, 4 = DROITE, …, 128 = HAUT_GAUCHE). `get_lieu_directions()` in `utils/lieux.py` computes the allowed directions from a `nav` dict stored on the `lieu` document.

### Location links (CouchDB view)
Connections between locations are fetched via a CouchDB design view `reseau/liens_cases` keyed on `[lieu_id, x, y]`. This view must exist in CouchDB for navigation to work.

### Template CSS structure
`home_telluris.html` and `auth_telluris.html` use `{% include "part-*-css.html" %}` for shared styles. `play_town_telluris.html` has all CSS inlined directly and does not use the partials.

### Authentication
`get_current_user()` reads an `auth_token` HTTP-only cookie, decodes the JWT, and returns the full user document from CouchDB (password field stripped). Routes that require auth declare `current_user: Annotated[User, Depends(get_current_user)]`. Admin-only routes additionally check `current_user["admin"] == 1`.

### Character image naming
Images under `templates/resources/characters/` follow `{vocation}_{sex}_{race}{num}.jpg` (e.g. `paladin_f_humain01.jpg`). Town images under `templates/resources/towns/` use `{lieu_name}_start_*.png` for the starting images listed in the emblem picker.
