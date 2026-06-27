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

La CouchDB live tourne sur un hôte distant, généralement NON joignable en local. Pour connaître les valeurs réelles des documents (races, espèces, profils, lieux, items…), lire le dump JSON committé à la racine : `telluris-dump-YYYYMMDD-HHmmss.json` (le timestamp change ; produit par l'export admin `GET /admin/exports/couchdb` / `db.config.dump_all_docs()`). C'est un objet `{"db","exported_at","doc_count","docs":[...]}` ; `docs` exclut les `user:*`. Repérer un doc via grep sur `"_id": "rules:races"`, etc. Export ciblé d'un seul type : `GET /admin/exports/by-type?type=<type>` (`find_docs({"type": t})`, `user:*` exclus) → fichier `<type>-AAAAMMJJ-HHMMSS.json` ; la page `/admin/exports` propose une liste à saisie libre des types présents en base.

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
Movement on grid maps uses an 8-direction bitmask (bit 1 = HAUT, 2 = HAUT_DROITE, 4 = DROITE, …, 128 = HAUT_GAUCHE). `get_lieu_directions()` in `utils/lieux.py` computes the allowed directions from a `nav` dict stored on the `lieu` document. `VALID_MOVES` (in `utils/lieux.py`) is the single source of truth for the 8 directions ; `MOVE_OFFSETS = [(dx,dy)…]` is derived from it. **Le pathfinding de combat partage cette source** : `_find_path` (A*, heuristique Chebyshev) et `_reachable_region` (flood fill du placement) dans `utils/combat.py` itèrent sur `MOVE_OFFSETS` et valident chaque pas avec `nav_allows` exactement comme le déplacement joueur — diagonales comprises, même règle des deux côtés (pas de contrôle géométrique anti corner-cutting ad hoc : le blocage de coin s'exprime via les masques `nav` de la carte). Ne jamais ré-introduire un jeu de directions à 4 cases : ça recrée des « îlots » inatteignables là où l'accès n'est que diagonal (ex. `lieu:chemin2`).

### Location links (CouchDB view)
Connections between locations are fetched via a CouchDB design view `reseau/liens_cases` keyed on `[lieu_id, x, y]`. This view must exist in CouchDB for navigation to work.

### Template CSS structure
`home_telluris.html` and `auth_telluris.html` use `{% include "part-*-css.html" %}` for shared styles. `play_town_telluris.html` has all CSS inlined directly and does not use the partials.

### Écran de combat — carte isométrique (`combat_telluris.html`)
La carte de combat utilise une **projection isométrique** (clip-path trapézoïdal généré par `buildViewportClipPath`, échelle `--step`, joueur fixe en bas-centre, monde qui pivote). **Tout le placement des tokens et la caméra en dépendent** : `renderTokens`/`updateCamera`/`worldToScreen`/`rot`/`dirAvailable`. Le handoff de design `Combat HTML file/design_handoff_combat/` propose un **sol en perspective** (`perspective()/rotateX()`) — **non adopté volontairement** (le faire = réécrire toute cette math). La passe visuelle « Refined Classic » (2026-06-25) n'a touché que la présentation : flou retiré au profit d'une **vignette** `::after` (clippée par la même forme iso), thème cuir/or via les tokens `:root`, pilule d'initiative au-dessus de la carte. Bord des tokens monstres laissé **rouge** car le **doré** signale l'adjacence (cible attaquable) — ne pas le passer en or par défaut.

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

### Monnaie & marché (`utils/characters.py` + `utils/marche.py` + `routers/user.py`)
Trois paliers **Or / Argent / Cuivre** (1 or = 100 argent = 10 000 cuivre, base = cuivre), stockés en entiers `or`/`argent`/`cuivre` sur le `character:*` (absents = 0 ; initialisés à la création). Toujours passer par les helpers : `money_to_cuivre(character)`, `cuivre_to_purse(total)→{or,argent,cuivre}`, `credit_character`/`debit_character(character, cuivre)` (mutent en place, **NE save pas** — l'endpoint persiste, comme `grant_xp` ; `debit_character` renvoie None si fonds insuffisants). **Éligibilité marchand** : un lieu de `categorie` marchande (ex. `"boucherie"`) achète les items dont la **sous-catégorie** ∈ `ACHAT_SOUS_CAT_PAR_LIEU[categorie]` (tunable monde). `item_sous_categorie(item)` = champ `sous_categorie` de l'item s'il est renseigné (ex. `"carcasse"` sur les dépouilles, taggé dans la donnée), **sinon repli sur la `categorie`** ; un `sous_categorie` vide (`""`) est ignoré. Les carcasses doivent porter `sous_categorie:"carcasse"` en base. **Fourchette de prix** (`prix_range_cuivre`) : champ item `valeur` à ≥2 bornes (`[{or,ag,cu},…]` → min/max), sinon `pmin = item_sale_price_cuivre` (poids × MULT_RARETE × PRIX_DERIVE_BASE) et `pmax = pmin × PRIX_MAX_FACTEUR`. Endpoints : `GET /api/marchand/quotes` (vendables + achetables + bourse + relation), `POST /api/sell_item` et `POST /api/buy_item` (adressage par index vérifié item_id côté vente ; `save_doc` is None ⇒ 409 ; contrôle de charge à l'achat). Le template `/play` reçoit `lieu_categorie` + `achat_sous_categories` pour n'afficher le panneau **Actions → Vente/Achat** que chez un marchand. **Conversion** (`convertir_apres_achat`, `utils/marche.py`) : une vente à un lieu absorbe l'objet en `stock_matieres`, cuit les `recette:*` du lieu pour remplir `stock_vente` (revendable), et revend brute toute matière non transformable ; carcasse dépecée par espèce (`depecage_carcasse`, tags → matières, hybride avec les quantités de recette).

### Marchandage volontaire & relations (`utils/marche.py` + `routers/user.py`)
Le prix appliqué est **`prix_courant(relation_doc, item_id, pmin, pmax, sens)`** : prix négocié persistant s'il existe, sinon **prix de base pondéré par la relation** (`prix_base_cuivre` : `frac = clamp(0.5 + (relation−50)·RELATION_SEUIL_COEFF/100, 0, 1)` — médian à relation 50, favorable au-dessus, défavorable en dessous). **Le prix négocié est persisté comme une FRACTION de la fourchette** (`prix_negocies[item_id][sens] = {"frac": t}`), pas un montant fixe : `prix_negocie` le rejoue `pmin + (pmax−pmin)·frac` contre la fourchette de **chaque instance** (qui dépend du poids) → deux exemplaires de même `item_id` mais de poids différents gardent des prix distincts après marchandage. Rétro-compat : un montant scalaire stocké (ancien format) est renvoyé tel quel. **`sell_item`/`buy_item` ne font PLUS de jet** ; ils gatent à relation ≤ 0 (403, transactions interdites). **Relation** = doc CouchDB **`type:"relation"`** par couple perso×lieu (`relation:<char_id>::<lieu_id>` ; `value` 0–100 neutre 50, `prix_negocies:{item_id:{vente,achat}}`, `marchandage_bloque_jusqu` epoch). Helpers `get_relation`/`relation_value`/`marchandage_bloque`/`appliquer_marchandage`/`now_epoch` (mutent sans save — l'endpoint persiste). **Marchander = action explicite** : `POST /api/marchander` (body `{item_id, index?, sens}`) → jet `marchander(...)` avec `seuil_bonus=(relation−50)·RELATION_SEUIL_COEFF` ; **réussite** persiste le prix dans `prix_negocies` (remplace, parfois pire — re-marchandage illimité mais risqué) ; **crit réussite** (roll ≤ `CRIT_REUSSITE_MAX`) → +1 relation ; **crit échec** (roll ≥ `CRIT_ECHEC_MIN`) → −1 relation **et** blocage du marchandage `MARCHANDAGE_BLOCAGE_SECONDES` (vente/achat au prix de base restent permis). `CRIT_*` sont des seuils de critique **génériques** (réutilisables par tout jet d100), pas spécifiques au marché. UI `play_town_telluris.html` : badge `#sell-relation`, prix courant + fourchette par ligne (champ `negocie`), bouton 🤝 Marchander (`marchanderItem`, désactivé pendant le blocage via horloge client `MARCHAND.blocDeadline`).

### Variables de monde réglables
Tunables de gameplay dans le doc CouchDB `rules:world_variables`, chargés au démarrage par `load_world_variables()` (`models/character_stats.py`). **Toujours lire via le module** (`character_stats.FACTEUR_DEGATS_ARMURE`, etc.), jamais `from … import CONST` (le chargeur réassigne les globales). Éditables à chaud via la page `/admin`. Variables marchandes : `PRIX_DERIVE_BASE`, `MULT_RARETE` (dict par rareté), `ACHAT_SOUS_CAT_PAR_LIEU` (dict catégorie-de-lieu → sous-catégories achetées), `CHA_MARCHAND`(`_PAR_CATEGORIE`), `PRIX_MAX_FACTEUR`, `DEPECAGE_TAGS`. Marchandage/relation : `RELATION_INITIALE` (50), `RELATION_SEUIL_COEFF` (2), `MARCHANDAGE_BLOCAGE_SECONDES` (3600). Jets : `CRIT_REUSSITE_MAX` (5), `CRIT_ECHEC_MIN` (96) — **génériques**.
