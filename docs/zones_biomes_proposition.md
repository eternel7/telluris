# Zones d'influence par biome — proposition à valider

> Statut : **PROPOSITION** (16/11/2026), rien n'est en base. Une fois validée, elle sert de source
> au générateur (zones, essences, espèces, repeinte des cartes africaines), dans UN seul fichier à
> importer.

## Règles retenues (Auteur, 15-16/11)

- **Une zone par biome**, jamais par lieu : nom et `_id` **génériques**, aucune référence à une région,
  un pays, une île, un massif ou un fleuve réels. La zone décrit les particularités du milieu.
- Le filtre `regions` reste dans le code **en réserve** (cas d'un endémique isolé) ; l'amorçage n'en
  écrit plus.
- Les 88 zones existantes gardent leur `_id` (placements et rencontres y pointent ; aucune
  migration). Les biomes tempérés existants (`foret_feuillus`, `lac`, `riviere`…) restent **tempérés**.
- Chaque zone neuve copie `table_evenements` et `modificateurs` de son **modèle** (zone existante la
  plus proche), puis ajuste `danger` et `deplacement` ; `terrain_tags` pris dans le vocabulaire des
  battle maps existantes.

Légende : ✓ = déjà en base · ★ = à créer · **essence ★** = chaîne de bois complète à créer
(arbre, tronc, gros rondin, rondin, petit rondin, branche + recettes de découpe, comme les 14
essences actuelles).

## 1. Climats secs (12)

| Zone (`_id`) | Modèle | Terrain | Espèces | Ressources |
|---|---|---|---|---|
| Maquis (`maquis`) | `garrigue` | broussaille, colline, pierre, aride | ✓ sanglier, serpent, renard, lievre, rapaces · ✓ satyre | essence ★ arbousier · ★ baies d'arbousier · ✓ Herbes_a_bruler, Herbes_medicinales |
| Pinède sèche (`pinede_seche`) | `foret_coniferes` | foret, conifere, aride, pierre | ✓ loup, sanglier, serpent, araignee · ✓ dryade | essence ★ pin · ★ résine de pin · ✓ graines |
| Forêt de chênes-lièges (`foret_chenes_lieges`) | `foret_feuillus` | foret, bois, clariere, aride | ✓ cerf, sanglier, renard, ecureuil · ✓ homme_arbre | essence ★ chêne-liège · ★ liège · ✓ Herbes_medicinales |
| Cédraie d'altitude (`cedraie_altitude`) | `contreforts` | foret, montagne, conifere, pente | ★ singes · ✓ fauves, ours, rapaces · ✓ oreade | essence ★ cèdre · ★ résine de cèdre · ✓ Eau_de_source |
| Oliveraie (`oliveraie`) | `verger` | verger, culture, rural, colline | ✓ petits_animaux_divers, serpent, renard | essence ★ olivier · ★ olives · ✓ Herbes_a_bruler |
| Palmeraie (`palmeraie`) | `oasis` | oasis, eau, vegetation, desert | ✓ serpent, scorpion_geant, nuee_de_scarabees · ✓ aicha_kandicha, jann | essence ★ palmier · ★ dattes · ✓ Eau_de_source |
| Steppe aride (`steppe_aride`) | `steppe` | steppe, plaine, herbe, aride | ★ antilopes · ✓ loup, rapaces, lievre · ✓ centaure | ★ alfa (fibre) · ✓ Feuilles_d_absinthe, graines |
| Contreforts arides (`contreforts_arides`) | `contreforts` | montagne, colline, roche, pente, aride | ✓ scorpion_geant, serpent, fauves, oiseaux_de_proies · ✓ boukhnoun, ghul_des_sables | essence ★ genévrier · ✓ pierre, fer, Sel_gemme |
| Steppe épineuse à acacias (`steppe_epineuse`) | `savane` | savane, plaine, broussaille, aride | ★ antilopes, ★ hyènes, ★ autruches · ✓ fauves, rapaces · ✓ nasnas | essence ★ acacia · ★ gomme d'acacia · ✓ graines |
| Désert froid (`desert_froid`) | `hamada` | desert, roche, froid, plateau | ✓ loup, rapaces, vers_des_sables · ✓ troll | essence ★ saxaoul · ✓ Sel_gemme, pierre |
| Désert côtier brumeux (`desert_brumeux`) | `desert` | desert, sable, cote, brume | ★ antilopes · ✓ nuee_de_scarabees, serpent, scorpion_geant · ✓ silat | ★ lichen des brumes · ✓ Sel_gemme |
| Désert de succulentes (`desert_succulentes`) | `desert` | desert, sable, vegetation, aride | ✓ serpent, scorpion_geant, araignee_geante, rapaces · ✓ serpopard | ★ sève de succulente · ★ épines · ✓ Herbes_medicinales |

## 2. Tropiques (10)

| Zone (`_id`) | Modèle | Terrain | Espèces | Ressources |
|---|---|---|---|---|
| Fleuve tropical (`fleuve_tropical`) | `riviere` | riviere, eau, berge, roseau, tropical | ✓ crocodile, rapaces · ★ hippopotames · ✓ fils_de_sobek, naiade | ★ papyrus · ★ lotus · essence ★ acacia · ✓ Eau_de_source |
| Marécage tropical (`marecage_tropical`) | `marais` | marais, eau, boue, tropical | ✓ crocodile, serpent_geant · ★ hippopotames · ✓ bunyip, gobelin_des_marais | ★ papyrus · ✓ Herbes_medicinales, Racine_de_mandragore |
| Lac alcalin (`lac_alcalin`) | `lac` | lac, eau, berge, sel, tropical | ★ flamants · ✓ rapaces, crocodile · ★ hyènes | ★ natron · ✓ Sel_gemme |
| Savane arborée (`savane_arboree`) | `savane` | savane, plaine, herbe, tropical | ★ éléphants, ★ antilopes, ★ buffles, ★ hyènes · ✓ fauves · ✓ grootslang | essence ★ baobab · ★ fruit du baobab · ✓ graines |
| Fourré épineux (`fourre_epineux`) | `garrigue` | broussaille, aride, tropical, pierre | ★ singes · ✓ serpent, araignee_geante, rapaces | essence ★ acacia · ★ épines · ✓ Herbes_medicinales |
| Forêt équatoriale (`foret_equatoriale`) | `jungle` | jungle, foret, tropical | ★ grands singes, ★ éléphants · ✓ fauves, serpent_geant, araignee_geante · ✓ uturuncu | essence ★ acajou · essence ★ ébène · ★ lianes · ✓ Herbes_medicinales |
| Forêt-galerie (`foret_galerie`) | `foret_temperee_humide` | foret, riviere, berge, tropical | ★ singes · ✓ crocodile, serpent, fauves · ✓ naiade | essence ★ acajou · ★ figues · ✓ Eau_de_source |
| Forêt tropicale sèche (`foret_tropicale_seche`) | `foret_feuillus` | foret, bois, aride, tropical | ✓ fauves, serpent, sanglier · ★ singes · ✓ nahual | essence ★ teck · ★ tamarin · ✓ Herbes_a_bruler |
| Prairie d'altitude tropicale (`prairie_altitude_tropicale`) | `alpage` | montagne, herbe, pente, brume, tropical | ★ singes · ✓ rapaces, oiseaux_de_proies · ✓ griffon | ★ lobélie géante · ✓ Herbes_medicinales, Eau_de_source |
| Rizière (`riziere`) | `terres_cultivees` | culture, eau, rural, marais | ★ buffles · ✓ serpent, rat_geant, petits_animaux_divers | ★ riz · ✓ Eau_de_source |

## 3. Froid et tempéré (4)

| Zone (`_id`) | Modèle | Terrain | Espèces | Ressources |
|---|---|---|---|---|
| Forêt mixte de montagne (`foret_mixte_montagne`) | `contreforts` | foret, montagne, conifere, bois, pente | ✓ ours, loup, cerf, ecureuil, rapaces · ✓ troll | essence ★ sapin · ✓ Hetre, Erable · ✓ Seve_de_chene |
| Lande arctique (`lande_arctique`) | `toundra` | toundra, neige, froid, lande | ★ rennes, ★ bœufs musqués · ✓ loup, ours_polaire · ✓ draugr | ★ lichen · ✓ Bouleau (nain) · ✓ plumes |
| Prairie à hautes herbes (`prairie_hautes_herbes`) | `plaine_ouverte` | plaine, herbe, champ, steppe | ★ bisons · ✓ loup, cheval, rapaces, lievre · ✓ centaure | ✓ graines, Herbes_medicinales, Fleur_de_souci |
| Haut plateau froid (`haut_plateau_froid`) | `plateau` | plateau, herbe, roche, froid, neige | ★ yacks · ✓ loup, rapaces, oiseaux_de_proies · ✓ mammouth | ✓ Sel_gemme, pierre · ★ lichen |

## 4. Mers et côtes (4)

| Zone (`_id`) | Modèle | Terrain | Espèces | Ressources |
|---|---|---|---|---|
| Récif corallien (`recif_corallien`) | `recif` | mer, recif, eau, cote, tropical | ✓ poissons_mammiferes_marins, serpent_geant · ✓ sirene, triton | ★ corail · ★ nacre |
| Mer froide (`mer_froide`) | `mer_cotiere` | mer, eau, froid, glace | ★ phoques et morses · ✓ poissons_mammiferes_marins, ours_polaire · ✓ polar_kraken | ★ huile de phoque · ✓ Sel_gemme |
| Côte tropicale (`cote_tropicale`) | `littoral` | cote, mer, plage, sable, tropical | ✓ crocodile, rapaces · ★ tortues marines · ✓ nereide | essence ★ cocotier · ★ noix de coco · ★ nacre |
| Forêt claire sèche (`foret_claire_seche`) | `foret_feuillus` | foret, clariere, aride, herbe | ✓ fauves, serpent, araignee · ★ antilopes · ✓ dryade | essence ★ eucalyptus · ★ huile d'eucalyptus · ✓ Herbes_medicinales |

## 5. Contenu à créer (récapitulatif)

- **Essences ★ (16)** : arbousier, pin, chêne-liège, cèdre, olivier, palmier, genévrier, acacia, saxaoul,
  baobab, acajou, ébène, teck, sapin, cocotier, eucalyptus — soit environ 96 items (6 par essence)
  et leurs recettes de découpe.
- **Ressources ★ (26)** : baies d'arbousier, résine de pin, liège, résine de cèdre, olives, dattes,
  alfa, gomme d'acacia, lichen des brumes, sève de succulente, épines, papyrus, lotus, natron,
  fruit du baobab, lianes, figues, tamarin, lobélie géante, riz, lichen, corail, nacre, huile de
  phoque, noix de coco, huile d'eucalyptus.
- **Espèces ★ (15, faune ordinaire, groupées comme `fauves` ou `rapaces`)** : singes, grands singes,
  antilopes, hyènes, autruches, hippopotames, flamants, éléphants, buffles, rennes, bœufs musqués,
  bisons, yacks, phoques et morses, tortues marines. Statistiques calées sur une espèce proche
  existante, carcasse (`item:<espece>`) générée comme les autres.

## 6. Repeinte des cartes déjà peintes (table retenue)

| Lieu | Ancienne zone | Nouvelle zone | Placements |
|---|---|---|---|
| `lieu:afrique_du_nord` | `lac` (le grand fleuve) | `fleuve_tropical` | 14 |
| `lieu:afrique_du_nord` | `jungle` (bande du bord sud) | `steppe_epineuse` | 9 |
| `lieu:afrique_du_nord` | `contreforts` | `contreforts_arides` | 38 |
| `lieu:egypte` | `lac` | `fleuve_tropical` | 4 |
| `lieu:egypte` | `montagne` | `contreforts_arides` | 6 |

Les `zones` des `rencontres` / `ressources` de ces deux lieux suivent la même table. Inchangés :
`haute_montagne`, `desert`, `erg`, `delta`, `oasis`. Le défaut `crocodile` de `lac` (réservé par
région dans l'amorçage du 15/11) passe sans région sur `fleuve_tropical`, et quitte `lac`.

## 7. Points à trancher

- Noms des espèces neuves en **groupes** (« Antilopes », comme « Fauves ») ou en **individus**
  (« Gazelle », « Oryx »…).
- Essences : chaîne **complète** (6 calibres, comme les feuillus d'Europe) ou **réduite** (arbre +
  rondin + branche) pour les essences secondaires.
- Créatures des mythes ajoutées ci-dessus (satyre, aicha_kandicha, grootslang, nahual…) : les garder
  comme **défauts** de zone, ou les réserver aux placements (contenu propre, une créature à un
  endroit précis).
