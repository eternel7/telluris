"""Sanction de réputation d'un renoncement (utils/quetes.py) — logique pure, sans DB.

Renoncer à une quête (abandon volontaire ou délai laissé filer) fâche le donneur ET toute sa
MAISON : les lieux qui partagent sa `sous_categorie` ET son `lieu_parent`. Les dépendances DB
sont injectées (get_doc_fn / save_doc_fn / find_docs_fn), comme dans test_transport.py.
"""

import pytest

from models import character_stats
from utils import marche, quetes, transport


# ── Monde de test ────────────────────────────────────────────────────────────────
# Une guilde éclatée en trois lieux d'une même ville : la réception et le comptoir portent la
# `sous_categorie` (ils sont la maison), la façade non (extérieur inerte). Une boucherie partage
# leur `lieu_parent` — c'est le piège que la conjonction doit écarter. Une seconde guilde, dans
# une autre ville, porte la MÊME `sous_categorie` : le `lieu_parent` doit l'écarter à son tour.

RECEPTION = {
	"_id": "lieu:bastion_interieur", "type": "lieu", "label": "Le Bastion - réception",
	"categorie": "guilde_aventurier", "sous_categorie": "guilde_aventurier",
	"lieu_parent": "lieu:auxerre",
}
COMPTOIR = {
	"_id": "lieu:bastion_comptoir", "type": "lieu", "label": "Le comptoir du Bastion",
	"categorie": "guilde_aventurier_comptoir", "sous_categorie": "guilde_aventurier",
	"lieu_parent": "lieu:auxerre",
}
FACADE = {
	"_id": "lieu:bastion", "type": "lieu", "label": "Le Bastion",
	"categorie": "guilde_aventurier_exterieur",  # pas de `sous_categorie` → hors maison
	"lieu_parent": "lieu:auxerre",
}
BOUCHERIE = {
	"_id": "lieu:boucherie", "type": "lieu", "label": "L'Étal",
	"categorie": "boucherie", "lieu_parent": "lieu:auxerre",
}
GUILDE_AILLEURS = {
	"_id": "lieu:guilde_rhemi", "type": "lieu", "label": "La guilde de Rhemi",
	"categorie": "guilde_aventurier", "sous_categorie": "guilde_aventurier",
	"lieu_parent": "lieu:rhemi",  # autre cité
}

MONDE = [RECEPTION, COMPTOIR, FACADE, BOUCHERIE, GUILDE_AILLEURS]


def make_find_docs(monde=MONDE):
	"""find_docs injecté : ne sait filtrer que sur le sélecteur qu'utilise `lieux_solidaires`."""
	def find_docs_fn(selector):
		return [
			d for d in monde
			if d.get("type") == selector.get("type")
			and d.get("lieu_parent") == selector.get("lieu_parent")
		]
	return find_docs_fn


@pytest.fixture
def perso():
	return {"_id": "character:test", "quetes_actives": [], "inventaire": []}


@pytest.fixture
def db():
	"""Base en mémoire : `docs` sert de get_doc, `sauves` enregistre les save_doc."""
	docs, sauves = {}, []

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		sauves.append(doc)
		return doc

	return {"docs": docs, "sauves": sauves, "get": get_doc_fn, "save": save_doc_fn}


def ids(lieux):
	return sorted(l["_id"] for l in lieux)


# ── sous_categorie_lieu ──────────────────────────────────────────────────────────

def test_sous_categorie_lue_sur_le_lieu():
	assert quetes.sous_categorie_lieu(RECEPTION) == "guilde_aventurier"


def test_sous_categorie_absente_ou_doc_vide():
	assert quetes.sous_categorie_lieu(BOUCHERIE) == ""
	assert quetes.sous_categorie_lieu(None) == ""


# ── lieux_solidaires ─────────────────────────────────────────────────────────────

def test_magasin_nest_solidaire_que_de_lui_meme():
	"""Sans `sous_categorie`, pas de maison : le comportement historique est préservé."""
	assert quetes.lieux_solidaires(BOUCHERIE, make_find_docs()) == [BOUCHERIE]


def test_guilde_regroupe_ses_lieux_sans_ramasser_la_ville():
	"""Réception + comptoir. NI la boucherie (même `lieu_parent`, pas la maison),
	NI la façade (pas de `sous_categorie`), NI la guilde de l'autre cité."""
	lieux = quetes.lieux_solidaires(RECEPTION, make_find_docs())
	assert ids(lieux) == ["lieu:bastion_comptoir", "lieu:bastion_interieur"]


def test_la_maison_se_reconstitue_depuis_nimporte_lequel_de_ses_lieux():
	"""Le comptoir (donneur de la mission de Borin) retrouve la réception, et réciproquement."""
	assert ids(quetes.lieux_solidaires(COMPTOIR, make_find_docs())) == ids(
		quetes.lieux_solidaires(RECEPTION, make_find_docs())
	)


def test_le_giver_est_toujours_en_tete():
	assert quetes.lieux_solidaires(COMPTOIR, make_find_docs())[0]["_id"] == "lieu:bastion_comptoir"


def test_giver_absent_du_resultat_de_find_docs_nest_pas_perdu():
	"""find_docs muet (index absent, base en vrac) → on retombe sur le donneur seul, sans crash."""
	assert quetes.lieux_solidaires(RECEPTION, lambda selector: None) == [RECEPTION]


def test_giver_sans_lieu_parent():
	orphelin = {"_id": "lieu:orphelin", "sous_categorie": "guilde_aventurier"}
	assert quetes.lieux_solidaires(orphelin, make_find_docs()) == [orphelin]


# ── sanctionner_renoncement ──────────────────────────────────────────────────────

def test_sanction_frappe_toute_la_maison(perso, db, monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)

	valeurs = quetes.sanctionner_renoncement(perso, COMPTOIR, db["get"], db["save"], make_find_docs())

	assert valeurs == {"lieu:bastion_comptoir": 49, "lieu:bastion_interieur": 49}
	# Un doc `relation` persisté par lieu — ce sont des docs ANNEXES, hors character.
	assert len(db["sauves"]) == 2
	assert all(d["type"] == "relation" for d in db["sauves"])


def test_le_giver_nest_pas_decremente_deux_fois(perso, db, monkeypatch):
	"""Il est en tête de la liste ET rendu par find_docs : la déduplication doit tenir."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)

	quetes.sanctionner_renoncement(perso, RECEPTION, db["get"], db["save"], make_find_docs())

	relation = db["docs"][marche.relation_doc_id(perso, RECEPTION)]
	assert marche.relation_value(relation) == 49


def test_sanction_repart_de_la_relation_existante(perso, db, monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	db["docs"][marche.relation_doc_id(perso, RECEPTION)] = {
		"_id": marche.relation_doc_id(perso, RECEPTION), "type": "relation",
		"character_id": perso["_id"], "lieu_id": RECEPTION["_id"], "value": 72,
	}
	valeurs = quetes.sanctionner_renoncement(perso, RECEPTION, db["get"], db["save"], make_find_docs())
	assert valeurs["lieu:bastion_interieur"] == 71


def test_relation_bornee_a_zero(perso, db, monkeypatch):
	"""Un banni ne peut pas descendre plus bas (`ajuster_relation` clampe 0–100)."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	db["docs"][marche.relation_doc_id(perso, RECEPTION)] = {
		"_id": marche.relation_doc_id(perso, RECEPTION), "type": "relation",
		"character_id": perso["_id"], "lieu_id": RECEPTION["_id"], "value": 0,
	}
	valeurs = quetes.sanctionner_renoncement(perso, RECEPTION, db["get"], db["save"], make_find_docs())
	assert valeurs["lieu:bastion_interieur"] == 0


def test_sanction_dun_magasin_ne_touche_que_lui(perso, db, monkeypatch):
	"""Une course confiée par une boutique reste une affaire entre elle et le joueur."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)

	valeurs = quetes.sanctionner_renoncement(perso, BOUCHERIE, db["get"], db["save"], make_find_docs())

	assert valeurs == {"lieu:boucherie": 49}
	assert len(db["sauves"]) == 1


# ── Expiration d'une course (utils/transport.py) ─────────────────────────────────

def test_expiration_dune_course_de_guilde_fache_toute_la_maison(perso, db, monkeypatch):
	"""Laisser filer le délai de la mission du comptoir doit coûter autant que l'abandonner —
	et la réception l'apprend aussi."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)
	db["docs"][COMPTOIR["_id"]] = COMPTOIR
	perso["quetes_actives"] = [{
		"id": "quete:mission", "titre": "Deux caisses de viande",
		"giver": "lieu:bastion_comptoir",
		"objectif": {"type": "transport"},
		"expire_at": 1000,
		"cargaison": [{"item": "item:viande", "poids": 2}],
	}]

	echues = transport.traiter_expirations(perso, 1001, db["get"], db["save"], make_find_docs())

	assert len(echues) == 1
	assert perso["quetes_actives"] == []
	relations = {d["lieu_id"]: marche.relation_value(d) for d in db["sauves"] if d["type"] == "relation"}
	assert relations == {"lieu:bastion_comptoir": 49, "lieu:bastion_interieur": 49}
	# La cargaison reste dans le sac : le joueur garde la marchandise, seule sa réputation paie.
	assert echues[0]["cargaison"] == [{"item": "item:viande", "poids": 2}]
