---
name: telluris-tests
description: How Telluris tests are built and run — pytest collection requirements on the agent's machine, dev/check_js.js (syntax of inline template JS and templates/scripts/*.js), and the dependency-free Node harnesses dev/test_*_client.js that EXECUTE client JS — extracting pure functions from templates by name, vm.runInThisContext vs createContext realms, seeding globals (VOCAB, PORTE_* constants), what each harness locks and what is out of reach without jsdom. Load when adding or changing a test harness, writing a client JS function that deserves a test, when a Node harness or check_js fails in a puzzling way, or when pytest fails to collect locally.
---

### Lancer toute la suite (agent, Git Bash)
```bash
python -m pytest tests/ -q
for f in dev/check_js.js dev/test_*_client.js; do out=$("/c/Program Files/nodejs/node.exe" "$f" 2>&1) || { echo "ÉCHEC $f"; echo "$out"; }; done
```
Annoncer le nombre de tests passés avant de clore (CLAUDE.md §14).


### Collecte pytest en local
`tests/` importe `utils/*` → `routers/*` : il faut `pytest` + `fastapi Jinja2 couchdb2 bcrypt pyjwt[crypto] authlib httpx itsdangerous` (la ligne du `docker-compose.yml` **sans `uvicorn` ni `Pillow`**). L'exe pytest vit hors `PATH` (`~/AppData/Roaming/Python/Python314/Scripts`) → `python -m pytest`.

- CouchDB injoignable : `db/config.py` pose `server`/`db` à `None` à l'import, ses helpers renvoient `None` — les tests purs se collectent.
- ⚠️ **Pillow importé paresseusement** (`utils/grille_image.py`, `utils/lieux.py`, `routers/animations.py`) : un import en tête casserait la collecte.
- Hasard **injecté** (`rand_fn`/`des_fn`), jamais `random` direct ; une fixture de compagnon porte `caracteristiques_current`.


### `dev/check_js.js` — syntaxe
- Neutralise les expressions Jinja en **`(0)`**, pas `0` : `{{ liste | tojson }}.forEach(...)` deviendrait `0.forEach(...)`, faux positif garanti.
- Contrôle aussi **`templates/scripts/*.js`**, fichier entier = un bloc : les `<script src=…>` n'ont pas de corps dans la page, ces fichiers n'étaient couverts par rien.
- ⚠️ Ne jamais écrire une balise d'ouverture de script en toutes lettres dans un **commentaire HTML** : `check_js` la prend pour un vrai bloc et contrôle du texte français.


### Harnais d'exécution — la méthode
Aucune dépendance (ni `package.json`, ni second écosystème), code 1 en échec, helper `t(nom, fn)`.

- **Extraction** : les fonctions **pures** sont extraites du template **par nom** (accolades équilibrées, `extraire(nom)`), les constantes aussi (`extraireConst`, ex. `PORTE_*`) plutôt que recopiées — une recopie dérive en silence.
- **Chargement direct** quand la logique vit dans `templates/scripts/` : `nav.js` → `deplacement.js` (→ `voies.js`).
- ⚠️ **`vm.runInThisContext`, pas `vm.createContext`** : un contexte séparé est un autre *realm*, ses tableaux ont un autre prototype `Array` et `assert.deepStrictEqual` les refuse tous. Le realm du test permet aussi de **semer des globales** sur `globalThis` : `VOCAB` (dialogues — vocabulaire servi par le serveur), les globales de `_reappliquerPortes` (resize, pour éprouver l'idempotence).
- Une fonction testable prend ses données **en paramètres** au lieu de lire l'état de page (`dejaPris` de `_prochainLinkId`, `tenanciers` de `_lotDocs`).
- ⚠️ **Hors de portée sans jsdom** : rendu DOM/SVG/canvas, visées, clic long, ordre mobile, overlays — à vérifier à l'écran (CLAUDE.md §15). Chaque harnais le liste dans son en-tête.


### Ce que verrouille chaque harnais
| Harnais | Cible | Classe de bug fermée |
|---|---|---|
| `test_slots_client` | barre de slots (`combat_telluris.html`) | à qui appartient ce que j'affiche et ce que j'écris (`acteurCompagnonId`) |
| `test_deplacement_client` | `scripts/deplacement.js` | les **seules** règles de marche du jeu — aucune n'existe côté serveur |
| `test_voies_client` | `scripts/voies.js` | régions, goulots (coin, eau, brèche de 2), Tarjan itératif, chemins, coupe |
| `test_resize_client` | redimensionnement (`admin_map_editor.html`) | `nav`/zones/portes rééchantillonnés, recalage idempotent |
| `test_lieu_form_client` | formulaire de lieu | capacités ; fusion (`progeniture`, `pnj[1..]`, clés inconnues) |
| `test_connexions_client` | formulaire de connexion | `link:*` écrasé ; clés du doc/nœud perdues ; case posable |
| `test_portes_client` | portes de rempart | ordre des nœuds (porte qui change de côté) ; 5 `_id` ; clés perdues |
| `test_lot_lieux_client` | lot de lieux | N boutiques ⇒ un seul `link:*` ⇒ boutiques sans porte |
| `test_dialogues_client` | `/admin/dialogues` | fusion doc/nœud/choix ; atteignabilité **avec** les nœuds de service |
