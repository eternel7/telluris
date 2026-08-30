"""Endpoints de la taverne (`routers/auberge.py`) — enchaînement et cycle de vie des docs.

Ce que la logique pure (`tests/test_auberge.py`) ne peut pas couvrir, et qui casse en
silence :

1. **La nuit est une séquence à six temps** (débit → repos → étals → recrues → fin de
   soirée → sauvegardes) dont l'ordre porte du sens : le débit ne doit pas passer si une
   garde échoue plus loin, et le personnage est AUTORITATIF alors que les dizaines de docs
   lieu sont annexes.
2. **La table qu'on vient de quitter doit s'effacer si elle est vide** — et ce test se fait
   sur la liste de messages DÉJÀ amputée de ceux du dormeur, sinon une table qu'il occupait
   seul survivrait à vide, en gardant son `anciens` pour toujours.
3. **Le plafond de messages** s'applique après l'ajout, et sacrifie les plus anciens de
   CETTE table seulement.
4. **Retirer une annonce n'exige aucune propriété**, mais exige que le message appartienne
   à CETTE auberge et au TABLEAU — sinon un id forgé effacerait la conversation d'autrui.

Base en mémoire, gabarit de `tests/test_quetes_endpoints.py`.
"""

import asyncio
import json

import pytest

from models import character_stats
from utils import auberge


AUBERGE = {"_id": "lieu:auberge", "type": "lieu", "categorie": "auberge",
		   "label": "L'Auberge", "lieu_parent": "lieu:ville"}
VILLE = {"_id": "lieu:ville", "type": "lieu", "categorie": "ville"}
ETABLE = {"_id": "lieu:etable", "type": "lieu", "categorie": "etable",
		  "lieu_parent": "lieu:ville"}
PAPIER = {"_id": "item:Papier", "type": "item", "categorie": "composant",
		  "sous_categorie": "papier"}
ENCRE = {"_id": "item:Encre", "type": "item", "categorie": "composant",
		 "sous_categorie": "encre"}
PLUME = {"_id": "item:Plume_d_oie", "type": "item", "categorie": "outil",
		 "sous_categorie": "plume_a_ecrire"}

CARACTS = {"V": 5, "F": 40, "R": 40, "Ag": 40, "Vol": 40, "Int": 40, "Cha": 40, "Ch": 40}


def _perso(**champs):
	base = {
		"_id": "character:u_1", "type": "character", "lieu": "lieu:auberge",
		"prenom": "Greta", "nom": "Hazgard", "cite": "lieu:ville",
		"inventaire": [], "slots": {}, "groupe": [], "montures": [],
		"caracteristiques_current": dict(CARACTS),
		"currentPV": 1, "currentPM": 0,
		"or": 5, "argent": 0, "cuivre": 0,
	}
	base.update(champs)
	return base


@pytest.fixture
def monde(monkeypatch):
	"""`routers/auberge` câblé sur une base en mémoire. Renvoie {docs, supprimes, ra}."""
	from routers import auberge as ra

	docs = {d["_id"]: d for d in (AUBERGE, VILLE, ETABLE, PAPIER, ENCRE, PLUME)}
	supprimes = []

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	def delete_doc_fn(doc):
		docs.pop(doc.get("_id"), None)
		supprimes.append(doc)
		return doc

	def find_docs_fn(selector, fields=None):
		return [d for d in list(docs.values())
				if all(d.get(k) == v for k, v in (selector or {}).items())]

	for mod in (ra, auberge):
		monkeypatch.setattr(mod, "get_doc", get_doc_fn, raising=False)
		monkeypatch.setattr(mod, "save_doc", save_doc_fn, raising=False)
		monkeypatch.setattr(mod, "find_docs", find_docs_fn, raising=False)
		monkeypatch.setattr(mod, "delete_doc", delete_doc_fn, raising=False)
	return {"docs": docs, "supprimes": supprimes, "ra": ra}


def _appel(monde, character, coro_fn, *args):
	"""Joue un endpoint avec ce personnage comme personnage sélectionné."""
	ra = monde["ra"]
	monde["docs"][character["_id"]] = character
	origine = ra.get_selected_character
	try:
		ra.get_selected_character = lambda _u: character
		resultat = coro_fn(*args)
		return asyncio.run(resultat) if asyncio.iscoroutine(resultat) else resultat
	finally:
		ra.get_selected_character = origine


# ── Accès ────────────────────────────────────────────────────────────────────────

def test_la_salle_est_refusee_hors_taverne(monde):
	from fastapi import HTTPException
	char = _perso(lieu="lieu:etable")
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["ra"].salle, None)
	assert e.value.status_code == 403


# ── Tables ───────────────────────────────────────────────────────────────────────

def test_prendre_une_table_puis_y_parler(monde):
	ra = monde["ra"]
	char = _perso()
	data = _appel(monde, char, ra.prendre_table, None, {})
	assert len(data["tables"]) == 1 and data["tables"][0]["assis"] is True
	assert data["ma_table"] == data["tables"][0]["id"]

	data = _appel(monde, char, ra.poster_message, None, {"texte": "  bonsoir  "})
	msgs = data["tables"][0]["messages"]
	assert [m["texte"] for m in msgs] == ["bonsoir"]      # borné : blancs écrasés
	assert msgs[0]["mien"] is True


def test_le_payload_expose_le_portrait_de_l_auteur(monde):
	ra = monde["ra"]
	char = _perso(image="guerriere_h_02.png", portrait_zoom=120,
				  portrait_translate={"x": -12.0, "y": -30.0})
	_appel(monde, char, ra.prendre_table, None, {})
	data = _appel(monde, char, ra.poster_message, None, {"texte": "bonsoir"})
	msg = data["tables"][0]["messages"][0]
	assert msg["auteur_image"] == "guerriere_h_02.png"
	assert msg["auteur_zoom"] == 120
	assert msg["auteur_translate"] == {"x": -12.0, "y": -30.0}


def test_le_payload_N_EXPOSE_JAMAIS_l_id_de_l_auteur(monde):
	"""⚠️ Un `_id` de personnage s'écrit `character:user:<email>_<uuid>` : le publier
	livrerait l'ADRESSE E-MAIL de chaque joueur à toute la salle. Le serveur calcule `mien`
	lui-même et ne transmet jamais l'id."""
	ra = monde["ra"]
	char = _perso(_id="character:user:greta@exemple.fr_abc")
	_appel(monde, char, ra.prendre_table, None, {})
	data = _appel(monde, char, ra.poster_message, None, {"texte": "bonsoir"})
	msg = data["tables"][0]["messages"][0]
	assert "auteur" not in msg and "auteur_id" not in msg
	assert "exemple.fr" not in json.dumps(data)
	assert msg["mien"] is True


def test_un_message_herite_sans_portrait_ne_casse_pas_la_salle(monde):
	"""Un doc écrit avant l'ajout du portrait : le payload doit sortir des valeurs neutres."""
	ra = monde["ra"]
	char = _perso()
	table_id = _appel(monde, char, ra.prendre_table, None, {})["ma_table"]
	monde["docs"]["message:vieux"] = {
		"_id": "message:vieux", "type": "message", "lieu": "lieu:auberge",
		"support": "table", "table": table_id, "auteur": char["_id"],
		"auteur_nom": "Ancien", "texte": "d'avant", "cree_at": 1,
		"expire_at": 4_000_000_000,
	}
	data = _appel(monde, char, ra.salle, None)
	msg = next(m for m in data["tables"][0]["messages"] if m["id"] == "message:vieux")
	assert msg["auteur_image"] == "" and msg["auteur_zoom"] is None


def test_parler_sans_table_est_refuse(monde):
	from fastapi import HTTPException
	with pytest.raises(HTTPException) as e:
		_appel(monde, _perso(), monde["ra"].poster_message, None, {"texte": "ohé"})
	assert e.value.status_code == 409


def test_un_message_vide_est_refuse(monde):
	from fastapi import HTTPException
	ra = monde["ra"]
	char = _perso()
	_appel(monde, char, ra.prendre_table, None, {})
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, ra.poster_message, None, {"texte": "   "})
	assert e.value.status_code == 422


def test_le_plafond_sacrifie_les_plus_anciens(monde):
	ra = monde["ra"]
	char = _perso()
	_appel(monde, char, ra.prendre_table, None, {})
	plafond = int(character_stats.AUBERGE_TABLE_MESSAGES_MAX)
	for i in range(plafond + 3):
		data = _appel(monde, char, ra.poster_message, None, {"texte": f"m{i}"})
	textes = [m["texte"] for m in data["tables"][0]["messages"]]
	assert len(textes) == plafond
	assert textes[0] == "m3" and textes[-1] == f"m{plafond + 2}"


def test_s_asseoir_ailleurs_SUPPRIME_la_table_precedente_devenue_vide(monde):
	"""Il l'occupait seul : elle n'a plus personne, donc elle n'existe plus."""
	ra = monde["ra"]
	char = _perso()
	premiere = _appel(monde, char, ra.prendre_table, None, {})["ma_table"]
	_appel(monde, char, ra.poster_message, None, {"texte": "je change de place"})

	data = _appel(monde, char, ra.prendre_table, None, {})     # une neuve
	assert data["ma_table"] != premiere
	assert [t["id"] for t in data["tables"]] == [data["ma_table"]]
	assert premiere not in monde["docs"]
	# Le message de l'ancienne table est parti avec elle.
	assert [d for d in monde["docs"].values() if d.get("type") == "message"] == []


def test_quitter_une_table_encore_occupee_n_emporte_QUE_ses_messages(monde):
	ra = monde["ra"]
	moi = _perso(_id="character:u_1")
	autre = _perso(_id="character:u_2", prenom="Baal")

	table_id = _appel(monde, moi, ra.prendre_table, None, {})["ma_table"]
	_appel(monde, moi, ra.poster_message, None, {"texte": "je m'en vais"})
	_appel(monde, autre, ra.prendre_table, None, {"table_id": table_id})
	_appel(monde, autre, ra.poster_message, None, {"texte": "je reste"})

	_appel(monde, moi, ra.prendre_table, None, {})             # je change de table
	assert table_id in monde["docs"]                            # l'autre y est encore
	restants = [m["texte"] for m in monde["docs"].values() if m.get("type") == "message"]
	assert restants == ["je reste"]


def test_se_rasseoir_a_SA_table_n_efface_pas_ses_messages(monde):
	"""⚠️ Sans le `sauf` de `quitter_tables`, un second clic sur sa propre table effacerait
	ce qu'on vient d'y dire."""
	ra = monde["ra"]
	char = _perso()
	table_id = _appel(monde, char, ra.prendre_table, None, {})["ma_table"]
	_appel(monde, char, ra.poster_message, None, {"texte": "toujours là"})

	data = _appel(monde, char, ra.prendre_table, None, {"table_id": table_id})
	assert [m["texte"] for m in data["tables"][0]["messages"]] == ["toujours là"]


def test_sortir_de_l_auberge_leve_le_personnage_de_sa_table(monde):
	"""⚠️ Sans ce traitement, rien ne relèverait jamais quelqu'un qui sort simplement de
	l'auberge : les tables ne se videraient donc JAMAIS."""
	ra = monde["ra"]
	char = _perso()
	table_id = _appel(monde, char, ra.prendre_table, None, {})["ma_table"]
	_appel(monde, char, ra.poster_message, None, {"texte": "je sors"})
	assert char["taverne_table"] == table_id

	char["lieu"] = "lieu:ville"                                 # il quitte l'auberge
	change = auberge.traiter_deplacement(char, monde["docs"].get,
										 lambda d: monde["docs"].__setitem__(d["_id"], d) or d,
										 lambda d: monde["docs"].pop(d.get("_id"), None),
										 lambda s, fields=None: [
											 d for d in list(monde["docs"].values())
											 if all(d.get(k) == v for k, v in s.items())])
	assert change is True
	assert "taverne_table" not in char
	assert table_id not in monde["docs"]
	assert [d for d in monde["docs"].values() if d.get("type") == "message"] == []


def test_rester_dans_l_auberge_ne_leve_de_rien(monde):
	"""Coût nul et aucun effet tant qu'on n'a pas changé de lieu."""
	ra = monde["ra"]
	char = _perso()
	table_id = _appel(monde, char, ra.prendre_table, None, {})["ma_table"]
	assert auberge.traiter_deplacement(char, monde["docs"].get, None, None, None) is False
	assert char["taverne_table"] == table_id


def test_un_personnage_jamais_attable_ne_coute_aucune_lecture(monde):
	"""⚠️ Le marqueur absent doit sortir IMMÉDIATEMENT : ce code tourne à chaque déplacement
	de chaque joueur."""
	lectures = []
	def get(doc_id):
		lectures.append(doc_id)
		return monde["docs"].get(doc_id)
	assert auberge.traiter_deplacement(_perso(), get, None, None, None) is False
	assert lectures == []


# ── Tableau d'information ────────────────────────────────────────────────────────

def test_sans_fournitures_l_annonce_est_refusee_en_nommant_ce_qui_manque(monde):
	from fastapi import HTTPException
	char = _perso(inventaire=["item:Papier"])
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["ra"].poser_annonce, None, {"texte": "avis"})
	assert e.value.status_code == 422
	assert "encre" in e.value.detail and "plume" in e.value.detail


def test_l_annonce_DEPENSE_le_papier_et_l_encre_mais_PAS_la_plume(monde):
	"""⚠️ La plume est un `outil` : elle sert et ressert. Le papier et l'encre sont des
	`composant` : ils partent avec l'avis. La règle ne fait que suivre la donnée."""
	ra = monde["ra"]
	char = _perso(inventaire=["item:Papier", "item:Encre", "item:Plume_d_oie"])
	data = _appel(monde, char, ra.poser_annonce, None, {"texte": "Cherche compagnon\n\n\nsérieux"})
	assert [m["texte"] for m in data["tableau"]] == ["Cherche compagnon\n\nsérieux"]
	assert char["inventaire"] == ["item:Plume_d_oie"]
	assert data["consomme"] == ["papier", "encre"]
	# ⚠️ Le sac a bougé : le payload doit le republier, sinon la fiche resterait figée.
	assert "inventaire_payload" in data


def test_une_seconde_annonce_est_refusee_faute_de_papier(monde):
	"""La dépense a un effet observable : on ne peut pas écrire deux fois avec une feuille."""
	from fastapi import HTTPException
	ra = monde["ra"]
	char = _perso(inventaire=["item:Papier", "item:Encre", "item:Plume_d_oie"])
	_appel(monde, char, ra.poser_annonce, None, {"texte": "premier"})
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, ra.poser_annonce, None, {"texte": "second"})
	assert e.value.status_code == 422
	assert "papier" in e.value.detail


def test_deux_annonces_avec_deux_jeux_de_fournitures(monde):
	ra = monde["ra"]
	char = _perso(inventaire=["item:Papier", "item:Papier", "item:Encre",
							  "item:Encre", "item:Plume_d_oie"])
	_appel(monde, char, ra.poser_annonce, None, {"texte": "premier"})
	data = _appel(monde, char, ra.poser_annonce, None, {"texte": "second"})
	assert [m["texte"] for m in data["tableau"]] == ["premier", "second"]
	assert char["inventaire"] == ["item:Plume_d_oie"]


def test_une_annonce_refusee_pour_texte_vide_NE_DEPENSE_RIEN(monde):
	"""⚠️ Le contrôle du texte passe AVANT la dépense : un avis vide ne coûte pas une
	feuille."""
	from fastapi import HTTPException
	ra = monde["ra"]
	sac = ["item:Papier", "item:Encre", "item:Plume_d_oie"]
	char = _perso(inventaire=list(sac))
	with pytest.raises(HTTPException):
		_appel(monde, char, ra.poser_annonce, None, {"texte": "   \n "})
	assert char["inventaire"] == sac


def test_une_annonce_vide_est_refusee(monde):
	from fastapi import HTTPException
	char = _perso(inventaire=["item:Papier", "item:Encre", "item:Plume_d_oie"])
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["ra"].poser_annonce, None, {"texte": "\n \n"})
	assert e.value.status_code == 422


def test_n_IMPORTE_QUI_dans_l_auberge_peut_decrocher_un_avis(monde):
	"""Aucun contrôle de propriété : c'est le geste physique d'un tableau de village."""
	ra = monde["ra"]
	auteur = _perso(_id="character:u_1",
					inventaire=["item:Papier", "item:Encre", "item:Plume_d_oie"])
	data = _appel(monde, auteur, ra.poser_annonce, None, {"texte": "avis"})
	avis_id = data["tableau"][0]["id"]

	passant = _perso(_id="character:u_2", prenom="Baal")
	data = _appel(monde, passant, ra.retirer_annonce, None, {"message_id": avis_id})
	assert data["tableau"] == []
	assert avis_id not in monde["docs"]


def test_on_ne_decroche_pas_un_message_de_TABLE_par_le_tableau(monde):
	"""⚠️ Un id forgé ne doit pas effacer une conversation : le doc doit être une ANNONCE
	de CETTE auberge."""
	from fastapi import HTTPException
	ra = monde["ra"]
	char = _perso()
	_appel(monde, char, ra.prendre_table, None, {})
	data = _appel(monde, char, ra.poster_message, None, {"texte": "secret"})
	msg_id = data["tables"][0]["messages"][0]["id"]

	with pytest.raises(HTTPException) as e:
		_appel(monde, char, ra.retirer_annonce, None, {"message_id": msg_id})
	assert e.value.status_code == 404
	assert msg_id in monde["docs"]


# ── La nuit ──────────────────────────────────────────────────────────────────────

def test_la_nuit_remet_les_points_et_debite_la_chambre(monde):
	ra = monde["ra"]
	char = _perso(currentPV=1, currentPM=0)
	data = _appel(monde, char, ra.passer_la_nuit, None)
	assert char["currentPV"] == data["vitals"]["pv_max"] > 1
	assert char["currentPM"] == data["vitals"]["pm_max"]
	assert data["cout"] == int(character_stats.AUBERGE_NUIT_COUT_CUIVRE)
	assert data["log"]


def test_sans_argent_la_nuit_est_refusee_ET_NE_SOIGNE_PAS(monde):
	"""⚠️ Le débit passe après les gardes : un refus ne doit rien laisser derrière lui."""
	from fastapi import HTTPException
	char = _perso(**{"or": 0, "argent": 0, "cuivre": 0}, currentPV=1)
	with pytest.raises(HTTPException) as e:
		_appel(monde, char, monde["ra"].passer_la_nuit, None)
	assert e.value.status_code == 409
	assert char["currentPV"] == 1


def test_la_nuit_efface_les_messages_du_dormeur_ET_PAS_CEUX_DES_AUTRES(monde):
	ra = monde["ra"]
	dormeur = _perso(_id="character:u_1")
	autre = _perso(_id="character:u_2", prenom="Baal")

	_appel(monde, dormeur, ra.prendre_table, None, {})
	data = _appel(monde, dormeur, ra.poster_message, None, {"texte": "je monte"})
	table_id = data["ma_table"]
	_appel(monde, autre, ra.prendre_table, None, {"table_id": table_id})
	_appel(monde, autre, ra.poster_message, None, {"texte": "bonne nuit"})

	_appel(monde, dormeur, ra.passer_la_nuit, None)

	# La table survit (l'autre y est encore) et ne garde que sa phrase à lui.
	table = monde["docs"][table_id]
	assert table["participants"] == ["character:u_2"]
	assert table["anciens"] == ["character:u_1"]
	restants = [d for d in monde["docs"].values() if d.get("type") == "message"]
	assert [m["texte"] for m in restants] == ["bonne nuit"]


def test_une_table_que_le_dormeur_occupait_SEUL_disparait(monde):
	"""⚠️ Le test d'abandon se fait sur les messages DÉJÀ amputés : sinon la table
	survivrait à vide et garderait son `anciens` pour toujours."""
	ra = monde["ra"]
	char = _perso()
	table_id = _appel(monde, char, ra.prendre_table, None, {})["ma_table"]
	_appel(monde, char, ra.poster_message, None, {"texte": "seul au monde"})

	data = _appel(monde, char, ra.passer_la_nuit, None)
	assert table_id not in monde["docs"]
	assert data["tables"] == []


def test_la_nuit_EPARGNE_le_tableau_d_information(monde):
	ra = monde["ra"]
	char = _perso(inventaire=["item:Papier", "item:Encre", "item:Plume_d_oie"])
	_appel(monde, char, ra.poser_annonce, None, {"texte": "avis durable"})
	data = _appel(monde, char, ra.passer_la_nuit, None)
	assert [m["texte"] for m in data["tableau"]] == ["avis durable"]


def test_apres_la_nuit_on_ne_peut_plus_se_rasseoir_a_SA_table(monde):
	from fastapi import HTTPException
	ra = monde["ra"]
	dormeur = _perso(_id="character:u_1")
	autre = _perso(_id="character:u_2", prenom="Baal")

	table_id = _appel(monde, dormeur, ra.prendre_table, None, {})["ma_table"]
	_appel(monde, autre, ra.prendre_table, None, {"table_id": table_id})   # la garde en vie
	_appel(monde, dormeur, ra.passer_la_nuit, None)

	with pytest.raises(HTTPException) as e:
		_appel(monde, dormeur, ra.prendre_table, None, {"table_id": table_id})
	assert e.value.status_code == 409
	# …mais elle reste ouverte à qui n'y a pas dormi.
	data = _appel(monde, autre, ra.prendre_table, None, {"table_id": table_id})
	assert data["ma_table"] == table_id


def test_la_nuit_relance_les_etals_du_LIEU_PARENT(monde, monkeypatch):
	"""Les magasins de la cité sont tickés `AUBERGE_NUIT_PASSES_ATELIER` fois chacun —
	et l'auberge elle-même n'est pas un magasin."""
	ra = monde["ra"]
	boutique = {"_id": "lieu:forge", "type": "lieu", "categorie": "armurerie",
				"lieu_parent": "lieu:ville", "stock_vente": [{"item": "item:Papier", "qty": 1}]}
	monde["docs"]["lieu:forge"] = boutique

	appels = []
	monkeypatch.setattr(ra, "tick_atelier", lambda doc, rec: appels.append(doc["_id"]) or True)
	monkeypatch.setattr(ra, "lieu_recettes", lambda cat: [])
	monkeypatch.setattr(ra, "appro_leaves_categorie", lambda cat: [])

	data = _appel(monde, _perso(), ra.passer_la_nuit, None)
	assert appels == ["lieu:forge"] * int(character_stats.AUBERGE_NUIT_PASSES_ATELIER)
	assert data["magasins"] == 1


def test_la_nuit_PERIME_les_recrues_avant_de_repeupler(monde, monkeypatch):
	"""⚠️ On périme au lieu de supprimer : c'est ce qui fait traverser `retirer_du_tableau`,
	le chokepoint qui sait qu'un ANCIEN COMPAGNON repasse `parti` au lieu d'être détruit."""
	ra = monde["ra"]
	guilde = {"_id": "lieu:guilde", "type": "lieu", "categorie": "guilde_aventurier",
			  "lieu_parent": "lieu:ville"}
	monde["docs"]["lieu:guilde"] = guilde
	recrue = {"_id": "aventurier:vieille", "type": "aventurier", "statut": "offert",
			  "giver": "lieu:guilde", "expire_at": 4_000_000_000}
	monde["docs"]["aventurier:vieille"] = recrue

	monkeypatch.setattr(ra.recrutement, "recrues_du_giver", lambda gid: [recrue])
	remplissages = []
	monkeypatch.setattr(ra.recrutement, "remplir_tableau_recrues",
						lambda doc, char: remplissages.append(doc["_id"]) or [])

	_appel(monde, _perso(), ra.passer_la_nuit, None)
	assert remplissages == ["lieu:guilde"]
	assert recrue["expire_at"] < auberge.now_epoch()      # périmée AVANT le remplissage
