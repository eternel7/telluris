# tests/test_butin_au_sol.py
# Le butin de victoire que PERSONNE n'emporte tombe au sol du principal au lieu de
# disparaître (chokepoint `utils.combat.verser_butin_au_sol`), d'où il redevient débitable.
#
# Ce que ces tests ferment : une carcasse est INDIVISIBLE dans l'overlay de fin, si bien
# qu'un gibier trop lourd pour tout le groupe n'avait qu'une issue — s'évaporer. C'est
# précisément le butin que `utils/carcasse.py` existe pour rendre accessible.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import carcasse
from utils.characters import carried_weight
from utils.combat import verser_butin_au_sol, MEMOIRE_COMBATS_MAX


def _combat(*entrees, status="victoire", cid="combat:1"):
	return {"_id": cid, "type": "combat", "status": status,
			"butin_disponible": [dict(e) for e in entrees]}


def _carcasse(mid, item="item:cerf", nom="Carcasse de cerf", poids=180.0):
	return {"monstre_id": mid, "item_id": item, "nom": nom, "poids": poids}


def _cerf_doc():
	"""Doc carcasse découpable, tel que le pose `dev/gen_carcasses_parties.py`."""
	return {
		"_id": "item:cerf", "type": "item", "sous_categorie": "carcasse",
		"poids": [100, 250], "decoupe_poids_min": 20,
		"decoupe": [
			{"item": "item:cerf_tete",  "quantite": 1, "fraction": 0.4},
			{"item": "item:cerf_corps", "quantite": 1, "fraction": 0.6},
		],
	}


# ── Le versement lui-même ───────────────────────────────────────────────────────

def test_ce_que_personne_nemporte_tombe_au_sol_avec_son_poids_dinstance():
	perso = {"_id": "character:a", "inventaire": []}
	combat = _combat(_carcasse("m1", poids=180.5))

	verses = verser_butin_au_sol(perso, combat)

	# Réf {item, poids} — la MÊME forme que l'encaissement : c'est ce poids d'instance
	# (et non celui du doc item) que la découpe compare ensuite à son seuil.
	assert perso["objets_au_sol"] == [{"item": "item:cerf", "poids": 180.5}]
	assert verses == [{"nom": "Carcasse de cerf", "poids": 180.5}]
	assert combat["butin_disponible"] == []


def test_le_sol_ne_surcharge_personne():
	"""`carried_weight` somme le sac et les équipés, JAMAIS le sol : verser une carcasse de
	180 kg sur un personnage qui n'en porte que 5 ne peut pas le bloquer sur place."""
	perso = {"_id": "character:a", "inventaire": [{"item": "item:corde", "poids": 5.0}]}
	avant = carried_weight(perso)

	verser_butin_au_sol(perso, _combat(_carcasse("m1", poids=180.0)))

	assert carried_weight(perso) == avant


def test_le_sol_deja_occupe_est_complete_jamais_ecrase():
	perso = {"_id": "character:a", "objets_au_sol": [{"item": "item:hache", "poids": 3.0}]}

	verser_butin_au_sol(perso, _combat(_carcasse("m1")))

	assert [r["item"] for r in perso["objets_au_sol"]] == ["item:hache", "item:cerf"]


# ── La garde : « sorti du butin », sac OU sol ────────────────────────────────────

def test_deux_appels_ne_versent_quune_fois():
	"""Le filet de /play tourne APRÈS /collect ; sans la garde, un `save_doc(combat_doc)`
	best-effort échoué doublerait la carcasse."""
	perso = {"_id": "character:a"}
	combat = _combat(_carcasse("m1"))

	verser_butin_au_sol(perso, combat)
	# Le doc combat relu en base porterait encore son butin : on rejoue à l'identique.
	combat["butin_disponible"] = [_carcasse("m1")]
	assert verser_butin_au_sol(perso, combat) == []
	assert len(perso["objets_au_sol"]) == 1


def test_une_carcasse_encaissee_nest_jamais_versee_au_sol():
	perso = {"_id": "character:a"}
	combat = _combat(_carcasse("m1"), _carcasse("m2", item="item:loup", nom="Carcasse de loup"))

	verses = verser_butin_au_sol(perso, combat, deja={"m1"})

	assert [v["nom"] for v in verses] == ["Carcasse de loup"]
	assert [r["item"] for r in perso["objets_au_sol"]] == ["item:loup"]
	# La garde mémorise ENSEMBLE l'encaissé et le versé : ni l'un ni l'autre ne revient.
	assert perso["butin_collectes"]["combat:1"] == ["m1", "m2"]


def test_la_garde_est_bornee_et_lordre_dinsertion_suit_la_recence():
	perso = {"_id": "character:a"}
	for n in range(MEMOIRE_COMBATS_MAX + 3):
		verser_butin_au_sol(perso, _combat(_carcasse("m1"), cid=f"combat:{n}"))

	garde = perso["butin_collectes"]
	assert len(garde) == MEMOIRE_COMBATS_MAX
	assert list(garde)[-1] == f"combat:{MEMOIRE_COMBATS_MAX + 2}"   # le plus récent survit
	assert "combat:0" not in garde                                   # le plus ancien est évincé


def test_un_combat_deja_verse_qui_revient_remonte_en_tete_de_recence():
	"""`pop` avant réécriture : réassigner une clé existante ne la déplacerait pas en fin de
	dict, et elle vieillirait à sa place jusqu'à être évincée alors qu'elle vient de servir."""
	perso = {"_id": "character:a"}
	verser_butin_au_sol(perso, _combat(_carcasse("m1"), cid="combat:vieux"))
	verser_butin_au_sol(perso, _combat(_carcasse("m1"), cid="combat:autre"))
	verser_butin_au_sol(perso, _combat(_carcasse("m2"), cid="combat:vieux"))

	assert list(perso["butin_collectes"])[-1] == "combat:vieux"


# ── Ce que le versement N'EST PAS ────────────────────────────────────────────────

def test_une_defaite_ne_verse_rien():
	"""`butin_disponible` n'a de sens qu'à la victoire — c'est là, et là seulement, que
	`finalize_combat` le remplit. Le garde interdit qu'une écriture future y dépose quoi que
	ce soit qui se retrouverait au sol sans qu'on l'ait décidé : la cargaison d'une monture
	tombée y transitait POUR TOUTES LES ISSUES (elle va au sol directement aujourd'hui),
	et un filet non gardé aurait rendu sur une défaite un butin délibérément perdu."""
	perso = {"_id": "character:a"}
	combat = _combat(_carcasse("m1"), status="defaite")

	assert verser_butin_au_sol(perso, combat) == []
	assert perso.get("objets_au_sol") in (None, [])
	assert combat["butin_disponible"] != []   # rien n'a été consommé non plus


def test_une_garde_illisible_ne_fait_pas_perdre_le_butin():
	perso = {"_id": "character:a", "butin_collectes": "n'importe quoi"}

	assert len(verser_butin_au_sol(perso, _combat(_carcasse("m1")))) == 1
	assert isinstance(perso["butin_collectes"], dict)


# ── Le chaînage vers la découpe, qui est TOUTE la raison d'être du versement ──────

def test_la_carcasse_versee_est_debitable_sur_place():
	"""Le poids d'instance conservé au versement est celui que `item_est_decoupable`
	compare au seuil : sans lui, le 🪓 du sol ne verrait rien à couper."""
	perso = {"_id": "character:a"}
	verser_butin_au_sol(perso, _combat(_carcasse("m1", poids=180.0)))

	ref = perso["objets_au_sol"][0]
	assert carcasse.item_est_decoupable(_cerf_doc(), ref["poids"])
	pieces = carcasse.decouper_ref(ref, _cerf_doc())
	# Conservation de la masse : ce qu'on repose au sol pèse ce qu'on y avait laissé.
	assert round(sum(p["poids"] for p in pieces), 2) == 180.0
