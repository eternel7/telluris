"""Catalogues d'administration des sorts (par école) et des compétences (par vocation).

Pur : les docs bruts et `rules:vocations` sont INJECTÉS, rien n'est lu en base ici.
Chaque entrée porte les champs que le rendu de l'onglet ⚡ de /play lit sur une
capacité CONNUE (`sorts.liste_sorts_payload` / `competences.liste_competences_payload`)
— le texte affiché par /admin/sorts et /admin/competences sort des MÊMES fonctions
client (`templates/scripts/capacites_texte.js`) — plus le doc brut, pour l'éditeur JSON.

⚠️ Aucun personnage ici : une formule à caractéristiques (`1D{Int/5}`) n'a pas de
valeur. Les effets sont résolus sur les caracts INDICATIVES (toutes à 100) pour que leur
présence et leur signe soient justes, et le client, en mode `CAPA_FORMULES_SEULES`,
affiche la formule seule. Portée / incantation / entretien formulés : la FORMULE
remplace la valeur.
"""

from utils import sorts
from utils import competences

SANS_ECOLE = "(sans école)"
SANS_VOCATION = "(sans vocation)"


def _temps(vue: dict, cle: str):
	"""Valeur d'un champ de temps (`maintien`, `incantation`) : sa formule si elle en a une."""
	return vue.get(f"{cle}_formule") or vue.get(cle)


def _portee(vue: dict):
	return vue.get("portee_formule") or vue.get("portee")


def _apercu(effets: dict) -> dict:
	return sorts.apercu_effets(effets or {}, sorts._CARACTS_INDICATIVES)


def entree_sort(doc: dict, items: dict, rules_vocations) -> dict:
	"""Entrée de catalogue d'un doc `sort:*`. `items` = {item_id: {nom, icon}} pour les
	composants. Un doc que `normaliser_sort` refuse reste listé (`invalide`) : c'est
	justement celui qu'on vient corriger."""
	ecole = sorts.magie_de_sort(doc, rules_vocations) or SANS_ECOLE
	base = {"id": doc.get("_id", ""), "ecole": ecole, "doc": doc}
	vue = sorts.normaliser_sort(doc)
	if vue is None:
		return {**base, "invalide": True, "nom": doc.get("nom") or doc.get("_id", ""),
				"icon": doc.get("icon") or "🔮", "description": doc.get("description", ""),
				"niveau": sorts._as_int(doc.get("niveau")), "cout_pm": doc.get("cout_pm", 0),
				"effets": {}, "composants": []}
	return {
		**base,
		"sort_id": vue["id"],
		"nom": vue["nom"],
		"icon": vue["icon"],
		"description": vue["description"],
		"niveau": vue["niveau"],
		"famille": vue.get("famille") or "",
		"cout_pm": vue["cout_pm"],
		"incantation": _temps(vue, "incantation"),
		"maintien": _temps(vue, "maintien"),
		"cible": vue["cible"],
		"jet": vue["jet"],
		"portee": _portee(vue),
		"zone": vue["zone"],
		"effets": _apercu(vue["effets"]),
		"invocation": vue["invocation"],
		"sensibilite_charge": vue["sensibilite_charge"],
		"composants": [{
			"item": c["item"],
			"nom": (items.get(c["item"]) or {}).get("nom", c["item"]),
			"icon": (items.get(c["item"]) or {}).get("icon", "❔"),
			"consomme": c["consomme"],
			"bonus": _apercu(c["bonus"]),
			# Aucun porteur : un composant n'est jamais grisé ici.
			"disponible": True,
		} for c in vue["composants"]],
	}


def entree_competence(doc: dict) -> dict:
	"""Entrée de catalogue d'un doc `competence:*` (même contrat que `entree_sort`)."""
	base = {"id": doc.get("_id", ""), "vocation": doc.get("vocation") or SANS_VOCATION, "doc": doc}
	vue = competences.normaliser_competence(doc)
	if vue is None:
		return {**base, "invalide": True, "nom": doc.get("nom") or doc.get("_id", ""),
				"icon": doc.get("icon") or "⚡", "description": doc.get("description", ""),
				"niveau": sorts._as_int(doc.get("niveau")), "mode": doc.get("mode") or "",
				"cout_pm": doc.get("cout_pm", 0), "effets": {}}
	return {
		**base,
		"competence_id": vue["id"],
		"nom": vue["nom"],
		"icon": vue["icon"],
		"description": vue["description"],
		"niveau": vue["niveau"],
		"famille": vue.get("famille") or "",
		"mode": vue["mode"],
		"action_piege": competences.action_piege(vue),
		"cout_pm": vue["cout_pm"],
		"maintien": _temps(vue, "maintien"),
		"incantation": _temps(vue, "incantation"),
		"cible": vue["cible"],
		"jet": vue["jet"],
		"portee": _portee(vue),
		"zone": vue["zone"],
		"effets": _apercu(vue["effets"]),
		"sensibilite_charge": vue["sensibilite_charge"],
	}


def _vocations(rules_vocations) -> list:
	return [v for v in sorts._vocations_entries(rules_vocations) if (v or {}).get("id")]


def catalogue_sorts(docs: list, items: dict, rules_vocations) -> dict:
	"""`{"groupes": [{cle, label, icon, entrees}]}` — une école par groupe, triées par nom ;
	`(sans école)` en dernier."""
	par_ecole = {}
	for doc in docs or []:
		if (doc or {}).get("type") != "sort":
			continue
		e = entree_sort(doc, items, rules_vocations)
		par_ecole.setdefault(e["ecole"], []).append(e)
	# Vocations qui pratiquent chaque école : le contexte que l'admin cherche en ouvrant une école.
	pratiquee = {}
	for v in _vocations(rules_vocations):
		if v.get("magie"):
			pratiquee.setdefault(str(v["magie"]).strip(), []).append(v.get("label") or v["id"])
	cles = sorted(par_ecole, key=lambda k: (k == SANS_ECOLE, k.lower()))
	return {"groupes": [{
		"cle": k, "label": k, "icon": "✨",
		"detail": ", ".join(pratiquee.get(k, [])),
		"entrees": par_ecole[k],
	} for k in cles]}


def catalogue_competences(docs: list, rules_vocations) -> dict:
	"""`{"groupes": [...]}` — une vocation par groupe, dans l'ordre de `rules:vocations`
	(libellé et icône de la vocation), les vocations inconnues ensuite."""
	par_voc = {}
	for doc in docs or []:
		if (doc or {}).get("type") != "competence":
			continue
		e = entree_competence(doc)
		par_voc.setdefault(e["vocation"], []).append(e)
	connues = {v["id"]: v for v in _vocations(rules_vocations)}
	ordre = [v["id"] for v in _vocations(rules_vocations) if v["id"] in par_voc]
	ordre += sorted((k for k in par_voc if k not in connues), key=lambda k: (k == SANS_VOCATION, k))
	return {"groupes": [{
		"cle": k,
		"label": (connues.get(k) or {}).get("label") or k,
		"icon": (connues.get(k) or {}).get("icon") or "⚡",
		"detail": (connues.get(k) or {}).get("magie") or "",
		"entrees": par_voc[k],
	} for k in ordre]}


def items_composants(docs: list) -> list:
	"""Ids d'items cités comme composants par des docs `sort:*` (pour une lecture groupée)."""
	ids = set()
	for doc in docs or []:
		for c in (doc or {}).get("composants") or []:
			if (c or {}).get("item"):
				ids.add(str(c["item"]))
	return sorted(ids)
