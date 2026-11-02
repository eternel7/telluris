"""Générateur des contenants (`dev/gen_contenants.py`).

Verrouille la forme que lit la mécanique (`utils/contenants.py`) et les règles arbitrées par
l'Auteur le 02/11/2026 (docs/conception_contenants.md) : jamais équipé, jamais personnalisé,
marée sur le seul Sac de Manannán, copies à prix fixe, reliques marquées, aucune collision
d'`_id` avec le dump (un import PUT complet écraserait en silence).
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev import gen_contenants as gen
from utils import contenants, marche

DOCS = {d["_id"]: d for d in gen.DOCS}
# Les trois copies d'Architectes : seuls objets vendus à prix fixe (décision du 02/11).
COPIES = ("item:besace_profonde", "item:urne_interieure", "item:coffre_de_retrait")


def test_chaque_doc_est_un_contenant_du_sac():
	assert len(DOCS) == len(gen.DOCS)                     # aucun _id en double
	for d in gen.DOCS:
		assert contenants.est_contenant(d), d["_id"]
		assert d["slots"] == [], d["_id"]                    # jamais équipé
		assert d["sous_categorie"] == "contenant"
		assert not marche.est_personnalisable(d), d["_id"]  # une variante changerait d'_id


def test_maree_sur_le_seul_sac_de_manannan():
	assert [i for i, d in DOCS.items() if contenants.a_maree(d)] == ["item:sac_de_manannan"]


def test_copies_a_prix_fixe_et_contenance_croissante():
	for i in COPIES:
		v = DOCS[i]["valeur"]
		assert v[0] == v[1], i
	caps = [contenants.capacite(DOCS[i]) for i in COPIES]
	prix = [DOCS[i]["valeur"][0]["cu"] for i in COPIES]
	assert caps == sorted(caps) and prix == sorted(prix)
	assert all("valeur" not in d for i, d in DOCS.items() if i not in COPIES)


def test_reliques_marquees_et_pots_d_anansi_non():
	reliques = {i for i, d in DOCS.items() if "relique" in d["tags"]}
	assert "item:pot_d_anansi" not in reliques               # « plusieurs pots » (Auteur)
	assert {"item:sac_de_manannan", "item:sac_de_rhiannon", "item:coquille_d_oduduwa"} <= reliques
	assert not reliques & set(COPIES)


def test_la_coquille_d_oduduwa_est_la_plus_vaste():
	plus_vaste = max(gen.DOCS, key=contenants.capacite)
	assert plus_vaste["_id"] == "item:coquille_d_oduduwa"


def test_aucune_collision_avec_le_dump_le_plus_recent():
	dumps = sorted(glob.glob(os.path.join(gen.RACINE, "jsons", "telluris-dump-*.json")))
	assert dumps
	with open(dumps[-1], encoding="utf-8") as f:
		existants = {d.get("_id") for d in json.load(f)["docs"]}
	assert gen.collisions(gen.DOCS, existants) == []
	assert gen.collisions(gen.DOCS, {"item:kibisis"}) == ["item:kibisis"]


def test_fichier_livre_identique_au_generateur():
	with open(gen.SORTIE, encoding="utf-8") as f:
		assert json.load(f)["docs"] == gen.DOCS
