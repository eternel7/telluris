---
name: telluris-colonisation
description: Colonisation path — founding a settlement on a country map and growing it from Campement to Ville - site sheet read from the map, guild charter, model places per tier (pure link, grid read through db/config), buildings placed with « Poser ici », named NPC posts, four stocks, derived security and morale, lazy catch-up of elapsed time, territorial threat, status and fortification worksites, other players as visitor / supporter / associate (utils/colonisation.py, routers/colonisation.py, templates/scripts/colonisation.js, dev/gen_colonisation.py, rules:colonisation). Load when working on settlements, including French requests such as « implantation », « campement », « hameau », « fonder », « charte », « palier », « lieu modèle », « associé », « fiche de site ».
---

### Voie de colonisation (`utils/colonisation.py`, `routers/colonisation.py`)

Décisions de l'Auteur : `docs/lore/systemes/20261112_voie_de_colonisation.md` (les § ci-dessous sont les siens). Pendant de la voie urbaine (`telluris-proprietes`).

- **Doc `implantation:<hex12>`** (état de partie, `type:"implantation"`, `categorie:"implantation"`, `lieu_parent` = pays) : `palier`, `modele`, `origine {lieu, pos}`, `lien`, `fondateur` (+ `fondateur_nom`, `fondateur_rang` dénormalisés), `stocks`, `population` (comptée), `feu`, `batiments [{id, type, pos|None, endommage?}]`, `fortifications [id]`, `employes [id]`, `souffrants`, `menace {espece, etape}`, `attaques`, `morts`, `rattrape_at`, `chantier`, `journal`, `soutiens`, `associes`, `demandes`, `candidats`. Relié à sa case du pays par `link:implantation_<hex>` (`metadata.type:"implantation"`, point bleu, visible de tous dès le Campement).
- **Personnage** : `implantations` (index), `association` (une seule), `demande_association` (une seule). Absents ⇒ rien.

#### Lien PUR au lieu modèle (§ 12.3) — ⚠️ point unique dans `db/config.py`
- L'implantation ne porte que `modele`. `get_doc` pose `CHAMPS_MODELE` (`image`, `dimensions`, `cells`, `nav`, `entrees`) sur l'exemplaire lu (`suivre_modele`) ; `save_doc` / `save_docs` les retirent de ce qui part en base (`sans_modele`). Tout le moteur lit donc la grille comme celle d'un lieu ordinaire.
- Limité au préfixe `implantation:`. ⚠️ `find_docs` ne suit PAS le modèle (un balayage n'a pas de grille).
- Un modèle n'est jamais écrit en jeu. Verrouillé par `tests/test_colonisation.py` § Lien pur et `test_fonder_cree_…sans_recopier_la_grille`.

#### Lieux modèles (§ 12.1, § 12.2)
- `lieu:*` tagué `modele_colonie` + l'id du palier + milieux éventuels + `pays_<slug>` éventuel ; champ `entrees [[x, y], …]` (1 à 4, la première = arrivée). Sans autre tag que ces deux-là ⇒ GÉNÉRIQUE.
- `modeles_proposes` : recouvrement de tags décroissant, générique en dernier ; modèles propres au pays ⇒ seuls proposés (+ générique). Tags de référence : ceux du site à la fondation (`tags_site` : zone, pays, `pays_<slug>`), ceux du modèle ACTUEL à la montée.
- Vignette écartée si le modèle est injouable (`modele_valide`) ou son image absente du disque.
- Livrés : sept génériques `lieu:modele_colonie_<palier>` — images PROVISOIRES, grille ouverte sans mur. Vraie image + vraie grille : `/admin/lieux` ; `entrees` : `/admin/table`.

#### Fonder (§ 2, § 3)
- Bouton « 🏕️ Fonder une implantation » sur toute carte de pays à qui tient `reglages.rang_min` (meilleur rang, toutes cités) ; la case est jugée à l'ouverture (`GET /colonisation/site`).
- `peut_fonder` : case marchable et sans connexion, ≥ `distance_cite_min` de toute `categorie:"ville"`, ≥ `distance_implantation_min` d'une autre implantation, `implantations_par_pays` par personnage. Distances de Chebyshev, cités lues dans les connexions du pays (`lieux_relies`).
- Charte `reglages.charte_cuivre`, payée sur place ; le panneau nomme le maître de guilde des cités les plus proches (`cites_de_la_charte`, ex æquo tous).
- `fiche_site` : six axes notés 0-3, LUS à chaque fois (zones qui couvrent la case, tags du pays, cases d'eau, ressources, cités, donjons) — jamais stockés. Mots-clés et libellés : `site` des règles.
- Menace : une espèce rencontrable des zones du site, tirée à la fondation.

#### Dans l'implantation
- `/play` : bouton « 🏕️ » → panneau `#colonie-panel` (`scripts/colonisation.js`), onglets Site · Population · Bâtiments · Défense ; le visiteur n'a que la lecture (site en mots, besoins, dons, demande d'association).
- **Rôles** (`role_de`) : fondateur · associé · soutien (a donné) · visiteur. Seul le personnage PRINCIPAL : aucune route ne lit `compagnon_id`.
- **Bâtiments** (`batiments_def`) : `construire` (fondateur ; cuivre + bois + matériaux) crée le bâtiment SANS case ; `poser` = « Poser ici », sous les pieds, fondateur ou associé ; même geste pour déplacer. Case marchable, hors entrées, une par bâtiment. Repères posés ⇒ marqueurs ajoutés aux `passages` de `/play` (`reperes_carte`, halo `RGB_REPERE`).
- **Personnel nommé** : `employe:*` (machinerie des propriétés : `_candidats_pour`, `creer_employe`), poste = id du bâtiment. Métiers = `rules:proprietes.metiers` + `metiers_def`. Bâtiment endommagé ⇒ postes à l'arrêt (`au_poste`).
- **Stocks** : nourriture, bois, matériaux, médicaments ; capacité `stockage` (base + entrepôts × rang du palier). Don d'un objet du sac (`POST /colonisation/donner`, tout rôle) : règle `depots` (clés de `filtres_boutique.filtres_item` ou `sous_categories`), unités = poids × `unites_par_kg`. Compté en apports (associé) ou en dons (⇒ soutien), noté au carnet.
- **Sécurité** (`securite`) : cinq familles de 0 à 20, plafond `securite.plafond`. **Moral** (`moral`) : base + facteurs. Dérivés à la lecture ; mots par seuils.
- **Chantiers** (un à la fois) : fortification (bois et matériaux partent à l'ouverture) ou statut (seuils du palier suivant atteints : population, postes nommés tenus, fortification `requis_pour`). Versements du fondateur et des associés (`financer`). Fortification payée ⇒ en place ; statut payé ⇒ le fondateur choisit le modèle (`POST /colonisation/palier`) : `changer_palier`, `replacer_batiments`, nœud du lien et personnage sur la première entrée, page rechargée.
- **Association** : demande écrite (`demander`), réponse du fondateur (`repondre`), places `autres_joueurs.associes_max[palier]`, exclusion / départ (apports conservés). ⚠️ On ne mute jamais le `character:*` d'autrui : le doc du LIEU fait foi, `synchroniser_association` rattrape le personnage à son passage (`/play`, `_ici`).

#### Le temps (§ 1, § 6)
- `rattraper` : une passe par `temps.passe_s`, au plus `reglages.rattrapage_max_s` ; reliquat conservé ; déclenché par la présence du fondateur ou d'un associé (`/play`, `GET /colonisation/ici`). Événements ⇒ carnet + toasts.
- Une passe (`_passe`) : production (métier × `facteur_axe` du site) → consommation → réparation (bâtisseur) → santé → population → menace.
- Menace : étapes 1 → 4 ; dès 2, attaque résolue d'après la sécurité (`_attaque`) — blessés, morts, réserves, bâtiment endommagé, incendie, jamais le lieu. Mort d'un PNJ nommé : définitive (`statut:"mort"`), les comptés partent d'abord.
- ⚠️ Hasard injecté (`rand`) dans tous les tests.

#### Fuites à ne pas rouvrir
- `lieux.get_lieu_links` réduit une implantation à `CHAMPS_PUBLICS` (`details_publics`) : carnet et réserves ne partent pas au client d'un visiteur.
- `vue` : le visiteur n'a que des mots ; verrouillé par `test_le_visiteur_lit_en_mots_…` et `dev/test_colonisation_client.js`.

#### Données et tests
- `rules:colonisation` ; tout bloc absent retombe sur `colonisation.DEFAUTS`. `dev/gen_colonisation.py` relit le dump, n'ajoute que les blocs et modèles qui manquent → `jsons/colonisation_moteur_a_importer.json`.
- `tests/test_colonisation.py` (pur + générateur), `tests/test_colonisation_endpoints.py`, `dev/test_colonisation_client.js`.

#### Pas encore en jeu
- Sous-lieux où l'on entre (boutique, atelier, auberge, étable : au catalogue, refusés par `NATURES_OUVERTES`) et leurs échanges ; l'implantation n'est donc pas encore une `marche.est_cite`.
- Attaque jouée en combat quand le fondateur est présent ; tanière à vider (étape 4) ; nuit et repos au feu.
- Guilde du joueur (§ 9). Colons escortés, coffre d'associé, prix de faveur (§ 10).
- Formulaire d'édition de `entrees` dans l'éditeur.
