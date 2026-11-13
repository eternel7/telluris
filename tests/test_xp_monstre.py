"""XP d'un monstre et prix de sa dépouille, tirés de la dangerosité du spécimen (utils/xp_monstre)."""
import pytest

from models import character_stats
from utils import xp_monstre, carcasse, characters, combat


def _cout(niveau):
	return character_stats.xp_seuil_niveau(niveau + 1) - character_stats.xp_seuil_niveau(niveau)


@pytest.fixture(autouse=True)
def _memo_vide():
	xp_monstre._memo_potentiel.clear()
	yield
	xp_monstre._memo_potentiel.clear()


# ── Courbe d'XP ──────────────────────────────────────────────────────────────────

def test_au_plancher_de_chaque_rang_la_part_du_niveau_d_entree():
	part = character_stats.XP_MONSTRE_PART_NIVEAU
	for rang, seuil in character_stats.QUETE_RANG_POTENTIEL_MIN.items():
		niveau = character_stats.QUETE_RANG_NIVEAU_ENTREE[rang]
		assert xp_monstre.xp_de_potentiel(seuil) == round(_cout(niveau) * part)


def test_regle_de_l_auteur_un_monstre_s_vaut_un_dixieme_du_niveau_61():
	# Auteur, 13/11 : « un monstre de rang S rapporte environ 1/10 du plus bas niveau visé ».
	seuil_s = character_stats.QUETE_RANG_POTENTIEL_MIN["S"]
	niveau_s = character_stats.QUETE_RANG_NIVEAU_ENTREE["S"]
	assert xp_monstre.xp_de_potentiel(seuil_s) == pytest.approx(_cout(niveau_s) / 10, rel=0.02)


def test_premier_rang_au_potentiel_zero():
	assert xp_monstre.xp_de_potentiel(0) == round(
		_cout(xp_monstre.NIVEAU_ENTREE_PREMIER_RANG) * character_stats.XP_MONSTRE_PART_NIVEAU)
	assert xp_monstre.xp_de_potentiel(-5) == xp_monstre.xp_de_potentiel(0)
	assert xp_monstre.xp_de_potentiel(None) == xp_monstre.xp_de_potentiel(0)


def test_courbe_croissante_interpolee_et_prolongee():
	pts = xp_monstre.ancres()
	(x0, y0), (x1, y1) = pts[1], pts[2]
	assert xp_monstre.xp_de_potentiel((x0 + x1) / 2) == round((y0 + y1) / 2)
	valeurs = [xp_monstre.xp_de_potentiel(p) for p in range(0, 1500, 7)]
	assert valeurs == sorted(valeurs)
	# Au-delà du dernier plancher, la pente du dernier segment se prolonge.
	(xa, ya), (xb, yb) = pts[-2], pts[-1]
	assert xp_monstre.xp_de_potentiel(xb + (xb - xa)) == round(yb + (yb - ya))


def test_les_ancres_suivent_les_world_vars(monkeypatch):
	monkeypatch.setattr(character_stats, "XP_MONSTRE_PART_NIVEAU", 0.2)
	seuil_s = character_stats.QUETE_RANG_POTENTIEL_MIN["S"]
	assert xp_monstre.xp_de_potentiel(seuil_s) == round(
		_cout(character_stats.QUETE_RANG_NIVEAU_ENTREE["S"]) * 0.2)
	monkeypatch.setitem(character_stats.QUETE_RANG_POTENTIEL_MIN, "S", seuil_s + 100)
	assert dict(xp_monstre.ancres())[seuil_s + 100] == pytest.approx(
		_cout(character_stats.QUETE_RANG_NIVEAU_ENTREE["S"]) * 0.2)


def test_un_rang_sans_plancher_ne_fait_pas_d_ancre(monkeypatch):
	monkeypatch.delitem(character_stats.QUETE_RANG_POTENTIEL_MIN, "C")
	assert len(xp_monstre.ancres()) == len(character_stats.QUETE_RANG_POTENTIEL_MIN) + 1


# ── Potentiel du spécimen ────────────────────────────────────────────────────────

DOCS = {
	"espece:loup": {"_id": "espece:loup", "_rev": "1-a"},
	"profil:novice": {"_id": "profil:novice", "_rev": "1-n"},
	"profil:seigneur": {"_id": "profil:seigneur", "_rev": "1-s"},
	"profil:combattant": {"_id": "profil:combattant", "_rev": "1-c"},
}
MENACE = {None: 40.0, "profil:novice": 25.0, "profil:combattant": 50.0, "profil:seigneur": 400.0}


@pytest.fixture
def menace(monkeypatch):
	from utils import potentiel
	appels = []

	def faux(eid, pid, get):
		appels.append((eid, pid))
		return MENACE[pid], 0.5
	monkeypatch.setattr(potentiel, "potentiel_menace", faux)
	return appels


def test_xp_du_specimen_suit_son_grade(menace):
	novice = xp_monstre.xp_specimen("espece:loup", "profil:novice", DOCS.get)
	seigneur = xp_monstre.xp_specimen("espece:loup", "profil:seigneur", DOCS.get)
	assert novice == xp_monstre.xp_de_potentiel(25.0)
	assert seigneur == xp_monstre.xp_de_potentiel(400.0)


def test_potentiel_memoise_par_revision(menace):
	docs = dict(DOCS)
	xp_monstre.xp_specimen("espece:loup", "profil:novice", docs.get)
	xp_monstre.xp_specimen("espece:loup", "profil:novice", docs.get)
	assert len(menace) == 1
	docs["espece:loup"] = {**docs["espece:loup"], "_rev": "2-b"}   # l'espèce a été retouchée
	xp_monstre.xp_specimen("espece:loup", "profil:novice", docs.get)
	assert len(menace) == 2


def test_espece_inconnue_ou_illisible_tombe_au_bas_de_la_courbe(monkeypatch):
	from utils import potentiel

	def casse(*a):
		raise ValueError("belligérant impossible")
	monkeypatch.setattr(potentiel, "potentiel_menace", casse)
	assert xp_monstre.xp_specimen("espece:absente", None, DOCS.get) == xp_monstre.xp_de_potentiel(0)
	assert xp_monstre.xp_specimen("espece:loup", "profil:novice", DOCS.get) == xp_monstre.xp_de_potentiel(0)


def test_xp_attendue_ponderee_par_les_grades_du_lieu(menace):
	poids = {"profil:novice": 3, "profil:seigneur": 1, "profil:inconnu": 5, "profil:combattant": 0}
	attendu = round((3 * xp_monstre.xp_de_potentiel(25.0) + xp_monstre.xp_de_potentiel(400.0)) / 4)
	assert xp_monstre.xp_attendue("espece:loup", poids, DOCS.get) == attendu
	# Aucun poids exploitable ⇒ grade de référence du rang.
	assert xp_monstre.xp_attendue("espece:loup", {}, DOCS.get) == xp_monstre.xp_de_potentiel(50.0)


# ── Prix de la dépouille ─────────────────────────────────────────────────────────

def test_prix_de_xp_cale_sur_la_reference_et_croissant():
	ref = character_stats.CARCASSE_PRIX_REF_XP
	assert xp_monstre.prix_de_xp(ref) == round(character_stats.CARCASSE_PRIX_REF_CUIVRE)
	prix = [xp_monstre.prix_de_xp(x) for x in range(0, 1200, 25)]
	assert prix == sorted(prix) and min(prix) >= 1


def test_calibration_de_l_auteur():
	# Auteur, 13/11 : rang F médian (59 XP) ≈ 50 cu, rang S médian (726 XP) ≈ 40 000 cu.
	assert xp_monstre.prix_de_xp(59) == pytest.approx(50, rel=0.1)
	assert xp_monstre.prix_de_xp(726) == pytest.approx(40000, rel=0.1)


CARCASSE = {"_id": "item:loup", "source_espece": "espece:loup", "poids": [30, 50], "decoupe_poids_min": 10,
			"decoupe": [{"item": "item:loup_tete", "quantite": 1, "fraction": 0.25},
						{"item": "item:loup_patte", "quantite": 3, "fraction": 0.75}]}
TETE = {"_id": "item:loup_tete", "source_espece": "espece:loup", "portion_de": "item:loup", "poids": [7.5, 12.5]}
PATTE = {"_id": "item:loup_patte", "source_espece": "espece:loup", "portion_de": "item:loup", "poids": [7.5, 12.5]}
ITEMS = {**DOCS, "item:loup": CARCASSE, "item:loup_tete": TETE, "item:loup_patte": PATTE}


def test_prix_depouille_grade_et_poids(menace):
	base = xp_monstre.prix_de_xp(xp_monstre.xp_de_potentiel(400.0))
	assert xp_monstre.prix_depouille(CARCASSE, 40, "profil:seigneur", ITEMS.get) == base
	assert xp_monstre.prix_depouille(CARCASSE, 50, "profil:seigneur", ITEMS.get) == round(base * 50 / 40)
	assert xp_monstre.prix_depouille(CARCASSE, None, "profil:seigneur", ITEMS.get) == base
	# Sans grade : grade de référence du rang (combattant).
	assert xp_monstre.prix_depouille(CARCASSE, 40, None, ITEMS.get) == xp_monstre.prix_de_xp(
		xp_monstre.xp_de_potentiel(50.0))


def test_ce_qui_n_est_pas_une_depouille_n_a_pas_ce_prix():
	assert xp_monstre.prix_depouille({"_id": "item:epee", "poids": 2}, 2, None, ITEMS.get) is None
	ecrit = {**CARCASSE, "valeur": [{"cu": 10}, {"cu": 20}]}
	assert not xp_monstre.est_depouille(ecrit)


def test_decouper_conserve_la_valeur_et_le_grade(menace):
	ref = {"item": "item:loup", "poids": 50, "profil": "profil:seigneur"}
	pieces = carcasse.decouper_ref(ref, CARCASSE)
	assert all(p["profil"] == "profil:seigneur" for p in pieces)
	total = sum(xp_monstre.prix_depouille(ITEMS[p["item"]], p["poids"], p["profil"], ITEMS.get)
				for p in pieces)
	entier = xp_monstre.prix_depouille(CARCASSE, 50, "profil:seigneur", ITEMS.get)
	assert abs(total - entier) <= len(pieces)   # arrondis au cuivre près, pièce par pièce


def test_decouper_sans_grade_n_en_invente_pas():
	pieces = carcasse.decouper_ref({"item": "item:loup", "poids": 50}, CARCASSE)
	assert all("profil" not in p for p in pieces)


def test_le_prix_de_vente_passe_par_la_depouille(menace, monkeypatch):
	monkeypatch.setattr(characters, "get_doc", ITEMS.get)
	ref = {"item": "item:loup", "poids": 50, "profil": "profil:seigneur"}
	assert characters.item_sale_price_cuivre(CARCASSE, ref) == xp_monstre.prix_depouille(
		CARCASSE, 50, "profil:seigneur", ITEMS.get)
	# Réf nue (rayon d'une boutique) : poids moyen, grade de référence.
	assert characters.item_sale_price_cuivre(CARCASSE, "item:loup") == xp_monstre.prix_depouille(
		CARCASSE, None, None, ITEMS.get)


# ── Le grade voyage avec le butin ────────────────────────────────────────────────

def test_ref_de_butin_porte_le_grade():
	ligne = {"item_id": "item:loup", "poids": 42, "profil": "profil:seigneur"}
	assert combat.ref_de_butin(ligne) == {"item": "item:loup", "poids": 42, "profil": "profil:seigneur"}
	assert combat.ref_de_butin({"item_id": "item:epee", "poids": 2}) == {"item": "item:epee", "poids": 2}

