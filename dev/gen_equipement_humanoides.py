#!/usr/bin/env python
# dev/gen_equipement_humanoides.py
# Arme les monstres HUMANOÏDES : pose `items` (armes + armures assignables) sur leur espèce.
#
# Le champ est lu par `utils.combat.roll_monster_equipment` : un jet INDÉPENDANT par pièce
# (world-var `MONSTRE_EQUIPEMENT_PROBA`), posée sur un slot libre de ceux qu'elle couvre, une
# `deux_mains` bloquant l'autre main. Les pièces portées tombent en BUTIN à la mort
# (`_objets_payload`). Sans `items`, un humanoïde frappe à mains nues avec un seul dé de
# Force (`des_cc_espece`) : plus faible qu'une bête de même Force.
#
# Principe des kits : plusieurs armes EN CONCURRENCE pour les mains (le premier tiré prend le
# slot), 2 à 4 pièces d'armure. ⚠️ Une arme de tir/jet PRIME sur la mêlée
# (`_profil_arme_monstre` : tir > jet > cac) et fait kiter le monstre : on la met en
# concurrence avec une arme de mêlée, pour qu'une meute mêle tireurs et combattants au
# contact au lieu de n'aligner que des archers. ⚠️ Seule une arme de TIR à deux mains
# concurrence vraiment la mêlée : une arme de JET à une main se loge dans l'AUTRE main et
# prime quand même — une seule par kit, sinon la meute entière tire.
#
# ⚠️ LA TABLE EST EXHAUSTIVE sur les espèces taguées `humanoide` : `None` = mains nues (corps
# naturel : golems, morts-vivants griffus, esprits, familier), aucun champ. Le script ÉCHOUE —
# sans rien écrire — si un humanoïde du dump manque à la table, si la table cite une espèce
# absente ou non humanoïde, si un id n'est pas une arme/armure de base portable, si la
# `restriction` d'une pièce dépasse le MINIMUM de la caract de l'espèce (tout individu tiré
# doit pouvoir la porter — le moteur, lui, ne vérifie pas), si une pièce `rare` va à une espèce
# ni `boss` ni `legendaire`, ou si une pièce vise un slot que le corps n'a pas.
#
# ⚠️ POURQUOI UN SCRIPT : `admin_import_bulk` fait un PUT COMPLET. On RELIT chaque espèce
# depuis le dump le plus récent et on n'y injecte que `items` (juste après `tags`) :
# régénération idempotente, une retouche faite en base survit — sur un dump FRAIS.
#
# Usage : python dev/gen_equipement_humanoides.py
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/equipement_humanoides_a_importer.json

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = "jsons/equipement_humanoides_a_importer.json"

TAG_HUMANOIDE = "humanoide"
MODES_DISTANCE = ("tir", "jet", "distance")
TAGS_RARE_PERMIS = ("boss", "legendaire")

# slug d'espèce → liste d'`item:*` (sans préfixe), ou None pour mains nues (aucun champ).
TABLE = {
	"ange_de_la_connaissance": [
		"Baton_canalisateur", "Epee_argent",
		"Robe_de_savant", "Calotte_cuir_rune", "Sandales_moine",
	],
	"ange_de_la_justice": [
		"Epee_une_main_benie", "Masse_benie", "Arc_long", "Bouclier_sacre",
		"Cotte_mailles_benie", "Epaulieres_de_fer", "Heaume_ouvert_grave",
	],
	"archange_de_l_ordre": [
		"Epee_une_main_benie", "Masse_benie", "Arc_long", "Bouclier_sacre",
		"Cotte_mailles_benie", "Epaulieres_benies", "Heaume_de_plates", "Gantelets_de_plates",
	],
	"archange_du_savoir": [
		"Baguette_ouvragee", "Baton_canalisateur",
		"Armure_cuir_runee", "Epaulieres_benies", "Calotte_cuir_rune",
	],
	"avatar": [
		"Epee_une_main_benie", "Morgenstern", "Bouclier_sacre",
		"Harnois_du_grand_arsenal", "Epaulieres_benies", "Heaume_de_plates",
		"Gantelets_de_plates", "Bottes_de_plates",
	],
	"centaure": [
		"Arc_long", "Arc", "Pique",
		"Pourpoint_cuir_renf", "Epaulieres_cuir_bouilli", "Bandeau_de_cuir", "Gants_archer",
	],
	"comte_vampire": [
		"Rapiere", "Epee_longue", "Dague_de_parade",
		"Manteau_de_cour_double", "Pantalon_velours", "Bottes_noires", "Gants_fins_noirs",
	],
	"cyclope": [
		"Kanabo", "Rungu",
		"Braies_fourrure", "Etole_de_fourrure", "Bracelets_os",
	],
	"demon_guerrier": [
		"Talwar", "Fleau_arme", "Pilum", "Bouclier_chauffe",
		"Cuirasse_cuir_noir", "Epaulieres_de_fer", "Heaume_de_fer", "Gantelets_acier",
	],
	"demon_majeur_de_la_destinee": [
		"Sceptre_os", "Baton_cornu", "dague_rituelle",
		"Robe_noire_capuche", "Cape_de_plumes_noires", "Gants_runiques",
	],
	"demon_majeur_de_la_destruction": [
		"Kanabo", "Morgenstern", "Hache_de_guerre",
		"Harnois_du_grand_arsenal", "Epaulieres_acier_gravees", "Gantelets_de_plates",
		"Bottes_de_fer",
	],
	"demon_mineur": [
		"Dague", "Epee_courte", "Chakram",
		"Harnais_d_ossements", "Jupe_lanieres_cuir",
	],
	"doppleganger": [
		"Dague", "Rapiere", "Dague_de_jet",
		"Veste_cuir_souple", "Capuche_noire", "Gants_fins_noirs", "Bottes_silencieuses",
	],
	"familier": None,
	"geant_ou_titan": [
		"Kanabo", "Rungu",
		"Braies_fourrure", "Manteau_de_loup", "Bracelets_os",
	],
	"gnome": [
		"Dague", "Epee_courte", "Arbalete_legere",
		"Veste_cuir_souple", "Chapeau_mou", "Gants_cuir_epais", "Souliers_cuir",
	],
	"gobelin": [
		"Dague", "Epee_courte", "Arc_court", "Sarbacane",
		"Pourpoint_cuir_renf", "Bandeau_de_cuir", "Mocassins",
	],
	"gobelin_chamanique": [
		"Sceptre_os", "Baton_cornu", "dague_rituelle",
		"Vetements_totémiques", "Coiffe_plumes", "Bracelets_os",
	],
	"gobelin_des_marais": [
		"Couteau_de_chasse", "Trident_barbele", "Sarbacane",
		"Jupe_de_chanvre", "Bandeau_de_cuir", "Sandales_de_corde",
	],
	"golem_de_chair": None,
	"golem_de_fer": None,
	"golem_de_pierre": None,
	"goule": None,
	"incube": [
		"Rapiere", "Dague",
		"Pourpoint_colore", "Pantalon_ajuste_noir", "Bottes_noires", "Gants_fins_noirs",
	],
	"leprechaun": [
		"Canne_ferree", "Bolas",
		"Pourpoint_colore", "Chapeau_a_plume", "Souliers_cuir",
	],
	"liche": [
		"Sceptre_os", "Baton_cornu", "dague_rituelle",
		"Robe_noire_capuche", "Capuche_noire", "Gants_peau_noire",
	],
	"minotaure": [
		"Kanabo", "Hache_de_guerre", "Morgenstern",
		"Braies_fourrure", "Harnais_d_ossements", "Bracelets_os",
	],
	"momie": None,
	"naiade": None,
	"nereide": None,
	"oceanide": None,
	"ondin": [
		"Trident_barbele", "Dague", "Javelot_ethiopien",
		"Jupe_de_chanvre", "Bracelets_os",
	],
	"orc": [
		"Hache_de_guerre", "Kanabo", "Francisque", "Arbalete", "Targe",
		"Cuirasse_cuir_brut", "Heaume_de_fer", "Epaulieres_d_os", "Bottes_cuir_epais",
	],
	"oreade": None,
	"prince_demon": [
		"Da_dao", "Morgenstern", "Talwar", "Pavois",
		"Harnois_du_grand_arsenal", "Epaulieres_acier_gravees", "Heaume_de_plates",
		"Gantelets_de_plates", "Bottes_de_plates",
	],
	"reine_lhamia": [
		"Naginata", "Jian", "Chakram",
		"Manteau_de_cour_double", "Diademe_d_orfevre", "Gants_fins",
	],
	"roi_des_tombes": [
		"Epee_longue", "Morgenstern", "Arbalete", "Ecu",
		"Cotte_de_mailles", "Heaume_de_plates", "Gantelets_de_plates", "Jambières_de_plates",
	],
	"roi_liche": [
		"Baguette_ouvragee", "Sceptre_os", "Baton_cornu",
		"Robe_noire_capuche", "Reliquaire_de_thanaturge", "Cape_de_plumes_noires",
		"Capuche_noire",
	],
	"satyre": [
		"Couteau_de_chasse", "Baton_de_combat", "Arc_court",
		"Etole_de_fourrure", "Couronne_branchages",
	],
	"seigneur_du_sang": [
		"Epee_longue", "Schiavona", "Morgenstern", "Bouclier_normand",
		"Cotte_de_mailles", "Heaume_de_plates", "Gantelets_de_plates",
		"Jambières_de_plates", "Bottes_de_fer",
	],
	"seraphin": [
		"Epee_une_main_benie", "Masse_benie", "Bouclier_sacre",
		"Harnois_du_grand_arsenal", "Epaulieres_benies", "Heaume_de_plates",
		"Gantelets_de_plates",
	],
	"squelette": [
		"Epee_courte", "Gladius", "Arc_court", "Arbalete_legere", "Rondache",
		"Camail_de_mailles", "Heaume_de_fer",
	],
	"succube": [
		"Fleau_asiatique", "Dague",
		"Cape_soie_sombre", "Jupe_lanieres_cuir", "Bottines_legeres", "Gants_fins_noirs",
	],
	"troglodyte": [
		"Casse_tete_polynesien", "Azagay",
		"Harnais_d_ossements", "Jupe_lanieres_cuir", "Bracelets_os",
	],
	"troll": [
		"Kanabo", "Hache_de_guerre",
		"Braies_fourrure", "Etole_de_fourrure", "Bracelets_os",
	],
	"vampire": [
		"Rapiere", "Epee_longue", "Dague_de_parade",
		"Cape_soie_sombre", "Pantalon_ajuste_noir", "Bottes_noires", "Gants_fins_noirs",
	],
	"vouivre": [
		"Jian", "Naginata",
		"Cape_soie_sombre", "Gants_fins",
	],
	"zombie": None,
}

# Slots que le corps n'a pas : queue de serpent, arrière-train de cheval, pattes de bouc.
SLOTS_INTERDITS = {
	"centaure": {"jambes", "pieds"},
	"reine_lhamia": {"jambes", "pieds"},
	"vouivre": {"jambes", "pieds"},
	"satyre": {"jambes", "pieds"},
}


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	return dumps[-1]


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def est_distance(item: dict) -> bool:
	return any(t in MODES_DISTANCE for t in (item.get("tags") or []))


def _manque_restriction(item: dict, espece: dict) -> dict:
	"""Caracts dont la restriction de l'item dépasse le MINIMUM de l'espèce. Même sémantique
	ET que `utils.characters.restriction_satisfaite`, recopiée ici pour ne pas tirer la base."""
	attrs = espece.get("base_attributes") or {}
	manque = {}
	for caract, mini in (item.get("restriction") or {}).items():
		borne = (attrs.get(caract) or {}).get("min", 0)
		if int(borne or 0) < int(mini or 0):
			manque[caract] = (mini, borne)
	return manque


def erreurs_kit(slug: str, espece: dict, ids: list, items: dict) -> list:
	"""Tout ce qui interdit de poser ce kit sur cette espèce (liste vide = kit valable)."""
	erreurs = []
	tags = espece.get("tags") or []
	interdits = SLOTS_INTERDITS.get(slug, set())
	if len(set(ids)) != len(ids):
		erreurs.append("id en double")
	armes = 0
	for iid in ids:
		item = items.get(f"item:{iid}")
		if not item:
			erreurs.append(f"item:{iid} absent du dump")
			continue
		if item.get("categorie") not in ("arme", "armure"):
			erreurs.append(f"item:{iid} n'est ni arme ni armure")
			continue
		if item.get("fabrication"):
			erreurs.append(f"item:{iid} est une variante sur mesure")
		if item.get("sous_categorie") in ("instrument", "bijou", "outil"):
			erreurs.append(f"item:{iid} est un {item['sous_categorie']}")
		if item.get("rarete") == "rare" and not any(t in tags for t in TAGS_RARE_PERMIS):
			erreurs.append(f"item:{iid} est rare, espèce ni boss ni légendaire")
		manque = _manque_restriction(item, espece)
		if manque:
			erreurs.append(f"item:{iid} exige {manque} (exigé, min de l'espèce)")
		slots = [s for s in (item.get("slots") or []) if s not in interdits]
		if not slots:
			erreurs.append(f"item:{iid} ne vise que des slots absents du corps {item.get('slots')}")
		if item.get("categorie") == "arme":
			armes += 1
	if not armes:
		erreurs.append("aucune arme dans le kit")
	return erreurs


def _avec_items(doc: dict, items: list | None) -> dict:
	"""Copie du doc avec `items` juste après `tags` (ou retiré si None) — la table fait autorité."""
	out = {}
	for cle, valeur in doc.items():
		if cle == "items":
			continue
		out[cle] = valeur
		if cle == "tags" and items is not None:
			out["items"] = items
	if items is not None and "items" not in out:
		out["items"] = items
	return out


def main() -> None:
	source = _dump_le_plus_recent()
	docs_dump = charger(source)
	especes = {d["_id"]: d for d in docs_dump
			   if isinstance(d, dict) and d.get("type") == "espece" and d.get("_id")}
	items = {d["_id"]: d for d in docs_dump
			 if isinstance(d, dict) and str(d.get("_id", "")).startswith("item:")}
	humanoides = {i.split(":", 1)[1] for i, d in especes.items()
				  if TAG_HUMANOIDE in (d.get("tags") or [])}

	manquantes = sorted(humanoides - set(TABLE))
	fantomes = sorted(s for s in TABLE if f"espece:{s}" not in especes)
	non_humanoides = sorted(set(TABLE) - humanoides - set(fantomes))
	erreurs = {}
	for slug, ids in TABLE.items():
		if ids is None or slug in fantomes:
			continue
		e = erreurs_kit(slug, especes[f"espece:{slug}"], ids, items)
		if e:
			erreurs[slug] = e
	if manquantes or fantomes or non_humanoides or erreurs:
		if manquantes:
			print("Humanoïdes du dump ABSENTS de la table (à classer) :\n   " + ", ".join(manquantes))
		if fantomes:
			print("Espèces de la table ABSENTES du dump :\n   " + ", ".join(fantomes))
		if non_humanoides:
			print("Espèces de la table SANS le tag humanoide :\n   " + ", ".join(non_humanoides))
		for slug in sorted(erreurs):
			print(f"{slug} :")
			for e in erreurs[slug]:
				print(f"   {e}")
		sys.exit(1)

	docs, deja, armees, nues, distance, pieces = [], 0, 0, 0, [], 0
	for slug in sorted(TABLE):
		doc = especes[f"espece:{slug}"]
		ids = TABLE[slug]
		valeur = [f"item:{i}" for i in ids] if ids is not None else None
		if valeur is None:
			nues += 1
		else:
			armees += 1
			pieces += len(valeur)
			armes = [items[i] for i in valeur if items[i]["categorie"] == "arme"]
			loin = [a for a in armes if est_distance(a)]
			if loin:
				distance.append(f"{slug} ({len(loin)}/{len(armes)})")
		if doc.get("items") == valeur or (valeur is None and "items" not in doc):
			if valeur is not None:
				deja += 1
			continue
		docs.append(_avec_items(doc, valeur))

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"relu {os.path.relpath(source, RACINE)} ({len(especes)} espèces, "
		  f"{len(humanoides)} humanoïdes)")
	print(f"écrit {SORTIE} : {len(docs)} doc(s)")
	print(f"   armées : {armees} ({pieces / max(1, armees):.1f} pièces en moyenne), "
		  f"mains nues : {nues}")
	print(f"   arme à distance (à distance / armes) : {len(distance)} espèce(s)")
	print("      " + ", ".join(distance))
	if deja:
		print(f"   dont {deja} déjà à jour en base (réimport sans effet)")


if __name__ == "__main__":
	main()
