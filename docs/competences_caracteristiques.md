# Compétences 1 → 10 à formules de caractéristiques

**Document GÉNÉRÉ par `python dev/gen_competences_caracteristiques.py`** — ne pas retoucher. Import : `jsons/competences_caracteristiques_a_importer.json`.

Référentiel : `telluris-dump-20261007-160534.json`. Valeur d'origine conservée à la caractéristique de référence `30 + 4 × niveau` ; colonnes « à 20 » / « à 80 » = valeur résolue (dés : moyenne).

## assassin

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Coup de dague | `degats` | `1D8+3` | `1D8+{Ag/10}` | 6.5 | 12.5 |
| 1 | Entaille au tendon | `buffs.Ag` | `-6` | `-3-{Int/10}` | -5 | -11 |
| 1 | Lame enduite | `regen_pv` | `-3` | `-1-{Int/15}` | -2 | -6 |
| 1 | Sang-froid du tueur | `buffs.Ag` | `8` | `4+{Ag/8}` | 6 | 14 |
| 2 | Coup dans le dos | `degats` | `2D6+3` | `2D6+{Ag/12}` | 8 | 13 |
| 2 | Double lame | `degats` | `1D8+3` | `1D8+{Ag/12}` | 5.5 | 10.5 |
| 2 | Fiole de belladone | `regen_pm` | `-2` | `-1-{Int/30}` | -1 | -3 |
| 2 | Garrot | `buffs.F` | `-7` | `-3-{Int/8}` | -5 | -13 |
| 2 | Pas dans l'ombre | `buffs.Ag` | `4` | `2+{Ag/15}` | 3 | 7 |
| 3 | Perce-cœur | `degats` | `2D8+3` | `2D8+{Ag/12}` | 10 | 15 |
| 3 | Poudre de pavot | `buffs.Ag` | `-8` | `-4-{Int/10}` | -6 | -12 |
| 3 | Venin d'aspic | `regen_pv` | `-4` | `-2-{Int/20}` | -3 | -6 |
| 4 | Fleur de lames | `degats` | `2D6+3` | `2D6+{Ag/15}` | 8 | 12 |
| 4 | Sang du contrat | `degats` | `3D8+5` | `3D8+{Ag/8}` | 15.5 | 23.5 |
| 4 | Toxine paralysante | `buffs.Ag` | `-9` | `-4-{Int/8}` | -6 | -14 |
| 4 | Voile de fumée | `buffs.Ag` | `6` | `3+{Ag/15}` | 4 | 8 |
| 5 | Concentration mortelle | `buffs.Ag` | `16` | `8+{Ag/6}` | 11 | 21 |
| 5 | Essence de mandragore | `regen_pm` | `-3` | `-1-{Int/25}` | -1 | -4 |
| 5 | Égorgement | `degats` | `3D8+4` | `3D8+{Ag/12}` | 14.5 | 19.5 |
| 6 | Lame dans les reins | `degats` | `3D8+6` | `3D8+{Ag/8}` | 15.5 | 23.5 |
| 6 | Marque de mort | `buffs.Vol` | `-12` | `-6-{Int/8}` | -8 | -16 |
| 6 | Nuage toxique | `degats` | `3D6+6` | `3D6+{Ag/8}` | 12.5 | 20.5 |
| 6 | Voler le souffle | `degats_pm` | `2D6+2` | `2D6+{Int/25}` | 7 | 10 |
| 7 | Assassinat | `degats` | `3D10+7` | `3D10+{Ag/8}` | 18.5 | 26.5 |
| 7 | Danse des dagues | `degats` | `2D8+4` | `2D8+{Ag/12}` | 10 | 15 |
| 7 | Saignée silencieuse | `degats` | `3D10+7` | `3D10+{Ag/8}` | 18.5 | 26.5 |
| 7 | Venin du scorpion noir | `regen_pv` | `-6` | `-3-{Int/15}` | -4 | -8 |
| 8 | Coup du cobra | `degats` | `4D10+6` | `4D10+{Ag/10}` | 24 | 30 |
| 8 | Oubli de la douleur | `degats` | `4D10+10` | `4D10+{Ag/6}` | 25 | 35 |
| 8 | Poudre de sommeil | `buffs.Ag` | `-14` | `-7-{Int/8}` | -9 | -17 |
| 8 | Venin de l'âme | `regen_pm` | `-4` | `-2-{Int/30}` | -2 | -4 |
| 8 | Éventail de dagues | `degats` | `3D8+8` | `3D8+{Ag/7}` | 15.5 | 24.5 |
| 9 | Brume empoisonnée | `degats` | `3D8+6` | `3D8+{Ag/10}` | 15.5 | 21.5 |
| 9 | Exécution silencieuse | `degats` | `4D10+9` | `4D10+{Ag/7}` | 24 | 33 |
| 9 | Pacte de l'ombre | `buffs.Ag` | `21` | `10+{Ag/6}` | 13 | 23 |
| 9 | Peste noire | `regen_pv` | `-7` | `-3-{Int/15}` | -4 | -8 |
| 10 | Disparition | `buffs.Ag` | `10` | `5+{Ag/12}` | 6 | 11 |
| 10 | Fiole du maître empoisonneur | `regen_pv` | `-8` | `-4-{Int/15}` | -5 | -9 |
| 10 | Fléau silencieux | `degats` | `3D8+7` | `3D8+{Ag/10}` | 15.5 | 21.5 |
| 10 | Mort certaine | `degats` | `5D10+12` | `5D10+{Ag/6}` | 30.5 | 40.5 |

## barbare

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Coup de hache | `degats` | `1D8+3` | `1D8+{F/10}` | 6.5 | 12.5 |
| 1 | Hurlement | `buffs.Vol` | `-6` | `-3-{R/10}` | -5 | -11 |
| 1 | Morsure du fer | `degats` | `2D6+4` | `2D6+{F/8}` | 9 | 17 |
| 1 | Échauffement | `buffs.F` | `8` | `4+{R/8}` | 6 | 14 |
| 2 | Fracas | `degats` | `2D6+3` | `2D6+{F/12}` | 8 | 13 |
| 2 | Sang qui bout | `buffs.F` | `12` | `6+{R/6}` | 9 | 19 |
| 2 | Taille sauvage | `degats` | `1D8+3` | `1D8+{F/12}` | 5.5 | 10.5 |
| 2 | Tête la première | `buffs.Int` | `-7` | `-3-{R/8}` | -5 | -13 |
| 3 | Cri des ancêtres | `buffs.F` | `7` | `3+{R/10}` | 5 | 11 |
| 3 | Fendeur de crânes | `degats` | `2D8+3` | `2D8+{F/12}` | 10 | 15 |
| 3 | Griffes de l'ours | `regen_pv` | `-4` | `-2-{R/20}` | -3 | -6 |
| 4 | Frappe du mammouth | `buffs.Ag` | `-9` | `-4-{R/8}` | -6 | -14 |
| 4 | Ivresse du combat | `buffs.F` | `12` | `6+{R/7}` | 8 | 17 |
| 4 | Tourbillon sauvage | `degats` | `2D6+3` | `2D6+{F/15}` | 8 | 12 |
| 5 | Brise-os | `degats` | `3D8+4` | `3D8+{F/12}` | 14.5 | 19.5 |
| 5 | Charge du sanglier | `buffs.Ag` | `-10` | `-5-{R/10}` | -7 | -13 |
| 5 | Fauche | `degats` | `2D8+5` | `2D8+{F/10}` | 11 | 17 |
| 5 | Folie sanglante | `degats` | `3D8+8` | `3D8+{F/6}` | 16.5 | 26.5 |
| 5 | Rage partagée | `buffs.F` | `9` | `4+{R/10}` | 6 | 12 |
| 6 | Griffe de la bête | `degats` | `3D6+6` | `3D6+{F/8}` | 12.5 | 20.5 |
| 6 | Massacre | `degats` | `3D8+6` | `3D8+{F/8}` | 15.5 | 23.5 |
| 6 | Peau de pierre | `buffs.R` | `17` | `8+{R/6}` | 11 | 21 |
| 6 | Rugissement | `buffs.Vol` | `-12` | `-6-{R/8}` | -8 | -16 |
| 7 | Fendoir des montagnes | `degats` | `3D10+7` | `3D10+{F/8}` | 18.5 | 26.5 |
| 7 | Hémorragie | `regen_pv` | `-6` | `-3-{R/15}` | -4 | -8 |
| 7 | Transe sanglante | `degats` | `4D10+6` | `4D10+{F/10}` | 24 | 30 |
| 8 | Briseur de lignes | `degats` | `3D8+8` | `3D8+{F/7}` | 15.5 | 24.5 |
| 8 | Coup de tonnerre | `degats` | `4D10+6` | `4D10+{F/10}` | 24 | 30 |
| 8 | Furie du clan | `buffs.F` | `12` | `6+{R/10}` | 8 | 14 |
| 8 | Griffes du grand ours | `degats` | `3D8+8` | `3D8+{F/7}` | 15.5 | 24.5 |
| 8 | Terreur des steppes | `buffs.Vol` | `-14` | `-7-{R/8}` | -9 | -17 |
| 9 | Berserk | `buffs.F` | `21` | `10+{R/6}` | 13 | 23 |
| 9 | Décapitation | `degats` | `4D10+9` | `4D10+{F/7}` | 24 | 33 |
| 9 | Folie du massacre | `degats` | `5D10+10` | `5D10+{F/7}` | 29.5 | 38.5 |
| 9 | Séisme | `degats` | `3D8+4` | `3D8+{F/15}` | 14.5 | 18.5 |
| 10 | Carnage | `degats` | `3D8+7` | `3D8+{F/10}` | 15.5 | 21.5 |
| 10 | Coup du fléau des clans | `degats` | `5D10+12` | `5D10+{F/6}` | 30.5 | 40.5 |
| 10 | Cri du dernier clan | `buffs.F` | `14` | `7+{R/10}` | 9 | 15 |
| 10 | Sang pour sang | `degats` | `5D10+12` | `5D10+{F/6}` | 30.5 | 40.5 |

## chaman

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Bénédiction ancestrale | `pv` | `16` | `8+{Cha/4}` | 13 | 28 |
| 1 | Cri de l'esprit | `buffs.Vol` | `-6` | `-3-{Vol/10}` | -5 | -11 |
| 1 | Force de l'ours | `buffs.F` | `8` | `4+{Cha/8}` | 6 | 14 |
| 1 | Griffe du loup | `degats` | `1D8+3` | `1D8+{Vol/10}` | 6.5 | 12.5 |
| 2 | Esprit voleur | `degats_pm` | `1D6+1` | `1D6+{Vol/30}` | 3.5 | 5.5 |
| 2 | Morsure du serpent | `regen_pv` | `-3` | `-1-{Vol/15}` | -2 | -6 |
| 2 | Œil du faucon | `buffs.Ag` | `9` | `4+{Cha/7}` | 6 | 15 |
| 3 | Ruée du sanglier-esprit | `buffs.Ag` | `-8` | `-4-{Vol/10}` | -6 | -12 |
| 3 | Tambour des esprits | `buffs.Vol` | `7` | `3+{Cha/10}` | 5 | 11 |
| 4 | Fièvre des marais | `regen_pm` | `-3` | `-1-{Vol/20}` | -2 | -5 |
| 4 | Foudre des ancêtres | `degats` | `2D8+5` | `2D8+{Vol/8}` | 11 | 19 |
| 4 | Hurlement de la meute | `degats` | `2D6+5` | `2D6+{Vol/8}` | 9 | 17 |
| 5 | Crocs de l'esprit | `degats` | `3D8+4` | `3D8+{Vol/12}` | 14.5 | 19.5 |
| 5 | Esprit guérisseur | `regen_pv` | `3` | `1+{Cha/25}` | 1 | 4 |
| 5 | Masque des morts | `buffs.Vol` | `-10` | `-5-{Vol/10}` | -7 | -13 |
| 5 | Transe | `pm` | `16` | `8+{Cha/6}` | 11 | 21 |
| 6 | Griffes de l'ours-esprit | `degats` | `3D6+6` | `3D6+{Vol/8}` | 12.5 | 20.5 |
| 7 | Chaînes spirituelles | `buffs.Ag` | `-13` | `-6-{Vol/8}` | -8 | -16 |
| 7 | Esprit du sanglier | `degats` | `3D10+7` | `3D10+{Vol/8}` | 18.5 | 26.5 |
| 7 | Fléau des esprits | `regen_pv` | `-6` | `-3-{Vol/15}` | -4 | -8 |
| 7 | Totem de guerre | `buffs.F` | `11` | `5+{Cha/10}` | 7 | 13 |
| 8 | Danse de l'esprit | `pv` | `23` | `11+{Cha/5}` | 15 | 27 |
| 8 | Orage ancestral | `degats` | `3D8+4` | `3D8+{Vol/15}` | 14.5 | 18.5 |
| 8 | Peau de l'ours | `buffs.R` | `20` | `10+{Cha/6}` | 13 | 23 |
| 8 | Vol d'âme | `degats_pm` | `2D8+1` | `2D8+{Vol/30}` | 9 | 11 |
| 9 | Chant des morts | `regen_pm` | `-5` | `-2-{Vol/20}` | -3 | -6 |
| 9 | Fureur totémique | `degats` | `4D10+9` | `4D10+{Vol/7}` | 24 | 33 |
| 9 | Rituel du grand esprit | `degats` | `5D10+10` | `5D10+{Vol/7}` | 29.5 | 38.5 |
| 10 | Avatar totémique | `buffs.F` | `23` | `11+{Cha/6}` | 14 | 24 |
| 10 | Colère des ancêtres | `degats` | `3D8+7` | `3D8+{Vol/10}` | 15.5 | 21.5 |

## demoniste

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Malédiction | `buffs.Vol` | `-6` | `-3-{Vol/10}` | -5 | -11 |
| 1 | Pacte mineur | `degats` | `2D6+4` | `2D6+{Int/8}` | 9 | 17 |
| 1 | Peau de démon | `buffs.R` | `8` | `4+{Vol/8}` | 6 | 14 |
| 1 | Trait infernal | `degats` | `1D8+3` | `1D8+{Int/10}` | 6.5 | 12.5 |
| 2 | Flammes de l'abîme | `regen_pv` | `-3` | `-1-{Vol/15}` | -2 | -6 |
| 2 | Sang pour le démon | `degats` | `2D6+3` | `2D6+{Int/12}` | 8 | 13 |
| 2 | Siphon infernal | `degats_pm` | `1D6+1` | `1D6+{Vol/30}` | 3.5 | 5.5 |
| 3 | Pluie de soufre | `degats` | `2D6+3` | `2D6+{Int/12}` | 8 | 13 |
| 3 | Regard du démon | `buffs.Ag` | `-8` | `-4-{Vol/10}` | -6 | -12 |
| 4 | Bouclier infernal | `buffs.R` | `15` | `7+{Vol/6}` | 10 | 20 |
| 4 | Corruption de l'âme | `regen_pm` | `-3` | `-1-{Vol/20}` | -2 | -5 |
| 4 | Don du démon | `pm` | `14` | `7+{Vol/6}` | 10 | 20 |
| 5 | Chaînes de l'enfer | `buffs.Ag` | `-10` | `-5-{Vol/10}` | -7 | -13 |
| 5 | Explosion infernale | `degats` | `2D6+5` | `2D6+{Int/10}` | 9 | 15 |
| 5 | Fièvre infernale | `regen_pv` | `-5` | `-2-{Vol/15}` | -3 | -7 |
| 5 | Pacte de puissance | `degats` | `3D8+8` | `3D8+{Int/6}` | 16.5 | 26.5 |
| 6 | Souffle de l'abîme | `degats` | `2D8+4` | `2D8+{Int/12}` | 10 | 15 |
| 7 | Feu de l'âme | `degats` | `3D10+7` | `3D10+{Int/8}` | 18.5 | 26.5 |
| 7 | Forme démoniaque | `buffs.F` | `19` | `9+{Vol/6}` | 12 | 22 |
| 7 | Peur infernale | `buffs.Vol` | `-13` | `-6-{Vol/8}` | -8 | -16 |
| 7 | Siphon de l'abîme | `degats_pm` | `2D8` | `2D{Vol/7}` | 3 | 12 |
| 8 | Malédiction de l'abîme | `regen_pm` | `-4` | `-2-{Vol/30}` | -2 | -4 |
| 8 | Pacte de sang majeur | `degats` | `4D10+10` | `4D10+{Int/6}` | 25 | 35 |
| 8 | Tempête de feu noir | `degats` | `2D8+6` | `2D8+{Int/10}` | 11 | 17 |
| 9 | Banquet de l'abîme | `degats` | `4D10+9` | `4D10+{Int/7}` | 24 | 33 |
| 9 | Flamme du seigneur démon | `degats` | `4D10+9` | `4D10+{Int/7}` | 24 | 33 |
| 9 | Peste infernale | `regen_pv` | `-7` | `-3-{Vol/15}` | -4 | -8 |
| 9 | Rituel infernal | `degats` | `5D10+10` | `5D10+{Int/7}` | 29.5 | 38.5 |
| 10 | Apocalypse | `degats` | `3D10+6` | `3D10+{Int/12}` | 17.5 | 22.5 |
| 10 | Âme damnée | `buffs.Vol` | `-16` | `-8-{Vol/8}` | -10 | -18 |

## druide

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Baume de mousse | `pv` | `16` | `8+{Vol/4}` | 13 | 28 |
| 1 | Lianes | `buffs.Ag` | `-6` | `-3-{Int/10}` | -5 | -11 |
| 1 | Écorce | `buffs.R` | `8` | `4+{Vol/8}` | 6 | 14 |
| 1 | Épines | `degats` | `1D8+3` | `1D8+{Vol/10}` | 6.5 | 12.5 |
| 2 | Pollen soporifique | `buffs.Vol` | `-7` | `-3-{Int/8}` | -5 | -13 |
| 2 | Sève de chêne | `regen_pv` | `2` | `1+{Vol/30}` | 1 | 3 |
| 3 | Bénédiction des bois | `buffs.R` | `10` | `5+{Vol/8}` | 7 | 15 |
| 3 | Champ de ronces | `degats` | `2D6+3` | `2D6+{Vol/12}` | 8 | 13 |
| 4 | Nuée d'insectes | `regen_pv` | `-4` | `-2-{Int/20}` | -3 | -6 |
| 4 | Peau d'écorce | `buffs.R` | `15` | `7+{Vol/6}` | 10 | 20 |
| 4 | Racines dévorantes | `degats` | `2D8+5` | `2D8+{Vol/8}` | 11 | 19 |
| 4 | Rosée du matin | `pm` | `14` | `7+{Vol/6}` | 10 | 20 |
| 5 | Fouet de liane | `degats` | `3D8+4` | `3D8+{Vol/12}` | 14.5 | 19.5 |
| 5 | Régénération sylvestre | `pv` | `16` | `8+{Vol/6}` | 11 | 21 |
| 5 | Spores étouffantes | `degats` | `2D6+5` | `2D6+{Vol/10}` | 9 | 15 |
| 6 | Cercle de vie | `buffs.R` | `10` | `5+{Vol/10}` | 7 | 13 |
| 6 | Colère de la forêt | `degats` | `3D6+6` | `3D6+{Vol/8}` | 12.5 | 20.5 |
| 7 | Pieu de bois vivant | `degats` | `3D10+7` | `3D10+{Vol/8}` | 18.5 | 26.5 |
| 7 | Venin de la vipère verte | `regen_pm` | `-4` | `-2-{Int/25}` | -2 | -5 |
| 7 | Étreinte du saule | `buffs.Ag` | `-13` | `-6-{Int/8}` | -8 | -16 |
| 8 | Bouclier d'épines | `buffs.R` | `20` | `10+{Vol/6}` | 13 | 23 |
| 8 | Floraison | `pv` | `38` | `19+{Vol/3}` | 25 | 45 |
| 8 | Tempête de feuilles | `degats` | `3D8+8` | `3D8+{Vol/7}` | 15.5 | 24.5 |
| 9 | Courroux du chêne | `degats` | `4D10+9` | `4D10+{Vol/7}` | 24 | 33 |
| 9 | Marais | `degats` | `3D8+6` | `3D8+{Vol/10}` | 15.5 | 21.5 |
| 9 | Pluie de vie | `regen_pv` | `5` | `2+{Vol/20}` | 3 | 6 |
| 9 | Rituel du cycle | `degats` | `5D10+10` | `5D10+{Vol/7}` | 29.5 | 38.5 |
| 10 | Fureur de Gaïa | `degats` | `3D8+7` | `3D8+{Vol/10}` | 15.5 | 21.5 |
| 10 | Renouveau | `pv` | `27` | `13+{Vol/5}` | 17 | 29 |

## duelliste

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Battement | `buffs.Ag` | `-6` | `-3-{Ag/10}` | -5 | -11 |
| 1 | Coup droit | `degats` | `1D8+3` | `1D8+{Ag/10}` | 6.5 | 12.5 |
| 1 | En garde | `buffs.Ag` | `4` | `2+{Cha/15}` | 3 | 7 |
| 1 | Riposte | `degats` | `1D8+3` | `1D8+{Ag/10}` | 6.5 | 12.5 |
| 2 | Coup de manchette | `buffs.F` | `-7` | `-3-{Ag/8}` | -5 | -13 |
| 2 | Défi d'honneur | `buffs.Ag` | `9` | `4+{Cha/7}` | 6 | 15 |
| 2 | Estafilade | `regen_pv` | `-3` | `-1-{Ag/15}` | -2 | -6 |
| 2 | Taille en tierce | `degats` | `2D6+3` | `2D6+{Ag/12}` | 8 | 13 |
| 3 | Danse des lames | `degats` | `2D6+3` | `2D6+{Ag/12}` | 8 | 13 |
| 3 | Double attaque | `degats` | `2D8+3` | `2D8+{Ag/12}` | 10 | 15 |
| 3 | Désarmement | `buffs.F` | `-8` | `-4-{Ag/10}` | -6 | -12 |
| 4 | Bravade | `buffs.Cha` | `12` | `6+{Cha/7}` | 8 | 17 |
| 4 | Coup de Jarnac | `buffs.Ag` | `-9` | `-4-{Ag/8}` | -6 | -14 |
| 4 | Fente basse | `degats` | `2D8+5` | `2D8+{Ag/8}` | 11 | 19 |
| 4 | Volte | `degats` | `2D6+3` | `2D6+{Ag/15}` | 8 | 12 |
| 5 | Coup de pointe | `degats` | `3D8+4` | `3D8+{Ag/12}` | 14.5 | 19.5 |
| 5 | Liement | `buffs.Ag` | `-10` | `-5-{Ag/10}` | -7 | -13 |
| 5 | Moulinet du bretteur | `degats` | `2D8+5` | `2D8+{Ag/10}` | 11 | 17 |
| 5 | Saignées multiples | `regen_pv` | `-5` | `-2-{Ag/15}` | -3 | -7 |
| 5 | Salut du maître | `buffs.Ag` | `13` | `6+{Cha/7}` | 8 | 17 |
| 6 | Coup de maître | `degats` | `3D8+6` | `3D8+{Ag/8}` | 15.5 | 23.5 |
| 6 | Éventail d'acier | `degats` | `3D6+6` | `3D6+{Ag/8}` | 12.5 | 20.5 |
| 7 | Assaut de grâce | `buffs.Ag` | `16` | `8+{Cha/7}` | 10 | 19 |
| 7 | Botte secrète | `degats` | `3D10+7` | `3D10+{Ag/8}` | 18.5 | 26.5 |
| 7 | Coup de pied de salle | `degats` | `3D10+7` | `3D10+{Ag/8}` | 18.5 | 26.5 |
| 7 | Coup du papillon | `degats` | `2D8+6` | `2D8+{Ag/10}` | 11 | 17 |
| 7 | Prise de fer | `buffs.F` | `-13` | `-6-{Ag/8}` | -8 | -16 |
| 8 | Inspiration du maître d'armes | `buffs.Ag` | `17` | `8+{Cha/7}` | 10 | 19 |
| 8 | Pointe au cœur | `degats` | `4D10+6` | `4D10+{Ag/10}` | 24 | 30 |
| 8 | Saignée d'artère | `regen_pv` | `-6` | `-3-{Ag/20}` | -4 | -7 |
| 8 | Tourbillon du bretteur | `degats` | `2D8+6` | `2D8+{Ag/10}` | 11 | 17 |
| 9 | Coup du roi | `degats` | `4D10+9` | `4D10+{Ag/7}` | 24 | 33 |
| 9 | Garde absolue | `buffs.Ag` | `21` | `10+{Cha/6}` | 13 | 23 |
| 9 | Main paralysée | `buffs.F` | `-15` | `-7-{Ag/8}` | -9 | -17 |
| 9 | Sang du duel | `degats` | `4D10+9` | `4D10+{Ag/7}` | 24 | 33 |
| 9 | Vent de lames | `degats` | `3D10+8` | `3D10+{Ag/8}` | 18.5 | 26.5 |
| 10 | Ballet mortel | `degats` | `3D8+7` | `3D8+{Ag/10}` | 15.5 | 21.5 |
| 10 | Coup parfait | `degats` | `5D10+12` | `5D10+{Ag/6}` | 30.5 | 40.5 |
| 10 | Maître du terrain | `buffs.Ag` | `14` | `7+{Cha/10}` | 9 | 15 |

## elementaliste

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Gel des membres | `buffs.Ag` | `-6` | `-3-{Int/10}` | -5 | -11 |
| 1 | Peau de granit | `buffs.R` | `8` | `4+{Vol/8}` | 6 | 14 |
| 1 | Étincelle | `degats` | `1D8+3` | `1D8+{Int/10}` | 6.5 | 12.5 |
| 2 | Arc électrique | `degats_pm` | `1D6+1` | `1D6+{Int/30}` | 3.5 | 5.5 |
| 2 | Brûlure | `regen_pv` | `-3` | `-1-{Int/15}` | -2 | -6 |
| 2 | Pluie douce | `regen_pv` | `2` | `1+{Vol/30}` | 1 | 3 |
| 3 | Bourrasque | `buffs.Ag` | `-8` | `-4-{Int/10}` | -6 | -12 |
| 3 | Gerbe de flammes | `degats` | `2D6+3` | `2D6+{Int/12}` | 8 | 13 |
| 4 | Armure de glace | `buffs.R` | `15` | `7+{Vol/6}` | 10 | 20 |
| 4 | Givre rampant | `regen_pv` | `-4` | `-2-{Int/20}` | -3 | -6 |
| 4 | Lance de foudre | `degats` | `2D8+5` | `2D8+{Int/8}` | 11 | 19 |
| 4 | Torrent | `degats` | `2D6+5` | `2D6+{Int/8}` | 9 | 17 |
| 5 | Langue de feu | `degats` | `2D6+5` | `2D6+{Int/10}` | 9 | 15 |
| 5 | Projection de roc | `degats` | `3D8+4` | `3D8+{Int/12}` | 14.5 | 19.5 |
| 5 | Souffle des éléments | `buffs.R` | `13` | `6+{Vol/7}` | 8 | 17 |
| 6 | Forme de vapeur | `buffs.Int` | `7` | `3+{Vol/12}` | 4 | 9 |
| 6 | Tempête de grêle | `degats` | `2D8+4` | `2D8+{Int/12}` | 10 | 15 |
| 7 | Sables mouvants | `buffs.Ag` | `-13` | `-6-{Int/8}` | -8 | -16 |
| 7 | Source de mana | `pm` | `20` | `10+{Vol/6}` | 13 | 23 |
| 7 | Éclair en chaîne | `degats` | `2D8+6` | `2D8+{Int/10}` | 11 | 17 |
| 8 | Javelot de glace | `degats` | `4D10+6` | `4D10+{Int/10}` | 24 | 30 |
| 8 | Rituel de la tempête | `degats` | `4D10+10` | `4D10+{Int/6}` | 25 | 35 |
| 8 | Siphon des éléments | `degats` | `4D10+6` | `4D10+{Int/10}` | 24 | 30 |
| 8 | Tremblement | `degats` | `2D8+6` | `2D8+{Int/10}` | 11 | 17 |
| 9 | Bouclier des quatre vents | `buffs.R` | `13` | `6+{Vol/10}` | 8 | 14 |
| 9 | Brasier | `regen_pv` | `-7` | `-3-{Int/15}` | -4 | -8 |
| 9 | Raz-de-marée | `degats` | `3D10+8` | `3D10+{Int/8}` | 18.5 | 26.5 |
| 10 | Fureur élémentaire | `degats` | `6D10+12` | `6D10+{Int/6}` | 36 | 46 |
| 10 | Zéro absolu | `buffs.Ag` | `-16` | `-8-{Int/8}` | -10 | -18 |

## forestier

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Coup de couteau | `degats` | `1D8+3` | `1D8+{Ag/10}` | 6.5 | 12.5 |
| 1 | Flèche rapide | `degats` | `1D8+3` | `1D8+{Ag/10}` | 6.5 | 12.5 |
| 1 | Tir aux jambes | `buffs.Ag` | `-6` | `-3-{Int/10}` | -5 | -11 |
| 2 | Flèche barbelée | `regen_pv` | `-3` | `-1-{Int/15}` | -2 | -6 |
| 2 | Herbes de guérison | `pv` | `18` | `9+{Ch/4}` | 14 | 29 |
| 2 | Patience du chasseur | `buffs.Ag` | `9` | `4+{Ch/7}` | 6 | 15 |
| 2 | Volée | `degats` | `1D8+3` | `1D8+{Ag/12}` | 5.5 | 10.5 |
| 3 | Cri du faucon | `buffs.Vol` | `-8` | `-4-{Int/10}` | -6 | -12 |
| 3 | Flèche perforante | `degats` | `2D8+3` | `2D8+{Ag/12}` | 10 | 15 |
| 3 | Marque du gibier | `degats_pm` | `1D8+1` | `1D8+{Int/30}` | 4.5 | 6.5 |
| 3 | Pas de côté du rôdeur | `buffs.Ag` | `5` | `2+{Ch/12}` | 3 | 8 |
| 4 | Flèche de chasse | `buffs.Ag` | `-9` | `-4-{Int/8}` | -6 | -14 |
| 4 | Lame et pointe | `degats` | `2D6+5` | `2D6+{Ag/8}` | 9 | 17 |
| 4 | Remède du bois | `regen_pv` | `3` | `1+{Ch/20}` | 2 | 5 |
| 4 | Tir à l'œil | `degats` | `2D8+5` | `2D8+{Ag/8}` | 11 | 19 |
| 5 | Appel du loup | `buffs.Ag` | `9` | `4+{Ch/10}` | 6 | 12 |
| 5 | Flèche longue | `degats` | `3D8+4` | `3D8+{Ag/12}` | 14.5 | 19.5 |
| 5 | Flèche venimeuse | `regen_pv` | `-5` | `-2-{Int/15}` | -3 | -7 |
| 5 | Pluie de flèches | `degats` | `2D6+5` | `2D6+{Ag/10}` | 9 | 15 |
| 6 | Clouer au sol | `buffs.Ag` | `-12` | `-6-{Int/8}` | -8 | -16 |
| 6 | Flèche épuisante | `degats_pm` | `2D6+2` | `2D6+{Int/25}` | 7 | 10 |
| 6 | Ombre des feuilles | `buffs.Ag` | `7` | `3+{Ch/12}` | 4 | 9 |
| 7 | Pharmacopée sylvestre | `pv` | `34` | `17+{Ch/3}` | 23 | 43 |
| 7 | Saignée de cerf | `regen_pv` | `-6` | `-3-{Int/15}` | -4 | -8 |
| 7 | Tir mortel | `degats` | `3D10+7` | `3D10+{Ag/8}` | 18.5 | 26.5 |
| 7 | Volée en éventail | `degats` | `2D8+6` | `2D8+{Ag/10}` | 11 | 17 |
| 8 | Couteau du dépeceur | `degats` | `4D10+6` | `4D10+{Ag/10}` | 24 | 30 |
| 8 | Esprit de la forêt | `buffs.R` | `17` | `8+{Ch/7}` | 10 | 19 |
| 8 | Flèche aveuglante | `buffs.Ag` | `-14` | `-7-{Int/8}` | -9 | -17 |
| 8 | Grêle de flèches | `degats` | `3D8+4` | `3D8+{Ag/15}` | 14.5 | 18.5 |
| 8 | Tir transperçant | `degats` | `4D10+6` | `4D10+{Ag/10}` | 24 | 30 |
| 9 | Flèche du roi des bois | `degats` | `4D10+9` | `4D10+{Ag/7}` | 24 | 33 |
| 9 | Tir de suppression | `degats` | `3D8+6` | `3D8+{Ag/10}` | 15.5 | 21.5 |
| 9 | Venin du marais | `regen_pv` | `-7` | `-3-{Int/15}` | -4 | -8 |
| 9 | Vigilance du guetteur | `buffs.Ag` | `21` | `10+{Ch/6}` | 13 | 23 |
| 10 | Appel de la grande chasse | `buffs.Ag` | `14` | `7+{Ch/10}` | 9 | 15 |
| 10 | Ciel de flèches | `degats` | `3D10+6` | `3D10+{Ag/12}` | 17.5 | 22.5 |
| 10 | Flèche de légende | `degats` | `5D10+12` | `5D10+{Ag/6}` | 30.5 | 40.5 |
| 10 | Proie épuisée | `degats_pm` | `3D8` | `3D{Int/8}` | 4.5 | 16.5 |

## guerrier

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Bousculade | `buffs.Ag` | `-6` | `-3-{F/10}` | -5 | -11 |
| 1 | Coup d'estoc | `degats` | `1D8+3` | `1D8+{F/10}` | 6.5 | 12.5 |
| 1 | Garde haute | `buffs.R` | `4` | `2+{Vol/15}` | 3 | 7 |
| 2 | Coup de taille | `degats` | `2D6+3` | `2D6+{F/12}` | 8 | 13 |
| 2 | Pommeau au visage | `buffs.Int` | `-7` | `-3-{F/8}` | -5 | -13 |
| 2 | Second souffle | `buffs.R` | `9` | `4+{Vol/7}` | 6 | 15 |
| 2 | Taille horizontale | `degats` | `1D8+3` | `1D8+{F/12}` | 5.5 | 10.5 |
| 3 | Cercle d'acier | `degats` | `1D8+4` | `1D8+{F/10}` | 6.5 | 12.5 |
| 3 | Mur de boucliers | `buffs.R` | `13` | `6+{Vol/6}` | 9 | 19 |
| 3 | Taillade aux jarrets | `regen_pv` | `-4` | `-2-{F/20}` | -3 | -6 |
| 4 | Coup de bélier | `buffs.F` | `-9` | `-4-{F/8}` | -6 | -14 |
| 4 | Coup du maître de corps | `degats` | `3D8+5` | `3D8+{F/8}` | 15.5 | 23.5 |
| 4 | Cri de guerre | `buffs.F` | `8` | `4+{Vol/10}` | 6 | 12 |
| 4 | Lame lourde | `degats` | `2D8+5` | `2D8+{F/8}` | 11 | 19 |
| 5 | Brise-garde | `buffs.Ag` | `-10` | `-5-{F/10}` | -7 | -13 |
| 5 | Estocade | `degats` | `3D8+4` | `3D8+{F/12}` | 14.5 | 19.5 |
| 5 | Fauchage | `degats` | `2D8+5` | `2D8+{F/10}` | 11 | 17 |
| 5 | Ordre de la ligne | `buffs.R` | `13` | `6+{Vol/7}` | 8 | 17 |
| 6 | Coup de grâce | `degats` | `3D8+6` | `3D8+{F/8}` | 15.5 | 23.5 |
| 6 | Vague d'acier | `degats` | `3D6+6` | `3D6+{F/8}` | 12.5 | 20.5 |
| 7 | Frappe de siège | `degats` | `3D10+7` | `3D10+{F/8}` | 18.5 | 26.5 |
| 7 | Hachoir | `degats` | `4D10+6` | `4D10+{F/10}` | 24 | 30 |
| 7 | Lame tournoyante | `degats` | `3D8+5` | `3D8+{F/10}` | 15.5 | 21.5 |
| 7 | Tenue de ligne | `buffs.R` | `11` | `5+{Vol/10}` | 7 | 13 |
| 8 | Garde du capitaine | `buffs.R` | `20` | `10+{Vol/6}` | 13 | 23 |
| 8 | Moulinet | `degats` | `2D8+6` | `2D8+{F/10}` | 11 | 17 |
| 8 | Soin de campagne | `pv` | `38` | `19+{Vol/3}` | 25 | 45 |
| 8 | Tranche-armure | `degats` | `4D10+6` | `4D10+{F/10}` | 24 | 30 |
| 8 | Écrasement | `buffs.Ag` | `-14` | `-7-{F/8}` | -9 | -17 |
| 9 | Assaut sanglant | `degats` | `5D10+10` | `5D10+{F/7}` | 29.5 | 38.5 |
| 9 | Bannière haute | `buffs.F` | `13` | `6+{Vol/10}` | 8 | 14 |
| 9 | Coupe-tête | `degats` | `4D10+9` | `4D10+{F/7}` | 24 | 33 |
| 9 | Fracasse-bouclier | `buffs.R` | `-15` | `-7-{F/8}` | -9 | -17 |
| 9 | Ouragan d'acier | `degats` | `3D10+8` | `3D10+{F/8}` | 18.5 | 26.5 |
| 10 | Coup du seigneur de guerre | `degats` | `5D10+12` | `5D10+{F/6}` | 30.5 | 40.5 |
| 10 | Inébranlable | `buffs.R` | `23` | `11+{Vol/6}` | 14 | 24 |
| 10 | Tempête de lames | `degats` | `3D8+7` | `3D8+{F/10}` | 15.5 | 21.5 |

## illusionniste

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Image miroir | `buffs.Int` | `4` | `2+{Cha/15}` | 3 | 7 |
| 1 | Lueur aveuglante | `degats` | `1D8+3` | `1D8+{Int/10}` | 6.5 | 12.5 |
| 1 | Mirage | `buffs.Ag` | `-6` | `-3-{Cha/10}` | -5 | -11 |
| 2 | Charme | `buffs.Cha` | `9` | `4+{Cha/7}` | 6 | 15 |
| 2 | Couleurs dansantes | `degats` | `1D8+3` | `1D8+{Int/12}` | 5.5 | 10.5 |
| 2 | Peur fantasmée | `buffs.Vol` | `-7` | `-3-{Cha/8}` | -5 | -13 |
| 3 | Lame illusoire | `degats` | `2D8+3` | `2D8+{Int/12}` | 10 | 15 |
| 3 | Voile | `buffs.Ag` | `13` | `6+{Cha/6}` | 9 | 19 |
| 4 | Cauchemar éveillé | `regen_pv` | `-4` | `-2-{Cha/20}` | -3 | -6 |
| 4 | Confusion | `buffs.Int` | `-9` | `-4-{Cha/8}` | -6 | -14 |
| 4 | Prisme | `degats` | `2D8+5` | `2D8+{Int/8}` | 11 | 19 |
| 4 | Rêve apaisant | `regen_pv` | `3` | `1+{Cha/20}` | 2 | 5 |
| 5 | Doubles multiples | `buffs.Int` | `6` | `3+{Cha/15}` | 4 | 8 |
| 5 | Ombres hurlantes | `degats` | `2D6+5` | `2D6+{Int/10}` | 9 | 15 |
| 5 | Vol de pensée | `degats_pm` | `2D6+1` | `2D6+{Cha/30}` | 7 | 9 |
| 6 | Éventail de folie | `degats` | `2D6+5` | `2D6+{Int/10}` | 9 | 15 |
| 7 | Dévoreur de rêves | `degats` | `3D10+7` | `3D10+{Int/8}` | 18.5 | 26.5 |
| 7 | Lame de cauchemar | `degats` | `3D10+7` | `3D10+{Int/8}` | 18.5 | 26.5 |
| 7 | Spectacle | `buffs.Cha` | `11` | `5+{Cha/10}` | 7 | 13 |
| 8 | Démence | `regen_pm` | `-4` | `-2-{Cha/30}` | -2 | -4 |
| 8 | Kaléidoscope | `degats` | `3D8+4` | `3D8+{Int/15}` | 14.5 | 18.5 |
| 8 | Masque de terreur | `buffs.Vol` | `-14` | `-7-{Cha/8}` | -9 | -17 |
| 8 | Mirage de refuge | `buffs.Ag` | `20` | `10+{Cha/6}` | 13 | 23 |
| 9 | Folie collective | `degats` | `3D8+4` | `3D8+{Int/15}` | 14.5 | 18.5 |
| 9 | Grand théâtre | `degats` | `5D10+10` | `5D10+{Int/7}` | 29.5 | 38.5 |
| 9 | Illusion mortelle | `degats` | `4D10+9` | `4D10+{Int/7}` | 24 | 33 |
| 9 | Rêve partagé | `pm` | `24` | `12+{Cha/6}` | 15 | 25 |
| 10 | Fantasmagorie | `degats` | `3D10+6` | `3D10+{Int/12}` | 17.5 | 22.5 |
| 10 | Réalité brisée | `buffs.Int` | `-16` | `-8-{Cha/8}` | -10 | -18 |

## lettre

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Citation savante | `buffs.Int` | `-6` | `-3-{Int/10}` | -5 | -11 |
| 1 | Fiole corrosive | `degats` | `1D8+3` | `1D8+{Int/10}` | 6.5 | 12.5 |
| 1 | Tonique | `pv` | `16` | `8+{Vol/4}` | 13 | 28 |
| 1 | Étude de l'adversaire | `buffs.Int` | `8` | `4+{Vol/8}` | 6 | 14 |
| 2 | Poudre détonante | `degats` | `1D8+3` | `1D8+{Int/12}` | 5.5 | 10.5 |
| 2 | Somnifère | `buffs.Ag` | `-7` | `-3-{Int/8}` | -5 | -13 |
| 2 | Élixir de clarté | `pm` | `10` | `5+{Vol/7}` | 7 | 16 |
| 3 | Glyphe protecteur | `buffs.R` | `10` | `5+{Vol/8}` | 7 | 15 |
| 4 | Bombe de fumée | `buffs.Int` | `6` | `3+{Vol/15}` | 4 | 8 |
| 4 | Dissolvant | `degats_pm` | `2D6` | `2D{Int/7}` | 3 | 12 |
| 4 | Onguent | `regen_pv` | `3` | `1+{Vol/20}` | 2 | 5 |
| 4 | Éclat de savoir | `degats` | `2D8+5` | `2D8+{Int/8}` | 11 | 19 |
| 5 | Feu liquide | `degats` | `2D8+5` | `2D8+{Int/10}` | 11 | 17 |
| 5 | Mémoire du palais | `buffs.Int` | `16` | `8+{Vol/6}` | 11 | 21 |
| 5 | Paradoxe | `buffs.Int` | `-10` | `-5-{Int/10}` | -7 | -13 |
| 5 | Transmutation | `degats` | `3D8+4` | `3D8+{Int/12}` | 14.5 | 19.5 |
| 6 | Panacée | `pv` | `18` | `9+{Vol/6}` | 12 | 22 |
| 7 | Enchantement d'arme | `buffs.F` | `16` | `8+{Vol/7}` | 10 | 19 |
| 7 | Gaz innervant | `regen_pm` | `-4` | `-2-{Int/25}` | -2 | -5 |
| 7 | Verbe de pouvoir | `degats` | `3D10+7` | `3D10+{Int/8}` | 18.5 | 26.5 |
| 8 | Acide royal | `regen_pv` | `-6` | `-3-{Int/20}` | -4 | -7 |
| 8 | Démonstration | `buffs.Int` | `-14` | `-7-{Int/8}` | -9 | -17 |
| 8 | Explosion en chaîne | `degats` | `3D8+4` | `3D8+{Int/15}` | 14.5 | 18.5 |
| 8 | Grande encyclopédie | `buffs.Int` | `12` | `6+{Vol/10}` | 8 | 14 |
| 9 | Pierre philosophale | `degats` | `5D10+10` | `5D10+{Int/7}` | 29.5 | 38.5 |
| 9 | Rune de silence | `degats_pm` | `2D8+2` | `2D8+{Int/30}` | 9 | 11 |
| 9 | Éclair de génie | `degats` | `4D10+9` | `4D10+{Int/7}` | 24 | 33 |
| 9 | Élixir de vie | `pv` | `42` | `21+{Vol/3}` | 27 | 47 |
| 10 | Savoir universel | `buffs.Int` | `23` | `11+{Vol/6}` | 14 | 24 |
| 10 | Œuvre au noir | `degats` | `3D10+6` | `3D10+{Int/12}` | 17.5 | 22.5 |

## mage

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Bouclier réflexe | `buffs.Int` | `4` | `2+{Int/15}` | 3 | 7 |
| 1 | Lame chargée | `degats` | `1D8+3` | `1D8+{Int/10}` | 6.5 | 12.5 |
| 1 | Projectile arcanique | `degats` | `1D8+3` | `1D8+{Int/10}` | 6.5 | 12.5 |
| 2 | Arme enchantée | `buffs.F` | `9` | `4+{Int/7}` | 6 | 15 |
| 2 | Brèche de mana | `degats_pm` | `1D6+1` | `1D6+{Int/30}` | 3.5 | 5.5 |
| 2 | Onde de choc arcanique | `degats` | `1D8+3` | `1D8+{Int/12}` | 5.5 | 10.5 |
| 2 | Rayon de force | `buffs.F` | `-7` | `-3-{Int/8}` | -5 | -13 |
| 3 | Champ de force | `buffs.R` | `13` | `6+{Int/6}` | 9 | 19 |
| 4 | Explosion arcanique | `degats` | `2D6+5` | `2D6+{Int/8}` | 9 | 17 |
| 4 | Lame de mana | `degats` | `2D8+5` | `2D8+{Int/8}` | 11 | 19 |
| 4 | Ralentissement | `buffs.Ag` | `-9` | `-4-{Int/8}` | -6 | -14 |
| 4 | Rune de vigueur | `buffs.F` | `12` | `6+{Int/7}` | 8 | 17 |
| 5 | Bouclier partagé | `buffs.R` | `13` | `6+{Int/7}` | 8 | 17 |
| 5 | Brûlure de mana | `regen_pm` | `-3` | `-1-{Int/25}` | -1 | -4 |
| 5 | Éclair de bataille | `degats` | `3D8+4` | `3D8+{Int/12}` | 14.5 | 19.5 |
| 6 | Absorption | `degats` | `3D8+6` | `3D8+{Int/8}` | 15.5 | 23.5 |
| 6 | Tourbillon arcanique | `degats` | `2D8+4` | `2D8+{Int/12}` | 10 | 15 |
| 7 | Cage de force | `buffs.Ag` | `-13` | `-6-{Int/8}` | -8 | -16 |
| 7 | Décharge | `degats` | `2D8+6` | `2D8+{Int/10}` | 11 | 17 |
| 7 | Lance arcanique | `degats` | `3D10+7` | `3D10+{Int/8}` | 18.5 | 26.5 |
| 7 | Égide de bataille | `buffs.R` | `11` | `5+{Int/10}` | 7 | 13 |
| 8 | Bombardement | `degats` | `3D8+4` | `3D8+{Int/15}` | 14.5 | 18.5 |
| 8 | Frappe runique | `degats` | `4D10+6` | `4D10+{Int/10}` | 24 | 30 |
| 8 | Recharge | `pm` | `22` | `11+{Int/6}` | 14 | 24 |
| 8 | Vide arcanique | `degats_pm` | `2D8+1` | `2D8+{Int/30}` | 9 | 11 |
| 9 | Armure runique | `buffs.R` | `21` | `10+{Int/6}` | 13 | 23 |
| 9 | Sceau de silence | `regen_pm` | `-5` | `-2-{Int/20}` | -3 | -6 |
| 9 | Tempête arcanique | `degats` | `5D10+10` | `5D10+{Int/7}` | 29.5 | 38.5 |
| 10 | Lame du mage-guerrier | `degats` | `6D10+12` | `6D10+{Int/6}` | 36 | 46 |
| 10 | Nova arcanique | `degats` | `3D8+7` | `3D8+{Int/10}` | 15.5 | 21.5 |

## menestrel

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Chanson à boire | `buffs.Vol` | `8` | `4+{Cha/8}` | 6 | 14 |
| 1 | Coup de luth | `degats` | `1D8+3` | `1D8+{Cha/10}` | 6.5 | 12.5 |
| 1 | Note discordante | `buffs.Vol` | `-6` | `-3-{Cha/10}` | -5 | -11 |
| 2 | Berceuse | `buffs.Ag` | `-7` | `-3-{Cha/8}` | -5 | -13 |
| 2 | Mélodie apaisante | `regen_pv` | `2` | `1+{Cha/30}` | 1 | 3 |
| 2 | Satire | `regen_pm` | `-2` | `-1-{Cha/30}` | -1 | -3 |
| 3 | Air de bravoure | `buffs.F` | `7` | `3+{Cha/10}` | 5 | 11 |
| 3 | Cri strident | `degats` | `2D6+3` | `2D6+{Cha/12}` | 8 | 13 |
| 4 | Accord dissonant | `degats` | `2D8+5` | `2D8+{Cha/8}` | 11 | 19 |
| 4 | Chant de repos | `pm` | `14` | `7+{Cha/6}` | 10 | 20 |
| 4 | Charme du barde | `buffs.Int` | `-9` | `-4-{Cha/8}` | -6 | -14 |
| 5 | Lame du conteur | `degats` | `3D8+4` | `3D8+{Cha/12}` | 14.5 | 19.5 |
| 5 | Requiem | `regen_pv` | `-5` | `-2-{Cha/15}` | -3 | -7 |
| 6 | Sérénade | `pv` | `30` | `15+{Cha/4}` | 20 | 35 |
| 6 | Tonnerre de tambour | `degats` | `2D6+5` | `2D6+{Cha/10}` | 9 | 15 |
| 7 | Chanson de geste | `buffs.F` | `11` | `5+{Cha/10}` | 7 | 13 |
| 7 | Danse macabre | `buffs.Vol` | `-13` | `-6-{Cha/8}` | -8 | -16 |
| 7 | Ritournelle | `buffs.Cha` | `19` | `9+{Cha/6}` | 12 | 22 |
| 8 | Complainte | `regen_pm` | `-4` | `-2-{Cha/30}` | -2 | -4 |
| 8 | Crescendo | `degats` | `4D10+6` | `4D10+{Cha/10}` | 24 | 30 |
| 8 | Hymne de victoire | `buffs.Vol` | `17` | `8+{Cha/7}` | 10 | 19 |
| 8 | Opéra | `degats` | `3D8+4` | `3D8+{Cha/15}` | 14.5 | 18.5 |
| 9 | Chant de vie | `pv` | `25` | `12+{Cha/5}` | 16 | 28 |
| 9 | Symphonie | `degats` | `5D10+10` | `5D10+{Cha/7}` | 29.5 | 38.5 |
| 9 | Voix de sirène | `buffs.Vol` | `-15` | `-7-{Cha/8}` | -9 | -17 |
| 10 | Cantate des héros | `buffs.F` | `14` | `7+{Cha/10}` | 9 | 15 |
| 10 | Dernière note | `degats` | `5D10+12` | `5D10+{Cha/6}` | 30.5 | 40.5 |

## moine

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Balayage de jambe | `buffs.Ag` | `-6` | `-3-{Vol/10}` | -5 | -11 |
| 1 | Paume tranchante | `degats` | `1D8+3` | `1D8+{Ag/10}` | 6.5 | 12.5 |
| 1 | Respiration du lotus | `buffs.Vol` | `8` | `4+{Vol/8}` | 6 | 14 |
| 2 | Coup du dragon | `degats` | `2D6+3` | `2D6+{Ag/12}` | 8 | 13 |
| 2 | Main apaisante | `pv` | `18` | `9+{Vol/4}` | 14 | 29 |
| 2 | Toucher des méridiens | `degats_pm` | `1D6+1` | `1D6+{Vol/30}` | 3.5 | 5.5 |
| 3 | Roue du vent | `degats` | `1D8+4` | `1D8+{Ag/10}` | 6.5 | 12.5 |
| 4 | Esprit clair | `buffs.Vol` | `12` | `6+{Vol/7}` | 8 | 17 |
| 4 | Frappe du tigre | `buffs.Ag` | `-9` | `-4-{Vol/8}` | -6 | -14 |
| 4 | Poing de pierre | `degats` | `2D8+5` | `2D8+{Ag/8}` | 11 | 19 |
| 4 | Posture de la montagne | `buffs.R` | `15` | `7+{Vol/6}` | 10 | 20 |
| 5 | Chant du monastère | `buffs.Vol` | `9` | `4+{Vol/10}` | 6 | 12 |
| 5 | Coup du serpent | `regen_pm` | `-3` | `-1-{Vol/25}` | -1 | -4 |
| 5 | Paume de lumière | `degats` | `3D8+4` | `3D8+{Ag/12}` | 14.5 | 19.5 |
| 6 | Mille poings | `degats` | `3D6+6` | `3D6+{Ag/8}` | 12.5 | 20.5 |
| 6 | Sceau d'harmonie | `regen_pv` | `3` | `1+{Vol/25}` | 1 | 4 |
| 7 | Corps de bronze | `buffs.R` | `19` | `9+{Vol/6}` | 12 | 22 |
| 7 | Frappe de l'âme | `degats` | `3D10+7` | `3D10+{Ag/8}` | 18.5 | 26.5 |
| 7 | Pied du phénix | `degats` | `3D10+7` | `3D10+{Ag/8}` | 18.5 | 26.5 |
| 8 | Onde de choc | `degats` | `2D8+6` | `2D8+{Ag/10}` | 11 | 17 |
| 8 | Point de pression | `buffs.F` | `-14` | `-7-{Vol/8}` | -9 | -17 |
| 8 | Souffle de vie | `pv` | `23` | `11+{Vol/5}` | 15 | 27 |
| 9 | Brise-esprit | `regen_pm` | `-5` | `-2-{Vol/20}` | -3 | -6 |
| 9 | Danse des mille mains | `degats` | `3D8+6` | `3D8+{Ag/10}` | 15.5 | 21.5 |
| 9 | Paix du sage | `buffs.Vol` | `13` | `6+{Vol/10}` | 8 | 14 |
| 9 | Poing du ciel | `degats` | `4D10+9` | `4D10+{Ag/7}` | 24 | 33 |
| 10 | Paume du néant | `degats` | `5D10+12` | `5D10+{Ag/6}` | 30.5 | 40.5 |

## necromancien

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Linceul | `buffs.R` | `8` | `4+{Int/8}` | 6 | 14 |
| 1 | Malaise | `buffs.R` | `-6` | `-3-{Vol/10}` | -5 | -11 |
| 1 | Sangsue | `degats` | `1D8+3` | `1D8+{Int/10}` | 6.5 | 12.5 |
| 1 | Toucher glacé | `degats` | `1D8+3` | `1D8+{Int/10}` | 6.5 | 12.5 |
| 2 | Murmure des morts | `regen_pm` | `-2` | `-1-{Vol/30}` | -1 | -3 |
| 2 | Peste | `regen_pv` | `-3` | `-1-{Vol/15}` | -2 | -6 |
| 2 | Trait d'os | `degats` | `2D6+3` | `2D6+{Int/12}` | 8 | 13 |
| 3 | Nuage pestilentiel | `degats` | `2D6+3` | `2D6+{Int/12}` | 8 | 13 |
| 4 | Carapace d'os | `buffs.R` | `15` | `7+{Int/6}` | 10 | 20 |
| 4 | Lance d'ombre | `degats` | `2D8+5` | `2D8+{Int/8}` | 11 | 19 |
| 4 | Siphon d'âme | `degats_pm` | `2D6` | `2D{Vol/7}` | 3 | 12 |
| 4 | Vampirisme | `degats` | `2D8+5` | `2D8+{Int/8}` | 11 | 19 |
| 5 | Explosion de cadavre | `degats` | `2D6+5` | `2D6+{Int/10}` | 9 | 15 |
| 5 | Main du tombeau | `buffs.Ag` | `-10` | `-5-{Vol/10}` | -7 | -13 |
| 5 | Pacte de sang noir | `degats` | `3D8+8` | `3D8+{Int/6}` | 16.5 | 26.5 |
| 5 | Énergie sombre | `pm` | `16` | `8+{Int/6}` | 11 | 21 |
| 6 | Souffle de la tombe | `degats` | `2D6+5` | `2D6+{Int/10}` | 9 | 15 |
| 7 | Doigt de mort | `degats` | `3D10+7` | `3D10+{Int/8}` | 18.5 | 26.5 |
| 7 | Moisson d'âmes | `degats` | `3D10+7` | `3D10+{Int/8}` | 18.5 | 26.5 |
| 7 | Terreur | `buffs.Vol` | `-13` | `-6-{Vol/8}` | -8 | -16 |
| 8 | Fléau | `degats` | `3D8+4` | `3D8+{Int/15}` | 14.5 | 18.5 |
| 8 | Malédiction de la liche | `regen_pm` | `-4` | `-2-{Vol/30}` | -2 | -4 |
| 8 | Peau de cadavre | `buffs.R` | `20` | `10+{Int/6}` | 13 | 23 |
| 9 | Banquet du vampire | `degats` | `5D10+10` | `5D10+{Int/7}` | 29.5 | 38.5 |
| 9 | Nuée de spectres | `degats` | `3D8+4` | `3D8+{Int/15}` | 14.5 | 18.5 |
| 9 | Rituel de mort | `degats` | `5D10+10` | `5D10+{Int/7}` | 29.5 | 38.5 |
| 9 | Ténèbres dévorantes | `degats` | `4D10+9` | `4D10+{Int/7}` | 24 | 33 |
| 10 | Hiver éternel | `buffs.Ag` | `-16` | `-8-{Vol/8}` | -10 | -18 |
| 10 | Mot de mort | `degats` | `5D10+12` | `5D10+{Int/6}` | 30.5 | 40.5 |

## paladin

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Bouclier de la foi | `buffs.Vol` | `4` | `2+{Vol/15}` | 3 | 7 |
| 1 | Châtiment léger | `buffs.Vol` | `-6` | `-3-{Vol/10}` | -5 | -11 |
| 1 | Coup béni | `degats` | `1D8+3` | `1D8+{F/10}` | 6.5 | 12.5 |
| 2 | Bénédiction de l'acier | `buffs.F` | `9` | `4+{Vol/7}` | 6 | 15 |
| 2 | Frappe du juste | `degats` | `2D6+3` | `2D6+{F/12}` | 8 | 13 |
| 2 | Prière de guérison | `pv` | `18` | `9+{Vol/4}` | 14 | 29 |
| 4 | Aura de courage | `buffs.Vol` | `8` | `4+{Vol/10}` | 6 | 12 |
| 4 | Soins du champ de bataille | `regen_pv` | `3` | `1+{Vol/20}` | 2 | 5 |
| 5 | Brûlure sacrée | `regen_pv` | `-5` | `-2-{Vol/15}` | -3 | -7 |
| 5 | Frappe du croisé | `degats` | `3D8+4` | `3D8+{F/12}` | 14.5 | 19.5 |
| 5 | Égide | `buffs.R` | `13` | `6+{Vol/7}` | 8 | 17 |
| 6 | Mains de lumière | `pv` | `18` | `9+{Vol/6}` | 12 | 22 |
| 7 | Bannissement | `degats_pm` | `2D8` | `2D{Vol/7}` | 3 | 12 |
| 7 | Grâce restauratrice | `pv` | `34` | `17+{Vol/3}` | 23 | 43 |
| 7 | Lame de l'aube | `degats` | `3D10+7` | `3D10+{F/8}` | 18.5 | 26.5 |
| 7 | Rempart sacré | `buffs.R` | `19` | `9+{Vol/6}` | 12 | 22 |
| 8 | Colère divine | `degats` | `3D8+4` | `3D8+{F/15}` | 14.5 | 18.5 |
| 8 | Purge | `regen_pv` | `-6` | `-3-{Vol/20}` | -4 | -7 |
| 8 | Vœu du protecteur | `buffs.R` | `17` | `8+{Vol/7}` | 10 | 19 |
| 9 | Croisade | `buffs.F` | `13` | `6+{Vol/10}` | 8 | 14 |
| 9 | Pénitence | `buffs.F` | `-15` | `-7-{Vol/8}` | -9 | -17 |
| 9 | Vague sainte | `degats` | `3D10+8` | `3D10+{F/8}` | 18.5 | 26.5 |
| 9 | Épée de la foi | `degats` | `4D10+9` | `4D10+{F/7}` | 24 | 33 |
| 10 | Jugement dernier | `degats` | `5D10+12` | `5D10+{F/6}` | 30.5 | 40.5 |
| 10 | Miracle | `pv` | `27` | `13+{Vol/5}` | 17 | 29 |

## pretre

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Bénédiction | `buffs.Vol` | `8` | `4+{Vol/8}` | 6 | 14 |
| 1 | Lumière sainte | `degats` | `1D8+3` | `1D8+{Vol/10}` | 6.5 | 12.5 |
| 1 | Prière de soin | `pv` | `16` | `8+{Vol/4}` | 13 | 28 |
| 1 | Réprimande | `buffs.Vol` | `-6` | `-3-{Vol/10}` | -5 | -11 |
| 2 | Clarté | `pm` | `10` | `5+{Vol/7}` | 7 | 16 |
| 2 | Feu sacré | `regen_pv` | `-3` | `-1-{Vol/15}` | -2 | -6 |
| 2 | Sanctuaire | `buffs.R` | `12` | `6+{Vol/6}` | 9 | 19 |
| 3 | Cercle de guérison | `pv` | `12` | `6+{Vol/7}` | 8 | 17 |
| 4 | Lumière de l'aube | `degats` | `2D6+5` | `2D6+{Vol/8}` | 9 | 17 |
| 4 | Protection divine | `buffs.R` | `12` | `6+{Vol/7}` | 8 | 17 |
| 4 | Purification | `degats_pm` | `2D6` | `2D{Vol/7}` | 3 | 12 |
| 4 | Éclat divin | `degats` | `2D8+5` | `2D8+{Vol/8}` | 11 | 19 |
| 5 | Chaînes de lumière | `buffs.Ag` | `-10` | `-5-{Vol/10}` | -7 | -13 |
| 5 | Guérison majeure | `pv` | `26` | `13+{Vol/4}` | 18 | 33 |
| 5 | Hymne | `buffs.Vol` | `9` | `4+{Vol/10}` | 6 | 12 |
| 6 | Colonne de lumière | `degats` | `3D8+6` | `3D8+{Vol/8}` | 15.5 | 23.5 |
| 7 | Châtiment divin | `degats` | `2D8+6` | `2D8+{Vol/10}` | 11 | 17 |
| 7 | Exorcisme | `regen_pm` | `-4` | `-2-{Vol/25}` | -2 | -5 |
| 7 | Prière de masse | `pv` | `20` | `10+{Vol/6}` | 13 | 23 |
| 7 | Rempart de la foi | `buffs.R` | `19` | `9+{Vol/6}` | 12 | 22 |
| 8 | Bénédiction de masse | `buffs.Vol` | `12` | `6+{Vol/10}` | 8 | 14 |
| 8 | Grâce de l'esprit | `pm` | `22` | `11+{Vol/6}` | 14 | 24 |
| 8 | Jugement céleste | `degats` | `4D10+6` | `4D10+{Vol/10}` | 24 | 30 |
| 8 | Silence sacré | `buffs.Vol` | `-14` | `-7-{Vol/8}` | -9 | -17 |
| 9 | Anathème | `degats_pm` | `2D8+2` | `2D8+{Vol/30}` | 9 | 11 |
| 9 | Lumière purificatrice | `degats` | `5D10+10` | `5D10+{Vol/7}` | 29.5 | 38.5 |
| 9 | Résurgence | `pv` | `42` | `21+{Vol/3}` | 27 | 47 |
| 9 | Vœu de lumière | `buffs.R` | `18` | `9+{Vol/7}` | 11 | 20 |
| 10 | Apothéose | `pv` | `27` | `13+{Vol/5}` | 17 | 29 |
| 10 | Courroux du ciel | `degats` | `3D10+6` | `3D10+{Vol/12}` | 17.5 | 22.5 |

## repurgateur

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Lame d'argent | `degats` | `1D8+3` | `1D8+{Vol/10}` | 6.5 | 12.5 |
| 1 | Sel et cendre | `buffs.Vol` | `-6` | `-3-{Int/10}` | -5 | -11 |
| 1 | Signe noir | `degats_pm` | `1D6` | `1D{Int/5}` | 2.5 | 8.5 |
| 1 | Œil du chasseur de sorcières | `buffs.Vol` | `8` | `4+{Vol/8}` | 6 | 14 |
| 2 | Coup de pieu | `degats` | `2D6+3` | `2D6+{Vol/12}` | 8 | 13 |
| 2 | Eau lustrale | `regen_pv` | `-3` | `-1-{Int/15}` | -2 | -6 |
| 2 | Sang contre sang | `degats` | `2D8+4` | `2D8+{Vol/8}` | 11 | 19 |
| 3 | Chaînes d'argent | `buffs.Ag` | `-8` | `-4-{Int/10}` | -6 | -12 |
| 3 | Flamme noire | `degats` | `2D8+3` | `2D8+{Vol/12}` | 10 | 15 |
| 4 | Croix renversée | `degats` | `2D8+5` | `2D8+{Vol/8}` | 11 | 19 |
| 4 | Garde du chasseur | `buffs.Vol` | `15` | `7+{Vol/6}` | 10 | 20 |
| 4 | Soufre | `degats` | `2D6+5` | `2D6+{Vol/8}` | 9 | 17 |
| 5 | Carreau béni | `degats` | `3D8+4` | `3D8+{Vol/12}` | 14.5 | 19.5 |
| 5 | Fouet de flammes | `degats` | `2D8+5` | `2D8+{Vol/10}` | 11 | 17 |
| 5 | Marque d'argent | `regen_pm` | `-3` | `-1-{Int/25}` | -1 | -4 |
| 5 | Pacte inversé | `buffs.F` | `13` | `6+{Vol/7}` | 8 | 17 |
| 6 | Haleine de l'abîme | `degats` | `2D8+4` | `2D8+{Vol/12}` | 10 | 15 |
| 7 | Brise-sortilège | `degats_pm` | `2D8` | `2D{Int/7}` | 3 | 12 |
| 7 | Lame sanctifiée | `degats` | `3D10+7` | `3D10+{Vol/8}` | 18.5 | 26.5 |
| 7 | Malédiction de l'inquisiteur | `regen_pv` | `-6` | `-3-{Int/15}` | -4 | -8 |
| 8 | Endurance du traqueur | `buffs.R` | `20` | `10+{Vol/6}` | 13 | 23 |
| 8 | Feu de l'enfer retourné | `degats` | `3D8+4` | `3D8+{Vol/15}` | 14.5 | 18.5 |
| 8 | Pieu au cœur | `degats` | `4D10+6` | `4D10+{Vol/10}` | 24 | 30 |
| 8 | Sceau d'entrave | `buffs.Ag` | `-14` | `-7-{Int/8}` | -9 | -17 |
| 9 | Purification par le feu | `regen_pv` | `-7` | `-3-{Int/15}` | -4 | -8 |
| 9 | Tourbillon d'argent | `degats` | `3D8+6` | `3D8+{Vol/10}` | 15.5 | 21.5 |
| 10 | Fléau des démons | `degats` | `5D10+12` | `5D10+{Vol/6}` | 30.5 | 40.5 |
| 10 | Pacte rompu | `degats_pm` | `3D8` | `3D{Int/8}` | 4.5 | 16.5 |

## templier

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Coup réglementaire | `degats` | `1D8+3` | `1D8+{F/10}` | 6.5 | 12.5 |
| 1 | Discipline du rang | `buffs.R` | `8` | `4+{R/8}` | 6 | 14 |
| 1 | Garde de l'ordre | `buffs.R` | `4` | `2+{R/15}` | 3 | 7 |
| 1 | Ordre de halte | `buffs.Ag` | `-6` | `-3-{Vol/10}` | -5 | -11 |
| 2 | Bouclier repoussant | `buffs.F` | `-7` | `-3-{Vol/8}` | -5 | -13 |
| 2 | Frappe du gardien | `degats` | `2D6+3` | `2D6+{F/12}` | 8 | 13 |
| 2 | Rune de résistance | `buffs.R` | `9` | `4+{R/7}` | 6 | 15 |
| 3 | Annulation | `degats_pm` | `1D8+1` | `1D8+{Vol/30}` | 4.5 | 6.5 |
| 3 | Ligne de l'ordre | `degats` | `2D6+3` | `2D6+{F/12}` | 8 | 13 |
| 4 | Chaînes de l'ordre | `buffs.Ag` | `-9` | `-4-{Vol/8}` | -6 | -14 |
| 4 | Lame enflammée | `degats` | `2D8+5` | `2D8+{F/8}` | 11 | 19 |
| 4 | Ordre de bataille | `buffs.R` | `8` | `4+{R/10}` | 6 | 12 |
| 4 | Sceau de garde | `buffs.R` | `15` | `7+{R/6}` | 10 | 20 |
| 5 | Coup de l'inquisition | `degats` | `3D8+4` | `3D8+{F/12}` | 14.5 | 19.5 |
| 5 | Explosion runique | `degats` | `2D8+5` | `2D8+{F/10}` | 11 | 17 |
| 5 | Fer rouge | `regen_pv` | `-5` | `-2-{Vol/15}` | -3 | -7 |
| 6 | Taille du gardien des temples | `degats` | `3D8+6` | `3D8+{F/8}` | 15.5 | 23.5 |
| 6 | Égide runique | `buffs.R` | `17` | `8+{R/6}` | 11 | 21 |
| 7 | Interdit | `buffs.Ag` | `-13` | `-6-{Vol/8}` | -8 | -16 |
| 7 | Lame de foudre | `degats` | `3D10+7` | `3D10+{F/8}` | 18.5 | 26.5 |
| 7 | Restauration de l'ordre | `pv` | `34` | `17+{R/3}` | 23 | 43 |
| 7 | Rotation du templier | `degats` | `2D8+6` | `2D8+{F/10}` | 11 | 17 |
| 8 | Bastion | `buffs.R` | `12` | `6+{R/10}` | 8 | 14 |
| 8 | Jugement de l'ordre | `degats` | `4D10+6` | `4D10+{F/10}` | 24 | 30 |
| 9 | Garde inflexible | `buffs.R` | `21` | `10+{R/6}` | 13 | 23 |
| 9 | Tempête runique | `degats` | `3D8+6` | `3D8+{F/10}` | 15.5 | 21.5 |
| 9 | Épée de l'institution | `degats` | `4D10+9` | `4D10+{F/7}` | 24 | 33 |
| 10 | Rempart de la cité | `buffs.R` | `14` | `7+{R/10}` | 9 | 15 |
| 10 | Sentence capitale | `degats` | `5D10+12` | `5D10+{F/6}` | 30.5 | 40.5 |

## voleur

| niv | compétence | champ | avant | après | à 20 | à 80 |
|---|---|---|---|---|---|---|
| 1 | Chance du gredin | `buffs.Ch` | `8` | `4+{Ch/8}` | 6 | 14 |
| 1 | Coup bas | `buffs.Ag` | `-6` | `-3-{Int/10}` | -5 | -11 |
| 1 | Lame de poche | `degats` | `1D8+3` | `1D8+{Ag/10}` | 6.5 | 12.5 |
| 1 | Sable aux yeux | `buffs.Ag` | `-6` | `-3-{Int/10}` | -5 | -11 |
| 2 | Couteaux de lancer | `degats` | `1D8+3` | `1D8+{Ag/12}` | 5.5 | 10.5 |
| 2 | Croc-en-jambe | `buffs.Ag` | `-7` | `-3-{Int/8}` | -5 | -13 |
| 2 | Esquive du coupe-bourse | `buffs.Ag` | `4` | `2+{Ch/15}` | 3 | 7 |
| 2 | Surin | `degats` | `2D6+3` | `2D6+{Ag/12}` | 8 | 13 |
| 3 | Coup du pavé | `degats` | `2D8+3` | `2D8+{Ag/12}` | 10 | 15 |
| 3 | Pickpocket de combat | `degats_pm` | `1D8+1` | `1D8+{Int/30}` | 4.5 | 6.5 |
| 3 | Poivre des quais | `buffs.Ag` | `-8` | `-4-{Int/10}` | -6 | -12 |
| 4 | Bombe fumigène | `degats` | `2D6+5` | `2D6+{Ag/8}` | 9 | 17 |
| 4 | Cordelette | `buffs.Ag` | `-9` | `-4-{Int/8}` | -6 | -14 |
| 4 | Gouaille | `buffs.Cha` | `12` | `6+{Ch/7}` | 8 | 17 |
| 4 | Lame cachée | `degats` | `2D8+5` | `2D8+{Ag/8}` | 11 | 19 |
| 5 | Coup du lapin | `degats` | `3D8+4` | `3D8+{Ag/12}` | 14.5 | 19.5 |
| 5 | Fiel de crapaud | `regen_pv` | `-5` | `-2-{Int/15}` | -3 | -7 |
| 5 | Pluie de clous | `degats` | `2D8+5` | `2D8+{Ag/10}` | 11 | 17 |
| 5 | Vol à l'arraché | `degats_pm` | `2D6+1` | `2D6+{Int/30}` | 7 | 9 |
| 6 | Cendre au visage | `buffs.Ag` | `-12` | `-6-{Int/8}` | -8 | -16 |
| 6 | Coup de surin | `degats` | `3D8+6` | `3D8+{Ag/8}` | 15.5 | 23.5 |
| 6 | Tourbillon de coutelas | `degats` | `2D8+4` | `2D8+{Ag/12}` | 10 | 15 |
| 7 | Coup de crosse | `buffs.Int` | `-13` | `-6-{Int/8}` | -8 | -16 |
| 7 | Lame du coupe-jarret | `degats` | `3D10+7` | `3D10+{Ag/8}` | 18.5 | 26.5 |
| 7 | Mauvaise fiole | `regen_pm` | `-4` | `-2-{Int/25}` | -2 | -5 |
| 7 | Réseau d'informateurs | `buffs.Int` | `16` | `8+{Ch/7}` | 10 | 19 |
| 8 | Chausse-trappe lancée | `buffs.Ag` | `-14` | `-7-{Int/8}` | -9 | -17 |
| 8 | Coup du maître voleur | `degats` | `4D10+6` | `4D10+{Ag/10}` | 24 | 30 |
| 8 | Disparition dans la foule | `buffs.Ag` | `8` | `4+{Ch/15}` | 5 | 9 |
| 8 | Détrousser l'âme | `degats_pm` | `2D8+1` | `2D8+{Int/30}` | 9 | 11 |
| 8 | Feu grégeois de poche | `degats` | `3D8+8` | `3D8+{Ag/7}` | 15.5 | 24.5 |
| 9 | Bagout | `buffs.Cha` | `13` | `6+{Ch/10}` | 8 | 14 |
| 9 | Coup du prince des voleurs | `degats` | `4D10+9` | `4D10+{Ag/7}` | 24 | 33 |
| 9 | Lame dans la manche | `degats` | `4D10+9` | `4D10+{Ag/7}` | 24 | 33 |
| 9 | Nuage de poivre | `degats` | `3D8+6` | `3D8+{Ag/10}` | 15.5 | 21.5 |
| 10 | Le grand coup | `degats` | `5D10+12` | `5D10+{Ag/6}` | 30.5 | 40.5 |
| 10 | Prestidigitation | `buffs.Ag` | `10` | `5+{Ch/12}` | 6 | 11 |
| 10 | Tempête de couteaux | `degats` | `3D8+7` | `3D8+{Ag/10}` | 15.5 | 21.5 |
| 10 | Voleur d'ombres | `degats_pm` | `3D8` | `3D{Int/8}` | 4.5 | 16.5 |

