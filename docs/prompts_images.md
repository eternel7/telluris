# Prompts d'images — Telluris

Gabarits de prompts pour générer les illustrations du jeu (Gemini). Chaque gabarit est une **phrase à trous** : les `{champs}` sont remplis depuis la base (dump), ce qui permet de produire des lots par script.

## 0. Règles communes

⚠️ **Tout prompt livré COMMENCE par « Réalise l'image de… »** (Auteur, 14/10/2026) — « Réalise l'image de la clairière… », « Réalise l'image d'un ogre… », « Réalise l'image des… ».

### 0.1 Bloc de style (ajouté à la fin de CHAQUE prompt)

⚠️ **Écrit EN ENTIER dans chaque prompt livré**, jamais en renvoi (`[0.1]`) : un prompt se copie-colle tel quel (Auteur, 13/10/2026). Idem pour 0.1 bis et la phrase de foule.

> Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.

### 0.2 Foule de Telluris (quand la scène est peuplée)

> Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation.

(Phrase d'origine de l'auteur, à garder **telle quelle** dans tout prompt peuplé — portraits de tenanciers compris.) ⚠️ **Répartition ÉGALE entre les cinq Lignées** (consigne de l'auteur, 10/10/2026) : avec un tenancier humain, le modèle peuplait la rue d'humains — le prompt précise « en proportions égales… les humains ne sont pas plus nombreux que les autres, même si le tenancier est humain » (`FOULE_FR` / `FOULE` de `dev/gen_images_magasins.py`).

- ⚠️ **Combien de monde** (Auteur, 11/11/2026 : rue toujours bondée) : `FOULE` ne dit que QUI passe ; la densité est tirée par lieu (`animation_rue`, `ANIMATIONS_RUE` pondérées : presque déserte → bondée, la cohue en exception), façades ET auberges.
- ⚠️ **Échelle du tenancier en façade** (même date : tenancier peint plus grand que tout le monde, pire en nain/hobbit — le portrait joint est un gros plan dont le modèle gardait la taille) : `echelle_scene` pose un repère absolu (humain = un tiers de l'image), la taille de la lignée, « jamais la plus grande figure », plan moyen.
- ⚠️ **Âge des tenanciers** (10/10/2026) : des **adultes de tous âges** (`AGES` : huit âges, un seul vieux), et l'âge tiré est **redit** dans le prompt pour que le modèle ne le vieillisse pas — le vieillissement touchait toutes les Lignées (hobbits peut-être exceptés).

### 0.2 bis Modèle

**`gemini-3.1-flash-lite-image`** (Flash Lite) par défaut : le moins cher, celui qu'utilise l'auteur. `gemini-2.5-flash-image` a servi aux essais v1-v3 de Berga.

**En local (gratuit)** : ComfyUI portable AMD (`C:\ComfyUI_windows_portable`, lancer **`run_telluris.bat`**, `http://127.0.0.1:8188`) + **Z-Image Turbo** (`z_image_turbo_bf16` chargé en **fp8** + encodeur `qwen_3_4b_fp8_mixed` + VAE `ae`) : 8 pas, CFG 1, `res_multistep`/`simple`, décalage AuraFlow 3 ; ~5-6 min l'image sur la Radeon 890M.
- ⚠️ Radeon 890M : `--bf16-text-enc` obligatoire (Qwen3 en fp16 → NaN → image de bruit) ; la mémoire « VRAM » plafonne à 14,4 Go et le pilote annonce 0 Go libre dès ~10 Go tenus → modèle en fp8 + `--disable-smart-memory`, sinon la 2e image sort en bruit ou en gris. Ne pas lancer d'autre gros travail en parallèle : la RAM est partagée. Prompt **anglais, en phrases** ; **aucun prompt négatif** (CFG 1) → l'interdiction du texte s'écrit dans le prompt. Aucune image de référence : un personnage se **décrit**, il ne se reprend pas. Repli des magasins (§1 bis, `generer`, sous FLUX.2 Klein qui accepte une référence) — la voie par défaut est Gemini.
- ⚠️ DreamShaper XL Lightning (SDXL, installé aussi) **écarté** le 08/10/2026 : lignées ignorées (une ogresse rendue en humaine), foule de Telluris jamais dessinée, faux texte sur les bannières.

### 0.3 Formats

| Type | Format | Dossier | Nom de fichier |
|---|---|---|---|
| Magasin | **paysage 16:9** (1408×768, comme 233 des 294 images de `towns/`) | `templates/resources/towns/` | `<categorie>_<region>NN.png` (ex. `fletcher_europe04.png`) ; propre à une cité : `<base>_<cite>NN.png` (ex. `archerie_europe_rhemi01.png`, cf. `auberge_europe_lutecia*`) |
| Tenancier | **paysage 16:9** (comme les portraits existants, ~1408×768) | `templates/resources/pnj/` | `marchand_<race>_<m\|f>_<categorie>NN.png` |
| Monstre | carré 1:1 | `templates/resources/monsters/` | `<slug_espece>_transparent.webp` (fond retiré après génération, WebP sans perte) |
| Porte (ext./int.) | paysage 16:9 | `templates/resources/towns/` | `<slug_porte>.png` |
| Logement du joueur (§ 7) | paysage 16:9 | `templates/resources/towns/` | `<type>_<region>NN.jpg` (ex. `maison_grand_nord01.jpg`) — région obligatoire |

### 0.4 Champs disponibles

| Champ | Source |
|---|---|
| `{metier}` | libellé lisible de la catégorie du lieu (`fletcher` → « archerie », `atelier_de_cirier` → « atelier de cirier ») |
| `{nom_magasin}` | `label` du doc `lieu:*` |
| `{cite}` | `label` du `lieu_parent` (« Lutèce », « Reims ») |
| `{repere_cite}` | un détail qui ancre l'image dans la vraie ville (cathédrale de Reims, Seine et Notre-Dame, Yonne…) |
| `{precision_lieu}` | **saisie à la main** : l'endroit exact voulu dans l'image (« dans un petit village à l'extérieur des remparts, avec vue sur la capitale », « dans une ruelle au pied de la cathédrale »…) — tous les autres champs sont générés depuis l'Excel |
| `{tenancier}` | `nom` de l'entrée `pnj` du lieu |
| `{race}`, `{sexe}` | lus sur le portrait ou le doc PNJ (`hobbit`, `homme`/`femme`) |
| `{signe_physique}` | un trait distinctif court (« cheveux blonds bouclés, regard vif ») |
| `{espece}` | `nom` du doc `espece:*`, **accents rétablis** (« Aigle Géant ») |
| `{description}` | `description` du doc `espece:*` |
| `{posture}` | traduction visuelle des tags (voir 3) |

### 0.4 bis Correspondance avec l'Excel `telluris lieux prompts.xlsx`

| Feuille | Colonnes lues | Gabarit |
|---|---|---|
| `magasins` | Label → `{nom_magasin}` · Type de lieu → `{metier}` · Tenancier → `{tenancier}` · Description tenancier → `{tenancier}, {signe_physique}` (race comprise) · Sexe (`M`/`F`) · Lieu parent → `{cite}` · Additionnal prompt → `{precision_lieu}` · Done? (0/1) | §1 + §2 |
| `referentiels` | Nom prénom · Sexe · Description (« Adèle de Rochefort, une humaine élégante aux longs cheveux châtains ») · Utilisé (0/1) | réserve de tenanciers |
| `monstres` | nom → `{espece}` · description → `{description}` · tags → `{posture}` · image → nom du fichier · Done (0/1) | §3 |
| `portes` | textes libres (extérieure, intérieure, version générique) | §4 + §5 |

Seules les lignes `Done = 0` sont à générer ; une ligne sans `Description tenancier` ne produit pas de portrait.

### 0.5 Prompts « suite »

Un prompt qui renvoie à une image précédente (« le même tenancier », « la même porte ») exige d'**envoyer cette image en référence** avec le prompt. Sans elle, le modèle invente une autre scène. ⚠️ À l'inverse, une image jointe est **recopiée** : n'en joindre une que pour reproduire CE sujet, jamais pour un simple style.

### 0.5 bis Cartes de cité : aucun portail par défaut

⚠️ Une carte de cité (`towns/<cite>_capital`) **ne montre aucun portail**, ni dans les murs ni autour (Auteur, 22/10/2026) : il est plus intéressant de tomber sur un portail en se déplaçant que de le voir sur la carte. Toute apparition d'un portail sur une carte exige une **vraie justification par le lore** de la cité. Aucune cité décrite à ce jour n'en a.

### 0.5 ter Cartes de cité : aucun personnage

⚠️ Une carte de cité ne montre **aucun personnage** : ni passant dans les rues, ni foule sur les places, ni chevalier ou cavalier dans la campagne autour (Auteur, 22/10/2026). Deux raisons : un passant posé dans une rue empêche de la lire (la grille praticable se tire de l'image, et une silhouette casse la lecture des algorithmes comme celle à l'œil), et des petits personnages humanisent la carte au lieu de rester anthrope. Le prompt l'écrit en toutes lettres (« rues, places et campagne entièrement vides de personnages, de cavaliers et d'animaux de trait ») — la règle du § 0.2 (foule de Telluris) ne s'applique PAS aux cartes de cité.

### 0.5 quater Cartes de combat : « C'est une battlemap »

⚠️ Tout prompt de carte de combat (`battle_maps/`) **se termine** par la phrase « La vue est aérienne. C'est une battlemap. », écrite après le bloc de style (Auteur, 24/10/2026) : sans elle, le modèle dessine la salle en perspective (`battle_maps/donjon_djinns.jpg`, premier essai de Petra).

### 0.6 Enregistrement

Chaque image générée est écrite **directement dans son dossier cible** (cf. 0.3), et **n'écrase jamais** un fichier existant : si `…01` est pris, on passe à `…02`, et ainsi de suite.

**Format de fichier** : celui que rend le modèle, sans conversion (Flash Lite → `.jpg`). Seuls les **monstres** sont convertis : **WebP sans perte** (transparence du fond détouré, −40 % face au PNG ; tout le dossier converti le 15/11/2026). Ailleurs, `.jpg` comme `.png` conviennent.

---

## 1. Magasin

> Façade et étal d'une boutique de **{metier}** nommée « {nom_magasin} », dans la cité de **{cite}**, dans le monde médiéval fantastique de Telluris. {precision_lieu}. {repere_cite}. La boutique occupe environ 80 % de l'image, vue de face ou de trois-quarts depuis la rue ; ses marchandises sont exposées et immédiatement reconnaissables comme celles d'un {metier}. Le tenancier, {tenancier}, un·e {race} {signe_physique}, se tient sur le seuil. [0.2] [0.1]

**Exemple (rempli depuis l'Excel)** : boutique d'archerie « L'Arc et la Corde de la Cité », Lutèce, tenue par Nicolas Piedléger, un hobbit aux cheveux blonds bouclés et au regard vif ; `{precision_lieu}` = « dans un petit village à l'extérieur des remparts de Lutèce, avec vue sur la capitale ».

### 1 bis. Magasin — portrait du tenancier en référence (Gemini)

**Options de reprise (10/10/2026)** — `preparer --doublons` : seules les façades/portraits de marchands PARTAGÉS avec un autre lieu (le porteur hors de la cité, sinon le premier par id, garde le fichier) ; `--refaire a,b` : boutiques désignées (façade ; portrait aussi s'il n'est pas `marchand_*`), auberges comprises (`HORS_LES_MURS` : décor de hameau propre à un lieu) ; `--ecraser` : portrait ET façade réécrits sous leurs noms actuels (seule exception à « jamais d'écrasement », rien à importer) ; `--source <export>` : lieux plus frais que le dump (l'import est un PUT complet). `appliquer` nomme aussi tout marchand de la cité qui n'a pas de `nom` (répertoire du recrutement, graine du lieu). `portrait_facade --facade … --race … --sexe … --categorie …` : portrait du tenancier d'une façade GARDÉE pour un lieu ultérieur (paire notée dans `dev/batch/<cite>/images/reserve.json`). Petits tenanciers (hobbit, nain) : un client tiré par lieu se tient à côté, tailles données en fois celle d'un humain (`TAILLES`, `comparatif_client`).

Script : `dev/gen_images_magasins.py --cite lieu:<cite>` — **un seul générateur pour les portraits (§2) ET les façades** : `preparer` → `essai --limite N` (interactif, `essais/`, portrait puis façade) → `avancer` rejoué jusqu'à « terminé » (soumet / suit / récupère / resoumet) → `appliquer` (un seul import : `pnj[0].portrait` + `image`). Ajout à une cité déjà peuplée : `preparer --lot <import des boutiques>` ne prépare QUE les boutiques de cet import (ex. `jsons/caves_negoces_a_importer.json`). Plusieurs cités : `appliquer --cite lieu:a,lieu:b` → UN seul `jsons/images_magasins_a_importer.json`. ⚠️ Revue du lot des caves (10/10) : le nom de la cité n'est plus dans le portrait (peint en écriteau), étiquettes et écriteaux interdits, ogres « ni orcs ni trolls » (petits crocs pointant de la lèvre inférieure admis) et teint humain pour toute la foule, naine/hobbit « à hauteur d'un enfant de dix/huit ans », façade vue de face aux pans latéraux murés (une seule banne). Deux lots batch Gemini (−50 %), enchaînés : **lot 1** = portraits + auberges, **lot 2** = façades des boutiques, écrit par `recuperer` du lot 1 ; état dans `dev/batch/<cite>/images/manifeste.json`. Le **portrait du tenancier** (`pnj[0].portrait`, ramené à ~1 Mpx) part dans la requête **avant** le texte : c'est l'« image 1 » du prompt (§0.5). Repli local gratuit : `generer [--essai]` (ComfyUI + FLUX.2 Klein, `run_telluris.bat`). Le §1 traduit, **sans aucun nom** — ni boutique, ni tenancier, **ni « Telluris »** (essai du 08/10 : le mot est sorti peint sur une enseigne) :

> The person shown in image 1 is the shopkeeper: keep exactly the same face, hair, facial hair, body, skin and clothes as in image 1 ({lignee}, {traits}, {repere_lignee}), but NOT the same pose or expression. Do not reuse the background of image 1. Show this shopkeeper at work in the ground-floor shop of a medieval fantasy {boutique} in the city of {cite}, {quartier}, busy with the trade, absorbed in the task, not looking at the camera, not posing, not presenting anything to the viewer. The shop is a solid, permanent town house of two or three storeys, built of stone and timber framing, with its own walls, roof and upper floors — never a market stall, booth, tent, cart or makeshift lean-to. It fills about 80% of the image, seen from the street in a three-quarter view. Its street wall stays a real wall of stone and timber with a door and ONE shop window whose wooden shutter is folded down to serve as the sales counter; the shopkeeper works behind that window or just inside the open door. Never two open walls, never a corner shop open on two sides, never a front entirely open onto the street. No hanging shop sign, no signboard, no name board or plaque above the door or window. The goods are displayed on shelves, racks and counters seen through the window and the door, and on the shutter counter, and are immediately recognizable: {marchandises}. [échelle des hobbits et nains] [0.2 en anglais] [0.1 en anglais + « No text anywhere in the image… »]

- ⚠️ **Style d'Auxerre, pas photo** (préférence de l'auteur après le lot de Rhemi du 09/10) : illustration peinte §0.1, palette chaude, couleurs franches. Le photoréaliste désaturé de Rhemi sortait gris. **Foule variée** : chaque passant différent (couleurs de cheveux, tenues, armures…) ; ⚠️ **ogres jamais verts** — teints humains, burinés, rougeauds, hâlés ou cendrés ; ⚠️ jamais de renvoi aux films du Seigneur des Anneaux, qui produisait des figurants en costumes identiques.
- ⚠️ **Même personne, pas même pose** (consigne de l'auteur, lot de Rhemi du 09/10) : le portrait (§2) montre le tenancier face à nous, souriant, qui présente sa marchandise ; la boutique le montre **au travail**, absorbé, sans regarder l'objectif. Sans cette consigne, le modèle recopie la pose du portrait joint. C'est le partage d'origine de l'Excel (colonne `Prompt tenancier` : « Il nous regarde et nous propose ses marchandises », la boutique étant générée d'abord).
- ⚠️ **Boutique fermée sur la rue sauf UNE vitrine** (consigne de l'auteur, lot de Lutecia du 10/10) : le volet rabattu sert d'étal, jamais deux pans de mur ouverts ni façade entièrement ouverte. **Aucune enseigne** (faux nom peint sur « L'Herbier de la Grève »). **Hobbit et nain gardent leur taille DANS la boutique** : comptoir à hauteur de poitrine, mobilier fait pour les humains (hobbit de « La Besogne des Halles » rendu à taille humaine).
- ⚠️ **Le portrait d'un tenancier est un portrait de MARCHAND** (`marchand_*`) : un guerrier ou un clerc pris dans le fonds des personnages est refait (`preparer --refaire`), façade comprise.
- **Auberges** (`categorie == "auberge"`) : aucun PNJ posté → pas d'image jointe ; `prompt_auberge` (salle commune ouverte, enseigne à emblème sans texte). Quartier lu sur l'enseigne, sinon `QUARTIERS_AUBERGES` (« Au Bon Vigneron » → Coteaux, « La Crayère » → Crayères).

- `{boutique}`, `{marchandises}` : `METIERS_EN`, une ligne par catégorie (mêmes clés que les portraits).
- `{quartier}` = `{precision_lieu}` + `{repere_cite}`, lu sur le **toponyme qui termine l'enseigne** (`utils/enseignes.TOPONYMES_PAR_LIEU`) : à Reims, « du Sacre » → parvis de la cathédrale, « de la Porte de Mars » → l'arc romain, « des Crayères » → caves de craie… (`QUARTIERS_EN`).
- `{traits}` : ceux tirés pour le **portrait** du tenancier (âge, corps, cheveux, allure — `tirage` de l'entrée du manifeste, graine propre au lieu), traduits par `TRAITS_EN`.

---

## 2. Tenancier

*(Joindre en référence l'image du magasin s'il existe — même personnage, même tenue — sinon un portrait `marchand_*` existant, pour le style seulement.)*

> Portrait illustré d'un personnage de fantasy médiévale, format paysage large. **{une_lignee}** {signe_physique}, {morphologie}, {tenancier_metier} à {cite}, dans un monde médiéval fantastique. {Il·Elle} se tient légèrement décalé·e du centre et regarde droit vers le spectateur avec l'assurance d'un·e commerçant·e ; {il·elle} lui présente {objet_metier}. Tenue de travail usée et crédible : {tenue_metier}. Décor de part et d'autre : {decor_metier}. [foule variée] [0.1 bis]

**Foule variée** : la phrase §0.2 de l'auteur, telle quelle, prolongée de « chacun différent par l'âge, la carrure, les cheveux et la tenue » et de variations par Lignée (elfes de toutes couleurs de cheveux, nains en armure ou en tablier, hobbits ronds ou fluets, **ogres aux teints humains, jamais verts**…).

**0.1 bis — style des portraits** : le **même que les façades** (style d'Auxerre, §0.1), puisque le portrait part en référence de sa boutique (§1 bis) :

> Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle chaude, palette chaude et terreuse relevée de touches de couleurs vives, proportions crédibles ; pas une photographie. Image entièrement dépourvue d'écriture : aucun nom, aucune lettre, aucune signature, aucun monogramme, aucun filigrane, aucune enseigne lisible.

*(Les portraits de Rhemi du 08/10 ont été faits en photoréaliste ; l'auteur préfère le style d'Auxerre depuis le 09/10.)*

**Règles tirées du premier essai** (Berga Rudemarteau, 08/10/2026 — `marchand_nain_f_etable01.png`) :
- ⚠️ **Créativité libre** (consigne de l'auteur, 10/10 : trois jardinières au même chapeau de paille et au même panier) : objet, tenue, décor (`METIERS`) et marchandises (`METIERS_EN`) sont des **exemples**, jamais imposés ; `LIBERTE_FR` / `LIBERTE` demandent une allure propre à chaque tenancier et à chaque boutique. **10 variantes par métier** (`dev/gabarits_metiers.py` : `PORTRAIT` en français, `FACADE` en anglais), une par lieu (`variante_de`, graine du lieu) — tout nouveau métier reçoit ses 10 variantes.
- ⚠️ **Le tenancier est DANS sa boutique, derrière son comptoir** (consigne de l'auteur, lot de Lutecia du 10/10) : la rue n'apparaît qu'au fond, par la porte ou la vitrine. Son **nom** vit dans la donnée (`pnj[0].nom`, tiré par `appliquer` pour tout marchand qui n'en a pas), jamais dans le prompt.
- **Ne jamais écrire le nom du personnage dans le prompt** : le modèle l'a recopié en signature (« Rudemarteu » en bas à gauche). Le nom vit dans la donnée, pas dans l'image ; on décrit « une naine… ».
- **Format paysage 16:9** : l'essai en 3:4 détonnait à côté des portraits existants. *(Le « rendu photoréaliste » retenu le 08/10 est abandonné le 09/10 au profit du style d'Auxerre, cf. 0.1 bis.)*
- **Ne jamais joindre un portrait existant comme « référence de style »** (essai v2) : le modèle l'a recopié presque à l'identique (même pose, même tablier, mêmes outils, même décor), seuls les cheveux ont changé — et il a ignoré l'objet à présenter. Une image de référence ne sert qu'à garder le **même** personnage (magasin → tenancier). Le style passe par le texte seul, qui suffit à obtenir le rendu photo.
- **La Lignée en tête de phrase, avec une échelle visible** : « une naine, nettement plus petite que les humains qui passent derrière elle » — sans élément de comparaison dans l'image, une naine seule ressemble à une humaine.
- **Rendre la Lignée reconnaissable**, sinon le modèle dessine un humain — mais **sans figer le physique** : un nain peut être rachitique, un hobbit gros et vieux, une elfe trapue. `{morphologie}` assemble donc deux parties :
  1. **`{marqueur_lignee}`** — ce qui fait reconnaître la Lignée, quel que soit le corps (une ou deux mentions, pas plus) ;
  2. **`{corps}`** — âge, corpulence, allure, propres à CE personnage : tirés de sa `Description tenancier` quand elle en parle, sinon variés d'un portrait à l'autre (jeune / mûr / âgé ; maigre / ordinaire / fort / bedonnant ; vif / las / bourru…).

| Lignée | `{marqueur_lignee}` (repères, pas une règle de corps) | Variations à laisser ouvertes |
|---|---|---|
| nain·e | taille nettement plus petite qu'un humain, proportions de nain (tête et mains grandes pour la taille) | robuste ou malingre, barbu — une **naine n'a jamais de barbe** (consigne de l'auteur, 10/10) —, jeune ou chenu·e |
| hobbit | toute petite taille d'adulte, pieds nus | rond·e ou fluet·te, enfantin·e ou ridé·e, soigné·e ou débraillé·e |
| elfe | oreilles longues et pointues | élancé·e ou râblé·e, d'apparence jeune ou visiblement ancien·ne |
| ogre | bien plus grand·e et massif·ve qu'un humain, peau épaisse | imposant·e ou voûté·e, défenses ou non, sage ou rustre |
| humain·e | *(aucun marqueur)* | tout est ouvert |

Exemple : « Une naine maigre et âgée, aux mains noueuses, nettement plus petite qu'un humain… » — et non « une naine trapue » par défaut.

Champs propres au tenancier (dérivés du métier, une ligne par catégorie à tenir à jour) : `{une_lignee}` (« Une naine », « Un hobbit »), `{tenancier_metier}` (« tenancière d'une étable »), `{objet_metier}` (« un licol de cuir neuf »), `{tenue_metier}` (« tablier de cuir, manches retroussées, brins de paille »), `{decor_metier}` (« enclos de bois, bottes de foin, une mule et un poney »).

---

## 3. Monstre

> Illustration en pied d'un **{espece}** : {description}. {posture} La créature occupe environ 80 % de l'image, entière, sans membre coupé par le cadre, en vue de trois-quarts. Fond **parfaitement uni et plat, {couleur_fond} pur**, sans dégradé, sans décor, sans sol visible, sans ombre portée, sans halo — la créature ne doit contenir aucune touche de cette couleur. [0.1]

`{couleur_fond}` = une couleur absente de la créature, pour que le fond se retire automatiquement (`python dev/detourer_image.py <image> <slug_espece>` : Pillow seul, remplissage depuis les bords + poches de fond enclavées, recadré ; ⚠️ une image avec décor collé à la créature ne se détoure pas — la régénérer) : **magenta** par défaut, **vert vif** si la créature est rose, violette ou rouge, **bleu vif** si elle est verte. Le fichier détouré s'enregistre en `<slug_espece>_transparent.webp`.

Traduction des tags en `{posture}` :

| Tag | Phrase |
|---|---|
| `vol` | « Elle est en vol, ailes déployées. » |
| `predateur` | « Attitude de chasse, griffes et crocs visibles, regard fixé sur sa proie. » |
| `proie` | « Attitude aux aguets, prête à fuir. » |
| `aquatique` | « Corps luisant, comme sortant de l'eau. » |
| `mort_vivant` | « Chair desséchée ou os apparents, lueur froide dans les orbites. » |
| *(autre)* | *(aucune phrase)* |

---

## 4. Porte de rempart — vue extérieure

> Vue réaliste et détaillée de la **porte principale fortifiée de {cite}**, dans le monde médiéval fantastique de Telluris.
>
> **Point de vue :** la caméra est **sur la route, à l'extérieur de la cité**, face aux remparts. Une seule porte monumentale, grande ouverte, perce les remparts. À travers l'ouverture, on voit une rue pavée qui s'enfonce **dans la ville** : maisons de pierre et de bois, toits, tours. Au premier plan, la route de campagne arrive jusqu'à la porte.
>
> **Garde :** cinq gardes contrôlent les voyageurs qui entrent ; un seul garde surveille ceux qui sortent. Les gardes sont de différentes Lignées (humains, elfes, nains, hobbits, ogres), en armure médiévale fantastique cohérente.
>
> **Architecture :** remparts de pierre hauts et massifs, tours défensives, créneaux, chemin de ronde, herse relevée. {repere_cite}.
>
> **Exclusions :** une seule ouverture dans les remparts — aucune porte secondaire ni latérale. [0.1]

---

## 5. Porte de rempart — vue intérieure

*(Joindre l'image de la vue extérieure en référence : même porte, mêmes tours, mêmes gardes.)*

> La **même porte** que l'image de référence, vue cette fois **depuis l'intérieur de {cite}**.
>
> **Point de vue :** la caméra est **dans une rue de la ville**, dos à la cité, face à la porte. Des maisons de la ville bordent la rue au premier plan, de chaque côté. À travers la porte ouverte, on voit **l'extérieur** : la route qui s'éloigne dans la campagne, des champs, l'horizon. Au-dessus du rempart, rien d'autre que le ciel — aucun bâtiment.
>
> Les gardes contrôlent le passage depuis l'intérieur. [0.2]
>
> **Exclusions :** une seule ouverture dans les remparts. [0.1]

---

## 6. Lieux modèles génériques de la voie de colonisation

Un par palier (docs/lore/systemes/20261112_voie_de_colonisation.md § 12.1), milieu tempéré neutre. La carte se **parcourt** (cases tirées de l'image) **et sert de carte de combat** quand le lieu est attaqué : vue verticale, phrase du § 0.5 quater, aucun personnage (§ 0.5 ter), aucun portail (§ 0.5 bis). Les **entrées** déclarées sur le modèle (`entrees`, `dev/gen_colonisation.py`) sont au milieu des bords — une au campement, deux au hameau, quatre ensuite : les portes peintes doivent y tomber. Les fortifications du palier (§ 4) sont **peintes**. Le joueur pose ses bâtiments sur les cases libres : l'image en laisse beaucoup. Pas de lieu de culte (§ 8).

Livrées le 13/11/2026 (le Bourg en a deux : `…01` retenue, `…02` en réserve — grille visible, une enseigne au faux texte et un édifice d'allure religieuse ; Campement et Bourgade sortis en légère perspective). Enregistrement : `templates/resources/towns/colonie_<palier>_generique01.jpg` — `dev/gen_colonisation.py` remplace alors l'image provisoire du modèle ; refaire ensuite sa grille dans `/admin/lieux` (et vérifier `entrees`).

| Palier | Format | Fichier | Entrées |
|---|---|---|---|
| Campement | 16:9 | `colonie_campement_generique01.jpg` | un seul sentier au milieu du bord inférieur |
| Hameau | 3:2 | `colonie_hameau_generique01.jpg` | deux portes : milieu du bord inférieur et milieu du bord supérieur |
| Bourgade | 3:2 | `colonie_bourgade_generique01.jpg` | quatre portes : milieu de chaque bord |
| Village | 3:2 | `colonie_village_generique01.jpg` | quatre portes fortifiées : milieu de chaque bord |
| Bourg | 5:4 | `colonie_bourg_generique01.jpg` | quatre portes : milieu de chaque bord |
| Petite ville | 5:4 | `colonie_petite_ville_generique01.jpg` | quatre portes : milieu de chaque bord |
| Ville | 5:4 | `colonie_ville_generique01.jpg` | quatre grandes portes : milieu de chaque bord, ponts sur les douves |

### 6.1 Campement

```
Réalise l'image d'un campement de colons au cœur d'une clairière herbeuse d'une contrée tempérée, au format paysage 16:9. Au centre, un grand feu de camp cerclé de pierres ; autour, la tente du fondateur, deux ou trois tentes plus petites, des caisses, des sacs et des tonneaux empilés sous une bâche, un tas de bois coupé et un poste de guet en rondins. Aucune enceinte : le camp s'ouvre sur l'herbe, et un seul sentier de terre en sort, au milieu du bord inférieur de l'image. Quelques buissons et arbres isolés bordent la clairière. Vue parfaitement verticale, vue du dessus, sans perspective, pour qu'une grille de cases se pose sur la carte : les zones où l'on marche (terre battue, herbe rase, pavés) se distinguent nettement des bâtiments, des murs et des obstacles. De larges espaces dégagés restent libres entre les constructions. Aucun lieu de culte : ni église, ni chapelle, ni clocher. Aucun portail magique. Le lieu et la campagne autour sont entièrement vides de personnages, de cavaliers et d'animaux de trait. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane. La vue est aérienne. C'est une battlemap.
```

### 6.2 Hameau

```
Réalise l'image d'un jeune hameau de colons dans une plaine tempérée, au format paysage 3:2. Une palissade complète de pieux taillés en pointe l'entoure ; elle s'ouvre par deux portes de bois, l'une au milieu du bord inférieur de l'image, l'autre au milieu du bord supérieur, reliées par un chemin de terre. Dedans : quatre ou cinq maisons à colombages au toit de chaume, un enclos à bétail vide, des potagers, un puits et un feu central, avec de larges cours de terre battue et d'herbe entre les bâtiments. Dehors, des champs labourés et des prés. Vue parfaitement verticale, vue du dessus, sans perspective, pour qu'une grille de cases se pose sur la carte : les zones où l'on marche (terre battue, herbe rase, pavés) se distinguent nettement des bâtiments, des murs et des obstacles. De larges espaces dégagés restent libres entre les constructions. Aucun lieu de culte : ni église, ni chapelle, ni clocher. Aucun portail magique. Le lieu et la campagne autour sont entièrement vides de personnages, de cavaliers et d'animaux de trait. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane. La vue est aérienne. C'est une battlemap.
```

### 6.3 Bourgade

```
Réalise l'image d'une bourgade de colons dans une plaine tempérée, au format paysage 3:2. Une palissade doublée d'un fossé sec l'entoure, avec des tours de guet en bois aux angles ; quatre portes de bois flanquées de tours la percent, au milieu de chacun des quatre bords de l'image, et deux rues de terre se croisent au centre pour les relier. Autour d'une petite place dégagée : une dizaine de maisons à colombages, une grange, des ateliers sous appentis, des potagers et plusieurs terrains libres. Vue parfaitement verticale, vue du dessus, sans perspective, pour qu'une grille de cases se pose sur la carte : les zones où l'on marche (terre battue, herbe rase, pavés) se distinguent nettement des bâtiments, des murs et des obstacles. De larges espaces dégagés restent libres entre les constructions. Aucun lieu de culte : ni église, ni chapelle, ni clocher. Aucun portail magique. Le lieu et la campagne autour sont entièrement vides de personnages, de cavaliers et d'animaux de trait. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane. La vue est aérienne. C'est une battlemap.
```

### 6.4 Village

```
Réalise l'image d'un village fortifié de colons dans une plaine tempérée, au format paysage 3:2. Une enceinte de pierre maçonnée, basse mais continue, l'entoure ; quatre portes fortifiées, chacune entre deux tourelles, la percent au milieu de chacun des quatre bords de l'image. Deux rues de galets se croisent sur une place centrale avec une fontaine. Maisons de pierre et de colombages, potagers, vergers et cours dégagées emplissent l'enceinte ; dehors, des champs en lanières. Vue parfaitement verticale, vue du dessus, sans perspective, pour qu'une grille de cases se pose sur la carte : les zones où l'on marche (terre battue, herbe rase, pavés) se distinguent nettement des bâtiments, des murs et des obstacles. De larges espaces dégagés restent libres entre les constructions. Aucun lieu de culte : ni église, ni chapelle, ni clocher. Aucun portail magique. Le lieu et la campagne autour sont entièrement vides de personnages, de cavaliers et d'animaux de trait. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane. La vue est aérienne. C'est une battlemap.
```

### 6.5 Bourg

```
Réalise l'image d'un bourg fortifié dans une plaine tempérée, au format 5:4. Des murailles de pierre crénelées, rythmées de tours carrées, l'entourent ; quatre portes à herse les percent, au milieu de chacun des quatre bords de l'image. Au centre, une vaste place de marché dégagée avec une halle couverte ; des rues pavées en croix mènent aux portes, bordées de maisons serrées entrecoupées de cours, de jardins et de petites places. Une grande auberge et une maison commune donnent sur la place. Dehors, des champs. Vue parfaitement verticale, vue du dessus, sans perspective, pour qu'une grille de cases se pose sur la carte : les zones où l'on marche (terre battue, herbe rase, pavés) se distinguent nettement des bâtiments, des murs et des obstacles. De larges espaces dégagés restent libres entre les constructions. Aucun lieu de culte : ni église, ni chapelle, ni clocher. Aucun portail magique. Le lieu et la campagne autour sont entièrement vides de personnages, de cavaliers et d'animaux de trait. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane. La vue est aérienne. C'est une battlemap.
```

### 6.6 Petite ville

```
Réalise l'image d'une petite ville fortifiée dans une plaine tempérée, au format 5:4. De hautes murailles de pierre à tours rondes l'entourent ; quatre portes monumentales les percent, au milieu de chacun des quatre bords de l'image. Deux grandes rues pavées se croisent sur une place centrale ; des quartiers distincts s'organisent autour : quartier des artisans aux cours d'ateliers, quartier marchand aux halles et entrepôts, quartiers d'habitation aux jardins. Plusieurs places secondaires et des esplanades restent dégagées. Vue parfaitement verticale, vue du dessus, sans perspective, pour qu'une grille de cases se pose sur la carte : les zones où l'on marche (terre battue, herbe rase, pavés) se distinguent nettement des bâtiments, des murs et des obstacles. De larges espaces dégagés restent libres entre les constructions. Aucun lieu de culte : ni église, ni chapelle, ni clocher. Aucun portail magique. Le lieu et la campagne autour sont entièrement vides de personnages, de cavaliers et d'animaux de trait. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane. La vue est aérienne. C'est une battlemap.
```

### 6.7 Ville

```
Réalise l'image d'une ville fortifiée dans une plaine tempérée, au format 5:4. Un système défensif complet l'entoure : double enceinte de pierre aux tours massives, chemin de ronde, et douves en eau au pied du mur extérieur ; quatre grandes portes fortifiées, chacune avec un pont sur les douves, percent les murailles au milieu de chacun des quatre bords de l'image. Dedans, une grande place centrale, des rues pavées hiérarchisées, des quartiers denses entrecoupés de places, de jardins et d'esplanades dégagées, et une vaste cour libre devant une grande bâtisse à plusieurs ailes. Vue parfaitement verticale, vue du dessus, sans perspective, pour qu'une grille de cases se pose sur la carte : les zones où l'on marche (terre battue, herbe rase, pavés) se distinguent nettement des bâtiments, des murs et des obstacles. De larges espaces dégagés restent libres entre les constructions. Aucun lieu de culte : ni église, ni chapelle, ni clocher. Aucun portail magique. Le lieu et la campagne autour sont entièrement vides de personnages, de cavaliers et d'animaux de trait. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane. La vue est aérienne. C'est une battlemap.
```

---

## 7. Logements des joueurs (Chambre → Domaine) par région

Un prompt par type de bien × région de `rules:regions` (16:9, comme les images provisoires `chambre.jpg`…`domaine.jpg`). Le propriétaire choisit l'image de son bien **à tout moment** parmi celles de **son type** (section « 🖼️ Apparence du bien » du panneau 🏠, `POST /api/proprietes/image`, `proprietes.images_du_type`) : une image déposée sous le bon nom est offerte **sans import ni redémarrage**.

- **Nom de fichier** : `templates/resources/towns/<type>_<region>NN.jpg` (`maison_grand_nord01.jpg`) ; propre à une cité : `<type>_<region>_<cite>NN.jpg` (`demeure_afrique_du_nord_petra01.jpg`). ⚠️ La région (clé de `rules:regions`) est **obligatoire** : un fichier sans elle n'est pas proposé — c'est elle qui empêche `maison_des_conserves_europe01.jpg` de passer pour une Maison. `.jpg`, `.jpeg`, `.png`, `.webp`. Ne jamais écraser (§ 0.6).
- **Cadrage** : Chambre et Logement = **intérieur vide** (le logis attend son occupant) ; Maison et Demeure = **façade** depuis la rue, peuplée (phrase du § 0.2) ; Domaine = **vue d'ensemble** légèrement plongeante, à l'abri d'une enceinte (on ne vit pas près des monstres sans se protéger).
- Mot « portail » proscrit pour une entrée (porte cochère, porche) : il désigne un portail magique, absent de chaque prompt.
- ⚠️ **Tout logement est À L'INTÉRIEUR d'une cité-État, à l'abri de ses remparts** (Auteur, 15/11/2026), Domaine compris : un domaine clos AU CŒUR de la ville, entouré de ses rues et de ses toits, l'enceinte de la cité seulement à l'horizon. Les six premiers domaines, peints hors les murs, sont gardés sous `hameau_<region>01.jpg` (versions de hameau, branchées nulle part).
- ⚠️ **Décor tiré de la cité principale de la région** (carte `towns/<cite>_capital`) : Lutecia (fleuve, île à la cathédrale, toits de tuiles rouges, moulins sur la butte), Reykjavik (presqu'île, maisons de pierre sombre, haute tour à flèche, drakkars, volcans), Alexandrie (grand port, phare colossal couronné d'un feu, coupole, palmeraies), Aksoum (ville ocre, maisons à assises de bois, cases rondes, champ de stèles, montagnes tabulaires, chevaux ailés), Sydney (baie découpée, collines boisées). Steppes : aucune cité, décor générique. Sans nom de cité dans le prompt (risque de texte peint).
- ⚠️ **Aucun anachronisme** (demeure d'Océanie du 15/11 : immeubles, ville gigantesque, passants en tenue moderne — supprimée) : chaque prompt refait le dit en toutes lettres. Ogres « teints humains, jamais verts » dans tout prompt peuplé refait.
- ⚠️ **Afrique subsaharienne : des Lignées aux traits locaux** (Auteur, 15/11) — peaux brunes à très sombres, coiffures et tenues des hauts plateaux, sans rompre l'égalité des cinq Lignées. La première `maison_afrique`, d'allure sud-américaine, est gardée sous `maison_amerique_du_sud01.jpg` (région absente de `rules:regions` : non proposée).
- **Steppes et Caucase** : région déclarée sans cité en jeu à ce jour ; prompts prêts pour la première. **Océanie** : le grand édifice blanc aux voûtes en coquilles (temple des trois frères) n'est plus demandé : le modèle peignait l'opéra moderne de Sydney.

### 7.1 Europe (`europe`) — Lutecia, Auxerre, Rhemi, Chartres, Orléans, Rome, Camelot, Bruges, Aix-la-Chapelle, Bucarest…

#### Chambre — `chambre_europe01.jpg`

```
Réalise l'image de l'intérieur d'une chambre individuelle dans une auberge d'une cité-État d'Europe, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. Vue depuis le seuil, la pièce entière est visible : petite, modeste et propre, on y dort et on y range quelques affaires. Murs de torchis blanchis entre des poutres de chêne, plafond bas aux solives apparentes, plancher de chêne usé ; un lit simple garni d'une couverture de laine et d'un édredon de plumes, un coffre ferré au pied du lit, une petite table avec une chandelle et un pichet, un tabouret ; une fenêtre à petits carreaux sertis de plomb donne sur des toits d'ardoise et de tuile et, au loin, le chemin de ronde d'un rempart. La pièce est entièrement vide de personnages : le logis attend son occupant. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Logement — `logement_europe01.jpg`

```
Réalise l'image de l'intérieur d'un petit logement indépendant à l'étage d'une maison à colombages d'une cité-État d'Europe, au-dessus d'un atelier, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. Vue depuis l'entrée sur la pièce principale, un passage vers une seconde pièce plus petite : un foyer simple pour un ou deux occupants. Une cheminée de pierre où pend une crémaillère, une table de chêne et deux chaises, un banc-coffre, de la vaisselle d'étain sur une étagère ; au fond, une alcôve fermée par un rideau de laine abrite un lit pour deux ; une fenêtre à meneau s'ouvre sur une ruelle. La pièce est entièrement vide de personnages : le logis attend son occupant. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Maison — `maison_europe01.jpg`

```
Réalise l'image de la façade d'une maison individuelle dans une ruelle pavée d'une cité-État d'Europe, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. La maison occupe environ 80 % de l'image, vue de trois-quarts depuis la rue : un véritable foyer de plusieurs pièces, ni pauvre ni fastueux. Deux étages à colombages en encorbellement sur un soubassement de pierre calcaire, un toit pentu d'ardoise percé de lucarnes et d'une cheminée qui fume, une porte de chêne cloutée sous un auvent, des volets peints, un jardinet clos d'un muret avec un puits ; au fond, les tours d'un rempart. La rue est calme : quelques passants seulement, bien espacés, laissent voir le pavé. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Demeure — `demeure_europe01.jpg`

```
Réalise l'image de la façade d'une grande demeure de notable dans une rue large d'une cité-État d'Europe, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. La demeure occupe environ 80 % de l'image, vue de trois-quarts depuis la rue : nombreuses pièces, logement du personnel, de quoi recevoir des invités. Un hôtel particulier de pierre de taille blonde sur trois niveaux, une tourelle d'escalier en encorbellement à l'angle, de hautes fenêtres à meneaux, des toits d'ardoise à fortes pentes ornés de girouettes, une grande porte cochère ouverte sur une cour d'honneur pavée, des écuries au fond de la cour. La rue est calme : quelques passants seulement, bien espacés, laissent voir le pavé. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Domaine — `domaine_europe01.jpg`

```
Réalise l'image d'un domaine clos au cœur d'une grande cité-État d'Europe traversée par un fleuve, à l'intérieur de ses remparts, dans le monde médiéval fantastique de Telluris, au format paysage 16:9, en vue d'ensemble légèrement plongeante : une demeure principale, ses dépendances et ses terres privées, en pleine ville, à l'abri de l'enceinte de la cité, car on ne vit pas près des monstres sans se protéger. Un manoir de pierre aux toits d'ardoise flanqué d'une tour carrée ; une grange, un pressoir, un colombier rond et des écuries ; un potager en carrés, un verger et quelques rangs de vigne ; le tout clos d'un haut mur de pierre percé d'une porte cochère sur la rue. Tout autour du domaine, de tous côtés, la ville serrée : maisons à colombages et toits de tuiles rouges, ruelles et places ; plus loin, le fleuve, ses ponts de pierre et une île portant une grande cathédrale gothique ; à l'horizon seulement, l'enceinte crénelée de la cité et, au-delà, des moulins à vent sur une butte. Le domaine occupe environ la moitié de l'image, la ville l'entoure entièrement. Quelques silhouettes, toutes petites à cette distance, travaillent dans les jardins et passent dans les rues. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres ; les ogres ont des teints humains, jamais verts. Aucun élément moderne : ni immeuble, ni verre, ni métal moderne, ni vêtement contemporain ; chacun porte une tenue médiévale fantastique. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

### 7.2 Grand Nord (`grand_nord`) — Reykjavik, Akureyri (Islande), Laponie

#### Chambre — `chambre_grand_nord01.jpg`

```
Réalise l'image de l'intérieur d'une chambre individuelle dans une auberge d'une cité-État du Grand Nord, terre de volcans et de dragons, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. Vue depuis le seuil, la pièce entière est visible : petite, modeste et propre, on y dort et on y range quelques affaires. Murs de planches goudronnées doublés de tourbe, poutres sculptées d'entrelacs ; un lit-banc fermé garni de peaux de mouton et d'une fourrure de renne, un coffre de bois peint, une lampe à huile, un petit poêle de pierre de lave ; une fenêtre étroite s'ouvre sur des coulées de lave noire saupoudrées de neige. La pièce est entièrement vide de personnages : le logis attend son occupant. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Logement — `logement_grand_nord01.jpg`

```
Réalise l'image de l'intérieur d'un petit logement indépendant dans une maison de tourbe d'une cité-État du Grand Nord, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. Vue depuis l'entrée sur la pièce principale, un passage vers une seconde pièce plus petite : un foyer simple pour un ou deux occupants. Une pièce longue au foyer central de pierres plates sous un trou à fumée, des banquettes-lits le long des murs couvertes de peaux, un métier à tisser vertical lesté de pierres, une marmite suspendue, des poissons séchés pendus aux poutres ; une porte basse mène à une petite réserve. La pièce est entièrement vide de personnages : le logis attend son occupant. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Maison — `maison_grand_nord01.jpg`

```
Réalise l'image de la façade d'une maison individuelle dans une cité-État du Grand Nord, entre mer grise et montagnes enneigées, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. La maison occupe environ 80 % de l'image, vue de trois-quarts depuis la rue : un véritable foyer de plusieurs pièces, ni pauvre ni fastueux. Une maison de tourbe et de bois au toit couvert d'herbe, des pignons de planches peints en noir et rouge, un soubassement de pierre de lave, une petite cour de galets et un séchoir à poissons ; plus loin, une source chaude qui fume ; très haut dans le ciel, la silhouette lointaine d'un dragon. La rue est calme : quelques passants seulement, bien espacés, laissent voir le pavé. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Demeure — `demeure_grand_nord01.jpg`

```
Réalise l'image de la façade d'une grande demeure de notable dans une cité-État du Grand Nord, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. La demeure occupe environ 80 % de l'image, vue de trois-quarts depuis la rue : nombreuses pièces, logement du personnel, de quoi recevoir des invités. Une grande demeure faite de plusieurs pignons de bois accolés en rang sous des toits d'herbe, des poutres faîtières sculptées de têtes de dragon, des murs de pierre de lave et de tourbe, une cour close de pierre sèche où fume un bain alimenté par une source chaude. La rue est calme : quelques passants seulement, bien espacés, laissent voir le pavé. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Domaine — `domaine_grand_nord01.jpg`

```
Réalise l'image d'un domaine clos au cœur d'une cité-État portuaire du Grand Nord, bâtie sur une presqu'île entre une baie grise et des volcans enneigés, à l'intérieur de ses remparts, dans le monde médiéval fantastique de Telluris, au format paysage 16:9, en vue d'ensemble légèrement plongeante : une demeure principale, ses dépendances et ses terres privées, en pleine ville, à l'abri de l'enceinte de la cité, car on ne vit pas près des monstres sans se protéger. Une demeure aux pignons de bois et aux toits d'herbe, des étables à moutons, un enclos de petits chevaux trapus à crinière épaisse, des séchoirs à poissons, un bassin de source chaude fumant, un pré de fauche ; le tout clos d'un mur de pierre de lave percé d'une porte de bois sur la rue. Tout autour du domaine, de tous côtés, la ville serrée : maisons de pierre sombre et de bois goudronné, ruelles, et une haute tour de pierre à flèche pointue qui domine les toits ; plus loin, le port où mouillent des drakkars, la baie et les montagnes ; à l'horizon seulement, l'enceinte de pierre de la cité. Le domaine occupe environ la moitié de l'image, la ville l'entoure entièrement. Quelques silhouettes, toutes petites à cette distance, travaillent dans les cours et passent dans les rues. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres ; les ogres ont des teints humains, jamais verts. Aucun élément moderne : ni immeuble, ni verre, ni métal moderne, ni vêtement contemporain ; chacun porte une tenue médiévale fantastique. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

### 7.3 Steppes et Caucase (`steppes`) — steppe pontique, Volga, Oural, Caucase — aucune cité en jeu à ce jour

#### Chambre — `chambre_steppes01.jpg`

```
Réalise l'image de l'intérieur d'une chambre individuelle dans un caravansérail fortifié des steppes et du Caucase, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. Vue depuis le seuil, la pièce entière est visible : petite, modeste et propre, on y dort et on y range quelques affaires. Murs de pierre enduits d'argile, une niche voûtée ; une couche basse couverte de tapis de laine aux motifs géométriques et de coussins de feutre, un coffre de bois sculpté de rosaces, une lampe de cuivre, un brasero ; une petite fenêtre s'ouvre sur la steppe infinie et des cimes enneigées. La pièce est entièrement vide de personnages : le logis attend son occupant. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Logement — `logement_steppes01.jpg`

```
Réalise l'image de l'intérieur d'un petit logement indépendant à l'abri des remparts d'une cité-État des steppes, dans le monde médiéval fantastique de Telluris : une yourte de feutre blanc richement aménagée, au format paysage 16:9. Vue depuis l'entrée sur la pièce principale, un passage vers une seconde pièce plus petite : un foyer simple pour un ou deux occupants. Un treillis de bois peint en rouge et en ocre, une couronne centrale ouverte sur le ciel, un foyer sur trépied, des feutres et des tapis épais, un lit bas, des coffres peints, un harnachement de cheval suspendu ; un rideau de feutre brodé sépare une seconde partie. La pièce est entièrement vide de personnages : le logis attend son occupant. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Maison — `maison_steppes01.jpg`

```
Réalise l'image de la façade d'une maison individuelle dans une cité-État du Caucase adossée à la montagne, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. La maison occupe environ 80 % de l'image, vue de trois-quarts depuis la rue : un véritable foyer de plusieurs pièces, ni pauvre ni fastueux. Une maison de pierre au toit plat de terre battue, accrochée à la pente, un balcon de bois sculpté, une porte basse en bois clouté ; juste à côté, une haute tour défensive de pierre ; une ruelle de pierres et, au fond, des montagnes enneigées. La rue est calme : quelques passants seulement, bien espacés, laissent voir le pavé. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Demeure — `demeure_steppes01.jpg`

```
Réalise l'image de la façade d'une grande demeure de notable dans une cité-État du Caucase, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. La demeure occupe environ 80 % de l'image, vue de trois-quarts depuis la rue : nombreuses pièces, logement du personnel, de quoi recevoir des invités. Une demeure de pierre autour d'une cour à galeries de bois sculpté sur deux niveaux, une haute tour carrée à mâchicoulis, des portes de bois sculpté, des tapis qui sèchent aux balcons, une vigne en treille au-dessus de l'entrée. La rue est calme : quelques passants seulement, bien espacés, laissent voir le pavé. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Domaine — `domaine_steppes01.jpg`

```
Réalise l'image d'un domaine clos au cœur d'une cité-État des steppes et du Caucase, ceinte d'un rempart de pierre et de terre, à l'intérieur de ce rempart, dans le monde médiéval fantastique de Telluris, au format paysage 16:9, en vue d'ensemble légèrement plongeante : une demeure principale, ses dépendances et ses terres privées, en pleine ville, à l'abri de l'enceinte de la cité, car on ne vit pas près des monstres sans se protéger. Une demeure de pierre flanquée d'une tour, des enclos de chevaux de steppe, deux yourtes de feutre blanc pour les gardiens des chevaux, des meules de foin, un verger ; le tout clos d'un mur de pierre percé d'une porte de bois sculpté sur la rue. Tout autour du domaine, de tous côtés, la ville serrée : maisons de pierre et d'argile aux toits plats, quelques coupoles, un caravansérail à cour carrée, des ruelles et un bazar couvert ; à l'horizon seulement, le rempart de la cité et, au-delà, la steppe à perte de vue et des cimes enneigées. Le domaine occupe environ la moitié de l'image, la ville l'entoure entièrement. Quelques silhouettes, toutes petites à cette distance, travaillent dans les cours et passent dans les rues. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres ; les ogres ont des teints humains, jamais verts. Aucun élément moderne : ni immeuble, ni verre, ni métal moderne, ni vêtement contemporain ; chacun porte une tenue médiévale fantastique. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

### 7.4 Afrique du Nord et Orient (`afrique_du_nord`) — Alexandrie, Le Caire, Abou Simbel, Petra, Maroc, Levant

#### Chambre — `chambre_afrique_du_nord01.jpg`

```
Réalise l'image de l'intérieur d'une chambre individuelle dans une auberge de caravaniers d'une cité-État d'Afrique du Nord, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. Vue depuis le seuil, la pièce entière est visible : petite, modeste et propre, on y dort et on y range quelques affaires. Une pièce voûtée en pierre blanchie à la chaux, des niches dans les murs ; une banquette basse couverte de tapis et de coussins, un coffre de cèdre marqueté, une lanterne de cuivre ajourée, une jarre d'eau ; une fenêtre à moucharabieh de bois tourné jette sur le sol des motifs de lumière et laisse deviner des terrasses et des palmiers. La pièce est entièrement vide de personnages : le logis attend son occupant. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Logement — `logement_afrique_du_nord01.jpg`

```
Réalise l'image de l'intérieur d'un petit logement indépendant à l'étage d'une maison de briques crues d'une cité-État d'Afrique du Nord, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. Vue depuis l'entrée sur la pièce principale, un passage vers une seconde pièce plus petite : un foyer simple pour un ou deux occupants. Des murs enduits de chaux ocre, un sol de tomettes couvert d'un tapis, une banquette, une table basse de cuivre martelé avec une théière, des coffres, une jarre ; un escalier de terre monte vers la terrasse du toit. La pièce est entièrement vide de personnages : le logis attend son occupant. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Maison — `maison_afrique_du_nord01.jpg`

```
Réalise l'image de la façade d'une maison individuelle dans une ruelle étroite d'une cité-État d'Afrique du Nord, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. La maison occupe environ 80 % de l'image, vue de trois-quarts depuis la rue : un véritable foyer de plusieurs pièces, ni pauvre ni fastueux. Une maison à cour intérieure aux murs blanchis à la chaux, presque aveugles côté rue, une porte de bois clouté sous un arc outrepassé, un moucharabieh en encorbellement à l'étage, une terrasse sur le toit, un palmier qui dépasse de la cour. La rue est calme : quelques passants seulement, bien espacés, laissent voir le pavé. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Demeure — `demeure_afrique_du_nord01.jpg`

```
Réalise l'image de la façade d'une grande demeure de notable dans une cité-État d'Afrique du Nord et d'Orient, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. La demeure occupe environ 80 % de l'image, vue de trois-quarts depuis la rue : nombreuses pièces, logement du personnel, de quoi recevoir des invités. Une grande demeure de pierre ocre ornée de frises géométriques, une haute porte sous un arc polylobé, des moucharabiehs, une tour à vent qui rafraîchit les pièces ; par la porte ouverte, une cour d'honneur à bassin et fontaine, des galeries à colonnes et des orangers. La rue est calme : quelques passants seulement, bien espacés, laissent voir le pavé. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Domaine — `domaine_afrique_du_nord01.jpg`

```
Réalise l'image d'un domaine clos au cœur d'une grande cité-État portuaire d'Afrique du Nord, sur la côte, à l'intérieur de ses remparts, dans le monde médiéval fantastique de Telluris, au format paysage 16:9, en vue d'ensemble légèrement plongeante : une demeure principale, ses dépendances et ses terres privées, en pleine ville, à l'abri de l'enceinte de la cité, car on ne vit pas près des monstres sans se protéger. Rien d'européen : ni créneaux, ni tours de château, ni toits pentus, ni colombages. Une demeure blanchie à la chaux bâtie autour d'un patio, aux toits plats en terrasses, avec des arcs outrepassés, des moucharabiehs de bois tourné, des zelliges aux couleurs vives, une tour à vent et une petite coupole ; un jardin clos en croix à la manière d'un riad, partagé par des canaux d'irrigation autour d'une fontaine, une palmeraie, des orangers et des grenadiers, des greniers voûtés en terre, des pigeonniers de terre en forme de tours coniques percées de trous ; le tout clos d'un simple mur de terre ocre, lisse et sans créneaux, percé d'une porte de bois clouté sous un arc outrepassé. Tout autour du domaine, de tous côtés, la ville serrée : maisons cubiques blanches et ocre aux toits plats en terrasses, ruelles étroites couvertes de toiles, un souk, des coupoles et une grande coupole bleue ; plus loin, le grand port plein de navires à voiles et, sur son île, un phare de pierre colossal couronné d'un feu ; à l'horizon seulement, le rempart de la cité, un lac bordé de palmiers et le désert. Le domaine occupe environ la moitié de l'image, la ville l'entoure entièrement. Quelques silhouettes, toutes petites à cette distance, travaillent dans les jardins et passent dans les rues. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres ; les ogres ont des teints humains, jamais verts. Aucun élément moderne : ni immeuble, ni verre, ni métal moderne, ni vêtement contemporain ; chacun porte une tenue médiévale fantastique. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

### 7.5 Afrique subsaharienne (`afrique`) — Aksoum, Abyssinie, Sénégambie, Grands Lacs, Zambèze, Madagascar…

#### Chambre — `chambre_afrique01.jpg`

```
Réalise l'image de l'intérieur d'une chambre individuelle dans une auberge de caravanes d'une cité-État du Sahel, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. Vue depuis le seuil, la pièce entière est visible : petite, modeste et propre, on y dort et on y range quelques affaires. Des murs de terre crue lissés à la main, des niches, un plafond de rondins de palmier ; un lit de bois tendu de cuir et d'une natte, une couverture de coton tissé à bandes, une jarre de terre, une petite lampe à huile ; une ouverture étroite donne sur des toits-terrasses et des façades hérissées de pieux de bois. La pièce est entièrement vide de personnages : le logis attend son occupant. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Logement — `logement_afrique01.jpg`

```
Réalise l'image de l'intérieur d'un petit logement indépendant dans une cité-État d'Afrique subsaharienne, dans le monde médiéval fantastique de Telluris : une case ronde, au format paysage 16:9. Vue depuis l'entrée sur la pièce principale, un passage vers une seconde pièce plus petite : un foyer simple pour un ou deux occupants. Des murs de terre peints de motifs géométriques ocre et blanc, la charpente conique d'un toit de chaume, un foyer de trois pierres, un lit bas de bois sculpté, des tabourets sculptés, des calebasses et des nattes ; la seconde pièce est une case voisine, qu'on aperçoit par la porte de l'autre côté d'une petite cour. La pièce est entièrement vide de personnages : le logis attend son occupant. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Maison — `maison_afrique01.jpg`

```
Réalise l'image de la façade d'une maison individuelle dans une ruelle de terre rouge d'une cité-État des hauts plateaux d'Abyssinie, en Afrique de l'Est, à l'intérieur de ses remparts ocre, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. La maison occupe environ 80 % de l'image, vue de trois-quarts depuis la rue : un véritable foyer de plusieurs pièces, ni pauvre ni fastueux. Une maison de pierre ocre à assises alternées de pierre et de poutres de bois aux extrémités rondes saillantes, des fenêtres encadrées de bois sombre, un toit-terrasse, un escalier extérieur de pierre ; dans la cour, une case ronde au toit de chaume conique sert de cuisine, sous un grand figuier ; au loin, un champ de hautes stèles de pierre dressées et des montagnes aux sommets plats. La rue est calme : quelques passants seulement, bien espacés, laissent voir la terre battue. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres ; les ogres ont des teints humains, jamais verts. Ici, toutes les Lignées ont les traits des peuples des hauts plateaux d'Afrique de l'Est : peaux brunes à très sombres, cheveux crépus tressés, nattés ou couverts d'un foulard, châles et toges de coton blanc aux bordures tissées de couleurs vives, bijoux d'argent. Aucun élément moderne : ni immeuble, ni verre, ni métal moderne, ni vêtement contemporain ; chacun porte une tenue médiévale fantastique. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Demeure — `demeure_afrique01.jpg`

```
Réalise l'image de la façade d'une grande demeure de notable dans une cité-État d'Afrique australe, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. La demeure occupe environ 80 % de l'image, vue de trois-quarts depuis la rue : nombreuses pièces, logement du personnel, de quoi recevoir des invités. Une demeure ceinte de hauts murs courbes de pierre sèche appareillée sans mortier, ornés de frises à chevrons, une tour conique pleine ; derrière l'entrée, des cases de terre au toit de chaume et des cours dallées. La rue est calme : quelques passants seulement, bien espacés, laissent voir le pavé. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Domaine — `domaine_afrique01.jpg`

```
Réalise l'image d'un domaine clos au cœur d'une cité-État des hauts plateaux d'Abyssinie, en Afrique de l'Est, à l'intérieur de ses remparts ocre, dans le monde médiéval fantastique de Telluris, au format paysage 16:9, en vue d'ensemble légèrement plongeante : une demeure principale, ses dépendances et ses terres privées, en pleine ville, à l'abri de l'enceinte de la cité, car on ne vit pas près des monstres sans se protéger. Une demeure de pierre ocre à assises de bois aux extrémités rondes saillantes, des greniers, des cases rondes au toit de chaume pour le personnel, un potager, un petit champ de teff, des enclos et un haras ; le tout clos d'un mur de pierre sèche percé d'une porte de bois sur la rue. Tout autour du domaine, de tous côtés, la ville serrée : maisons de pierre ocre à assises de bois, cases rondes au toit de chaume, ruelles de terre rouge, et un champ de hautes stèles de pierre dressées ; à l'horizon seulement, le rempart ocre de la cité puis des montagnes aux sommets plats, au-dessus desquelles planent quelques chevaux ailés sauvages. Le domaine occupe environ la moitié de l'image, la ville l'entoure entièrement. Quelques silhouettes, toutes petites à cette distance, travaillent dans les cours et passent dans les rues. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres ; les ogres ont des teints humains, jamais verts. Ici, toutes les Lignées ont les traits des peuples des hauts plateaux d'Afrique de l'Est : peaux brunes à très sombres, cheveux crépus tressés ou couverts d'un foulard, châles et toges de coton blanc aux bordures tissées de couleurs vives. Aucun élément moderne : ni immeuble, ni verre, ni métal moderne, ni vêtement contemporain ; chacun porte une tenue médiévale fantastique. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

### 7.6 Océanie (`oceanie`) — Sydney, Melbourne (Australie)

#### Chambre — `chambre_oceanie01.jpg`

```
Réalise l'image de l'intérieur d'une chambre individuelle dans une auberge d'une cité-État au bord d'une grande baie d'Océanie, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. Vue depuis le seuil, la pièce entière est visible : petite, modeste et propre, on y dort et on y range quelques affaires. Des murs de grès doré, un plafond de poutres d'eucalyptus ; un lit bas tendu de cordages de fibres et couvert d'un manteau de peaux d'opossum cousues et gravées, un coffre de bois d'eucalyptus, des paniers tressés et un plat de bois creusé ; une fenêtre s'ouvre sur les eaux turquoise de la baie. La pièce est entièrement vide de personnages : le logis attend son occupant. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Logement — `logement_oceanie01.jpg`

```
Réalise l'image de l'intérieur d'un petit logement indépendant dans une cité-État d'Océanie, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. Vue depuis l'entrée sur la pièce principale, un passage vers une seconde pièce plus petite : un foyer simple pour un ou deux occupants. Des murs de grès ornés de motifs peints à points et de spirales ocre, blancs et rouges, un foyer, des nattes et des paniers tressés, des boomerangs et des propulseurs accrochés au mur, une couche couverte d'un manteau de peaux d'opossum ; la porte ouvre sur une terrasse ombragée d'écorce. La pièce est entièrement vide de personnages : le logis attend son occupant. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Maison — `maison_oceanie01.jpg`

```
Réalise l'image de la façade d'une maison individuelle dans une rue de grès d'une cité-État d'Océanie, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. La maison occupe environ 80 % de l'image, vue de trois-quarts depuis la rue : un véritable foyer de plusieurs pièces, ni pauvre ni fastueux. Une maison de grès doré au toit d'écorce et de bois, un large auvent sur des poteaux d'eucalyptus, des motifs peints à points sur les murs, un jardin d'arbustes à fleurs rouges, des eucalyptus à l'écorce blanche. La rue est calme : quelques passants seulement, bien espacés, laissent voir le pavé. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Demeure — `demeure_oceanie01.jpg`

```
Réalise l'image de la façade d'une grande demeure de notable sur une colline, à l'intérieur des remparts d'une cité-État médiévale d'Océanie bâtie autour d'une grande baie découpée, dans le monde médiéval fantastique de Telluris, au format paysage 16:9. La demeure occupe environ 80 % de l'image, vue de trois-quarts depuis la rue : nombreuses pièces, logement du personnel, de quoi recevoir des invités. Une grande demeure de grès doré sur deux niveaux, des terrasses étagées, des galeries ombragées sur des poteaux d'eucalyptus, de grandes fresques de spirales et de points qui racontent le voyage de trois frères, des bassins et des fougères arborescentes ; en contrebas, les toits bas de grès et d'écorce d'une ville modeste, aucune maison de plus de deux étages, quelques eucalyptus, la baie où mouillent des navires de bois à voiles, et le rempart de grès de la cité ; au-delà, des collines boisées. La rue est calme : quelques passants seulement, bien espacés, laissent voir le pavé. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres ; les ogres ont des teints humains, jamais verts. Aucun élément moderne : ni immeuble, ni tour d'habitation, ni opéra, ni verre, ni métal moderne, ni vêtement contemporain ; chacun porte une tenue médiévale fantastique faite de peaux, de fibres tressées, de lin et de laine. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

#### Domaine — `domaine_oceanie01.jpg`

```
Réalise l'image d'un domaine clos au cœur d'une cité-État médiévale d'Océanie, bâtie sur la côte au bord d'une baie largement ouverte sur l'océan, à l'intérieur de ses remparts de grès, dans le monde médiéval fantastique de Telluris, au format paysage 16:9, en vue d'ensemble légèrement plongeante : une demeure principale, ses dépendances et ses terres privées, en pleine ville, à l'abri de l'enceinte de la cité, car on ne vit pas près des monstres sans se protéger. Une demeure de grès doré aux toits plats et bas couverts d'écorce et ses dépendances, des jardins d'ignames, un petit bassin à poissons de pierre sèche, des eucalyptus à l'écorce blanche ; le tout clos d'un mur de grès lisse et arrondi, sans créneaux ni tours, orné de motifs peints à points ocre, blancs et rouges, percé d'une porte sur la rue. Tout autour du domaine, de tous côtés, la ville serrée : maisons basses de grès doré aux murs peints de spirales et de points, aux toits plats ou très peu pentus couverts d'écorce, sous de larges auvents d'écorce posés sur des poteaux d'eucalyptus, aucune de plus de deux étages ; ruelles et places. Rien d'européen : ni toits pentus de bardeaux ou de tuiles, ni colombages, ni créneaux, ni tours de château, ni conifères — les seuls arbres sont des eucalyptus, des acacias et des fougères arborescentes. D'un côté seulement, au-delà des toits et du rempart côté mer, la ville s'arrête sur le rivage : un port de bois où mouillent des navires à voiles, la baie qui s'ouvre sans obstacle sur l'océan jusqu'à l'horizon. Aucun lac ni plan d'eau à l'intérieur de la ville. De l'autre côté, à l'horizon, le rempart de grès de la cité, puis une forêt d'eucalyptus bleutée et des montagnes bleues. Le domaine occupe environ la moitié de l'image, la ville l'entoure entièrement. Au premier plan, en bas de l'image, la rue qui longe le mur du domaine est assez proche pour que chaque passant se reconnaisse, et on y reconnaît clairement les cinq Lignées, dispersées naturellement dans la rue, chacun à son occupation (l'un porte un panier, l'autre parle à un voisin, un troisième marche) — jamais alignés, jamais présentés côte à côte comme sur une planche de comparaison, aucune légende sous les personnages. Leurs tailles sont cohérentes entre elles : les humains et les elfes sont des adultes de taille ordinaire, dont la tête arrive au bord des auvents ; l'ogre dépasse un humain d'une tête et demie, massif et large d'épaules, à la peau épaisse — grand mais PAS un géant : aucun personnage n'est deux fois plus grand qu'un humain ; la naine sans barbe et le nain à la barbe noire et crépue arrivent à la poitrine d'un humain, trapus, aux grandes mains ; le hobbit arrive à la taille d'un humain, pieds nus ; l'elfe a de longues oreilles pointues bien visibles. Les humains sont nettement plus grands que les nains et les hobbits. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation, en proportions égales : aucune Lignée n'est plus nombreuse que les autres, les humains ne sont pas plus nombreux que les autres ; les ogres ont des teints humains, jamais verts. Ici, TOUTES les Lignées sans exception — l'ogre, la naine, le nain et le hobbit autant que les humains et les elfes — ont les traits et les tenues des peuples de cette terre : peaux brunes à très sombres, aucune peau claire, aucune barbe ni chevelure rousse ou blonde, cheveux bouclés ou ondulés, souvent noués d'un bandeau tressé ; manteaux de peaux d'opossum cousues et gravées de motifs, pagnes et ceintures de fibres tressées, colliers de coquillages et de dents, sacs de filet de fibres, peintures d'ocre blanche et rouge sur les bras ; lances, propulseurs et boucliers de bois gravé. Aucune tenue européenne, pour aucune Lignée : ni tunique de laine, ni gilet, ni chemise, ni capuchon, ni chausses, ni cotte de mailles, ni casque, ni bouclier de métal. Aucun élément moderne : ni immeuble, ni tour d'habitation, ni verre, ni métal moderne, ni vêtement contemporain. Aucun portail magique. Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.
```

---

## Annexe — versions d'origine

### MAGASIN
Réalise l'image d'un magasin du type 'archerie' du nom de 'L'Arc et la Corde de la Cité' dans un monde médiéval fantastique archerie à 'Lutecia' tenu par Nicolas Piedléger, un hobbit vif aux cheveux blonds bouclés. Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation. Pas de texte visible. Le magasin prend 80% de l'image. C'est dans un petit village à l'extérieur des remparts de Lutecia avec vue sur la capitale.

### TENANCIER
Réalise un portrait de 'Nicolas Piedléger, un hobbit vif aux cheveux blonds bouclés'  tenancier du magasin généré dans l'image précédente.  Il  nous regarde et nous propose ses marchandises. Sans texte apparrant.

### MONSTRE
Réalise moi l'image de style médiéval fantastique d'un 'Aigle Geant'. Il est décrit ainsi : 'Rapace d'envergure colossale, capable d'emporter un homme dans ses serres et de planer des heures durant.'. Le monstre doit faire 80% de l'image et le fond doit être uni de couleur opposée à l'image et sans parchemin ni texte ni autre fioriture. Voici quelques tags qui s'applique ["monstre", "vol", "predateur"]

### PORTE EXTERIEURE
Réalise une vue réaliste et détaillée de la porte principale fortifiée de Lutèce (Paris), dans un monde médiéval fantastique.

**Point de vue et géométrie :**
La caméra se trouve clairement **à l'extérieur de la ville**, face aux remparts et à leur porte principale. La scène montre une imposante fortification en pierre avec **une seule grande porte monumentale** percée dans les remparts.

La porte est **ouverte**. À travers l'ouverture, on doit voir clairement **l'intérieur de Lutèce** : une rue qui pénètre dans la ville, des bâtiments médiévaux, des maisons, des tours et une partie de la cité derrière les remparts.

La perspective doit rendre évident que la caméra se trouve **à l'extérieur** et que la route visible à travers la porte mène **vers l'intérieur de la ville**.

Les remparts encadrent la porte et doivent être suffisamment hauts et massifs pour former une séparation visuelle claire entre l'extérieur et l'intérieur de Lutèce. Les bâtiments de la ville peuvent être visibles **à travers l'ouverture de la porte et derrière les remparts**, puisque la caméra regarde vers l'intérieur de la cité.

Il n'y a **aucune sous-porte, aucune porte secondaire et aucune ouverture latérale**. Une seule porte principale, large et monumentale, constitue le passage à travers les remparts.

**Garde de la porte :**
La porte est fortement gardée. Cinq gardes contrôlent principalement **les personnes qui entrent dans la ville**, donc les voyageurs arrivant depuis l'extérieur et passant sous la porte. Un seul garde surveille principalement **les personnes qui sortent de la ville**, se dirigeant vers l'extérieur.

Les gardes sont des personnages humanoïdes de différentes races : elfes, nains, hobbits, ogres et humains. Ils portent des équipements et armures médiévaux fantastiques cohérents avec leur fonction de gardes d'une cité fortifiée.

La composition doit rendre immédiatement compréhensible que :

* la caméra est **à l'extérieur de Lutèce** ;
* la caméra regarde **vers l'intérieur de la ville** ;
* la porte ouverte permet d'entrer dans Lutèce ;
* la ville est visible **à travers l'ouverture de la porte** ;
* les cinq gardes contrôlent principalement les voyageurs entrant dans la ville ;
* un seul garde surveille principalement les personnes quittant la ville.

**Architecture :**
Architecture médiévale fantastique inspirée de Lutèce/Paris : puissants remparts en pierre, grande porte fortifiée, tours défensives, créneaux, chemin de ronde, herse éventuellement relevée et dispositifs défensifs crédibles.

À travers la porte, montrer progressivement la ville médiévale de Lutèce : rue pavée entrant dans la cité, bâtiments en pierre et bois, toits, maisons, tours et autres constructions urbaines. La ville doit sembler protégée et dense, mais rester cohérente avec une cité médiévale fortifiée.

La route extérieure devant la porte doit clairement appartenir au **territoire extérieur à la ville** et rejoindre le passage de la porte.

Ambiance réaliste, proportions architecturales cohérentes, perspective naturelle, niveau de détail élevé, aspect de concept art de jeu vidéo médiéval-fantastique.

**Contraintes importantes :**

* une seule porte ;
* aucune sous-porte ;
* aucune porte latérale ;
* aucune ouverture secondaire dans les remparts ;
* la caméra est sans ambiguïté **à l'extérieur de la ville** ;
* la ville est visible **à travers la porte ouverte** ;
* la route extérieure mène directement à la porte ;
* la route visible derrière la porte appartient à **l'intérieur de Lutèce** ;
* les bâtiments de Lutèce ne doivent être visibles que du côté intérieur, derrière la porte ;
* aucun élément ne doit inverser les deux côtés de la fortification ;
* aucun texte, aucune inscription, aucun symbole écrit ou panneau lisible dans l'image.

**NE PAS MONTRER :** sous-portes, portes latérales, passages secondaires, bâtiments de la ville devant les remparts du côté extérieur, ville située du mauvais côté de la porte, paysage extérieur visible à travers la porte à la place de la ville.

### PORTE INTERIEURE
Réalise la vue de cette même porte depuis l'intérieure de la ville. **NE PAS MONTRER :** sous-portes, portes latérales, passages secondaires, bâtiments de la ville devant les remparts du côté extérieur, ville située du mauvais côté de la porte, paysage extérieur visible à travers la porte à la place de la ville. Retire les bâtiments visibles au dessus de la muraille qui ne sont pas dans l'enceinte de la ville. Des ogres, des nains, des elfes, des hobbits et des humains vaquent à leurs occupations.
