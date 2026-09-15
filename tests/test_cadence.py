"""Plafond de requêtes par IP (`utils/cadence.py`).

Ce qui est verrouillé ici : la fenêtre GLISSE (un quota épuisé se relâche au fil du
temps, il ne se réarme pas d'un bloc), un appel refusé n'allonge PAS la punition,
les seaux sont cloisonnés par adresse, un client sans adresse n'est jamais compté,
et `X-Forwarded-For` n'est lu QUE si `TRUST_PROXY_HOPS` le permet — sinon n'importe
qui s'inventerait une adresse neuve à chaque requête et le plafond ne vaudrait rien.
"""

import pytest

from utils import cadence


@pytest.fixture(autouse=True)
def compteurs_vides():
	cadence.reinitialiser()
	yield
	cadence.reinitialiser()


def test_le_quota_se_remplit_puis_bloque():
	for essai in range(3):
		assert cadence.plafond_atteint("1.2.3.4", now=1000, maximum=3, fenetre=60) is False
	assert cadence.plafond_atteint("1.2.3.4", now=1000, maximum=3, fenetre=60) is True


def test_la_fenetre_glisse():
	for instant in (1000, 1010, 1020):
		assert cadence.plafond_atteint("1.2.3.4", now=instant, maximum=3, fenetre=60) is False
	assert cadence.plafond_atteint("1.2.3.4", now=1030, maximum=3, fenetre=60) is True

	# Le premier appel sort de la fenêtre → une place se libère, une seule.
	assert cadence.plafond_atteint("1.2.3.4", now=1060, maximum=3, fenetre=60) is False
	assert cadence.plafond_atteint("1.2.3.4", now=1060, maximum=3, fenetre=60) is True


def test_un_appel_refuse_n_allonge_pas_la_punition():
	assert cadence.plafond_atteint("1.2.3.4", now=1000, maximum=1, fenetre=60) is False
	for instant in range(1001, 1050):
		assert cadence.plafond_atteint("1.2.3.4", now=instant, maximum=1, fenetre=60) is True
	# L'acharnement n'a rien repoussé : la fenêtre s'écoule depuis le SEUL appel retenu.
	assert cadence.plafond_atteint("1.2.3.4", now=1060, maximum=1, fenetre=60) is False


def test_les_seaux_sont_cloisonnes_par_adresse():
	assert cadence.plafond_atteint("1.2.3.4", now=1000, maximum=1, fenetre=60) is False
	assert cadence.plafond_atteint("1.2.3.4", now=1000, maximum=1, fenetre=60) is True
	assert cadence.plafond_atteint("5.6.7.8", now=1000, maximum=1, fenetre=60) is False


def test_un_client_sans_adresse_n_est_jamais_compte():
	# Un seau « sans adresse » bloquerait tout le monde d'un coup : on ne compte pas.
	for _ in range(50):
		assert cadence.plafond_atteint("", now=1000, maximum=1, fenetre=60) is False


def test_les_adresses_sans_appel_recent_sont_balayees(monkeypatch):
	monkeypatch.setattr(cadence, "MAX_IP_SUIVIES", 5)
	for numero in range(10):
		cadence.plafond_atteint("10.0.0.%d" % numero, now=1000, maximum=3, fenetre=60)
	# Bien après la fenêtre, une nouvelle adresse déclenche le balayage des anciennes.
	cadence.plafond_atteint("10.0.1.1", now=9000, maximum=3, fenetre=60)
	assert len(cadence._appels) == 1


def test_sans_proxy_de_confiance_l_entete_est_ignoree(monkeypatch):
	monkeypatch.delenv("TRUST_PROXY_HOPS", raising=False)
	# ⚠️ Le cœur du dispositif : un en-tête cru sur parole donnerait à chacun une
	# adresse neuve par requête, et le plafond ne compterait plus rien.
	assert cadence.ip_du_client("172.18.0.2", "203.0.113.7") == "172.18.0.2"
	assert cadence.ip_du_client("172.18.0.2", "je, me, forge, une, adresse") == "172.18.0.2"


def test_avec_proxy_de_confiance_on_lit_le_dernier_maillon(monkeypatch):
	monkeypatch.setenv("TRUST_PROXY_HOPS", "1")
	# Le dernier maillon est le seul que le proxy ait écrit lui-même ; ceux d'avant
	# viennent du client.
	assert cadence.ip_du_client("172.18.0.2", "invente, 203.0.113.7") == "203.0.113.7"
	assert cadence.ip_du_client("172.18.0.2", "") == "172.18.0.2"

	monkeypatch.setenv("TRUST_PROXY_HOPS", "2")
	assert cadence.ip_du_client("172.18.0.2", "203.0.113.7, 10.1.1.1") == "203.0.113.7"
	# Moins de maillons que de sauts annoncés : on retombe sur la socket plutôt que
	# de prendre au hasard ce que le client a bien voulu écrire.
	assert cadence.ip_du_client("172.18.0.2", "203.0.113.7") == "172.18.0.2"


def test_un_trust_proxy_hops_illisible_vaut_zero(monkeypatch):
	monkeypatch.setenv("TRUST_PROXY_HOPS", "oui")
	assert cadence.hops_de_confiance() == 0
	assert cadence.ip_du_client("172.18.0.2", "203.0.113.7") == "172.18.0.2"

	monkeypatch.setenv("TRUST_PROXY_HOPS", "-3")
	assert cadence.hops_de_confiance() == 0
