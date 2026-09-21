---
name: telluris-economie
description: Items, weight, currency and the market — inventory item references & weight, carry capacity/overload, currency tiers, weapon/raw-material content rules, haggling/relation-driven pricing, higher-tier shops merging categories (LIEU_CATEGORIES_FUSION), geographic recipe scope (lieu_portee), the city goods flow between workshops (flux_marchand), and ordering from a craftsman — made-to-order catalogue pieces and generated custom variants with their `sur_commande` recipes (utils/characters.py, utils/marche.py, utils/commande.py, utils/fabrication.py, routers/user.py market endpoints, routers/commande.py). Load when working on inventory weight, the shop/market, pricing, recipes, the workshop tick, crafting materials, or placing/customising an order at a shop.
---

### Références d'items & poids
Entrée d'inventaire = **string legacy** `"item:xxx"` (poids = min) **ou objet** `{"item": "item:xxx", "poids": <nb>}` ; le champ `poids` d'un doc `item:*` est un nombre OU `[min,max]`. Helpers `item_ref_id`/`poids_bounds`/`item_ref_weight`/`resolve_item_ref` couverts par `tests/test_item_ref.py`. Une référence peut porter **`lieu_parent`** = le lieu qui a délivré CET exemplaire (`item_ref_lieu`), dont `resolve_item_ref` dérive un label localisé (« Carte d'aventurier (Auxerre) ») sans jamais toucher le doc item générique.

**Nom propre d'un exemplaire** (`POST /api/renommer_objet`, objets **équipables** seulement : `slots` non vide) : `nom_perso` sur la **référence** (`characters.renommer_ref` ; une chaîne legacy devient un dict au poids figé). `resolve_item_ref` l'applique **en dernier** et rend le libellé calculé en `nom_origine` (sous-titre de la fiche). Suit la ref (équiper, poser, transférer, profil d'arme en combat — `label`, jamais `effets_source_id`) ; **disparaît à la vente** (rayon stocké par id). ⚠️ `nettoyer_nom_objet` = **lettres, chiffres, espace, `’ - . ,`**, `'` → `’`, 40 signes : c'est la défense XSS, les noms d'objets étant interpolés sans échappement dans tout le client. ⚠️ `/equip` prend un **`index`** optionnel : sans lui, deux exemplaires identiques dont un renommé seraient indiscernables. Verrouillé par `tests/test_renommer_objet.py`.

**Nom affichable d'un LIEU = `characters.lieu_label(doc, id?)`**, pendant de `item_label` et **source unique** : le nom d'un lieu part dans les libellés de quêtes, les placeholders de dialogue, l'onglet 🤝 et le guidage 🧭. ⚠️ Les docs `lieu:*` portent **`label` et lui seul** (90/90 dans le dump — ni `nom`, ni `description`) ; le dernier repli est le **slug** de l'id, jamais l'id entier. ⚠️ Il prend le **DOC**, pas l'id : les `lieu:*` sont les plus gros documents du jeu et sont exclus du cache de requête. La formule était recopiée à sept endroits et l'un d'eux l'avait oubliée — `quetes._cible_nom` n'aiguillait pas le type **`escorte`**, et la fiche annonçait « Escorter … jusqu'à : `lieu:athanor` ». ⚠️ Tout type d'objectif dont la cible est un lieu doit figurer dans son tuple, et lui recevoir le getter **mémoïsé** de la passe.


### Charge & surcharge
`charge_max_of(character)` (dérivée de F, jamais stockée) et `carried_weight(character)` (inventaire + équipés, pas le sol) sont couverts par `tests/test_character_stats.py`/`tests/test_groupe.py`. En **exploration**, dépasser la charge bloque le déplacement (409) et le pickup fait tomber des items aléatoires au sol ; en **combat**, au-delà de la demi-charge le déplacement est divisé par deux.


### Monnaie & marché
3 paliers Or/Argent/Cuivre. Éligibilité marchand (`lieu_buys`, `params_vente_lieu`), agrégation du sac du groupe pour la vente (compagnons **et** montures, via `recrutement.porteurs_effectifs`, obligatoire aux 4 endpoints du marchand sans exception), coût de revient (`valeur` explicite ou récursif via les recettes), prix marché (`prix_courant × facteur_stock`) et tick d'atelier (appro des feuilles, production en pool unifié, écoulement PNJ) sont couverts par `tests/test_marche_recettes.py` et `tests/test_appro_comptoir.py` — dont le test de non-régression sur l'exploit d'arbitrage achat-revente via le rayon (`RACHAT_FACTEUR`). Dépeçage : matières gated par tags d'espèce (`DEPECAGE_TAGS`), surplus non consommé par une recette du lieu déplacé en rayon et vendu au joueur.

**Coût des 4 endpoints du marchand** — chemin le plus lourd du jeu : `marchand_quotes` est `def` (lecture pure, threadpool) tandis que `sell_item`/`buy_item`/`marchander` restent `async def` et donc **sérialisés** (écriture, `save_doc(lieu_doc)` best-effort). ⚠️ **`relations_lieux` n'est renvoyé QUE par ce qui fait bouger une relation** — ce payload relit tous les docs `relation` et un doc lieu COMPLET par lieu connu. Côté client, le panneau s'ouvre **avant** le fetch, les boutons se désactivent pendant la requête, et le rendu du sac/sol/silhouette est différé tant que `#sell-panel` masque la fiche.


### Armement & matières premières (contenu)
**Un modèle d'arme = UN doc.** ⚠️ Ne pas recréer de paliers de qualité en documents (`item:X_2`…`_7`) : une échelle de qualité devra être une **mécanique** (modificateur d'instance), jamais un clone de doc.

**`manche` vs `hampe`** : deux sous-catégories de fût, et c'est le fût qui décide de la portée (`manche` = portée 1 et arcs ; `hampe` = armes d'hast, `portee ≥ 2`), toutes deux produites sur place via le pool unifié du tick atelier.

⚠️ **Toute matière consommée par une catégorie de lieu devient une feuille auto-approvisionnée, donc ACHETABLE sur place** (`appro_leaves_categorie` → `approvisionner`) : écrire une recette, c'est ouvrir un point de vente pour chacun de ses intrants bruts. Ne jamais y mettre une matière dont la **rareté fait le sel d'une quête ou d'un don** (les armes bénies consomment de l'`argent`, pas `item:Eau_benite`). Symétriquement, c'est le bon levier pour ouvrir un débouché à du butin de dépeçage.

⚠️ « Achetable » tient à **DEUX destinations dans `approvisionner`** (`stock_matieres` pour l'atelier, `stock_vente` pour le comptoir) — rien ne fait jamais passer une matière de l'un à l'autre, et la vitrine est regarnie **jusqu'au `stock_cible` et jamais au-dessus**, ce qui rend le comptoir neutre pour l'atelier. Épinglé par `tests/test_appro_comptoir.py`.

⚠️ **Le seul transfert entre deux `lieu:*`, hors quête de transport** : le **flux de cité** (§ Flux de marchandises, plus bas).

⚠️ **Deux exceptions, assumées** : `APPRO_DEBIT` à 0 ⇒ aucune livraison (`herbe`, récolte joueur seule) ; `matiere_item_id` rendant un id inexistant ⇒ fail-soft, consommable en production mais jamais vendu (`branche`, `rondin`…). ⚠️ Créer le doc item manquant suffirait à les mettre en vente **sans qu'on l'ait décidé**.

⚠️ **La FAUSSE feuille — le piège le plus silencieux de la chaîne.** Une matière qu'une recette produit *quelque part* n'est **pas** une feuille (`_get_marche_map` : `feuilles = inputs − outputs`), donc `approvisionner` ne la livre **jamais** : elle ne peut venir que du flux de cité ou du joueur. Si elle manque, **toutes** les recettes qui la citent deviennent inapplicables, en silence — l'amont continue de cuire et le rayon enfle de l'intermédiaire que plus personne ne consomme. Signature à reconnaître : un intrant à 0 et son voisin à 30× sa cible. Cas vécu : `item:Plume_d_oie` (produite par `plume_a_ecrire`, et sa matière `plumes` produite par la boucherie — deux fausses feuilles d'affilée) a gelé les 112 recettes de grimoire jusqu'au 20/09 (`dev/gen_grimoires_sans_plume.py` l'a retirée). ⚠️ Avant d'ajouter un intrant à une recette : vérifier qu'il est une feuille, ou qu'un flux l'amène vraiment.

⚠️ **Un LIVRE déjà en rayon se refait moins** (`marche._poids_tirage`) : pour une recette dont le produit est `categorie == "livre"` (grimoire, traité, recueil, carte), le poids de tirage est divisé par **2 × la quantité déjà exposée** (1 → /2, 2 → /4…), recompté à chaque cuisson. Sans cela, 112 recettes de grimoire de poids identique faisaient du rayon une loterie à 1/112 où un sort neuf attendait derrière les rééditions (catalogue complet en ~5 passes au lieu de 50+, à volume produit égal). Ne vaut **que** pour les livres — un rayon de pain ou de fer doit continuer de se remplir — et seulement si `resolve_fn` répond. Verrouillé par `tests/test_marche_recettes.py`.

⚠️ Une clé matière **sous-catégorie** est résolue en `item:<sous_categorie>` par `matiere_item_id` : ce doc doit exister, sinon la matière est valorisée à vide. Quand l'item générique porte un autre id, utiliser la forme **`{"item": "item:XXX", "quantite": n}`**.

Contenu : `jsons/armes_hast_a_importer.json` (armes d'hast, matières `item:hampe` + `item:argent`, recettes d'armurerie/tabletterie).


### Marchandage & relations
`prix_courant` = prix négocié ou prix de base pondéré par la relation (0-100, neutre 50) ; **prix appliqué** = `prix_marche` (re-clampé par le facteur de stock). La négociation est persistée comme **FRACTION de la fourchette**, pas comme montant fixe. Relation = doc `type:"relation"` (char × lieu), avec crit ok/fail sur `POST /api/marchander` et blocage temporaire en cas d'échec critique. Formules, fidélité (`marche.compter_transaction`, +1 relation tous les N échanges sous un seuil) et persistance sont couverts par `tests/test_marche_recettes.py` et `tests/test_quetes_relation.py`.


### Magasins de niveau supérieur — fusion de catégories
Une catégorie de lieu peut **en inclure d'autres** : `LIEU_CATEGORIES_FUSION` (variable de monde, `models/character_stats.py`), ex. `grande_apothicairerie` = apothicairerie + jardinier + ses recettes propres. 18 grandes maisons à Lutèce (`dev/gen_magasins_superieurs.py`). Verrouillé par `tests/test_magasins_superieurs.py`.

- Résolu **à la lecture** (`marche.categories_incluses`, transitif, catégorie propre en tête, anti-cycle) ; les index restent sur la valeur **littérale** de `recette.lieu_categorie` ⇒ **aucune recette dupliquée en base**, régler la table à chaud = `reset_prix_cache()`. Les quatre accesseurs (`besoins_categorie`, `appro_leaves_categorie`, `produits_categorie`, `lieu_recettes`) unionnent : **aucun site d'appel n'a changé**.
- ⚠️ Une capacité se perd à la fusion si son prédicat ne teste que la catégorie : le grand scriptorium porte `tags: ["scriptorium"]` (même échappatoire pour `auberge`/`etable` si on les fusionne un jour).
- ⚠️ Une recette exclusive doit être **CROISÉE** — aucun métier réuni ne fournit seul tous ses intrants —, sinon la grande maison n'apporte rien. Contrôlé à la génération (`_metier_unique`), qui refuse d'écrire.


### Portée géographique des recettes — spécialités de terroir
`recette.lieu_portee` (id de lieu) : cuisinable seulement par les boutiques dont la chaîne `lieu_parent` remonte jusqu'à lui ; **absent ⇒ portée mondiale**. Contenu `dev/gen_specialites_france.py`. Verrouillé par `tests/test_recettes_portee.py`.

- `marche.portees_lieu(lieu_doc)` = le lieu puis ses ancêtres, **mémoïsé** : `lieu:` est hors du cache de requête et la nuit d'auberge tique toutes les boutiques de la cité.
- Une recette portée sort des index par catégorie ; seules les variantes **`recettes_lieu` / `besoins_lieu` / `produits_lieu` / `appro_leaves_lieu`** (qui prennent le doc) la servent. `scriptorium.recettes_effectives` reste le chokepoint des 4 sites de tick.
- ⚠️ **`feuilles` reste GLOBAL** : une matière que seule une recette portée consomme n'est livrée qu'aux boutiques dans la portée — c'est ce qui rend le mécanisme visible en jeu.
- ⚠️ **Le prix reste MONDIAL** (`_get_recipe_map` / `_cout_memo` non scopés) : scoper ferait dépendre le prix du premier lieu demandeur du process et rouvrirait l'arbitrage « acheter où c'est produit, revendre ailleurs ». **La portée dit où l'on fabrique, jamais combien ça vaut.**
- ⚠️ Les cités portent `lieu_parent: "lieu:france"` : toute remontée d'ancêtres qui cherche « la ville » doit s'arrêter aux `categorie == "ville"` (`quetes.lieux_solidaires`, `marche.flux_cite`) — sinon Auxerre et Reims deviennent sœurs, ou le flux se pose sur le pays.


### Flux de marchandises entre boutiques d'une cité
Le **seul transfert entre deux `lieu:*` hors quête de transport**. Pool `flux_marchand: {item_id: qty}` sur le doc de la **ville**, où les ateliers dont une recette en a l'usage puisent **en réserve** (`stock_matieres`, clé `cle_matiere_lieu`). Champ absent ⇒ comportement d'avant. Verrouillé par `tests/test_flux_pnj.py`.

**DEUX alimentations, et il faut les deux :**
- `_crediter_flux` — part `VENTE_PNJ_REDISTRIB` de ce que les PNJ viennent d'acheter (`ecouler_produits_pnj`). Aléatoire et menue.
- `_deverser_surplus_flux` — tout ce qui dépasse le `stock_cible` du rayon, **déterministe**, part `FLUX_SURPLUS_PART`. ⚠️ Sans lui le crédit PNJ passait par quatre portes multiplicatives et deux arrondis (`round(0.5) == 0`) : **55 exemplaires en rayon** (cible 25) pour qu'UNE unité atteigne la ville, rien en dessous. Mesuré sur le dump du 16/09, 60 sangliers vendus au boucher de Lutèce : pool 1 tendon → 25, et l'armurier passe de 3 à 62 ligatures.

- ⚠️ **`flux=None` ⇒ tick strictement d'avant.** L'appelant ouvre (`flux_cite`), passe le contexte à N `tick_atelier`, referme (`persister_flux` : une écriture, seulement si le pool a bougé). La nuit d'auberge l'ouvre **hors de la boucle** (sinon ~60 × N `find_docs`).
- ⚠️ **Ordre du tick** : puiser AVANT d'écouler (sinon une boutique reprend ce qu'elle vient de vendre), **déverser en DERNIER** (sinon le rayon est déjà à la cible quand `ecouler_produits_pnj` passe et la vente PNJ meurt en silence).
- ⚠️ **Deux gardes symétriques** : on ne **puise** pas ce que le lieu produit (`lieu_produit` — sinon corde → arc tournerait en manège), on ne **déverse** pas ce que le lieu consomme (`besoins_lieu` — le surplus de rayon EST la matière du prochain batch, cf. pool unifié, et `lieu_produit` interdirait de le reprendre).
- `cles_consommees()` = **seul index inverse** du marché ; pool plafonné par clé à `STOCK_CIBLE_DEFAUT` (pas de second réservoir non borné) — ce qui ne rentre pas reste en rayon, où les PNJ le reprendront.
- ⚠️ `puiser_flux` prend une **PART** de la ligne (`FLUX_PART_MAX`, plancher d'une unité), pas le lot entier : le pool est un bien commun et trois ateliers peuvent réclamer le même cuir.
- ⚠️ **`carcasse` ne circule jamais** : aucun doc `item:carcasse`, et la clé n'est écrite nulle part — `_matieres_entrantes` décompose la bête **À LA VENTE** (les 16 recettes `carcasse → X` de la boucherie ne cuisent jamais, elles servent de **table de quantités** à `convertir_apres_achat`). C'est le seul point d'entrée de l'aventurier, et le seul verrou de l'économie : carcasse accordée, les 614 recettes du monde cuisent.
- **Découpe des grosses carcasses** (`dev/gen_carcasses_parties.py`, `utils/carcasse.py`) : carcasse > `CARCASSE_DECOUPE_POIDS_MIN` → portions anatomiques `item:<espece>_<partie>` ; portion encore trop lourde → n `item:<portion>_morceau` identiques, tous < seuil à poids max (`nb_morceaux`), sans `decoupe` (terminal). ⚠️ Tout doc portant **`portion_de`** n'est JAMAIS une source : sans cette garde, une relance produisait `item:aigle_geant_corps_tete`. Relancé sur dump frais ; le fichier ne porte que le **diff** (nouveaux + modifiés, repris du dump pour garder les clés manuelles — PUT complet), base à jour ⇒ aucun fichier ; orphelins listés (verrouillé par `tests/test_gen_carcasses_parties.py`).


### Commande auprès d'un artisan
`utils/commande.py` (cycle, sourçage, devis) + `utils/fabrication.py` (variantes) + `routers/commande.py` + 3ᵉ section de `#sell-panel`. Verrouillé par `tests/test_commande.py`, `tests/test_fabrication.py`, `tests/test_sur_commande_index.py`.

**DEUX capacités, indépendantes** — les confondre laisserait n'importe quelle échoppe créer des docs permanents :

| | qui | dérivé de |
|---|---|---|
| **prendre une commande** (refaire son catalogue, vitrine vide) | tout atelier | son **catalogue épuré** n'est pas vide — ni catégorie ni tag, donc **hors de `capacites.CAPACITES`** |
| **fabriquer sur mesure** (variante inédite) | grande maison | `categorie ∈ LIEU_CATEGORIES_FUSION` **OU** tag `sur_mesure` — 6ᵉ entrée du catalogue, `categories` relue par `capacites.categories_de` |

⇒ la trichotomie petit magasin / artisan / grand magasin **sans authorer un doc**. Flags de `/play` : `est_commande` (la section) et `est_sur_mesure` (le seul bouton « ✨ Sur mesure »).

**⚠️ Le catalogue écarte les MATIÈRES et DEMI-PRODUITS** — `marche.item_commandable`, `categorie ∈ `**`CATEGORIES_INTERMEDIAIRES`**` = {composant, metal}` (variable de monde). L'Arsenal de Lutèce proposait « Hampe », « Cuir », « Acier plissé », « Manche », « Ligatures », « Cordes d'arc » à côté de ses 133 armes : 144 → 138 lignes, 2757 → 2268 sur le monde, 121 → **106 boutiques** prenant commande (11 boucheries + 4 tanneries ne produisent QUE des matières et perdent leur section — d'où `lieu_prend_commandes` = « catalogue épuré non vide » et non « a des recettes »).

- **Dérogation** = tag `commandable` sur le doc item. Aucun posé à la livraison. ⚠️ Il rouvre la **commande**, **jamais le sur-mesure** : `marche.est_intermediaire` (pur, doc en main, sans dérogation) reste le prédicat du façonnage. Confondre les deux prédicats laisserait façonner un lingot.
- ⚠️ **Le mémo `_commandable_memo` est vidé par `reset_prix_cache()`** — sans quoi poser le tag depuis `/admin` resterait sans effet jusqu'au redémarrage. `item` est dans `main._TYPES_PRIX`, donc l'écriture déclenche déjà le vidage : la dérogation prend effet à chaud.
- ⚠️ **Classement par CATÉGORIE, pas par « consommé par une recette »**, mesuré et écarté : `item_sous_categorie` retombe sur `categorie`, donc une recette consommant la clé `arme` faisait passer Arc long, Plumbata, armure de cuir et harnais pour des intermédiaires. Au dump du 20/09 les 438 items `composant`/`metal` sont **tous** non équipables (`slots` vide) — la catégorie classe juste.

**⚠️ Le piège central — `sur_commande`.** Une recette de variante est un doc `recette:*` ordinaire à un drapeau près. Filtrée aux **consommateurs**, jamais à `_all_recettes` :
- `_get_recipe_map` la **garde** (le prix de la variante doit dériver de ses intrants) ;
- `_get_marche_map` et `lieu_recettes` la **sautent**.

Sans cette coupure, rien ne lève : toutes les boutiques de la catégorie se mettent à fabriquer et exposer la pièce unique d'un joueur, chacun de ses intrants devient une feuille auto-approvisionnée donc vendue au comptoir, et le recalcul global `feuilles = inputs − outputs` peut créer une **fausse feuille**. Corollaire assumé : la variante sort de `produits_lieu`, d'où le repli de `lieu_produit` sur `fabrication.base_item` — sinon une pièce commandée ne se revendrait nulle part.

**Le prix — ne JAMAIS refacturer les ingrédients.** `prix_base` = `prix_marche(…, "achat", stock=0, …)` (l'objet n'est pas en vitrine : c'est la situation même), et il contient **déjà** le coût propagé des ingrédients (× `MARGE_TRANSFO`). D'où deux traitements :
- ingrédient de la RECETTE apporté par le joueur → **remise** (`credit_matieres`, plafonnée à `prix_base` — sans ce plafond : acheter du fer au comptoir, le rapporter, repartir avec l'épée pour 1 cu) ;
- matière SUR MESURE → **supplément** (`cout_matieres`), elle n'est dans le prix d'aucun objet de base.

`total = prix_base − remise + matières sur mesure + façon + complexité`. La façon (`COMMANDE_FACON_PART`) se paie même quand le client apporte tout ; la complexité ne court qu'à partir de la 2ᵉ matière. ⚠️ `COMMANDE_MARGE` est **distincte de `MARGE_TRANSFO`** : à ×5 par étape, la variante d'un objet déjà transformé coûterait ×25. La variante porte une **`valeur` explicite figée** à la création, ce qui coupe la propagation (`cout_production_cuivre` traite `valeur` comme autoritative).

**Sourçage (§7), DEUX passes à `retenus` partagés** (sans partage, le même lingot serait crédité *et* fourni gratuitement) :
- ingrédients de recette → sac du groupe, puis **`stock_matieres` de l'artisan** puis son rayon, sans rien facturer. ⚠️ C'est la seule lecture de la réserve : l'artisan ne la VEND pas (ce serait l'interdit du § Armement), il la CONSOMME comme le ferait son tick. Sans elle, **65 %** du catalogue du monde naîtrait `en_attente_materiaux` — les intermédiaires (cuir, tendons, os…) vivent en réserve, pas en vitrine ; avec elle, 46 % restent en attente, ce qui est la rareté réelle du contenu (`carcasse`, `Plume_d_oie`, `cuir`).
- matières sur mesure → sac, puis **`stock_vente` seulement**, au prix du marché.
- introuvable ⇒ `en_attente_materiaux`, rien n'est prélevé ni débité ; `POST /commande/relancer` re-résout **tout depuis zéro** (prix et stocks ont bougé) et remplace l'entrée.

⚠️ **Appariement d'une clé de recette = `commande.correspond`**, source unique : id, **ou** sous-catégorie, **ou** `marche.matiere_item_id(cle) == item_id`. Le troisième n'est pas du zèle — `item:argent` porte `sous_categorie: "metaux_precieux"` alors que les 17 recettes d'armurerie le désignent par la clé `argent`.

**Cycle de vie** : `en_attente_materiaux` → `payee` → (`en_fabrication` → `terminee` → `expiree`) → `livree` / `annulee` / `impossible`. ⚠️ Les trois du milieu sont **DÉRIVÉS de l'horloge** (`statut(cmd, now)` lit `pret_at`) : aucun tick de fond, aucun des 5 sites de `traiter_expirations` touché. La liste vit **sur le doc personnage** — prélèvement et inscription dans la MÊME mutation, donc le même `save_doc` : double consommation et double fabrication impossibles sans transaction inter-documents. ⚠️ `purger_commandes` s'appelle **AVANT** le save, sinon la liste nettoyée ne vit qu'en mémoire ; une commande `expiree` n'est pas balayée (le joueur doit voir ce qu'il a perdu). **Nuit à l'auberge** (`achever_pendant_la_nuit`, appelé par `/auberge/nuit`) : toute commande `en_fabrication` voit son `pret_at` ramené à l'instant de la nuit → `terminee` au réveil, péremption comptée depuis le réveil ; attente de matériaux et états figés intacts.

**Variantes** : `signature()` normalise les matières (agrégées par id, triées) puis `sha1` — ⚠️ pas `hash()`, salé par processus. Même combinaison ⇒ même `item:<base>_<sig8>` ⇒ **une définition, N exemplaires**. `assurer_variante` ne retouche JAMAIS un doc existant et lève sur un `_id` occupé par autre chose (un PUT complet l'écraserait). L'exemplaire reste une **référence d'inventaire** enrichie (`fabrique_par`, `commande_at`), jamais un doc.

**Ce qu'une matière apporte vit dans la DONNÉE** : bloc `fabrication: {nom, modificateurs}` sur son doc item (`dev/gen_fabrication_matieres.py`, table `MATIERES` ; même contrat que les carcasses : dump frais, fichier = **diff** repris du dump, base à jour ⇒ aucun fichier, blocs posés hors table listés comme orphelins — verrouillé par `tests/test_gen_fabrication_matieres.py`). Bloc absent ⇒ la matière est utilisable mais n'apporte rien (les 1 324 items en base). ⚠️ `CLES_MODIFIABLES` est une **liste blanche** — un doc de contenu ne doit pas pouvoir injecter `slots`, `sorts` ni `type`. Composition : additif sur les `bonus_*` (× quantité), fusion clé à clé sur `bonus`/`effets`, **max** sur `restriction`, `{facteur}` multiplicatif sur `poids`/`valeur`, palier le plus haut sur `rarete` (échelle relue dans `MULT_RARETE`). ⚠️ Les facteurs ne sont PAS multipliés par la quantité : « une épée en acier » ne doit pas peser dix fois plus parce qu'on a fourni dix lingots.

⚠️ **Le générateur ne touche AUCUNE recette** : ajouter un intrant ouvrirait un point de vente pour lui et risquerait la fausse feuille (cf. § Armement).

