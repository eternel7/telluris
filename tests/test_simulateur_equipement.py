# tests/test_simulateur_equipement.py
# Équiper une espèce HUMANOÏDE dans le banc d'essai : PA ventilés par zone, armes qui
# donnent leurs modes d'attaque, restrictions refusées comme en jeu. Rien n'est écrit en
# base et le moteur n'est pas modifié — on habille le snapshot avec ses propres helpers.

import pytest

from utils import characters, combat, simulateur

ORC = {"_id": "espece:orc", "type": "espece", "nom": "Orc", "tags": ["humanoide"],
	   "base_attributes": {k: {"min": v, "max": v} for k, v in
						   {"V": 4, "F": 40, "R": 40, "Ag": 30,
							"Vol": 20, "Int": 15, "Cha": 10, "Ch": 10}.items()}}
LOUP = {"_id": "espece:loup", "type": "espece", "nom": "Loup", "tags": ["predateur"],
		"base_attributes": {k: {"min": v, "max": v} for k, v in
							{"V": 5, "F": 30, "R": 25, "Ag": 40,
							 "Vol": 10, "Int": 5, "Cha": 0, "Ch": 0}.items()}}

ITEMS = {
	"item:cotte":    {"nom": "Cotte", "categorie": "armure", "slots": ["torse"], "bonus_pa": 17},
	"item:heaume":   {"nom": "Heaume", "categorie": "armure", "slots": ["tete"], "bonus_pa": 5},
	"item:gantelets": {"nom": "Gantelets", "categorie": "armure", "slots": ["mains"], "bonus_pa": 4},
	"item:bouclier": {"nom": "Bouclier", "categorie": "armure", "slots": ["main_gauche"], "bonus_pa": 11},
	"item:hache2m":  {"nom": "Hache lourde", "categorie": "arme", "slots": ["main_droite"],
					  "deux_mains": True, "portee": 1, "bonus_degats": 4},
	"item:arc":      {"nom": "Arc court", "categorie": "arme", "slots": ["main_droite"],
					  "tags": ["tir"], "portee": 8, "bonus_degats": 2},
	"item:plate":    {"nom": "Plate", "categorie": "armure", "slots": ["torse"],
					  "bonus_pa": 25, "restriction": {"F": 60}},
	"item:amulette": {"nom": "Amulette", "categorie": "armure", "slots": ["cou"],
					  "bonus": {"F": 10}},
}
DOCS = {**{k: {"_id": k, "type": "item", **v} for k, v in ITEMS.items()},
		ORC["_id"]: ORC, LOUP["_id"]: LOUP}


@pytest.fixture(autouse=True)
def db(monkeypatch):
	"""⚠️ `recompute_equipment_bonus` et `_weapon_attacks` lisent le `get_doc` GLOBAL de
	leur module (pas d'injection) : les deux doivent être détournés."""
	monkeypatch.setattr(characters, "get_doc", DOCS.get)
	monkeypatch.setattr(combat, "get_doc", DOCS.get)
	return DOCS.get


def _bel(slots=None, espece="espece:orc", **spec):
	return simulateur.construire_belligerant(
		{"type": "espece", "id": espece, **({"slots": slots} if slots else {}), **spec}, DOCS.get)


# ── Refus (fail-closed, comme equip_item en jeu) ─────────────────────────────────────

def test_une_espece_non_humanoide_ne_s_equipe_pas():
	with pytest.raises(ValueError, match="humano"):
		_bel({"torse": "item:cotte"}, espece="espece:loup")


def test_restriction_de_caracteristique_refusee():
	"""L'orc a F 40 : la plate en exige 60. Le serveur refuse, comme `equip_item`."""
	with pytest.raises(ValueError, match="exige"):
		_bel({"torse": "item:plate"})


def test_slot_incompatible_ou_inconnu_refuse():
	with pytest.raises(ValueError, match="ne se porte pas"):
		_bel({"tete": "item:cotte"})
	with pytest.raises(ValueError, match="Emplacement inconnu"):
		_bel({"queue": "item:cotte"})


def test_item_introuvable_refuse():
	with pytest.raises(LookupError):
		_bel({"torse": "item:fantome"})


def test_arme_a_deux_mains_et_bouclier_refuses():
	"""Dans les DEUX sens : l'ordre des clés d'un dict ne dit rien de l'intention."""
	for slots in ({"main_droite": "item:hache2m", "main_gauche": "item:bouclier"},
				  {"main_gauche": "item:bouclier", "main_droite": "item:hache2m"}):
		with pytest.raises(ValueError, match="deux mains"):
			_bel(slots)


# ── Effets de l'équipement ───────────────────────────────────────────────────────────

def test_les_pa_sont_ventiles_par_zone():
	snap = _bel({"torse": "item:cotte", "tete": "item:heaume",
				 "mains": "item:gantelets", "main_gauche": "item:bouclier"})["snapshot_reference"]
	# ⚠️ « bras » est le slot `mains` — même correspondance que la localisation.
	assert snap["pa_zones"] == {"torse": 17, "tete": 5, "bras": 4}
	# Le bouclier ne couvre aucune zone : il protège partout, avec l'armure naturelle.
	nu = _bel()["snapshot_reference"]["pa"]
	assert combat.pa_de_zone(snap, "torse") == nu + 11 + 17
	assert combat.pa_de_zone(snap, "jambes") == nu + 11      # zone nue : le global seul


def test_une_arme_donne_son_mode_et_sa_portee():
	snap = _bel({"main_droite": "item:arc"})["snapshot_reference"]
	modes = {p["mode"]: p for p in snap["attaque_profils"]}
	assert modes["tir"]["portee"] == 8 and modes["tir"]["label"] == "Arc court"
	assert "cac" in modes          # les poings restent toujours disponibles


def test_le_tir_exige_des_derivees_absentes_d_un_monstre_nu():
	"""⚠️ Un snapshot monstre n'a ni `cd` ni `degats_cd` : sans recalcul, une arme de tir
	toucherait avec 0 et blesserait avec une notation vide."""
	# Une espèce nue n'a pas de `cd` : c'est `_normaliser_snapshot` qui le pose à 0.
	assert _bel()["snapshot_reference"]["cd"] == 0
	equipe = _bel({"main_droite": "item:arc"})["snapshot_reference"]
	assert equipe["cd"] > 0 and equipe["degats_cd"]
	assert equipe["toucher_magique"] > 0 and equipe["pm_max"] > 0


def test_un_buff_de_caract_porte_par_un_objet_compte():
	snap = _bel({"cou": "item:amulette"})["snapshot_reference"]
	assert snap["caracts_base"]["F"] == 50          # 40 + 10
	assert snap["degats_cc"] != _bel()["snapshot_reference"]["degats_cc"]


def test_l_equipement_survit_a_la_pose_d_un_effet():
	"""LE piège : `_refresh_snapshot_stats` recompose les dérivées à chaque effet. Sans
	`equipment_bonus` sur le snapshot, l'armure disparaîtrait au premier buff du duel."""
	snap = _bel({"torse": "item:cotte"})["fabrique"]()
	pa_avant = snap["pa"]
	combat._empiler_effet_combat(snap, {"id": "sort:x", "nom": "Vigueur"},
								 {"buffs": {"R": 10}, "duree": 3}, 1)
	assert snap["pa"] >= pa_avant                    # l'armure n'a pas disparu
	assert snap["pa_zones"] == {"torse": 17}


def test_une_espece_nue_est_inchangee():
	"""Aucune régression : sans équipement, le snapshot est celui d'avant la feature."""
	snap = _bel()["snapshot_reference"]
	assert snap["pa_zones"] == {} and "equipment_bonus" not in snap
	assert [p["label"] for p in snap["attaque_profils"]] == ["Attaque naturelle"]
	assert simulateur.equipement_du_snapshot(snap) == {}


def test_le_recap_dit_ce_qui_est_porte():
	bel = _bel({"torse": "item:cotte", "main_droite": "item:hache2m"})
	assert simulateur.equipement_du_snapshot(bel["snapshot_reference"]) == {
		"torse": "item:cotte", "main_droite": "item:hache2m"}


def test_un_orc_equipe_bat_un_orc_nu():
	"""Bout en bout : l'armure et la hache doivent se voir dans le résultat du duel."""
	res = simulateur.simuler_belligerants(
		_bel({"torse": "item:cotte", "tete": "item:heaume", "main_droite": "item:hache2m"}),
		_bel(), distance=1, passes=40)
	assert res["a"]["taux"] > 0.8
