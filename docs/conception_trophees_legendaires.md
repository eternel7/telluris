# Trophées et matières des chasses légendaires — cahier des charges

Décisions de l'Auteur (questionnaires du 13/11/2026). Livraison **en une seule passe** : moteur + contenu, **un seul** `jsons/trophees_legendaires_a_importer.json`.

## Constat (dump du 13/11)

- 267 parties de carcasse `rare`/`tres_rare`/`legendaire`. **230 sans bloc `fabrication`** : 137 parties entières sur ~35 espèces et 93 morceaux de découpe. Elles ne servent qu'à la boucherie et au dépeçage générique.
- 16 recettes à trophée (`gen_trophees.py`) ; le moteur sur mesure (`commande` / `fabrication`) et les trophées (`marche.cles_trophee`) existent déjà.
- Les armures n'ont **aucun matériau** (sous-catégorie vide, aucun tag).
- **Aucun objet ne donne de compétence** : les grimoires apprennent un sort, rien n'est accordé par le port.

## 1. Sur mesure — toutes les parties rare+

- Bloc `fabrication` + tags `fabrication_*` sur les 137 parties ET sur leurs morceaux (**même bloc** : un morceau suffit, la partie entière reste utilisable).
- Budget : **barème existant** `gen_fabrication_matieres.score_matiere` (palier de l'espèce).
- Tags par partie, inchangés : tête → arme + armure, bras/patte/queue → arme, aile → armure + catalyseur, corps → armure + consommable.

## 2. Matières raffinées nommées — les ~35 espèces rare+

- Le `depecage` rend une matière **propre à l'espèce** (Écailles de Dragon rouge, Cuir de Tarasque, Soie d'aile de Séraphin, Os de Léviathan, Sang de Grand Phénix…) **à la place** du générique correspondant.
- Chaque matière porte son bloc `fabrication` (≈ 80 % du budget de sa partie : elle est plus légère) et ses tags matériau d'armure (§ 3).
- ⚠️ Contrôle de flux : une matière nommée n'est jamais une feuille livrée (pas de vente au comptoir, rachat par le négociant seul).

## 3. Matériau d'armure — tags

- Pose de `armure_tissu` / `armure_cuir` / `armure_metal` sur les 263 armures (générateur, table relue sur le nom et les bonus de PA ; bijoux et harnachement exclus).
- Moteur : `commande.tags_fabrication` ajoute `fabrication_<tag matériau>` → une matière `fabrication_armure_metal` n'entre que dans le métal. Filtre « matière » de l'overlay ✨ inchangé.
- Exemples : écailles draconiques → métal + cuir ; soies et plumes → tissu ; cuirs de bête → cuir.

## 4. Trophées 🏆 nommés (recettes à trophée)

Budget du barème ; `valeur` = variante sur mesure du socle. Trophée = la partie OU son morceau.

| Famille | Pièces | Maison |
|---|---|---|
| Lames draconiques | Épée-croc de Dragon rouge, Faux d'os de Dragon blanc, Glaive-écaille de Dragon empereur, Hache-mâchoire de Balaur | grand_arsenal |
| Bête légendaire | Masse-dard de Tarasque, Lance-défense de Twrch Trwyth, Fléau-griffe de Bête du Gévaudan, Arc-tendon de Cath Palug | grand_arsenal / empenneur |
| Abysses | Trident-bec de Kraken, Harpon-épine de Léviathan, Fouet-tentacule de Kraken polaire, Dague-dent de Grootslang | grand_arsenal / manufacture du cuir |
| Céleste / infernal | Épée-plume de Séraphin, Sceptre-corne de Prince démon, Lance-aile d'Archange de l'Ordre, Massue de Géant du Mont-Saint-Michel | grand_arsenal |
| Armure métal | Heaume-crâne de Dragon rouge, Cuirasse d'écailles de Dragon empereur, Pavois de Tarasque (existant, complété), Gantelets-griffes de Balaur | grand_arsenal |
| Armure cuir | Brigandine en peau de Léviathan, Bottes de Vers des sables, Jaque de Twrch Trwyth, Cape-ailes de Zmey Gorynych | grande_manufacture_du_cuir |
| Armure tissu | Robe de soie de Séraphin, Manteau de plumes de Grand Phénix, Capuche-écaille d'Illuyanka, Étole de Gwyn ap Nudd | grande_manufacture_textile |
| Bijoux / catalyseurs | Œil de Ladon serti, Cœur de Dragon cristallisé (focus), Bâton-vertèbre d'Hydre, Orbe-œil d'Avatar | grande_orfevrerie / laboratoire |

Élixirs (grand_laboratoire_alchimique), sur le modèle de l'Élixir de sang de dragon : sang, cœur ou yeux des espèces rare+ → un élixir par espèce phare.

## 5. Compétence accordée par un objet porté (moteur neuf)

- Champ item `competences: ["sort:souffle_de_feu", …]` (ids de **sorts ou compétences existants**, jamais de capacité neuve).
- Actif **tant que l'objet est équipé** : apparaît dans ⚡ et dans la barre de combat, sans être appris ; retirer l'objet le retire (slot de barre conservé, grisé ; cf. `slots_effectifs`).
- **Hors vocation autorisé** ; coûts PM/PA normaux.
- **Exigence de caractéristique** : le pouvoir ne s'éveille que si la `restriction` de l'objet est satisfaite (lue BRUT, convention 3).
- Pouvoirs de l'espèce : Souffle de feu (Dragon rouge), Regard glacial (Dragon blanc), Envol du griffon (pièces d'ailes), Terreur (Bête du Gévaudan), Raz-de-marée (Léviathan), Souffle de soufre (Prince démon), Main de venin (Grootslang)… Réservés aux trophées `tres_rare`/`legendaire`.

## 6. Panoplie d'espèce (moteur neuf)

- 2 ou 3 trophées portés d'une même `source_espece` → bonus de panoplie, déclaré dans `rules:panoplies` (`{espece, seuils: {2: {...}, 3: {...}}}`), calculé **à la lecture** comme `sync_equipment_bonus` (fiche + combat), jamais stocké.

## 7. Trophée signé du chasseur

- Le loot d'une espèce rare+ inscrit sur la **référence** `chasse: {par, espece, quand}`, à côté du grade que `combat.ref_de_butin` y pose déjà (#313) ; il suit la portion → morceau → pièce fabriquée (comme `nom_perso` via `ref_livree`).
- Affiché sur la fiche objet ; un collectionneur (§ 9) paie une prime aux pièces signées.

## 8. Mur des trophées

- Aménagement de propriété (Maison et au-delà, `rules:proprietes`) : y exposer un Spécimen monté d'une espèce rare+ donne un `effets` de réveil après une nuit chez soi (non cumulatif, mécanisme existant).

## 9. Collectionneurs et commandes de guilde

- PNJ collectionneur (service `vente` inversé : rachat d'une liste de parties précises au prix fort + relation).
- Commandes de guilde « rapporter <partie> de <espèce> » : réutiliser le moteur de quêtes de chasse (récompense + rang).

## Garde-fous

- Générateur unique `dev/gen_trophees_legendaires.py`, relu sur le dump, idempotent, **diff seul**, aucune collision d'`_id` ; relance de `gen_fabrication_matieres` / `gen_carcasses_parties` sans effet de bord (convention 11).
- Prix : celui d'une partie suit désormais la dangerosité du spécimen (`utils/xp_monstre.py`, #313) ; le budget de fabrication reste celui du palier d'espèce.
- Anti-arbitrage : les variantes et trophées se rachètent en bande (règle existante).
- Tests : tags matériau (`tags_fabrication`), compétences d'objet (fiche, barre, restriction, déséquipement), panoplie, signature qui suit la ref, aménagement.
