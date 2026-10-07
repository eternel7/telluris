# Compétences de vocation — niveaux 1 à 10

**Document GÉNÉRÉ par `python dev/gen_competences_1_10.py`** — ne pas retoucher : les données vivent dans `dev/competences_1_10/<vocation>.py`, les valeurs dans l'échelle `ECHELLE` du générateur. Import : `jsons/competences_vocations_1_10_a_importer.json`.

Référentiel : `telluris-dump-20261007-134648.json` + `jsons/*_a_importer.json`.

## Règle de compte

À chaque niveau de 1 à 10, **existantes comprises (pièges inclus)** :

| groupe | passives | actives | total |
|---|---|---|---|
| sans magie | 2 | 5 | 7 |
| avec magie | existantes seulement | complément | 4 |

Les vocations à magie ne reçoivent **aucune passive** neuve. Chaque active neuve porte une animation `animation:capa_*` et son son ; un cône porte en plus sa nappe (`animation_zone`). Les passives n'ont pas d'animation : le combat ne les joue jamais.

## Récapitulatif

| vocation | magie | passives neuves | actives neuves | total neuf |
|---|---|---|---|---|
| Assassin | — | 11 | 47 | 58 |
| Barbare | — | 17 | 46 | 63 |
| Chaman | Nature | 0 | 34 | 34 |
| Démoniste | Démonologie | 0 | 34 | 34 |
| Druide | Nature | 0 | 34 | 34 |
| Duelliste | — | 17 | 47 | 64 |
| Élémentaliste | Élémentaire | 0 | 34 | 34 |
| Forestier | — | 8 | 46 | 54 |
| Guerrier | — | 17 | 45 | 62 |
| Illusionniste | Illusoire | 0 | 34 | 34 |
| Lettré | Illusoire | 0 | 34 | 34 |
| Magicien de combat | Bataille | 0 | 34 | 34 |
| Ménestrel | Illusoire | 0 | 33 | 33 |
| Moine | Sainte | 0 | 33 | 33 |
| Nécromancien | Nécromancie | 0 | 34 | 34 |
| Paladin | Sainte | 0 | 33 | 33 |
| Prêtre | Sainte | 0 | 33 | 33 |
| Répurgateur | Démonologie | 0 | 34 | 34 |
| Templier | Bataille | 0 | 34 | 34 |
| Voleur | — | 8 | 47 | 55 |
| **total** | | **78** | **750** | **828** |

## Échelle par niveau

| niveau | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| `pm` | 10 | 12 | 15 | 18 | 21 | 25 | 29 | 33 | 37 | 40 |
| `des` | 1D8+3 | 2D6+3 | 2D8+3 | 2D8+5 | 3D8+4 | 3D8+6 | 3D10+7 | 4D10+6 | 4D10+9 | 5D10+12 |
| `des_petite` | 1D6+2 | 1D8+3 | 2D6+3 | 2D6+5 | 2D8+5 | 3D6+6 | 3D8+5 | 3D8+8 | 3D10+8 | 4D10+8 |
| `des_moyenne` | 1D6+1 | 1D6+3 | 1D8+4 | 2D6+3 | 2D6+5 | 2D8+4 | 2D8+6 | 3D8+4 | 3D8+6 | 3D10+6 |
| `des_large` | 1D4+1 | 1D6+2 | 1D8+2 | 1D8+4 | 2D6+3 | 2D6+5 | 2D8+4 | 2D8+6 | 3D8+4 | 3D8+7 |
| `buff` | 8 | 9 | 10 | 12 | 13 | 14 | 16 | 17 | 18 | 20 |
| `malus` | 6 | 7 | 8 | 9 | 10 | 12 | 13 | 14 | 15 | 16 |
| `duree` | 3 | 3 | 3 | 3 | 4 | 4 | 4 | 4 | 5 | 5 |
| `poison` | 3 | 3 | 4 | 4 | 5 | 5 | 6 | 6 | 7 | 8 |
| `soin` | 16 | 18 | 20 | 23 | 26 | 30 | 34 | 38 | 42 | 45 |
| `posture_pm` | 6 | 7 | 8 | 9 | 10 | 12 | 13 | 15 | 16 | 18 |
| `posture_tour` | 2 | 2 | 3 | 3 | 3 | 4 | 4 | 5 | 5 | 6 |
| `p_pts` | 2 | 2 | 3 | 3 | 3 | 4 | 4 | 4 | 5 | 5 |
| `p_esquive` | 3 | 3 | 4 | 4 | 5 | 5 | 6 | 6 | 7 | 8 |

## Assassin 🗡

### Niveau 1 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🧊 **Main froide** — *Une main qui ne tremble pas, même au moment de tuer.* | passive | — | permanent | Ag +2 | — |
| 🐾 **Pas feutrés** — *Dans le noir, il n'est qu'un souffle de plus.* | passive | — | permanent | furtivité 4 (sous-terrain, catacombe, donjon, grotte, couvert, humide, mine) | — |
| 🗡️ **Coup de dague** — *Rapide, discret, précis.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | lame · 🔊 sword sound.wav |
| 🦵 **Entaille au tendon** — *Un coup bas qui coupe la fuite.* | active | 10 PM | ennemi / cc / portée 1 | 1D4 dégâts · Ag -6 · 3 tours | saignee · 🔊 sword sound.wav |
| 👣 **Glissade** — *Il glisse d'une ombre à l'autre.* | active | 10 PM | soi / portée 1 | saut 2 cases | furtif · 🔊 swish_2.wav |
| 🧪 **Lame enduite** — *Une goutte de venin sur le fil, et la plaie brûle.* | active | 10 PM | ennemi / cc / portée 1 | 1D4 dégâts · régén PV -3 · 3 tours | poison · 🔊 17.mp3 |
| ❄️ **Sang-froid du tueur** — *Le cœur ralentit, le regard se fixe.* | active | 10 PM | soi / portée 1 | Ag +8 Vol +4 · 4 tours | furtif · 🔊 swish_2.wav |

### Niveau 2 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌫️ **Silhouette effacée** — *On le regarde sans le voir.* | passive | — | permanent | esquive 3 | — |
| 🔪 **Coup dans le dos** — *La lame entre là où la victime ne regardait pas.* | active | 12 PM | ennemi / cc / portée 1 | 2D6+3 dégâts | saignee · 🔊 sword sound.wav |
| ⚔️ **Double lame** — *Ses deux lames frappent en même temps, à gauche et à droite.* | active | 12 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 1D8+3 dégâts | lame · 🔊 sword sound.wav |
| 🫙 **Fiole de belladone** — *Une poudre qui embrume l'esprit et vide les forces.* | active | 12 PM | ennemi / cc / portée 1 | 1D6 dégâts · régén PM -2 · 3 tours | poison · 🔊 17.mp3 |
| 🪢 **Garrot** — *Une cordelette autour de la gorge, juste le temps d'affaiblir.* | active | 12 PM | ennemi / cc / portée 1 | 1D6 dégâts · F -7 Vol -3 · 3 tours | saignee · 🔊 sword sound.wav |
| 🌑 **Pas dans l'ombre** — *Il recule dans une ombre et disparaît un instant.* | active | 12 PM | soi / portée 1 | Ag +4 · esquive 7 · 3 tours | furtif · 🔊 swish_2.wav |

### Niveau 3 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🕷️ **Patience de l'araignée** — *Il peut attendre des heures pour un seul geste.* | passive | — | permanent | Vol +3 | — |
| ❤️ **Perce-cœur** — *La lame cherche le cœur entre deux côtes.* | active | 15 PM | ennemi / cc / portée 1 | 2D8+3 dégâts | lame · 🔊 sword sound.wav |
| 💨 **Poudre de pavot** — *Un nuage de poudre qui engourdit les membres.* | active | 15 PM | ennemi / cc / portée 1 | 1D6+1 dégâts · Ag -8 Int -4 · 3 tours | poudre · 🔊 swish_2.wav |
| 🌑 **Saut de l'ombre** — *Il disparaît ici pour réapparaître derrière sa cible.* | active | 15 PM | soi / portée 1 | saut 3 cases | furtif · 🔊 swish_2.wav |
| 🐍 **Venin d'aspic** — *Un venin lent, qui ne pardonne pas.* | active | 15 PM | ennemi / cc / portée 1 | 1D6+1 dégâts · régén PV -4 · 3 tours | poison · 🔊 17.mp3 |

### Niveau 4 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🐍 **Réflexes de vipère** — *Il esquive comme frappe le serpent : avant qu'on ne bouge.* | passive | — | permanent | esquive 4 | — |
| 🌸 **Fleur de lames** — *Il tourne, et ses deux lames ouvrent une fleur sanglante.* | active | 18 PM | ennemi / cc / portée 1 · carre rayon 1 | 2D6+3 dégâts | lame · 🔊 sword sound.wav |
| 🗡️ **Lame de miséricorde** — *La dague fine qu'on glisse dans la visière.* | active | 18 PM | ennemi / cc / portée 1 | 2D8+5 dégâts | saignee · 🔊 sword sound.wav |
| 🩸 **Sang du contrat** — *Il s'ouvre la main pour sceller la mort de la cible.* | active | 18 PM | ennemi / cc / portée 1 | 3D8+5 dégâts · coûte 7 PV | saignee · 🔊 sword sound.wav |
| 🧪 **Toxine paralysante** — *La victime sent ses jambes se dérober.* | active | 18 PM | ennemi / cc / portée 1 | 1D8 dégâts · Ag -9 F -4 · 3 tours | poison · 🔊 17.mp3 |
| 🌫️ **Voile de fumée** — *Une fiole brisée au sol, et il n'est plus là.* | active | 18 PM | soi / portée 1 | Ag +6 · esquive 9 · 3 tours | poudre · 🔊 swish_2.wav |

### Niveau 5 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌙 **Œil de nuit** — *Il voit dans le noir comme d'autres en plein jour.* | passive | — | permanent | Int +3 | — |
| ☠️ **Ciguë** — *Le poison des philosophes, pour ceux qui parlent trop.* | active | 21 PM | ennemi / cc / portée 1 | 1D8+2 dégâts · régén PV -5 · 4 tours | poison · 🔊 17.mp3 |
| 🎯 **Concentration mortelle** — *Plus rien n'existe que la cible.* | active | 10 PM + 3/round | soi / portée 1 | Ag +16 F +8 | marque · 🔊 17.mp3 |
| 🌿 **Essence de mandragore** — *Une essence qui ronge la volonté.* | active | 21 PM | ennemi / cc / portée 1 | 1D8+2 dégâts · régén PM -3 · 4 tours | poison · 🔊 17.mp3 |
| 🐈 **Saut du chat** — *D'un toit à l'autre, d'une ombre à l'autre.* | active | 21 PM | soi / portée 1 | saut 3 cases | saut · 🔊 swish_4.wav |
| 🔪 **Égorgement** — *Un geste, et la gorge s'ouvre.* | active | 21 PM | ennemi / cc / portée 1 | 3D8+4 dégâts | saignee · 🔊 sword sound.wav |

### Niveau 6 — 3 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🗡️ **Lame dans les reins** — *Un coup sous la cuirasse, là où elle ne protège pas.* | active | 25 PM | ennemi / cc / portée 1 | 3D8+6 dégâts | lame · 🔊 sword sound.wav |
| 💀 **Marque de mort** — *La cible sait qu'elle est condamnée, et ses forces la quittent.* | active | 25 PM | ennemi / cc / portée 1 | 2D6+2 dégâts · Vol -12 Ag -6 · 4 tours | marque · 🔊 17.mp3 |
| ☁️ **Nuage toxique** — *Une fiole lancée, et le poison se répand sur le groupe.* | active | 25 PM | ennemi / cc / portée 1 · cercle rayon 1 | 3D6+6 dégâts | poison · 🔊 17.mp3 |
| 😮‍💨 **Voler le souffle** — *Un coup au plexus, et la victime ne peut plus rien.* | active | 25 PM | ennemi / cc / portée 1 | 2D6+2 dégâts · 2D6+2 aux PM | ombre · 🔊 17.mp3 |

### Niveau 7 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌑 **Ombre parmi les ombres** — *Dans les souterrains, il est l'obscurité même.* | passive | — | permanent | furtivité 10 (sous-terrain, catacombe, donjon, grotte, couvert, humide, mine) | — |
| 💀 **Assassinat** — *Un seul coup, celui pour lequel on l'a payé.* | active | 29 PM | ennemi / cc / portée 1 | 3D10+7 dégâts | saignee · 🔊 sword sound.wav |
| 🗡️ **Danse des dagues** — *Les dagues volent autour de lui comme des guêpes.* | active | 29 PM | ennemi / cc / portée 1 · carre rayon 2 | 2D8+4 dégâts | lame · 🔊 sword sound.wav |
| 👣 **Pas de l'assassin** — *Il franchit la salle sans un bruit.* | active | 29 PM | soi / portée 1 | saut 4 cases | furtif · 🔊 swish_2.wav |
| 🩸 **Saignée silencieuse** — *Il boit la vie de sa victime avec sa lame.* | active | 29 PM | ennemi / cc / portée 1 | 3D10+7 dégâts · drain 35 % (max 20) | drain · 🔊 17.mp3 |
| 🦂 **Venin du scorpion noir** — *Le poison le plus cher du marché noir.* | active | 29 PM | ennemi / cc / portée 1 | 2D6+4 dégâts · régén PV -6 · 4 tours | poison · 🔊 17.mp3 |

### Niveau 8 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💨 **Insaisissable** — *On le frappe, et ce n'est déjà plus lui.* | passive | — | permanent | esquive 6 | — |
| 🐍 **Coup du cobra** — *Une détente fulgurante, sans prévenir.* | active | 33 PM | ennemi / cc / portée 1 | 4D10+6 dégâts | lame · 🔊 sword sound.wav |
| 💉 **Oubli de la douleur** — *Une drogue qui fait oublier ses blessures le temps d'un coup.* | active | 33 PM | ennemi / cc / portée 1 | 4D10+10 dégâts · coûte 12 PV | rage · 🔊 power_up_sound_v3.ogg |
| 😴 **Poudre de sommeil** — *Un nuage qui alourdit les paupières et les bras.* | active | 33 PM | ennemi / cc / portée 1 | 2D8+2 dégâts · Ag -14 Vol -7 · 4 tours | poudre · 🔊 swish_2.wav |
| 🖤 **Venin de l'âme** — *Un poison qui n'attaque pas le corps, mais l'esprit.* | active | 33 PM | ennemi / cc / portée 1 | 2D8+2 dégâts · régén PM -4 · 4 tours | poison · 🔊 17.mp3 |
| 🪭 **Éventail de dagues** — *Une poignée de couteaux lancés en éventail.* | active | 33 PM | ennemi / cc / portée 1 · cone longueur 2 | 3D8+8 dégâts | impact_plaie + nappe cone_griffe · 🔊 animal melee sound.wav |

### Niveau 9 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🧊 **Cœur de glace** — *Plus aucune émotion ne passe : il est la lame.* | passive | — | permanent | Vol +5 | — |
| ☠️ **Main de la mort** — *Chaque geste est économe, et chaque geste tue.* | passive | — | permanent | Ag +5 | — |
| 🌫️ **Brume empoisonnée** — *Une brume verte qui s'étend et ronge les poumons.* | active | 37 PM | ennemi / cc / portée 1 · cercle rayon 2 | 3D8+6 dégâts | poison · 🔊 17.mp3 |
| 🤫 **Exécution silencieuse** — *La victime meurt sans avoir crié.* | active | 37 PM | ennemi / cc / portée 1 | 4D10+9 dégâts | saignee · 🔊 sword sound.wav |
| 🌑 **Ombre mortelle** — *Il surgit de l'ombre la plus lointaine.* | active | 37 PM | soi / portée 1 | saut 5 cases | furtif · 🔊 swish_2.wav |
| 🌑 **Pacte de l'ombre** — *Il appelle l'obscurité à lui et s'y installe.* | active | 16 PM + 5/round | soi / portée 1 | Ag +21 Vol +10 | ombre · 🔊 17.mp3 |
| ☠️ **Peste noire** — *Une contagion distillée dans une fiole.* | active | 37 PM | ennemi / cc / portée 1 | 2D8+4 dégâts · régén PV -7 · 5 tours | poison · 🔊 17.mp3 |

### Niveau 10 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🖤 **Maître de la guilde noire** — *Son nom ne se prononce qu'à voix basse.* | passive | — | permanent | esquive 8 | — |
| 💨 **Disparition** — *Il n'était jamais là.* | active | 40 PM | soi / portée 1 | Ag +10 · esquive 15 · 5 tours | furtif · 🔊 swish_2.wav |
| ⚗️ **Fiole du maître empoisonneur** — *Son chef-d'œuvre : un poison sans antidote.* | active | 40 PM | ennemi / cc / portée 1 | 3D8+2 dégâts · régén PV -8 · 5 tours | poison · 🔊 17.mp3 |
| 🗡️ **Fléau silencieux** — *Il traverse le groupe ennemi, et derrière lui chacun saigne.* | active | 40 PM | ennemi / cc / portée 1 · carre rayon 2 | 3D8+7 dégâts | lame · 🔊 sword sound.wav |
| ⚰️ **Mort certaine** — *Il n'a jamais raté un contrat.* | active | 40 PM | ennemi / cc / portée 1 | 5D10+12 dégâts | saignee · 🔊 sword sound.wav |

## Barbare 🪓

### Niveau 1 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💪 **Bras noueux** — *Des bras qui ont fendu plus de bûches que de crânes — pour l'instant.* | passive | — | permanent | F +2 | — |
| 🏔️ **Fils des steppes** — *Le froid et la faim ont forgé ce corps bien avant les armes.* | passive | — | permanent | R +2 | — |
| 🪓 **Coup de hache** — *Pas de technique : la hache monte, la hache tombe.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | coup_lourd · 🔊 melee sound.wav |
| 😱 **Hurlement** — *Un cri de bête qui glace le sang de ceux qui l'entendent.* | active | 10 PM | ennemi / cc / portée 1 | 1D4 dégâts · Vol -6 · 3 tours | rage · 🔊 power_up_sound_v3.ogg |
| 🩸 **Morsure du fer** — *Il frappe si fort que le manche lui brûle les mains.* | active | 10 PM | ennemi / cc / portée 1 | 2D6+4 dégâts · coûte 4 PV | saignee · 🔊 sword sound.wav |
| 🐗 **Ruée** — *Il fonce tête baissée et franchit la distance d'un seul élan.* | active | 10 PM | soi / portée 1 | saut 2 cases | saut · 🔊 swish_4.wav |
| 🔥 **Échauffement** — *Le sang commence à battre aux tempes.* | active | 10 PM | soi / portée 1 | F +8 · 4 tours | rage · 🔊 power_up_sound_v3.ogg |

### Niveau 2 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 😠 **Fureur latente** — *La colère qui couve répare ce que les coups défont.* | passive | — | permanent | régén PV +1 | — |
| 🐻 **Peau de bête** — *Sous les fourrures, une peau qui ne craint ni lame ni griffe.* | passive | — | permanent | R +2 | — |
| 💥 **Fracas** — *Le métal hurle contre le métal.* | active | 12 PM | ennemi / cc / portée 1 | 2D6+3 dégâts | coup_lourd · 🔊 melee sound.wav |
| 🌋 **Sang qui bout** — *Il laisse monter la rage et la tient au bord des lèvres.* | active | 7 PM + 2/round | soi / portée 1 | F +12 | rage · 🔊 power_up_sound_v3.ogg |
| 🪓 **Taille sauvage** — *Un revers aveugle qui frappe tout ce qui bouge devant lui.* | active | 12 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 1D8+3 dégâts | balayage · 🔊 swish_3.wav |
| 🐏 **Tête la première** — *Un coup de front qui laisse l'ennemi hébété.* | active | 12 PM | ennemi / cc / portée 1 | 1D6 dégâts · Int -7 Ag -3 · 3 tours | coup_lourd · 🔊 melee sound.wav |

### Niveau 3 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🔥 **Sang chaud des clans** — *Le sang de ses ancêtres coule plus vite que celui des autres.* | passive | — | permanent | F +3 | — |
| 📣 **Cri des ancêtres** — *Le cri des morts du clan passe par sa gorge, et les vivants se lèvent.* | active | 15 PM | soi / portée 1 · carre rayon 1 | F +7 Vol +3 · 3 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| 💀 **Fendeur de crânes** — *Un coup vertical qui ne laisse rien à recoudre.* | active | 15 PM | ennemi / cc / portée 1 | 2D8+3 dégâts | coup_lourd · 🔊 melee sound.wav |
| 🐻 **Griffes de l'ours** — *Il lacère comme une bête, et les plaies ne se referment pas.* | active | 15 PM | ennemi / cc / portée 1 | 1D6+1 dégâts · régén PV -4 · 3 tours | griffe · 🔊 animal melee sound.wav |
| 🩸 **Saignée furieuse** — *Plus il saigne, plus il frappe fort.* | active | 15 PM | ennemi / cc / portée 1 | 3D6+6 dégâts · coûte 6 PV | rage · 🔊 power_up_sound_v3.ogg |

### Niveau 4 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🐺 **Indomptable** — *Rien ne l'arrête, rien ne le plie.* | passive | — | permanent | Vol +3 | — |
| 🐾 **Instinct de la meute** — *Comme le loup, il sent le coup venir dans son dos.* | passive | — | permanent | esquive 4 | — |
| 🐆 **Bond du fauve** — *D'un saut il est sur sa proie, avant qu'elle ne lève son arme.* | active | 18 PM | soi / portée 1 | saut 3 cases | saut · 🔊 swish_4.wav |
| 🦣 **Frappe du mammouth** — *Un choc qui fait plier les genoux.* | active | 18 PM | ennemi / cc / portée 1 | 1D8 dégâts · Ag -9 R -4 · 3 tours | coup_lourd · 🔊 melee sound.wav |
| 🪓 **Hache rouge** — *La hache revient rouge à chaque passage.* | active | 18 PM | ennemi / cc / portée 1 | 2D8+5 dégâts | saignee · 🔊 sword sound.wav |
| 🍺 **Ivresse du combat** — *La douleur s'efface, il ne reste que la joie de frapper.* | active | 18 PM | soi / portée 1 | F +12 R +6 · 4 tours | rage · 🔊 power_up_sound_v3.ogg |
| 🌀 **Tourbillon sauvage** — *Il tourne sur lui-même, hache tendue, en hurlant.* | active | 18 PM | ennemi / cc / portée 1 · carre rayon 1 | 2D6+3 dégâts | balayage · 🔊 swish_3.wav |

### Niveau 5 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🧌 **Cuir de troll** — *On dit qu'un troll a été son père. On ne le dit pas devant lui.* | passive | — | permanent | R +3 | — |
| 🏋️ **Muscles d'airain** — *Il porte sa hache à une main, comme une branche morte.* | passive | — | permanent | F +3 | — |
| 🦴 **Brise-os** — *Le bruit de l'os qui casse couvre le fracas des armes.* | active | 21 PM | ennemi / cc / portée 1 | 3D8+4 dégâts | coup_lourd · 🔊 melee sound.wav |
| 🐗 **Charge du sanglier** — *Il renverse tout sur son passage.* | active | 21 PM | ennemi / cc / portée 1 | 1D8+2 dégâts · Ag -10 · 4 tours | griffe · 🔊 animal melee sound.wav |
| 🌾 **Fauche** — *La hache passe à hauteur de genou, et trois ennemis tombent.* | active | 21 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 2D8+5 dégâts | balayage · 🔊 swish_3.wav |
| 🩸 **Folie sanglante** — *Il se mord jusqu'au sang et se jette en avant.* | active | 21 PM | ennemi / cc / portée 1 | 3D8+8 dégâts · coûte 8 PV | rage · 🔊 power_up_sound_v3.ogg |
| 🔥 **Rage partagée** — *Sa furie déborde sur ceux qui combattent à ses côtés.* | active | 21 PM | soi / portée 1 · carre rayon 1 | F +9 · 4 tours | rage · 🔊 power_up_sound_v3.ogg |

### Niveau 6 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🫀 **Cœur de bête** — *Il bouge comme un animal, sans prévenir ni réfléchir.* | passive | — | permanent | esquive 5 | — |
| 🐾 **Griffe de la bête** — *Il lacère devant lui comme un ours debout.* | active | 25 PM | ennemi / cc / portée 1 · cone longueur 2 | 3D6+6 dégâts | impact_plaie + nappe cone_griffe · 🔊 animal melee sound.wav |
| ⚔️ **Massacre** — *Un coup, puis un autre, jusqu'à ce que ce soit fini.* | active | 25 PM | ennemi / cc / portée 1 | 3D8+6 dégâts | saignee · 🔊 sword sound.wav |
| 🪨 **Peau de pierre** — *La rage durcit sa peau jusqu'à ce que les lames y rebondissent.* | active | 12 PM + 4/round | soi / portée 1 | R +17 | garde · 🔊 sword sound.wav |
| 🦁 **Rugissement** — *Un rugissement qui fait trembler les mains ennemies.* | active | 25 PM | ennemi / cc / portée 1 | 2D6+2 dégâts · Vol -12 F -6 · 4 tours | rage · 🔊 power_up_sound_v3.ogg |

### Niveau 7 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🗿 **Colosse** — *Il dépasse tout le monde d'une tête, et d'une hache.* | passive | — | permanent | F +4 | — |
| 🪶 **Volonté du clan** — *Le clan entier tient debout dans sa poitrine.* | passive | — | permanent | Vol +4 | — |
| 🦘 **Bond du berserk** — *Il saute par-dessus le mur de boucliers.* | active | 29 PM | soi / portée 1 | saut 4 cases | saut · 🔊 swish_4.wav |
| ⛰️ **Fendoir des montagnes** — *Un coup à fendre la roche, porté sur un homme.* | active | 29 PM | ennemi / cc / portée 1 | 3D10+7 dégâts | coup_lourd · 🔊 melee sound.wav |
| 🩸 **Hémorragie** — *La plaie qu'il laisse ne se ferme pas.* | active | 29 PM | ennemi / cc / portée 1 | 2D6+4 dégâts · régén PV -6 · 4 tours | saignee · 🔊 sword sound.wav |
| 🌪️ **Tornade de fer** — *Une rotation folle dont il ne sort qu'après le dernier cri.* | active | 29 PM | ennemi / cc / portée 1 · carre rayon 2 | 2D8+4 dégâts | balayage · 🔊 swish_3.wav |
| 🔥 **Transe sanglante** — *Il entre dans une transe où seule compte la prochaine victime.* | active | 29 PM | ennemi / cc / portée 1 | 4D10+6 dégâts · coûte 10 PV | rage · 🔊 power_up_sound_v3.ogg |

### Niveau 8 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ♾️ **Inusable** — *Il guérit de blessures qui auraient tué deux hommes.* | passive | — | permanent | régén PV +2 | — |
| 🦴 **Ossature de géant** — *Ses os ont la densité du chêne vieux de mille ans.* | passive | — | permanent | R +4 | — |
| 🧱 **Briseur de lignes** — *Il entre dans le rang ennemi comme un coin dans une bûche.* | active | 33 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 3D8+8 dégâts | balayage · 🔊 swish_3.wav |
| ⚡ **Coup de tonnerre** — *Le coup tombe comme la foudre sur l'arbre seul.* | active | 33 PM | ennemi / cc / portée 1 | 4D10+6 dégâts | coup_lourd · 🔊 melee sound.wav |
| 🔥 **Furie du clan** — *Le clan hurle avec lui, et chaque bras frappe plus fort.* | active | 33 PM | soi / portée 1 · carre rayon 2 | F +12 R +6 · 4 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| 🐻 **Griffes du grand ours** — *Deux revers en croix, larges comme des pattes d'ours.* | active | 33 PM | ennemi / cc / portée 1 · cone longueur 2 | 3D8+8 dégâts | impact_plaie + nappe cone_griffe · 🔊 animal melee sound.wav |
| 😱 **Terreur des steppes** — *Son seul regard fait reculer les braves.* | active | 33 PM | ennemi / cc / portée 1 | 2D8+2 dégâts · Vol -14 Ag -7 · 4 tours | rage · 🔊 power_up_sound_v3.ogg |

### Niveau 9 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🔥 **Fureur éternelle** — *La rage ne le quitte plus, même dans son sommeil.* | passive | — | permanent | F +5 | — |
| 🧊 **Insensible** — *Il ne sent plus les coups, il les voit seulement venir.* | passive | — | permanent | esquive 7 | — |
| 😡 **Berserk** — *Il cesse de penser, il ne fait plus que tuer.* | active | 16 PM + 5/round | soi / portée 1 | F +21 R +10 | rage · 🔊 power_up_sound_v3.ogg |
| 🏔️ **Bond de l'avalanche** — *Il dévale sur l'ennemi comme la neige des cimes.* | active | 37 PM | soi / portée 1 | saut 5 cases | saut · 🔊 swish_4.wav |
| 💀 **Décapitation** — *Un geste ample, définitif.* | active | 37 PM | ennemi / cc / portée 1 | 4D10+9 dégâts | saignee · 🔊 sword sound.wav |
| 🩸 **Folie du massacre** — *Il sacrifie sa chair pour le coup le plus terrible de sa vie.* | active | 37 PM | ennemi / cc / portée 1 | 5D10+10 dégâts · coûte 13 PV | rage · 🔊 power_up_sound_v3.ogg |
| 🌋 **Séisme** — *Il frappe le sol, et la terre jette ses ennemis à bas.* | active | 37 PM | ennemi / cc / portée 1 · carre rayon 2 | 3D8+4 dégâts | coup_lourd · 🔊 melee sound.wav |

### Niveau 10 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 👹 **Avatar de la rage** — *Les clans le croient habité par l'esprit de la guerre.* | passive | — | permanent | F +5 | — |
| 🌪️ **Carnage** — *Un cercle de mort, au centre duquel il hurle.* | active | 40 PM | ennemi / cc / portée 1 · carre rayon 2 | 3D8+7 dégâts | balayage · 🔊 swish_3.wav |
| 🪓 **Coup du fléau des clans** — *Le coup dont les chants des steppes se souviendront.* | active | 40 PM | ennemi / cc / portée 1 | 5D10+12 dégâts | coup_lourd · 🔊 melee sound.wav |
| 📯 **Cri du dernier clan** — *Le cri qui a précédé chaque victoire de son peuple.* | active | 40 PM | soi / portée 1 · carre rayon 2 | F +14 Vol +7 · 5 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| 🩸 **Sang pour sang** — *Chaque goutte qu'il fait couler lui revient en force.* | active | 40 PM | ennemi / cc / portée 1 | 5D10+12 dégâts · drain 40 % (max 20) | saignee · 🔊 sword sound.wav |

## Chaman 🐺

### Niveau 1 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🪶 **Bénédiction ancestrale** — *Les ancêtres posent la main sur la plaie.* | active | 10 PM | allie / portée 4 | +16 PV | soin_nature · 🔊 power_up_sound_v2.ogg |
| 👻 **Cri de l'esprit** — *Un cri qui appelle un esprit hostile sur la cible.* | active | 10 PM | ennemi / magique / portée 6 | 1D4 dégâts · Vol -6 · 3 tours | totem · 🔊 power_up_sound_v2.ogg |
| 🐻 **Force de l'ours** — *L'esprit de l'ours lui prête sa force.* | active | 10 PM | soi / portée 1 | F +8 R +4 · 4 tours | totem · 🔊 power_up_sound_v2.ogg |
| 🐺 **Griffe du loup** — *Ses ongles s'allongent en griffes le temps d'un coup.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | griffe · 🔊 animal melee sound.wav |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🐈 **Bond du chat sauvage** — *Il bondit avec la souplesse du chat.* | active | 12 PM | soi / portée 1 | saut 2 cases | totem · 🔊 power_up_sound_v2.ogg |
| 👤 **Esprit voleur** — *Un esprit vole l'énergie de la cible.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · 1D6+1 aux PM | spectre · 🔊 17.mp3 |
| 🐍 **Morsure du serpent** — *Un esprit-serpent mord la cible.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · régén PV -3 · 3 tours | poison · 🔊 17.mp3 |
| 🦅 **Œil du faucon** — *L'esprit du faucon aiguise le regard d'un compagnon.* | active | 12 PM | allie / portée 4 | Ag +9 Int +4 · 3 tours | totem · 🔊 power_up_sound_v2.ogg |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🐗 **Ruée du sanglier-esprit** — *Il fonce comme le sanglier et renverse l'ennemi.* | active | 15 PM | ennemi / cc / portée 1 | 1D6+1 dégâts · Ag -8 · 3 tours | griffe · 🔊 animal melee sound.wav |
| 🥁 **Tambour des esprits** — *Le tambour bat, et les esprits fortifient le groupe.* | active | 15 PM | soi / portée 1 · carre rayon 1 | Vol +7 F +3 · 3 tours | totem · 🔊 power_up_sound_v2.ogg |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🤒 **Fièvre des marais** — *Un esprit de fièvre ronge la volonté de la cible.* | active | 18 PM | ennemi / magique / portée 6 | 1D8 dégâts · régén PM -3 · 3 tours | poison · 🔊 17.mp3 |
| ⚡ **Foudre des ancêtres** — *Les ancêtres frappent du haut des nuages.* | active | 18 PM | ennemi / magique / portée 6 | 2D8+5 dégâts | foudre · 🔊 17.mp3 |
| 🐺 **Hurlement de la meute** — *Un hurlement qui fait trembler tout un groupe d'ennemis.* | active | 18 PM | ennemi / magique / portée 6 · cercle rayon 1 | 2D6+5 dégâts | appel_sauvage · 🔊 animal melee sound.wav |
| 👁️ **Veille de l'esprit** — *Un esprit veille sur lui et détourne les coups.* | active | 9 PM + 3/round | soi / portée 1 | Vol +15 R +7 | totem · 🔊 power_up_sound_v2.ogg |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦷 **Crocs de l'esprit** — *L'esprit-loup mord et lui rend la vie volée.* | active | 21 PM | ennemi / cc / portée 1 | 3D8+4 dégâts · drain 30 % | griffe · 🔊 animal melee sound.wav |
| 💚 **Esprit guérisseur** — *Un esprit bienveillant veille sur un compagnon.* | active | 21 PM | allie / portée 4 | régén PV +3 · 5 tours | soin_nature · 🔊 power_up_sound_v2.ogg |
| 👺 **Masque des morts** — *Il revêt le masque des morts, et l'ennemi recule.* | active | 21 PM | ennemi / magique / portée 6 | 1D8+2 dégâts · Vol -10 F -5 · 4 tours | spectre · 🔊 17.mp3 |
| 🌀 **Transe** — *Une transe qui ouvre à un compagnon la source des esprits.* | active | 21 PM | allie / portée 4 | +16 PM | totem · 🔊 power_up_sound_v2.ogg |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦅 **Ailes du faucon** — *Les ailes de l'esprit l'emportent.* | active | 25 PM | soi / portée 1 | saut 4 cases | vent · 🔊 swish_4.wav |
| 🐻 **Griffes de l'ours-esprit** — *Une patte immense d'esprit lacère devant lui.* | active | 25 PM | ennemi / magique / portée 6 · cone longueur 2 | 3D6+6 dégâts | impact_plaie + nappe cone_griffe · 🔊 animal melee sound.wav |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⛓️ **Chaînes spirituelles** — *Des chaînes d'esprit lient la cible.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · Ag -13 Vol -6 · 4 tours | spectre · 🔊 17.mp3 |
| 🐗 **Esprit du sanglier** — *La fureur du sanglier dans un seul coup.* | active | 29 PM | ennemi / cc / portée 1 | 3D10+7 dégâts | griffe · 🔊 animal melee sound.wav |
| 💀 **Fléau des esprits** — *Les esprits hantent la cible et la consument.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · régén PV -6 · 4 tours | spectre · 🔊 17.mp3 |
| 🗿 **Totem de guerre** — *Il plante un totem, et la troupe se bat comme une meute.* | active | 29 PM | soi / portée 1 · carre rayon 2 | F +11 Ag +5 · 4 tours | totem · 🔊 power_up_sound_v2.ogg |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💃 **Danse de l'esprit** — *Une danse qui soigne tous ceux qui l'entourent.* | active | 33 PM | allie / portée 4 · cercle rayon 1 | +23 PV | totem · 🔊 power_up_sound_v2.ogg |
| ⛈️ **Orage ancestral** — *Les ancêtres déchaînent l'orage sur les ennemis.* | active | 33 PM | ennemi / magique / portée 6 · cercle rayon 2 | 3D8+4 dégâts | foudre · 🔊 17.mp3 |
| 🐻 **Peau de l'ours** — *Il revêt la peau de l'ours-esprit.* | active | 15 PM + 5/round | soi / portée 1 | R +20 F +10 | totem · 🔊 power_up_sound_v2.ogg |
| 👻 **Vol d'âme** — *Il arrache un morceau d'âme à la cible.* | active | 33 PM | ennemi / magique / portée 6 | 2D8+2 dégâts · 2D8+1 aux PM | spectre · 🔊 17.mp3 |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🐺 **Bond du loup-garou** — *Un bond surhumain, porté par l'esprit du loup.* | active | 37 PM | soi / portée 1 | saut 5 cases | griffe · 🔊 animal melee sound.wav |
| 💀 **Chant des morts** — *Les morts chantent dans la tête de la cible.* | active | 37 PM | ennemi / magique / portée 6 | 2D8+4 dégâts · régén PM -5 · 5 tours | spectre · 🔊 17.mp3 |
| 🗿 **Fureur totémique** — *Tous les esprits frappent en même temps.* | active | 37 PM | ennemi / magique / portée 6 | 4D10+9 dégâts | totem · 🔊 power_up_sound_v2.ogg |
| 🔥 **Rituel du grand esprit** — *Un long chant qui appelle le grand esprit.* | active | 48 PM · ⏱ 3 PA | ennemi / magique / portée 6 | 5D10+10 dégâts | totem · 🔊 power_up_sound_v2.ogg |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🐻 **Avatar totémique** — *Il devient l'esprit lui-même.* | active | 18 PM + 6/round | soi / portée 1 | F +23 R +11 | totem · 🔊 power_up_sound_v2.ogg |
| ⚡ **Colère des ancêtres** — *Les ancêtres frappent tout autour de lui.* | active | 40 PM | ennemi / magique / portée 6 · carre rayon 2 | 3D8+7 dégâts | foudre · 🔊 17.mp3 |

## Démoniste 😈

### Niveau 1 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 😈 **Malédiction** — *Une malédiction qui affaiblit la cible.* | active | 10 PM | ennemi / magique / portée 6 | 1D4 dégâts · Vol -6 · 3 tours | demon_buff · 🔊 power_up_sound_v3.ogg |
| 📜 **Pacte mineur** — *Il paie de son sang un sort plus puissant.* | active | 10 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · coûte 4 PV | rage · 🔊 power_up_sound_v3.ogg |
| 👹 **Peau de démon** — *Sa peau se couvre d'écailles infernales.* | active | 10 PM | soi / portée 1 | R +8 Int +4 · 4 tours | demon_buff · 🔊 power_up_sound_v3.ogg |
| 🔥 **Trait infernal** — *Un trait de flamme infernale.* | active | 10 PM | ennemi / magique / portée 6 | 1D8+3 dégâts | projectile_infernal · 🔊 foom_0.wav |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🕳️ **Faille** — *Une faille s'ouvre, il y entre, et ressort ailleurs.* | active | 12 PM | soi / portée 1 | saut 2 cases | portail_infernal · 🔊 foom_0.wav |
| 🔥 **Flammes de l'abîme** — *Des flammes qui brûlent l'âme autant que le corps.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · régén PV -3 · 3 tours | feu · 🔊 foom_0.wav |
| 🩸 **Sang pour le démon** — *Il offre le sang de la cible à son démon, qui lui en rend une part.* | active | 12 PM | ennemi / magique / portée 6 | 2D6+3 dégâts · drain 25 % | drain · 🔊 17.mp3 |
| 🌀 **Siphon infernal** — *Il aspire la magie de la cible au profit de ses maîtres.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · 1D6+1 aux PM | drain · 🔊 17.mp3 |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌋 **Pluie de soufre** — *Une pluie de soufre ardent sur les ennemis.* | active | 15 PM | ennemi / magique / portée 6 · cercle rayon 1 | 2D6+3 dégâts | soufre · 🔊 foom_0.wav |
| 👁️ **Regard du démon** — *Le regard du démon paralyse la cible.* | active | 15 PM | ennemi / magique / portée 6 | 1D6+1 dégâts · Ag -8 Vol -4 · 3 tours | demon_buff · 🔊 power_up_sound_v3.ogg |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🛡️ **Bouclier infernal** — *Un bouclier de flammes noires l'entoure.* | active | 9 PM + 3/round | soi / portée 1 | R +15 Vol +7 | demon_buff · 🔊 power_up_sound_v3.ogg |
| 🖤 **Corruption de l'âme** — *Une corruption qui ronge la volonté de la cible.* | active | 18 PM | ennemi / magique / portée 6 | 1D8 dégâts · régén PM -3 · 3 tours | demon_buff · 🔊 power_up_sound_v3.ogg |
| 🎁 **Don du démon** — *Il partage avec un compagnon l'énergie de son pacte.* | active | 18 PM | allie / portée 4 | +14 PM | demon_buff · 🔊 power_up_sound_v3.ogg |
| 🔱 **Lance de l'enfer** — *Une lance de feu infernal.* | active | 18 PM | ennemi / magique / portée 6 | 2D8+5 dégâts | projectile_infernal · 🔊 foom_0.wav |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⛓️ **Chaînes de l'enfer** — *Des chaînes infernales enserrent la cible.* | active | 21 PM | ennemi / magique / portée 6 | 1D8+2 dégâts · Ag -10 F -5 · 4 tours | demon_buff · 🔊 power_up_sound_v3.ogg |
| 💥 **Explosion infernale** — *Une explosion de feu noir.* | active | 21 PM | ennemi / magique / portée 6 · cercle rayon 2 | 2D6+5 dégâts | explosion_feu · 🔊 foom_0.wav |
| 🤒 **Fièvre infernale** — *Une fièvre qui brûle de l'intérieur.* | active | 21 PM | ennemi / magique / portée 6 | 1D8+2 dégâts · régén PV -5 · 4 tours | soufre · 🔊 foom_0.wav |
| 📜 **Pacte de puissance** — *Il sacrifie sa chair pour une puissance infernale.* | active | 21 PM | ennemi / magique / portée 6 | 3D8+8 dégâts · coûte 8 PV | rage · 🔊 power_up_sound_v3.ogg |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 👻 **Rapt d'âme** — *Il arrache un fragment d'âme à la cible.* | active | 25 PM | ennemi / magique / portée 6 | 3D8+6 dégâts · drain 35 % | drain · 🔊 17.mp3 |
| 🌋 **Souffle de l'abîme** — *Un souffle de flammes infernales.* | active | 25 PM | ennemi / magique / portée 6 · cone longueur 3 | 2D8+4 dégâts | impact_brulure + nappe cone_souffle_feu · 🔊 foom_0.wav |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🔥 **Feu de l'âme** — *Un feu qui brûle l'âme de la cible.* | active | 29 PM | ennemi / magique / portée 6 | 3D10+7 dégâts | projectile_infernal · 🔊 foom_0.wav |
| 👹 **Forme démoniaque** — *Il prend un instant la forme de son démon.* | active | 13 PM + 4/round | soi / portée 1 | F +19 R +9 | demon_buff · 🔊 power_up_sound_v3.ogg |
| 😱 **Peur infernale** — *Une terreur venue des enfers.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · Vol -13 Ag -6 · 4 tours | demon_buff · 🔊 power_up_sound_v3.ogg |
| 🕳️ **Siphon de l'abîme** — *L'abîme aspire la magie de la cible.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · 2D8 aux PM | drain · 🔊 17.mp3 |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 📜 **Malédiction de l'abîme** — *Une malédiction qui coupe la cible de toute magie.* | active | 33 PM | ennemi / magique / portée 6 | 2D8+2 dégâts · régén PM -4 · 4 tours | demon_buff · 🔊 power_up_sound_v3.ogg |
| 🩸 **Pacte de sang majeur** — *Un pacte majeur, payé au prix fort.* | active | 33 PM | ennemi / magique / portée 6 | 4D10+10 dégâts · coûte 12 PV | rage · 🔊 power_up_sound_v3.ogg |
| 🚪 **Porte de l'enfer** — *Il ouvre une porte vers l'enfer, et en ressort ailleurs.* | active | 33 PM | soi / portée 1 | saut 4 cases | portail_infernal · 🔊 foom_0.wav |
| 🔥 **Tempête de feu noir** — *Un tourbillon de feu noir autour de lui.* | active | 33 PM | ennemi / magique / portée 6 · carre rayon 2 | 2D8+6 dégâts | feu · 🔊 foom_0.wav |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🍷 **Banquet de l'abîme** — *L'abîme se nourrit de la cible, et lui en rend une part.* | active | 37 PM | ennemi / magique / portée 6 | 4D10+9 dégâts · drain 40 % (max 20) | drain · 🔊 17.mp3 |
| 🔥 **Flamme du seigneur démon** — *La flamme d'un seigneur démon.* | active | 37 PM | ennemi / magique / portée 6 | 4D10+9 dégâts | projectile_infernal · 🔊 foom_0.wav |
| ☠️ **Peste infernale** — *Une peste venue des enfers.* | active | 37 PM | ennemi / magique / portée 6 | 2D8+4 dégâts · régén PV -7 · 5 tours | soufre · 🔊 foom_0.wav |
| ⛧ **Rituel infernal** — *Un rituel long qui ouvre une brèche sur l'enfer.* | active | 48 PM · ⏱ 3 PA | ennemi / magique / portée 6 | 5D10+10 dégâts | portail_infernal · 🔊 foom_0.wav |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌋 **Apocalypse** — *Le ciel s'ouvre et le feu infernal tombe.* | active | 40 PM | ennemi / magique / portée 6 · cercle rayon 2 | 3D10+6 dégâts | meteore · 🔊 foom_0.wav |
| 💀 **Âme damnée** — *Il marque l'âme de la cible pour l'enfer.* | active | 40 PM | ennemi / magique / portée 6 | 3D8+2 dégâts · Vol -16 F -8 R -8 · 5 tours | demon_buff · 🔊 power_up_sound_v3.ogg |

## Druide 🌳

### Niveau 1 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🍃 **Baume de mousse** — *Une mousse fraîche posée sur la plaie.* | active | 10 PM | allie / portée 4 | +16 PV | soin_nature · 🔊 power_up_sound_v2.ogg |
| 🌿 **Lianes** — *Des lianes s'enroulent autour des chevilles.* | active | 10 PM | ennemi / magique / portée 6 | 1D4 dégâts · Ag -6 · 3 tours | nature_buff · 🔊 power_up_sound_v2.ogg |
| 🌳 **Écorce** — *Sa peau se couvre d'une écorce protectrice.* | active | 10 PM | soi / portée 1 | R +8 · 4 tours | nature_buff · 🔊 power_up_sound_v2.ogg |
| 🌵 **Épines** — *Des épines jaillissent du sol sous la cible.* | active | 10 PM | ennemi / magique / portée 6 | 1D8+3 dégâts | griffe · 🔊 animal melee sound.wav |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦌 **Bond du cerf** — *Il bondit avec la grâce du cerf.* | active | 12 PM | soi / portée 1 | saut 2 cases | nature_buff · 🔊 power_up_sound_v2.ogg |
| 🌼 **Pollen soporifique** — *Un nuage de pollen qui alourdit les membres.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · Vol -7 Ag -3 · 3 tours | nature_buff · 🔊 power_up_sound_v2.ogg |
| 🥀 **Ronces** — *Des ronces qui griffent et empoisonnent.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · régén PV -3 · 3 tours | griffe · 🔊 animal melee sound.wav |
| 🌰 **Sève de chêne** — *La sève du vieux chêne coule dans les veines d'un compagnon.* | active | 12 PM | allie / portée 4 | régén PV +2 · 4 tours | soin_nature · 🔊 power_up_sound_v2.ogg |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌲 **Bénédiction des bois** — *Il appelle la force des bois sur un compagnon.* | active | 15 PM | allie / portée 4 | R +10 Vol +5 · 3 tours | nature_buff · 🔊 power_up_sound_v2.ogg |
| 🌾 **Champ de ronces** — *Le sol se couvre de ronces acérées sous les ennemis.* | active | 15 PM | ennemi / magique / portée 6 · cercle rayon 1 | 2D6+3 dégâts | griffe · 🔊 animal melee sound.wav |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🐝 **Nuée d'insectes** — *Un essaim qui pique et harcèle.* | active | 18 PM | ennemi / magique / portée 6 | 1D8 dégâts · régén PV -4 · 3 tours | poison · 🔊 17.mp3 |
| 🪵 **Peau d'écorce** — *Il prend racine, et son corps devient bois.* | active | 9 PM + 3/round | soi / portée 1 | R +15 Vol +7 | nature_buff · 🔊 power_up_sound_v2.ogg |
| 🌱 **Racines dévorantes** — *Les racines boivent la vie de la cible pour la lui rendre.* | active | 18 PM | ennemi / magique / portée 6 | 2D8+5 dégâts · drain 30 % | soin_nature · 🔊 power_up_sound_v2.ogg |
| 💧 **Rosée du matin** — *La rosée d'aube, qui rend force et clarté.* | active | 18 PM | allie / portée 4 | +14 PM | source · 🔊 power_up_sound_v1.ogg |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🍄 **Champignon de mana** — *Des spores qui sapent la magie de la cible.* | active | 21 PM | ennemi / magique / portée 6 | 1D8+2 dégâts · 2D6+1 aux PM | poison · 🔊 17.mp3 |
| 🌿 **Fouet de liane** — *Une liane épaisse qui claque comme un fouet.* | active | 21 PM | ennemi / magique / portée 6 | 3D8+4 dégâts | nature_buff · 🔊 power_up_sound_v2.ogg |
| 🌳 **Régénération sylvestre** — *La forêt soigne ceux qui l'entourent.* | active | 21 PM | allie / portée 4 · cercle rayon 1 | +16 PV | soin_nature · 🔊 power_up_sound_v2.ogg |
| 🍄 **Spores étouffantes** — *Un nuage de spores qui s'abat sur les ennemis.* | active | 21 PM | ennemi / magique / portée 6 · cercle rayon 2 | 2D6+5 dégâts | poison · 🔊 17.mp3 |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ♻️ **Cercle de vie** — *Un cercle verdoyant qui fortifie ses alliés.* | active | 25 PM | soi / portée 1 · carre rayon 1 | R +10 Vol +5 · 4 tours | soin_nature · 🔊 power_up_sound_v2.ogg |
| 🌲 **Colère de la forêt** — *Des branches fouettent le premier rang ennemi.* | active | 25 PM | ennemi / magique / portée 6 · rectangle longueur 1 largeur 3 | 3D6+6 dégâts | griffe · 🔊 animal melee sound.wav |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌱 **Passage des racines** — *Il entre dans le sol et ressort plus loin.* | active | 29 PM | soi / portée 1 | saut 4 cases | nature_buff · 🔊 power_up_sound_v2.ogg |
| 🪵 **Pieu de bois vivant** — *Une souche jaillit du sol comme une lance.* | active | 29 PM | ennemi / magique / portée 6 | 3D10+7 dégâts | roc · 🔊 melee sound.wav |
| 🐍 **Venin de la vipère verte** — *Un venin qui trouble l'esprit.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · régén PM -4 · 4 tours | poison · 🔊 17.mp3 |
| 🌳 **Étreinte du saule** — *Les branches enserrent l'ennemi et le paralysent.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · Ag -13 F -6 · 4 tours | nature_buff · 🔊 power_up_sound_v2.ogg |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌵 **Bouclier d'épines** — *Une armure d'épines qui fait payer chaque coup.* | active | 15 PM + 5/round | soi / portée 1 | R +20 F +10 | griffe · 🔊 animal melee sound.wav |
| 🌸 **Floraison** — *Une fleur s'ouvre sur la plaie et la referme.* | active | 33 PM | allie / portée 4 | +38 PV | soin_nature · 🔊 power_up_sound_v2.ogg |
| 🍁 **Malédiction des saisons** — *L'automne entre dans les os de la cible.* | active | 33 PM | ennemi / magique / portée 6 | 2D8+2 dégâts · F -14 R -7 · 4 tours | nature_buff · 🔊 power_up_sound_v2.ogg |
| 🍂 **Tempête de feuilles** — *Des feuilles tranchantes comme des lames.* | active | 33 PM | ennemi / magique / portée 6 · cone longueur 2 | 3D8+8 dégâts | impact_plaie + nappe cone_griffe · 🔊 animal melee sound.wav |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌳 **Courroux du chêne** — *Le vieux chêne frappe de toute sa masse.* | active | 37 PM | ennemi / magique / portée 6 | 4D10+9 dégâts | roc · 🔊 melee sound.wav |
| 🐸 **Marais** — *Le sol devient un marais qui engloutit les ennemis.* | active | 37 PM | ennemi / magique / portée 6 · cercle rayon 2 | 3D8+6 dégâts | eau · 🔊 swish_3.wav |
| 🌧️ **Pluie de vie** — *Une pluie qui ranime et fortifie.* | active | 37 PM | allie / portée 4 | régén PV +5 · 6 tours | source · 🔊 power_up_sound_v1.ogg |
| ♻️ **Rituel du cycle** — *Un rituel lent qui retourne la cible à la terre.* | active | 48 PM · ⏱ 3 PA | ennemi / magique / portée 6 | 5D10+10 dégâts | nature_buff · 🔊 power_up_sound_v2.ogg |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌍 **Fureur de Gaïa** — *La terre elle-même se soulève contre l'ennemi.* | active | 40 PM | ennemi / magique / portée 6 · carre rayon 2 | 3D8+7 dégâts | roc · 🔊 melee sound.wav |
| 🌱 **Renouveau** — *Le printemps éclate au milieu du combat.* | active | 40 PM | allie / portée 4 · cercle rayon 1 | +27 PV | soin_vague · 🔊 power_up_sound_v1.ogg |

## Duelliste 🤺

### Niveau 1 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🤌 **Poignet souple** — *La lame tourne dans sa main comme une plume.* | passive | — | permanent | Ag +2 | — |
| 🎩 **Élégance** — *Même dans la boue, il garde l'allure d'un salon.* | passive | — | permanent | Cha +2 | — |
| 🤺 **Battement** — *Un coup sec sur la lame adverse, qui ouvre la garde.* | active | 10 PM | ennemi / cc / portée 1 | 1D4 dégâts · Ag -6 · 3 tours | lame · 🔊 sword sound.wav |
| 🗡️ **Coup droit** — *La première leçon de toute salle d'armes, exécutée à la perfection.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | lame · 🔊 sword sound.wav |
| ⚜️ **En garde** — *Il prend la garde, et l'on comprend qu'il ne sera pas facile à toucher.* | active | 10 PM | soi / portée 1 | Ag +4 · esquive 6 · 3 tours | garde · 🔊 sword sound.wav |
| 🦶 **Marche-fente** — *Un pas glissé, puis la détente : il est déjà au contact.* | active | 10 PM | soi / portée 1 | saut 2 cases | saut · 🔊 swish_4.wav |
| ↩️ **Riposte** — *Il pare et rend la politesse dans le même mouvement.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | lame · 🔊 sword sound.wav |

### Niveau 2 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 👑 **Port de tête** — *Son assurance déroute ceux qui le croisent.* | passive | — | permanent | Vol +2 | — |
| 👁️ **Œil de l'escrimeur** — *Il lit l'épaule avant que la lame ne parte.* | passive | — | permanent | esquive 3 | — |
| ✂️ **Coup de manchette** — *La lame effleure le poignet, et l'arme pèse soudain plus lourd.* | active | 12 PM | ennemi / cc / portée 1 | 1D6 dégâts · F -7 · 3 tours | saignee · 🔊 sword sound.wav |
| 🧤 **Défi d'honneur** — *Il jette le gant, et son sang s'échauffe.* | active | 12 PM | soi / portée 1 | Ag +9 Cha +4 · 4 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| 🩸 **Estafilade** — *Une entaille fine, qui saigne plus qu'on ne le croit.* | active | 12 PM | ennemi / cc / portée 1 | 1D6 dégâts · régén PV -3 · 3 tours | saignee · 🔊 sword sound.wav |
| ➡️ **Flèche** — *Une course en extension, la pointe en avant.* | active | 12 PM | soi / portée 1 | saut 2 cases | saut · 🔊 swish_4.wav |
| ⚔️ **Taille en tierce** — *Un coup haut, porté avec la grâce d'une révérence.* | active | 12 PM | ennemi / cc / portée 1 | 2D6+3 dégâts | lame · 🔊 sword sound.wav |

### Niveau 3 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦢 **Grâce naturelle** — *Chacun de ses gestes semble avoir été répété mille fois.* | passive | — | permanent | Ag +3 | — |
| 💃 **Danse des lames** — *Un enchaînement léger qui touche trois adversaires.* | active | 15 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 2D6+3 dégâts | balayage · 🔊 swish_3.wav |
| ⚔️ **Double attaque** — *Deux coups si proches qu'on n'en voit qu'un.* | active | 15 PM | ennemi / cc / portée 1 | 2D8+3 dégâts | lame · 🔊 sword sound.wav |
| 🫳 **Désarmement** — *D'une torsion du poignet, l'arme adverse lui échappe presque.* | active | 15 PM | ennemi / cc / portée 1 | 1D6+1 dégâts · F -8 Ag -4 · 3 tours | garde · 🔊 sword sound.wav |
| 🧵 **Garde de soie** — *Une garde si souple qu'elle ne laisse aucune prise.* | active | 8 PM + 3/round | soi / portée 1 | Ag +13 | garde · 🔊 sword sound.wav |

### Niveau 4 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🎯 **Coup d'œil** — *Il voit l'ouverture avant qu'elle n'existe.* | passive | — | permanent | Int +3 | — |
| 🩰 **Jambes de danseur** — *Il ne se trouve jamais là où tombe le coup.* | passive | — | permanent | esquive 4 | — |
| 😏 **Bravade** — *Un sourire insolent : il se sait meilleur.* | active | 18 PM | soi / portée 1 | Cha +12 Ag +6 · 4 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| 🦵 **Coup de Jarnac** — *Un coup bas, légal mais déloyal, au défaut du genou.* | active | 18 PM | ennemi / cc / portée 1 | 1D8 dégâts · Ag -9 · 3 tours | saignee · 🔊 sword sound.wav |
| 🗡️ **Fente basse** — *Il plonge sous la garde et pique au flanc.* | active | 18 PM | ennemi / cc / portée 1 | 2D8+5 dégâts | lame · 🔊 sword sound.wav |
| ↗️ **Saut de côté** — *Il s'efface d'un bond et réapparaît dans le dos de l'adversaire.* | active | 18 PM | soi / portée 1 | saut 3 cases | saut · 🔊 swish_4.wav |
| 🌀 **Volte** — *Une pirouette et sa lame fait le tour de ses adversaires.* | active | 18 PM | ennemi / cc / portée 1 · carre rayon 1 | 2D6+3 dégâts | balayage · 🔊 swish_3.wav |

### Niveau 5 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ✋ **Main du prévôt** — *La main de celui qui enseigne : jamais crispée, jamais lâche.* | passive | — | permanent | Ag +3 | — |
| 🎭 **Prestance** — *Il se bat comme on joue sur scène, et le public le sent.* | passive | — | permanent | Cha +3 | — |
| 📍 **Coup de pointe** — *La pointe trouve le cœur de la cible comme une aiguille son chas.* | active | 21 PM | ennemi / cc / portée 1 | 3D8+4 dégâts | lame · 🔊 sword sound.wav |
| 🔗 **Liement** — *Il enroule sa lame autour de l'autre et l'emporte.* | active | 21 PM | ennemi / cc / portée 1 | 1D8+2 dégâts · Ag -10 F -5 · 4 tours | garde · 🔊 sword sound.wav |
| ⚔️ **Moulinet du bretteur** — *Un moulinet de poignet, rapide et tranchant.* | active | 21 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 2D8+5 dégâts | balayage · 🔊 swish_3.wav |
| 🩸 **Saignées multiples** — *Dix petites coupures, et aucune ne se ferme.* | active | 21 PM | ennemi / cc / portée 1 | 1D8+2 dégâts · régén PV -5 · 4 tours | saignee · 🔊 sword sound.wav |
| 🤺 **Salut du maître** — *Il salue un compagnon, et celui-ci se tient soudain mieux.* | active | 21 PM | allie / portée 4 | Ag +13 Vol +6 · 4 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |

### Niveau 6 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🐈 **Réflexes de chat** — *Il esquive comme un chat retombe sur ses pattes.* | passive | — | permanent | esquive 5 | — |
| 🏅 **Coup de maître** — *Un coup qu'on ne voit qu'une fois par vie.* | active | 25 PM | ennemi / cc / portée 1 | 3D8+6 dégâts | lame · 🔊 sword sound.wav |
| 🎭 **Feinte double** — *Il menace à gauche, puis à droite, et l'adversaire ne sait plus où se garder.* | active | 25 PM | ennemi / cc / portée 1 | 2D6+2 dégâts · Int -12 Ag -6 · 4 tours | double · 🔊 swish_2.wav |
| 👣 **Pas de l'ombre** — *Il glisse d'une ombre à l'autre.* | active | 25 PM | soi / portée 1 | saut 4 cases | furtif · 🔊 swish_2.wav |
| 🪭 **Éventail d'acier** — *La lame se déploie en éventail devant lui.* | active | 25 PM | ennemi / cc / portée 1 · cone longueur 2 | 3D6+6 dégâts | impact_eclat_dore + nappe cone_tueur_demon · 🔊 sword sound.wav |

### Niveau 7 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🗡️ **Lame vivante** — *L'épée n'est plus un outil : elle est le prolongement de son bras.* | passive | — | permanent | Ag +4 | — |
| 🪶 **Panache** — *Il ne recule jamais sans un mot d'esprit.* | passive | — | permanent | Vol +4 | — |
| 💫 **Assaut de grâce** — *Une série parfaite, enchaînée sans un faux pas.* | active | 29 PM | soi / portée 1 | Ag +16 F +8 · 5 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| 🤫 **Botte secrète** — *Un coup transmis de maître à élève, jamais écrit.* | active | 29 PM | ennemi / cc / portée 1 | 3D10+7 dégâts | saignee · 🔊 sword sound.wav |
| 🦶 **Coup de pied de salle** — *Un coup de botte, que les règles tolèrent à peine.* | active | 29 PM | ennemi / cc / portée 1 | 3D10+7 dégâts | poing · 🔊 melee sound.wav |
| 🦋 **Coup du papillon** — *Une volte légère, et partout autour la lame a mordu.* | active | 29 PM | ennemi / cc / portée 1 · carre rayon 1 | 2D8+6 dégâts | balayage · 🔊 swish_3.wav |
| 🔗 **Prise de fer** — *Sa lame cloue celle de l'autre et la paralyse.* | active | 29 PM | ennemi / cc / portée 1 | 2D6+4 dégâts · F -13 Ag -6 · 4 tours | garde · 🔊 sword sound.wav |

### Niveau 8 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⚖️ **Instinct du duel** — *Face à un seul adversaire, il est presque intouchable.* | passive | — | permanent | esquive 6 | — |
| 🦅 **Œil de faucon** — *Pas un mouvement adverse ne lui échappe.* | passive | — | permanent | Int +4 | — |
| 📖 **Inspiration du maître d'armes** — *Un conseil glissé à l'oreille d'un compagnon, qui change tout.* | active | 33 PM | allie / portée 4 | Ag +17 F +8 · 4 tours | chant · 🔊 power_up_sound_v1.ogg |
| 🌬️ **Pas du vent** — *Il franchit la distance comme une bourrasque.* | active | 33 PM | soi / portée 1 | saut 4 cases | vent · 🔊 swish_4.wav |
| ❤️ **Pointe au cœur** — *La pointe entre entre deux côtes.* | active | 33 PM | ennemi / cc / portée 1 | 4D10+6 dégâts | lame · 🔊 sword sound.wav |
| 🩸 **Saignée d'artère** — *Une coupure précise, là où le sang court le plus vite.* | active | 33 PM | ennemi / cc / portée 1 | 2D8+2 dégâts · régén PV -6 · 4 tours | saignee · 🔊 sword sound.wav |
| 🌀 **Tourbillon du bretteur** — *Une danse circulaire où chaque pas porte un coup.* | active | 33 PM | ennemi / cc / portée 1 · carre rayon 2 | 2D8+6 dégâts | balayage · 🔊 swish_3.wav |

### Niveau 9 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🏆 **Aura de champion** — *On sait, en le voyant entrer, qui gagnera le duel.* | passive | — | permanent | Cha +5 | — |
| ✨ **Perfection du geste** — *Pas un muscle ne se contracte en vain.* | passive | — | permanent | Ag +5 | — |
| 👑 **Coup du roi** — *Le coup réservé aux adversaires dignes de lui.* | active | 37 PM | ennemi / cc / portée 1 | 4D10+9 dégâts | lame · 🔊 sword sound.wav |
| 🛡️ **Garde absolue** — *Aucune lame ne passe : il les détourne toutes.* | active | 16 PM + 5/round | soi / portée 1 | Ag +21 R +10 | garde · 🔊 sword sound.wav |
| 🫳 **Main paralysée** — *Une entaille aux tendons : la main ne serre plus.* | active | 37 PM | ennemi / cc / portée 1 | 2D8+4 dégâts · F -15 Ag -7 · 5 tours | saignee · 🔊 sword sound.wav |
| 🩸 **Sang du duel** — *Chaque touche lui rend de la vigueur.* | active | 37 PM | ennemi / cc / portée 1 | 4D10+9 dégâts · drain 40 % (max 20) | saignee · 🔊 sword sound.wav |
| 🌪️ **Vent de lames** — *Une série de coups si rapide qu'elle semble faire du vent.* | active | 37 PM | ennemi / cc / portée 1 · cone longueur 2 | 3D10+8 dégâts | impact_eclat_dore + nappe cone_tueur_demon · 🔊 sword sound.wav |

### Niveau 10 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 📜 **Légende de l'escrime** — *Les traités d'escrime citeront son nom.* | passive | — | permanent | esquive 8 | — |
| 💃 **Ballet mortel** — *Une danse dont aucun partenaire ne se relève.* | active | 40 PM | ennemi / cc / portée 1 · carre rayon 2 | 3D8+7 dégâts | balayage · 🔊 swish_3.wav |
| 💎 **Coup parfait** — *Le coup que tout bretteur cherche, et que lui seul a trouvé.* | active | 40 PM | ennemi / cc / portée 1 | 5D10+12 dégâts | lame · 🔊 sword sound.wav |
| 🦅 **Envol du bretteur** — *Il bondit par-dessus la mêlée et retombe la pointe en avant.* | active | 40 PM | soi / portée 1 | saut 5 cases | saut · 🔊 swish_4.wav |
| ♟️ **Maître du terrain** — *Il dirige le combat comme une leçon, et chacun y trouve sa place.* | active | 40 PM | soi / portée 1 · carre rayon 2 | Ag +14 Vol +7 · 5 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |

## Élémentaliste 🔥

### Niveau 1 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌬️ **Brise** — *Le vent le soulève et le dépose plus loin.* | active | 10 PM | soi / portée 1 | saut 2 cases | vent · 🔊 swish_4.wav |
| 🥶 **Gel des membres** — *Le froid saisit les articulations de l'ennemi.* | active | 10 PM | ennemi / magique / portée 6 | 1D4 dégâts · Ag -6 · 3 tours | givre · 🔊 17.mp3 |
| 🪨 **Peau de granit** — *Sa peau prend le grain du granit.* | active | 10 PM | soi / portée 1 | R +8 · 4 tours | roc · 🔊 melee sound.wav |
| ✨ **Étincelle** — *Une étincelle claque au bout des doigts et mord la cible.* | active | 10 PM | ennemi / magique / portée 6 | 1D8+3 dégâts | feu · 🔊 foom_0.wav |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⚡ **Arc électrique** — *Un arc qui court sur la cible et grille ses réserves.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · 1D6+1 aux PM | foudre · 🔊 17.mp3 |
| 🔥 **Brûlure** — *Une flamme qui s'accroche et ne s'éteint pas.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · régén PV -3 · 3 tours | feu · 🔊 foom_0.wav |
| 🌧️ **Pluie douce** — *Une ondée qui lave et apaise les plaies d'un compagnon.* | active | 12 PM | allie / portée 4 | régén PV +2 · 4 tours | source · 🔊 power_up_sound_v1.ogg |
| 🧊 **Trait de glace** — *Une aiguille de glace qui file droit au but.* | active | 12 PM | ennemi / magique / portée 6 | 2D6+3 dégâts | givre · 🔊 17.mp3 |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌪️ **Bourrasque** — *Une rafale qui fait chanceler les plus solides.* | active | 15 PM | ennemi / magique / portée 6 | 1D6+1 dégâts · Ag -8 F -4 · 3 tours | vent · 🔊 swish_4.wav |
| 🔥 **Gerbe de flammes** — *Le feu éclate au milieu des ennemis.* | active | 15 PM | ennemi / magique / portée 6 · cercle rayon 1 | 2D6+3 dégâts | explosion_feu · 🔊 foom_0.wav |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🧊 **Armure de glace** — *Une carapace de glace se forme et se reforme autour de lui.* | active | 9 PM + 3/round | soi / portée 1 | R +15 | givre · 🔊 17.mp3 |
| ❄️ **Givre rampant** — *Le gel gagne la chair, lentement, inexorablement.* | active | 18 PM | ennemi / magique / portée 6 | 1D8 dégâts · régén PV -4 · 3 tours | givre · 🔊 17.mp3 |
| ⚡ **Lance de foudre** — *La foudre se fait lance et transperce.* | active | 18 PM | ennemi / magique / portée 6 | 2D8+5 dégâts | foudre · 🔊 17.mp3 |
| 🌊 **Torrent** — *Un jet d'eau furieux qui balaie le premier rang.* | active | 18 PM | ennemi / magique / portée 6 · rectangle longueur 1 largeur 3 | 2D6+5 dégâts | eau · 🔊 swish_3.wav |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🔥 **Langue de feu** — *Les flammes jaillissent de ses mains en éventail.* | active | 21 PM | ennemi / magique / portée 6 · cone longueur 3 | 2D6+5 dégâts | impact_brulure + nappe cone_souffle_feu · 🔊 foom_0.wav |
| 🪨 **Projection de roc** — *Un bloc arraché au sol vole vers la cible.* | active | 21 PM | ennemi / magique / portée 6 | 3D8+4 dégâts | roc · 🔊 melee sound.wav |
| 🌀 **Souffle des éléments** — *Il prête à un compagnon la force des éléments.* | active | 21 PM | allie / portée 4 | R +13 F +6 · 4 tours | nature_buff · 🔊 power_up_sound_v2.ogg |
| 🌩️ **Écho du tonnerre** — *Un coup de tonnerre qui laisse l'ennemi sourd et hébété.* | active | 21 PM | ennemi / magique / portée 6 | 1D8+2 dégâts · Int -10 Ag -5 · 4 tours | foudre · 🔊 17.mp3 |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ♨️ **Forme de vapeur** — *Son corps se fait brume, et les coups le traversent.* | active | 25 PM | soi / portée 1 | Int +7 · esquive 11 · 4 tours | eau · 🔊 swish_3.wav |
| 🌨️ **Tempête de grêle** — *La grêle s'abat sur une large zone.* | active | 25 PM | ennemi / magique / portée 6 · cercle rayon 2 | 2D8+4 dégâts | givre · 🔊 17.mp3 |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🔥 **Colonne de feu** — *Une colonne de flammes jaillit sous les pieds de la cible.* | active | 29 PM | ennemi / magique / portée 6 | 3D10+7 dégâts | meteore · 🔊 foom_0.wav |
| 🏜️ **Sables mouvants** — *Le sol se dérobe sous l'ennemi.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · Ag -13 · 4 tours | roc · 🔊 melee sound.wav |
| 💧 **Source de mana** — *Il fait jaillir pour un compagnon une source d'énergie pure.* | active | 29 PM | allie / portée 4 | +20 PM | source · 🔊 power_up_sound_v1.ogg |
| ⚡ **Éclair en chaîne** — *La foudre bondit de cible en cible devant lui.* | active | 29 PM | ennemi / magique / portée 6 · cone longueur 3 | 2D8+6 dégâts | impact_etincelles + nappe cone_decharge · 🔊 17.mp3 |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🧊 **Javelot de glace** — *Un javelot de glace pure, lourd comme la mort.* | active | 33 PM | ennemi / magique / portée 6 | 4D10+6 dégâts | givre · 🔊 17.mp3 |
| ⛈️ **Rituel de la tempête** — *Il invoque l'orage, et l'orage met du temps à venir.* | active | 43 PM · ⏱ 3 PA | ennemi / magique / portée 6 | 4D10+10 dégâts | foudre · 🔊 17.mp3 |
| 🌀 **Siphon des éléments** — *Il aspire la vie de la cible avec le vent.* | active | 33 PM | ennemi / magique / portée 6 | 4D10+6 dégâts · drain 35 % (max 20) | vent · 🔊 swish_4.wav |
| 🌋 **Tremblement** — *La terre tremble autour de lui et renverse les ennemis.* | active | 33 PM | ennemi / magique / portée 6 · carre rayon 2 | 2D8+6 dégâts | roc · 🔊 melee sound.wav |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🛡️ **Bouclier des quatre vents** — *Les vents tournent autour du groupe et détournent les coups.* | active | 37 PM | soi / portée 1 · carre rayon 2 | R +13 Ag +6 · 5 tours | bouclier · 🔊 power_up_sound_v2.ogg |
| 🔥 **Brasier** — *Un feu qui dévore longtemps.* | active | 37 PM | ennemi / magique / portée 6 | 2D8+4 dégâts · régén PV -7 · 5 tours | feu · 🔊 foom_0.wav |
| 🌪️ **Cyclone** — *Le vent l'emporte et le dépose où il veut.* | active | 37 PM | soi / portée 1 | saut 5 cases | vent · 🔊 swish_4.wav |
| 🌊 **Raz-de-marée** — *Une vague qui emporte le premier rang ennemi.* | active | 37 PM | ennemi / magique / portée 6 · rectangle longueur 1 largeur 3 | 3D10+8 dégâts | eau · 🔊 swish_3.wav |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💥 **Fureur élémentaire** — *Feu, glace, foudre et roc frappent ensemble la même cible.* | active | 52 PM · ⏱ 3 PA | ennemi / magique / portée 6 | 6D10+12 dégâts | explosion_feu · 🔊 foom_0.wav |
| ❄️ **Zéro absolu** — *Le froid absolu fige la cible dans la glace.* | active | 40 PM | ennemi / magique / portée 6 | 3D8+2 dégâts · Ag -16 F -8 · 5 tours | givre · 🔊 17.mp3 |

## Forestier 🏹

### Niveau 1 — 3 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🐇 **Bond du lièvre** — *Il s'éloigne d'un bond pour retrouver la bonne distance.* | active | 10 PM | soi / portée 1 | saut 2 cases | saut · 🔊 swish_4.wav |
| 🔪 **Coup de couteau** — *Le couteau de chasse, quand la bête est trop près pour l'arc.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | saignee · 🔊 sword sound.wav |
| 🏹 **Flèche rapide** — *Encoche, vise, lâche : un seul souffle.* | active | 10 PM | ennemi / cd / portée 8 | 1D8+3 dégâts | tir · 🔊 Bow.wav |
| 🦵 **Tir aux jambes** — *Une flèche basse qui ralentit la course de la proie.* | active | 10 PM | ennemi / cd / portée 8 | 1D4 dégâts · Ag -6 · 3 tours | tir · 🔊 Bow.wav |

### Niveau 2 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🍂 **Pas de velours** — *Il marche sur les feuilles mortes sans en froisser une.* | passive | — | permanent | furtivité 5 (foret, bois, clariere, couvert, chemin) | — |
| 🏹 **Double flèche** — *Deux flèches encochées ensemble, deux plaies.* | active | 12 PM | ennemi / cd / portée 8 | 2D6+3 dégâts | tir · 🔊 Bow.wav |
| 🩸 **Flèche barbelée** — *La pointe accroche les chairs, et la plaie saigne.* | active | 12 PM | ennemi / cd / portée 8 | 1D6 dégâts · régén PV -3 · 3 tours | tir · 🔊 Bow.wav |
| 🌿 **Herbes de guérison** — *Une poignée de plantes mâchées, appliquée sur la plaie.* | active | 12 PM | allie / portée 4 | +18 PV | soin_nature · 🔊 power_up_sound_v2.ogg |
| 🧘 **Patience du chasseur** — *Il retient son souffle ; le monde ralentit autour de sa cible.* | active | 12 PM | soi / portée 1 | Ag +9 · 4 tours | nature_buff · 🔊 power_up_sound_v2.ogg |
| 🌧️ **Volée** — *Une pluie de flèches sur une petite clairière.* | active | 12 PM | ennemi / cd / portée 8 · cercle rayon 1 | 1D8+3 dégâts | tir · 🔊 Bow.wav |

### Niveau 3 — 3 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦅 **Cri du faucon** — *Un sifflement aigu qui affole la proie.* | active | 15 PM | ennemi / cd / portée 8 | 1D6+1 dégâts · Vol -8 Ag -4 · 3 tours | vent · 🔊 swish_4.wav |
| 🎯 **Flèche perforante** — *Une pointe lourde qui traverse le cuir et l'os.* | active | 15 PM | ennemi / cd / portée 8 | 2D8+3 dégâts | tir · 🔊 Bow.wav |
| 🎯 **Marque du gibier** — *Il repère le point faible de la bête et l'épuise.* | active | 15 PM | ennemi / cd / portée 8 | 1D6+1 dégâts · 1D8+1 aux PM | marque · 🔊 17.mp3 |
| 🍃 **Pas de côté du rôdeur** — *Il se fond dans un fourré, et la riposte frappe le vide.* | active | 15 PM | soi / portée 1 | Ag +5 · esquive 8 · 3 tours | furtif · 🔊 swish_2.wav |

### Niveau 4 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 👁️ **Œil perçant** — *Il distingue un écureuil à cent pas dans le feuillage.* | passive | — | permanent | Ag +3 | — |
| 🏹 **Flèche de chasse** — *Une flèche à large fer, qui handicape plus qu'elle ne tue.* | active | 18 PM | ennemi / cd / portée 8 | 1D8 dégâts · Ag -9 F -4 · 3 tours | tir · 🔊 Bow.wav |
| 🔪 **Lame et pointe** — *Couteau dans une main, flèche dans l'autre : il taille large.* | active | 18 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 2D6+5 dégâts | balayage · 🔊 swish_3.wav |
| 🌱 **Remède du bois** — *Un baume d'écorce qui referme lentement les plaies.* | active | 18 PM | allie / portée 4 | régén PV +3 · 4 tours | soin_nature · 🔊 power_up_sound_v2.ogg |
| 🌳 **Saut de branche** — *Il grimpe et retombe plus loin, hors d'atteinte.* | active | 18 PM | soi / portée 1 | saut 3 cases | saut · 🔊 swish_4.wav |
| 👁️ **Tir à l'œil** — *Une flèche qui cherche le seul point que l'armure ne couvre pas.* | active | 18 PM | ennemi / cd / portée 8 | 2D8+5 dégâts | tir · 🔊 Bow.wav |

### Niveau 5 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🥾 **Endurance du pisteur** — *Des jours sur la piste, sans repos, et toujours debout.* | passive | — | permanent | régén PV +1 | — |
| 🌲 **Affût** — *Il se poste et ne bouge plus : chaque tir sera mortel.* | active | 10 PM + 3/round | soi / portée 1 | Ag +16 Ch +8 | nature_buff · 🔊 power_up_sound_v2.ogg |
| 🐺 **Appel du loup** — *Un hurlement qui rend la meute — et ses compagnons — plus mordants.* | active | 21 PM | soi / portée 1 · carre rayon 1 | Ag +9 F +4 · 4 tours | appel_sauvage · 🔊 animal melee sound.wav |
| 🏹 **Flèche longue** — *Un tir à la limite de la portée, qui touche quand même.* | active | 21 PM | ennemi / cd / portée 10 | 3D8+4 dégâts | tir · 🔊 Bow.wav |
| 🐍 **Flèche venimeuse** — *La pointe trempée dans la sève des marais.* | active | 21 PM | ennemi / cd / portée 8 | 1D8+2 dégâts · régén PV -5 · 4 tours | poison · 🔊 17.mp3 |
| 🌧️ **Pluie de flèches** — *Le ciel s'assombrit au-dessus des ennemis.* | active | 21 PM | ennemi / cd / portée 8 · cercle rayon 2 | 2D6+5 dégâts | tir · 🔊 Bow.wav |

### Niveau 6 — 3 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 📌 **Clouer au sol** — *La flèche traverse le pied et s'enfonce dans la terre.* | active | 25 PM | ennemi / cd / portée 8 | 2D6+2 dégâts · Ag -12 · 4 tours | tir · 🔊 Bow.wav |
| 🏹 **Flèche du pistard** — *Il tire là où la bête sera, pas là où elle est.* | active | 25 PM | ennemi / cd / portée 8 | 3D8+6 dégâts | tir · 🔊 Bow.wav |
| 😮‍💨 **Flèche épuisante** — *Une pointe qui vide la bête de ses forces.* | active | 25 PM | ennemi / cd / portée 8 | 2D6+2 dégâts · 2D6+2 aux PM | tir · 🔊 Bow.wav |
| 🍃 **Ombre des feuilles** — *Il disparaît dans le feuillage le temps d'un souffle.* | active | 25 PM | soi / portée 1 | Ag +7 · esquive 11 · 4 tours | furtif · 🔊 swish_2.wav |

### Niveau 7 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦌 **Peau de chasseur** — *Les ronces, le froid, la pluie : il les ignore.* | passive | — | permanent | R +4 | — |
| 🐆 **Bond de la panthère** — *Un saut silencieux vers la position idéale.* | active | 29 PM | soi / portée 1 | saut 4 cases | saut · 🔊 swish_4.wav |
| 🌿 **Pharmacopée sylvestre** — *Il sait quelle herbe pousse au pied de quel arbre.* | active | 29 PM | allie / portée 4 | +34 PV | soin_nature · 🔊 power_up_sound_v2.ogg |
| 🩸 **Saignée de cerf** — *Il vise l'artère comme on achève un grand cerf.* | active | 29 PM | ennemi / cd / portée 8 | 2D6+4 dégâts · régén PV -6 · 4 tours | saignee · 🔊 sword sound.wav |
| 💀 **Tir mortel** — *Une flèche qu'on n'entend qu'une fois.* | active | 29 PM | ennemi / cd / portée 8 | 3D10+7 dégâts | tir · 🔊 Bow.wav |
| 🪭 **Volée en éventail** — *Trois flèches à la fois, ouvertes en éventail.* | active | 29 PM | ennemi / cd / portée 8 · cone longueur 3 | 2D8+6 dégâts | impact_etincelles + nappe cone_decharge · 🔊 17.mp3 |

### Niveau 8 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 👻 **Fantôme des bois** — *Même les oiseaux ne le remarquent pas.* | passive | — | permanent | furtivité 11 (foret, bois, clariere, couvert, chemin) | — |
| 🔪 **Couteau du dépeceur** — *Le geste sûr de celui qui a dépecé mille bêtes.* | active | 33 PM | ennemi / cc / portée 1 | 4D10+6 dégâts · drain 35 % (max 20) | saignee · 🔊 sword sound.wav |
| 🌳 **Esprit de la forêt** — *Il murmure aux arbres, et un compagnon en reçoit la force.* | active | 33 PM | allie / portée 4 | R +17 Ag +8 · 4 tours | nature_buff · 🔊 power_up_sound_v2.ogg |
| 😵 **Flèche aveuglante** — *Une pointe enduite de résine qui brûle les yeux.* | active | 33 PM | ennemi / cd / portée 8 | 2D8+2 dégâts · Ag -14 Int -7 · 4 tours | eblouissant · 🔊 17.mp3 |
| 🌧️ **Grêle de flèches** — *Un orage de traits sur une large zone.* | active | 33 PM | ennemi / cd / portée 8 · cercle rayon 2 | 3D8+4 dégâts | tir · 🔊 Bow.wav |
| 🎯 **Tir transperçant** — *La flèche traverse le premier et cherche le second.* | active | 33 PM | ennemi / cd / portée 8 | 4D10+6 dégâts | tir · 🔊 Bow.wav |

### Niveau 9 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🏹 **Maîtrise de l'arc** — *L'arc est devenu une partie de son corps.* | passive | — | permanent | Ag +5 | — |
| 👃 **Sens aiguisés** — *Il sent l'embuscade avant de la voir.* | passive | — | permanent | esquive 7 | — |
| 🦌 **Bond de l'élan** — *Un saut puissant qui l'emporte loin de la mêlée.* | active | 37 PM | soi / portée 1 | saut 5 cases | saut · 🔊 swish_4.wav |
| 👑 **Flèche du roi des bois** — *La flèche que l'on garde pour le monstre de la forêt.* | active | 37 PM | ennemi / cd / portée 8 | 4D10+9 dégâts | tir · 🔊 Bow.wav |
| 🌧️ **Tir de suppression** — *Un barrage de flèches qui force l'ennemi à se terrer.* | active | 37 PM | ennemi / cd / portée 8 · cone longueur 3 | 3D8+6 dégâts | impact_etincelles + nappe cone_decharge · 🔊 17.mp3 |
| 🐸 **Venin du marais** — *Un poison noir qui ronge jusqu'à l'os.* | active | 37 PM | ennemi / cd / portée 8 | 2D8+4 dégâts · régén PV -7 · 5 tours | poison · 🔊 17.mp3 |
| 👁️ **Vigilance du guetteur** — *Il garde l'œil sur tout le champ de bataille.* | active | 16 PM + 5/round | soi / portée 1 | Ag +21 Int +10 | nature_buff · 🔊 power_up_sound_v2.ogg |

### Niveau 10 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦌 **Seigneur des bois** — *La forêt le reconnaît comme l'un des siens.* | passive | — | permanent | Ag +5 | — |
| 📯 **Appel de la grande chasse** — *Le cor sonne, et tout le groupe se met en chasse.* | active | 40 PM | soi / portée 1 · carre rayon 2 | Ag +14 F +7 · 5 tours | appel_sauvage · 🔊 animal melee sound.wav |
| 🌧️ **Ciel de flèches** — *Il assombrit le ciel, et la pluie qui tombe est d'acier.* | active | 40 PM | ennemi / cd / portée 8 · cercle rayon 2 | 3D10+6 dégâts | tir · 🔊 Bow.wav |
| 🌠 **Flèche de légende** — *La flèche dont parlent les chansons de chasse.* | active | 40 PM | ennemi / cd / portée 8 | 5D10+12 dégâts | tir · 🔊 Bow.wav |
| 😮‍💨 **Proie épuisée** — *Il traque sa cible jusqu'à ce qu'elle n'ait plus rien.* | active | 40 PM | ennemi / cd / portée 8 | 3D8+2 dégâts · 3D8 aux PM | marque · 🔊 17.mp3 |

## Guerrier ⚔️

### Niveau 1 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🛡️ **Peau tannée** — *Les bleus d'hier sont la cuirasse de demain.* | passive | — | permanent | R +2 | — |
| ✊ **Poigne d'acier** — *Des années à serrer la garde : la main ne lâche plus rien.* | passive | — | permanent | F +2 | — |
| 💢 **Bousculade** — *Un coup d'épaule qui déséquilibre et laisse l'ennemi chancelant.* | active | 10 PM | ennemi / cc / portée 1 | 1D4 dégâts · Ag -6 · 3 tours | coup_lourd · 🔊 melee sound.wav |
| 🗡️ **Coup d'estoc** — *Une pointe sèche, portée au défaut de la garde adverse.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | lame · 🔊 sword sound.wav |
| 🛡️ **Garde haute** — *Le bouclier remonte, l'épée se replie : il n'offre plus que du fer.* | active | 10 PM | soi / portée 1 | R +4 · esquive 6 · 3 tours | garde · 🔊 sword sound.wav |

### Niveau 2 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦶 **Pas assuré** — *Chaque appui est choisi : on ne le prend jamais à contre-pied.* | passive | — | permanent | esquive 3 | — |
| 🌬️ **Souffle long** — *Il a appris à respirer sous le heaume sans jamais manquer d'air.* | passive | — | permanent | Vol +2 | — |
| 🐂 **Charge courte** — *Trois pas d'élan et il est déjà sur la ligne adverse.* | active | 12 PM | soi / portée 1 | saut 2 cases | saut · 🔊 swish_4.wav |
| ⚔️ **Coup de taille** — *Un geste ample, de toute la longueur de la lame.* | active | 12 PM | ennemi / cc / portée 1 | 2D6+3 dégâts | lame · 🔊 sword sound.wav |
| 👊 **Pommeau au visage** — *Le pommeau frappe là où la lame ne passe pas.* | active | 12 PM | ennemi / cc / portée 1 | 1D6 dégâts · Int -7 Ag -3 · 3 tours | coup_lourd · 🔊 melee sound.wav |
| 💪 **Second souffle** — *Il serre les dents et repart comme au premier assaut.* | active | 12 PM | soi / portée 1 | R +9 F +4 · 4 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| ⚔️ **Taille horizontale** — *Un revers large qui fauche tout ce qui se tient devant lui.* | active | 12 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 1D8+3 dégâts | balayage · 🔊 swish_3.wav |

### Niveau 3 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🥾 **Endurance du soldat** — *Les marches forcées ont appris à son corps à se refaire en marchant.* | passive | — | permanent | régén PV +1 | — |
| 🌀 **Cercle d'acier** — *Il pivote sur lui-même, lame tendue, et dégage la place.* | active | 15 PM | ennemi / cc / portée 1 · carre rayon 1 | 1D8+4 dégâts | balayage · 🔊 swish_3.wav |
| 🪓 **Fendoir** — *Le coup tombe d'en haut, de tout son poids.* | active | 15 PM | ennemi / cc / portée 1 | 2D8+3 dégâts | coup_lourd · 🔊 melee sound.wav |
| 🛡️ **Mur de boucliers** — *Il plante les pieds et lève le bouclier : la ligne tiendra.* | active | 8 PM + 3/round | soi / portée 1 | R +13 Vol +6 | garde · 🔊 sword sound.wav |
| 🩸 **Taillade aux jarrets** — *Une entaille basse, qui saigne longtemps.* | active | 15 PM | ennemi / cc / portée 1 | 1D6+1 dégâts · régén PV -4 · 3 tours | saignee · 🔊 sword sound.wav |

### Niveau 4 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🏋️ **Carrure** — *Des épaules faites pour porter l'acier et ceux qui tombent.* | passive | — | permanent | F +3 | — |
| 👁️ **Œil du vétéran** — *Il voit venir le coup avant que l'autre ne le sache.* | passive | — | permanent | esquive 4 | — |
| 🦘 **Bond du fantassin** — *Par-dessus le fossé, par-dessus le mort, droit sur l'ennemi.* | active | 18 PM | soi / portée 1 | saut 3 cases | saut · 🔊 swish_4.wav |
| 🐏 **Coup de bélier** — *Tout le corps derrière l'épaule : l'ennemi recule et s'essouffle.* | active | 18 PM | ennemi / cc / portée 1 | 1D8 dégâts · F -9 Ag -4 · 3 tours | coup_lourd · 🔊 melee sound.wav |
| 🩸 **Coup du maître de corps** — *Il paie de sa chair un coup qui ne pardonne pas.* | active | 18 PM | ennemi / cc / portée 1 | 3D8+5 dégâts · coûte 7 PV | saignee · 🔊 sword sound.wav |
| 📣 **Cri de guerre** — *Un hurlement que la troupe reprend, et qui fait lever les armes.* | active | 18 PM | soi / portée 1 · carre rayon 1 | F +8 Vol +4 · 3 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| ⚔️ **Lame lourde** — *Un coup sans finesse, mais qui ne s'arrête pas à l'armure.* | active | 18 PM | ennemi / cc / portée 1 | 2D8+5 dégâts | lame · 🔊 sword sound.wav |

### Niveau 5 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🐗 **Cuir épais** — *Il porte ses cicatrices comme une seconde armure.* | passive | — | permanent | R +3 | — |
| 🧠 **Nerfs d'acier** — *Le fracas autour de lui ne fait plus trembler sa main.* | passive | — | permanent | Vol +3 | — |
| 🔨 **Brise-garde** — *Il frappe l'arme plutôt que l'homme, et l'arme cède.* | active | 21 PM | ennemi / cc / portée 1 | 1D8+2 dégâts · Ag -10 R -5 · 4 tours | coup_lourd · 🔊 melee sound.wav |
| 🗡️ **Estocade** — *La pointe entre là où la maille s'ouvre.* | active | 21 PM | ennemi / cc / portée 1 | 3D8+4 dégâts | lame · 🔊 sword sound.wav |
| 🌾 **Fauchage** — *Trois adversaires, un seul geste, aucun ne reste debout indemne.* | active | 21 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 2D8+5 dégâts | balayage · 🔊 swish_3.wav |
| 🎺 **Ordre de la ligne** — *Un mot sec à un compagnon, et celui-ci retrouve sa place et son courage.* | active | 21 PM | allie / portée 4 | R +13 Vol +6 · 4 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| 🧱 **Rempart vivant** — *Il devient le mur derrière lequel les autres respirent.* | active | 10 PM + 3/round | soi / portée 1 | R +16 | garde · 🔊 sword sound.wav |

### Niveau 6 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🎯 **Main sûre** — *Plus un geste perdu : chaque coup porte où il le veut.* | passive | — | permanent | Ag +4 | — |
| 💀 **Coup de grâce** — *Là où l'ennemi a déjà cédé, il achève.* | active | 25 PM | ennemi / cc / portée 1 | 3D8+6 dégâts | saignee · 🔊 sword sound.wav |
| 😤 **Défi** — *Il appelle l'ennemi d'un geste, et celui-ci se jette sur lui sans réfléchir.* | active | 25 PM | ennemi / cc / portée 1 | 2D6+2 dégâts · Int -12 Vol -6 · 4 tours | rage · 🔊 power_up_sound_v3.ogg |
| 🌊 **Vague d'acier** — *Un revers en éventail qui ouvre la mêlée.* | active | 25 PM | ennemi / cc / portée 1 · cone longueur 2 | 3D6+6 dégâts | impact_eclat_dore + nappe cone_tueur_demon · 🔊 sword sound.wav |
| 🌀 **Volée de taille** — *La lame tourne et ne revient qu'après avoir fait le tour des ennemis.* | active | 25 PM | ennemi / cc / portée 1 · carre rayon 1 | 2D8+4 dégâts | balayage · 🔊 swish_3.wav |

### Niveau 7 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🗿 **Force tranquille** — *Il ne se presse jamais, et pourtant rien ne lui résiste.* | passive | — | permanent | F +4 | — |
| ❤️‍🩹 **Instinct de survie** — *Le corps esquive avant que la tête n'ait compris.* | passive | — | permanent | esquive 6 | — |
| 🐎 **Charge du chevalier** — *D'un bond il franchit la mêlée pour tomber sur celui qui commande.* | active | 29 PM | soi / portée 1 | saut 4 cases | saut · 🔊 swish_4.wav |
| 🏰 **Frappe de siège** — *Un coup qu'on réserve d'ordinaire aux portes.* | active | 29 PM | ennemi / cc / portée 1 | 3D10+7 dégâts | coup_lourd · 🔊 melee sound.wav |
| 🪓 **Hachoir** — *Il s'ouvre la paume sur la garde et frappe comme un forcené.* | active | 29 PM | ennemi / cc / portée 1 | 4D10+6 dégâts · coûte 10 PV | saignee · 🔊 sword sound.wav |
| ⚔️ **Lame tournoyante** — *Trois coups en un, de gauche à droite et retour.* | active | 29 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 3D8+5 dégâts | balayage · 🔊 swish_3.wav |
| 🛡️ **Tenue de ligne** — *Autour de lui, les boucliers se resserrent.* | active | 29 PM | soi / portée 1 · carre rayon 1 | R +11 · 4 tours | garde · 🔊 sword sound.wav |

### Niveau 8 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌳 **Ossature de chêne** — *Les coups glissent sur lui comme la pluie sur l'écorce.* | passive | — | permanent | R +4 | — |
| 🔩 **Volonté de fer** — *Ni la peur ni la fatigue n'entrent plus sous son casque.* | passive | — | permanent | Vol +4 | — |
| 🛡️ **Garde du capitaine** — *Il tient le terrain comme on tient une promesse.* | active | 15 PM + 5/round | soi / portée 1 | R +20 F +10 | garde · 🔊 sword sound.wav |
| 🌀 **Moulinet** — *Une roue d'acier dont personne ne sort indemne.* | active | 33 PM | ennemi / cc / portée 1 · carre rayon 2 | 2D8+6 dégâts | balayage · 🔊 swish_3.wav |
| 🩹 **Soin de campagne** — *Un bandage serré, un mot bourru : le camarade se relève.* | active | 33 PM | allie / portée 1 | +38 PV | soin_nature · 🔊 power_up_sound_v2.ogg |
| ⚔️ **Tranche-armure** — *La lame cherche la jointure et la trouve.* | active | 33 PM | ennemi / cc / portée 1 | 4D10+6 dégâts | lame · 🔊 sword sound.wav |
| 🔨 **Écrasement** — *Le genou de l'ennemi cède sous le choc.* | active | 33 PM | ennemi / cc / portée 1 | 2D8+2 dégâts · Ag -14 F -7 · 4 tours | coup_lourd · 🔊 melee sound.wav |

### Niveau 9 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⚙️ **Corps de bataille** — *Il guérit entre deux combats comme d'autres reprennent haleine.* | passive | — | permanent | régén PV +2 | — |
| ❄️ **Sang-froid** — *Au cœur du chaos, il reste celui qui voit clair.* | passive | — | permanent | esquive 7 | — |
| 🩸 **Assaut sanglant** — *Il ne compte plus ses blessures, seulement les coups qu'il rend.* | active | 37 PM | ennemi / cc / portée 1 | 5D10+10 dégâts · coûte 13 PV | rage · 🔊 power_up_sound_v3.ogg |
| 🚩 **Bannière haute** — *Il lève l'étendard : toute la troupe retrouve ses forces.* | active | 37 PM | soi / portée 1 · carre rayon 2 | F +13 R +6 · 5 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| ⚔️ **Coupe-tête** — *Un coup haut, porté avec la certitude du bourreau.* | active | 37 PM | ennemi / cc / portée 1 | 4D10+9 dégâts | saignee · 🔊 sword sound.wav |
| 💥 **Fracasse-bouclier** — *Le bouclier vole en éclats, et la garde avec lui.* | active | 37 PM | ennemi / cc / portée 1 | 2D8+4 dégâts · R -15 Ag -7 · 5 tours | coup_lourd · 🔊 melee sound.wav |
| 🌪️ **Ouragan d'acier** — *La lame dessine un arc devant lui, et l'arc emporte tout.* | active | 37 PM | ennemi / cc / portée 1 · cone longueur 2 | 3D10+8 dégâts | impact_eclat_dore + nappe cone_tueur_demon · 🔊 sword sound.wav |

### Niveau 10 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🏆 **Légende des champs de bataille** — *On raconte ses batailles aux recrues ; lui ne les compte plus.* | passive | — | permanent | F +5 | — |
| 👑 **Coup du seigneur de guerre** — *Le coup qui termine les batailles.* | active | 40 PM | ennemi / cc / portée 1 | 5D10+12 dégâts | coup_lourd · 🔊 melee sound.wav |
| ⛰️ **Inébranlable** — *Une montagne n'a pas besoin de bouger pour arrêter l'armée.* | active | 18 PM + 6/round | soi / portée 1 | R +23 Vol +11 | garde · 🔊 sword sound.wav |
| 🦅 **Saut du conquérant** — *Il tombe au cœur des rangs ennemis comme un aigle sur sa proie.* | active | 40 PM | soi / portée 1 | saut 5 cases | saut · 🔊 swish_4.wav |
| 🌪️ **Tempête de lames** — *Une tourmente de fer qui ne laisse rien debout autour de lui.* | active | 40 PM | ennemi / cc / portée 1 · carre rayon 2 | 3D8+7 dégâts | balayage · 🔊 swish_3.wav |

## Illusionniste 🎭

### Niveau 1 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🪞 **Image miroir** — *Un reflet de lui-même attire les coups.* | active | 10 PM | soi / portée 1 | Int +4 · esquive 6 · 3 tours | double · 🔊 swish_2.wav |
| 💡 **Lueur aveuglante** — *Un éclat qui brûle les yeux autant que la chair.* | active | 10 PM | ennemi / magique / portée 6 | 1D8+3 dégâts | eblouissant · 🔊 17.mp3 |
| 🌫️ **Mirage** — *Une image trouble qui égare le regard de l'ennemi.* | active | 10 PM | ennemi / magique / portée 6 | 1D4 dégâts · Ag -6 · 3 tours | illusion · 🔊 power_up_sound_v3.ogg |
| 👻 **Pas fantôme** — *Il disparaît ici et réapparaît là-bas.* | active | 10 PM | soi / portée 1 | saut 2 cases | spectre · 🔊 17.mp3 |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💕 **Charme** — *Il donne à un compagnon une aura de séduction troublante.* | active | 12 PM | allie / portée 4 | Cha +9 Vol +4 · 3 tours | chant · 🔊 power_up_sound_v1.ogg |
| 🌈 **Couleurs dansantes** — *Un tourbillon de couleurs qui étourdit le groupe ennemi.* | active | 12 PM | ennemi / magique / portée 6 · cercle rayon 1 | 1D8+3 dégâts | illusion_zone · 🔊 power_up_sound_v3.ogg |
| 🗣️ **Murmure trompeur** — *Une voix dans la tête de l'ennemi qui l'épuise.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · régén PM -2 · 3 tours | illusion · 🔊 power_up_sound_v3.ogg |
| 😱 **Peur fantasmée** — *L'ennemi voit sa pire peur se dresser devant lui.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · Vol -7 F -3 · 3 tours | spectre · 🔊 17.mp3 |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🗡️ **Lame illusoire** — *Une lame qui n'existe pas, mais qui blesse.* | active | 15 PM | ennemi / magique / portée 6 | 2D8+3 dégâts | illusion · 🔊 power_up_sound_v3.ogg |
| 🫥 **Voile** — *Il s'enveloppe d'un voile qui trouble sa silhouette.* | active | 8 PM + 3/round | soi / portée 1 | Ag +13 Int +6 | furtif · 🔊 swish_2.wav |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 😨 **Cauchemar éveillé** — *Des visions horribles qui rongent l'esprit et le corps.* | active | 18 PM | ennemi / magique / portée 6 | 1D8 dégâts · régén PV -4 · 3 tours | spectre · 🔊 17.mp3 |
| 🌀 **Confusion** — *L'ennemi ne sait plus où est la gauche ni la droite.* | active | 18 PM | ennemi / magique / portée 6 | 1D8 dégâts · Int -9 Ag -4 · 3 tours | illusion · 🔊 power_up_sound_v3.ogg |
| 🔷 **Prisme** — *La lumière se brise en mille éclats tranchants.* | active | 18 PM | ennemi / magique / portée 6 | 2D8+5 dégâts | eblouissant · 🔊 17.mp3 |
| 😌 **Rêve apaisant** — *Un rêve doux qui soigne les blessures d'un compagnon.* | active | 18 PM | allie / portée 4 | régén PV +3 · 4 tours | meditation · 🔊 power_up_sound_v1.ogg |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 👯 **Doubles multiples** — *Trois, quatre, cinq de lui : lequel est le vrai ?* | active | 21 PM | soi / portée 1 | Int +6 · esquive 10 · 4 tours | double · 🔊 swish_2.wav |
| ✨ **Inspiration trompeuse** — *Il fait croire à un compagnon qu'il est invincible — et ça marche.* | active | 21 PM | allie / portée 4 | Vol +13 F +6 · 4 tours | illusion · 🔊 power_up_sound_v3.ogg |
| 👥 **Ombres hurlantes** — *Des ombres surgissent et assaillent le groupe ennemi.* | active | 21 PM | ennemi / magique / portée 6 · cercle rayon 2 | 2D6+5 dégâts | illusion_zone · 🔊 power_up_sound_v3.ogg |
| 🧠 **Vol de pensée** — *Il dérobe les pensées de la cible, et sa magie avec.* | active | 21 PM | ennemi / magique / portée 6 | 1D8+2 dégâts · 2D6+1 aux PM | illusion · 🔊 power_up_sound_v3.ogg |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🪞 **Pas entre les reflets** — *Il passe d'un reflet à un autre.* | active | 25 PM | soi / portée 1 | saut 4 cases | double · 🔊 swish_2.wav |
| 🌀 **Éventail de folie** — *Une vague de démence qui déferle devant lui.* | active | 25 PM | ennemi / magique / portée 6 · cone longueur 4 | 2D6+5 dégâts | impact_etincelles + nappe cone_folie · 🔊 power_up_sound_v3.ogg |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌙 **Dévoreur de rêves** — *Il se nourrit des rêves de la cible.* | active | 29 PM | ennemi / magique / portée 6 | 3D10+7 dégâts · drain 35 % (max 20) | spectre · 🔊 17.mp3 |
| 🗡️ **Lame de cauchemar** — *Une lame forgée dans les cauchemars de la cible.* | active | 29 PM | ennemi / magique / portée 6 | 3D10+7 dégâts | spectre · 🔊 17.mp3 |
| 😵 **Paralysie hypnotique** — *Un regard, et la cible ne bouge plus.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · Ag -13 Vol -6 · 4 tours | illusion · 🔊 power_up_sound_v3.ogg |
| 🎪 **Spectacle** — *Une illusion grandiose qui galvanise ses alliés.* | active | 29 PM | soi / portée 1 · carre rayon 1 | Cha +11 Vol +5 · 4 tours | illusion_zone · 🔊 power_up_sound_v3.ogg |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🤪 **Démence** — *La raison de la cible se délite peu à peu.* | active | 33 PM | ennemi / magique / portée 6 | 2D8+2 dégâts · régén PM -4 · 4 tours | illusion · 🔊 power_up_sound_v3.ogg |
| 🔮 **Kaléidoscope** — *Un éclatement de lumière qui aveugle tout un groupe.* | active | 33 PM | ennemi / magique / portée 6 · cercle rayon 2 | 3D8+4 dégâts | eblouissant · 🔊 17.mp3 |
| 🎭 **Masque de terreur** — *Il revêt un masque qui terrifie quiconque le regarde.* | active | 33 PM | ennemi / magique / portée 6 | 2D8+2 dégâts · Vol -14 F -7 · 4 tours | spectre · 🔊 17.mp3 |
| 🏝️ **Mirage de refuge** — *Il se dissimule dans un refuge qui n'existe pas.* | active | 15 PM + 5/round | soi / portée 1 | Ag +20 R +10 | illusion · 🔊 power_up_sound_v3.ogg |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌀 **Folie collective** — *Le groupe ennemi perd toute raison.* | active | 37 PM | ennemi / magique / portée 6 · cone longueur 4 | 3D8+4 dégâts | impact_etincelles + nappe cone_folie · 🔊 power_up_sound_v3.ogg |
| 🎭 **Grand théâtre** — *Une illusion longue à monter, terrible à vivre.* | active | 48 PM · ⏱ 3 PA | ennemi / magique / portée 6 | 5D10+10 dégâts | illusion_zone · 🔊 power_up_sound_v3.ogg |
| 💀 **Illusion mortelle** — *La cible croit mourir — et son corps la croit.* | active | 37 PM | ennemi / magique / portée 6 | 4D10+9 dégâts | spectre · 🔊 17.mp3 |
| 💭 **Rêve partagé** — *Il partage un rêve qui restaure l'énergie d'un compagnon.* | active | 37 PM | allie / portée 4 | +24 PM | meditation · 🔊 power_up_sound_v1.ogg |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🎆 **Fantasmagorie** — *Le monde entier semble se retourner contre l'ennemi.* | active | 40 PM | ennemi / magique / portée 6 · cercle rayon 2 | 3D10+6 dégâts | illusion_zone · 🔊 power_up_sound_v3.ogg |
| 💔 **Réalité brisée** — *La cible ne sait plus ce qui est réel.* | active | 40 PM | ennemi / magique / portée 6 | 3D8+2 dégâts · Int -16 Vol -8 Ag -8 · 5 tours | illusion · 🔊 power_up_sound_v3.ogg |

## Lettré 📜

### Niveau 1 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 📖 **Citation savante** — *Une citation si brillante qu'elle laisse l'ennemi interdit.* | active | 10 PM | ennemi / magique / portée 6 | 1D4 dégâts · Int -6 · 3 tours | arcane · 🔊 17.mp3 |
| 🧪 **Fiole corrosive** — *Une fiole d'acide jetée avec précision.* | active | 10 PM | ennemi / magique / portée 6 | 1D8+3 dégâts | alchimie · 🔊 power_up_sound_v1.ogg |
| 🍵 **Tonique** — *Une infusion de sa composition qui remet d'aplomb.* | active | 10 PM | allie / portée 4 | +16 PV | alchimie · 🔊 power_up_sound_v1.ogg |
| 🔍 **Étude de l'adversaire** — *Il observe, note, et comprend comment frapper.* | active | 10 PM | soi / portée 1 | Int +8 Ag +4 · 4 tours | meditation · 🔊 power_up_sound_v1.ogg |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⚙️ **Mécanisme à ressort** — *Une semelle à ressort de son invention.* | active | 12 PM | soi / portée 1 | saut 2 cases | saut · 🔊 swish_4.wav |
| 💥 **Poudre détonante** — *Un petit sachet de poudre qui fait grand bruit.* | active | 12 PM | ennemi / magique / portée 6 · cercle rayon 1 | 1D8+3 dégâts | explosion_feu · 🔊 foom_0.wav |
| 😴 **Somnifère** — *Une fiole qui alourdit les paupières.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · Ag -7 Vol -3 · 3 tours | alchimie · 🔊 power_up_sound_v1.ogg |
| 💧 **Élixir de clarté** — *Un élixir qui clarifie l'esprit et rend du mana.* | active | 12 PM | allie / portée 4 | +10 PM | alchimie · 🔊 power_up_sound_v1.ogg |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🏹 **Flèche alchimique** — *Une fléchette trempée dans une mixture corrosive.* | active | 15 PM | ennemi / magique / portée 6 | 1D6+1 dégâts · régén PV -4 · 3 tours | alchimie · 🔊 power_up_sound_v1.ogg |
| 🔰 **Glyphe protecteur** — *Il trace un glyphe sur l'armure d'un compagnon.* | active | 15 PM | allie / portée 4 | R +10 Vol +5 · 3 tours | enchantement · 🔊 power_up_sound_v0.ogg |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💨 **Bombe de fumée** — *Un nuage dense qui couvre sa retraite.* | active | 18 PM | soi / portée 1 | Int +6 · esquive 9 · 3 tours | poudre · 🔊 swish_2.wav |
| 🫗 **Dissolvant** — *Une fiole qui dissout la magie de la cible.* | active | 18 PM | ennemi / magique / portée 6 | 1D8 dégâts · 2D6 aux PM | alchimie · 🔊 power_up_sound_v1.ogg |
| 🧴 **Onguent** — *Un onguent à base de miel et d'herbes rares.* | active | 18 PM | allie / portée 4 | régén PV +3 · 4 tours | alchimie · 🔊 power_up_sound_v1.ogg |
| 💡 **Éclat de savoir** — *La connaissance brute, projetée comme une lame.* | active | 18 PM | ennemi / magique / portée 6 | 2D8+5 dégâts | eblouissant · 🔊 17.mp3 |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🔥 **Feu liquide** — *Une fiole de feu liquide qui se répand devant lui.* | active | 21 PM | ennemi / magique / portée 6 · rectangle longueur 1 largeur 3 | 2D8+5 dégâts | feu · 🔊 foom_0.wav |
| 🏛️ **Mémoire du palais** — *Il se retire dans son palais mental, où rien ne l'atteint.* | active | 10 PM + 3/round | soi / portée 1 | Int +16 Vol +8 | meditation · 🔊 power_up_sound_v1.ogg |
| ♾️ **Paradoxe** — *Une énigme insoluble qui paralyse l'esprit de la cible.* | active | 21 PM | ennemi / magique / portée 6 | 1D8+2 dégâts · Int -10 Ag -5 · 4 tours | illusion · 🔊 power_up_sound_v3.ogg |
| ⚗️ **Transmutation** — *Il transmute la vitalité de la cible en la sienne.* | active | 21 PM | ennemi / magique / portée 6 | 3D8+4 dégâts · drain 30 % | alchimie · 🔊 power_up_sound_v1.ogg |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💣 **Grenade alchimique** — *Un globe de verre qui éclate en flammes vertes.* | active | 25 PM | ennemi / magique / portée 6 · cercle rayon 2 | 2D8+4 dégâts | explosion_feu · 🔊 foom_0.wav |
| 💊 **Panacée** — *Une brume curative qui soigne tout un groupe.* | active | 25 PM | allie / portée 4 · cercle rayon 1 | +18 PV | alchimie · 🔊 power_up_sound_v1.ogg |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🤖 **Automate de saut** — *Un harnais mécanique le projette au loin.* | active | 29 PM | soi / portée 1 | saut 4 cases | saut · 🔊 swish_4.wav |
| ✨ **Enchantement d'arme** — *Il enchante l'arme d'un compagnon pour la durée du combat.* | active | 29 PM | allie / portée 4 | F +16 Ag +8 · 4 tours | enchantement · 🔊 power_up_sound_v0.ogg |
| ☁️ **Gaz innervant** — *Une vapeur qui ronge la volonté.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · régén PM -4 · 4 tours | poison · 🔊 17.mp3 |
| 🗣️ **Verbe de pouvoir** — *Un mot ancien qui frappe comme un coup de masse.* | active | 29 PM | ennemi / magique / portée 6 | 3D10+7 dégâts | arcane · 🔊 17.mp3 |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🧪 **Acide royal** — *L'acide qui dissout l'or — et le reste.* | active | 33 PM | ennemi / magique / portée 6 | 2D8+2 dégâts · régén PV -6 · 4 tours | alchimie · 🔊 power_up_sound_v1.ogg |
| 📐 **Démonstration** — *Une démonstration si implacable que l'ennemi en perd ses moyens.* | active | 33 PM | ennemi / magique / portée 6 | 2D8+2 dégâts · Int -14 Vol -7 · 4 tours | arcane · 🔊 17.mp3 |
| 💥 **Explosion en chaîne** — *Une série de fioles explosent en éventail.* | active | 33 PM | ennemi / magique / portée 6 · cone longueur 3 | 3D8+4 dégâts | impact_brulure + nappe cone_souffle_feu · 🔊 foom_0.wav |
| 📚 **Grande encyclopédie** — *Il partage ce qu'il sait, et le groupe combat plus intelligemment.* | active | 33 PM | soi / portée 1 · carre rayon 1 | Int +12 Vol +6 · 4 tours | meditation · 🔊 power_up_sound_v1.ogg |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💎 **Pierre philosophale** — *Un processus long qui libère une énergie terrible.* | active | 48 PM · ⏱ 3 PA | ennemi / magique / portée 6 | 5D10+10 dégâts | alchimie · 🔊 power_up_sound_v1.ogg |
| 🤐 **Rune de silence** — *Une rune qui coupe la cible de toute magie.* | active | 37 PM | ennemi / magique / portée 6 | 2D8+4 dégâts · 2D8+2 aux PM | enchantement · 🔊 power_up_sound_v0.ogg |
| ⚡ **Éclair de génie** — *Une idée si brillante qu'elle foudroie.* | active | 37 PM | ennemi / magique / portée 6 | 4D10+9 dégâts | foudre · 🔊 17.mp3 |
| ❤️ **Élixir de vie** — *L'élixir que cherchent tous les alchimistes.* | active | 37 PM | allie / portée 4 | +42 PV | soin_sacre · 🔊 power_up_sound_v1.ogg |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌐 **Savoir universel** — *Il embrasse toutes les connaissances, et rien ne le surprend plus.* | active | 18 PM + 6/round | soi / portée 1 | Int +23 Vol +11 | enchantement · 🔊 power_up_sound_v0.ogg |
| ⚫ **Œuvre au noir** — *Le premier stade du Grand Œuvre, libéré sur l'ennemi.* | active | 40 PM | ennemi / magique / portée 6 · cercle rayon 2 | 3D10+6 dégâts | ombre · 🔊 17.mp3 |

## Magicien de combat 🌀

### Niveau 1 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🛡️ **Bouclier réflexe** — *Un bouclier qui se dresse avant même qu'il ne le décide.* | active | 10 PM | soi / portée 1 | Int +4 · esquive 6 · 3 tours | bouclier · 🔊 power_up_sound_v2.ogg |
| ⚔️ **Lame chargée** — *Le bâton s'illumine au moment du coup.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | enchantement · 🔊 power_up_sound_v0.ogg |
| ⚡ **Pas éclair** — *Un pas, un éclair, il est ailleurs.* | active | 10 PM | soi / portée 1 | saut 2 cases | saut · 🔊 swish_4.wav |
| 🔮 **Projectile arcanique** — *Une sphère d'énergie violette qui file vers la cible.* | active | 10 PM | ennemi / magique / portée 6 | 1D8+3 dégâts | arcane · 🔊 17.mp3 |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🗡️ **Arme enchantée** — *Il grave une rune sur l'arme d'un compagnon.* | active | 12 PM | allie / portée 4 | F +9 · 3 tours | enchantement · 🔊 power_up_sound_v0.ogg |
| 🕳️ **Brèche de mana** — *Il ouvre une brèche dans la réserve de mana adverse.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · 1D6+1 aux PM | arcane · 🔊 17.mp3 |
| 💥 **Onde de choc arcanique** — *Une onde violette qui repousse le premier rang.* | active | 12 PM | ennemi / magique / portée 6 · rectangle longueur 1 largeur 3 | 1D8+3 dégâts | arcane · 🔊 17.mp3 |
| 💫 **Rayon de force** — *Un rayon qui pèse sur les membres de l'ennemi.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · F -7 Ag -3 · 3 tours | arcane · 🔊 17.mp3 |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🛡️ **Champ de force** — *Un champ de force qu'il tient à bout de volonté.* | active | 8 PM + 3/round | soi / portée 1 | R +13 Int +6 | bouclier · 🔊 power_up_sound_v2.ogg |
| 🎯 **Missile guidé** — *Le projectile contourne la garde et frappe juste.* | active | 15 PM | ennemi / magique / portée 6 | 2D8+3 dégâts | arcane · 🔊 17.mp3 |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💥 **Explosion arcanique** — *Une sphère d'énergie éclate au milieu des ennemis.* | active | 18 PM | ennemi / magique / portée 6 · cercle rayon 1 | 2D6+5 dégâts | arcane · 🔊 17.mp3 |
| 🔪 **Lame de mana** — *Une lame faite de mana pur, qui ignore le métal.* | active | 18 PM | ennemi / cc / portée 1 | 2D8+5 dégâts | enchantement · 🔊 power_up_sound_v0.ogg |
| 🐌 **Ralentissement** — *Le temps s'épaissit autour de la cible.* | active | 18 PM | ennemi / magique / portée 6 | 1D8 dégâts · Ag -9 · 3 tours | illusion · 🔊 power_up_sound_v3.ogg |
| ᚢ **Rune de vigueur** — *Une rune tracée sur sa poitrine qui le rend plus fort.* | active | 18 PM | soi / portée 1 | F +12 R +6 · 4 tours | enchantement · 🔊 power_up_sound_v0.ogg |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🛡️ **Bouclier partagé** — *Il projette un bouclier sur un compagnon.* | active | 21 PM | allie / portée 4 | R +13 · 4 tours | bouclier · 🔊 power_up_sound_v2.ogg |
| 🔥 **Brûlure de mana** — *Le mana adverse se met à brûler son porteur.* | active | 21 PM | ennemi / magique / portée 6 | 1D8+2 dégâts · régén PM -3 · 4 tours | arcane · 🔊 17.mp3 |
| 🌀 **Saut de force** — *Une impulsion de force qui le projette en avant.* | active | 21 PM | soi / portée 1 | saut 3 cases | saut · 🔊 swish_4.wav |
| ⚡ **Éclair de bataille** — *La foudre des champs de bataille, maîtrisée.* | active | 21 PM | ennemi / magique / portée 6 | 3D8+4 dégâts | foudre · 🔊 17.mp3 |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌀 **Absorption** — *Il absorbe l'énergie vitale de la cible.* | active | 25 PM | ennemi / magique / portée 6 | 3D8+6 dégâts · drain 35 % | drain · 🔊 17.mp3 |
| 🌀 **Tourbillon arcanique** — *L'énergie tourbillonne autour de lui et frappe tout ce qu'elle touche.* | active | 25 PM | ennemi / magique / portée 6 · carre rayon 1 | 2D8+4 dégâts | arcane · 🔊 17.mp3 |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🔲 **Cage de force** — *Des murs invisibles enferment l'ennemi.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · Ag -13 F -6 · 4 tours | bouclier · 🔊 power_up_sound_v2.ogg |
| ⚡ **Décharge** — *Une décharge en éventail qui grille les premiers rangs.* | active | 29 PM | ennemi / magique / portée 6 · cone longueur 3 | 2D8+6 dégâts | impact_etincelles + nappe cone_decharge · 🔊 17.mp3 |
| 🔱 **Lance arcanique** — *Une lance de pure énergie qui transperce tout.* | active | 29 PM | ennemi / magique / portée 6 | 3D10+7 dégâts | arcane · 🔊 17.mp3 |
| 🛡️ **Égide de bataille** — *Un dôme protecteur s'étend autour du groupe.* | active | 29 PM | soi / portée 1 · carre rayon 1 | R +11 Int +5 · 4 tours | bouclier · 🔊 power_up_sound_v2.ogg |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ☄️ **Bombardement** — *Une pluie de projectiles s'abat sur la zone.* | active | 33 PM | ennemi / magique / portée 6 · cercle rayon 2 | 3D8+4 dégâts | meteore · 🔊 foom_0.wav |
| ᚦ **Frappe runique** — *Le bâton gravé de runes frappe comme un marteau.* | active | 33 PM | ennemi / cc / portée 1 | 4D10+6 dégâts | enchantement · 🔊 power_up_sound_v0.ogg |
| 🔋 **Recharge** — *Il transfère une part de son mana à un compagnon.* | active | 33 PM | allie / portée 4 | +22 PM | enchantement · 🔊 power_up_sound_v0.ogg |
| 🕳️ **Vide arcanique** — *Il crée un vide qui aspire toute la magie de la cible.* | active | 33 PM | ennemi / magique / portée 6 | 2D8+2 dégâts · 2D8+1 aux PM | arcane · 🔊 17.mp3 |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🛡️ **Armure runique** — *Des runes recouvrent son armure et brillent tant qu'il les nourrit.* | active | 16 PM + 5/round | soi / portée 1 | R +21 Int +10 | enchantement · 🔊 power_up_sound_v0.ogg |
| 💀 **Rayon désintégrant** — *Un rayon qui défait la matière.* | active | 37 PM | ennemi / magique / portée 6 | 4D10+9 dégâts | arcane · 🔊 17.mp3 |
| 🤐 **Sceau de silence** — *Un sceau qui empêche la cible de puiser dans sa magie.* | active | 37 PM | ennemi / magique / portée 6 | 2D8+4 dégâts · régén PM -5 · 5 tours | arcane · 🔊 17.mp3 |
| ⛈️ **Tempête arcanique** — *Il rassemble l'énergie pendant de longs instants avant de la libérer.* | active | 48 PM · ⏱ 3 PA | ennemi / magique / portée 6 | 5D10+10 dégâts | arcane · 🔊 17.mp3 |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⚔️ **Lame du mage-guerrier** — *Il nourrit sa lame de sa propre vie.* | active | 40 PM | ennemi / cc / portée 1 | 6D10+12 dégâts · coûte 15 PV | enchantement · 🔊 power_up_sound_v0.ogg |
| 💥 **Nova arcanique** — *Une explosion d'énergie pure tout autour de lui.* | active | 40 PM | ennemi / magique / portée 6 · carre rayon 2 | 3D8+7 dégâts | arcane · 🔊 17.mp3 |

## Ménestrel 🎶

### Niveau 1 — 1 existante(s) + 3 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🍺 **Chanson à boire** — *Un refrain joyeux qui redonne courage.* | active | 10 PM | allie / portée 4 | Vol +8 Cha +4 · 3 tours | chant · 🔊 power_up_sound_v1.ogg |
| 🪕 **Coup de luth** — *Le luth sert aussi à ça.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | poing · 🔊 melee sound.wav |
| 🎵 **Note discordante** — *Une note fausse qui fait grincer les dents.* | active | 10 PM | ennemi / magique / portée 6 | 1D4 dégâts · Vol -6 · 3 tours | chant · 🔊 power_up_sound_v1.ogg |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 😴 **Berceuse** — *Une mélodie douce qui alourdit les paupières.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · Ag -7 Vol -3 · 3 tours | chant · 🔊 power_up_sound_v1.ogg |
| 🎶 **Mélodie apaisante** — *Une mélodie qui apaise les blessures.* | active | 12 PM | allie / portée 4 | régén PV +2 · 4 tours | chant · 🔊 power_up_sound_v1.ogg |
| 💃 **Pas de danse** — *Il danse entre les coups.* | active | 12 PM | soi / portée 1 | Cha +4 · esquive 7 · 3 tours | chant · 🔊 power_up_sound_v1.ogg |
| 😂 **Satire** — *Une chanson moqueuse qui sape le moral.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · régén PM -2 · 3 tours | chant · 🔊 power_up_sound_v1.ogg |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🎺 **Air de bravoure** — *Un air héroïque qui galvanise ses alliés.* | active | 15 PM | soi / portée 1 · carre rayon 1 | F +7 Vol +3 · 3 tours | chant · 🔊 power_up_sound_v1.ogg |
| 📢 **Cri strident** — *Un cri si aigu qu'il blesse les oreilles.* | active | 15 PM | ennemi / magique / portée 6 · cercle rayon 1 | 2D6+3 dégâts | chant · 🔊 power_up_sound_v1.ogg |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🎸 **Accord dissonant** — *Un accord qui fait vibrer les os.* | active | 18 PM | ennemi / magique / portée 6 | 2D8+5 dégâts | chant · 🔊 power_up_sound_v1.ogg |
| 📜 **Ballade du héros** — *La ballade d'un héros, chantée pour un compagnon.* | active | 18 PM | allie / portée 4 | F +12 R +6 · 3 tours | chant · 🔊 power_up_sound_v1.ogg |
| 😌 **Chant de repos** — *Un chant qui rend le souffle et l'énergie.* | active | 18 PM | allie / portée 4 | +14 PM | chant · 🔊 power_up_sound_v1.ogg |
| 💕 **Charme du barde** — *Un sourire et un vers, et l'ennemi baisse sa garde.* | active | 18 PM | ennemi / magique / portée 6 | 1D8 dégâts · Int -9 Vol -4 · 3 tours | illusion · 🔊 power_up_sound_v3.ogg |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🎶 **Chœur** — *Un chœur qui soigne tous ceux qui l'entendent.* | active | 21 PM | allie / portée 4 · cercle rayon 1 | +16 PV | chant · 🔊 power_up_sound_v1.ogg |
| 🗡️ **Lame du conteur** — *Une dague sortie au milieu d'une histoire.* | active | 21 PM | ennemi / cc / portée 1 | 3D8+4 dégâts | lame · 🔊 sword sound.wav |
| 🤸 **Pirouette** — *Une pirouette acrobatique qui le met hors de portée.* | active | 21 PM | soi / portée 1 | saut 3 cases | saut · 🔊 swish_4.wav |
| ⚰️ **Requiem** — *Un chant funèbre qui ronge la cible.* | active | 21 PM | ennemi / magique / portée 6 | 1D8+2 dégâts · régén PV -5 · 4 tours | chant · 🔊 power_up_sound_v1.ogg |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌹 **Sérénade** — *Une sérénade qui soigne le cœur et le corps.* | active | 25 PM | allie / portée 4 | +30 PV | chant · 🔊 power_up_sound_v1.ogg |
| 🥁 **Tonnerre de tambour** — *Un roulement de tambour qui déferle devant lui.* | active | 25 PM | ennemi / magique / portée 6 · cone longueur 4 | 2D6+5 dégâts | impact_etincelles + nappe cone_folie · 🔊 power_up_sound_v3.ogg |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 📯 **Chanson de geste** — *La chanson des grandes batailles, que tous reprennent.* | active | 29 PM | soi / portée 1 · carre rayon 2 | F +11 R +5 · 4 tours | chant · 🔊 power_up_sound_v1.ogg |
| 💀 **Danse macabre** — *Une danse qui fait trembler les morts et les vivants.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · Vol -13 Ag -6 · 4 tours | spectre · 🔊 17.mp3 |
| 🔁 **Ritournelle** — *Une ritournelle qu'il ne cesse de fredonner, et qui le protège.* | active | 13 PM + 4/round | soi / portée 1 | Cha +19 Ag +9 | chant · 🔊 power_up_sound_v1.ogg |
| 🎤 **Voix d'or** — *Une voix si belle qu'elle vide l'ennemi de ses forces.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · 2D8 aux PM | chant · 🔊 power_up_sound_v1.ogg |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 😢 **Complainte** — *Une complainte si triste qu'elle désespère.* | active | 33 PM | ennemi / magique / portée 6 | 2D8+2 dégâts · régén PM -4 · 4 tours | chant · 🔊 power_up_sound_v1.ogg |
| 📈 **Crescendo** — *La musique monte, monte, et frappe.* | active | 33 PM | ennemi / magique / portée 6 | 4D10+6 dégâts | chant · 🔊 power_up_sound_v1.ogg |
| 🏆 **Hymne de victoire** — *Un hymne qui annonce la victoire.* | active | 33 PM | allie / portée 4 | Vol +17 F +8 · 4 tours | chant · 🔊 power_up_sound_v1.ogg |
| 🎭 **Opéra** — *Une scène entière qui s'abat sur l'ennemi.* | active | 33 PM | ennemi / magique / portée 6 · cercle rayon 2 | 3D8+4 dégâts | illusion_zone · 🔊 power_up_sound_v3.ogg |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💚 **Chant de vie** — *Un chant qui soigne tout un groupe.* | active | 37 PM | allie / portée 4 · cercle rayon 1 | +25 PV | soin_vague · 🔊 power_up_sound_v1.ogg |
| 🎪 **Pas du saltimbanque** — *Un saut acrobatique digne des foires.* | active | 37 PM | soi / portée 1 | saut 5 cases | saut · 🔊 swish_4.wav |
| 🎼 **Symphonie** — *Une symphonie longue à jouer, terrible à entendre.* | active | 48 PM · ⏱ 3 PA | ennemi / magique / portée 6 | 5D10+10 dégâts | chant · 🔊 power_up_sound_v1.ogg |
| 🧜 **Voix de sirène** — *Une voix qui envoûte et paralyse.* | active | 37 PM | ennemi / magique / portée 6 | 2D8+4 dégâts · Vol -15 Int -7 · 5 tours | illusion · 🔊 power_up_sound_v3.ogg |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🎶 **Cantate des héros** — *La cantate que chantent les héros avant de mourir — ou de vaincre.* | active | 40 PM | soi / portée 1 · carre rayon 2 | F +14 Vol +7 · 5 tours | chant · 🔊 power_up_sound_v1.ogg |
| 🎵 **Dernière note** — *La note finale, qui laisse le silence derrière elle.* | active | 40 PM | ennemi / magique / portée 6 | 5D10+12 dégâts | chant · 🔊 power_up_sound_v1.ogg |

## Moine 🥋

### Niveau 1 — 1 existante(s) + 3 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦵 **Balayage de jambe** — *Il fauche les appuis de l'adversaire d'un seul mouvement.* | active | 10 PM | ennemi / cc / portée 1 | 1D4 dégâts · Ag -6 · 3 tours | poing · 🔊 melee sound.wav |
| 🤚 **Paume tranchante** — *Le tranchant de la main, durci par mille planches brisées.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | poing · 🔊 melee sound.wav |
| 🪷 **Respiration du lotus** — *Un souffle profond, et le corps se fait léger.* | active | 10 PM | soi / portée 1 | Vol +8 Ag +4 · 4 tours | meditation · 🔊 power_up_sound_v1.ogg |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🕊️ **Bond de la grue** — *Il s'élève comme la grue et retombe où il le veut.* | active | 12 PM | soi / portée 1 | saut 2 cases | vent · 🔊 swish_4.wav |
| 🐉 **Coup du dragon** — *Un poing qui part des talons et finit dans la poitrine adverse.* | active | 12 PM | ennemi / cc / portée 1 | 2D6+3 dégâts | poing · 🔊 melee sound.wav |
| 🤲 **Main apaisante** — *Une paume posée sur la blessure, et la douleur reflue.* | active | 12 PM | allie / portée 1 | +18 PV | soin_sacre · 🔊 power_up_sound_v1.ogg |
| ☯️ **Toucher des méridiens** — *Deux doigts sur un point vital, et l'énergie de l'autre se dissipe.* | active | 12 PM | ennemi / cc / portée 1 | 1D6 dégâts · 1D6+1 aux PM | meditation · 🔊 power_up_sound_v1.ogg |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌀 **Roue du vent** — *Il tourne sur lui-même, pieds et poings en éventail.* | active | 15 PM | ennemi / cc / portée 1 · carre rayon 1 | 1D8+4 dégâts | poing · 🔊 melee sound.wav |
| 🌬️ **Souffle intérieur** — *Il partage le calme de son souffle avec un compagnon.* | active | 15 PM | allie / portée 4 | +12 PM | meditation · 🔊 power_up_sound_v1.ogg |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💭 **Esprit clair** — *Un mot calme, et un compagnon retrouve sa lucidité.* | active | 18 PM | allie / portée 4 | Vol +12 Int +6 · 3 tours | meditation · 🔊 power_up_sound_v1.ogg |
| 🐯 **Frappe du tigre** — *Les doigts en griffes, il déchire la garde.* | active | 18 PM | ennemi / cc / portée 1 | 1D8 dégâts · Ag -9 F -4 · 3 tours | griffe · 🔊 animal melee sound.wav |
| 🪨 **Poing de pierre** — *Sa main frappe comme la roche tombe.* | active | 18 PM | ennemi / cc / portée 1 | 2D8+5 dégâts | roc · 🔊 melee sound.wav |
| ⛰️ **Posture de la montagne** — *Il s'enracine : rien ne le déplacera.* | active | 9 PM + 3/round | soi / portée 1 | R +15 Vol +7 | meditation · 🔊 power_up_sound_v1.ogg |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🔔 **Chant du monastère** — *Un mantra grave que reprennent ceux qui l'entourent.* | active | 21 PM | soi / portée 1 · carre rayon 1 | Vol +9 R +4 · 4 tours | chant · 🔊 power_up_sound_v1.ogg |
| 🐍 **Coup du serpent** — *Deux doigts au creux de l'épaule, et l'énergie fuit.* | active | 21 PM | ennemi / cc / portée 1 | 1D8+2 dégâts · régén PM -3 · 4 tours | poing · 🔊 melee sound.wav |
| 🍃 **Pas de la brise** — *Il devient insaisissable comme une brise.* | active | 21 PM | soi / portée 1 | Vol +6 · esquive 10 · 4 tours | vent · 🔊 swish_4.wav |
| ☀️ **Paume de lumière** — *Une paume chargée d'énergie pure.* | active | 21 PM | ennemi / magique / portée 4 | 3D8+4 dégâts | lumiere · 🔊 17.mp3 |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 👊 **Mille poings** — *Une rafale de coups si rapide qu'on n'en compte que le bruit.* | active | 25 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 3D6+6 dégâts | poing · 🔊 melee sound.wav |
| ☯️ **Sceau d'harmonie** — *Il rétablit l'équilibre dans le corps d'un compagnon.* | active | 25 PM | allie / portée 4 | régén PV +3 · 5 tours | soin_sacre · 🔊 power_up_sound_v1.ogg |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🛡️ **Corps de bronze** — *Il durcit sa peau par la seule volonté.* | active | 13 PM + 4/round | soi / portée 1 | R +19 | bouclier · 🔊 power_up_sound_v2.ogg |
| 👻 **Frappe de l'âme** — *Le coup traverse la chair et touche l'esprit.* | active | 29 PM | ennemi / magique / portée 4 | 3D10+7 dégâts · drain 35 % (max 20) | meditation · 🔊 power_up_sound_v1.ogg |
| 🔥 **Pied du phénix** — *Un coup de pied qui laisse une traînée brûlante.* | active | 29 PM | ennemi / cc / portée 1 | 3D10+7 dégâts | feu · 🔊 foom_0.wav |
| 🐒 **Saut du singe** — *Un bond acrobatique par-dessus la mêlée.* | active | 29 PM | soi / portée 1 | saut 4 cases | saut · 🔊 swish_4.wav |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💥 **Onde de choc** — *Il frappe le sol, et l'onde renverse tout autour de lui.* | active | 33 PM | ennemi / cc / portée 1 · carre rayon 2 | 2D8+6 dégâts | poing · 🔊 melee sound.wav |
| 📍 **Point de pression** — *Un doigt sur un nerf, et le bras de l'ennemi ne répond plus.* | active | 33 PM | ennemi / cc / portée 1 | 2D8+2 dégâts · F -14 Ag -7 · 4 tours | poing · 🔊 melee sound.wav |
| 💨 **Souffle de vie** — *Un souffle qui ranime ceux qui l'entourent.* | active | 33 PM | allie / portée 4 · cercle rayon 1 | +23 PV | soin_vague · 🔊 power_up_sound_v1.ogg |
| 🕳️ **Vide intérieur** — *Il fait le vide en lui — et chez l'autre.* | active | 33 PM | ennemi / magique / portée 4 | 2D8+2 dégâts · 2D8+1 aux PM | arcane · 🔊 17.mp3 |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🧠 **Brise-esprit** — *Un coup au front qui trouble les pensées.* | active | 37 PM | ennemi / magique / portée 4 | 2D8+4 dégâts · régén PM -5 · 5 tours | arcane · 🔊 17.mp3 |
| 🙏 **Danse des mille mains** — *Une rafale de paumes qui s'ouvre devant lui en éventail.* | active | 37 PM | ennemi / cc / portée 1 · cone longueur 3 | 3D8+6 dégâts | impact_etincelles + nappe cone_decharge · 🔊 17.mp3 |
| 🕊️ **Paix du sage** — *Une sérénité qui gagne tout le groupe.* | active | 37 PM | soi / portée 1 · carre rayon 2 | Vol +13 R +6 · 5 tours | meditation · 🔊 power_up_sound_v1.ogg |
| ☁️ **Poing du ciel** — *Un poing qui tombe comme la foudre du ciel.* | active | 37 PM | ennemi / cc / portée 1 | 4D10+9 dégâts | lumiere · 🔊 17.mp3 |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌤️ **Ascension** — *Il s'élève et retombe comme une feuille portée par le vent.* | active | 40 PM | soi / portée 1 | saut 5 cases | aura_sacree · 🔊 power_up_sound_v0.ogg |
| 🌑 **Paume du néant** — *Une paume qui efface ce qu'elle touche.* | active | 40 PM | ennemi / cc / portée 1 | 5D10+12 dégâts | arcane · 🔊 17.mp3 |

## Nécromancien 💀

### Niveau 1 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⚰️ **Linceul** — *Il s'enveloppe d'un linceul qui le protège.* | active | 10 PM | soi / portée 1 | R +8 Vol +4 · 4 tours | tombeau · 🔊 17.mp3 |
| 🤢 **Malaise** — *Une nausée soudaine qui affaiblit la cible.* | active | 10 PM | ennemi / magique / portée 6 | 1D4 dégâts · R -6 · 3 tours | poison · 🔊 17.mp3 |
| 🩸 **Sangsue** — *Il boit un peu de la vie de la cible.* | active | 10 PM | ennemi / magique / portée 6 | 1D8+3 dégâts · drain 25 % | drain · 🔊 17.mp3 |
| 🥶 **Toucher glacé** — *Un toucher qui glace la chair jusqu'à l'os.* | active | 10 PM | ennemi / magique / portée 6 | 1D8+3 dégâts | ombre · 🔊 17.mp3 |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 👻 **Murmure des morts** — *Les morts murmurent à l'oreille de la cible et l'épuisent.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · régén PM -2 · 3 tours | spectre · 🔊 17.mp3 |
| 🪦 **Pas de la tombe** — *Il disparaît dans le sol et ressort plus loin.* | active | 12 PM | soi / portée 1 | saut 2 cases | spectre · 🔊 17.mp3 |
| ☠️ **Peste** — *Une maladie qui ronge la cible.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · régén PV -3 · 3 tours | poison · 🔊 17.mp3 |
| 🦴 **Trait d'os** — *Un éclat d'os projeté comme une flèche.* | active | 12 PM | ennemi / magique / portée 6 | 2D6+3 dégâts | roc · 🔊 melee sound.wav |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦴 **Faiblesse** — *Les muscles de la cible se changent en chiffons.* | active | 15 PM | ennemi / magique / portée 6 | 1D6+1 dégâts · F -8 R -4 · 3 tours | ombre · 🔊 17.mp3 |
| ☁️ **Nuage pestilentiel** — *Un nuage de pestilence qui empoisonne le groupe.* | active | 15 PM | ennemi / magique / portée 6 · cercle rayon 1 | 2D6+3 dégâts | poison · 🔊 17.mp3 |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦴 **Carapace d'os** — *Des os se soudent autour de lui en armure.* | active | 9 PM + 3/round | soi / portée 1 | R +15 | tombeau · 🔊 17.mp3 |
| 🌑 **Lance d'ombre** — *Une lance d'ombre pure qui transperce.* | active | 18 PM | ennemi / magique / portée 6 | 2D8+5 dégâts | ombre · 🔊 17.mp3 |
| 👻 **Siphon d'âme** — *Il aspire l'énergie magique de la cible.* | active | 18 PM | ennemi / magique / portée 6 | 1D8 dégâts · 2D6 aux PM | spectre · 🔊 17.mp3 |
| 🧛 **Vampirisme** — *Il se nourrit du sang de la cible.* | active | 18 PM | ennemi / magique / portée 6 | 2D8+5 dégâts · drain 30 % | drain · 🔊 17.mp3 |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💥 **Explosion de cadavre** — *Un cadavre éclate au milieu des ennemis.* | active | 21 PM | ennemi / magique / portée 6 · cercle rayon 2 | 2D6+5 dégâts | explosion_feu · 🔊 foom_0.wav |
| 🖐️ **Main du tombeau** — *Une main sort de terre et agrippe la cible.* | active | 21 PM | ennemi / magique / portée 6 | 1D8+2 dégâts · Ag -10 · 4 tours | tombeau · 🔊 17.mp3 |
| 🩸 **Pacte de sang noir** — *Il paie de son sang un sort de mort.* | active | 21 PM | ennemi / magique / portée 6 | 3D8+8 dégâts · coûte 8 PV | drain · 🔊 17.mp3 |
| ⚫ **Énergie sombre** — *Il transfère de l'énergie sombre à un compagnon.* | active | 21 PM | allie / portée 4 | +16 PM | ombre · 🔊 17.mp3 |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦠 **Corruption** — *Une corruption qui ronge le corps lentement.* | active | 25 PM | ennemi / magique / portée 6 | 2D6+2 dégâts · régén PV -5 · 4 tours | poison · 🔊 17.mp3 |
| 🌫️ **Souffle de la tombe** — *Un souffle froid venu d'outre-tombe.* | active | 25 PM | ennemi / magique / portée 6 · cone longueur 4 | 2D6+5 dégâts | impact_etincelles + nappe cone_folie · 🔊 power_up_sound_v3.ogg |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ☝️ **Doigt de mort** — *Il pointe le doigt, et la mort suit.* | active | 29 PM | ennemi / magique / portée 6 | 3D10+7 dégâts | ombre · 🔊 17.mp3 |
| 🌑 **Marche des ombres** — *Il passe d'une ombre à l'autre.* | active | 29 PM | soi / portée 1 | saut 4 cases | ombre · 🔊 17.mp3 |
| 🌾 **Moisson d'âmes** — *Il moissonne la vie de la cible.* | active | 29 PM | ennemi / magique / portée 6 | 3D10+7 dégâts · drain 35 % (max 20) | drain · 🔊 17.mp3 |
| 😱 **Terreur** — *Une terreur glaciale paralyse l'ennemi.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · Vol -13 Ag -6 · 4 tours | spectre · 🔊 17.mp3 |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ☠️ **Fléau** — *Un fléau qui s'abat sur tout un groupe.* | active | 33 PM | ennemi / magique / portée 6 · cercle rayon 2 | 3D8+4 dégâts | poison · 🔊 17.mp3 |
| 📜 **Malédiction de la liche** — *Une malédiction qui empêche toute magie.* | active | 33 PM | ennemi / magique / portée 6 | 2D8+2 dégâts · régén PM -4 · 4 tours | ombre · 🔊 17.mp3 |
| 🧟 **Peau de cadavre** — *Sa peau devient froide et insensible.* | active | 15 PM + 5/round | soi / portée 1 | R +20 Vol +10 | tombeau · 🔊 17.mp3 |
| 💀 **Vol de mana** — *Il arrache la magie de la cible comme on arrache une âme.* | active | 33 PM | ennemi / magique / portée 6 | 2D8+2 dégâts · 2D8+1 aux PM | spectre · 🔊 17.mp3 |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🧛 **Banquet du vampire** — *Il paie de son sang un coup qui lui en rendra davantage.* | active | 37 PM | ennemi / magique / portée 6 | 5D10+10 dégâts · coûte 13 PV | drain · 🔊 17.mp3 |
| 👻 **Nuée de spectres** — *Des spectres tourbillonnent autour de lui et frappent.* | active | 37 PM | ennemi / magique / portée 6 · carre rayon 2 | 3D8+4 dégâts | spectre · 🔊 17.mp3 |
| ⚰️ **Rituel de mort** — *Un rituel long qui arrache la vie de la cible.* | active | 48 PM · ⏱ 3 PA | ennemi / magique / portée 6 | 5D10+10 dégâts | tombeau · 🔊 17.mp3 |
| 🌑 **Ténèbres dévorantes** — *Les ténèbres dévorent la cible.* | active | 37 PM | ennemi / magique / portée 6 | 4D10+9 dégâts | ombre · 🔊 17.mp3 |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ❄️ **Hiver éternel** — *Le froid de la tombe fige la cible.* | active | 40 PM | ennemi / magique / portée 6 | 3D8+2 dégâts · Ag -16 F -8 R -8 · 5 tours | givre · 🔊 17.mp3 |
| 💀 **Mot de mort** — *Un mot que seuls les morts connaissent.* | active | 40 PM | ennemi / magique / portée 6 | 5D10+12 dégâts | spectre · 🔊 17.mp3 |

## Paladin 🛡

### Niveau 1 — 1 existante(s) + 3 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🛡️ **Bouclier de la foi** — *Sa foi dresse devant lui un bouclier que l'on ne voit pas.* | active | 10 PM | soi / portée 1 | Vol +4 · esquive 6 · 3 tours | bouclier · 🔊 power_up_sound_v2.ogg |
| ⚖️ **Châtiment léger** — *Un éclat de lumière qui fait baisser les yeux du mécréant.* | active | 10 PM | ennemi / magique / portée 5 | 1D4 dégâts · Vol -6 · 3 tours | lumiere · 🔊 17.mp3 |
| ✨ **Coup béni** — *La masse s'abat, nimbée d'une lueur dorée.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | lame_sacree · 🔊 sword sound.wav |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦅 **Bond du croisé** — *Il s'élance au secours d'un frère d'armes.* | active | 12 PM | soi / portée 1 | saut 2 cases | saut · 🔊 swish_4.wav |
| 🗡️ **Bénédiction de l'acier** — *Il bénit l'arme d'un compagnon, qui frappe plus juste.* | active | 12 PM | allie / portée 4 | F +9 Vol +4 · 3 tours | aura_sacree · 🔊 power_up_sound_v0.ogg |
| ⚔️ **Frappe du juste** — *Un coup porté sans haine, mais sans pitié.* | active | 12 PM | ennemi / cc / portée 1 | 2D6+3 dégâts | lame_sacree · 🔊 sword sound.wav |
| 🙏 **Prière de guérison** — *Une prière courte, et une plaie se referme.* | active | 12 PM | allie / portée 4 | +18 PV | soin_sacre · 🔊 power_up_sound_v1.ogg |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ☀️ **Lumière aveuglante** — *Un éclat sacré qui brûle les yeux des impurs.* | active | 15 PM | ennemi / magique / portée 5 · cercle rayon 1 | 2D6+3 dégâts | lumiere_zone · 🔊 17.mp3 |
| 📜 **Serment de protection** — *Il prête serment, et sa garde ne faiblit plus.* | active | 8 PM + 3/round | soi / portée 1 | R +13 Vol +6 | bouclier · 🔊 power_up_sound_v2.ogg |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦁 **Aura de courage** — *Autour de lui, plus personne ne recule.* | active | 18 PM | soi / portée 1 · carre rayon 1 | Vol +8 R +4 · 3 tours | aura_sacree · 🔊 power_up_sound_v0.ogg |
| ⚖️ **Jugement** — *Un coup qui fait plier l'ennemi sous le poids de ses fautes.* | active | 18 PM | ennemi / cc / portée 1 | 1D8 dégâts · F -9 Vol -4 · 3 tours | lame_sacree · 🔊 sword sound.wav |
| 🔨 **Masse de lumière** — *La masse s'abat dans une gerbe d'étincelles dorées.* | active | 18 PM | ennemi / cc / portée 1 | 2D8+5 dégâts | lumiere · 🔊 17.mp3 |
| ⛑️ **Soins du champ de bataille** — *Il impose les mains et laisse la grâce agir.* | active | 18 PM | allie / portée 4 | régén PV +3 · 4 tours | soin_sacre · 🔊 power_up_sound_v1.ogg |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🔥 **Brûlure sacrée** — *Une lumière qui continue de brûler longtemps après le coup.* | active | 21 PM | ennemi / magique / portée 5 | 1D8+2 dégâts · régén PV -5 · 4 tours | lumiere · 🔊 17.mp3 |
| 🐎 **Charge sainte** — *Il franchit la mêlée, porté par sa foi.* | active | 21 PM | soi / portée 1 | saut 3 cases | aura_sacree · 🔊 power_up_sound_v0.ogg |
| ✝️ **Frappe du croisé** — *Un coup qui porte la croix gravée dans le métal.* | active | 21 PM | ennemi / cc / portée 1 | 3D8+4 dégâts | lame_sacree · 🔊 sword sound.wav |
| 🛡️ **Égide** — *Il étend sa protection sur un compagnon menacé.* | active | 21 PM | allie / portée 4 | R +13 · 4 tours | bouclier · 🔊 power_up_sound_v2.ogg |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🙌 **Mains de lumière** — *La lumière jaillit de ses mains et soigne ceux qui l'entourent.* | active | 25 PM | allie / portée 4 · cercle rayon 1 | +18 PV | soin_vague · 🔊 power_up_sound_v1.ogg |
| 🔨 **Marteau de justice** — *Un coup large qui frappe tous ceux qui se dressent devant lui.* | active | 25 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 3D6+6 dégâts | lame_sacree · 🔊 sword sound.wav |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🚫 **Bannissement** — *Il chasse la magie impie hors du corps ennemi.* | active | 29 PM | ennemi / magique / portée 5 | 2D6+4 dégâts · 2D8 aux PM | lumiere_zone · 🔊 17.mp3 |
| 💫 **Grâce restauratrice** — *Une grâce qui relève les plus touchés.* | active | 29 PM | allie / portée 4 | +34 PV | soin_sacre · 🔊 power_up_sound_v1.ogg |
| 🌅 **Lame de l'aube** — *Une lame qui brille comme le soleil levant.* | active | 29 PM | ennemi / cc / portée 1 | 3D10+7 dégâts | lumiere · 🔊 17.mp3 |
| 🏰 **Rempart sacré** — *Une muraille de foi se dresse autour de lui.* | active | 13 PM + 4/round | soi / portée 1 | R +19 Vol +9 | aura_sacree · 🔊 power_up_sound_v0.ogg |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 👼 **Bond de l'ange** — *Il descend sur le champ de bataille comme un ange.* | active | 33 PM | soi / portée 1 | saut 4 cases | descente_celeste · 🔊 power_up_sound_v0.ogg |
| ⚡ **Colère divine** — *La lumière tombe du ciel sur les ennemis rassemblés.* | active | 33 PM | ennemi / magique / portée 5 · cercle rayon 2 | 3D8+4 dégâts | lumiere_zone · 🔊 17.mp3 |
| 🔥 **Purge** — *Une flamme sacrée qui ronge l'impur.* | active | 33 PM | ennemi / magique / portée 5 | 2D8+2 dégâts · régén PV -6 · 4 tours | lumiere · 🔊 17.mp3 |
| 🤝 **Vœu du protecteur** — *Il jure de protéger un compagnon, et celui-ci se sent invincible.* | active | 33 PM | allie / portée 4 | R +17 Vol +8 · 4 tours | lien · 🔊 power_up_sound_v1.ogg |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ✝️ **Croisade** — *Il lève sa masse, et la troupe entière marche avec lui.* | active | 37 PM | soi / portée 1 · carre rayon 2 | F +13 Vol +6 · 5 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| ⛓️ **Pénitence** — *Le mécréant ploie sous le poids de ses péchés.* | active | 37 PM | ennemi / magique / portée 5 | 2D8+4 dégâts · F -15 Ag -7 · 5 tours | lumiere · 🔊 17.mp3 |
| 🌊 **Vague sainte** — *Une vague de lumière tranchante qui s'ouvre devant lui.* | active | 37 PM | ennemi / cc / portée 1 · cone longueur 2 | 3D10+8 dégâts | impact_eclat_dore + nappe cone_tueur_demon · 🔊 sword sound.wav |
| 🗡️ **Épée de la foi** — *Le coup d'un homme qui ne doute plus.* | active | 37 PM | ennemi / cc / portée 1 | 4D10+9 dégâts | lame_sacree · 🔊 sword sound.wav |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⚖️ **Jugement dernier** — *Le coup qui pèse l'âme avant de la frapper.* | active | 40 PM | ennemi / cc / portée 1 | 5D10+12 dégâts | lumiere · 🔊 17.mp3 |
| 🌟 **Miracle** — *Un miracle, et ceux qui tombaient se relèvent.* | active | 40 PM | allie / portée 4 · cercle rayon 1 | +27 PV | aura_sacree · 🔊 power_up_sound_v0.ogg |

## Prêtre ✝

### Niveau 1 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🕊️ **Bénédiction** — *Il bénit un compagnon, qui se sent plus fort.* | active | 10 PM | allie / portée 4 | Vol +8 R +4 · 3 tours | aura_sacree · 🔊 power_up_sound_v0.ogg |
| ✨ **Lumière sainte** — *Un rai de lumière qui brûle l'impur.* | active | 10 PM | ennemi / magique / portée 6 | 1D8+3 dégâts | lumiere · 🔊 17.mp3 |
| 🙏 **Prière de soin** — *Une prière murmurée, et la plaie se referme.* | active | 10 PM | allie / portée 4 | +16 PV | soin_sacre · 🔊 power_up_sound_v1.ogg |
| ☝️ **Réprimande** — *Un mot sévère qui fait plier l'ennemi.* | active | 10 PM | ennemi / magique / portée 6 | 1D4 dégâts · Vol -6 · 3 tours | lumiere · 🔊 17.mp3 |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💡 **Clarté** — *Il éclaire l'esprit d'un compagnon et lui rend son énergie.* | active | 12 PM | allie / portée 4 | +10 PM | meditation · 🔊 power_up_sound_v1.ogg |
| 🔥 **Feu sacré** — *Une flamme sacrée qui brûle longtemps.* | active | 12 PM | ennemi / magique / portée 6 | 1D6 dégâts · régén PV -3 · 3 tours | lumiere · 🔊 17.mp3 |
| 💫 **Grâce** — *Une grâce qui soigne lentement mais sûrement.* | active | 12 PM | allie / portée 4 | régén PV +2 · 4 tours | soin_sacre · 🔊 power_up_sound_v1.ogg |
| ⛪ **Sanctuaire** — *Il se recueille, et une lumière le protège.* | active | 7 PM + 2/round | soi / portée 1 | R +12 Vol +6 | bouclier · 🔊 power_up_sound_v2.ogg |

### Niveau 3 — 3 existante(s) + 1 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⭕ **Cercle de guérison** — *Un cercle de lumière soigne tous ceux qui s'y tiennent.* | active | 15 PM | allie / portée 4 · cercle rayon 1 | +12 PV | soin_vague · 🔊 power_up_sound_v1.ogg |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🌅 **Lumière de l'aube** — *Une lumière aveuglante sur le groupe ennemi.* | active | 18 PM | ennemi / magique / portée 6 · cercle rayon 1 | 2D6+5 dégâts | lumiere_zone · 🔊 17.mp3 |
| 🛡️ **Protection divine** — *Un bouclier de lumière sur un compagnon.* | active | 18 PM | allie / portée 4 | R +12 · 3 tours | bouclier · 🔊 power_up_sound_v2.ogg |
| 💧 **Purification** — *Il purifie la magie impie de la cible.* | active | 18 PM | ennemi / magique / portée 6 | 1D8 dégâts · 2D6 aux PM | lumiere · 🔊 17.mp3 |
| 🌟 **Éclat divin** — *Un éclat de pure divinité.* | active | 18 PM | ennemi / magique / portée 6 | 2D8+5 dégâts | lumiere · 🔊 17.mp3 |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⛓️ **Chaînes de lumière** — *Des chaînes de lumière entravent l'ennemi.* | active | 21 PM | ennemi / magique / portée 6 | 1D8+2 dégâts · Ag -10 F -5 · 4 tours | lumiere · 🔊 17.mp3 |
| ❤️‍🩹 **Guérison majeure** — *Une prière puissante qui referme les blessures graves.* | active | 21 PM | allie / portée 4 | +26 PV | soin_sacre · 🔊 power_up_sound_v1.ogg |
| 🎶 **Hymne** — *Un hymne qui fortifie tous ceux qui l'entendent.* | active | 21 PM | soi / portée 1 · carre rayon 1 | Vol +9 R +4 · 4 tours | chant · 🔊 power_up_sound_v1.ogg |
| 🕊️ **Saut de foi** — *Il s'en remet à la foi, et elle le porte.* | active | 21 PM | soi / portée 1 | saut 3 cases | aura_sacree · 🔊 power_up_sound_v0.ogg |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ☀️ **Colonne de lumière** — *Une colonne de lumière s'abat sur la cible.* | active | 25 PM | ennemi / magique / portée 6 | 3D8+6 dégâts | lumiere_zone · 🔊 17.mp3 |
| ⛲ **Source de grâce** — *Une source de grâce qui coule sans fin.* | active | 25 PM | allie / portée 4 | régén PV +3 · 5 tours | source · 🔊 power_up_sound_v1.ogg |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⚡ **Châtiment divin** — *Le ciel frappe le groupe ennemi.* | active | 29 PM | ennemi / magique / portée 6 · cercle rayon 2 | 2D8+6 dégâts | lumiere_zone · 🔊 17.mp3 |
| 📿 **Exorcisme** — *Il chasse les esprits impurs, et la magie avec eux.* | active | 29 PM | ennemi / magique / portée 6 | 2D6+4 dégâts · régén PM -4 · 4 tours | lumiere · 🔊 17.mp3 |
| 🙏 **Prière de masse** — *Toute l'assemblée est soignée d'une seule prière.* | active | 29 PM | allie / portée 4 · cercle rayon 1 | +20 PV | soin_vague · 🔊 power_up_sound_v1.ogg |
| 🛡️ **Rempart de la foi** — *Sa foi devient un rempart impénétrable.* | active | 13 PM + 4/round | soi / portée 1 | R +19 Vol +9 | aura_sacree · 🔊 power_up_sound_v0.ogg |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🕊️ **Bénédiction de masse** — *Il bénit tout le groupe.* | active | 33 PM | soi / portée 1 · carre rayon 2 | Vol +12 F +6 · 4 tours | aura_sacree · 🔊 power_up_sound_v0.ogg |
| 💫 **Grâce de l'esprit** — *Il restaure l'énergie d'un compagnon par la prière.* | active | 33 PM | allie / portée 4 | +22 PM | soin_sacre · 🔊 power_up_sound_v1.ogg |
| ⚖️ **Jugement céleste** — *Le ciel juge, et le ciel frappe.* | active | 33 PM | ennemi / magique / portée 6 | 4D10+6 dégâts | lumiere · 🔊 17.mp3 |
| 🤫 **Silence sacré** — *Un silence qui coupe l'ennemi de ses forces.* | active | 33 PM | ennemi / magique / portée 6 | 2D8+2 dégâts · Vol -14 Int -7 · 4 tours | lumiere · 🔊 17.mp3 |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🚫 **Anathème** — *Il frappe la cible d'anathème et la coupe de sa magie.* | active | 37 PM | ennemi / magique / portée 6 | 2D8+4 dégâts · 2D8+2 aux PM | lumiere_zone · 🔊 17.mp3 |
| ☀️ **Lumière purificatrice** — *Une prière longue, et une lumière qui purifie tout.* | active | 48 PM · ⏱ 3 PA | ennemi / magique / portée 6 | 5D10+10 dégâts | lumiere_zone · 🔊 17.mp3 |
| ❤️ **Résurgence** — *Une guérison presque miraculeuse.* | active | 37 PM | allie / portée 4 | +42 PV | soin_vague · 🔊 power_up_sound_v1.ogg |
| 🌟 **Vœu de lumière** — *Un vœu qui rend un compagnon presque invincible.* | active | 37 PM | allie / portée 4 | R +18 Vol +9 · 5 tours | aura_sacree · 🔊 power_up_sound_v0.ogg |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 👼 **Apothéose** — *Une lumière divine qui relève tous les blessés.* | active | 40 PM | allie / portée 4 · cercle rayon 1 | +27 PV | aura_sacree · 🔊 power_up_sound_v0.ogg |
| ⚡ **Courroux du ciel** — *La colère du ciel s'abat sur l'ennemi.* | active | 40 PM | ennemi / magique / portée 6 · cercle rayon 2 | 3D10+6 dégâts | lumiere_zone · 🔊 17.mp3 |

## Répurgateur 🔱

### Niveau 1 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🗡️ **Lame d'argent** — *L'argent mord la chair maudite.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | lame · 🔊 sword sound.wav |
| 🧂 **Sel et cendre** — *Une poignée de sel béni jetée au visage du monstre.* | active | 10 PM | ennemi / cc / portée 1 | 1D4 dégâts · Vol -6 · 3 tours | poudre · 🔊 swish_2.wav |
| 🔱 **Signe noir** — *Un signe tracé dans l'air, qui aspire la magie de la cible.* | active | 10 PM | ennemi / magique / portée 5 | 1D4 dégâts · 1D6 aux PM | demon_buff · 🔊 power_up_sound_v3.ogg |
| 👁️ **Œil du chasseur de sorcières** — *Il voit ce que la créature voudrait cacher.* | active | 10 PM | soi / portée 1 | Vol +8 Int +4 · 4 tours | marque · 🔊 17.mp3 |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🪵 **Coup de pieu** — *Le pieu cherche le cœur, comme il se doit.* | active | 12 PM | ennemi / cc / portée 1 | 2D6+3 dégâts | saignee · 🔊 sword sound.wav |
| 💧 **Eau lustrale** — *Une fiole d'eau bénite qui ronge la créature.* | active | 12 PM | ennemi / cd / portée 4 | 1D6 dégâts · régén PV -3 · 3 tours | eau · 🔊 swish_3.wav |
| 👣 **Pas du traqueur** — *Il surgit derrière la proie qu'il pistait.* | active | 12 PM | soi / portée 1 | saut 2 cases | furtif · 🔊 swish_2.wav |
| 🩸 **Sang contre sang** — *Il paie de son sang le droit de frapper le maudit.* | active | 12 PM | ennemi / cc / portée 1 | 2D8+4 dégâts · coûte 5 PV | rage · 🔊 power_up_sound_v3.ogg |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⛓️ **Chaînes d'argent** — *Des chaînes d'argent qui brûlent la peau des maudits.* | active | 15 PM | ennemi / cc / portée 1 | 1D6+1 dégâts · Ag -8 F -4 · 3 tours | marque · 🔊 17.mp3 |
| 🔥 **Flamme noire** — *Une flamme infernale retournée contre ses semblables.* | active | 15 PM | ennemi / magique / portée 5 | 2D8+3 dégâts | projectile_infernal · 🔊 foom_0.wav |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ✝️ **Croix renversée** — *Un coup porté avec la garde en croix.* | active | 18 PM | ennemi / cc / portée 1 | 2D8+5 dégâts | lame_sacree · 🔊 sword sound.wav |
| 📿 **Exorcisme mineur** — *Une prière qui arrache au maudit une part de sa force.* | active | 18 PM | ennemi / magique / portée 5 | 1D8 dégâts · 2D6 aux PM | lumiere · 🔊 17.mp3 |
| 🛡️ **Garde du chasseur** — *Une garde forgée face aux griffes et aux crocs.* | active | 9 PM + 3/round | soi / portée 1 | Vol +15 R +7 | demon_buff · 🔊 power_up_sound_v3.ogg |
| 💨 **Soufre** — *Une bouffée de soufre qui suffoque tout le nid.* | active | 18 PM | ennemi / magique / portée 5 · cercle rayon 1 | 2D6+5 dégâts | soufre · 🔊 foom_0.wav |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🏹 **Carreau béni** — *Un carreau d'arbalète trempé dans l'eau bénite.* | active | 21 PM | ennemi / cd / portée 8 | 3D8+4 dégâts | tir · 🔊 Bow.wav |
| 🔥 **Fouet de flammes** — *Une lanière de feu qui claque devant lui.* | active | 21 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 2D8+5 dégâts | feu · 🔊 foom_0.wav |
| 🎯 **Marque d'argent** — *Une marque qui empêche le maudit de puiser dans ses forces.* | active | 21 PM | ennemi / cc / portée 1 | 1D8+2 dégâts · régén PM -3 · 4 tours | marque · 🔊 17.mp3 |
| 😈 **Pacte inversé** — *Il emprunte au démon sa force pour mieux le tuer.* | active | 21 PM | soi / portée 1 | F +13 Vol +6 · 5 tours | demon_buff · 🔊 power_up_sound_v3.ogg |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 💀 **Coup du tueur de monstres** — *Le coup qu'on garde pour la créature qui a tué le village.* | active | 25 PM | ennemi / cc / portée 1 | 3D8+6 dégâts | saignee · 🔊 sword sound.wav |
| 🌋 **Haleine de l'abîme** — *Il souffle le feu de l'abîme sur les créatures.* | active | 25 PM | ennemi / cc / portée 1 · cone longueur 3 | 2D8+4 dégâts | impact_brulure + nappe cone_souffle_feu · 🔊 foom_0.wav |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🦇 **Bond de la chasse** — *Il bondit sur la créature avant qu'elle ne s'envole.* | active | 29 PM | soi / portée 1 | saut 4 cases | saut · 🔊 swish_4.wav |
| 🚫 **Brise-sortilège** — *Il brise la magie du sorcier comme on brise un os.* | active | 29 PM | ennemi / cc / portée 1 | 2D6+4 dégâts · 2D8 aux PM | arcane · 🔊 17.mp3 |
| ⚔️ **Lame sanctifiée** — *Une lame consacrée qui ne connaît qu'une cible.* | active | 29 PM | ennemi / cc / portée 1 | 3D10+7 dégâts | lame_sacree · 🔊 sword sound.wav |
| 📜 **Malédiction de l'inquisiteur** — *Une malédiction qui ronge le maudit de l'intérieur.* | active | 29 PM | ennemi / magique / portée 5 | 2D6+4 dégâts · régén PV -6 · 4 tours | poison · 🔊 17.mp3 |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🩸 **Endurance du traqueur** — *Des nuits de traque ont fait de lui un homme qu'on ne fatigue pas.* | active | 15 PM + 5/round | soi / portée 1 | R +20 Vol +10 | rage · 🔊 power_up_sound_v3.ogg |
| 🔥 **Feu de l'enfer retourné** — *Il retourne le feu des démons contre leur nid.* | active | 33 PM | ennemi / magique / portée 5 · cercle rayon 2 | 3D8+4 dégâts | explosion_feu · 🔊 foom_0.wav |
| ❤️ **Pieu au cœur** — *Le pieu s'enfonce, et la vie volée de la créature passe en lui.* | active | 33 PM | ennemi / cc / portée 1 | 4D10+6 dégâts · drain 35 % (max 20) | saignee · 🔊 sword sound.wav |
| 🔱 **Sceau d'entrave** — *Un sceau démoniaque qui lie le monstre à la terre.* | active | 33 PM | ennemi / magique / portée 5 | 2D8+2 dégâts · Ag -14 Vol -7 · 4 tours | demon_buff · 🔊 power_up_sound_v3.ogg |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⚔️ **Exécution du maudit** — *La sentence de l'inquisition, portée à la lame.* | active | 37 PM | ennemi / cc / portée 1 | 4D10+9 dégâts | lame_sacree · 🔊 sword sound.wav |
| 🔥 **Purification par le feu** — *Le bûcher, sans le bûcher.* | active | 37 PM | ennemi / magique / portée 5 | 2D8+4 dégâts · régén PV -7 · 5 tours | feu · 🔊 foom_0.wav |
| 📿 **Rituel d'exorcisme** — *Un rituel long, qui arrache le démon de sa chair.* | active | 48 PM · ⏱ 3 PA | ennemi / magique / portée 5 | 5D10+10 dégâts | lumiere_zone · 🔊 17.mp3 |
| 🌀 **Tourbillon d'argent** — *Ses lames d'argent tournent autour de lui.* | active | 37 PM | ennemi / cc / portée 1 · carre rayon 1 | 3D8+6 dégâts | balayage · 🔊 swish_3.wav |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 😈 **Fléau des démons** — *La flamme qui a chassé les démons de trois provinces.* | active | 40 PM | ennemi / magique / portée 5 | 5D10+12 dégâts | projectile_infernal · 🔊 foom_0.wav |
| 💔 **Pacte rompu** — *Il rompt le pacte qui nourrit le maudit.* | active | 40 PM | ennemi / cc / portée 1 | 3D8+2 dégâts · 3D8 aux PM | demon_buff · 🔊 power_up_sound_v3.ogg |

## Templier ⚜️

### Niveau 1 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⚔️ **Coup réglementaire** — *Un coup tel qu'on l'enseigne à l'ordre : propre et efficace.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | lame · 🔊 sword sound.wav |
| 📏 **Discipline du rang** — *Il rectifie sa posture et respire au rythme de l'ordre.* | active | 10 PM | soi / portée 1 | R +8 Vol +4 · 4 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| 🛡️ **Garde de l'ordre** — *La garde réglementaire, haute et serrée.* | active | 10 PM | soi / portée 1 | R +4 · esquive 6 · 3 tours | garde · 🔊 sword sound.wav |
| ✋ **Ordre de halte** — *Un commandement sec qui fige l'adversaire.* | active | 10 PM | ennemi / cc / portée 1 | 1D4 dégâts · Ag -6 · 3 tours | garde · 🔊 sword sound.wav |

### Niveau 2 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🛡️ **Bouclier repoussant** — *Un coup de bouclier qui fait reculer l'ennemi.* | active | 12 PM | ennemi / cc / portée 1 | 1D6 dégâts · F -7 Ag -3 · 3 tours | coup_lourd · 🔊 melee sound.wav |
| 🗡️ **Frappe du gardien** — *Le coup du gardien de porte : économe et sûr.* | active | 12 PM | ennemi / cc / portée 1 | 2D6+3 dégâts | lame · 🔊 sword sound.wav |
| 🚶 **Pas de la patrouille** — *Il couvre la distance au pas de charge réglementaire.* | active | 12 PM | soi / portée 1 | saut 2 cases | saut · 🔊 swish_4.wav |
| ᚱ **Rune de résistance** — *Il trace une rune sur l'armure d'un compagnon.* | active | 12 PM | allie / portée 4 | R +9 · 3 tours | enchantement · 🔊 power_up_sound_v0.ogg |

### Niveau 3 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🚫 **Annulation** — *Une formule de l'ordre qui dissipe la magie adverse.* | active | 15 PM | ennemi / magique / portée 5 | 1D6+1 dégâts · 1D8+1 aux PM | arcane · 🔊 17.mp3 |
| 🧱 **Ligne de l'ordre** — *Une taille horizontale qui frappe le premier rang adverse.* | active | 15 PM | ennemi / cc / portée 1 · rectangle longueur 1 largeur 3 | 2D6+3 dégâts | lame · 🔊 sword sound.wav |

### Niveau 4 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⛓️ **Chaînes de l'ordre** — *Des chaînes d'énergie entravent le malfaiteur.* | active | 18 PM | ennemi / magique / portée 5 | 1D8 dégâts · Ag -9 F -4 · 3 tours | arcane · 🔊 17.mp3 |
| 🔥 **Lame enflammée** — *Une formule de bataille, et l'épée s'embrase.* | active | 18 PM | ennemi / cc / portée 1 | 2D8+5 dégâts | feu · 🔊 foom_0.wav |
| 📯 **Ordre de bataille** — *Il donne l'ordre, et la ligne se reforme.* | active | 18 PM | soi / portée 1 · carre rayon 1 | R +8 F +4 · 3 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| 🔰 **Sceau de garde** — *Un sceau runique qui renforce la garde tant qu'il le tient.* | active | 9 PM + 3/round | soi / portée 1 | R +15 Vol +7 | bouclier · 🔊 power_up_sound_v2.ogg |

### Niveau 5 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🔨 **Coup de l'inquisition** — *Un coup qui porte la sentence de l'ordre.* | active | 21 PM | ennemi / cc / portée 1 | 3D8+4 dégâts | lame_sacree · 🔊 sword sound.wav |
| 💥 **Explosion runique** — *Une rune gravée explose au milieu des ennemis.* | active | 21 PM | ennemi / magique / portée 5 · cercle rayon 1 | 2D8+5 dégâts | explosion_feu · 🔊 foom_0.wav |
| 🔥 **Fer rouge** — *Une lame chauffée à blanc qui marque l'ennemi.* | active | 21 PM | ennemi / cc / portée 1 | 1D8+2 dégâts · régén PV -5 · 4 tours | feu · 🔊 foom_0.wav |
| 🏰 **Mur de l'ordre** — *Il étend sa garde sur un compagnon.* | active | 21 PM | allie / portée 4 | R +13 Vol +6 · 4 tours | bouclier · 🔊 power_up_sound_v2.ogg |

### Niveau 6 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| ⚔️ **Taille du gardien des temples** — *Un coup appris dans le cloître, pour défendre l'autel.* | active | 25 PM | ennemi / cc / portée 1 | 3D8+6 dégâts | lame · 🔊 sword sound.wav |
| 🛡️ **Égide runique** — *Des runes s'allument sur son armure et la rendent impénétrable.* | active | 12 PM + 4/round | soi / portée 1 | R +17 | enchantement · 🔊 power_up_sound_v0.ogg |

### Niveau 7 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🚷 **Interdit** — *Une parole de l'ordre interdit à l'ennemi de bouger.* | active | 29 PM | ennemi / magique / portée 5 | 2D6+4 dégâts · Ag -13 Int -6 · 4 tours | arcane · 🔊 17.mp3 |
| ⚡ **Lame de foudre** — *L'épée crépite d'éclairs au moment du coup.* | active | 29 PM | ennemi / cc / portée 1 | 3D10+7 dégâts | foudre · 🔊 17.mp3 |
| 🩹 **Restauration de l'ordre** — *Une prière de l'ordre qui remet un frère sur pied.* | active | 29 PM | allie / portée 4 | +34 PV | soin_sacre · 🔊 power_up_sound_v1.ogg |
| 🌀 **Rotation du templier** — *Il pivote, épée et bouclier, et frappe tout autour.* | active | 29 PM | ennemi / cc / portée 1 · carre rayon 1 | 2D8+6 dégâts | balayage · 🔊 swish_3.wav |

### Niveau 8 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🏯 **Bastion** — *Il fait de ses compagnons un bastion.* | active | 33 PM | soi / portée 1 · carre rayon 2 | R +12 Vol +6 · 4 tours | bouclier · 🔊 power_up_sound_v2.ogg |
| ✨ **Dissipation** — *Il défait la magie de l'ennemi fil à fil.* | active | 33 PM | ennemi / magique / portée 5 | 2D8+2 dégâts · 2D8+1 aux PM | arcane · 🔊 17.mp3 |
| 🔥 **Feu de l'autel** — *Un souffle de flammes sacrées s'échappe de sa lame.* | active | 33 PM | ennemi / cc / portée 1 · cone longueur 3 | 3D8+4 dégâts | impact_brulure + nappe cone_souffle_feu · 🔊 foom_0.wav |
| ⚖️ **Jugement de l'ordre** — *La sentence tombe sans appel.* | active | 33 PM | ennemi / cc / portée 1 | 4D10+6 dégâts | lame_sacree · 🔊 sword sound.wav |

### Niveau 9 — 0 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🛡️ **Garde inflexible** — *Il ne bouge plus d'un pouce, quoi qu'il arrive.* | active | 16 PM + 5/round | soi / portée 1 | R +21 F +10 | garde · 🔊 sword sound.wav |
| 🦅 **Saut du gardien** — *Il bondit pour couvrir le point faible de la ligne.* | active | 37 PM | soi / portée 1 | saut 5 cases | saut · 🔊 swish_4.wav |
| 🌩️ **Tempête runique** — *Les runes s'embrasent et la foudre tombe sur les ennemis.* | active | 37 PM | ennemi / magique / portée 5 · cercle rayon 2 | 3D8+6 dégâts | foudre · 🔊 17.mp3 |
| 🗡️ **Épée de l'institution** — *Le coup qui fait respecter la loi.* | active | 37 PM | ennemi / cc / portée 1 | 4D10+9 dégâts | lame · 🔊 sword sound.wav |

### Niveau 10 — 2 existante(s) + 2 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🏰 **Rempart de la cité** — *Tant qu'il est debout, la cité ne tombera pas.* | active | 40 PM | soi / portée 1 · carre rayon 2 | R +14 Vol +7 · 5 tours | aura_bataille · 🔊 power_up_sound_v0.ogg |
| ⚔️ **Sentence capitale** — *L'ordre a jugé ; l'épée exécute.* | active | 40 PM | ennemi / cc / portée 1 | 5D10+12 dégâts | lame_sacree · 🔊 sword sound.wav |

## Voleur 🔑

### Niveau 1 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🍀 **Chance du gredin** — *Tout lui réussit aujourd'hui, et il le sait.* | active | 10 PM | soi / portée 1 | Ch +8 Ag +4 · 4 tours | furtif · 🔊 swish_2.wav |
| 🦵 **Coup bas** — *Un coup de genou là où ça fait mal.* | active | 10 PM | ennemi / cc / portée 1 | 1D4 dégâts · Ag -6 · 3 tours | coup_lourd · 🔊 melee sound.wav |
| 💨 **Filer à l'anglaise** — *Il est là, puis il n'y est plus.* | active | 10 PM | soi / portée 1 | saut 2 cases | furtif · 🔊 swish_2.wav |
| 🔪 **Lame de poche** — *Un canif sorti de nulle part.* | active | 10 PM | ennemi / cc / portée 1 | 1D8+3 dégâts | lame · 🔊 sword sound.wav |
| 🏖️ **Sable aux yeux** — *Une poignée de sable, et l'ennemi frappe au hasard.* | active | 10 PM | ennemi / cc / portée 1 | 1D4 dégâts · Ag -6 Int -3 · 3 tours | poudre · 🔊 swish_2.wav |

### Niveau 2 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🪄 **Doigts de fée** — *Il dénoue une bourse sans que le nœud ne s'en aperçoive.* | passive | — | permanent | Ag +2 | — |
| 💰 **Bourse lestée** — *Une bourse pleine de plomb, au bout d'une lanière.* | active | 12 PM | ennemi / cc / portée 1 | 2D6+3 dégâts | poing · 🔊 melee sound.wav |
| 🔪 **Couteaux de lancer** — *Trois couteaux, trois cibles.* | active | 12 PM | ennemi / cd / portée 4 · rectangle longueur 1 largeur 3 | 1D8+3 dégâts | lame · 🔊 sword sound.wav |
| 🦶 **Croc-en-jambe** — *Un pied qui traîne, et le colosse s'étale.* | active | 12 PM | ennemi / cc / portée 1 | 1D6 dégâts · Ag -7 · 3 tours | coup_lourd · 🔊 melee sound.wav |
| 🤸 **Esquive du coupe-bourse** — *Il roule sous la table et ressort de l'autre côté.* | active | 12 PM | soi / portée 1 | Ag +4 · esquive 7 · 3 tours | furtif · 🔊 swish_2.wav |
| 🗡️ **Surin** — *Un coup vicieux, porté de près.* | active | 12 PM | ennemi / cc / portée 1 | 2D6+3 dégâts | saignee · 🔊 sword sound.wav |

### Niveau 3 — 3 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🧱 **Coup du pavé** — *Ce qui traîne dans la rue fait une très bonne arme.* | active | 15 PM | ennemi / cc / portée 1 | 2D8+3 dégâts | coup_lourd · 🔊 melee sound.wav |
| 🫳 **Pickpocket de combat** — *Il vole jusqu'au souffle de son adversaire.* | active | 15 PM | ennemi / cc / portée 1 | 1D6+1 dégâts · 1D8+1 aux PM | furtif · 🔊 swish_2.wav |
| 🌶️ **Poivre des quais** — *Une poignée de poivre noir qui fait pleurer les plus durs.* | active | 15 PM | ennemi / cc / portée 1 | 1D6+1 dégâts · Ag -8 Vol -4 · 3 tours | poudre · 🔊 swish_2.wav |
| 🏚️ **Saut de toit** — *Il connaît chaque toit de la ville par cœur.* | active | 15 PM | soi / portée 1 | saut 3 cases | saut · 🔊 swish_4.wav |

### Niveau 4 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🐭 **Pas de souris** — *Dans les caves et les égouts, il est chez lui.* | passive | — | permanent | furtivité 7 (sous-terrain, catacombe, donjon, grotte, couvert, humide, mine) | — |
| 💨 **Bombe fumigène** — *Un éclat de verre, un nuage âcre, et la confusion.* | active | 18 PM | ennemi / cc / portée 1 · cercle rayon 1 | 2D6+5 dégâts | poudre · 🔊 swish_2.wav |
| 🪢 **Cordelette** — *Une cordelette qui entrave les chevilles.* | active | 18 PM | ennemi / cc / portée 1 | 1D8 dégâts · Ag -9 · 3 tours | saignee · 🔊 sword sound.wav |
| 😏 **Gouaille** — *Un bon mot lancé au bon moment : il reprend confiance.* | active | 18 PM | soi / portée 1 | Cha +12 Ch +6 · 4 tours | chant · 🔊 power_up_sound_v1.ogg |
| 🗡️ **Lame cachée** — *La lame sort de la manche au dernier moment.* | active | 18 PM | ennemi / cc / portée 1 | 2D8+5 dégâts | lame · 🔊 sword sound.wav |
| 😈 **Sale coup** — *Il se blesse en frappant, mais le coup en vaut la peine.* | active | 18 PM | ennemi / cc / portée 1 | 3D8+5 dégâts · coûte 7 PV | saignee · 🔊 sword sound.wav |

### Niveau 5 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🎲 **Chance insolente** — *Les dés tombent toujours du bon côté pour lui.* | passive | — | permanent | Ch +3 | — |
| 🐇 **Coup du lapin** — *Un coup sec à la nuque.* | active | 21 PM | ennemi / cc / portée 1 | 3D8+4 dégâts | coup_lourd · 🔊 melee sound.wav |
| 🐸 **Fiel de crapaud** — *Une lame trempée dans un fiel que vend l'apothicaire véreux.* | active | 21 PM | ennemi / cc / portée 1 | 1D8+2 dégâts · régén PV -5 · 4 tours | poison · 🔊 17.mp3 |
| 📌 **Pluie de clous** — *Il jette une poignée de clous rouillés sous les pieds ennemis.* | active | 21 PM | ennemi / cc / portée 1 · cercle rayon 1 | 2D8+5 dégâts | lame · 🔊 sword sound.wav |
| 🤸 **Roulade** — *Une roulade sous les jambes de l'ennemi.* | active | 21 PM | soi / portée 1 | saut 3 cases | saut · 🔊 swish_4.wav |
| 🫳 **Vol à l'arraché** — *Il arrache à sa victime ce qui lui restait de forces.* | active | 21 PM | ennemi / cc / portée 1 | 1D8+2 dégâts · 2D6+1 aux PM | furtif · 🔊 swish_2.wav |

### Niveau 6 — 3 existante(s) + 4 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🪑 **Bouclier de fortune** — *Un tabouret, une planche, un couvercle : tout lui sert de bouclier.* | active | 12 PM + 4/round | soi / portée 1 | Ag +17 R +8 | garde · 🔊 sword sound.wav |
| 🌫️ **Cendre au visage** — *Une poignée de cendre chaude, en plein visage.* | active | 25 PM | ennemi / cc / portée 1 | 2D6+2 dégâts · Ag -12 Int -6 · 4 tours | poudre · 🔊 swish_2.wav |
| 🔪 **Coup de surin** — *Un coup vif dans le flanc, sans prévenir.* | active | 25 PM | ennemi / cc / portée 1 | 3D8+6 dégâts | saignee · 🔊 sword sound.wav |
| 🌀 **Tourbillon de coutelas** — *Il fait tournoyer ses lames dans la ruelle étroite.* | active | 25 PM | ennemi / cc / portée 1 · carre rayon 1 | 2D8+4 dégâts | lame · 🔊 sword sound.wav |

### Niveau 7 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🎭 **Feinte de rue** — *Il a appris l'escrime dans les ruelles, et ça se voit.* | passive | — | permanent | esquive 6 | — |
| 🔨 **Coup de crosse** — *Un coup derrière l'oreille, qui fait voir trente-six chandelles.* | active | 29 PM | ennemi / cc / portée 1 | 2D6+4 dégâts · Int -13 Ag -6 · 4 tours | coup_lourd · 🔊 melee sound.wav |
| 🧗 **Grimpe éclair** — *Une gouttière, un balcon, et il est hors d'atteinte.* | active | 29 PM | soi / portée 1 | saut 4 cases | saut · 🔊 swish_4.wav |
| 🗡️ **Lame du coupe-jarret** — *La lame qui fait la réputation du quartier.* | active | 29 PM | ennemi / cc / portée 1 | 3D10+7 dégâts | saignee · 🔊 sword sound.wav |
| 🧪 **Mauvaise fiole** — *Une fiole volée chez un alchimiste, qui ronge l'esprit.* | active | 29 PM | ennemi / cc / portée 1 | 2D6+4 dégâts · régén PM -4 · 4 tours | poison · 🔊 17.mp3 |
| 🕸️ **Réseau d'informateurs** — *Il souffle à un compagnon ce qu'il a appris sur l'ennemi.* | active | 29 PM | allie / portée 4 | Int +16 Ag +8 · 4 tours | chant · 🔊 power_up_sound_v1.ogg |

### Niveau 8 — 1 existante(s) + 6 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 👑 **Roi des ruelles** — *Dans la ville basse, chaque pavé lui obéit.* | passive | — | permanent | Ag +4 | — |
| 📌 **Chausse-trappe lancée** — *Des pointes semées sous les pas, qui font boiter.* | active | 33 PM | ennemi / cc / portée 1 | 2D8+2 dégâts · Ag -14 · 4 tours | lame · 🔊 sword sound.wav |
| 🔑 **Coup du maître voleur** — *Un coup si propre qu'on croirait un tour de passe-passe.* | active | 33 PM | ennemi / cc / portée 1 | 4D10+6 dégâts | lame · 🔊 sword sound.wav |
| 👥 **Disparition dans la foule** — *Il se fond dans la mêlée comme dans une foule de marché.* | active | 33 PM | soi / portée 1 | Ag +8 · esquive 13 · 4 tours | double · 🔊 swish_2.wav |
| 👻 **Détrousser l'âme** — *Il vole même ce qui ne se voit pas.* | active | 33 PM | ennemi / cc / portée 1 | 2D8+2 dégâts · 2D8+1 aux PM | ombre · 🔊 17.mp3 |
| 🔥 **Feu grégeois de poche** — *Une petite fiole qui fait un très grand feu.* | active | 33 PM | ennemi / cd / portée 4 · cercle rayon 1 | 3D8+8 dégâts | feu · 🔊 foom_0.wav |

### Niveau 9 — 0 existante(s) + 7 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 😇 **Ange gardien des voleurs** — *Il devrait être mort cent fois.* | passive | — | permanent | Ch +5 | — |
| 🚪 **Toujours une issue** — *Il trouve toujours une sortie, même là où il n'y en a pas.* | passive | — | permanent | esquive 7 | — |
| 🗣️ **Bagout** — *Il harangue ses compagnons comme une foule de marché.* | active | 37 PM | soi / portée 1 · carre rayon 2 | Cha +13 Ag +6 · 5 tours | chant · 🔊 power_up_sound_v1.ogg |
| 🤴 **Coup du prince des voleurs** — *Le coup qui a fait de lui une légende des bas-fonds.* | active | 37 PM | ennemi / cc / portée 1 | 4D10+9 dégâts | saignee · 🔊 sword sound.wav |
| 🏚️ **Fuite par les toits** — *Plus personne ne le rattrape quand il prend les toits.* | active | 37 PM | soi / portée 1 | saut 5 cases | saut · 🔊 swish_4.wav |
| 🗡️ **Lame dans la manche** — *Chaque coup volé lui rend des forces.* | active | 37 PM | ennemi / cc / portée 1 | 4D10+9 dégâts · drain 40 % (max 20) | saignee · 🔊 sword sound.wav |
| 🌶️ **Nuage de poivre** — *Une grosse bourse de poivre éventrée au milieu des ennemis.* | active | 37 PM | ennemi / cc / portée 1 · cercle rayon 2 | 3D8+6 dégâts | poudre · 🔊 swish_2.wav |

### Niveau 10 — 2 existante(s) + 5 neuve(s)

| compétence | mode | coût | cible | effets | animation |
|---|---|---|---|---|---|
| 🫥 **Main invisible** — *On dit qu'il a volé la couronne sur la tête du roi.* | passive | — | permanent | Ag +5 | — |
| 💎 **Le grand coup** — *Le casse de sa vie, mais avec une lame.* | active | 40 PM | ennemi / cc / portée 1 | 5D10+12 dégâts | lame · 🔊 sword sound.wav |
| 🎩 **Prestidigitation** — *Un tour de passe-passe, et il est derrière vous.* | active | 40 PM | soi / portée 1 | Ag +10 · esquive 15 · 5 tours | double · 🔊 swish_2.wav |
| 🌪️ **Tempête de couteaux** — *Une volée de couteaux autour de lui.* | active | 40 PM | ennemi / cc / portée 1 · carre rayon 2 | 3D8+7 dégâts | lame · 🔊 sword sound.wav |
| 🌑 **Voleur d'ombres** — *Il vole jusqu'à l'énergie qui fait vivre les mages.* | active | 40 PM | ennemi / cc / portée 1 | 3D8+2 dégâts · 3D8 aux PM | ombre · 🔊 17.mp3 |

