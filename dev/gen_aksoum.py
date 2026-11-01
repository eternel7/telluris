"""Aksoum en jeu, posée sur la carte d'Afrique du Nord : UN fichier à importer.

Lore : docs/lore/cites/20261101_histoire_d_aksoum.md (cité de la reine, des éleveurs de
pégases ; enceinte ouverte à l'ouest VOULUE : palais, haras, bassin hors des murs).
Image : towns/aksoum_capital.jpg (retenue par l'Auteur, 01/11/2026).

- `lieu:aksoum` : doc minimal de `gen_villes_images.villes_a_creer` (forme de `lieu:rhemi`),
  PREMIÈRE PASSE de grille de `gen_grille_image.proposer_pour_image`, à retoucher dans
  l'éditeur ; `lieu_parent` = `lieu:afrique_du_nord`. Créée UNE fois : en base, le doc est
  relu tel quel (les retouches de l'éditeur survivent au rejeu).
- Position sur la carte d'Afrique du Nord : la vraie Aksoum (14° N, 38,7° E) tombe juste
  hors du cadre ; elle est posée dans le COIN SUD-EST, sur les hauts plateaux, au-delà de la
  source de l'affluent qui rejoint le Nil (Abou Simbel est en (76, 32)).
- Sorties (schéma de `gen_villes_pays.connexions_cite`) : une case de terre de la carte par
  sortie autour de la position ; dans la cité, la case la plus proche du repère dans la plus
  grande zone (la campagne, hors les murs). Portes de rempart : à poser dans l'éditeur.

⚠️ Pourquoi pas `gen_villes_pays` : rejoué sur le dump du 31/10, il réémet aussi des
connexions (Égypte, Londres, Abou Simbel) déplacées depuis à la main — l'import les
écraserait (CLAUDE.md § 18 : le fichier ne porte que le delta de la demande).

N'émet que ce qui diffère du dump (`gen_voisins_france.a_emettre`) ; ne touche pas
`lieu:afrique_du_nord` (aucun PUT complet de la carte du pays).

Usage : python dev/gen_aksoum.py [--dump jsons/telluris-dump-….json] [--sans-apercu]
Sortie : jsons/aksoum_a_importer.json (+ jsons/aksoum_grille_apercu.png si la cité est créée)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_plaine_europeenne import (  # noqa: E402
	case_proche, cases_autour, connexion, libelle_sortie, sans_rev, zone_de)
from dev.gen_villes_images import _taille_image, poser_grille, villes_a_creer  # noqa: E402
from dev.gen_voisins_france import a_emettre  # noqa: E402

RACINE = ggi.RACINE
SORTIE = os.path.join(ggi.DOSSIER_JSONS, "aksoum_a_importer.json")

IMAGE = "aksoum_capital.jpg"
CITE = "lieu:aksoum"
PAYS = "lieu:afrique_du_nord"
# Point de terre de la carte du pays (celui de `gen_villes_pays.ANCRES_PAYS`) : Sahara.
ANCRE_PAYS = (40, 30)
# Hauts plateaux du coin sud-est de la carte d'Afrique du Nord (lus sur l'image).
POSITION = (85, 45)
# nom → repère dans la cité (dehors) : la route de l'est (vers la mer et l'auberge-relais),
# les champs du sud, l'ouest par le bassin.
SORTIES = {"est": (80, 22), "sud": (56, 46), "ouest": (4, 40)}


def construire(docs, taille_fn, proposer_fn):
	"""(sortants, refus, proposition | None). `proposer_fn(doc) -> {cells, nav, rapport}`."""
	par_id = {d.get("_id"): d for d in docs}
	pays = par_id.get(PAYS)
	if not pays or not pays.get("cells"):
		return [], [f"{PAYS} absent du dump ou sans grille"], None
	proposition = None
	cite = par_id.get(CITE)
	if cite is None:
		nouvelles, refus = villes_a_creer([IMAGE], docs, taille_fn)
		if refus:
			return [], refus, None
		if not nouvelles or nouvelles[0]["_id"] != CITE:
			return [], [f"{IMAGE} : pas de {CITE} à créer (image déjà citée par un autre lieu ?)"], None
		proposition = proposer_fn(nouvelles[0])
		cite = poser_grille(nouvelles[0], proposition)
	cite = sans_rev(cite)
	if not cite.get("lieu_parent"):
		cite["lieu_parent"] = PAYS

	zone_pays = zone_de(pays["cells"], pays.get("nav") or {}, ANCRE_PAYS)
	centre = case_proche(zone_pays, POSITION)
	cases = cases_autour(zone_pays, centre, len(SORTIES)) if centre else None
	if not cases:
		return [], [f"{PAYS} : pas {len(SORTIES)} cases de terre autour de {list(POSITION)}"], None
	zone_cite = zone_de(cite["cells"], cite.get("nav") or {})
	liens, refus = [], []
	for (nom, repere), pos_pays in zip(SORTIES.items(), cases):
		pos = case_proche(zone_cite, repere)
		if pos is None:
			refus.append(f"{CITE} : aucune case libre pour la sortie {nom}")
			continue
		lien = connexion(f"link:afrique_du_nord_to_aksoum_{nom}", PAYS, pos_pays, CITE, pos)
		lien["nodes"][1]["label"] = libelle_sortie(cite["label"], nom)
		liens.append(lien)
	return [cite] + liens, refus, proposition


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

	def proposer(doc):
		dim = doc["dimensions"]
		return ggi.proposer_pour_image(ggi.trouver_image(doc["image"]), dim["x"], dim["y"], doc)

	sortants, refus, proposition = construire(docs, _taille_image, proposer)
	emis, r = a_emettre(docs, sortants)
	refus += r
	for r in refus:
		print(f"✗ {r}")
	if refus:
		print("✗ lot refusé : rien n'est écrit.")
		return 1
	if not emis:
		print("Tout est déjà en base : rien à écrire.")
		return 0
	for doc in emis:
		if doc.get("type") == "connection":
			a, b = doc["nodes"]
			print(f"  🔗 {doc['_id']} : {a['lieu']} {a['pos']} ↔ {b['lieu']} {b['pos']}")
		else:
			print(f"  ✚ {doc['_id']} — {doc['label']} · parent {doc.get('lieu_parent')}")
	if proposition:
		chemin = ggi.trouver_image(IMAGE)
		ggi.imprimer_resume(chemin, proposition)
		if "--sans-apercu" not in args:
			apercu = os.path.join(ggi.DOSSIER_JSONS, "aksoum_grille_apercu.png")
			ggi.ecrire_apercu(chemin, proposition["cells"], apercu, proposition["nav"],
				proposition["rapport"])
			print(f"  aperçu : {os.path.relpath(apercu, RACINE)}")
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(emis, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"\n✎ {os.path.relpath(SORTIE, RACINE)} — {len(emis)} doc(s)")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
