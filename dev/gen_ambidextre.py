#!/usr/bin/env python
# dev/gen_ambidextre.py
# Passive « Ambidextre » : lève le malus de précision des coups de la SECONDE arme
# (`DEUX_ARMES_MALUS_SECOND`, cf. utils/combat.coups_du_profil). Clé d'effet `ambidextre`,
# agrégée par `competences.bonus_passifs`, posée au snapshot de combat.
#
# Une compétence n'appartient qu'à UNE vocation (`vocation` obligatoire) : un doc par
# vocation, tous nommés « Ambidextre ». Niveaux retenus par l'Auteur (11/11) : assassin 2,
# duelliste 3, voleur 6, barbare 6, guerrier 8 — en SUS de la règle « 2 passives + 5 actives »
# de dev/gen_competences_1_10.py (exception assumée, option (a) : rien n'est retiré).
#
# ⚠️ `admin_import_bulk` fait un PUT COMPLET : seuls les docs absents du dump le plus récent,
# ou qui en diffèrent, sont écrits — régénération idempotente. Chaque doc passe les gardes
# de dev/check_competences_doc.py ; rien n'est écrit sinon.
#
# Usage : python dev/gen_ambidextre.py
# Sortie (/admin → Import en masse) : jsons/competences_ambidextre_a_importer.json

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "dev"))

import check_competences_doc as check  # noqa: E402

SORTIE = "jsons/competences_ambidextre_a_importer.json"
NOM = "Ambidextre"

# vocation → (niveau, icône, description). Joueur au NEUTRE (règle de l'Auteur, 16/10).
AMBIDEXTRES = {
	"assassin":  (2, "🗡️", "Deux lames dans le noir, et nul ne sait laquelle frappera la première."),
	"duelliste": (3, "🤺", "La main gauche ne fait plus que parer : elle porte l'estoc à l'égal de la droite, "
						  "comme le veut l'école de la rapière et de la main-gauche."),
	"voleur":    (6, "🔪", "Les ruelles ont appris aux deux mains le même métier : la seconde lame ne tremble plus."),
	"barbare":   (6, "🪓", "Une hache dans chaque poing : la seconde tombe aussi juste que la première."),
	"guerrier":  (8, "⚔️", "Des années de salle d'armes : le bras faible ne l'est plus."),
}


def docs_ambidextre() -> list:
	"""Les docs `competence:ambidextre_<vocation>`, tels qu'importés (sans `_rev`)."""
	return [{
		"_id": f"competence:ambidextre_{voc}", "type": "competence", "nom": NOM,
		"icon": icon, "description": desc, "vocation": voc, "niveau": niveau,
		"mode": "passive", "effets": {"ambidextre": 1},
	} for voc, (niveau, icon, desc) in AMBIDEXTRES.items()]


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	return dumps[-1]


def delta(base: dict) -> list:
	"""Docs neufs ou modifiés par rapport à `base` ({_id: doc}), gardes passées."""
	vocations = {d.get("vocation") for d in base.values() if d.get("type") == "competence"}
	erreurs, sortie = [], []
	for doc in docs_ambidextre():
		if doc["vocation"] not in vocations:
			erreurs.append(f"{doc['_id']} : vocation `{doc['vocation']}` inconnue du dump")
		erreurs += check.verifier_competence(doc, doc["_id"], niveaux=None)
		existant = {k: v for k, v in (base.get(doc["_id"]) or {}).items() if k != "_rev"}
		if existant != doc:
			sortie.append(doc)
	if erreurs:
		raise SystemExit("ERREUR :\n  " + "\n  ".join(erreurs))
	return sortie


def main() -> None:
	dump = _dump_le_plus_recent()
	with open(dump, encoding="utf-8") as f:
		base = {d["_id"]: d for d in json.load(f)["docs"]}
	sortie = delta(base)
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(sortie)} compétence(s) → {SORTIE} (dump {os.path.basename(dump)})")


if __name__ == "__main__":
	main()
