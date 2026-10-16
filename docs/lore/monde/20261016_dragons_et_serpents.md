# Dragons et serpents des mythes — huit entrées du bestiaire

- **Source :** séance Claude Code du 16/10/2026. L'Auteur montre une planche de huit dragons et serpents des mythes (Tiamat, Ladon, Mušḫuššu, Illuyanka, Yamata no Orochi, Apophis, Zmey Gorynych, Quetzalcoatl) et demande leur mythologie, leur correspondance dans le bestiaire, puis des créations.
- **Créée :** 16/10/2026
- **Statut :** l'arbitrage de l'Auteur (§ ✍️ deuxième message) **fait foi** ; les descriptions et lieux proposés ici sont **proposés, non tranchés** tant que l'Auteur ne les a pas repris. Bestiaire en jeu : `dev/gen_dragons_serpents.py` → `jsons/dragons_serpents_a_importer.json`.

---

## ✍️ Auteur

Quels seraient les monstres du bestiaire, les espèces du bestiaire qui correspondraient à ces monstres ? Est-ce que ça serait pas intéressant d'en créer pour certains ? Mais il faut que tu m'expliques d'abord leur mythologie. Pour certains, créer des monstres uniques qui correspondraient. C'est une entrée dans le bestiaire, et puis voilà.

## 🤖 Claude Code — les mythes

- **Tiamat** (Mésopotamie, *Enûma Eliš*) : l'eau salée primordiale, face à Apsû l'eau douce. Apsû tué, elle enfante **onze monstres** (hommes-scorpions, hommes-lions, serpents cornus, le Mušḫuššu…) ; Marduk la vainc et la fend en deux pour faire le ciel et la terre. Sa forme n'est pas décrite : le dragon (et la Tiamat à cinq têtes) est moderne. Sur Telluris, Marduk ne l'a pas détruite, il lui a **imposé un ordre** (`cites/20260819_histoire_de_babylone.md`).
- **Ladon** (Grèce) : serpent aux **cent têtes et cent voix** enroulé autour de l'arbre aux pommes d'or des **Hespérides**, à l'extrême Ouest, près d'Atlas ; tué par Héraclès (flèches au venin de l'hydre de Lerne) ou contourné par Atlas ; Héra en fait la constellation du Dragon. Parents : Typhon et **Échidna**, ou Phorcys et **Cétô**.
- **Mušḫuššu** (Babylone) : « serpent furieux » — tête de serpent cornue, pattes avant de lion, pattes arrière d'aigle, dard de scorpion ; un des onze de Tiamat, **dompté par Marduk** dont il devient l'animal ; sur la **porte d'Ishtar**. Emblème de Marduk : la bêche (*marru*).
- **Illuyanka** (Hittites) : serpent-dragon qui bat le dieu de l'orage. Version 1 : la déesse Inara dresse un **festin**, le serpent gavé ne repasse plus par son trou, le mortel Hupasiya le ligote. Version 2 : il prend le **cœur et les yeux** du dieu, que le fils du dieu reprend en épousant la fille du serpent. Fête de printemps (*purulli*).
- **Yamata no Orochi** (Japon, *Kojiki*) : **huit têtes, huit queues**, long de huit vallées et huit collines, cyprès sur le dos, yeux rouges comme des cerises d'hiver ; il dévore chaque année une fille d'un couple d'Izumo. Susanoo l'enivre de **saké huit fois brassé** et le tranche ; dans une queue, l'épée **Kusanagi**.
- **Apophis / Apep** (Égypte) : serpent du chaos qui assaille chaque nuit la **barque de Râ** dans la Douat ; Seth le repousse ; les prêtres brûlent son **nom écrit** et des figurines de cire (*Livre du renversement d'Apophis*). Repoussé, jamais tué ; éclipses et orages sont ses assauts. Déjà en jeu : `espece:apep`.
- **Zmey Gorynych** (Slaves orientaux) : dragon à **trois têtes** (ou plus) cracheur de feu, têtes qui repoussent ; garde le **pont Kalinov** sur la **Smorodina**, rivière de feu, frontière du monde des morts ; enlève la nièce du prince de Kiev ; vaincu par Dobrynia Nikititch (la terre refuse de boire son sang). Cousin du **balaur** roumain.
- **Quetzalcoatl** (Mésoamérique) : le **serpent à plumes**, dieu du vent et du savoir ; temple à Teotihuacan ; roi-prêtre toltèque exilé vers l'Est qui promit de revenir ; **Kukulkan** chez les Mayas. Un dieu, pas un monstre. Son pendant monstrueux : **Xiuhcóatl**, le serpent de feu turquoise, arme de Huitzilopochtli à Coatepec.

Correspondances en jeu avant la séance : `leviathan` (Tiamat, de loin), `hydre` (Ladon, Orochi, Zmey), `dragon`, `serpent_geant` (Illuyanka), `apep`. Le **balaur**, canon depuis le 13/10 (le monstre de Vlad), n'avait pas d'entrée.

## ✍️ Auteur — arbitrage

Xiuhcoatl à ajouter. Dragon hydre à ajouter.
2. Faiblesses potentielles, pas nécessairement uniques. Non réelles, uniquement description.
3. Un prompt par nouvelle entrée dans le bestiaire.

## 1. Décisions

- **Espèces neuves** : `balaur` · `dragon_hydre` · `mushhushshu` (affiché « Mušḫuššu ») · `xiuhcoatl` (« Xiuhcóatl »).
- **Êtres uniques, boss** : `zmey_gorynych` (« Zmeï Gorynytch ») · `ladon` · `yamata_no_orochi` · `illuyanka`.
- **Apep** : description enrichie de son mythe égyptien, caractéristiques inchangées.
- **Hors bestiaire** : Tiamat (puissance primordiale) et Quetzalcoatl (dieu).
- **Faiblesses** : dans la **description seule**, aucune mécanique, et pas forcément propres à un être (le feu sur le cou tranché vaut pour le balaur comme pour le dragon-hydre).
- Proposé, non tranché : le pont Kalinov « mène au pays des morts » (rumeur, jamais confirmée) ; le jardin des Hespérides « au-delà des Colonnes, aperçu au couchant » ; les parents de Ladon disputés (Cétô ou Échidna).

## 2. Prompts d'image

Un par entrée neuve (Auteur) ; fichier détouré `templates/resources/monsters/<slug>_transparent.png`, carré 1:1 (`docs/prompts_images.md` § 3).

**`balaur`**
```
Réalise l'image d'un Balaur, dragon-serpent des Carpates : long corps de serpent aux écailles vert-de-gris et bronze, quatre pattes griffues, grandes ailes de cuir, sept têtes de serpent cornues sur sept cous ondulants, gueules ouvertes d'où coule une bave qui scintille comme des gemmes. Elle est en vol, ailes déployées. Attitude de chasse, griffes et crocs visibles, regard fixé sur sa proie. La créature occupe environ 80 % de l'image, entière, sans membre coupé par le cadre, en vue de trois-quarts. Fond parfaitement uni et plat, bleu vif pur, sans dégradé, sans décor, sans sol visible, sans ombre portée, sans halo — la créature ne doit contenir aucune touche de cette couleur. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**`dragon_hydre`**
```
Réalise l'image d'un Dragon-hydre : dragon sans ailes au corps massif et trapu sur quatre pattes puissantes, écailles brun-noir, ventre ocre, longue queue épaisse ; six longs cous jaillissent de ses épaules, chacun terminé par une tête de dragon cornue, deux d'entre elles crachant des flammes orangées ; un moignon de cou cautérisé, noirci. Attitude de chasse, griffes et crocs visibles, regard fixé sur sa proie. La créature occupe environ 80 % de l'image, entière, sans membre coupé par le cadre, en vue de trois-quarts. Fond parfaitement uni et plat, magenta pur, sans dégradé, sans décor, sans sol visible, sans ombre portée, sans halo — la créature ne doit contenir aucune touche de cette couleur. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**`mushhushshu`**
```
Réalise l'image d'un Mušḫuššu, le dragon de Babylone : corps mince couvert d'écailles ocre et or, long cou, tête de serpent coiffée de deux cornes droites et d'une crête, langue fourchue, pattes avant de lion, pattes arrière d'aigle à serres, queue dressée terminée par un dard de scorpion. Attitude de chasse, griffes et crocs visibles, regard fixé sur sa proie. La créature occupe environ 80 % de l'image, entière, sans membre coupé par le cadre, en vue de trois-quarts. Fond parfaitement uni et plat, magenta pur, sans dégradé, sans décor, sans sol visible, sans ombre portée, sans halo — la créature ne doit contenir aucune touche de cette couleur. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**`xiuhcoatl`**
```
Réalise l'image d'un Xiuhcóatl, serpent de feu des Mexicas : long corps de serpent fait d'anneaux d'écailles turquoise cerclés d'ocre, museau retroussé en volute, deux courtes pattes avant, queue terminée par une gerbe de flammes ; des braises et des flammes orangées courent le long de son dos. Attitude de chasse, griffes et crocs visibles, regard fixé sur sa proie. La créature occupe environ 80 % de l'image, entière, sans membre coupé par le cadre, en vue de trois-quarts. Fond parfaitement uni et plat, magenta pur, sans dégradé, sans décor, sans sol visible, sans ombre portée, sans halo — la créature ne doit contenir aucune touche de cette couleur. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**`zmey_gorynych`**
```
Réalise l'image de Zmeï Gorynytch, le dragon à trois têtes des terres de Kiev : corps de dragon dressé sur deux pattes arrière puissantes, écailles vert olive et bronze, griffes de fer sombre, grandes ailes de cuir, trois têtes cornues sur trois cous, celle du milieu crachant un jet de feu. Elle est en vol, ailes déployées. La créature occupe environ 80 % de l'image, entière, sans membre coupé par le cadre, en vue de trois-quarts. Fond parfaitement uni et plat, bleu vif pur, sans dégradé, sans décor, sans sol visible, sans ombre portée, sans halo — la créature ne doit contenir aucune touche de cette couleur. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**`ladon`**
```
Réalise l'image de Ladon, le serpent gardien du jardin des Hespérides : immense serpent aux écailles vert sombre et or, sans pattes, dont le corps se divise en une multitude de cous terminés par des dizaines de petites têtes de serpent, toutes éveillées, les yeux grands ouverts, gueules entrouvertes ; ses anneaux sont enroulés sur eux-mêmes comme autour d'un tronc absent. La créature occupe environ 80 % de l'image, entière, sans membre coupé par le cadre, en vue de trois-quarts. Fond parfaitement uni et plat, bleu vif pur, sans dégradé, sans décor, sans sol visible, sans ombre portée, sans halo — la créature ne doit contenir aucune touche de cette couleur. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**`yamata_no_orochi`**
```
Réalise l'image de Yamata no Orochi, le serpent d'Izumo : colossal serpent sans pattes aux écailles rouge sombre, à huit têtes de serpent cornues sur huit longs cous et huit queues, yeux rouge vif comme des cerises d'hiver, ventre luisant de sang, mousse et petits cyprès poussant sur son dos. Attitude de chasse, crocs visibles, regard fixé sur sa proie. La créature occupe environ 80 % de l'image, entière, sans membre coupé par le cadre, en vue de trois-quarts. Fond parfaitement uni et plat, bleu vif pur, sans dégradé, sans décor, sans sol visible, sans ombre portée, sans halo — la créature ne doit contenir aucune touche de cette couleur. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

**`illuyanka`**
```
Réalise l'image d'Illuyanka, le serpent-dragon des montagnes d'Anatolie : énorme serpent trapu aux écailles brun-gris couleur de roche, sans ailes, tête massive de dragon aux mâchoires lourdes et aux petits yeux avides, ventre gonflé de festin, corps lové sur lui-même comme pour s'enfoncer dans un trou de la montagne. La créature occupe environ 80 % de l'image, entière, sans membre coupé par le cadre, en vue de trois-quarts. Fond parfaitement uni et plat, magenta pur, sans dégradé, sans décor, sans sol visible, sans ombre portée, sans halo — la créature ne doit contenir aucune touche de cette couleur. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```
