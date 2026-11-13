"""Trophée signé du chasseur (pur) — `docs/conception_trophees_legendaires.md` § 7.

La dépouille d'une bête `rare` ou plus porte sur sa RÉFÉRENCE d'inventaire un bloc
`chasse: {par, espece, quand}` (comme le grade `profil`, #313). Il suit la carcasse découpée
(`carcasse.decouper_ref`), puis la pièce faite de ce trophée (`commande.ref_livree`).
`quand` est un epoch, gardé pour la donnée : l'affichage ne cite jamais de date terrestre
(règle du lore), seulement le chasseur et la bête.
"""

RARETES_SIGNEES = ("rare", "tres_rare", "legendaire")
NOMS_MAX = 3  # au-delà, « … et leurs compagnons » : la ligne reste lisible


def signature(item_doc: dict | None, espece_nom: str, quand: int) -> dict | None:
	"""Bloc `chasse` d'une dépouille, ou None si la bête n'est pas assez rare pour être signée.
	`par` reste vide ici : le chasseur se pose au combat (`signer_par`)."""
	if not item_doc or str(item_doc.get("rarete") or "") not in RARETES_SIGNEES:
		return None
	return {"par": "", "espece": str(espece_nom or item_doc.get("nom") or ""), "quand": int(quand)}


def nom_des_chasseurs(noms) -> str:
	noms = [str(n) for n in noms if n]
	if not noms:
		return ""
	if len(noms) > NOMS_MAX:
		return ", ".join(noms[:NOMS_MAX]) + " et leurs compagnons"
	if len(noms) == 1:
		return noms[0]
	return ", ".join(noms[:-1]) + " et " + noms[-1]


def signer_par(lignes: list, noms) -> list:
	"""Pose `par` sur les lignes de butin signées qui ne l'ont pas encore. Mute et rend `lignes`."""
	par = nom_des_chasseurs(noms)
	for d in lignes or []:
		chasse = d.get("chasse")
		if isinstance(chasse, dict) and not chasse.get("par"):
			chasse["par"] = par
	return lignes


def chasse_de_ref(ref) -> dict | None:
	chasse = ref.get("chasse") if isinstance(ref, dict) else None
	return dict(chasse) if isinstance(chasse, dict) else None


def chasse_des_refs(refs) -> dict | None:
	"""Première signature parmi des références (le trophée fourni à une commande)."""
	for ref in refs or []:
		chasse = chasse_de_ref(ref)
		if chasse:
			return chasse
	return None


def libelle(chasse) -> str:
	"""« Abattu par Aldric — Dragon rouge » ; vide sans signature."""
	if not isinstance(chasse, dict):
		return ""
	par, espece = chasse.get("par") or "", chasse.get("espece") or ""
	if par and espece:
		return f"Abattu par {par} — {espece}"
	return f"Abattu par {par}" if par else espece
