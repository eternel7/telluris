# tests/test_rencontre_groupee.py
# Rencontre GROUPÉE PAR ESPÈCE (`combat.instantiate_groupes`, budget de menace) et ARMURE
# NATURELLE des espèces (`combat.armure_naturelle_espece`, `dev/gen_armure_naturelle.py`).
import copy
import os
import sys

from models.character_stats import BaseStats, EquipmentBonus
from utils import combat, simulateur

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))
import gen_armure_naturelle as gen  # noqa: E402


def _espece(slug, **extra):
	return {"_id": f"espece:{slug}", "nom": slug.capitalize(), "tags": [],
			"base_attributes": {"R": {"min": 40, "max": 60}}, **extra}


class _Rand:
	"""Hasard piloté : `choice` / `choices` prennent l'élément d'index `pick`, `random` rend `r`."""
	def __init__(self, r=0.99, pick=0):
		self.r, self.pick, self.weights = r, pick, []

	def choice(self, seq):
		return seq[self.pick % len(seq)]

	def choices(self, seq, weights=None, k=1):
		self.weights.append(list(weights))
		return [seq[self.pick % len(seq)]]

	def random(self):
		return self.r


def _couts(table):
	return lambda e, p: table[e["_id"]]


# ── Budget de menace ──────────────────────────────────────────────────────────

def test_le_nombre_baisse_quand_la_puissance_monte():
	rat, troll = _espece("rat"), _espece("troll")
	couts = _couts({"espece:rat": 10, "espece:troll": 100})
	nb_rats = len(combat.instantiate_groupes([rat], [], 40, couts, plafond=8, proba_second=0))
	nb_trolls = len(combat.instantiate_groupes([troll], [], 40, couts, plafond=8, proba_second=0))
	assert nb_rats == 4    # 4 × 10 tiennent dans 40
	assert nb_trolls == 1  # trop cher, mais un groupe a toujours son premier spécimen


def test_un_seul_groupe_homogene_sans_second():
	pool = [_espece("loup"), _espece("rat")]
	monstres = combat.instantiate_groupes(pool, [], 100, _couts({"espece:loup": 20, "espece:rat": 5}),
										  plafond=8, proba_second=0, rand=_Rand(pick=0))
	assert {m["espece_id"] for m in monstres} == {"espece:loup"}
	assert len(monstres) == 5
	assert [m["id"] for m in monstres] == [f"monstre_{i}" for i in range(5)]


def test_plafond_respecte():
	monstres = combat.instantiate_groupes([_espece("rat")], [], 1000, _couts({"espece:rat": 1}),
										  plafond=3, proba_second=0)
	assert len(monstres) == 3


def test_second_groupe_depense_le_reste():
	pool = [_espece("gobelin"), _espece("loup")]
	couts = _couts({"espece:gobelin": 30, "espece:loup": 20})
	# r = 0 < proba : second groupe. Gobelins : 3 × 30 = 90 sur 100, reste 10 → au moins un loup.
	monstres = combat.instantiate_groupes(pool, [], 100, couts, plafond=8, proba_second=0.2,
										  rand=_Rand(r=0.0, pick=0))
	assert [m["espece_id"] for m in monstres] == ["espece:gobelin"] * 3 + ["espece:loup"]
	# r au-dessus de la proba : pas de second groupe.
	sans = combat.instantiate_groupes(pool, [], 100, couts, plafond=8, proba_second=0.2,
									  rand=_Rand(r=0.5, pick=0))
	assert {m["espece_id"] for m in sans} == {"espece:gobelin"}


def test_second_groupe_borne_par_le_plafond():
	pool = [_espece("rat"), _espece("loup")]
	monstres = combat.instantiate_groupes(pool, [], 1000, _couts({"espece:rat": 1, "espece:loup": 1}),
										  plafond=4, proba_second=1.0, rand=_Rand(r=0.0))
	assert len(monstres) == 4 and {m["espece_id"] for m in monstres} == {"espece:rat"}


def test_pool_d_une_seule_espece_sans_second_groupe():
	monstres = combat.instantiate_groupes([_espece("loup")], [], 30, _couts({"espece:loup": 20}),
										  plafond=8, proba_second=1.0, rand=_Rand(r=0.0))
	assert len(monstres) == 1


def test_cout_illisible_ne_fait_pas_une_nuee():
	monstres = combat.instantiate_groupes([_espece("x")], [], 500, lambda e, p: None,
										  plafond=8, proba_second=0)
	assert len(monstres) == 1


def test_focalisation_pondere_l_espece_principale():
	pool = [_espece("loup"), _espece("rat")]
	r = _Rand()
	combat.instantiate_groupes(pool, [], 10, _couts({"espece:loup": 5, "espece:rat": 5}),
							   plafond=8, proba_second=0, espece_weights={"espece:loup": 3.0}, rand=r)
	assert r.weights[0] == [3.0, 1.0]


def test_pool_vide():
	assert combat.instantiate_groupes([], [], 100, lambda e, p: 1) == []


def test_cout_mesure_au_grade_tire():
	"""Le coût reçoit le PROFIL tiré : un grade plus haut coûte plus, donc vient moins nombreux."""
	vus = []
	profil = {"_id": "profil:veteran", "niveau": 3}
	combat.instantiate_groupes([_espece("loup")], [profil], 50,
							   lambda e, p: vus.append(p and p["_id"]) or 20, plafond=8, proba_second=0)
	assert vus and set(vus) == {"profil:veteran"}


# ── Armure naturelle ──────────────────────────────────────────────────────────

def test_armure_naturelle_ajoutee_aux_pa():
	sans = combat.build_monster_snapshot(_espece("bete"), None, 0, calculer_xp=False)
	avec = combat.build_monster_snapshot(_espece("bete", armure_naturelle=3), None, 0, calculer_xp=False)
	assert avec["pa"] == sans["pa"] + 3
	assert avec["pa_zones"] == sans["pa_zones"] == {}
	assert avec["armure_naturelle"] == 3
	assert "armure_naturelle" not in sans and "equipment_bonus" not in sans


def test_armure_naturelle_survit_au_recalcul_des_stats():
	snap = combat.build_monster_snapshot(_espece("bete", armure_naturelle=4), None, 0, calculer_xp=False)
	pa = snap["pa"]
	combat._refresh_snapshot_stats(snap)
	assert snap["pa"] == pa


def test_armure_naturelle_gardee_par_le_banc():
	snap = combat.build_monster_snapshot(_espece("bete", armure_naturelle=2), None, 0, calculer_xp=False)
	base = snap["pa"]
	equipe = simulateur._equiper_snapshot(copy.deepcopy(snap), {"cou": "item:inexistant"})
	assert equipe["pa"] == base


def test_armure_naturelle_illisible_vaut_zero():
	assert combat.armure_naturelle_espece({"armure_naturelle": "x"}) == 0
	assert combat.armure_naturelle_espece({"armure_naturelle": -2}) == 0
	assert combat.armure_naturelle_espece({}) == 0


def test_avec_armure_naturelle_garde_l_invariant():
	eq = EquipmentBonus(pa=5, pa_hors_zone=1, pa_zones={"torse": 4})
	combat.avec_armure_naturelle(eq, 3)
	assert eq.pa == eq.pa_hors_zone + sum(eq.pa_zones.values()) == 8


# ── Générateur ────────────────────────────────────────────────────────────────

def test_bareme_par_rang():
	assert [gen.bonus_armure(r, []) for r in ("F", "E", "D", "C", "B", "A", "S", "S+")] == \
		[0, 0, 0] + [gen.BAREME[r] for r in ("C", "B", "A", "S", "S+")]


def test_nature_module_seulement_a_partir_du_rang_c():
	cuirasse, sans_corps = [gen.TAGS_CUIRASSE[0]], [gen.TAGS_SANS_CORPS[0]]
	assert gen.bonus_armure("D", cuirasse) == 0
	assert gen.bonus_armure("B", cuirasse) == gen.BAREME["B"] + 1
	assert gen.bonus_armure("B", sans_corps) == gen.BAREME["B"] - 1
	assert gen.bonus_armure("C", sans_corps) == 0          # jamais sous 0
	assert gen.bonus_armure("B", cuirasse + sans_corps) == gen.BAREME["B"]


def test_delta_idempotent_et_retrait():
	a = _espece("a")
	b = _espece("b", armure_naturelle=gen.BAREME["B"])
	c = _espece("c", armure_naturelle=2)  # rang D : le champ doit partir
	rangs = {a["_id"]: "A", b["_id"]: "B", c["_id"]: "D"}
	sortie = gen.delta([a, b, c], rangs)
	assert [d["_id"] for d in sortie] == [a["_id"], c["_id"]]
	assert sortie[0]["armure_naturelle"] == gen.BAREME["A"]
	assert "armure_naturelle" not in sortie[1]
	assert {k: v for k, v in sortie[0].items() if k != "armure_naturelle"} == a
	# Rejeu sur le résultat : plus rien à importer.
	assert gen.delta([sortie[0], b, sortie[1]], rangs) == []


# ── Composition (`rules:affinites_especes`, utils/composition_rencontre) ──────

from utils import composition_rencontre as compo  # noqa: E402

_P = {n: {"_id": f"profil:p{n}", "niveau": n} for n in (1, 2, 3, 4)}
_MAGE = {"_id": "profil:mage", "niveau": 1, "restriction_tags": ["magique"]}


def _aff(**extra):
	"""Doc de règles minimal : DEFAUTS + ce que le test pose."""
	return {"_id": compo.DOC_ID, **extra}


class _Seq(_Rand):
	"""`choice` / `choices` prennent le PREMIER élément ; `random` rend les valeurs de `rs`
	dans l'ordre (puis la dernière)."""
	def __init__(self, rs):
		super().__init__()
		self.rs = list(rs)

	def random(self):
		return self.rs.pop(0) if len(self.rs) > 1 else self.rs[0]


def test_sans_doc_le_comportement_d_avant():
	pool = [_espece("loup", tags=["ia_meute"])]
	avant = combat.instantiate_groupes(pool, [], 100, _couts({"espece:loup": 20}), plafond=8, proba_second=0)
	apres = combat.instantiate_groupes(pool, [], 100, _couts({"espece:loup": 20}), plafond=8,
									   proba_second=0, affinites=None)
	assert len(avant) == len(apres) == 5


def test_regles_completent_les_defauts():
	r = compo.regles(_aff(formes={"rodeur_max": 3}))
	assert r["formes"]["rodeur_max"] == 3
	assert r["formes"]["meute_min"] == compo.DEFAUTS["formes"]["meute_min"]
	assert compo.regles(None) is None


def test_motif_de_tag_couvre_les_suffixes():
	assert compo.tag_correspond(["ia_embuscade_1"], ["ia_embuscade"])
	assert compo.tag_correspond(["magie_necromancie_8_mage"], ["magie_necromancie"])
	assert not compo.tag_correspond(["ia_embuscadeX"], ["ia_embuscade"])


def test_solitaire_seul_et_grade_releve_par_le_budget():
	dragon = _espece("dragon", tags=["legendaire"])
	pool = [dragon, _espece("kobold")]
	couts = lambda e, p: 10 * p["niveau"]
	# Tiré au niveau 1 (premier), le budget 35 paie jusqu'au niveau 3 (30), pas au 4 (40).
	m = combat.instantiate_groupes(pool, list(_P.values()), 35, couts, plafond=8, proba_second=1.0,
								   affinites=_aff(), rand=_Seq([0.0]))
	assert [(x["espece_id"], x["profil_id"]) for x in m] == [("espece:dragon", "profil:p3")]


def test_meute_jamais_seule_et_chef_rabaisse():
	loup = _espece("loup", tags=["ia_meute"])
	couts = lambda e, p: 10 * p["niveau"]
	# Budget 25 : un chef p2 (20) + un p1 (10) = 30 ne tient pas → le chef descend à p1.
	m = combat.instantiate_groupes([loup], [_P[1], _P[2]], 25, couts, plafond=8, proba_second=0,
								   affinites=_aff(), rand=_Seq([0.99]))
	assert len(m) >= compo.DEFAUTS["formes"]["meute_min"]
	assert m[0]["profil_id"] == "profil:p1"
	# Budget 5 : moins qu'un seul loup, la meute a quand même son minimum.
	m = combat.instantiate_groupes([loup], [_P[1]], 5, couts, plafond=8, proba_second=0,
								   affinites=_aff(), rand=_Seq([0.99]))
	assert len(m) == compo.DEFAUTS["formes"]["meute_min"]


def test_rodeur_plafonne():
	araignee = _espece("araignee", tags=["ia_embuscade_2"])
	m = combat.instantiate_groupes([araignee], [], 1000, _couts({"espece:araignee": 1}), plafond=8,
								   proba_second=0, affinites=_aff())
	assert len(m) == compo.DEFAUTS["formes"]["rodeur_max"]


def test_chef_releve_et_suite_dessous():
	orc = _espece("orc")
	couts = lambda e, p: p["niveau"]
	# random 0.99 → 2 crans : tiré p1 (premier), le chef monte à p3 ; la suite reste sous p3.
	m = combat.instantiate_groupes([orc], list(_P.values()), 20, couts, plafond=4, proba_second=0,
								   affinites=_aff(), rand=_Seq([0.99]))
	assert m[0]["profil_id"] == "profil:p3"
	assert all(int(x["profil_id"][-1]) < 3 for x in m[1:]) and len(m) == 4


def test_roles_repartis_chez_les_humanoides():
	chaman = _espece("chaman", tags=["humanoide", "magique"])
	profils = [_P[1], _MAGE, _P[2]]
	m = combat.instantiate_groupes([chaman], profils, 100, lambda e, p: 1, plafond=4, proba_second=0,
								   affinites=_aff(hierarchie={"chef_crans_max": 1}), rand=_Seq([0.0]))
	roles = [compo.role({"restriction_tags": ["magique"]} if x["profil_id"] == "profil:mage" else {})
			 for x in m]
	assert roles.count("magique") == 2 and roles.count("melee") == 2


def test_bande_prioritaire_sur_le_hasard():
	orc, gob, cerf = _espece("orc"), _espece("gobelin"), _espece("cerf")
	aff = _aff(bandes=[{"id": "horde", "especes": ["espece:orc", "gobelin"]}], diversite_pleine=1)
	# Pool : orc en tête (principale), cerf AVANT le gobelin — seule la bande désigne le gobelin.
	m = combat.instantiate_groupes([orc, cerf, gob], [], 30, _couts({"espece:orc": 20, "espece:gobelin": 5,
																	   "espece:cerf": 5}),
								   plafond=8, proba_second=1.0, affinites=aff, rand=_Seq([0.0]))
	assert {x["espece_id"] for x in m} == {"espece:orc", "espece:gobelin"}


def test_association_par_famille_de_tags_hors_bande():
	r = compo.regles(_aff(familles_tags=[{"id": "morts", "tags": ["undead"]}]))
	zombie, goule, cerf = (_espece("zombie", tags=["undead"]), _espece("goule", tags=["undead"]),
						   _espece("cerf"))
	assert compo.associations(zombie, [cerf, goule], r) == {"famille": [goule]}


def test_maitre_betes_et_necromancien():
	r = compo.regles(_aff(maitre_betes={"maitres_tags": ["humanoide"], "maitres_exclure": ["undead"],
										"betes_tags": ["ia_meute"], "betes_exclure": ["humanoide"],
										"necromanciens_tags": ["magie_necromancie"], "morts_tags": ["undead"]}))
	bandit, loup = _espece("bandit", tags=["humanoide"]), _espece("loup", tags=["ia_meute"])
	gob = _espece("gobelin", tags=["humanoide", "ia_meute"])
	assert compo.associations(bandit, [gob, loup], r) == {"maitre_betes": [loup]}
	liche = _espece("liche", tags=["humanoide", "undead", "magie_necromancie_3"])
	squelette = _espece("squelette", tags=["undead"])
	assert compo.associations(liche, [loup, squelette], r) == {"maitre_betes": [squelette]}


def test_chasse_la_proie_fuit():
	loup, cerf = _espece("loup", tags=["predateur"]), _espece("cerf", tags=["proie"])
	aff = _aff(chasse={"predateurs_tags": ["predateur"], "proies_tags": ["proie"], "fuite_pct": 70},
			   diversite_pleine=1)
	m = combat.instantiate_groupes([loup, cerf], [], 30, _couts({"espece:loup": 20, "espece:cerf": 5}),
								   plafond=8, proba_second=1.0, affinites=aff, rand=_Seq([0.0]))
	proies = [x for x in m if x["espece_id"] == "espece:cerf"]
	assert proies and all(x["ia"]["fuite"] == 70 for x in proies)
	assert all("ia" not in x or not x["ia"].get("fuite") for x in m if x["espece_id"] == "espece:loup")


def test_charognards_peu_nombreux():
	ours, rat = _espece("ours", tags=["predateur"]), _espece("rat", tags=["vermine"])
	aff = _aff(charognards={"suivis_tags": ["predateur"], "tags": ["vermine"], "max": 2}, diversite_pleine=1)
	m = combat.instantiate_groupes([ours, rat], [], 100, _couts({"espece:ours": 60, "espece:rat": 1}),
								   plafond=8, proba_second=1.0, affinites=aff, rand=_Seq([0.0]))
	assert [x["espece_id"] for x in m].count("espece:rat") == 2


def test_solitaire_jamais_en_second_groupe_ni_suivi():
	loup, dragon = _espece("loup"), _espece("dragon", tags=["boss"])
	r = compo.regles(_aff())
	assert compo.candidats_second(loup, [loup, dragon], r) == []
	m = combat.instantiate_groupes([loup, dragon], [], 100, _couts({"espece:loup": 50, "espece:dragon": 1}),
								   plafond=8, proba_second=1.0, affinites=_aff(), rand=_Seq([0.0]))
	assert {x["espece_id"] for x in m} == {"espece:loup"}


def test_proba_second_suit_la_diversite():
	r = compo.regles(_aff(diversite_pleine=3))
	assert compo.proba_second(0.3, 0, r) == 0
	assert abs(compo.proba_second(0.3, 1, r) - 0.1) < 1e-9
	assert compo.proba_second(0.3, 5, r) == 0.3


def test_repli_au_hasard_sans_association():
	a, b = _espece("a"), _espece("b")
	m = combat.instantiate_groupes([a, b], [], 30, _couts({"espece:a": 20, "espece:b": 5}),
								   plafond=8, proba_second=1.0, affinites=_aff(diversite_pleine=1),
								   rand=_Seq([0.0]))
	assert "espece:b" in {x["espece_id"] for x in m}


def test_bandes_du_generateur_valides():
	import gen_affinites_especes as gen_aff
	doc = gen_aff.construire()
	ids = {e for b in doc["bandes"] for e in b["especes"]}
	assert gen_aff.controler(doc, ids) == []
	assert gen_aff.controler(doc, ids - {next(iter(ids))}) != []
	assert compo.regles(doc)["diversite_pleine"] == compo.DEFAUTS["diversite_pleine"]
