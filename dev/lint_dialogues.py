"""Vérifie la cohérence des arbres de dialogue PNJ d'un ou plusieurs fichiers JSON.

Un dialogue est de la DONNÉE : rien ne le type ni ne l'exécute à l'import. Une référence
morte (`next` vers un nœud inexistant, `services.transport.noeuds.accepte` pointant à côté)
ou une condition mal orthographiée ne se voit qu'en JOUANT la branche — et une branche
conditionnée qui ne s'affiche jamais est indiscernable d'un tirage malheureux. Ce script
rend ces fautes visibles avant l'import.

La logique vit dans `utils/lint_dialogues.py` (pur, sans DB) : le bouton « Vérifier » de la
page d'import `/admin` appelle exactement le même code. Même précédent que `utils/xlsx.py`,
partagé par l'export bestiaire et l'export du tableau admin.

	python dev/lint_dialogues.py jsons/marchand_etable_exemple.json
	python dev/lint_dialogues.py jsons/*.json
	python dev/lint_dialogues.py            # tous les jsons/ du dépôt

Sort en code 1 s'il reste au moins une ERREUR (utilisable en pré-commit) ; les
avertissements n'échouent pas.
"""

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils.lint_dialogues import analyser   # noqa: E402  (après le sys.path)

# Le terminal Windows n'est pas toujours en UTF-8 : sans repli, un simple « … » dans un
# message ferait planter le script au lieu de rapporter les fautes qu'il a trouvées.
def ecrire(ligne: str) -> None:
	try:
		print(ligne)
	except UnicodeEncodeError:
		print(ligne.encode("ascii", "replace").decode("ascii"))


def fichiers_cibles(args: list) -> list:
	if args:
		# Le shell ne développe pas toujours les jokers (cmd.exe) : on s'en charge.
		cibles = []
		for a in args:
			cibles.extend(sorted(glob.glob(a)) or [a])
		return cibles
	# Sans argument : les fichiers qu'on IMPORTE. Les `telluris-dump-*.json` sont des
	# ARCHIVES d'états passés de la base — elles gardent les fautes déjà corrigées depuis
	# et rendraient la sortie ininterprétable. On peut toujours en viser une explicitement.
	return [c for c in sorted(glob.glob(os.path.join(RACINE, "jsons", "*.json")))
			if not os.path.basename(c).startswith("telluris-dump-")]


def main() -> None:
	cibles = fichiers_cibles(sys.argv[1:])
	if not cibles:
		raise SystemExit("Aucun fichier à vérifier.")

	total_err = total_av = total_doc = 0
	for chemin in cibles:
		try:
			with open(chemin, encoding="utf-8") as f:
				payload = json.load(f)
		except (OSError, json.JSONDecodeError) as e:
			ecrire(f"\n== {os.path.basename(chemin)} ==")
			ecrire(f"  ERREUR  illisible : {e}")
			total_err += 1
			continue

		bilan = analyser(payload)
		total_doc += bilan["analyses"]
		total_err += bilan["erreurs"]
		total_av += bilan["avertissements"]

		# Un fichier sans aucun dialogue (items, lieux, espèces…) n'a rien à dire : on ne
		# l'affiche que si on l'a explicitement demandé, sinon la sortie serait noyée.
		if not bilan["analyses"] and not sys.argv[1:]:
			continue

		ecrire(f"\n== {os.path.basename(chemin)} : {bilan['analyses']} dialogue(s), "
			   f"{bilan['ignores']} doc(s) sans dialogue ==")
		if not bilan["trouvailles"]:
			ecrire("  OK")
		for t in bilan["trouvailles"]:
			etiquette = "ERREUR " if t["niveau"] == "erreur" else "AVERTI "
			ou = f" [{t['noeud']}]" if t["noeud"] else ""
			ecrire(f"  {etiquette} {t['doc_id']}{ou} : {t['message']}")

	ecrire(f"\n{total_doc} dialogue(s) vérifié(s) — {total_err} erreur(s), "
		   f"{total_av} avertissement(s).")
	sys.exit(1 if total_err else 0)


if __name__ == "__main__":
	main()
