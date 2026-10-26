# tests/test_lumiere_paladine_contenu.py
#
# Contenu de dev/gen_lumiere_paladine.py → jsons/lumiere_paladine_a_importer.json : Rayon et
# Lance de lumière (défense anti-aérienne), leurs quatre maîtres et leurs épreuves.

import json
import os
import sys

import pytest

import re

from utils import lint_dialogues, sorts as sorts_util
from utils.simulateur import moyenne_de_des

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENU = os.path.join(RACINE, "jsons", "lumiere_paladine_a_importer.json")
# Dump FIXE, antérieur à l'import : sur un dump qui contient déjà ces docs, le générateur
# (idempotent) ne rendrait plus rien.
DUMP = os.path.join(RACINE, "jsons", "telluris-dump-20261026-123727.json")

sys.path.insert(0, os.path.join(RACINE, "dev"))
import gen_lumiere_paladine as gen  # noqa: E402


def _minimum(notation: str) -> int:
	"""Jet minimal d'une notation `a+nDm` : chaque dé vaut 1."""
	sans_des = re.sub(r"\d*D\d+", "", notation.upper())
	des = sum(int(n or "1") for n in re.findall(r"(\d*)D\d+", notation.upper()))
	return des + sum(int(x) for x in re.findall(r"\d+", sans_des))


def _contenu():
	with open(CONTENU, encoding="utf-8") as f:
		return json.load(f)


def _doc(doc_id):
	return next(d for d in _contenu() if d["_id"] == doc_id)


def test_le_json_est_la_sortie_du_generateur(tmp_path):
	sortie = tmp_path / "lumiere.json"
	assert gen.main(["--dump", DUMP, "--sortie", str(sortie)]) == 0
	assert json.loads(sortie.read_text(encoding="utf-8")) == _contenu()


def test_aucun_id_en_double():
	ids = [d["_id"] for d in _contenu()]
	assert len(ids) == len(set(ids))


def test_les_dialogues_des_maitres_sont_propres():
	rapport = lint_dialogues.analyser(_contenu())
	assert rapport["analyses"] >= len(gen.MAITRES)
	assert rapport["erreurs"] == 0 and rapport["avertissements"] == 0, rapport["trouvailles"]


@pytest.mark.parametrize("sort_id", [gen.RAYON_ID, gen.LANCE_ID])
def test_paire_de_composants_catalyseur_plus_faible(sort_id):
	doc = _doc(sort_id)
	catalyseurs = [c for c in doc["composants"] if not c["consomme"]]
	consommes = [c for c in doc["composants"] if c["consomme"]]
	assert len(catalyseurs) == 1 and len(consommes) == 1
	assert doc["composants"].index(catalyseurs[0]) < doc["composants"].index(consommes[0])
	assert (moyenne_de_des(catalyseurs[0]["bonus"]["degats"])
			< moyenne_de_des(consommes[0]["bonus"]["degats"]))


def test_la_lance_est_enseignee_et_ameliore_le_rayon():
	rayon = sorts_util.normaliser_sort(_doc(gen.RAYON_ID))
	lance = sorts_util.normaliser_sort(_doc(gen.LANCE_ID))
	assert not rayon["enseignement"] and lance["enseignement"]
	assert lance["ameliore"] == gen.RAYON_ID
	# Seul le Rayon a un grimoire.
	grimoires = [d for d in _contenu() if d.get("sous_categorie") == "grimoire"]
	assert [g["sorts"] for g in grimoires] == [[gen.RAYON_ID]]
	# Même ligne : perce et tir ami, longueur = portée.
	for s in (rayon, lance):
		assert s["zone"]["perce"] and s["zone"]["tir_ami"]
		assert s["zone"]["longueur"] == s["portee"]


def test_dix_lances_abattent_un_dragon_empereur():
	"""Calibrage voulu (« un Empereur n'est pas tué en un coup, dix peuvent suffire ») : dix
	lances MOYENNES tuent l'Empereur le plus fort ; dix lances au jet MINIMAL, l'Empereur médian.
	PV = R×3 + F (compute_derived_stats), sorts sans armure."""
	base = {d["_id"]: d for d in json.load(open(DUMP, encoding="utf-8"))["docs"]}
	a = base["espece:dragon_empereur"]["base_attributes"]
	pv_max = a["R"]["max"] * 3 + a["F"]["max"]
	pv_median = (a["R"]["min"] + a["R"]["max"]) // 2 * 3 + (a["F"]["min"] + a["F"]["max"]) // 2
	degats = _doc(gen.LANCE_ID)["effets"]["degats"]
	assert 10 * moyenne_de_des(degats) >= pv_max
	assert 10 * _minimum(degats) >= pv_median
	assert 100 < pv_max                                   # une lance maximale (100) ne suffit jamais


def test_chaque_maitre_tient_une_epreuve_et_enseigne_la_lance():
	maitres = [d for d in _contenu() if d["type"] == "pnj"]
	assert len(maitres) == len(gen.MAITRES)
	for m in maitres:
		assert m["services"]["enseignement"]["sort"] == gen.LANCE_ID
		offre = m["services"]["apport"]["offre"]
		# L'apprentissage n'est proposé qu'après l'épreuve réussie.
		choix = m["dialogue"]["noeuds"]["accueil"]["choix"]
		apprendre = next(c for c in choix if (c.get("action") or {}).get("service") == "enseignement")
		assert apprendre["condition"]["quete_reussie"]["id"] == offre["id"]
		assert apprendre["condition"]["enseignement_possible"] is True


def test_chaque_maitre_est_present_dans_son_lieu():
	lieux = {d["_id"]: d for d in _contenu() if d["type"] == "lieu"}
	for m in gen.MAITRES:
		assert any(p.get("character") == "pnj:" + m["slug"] for p in lieux[m["lieu"]]["pnj"])
