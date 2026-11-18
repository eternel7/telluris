#!/usr/bin/env python
# dev/gen_equilibrage_competences.py
# Révision des compétences de vocation (décisions de l'Auteur, 18/11/2026) :
#
#  1. PASSIVES DE CARACTÉRISTIQUE — barème par niveau, cumul LIBRE entre passives, prix inchangé :
#       principale : niv0 → 1/2 · niv1 → 2/3 · niv2 → 3/4 · niv3-4 → 4/5 · niv5+ → 5 (jamais plus) ;
#                    sous le niv5, la valeur haute quand la carac est le SEUL effet, sinon la basse ;
#       secondaire : à partir du niv5, +1 · niv6 +2 · niv7 +3 · niv8 +4 · niv9-10 +5 (≤ principale) ;
#                    ajoutée (thématique : `SECONDAIRES` par vocation) si la passive n'en a pas ;
#                    sous le niv5, une secondaire déjà présente garde +1 ;
#                    deux caracs au plus (une troisième disparaît) ; la Vitesse `V` reste à +1.
#     ESQUIVE (ne s'achète pas en points) : PLAFONNÉE au barème × 4 (20 au plus), jamais relevée.
#     Bonus FORMULÉ (`{R/12}`) : formule gardée, diviseur recalculé pour n'atteindre la valeur
#     du barème qu'au plafond humain de la carac source (`PLAFOND_SOURCE`).
#
#  2. EXIGENCES DE CARACTÉRISTIQUE (champ `exigences`, lu par `utils/exigence_caract.py`) —
#     posées SEULEMENT sur les compétences HORS NORME : puissance ≥ 130 % de la médiane des
#     compétences de même mode et même famille d'effet, niveaux voisins compris (n-1 … n+1).
#       seuil = base + 3 × niv_eff     base : 20 (F, R, Ag, Ch) · 30 (Vol, Int, Cha)
#       niv_eff = niv + 2 (≥ 130 %) · niv + 4 (≥ 180 %), plafonné à 10
#       principale dès le niv0 ; secondaire (base + 1,5 × niv_eff) à partir du niv6.
#     Les autres compétences n'ont AUCUNE exigence (le champ leur est retiré s'il traînait).
#
# ⚠️ PUT COMPLET à l'import : chaque doc est RELU dans le dump le plus récent, seuls `effets.buffs`
# et `exigences` changent ; seuls les docs qui CHANGENT sont écrits (régénération idempotente).
#
# Usage : python dev/gen_equilibrage_competences.py
# Sorties :
#   jsons/equilibrage_competences_a_importer.json
#   docs/equilibrage_competences.md   (GÉNÉRÉ : la liste à relire)

import copy
import glob
import json
import math
import os
import re
import statistics
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils import exigence_caract   # noqa: E402

SORTIE = "jsons/equilibrage_competences_a_importer.json"
DOC = "docs/equilibrage_competences.md"

SEUIL_HORS_NORME = 1.3
SEUIL_TRES_HORS_NORME = 1.8
NIV_SECONDAIRE_EXIGENCE = 6

# Ordre de préférence des caracs d'une vocation : la 1re est la principale par défaut, la
# suivante ≠ principale sert de secondaire (passive à une carac, exigence sans 2e carac lue).
SECONDAIRES = {
	"guerrier": ["F", "R", "Vol"], "barbare": ["F", "R", "Vol"], "forestier": ["Ag", "Ch", "R"],
	"duelliste": ["Ag", "Cha", "Vol"], "assassin": ["Ag", "F", "Vol"], "voleur": ["Ag", "Ch", "Cha"],
	"moine": ["Vol", "Ag", "R"], "elementaliste": ["Int", "Vol", "R"], "mage": ["Int", "Vol", "R"],
	"illusionniste": ["Int", "Ag", "Cha"], "lettre": ["Int", "Vol", "Cha"],
	"druide": ["Vol", "R", "Cha"], "chaman": ["Vol", "R", "Int"], "necromancien": ["Vol", "Int", "R"],
	"demoniste": ["Int", "Vol", "R"], "pretre": ["Vol", "Int", "Cha"], "paladin": ["Vol", "R", "Cha"],
	"templier": ["R", "Vol", "F"], "repurgateur": ["Vol", "Ch", "Int"], "menestrel": ["Cha", "Int", "Vol"],
}
# Plafond humain de la carac SOURCE d'un bonus formulé (diviseur recalculé dessus).
PLAFOND_SOURCE = {"F": 50, "R": 50, "Ag": 60, "Ch": 60, "Vol": 70, "Int": 70, "Cha": 80}

FACTEUR_ESQUIVE = 4

STATS = ("F", "R", "Ag", "Ch", "Vol", "Int", "Cha")
RE_VAR = re.compile(r"\{\s*([A-Za-z]+)\s*/\s*(\d+(?:\.\d+)?)\s*\}")


def dernier_dump():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json"))
				   + glob.glob(os.path.join(RACINE, "telluris-dump-*.json")),
				   key=os.path.basename)
	if not dumps:
		sys.exit("Aucun dump telluris-dump-*.json")
	return dumps[-1]


# ── Barème des passives ──────────────────────────────────────────────────────────

def bareme_principale(niv: int, seul_effet: bool) -> int:
	if niv >= 5:
		return 5
	bas = min(4, niv + 1)
	return min(5, bas + 1) if seul_effet else bas


def bareme_secondaire(niv: int) -> int:
	return 0 if niv < 5 else min(5, niv - 4)


def _valeur_buff(v, caract_estimee=None) -> float:
	if isinstance(v, (int, float)):
		return float(v)
	m = RE_VAR.search(str(v))
	if m:
		return (caract_estimee or PLAFOND_SOURCE.get(m.group(1), 50)) / float(m.group(2))
	return 0.0


def _formule_bornee(texte: str, cible: int) -> str:
	m = RE_VAR.search(str(texte))
	src = m.group(1)
	div = max(1, math.ceil(PLAFOND_SOURCE.get(src, 50) / max(1, cible)))
	return "{%s/%d}" % (src, div)


def reecrire_passive(doc: dict) -> dict | None:
	"""Nouveaux `buffs` d'une passive de caractéristique, ou None (pas de buff de carac)."""
	eff = doc.get("effets") or {}
	buffs = eff.get("buffs") or {}
	if not buffs:
		return None
	niv = int(doc.get("niveau") or 0)
	voc = doc.get("vocation")
	ordre = sorted(buffs, key=lambda k: -abs(_valeur_buff(buffs[k])))
	ordre_carac = [k for k in ordre if k != "V"]
	vitesse = "V" in buffs
	autres_effets = any(k not in ("buffs",) for k in eff) or bool(doc.get("zone"))
	if not ordre_carac:
		return dict(buffs)
	principale = ordre_carac[0]
	secondaire = ordre_carac[1] if len(ordre_carac) > 1 else None
	seul = not autres_effets and secondaire is None and not vitesse
	out = {}
	val_p = bareme_principale(niv, seul and niv < 5)
	out[principale] = (_formule_bornee(buffs[principale], val_p)
					   if isinstance(buffs[principale], str) else val_p)
	if vitesse:
		out["V"] = 1      # la Vitesse (4 à 8) tient lieu de secondaire, à +1
		return out
	val_s = min(bareme_secondaire(niv), val_p)   # jamais au-dessus de la principale
	if val_s:
		if secondaire is None:
			secondaire = next((s for s in SECONDAIRES.get(voc, []) if s != principale), None)
		if secondaire:
			v = buffs.get(secondaire)
			out[secondaire] = _formule_bornee(v, val_s) if isinstance(v, str) else val_s
	elif secondaire is not None:
		out[secondaire] = 1
		out[principale] = (_formule_bornee(buffs[principale], bareme_principale(niv, False))
						   if isinstance(buffs[principale], str) else bareme_principale(niv, False))
	return out


def plafond_esquive(doc: dict):
	"""Esquive d'une passive PLAFONNÉE au barème × 4 (l'esquive ne s'achète pas en points) :
	niv0 4/8 · niv1 8/12 · niv2 12/16 · niv3-4 16/20 · niv5+ 20. Jamais relevée. None si absente."""
	eff = doc.get("effets") or {}
	v = eff.get("esquive")
	if v is None:
		return None
	niv = int(doc.get("niveau") or 0)
	seul = set(eff) == {"esquive"} and not doc.get("zone")
	plafond = FACTEUR_ESQUIVE * bareme_principale(niv, seul)
	if isinstance(v, str):
		return _formule_bornee(v, plafond) if _valeur_buff(v) > plafond else v
	return min(int(v), plafond)


# ── Mesure de puissance ──────────────────────────────────────────────────────────

def _esperance(formule, niv: int) -> float:
	if formule is None or formule == "":
		return 0.0
	s = str(formule).replace(" ", "")

	def _var(m):
		return str(exigence_caract.seuil(m.group(1), niv) / float(m.group(2)))
	s = RE_VAR.sub(_var, s)
	total = 0.0
	for signe, terme in re.findall(r"([+-]?)([^+-]+)", s):
		m = re.fullmatch(r"(\d*)[dD](\d+(?:\.\d+)?)", terme)
		try:
			v = (int(m.group(1) or 1)) * (float(m.group(2)) + 1) / 2 if m else float(terme)
		except ValueError:
			return 0.0
		total += -v if signe == "-" else v
	return max(0.0, total)


def puissance(doc: dict) -> tuple:
	"""(famille, score) : `off` (dégâts) ou `sup` (buffs, esquive, régén, soins)."""
	eff = doc.get("effets") or {}
	niv = int(doc.get("niveau") or 0)
	zone = 1.6 if doc.get("zone") else 1.0
	off = _esperance(eff.get("degats"), niv) + 0.5 * _esperance(eff.get("degats_pm"), niv) \
		+ 0.5 * _esperance(eff.get("drain_pv"), niv)
	buffs = sum(abs(_valeur_buff(v, exigence_caract.seuil("F", niv))) for k, v in (eff.get("buffs") or {}).items()
				if k != "V") + 5 * abs(_valeur_buff((eff.get("buffs") or {}).get("V", 0)))
	sup = buffs + abs(_valeur_buff(eff.get("esquive", 0))) + 3 * abs(_valeur_buff(eff.get("regen_pv", 0))) \
		+ 2 * abs(_valeur_buff(eff.get("regen_pm", 0))) + 0.5 * _valeur_buff(eff.get("furtivite", 0)) \
		+ 0.5 * _valeur_buff(eff.get("pv", 0)) + 0.5 * _valeur_buff(eff.get("pm", 0)) \
		+ _esperance(eff.get("soin"), niv)
	if (doc.get("mode") or "passive") == "active":
		duree = eff.get("duree")
		sup *= min(5, int(duree)) if isinstance(duree, (int, float)) and duree else 2
	if off > 0:
		return "off", off * zone
	return "sup", sup * zone


# ── Exigences ────────────────────────────────────────────────────────────────────

def caracs_lues(doc: dict) -> list:
	eff = doc.get("effets") or {}
	vues = []
	for cle in ("degats", "degats_pm", "drain_pv", "soin"):
		for m in RE_VAR.finditer(str(eff.get(cle) or "")):
			if m.group(1) in STATS and m.group(1) not in vues:
				vues.append(m.group(1))
	buffs = eff.get("buffs") or {}
	for k in sorted(buffs, key=lambda k: -_valeur_buff(buffs[k])):
		if k in STATS and _valeur_buff(buffs[k]) > 0 and k not in vues:
			vues.append(k)
	return vues


def exigences_de(doc: dict, ratio: float) -> dict:
	niv = int(doc.get("niveau") or 0)
	niv_eff = min(10, niv + (4 if ratio >= SEUIL_TRES_HORS_NORME else 2))
	vues = caracs_lues(doc)
	pref = SECONDAIRES.get(doc.get("vocation"), ["F"])
	principale = vues[0] if vues else pref[0]
	out = {principale: exigence_caract.seuil(principale, niv_eff)}
	if niv >= NIV_SECONDAIRE_EXIGENCE:
		sec = next((s for s in vues[1:] + pref if s != principale), None)
		if sec:
			out[sec] = exigence_caract.seuil(sec, niv_eff, secondaire=True)
	return out


def main():
	chemin = dernier_dump()
	docs = json.load(open(chemin, encoding="utf-8"))["docs"]
	comps = [d for d in docs if d.get("type") == "competence" and d.get("vocation") not in (None, "monstre")]
	neufs = {d["_id"]: copy.deepcopy(d) for d in comps}

	# 1. Passives réécrites AVANT la mesure : leur norme est celle d'après le barème.
	passives = []
	for d in neufs.values():
		if (d.get("mode") or "passive") != "passive":
			continue
		eff = d.get("effets") or {}
		avant = {k: eff[k] for k in ("buffs", "esquive") if k in eff}
		b = reecrire_passive(d)
		if b is not None:
			eff["buffs"] = b
		e = plafond_esquive(d)
		if e is not None:
			eff["esquive"] = e
		apres = {k: eff[k] for k in ("buffs", "esquive") if k in eff}
		if apres != avant:
			passives.append((d["_id"], avant, apres))

	# 2. Hors-norme et exigences.
	mesures = {i: puissance(d) for i, d in neufs.items()}
	hors_norme = []
	for i, d in neufs.items():
		fam, score = mesures[i]
		if score <= 0:
			d.pop("exigences", None)
			continue
		niv = int(d.get("niveau") or 0)
		mode = d.get("mode") or "passive"
		pairs = [mesures[j][1] for j, e in neufs.items()
				 if (e.get("mode") or "passive") == mode and mesures[j][0] == fam
				 and abs(int(e.get("niveau") or 0) - niv) <= 1 and mesures[j][1] > 0]
		med = statistics.median(pairs) if len(pairs) >= 3 else score
		ratio = score / med if med else 1.0
		if ratio >= SEUIL_HORS_NORME:
			d["exigences"] = exigences_de(d, ratio)
			hors_norme.append((d, fam, score, med, ratio))
		else:
			d.pop("exigences", None)

	ecrits = []
	for i, d in neufs.items():
		avant = next(c for c in comps if c["_id"] == i)
		if d != avant:
			d.pop("_rev", None)
			ecrits.append(d)
	ecrits.sort(key=lambda d: d["_id"])
	ids = [d["_id"] for d in ecrits]
	assert len(ids) == len(set(ids)), "collision d'_id"

	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(ecrits, f, ensure_ascii=False, indent=1)

	lignes = ["# Équilibrage des compétences (GÉNÉRÉ par dev/gen_equilibrage_competences.py)", "",
			  f"Dump : `{os.path.basename(chemin)}` · {len(ecrits)} docs écrits · "
			  f"{len(passives)} passives réécrites · {len(hors_norme)} compétences hors norme.", "",
			  "## Compétences hors norme → exigences", "",
			  "| Vocation | Niv | Compétence | Mode | Famille | Puissance | Médiane | Ratio | Exigences |",
			  "|---|---|---|---|---|---|---|---|---|"]
	for d, fam, score, med, ratio in sorted(hors_norme, key=lambda t: (t[0]["vocation"], t[0]["niveau"], t[0]["_id"])):
		ex = " · ".join(f"{k} {v}" for k, v in d["exigences"].items())
		lignes.append(f"| {d['vocation']} | {d['niveau']} | {d['nom']} (`{d['_id'].split(':', 1)[1]}`) | "
					  f"{d.get('mode')} | {fam} | {score:.1f} | {med:.1f} | {ratio:.2f} | {ex} |")
	lignes += ["", "## Passives réécrites", "", "| Compétence | Avant | Après |", "|---|---|---|"]
	for i, av, ap in sorted(passives):
		lignes.append(f"| `{i.split(':', 1)[1]}` | {json.dumps(av, ensure_ascii=False)} | "
					  f"{json.dumps(ap, ensure_ascii=False)} |")
	with open(os.path.join(RACINE, DOC), "w", encoding="utf-8", newline="\n") as f:
		f.write("\n".join(lignes) + "\n")
	print(f"{len(ecrits)} docs → {SORTIE} ; {len(hors_norme)} hors norme ; {len(passives)} passives ; doc {DOC}")


if __name__ == "__main__":
	main()
