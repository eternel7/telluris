#!/usr/bin/env python
# dev/gen_images_guildes_pnj.py
# Portraits des réceptionnistes et maîtres de guilde : pnj/guilde_<lignée>_<sexe>_<cité>NN.jpg.
# Prompts : docs/prompts_guildes_pnj.md (chaque bloc de code précédé de son nom de fichier).
#
#   python dev/gen_images_guildes_pnj.py compter
#   python dev/gen_images_guildes_pnj.py avancer   → soumet le lot / suit / récupère dans pnj/ (PAYANT), à rejouer jusqu'à « terminé »
#
# Tout l'état vit dans dev/batch/guildes_pnj/manifeste.json. Prochain nom libre, jamais d'écrasement.

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_images_magasins as magasins  # noqa: E402

SOURCE = os.path.join(magasins.RACINE, "docs", "prompts_guildes_pnj.md")
DOSSIER = os.path.join(magasins.RACINE, "dev", "batch", "guildes_pnj")
MANIFESTE = os.path.join(DOSSIER, "manifeste.json")
REQUETES = os.path.join(DOSSIER, "requetes.jsonl")
BLOC = re.compile(r"^`(guilde_[a-z_]+)01\.jpg` — [^\n]*\n\n```\n(.+?)\n```", re.M | re.S)


def entrees():
	"""{base du nom de fichier : prompt}, lus dans le document."""
	with open(SOURCE, encoding="utf-8") as f:
		return dict(BLOC.findall(f.read()))


def _manifeste(nouveau=None):
	os.makedirs(DOSSIER, exist_ok=True)
	if nouveau is not None:
		with open(MANIFESTE, "w", encoding="utf-8") as f:
			json.dump(nouveau, f, ensure_ascii=False, indent="\t")
		return nouveau
	if os.path.exists(MANIFESTE):
		with open(MANIFESTE, encoding="utf-8") as f:
			return json.load(f)
	return _manifeste({"modele": magasins.MODELE_GEMINI, "batch": None, "lots": [], "images": {}})


def compter():
	n = len(entrees())
	print(f"{n} images ; en lot ≈ {n * magasins.EUR_PAR_IMAGE_INTERACTIF * magasins.REMISE_BATCH:.2f} €")


def _recuperer(man):
	prompts = entrees()
	ecrites, erreurs = 0, []
	for cle, part, r in magasins.reponses_lot(man["batch"]):
		if cle not in prompts or cle in man["images"]:
			continue
		if not part:
			erreurs.append(f"{cle} : {json.dumps(r.get('error') or r)[:200]}")
			continue
		nom, motif = magasins._ecrire_image(magasins.DOSSIER_PNJ, cle, part, set(man["images"].values()))
		if not nom:
			erreurs.append(f"{cle} : {motif}")
			continue
		man["images"][cle] = nom
		ecrites += 1
	man["lots"].append(man["batch"])
	man["batch"] = None
	_manifeste(man)
	print(f"{ecrites} image(s) écrite(s), {len(erreurs)} échec(s), {len(man['images'])}/{len(prompts)} au total")
	for err in erreurs:
		print("  ✗", err)


def avancer():
	man = _manifeste()
	if man.get("batch"):
		statut = magasins.statut_lot(man["batch"])
		meta = statut.get("metadata") or statut
		etat = meta.get("state")
		print(man["batch"], "→", etat, "|", meta.get("batchStats"))
		if etat in magasins.ETATS_ECHOUES:
			print("⚠ Lot en échec : ses requêtes repartiront au prochain `avancer`.")
			man["lots"].append(man["batch"])
			man["batch"] = None
			_manifeste(man)
			return
		if etat not in magasins.ETATS_REUSSIS and not statut.get("done"):
			print("En cours : rejouer `avancer` plus tard.")
			return
		_recuperer(man)
	restantes = {c: p for c, p in entrees().items() if c not in man["images"]}
	if not restantes:
		print("Terminé : toutes les images sont générées.")
		return
	with open(REQUETES, "w", encoding="utf-8") as f:
		for cle, prompt in restantes.items():
			f.write(json.dumps({"key": cle, "request": magasins.requete_gemini(prompt)}, ensure_ascii=False) + "\n")
	man["batch"] = magasins.soumettre_lot(REQUETES, man["modele"], f"images-guildes-pnj-{len(man['lots']) + 1}")
	_manifeste(man)
	print(f"Lot soumis ({len(restantes)} requête(s)) :", man["batch"])


def main():
	sys.stdout.reconfigure(encoding="utf-8")
	if len(sys.argv) != 2 or sys.argv[1] not in ("compter", "avancer"):
		raise SystemExit("Usage : gen_images_guildes_pnj.py compter|avancer")
	compter() if sys.argv[1] == "compter" else avancer()


if __name__ == "__main__":
	main()
