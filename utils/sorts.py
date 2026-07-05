# utils/sorts.py
# Sorts (magie) : un doc CouchDB `sort:*` porte une vocation, un niveau, un coût en PM
# et des `effets` au format des consommables ({pv, pm, regen_pv, regen_pm, buffs, duree})
# étendu d'une clé `degats` (notation dés, ex. "2D6"). Deux modes d'utilisation :
# sans composant (PM seuls, effet de base) ou avec composant(s) — chaque entrée de
# `composants` [{item, consomme, bonus}] ajoute son `bonus` (même schéma qu'`effets`)
# aux effets de base. Composant `consomme:true` = retiré du sac (gros bonus) ;
# `consomme:false` = catalyseur, il suffit de le porter (sac ou équipé, bonus moindre).
#
# Apprentissage : le personnage stocke `sorts_connus` (liste d'ids). Un sort de niveau n
# est achetable en points de caractéristique — coût (n+1) × SORT_COUT_COEFF — dès que
# vocations_niveaux[vocation] ≥ n ET qu'un grimoire l'enseignant (item sous_categorie
# "grimoire", champ `sorts` contenant l'id) est porté. Le grimoire n'est PAS consommé.
#
# Logique pure (get_doc/find_docs/resolve_ref injectés), ne sauvegarde jamais — les
# endpoints persistent. Comme pour les consommables : pv/pm/degats = instantanés (seuls
# applicables en combat) ; buffs/regen_* + duree = effet actif empilé sur
# character["effets_actifs"] (tour monde uniquement) ; jamais de buff sur V.

from models import character_stats
from utils.characters import item_ref_id
from utils.consommables import _as_int


def _bonus_dict(raw) -> dict:
	"""Normalise un bloc d'effets/bonus : degats str, entiers ≥ 0, buffs {caract:int}
	(V exclu — échelle 1-10, incompatible avec des deltas ×10), duree ≥ 0."""
	raw = raw or {}
	buffs = {}
	for k, v in (raw.get("buffs") or {}).items():
		if str(k) == "V":
			continue
		try:
			buffs[str(k)] = int(v)
		except (TypeError, ValueError):
			continue
	return {
		"degats": str(raw.get("degats") or "").strip(),
		"pv": _as_int(raw.get("pv")),
		"pm": _as_int(raw.get("pm")),
		"regen_pv": _as_int(raw.get("regen_pv")),
		"regen_pm": _as_int(raw.get("regen_pm")),
		"buffs": buffs,
		"duree": _as_int(raw.get("duree")),
	}


def effets_de_sort(sort_doc) -> dict:
	"""Champ `effets` du sort, normalisé (clés toujours présentes)."""
	return _bonus_dict((sort_doc or {}).get("effets"))


def normaliser_sort(sort_doc) -> dict | None:
	"""Vue normalisée d'un doc `sort:*`, ou None si le doc n'est pas un sort valide
	(type ≠ "sort", vocation absente, coût PM ≤ 0)."""
	doc = sort_doc or {}
	if doc.get("type") != "sort" or not doc.get("vocation"):
		return None
	cout_pm = _as_int(doc.get("cout_pm"))
	if cout_pm <= 0:
		return None
	composants = []
	for c in doc.get("composants") or []:
		item_id = (c or {}).get("item")
		if not item_id:
			continue
		composants.append({
			"item": str(item_id),
			"consomme": bool(c.get("consomme")),
			"bonus": _bonus_dict(c.get("bonus")),
		})
	return {
		"id": doc.get("_id", ""),
		"nom": doc.get("nom", "Sort"),
		"icon": doc.get("icon", "🔮"),
		"description": doc.get("description", ""),
		"vocation": doc.get("vocation"),
		"niveau": _as_int(doc.get("niveau")),
		"cout_pm": cout_pm,
		"cible": doc.get("cible") or "soi",
		"portee": _as_int(doc.get("portee")),
		"effets": effets_de_sort(doc),
		"composants": composants,
	}


def _concat_degats(a: str, b: str) -> str:
	"""Concatène deux notations de dés/bonus plats ("2D6" + "1D6" → "2D6+1D6")."""
	a, b = (a or "").strip(), (b or "").strip()
	if not a:
		return b
	if not b:
		return a
	return a + "+" + b


def fusionner_effets(base: dict, bonus_list: list) -> dict:
	"""Effets de base + bonus additifs des composants engagés : entiers additionnés,
	buffs sommés par caract, notations `degats` concaténées, durée additive."""
	out = {
		"degats": base.get("degats", ""),
		"pv": _as_int(base.get("pv")),
		"pm": _as_int(base.get("pm")),
		"regen_pv": _as_int(base.get("regen_pv")),
		"regen_pm": _as_int(base.get("regen_pm")),
		"buffs": dict(base.get("buffs") or {}),
		"duree": _as_int(base.get("duree")),
	}
	for bonus in bonus_list or []:
		bonus = bonus or {}
		out["degats"] = _concat_degats(out["degats"], bonus.get("degats", ""))
		for key in ("pv", "pm", "regen_pv", "regen_pm", "duree"):
			out[key] += _as_int(bonus.get(key))
		for k, delta in (bonus.get("buffs") or {}).items():
			if str(k) == "V":
				continue
			try:
				out["buffs"][str(k)] = int(out["buffs"].get(str(k), 0)) + int(delta)
			except (TypeError, ValueError):
				continue
	return out


def _ids_sac(character: dict) -> list:
	return [item_ref_id(ref) for ref in (character or {}).get("inventaire") or []]


def _ids_portes(character: dict) -> list:
	"""Ids des items portés : sac + slots équipés."""
	ids = _ids_sac(character)
	for ref in ((character or {}).get("slots") or {}).values():
		if ref:
			ids.append(item_ref_id(ref))
	return ids


def composants_etat(sort: dict, character: dict) -> list:
	"""Disponibilité de chaque composant du sort : un catalyseur (`consomme:false`)
	est disponible s'il est porté (sac OU équipé) ; un composant consommé exige au
	moins un exemplaire AU SAC (un item seulement équipé ne se consume pas)."""
	sac = _ids_sac(character)
	portes = _ids_portes(character)
	out = []
	for c in (sort or {}).get("composants") or []:
		pool = sac if c.get("consomme") else portes
		out.append({**c, "disponible": c.get("item") in pool})
	return out


def effets_effectifs(sort: dict, composants_engages: list) -> dict:
	"""Effets du sort avec les bonus des composants dont l'id figure dans
	`composants_engages` (liste d'ids item, déjà re-vérifiés par l'appelant)."""
	engages = set(composants_engages or [])
	bonus = [c["bonus"] for c in (sort or {}).get("composants") or []
			 if c.get("item") in engages]
	return fusionner_effets((sort or {}).get("effets") or {}, bonus)


def sort_utilisable_combat(sort: dict) -> bool:
	"""Éligibilité combat : le sort doit avoir une part instantanée (dégâts, PV ou PM).
	La part buffs/durée d'un sort mixte est perdue en combat (règle consommables)."""
	eff = (sort or {}).get("effets") or {}
	return bool(eff.get("degats")) or _as_int(eff.get("pv")) > 0 or _as_int(eff.get("pm")) > 0


def sort_utilisable_exploration(sort: dict) -> bool:
	"""Éligibilité exploration : ciblé sur soi ET au moins un effet applicable hors
	combat (soin/PM instantanés, ou buffs/régén à durée)."""
	s = sort or {}
	if (s.get("cible") or "soi") != "soi":
		return False
	eff = s.get("effets") or {}
	instant = _as_int(eff.get("pv")) > 0 or _as_int(eff.get("pm")) > 0
	duratif = _as_int(eff.get("duree")) > 0 and bool(
		eff.get("buffs") or _as_int(eff.get("regen_pv")) or _as_int(eff.get("regen_pm")))
	return instant or duratif


def empiler_effet_sort(character: dict, sort: dict, effets: dict) -> dict | None:
	"""Empile la part à durée (buffs/régén) des effets FUSIONNÉS sur
	character["effets_actifs"] (mute en place, NE SAUVEGARDE PAS). Même forme d'entrée
	que les consommables → tick_effets/caracts_avec_buffs/regen_bonus/chips inchangés."""
	eff = effets or {}
	if _as_int(eff.get("duree")) <= 0 or not (
			eff.get("buffs") or _as_int(eff.get("regen_pv")) or _as_int(eff.get("regen_pm"))):
		return None
	entry = {
		"sort_id": (sort or {}).get("id", ""),
		"nom": (sort or {}).get("nom", "Sort"),
		"icon": (sort or {}).get("icon", "🔮"),
		"buffs": dict(eff.get("buffs") or {}),
		"regen_pv": _as_int(eff.get("regen_pv")),
		"regen_pm": _as_int(eff.get("regen_pm")),
		"restants": _as_int(eff.get("duree")),
	}
	character.setdefault("effets_actifs", []).append(entry)
	return entry


# ── Apprentissage ────────────────────────────────────────────────────────────────

def cout_apprentissage(sort: dict) -> int:
	"""Coût en points de caractéristique : (niveau du sort + 1) × SORT_COUT_COEFF
	(lecture via le module — la world-var est réassignée à chaud)."""
	return (_as_int((sort or {}).get("niveau")) + 1) * character_stats.SORT_COUT_COEFF


def est_grimoire(item_doc) -> bool:
	return bool(item_doc) and item_doc.get("sous_categorie") == "grimoire"


def grimoire_pour(character: dict, sort_id: str, resolve_ref) -> dict | None:
	"""Premier grimoire porté (sac puis équipé) qui enseigne `sort_id`
	(item `sous_categorie:"grimoire"` dont le champ `sorts` contient l'id)."""
	refs = list((character or {}).get("inventaire") or [])
	refs += [ref for ref in ((character or {}).get("slots") or {}).values() if ref]
	for ref in refs:
		doc = resolve_ref(ref)
		if est_grimoire(doc) and sort_id in (doc.get("sorts") or []):
			return doc
	return None


def sorts_connus_docs(character: dict, get_doc) -> list:
	"""Docs normalisés des sorts connus du personnage (ids morts ignorés)."""
	out = []
	for sort_id in (character or {}).get("sorts_connus") or []:
		sort = normaliser_sort(get_doc(sort_id))
		if sort:
			out.append(sort)
	return out


def sorts_epingles_effectifs(character: dict) -> list:
	"""Sorts d'accès rapide (barre d'icônes en combat), ids ordonnés.

	Champ `sorts_epingles` présent → liste filtrée aux sorts encore connus (ordre
	conservé, y compris vide = choix explicite du joueur). Champ absent (perso
	d'avant la feature ou jamais touché) → **auto-épinglage du premier sort connu**,
	sans migration."""
	character = character or {}
	connus = character.get("sorts_connus") or []
	if "sorts_epingles" in character:
		epingles = character.get("sorts_epingles") or []
		return [s for s in epingles if s in connus]
	return connus[:1]


def sorts_apprenables(character: dict, find_docs, resolve_ref) -> list:
	"""Sorts achetables par le personnage : vocation pratiquée (présente dans
	vocations_niveaux), niveau de vocation suffisant, pas déjà connu. Chaque entrée
	est enrichie de `cout_points` et `grimoire_ok` (grimoire enseignant porté)."""
	connus = set((character or {}).get("sorts_connus") or [])
	niveaux = (character or {}).get("vocations_niveaux") or {}
	out = []
	for doc in find_docs({"type": "sort"}) or []:
		sort = normaliser_sort(doc)
		if not sort or sort["id"] in connus:
			continue
		if sort["vocation"] not in niveaux or niveaux[sort["vocation"]] < sort["niveau"]:
			continue
		sort["cout_points"] = cout_apprentissage(sort)
		sort["grimoire_ok"] = grimoire_pour(character, sort["id"], resolve_ref) is not None
		out.append(sort)
	out.sort(key=lambda s: (s["vocation"], s["niveau"], s["nom"]))
	return out


def sorts_depart_par_vocation(find_docs) -> dict:
	"""Sorts niveau 0 groupés par vocation — choix du sort de départ à la création
	de personnage : {vocation: [{id, nom, icon, description}]}."""
	out: dict = {}
	for doc in find_docs({"type": "sort"}) or []:
		s = normaliser_sort(doc)
		if not s or s["niveau"] != 0:
			continue
		out.setdefault(s["vocation"], []).append({
			"id": s["id"], "nom": s["nom"], "icon": s["icon"],
			"description": s["description"],
		})
	for lst in out.values():
		lst.sort(key=lambda x: x["nom"])
	return out


# ── Payloads UI ──────────────────────────────────────────────────────────────────

def _composants_payload(sort: dict, character: dict, resolve_ref_doc) -> list:
	"""Composants avec disponibilité + nom/icône résolus pour l'affichage."""
	out = []
	for c in composants_etat(sort, character):
		doc = resolve_ref_doc(c["item"]) or {}
		out.append({
			"item": c["item"],
			"nom": doc.get("nom", c["item"]),
			"icon": doc.get("icon", "❔"),
			"consomme": c["consomme"],
			"bonus": c["bonus"],
			"disponible": c["disponible"],
		})
	return out


def liste_sorts_payload(character: dict, get_doc, contexte: str) -> list:
	"""Sorts connus pour l'UI (rendu initial ET resync après action) : effets de base +
	composants avec disponibilité — le client affiche les bonus et envoie les ids engagés.
	Contexte "combat" : seuls les sorts à part instantanée (sélecteur 🔮). Contexte
	"exploration" : TOUS les sorts connus (onglet ⚡ = catalogue), drapeau `lancable`
	pour les seuls lançables hors combat."""
	out = []
	for sort in sorts_connus_docs(character, get_doc):
		if contexte == "combat" and not sort_utilisable_combat(sort):
			continue
		out.append({
			"lancable": True if contexte == "combat" else sort_utilisable_exploration(sort),
			"sort_id": sort["id"],
			"nom": sort["nom"],
			"icon": sort["icon"],
			"description": sort["description"],
			"niveau": sort["niveau"],
			"cout_pm": sort["cout_pm"],
			"cible": sort["cible"],
			"portee": sort["portee"],
			"effets": sort["effets"],
			"composants": _composants_payload(sort, character, get_doc),
		})
	return out
