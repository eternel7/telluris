"""Commandes auprès d'un artisan (pur) : faire fabriquer ce qui n'est pas en rayon.

DEUX capacités distinctes, et c'est la distinction qui porte tout le système :

1. **Prendre une commande** — `lieu_prend_commandes`, entièrement DÉRIVÉ : tout atelier sait
   refaire ce que ses recettes produisent déjà, même si sa vitrine est vide. Aucun tag, aucun
   contenu à écrire, aucune migration. Une échoppe sans recettes ne prend aucune commande —
   ni une boucherie, dont les seize recettes ne rendent que des matières.
2. **Fabriquer sur mesure** — `lieu_fabrique_sur_mesure` : assembler une VARIANTE inédite à
   partir de matières. Réservé aux grandes maisons (`LIEU_CATEGORIES_FUSION`) ou à un artisan
   promu par le tag `sur_mesure`. ⚠️ C'est la SEULE porte de `fabrication.assurer_variante` :
   hors d'un grand magasin, aucun doc `item:`/`recette:` n'est jamais créé.

⚠️ **Une MATIÈRE ou un DEMI-PRODUIT ne se commande pas** (`marche.item_commandable`) : l'Arsenal
de Lutèce proposait « Hampe », « Cuir » et « Acier plissé » à côté de ses 133 armes et armures.
Le tag `commandable` sur un doc item déroge à cette règle, **mais jamais au sur-mesure** : on ne
façonne pas un lingot à la demande, fût-il remis au catalogue (`marche.est_intermediaire`).

Ce qui donne la trichotomie voulue sans authorer un seul doc : petit magasin (rayon seul) /
artisan (son catalogue) / grand magasin (+ le sur-mesure), la fusion de catégories élargissant
déjà mécaniquement le catalogue ET les matières acceptées d'une grande maison.

Logique pure : accès DB injectés (`get_doc_fn`), on MUTE le personnage sans jamais le sauver —
l'appelant persiste. Tunables lus VIA le module `character_stats` (réglables à chaud).

⚠️ **Le statut d'une commande est DÉRIVÉ de l'horloge, jamais avancé par un tick** : aucun tick
de fond n'existe dans ce jeu (CLAUDE.md §5). `statut()` lit `pret_at` ; seuls les gestes du
joueur (passer, retirer, annuler) écrivent.

⚠️ **La commande vit sur le doc PERSONNAGE.** Prélever les matières et inscrire la commande se
font dans la même mutation, donc dans le même `save_doc` : la double consommation et la double
fabrication sont impossibles par construction, sans transaction inter-documents (§8/§18 du
cahier des charges).
"""

import time
import uuid

from models import character_stats
from utils import fabrication, marche
from utils.characters import (
	item_ref_id, item_sous_categorie, poids_bounds, resolve_item_ref,
)

TAG_SUR_MESURE = "sur_mesure"

# Préfixe des tags qui ouvrent une matière à une FAMILLE de pièces : `fabrication_arme`,
# `fabrication_armure`, `fabrication_bijou`… La donnée dit elle-même ce à quoi elle sert.
TAG_FABRICATION_PREFIXE = "fabrication_"

# États persistés sur la commande. Les états de DÉROULEMENT (`en_fabrication`, `terminee`,
# `expiree`) ne sont jamais écrits : ils se lisent sur l'horloge.
ETAT_ATTENTE_MATERIAUX = "en_attente_materiaux"
ETAT_PAYEE = "payee"
ETAT_LIVREE = "livree"
ETAT_ANNULEE = "annulee"
ETAT_IMPOSSIBLE = "impossible"

ETAT_EN_FABRICATION = "en_fabrication"
ETAT_TERMINEE = "terminee"
ETAT_EXPIREE = "expiree"

# Ce qui ne bouge plus tout seul : rendu tel quel par `statut()`.
ETATS_FIGES = frozenset({ETAT_ATTENTE_MATERIAUX, ETAT_LIVREE, ETAT_ANNULEE, ETAT_IMPOSSIBLE})
# Ce que `purger_commandes` balaie. ⚠️ `expiree` n'en est PAS : une commande perdue doit rester
# visible au joueur qui revient trop tard, sinon elle s'évapore sans qu'il sache pourquoi. Il
# l'écarte lui-même (`oublier`).
ETATS_PURGEABLES = frozenset({ETAT_LIVREE, ETAT_ANNULEE, ETAT_IMPOSSIBLE})


def now_epoch() -> int:
	"""Epoch entier — miroir de `scriptorium.now_epoch`. Local pour ne pas tirer `utils.quetes`
	derrière ce module."""
	return int(time.time())


# ── Les deux capacités ──────────────────────────────────────────────────────────

def lieu_prend_commandes(lieu_doc: dict, get_doc_fn=None) -> bool:
	"""Cet atelier accepte-t-il une commande ? DÉRIVÉ : son catalogue ÉPURÉ n'est pas vide.

	⚠️ Pas de prédicat « categorie OU tag » ici, contrairement aux six capacités de
	`utils/capacites.py` : savoir refaire ce qu'on fabrique déjà n'est pas une capacité qu'on
	accorde, c'est une conséquence. Un comptoir sans recettes (façade de guilde, échoppe de
	revente) rend naturellement False.

	⚠️ « Son catalogue n'est pas vide » et non « il a des recettes » : une boucherie en a
	seize et ne produit que des matières (viande, foie, os, tendons). Quinze boutiques du
	dump sont dans ce cas — onze boucheries et quatre tanneries — et leur section Commande
	n'aurait rien à montrer."""
	return bool(catalogue_commandable(lieu_doc, get_doc_fn))


def lieu_fabrique_sur_mesure(lieu_doc: dict) -> bool:
	"""Ce lieu sait-il inventer une variante ? Même idiome que les cinq prédicats historiques
	(`auberge.lieu_est_taverne`…) : `categorie` accordante **OU** tag — le OU évite toute
	migration et ouvre la capacité à n'importe quel lieu par la donnée seule.

	⚠️ Les catégories accordantes sont relues depuis `LIEU_CATEGORIES_FUSION` et non recopiées :
	ouvrir une grande maison de plus ne doit pas obliger à penser à deux endroits (même
	dérivation que `CHA_MARCHAND_PAR_CATEGORIE`)."""
	if not lieu_doc:
		return False
	return (lieu_doc.get("categorie") in character_stats.LIEU_CATEGORIES_FUSION
			or TAG_SUR_MESURE in (lieu_doc.get("tags") or []))


# ── Ce que l'atelier sait faire ─────────────────────────────────────────────────

def catalogue_commandable(lieu_doc: dict, get_doc_fn=None) -> list:
	"""Item_ids que ce lieu sait produire **et qu'on peut lui commander**, triés. Fusion de
	catégories et portée de terroir comprises (`marche.produits_lieu` prend le doc).

	⚠️ Les MATIÈRES et DEMI-PRODUITS sont écartés (`marche.item_commandable`) : l'Arsenal de
	Lutèce proposait « Hampe », « Cuir » et « Acier plissé » à côté de ses 133 armes et
	armures. Un demi-produit s'achète au rayon, il ne se commande pas à façon — sauf
	dérogation explicite par le tag `commandable` sur son doc item.

	`get_doc_fn` optionnel : sans lui, `marche.item_commandable` lit la base lui-même
	(mémoïsé). Les appelants qui tiennent déjà `get_doc` le passent."""
	if not lieu_doc:
		return []
	produits = marche.produits_lieu(lieu_doc)
	return sorted(i for i in produits
				  if marche.item_commandable(i, get_doc_fn(i) if get_doc_fn else None))


def recette_pour(lieu_doc: dict, item_id: str):
	"""La recette de CE lieu qui produit `item_id`, ou None. La première trouvée fait foi :
	`recettes_lieu` sert la catégorie propre en tête, donc la recette maison prime sur celle
	d'un métier réuni."""
	if not item_id:
		return None
	for r in marche.recettes_lieu(lieu_doc):
		if marche.objet_final_item_id(r.get("objet_final", "")) == item_id:
			return r
	return None


def fabrication_valide(item_doc: dict) -> bool:
	"""Le bloc `fabrication` de ce doc apporte-t-il quelque chose ? Délégué à
	`fabrication.apporte`, source unique de ce qu'est un bloc bien formé : un bloc absent, mal
	formé ou vide ne fait pas une matière de sur-mesure. Une matière sans apport ne ferait que
	renchérir la pièce sans rien y changer."""
	return fabrication.apporte(item_doc)


def tags_fabrication(base_doc: dict) -> set:
	"""Les tags qui ouvrent une matière à CETTE pièce : `fabrication_<categorie>` et
	`fabrication_<sous_categorie>` de l'objet à façonner (`arme`, `armure`, `bijou`…)."""
	if not base_doc:
		return set()
	cles = (base_doc.get("categorie"), item_sous_categorie(base_doc))
	return {TAG_FABRICATION_PREFIXE + str(c) for c in cles if c}


def matiere_acceptee(lieu_doc: dict, item_doc: dict, base_doc: dict | None = None) -> bool:
	"""Cette matière peut-elle entrer dans la pièce ? DEUX portes, et il suffit d'une :

	- le **tour de main de la maison** — même critère que ce qu'elle achète au joueur
	  (`besoins_lieu` : id d'item ou sous-catégorie). Un cirier refuse donc le métal, un
	  armurier refuse la cire — §10 du cahier des charges ;
	- le **tag de la matière** — `fabrication_<categorie>` / `fabrication_<sous_categorie>`
	  de la PIÈCE à façonner : la matière désigne elle-même la famille d'objets où elle
	  s'emploie, sans passer par les recettes du lieu (une maison qui ne travaille pas la
	  gemme peut la sertir sur une épée si la gemme porte `fabrication_arme`).

	⚠️ Sans `base_doc`, cette seconde porte reste FERMÉE : on ne sait pas ce qu'on façonne,
	donc aucune famille ne s'applique. Les appelants du sur-mesure passent la pièce.

	Dans les deux cas le bloc `fabrication` doit être renseigné (`fabrication_valide`)."""
	if not fabrication_valide(item_doc):
		return False
	item_id = item_doc.get("item") or item_doc.get("_id")
	if any(correspond(item_id, item_doc, cle) for cle in marche.besoins_lieu(lieu_doc)):
		return True
	return bool(tags_fabrication(base_doc) & set(item_doc.get("tags") or []))


def matieres_disponibles(lieu_doc: dict, base_doc: dict, porteurs, get_doc_fn) -> list:
	"""Ce qu'on peut mettre dans CETTE pièce ICI : `[{"item_id", "qty", "qty_sac"}, …]` trié
	par id. TROIS provenances, une seule règle d'admission (`matiere_acceptee`) :

	- le **rayon** de l'artisan (`stock_vente`), que le joueur paiera au comptoir ;
	- les **sacs de l'expédition**, que `sourcer` prélève EN PREMIER, donc sans rien facturer ;
	- le **catalogue du monde** (`marche.matieres_fabrication`), pour tout ce que la maison
	  accepterait sans l'avoir : `qty == qty_sac == 0` dit « ni ici ni sur vous ».

	Les deux dernières ne sont pas du confort. Sans les sacs, le tag `fabrication_<famille>` ne
	servirait qu'à filtrer la vitrine : une gemme achetée au joaillier d'en face ne pourrait
	jamais être sertie, puisque l'armurier n'en vend pas. Sans le catalogue, le joueur ne
	saurait même pas que la pièce peut la recevoir — il ne peut pas deviner ce qu'aucune des
	deux listes ne montre. Choisie sans être là, la matière part en `manquantes` : la commande
	naît `en_attente_materiaux`, rien n'est prélevé ni débité, et « Relancer » la reprend au
	retour du joueur (§7 cas C).

	⚠️ Les sacs sont balayés exactement comme `emplacements_fournis` les balaie (les
	références de `inventaire`, porteurs compris) : proposer ce que la dépense ne saurait pas
	prendre afficherait une matière aussitôt portée `manquantes`.

	⚠️ Une matière vue plusieurs fois ne fait qu'UNE ligne — c'est le même objet, et le sac
	passe d'abord. Le rayon reste compté à part pour que le client sache s'il la fournit.

	`get_doc_fn` n'est appelé qu'une fois par id : `matiere_acceptee` relit les besoins du
	lieu, et un sac de trente objets ne doit pas le faire trente fois."""
	lignes: dict[str, dict] = {}
	admises: dict[str, bool] = {}

	def _admise(item_id: str) -> bool:
		if item_id not in admises:
			doc = get_doc_fn(item_id)
			admises[item_id] = bool(doc) and matiere_acceptee(lieu_doc, doc, base_doc)
		return admises[item_id]

	def _ligne(item_id: str) -> dict:
		return lignes.setdefault(item_id, {"item_id": item_id, "qty": 0, "qty_sac": 0})

	for entree in (lieu_doc or {}).get("stock_vente", []) or []:
		item_id = entree.get("item_id")
		qty = int(entree.get("qty", 0) or 0)
		if item_id and qty > 0 and _admise(item_id):
			_ligne(item_id)["qty"] += qty

	for porteur in (porteurs or []):
		for ref in (porteur or {}).get("inventaire", []) or []:
			item_id = item_ref_id(ref)
			if item_id and _admise(item_id):
				_ligne(item_id)["qty_sac"] += 1

	# Le catalogue en dernier : il n'apporte aucune quantité, seulement l'existence de la
	# ligne. Les deux passes précédentes ont déjà posé leurs compteurs, `_ligne` ne les
	# écrase pas.
	for item_id in marche.matieres_fabrication():
		if _admise(item_id):
			_ligne(item_id)

	return [lignes[cle] for cle in sorted(lignes)]


# ── Approvisionnement des matières (§7 : les trois cas) ─────────────────────────

def correspond(item_id: str, item_doc: dict, cle: str) -> bool:
	"""Cet objet répond-il à une clé de recette ? SOURCE UNIQUE des trois appariements du
	module (sac du joueur, rayon de l'artisan, matière acceptée).

	Une clé de recette est polymorphe (`marche.recette_matieres`) : un id d'item OU une
	sous-catégorie. Les deux premiers tests couvrent ces cas.

	⚠️ Le TROISIÈME n'est pas du zèle. Le marché résout une clé sous-catégorie en
	`item:<clé>` (`marche.matiere_item_id`, overrides compris) sans jamais relire la
	`sous_categorie` du doc obtenu — et les deux divergent en base : `item:argent` porte
	`sous_categorie: "metaux_precieux"` alors que les 17 recettes d'armurerie le désignent
	par la clé `argent`. Sans cette ligne, un joueur portant un lingot d'argent ne pourrait
	pas le fournir, et aucun artisan n'accepterait l'argent en sur-mesure."""
	if not item_id:
		return False
	return (item_id == cle
			or item_sous_categorie(item_doc or {}) == cle
			or marche.matiere_item_id(cle) == item_id)


def _ref_satisfait(ref, cle: str, get_doc_fn) -> bool:
	"""Une référence d'inventaire répond-elle à une clé de recette ?"""
	item_id = item_ref_id(ref)
	if not item_id:
		return False
	if item_id == cle or marche.matiere_item_id(cle) == item_id:
		return True   # sans lecture DB quand l'id suffit
	return correspond(item_id, get_doc_fn(item_id), cle)


def emplacements_fournis(besoins, porteurs, get_doc_fn, retenus=None) -> tuple:
	"""`(trouves, manquants)` où `trouves` = `[{"cle", "porteur", "index", "item_id"}, …]`.

	Balaie les sacs de TOUTE l'expédition (`recrutement.porteurs_effectifs` côté appelant) :
	une bête de somme qui porte le lingot doit pouvoir le fournir sans transfert préalable,
	exactement comme elle peut le vendre.

	⚠️ Repérage SEUL, aucun retrait : c'est le contrôle, `retirer_fournitures` est la dépense.
	Les deux doivent voir la même chose, sinon la commande serait acceptée puis rien ne serait
	prélevé (même précédent qu'`auberge._emplacement_fourniture`).

	⚠️ Un emplacement déjà retenu ne peut pas l'être deux fois : sans ce suivi, une recette
	demandant deux lingots serait satisfaite par un seul, compté deux fois.

	⚠️ `retenus` est PARTAGEABLE entre deux passes (matières de la recette, puis matières sur
	mesure) : sans ce partage, le même lingot satisferait les deux, et le joueur se le verrait
	créditer d'un côté pendant qu'il le fournit gratuitement de l'autre."""
	retenus = retenus if retenus is not None else set()   # (id du porteur, index)
	trouves, manquants = [], []
	for cle, quantite in besoins:
		reste = int(quantite or 1)
		for porteur in porteurs:
			pid = (porteur or {}).get("_id") or ""
			for index, ref in enumerate((porteur or {}).get("inventaire", []) or []):
				if reste <= 0:
					break
				if (pid, index) in retenus or not _ref_satisfait(ref, cle, get_doc_fn):
					continue
				retenus.add((pid, index))
				trouves.append({"cle": cle, "porteur": porteur, "index": index,
								"item_id": item_ref_id(ref)})
				reste -= 1
			if reste <= 0:
				break
		if reste > 0:
			manquants.append({"cle": cle, "quantite": reste})
	return trouves, manquants


def retirer_fournitures(trouves) -> list:
	"""Retire de leur porteur les emplacements repérés — rend les références retirées.

	⚠️ TOUT OU RIEN par construction : on ne l'appelle qu'après `emplacements_fournis` sans
	manquant. ⚠️ Les index SE DÉCALENT à chaque retrait : on supprime du plus grand au plus
	petit, par porteur (même piège qu'`auberge.retirer_fournitures`)."""
	par_porteur: dict[int, list] = {}
	for t in trouves:
		par_porteur.setdefault(id(t["porteur"]), []).append(t)
	retirees = []
	for entrees in par_porteur.values():
		porteur = entrees[0]["porteur"]
		inventaire = list(porteur.get("inventaire", []) or [])
		for t in sorted(entrees, key=lambda e: e["index"], reverse=True):
			retirees.append(inventaire.pop(t["index"]))
		porteur["inventaire"] = inventaire
	return retirees


def achetable_sur_place(lieu_doc: dict, cle: str, get_doc_fn):
	"""`(item_id, qty_en_rayon)` de la matière que l'artisan peut VENDRE pour cette clé, ou
	`(None, 0)`.

	⚠️ On ne lit QUE `stock_vente`, jamais `stock_matieres`. Vendre depuis la réserve de
	l'atelier ferait passer une matière de la réserve au comptoir — ce que rien ne fait jamais
	dans le jeu — et casserait l'invariante « la vitrine est regarnie jusqu'au `stock_cible`
	et jamais au-dessus » (épinglée par `tests/test_appro_comptoir.py`)."""
	for entree in (lieu_doc or {}).get("stock_vente", []) or []:
		item_id = entree.get("item_id")
		qty = int(entree.get("qty", 0) or 0)
		if not item_id or qty <= 0:
			continue
		if item_id == cle or marche.matiere_item_id(cle) == item_id:
			return item_id, qty   # sans lecture DB quand l'id suffit
		if correspond(item_id, get_doc_fn(item_id), cle):
			return item_id, qty
	return None, 0


def dispo_atelier(lieu_doc: dict, cle: str, get_doc_fn) -> tuple:
	"""`(qty_reserve, item_id_en_rayon, qty_en_rayon)` — ce que l'artisan a sous la main pour
	honorer une commande de son CATALOGUE.

	⚠️ Ici, et seulement ici, on lit `stock_matieres` : la réserve de l'atelier est exactement
	ce dans quoi `marche._executer_production_batch` puise pour cuire une recette. L'artisan ne
	VEND pas sa réserve (ce serait l'interdit ci-dessus), il la CONSOMME pour fabriquer la
	pièce que le client paie au prix de détail — le geste même de son métier.

	Sans cette lecture, 65 % du catalogue du monde naîtrait `en_attente_materiaux` : les
	intermédiaires (cuir, tendons, os, graisse…) vivent dans la réserve, pas en vitrine.

	⚠️ La clé d'une recette EST la clé de bucket de `stock_matieres` (`cle_matiere_lieu` rend
	l'id d'item quand une recette du lieu le nomme, sinon la sous-catégorie) : on indexe donc
	directement, sans re-dériver."""
	reserve = int(((lieu_doc or {}).get("stock_matieres") or {}).get(cle, 0) or 0)
	item_id, en_rayon = achetable_sur_place(lieu_doc, cle, get_doc_fn)
	return reserve, item_id, en_rayon


def sourcer(besoins, porteurs, lieu_doc, get_doc_fn, prix_fn=None, retenus=None,
			atelier=False) -> dict:
	"""Les trois cas du §7 : ce que le joueur fournit, ce que l'artisan met, ce qui manque.

	DEUX modes, parce que les deux familles de matières ne se facturent pas pareil :

	- **`atelier=True`** (ingrédients de la RECETTE) : ce que le joueur n'apporte pas,
	  l'artisan le prend dans sa réserve puis dans son rayon, **sans rien facturer** — leur
	  coût est déjà compris dans le prix de la pièce (`commande.devis`). Rendu dans `atelier`.
	- **`atelier=False`** (matières SUR MESURE) : ce que le joueur n'apporte pas, il l'achète
	  au comptoir au prix du marché. Rendu dans `achetees`, avec son coût.

	`prix_fn(item_id, item_doc, qty_en_rayon)` rend le prix unitaire en cuivre — injecté pour
	que ce module reste pur et que le prix reste celui du marché (`marche.prix_marche`, sens
	achat), jamais une deuxième formule parallèle.

	Une clé manquante ne fait pas échouer : la commande naîtra `en_attente_materiaux`.

	`retenus` : voir `emplacements_fournis` — à passer d'une passe à l'autre."""
	trouves, manquants = emplacements_fournis(besoins, porteurs, get_doc_fn, retenus)
	achetees, fournies_atelier, introuvables = [], [], []
	for manque in manquants:
		cle, reste = manque["cle"], int(manque["quantite"])
		if atelier:
			reserve, item_id, en_rayon = dispo_atelier(lieu_doc, cle, get_doc_fn)
			if reserve + en_rayon < reste:
				introuvables.append({"cle": cle, "quantite": reste})
				continue
			pris_reserve = min(reserve, reste)
			doc = get_doc_fn(item_id) if item_id else None
			fournies_atelier.append({
				"cle": cle, "item_id": item_id, "quantite": reste,
				"reserve": pris_reserve, "rayon": reste - pris_reserve,
				"nom": (doc or {}).get("nom") or item_id or cle,
			})
			continue
		item_id, en_rayon = achetable_sur_place(lieu_doc, cle, get_doc_fn)
		if not item_id or en_rayon < reste:
			introuvables.append({"cle": cle, "quantite": reste})
			continue
		doc = get_doc_fn(item_id) or {}
		unitaire = int(prix_fn(item_id, doc, en_rayon)) if prix_fn else 0
		achetees.append({"cle": cle, "item_id": item_id, "quantite": reste,
						 "prix_unitaire": unitaire, "prix": unitaire * reste,
						 "nom": doc.get("nom") or item_id})
	return {
		"fournies": trouves,
		"atelier": fournies_atelier,
		"achetees": achetees,
		"manquantes": introuvables,
		"cout_matieres": sum(a["prix"] for a in achetees),
	}


def retirer_du_rayon(lieu_doc: dict, achetees) -> None:
	"""Décrémente `stock_vente` des matières achetées à l'artisan — même geste que `buy_item`,
	lignes vidées purgées. Mute `lieu_doc` sans le sauver (commodité monde, best-effort)."""
	stock = (lieu_doc or {}).get("stock_vente", []) or []
	for achat in achetees:
		reste = int(achat["quantite"])
		for entree in stock:
			if entree.get("item_id") == achat["item_id"]:
				entree["qty"] = int(entree.get("qty", 0) or 0) - reste
				break
	lieu_doc["stock_vente"] = [e for e in stock if int(e.get("qty", 0) or 0) > 0]


def consommer_atelier(lieu_doc: dict, fournies_atelier) -> None:
	"""L'artisan consomme ce qu'il a mis de lui-même : réserve d'abord, rayon ensuite —
	exactement l'ordre de `marche._executer_production_batch._consommer`. Mute `lieu_doc` sans
	le sauver (commodité monde, best-effort comme le reste du stock)."""
	reserve = (lieu_doc or {}).setdefault("stock_matieres", {})
	for part in fournies_atelier:
		if part.get("reserve"):
			restant = int(reserve.get(part["cle"], 0) or 0) - int(part["reserve"])
			if restant > 0:
				reserve[part["cle"]] = restant
			else:
				reserve.pop(part["cle"], None)
		if part.get("rayon") and part.get("item_id"):
			retirer_du_rayon(lieu_doc, [{"item_id": part["item_id"], "quantite": part["rayon"]}])


# ── Prix (§9 : le détail est conservé) ──────────────────────────────────────────

def devis(prix_base: int, cout_matieres: int = 0, credit_matieres: int = 0,
		  matieres_distinctes: int = 0) -> dict:
	"""Détail du prix d'une commande, conservé tel quel sur la commande.

	    total = prix de base − matières apportées + matières sur mesure achetées
	            + façon + supplément de complexité

	`prix_base` est calculé par l'appelant avec `marche.prix_marche(…, "achat", stock=0, …)` :
	le prix du marché pour un objet dont il ne reste rien en rayon, relation et marchandage
	compris. `stock=0` n'est pas un raccourci — c'est la situation même : l'objet n'est pas
	en vitrine, c'est pour cela qu'on le commande.

	⚠️ **Les ingrédients de la recette sont DÉJÀ dans `prix_base`** — `cout_production_cuivre`
	les propage (× `MARGE_TRANSFO` par étape). Les refacturer rendrait la commande plus chère
	que le même objet pris en rayon, et personne ne commanderait jamais rien. D'où les deux
	traitements distincts :
	- **matière de la recette apportée par le joueur** → `credit_matieres`, une REMISE : il
	  fournit ce que l'artisan aurait payé ;
	- **matière SUR MESURE** → `cout_matieres`, un SUPPLÉMENT : elle n'est dans le prix
	  d'aucun objet de base, puisque aucune recette ne la cite.

	⚠️ La remise est plafonnée à `prix_base` : sans ce plafond, apporter plus de matière que
	la pièce n'en vaut ferait tomber le total au plancher — acheter du fer au comptoir puis le
	rapporter comme « matière sur mesure » suffirait à obtenir l'épée pour une pièce de cuivre.

	La façon est ce que l'artisan vend en propre : elle se paie même quand le client apporte
	tout. Le supplément ne court qu'à partir de la DEUXIÈME matière — une pièce simple n'a pas
	à payer un surcoût de complexité."""
	prix_base = max(0, int(prix_base or 0))
	cout_matieres = max(0, int(cout_matieres or 0))
	credit = min(prix_base, max(0, int(credit_matieres or 0)))
	facon = int(round(prix_base * float(character_stats.COMMANDE_FACON_PART)))
	sup = int(round(prix_base * float(character_stats.COMMANDE_COMPLEXITE_PART)
					* max(0, int(matieres_distinctes or 0) - 1)))
	return {
		"prix_base": prix_base,
		"credit_matieres": credit,
		"cout_matieres": cout_matieres,
		"cout_fabrication": facon,
		"supplement_complexite": sup,
		"total": max(1, prix_base - credit + cout_matieres + facon + sup),
	}


# ── Cycle de vie ────────────────────────────────────────────────────────────────

def nouvelle_commande(lieu_doc: dict, item_id: str, detail: dict, now: int | None = None,
					  base_item: str = "", matieres=None, fournies=None,
					  achetees=None, manquantes=None, poids: float = 0.0) -> dict:
	"""Enregistrement d'une commande, prêt à être poussé dans `character["commandes"]`.

	Naît `payee` si tout est réuni, `en_attente_materiaux` sinon — jamais en échec (§7 cas C).
	`pret_at` n'a de sens que pour une commande payée ; il est posé dès maintenant pour que le
	statut reste purement dérivable de l'horloge, sans second champ à tenir à jour."""
	instant = now_epoch() if now is None else int(now)
	complet = not (manquantes or [])
	return {
		"id": uuid.uuid4().hex,
		"lieu": (lieu_doc or {}).get("_id", ""),
		"lieu_categorie": (lieu_doc or {}).get("categorie", ""),
		"item": item_id,
		"base_item": base_item or "",
		"matieres": list(matieres or []),
		"statut": ETAT_PAYEE if complet else ETAT_ATTENTE_MATERIAUX,
		"fournies": list(fournies or []),
		"achetees": list(achetees or []),
		"manquantes": list(manquantes or []),
		"devis": dict(detail or {}),
		"paye": int((detail or {}).get("total", 0)) if complet else 0,
		"poids": round(float(poids or 0), 2),
		"cree_at": instant,
		"pret_at": instant + int(character_stats.COMMANDE_DELAI_SECONDES),
	}


def statut(commande: dict, now: int | None = None) -> str:
	"""Statut EFFECTIF d'une commande — dérivé, jamais stocké.

	Un état figé (attente de matériaux, livrée, annulée, impossible) est rendu tel quel. Une
	commande payée traverse `en_fabrication` → `terminee` → `expiree` à la seule horloge :
	c'est ce qui permet de n'avoir aucun tick de fond, et de ne rien écrire tant que le joueur
	n'agit pas."""
	brut = (commande or {}).get("statut") or ETAT_ATTENTE_MATERIAUX
	if brut in ETATS_FIGES:
		return brut
	instant = now_epoch() if now is None else int(now)
	pret = int((commande or {}).get("pret_at", 0) or 0)
	if instant < pret:
		return ETAT_EN_FABRICATION
	if instant >= pret + int(character_stats.COMMANDE_PEREMPTION_SECONDES):
		return ETAT_EXPIREE
	return ETAT_TERMINEE


def retirable(commande: dict, lieu_id: str, now: int | None = None) -> bool:
	"""Prête ET on est bien chez l'artisan qui l'a fabriquée."""
	return (statut(commande, now) == ETAT_TERMINEE
			and (commande or {}).get("lieu") == lieu_id)


def trouver(character: dict, commande_id: str):
	"""La commande d'id donné, ou None. Adressage par id et non par index : la liste est
	purgée entre deux gestes du joueur."""
	if not commande_id:
		return None
	return next((c for c in (character or {}).get("commandes", []) or []
				 if c.get("id") == commande_id), None)


def ref_livree(commande: dict) -> dict:
	"""Référence d'inventaire de l'exemplaire retiré — l'exemplaire est une RÉFÉRENCE enrichie,
	pas un document (même idiome que `item_ref_lieu` pour la carte de guilde et que le
	manuscrit du scriptorium). `resolve_item_ref` sait déjà l'afficher sans toucher au doc.

	⚠️ Le poids tiré à la commande voyage avec : la définition d'une variante peut porter un
	poids `[min, max]` comme n'importe quel item."""
	ref = {
		"item": commande.get("item"),
		"fabrique_par": commande.get("lieu"),
		"commande_at": int(commande.get("cree_at", 0) or 0),
	}
	poids = float(commande.get("poids", 0) or 0)
	if poids > 0:
		ref["poids"] = poids
	return ref


def marquer(commande: dict, etat: str) -> None:
	"""Passe une commande dans un état figé. Mute sans sauver."""
	commande["statut"] = etat


def purger_commandes(character: dict, now: int | None = None) -> int:
	"""Balaie les commandes soldées — rend le nombre retiré. Péremption PARESSEUSE : appelée
	au prochain geste du joueur, jamais par un tick.

	⚠️ Une commande `expiree` n'est PAS balayée : le joueur qui revient trop tard doit voir ce
	qu'il a perdu, pas trouver une liste vide. Il l'écarte lui-même."""
	commandes = (character or {}).get("commandes") or []
	restantes = [c for c in commandes if statut(c, now) not in ETATS_PURGEABLES]
	retirees = len(commandes) - len(restantes)
	if retirees:
		character["commandes"] = restantes
	return retirees


# ── Vue client ──────────────────────────────────────────────────────────────────

def vue(commande: dict, get_doc_fn, now: int | None = None) -> dict:
	"""Une ligne de la liste des commandes, prête pour le client. Le nom et l'icône sont
	résolus ici : le client ne reconstruit jamais un état (CLAUDE.md §10)."""
	instant = now_epoch() if now is None else int(now)
	item = resolve_item_ref(commande.get("item")) if commande.get("item") else None
	etat = statut(commande, instant)
	return {
		"id": commande.get("id"),
		"lieu": commande.get("lieu"),
		"item_id": commande.get("item"),
		"nom": (item or {}).get("nom") or commande.get("item"),
		"icon": (item or {}).get("icon") or "🛠️",
		"statut": etat,
		"sur_mesure": bool(commande.get("base_item")),
		"manquantes": list(commande.get("manquantes") or []),
		"devis": dict(commande.get("devis") or {}),
		"paye": int(commande.get("paye", 0) or 0),
		"poids": round(float(commande.get("poids", 0) or 0), 2),
		"pret_dans": max(0, int(commande.get("pret_at", 0) or 0) - instant),
		"expire_dans": max(0, int(commande.get("pret_at", 0) or 0)
						   + int(character_stats.COMMANDE_PEREMPTION_SECONDES) - instant),
		"retirable": etat == ETAT_TERMINEE,
	}


def poids_attendu(item_doc: dict) -> float:
	"""Poids de l'exemplaire à livrer — le MINIMUM du doc, comme tout objet acheté
	(`buy_item` pose une référence nue, dont `item_ref_weight` tire le min). Un doc à poids
	`[min, max]` ne tire donc pas au hasard ici : une pièce commandée est une pièce choisie."""
	return poids_bounds(item_doc or {})[0]
