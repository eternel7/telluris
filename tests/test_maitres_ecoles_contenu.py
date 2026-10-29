# tests/test_maitres_ecoles_contenu.py
#
# Contenu de dev/gen_maitres_ecoles.py → jsons/maitres_ecoles_a_importer.json : les formes
# ENSEIGNÉES des sept écoles (contrat de la Lance de lumière), leurs maîtres et leurs épreuves,
# les formes simples de niveau 10 créées pour l'occasion et leurs grimoires.

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

from utils import lint_dialogues, sorts as sorts_util
from utils.simulateur import moyenne_de_des

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENU = os.path.join(RACINE, "jsons", "maitres_ecoles_a_importer.json")
# Dump FIXE, antérieur à l'import : sur un dump qui contient déjà ces docs, le générateur
# (idempotent) ne rendrait plus rien.
DUMP = os.path.join(RACINE, "jsons", "telluris-dump-20261026-175531.json")

sys.path.insert(0, os.path.join(RACINE, "dev"))
import gen_maitres_ecoles as gen  # noqa: E402


def _contenu():
	with open(CONTENU, encoding="utf-8") as f:
		return json.load(f)


def _base():
	with open(DUMP, encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}


def _sorts():
	return {d["_id"]: d for d in _contenu() if d["type"] == "sort"}


ENSEIGNES = [d["_id"] for d in gen.SORTS_ENSEIGNES]


def test_le_json_est_la_sortie_du_generateur(tmp_path):
	sortie = tmp_path / "maitres.json"
	assert gen.main(["--dump", DUMP, "--sortie", str(sortie)]) == 0
	assert json.loads(sortie.read_text(encoding="utf-8")) == _contenu()


def test_aucun_id_en_double_ni_pris_en_base():
	ids = [d["_id"] for d in _contenu()]
	assert len(ids) == len(set(ids))
	base = _base()
	neufs = [i for i in ids if not i.startswith("lieu:")]
	assert not [i for i in neufs if i in base]


def test_les_dialogues_des_maitres_sont_propres():
	rapport = lint_dialogues.analyser(_contenu())
	assert rapport["analyses"] >= len(gen.MAITRES)
	assert rapport["erreurs"] == 0 and rapport["avertissements"] == 0, rapport["trouvailles"]


@pytest.mark.parametrize("sort_id", ENSEIGNES)
def test_forme_enseignee_de_meme_ecole_et_niveau_que_sa_forme_simple(sort_id):
	sorts = {**{i: d for i, d in _base().items() if i.startswith("sort:")}, **_sorts()}
	forme = sorts_util.normaliser_sort(sorts[sort_id])
	simple = sorts_util.normaliser_sort(sorts[forme["ameliore"]])
	assert forme["enseignement"] and not simple["enseignement"]
	assert forme["magie"] == simple["magie"] and forme["niveau"] == simple["niveau"]
	assert bool(forme.get("invocation")) == bool(simple.get("invocation"))


def test_un_couple_de_niveau_10_par_ecole():
	"""La Sainte a déjà le sien en base (Rayon → Lance) ; les six autres viennent d'ici."""
	ecoles = {d.get("magie") for d in _base().values() if d.get("type") == "sort"} - {None}
	sorts = {**{i: d for i, d in _base().items() if i.startswith("sort:")}, **_sorts()}
	couverts = {d["magie"] for d in sorts.values()
				if d.get("enseignement") and d.get("niveau") == 10
				and sorts[d["ameliore"]].get("niveau") == 10}
	assert couverts == ecoles


@pytest.mark.parametrize("sort_id", [d["_id"] for d in gen.BASES + gen.SORTS_ENSEIGNES])
def test_paire_de_composants_catalyseur_plus_faible(sort_id):
	doc = _sorts()[sort_id]
	catalyseurs = [c for c in doc["composants"] if not c["consomme"]]
	consommes = [c for c in doc["composants"] if c["consomme"]]
	assert len(catalyseurs) == 1 and len(consommes) == 1
	cat, cons = catalyseurs[0]["bonus"], consommes[0]["bonus"]
	for cle in set(cat) & set(cons):
		if cle in ("degats", "soin"):
			assert moyenne_de_des(cat[cle]) < moyenne_de_des(cons[cle])
		elif cle != "buffs":
			assert cat[cle] < cons[cle]


def test_seules_les_formes_simples_creees_ont_un_grimoire():
	grimoires = [d for d in _contenu() if d.get("sous_categorie") == "grimoire"]
	assert sorted(s for g in grimoires for s in g["sorts"]) == sorted(d["_id"] for d in gen.BASES)
	assert all(len(g["sorts"]) == 1 for g in grimoires)


def test_trois_formes_abattent_les_volants():
	abattent = {i for i, d in _sorts().items() if (d.get("effets") or {}).get("abattre")}
	assert abattent == {"sort:harpon_arcanique", "sort:cisaille_des_vents",
						"sort:liane_d_abattage"}
	for i in abattent:
		assert sorts_util.part_durative(sorts_util.normaliser_sort(_sorts()[i])["effets"])


def test_un_maitre_par_forme_enseignee_avec_son_epreuve():
	maitres = [d for d in _contenu() if d["type"] == "pnj"]
	assert sorted(m["services"]["enseignement"]["sort"] for m in maitres) == sorted(ENSEIGNES)
	base = _base()
	for m in maitres:
		offre = m["services"]["apport"]["offre"]
		assert offre["item"] in base and offre["unique"] is True
		# L'apprentissage n'est proposé qu'après l'épreuve réussie.
		choix = m["dialogue"]["noeuds"]["accueil"]["choix"]
		apprendre = next(c for c in choix if (c.get("action") or {}).get("service") == "enseignement")
		assert apprendre["condition"]["quete_reussie"]["id"] == offre["id"]
		assert apprendre["condition"]["enseignement_possible"] is True
	assert len({m["services"]["apport"]["offre"]["id"] for m in maitres}) == len(maitres)


def test_le_maitre_rappelle_ce_qui_manque_a_l_epreuve():
	"""Épreuve en cours sans rien à remettre : un choix mène au reste à apporter — exclusif de
	la remise (`apport_possible`), qui a déjà son nœud `partiel`."""
	for m in (d for d in _contenu() if d["type"] == "pnj"):
		choix = m["dialogue"]["noeuds"]["accueil"]["choix"]
		rappel = next(c for c in choix if c["id"] == "rappel")
		assert rappel["condition"] == {"apport_en_cours": True, "apport_possible": False}
		texte = m["dialogue"]["noeuds"][rappel["next"]]["texte"]
		assert "{reste}" in texte and "{objet}" in texte, m["_id"]


def test_le_maitre_pratique_l_ecole_qu_il_enseigne():
	base = _base()
	vocations = {v["id"]: v for v in base["rules:vocations"]["value"]}
	for m in (d for d in _contenu() if d["type"] == "pnj"):
		sort = _sorts()[m["services"]["enseignement"]["sort"]]
		assert vocations[m["vocation"]]["magie"] == sort["magie"], m["_id"]


def test_chaque_maitre_est_present_dans_son_lieu_sans_toucher_aux_autres():
	base = _base()
	lieux = {d["_id"]: d for d in _contenu() if d["type"] == "lieu"}
	for m in gen.MAITRES:
		assert any(p.get("character") == "pnj:" + m["slug"] for p in lieux[m["lieu"]]["pnj"])
	for lieu_id, doc in lieux.items():
		avant = base[lieu_id]
		assert doc["pnj"][:len(avant.get("pnj") or [])] == list(avant.get("pnj") or [])
		assert {k: v for k, v in doc.items() if k != "pnj"} == {
			k: v for k, v in avant.items() if k not in ("pnj", "_rev")}


def _dump_apres_import():
	with open(os.path.join(RACINE, "jsons", "telluris-dump-20261027-060252.json"),
			  encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}


def test_philibert_ne_se_tient_que_sur_la_descente_des_catacombes():
	"""Importé d'abord sans `cases`, Philibert était sur toutes les cases de Lutecia : rejoué
	sur ce dump, le générateur ne réécrit que son entrée, postée sur la case qui descend."""
	base = _dump_apres_import()
	docs, erreurs = gen.construire(base)
	assert not erreurs
	# Chartres : Maître Bernard, posté devant le scriptorium (test suivant).
	# Les maîtres reviennent aussi (fusionnés) : ce dump précède leur choix `rappel`.
	assert sorted(d["_id"] for d in docs if d["type"] == "lieu") == ["lieu:chartres", "lieu:lutecia"]
	(entree,) = next(d for d in docs if d["_id"] == "lieu:lutecia")["pnj"]
	lien = base["link:lutecia_to_catacombes0001"]
	descente = next(n["pos"] for n in lien["nodes"] if n["lieu"] == "lieu:lutecia")
	assert entree["character"] == "pnj:philibert_des_catacombes"
	assert entree["cases"] == [descente]


def test_bernard_se_tient_devant_le_scriptorium_du_pont_bouju_joignable_des_portes():
	"""Maître Bernard n'est plus sur toute la cité : sur une case praticable voisine de la porte
	du Livre Relié du Pont Bouju, joignable à pied (voies.js, règle des flèches) depuis la case
	intérieure de CHAQUE porte de rempart de Chartres. Seule son entrée change."""
	base = _dump_apres_import()
	docs, erreurs = gen.construire(base)
	assert not erreurs
	chartres = next(d for d in docs if d["_id"] == "lieu:chartres")
	assert chartres == {**{k: v for k, v in base["lieu:chartres"].items() if k != "_rev"},
						"pnj": chartres["pnj"]}
	(entree,) = chartres["pnj"]
	assert entree["character"] == "pnj:bernard_de_l_ecole"
	(case,) = entree["cases"]
	x, y = case
	porte = next(n["pos"] for n in base["link:scriptorium01_to_chartres"]["nodes"]
				 if n["lieu"] == "lieu:chartres")
	assert max(abs(x - porte[0]), abs(y - porte[1])) == 1
	assert chartres["cells"][y][x] == 1
	interieurs = []
	for d in base.values():
		if d.get("type") != "connection":
			continue
		ici = [n for n in d["nodes"] if n["lieu"] == "lieu:chartres"]
		autre = [n["lieu"] for n in d["nodes"] if n["lieu"] != "lieu:chartres"]
		if ici and autre and autre[0].startswith("lieu:chartres_porte_") \
				and autre[0].endswith("_interieur"):
			interieurs.append(ici[0]["pos"])
	assert interieurs
	node = shutil.which("node")
	if node is None:
		pytest.skip("node absent : chemins non tracés")
	paires = [{"nom": str(p), "a": p, "b": case} for p in interieurs]
	paires.append({"nom": "porte", "a": case, "b": porte})
	with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
		json.dump({"cells": chartres["cells"], "nav": chartres.get("nav") or {},
				   "dims": chartres["dimensions"], "regle": "exploration", "max": 1,
				   "paires": paires}, f)
	try:
		sortie = subprocess.run([node, os.path.join(RACINE, "dev", "tracer_chemins.js"), f.name],
								capture_output=True, text=True, check=True).stdout
	finally:
		os.unlink(f.name)
	injoignables = [p["nom"] for p in json.loads(sortie)["paires"] if not p["chemins"]]
	assert injoignables == []


def test_un_maitre_deplace_quitte_son_ancien_lieu():
	"""Un maître posté ailleurs que là où une entrée le place encore : l'entrée part."""
	base = copy.deepcopy(_dump_apres_import())
	(entree,) = base["lieu:lutecia"]["pnj"]
	base["lieu:catacombes0001"]["pnj"] = [entree]
	docs, erreurs = gen.construire(base)
	assert not erreurs
	lieux = {d["_id"]: d for d in docs}
	assert "pnj" not in lieux["lieu:catacombes0001"]
	assert lieux["lieu:catacombes0001"] == {k: v for k, v in base["lieu:catacombes0001"].items()
											if k not in ("pnj", "_rev")}


def test_aucun_portrait_partage():
	portraits = [d["portrait"] for d in _contenu() if d["type"] == "pnj"]
	assert len(set(portraits)) == len(portraits)


def test_chaque_maitre_a_son_portrait_dans_le_depot():
	for m in gen.MAITRES:
		assert os.path.isfile(os.path.join(RACINE, "templates", "resources", "pnj", gen.portrait(m))), m["slug"]
