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
main.py                  # FastAPI app, page routes (/play, /combat/{id}, /admin*), static mounts
routers/
  user.py                # /api/* : auth, character CRUD, movement, equip/unequip, drop/pickup, spend_xp
  combat.py              # /api/combat/* : start, get, action, collect (loot)
  zones.py               # /api/* : zones d'influence + tables de rencontres par lieu
  bestiaire.py           # /admin/* : CRUD espece:* / profil:* (+ éditeur)
utils/
  auth.py                # JWT creation + get_current_user() FastAPI dependency
  characters.py          # get/selected character, recompute_equipment_bonus, grant_xp,
                         #   carried_weight, charge_max_of, références d'items (item_ref_*)
  lieux.py               # lieu_router, movement logic, navigation bitmask
  combat.py              # logique de combat pure (snapshots, A*, résolution, loot, finalize)
  zones.py               # géométrie des zones d'influence + tirage d'événements
db/
  config.py              # CouchDB connection, get_doc / save_doc / find_docs helpers
models/
  character_stats.py     # BaseStats, DerivedStats, EquipmentBonus, compute_derived_stats()
  character_document.py  # Pydantic spec for a character document (reference only — see note below)
templates/
  *.html                 # Jinja2 pages (play_town, combat, fiche perso, admin, éditeurs)
  part-*.html            # Shared CSS fragments included via {% include %}
  scripts/               # JS files (battle_map.js, nav.js — bitmask nav partagé)
  resources/             # Static assets (characters, towns, maps, monsters, icons)
dev/
  export_bestiaire.py    # writer xlsx pur stdlib (export d'équilibrage)
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

### Références d'items & poids (`utils/characters.py`)
Une entrée d'`inventaire` / `objets_au_sol` / `slots` / `butin_ramasse` est **soit** une chaîne `"item:xxx"` (legacy → poids = **min** de l'item) **soit** un objet **`{"item": "item:xxx", "poids": <nb>}`** portant le poids propre à l'instance. Le champ `poids` d'un doc `item:*` peut être un **nombre fixe** OU un tableau **`[min, max]`**. Toujours passer par les helpers : `item_ref_id(ref)`, `poids_bounds(item)→(min,max)`, `item_ref_weight(ref)`, `resolve_item_ref(ref)` (renvoie le doc avec `poids` écrasé par le poids effectif scalaire + champ `item`). Ne jamais supposer qu'une entrée est une simple chaîne. Les actions client (poser/prendre) adressent par **index vérifié par `item_id`** (deux exemplaires d'un même item peuvent peser différemment).

### Charge & surcharge
`charge_max_of(character)` = `F*5` (dérivée, jamais stockée). `carried_weight(character)` somme les poids effectifs de l'inventaire **+ équipés** (pas le sol). En **exploration**, si `carried_weight > charge_max` le déplacement est bloqué (garde 409 dans `move_character`, flèches désactivées côté client) ; au pickup, le dépassement fait tomber des items **aléatoires** au sol. En **combat**, au-delà de la **demi-charge** le déplacement est divisé par deux (`utils/combat.py`). Les objets au sol (`objets_au_sol`) sont **transitoires** : vidés dès un déplacement réel.

### Combat & butin (`utils/combat.py` + `routers/combat.py`)
Un combat est un doc `combat:*` (snapshots `joueurs[]`/`monstres[]`, `ordre_initiative`, `battle_map_id`). Les **stats dérivées des monstres** viennent de `espece:*` (min/max) modulées par `profil:*` (niveau, deltas). `finalize_combat()` applique XP/PV **et** le butin ramassé en combat, de façon **idempotente atomique** (id du combat dans `character["combats_recompenses"]`, même doc que l'XP). Le butin de victoire n'est **jamais** auto-ajouté : `butin_disponible` (poids tiré au niveau du profil via `random.choices`) est proposé dans l'overlay, encaissé par `POST /api/combat/{id}/collect` (borné par `charge_max`). Carcasses = `item:<sub_id>` (1-pour-1 avec `espece:<sub_id>`), créées à la volée si absentes.

### Monnaie & vente marchande (`utils/characters.py` + `routers/user.py`)
Trois paliers **Or / Argent / Cuivre** (1 or = 100 argent = 10 000 cuivre, base = cuivre), stockés en entiers `or`/`argent`/`cuivre` sur le `character:*` (absents = 0 ; initialisés à la création). Toujours passer par les helpers : `money_to_cuivre(character)`, `cuivre_to_purse(total)→{or,argent,cuivre}`, `credit_character(character, cuivre)` (mute en place, **NE save pas** — l'endpoint persiste, comme `grant_xp`). **Éligibilité marchand** : un lieu de `categorie` marchande (ex. `"boucherie"`) achète les items dont la **sous-catégorie** ∈ `ACHAT_SOUS_CAT_PAR_LIEU[categorie]` (tunable monde). `item_sous_categorie(item)` = `sous_categorie` explicite, sinon `"carcasse"` si `source_espece`/`categorie=="composant"`. **Prix** (`item_sale_price_cuivre`) : champ item `valeur` (`[{or,ag,cu},…]` → on propose le **min**, place pour un marchandage futur vers le max), sinon prix dérivé `max(1, poids × MULT_RARETE[rarete] × PRIX_DERIVE_BASE)`. Endpoints `GET /api/marchand/quotes` (liste vendable + bourse) et `POST /api/sell_item` (body `{index, item_id}`, calqué sur `drop_item` : `_take_ref` par index vérifié item_id → `credit_character` → `save_doc` is None ⇒ 409). Le template `/play` reçoit `lieu_categorie` + `achat_sous_categories` pour n'afficher le panneau **Actions → Vente** que chez un marchand. **Ce maillon ne fait que la vente** (pas d'achat ni de marchandage ni de transformation — cf. roadmap §1.3 / §3.3).

### Variables de monde réglables
Tunables de gameplay dans le doc CouchDB `rules:world_variables`, chargés au démarrage par `load_world_variables()` (`models/character_stats.py`). **Toujours lire via le module** (`character_stats.FACTEUR_DEGATS_ARMURE`, etc.), jamais `from … import CONST` (le chargeur réassigne les globales). Éditables à chaud via la page `/admin`. Variables marchandes : `PRIX_DERIVE_BASE`, `MULT_RARETE` (dict par rareté), `ACHAT_SOUS_CAT_PAR_LIEU` (dict catégorie-de-lieu → sous-catégories achetées).
