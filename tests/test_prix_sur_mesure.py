"""Prix du sur-mesure — dev/audit_economy.py §7 et la rareté cohérente des matières.

Le trou repéré au dump du 02/10 : la `valeur` d'une variante était figée sur le DEVIS de son
premier client. 33 variantes sur 35 se revendaient plus cher qu'elles ne coûtaient à commander
(une calotte : 441 000 cu commandée, 8,1 M revendue), deux sous leur coût de revient. Et
l'adamantite, « peu commune » à 20 or, rendait une pièce légendaire.

Le moteur est injecté : ces tests ne branchent pas `db.config` sur un dump.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dev.audit_economy import variantes_mal_cotees  # noqa: E402
from models import character_stats  # noqa: E402
from utils import fabrication  # noqa: E402


BASE = {"_id": "item:piece", "type": "item", "nom": "Pièce"}
LINGOT = {"_id": "item:lingot", "type": "item", "rarete": "peu_commun",
		  "fabrication": {"nom": "en lingot", "modificateurs": {"rarete": "legendaire"}}}


def _variante(valeur):
	return {"_id": "item:piece_abcd1234", "type": "item", "valeur": valeur,
			"fabrication": {"base_item": "item:piece", "matieres": [{"item": "item:lingot", "quantite": 1}]}}


def _audit(valeur):
	# Plancher de commande 1 200, haut de l'objet de base 3 000 ; la fourchette se lit telle quelle.
	return variantes_mal_cotees(
		[BASE, LINGOT, _variante(valeur)],
		prix_variante=lambda b, m: _KW,
		prix_range=lambda d, i: (d["valeur"][0]["cu"], d["valeur"][1]["cu"]))


_KW = {"plancher_cuivre": 1_200, "haut_base_cuivre": 3_000, "haut_matieres_cuivre": 2_000,
	   "matieres_distinctes": 1}


def test_variante_dans_sa_fourchette_nest_pas_signalee():
	assert _audit([{"cu": 1_200}, {"cu": 6_000}]) == []


def test_bas_au_dessus_du_plancher_de_commande_est_un_arbitrage():
	# Le rachat (toujours en bande, ≤ bas) rapporterait plus que la commande n'a coûté.
	assert [l["defaut"] for l in _audit([{"cu": 1_201}, {"cu": 6_000}])] == ["arbitrage"]


def test_bas_sous_le_plancher_est_une_perte():
	assert [l["defaut"] for l in _audit([{"cu": 1_199}, {"cu": 6_000}])] == ["perte"]


def test_haut_sous_celui_du_base_est_signale():
	# La dague façonnée de l'Arsenal, 08/11 : moins chère en rayon que la dague simple.
	assert [l["defaut"] for l in _audit([{"cu": 1_200}, {"cu": 2_999}])] == ["sous_base"]


def test_variante_a_matiere_absente_est_ignoree():
	docs = [BASE, _variante([{"cu": 1}, {"cu": 9_999_999}])]   # pas de doc lingot
	assert variantes_mal_cotees(docs, prix_variante=None, prix_range=None) == []


def test_une_variante_ecrite_par_valeur_variante_nest_jamais_signalee():
	# Ce qu'écrit le moteur passe le contrôle de l'audit : les deux règles sont la même.
	valeur = fabrication.valeur_variante(facteur_valeur=fabrication.FACTEUR_MAX, **_KW)
	assert _audit(valeur) == []


# ── Rareté d'une matière ────────────────────────────────────────────────────────

def _echelle():
	return sorted(character_stats.MULT_RARETE, key=lambda r: character_stats.MULT_RARETE[r])


def test_matiere_qui_confere_trop_haut_remonte_a_un_palier_sous_sa_rarete_conferee():
	e = _echelle()
	attendue = e[e.index("legendaire") - fabrication.RARETE_ECART_MAX]
	assert fabrication.rarete_minimale_matiere(LINGOT) == attendue


def test_matiere_coherente_nest_pas_retouchee():
	e = _echelle()
	juste = dict(LINGOT, rarete=e[e.index("legendaire") - fabrication.RARETE_ECART_MAX])
	assert fabrication.rarete_minimale_matiere(juste) is None


def test_matiere_sans_rarete_propre_nest_pas_retouchee():
	# Sans `valeur`, le prix d'un item dépend de sa rareté : on n'en invente pas une.
	assert fabrication.rarete_minimale_matiere({k: v for k, v in LINGOT.items() if k != "rarete"}) is None


def test_matiere_qui_ne_confere_aucune_rarete_nest_pas_retouchee():
	assert fabrication.rarete_minimale_matiere(
		{"rarete": "commun", "fabrication": {"nom": "x", "modificateurs": {"bonus_pm": 1}}}) is None
