# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Telluris est un RPG médiéval-fantastique jouable en navigateur. Backend FastAPI servant des templates Jinja2 ; base CouchDB. Pas de framework JS — tout l'interactif est du **JS vanilla embarqué dans les templates**.

## Running the app

```bash
docker compose up
```

FastAPI sur `http://localhost:8000`, CouchDB sur `http://localhost:5984`. Le compose installe les dépendances Python au démarrage du conteneur (pas d'image pré-construite).

## Running tests

```bash
python -m pytest tests/            # logique Python pure, aucune dépendance base
node dev/check_js.js               # syntaxe du JS inline des templates ET de templates/scripts/*.js
node dev/test_<x>_client.js        # EXÉCUTION du JS client, sans dépendance, code 1 en échec
```

Harnais : `slots` · `resize` · `deplacement` · `voies` · `lot_lieux` · `lieu_form` · `connexions` · `dialogues` · `portes`. Méthode (extraction par nom, `runInThisContext`, globales semées), portée de chacun, collecte pytest en local : compétence **telluris-tests**.

- ⚠️ **Aucune règle de marche côté serveur** (`move_character` ne valide que les bornes) : `scripts/deplacement.js` EST la règle, `test_deplacement_client.js` son seul test.
- **Environnement local de l'agent** : Node (`C:\Program Files\nodejs\`) et Python (`C:\Python314\`) souvent **hors `PATH`** — `"/c/Program Files/nodejs/node.exe"` depuis Bash, `python -m pytest`. CouchDB injoignable en local ; Docker et l'app tournent côté utilisateur.

## Inspecting live DB values

La CouchDB live est distante, NON joignable en local. Valeurs réelles des docs : lire le dump committé **`telluris-dump-*.json`** (`{"db","exported_at","doc_count","docs":[...]}`, sans `user:*`) — grep sur `"_id": "rules:races"`. Exports ciblés, `/admin/table`, sémantique d'écriture, caches : compétence **telluris-db**.

## Gameplay Systems

```
main.py                  # FastAPI app, page routes (/play, /combat/{id}, /admin*, /admin/simulateur), static mounts
routers/
  user.py                # /api/* : auth, character CRUD, movement, equip/unequip, drop/pickup, spend_xp
  combat.py              # /api/combat/* : start, get, action, collect (loot)
  zones.py               # /api/* : zones d'influence + tables de rencontres/ressources par lieu + GET /api/items
  bestiaire.py           # /admin/* : CRUD espece:* / profil:* (+ éditeur)
  quetes.py              # /api/quetes/* : board, accepter, terminer, abandonner (guilde)
  recrutement.py         # /api/recrutement/* + /api/groupe/* : board de recrues, embaucher, congedier, engager
  montures.py            # /api/montures/* : étable, acheter, relacher
  auberge.py             # /api/auberge/* : salle commune (tables, tableau d'information), nuit
  scriptorium.py         # /api/scriptorium(/ecrire) : écrit personnel (papier+encre+plume → livre)
  animations.py          # /admin/animations/* : scan des feuilles de sprites, liaison au contenu
  pnj.py                 # /api/pnj/dialogue (+ /choix) : dialogues PNJ + services ; /api/intro/raison
utils/
  auth.py                # JWT creation + get_current_user() FastAPI dependency
  characters.py          # get/selected character, sync_equipment_bonus, grant_xp,
                         #   carried_weight, charge_max_of, références d'items (item_ref_*)
  fiche.py               # source unique du contenu des onglets Stats et ⚡ (bloc_fiche, derived_de, stat_caps, race_de)
  lieux.py               # lieu_router, movement logic, navigation bitmask
  combat.py              # logique de combat pure (snapshots, A*, résolution, loot, finalize)
  zones.py               # géométrie des zones d'influence + tirage d'événements + resolve_profil_weights
  sorts.py               # sorts (pur) : normalisation, composants, écoles de magie, apprentissage
  competences.py         # compétences de vocation (pur) : passives permanentes, actives, apprentissage
  consommables.py        # chokepoint des buffs : sources, cumul, effets_actifs
  slots_actions.py       # barre d'action de combat (pur) : entrées, invariante, migration à la lecture
  animations.py          # animations de combat (pur) : découpe d'une feuille, cascade de canaux, charge `vfx`
  quetes.py              # moteur de génération de quêtes (pur) + état joueur / progression / récompenses
  transport.py           # quêtes de transport (pur) : cargaison, délai, géographie, courses authorées
  chasse.py              # quêtes de chasse (pur) : élite à profil élevé, rang de guilde
  donjon.py              # donjons (pur) : salles curatées, plafond de grade, commissions d'éradication
  recrutement.py         # recrutement (pur) : recrues, tableau, groupe, affinités, parts, compagnie
  montures.py            # montures (pur) : étable, charge multipliée, troupeau
  auberge.py             # tavernes (pur) : tables-chatrooms, tableau d'information, nuit
  scriptorium.py         # scriptorium (pur) : écrit personnel transportable + livres de contenu générés au tick d'atelier
  escorte.py             # escortes (pur) : personne à retrouver, à protéger, à déposer vivante
  expedition.py          # capacités MISES EN COMMUN par le groupe (pur) : membres, outil partagé, négociateur
  marche.py              # prix, stocks, tick atelier, relations de lieu
  focalisation.py        # 🧭 lieu (BFS) / 🎯 quête (biais probabiliste)
  enseignes.py           # noms d'enseigne (pur) : tournures par métier × toponymes de cité
  capacites.py           # capacités d'un lieu (pur) : catalogue taverne/étable/scriptorium/recrutement/guilde
  grille_image.py        # grille de terrain depuis l'image d'une carte (pur) : indices auto-calibrés → 0/1/5
  bois.py                # découpe du bois (pur) : tier suivant par essence, conservation du poids, outil
  pnj.py                 # PNJ de lieu (pur) : tirage de présence, arbre de dialogue, services
  acces.py               # barrière d'accès à un lieu gardée par un PNJ (pur) : conditions, laissez-passer, cycle
  intro.py               # intro narrative (pur) : démarrage, overlay, raisons, conclusion en zone sûre
  simulateur.py          # duel 1D Monte Carlo (pur) : belligérants, politique de duel, équipement d'essai
  potentiel.py           # potentiels combat/survie/support (pur) : `REGLES_POTENTIEL` = le point d'édition
  xlsx.py                # writer xlsx OOXML pur stdlib (zipfile) — partagé bestiaire + export tableau admin
  lint_dialogues.py      # contrôle des arbres de dialogue (pur) — partagé CLI dev + bouton /admin
  dev_tools.py           # catalogue + lanceur des scripts de dev/ (liste blanche) — écran /admin/dev-tools
db/
  config.py              # CouchDB connection, get_doc / save_doc / find_docs helpers, cache de requête
models/
  character_stats.py     # BaseStats, DerivedStats, EquipmentBonus, compute_derived_stats(), variables de monde
  character_document.py  # Pydantic spec d'un doc personnage (référence seule — cf. note ci-dessous)
templates/
  *.html                 # Jinja2 pages (play_town, combat, fiche perso, admin, éditeurs)
  part-*.html            # fragments partagés : {% include %} de markup OU macros paramétrées
                         #   (part-character-card, part-slot-bar-css, part-move-panel)
  scripts/               # JS partagé, servi par le mount /scripts
                         #   battle_map.js · nav.js (bitmask nav) · deplacement.js (règles de marche)
                         #   voies.js (tracé des voies de l'éditeur : régions, goulots, passage)
  resources/             # assets statiques (characters, towns, maps, monsters, icons, pnj, sounds)
dev/
  gen_*.py               # générateurs de contenu → jsons/*_a_importer.json (catalogue : telluris-admin-tools)
  lint_dialogues.py · export_bestiaire.py · purge_quetes_acceptees.py · gen_grille_image.py
  check_js.js · test_*_client.js   # contrôle syntaxique + harnais d'exécution du JS client
tests/                   # tests purs, un fichier par système
```

## Compétences — où vit le détail

Chaque mécanique est documentée dans une compétence `.claude/skills/telluris-*` ; un renvoi « CLAUDE.md § <titre> » dans le code désigne la section homonyme de la compétence.

| Sujet | Compétence |
|---|---|
| caractéristiques, combat, dégâts, barre de slots, effets à durée, animations, simulateur | `telluris-combat` |
| bitmask `nav`, règles de marche, animation de carte/jetons, pavé partagé, mode test de déplacement | `telluris-map-movement` |
| `/admin/editor` : mode Lieux, formulaires de lieu/connexion, portes de rempart, lot de lieux, voies, redimensionnement | `telluris-editeur-carte` |
| items, poids, marché, recettes, grandes maisons, portée des recettes, flux de cité | `telluris-economie` |
| quêtes (guilde, transport, chasse, escorte), PNJ et dialogues, `/admin/dialogues`, accès, donjons, intro | `telluris-quetes-pnj` |
| recrutement, groupe, compagnie, contrat de mission, montures | `telluris-recrutement` |
| sorts, compétences de vocation, focalisation | `telluris-magie` |
| journal, relations, cartes/portraits, listes scrollables, tavernes, scriptorium, toasts | `telluris-social-ui` |
| dump, exports, `/admin/table`, écritures PUT complet, cache de requête, caches process | `telluris-db` |
| lanceur `dev/`, générateurs de contenu, variables de monde | `telluris-admin-tools` |
| harnais Node, `check_js`, collecte pytest | `telluris-tests` |

## Conventions transverses

Règles qui valent **partout** ; les compétences ne répètent que ce qui leur est propre.

**1. Chokepoint `_acteur(current_user, body)`** (`routers/user.py`) → `(porteur, principal)`. Sans `compagnon_id` les deux sont le même dict ; avec, le porteur est le doc `aventurier:*` ou `monture:*`. ⚠️ Ces docs **n'ont pas de `user_id`** : leur appartenance se prouve par le statut + le lien vers CE personnage (`groupe_effectif`/`montures_effectives`) → **403** sinon. Client : **`_actionBody(extra)`** injecte le `compagnon_id`. Sauvegarde **`_save_acteur`** : porteur **autoritatif d'abord** (409), le reste best-effort. ⚠️ **Toute action doit porter le `compagnon_id` de l'ACTEUR COURANT** — sans lui, `_acteur` retombe **en silence** sur le principal : il écrit le mauvais doc *et* renvoie son état, que le client affiche comme celui du compagnon. C'est la classe de bug la plus coûteuse du projet.

**2. Modules purs `utils/*`** : DB injectée (`get_doc_fn`/`save_doc_fn`/`find_docs`), **mutent sans sauver** (l'appelant persiste), testés sans base. Un helper partagé par plusieurs routers vit dans `utils/`, **jamais dans un router** — `routers/recrutement` importe `routers/user`, l'inverse créerait un cycle.

**3. Anti-exploit des buffs** : `charge_max_of`, les plafonds et coûts d'XP (`compute_stat_cap`, `compute_xp_cost`) et `restriction_satisfaite` lisent `caracteristiques_current` **BRUT**. Un buff n'ouvre jamais un plafond, n'abaisse jamais un tarif, ne débloque jamais une arme.

**4. Aucune migration de base.** Champ absent ⇒ comportement d'avant ; une forme neuve est reconstruite **À LA LECTURE** (`slots_effectifs`, `_slots_derives`, replis `.get(..., 0)` sur les snapshots). Un doc déjà en base doit toujours continuer de tourner.

**5. Péremption et vérification PARESSEUSES** — **aucun tick de fond n'existe**. Tout ce qui expire est contrôlé au passage : tableaux de quêtes et de recrues (`purger_*`), délais de course (`traiter_expirations` : `/play`, les **deux** branches de `move_character`, entrée du dialogue PNJ), départs volontaires de compagnons, laissez-passer.

**6. Champs transitoires du personnage** : `pnj_present`, `transport_offert`, `rang_offert`, `ressource_recoltable`, `objets_au_sol`. Tirés à l'**ENTRÉE** dans le lieu et persistés (un refresh ne re-tire pas ; ressortir/rentrer re-tire), vidés dès un déplacement réel.

**7. Porteurs vs membres.** `recrutement.porteurs_effectifs(character, get_doc)` = SOURCE UNIQUE de qui **porte** (compagnons + montures). `expedition.membres(character, get_doc)` = qui **agit** (principal EN TÊTE puis compagnons) — ⚠️ **JAMAIS de monture**. L'ordre compte : les ex æquo se départagent par « le premier gagne », et c'est le joueur qui doit gagner.

**8. Overlays de décision bloquante** (`#clauses-overlay`, `#engagement-overlay`, `#max-bonus-overlay`, `#cible-allie-overlay`…) : ⚠️ **✕ / Échap / clic sur le backdrop = ANNULER sans rien engager**. Quand un appel attend la réponse, l'annulation **résout la promesse à `null`**, sinon le lancement reste suspendu et son bouton désactivé pour toujours.

**9. XSS — on BORNE au serveur, on ÉCHAPPE au rendu.** Les nettoyages serveur (`recrutement.nettoyer_nom_compagnie`…) valident et bornent sans échapper (double échappement sinon) ; `escapeHtml` est obligatoire dès qu'une chaîne saisie part dans un template literal `innerHTML`. ⚠️ **Jamais dans un `onclick="…('${x}')"`** (`'` → `&#39;` casse la chaîne JS) : lire la valeur depuis l'`<input>` en JS. ⚠️ **Jamais pour `showToast`**, qui écrit en `textContent`.

**9 bis. Les toasts s'EMPILENT** : un appel à `showToast(msg)` = une bulle, pile plafonnée ; `{major:true}` est réservé aux moments de jeu. Détail : `telluris-social-ui`.

**10. Resync de payload.** Tout endpoint qui bouge un état **renvoie le bloc recalculé** (`slots`, `relations_lieux`, `caracts_detail`, `inventaire_payload`, `links`…). Le client ne reconstruit jamais un état ; sans le bloc, l'onglet reste figé sur le dernier chargement de `/play` — symptôme difficile à relier à sa cause.

**11. Import et écriture de contenu.** Docs de contenu dans `jsons/*_a_importer.json`, chargés par la carte d'import de `/admin`. ⚠️ **`admin_import_bulk` et `PUT /admin/doc` font un PUT COMPLET, jamais un merge, et ne refusent rien** (`_rev` réattaché depuis la base) : un `_id` réutilisé écrase en silence, une clé absente disparaît. D'où les générateurs `dev/gen_*.py`, qui relisent le **dump** et n'injectent que le champ ajouté (régénération **idempotente**), et les formulaires d'admin qui fusionnent le doc **relu**. ⚠️ Avant de livrer un générateur : aucune collision d'`_id`, rejeu contre un export récent.

**12. Écriture de fichiers — jamais de heredoc shell.** Toujours Write/Edit : l'échappement casse sur l'Unicode, les tabulations et les apostrophes. ⚠️ **Fins de ligne MIXTES selon le fichier** (pas de `.gitattributes`) : ne jamais normaliser CRLF↔LF au passage d'une édition.

**13. Discipline de périmètre.** Implémenter exactement ce qui est demandé : pas de repli, de nouvel opérateur de condition, ni de lecture défensive depuis un autre type de doc sans demande explicite. Un mécanisme jugé nécessaire se propose et attend une réponse.

**14. La suite de tests clôt la tâche.** Après toute modification du moteur, du simulateur ou d'un payload client, relancer `pytest` (et les harnais Node concernés si du JS a bougé) et annoncer le nombre de tests passés ; si le comportement change, les tests sont mis à jour dans la même passe. ⚠️ Pièges déjà pris : un `random` non contrôlé dans un test (le hasard passe par un `rand_fn`/`des_fn` injecté) et un compagnon de fixture sans `caracteristiques_current`.

**15. Vérifier le rendu après une modif template/CSS/JS**, pas seulement la relire. Pièges déjà pris : un calque `pointer-events:none` qui avale les clics d'un enfant (`telluris-combat` § Sur un ALLIÉ) ; un `const` capturé par `getElementById` avant que son markup existe (`telluris-map-movement` § mode test de déplacement) ; un sondage qui redessine un champ en cours de frappe (`telluris-social-ui` § Tavernes).

**16. Documentation compacte.** Listes courtes, pas de prose ; ne pas restituer ce que le code dit déjà ni ce qu'un test verrouille (une ligne « verrouillé par … » suffit). Le détail d'un système va dans sa compétence, pas ici.

## Core Design Patterns

### CouchDB document IDs
Pattern `type:identifier` — `user:email@example.com`, `lieu:lutecia`, `rules:races`. Personnages = `character:<user_id>_<uuid>`.

### Derived stats are never stored
`DerivedStats` recalculées par `compute_derived_stats()` à chaque requête. Ne jamais persister une valeur dérivée.

### Character document vs. Pydantic model
`models/character_document.py` = spec de référence. **Vérité = le code de création dans `routers/user.py`.** Les noms de champs diffèrent : `voc`, `sex`, `caracteristiques_standard`/`current`, `cite`.

### Capacités d'un lieu — « le type » n'est pas un champ
Résolues **à la lecture** par cinq prédicats `categorie == X` **OU** tag `Y` (le OU évite toute migration) : `auberge.lieu_est_taverne` · `montures.lieu_vend_montures` · `scriptorium.lieu_est_scriptorium` · `recrutement.lieu_recrute` · `recrutement.lieu_de_guilde`. ⚠️ `utils/capacites.py` les **RECOPIE** pour l'éditeur (les importer tirerait `marche`/`expedition`/`quetes`) ; la recopie est verrouillée par `tests/test_capacites.py` — modifier un prédicat, c'est modifier les deux.

### Cache de documents
`get_doc` est mémorisé **par requête** pour les seuls préfixes de contenu (`_CACHEABLE_PREFIXES`) ; tout doc d'état de partie en est exclu. Un nouveau préfixe se classe explicitement. Recettes, fusion de catégories et portée sont mémoïsées par process et vidées par `marche.reset_prix_cache()`. Détail : `telluris-db`.
