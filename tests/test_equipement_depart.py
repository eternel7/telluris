# tests/test_equipement_depart.py
# Équipement de départ porté dès la création (utils.characters.equiper_au_depart) :
# premier slot libre de l'objet, règles de l'équipement manuel, rien de délogé.

from utils.characters import equiper_au_depart

ITEMS = {
	"item:Hache_de_guerre": {"slots": ["main_droite"]},
	"item:Dague": {"slots": ["main_droite", "main_gauche"]},
	"item:Lame_courte": {"slots": ["main_droite"]},
	"item:Arc_court": {"slots": ["main_droite", "main_gauche"], "deux_mains": True},
	"item:Couteau_de_chasse": {"slots": ["main_droite", "main_gauche"]},
	"item:Masse_lourde": {"slots": ["main_droite"], "restriction": {"F": 40}},
	"item:Potion": {"slots": []},
	"item:Bride": {"slots": ["harnachement"]},
}
SLOTS = ["main_droite", "main_gauche", "torse", "tete"]


def _resoudre(ref):
	return ITEMS.get(ref if isinstance(ref, str) else ref.get("item"))


def _perso(inventaire, F=30, **slots):
	return {
		"inventaire": list(inventaire),
		"slots": {s: slots.get(s) for s in SLOTS},
		"caracteristiques_current": {"F": F},
	}


def test_barbare_hache_en_main_droite():
	c = _perso(["item:Hache_de_guerre"])
	assert equiper_au_depart(c, _resoudre) == ["main_droite"]
	assert c["slots"]["main_droite"] == "item:Hache_de_guerre"
	assert c["inventaire"] == []


def test_reference_a_poids_d_instance_conservee():
	ref = {"item": "item:Hache_de_guerre", "poids": 3.2}
	c = _perso([ref])
	equiper_au_depart(c, _resoudre)
	assert c["slots"]["main_droite"] is ref


def test_l_objet_au_slot_unique_passe_d_abord():
	# Assassin : la dague irait aussi à gauche, la lame courte seulement à droite.
	c = _perso(["item:Dague", "item:Lame_courte"])
	equiper_au_depart(c, _resoudre)
	assert c["slots"]["main_droite"] == "item:Lame_courte"
	assert c["slots"]["main_gauche"] == "item:Dague"
	assert c["inventaire"] == []


def test_arme_a_deux_mains_bloque_l_autre_main():
	# Forestier : l'arc prend les deux mains, le couteau reste au sac.
	c = _perso(["item:Arc_court", "item:Couteau_de_chasse"])
	equiper_au_depart(c, _resoudre)
	assert c["slots"]["main_droite"] == "item:Arc_court"
	assert c["slots"]["main_gauche"] is None
	assert c["inventaire"] == ["item:Couteau_de_chasse"]


def test_deux_mains_ne_deloge_rien():
	c = _perso(["item:Arc_court"], main_gauche="item:Dague")
	assert equiper_au_depart(c, _resoudre) == []
	assert c["inventaire"] == ["item:Arc_court"]


def test_restriction_insuffisante_reste_au_sac():
	c = _perso(["item:Masse_lourde"], F=30)
	assert equiper_au_depart(c, _resoudre) == []
	assert c["inventaire"] == ["item:Masse_lourde"]
	c = _perso(["item:Masse_lourde"], F=40)
	assert equiper_au_depart(c, _resoudre) == ["main_droite"]


def test_non_portable_inconnu_ou_slot_absent_restent_au_sac():
	c = _perso(["item:Potion", "item:Inconnu", "item:Bride"])
	assert equiper_au_depart(c, _resoudre) == []
	assert c["inventaire"] == ["item:Potion", "item:Inconnu", "item:Bride"]


def test_slot_occupe_jamais_deloge():
	c = _perso(["item:Hache_de_guerre"], main_droite="item:Lame_courte")
	assert equiper_au_depart(c, _resoudre) == []
	assert c["slots"]["main_droite"] == "item:Lame_courte"
