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


def L(niveau, nom, icon, theme, description, champs, remplace=None, zone_persistante=False):
	"""Compétence ACTIVE « libre » : ses champs de jeu (`cible`, `jet`, `portee`, `cout_pm`,
	`maintien`, `incantation`, `zone`, `effets`) sont ÉCRITS tels quels, formules à
	caractéristiques comprises — pour les formes que l'échelle ne sait pas dire (lien de vie,
	partage de soin, drain de PM, saut d'un allié, coût décroissant…). Moteur actuel seulement.

	`remplace` = slug (suffixe d'`_id`) d'une entrée EXISTANTE dont celle-ci prend la place :
	même `_id`, donc les personnages qui la connaissaient reçoivent la nouvelle, et le doc
	est RÉÉMIS tant qu'il diffère de la base. `zone_persistante=True` déclare VOULU le mur
	d'une active `ennemi` à `zone` + `maintien` (garde (12) de check_competences_doc)."""
	options = {"champs": champs, "zone_persistante": zone_persistante}
	if remplace:
		options.update(id=remplace, remplace=True)
	return {"mode": "active", "niveau": niveau, "nom": nom, "icon": icon,
			"archetype": "libre", "theme": theme, "description": description,
			"options": options}
