#!/usr/bin/env python
# dev/gen_images_logements.py
# Images des logements du joueur (Chambre → Domaine) par région : towns/<type>_<region>NN.jpg.
# Prompts : docs/prompts_images.md § 7 (chaque bloc de code précédé de son titre « #### Type — `fichier01.jpg` »).
# Une image déposée est proposée au propriétaire sans import ni redémarrage (`proprietes.images_du_type`).
#
#   python dev/gen_images_logements.py compter
#   python dev/gen_images_logements.py avancer   → soumet le lot / suit / récupère dans towns/ (PAYANT), à rejouer jusqu'à « terminé »
#   python dev/gen_images_logements.py refaire maison_europe,domaine_europe  → remet ces clés au prochain lot
#
# Tout l'état vit dans dev/batch/logements/manifeste.json. Prochain nom libre, jamais d'écrasement.

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_images_magasins as magasins  # noqa: E402

SOURCE = os.path.join(magasins.RACINE, "docs", "prompts_images.md")
DOSSIER = os.path.join(magasins.RACINE, "dev", "batch", "logements")
MANIFESTE = os.path.join(DOSSIER, "manifeste.json")
REQUETES = os.path.join(DOSSIER, "requetes.jsonl")
TYPES = ("chambre", "logement", "maison", "demeure", "domaine")
BLOC = re.compile(r"^#### [^\n]*`((?:" + "|".join(TYPES) + r")_[a-z_]+)01\.jpg`\s*\n\s*\n```\n(.+?)\n```", re.M | re.S)
ATTENDUES = 30  # 5 types de bien × 6 régions de rules:regions (§ 7 du document)


def entrees():
	"""{base du nom de fichier : prompt}, lus dans le § 7 du document."""
	with open(SOURCE, encoding="utf-8") as f:
		texte = f.read().replace("\r\n", "\n")
	debut = texte.find("## 7. Logements")
	if debut < 0:
		raise SystemExit("ERREUR : § 7 introuvable dans docs/prompts_images.md.")
	fin = texte.find("\n## ", debut + 1)
	trouvees = BLOC.findall(texte[debut:fin if fin > 0 else None])
	prompts = dict(trouvees)
	if len(prompts) != len(trouvees) or len(prompts) != ATTENDUES:
		raise SystemExit(f"ERREUR : {len(trouvees)} prompt(s) lus ({len(prompts)} distincts), {ATTENDUES} attendus.")
	return prompts


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
		nom, motif = magasins._ecrire_image(magasins.DOSSIER_TOWNS, cle, part, set(man["images"].values()))
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
	man["batch"] = magasins.soumettre_lot(REQUETES, man["modele"], f"images-logements-{len(man['lots']) + 1}")
	_manifeste(man)
	print(f"Lot soumis ({len(restantes)} requête(s)) :", man["batch"])


def refaire(cles):
	"""Remet des clés à générer au prochain `avancer` (l'ancien fichier, renommé ou gardé, est noté
	dans `remplacees` ; rien n'est supprimé ici)."""
	man = _manifeste()
	connues = entrees()
	inconnues = [c for c in cles if c not in connues]
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
		raise SystemExit("Usage : gen_images_logements.py compter|avancer|refaire <clé,clé…>")
	compter() if sys.argv[1] == "compter" else avancer()


if __name__ == "__main__":
	main()
