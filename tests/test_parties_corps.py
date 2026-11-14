"""Parties du corps des plus grands jetons (utils/parties_corps.py) et leur branchement dans le
combat (utils/combat.py) : partie frappée selon le côté, barème des PA, ailes brisées, zone
partie de la tête, coup de queue dans le dos.

Tests purs : docs à la main, aucune DB ; jets et dés neutralisés par monkeypatch. Fixtures de
tests/test_combat_jetons.py.
"""
from tests.test_combat_jetons import _combat, _espece, _joueur, _monstre
from utils import combat as combat_mod
from utils import parties_corps as pc
from utils.zones_effet import normaliser_zone

TETE, QUEUE, AILES, FLANCS = pc.TETE, pc.QUEUE, pc.AILES, pc.FLANCS


def _acteur(x, y, taille, cap="bas", vol=False):
	largeur, profondeur = (int(v) for v in taille.split("x"))
	a = {"pos": {"x": x, "y": y}, "cap": cap,
		 "jeton": {"largeur": largeur, "profondeur": profondeur, "forme": "croix"}}
	if vol:
		a["vol_espece"] = True
	return a


def _un(x, y):
	return {"pos": {"x": x, "y": y}}


# ── Découpage ────────────────────────────────────────────────────────────────────

def test_seuls_les_gabarits_geants_ont_des_parties():
	assert pc.a_des_parties(_acteur(0, 0, "4x3"))
	assert pc.a_des_parties(_acteur(0, 0, "5x4"))
	assert pc.a_des_parties(_acteur(0, 0, "2x5"))
	assert not pc.a_des_parties(_acteur(0, 0, "3x2", vol=True))
	assert not pc.a_des_parties(_un(0, 0))
	assert pc.parties(_acteur(0, 0, "3x2")) == {}


def test_dragon_4x3_volant_cap_bas():
	"""x 0..3 × y 0..2, tête en bas : colonnes 0 et 3 = ailes, rangée y=2 = tête."""
	p = pc.parties(_acteur(0, 0, "4x3", "bas", vol=True))
	assert p[AILES] == [(0, 0), (3, 0), (0, 1), (3, 1), (0, 2), (3, 2)]
	assert p[TETE] == [(1, 2), (2, 2)]
	assert p[QUEUE] == [(1, 0), (2, 0)]
	assert p[FLANCS] == [(1, 1), (2, 1)]


def test_sans_vol_pas_dailes():
	p = pc.parties(_acteur(0, 0, "4x3", "haut"))
	assert AILES not in p
	assert p[TETE] == [(0, 0), (1, 0), (2, 0), (3, 0)]
	assert p[QUEUE] == [(0, 2), (1, 2), (2, 2), (3, 2)]


def test_trop_etroit_pour_des_ailes():
	assert AILES not in pc.parties(_acteur(0, 0, "2x5", "bas", vol=True))


def test_ver_2x5_cap_droite():
	"""Couché vers la droite : x 0..4 × y 0..1, tête = colonne x=4, queue = x=0."""
	p = pc.parties(_acteur(0, 0, "2x5", "droite"))
	assert p[TETE] == [(4, 0), (4, 1)]
	assert p[QUEUE] == [(0, 0), (0, 1)]
	assert len(p[FLANCS]) == 6


def test_cap_gauche_ailes_en_haut_et_en_bas():
	p = pc.parties(_acteur(0, 0, "4x3", "gauche", vol=True))   # x 0..2 × y 0..3
	assert p[TETE] == [(0, 1), (0, 2)]
	assert p[QUEUE] == [(2, 1), (2, 2)]
	assert all(y in (0, 3) for (_, y) in p[AILES])


# ── Partie frappée, tête, queue ──────────────────────────────────────────────────

def test_partie_visee_selon_le_cote():
	dragon = _acteur(2, 2, "4x3", "bas", vol=True)   # x 2..5 × y 2..4
	assert pc.partie_visee(dragon, _un(3, 5)) == TETE
	assert pc.partie_visee(dragon, _un(4, 1)) == QUEUE
	assert pc.partie_visee(dragon, _un(1, 3)) == AILES
	assert pc.partie_visee(dragon, _un(3, 9)) == TETE, "à distance aussi"
	assert pc.partie_visee(_acteur(2, 2, "4x3", "bas"), _un(1, 3)) == FLANCS
	assert pc.partie_visee(_acteur(2, 2, "3x2"), _un(3, 5)) is None


def test_ancre_tete_et_queue_au_contact():
	dragon = _acteur(2, 2, "4x3", "bas", vol=True)
	assert pc.ancre_tete(dragon, _un(9, 9)) == (4, 4)
	assert pc.ancre_tete(dragon, _un(0, 9)) == (3, 4)
	assert pc.queue_au_contact(dragon, _un(3, 1))
	assert pc.queue_au_contact(dragon, _un(2, 1)), "diagonale de la queue (3,2)"
	assert not pc.queue_au_contact(dragon, _un(1, 1)), "derrière une aile, pas la queue"
	assert not pc.queue_au_contact(dragon, _un(3, 5))


def test_ailes_brisees_au_seuil():
	dragon = dict(_acteur(0, 0, "4x3", vol=True), pv_max=100)
	seuil = int(pc.SEUIL_AILES * 100)
	assert pc.blesser_ailes(dragon, seuil - 1) is False
	assert pc.blesser_ailes(dragon, 1) is True
	assert dragon["ailes_brisees"] is True
	assert pc.blesser_ailes(dragon, 50) is False, "déjà brisées : une seule fois"
	assert pc.blesser_ailes(dict(_acteur(0, 0, "4x3"), pv_max=10), 99) is False


# ── Combat ───────────────────────────────────────────────────────────────────────

DRAGON_GEANT = dict(_espece("espece:dragon_rouge", "Dragon rouge",
							{"taille": "4x3", "forme": "croix"}), tags=["vol"])


def _toujours_touche(monkeypatch, des=20):
	monkeypatch.setattr(combat_mod, "_resoudre_jet", lambda a, d, s, furtif=False: {
		"roll": 10, "seuil": s, "touche": True, "critique": False, "fumble": False,
		"mult_degats": 1, "furtif": False})
	monkeypatch.setattr(combat_mod, "roll_dice", lambda notation: des)


def test_pa_de_zone_module_par_la_partie():
	m = {"pa": 10}
	assert combat_mod.pa_de_zone(m, TETE) == round(10 * pc.MULT_PA[TETE])
	assert combat_mod.pa_de_zone(m, FLANCS) == round(10 * pc.MULT_PA[FLANCS])
	assert combat_mod.pa_de_zone(m, AILES) == round(10 * pc.MULT_PA[AILES])
	assert combat_mod.pa_de_zone(m) == 10


def test_frappe_de_face_touche_la_tete(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 5})
	dragon = _monstre(monkeypatch, 2, 2, espece=DRAGON_GEANT, cap="bas")
	dragon.update(pa=10, currentPV=500, pv_max=500)
	combat = _combat([joueur], [dragon])
	_toujours_touche(monkeypatch, des=40)

	res = combat_mod.resolve_action(combat, "attaquer", cible_id=dragon["id"], mode="cac")
	assert "error" not in res
	assert any("à la tête" in e.get("texte", "") for e in combat["log"])
	assert dragon["currentPV"] == 500 - (40 - combat_mod.pa_de_zone(dragon, TETE))


def test_ailes_brisees_en_combat(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 1, "y": 3})
	dragon = _monstre(monkeypatch, 2, 2, espece=DRAGON_GEANT, cap="bas")
	combat_mod._appliquer_couvert(dragon, False)   # posé à l'entrée du combat (lieu découvert)
	assert combat_mod._can_fly(dragon)
	dragon.update(pa=0, currentPV=100, pv_max=100)
	combat = _combat([joueur], [dragon])
	_toujours_touche(monkeypatch, des=int(pc.SEUIL_AILES * 100))

	combat_mod.resolve_action(combat, "attaquer", cible_id=dragon["id"], mode="cac")
	assert any("à l'aile" in e.get("texte", "") for e in combat["log"])
	assert dragon["ailes_brisees"] is True
	assert combat_mod._can_fly(dragon) is False
	assert any("ailes" in e.get("texte", "") and "brisées" in e.get("texte", "")
			   for e in combat["log"])


def test_la_zone_part_de_la_tete(monkeypatch):
	joueur = _joueur(monkeypatch, 0, pos={"x": 7, "y": 7})
	dragon = _monstre(monkeypatch, 2, 2, espece=DRAGON_GEANT, cap="bas")   # tête (3,4),(4,4)
	combat = _combat([joueur], [dragon])
	zone = normaliser_zone({"forme": "carre", "rayon": 0, "origine": "lanceur"})
	cases = combat_mod._cases_zone_offensive(dragon, joueur, zone, combat_mod.get_combat_grid(combat))
	assert cases == {(4, 4)}


def test_coup_de_queue_sans_pivot(monkeypatch):
	"""Joueur derrière la queue (y=1, dragon tête en bas) : frappé sans que le dragon tourne,
	à COUP_DE_QUEUE_FACTEUR des dégâts."""
	joueur = _joueur(monkeypatch, 0, pos={"x": 3, "y": 1}, currentPV=500, pv_max=500)
	joueur["pa"] = 0
	dragon = _monstre(monkeypatch, 2, 2, espece=DRAGON_GEANT, cap="bas")
	dragon["deplacement"] = 0
	combat = _combat([joueur], [dragon], w=10, h=10)
	combat["acteur_courant_index"] = 1
	_toujours_touche(monkeypatch, des=40)

	combat_mod._run_monster_turn(combat, dragon, combat_mod.get_combat_grid(combat))
	assert dragon["cap"] == "bas"
	queue = [e for e in combat["log"] if "coup de queue" in e.get("texte", "")]
	assert queue
	assert joueur["currentPV"] == 500 - len(queue) * int(40 * pc.COUP_DE_QUEUE_FACTEUR)
