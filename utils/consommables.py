# utils/consommables.py
# Consommables à effet de gameplay : un item `categorie:"consommable"` porte un champ
# `effets` {pv, pm, regen_pv, regen_pm, buffs:{caract:+delta}, duree} (tous optionnels).
# pv/pm = instantanés ; buffs/regen_* = effet actif empilé sur character["effets_actifs"],
# décrémenté à chaque tour monde (move_character). Un effet à durée vaut AUSSI en combat :
# le snapshot en porte une copie vivante, décrémentée au tour de son porteur puis reversée
# sur le personnage en fin de combat (cf. utils/combat._tick_effets_combat / _finalize_membre).
#
# Logique pure (resolve_ref injecté), ne sauvegarde jamais — l'endpoint persiste.
# Les buffs sont volontairement EXCLUS de charge_max_of, des plafonds/coûts d'XP et de
# restriction_satisfaite (équipement) : un buff expiré ne doit ni bloquer un déplacement
# (surcharge), ni permettre d'équiper/monter ce qu'on ne pourrait pas sans lui.

from utils.characters import item_ref_id


def _as_int(x) -> int:
	try:
		return max(0, int(x or 0))
	except (TypeError, ValueError):
		return 0


def effets_de(item_doc) -> dict:
	"""Champ `effets` de l'item, normalisé : pv/pm/regen_pv/regen_pm entiers ≥ 0,
	buffs dict {caract: int}, duree entier ≥ 0. Dict aux clés toujours présentes."""
	raw = (item_doc or {}).get("effets") or {}
	buffs = {}
	for k, v in (raw.get("buffs") or {}).items():
		try:
			buffs[str(k)] = int(v)
		except (TypeError, ValueError):
			continue
	return {
		"pv": _as_int(raw.get("pv")),
		"pm": _as_int(raw.get("pm")),
		"regen_pv": _as_int(raw.get("regen_pv")),
		"regen_pm": _as_int(raw.get("regen_pm")),
		"buffs": buffs,
		"duree": _as_int(raw.get("duree")),
		"esquive": _as_int(raw.get("esquive")),
	}


def est_consommable(item_doc) -> bool:
	"""Consommable actif = catégorie `consommable` ET au moins un effet. Les consommables
	sans `effets` (Torche, Bougie…) restent inertes — rétro-compat volontaire."""
	if not item_doc or item_doc.get("categorie") != "consommable":
		return False
	eff = effets_de(item_doc)
	return bool(eff["pv"] or eff["pm"] or eff["regen_pv"] or eff["regen_pm"]
				or eff["buffs"] or eff["esquive"])


def effet_instantane(item_doc) -> bool:
	"""Éligibilité combat : une part instantanée (pv/pm) OU un effet à DURÉE (buffs/régén/
	esquive), désormais empilable en combat comme en exploration. Nom historique conservé —
	c'est le prédicat « utilisable en combat », miroir de sorts.sort_utilisable_combat."""
	eff = effets_de(item_doc)
	if eff["pv"] > 0 or eff["pm"] > 0:
		return True
	return eff["duree"] > 0 and bool(
		eff["buffs"] or eff["regen_pv"] or eff["regen_pm"] or eff["esquive"])


ORIGINES_BUFFS: tuple = ("effet", "equipement", "competence")


def _sources_de_buffs_detaillees(character: dict, origines: tuple = ORIGINES_BUFFS) -> list:
	"""Toutes les sources de buffs/régén, étiquetées par origine : [(origine, entrée), …].

	origine ∈ "effet" (consommables/sorts/compétences actives — TEMPORAIRE, décrémenté au
	tour monde ET, depuis les effets en combat, au tour du porteur), "equipement"
	(`equipment_bonus`, dénormalisé par utils/characters.sync_equipment_bonus) et
	"competence" (`competences_bonus`, passives permanentes, dénormalisé par
	utils/competences.recompute_competences_bonus).

	`origines` restreint le repli à un sous-ensemble. Seul le snapshot de combat s'en sert,
	pour obtenir la base PERMANENTE (équipement + passives) : les effets temporaires y
	deviennent vivants, portés par le snapshot lui-même et recalculés à chaque tour
	(cf. utils/combat._refresh_snapshot_stats). Partout ailleurs, le défaut s'applique.

	Toutes les entrées ont le même format {buffs, regen_pv, regen_pm, esquive} — celles qui
	n'en portent qu'une partie (l'équipement n'a que `buffs`) sont neutres pour le reste.
	"""
	character = character or {}
	sources = []
	if "effet" in origines:
		sources += [("effet", eff) for eff in (character.get("effets_actifs") or [])]
	for origine, cle in (("equipement", "equipment_bonus"), ("competence", "competences_bonus")):
		if origine not in origines:
			continue
		entree = character.get(cle)
		if entree:
			sources.append((origine, entree))
	return sources


def _sources_de_buffs(character: dict, origines: tuple = ORIGINES_BUFFS) -> list:
	"""Chokepoint unique : tout ce qui buffe un personnage passe ici, donc par
	caracts_avec_buffs / regen_bonus / esquive_bonus."""
	return [eff for _, eff in _sources_de_buffs_detaillees(character, origines)]


def caracts_avec_buffs(character: dict, origines: tuple = ORIGINES_BUFFS) -> dict:
	"""COPIE de caracteristiques_current + somme des buffs (clamp ≥ 0). N'applique que les
	caracts déjà présentes. V incluse : une dague +1 V accélère bel et bien le personnage
	(deltas de V à son échelle 1-10, comme dans les données d'items)."""
	caracts = dict((character or {}).get("caracteristiques_current") or {})
	for eff in _sources_de_buffs(character, origines):
		for k, delta in (eff.get("buffs") or {}).items():
			if k not in caracts:
				continue
			try:
				caracts[k] = max(0, int(caracts[k] or 0) + int(delta))
			except (TypeError, ValueError):
				continue
	return caracts


def caracts_detail(character: dict) -> dict:
	"""Détail par caractéristique pour la fiche : {code: {base, total, delta, sources}}.

	`sources` = [{origine, nom, icon, delta}] — une entrée par contributeur NOMMÉ (l'objet
	équipé, la compétence passive, le consommable/sort en cours), pour le tooltip de la
	grille « Profil modifié ». Fonction PURE : tout est déjà dénormalisé sur le doc perso
	(les agrégats `equipment_bonus`/`competences_bonus` portent un `buffs_sources`).
	"""
	base = dict((character or {}).get("caracteristiques_current") or {})
	total = caracts_avec_buffs(character)
	detail = {
		code: {"base": val, "total": total.get(code, val), "delta": total.get(code, val) - val,
			   "sources": []}
		for code, val in base.items()
	}
	for origine, eff in _sources_de_buffs_detaillees(character):
		# Un agrégat (équipement, compétences) porte le détail nommé de ses contributeurs ;
		# une entrée d'effet actif est elle-même déjà nommée.
		contributeurs = eff.get("buffs_sources") or [eff]
		for src in contributeurs:
			for code, delta in (src.get("buffs") or {}).items():
				if code not in detail or not delta:
					continue
				detail[code]["sources"].append({
					"origine": origine,
					"nom":     src.get("nom", "?"),
					"icon":    src.get("icon", "✨"),
					"delta":   int(delta),
				})
	return detail


def regen_bonus(character: dict, origines: tuple = ORIGINES_BUFFS) -> tuple[int, int]:
	"""(Σ regen_pv, Σ regen_pm) des effets actifs et des passives — s'ajoute à la régén
	naturelle."""
	pv = pm = 0
	for eff in _sources_de_buffs(character, origines):
		pv += _as_int(eff.get("regen_pv"))
		pm += _as_int(eff.get("regen_pm"))
	return pv, pm


def esquive_bonus(character: dict, origines: tuple = ORIGINES_BUFFS) -> int:
	"""Σ `esquive` des effets actifs et des passives — malus au seuil de toucher
	PHYSIQUE (cc/cd) des attaques subies en combat (la magie se résout sur pm_def,
	jamais réduite par l'esquive)."""
	total = 0
	for eff in _sources_de_buffs(character, origines):
		total += _as_int(eff.get("esquive"))
	return total


def empiler_effet(character: dict, item_doc: dict) -> dict | None:
	"""Empile l'effet à durée (buffs/régén) de l'item sur character["effets_actifs"]
	(mute en place, NE SAUVEGARDE PAS). Renvoie l'entrée créée, None si l'item n'a pas
	d'effet à durée. Empilement autorisé (2 potions = 2 entrées)."""
	eff = effets_de(item_doc)
	if eff["duree"] <= 0 or not (eff["buffs"] or eff["regen_pv"] or eff["regen_pm"]
			or eff["esquive"]):
		return None
	entry = {
		"item_id": item_doc.get("item") or item_doc.get("_id"),
		"nom": item_doc.get("nom", "Effet"),
		"icon": item_doc.get("icon", "✨"),
		"buffs": eff["buffs"],
		"regen_pv": eff["regen_pv"],
		"regen_pm": eff["regen_pm"],
		"esquive": eff["esquive"],
		"restants": eff["duree"],
	}
	character.setdefault("effets_actifs", []).append(entry)
	return entry


def appliquer_instantane(character: dict, item_doc: dict, pv_max: int, pm_max: int) -> dict:
	"""Applique la part instantanée (pv/pm) au personnage, clampée aux max passés (mute
	en place, NE SAUVEGARDE PAS). pv_max/pm_max sont fournis par l'appelant, calculés
	APRÈS l'empilement du buff : une potion mixte soigne dans le max bufffé."""
	eff = effets_de(item_doc)
	avant_pv = int(character.get("currentPV", pv_max) or 0)
	avant_pm = int(character.get("currentPM", pm_max) or 0)
	character["currentPV"] = min(int(pv_max), avant_pv + eff["pv"])
	character["currentPM"] = min(int(pm_max), avant_pm + eff["pm"])
	return {
		"pv_rendu": character["currentPV"] - avant_pv,
		"pm_rendu": character["currentPM"] - avant_pm,
	}


def tick_effets(character: dict) -> list:
	"""Décrémente `restants` de chaque effet actif, purge ceux à 0 (mute en place).
	Renvoie les entrées expirées (l'appelant re-clampe PV/PM si un buff R/Vol tombe)."""
	actifs = (character or {}).get("effets_actifs") or []
	if not actifs:
		return []
	restants, expires = [], []
	for eff in actifs:
		eff["restants"] = _as_int(eff.get("restants")) - 1
		(restants if eff["restants"] > 0 else expires).append(eff)
	character["effets_actifs"] = restants
	return expires


def effets_actifs_payload(character: dict) -> list:
	"""Effets actifs pour l'UI (chips ✨ de la fiche) — copies, jamais les entrées vives."""
	return [dict(eff) for eff in (character or {}).get("effets_actifs") or []]


def liste_consommables_combat(character: dict, resolve_ref_fn) -> list:
	"""Consommables du sac utilisables en combat (effet instantané seulement), avec leur
	index D'ORIGINE dans l'inventaire (adressage serveur par index vérifié item_id)."""
	out = []
	for idx, ref in enumerate((character or {}).get("inventaire") or []):
		doc = resolve_ref_fn(ref)
		if not doc or not est_consommable(doc) or not effet_instantane(doc):
			continue
		eff = effets_de(doc)
		out.append({
			"index": idx,
			"item_id": item_ref_id(ref),
			"nom": doc.get("nom", "?"),
			"icon": doc.get("icon", "🧪"),
			"pv": eff["pv"],
			"pm": eff["pm"],
			# Durée > 0 = potion à effet prolongé : l'UI l'annonce autrement qu'un soin sec.
			"duree": eff["duree"],
			"poids": doc.get("poids", 0),
		})
	return out
