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
from utils.consommables import _as_int, poser_effet

# Jet de toucher d'un effet offensif, porté par la DONNÉE. SOURCE UNIQUE, partagée avec
# les compétences (utils/competences.py l'importe) — les deux familles se résolvent par
# le même contrat, il ne doit pas exister deux listes qui divergent.
#   `magique` → seuil `_magic_hit_threshold` contre la pm_def, PA NON soustraits ;
#   `cc`/`cd` → seuil `_hit_threshold` contre l'Ag (+ esquive), PA soustraits.
# ⚠️ Le défaut DIFFÈRE entre les deux familles, et c'est voulu : une compétence est
# martiale par défaut (`cc`), un sort est magique par défaut (`magique`) — sans quoi les
# sorts déjà en base changeraient de mode de résolution du jour au lendemain.
JETS = ("cc", "cd", "magique")
JET_SORT_DEFAUT = "magique"

# Cibles possibles d'un sort ou d'une compétence. SOURCE UNIQUE, partagée elle aussi.
#   `soi`    → le lanceur ;
#   `ennemi` → un monstre, jet de toucher (cf. JETS) ;
#   `allie`  → un COMPAGNON ou une MONTURE du groupe, SANS jet (un allié ne se défend
#              pas). Combat uniquement : l'exploration ne sait pas encore désigner un
#              porteur comme cible, cf. `sort_utilisable_exploration`.
CIBLES = ("soi", "ennemi", "allie")
CIBLE_DEFAUT = "soi"


def _bonus_dict(raw) -> dict:
	"""Normalise un bloc d'effets/bonus : degats str, entiers ≥ 0, buffs {caract:int},
	duree ≥ 0.

	⚠️ **V est buffable, mais à SON échelle (1-10), pas à celle des autres (×10).** Elle
	en était exclue par prudence — un auteur écrivant `{V: 10}` en pensant « +1 case »
	aurait immobilisé puis catapulté sa cible. L'exclusion a été levée quand il a fallu
	entraver les jambes d'une cible (bolas) : elle ne protégeait aucun contenu (aucun doc
	du jeu n'écrivait de buff de V) et elle rendait l'entrave **impossible à exprimer**,
	alors que toute la chaîne aval la gère déjà (`_refresh_snapshot_stats` recompose
	`deplacement_base` depuis V, l'IA monstre lit `deplacement`). Ordres de grandeur :
	**−2 = un tiers du déplacement d'un humain**, −5 l'immobilise à peu près. Deux
	planchers bornent la casse : V ne descend pas sous 0 (`_refresh_snapshot_stats`) et
	`deplacement = max(1, V)` — une cible entravée avance toujours d'une case.

	Clés de combat partagées sorts/compétences :
	- `esquive`  : malus au seuil de toucher PHYSIQUE (cc/cd) des attaques subies —
	  jamais la magie (elle se résout sur pm_def, pas sur l'Ag).
	- `furtivite`: > 0 = confère l'état furtif ; la valeur s'ajoute à l'Ag dans la
	  difficulté du jet de détection des ennemis."""
	raw = raw or {}
	buffs = {}
	for k, v in (raw.get("buffs") or {}).items():
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
		"esquive": _as_int(raw.get("esquive")),
		"furtivite": _as_int(raw.get("furtivite")),
	}


def effets_de_sort(sort_doc) -> dict:
	"""Champ `effets` du sort, normalisé (clés toujours présentes)."""
	return _bonus_dict((sort_doc or {}).get("effets"))


# Une ARME porte le même bloc `effets` qu'un sort, mais ne sait viser que deux personnes :
# celui qu'elle frappe, ou celui qui la tient. `allie` n'a pas de sens pour un coup porté
# (aucun jet de toucher n'a désigné d'allié) → il retombe sur `ennemi` plutôt que d'ouvrir
# un troisième comportement silencieux, exactement comme `normaliser_sort` clampe `cible`.
CIBLES_ARME = ("ennemi", "soi")
CIBLE_ARME_DEFAUT = "ennemi"


def effets_d_arme(item_doc) -> tuple[dict, str]:
	"""`(effets normalisés, cible)` d'un doc `item:*` — le bloc `effets` d'une arme.

	Même normalisation que les sorts et les compétences (source unique `_bonus_dict`) :
	un effet d'arme se décrit exactement comme un effet de sort, et se pose par les mêmes
	chokepoints. Seule la **part durative** est exploitée à l'impact (`part_durative`) ;
	`degats`/`pv`/`pm` d'une arme passent par ses `bonus_degats*`, pas par ce bloc."""
	doc = item_doc or {}
	cible = str(doc.get("cible") or CIBLE_ARME_DEFAUT)
	if cible not in CIBLES_ARME:
		cible = CIBLE_ARME_DEFAUT
	return _bonus_dict(doc.get("effets")), cible


def normaliser_sort(sort_doc) -> dict | None:
	"""Vue normalisée d'un doc `sort:*`, ou None si le doc n'est pas un sort valide
	(type ≠ "sort", vocation absente, coût PM ≤ 0)."""
	doc = sort_doc or {}
	if doc.get("type") != "sort" or not doc.get("vocation"):
		return None
	cout_pm = _as_int(doc.get("cout_pm"))
	if cout_pm <= 0:
		return None
	cible = str(doc.get("cible") or CIBLE_DEFAUT)
	if cible not in CIBLES:
		cible = CIBLE_DEFAUT
	jet = str(doc.get("jet") or JET_SORT_DEFAUT)
	if jet not in JETS:
		jet = JET_SORT_DEFAUT
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
		"magie": (str(doc.get("magie")).strip() or None) if doc.get("magie") else None,
		"niveau": _as_int(doc.get("niveau")),
		"cout_pm": cout_pm,
		"cible": cible,
		# Jet de toucher (cible ennemie seulement) : `magique` par défaut — un sort de
		# CONTACT peut demander `cc` (« au toucher » : il faut d'abord poser la main).
		"jet": jet,
		"portee": _as_int(doc.get("portee")),
		"effets": effets_de_sort(doc),
		"composants": composants,
		# Condition d'activation optionnelle (partagée avec les compétences) :
		# {"battle_map_tags": [...]} — évaluée en combat via condition_remplie.
		"condition": dict(doc.get("condition") or {}),
		# Animation de combat (doc `animation:*`), optionnelle : le router passe la vue
		# normalisée à resolve_action, donc sans ce champ EXPLICITE la liaison serait
		# perdue avant d'atteindre le moteur (cette vue est une liste blanche).
		"animation": str(doc.get("animation") or ""),
	}


def concat_degats(a: str, b: str) -> str:
	"""Concatène deux notations de dés/bonus plats ("2D6" + "1D6" → "2D6+1D6"). Publique :
	partagée par les composants de sort (fusionner_effets) et par les compétences de corps à
	corps, qui ajoutent les dégâts d'arme du porteur aux leurs (combat._degats_competence)."""
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
		"esquive": _as_int(base.get("esquive")),
		"furtivite": _as_int(base.get("furtivite")),
	}
	for bonus in bonus_list or []:
		bonus = bonus or {}
		out["degats"] = concat_degats(out["degats"], bonus.get("degats", ""))
		for key in ("pv", "pm", "regen_pv", "regen_pm", "duree", "esquive", "furtivite"):
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


def part_durative(effets: dict) -> bool:
	"""Vrai si `effets` porte quelque chose à empiler sur la durée : une `duree` > 0 ET
	au moins un bénéfice prolongé (buffs de caract, régén, esquive).

	SOURCE UNIQUE de ce test — utilisée par les éligibilités combat/exploration des sorts,
	des compétences et des consommables, et par les deux `empiler_effet_*`. Un critère qui
	diverge entre « lançable » et « empilable » produirait un sort accepté puis sans effet.
	"""
	eff = effets or {}
	return _as_int(eff.get("duree")) > 0 and bool(
		eff.get("buffs") or _as_int(eff.get("regen_pv")) or _as_int(eff.get("regen_pm"))
		or _as_int(eff.get("esquive")))


def sort_utilisable_combat(sort: dict) -> bool:
	"""Éligibilité combat : une part instantanée (dégâts, PV, PM — ou furtivité, état de
	combat posé instantanément) OU une part à DURÉE. Depuis que le snapshot porte ses
	effets vivants et les décrémente au tour de son porteur, un buff pur (« Armure de
	givre ») est lançable en combat exactement comme en exploration."""
	eff = (sort or {}).get("effets") or {}
	return (bool(eff.get("degats")) or _as_int(eff.get("pv")) > 0
			or _as_int(eff.get("pm")) > 0 or _as_int(eff.get("furtivite")) > 0
			or part_durative(eff))


def sort_utilisable_exploration(sort: dict) -> bool:
	"""Éligibilité exploration : NON offensif (`soi` ou `allie`) ET au moins un effet
	applicable hors combat (soin/PM instantanés, ou buffs/régén/esquive à durée).

	⚠️ Seul `ennemi` est exclu : il n'y a pas de monstre à viser hors combat. Un sort
	`allie` est lançable sur un compagnon ou une monture — la cible est désignée par le
	`cible_id` du corps de requête (cf. `_cible_alliee`, routers/user.py)."""
	s = sort or {}
	if (s.get("cible") or "soi") == "ennemi":
		return False
	eff = s.get("effets") or {}
	instant = _as_int(eff.get("pv")) > 0 or _as_int(eff.get("pm")) > 0
	return instant or part_durative(eff)


def empiler_effet_sort(character: dict, sort: dict, effets: dict) -> dict | None:
	"""Empile la part à durée (buffs/régén) des effets FUSIONNÉS sur
	character["effets_actifs"] (mute en place, NE SAUVEGARDE PAS). Même forme d'entrée
	que les consommables → tick_effets/caracts_avec_buffs/regen_bonus/chips inchangés.
	⚠️ Relancer le MÊME sort ne cumule pas : `poser_effet` remplace l'entrée précédente
	(seuls les effets du dernier lancement comptent — composants engagés compris)."""
	eff = effets or {}
	if not part_durative(eff):
		return None
	entry = {
		"sort_id": (sort or {}).get("id", ""),
		"nom": (sort or {}).get("nom", "Sort"),
		"icon": (sort or {}).get("icon", "🔮"),
		"buffs": dict(eff.get("buffs") or {}),
		"regen_pv": _as_int(eff.get("regen_pv")),
		"regen_pm": _as_int(eff.get("regen_pm")),
		"esquive": _as_int(eff.get("esquive")),
		"restants": _as_int(eff.get("duree")),
	}
	return poser_effet(character, entry)


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


# ── Écoles de magie (accès par école, pas par vocation) ──────────────────────────
# L'accès aux sorts se fait par ÉCOLE de magie (`magie` du sort, en miroir du `magie`
# de rules:vocations), pas par la vocation. Chaque personnage « pratique » son école
# native (dérivée de sa vocation) ; seules les vocations polyvalentes (lettré) peuvent
# ACHETER la pratique d'autres écoles avec des points de caractéristique. Le niveau de
# l'école native = niveau de la vocation native (vocations_niveaux) ; les écoles achetées
# ont leur propre niveau, stocké dans character["magies_apprises"] = {ecole: niveau}, et
# n'affectent JAMAIS les stats dérivées (anti-exploit).

def _vocation_magie_map(rules_vocations) -> dict:
	"""Map {id_vocation: ecole} depuis le doc rules:vocations (doc complet OU sa `value`).
	Tolère None (→ map vide) et les vocations sans magie (→ chaîne vide)."""
	entries = rules_vocations
	if isinstance(rules_vocations, dict):
		entries = rules_vocations.get("value") or []
	out = {}
	for v in entries or []:
		vid = (v or {}).get("id")
		if vid:
			out[str(vid)] = (str((v or {}).get("magie") or "")).strip()
	return out


def ecole_native(voc, rules_vocations) -> str | None:
	"""École de magie de la vocation native, ou None si la vocation n'est pas magique."""
	return _vocation_magie_map(rules_vocations).get(str(voc or ""), "") or None


def magie_de_sort(sort: dict, rules_vocations) -> str | None:
	"""École d'un sort : champ `magie` s'il est présent, sinon fallback dérivé de sa
	`vocation` via rules:vocations (rétro-compat des sorts non ré-importés)."""
	m = (sort or {}).get("magie")
	if m:
		return str(m).strip()
	return _vocation_magie_map(rules_vocations).get(str((sort or {}).get("vocation") or ""), "") or None


def ecoles_de_grimoire(item_doc: dict, get_doc, rules_vocations) -> list:
	"""Écoles de magie enseignées par un grimoire = union des écoles de ses sorts, triée.

	Un grimoire ne porte AUCUNE école en propre : elle vit sur les sorts de son champ
	`sorts`. Un id mort est ignoré, un sort dont l'école n'est pas résoluble (vocation
	non magique) ne contribue rien — un grimoire peut donc légitimement rendre []."""
	if not est_grimoire(item_doc):
		return []
	out = set()
	for sort_id in (item_doc.get("sorts") or []):
		doc = get_doc(sort_id)
		if not doc:
			continue
		if (ecole := magie_de_sort(doc, rules_vocations)):
			out.add(ecole)
	return sorted(out)


def niveau_ecole(character: dict, ecole, rules_vocations) -> int | None:
	"""Niveau effectif d'une école POUR CE PERSONNAGE, ou None si non pratiquée.
	École native → niveau de la vocation native ; école achetée → magies_apprises."""
	character = character or {}
	if not ecole:
		return None
	native = ecole_native(character.get("voc"), rules_vocations)
	if ecole == native:
		return _as_int((character.get("vocations_niveaux") or {}).get(character.get("voc", ""), 0))
	apprises = character.get("magies_apprises") or {}
	if ecole in apprises:
		return _as_int(apprises[ecole])
	return None


def magies_pratiquees(character: dict, rules_vocations) -> dict:
	"""{ecole: niveau} de toutes les écoles pratiquées : native + achetées."""
	character = character or {}
	out = {}
	native = ecole_native(character.get("voc"), rules_vocations)
	if native:
		out[native] = _as_int((character.get("vocations_niveaux") or {}).get(character.get("voc", ""), 0))
	for ecole, niv in (character.get("magies_apprises") or {}).items():
		out[str(ecole)] = _as_int(niv)
	return out


def ecoles_du_monde(rules_vocations) -> list:
	"""Toutes les écoles de magie existantes (valeurs `magie` non vides), triées."""
	return sorted({m for m in _vocation_magie_map(rules_vocations).values() if m})


def peut_apprendre_magie(character: dict) -> bool:
	"""Vrai si la vocation du perso est polyvalente (lettré) et peut acheter des écoles."""
	return (character or {}).get("voc") in character_stats.MAGIE_POLYVALENTE_VOCATIONS


def ecoles_achetables(character: dict, rules_vocations) -> list:
	"""Écoles que le perso peut encore acheter (polyvalent uniquement, hors déjà pratiquées)."""
	if not peut_apprendre_magie(character):
		return []
	pratiquees = set(magies_pratiquees(character, rules_vocations))
	return [e for e in ecoles_du_monde(rules_vocations) if e not in pratiquees]


def cout_ecole(niveau) -> int:
	"""Coût en points pour acheter (niveau 0) ou monter une école : (niveau+1) × coeff
	(lecture via le module — world-var réassignée à chaud)."""
	return (_as_int(niveau) + 1) * character_stats.MAGIE_ECOLE_COUT_COEFF


def apprentissage_magies_payload(character: dict, rules_vocations) -> dict:
	"""État des écoles pour l'onglet ⚡ (rendu initial + resync) : écoles pratiquées
	(niveau, native/achetée, coût de montée) et écoles achetables (coût d'achat)."""
	native = ecole_native((character or {}).get("voc"), rules_vocations)
	pratiquees = magies_pratiquees(character, rules_vocations)
	return {
		"peut_apprendre": peut_apprendre_magie(character),
		"native": native,
		"pratiquees": [
			{"ecole": e, "niveau": n, "native": e == native,
			 "montable": e != native, "cout_montee": cout_ecole(n)}
			for e, n in sorted(pratiquees.items())
		],
		"achetables": [{"ecole": e, "cout": cout_ecole(0)}
					   for e in ecoles_achetables(character, rules_vocations)],
	}


def sorts_apprenables(character: dict, find_docs, resolve_ref, rules_vocations) -> list:
	"""Sorts achetables par le personnage : école pratiquée (native ou achetée), niveau
	d'école suffisant, pas déjà connu. Chaque entrée est enrichie de `cout_points`,
	`grimoire_ok` (grimoire enseignant porté) et `magie` (école résolue)."""
	connus = set((character or {}).get("sorts_connus") or [])
	out = []
	for doc in find_docs({"type": "sort"}) or []:
		sort = normaliser_sort(doc)
		if not sort or sort["id"] in connus:
			continue
		ecole = magie_de_sort(sort, rules_vocations)
		niv = niveau_ecole(character, ecole, rules_vocations)
		if niv is None or niv < sort["niveau"]:
			continue
		sort["magie"] = ecole
		sort["cout_points"] = cout_apprentissage(sort)
		sort["grimoire_ok"] = grimoire_pour(character, sort["id"], resolve_ref) is not None
		out.append(sort)
	out.sort(key=lambda s: (s.get("magie") or "", s["niveau"], s["nom"]))
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
