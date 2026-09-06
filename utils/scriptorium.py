# utils/scriptorium.py
# Le scriptorium : DEUX mécaniques distinctes.
#
# 1. L'ÉCRIT PERSONNEL — un geste du JOUEUR, symétrique du tableau d'annonce d'auberge
#    (utils/auberge.py) : même règle d'écriture (papier+encre consommés, plume outil, cf.
#    Convention « une seule règle d'écriture dans tout le jeu »), mais le résultat est un
#    OBJET TRANSPORTABLE (le contenu vit sur la référence d'inventaire, comme `item_ref_lieu`
#    pour la carte de guilde) plutôt qu'un message public.
#
# 2. LES LIVRES DE CONTENU (détail complet d'un sort, une recette, un bout de carte) — PAS un
#    geste du joueur : fabriqués par le scriptorium LUI-MÊME, via son tick d'atelier existant
#    (utils/marche.py::tick_atelier). Aucun doc `recette:*` n'est créé pour cela : les recettes
#    sont indexées par `lieu_categorie` SEUL (marche.lieu_recettes), donc un doc persisté
#    s'appliquerait à TOUS les scriptoriums du jeu, y compris ceux d'une autre cité qui n'ont
#    rien à voir avec le sujet documenté. La recette est donc construite EN MÉMOIRE, à chaque
#    tick, scopée au `lieu_parent` du lieu qui tick — jamais persistée.
#
# Logique pure : accès DB injectés (`find_docs_fn`/`get_doc_fn`/`save_doc_fn`), on MUTE/CRÉE
# sans jamais présumer d'un appelant précis. World-vars lues VIA le module `character_stats`.

import random
import time

from models import character_stats
from utils import auberge
from utils import marche
from utils.characters import lieu_label

ITEM_LIVRE_ECRIT_ID = "item:livre_ecrit"
SOUS_CATEGORIE_LIVRE_ECRIT = "livre_ecrit"

# Préfixes des items générés par la production automatique (point 2). ⚠️ Sous-catégories
# DISTINCTES de "grimoire" : ces livres n'enseignent rien, `sorts.est_grimoire`/
# `sorts.grimoire_pour` ne doivent jamais les voir.
PREFIXE_LIVRE_SORT = "livre_sort_"
PREFIXE_LIVRE_RECETTE = "livre_recette_"
PREFIXE_LIVRE_CARTE = "livre_carte_"


def now_epoch() -> int:
	"""Epoch entier — miroir de `auberge.now_epoch`. Local pour ne pas tirer `utils.quetes`
	(la source unique du jeu) derrière ce module."""
	return int(time.time())


def lieu_est_scriptorium(lieu_doc: dict) -> bool:
	"""Un scriptorium = `categorie:"scriptorium"` OU tag `"scriptorium"`. Miroir exact de
	`auberge.lieu_est_taverne` / `montures.lieu_vend_montures` : le OU évite toute migration."""
	if not lieu_doc:
		return False
	return (lieu_doc.get("categorie") == "scriptorium"
			or "scriptorium" in (lieu_doc.get("tags") or []))


# ── Point 1 : l'écrit personnel ─────────────────────────────────────────────────

def nouveau_livre(auteur: dict, texte: str, now: int | None = None) -> dict:
	"""Référence d'inventaire d'un manuscrit personnel. Miroir de `auberge.nouveau_message` :
	`texte` est supposé DÉJÀ borné par l'appelant (c'est lui qui doit lever le 422 sur un
	texte vide)."""
	instant = now_epoch() if now is None else int(now)
	return {
		"item": ITEM_LIVRE_ECRIT_ID,
		"livre_mode": "libre",
		"texte": texte,
		"auteur_nom": auberge.nom_affichable(auteur),
		"cree_at": instant,
	}


def titre_livre(nom_generique: str, ref) -> str:
	"""« Manuscrit relié de Bran Osier » — mirroir de `characters.item_label`, sans lecture
	DB : l'auteur est dénormalisé sur la ref, comme `auteur_nom` sur un `message:*`."""
	auteur = (ref or {}).get("auteur_nom")
	return f"{nom_generique} de {auteur}" if auteur else nom_generique


# ── Point 2 : ce qui peut être documenté autour d'un lieu_parent ────────────────

def sorts_documentables(lieu_parent_id: str, find_docs_fn, get_doc_fn) -> list[str]:
	"""Sorts enseignés par un grimoire (sous_categorie=="grimoire") en stock_vente de
	N'IMPORTE QUEL lieu enfant de `lieu_parent_id` — pas limité aux scriptoriums, un sort peut
	être enseigné ailleurs. Union des champs `sorts`, dédoublonnée et triée (déterministe)."""
	if not lieu_parent_id or not find_docs_fn or not get_doc_fn:
		return []
	enfants = find_docs_fn({"type": "lieu", "lieu_parent": lieu_parent_id},
						   fields=["_id", "stock_vente"]) or []
	sorts: set = set()
	for lieu in enfants:
		for entree in (lieu.get("stock_vente") or []):
			item_id = entree.get("item_id")
			if not item_id:
				continue
			doc = get_doc_fn(item_id)
			if doc and doc.get("sous_categorie") == "grimoire":
				sorts.update(doc.get("sorts") or [])
	return sorted(sorts)


def recettes_documentables(lieu_parent_id: str, find_docs_fn) -> list[str]:
	"""Recettes RÉELLEMENT appliquées par un magasin du lieu_parent : `marche.recettes_lieu`
	de chaque lieu enfant, ids dédoublonnés.

	⚠️ Par LIEU et non par catégorie : une spécialité de terroir n'est documentable que là où
	elle se cuit, et `recettes_lieu` a besoin du doc (son `_id` et son `lieu_parent`) pour
	résoudre la portée — d'où les deux champs ajoutés à la projection."""
	if not lieu_parent_id or not find_docs_fn:
		return []
	enfants = find_docs_fn({"type": "lieu", "lieu_parent": lieu_parent_id},
						   fields=["_id", "categorie", "lieu_parent"]) or []
	recettes: set = set()
	vus: set = set()
	for enfant in enfants:
		if not enfant.get("categorie") or enfant.get("_id") in vus:
			continue
		vus.add(enfant.get("_id"))
		for r in marche.recettes_lieu(enfant):
			rid = r.get("_id")
			if rid:
				recettes.add(rid)
	return sorted(recettes)


def lieux_documentables(lieu_parent_id: str, find_docs_fn) -> list[dict]:
	"""Lieux enfants de `lieu_parent_id` ayant une porte DIRECTE dans sa grille —
	[{"id": lieu_id, "porte": (x, y)}, …]. Fail-soft sur un lieu imbriqué sans porte directe
	(comme `chasse.position_de_chasse`) : il n'a simplement rien à documenter en carte.
	Import PARESSEUX de `focalisation` : ce module tire `utils.quetes` derrière lui, inutile
	au tick d'un scriptorium qui ne documente ni sort ni recette."""
	if not lieu_parent_id or not find_docs_fn:
		return []
	from utils import focalisation
	enfants_ids = {
		e.get("_id") for e in
		(find_docs_fn({"type": "lieu", "lieu_parent": lieu_parent_id}, fields=["_id"]) or [])
		if e.get("_id")
	}
	graphe = focalisation.charger_graphe(find_docs_fn)
	out = []
	for arete in graphe.get(lieu_parent_id, []):
		voisin = arete.get("voisin")
		if voisin in enfants_ids:
			out.append({"id": voisin, "porte": arete.get("porte")})
	return out


# ── Fabrication (assurer l'existence de l'item, jamais le recréer) ──────────────

def _detail_sort(sujet: dict) -> str:
	"""Texte du « détail complet » d'un sort, à partir de son doc (déjà en main)."""
	lignes = []
	ecole = sujet.get("magie") or sujet.get("vocation")
	if ecole:
		lignes.append(f"École : {ecole}")
	if sujet.get("niveau") is not None:
		lignes.append(f"Niveau : {sujet.get('niveau')}")
	if sujet.get("cout_pm") is not None:
		lignes.append(f"Coût : {sujet.get('cout_pm')} PM")
	if sujet.get("cible"):
		lignes.append(f"Cible : {sujet.get('cible')}")
	if sujet.get("jet"):
		lignes.append(f"Jet : {sujet.get('jet')}")
	if sujet.get("portee") is not None:
		lignes.append(f"Portée : {sujet.get('portee')}")
	degats = (sujet.get("effets") or {}).get("degats")
	if degats:
		lignes.append(f"Dégâts : {degats}")
	corps = "\n".join(lignes)
	description = sujet.get("description") or ""
	return "\n\n".join(t for t in (description, corps) if t)


def _detail_recette(sujet: dict, get_doc_fn) -> str:
	"""Texte du détail d'une recette : matières premières → objet final."""
	entrees = marche.recette_matieres(sujet)
	parts = []
	for cle, qte in entrees:
		item = get_doc_fn(marche.matiere_item_id(cle)) if get_doc_fn else None
		nom = (item or {}).get("nom") or cle
		parts.append(f"{qte} × {nom}")
	final_id = marche.objet_final_item_id(sujet.get("objet_final", ""))
	final = get_doc_fn(final_id) if get_doc_fn else None
	nom_final = (final or {}).get("nom") or sujet.get("objet_final", "")
	qp = sujet.get("quantite_produite", 1)
	lieu_categorie = sujet.get("lieu_categorie") or "atelier"
	base = f"Recette d'atelier ({lieu_categorie}) : " + " + ".join(parts) + f" → {qp} × {nom_final}."
	return base


def _assurer_item_livre(item_id: str, kind: str, sujet_id: str, get_doc_fn, save_doc_fn,
						lieu_parent_doc: dict | None = None, porte=None) -> None:
	"""Miroir de `combat._ensure_loot_item` : si `item_id` n'existe pas déjà, construit et
	sauve son doc — contenu figé au moment de la création, jamais recalculé ensuite. Un item
	déjà existant n'est JAMAIS retouché (le contenu d'un livre déjà vendu ne bouge pas sous le
	joueur qui l'a acheté)."""
	if get_doc_fn(item_id) is not None:
		return
	if kind == "sort":
		sujet = get_doc_fn(sujet_id) or {}
		nom = sujet.get("nom") or sujet_id
		doc = {
			"_id": item_id, "type": "item",
			"nom": f"Traité : {nom}",
			"icon": "📘",
			"categorie": "livre", "sous_categorie": "livre_sort",
			"slots": [], "poids": 0.4,
			"description": _detail_sort(sujet) or f"Un traité détaillant le sort « {nom} ».",
		}
	elif kind == "recette":
		sujet = get_doc_fn(sujet_id) or {}
		# Un doc `recette:*` ne porte pas de `nom` : on préfère celui de l'objet FINAL
		# (résolu, cache-friendly car `item:` est dans _CACHEABLE_PREFIXES) à son slug brut.
		final = get_doc_fn(marche.objet_final_item_id(sujet.get("objet_final", "")))
		nom = (final or {}).get("nom") or sujet.get("objet_final") or sujet_id
		doc = {
			"_id": item_id, "type": "item",
			"nom": f"Recueil : {nom}",
			"icon": "📗",
			"categorie": "livre", "sous_categorie": "livre_recette",
			"slots": [], "poids": 0.4,
			"description": _detail_recette(sujet, get_doc_fn),
		}
	elif kind == "carte":
		voisin_doc = get_doc_fn(sujet_id) or {}
		lieu_nom = lieu_label(voisin_doc, sujet_id)
		ville_nom = lieu_label(lieu_parent_doc, (lieu_parent_doc or {}).get("_id", ""))
		doc = {
			"_id": item_id, "type": "item",
			"nom": f"Carte : {lieu_nom}",
			"icon": "🗺️",
			"categorie": "livre", "sous_categorie": "livre_carte",
			"slots": [], "poids": 0.3,
			"description": f"Un bout de carte situant {lieu_nom}, dans {ville_nom}.",
		}
		image, route = marche._lieu_image_route(lieu_parent_doc or {})
		dimensions = (lieu_parent_doc or {}).get("dimensions")
		if image and route and dimensions and porte:
			doc["carte"] = {
				"position": {"x": int(porte[0]), "y": int(porte[1])},
				"dimensions": dimensions,
				"image": image,
				"image_route": route,
				"lieu_nom": lieu_nom,
			}
	else:
		return
	save_doc_fn(doc)


def _recette_virtuelle(item_id: str) -> dict:
	"""Recette EN MÉMOIRE (jamais persistée) produisant `item_id` — coût en papier/encre
	délibérément non trivial (cf. `recettes_virtuelles`, § rareté)."""
	slug = item_id[len("item:"):] if item_id.startswith("item:") else item_id
	return {
		"objet_final": slug,
		"lieu_categorie": "scriptorium",
		"matieres_premieres": [
			{"item": "item:Papier", "quantite": int(character_stats.SCRIPTORIUM_LIVRE_PAPIER)},
			{"item": "item:Encre", "quantite": int(character_stats.SCRIPTORIUM_LIVRE_ENCRE)},
		],
		"quantite_produite": 1,
	}


def recettes_virtuelles(lieu_doc: dict, find_docs_fn, get_doc_fn, save_doc_fn) -> list[dict]:
	"""Recettes de production virtuelles pour CE scriptorium, scopées à son `lieu_parent`.

	⚠️ AU PLUS UN sujet par pool (sort / recette / carte) et par appel — jamais tout le
	catalogue documentable : exposer N sujets simultanés ferait dominer le tirage pondéré de
	`marche._executer_production_batch` (poids ∝ quantité de matière) face aux quelques
	recettes génériques du scriptorium (papier/encre/plume/pigment), et la production perdrait
	toute rareté. Le tirage se renouvelle à chaque appel : sur de nombreux ticks, différents
	sujets ont leur chance, sans jamais en exposer plus de trois à la fois."""
	lieu_parent_id = (lieu_doc or {}).get("lieu_parent")
	if not lieu_parent_id or not find_docs_fn or not get_doc_fn or not save_doc_fn:
		return []

	out: list[dict] = []

	sorts = sorts_documentables(lieu_parent_id, find_docs_fn, get_doc_fn)
	if sorts:
		sort_id = random.choice(sorts)
		slug = sort_id[len("sort:"):] if sort_id.startswith("sort:") else sort_id
		item_id = f"item:{PREFIXE_LIVRE_SORT}{slug}"
		_assurer_item_livre(item_id, "sort", sort_id, get_doc_fn, save_doc_fn)
		out.append(_recette_virtuelle(item_id))

	recettes = recettes_documentables(lieu_parent_id, find_docs_fn)
	if recettes:
		recette_id = random.choice(recettes)
		slug = recette_id[len("recette:"):] if recette_id.startswith("recette:") else recette_id
		item_id = f"item:{PREFIXE_LIVRE_RECETTE}{slug}"
		_assurer_item_livre(item_id, "recette", recette_id, get_doc_fn, save_doc_fn)
		out.append(_recette_virtuelle(item_id))

	lieux = lieux_documentables(lieu_parent_id, find_docs_fn)
	if lieux:
		choix = random.choice(lieux)
		lieu_id = choix.get("id", "")
		slug = lieu_id[len("lieu:"):] if lieu_id.startswith("lieu:") else lieu_id
		item_id = f"item:{PREFIXE_LIVRE_CARTE}{slug}"
		lieu_parent_doc = get_doc_fn(lieu_parent_id)
		_assurer_item_livre(item_id, "carte", lieu_id, get_doc_fn, save_doc_fn,
						   lieu_parent_doc=lieu_parent_doc, porte=choix.get("porte"))
		out.append(_recette_virtuelle(item_id))

	return out


def recettes_effectives(lieu_doc: dict, find_docs_fn, get_doc_fn, save_doc_fn) -> list[dict]:
	"""Recettes à passer à `marche.tick_atelier` pour CE lieu — chokepoint des 4 sites
	d'appel du tick (visite, achat, vente/rachat, nuit). Pour un lieu NON scriptorium,
	identique à `marche.recettes_lieu(lieu_doc)` (comportement inchangé, zéro coût de plus :
	aucun appel à `find_docs_fn`/`save_doc_fn`).

	⚠️ C'est ici que la PORTÉE GÉOGRAPHIQUE entre dans le tick : `recettes_lieu` connaît le
	doc, donc les spécialités de terroir suivent les quatre sites d'appel sans qu'aucun
	appelant change."""
	base = marche.recettes_lieu(lieu_doc)
	if not lieu_est_scriptorium(lieu_doc):
		return base
	return base + recettes_virtuelles(lieu_doc, find_docs_fn, get_doc_fn, save_doc_fn)
