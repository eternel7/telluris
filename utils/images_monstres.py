"""Image d'un monstre en combat (pur) : choix parmi les VARIANTES de son espèce.

Convention de nommage, LUE dans le dossier, jamais déclarée dans la donnée :
`<base>_transparent<suffixe>.png`, `<base>` tiré de `espece.image`.
- suffixe vide ou numéroté (`01`, `02`…) → variante GÉNÉRIQUE ;
- suffixe à mots (`_arc`, `_epee`, `_arc01`…) → variante SPÉCIALISÉE, choisie seulement
  si CHAQUE mot est porté par une arme équipée (id, `sous_categorie` ou tag). Un mot
  qu'aucune arme ne porte (`_monture`) exclut donc la variante du combat.
Choix : spécialisées compatibles (l'évidente) → sinon génériques, à poids égaux →
sinon `espece.image` inchangé.
"""
from __future__ import annotations

import random
import re

_MOTIF = re.compile(r"^(?P<base>.+?)_transparent(?P<suffixe>.*)\.png$", re.IGNORECASE)


def _jetons(suffixe: str) -> frozenset[str]:
	"""Mots d'un suffixe, chiffres de fin retirés (`_arc01` → {arc}, `01` → ∅)."""
	mots = (re.sub(r"\d+$", "", m).lower() for m in suffixe.split("_"))
	return frozenset(m for m in mots if m)


def jetons_armes(armes: list[dict]) -> set[str]:
	"""Mots portés par les armes équipées : mots de l'id, `sous_categorie`, tags."""
	jetons: set[str] = set()
	for arme in armes or []:
		if not arme:
			continue
		slug = str(arme.get("_id") or "").split(":", 1)[-1]
		jetons.update(m.lower() for m in slug.split("_") if m)
		if arme.get("sous_categorie"):
			jetons.add(str(arme["sous_categorie"]).lower())
		jetons.update(str(t).lower() for t in arme.get("tags") or [] if t)
	return jetons


def variantes(image: str, fichiers: list[str]) -> list[tuple[str, frozenset[str]]]:
	"""Fichiers de la même espèce que `image`, avec les mots de leur suffixe. Vide si
	`image` ne suit pas la convention."""
	m = _MOTIF.match(image or "")
	if not m:
		return []
	base = m.group("base").lower()
	res = []
	for f in sorted(fichiers or []):
		mf = _MOTIF.match(f)
		if mf and mf.group("base").lower() == base:
			res.append((f, _jetons(mf.group("suffixe"))))
	return res


def choisir_image(image: str, fichiers: list[str], armes: list[dict],
		choix_fn=random.choice) -> str:
	"""Image retenue pour UN monstre (cf. docstring du module)."""
	vs = variantes(image, fichiers)
	portes = jetons_armes(armes)
	evidentes = [f for f, j in vs if j and j <= portes]
	if evidentes:
		return choix_fn(evidentes)
	generiques = [f for f, j in vs if not j]
	if generiques:
		return choix_fn(generiques)
	return image or ""
