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
| `pnj:milo_cartographe` | Milo | hobbit · aide-cartographe d'une compagnie de voyageurs (Auxerre) | arc de deuil n° 1 |
| `pnj:elise_herboriste` | Élise | **naine** · herboriste du **Coq de Lutèce** (faubourgs de Lutecia) | arc de deuil n° 2 |
| `pnj:reverend_malakor` | Révérend Malakor | ogre · prêtre (temple de Saint-Eusèbe, Auxerre) | — |
| `pnj:marchand_*` | tenanciers par métier (« Maître Gorm », « Dame Ysoline », « L'ombre de Vaudrec »…) | humains par défaut | un par catégorie de magasin |

Les noms de marchands suivent le gabarit **Maître / Dame / Frère / Docte / Le vieux + prénom médiéval français**, parfois « de Lutèce ». Listes de noms : [contenu/20260912_noms_marchands_de_lutece.md] (Lutèce, puis France). Enseignes par métier : [contenu/20260907_noms_de_magasins_par_type.md] (le jeu les tire de `utils/enseignes.py`).

## Mission « Les bûcherons disparus » (Auxerre → Lutecia) — [personnages/20260831_scenario_mission_auxerre.md], [personnages/20260831_prompt_mission_pnj_json.md]
**Auteur**
1. Dernière quête propre à Auxerre. Borin prévient que le maître cherche le personnage, puis Gautier confie la mission : retrouver des bûcherons partis trop loin dans les forêts denses.
2. On les retrouve **cachés dans une grotte** avec **Aélis**, jeune architecte humaine qui tentait de rejoindre Auxerre pour étudier les cristaux. Trois **Loups géants** rôdent devant l'entrée, trop étroite pour eux.
3. La mission s'achève par le **voyage vers Lutecia**, sous escorte paladine, avec la **dernière livraison de cristal** et Aélis.

## Aélis — [personnages/20260916_ecrire_deux_histoires_d_aelis.md], [personnages/20260924_etoffer_l_intrigue_des_catacombes.md]
**Auteur**
- **Retrouvailles** à l'**institut des architectes de Lutecia**, qui **mènent à une mission**.
- **Plus tard** : on lui offre d'approfondir sa formation à **Mu**, et elle veut que l'aventurier l'accompagne.
- La relation n'est **pas ambiguë**. L'aventurier peut être une femme. Ce qui compte, c'est la **confiance** et le **regard extérieur** que l'aventurier apporte à l'architecte.
- Elle est l'une des personnes qui portent des **théories contradictoires** sur le mystère.

**Proposé** : mission de l'Institut à travers un portail vers une forêt aux runes trop anciennes, avec des traces de passage récentes dans les deux sens. Formule : « Un Architecte sait comment fonctionne une porte. Un aventurier sait ce que cela signifie de la franchir. »

## Les deuils — [personnages/20260925_creer_trois_revirements_emotionnels.md], [personnages/20261003_ecrire_dialogues_de_milo.md], [personnages/20261003_scenario_d_elise.md], [personnages/20261003_prompt_pour_elise.md]
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
		- Les quatre dialogues de référence sont dans les messages de l'Auteur ([personnages/20261003_prompt_pour_elise.md]).

## Trame des quêtes par rang — [personnages/20260924_idees_de_quetes_a_lutecia.md], [personnages/20260924_etoffer_l_intrigue_des_catacombes.md]
**Auteur** :
- La France d'abord (escortes depuis Montmartre), le monde après le **rang A** : Notre-Dame, un voyage par cristal jaune.
- À partir du rang A, les quêtes **quittent Lutecia** (Mu ou ailleurs). Elles servent à faire **miroir des mythologies**, plutôt qu'à parler des portails et de leurs malfaçons.
- L'Auteur aurait voulu des quêtes plus ancrées dans les cités déjà décrites. Il a pourtant décidé : « On va garder ta dernière version ».

Trame **retenue** (D–B de la première version, A–S+ de la version gardée) :

| Rang | Quête | Lieu | Thème |
|---|---|---|---|
| D | « Les rats de la crypte » | catacombes de Lutecia | ouvriers disparus, crypte rouverte, objet au symbole de portail ancien |
| C | « La route de Saint-Denis » | route nord, avec un paladin du Sacré-Cœur | les monstres **précèdent** les donjons |
| B | « La porte qui ne devait pas s'ouvrir » | temple templier près de Lutecia | l'extraction de cristaux **modifie** un donjon |
| A | Mu : « Le serpent sous la cité » | Mu | rencontre avec **Lilith/Échidna** : la combattre ou parler. « Vous appelez monstres mes enfants. » |
| A+ | Rome → **Paradis** | Rome | des anges aux réponses ambiguës (« Vos dieux vous ont menti. » — est-ce vrai ?) |
| S | **Yggdrasil** | cité nordique | Asgard, Midgard, Jötunheim, Hel ; les mondes précèdent-ils les récits ? |
| S+ | « Celui qui était avant » | hors de toute mythologie | quatre hypothèses, **le jeu ne tranche pas** |

La première version d'A–S+ (« Le bélier de Mu », Orphée/Hadès, Ragnarök, « Le jardin derrière le ciel ») est une **variante** de la même séance. Règle proposée et cohérente avec l'Auteur : chaque mythologie **répond à une question et en ouvre deux**.

## Autres séances utiles
- **Ambiances de nuit** au logement (`utils/auberge.py`, `MESSAGES_NUIT_LOGEMENT`) : on y ajoute des **interrogations du personnage sur le monde**, chacune **autonome** — [personnages/20261005_ajouter_introspection_nocturne.md].
- **Vidéo de 15 s** pour un joueur qui commence dans une petite ville : ne pas trop en révéler — [contenu/20260830_prompt_video_telluris.md].
- **Descriptions de recettes**, à la voix d'un magicien, 800 caractères maximum — [contenu/20260830_rediger_une_recette_necromantique.md].
- **Auberge** en multijoueur asynchrone — [systemes/20260828_fonctions_d_une_auberge.md].
- **Propriétés** : Chambre → Logement → Maison → Demeure → Domaine, sans transformation de l'une en l'autre ; voie de **colonisation** par hameau. Mécanique : **telluris-proprietes** — [systemes/20260924_progression_des_lieux_de_guilde.md].
