# utils/vol.py
# VOL MAGIQUE — un effet à durée (`effets.vol`) qui fait léviter son porteur au-dessus du
# terrain qu'il ne peut pas fouler à pied. La règle, et rien d'autre (module PUR, CLAUDE.md §2).
#
#   • Combat      : le porteur franchit les FALAISES (3), comme une espèce taguée `vol`
#                   (`combat._can_fly` lit `vol_magique`, posé par `_refresh_snapshot_stats`).
#                   ⚠️ Contrairement aux ailes d'une espèce, la lévitation ignore le COUVERT :
#                   un mage qui lévite n'a rien à déployer.
#   • Exploration : la règle de case passe de `=== 1` à `>= 1` (eau, falaise, terrain
#                   difficile) — `scripts/deplacement.js` (`accesExploration`). Ni les murs
#                   (0 / -1) ni les murs `nav` ne s'ouvrent : on survole un obstacle naturel,
#                   on ne traverse pas une maison.
#
# FIN DU VOL au-dessus d'une case interdite à pied ⇒ CHUTE : posé sur la case sûre la plus
# proche, et UN DÉ PAR CASE parcourue pour la rejoindre (`notation_chute`) — D20 sur une
# falaise, D6 dans l'eau (on nage jusqu'à la terre ferme). Hors combat la chute ne tue jamais
# (plancher 1 PV, comme le poison) ; en combat elle peut mettre à terre (`combat._atterrir`).
#
# ⚠️ En exploration, seul le PRINCIPAL porte la position : c'est SON vol qui compte, le groupe
# suit (même parti pris que la surcharge, lue sur le principal seul).
#
# Aucune migration (CLAUDE.md §4) : une entrée d'`effets_actifs` sans `vol` reste ce qu'elle
# était, un personnage sans entrée `vol` marche comme avant.

# Seul terrain où l'on tient debout en EXPLORATION (miroir de `deplacement.js caseType1`).
TERRAIN_SOL = 1
# Terrains d'une chute (mêmes valeurs que `utils/grille_image` et `combat.TERRAIN_FALAISE`).
TERRAIN_FALAISE = 3
TERRAIN_EAU = 5

# Dé de chute PAR CASE parcourue jusqu'à la case d'arrivée, selon le terrain survolé (règle
# de l'Auteur) : une falaise fracasse (D20), l'eau épuise le nageur (D6). Tout autre terrain
# interdit à pied (terrain difficile, en exploration) : `CHUTE_FACES_DEFAUT`.
CHUTE_FACES = {TERRAIN_FALAISE: 20, TERRAIN_EAU: 6}
CHUTE_FACES_DEFAUT = 6


def vol_actif(porteur: dict | None) -> bool:
	"""Le porteur (personnage ou snapshot) lévite-t-il ? Une entrée vivante portant `vol`
	dans ses `effets_actifs`."""
	return any((e or {}).get("vol") for e in (porteur or {}).get("effets_actifs") or [])


def case_la_plus_proche(x: int, y: int, largeur: int, hauteur: int, accepte) -> tuple | None:
	"""La case (cx, cy) acceptée par `accepte(cx, cy)` la plus proche de (x, y), hors (x, y)
	elle-même ; None si aucune.

	Anneaux de CHEBYSHEV croissants (la métrique des pas du jeu) ; dans un anneau, la plus
	proche à vol d'oiseau, puis (y, x) — ordre TOTAL, donc déterministe : la même chute
	atterrit toujours au même endroit."""
	for r in range(1, max(largeur, hauteur) + 1):
		anneau = [(cx, cy)
				  for cy in range(y - r, y + r + 1) for cx in range(x - r, x + r + 1)
				  if max(abs(cx - x), abs(cy - y)) == r
				  and 0 <= cx < largeur and 0 <= cy < hauteur]
		anneau.sort(key=lambda c: ((c[0] - x) ** 2 + (c[1] - y) ** 2, c[1], c[0]))
		for cx, cy in anneau:
			if accepte(cx, cy):
				return cx, cy
	return None


def faces_de_chute(terrain) -> int:
	"""Faces du dé de chute au-dessus de `terrain`."""
	return CHUTE_FACES.get(terrain, CHUTE_FACES_DEFAUT)


def notation_chute(terrain, distance: int) -> str:
	"""Notation des dégâts d'une chute : un dé par case parcourue (au moins une) —
	`"3D20"` pour une falaise à trois cases du sol, `"1D6"` au bord de l'eau."""
	return f"{max(1, int(distance or 0))}D{faces_de_chute(terrain)}"


def distance_cases(a: tuple, b: tuple) -> int:
	"""Cases parcourues de `a` à `b` : Chebyshev, la métrique des pas du jeu."""
	return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def sol_exploration(cells: list, x: int, y: int) -> bool:
	"""Peut-on TENIR sur (x, y) à pied, hors combat ? Exactement le terrain 1."""
	if not cells or y < 0 or y >= len(cells):
		return False
	row = cells[y] or []
	return 0 <= x < len(row) and row[x] == TERRAIN_SOL


def chute_exploration(character: dict, lieu_doc: dict | None, des_fn=None) -> dict | None:
	"""Le vol est fini et le personnage plane au-dessus d'une case interdite à pied : il CHUTE
	sur la case de sol la plus proche et perd un dé par case parcourue (`notation_chute` :
	D20 depuis une falaise, D6 depuis l'eau), sans jamais descendre sous 1 PV (hors combat,
	une chute ne tue pas). Mute sans sauver.

	Renvoie `{degats, notation, eau, de, vers}` pour le toast, ou None : toujours en vol, lieu sans grille,
	pied déjà sur le sol, ou aucune case de sol où se poser (on reste alors en place)."""
	cells = (lieu_doc or {}).get("cells")
	pos = (character or {}).get("position") or {}
	if not cells or vol_actif(character) or "x" not in pos or "y" not in pos:
		return None
	x, y = int(pos["x"]), int(pos["y"])
	if sol_exploration(cells, x, y):
		return None
	largeur = max((len(r or []) for r in cells), default=0)
	vers = case_la_plus_proche(x, y, largeur, len(cells), lambda cx, cy: sol_exploration(cells, cx, cy))
	if vers is None:
		return None
	if des_fn is None:
		# Import PARESSEUX : `utils.combat` est lourd, et ce module doit rester pur.
		from utils.combat import roll_dice as des_fn
	row = cells[y] if 0 <= y < len(cells) else []
	terrain = row[x] if 0 <= x < len(row or []) else None
	notation = notation_chute(terrain, distance_cases((x, y), vers))
	degats = max(0, int(des_fn(notation)))
	avant = int(character.get("currentPV", 1) or 0)
	character["currentPV"] = max(min(avant, 1), avant - degats)
	character["position"] = {"x": vers[0], "y": vers[1]}
	return {"degats": avant - character["currentPV"], "notation": notation,
			"eau": terrain == TERRAIN_EAU,
			"de": {"x": x, "y": y}, "vers": {"x": vers[0], "y": vers[1]}}
