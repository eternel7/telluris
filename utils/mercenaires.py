# utils/mercenaires.py
# Compagnons-JOUEURS (multijoueur asynchrone) : un joueur inscrit son personnage au tableau
# d'information d'une auberge (doc `service:<empreinte>`, `id_offre`, clauses saisies par lui) ; un
# autre joueur l'y engage. Le personnage recruté est joué comme un compagnon : un doc
# `aventurier:joueur_*` (CLONE, miroir du character → tout le moteur de combat tourne dessus)
# dont la PROGRESSION et l'ÉQUIPEMENT PORTÉ sont relus sur l'original à chaque lecture
# (`synchroniser`, appelée par `recrutement.groupe_effectif`), et dont seuls le SAC, les PV/PM
# et les effets sont propres.
#
# - Un seul recruteur à la fois : disponibilité DÉRIVÉE (`offre_disponible`), rien à réécrire
#   quand le clone meurt ou part.
# - L'XP et la part de butin du clone remontent à l'original par COMPTEURS MONOTONES posés sur
#   le clone (`xp_pour_original`, `cuivre_pour_original`) ; l'original encaisse le delta à son
#   prochain /play (`encaisser`) — on n'écrit jamais le doc d'un autre joueur.
# - Mort (0 PV en fin de combat, toute issue) : `mourir` — hors du groupe, sac rendu (versé au
#   sol par l'appelant), équipement intact (il appartient à l'original).
#
# Logique pure : DB injectée, mute sans sauver. ⚠️ N'importe NI `recrutement` NI `auberge`
# (c'est `recrutement` qui importe ce module ; `auberge` → `expedition` → `recrutement`).

import copy
import hashlib
import time
import uuid

from models import character_stats
from models.character_stats import BaseStats, compute_derived_stats
from utils.characters import sync_equipment_bonus, grant_xp, credit_character
from utils.consommables import caracts_avec_buffs

TYPE_OFFRE = "offre_service"
PREFIXE_OFFRE = "service:"

# Champs RELUS sur l'original à chaque lecture : la progression et l'équipement porté.
# ⚠️ Ni `attribute_points` (la fiche du clone n'offre rien à dépenser), ni l'inventaire, ni
# les vitaux, ni les effets — ceux-là sont au clone.
CHAMPS_SYNCHRO = (
	"caracteristiques_current", "caracteristiques_standard", "vocations_niveaux", "voc",
	"xp_total", "sorts_connus", "competences_connues", "competences_bonus", "magies_apprises",
	"max_bonus_used",
)
IDENTITE = ("prenom", "nom", "sex", "race", "image", "portrait_zoom", "portrait_translate")


def now_epoch() -> int:
	return int(time.time())


def id_offre(character_id: str) -> str:
	"""Id OPAQUE de l'offre d'un personnage (déterministe : une offre par personnage). ⚠️ Pas
	l'id du personnage en clair : il contient le courriel de son joueur
	(`character:user:<courriel>_<uuid>`), et l'id de l'offre part chez tous les clients."""
	return PREFIXE_OFFRE + hashlib.sha256(str(character_id).encode()).hexdigest()[:24]


def est_clone(doc: dict | None) -> bool:
	"""Un compagnon-joueur : le doc porte le lien vers son original."""
	return bool((doc or {}).get("source_character"))


# ── Exigences saisies par le joueur ─────────────────────────────────────────────

def _ligne(brut, max_len: int) -> str:
	"""Miroir de `auberge.nettoyer_ligne` (non importable ici, cf. en-tête) : non-imprimables
	retirés, blancs écrasés, troncature dure. ⚠️ BORNE sans échapper (Convention §9)."""
	texte = "" if brut is None else str(brut)
	texte = "".join(" " if c in "\t\n\r\f\v" else c
					for c in texte if c.isprintable() or c in "\t\n\r\f\v")
	return " ".join(texte.split())[:max(0, int(max_len or 0))]


def nettoyer_exigences(body: dict | None) -> dict:
	"""Part de butin bornée dans [0, RECRUTEMENT_PART_BUTIN_MAX] (un joueur peut servir
	gratuitement, jamais plus cher qu'une recrue) ; clauses = une par ligne (liste ou texte),
	vides écartées, nombre et longueur bornés."""
	body = body or {}
	try:
		part = int(body.get("part_butin_pct", 0) or 0)
	except (TypeError, ValueError):
		part = 0
	part = max(0, min(int(character_stats.RECRUTEMENT_PART_BUTIN_MAX), part))
	brutes = body.get("clauses") or []
	if isinstance(brutes, str):
		brutes = brutes.splitlines()
	if not isinstance(brutes, list):
		brutes = []
	clauses = []
	for c in brutes:
		ligne = _ligne(c, int(character_stats.MERCENAIRE_CLAUSE_LONGUEUR_MAX))
		if ligne:
			clauses.append(ligne)
		if len(clauses) >= int(character_stats.MERCENAIRE_CLAUSES_MAX):
			break
	return {"part_butin_pct": part, "clauses": clauses}


# ── Offre au tableau ────────────────────────────────────────────────────────────

def nouvelle_offre(character: dict, lieu_doc: dict, exigences: dict,
				   ancienne: dict | None = None) -> dict:
	"""Doc d'offre (créé ou mis à jour : `ancienne` conserve `_rev`, l'historique `clones` et
	le `clone_id` courant). Ré-afficher une offre retirée la remet au tableau de CE lieu."""
	doc = dict(ancienne or {})
	doc.update({
		"_id": id_offre(character["_id"]),
		"type": TYPE_OFFRE,
		"character_id": character["_id"],
		"user_id": character.get("user_id"),
		"lieu": (lieu_doc or {}).get("_id", ""),
		"exigences": exigences,
		"identite": identite_de(character),
		"statut": "affiche",
		"maj_at": now_epoch(),
	})
	doc.setdefault("cree_at", doc["maj_at"])
	doc.setdefault("clones", [])
	return doc


def identite_de(character: dict) -> dict:
	"""Carte d'identité DÉNORMALISÉE sur l'offre (le tableau est sondé toutes les 4 s : on ne
	relit pas le personnage d'autrui à chaque passage) ; rafraîchie à l'inscription et à
	chaque /play de l'original (`encaisser`)."""
	voc = character.get("voc", "")
	return {
		"prenom": character.get("prenom", ""), "nom": character.get("nom", ""),
		"race": character.get("race", ""), "voc": voc, "sex": character.get("sex", ""),
		"voc_niveau": (character.get("vocations_niveaux") or {}).get(voc, 0),
		"niveau": character_stats.compute_character_level(character.get("xp_total", 0)),
		"image": character.get("image", ""),
		"portrait_zoom": character.get("portrait_zoom"),
		"portrait_translate": character.get("portrait_translate"),
	}


def clone_courant(offre: dict | None, get_doc_fn) -> dict | None:
	"""Le clone EN SERVICE de cette offre (statut `embauche`), sinon None."""
	cid = (offre or {}).get("clone_id")
	if not cid:
		return None
	clone = get_doc_fn(cid)
	if clone and clone.get("statut") == "embauche" and clone.get("embauche_par"):
		return clone
	return None


def offre_disponible(offre: dict | None, get_doc_fn) -> bool:
	"""Affichée ET personne ne l'emploie : DÉRIVÉ, aucune écriture à la mort ou au congé."""
	if not offre or offre.get("statut") != "affiche":
		return False
	return clone_courant(offre, get_doc_fn) is None


def peut_engager(recruteur: dict, offre: dict | None, get_doc_fn) -> tuple[bool, str, int]:
	"""(ok, raison, code HTTP). On n'engage ni un personnage de son PROPRE compte (sinon on
	ferait progresser ses autres personnages en en jouant un), ni une offre occupée."""
	if not offre or offre.get("statut") != "affiche":
		return False, "Cette offre n'est plus affichée.", 404
	if offre.get("user_id") and offre.get("user_id") == recruteur.get("user_id"):
		return False, "Vous ne pouvez pas engager l'un de vos propres personnages.", 403
	if not offre_disponible(offre, get_doc_fn):
		return False, "Ce personnage est déjà engagé par quelqu'un d'autre.", 409
	return True, "", 200


# ── Clone ──────────────────────────────────────────────────────────────────────

def _slots_sans_contenu(slots: dict) -> dict:
	"""Copie profonde des slots de l'original SANS `contenu` : un contenant équipé ne doit
	jamais ouvrir au recruteur ce que l'original y range."""
	out = {}
	for s, ref in (slots or {}).items():
		ref = copy.deepcopy(ref)
		if isinstance(ref, dict):
			ref.pop("contenu", None)
		out[s] = ref
	return out


def _maxima(doc: dict) -> tuple[int, int]:
	equipment = sync_equipment_bonus(doc)
	stats = caracts_avec_buffs(doc)
	base = BaseStats(
		v=stats.get("V", 0), f=stats.get("F", 0), r=stats.get("R", 0),
		ag=stats.get("Ag", 0), vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
		cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
	)
	niveau = (doc.get("vocations_niveaux") or {}).get(doc.get("voc", ""), 0)
	d = compute_derived_stats(base, niveau=niveau, equipment=equipment)
	return d.pv_max, d.pm_max


def synchroniser(clone: dict, original: dict | None) -> bool:
	"""Recopie sur le clone la progression et l'équipement porté de l'original (mute, ne
	sauve pas). Vitaux bornés au nouveau maximum. False si l'original a disparu."""
	if not original:
		return False
	for champ in CHAMPS_SYNCHRO:
		if champ in original:
			clone[champ] = copy.deepcopy(original[champ])
	for champ in IDENTITE:
		if champ in original:
			clone[champ] = copy.deepcopy(original[champ])
	clone["slots"] = _slots_sans_contenu(original.get("slots") or {})
	clone["attribute_points"] = 0
	pv_max, pm_max = _maxima(clone)
	clone["currentPV"] = min(int(clone.get("currentPV", pv_max) or 0), pv_max)
	clone["currentPM"] = min(int(clone.get("currentPM", pm_max) or 0), pm_max)
	return True


def creer_clone(original: dict, offre: dict) -> dict:
	"""Doc `aventurier:joueur_*` neuf (statut `offert`, à attacher par `recrutement`) :
	sac VIDE, bourse vide, exigences de l'offre, PV/PM au maximum."""
	# ⚠️ Id sans rien de l'original (son id contient le courriel de son joueur).
	clone = {
		"_id": f"aventurier:joueur_{uuid.uuid4().hex}",
		"type": "aventurier",
		"statut": "offert",
		"source_character": original["_id"],
		"source_user": original.get("user_id"),
		"offre": offre.get("_id"),
		"giver": offre.get("lieu"),
		"inventaire": [],
		"slots": {},
		"equipment_bonus": {},
		"effets_actifs": [],
		"or": 0, "argent": 0, "cuivre": 0,
		"combats_recompenses": [],
		"specialite": "Personnage d'un autre joueur.",
		"exigences": copy.deepcopy(offre.get("exigences") or {"part_butin_pct": 0, "clauses": []}),
		"xp_pour_original": 0,
		"cuivre_pour_original": 0,
		"genere_at": now_epoch(),
		"currentPV": 10 ** 6,   # bornés au maximum par `synchroniser`
		"currentPM": 10 ** 6,
	}
	synchroniser(clone, original)
	return clone


def crediter_xp(clone: dict, xp: int) -> None:
	"""XP gagnée par le clone → compteur monotone de l'original (encaissé à son /play)."""
	if est_clone(clone):
		clone["xp_pour_original"] = int(clone.get("xp_pour_original", 0) or 0) + max(0, int(xp or 0))


def crediter_cuivre(clone: dict, cuivre: int) -> None:
	"""Part de butin du clone → compteur monotone de l'original."""
	if est_clone(clone):
		clone["cuivre_pour_original"] = (int(clone.get("cuivre_pour_original", 0) or 0)
										 + max(0, int(cuivre or 0)))


def vider_sac(clone: dict) -> list:
	"""Retire et rend le sac du clone (l'équipement reste : il est à l'original)."""
	sac = list(clone.get("inventaire") or [])
	clone["inventaire"] = []
	return sac


def mourir(character: dict, clone: dict) -> list:
	"""Le clone tombe : hors du groupe, statut `mort`, sac rendu (l'appelant le verse au sol
	du principal). Mute les deux docs, ne sauve pas."""
	groupe = character.get("groupe", []) or []
	if clone.get("_id") in groupe:
		groupe.remove(clone["_id"])
	character["groupe"] = groupe
	clone["statut"] = "mort"
	clone["currentPV"] = 0
	clone.pop("auras_recues", None)
	return vider_sac(clone)


def doit_partir(clone: dict, get_doc_fn) -> bool:
	"""Clone en service dont l'original a disparu ou a RETIRÉ ses services : il quitte le
	groupe de son recruteur au prochain passage (paresseux, Convention §5)."""
	if not est_clone(clone):
		return False
	if not get_doc_fn(clone["source_character"]):
		return True
	offre = get_doc_fn(clone.get("offre") or "")
	return (not offre or offre.get("statut") != "affiche"
			or offre.get("clone_id") != clone.get("_id"))


# ── Encaissement par l'original ────────────────────────────────────────────────

def encaisser(character: dict, offre: dict | None, get_doc_fn) -> dict:
	"""Crédite à l'original le DELTA des compteurs de chacun de ses clones (mute `character`
	et `offre` — l'historique est élagué des clones partis entièrement encaissés). Idempotent :
	la mémoire `encaisse_clones` vit dans le même doc que l'XP. Retourne {xp, cuivre, offre_mutee}."""
	total_xp = total_cu = 0
	if not offre:
		return {"xp": 0, "cuivre": 0, "offre_mutee": False}
	memo = character.get("encaisse_clones") or {}
	garder = []
	for cid in offre.get("clones") or []:
		clone = get_doc_fn(cid)
		if not clone:
			memo.pop(cid, None)
			continue
		vu = memo.get(cid) or {}
		dxp = max(0, int(clone.get("xp_pour_original", 0) or 0) - int(vu.get("xp", 0) or 0))
		dcu = max(0, int(clone.get("cuivre_pour_original", 0) or 0) - int(vu.get("cuivre", 0) or 0))
		if dxp:
			grant_xp(character, dxp)
			total_xp += dxp
		if dcu:
			credit_character(character, dcu)
			total_cu += dcu
		memo[cid] = {"xp": int(clone.get("xp_pour_original", 0) or 0),
					 "cuivre": int(clone.get("cuivre_pour_original", 0) or 0)}
		if clone.get("statut") == "embauche" or cid == offre.get("clone_id"):
			garder.append(cid)
		else:
			memo.pop(cid, None)   # parti / mort et soldé : plus rien à encaisser
	identite = identite_de(character)
	mutee = garder != list(offre.get("clones") or []) or identite != offre.get("identite")
	offre["clones"] = garder
	offre["identite"] = identite
	character["encaisse_clones"] = memo
	return {"xp": total_xp, "cuivre": total_cu, "offre_mutee": mutee}
