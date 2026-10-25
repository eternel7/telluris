# Les cinq portes d'Aix-la-Chapelle — temples de sortie et Templiers gardiens

- **Source :** séance Claude Code du 25/10/2026. L'Auteur choisit les cinq portes de la Chapelle Palatine pour créer des portails en jeu, demande un temple et un Templier gardien à chaque sortie, leurs prompts d'image, puis la liste des lieux propices à de nouveaux portails.
- **Créée :** 25/10/2026
- **Statut :** destinations = **canon** (Auteur, 24/08 et 26/08). Temples, Templiers, noms et théories = **proposition de Claude Code, à arbitrer**. En jeu : `dev/gen_portails_aix.py` → `jsons/portails_aix_a_importer.json`.

---

## ✍️ Auteur

On va créer des portails. Normalement, X-la-chapelle est un bon concurrent. On sait déjà où ça mène. À l'endroit là où il y a la sortie, il faut créer un temple et un templier gardien. Donc tu me donneras les prompts correspondants. Et après, par la suite, tu peux me lister les lieux qui sont propices à la création de nouveaux portails en fonction de ce que l'on a déjà et de comment ils sont déjà alimentés, on va dire.

## 🤖 Claude Code — proposition

### 1. Ce qui fait foi
- Chapelle Palatine : **5 portails transversaux** en pentagramme, œuvre d'**un frère** venu en Europe, **destination fixe**, intacts après la Vague (Auteur, 24/08) : Sydney, Tokyo, Teotihuacan, Pichao/Pcho (Machu Picchu), Abou Simbel (tableau du 26/08).
- Portails **originaux des frères** : presque toujours **sans cristal** (Auteur, 11/10) → ces cinq portes ne consomment rien.
- Les fenêtres de `towns/chapelle_palatine.jpg` montrent l'autre côté : falaises ocre sous un ciel immense · toits de bois courbes sous des cerisiers · pyramide à degrés au bout d'une allée · terrasses accrochées à une montagne verte dans les nuages · colosses assis au bord d'un fleuve. Les temples ci-dessous s'y accordent.

### 2. Les cinq temples de sortie (proposé)
Chaque temple est **bâti autour de la porte** (règle : monuments et temples bâtis autour d'un portail), adapté d'un lieu réel.

| Porte | Temple (`lieu:*`) | Lieu réel adapté | Templier (`pnj:*`) |
|---|---|---|---|
| Sydney | Sanctuaire de Baiame (`sanctuaire_de_baiame`) | gravures rupestres des promontoires de grès de Sydney ; Baiame, père du ciel | **Barangaroo**, humaine, ancienne pêcheuse |
| Tokyo | Temple de Sensō-ji (`temple_de_senso_ji`) | Sensō-ji d'Asakusa : deux frères pêcheurs tirent une statuette de la Sumida, le chef de village bâtit le sanctuaire | **Haji no Nakatomo**, nain, porte le nom du chef de village |
| Teotihuacan | Temple du Serpent à plumes (`temple_du_serpent_a_plumes`) | Ciudadela ; tunnel sous le temple et ses flaques de mercure | **Ocelotl**, ogre, peau de jaguar (alliance avec les guerriers-jaguars, canon) |
| Pichao | Temple du Soleil de Pichao (`temple_du_soleil_de_pichao`) | Torreón et sa grotte ; Intihuatana, « la pierre où l'on attache le soleil » | **Cusi Coyllur**, hobbit (nom de l'héroïne d'*Ollantay*) |
| Abou Simbel | Petit Temple d'Abou Simbel (`petit_temple_d_abou_simbel`) | petit temple d'Hathor et de Néfertari ; ici colosses de Néfertiti et d'Akhénaton | **Nakhtmin**, elfe, mort-vivant bien conservé de la cour |

Théories contradictoires portées par les Templiers, aucune tranchée : le frère parti de Sydney vs la porte bâtie depuis Aix · la statuette qui appelle la porte vs la porte qui met la statuette dans le filet · le Serpent à plumes qui enseigne le frère vs le frère seul · la pierre qui tient la porte vs la porte qui tient la pierre · la porte obtenue contre un secret de longue vie vs donnée pour que la Reine ne vienne jamais la chercher.

### 3. En jeu
- Liens `portail` chapelle ↔ temple : ils entrent d'office au **tableau des seuils de Notre-Dame** (`utils/portails.py`) — la chapelle d'Aix et les cinq temples deviennent des points d'arrivée.
- Barrière **rang A de Lutecia** sur chaque temple (forme d'ad-Deir et de la Khazneh) ; aucune sur la chapelle, dont la gardienne parle à tous.
- Lien `temple` vers la ville d'arrivée : Sydney (falaises à l'entrée de la baie), Tokyo (la pagode au nord-est du château), Teotihuacan (la Ciudadela), Abou Simbel (petite porte au pied de la falaise, à gauche du Grand Temple).
- ⚠️ **Pichao n'existe pas au dump** : son temple n'a que la porte (cul-de-sac) jusqu'à la création de la cité.
- ⚠️ Tokyo et Teotihuacan n'ont **aucun autre lien** : la porte d'Aix en est le seul accès.

### 4. Prompts d'image
Lieux : `templates/resources/towns/`, paysage 16:9. Portraits : `templates/resources/pnj/`, paysage 16:9, aucun nom dans le prompt.

**Le Sanctuaire de Baiame** (`towns/sanctuaire_de_baiame_sydney.jpg`) :

```
Réalise l'image d'un sanctuaire à ciel ouvert sur un promontoire de falaises de grès ocre qui garde l'entrée d'une grande baie, près de la cité de Sydney, dans un monde médiéval fantastique, format paysage 16:9. Sur la roche plate et nue du promontoire, de grandes gravures anciennes creusées dans le grès : des baleines, des poissons, des chasseurs, une grande silhouette aux bras ouverts et trois petites figures côte à côte. Les Templiers ont élevé autour une enceinte basse de pierre sèche, sans toit. Au centre, une arche de grès nu, massive et sans ornement, encadre un voile de lumière qui tourne lentement sur lui-même ; derrière le voile, on devine l'intérieur doré d'une chapelle octogonale. Une Templière humaine à la peau brun foncé, en manteau blanc, pieds nus sur la roche, se tient près de l'arche ; des Templiers en manteau blanc montent la garde sur le muret. Au loin, l'océan immense sous un ciel immense, les vagues qui se brisent au pied des falaises, et le dos d'un serpent de mer géant qui fend l'eau. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Ils sont en proportions égales : les humains ne sont pas plus nombreux que les autres. Pas de texte visible. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**Le temple de Sensō-ji** (`towns/temple_de_senso_ji_tokyo.jpg`) :

```
Réalise l'image du temple de Sensō-ji à Tokyo, au bord de la rivière Sumida, dans un monde médiéval fantastique, format paysage 16:9. Une grande porte de bois laqué de rouge ouvre sur une cour dallée semée de pétales de cerisier ; à gauche, une pagode de bois à cinq toits courbes ; au fond, la salle principale aux grands toits de tuiles, dont les portes ouvertes laissent voir, tout au fond, une arche de bois sombre où tremble un voile de lumière blanc doré. Un Templier nain, nettement plus petit qu'un humain, en manteau blanc sur une armure de lamelles laquées, balaie les pétales devant les marches avec un balai de bambou. Des Templiers en manteau blanc gardent les portes de la salle. Des cerisiers en fleur, des lanternes de papier sans aucune écriture. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Ils sont en proportions égales : les humains ne sont pas plus nombreux que les autres. Pas de texte visible. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**Le temple du Serpent à plumes** (`towns/temple_du_serpent_a_plumes_teotihuacan.jpg`) :

```
Réalise l'image de la salle souterraine sous le temple du Serpent à plumes, à Teotihuacan, dans un monde médiéval fantastique, format paysage 16:9. Au bout d'un long tunnel creusé dans la roche, une salle basse aux murs incrustés de poussière de pyrite qui scintille comme un ciel étoilé ; sur le sol, des flaques de métal liquide argenté brillent comme des lacs minuscules. Au fond, une arche de pierre noire ornée de têtes de serpents emplumés sculptées encadre un voile de lumière vert jade qui tourne lentement sur lui-même. Un Templier ogre, bien plus grand et massif qu'un humain, au teint cuivré, en manteau blanc avec une peau de jaguar jetée sur les épaules, se tient près de l'arche, courbé sous la voûte basse. Deux guerriers coiffés de têtes de jaguar montent la garde à l'entrée du tunnel. Des torches et des braseros éclairent la salle. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Ils sont en proportions égales : les humains ne sont pas plus nombreux que les autres. Pas de texte visible. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**Le temple du Soleil de Pichao** (`towns/temple_du_soleil_de_pichao.jpg`) :

```
Réalise l'image du temple du Soleil de Pichao, sur les terrasses de pierre d'une cité accrochée à une montagne verte et abrupte, au-dessus d'une mer de nuages, dans un monde médiéval fantastique, format paysage 16:9. Une tour de pierre courbe aux blocs de granit ajustés sans mortier se dresse sur un rocher ; sous elle s'ouvre une grotte taillée où une arche de granit encadre un voile de lumière doré qui tourne lentement sur lui-même. Plus haut, sur la crête, une pierre sculptée dressée projette son ombre sur les nuages. Une Templière hobbit, toute petite, pieds nus, en manteau blanc avec un châle de laine aux couleurs vives noué par-dessus, tend une gourde à un voyageur essoufflé qui sort de l'arche. Des lamas broutent sur les terrasses ; un pic vert et pointu domine la scène. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Ils sont en proportions égales : les humains ne sont pas plus nombreux que les autres. Pas de texte visible. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**Le Petit Temple d'Abou Simbel** (`towns/petit_temple_d_abou_simbel.jpg`) :

```
Réalise l'image de l'intérieur du Petit Temple d'Abou Simbel, taillé dans la falaise de grès au bord du Nil, dans un monde médiéval fantastique, format paysage 16:9. Une salle à piliers carrés, fraîche et sombre, dont chaque pilier porte en haut un visage de femme sculpté aux oreilles de vache ; les murs sont couverts de bas-reliefs peints de reines et de rois sans aucun hiéroglyphe lisible. Par la porte basse, au fond de la salle, on aperçoit la façade extérieure : de hauts colosses debout taillés dans la roche, une reine et un roi tour à tour. Au centre, une arche de pierre ocre encadre un voile de lumière d'un bleu froid qui tourne lentement sur lui-même. Un Templier elfe aux oreilles longues et pointues, en manteau blanc sur une cuirasse dorée, à la peau sèche et brune comme un parchemin mais aux yeux parfaitement vivants, se tient près de l'arche. Des lampes à huile et des volutes de résine brûlée. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation ; plusieurs sont des morts-vivants bien conservés, à la peau sèche et brune, vêtus de lin blanc et de bijoux d'or. Ils sont en proportions égales : les humains ne sont pas plus nombreux que les autres. Pas de texte visible. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**La Templière du Sanctuaire de Baiame** (`pnj/templier_humain_f_sydney01.jpg`) :

```
Réalise l'image d'un portrait illustré d'un personnage de fantasy médiévale, format paysage large. Une humaine d'une quarantaine d'années, à la peau brun foncé, aux cheveux noirs bouclés coupés court, élancée et musclée, le visage tanné par le vent de la mer, Templière gardienne d'un sanctuaire. Elle porte un manteau blanc sur une cotte de mailles légère, va pieds nus sur la roche, et enroule une ligne de pêche autour de son poignet. Elle se tient légèrement décalée du centre et regarde droit vers le spectateur, calme et attentive, comme on regarde quelqu'un arriver de loin. Décor : un promontoire de grès ocre couvert de gravures anciennes de baleines et de poissons, une enceinte basse de pierre sèche, une arche de grès où tourne un voile de lumière, et l'océan immense derrière. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Ils sont en proportions égales : les humains ne sont pas plus nombreux que les autres, même si la Templière est humaine ; chacun est différent par l'âge, la carrure, les cheveux et la tenue, et les ogres ont des teints humains, jamais verts. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle chaude, palette chaude et terreuse relevée de touches de couleurs vives, proportions crédibles ; pas une photographie. Image entièrement dépourvue d'écriture : aucun nom, aucune lettre, aucune signature, aucun monogramme, aucun filigrane, aucune enseigne lisible.
```

**Le Templier de Sensō-ji** (`pnj/templier_nain_m_tokyo01.jpg`) :

```
Réalise l'image d'un portrait illustré d'un personnage de fantasy médiévale, format paysage large. Un nain, nettement plus petit que les humains qui passent derrière lui, aux proportions de nain, tête et mains grandes pour sa taille, d'âge mûr, trapu, le crâne rasé et la barbe noire courte et soignée, Templier gardien d'un temple. Il porte un manteau blanc passé sur une armure de lamelles laquées de rouge sombre, et tient un balai de bambou planté devant lui comme une lance. Il se tient légèrement décalé du centre et regarde droit vers le spectateur avec une politesse un peu sévère, comme on accueille un visiteur aux bottes poussiéreuses. Décor : la cour dallée d'un temple de bois, une pagode à cinq toits courbes, des cerisiers en fleur dont les pétales tombent, et au fond une arche de bois sombre où tremble un voile de lumière. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Ils sont en proportions égales : les humains ne sont pas plus nombreux que les autres ; chacun est différent par l'âge, la carrure, les cheveux et la tenue, et les ogres ont des teints humains, jamais verts. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle chaude, palette chaude et terreuse relevée de touches de couleurs vives, proportions crédibles ; pas une photographie. Image entièrement dépourvue d'écriture : aucun nom, aucune lettre, aucune signature, aucun monogramme, aucun filigrane, aucune enseigne lisible.
```

**Le Templier du Serpent à plumes** (`pnj/templier_ogre_m_teotihuacan01.jpg`) :

```
Réalise l'image d'un portrait illustré d'un personnage de fantasy médiévale, format paysage large. Un ogre, bien plus grand et massif qu'un humain, à la peau épaisse et au teint cuivré, jamais vert, d'une trentaine d'années, sans défenses, le visage large et calme, les cheveux noirs tressés, Templier gardien d'un temple souterrain. Il porte un manteau blanc sur une cotte de mailles, une peau de jaguar tachetée jetée sur les épaules, et tient une grande masse de pierre noire. Il se tient légèrement décalé du centre, un peu courbé sous une voûte basse, et regarde droit vers le spectateur avec la patience de quelqu'un qui garde un passage depuis longtemps. Décor : une salle souterraine aux murs scintillants de pyrite, des flaques de métal liquide argenté au sol, et au fond une arche de pierre noire ornée de têtes de serpents emplumés où tourne un voile de lumière vert jade. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Ils sont en proportions égales : les humains ne sont pas plus nombreux que les autres ; chacun est différent par l'âge, la carrure, les cheveux et la tenue, et les ogres ont des teints humains, jamais verts. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle chaude, palette chaude et terreuse relevée de touches de couleurs vives, proportions crédibles ; pas une photographie. Image entièrement dépourvue d'écriture : aucun nom, aucune lettre, aucune signature, aucun monogramme, aucun filigrane, aucune enseigne lisible.
```

**La Templière du temple du Soleil** (`pnj/templier_hobbit_f_pichao01.jpg`) :

```
Réalise l'image d'un portrait illustré d'un personnage de fantasy médiévale, format paysage large. Une hobbit, toute petite taille d'adulte, à hauteur d'un enfant de huit ans à côté des humains qui passent derrière elle, pieds nus, jeune, ronde et vive, les joues rougies par le froid, les cheveux noirs en deux longues tresses, Templière gardienne d'un temple de montagne. Elle porte un manteau blanc avec un châle de laine aux couleurs vives noué par-dessus, et tend vers le spectateur une gourde de cuir avec un sourire. Elle se tient légèrement décalée du centre et regarde droit vers le spectateur. Décor : des terrasses de pierre accrochées à une montagne verte et abrupte, une tour de pierre courbe aux blocs ajustés, des lamas, et une mer de nuages en contrebas. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Ils sont en proportions égales : les humains ne sont pas plus nombreux que les autres ; chacun est différent par l'âge, la carrure, les cheveux et la tenue, et les ogres ont des teints humains, jamais verts. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle chaude, palette chaude et terreuse relevée de touches de couleurs vives, proportions crédibles ; pas une photographie. Image entièrement dépourvue d'écriture : aucun nom, aucune lettre, aucune signature, aucun monogramme, aucun filigrane, aucune enseigne lisible.
```

**Le Templier du Petit Temple** (`pnj/templier_elfe_m_abou_simbel01.jpg`) :

```
Réalise l'image d'un portrait illustré d'un personnage de fantasy médiévale, format paysage large. Un elfe aux oreilles longues et pointues, élancé, d'apparence ancienne, mort-vivant fort bien conservé : sa peau est sèche, brune et fine comme un parchemin, mais ses yeux sont parfaitement vivants et attentifs. Templier gardien d'un temple taillé dans la falaise, il porte un manteau blanc sur une cuirasse dorée, un large collier d'or et de lapis, et tient une lance à pointe de bronze. Il se tient légèrement décalé du centre et regarde droit vers le spectateur avec une courtoisie lente, comme on reçoit un invité qu'on sait de passage. Décor : une salle à piliers carrés surmontés de visages de femme aux oreilles de vache, des bas-reliefs peints sans aucun hiéroglyphe lisible, des lampes à huile, et au fond une arche de pierre ocre où tourne un voile de lumière bleu froid. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation ; plusieurs sont des morts-vivants bien conservés, vêtus de lin blanc. Ils sont en proportions égales : les humains ne sont pas plus nombreux que les autres ; chacun est différent par l'âge, la carrure, les cheveux et la tenue, et les ogres ont des teints humains, jamais verts. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle chaude, palette chaude et terreuse relevée de touches de couleurs vives, proportions crédibles ; pas une photographie. Image entièrement dépourvue d'écriture : aucun nom, aucune lettre, aucune signature, aucun monogramme, aucun filigrane, aucune enseigne lisible.
```

### 5. Lieux propices à de nouveaux portails
« Alimenté » au sens du jeu : **tout lien `portail` nourrit le tableau des seuils de Notre-Dame** (`utils/portails.py`) — chaque porte créée ajoute deux points d'arrivée possibles depuis Lutecia. Avant cette séance, le tableau n'en avait que quatre (Khazneh, Alexandrie, ad-Deir, Bucarest). Côté coût : une porte **d'un frère** ne consomme rien, une porte **d'héritier** demande des cristaux (Auteur, 11/10) — sources en jeu : mine d'Auxerre, catacombes de Lutecia et puits de Chartres (jaunes), trésor de Petra (violet).

Classés du plus prêt au moins prêt (✍️ = portail déjà décidé par l'Auteur ; 🗺 = les deux bouts existent au dump avec une carte) :

1. **Akureyri → Reykjavik** ✍️🗺 — forteresse-portail des Templiers, active mais **altérée** par la Vague, passages instables scellés (tableau du 26/08). Les deux cités ont leur carte ; il manque la forteresse à Akureyri et un temple d'arrivée (Hallgrímskirkja, bâtiment partagé Templiers/Paladins). Bon terrain pour une porte « qui vacille ».
2. **Bucarest et Alexandrie, côté arrivée** ✍️🗺 — les portes de Petra y débouchent en pleine rue. Même traitement qu'Aix : un **Sérapéum** à Alexandrie (nommé dans le texte de la Khazneh) et un temple à Bucarest, chacun avec son Templier.
3. **Rome — Château Saint-Ange** ✍️🗺 — portail transversal actif de la papauté (destination non dite). Rome a sa carte mais aucun lieu intérieur. Bout naturel de **Sainte-Sophie ↔ Rome**, la « grande artère » (Constantinople à créer).
4. **Bruges — Notre-Dame de Bruges** ✍️🗺 — portail **commercial** qui a résisté à la Vague, vers « d'autres lieux réels ». Bruges a sa carte, rien dedans. Destination à arbitrer ; **piste proposée** : un comptoir de la Hanse — **Londres** (au dump, 12 liens) ou Novgorod (refuge des lamies).
5. **Aix — Hôtel de Ville → cités sœurs** ✍️ — réseau de Charlemagne, aucun vers un donjon. Le lieu et son chancelier existent ; il manque les cités germaniques (aucune au dump). **Pistes** : Cologne, Mayence, Trèves, Worms, Ingelheim.
6. **Petra — Qasr al-Bint → Muziris** ✍️ — le seuil existe sans connexion ; il manque Muziris (cité-État d'Inde, à créer).
7. **Pichao** ✍️ — la porte est posée, la cité manque (carte à faire) : le temple restera un cul-de-sac d'ici là.
8. **Sans lore, mais cartes prêtes** : Melbourne (Australie, pays des frères), Pékin, Le Caire, Lyon, Orléans. Aucun portail n'y est évoqué — ⚠️ aucune ville n'a **forcément** un portail (Auteur, 22/10) : à n'ouvrir qu'avec une raison d'être.
9. **Décidés mais sans lieu au dump** : Constantinople (Sainte-Sophie, Grand Palais), Cordoue (Mezquita, Nœud des Mille Portails), Venise (Saint-Marc diplomatique, Frari et San Zanipolo), Gênes (San Lorenzo), Jérusalem (héritage de Salomon).
