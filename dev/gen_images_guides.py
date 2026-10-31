#!/usr/bin/env python
# dev/gen_images_guides.py
# Portraits des guides : pnj/guide_<type>_<sexe>_<lignée>NN.jpg. Pour chaque type et chaque
# Lignée : 2 femmes + 2 hommes (20 images par type). Gabarits : dev/gabarits_guides.py.
#
#   python dev/gen_images_guides.py compter
#   python dev/gen_images_guides.py essai --seulement guide_routes_f_nain#1,…   → interactif, dev/batch/guides/essais/ (PAYANT)
#   python dev/gen_images_guides.py avancer   → soumet le lot / suit / récupère dans pnj/ (PAYANT), à rejouer jusqu'à « terminé »
#
# Tout l'état vit dans dev/batch/guides/manifeste.json. Prochain nom libre, jamais d'écrasement.
# ⚠️ Aucun nom propre dans un prompt : le modèle le peint. Fonctions d'API : gen_images_magasins.

import argparse
import json
import os
import random
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_images_magasins as magasins  # noqa: E402
from gabarits_guides import GUIDES  # noqa: E402

DOSSIER = os.path.join(magasins.RACINE, "dev", "batch", "guides")
MANIFESTE = os.path.join(DOSSIER, "manifeste.json")
REQUETES = os.path.join(DOSSIER, "requetes.jsonl")
LIGNEES = ["humain", "elfe", "nain", "ogre", "hobbit"]
SEXES = ["F", "M"]
PAR_SEXE = 2

# Repères de Lignée SANS autre personnage (consigne de l'auteur, 31/10) : ceux des marchands
# posent un humain « au même plan », que le modèle peignait à côté du guide. L'échelle passe
# par le décor.
MARQUEURS = {
	"nain": ("nettement plus petit{e} qu'un humain, trapu{e}, tête et mains grandes pour sa taille{imberbe} ; "
			 "sa petite taille se lit au décor : une porte, un tonneau, un muret ou un outil fait pour des "
			 "humains paraît grand à côté {de_lui}"),
	"hobbit": ("de toute petite taille d'adulte, pieds nus ; sa petite taille se lit au décor : une porte, un "
			   "tonneau, un muret ou un outil fait pour des humains paraît immense à côté {de_lui}"),
	"elfe": "aux oreilles longues et pointues",
	"ogre": ("bien plus grand{e} et massi{ve} qu'un humain, peau épaisse au teint humain, jamais verte ni "
			 "gris-vert, parfois de petits crocs pointant de la lèvre inférieure ; sa grande taille se lit au "
			 "décor : une porte, un muret ou un outil fait pour des humains paraît petit à côté {de_lui}"),
	"humain": "",
}


def entrees():
	"""PURE. Toutes les images à produire : tirages et variantes stables d'un rejeu à l'autre."""
	sortie = []
	for type_id in GUIDES:
		for li, race in enumerate(LIGNEES):
			for si, sexe in enumerate(SEXES):
				for n in range(1, PAR_SEXE + 1):
					base = f"guide_{type_id}_{sexe.lower()}_{race}"
					cle = f"{base}#{n}"
					rng = random.Random(zlib.crc32(cle.encode()))
					# Les 20 images d'un type se répartissent les 10 variantes sans doublon proche.
					variante = (li * 4 + si * 2 + n - 1) % len(GUIDES[type_id][1])
					sortie.append({"key": cle, "type": type_id, "race": race, "sexe": sexe, "base": base,
								   "variante": variante, "tirage": magasins.tirage_tenancier(rng)})
	return sortie


def prompt_guide(e):
	"""PURE. Prompt complet d'un portrait de guide."""
	f = e["sexe"] == "F"
	une_f, un_m, _ = magasins.LIGNEES[e["race"]]
	marqueur = MARQUEURS[e["race"]].replace("{de_lui}", "d'elle" if f else "de lui")
	qui, variantes = GUIDES[e["type"]]
	objet, tenue, decor = variantes[e["variante"]]
	corps = ", ".join(magasins._accord(t, f) for t in e["tirage"])
	sujet = (une_f if f else un_m) + f" {corps}" + (f", {magasins._accord(marqueur, f)}" if marqueur else "")
	sujet = sujet[0].lower() + sujet[1:]
	il = "Elle" if f else "Il"
	age = magasins._accord(e["tirage"][0], f)
	return (f"Réalise l'image d'{sujet}. {il} {qui}, dans un monde médiéval fantastique. Format paysage large. "
			f"Son âge — {age} — doit se lire clairement : ne le vieillis pas, aucune ride ni aucun cheveu blanc "
			f"que cet âge ne justifie pas. {il} est seul{'e' if f else ''} à l'image : aucun autre personnage, ni à "
			f"côté ni au loin. Cadrage de portrait, de la tête à la taille ou à mi-cuisse, le visage bien lisible, "
			f"légèrement décalé{'e' if f else ''} du centre ; {il.lower()} regarde droit vers le spectateur, prêt{'e' if f else ''} à "
			f"l'accompagner en route. On pourrait {'la' if f else 'le'} voir tenir {objet}, porter {tenue}, avec "
			f"pour décor : {decor} ; rien de tout cela n'est imposé. Compose librement le cadrage, la lumière, la "
			f"posture et les couleurs : cette personne doit avoir une allure qui n'appartient qu'à elle, jamais "
			f"une tenue type. Aucun symbole religieux. Pas de texte visible. {magasins.STYLE_FR}")


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
	total = entrees()
	print(f"{len(GUIDES)} types, {len(total)} images ; en lot ≈ "
		  f"{len(total) * magasins.EUR_PAR_IMAGE_INTERACTIF * magasins.REMISE_BATCH:.2f} €")


def essai(cles):
	dossier = os.path.join(DOSSIER, "essais")
	os.makedirs(dossier, exist_ok=True)
	a_faire = [e for e in entrees() if e["key"] in cles]
	inconnues = cles - {e["key"] for e in a_faire}
	if inconnues:
		raise SystemExit(f"Clés inconnues : {sorted(inconnues)}")
	print(f"{len(a_faire)} essai(s), ≈ {len(a_faire) * magasins.EUR_PAR_IMAGE_INTERACTIF:.2f} €", flush=True)
	for e in a_faire:
		_, rep = magasins._http(f"{magasins.API}/v1beta/models/{magasins.MODELE_GEMINI}:generateContent",
								magasins.requete_gemini(prompt_guide(e)))
		part = magasins.image_de_reponse(json.loads(rep))
		if not part:
			print(f"  ✗ {e['key']} : {rep.decode('utf-8', 'replace')[:300]}", flush=True)
			continue
		nom, motif = magasins._ecrire_image(dossier, e["base"], part, ())
		print(f"  {nom or '✗ ' + motif}", flush=True)


def _ecrire_requetes(man):
	restantes = [e for e in entrees() if e["key"] not in man["images"]]
	os.makedirs(DOSSIER, exist_ok=True)
	with open(REQUETES, "w", encoding="utf-8") as f:
		for e in restantes:
			f.write(json.dumps({"key": e["key"], "request": magasins.requete_gemini(prompt_guide(e))},
							   ensure_ascii=False) + "\n")
	return len(restantes)


def _recuperer(man):
	par_cle = {e["key"]: e for e in entrees()}
	ecrites, erreurs = 0, []
	for cle, part, r in magasins.reponses_lot(man["batch"]):
		e = par_cle.get(cle)
		if not e or cle in man["images"]:
			continue
		if not part:
			erreurs.append(f"{cle} : {json.dumps(r.get('error') or r)[:200]}")
			continue
		nom, motif = magasins._ecrire_image(magasins.DOSSIER_PNJ, e["base"], part, set(man["images"].values()))
		if not nom:
			erreurs.append(f"{cle} : {motif}")
			continue
		man["images"][cle] = nom
		ecrites += 1
	man["lots"].append(man["batch"])
	man["batch"] = None
	_manifeste(man)
	print(f"{ecrites} image(s) écrite(s), {len(erreurs)} échec(s), {len(man['images'])}/{len(par_cle)} au total")
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
	n = _ecrire_requetes(man)
	if not n:
		print("Terminé : toutes les images sont générées.")
		return
	man["batch"] = magasins.soumettre_lot(REQUETES, man["modele"], f"images-guides-{len(man['lots']) + 1}")
	_manifeste(man)
	print(f"Lot soumis ({n} requête(s)) :", man["batch"])


def main():
	sys.stdout.reconfigure(encoding="utf-8")
	p = argparse.ArgumentParser(description=__doc__)
	sous = p.add_subparsers(dest="commande", required=True)
	sous.add_parser("compter")
	sous.add_parser("avancer")
	pe = sous.add_parser("essai")
	pe.add_argument("--seulement", required=True, help="clés séparées par des virgules, ex. guide_routes_f_nain#1")
	a = p.parse_args()
	if a.commande == "compter":
		compter()
	elif a.commande == "avancer":
		avancer()
	else:
		essai(set(a.seulement.split(",")))


if __name__ == "__main__":
	main()
