# Les morts d'Escolives — l'enquête du rang D

- **Source :** séance Claude Code du 13/10/2026 ; l'Auteur arbitre par questionnaire (§ 1).
- **Créée :** 13/10/2026
- **Statut :** le § 1 **fait foi** (noms, récompense compris) ; le reste du scénario (§ 2) et les textes sont **proposés, non tranchés**. Le contenu en jeu sera construit une fois les images générées (§ 3).

---

## 1. Arbitrage (Auteur, 13/10, questionnaire)

| Point | Décision |
|---|---|
| Rang | premier vampire de l'aventurier, au **rang D**, par une **enquête** (modèle Arnold Paole / Peter Plogojowitz) |
| Lieu | **Escolives**, village au sud d'Auxerre, avec sa nécropole ancienne |
| Issue | un **Strigoï** à combattre, mais le **doute reste** : certains PNJ croient toujours à une maladie |
| Donneur | la **guilde d'Auxerre** |
| Forme | **preuve rapportée** : quête d'apport unique (les ossements du Strigoï) ; la crypte est une salle gardée, comme la nef de Jumièges ; aucun code neuf |
| Monstres | **1 Strigoï + 2 relevés** (morts du village déjà déformés) |
| PNJ du village | le **fossoyeur**, la **guérisseuse**, une **veuve** |
| Images | carte de combat **neuve**, image du village **neuve** (prompts au § 3) |
| PNJ | Gaspard Fouquet (fossoyeur, nain) · Ysolde Vernier (guérisseuse, elfe) · Perrine Vaudin (veuve, hobbit ; son mari Jehan, premier mort) — **validés** |
| Récompense | **120 XP + 30 000 cuivres** |
| Jehan | qu'il soit l'un des relevés n'est **jamais dit** |
| Images de PNJ | **portraits seuls**, pas de variante de présence |

## 2. Scénario (proposé)

**Chaîne :**
1. **Bureau du maître de guilde d'Auxerre.** Gautier de Valcroix confie la quête d'apport `quete:les_morts_d_escolives` : « Rapportez-moi la preuve. » Quête unique, rang D, objet à remettre : `item:strigoi` (Ossements de Strigoï, butin par défaut du monstre).
2. **Escolives.** Lieu sur la carte de France, au sud d'Auxerre, sur l'Yonne. Trois PNJ y sont présents tant que la quête n'est pas réussie.
3. **La crypte de la nécropole.** Une salle gardée (`battle_map` + donjon). Le fossoyeur l'ouvre par le service `acces`, à condition que la quête soit active. Le combat oppose l'aventurier à 1 Strigoï et 2 relevés.
4. **Retour au bureau.** Le joueur remet les ossements à Gautier. La quête est réussie, avec XP et prime.
5. **Après.** À Escolives, la guérisseuse n'est toujours pas convaincue et la veuve ne pardonne pas ; le fossoyeur dort de nouveau. Rien ne tranche.

**PNJ (validés, Auteur 13/10) :**

| Rôle | Lignée | Nom proposé | Ce qu'il croit |
|---|---|---|---|
| Fossoyeur | nain | Gaspard Fouquet | Il a rouvert les tombes et a vu les corps gonflés, le sang frais à la bouche. Pour lui, c'est un Strigoï. Il garde la porte de la crypte. |
| Guérisseuse | elfe | Ysolde Vernier | Elle parle de fièvre et d'un puits souillé. Avant comme après le combat, elle ne croit pas aux vampires : « Vous avez tué une chose. Vous n'avez pas guéri le village. » |
| Veuve | hobbit | Perrine Vaudin | Son mari Jehan a été le premier mort, et c'est lui qu'on accuse. Elle refuse qu'on brûle son corps. Après le combat, elle ne sait pas si ce qu'on a tué était encore Jehan. |

**Le doute** : l'un des deux relevés pourrait être Jehan ; ce n'est **jamais dit** (Auteur).

**Récompenses (Auteur)** : 120 XP et 30 000 cuivres, comme l'escorte des bûcherons du même rang.

## 3. Prompts d'images à produire

Style : bloc 0.1 de `docs/prompts_images.md`, à ajouter à la fin de chaque prompt.

### 3.1 Carte de combat — la crypte de la nécropole

Fichier : `templates/resources/battle_maps/crypte_de_la_necropole_d_escolives.jpg` · format **portrait 9:16**, comme `abbaye_de_jumieges_nef.jpg` (720×1456).

> Carte de combat de jeu de rôle tactique, vue strictement du dessus, format portrait vertical. Une crypte voûtée creusée sous une nécropole très ancienne : un couloir d'entrée au sud, avec un escalier de pierre qui descend depuis la surface, puis une salle principale aux murs de pierre sèche. Des sarcophages de pierre alignés, certains au couvercle repoussé ou brisé, des niches funéraires creusées dans les murs, des ossements épars, de la terre fraîchement remuée, deux tombes ouvertes. Au nord, une petite salle plus sombre, où des os brisés sont entassés comme une litière. Torches éteintes, flaques d'eau, racines qui percent la voûte. Lumière froide et rare, ombres profondes. Un quadrillage fin et régulier de cases carrées couvre toute l'image, et une petite flèche indique le nord en haut à droite. Pas de personnages. [0.1]

### 3.2 Le village d'Escolives

Fichier : `templates/resources/towns/escolives.jpg` · **paysage 16:9**.

> Un petit village fortifié de palissades, dans un vallon de Bourgogne, au bord d'une rivière, l'Yonne, dans un monde médiéval fantastique. Maisons de pierre blonde aux toits de tuiles, vignes sur les coteaux, un lavoir. À la lisière du village, une nécropole très ancienne : rangées de sarcophages de pierre affleurant l'herbe, quelques tombes fraîchement rouvertes, un tas de terre. Soir d'automne, ciel bas. Des villageois inquiets se tiennent en petits groupes. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. En proportions égales, les humains ne sont pas plus nombreux que les autres. [0.1]

### 3.3 Portraits (dossier `templates/resources/pnj/`, paysage 16:9)

Le nom du personnage ne figure jamais dans un prompt (§ 2 de `docs/prompts_images.md`).

- **`fossoyeur_Gaspard_Fouquet_nain_m.jpg`** — Un nain, nettement plus petit qu'un humain, mains et tête grandes pour sa taille, d'âge mûr, trapu et voûté, barbe grise taillée court et terre sous les ongles. C'est le fossoyeur d'un village de Bourgogne. Il s'appuie sur une pelle, devant une tombe rouverte d'une nécropole ancienne. Tenue de travail usée : chemise de lin, tablier de cuir, sabots crottés. Regard grave et sûr de lui : il a vu ce qu'il a vu. [0.1 bis]
- **`guerisseuse_Ysolde_Vernier_elfe_f.jpg`** — Une elfe aux longues oreilles pointues, d'apparence d'une quarantaine d'années, sèche et droite, cheveux châtains tressés. C'est la guérisseuse du village. Elle se tient dans sa maison, entre des bouquets d'herbes qui sèchent et des fioles, et tient une coupe d'eau trouble qu'elle examine. Regard sceptique et las. [0.1 bis]
- **`veuve_Perrine_Vaudin_hobbit_f.jpg`** — Une hobbit, toute petite taille d'adulte, pieds nus, jeune, ronde, les yeux rougis, vêtue de deuil simple. C'est une veuve de village. Elle se tient sur le seuil de sa maison, les bras croisés sur un châle, devant une porte où l'on a cloué de l'aubépine. Regard dur et blessé. [0.1 bis]

### 3.4 Monstres (gabarit § 3 de `docs/prompts_images.md`, dossier `monsters/`)

- **`strigoi_transparent.png`** — prompt déjà donné au § 8 de `docs/lore/monde/20261012_les_vampires_de_telluris.md`.
- **`abhartach_transparent.png`** — Illustration en pied d'un **Abhartach**, un roi-nain tyran revenu de sa tombe : nain mort-vivant trapu et massif, couronne de fer rouillée, cotte de mailles en lambeaux, peau grise et terreuse, terre et racines accrochées à sa barbe, un bol de bronze taché de sang à la main, une masse d'armes à l'autre. Chair desséchée, lueur froide dans les orbites. Fond parfaitement uni et plat, magenta pur. [0.1]
- **`penanggalan_transparent.png`** — Illustration en pied d'une **Penanggalan** : une tête de femme aux longs cheveux noirs mouillés qui vole seule, traînant sous elle ses viscères luisants ; des écailles et des traces de morsures de poissons sur ses joues, des algues prises dans ses cheveux. Elle est en vol, regard affamé. Fond parfaitement uni et plat, vert vif pur. [0.1]
- **`draugr_transparent.png`** — Illustration en pied d'un **Draugr**, un mort-vivant des terres du Nord : grand cadavre gonflé, à la peau bleu-noir, vêtu d'une broigne et d'une fourrure pourries, une hache à la main, de la terre de tertre sur les épaules, des yeux pâles qui luisent. Chair desséchée, lueur froide dans les orbites. Fond parfaitement uni et plat, magenta pur. [0.1]

## 4. À construire une fois les images livrées

- un générateur `dev/gen_enquete_escolives.py`, qui produit **un seul** `jsons/enquete_escolives_a_importer.json` :
  - `lieu:escolives` (carte de France), avec ses PNJ et leurs conditions de présence ;
  - `lieu:crypte_de_la_necropole_d_escolives` (grille tirée de l'image) ;
  - `donjon:crypte_d_escolives`, la connexion, les trois `pnj:*` ;
  - Gautier relu du dump, avec le seul service `apport` ajouté ;
- le passage au linter de dialogues, des tests, puis l'import.
