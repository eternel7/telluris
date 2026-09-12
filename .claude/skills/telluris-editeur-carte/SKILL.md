---
name: telluris-editeur-carte
description: Map editor authoring at /admin/editor (admin_map_editor.html) — the "Lieux" mode (sub-place creation, JSON overlay, door repositioning), the place form with its capabilities (tavern/stable/scriptorium/recruitment/guild) and edit-by-merge, /api/lieux/creation_options, the connection form, rampart-gate pairs, batch shop placement ("lot de lieux" + shop-sign names from utils/enseignes.py), image analysis and route tracing (templates/scripts/voies.js — regions, chokepoints, flow map, A/B paths, min cut), and grid resizing. Load whenever you touch admin_map_editor.html, voies.js, utils/capacites.py, utils/enseignes.py or utils/grille_image.py, or when populating a city with shops, doors or connections — even if the request only says "ajouter des boutiques", "relier deux lieux", "poser une porte" or "la carte a un trou".
---

Écrire la carte du monde depuis `/admin/editor`. Marcher dedans (règles de pas, pavé partagé, mode test de déplacement) : **telluris-map-movement**.

**Patron commun** — `PUT /admin/doc` et `POST /admin/import-bulk` font un PUT **COMPLET** et ne refusent rien (`_rev` rattaché en base, CLAUDE.md §11). Tout formulaire part donc du doc **RELU**, n'écrit que les champs qu'il possède (`_fusionLieu`, `_fusionConnexion`) et refuse un `_id` déjà pris **avant** l'envoi. Fusions, conventions d'`_id`, ordre des nœuds et seuils de case sont verrouillés par `dev/test_{lieu_form,connexions,portes,lot_lieux,voies,resize}_client.js` : ce qui suit garde le pourquoi et ce qu'aucun harnais n'atteint (DOM, visée, séquencement réseau). ✕ / Échap annulent sans rien écrire (CLAUDE.md §8).


### Mode « Lieux »
Points cliquables aux positions des connexions du lieu courant. `GET /api/lieu/{id}/connections` = range sur la vue `reseau/liens_cases`, chaque nœud enrichi de `details` (doc lieu sans `cells`/`_rev`/`_id`). ⚠️ **Ne peint jamais la grille** ; le clic sélectionne la case (`lieuxSelectedCell`) et filtre la liste latérale. Fiche `#lieu-fiche-overlay` = réplique de play_town (image `towns→battle_maps→maps`, sous-lieux `.lf-subbtn`, destinations sans `cells` en image fit).

- Sélecteur de mode = `<select id="mode-select">`, `setMode` seul writer d'`editMode`. ⚠️ `updateBattleMapTabs` pose `hidden` **ET `disabled`** sur les options Zones/Rencontres/Ressources — Safari ignore `hidden` sur une option.
- **`🧾 JSON`** → `#lj-overlay`, panneau **fixe à droite** (pas un modal : la carte reste cliquable). 💾 `PUT /admin/doc`, 🗑 `DELETE /admin/doc?id=` (porte et boutique = deux gestes). ⚠️ `node.details` est **retiré** avant affichage et écriture (`_connNu`), sinon la copie enrichie du lieu serait persistée dans la connexion. ⚠️ Connexion **re-résolue par `_id` à chaque rendu** : `fetchLieuxConnections` remplace le tableau, l'objet d'ouverture porterait un `_rev` périmé → 409.
- **`🎯` Repositionner une porte** (éditeur JSON) : le clic suivant réécrit la `pos` du nœud **qui porte le lieu courant** et **enregistre aussitôt** (mutation dans la zone de texte, puis `sauverDocJson`). Fills de terrain rallumés le temps de la visée. Case acceptée = **`_caseAccessible` (`>= 1`)**, source unique du voile rouge, du cadre et du refus ; un clic refusé laisse l'outil armé. ⚠️ `lieuxSelectedCell` suit la nouvelle case **avant** le save (la liste filtrée perdrait la connexion) et l'outil est désarmé **avant l'`await`**. Désarmement dans tous les chemins de sortie (✕, `setMode`, changement de lieu, suppression, Échap **avant** la fermeture).
- ⚠️ **Écart assumé** : `>= 1` est le prédicat de `combat._walkable` (guidage 🧭) alors que les flèches de play_town exigent `loc_access === 1`. Une porte sur terrain 2/3/5 est posable mais inatteignable aux flèches — d'où l'alerte terrain du formulaire de connexion.


### Formulaire de lieu — création, capacités, édition par FUSION
`➕` (`#lieu-add-overlay`) crée, `✏️ Éditer` rouvre le **même** formulaire pré-rempli par `GET /api/lieu/{id}` ; `_docsNouveauLieu` passe par `_fusionLieu({}, …)`, création et édition ont donc la même forme. Écrit le `lieu:<slug du label>` **puis** son `link:<categorie><NN>_to_<parent>` — ⚠️ **le lieu d'abord** : une connexion orpheline fait échouer l'enrichissement `details`. Une boutique n'a ni `dimensions` ni `cells`, donc n'apparaît pas au sélecteur de lieux (`get_lieux_ids` filtre sur `cells`).

- `_fusionLieu` n'écrit que `label`, `image`, `categorie`, `tags`, `pnj`, `nuit_messages`. `pnj` est une **liste** : fusion dans `[0]` (`character`/`nom`/`portrait`/`montures`), tout le reste survit (`progeniture` = chaînes d'escorte). Retirer un PNJ porteur de `progeniture` ou d'écurie demande une **confirmation**.
- ⚠️ `_id` **gelé** (CouchDB ne renomme pas, la connexion pointe l'ancien) ; label libre. `metadata.type` de la connexion n'est pas retouché (lu par aucun code) : l'édition n'écrit qu'un doc.
- **Tenancier** déduit en `pnj:marchand_<categorie>` ; ⚠️ bloc PNJ coché d'office **seulement si ce doc existe** (`_nlTenancierDefaut`) — sinon référence morte (`auberge` et 15 autres catégories). `nom`/`portrait` vides **non écrits** : `pnj_payload` retombe sur le doc PNJ (portrait générique `marchand_<race>_<sexe>_<cat>.png` sans nom ; nommé `marchand_<prenom>_<nom>_<cat>.png` en donne un).
- ⚠️ **Nommage des images NON dérivable de la catégorie** (`laboratoire_d_alchimie` → `cabinet_alchimie_*.png`, `fletcher` → `archerie_*.png`) : filtre par recouvrement de jetons, repli sur la liste complète — ne jamais le durcir en préfixe. Fichier réel absent du filtre ⇒ « toutes les images » coché d'office (sinon « Image requise » sur un lieu qui en a une).
- **Capacités** (catalogue `creation_options.capacites`, cf. CLAUDE.md § Capacités d'un lieu) : accordée par la **catégorie** ⇒ cochée **et grisée** (aucun anti-tag n'existe) ; tag redondant non posé.
- **Auberge** = doc le plus dépouillé du jeu : la catégorie (ou le tag) suffit, seul champ propre optionnel `nuit_messages`. ⚠️ **Aucun tenancier** : aucun code d'auberge ne lit `lieu.pnj[]` et `pnj:marchand_auberge` n'existe pas.
- **Étable** : ⚠️ l'écurie vit sur le **tenancier** (`pnj[0].montures`) — `lieu_vend_montures` seul ouvre le bouton sur un rayon vide. Picker filtré sur le tag d'espèce `monture` (celles qui portent `charge_mult`/`prix_cuivre`).


### `GET /api/lieux/creation_options`
Source unique des formulaires (admin) : catégories (`lieu.categorie` ∪ `recette.lieu_categorie`), fichiers `towns`/`pnj`, docs `pnj:*`, `lieu_ids`, `capacites`, `lieux` projetés (`_id`, `categorie`, `image`, `lieu_parent`, `label`). ⚠️ `lieu_ids` porte le contrôle de collision parce que `GET /api/lieu/{id}` ne le peut pas : son 404 est levé *dans* son propre `try/except Exception` et ressort en **500**. ⚠️ `find_docs` **projetés** (`fields=[...]`), sinon on rapatrie les `cells` de chaque carte.


### Formulaire de connexion
`🔗 Connexion` (sur une ligne) → `#conn-overlay`, même géométrie que `#lj-overlay` (ouvrir l'un ferme l'autre). N'écrit **qu'un** `link:*` ; la ligne de liste montre `_id`, `status` et les deux positions. ⚠️ **La création générique n'existe plus** (le bouton a cédé la place à « 🏰 Ajouter une porte de rempart ») ; `openConnForm` garde son mode `'creation'`, dont l'édition se sert pour pré-remplir.

- ⚠️ Anti-écrasement : la liste **complète** des `_id` est lue à chaque ouverture sur `GET /admin/table/data?type=connection` (`lieuxConnections` ne voit que le lieu courant), `_cxIdPropose` suffixe. Lecture échouée ⇒ le formulaire **le dit** plutôt que de laisser croire au garde-fou.
- `_fusionConnexion` fusionne les nœuds **par position** : `champs.noeuds` dans l'ordre du doc (`cxIciIdx`). Label vidé = **supprimé** (`get_lieu_links` doit replier sur le label du lieu).
- Case : `_cxPosPosable` (`>= 1` s'il y a une grille ; `cells` absent ⇒ aucune règle, le `[0,0]` des boutiques). Ici éprouvée sur la grille **en cours d'édition**, là-bas sur les `cells` du doc de destination (`lieuxDocCache`).
- **Alerte terrain ≠ 1** (`_lieuxHorsTerrain`, bandeau `#lieux-terrain-alerte` + anneau rouge pointillé) : prédicat **différent** (`!== 1`), avertissement et non refus.
- ⚠️ La visée 🎯 écrit **dans le formulaire**, pas en base ; le panneau passe en **`pointer-events:none`** le temps du geste (il couvre la moitié droite de la carte), son ✕ est donc inerte — Échap est rappelé dans la barre de statut. Refusée hors mode Lieux ; formulaire refusé pendant un **aperçu de redimensionnement** ; fermé dans tous les chemins de sortie.
- `_id` gelé en édition ; la destination reste modifiable (l'`_id` ne la suit pas).


### Porte de rempart — une PAIRE, cinq documents
`categorie: "Porte de rempart"` (5 paires en base, toutes à Auxerre). Un lieu **extérieur** + un **intérieur**, chacun relié à une case de la cité, + le **passage** : 2 `lieu:*` + 3 `connection` en un `import-bulk`. « 🏰 Ajouter une porte de rempart » crée, « 🏰 Porte » rouvre la paire. Forme exacte des cinq docs (aucune grille, nœuds porte en `[0,0]`, `metadata.type` = « poste de garde », label « au-delà des remparts » sur le seul nœud carte extérieur, convention d'`_id` neuve non rétro-appliquée) : **`dev/test_portes_client.js`**.

- Les deux cases **carte** doivent différer et passer le voile rouge. ⚠️ L'éditeur ne peut pas vérifier qu'elles sont du bon **côté** du mur : c'est l'œil de l'auteur (le tracé des voies aide).
- ⚠️ `_ptOrdonner` remet les nœuds dans l'ordre du **doc** avant `_fusionConnexion` : fusion par position, permuter changerait la porte de côté en silence.
- `_ptPaireDe` lit **`cxDocsConnus`**, pas `lieuxConnections` : le passage n'a aucun nœud sur la cité. Côté indécidable ⇒ **refus d'ouvrir** plutôt qu'intervertir.
- ⚠️ `_ptRepeuplerImages(voulues)` reçoit la valeur en **paramètre**, jamais relue du DOM : affecter `.value` sur un `<select>` encore vide ne prend pas (« image requise » sur une porte qui en avait une). L'image courante reste offerte même si un autre lieu la porte.


### Lot de lieux — peupler une ville
Poser N boutiques sans écrire un `dev/gen_magasins_<ville>.py` de plus. **Maj+clic** empile des cases (une par boutique, l'ordre compte), `➕ Ajouter un lot` ouvre le tableau : composition à gauche (métier + quantité, avec l'existant de la cité), lignes à droite (enseigne 🎲, image, portrait). Une seule requête `import-bulk`.

- Docs écrits = **ceux de `dev/gen_magasins_auxerre.py`** (`lieu:<slug>` + connexion, stocks vides garnis au premier `tick_atelier`). Générateur = contenu **authoré** (items/recettes exclusifs) ; lot = contenu de **remplissage**. Un lot ne pose ni capacité ni champ propre.
- ⚠️ `_prochainLinkId(…, dejaPris)` : le compteur dérive de `lieuxConnections`, immobile tant que rien n'est écrit — sans `dejaPris`, N boutiques d'un métier partageraient un `link:*` et toutes sauf une seraient **sans porte, sans erreur**. `_lotDocs` n'écrit `pnj` que si le tenancier générique existe.
- Un `_id` déjà en base **refuse le lot** avant l'envoi. Après écriture, `creationOptions = null` (périmé, il laisserait recréer ce qu'on vient de poser).
- Retouches manuelles indexées sur **`<categorie>#<rang>`**, jamais sur l'index de ligne.
- **Enseignes** : `utils/enseignes.py` (pur, `rand_fn` injecté), `POST /api/lieux/enseignes`. Ville neuve ⇒ `TOPONYMES_DEFAUT` ; l'enrichir se fait dans ce seul fichier.


### Analyse d'image — grille proposée et tracé des voies
Carte « 🔍 Analyse d'image » : **Proposer une grille** (`utils/grille_image.py`, CLI `dev/gen_grille_image.py`) et **Tracer les voies** — où l'on circule vraiment (trou de rempart, gué, enclave). Calcul `templates/scripts/voies.js`, rendu `_voiesDessiner` dans `renderGrid`.

- ⚠️ **LECTURE SEULE** (ni base ni `grid`). Source = la **proposition si elle est affichée**, sinon la grille en base : on juge avant ✔ Appliquer.
- ⚠️ **`pasAutoriseRegle(regle, …)`** (deplacement.js) est le prédicat de pas UNIQUE des voies et du mode test : voies.js ne recopie aucune règle.
- Vues : **régions** (rang 0 = principale en vert discret, enclaves en teintes vives) + **goulots** (points d'articulation d'importance `>= VOIES_GOULOT_MIN`, cerclés magenta) ; ou **carte de passage** (Brandes échantillonné). Une brèche de 2 cases n'a pas de goulot : c'est la carte de passage qui la montre. ⚠️ Pas **non pondérés** : le surcoût ×2/×5 du terrain difficile n'y entre pas.
- ⚠️ **Péremption** : `voiesSignature` comparée à chaque rendu ; tracé périmé ⇒ **pas dessiné** (« ↻ Recalculer »). Changer de lieu le ferme.
- **Directions nav près des murs** (`voiesDirectionsNav`) : trait vert = autorisé, tiret rouge = fermé **par nav seule** (le terrain prime).
- **A/B** : visée interceptée **en tête** de `mousedown`/`touchstart` (ne peint rien), refusée si le tracé est périmé ou qu'une visée Lieux est armée ; A/B survivent à ↻. Jusqu'à `#voies-nb-chemins` (1-8, 3 par défaut) chemins : le plus court puis des variantes par **PÉNALITÉ** — jamais par retrait de cases, qui tuait toute variante dès un passage obligé (74 % des paires à 1 chemin sur Auxerre). Plus la **coupe minimale** (`voiesCoupeMin`) : la brèche de 2-3 cases qu'aucun goulot ne montre ; sort la coupe la plus proche de A, et `collee` signale une coupe faite **uniquement de voisines** de A (elle entoure le point au lieu de fermer le rempart).
- **En mode test de déplacement**, `#dep-open-btn` devient « 🛤️ Tracer / ↻ Recalculer les voies » (`_depOpenBtnMaj`, `depOpenBtnClic`) ; ⚠️ le tracé suit alors la règle **du jeton** (`depReglesCombat` → `#voies-regle-combat`), comptes dans la barre de statut.


### Redimensionner la grille (carte 📐)
Rééchantillonnage **au plus proche voisin** de `dimensions`, `cells`, `nav`, zones d'influence et portes. Carte `#dim-card`, masquée sans grille chargée. Fonctions pures du template (`_resizeMatrice`, `_resizeNav`, `_resizeZones`, `_resizePos`, `_caseLibreProche`…) ; côté serveur `utils.lieux.dimensions_coherentes` (422, `tests/test_lieu_dimensions.py`).

- **Deux temps, un écrivain** : `↔ Appliquer` = état client seul ; `💾` = les écritures ; `↺ Annuler` relit. ⚠️ **Auto-sauvegarde du pinceau SUSPENDUE** pendant l'aperçu (`scheduleGridSend`, `debounceTimer` désarmé) — sinon `cells` neuves sous anciennes `dimensions`.
- ⚠️ **Écritures séquentielles, jamais `Promise.all`** : (1) `PUT /api/update_cells` avec `dimensions` (autoritative), (2) `PUT /api/lieu/{id}/zone_influences`, (3) un `PUT /admin/doc` par connexion déplacée. (1) et (2) font chacune `get_doc → mutation → save_doc` sur le même doc.
- ⚠️ **Non recalés** : `position` des personnages présents, `intro.position_depart`, `objectif.position` des quêtes en cours, `combat:*` ouvert sur la carte. Plafond `DIM_MAX` = 512 par axe.
