# Propositions — compétences de vocation : caractéristiques et mécaniques créatives

**Statut : PROPOSITION, rien n'est importé.** Ce document est à relire et à trier ; ce qui sera retenu passera par un générateur (`dev/competences_1_10/<vocation>.py` ou un lot dédié), jamais à la main.

Chaque compétence proposée ci-dessous a été **construite en doc et passée par les mêmes gardes que le lot 1 → 10** (`check_competences_doc.verifier_competence`, `normaliser_competence`, éligibilité au combat), plus les garde-fous des formules des sorts (buff ≤ `{Car/3}`, jamais V par formule, durée ≤ 6 à 80) et l'unicité des noms contre le dump. La colonne « à 20 → à 80 » donne la valeur résolue pour un lanceur à 20 puis à 80 dans la caractéristique (dés : moyenne).

## Ce qui change par rapport au premier lot à formules

Le lot `competences_caracteristiques_a_importer.json` appliquait une seule règle (« l'effet principal lit UNE caractéristique »). Ici :

| | idée | exemple |
|---|---|---|
| 🧮 | **deux caractéristiques** dans une même formule | `2D8+{F/15}+{R/15}` (Frappe du vétéran) |
| 🧮 | **la taille du dé** comme axe de progression | `1D{Ch/4}` : 1D5 à Ch 20, 1D15 à Ch 60 (Coup de veine) |
| 🧮 | formule sur un champ **secondaire** : durée, portée, % de drain, plafond de drain | `duree: 1+{Cha/30}`, `portee: 6+{Ag/10}`, `drain_pv: 20+{Vol/4}` |
| 🧮 | **coût décroissant** : `cout_pv: 12-{R/8}` (plancher 0) | Rage qui ronge : 10 PV à R 20, 2 PV à R 80 |
| 🧮 | caractéristique **inattendue mais justifiée** | soin du forestier sur l'Int (les plantes), malus du duelliste sur la Cha (le bon mot) |
| ✨ | mécaniques **déjà dans le moteur, presque jamais utilisées** par les compétences | `lien_vie` (1 compétence), `partage_soin` (0), `drain_pm` (0), saut d'un ALLIÉ, zone persistante, esquive maintenue, échange PV → PM |

✨ ne demande **aucun changement de moteur**. Seules les zones persistantes (marquées ⚠️) butent sur la garde (12) du lot, qui refuse `zone` + `maintien` sur une active `ennemi` pour éviter un « mur de feu » involontaire : il faudrait une exception **explicite** (par exemple une clé de donnée du générateur), le moteur, lui, les gère déjà.

## Propositions par vocation

### Guerrier · magie —

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 3 | ⚔️ **Frappe du vétéran** | ennemi / cc / portée `1` · 15 PM | `{degats: 2D8+{F/15}+{R/15}}` | degats 11 → 19 | Deux caractéristiques dans une même formule : la force du coup ET l'endurance de celui qui frappe depuis des heures. |
| 🧮 | 6 | 🪖 **Tenir jusqu'au bout** | soi / portée `1` · 25 PM | `{buffs: {R: 4+{Vol/8}}, duree: 2+{Vol/30}}` | buffs.R 6 → 14<br>duree 2 → 4 | La volonté fixe à la fois la force de la garde ET sa DURÉE (3 tours à Vol 30, 4 à 60). |
| ✨ | 5 | 🛡️ **Bouclier humain** | allie / portée `1` · 12 PM + 3/round | `{lien_vie: {part: 50, reduction: 0}}` | — | LIEN DE VIE porté par un martial : la moitié des coups destinés à l'allié adjacent passe sur le guerrier, tant qu'il paie 3 PM par round. |

### Barbare · magie —

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 4 | 😤 **Rage qui ronge** | ennemi / cc / portée `1` · 18 PM | `{degats: 3D8+{F/10}, cout_pv: 12-{R/8}}` | degats 15.5 → 21.5<br>cout_pv 10 → 2 | Coût en PV DÉCROISSANT : 10 PV à R 20, 2 PV à R 80. Plus le barbare est robuste, moins la rage lui coûte (plancher 0). |
| ✨ | 7 | 🍖 **Festin du carnage** | ennemi / cc / portée `1` · 29 PM · carre rayon 1 | `{degats: 2D8+{F/12}, drain_pv: 30, drain_max: {R/4}}` | degats 10 → 15<br>drain_max 5 → 20 | Drain sommé sur TOUTES les victimes de la zone, plafonné une fois par lancement par la R : plus la mêlée est dense, plus il se nourrit. |
| ✨ | 3 | 🤾 **Lancer de camarade** | allie / portée `1` · 15 PM | `{saut: 4}` | — | SAUT d'un allié : le barbare empoigne un compagnon adjacent et le jette par-dessus la mêlée. Le moteur sait déjà faire, aucune compétence ne s'en sert. |

### Forestier · magie —

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 2 | 🏹 **Tir à longue portée** | ennemi / cd / portée `6+{Ag/10}` · 12 PM | `{degats: 1D8+3}` | portee 8 → 14 | Formule de PORTÉE : l'adresse allonge le tir (8 cases à Ag 20, 14 à 80). La portée de l'arc reste un plancher. |
| 🧮 | 5 | 🌿 **Se fondre dans les fourrés** | soi / portée `1` · 21 PM | `{furtivite: 4+{Ag/10}}` | furtivite 6 → 12 | Furtivité ACTIVE (rare : 10 compétences en tout) dont la qualité suit l'Ag. |
| ✨ | 6 | 🌱 **Cataplasme de sente** | allie / portée `1` · 25 PM | `{soin: 1D6+{Int/10}, regen_pv: 2, duree: 3}` | soin  →  | Un SOIN martial, qui lit l'Int (la connaissance des plantes) et non la Vol : le forestier panse avec ce qu'il a cueilli. |

### Duelliste · magie —

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 3 | 🤺 **Garde élégante** | soi / portée `1` · 15 PM | `{esquive: 3+{Ag/10}, duree: 1+{Cha/30}}` | esquive 5 → 11<br>duree 1 → 3 | L'Ag fait l'esquive, le PANACHE (Cha) la fait durer. |
| ✨ | 6 | 😏 **Humiliation** | ennemi / cc / portée `1` · 25 PM | `{degats: 1D6, buffs: {Vol: -2-{Cha/8}}, duree: 3}` | buffs.Vol -4 → -12 | Un coup du plat de la lame et un bon mot : la VOLONTÉ de la cible s'effondre, à la mesure du charisme du duelliste. |
| ✨ | 8 | 💃 **Danse sur le fil** | soi / portée `1` · 15 PM + 3/round | `{esquive: 4+{Ag/8}}` | esquive 6 → 14 | Esquive MAINTENUE (aucune durée) : elle tient tant que le duelliste paie, et tombe s'il rate un test de concentration. |

### Assassin · magie —

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 4 | 🫀 **Coup au cœur** | ennemi / cc / portée `1` · 18 PM | `{degats: 2D{Ag/8}+{Int/10}}` | degats 5 → 19 | La PRÉCISION (Ag) fait la taille du dé, l'ANATOMIE (Int) le bonus : deux voies de progression distinctes. |
| ✨ | 5 | 🧪 **Venin double** | ennemi / cc / portée `1` · 21 PM | `{degats: 1D6, regen_pv: -2-{Int/20}, regen_pm: -1-{Int/30}, duree: 3}` | regen_pv -3 → -6<br>regen_pm -1 → -3 | Poison sur les DEUX jauges, dosé par la science des poisons (Int). |

### Voleur · magie —

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 2 | 🍀 **Coup de veine** | ennemi / cc / portée `1` · 12 PM | `{degats: 1D{Ch/4}}` | degats 3 → 10.5 | La CHANCE fait la taille du dé : 1D5 à Ch 20, 1D15 à Ch 60. Le coup le plus imprévisible du jeu, et c'est le voleur qui l'a. |
| ✨ | 4 | 👛 **Faire les poches** | ennemi / cc / portée `1` · 10 PM | `{degats: 1D6+{Ag/15}, drain_pm: 60}` | degats 4.5 → 8.5 | DRAIN DE PM (inutilisé à ce jour) : le voleur récupère en mana 60 % des PV qu'il arrache. Peu cher, il se finance lui-même. |
| ✨ | 6 | 🌫️ **Nuage de farine** | soi / portée `1` · 25 PM · carre rayon 1 | `{esquive: 2+{Ag/10}, duree: 2}` | esquive 4 → 10 | Un sac crevé au sol : tout le groupe autour du voleur devient difficile à viser. |

### Moine · magie Sainte

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 3 | 👊 **Poing du souffle** | ennemi / cc / portée `1` · 15 PM | `{degats: 2D6+{Vol/10}+{Ag/20}}` | degats 10 → 19 | Le ki (Vol) avant le geste (Ag). |
| ✨ | 5 | 🌬️ **Don du souffle** | allie / portée `1` · 0 PM | `{pm: 4+{Vol/6}, cout_pv: 6}` | pm 7 → 17 | ÉCHANGE : le moine paie de son corps (6 PV) pour rendre du mana à un allié. Aucun PM dépensé. |
| ✨ | 8 | 🪷 **Corps de lotus** | soi / portée `1` · 15 PM + 3/round | `{buffs: {R: {Vol/6}}, regen_pv: 2}` | buffs.R 3 → 13 | Méditation MAINTENUE : résistance et régénération tant qu'il garde sa concentration. |

### Paladin · magie Sainte

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 4 | ⚖️ **Châtiment juste** | ennemi / cc / portée `1` · 18 PM | `{degats: 2D8+{Vol/8}}` | degats 11 → 19 | La FOI frappe, pas le bras : un paladin de Vol haute et de F moyenne reste redoutable. |
| ✨ | 6 | 🤝 **Serment de garde** | allie / portée `4` · 20 PM + 4/round | `{lien_vie: {part: 60, reduction: 20}}` | — | LIEN DE VIE avec réduction : 20 % du coup se perd dans la foi, le paladin prend 60 % du reste. |
| ✨ | 3 | 🙌 **Mains secourables** | allie / portée `1` · 15 PM | `{soin: 1D8+{Vol/10}, partage_soin: 30}` | soin  →  | PARTAGE DE SOIN (inutilisé par les compétences) : 30 % des PV rendus reviennent au paladin. |

### Templier · magie Bataille

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 5 | 🧱 **Mur de foi** | allie / portée `4` · 21 PM · cercle rayon 1 | `{esquive: 2+{R/12}, duree: 3}` | esquive 3 → 8 | Esquive de groupe tirée de la R : le templier ne protège pas par la grâce mais par l'exemple. |
| ✨ | 8 | 🔥 **Bûcher purificateur** | ennemi / magique / portée `3` · 25 PM + 3/round · rectangle longueur 3 largeur 1 | `{degats: 2D6+{Vol/12}}` | degats 8 → 13 | ZONE PERSISTANTE (le « Mur de feu » des sorts) : une ligne de flammes qui brûle QUICONQUE la traverse, alliés compris. Fanatisme assumé. ⚠️ *assouplir la garde (12) du lot* |

### Répurgateur · magie Démonologie

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 4 | ✝️ **Rite d'expulsion** | ennemi / magique / portée `3` · 18 PM | `{degats: 1D8, degats_pm: 2D6+{Vol/10}}` | degats_pm 9 → 15 | Frappe surtout le MANA : arme contre les lanceurs et les démons. |
| ✨ | 6 | 🧂 **Fer et sel** | ennemi / cc / portée `1` · 25 PM | `{degats: 1D6, buffs: {Vol: -3-{Int/8}}, regen_pm: -2-{Int/25}, duree: 3}` | buffs.Vol -5 → -13<br>regen_pm -2 → -5 | Sa SCIENCE des démons (Int) dose l'entrave : volonté brisée et mana qui fuit. |
| ✨ | 9 | 🩸 **Purge par le sang** | ennemi / magique / portée `3` · 37 PM | `{degats: 4D10+{Vol/8}, cout_pv: 10, drain_pm: 30}` | degats 24 → 32 | Il brûle son propre sang pour arracher le mana de la cible : coût en PV + drain de PM. |

### Élémentaliste · magie Élémentaire

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 2 | 🌪️ **Rafale tranchante** | ennemi / magique / portée `1` · 12 PM · cone longueur 2 | `{degats: 1D{Int/6}}` | degats 2 → 7 | Cône dont la taille du dé suit l'Int. |
| ✨ | 7 | 🔥 **Ligne de braise** | ennemi / magique / portée `4` · 22 PM + 3/round · rectangle longueur 1 largeur 3 | `{degats: 2D6+{Int/12}}` | degats 8 → 13 | Zone persistante de travers (largeur 3), pour COUPER un couloir. ⚠️ *assouplir la garde (12) du lot* |
| ✨ | 5 | 🪨 **Peau de basalte** | soi / portée `1` · 12 PM + 2/round | `{buffs: {R: 3+{Int/8}}, esquive: 3}` | buffs.R 5 → 13 | Armure de pierre maintenue, sans durée. |

### Magicien de combat · magie Bataille

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 3 | 🔮 **Projectile savant** | ennemi / magique / portée `4+{Int/15}` · 15 PM | `{degats: 2D{Int/8}}` | degats 3 → 11<br>portee 5 → 9 | Dé ET portée tirés de l'Int. |
| ✨ | 9 | 💥 **Surcharge arcanique** | ennemi / magique / portée `6` · 45 PM · ⏱ 3 PA | `{degats: 6D10+{Int/5}, cout_pv: 10}` | degats 37 → 49 | Incantation de 3 PA + coût en PV : le coup le plus lourd du mage, qu'on voit venir. |

### Illusionniste · magie Illusoire

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 2 | 🪞 **Reflet trompeur** | soi / portée `1` · 12 PM | `{esquive: 2+{Cha/8}, duree: 1+{Int/25}}` | esquive 4 → 12<br>duree 1 → 4 | Le reflet convainc (Cha) et tient (Int). |
| ✨ | 5 | 🔀 **Permutation** | allie / portée `6` · 21 PM | `{saut: 4}` | — | Un allié disparaît et réapparaît 4 cases plus loin : SAUT d'un allié, à distance. |
| ✨ | 7 | 😱 **Terreur nocturne** | ennemi / magique / portée `5` · 29 PM | `{buffs: {Vol: -3-{Cha/8}}, regen_pm: -3, duree: 3}` | buffs.Vol -5 → -13 | Entrave sans dégâts : la terreur brise la volonté et fait fuir le mana. |

### Lettré · magie Illusoire

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 3 | 📝 **Point faible noté** | ennemi / magique / portée `5` · 15 PM | `{buffs: {R: -3-{Int/8}}, duree: 2+{Int/40}}` | buffs.R -5 → -13<br>duree 2 → 4 | Il a LU sur cette bête : la résistance de la cible chute à proportion de son savoir. |
| ✨ | 6 | 📖 **Lecture à voix haute** | allie / portée `4` · 25 PM · cercle rayon 1 | `{pm: 3+{Int/10}}` | pm 5 → 11 | Rend du MANA à un groupe : le lettré comme batterie du groupe. |

### Druide · magie Nature

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 2 | 🌵 **Ronces mordantes** | ennemi / magique / portée `5` · 12 PM | `{degats: 1D{Vol/10}, buffs: {V: -2}, duree: 2}` | degats 1.5 → 4.5 | Entrave des JAMBES (V −2, fixe : V ne passe jamais par une formule) ; les épines suivent la Vol. |
| ✨ | 5 | 🌳 **Sève partagée** | allie / portée `4` · 21 PM | `{soin: 2D6+{Vol/10}, partage_soin: 25}` | soin  →  | Le soin circule entre le druide et le blessé. |
| ✨ | 8 | 🌿 **Racines étouffantes** | ennemi / magique / portée `5` · 25 PM + 3/round · cercle rayon 1 | `{degats: 1D8+{Vol/15}}` | degats 5.5 → 9.5 | Un parterre de ronces qui blesse à chaque pas — zone persistante. ⚠️ *assouplir la garde (12) du lot* |

### Chaman · magie Nature

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 4 | 🥁 **Transe des ancêtres** | soi / portée `1` · 18 PM | `{buffs: {F: 3+{Cha/8}, Vol: 2+{Cha/12}}, duree: 3}` | buffs.F 5 → 13<br>buffs.Vol 3 → 8 | Les ancêtres répondent à la voix (Cha) du chaman. |
| ✨ | 6 | 👻 **Fardeau des esprits** | allie / portée `3` · 20 PM + 3/round | `{lien_vie: {part: 40, reduction: 30}}` | — | Lien de vie où les ESPRITS absorbent 30 % : le chaman en prend moins qu'un paladin, mais protège de plus loin. |

### Prêtre · magie Sainte

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 2 | 🙏 **Oraison du chevet** | allie / portée `4` · 12 PM | `{soin: 1D8+{Vol/8}}` | soin  →  | Le soin le plus simple, enfin indexé sur la foi. |
| ✨ | 6 | 🕯️ **Martyre** | allie / portée `1` · 10 PM | `{pv: 10+{Vol/4}, cout_pv: 12}` | pv 15 → 30 | Le prêtre donne SA vie : 12 PV dépensés, 17 à 30 rendus. Peu de mana, beaucoup de sacrifice. |

### Nécromancien · magie Nécromancie

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 3 | 🦴 **Toucher de la tombe** | ennemi / magique / portée `1` · 15 PM | `{degats: 2D6+{Int/12}, drain_pv: 20+{Vol/4}}` | degats 8 → 13<br>drain_pv 25 → 40 | Le POURCENTAGE de drain suit la Vol (25 % à Vol 20, 40 % à 80). |
| ✨ | 6 | 🩸 **Pacte de chair** | soi / portée `1` · 0 PM | `{pm: 8+{Int/5}, cout_pv: 15-{R/10}}` | pm 12 → 24<br>cout_pv 13 → 7 | Convertit des PV en PM, à un coût que la R adoucit. |
| ✨ | 8 | 🌑 **Sangsue d'âme** | ennemi / magique / portée `4` · 25 PM | `{degats: 2D8+{Int/10}, drain_pm: 40, drain_max: 20}` | degats 11 → 17 | Drain de MANA plafonné : le nécromancien se recharge sur ses victimes. |

### Ménestrel · magie Illusoire

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 2 | 🎵 **Couplet entraînant** | allie / portée `4` · 12 PM · cercle rayon 1 | `{buffs: {Ag: 2+{Cha/10}}, duree: 1+{Cha/30}}` | buffs.Ag 4 → 10<br>duree 1 → 3 | Le charisme fait la force ET la durée de la chanson. |
| ✨ | 5 | 🍺 **Tournée générale** | allie / portée `4` · 21 PM · cercle rayon 1 | `{soin: 1D6+{Cha/10}, partage_soin: 20}` | soin  →  | Soin de groupe ; le ménestrel se nourrit des applaudissements (20 % des PV rendus). |
| ✨ | 7 | 🎻 **Fausse note** | ennemi / magique / portée `1` · 29 PM · cone longueur 3 | `{degats_pm: 1D6+{Cha/12}, buffs: {Int: -2-{Cha/10}}, duree: 2}` | degats_pm 4.5 → 9.5<br>buffs.Int -4 → -10 | Une dissonance qui siphonne le mana et brouille l'esprit, en cône. |
| ✨ | 4 | 🎶 **Refrain tenu** | soi / portée `1` · 10 PM + 3/round · carre rayon 1 | `{buffs: {Vol: 2+{Cha/10}}}` | buffs.Vol 4 → 10 | Buff de groupe MAINTENU : tant qu'il chante, ceux qui l'entouraient au lancement tiennent bon. |

### Démoniste · magie Démonologie

| | niv | compétence | forme | effets | à 20 → à 80 | l'idée |
|---|---|---|---|---|---|---|
| 🧮 | 4 | 🔥 **Brasier du pacte** | ennemi / magique / portée `5` · 18 PM | `{degats: 2D8+{Int/10}, cout_pv: 6-{Vol/15}}` | degats 11 → 17<br>cout_pv 5 → 1 | Le prix en sang baisse quand la volonté du démoniste tient le démon en laisse. |
| ✨ | 6 | 😈 **Soif du pacte** | ennemi / magique / portée `4` · 25 PM | `{degats: 3D8+{Int/10}, cout_pv: 8, drain_pv: 50, drain_max: {Vol/3}}` | degats 15.5 → 21.5<br>drain_max 6 → 26 | Payer en sang pour se nourrir du sang d'un autre : coût fixe, gain plafonné par la Vol. |
## Idées qui demanderaient du moteur neuf

Hors de portée sans développement : chacune se décide **avant** d'être écrite (CLAUDE.md §13).

| idée | vocations | ce qui manque aujourd'hui |
|---|---|---|
| **Active conditionnée au terrain** : « Embuscade sylvestre » plus forte en forêt, « Appel des morts » au cimetière | forestier, druide, nécromancien | `condition` n'est relue que pour la furtivité des passives (`furtivite_passive`) ; `_lancer_capacite` l'ignore |
| **Bonus selon l'état** : « Achever » (+dés si la cible est sous 25 % PV), « Rage du désespoir » (sous 50 % PV du lanceur) | assassin, barbare | aucun opérateur d'état de PV dans les effets |
| **Repousser / attirer** une cible d'une ou deux cases | guerrier, templier, élémentaliste | le saut ne déplace que soi ou un allié |
| **Provocation** : forcer les monstres à viser le lanceur | guerrier, templier, paladin | l'IA monstre choisit sa cible seule |
| **Invocation par compétence** : esprit-loup du chaman, nuée du druide | chaman, druide | le bloc `invocation` n'est lu que sur un `sort:*` |
| **Canalisation par compétence** : « Canal dégagé » du mage, qui annule la pénalité de charge 3 tours | mage, moine | `effets.canalisation` n'est pas recopié dans l'effet à durée de combat (`_empiler_effet_combat`) et ne compte pas dans `part_durative` : une active qui le porterait serait sans effet |
| **Munition spéciale** : flèche enflammée qui consomme une flèche dédiée | forestier, assassin | les compétences n'ont pas de composants |
| **Formules sur `maintien`, `incantation`, `saut`, `lien_vie.part`** | toutes | hors de `FORMULE_CLES_ENTIERES` ; `saut` et `lien_vie` sont bornés à part |
| **Passives à formule** : « +{Vol/10} en R » qui grandit avec le personnage | toutes | `bonus_passifs` ne résout aucune formule |

## Pour passer à l'import

1. Cocher les propositions retenues (ou renommer, reniveler).
2. Les placer en entrées de `dev/competences_1_10/<vocation>.py`. ⚠️ Le compte par niveau du lot (4 / 2 + 5) est **déjà plein** : il faut soit remplacer une entrée existante, soit en faire un lot à part, hors règle de compte.
3. Formules et mécaniques neuves exigent d'étendre les archétypes du générateur (aujourd'hui des valeurs d'`ECHELLE` uniquement) ou un archétype « libre » qui prend ses `effets` tels quels.
4. Pour les zones persistantes : décider de l'exception à la garde (12).
5. Animation `animation:capa_*` sonore à choisir pour chaque active.
