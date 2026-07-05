# utils/intro.py
# Événement narratif d'introduction : le personnage a fui son village natal et doit
# rejoindre la sécurité de sa cité de départ. Les éléments de personnalisation vivent
# sur le doc lieu de la cité, bloc `intro` :
#   {titre, texte, texte_conclusion, xp_conclusion, position_depart:{x,y},
#    zone_securite:"zone::coeur_ville", raisons:[{id, label, texte_suite}]}
# État sur le personnage : character["intro"] = {"statut":"en_cours"|"terminee",
# "raison": "<id>"?}. Clé absente (perso ancien / cité sans bloc intro) = aucun
# comportement — rétro-compat par .get. La raison choisie sert aux dialogues PNJ
# (condition {"intro_raison": id} dans utils/pnj.py).
#
# Logique pure, mute sans save — les appelants (add_character, move_character,
# POST /api/intro/raison) persistent.

from utils.zones import est_dans_zone


def intro_en_cours(character: dict) -> bool:
	return ((character or {}).get("intro") or {}).get("statut") == "en_cours"


def demarrer(character_dict: dict, lieu_doc: dict) -> None:
	"""Démarre l'intro à la création du personnage si sa cité porte un bloc `intro` :
	spawn à `position_depart` (repli default_position déjà posée) + statut en_cours.
	Mute le dict AVANT le premier save (appelé par add_character). Sans bloc → no-op."""
	bloc = (lieu_doc or {}).get("intro")
	if not bloc:
		return
	depart = bloc.get("position_depart")
	if isinstance(depart, dict) and "x" in depart and "y" in depart:
		character_dict["position"] = {"x": int(depart["x"]), "y": int(depart["y"])}
	character_dict["intro"] = {"statut": "en_cours"}


def _substituer(texte: str, character: dict) -> str:
	"""Placeholders {prenom} / {nom} / {race} dans les textes d'intro."""
	if not texte:
		return ""
	for cle in ("prenom", "nom", "race"):
		texte = texte.replace("{" + cle + "}", str((character or {}).get(cle, "")))
	return texte


def payload_overlay(character: dict, lieu_doc: dict) -> dict | None:
	"""Payload de l'overlay narratif au rendu /play. None si : pas d'intro en cours,
	raison déjà choisie (l'overlay ne revient pas), personnage hors de sa cité, ou
	cité sans bloc intro (donnée retirée depuis la création)."""
	if not intro_en_cours(character):
		return None
	if character.get("intro", {}).get("raison"):
		return None
	if (lieu_doc or {}).get("_id") != character.get("cite"):
		return None
	bloc = lieu_doc.get("intro")
	if not bloc:
		return None
	return {
		"titre": _substituer(bloc.get("titre", ""), character),
		"texte": _substituer(bloc.get("texte", ""), character),
		"raisons": [
			{"id": r["id"], "label": r.get("label", r["id"])}
			for r in bloc.get("raisons") or [] if r.get("id")
		],
	}


def raison_valide(lieu_doc: dict, raison_id: str) -> dict | None:
	"""L'entrée raison du bloc intro de la cité si `raison_id` existe, None sinon."""
	if not raison_id:
		return None
	bloc = (lieu_doc or {}).get("intro") or {}
	for r in bloc.get("raisons") or []:
		if r.get("id") == raison_id:
			return r
	return None


def conclure_si_en_securite(character: dict, lieu_doc: dict) -> dict | None:
	"""Conclut l'intro si le personnage vient d'atteindre la zone de sécurité de SA cité
	(mute le statut, NE SAUVEGARDE PAS — appelé par move_character avant son save).
	`zone_securite` absente/introuvable = conclusion au premier déplacement dans la cité
	(mode dégradé explicite). Renvoie {titre, texte, xp} ou None."""
	if not intro_en_cours(character):
		return None
	if (lieu_doc or {}).get("_id") != character.get("cite"):
		return None
	bloc = lieu_doc.get("intro") or {}
	zone_id = bloc.get("zone_securite")
	if zone_id:
		pos = character.get("position") or {}
		if not est_dans_zone(pos.get("x", 0), pos.get("y", 0), zone_id,
				lieu_doc.get("zone_influences") or []):
			return None
	character["intro"]["statut"] = "terminee"
	return {
		"titre": _substituer(bloc.get("titre", ""), character),
		"texte": _substituer(bloc.get("texte_conclusion", ""), character),
		"xp": max(0, int(bloc.get("xp_conclusion", 0) or 0)),
	}
