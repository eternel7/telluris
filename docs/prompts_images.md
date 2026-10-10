# Prompts d'images — Telluris

Gabarits de prompts pour générer les illustrations du jeu (Gemini). Chaque gabarit est une **phrase à trous** : les `{champs}` sont remplis depuis la base (dump), ce qui permet de produire des lots par script.

## 0. Règles communes

### 0.1 Bloc de style (ajouté à la fin de CHAQUE prompt)

> Illustration de fantasy médiévale semi-réaliste, dans le style d'un RPG narratif 2D haut de gamme : peinture numérique détaillée, lumière naturelle, palette chaude et terreuse, proportions crédibles. Aucun texte, aucune lettre, aucune inscription, aucun panneau lisible, aucun logo, aucune signature, aucun filigrane.

### 0.2 Foule de Telluris (quand la scène est peuplée)

> Des ogres, des nains, des hobbits, des elfes et des humains vaquent à leur occupation.

(Phrase d'origine de l'auteur, à garder **telle quelle** dans tout prompt peuplé — portraits de tenanciers compris.) ⚠️ **Répartition ÉGALE entre les cinq Lignées** (consigne de l'auteur, 10/10/2026) : avec un tenancier humain, le modèle peuplait la rue d'humains — le prompt précise « en proportions égales… les humains ne sont pas plus nombreux que les autres, même si le tenancier est humain » (`FOULE_FR` / `FOULE` de `dev/gen_images_magasins.py`).

- ⚠️ **Âge des tenanciers** (même date) : des **adultes de tous âges** (`AGES` : huit âges, un seul vieux), et l'âge tiré est **redit** dans le prompt pour que le modèle ne le vieillisse pas — le vieillissement touchait toutes les Lignées (hobbits peut-être exceptés).

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
| Monstre | carré 1:1 | `templates/resources/monsters/` | `<slug_espece>_transparent.png` (fond retiré après génération) |
| Porte (ext./int.) | paysage 16:9 | `templates/resources/towns/` | `<slug_porte>.png` |

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

### 0.6 Enregistrement

Chaque image générée est écrite **directement dans son dossier cible** (cf. 0.3), et **n'écrase jamais** un fichier existant : si `…01` est pris, on passe à `…02`, et ainsi de suite.

**Format de fichier** : celui que rend le modèle, sans conversion (Flash Lite → `.jpg`). Seuls les **monstres** sont en **PNG**, pour la transparence du fond détouré. Les extensions `.png` du tableau 0.3 valent donc pour les monstres ; ailleurs, `.jpg` comme `.png` conviennent.

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

`{couleur_fond}` = une couleur absente de la créature, pour que le fond se retire automatiquement (Pillow, `dev/` — détourage par couleur depuis les bords) : **magenta** par défaut, **vert vif** si la créature est rose, violette ou rouge, **bleu vif** si elle est verte. Le fichier détouré s'enregistre en `<slug_espece>_transparent.png`.

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
