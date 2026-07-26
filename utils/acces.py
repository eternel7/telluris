# utils/acces.py
# Barrière d'accès à un lieu, gardée par un PNJ — « un PNJ ouvre un lieu sous
# conditions ». Pattern utils/recrutement.py / utils/transport.py : logique PURE, DB
# injectée (get_doc_fn), mute sans jamais sauvegarder — l'appelant persiste.
#
# La barrière est une DONNÉE portée par le lieu de DESTINATION (jamais par le doc
# `connection` : un lieu peut avoir plusieurs portes, la barrière est une propriété
# du lieu, pas du chemin) :
#
#   "acces": {
#     "gardien": "pnj:xxx",       # informatif (lore/403), ne participe pas au test
#     "refus": "texte du 403",    # informatif
#     "cycle": 1,                 # crochet de révocation du futur reset de donjon
#     "conditions": [ {...}, {...} ]   # ET logique, liste vide/absente = lieu libre
#   }
#
# Vocabulaire des conditions (trois clés) :
#   - quete_active: {lieu?, types?, giver_categorie?, cible?, objectif_atteint?} — une entrée
#     de character["quetes_actives"] satisfait TOUS les filtres fournis (chacun optionnel).
#     ⚠️ `objectif_atteint: false` = « la quête est encore À FAIRE ». Sans lui, une quête
#     ACCOMPLIE mais pas encore rapportée continue d'ouvrir la porte : le joueur peut rejouer
#     le donjon en boucle jusqu'à ce qu'il aille enfin rendre compte. C'est le filtre qui
#     ferme la boucle, et il doit être explicite (l'absence = comportement historique).
#   - item: {item, lieu_parent?} — miroir de recrutement.acces_autorise (carte
#     d'aventurier de guilde) : item_ref_id(ref) == item, et si lieu_parent est fourni,
#     item_ref_lieu(ref) == lieu_parent (porte verrouillée à clef).
#   - rang_min: {cite, rang} — le rang de guilde du perso dans CETTE cité
#     (character["rangs_guilde"][cite], absent ⇒ le premier de l'échelle) atteint au moins
#     `rang` sur l'échelle recrutement.RANGS. Une porte de prestige : le maître de guilde
#     ne reçoit pas les novices.
#
# ⚠️ FAIL-CLOSED : une clé de condition inconnue REFUSE l'accès (jamais un troisième
# comportement silencieux). Le garde-fou contre le contenu muet est le linter
# (utils/lint_dialogues.conditions_invalides), pas une permissivité du moteur.
#
# État persistant : character["laissez_passer"] = {lieu_id: {"pose_at", "par", "cycle"}}.
# Champ absent ⇒ aucun laissez-passer — aucune migration. Le laissez-passer mémorise
# le `cycle` qui l'a émis : si `lieu["acces"]["cycle"]` change (futur reset de donjon),
# il est périmé sans une ligne de code supplémentaire.

import time

from models import character_stats
from utils.characters import item_ref_id, item_ref_lieu
# L'échelle des rangs de guilde est lue à sa SOURCE (jamais recopiée : elle est passée de
# 7 à 8 crans une fois déjà). `utils.recrutement` la définit ; `utils.chasse` fait le même
# import — on ne passe pas par lui, qui tirerait zones + quetes dans ce module minimal.
from utils.recrutement import RANGS


def now_epoch() -> int:
	return int(time.time())

# Clés de condition reconnues par `conditions_remplies`. Toute autre clé fait échouer
# `conditions_invalides` (signalée par le linter) ET `conditions_remplies` (fail-closed).
CONDITIONS_CONNUES = {"quete_active", "item", "rang_min"}

# Sous-filtres reconnus par condition. ⚠️ Les valider AUSSI : une clé de premier niveau
# inconnue refuse (fail-closed, donc visible en jeu), mais un SOUS-filtre inconnu était
# simplement ignoré — donc PERMISSIF, donc invisible. Un `objectifatteint` mal orthographié
# rouvrirait la boucle du donjon sans que rien ne le signale. C'est le linter qui les attrape.
SOUS_FILTRES_CONNUS = {
	"quete_active": {"lieu", "types", "giver_categorie", "cible", "objectif_atteint"},
	"item": {"item", "lieu_parent"},
	"rang_min": {"cite", "rang"},
}


def gate_de(lieu_doc: dict) -> dict | None:
	"""Le bloc `acces` du lieu, ou None s'il est absent/vide."""
	acces = (lieu_doc or {}).get("acces")
	return acces if acces else None


def cycle_de(lieu_doc: dict) -> int:
	"""Cycle courant de la barrière (défaut 1 si le lieu n'en porte pas)."""
	return int((gate_de(lieu_doc) or {}).get("cycle", 1))


def conditions_invalides(lieu_doc: dict) -> list[str]:
	"""Clés de condition hors vocabulaire connu, pour le linter — CLÉS de premier niveau
	(que le moteur refuse déjà, fail-closed) **et** SOUS-FILTRES (que le moteur ignore
	silencieusement, donc bien plus dangereux : ils rendent la barrière plus permissive).
	Un sous-filtre fautif est rendu `quete_active.objectifatteint` pour être repérable."""
	gate = gate_de(lieu_doc)
	if not gate:
		return []
	invalides = []
	for condition in gate.get("conditions") or []:
		if not isinstance(condition, dict):
			continue
		for cle, filtre in condition.items():
			if cle not in CONDITIONS_CONNUES:
				if cle not in invalides:
					invalides.append(cle)
				continue
			connus = SOUS_FILTRES_CONNUS.get(cle, set())
			for sous in (filtre if isinstance(filtre, dict) else {}):
				if sous not in connus and f"{cle}.{sous}" not in invalides:
					invalides.append(f"{cle}.{sous}")
	return invalides


def _quete_satisfait(q: dict, filtre: dict, character: dict, get_doc_fn) -> bool:
	obj = q.get("objectif") or {}
	if "lieu" in filtre and obj.get("lieu") != filtre["lieu"]:
		return False
	if "cible" in filtre and obj.get("cible") != filtre["cible"]:
		return False
	if "types" in filtre and obj.get("type") not in (filtre.get("types") or []):
		return False
	if "giver_categorie" in filtre:
		giver_doc = get_doc_fn(q.get("giver")) if q.get("giver") else None
		if (giver_doc or {}).get("categorie") != filtre["giver_categorie"]:
			return False
	if "objectif_atteint" in filtre:
		# Import PARESSEUX : `utils.quetes` tire bois/expedition/recrutement/marche, et ce
		# module-ci est importé par `utils.lieux`, donc par le combat et la focalisation. On
		# ne recopie pas la règle pour autant (elle a déjà changé une fois) : on appelle le
		# prédicat d'origine. Même idiome que `quetes._focalisable`.
		from utils.quetes import objectif_atteint
		if bool(objectif_atteint(character, q)) != bool(filtre["objectif_atteint"]):
			return False
	return True


def _condition_quete_active(character: dict, filtre: dict, get_doc_fn) -> bool:
	actives = (character or {}).get("quetes_actives") or []
	return any(_quete_satisfait(q, filtre or {}, character, get_doc_fn) for q in actives)


def _condition_item(character: dict, filtre: dict) -> bool:
	item_id = (filtre or {}).get("item")
	if not item_id:
		return False
	lieu_parent = filtre.get("lieu_parent")
	for ref in (character or {}).get("inventaire", []):
		if item_ref_id(ref) != item_id:
			continue
		if lieu_parent and item_ref_lieu(ref) != lieu_parent:
			continue
		return True
	return False


def _condition_rang_min(character: dict, filtre: dict) -> bool:
	"""Le rang de guilde du perso DANS CETTE CITÉ atteint-il le seuil ? Rang courant absent
	⇒ le premier de l'échelle (miroir de `chasse.rang_de`). Un `cite`/`rang` manquant, ou un
	rang hors échelle (côté donnée comme côté perso), REFUSE — même esprit fail-closed que
	la clé inconnue : on n'ouvre pas une porte sur une comparaison qu'on ne sait pas faire."""
	cite = (filtre or {}).get("cite")
	seuil = (filtre or {}).get("rang")
	if not cite or not seuil or seuil not in RANGS:
		return False
	courant = ((character or {}).get("rangs_guilde") or {}).get(cite, RANGS[0])
	if courant not in RANGS:
		return False
	return RANGS.index(courant) >= RANGS.index(seuil)


def conditions_remplies(character: dict, lieu_doc: dict, get_doc_fn) -> tuple[bool, str]:
	"""Toutes les conditions du lieu sont-elles remplies (ET logique) ? (ok, raison du
	refus — le `refus` du lieu, ou un texte générique). Pas de barrière ⇒ (True, "")."""
	gate = gate_de(lieu_doc)
	if not gate:
		return True, ""
	for condition in gate.get("conditions") or []:
		if not isinstance(condition, dict) or len(condition) != 1:
			return False, gate.get("refus", "L'accès vous est refusé.")
		(cle, filtre), = condition.items()
		if cle == "quete_active":
			ok = _condition_quete_active(character, filtre or {}, get_doc_fn)
		elif cle == "item":
			ok = _condition_item(character, filtre or {})
		elif cle == "rang_min":
			ok = _condition_rang_min(character, filtre or {})
		else:
			# Fail-closed : une clé inconnue refuse toujours (typo ≠ porte ouverte).
			ok = False
		if not ok:
			return False, gate.get("refus", "L'accès vous est refusé.")
	return True, ""


def laissez_passer_valide(character: dict, lieu_doc: dict) -> bool:
	"""Un laissez-passer posé pour ce lieu, ET émis pour le cycle courant."""
	lieu_id = (lieu_doc or {}).get("_id")
	if not lieu_id:
		return False
	entree = ((character or {}).get("laissez_passer") or {}).get(lieu_id)
	if not entree:
		return False
	return int(entree.get("cycle", -1)) == cycle_de(lieu_doc)


def poser_laissez_passer(character: dict, lieu_doc: dict, pnj_id: str) -> dict:
	"""Pose le laissez-passer de CE lieu (mute `character["laissez_passer"]`, ne
	sauve pas). Renvoie l'entrée posée."""
	lieu_id = (lieu_doc or {}).get("_id")
	entree = {"pose_at": now_epoch(), "par": pnj_id, "cycle": cycle_de(lieu_doc)}
	laissez_passer = character.setdefault("laissez_passer", {})
	laissez_passer[lieu_id] = entree
	return entree


def revoquer(character: dict, lieu_id: str) -> bool:
	"""Retire le laissez-passer de ce lieu (mute, ne sauve pas). Appelé par le futur
	reset de donjon. Renvoie True si quelque chose a été retiré."""
	laissez_passer = (character or {}).get("laissez_passer") or {}
	if lieu_id in laissez_passer:
		del laissez_passer[lieu_id]
		return True
	return False


def acces_autorise(character: dict, lieu_doc: dict, get_doc_fn) -> tuple[bool, str]:
	"""CHOKEPOINT unique. Ordre : kill-switch → pas de barrière → laissez-passer valide
	→ conditions. (ok, raison) — la raison est le texte à remonter au joueur (403)."""
	if not character_stats.ACCES_GARDIEN_ACTIF:
		return True, ""
	gate = gate_de(lieu_doc)
	if not gate:
		return True, ""
	if laissez_passer_valide(character, lieu_doc):
		return True, ""
	return conditions_remplies(character, lieu_doc, get_doc_fn)
