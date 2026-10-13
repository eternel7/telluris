"""Calage des cartes de pays voisines (pur) : repères, similitude, projection de case à case.

Toutes les cartes de pays sont orientées nord en haut : d'une carte POSÉE vers une carte de
FOND, la transformation est une SIMILITUDE SANS ROTATION (échelle + translation), ajustée aux
moindres carrés sur des repères lus à la main sur les deux images (px de l'image d'origine).
Une paire par frontière (`PAIRES`) ; la carte posée est la plus DÉTAILLÉE (celle qu'on
rétrécit) — c'est elle qui FAIT FOI sur la frontière (`dev/frontieres_calees.py`).

Partagé par `dev/superposer_cartes.py` (validation visuelle) et les générateurs de frontières.
Toutes les cartes de pays font 1408×768 px pour une grille de 88×48 : une case = `CASE_PX`.
"""

CASE_PX = 16

# Paire → fond, carte posée, repères : nom → (point sur la carte POSÉE, point sur le FOND).
PAIRES = {
	"plaine_france": {
		"fond": "lieu:france", "pose": "lieu:plaine_europeenne",
		"reperes": {
			"embouchure de la Seine": ((148, 597), (560, 160)),
			"Lutecia": ((258, 705), (715, 212)),
			"pas de Calais": ((215, 550), (660, 20)),
			"forêt d'Ardenne": ((500, 620), (950, 190)),
		},
	},
	"france_espagne": {
		"fond": "lieu:espagne", "pose": "lieu:france",
		"reperes": {
			# Le coin basque (la côte cantabrique rejoint l'Atlantique) et la descente des
			# Pyrénées dans la Méditerranée (cap de Creus).
			"coin basque": ((405, 628), (845, 95)),
			"cap de Creus": ((792, 700), (1175, 180)),
		},
	},
	"france_italie": {
		"fond": "lieu:italie", "pose": "lieu:france",
		"reperes": {
			"lac Léman": ((1040, 395), (277, 95)),
			"lac Majeur": ((1215, 415), (432, 180)),
			"lac de Garde": ((1370, 455), (621, 168)),
			"fond du golfe de Gênes": ((1240, 545), (487, 262)),
			"cap Corse": ((1285, 648), (527, 353)),
		},
	},
	"italie_pannonie": {
		"fond": "lieu:italie", "pose": "lieu:pannonie",
		"reperes": {
			"Venise": ((235, 405), (735, 180)),
			"pointe de l'Istrie": ((358, 487), (858, 222)),
			"lac Balaton": ((660, 285), (1062, 112)),
			"bouches de Kotor": ((785, 742), (1082, 393)),
		},
	},
	"pannonie_roumanie": {
		"fond": "lieu:pannonie", "pose": "lieu:roumanie",
		"reperes": {
			# Le Danube à la sortie des Portes de Fer, puis au confluent de l'Olt.
			"Portes de Fer": ((410, 615), (1075, 565)),
			"confluent de l'Olt": ((615, 700), (1190, 575)),
		},
	},
	"egypte_afrique": {
		"fond": "lieu:afrique_du_nord", "pose": "lieu:egypte",
		"reperes": {
			"Le Caire": ((800, 265), (1180, 265)),
			"pyramides": ((575, 285), (1095, 290)),
			"Siwa": ((205, 330), (948, 315)),
			# Haute-Égypte : le Nil, pas un monument — Louxor est dessinée rive EST sur l'Égypte
			# et son temple rive OUEST sur l'Afrique du Nord (5 cases d'écart, rive comprise).
			"Nil à Louxor": ((988, 645), (1225, 429)),
		},
	},
}


def ajuster(reperes):
	"""(s, tx, ty) minimisant Σ |s·p + t − f|² — similitude sans rotation, p sur la carte
	posée, f sur le fond."""
	ps = [p for p, _ in reperes.values()]
	fs = [f for _, f in reperes.values()]
	n = len(ps)
	pcx, pcy = sum(p[0] for p in ps) / n, sum(p[1] for p in ps) / n
	fcx, fcy = sum(f[0] for f in fs) / n, sum(f[1] for f in fs) / n
	num = sum((p[0] - pcx) * (f[0] - fcx) + (p[1] - pcy) * (f[1] - fcy) for p, f in zip(ps, fs))
	den = sum((p[0] - pcx) ** 2 + (p[1] - pcy) ** 2 for p in ps)
	s = num / den
	return s, fcx - s * pcx, fcy - s * pcy


def paire_de(a, b):
	"""Le nom de la paire qui relie les lieux `a` et `b` (dans un sens ou l'autre)."""
	for nom, cfg in PAIRES.items():
		if {cfg["fond"], cfg["pose"]} == {a, b}:
			return nom
	raise KeyError(f"aucune paire calée entre {a} et {b}")


def projection(source, cible):
	"""f((x, y)) → (x, y) : la case de `cible` qui contient le CENTRE de la case (x, y) de
	`source` (peut tomber hors de la grille)."""
	cfg = PAIRES[paire_de(source, cible)]
	s, tx, ty = ajuster(cfg["reperes"])
	if cfg["pose"] != source:          # fond → pose : l'inverse de la similitude
		s, tx, ty = 1 / s, -tx / s, -ty / s

	def f(case):
		x, y = case
		px, py = s * (x + 0.5) * CASE_PX + tx, s * (y + 0.5) * CASE_PX + ty
		return int(px // CASE_PX), int(py // CASE_PX)
	return f
