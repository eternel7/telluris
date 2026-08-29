# tests/test_combat_localisation.py
# Localisation des touches : un d100 décide OÙ le coup porte, et seuls les PA de la pièce
# couvrant cette zone s'appliquent — plus ceux qui protègent partout (armure naturelle,
# bouclier). Tête 01-07, Épaules 08-15, Torse 16-50, Bras 51-73, Jambes 74-89, Pieds 90-100.

from models import character_stats
from models.character_stats import BaseStats, EquipmentBonus, compute_derived_stats
from utils import characters, combat


# ── La table ─────────────────────────────────────────────────────────────────────────

def test_la_table_couvre_1_a_100_sans_trou():
	"""Bornes hautes cumulées : la dernière vaut 100 et chaque tranche est non vide —
	une table trouée enverrait certains jets dans le vide."""
	table = sorted(character_stats.LOCALISATION_TOUCHES.values())
	assert table[-1] == 100
	assert table == sorted(set(table))          # pas deux zones sur la même borne
	assert all(b > 0 for b in table)


def test_les_zones_correspondent_aux_tranches_annoncees():
	assert character_stats.LOCALISATION_TOUCHES == {
		"tete": 7, "epaules": 15, "torse": 50, "bras": 73, "jambes": 89, "pieds": 100,
	}


# ── Le tirage ────────────────────────────────────────────────────────────────────────

def test_tirage_aux_bornes_de_chaque_tranche():
	attendu = [(1, "tete"), (7, "tete"), (8, "epaules"), (15, "epaules"),
			   (16, "torse"), (50, "torse"), (51, "bras"), (73, "bras"),
			   (74, "jambes"), (89, "jambes"), (90, "pieds"), (100, "pieds")]
	for roll, zone in attendu:
		assert combat.tirer_localisation(lambda a, b: roll) == zone, roll


def test_table_vide_desactive_la_mecanique(monkeypatch):
	"""Vider la world-var doit rendre le comportement d'AVANT, pas planter."""
	monkeypatch.setattr(character_stats, "LOCALISATION_TOUCHES", {})
	assert combat.tirer_localisation(lambda a, b: 42) is None


# ── Les PA opposés ───────────────────────────────────────────────────────────────────

# Total 58 = 13 de global (armure naturelle + bouclier) + 45 ventilés (5+8+17+4+6+5).
DEFENSEUR = {"nom": "Chevalier", "pa": 58,
			 "pa_zones": {"tete": 5, "epaules": 8, "torse": 17, "bras": 4,
						  "jambes": 6, "pieds": 5}}


def test_pa_par_zone_ajoute_le_global():
	assert combat.pa_de_zone(DEFENSEUR, "torse") == 30      # 13 + 17
	assert combat.pa_de_zone(DEFENSEUR, "tete") == 18       # 13 + 5
	assert combat.pa_de_zone(DEFENSEUR, "bras") == 17       # 13 + 4


def test_zone_nue_ne_laisse_que_le_global():
	nu = {"pa": 13, "pa_zones": {"torse": 0}}
	assert combat.pa_de_zone(nu, "torse") == 13
	assert combat.pa_de_zone(nu, "tete") == 13


def test_snapshot_sans_ventilation_garde_le_comportement_d_avant():
	"""⚠️ Aucune migration : un combat déjà en base, un monstre ou l'étalon des
	potentiels n'ont pas de `pa_zones` → tout est global, le total agrégé s'applique."""
	for ancien in ({"pa": 58}, {"pa": 58, "pa_zones": {}}):
		assert combat.pa_de_zone(ancien, "torse") == 58
		assert combat.pa_de_zone(ancien, None) == 58


def test_un_pa_surcharge_deplace_la_part_globale():
	"""⚠️ Le global est DÉRIVÉ de `pa` − Σ zones : forcer `pa` (stats forcées du
	simulateur, snapshots bricolés par les tests) doit rester cohérent. Deux champs
	indépendants auraient ignoré la surcharge en silence."""
	force = {**DEFENSEUR, "pa": 70}          # +12 sur le total → +12 de global
	assert combat.pa_de_zone(force, "torse") == 70 - 45 + 17


def test_zone_absente_donne_l_esperance_ponderee():
	"""C'est ce que consomment les ESTIMATIONS (score du simulateur, potentiels) : elles
	doivent rester déterministes, donc pas de tirage — l'espérance exacte des PA."""
	# 0.07×5 + 0.08×8 + 0.35×17 + 0.23×4 + 0.16×6 + 0.11×5 = 9.37, + 13 de global.
	assert round(combat.pa_de_zone(DEFENSEUR, None), 6) == 22.37
	# Elle est bien COMPRISE entre la zone la moins et la mieux protégée.
	assert (combat.pa_de_zone(DEFENSEUR, "bras")
			< combat.pa_de_zone(DEFENSEUR, None)
			< combat.pa_de_zone(DEFENSEUR, "torse"))


def test_un_monstre_a_la_meme_armure_partout():
	"""Armure NATURELLE : uniforme par nature, la localisation ne change rien pour lui."""
	espece = {"_id": "espece:test", "type": "espece", "nom": "Ours",
			  "base_attributes": {k: {"min": v, "max": v} for k, v in
								  {"V": 4, "F": 40, "R": 40, "Ag": 40,
								   "Vol": 10, "Int": 10, "Cha": 0, "Ch": 0}.items()}}
	snap = combat.build_monster_snapshot(espece, None, 0)
	assert snap["pa_zones"] == {}
	assert all(combat.pa_de_zone(snap, z) == snap["pa"]
			   for z in character_stats.LOCALISATION_TOUCHES)


# ── La ventilation depuis l'équipement ───────────────────────────────────────────────

ITEMS = {
	"item:heaume":     {"_id": "item:heaume", "nom": "Heaume", "bonus_pa": 5},
	"item:cotte":      {"_id": "item:cotte", "nom": "Cotte", "bonus_pa": 17},
	"item:gantelets":  {"_id": "item:gantelets", "nom": "Gantelets", "bonus_pa": 4},
	"item:bouclier":   {"_id": "item:bouclier", "nom": "Bouclier", "bonus_pa": 11},
	"item:collier":    {"_id": "item:collier", "nom": "Collier", "bonus_pa": 2},
}


def _bonus(monkeypatch, slots):
	monkeypatch.setattr(characters, "get_doc", lambda i: ITEMS.get(i))
	return characters.recompute_equipment_bonus(slots)


def test_ventilation_par_slot(monkeypatch):
	bonus = _bonus(monkeypatch, {
		"tete": "item:heaume", "torse": "item:cotte", "mains": "item:gantelets",
		"main_gauche": "item:bouclier", "cou": "item:collier", "pieds": None,
	})
	# ⚠️ « bras » est le slot `mains` : ce sont les gantelets qui couvrent cette zone.
	assert bonus.pa_zones == {"tete": 5, "torse": 17, "bras": 4}
	# Bouclier et collier ne couvrent aucune zone : ils protègent PARTOUT.
	assert bonus.pa_hors_zone == 13
	assert bonus.pa == 39


def test_invariant_du_total(monkeypatch):
	"""Un PA ne doit jamais disparaître de la ventilation — c'est ce qui casserait le
	jour où un slot est ajouté (les épaules l'ont été)."""
	bonus = _bonus(monkeypatch, {
		"tete": "item:heaume", "torse": "item:cotte", "mains": "item:gantelets",
		"main_gauche": "item:bouclier", "cou": "item:collier",
	})
	assert bonus.pa == bonus.pa_hors_zone + sum(bonus.pa_zones.values())


def test_les_derivees_separent_global_et_zones():
	equip = EquipmentBonus(pa=39, pa_zones={"tete": 5, "torse": 17, "bras": 4},
						   pa_hors_zone=13)
	base = BaseStats(v=5, f=40, r=40, ag=30, vol=20, int_=20, cha=10, ch=10)
	d = compute_derived_stats(base, niveau=1, equipment=equip)
	assert d.pa == 2 + 39                       # total, inchangé (R//20 = 2)
	assert d.pa_global == 2 + 13                # armure naturelle + hors-zone
	assert d.pa_zones == {"tete": 5, "torse": 17, "bras": 4}


# ── Bout en bout ─────────────────────────────────────────────────────────────────────

def test_un_coup_au_torse_fait_moins_de_mal_qu_un_coup_au_pied(monkeypatch):
	monkeypatch.setattr(combat, "roll_dice", lambda n: 40)
	torse = combat.calculer_degats({}, DEFENSEUR, "1D6", 1, "cc", zone="torse")
	pied = combat.calculer_degats({}, DEFENSEUR, "1D6", 1, "cc", zone="pieds")
	assert torse == 40 - 30 and pied == 40 - 18   # 13+17 au torse, 13+5 au pied
	assert torse < pied
	# La magie continue d'ignorer l'armure, où qu'elle frappe.
	assert combat.calculer_degats({}, DEFENSEUR, "1D6", 1, "magique", zone="torse") == 40
