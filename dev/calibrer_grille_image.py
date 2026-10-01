"""Mesure — et optimise sur demande — les profils de `utils/grille_image.PROFILS_GRILLE`
contre les grilles peintes à la main.

POURQUOI UN SCRIPT : un seuil réglé à l'œil sur une carte se trompe sur la suivante. Les dix
lieux à grille peinte (trois villes, quatre forêts, quatre souterrains) sont la seule vérité
terrain du dépôt ; ce script les relit dans le DUMP, échantillonne leurs images une fois, et
note chaque profil sur les lieux qui lui reviennent.

Score = F1 moyen PAR VALEUR (`concordance`), jamais le taux global : sur une carte à 65 % de
cases libres, répondre « libre » partout afficherait 65 %. Imprimé aussi : le rappel des murs
`nav` peints (à une case près) et ce que la topologie a fait (passages, zones isolées).

`--optimiser` : descente par coordonnées sur les poids et décalages du profil (pas 1 ; 0,5 ;
0,25), puis VALIDATION EN LAISSANT UN LIEU DE CÔTÉ — chaque lieu est noté par un réglage
appris sans lui. Un écart fort entre « entraîné » et « testé » signale un réglage qui imite
ses cartes au lieu de lire l'image. ⚠️ Le script n'écrit rien : le jeu retenu se recopie À LA
MAIN dans `PROFILS_GRILLE`, avec la mesure qui le justifie en commentaire.

Usage :
  python dev/calibrer_grille_image.py                     # les trois profils, réglage actuel
  python dev/calibrer_grille_image.py ville               # un profil
  python dev/calibrer_grille_image.py ville --optimiser   # + descente et validation croisée
  python dev/calibrer_grille_image.py --apercus           # + jsons/calibration_<lieu>.png
"""

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import grille_image  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_grille_image as gen  # noqa: E402

# Lieux de calibration par profil — ceux qui portent une grille peinte à la main.
LIEUX_CALIBRATION = {
	"ville": ["lieu:auxerre", "lieu:lutecia", "lieu:rhemi"],
	"foret": ["lieu:chemin1", "lieu:chemin2", "lieu:clariere01", "lieu:grotte_en_foret"],
	"catacombes": ["lieu:catacombes0001", "lieu:catacombes0002", "lieu:catacombes0003",
		"lieu:la_mine_aux_cristaux"],
}


def charger(ids, docs):
	"""{id: {doc, couleurs, contours, cols, rows}} — images échantillonnées une fois."""
	sortie = {}
	for lid in ids:
		doc = next((d for d in docs if d.get("_id") == lid), None)
		if not doc or not doc.get("cells") or not doc.get("image"):
			print(f"  ⚠ {lid} : absent du dump, sans grille ou sans image — ignoré.")
			continue
		chemin = gen.trouver_image(doc["image"])
		if not chemin:
			print(f"  ⚠ {lid} : image introuvable ({doc['image']}) — ignoré.")
			continue
		cols, rows = len(doc["cells"][0]), len(doc["cells"])
		couleurs, contours, _ = gen.echantillonner(chemin, cols, rows)
		sortie[lid] = {"doc": doc, "couleurs": couleurs, "contours": contours,
			"fins": gen.echantillonner_fins(chemin, cols, rows),
			"cols": cols, "rows": rows, "chemin": chemin}
	return sortie


def noter(lieu, regles, topologie=False):
	"""(f1 moyen, concordance, résultat de `proposer` ou None).

	⚠️ `proposer` part ici d'un `nav` VIDE, pas de celui du doc : il conserve tous les bits
	qu'on lui donne, et le rappel des murs peints serait de 100 % par construction."""
	if topologie:
		res = grille_image.proposer(lieu["couleurs"], lieu["contours"], lieu["cols"],
			lieu["rows"], nav=None, regles=regles, fins=lieu["fins"])
		cells = res["cells"]
	else:
		# Classification + lissage + rues : ce que la descente règle (la topologie, plus
		# lente, ne change presque pas le score et n'a pas de paramètre de couleur).
		res = None
		cells = grille_image.proposer(lieu["couleurs"], lieu["contours"], lieu["cols"],
			lieu["rows"], regles=regles, fins=lieu["fins"], passages=False)["cells"]
	rapport = grille_image.concordance(cells, lieu["doc"]["cells"])
	return rapport["f1_moyen"], rapport, res


def score_moyen(lieux, regles):
	return sum(noter(l, regles)[0] for l in lieux) / len(lieux) if lieux else 0.0


def _reglages(regles):
	"""Les boutons de la descente : poids des scores et décalages (et l'écart d'eau).
	⚠️ Le poids des contours du bâti n'en est PAS : fixé à la main (cf. `PROFILS_GRILLE`)."""
	cles = [("obstacle", n) for n in grille_image.INDICES if n != "contours"]
	cles.append(("obstacle_decalage", None))
	if regles.get("roche"):
		cles += [("roche", n) for n in grille_image.INDICES] + [("roche_decalage", None)]
	if regles.get("eau", True):
		cles.append(("eau_ecart_froideur", None))
	if regles.get("rues"):
		cles += [("rues", "poids_saturation"), ("rues", "decalage")]
	return cles


def optimiser(lieux, regles):
	"""Descente par coordonnées, déterministe. Rend (score, règles)."""
	regles = copy.deepcopy(regles)
	meilleur = score_moyen(lieux, regles)
	for pas in (1.0, 0.5, 0.25):
		ameliore = True
		while ameliore:
			ameliore = False
			for cle, sous in _reglages(regles):
				for d in (-pas, pas):
					essai = copy.deepcopy(regles)
					if sous is None:
						essai[cle] = essai.get(cle, 0.0) + (d * 10 if cle == "eau_ecart_froideur" else d / 2)
					else:
						essai[cle][sous] = essai[cle].get(sous, 0.0) + d
						if not any(essai[cle].values()):
							continue
					s = score_moyen(lieux, essai)
					if s > meilleur + 1e-4:
						meilleur, regles, ameliore = s, essai, True
	return meilleur, regles


def imprimer(lid, lieu, regles):
	f1, rapport, res = noter(lieu, regles, topologie=True)
	nav = grille_image.concordance_nav(res["nav"], lieu["doc"].get("nav"))
	valeurs = "  ".join(f"{v}: R {m['rappel']:.2f} P {m['precision']:.2f}"
		for v, m in sorted(rapport["par_valeur"].items()))
	r = res["rapport"]
	print(f"  {lid:28} F1 {f1:.3f}   {valeurs}")
	if regles.get("rues"):
		# Rues retrouvées = cases peintes 1 que la classification SANS rues rendait bâties.
		sans = grille_image.proposer(lieu["couleurs"], lieu["contours"], lieu["cols"],
			lieu["rows"], regles=regles, passages=False)["cells"]
		peinte = lieu["doc"]["cells"]
		cibles = {(x, y) for y, ligne in enumerate(sans) for x, v in enumerate(ligne)
			if v == grille_image.TERRAIN_INACCESSIBLE and peinte[y][x] == grille_image.TERRAIN_LIBRE}
		ouvertes = {tuple(c) for c in r["rues"]}
		justes = len(cibles & ouvertes)
		print(f"  {'':28} rues : {len(ouvertes)} case(s) ouverte(s), {justes} peinte(s) 1"
			f" (précision {justes / max(1, len(ouvertes)):.2f}) — rues peintes retrouvées"
			f" {justes}/{len(cibles)} ({justes / max(1, len(cibles)):.2f})")
	print(f"  {'':28} nav peint retrouvé {nav['retrouvees']}/{nav['peintes']}"
		f"  · {len(r['passages'])} passage(s) · {r['zones']} zone(s) praticable(s)"
		f" dont {len(r['zones_isolees'])} isolée(s) signalée(s)"
		f" · {r['nav_ajoutes']} bit(s) nav · enceinte {'oui' if r['enceinte'] else 'non'}")
	return res


def main() -> int:
	args = [a for a in sys.argv[1:] if not a.startswith("--")]
	options = {a for a in sys.argv[1:] if a.startswith("--")}
	profils = args or list(LIEUX_CALIBRATION)
	inconnus = [p for p in profils if p not in LIEUX_CALIBRATION]
	if inconnus:
		print(f"✗ profil(s) inconnu(s) : {', '.join(inconnus)} — {', '.join(LIEUX_CALIBRATION)}")
		return 2
	docs = gen.charger_dump()
	for profil in profils:
		regles = grille_image.PROFILS_GRILLE[profil]
		print(f"\n══ {profil} ══")
		lieux = charger(LIEUX_CALIBRATION[profil], docs)
		if not lieux:
			continue
		print(f"  Réglage actuel — F1 moyen {score_moyen(list(lieux.values()), regles):.3f}")
		for lid, lieu in lieux.items():
			res = imprimer(lid, lieu, regles)
			if "--apercus" in options:
				cible = os.path.join(gen.DOSSIER_JSONS, f"calibration_{lid.split(':', 1)[1]}.png")
				gen.ecrire_apercu(lieu["chemin"], res["cells"], cible, res["nav"], res["rapport"])
				print(f"  {'':28} ✎ {os.path.relpath(cible, gen.RACINE)}")
		if "--optimiser" not in options:
			continue
		score, meilleures = optimiser(list(lieux.values()), regles)
		print(f"  Optimisé — F1 moyen {score:.3f}")
		for lid, lieu in lieux.items():
			imprimer(lid, lieu, meilleures)
		print("  Validation en laissant un lieu de côté :")
		for lid, lieu in lieux.items():
			autres = [l for k, l in lieux.items() if k != lid]
			if not autres:
				continue
			entraine, apprises = optimiser(autres, regles)
			print(f"    {lid:28} entraîné {entraine:.3f}   testé {noter(lieu, apprises)[0]:.3f}")
		print("  Jeu retenu (à recopier dans PROFILS_GRILLE) :")
		print(json.dumps({k: meilleures[k] for k in ("obstacle", "obstacle_decalage", "roche",
			"roche_decalage", "eau_ecart_froideur", "rues") if k in meilleures},
			ensure_ascii=False, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
