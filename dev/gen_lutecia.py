#!/usr/bin/env python
# dev/gen_lutecia.py
# Donne à la capitale Lutèce la densité de contenu d'Auxerre — côté CARTE DU MONDE.
#
# CE QUI N'ALLAIT PAS (comparaison Auxerre / Lutèce, exports du 08/08/2026) :
#
#   · `lieu:lutecia` ne portait que **10 placements de zone**, tous `zone:foret_feuillus`, sur
#     une carte de 88×48 : **6 % de la carte couverte**, contre 56 % pour Auxerre. Sur les
#     94 % restants `resolve_zone_event` rend None — il ne s'y passe strictement rien.
#   · Ses `rencontres` et `ressources` sont la COPIE LITTÉRALE de celles d'Auxerre et citent
#     `zone:foret_dense` et `zone:riviere`, qui n'étaient **posées nulle part** sur Lutèce :
#     `gobelin` et `grand_sanglier` ne pouvaient donc jamais y apparaître.
#   · **Aucune zone urbaine**, alors que Lutèce est la seule `sous_categorie: "capitale"` du
#     jeu et que quatre zone-defs ont été écrites pour elle — `zone::coeur_capitale`,
#     `zone::quartier_politique_capitale`, `zone::quartier_bas_capitale`,
#     `zone::remparts_capitale` — et ne sont posées sur AUCUN lieu de la base. Une capitale
#     sans cœur ni remparts.
#   · Les **quatre portes venant de `lieu:france`** — (87,13), (1,10), (87,47), (0,46) —
#     tombaient hors de toute zone : on entre dans la capitale par un no man's land.
#
# ⚠️ CE QUE CE SCRIPT NE PEUT PAS RÉPARER : Lutèce n'a **AUCUN lieu enfant** (0 contre 79 pour
# Auxerre) — pas une boutique, pas de guilde, pas d'étable, pas de temple. Donc ni commerce, ni
# tableau de quêtes, ni recrutement, et **aucune destination possible pour une course de
# transport**. Cela demande des docs `lieu:*` + `connection` par échoppe, et un choix
# d'auteur sur ce que la capitale doit offrir : c'est un autre chantier.
#
# LA GÉOMÉTRIE VIENT DE L'IMAGE. Les 25 placements ajoutés ont été calés sur
# `templates/resources/towns/paris_capital.png` (1408×768 px = 88×48 cases de 16 px) : l'île
# de la Cité et sa cathédrale au centre, le palais au nord-ouest, la forteresse à l'est, les
# bas quartiers denses au sud-ouest et au nord-est, la Seine et son bras nord-est, les
# remparts, puis les faubourgs, les coteaux de vignes à l'est et les bois au sud. Ils sont
# donc à retoucher dans le mode « Zones » de `/admin/editor` si le rendu ne colle pas —
# ce sont des ellipses et des rectangles, pas une décalque au pixel.
#
# ⚠️ POURQUOI UN SCRIPT ET PAS UN JSON ÉCRIT À LA MAIN : `admin_import_bulk` fait un PUT
# COMPLET, jamais un merge — éditer un champ oblige à reproduire tout le doc, `cells` et `nav`
# compris. On RELIT donc le doc depuis le dump figé et on n'y injecte que ce qu'on ajoute :
# régénérer est idempotent (les placements neufs sont dédoublonnés contre l'existant), et une
# retouche faite à la main en base survit à la régénération.
#
# Usage : python dev/gen_lutecia.py
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/lutecia_zones_a_importer.json   (1 doc : lieu:lutecia)

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils.zones import compute_bbox  # noqa: E402  (source unique du calcul de bbox)

# SOURCE FIGÉE (et non « le glob le plus récent ») pour que régénérer donne toujours le même
# résultat ; à mettre à jour à la main après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260808-200458.json"

LIEU_ID = "lieu:lutecia"
SORTIE = "jsons/lutecia_zones_a_importer.json"

# ── Placements ajoutés ──────────────────────────────────────────────────────────
# (zone, x, y, w, h, rot, forme) — coordonnées en CASES, relevées sur paris_capital.png.
PLACEMENTS = [
	# Remparts : l'anneau de muraille, approché par quatre bandes.
	("zone::remparts_capitale", 36, 11, 50, 3, 0, "rectangle"),
	("zone::remparts_capitale", 36, 43, 46, 3, 0, "rectangle"),
	("zone::remparts_capitale", 11, 27, 3, 32, 0, "rectangle"),
	("zone::remparts_capitale", 62, 26, 3, 30, 0, "rectangle"),
	# Cœur : l'île de la Cité et sa cathédrale.
	("zone::coeur_capitale", 46, 29, 22, 12, 0, "ellipse"),
	# Politique : le palais au nord-ouest, la forteresse à l'est.
	("zone::quartier_politique_capitale", 32, 19, 12, 8, 0, "ellipse"),
	("zone::quartier_politique_capitale", 61, 27, 9, 7, 0, "ellipse"),
	# Bas quartiers : la rive sud-ouest, et le quartier dense du nord-est.
	("zone::quartier_bas_capitale", 26, 38, 26, 12, 0, "ellipse"),
	("zone::quartier_bas_capitale", 52, 14, 16, 10, 0, "ellipse"),
	# Marchand : les quais de la rive gauche, et la rive sud-est.
	("zone::quartier_marchand_ville", 22, 20, 12, 7, 0, "ellipse"),
	("zone::quartier_marchand_ville", 52, 38, 14, 8, 0, "ellipse"),
	# La Seine : le bassin ouest, le cours central, la sortie sud-est, le bras nord-est.
	("zone:riviere", 20, 25, 26, 5, 0, "rectangle"),
	("zone:riviere", 44, 30, 26, 4, 0, "rectangle"),
	("zone:riviere", 66, 38, 20, 4, 25, "rectangle"),
	("zone:riviere", 80, 45, 16, 4, 10, "rectangle"),
	("zone:riviere", 60, 16, 4, 18, 0, "rectangle"),
	# Faubourgs hors les murs.
	("zone::faubourg_ville", 5, 26, 9, 20, 0, "ellipse"),
	("zone::faubourg_ville", 40, 5, 44, 7, 0, "ellipse"),
	("zone::faubourg_ville", 70, 30, 18, 14, 0, "ellipse"),
	# Campagne. ⚠️ Ces deux-là couvrent les portes venant de la France : les élargir ou les
	# déplacer sans vérifier remettrait l'entrée de la capitale hors de toute zone.
	("zone:collines", 77, 16, 24, 16, 0, "ellipse"),          # coteaux de vignes, à l'est
	("zone:plaine_ouverte", 12, 44, 30, 10, 0, "ellipse"),    # champs, au sud-ouest
	# Bois. Sans eux, `zone:foret_dense` resterait citée par les rencontres sans être posée.
	("zone:foret_dense", 8, 44, 16, 6, 0, "ellipse"),
	("zone:foret_dense", 60, 46, 16, 5, 0, "ellipse"),
	("zone:foret_dense", 6, 12, 12, 8, 0, "ellipse"),
]

# Portes venant de `lieu:france` : contrôlées à la génération (cf. l'avertissement ci-dessus).
PORTES = [(87, 13), (1, 10), (87, 47), (0, 46)]

# ── Ressources ajoutées ─────────────────────────────────────────────────────────
# Les 10 ressources déjà en base ne parlaient que des forêts. La Seine et les champs en
# apportent d'autres. item → zones ; fusionné avec l'existant, jamais réécrit.
RESSOURCES_AJOUT = {
	"item:Saule": ["zone:riviere"],
	"item:Peuplier": ["zone:riviere"],
	"item:Aulne": ["zone:riviere"],
	"item:Eau_de_source": ["zone:riviere"],
	"item:Herbes_medicinales": ["zone:riviere", "zone:plaine_ouverte"],
	"item:Herbes_a_bruler": ["zone:plaine_ouverte", "zone:collines"],
	"item:Fleur_de_souci": ["zone:plaine_ouverte", "zone:collines"],
	"item:graines": ["zone:plaine_ouverte", "zone:collines"],
	"item:Merisier": ["zone:collines"],
}


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def indexer(chemin: str) -> dict:
	return {d["_id"]: d for d in charger(chemin) if isinstance(d, dict) and d.get("_id")}


def _cle(p: dict) -> tuple:
	return (p.get("zone"), p.get("x"), p.get("y"), p.get("w"), p.get("h"),
			p.get("rot", 0), p.get("forme"))


def _dedans(px: int, py: int, p: dict) -> bool:
	"""Miroir minimal de `zones.compute_zone_intensity` — sert au seul contrôle des portes."""
	import math
	b = p["bbox"]
	if not (b["x_min"] <= px <= b["x_max"] and b["y_min"] <= py <= b["y_max"]):
		return False
	a = math.radians(-p.get("rot", 0))
	rx = (px - p["x"]) * math.cos(a) - (py - p["y"]) * math.sin(a)
	ry = (px - p["x"]) * math.sin(a) + (py - p["y"]) * math.cos(a)
	hw, hh = p["w"] / 2.0, p["h"] / 2.0
	if p.get("forme") == "rectangle":
		return abs(rx) <= hw and abs(ry) <= hh
	return (rx / hw) ** 2 + (ry / hh) ** 2 <= 1.0


def valider(lieu: dict, base: dict, placements: list) -> None:
	"""Aucune référence morte, aucune porte orpheline : les deux défauts qu'on répare."""
	erreurs = []
	posees = {p["zone"] for p in placements}

	for z in sorted(posees):
		if z not in base:
			erreurs.append(f"zone posée mais absente de la base : {z}")
	for item_id in RESSOURCES_AJOUT:
		if item_id not in base:
			erreurs.append(f"ressource inconnue en base : {item_id}")
	for r in lieu.get("rencontres") or []:
		if r.get("espece") not in base:
			erreurs.append(f"espèce inconnue en base : {r.get('espece')}")
		orphelines = [z for z in r.get("zones") or [] if z not in posees]
		if orphelines:
			erreurs.append(f"{r.get('espece')} cite {orphelines}, non posée(s) sur Lutèce")
	for r in lieu.get("ressources") or []:
		orphelines = [z for z in r.get("zones") or [] if z not in posees]
		if orphelines:
			erreurs.append(f"{r.get('ressource')} cite {orphelines}, non posée(s) sur Lutèce")
	for px, py in PORTES:
		if not any(_dedans(px, py, p) for p in placements):
			erreurs.append(f"la porte ({px},{py}) venant de la France n'est dans aucune zone")

	if erreurs:
		for e in erreurs:
			print(f"   ERREUR : {e}")
		sys.exit(f"{len(erreurs)} erreur(s) — rien n'a été écrit.")


def main() -> None:
	base = indexer(SRC_DUMP)
	if LIEU_ID not in base:
		sys.exit(f"ERREUR : {LIEU_ID} introuvable dans {SRC_DUMP}")
	lieu = base[LIEU_ID]

	# Placements : on ajoute ceux qui manquent, on ne réécrit jamais l'existant.
	existants = list(lieu.get("zone_influences") or [])
	vus = {_cle(p) for p in existants}
	ajoutes = 0
	for zone, x, y, w, h, rot, forme in PLACEMENTS:
		p = {"x": x, "y": y, "w": w, "h": h, "rot": rot, "forme": forme, "zone": zone}
		p["bbox"] = compute_bbox(p)
		if _cle(p) in vus:
			continue
		vus.add(_cle(p))
		existants.append(p)
		ajoutes += 1
	lieu["zone_influences"] = existants

	# Ressources : fusion par item, l'ordre existant est préservé.
	par_item, ordre = {}, []
	for r in lieu.get("ressources") or []:
		iid = r.get("ressource")
		if not iid:
			continue
		if iid not in par_item:
			par_item[iid] = list(r.get("zones") or [])
			ordre.append(iid)
		else:
			for z in r.get("zones") or []:
				if z not in par_item[iid]:
					par_item[iid].append(z)
	for iid, zones in RESSOURCES_AJOUT.items():
		if iid not in par_item:
			par_item[iid] = []
			ordre.append(iid)
		for z in zones:
			if z not in par_item[iid]:
				par_item[iid].append(z)
	lieu["ressources"] = [{"ressource": iid, "zones": par_item[iid]} for iid in ordre]

	valider(lieu, base, existants)

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump([lieu], f, ensure_ascii=False, indent=2)
		f.write("\n")

	zones = sorted({p["zone"] for p in existants})
	print(f"écrit {SORTIE}")
	print(f"   zone_influences : {len(existants)} placements (+{ajoutes}), {len(zones)} zones")
	print(f"   rencontres      : {len(lieu.get('rencontres') or [])} espèces, toutes zonées")
	print(f"   ressources      : {len(lieu['ressources'])} entrées")
	print("   portes venant de la France : les 4 sont dans une zone")


if __name__ == "__main__":
	main()
