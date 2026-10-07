"""Données des compétences de vocation niveaux 1 → 10 (`dev/gen_competences_1_10.py`).

Un module par vocation, portant `ENTREES` : la liste des compétences NEUVES, écrites avec
les deux constructeurs ci-dessous. Les VALEURS (PM, dés, buffs, durées…) n'y figurent pas :
elles viennent de l'échelle par niveau du générateur, l'archétype disant seulement quelle
forme prend la compétence. Une entrée ne surcharge que ce qui la distingue (caractéristiques
visées, portée, rayon…).
"""


def A(niveau, nom, icon, archetype, theme, description, **options):
	"""Compétence ACTIVE. `theme` = suffixe d'un `animation:capa_<thème>` du dump (son
	compris) ; pour un cône, `"<impact muet>/<nappe>"`."""
	return {"mode": "active", "niveau": niveau, "nom": nom, "icon": icon,
			"archetype": archetype, "theme": theme, "description": description,
			"options": options}


def P(niveau, nom, icon, archetype, description, **options):
	"""Compétence PASSIVE — sans animation : aucune résolution de coup ne la joue."""
	return {"mode": "passive", "niveau": niveau, "nom": nom, "icon": icon,
			"archetype": archetype, "theme": None, "description": description,
			"options": options}
