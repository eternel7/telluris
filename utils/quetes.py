# utils/quetes.py
# Moteur de quêtes : génère les offres d'une guilde à partir de son lieu PARENT
# (espèces des `rencontres` → quêtes de chasse `kill` ; `ressources` du lieu + carcasses
# des espèces → quêtes de collecte `collect`), et fournit les helpers d'état joueur
# (progression, récompenses). Le doc `quete:*` est PARTAGÉ entre quêtes générées
# (`source:"genere"`) et authorées à la main (`source:"authoree"`) ; le générateur ne
# gère/complète que les générées, les authorées s'affichent au tableau aux côtés.
#
# Comme utils/marche.py : logique pure, ne sauvegarde jamais — SAUF `remplir_tableau`,
# qui persiste les offres nouvellement générées (création des docs au tableau). Les
# helpers d'état (progression/récompenses) mutent les docs en place ; l'endpoint persiste.

import random
import time
import uuid

from db.config import get_doc, find_docs, save_doc, delete_doc
from models import character_stats
from utils.characters import item_ref_id, grant_xp, credit_character, cuivre_to_purse, poids_bounds
from utils import bois, marche
# ⚠️ Acyclique, et déjà tiré transitivement (quetes → bois → expedition → recrutement) :
# `recrutement` n'importe que characters/consommables/montures, jamais quetes.
from utils import recrutement


def now_epoch() -> int:
	return int(time.time())


def _cached_getter(fn):
	"""Mémoïse `fn(doc_id)` (typiquement `get_doc`) dans un dict LOCAL À L'APPEL — jamais partagé
	entre requêtes (pas de staleness), juste évite de re-fetcher le même lieu/espèce/profil/zone
	plusieurs fois dans une même passe de génération (ex. `_candidats_chasse` relit les mêmes
	docs zone/profil à chaque espèce d'un même lieu)."""
	cache: dict = {}
	def get(doc_id):
		if doc_id not in cache:
			cache[doc_id] = fn(doc_id)
		return cache[doc_id]
	return get


def _cached_finder(fn):
	"""Frère de `_cached_getter` pour `find_docs` — mémo LOCAL À L'APPEL, jamais partagé.

	⚠️ `_cached_getter` ne couvrait que `get_doc`, et c'est par les `find_docs` que fuyait
	l'essentiel : `cibles_collect` appelle `bois.pieces_legeres` pour CHAQUE ressource
	coupable du lieu, et chacune refait UNE requête PAR TIER de `BOIS_A_COUPER` — six
	ressources × six tiers = 36 requêtes non indexées pour six résultats distincts."""
	cache: dict = {}
	def find(selector, fields=None):
		cle = (repr(sorted(selector.items())), repr(fields))
		if cle not in cache:
			cache[cle] = fn(selector, fields) if fields is not None else fn(selector)
		return cache[cle]
	return find


def _carcasse_item_id(espece_id: str) -> str | None:
	"""item:<sub_id> depuis 'espece:<sub_id>' (1-pour-1 avec les carcasses du bestiaire)."""
	if not espece_id or not espece_id.startswith("espece:"):
		return None
	return "item:" + espece_id[len("espece:"):]


# ── Lecture du lieu parent ───────────────────────────────────────────────────────

def especes_du_parent(parent_doc: dict) -> list:
	"""IDs d'espèces rencontrables dans le lieu parent (dédup, ordre stable)."""
	out = []
	for r in (parent_doc or {}).get("rencontres", []):
		eid = r.get("espece")
		if eid and eid not in out:
			out.append(eid)
	return out


def ressources_du_parent(parent_doc: dict) -> list:
	"""IDs d'items récoltables dans le lieu parent (attribut `ressources`)."""
	out = []
	for r in (parent_doc or {}).get("ressources", []):
		iid = r.get("ressource")
		if iid and iid not in out:
			out.append(iid)
	return out


def cibles_collect(parent_doc: dict, get_doc_fn=None, find_docs_fn=None) -> list:
	"""Items collectables : ressources du lieu PLUS carcasses des espèces rencontrables, bornés à
	`QUETE_COLLECT_POIDS_MAX` par objet. Un item bois coupable (ex. un arbre) n'est PAS réclamé tel
	quel mais remplacé par les pièces transportables (≤ limite) de la même essence.

	⚠️ `find_docs_fn` est le poste le plus cher de tout le tableau : `bois.pieces_legeres` fait
	UNE requête PAR TIER de `BOIS_A_COUPER`, et on l'appelle une fois par ressource coupable.
	L'appelant doit passer un finder MÉMOÏSÉ (`_cached_finder`) — six ressources d'une même
	essence redemandent sinon exactement les mêmes six listes."""
	get_doc_fn = get_doc_fn or get_doc
	find_docs_fn = find_docs_fn or find_docs
	limite = character_stats.QUETE_COLLECT_POIDS_MAX
	raw = list(ressources_du_parent(parent_doc))
	for eid in especes_du_parent(parent_doc):
		cid = _carcasse_item_id(eid)
		if cid:
			raw.append(cid)

	out = []
	for iid in raw:
		doc = get_doc_fn(iid)
		if not doc:
			continue
		# Bois coupable (arbre/tronc/gros rondin…) : on cible les pièces ≤ limite de l'essence.
		if bois.item_est_coupable(doc):
			for pid in bois.pieces_legeres(doc, find_docs_fn, limite):
				if pid not in out:
					out.append(pid)
			continue
		# Autres ressources / carcasses : gardées si l'objet reste transportable (≤ limite).
		if poids_bounds(doc)[1] <= limite and iid not in out:
			out.append(iid)
	return out


def niveau_representatif(parent_doc: dict, get_doc_fn=None) -> int:
	"""Niveau de profil « moyen » du lieu, pondéré par `profil_weights` (repli 1)."""
	get_doc_fn = get_doc_fn or get_doc
	weights = (parent_doc or {}).get("profil_weights") or {}
	total_w = 0.0
	acc = 0.0
	for pid, w in weights.items():
		try:
			w = float(w)
		except (TypeError, ValueError):
			continue
		if w <= 0:
			continue
		prof = get_doc_fn(pid)
		if not prof:
			continue
		acc += float(prof.get("niveau", 1)) * w
		total_w += w
	if total_w <= 0:
		return 1
	return max(1, round(acc / total_w))


# ── Noms d'affichage ─────────────────────────────────────────────────────────────

def _nom_espece(espece_id: str) -> str:
	doc = get_doc(espece_id)
	return (doc.get("nom") if doc else None) or (espece_id or "").split(":", 1)[-1]


def _nom_item(item_id: str) -> str:
	doc = get_doc(item_id)
	return (doc.get("nom") if doc else None) or (item_id or "").split(":", 1)[-1]


def _cible_nom(objectif: dict) -> str:
	t = objectif.get("type")
	cible = objectif.get("cible", "")
	if t in ("kill", "chasse"):
		return _nom_espece(cible)
	if t == "collect":
		return _nom_item(cible)
	if t in ("visite", "transport"):
		doc = get_doc(cible)
		return (doc.get("label") if doc else None) or (cible or "").split(":", 1)[-1]
	return cible


# ── XP / récompenses ─────────────────────────────────────────────────────────────

def _xp_unitaire(espece_doc: dict, niveau: int) -> int:
	"""XP estimée pour tuer un individu de l'espèce au niveau donné — réutilise la formule
	du combat (`max(1, niveau*4 + somme_attrs_moyens // 10)`, cf. utils/combat.py)."""
	attrs = (espece_doc or {}).get("base_attributes", {}) or {}
	somme = 0.0
	for v in attrs.values():
		if isinstance(v, dict):
			somme += (float(v.get("min", 0) or 0) + float(v.get("max", 0) or 0)) / 2.0
	return max(1, int(niveau) * 4 + int(somme) // 10)


def _xp_unitaire_item(item_doc: dict, niveau: int, get_doc_fn=None) -> int:
	"""Valeur unitaire d'une cible de collecte. Carcasse (item lié à une espèce) → XP de
	chasse de l'espèce ; ressource brute → effort de récolte modéré pondéré par la rareté."""
	get_doc_fn = get_doc_fn or get_doc
	src = (item_doc or {}).get("source_espece")
	if src:
		esp = get_doc_fn(src)
		if esp:
			return _xp_unitaire(esp, niveau)
	rarete = (item_doc or {}).get("rarete", "commun")
	mult = character_stats.MULT_RARETE.get(rarete, 1) or 1
	return max(1, int(niveau) * 2 + min(20, int(mult)))


_TITRES_KILL = ["Réguler les {nom}", "Chasse aux {nom}", "Éliminer les {nom}"]
_TITRES_COLLECT = ["Récolte : {nom}", "Rapporter du {nom}", "Collecte de {nom}"]
_TITRES_CHASSE = ["Traquer le {nom} « {grade} »", "Abattre le {nom} « {grade} »", "La tête du {nom} « {grade} »"]


def _generer_chasse(guild_doc: dict, parent_doc: dict, cible, get_doc_fn=None) -> dict | None:
	"""Doc `quete:*` d'une quête de chasse `board` (grade `max−1`) : `cible = (lieu_id, espece_id)`.
	Le grade est RÉSOLU ICI (à la génération), nommé dans le titre. None si aucun grade compatible."""
	from utils import chasse  # import paresseux : chasse dépend de ce module
	get_doc_fn = get_doc_fn or get_doc
	lieu_id, espece_id = cible
	lieu_doc = get_doc_fn(lieu_id)
	espece_doc = get_doc_fn(espece_id)
	if not lieu_doc or not espece_doc:
		return None
	position = chasse.position_de_chasse(lieu_doc, espece_doc)
	profil_id = chasse.resoudre_profil_chasse(lieu_doc, espece_doc, chasse.TIER_MAX_MOINS_1, position, get_doc_fn)
	if not profil_id:
		return None
	profil = get_doc_fn(profil_id) or {}
	niv = int(profil.get("niveau", 1))
	grade = chasse.qualificatif_de(profil)
	nom = espece_doc.get("nom") or _nom_espece(espece_id)
	lieu_nom = lieu_doc.get("label") or lieu_doc.get("nom") or (lieu_id or "").split(":", 1)[-1]

	xp = max(1, round(_xp_unitaire(espece_doc, niv) * character_stats.QUETE_CHASSE_XP_FACTEUR))
	cuivre = max(0, round(xp * character_stats.QUETE_CUIVRE_PAR_XP))
	objectif = {"type": "chasse", "cible": espece_id, "lieu": lieu_id, "profil": profil_id, "quantite": 1}
	if position is not None:
		objectif["position"] = position

	guild_id = guild_doc.get("_id", "")
	sub = guild_id.split(":", 1)[-1] if ":" in guild_id else guild_id
	now = now_epoch()
	return {
		"_id": f"quete:{sub}_{uuid.uuid4().hex[:12]}",
		"type": "quete",
		"source": "genere",
		"giver": guild_id,
		"lieu_parent": (parent_doc or {}).get("_id"),
		"titre": random.choice(_TITRES_CHASSE).format(nom=nom, grade=grade),
		"description": (
			f"Un {nom} d'exception — un « {grade} » — écume {lieu_nom}. "
			f"La guilde met sa tête à prix : traquez-le et abattez-le."
		),
		"rang": "F",
		"objectif": objectif,
		"recompenses": {"xp": xp, "cuivre": cuivre, "items": []},
		"statut": "offerte",
		"genere_at": now,
		"expire_at": now + _duree_de_vie(),
	}


def generer_quete(guild_doc: dict, parent_doc: dict, type_obj: str, cible, niveau: int, get_doc_fn=None) -> dict | None:
	"""Construit un doc `quete:*` (non persisté) pour une cible donnée. Renvoie None si une
	quête `chasse` ne peut être résolue (aucun grade compatible) — l'appelant saute la cible."""
	get_doc_fn = get_doc_fn or get_doc
	if type_obj == "chasse":
		return _generer_chasse(guild_doc, parent_doc, cible, get_doc_fn)
	if type_obj == "kill":
		esp = get_doc_fn(cible)
		xp_unit = _xp_unitaire(esp, niveau) if esp else max(1, int(niveau) * 4)
		nom = (esp.get("nom") if esp else None) or _nom_espece(cible)
		titre = random.choice(_TITRES_KILL).format(nom=nom)
		desc_tpl = "La guilde demande d'abattre {q} {nom} qui rôdent dans les environs d'Auxerre."
	else:  # collect
		item = get_doc_fn(cible)
		xp_unit = _xp_unitaire_item(item, niveau, get_doc_fn)
		nom = (item.get("nom") if item else None) or _nom_item(cible)
		titre = random.choice(_TITRES_COLLECT).format(nom=nom)
		desc_tpl = "Rapportez {q} {nom} à la guilde."

	# Quantité tirée dans [QTE_MIN, borne_haute] : plus la cible est « chère » (xp_unit
	# élevé), plus la borne haute se rapproche du minimum (objectifs courts pour les durs).
	qmin = int(character_stats.QUETE_QTE_MIN)
	qmax = max(qmin, int(character_stats.QUETE_QTE_MAX))
	plage = qmax - qmin
	facteur_diff = min(1.0, xp_unit / 40.0)  # ~40 XP/unité = cible difficile
	borne_haute = max(qmin, int(round(qmax - plage * facteur_diff)))
	quantite = random.randint(qmin, borne_haute)

	xp = max(1, round(xp_unit * quantite * character_stats.QUETE_XP_FACTEUR))
	cuivre = max(0, round(xp * character_stats.QUETE_CUIVRE_PAR_XP))

	guild_id = guild_doc.get("_id", "")
	sub = guild_id.split(":", 1)[-1] if ":" in guild_id else guild_id
	now = now_epoch()
	return {
		"_id": f"quete:{sub}_{uuid.uuid4().hex[:12]}",
		"type": "quete",
		"source": "genere",
		"giver": guild_id,
		"lieu_parent": (parent_doc or {}).get("_id"),
		"titre": titre,
		"description": desc_tpl.format(q=quantite, nom=nom),
		"rang": "F",
		"objectif": {"type": type_obj, "cible": cible, "quantite": quantite},
		"recompenses": {"xp": xp, "cuivre": cuivre, "items": []},
		"statut": "offerte",
		"genere_at": now,
		"expire_at": now + _duree_de_vie(),
	}


# ── Tableau de la guilde ─────────────────────────────────────────────────────────

def _duree_de_vie() -> int:
	"""Durée de vie d'une offre générée : QUETE_BOARD_DUREE_SECONDES, JITTÉE. Les offres d'un
	tableau naissent au même instant — sans jitter, elles périmeraient toutes ensemble et le
	tableau basculerait d'un bloc au lieu de tourner par petites touches."""
	base = int(character_stats.QUETE_BOARD_DUREE_SECONDES)
	jitter = max(0.0, float(character_stats.QUETE_BOARD_DUREE_JITTER))
	return max(1, int(base * random.uniform(1.0 - jitter, 1.0 + jitter)))


def offre_perimee(offre: dict, now: int) -> bool:
	"""Une offre GÉNÉRÉE encore au tableau dont l'échéance est passée : d'autres aventuriers
	ont vécu leur vie et l'ont prise. Une quête AUTHORÉE (mission écrite) ne périme jamais, et
	une offre déjà ACCEPTÉE n'est plus au tableau — ni l'une ni l'autre n'est concernée.
	Repli pour les offres d'avant la feature (pas d'`expire_at`) : `genere_at` + la durée
	nominale ; sans horodatage du tout, elles sont périmées d'office."""
	if offre.get("source") != "genere" or offre.get("statut", "offerte") != "offerte":
		return False
	expire_at = offre.get("expire_at")
	if not expire_at:
		genere_at = int(offre.get("genere_at", 0) or 0)
		expire_at = genere_at + int(character_stats.QUETE_BOARD_DUREE_SECONDES) if genere_at else 0
	return now >= int(expire_at)


def purger_offres_perimees(offres: list, now: int, delete_doc_fn=None) -> list:
	"""Retire du tableau — et de la BASE — les offres générées périmées. Le doc est supprimé
	(personne ne le référence : accepter une quête en fait un snapshot dans le perso) plutôt
	qu'archivé, sinon la collection `quete:*` gonflerait de plusieurs docs morts par guilde et
	par heure. Suppression best-effort. Renvoie les offres qui restent."""
	supprimer = delete_doc_fn or delete_doc
	restantes = []
	for o in offres:
		if offre_perimee(o, now):
			supprimer(o)
		else:
			restantes.append(o)
	return restantes


def offres_du_giver(guild_id: str) -> list:
	"""Offres ouvertes (`statut:"offerte"`) d'une guilde — générées ET authorées. Filtre `giver`
	posé DANS le selector Mango (pas en Python après coup) : sans lui, CouchDB renvoie tous les
	`quete:*` de TOUTES les guildes du jeu sur le réseau à chaque ouverture du tableau — un coût
	qui grandit avec le nombre de guildes/quêtes déjà générées, pour ne garder que celles d'ICI."""
	docs = find_docs({"type": "quete", "giver": guild_id}) or []
	return [d for d in docs if d.get("statut", "offerte") == "offerte"]


def lister_offres(guild_doc: dict) -> list:
	"""Offres ouvertes du tableau, PÉRIMÉES PURGÉES, **sans complétion**.

	Pour les endpoints qui ne libèrent AUCUNE place — terminer, déposer, abandonner : la quête
	a quitté le tableau à l'ACCEPTATION, il n'y a rien à recompléter, seulement à afficher.
	Y appeler `remplir_tableau` faisait payer à chacun une génération complète (jusqu'à 38
	requêtes) pour un tableau rigoureusement identique."""
	return purger_offres_perimees(offres_du_giver(guild_doc.get("_id")), now_epoch())


def remplir_tableau(guild_doc: dict) -> list:
	"""Périme les offres générées trop vieilles (prises par d'autres aventuriers) PUIS garantit
	QUETE_BOARD_TAILLE offres GÉNÉRÉES au tableau (complétées à la volée), persiste les
	nouvelles, et renvoie toutes les offres ouvertes (générées + authorées). Le nombre d'offres
	générées est borné par le nombre de cibles distinctes du parent."""
	parent_id = guild_doc.get("lieu_parent")
	parent_doc = get_doc(parent_id) if parent_id else None

	# Péremption PARESSEUSE (aucun tick de fond dans le jeu) : les places libérées sont
	# aussitôt repeuplées par la complétion ci-dessous.
	offres = lister_offres(guild_doc)
	generees = [o for o in offres if o.get("source") == "genere"]
	manquantes = max(0, int(character_stats.QUETE_BOARD_TAILLE) - len(generees))

	if manquantes > 0 and parent_doc:
		# Caches mémoïsés LOCAUX à cette passe : `_candidats_chasse` relit les mêmes docs
		# lieu/espèce/zone/profil à chaque paire (lieu, espèce) — sans lui, un tableau à
		# compléter revisite la même douzaine de docs des dizaines de fois. ⚠️ Le finder est
		# tout aussi indispensable que le getter : `cibles_collect` refaisait 36 requêtes
		# non indexées (6 ressources coupables × 6 tiers de bois) pour 6 listes distinctes.
		get_doc_c = _cached_getter(get_doc)
		find_docs_c = _cached_finder(find_docs)
		niveau = niveau_representatif(parent_doc, get_doc_c)
		existants = {_offre_key(o["objectif"]) for o in offres if o.get("objectif")}
		candidats = [("kill", eid) for eid in especes_du_parent(parent_doc)]
		candidats += [("collect", iid) for iid in cibles_collect(parent_doc, get_doc_c, find_docs_c)]
		candidats += _candidats_chasse(parent_id, get_doc_c, find_docs_c)
		random.shuffle(candidats)
		for type_obj, cible in candidats:
			if manquantes <= 0:
				break
			key = ("chasse", cible) if type_obj == "chasse" else (type_obj, cible)
			if key in existants:
				continue
			q = generer_quete(guild_doc, parent_doc, type_obj, cible, niveau, get_doc_c)
			if q is None or save_doc(q) is None:
				continue
			offres.append(q)
			existants.add(key)
			manquantes -= 1
	return offres


def _offre_key(objectif: dict):
	"""Clé de déduplication d'une offre au tableau. Une chasse est dédupliquée sur le couple
	(lieu, espèce) — une même espèce peut être traquée dans deux lieux ; les autres types sur
	(type, cible)."""
	if objectif.get("type") == "chasse":
		return ("chasse", (objectif.get("lieu"), objectif.get("cible")))
	return (objectif.get("type"), objectif.get("cible"))


def _candidats_chasse(cite_id: str, get_doc_fn=None, find_docs_fn=None) -> list:
	"""Candidats `("chasse", (lieu_id, espece_id))` du tableau : élites d'un lieu de la cité,
	résolvables au grade `max−1`. Balaie les lieux de chasse × leurs rencontres."""
	from utils import chasse  # import paresseux : chasse dépend de ce module
	get_doc_fn = get_doc_fn or get_doc
	find_docs_fn = find_docs_fn or find_docs
	out = []
	for L in chasse.lieux_chasse_de(cite_id, get_doc_fn, find_docs_fn):
		for eid in especes_du_parent(L):
			espece = get_doc_fn(eid)
			if not espece:
				continue
			position = chasse.position_de_chasse(L, espece)
			if position is None:
				continue
			if chasse.resoudre_profil_chasse(L, espece, chasse.TIER_MAX_MOINS_1, position, get_doc_fn):
				out.append(("chasse", (L["_id"], eid)))
	return out


# ── État joueur ──────────────────────────────────────────────────────────────────

def snapshot_quete(q: dict) -> dict:
	"""Copie figée d'une offre, posée dans `character["quetes_actives"]` à l'acceptation
	(la quête reste stable même si le doc `quete:*` est ensuite purgé/régénéré)."""
	return {
		"id": q.get("_id"),
		"titre": q.get("titre", "—"),
		"description": q.get("description", ""),
		"rang": q.get("rang", "F"),
		"giver": q.get("giver"),
		"objectif": dict(q.get("objectif", {})),
		"recompenses": dict(q.get("recompenses", {})),
		"progress": 0,
		"accepte_at": now_epoch(),
	}


def quete_active(character: dict, quete_id: str) -> dict | None:
	for q in character.get("quetes_actives", []):
		if q.get("id") == quete_id:
			return q
	return None


def _count_inventaire(character: dict, item_id: str) -> int:
	return sum(1 for ref in character.get("inventaire", []) if item_ref_id(ref) == item_id)


def progress_courant(character: dict, q: dict) -> int:
	"""Progression effective (entier) = compteur **`progress` stocké** sur la quête active, pour
	tous les types : `kill`/`visite` (incrémentés par les hooks) et `collect` (incrémenté par les
	dépôts à la guilde, cf. `deposer_collect`)."""
	return int(q.get("progress", 0) or 0)


def deposer_collect(character: dict, q: dict) -> int:
	"""Dépose à la guilde les pièces de collecte actuellement portées (jusqu'au reste à faire) :
	les retire de l'inventaire et incrémente `progress`. Mute en place ; renvoie le nombre déposé."""
	obj = q.get("objectif", {})
	if obj.get("type") != "collect":
		return 0
	reste = int(obj.get("quantite", 0) or 0) - int(q.get("progress", 0) or 0)
	if reste <= 0:
		return 0
	cible = obj.get("cible")
	n = min(reste, _count_inventaire(character, cible))
	if n <= 0:
		return 0
	retirer_items(character, cible, n)
	q["progress"] = int(q.get("progress", 0) or 0) + n
	return n


def objectif_atteint(character: dict, q: dict) -> bool:
	obj = q.get("objectif", {})
	return progress_courant(character, q) >= int(obj.get("quantite", 0) or 0)


def _focalisable(q: dict) -> bool:
	"""Cette quête accepte-t-elle la focalisation 🎯 ? (règle portée par utils/focalisation,
	importé paresseusement : c'est lui qui dépend de ce module, pas l'inverse.)"""
	from utils.focalisation import quete_focalisable
	return quete_focalisable(q)


def quete_detail(character: dict, q: dict, get_doc_fn=None) -> dict:
	"""Vue d'affichage d'une quête active (onglet fiche + tableau) : progression + récompenses.

	⚠️ `get_doc_fn` sert aux seules lectures de docs `lieu:*` — les plus GROSSES du jeu
	(`lieu:auxerre` ≈ 28 Ko avec ses `cells`) et les seules que le cache de requête ne peut
	pas amortir (cf. CLAUDE.md : copie de surface vs mutations imbriquées du stock). Trois
	chasses dans le même lieu le relisaient trois fois : `fiche_details` passe un getter
	mémoïsé pour toute la passe. `_cible_nom` garde le `get_doc` du module — il ne lit que
	des `espece:`/`item:`, déjà amortis."""
	lire = get_doc_fn or get_doc
	obj = q.get("objectif", {})
	prog = progress_courant(character, q)
	qte = int(obj.get("quantite", 0) or 0)
	rec = q.get("recompenses", {}) or {}
	purse = cuivre_to_purse(rec.get("cuivre", 0))
	carte_chasse = None
	if obj.get("type") == "transport":
		if q.get("livree_at"):
			# Course à retour : la marchandise est remise, il reste à en rendre compte au donneur.
			giver = lire(q.get("giver")) if q.get("giver") else None
			progress_txt = f"Rendre compte : {(giver or {}).get('label') or 'au donneur'}"
		else:
			progress_txt = f"Livraison à {_cible_nom(obj)}"
	elif obj.get("type") == "escorte":
		# Deux temps, deux libellés : tant qu'on ne l'a pas retrouvée, c'est une recherche
		# (et la carte 🗺️ mène au rendez-vous) ; ensuite c'est une livraison de personne.
		# Import PARESSEUX : `escorte` dépend de ce module, jamais l'inverse (cf. `_focalisable`).
		from utils.escorte import noms_proteges
		qui = noms_proteges(q.get("proteges") or []) or "votre protégé"
		if q.get("rencontre_at"):
			progress_txt = f"Escorter {qui} jusqu'à : {_cible_nom(obj)}"
		else:
			rdv = obj.get("rencontre") or {}
			rdv_doc = lire(rdv.get("lieu")) if rdv.get("lieu") else None
			rdv_nom = ((rdv_doc or {}).get("label") or (rdv_doc or {}).get("nom")
					   or (rdv.get("lieu") or "").split(":", 1)[-1])
			if rdv.get("position"):
				# ⚠️ `_carte_chasse` est réutilisée SANS être modifiée : on lui passe un
				# objectif SYNTHÉTIQUE `{lieu, position}` bâti depuis `rencontre`. L'ancre du
				# repère est le donneur — un temple n'est pas « le bâtiment de la guilde ».
				giver_doc = lire(q.get("giver")) if q.get("giver") else None
				carte_chasse = _carte_chasse(
					{"lieu": rdv["lieu"], "position": rdv["position"]},
					q.get("giver"), rdv_doc, ancre=_ancre_de(giver_doc))
			repere = (carte_chasse or {}).get("direction_texte")
			progress_txt = (
				f"Retrouver {qui}" + (f" ({rdv_nom})" if rdv_nom else "")
				+ (f" — {repere}" if repere else "")
			)
	elif obj.get("type") == "chasse":
		lieu_doc = lire(obj.get("lieu")) if obj.get("lieu") else None
		lieu_nom = (lieu_doc.get("label") or lieu_doc.get("nom")) if lieu_doc else None
		lieu_nom = lieu_nom or (obj.get("lieu") or "").split(":", 1)[-1]
		compteur = min(prog, qte) if qte else prog
		if obj.get("position"):
			carte_chasse = _carte_chasse(obj, q.get("giver"), lieu_doc)
		# ⚠️ Deux chasses au même gibier et au même grade portent un titre et une description
		# RIGOUREUSEMENT identiques (figés à la génération) : sans le repère d'orientation, le
		# joueur n'a aucun moyen de les distinguer dans sa fiche et croit en voir une seule qui
		# oscille. C'est la case visée — donc la direction — qui les sépare.
		repere = (carte_chasse or {}).get("direction_texte")
		progress_txt = (
			f"Traquer l'élite : {_cible_nom(obj)} ({lieu_nom}) — {compteur}/{qte}"
			+ (f" · {repere}" if repere else "")
		)
	else:
		progress_txt = f"{_cible_nom(obj)} : {min(prog, qte) if qte else prog}/{qte}"
	detail = {
		"id": q.get("id") or q.get("_id"),
		"titre": q.get("titre", "—"),
		"description": q.get("description", ""),
		"rang": q.get("rang", "F"),
		"objectif": obj,
		"progress": min(prog, qte) if qte else prog,
		"quantite": qte,
		"complete": prog >= qte,
		"progress_txt": progress_txt,
		# Le bouton 🎯 n'a de sens que si la focalisation ferait quelque chose (guidage ou biais
		# des tirages) — pas sur une course de transport. Import paresseux : focalisation importe
		# déjà ce module.
		"focalisable": _focalisable(q),
		"recompenses": {
			"xp": rec.get("xp", 0),
			"or": purse["or"],
			"argent": purse["argent"],
			"cuivre": purse["cuivre"],
		},
	}
	# Quête à délai réel (transport) : on expose l'échéance ET l'heure serveur, le client en
	# déduit une deadline locale — comparer `expire_at` à l'horloge du navigateur dériverait.
	if q.get("expire_at"):
		detail["expire_at"] = int(q["expire_at"])
		detail["now"] = now_epoch()
	# Quête de chasse localisée : de quoi dessiner le crop 3×3 de la carte centré sur la cible
	# (déjà calculé plus haut — le libellé de progression en tire son repère d'orientation).
	if carte_chasse:
		detail["carte"] = carte_chasse
	return detail


ANCRE_DEFAUT = "du bâtiment de la guilde"


def _ancre_de(giver_doc: dict | None) -> str:
	"""Groupe nominal désignant le donneur dans la ligne d'orientation (« du temple de
	Saint-Eusèbe »). Repli sur l'ancre historique quand le donneur n'est pas joignable."""
	nom = (giver_doc or {}).get("label") or (giver_doc or {}).get("nom")
	return f"de {nom}" if nom else ANCRE_DEFAUT


def _phrase_direction(direction: str, ancre: str = ANCRE_DEFAUT) -> str:
	"""Ligne d'orientation de l'overlay carte à partir d'une direction cardinale (« sud-est »…).
	Gère la préposition : « À l'est/ouest » (pur E/O), « Au … » sinon (nord/sud, composés).
	`ancre` = le repère de départ ; défaut inchangé pour les chasses (guilde)."""
	if not direction:
		return f"Sur l'emplacement {ancre}"
	prep = "À l'" if direction[0] in ("e", "o") else "Au "
	return f"{prep}{direction} {ancre}"


def _carte_chasse(objectif: dict, giver_id: str | None = None, lieu_doc: dict | None = None,
				  ancre: str = ANCRE_DEFAUT) -> dict | None:
	"""Données du bouton 🗺️ d'une quête de chasse : l'image servable du lieu + ses dimensions
	en cases + la position cible → le client recadre un 3×3 centré sur la case. None si le lieu
	n'a pas d'image servable ou pas de grille (le bouton est alors masqué). Ajoute une ligne
	d'orientation « Au <direction> du bâtiment de la guilde » si le donneur est joignable.
	`lieu_doc` réutilise le doc déjà fetché par `quete_detail` (même lieu) au lieu de le relire."""
	lieu = lieu_doc if lieu_doc is not None else (get_doc(objectif.get("lieu")) if objectif.get("lieu") else None)
	dims = (lieu or {}).get("dimensions")
	if not lieu or not dims:
		return None
	# Pas de case visée ⇒ pas de carte : tout l'objet de l'overlay est « va sur CETTE case ».
	# Sans ce garde, un objectif sans `position` recadrerait sur (0,0) et enverrait le joueur
	# au mauvais endroit. Aucune régression : les chasses générées ne posent `position` que
	# lorsque le lieu a une grille, et sans grille on est déjà sorti juste au-dessus — c'est
	# une commission de donjon (lieu `battle_map`, où l'on entre par un PNJ) qui l'exerce.
	pos = objectif.get("position") or {}
	if not pos:
		return None
	image, route = marche._lieu_image_route(lieu)
	if not image or not route:
		return None
	carte = {
		"position": dict(pos),
		"dimensions": dims,
		"image": image,
		"image_route": route,
		"lieu_nom": lieu.get("label") or lieu.get("nom") or (lieu.get("_id") or "").split(":", 1)[-1],
	}
	# Orientation depuis le bâtiment donneur : porte du 1er lien vers le donneur, dans la grille
	# de CE lieu (BFS multi-hop → marche même si le comptoir est imbriqué derrière une façade).
	if giver_id:
		from utils import focalisation, chasse  # imports paresseux (dépendent de ce module)
		etape = focalisation.prochaine_etape(
			focalisation.charger_graphe(find_docs), objectif.get("lieu"), giver_id)
		if etape and etape.get("porte"):
			direction = chasse.direction_cardinale_simple(
				etape["porte"], (int(pos.get("x", 0)), int(pos.get("y", 0))))
			carte["direction_texte"] = _phrase_direction(direction, ancre)
	return carte


def fiche_details(character: dict, get_doc_fn=None) -> tuple:
	"""Détails affichables des quêtes du perso, TOUS donneurs confondus (onglet 📜 de la
	fiche). Renvoie (actives_detail, terminees). Partagé par /play et les endpoints quêtes
	pour que la fiche reflète accept/terminer sans rechargement.

	UN getter mémoïsé pour toute la passe : plusieurs chasses dans le même lieu ne relisent
	plus le même (gros) doc `lieu:*` une fois chacune."""
	lire = get_doc_fn or _cached_getter(get_doc)
	actives = [quete_detail(character, q, lire) for q in character.get("quetes_actives", [])]
	terminees = list(character.get("quetes_terminees", []))
	return actives, terminees


def retirer_items(character: dict, item_id: str, quantite: int) -> int:
	"""Retire jusqu'à `quantite` exemplaires de `item_id` de l'inventaire (mute en place).
	Renvoie le nombre réellement retiré. Utilisé au turn-in des quêtes `collect`."""
	inv = character.get("inventaire", [])
	garde = []
	retire = 0
	for ref in inv:
		if retire < quantite and item_ref_id(ref) == item_id:
			retire += 1
			continue
		garde.append(ref)
	character["inventaire"] = garde
	return retire


def appliquer_recompenses(character: dict, q: dict, compagnons: list | None = None,
						  get_doc_fn=None) -> dict:
	"""Crédite XP + cuivre (+ items éventuels) d'une quête (mute en place, NE SAUVEGARDE
	PAS — l'endpoint persiste). Renvoie un récap {xp, purse, compagnie}.

	CHOKEPOINT UNIQUE des récompenses de quête (tableau de guilde, épreuve de rang,
	commission de donjon, course de transport) : c'est donc ici — et nulle part ailleurs —
	que la COMPAGNIE touche la même XP que le principal (`recrutement.partager_xp`).

	⚠️ `compagnie` = les docs `aventurier:*` MUTÉS, **à persister par l'appelant** après son
	`save_doc(character)` autoritatif. Un compagnon sous contrat n'y figure jamais ; la part
	de butin n'est pas concernée (un permanent reste à 0, cf. `conditions_effectives`).
	⚠️ `compagnons` : docs déjà chargés par l'appelant, à repasser pour ne pas obtenir un
	second dict du même document."""
	rec = q.get("recompenses", {}) or {}
	xp = rec.get("xp", 0)
	xp_info = grant_xp(character, xp)
	compagnie = recrutement.partager_xp(character, xp, compagnons, get_doc_fn)
	purse = credit_character(character, rec.get("cuivre", 0))
	items = rec.get("items") or []
	if items:
		inv = character.get("inventaire", [])
		inv.extend(items)
		character["inventaire"] = inv
	# Inscription à un rang de guilde portée par la récompense (`{cite, rang}`, résolu à la
	# génération de l'offre) : c'est ainsi qu'une PREMIÈRE MISSION fait entrer le joueur dans
	# la guilde, là où l'épreuve de rang le fait MONTER (`chasse.promouvoir`).
	# ⚠️ Import PARESSEUX : `chasse` importe ce module, un import de tête boucle.
	rang = None
	if rec.get("rang_guilde"):
		from utils.chasse import crediter_rang
		rang = crediter_rang(character, rec["rang_guilde"])
	return {"xp": xp_info, "purse": purse, "compagnie": compagnie, "rang": rang}


# ── Renoncement : la maison du donneur encaisse d'un bloc ────────────────────────

def sous_categorie_lieu(lieu_doc: dict) -> str:
	"""Maison à laquelle un lieu appartient (`sous_categorie`, même orthographe que sur les items)."""
	return str((lieu_doc or {}).get("sous_categorie") or "").strip()


def lieux_solidaires(giver_doc: dict, find_docs_fn=None) -> list:
	"""Lieux dont la réputation encaisse ENSEMBLE un renoncement du joueur.

	Une maison (guilde…) est éclatée en plusieurs lieux — réception, comptoir… — qui portent
	la même `sous_categorie` mais ont la CITÉ pour `lieu_parent` : c'est la CONJONCTION des
	deux qui la reconstitue (le seul `lieu_parent` ramènerait toute la ville, boucheries
	comprises ; la seule `sous_categorie` ramènerait les guildes des autres cités). Un donneur
	sans `sous_categorie` — un magasin — n'est solidaire que de lui-même.
	"""
	sous_cat = sous_categorie_lieu(giver_doc)
	parent = (giver_doc or {}).get("lieu_parent")
	if not sous_cat or not parent:
		return [giver_doc]
	freres = (find_docs_fn or find_docs)({"type": "lieu", "lieu_parent": parent}) or []
	lieux = [giver_doc]
	vus = {(giver_doc or {}).get("_id")}
	for d in freres:
		if d.get("_id") not in vus and sous_categorie_lieu(d) == sous_cat:
			lieux.append(d)
			vus.add(d.get("_id"))
	return lieux


def sanctionner_renoncement(character: dict, giver_doc: dict, get_doc_fn, save_doc_fn, find_docs_fn=None) -> dict:
	"""Renoncer à une quête (abandon volontaire ou délai laissé filer) coûte
	QUETE_TRANSPORT_RELATION_DELTA de réputation chez le donneur ET chez tous les lieux de sa
	maison : lâcher la mission du comptoir fâche aussi la réception. Les docs `relation` sont
	ANNEXES (hors character) → persistés ici, un par DOC relation. Renvoie
	{lieu_id: nouvelle_valeur}."""
	delta = -int(character_stats.QUETE_TRANSPORT_RELATION_DELTA)
	valeurs = {}
	# ⚠️ Dédup par DOC RELATION et non par id de lieu : deux lieux d'une maison peuvent
	# déléguer leur réputation au même porteur (`marche.lieu_de_relation`) — les traiter
	# séparément appliquerait le malus DEUX fois, le second `get_relation` relisant le doc que
	# le premier vient de sauver. Le retour reste indexé par LIEU (même valeur pour les lieux
	# qui partagent une relation : c'est exact, ils la partagent).
	docs: dict[str, dict] = {}
	for lieu in lieux_solidaires(giver_doc, find_docs_fn):
		doc_id = marche.relation_doc_id(character, lieu)
		relation = docs.get(doc_id)
		if relation is None:
			relation = marche.get_relation(character, lieu, get_doc_fn)
			docs[doc_id] = relation
			marche.ajuster_relation(relation, delta)
			save_doc_fn(relation)
		valeurs[lieu.get("_id")] = marche.relation_value(relation)
	return valeurs


def recompenser_lieux(character: dict, lieux_docs: list, get_doc_fn, save_doc_fn) -> dict:
	"""Monte de QUETE_REUSSITE_RELATION_DELTA (borné 0–100) la réputation de CHACUN des lieux
	remerciés par une quête réussie. Implémentation unique de `recompenser_donneur`, qui n'en
	est que le cas à un lieu.

	⚠️ **Dédup par DOC RELATION et non par id de lieu** — c'est tout l'intérêt d'un chokepoint
	ici. Deux cas le rendent indispensable : une escorte de progéniture confiée par le magasin
	LUI-MÊME a le même lieu pour donneur et pour destination (elle paierait +2), et deux lieux
	d'une maison peuvent déléguer leur réputation au même porteur (`marche.lieu_de_relation`).
	Dans les deux cas le second `get_relation` relirait le doc que le premier vient de sauver.
	Même précaution, même forme que `sanctionner_renoncement`.

	Les docs `relation` sont ANNEXES (hors character) : persistés ici, un par DOC relation ; le
	personnage est laissé à son appelant. Renvoie {lieu_id: nouvelle_valeur} — même valeur pour
	les lieux qui partagent une relation, c'est exact : ils la partagent."""
	delta = int(character_stats.QUETE_REUSSITE_RELATION_DELTA)
	valeurs: dict = {}
	docs: dict[str, dict] = {}
	for lieu in lieux_docs or []:
		if not lieu:
			continue
		doc_id = marche.relation_doc_id(character, lieu)
		relation = docs.get(doc_id)
		if relation is None:
			relation = marche.get_relation(character, lieu, get_doc_fn)
			docs[doc_id] = relation
			marche.ajuster_relation(relation, delta)
			save_doc_fn(relation)
		valeurs[lieu.get("_id")] = marche.relation_value(relation)
	return valeurs


def recompenser_donneur(character: dict, giver_doc: dict, get_doc_fn, save_doc_fn) -> int | None:
	"""Réussir une quête monte la réputation chez son DONNEUR de
	QUETE_REUSSITE_RELATION_DELTA (borné 0–100). Pendant positif de
	`sanctionner_renoncement`, et chokepoint unique des CINQ turn-in : tableau de guilde,
	épreuve de rang, commission de donjon, course de transport, escorte.

	⚠️ **Asymétrie VOULUE** : la maison punit collectivement (`lieux_solidaires`), elle ne
	remercie que le donneur — c'est `relation_lieu` qui route le gain vers le consolidateur
	quand la donnée le demande. Une quête qui veut remercier un SECOND lieu (l'escorte de
	progéniture remercie la guilde ET le magasin) passe par `recompenser_lieux`, dont ceci
	n'est que le cas à un lieu. Renvoie la nouvelle valeur, `None` sans donneur."""
	if not giver_doc:
		return None
	valeurs = recompenser_lieux(character, [giver_doc], get_doc_fn, save_doc_fn)
	return valeurs.get(giver_doc.get("_id"))


# ── Hooks de progression (appelés par combat / déplacement) ──────────────────────

def maj_progress_kills(character: dict, monstres: list) -> None:
	"""Incrémente la progression des quêtes `kill` actives selon les monstres tués
	(`not vivant`). Mute `character["quetes_actives"]` en place. À appeler dans
	finalize_combat, sous le garde exactly-once `combats_recompenses`."""
	actives = character.get("quetes_actives", [])
	if not actives:
		return
	morts = {}
	for m in monstres or []:
		if not m.get("vivant", True):
			eid = m.get("espece_id")
			if eid:
				morts[eid] = morts.get(eid, 0) + 1
	if not morts:
		return
	for q in actives:
		obj = q.get("objectif", {})
		if obj.get("type") != "kill":
			continue
		n = morts.get(obj.get("cible"), 0)
		if not n:
			continue
		qte = int(obj.get("quantite", 0) or 0)
		q["progress"] = min(qte, int(q.get("progress", 0) or 0) + n)


def maj_progress_chasse(character: dict, monstres: list) -> None:
	"""Complète les quêtes `chasse` actives dont l'élite MARQUÉE est tombée : un monstre mort
	(`not vivant`) portant `quete_chasse == q.id`. Les autres monstres de la même espèce ne
	comptent pas — seule la cible marquée, et une bête ne porte JAMAIS qu'un seul contrat
	(cf. `chasse.marquer_elites`). Mute en place. À appeler dans finalize_combat, juste après
	maj_progress_kills (même fenêtre d'idempotence, garde `combats_recompenses`)."""
	actives = character.get("quetes_actives", [])
	if not actives:
		return
	tues = {
		m.get("quete_chasse") for m in (monstres or [])
		if not m.get("vivant", True) and m.get("quete_chasse")
	}
	if not tues:
		return
	for q in actives:
		obj = q.get("objectif", {})
		if obj.get("type") != "chasse":
			continue
		if (q.get("id") or q.get("_id")) in tues:
			q["progress"] = int(obj.get("quantite", 1) or 1)


def maj_progress_visite(character: dict, lieu_id: str) -> None:
	"""Marque atteint tout objectif `visite` actif ciblant `lieu_id`. Mute en place."""
	for q in character.get("quetes_actives", []):
		obj = q.get("objectif", {})
		if obj.get("type") == "visite" and obj.get("cible") == lieu_id:
			q["progress"] = int(obj.get("quantite", 1) or 1)
