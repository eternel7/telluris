---
name: telluris-colonisation
description: Colonisation path — founding a settlement on a country map and growing it from Campement to Ville - site sheet read from the map, guild charter, model places per tier (pure link, grid read through db/config), buildings placed with « Poser ici », named NPC posts, four stocks, derived security and morale, lazy catch-up of elapsed time, territorial threat, status and fortification worksites, other players as visitor / supporter / associate (utils/colonisation.py, routers/colonisation.py, templates/scripts/colonisation.js, dev/gen_colonisation.py, rules:colonisation). Load when working on settlements, including French requests such as « implantation », « campement », « hameau », « fonder », « charte », « palier », « lieu modèle », « associé », « fiche de site ».
---

### Voie de colonisation (`utils/colonisation.py`, `routers/colonisation.py`)

Décisions de l'Auteur : `docs/lore/systemes/20261112_voie_de_colonisation.md` (les § ci-dessous sont les siens). Pendant de la voie urbaine (`telluris-proprietes`).

- **Doc `implantation:<hex12>`** (état de partie, `type:"implantation"`, `categorie:"implantation"`, `lieu_parent` = pays) : `palier`, `modele`, `origine {lieu, pos}`, `lien`, `fondateur` (+ `fondateur_nom`, `fondateur_rang` dénormalisés), `stocks`, `population` (comptée), `feu`, `batiments [{id, type, pos|None, endommage?}]`, `fortifications [id]`, `employes [id]`, `souffrants`, `menace {espece, etape}`, `attaques`, `morts`, `rattrape_at`, `chantier`, `journal`, `soutiens`, `associes`, `demandes`, `candidats`. Relié à sa case du pays par `link:implantation_<hex>` (`metadata.type:"implantation"`, point bleu, visible de tous dès le Campement).
- **Personnage** : `implantations` (index), `association` (une seule), `demande_association` (une seule), `charte_colonie` (une, consommée à la fondation), `colons` (convoi escorté). Absents ⇒ rien.

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
- **Charte** : achetée au bureau d'un maître de guilde (`categorie:"bureau_maitre_guilde"`, bouton « 📜 Charte de colonisation », `GET|POST /colonisation/charte[/acheter]`, `reglages.charte_cuivre`, rang `reglages.rang_min`), attachée à la CITÉ du bureau (`lieu_parent`) ; une à la fois. Elle ne vaut que sur une case dont cette cité est la plus proche (`charte_valable`, dernier test de `peut_fonder`) ; la fondation la consomme.
- Bouton « 🏕️ Fonder une implantation » sur toute carte de pays à qui tient une charte ; la case est jugée à l'ouverture (`GET /colonisation/site`).
- `peut_fonder` : case marchable et sans connexion, ≥ `distance_cite_min` de toute `categorie:"ville"`, ≥ `distance_implantation_min` d'une autre implantation, `implantations_par_pays` par personnage. Distances de Chebyshev, cités lues dans les connexions du pays (`lieux_relies`).
- Le panneau nomme le maître de guilde des cités les plus proches (`cites_de_la_charte`, ex æquo tous).
- `fiche_site` : six axes notés 0-3, LUS à chaque fois (zones qui couvrent la case, tags du pays, cases d'eau, ressources, cités, donjons) — jamais stockés. Mots-clés et libellés : `site` des règles.
- Menace : une espèce rencontrable des zones du site, tirée à la fondation.

#### Dans l'implantation
- `/play` : bouton « 🏕️ » → panneau `#colonie-panel` (`scripts/colonisation.js`), onglets Site · Population · Bâtiments · Défense ; le visiteur n'a que la lecture (site en mots, besoins, dons, demande d'association).
- **Rôles** (`role_de`) : fondateur · associé · soutien (a donné) · visiteur. Seul le personnage PRINCIPAL : aucune route ne lit `compagnon_id`.
- **Bâtiments** (`batiments_def`) : `construire` (fondateur ; cuivre + bois + matériaux) crée le bâtiment SANS case ; `poser` = « Poser ici », sous les pieds, fondateur ou associé ; même geste pour déplacer. Case marchable, hors entrées, une par bâtiment. Repères posés ⇒ marqueurs ajoutés aux `passages` de `/play` (`reperes_carte`, halo `RGB_REPERE`). `catalogue: false` ⇒ jamais construit à la main (maison de guilde).
- **Sous-lieux** (`nature:"sous_lieu"`) : à la PREMIÈRE pose, `lieu:colonie_<hex>` (`type:"lieu"`, `colonie`, `batiment`, `lieu_parent` = l'implantation, forme d'une boutique de cité) + `link:colonie_<hex>` depuis la case (`creer_sous_lieu`) ; poses suivantes et changement de palier ne déplacent que le nœud (`deplacer_sous_lieu`). Métier : `categorie` fixe (auberge, étable) ou choisi à la construction parmi les `familles` d'enseigne (`categories_possibles`, `enseignes_icones.METIERS` relu, marchand générique existant, ni grande maison ni négociant). Image : première `<categorie>_europe*` (ou `image_prefixe`) de `towns/`.
  - Fermé sans PNJ au poste ou endommagé : garde d'ENTRÉE `sous_lieu_ouvert` dans `move_character` (`sans_tenancier` l'épargne). Entrée `pnj` = marchand générique sous le nom du PNJ nommé (`synchroniser_tenanciers` après embauche, renvoi, rattrapage, combat ; étable : `montures_etable`).
  - ⚠️ `marche.est_cite` inclut `type:"implantation"` : ses boutiques partagent SON flux (tick à la visite, nuit), `echanges_cite.cite_de` s'y arrête.
- **Vente de la production** (`echanger`, après chaque rattrapage, au plus `echanges.passes_max`) : surplus d'un stock (au-delà de `surplus_facteur` × seuil bas) des PNJ producteurs (`produit.items`) vendu aux boutiques du lieu, prix du FONDATEUR (`echanges_cite.prix_vente_boutique` via `Contexte.libre`), plus offrant d'abord, `marche.absorber_achat` ; crieur ; recette → `imp.caisse_cuivre` (`caisse_max`, relevée par le fondateur). Comptoir de négoce (repère) : négociant (catégorie `negociant`, `activite`) + `effets_metier` (commis, charretier, teneur, crieur) ; formation et « Tenir les livres » comme en ville. Option par PNJ `vente_cite` (`POST /colonisation/employe/vente`).
- **Personnel nommé** : `employe:*` (machinerie des propriétés : `_candidats_pour`, `creer_employe`), poste = id du bâtiment. Métiers = `rules:proprietes.metiers` + `metiers_def`. Bâtiment endommagé ⇒ postes à l'arrêt (`au_poste`).
- **Repos au feu** : `routers/auberge._acces_nuit` gratuit dans l'implantation (lignes `nuit_feu` par `lieu_de_nuit`) ; ⚠️ les étals tickés sont ceux de l'implantation, jamais du pays. Auberge d'un sous-lieu : remise `remise_auberge` au fondateur et aux associés.
- **Stocks** : nourriture, bois, matériaux, médicaments ; capacité `stockage` (base + entrepôts × rang du palier). Don d'un objet du sac (`POST /colonisation/donner`, tout rôle) : règle `depots` (clés de `filtres_boutique.filtres_item` ou `sous_categories`), unités = poids × `unites_par_kg`. Compté en apports (associé) ou en dons (⇒ soutien), noté au carnet.
- **Sécurité** (`securite`) : cinq familles de 0 à 20, plafond `securite.plafond`. **Moral** (`moral`) : base + facteurs. Dérivés à la lecture ; mots par seuils.
- **Chantiers** (un à la fois) : fortification (bois et matériaux partent à l'ouverture), échelon de guilde, ou statut (seuils du palier suivant atteints : population, postes nommés tenus, fortification `requis_pour`). Versements du fondateur et des associés (`financer`). Fortification payée ⇒ en place ; statut payé ⇒ le fondateur choisit le modèle (`POST /colonisation/palier`) : `changer_palier`, `replacer_batiments`, nœud du lien et personnage sur la première entrée, page rechargée.
- **Association** : demande écrite (`demander`), réponse du fondateur (`repondre`), places `autres_joueurs.associes_max[palier]`, exclusion / départ (apports conservés). ⚠️ On ne mute jamais le `character:*` d'autrui : le doc du LIEU fait foi, `synchroniser_association` rattrape le personnage à son passage (`/play`, `_ici`).

#### La guilde du joueur (§ 9)
- `imp.guilde = {echelon, nom, membres {id: {nom, titre}}, coffre, expeditions}`. Échelons = `guilde.echelons` + `guilde_echelons` (prix, `fonctions` CUMULATIVES : recrutement, expeditions, missions, specialistes, coffre, donjons, defense, attraction). Chantier `genre:"guilde"` (`peut_ouvrir_echelon`, nom au premier) → `achever_guilde` : au premier, maître = fondateur, membres FONDATEURS = associés d'alors, bâtiment `maison_guilde` à poser (sous-lieu `guilde_colonie`, tag `recrutement`, sans tenancier, postes de spécialistes).
- Tableau de recrues : `recrutement.acces_autorise` délègue à `acces_tableau_guilde` dans un sous-lieu de colonie (membres seuls, sans carte). Rejoindre / quitter (`rejoindre`, `quitter_guilde`).
- Expéditions (`envoyer` / `accueillir`) : un membre envoie des compagnons de SON groupe (ni clone) sur une mission ouverte ; ils sortent du groupe (`en_mission`), reviennent à `retour` ; issue tirée à l'accueil (`chance_reussite` : niveaux vs difficulté, maître d'armes) ; récompense au membre moins `commission` (caisse du lieu), XP (archiviste), échec = blessés. Matériel commun : dépôt des membres, retrait du maître et des fondateurs. `defense` relève la défense humaine, `attraction` les arrivées.
- Routes : `/colonisation/guilde[/rejoindre|quitter|envoyer|accueillir|coffre/deposer|coffre/retirer]`, depuis l'implantation OU sa maison de guilde (`_ici_guilde`) ; bouton « 🏰 La guilde » dans la maison.

#### Combats joués (§ 6)
- Présent (fondateur, associé), `attaque_presente` tire au plus une attaque par passe (étape ≥ 2) → `attaque_en_cours` ; « ⚔️ Repousser l'attaque » (`POST /colonisation/defendre`) : combat sur la carte du LIEU (`battle_map` = l'implantation, `map_route` pour l'image), assaillants aux entrées (`placer_assaillants`), gardes au poste à ses côtés (`garde_combattant` → `create_combat_doc(gardes=…)`, `est_garde`, tour serveur `se_defend`). Sans réponse `delai_defense_s`, résolue au rattrapage suivant.
- Tanière (étape 4) : « 🐺 Vider la tanière » (`POST /colonisation/taniere`, fondateur ou associé) sur une battle map du terrain du site ; victoire ⇒ `etape 0` + `nettoyee_at`, expédition réussie ; `repousse_s` plus tard, une autre bête.
- Issue : `combat._finalize_colonie` → `issue_combat` (idempotent par `combats_traites`, AVANT le garde du principal) ; garde tombé = mort pour de bon.

#### Associés (§ 10, suite)
- Prix de faveur : `marche.get_relation` pose `faveur` (recalculée à chaque lecture) sur la relation d'un sous-lieu de colonie ; seul `prix_courant` la lit (`max(value, faveur)`).
- Rangements (`/colonisation/rangements[/deposer|retirer|autoriser]`) : entrepôt commun (capacité des entrepôts debout, dépôt libre, retrait autorisé associé par associé), petit coffre de l'associé (habitation debout).
- Colons : à l'auberge d'une cité à `colons_distance_max` (bouton « 🏕️ Colons », `/colonisation/colons[/recruter]`), convoi `character.colons` (logements libres, `colons_max`) ; installés à l'arrivée (`/play`, `deposer_colons`, compté en apport), dispersés par une défaite (`finalize_combat`) ou au bout de `colons_duree_s`.

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

#### Images et limites
- Lieux modèles génériques : prompts `docs/prompts_images.md` § 6 ; `colonie_<palier>_generique*` posé dans `towns/` ⇒ le générateur bascule l'image du modèle (champ `image` seul) ; grille à refaire dans `/admin/lieux`, `entrees` dans `/admin/table`.
- Les ateliers de colonie sont des boutiques de cité (recettes, flux du lieu) : pas d'atelier « confié » comme dans un bien urbain.
