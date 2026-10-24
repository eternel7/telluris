"""Égypte ↔ Levant — les passages du Sinaï, sur le modèle d'Égypte ↔ Afrique du Nord.

Les deux territoires sont PEINTS par l'Auteur (dump du 24/10/2026) : l'Égypte ferme ce qui est
à l'est de x = 71 au-dessus de la mer Rouge (le Sinaï oriental, le golfe d'Aqaba), le Levant
ferme tout ce qui est à l'ouest de x = 20 (le Sinaï occidental, le golfe de Suez). Rien n'est
donc recalé (`frontieres_calees.recaler` n'est PAS appelé : il écraserait la peinture) ; seules
les deux LIGNES sont lues sur la peinture — les cases praticables qui touchent la bande fermée
de leur propre carte —, puis jumelées par la projection calée (`calage_cartes`, paire
`egypte_levant` : le Levant, deux fois plus détaillé, est posé).

DENSITÉ (même règle qu'Égypte ↔ Afrique du Nord) : la carte la moins détaillée COMPTE — une
case sur deux côté Égypte (`postes`) ; côté Levant, chaque passage se pose sur la case de sa
ligne la plus proche de la projection du poste (`frontieres_calees.liens_projetes`).

Toute autre connexion dont un nœud tombe sur une case fermée est SIGNALÉE (avertissement).

Usage : python dev/gen_egypte_levant.py [--dump jsons/telluris-dump-….json]
Sortie : jsons/egypte_levant_a_importer.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import frontieres_calees  # noqa: E402
from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_plaine_europeenne import zone_de  # noqa: E402

EGYPTE, LEVANT = "lieu:egypte", "lieu:levant"
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "egypte_levant_a_importer.json")
PREFIXE = "link:egypte_to_levant"

ANCRE_EGYPTE = (40, 30)   # désert occidental
ANCRE_LEVANT = (70, 20)   # désert d'Arabie
# Colonne de la frontière peinte, côté praticable : (x de la ligne, x de la bande fermée).
COLONNE_EGYPTE = (71, 72)
COLONNE_LEVANT = (20, 19)

# Du nord au sud, un nom par poste côté Égypte : la côte, les pistes et les cols du Sinaï.
PASSAGES = (
	"Route côtière d'El-Arich", "Piste de Bir el-Abd", "Piste du djebel Maghara", "Col de la Mitla",
	"Col du Giddi", "Darb el-Hajj, par Nakhl", "Plateau du Tih", "Wadi Feiran", "Piste de Dahab",
	"Piste de Ras Mohammed",
)


def ligne_peinte(doc, zone, colonne) -> list:
	"""Cases de `zone` dans la colonne de la ligne, dont la voisine de la bande est FERMÉE,
	du nord au sud."""
	x, x_ferme = colonne
	cells = doc["cells"]
	return sorted(((x, y) for (cx, y) in zone if cx == x and cells[y][x_ferme] == 0), key=lambda c: c[1])


def connexions_coupees(docs, par_id) -> list:
	avert = []
	for d in docs:
		if d.get("type") != "connection" or d["_id"].startswith(PREFIXE):
			continue
		for n in d.get("nodes") or []:
			if n.get("lieu") not in (EGYPTE, LEVANT):
				continue
			grille = par_id[n["lieu"]]["cells"]
			x, y = (n.get("pos") or (0, 0))[:2]
			if 0 <= y < len(grille) and 0 <= x < len(grille[y]) and grille[y][x] == 0:
				avert.append(f"{d['_id']} : nœud {n['lieu']} {n['pos']} sur une case fermée")
	return avert


def construire(docs) -> tuple[list, list, list]:
	"""(docs à importer, refus, avertissements)."""
	par_id = {d.get("_id"): d for d in docs}
	manquants = [i for i in (EGYPTE, LEVANT) if not (par_id.get(i) or {}).get("cells")]
	if manquants:
		return [], [f"absent(s) du dump ou sans grille : {', '.join(manquants)}"], []
	egypte, levant = par_id[EGYPTE], par_id[LEVANT]
	zone_e = zone_de(egypte["cells"], egypte.get("nav") or {}, ANCRE_EGYPTE)
	zone_l = zone_de(levant["cells"], levant.get("nav") or {}, ANCRE_LEVANT)
	ligne_e = ligne_peinte(egypte, zone_e, COLONNE_EGYPTE)
	ligne_l = ligne_peinte(levant, zone_l, COLONNE_LEVANT)
	libelles = {EGYPTE: egypte.get("label"), LEVANT: levant.get("label")}
	liens, refus, avert = frontieres_calees.liens_projetes(PREFIXE, EGYPTE, ligne_e, LEVANT, ligne_l,
		PASSAGES, libelles)
	liens += frontieres_calees.liens_perimes(docs, PREFIXE + "_", {l["_id"] for l in liens})
	avert += connexions_coupees(docs, par_id)
	return liens, refus, avert


def main() -> int:
	args = sys.argv[1:]
	docs = ggi.charger_dump(args[args.index("--dump") + 1] if "--dump" in args else None)
	sortie, refus, avert = construire(docs)
	for a in avert:
		print(f"⚠ {a}")
	if refus:
		print("✗ " + "\n✗ ".join(refus))
		return 1
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	for d in sortie:
		if d.get("type") == "connection":
			print("   " + d["_id"] + " : " + " ↔ ".join(f"{n['lieu']} {n['pos']}" for n in d["nodes"]))
	print(f"{len(sortie)} doc(s) → {os.path.relpath(SORTIE, ggi.RACINE)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
