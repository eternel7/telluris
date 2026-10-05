#!/usr/bin/env python
"""Compétences de vocation des niveaux 3, 6 et 10 — import tiré du document de conception.

    python dev/gen_competences_3_6_10.py

Source :  docs/competences_vocations_3_6_10.md (chaque bloc ```json``` = un doc COMPLET)
Sortie :  jsons/competences_vocations_3_6_10_a_importer.json   (carte d'import de /admin)

Le document reste la source : on y retouche une compétence, puis on relance ce script.
⚠️ Garde-fou — rien n'est écrit si `dev/check_competences_doc.py` échoue (JSON invalide,
invariants du moteur, `_id` déjà pris en base ou dans un autre `jsons/*_a_importer.json`,
vocation inconnue) : `admin_import_bulk` fait un PUT complet et ne refuse rien.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_competences_doc as check  # noqa: E402

SORTIE = os.path.join(check.DOSSIER_JSONS, check.IMPORT_DU_DOC)


def main():
	code = check.main()
	if code:
		print("\nRien n'est écrit : le document ne passe pas le vérificateur.")
		return code
	docs = [json.loads(brut) for _ligne, brut in check.charger_blocs(check.DOC_DEFAUT)]
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		json.dump(docs, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print(f"\n{len(docs)} doc(s) écrits dans {os.path.relpath(SORTIE, check.RACINE)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
