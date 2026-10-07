#!/usr/bin/env python
"""Compétences de vocation niveaux 1 → 10, chaque active avec son animation et son son.

    python dev/gen_competences_1_10.py

Sorties (rien n'est écrit si une garde échoue) :
  · jsons/competences_vocations_1_10_a_importer.json — carte d'import de /admin ;
  · docs/competences_vocations_1_10.md — la proposition lisible, GÉNÉRÉE (jamais retouchée à
    la main : retoucher les données de dev/competences_1_10/<vocation>.py puis relancer).

RÈGLE DE COMPTE — existantes comprises (dump + jsons/*_a_importer.json, pièges inclus), à
chaque niveau de 1 à 10, toutes les vocations d'un même groupe finissent identiques :
  · vocation SANS magie (`rules:vocations.magie` vide) : 2 passives + 5 actives = 7 ;
  · vocation À magie : 4, et AUCUNE passive neuve (le complément est fait d'actives).
D'où, au plus, 2 passives neuves par niveau. Les données ne disent que CE QUI MANQUE : une
entrée de trop ou de moins fait échouer le générateur, palier par palier.

VALEURS — jamais écrites dans les données : une échelle par niveau (ECHELLE), interpolée sur
la grille de calibrage de docs/competences_vocations_3_6_10.md, donne PM, dés, buffs, durées.
L'archétype d'une entrée dit seulement quelle FORME elle prend (frappe, zone, entrave, poison,
posture…). Les entrées neuves des paliers 3, 6 et 10 restent ~15 % sous l'active « signature »
déjà en place ; la zone se paie par la décote (−25 / −40 / −50 %).

ANIMATION + SON — chaque active pointe vers un `animation:capa_<thème>` du dump (créés par
dev/gen_animations_capacites.py) dont le `son` n'est pas vide ; un CÔNE porte `(impact muet,
nappe sonore)` en `animation` + `animation_zone`, et sa longueur suit la nappe (l'échelle de
la nappe a été réglée pour cette longueur). Les passives n'en portent pas : aucune résolution
de coup ne les joue, le champ y serait inerte.

GARDES — chaque doc passe `check_competences_doc.verifier_competence` (mêmes invariants que le
document 3/6/10), plus : thème présent et sonore, cardinalités, budget des passives neuves,
noms et `_id` uniques. Un `_id` déjà en base n'est accepté que s'il désigne la MÊME compétence
(même vocation, niveau, mode : ce lot déjà importé) — il est alors compté comme existant et
n'est PAS réémis (`admin_import_bulk` fait un PUT complet : une retouche faite en base
l'emporte). Régénération idempotente.
"""

import importlib
import json
import os
import re
import sys
import unicodedata

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_competences_doc as check  # noqa: E402

NOM_IMPORT = "competences_vocations_1_10_a_importer.json"
SORTIE = os.path.join(check.DOSSIER_JSONS, NOM_IMPORT)
SORTIE_DOC = os.path.join(RACINE, "docs", "competences_vocations_1_10.md")
PREFIXE_ANIM = "animation:capa_"

NIVEAUX = range(1, 11)
# Cibles de compte PAR NIVEAU, existantes comprises — la demande de conception.
TOTAL_MAGIE = 4
PASSIVES_SANS_MAGIE = 2
ACTIVES_SANS_MAGIE = 5
# Points de caractéristique cumulés que les passives NEUVES d'une vocation peuvent donner :
# elles s'additionnent toutes dans `competences_bonus`. ~17 passives × 3,5 pts en moyenne.
BUDGET_PASSIVES_PTS = 64

# Longueur d'un cône selon sa NAPPE : l'`echelle` de chaque thème de cône a été réglée pour
# couvrir exactement ce nombre de crans (cf. dev/gen_animations_capacites.py, THEMES).
LONGUEUR_CONE = {"cone_griffe": 2, "cone_tueur_demon": 2, "cone_souffle_feu": 3,
				 "cone_decharge": 3, "cone_folie": 4}

# ── Échelle par niveau (index = niveau − 1) ──────────────────────────────────────────
ECHELLE = {
	"pm":           [10, 12, 15, 18, 21, 25, 29, 33, 37, 40],
	"des":          ["1D8+3", "2D6+3", "2D8+3", "2D8+5", "3D8+4", "3D8+6", "3D10+7",
					 "4D10+6", "4D10+9", "5D10+12"],
	# frappe qui se paie en PV, ou s'arme plusieurs tours : un cran au-dessus
	"des_fort":     ["2D6+4", "2D8+4", "3D6+6", "3D8+5", "3D8+8", "4D8+6", "4D10+6",
					 "4D10+10", "5D10+10", "6D10+12"],
	# décote de zone : petite −25 %, moyenne −40 %, large −50 %
	"des_petite":   ["1D6+2", "1D8+3", "2D6+3", "2D6+5", "2D8+5", "3D6+6", "3D8+5",
					 "3D8+8", "3D10+8", "4D10+8"],
	"des_moyenne":  ["1D6+1", "1D6+3", "1D8+4", "2D6+3", "2D6+5", "2D8+4", "2D8+6",
					 "3D8+4", "3D8+6", "3D10+6"],
	"des_large":    ["1D4+1", "1D6+2", "1D8+2", "1D8+4", "2D6+3", "2D6+5", "2D8+4",
					 "2D8+6", "3D8+4", "3D8+7"],
	# dés d'une frappe qui porte surtout une entrave ou un poison
	"des_entrave":  ["1D4", "1D6", "1D6+1", "1D8", "1D8+2", "2D6+2", "2D6+4", "2D8+2",
					 "2D8+4", "3D8+2"],
	"siphon":       ["1D6", "1D6+1", "1D8+1", "2D6", "2D6+1", "2D6+2", "2D8", "2D8+1",
					 "2D8+2", "3D8"],
	"buff":         [8, 9, 10, 12, 13, 14, 16, 17, 18, 20],
	"malus":        [6, 7, 8, 9, 10, 12, 13, 14, 15, 16],
	"duree":        [3, 3, 3, 3, 4, 4, 4, 4, 5, 5],
	"poison":       [3, 3, 4, 4, 5, 5, 6, 6, 7, 8],
	"poison_pm":    [2, 2, 3, 3, 3, 4, 4, 4, 5, 5],
	"soin":         [16, 18, 20, 23, 26, 30, 34, 38, 42, 45],
	"regen":        [2, 2, 2, 3, 3, 3, 4, 4, 5, 5],
	"pm_allie":     [8, 10, 12, 14, 16, 18, 20, 22, 24, 26],
	"posture_pm":   [6, 7, 8, 9, 10, 12, 13, 15, 16, 18],
	"posture_tour": [2, 2, 3, 3, 3, 4, 4, 5, 5, 6],
	"drain":        [25, 25, 30, 30, 30, 35, 35, 35, 40, 40],
	"saut":         [2, 2, 3, 3, 3, 4, 4, 4, 5, 5],
	"cout_pv":      [4, 5, 6, 7, 8, 9, 10, 12, 13, 15],
	"esquive":      [6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
	# passives neuves : petites, elles s'additionnent toutes
	"p_pts":        [2, 2, 3, 3, 3, 4, 4, 4, 5, 5],
	"p_esquive":    [3, 3, 4, 4, 5, 5, 6, 6, 7, 8],
	"p_furtivite":  [4, 5, 6, 7, 8, 9, 10, 11, 12, 14],
}

# Profil par vocation : `martial` ⇒ `sensibilite_charge: 0` sur les actives (la technique
# d'un martial ne dépend pas de ce qu'il porte), `jet`/`portee` par défaut d'une frappe,
# `stats` = caractéristiques par défaut d'un buff, `malus` = celles d'une entrave.
PROFILS = {
	"guerrier":      {"martial": True,  "jet": "cc", "portee": 1, "stats": ("F", "R"), "malus": ("Ag", "F")},
	"barbare":       {"martial": True,  "jet": "cc", "portee": 1, "stats": ("F", "R"), "malus": ("R", "Ag")},
	"forestier":     {"martial": True,  "jet": "cd", "portee": 8, "stats": ("Ag", "Ch"), "malus": ("Ag",)},
	"duelliste":     {"martial": True,  "jet": "cc", "portee": 1, "stats": ("Ag", "Cha"), "malus": ("Ag", "F")},
	"assassin":      {"martial": True,  "jet": "cc", "portee": 1, "stats": ("Ag", "F"), "malus": ("Ag", "Vol")},
	"voleur":        {"martial": True,  "jet": "cc", "portee": 1, "stats": ("Ag", "Ch"), "malus": ("Ag", "Int")},
	"moine":         {"martial": False, "jet": "cc", "portee": 1, "stats": ("Vol", "Ag"), "malus": ("Ag", "F")},
	"paladin":       {"martial": False, "jet": "cc", "portee": 1, "stats": ("Vol", "R"), "malus": ("F", "Vol")},
	"templier":      {"martial": False, "jet": "cc", "portee": 1, "stats": ("R", "Vol"), "malus": ("F", "Int")},
	"repurgateur":   {"martial": False, "jet": "cc", "portee": 1, "stats": ("Vol", "Ag"), "malus": ("Vol", "Int")},
	"elementaliste": {"martial": False, "jet": "magique", "portee": 6, "stats": ("Int", "R"), "malus": ("Ag", "R")},
	"mage":          {"martial": False, "jet": "magique", "portee": 6, "stats": ("Int", "R"), "malus": ("Int", "Ag")},
	"illusionniste": {"martial": False, "jet": "magique", "portee": 6, "stats": ("Int", "Cha"), "malus": ("Int", "Vol")},
	"lettre":        {"martial": False, "jet": "magique", "portee": 6, "stats": ("Int", "Vol"), "malus": ("Int", "Ag")},
	"druide":        {"martial": False, "jet": "magique", "portee": 6, "stats": ("Vol", "R"), "malus": ("Ag", "F")},
	"chaman":        {"martial": False, "jet": "magique", "portee": 6, "stats": ("Vol", "F"), "malus": ("F", "Vol")},
	"pretre":        {"martial": False, "jet": "magique", "portee": 6, "stats": ("Vol", "R"), "malus": ("F", "Int")},
	"necromancien":  {"martial": False, "jet": "magique", "portee": 6, "stats": ("Int", "Vol"), "malus": ("R", "F")},
	"menestrel":     {"martial": False, "jet": "magique", "portee": 6, "stats": ("Cha", "Vol"), "malus": ("Vol", "Cha")},
	"demoniste":     {"martial": False, "jet": "magique", "portee": 6, "stats": ("Int", "Vol"), "malus": ("Vol", "R")},
}
PORTEE_SOUTIEN = 4


def _e(cle, niveau):
	return ECHELLE[cle][niveau - 1]


def _buffs(stats, valeur, signe=1):
	"""Première caractéristique à plein, les suivantes à moitié."""
	out = {}
	for i, car in enumerate(stats):
		out[car] = signe * (valeur if i == 0 else max(1, valeur // 2))
	return out


def _offensive(n, prof, o, degats=None):
	doc = {"cible": "ennemi", "jet": o.get("jet", prof["jet"]),
		   "portee": o.get("portee", prof["portee"]), "cout_pm": _e("pm", n)}
	if degats:
		doc["effets"] = {"degats": degats}
	return doc


def _zone_lanceur(forme, **dims):
	z = {"forme": forme, "origine": "lanceur"}
	if forme in ("rectangle", "cone"):
		z["orientation"] = "cible"
		z["decalage"] = 1
	z.update(dims)
	return z


def construire_effets(entree, voc):
	"""Champs de jeu d'une entrée (cible, jet, portée, zone, coûts, effets) — ou ValueError."""
	n, o, prof = entree["niveau"], entree["options"], PROFILS[voc]
	arch = entree["archetype"]
	stats = tuple(o.get("stats", prof["stats"]))
	malus = tuple(o.get("malus", prof["malus"]))
	# ── passives ──────────────────────────────────────────────────────────────────
	if arch == "p_carac":
		return {"effets": {"buffs": _buffs(stats, _e("p_pts", n))}}
	if arch == "p_esquive":
		return {"effets": {"esquive": _e("p_esquive", n)}}
	if arch == "p_regen":
		return {"effets": {"regen_pv": 1 if n < 7 else 2}}
	if arch == "p_furtif":
		return {"condition": {"battle_map_tags": list(o["terrains"])},
				"effets": {"furtivite": _e("p_furtivite", n)}}
	# ── actives offensives ────────────────────────────────────────────────────────
	if arch == "frappe":
		return _offensive(n, prof, o, _e("des", n))
	if arch == "sang":
		doc = _offensive(n, prof, o, _e("des_fort", n))
		doc["effets"]["cout_pv"] = _e("cout_pv", n)
		return doc
	if arch == "rituel":
		doc = _offensive(n, prof, o, _e("des_fort", n))
		doc["cout_pm"] = round(_e("pm", n) * 1.3)
		doc["incantation"] = 2 if n < 6 else 3
		return doc
	if arch == "zone_rect":
		doc = _offensive(n, prof, o, _e("des_petite", n))
		doc["zone"] = _zone_lanceur("rectangle", longueur=1, largeur=3)
		return doc
	if arch == "zone_carre":
		rayon = o.get("rayon", 1)
		doc = _offensive(n, prof, o, _e("des_moyenne" if rayon == 1 else "des_large", n))
		doc["zone"] = _zone_lanceur("carre", rayon=rayon)
		return doc
	if arch == "zone_cercle":
		rayon = o.get("rayon", 1)
		doc = _offensive(n, prof, o, _e("des_petite" if rayon == 1 else "des_moyenne", n))
		doc["zone"] = {"forme": "cercle", "origine": "cible", "rayon": rayon}
		return doc
	if arch == "zone_cone":
		nappe = entree["theme"].split("/")[1]
		longueur = LONGUEUR_CONE[nappe]
		cle = {2: "des_petite", 3: "des_moyenne", 4: "des_large"}[longueur]
		doc = _offensive(n, prof, o, _e(cle, n))
		doc["zone"] = _zone_lanceur("cone", longueur=longueur, angle=90)
		return doc
	if arch == "entrave":
		doc = _offensive(n, prof, o, _e("des_entrave", n))
		doc["effets"].update({"buffs": _buffs(malus, _e("malus", n), -1), "duree": _e("duree", n)})
		return doc
	if arch == "poison":
		doc = _offensive(n, prof, o, _e("des_entrave", n))
		doc["effets"].update({"regen_pv": -_e("poison", n), "duree": _e("duree", n)})
		return doc
	if arch == "poison_pm":
		doc = _offensive(n, prof, o, _e("des_entrave", n))
		doc["effets"].update({"regen_pm": -_e("poison_pm", n), "duree": _e("duree", n)})
		return doc
	if arch == "siphon":
		doc = _offensive(n, prof, o, _e("des_entrave", n))
		doc["effets"]["degats_pm"] = _e("siphon", n)
		return doc
	if arch == "drain":
		doc = _offensive(n, prof, o, _e("des", n))
		doc["effets"]["drain_pv"] = _e("drain", n)
		if n >= 7:
			doc["effets"]["drain_max"] = 20
		return doc
	# ── actives de soutien ────────────────────────────────────────────────────────
	if arch == "buff_soi":
		return {"cible": "soi", "portee": 1, "cout_pm": _e("pm", n),
				"effets": {"buffs": _buffs(stats, _e("buff", n)), "duree": _e("duree", n) + 1}}
	if arch == "esquive_soi":
		return {"cible": "soi", "portee": 1, "cout_pm": _e("pm", n),
				"effets": {"esquive": _e("esquive", n), "buffs": _buffs(stats[:1], _e("buff", n) // 2),
						   "duree": _e("duree", n)}}
	if arch == "posture":
		return {"cible": "soi", "portee": 1, "cout_pm": _e("posture_pm", n),
				"maintien": _e("posture_tour", n),
				"effets": {"buffs": _buffs(stats, _e("buff", n) + 3)}}
	if arch == "cri":
		rayon = o.get("rayon", 1)
		return {"cible": "soi", "portee": 1, "cout_pm": _e("pm", n),
				"zone": _zone_lanceur("carre", rayon=rayon),
				"effets": {"buffs": _buffs(stats, round(_e("buff", n) * 0.7)),
						   "duree": _e("duree", n)}}
	if arch == "soin":
		return {"cible": "allie", "portee": o.get("portee", PORTEE_SOUTIEN), "cout_pm": _e("pm", n),
				"effets": {"pv": _e("soin", n)}}
	if arch == "soin_zone":
		return {"cible": "allie", "portee": o.get("portee", PORTEE_SOUTIEN), "cout_pm": _e("pm", n),
				"zone": {"forme": "cercle", "origine": "cible", "rayon": 1},
				"effets": {"pv": round(_e("soin", n) * 0.6)}}
	if arch == "buff_allie":
		return {"cible": "allie", "portee": o.get("portee", PORTEE_SOUTIEN), "cout_pm": _e("pm", n),
				"effets": {"buffs": _buffs(stats, _e("buff", n)), "duree": _e("duree", n)}}
	if arch == "regen_allie":
		return {"cible": "allie", "portee": o.get("portee", PORTEE_SOUTIEN), "cout_pm": _e("pm", n),
				"effets": {"regen_pv": _e("regen", n), "duree": _e("duree", n) + 1}}
	if arch == "pm_allie":
		return {"cible": "allie", "portee": o.get("portee", PORTEE_SOUTIEN), "cout_pm": _e("pm", n),
				"effets": {"pm": _e("pm_allie", n)}}
	if arch == "saut":
		return {"cible": "soi", "portee": 1, "cout_pm": _e("pm", n),
				"effets": {"saut": _e("saut", n)}}
	raise ValueError(f"archétype inconnu : {arch}")


ARCHETYPES_PASSIFS = {"p_carac", "p_esquive", "p_regen", "p_furtif"}


def slug(nom):
	s = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
	return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def construire_doc(entree, voc):
	champs = construire_effets(entree, voc)
	doc = {"_id": "competence:" + entree["options"].get("id", slug(entree["nom"])),
		   "type": "competence", "nom": entree["nom"], "icon": entree["icon"]}
	theme = entree["theme"]
	if theme:
		if "/" in theme:
			impact, nappe = theme.split("/")
			doc["animation"] = PREFIXE_ANIM + impact
			doc["animation_zone"] = PREFIXE_ANIM + nappe
		else:
			doc["animation"] = PREFIXE_ANIM + theme
	doc.update({"description": entree["description"], "vocation": voc,
				"niveau": entree["niveau"], "mode": entree["mode"]})
	if entree["mode"] == "active":
		doc["cout_pm"] = champs.pop("cout_pm")
		for cle in ("maintien", "incantation"):
			if cle in champs:
				doc[cle] = champs.pop(cle)
		if PROFILS[voc]["martial"]:
			doc["sensibilite_charge"] = 0
		for cle in ("cible", "jet", "portee", "zone"):
			if cle in champs:
				doc[cle] = champs.pop(cle)
	if "condition" in champs:
		doc["condition"] = champs.pop("condition")
	doc["effets"] = champs.pop("effets")
	assert not champs, champs
	return doc


# ── Référentiel ───────────────────────────────────────────────────────────────────

def charger_referentiel():
	"""Dump le plus récent + compétences des imports (hors la sortie de CE générateur)."""
	dumps = sorted(f for f in os.listdir(check.DOSSIER_JSONS)
				   if f.startswith("telluris-dump-") and f.endswith(".json"))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	docs = json.load(open(os.path.join(check.DOSSIER_JSONS, dumps[-1]), encoding="utf-8"))["docs"]
	par_id = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}
	competences = {i: d for i, d in par_id.items() if d.get("type") == "competence"}
	for nom in sorted(os.listdir(check.DOSSIER_JSONS)):
		if not nom.endswith("_a_importer.json") or nom == NOM_IMPORT:
			continue
		try:
			contenu = json.load(open(os.path.join(check.DOSSIER_JSONS, nom), encoding="utf-8"))
		except (json.JSONDecodeError, OSError):
			continue
		for d in (contenu if isinstance(contenu, list) else [contenu]):
			if isinstance(d, dict) and str(d.get("_id", "")).startswith("competence:"):
				competences.setdefault(d["_id"], d)
	vocations = {}
	for v in (par_id.get("rules:vocations") or {}).get("value") or []:
		vocations[str(v.get("id"))] = v
	themes = {i[len(PREFIXE_ANIM):]: d for i, d in par_id.items() if i.startswith(PREFIXE_ANIM)}
	return {"dump": dumps[-1], "competences": competences, "vocations": vocations,
			"themes": themes}


def charger_entrees(voc):
	return importlib.import_module(f"competences_1_10.{voc}").ENTREES


def _est_magique(regle_voc):
	return bool(str(regle_voc.get("magie") or "").strip())


def _meme_competence(a, b):
	return all(a.get(k) == b.get(k) for k in ("vocation", "niveau", "mode"))


# ── Construction + gardes ─────────────────────────────────────────────────────────

def construire(ref=None):
	"""→ (docs du lot, docs à émettre, erreurs, compte). Ne lit ni n'écrit de fichier de sortie."""
	ref = ref or charger_referentiel()
	erreurs, lot, a_emettre = [], [], []
	compte = {}
	vocations = ref["vocations"]
	if set(vocations) != set(PROFILS):
		erreurs.append(f"vocations de rules:vocations ≠ PROFILS : "
					   f"{sorted(set(vocations) ^ set(PROFILS))}")
	themes = ref["themes"]
	ids_lot = set()
	for voc in sorted(PROFILS):
		if voc not in vocations:
			continue
		magique = _est_magique(vocations[voc])
		try:
			entrees = charger_entrees(voc)
		except ModuleNotFoundError:
			erreurs.append(f"{voc} : module de données absent (dev/competences_1_10/{voc}.py)")
			continue
		docs_voc = []
		for e in entrees:
			prefixe = f"{voc} niv {e['niveau']} « {e['nom']} »"
			try:
				doc = construire_doc(e, voc)
			except (ValueError, KeyError) as exc:
				erreurs.append(f"{prefixe} : {exc!r}")
				continue
			docs_voc.append(doc)
			passif = e["archetype"] in ARCHETYPES_PASSIFS
			if passif != (e["mode"] == "passive"):
				erreurs.append(f"{prefixe} : archétype {e['archetype']} incompatible avec le mode")
			# thème : présent, actif, sonore ; impact muet seulement sous une nappe de cône
			if e["mode"] == "active":
				parts = (e["theme"] or "").split("/")
				for t in parts:
					if t not in themes:
						erreurs.append(f"{prefixe} : thème `{PREFIXE_ANIM}{t}` absent du dump")
				if all(t in themes for t in parts):
					sonore = themes[parts[-1]].get("son")
					if not sonore:
						erreurs.append(f"{prefixe} : thème `{parts[-1]}` MUET — l'active n'aurait pas de son")
					if (e["archetype"] == "zone_cone") != (len(parts) == 2):
						erreurs.append(f"{prefixe} : un cône exige « impact/nappe », et seul un cône")
					if len(parts) == 2 and parts[1] not in LONGUEUR_CONE:
						erreurs.append(f"{prefixe} : nappe de cône inconnue {parts[1]}")
			cid = doc["_id"]
			if cid in ids_lot:
				erreurs.append(f"{prefixe} : `_id` {cid} en double dans le lot")
			ids_lot.add(cid)
			existant = ref["competences"].get(cid)
			if existant is not None and not _meme_competence(existant, doc):
				erreurs.append(f"{prefixe} : `_id` {cid} DÉJÀ PRIS par une autre compétence "
							   f"({existant.get('vocation')} niv {existant.get('niveau')}) — renommer")
			ids_existants = {i for i in ref["competences"] if i != cid}
			erreurs.extend(check.verifier_competence(doc, prefixe, ids_existants,
													 set(vocations), niveaux=tuple(NIVEAUX)))
			lot.append(doc)
			if existant is None:
				a_emettre.append(doc)
		noms = [d["nom"] for d in docs_voc]
		doublons = sorted({x for x in noms if noms.count(x) > 1})
		if doublons:
			erreurs.append(f"{voc} : noms en double {doublons}")
		# budget des passives neuves
		pts = sum(sum(abs(v) for v in (d["effets"].get("buffs") or {}).values())
				  for d in docs_voc if d["mode"] == "passive")
		if pts > BUDGET_PASSIVES_PTS:
			erreurs.append(f"{voc} : passives neuves = {pts} pts de caract > budget {BUDGET_PASSIVES_PTS}")
		# cardinalités, existantes comprises (hors lot)
		ids_voc = {d["_id"] for d in docs_voc}
		anciens = [c for i, c in ref["competences"].items()
				   if c.get("vocation") == voc and i not in ids_voc]
		compte[voc] = {"magique": magique, "niveaux": {}}
		for niv in NIVEAUX:
			ex_p = sum(1 for c in anciens if c.get("niveau") == niv and c.get("mode") == "passive")
			ex_a = sum(1 for c in anciens if c.get("niveau") == niv and c.get("mode") == "active")
			nv_p = sum(1 for d in docs_voc if d["niveau"] == niv and d["mode"] == "passive")
			nv_a = sum(1 for d in docs_voc if d["niveau"] == niv and d["mode"] == "active")
			compte[voc]["niveaux"][niv] = (ex_p, ex_a, nv_p, nv_a)
			if magique:
				if nv_p:
					erreurs.append(f"{voc} niv {niv} : {nv_p} passive(s) neuve(s) — interdit "
								   f"pour une vocation qui pratique la magie")
				if ex_p + ex_a + nv_a != TOTAL_MAGIE:
					erreurs.append(f"{voc} niv {niv} : {ex_p + ex_a} existante(s) + {nv_a} "
								   f"neuve(s) ≠ {TOTAL_MAGIE} (il en faut "
								   f"{TOTAL_MAGIE - ex_p - ex_a} neuve(s))")
			else:
				if ex_p + nv_p != PASSIVES_SANS_MAGIE:
					erreurs.append(f"{voc} niv {niv} : passives {ex_p} existante(s) + {nv_p} "
								   f"neuve(s) ≠ {PASSIVES_SANS_MAGIE}")
				if ex_a + nv_a != ACTIVES_SANS_MAGIE:
					erreurs.append(f"{voc} niv {niv} : actives {ex_a} existante(s) + {nv_a} "
								   f"neuve(s) ≠ {ACTIVES_SANS_MAGIE}")
	# Un nom porté par deux compétences, toutes vocations confondues, se confond dans la barre
	# d'action et dans l'onglet ⚡ d'un lettré ou d'un compagnon : il est refusé.
	noms = {}
	for c in list(ref["competences"].values()) + lot:
		if c.get("_id") in ids_lot and c not in lot:
			continue
		noms.setdefault(str(c.get("nom", "")).lower(), set()).add(c.get("_id"))
	for d in lot:
		autres = noms.get(d["nom"].lower(), set()) - {d["_id"]}
		if autres:
			erreurs.append(f"{d['vocation']} niv {d['niveau']} « {d['nom']} » : nom déjà porté "
						   f"par {sorted(autres)}")
	return lot, a_emettre, erreurs, compte


# ── Document lisible ──────────────────────────────────────────────────────────────

def _resume_effets(doc):
	e = doc["effets"]
	parts = []
	if e.get("degats"):
		parts.append(f"{e['degats']} dégâts")
	if e.get("degats_pm"):
		parts.append(f"{e['degats_pm']} aux PM")
	if e.get("pv"):
		parts.append(f"+{e['pv']} PV")
	if e.get("pm"):
		parts.append(f"+{e['pm']} PM")
	if e.get("buffs"):
		parts.append(" ".join(f"{k} {v:+d}" for k, v in e["buffs"].items()))
	if e.get("esquive"):
		parts.append(f"esquive {e['esquive']}")
	if e.get("regen_pv"):
		parts.append(f"régén PV {e['regen_pv']:+d}")
	if e.get("regen_pm"):
		parts.append(f"régén PM {e['regen_pm']:+d}")
	if e.get("drain_pv"):
		parts.append(f"drain {e['drain_pv']} %" + (f" (max {e['drain_max']})" if e.get("drain_max") else ""))
	if e.get("saut"):
		parts.append(f"saut {e['saut']} cases")
	if e.get("cout_pv"):
		parts.append(f"coûte {e['cout_pv']} PV")
	if e.get("furtivite"):
		parts.append(f"furtivité {e['furtivite']} ({', '.join(doc['condition']['battle_map_tags'])})")
	if e.get("duree"):
		parts.append(f"{e['duree']} tours")
	return " · ".join(parts)


def _resume_cout(doc):
	if doc["mode"] == "passive":
		return "—"
	txt = f"{doc['cout_pm']} PM"
	if doc.get("maintien"):
		txt += f" + {doc['maintien']}/round"
	if doc.get("incantation"):
		txt += f" · ⏱ {doc['incantation']} PA"
	return txt


def _resume_cible(doc):
	if doc["mode"] == "passive":
		return "permanent"
	txt = doc["cible"]
	if doc.get("jet") and doc["cible"] == "ennemi":
		txt += f" / {doc['jet']}"
	txt += f" / portée {doc['portee']}"
	z = doc.get("zone")
	if z:
		dims = {k: v for k, v in z.items() if k in ("rayon", "longueur", "largeur")}
		txt += f" · {z['forme']} " + " ".join(f"{k} {v}" for k, v in dims.items())
	return txt


def _resume_anim(doc, themes):
	if doc["mode"] == "passive":
		return "—"
	nappe = (doc.get("animation_zone") or doc["animation"])[len(PREFIXE_ANIM):]
	impact = doc["animation"][len(PREFIXE_ANIM):]
	son = (themes.get(nappe) or {}).get("son") or "?"
	nom = f"{impact} + nappe {nappe}" if doc.get("animation_zone") else impact
	return f"{nom} · 🔊 {son}"


def ecrire_doc(lot, compte, ref):
	themes = ref["themes"]
	L = ["# Compétences de vocation — niveaux 1 à 10", "",
		 "**Document GÉNÉRÉ par `python dev/gen_competences_1_10.py`** — ne pas retoucher : les "
		 "données vivent dans `dev/competences_1_10/<vocation>.py`, les valeurs dans l'échelle "
		 "`ECHELLE` du générateur. Import : `jsons/competences_vocations_1_10_a_importer.json`.", "",
		 f"Référentiel : `{ref['dump']}` + `jsons/*_a_importer.json`.", "",
		 "## Règle de compte", "",
		 "À chaque niveau de 1 à 10, **existantes comprises (pièges inclus)** :", "",
		 "| groupe | passives | actives | total |", "|---|---|---|---|",
		 f"| sans magie | {PASSIVES_SANS_MAGIE} | {ACTIVES_SANS_MAGIE} | "
		 f"{PASSIVES_SANS_MAGIE + ACTIVES_SANS_MAGIE} |",
		 f"| avec magie | existantes seulement | complément | {TOTAL_MAGIE} |", "",
		 "Les vocations à magie ne reçoivent **aucune passive** neuve. Chaque active neuve "
		 "porte une animation `animation:capa_*` et son son ; un cône porte en plus sa nappe "
		 "(`animation_zone`). Les passives n'ont pas d'animation : le combat ne les joue jamais.", "",
		 "## Récapitulatif", "",
		 "| vocation | magie | passives neuves | actives neuves | total neuf |", "|---|---|---|---|---|"]
	tot_p = tot_a = 0
	for voc in sorted(compte):
		nv_p = sum(v[2] for v in compte[voc]["niveaux"].values())
		nv_a = sum(v[3] for v in compte[voc]["niveaux"].values())
		tot_p += nv_p
		tot_a += nv_a
		magie = ref["vocations"][voc].get("magie") or "—"
		L.append(f"| {ref['vocations'][voc].get('label', voc)} | {magie} | {nv_p} | {nv_a} | {nv_p + nv_a} |")
	L.append(f"| **total** | | **{tot_p}** | **{tot_a}** | **{tot_p + tot_a}** |")
	L.append("")
	L += ["## Échelle par niveau", "",
		  "| niveau | " + " | ".join(str(n) for n in NIVEAUX) + " |",
		  "|---|" + "---|" * len(NIVEAUX)]
	for cle in ("pm", "des", "des_petite", "des_moyenne", "des_large", "buff", "malus",
				"duree", "poison", "soin", "posture_pm", "posture_tour", "p_pts", "p_esquive"):
		L.append(f"| `{cle}` | " + " | ".join(str(v) for v in ECHELLE[cle]) + " |")
	L.append("")
	par_voc = {}
	for d in lot:
		par_voc.setdefault(d["vocation"], []).append(d)
	for voc in sorted(par_voc):
		regle = ref["vocations"][voc]
		L += [f"## {regle.get('label', voc)} {regle.get('icon', '')}", ""]
		for niv in NIVEAUX:
			ex_p, ex_a, nv_p, nv_a = compte[voc]["niveaux"][niv]
			L += [f"### Niveau {niv} — {ex_p + ex_a} existante(s) + {nv_p + nv_a} neuve(s)", "",
				  "| compétence | mode | coût | cible | effets | animation |", "|---|---|---|---|---|---|"]
			for d in sorted((d for d in par_voc[voc] if d["niveau"] == niv),
							key=lambda d: (d["mode"] != "passive", d["nom"])):
				L.append(f"| {d['icon']} **{d['nom']}** — *{d['description']}* | {d['mode']} | "
						 f"{_resume_cout(d)} | {_resume_cible(d)} | {_resume_effets(d)} | "
						 f"{_resume_anim(d, themes)} |")
			L.append("")
	return "\n".join(L)


def main():
	ref = charger_referentiel()
	lot, a_emettre, erreurs, compte = construire(ref)
	print(f"relu {ref['dump']} · {len(ref['competences'])} compétence(s) en base (dump + imports)")
	if erreurs:
		print(f"\n{len(erreurs)} PROBLÈME(S) — rien n'est écrit :")
		for e in erreurs:
			print(f"  - {e}")
		return 1
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		json.dump(a_emettre, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	with open(SORTIE_DOC, "w", encoding="utf-8", newline="\n") as f:
		f.write(ecrire_doc(lot, compte, ref))
		f.write("\n")
	passives = sum(1 for d in lot if d["mode"] == "passive")
	print(f"OK — {len(lot)} compétence(s) dans le lot ({passives} passives / "
		  f"{len(lot) - passives} actives), {len(a_emettre)} à importer")
	print(f"écrit {os.path.relpath(SORTIE, RACINE)} et {os.path.relpath(SORTIE_DOC, RACINE)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
