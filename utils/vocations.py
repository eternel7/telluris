# utils/vocations.py
# CHANGEMENT DE VOCATION (pur, DB injectée par l'appelant : docs passés en argument, rien n'est
# lu ni sauvé ici ; `appliquer_changement` MUTE sans sauver).
#
# Règles (Auteur, 11/11/2026) :
# - Vers une vocation NOUVELLE : seulement par un arc de `rules:vocations_transitions`
#   (`{id: [ids accessibles]}`, repris de la page d'accueil), au prix
#   round(BASE × FACTEUR^(n + k)) — n = niveau de la vocation QUITTÉE, k = vocations déjà
#   pratiquées hors la courante (on paie le papillonnage, pas seulement la profondeur).
# - Vers une vocation déjà CONNUE (clé de `vocations_niveaux`) : LIBRE, graphe ou non, au prix
#   min(RETOUR, prix d'un changement neuf) — jamais plus cher que de partir ailleurs.
# - On ne perd RIEN : sorts, compétences (elles s'empilent), niveaux de chaque vocation
#   (`vocations_niveaux`, gardé par vocation). Seul l'APPRENTISSAGE suit la vocation courante
#   (`sorts.niveau_ecole`, `competences.competences_apprenables`). Ni équipement de base, ni
#   sort / compétence gratuits : ils n'appartiennent qu'à la création.
# - On (re)devient aspirant : la nouvelle vocation commence au niveau 0.
# - Compagnon recruté : le portrait reste (c'est une personne), la `specialite` suit.

import math

from models import character_stats

TRANSITIONS_DOC_ID = "rules:vocations_transitions"


def _entrees(rules_vocations) -> list:
	"""Entrées de `rules:vocations` (doc complet OU sa `value`)."""
	if isinstance(rules_vocations, dict):
		return rules_vocations.get("value") or []
	return rules_vocations or []


def _valeur(rules_transitions) -> dict:
	"""{id: [ids]} de `rules:vocations_transitions` (doc complet OU sa `value`)."""
	if isinstance(rules_transitions, dict) and "value" in rules_transitions:
		return rules_transitions.get("value") or {}
	return rules_transitions or {}


def transitions_de(voc, rules_transitions) -> list:
	"""Vocations NOUVELLES accessibles depuis `voc` (ordre de la donnée)."""
	return [str(v) for v in (_valeur(rules_transitions).get(str(voc or "")) or [])]


def _niveaux(character: dict) -> dict:
	return (character or {}).get("vocations_niveaux") or {}


def niveau_courant(character: dict) -> int:
	return int(_niveaux(character).get((character or {}).get("voc", ""), 0) or 0)


def nb_autres_pratiquees(character: dict) -> int:
	"""k : vocations déjà pratiquées, la courante exclue."""
	voc = (character or {}).get("voc", "")
	return len([v for v in _niveaux(character) if v != voc])


def cout_nouvelle(character: dict) -> int:
	"""Prix d'un changement vers une vocation NOUVELLE (arrondi au plus proche, ½ vers le haut)."""
	exposant = niveau_courant(character) + nb_autres_pratiquees(character)
	brut = character_stats.VOC_CHANGEMENT_BASE * character_stats.VOC_CHANGEMENT_FACTEUR ** exposant
	return int(math.floor(brut + 0.5))


def cout_retour(character: dict) -> int:
	"""Prix d'un retour vers une vocation déjà connue : jamais plus cher qu'un départ neuf."""
	return min(int(character_stats.VOC_RETOUR_COUT), cout_nouvelle(character))


def options(character: dict, rules_vocations, rules_transitions) -> list:
	"""Vocations accessibles depuis la vocation courante, CONNUES d'abord puis NOUVELLES, chacune
	dans l'ordre de `rules:vocations` : `{id, label, icon, blurb, magie, connue, niveau, cout}`.
	`niveau` = niveau déjà acquis (0 pour une nouvelle)."""
	voc = (character or {}).get("voc", "")
	niveaux = _niveaux(character)
	nouvelles = set(transitions_de(voc, rules_transitions))
	prix_nouvelle, prix_retour = cout_nouvelle(character), cout_retour(character)
	connues, neuves = [], []
	for e in _entrees(rules_vocations):
		vid = str((e or {}).get("id") or "")
		if not vid or vid == voc:
			continue
		connue = vid in niveaux
		if not connue and vid not in nouvelles:
			continue
		entree = {
			"id": vid, "label": e.get("label") or vid, "icon": e.get("icon") or "",
			"blurb": e.get("blurb") or "", "magie": e.get("magie") or "",
			"connue": connue, "niveau": int(niveaux.get(vid, 0) or 0),
			"cout": prix_retour if connue else prix_nouvelle,
		}
		(connues if connue else neuves).append(entree)
	return connues + neuves


def refus(character: dict, cible, rules_vocations, rules_transitions) -> tuple | None:
	"""Motif `(code_http, message)` d'un refus, ou None si le changement est permis."""
	cible = str(cible or "")
	if cible == (character or {}).get("voc", ""):
		return 422, "C'est déjà votre vocation"
	choix = next((o for o in options(character, rules_vocations, rules_transitions)
				  if o["id"] == cible), None)
	if choix is None:
		return 422, "Cette vocation n'est pas accessible depuis la vôtre"
	points = int((character or {}).get("attribute_points", 0) or 0)
	if points < choix["cout"]:
		return 422, f"Points insuffisants (besoin {choix['cout']}, disponible {points})"
	return None


def appliquer_changement(character: dict, cible, rules_vocations, rules_transitions) -> dict:
	"""Change la vocation (refus vérifié par l'appelant) : MUTE `voc`, `vocations_niveaux`,
	`attribute_points` (+ `specialite` d'un compagnon recruté), NE SAUVE PAS.
	Rend `{de, vers, retour, cout, niveau}`."""
	choix = next(o for o in options(character, rules_vocations, rules_transitions)
				 if o["id"] == str(cible))
	de = character.get("voc", "")
	niveaux = dict(_niveaux(character))
	niveaux.setdefault(de, 0)          # l'ancienne reste comptée, même jamais montée
	niveaux.setdefault(choix["id"], 0)
	character["vocations_niveaux"] = niveaux
	character["voc"] = choix["id"]
	character["attribute_points"] = int(character.get("attribute_points", 0) or 0) - choix["cout"]
	# Compagnon recruté : sa spécialité affichée suit la vocation (le portrait, lui, reste).
	if character.get("type") == "aventurier" and "specialite" in character:
		character["specialite"] = choix["blurb"]
	return {"de": de, "vers": choix["id"], "retour": choix["connue"], "cout": choix["cout"],
			"niveau": choix["niveau"]}
