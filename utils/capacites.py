"""CAPACITÉS d'un lieu — ce que le lieu SAIT FAIRE (pur).

Dans ce jeu, « le type d'un lieu » n'est pas un champ : c'est un jeu de capacités résolues
À LA LECTURE par cinq prédicats du même idiome, tous de la forme
« `categorie == X` **OU** tag `Y` » (le OU évite toute migration et permet d'ouvrir une
capacité à n'importe quel lieu par la donnée seule). Ils vivent dans cinq modules qui se
citent mutuellement dans leurs docstrings :

    auberge.lieu_est_taverne          categorie "auberge"      OU tag "taverne"
    montures.lieu_vend_montures       categorie "etable"       OU tag "montures"
    scriptorium.lieu_est_scriptorium  categorie "scriptorium"  OU tag "scriptorium"
    recrutement.lieu_recrute          categorie "guilde_aventurier" OU tag "recrutement"
    recrutement.lieu_de_guilde        sous_categorie "guilde_aventurier" OU tag "guilde"
    commande.lieu_fabrique_sur_mesure categories de LIEU_CATEGORIES_FUSION OU tag "sur_mesure"

⚠️ « Prendre une commande » (`commande.lieu_prend_commandes`) n'est PAS dans cette table et ne
peut pas y entrer : ce n'est ni une catégorie ni un tag, c'est une CONSÉQUENCE — tout atelier
qui a des recettes sait refaire ce qu'il fabrique. Seule la fabrication SUR MESURE (inventer une
variante, donc créer des docs en base) s'accorde, et la `note` de la case le dit au lecteur.

Ce module existe pour que l'ÉDITEUR DE CARTE puisse les montrer et les poser : sans lui,
créer une auberge demandait de savoir par cœur que la catégorie `auberge` ouvre la salle
commune, et rien à l'écran ne le disait.

⚠️ C'est une RECOPIE ASSUMÉE des cinq prédicats, PAS leur source. La vérité reste dans les
cinq modules. Importer ceux-ci ici tirerait `marche`, `expedition` et `quetes` derrière eux
pour un simple catalogue servi par un GET d'administration. La recopie est verrouillée par
`tests/test_capacites.py`, qui compare `capacites_de` aux VRAIS prédicats sur une matrice de
cas : la table ne peut pas dériver en silence.

⚠️ Une capacité accordée par la CATÉGORIE ne peut pas être retirée — il n'existe aucun
anti-tag. C'est ce que `accordee_par_categorie` sert à dire au client, qui grise la case.
"""

from models import character_stats

# ── Le catalogue ────────────────────────────────────────────────────────────────
# Sérialisé tel quel dans `GET /api/lieux/creation_options` : le client doit pouvoir
# pré-cocher, griser et expliquer chaque case sans réimplémenter la règle.
#
# `tag`             : le tag qui accorde la capacité à un lieu de n'importe quelle catégorie.
# `categories`      : les `categorie` qui l'accordent d'office.
# `sous_categories` : idem pour `sous_categorie` (la guilde est la seule dans ce cas).
# `note`            : ce que la capacité change EN JEU, affiché sous la case.
# `categories_var`  : nom d'une variable de monde qui FOURNIT `categories` (au lieu de la
#                     lister en dur). Résolu par `categories_de`, sérialisé résolu par
#                     `catalogue()` — le client continue de ne lire que `categories`.
CAPACITES = [
	{
		"id": "taverne", "label": "Taverne", "tag": "taverne",
		"categories": ["auberge"], "sous_categories": [],
		"note": "Salle commune (tables, tableau d'information) et « Passer la nuit ».",
	},
	{
		"id": "montures", "label": "Étable", "tag": "montures",
		"categories": ["etable"], "sous_categories": [],
		"note": "Vend des montures — l'écurie est la liste `montures` du TENANCIER.",
	},
	{
		"id": "scriptorium", "label": "Scriptorium", "tag": "scriptorium",
		"categories": ["scriptorium"], "sous_categories": [],
		"note": "Permet d'écrire un livre (papier + encre + plume).",
	},
	{
		"id": "recrutement", "label": "Recrutement", "tag": "recrutement",
		"categories": ["guilde_aventurier"], "sous_categories": [],
		"note": "Affiche un tableau de recrues.",
	},
	{
		# ⚠️ La maison de guilde est ÉCLATÉE en quatre lieux aux `categorie` différentes
		# (réception, comptoir, façade, bureau du maître) : le prédicat les couvre TOUTES,
		# en plus de la sous-catégorie. Recopie de `recrutement.GUILDE_CATEGORIES`.
		"id": "guilde", "label": "Maison de guilde", "tag": "guilde",
		"categories": ["guilde_aventurier", "guilde_aventurier_comptoir",
					   "guilde_aventurier_exterieur", "bureau_maitre_guilde"],
		"sous_categories": ["guilde_aventurier"],
		"note": "Un contrat de mission s'y signe, s'y rompt sans frais et s'y achève.",
	},
	{
		# ⚠️ Les catégories accordantes sont les 18 grandes maisons de LIEU_CATEGORIES_FUSION,
		# RELUES et non recopiées : ouvrir une grande maison de plus ne doit pas obliger à
		# penser à deux endroits (même dérivation que `CHA_MARCHAND_PAR_CATEGORIE`).
		"id": "sur_mesure", "label": "Fabrication sur mesure", "tag": "sur_mesure",
		"categories": [], "categories_var": "LIEU_CATEGORIES_FUSION", "sous_categories": [],
		"note": "Assemble une VARIANTE inédite à partir de matières (crée un objet et sa "
				"recette en base). Prendre une commande de son catalogue ne demande rien : "
				"tout atelier qui a des recettes le fait déjà.",
	},
]

PAR_ID = {c["id"]: c for c in CAPACITES}

# Les tags que le formulaire s'autorise à poser et à retirer. ⚠️ Tout AUTRE tag d'un doc
# (pondération de carte de combat, marquage d'auteur…) doit survivre à une édition.
TAGS_CAPACITE = {c["tag"] for c in CAPACITES}


def categories_de(cap: dict) -> list:
	"""Catégories qui accordent cette capacité, `categories_var` résolue.

	⚠️ Lue à CHAQUE appel, jamais figée à l'import : les variables de monde se rechargent à
	chaud depuis `/admin`, et une table figée ferait diverger l'éditeur du jeu sans un mot."""
	if not cap:
		return []
	nom_var = cap.get("categories_var")
	if nom_var:
		table = getattr(character_stats, nom_var, None) or {}
		return sorted(table)
	return list(cap.get("categories") or [])


def catalogue() -> list:
	"""Le catalogue sérialisable : comme `CAPACITES`, mais `categories` RÉSOLUE.

	C'est ce que sert `/api/lieux/creation_options` — le client (`part-lieux-js.html`) ne lit
	que `categories` et n'a pas à connaître `categories_var`."""
	return [dict(cap, categories=categories_de(cap)) for cap in CAPACITES]


def accordee_par_categorie(cap: dict, categorie, sous_categorie="") -> bool:
	"""Cette capacité est-elle acquise par la seule CATÉGORIE (ou sous-catégorie) ?

	C'est ce qui rend la case à cocher inopérante côté client : aucun anti-tag n'existe,
	donc décocher ne pourrait rien retirer. Mieux vaut une case grisée qu'un geste sans effet."""
	if not cap:
		return False
	return (str(categorie or "") in categories_de(cap)
			or str(sous_categorie or "") in (cap.get("sous_categories") or []))


def capacites_de(lieu_doc: dict) -> dict:
	"""`{id: bool}` pour les cinq capacités — recopie des cinq prédicats du jeu."""
	doc = lieu_doc or {}
	categorie = doc.get("categorie")
	sous_categorie = doc.get("sous_categorie")
	tags = doc.get("tags") or []
	return {
		cap["id"]: (accordee_par_categorie(cap, categorie, sous_categorie)
					or cap["tag"] in tags)
		for cap in CAPACITES
	}


def tags_apres(tags, voulues: dict, categorie, sous_categorie="") -> list:
	"""Les `tags` d'un lieu après application des cases cochées.

	⚠️ Ne touche QUE les cinq tags de capacité : tout autre tag est préservé, dans son
	ordre. ⚠️ Un tag dont la capacité est déjà accordée par la catégorie n'est pas posé —
	il serait redondant, et le doc de référence (`lieu:auberge_de_la_tour_de_l_horloge`)
	n'en porte aucun."""
	sortie = [t for t in (tags or []) if t not in TAGS_CAPACITE]
	for cap in CAPACITES:
		if not (voulues or {}).get(cap["id"]):
			continue
		if accordee_par_categorie(cap, categorie, sous_categorie):
			continue
		sortie.append(cap["tag"])
	return sortie
