"""`dev/gen_ports_manche.py` — ce que le générateur garantit sans relire d'image.

1. **Ouvrir une porte lève le mur dans LES DEUX sens** (la règle de pas exige la case de
   départ ET la case d'arrivée libres) et fait d'un dedans et d'un dehors une seule zone.
2. **Le quai borde l'eau** : la case choisie touche une case 5.
3. **Les deux routes sont l'aller et le retour** : même chemin inversé, segments côtier /
   haute mer / côtier, arrivée sur les quais d'en face.
4. **Les capitaines passent le linter** et chacun vend la route qui part de SON quai.
"""

from dev import gen_ports_manche as g
from utils import grille_image, lint_dialogues, traversee
from utils.lieux import nav_allows


def test_ouvrir_pas_leve_le_mur_dans_les_deux_sens():
	nav = {"1,1": 0b11111111, "2,1": 0b11111111}
	g.ouvrir_pas(nav, (1, 1), (2, 1))
	assert nav_allows(nav, 1, 1, 1, 0) and nav_allows(nav, 2, 1, -1, 0)
	assert not nav_allows(nav, 1, 1, 0, 1)          # les autres murs restent


def test_ouvrir_porte_relie_dedans_et_dehors():
	# Deux pièces séparées par une colonne murée d'une case (x = 2).
	cells = [[1, 1, 0, 1, 1] for _ in range(3)]
	nav = {}
	dedans = g.zone_proche(cells, nav, (0, 1))
	dehors = g.zone_proche(cells, nav, (4, 1))
	assert not (dedans & dehors)
	ouvertes = g.ouvrir_porte(cells, nav, dedans, dehors, (2, 1))
	assert ouvertes and cells[1][2] == 1
	assert (4, 1) in g.zone_proche(cells, nav, (0, 1))


def test_le_quai_borde_l_eau():
	cells = [[1, 1, 1, 5], [1, 1, 1, 5], [1, 1, 1, 5]]
	zone = g.zone_proche(cells, {}, (0, 0))
	x, y = g.case_de_quai(cells, zone, (0, 1))
	assert x == 2                                   # la colonne voisine de l'eau


def test_aller_et_retour():
	aller = g.doc_route("lieu:calais", "lieu:douvres", g.CHEMIN_CALAIS_DOUVRES)
	retour = g.doc_route("lieu:douvres", "lieu:calais",
						 list(reversed(traversee.cases_du_chemin(g.CHEMIN_CALAIS_DOUVRES))))
	assert traversee.cases_du_chemin(retour["chemin"]) == \
		list(reversed(traversee.cases_du_chemin(aller["chemin"])))
	for route, depart, arrivee in ((aller, "lieu:calais_quais", "lieu:douvres_quais"),
								   (retour, "lieu:douvres_quais", "lieu:calais_quais")):
		assert route["depart"]["lieu"] == depart and route["arrivee"]["lieu"] == arrivee
		zones = [traversee.segment_a(route, e)["zone"] for e in range(traversee.total_etapes(route))]
		assert zones[0] == zones[-1] == "zone:mer_cotiere" and "zone:haute_mer" in zones


def test_les_capitaines_passent_le_linter():
	routes = {"lieu:calais": "traversee:calais_douvres", "lieu:douvres": "traversee:douvres_calais"}
	docs = [g.doc_capitaine(cite, route, "ailleurs") for cite, route in routes.items()]
	rapport = lint_dialogues.analyser(docs)
	assert rapport["analyses"] == 2 and rapport["erreurs"] == 0, rapport["trouvailles"]
	for doc, (cite, route) in zip(docs, routes.items()):
		assert doc["services"]["traversee"]["route"] == route
		assert doc["_id"] == g.QUAIS[cite]["capitaine"]


def test_zones_de_la_grille_utilisees_par_le_generateur():
	# `zone_proche` s'appuie sur la règle de marche de `grille_image.zones` : une case murée
	# (0) n'appartient à aucune zone.
	cells = [[0, 1]]
	assert g.zone_proche(cells, {}, (0, 0)) == {(1, 0)}
	assert grille_image.zones(cells, {})[0][0][0] == -1
