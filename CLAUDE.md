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

> **Environnement de l'agent : ni Python ni Docker ne sont accessibles en local.** Ne pas tenter de lancer `pytest`, `python`, `docker` ou `docker compose` depuis le shell — ça échoue toujours. Les tests et l'app se lancent côté utilisateur (dans le conteneur). Vérifier la logique par lecture/raisonnement et laisser l'utilisateur exécuter `pytest tests/` / `docker compose up`.

## Inspecting live DB values

La CouchDB live tourne sur un hôte distant, généralement NON joignable en local. Pour connaître les valeurs réelles des documents (races, espèces, profils, lieux, items…), lire le dump JSON committé à la racine : `telluris-dump-YYYYMMDD-HHmmss.json` (le timestamp change ; produit par l'export admin `GET /admin/exports/couchdb` / `db.config.dump_all_docs()`). C'est un objet `{"db","exported_at","doc_count","docs":[...]}` ; `docs` exclut les `user:*`. Repérer un doc via grep sur `"_id": "rules:races"`, etc.

### Échelle des caractéristiques (×10, sauf V)
7 des 8 caractéristiques ont été passées ×10 (F/R/Ag/Vol/Int/Cha/Ch ≈ 10-100). **La Vitesse (V) est restée sur l'échelle 1-10** (base raciale ~4-5, max ~7-8). C'est pourquoi `deplacement = V` et `_compute_actions_max(ag, v) = ceil(ag/20 + v/5)` restent corrects. Les formules dérivées qui divisent une stat ×10 utilisent des diviseurs ×10 (`pa = R//20`, seuils de dés `_caract_to_dice_` à 20/40/60/80/90).

## Architecture

```
main.py                  # FastAPI app, page routes, static mounts
routers/
  user.py                # /api/* endpoints: auth, character CRUD, movement
utils/
  auth.py                # JWT creation + get_current_user() FastAPI dependency
  characters.py          # get_user_characters(), get_selected_character(), recompute_equipment_bonus()
  lieux.py               # lieu_router, movement logic, navigation bitmask
db/
  config.py              # CouchDB connection, get_doc / save_doc / find_docs helpers
models/
  character_stats.py     # BaseStats, DerivedStats, EquipmentBonus, compute_derived_stats()
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
