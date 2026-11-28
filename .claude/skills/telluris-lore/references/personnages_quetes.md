# Personnages et trame des quêtes

⚠️ Les races, noms et descriptions **en jeu** sont dans le dump (`pnj:*`, champ `description`) : ils priment sur les fiches des séances. Écrire un dialogue importable relève de **telluris-quetes-pnj** (arbre de dialogue, `jsons/pnj-*.json`, linter).

## PNJ établis (dump du 08/10/2026)

| `_id` | Nom | Lignée · fonction | Rôle narratif |
|---|---|---|---|
| `pnj:borin_barbe_de_jais` | Borin Barbe-de-Jais | nain · réceptionniste du Bastion de l'Yonne (Auxerre) | déclenche la mission des bûcherons |
| `pnj:gautier_de_valcroix` | Gautier de Valcroix | humain · maître de guilde d'Auxerre | donneur de mission |
| `pnj:armand_renaud` · `pnj:etienne_morel` · `pnj:matthieu_perrin` | les trois bûcherons | humain · nain · ogre (le dump a changé les Lignées des fiches) | réfugiés dans la grotte avec Aélis |
| `pnj:aelis_de_montfaucon` | Aélis de Montfaucon | humaine · jeune architecte, spécialiste des cristaux de mana dans la structure des bâtiments | amie possible ; porteuse de **théories contradictoires** sur le mystère |
| `pnj:dame_eleonore_de_rochefort` (+ `_lutecia`) | Dame Éléonore de Rochefort | **elfe** · paladine, commandante des convois de cristaux d'Auxerre | escorte vers Lutecia ; attend ensuite ses ordres sur le parvis de Notre-Dame |
| `pnj:frere_martin_de_clairvaux` (+ `_lutecia`) | Frère Martin de Clairvaux | **hobbit** · paladin, second de l'escorte | « comparse hobbit » de la paladine |
| `pnj:eleonore_de_vaugirard` | Éléonore de Vaugirard | humaine · réceptionniste du Grand Relais des Frontières (Lutecia) | accueil à Lutecia |
| `pnj:maelys` | Maëlys **de Valombre** (Valombre = son hameau, pas un titre) | **naine** · maîtresse de la Guilde de Lutecia (bureau du Grand Relais) | remplace le « vieux elfe » (Auteur, 11/10) ; cicatrice jamais racontée ; ancienne aventurière ; prédécesseur = le **vieil elfe**, sans nom, **porté disparu** (enquête secrète sur un portail hors de Lutecia) ; première rencontre **au bureau, au rang D**, sur recommandation de Gautier de Valcroix ; donne l'**épreuve du rang C** (portail de Jumièges, escorte d'Aélis) ; secret : **même lieu** dans des donjons de portails différents — tour inclinée (**Babel**), arbre mort (**Yggdrasil**), porte rouge, inscription en **hénochien** (piste Grigori), mystère ouvert. Arbitrage de l'Auteur : [personnages/20261011_maelys_maitresse_de_guilde.md] |
| `pnj:milo_cartographe` | Milo | hobbit · aide-cartographe d'une compagnie de voyageurs (Auxerre) | arc de deuil n° 1 |
| `pnj:elise_herboriste` | Élise | **naine** · herboriste du **Coq de Lutèce** (faubourgs de Lutecia) | arc de deuil n° 2 |
| `pnj:reverend_malakor` | Révérend Malakor | ogre · prêtre (temple de Saint-Eusèbe, Auxerre) | — |
| `pnj:marchand_*` | tenanciers par métier (« Maître Gorm », « Dame Ysoline », « L'ombre de Vaudrec »…) | humains par défaut | un par catégorie de magasin |

Les noms de marchands suivent le gabarit **Maître / Dame / Frère / Docte / Le vieux + prénom médiéval français**, parfois « de Lutèce ». Listes de noms : `docs/archives/lore/contenu/20260912_noms_marchands_de_lutece.md` (Lutèce, puis France). Enseignes par métier : `docs/archives/lore/contenu/20260907_noms_de_magasins_par_type.md` (le jeu les tire de `utils/enseignes.py`).

## Mission « Les bûcherons disparus » (Auxerre → Lutecia) — [personnages/20260831_scenario_mission_auxerre.md], [personnages/20260831_scenario_mission_auxerre.md]
**Auteur**
1. Dernière quête propre à Auxerre. Borin prévient que le maître cherche le personnage, puis Gautier confie la mission : retrouver des bûcherons partis trop loin dans les forêts denses.
2. On les retrouve **cachés dans une grotte** avec **Aélis**, jeune architecte humaine qui tentait de rejoindre Auxerre pour étudier les cristaux. Trois **Loups géants** rôdent devant l'entrée, trop étroite pour eux.
3. La mission s'achève par le **voyage vers Lutecia**, sous escorte paladine, avec la **dernière livraison de cristal** et Aélis.

## Aélis — [personnages/20260916_ecrire_deux_histoires_d_aelis.md], [personnages/20260924_etoffer_l_intrigue_des_catacombes.md]
**Auteur**
- **Retrouvailles** à l'**institut des architectes de Lutecia**, qui **mènent à une mission** — écrite (11/10/2026) : Maëlys, pour le **rang C**, envoie l'aventurier escorter Aélis jusqu'au portail des ruines de **Jumièges** ; elle revient aux **Archives des Seuils** avec trois théories et aucune réponse.
- **Plus tard** : on lui offre d'approfondir sa formation à **Mu**, et elle veut que l'aventurier l'accompagne.
- **Arc après Jumièges** (Auteur, 19/11) : rang C « La pièce derrière le mur » (boîte de **Maître Villard**, rapportée de Mu — **jamais dit** ; départs : Aélis, Villard, réception de la Guilde, Maëlys ; Aélis **escortée** ; **nouveau système d'énigmes**) → rang B « Les vestiges du premier passage » → rang A, partir pour Mu : [personnages/20261119_la_piece_derriere_le_mur.md]. **21/11** : arc suivi **dans l'ordre**, on n'arrive à Mu que par lui ; Mu-la-Centrale **à demi fermée** (invité de l'Institut, auberge + marché restreint, le reste par réputation/quêtes, **aucune maison de Guilde**) ; 1ʳᵉ livraison = accès Notre-Dame ↔ Mu + cité explorable, Échidna en seconde passe. **22/11 — « Partir pour Mu »** (rang A) : deux départs (Aélis aux Archives, Maëlys à la Guilde ; vestiges réussis + rang A), passage gardé par **Aénor de Sully** à Notre-Dame, **aucun combat**, cristal jaune **payé par le joueur** dès le 1ᵉʳ passage ; à Mu d'abord le **portail d'arrivée**, l'**auberge** et le **marché restreint** (Institut de Mu, Sept Sages plus tard). Contenu : `dev/gen_partir_pour_mu.py` (proposé : cristal jaune vendu au marché de Mu, seule sortie).
- La relation n'est **pas ambiguë**. L'aventurier peut être une femme. Ce qui compte, c'est la **confiance** et le **regard extérieur** que l'aventurier apporte à l'architecte.
- Elle est l'une des personnes qui portent des **théories contradictoires** sur le mystère.

**Proposé** : mission de l'Institut à travers un portail vers une forêt aux runes trop anciennes, avec des traces de passage récentes dans les deux sens. Formule : « Un Architecte sait comment fonctionne une porte. Un aventurier sait ce que cela signifie de la franchir. »

## Les deuils — [personnages/20260925_creer_trois_revirements_emotionnels.md], [personnages/20261003_ecrire_dialogues_de_milo.md], [personnages/20261003_scenario_d_elise.md], [personnages/20261003_scenario_d_elise.md]
L'Auteur veut des événements **traumatiques** : la mort d'un PNJ amical.
- La paladine se prête mal à un lien émotionnel, car elle reste concentrée sur sa mission.
- Deux arcs ont été retenus :
	- **Milo — l'attachement par la complicité** (texte de l'Auteur, 03/10) :
		- Il veut dresser la carte complète de la région ; à chaque retour, ils la complètent ensemble.
		- Une mission banale d'escorte de caravane tourne mal, et Milo meurt en voulant récupérer **sa carte**.
		- Une région de la carte reste **vierge**, et l'aventurier veut la terminer : une quête personnelle, **pas une vengeance**.
		- Avant, il explorait pour devenir quelqu'un. Après, il explore parce que quelqu'un qu'il aimait ne verra jamais ce qu'il y a derrière l'horizon.
	- **Élise — l'attachement par la vie quotidienne** (texte de l'Auteur, 03/10) :
		- Quatre visites : elle soigne en plaisantant, reconnaît ses habitudes, demande une plante, puis devient familière.
		- Elle part chercher des herbes dans une forêt **qu'elle connaît depuis des années**, et ne revient pas.
		- L'**aubergiste** l'annonce. Aucun monstre exceptionnel, aucune explication : « Elle était simplement partie chercher des herbes. »
		- Le dernier dialogue est **volontairement anodin** (« À tout à l'heure. »).
		- Les quatre dialogues de référence sont dans les messages de l'Auteur ([personnages/20261003_scenario_d_elise.md]).

## Trame des quêtes par rang — [cites/20261124_de_mu_aux_mondes_divins.md], [personnages/20260924_etoffer_l_intrigue_des_catacombes.md]
**Auteur** :
- La France d'abord (escortes depuis Montmartre), le monde après le **rang A** : Notre-Dame : gemme violette vers le reste du monde, cristal jaune vers Mu (11/10).
- À partir du rang A, les quêtes **quittent Lutecia** (Mu ou ailleurs). Elles servent à faire **miroir des mythologies**, plutôt qu'à parler des portails et de leurs malfaçons.
- L'Auteur aurait voulu des quêtes plus ancrées dans les cités déjà décrites. Il a pourtant décidé : « On va garder ta dernière version ».

Trame **retenue** (D–B de la première version, A–S+ de la version gardée) :

| Rang | Quête | Lieu | Thème |
|---|---|---|---|
| D | « Les rats de la crypte » | catacombes de Lutecia | ouvriers disparus, crypte rouverte, objet au symbole de portail ancien |
| C | « La route de Saint-Denis » | route nord ; **4ᵉ escorte de Bouchard** (Montmartre), pas une épreuve de rang (Jumièges l'est) — arbitrée le 08/11 : [personnages/20261108_la_route_de_saint_denis.md] | les monstres **précèdent** les donjons : loups et corneilles rabattent vers le **Chemin du Saint**, serpent de Marcel (être unique) ; légendes de Denis et de Marcel, sans christianisme |
| B | « La porte qui ne devait pas s'ouvrir » | temple templier près de Lutecia | l'extraction de cristaux **modifie** un donjon |
| A | Mu : « Le serpent sous la cité » | Mu | rencontre avec **Échidna**, « mère des serpents » des traditions de Mu, sous Mu-la-Centrale près de la porte fermée (11/10) : la combattre ou parler — **deux voies, choix définitif** inscrit sur le personnage, la parole pouvant aboutir sans combat ou y basculer, aucune voie « bonne » (Auteur, 21/11). « Vous appelez monstres mes enfants. » **Séjour** (Auteur, 22/11 ; [cites/20261011_histoire_de_mu_chatgpt.md] arbitrage, [cites/20261124_de_mu_aux_mondes_divins.md]) : gagner sa place → descendre (réseau d'eau, portail scellé qui **réagit**, empreintes à trois têtes, **fragments de la serrure**, **Templiers de Mu contre Aélis**) → Échidna ; **arc court** (Auteur, 24/11) : **3 quêtes** pour gagner sa place, descente = **enquête modulaire** sans nombre fixe (énigmes secondaires, Templiers secondaires, Aélis autonome et faillible), Échidna qui **avertit** avant un combat **très difficile** ; quête 1 « Les eaux troubles de Mu » (**Rangi Waiora**, **Naga** cherchant Échidna par les conduites, trois issues) ; demande de réunion avec Cerbère **au bout de la parole** : **Cerbère passe, la porte reste close** ; au bout du **combat**, Échidna, **immortelle**, **s'enfuit**, introuvable, ne défend plus Mu (qui le paie à terme) mais reste proche dans l'espoir de retrouver Cerbère ; sept facultatives (cartographes, chant, marchand du passé, enfants de la marée, dernier gardien, eaux sans poissons, nom effacé), **développées** (Auteur, 24/11 ; [cites/20261124_de_mu_aux_mondes_divins.md]) : quatre dès l'arrivée (chant, marchand, enfants, eaux), trois après rencontre ; ordre libre, indices indépendants, conclusion locale, **aucun effet sur la trame**, accessibles au retour à Mu ; chant = tradition familiale, « coque d'or » = la bulle, sanctuaire noyé de Tangaroa, cérémonie collective, origine des rêves inconnue ; gardien tenu par le **mana** (pas de vocabulaire technique). **Colère contre les dieux** (Auteur, 24/11 ; [cites/20261124_de_mu_aux_mondes_divins.md]) : indices **progressifs** sur tout l'arc — fresques de la porte (héros enchaînant le chien à trois têtes ; Hadès « qui reçoit beaucoup », porte vorace laissée grandir), nom effacé, eaux sans poissons et silence de **Tangaroa**, dernier gardien — reliés par **Échidna** (Héraclès tue ses enfants, enchaîne Cerbère ; elle épargnée « pour éprouver les héros ») ; parole → **Enfers d'Hadès vides** entrevus au passage de Cerbère ; combat → **antre abandonné**, culpabilité du héros-pion ; mystère gardé par voix contradictoires (Aélis : dieux absents ; **Uannedugga** : dieux enfuis ; un Templier de Mu : sacrifice juste), Héraclès qui ramène Cerbère, bulle dorée peut-être réponse de Tangaroa. **Départ** : relevé des seuils « demeure » du siège d'**Uanna**, refusé par les Sages, obtenu selon la voie. |
| A (suite) | **Hekla** → Enfer de Lucifer, **prison habitée et fonctionnelle**, pas une demeure (contrepoint des Enfers vides d'Hadès) ; trajet Notre-Dame → réseau → **Reykjavik** → route → **forteresse templière du volcan** (garde : Templiers de Reykjavik, commandeur elfe au nom islandais ; Sæmundr y sert ; Akureyri hors de l'arc) ; ouvert par la **copie** du relevé d'Uanna + **une épreuve au choix** (chasse d'un Malebranche échappé OU énigme de déduction démasquant un démon captif ; XP, aucun objet) ; **Aélis au seuil**, vouvoie ; **neuf cercles** de Dante déformés en **fautes carcérales** (Charon, Minos, Ciacco, Plutus, Phlégyas, Furies, Géryon, Malacoda, Antée), **trois donjons à étages enchaînés** + Cocyte ; Dante = voyageur revenu (théorie) ; Lucifer au Cocyte, **parole seule** : « **ceux qui étaient avant** » ; sortie à sens unique du Cocyte vers la forteresse ; retour **par voie** de Mu (Auteur, 27-28/11 ; `cites/20260820_decrire_l_histoire_de_reykjavik.md`) | Reykjavik | les demeures divines ne sont pas toutes vides : pourquoi certains partent-ils, et qui jette ? |
| S | Rome → **Paradis** (avant Yggdrasil ; Auteur, 24/11) | Rome | des anges aux réponses ambiguës (« Vos dieux vous ont menti. » — est-ce vrai ?) ; répond à « qui jette ? » |
| S | **Yggdrasil** | cité nordique | Asgard, Midgard, Jötunheim, Hel ; les mondes précèdent-ils les récits ? |
| S+ | « Celui qui était avant » | hors de toute mythologie | quatre hypothèses, **le jeu ne tranche pas** |

**Épreuves de rang de Lutecia en jeu** (Auteur, 25/10) : au rang C → B et B → A, Maëlys propose **plusieurs épreuves** — B : Gargouille de la Seine, pli d'Aix-la-Chapelle, Porte de Mars, la porte qui ne devait pas s'ouvrir (Enclos du Temple, catacombes) ; A : géant de la baie, Bête du Gévaudan, Minotaure du puits de Chartres (deux, on y descend), Ampoule du Sacre, délégation palatine. Chasses = trophées sur la carte de France. Détail : [personnages/20261025_missions_rang_b_a_lutecia.md].

La première version d'A–S+ (« Le bélier de Mu », Orphée/Hadès, Ragnarök, « Le jardin derrière le ciel ») est une **variante** de la même séance. Règle proposée et cohérente avec l'Auteur : chaque mythologie **répond à une question et en ouvre deux**.

## Autres séances utiles
- **Ambiances de nuit** au logement (`utils/auberge.py`, `MESSAGES_NUIT_LOGEMENT`) : on y ajoute des **interrogations du personnage sur le monde**, chacune **autonome** — [personnages/20261005_ajouter_introspection_nocturne.md].
- **Vidéo de 15 s** pour un joueur qui commence dans une petite ville : ne pas trop en révéler — `docs/archives/lore/contenu/20260830_prompt_video_telluris.md`.
- **Descriptions de recettes**, à la voix d'un magicien, 800 caractères maximum — `docs/archives/lore/contenu/20260830_rediger_une_recette_necromantique.md`.
- **Auberge** en multijoueur asynchrone — [systemes/20260828_fonctions_d_une_auberge.md].
- **Propriétés** : Chambre → Logement → Maison → Demeure → Domaine, sans transformation de l'une en l'autre ; voie de **colonisation** par hameau. Mécanique : **telluris-proprietes** — [systemes/20260924_progression_des_lieux_de_guilde.md].
- **Colonisation** (décisions de l'Auteur, 12/11 ; première tranche en jeu le 13/11, mécanique : **telluris-colonisation**) : Campement → Hameau → Bourgade → Village → Bourg → Petite ville → Ville ; guilde du joueur indépendante, en cinq échelons du Village à la Ville ; interface au § 12 (lieu modèle par palier et milieu choisi par tags, lien pur vers le modèle, pose libre « Poser ici », replacement automatique à la montée) ; valeurs de départ dans `rules:colonisation` — [systemes/20261112_voie_de_colonisation.md].
