#!/usr/bin/env python
# dev/gen_grades_france.py
# Descend les HAUTS GRADES du niveau du LIEU vers les seuls placements de la zone très
# dangereuse — pour que la zone dangereuse soit la seule à l'être.
#
# CE QUI N'ALLAIT PAS (dump du 08/08/2026 20:04, `lieu:france` rev 333) :
#
# Les seize profils du jeu avaient été versés dans le `profil_weights` du LIEU, dont les six
# de niveau 5-6 (Seigneur, Héros et leurs variantes archer/mage). Or `zones.resolve_profil_weights`
# ne retombe sur la table du lieu QUE si aucun placement actif n'en définit une — et les
# 36 placements de `zone:tres_dangereuse` n'en portaient aucune (`36 × null`).
#
# Conséquence exactement inverse de l'intention :
#   · **23 % de TOUS les monstres de la France** sortaient en niveau 5-6, y compris le gobelin
#     de la plaine à deux pas de la porte d'Auxerre — un Gobelin Seigneur, c'est 100 PV et
#     cc 40 au lieu de 53 PV et cc 21 ;
#   · et la zone à 10 de danger n'avait, côté grade, **rien de plus** que la plaine ouverte.
#
# CE QUE FAIT CE SCRIPT :
#   1. retire du `profil_weights` du LIEU les profils de niveau >= SEUIL_HAUT_GRADE, en
#      laissant intact tout le reste de ce que l'auteur y a mis ;
#   2. pose GRADES_ZONE sur chacun des placements de `zone:tres_dangereuse`.
#
# ⚠️ LA TABLE D'UN PLACEMENT REMPLACE CELLE DU LIEU, ELLE NE S'Y AJOUTE PAS.
# `resolve_profil_weights` somme les tables des placements ACTIFS et n'utilise celle du lieu
# que si cette somme est vide. La table posée ici doit donc être une distribution COMPLÈTE
# (bas grades compris), sans quoi la zone ne produirait plus que des Seigneurs.
#
# ⚠️ CE QUI N'EST PAS TRAITÉ ICI (le point « c » de l'audit) : `dragon`, `comte_vampire`,
# `harpie`, `nosferatu`, `petit_dragon`, `minotaure` et `serpent_geant` sont aussi déclarés
# dans les `rencontres` de `montagne`, `foret_dense` et `marais` — 678 cases hors de la zone
# dangereuse peuvent donc les produire. Après ce correctif elles les produiront au moins en
# grade ordinaire (niveau <= 4). Resserrer le bestiaire est un choix d'auteur, pas un défaut
# de donnée.
#
# ⚠️ `combat._pick_profil` NE FILTRE PAS `restriction_tags` : les variantes archer et mage
# tomberont sur n'importe quelle espèce en combat aléatoire (seule l'élite d'une chasse ou
# d'un donjon est filtrée). Les garder à poids faible est délibéré ; aucune espèce ne porte
# le tag `distance`, donc aucun archer n'est atteignable par une chasse.
#
# ⚠️ POURQUOI UN SCRIPT ET PAS UN JSON ÉCRIT À LA MAIN : `admin_import_bulk` fait un PUT
# COMPLET, jamais un merge — éditer un champ oblige à reproduire tout le doc, `cells` et `nav`
# compris. On RELIT donc le doc depuis le dump figé et on n'y touche que ces deux champs :
# régénérer est idempotent, et les placements ajoutés entre-temps dans l'éditeur survivent.
#
# Usage : python dev/gen_grades_france.py
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/france_grades_a_importer.json   (1 doc : lieu:france)

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SOURCE FIGÉE (et non « le glob le plus récent ») pour que régénérer donne toujours le même
# résultat ; à mettre à jour à la main après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260808-200458.json"

LIEU_ID = "lieu:france"
ZONE_DANGEREUSE = "zone:tres_dangereuse"
SORTIE = "jsons/france_grades_a_importer.json"

# Niveau à partir duquel un profil n'a plus rien à faire dans la table du LIEU. Lu sur les
# docs `profil:*` et non codé par id : renommer un profil ne casse rien.
SEUIL_HAUT_GRADE = 5

# Distribution posée sur CHAQUE placement de la zone très dangereuse. Complète par
# construction (cf. l'avertissement en tête) : 65 % de niveau 5-6, 30 % de niveau 6, et un
# fond de grades ordinaires pour que tout ne soit pas une exécution.
GRADES_ZONE = {
	"profil:veteran": 1,          # niveau 3
	"profil:champion": 3,         # niveau 4
	"profil:mage": 2,             # niveau 4
	"profil:maitre_archer": 1,    # niveau 4
	"profil:heros": 4,            # niveau 5
	"profil:heros_mage": 2,       # niveau 5
	"profil:heros_archer": 1,     # niveau 5
	"profil:seigneur": 3,         # niveau 6
	"profil:seigneur_mage": 2,    # niveau 6
	"profil:seigneur_archer": 1,  # niveau 6
}


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def indexer(chemin: str) -> dict:
	return {d["_id"]: d for d in charger(chemin) if isinstance(d, dict) and d.get("_id")}


def niveau_de(base: dict, pid: str) -> int:
	return int((base.get(pid) or {}).get("niveau", 1) or 1)


def repartition(base: dict, poids: dict) -> str:
	"""Part du poids revenant à chaque niveau, pour que le récap se lise d'un coup d'œil."""
	if not poids:
		return "(aucune)"
	total = sum(poids.values())
	par_niveau = {}
	for pid, w in poids.items():
		n = niveau_de(base, pid)
		par_niveau[n] = par_niveau.get(n, 0) + w
	return "  ".join(
		f"niv{n}:{100 * w / total:.0f}%" for n, w in sorted(par_niveau.items())
	)


def valider(base: dict, lieu: dict) -> None:
	"""Un profil inconnu serait ignoré EN SILENCE par `_pick_profil` (il filtre sur les docs
	réellement chargés) : la distribution posée ne serait pas celle qu'on croit lire."""
	erreurs = []
	for pid in list(GRADES_ZONE) + list(lieu.get("profil_weights") or {}):
		if pid not in base:
			erreurs.append(f"profil inconnu en base : {pid}")
		elif (base[pid].get("type")) != "profil":
			erreurs.append(f"{pid} n'est pas un doc de type profil")
	if not any(p.get("zone") == ZONE_DANGEREUSE for p in lieu.get("zone_influences") or []):
		erreurs.append(f"aucun placement de {ZONE_DANGEREUSE} sur {LIEU_ID}")
	if ZONE_DANGEREUSE not in base:
		erreurs.append(f"{ZONE_DANGEREUSE} n'existe pas en base")
	# Un autre placement porteur d'une table changerait le résultat par SOMME : à signaler.
	for p in lieu.get("zone_influences") or []:
		if p.get("zone") != ZONE_DANGEREUSE and p.get("profil_weights"):
			erreurs.append(
				f"le placement {p.get('zone')} en ({p.get('x')},{p.get('y')}) porte déjà une "
				f"table de grades — elle se SOMMERAIT à celle de la zone dangereuse"
			)
	if erreurs:
		for e in erreurs:
			print(f"   ERREUR : {e}")
		sys.exit(f"{len(erreurs)} erreur(s) — rien n'a été écrit.")


def main() -> None:
	base = indexer(SRC_DUMP)
	if LIEU_ID not in base:
		sys.exit(f"ERREUR : {LIEU_ID} introuvable dans {SRC_DUMP}")
	lieu = base[LIEU_ID]

	valider(base, lieu)

	avant = dict(lieu.get("profil_weights") or {})
	print("AVANT")
	print(f"   lieu           : {len(avant)} profils   {repartition(base, avant)}")
	print(f"   zone dangereuse: aucune table -> elle héritait de celle du lieu")

	# 1. Le lieu ne garde que les grades ordinaires.
	retires = {pid: w for pid, w in avant.items() if niveau_de(base, pid) >= SEUIL_HAUT_GRADE}
	lieu["profil_weights"] = {
		pid: w for pid, w in avant.items() if niveau_de(base, pid) < SEUIL_HAUT_GRADE
	}

	# 2. Les placements de la zone dangereuse portent la leur.
	poses = 0
	for p in lieu.get("zone_influences") or []:
		if p.get("zone") != ZONE_DANGEREUSE:
			continue
		if p.get("profil_weights") != GRADES_ZONE:
			poses += 1
		p["profil_weights"] = dict(GRADES_ZONE)
	placements = sum(1 for p in lieu["zone_influences"] if p.get("zone") == ZONE_DANGEREUSE)

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump([lieu], f, ensure_ascii=False, indent=2)
		f.write("\n")

	print("APRÈS")
	print(f"   lieu           : {len(lieu['profil_weights'])} profils   "
		  f"{repartition(base, lieu['profil_weights'])}")
	print(f"   zone dangereuse: {len(GRADES_ZONE)} profils   {repartition(base, GRADES_ZONE)}")
	print(f"\nécrit {SORTIE}")
	print(f"   retirés du lieu : {', '.join(sorted(retires)) or 'aucun'}")
	print(f"   table posée sur {placements} placement(s) de {ZONE_DANGEREUSE} "
		  f"({poses} modifié(s), le reste déjà à jour)")


if __name__ == "__main__":
	main()
