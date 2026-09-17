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
from utils import cadence
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


def test_cadence_lue_sur_les_jetons_deja_emis():
	jetons = [{"type": "reset", "user_id": "user:a@b.c", "cree_le": 1000, "expire_le": 4600}]

	assert motdepasse.demande_trop_recente(jetons, now=1000) is True
	assert motdepasse.demande_trop_recente(
		jetons, now=1000 + motdepasse.DELAI_ENTRE_DEMANDES_SECONDES - 1) is True
	# À la seconde près : le délai écoulé, la demande repasse.
	assert motdepasse.demande_trop_recente(
		jetons, now=1000 + motdepasse.DELAI_ENTRE_DEMANDES_SECONDES) is False
	assert motdepasse.demande_trop_recente([], now=1000) is False


def test_jetons_perimes_et_selecteur_du_compte():
	vieux = {"type": "reset", "user_id": "user:a@b.c", "cree_le": 0, "expire_le": 3600}
	recent = {"type": "reset", "user_id": "user:a@b.c", "cree_le": 5000, "expire_le": 8600}

	assert motdepasse.jetons_perimes([vieux, recent], now=5000) == [vieux]
	assert motdepasse.jetons_perimes([vieux, recent], now=0) == []

	# Sélecteur servi par l'index ["type", "user_id"] : rien d'autre n'est demandé.
	vus = []
	motdepasse.jetons_du_compte("user:a@b.c", lambda selector: vus.append(selector) or [])
	assert vus == [{"type": "reset", "user_id": "user:a@b.c"}]
	assert motdepasse.jetons_du_compte("", lambda selector: 1 / 0) == []


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


def test_le_relais_declare_sa_presence(monkeypatch):
	"""⚠️ Ce prédicat ne sert pas qu'à l'envoi : `/auth` s'en sert pour proposer — ou
	NON — le volet « Sceau Secret oublié ? » (`is_reset_mail`, main.read_page_auth).
	Un lien qui promettrait un messager inexistant vaut moins que pas de lien."""
	monkeypatch.delenv("SMTP_HOST", raising=False)
	assert courriel.smtp_est_configure() is False
	monkeypatch.setenv("SMTP_HOST", "smtp.exemple.fr")
	assert courriel.smtp_est_configure() is True
	# Une variable posée mais vide n'est pas un relais.
	monkeypatch.setenv("SMTP_HOST", "")
	assert courriel.smtp_est_configure() is False


def test_destinataire_vide_ne_tente_meme_pas_l_envoi(monkeypatch):
	monkeypatch.setenv("SMTP_HOST", "smtp.exemple.fr")
	assert courriel.envoyer("", "Sujet", "Corps") is False


# ── Endpoints ─────────────────────────────────────────────────────────────────

class _Client:
	def __init__(self, host):
		self.host = host


class _Requete:
	"""Le strict nécessaire : `base_url`, la socket et l'en-tête de proxy."""

	def __init__(self, base_url="http://host-de-l-attaquant/", host="10.0.0.1", forwarded=""):
		self.base_url = base_url
		self.client = _Client(host) if host else None
		self.headers = {"x-forwarded-for": forwarded} if forwarded else {}


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
	monkeypatch.setattr(user_router, "find_docs", lambda selector, *a, **k: [
		d for d in list(docs.values())
		if all(d.get(champ) == valeur for champ, valeur in selector.items())
	])
	monkeypatch.setattr(courriel, "envoyer",
						lambda destinataire, sujet, corps: envois.append((destinataire, sujet, corps)) or True)
	monkeypatch.setenv("APP_BASE_URL", "https://telluris.fr")
	# Le plafond par IP est un état de PROCESS : sans ce vidage, les tests se
	# contamineraient entre eux (tous tapent depuis la même adresse stub).
	cadence.reinitialiser()
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


def test_une_seconde_demande_trop_tot_n_envoie_rien(base):
	docs, envois = base
	asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("a@b.c")))
	reponse = asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("a@b.c")))

	# ⚠️ MÊME réponse : le refus de cadence ne doit pas se distinguer d'un envoi, sinon
	# il redit ce que la réponse unique s'applique à taire.
	assert reponse["message"] == motdepasse.MESSAGE_DEMANDE
	assert len(envois) == 1
	assert len(_jetons(docs)) == 1


def test_le_delai_ecoule_la_demande_repasse(base, monkeypatch):
	docs, envois = base
	asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("a@b.c")))
	# On vieillit le jeton émis plutôt que d'attendre : le délai est la seule variable.
	_jetons(docs)[0]["cree_le"] -= motdepasse.DELAI_ENTRE_DEMANDES_SECONDES

	asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("a@b.c")))
	assert len(envois) == 2
	assert len(_jetons(docs)) == 2


def test_les_jetons_perimes_sont_balayes_a_la_demande_suivante(base):
	docs, _envois = base
	asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("a@b.c")))
	perime = _jetons(docs)[0]
	perime["cree_le"] -= 86400
	perime["expire_le"] -= 86400

	asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("a@b.c")))
	# Le vieux jeton a disparu (aucun tick de fond ne le ferait), le neuf l'a remplacé.
	restants = _jetons(docs)
	assert len(restants) == 1 and restants[0]["_id"] != perime["_id"]


def test_la_cadence_ne_vise_que_le_compte_concerne(base):
	docs, envois = base
	docs["user:d@e.f"] = {"_id": "user:d@e.f", "type": "user", "email": "d@e.f",
						  "username": "Autre",
						  "password": bcrypt.hashpw(b"Ancien1!", bcrypt.gensalt()).decode()}
	asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("a@b.c")))
	asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("d@e.f")))

	assert [envoi[0] for envoi in envois] == ["a@b.c", "d@e.f"]


def test_plafond_par_ip_coupe_avant_toute_lecture(base, monkeypatch):
	docs, envois = base
	monkeypatch.setattr(cadence, "DEMANDES_MAX_PAR_IP", 3)
	lectures = []
	monkeypatch.setattr(user_router, "get_doc",
						lambda doc_id: lectures.append(doc_id) or docs.get(doc_id))

	for _ in range(3):
		asyncio.run(user_router.mot_de_passe_oubli(_Requete(host="10.0.0.9"),
												   _Demande("inconnu@nulle.part")))
	assert len(lectures) == 3

	# Au-delà du quota, un 429 FRANC : il ne dépend que de l'appelant, donc il ne dit
	# rien d'un compte — et la lecture n'a même pas lieu.
	with pytest.raises(HTTPException) as erreur:
		asyncio.run(user_router.mot_de_passe_oubli(_Requete(host="10.0.0.9"), _Demande("a@b.c")))
	assert erreur.value.status_code == 429
	assert len(lectures) == 3
	assert envois == []

	# Le seau est bien PAR adresse : le voisin n'est pas puni.
	asyncio.run(user_router.mot_de_passe_oubli(_Requete(host="10.0.0.10"), _Demande("a@b.c")))
	assert len(envois) == 1


def test_derriere_un_proxy_de_confiance_le_seau_suit_le_vrai_client(base, monkeypatch):
	_docs, envois = base
	monkeypatch.setattr(cadence, "DEMANDES_MAX_PAR_IP", 1)
	monkeypatch.setenv("TRUST_PROXY_HOPS", "1")

	# Même socket (le proxy), deux clients réels : sans la lecture de l'en-tête, le
	# second mangerait le quota du premier.
	asyncio.run(user_router.mot_de_passe_oubli(
		_Requete(host="172.18.0.2", forwarded="203.0.113.7"), _Demande("a@b.c")))
	asyncio.run(user_router.mot_de_passe_oubli(
		_Requete(host="172.18.0.2", forwarded="203.0.113.8"), _Demande("a@b.c")))
	assert len(envois) == 1   # le second est arrêté par la cadence DU COMPTE, pas par l'IP

	with pytest.raises(HTTPException) as erreur:
		asyncio.run(user_router.mot_de_passe_oubli(
			_Requete(host="172.18.0.2", forwarded="203.0.113.7"), _Demande("a@b.c")))
	assert erreur.value.status_code == 429


def test_compte_disparu_entre_la_demande_et_la_gravure(base):
	docs, envois = base
	asyncio.run(user_router.mot_de_passe_oubli(_Requete(), _Demande("a@b.c")))
	jeton = _jeton_du_courriel(envois[0][2])
	del docs["user:a@b.c"]

	with pytest.raises(HTTPException) as erreur:
		asyncio.run(user_router.mot_de_passe_reinitialiser(_Reinit(jeton, "Nouveau1!", "Nouveau1!")))
	assert erreur.value.status_code == 400


# ── Inscription ───────────────────────────────────────────────────────────────
# La règle du sceau a UNE source (`verifier_force`) : l'inscription annonçait
# « 8 caractères, 1 majuscule, 1 chiffre, 1 symbole » dans son champ sans rien vérifier.

class _Inscription:
	def __init__(self, email, password, password_again, username="Novice"):
		self.email = email
		self.username = username
		self.password = password
		self.password_again = password_again


def test_inscription_refuse_un_sceau_hors_regle(base):
	docs, _envois = base
	for faible in ("Court1!", "aventure1!", "Aventuree!", "Aventure11"):
		with pytest.raises(HTTPException) as erreur:
			asyncio.run(user_router.register_user(_Inscription("neuf@b.c", faible, faible), None))
		assert erreur.value.status_code == 400
		assert "user:neuf@b.c" not in docs


def test_inscription_refuse_toujours_deux_saisies_differentes(base):
	_docs, _envois = base
	with pytest.raises(HTTPException) as erreur:
		asyncio.run(user_router.register_user(_Inscription("neuf@b.c", "Aventure1!", "Aventure2!"), None))
	assert erreur.value.detail == "Les mots de passe ne correspondent pas"


def test_inscription_accepte_un_sceau_conforme(base):
	docs, _envois = base
	reponse = asyncio.run(user_router.register_user(_Inscription("neuf@b.c", "Aventure1!", "Aventure1!"), None))

	assert reponse.status_code == 200
	assert bcrypt.checkpw(b"Aventure1!", docs["user:neuf@b.c"]["password"].encode())


def test_le_compte_deja_pris_prime_sur_la_regle(base):
	"""Un sceau faible sur une adresse DÉJÀ inscrite rend toujours « existe déjà » :
	sinon le message de force deviendrait un moyen de tester des adresses."""
	_docs, _envois = base
	with pytest.raises(HTTPException) as erreur:
		asyncio.run(user_router.register_user(_Inscription("a@b.c", "faible", "faible"), None))
	assert erreur.value.detail == "L'utilisateur existe déjà"
