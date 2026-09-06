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
python -m pytest tests/          # logique Python pure, aucune dépendance base
node dev/check_js.js               # syntaxe du JS inline des templates/*.html ET de templates/scripts/*.js
node dev/test_slots_client.js      # exécution des fonctions pures de la barre de slots
node dev/test_resize_client.js     # exécution du redimensionnement de grille (éditeur de carte)
node dev/test_deplacement_client.js # exécution des règles de MARCHE partagées (scripts/deplacement.js)
```

Les tests pytest ne couvrent que la logique pure (stats, combat, marché/recettes, consommables, sorts, quêtes…). Les quatre harnais Node sont **sans aucune dépendance** (ni `package.json`, ni second écosystème à entretenir) et sortent en **code 1** en cas d'échec.

- `check_js.js` neutralise les expressions Jinja avant de passer le code au parseur de Node — ⚠️ en `(0)` et non `0`, sinon `{{ liste | tojson }}.forEach(...)` deviendrait `0.forEach(...)`, faux positif garanti. ⚠️ Il contrôle **aussi `templates/scripts/*.js`** : les `<script src=…>` sont sautés (ils n'ont pas de corps dans la page), si bien que `nav.js`, `battle_map.js` et `deplacement.js` n'étaient couverts par **rien**. Un `.js` n'ayant pas de balise, le fichier entier est traité comme un unique bloc.
- `test_slots_client.js` extrait les fonctions **pures** du template (par nom, accolades équilibrées) et les exécute dans un contexte `vm` : il ferme la classe de bug « à qui appartient ce que j'affiche et ce que j'écris ? », qu'aucun test pytest ne peut atteindre. **Hors de portée sans jsdom** : rendu DOM, clic long, ordre inversé en mobile — à vérifier en jeu.
- `test_deplacement_client.js` est le seul des quatre à **charger directement un `.js`** (`scripts/nav.js` puis `scripts/deplacement.js`) : il n'y a rien à extraire d'un template. Il est aussi le **seul test des règles de marche du jeu**, et ce n'est pas une commodité — ⚠️ **il n'existe AUCUNE règle de marche côté serveur** : la branche x/y de `move_character` ne valide que les bornes, ni terrain ni `nav`. `deplacement.js` ne double donc pas le serveur, **il EST la règle**.
- `test_resize_client.js` suit la même méthode pour le redimensionnement de carte (`admin_map_editor.html`) — ⚠️ mais avec **`vm.runInThisContext`** et non `vm.createContext` : un contexte séparé est un autre *realm*, donc ses tableaux ont un autre prototype `Array` et `deepStrictEqual` les refuse tous. Ces fonctions-ci n'ayant besoin d'aucune globale, les évaluer dans le realm du test suffit — et permet au passage de semer sur `globalThis` les quelques globales dont `_reappliquerPortes` dépend, seul moyen d'éprouver son idempotence.

**Environnement local de l'agent** : Node dans `C:\Program Files\nodejs\`, Python dans `C:\Python314\`. ⚠️ Les deux peuvent être **hors du `PATH`** — appeler Node par son chemin complet (`"/c/Program Files/nodejs/node.exe"` depuis Bash) et pytest par `python -m pytest` (l'exe vit dans `~/AppData/Roaming/Python/Python314/Scripts`, hors `PATH`). Dépendances nécessaires **rien que pour collecter** les tests purs (ils importent `utils/*` → `routers/*`) : `pytest` + la ligne du `docker-compose.yml` **sans `uvicorn` ni `Pillow`** (`fastapi Jinja2 couchdb2 bcrypt pyjwt[crypto] authlib httpx itsdangerous`). CouchDB est injoignable en local : `db/config.py` tolère l'absence de connexion à l'import (`server`/`db` = `None`, les helpers renvoient `None`) pour que les tests purs se collectent. Docker et l'app tournent côté utilisateur.

## Inspecting live DB values

La CouchDB live tourne sur un hôte distant, généralement NON joignable en local. Pour connaître les valeurs réelles des documents (races, espèces, profils, lieux, items…), lire le dump JSON committé à la racine : **`telluris-dump-*.json`** (produit par `GET /admin/exports/couchdb` / `db.config.dump_all_docs()`). Objet `{"db","exported_at","doc_count","docs":[...]}` ; `docs` exclut les `user:*`. Repérer un doc par grep sur `"_id": "rules:races"`.

- **Export ciblé d'un type** : `GET /admin/exports/by-type?type=<type>` (`find_docs({"type": t})`, `user:*` exclus) → `<type>-AAAAMMJJ-HHMMSS.json` ; la page `/admin/exports` liste les types présents en base.
- **Édition en tableau** : `/admin/table` (`admin_table.html`, carte « Mise à jour en tableau » dans `/admin`) liste les docs d'un type en tableau (colonnes choisies/ordonnées par drag, triables, filtrables, redimensionnables) ; cliquer une ligne ouvre le JSON dans un overlay fixe à droite. **Save** = `PUT /admin/doc` / **Cancel** ferme / **Delete** = `DELETE /admin/doc?id=…` après `confirm()`, la ligne étant retirée localement sans rechargement du type. ⚠️ Le `_rev` est **relu en base**, jamais celui du client ; `db.delete_doc` renvoyant `None` succès comme échec, le serveur vérifie par relecture → 409. Données : `GET /admin/table/data?type=<t>`. Préférences d'affichage (colonnes/ordre/tri/filtres/largeurs) mémorisées **par type** dans `localStorage` (`telluris.admin_table.v1.<type>`).
- **Export du tableau** : deux boutons au-dessus exportent les lignes **actuellement affichées** (filtres+tri, `computeVisibleRows`) — **⬇ Export JSON** (docs complets) et **⬇ Export Excel** (`POST /admin/table/export.xlsx` → writer OOXML partagé `utils/xlsx.py`, une colonne par clé de 1er niveau, valeurs imbriquées en JSON). Nom commun `exportFilename(ext)` = `<type>_filtre_<col>_<val>…_AAAAMMJJ-HHMMSS.(json|xlsx)`, horodatage **UTC** aligné sur les exports serveur (`datetime.utcnow()`).

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
  config.py              # CouchDB connection, get_doc / save_doc / find_docs helpers
models/
  character_stats.py     # BaseStats, DerivedStats, EquipmentBonus, compute_derived_stats()
  character_document.py  # Pydantic spec d'un doc personnage (référence seule — cf. note ci-dessous)
templates/
  *.html                 # Jinja2 pages (play_town, combat, fiche perso, admin, éditeurs)
  part-*.html            # fragments partagés : {% include %} de markup OU macros paramétrées
                         #   (part-character-card, part-slot-bar-css, part-move-panel)
  scripts/               # JS partagé, servi par le mount /scripts
                         #   battle_map.js · nav.js (bitmask nav) · deplacement.js (règles de marche)
  resources/             # assets statiques (characters, towns, maps, monsters, icons, pnj, sounds)
dev/
  export_bestiaire.py    # export d'équilibrage (writer OOXML → utils/xlsx.py)
  gen_marchands.py       # génère les 28 tenanciers génériques `pnj:marchand_*`
  gen_acces_donjon.py    # génère les imports de la chaîne d'accès au donjon-mine
  gen_relation_guilde.py # pose `relation_lieu` : les 4 lieux du Bastion partagent UNE cote
  gen_escorte_marchands.py # pose les nœuds d'escorte sur les 29 `pnj:marchand_*`
  gen_progeniture.py     # donne une FAMILLE à une dizaine de boutiques (entrée `pnj` du lieu)
  gen_escorte_guilde.py  # ouvre le registre des disparitions au comptoir (Borin)
  gen_epaulieres.py      # 21 pièces d'épaules + recettes — l'emplacement `epaules` n'avait rien à porter
  gen_loot_immateriel.py # sous-catégorie + recettes pour 32 butins immatériels (esprits, morts-vivants)
  gen_coherence_france.py# ressources + espèces manquantes de `lieu:france` (+ `restriction_tags` magique)
  gen_grades_france.py   # descend les profils de niveau 5-6 du lieu vers `zone:tres_dangereuse`
  gen_lutecia.py         # donne ses zones d'influence à la capitale (urbain, Seine, faubourgs, campagne)
  lint_dialogues.py      # CLI de contrôle des dialogues PNJ (→ utils/lint_dialogues.py)
  purge_quetes_acceptees.py # purge ONE-SHOT des docs `quete:*` générés acceptés (poids mort)
  check_js.js            # contrôle SYNTAXIQUE du JS des templates ET de templates/scripts/ (node)
  test_slots_client.js   # tests d'EXÉCUTION du JS de la barre de slots (node, sans dépendance)
  test_deplacement_client.js # tests d'EXÉCUTION des règles de marche (scripts/deplacement.js)
tests/                   # tests purs, un fichier par système
```

## Conventions transverses

Règles qui valent **partout** ; les sections suivantes ne répètent que ce qui leur est propre.

**1. Chokepoint `_acteur(current_user, body)`** (`routers/user.py`) → `(porteur, principal)`. Sans `compagnon_id` les deux sont le même dict (un seul `save_doc`) ; avec, le porteur est le doc `aventurier:*` ou `monture:*`. ⚠️ Ces docs **n'ont pas de `user_id`** : leur seule preuve d'appartenance est le statut + le lien vers CE personnage (`embauche`/`embauche_par`, `acquise`/`acquise_par`) via `groupe_effectif`/`montures_effectives` → **403** sinon. Côté client, **`_actionBody(extra)`** injecte le `compagnon_id`. Sauvegarde multi-docs **`_save_acteur`** : porteur **autoritatif d'abord** (409), le reste best-effort. ⚠️ **Toute action doit porter le `compagnon_id` de l'ACTEUR COURANT** — `_acteur` retombe **silencieusement sur le principal** quand le corps n'en porte pas, ce qui écrit sur le mauvais doc *et* renvoie l'état du mauvais doc, que le client affiche comme celui du compagnon. Les deux états finissent durablement mélangés. C'est la classe de bug la plus coûteuse du projet.

**2. Modules purs `utils/*`** : DB injectée (`get_doc_fn`/`save_doc_fn`/`find_docs`), **mutent sans sauver** (l'appelant persiste), testés sans dépendance base. Un helper partagé par plusieurs routers vit dans `utils/`, **jamais dans un router** — `routers/recrutement` importe `routers/user`, donc l'inverse créerait un cycle.

**3. Anti-exploit des buffs** : `charge_max_of`, les plafonds et coûts d'XP (`compute_stat_cap`, `compute_xp_cost`) et `restriction_satisfaite` lisent `caracteristiques_current` **BRUT**. Un buff n'ouvre jamais un plafond, n'abaisse jamais un tarif, ne débloque jamais une arme.

**4. Aucune migration de base.** Champ absent ⇒ comportement d'avant ; quand une forme neuve est nécessaire, elle est reconstruite **À LA LECTURE** (`slots_effectifs`, `_slots_derives`, replis `.get(..., 0)` sur les snapshots de combat). Un doc déjà en base doit toujours continuer de tourner.

**5. Péremption et vérification PARESSEUSES** — **aucun tick de fond n'existe dans le jeu**. Tout ce qui expire est contrôlé au passage : tableaux de quêtes et de recrues (`purger_*`), délais de course (`traiter_expirations`, appelé à `/play`, dans les **deux** branches de `move_character` et à l'entrée du dialogue PNJ), départs volontaires de compagnons, laissez-passer.

**6. Champs transitoires du personnage** : `pnj_present`, `transport_offert`, `rang_offert`, `ressource_recoltable`, `objets_au_sol`. Même sémantique — tirés à l'**ENTRÉE** dans le lieu et persistés, donc un refresh ne re-tire pas ; ressortir/rentrer re-tire ; vidés dès un déplacement réel.

**7. Porteurs vs membres — deux listes à ne pas confondre.** `recrutement.porteurs_effectifs(character, get_doc)` = SOURCE UNIQUE de « qui **porte** pour moi » (`groupe_effectif` + `montures_effectives`, compagnons d'abord). `expedition.membres(character, get_doc)` = qui **agit** (principal EN TÊTE puis compagnons) — ⚠️ **JAMAIS de monture** : une bête porte le butin, elle ne négocie pas et ne manie pas une hache. L'ordre compte : plusieurs appelants départagent les ex æquo par « le premier gagne », et c'est le joueur qui doit gagner.

**8. Overlays de décision bloquante** (`#clauses-overlay`, `#engagement-overlay`, `#max-bonus-overlay`, `#cible-allie-overlay`) : ⚠️ **✕ / Échap / clic sur le backdrop = ANNULER sans rien engager** — une décision irréversible ne doit jamais partir d'un geste de sortie. Quand un appel attend la réponse, l'annulation doit **résoudre la promesse à `null`**, sinon le lancement reste suspendu et son bouton désactivé pour toujours.

**9. XSS — on BORNE au serveur, on ÉCHAPPE au rendu.** Les helpers de nettoyage serveur (`recrutement.nettoyer_nom_compagnie`…) valident et bornent mais **n'échappent pas le HTML** (double échappement sinon) ; le client a son `escapeHtml`, obligatoire dès qu'une chaîne saisie par le joueur part dans un template literal `innerHTML`. ⚠️ **Jamais dans un `onclick="…('${x}')"`** (`'` → `&#39;` casserait la chaîne JS) : lire la valeur depuis l'`<input>` en JS. ⚠️ **Jamais pour `showToast`**, qui écrit en `textContent`.

**9 bis. Les toasts s'EMPILENT** (`play_town_telluris.html`, seul fichier à définir `showToast` — `combat_telluris.html` a le sien). `#toast` et `#toast-major` sont des **conteneurs**, pas des bulles : chaque appel crée sa `.toast-item`, avec sa propre durée de vie, et la pile est plafonnée à `TOAST_MAX` (4). Avant, l'élément était unique et `textContent` était réécrit à chaque appel → **deux messages coup sur coup n'en laissaient voir qu'un**, en silence. Signature **rétro-compatible** : `showToast(msg)` inchangé sur la centaine de sites d'appel, `{major:true}` en 2ᵉ argument pour la bulle haute, grande et longue (7 s), réservée aux **moments de jeu** (dépose d'escorte) et non aux accusés de réception. ⚠️ **Double `requestAnimationFrame`** avant la classe `.show` — une transition n'a rien à interpoler sur un élément qui vient de naître (même piège que les jetons de combat). ⚠️ Garde `prefers-reduced-motion` **locale** : ce template n'inclut pas `part-accessibility-css.html`. ⚠️ `_fideliteSuffixe` / `_xpCompagnieSuffixe` **restent** — suffixer n'est plus une contrainte technique mais le bon rendu (une vente et son bonus de fidélité sont *un* événement, pas deux).

**10. Resync de payload.** Tout endpoint qui bouge un état doit **renvoyer le bloc correspondant recalculé** (`slots`, `relations_lieux`, `caracts_detail`, `inventaire_payload`, `links`…). Le client ne reconstruit jamais un état lui-même ; sans le bloc, l'onglet reste figé sur l'état du dernier chargement de `/play` — symptôme classique et difficile à relier à sa cause.

**11. Import de contenu.** Les docs de contenu vivent dans `jsons/*_a_importer.json`, chargés par la carte d'import de `/admin`. ⚠️ **`admin_import_bulk` fait un PUT COMPLET, jamais un merge** : éditer un champ oblige à reproduire tout le doc — d'où les générateurs `dev/gen_*.py`, qui relisent les docs depuis le **dump** (source unique) et n'y injectent que le champ ajouté, ce qui rend la régénération **idempotente** (une retouche faite à la main en base survit, réimporter ne peut rien annuler en silence). Le `_rev` d'un doc importé est sans effet : il est toujours réattaché depuis la base. ⚠️ Avant de livrer un générateur neuf, vérifier l'absence de collision d'`_id` et rejouer le générateur contre un export récent (`telluris-dump-*.json` ou `/admin/exports/by-type`) plutôt que de le supposer correct.

**12. Écriture de fichiers — jamais de heredoc shell.** Toujours passer par les outils Write/Edit pour écrire ou patcher un fichier, jamais par un heredoc shell (`cat <<EOF`) : l'échappement casse sur l'Unicode, les tabulations et les apostrophes, et bute sur les limites de spawn. ⚠️ **Fins de ligne MIXTES selon le fichier** (aucune convention uniforme dans ce dépôt, pas de `.gitattributes`) : ne jamais normaliser CRLF→LF (ni l'inverse) au passage d'une édition — préserver celles du fichier touché, quelles qu'elles soient.

**13. Discipline de périmètre.** Implémenter exactement ce qui est demandé : pas de repli, de nouvel opérateur de condition, ni de lecture défensive depuis un autre type de doc (ex. un repli non demandé vers `pnj:*`) sans que ce soit explicitement demandé. Un mécanisme supplémentaire jugé nécessaire se propose et s'attend une réponse, il ne s'ajoute pas en silence.

**14. La suite de tests clôt la tâche.** Après toute modification touchant le moteur, le simulateur ou un payload client, relancer `pytest` (et les harnais Node concernés si du JS a bougé, cf. § Running tests) et annoncer le nombre de tests passés avant de déclarer la tâche terminée ; si le comportement change, les tests eux-mêmes sont mis à jour dans la même passe. ⚠️ Deux pièges déjà rencontrés dans ce projet : un tirage `random` non contrôlé dans un test (le hasard doit passer par un `rand_fn`/`des_fn` injecté, cf. §Dégâts) et un dict de compagnon de fixture auquel il manque `caracteristiques_current`.

**15. Vérifier le rendu après une modif template/CSS/JS**, pas seulement la relire. Trois pièges déjà pris dans ce projet, à ne pas rejouer : un calque `pointer-events:none` qui avale les clics d'un enfant qui ne le rouvre pas pour lui-même (cf. § Sur un ALLIÉ) ; un `const` capturé par `getElementById` avant que son markup n'existe dans le DOM (cf. § mode « test de déplacement ») ; un sondage qui redessine un champ de saisie en cours de frappe (cf. § Tavernes, SONDAGE).

**16. Documentation compacte.** CLAUDE.md et la doc du projet restent en listes courtes, pas en prose : ne pas y restituer ce que le code dit déjà lui-même, ni ce qu'un test verrouille déjà.

## Core Design Patterns

### CouchDB document IDs
Pattern `type:identifier` — `user:email@example.com`, `lieu:lutecia`, `rules:races`. Personnages = `character:<user_id>_<uuid>`.

### Derived stats are never stored
`DerivedStats` recalculées par `compute_derived_stats()` à chaque requête. Ne jamais persister une valeur dérivée.

### Character document vs. Pydantic model
`models/character_document.py` = spec de référence. **Vérité = le code de création dans `routers/user.py`.** Les noms de champs diffèrent : `voc`, `sex`, `caracteristiques_standard`/`current`, `cite`.

### Cache de documents à portée REQUÊTE (`db/config.py`)
`get_doc` était un aller-retour HTTP par appel, sans cache — une seule vente en faisait 200 à 350 (relectures répétées du même doc `item:*`). D'où **`RequestDocCacheMiddleware`**, monté dans `main.py` après le `SessionMiddleware`, qui mémorise par requête les docs de **CONTENU** (`_CACHEABLE_PREFIXES`) et exclut tout ce qui porte un état de partie (`character:`, `aventurier:`, `lieu:`, `combat:`, `quete:`…), lu/muté/sauvé dans la même requête. Hit/miss, whitelist, copie de surface, invalidation et kill-switch `TELLURIS_DOC_CACHE=0` sont couverts par `tests/test_doc_cache.py`.

⚠️ **Middleware ASGI PUR, jamais `@app.middleware("http")`** : `BaseHTTPMiddleware` exécute l'aval dans une tâche anyio distincte, ce qui casserait la propagation du `ContextVar`. ⚠️ Le `ContextVar` est posé **par le middleware et nulle part ailleurs** — `get_doc` ne fait que **muter** l'objet stocké : un endpoint `def` tourne dans le threadpool avec une **copie** du contexte, la copie partage l'objet (donc les mutations portent) mais un `set()` fait depuis le thread serait perdu.

**Caches process voisins, à ne pas confondre** : `utils/marche.py` mémorise les **recettes** (`_all_recettes` → `_recipe_map` / `_marche_map` / `lieu_recettes`, une lecture par process) et la **route d'image d'un lieu** (`_lieu_image_route`, mémo par nom de fichier — aucun endpoint d'upload n'existe, le disque ne bouge pas à chaud). Vidés par **`reset_prix_cache()`**, appelé au chargement des variables de monde **et** en fin d'`admin_import_bulk` / `PUT /admin/doc` quand un doc `type ∈ {recette, item}` est écrit — sans quoi importer une recette n'avait aucun effet visible.
