# Compétences de vocation — niveaux 3, 6 et 10

**Proposition de contenu, pas du contenu importé.** Rien de ce document n'est en base. Aucun
code de jeu n'a été modifié. Chaque bloc `json` est un doc CouchDB **complet**, prêt à coller
dans `/admin/doc` ou à rassembler dans un `jsons/*_a_importer.json` une fois la liste arbitrée.

Vérificateur : `python dev/check_competences_doc.py` — relit ce fichier, normalise chaque bloc
par le moteur réel (`utils/competences.normaliser_competence`, `utils/zones_effet.normaliser_zone`)
et contrôle les invariants listés plus bas. Il échoue en code 1.

> **Révision 2** — mise à jour pour les **zones d'effet** (PR #11) et la famille **invocation**
> (PR #10). 24 entrées gagnent un bloc `zone` ; le répurgateur change d'école. Le détail de ce
> qui a bougé est en fin de document, § « Ce que la révision 2 a changé ».

---

## Pourquoi

La base ne contient qu'une poignée de compétences, de niveau 0 ou 1.
`competences_apprenables` filtre sur `vocations_niveaux[voc] ≥ niveau` : passé le niveau 1 de
vocation, l'onglet ⚡ n'a plus rien à vendre, pour aucune des 20 vocations. Ce document propose
**120 compétences** — 20 vocations × 3 paliers (3 / 6 / 10) × (1 passive + 1 active).

Inspiration : `vocations et titres.txt` (titres de niveaux 3 et 5 de la table de jeu d'origine).
Le palier **10** n'y existe pas : il est neuf, et traité en **capstone de signature**.

---

## Le cadre — ce que le moteur sait lire, et rien d'autre

`_bonus_dict` (`utils/sorts.py`) et `normaliser_competence` (`utils/competences.py`) sont des
**listes blanches fermées**. Une clé inventée ne lève rien et **disparaît**. Vocabulaire
disponible, et lui seul :

| dans `effets` | au premier niveau du doc |
|---|---|
| `degats` `"2D8+4"` · `pv` · `pm` · `regen_pv` · `regen_pm` | `mode` (passive/active) · `cout_pm` · `famille` |
| `buffs` `{V,F,R,Ag,Vol,Int,Cha,Ch: ±int}` · `duree` | `cible` (soi/ennemi/allie) · `jet` (cc/cd/magique) |
| `esquive` · `furtivite` | `portee` · **`zone`** · `condition.battle_map_tags` · `animation` |

### Les zones d'effet — la nouveauté qui change le plus le contenu

Bloc `zone`, géométrie pure dans `utils/zones_effet.py`, miroir client
`templates/scripts/zones_effet.js`. **Bloc absent ⇒ la seule case de la cible désignée**, à la
lettre. Il vaut pour les **trois** `cible` : `ennemi`, `allie` et `soi`.

| `forme` | dimensions | figure |
|---|---|---|
| `cercle` | `rayon` | disque EUCLIDIEN — rayon 1 = la croix (5 cases), rayon 2 = 13 cases |
| `carre` | `rayon` | disque de CHEBYSHEV — rayon 1 = les 8 cases autour + l'ancre (9) |
| `rectangle` | `longueur` × `largeur`, `decalage` | bande orientée — les 3 cases devant : `longueur 1, largeur 3, decalage 1` |
| `cone` | `longueur`, `angle` (défaut 90), `decalage` | secteur — 3 + 5 + 7 cases sur 3 crans |

`origine` : `cible` (la case visée) ou `lanceur` (la sienne). `orientation` (rectangle et cône
seuls) : `cible` (l'axe lanceur → cible, ramené au huitième de tour) ou `facing`.

**Cinq règles de zone qui ont dicté l'écriture de chaque bloc :**

1. ⚠️ **`decalage` compte depuis l'ancre INCLUSE.** Une forme orientée ancrée sur le **lanceur**
   s'écrit `decalage: 1` — sinon son premier cran est la case du lanceur lui-même. Ancrée sur la
   **cible**, elle garde `0`, faute de quoi la cible désignée serait la seule épargnée. Toutes
   les formes orientées de ce document sont ancrées sur le lanceur et portent `decalage: 1`.
2. ⚠️ **`cercle` et `carre` de rayon 1 sont deux figures distinctes** (la croix contre les huit
   cases autour), pas deux écritures de la même. Un tourbillon est un `carre`, une explosion un
   `cercle`.
3. ⚠️ **Les deux camps ne se mélangent jamais** : aucune zone hostile ne touche un allié, aucune
   zone bénéfique ne touche un monstre. Il n'y a pas de tir ami à doser.
4. ⚠️ **La cible désignée est toujours touchée**, même hors de la forme — et **seul son jet peut
   échouer critiquement**. Une zone large n'est donc jamais plus dangereuse pour son lanceur.
5. ⚠️ **`portee` (qui l'on peut DÉSIGNER) et la zone (ce qui est ATTEINT) sont indépendantes.**
   Une forme ancrée sur le lanceur porte sa propre distance ; `portee` n'y change rien. La forme
   est filtrée par le terrain et par la ligne de vue **depuis l'ancre** — une nappe ne soigne ni
   ne brûle à travers un mur.

Et deux effets de bord utiles, exploités ici : **le lanceur profite d'une zone bénéfique où il se
tient** (alors qu'il ne peut jamais être *désigné*), et une zone `allie` **sert aussi les
montures, les personnes escortées et les invocations**. En revanche un allié **à terre est
écarté**.

### ⚠️ Les invocations ne sont PAS disponibles pour une compétence

Le bloc `invocation` (`{espece, profil?, nombre ≤ 4, duree}`) est lu par `normaliser_sort`
**et par lui seul**. `normaliser_competence` ne le lit pas, et la branche `competence` de
`resolve_action` (`utils/combat.py`) n'en a aucune trace — là où la branche `sort` la traite
avant même la cible. **Un bloc `invocation` posé sur un doc `competence:*` serait silencieusement
inerte** : la compétence partirait en base et ne ferait rien.

Aucune entrée de ce document n'invoque donc quoi que ce soit. Trois capstones sont pourtant des
invocations par leur thème — `competence:gardien_des_esprits` (« +1 esprit invocable par jour »),
`competence:invocation_majeure`, `competence:couronne_de_liche` — et sont rendus ici en
**possession du lanceur** (un très gros buff de soi), seule forme que le moteur sache porter pour
une compétence. Deux voies existent pour les rendre littéralement, toutes deux **hors du
périmètre de ce document** : les écrire en `sort:*` (aucun code à toucher — c'est ce qu'ont fait
`sort:pacte_du_servant` et `sort:levee_des_ossements`), ou étendre `invocation` aux compétences
(du code moteur). À arbitrer.

### La famille `invocation` et le répurgateur

`famille` est une étiquette libre portée par la donnée, lue par `normaliser_competence` comme par
`normaliser_sort`. Elle sert à une seule chose : permettre à une vocation d'exclure tout un
**type** de capacité de son apprentissage (`familles_exclues` de `rules:vocations`). Le
répurgateur est passé en **Démonologie** et exclut `["invocation"]` — il pratique l'école du
démoniste sans ses invocations.

Conséquence pour ce document : **aucune entrée ne porte `famille`**. En poser une vaudrait
s'exposer à ce qu'une vocation la rende inapprenable sans que rien ne le signale au moment de
l'écriture. Le champ ne se justifiera que le jour où une compétence appartiendra vraiment à un
type qu'une vocation doit pouvoir refuser.

### Les cinq pièges de fond

1. **Une passive `condition`nnée est EXCLUE du repli permanent** (`bonus_passifs`) : seule sa
   `furtivite` est lue, au snapshot de combat. ⇒ **une passive à `condition` ne porte QUE
   `furtivite`**. Une seule entrée en use (`competence:eclaireur`).
2. **`furtivite` est ignorée hors combat**, et se prend en **MAX**, jamais en somme.
3. **`Cha` n'a aucune dérivée de combat** : un buff de Cha est social et marchand. Réservé aux
   vocations dont c'est l'identité — ménestrel, duelliste, druide, prêtre, paladin.
4. **`V` est à SON échelle 1-10**, pas ×10 : `+1` est un gain notable, `−3` entrave lourdement
   (plancher `deplacement = max(1, V)`).
5. **Deux actives ne cumulent pas sur la même caract** (meilleur bonus + pire malus retenus).
   Passives et équipement, eux, s'additionnent.

### Ce que les titres du `.txt` ne permettaient pas de rendre

Aucune de ces mécaniques n'existe : réussite critique sur 9+, annulation d'un échec critique,
attaque supplémentaire par round (`+1 A`), immunité psychologique, plafond de caract dépassé
(`+1 au-dessus du maximum`), résistance typée (feu / poison / maladie), doublement d'un bonus de
compétence hors combat. Les titres qui en dépendaient sont **réinterprétés** : la note *Source*
de chaque entrée dit ce qui a été retenu à la place.

### Deux leviers supportés et sous-employés par le contenu actuel

- **le debuff pur sur `cible:"ennemi"`** — `{buffs:{F:-15}, duree:3}` sans dégâts, accepté par
  `resolve_action` (« la prise porte ») ; onze entrées en vivent ;
- **`regen_pm`**, et `esquive` sur une active.

### Ce qu'une frappe `cc` vaut réellement

Une active `jet:"cc"` **à dés** emprunte les dés ET l'allonge de l'arme équipée
(`_degats_competence`, `_portee_competence`) — `cd` et `magique` en sont exclus. Le bloc `degats`
d'une frappe de contact se lit donc **au-dessus** du `degats_cc` du porteur.

---

## Grille de calibrage

Référence en base : passive niveau 0 ≈ **+4** en une caract ; active niveau 0 ≈ **10 PM pour
1D8+2**. Les sorts plafonnent à `buffs ±20`, `pv 16`, `regen 4`, `duree 5`, `12 PM`.
Coût d'achat = `(niveau+1) × COMPETENCE_COUT_COEFF` → **8 / 14 / 22** points de caractéristique.

| | **Niveau 3** | **Niveau 6** | **Niveau 10 — capstone** |
|---|---|---|---|
| **Passive** | +8 pts de caract (1-2 caracts) | +14 pts, ou +8 pts `+ esquive 5` | +22 pts, **ou** un effet de signature seul |
| variantes | `esquive 4-6`, `regen_pv 1` | `esquive 10`, `regen_pv 2` | `esquive 20` · `regen_pv 4-5` · `regen_pm 4-5` · `furtivite 18-20` |
| **Active — PM** | **15** | **25** | **40** |
| offensive mono-cible | `2D8+4` (≈ 13) | `3D8+8` (≈ 21) | `5D10+18…20` (≈ 45-48) |
| offensive + entrave | `1D6` + buffs `−8` / `duree 3` | `2D8+4` + buffs `−15` / `duree 3` | `3D10` + buffs `−20` / `duree 4` |
| soutien `soi` / `allie` | `pv 18`, ou buffs `+12` / `duree 4` | `pv 30`, ou buffs `+18` / `duree 5` | `pv 45` + `regen_pv 5` + buffs `+20` / `duree 5` |

### La décote de zone

Une zone multiplie l'effet par le nombre de cibles prises **pour le même coût, la même action et
un seul débit de PM**. Elle se paie donc sur la puissance unitaire :

| portée de la forme | décote appliquée | formes concernées |
|---|---|---|
| petite (≈ 3-5 cases) | **−25 %** | `rectangle 1×3`, `cone` longueur 2, `cercle` rayon 1 |
| moyenne (≈ 9-13 cases) | **−40 %** | `carre` rayon 1, `cercle` rayon 2, `cone` longueur 3 |
| large (≥ 20 cases) | **−50 %** | `carre` rayon 2, `cone` longueur 4 |

Appliquée aux dégâts pour les zones hostiles, aux `pv`/`buffs` pour les zones bénéfiques. Un
capstone offensif mono-cible reste donc **le plus gros coup unitaire du jeu** : la zone ne le
périme pas, elle propose l'autre moitié du choix.

⚠️ Un gros buff de `R` ou de `Vol` **re-clampe PV/PM à son expiration** (plancher `pv_max ≥ 1`) :
voulu, déjà éprouvé par les sorts, et visible sur les capstones de chaman et de démoniste.

---

## Invariants contrôlés par `dev/check_competences_doc.py`

1. Chaque bloc passe `normaliser_competence` **sans perte de clé** — ni dans `effets`, ni au
   premier niveau du doc, ni dans `buffs`, ni dans `zone`. Une clé inventée (`crit_bonus`, un
   `magie` recopié d'un sort, un buff sur une caract qui n'existe pas, une `forme` mal
   orthographiée) ne lève rien et **disparaît en silence**.
2. **Aucun bloc `invocation`** : il serait inerte sur une compétence (cf. ci-dessus).
3. Aucun `_id` en double, aucune collision avec les `competence:*` déjà en base.
4. Exactement **6 entrées par vocation** : une passive et une active par niveau 3, 6, 10.
5. `vocation` ∈ les 20 ids de `rules:vocations` ; `niveau` ∈ {3, 6, 10}.
6. Toute passive portant `condition` n'a **que** `furtivite` dans ses effets ; **aucune passive
   ne porte de `zone`** (une passive ne vise rien — le bloc serait décoratif).
7. Toute active `cible:"ennemi"` porte `degats` **ou** une part durative ; toute active passe
   `competence_utilisable_combat` **ou** `competence_utilisable_exploration`.
8. Convention de `decalage` : une forme orientée ancrée sur le `lanceur` porte `decalage ≥ 1`,
   ancrée sur la `cible` porte `decalage == 0`.
9. Aucune passive ne porte `cout_pm`, `cible`, `jet` ou `portee`.

## Guerrier ⚔️

*Axe : encaisse et frappe lourde. Titres sources : Chevalier, Stratège, Mercenaire, Protecteur,
Seigneur de guerre, Mastodonte.*

### Niveau 3

**Chevalier** 🐴 · passive — *L'acier ne le gêne plus : il a fini par l'oublier sur ses épaules.*
```json
{"_id": "competence:chevalier", "type": "competence", "nom": "Chevalier", "icon": "🐴",
 "description": "Tant d'années sous le harnois que l'armure a cessé de peser : il y bouge comme un autre en chemise.",
 "vocation": "guerrier", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"R": 6, "Ag": 2}}}
```
*Source : « Chevalier » (niv. 3) — « +1 en Ag d'un malus d'armure » n'est pas exprimable (les malus d'armure passent par `equipment_bonus.malus_depl`) ; rendu par le couple encaisse + souplesse.*

**Coup de mercenaire** ⚔️ · active · 15 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:coup_de_mercenaire", "type": "competence", "nom": "Coup de mercenaire", "icon": "⚔️",
 "description": "Pas une passe d'armes : un coup de métier, donné par quelqu'un qu'on paie pour qu'il porte.",
 "vocation": "guerrier", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "2D8+4"}}
```
*Source : « Mercenaire » (niv. 3) — le changement d'arme sans perte d'action n'existe pas ; rendu en frappe polyvalente.*

### Niveau 6

**Protecteur** 🩹 · passive
```json
{"_id": "competence:protecteur", "type": "competence", "nom": "Protecteur", "icon": "🩹",
 "description": "Ses cicatrices se comptent par dizaines. Chacune est une leçon que son corps a retenue.",
 "vocation": "guerrier", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"R": 14}}}
```
*Source : « Protecteur » (niv. 5) — « +5 PV au-dessus du maximum » : `pv_max = R·3 + F`, donc +14 R vaut +42 PV. Le plafond de caract n'est pas touché (un buff s'ajoute après `compute_stat_cap`).*

**Garde de fer** 🛡️ · active · 25 PM · `soi` / portée 1 · zone : les 8 cases autour
```json
{"_id": "competence:garde_de_fer", "type": "competence", "nom": "Garde de fer", "icon": "🛡️",
 "description": "Il ferme la garde et cesse d'avancer. Pendant quelques instants, il n'y a plus d'ouverture.",
 "vocation": "guerrier", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "soi", "portee": 1,
 "zone": {"forme": "carre", "origine": "lanceur", "rayon": 1},
 "effets": {"buffs": {"R": 11}, "esquive": 5, "duree": 5}}
```
*Source : « Stratège » (niv. 3), tenue de ligne.*

### Niveau 10 — capstone

**Mastodonte** 🗿 · passive
```json
{"_id": "competence:mastodonte", "type": "competence", "nom": "Mastodonte", "icon": "🗿",
 "description": "Il manie d'une seule main ce que deux bras peinent à lever, et personne autour de lui n'a l'air de trouver cela normal.",
 "vocation": "guerrier", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"F": 16, "R": 6}}}
```
*Source : « Mastodonte » (niv. 5) — « arme à 2 mains dans une main » n'est pas exprimable (les mains d'équipement ne se négocient pas) ; rendu par la Force pure.*

**Brise-ligne** 💥 · active · 40 PM · `ennemi` / `cc` / portée 1 · zone : les 3 cases devant
```json
{"_id": "competence:brise_ligne", "type": "competence", "nom": "Brise-ligne", "icon": "💥",
 "description": "Un seul coup, porté là où la ligne tient. Après lui, il n'y a plus de ligne.",
 "vocation": "guerrier", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "zone": {"forme": "rectangle", "origine": "lanceur", "orientation": "cible", "longueur": 1, "largeur": 3, "decalage": 1},
 "effets": {"degats": "4D10+14"}}
```
*Source : « Seigneur de guerre » (niv. 5) — le commandement n'a pas de support ; rendu en frappe décisive.*

---

## Barbare 🪓

*Axe : R et F brutes, frénésie assumée. Titres : Berserker, Gladiateur, Conquérant, Annonce de
sang, Vétéran, Danseur de guerre.*

### Niveau 3

**Conquérant** 🏔️ · passive
```json
{"_id": "competence:conquerant", "type": "competence", "nom": "Conquérant", "icon": "🏔️",
 "description": "Il a dormi dans la neige et bu l'eau des flaques. Son corps a pris l'habitude de se refaire tout seul.",
 "vocation": "barbare", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"R": 6}, "regen_pv": 1}}
```
*Source : « Conquérant » (niv. 3), « double les PV récupérés naturellement » → régénération permanente.*

**Frénésie** 🩸 · active · 15 PM · `soi` / portée 1
```json
{"_id": "competence:frenesie", "type": "competence", "nom": "Frénésie", "icon": "🩸",
 "description": "Il cesse de se défendre et se met à frapper. Ce n'est pas une décision, c'est une bascule.",
 "vocation": "barbare", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "soi", "portee": 1,
 "effets": {"buffs": {"F": 12, "R": 6, "Ag": -6}, "duree": 4}}
```
*Source : « Berserker » (niv. 3). La garde ouverte est rendue par le malus d'Ag — la frénésie doit coûter quelque chose.*

### Niveau 6

**Vétéran** 🪖 · passive
```json
{"_id": "competence:veteran", "type": "competence", "nom": "Vétéran", "icon": "🪖",
 "description": "Vieux roublard des batailles. Il n'y a plus de situation qu'il n'ait déjà vue tourner mal.",
 "vocation": "barbare", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"F": 8, "R": 6}}}
```
*Source : « Vétéran » (niv. 5) — « pas de malus de situation » n'a pas de support ; rendu en socle martial.*

**Annonce de sang** 🔥 · active · 25 PM · `soi` / portée 1
```json
{"_id": "competence:annonce_de_sang", "type": "competence", "nom": "Annonce de sang", "icon": "🔥",
 "description": "La fureur guerrière montée d'un cran. Ceux qui l'ont vue une fois changent de chemin la fois suivante.",
 "vocation": "barbare", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "soi", "portee": 1,
 "effets": {"buffs": {"F": 20, "Ag": 6}, "regen_pv": 3, "duree": 5}}
```
*Source : « Annonce de sang » (niv. 5).*

### Niveau 10 — capstone

**Danseur de guerre** 🌀 · passive
```json
{"_id": "competence:danseur_de_guerre", "type": "competence", "nom": "Danseur de guerre", "icon": "🌀",
 "description": "Une transe, pas un style. Les blessures se referment presque au rythme où on les lui ouvre.",
 "vocation": "barbare", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"R": 8}, "regen_pv": 4}}
```
*Source : « Danseur de guerre » (niv. 5) — « ignore la première blessure du jour » n'est pas exprimable (pas de système de blessures) ; rendu par la régénération la plus lourde du jeu.*

**Spasme de furie** 🪓 · active · 40 PM · `ennemi` / `cc` / portée 1 · zone : les 8 cases autour
```json
{"_id": "competence:spasme_de_furie", "type": "competence", "nom": "Spasme de furie", "icon": "🪓",
 "description": "Il ne frappe plus une cible : il frappe, et quelque chose se trouve devant.",
 "vocation": "barbare", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "zone": {"forme": "carre", "origine": "lanceur", "rayon": 1},
 "effets": {"degats": "3D10+12"}}
```

---

## Forestier 🏹

*Axe : `cd` à longue portée et furtivité de terrain. Titres : Pisteur, Franc-archer, Rôdeur,
Éclaireur, Tireur d'élite, Chasseur de monstres.*

### Niveau 3

**Pisteur** 👁️ · passive
```json
{"_id": "competence:pisteur", "type": "competence", "nom": "Pisteur", "icon": "👁️",
 "description": "L'œil du faucon, l'oreille du loup, le nez du chien. Il ne suit pas une piste : il la lit.",
 "vocation": "forestier", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Ag": 6, "Ch": 2}}}
```
*Source : « Pisteur » (niv. 3) — « +1 en Sens » : la caractéristique Sens n'existe pas ici, Ag et Ch en tiennent lieu.*

**Flèche de franc-archer** 🏹 · active · 15 PM · `ennemi` / `cd` / portée 10
```json
{"_id": "competence:fleche_de_franc_archer", "type": "competence", "nom": "Flèche de franc-archer", "icon": "🏹",
 "description": "Il tire dans la mêlée sans hésiter : il sait exactement où sont les siens.",
 "vocation": "forestier", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "ennemi", "jet": "cd", "portee": 10,
 "effets": {"degats": "2D8+4"}}
```
*Source : « Franc-archer » (niv. 3) — l'annulation d'échec critique n'existe pas ; rendu en portée et en dégâts.*

### Niveau 6

**Rôdeur** 🌲 · passive
```json
{"_id": "competence:rodeur", "type": "competence", "nom": "Rôdeur", "icon": "🌲",
 "description": "Guide des terres hostiles, habitué des escarmouches. Deux lames, et jamais le même pied devant.",
 "vocation": "forestier", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Ag": 10, "V": 1}}}
```
*Source : « Rôdeur » (niv. 3) — l'ambidextrie n'a pas de support (l'équipement n'a pas de malus de seconde arme) ; rendue en vivacité.*

**Tir d'élite** 🎯 · active · 25 PM · `ennemi` / `cd` / portée 12
```json
{"_id": "competence:tir_d_elite", "type": "competence", "nom": "Tir d'élite", "icon": "🎯",
 "description": "Il retient son souffle une seconde de trop. Le trait part, et arrive entre les deux yeux.",
 "vocation": "forestier", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "ennemi", "jet": "cd", "portee": 12,
 "effets": {"degats": "3D8+8"}}
```
*Source : « Tireur d'élite » (niv. 5) — la touche transformée en critique n'est pas exprimable ; rendue en dégâts et en allonge.*

### Niveau 10 — capstone

**Éclaireur** 🍃 · passive — *la seule entrée conditionnelle de ce document*
```json
{"_id": "competence:eclaireur", "type": "competence", "nom": "Éclaireur", "icon": "🍃",
 "description": "En terrain ouvert ou sous les frondaisons, il cesse simplement d'être là où on le cherche.",
 "vocation": "forestier", "niveau": 10, "mode": "passive",
 "condition": {"battle_map_tags": ["foret", "bois", "clariere", "herbe", "plaine", "colline", "montagne", "marais", "roche", "pente", "neige", "desert", "sable"]},
 "effets": {"furtivite": 18}}
```
*Source : « Éclaireur » (niv. 5). **Forme obligatoire** : une passive conditionnée ne peut porter que `furtivite` (cf. piège n°1). Prolonge `competence:furtivite_sylvestre` (niv. 0) — les deux se prennent en max, pas en somme.*

**Trait du chasseur de monstres** 🐉 · active · 40 PM · `ennemi` / `cd` / portée 14
```json
{"_id": "competence:trait_du_chasseur_de_monstres", "type": "competence", "nom": "Trait du chasseur de monstres", "icon": "🐉",
 "description": "Une flèche taillée pour ce qui n'a pas de nom, encochée par quelqu'un que cela n'effraie plus.",
 "vocation": "forestier", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "cd", "portee": 14,
 "effets": {"degats": "5D10+18"}}
```
*Source : « Chasseur de monstres » (niv. 5) — l'immunité psychologique n'existe pas ; rendue en puissance de trait.*

---

## Duelliste 🤺

*Axe : Ag, esquive, précision, et la seule vocation martiale qui vit aussi de son Charisme.
Titres : Gentilhomme, Mousquetaire, Garde, Seigneur, Maître d'armes, Exécuteur.*

### Niveau 3

**Gentilhomme** 🎩 · passive
```json
{"_id": "competence:gentilhomme", "type": "competence", "nom": "Gentilhomme", "icon": "🎩",
 "description": "Il se bat plus souvent à la cour qu'en champ clos, et y gagne davantage.",
 "vocation": "duelliste", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Cha": 8}}}
```
*Source : « Gentilhomme » (niv. 3). ⚠️ Cha n'a aucune dérivée de combat : gain social et marchand uniquement — c'est l'intention.*

**Botte de mousquetaire** 🤺 · active · 15 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:botte_de_mousquetaire", "type": "competence", "nom": "Botte de mousquetaire", "icon": "🤺",
 "description": "Une figure apprise, répétée mille fois, placée une seule — au bon moment.",
 "vocation": "duelliste", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "2D8+4"}}
```
*Source : « Mousquetaire » (niv. 3).*

### Niveau 6

**Garde** 🛡️ · passive
```json
{"_id": "competence:garde", "type": "competence", "nom": "Garde", "icon": "🛡️",
 "description": "Champion implacable ou garde du corps dévoué : il n'a jamais reculé devant un combat difficile, et cela se sait.",
 "vocation": "duelliste", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Vol": 8, "R": 6}}}
```
*Source : « Garde » (niv. 3), « +2 en résistance au moral et à la panique » → Volonté.*

**Parade de maître** ⚔️ · active · 25 PM · `soi` / portée 1 · zone : les 8 cases autour
```json
{"_id": "competence:parade_de_maitre", "type": "competence", "nom": "Parade de maître", "icon": "⚔️",
 "description": "Il cesse d'attaquer et se contente de répondre. Plus rien ne passe.",
 "vocation": "duelliste", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "soi", "portee": 1,
 "zone": {"forme": "carre", "origine": "lanceur", "rayon": 1},
 "effets": {"buffs": {"Ag": 6}, "esquive": 10, "duree": 5}}
```

### Niveau 10 — capstone

**Maître d'armes** 🗡️ · passive
```json
{"_id": "competence:maitre_d_armes", "type": "competence", "nom": "Maître d'armes", "icon": "🗡️",
 "description": "L'arme a cessé d'être un objet qu'il tient : c'est le bout de son bras, et il le sait depuis longtemps.",
 "vocation": "duelliste", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Ag": 14, "F": 8}}}
```
*Source : « Maître d'armes » (niv. 5) — les modificateurs de caractéristique d'une arme ne sont pas éditables par une compétence ; rendus en maîtrise du porteur.*

**Coup de l'Exécuteur** ⚰️ · active · 40 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:coup_de_l_executeur", "type": "competence", "nom": "Coup de l'Exécuteur", "icon": "⚰️",
 "description": "Un chirurgien du combat, qui décide de la blessure avant de la porter.",
 "vocation": "duelliste", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "5D10+20"}}
```
*Source : « Exécuteur » (niv. 5) — le choix de l'effet de blessure n'existe pas (la localisation est tirée) ; rendu en dégâts maximaux.*

---

## Assassin 🗡

*Axe : furtivité, poison rendu en debuff durable, burst de contact. Titres : Espion, Surineur,
Empoisonneur, Maître des ombres, Maître lames, Maître venins.*

### Niveau 3

**Surineur** 🔪 · passive
```json
{"_id": "competence:surineur", "type": "competence", "nom": "Surineur", "icon": "🔪",
 "description": "Les lames courtes ne sont plus un pis-aller : sa dague trouve l'ouverture que l'épée cherche encore.",
 "vocation": "assassin", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Ag": 6, "F": 2}}}
```
*Source : « Surineur » (niv. 3) — la « note petite taille » des armes n'existe pas ; rendue en maîtrise des armes légères.*

**Venin de contact** 🧪 · active · 15 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:venin_de_contact", "type": "competence", "nom": "Venin de contact", "icon": "🧪",
 "description": "Une goutte sur le fil, et la plaie fait le reste du travail.",
 "vocation": "assassin", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "1D6", "buffs": {"R": -8, "F": -6}, "duree": 3}}
```
*Source : « Empoisonneur » (niv. 3) — la fabrication de poisons n'est pas une mécanique ; le poison est rendu par le seul support réel, un debuff durable.*

### Niveau 6

**Maître des ombres** 🌑 · passive
```json
{"_id": "competence:maitre_des_ombres", "type": "competence", "nom": "Maître des ombres", "icon": "🌑",
 "description": "Souplesse et grâce poussées au point où le regard glisse sur lui sans accrocher.",
 "vocation": "assassin", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Ag": 8}, "esquive": 5}}
```
*Source : « Maître des ombres » (niv. 5), « +1 en Ag au-dessus du maximum ».*

**Maître lames** ⚔️ · active · 25 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:maitre_lames", "type": "competence", "nom": "Maître lames", "icon": "⚔️",
 "description": "Personne n'inflige autant de dégâts en une seule attaque. C'est tout ce qu'il a jamais cherché à faire.",
 "vocation": "assassin", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "3D8+8"}}
```
*Source : « Maître lames » (niv. 5) — le critique sur 9+ n'existe pas ; rendu en dégâts bruts.*

### Niveau 10 — capstone

**Ombre incarnée** 👤 · passive
```json
{"_id": "competence:ombre_incarnee", "type": "competence", "nom": "Ombre incarnée", "icon": "👤",
 "description": "Il n'entre pas dans un combat : il y est déjà, et personne ne sait où.",
 "vocation": "assassin", "niveau": 10, "mode": "passive",
 "effets": {"furtivite": 20}}
```
*Furtivité permanente à l'entrée de tout combat, sans condition de terrain — lue par `furtivite_passive`, prise en max avec `competence:furtivite` (niv. 0), qui reste utile pour se refondre après avoir frappé.*

**Exécution** 🗡️ · active · 40 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:execution", "type": "competence", "nom": "Exécution", "icon": "🗡️",
 "description": "Il a choisi l'instant longtemps avant d'entrer dans la pièce.",
 "vocation": "assassin", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "5D10+20"}}
```

---

## Voleur 🔑

*Axe : esquive, Chance, Agilité. Titres : Tire-laine, Coupe-jarret, Escamoteur, Bandit de grands
chemins, Grand maître de guilde, Maraudeur.*

### Niveau 3

**Tire-laine** 🤞 · passive
```json
{"_id": "competence:tire_laine", "type": "competence", "nom": "Tire-laine", "icon": "🤞",
 "description": "On ne l'a jamais pris en flagrant délit. Statistiquement, cela ne devrait pas être possible.",
 "vocation": "voleur", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Ch": 6, "Ag": 2}}}
```
*Source : « Tire-laine » (niv. 3) — l'annulation d'échec critique n'existe pas ; rendue par la Chance, qui déplace les fenêtres de critique (`_seuils_critiques`).*

**Coup de coupe-jarret** 🔪 · active · 15 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:coup_de_coupe_jarret", "type": "competence", "nom": "Coup de coupe-jarret", "icon": "🔪",
 "description": "Il ne vise pas le cœur. Il vise le tendon, et attend que l'autre tombe.",
 "vocation": "voleur", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "1D8+2", "buffs": {"V": -2}, "duree": 3}}
```
*Source : « Coupe-jarret » (niv. 3). `V: -2` ≈ un tiers du déplacement d'un humain — la cible garde toujours une case (`deplacement = max(1, V)`).*

### Niveau 6

**Escamoteur** ✋ · passive
```json
{"_id": "competence:escamoteur", "type": "competence", "nom": "Escamoteur", "icon": "✋",
 "description": "Un objet disparaît de sa paume en quelques centièmes de seconde, et personne ne saurait dire vers où.",
 "vocation": "voleur", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Ag": 8, "Ch": 6}}}
```
*Source : « Escamoteur » (niv. 3).*

**Fuite de maraudeur** 💨 · active · 25 PM · `soi` / portée 1
```json
{"_id": "competence:fuite_de_maraudeur", "type": "competence", "nom": "Fuite de maraudeur", "icon": "💨",
 "description": "Il cesse de se battre et se met à ne plus être touchable. C'est un métier différent, qu'il connaît aussi.",
 "vocation": "voleur", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "soi", "portee": 1,
 "effets": {"buffs": {"Ag": 8}, "esquive": 18, "duree": 4}}
```

### Niveau 10 — capstone

**Maraudeur** 🌪️ · passive
```json
{"_id": "competence:maraudeur", "type": "competence", "nom": "Maraudeur", "icon": "🌪️",
 "description": "Ses réflexes sont tels qu'il semble impossible à toucher. On finit par cesser d'essayer.",
 "vocation": "voleur", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Ag": 6}, "esquive": 20}}
```
*Source : « Maraudeur » (niv. 5) — « une esquive par round transformée en critique » n'est pas exprimable ; rendue par la plus forte esquive permanente du jeu (le double de `competence:esquive`, niv. 0, qui s'y additionne : les passives se somment).*

**Coup du bandit de grands chemins** 🏴 · active · 40 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:coup_du_bandit", "type": "competence", "nom": "Coup du bandit de grands chemins", "icon": "🏴",
 "description": "La bourse ou la vie — sauf qu'il a déjà décidé, et qu'il ne repose pas la question.",
 "vocation": "voleur", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "4D10+14", "buffs": {"Ag": -20}, "duree": 3}}
```
*Source : « Bandit de grands chemins » (niv. 5), « +1 A au-dessus du maximum » — les actions supplémentaires n'existent pas ; rendues en frappe lourde qui ouvre la garde de la cible.*

---

## Moine 🥋

*Axe : Volonté, contact à mains nues, don de PM. Titres : Vagabond, Sage, Pèlerin, Légende,
Sensei, Ascète.*

### Niveau 3

**Sage** ☯️ · passive
```json
{"_id": "competence:sage", "type": "competence", "nom": "Sage", "icon": "☯️",
 "description": "Calme et réfléchi. Son esprit se trouble si rarement qu'on a cessé de chercher ce qui y parviendrait.",
 "vocation": "moine", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Vol": 8}}}
```
*Source : « Sage » (niv. 3), « +2 en résistance à la folie » → Volonté (et, par elle, `pm_max` et `pm_def`).*

**Garde du pèlerin** 🥢 · active · 15 PM · `soi` / portée 1
```json
{"_id": "competence:garde_du_pelerin", "type": "competence", "nom": "Garde du pèlerin", "icon": "🥢",
 "description": "Le bâton tenu en travers, comme un bouclier de bois. Même les traits finissent par s'y perdre.",
 "vocation": "moine", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "soi", "portee": 1,
 "effets": {"buffs": {"R": 12}, "esquive": 6, "duree": 4}}
```
*Source : « Pèlerin » (niv. 3), parade des projectiles.*

### Niveau 6

**Vagabond** 👣 · passive
```json
{"_id": "competence:vagabond", "type": "competence", "nom": "Vagabond", "icon": "👣",
 "description": "Voyageur habitué à se défendre. Il réagit avec la rapidité du chat, et frappe avant qu'on ait fini de décider.",
 "vocation": "moine", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Ag": 8, "Vol": 4, "V": 1}}}
```
*Source : « Vagabond » (niv. 3) — « frappe toujours en premier » n'est pas exprimable ; rendu par l'initiative, qui dérive d'Ag et de V.*

**Poing de légende** 👊 · active · 25 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:poing_de_legende", "type": "competence", "nom": "Poing de légende", "icon": "👊",
 "description": "Les légendes disent qu'ils fendent la roche. Les légendes ont vu.",
 "vocation": "moine", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "3D8+8"}}
```
*Source : « Légende » (niv. 5).*

### Niveau 10 — capstone

**Ascète** 🧘 · passive
```json
{"_id": "competence:ascete", "type": "competence", "nom": "Ascète", "icon": "🧘",
 "description": "Il peut survivre sans boire, sans manger, sans dormir. Sa méditation suffit à tout le reste.",
 "vocation": "moine", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Vol": 10}, "regen_pv": 3, "regen_pm": 3}}
```
*Source : « Ascète » (niv. 5) — les résistances typées n'existent pas ; rendues par la seule double régénération permanente du jeu.*

**Souffle du Sensei** 🌬️ · active · 40 PM · `allie` / portée 2 · zone : croix de rayon 1
```json
{"_id": "competence:souffle_du_sensei", "type": "competence", "nom": "Souffle du Sensei", "icon": "🌬️",
 "description": "Front contre front, une longue expiration — mais il n'y a plus de limite à ce qu'il peut céder.",
 "vocation": "moine", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "allie", "portee": 2,
 "zone": {"forme": "cercle", "origine": "cible", "rayon": 1},
 "effets": {"pv": 34, "pm": 15, "buffs": {"Vol": 15}, "regen_pv": 4, "duree": 5}}
```
*Source : « Sensei » (niv. 5). Prolonge `competence:souffle_partage` (niv. 1) — le don au compagnon est l'axe du moine.*

---

## Paladin 🛡

*Axe : soin d'allié, Volonté, aura. Titres : Champion, Prélat, Martyr, Héros, Exarque,
Purificateur.*

### Niveau 3

**Prélat** ✝️ · passive
```json
{"_id": "competence:prelat", "type": "competence", "nom": "Prélat", "icon": "✝️",
 "description": "Habitué à combattre les pires abominations du monde. Sans peur, et sans reproche.",
 "vocation": "paladin", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Vol": 6, "R": 2}}}
```
*Source : « Prélat » (niv. 3), « résistance à la peur et à la terreur ».*

**Frappe du champion** 🔨 · active · 15 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:frappe_du_champion", "type": "competence", "nom": "Frappe du champion", "icon": "🔨",
 "description": "Il sait où sont les points faibles de ce qui ne devrait plus marcher, et il frappe là.",
 "vocation": "paladin", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "2D8+4"}}
```
*Source : « Champion » (niv. 3) — le bonus ciblé contre les morts-vivants n'est pas exprimable (aucune clé d'effet par type de créature) ; rendu en frappe sacrée générique.*

### Niveau 6

**Héros** 🛡️ · passive
```json
{"_id": "competence:heros", "type": "competence", "nom": "Héros", "icon": "🛡️",
 "description": "Maître du bouclier, qui est chez lui la forme visible d'une volonté de défendre les plus faibles.",
 "vocation": "paladin", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"R": 10, "Vol": 4}}}
```
*Source : « Héros » (niv. 5), « +1 PA et +2 en parade avec les boucliers » — les PA viennent de l'équipement ; rendus par la R, qui alimente `pa = R // 20`.*

**Serment du martyr** 🩸 · active · 25 PM · `allie` / portée 2 · zone : croix de rayon 1
```json
{"_id": "competence:serment_du_martyr", "type": "competence", "nom": "Serment du martyr", "icon": "🩸",
 "description": "Il prend sur lui ce qu'un autre ne peut plus porter. C'est tout le serment, et il n'en a jamais fait d'autre.",
 "vocation": "paladin", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "allie", "portee": 2,
 "zone": {"forme": "cercle", "origine": "cible", "rayon": 1},
 "effets": {"pv": 22, "buffs": {"R": 9}, "regen_pv": 3, "duree": 5}}
```
*Source : « Martyr » (niv. 3). Prolonge `competence:imposition_des_mains` (niv. 1).*

### Niveau 10 — capstone

**Exarque** 👑 · passive
```json
{"_id": "competence:exarque", "type": "competence", "nom": "Exarque", "icon": "👑",
 "description": "Sa ferveur est devenue une architecture. Les attaques contre l'esprit n'y trouvent aucune prise.",
 "vocation": "paladin", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Vol": 16, "Cha": 6}}}
```
*Source : « Exarque » (niv. 5), « +1 en Vol au-dessus du maximum ».*

**Lumière du Purificateur** ☀️ · active · 40 PM · `ennemi` / `magique` / portée 6 · zone : disque de rayon 2
```json
{"_id": "competence:lumiere_du_purificateur", "type": "competence", "nom": "Lumière du Purificateur", "icon": "☀️",
 "description": "Une lumière sans chaleur, dirigée. Ce qui vient du monde des morts n'y survit pas longtemps.",
 "vocation": "paladin", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "magique", "portee": 6,
 "zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
 "effets": {"degats": "2D10+8", "buffs": {"Vol": -12}, "duree": 3}}
```
*Source : « Purificateur » (niv. 5) — l'immunité psychologique n'existe pas ; rendue en frappe sacrée à distance qui brise la volonté de la cible. `jet:"magique"` ⇒ résolution sur la `pm_def`, PA non soustraits.*

---

## Templier ⚜️

*Axe : Résistance, encaisse, brisure des sorts. Titres : Juge, Vengeur, Brise-sort, Champion de
Justice, Bras divin, Gardien.*

### Niveau 3

**Brise-sort** ⚜️ · passive
```json
{"_id": "competence:brise_sort", "type": "competence", "nom": "Brise-sort", "icon": "⚜️",
 "description": "À force de lutter contre des sources magiques, quelque chose en lui a fini par leur résister tout seul.",
 "vocation": "templier", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Vol": 6, "Int": 2}}}
```
*Source : « Brise-sort » (niv. 3), « dissipation naturelle 10+ » → `pm_def = Vol//2 + Int//4`, la seule défense magique du moteur.*

**Arme de justice** ⚔️ · active · 15 PM · `soi` / portée 1
```json
{"_id": "competence:arme_de_justice", "type": "competence", "nom": "Arme de justice", "icon": "⚔️",
 "description": "Il n'enchante pas sa lame : il lui rappelle pourquoi elle a été forgée.",
 "vocation": "templier", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "soi", "portee": 1,
 "effets": {"buffs": {"F": 12}, "duree": 4}}
```
*Source : « Juge » (niv. 3), sort Arme de vie.*

### Niveau 6

**Champion de Justice** 🔆 · passive
```json
{"_id": "competence:champion_de_justice", "type": "competence", "nom": "Champion de Justice", "icon": "🔆",
 "description": "Le feu, la glace et la foudre lui passent dessus sans vraiment le convaincre.",
 "vocation": "templier", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"R": 10, "Vol": 4}}}
```
*Source : « Champion de Justice » (niv. 5) — les résistances élémentaires typées n'existent pas ; rendues en encaisse générale.*

**Bras divin** 🌟 · active · 25 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:bras_divin", "type": "competence", "nom": "Bras divin", "icon": "🌟",
 "description": "L'arme enchantée devient une extension du serment. Ce qu'elle touche cesse de discuter.",
 "vocation": "templier", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "3D8+8"}}
```
*Source : « Bras divin » (niv. 5).*

### Niveau 10 — capstone

**Gardien** 🗿 · passive
```json
{"_id": "competence:gardien", "type": "competence", "nom": "Gardien", "icon": "🗿",
 "description": "Son corps et son esprit sont devenus si massifs qu'il paraît, de loin, insensible aux dommages.",
 "vocation": "templier", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"R": 16, "Vol": 6}}}
```
*Source : « Gardien » (niv. 5), « sauvegarde naturelle 10+ » — pas de jet de sauvegarde ici ; rendu par la plus haute R permanente du jeu (+48 PV, +0 à +1 PA).*

**Verdict** ⚖️ · active · 40 PM · `ennemi` / `cc` / portée 1 · zone : les 3 cases devant
```json
{"_id": "competence:verdict", "type": "competence", "nom": "Verdict", "icon": "⚖️",
 "description": "Il ne juge pas : il énonce. Le coup vient après, pour la forme.",
 "vocation": "templier", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "zone": {"forme": "rectangle", "origine": "lanceur", "orientation": "cible", "longueur": 1, "largeur": 3, "decalage": 1},
 "effets": {"degats": "3D10+12", "buffs": {"R": -15}, "duree": 3}}
```
*Source : « Vengeur » (niv. 3), haine testée à la volonté.*

---

## Répurgateur 🔱

*Axe : Volonté et entrave des créatures. Titres : Exalté, Chasseur de Sorcier, Traqueur,
Inquisiteur, Tueur de démon, Rejeton ou Saint.*

### Niveau 3

**Exalté** 🔥 · passive
```json
{"_id": "competence:exalte", "type": "competence", "nom": "Exalté", "icon": "🔥",
 "description": "Sa volonté d'affronter les créatures les plus terrifiantes relève moins du courage que de la pathologie.",
 "vocation": "repurgateur", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Vol": 8}}}
```
*Source : « Exalté » (niv. 3), « ajouter son bonus de Vol aux résistances ».*

**Marque du traqueur** 🎯 · active · 15 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:marque_du_traqueur", "type": "competence", "nom": "Marque du traqueur", "icon": "🎯",
 "description": "Il pose sur la bête un signe qu'elle ne comprend pas, et qui l'empêche désormais de bien fuir.",
 "vocation": "repurgateur", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "1D6", "buffs": {"Ag": -10, "Vol": -6}, "duree": 3}}
```
*Source : « Traqueur » (niv. 3) — la détection des créatures n'est pas une compétence jouable ; rendue en marque qui entrave.*

### Niveau 6

**Chasseur de sorcier** 🧿 · passive
```json
{"_id": "competence:chasseur_de_sorcier", "type": "competence", "nom": "Chasseur de sorcier", "icon": "🧿",
 "description": "Expert de la chasse aux magiciens. Il a appris ce qu'il faut savoir pour défaire ce qu'ils font.",
 "vocation": "repurgateur", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Vol": 10, "Int": 4}}}
```
*Source : « Chasseur de Sorcier » (niv. 3) — les sorts de dissipation ne s'octroient pas par une compétence ; rendu par la `pm_def`.*

**Fer de l'Inquisiteur** 🔱 · active · 25 PM · `ennemi` / `cc` / portée 1
```json
{"_id": "competence:fer_de_l_inquisiteur", "type": "competence", "nom": "Fer de l'Inquisiteur", "icon": "🔱",
 "description": "Le zèle poussé au-delà de ce qu'une conscience ordinaire supporte, et une lame au bout.",
 "vocation": "repurgateur", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "effets": {"degats": "3D8+8"}}
```
*Source : « Inquisiteur » (niv. 5).*

### Niveau 10 — capstone

**Rejeton ou Saint** ⚱️ · passive
```json
{"_id": "competence:rejeton_ou_saint", "type": "competence", "nom": "Rejeton ou Saint", "icon": "⚱️",
 "description": "Il s'est tellement approché de ce qu'il sert qu'il a commencé à s'en nourrir. On ne lui demande plus lequel des deux.",
 "vocation": "repurgateur", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Vol": 10}, "regen_pv": 4}}
```
*Source : « Rejeton ou Saint » (niv. 5), « regagne 1D5 PV après des dommages de vie ou de mort » — l'absorption typée n'existe pas ; rendue en régénération permanente.*

**Tueur de démon** 😈 · active · 40 PM · `ennemi` / `cc` / portée 1 · zone : cône de 2 crans
```json
{"_id": "competence:tueur_de_demon", "type": "competence", "nom": "Tueur de démon", "icon": "😈",
 "description": "Son bras terrorise les démons les plus maléfiques et défait les anges les plus purs. Il ne fait pas la différence.",
 "vocation": "repurgateur", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "cc", "portee": 1,
 "zone": {"forme": "cone", "origine": "lanceur", "orientation": "cible", "longueur": 2, "decalage": 1, "angle": 90},
 "effets": {"degats": "4D10+13", "buffs": {"Vol": -20}, "duree": 3}}
```
*Source : « Tueur de démon » (niv. 5), « −1 à la sauvegarde des démons et des anges » — rendu par un debuff de Vol, qui abaisse la `pm_def` de la cible.*

---

## Ménestrel 🎶

*Axe : Charisme, buffs d'allié à distance, charmes rendus en debuffs. Titres : Célébrité,
Artiste, Bouffon, Étoile, Prodige, Imitateur.*

### Niveau 3

**Célébrité** ⭐ · passive
```json
{"_id": "competence:celebrite", "type": "competence", "nom": "Célébrité", "icon": "⭐",
 "description": "Sa renommée le précède de deux jours de route et lui ouvre des portes qu'il n'a pas frappées.",
 "vocation": "menestrel", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Cha": 8}}}
```
*Source : « Célébrité » (niv. 3). ⚠️ Gain social et marchand — Cha n'a aucune dérivée de combat.*

**Mort de rire** 🤡 · active · 15 PM · `ennemi` / `magique` / portée 5
```json
{"_id": "competence:mort_de_rire", "type": "competence", "nom": "Mort de rire", "icon": "🤡",
 "description": "Une pique lancée au bon moment. L'autre rit, se trouve ridicule, et cesse d'être dangereux.",
 "vocation": "menestrel", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "ennemi", "jet": "magique", "portee": 5,
 "effets": {"buffs": {"Vol": -10, "Ag": -6}, "duree": 3}}
```
*Source : « Bouffon » (niv. 3), charme « mort de rire » (−2 en Vol, −2 à la parade et à l'esquive) — **traduction fidèle** : un debuff pur sans dégâts, accepté par `resolve_action` (« la prise porte »).*

### Niveau 6

**Artiste** 🎭 · passive
```json
{"_id": "competence:artiste", "type": "competence", "nom": "Artiste", "icon": "🎭",
 "description": "La précision de son art atteint les esprits les plus récalcitrants, et il le sait à la seconde près.",
 "vocation": "menestrel", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Cha": 10, "Int": 4}}}
```
*Source : « Artiste » (niv. 3), « +2 à l'effet des charmes ».*

**Hymne de l'Étoile** 🌟 · active · 25 PM · `allie` / portée 5 · zone : les 24 cases autour
```json
{"_id": "competence:hymne_de_l_etoile", "type": "competence", "nom": "Hymne de l'Étoile", "icon": "🌟",
 "description": "Un air lancé par-dessus la mêlée. Celui qui l'entend redresse la garde et oublie de compter ses plaies.",
 "vocation": "menestrel", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "soi", "portee": 1,
 "zone": {"forme": "carre", "origine": "lanceur", "rayon": 2},
 "effets": {"pv": 10, "buffs": {"Vol": 9, "Cha": 5}, "regen_pv": 2, "duree": 5}}
```
*Prolonge `competence:refrain_de_ralliement` (niv. 1), qui visait UN compagnon. Passé en `cible:"soi"` + zone : un chant de ralliement rayonne autour de celui qui chante, il ne se désigne pas. Le ménestrel en profite lui-même (une zone bénéfique sert le lanceur), et elle porte aussi aux montures, aux personnes escortées et aux invocations. Décote large (−50 %) : 24 cases autour de lui.*

### Niveau 10 — capstone

**Étoile** 💫 · passive
```json
{"_id": "competence:etoile", "type": "competence", "nom": "Étoile", "icon": "💫",
 "description": "Sa beauté, sa voix, sa grâce. On ne discute plus de savoir s'il a du talent : on discute de l'avoir vu.",
 "vocation": "menestrel", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Cha": 16, "Vol": 6}}}
```
*Source : « Étoile » (niv. 5), « +1 en Cha au-dessus du maximum ».*

**Chant du Prodige** 🎼 · active · 40 PM · `ennemi` / `magique` / portée 6 · zone : disque de rayon 2
```json
{"_id": "competence:chant_du_prodige", "type": "competence", "nom": "Chant du Prodige", "icon": "🎼",
 "description": "La virtuosité poussée jusqu'à la torpeur : ceux qui l'écoutent glissent vers quelque chose qui ressemble à l'inconscience.",
 "vocation": "menestrel", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "magique", "portee": 6,
 "zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
 "effets": {"degats": "1D8", "buffs": {"F": -12, "Ag": -12, "Vol": -9}, "duree": 4}}
```
*Source : « Prodige » (niv. 5), « charme de faiblesse ». Le capstone du ménestrel n'est pas un burst mais un affaiblissement de MASSE : trois caractéristiques abattues sur un disque de rayon 2, là où les debuffs mono-cible frappent plus fort mais un seul. C'est son identité, et la zone la sert mieux que ne le faisait la version d'avant.*

---

## Prêtre ✝

*Axe : soin, régénération, don de PM. Titres : Guérisseur, Clerc, Augure, Thaumaturge, Prophète,
Oracle.*

### Niveau 3

**Clerc** 📖 · passive
```json
{"_id": "competence:clerc", "type": "competence", "nom": "Clerc", "icon": "📖",
 "description": "Des années à lire et à recopier des piles de livres. Le savoir des grimoires lui vient plus vite qu'aux autres.",
 "vocation": "pretre", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Int": 8}}}
```
*Source : « Clerc » (niv. 3), « double le bonus d'Int pour l'alphabétisation » — l'Int alimente `pm_max` et le toucher magique.*

**Main du guérisseur** 🙏 · active · 15 PM · `allie` / portée 2
```json
{"_id": "competence:main_du_guerisseur", "type": "competence", "nom": "Main du guérisseur", "icon": "🙏",
 "description": "Il améliore n'importe quel soin, qu'il soit naturel ou magique. Souvent d'assez peu, toujours d'assez.",
 "vocation": "pretre", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "allie", "portee": 2,
 "effets": {"pv": 18, "regen_pv": 3, "duree": 4}}
```
*Source : « Guérisseur » (niv. 3).*

### Niveau 6

**Augure** 🔮 · passive
```json
{"_id": "competence:augure", "type": "competence", "nom": "Augure", "icon": "🔮",
 "description": "Un don de voyance modeste, qui lui donne sur la roue du destin une avance de quelques degrés.",
 "vocation": "pretre", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Ch": 10, "Vol": 4}}}
```
*Source : « Augure » (niv. 3), « +1 en Ch au-dessus du maximum » — la Chance déplace les fenêtres de critique (`_seuils_critiques`).*

**Bénédiction du Prophète** 🕊️ · active · 25 PM · `allie` / portée 4
```json
{"_id": "competence:benediction_du_prophete", "type": "competence", "nom": "Bénédiction du Prophète", "icon": "🕊️",
 "description": "Son aura de bienfaisance irradie ceux qui le suivent, qu'ils l'aient demandé ou non.",
 "vocation": "pretre", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "allie", "portee": 4,
 "effets": {"pv": 20, "buffs": {"R": 18, "Vol": 10}, "regen_pv": 3, "duree": 5}}
```
*Source : « Prophète » (niv. 5), « affecte ses compagnons ».*

### Niveau 10 — capstone

**Thaumaturge** ✨ · passive
```json
{"_id": "competence:thaumaturge", "type": "competence", "nom": "Thaumaturge", "icon": "✨",
 "description": "Le nombre de gens morts sous ses mains se compte sur les doigts d'une seule. Il les connaît tous par leur nom.",
 "vocation": "pretre", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Vol": 8, "Int": 4}, "regen_pv": 5}}
```
*Source : « Thaumaturge » (niv. 5) — l'échec de chirurgie qui ne blesse plus n'est pas exprimable ; rendu par la plus forte régénération de PV du jeu.*

**Oracle** 👁️‍🗨️ · active · 40 PM · `allie` / portée 6 · zone : disque de rayon 2
```json
{"_id": "competence:oracle", "type": "competence", "nom": "Oracle", "icon": "👁️‍🗨️",
 "description": "Ses prédictions sont complexes à décrypter et s'avèrent souvent exactes. Celui qu'il désigne ne peut plus vraiment échouer.",
 "vocation": "pretre", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "allie", "portee": 6,
 "zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
 "effets": {"pv": 27, "pm": 15, "buffs": {"Ch": 12, "Vol": 9}, "regen_pv": 3, "regen_pm": 2, "duree": 5}}
```
*Source : « Oracle » (niv. 5), « une réussite automatique » — la réussite forcée n'existe pas ; rendue par un très fort bonus de Chance, qui rapproche les critiques.*

---

## Druide 🌳

*Axe : régénération, endurance, emprise sur le vivant. Titres : Belluaire, Ermite, Chasseur,
Dompteur de monstres, Fils de la nature, Homme-tempête.*

### Niveau 3

**Ermite** 🍄 · passive
```json
{"_id": "competence:ermite", "type": "competence", "nom": "Ermite", "icon": "🍄",
 "description": "Habitué à vivre dans des conditions où l'on ne vit pas. Les maladies s'y sont lassées avant lui.",
 "vocation": "druide", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"R": 6}, "regen_pv": 1}}
```
*Source : « Ermite » (niv. 3), « +2 en résistance à la maladie » — pas de résistances typées ; rendues en endurance et en régénération. Prolonge `competence:symbiose_naturelle` (niv. 0).*

**Trait du chasseur** 🏹 · active · 15 PM · `ennemi` / `cd` / portée 8
```json
{"_id": "competence:trait_du_chasseur", "type": "competence", "nom": "Trait du chasseur", "icon": "🏹",
 "description": "Arc, fronde, javelot, lance : il manie les armes traditionnelles de la chasse comme on respire.",
 "vocation": "druide", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "ennemi", "jet": "cd", "portee": 8,
 "effets": {"degats": "2D8+4"}}
```
*Source : « Chasseur » (niv. 3) — « 1 attaque supplémentaire par round » n'existe pas ; rendue en tir renforcé.*

### Niveau 6

**Belluaire** 🐻 · passive
```json
{"_id": "competence:belluaire", "type": "competence", "nom": "Belluaire", "icon": "🐻",
 "description": "Si proche des bêtes qu'aucune ne l'attaquerait, même poussée par une faim de loup.",
 "vocation": "druide", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Cha": 10, "Vol": 4}}}
```
*Source : « Belluaire » (niv. 3), « inspire respect aux animaux » — le respect n'est pas une mécanique ; rendu par le Charisme (emprise, marchandage, montures).*

**Sève vive** 🌿 · active · 25 PM · `allie` / portée 3 · zone : croix de rayon 1
```json
{"_id": "competence:seve_vive", "type": "competence", "nom": "Sève vive", "icon": "🌿",
 "description": "Il pose la main et la chair se referme comme l'écorce d'un arbre qu'on a entaillé au printemps.",
 "vocation": "druide", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "allie", "portee": 3,
 "zone": {"forme": "cercle", "origine": "cible", "rayon": 1},
 "effets": {"pv": 22, "buffs": {"R": 9}, "regen_pv": 3, "duree": 5}}
```

### Niveau 10 — capstone

**Fils de la nature** 🌳 · passive
```json
{"_id": "competence:fils_de_la_nature", "type": "competence", "nom": "Fils de la nature", "icon": "🌳",
 "description": "Un état de symbiose que la nature lui rend bien, et dont il ne parle jamais.",
 "vocation": "druide", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"R": 12, "Vol": 6}, "regen_pv": 4}}
```
*Source : « Fils de la nature » (niv. 5), « +2 en résistance totale ».*

**Homme-tempête** ⛈️ · active · 40 PM · `ennemi` / `magique` / portée 10 · zone : disque de rayon 2
```json
{"_id": "competence:homme_tempete", "type": "competence", "nom": "Homme-tempête", "icon": "⛈️",
 "description": "Il s'est voué à la maîtrise des éléments du ciel, et le ciel a fini par répondre.",
 "vocation": "druide", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "magique", "portee": 10,
 "zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
 "effets": {"degats": "3D10+10", "buffs": {"V": -2}, "duree": 3}}
```
*Source : « Homme-tempête » (niv. 5), sorts Foudre / Aiguilles de glace / Avalanche. `V: -3` immobilise presque (plancher : une case).*

---

## Chaman 🐺

*Axe : métamorphose — de très gros buffs de soi, payés en Intelligence. Titres : Métamorphe,
Médium, Onirologue, Homme bête, Gardien des esprits, Ancien.*

### Niveau 3

**Onirologue** 💭 · passive
```json
{"_id": "competence:onirologue", "type": "competence", "nom": "Onirologue", "icon": "💭",
 "description": "Ses longues conversations avec les esprits lui ont livré assez du réel pour qu'il cesse d'en avoir peur.",
 "vocation": "chaman", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Vol": 6, "Int": 2}}}
```
*Source : « Onirologue » (niv. 3), « +1 en Vol, Int et Sf contre les sorts » → `pm_def`.*

**Forme de l'esprit totem** 🐗 · active · 15 PM · `soi` / portée 1
```json
{"_id": "competence:forme_esprit_totem", "type": "competence", "nom": "Forme de l'esprit totem", "icon": "🐗",
 "description": "Il laisse l'esprit prendre la place. Ce qui reste de lui suffit à viser, et c'est tout ce qu'il faut.",
 "vocation": "chaman", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "soi", "portee": 1,
 "effets": {"buffs": {"F": 12, "R": 6, "Int": -6}, "duree": 4}}
```
*Source : « Métamorphe » (niv. 3), « −1 dans un des malus de transformation » — le malus d'Int **est** le malus de transformation, gardé exprès : une métamorphose doit coûter l'esprit.*

### Niveau 6

**Métamorphe** 🦅 · passive
```json
{"_id": "competence:metamorphe", "type": "competence", "nom": "Métamorphe", "icon": "🦅",
 "description": "Expert des métamorphoses. Il sait mieux que quiconque compenser les faiblesses de ce avec quoi il fusionne.",
 "vocation": "chaman", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"R": 8, "Vol": 6}}}
```

**Homme bête** 🐺 · active · 25 PM · `soi` / portée 1
```json
{"_id": "competence:homme_bete", "type": "competence", "nom": "Homme bête", "icon": "🐺",
 "description": "L'esprit n'est plus un compagnon qu'il invoque : il vit à l'intérieur, et sort quand on l'y oblige.",
 "vocation": "chaman", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "soi", "portee": 1,
 "effets": {"buffs": {"F": 18, "R": 12, "Ag": 8, "Int": -10}, "regen_pv": 3, "duree": 5}}
```
*Source : « Homme bête » (niv. 5).*

### Niveau 10 — capstone

**Gardien des esprits** 👻 · passive
```json
{"_id": "competence:gardien_des_esprits", "type": "competence", "nom": "Gardien des esprits", "icon": "👻",
 "description": "Il en contrôle plus qu'aucun autre chaman n'en a jamais tenu, et la plupart du temps sans y penser.",
 "vocation": "chaman", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Vol": 14, "Int": 8}}}
```
*Source : « Gardien des esprits » (niv. 5), « +1 esprit invocable par jour » — le compte d'invocations n'existe pas ; rendu en réserve magique (`pm_max = 2·Vol + 2·Int` ⇒ +44 PM).*

**Esprit Antique** 🦣 · active · 40 PM · `soi` / portée 1
```json
{"_id": "competence:esprit_antique", "type": "competence", "nom": "Esprit Antique", "icon": "🦣",
 "description": "Le mammouth, le tigre à dents de sabre, le grand saurien. Un seul, une seule fois, et il faut ensuite s'en remettre.",
 "vocation": "chaman", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "soi", "portee": 1,
 "effets": {"pv": 30, "buffs": {"F": 25, "R": 20, "Ag": 10, "V": 1}, "regen_pv": 5, "duree": 5}}
```
*Source : « Ancien » (niv. 5), « coûte 30 PM et compte pour 2 esprits ». ⚠️ À l'expiration, les PV sont re-clampés sur le `pv_max` non buffé (`combat.py:148-151`) — un chaman qui sort de sa forme antique perd la part de PV qu'elle portait. C'est le comportement normal des gros buffs de R, pas un bug.*

---

## Élémentaliste 🔥

*Axe : Intelligence et dégâts magiques à longue portée. Titres de sorciers : Mage, Arcaniste,
Conjurateur, Archimage, Nexus, Invocateur.*

### Niveau 3

**Affinité des flux** 🌡️ · passive
```json
{"_id": "competence:affinite_des_flux", "type": "competence", "nom": "Affinité des flux", "icon": "🌡️",
 "description": "Les éléments ne lui obéissent pas : ils anticipent, ce qui est plus commode et plus inquiétant.",
 "vocation": "elementaliste", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Int": 8}}}
```
*Prolonge `competence:affinite_elementaire` (niv. 0). Int alimente `pm_max` et `toucher_magique = (3·Int + Vol)//4`.*

**Manteau élémentaire** 🔥 · active · 15 PM · `soi` / portée 1
```json
{"_id": "competence:manteau_elementaire", "type": "competence", "nom": "Manteau élémentaire", "icon": "🔥",
 "description": "Il s'enroule dans l'élément comme dans une couverture. La chaleur passe d'un côté seulement.",
 "vocation": "elementaliste", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "soi", "portee": 1,
 "effets": {"buffs": {"R": 12, "Int": 6}, "duree": 4}}
```

### Niveau 6

**Arcaniste** 📜 · passive
```json
{"_id": "competence:arcaniste", "type": "competence", "nom": "Arcaniste", "icon": "📜",
 "description": "Les arcanes enfermées dans les parchemins ont cessé d'être un secret : il y lit comme dans une facture.",
 "vocation": "elementaliste", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Int": 10, "Vol": 4}}}
```
*Source : « Arcaniste » (niv. 3), « double le bonus de Vol pour la lecture de parchemins ».*

**Décharge primordiale** ⚡ · active · 25 PM · `ennemi` / `magique` / portée 10 · zone : cône de 3 crans
```json
{"_id": "competence:decharge_primordiale", "type": "competence", "nom": "Décharge primordiale", "icon": "⚡",
 "description": "Pas une formule : une ouverture. Ce qui passe au travers n'a pas été façonné par lui.",
 "vocation": "elementaliste", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "ennemi", "jet": "magique", "portee": 10,
 "zone": {"forme": "cone", "origine": "lanceur", "orientation": "cible", "longueur": 3, "decalage": 1, "angle": 90},
 "effets": {"degats": "2D8+5"}}
```
*`jet:"magique"` : résolution sur la `pm_def` de la cible, PA **non** soustraits — un peu plus de dés qu'une frappe `cc` de même palier, qui emprunte en échange les dés de l'arme.*

### Niveau 10 — capstone

**Archimage** 🌀 · passive
```json
{"_id": "competence:archimage", "type": "competence", "nom": "Archimage", "icon": "🌀",
 "description": "Sa maîtrise des pouvoirs de la nature le rend terriblement dangereux, y compris pour lui-même.",
 "vocation": "elementaliste", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Int": 16, "Vol": 6}}}
```
*Source : « Archimage » (niv. 5), « +2 à la force et à l'activation d'un effet de la nature ».*

**Courroux des éléments** 🌋 · active · 40 PM · `ennemi` / `magique` / portée 12 · zone : disque de rayon 2
```json
{"_id": "competence:courroux_des_elements", "type": "competence", "nom": "Courroux des éléments", "icon": "🌋",
 "description": "Il n'appelle plus le feu : il le laisse arriver, et s'écarte de son chemin.",
 "vocation": "elementaliste", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "magique", "portee": 12,
 "zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
 "effets": {"degats": "3D12+12", "buffs": {"R": -15}, "duree": 3}}
```

---

## Magicien de combat 🌀

*Axe : réserve de PM, bouclier arcanique, enchantement d'arme. Titres : Mage, Arcaniste, Nexus.*

### Niveau 3

**Réserve arcanique** 🔷 · passive
```json
{"_id": "competence:reserve_arcanique", "type": "competence", "nom": "Réserve arcanique", "icon": "🔷",
 "description": "Il puise dans sa volonté la puissance qui épuiserait la plupart des magiciens, et n'en fait pas une histoire.",
 "vocation": "mage", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Vol": 8}}}
```
*Source : « Conjurateur » (niv. 3) — relancer un sort à usage limité n'est pas exprimable ; rendu par la réserve (`pm_max = 2·Vol + 2·Int` ⇒ +16 PM).*

**Égide arcanique** 🛡️ · active · 15 PM · `soi` / portée 1
```json
{"_id": "competence:egide_arcanique", "type": "competence", "nom": "Égide arcanique", "icon": "🛡️",
 "description": "Une pellicule d'arcanes épouse sa peau et amortit ce qui arrive. Elle tient le temps qu'il faut.",
 "vocation": "mage", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "soi", "portee": 1,
 "effets": {"buffs": {"R": 12, "Vol": 6}, "esquive": 5, "duree": 4}}
```
*Prolonge `competence:bouclier_arcanique` (niv. 0), qui en est la version passive.*

### Niveau 6

**Nexus** 💠 · passive
```json
{"_id": "competence:nexus", "type": "competence", "nom": "Nexus", "icon": "💠",
 "description": "Un nœud dans la circulation des forces magiques, qui se trouve avoir une adresse et un nom.",
 "vocation": "mage", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Vol": 8, "Int": 6}}}
```
*Source : « Nexus » (niv. 5), « +1D de PM au-dessus du maximum » ⇒ +28 PM.*

**Lame enchantée** ✨ · active · 25 PM · `soi` / portée 1
```json
{"_id": "competence:lame_enchantee", "type": "competence", "nom": "Lame enchantée", "icon": "✨",
 "description": "La magie au service de la guerre, et pas l'inverse : il enchante sa propre arme et va s'en servir.",
 "vocation": "mage", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "soi", "portee": 1,
 "effets": {"buffs": {"F": 20, "Ag": 8}, "duree": 5}}
```

### Niveau 10 — capstone

**Cœur de Nexus** 💠 · passive
```json
{"_id": "competence:coeur_de_nexus", "type": "competence", "nom": "Cœur de Nexus", "icon": "💠",
 "description": "La magie ne le traverse plus : elle s'y arrête un instant, puis repart plus nombreuse.",
 "vocation": "mage", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Vol": 12, "Int": 6}, "regen_pm": 5}}
```
*Le seul `regen_pm` permanent élevé du jeu — la signature du drain magique, et ce qui distingue le magicien de combat de l'élémentaliste.*

**Rupture arcanique** 💥 · active · 40 PM · `ennemi` / `magique` / portée 10 · zone : disque de rayon 2
```json
{"_id": "competence:rupture_arcanique", "type": "competence", "nom": "Rupture arcanique", "icon": "💥",
 "description": "Il ne lance pas un sort : il casse quelque chose, et laisse le monde recoller les morceaux.",
 "vocation": "mage", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "magique", "portee": 10,
 "zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
 "effets": {"degats": "3D10+12", "buffs": {"Vol": -15}, "duree": 3}}
```

---

## Illusionniste 🎭

*Axe : esquive, furtivité, perception détournée. Titres : Voile, Conjurateur, Nexus.*

### Niveau 3

**Silhouette trouble** 🌫️ · passive
```json
{"_id": "competence:silhouette_trouble", "type": "competence", "nom": "Silhouette trouble", "icon": "🌫️",
 "description": "Sa silhouette tremble légèrement. L'œil qui le vise ne sait jamais tout à fait où il est.",
 "vocation": "illusionniste", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Ag": 6}, "esquive": 4}}
```
*Prolonge `competence:voile_d_illusion` (niv. 0), en y ajoutant l'esquive.*

**Double illusoire** 👥 · active · 15 PM · `soi` / portée 1
```json
{"_id": "competence:double_illusoire", "type": "competence", "nom": "Double illusoire", "icon": "👥",
 "description": "Il y en a deux, puis trois. Un seul saigne, mais il faut d'abord trouver lequel.",
 "vocation": "illusionniste", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "soi", "portee": 1,
 "effets": {"buffs": {"Ag": 8}, "esquive": 14, "duree": 4}}
```

### Niveau 6

**Conjurateur** 🎴 · passive
```json
{"_id": "competence:conjurateur", "type": "competence", "nom": "Conjurateur", "icon": "🎴",
 "description": "Manipulateur de perceptions. Ses illusions ont déjà détourné des armées, et il en parle peu.",
 "vocation": "illusionniste", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Int": 10, "Ag": 4}}}
```

**Mirage paralysant** 🌀 · active · 25 PM · `ennemi` / `magique` / portée 8
```json
{"_id": "competence:mirage_paralysant", "type": "competence", "nom": "Mirage paralysant", "icon": "🌀",
 "description": "Il montre à la cible un sol qui n'existe pas. Elle cesse d'avancer, ce qui est déjà beaucoup.",
 "vocation": "illusionniste", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "ennemi", "jet": "magique", "portee": 8,
 "effets": {"degats": "1D8", "buffs": {"Ag": -18, "V": -2}, "duree": 4}}
```

### Niveau 10 — capstone

**Présence effacée** 👻 · passive
```json
{"_id": "competence:presence_effacee", "type": "competence", "nom": "Présence effacée", "icon": "👻",
 "description": "Il n'est pas caché : il est simplement difficile de soutenir l'idée qu'il soit là.",
 "vocation": "illusionniste", "niveau": 10, "mode": "passive",
 "effets": {"furtivite": 18, "esquive": 10}}
```
*Sans `condition` : `furtivite` (état furtif à l'entrée du combat) **et** `esquive` (repli permanent) sont tous deux lus. C'est le seul capstone qui cumule les deux mécaniques de dissimulation.*

**Théâtre des ombres** 🎭 · active · 40 PM · `ennemi` / `magique` / portée 10 · zone : disque de rayon 2
```json
{"_id": "competence:theatre_des_ombres", "type": "competence", "nom": "Théâtre des ombres", "icon": "🎭",
 "description": "Il donne à voir une scène entière. Quand elle se termine, la cible ne sait plus ce qu'elle faisait.",
 "vocation": "illusionniste", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "magique", "portee": 10,
 "zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
 "effets": {"degats": "2D8", "buffs": {"F": -12, "Ag": -12, "Int": -9}, "duree": 4}}
```

---

## Nécromancien 💀

*Axe : Volonté, entrave et dépérissement. Titres de sorciers : Archimage, Nexus, Conjurateur ;
voie ultime, la Liche.*

### Niveau 3

**Chair froide** 🦴 · passive
```json
{"_id": "competence:chair_froide", "type": "competence", "nom": "Chair froide", "icon": "🦴",
 "description": "Son corps a pris les habitudes de ce qu'il fréquente : il saigne moins, et plus lentement.",
 "vocation": "necromancien", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"R": 6, "Vol": 2}}}
```
*Prolonge `competence:affinite_morbide` (niv. 0).*

**Toucher du sépulcre** ⚰️ · active · 15 PM · `ennemi` / `magique` / portée 4
```json
{"_id": "competence:toucher_du_sepulcre", "type": "competence", "nom": "Toucher du sépulcre", "icon": "⚰️",
 "description": "Rien de spectaculaire : la cible a seulement l'impression d'avoir vieilli de quelques années d'un coup.",
 "vocation": "necromancien", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "ennemi", "jet": "magique", "portee": 4,
 "effets": {"degats": "2D8+4", "buffs": {"R": -8}, "duree": 3}}
```

### Niveau 6

**Seigneur des os** 💀 · passive
```json
{"_id": "competence:seigneur_des_os", "type": "competence", "nom": "Seigneur des os", "icon": "💀",
 "description": "Ce qui a été vivant lui répond encore, à condition qu'il insiste un peu.",
 "vocation": "necromancien", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Vol": 10, "Int": 4}}}
```

**Drain vital** 🩸 · active · 25 PM · `ennemi` / `magique` / portée 6
```json
{"_id": "competence:drain_vital", "type": "competence", "nom": "Drain vital", "icon": "🩸",
 "description": "Il prend ce qui tient la cible debout. Ce qu'il en fait ensuite ne regarde personne.",
 "vocation": "necromancien", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "ennemi", "jet": "magique", "portee": 6,
 "effets": {"degats": "3D8+8", "buffs": {"F": -12, "R": -8}, "duree": 3}}
```
*⚠️ Le drain **au sens strict** n'est pas exprimable : sur `cible:"ennemi"`, `resolve_action` n'applique `pv` qu'à un allié ou à soi, jamais en retour d'une attaque. Le vol de vie est donc rendu par « dégâts + affaiblissement durable », et non par un gain de PV du lanceur.*

### Niveau 10 — capstone

**Couronne de liche** 👑 · passive
```json
{"_id": "competence:couronne_de_liche", "type": "competence", "nom": "Couronne de liche", "icon": "👑",
 "description": "La voie ultime, ou son avant-dernière marche. Il a cessé de compter les années depuis un moment.",
 "vocation": "necromancien", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Vol": 16, "Int": 6}}}
```

**Étreinte du tombeau** ⚱️ · active · 40 PM · `ennemi` / `magique` / portée 8 · zone : disque de rayon 2
```json
{"_id": "competence:etreinte_du_tombeau", "type": "competence", "nom": "Étreinte du tombeau", "icon": "⚱️",
 "description": "Le sol se souvient de tous ceux qu'il a reçus, et tend les mains vers celui qui marche dessus.",
 "vocation": "necromancien", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "ennemi", "jet": "magique", "portee": 8,
 "zone": {"forme": "cercle", "origine": "cible", "rayon": 2},
 "effets": {"degats": "3D10+11", "buffs": {"R": -12, "V": -2}, "duree": 4}}
```

---

## Démoniste 😈

*Axe : pactes — de très gros gains payés en Résistance. Titres de sorciers : Conjurateur,
Invocateur, Archimage.*

### Niveau 3

**Marque du pacte** 🔺 · passive
```json
{"_id": "competence:marque_du_pacte", "type": "competence", "nom": "Marque du pacte", "icon": "🔺",
 "description": "Quelque chose, quelque part, lui souffle les mots justes — et tient les comptes.",
 "vocation": "demoniste", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Int": 6, "Vol": 2}}}
```
*Prolonge `competence:pacte_obscur` (niv. 0).*

**Pacte de sang** 🩸 · active · 15 PM · `soi` / portée 1
```json
{"_id": "competence:pacte_de_sang", "type": "competence", "nom": "Pacte de sang", "icon": "🩸",
 "description": "Il avance une part de lui-même contre une avance de puissance. Le taux est mauvais, il le sait.",
 "vocation": "demoniste", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "soi", "portee": 1,
 "effets": {"buffs": {"Int": 14, "Vol": 8, "R": -8}, "duree": 4}}
```
*Le malus de R est délibéré : « chaque pacte consume une part de son âme » (blurb de la vocation). ⚠️ Le malus de R abaisse `pv_max` et re-clampe les PV — le démoniste est réellement plus fragile sous pacte.*

### Niveau 6

**Écaille infernale** 🔥 · passive
```json
{"_id": "competence:ecaille_infernale", "type": "competence", "nom": "Écaille infernale", "icon": "🔥",
 "description": "Sa peau a commencé à ressembler à celle de ses interlocuteurs. Il évite les miroirs.",
 "vocation": "demoniste", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"R": 10, "Int": 4}}}
```

**Griffe du familier** 👹 · active · 25 PM · `ennemi` / `magique` / portée 6 · zone : cône de 2 crans
```json
{"_id": "competence:griffe_du_familier", "type": "competence", "nom": "Griffe du familier", "icon": "👹",
 "description": "Il ouvre à peine. Ce qui passe la main de l'autre côté fait le travail et repart.",
 "vocation": "demoniste", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "ennemi", "jet": "magique", "portee": 6,
 "zone": {"forme": "cone", "origine": "lanceur", "orientation": "cible", "longueur": 2, "decalage": 1, "angle": 90},
 "effets": {"degats": "2D10+6"}}
```

### Niveau 10 — capstone

**Âme gagée** 😈 · passive
```json
{"_id": "competence:ame_gagee", "type": "competence", "nom": "Âme gagée", "icon": "😈",
 "description": "Elle ne lui appartient plus depuis longtemps, et le loyer qu'on lui verse est confortable.",
 "vocation": "demoniste", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Int": 12, "Vol": 6}, "regen_pm": 4}}
```

**Invocation majeure** 🔯 · active · 40 PM · `soi` / portée 1
```json
{"_id": "competence:invocation_majeure", "type": "competence", "nom": "Invocation majeure", "icon": "🔯",
 "description": "Il n'appelle plus une créature : il lui prête sa peau pour la durée du contrat.",
 "vocation": "demoniste", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "soi", "portee": 1,
 "effets": {"pv": 25, "buffs": {"F": 20, "Int": 20, "R": 15}, "regen_pv": 4, "regen_pm": 3, "duree": 5}}
```
*Source : « Invocateur » (niv. 5), « 2 invocations simultanées » — le compte d'invocations n'existe pas ; rendu par la possession du lanceur, seule forme que le moteur sache porter. Même re-clamp de PV à l'expiration que l'Esprit Antique du chaman.*

---

## Lettré 📜

*Axe : Intelligence, régénération de PM, soutien d'atelier. Seule vocation polyvalente
(`MAGIE_POLYVALENTE_VOCATIONS`). Titres : Ingénieur, Érudit, Alchimiste, Génie, Maître artisan,
Enchanteur.*

### Niveau 3

**Érudit** 📖 · passive
```json
{"_id": "competence:erudit", "type": "competence", "nom": "Érudit", "icon": "📖",
 "description": "Sa faculté à apprendre lui fait assimiler le savoir plus vite que les autres, ce qu'il ne se prive pas de rappeler.",
 "vocation": "lettre", "niveau": 3, "mode": "passive",
 "effets": {"buffs": {"Int": 8}}}
```
*Source : « Érudit » (niv. 3), « +10 % de PEX » — le gain d'XP n'est pas modulable par une compétence ; rendu en Intelligence. Prolonge `competence:memoire_encyclopedique` (niv. 0).*

**Formule de l'alchimiste** ⚗️ · active · 15 PM · `soi` / portée 1
```json
{"_id": "competence:formule_de_l_alchimiste", "type": "competence", "nom": "Formule de l'alchimiste", "icon": "⚗️",
 "description": "Un filtre préparé la veille, bu sans cérémonie. Il sait ce qu'il y a dedans, c'est déjà rassurant.",
 "vocation": "lettre", "niveau": 3, "mode": "active", "cout_pm": 15,
 "cible": "soi", "portee": 1,
 "effets": {"pv": 18, "regen_pv": 2, "duree": 4}}
```
*Source : « Alchimiste » (niv. 3), « double le bonus d'Ag pour la compétence Potions ».*

### Niveau 6

**Ingénieur** ⚙️ · passive
```json
{"_id": "competence:ingenieur", "type": "competence", "nom": "Ingénieur", "icon": "⚙️",
 "description": "Un objet qu'il fabrique ne marche pas toujours, mais n'est jamais raté. La nuance a son importance.",
 "vocation": "lettre", "niveau": 6, "mode": "passive",
 "effets": {"buffs": {"Int": 10, "Ag": 4}}}
```
*Source : « Ingénieur » (niv. 3) — l'annulation d'échec critique en fabrication n'existe pas ; rendue en tête et en main.*

**Élixir du maître artisan** 🧪 · active · 25 PM · `allie` / portée 2
```json
{"_id": "competence:elixir_du_maitre_artisan", "type": "competence", "nom": "Élixir du maître artisan", "icon": "🧪",
 "description": "Il le tend sans commentaire. Ce qui est dedans a demandé trois semaines et deux échecs.",
 "vocation": "lettre", "niveau": 6, "mode": "active", "cout_pm": 25,
 "cible": "allie", "portee": 2,
 "effets": {"pv": 30, "pm": 15, "regen_pm": 3, "duree": 5}}
```
*Source : « Maître artisan » (niv. 5). Le lettré est la seule vocation dont le soutien d'allié rend des PM autant que des PV.*

### Niveau 10 — capstone

**Génie** 🧠 · passive
```json
{"_id": "competence:genie", "type": "competence", "nom": "Génie", "icon": "🧠",
 "description": "Son intelligence impressionnerait les plus grands savants, ce qu'il a vérifié à plusieurs reprises.",
 "vocation": "lettre", "niveau": 10, "mode": "passive",
 "effets": {"buffs": {"Int": 16, "Vol": 6}}}
```
*Source : « Génie » (niv. 5), « +1 en Int au-dessus du maximum ».*

**Œuvre de l'Enchanteur** 💎 · active · 40 PM · `soi` / portée 1 · zone : les 8 cases autour
```json
{"_id": "competence:oeuvre_de_l_enchanteur", "type": "competence", "nom": "Œuvre de l'Enchanteur", "icon": "💎",
 "description": "Il a créé les objets magiques les plus puissants de ce monde. Seuls les dieux peuvent prétendre mieux, et ils ne publient pas.",
 "vocation": "lettre", "niveau": 10, "mode": "active", "cout_pm": 40,
 "cible": "soi", "portee": 1,
 "zone": {"forme": "carre", "origine": "lanceur", "rayon": 1},
 "effets": {"pm": 18, "buffs": {"Int": 13, "Vol": 9}, "regen_pm": 3, "duree": 5}}
```
*Source : « Enchanteur » (niv. 5), « triple le bonus d'Ag pour les Objets magiques ».*

---

## Récapitulatif

| vocation | niv. 3 passive / active | niv. 6 passive / active | niv. 10 passive / active |
|---|---|---|---|
| guerrier | Chevalier / Coup de mercenaire | Protecteur / Garde de fer | Mastodonte / Brise-ligne |
| barbare | Conquérant / Frénésie | Vétéran / Annonce de sang | Danseur de guerre / Spasme de furie |
| forestier | Pisteur / Flèche de franc-archer | Rôdeur / Tir d'élite | Éclaireur / Trait du chasseur de monstres |
| duelliste | Gentilhomme / Botte de mousquetaire | Garde / Parade de maître | Maître d'armes / Coup de l'Exécuteur |
| assassin | Surineur / Venin de contact | Maître des ombres / Maître lames | Ombre incarnée / Exécution |
| voleur | Tire-laine / Coup de coupe-jarret | Escamoteur / Fuite de maraudeur | Maraudeur / Coup du bandit |
| moine | Sage / Garde du pèlerin | Vagabond / Poing de légende | Ascète / Souffle du Sensei |
| paladin | Prélat / Frappe du champion | Héros / Serment du martyr | Exarque / Lumière du Purificateur |
| templier | Brise-sort / Arme de justice | Champion de Justice / Bras divin | Gardien / Verdict |
| répurgateur | Exalté / Marque du traqueur | Chasseur de sorcier / Fer de l'Inquisiteur | Rejeton ou Saint / Tueur de démon |
| ménestrel | Célébrité / Mort de rire | Artiste / Hymne de l'Étoile | Étoile / Chant du Prodige |
| prêtre | Clerc / Main du guérisseur | Augure / Bénédiction du Prophète | Thaumaturge / Oracle |
| druide | Ermite / Trait du chasseur | Belluaire / Sève vive | Fils de la nature / Homme-tempête |
| chaman | Onirologue / Forme de l'esprit totem | Métamorphe / Homme bête | Gardien des esprits / Esprit Antique |
| élémentaliste | Affinité des flux / Manteau élémentaire | Arcaniste / Décharge primordiale | Archimage / Courroux des éléments |
| mage | Réserve arcanique / Égide arcanique | Nexus / Lame enchantée | Cœur de Nexus / Rupture arcanique |
| illusionniste | Silhouette trouble / Double illusoire | Conjurateur / Mirage paralysant | Présence effacée / Théâtre des ombres |
| nécromancien | Chair froide / Toucher du sépulcre | Seigneur des os / Drain vital | Couronne de liche / Étreinte du tombeau |
| démoniste | Marque du pacte / Pacte de sang | Écaille infernale / Griffe du familier | Âme gagée / Invocation majeure |
| lettré | Érudit / Formule de l'alchimiste | Ingénieur / Élixir du maître artisan | Génie / Œuvre de l'Enchanteur |

### Répartition des capstones (niveau 10)

| forme du capstone | passives | actives |
|---|---|---|
| gros socle de caractéristiques (+22) | guerrier, duelliste, paladin, templier, ménestrel, chaman, élémentaliste, nécromancien, lettré | — |
| régénération de signature | barbare, moine, répurgateur, prêtre, druide (PV) · mage, démoniste (PM) | — |
| dissimulation | assassin (`furtivite 20`), forestier (`furtivite 18` conditionnelle), illusionniste (`furtivite 18` + `esquive 10`), voleur (`esquive 20`) | — |
| burst pur mono-cible | — | duelliste, assassin, forestier |
| burst de zone | — | guerrier (bande), barbare (tourbillon) |
| burst + entrave, mono-cible | — | voleur |
| burst + entrave, de zone | — | templier, répurgateur, paladin, druide, élémentaliste, mage, illusionniste, nécromancien |
| debuff de masse | — | ménestrel |
| soutien d'allié de zone | — | moine, prêtre |
| métamorphose / possession de soi | — | chaman, démoniste · lettré (de zone) |

### Où vivent les 21 zones

| vocation | zone(s) | forme |
|---|---|---|
| guerrier | N6 `soi`, N10 `ennemi` | carré r1 · rectangle 1×3 devant |
| barbare | N10 `ennemi` | carré r1 (tourbillon) |
| duelliste | N6 `soi` | carré r1 |
| moine | N10 `allie` | croix r1 |
| paladin | N6 `allie`, N10 `ennemi` | croix r1 · disque r2 |
| templier | N10 `ennemi` | rectangle 1×3 devant |
| répurgateur | N10 `ennemi` | cône 2 crans |
| ménestrel | N6 `soi`, N10 `ennemi` | carré r2 · disque r2 |
| prêtre | N10 `allie` | disque r2 |
| druide | N6 `allie`, N10 `ennemi` | croix r1 · disque r2 |
| élémentaliste | N6 `ennemi`, N10 `ennemi` | cône 3 crans · disque r2 |
| mage | N10 `ennemi` | disque r2 |
| illusionniste | N10 `ennemi` | disque r2 |
| nécromancien | N10 `ennemi` | disque r2 |
| démoniste | N6 `ennemi` | cône 2 crans |
| lettré | N10 `soi` | carré r1 |

**Quatre vocations restent sans aucune zone, et c'est délibéré** : l'**assassin** et le
**duelliste** (hors sa parade) sont les vocations du coup unique et placé, le **forestier** celle
du tir précis, le **voleur** celle de l'esquive et du vol — leur donner une nappe effacerait ce
qui les distingue. Elles conservent en échange les plus gros coups unitaires du document.

---

## Ce que la révision 2 a changé

Écrite après les PR #10 (familles, magie noire du répurgateur, invocations) et #11 (zones
d'effet). Les 120 `_id`, les noms et les paliers n'ont pas bougé — seuls les blocs et la doctrine.

| | révision 1 | révision 2 |
|---|---|---|
| zones | inexistantes | **21 entrées** portent un bloc `zone` (13 hostiles, 8 bénéfiques) |
| `hymne_de_l_etoile` | `cible: "allie"`, un compagnon | `cible: "soi"` + carré r2 — un chant rayonne, il ne se désigne pas |
| dégâts des 21 | pleine puissance mono-cible | **décotés de 25 à 50 %** selon la portée de la forme |
| capstones offensifs | tous à `5D10+20` | 3 restent mono-cible à pleine puissance, 8 passent en zone décotée |
| invocations | sujet absent | **documentées comme indisponibles** aux compétences, avec les deux voies possibles |
| `famille` | sujet absent | documentée ; **aucune entrée n'en porte**, et pourquoi |
| répurgateur | école Sainte | école **Démonologie**, `familles_exclues: ["invocation"]` |

**Ce qui n'a pas changé et méritait d'être revérifié** : les 60 passives (une passive ne vise
rien, une `zone` y serait décorative — l'invariant n°6 du vérificateur l'interdit désormais), la
grille de calibrage des paliers, et les quatre vocations laissées sans zone.

---

## Et ensuite

Cette liste n'est **pas importée**. Une fois arbitrée, l'étape suivante est un générateur
`dev/gen_competences_vocations.py` → `jsons/competences_vocations_a_importer.json`, sur le
patron de `dev/gen_armes_tranchantes.py` (dump figé en dur, `_id` déterministes, réimport
idempotent), inscrit au lanceur `/admin/dev-tools` (`utils/dev_tools.py`).

⚠️ Rappel de la convention 11 : `admin_import_bulk` fait un **PUT COMPLET**, jamais un merge, et
ne refuse rien. Les blocs de ce document sont donc des docs entiers — il ne faut jamais en
importer une version partielle.



