#!/usr/bin/env python
# dev/gen_coherence_france.py
# Répare la cohérence de `lieu:france` : ressources récoltables, bestiaire des zones muettes,
# placements dédoublonnés — et corrige au passage le tag mort des profils « magie ».
#
# CE QUI N'ALLAIT PAS (audit du 08/08/2026, export rev 329) :
#
#   1. `lieu:france` ne portait AUCUN champ `ressources`. `zones.resolve_recolte` renvoie donc
#      toujours None : TOUT événement `ressource` était un no-op silencieux, alors que c'est
#      l'entrée la plus lourde de presque toutes les tables de zone (40-55 % du poids). Le
#      bouton 🌿 Récolter n'est jamais apparu sur la carte du monde, nulle part.
#   2. Trois zones POSÉES sur la carte n'avaient aucune espèce dans `rencontres` — `marais`
#      (3 placements), `collines` (17) et `glacier` (4) : leur poids `combat` retombait sur
#      `{"combat_id": None}`, donc sur un silence indiscernable d'un tirage malheureux.
#   3. Quatre emplacements portaient des placements DUPLIQUÉS à l'identique (même zone,
#      centre, taille, forme, rotation) — 5 copies en trop, `plaine_ouverte` en (51,3) étant
#      posée TROIS fois. Sans effet géométrique — le test d'appartenance est un OU — mais
#      chaque copie repèse dans la table de poids composite de `resolve_zone_event`.
#   4. `profil:apprenti` et `profil:mage` (5/16 du `profil_weights` du lieu) exigent
#      `restriction_tags: ["magie"]`, or AUCUNE des 139 espèces de la base ne porte ce tag :
#      le vocabulaire réel est `magique`. `chasse._profils_compatibles` et
#      `donjon._profil_max_compatible` les écartaient donc toujours, pendant que
#      `combat._pick_profil` — qui ne filtre PAS `restriction_tags` — les tirait bel et bien
#      en combat aléatoire. Deux chemins qui se contredisent sur la même donnée.
#      ⚠️ Le correctif vise les QUATRE profils du vocabulaire (apprenti, mage, heros_mage,
#      seigneur_mage) et pas seulement les deux cités par france : n'en corriger que la
#      moitié laisserait deux orthographes pour une même notion — le défaut qu'on répare.
#
# ⚠️ CE QUI N'EST PAS TRAITÉ ICI, et pourquoi :
#   · 39 % de la carte (1 656 cases) ne porte aucun placement de zone → il ne s'y passe
#     jamais rien. C'est un choix d'authoring, pas une incohérence.
#   · Aucune battle map ne porte les terrains `montagne`/`plaine`/`marais`/`colline`/
#     `glacier` : `combat.select_battle_map` retombe sur son repli uniforme, donc sur un
#     décor de forêt. Il manque des IMAGES, pas de la donnée.
#   · Aucun item de conifère n'existe (les 15 `sous_categorie: "arbre"` sont des feuillus),
#     alors que `foret_coniferes`/`foret_persistante` annoncent pin et résine. On y pose les
#     essences claires disponibles ; `resolve_recolte` retombe de toute façon sur un candidat
#     au hasard quand aucun tag ne recoupe.
#   · `restriction_tags: ["distance"]` est mort exactement de la même façon (6 profils
#     d'archers, zéro espèce portant `distance`). Le réparer demande une passe de bestiaire
#     — quelles créatures attaquent à distance ? — et n'est pas tranché ici.
#
# ⚠️ POURQUOI UN SCRIPT ET PAS UN JSON ÉCRIT À LA MAIN : `admin_import_bulk` fait un PUT
# COMPLET, jamais un merge — éditer un champ oblige à reproduire tout le doc, `cells` et `nav`
# compris (4 224 cases). On RELIT donc les docs depuis des sources FIGÉES et on n'y injecte que
# les champs ajoutés : régénérer est idempotent, et une retouche faite à la main en base
# survit à la régénération.
#
# Usage : python dev/gen_coherence_france.py
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/france_coherence_a_importer.json      (1 doc  : lieu:france)
#   jsons/profils_tag_magique_correctif.json    (4 docs : profil:*)

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SOURCES FIGÉES (et non « le glob le plus récent ») pour que régénérer donne toujours le même
# résultat ; à mettre à jour à la main après un nouvel export.
# ⚠️ DEUX sources, chacune la plus fraîche pour ce qu'elle porte : l'export ciblé est en rev
# 329 et contient les 21 placements collines/glacier que le dump (rev 328) ignore encore.
SRC_LIEU = "jsons/lieu_filtre_id_france_20260808-182809.json"
SRC_DUMP = "jsons/telluris-dump-20260808-150706.json"

LIEU_ID = "lieu:france"

SORTIE_LIEU = "jsons/france_coherence_a_importer.json"
SORTIE_PROFILS = "jsons/profils_tag_magique_correctif.json"

# ── Ressources récoltables ───────────────────────────────────────────────────────
# item → zones qui le fournissent. Le doc `lieu` attend la forme inverse
# (`[{"ressource", "zones"}]`, cf. `lieu:auxerre`) ; on écrit ici dans le sens qui se relit,
# et `main()` retourne la table. Toutes les essences existent en `sous_categorie: "arbre"`,
# donc coupables (tag `a_couper`) : récolter un arbre abat un niveau vers le sol.
RESSOURCES = {
	# Feuillus — les essences nobles des forêts de plaine.
	"item:Chene": ["zone:foret_feuillus", "zone:foret_dense"],
	"item:Hetre": ["zone:foret_feuillus", "zone:foret_dense"],
	"item:Frene": ["zone:foret_feuillus", "zone:foret_dense"],
	"item:Charme": ["zone:foret_feuillus", "zone:foret_dense"],
	"item:Erable": ["zone:foret_feuillus"],
	"item:Tilleul": ["zone:foret_feuillus"],
	"item:Orme": ["zone:foret_dense"],
	"item:Chataignier": ["zone:foret_dense"],
	"item:Seve_de_chene": ["zone:foret_feuillus"],
	# Essences claires — faute d'item de conifère en base (cf. l'avertissement en tête).
	"item:Bouleau": ["zone:foret_feuillus", "zone:foret_coniferes", "zone:foret_persistante"],
	"item:Tremble": ["zone:foret_coniferes", "zone:foret_persistante"],
	"item:Alisier": ["zone:foret_coniferes", "zone:foret_persistante", "zone:collines"],
	"item:Merisier": ["zone:foret_feuillus", "zone:collines"],
	# Essences de bord d'eau.
	"item:Saule": ["zone:riviere", "zone:marais"],
	"item:Peuplier": ["zone:riviere"],
	"item:Aulne": ["zone:riviere", "zone:marais"],
	"item:Eau_de_source": ["zone:riviere"],
	# Simples et fleurs.
	"item:Herbes_medicinales": ["zone:foret_feuillus", "zone:foret_dense", "zone:riviere",
								"zone:plaine_ouverte", "zone:montagne"],
	"item:Herbes_a_bruler": ["zone:foret_dense", "zone:foret_coniferes",
							 "zone:foret_persistante", "zone:plaine_ouverte", "zone:collines"],
	"item:Fleur_de_souci": ["zone:foret_feuillus", "zone:foret_persistante",
							"zone:plaine_ouverte", "zone:collines"],
	"item:graines": ["zone:plaine_ouverte", "zone:collines"],
	# Les trois simples vénéneuses tiennent l'ombre et la tourbe.
	"item:Racine_de_mandragore": ["zone:foret_dense", "zone:foret_coniferes", "zone:marais"],
	"item:Capsules_de_pavot": ["zone:plaine_ouverte", "zone:marais"],
	"item:Feuilles_d_absinthe": ["zone:plaine_ouverte", "zone:marais"],
	# Minéral et dépouilles.
	"item:fer": ["zone:montagne", "zone:glacier"],
	"item:Sel_gemme": ["zone:montagne", "zone:collines", "zone:glacier"],
	"item:plumes": ["zone:foret_dense", "zone:montagne"],
}

# ── Bestiaire des zones muettes ─────────────────────────────────────────────────
# zone → espèces à y faire rôder. ⚠️ FUSIONNÉ PAR ESPÈCE avec les `rencontres` existantes,
# jamais concaténé : `espece:aigle_geant` a déjà son entrée (montagne) et doit voir
# `zone:glacier` s'AJOUTER à sa liste de zones — une seconde entrée pour la même espèce
# la ferait peser double dans le pool de `start_combat`.
RENCONTRES_AJOUT = {
	"zone:marais": ["espece:gobelin_des_marais", "espece:bunyip", "espece:crocodile",
					"espece:serpent", "espece:rat_geant"],
	"zone:collines": ["espece:loup", "espece:sanglier", "espece:renard", "espece:lievre",
					  "espece:orc", "espece:oiseaux_de_proies"],
	"zone:glacier": ["espece:ours_polaire", "espece:loup_geant", "espece:aigle_geant"],
}

# ── Profils au tag mort ─────────────────────────────────────────────────────────
PROFILS_MAGIE = ["profil:apprenti", "profil:mage", "profil:heros_mage", "profil:seigneur_mage"]
TAG_MORT = "magie"
TAG_REEL = "magique"


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def indexer(chemin: str) -> dict:
	return {d["_id"]: d for d in charger(chemin) if isinstance(d, dict) and d.get("_id")}


def extraire(base: dict, doc_id: str, source: str) -> dict:
	"""Le doc tel qu'il est EN BASE, jamais retapé. Sortie en erreur s'il manque : mieux vaut
	ne rien générer qu'un fichier d'import qui écraserait un doc par une version inventée."""
	if doc_id not in base:
		sys.exit(f"ERREUR : {doc_id} introuvable dans {source}")
	return base[doc_id]


def _cle_placement(p: dict) -> tuple:
	return (p.get("zone"), p.get("x"), p.get("y"), p.get("w"), p.get("h"),
			p.get("rot", 0), p.get("forme"))


def dedoublonner(placements: list):
	"""Placements sans doublon strict — PREMIER GAGNE, pour que l'ordre d'authoring survive."""
	vus = set()
	garde = []
	for p in placements:
		cle = _cle_placement(p)
		if cle in vus:
			continue
		vus.add(cle)
		garde.append(p)
	return garde, len(placements) - len(garde)


def fusionner_rencontres(existantes: list, ajouts: dict) -> list:
	"""`rencontres` = UNE entrée par espèce, portant sa liste de zones. On repart des entrées
	en place (ordre préservé) et on n'en crée une que pour une espèce encore absente."""
	par_espece = {}
	ordre = []
	for r in existantes or []:
		eid = r.get("espece")
		if not eid:
			continue
		if eid not in par_espece:
			par_espece[eid] = list(r.get("zones") or [])
			ordre.append(eid)
		else:  # doc bricolé à la main : on replie les deux entrées plutôt que d'en perdre une
			for z in r.get("zones") or []:
				if z not in par_espece[eid]:
					par_espece[eid].append(z)
	for zone, especes in ajouts.items():
		for eid in especes:
			if eid not in par_espece:
				par_espece[eid] = []
				ordre.append(eid)
			if zone not in par_espece[eid]:
				par_espece[eid].append(zone)
	return [{"espece": eid, "zones": par_espece[eid]} for eid in ordre]


def valider(lieu: dict, base: dict) -> None:
	"""Aucune référence morte ne doit sortir d'ici : ce serait réintroduire, sous une autre
	forme, le défaut même que ce script répare (un placement dont la zone n'existe pas est
	écarté EN SILENCE par `load_zone_defs_for_lieu`)."""
	zones_posees = {p.get("zone") for p in lieu.get("zone_influences") or []}
	erreurs = []

	for item_id, zones in RESSOURCES.items():
		if item_id not in base:
			erreurs.append(f"ressource inconnue en base : {item_id}")
		for z in zones:
			if z not in zones_posees:
				erreurs.append(f"{item_id} cite {z}, qui n'est posée sur aucun placement")
	for zone, especes in RENCONTRES_AJOUT.items():
		if zone not in zones_posees:
			erreurs.append(f"rencontres : {zone} n'est posée sur aucun placement")
		for eid in especes:
			if eid not in base:
				erreurs.append(f"espèce inconnue en base : {eid}")

	if erreurs:
		for e in erreurs:
			print(f"   ERREUR : {e}")
		sys.exit(f"{len(erreurs)} erreur(s) — rien n'a été écrit.")

	# Non bloquant : le dump peut simplement être plus ancien que l'import des zones.
	# (Pas d'emoji dans un print : la console Windows est en cp1252, elle lèverait un
	# UnicodeEncodeError — le lanceur de /admin/dev-tools, lui, force PYTHONIOENCODING=utf-8.)
	for z in sorted(zones_posees):
		if z and z not in base:
			print(f"   ATTENTION : {z} est posée sur la carte mais absente de {SRC_DUMP} — "
				  f"vérifier qu'elle a bien été importée, sinon ses placements sont INERTES.")


def ecrire(chemin: str, docs: list) -> None:
	with open(os.path.join(RACINE, chemin), "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")


def main() -> None:
	base = indexer(SRC_DUMP)
	lieu = extraire(indexer(SRC_LIEU), LIEU_ID, SRC_LIEU)

	valider(lieu, base)

	avant = len(lieu.get("zone_influences") or [])
	especes_avant = len(lieu.get("rencontres") or [])
	lieu["zone_influences"], retires = dedoublonner(lieu.get("zone_influences") or [])
	lieu["rencontres"] = fusionner_rencontres(lieu.get("rencontres"), RENCONTRES_AJOUT)
	lieu["ressources"] = [
		{"ressource": item_id, "zones": zones}
		for item_id, zones in sorted(RESSOURCES.items())
	]
	ecrire(SORTIE_LIEU, [lieu])

	profils = []
	for pid in PROFILS_MAGIE:
		p = extraire(base, pid, SRC_DUMP)
		tags = list(p.get("restriction_tags") or [])
		if TAG_REEL in tags:
			print(f"   {pid} : déjà corrigé (réimport sans effet)")
		p["restriction_tags"] = [TAG_REEL if t == TAG_MORT else t for t in tags]
		profils.append(p)
	ecrire(SORTIE_PROFILS, profils)

	zones = sorted({z for zs in RESSOURCES.values() for z in zs})
	print(f"écrit {SORTIE_LIEU}")
	print(f"   ressources     : {len(lieu['ressources'])} entrées réparties sur "
		  f"{len(zones)} zones")
	print(f"   rencontres     : {len(lieu['rencontres'])} espèces "
		  f"(+{len(lieu['rencontres']) - especes_avant})")
	print(f"   zone_influences: {len(lieu['zone_influences'])} placements "
		  f"({avant} - {retires} doublon(s))")
	print(f"écrit {SORTIE_PROFILS}")
	print(f"   {len(profils)} profil(s) : restriction_tags « {TAG_MORT} » -> « {TAG_REEL} »")


if __name__ == "__main__":
	main()
