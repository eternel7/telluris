#!/usr/bin/env python
# dev/gen_depecage_tags.py
# Pousse les réglages de DÉPEÇAGE du défaut de code vers `rules:world_variables`.
#
# POURQUOI CE SCRIPT EXISTE. `DEPECAGE_TAGS` vit à DEUX endroits : le défaut de code
# (`models/character_stats.py`, là où on l'édite et où le diff se relit) et le doc
# `rules:world_variables` (la valeur qui tourne réellement, chargée au démarrage). Le doc
# GAGNE TOUJOURS : tant qu'il porte la clé, éditer le code ne change rien en jeu — sans le
# moindre symptôme, ce qui en fait un des pièges les plus coûteux du projet. Ce script
# transporte la table du premier vers le second.
#
# CE QU'IL POUSSE, et RIEN D'AUTRE (cf. `CLES`) :
#   · `DEPECAGE_TAGS` — quelle matière rend quel tag d'espèce ;
#   · `CARCASSE_TRANCHANT_TAG` / `CARCASSE_DECOUPE_POIDS_MIN` — la découpe des grosses
#     carcasses en portions localisées ; absentes du doc, elles retomberaient déjà sur le
#     défaut de code, mais les publier les rend ÉDITABLES depuis /admin comme les autres.
# Tout le reste du doc est recopié tel quel depuis le dump.
#
# ⚠️ LE DUMP EST UN INSTANTANÉ. Un réglage changé dans /admin depuis l'export serait ramené à
# sa valeur d'alors — `rules:world_variables` porte les ~105 variables du monde et
# `admin_import_bulk` fait un PUT COMPLET. Rafraîchir `SRC_DUMP` avant de régénérer. Le
# script imprime tout ce qui diffère entre le dump et le code, pour qu'un écart inattendu
# saute aux yeux AVANT l'import.
#
# ⚠️ IMPORTER NE SUFFIT PAS : `admin_import_bulk` écrit le doc mais n'appelle pas
# `load_world_variables()`. Après l'import, /admin → **Recharger les variables de monde**
# (POST /admin/world_variables/reload), sinon le processus continue de tourner sur l'ancienne
# table sans le moindre symptôme.
#
# ⚠️ ET RELANCER `dev/gen_carcasses_parties.py` : le dépeçage d'une portion (tête, patte…) est
# BAKÉ dans son doc item à la génération. Changer `DEPECAGE_TAGS` sans régénérer laisserait
# les portions sur l'ancienne table — les carcasses entières changeraient, les morceaux non.
#
# Usage : python dev/gen_depecage_tags.py
# Sortie (à coller dans /admin -> Import en masse) :
#   jsons/depecage_tags_a_importer.json   (1 doc : rules:world_variables)

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from models import character_stats   # noqa: E402

# SOURCE UNIQUE : le dump complet de la base. ⚠️ Figé explicitement (et non « le glob le plus
# récent ») pour que régénérer donne toujours le même résultat ; à mettre à jour à la main
# après un nouveau dump.
SRC_DUMP = "jsons/telluris-dump-20260831-122931.json"

DOC_ID = "rules:world_variables"

# Les SEULES clés que ce script écrit. Élargir cette liste, c'est élargir ce qu'un import
# écrase en base : à ne faire qu'en connaissance de cause.
CLES = ["DEPECAGE_TAGS", "CARCASSE_TRANCHANT_TAG", "CARCASSE_DECOUPE_POIDS_MIN"]

SORTIE = "jsons/depecage_tags_a_importer.json"


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(os.path.join(RACINE, chemin), encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def diff_tags(avant: dict, apres: dict) -> list[str]:
	"""Lignes lisibles décrivant ce que l'import va changer dans DEPECAGE_TAGS."""
	lignes = []
	for tag in sorted(set(avant) | set(apres)):
		a, b = list(avant.get(tag) or []), list(apres.get(tag) or [])
		if a == b:
			continue
		if tag not in avant:
			lignes.append(f"      + {tag:16} {' '.join(b)}")
		elif tag not in apres:
			lignes.append(f"      - {tag:16} (retiree)")
		else:
			# Les listes sont des MULTI-ENSEMBLES (une matiere repetee = quantite) : on
			# compare terme a terme plutot que par ensemble, sinon un doublon retire
			# passerait inapercu.
			ajouts = [m for m in b if b.count(m) > a.count(m)]
			retraits = [m for m in a if a.count(m) > b.count(m)]
			detail = []
			if ajouts:
				detail.append("+" + " +".join(sorted(set(ajouts))))
			if retraits:
				detail.append("-" + " -".join(sorted(set(retraits))))
			lignes.append(f"      ~ {tag:16} {' '.join(detail)}")
	return lignes


def main() -> None:
	docs = {d["_id"]: d for d in charger(SRC_DUMP)
			if isinstance(d, dict) and d.get("_id")}
	if DOC_ID not in docs:
		sys.exit(f"ERREUR : {DOC_ID} introuvable dans {SRC_DUMP}")

	doc = docs[DOC_ID]
	valeurs = doc.get("value")
	if not isinstance(valeurs, dict):
		sys.exit(f"ERREUR : {DOC_ID} sans bloc `value` exploitable.")

	# Le defaut de code fait foi pour les seules cles listees.
	code = character_stats.CODE_DEFAULTS
	manquantes = [c for c in CLES if c not in code]
	if manquantes:
		sys.exit(f"ERREUR : cles absentes de CODE_DEFAULTS : {manquantes}\n"
				 "   (les ajouter a current_world_variables() dans character_stats.py)")

	lignes_diff = []
	for cle in CLES:
		avant, apres = valeurs.get(cle), code[cle]
		if avant == apres:
			print(f"   {cle:28} identique (reimport sans effet)")
			continue
		if cle == "DEPECAGE_TAGS" and isinstance(avant, dict):
			print(f"   {cle:28} MODIFIEE :")
			lignes_diff += diff_tags(avant, apres)
		else:
			print(f"   {cle:28} {avant!r} -> {apres!r}")
		valeurs[cle] = apres
	for ligne in lignes_diff:
		print(ligne)

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump([doc], f, ensure_ascii=False, indent=2)
		f.write("\n")

	# Sorties en ASCII : la console Windows par defaut encode en cp1252 (dev_tools, lui,
	# force PYTHONIOENCODING=utf-8 pour le lancement depuis /admin).
	print(f"ecrit {SORTIE}")
	print(f"   1 doc ({DOC_ID}), {len(valeurs)} variables de monde au total")
	print("   ATTENTION apres l'import : /admin -> Recharger les variables de monde")
	print("   ET relancer dev/gen_carcasses_parties.py (le depecage des portions est bake)")


if __name__ == "__main__":
	main()
