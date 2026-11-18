# La furtivité — tout le système

- **Rédigé le :** 18/11/2026, d'après le code en jeu (`utils/combat.py`, `utils/competences.py`, `utils/donjon.py`, `utils/simulateur.py`, `utils/bruit.py`) et le dump du 17/11/2026.
- **Statut :** description de ce qui **tourne**, pas une proposition. Les chiffres sont les valeurs par défaut ; ceux marqués *(variable de monde)* se règlent dans `rules:world_variables`.

En une phrase : **la furtivité est un état de COMBAT**. Un combattant furtif est invisible pour chaque monstre qui ne l'a pas encore repéré ; ce monstre doit réussir un jet de détection avant de venir à lui, et tout coup porté à un monstre qui ne l'a pas repéré est un coup critique. Hors combat, la furtivité n'existe pas — ce qui en tient lieu est le **bruit du groupe** (§ 9).

---

## 1. Les deux valeurs qui portent l'état

Chaque combattant du camp du joueur porte, dans son instantané de combat :

| Champ | Sens |
|---|---|
| `furtif` | vrai = caché. Faux par défaut. |
| `furtivite_bonus` | le bonus de dissimulation, qui s'ajoute à l'Agilité dans la difficulté du jet de détection (§ 3). |

Chaque monstre porte un drapeau **`detecte`** : « j'ai repéré les furtifs ». ⚠️ Ce drapeau est **par monstre**, pas par couple monstre-joueur : un monstre qui a repéré un membre du groupe voit **tous** les membres furtifs.

## 2. Comment on devient furtif

Entrer en furtivité ne demande **aucun jet** : soit c'est automatique à l'entrée du combat, soit cela coûte une action. Toute la difficulté est reportée sur le jet de détection des monstres (§ 3).

### 2.1 À l'entrée d'un combat — les passives

`competences.furtivite_passive` parcourt les compétences **passives** connues du personnage :

- une passive **sans condition** qui porte `furtivite` (Ombre incarnée, Présence effacée) vaut **partout** ;
- une passive **à condition de terrain** (`condition.battle_map_tags`) ne vaut que si l'un de ses tags figure parmi les tags du terrain, c'est-à-dire **tags de la battle map ∪ tags des zones actives** du lieu ;
- une passive qui exige une arme (`arme`) ne vaut que si l'arme est portée ;
- s'il y a plusieurs sources, on prend le **MAXIMUM**, jamais la somme : on n'est pas « plus caché » en empilant deux dissimulations. Une échelle de passives de furtivité ne vaut que sa meilleure marche.

Résultat > 0 ⇒ le combattant entre `furtif` avec ce bonus. L'état est posé **avant** l'ordre d'initiative : un monstre plus rapide tente sa détection dès le premier tour.

Qui en profite, selon le type de combat :

| Combat | Furtivité d'entrée |
|---|---|
| Rencontre de zone (`/api/combat/start`) | **Le personnage principal seul** (v1). Compagnons, montures et escortés entrent **à découvert**. |
| Donjon à étages (entrée et chaque changement d'étage) | **Tout le groupe** entre furtif, à chaque étage : chaque membre qui agit (principal, compagnons) avec **son propre** bonus passif évalué contre les tags de l'étage ; montures et personnes escortées furtives **avec un bonus de 0**. Les monstres de l'étage n'ont encore repéré personne. |
| Donjon simple (salle de `_declencher_combat_donjon`), escalier gardé d'un PNJ | **Aucune** : on descend par un passage gardé, annoncé, pas en embuscade. |
| Gardien d'un lieu (`combat_arrivee`, ex. sommet du Mont) | Aucune. |
| Défense d'une implantation (colonisation) | Aucune. |

### 2.2 En cours de combat — les actives et les sorts

Toute capacité dont `effets.furtivite > 0` (compétence active ou sort), lancée **sur soi** ou **sur un allié** :

- coûte **une action** (+ son coût en PM, + composants pour un sort) ;
- pose `furtif` sur sa cible ;
- fixe son bonus à **max(bonus actuel, valeur de la capacité)** ;
- **efface la détection de TOUS les monstres** : chacun doit réussir un nouveau jet (sauf les insensibles, § 6).

Une dissimulation lancée sur un allié dissimule **cet allié** et remet aussi la détection de tous les monstres à zéro.

⚠️ La furtivité n'a **pas de durée**. Le `duree` d'un sort comme *Zone de silence* ne règle que sa part à durée (l'esquive) : l'état furtif, lui, tient jusqu'à ce qu'il soit rompu (§ 5).

⚠️ Une fois révélé, le bonus retombe à **0**. Se refondre avec *Furtivité* (assassin, +1) redonne l'état, mais avec un bonus de **1**, pas les 20 d'*Ombre incarnée* : la passive ne joue qu'à l'entrée du combat (ou d'un étage).

## 3. Le jet de détection

Un monstre qui ne voit **aucune** cible (tous les joueurs vivants sont furtifs et il ne les a pas repérés) tente, **au début de son tour**, un jet de détection contre le furtif **le plus proche**. Le jet est un d100 : **jet ≤ seuil = repéré**.

```
seuil = 50 + compétence du monstre − difficulté          (borné à [5, 95])

compétence du monstre = Vol                 si Vol > 0
                      = Int − 10            sinon, si Int > 0   (créature sans volonté)
                      = Ag − 30             sinon               (créature sans intelligence)

difficulté = Ag du furtif + furtivite_bonus + 5 × distance en cases
```

- **Ag du furtif** : l'Agilité de l'instantané de combat, donc **avec** les bonus d'équipement, des compétences passives et des effets en cours (l'Ag +12 d'*Ombre incarnée*, l'Ag +2 d'une *Lame courte* comptent).
- **Distance** : Chebyshev (les diagonales comptent pour 1), entre emprises pour les grands jetons. Le facteur 5 est `DETECTION_DISTANCE_FACTEUR` *(variable de monde)*.
- **Bornes** : il reste toujours au moins **5 %** de chance d'être repéré, et au plus 95 %.
- **Une réussite est DÉFINITIVE** pour le combat : le monstre garde `detecte` jusqu'à ce qu'une dissimulation (§ 2.2) ou un changement d'étage efface sa mémoire.
- Le journal affiche le jet : « X vous repère ! (jet 23 / seuil 30) ».

### Lecture pratique : chaque point compte pour 1 %

Un point de `furtivite_bonus`, un point d'Agilité ou un cinquième de case retire **1 %** de chance d'être repéré, à chaque jet. Quelques cas, contre un monstre de Vol 40 :

| Furtif | Distance | Difficulté | Seuil (chance d'être repéré par tour) |
|---|---|---|---|
| Ag 40, sans bonus (vient de se cacher avec *Furtivité*, +1) | 4 | 40 + 1 + 20 = 61 | **29 %** |
| Ag 40, *Pas feutrés* (+4) en souterrain | 4 | 64 | **26 %** |
| Ag 40, *Fantôme des bois* (+11) en forêt | 4 | 71 | **19 %** |
| Ag 40, *Zone de silence* (+12, +5 avec Poudre de miroir) | 2 | 40 + 17 + 10 = 67 | **23 %** |
| Ag 52 (40 + 12), *Ombre incarnée* (+20) | 4 | 92 | **5 %** (plancher) |
| Ag 40, *Furtivité* (+1), **adjacent** | 1 | 40 + 1 + 5 = 46 | **44 %** |

Contre une bête sans Vol ni Int (compétence = Ag − 30), le seuil baisse d'autant : une bête d'Ag 50 a une compétence de 20, soit 20 points de moins qu'un monstre de Vol 40. Contre un esprit de Vol 70, il monte de 30.

La chance de **tenir** n tours face à un monstre est (1 − seuil)ⁿ : à 26 %, on tient 3 tours une fois sur 2,5 environ ; à 5 %, une vingtaine de tours en moyenne.

## 4. Ce que la furtivité change au combat

### 4.1 Les monstres ne viennent pas à vous

- **Ciblage** (`_cible_joueur`, seul point de choix de cible de l'IA) : un furtif non repéré est **exclu** des cibles. Le monstre vise les autres joueurs visibles (compagnons, montures, escortés à découvert) **sans tenter de détection** — il ne cherche que s'il ne voit **personne**.
- **Échec du jet** : le monstre ne vient pas. Un **prédateur** (tag `predateur`) chasse la **proie** la plus proche (tag `proie`) avec ses règles d'attaque ordinaires ; la victime ne rapporte pas d'XP mais reste au butin. Les autres **errent** quelques pas au hasard, sans jamais fondre sur vous.
- **Embuscades** (IA `ia_embuscade`) : un embusqué ne se réveille que si un joueur **visible** entre dans son rayon (3 cases par défaut), qu'on l'attaque ou qu'on le provoque. Un furtif non repéré peut passer à côté sans le réveiller.
- **Zones des monstres** : les joueurs que le monstre peut viser pour ses capacités suivent la même règle (un furtif non repéré est invisible).
- **Provocation** : un monstre provoqué vise son provocateur **même furtif** — on ne provoque pas en restant caché.

### 4.2 L'attaque furtive : tout coup qui touche est critique

Un coup est **furtif** si l'attaquant est `furtif` **et** que **cette cible-là** ne l'a pas repéré (`_attaque_furtive`). Le jet d100 reste fait :

| Résultat du d100 | Sans furtivité | En furtivité |
|---|---|---|
| Réussite critique (≤ 5, élargie par la Chance) | dés **×2** | dés **×4** |
| Touché ordinaire (≤ seuil de toucher) | dés ×1 | **critique automatique : ×2** |
| Raté | raté | raté |
| Échec critique (≥ 96, repoussé par la Chance) | une action perdue | une action perdue |

- Les multiplicateurs s'appliquent aux **dés, avant** la soustraction des PA de l'armure.
- Vaut pour l'attaque d'arme, les compétences et les sorts offensifs (jet physique ou magique). Dans une zone d'effet, **chaque** monstre touché est jugé pour lui-même : critique contre ceux qui ne vous ont pas repéré, ordinaire contre les autres.
- **Deux armes** : la furtivité est évaluée **une fois**, avant le premier coup, et profite aux **deux** jets.
- **Jamais** pour le test de concentration (un coup reçu n'est pas un coup porté).
- La fenêtre des critiques glisse avec l'écart de **Chance** (`CRIT_CHANCE_DIVISEUR` 10, bornes `CRIT_REUSSITE_MAX` 5 / `CRIT_ECHEC_MIN` 96, *variables de monde*).

## 5. Ce qui rompt la furtivité

| Action du furtif | Effet |
|---|---|
| Attaque **au corps à corps** (arme, compétence ou sort de contact), touchée **ou** ratée | **Révélation totale** : `furtif` et bonus remis à 0, « X sort de l'ombre : tous les ennemis l'ont repéré ! ». |
| Attaque **à distance** (arme de jet/tir, sort ou compétence dont la portée dépasse 1) | Seule **la cible** tente un jet de détection (même formule, § 3). Les autres monstres restent dans l'ignorance — l'embuscade tient. Cible **tuée** du coup, ou qui l'avait **déjà repéré** : aucun jet. |
| Se déplacer, consommer, ramasser, changer d'arme, se soigner, lancer un soutien sur soi ou un allié | **Rien** : seule une action **offensive** révèle. |
| Payer des PV (`effets.cout_pv`) | Rien : c'est un coût, pas un coup. |

- ⚠️ On ne peut pas tirer quand un ennemi est **adjacent** (« Un ennemi vous menace au corps à corps ») : un archer furtif doit garder ses distances, ce qui l'arrange aussi pour la détection (+5 de difficulté par case).
- Une hallebarde qui frappe à 2 cases reste du **corps à corps** : c'est le drapeau « à distance » de l'arme ou de la capacité qui décide, pas la portée.

**Le cycle de l'assassin** : entrer furtif → frapper (critique) → être révélé → *Furtivité* (1 action, 0 PM) → tous les monstres oublient → nouveau jet pour chacun → frapper de nouveau en critique contre ceux qui ont raté.

## 6. Les monstres insensibles

Tag d'espèce **`insensible_furtivite`** : le monstre a `detecte` **dès son instantané** et ne l'oublie jamais (ni une dissimulation, ni un changement d'étage ne l'effacent). Contre lui : aucune embuscade, aucun coup furtif, aucun jet.

30 espèces au dump du 17/11/2026 — esprits, sens surnaturels, gardiens, boss : Fantôme, Spectre, Banshee, Revenant, Dullahan, Liche, Roi Liche, Chauve-souris et Chauve-souris géante, Mimique, Cerbère, Barghest, Bête du Gévaudan, Bête glatissante, Chien d'Annwn, Gwyn ap Nudd, Nuckelavee, Boukhnoun, Grootslang, Ladon, Ammit, Djinn des ruines, archanges, Avatar, démons majeurs… Posé par `dev/gen_insensible_furtivite.py` (outil 👻 de `/admin/dev-tools`).

Ne pas confondre avec le tag **`furtif`** d'une espèce (Adze, Tokoloshe, Doppelganger, Si'lat…) : il ne rend pas le monstre invisible ; il le classe **rôdeur** dans la composition des rencontres (`rodeur_tags`, au plus 2 spécimens). Les monstres n'ont **pas** d'état furtif contre le joueur ; leur équivalent est l'IA d'embuscade (§ 4.1).

Renforts d'alarme (coffre piégé) et mimique qui s'anime arrivent **en sachant où est le groupe** (`detecte` posé).

## 7. Les sources de furtivité en jeu

Dump du 17/11/2026. « Terrain souterrain » = `sous-terrain, catacombe, donjon, grotte, couvert, humide, mine` ; « terrain sylvestre » = `foret, bois, clariere, couvert, chemin`.

### Compétences passives (entrée de combat)

| Vocation | Niv. | Compétence | Furtivité | Condition |
|---|---|---|---|---|
| Forestier | 0 | Furtivité sylvestre | 1 | `foret`, `bois` |
| Assassin | 1 | Pas feutrés | 4 | terrain souterrain |
| Forestier | 2 | Pas de velours | 5 | terrain sylvestre |
| Voleur | 4 | Pas de souris | 7 | terrain souterrain |
| Assassin | 7 | Ombre parmi les ombres | 10 | terrain souterrain |
| Forestier | 8 | Fantôme des bois | 11 | terrain sylvestre |
| Forestier | 10 | Éclaireur | 18 | presque tout le plein air : forêt, bois, clairière, herbe, plaine, colline, montagne, marais, roche, pente, neige, désert, sable |
| Illusionniste | 10 | Présence effacée | 18 (+ esquive 10, Int +8) | **aucune** |
| Assassin | 10 | Ombre incarnée | 20 (+ esquive 10, Ag +12) | **aucune** |

### Compétences actives (une action)

| Vocation | Niv. | Compétence | Furtivité | Coût |
|---|---|---|---|---|
| Assassin | 0 | Furtivité | 1 | 0 PM |
| Forestier | 5 | Se fondre dans les fourrés | `4 + Ag/10` (6 à 12 selon l'Ag) | 21 PM |

### Sorts (toute vocation qui les apprend)

| Sort | École | Furtivité | Coût | Composants |
|---|---|---|---|---|
| Amitié des bêtes | Nature, niv. 0 | 10 | 10 PM | Herbes à brûler (consommées, +5) · Sève de chêne (gardée, +1) |
| Zone de silence | Illusoire, niv. 0 | 12 (+ esquive 5 pendant 3 tours) | 10 PM | Poudre de miroir (consommée, +5) · Sel noir (gardé, +1 tour) |

### Ce qui aide sans porter de furtivité

- Tout ce qui monte l'**Agilité** de l'instantané (équipement, buffs, passives) monte la difficulté point pour point.
- **Se tenir loin** : +5 de difficulté par case.
- **La Chance** élargit la fenêtre de critique, donc la part des coups à ×4.

## 8. Ce que le joueur voit

- **Badge 🥷** dans l'en-tête de tour, tant que le membre **actif** est furtif.
- **Œil barré** sur le badge de chaque ennemi qui ne vous a pas encore repéré (affiché dès qu'un membre vivant du groupe est furtif).
- **Journal** : « X se fond dans les ombres… », « X vous repère ! (jet / seuil) », « X cherche d'où vient le coup sans repérer Y ! (jet / seuil) », « X sort de l'ombre : tous les ennemis l'ont repéré ! », et les lignes d'errance des monstres aveugles.
- **Onglet ⚡ de `/play`**, `/admin/sorts`, `/admin/competences` : « 🥷 furtivité +N », la formule puis sa valeur résolue (« +{Ag/10} → 6 »), et la condition de terrain (« 🗺️ seulement en terrain : … »).
- **Animation** : `animation:capa_furtif` (fondu dans la fumée).

## 9. Hors combat : le bruit du groupe

La furtivité ne joue **aucun** rôle en exploration : une compétence ou un sort de furtivité n'y est pas lançable pour sa furtivité (seule une part à durée, comme l'esquive de *Zone de silence*, peut l'être). Ce qui rend un groupe **discret** sur la carte est le **bruit** (`utils/bruit.py`, zones de nature seulement : ni en ville, ni en mer, ni dans un donjon à étages) :

```
points = 1 (vous) + 1 × compagnons + 0,5 × montures (guides compris) + 0,5 × escortés
       + 1 × taux de charge (poids porté par tous les porteurs / leur charge max cumulée)
rapport = points / 3
```

| Rapport | Niveau affiché |
|---|---|
| < 0,75 | 🤫 Discret |
| < 1,25 | 👣 Audible |
| au-delà | 📣 Bruyant |

Le rapport agit sur les rencontres de zone (jamais sur les grades) :

- **Effectif** tiré dans la fourchette de l'espèce : seul ⇒ bas de fourchette, groupe de référence ⇒ milieu, convoi ⇒ haut (jamais au-delà) ;
- **chance d'un second groupe** : × rapport, plafonnée à × 1,5 ;
- **fréquence des combats** : × rapport, bornée entre × 0,6 et × 1,5 (les récoltes gardent leur fréquence).

Réglages : `RENCONTRE_BRUIT_REFERENCE` (3 ; à 0 le système s'éteint), `_COMPAGNON`, `_MONTURE`, `_PROTEGE`, `_CHARGE`, `_FREQ_MIN`, `_FREQ_MAX`, `_SECOND_MAX` *(variables de monde)*.

## 10. Équilibrage et outils

- **Simulateur de duel** (`/admin/simulateur`) : le choix du **type de lieu** (tags du terrain) pose la furtivité d'entrée et ouvre les capacités conditionnées ; un adversaire furtif non repéré n'est ni approché ni attaqué (un jet de détection par tour) ; la rupture suit le moteur. Une capacité de la barre qui pose la furtivité forme l'arsenal **dissimulations** : révélé, l'acteur garde sa dernière action pour s'y refondre — le geste qui tient un assassin en vie contre un hit-and-run.
- **Potentiel de soutien** (`utils/potentiel.py`) : forfait `poids_furtivite` de 15 si la capacité confère la furtivité.
- **Écrire une compétence** : une passive **à condition** ne porte **que** `furtivite` (le reste ne serait jamais lu ; contrôlé par `dev/check_competences_doc.py`) ; `furtivite` accepte une formule à caractéristiques (`"4+{Ag/10}"`) ; un composant de sort peut porter un bonus `furtivite`.
- **Tests** : `tests/test_combat_crit.py` (critiques furtifs, insensibles), `tests/test_competences.py` (passives selon le terrain, rupture, détection), `tests/test_donjon_etages.py` (entrée furtive du groupe), `tests/test_combat_groupe.py` (principal seul en rencontre de zone), `tests/test_simulateur.py`, `dev/test_capacites_texte_client.js` (libellés).
