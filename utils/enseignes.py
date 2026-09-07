"""Propositions de NOMS D'ENSEIGNE pour la création d'un lot de lieux (pur).

Ce module ne connaît ni la base ni le web : il croise une tournure de métier avec un
complément de lieu et rend des libellés distincts. Il sert le tableau du lot de
`/admin/editor` (mode Lieux), dont c'était le seul verrou — poser trente boutiques
demande trente noms, et c'est ce qui rendait le geste impraticable à la main.

⚠️ `rand_fn` est INJECTÉ (cf. CLAUDE.md §14) : un test qui tire au hasard n'est pas un
test. Le défaut est `random.shuffle`, un test passe le sien.

⚠️ Le tirage ne garantit **que la distinction**, jamais le goût : un nom proposé est un
point de départ que l'auteur réécrit dans le tableau. C'est pourquoi le catalogue reste
volontairement court — l'enrichir se fait ici, sans toucher à une ligne de code.
"""

import random

# ── Tournures par catégorie ─────────────────────────────────────────────────────
# La clé est la `categorie` du doc lieu — donc aussi le suffixe de `pnj:marchand_*`.
# Les 48 catégories à tenancier générique sont couvertes ; une catégorie absente
# retombe sur `_tournures_repli` (bâti sur le nom de catégorie), jamais sur rien.
TOURNURES = {
	# — Les trente métiers de base —
	"apothicairerie":        ["L'Herbier", "L'Officine", "Le Mortier", "La Simple", "L'Alambic"],
	"armurerie":             ["L'Enclume", "La Forge", "Le Marteau", "L'Écu", "La Trempe"],
	"atelier_d_artisan":     ["L'Établi", "Le Copeau", "La Varlope", "Le Rabot", "La Besogne"],
	"atelier_de_cirier":     ["La Mèche", "Le Cierge", "La Chandelle", "La Cire", "La Veilleuse"],
	"atelier_de_l_empenneur": ["La Plume et l'Encoche", "L'Empennage", "La Penne", "Le Trait Droit"],
	"bijouterie":            ["L'Écrin", "Le Chaton", "La Sertissure", "Le Camée", "L'Orfroi"],
	"boucherie":             ["Le Billot", "Le Couperet", "L'Étal", "La Hampe", "Le Quartier"],
	"boulangerie":           ["Le Fournil", "Le Four Banal", "La Huche", "Le Levain", "La Miche"],
	"bourrellerie":          ["Le Harnais", "La Bricole", "Le Collier", "La Sangle", "L'Attelage"],
	"boyauderie":            ["La Corde de Boyau", "Le Fil Tendu", "La Baudruche", "Le Boyau Filé"],
	"brosserie":             ["La Soie et le Manche", "La Brosse", "Le Crin", "L'Époussette"],
	"corderie":              ["Le Chanvre Tressé", "Le Commettage", "L'Aussière", "Le Toron"],
	"cordonnerie":           ["L'Alêne", "Le Soulier", "La Forme", "L'Empeigne", "Le Bon Pas"],
	"cuisine":              ["Le Fourneau", "La Marmite", "Le Chaudron", "L'Écuelle", "La Braise"],
	"etable":                ["Le Sabot", "Le Pré aux Bêtes", "La Litière", "L'Avoine", "Le Licol"],
	"fletcher":              ["L'Arc et la Corde", "La Flèche", "Le Fût d'If", "La Coche"],
	"fumoir":                ["Le Haloir", "La Fumée Lente", "Le Lard Pendu", "Le Boucanage"],
	"jardinier":             ["Le Carré de Simples", "La Serpe", "Le Plant", "La Treille", "Le Semis"],
	"laboratoire_d_alchimie": ["Le Cabinet des Sels", "L'Athanor", "Le Creuset", "La Cornue"],
	"lutherie":              ["La Table d'Harmonie", "L'Éclisse", "Le Chevalet", "L'Accord Juste"],
	"maroquinerie":          ["Le Cuir Repoussé", "La Gaine", "L'Étui", "La Basane", "Le Maroquin"],
	"necromancie":           ["L'Ossuaire", "Le Suaire", "La Veille des Morts", "Le Cercle Éteint"],
	"plumasserie":           ["La Coiffe", "La Parure", "Le Duvet", "L'Aigrette", "Le Plumail"],
	"salaison":              ["Le Saloir", "La Saumure", "Le Muid Salé", "Le Sel Gris"],
	"savonnerie":            ["La Cendre et l'Huile", "Le Savon Dur", "La Buanderie", "L'Essence"],
	"scriptorium":           ["Le Calame", "La Plume et l'Encre", "Le Pupitre", "Le Vélin"],
	"tabletterie":           ["L'Os Tourné", "Le Buis", "Le Tour", "La Plaquette", "L'Ivoire Feint"],
	"tannerie":              ["Le Tan", "La Fosse", "Le Cuir Vert", "L'Écorce", "Le Corroi"],
	"taxidermie":            ["Le Trophée de Chasse", "L'Œil de Verre", "La Bête Montée", "L'Empaillage"],
	"tissage":               ["La Navette", "Le Métier Haut", "L'Ourdissoir", "La Trame", "Le Lissier"],
	# — Les dix-huit grandes maisons (catégories fusionnées) —
	"cabinet_des_specimens":            ["Le Cabinet des Spécimens", "La Grande Vitrine", "Le Muséum"],
	"grand_arsenal":                    ["Le Grand Arsenal", "La Fonderie Royale", "L'Armurerie Majeure"],
	"grand_atelier_d_empennage":        ["Le Grand Atelier d'Empennage", "La Maison du Trait"],
	"grand_laboratoire_alchimique":     ["Le Grand Athanor", "Le Laboratoire Majeur"],
	"grand_scriptorium":                ["Le Grand Scriptorium", "La Grande Librairie"],
	"grande_apothicairerie":            ["La Grande Officine", "La Maison des Simples"],
	"grande_boulangerie":               ["Le Grand Fournil", "La Halle au Pain"],
	"grande_corderie":                  ["La Grande Corderie", "La Maison du Câble"],
	"grande_maison_des_arts":           ["La Maison des Arts", "Le Grand Atelier"],
	"grande_manufacture_du_cuir":       ["La Grande Mégisserie", "La Manufacture du Cuir"],
	"grande_manufacture_textile":       ["La Manufacture des Toiles", "La Grande Draperie"],
	"grande_orfevrerie":                ["L'Orfèvrerie Royale", "La Grande Orfèvrerie"],
	"grandes_halles_alimentaires":      ["Les Grandes Halles", "La Halle aux Vivres"],
	"institut_de_thanaturgie":          ["L'Institut de Thanaturgie", "Le Grand Ossuaire"],
	"institut_medico_alchimique":       ["L'Institut des Humeurs", "Le Grand Cabinet"],
	"maison_des_conserves":             ["La Maison des Conserves", "Le Grand Saloir"],
	"manufacture_des_instruments":      ["La Manufacture des Instruments", "La Grande Lutherie"],
	"manufacture_des_savons_et_parfums": ["La Maison des Parfums", "La Grande Savonnerie"],
}

# ── Compléments de lieu ─────────────────────────────────────────────────────────
# Ce qui donne à l'enseigne son ancrage : « du Rempart », « de l'Yonne ». Une cité
# absente de la table prend `TOPONYMES_DEFAUT` — donc ouvrir une ville neuve ne
# demande rien, et l'enrichir se fait en ajoutant une entrée ici.
TOPONYMES_PAR_LIEU = {
	"lieu:auxerre": [
		"du Rempart", "de l'Yonne", "de Sainte-Colombe", "du Pont", "de Saint-Germain",
		"du Vieux Quai", "de la Tour de l'Horloge", "des Fossés", "du Faubourg",
	],
	"lieu:lutecia": [
		"de la Seine", "du Parvis", "des Halles", "de la Cité", "du Petit-Pont",
		"des Écoles", "de la Grève", "du Palais", "des Faubourgs", "de la Montagne",
	],
	"lieu:rhemi": [
		"du Sacre", "de la Vesle", "des Coteaux", "de la Porte de Mars", "du Chapitre",
		"des Crayères", "du Vieux Cloître",
	],
}

TOPONYMES_DEFAUT = [
	"du Marché", "de la Grand-Rue", "du Vieux Puits", "de la Place", "du Beffroi",
	"des Trois Chemins", "du Pilori", "de la Halle", "du Guet", "de la Poterne",
]

# Suffixes de désambiguïsation quand tournures × toponymes ne suffisent plus.
# ⚠️ Épuisés à leur tour, on repart sur un compteur décimal (cf. `_suffixes`) : la
# fonction doit TOUJOURS rendre `n` libellés, sans quoi une ligne du tableau naîtrait
# sans nom et l'admin ne saurait pas laquelle.
_ROMAINS = ["II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def toponymes_de(lieu_parent: str) -> list:
	"""Compléments de lieu d'une cité — les siens, sinon les génériques."""
	return list(TOPONYMES_PAR_LIEU.get(lieu_parent or "") or TOPONYMES_DEFAUT)


def _tournures_repli(categorie: str) -> list:
	"""Tournure bâtie sur le nom de catégorie, pour une catégorie hors catalogue.

	`atelier_de_cirier` → « Atelier De Cirier ». Laid, mais nommé : mieux vaut un
	libellé perfectible qu'une ligne vide que l'admin devra remplir à la main."""
	mots = [m for m in str(categorie or "").replace("_", " ").split() if m]
	if not mots:
		return ["L'Échoppe"]
	return [" ".join(m.capitalize() for m in mots)]


def _suffixes():
	"""Suite infinie de désambiguïsateurs : II, III… X, puis 11, 12, 13…

	⚠️ `_ROMAINS` commence à **II** et couvre donc les rangs 2 à 10 : la suite décimale
	reprend à `len + 2`, pas à `len + 1`. Sinon « X » et « 10 » nommeraient deux
	boutiques différentes du même rang."""
	for r in _ROMAINS:
		yield r
	n = len(_ROMAINS) + 2
	while True:
		yield str(n)
		n += 1


def tirer_labels(categorie, n, lieu_parent="", exclus=(), rand_fn=random.shuffle) -> list:
	"""`n` enseignes DISTINCTES pour cette catégorie, aucune dans `exclus`.

	Croise les tournures du métier avec les compléments de la cité, mélange, et
	complète au suffixe numéroté si le produit ne suffit pas. Rend toujours
	exactement `n` libellés (ou `[]` si `n <= 0`).

	⚠️ `exclus` est comparé TEL QUEL, sans normalisation : l'appelant y met les
	labels déjà en base ET ceux déjà posés dans le tableau du lot. C'est le seul
	rempart contre deux `lieu:<slug>` identiques, l'`_id` se déduisant du label.
	⚠️ `rand_fn` reçoit la liste et la mélange EN PLACE (contrat de `random.shuffle`).
	"""
	try:
		combien = int(n)
	except (TypeError, ValueError):
		return []
	if combien <= 0:
		return []

	tournures = list(TOURNURES.get(categorie) or _tournures_repli(categorie))
	toponymes = toponymes_de(lieu_parent)

	# Produit complet, mélangé une fois : le tirage doit être stable pour un même
	# `rand_fn`, donc on ne re-mélange jamais en cours de route.
	candidats = ["%s %s" % (t, top) for t in tournures for top in toponymes]
	rand_fn(candidats)

	pris = set(exclus or ())
	labels = []
	for c in candidats:
		if len(labels) >= combien:
			break
		if c in pris:
			continue
		pris.add(c)
		labels.append(c)

	if len(labels) < combien:
		# Catalogue épuisé : on re-suffixe les candidats dans le même ordre mélangé.
		for suffixe in _suffixes():
			for c in candidats:
				if len(labels) >= combien:
					break
				propose = "%s %s" % (c, suffixe)
				if propose in pris:
					continue
				pris.add(propose)
				labels.append(propose)
			if len(labels) >= combien:
				break
	return labels
