"""Inventaire du groupe (utils/recrutement.py) — transfert d'objets, logique pure.

Le sac d'un compagnon est celui d'un doc `aventurier:*`, miroir du character : les mêmes
helpers de poids/charge s'y appliquent. On vérifie ici les trois invariants du transfert :
le poids d'INSTANCE est préservé (deux exemplaires d'un même item peuvent peser différemment),
la charge max du destinataire est un refus DUR, et un refus ne doit JAMAIS amputer la source.
"""

import pytest

from utils import recrutement
from utils import characters as characters_util


# ── Monde de test ────────────────────────────────────────────────────────────────

CAILLOU = {"_id": "item:caillou", "type": "item", "nom": "Caillou", "poids": [1, 9]}
ENCLUME = {"_id": "item:enclume", "type": "item", "nom": "Enclume", "poids": 40}
EPEE    = {"_id": "item:epee", "type": "item", "nom": "Épée", "poids": 2, "slots": ["main_droite"]}


@pytest.fixture
def monde(monkeypatch):
	docs = {d["_id"]: d for d in (CAILLOU, ENCLUME, EPEE)}
	monkeypatch.setattr(characters_util, "get_doc", lambda doc_id: docs.get(doc_id))
	return docs


def porteur(_id="character:u_1", force=10, inventaire=None, slots=None):
	"""charge_max = F × 5 → F=10 donne 50 kg."""
	return {
		"_id": _id, "prenom": "Test", "nom": "Porteur",
		"caracteristiques_current": {"V": 5, "F": force, "R": 20, "Ag": 20,
									 "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
		"inventaire": list(inventaire or []),
		"slots": dict(slots or {}),
	}


# ── peut_porter ──────────────────────────────────────────────────────────────────

def test_peut_porter_borne_exacte(monde):
	"""À la charge max PILE, l'objet passe encore ; un gramme au-dessus, non."""
	av = porteur(force=10)                                  # charge_max = 50
	av["inventaire"] = [{"item": "item:caillou", "poids": 10}]
	assert recrutement.peut_porter(av, {"item": "item:enclume", "poids": 40}) is True
	assert recrutement.peut_porter(av, {"item": "item:enclume", "poids": 41}) is False


def test_peut_porter_compte_les_equipes(monde):
	"""La charge portée inclut l'équipement, pas seulement le sac."""
	av = porteur(force=10, slots={"main_droite": {"item": "item:enclume", "poids": 45}})
	assert recrutement.peut_porter(av, {"item": "item:caillou", "poids": 6}) is False
	assert recrutement.peut_porter(av, {"item": "item:caillou", "poids": 5}) is True


# ── transferer_ref ───────────────────────────────────────────────────────────────

def test_transfert_preserve_le_poids_d_instance(monde):
	"""Deux cailloux de poids différents : c'est bien l'exemplaire visé qui part, avec SON
	poids (une re-résolution par item_id seul ramènerait le poids minimum du doc)."""
	joueur = porteur(inventaire=[{"item": "item:caillou", "poids": 2},
								 {"item": "item:caillou", "poids": 8}])
	av = porteur("aventurier:x", force=10)

	ok, raison, ref = recrutement.transferer_ref(joueur, av, 1, "item:caillou")

	assert (ok, raison) == (True, "")
	assert ref == {"item": "item:caillou", "poids": 8}
	assert joueur["inventaire"] == [{"item": "item:caillou", "poids": 2}]
	assert av["inventaire"] == [{"item": "item:caillou", "poids": 8}]


def test_transfert_ref_legacy_string(monde):
	"""Une entrée legacy (simple chaîne) traverse telle quelle."""
	joueur = porteur(inventaire=["item:epee"])
	av = porteur("aventurier:x")

	ok, _, ref = recrutement.transferer_ref(joueur, av, 0, "item:epee")

	assert ok and ref == "item:epee"
	assert joueur["inventaire"] == [] and av["inventaire"] == ["item:epee"]


def test_transfert_index_desaligne_repli_sur_item_id(monde):
	"""Index périmé (le client a une vue plus ancienne) : on retombe sur le premier
	exemplaire de l'item plutôt que de transférer le mauvais objet."""
	joueur = porteur(inventaire=["item:epee"])
	av = porteur("aventurier:x")

	ok, _, ref = recrutement.transferer_ref(joueur, av, 7, "item:epee")

	assert ok and ref == "item:epee"
	assert joueur["inventaire"] == []


def test_transfert_objet_absent(monde):
	joueur = porteur(inventaire=["item:epee"])
	av = porteur("aventurier:x")

	ok, raison, ref = recrutement.transferer_ref(joueur, av, 0, "item:enclume")

	assert ok is False and ref is None
	assert raison.startswith("Objet")
	assert joueur["inventaire"] == ["item:epee"]


def test_transfert_refuse_si_surcharge_et_n_ampute_pas_la_source(monde):
	"""Refus DUR : rien ne tombe au sol, et surtout la source garde son objet — un pop
	avant contrôle le ferait disparaître."""
	joueur = porteur(inventaire=[{"item": "item:enclume", "poids": 40}])
	av = porteur("aventurier:x", force=4)                   # charge_max = 20
	av["inventaire"] = [{"item": "item:caillou", "poids": 5}]

	ok, raison, ref = recrutement.transferer_ref(joueur, av, 0, "item:enclume")

	assert ok is False and ref is None
	assert "porter davantage" in raison
	assert joueur["inventaire"] == [{"item": "item:enclume", "poids": 40}]
	assert av["inventaire"] == [{"item": "item:caillou", "poids": 5}]


def test_transfert_retour_vers_le_joueur(monde):
	"""Le sens inverse n'est pas un cas particulier : mêmes contrôles, docs échangés."""
	av = porteur("aventurier:x", inventaire=[{"item": "item:caillou", "poids": 3}])
	joueur = porteur()

	ok, _, _ = recrutement.transferer_ref(av, joueur, 0, "item:caillou")

	assert ok
	assert av["inventaire"] == []
	assert joueur["inventaire"] == [{"item": "item:caillou", "poids": 3}]


def test_objet_equipe_non_transferable(monde):
	"""Un objet équipé vit dans `slots`, pas dans `inventaire` : il faut le déséquiper
	d'abord (sinon on le dupliquerait)."""
	joueur = porteur(slots={"main_droite": "item:epee"})
	av = porteur("aventurier:x")

	ok, raison, _ = recrutement.transferer_ref(joueur, av, 0, "item:epee")

	assert ok is False and raison.startswith("Objet")
	assert joueur["slots"]["main_droite"] == "item:epee"
	assert av["inventaire"] == []


def test_transfert_sans_inventaire_initial(monde):
	"""Le destinataire n'a pas encore de clé `inventaire` (doc fraîchement généré)."""
	joueur = porteur(inventaire=["item:epee"])
	av = {"_id": "aventurier:x", "prenom": "Aldric",
		  "caracteristiques_current": {"F": 10, "V": 5, "R": 20, "Ag": 20,
									   "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20}}

	ok, _, _ = recrutement.transferer_ref(joueur, av, 0, "item:epee")

	assert ok and av["inventaire"] == ["item:epee"]


# ── Garde d'appartenance : groupe_effectif ───────────────────────────────────────

def test_groupe_effectif_exclut_les_non_compagnons(monde):
	"""Le seul verrou d'ownership d'un doc `aventurier:*` (il n'a pas de `user_id`) :
	un compagnon parti, ou embauché par quelqu'un d'autre, n'est pas du groupe — les
	endpoints /api/groupe/* et `_acteur` en dérivent leur 403."""
	docs = {
		"aventurier:a": {"_id": "aventurier:a", "statut": "embauche", "embauche_par": "character:u_1"},
		"aventurier:b": {"_id": "aventurier:b", "statut": "parti", "embauche_par": "character:u_1"},
		"aventurier:c": {"_id": "aventurier:c", "statut": "embauche", "embauche_par": "character:autre"},
	}
	joueur = porteur()
	joueur["groupe"] = ["aventurier:a", "aventurier:b", "aventurier:c", "aventurier:inconnu"]

	actifs = recrutement.groupe_effectif(joueur, lambda i: docs.get(i))

	assert [a["_id"] for a in actifs] == ["aventurier:a"]
