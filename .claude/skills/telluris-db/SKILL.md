---
name: telluris-db
description: CouchDB access layer and raw-document admin tools — reading live values from the committed dump, targeted exports (/admin/exports), the table editor /admin/table (PUT/DELETE /admin/doc, JSON/Excel export via utils/xlsx.py), full-PUT write semantics of admin_import_bulk and PUT /admin/doc, the per-request document cache (RequestDocCacheMiddleware, _CACHEABLE_PREFIXES in db/config.py) and the process-level market caches cleared by reset_prix_cache. Load when touching db/config.py or the middleware stack in main.py, adding a new document prefix/type, chasing a slow endpoint (too many get_doc), editing admin_table.html or the exports, or when an import "has no visible effect".
---

Couche CouchDB (`db/config.py`) et outils d'admin qui lisent ou écrivent des docs bruts. Règles transverses : CLAUDE.md §4 (aucune migration) et §11 (import).


### Lire les valeurs réelles
CouchDB live distante, injoignable en local : lire **`telluris-dump-*.json`** à la racine (produit par `GET /admin/exports/couchdb` / `db.config.dump_all_docs()`), `docs` sans `user:*`. ⚠️ Plusieurs dumps coexistent : prendre le plus récent, et recompter dessus avant d'annoncer un trou de données.

- **Export d'un type** : `GET /admin/exports/by-type?type=<t>` (`find_docs({"type": t})`, sans `user:*`) → `<type>-AAAAMMJJ-HHMMSS.json` ; `/admin/exports` liste les types présents.


### Éditeur en tableau — `/admin/table` (`admin_table.html`)
Docs d'un type en tableau (colonnes choisies/ordonnées par drag, tri, filtres, largeurs), données `GET /admin/table/data?type=<t>`. Clic sur une ligne → JSON dans un overlay fixe à droite : **Save** `PUT /admin/doc`, **Delete** `DELETE /admin/doc?id=…` après `confirm()` (ligne retirée localement, sans rechargement du type).

- ⚠️ `_rev` **relu en base**, jamais celui du client. `db.delete_doc` renvoie `None` en succès comme en échec ⇒ le serveur vérifie par **relecture** → 409.
- Préférences d'affichage **par type** dans `localStorage` (`telluris.admin_table.v1.<type>`).
- **Exports** des lignes **affichées** (`computeVisibleRows` : filtres + tri) : ⬇ JSON (docs complets) et ⬇ Excel (`POST /admin/table/export.xlsx` → `utils/xlsx.py`, writer OOXML stdlib partagé avec le bestiaire ; une colonne par clé de 1er niveau, imbriqué en JSON). Nom `exportFilename(ext)` = `<type>_filtre_<col>_<val>…_AAAAMMJJ-HHMMSS`, horodatage **UTC** aligné sur les exports serveur.


### Écrire : PUT complet, partout
`admin_import_bulk` et `PUT /admin/doc` remplacent le doc **entier** et ne refusent rien (`_rev` rattaché depuis la base) : un `_id` réutilisé écrase en silence, une clé absente disparaît. D'où les générateurs qui relisent le dump (**telluris-admin-tools**) et les formulaires d'admin qui fusionnent le doc relu (**telluris-editeur-carte**, `/admin/dialogues`).

⚠️ En fin d'écriture, un doc `type ∈ {recette, item, lieu}` déclenche `marche.reset_prix_cache()` — sans quoi une recette importée n'a aucun effet visible jusqu'au redémarrage.


### Cache de documents à portée REQUÊTE
`get_doc` = un aller-retour HTTP ; une seule vente en faisait 200 à 350 (le même `item:*` relu). **`RequestDocCacheMiddleware`**, monté dans `main.py` après `SessionMiddleware`, mémorise par requête les préfixes de **contenu** (`_CACHEABLE_PREFIXES`) ; tout ce qui porte un état de partie (`character:`, `aventurier:`, `lieu:`, `combat:`, `quete:`, `table:`, `message:`…) en est exclu, car lu/muté/sauvé dans la même requête. Comportement (hit/miss, whitelist, copie de surface, invalidation, kill-switch `TELLURIS_DOC_CACHE=0`) : `tests/test_doc_cache.py`.

- ⚠️ **Middleware ASGI PUR, jamais `@app.middleware("http")`** : `BaseHTTPMiddleware` exécute l'aval dans une tâche anyio distincte, le `ContextVar` ne se propage plus.
- ⚠️ Le `ContextVar` est posé **par le middleware et nulle part ailleurs** ; `get_doc` ne fait que **muter** l'objet stocké. Un endpoint `def` tourne en threadpool avec une **copie** du contexte : la copie partage l'objet (les mutations portent), un `set()` fait depuis le thread serait perdu.
- ⚠️ Copie de **surface** : une mutation imbriquée d'un doc servi par le cache se voit aux lectures suivantes de la même requête.
- Un nouveau préfixe de doc se **classe explicitement** : contenu (cacheable) ou état (exclu).


### Caches process (`utils/marche.py`)
Durée de vie = le process : **recettes** (`_all_recettes` → `_recipe_map` / `_marche_map` / `lieu_recettes`), **fusion de catégories** (`_categories_incluses_memo`, `_recettes_fusion_memo`), **portée géographique** (`_portees_memo`, `_marche_map_portee`, `_recettes_par_portee`), **route d'image d'un lieu** (`_lieu_image_route`, par nom de fichier — aucun endpoint d'upload, le disque ne bouge pas à chaud).

Tous vidés par **`reset_prix_cache()`**, appelé au chargement des variables de monde **et** après import/PUT d'un doc `recette`/`item`/`lieu` (`lieu` : la chaîne d'ancêtres est mémoïsée, rebrancher une cité doit prendre effet). Un nouveau mémo du marché doit y être vidé.
