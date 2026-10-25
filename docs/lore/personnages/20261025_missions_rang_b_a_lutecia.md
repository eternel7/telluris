# Les épreuves des rangs B et A de Lutecia

- **Source :** séance Claude Code du 25/10/2026 ; l'Auteur arbitre par questionnaire (§ 1).
- **Créée :** 25/10/2026
- **Statut :** le § 1 **fait foi** ; les noms de PNJ neufs, les motifs des escortes et les textes de dialogue sont **proposés**. Contenu en jeu : `dev/gen_missions_rang_b_a_lutecia.py` → `jsons/missions_rang_b_a_lutecia_a_importer.json`.

---

## 1. Arbitrage (Auteur, 25/10, questionnaire)

| Point | Décision |
|---|---|
| Donneuse | **Maëlys de Valombre**, maîtresse de la Guilde, pour toutes les épreuves C → B et B → A |
| Choix | **plusieurs missions par montée** ; le moteur accepte une liste d'offres par service (`offres`), une seule tenue à la fois par service |
| Chasses | cibles sur la **carte de France**, pas dans Lutecia ; **trophée au hasard** (on rapporte la tête d'une bête croisée), sauf le Minotaure |
| Cibles | **Gargouille de Rouen**, **Géant du Mont-Saint-Michel**, **Bête du Gévaudan** |
| Minotaure | il **ne sort pas** du puits de Chartres : on **descend** dans le donjon pour le tuer ; nouvelle battle map |
| Autres missions | **Porte de Mars** (Rhemi), **La porte qui ne devait pas s'ouvrir** (trame B de l'Auteur), **escorte de l'Ampoule**, un **pli** et une **escorte** vers **Aix-la-Chapelle** |
| Calibrage | planchers de potentiel des épreuves de comptoir = **simple référence** pour la Gargouille, la Bête et le Géant (folklore gardé, grades élevés visés) ; le Minotaure se **compense par l'effectif** : **2 Minotaures, grade Champion–Héros** |

Potentiels mesurés contre le dump du 24/10 (équipement espéré compris, du grade Combattant au grade Seigneur) : Gargouille 93-152 · Bête du Gévaudan 69-131 · Géant du Mont-Saint-Michel 173-236 · Minotaure armé 84-152 (Champion 131, Héros 148). Planchers : B 175, A 250.

Un Minotaure est **à peu près un ogre au plafond** (Force 50-80 contre 40 → 70 pour l'ogre joueur), moins agile et de moindre volonté ; ses armes (kanabō, morgenstern, hache de guerre) comptent pour beaucoup dans sa force.

## 2. Les neuf épreuves

### Rang B (au rang C)
1. **La Gargouille de la Seine** (apport, tête). Rouen raconte qu'une gargouille ravageait ses quais ; on la brûla, la tête et le cou ne brûlèrent pas et furent cloués au rempart — légende réelle de Rouen, adaptée sans le saint qui la vainc. Elle rejoint les rencontres des berges de France. **Doute après** : pierre animée par un portail jamais trouvé, ou bête qui finit en pierre ?
2. **Le pli d'Aix-la-Chapelle** (transport `retour`). Maëlys demande au chancelier de l'Hôtel de Ville si l'une des portes des cités sœurs a changé de couleur — piste de l'enquête de son prédécesseur, le vieil elfe disparu, sans la nommer. Réponse : non. Après : une porte a pâli une heure, une nuit ; « c'est l'hiver », disent les architectes.
3. **La Porte de Mars** (escorte d'Hugues Vaucelle, architecte de la Cour). Le portail mort-né de Rhemi ; « certains jurent qu'elle a marché une fois ». Après : Vaucelle reste sous l'arche (« elle attend »), le vieux gardien nain répond qu'à Rhemi une porte qui attend depuis des siècles s'appelle une porte morte.
4. **La porte qui ne devait pas s'ouvrir** (transport `retour` puis **descente dans les catacombes**, trame B de l'Auteur). Le commandeur de l'Enclos du Temple avoue qu'au fond de l'ossuaire des catacombes, là où l'on extrait les cristaux jaunes, une paroi s'est ouverte sur une porte de pierre fermée, tiède, gravée d'un signe illisible. Il ne répond à la Guilde qu'une fois qu'on est **descendu jusqu'à l'ossuaire** (3ᵉ et dernier étage des catacombes de Lutecia, Auteur 25/10) et qu'on lui a rapporté le **cristal jaune** de son coffre ; Maëlys ne donne le rang qu'ensuite. Doute : elle a toujours été là, ou l'extraction la fait venir « comme l'eau fait venir une racine ».

### Rang A (au rang B)
5. **Le géant de la baie** (apport, tête). Le géant venu d'Ibérie ; Arthur l'a tué, disent les chansons, pourtant il y a toujours un géant sur le Mont. Après : « le Mont est silencieux — il l'était déjà, la dernière fois, avant qu'un autre revienne ».
6. **La Bête** (apport, tête). Loup-garou ou non, jamais su (décision de l'Auteur, 14/10). La tête est celle d'une bête, sans visage ; une rebouteuse dit qu'elle a saigné trois semaines après la mort, un archiviste que c'est impossible.
7. **Le puits de Chartres** (apport, tête ; donjon). Le Templier nain de la crypte descend le groupe au treuil dans le labyrinthe. On y attend un Minotaure, **il y en a deux**. Doute : le second est un fils ; ou le labyrinthe en refait un chaque fois qu'on en tue un. Pas de Thésée : « ailleurs, on raconte qu'un héros est entré avec un fil ».
8. **L'Ampoule du Sacre** (escorte ; rendez-vous à l'Auberge du Sacre de Rhemi → Chapelle Palatine d'Aix). Le gardien Gervais de Sillery et deux paladins de Rhemi qui se défendent. Aix (plus de trente rois couronnés) demande l'Ampoule pour un couronnement. **Proposition** : ce prêt de l'Ampoule n'est écrit nulle part dans le lore. Après : les cinq portes de la Chapelle ont brillé ensemble à l'ouverture du coffret ; l'huile a-t-elle reconnu les portes, ou les portes l'huile ?
9. **La délégation palatine** (escorte de maître Anselme Gerbier et de Clémence d'Orval → Hôtel de Ville d'Aix). La Cour veut comprendre comment tiennent les portes de Charlemagne. Après : « bien faites », dit le maître ; « tenues de l'autre côté aussi », note l'élève — barré par le maître, recopié par la Cour.

## 3. Propositions non tranchées

- Noms et Lignées des PNJ neufs : Hugues Vaucelle, Gervais de Sillery, Aude de Cormicy, Baudouin de Verzy, Anselme Gerbier, Clémence d'Orval ; PNJ anonymes : le chancelier de l'Hôtel de Ville, la gardienne des cinq portes, le commandeur de l'Enclos, le gardien de la Porte de Mars, le Templier de la crypte.
- La Chapelle Palatine tenue par une **Templière** (les Templiers gèrent les portails de déplacement encore actifs depuis la Vague).
- L'**Enclos du Temple** comme maison des Templiers de Lutecia, gardiens des catacombes et de l'extraction des cristaux jaunes.
- Le prêt de l'Ampoule à Aix pour un couronnement.

## 4. Prompts d'images

Les lieux neufs utilisent une image existante en attendant ; noms de fichiers proposés entre parenthèses.

**Le labyrinthe du puits de Chartres** (`battle_maps/labyrinthe_du_puits_de_chartres.jpg`, paysage 3:2, carte 30 × 20 cases) :

```
Réalise l'image d'un labyrinthe souterrain vu exactement du dessus : des couloirs de dalles de pierre ocre et grise, larges de deux pas, séparés par des murs épais de pierre sèche, qui tournent toujours du même côté autour d'une petite salle centrale ronde. Au centre, une margelle de pierre noire et le bas d'une chaîne de fer qui pend d'en haut. Sur les dalles, de la paille piétinée, des os rongés, de grandes traces de sabots fendus, quelques torches éteintes fichées dans les murs ; dans deux recoins, des litières de paille plus épaisses. Une faible lueur violette sourd entre les joints des dalles du centre. Aucun personnage, aucune créature. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane. La vue est aérienne. C'est une battlemap.
```

**La crypte de Chartres** (`towns/crypte_de_chartres.jpg`, paysage 16:9) :

```
Réalise l'image de la crypte de la cathédrale de Chartres : une longue galerie basse voûtée en berceau, éclairée de lampes à huile, des piliers trapus et, au fond, une margelle de pierre noire surmontée d'un treuil de fer et d'une chaîne qui plonge dans un puits. Un Templier nain en manteau blanc et cotte de mailles se tient devant le puits, la main posée sur la manivelle. Sur un mur, une statue ancienne de femme noire, sculptée on ne sait par qui. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**L'Hôtel de Ville d'Aix-la-Chapelle** (`towns/hotel_de_ville_d_aix_la_chapelle.jpg`, paysage 16:9) :

```
Réalise l'image de la grande salle voûtée de l'Hôtel de Ville d'Aix-la-Chapelle : le long des murs, une rangée d'arches de pierre noire, chacune sous une bannière de couleur différente et emplie d'une lueur calme, les portes vers les cités sœurs. Au premier plan, une table chargée de registres où un chancelier humain en robe noire et chaîne d'office écrit à la plume. Une vapeur légère monte d'une grille au sol, venue des thermes voisins. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**La Chapelle Palatine** (`towns/chapelle_palatine.jpg`, paysage 16:9) :

```
Réalise l'image de l'intérieur de la Chapelle Palatine d'Aix-la-Chapelle : un octogone très haut, arcades de marbre bicolore, mosaïques dorées jusqu'à la coupole. Au sol, cinq arches de pierre disposées en étoile à cinq branches, chacune ouverte sur une lueur calme d'une couleur différente. Au centre de l'étoile, une Templière elfe en manteau blanc, les mains croisées. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**La Porte de Mars** (`towns/porte_de_mars_rhemi.jpg`, paysage 16:9) :

```
Réalise l'image de la Porte de Mars à Rhemi : une immense arche triple de pierre claire, haute comme trois maisons, couverte de bas-reliefs usés par la craie, plantée au milieu d'une rue ; derrière l'arche, la rue continue, il n'y a rien d'autre. Au pied du pilier central, un vieux gardien nain en cuirasse est assis sur un tabouret, une hallebarde en travers des genoux. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**L'Enclos du Temple** (`towns/enclos_du_temple_lutecia.jpg`, paysage 16:9) :

```
Réalise l'image de l'Enclos du Temple à Lutecia : une enceinte fortifiée dans la ville, une haute tour carrée flanquée de tourelles, une cour pavée où des Templiers en manteau blanc déchargent d'un chariot des caisses d'où s'échappe une lumière jaune. Un commandeur humain grisonnant observe depuis le seuil de la tour. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```
