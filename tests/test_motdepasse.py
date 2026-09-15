"""Sceau Secret oublié — jeton de réinitialisation (`utils/motdepasse.py`) et ses deux
endpoints (`routers/user.py`).

Ce qui est verrouillé ici, parce que c'est exactement ce qui se casse en silence :
le jeton n'existe JAMAIS en clair en base, un lien périmé ou déjà consommé ne vaut
plus rien, une saisie refusée ne consomme PAS le lien, la demande répond la MÊME
chose que l'adresse existe ou non, et le lien du courriel se bâtit sur `APP_BASE_URL`
et non sur l'en-tête `Host` fourni par le client.

Base en mémoire, patron de `tests/test_recrutement_endpoints.py` : `get_doc`/`save_doc`/
`delete_doc` patchés sur le router, endpoints `async` appelés par `asyncio.run`.
"""

import asyncio

import bcrypt
import pytest
from fastapi import HTTPException

from routers import user as user_router
from utils import courriel
from utils import motdepasse


# ── Module pur ────────────────────────────────────────────────────────────────

def test_le_jeton_clair_n_est_jamais_stocke():
	jeton, doc = motdepasse.nouveau_jeton("user:a@b.c", now=1000, jeton_fn=lambda: "secret-du-lien")
	assert jeton == "secret-du-lien"
	assert jeton not in repr(doc)
	assert doc["_id"] == "reset:" + motdepasse.empreinte(jeton)
	assert doc["type"] == "reset"
	assert doc["user_id"] == "user:a@b.c"
	assert doc["cree_le"] == 1000
	assert doc["expire_le"] == 1000 + motdepasse.DUREE_JETON_MINUTES * 60


def test_deux_demandes_donnent_deux_jetons_differents():
	premier, _ = motdepasse.nouveau_jeton("user:a@b.c")
	second, _ = motdepasse.nouveau_jeton("user:a@b.c")
	assert premier != second


def test_jeton_utilisable_avant_expiration_puis_plus_rien():
	jeton, doc = motdepasse.nouveau_jeton("user:a@b.c", now=1000, jeton_fn=lambda: "j")
	base = {doc["_id"]: doc}
	get_doc = base.get

	assert motdepasse.jeton_utilisable(jeton, get_doc, now=1000)["user_id"] == "user:a@b.c"
	assert motdepasse.jeton_utilisable(jeton, get_doc, now=doc["expire_le"] - 1)
	# À la seconde d'expiration, pas une de plus : la borne est fermée.
	assert motdepasse.jeton_utilisable(jeton, get_doc, now=doc["expire_le"]) is None
	assert motdepasse.jeton_utilisable(jeton, get_doc, now=doc["expire_le"] + 3600) is None


def test_jeton_inconnu_vide_ou_d_un_autre_type():
	jeton, doc = motdepasse.nouveau_jeton("user:a@b.c", now=1000, jeton_fn=lambda: "j")
	base = {doc["_id"]: doc}

	assert motdepasse.jeton_utilisable("autre", base.get, now=1000) is None
	assert motdepasse.jeton_utilisable("", base.get, now=1000) is None
	assert motdepasse.jeton_utilisable(None, base.get, now=1000) is None
	# Un doc qui n'est pas un jeton (collision d'`_id` forgée) ne passe pas.
	doc["type"] = "user"
	assert motdepasse.jeton_utilisable(jeton, base.get, now=1000) is None


def test_regle_du_nouveau_sceau():
	assert motdepasse.verifier_force("Aventure1!", "Aventure1!") is None
	assert motdepasse.verifier_force("Aventure1!", "Aventure1") == "Les mots de passe ne correspondent pas"
	assert "8 caractères" in motdepasse.verifier_force("Av1!", "Av1!")
	assert "majuscule" in motdepasse.verifier_force("aventure1!", "aventure1!")
	assert "chiffre" in motdepasse.verifier_force("Aventuree!", "Aventuree!")
	assert "symbole" in motdepasse.verifier_force("Aventure11", "Aventure11")


def test_lien_et_corps_du_courriel():
	assert motdepasse.lien_reinitialisation("https://telluris.fr/", "abc") == \
		"https://telluris.fr/reinitialisation?jeton=abc"
	assert motdepasse.lien_reinitialisation("https://telluris.fr", "abc") == \
		"https://telluris.fr/reinitialisation?jeton=abc"

	sujet, corps = motdepasse.courriel_de_reinitialisation("Gwendal", "https://telluris.fr/x")
	assert "Telluris" in sujet
	assert "Gwendal" in corps
	assert "https://telluris.fr/x" in corps
	# Sans nom de joueur (compte créé sans `username`), le message reste adressé.
	_, anonyme = motdepasse.courriel_de_reinitialisation("", "https://telluris.fr/x")
	assert "voyageur" in anonyme


# ── Envoi ─────────────────────────────────────────────────────────────────────

def test_sans_smtp_rien_ne_part_et_l_appelant_le_sait(monkeypatch, caplog):
	monkeypatch.delenv("SMTP_HOST", raising=False)
	with caplog.at_level("WARNING"):
		assert courriel.envoyer("a@b.c", "Sujet", "https://telluris.fr/x") is False
	# Le lien tombe dans le journal du serveur : c'est ce qui rend le parcours
	# jouable sur une instance de développement sans relais.
	assert "https://telluris.fr/x" in caplog.text


def test_destinataire_vide_ne_tente_meme_pas_l_envoi(monkeypatch):
	monkeypatch.setenv("SMTP_HOST", "smtp.exemple.fr")
	assert courriel.envoyer("", "Sujet", "Corps") is False


# ── Endpoints ─────────────────────────────────────────────────────────────────

class _Requete:
	"""Le strict nécessaire : seul `base_url` est lu par l'endpoint."""

	def __init__(self, base_url="http://host-de-l-attaquant/"):
		self.base_url = base_url


class _Demande:
	def __init__(self, email):
		self.email = email


class _Reinit:
	def __init__(self, jeton, password, password_again):
		self.jeton = jeton
		self.password = password
		self.password_again = password_again


@pytest.fixture
def base(monkeypatch):
	"""Base en mémoire + courriels interceptés."""
	docs = {
		"user:a@b.c": {"_id": "user:a@b.c", "type": "user", "email": "a@b.c",
					   "username": "Gwendal",
					   "password": bcrypt.hashpw(b"Ancien1!", bcrypt.gensalt()).decode()},
	}
	envois = []

	monkeypatch.setattr(user_router, "get_doc", lambda doc_id: docs.get(doc_id))
	monkeypatch.setattr(user_router, "save_doc", lambda doc: docs.__setitem__(doc["_id"], doc) or doc)
	monkeypatch.setattr(user_router, "delete_doc", lambda doc: docs.pop(doc["_id"], None))
	monkeypatch.setattr(courriel, "envoyer",
						lambda destinataire, sujet, corps: envois.append((destinataire, sujet, corps)) or True)
	monkeypatch.setenv("APP_BASE_URL", "https://telluris.fr")
	return docs, envois


def _jetons(docs):
	return [d for d in docs.values() if d.get("type") == "reset"]


def test_demande_sur_une_adresse_inconnue_ne_laisse_aucune_trace(base):
	docs, envois = base
	reponse = asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("personne@nulle.part")))

	assert reponse["message"] == motdepasse.MESSAGE_DEMANDE
	assert _jetons(docs) == []
	assert envois == []


def test_demande_sur_une_adresse_connue_envoie_le_lien(base):
	docs, envois = base
	reponse = asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("a@b.c")))

	# ⚠️ Message IDENTIQUE au cas inconnu : c'est ce qui empêche l'écran de dire
	# quelles adresses ont un compte.
	assert reponse["message"] == motdepasse.MESSAGE_DEMANDE
	assert len(_jetons(docs)) == 1
	assert len(envois) == 1

	destinataire, _sujet, corps = envois[0]
	assert destinataire == "a@b.c"
	# Le lien se bâtit sur APP_BASE_URL, jamais sur l'en-tête Host de la requête.
	assert "https://telluris.fr/reinitialisation?jeton=" in corps
	assert "host-de-l-attaquant" not in corps


def test_sans_app_base_url_le_lien_retombe_sur_la_requete(base, monkeypatch):
	_docs, envois = base
	monkeypatch.delenv("APP_BASE_URL")
	asyncio.run(user_router.mot_de_passe_oubli(_Requete("https://telluris.fr/"), _Demande("a@b.c")))

	assert "https://telluris.fr/reinitialisation?jeton=" in envois[0][2]


def test_compte_social_sans_adresse_ne_recoit_rien(base):
	docs, envois = base
	docs["user:apple_42"] = {"_id": "user:apple_42", "type": "user", "email": "",
							 "username": "Sans Courriel"}
	asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("apple_42")))

	# Le jeton est bien créé, mais le destinataire est celui du COMPTE : rien ne part
	# vers la chaîne saisie.
	assert len(_jetons(docs)) == 1
	assert envois[0][0] == ""


def _jeton_du_courriel(corps):
	return corps.split("jeton=")[1].split("\n")[0].strip()


def test_cycle_complet_le_lien_ne_vaut_qu_une_fois(base):
	docs, envois = base
	asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("a@b.c")))
	jeton = _jeton_du_courriel(envois[0][2])

	reponse = asyncio.run(user_router.mot_de_passe_reinitialiser(_Reinit(jeton, "Nouveau1!", "Nouveau1!")))
	assert reponse == {"reinitialise": True}
	assert bcrypt.checkpw(b"Nouveau1!", docs["user:a@b.c"]["password"].encode())
	assert not bcrypt.checkpw(b"Ancien1!", docs["user:a@b.c"]["password"].encode())
	# Le jeton est CONSOMMÉ : le même lien rejoué ne rouvre rien.
	assert _jetons(docs) == []

	with pytest.raises(HTTPException) as erreur:
		asyncio.run(user_router.mot_de_passe_reinitialiser(_Reinit(jeton, "Encore11!", "Encore11!")))
	assert erreur.value.status_code == 400


def test_une_saisie_refusee_ne_consomme_pas_le_lien(base):
	docs, envois = base
	asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("a@b.c")))
	jeton = _jeton_du_courriel(envois[0][2])

	with pytest.raises(HTTPException) as erreur:
		asyncio.run(user_router.mot_de_passe_reinitialiser(_Reinit(jeton, "faible", "faible")))
	assert erreur.value.status_code == 400
	assert len(_jetons(docs)) == 1
	assert bcrypt.checkpw(b"Ancien1!", docs["user:a@b.c"]["password"].encode())

	# Le joueur réessaie avec le MÊME lien, et cette fois ça passe.
	assert asyncio.run(user_router.mot_de_passe_reinitialiser(_Reinit(jeton, "Nouveau1!", "Nouveau1!")))
	assert _jetons(docs) == []


def test_jeton_inconnu_refuse_sans_toucher_au_compte(base):
	docs, _envois = base
	with pytest.raises(HTTPException) as erreur:
		asyncio.run(user_router.mot_de_passe_reinitialiser(_Reinit("forge", "Nouveau1!", "Nouveau1!")))
	assert erreur.value.status_code == 400
	assert bcrypt.checkpw(b"Ancien1!", docs["user:a@b.c"]["password"].encode())


def test_compte_disparu_entre_la_demande_et_la_gravure(base):
	docs, envois = base
	asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("a@b.c")))
	jeton = _jeton_du_courriel(envois[0][2])
	del docs["user:a@b.c"]

	with pytest.raises(HTTPException) as erreur:
		asyncio.run(user_router.mot_de_passe_reinitialiser(_Reinit(jeton, "Nouveau1!", "Nouveau1!")))
	assert erreur.value.status_code == 400
