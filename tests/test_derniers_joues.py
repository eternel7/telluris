"""Page /admin/personnages-recents : horodatage du jeu et liste des derniers personnages."""

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from utils.characters import marquer_joue
from utils.derniers_joues import derniers_joues


LIEUX = {
	"lieu:france": {"_id": "lieu:france", "label": "France"},
	"lieu:auxerre": {"_id": "lieu:auxerre", "label": "Auxerre", "lieu_parent": "lieu:france"},
	"lieu:forge": {"_id": "lieu:forge", "label": "La Forge", "lieu_parent": "lieu:auxerre"},
	"lieu:a": {"_id": "lieu:a", "label": "A", "lieu_parent": "lieu:b"},
	"lieu:b": {"_id": "lieu:b", "label": "B", "lieu_parent": "lieu:a"},
}


def _perso(id_, date=None, **champs):
	doc = {"_id": id_, "prenom": id_, "nom": "X", "lieu": "lieu:auxerre", "position": {"x": 1, "y": 2}}
	if date is not None:
		doc["dernier_jeu"] = date
	doc.update(champs)
	return doc


def _lignes(personnages, combats=(), **kw):
	return derniers_joues(personnages, LIEUX.get, list(combats), **kw)


def test_du_plus_recent_au_plus_ancien():
	lignes = _lignes([_perso("a", 10), _perso("b", 30), _perso("c", 20)])
	assert [l["id"] for l in lignes] == ["b", "c", "a"]


def test_plafond_a_dix_par_defaut():
	lignes = _lignes([_perso(f"p{i}", i) for i in range(15)])
	assert [l["id"] for l in lignes] == [f"p{i}" for i in range(14, 4, -1)]


def test_sans_date_en_bas_par_ordre_alphabetique():
	lignes = _lignes([_perso("zoe"), _perso("Bob"), _perso("alice"), _perso("daté", 1)])
	assert [l["id"] for l in lignes] == ["daté", "alice", "Bob", "zoe"]
	assert lignes[1]["dernier_jeu"] is None


def test_les_dates_passent_avant_les_inconnus_au_plafond():
	lignes = _lignes([_perso("inconnu"), _perso("a", 1), _perso("b", 2)], n=2)
	assert [l["id"] for l in lignes] == ["b", "a"]


def test_emplacement_avec_ses_parents_et_coordonnees():
	ligne = _lignes([_perso("a", lieu="lieu:forge")])[0]
	assert ligne["lieu_label"] == "La Forge"
	assert ligne["parents"] == ["Auxerre", "France"]
	assert (ligne["x"], ligne["y"]) == (1, 2)


def test_lieu_absent_montre_son_id_brut():
	ligne = _lignes([_perso("a", lieu="lieu:disparu")])[0]
	assert ligne["lieu_label"] == "lieu:disparu"
	assert ligne["parents"] == []


def test_cycle_de_parents_ne_boucle_pas():
	ligne = _lignes([_perso("a", lieu="lieu:a")])[0]
	assert ligne["parents"] == ["B"]


def test_badges_combat_et_mer():
	lignes = _lignes(
		[_perso("a", 3), _perso("b", 2, traversee={"route": "traversee:x"}), _perso("c", 1)],
		combats=[{"character_id": "a"}])
	assert [(l["en_combat"], l["en_mer"]) for l in lignes] == [
		(True, False), (False, True), (False, False)]


def test_marquer_joue_pose_la_date():
	perso = {}
	assert marquer_joue(perso, now=100) is True
	assert perso["dernier_jeu"] == 100


def test_marquer_joue_respecte_l_intervalle():
	perso = {"dernier_jeu": 100}
	assert marquer_joue(perso, now=159, intervalle=60) is False
	assert perso["dernier_jeu"] == 100
	assert marquer_joue(perso, now=160, intervalle=60) is True
	assert perso["dernier_jeu"] == 160


def test_marquer_joue_meme_seconde_ne_demande_pas_de_sauvegarde():
	perso = {"dernier_jeu": 100}
	assert marquer_joue(perso, now=100) is False


def _rendu(lignes):
	racine = Path(__file__).resolve().parent.parent / "templates"
	env = Environment(loader=FileSystemLoader(os.fspath(racine)), autoescape=True)
	env.globals.update(script_url=lambda nom: f"/scripts/{nom}", url_for=lambda *a, **k: "/x")
	return env.get_template("admin_personnages_recents.html").render(
		title="Derniers personnages joués", lignes=lignes, request=None)


def test_rendu_echappe_les_noms_et_affiche_l_emplacement():
	html = _rendu(_lignes([
		_perso("a", 1000, prenom="<script>x</script>", lieu="lieu:forge"),
		_perso("b"),
	], combats=[{"character_id": "a"}]))
	assert "<script>x</script>" not in html
	assert "&lt;script&gt;x&lt;/script&gt;" in html
	assert "La Forge" in html and "Auxerre › France" in html and "x 1, y 2" in html
	assert 'data-epoch="1000"' in html
	assert "en combat" in html and "avant le suivi" in html


def test_rendu_sans_personnage():
	assert "Aucun personnage en base." in _rendu([])
