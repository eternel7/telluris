# utils/images_lieu.py
# Image d'un lieu TIRÉE AU SORT parmi ses variantes (pur) — demande de l'Auteur, 19/11/2026 :
# « comme pour les monstres », mais déclarée sur le lieu (Auteur, même jour) :
#
#   "image": "ateliers_de_convergence01.jpg",             # image par défaut (inchangée)
#   "images": ["ateliers_de_convergence01.jpg", "ateliers_de_convergence02.jpg"]
#
# ⚠️ Liste EXPLICITE, jamais lue dans le dossier : beaucoup d'images de boutiques sont
# numérotées et partagées entre lieux (`fletcher_europe01…05`) — une convention de nommage
# changerait le décor de lieux qui n'ont rien demandé (cf. `utils/images_monstres.py`, où le
# dossier fait foi, mais pour une espèce seulement).
#
# Tirage à l'ENTRÉE, comme la présence des PNJ (`pnj.poser_pnj_present`) : champ transitoire
# `character["image_tiree"] = {"lieu", "image"}` — un rafraîchissement ne retire pas, ressortir
# puis revenir retire (CLAUDE.md, conventions 6 et 17). Champ absent, liste absente, vide ou
# sans fichier présent ⇒ `image` du lieu, comportement d'avant (convention 4).
#
# Module PUR : l'existence des fichiers est injectée (`existe_fn`), le hasard aussi.

import random


def variantes(lieu_doc: dict, existe_fn) -> list:
	"""Variantes SERVABLES du lieu : noms de `images` présents sur le disque, sans doublon,
	dans l'ordre écrit. Un fichier manquant est écarté (sinon /play répondrait 404)."""
	vus, out = set(), []
	for f in (lieu_doc or {}).get("images") or []:
		if isinstance(f, str) and f and f not in vus and existe_fn(f):
			vus.add(f)
			out.append(f)
	return out


def poser_image_tiree(character: dict, lieu_doc: dict, existe_fn, nouvelle_entree: bool,
					  choix_fn=random.choice) -> bool:
	"""Tire l'image du lieu à une NOUVELLE ENTRÉE (ou si le tirage gardé n'est plus valable),
	et la garde sur le personnage (mute sans save). → True si le champ a changé."""
	lieu_id = (lieu_doc or {}).get("_id")
	choix = variantes(lieu_doc, existe_fn)
	tiree = character.get("image_tiree") or {}
	if not lieu_id or len(choix) < 2:
		if tiree:
			character.pop("image_tiree", None)
			return True
		return False
	if not nouvelle_entree and tiree.get("lieu") == lieu_id and tiree.get("image") in choix:
		return False
	character["image_tiree"] = {"lieu": lieu_id, "image": choix_fn(choix)}
	return True


def image_effective(character: dict, lieu_doc: dict, existe_fn) -> str | None:
	"""L'image à afficher : celle tirée pour CE lieu si elle est toujours une variante
	servable, sinon `image` du lieu."""
	tiree = (character or {}).get("image_tiree") or {}
	if tiree.get("lieu") == (lieu_doc or {}).get("_id") and tiree.get("image") in variantes(lieu_doc, existe_fn):
		return tiree["image"]
	return (lieu_doc or {}).get("image")
