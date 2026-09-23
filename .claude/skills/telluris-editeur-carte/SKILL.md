---
name: telluris-editeur-carte
description: Map editor authoring at /admin/editor (admin_map_editor.html) — the "Lieux" mode (sub-place creation, JSON overlay, door repositioning), the place form with its capabilities (tavern/stable/scriptorium/recruitment/guild) and edit-by-merge, /api/lieux/creation_options, the connection form, rampart-gate pairs, batch shop placement ("lot de lieux" + shop-sign names from utils/enseignes.py), image analysis and route tracing (templates/scripts/voies.js — regions, chokepoints, flow map, A/B paths, min cut), and grid resizing. Load whenever you touch admin_map_editor.html, voies.js, utils/capacites.py, utils/enseignes.py or utils/grille_image.py, or when populating a city with shops, doors or connections — even if the request only says "ajouter des boutiques", "relier deux lieux", "poser une porte" or "la carte a un trou".
---

Écrire la carte du monde depuis `/admin/editor`. Marcher dedans (règles de pas, pavé partagé, mode test de déplacement) : **telluris-map-movement**.

**Patron commun** — `PUT /admin/doc` et `POST /admin/import-bulk` font un PUT **COMPLET** et ne refusent rien (`_rev` rattaché en base, CLAUDE.md §11). Tout formulaire part donc du doc **RELU**, n'écrit que les champs qu'il possède (`_fusionLieu`, `_fusionConnexion`) et refuse un `_id` déjà pris **avant** l'envoi. Fusions, conventions d'`_id`, ordre des nœuds et seuils de case sont verrouillés par `dev/test_{lieu_form,connexions,portes,guilde,lot_lieux,voies,resize}_client.js` : ce qui suit garde le pourquoi et ce qu'aucun harnais n'atteint (DOM, visée, séquencement réseau). ✕ / Échap annulent sans rien écrire (CLAUDE.md §8).


### Parts partagées et contrat `LIEUX_HOTE`
Ligne de liste, fiche 📄, éditeurs 🧾 JSON, formulaires ✏️ lieu et 🔗 connexion vivent dans **`part-lieux-{js,css,markup}.html`**, inclus (`include`, pas `import` : `url_for`) par `/admin/editor` et `/admin/lieux`. Porte de rempart, lot, repositionnement, voies restent dans l'éditeur.
- ⚠️ La part ne lit **aucune** globale de page : tout passe par `const LIEUX_HOTE` que chaque page déclare (clés `LIEUX_HOTE_REQUIS`, doc en tête de la part). `visee`/`repositionnement` à `null` masquent 🎯 ; `caseCourante()` null interdit la création. Verrouillé par `test_gestion_lieux_client.js` (clés des deux pages, liste de globales interdites).
- Scripts : la part JS est incluse **avant** le script de page (qui déclare `LIEUX_HOTE`), le markup **après**. `lieuxLigneHtml(conn, ici, {link, porte, ouvert})` = la ligne unique des deux pages.
- Harnais : lire les templates par `dev/_template_js.js` (includes développés).


### Gestion des lieux — `/admin/lieux`
Tableau des connexions d'une ville (`GET /api/lieu/{ville}/connections`), logique de `/admin/table` recopiée (colonnes, tri, filtres, largeurs ; `localStorage` `telluris.admin_lieux.v1`). 1re colonne fixe = `lieuxLigneHtml` sans `link:` ni 🏰. Villes = `dev_tools.est_ville`.
- **🛠 Outils** (à droite au-dessus du tableau) = catalogue `portee: "lieux"` de `utils/dev_tools.py` (cf. `telluris-admin-tools`). `lieux` = les lignes **affichées** (filtres compris) dont la 1re entrée `pnj` est un `pnj:marchand_*` explicite (`lieuxMarchandsVisibles`).
- **📍 Compléter les positions** (spec de magasins) : `voiesRegions(voiesGraphe(cells, nav, dims, 'exploration'))` → région **0** seule ; `_proposerCases` préfère ≤ `PROPOSITION_RAYON` d'une porte de boutique, puis le plus loin des portes du même métier et des cases déjà proposées. `gen_magasins.py` refuse ensuite toute case ≠ 1.
- **📥 Importer** : `GET /admin/dev-tools/sortie` puis `POST /admin/import-bulk` (NDJSON), `confirm` listant les `_id` ; bouton masqué après import.


### Mode « Lieux »
Points cliquables aux positions des connexions du lieu courant. `GET /api/lieu/{id}/connections` = range sur la vue `reseau/liens_cases`, chaque nœud enrichi de `details` (doc lieu sans `cells`/`_rev`/`_id`). ⚠️ **Ne peint jamais la grille** ; le clic sélectionne la case (`lieuxSelectedCell`) et filtre la liste latérale. Fiche `#lieu-fiche-overlay` = réplique de play_town (image `towns→maps→battle_maps`, l'ordre du jeu, sous-lieux `.lf-subbtn`, destinations sans `cells` en image fit).

- Sélecteur de mode = `<select id="mode-select">`, `setMode` seul writer d'`editMode`. ⚠️ `updateBattleMapTabs` pose `hidden` **ET `disabled`** sur les options Zones/Rencontres/Ressources — Safari ignore `hidden` sur une option.
- **`🧾 JSON`** → `#lj-overlay`, panneau à droite (pas un modal : la carte reste cliquable), **déplaçable** par son titre comme `#conn-overlay` (`height` et non `bottom`). 💾 `PUT /admin/doc`, 🗑 `DELETE /admin/doc?id=` (porte et boutique = deux gestes). ⚠️ `node.details` est **retiré** avant affichage et écriture (`_connNu`), sinon la copie enrichie du lieu serait persistée dans la connexion. ⚠️ Connexion **re-résolue par `_id` à chaque rendu** : `fetchLieuxConnections` remplace le tableau, l'objet d'ouverture porterait un `_rev` périmé → 409.
- **`🎯` Repositionner une porte** (éditeur JSON) : le clic suivant réécrit la `pos` du nœud **qui porte le lieu courant** et **enregistre aussitôt** (mutation dans la zone de texte, puis `sauverDocJson`). Fills de terrain rallumés le temps de la visée. Case acceptée = **`_caseAccessible` (`>= 1`)**, source unique du voile rouge, du cadre et du refus ; un clic refusé laisse l'outil armé. ⚠️ `lieuxSelectedCell` suit la nouvelle case **avant** le save (la liste filtrée perdrait la connexion) et l'outil est désarmé **avant l'`await`**. Désarmement dans tous les chemins de sortie (✕, `setMode`, changement de lieu, suppression, Échap **avant** la fermeture).
- ⚠️ **Écart assumé** : `>= 1` est le prédicat de `combat._walkable` (guidage 🧭) alors que les flèches de play_town exigent `loc_access === 1`. Une porte sur terrain 2/3/5 est posable mais inatteignable aux flèches — d'où l'alerte terrain du formulaire de connexion.


### Formulaire de lieu — création, capacités, édition par FUSION
`➕` (`#lieu-add-overlay`) crée, `✏️ Éditer` rouvre le **même** formulaire pré-rempli par `GET /api/lieu/{id}` ; `_docsNouveauLieu` passe par `_fusionLieu({}, …)`, création et édition ont donc la même forme. Écrit le `lieu:<slug du label>` **puis** son `link:<categorie><NN>_to_<parent>` — ⚠️ **le lieu d'abord** : une connexion orpheline fait échouer l'enrichissement `details`. Une boutique n'a ni `dimensions` ni `cells`, donc n'apparaît pas au sélecteur de lieux (`get_lieux_ids` filtre sur `cells`).

- `_fusionLieu` n'écrit que `label`, `image`, `categorie`, `tags`, `pnj`, `nuit_messages`.
- **PNJ du lieu** = une carte repliable par entrée `pnj`, dans l'ordre du lieu (▲▼ ; la 1re = nom annoncé à distance). ⚠️ Chaque ligne garde **`src`**, l'indice de son entrée dans le doc **relu** — jamais son `character` (4 × `pnj:marchand_cuisine` au Garde-manger des 3 fées). `_fusionPnjEntrees` part d'un clone de `existantes[src]` et n'écrit que `character`/`nom`/`portrait`/`probabilite`/`conditions`/`montures` : `progeniture`, `description`, `image` suivent leur entrée, même déplacée ; une valeur inchangée n'est pas réécrite. Verrouillé par `test_lieu_form_client.js` (dont « ouvrir puis enregistrer rend des entrées identiques »).
- **Vue inverse**, lecture seule : « Aussi présent dans » (`_lieuxDuPnj` sur `creation_options.lieux[].pnj`) ouvre l'autre lieu dans ce même formulaire, confirmation si modifié — un seul doc écrit. ⚠️ Un `pnj:marchand_*` tient aussi, implicitement, les boutiques de sa catégorie sans `pnj` (`transport.entree_marchand`).
- **Doublon de `character`** : averti, jamais refusé. La 1re entrée VISIBLE l'emporte (`inerte` derrière une entrée sans condition), mais le tirage retente un PNJ qui a raté le sien — `_probaPersonne` le compte.
- **Conditions de présence** : constructeur généré depuis `creation_options.conditions` (`acces.vocabulaire_conditions`, jamais recopié) ; une clause non représentable sans perte (`_clauseRepresentable`) reste une carte JSON intacte ; `{ } JSON` par ligne. Enregistrement bloqué par `_clausesFautives` (ce que `acces._clause_remplie` rendrait faux pour toujours) et par les fautes `pnj[i]…` de `POST /admin/lint-dialogues` — linter injoignable ⇒ **dit**, pas bloquant. ⚠️ La frappe ne redessine jamais (focus volé, clic avalé au blur) : seuls les `<select>`/cases et les boutons le font.
- Enregistrer = **un** `confirm` récapitulant les pertes : progéniture d'une entrée retirée, écurie vidée, PNJ joignable nulle part ailleurs.
- ⚠️ `_id` **gelé** (CouchDB ne renomme pas, la connexion pointe l'ancien) ; label libre. `metadata.type` de la connexion n'est pas retouché (lu par aucun code) : l'édition n'écrit qu'un doc.
- **Tenancier** déduit en `pnj:marchand_<categorie>` ; ⚠️ ligne de tenancier proposée d'office (`auto` : suit la catégorie tant qu'on n'y touche pas) **seulement si ce doc existe** (`_nlTenancierDefaut`) — sinon référence morte (`auberge` et 15 autres catégories). `nom`/`portrait` vides **non écrits** : `pnj_payload` retombe sur le doc PNJ (portrait générique `marchand_<race>_<sexe>_<cat>.png` sans nom ; nommé `marchand_<prenom>_<nom>_<cat>.png` en donne un).
- ⚠️ **Nommage des images NON dérivable de la catégorie** (`laboratoire_d_alchimie` → `cabinet_alchimie_*.png`, `fletcher` → `archerie_*.png`) : filtre par recouvrement de jetons, repli sur la liste complète — ne jamais le durcir en préfixe. Fichier réel absent du filtre ⇒ « toutes les images » coché d'office (sinon « Image requise » sur un lieu qui en a une). Le formulaire de lieu lit **`images_lieu`** (`{fichier: route}`, `lieux.images_de_lieu` : towns → maps → battle_maps, premier dossier gagnant, recopie de `marche._IMAGE_ROUTES` verrouillée par `tests/test_lieux.py`) — une salle de donjon porte une battle map ; vignette servie depuis la route, origine affichée hors `towns`. ⚠️ `images` (façades `towns/` seules) reste la source du lot, des portes et de la guilde.
- **Capacités** (catalogue `creation_options.capacites`, cf. CLAUDE.md § Capacités d'un lieu) : accordée par la **catégorie** ⇒ cochée **et grisée** (aucun anti-tag n'existe) ; tag redondant non posé.
- **Auberge** = doc le plus dépouillé du jeu : la catégorie (ou le tag) suffit, seul champ propre optionnel `nuit_messages`. ⚠️ **Aucun tenancier** : aucun code d'auberge ne lit `lieu.pnj[]` et `pnj:marchand_auberge` n'existe pas.
- **Étable** : ⚠️ l'écurie vit sur **une entrée `pnj`** (« Tenue par » ; relue comme l'union de toutes les entrées, ce que vend `montures.especes_offertes`) — `lieu_vend_montures` seul ouvre le bouton sur un rayon vide. Picker filtré sur le tag d'espèce `monture` (celles qui portent `charge_mult`/`prix_cuivre`).


### Section 🏰 Donjon du formulaire de lieu
En **édition** d'une battle map **à grille** (`_djSectionActive` ; ✎ Modifier le lieu de la carte ⚔️). Une salle ne sait pas à quel donjon elle appartient : c'est le doc `donjon:*` qui la revendique (`battle_maps[].lieu`, cf. telluris-quetes-pnj § Donjons). Enregistrer écrit donc le **lieu d'abord** (tag `donjon`, `acces` simple) **puis** le ou les donjons, **relus juste avant** (`_djEcrire`, `GET /admin/table/data?type=donjon`) : une autre salle a pu modifier le même donjon. Fusions et refus : **`dev/test_donjon_form_client.js`** (dont « ouvrir puis enregistrer » sur la mine et la grotte : aucun doc ne change).

- Salle décochée ⇒ l'ancien donjon perd la salle ; ni tag ni `acces` ne bougent. Changer de donjon ⇒ le nouveau la reçoit **puis** l'ancien la perd (double revendication passagère sans effet : le premier gagne). Donjon neuf ⇒ `donjon:<slug du nom>`, refusé si pris. Doc identique à sa base ⇒ pas écrit.
- **« Réservée » = tag `donjon`** : exclut la salle des combats aléatoires ET est exigé d'un étage — forcée en mode étages. À l'ouverture, elle dit ce qui EST (⚠️ `grotte_en_foret` n'a pas le tag : elle sert aussi de décor aléatoire).
- Bornes vides = **héritées** (clé retirée) ; une valeur égale n'est pas réécrite. Plancher > plafond : averti, pas refusé (le moteur fait céder le plancher).
- **Porte gardée simple** = `gardien`, `refus`, `cycle` (1) et la clause de la mine (commission de chasse active sur CETTE salle, bureau de maître, non accomplie). ⚠️ Tout autre bloc (`ou`, `rang_min`, autre salle…) est **personnalisé** (`_accesEstSimple`, clés comparées triées) : lecture seule, jamais réécrit ni retiré — c'est le cas de la grotte. La commission reste dans `/admin/dialogues`.
- **Passages** (mode étages) : lus dans `cxDocsConnus` (chargé à l'ouverture d'une battle map), classés étage/surface comme `passages_de_l_etage`, alerte sans sortie (`_djSortieExiste`). ➕ / ✏️ ferment le formulaire (confirm si modifié) et ouvrent le **formulaire de connexion** — `openConnForm('creation', null, {dest, type:'passage'})` présélectionne la destination (`_djPassageSuggere` : étage non relié, puis portail) et dérive l'`_id`. Offerts **seulement sur la carte courante** (la visée 🎯 vise SA grille, et exige le mode Lieux).


### `GET /api/lieux/creation_options`
Source unique des formulaires (admin) : catégories (`lieu.categorie` ∪ `recette.lieu_categorie`), fichiers `towns`/`pnj`, docs `pnj:*`, `lieu_ids`, `capacites`, `lieux` projetés (`_id`, `categorie`, `image`, `lieu_parent`, `label`, + `pnj` = résumé `pnj.resume_presences` : `character`, `nom`, `probabilite`, `conditionne` — ni progéniture ni description), `conditions` (`acces.vocabulaire_conditions`, aussi servi à `/admin/dialogues`), `especes` (`_id`, `nom`) et `donjons` (docs entiers) pour la section 🏰. ⚠️ `lieu_ids` porte le contrôle de collision parce que `GET /api/lieu/{id}` ne le peut pas : son 404 est levé *dans* son propre `try/except Exception` et ressort en **500**. ⚠️ `find_docs` **projetés** (`fields=[...]`), sinon on rapatrie les `cells` de chaque carte.


### Formulaire de connexion
`🔗 Connexion` (sur une ligne) → `#conn-overlay`, même géométrie que `#lj-overlay` (ouvrir l'un ferme l'autre), mais **déplaçable** par sa barre de titre (`rendreDeplacable`, `scripts/deplacable.js` chargé par les DEUX pages hôtes) — d'où `height` et non `bottom` : ancré haut et bas, il se tasserait au premier glisser. N'écrit **qu'un** `link:*` ; la ligne de liste montre `_id`, `status` et les deux positions. ⚠️ **La création générique n'existe plus** (le bouton a cédé la place à « 🏰 Ajouter une porte de rempart ») ; `openConnForm` garde son mode `'creation'`, dont l'édition se sert pour pré-remplir.

- ⚠️ Anti-écrasement : la liste **complète** des `_id` est lue à chaque ouverture sur `GET /admin/table/data?type=connection` (`lieuxConnections` ne voit que le lieu courant), `_cxIdPropose` suffixe. Lecture échouée ⇒ le formulaire **le dit** plutôt que de laisser croire au garde-fou.
- `_fusionConnexion` fusionne les nœuds **par position** : `champs.noeuds` dans l'ordre du doc (`cxIciIdx`). Label vidé = **supprimé** (`get_lieu_links` doit replier sur le label du lieu).
- Case : `_cxPosPosable` (`>= 1` s'il y a une grille ; `cells` absent ⇒ aucune règle, le `[0,0]` des boutiques). Ici éprouvée sur la grille **en cours d'édition**, là-bas sur les `cells` du doc de destination (`lieuxDocCache`).
- **Alerte terrain ≠ 1** (`_lieuxHorsTerrain`, bandeau `#lieux-terrain-alerte` + anneau rouge pointillé) : prédicat **différent** (`!== 1`), avertissement et non refus.
- ⚠️ La visée 🎯 écrit **dans le formulaire**, pas en base ; le panneau passe en **`pointer-events:none`** le temps du geste (il couvre la moitié droite de la carte), son ✕ est donc inerte — Échap est rappelé dans la barre de statut. Refusée hors mode Lieux ; formulaire refusé pendant un **aperçu de redimensionnement** ; fermé dans tous les chemins de sortie.
- `_id` gelé en édition ; la destination reste modifiable (l'`_id` ne la suit pas).
- **Connexion INTERNE** (🔀 « Relier deux cases de cette carte », panneau Lieux) : deux nœuds sur la carte courante — escalier, trappe. Même formulaire en mode `cxInterne` (lu sur le doc en édition, `_connInterne`) : pas de destination, **deux visées 🎯** (`cxViseeCote`), cases distinctes et **deux labels requis** (`_cxValider` — sinon deux boutons au nom du lieu), `_id` `link:<lieu>_<x2>_<y2>_to_<lieu>_<x1>_<y1>` (`_cxIdInterne`). En jeu : `lieux.noeud_destination` (move_character : l'autre bout, ni barrière `acces` ni descente de donjon ; tout le reste est un déplacement réel) et `buildLocationslist` (play_town : l'extrémité qui n'est pas ma case) ; miroir client `_connAutreBout` (points, alerte terrain, mode test). Le 🧾 JSON n'offre PAS le doc lieu (ce serait un PUT complet de la carte) ni 🎯 Repositionner.


### Porte de rempart — une PAIRE, cinq documents
`categorie: "Porte de rempart"` (5 paires en base, toutes à Auxerre). Un lieu **extérieur** + un **intérieur**, chacun relié à une case de la cité, + le **passage** : 2 `lieu:*` + 3 `connection` en un `import-bulk`. « 🏰 Ajouter une porte de rempart » crée, « 🏰 Porte » rouvre la paire. Forme exacte des cinq docs (aucune grille, nœuds porte en `[0,0]`, `metadata.type` = « poste de garde », label « au-delà des remparts » sur le seul nœud carte extérieur, convention d'`_id` neuve non rétro-appliquée) : **`dev/test_portes_client.js`**.

- Les deux cases **carte** doivent différer et passer le voile rouge. ⚠️ L'éditeur ne peut pas vérifier qu'elles sont du bon **côté** du mur : c'est l'œil de l'auteur (le tracé des voies aide).
- ⚠️ `_ptOrdonner` remet les nœuds dans l'ordre du **doc** avant `_fusionConnexion` : fusion par position, permuter changerait la porte de côté en silence.
- `_ptPaireDe` lit **`cxDocsConnus`**, pas `lieuxConnections` : le passage n'a aucun nœud sur la cité. Côté indécidable ⇒ **refus d'ouvrir** plutôt qu'intervertir.
- ⚠️ `_ptRepeuplerImages(voulues)` reçoit la valeur en **paramètre**, jamais relue du DOM : affecter `.value` sur un `<select>` encore vide ne prend pas (« image requise » sur une porte qui en avait une). L'image courante reste offerte même si un autre lieu la porte.


### Maison de guilde — une étape par geste
`categorie: "guilde_aventurier_exterieur"` ⇒ « 🏛️ Guilde » sur la ligne (`opts.guilde`, éditeur seul). Chaîne façade → réception → comptoir → bureau du maître, calquée sur le Bastion d'Auxerre ; chaque geste écrit **l'étape suivante seule** (lieu + connexion au maillon précédent, nœuds `[0,0]`) en un `import-bulk`, puis rouvre le panneau sur la suivante. Forme exacte des docs : **`dev/test_guilde_client.js`**.

- `_gdChaine` suit les voisins **par catégorie** dans `cxDocsConnus` (aucun maillon n'a de nœud sur la cité). Deux candidats pour un maillon ⇒ **refus** ; connexions illisibles ⇒ refus d'ouvrir (la chaîne ne se devine pas, on rebâtirait une réception).
- `_id` = `lieu:<façade sans _exterieur><suffixe>` : redonne `_interieur`/`_comptoir` du Bastion ; `_bureau_du_maitre` est neuf.
- ⚠️ Le bureau n'a **pas** de `sous_categorie` (utils/recrutement.py § Maison de guilde) ; aucun tag `recrutement` (la catégorie l'accorde).
- **`relation_lieu` → comptoir** : créer le comptoir **réécrit** façade et réception (relues **fraîches**, `_gdLireFrais`, clone + ce seul champ) ; le bureau le reçoit et répare un maillon qui ne l'aurait pas. Valeur déjà posée, même divergente : **jamais écrasée**, signalée.
- `acces` du bureau : `gardien` = 1re entrée `pnj` du comptoir relu (omis sinon : informatif), `rang_min {cite: lieu_parent, rang}` pris dans `creation_options.conditions.rangs`. ⚠️ Sans dialogue qui pose un laissez-passer, seul le rang ouvre.
- **🧾 JSON par maillon** : `#lj-overlay` s'ouvre **par-dessus** le panneau (z-index 60 > 59), qui reste dessous. `toggleSousLieuJson(…, {horsListe:true})` ne ferme pas les autres panneaux et résout la connexion dans `cxDocsConnus` (`_ljConnexion`), **relu après 💾/🗑** (sinon `_rev` périmé ⇒ 409). Façade = sa connexion à la carte ; maillon = celle au précédent ; doublon = chaque candidat. 🎯 masqué sur une connexion sans nœud sur la carte. Échap ferme le JSON avant le panneau.
- ⚠️ Un 💾 JSON pendant que le panneau est ouvert ⇒ `gdPerime` : la création **relit** la maison au lieu d'écrire (sinon `gdRelus` périmé réécrirait la façade sans la retouche).


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
- **Directions nav près des murs** (`voiesDirectionsNav`) : tiret rouge = fermé **par nav seule** (le terrain prime). `autorisees` reste calculé (harnais) mais **n'est plus dessiné**.
- **A/B** : visée interceptée **en tête** de `mousedown`/`touchstart` (ne peint rien), refusée si le tracé est périmé ou qu'une visée Lieux est armée ; A/B survivent à ↻. Jusqu'à `#voies-nb-chemins` (1-8, 3 par défaut) chemins : le plus court puis des variantes par **PÉNALITÉ** — jamais par retrait de cases, qui tuait toute variante dès un passage obligé (74 % des paires à 1 chemin sur Auxerre). Plus la **coupe minimale** (`voiesCoupeMin`) : la brèche de 2-3 cases qu'aucun goulot ne montre ; sort la coupe la plus proche de A, et `collee` signale une coupe faite **uniquement de voisines** de A (elle entoure le point au lieu de fermer le rempart).
- **En mode test de déplacement**, `#dep-open-btn` devient « 🛤️ Tracer / ↻ Recalculer les voies » (`_depOpenBtnMaj`, `depOpenBtnClic`) ; ⚠️ le tracé suit alors la règle **du jeton** (`depReglesCombat` → `#voies-regle-combat`), comptes dans la barre de statut.


### Redimensionner la grille (carte 📐)
Rééchantillonnage **au plus proche voisin** de `dimensions`, `cells`, `nav`, zones d'influence et portes. Carte `#dim-card`, masquée sans grille chargée. Fonctions pures du template (`_resizeMatrice`, `_resizeNav`, `_resizeZones`, `_resizePos`, `_caseLibreProche`…) ; côté serveur `utils.lieux.dimensions_coherentes` (422, `tests/test_lieu_dimensions.py`).

- **Deux temps, un écrivain** : `↔ Appliquer` = état client seul ; `💾` = les écritures ; `↺ Annuler` relit. ⚠️ **Auto-sauvegarde du pinceau SUSPENDUE** pendant l'aperçu (`scheduleGridSend`, `debounceTimer` désarmé) — sinon `cells` neuves sous anciennes `dimensions`.
- ⚠️ **Écritures séquentielles, jamais `Promise.all`** : (1) `PUT /api/update_cells` avec `dimensions` (autoritative), (2) `PUT /api/lieu/{id}/zone_influences`, (3) un `PUT /admin/doc` par connexion déplacée. (1) et (2) font chacune `get_doc → mutation → save_doc` sur le même doc.
- ⚠️ **Non recalés** : `position` des personnages présents, `intro.position_depart`, `objectif.position` des quêtes en cours, `combat:*` ouvert sur la carte. Plafond `DIM_MAX` = 512 par axe.
