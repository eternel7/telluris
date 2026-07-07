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

Tests only cover pure-Python logic (stats, combat à distance, marché/recettes, consommables, sorts) and have no DB dependency.

> **Environnement de l'agent : Python EST disponible en local (2026-07-03)** — lancer `pytest tests/` directement depuis le shell pour valider la logique pure (Python 3.12, pytest installé). CouchDB reste injoignable en local : `db/config.py` tolère l'absence de connexion à l'import (`server`/`db` = `None`, les helpers renvoient `None`) pour que les tests purs se collectent. Docker/l'app tournent côté utilisateur (`docker compose up` dans le conteneur).

## Inspecting live DB values

La CouchDB live tourne sur un hôte distant, généralement NON joignable en local. Pour connaître les valeurs réelles des documents (races, espèces, profils, lieux, items…), lire le dump JSON committé à la racine : `telluris-dump-YYYYMMDD-HHmmss.json` (le timestamp change ; produit par l'export admin `GET /admin/exports/couchdb` / `db.config.dump_all_docs()`). C'est un objet `{"db","exported_at","doc_count","docs":[...]}` ; `docs` exclut les `user:*`. Repérer un doc via grep sur `"_id": "rules:races"`, etc. Export ciblé d'un seul type : `GET /admin/exports/by-type?type=<type>` (`find_docs({"type": t})`, `user:*` exclus) → fichier `<type>-AAAAMMJJ-HHMMSS.json` ; la page `/admin/exports` propose une liste à saisie libre des types présents en base. **Édition en tableau** : la page `/admin/table` (`admin_table.html`, carte « Mise à jour en tableau » dans `/admin`) liste les docs d'un type choisi en tableau (colonnes choisies/ordonnées par drag, triables, filtrables, redimensionnables) ; cliquer une ligne ouvre le JSON dans un overlay fixe à droite, **Save** = `PUT /admin/doc` (réattache le `_rev` courant) / **Cancel** ferme. Données : `GET /admin/table/data?type=<t>` (`user:*` exclus). Les préférences d'affichage (colonnes/ordre/tri/filtres/largeurs) sont mémorisées **par type** dans `localStorage` (`telluris.admin_table.v1.<type>`). **Export** : deux boutons au-dessus du tableau exportent les lignes **actuellement affichées** (filtres+tri, `computeVisibleRows`) — **⬇ Export JSON** (docs complets, tableau JSON) et **⬇ Export Excel** (`POST /admin/table/export.xlsx` → writer OOXML partagé `utils/xlsx.py`, une colonne par clé de 1er niveau, valeurs imbriquées en JSON). Nom de fichier commun `exportFilename(ext)` = `<type>_filtre_<col>_<val>…_AAAAMMJJHHMMSS.(json|xlsx)`.

### Échelle des caractéristiques (×10, sauf V)
7 caractéristiques à l'échelle ×10 (F/R/Ag/Vol/Int/Cha/Ch ≈ 10-100). V = 1-10 (base raciale ~4-5, max ~7-8), `deplacement = V` cases/tour. Formules (joueur + monstres) : `cc = (F + Ag*3)//4`, `cd = (Ag*3 + V*10)//4`, `initiative = (Ag + V*20)//3`, `actions_max = max(1, ceil(Ag/40 + V/2))` → **Ag est la god-stat**.

### Références d'items & poids
Entrée d'inventaire = **string legacy** `"item:xxx"` (poids = min) **ou object** `{"item": "item:xxx", "poids": <nb>}`. Doc `item:*` `poids` = nombre OU `[min,max]`. Helpers : `item_ref_id`, `poids_bounds`, `item_ref_weight`, `resolve_item_ref`. Actions client adressent par **index+item_id** (instances d'un même item peuvent peser différemment).

### Charge & surcharge
`charge_max_of(character)` = `F*5`. `carried_weight(character)` = inventaire + équipés. Exploration : déplacement bloqué si surcharge, au pickup items tombent au sol. Combat : demi-charge = déplacement ÷2. Sol (`objets_au_sol`) = transitoire, vidé à chaque déplacement.

### Combat & butin
Doc `combat:*` = snapshots `joueurs[]`/`monstres[]`, `ordre_initiative`, `battle_map_id`. Stats monstres = `espece:*` (min/max) modulées `profil:*` (niveau, deltas). `finalize_combat()` : XP/PV + butin (idempotent atomique). Butin victoire = pas auto-ajouté, proposé overlay, encaissé `POST /api/combat/{id}/collect`. Carcasses = `item:<sub_id>`.

### Attaques par mode — corps à corps / jet / tir
Mode via tag : `tir` (arcs), `jet` (lancer), sinon **cac** (hast = cac `portee ≥ 2`). Champs item : `portee` (défaut 1), `restriction:{caract:min}` (ET). `restriction_satisfaite` → blocage dur `equip_item` (422). `_weapon_attacks` = `joueur["attaque_profils"]` (1 par mode, meilleure portée, poings portée 1 toujours présent). Chaque profil : `mode`, `portee`, `ranged`, `toucher` (cc/cd), `degats` (cc/cd). **cac** = cc/F, portée item ; **jet** = cd/F, portée `item + F//JET_PORTEE_F_DIV` ; **tir** = cd/Ag, portée item. `resolve_action` sélectionne profil. **Règles ranged** : interdit si engagé (1 case), exige ligne de vue (Bresenham `seeThroughCell` — falaise transparente, mur seul bloque —, `nav` ignoré). UI (refonte 2026-07-07) : **plus de sélecteur de mode** ; **3 boutons d'attaque directs** `.atk-mode-btn` (⚔ Mêlée `cac` / 🪃 Jet / 🏹 Tir) dans la barre d'action, chacun **visible seulement si le mode est équipé** (`updateAttackButtons`) et **actif seulement s'il a une cible attaquable** (`updateButtons` : `targetableMonsters(mode)`) → tous les modes possibles dispo simultanément. `triggerAttack(mode)` fixe `currentMode` puis attaque directe (1 cible) ou ouvre le sélecteur de cible (masque les boutons via `.hidden-selecting`). `currentMode` pilote la visibilité des cibles ; les **badges du bandeau d'initiative** (`.init-badge.monstre`) servent aussi de ciblage — bordure grise hors portée, **rouge + cliquables** (attaque, `refreshBadgeTargets`) uniquement quand attaquables (tour + action + portée), miroir du clic sur `.monster-token.adjacent`. Monstres = mêlée seule. Tests purs `tests/test_combat_ranged.py`.

**UI panneaux combat** (`combat_telluris.html`, refonte 2026-07-04) : panneau perso = reprise du `<section class="character-panel">` de play_town — portrait recadré du joueur (`#left-portrait.pt-crop` via `applyPlayerPortrait`, carré, barres PV/PM verticales), identité, pips d'actions + jauge de charge (pas de mini-stats). Vie des ennemis = **anneaux PV** sur les badges du header (`setRing`/`MONSTER_CIRC`) + grand portrait du dernier ciblé (plus de liste d'ennemis). Carte iso : `MAX_H`=10 rangées, `--step` borné à la **seule largeur** (`max(8, w/17)`) → hauteur agrandie sans toucher la largeur, page défilable.

## Gameplay Systems

```
main.py                  # FastAPI app, page routes (/play, /combat/{id}, /admin*), static mounts
routers/
  user.py                # /api/* : auth, character CRUD, movement, equip/unequip, drop/pickup, spend_xp
  combat.py              # /api/combat/* : start, get, action, collect (loot)
  zones.py               # /api/* : zones d'influence + tables de rencontres/ressources par lieu + GET /api/items
  bestiaire.py           # /admin/* : CRUD espece:* / profil:* (+ éditeur)
  quetes.py              # /api/quetes/* : board, accepter, terminer, abandonner (guilde)
  pnj.py                 # /api/pnj/dialogue (+ /choix) : dialogues PNJ + service soin ; /api/intro/raison
utils/
  auth.py                # JWT creation + get_current_user() FastAPI dependency
  characters.py          # get/selected character, recompute_equipment_bonus, grant_xp,
                         #   carried_weight, charge_max_of, références d'items (item_ref_*)
  lieux.py               # lieu_router, movement logic, navigation bitmask
  combat.py              # logique de combat pure (snapshots, A*, résolution, loot, finalize)
  zones.py               # géométrie des zones d'influence + tirage d'événements
  quetes.py              # moteur de génération de quêtes (pur) + état joueur / progression / récompenses
  bois.py                # découpe du bois (pur) : tier suivant par essence, conservation du poids, outil
  pnj.py                 # PNJ de lieu (pur) : tirage de présence, arbre de dialogue, service de soin
  intro.py               # intro narrative (pur) : démarrage, overlay, raisons, conclusion en zone sûre
  xlsx.py                # writer xlsx OOXML pur stdlib (zipfile) — partagé bestiaire + export tableau admin
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
  export_bestiaire.py    # export d'équilibrage (feuille bestiaire ; writer OOXML → utils/xlsx.py)
tests/
  test_character_stats.py
```

## Core Design Patterns

### CouchDB document IDs
Pattern `type:identifier` — e.g. `user:email@example.com`, `lieu:lutecia`, `rules:races`. Characters = `character:<user_id>_<uuid>`.

### Derived stats are never stored
`DerivedStats` recalculated by `compute_derived_stats()` at request time. Never persist derived values.

### Character document vs. Pydantic model
`models/character_document.py` = reference spec. Ground truth = `routers/user.py` creation code. Field names differ: `voc`, `sex`, `caracteristiques_standard`/`current`, `cite`.

## Core Mechanics

### Échelle des caractéristiques (×10, sauf V)
7 caractéristiques à l'échelle ×10 (F/R/Ag/Vol/Int/Cha/Ch ≈ 10-100). V = 1-10 (base raciale ~4-5, max ~7-8), `deplacement = V` cases/tour. Formules (joueur + monstres) : `cc = (F + Ag*3)//4`, `cd = (Ag*3 + V*10)//4`, `initiative = (Ag + V*20)//3`, `actions_max = max(1, ceil(Ag/40 + V/2))` → **Ag est la god-stat**.

### Navigation bitmask
8-direction via `nav` dict (bit 1=HAUT, 2=HAUT_DROITE, …, 128=HAUT_GAUCHE). `VALID_MOVES` (source unique, `utils/lieux.py`) → `MOVE_OFFSETS`. **Combat partage** : `_find_path` (A*) et `_reachable_region` (flood fill) utilisent mêmes directions + `nav_allows`. ⚠️ **Pas 4 directions** (îlots diagonaux). `create_combat_doc` : `grid = {dims, cells, nav}` — sans `nav`, placement ≠ déplacement. Même jeu + même masques.

### Références d'items & poids
Entrée d'inventaire = **string legacy** `"item:xxx"` (poids = min) **ou object** `{"item": "item:xxx", "poids": <nb>}`. Doc `item:*` `poids` = nombre OU `[min,max]`. Helpers : `item_ref_id`, `poids_bounds`, `item_ref_weight`, `resolve_item_ref`. Actions client adressent par **index+item_id** (instances d'un même item peuvent peser différemment).

### Charge & surcharge
`charge_max_of(character)` = `F*5` (dérivée, jamais stockée). `carried_weight(character)` somme les poids effectifs de l'inventaire **+ équipés** (pas le sol). En **exploration**, si `carried_weight > charge_max` le déplacement est bloqué (garde 409 dans `move_character`, flèches désactivées côté client) ; au pickup, le dépassement fait tomber des items **aléatoires** au sol. En **combat**, au-delà de la **demi-charge** le déplacement est divisé par deux (`utils/combat.py`). Les objets au sol (`objets_au_sol`) sont **transitoires** : vidés dès un déplacement réel.

### Combat & butin (`utils/combat.py` + `routers/combat.py`)
Un combat est un doc `combat:*` (snapshots `joueurs[]`/`monstres[]`, `ordre_initiative`, `battle_map_id`). Les **stats dérivées des monstres** viennent de `espece:*` (min/max) modulées par `profil:*` (niveau, deltas). `finalize_combat()` applique XP/PV **et** le butin ramassé en combat, de façon **idempotente atomique** (id du combat dans `character["combats_recompenses"]`, même doc que l'XP). Le butin de victoire n'est **jamais** auto-ajouté : `butin_disponible` (poids tiré au niveau du profil via `random.choices`) est proposé dans l'overlay, encaissé par `POST /api/combat/{id}/collect` (borné par `charge_max`). Carcasses = `item:<sub_id>` (1-pour-1 avec `espece:<sub_id>`), créées à la volée si absentes.

### Attaques par mode — corps à corps / jet / tir
Mode via tag : `tir` (arcs), `jet` (lancer), sinon **cac** (hast = cac `portee ≥ 2`). Champs item : `portee` (défaut 1), `restriction:{caract:min}` (ET). `restriction_satisfaite` → blocage dur `equip_item` (422). `_weapon_attacks` = `joueur["attaque_profils"]` (1 par mode, meilleure portée, poings portée 1 toujours présent). Chaque profil : `mode`, `portee`, `ranged`, `toucher` (cc/cd), `degats` (cc/cd). **cac** = cc/F, portée item ; **jet** = cd/F, portée `item + F//JET_PORTEE_F_DIV` ; **tir** = cd/Ag, portée item. `resolve_action` sélectionne profil. **Règles ranged** : interdit si engagé (1 case), exige ligne de vue (Bresenham `seeThroughCell` — falaise transparente, mur seul bloque —, `nav` ignoré). UI (refonte 2026-07-07) : **plus de sélecteur de mode** ; **3 boutons d'attaque directs** `.atk-mode-btn` (⚔ Mêlée `cac` / 🪃 Jet / 🏹 Tir) dans la barre d'action, chacun **visible seulement si le mode est équipé** (`updateAttackButtons`) et **actif seulement s'il a une cible attaquable** (`updateButtons` : `targetableMonsters(mode)`) → tous les modes possibles dispo simultanément. `triggerAttack(mode)` fixe `currentMode` puis attaque directe (1 cible) ou ouvre le sélecteur de cible (masque les boutons via `.hidden-selecting`). `currentMode` pilote la visibilité des cibles ; les **badges du bandeau d'initiative** (`.init-badge.monstre`) servent aussi de ciblage — bordure grise hors portée, **rouge + cliquables** (attaque, `refreshBadgeTargets`) uniquement quand attaquables (tour + action + portée), miroir du clic sur `.monster-token.adjacent`. Monstres = mêlée seule. Tests purs `tests/test_combat_ranged.py`.

**UI panneaux combat** (`combat_telluris.html`, refonte 2026-07-04) : panneau perso = reprise du `<section class="character-panel">` de play_town — portrait recadré du joueur (`#left-portrait.pt-crop` via `applyPlayerPortrait`, carré, barres PV/PM verticales), identité, pips d'actions + jauge de charge (pas de mini-stats). Vie des ennemis = **anneaux PV** sur les badges du header (`setRing`/`MONSTER_CIRC`) + grand portrait du dernier ciblé (plus de liste d'ennemis). Carte iso : `MAX_H`=10 rangées, `--step` borné à la **seule largeur** (`max(8, w/17)`) → hauteur agrandie sans toucher la largeur, page défilable.

### Monnaie & marché
3 paliers : Or/Argent/Cuivre (1 or = 100 ag = 10k cu). Helpers : `money_to_cuivre`, `cuivre_to_purse`, `credit_character`/`debit_character` (mutent, **sans save**). **Éligibilité marchand** : `lieu_buys(lieu, item)` = item sous-cat ∈ recettes du lieu OU produit du lieu (rachat ≤ pmin ≤ achat). `params_vente_lieu` = source unique prix. **Coût revient** : doc `valeur` explicite → autoritaire ; sinon récursif via recettes (transformations = bien plus cher). Feuilles (matières brutes) = `poids × MULT_RARETE × PRIX_DERIVE_BASE`. **Prix marché** = `prix_courant × facteur_stock`, re-clampé `[pmin,pmax]`. Stock target = `stock_cible_pour(lieu, item)` (item > sous-cat > catégorie > défaut). **Tick atelier** (vente/achat/visite) : (0) appro feuilles, (1) production (multi-matières, tirage pondéré), (2) écoulement PNJ. **Dépeçage** : poids instance × poids/REF (plus lourd = plus de matière).

### Marchandage & relations
`prix_courant` = prix négocié OU base pondéré relation (0-100 neutre 50, `frac = 0.5 + (val−50)·coeff/100`). **Prix appliqué** = `prix_marche` (courant × facteur_stock, re-clampé). Négociation persistée **FRACTION** de fourchette (pas montant fixe) → poids différent = prix différent. **Relation** = doc CouchDB `type:"relation"` (char×lieu, 0-100, `prix_negocies`, blocage epoch). `POST /api/marchander` : jet bonus=`(rel−50)·coeff` ; **réussite** = prix persisté ; **crit ok** = +1 rel ; **crit fail** = −1 rel + blocage. `CRIT_*` = génériques. UI : badge relation, bouton 🤝, toast affiche `prix_marche` exact (pas `prix_negocie` sans facteur_stock).

### Onglet 🤝 Relations
Panneau `#sh-relations` : 🏪 **Lieux connus** + 👥 Personnages. **`relations_lieux_payload(character)`** (source unique, `utils/marche.py`) = **tous les lieux CONNUS** = `lieux_visites` ∪ lieux ayant un doc `relation` (refonte 2026-07-07 : plus seulement ceux avec relation) → liste **à plat**, chaque entrée `{lieu_id, nom, categorie, est_ville, image, image_route, value, bloque, lieu_parent, parent_nom, parent_image…}` ; lieu sans relation = valeur neutre `RELATION_INITIALE`, trié value décroissant. **Rendu 100 % client** (`renderFicheRelations`, plus de boucle Jinja) : payload injecté `RELATIONS_LIEUX_INIT` à l'init + resync après marchandage. **Groupé par ville** (`lieu_parent` → lieu `categorie:"ville"`, sinon groupe « Autres lieux ») en **accordéon** (`toggleVilleGroup` : une ville ouverte à la fois, mémorisée par perso dans `localStorage` `telluris.play.rel_ville_open.<char_id>`, en-tête = score de la ville + compteur). **Filtre** `#sh-rel-filter` (nom de lieu OU catégorie, `applyRelFilter` auto-déplie les groupes correspondants). **Portrait** : cliquer une ligne plie/déplie son image (accordéon d'images, une ouverte à la fois), l'image **zoome au survol** (`scale(2)`, overflow recadré) ; zone `.sh-rel-scroll` scrollbar fine + ombre de fond. Échelle **0-100 neutre 50** : Banni(0) / Hostile(<35) / Méfiant(<50) / Neutre(50) / Cordial(<70) / Estimé(<90) / Honoré(≥90). Badge 🚫 si `marchandage_bloque`, bouton 🧭 focalisation par ligne. Affinité PNJ = même échelle (Phase 4.2 = inerte).

### Quêtes — guilde + moteur
**Lieu guilde** : `categorie:"guilde_aventurier"` + `lieu_parent` (ex. `auxerre`). Extérieur intermédiaire (`guilde_aventurier_exterieur`) inerte. Tableau généré = espèces rencontres → quêtes `kill` ; `ressources` lieu + carcasses → quêtes `collect`. Docs `quete:*` = générées (`source:"genere"`, max `QUETE_BOARD_TAILLE`) + authorées (`source:"authoree"`, affichées côté). **État joueur** : `quetes_actives[]` (snapshot + `progress`), `quetes_terminees[]`. **Hooks progression** : `kill` en combat (exactly-once), `visite` en déplacement, `collect` en dépôt guilde. **Dépôt progressif** : `POST /api/quetes/deposer` retire pièces portées, incrémente `progress` (plusieurs voyages OK). **Pas d'arbre entier** : `cibles_collect` découpe si `> QUETE_COLLECT_POIDS_MAX`. UI : bouton 📜, panneau AJAX, onglet fiche resync client `renderFicheQuetes`. CSS factorisé `.panel-frame`/`.board-panel`. Mode Ressources éditeur → `PUT /api/lieu/{id}/ressources`. World-vars : `QUETE_BOARD_TAILLE`, `QTE_MIN/MAX`, `XP_FACTEUR`, `CUIVRE_PAR_XP`.

### Récolte de ressources
Lieux portent `ressources:[{ressource:"item:x", zones:[…]}]`. Éditeur mode Ressources → `PUT /api/lieu/{id}/ressources`. En déplacement, `resolve_zone_event` → `resolve_recolte` = matcher tags `table_evenements` VS `{categorie, sous_categorie, tags}` item → `random.choice`. Résultat = champ transitoire `character["ressource_recoltable"]` (réf `{item, poids}`), vidé à chaque déplacement comme `objets_au_sol`. Endpoint `POST /api/recolter` : refuse surcharge (409), ajoute au sac. UI : bouton 🌿 Récolter dans sidebar.

### Découpe du bois
Chaîne joueur (distincte recettes PNJ). Item coupable = tag `a_couper` + sous_cat ∈ `BOIS_A_COUPER` (ordre petit→grand). Tailles même essence = tag `essence_<xxx>`. `cible_coupe` = tier immédiatement plus petit de l'essence. **Couper = 1 niveau** : `repartir_poids` découpe instance en pièces ≈ max tier (poids conservé exact, borné `COUPE_MAX_PIECES`). Pièces → sol. Terminal = `branche` (pas `a_couper`). **Outil requis** : tag `outil_coupe_bois` en sac/équipement. Endpoints : `POST /api/couper` (409 sans outil, 422 non coupable), `/api/recolter` étendu (si ressource coupable → abat niveau vers sol). UI : boutons 🪓 Couper / 🪓 Abattre. World-vars : `BOIS_A_COUPER`, `OUTIL_COUPE_BOIS_TAG`, `COUPE_MAX_PIECES`.

### Consommables & effets temporaires
Item `categorie:"consommable"` + champ `effets:{pv, pm, regen_pv, regen_pm, buffs:{caract:Δ}, duree}`. `pv`/`pm` = instantanés ; `buffs`/`regen_*` = actifs sur `character["effets_actifs"][]` (empilable), tick monde = décrément. ⚠️ **Pas de buff sur V**. Portée buffs : appliqués dérivées partout (combat = intégralement, pas de tick en combat) ; EXCLU de charge_max/XP/restriction = anti-exploit. **Régén PM naturelle** = `ceil(Vol/20)`/déplacement. **Exploration** : `POST /api/consommer` (index+item_id) → payload+vitals+effets+consomme. UI : bouton 🍽️, chips ✨ effets_actifs. **Combat** : action `"consommer"` (1 action, effets instantanés seuls). Ordre écriture : combat → character → finalize. Tests purs.

### Sorts — magie PM + composants + apprentissage
Doc `sort:*` : `{nom, icon, description, vocation, niveau, cout_pm (>0 obligatoire), cible:"ennemi"|"soi", portee, effets, composants[]}`. `effets` = clés consommables + **`degats`** (notation dés, `roll_dice` composite). `composants[]` = `{item:"item:xxx", consomme:bool, bonus:{même schéma}}` : **consommé** = retiré du sac (gros bonus), **catalyseur** (`consomme:false`) = il suffit de le porter (sac/équipé, bonus moindre) ; bonus **additifs cumulables** (`fusionner_effets`, dés concaténés `2D6+1D6+2`). Contexte **dérivé** : combat ⇔ part instantanée (degats/pv/pm) ; exploration ⇔ `cible=="soi"` + (pv/pm/buffs+durée). Logique pure `utils/sorts.py` (DB injectée, pas de buff sur V). **Apprentissage** : `character["sorts_connus"][]` ; sort niveau n achetable si `vocations_niveaux[voc] ≥ n` + **grimoire porté** (item `sous_categorie:"grimoire"`, champ `sorts:[ids]`, NON consommé) + `attribute_points ≥ (n+1)×SORT_COUT_COEFF` → `POST /api/apprendre_sort`. À la **création**, vocations `SORT_VOCATIONS_DEPART` (9 pures) choisissent 1 sort niveau 0 (`characterinfo.sort_initial`, validé serveur, wizard étape 3). **Combat** : action `"sort"` (`ActionRequest.sort_id`+`composants`, 1 action, compteur `sorts`) — cible ennemi = jet d100 ≤ `_magic_hit_threshold(toucher_magique, pm_def cible)` (dérivée `toucher_magique = (Int*3+Vol)//4` ; miroir `_hit_threshold`), **PM débités avant le jet** (raté = dépensés), dégâts **sans soustraction de PA** (pm_def remplace esquive ET armure) ; portée > 1 = règles ranged (engagé interdit + LoS) ; snapshots portent `pm_def`/`toucher_magique` (rétro-compat `.get(...,0)`) ; router = même séquence que consommer (pop composants en mémoire → save combat → save character → finalize). **Exploration** : `POST /api/lancer_sort` (409 PM insuffisants, buffs → `effets_actifs` via `empiler_effet_sort`, même forme que consommables). **UI** : combat = bouton 🔮 + `#sort-row` (sélecteur + checkbox « Composants » = engager tout le disponible) + ciblage badges/tokens **violets** (`pendingSort`/`.spellcast`) ; play_town = onglet ⚡ (sorts connus + section 📖 Apprentissage, rendu client `_renderSorts`/`_renderSortsApprenables`). Contenu : `jsons/sort-exemples.json` (24 sorts niveau 0 × 12 vocations + 24 grimoires, composants = items existants). Tests purs `tests/test_sorts.py` (26 verts, suite 126 verts). **Accès rapide (2026-07-05)** : champ `character["sorts_epingles"][]` (ids ordonnés, auto-épinglage du premier sort connu si absent) ; bouton 📌 toggle dans l'onglet ⚡ ; barre d'icônes directement cliquables dans la barre d'action de combat (`#quick-sorts`, avant 🔮), composants disponibles engagés par défaut, cast direct (soi/1 cible) ou ciblage violet (plusieurs), endpoint `POST /api/epingler_sort {sort_id, epingle}`. Helper `sorts_epingles_effectifs(character)` + 4 tests. ✅ **Validé en jeu 2026-07-05** (5/6 points : import ✅, création ✅, casting exploration ✅, combat ✅, export ✅ ; apprentissage ⏳ différé).

### Focalisation — 🧭 lieu / 🎯 quête
Personnage focalise **UNE à la fois** : `character["focalisation"]:{type:"lieu"|"quete", cible, posee_at}`. Logique pure (mute sans save, DB injectée). `focalisation_effective` → intention `guidage`/`kill`/`collect`. **Guidage (lieu)** : BFS graphe `connection` (cache TTL 60s) → `prochaine_etape` + direction A\* (import lazy). Payload client = `{cible_nom, etape, link_id, porte, direction|None, distance}`. **Biais (quête)** : `boost_zone_event` ×`FOCUS_EVENEMENT_MULT` poids events visés ; `espece_weights_focus` ×`FOCUS_CIBLE_MULT` tirage espèce. Carcasse (`item:<sub>` ↔ `espece:<sub>`) → boost combats source. **Effacement auto** : arrivée lieu, quête terminée/abandonnée, kill atteint, collect complété. Endpoint `POST /api/focaliser` → `{focalisation, guidage}`. UI : boutons 🧭 lieux (onglet 🤝) + 🎯 quêtes (onglet 📜), classe `.btn-highlight`, sidebar `#guidage-action`. Tests purs `tests/test_focalisation.py` (23 tests, suite 105 verts). ✅ **Validé en jeu 2026-07-05**.

### PNJ de lieu — dialogues à choix + services
Un doc `lieu:*` porte `pnj:[{character:"pnj:xxx", portrait, image?, probabilite, description}]`. **Tirage de présence à l'ENTRÉE** dans le lieu (`/play` : `poser_pnj_present` + save), persisté en champ **transitoire** `character["pnj_present"]:{lieu, character|null}` → un refresh ne re-tire jamais ; re-tenter = ressortir/rentrer. Si présent : l'`image` de l'entrée remplace celle du lieu (variante avec PNJ visible, repli silencieux sur la version `_vide`), bouton sidebar 🗣. Doc PNJ **`type:"pnj"`** (`_id` préfixe `pnj:`) : `{nom, race, vocation, portrait, description, dialogue, services}`. **Dialogue** = arbre embarqué `{noeud_depart, noeuds:{id:{texte, texte_gratuit?, choix:[{id, label, next?, action:{service}?, condition?}]}}}` ; choix **filtrés serveur** par condition (`relation_min:{lieux[…OU logique], seuil}`, `intro_raison`), adressés par `choix_id`, placeholders `{prenom}`/`{cout}`. **Service soin** data-driven : `services.soin = {cout_cuivre, fraction_pv, gratuit_si:{lieux, seuil (défaut PNJ_REPUTATION_SEUIL), fraction_pv}, noeuds:{fait, sans_fonds, inutile}}` — gratuit ET plus efficace si une relation ≥ seuil ; routage des nœuds de résultat côté serveur (PV pleins = rien débité ; bourse vide = rien débité). Logique pure `utils/pnj.py` (relation_value_fn injectée) ; endpoints `routers/pnj.py` (`GET /api/pnj/dialogue`, `POST /api/pnj/dialogue/choix` — stateless, actions revalidées/débitées à l'exécution). UI play_town : panneau `#pnj-panel` (pattern quêtes), portraits servis par le mount **`/pnj`** (`templates/resources/pnj/`). Contenu : `jsons/dialogues_a_importer.json` (révérend Malakor + 2 lieux temple). Tests purs `tests/test_pnj.py` (20 tests).

### Intro narrative — fuite du village natal
Bloc **`intro`** sur le doc lieu de la cité : `{titre, texte, texte_conclusion, xp_conclusion, position_depart:{x,y}, zone_securite:"zone::coeur_ville", raisons:[{id, label, texte_suite}]}` (placeholders `{prenom}/{nom}/{race}`). À la **création** (`add_character`) : si la cité porte le bloc → spawn à `position_depart` (périphérie, zones à monstres sur le chemin) + `character["intro"]={statut:"en_cours"}` ; clé absente = rétro-compat totale. **Premier /play** : overlay `#intro-overlay` (non fermable) raconte la fuite → choix de la **raison** (dont « n'en rien dire ») via `POST /api/intro/raison` (persistée, sert aux conditions de dialogue PNJ `intro_raison`) → l'overlay ne revient plus. **Conclusion** dans `move_character` (2 branches) : `conclure_si_en_securite` quand la position entre dans `zone_securite` (helper géométrique `est_dans_zone`, `utils/zones.py` ; zone absente = conclusion au 1er déplacement) → statut `terminee` + XP + overlay de conclusion (`intro_terminee` dans la réponse ; branche lien = rejoué post-reload via sessionStorage `intro_fin_notif`). Logique pure `utils/intro.py`, tests `tests/test_intro.py` (13 tests). Contenu : `jsons/ville_a_importer.json` (3 villes, docs complets avec cells — **généré par script**, jamais à la main ; ajoute les placements `zone::coeur_capitale` à Lutecia et `zone::coeur_ville` à Rhemi).

### Mode « Lieux » — éditeur de carte
5e onglet dans `/admin/editor` (après Terrain/Navigation/Zones/Rencontres) : affiche les **points cliquables** aux positions des connexions du lieu courant. Nouveau module `utils/lieux.py` → route `GET /api/lieu/{id}/connections` = requête range sur vue `reseau/liens_cases`, chaque node enrichi de `details` (doc lieu sans `cells`/`_rev`/`_id`). **Lecture seule** : ne peint jamais la grille, drag désactivé. Clic point → liste les connexions de cette case dans le panneau latéral. **Overlay fiche** (`#lieu-fiche-overlay`) = réplique `play_town` : image du lieu (cascade `towns→battle_maps→maps`), liste des sous-lieux cliquables (boutons `.lf-subbtn` qui rechargent la fiche sur le voisin, idempotent). Fermeture : ✕/Échap/clic backdrop. Gère destinations sans `cells` (boutiques) en image fit. Aucune migration (docs/vue déjà présents). ✅ **Validé en jeu 2026-07-05**.

### Variables de monde réglables
Doc CouchDB `rules:world_variables`, chargé au démarrage `load_world_variables()`. **Lire via module** (jamais `from … import`). Éditables `/admin`. Groupes :
- **Marché** : `PRIX_DERIVE_BASE`, `MULT_RARETE`, `CHA_MARCHAND`, `PRIX_MAX_FACTEUR`, `MARGE_TRANSFO` (5.0), `RACHAT_FACTEUR` (0.6), `DEPECAGE_TAGS`/`_POIDS_REF`, `ATELIER_TRANSFO_PROBA` (0.10), `STOCK_CIBLE_DEFAUT`, `PRIX_AMPLITUDE_STOCK`, `VENTE_PNJ_PROBA`/`_FRACTION`, `APPRO_DEBIT`/`_DEFAUT` (5).
- **Relation/marchandage** : `RELATION_INITIALE` (50), `RELATION_SEUIL_COEFF` (2), `MARCHANDAGE_BLOCAGE_SECONDES` (3600), `PNJ_REPUTATION_SEUIL` (70 — « bonne réputation » par défaut pour services/conditions PNJ).
- **Jets** : `CRIT_REUSSITE_MAX` (5), `CRIT_ECHEC_MIN` (96) — génériques.
- **Progression XP** : `XP_NIVEAU_BASE` (10), `XP_NIVEAU_INCREMENT` (5) — niveau n = `BASE + (n−1)·INC`, cumulé quadratique.
- **Combat** : `JET_PORTEE_F_DIV` (20).
- **Quêtes** : `QUETE_BOARD_TAILLE` (6), `QUETE_QTE_MIN`/`_MAX`, `QUETE_XP_FACTEUR` (1.5), `QUETE_CUIVRE_PAR_XP` (3.0), `QUETE_COLLECT_POIDS_MAX` (100).
- **Bois** : `BOIS_A_COUPER`, `OUTIL_COUPE_BOIS_TAG`, `COUPE_MAX_PIECES` (40).
- **Focalisation** : `FOCUS_EVENEMENT_MULT` (3.0), `FOCUS_CIBLE_MULT` (3.0).
- **Sorts** : `SORT_COUT_COEFF` (2 — coût points = (niveau+1)×coeff), `SORT_VOCATIONS_DEPART` (9 vocations pures, sort gratuit à la création).

`current_world_variables()` = valeurs effectives ; `CODE_DEFAULTS` = défauts seuls `/admin/world_variables/defaults`.
