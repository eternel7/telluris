#!/usr/bin/env python
# dev/gen_images_monstres.py
# Illustrations des espèces sans image : Gemini (lot, carré 1:1, fond uni) → détourage → monsters/<base>_transparent.png.
# Prompts : dev/batch/monstres/prompts.json ({base : {espece, champ_image, prompt}}), gabarit docs/prompts_images.md § 3.
#
#   python dev/gen_images_monstres.py compter
#   python dev/gen_images_monstres.py avancer   → soumet le lot / suit / récupère et détoure (PAYANT), à rejouer jusqu'à « terminé »
#   python dev/gen_images_monstres.py refaire apep,lamie  → remet ces clés au prochain lot
#
# État : dev/batch/monstres/manifeste.json. Image brute gardée dans dev/batch/monstres/brutes/ (re-détourage à la main
# avec dev/detourer_image.py si le fond résiste). Jamais d'écrasement : `<base>_transparent.png` pris → `…_transparent01.png`.

import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_images_magasins as magasins  # noqa: E402
from detourer_image import detourer  # noqa: E402

DOSSIER = os.path.join(magasins.RACINE, "dev", "batch", "monstres")
PROMPTS = os.path.join(DOSSIER, "prompts.json")
MANIFESTE = os.path.join(DOSSIER, "manifeste.json")
REQUETES = os.path.join(DOSSIER, "requetes.jsonl")
BRUTES = os.path.join(DOSSIER, "brutes")
MONSTRES = os.path.join(magasins.RACINE, "templates", "resources", "monsters")
RATIO = "1:1"  # docs/prompts_images.md § 0.3 : monstre carré


def entrees():
	with open(PROMPTS, encoding="utf-8") as f:
		return {base: e["prompt"] for base, e in json.load(f).items()}


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


def nom_transparent(base):
	"""PURE sur le dossier : `<base>_transparent.png`, sinon la première variante numérotée libre."""
	nom, n = f"{base}_transparent.png", 0
	while os.path.exists(os.path.join(MONSTRES, nom)):
		n += 1
		nom = f"{base}_transparent{n:02d}.png"
	return nom


def requete(prompt):
	r = magasins.requete_gemini(prompt)
	r["generationConfig"]["imageConfig"]["aspectRatio"] = RATIO
	return r


def compter():
	n = len(entrees())
	print(f"{n} images ; en lot ≈ {n * magasins.EUR_PAR_IMAGE_INTERACTIF * magasins.REMISE_BATCH:.2f} €")


def _recuperer(man):
	prompts = entrees()
	os.makedirs(BRUTES, exist_ok=True)
	ecrites, erreurs = 0, []
	for cle, part, r in magasins.reponses_lot(man["batch"]):
		if cle not in prompts or cle in man["images"]:
			continue
		if not part:
			erreurs.append(f"{cle} : {json.dumps(r.get('error') or r)[:200]}")
			continue
		octets = base64.b64decode(part["inlineData"]["data"])
		rejet = magasins.image_degeneree(*magasins._mesures(octets))
		if rejet:
			erreurs.append(f"{cle} : image {rejet}")
			continue
		ext = ".jpg" if "jpeg" in part["inlineData"].get("mimeType", "") else ".png"
		brute = os.path.join(BRUTES, cle + ext)
		with open(brute, "wb") as f:
			f.write(octets)
		nom = nom_transparent(cle)
		fond, taille, part_fond = detourer(brute, os.path.join(MONSTRES, nom))
		man["images"][cle] = nom
		ecrites += 1
		print(f"  ✓ {nom} : fond {tuple(round(c) for c in fond)}, {taille[0]}x{taille[1]}, {part_fond:.0%} retiré")
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
			f.write(json.dumps({"key": cle, "request": requete(prompt)}, ensure_ascii=False) + "\n")
	man["batch"] = magasins.soumettre_lot(REQUETES, man["modele"], f"images-monstres-{len(man['lots']) + 1}")
	_manifeste(man)
	print(f"Lot soumis ({len(restantes)} requête(s)) :", man["batch"])


def refaire(cles):
	"""Remet des clés au prochain `avancer` ; l'ancien fichier reste (noté dans `remplacees`), le nouveau prend
	la variante numérotée suivante."""
	man = _manifeste()
	inconnues = [c for c in cles if c not in entrees()]
	if inconnues:
		raise SystemExit(f"ERREUR : clé(s) inconnue(s) : {', '.join(inconnues)}")
	if man.get("batch"):
		raise SystemExit("ERREUR : un lot est en cours ; le terminer d'abord (`avancer`).")
	for c in cles:
		ancien = man["images"].pop(c, None)
		if ancien:
			man.setdefault("remplacees", []).append({"cle": c, "fichier": ancien})
	_manifeste(man)
	print(f"{len(cles)} clé(s) à refaire : {', '.join(cles)}")


def main():
	sys.stdout.reconfigure(encoding="utf-8")
	if len(sys.argv) == 3 and sys.argv[1] == "refaire":
		return refaire([c.strip() for c in sys.argv[2].split(",") if c.strip()])
	if len(sys.argv) != 2 or sys.argv[1] not in ("compter", "avancer"):
		raise SystemExit("Usage : gen_images_monstres.py compter|avancer|refaire <clé,clé…>")
	compter() if sys.argv[1] == "compter" else avancer()


if __name__ == "__main__":
	main()
