---
name: telluris-db
description: CouchDB access layer and raw-document admin tools — reading live values from the committed dump, targeted exports (/admin/exports), the table editor /admin/table (PUT/DELETE /admin/doc, JSON/Excel export via utils/xlsx.py), full-PUT write semantics of admin_import_bulk and PUT /admin/doc, the per-request document cache (RequestDocCacheMiddleware, _CACHEABLE_PREFIXES in db/config.py) and the process-level market caches cleared by reset_prix_cache. Load when touching db/config.py or the middleware stack in main.py, adding a new document prefix/type, chasing a slow endpoint (too many get_doc), editing admin_table.html or the exports, or when an import "has no visible effect".
---

Couche CouchDB (`db/config.py`) et outils d'admin qui lisent ou écrivent des docs bruts. Règles transverses : CLAUDE.md §4 (aucune migration) et §11 (import).


### Lire les valeurs réelles
CouchDB live distante, injoignable en local : lire **`telluris-dump-*.json`** à la racine (produit par `GET /admin/exports/couchdb` / `db.config.dump_all_docs()`). ⚠️ L'export téléchargé **inclut les `user:*`** (restauration à l'identique, `_dump_payload(avec_users=True)`) — les retirer avant de committer, ou prendre **`GET /admin/exports/couchdb-sans-users`** (carte « Dump committable »), qui rend le même dump que les outils de dev/ : format et filtrage dans **`utils/dump.py`** (`payload`, `ecrire_dump_frais`), source unique. ⚠️ Plusieurs dumps coexistent : prendre le plus récent, et recompter dessus avant d'annoncer un trou de données.

- **Dump → branche + PR** : `POST /admin/exports/dump-pr` → `serveur.publier_dump` : dump sans `user:*` commité en `jsons/telluris-dump-*.json` sur une **nouvelle** branche `admin/dump-AAAAMMJJ-HHMMSS` partant du `main` distant (plomberie + index temporaire : ⚠️ ni checkout ni fichier écrit dans l'arbre — un dump non suivi dans `jsons/` ferait refuser la mise à jour ff-only suivante), push, PR vers `main` via l'API GitHub (`GITHUB_TOKEN`, passé à git par `GIT_CONFIG_*`, jamais l'argv). Échec de la PR ≠ échec : branche poussée + `compare_url`. Push **retenté** (pauses `PAUSES_PUSH`) sur échec transitoire seul (`_push_transitoire` : 5xx GitHub, coupure réseau ; un 403 n'est pas retenté) ; abandon → branche locale supprimée, l'export suivant repart propre. Verrou partagé avec la mise à jour. Verrouillé par `tests/test_serveur.py`.
- **Export d'un type** : `GET /admin/exports/by-type?type=<t>` (`find_docs({"type": t})`, sans `user:*`) → `<type>-AAAAMMJJ-HHMMSS.json` ; `/admin/exports` liste les types présents.


### Éditeur en tableau — `/admin/table` (`admin_table.html`)
Docs d'un type en tableau (colonnes choisies/ordonnées par drag, tri, filtres, largeurs), données `GET /admin/table/data?type=<t>`. Clic sur une ligne → JSON dans un overlay fixe à droite : **Save** `PUT /admin/doc`, **Delete** `DELETE /admin/doc?id=…` après `confirm()` (ligne retirée localement, sans rechargement du type).

- ⚠️ `_rev` **relu en base**, jamais celui du client. `db.delete_doc` renvoie `None` en succès comme en échec ⇒ le serveur vérifie par **relecture** → 409.
- Préférences d'affichage **par type** dans `localStorage` (`telluris.admin_table.v1.<type>`).
- **Colonnes calculées** (✧) : servies À CÔTÉ des docs (`calcules: {_id: {col: val}}`), jamais dedans — un Save les persisterait. Potentiels du simulateur (`espece`/`character`) ; `node_inexistant` (`connection`, `main._colonnes_calculees`, relu après un Save ; absent si l'existence des lieux est illisible). Exclues de l'export Excel.
- **Exports** des lignes **affichées** (`computeVisibleRows` : filtres + tri) : ⬇ JSON (docs complets) et ⬇ Excel (`POST /admin/table/export.xlsx` → `utils/xlsx.py`, writer OOXML stdlib partagé avec le bestiaire ; une colonne par clé de 1er niveau, imbriqué en JSON). Nom `exportFilename(ext)` = `<type>_filtre_<col>_<val>…_AAAAMMJJ-HHMMSS`, horodatage **UTC** aligné sur les exports serveur.


### Écrire : PUT complet, partout
`admin_import_bulk` et `PUT /admin/doc` remplacent le doc **entier** et ne refusent rien (`_rev` rattaché depuis la base) : un `_id` réutilisé écrase en silence, une clé absente disparaît. D'où les générateurs qui relisent le dump (**telluris-admin-tools**) et les formulaires d'admin qui fusionnent le doc relu (**telluris-editeur-carte**, `/admin/dialogues`).

⚠️ En fin d'écriture, un doc `type ∈ {recette, item, lieu}` déclenche `marche.reset_prix_cache()` — sans quoi une recette importée n'a aucun effet visible jusqu'au redémarrage.


### Cache de documents (requête + process)
`get_doc` = un aller-retour HTTP ; une seule vente en faisait 200 à 350 (le même `item:*` relu). **`RequestDocCacheMiddleware`**, monté dans `main.py` après `SessionMiddleware`, mémorise par requête les préfixes de **contenu** (`_CACHEABLE_PREFIXES`) ; tout ce qui porte un état de partie (`character:`, `aventurier:`, `lieu:`, `combat:`, `quete:`, `table:`, `message:`…) en est exclu, car lu/muté/sauvé dans la même requête. Comportement (hit/miss, whitelist, copie de surface, invalidation, kill-switch `TELLURIS_DOC_CACHE=0`) : `tests/test_doc_cache.py`.

- ⚠️ **Middleware ASGI PUR, jamais `@app.middleware("http")`** : `BaseHTTPMiddleware` exécute l'aval dans une tâche anyio distincte, le `ContextVar` ne se propage plus.
- ⚠️ Le `ContextVar` est posé **par le middleware et nulle part ailleurs** ; `get_doc` ne fait que **muter** l'objet stocké. Un endpoint `def` tourne en threadpool avec une **copie** du contexte : la copie partage l'objet (les mutations portent), un `set()` fait depuis le thread serait perdu.
- ⚠️ Copie de **surface** : une mutation imbriquée d'un doc servi par le cache se voit aux lectures suivantes de la même requête.
- Un nouveau préfixe de doc se **classe explicitement** : contenu (`_CACHEABLE_PREFIXES`) ou état (tout le reste).
- **Contenu → aussi au cache de PROCESS** (`_process_cache`, stocké picklé, TTL `TELLURIS_PROCESS_CACHE_TTL` = 300 s) : servi d'une requête à l'autre, copie profonde à l'entrée de chaque requête (une mutation imbriquée ne déborde jamais de sa requête). Invalidé par `save_doc`/`delete_doc` **même hors contexte** (écritures /admin) et **après** le `put` (compteur de génération : une lecture concurrente ne repose pas l'ancienne version). ⚠️ Une édition faite HORS de l'app (Fauxton) met jusqu'au TTL à se voir ; seules les requêtes de jeu le lisent (/admin, tests, scripts lisent la base).
- **Docs d'ÉTAT (tout préfixe hors contenu) → mémo de REQUÊTE à copie PROFONDE** (`_get_doc_profond`) : chaque lecture rend ce qu'aurait rendu CouchDB (mutation non sauvée invisible, `save_doc` invalide) ; jamais au cache de process. Seul écart : l'écriture d'une AUTRE requête pendant celle-ci n'est pas vue (le `save_doc` suivant part en 409 au lieu d'écraser). Né des relectures en boucle (225 lectures de 3 lieux par achat via `resolve_item_ref`, `user:3/1` à chaque action).
- **`find_docs` sur un `type` de contenu → cache de PROCESS** (`_process_finds`, même TTL) : le catalogue des compétences et des sorts n'est plus retransféré à chaque payload de fiche. Vidé EN ENTIER à toute écriture d'un doc de contenu. Les recherches d'état (`lieu`, `relation`, `character`…) partent toujours en base.
- **`save_docs(docs)`** : écriture groupée (`_bulk_docs`), un aller-retour pour N docs, `_rev` posé, caches invalidés, un booléen par doc, **sans transaction** — docs annexes seulement (étals de la nuit d'auberge, recrues périmées). Un module qui l'importe doit la patcher dans les fixtures (cf. `test_auberge_endpoints`).
- **Lire N lieux connus** : `marche._lieux_par_id(ids, champs)` — une requête projetée (`type` + `$in`) au lieu de N `get_doc` (onglet 🤝 de /play).
- **Relevé par requête** (logger `telluris.db`, journal du conteneur) : `POST /api/buy_item — 840 ms (base 610 ms) | get:… hit:… find:… save:… | lus lieu:31/4 relation:12/1`. `base` = temps cumulé des allers-retours CouchDB : proche du total ⇒ trop de lectures ; loin ⇒ calcul Python. `lus` = lectures parties en base / docs distincts, par préfixe (lectures ≫ docs ⇒ un même doc relu). Point de départ de toute chasse à la lenteur. Relevé du 09/10 (NAS) : **~10 ms par aller-retour**, la base fait ~95 % du temps.


### Caches process (`utils/marche.py`)
Durée de vie = le process : **recettes** (`_all_recettes` → `_recipe_map` / `_marche_map` / `lieu_recettes`), **fusion de catégories** (`_categories_incluses_memo`, `_recettes_fusion_memo`), **portée géographique** (`_portees_memo`, `_marche_map_portee`, `_recettes_par_portee`), **route d'image d'un lieu** (`_lieu_image_route`, par nom de fichier — aucun endpoint d'upload, le disque ne bouge pas à chaud).

Tous vidés par **`reset_prix_cache()`**, appelé au chargement des variables de monde **et** après import/PUT d'un doc `recette`/`item`/`lieu` (`lieu` : la chaîne d'ancêtres est mémoïsée, rebrancher une cité doit prendre effet). Un nouveau mémo du marché doit y être vidé.

Hors marché, deux mémos à **TTL** (pas de vidage explicite, périmés seuls) : `focalisation.charger_graphe` (graphe des connexions) et `scriptorium._sujets_documentables` (60 s, par `lieu_parent` — le tick d'un scriptorium relisait toute la cité à chaque achat).
