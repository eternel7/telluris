"""Relie la France à l'Espagne et à l'Italie, et pose Rome sur la carte d'Italie.

MÊME MÉTHODE que `gen_plaine_europeenne.py` (on ne change de carte QUE par une connexion ; le
bord d'une carte est une borne) :
  · France ↔ Espagne : côté France, sa rangée SUD accessible (`FRANCE_Y_SUD`, sud fermé par
    les murs nav peints) ; côté Espagne, sa limite NORD accessible — la côte cantabrique
    (case murée au nord) ou, à l'est, le haut de la carte. ⚠️ Cases FIXÉES sur l'image et non
    calculées : la grille de l'Espagne a toutes ses cases à 1 et sa mer est dans la zone
    principale, « la plus au nord » tomberait en pleine mer Cantabrique.
  · France ↔ Italie : côté France, sa colonne EST accessible (`FRANCE_X_EST`, est fermé) ;
    côté Italie, la case de la zone principale la plus à l'OUEST de la rangée correspondante.
  · Italie ↔ Rome : sur l'Italie, la case de Rome et ses voisines (une par lien) ; dans
    Rome, une sortie par route qui quitte la carte (case libre la plus proche du point visé).
  Chaque case est éprouvée dans la zone principale de SA carte (`zone_principale`, règle de
  marche d'exploration, grille et nav DU DUMP) : sinon lot refusé.

`lieu:rome` reçoit `lieu_parent: "lieu:italie"` : le doc est RELU du dump et réémis entier
avec ce seul champ ajouté (import = PUT complet, CLAUDE.md §11) — dump frais exigé.

REJOUABLE : toutes les connexions déjà en base et Rome déjà rattachée ⇒ AUCUN fichier ; une
partie seulement des `_id` déjà prise ⇒ lot refusé.

Usage :
  python dev/gen_france_espagne_italie.py [--dump jsons/telluris-dump-….json]

Sortie : jsons/france_espagne_italie_a_importer.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_plaine_europeenne import (  # noqa: E402
	FRANCE, cases_autour, case_proche, connexion, zone_principale)

RACINE = ggi.RACINE
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "france_espagne_italie_a_importer.json")

ESPAGNE = "lieu:espagne"
ITALIE = "lieu:italie"
ROME = "lieu:rome"

# Bords accessibles de la France (murs nav peints : rangée 47 fermée au sud, colonne 86 à l'est).
FRANCE_Y_SUD = 47
FRANCE_X_EST = 86

# France ↔ Espagne : (x sur la France, case sur l'Espagne), d'ouest en est — Asturies et
# Cantabrie (côte murée au nord), Navarre et Catalogne (haut de la carte, sous le cadre de
# parchemin des rangées 0-1, resté à 1 dans `cells`).
PASSAGES_ESPAGNE = ((8, (24, 4)), (20, (40, 5)), (32, (56, 2)), (44, (68, 2)))

# France ↔ Italie : (y sur la France, y sur l'Italie), du nord au sud — Valais, Savoie,
# Dauphiné, comté de Nice. Le cadre de `italie.png` est déjà à 0.
PASSAGES_ITALIE = ((22, 5), (27, 9), (31, 13), (35, 17))

# Rome sur `italie.png` : la cité dessinée sur la rive du Tibre, au-dessus de la côte tyrrhénienne.
POSITION_ROME = (47, 25)
# Sorties de Rome : nom → point visé (une route qui quitte la carte, hors du cadre).
SORTIES_ROME = {"ouest": (3, 27), "nord": (32, 6), "est": (84, 30), "sud": (40, 44)}


def case_au_bord(principale, *, colonne=None, rangee=None, vers, borne=None):
	"""Case de `principale` la plus loin dans la direction `vers` ('nord', 'sud', 'est',
	'ouest') sur la colonne (nord/sud) ou la rangée (est/ouest) donnée, ou None.
	`borne` : coordonnée minimale (nord/ouest) ou maximale (sud/est) admise."""
	if vers in ("nord", "sud"):
		valeurs = [y for x, y in principale if x == colonne]
	else:
		valeurs = [x for x, y in principale if y == rangee]
	if borne is not None:
		valeurs = [v for v in valeurs if (v >= borne if vers in ("nord", "ouest") else v <= borne)]
	if not valeurs:
		return None
	v = min(valeurs) if vers in ("nord", "ouest") else max(valeurs)
	return (colonne, v) if vers in ("nord", "sud") else (v, rangee)


def connexions_pays(principale_france, principale_pays, pays_id, passages, cote_france,
		vers_pays=None):
	"""(docs, refus) des liens France ↔ pays voisin.

	`cote_france` : 'sud' (rangée FRANCE_Y_SUD, passages = (x France, …)) ou 'est' (colonne
	FRANCE_X_EST, passages = (y France, …)). Côté pays, une case `(x, y)` FIXÉE (éprouvée dans
	la zone principale), ou la colonne / rangée dont on prend la case la plus loin vers
	`vers_pays`, le bord du pays tourné vers la France."""
	slug = pays_id.split(":", 1)[1]
	docs, refus = [], []
	for i, (a, b) in enumerate(passages, start=1):
		pos_fr = (a, FRANCE_Y_SUD) if cote_france == "sud" else (FRANCE_X_EST, a)
		if pos_fr not in principale_france:
			refus.append(f"{FRANCE} : la case {list(pos_fr)} n'est pas dans sa zone principale")
			continue
		if isinstance(b, tuple):
			pos_pays = b if b in principale_pays else None
		elif vers_pays in ("nord", "sud"):
			pos_pays = case_au_bord(principale_pays, colonne=b, vers=vers_pays)
		else:
			pos_pays = case_au_bord(principale_pays, rangee=b, vers=vers_pays)
		if pos_pays is None:
			refus.append(f"{pays_id} : aucune case de la zone principale pour le passage {i}")
			continue
		docs.append(connexion(f"link:france_to_{slug}_{i:02d}", FRANCE, pos_fr, pays_id, pos_pays))
	return docs, refus


def connexions_rome(principale_italie, principale_rome):
	"""(docs, refus) des liens Italie ↔ Rome."""
	if POSITION_ROME not in principale_italie:
		return [], [f"{ITALIE} : la case {list(POSITION_ROME)} n'est pas dans sa zone principale"]
	cases = cases_autour(principale_italie, POSITION_ROME, len(SORTIES_ROME))
	if not cases:
		return [], [f"{ITALIE} : pas {len(SORTIES_ROME)} cases libres autour de {list(POSITION_ROME)}"]
	docs, refus = [], []
	for (nom, cible), pos_italie in zip(SORTIES_ROME.items(), cases):
		pos_rome = case_proche(principale_rome, cible)
		if pos_rome is None:
			refus.append(f"{ROME} : aucune case de sa zone principale pour la sortie {nom}")
			continue
		docs.append(connexion(f"link:italie_to_rome_{nom}", ITALIE, pos_italie, ROME, pos_rome))
	return docs, refus


def rome_rattachee(rome_doc):
	"""Le doc de Rome relu, `_rev` retiré, avec `lieu_parent` — None s'il l'a déjà."""
	if (rome_doc or {}).get("lieu_parent") == ITALIE:
		return None
	doc = {k: v for k, v in rome_doc.items() if k != "_rev"}
	doc["lieu_parent"] = ITALIE
	return doc


def a_ecrire(docs, liens, rome):
	"""(sortants, refus) : rien si tout est déjà en base ; refus si une partie seulement l'est."""
	ids = {d.get("_id") for d in docs}
	pris = [l["_id"] for l in liens if l["_id"] in ids]
	if len(pris) == len(liens):
		return ([rome] if rome else []), []
	if pris:
		return [], [f"{i} : `_id` déjà pris" for i in pris]
	return ([rome] if rome else []) + liens, []


def main() -> int:
	args = sys.argv[1:]
	chemin_dump = None
	if "--dump" in args:
		i = args.index("--dump")
		if i + 1 >= len(args):
			print("✗ --dump attend un chemin.")
			return 2
		chemin_dump = args[i + 1]
	docs = ggi.charger_dump(chemin_dump)
	if not docs:
		print("✗ aucun dump : passer --dump ou exporter un telluris-dump-*.json dans jsons/.")
		return 1
	par_id = {d.get("_id"): d for d in docs}
	manquants = [i for i in (FRANCE, ESPAGNE, ITALIE, ROME) if not (par_id.get(i) or {}).get("cells")]
	if manquants:
		print(f"✗ absent(s) du dump ou sans grille : {', '.join(manquants)}")
		return 1
	principales = {i: zone_principale(par_id[i]["cells"], par_id[i].get("nav") or {})
		for i in (FRANCE, ESPAGNE, ITALIE, ROME)}

	liens, refus = connexions_pays(principales[FRANCE], principales[ESPAGNE], ESPAGNE,
		PASSAGES_ESPAGNE, "sud")
	d, r = connexions_pays(principales[FRANCE], principales[ITALIE], ITALIE,
		PASSAGES_ITALIE, "est", "ouest")
	liens += d
	refus += r
	d, r = connexions_rome(principales[ITALIE], principales[ROME])
	liens += d
	refus += r
	sortants, r = a_ecrire(docs, liens, rome_rattachee(par_id[ROME]))
	refus += r
	for r in refus:
		print(f"✗ {r}")
	if refus:
		print("✗ lot refusé : rien n'est écrit.")
		return 1
	if not sortants:
		print("Connexions déjà en base et Rome déjà rattachée à l'Italie : rien à créer.")
		return 0
	for doc in sortants:
		if doc.get("type") == "connection":
			a, b = doc["nodes"]
			print(f"  🔗 {doc['_id']} : {a['lieu']} {a['pos']} ↔ {b['lieu']} {b['pos']}")
		else:
			print(f"  🏛 {doc['_id']} : lieu_parent = {doc['lieu_parent']}")

	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortants, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"\n✎ {os.path.relpath(SORTIE, RACINE)} — {len(sortants)} doc(s)")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
