# La bête de Dun-les-Places — l'enquête du rang E

- **Source :** séance Claude Code du 14/10/2026 ; l'Auteur arbitre par questionnaire (§ 1), après le sixième arbitrage des loups-garous (`docs/lore/monde/20261014_les_loups_garous_de_telluris.md` : enquête du rang E dans le **Morvan**, scénario validé).
- **Créée :** 14/10/2026
- **Statut :** le § 1 **fait foi** (noms, récompense compris) ; les textes de dialogue sont **proposés**. Contenu en jeu : `dev/gen_enquete_morvan.py` → `jsons/enquete_morvan_a_importer.json`. ⚠️ La grille de la clairière est un **brouillon** tant que la carte de combat n'est pas livrée : elle se recale sur l'image (§ 4).

---

## 1. Arbitrage (Auteur, 14/10, questionnaire)

| Point | Décision |
|---|---|
| Rang | premier lycanthrope de l'aventurier, au **rang E**, par une **enquête** (modèle du Gévaudan) |
| Donneur | **Borin Barbe-de-Jais**, au comptoir du Bastion de l'Yonne (le bureau de Gautier reste au rang D) |
| Garde de rang | nouvelle **condition de dialogue `rang_min`** (`{cite, rang}`, même comparateur que les barrières) : l'offre n'apparaît qu'au **rang E** à Auxerre |
| Issues | **combat + doute**, 100 % donnée : un loup-garou à combattre, les trois dénouements vivent dans les dialogues d'après |
| Preuve | **la tête** (`item:loup_garou_tete`), comme les primes au loup d'autrefois ; la carcasse trop lourde tombe au sol, on la découpe avec une lame |
| Village | **Dun-les-Places**, hameaux du haut Morvan, charbonniers et flotteurs de bois |
| Combat | la **clairière du charbonnier** : meules fumantes, cabane, souches, pleine lune ; carte neuve |
| Ennemis | **un seul loup-garou** (salle à espèce unique, grade bas) |
| PNJ | **Margot Gueneau** (bergère, hobbit) · **Pierre Chaumereuil**, dit le Gros-Pierre (charbonnier, ogre) · **la vieille Jacotte** (meneuse de loups, elfe) — validés |
| Récompense | **70 XP + 8 000 cuivres** |
| Doute, après le combat | le **charbonnier a disparu** · « **ce n'était qu'un loup** » (la meneuse) · le **nom qui n'a pas été dit** (jamais révélé) · les **troupeaux en paix**, la bergère a son coupable sans certitude |

## 2. Scénario

**Chaîne :**
1. **Comptoir du Bastion de l'Yonne.** Au rang E, Borin propose la quête d'apport `quete:la_bete_de_dun_les_places` : une bête décime les troupeaux de Dun-les-Places, puis a tué un berger. « Rapporte-moi sa tête. » Quête unique.
2. **Dun-les-Places.** Lieu sur la carte de France, au sud-est d'Auxerre, dans le Morvan (France (52,22)). Trois PNJ : la bergère et la meneuse toujours là ; le charbonnier **tant que la clairière n'a pas été gagnée**.
3. **La clairière du charbonnier.** Salle gardée (`battle_map` + `donjon:clairiere_du_charbonnier`). La meneuse y conduit l'aventurier la nuit (service `acces`) tant que la tête reste **à rapporter** — si la tête est perdue, elle l'y reconduit, et une bête l'y attend encore (aucune impasse). Un loup-garou.
4. **Retour au comptoir.** Le joueur remet la tête à Borin : 70 XP, 8 000 cuivres.
5. **Après.** Le charbonnier ne revient pas ; la meneuse jure que ce n'était qu'un loup, puis regrette qu'on ne l'ait pas appelé par son nom ; la bergère a son coupable, les troupeaux sont en paix. Rien ne tranche.

**PNJ (validés) :**

| Rôle | Lignée | Nom | Ce qu'il croit |
|---|---|---|---|
| Bergère | hobbit | Margot Gueneau | Son frère, berger, a été tué. Elle a vu « un loup trop grand, qui marchait mal ». Elle accuse le Gros-Pierre et son bras bandé. |
| Charbonnier | ogre | Pierre Chaumereuil, dit le Gros-Pierre | Il nie, bourru : le bandage vient d'une meule effondrée. Les nuits de pleine lune, il ne dort pas — « personne ne dort, ici ». Disparu après le combat. |
| Meneuse de loups | elfe | la vieille Jacotte | Elle joue de la musette, les loups la suivent. « Ce n'est pas un des miens. » Elle connaît le vrai nom de chacun et ne le dit pas. Elle mène à la clairière. |

**Le nom** : la meneuse connaît le nom de la bête, si c'en est une ; il n'est **jamais** dit (Auteur).

## 3. Prompts d'images à produire

Chaque prompt est **complet**, bloc de style compris : il se copie-colle tel quel (Auteur, 13/10).

### 3.1 Carte de combat — la clairière du charbonnier

Fichier : `templates/resources/battle_maps/clairiere_du_charbonnier.jpg` · format **paysage 16:9**.

> Carte de combat de jeu de rôle tactique, vue strictement du dessus, format paysage. Une clairière au cœur d'une forêt profonde de chênes et de hêtres, de nuit, sous la pleine lune. La forêt dense ferme tous les bords de l'image ; un sentier de terre entre par le bas. Au centre, de la terre noire et battue, couverte de poussière de charbon. Trois meules de charbon de bois en forme de dômes de terre, qui fument doucement par de petits trous. Une cabane de charbonnier en rondins et en mottes de terre, au nord-est. Des souches, des tas de bûches empilées, une hache plantée dans un billot. Des traces de griffes dans la terre, quelques brins de laine de mouton accrochés aux ronces. Lumière bleue et froide de la lune, lueurs rouges sous les meules. Un quadrillage fin et régulier de cases carrées couvre toute l'image, et une petite flèche indique le nord en haut à droite. Pas de personnages. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.

### 3.2 Le village de Dun-les-Places

Fichier : `templates/resources/towns/dun_les_places.jpg` · **paysage 16:9**.

> Un hameau du haut Morvan, dans un monde médiéval fantastique : quelques maisons basses de granit gris aux toits de chaume, serrées derrière une palissade de pieux, au creux de collines couvertes d'immenses forêts sombres. Des troupeaux de moutons dans un enclos aux pieux renforcés, une bergerie dont la porte a été arrachée, des piles de bûches et de charbon de bois, de la fumée de meules qui monte au loin entre les arbres. Fin de journée d'automne, brume dans les vallons. Des villageois inquiets regardent la lisière. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. En proportions égales, les humains ne sont pas plus nombreux que les autres. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.

### 3.3 Portraits (dossier `templates/resources/pnj/`, paysage 16:9)

Le nom du personnage ne figure jamais dans un prompt (§ 2 de `docs/prompts_images.md`).

- **`bergere_Margot_Gueneau_hobbit_f.jpg`** — Une hobbit, toute petite taille d'adulte, pieds nus, jeune, cheveux bruns bouclés sous un fichu, joues rondes et yeux rougis. C'est une bergère d'un hameau de forêt. Elle se tient devant un enclos de moutons, une houlette à la main, un brassard de deuil noir au bras. Regard dur, en colère, qui cherche un coupable. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle chaude, palette chaude et terreuse relevée de touches de couleurs vives, proportions crédibles ; pas une photographie. Image entièrement dépourvue d'écriture : aucun nom, aucune lettre, aucune signature, aucun monogramme, aucun filigrane, aucune enseigne lisible.
- **`charbonnier_Pierre_Chaumereuil_ogre_m.jpg`** — Un ogre, colossal, nettement plus grand et plus massif qu'un humain, petites défenses pointant de la lèvre inférieure (ni orc ni troll), d'âge mûr, peau et barbe noircies de suie, tablier de cuir brûlé. C'est un charbonnier de forêt. Il se tient près d'une meule de charbon qui fume, une pelle à la main, l'avant-bras gauche entouré d'un bandage frais. Regard bourru et méfiant, sur la défensive. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle chaude, palette chaude et terreuse relevée de touches de couleurs vives, proportions crédibles ; pas une photographie. Image entièrement dépourvue d'écriture : aucun nom, aucune lettre, aucune signature, aucun monogramme, aucun filigrane, aucune enseigne lisible.
- **`meneuse_de_loups_Jacotte_elfe_f.jpg`** — Une elfe aux longues oreilles pointues, très vieille pour une elfe, maigre et droite, longs cheveux blancs dénoués, manteau de laine grise rapiécé. C'est une meneuse de loups des forêts. Elle tient une musette (petite cornemuse de bois et de peau) contre elle, au bord d'un bois sombre ; derrière elle, entre les arbres, luisent les yeux de deux loups calmes. Regard perçant, qui sait des choses qu'elle ne dira pas. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle chaude, palette chaude et terreuse relevée de touches de couleurs vives, proportions crédibles ; pas une photographie. Image entièrement dépourvue d'écriture : aucun nom, aucune lettre, aucune signature, aucun monogramme, aucun filigrane, aucune enseigne lisible.

## 4. À faire une fois les images livrées

- Recaler `GRILLE_CLAIRIERE` de `dev/gen_enquete_morvan.py` sur la carte de combat (dimensions, arbres, meules, cabane), relancer le générateur, réimporter.
- Les images du village et des portraits n'exigent rien d'autre que leur dépôt aux noms ci-dessus.
