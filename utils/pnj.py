# utils/pnj.py
# PNJ de lieu avec dialogues à choix + services. Un doc `lieu:*` porte un champ `pnj`
# (liste d'entrées {character:"pnj:xxx", portrait, image?, probabilite, description}) ;
# le tirage de présence se fait à l'ENTRÉE dans le lieu et est persisté en champ
# transitoire character["pnj_present"] = {"lieu": id, "character": id|None} — un refresh
# ne re-tire jamais (character:None = « tirage fait, PNJ absent »).
#
# Le doc PNJ (`type:"pnj"`) porte :
# - `dialogue` : {"noeud_depart": id, "noeuds": {id: {texte, texte_gratuit?, choix:[...]}}}
#   Chaque choix = {id, label, next?, action:{"service":"soin"}?, condition?}. Les choix
#   sont FILTRÉS côté serveur par condition (le client n'adresse que des choix visibles,
#   par `choix_id`). Conditions v1 : {"relation_min": {"lieux":[...], "seuil": n}} (OU
#   logique sur les lieux) et {"intro_raison": "<id>"}.
# - `services.soin` : {cout_cuivre, fraction_pv, gratuit_si:{lieux, seuil, fraction_pv},
#   noeuds:{fait, sans_fonds, inutile}} — data-driven, seuil par défaut en world-var
#   PNJ_REPUTATION_SEUIL.
# - `services.don` : {item, quantite, cout_cuivre, gratuit_si:{lieux, seuil},
#   noeuds:{fait, sans_fonds, trop_charge}} — remise d'un objet (ex. eau bénite),
#   gratuit si bonne réputation ; contrôle de charge côté router.
# Placeholders substitués serveur dans texte/label : {prenom}, {cout}.
#
# Logique pure (DB injectée : relation_value_fn), mute sans save — l'endpoint persiste.

import random

from models import character_stats


# ---------------------------------------------------------------------------
# Présence dans le lieu
# ---------------------------------------------------------------------------

def tirer_pnj_present(lieu_doc: dict, rand_fn=random.random) -> str | None:
	"""Tire le PNJ présent parmi les entrées `pnj` du lieu : la première entrée dont
	`rand_fn() < probabilite` gagne (ordre de la liste = priorité). None si aucun."""
	for entree in (lieu_doc or {}).get("pnj") or []:
		pnj_id = entree.get("character")
		if not pnj_id:
			continue
		try:
			proba = float(entree.get("probabilite", 1.0))
		except (TypeError, ValueError):
			proba = 1.0
		if rand_fn() < proba:
			return pnj_id
	return None


def poser_pnj_present(character: dict, lieu_doc: dict, rand_fn=random.random) -> bool:
	"""Pose le champ transitoire `pnj_present` si le personnage vient d'entrer dans ce
	lieu (mute sans save). No-op si le tirage a déjà été fait pour ce lieu (refresh
	stable). Renvoie True si le champ a changé (l'appelant décide de sauvegarder)."""
	lieu_id = (lieu_doc or {}).get("_id")
	if not lieu_id:
		return False
	present = character.get("pnj_present") or {}
	if present.get("lieu") == lieu_id:
		return False
	character["pnj_present"] = {
		"lieu": lieu_id,
		"character": tirer_pnj_present(lieu_doc, rand_fn),
	}
	return True


def entree_pnj_active(character: dict, lieu_doc: dict) -> dict | None:
	"""L'entrée `pnj` du lieu correspondant au tirage persisté, ou None (tirage périmé,
	PNJ absent, lieu sans pnj, entrée retirée de la donnée depuis le tirage)."""
	present = (character or {}).get("pnj_present") or {}
	lieu_id = (lieu_doc or {}).get("_id")
	pnj_id = present.get("character")
	if not lieu_id or present.get("lieu") != lieu_id or not pnj_id:
		return None
	for entree in lieu_doc.get("pnj") or []:
		if entree.get("character") == pnj_id:
			return entree
	return None


def pnj_payload(entree: dict, pnj_doc: dict) -> dict:
	"""Payload de rendu du PNJ présent (template /play + panneau de dialogue).
	Portrait/description : l'entrée du lieu prime (ambiance par lieu), repli doc PNJ."""
	return {
		"character": (pnj_doc or {}).get("_id") or entree.get("character"),
		"nom": (pnj_doc or {}).get("nom", "???"),
		"portrait": entree.get("portrait") or (pnj_doc or {}).get("portrait"),
		"image_lieu": entree.get("image"),
		"description": entree.get("description") or (pnj_doc or {}).get("description", ""),
	}


# ---------------------------------------------------------------------------
# Contexte & conditions de dialogue
# ---------------------------------------------------------------------------

def _lieux_cites(pnj_doc: dict) -> set:
	"""Tous les lieux référencés par les conditions de l'arbre + gratuit_si des services
	(pour ne résoudre que les relations utiles)."""
	lieux = set()
	for service in ((pnj_doc or {}).get("services") or {}).values():
		for lid in ((service or {}).get("gratuit_si") or {}).get("lieux") or []:
			lieux.add(lid)
	noeuds = (((pnj_doc or {}).get("dialogue") or {}).get("noeuds") or {})
	for noeud in noeuds.values():
		for choix in (noeud or {}).get("choix") or []:
			cond = (choix or {}).get("condition") or {}
			for lid in (cond.get("relation_min") or {}).get("lieux") or []:
				lieux.add(lid)
	return lieux


def contexte_dialogue(character: dict, pnj_doc: dict, relation_value_fn) -> dict:
	"""Contexte d'évaluation des conditions : relations du personnage avec les lieux
	cités par l'arbre/les services (`relation_value_fn(lieu_id) -> int`, injectée par le
	router) + raison d'intro éventuelle. Ajoute aussi `prenom` pour les placeholders."""
	relations = {}
	for lid in _lieux_cites(pnj_doc):
		try:
			relations[lid] = int(relation_value_fn(lid))
		except (TypeError, ValueError):
			relations[lid] = 0
	return {
		"relations": relations,
		"intro_raison": ((character or {}).get("intro") or {}).get("raison"),
		"prenom": (character or {}).get("prenom", ""),
	}


def condition_ok(condition: dict | None, contexte: dict) -> bool:
	"""Évalue une condition de choix. Sans condition → True. `relation_min` = OU logique
	sur les lieux (une relation ≥ seuil suffit) ; `intro_raison` = égalité stricte."""
	if not condition:
		return True
	rel_min = condition.get("relation_min")
	if rel_min:
		seuil = int(rel_min.get("seuil", character_stats.PNJ_REPUTATION_SEUIL))
		relations = contexte.get("relations") or {}
		if not any(relations.get(lid, 0) >= seuil for lid in rel_min.get("lieux") or []):
			return False
	if "intro_raison" in condition:
		if contexte.get("intro_raison") != condition["intro_raison"]:
			return False
	return True


# ---------------------------------------------------------------------------
# Navigation de l'arbre
# ---------------------------------------------------------------------------

def _substituer(texte: str, contexte: dict, soin: dict | None) -> str:
	"""Placeholders {prenom} / {cout} (coût effectif du soin, « gratuit » si offert)."""
	if not texte:
		return ""
	texte = texte.replace("{prenom}", str(contexte.get("prenom", "")))
	if "{cout}" in texte:
		if soin and not soin.get("gratuit") and soin.get("cout_cuivre", 0) > 0:
			cout = f"{soin['cout_cuivre']} cuivre"
		else:
			cout = "gratuit"
		texte = texte.replace("{cout}", cout)
	return texte


def noeud_client(pnj_doc: dict, noeud_id: str, contexte: dict, soin: dict | None = None) -> dict | None:
	"""Nœud prêt à afficher : texte (variante `texte_gratuit` si le soin est offert),
	placeholders substitués, choix filtrés par condition (id + label + marqueur action
	booléen — jamais l'arbre entier ni les conditions). None si le nœud n'existe pas."""
	noeuds = (((pnj_doc or {}).get("dialogue") or {}).get("noeuds") or {})
	noeud = noeuds.get(noeud_id)
	if not noeud:
		return None
	texte = noeud.get("texte", "")
	if soin and soin.get("gratuit") and noeud.get("texte_gratuit"):
		texte = noeud["texte_gratuit"]
	choix_visibles = []
	for choix in noeud.get("choix") or []:
		if not choix.get("id") or not condition_ok(choix.get("condition"), contexte):
			continue
		choix_visibles.append({
			"id": choix["id"],
			"label": _substituer(choix.get("label", ""), contexte, soin),
			"action": bool(choix.get("action")),
		})
	return {
		"id": noeud_id,
		"texte": _substituer(texte, contexte, soin),
		"choix": choix_visibles,
	}


def choix_valide(pnj_doc: dict, noeud_id: str, choix_id: str, contexte: dict) -> dict | None:
	"""Le choix demandé s'il existe dans ce nœud ET que sa condition passe (revalidation
	serveur — le client ne fait pas foi). None sinon (422 côté router)."""
	noeuds = (((pnj_doc or {}).get("dialogue") or {}).get("noeuds") or {})
	noeud = noeuds.get(noeud_id)
	if not noeud:
		return None
	for choix in noeud.get("choix") or []:
		if choix.get("id") == choix_id:
			return choix if condition_ok(choix.get("condition"), contexte) else None
	return None


# ---------------------------------------------------------------------------
# Service de soin
# ---------------------------------------------------------------------------

def soin_effectif(pnj_doc: dict, contexte: dict) -> dict | None:
	"""Paramètres effectifs du soin pour CE personnage : gratuit et plus efficace si
	l'une des relations de `gratuit_si.lieux` atteint le seuil (défaut world-var
	PNJ_REPUTATION_SEUIL). None si le PNJ n'offre pas ce service."""
	service = (((pnj_doc or {}).get("services") or {}).get("soin"))
	if not service:
		return None
	gratuit_si = service.get("gratuit_si") or {}
	seuil = int(gratuit_si.get("seuil", character_stats.PNJ_REPUTATION_SEUIL))
	relations = contexte.get("relations") or {}
	gratuit = any(relations.get(lid, 0) >= seuil for lid in gratuit_si.get("lieux") or [])
	if gratuit:
		fraction = float(gratuit_si.get("fraction_pv", 1.0))
		cout = 0
	else:
		fraction = float(service.get("fraction_pv", 0.5))
		cout = max(0, int(service.get("cout_cuivre", 0)))
	return {"cout_cuivre": cout, "fraction_pv": fraction, "gratuit": gratuit}


def appliquer_soin(character: dict, pv_max: int, fraction: float) -> int:
	"""Rend `fraction × pv_max` PV, clampé au max (mute currentPV, NE SAUVEGARDE PAS).
	Renvoie les PV effectivement rendus."""
	avant = int(character.get("currentPV", pv_max) or 0)
	rendu = max(0, round(int(pv_max) * float(fraction)))
	character["currentPV"] = min(int(pv_max), avant + rendu)
	return character["currentPV"] - avant


# ---------------------------------------------------------------------------
# Service de don (remise d'un objet — ex. eau bénite du temple)
# ---------------------------------------------------------------------------

def don_effectif(pnj_doc: dict, contexte: dict) -> dict | None:
	"""Paramètres effectifs du service `don` pour CE personnage : quel item, quelle
	quantité, et son coût — **gratuit** si l'une des relations de `gratuit_si.lieux`
	atteint le seuil (défaut world-var PNJ_REPUTATION_SEUIL). None si le PNJ n'offre pas
	ce service. Miroir de `soin_effectif`. Schéma data attendu :
	`services.don = {item, quantite, cout_cuivre, gratuit_si:{lieux, seuil},
	noeuds:{fait, sans_fonds, trop_charge}}`."""
	service = (((pnj_doc or {}).get("services") or {}).get("don"))
	if not service or not service.get("item"):
		return None
	gratuit_si = service.get("gratuit_si") or {}
	seuil = int(gratuit_si.get("seuil", character_stats.PNJ_REPUTATION_SEUIL))
	relations = contexte.get("relations") or {}
	gratuit = any(relations.get(lid, 0) >= seuil for lid in gratuit_si.get("lieux") or [])
	cout = 0 if gratuit else max(0, int(service.get("cout_cuivre", 0)))
	return {
		"item": service.get("item"),
		"quantite": max(1, int(service.get("quantite", 1))),
		"cout_cuivre": cout,
		"gratuit": gratuit,
	}


def appliquer_don(character: dict, item_id: str, poids_unitaire: float, quantite: int) -> int:
	"""Ajoute `quantite` instances de `item_id` à l'inventaire, chacune en référence
	`{item, poids}` (mute `inventaire`, NE SAUVEGARDE PAS). Renvoie la quantité ajoutée.
	Le contrôle de charge et le débit se font côté router avant l'appel."""
	inv = character.setdefault("inventaire", [])
	n = max(1, int(quantite))
	for _ in range(n):
		inv.append({"item": item_id, "poids": float(poids_unitaire)})
	return n
