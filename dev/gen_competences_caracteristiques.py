#!/usr/bin/env python
"""Compétences 1 → 10 à FORMULES DE CARACTÉRISTIQUES : leur effet principal lit le lanceur.

    python dev/gen_competences_caracteristiques.py [--dump jsons/telluris-dump-*.json] [--sortie …]

Sorties (rien n'est écrit si une garde échoue) :
  · jsons/competences_caracteristiques_a_importer.json — carte d'import de /admin ;
  · docs/competences_caracteristiques.md — avant → après, GÉNÉRÉ.

POURQUOI. `dev/gen_competences_1_10.py` tire toutes ses valeurs d'une échelle FIXE par niveau
(`ECHELLE`) : aucune compétence ne lisait une caractéristique, alors que le moteur résout les
jetons `{Car/n}` pour les compétences comme pour les sorts (`sorts.resoudre_effets`, branche
`competence` de `resolve_action`, `utiliser_competence`). Ce générateur RETOUCHE les actives de
ce lot déjà en base : l'effet principal de chacune passe à une formule, sur une
caractéristique choisie par vocation ET par forme d'effet (`CARACS`).

ÉQUILIBRE — la valeur d'origine est conservée pour une caractéristique de RÉFÉRENCE
`REF(niveau) = 30 + 4 × niveau` (34 au niveau 1, 70 au niveau 10 : les races partent de
20-30, plafonnent à 50-80). En dessous la compétence faiblit, au-dessus elle monte :
  · dés `XdY+K` : `K` → `{Car/d}` ; sans `K`, la TAILLE du dé → `XD{Car/d}` ;
  · entier `v` (buff, malus, soin, PM, esquive, poison, régén) : moitié fixe, moitié formule
    `c+{Car/d}` — un personnage faible dans la caractéristique garde la moitié de l'effet.
Diviseurs pris dans `DIVISEURS` (lisibles), buffs ≥ `{Car/3}` (garde des sorts), durées
intactes, V jamais en formule. Le saut n'a pas de formule (`saut` hors `FORMULE_CLES_ENTIERES`).

IDEMPOTENT — la base fait foi (PUT complet, CLAUDE.md §11) : le doc émis est le doc RELU du
dump, seul son `effets` change. Un doc qui porte déjà une formule est tenu pour converti et
n'est pas réémis ; un doc absent du dump est sauté (pas encore importé).
"""

import argparse
import copy
import json
import os
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_competences_doc as check  # noqa: E402
import gen_competences_1_10 as lot_1_10  # noqa: E402
from utils import sorts as S  # noqa: E402
from utils.competences import normaliser_competence  # noqa: E402

DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "competences_caracteristiques_a_importer.json")
SORTIE_DOC = os.path.join(RACINE, "docs", "competences_caracteristiques.md")

# Diviseurs autorisés : de quoi lire « {F/6} » sans calculette.
DIVISEURS = (2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 25, 30)
DIVISEUR_BUFF_MIN = 3        # garde des sorts : aucun buff au-delà de {Car/3}
TOLERANCE = 0.15             # écart admis à la référence (au moins 1 point)


def ref(niveau):
	"""Caractéristique de RÉFÉRENCE d'un niveau : la valeur d'origine y est conservée."""
	return 30 + 4 * int(niveau)


# Caractéristique lue, par vocation et par FORME d'effet :
#   frappe  — dégâts d'une frappe (simple, zone, saignée, rituel, drain) ;
#   entrave — malus, poison, siphon de PM (ce qui affaiblit la cible) ;
#   soutien — buff, posture, cri, esquive, soin, régén, PM rendus.
CARACS = {
	"guerrier":      {"frappe": "F",   "entrave": "F",   "soutien": "Vol"},
	"barbare":       {"frappe": "F",   "entrave": "R",   "soutien": "R"},
	"forestier":     {"frappe": "Ag",  "entrave": "Int", "soutien": "Ch"},
	"duelliste":     {"frappe": "Ag",  "entrave": "Ag",  "soutien": "Cha"},
	"assassin":      {"frappe": "Ag",  "entrave": "Int", "soutien": "Ag"},
	"voleur":        {"frappe": "Ag",  "entrave": "Int", "soutien": "Ch"},
	"moine":         {"frappe": "Ag",  "entrave": "Vol", "soutien": "Vol"},
	"paladin":       {"frappe": "F",   "entrave": "Vol", "soutien": "Vol"},
	"templier":      {"frappe": "F",   "entrave": "Vol", "soutien": "R"},
	"repurgateur":   {"frappe": "Vol", "entrave": "Int", "soutien": "Vol"},
	"elementaliste": {"frappe": "Int", "entrave": "Int", "soutien": "Vol"},
	"mage":          {"frappe": "Int", "entrave": "Int", "soutien": "Int"},
	"illusionniste": {"frappe": "Int", "entrave": "Cha", "soutien": "Cha"},
	"lettre":        {"frappe": "Int", "entrave": "Int", "soutien": "Vol"},
	"druide":        {"frappe": "Vol", "entrave": "Int", "soutien": "Vol"},
	"chaman":        {"frappe": "Vol", "entrave": "Vol", "soutien": "Cha"},
	"pretre":        {"frappe": "Vol", "entrave": "Vol", "soutien": "Vol"},
	"necromancien":  {"frappe": "Int", "entrave": "Vol", "soutien": "Int"},
	"menestrel":     {"frappe": "Cha", "entrave": "Cha", "soutien": "Cha"},
	"demoniste":     {"frappe": "Int", "entrave": "Vol", "soutien": "Vol"},
}

_RE_DES = re.compile(r"^(\d+)D(\d+)(?:\+(\d+))?$")


def _diviseur(ref_val, cible, minimum=2):
	"""Diviseur de `DIVISEURS` (≥ `minimum`) dont `ref_val // d` approche le mieux `cible` ;
	à écart égal, le plus GRAND (la formule la plus prudente)."""
	candidats = [d for d in DIVISEURS if d >= minimum]
	return min(candidats, key=lambda d: (abs(ref_val // d - cible), -d))


def formule_des(notation, car, niveau):
	"""`"3D8+6"` → `"3D8+{F/12}"` ; `"2D6"` → `"2D{F/6}"`. None si la notation ne se lit pas."""
	m = _RE_DES.match(str(notation or "").replace(" ", "").upper())
	if not m:
		return None
	n, faces, k = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
	r = ref(niveau)
	if k:
		return f"{n}D{faces}+{{{car}/{_diviseur(r, k)}}}"
	return f"{n}D{{{car}/{_diviseur(r, faces)}}}"


def formule_entier(valeur, car, niveau, minimum=2):
	"""`v` → `"c+{Car/d}"` (moitié fixe, moitié formule), signe conservé : `-8` → `"-4-{Ag/8}"`."""
	signe = -1 if valeur < 0 else 1
	v = abs(int(valeur))
	part = (v + 1) // 2
	fixe = v - part
	jeton = f"{{{car}/{_diviseur(ref(niveau), part, minimum)}}}"
	if signe > 0:
		return f"{fixe}+{jeton}" if fixe else jeton
	return f"-{fixe}-{jeton}" if fixe else f"-{jeton}"


def convertir(doc):
	"""→ (effets retouchés, champ converti, caractéristique) ou None si rien à convertir."""
	eff = copy.deepcopy(doc.get("effets") or {})
	voc, niv = doc["vocation"], int(doc["niveau"])
	caracs = CARACS[voc]
	buffs = eff.get("buffs") or {}
	negatifs = [c for c, v in buffs.items() if isinstance(v, int) and v < 0 and c != "V"]
	positifs = [c for c, v in buffs.items() if isinstance(v, int) and v > 0 and c != "V"]
	if doc.get("cible") == "ennemi":
		if negatifs:                                   # entrave : le malus principal
			car, cle = caracs["entrave"], negatifs[0]
			buffs[cle] = formule_entier(buffs[cle], car, niv, DIVISEUR_BUFF_MIN)
			return eff, f"buffs.{cle}", car
		for cle in ("regen_pv", "regen_pm"):           # poison
			if isinstance(eff.get(cle), int) and eff[cle] < 0:
				car = caracs["entrave"]
				eff[cle] = formule_entier(eff[cle], car, niv)
				return eff, cle, car
		if eff.get("degats_pm"):                       # siphon
			car = caracs["entrave"]
			f = formule_des(eff["degats_pm"], car, niv)
			if f:
				eff["degats_pm"] = f
				return eff, "degats_pm", car
		if eff.get("degats"):                          # frappe, zone, saignée, rituel, drain
			car = caracs["frappe"]
			f = formule_des(eff["degats"], car, niv)
			if f:
				eff["degats"] = f
				return eff, "degats", car
		return None
	car = caracs["soutien"]
	if positifs:                                       # buff, posture, cri
		cle = positifs[0]
		buffs[cle] = formule_entier(buffs[cle], car, niv, DIVISEUR_BUFF_MIN)
		return eff, f"buffs.{cle}", car
	for cle in ("pv", "pm", "esquive", "regen_pv"):    # soin, PM rendus, esquive, régén
		if isinstance(eff.get(cle), int) and eff[cle] > 0:
			eff[cle] = formule_entier(eff[cle], car, niv)
			return eff, cle, car
	return None                                        # saut : pas de formule possible


def _lire(effets, champ, caracts):
	"""Valeur d'un champ une fois les formules résolues (dés : moyenne, sans tirage)."""
	res = S.resoudre_effets(S._bonus_dict(effets), caracts, des_fn=lambda _n: 0)
	if champ.startswith("buffs."):
		return res.get("buffs", {}).get(champ[6:], 0)
	val = res.get(champ)
	if isinstance(val, str):
		m = _RE_DES.match(val.replace(" ", "").upper())
		return int(m.group(1)) * (int(m.group(2)) + 1) / 2 + int(m.group(3) or 0) if m else 0
	return val or 0


def ids_du_lot():
	"""`_id` des compétences du lot 1 → 10, relus des DONNÉES du générateur (pas de son fichier
	de sortie, qui se vide une fois le lot importé).

	⚠️ Les entrées LIBRES (`competences_1_10.L`) sont exclues : leurs effets sont écrits à la
	main, formules comprises, et `gen_competences_1_10` les émet lui-même. Les convertir ici
	ferait émettre DEUX contenus pour un même `_id` — le dernier importé gagnerait."""
	out = {}
	for voc in sorted(lot_1_10.PROFILS):
		for e in lot_1_10.charger_entrees(voc):
			if e["archetype"] == "libre":
				continue
			out[lot_1_10.construire_doc(e, voc)["_id"]] = voc
	return out


def generer(base):
	"""→ (docs à émettre, lignes du rapport, erreurs, compte des sautés)."""
	erreurs, docs, lignes = [], [], []
	sautes = {"absent": 0, "passive": 0, "deja": 0, "sans_formule": 0}
	vocations = {str(v.get("id")) for v in (base.get("rules:vocations") or {}).get("value") or []}
	if set(CARACS) != set(lot_1_10.PROFILS):
		erreurs.append(f"CARACS ≠ PROFILS : {sorted(set(CARACS) ^ set(lot_1_10.PROFILS))}")
	ids_base = {i for i in base if i.startswith("competence:")}
	for cid, voc in sorted(ids_du_lot().items()):
		existant = base.get(cid)
		if existant is None:
			sautes["absent"] += 1
			continue
		if existant.get("mode") != "active":
			sautes["passive"] += 1
			continue
		if re.search(r"\{[A-Za-z]", json.dumps(existant.get("effets") or {}) + str(existant.get("portee", ""))):
			sautes["deja"] += 1
			continue
		conv = convertir(existant)
		if conv is None:
			sautes["sans_formule"] += 1
			continue
		effets, champ, car = conv
		doc = {k: v for k, v in existant.items() if k != "_rev"}
		doc["effets"] = effets
		prefixe = f"{voc} niv {doc['niveau']} « {doc['nom']} »"
		# gardes : mêmes invariants que le lot d'origine, mêmes prédicats, valeur à la référence
		erreurs.extend(check.verifier_competence(doc, prefixe, ids_base - {cid}, vocations or None,
												 niveaux=tuple(lot_1_10.NIVEAUX)))
		avant, apres = normaliser_competence(existant), normaliser_competence(doc)
		if apres is None:
			erreurs.append(f"{prefixe} : rejeté par normaliser_competence")
			continue
		if (S.capacite_utilisable_combat(avant) != S.capacite_utilisable_combat(apres)
				or S.effets_agissent_sur_cible(avant["effets"]) != S.effets_agissent_sur_cible(S._vue_indicative(apres["effets"]))):
			erreurs.append(f"{prefixe} : l'éligibilité au combat a changé")
		a_ref = {c: ref(doc["niveau"]) for c in S.CARACTS_FORMULE}
		v0, v1 = _lire(existant["effets"], champ, a_ref), _lire(effets, champ, a_ref)
		if abs(v1 - v0) > max(1, abs(v0) * TOLERANCE):
			erreurs.append(f"{prefixe} : {champ} {v0} → {v1} à la référence {ref(doc['niveau'])}")
		bas = _lire(effets, champ, {c: 20 for c in S.CARACTS_FORMULE})
		haut = _lire(effets, champ, {c: 80 for c in S.CARACTS_FORMULE})
		docs.append(doc)
		formule = effets["buffs"][champ[6:]] if champ.startswith("buffs.") else effets[champ]
		origine = existant["effets"]["buffs"][champ[6:]] if champ.startswith("buffs.") else existant["effets"][champ]
		lignes.append((voc, doc["niveau"], doc["nom"], champ, origine, formule, car, bas, haut))
	return docs, lignes, erreurs, sautes


def ecrire_doc(lignes, dump):
	L = ["# Compétences 1 → 10 à formules de caractéristiques", "",
		 "**Document GÉNÉRÉ par `python dev/gen_competences_caracteristiques.py`** — ne pas "
		 "retoucher. Import : `jsons/competences_caracteristiques_a_importer.json`.", "",
		 f"Référentiel : `{dump}`. Valeur d'origine conservée à la caractéristique de référence "
		 "`30 + 4 × niveau` ; colonnes « à 20 » / « à 80 » = valeur résolue (dés : moyenne).", ""]
	par_voc = {}
	for ligne in lignes:
		par_voc.setdefault(ligne[0], []).append(ligne)
	for voc in sorted(par_voc):
		L += [f"## {voc}", "", "| niv | compétence | champ | avant | après | à 20 | à 80 |",
			  "|---|---|---|---|---|---|---|"]
		for _v, niv, nom, champ, avant, apres, _car, bas, haut in sorted(par_voc[voc], key=lambda x: (x[1], x[2])):
			L.append(f"| {niv} | {nom} | `{champ}` | `{avant}` | `{apres}` | {bas:g} | {haut:g} |")
		L.append("")
	return "\n".join(L)


def charger_dump(chemin):
	if not chemin:
		dumps = sorted(f for f in os.listdir(DOSSIER_JSONS)
					   if f.startswith("telluris-dump-") and f.endswith(".json"))
		if not dumps:
			raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez --dump.")
		chemin = os.path.join(DOSSIER_JSONS, dumps[-1])
	print("source : %s" % os.path.relpath(chemin, RACINE))
	return os.path.basename(chemin), json.load(open(chemin, encoding="utf-8"))


def main():
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	parser = argparse.ArgumentParser(description="Compétences 1 → 10 à formules de caractéristiques")
	parser.add_argument("--dump", help="dump à relire (défaut : le plus récent de jsons/)")
	parser.add_argument("--sortie", default=SORTIE, help="fichier écrit")
	args = parser.parse_args()

	nom_dump, dump = charger_dump(args.dump)
	base = {d["_id"]: d for d in dump["docs"] if isinstance(d, dict) and d.get("_id")}
	docs, lignes, erreurs, sautes = generer(base)
	if erreurs:
		print("\n⚠️ %d erreur(s) — RIEN n'est écrit :" % len(erreurs))
		for e in erreurs:
			print("   " + e)
		return 1
	print("sautées : %d absente(s) du dump, %d passive(s), %d déjà à formule, %d sans champ "
		  "convertible (saut)" % (sautes["absent"], sautes["passive"], sautes["deja"],
								  sautes["sans_formule"]))
	if not docs:
		print("Tout est déjà converti. Aucun fichier écrit.")
		return 0
	with open(args.sortie, "w", encoding="utf-8", newline="\n") as f:
		json.dump(docs, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	with open(SORTIE_DOC, "w", encoding="utf-8", newline="\n") as f:
		f.write(ecrire_doc(lignes, nom_dump))
		f.write("\n")
	print("écrit %s : %d compétence(s) à formule, et %s" % (
		os.path.relpath(args.sortie, RACINE), len(docs), os.path.relpath(SORTIE_DOC, RACINE)))
	return 0


if __name__ == "__main__":
	sys.exit(main())
