---
name: telluris-economie
description: Items, weight, currency and the market: inventory item references & weight, carry capacity/overload, currency tiers, weapon/raw-material content rules, and haggling/relation-driven pricing (utils/characters.py, utils/marche.py, routers/user.py market endpoints). Load when working on inventory weight, the shop/market, pricing, or crafting materials.
---

### Références d'items & poids
Entrée d'inventaire = **string legacy** `"item:xxx"` (poids = min) **ou objet** `{"item": "item:xxx", "poids": <nb>}` ; le champ `poids` d'un doc `item:*` est un nombre OU `[min,max]`. Helpers `item_ref_id`/`poids_bounds`/`item_ref_weight`/`resolve_item_ref` couverts par `tests/test_item_ref.py`. Une référence peut porter **`lieu_parent`** = le lieu qui a délivré CET exemplaire (`item_ref_lieu`), dont `resolve_item_ref` dérive un label localisé (« Carte d'aventurier (Auxerre) ») sans jamais toucher le doc item générique.

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

⚠️ **Deux exceptions, assumées** : `APPRO_DEBIT` à 0 ⇒ aucune livraison (`herbe`, récolte joueur seule) ; `matiere_item_id` rendant un id inexistant ⇒ fail-soft, consommable en production mais jamais vendu (`branche`, `rondin`…). ⚠️ Créer le doc item manquant suffirait à les mettre en vente **sans qu'on l'ait décidé**.

⚠️ Une clé matière **sous-catégorie** est résolue en `item:<sous_categorie>` par `matiere_item_id` : ce doc doit exister, sinon la matière est valorisée à vide. Quand l'item générique porte un autre id, utiliser la forme **`{"item": "item:XXX", "quantite": n}`**.

Contenu : `jsons/armes_hast_a_importer.json` (armes d'hast, matières `item:hampe` + `item:argent`, recettes d'armurerie/tabletterie).


### Marchandage & relations
`prix_courant` = prix négocié ou prix de base pondéré par la relation (0-100, neutre 50) ; **prix appliqué** = `prix_marche` (re-clampé par le facteur de stock). La négociation est persistée comme **FRACTION de la fourchette**, pas comme montant fixe. Relation = doc `type:"relation"` (char × lieu), avec crit ok/fail sur `POST /api/marchander` et blocage temporaire en cas d'échec critique. Formules, fidélité (`marche.compter_transaction`, +1 relation tous les N échanges sous un seuil) et persistance sont couverts par `tests/test_marche_recettes.py` et `tests/test_quetes_relation.py`.

