"""Pouvoirs accordés par un objet PORTÉ (pur) — `docs/conception_trophees_legendaires.md` § 5.

Champ item `competences` : liste d'ids de sorts ou de compétences EXISTANTS
(`"sort:souffle_de_feu"`) ou d'entrées `{"id": …, "restriction": {caract: min}}`.

- Actif **tant que l'objet est équipé** (un slot de `character["slots"]`) : rien n'est
  appris, rien n'est écrit sur le personnage. Déséquiper l'objet retire le pouvoir ; sa case
  de barre reste stockée et revient au rééquipement (`slots_actions._entree_possedee`).
- **Hors vocation** : aucune vérification de vocation ni d'école, coûts normaux.
- **Exigence** : la `restriction` de l'entrée, lue sur `caracteristiques_current` BRUT
  (convention 3 : un buff n'éveille jamais un pouvoir).
"""

from utils.characters import item_ref_id, restriction_satisfaite

PREFIXES = ("sort:", "competence:")


def _entrees(item_doc: dict) -> list:
	out = []
	for brut in (item_doc or {}).get("competences") or []:
		if isinstance(brut, str):
			entree = {"id": brut, "restriction": None}
		elif isinstance(brut, dict) and isinstance(brut.get("id"), str):
			entree = {"id": brut["id"], "restriction": brut.get("restriction")}
		else:
			continue
		if entree["id"].startswith(PREFIXES):
			out.append(entree)
	return out


def pouvoirs_objets(character: dict, get_doc) -> list:
	"""Une ligne par pouvoir d'objet équipé, dans l'ordre des slots :
	`{id, item_id, item_nom, actif, manque}`. Un objet tenu à deux mains (même ref dans deux
	slots) ne compte qu'une fois ; un même pouvoir offert par deux objets aussi (le premier
	actif l'emporte)."""
	character = character or {}
	caracs = character.get("caracteristiques_current") or {}
	vus_items, lignes = set(), {}
	for ref in (character.get("slots") or {}).values():
		if not ref:
			continue
		item_id = item_ref_id(ref)
		if not item_id or item_id in vus_items:
			continue
		vus_items.add(item_id)
		doc = get_doc(item_id) or {}
		for entree in _entrees(doc):
			ok, manque = restriction_satisfaite(entree["restriction"], caracs)
			ligne = {"id": entree["id"], "item_id": item_id, "item_nom": doc.get("nom") or item_id,
					 "actif": ok, "manque": manque}
			ancienne = lignes.get(entree["id"])
			if ancienne is None or (ok and not ancienne["actif"]):
				lignes[entree["id"]] = ligne
	return list(lignes.values())


def accordes(character: dict, get_doc, prefixe: str | None = None) -> dict:
	"""`{id: nom de l'objet}` des pouvoirs ACTIFS (filtrés sur `prefixe` si donné)."""
	return {l["id"]: l["item_nom"] for l in pouvoirs_objets(character, get_doc)
			if l["actif"] and (prefixe is None or l["id"].startswith(prefixe))}


def connait(character: dict, capacite_id: str, get_doc) -> bool:
	"""Le personnage peut-il se servir de ce sort / cette compétence : appris OU accordé par un
	objet porté. Source unique des contrôles d'appartenance (routes de lancement, barre)."""
	character = character or {}
	champ = "sorts_connus" if str(capacite_id).startswith("sort:") else "competences_connues"
	if capacite_id in (character.get(champ) or []):
		return True
	return capacite_id in accordes(character, get_doc)
