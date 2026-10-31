# utils/derniers_joues.py
# /admin/personnages-recents (pur) : les derniers personnages joués et leur emplacement.
# `dernier_jeu` est posé par `characters.marquer_joue`. Champ absent (personnage qui n'a pas
# rejoué depuis l'arrivée du suivi) : date inconnue, classé après les autres sans être daté.

from models.character_stats import compute_character_level
from utils.characters import lieu_label
from utils.traversee import en_mer


def _date_de(personnage: dict) -> int | None:
	date = personnage.get("dernier_jeu")
	return date if isinstance(date, int) else None


def _nom_complet(personnage: dict) -> str:
	return " ".join(p for p in (personnage.get("prenom"), personnage.get("nom")) if p)


def _chemin_du_lieu(lieu_id: str, get_doc) -> tuple[str, list[str]]:
	"""(label du lieu, labels de ses parents du plus proche au plus lointain). Lieu absent de
	la base : son id brut, pour que l'admin voie la référence cassée."""
	doc = get_doc(lieu_id) if lieu_id else None
	if not doc:
		return lieu_id or "—", []
	parents = []
	vus = {lieu_id}
	parent_id = doc.get("lieu_parent")
	while parent_id and parent_id not in vus:
		vus.add(parent_id)
		parent = get_doc(parent_id)
		if not parent:
			break
		parents.append(lieu_label(parent, parent_id))
		parent_id = parent.get("lieu_parent")
	return lieu_label(doc, lieu_id), parents


def derniers_joues(personnages: list[dict], get_doc, combats_actifs: list[dict], n: int = 10) -> list[dict]:
	"""Les `n` derniers personnages joués, du plus récent au plus ancien, complétés au besoin
	par ceux dont la date est inconnue (ordre alphabétique : rien ne permet de les classer)."""
	dates = sorted(
		(p for p in personnages if _date_de(p) is not None),
		key=_date_de, reverse=True)
	sans_date = sorted(
		(p for p in personnages if _date_de(p) is None),
		key=lambda p: _nom_complet(p).casefold())
	en_combat = {c.get("character_id") for c in combats_actifs}

	lignes = []
	for p in (dates + sans_date)[:n]:
		lieu_id = p.get("lieu") or ""
		label, parents = _chemin_du_lieu(lieu_id, get_doc)
		position = p.get("position") or {}
		lignes.append({
			"id": p.get("_id"),
			"nom": _nom_complet(p),
			"race": p.get("race") or "",
			"voc": p.get("voc") or "",
			"niveau": compute_character_level(p.get("xp_total", 0)),
			"dernier_jeu": _date_de(p),
			"lieu_id": lieu_id,
			"lieu_label": label,
			"parents": parents,
			"x": position.get("x"),
			"y": position.get("y"),
			"en_combat": p.get("_id") in en_combat,
			"en_mer": en_mer(p),
		})
	return lignes
