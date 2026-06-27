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

La CouchDB live tourne sur un hôte distant, généralement NON joignable en local. Pour connaître les valeurs réelles des documents (races, espèces, profils, lieux, items…), lire le dump JSON committé à la racine : `telluris-dump-YYYYMMDD-HHmmss.json` (le timestamp change ; produit par l'export admin `GET /admin/exports/couchdb` / `db.config.dump_all_docs()`). C'est un objet `{"db","exported_at","doc_count","docs":[...]}` ; `docs` exclut les `user:*`. Repérer un doc via grep sur `"_id": "rules:races"`, etc. Export ciblé d'un seul type : `GET /admin/exports/by-type?type=<type>` (`find_docs({"type": t})`, `user:*` exclus) → fichier `<type>-AAAAMMJJ-HHMMSS.json` ; la page `/admin/exports` propose une liste à saisie libre des types présents en base. **Édition en tableau** : la page `/admin/table` (`admin_table.html`, carte « Mise à jour en tableau » dans `/admin`) liste les docs d'un type choisi en tableau (colonnes choisies/ordonnées par drag, triables, filtrables, redimensionnables) ; cliquer une ligne ouvre le JSON dans un overlay fixe à droite, **Save** = `PUT /admin/doc` (réattache le `_rev` courant) / **Cancel** ferme. Données : `GET /admin/table/data?type=<t>` (`user:*` exclus). Les préférences d'affichage (colonnes/ordre/tri/filtres/largeurs) sont mémorisées **par type** dans `localStorage` (`telluris.admin_table.v1.<type>`).

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
Movement on grid maps uses an 8-direction bitmask (bit 1 = HAUT, 2 = HAUT_DROITE, 4 = DROITE, …, 128 = HAUT_GAUCHE). `get_lieu_directions()` in `utils/lieux.py` computes the allowed directions from a `nav` dict stored on the `lieu` document. `VALID_MOVES` (in `utils/lieux.py`) is the single source of truth for the 8 directions ; `MOVE_OFFSETS = [(dx,dy)…]` is derived from it. **Le pathfinding de combat partage cette source** : `_find_path` (A*, heuristique Chebyshev) et `_reachable_region` (flood fill du placement) dans `utils/combat.py` itèrent sur `MOVE_OFFSETS` et valident chaque pas avec `nav_allows` exactement comme le déplacement joueur — diagonales comprises, même règle des deux côtés (pas de contrôle géométrique anti corner-cutting ad hoc : le blocage de coin s'exprime via les masques `nav` de la carte). Ne jamais ré-introduire un jeu de directions à 4 cases : ça recrée des « îlots » inatteignables là où l'accès n'est que diagonal (ex. `lieu:chemin2`). **La grille passée à `_place_actors` doit aussi porter `nav`** : `create_combat_doc` construit `grid = {dims, cells, nav: battle_map.get("nav", {})}` — sans `nav`, `_reachable_region` (placement) voit le terrain entier connecté alors que `_find_path` (déplacement) respecte `nav`, et un monstre peut spawner dans une région nav-séparée du joueur (donc injoignable). Placement et déplacement doivent partager **et** le jeu de directions **et** les masques nav.

### Location links (CouchDB view)
Connections between locations are fetched via a CouchDB design view `reseau/liens_cases` keyed on `[lieu_id, x, y]`. This view must exist in CouchDB for navigation to work.

### Template CSS structure
`home_telluris.html` and `auth_telluris.html` use `{% include "part-*-css.html" %}` for shared styles. `play_town_telluris.html` has all CSS inlined directly and does not use the partials.

### Écran de combat — carte isométrique (`combat_telluris.html`)
La carte de combat utilise une **projection isométrique** (clip-path trapézoïdal généré par `buildViewportClipPath`, échelle `--step`, joueur fixe en bas-centre, monde qui pivote). **Tout le placement des tokens et la caméra en dépendent** : `renderTokens`/`updateCamera`/`worldToScreen`/`rot`/`dirAvailable`. Le handoff de design `Combat HTML file/design_handoff_combat/` propose un **sol en perspective** (`perspective()/rotateX()`) — **non adopté volontairement** (le faire = réécrire toute cette math). La passe visuelle « Refined Classic » (2026-06-25) n'a touché que la présentation : flou retiré au profit d'une **vignette** `::after` (clippée par la même forme iso), thème cuir/or via les tokens `:root`, pilule d'initiative au-dessus de la carte. Bord des tokens monstres laissé **rouge** car le **doré** signale l'adjacence (cible attaquable) — ne pas le passer en or par défaut.

**Portraits & anneau PV/PM des jetons (2026-06-27)** : les jetons d'initiative (`.init-badge`) et le `.player-token` affichent l'image du monstre (`/monsters/…`) / le portrait du perso (`/characters/…`). Le portrait **joueur** reproduit la portion cadrée dans play_town (champs `portrait_zoom` + `portrait_translate` du doc `character`) via `background-size`/`background-position` en **%** (relatifs au conteneur → vaut pour le badge 42px comme pour le token en `var(--step)`, sans recalcul au resize ; fenêtre de cadrage de référence **100×100**, offset pris en valeur absolue comme play_town). La route `get_combat_page` (`main.py`) passe `portrait_largeur/hauteur` (PIL). PV/PM = **deux demi-arcs SVG** en bordure du jeton circulaire (gauche PV rouge `#ib-pv`/`#pt-pv`, droite PM bleu `#ib-pm`/`#pt-pm` ; viewBox `0 0 42 42`, r=17, `stroke-dasharray` via `updatePlayerVitals`). **Gotcha Jinja** : `url_for(...)` renvoie un objet `URL` non sérialisable par `| tojson` → toujours `| string | tojson` quand on l'injecte dans du JS (en attribut `src="…"` la conversion est implicite).

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
Trois paliers **Or / Argent / Cuivre** (1 or = 100 argent = 10 000 cuivre, base = cuivre), stockés en entiers `or`/`argent`/`cuivre` sur le `character:*` (absents = 0 ; initialisés à la création). Toujours passer par les helpers : `money_to_cuivre(character)`, `cuivre_to_purse(total)→{or,argent,cuivre}`, `credit_character`/`debit_character(character, cuivre)` (mutent en place, **NE save pas** — l'endpoint persiste, comme `grant_xp` ; `debit_character` renvoie None si fonds insuffisants). **Éligibilité marchand** : un lieu de `categorie` marchande (ex. `"boucherie"`) achète les items dont la **sous-catégorie** ∈ `ACHAT_SOUS_CAT_PAR_LIEU[categorie]` (tunable monde). `item_sous_categorie(item)` = champ `sous_categorie` de l'item s'il est renseigné (ex. `"carcasse"` sur les dépouilles, taggé dans la donnée), **sinon repli sur la `categorie`** ; un `sous_categorie` vide (`""`) est ignoré. Les carcasses doivent porter `sous_categorie:"carcasse"` en base. **Fourchette de prix** (`prix_range_cuivre`) : champ item `valeur` à ≥2 bornes (`[{or,ag,cu},…]` → min/max), sinon `pmin = item_sale_price_cuivre` (poids × MULT_RARETE × PRIX_DERIVE_BASE) et `pmax = pmin × PRIX_MAX_FACTEUR`. **Prix offre/demande** (`prix_marche`, source unique du prix appliqué côté listes ET transactions) : `prix_courant` (relation+marchandage) **× `facteur_stock(stock, cible)`** puis re-clampé dans `[pmin, pmax]`. `facteur_stock` borné ±`PRIX_AMPLITUDE_STOCK`, **même sens des deux côtés** (stock élevé → moins cher à l'achat / moins bien payé à la vente). Stock pertinent : `qty` du produit en rayon (achat) ou `stock_matieres[sous_cat]` (vente). **Stock cible par lieu** résolu par `stock_cible_pour(lieu_doc, item)` : champ `stock_cible` du doc `lieu:*` `{item|sous_categorie|categorie → cible}`, priorité item > sous_cat > catégorie > world-var `STOCK_CIBLE_DEFAUT`. Endpoints : `GET /api/marchand/quotes` (vendables + achetables + bourse + relation), `POST /api/sell_item` et `POST /api/buy_item` (adressage par index vérifié item_id côté vente ; `save_doc` is None ⇒ 409 ; contrôle de charge à l'achat). Le template `/play` reçoit `lieu_categorie` + `achat_sous_categories` pour n'afficher le panneau **Actions → Vente/Achat** que chez un marchand. **Conversion** (`convertir_apres_achat`, `utils/marche.py`) : une vente à un lieu absorbe l'objet en `stock_matieres` ; carcasse dépecée par espèce (`depecage_carcasse`, tags → matières, hybride avec les quantités de recette). **Tick marché** : `tick_atelier(lieu_doc)` est lancé **à chaque vente ET à chaque visite du lieu** (`get_playground` dans `main.py`, gardé sur `stock_matieres` **ou** `stock_vente` non vide, save si changement) et enchaîne deux passes probabilistes : (1) **production** `tenter_production` (proba `ATELIER_TRANSFO_PROBA`, défaut 0.10) → `_executer_production_batch` **draine le stock** (recettes tirées au hasard **pondéré par `quantite_matiere`**, cap `_CONVERSION_CAP` ; matières non consommées par recette = produits finis boucherie viande/os **mis en rayon** ; matière sous le seuil conservée) ; (2) **écoulement PNJ** `ecouler_produits_pnj` (proba `VENTE_PNJ_PROBA`) → retire `round(excédent × VENTE_PNJ_FRACTION)` de chaque produit en rayon au-dessus de sa cible (plancher = cible : les PNJ n'achètent que le surplus). Puits de demande, pas de temps monde. **Conservation de la masse** : les quantités de dépeçage sont mises à l'échelle du poids de l'instance de carcasse (`× poids / DEPECAGE_POIDS_REF`, min 1 par sous-cat présente) — plus la carcasse est lourde, plus elle rend de matières ; il n'y a plus de bucket `petite_taille`/`geant` (le poids encode déjà la taille).

### Marchandage volontaire & relations (`utils/marche.py` + `routers/user.py`)
**`prix_courant(relation_doc, item_id, pmin, pmax, sens)`** = couche relation/marchandage : prix négocié persistant s'il existe, sinon **prix de base pondéré par la relation** (`prix_base_cuivre` : `frac = clamp(0.5 + (relation−50)·RELATION_SEUIL_COEFF/100, 0, 1)` — médian à relation 50, favorable au-dessus, défavorable en dessous). Le **prix réellement appliqué** est `prix_marche` (= `prix_courant` × `facteur_stock`, re-clampé `[pmin,pmax]` ; cf. *Monnaie & marché*) ; le marchandage agit donc sur la couche relation, l'offre/demande par-dessus. **Le prix négocié est persisté comme une FRACTION de la fourchette** (`prix_negocies[item_id][sens] = {"frac": t}`), pas un montant fixe : `prix_negocie` le rejoue `pmin + (pmax−pmin)·frac` contre la fourchette de **chaque instance** (qui dépend du poids) → deux exemplaires de même `item_id` mais de poids différents gardent des prix distincts après marchandage. Rétro-compat : un montant scalaire stocké (ancien format) est renvoyé tel quel. **`sell_item`/`buy_item` ne font PLUS de jet** ; ils gatent à relation ≤ 0 (403, transactions interdites). **Relation** = doc CouchDB **`type:"relation"`** par couple perso×lieu (`relation:<char_id>::<lieu_id>` ; `value` 0–100 neutre 50, `prix_negocies:{item_id:{vente,achat}}`, `marchandage_bloque_jusqu` epoch). Helpers `get_relation`/`relation_value`/`marchandage_bloque`/`appliquer_marchandage`/`now_epoch` (mutent sans save — l'endpoint persiste). **Marchander = action explicite** : `POST /api/marchander` (body `{item_id, index?, sens}`) → jet `marchander(...)` avec `seuil_bonus=(relation−50)·RELATION_SEUIL_COEFF` ; **réussite** persiste le prix dans `prix_negocies` (remplace, parfois pire — re-marchandage illimité mais risqué) ; **crit réussite** (roll ≤ `CRIT_REUSSITE_MAX`) → +1 relation ; **crit échec** (roll ≥ `CRIT_ECHEC_MIN`) → −1 relation **et** blocage du marchandage `MARCHANDAGE_BLOCAGE_SECONDES` (vente/achat au prix de base restent permis). `CRIT_*` sont des seuils de critique **génériques** (réutilisables par tout jet d100), pas spécifiques au marché. UI `play_town_telluris.html` : badge `#sell-relation`, prix courant + fourchette par ligne (champ `negocie`), bouton 🤝 Marchander (`marchanderItem`, désactivé pendant le blocage via horloge client `MARCHAND.blocDeadline`).

### Variables de monde réglables
Tunables de gameplay dans le doc CouchDB `rules:world_variables`, chargés au démarrage par `load_world_variables()` (`models/character_stats.py`). **Toujours lire via le module** (`character_stats.FACTEUR_DEGATS_ARMURE`, etc.), jamais `from … import CONST` (le chargeur réassigne les globales). Éditables à chaud via la page `/admin`. Variables marchandes : `PRIX_DERIVE_BASE`, `MULT_RARETE` (dict par rareté), `ACHAT_SOUS_CAT_PAR_LIEU` (dict catégorie-de-lieu → sous-catégories achetées), `CHA_MARCHAND`(`_PAR_CATEGORIE`), `PRIX_MAX_FACTEUR`, `DEPECAGE_TAGS`, `DEPECAGE_POIDS_REF` (poids de référence du dépeçage : quantités × poids/réf), `ATELIER_TRANSFO_PROBA` (proba d'une passe de production par vente/visite, défaut 0.10), `STOCK_CIBLE_DEFAUT` (repli de stock cible), `PRIX_AMPLITUDE_STOCK` (amplitude ± du prix offre/demande), `VENTE_PNJ_PROBA` + `VENTE_PNJ_FRACTION` (écoulement PNJ des produits finis). Marchandage/relation : `RELATION_INITIALE` (50), `RELATION_SEUIL_COEFF` (2), `MARCHANDAGE_BLOCAGE_SECONDES` (3600). Jets : `CRIT_REUSSITE_MAX` (5), `CRIT_ECHEC_MIN` (96) — **génériques**.
