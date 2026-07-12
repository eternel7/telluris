"""Rotation du tableau de guilde (utils/quetes.py) — logique pure, sans DB.

Une offre GÉNÉRÉE a une durée de vie : passé son terme, elle est réputée prise par un autre
aventurier — son doc est supprimé et une nouvelle offre la remplace. Les accès DB de
`utils/quetes.py` sont des imports directs de `db.config` : on les monkeypatche sur le module.
"""

import pytest

from models import character_stats
from utils import quetes


# ── Monde de test ────────────────────────────────────────────────────────────────
# Une guilde et sa cité. Le parent porte assez d'espèces de rencontres pour que le générateur
# ait toujours des cibles distinctes sous la main (le tableau est borné par ce vivier).

GUILDE = {"_id": "lieu:guilde", "type": "lieu", "categorie": "guilde_aventurier",
          "lieu_parent": "lieu:ville"}
VILLE = {
	"_id": "lieu:ville", "type": "lieu", "categorie": "ville", "niveau": 1,
	"table_evenements": [
		{"type": "combat", "especes": [f"espece:bestiole{i}" for i in range(8)]},
	],
	"rencontres": [{"espece": f"espece:bestiole{i}"} for i in range(8)],
}
ESPECES = {
	f"espece:bestiole{i}": {
		"_id": f"espece:bestiole{i}", "type": "espece", "nom": f"Bestiole {i}",
		"caracteristiques": {"F": [20, 30], "R": [20, 30], "Ag": [20, 30], "V": [4, 5]},
	}
	for i in range(8)
}


@pytest.fixture
def board(monkeypatch):
	"""Base en mémoire branchée sur les accès DB du module `quetes`."""
	docs = dict(ESPECES)
	docs[VILLE["_id"]] = VILLE
	docs[GUILDE["_id"]] = GUILDE
	supprimes = []

	monkeypatch.setattr(quetes, "get_doc", lambda doc_id: docs.get(doc_id))
	monkeypatch.setattr(quetes, "find_docs", lambda selector: [
		d for d in docs.values() if d.get("type") == selector.get("type")
	])

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	def delete_doc_fn(doc):
		docs.pop(doc["_id"], None)
		supprimes.append(doc)
		return None

	monkeypatch.setattr(quetes, "save_doc", save_doc_fn)
	monkeypatch.setattr(quetes, "delete_doc", delete_doc_fn)
	# Horloge figée : `remplir_tableau` lit l'heure lui-même, les `expire_at` des tests sont
	# donc à situer autour de 1000 (et non sur l'epoch réelle).
	monkeypatch.setattr(quetes, "now_epoch", lambda: 1000)
	monkeypatch.setattr(character_stats, "QUETE_BOARD_TAILLE", 6)
	monkeypatch.setattr(character_stats, "QUETE_BOARD_DUREE_SECONDES", 3600)
	monkeypatch.setattr(character_stats, "QUETE_BOARD_DUREE_JITTER", 0.5)
	return {"docs": docs, "supprimes": supprimes}


def offre(oid, source="genere", statut="offerte", **champs):
	"""Offre minimale au tableau de la guilde (les champs d'horodatage varient selon le test)."""
	return {
		"_id": oid, "type": "quete", "source": source, "statut": statut,
		"giver": "lieu:guilde", "titre": oid, "objectif": {"type": "kill", "cible": oid, "quantite": 3},
		"recompenses": {"xp": 10, "cuivre": 30},
		**champs,
	}


# ── Durée de vie tirée à la génération ───────────────────────────────────────────

def test_expire_at_dans_la_fenetre_jittee(board, monkeypatch):
	monkeypatch.setattr(quetes, "now_epoch", lambda: 1000)
	q = quetes.generer_quete(GUILDE, VILLE, "kill", "espece:bestiole0", 1)
	assert q["genere_at"] == 1000
	assert 1000 + 1800 <= q["expire_at"] <= 1000 + 5400  # [D×0.5, D×1.5]


def test_les_offres_dun_meme_lot_ne_periment_pas_ensemble(board):
	"""Tout l'intérêt du jitter : sans lui, les 6 offres du tableau basculeraient d'un bloc."""
	echeances = {
		quetes.generer_quete(GUILDE, VILLE, "kill", f"espece:bestiole{i}", 1)["expire_at"]
		for i in range(8)
	}
	assert len(echeances) > 1


def test_jitter_nul_donne_une_duree_fixe(board, monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_BOARD_DUREE_JITTER", 0.0)
	monkeypatch.setattr(quetes, "now_epoch", lambda: 1000)
	q = quetes.generer_quete(GUILDE, VILLE, "kill", "espece:bestiole0", 1)
	assert q["expire_at"] == 1000 + 3600


# ── offre_perimee ────────────────────────────────────────────────────────────────

def test_generee_echue_est_perimee(board):
	assert quetes.offre_perimee(offre("quete:a", expire_at=1000), 1000) is True


def test_generee_fraiche_ne_lest_pas(board):
	assert quetes.offre_perimee(offre("quete:a", expire_at=1001), 1000) is False


def test_authoree_ne_perime_jamais(board):
	"""Une mission écrite est un contenu de scénario, pas un contrat pris par un passant."""
	vieille = offre("quete:borin", source="authoree", expire_at=1)
	assert quetes.offre_perimee(vieille, 999_999) is False


def test_acceptee_nest_pas_concernee(board):
	"""Elle a quitté le tableau : c'est le snapshot du joueur qui compte désormais."""
	prise = offre("quete:a", statut="acceptee", expire_at=1)
	assert quetes.offre_perimee(prise, 999_999) is False


def test_repli_legacy_sur_genere_at(board):
	"""Offre d'avant la feature (pas d'`expire_at`) : l'échéance se dérive de `genere_at`."""
	legacy = offre("quete:a", genere_at=1000)
	assert quetes.offre_perimee(legacy, 1000 + 3599) is False
	assert quetes.offre_perimee(legacy, 1000 + 3600) is True


def test_offre_sans_aucun_horodatage_est_perimee(board):
	assert quetes.offre_perimee(offre("quete:a"), 1000) is True


# ── Purge + recomplétion du tableau ──────────────────────────────────────────────

def test_purge_supprime_les_docs_perimes_et_garde_les_autres(board):
	perimee = offre("quete:vieille", expire_at=500)
	fraiche = offre("quete:fraiche", expire_at=5000)

	restantes = quetes.purger_offres_perimees([perimee, fraiche], 1000)

	assert restantes == [fraiche]
	assert board["supprimes"] == [perimee]


def test_le_tableau_remplace_les_offres_perimees(board):
	"""2 périmées sur 6 → les 2 docs sont supprimés, les 4 autres survivent à l'identique,
	et le tableau est recomplété à QUETE_BOARD_TAILLE."""
	docs = board["docs"]
	survivantes = []
	for i in range(4):
		o = offre(f"quete:fraiche{i}", expire_at=5000)
		o["objectif"] = {"type": "kill", "cible": f"espece:bestiole{i}", "quantite": 3}
		docs[o["_id"]] = o
		survivantes.append(o["_id"])
	for i in range(2):
		o = offre(f"quete:vieille{i}", expire_at=1)
		o["objectif"] = {"type": "kill", "cible": f"espece:bestiole{4 + i}", "quantite": 3}
		docs[o["_id"]] = o

	offres = quetes.remplir_tableau(GUILDE)

	assert sorted(d["_id"] for d in board["supprimes"]) == ["quete:vieille0", "quete:vieille1"]
	ids = {o["_id"] for o in offres}
	assert set(survivantes) <= ids            # les fraîches sont restées telles quelles
	assert not (ids & {"quete:vieille0", "quete:vieille1"})
	assert len(offres) == 6                   # le tableau est plein à nouveau
	# Les remplaçantes sont bien de vraies nouvelles offres persistées.
	nouvelles = ids - set(survivantes)
	assert len(nouvelles) == 2
	assert all(docs[n]["source"] == "genere" and docs[n]["expire_at"] for n in nouvelles)


def test_une_quete_authoree_ancienne_reste_au_tableau(board):
	"""Elle occupe une place hors quota généré : le tableau se remplit AUTOUR d'elle."""
	docs = board["docs"]
	docs["quete:borin"] = offre("quete:borin", source="authoree", genere_at=1)

	offres = quetes.remplir_tableau(GUILDE)

	assert "quete:borin" in {o["_id"] for o in offres}
	assert board["supprimes"] == []
	assert len([o for o in offres if o.get("source") == "genere"]) == 6
