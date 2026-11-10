# tests/test_mercenaires.py
#
# Compagnons-JOUEURS (utils/mercenaires.py + branchements recrutement / combat) : offre au
# tableau d'une auberge, clone synchronisé avec l'original (progression + équipement porté),
# sac propre, un seul recruteur, XP et part de butin remontées à l'original par compteurs
# monotones, mort à 0 PV en fin de combat (sac au sol, équipement intact).

import pytest

from models import character_stats
from utils import mercenaires
from utils import recrutement
from utils import combat as combat_util
from utils import characters as characters_util

from tests.test_combat_groupe import character, joueur_snap, monstre_snap, combat_doc


LIEU = {"_id": "lieu:auberge", "categorie": "auberge"}


def original(**champs):
	"""Le personnage proposé, sur un AUTRE compte que le recruteur (`character:u_1`)."""
	perso = character("character:o_1", user_id="user:o", prenom="Ysolde", nom="Brune",
					  xp_total=500, vocations_niveaux={"guerrier": 3},
					  slots={"main_droite": {"item": "item:epee", "poids": 2},
							 "dos": {"item": "item:sac", "poids": 1,
									 "contenu": [{"item": "item:or", "poids": 1}]}},
					  inventaire=[{"item": "item:pain", "poids": 1}],
					  sorts_connus=["sort:feu"], attribute_points=4)
	perso.update(champs)
	return perso


@pytest.fixture
def db(monkeypatch):
	docs = {}

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	monkeypatch.setattr(combat_util, "get_doc", get_doc_fn)
	monkeypatch.setattr(combat_util, "save_doc", save_doc_fn)
	monkeypatch.setattr(characters_util, "get_doc", get_doc_fn)
	monkeypatch.setattr(recrutement, "get_doc", get_doc_fn)
	docs["get"] = get_doc_fn
	return docs


def _engager(db, recruteur=None, orig=None, exigences=None):
	"""Inscription + embauche, comme l'endpoint (sans persistance HTTP)."""
	orig = orig or original()
	recruteur = recruteur or character()
	offre = mercenaires.nouvelle_offre(orig, LIEU, exigences or {"part_butin_pct": 10, "clauses": []})
	clone = mercenaires.creer_clone(orig, offre)
	ok, raison = recrutement.embaucher(recruteur, clone, db["get"])
	assert ok, raison
	offre["clone_id"] = clone["_id"]
	offre["clones"] = [clone["_id"]]
	for d in (orig, recruteur, offre, clone):
		db[d["_id"]] = d
	return orig, recruteur, offre, clone


# ── Exigences saisies ────────────────────────────────────────────────────────────

def test_exigences_bornees(monkeypatch):
	monkeypatch.setattr(character_stats, "MERCENAIRE_CLAUSES_MAX", 2)
	monkeypatch.setattr(character_stats, "MERCENAIRE_CLAUSE_LONGUEUR_MAX", 10)
	ex = mercenaires.nettoyer_exigences({"part_butin_pct": 999,
										 "clauses": "  a​  \n\n" + "x" * 50 + "\nc\nd"})
	assert ex["part_butin_pct"] == character_stats.RECRUTEMENT_PART_BUTIN_MAX
	assert ex["clauses"] == ["a", "x" * 10]
	assert mercenaires.nettoyer_exigences({"part_butin_pct": "-3"})["part_butin_pct"] == 0
	assert mercenaires.nettoyer_exigences({"part_butin_pct": "abc"})["part_butin_pct"] == 0


def test_id_offre_opaque_et_deterministe():
	"""L'id d'un personnage contient le courriel de son joueur : l'offre n'en dit rien."""
	cid = "character:user:quelqu.un@example.com_1234"
	assert mercenaires.id_offre(cid) == mercenaires.id_offre(cid)
	assert "example" not in mercenaires.id_offre(cid)
	assert "example" not in mercenaires.creer_clone(original(_id=cid), {"_id": "service:x"})["_id"]


# ── Clone et synchronisation ─────────────────────────────────────────────────────

def test_clone_sac_vide_et_progression_de_l_original():
	orig = original()
	clone = mercenaires.creer_clone(orig, mercenaires.nouvelle_offre(orig, LIEU, {"part_butin_pct": 5}))
	assert clone["inventaire"] == []
	assert clone["xp_total"] == 500 and clone["sorts_connus"] == ["sort:feu"]
	assert clone["attribute_points"] == 0          # rien à dépenser sur la fiche du clone
	assert clone["slots"]["main_droite"] == {"item": "item:epee", "poids": 2}
	# Le contenant équipé n'ouvre pas au recruteur ce que l'original y range.
	assert "contenu" not in clone["slots"]["dos"]
	assert "contenu" in orig["slots"]["dos"]
	assert clone["exigences"]["part_butin_pct"] == 5
	assert mercenaires.est_clone(clone) and not mercenaires.est_clone(orig)


def test_synchroniser_relit_l_equipement_et_borne_les_pv():
	orig = original()
	clone = mercenaires.creer_clone(orig, {"_id": "service:x"})
	clone["inventaire"] = [{"item": "item:pain", "poids": 1}]
	clone["slots"]["main_droite"] = None             # ce qu'un combat aurait pu y écrire
	orig["xp_total"] = 900
	orig["caracteristiques_current"]["V"] = 1        # PV max en baisse
	clone["currentPV"] = 10 ** 6
	assert mercenaires.synchroniser(clone, orig) is True
	assert clone["slots"]["main_droite"] == {"item": "item:epee", "poids": 2}
	assert clone["xp_total"] == 900
	assert clone["inventaire"] == [{"item": "item:pain", "poids": 1}]   # le sac reste au clone
	pv_max, _ = mercenaires._maxima(clone)
	assert clone["currentPV"] == pv_max
	assert mercenaires.synchroniser(clone, None) is False


def test_groupe_effectif_synchronise_et_ecarte_sans_original(db):
	orig, recruteur, _offre, clone = _engager(db)
	orig["xp_total"] = 1234
	membres = recrutement.groupe_effectif(recruteur, db["get"])
	assert [m["_id"] for m in membres] == [clone["_id"]]
	assert membres[0]["xp_total"] == 1234
	del db[orig["_id"]]
	assert recrutement.groupe_effectif(recruteur, db["get"]) == []


# ── Un seul recruteur, jamais soi-même ───────────────────────────────────────────

def test_offre_disponibilite_derivee(db):
	orig, recruteur, offre, clone = _engager(db)
	assert not mercenaires.offre_disponible(offre, db["get"])
	autre = character("character:z_1", user_id="user:z")
	assert mercenaires.peut_engager(autre, offre, db["get"])[2] == 409
	clone["statut"] = "mort"                          # aucune réécriture de l'offre
	assert mercenaires.offre_disponible(offre, db["get"])
	assert mercenaires.peut_engager(autre, offre, db["get"])[0]
	offre["statut"] = "retire"
	assert mercenaires.peut_engager(autre, offre, db["get"])[2] == 404


def test_on_n_engage_pas_son_propre_compte(db):
	orig = original()
	offre = mercenaires.nouvelle_offre(orig, LIEU, {"part_butin_pct": 0, "clauses": []})
	meme_compte = character("character:o_2", user_id="user:o")
	assert mercenaires.peut_engager(meme_compte, offre, db["get"])[2] == 403


def test_pas_d_engagement_durable(db, monkeypatch):
	_orig, recruteur, _offre, clone = _engager(db)
	recruteur["affinites"][clone["_id"]] = 100
	ok, _ = recrutement.peut_engager(recruteur, clone)
	assert not ok


# ── Départs : le sac reste au sol ────────────────────────────────────────────────

def test_congedier_pose_le_sac_au_sol(db):
	orig, recruteur, _offre, clone = _engager(db)
	clone["inventaire"] = [{"item": "item:pain", "poids": 1}]
	clone["slots"] = dict(orig["slots"])
	ok, _ = recrutement.congedier(recruteur, clone)
	assert ok
	assert recruteur["objets_au_sol"] == [{"item": "item:pain", "poids": 1}]
	assert clone["inventaire"] == []
	assert clone["slots"]["main_droite"]               # l'équipement n'est pas au recruteur


def test_retrait_de_l_offre_fait_partir_le_clone(db):
	_orig, recruteur, offre, clone = _engager(db)
	clone["inventaire"] = [{"item": "item:pain", "poids": 1}]
	offre["statut"] = "retire"
	partis = recrutement.departs_volontaires(recruteur, db["get"])
	assert [p["_id"] for p in partis] == [clone["_id"]]
	assert clone["statut"] == "parti" and clone["_id"] not in recruteur["groupe"]
	assert recruteur["objets_au_sol"] == [{"item": "item:pain", "poids": 1}]


def test_original_disparu_fait_partir_le_clone(db):
	orig, recruteur, _offre, clone = _engager(db)
	del db[orig["_id"]]
	partis = recrutement.departs_volontaires(recruteur, db["get"])
	assert [p["_id"] for p in partis] == [clone["_id"]]


# ── XP et part de butin remontées à l'original ───────────────────────────────────

def test_part_de_butin_vers_le_compteur(db):
	_orig, recruteur, _offre, clone = _engager(db, exigences={"part_butin_pct": 20, "clauses": []})
	reglement = recrutement.regler_part_butin(recruteur, [clone], 100)
	part = reglement["parts"][clone["_id"]]
	assert part > 0
	assert clone["cuivre_pour_original"] == part


def test_encaisser_par_delta_idempotent(db):
	orig, _recruteur, offre, clone = _engager(db)
	xp_avant = orig["xp_total"]
	mercenaires.crediter_xp(clone, 30)
	mercenaires.crediter_cuivre(clone, 7)
	gains = mercenaires.encaisser(orig, offre, db["get"])
	assert (gains["xp"], gains["cuivre"]) == (30, 7)
	assert orig["xp_total"] == xp_avant + 30 and orig["cuivre"] == 7
	assert mercenaires.encaisser(orig, offre, db["get"])["xp"] == 0    # rien de neuf
	mercenaires.crediter_xp(clone, 5)
	assert mercenaires.encaisser(orig, offre, db["get"])["xp"] == 5


def test_encaisser_elague_un_ancien_clone_solde(db):
	orig, _recruteur, offre, clone = _engager(db)
	mercenaires.crediter_xp(clone, 10)
	clone["statut"] = "mort"
	offre["clone_id"] = None
	gains = mercenaires.encaisser(orig, offre, db["get"])
	assert gains["xp"] == 10 and gains["offre_mutee"]
	assert offre["clones"] == [] and clone["_id"] not in orig["encaisse_clones"]


# ── Combat ───────────────────────────────────────────────────────────────────────

def test_combat_xp_du_clone_remonte_a_l_original(db):
	_orig, recruteur, _offre, clone = _engager(db)
	j0 = joueur_snap("joueur_0", recruteur["_id"], pv=30)
	j1 = joueur_snap("joueur_1", clone["_id"], pv=20)
	doc = combat_doc([j0, j1], [monstre_snap(vivant=False)], status="victoire", xp_gagnee=10)
	assert combat_util.finalize_combat(doc) is True
	assert clone["xp_pour_original"] == 10
	assert clone["statut"] == "embauche"
	combat_util.finalize_combat(doc)                  # re-finalisation : pas de doublon
	assert clone["xp_pour_original"] == 10


@pytest.mark.parametrize("issue", ["victoire", "defaite"])
def test_combat_clone_a_0_pv_meurt_sac_au_sol(db, issue):
	orig, recruteur, _offre, clone = _engager(db)
	clone["inventaire"] = [{"item": "item:pain", "poids": 1}]
	clone["slots"] = dict(orig["slots"])
	j0 = joueur_snap("joueur_0", recruteur["_id"], pv=30 if issue == "victoire" else 0)
	j1 = joueur_snap("joueur_1", clone["_id"], pv=0,
					 butin_ramasse=[{"item": "item:rat", "poids": 2}])
	doc = combat_doc([j0, j1], [monstre_snap(vivant=issue != "victoire")],
					 status=issue, xp_gagnee=10)
	combat_util.finalize_combat(doc)
	assert clone["statut"] == "mort"
	assert clone["_id"] not in recruteur["groupe"]
	assert recruteur["objets_au_sol"] == [{"item": "item:pain", "poids": 1},
										  {"item": "item:rat", "poids": 2}]
	assert clone["inventaire"] == []
	assert clone["slots"]["main_droite"]               # l'équipement ne tombe pas
	assert clone["xp_pour_original"] == 0              # un mort ne gagne rien
	combat_util.finalize_combat(doc)                  # idempotent : rien ne se dédouble
	assert len(recruteur["objets_au_sol"]) == 2
