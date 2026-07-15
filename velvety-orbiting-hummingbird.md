# Plan — Quêtes de « chasse » (tuer un ennemi à profil élevé dans un lieu précis) + rang de guilde

## Contexte

On ajoute au système de quêtes un nouveau type d'objectif : **traquer et tuer UN ennemi d'une
espèce donnée, marqué d'un profil élevé, dans un lieu précis**. Deux canaux le délivrent :

1. **Le tableau de la guilde** (`categorie:"guilde_aventurier"`) — profil visé = `max−1`.
2. **Le PNJ du comptoir** (`categorie:"guilde_aventurier_comptoir"`, seulement si un PNJ est présent,
   via dialogue) — profil visé = `max`, et **uniquement comme condition de gain de rang**. Le rang est
   propre à la guilde (clé = `lieu_parent` = la cité). Avant le combat de cette variante, une narration
   « c'est sûrement l'ennemi recherché, couvert du sang de ses victimes ».

Le mécanisme central : quand un combat **tire naturellement** l'espèce cible dans le lieu cible, **un
seul** des ennemis de cette espèce se voit forcer le profil de la quête (les autres restent normaux).

### Décisions validées (Q&R + correction)
- **Lieu cible** = la cité (`lieu_parent` de la guilde) **OU un lieu rattaché à elle** (`lieu_parent ==
  cité`), à condition qu'il porte `rencontres` + `zone_influences` contenant l'espèce. (Aujourd'hui seule
  la cité Auxerre remplit ça ; l'ouverture aux enfants est future-proof.)
- **Position `{x,y}` stockée dans l'objectif si le lieu cible a `cells`/`dimensions`** : un point à
  l'intérieur d'une zone d'influence qui contient l'espèce (centre `{x,y}` d'un placement de cette zone,
  intensité > 0). Sert à résoudre le profil et à guider/afficher.
- **Résolution du profil À LA GÉNÉRATION** (pas au combat), à partir : du **lieu cible**, de **cette
  position**, et des **zones d'influence actives à cette position qui contiennent l'espèce**
  (`compute_zone_intensity` + `lieu["rencontres"]`). Le profil résolu (`profil_id`) est **stocké dans
  l'objectif** ; le combat se contente de l'appliquer.
- **« Profil le plus haut possible »** = le plus haut `niveau` parmi les profils issus de la
  **`profil_weights` résolue sur les placements des zones concernées** (somme des `profil_weights` des
  placements des zones contenant l'espèce, sinon `profil_weights` du lieu) — logique identique à
  `_resolve_profil_weights` (`routers/combat.py`), mais appliquée aux placements **contenant la cible** —
  **filtrés** par `restriction_tags ⊆ espece.tags`. Égalité de niveau → tirage au hasard.
- **Board = `max−1`**, **comptoir = `max`**.
- Le profil étant connu à la génération, le titre/description peuvent **nommer le grade** (ex.
  « Traquer le loup Vétéran à Auxerre »).
- **Rang de guilde = prestige/affichage seul (v1)** : stocké par cité, affiché ; aucun effet mécanique
  encore (hooks laissés pour plus tard).
- **Complétion** = mort de l'ennemi **marqué** (celui qui a reçu le profil de la quête), quantité 1.

---

## Modèle de données

### Nouvel objectif `chasse`
```jsonc
"objectif": {
  "type": "chasse",
  "cible": "espece:loup",       // l'espèce à traquer
  "lieu": "lieu:auxerre",       // cité (lieu_parent) OU lieu rattaché à elle
  "position": {"x": 3, "y": 20},// présent si le lieu a cells/dimensions (dans une zone de la cible)
  "profil": "profil:veteran",   // RÉSOLU à la génération, appliqué tel quel au combat
  "quantite": 1
}
```
Le `tier` (`max` / `max_moins_1`) n'est qu'un **paramètre de génération** ; à l'exécution seul
`objectif.profil` compte. `position` est **omis** si le lieu n'a pas de grille.

### Champ personnage (net-new) — rang de guilde
```jsonc
"rangs_guilde": { "lieu:auxerre": "F" }   // clé = cité (lieu_parent), valeur = rang courant
```
Échelle réutilisée : `recrutement.RANGS = ["F","E","D","C","B","A","S"]`. Absent ⇒ rang `F`.

### Marquage combat (transitoire, sur le snapshot monstre)
Le monstre forcé porte `"quete_chasse": "<quete_id>"`. Pour la variante comptoir, le doc combat porte
`"chasse_narration": "<texte>"` (déclenche l'overlay pré-combat).

---

## Partie 1 — Objectif `chasse` : résolution (génération) + application (combat)

### Refactor pur `utils/zones.py` (ou `utils/combat.py`) — extraire la résolution des poids
Le corps de `routers/combat.py::_resolve_profil_weights(active_placements, lieu)` (somme des
`profil_weights` des placements, repli `lieu["profil_weights"]`) est déplacé dans une fonction **pure**
`resolve_profil_weights(placements, lieu)` ; `routers/combat.py` la réutilise (pas de duplication).

### Nouveau module pur `utils/chasse.py` (DB injectée, pattern `utils/transport.py`)
- **Lieux candidats** : `lieux_chasse_de(cite_id, get_doc_fn, find_docs_fn) -> list[dict]` =
  `[cité_doc]` + les enfants (`find_docs({"type":"lieu","lieu_parent":cite_id})`) qui portent
  `rencontres` **et** `zone_influences`.
- **Position dans une zone de la cible** : `position_de_chasse(lieu_doc, espece_doc) -> {x,y}|None` :
  `zones_cibles = { z for r in lieu_doc["rencontres"] if r["espece"]==espece_doc["_id"] for z in r["zones"] }` ;
  `placements = [p for p in lieu_doc["zone_influences"] if p.get("zone") in zones_cibles]` ; `None` si vide,
  sinon `random.choice(placements)` → `{"x": p["x"], "y": p["y"]}` (le **centre** d'un placement, intensité>0).
  Renvoie `None` (position omise) si le lieu n'a pas de `dimensions`.
- **Résolution du profil à la GÉNÉRATION** :
  `resoudre_profil_chasse(lieu_doc, espece_doc, tier, position, get_doc_fn) -> str|None` (`profil_id`) :
  - `zone_defs = load_zone_defs_for_lieu(lieu_doc, get_doc_fn)` (utils/zones).
  - active placements = les placements des `zones_cibles` où `compute_zone_intensity(pos.x, pos.y, p,
    zone_defs[p.zone]) > 0` (repli : tous les placements des `zones_cibles` si pas de position/grille).
  - `pw = resolve_profil_weights(active, lieu_doc)` (pure, §ci-dessus).
  - `possibles = [get_doc_fn(pid) for pid in pw]` (repli : tous les `profil:*` si `pw` vide).
  - `compatibles = [p for p in possibles if p and set(p.get("restriction_tags") or []) <= set(espece_doc.get("tags", []))]`.
  - `None` si vide. Sinon `niv_max = max(niveau)`, `cible_niv = niv_max` (tier `max`) ou `niv_max-1`
    (`max_moins_1`). Candidats = compatibles `niveau==cible_niv` ; à défaut le compatible de niveau le plus
    proche **≤** `cible_niv` (repli : le plus bas). Égalité → `random.choice`. Retourne son `_id`.
- `quetes_chasse_actives(character, lieu_id)` → quêtes actives `type=="chasse"` avec `objectif.lieu==lieu_id`.
- Helpers rang : `rang_de(character, cite_id)`, `rang_suivant(rang)`, `promouvoir(character, cite_id)`
  (mute, sans save), `rang_max_atteint(rang)`.

### Refactor `utils/combat.py` — extraire la construction d'un monstre
Extraire le corps de la boucle `instantiate_monsters` (lignes 666-715) en
**`build_monster_snapshot(espece, profil, idx) -> dict`** (profil `None` = fallback midpoint) ; faire
appeler ce helper par `instantiate_monsters`. But : reconstruire **un** monstre avec un profil forcé sans
dupliquer la dérivation des stats.

### Application dans `routers/combat.py::start_combat`
Après `instantiate_monsters(...)` (ligne ~185) et avant `create_combat_doc` :
- `for q in chasse.quetes_chasse_actives(character, depart_lieu["_id"])` (une passe, un monstre marqué
  par quête, sans re-marquer) :
  - Trouver un `m` de `monstres` avec `m["espece_id"] == q.objectif["cible"]` et sans `quete_chasse`.
  - `profil_doc = get_doc(q.objectif["profil"])` (le profil **déjà résolu à la génération**, appliqué
    tel quel — pas de re-résolution au combat).
  - Si trouvés : remplacer `m` par `combat.build_monster_snapshot(espece_doc, profil_doc, idx_de_m)` en
    conservant `m["id"]`/`pos`, puis `m["quete_chasse"] = q.id`.
  - Si la quête est une quête de rang (`source=="rang"`) : poser `chasse_narration = <texte de la quête>`
    sur le doc combat après `create_combat_doc`.
- Note : on **ne force pas** l'espèce à apparaître (« dès qu'un combat tire l'espèce cible ») ; si elle
  n'est pas tirée, rien n'est marqué.

### Hook de progression — `utils/quetes.py`
Ajouter `maj_progress_chasse(character, monstres)` : pour chaque quête active `type=="chasse"`, si un
monstre mort (`not vivant`) porte `quete_chasse == q.id` → `q["progress"] = q.objectif.quantite`.
L'appeler dans `utils/combat.py::finalize_combat` **juste après** `maj_progress_kills` (ligne ~1947),
donc dans la même fenêtre d'idempotence (garde `combats_recompenses` du principal).

### Affichage — `utils/quetes.py`
- `_cible_nom` : brancher `type=="chasse"` → `_nom_espece(cible)`.
- `quete_detail` : libellé « Traquer l'élite : {espèce} à {lieu} » + progress `0/1 | 1/1`.

### Focalisation — `utils/focalisation.py` (comme le type `kill`)
- Ajouter `"chasse"` à `OBJECTIFS_FOCALISABLES` (ligne 70).
- `focalisation_effective` (ligne 57) : brancher `if t == "chasse" and cible: return {"mode":"kill",
  "espece":cible, "quete_id":f["cible"]}` → **réutilise intégralement la mécanique kill** :
  `espece_weights_focus` (biais du tirage d'espèce → plus de chances de faire apparaître la cible marquée),
  `boost_zone_event`, et `effacer_si_objectif_atteint` (déjà générique : efface au `progress>=1`).
- `payload_client` : label de la cible chasse = `_nom_espece(cible)` (bouton 🎯).
- Rien d'autre : le biais d'espèce est inerte là où l'espèce n'est pas au pool → il n'agit que dans le
  lieu cible, ce qui suffit (pas de guidage séparé, cohérent avec le type `kill`).

---

## Partie 2 — Canal tableau (board)

### `utils/quetes.py::remplir_tableau` (ligne 279-280)
Construire les candidats chasse en **balayant les lieux de chasse** : pour `L in
chasse.lieux_chasse_de(parent_id, get_doc, find_docs)` et chaque `eid in L["rencontres"]`, candidat
`("chasse", (L["_id"], eid))` si `position_de_chasse(L, espece)` **et**
`resoudre_profil_chasse(L, espece, "max_moins_1", position, get_doc)` renvoient non-`None`. Dédup sur la
paire `(type, (lieu, cible))`. (Aujourd'hui `lieux_chasse_de` = juste la cité.)

### `utils/quetes.py::generer_quete`
Brancher `type_obj == "chasse"` (avec `cible = (lieu_id, espece_id)`) :
- `position = chasse.position_de_chasse(lieu_doc, espece_doc)`.
- `profil_id = chasse.resoudre_profil_chasse(lieu_doc, espece_doc, "max_moins_1", position, get_doc)` (skip si `None`).
- `objectif = {type:"chasse", cible:espece_id, lieu:lieu_id, position:position, profil:profil_id, quantite:1}`
  (`position` omis si `None`).
- Titre/description dédiés (`_TITRES_CHASSE`) **nommant le grade** connu, ex. « Traquer le {nom} {grade} à {lieu} ».
- Récompense : `niv = get_doc(profil_id)["niveau"]` ; `xp = _xp_unitaire(espece, niv) * QUETE_CHASSE_XP_FACTEUR` ;
  `cuivre` via `QUETE_CUIVRE_PAR_XP`.

Accept / suivi / turn-in board : **réutilisent tels quels** `POST /quetes/accepter`,
`snapshot_quete` (copie l'`objectif` complet, incluant `lieu`/`tier`), la progression (Partie 1), et
`POST /quetes/terminer` (déjà : `objectif_atteint` + giver == guilde courante).

---

## Partie 3 — Canal comptoir + rang de guilde

Mirroir **simplifié** du chemin authoré transport (`utils/transport.py` + `routers/pnj.py`).

### Offre (générée, délivrée par dialogue)
- `utils/chasse.py::offre_rang_pour(character, comptoir_doc, get_doc, rand_fn)` :
  - Cité = `comptoir_doc["lieu_parent"]`. Rang courant = `rang_de(character, cité)`.
  - `None` si rang max, si une quête de rang de cette cité est déjà active, ou pas de PNJ présent.
  - Sinon tire un couple `(L, espèce)` parmi `lieux_chasse_de(cité, get_doc, find_docs)` × leurs
    `rencontres`, tel que `position_de_chasse(L, espèce)` et `resoudre_profil_chasse(L, espèce, "max",
    position, get_doc)` renvoient non-`None` ; construit une quête `objectif = {type:"chasse", cible,
    lieu:L, position, profil:profil_id, quantite:1}`, `source:"rang"`, `giver = comptoir_id`,
    `lieu_parent = cité`, `rang_vise = rang_suivant(courant)`, `narration = <texte sang des victimes>`.
- **Seed à l'entrée** (comme transport) : dans `main.py` (près de la ligne 538 où
  `poser_transport_offert` est appelé), appeler `chasse.poser_rang_offert(...)` qui persiste un champ
  transitoire `character["rang_offert"] = {lieu, quete}` (re-tiré seulement en ressortant/rentrant).

### Dialogue PNJ — `routers/pnj.py`
- `_contexte` (lignes 64-99) : ajouter les flags booléens `rang_offert`, `rang_a_rapporter`
  (quête de rang de cette cité complétée, `progress>=1`, pas encore soldée), `rang_max`.
- Dispatch service (`pnj_dialogue_choix`, ligne ~255) : nouvelle branche
  `elif action.get("service") == "rang":` avec `op` :
  - `accepter` → `chasse.accepter_rang(character, ...)` : pousse `snapshot_quete(offre)` (avec l'`objectif`
    chasse) dans `quetes_actives`, vide `rang_offert`, save.
  - `rapporter` → `chasse.solder_rang(character, ...)` : vérifie `objectif_atteint`, `promouvoir(character,
    cité)`, applique récompenses (`quetes.appliquer_recompenses`), déplace la quête vers `quetes_terminees`,
    save. (Pas de `retour` de marchandise — juste rendre compte.)
- Placeholders : `{espece}`, `{lieu}`, `{rang}`, `{rang_vise}` via `_substituer`.
- Conditions de choix (`condition:{rang_offert:true}` etc.) fonctionnent sans modif (`condition_ok`
  traite toute clé inconnue comme flag booléen).

### Contenu (jsons/)
Ajouter au PNJ du comptoir (Borin, `pnj:borin_barbe_de_jais`) un bloc **`services.rang`** = `{noeuds:{...}}`
(propose / infos / accepte / en_cours / rapporte / rang_max) + les choix gated dans son `dialogue`.
Nouveau fichier `jsons/rang_guilde_a_importer.json` (doc PNJ mis à jour + éventuels textes). Le texte de
narration « couvert du sang de ses victimes » est porté par l'offre (généré par `offre_rang_pour`), pas
en dur dans un nœud (l'espèce varie).

---

## UI

- **Overlay pré-combat** (`templates/combat_telluris.html`) : si `combat_doc.chasse_narration` présent,
  afficher un overlay narratif non bloquant au chargement du combat (avant le 1er tour), pattern de
  l'overlay d'intro (`#intro-overlay`).
- **Tableau / onglet quêtes** : les quêtes `chasse` s'affichent via le rendu existant (ce sont des
  `quete:*`) ; vérifier `renderFicheQuetes` / `quete_detail` (nom espèce + lieu + `0/1`).
- **Dialogue comptoir** : panneau PNJ existant (`#pnj-panel`), choix gated par flags.
- **Rang affiché** : ligne « Rang de guilde : D » dans le dialogue du comptoir (PNJ) **et** une petite
  entrée dans l'onglet 🤝 Relations (section guilde/lieu de la cité). v1 = lecture seule.

---

## Config (`models/character_stats.py` + `rules:world_variables`)

Nouvelles world-vars (défaut + override, comme les `QUETE_*`) :
- `QUETE_CHASSE_XP_FACTEUR` (ex. 3.0 — l'élite vaut plus qu'un individu normal).
- `QUETE_CHASSE_PROBA_RANG` (ex. 0.5 — proba de tirer une offre de rang à l'entrée du comptoir).
Réutilise `QUETE_CUIVRE_PAR_XP`, `RANGS` (recrutement).

---

## Tests (purs, pattern monkeypatch DB des modules)

- `tests/test_chasse.py` (nouveau) :
  - `position_de_chasse` : renvoie le centre d'un placement d'une zone **contenant** l'espèce ; `None`
    si aucune zone de l'espèce n'est placée.
  - `resoudre_profil_chasse` : ne retient que les zones **actives à la position** et **contenant**
    l'espèce ; filtre `restriction_tags` (lapin sans `magie` → jamais un profil `magie` ; aigle sans
    `distance` → jamais `distance`) ; choix du niveau max / max−1 ; égalité aléatoire (seed) ; repli
    quand `max−1` absent ; `None` si aucun compatible.
  - `resolve_profil_weights` (pur, extrait) : somme des placements, repli lieu.
  - `lieux_chasse_de` : cité + enfants avec `rencontres`+`zone_influences` seulement.
  - `quetes_chasse_actives`, helpers de rang (`promouvoir`, `rang_suivant`, rang max).
  - `offre_rang_pour` : pas d'offre si rang max / quête de rang déjà active.
- `tests/test_combat_groupe.py` (étendre) : `build_monster_snapshot` cohérent avec l'ancien inline ;
  un monstre forcé porte le bon `profil_id`/`niveau`/`quete_chasse`.
- `tests/test_quetes_board.py` (étendre) : `remplir_tableau` émet des candidats `chasse` ;
  `generer_quete("chasse", ...)` a l'objectif attendu.
- `maj_progress_chasse` : la mort du monstre marqué (et lui seul) complète la quête.

Cible : suite complète verte (`pytest tests/`), en tenant compte des 5 échecs pré-existants connus de
`test_character_stats.py` (hors périmètre).

## Fichiers clés à modifier
- `utils/chasse.py` (nouveau) — logique pure : `resoudre_profil_chasse`, `quetes_chasse_actives`,
  offre de rang, helpers rang.
- `utils/zones.py` (ou `utils/combat.py`) — `resolve_profil_weights(placements, lieu)` pur (extrait de
  `routers/combat.py::_resolve_profil_weights`, qui le réutilise).
- `utils/combat.py` — refactor `build_monster_snapshot`, appel `maj_progress_chasse` dans `finalize_combat`.
- `routers/combat.py::start_combat` — application du profil résolu au monstre élite + narration.
- `utils/quetes.py` — `generer_quete`/`remplir_tableau`/`_cible_nom`/`quete_detail` + `maj_progress_chasse`.
- `utils/focalisation.py` — `OBJECTIFS_FOCALISABLES` + `focalisation_effective`/`payload_client` (mode kill).
- `routers/pnj.py` — flags + service `rang` (accepter/rapporter).
- `main.py` — seed `poser_rang_offert` à l'entrée du comptoir.
- `models/character_stats.py` — world-vars chasse/rang ; `routers/user.py` — init `rangs_guilde` à la création.
- `templates/combat_telluris.html` — overlay narration ; `templates/play_town_telluris.html` — affichage rang.
- `jsons/rang_guilde_a_importer.json` (nouveau) — dialogue + service du comptoir.

## Vérification end-to-end
1. `pytest tests/` (logique pure).
2. Import du contenu (`jsons/rang_guilde_a_importer.json`) via l'outil d'admin d'import.
3. `docker compose up` ; en jeu :
   - **Board** : à la guilde, accepter une quête « Traquer … d'élite » ; se déplacer dans le lieu cité
     jusqu'à tirer un combat contenant l'espèce → vérifier qu'**un** monstre a un profil supérieur
     (PV/stats), le tuer, revenir à la guilde, `terminer` → récompense.
   - **Comptoir** : entrer au comptoir avec PNJ présent → dialogue propose la quête de rang → accepter →
     combat avec l'espèce → **overlay narratif** avant le tour → tuer l'élite → revenir au comptoir →
     `rapporter` → rang de la cité incrémenté (affiché).
   - **Tags** : vérifier via `/admin/table` qu'aucune espèce sans tag `magie`/`distance` ne reçoit un
     profil `magie`/`distance`.

## Limitations v1 assumées
- Rang = affichage seul (aucun déblocage mécanique).
- Focalisation 🎯 = biais d'espèce (mode kill), sans guidage séparé vers le lieu.
- Une seule cible marquée par quête et par combat ; furtivité/compagnons non spécifiquement traités.
