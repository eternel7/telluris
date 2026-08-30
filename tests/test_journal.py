# tests/test_journal.py
# Le CARNET du personnage (onglet 📖) : ce qu'il écrit, et le bestiaire de ce qu'il a croisé.
#
# ⚠️ Ici « journal » = un carnet. Partout ailleurs dans le projet le mot désigne un LOG
# (journal de combat, tampon de `dev_tools`, journal du simulateur) — c'est la première
# confusion que ce fichier documente.
#
# Ce qu'il protège, et qui casse en silence :
#
#   1. **Le bestiaire note ce qu'on a VU, pas ce qu'on a TUÉ.** C'est toute la différence
#      avec `quetes.maj_progress_kills`, qui ne retient que `not vivant` et vit à trois
#      lignes de là dans `finalize_combat`. Copier son filtre ferait disparaître du carnet
#      toute bête qu'on a fuie — sans le moindre symptôme.
#   2. **Une seule règle d'écriture dans tout le jeu.** Papier + encre + plume exigés, papier
#      et encre dépensés : le carnet réutilise `utils/auberge.py` au lieu de la réécrire.
#      Deux règles divergentes, c'est un jour où l'on peut écrire ici et pas là.
#   3. **Le contrôle du texte passe AVANT la dépense** : une page blanche ne coûte pas une
#      feuille (miroir de `test_une_annonce_refusee_pour_texte_vide_NE_DEPENSE_RIEN`).
#   4. **Le libellé du lieu est dénormalisé**, et le doc `lieu:*` — le plus gros du jeu, hors
#      cache de requête — n'est relu que si la paire (espèce, lieu) est neuve.
#
# Tests PURS pour le module ; la partie endpoint monte une base en mémoire, gabarit de
# `tests/test_auberge_endpoints.py`.

import asyncio

import pytest

from models import character_stats
from utils import journal


# ── Monde de test ────────────────────────────────────────────────────────────────
PAPIER = {"_id": "item:Papier", "type": "item", "nom": "Papier",
		  "categorie": "composant", "sous_categorie": "papier"}
ENCRE = {"_id": "item:Encre", "type": "item", "nom": "Encre",
		 "categorie": "composant", "sous_categorie": "encre"}
PLUME = {"_id": "item:Plume_d_oie", "type": "item", "nom": "Plume d'oie",
		 "categorie": "outil", "sous_categorie": "plume_a_ecrire"}
LOUP = {"_id": "espece:loup", "type": "espece", "nom": "Loup",
		"image": "loup_transparent.png", "description": "Prédateur agile chassant en meute.",
		"tags": ["animal", "predateur"],
		"base_attributes": {"F": {"min": 20, "max": 35}}}
OURS = {"_id": "espece:ours", "type": "espece", "nom": "Ours",
		"image": "ours.png", "description": "Masse de muscles et de griffes.",
		"tags": ["animal"], "base_attributes": {"F": {"min": 40, "max": 60}}}

CATALOGUE = {d["_id"]: d for d in (PAPIER, ENCRE, PLUME, LOUP, OURS)}


def _get_doc(doc_id):
	return CATALOGUE.get(doc_id)


def _perso(**kw):
	base = {"_id": "character:moi", "type": "character", "prenom": "Greta", "nom": "Hazgard",
			"lieu": "lieu:auxerre", "inventaire": [], "slots": {}}
	base.update(kw)
	return base


def _monstre(espece_id="espece:loup", vivant=True):
	return {"id": "monstre_0", "espece_id": espece_id, "vivant": vivant}


# ── Le carnet ────────────────────────────────────────────────────────────────────

def test_une_entree_porte_son_heure_son_lieu_et_son_texte():
	perso = _perso()
	e = journal.nouvelle_entree(perso, "Il pleut sur Auxerre.", "Auxerre", now=1000)
	assert e == {"cree_at": 1000, "lieu": "Auxerre", "texte": "Il pleut sur Auxerre."}
	assert perso["journal"] == [e]


def test_le_champ_absent_vaut_carnet_vide():
	"""Convention §4 : aucune migration, un doc déjà en base continue de tourner."""
	assert journal.entrees_de({}) == []
	assert journal.entrees_de(_perso()) == []
	assert journal.bestiaire_de(_perso()) == {}


def test_les_entrees_sont_stockees_dans_l_ordre_D_ECRITURE():
	"""⚠️ Le stockage garde l'ordre naturel : c'est ce qui permet au bornage `[-MAX:]` de
	sacrifier les plus VIEILLES. Stocker à l'envers ferait sauter les plus récentes."""
	perso = _perso()
	journal.nouvelle_entree(perso, "un", now=1)
	journal.nouvelle_entree(perso, "deux", now=2)
	assert [e["texte"] for e in perso["journal"]] == ["un", "deux"]


def test_le_carnet_est_borne_et_ce_sont_les_PLUS_ANCIENNES_qui_sautent(monkeypatch):
	monkeypatch.setattr(character_stats, "JOURNAL_ENTREES_MAX", 3)
	perso = _perso()
	for i in range(5):
		journal.nouvelle_entree(perso, f"page {i}", now=i)
	assert [e["texte"] for e in perso["journal"]] == ["page 2", "page 3", "page 4"]


def test_le_plafond_d_entrees_est_planche_a_1(monkeypatch):
	"""Un carnet qui ne peut rien retenir ne serait pas un carnet."""
	monkeypatch.setattr(character_stats, "JOURNAL_ENTREES_MAX", 0)
	assert journal.entrees_max() == 1
	monkeypatch.setattr(character_stats, "JOURNAL_LONGUEUR_MAX", 0)
	assert journal.longueur_max() == 1


def test_une_entree_sans_lieu_reste_valide():
	"""On peut écrire hors de tout lieu nommé : le champ est vide, pas absent."""
	perso = _perso()
	e = journal.nouvelle_entree(perso, "Nulle part.", now=1)
	assert e["lieu"] == ""


# ── Le bestiaire ─────────────────────────────────────────────────────────────────

def test_une_espece_SURVIVANTE_entre_quand_meme_au_bestiaire():
	"""⚠️ LE test de ce fichier. Le bestiaire note ce qu'on a VU, pas ce qu'on a tué — une
	bête qu'on a fuie a bien été rencontrée. Reprendre le filtre `not vivant` de
	`maj_progress_kills` la ferait disparaître du carnet, sans aucun symptôme."""
	perso = _perso()
	assert journal.noter_rencontres(perso, [_monstre(vivant=True)], "lieu:auxerre", "Auxerre")
	fiche = perso["bestiaire"]["espece:loup"]
	assert fiche["combats"] == 1
	assert fiche["tues"] == 0


def test_tues_ne_compte_que_les_betes_TOMBEES():
	perso = _perso()
	journal.noter_rencontres(perso, [
		_monstre(vivant=False), _monstre(vivant=False), _monstre(vivant=True),
	], "lieu:auxerre", "Auxerre")
	fiche = perso["bestiaire"]["espece:loup"]
	# ⚠️ UN seul incrément de `combats` pour les trois exemplaires : `combats` compte les
	# RENCONTRES, `tues` compte les bêtes.
	assert fiche["combats"] == 1
	assert fiche["tues"] == 2


def test_deux_combats_cumulent_sans_dupliquer_l_espece():
	perso = _perso()
	journal.noter_rencontres(perso, [_monstre(vivant=False)], "lieu:auxerre", "Auxerre")
	journal.noter_rencontres(perso, [_monstre(vivant=True)], "lieu:auxerre", "Auxerre")
	assert list(perso["bestiaire"]) == ["espece:loup"]
	assert perso["bestiaire"]["espece:loup"] == {
		"vu_at": perso["bestiaire"]["espece:loup"]["vu_at"],
		"combats": 2, "tues": 1, "lieux": [{"id": "lieu:auxerre", "label": "Auxerre"}],
	}


def test_la_date_de_PREMIERE_vue_ne_bouge_plus():
	perso = _perso()
	journal.noter_rencontres(perso, [_monstre()], "lieu:auxerre", "Auxerre", now=100)
	journal.noter_rencontres(perso, [_monstre()], "lieu:auxerre", "Auxerre", now=999)
	assert perso["bestiaire"]["espece:loup"]["vu_at"] == 100


def test_un_second_lieu_s_ajoute_sans_doublon():
	perso = _perso()
	journal.noter_rencontres(perso, [_monstre()], "lieu:auxerre", "Auxerre")
	journal.noter_rencontres(perso, [_monstre()], "lieu:foret", "La Forêt")
	journal.noter_rencontres(perso, [_monstre()], "lieu:auxerre", "Auxerre")
	assert perso["bestiaire"]["espece:loup"]["lieux"] == [
		{"id": "lieu:auxerre", "label": "Auxerre"},
		{"id": "lieu:foret", "label": "La Forêt"},
	]


def test_les_lieux_sont_bornes_et_gardent_les_PREMIERS(monkeypatch):
	"""Le carnet dit où l'on a COMMENCÉ à croiser l'espèce ; il n'a pas à devenir un
	journal de bord."""
	monkeypatch.setattr(character_stats, "JOURNAL_BESTIAIRE_LIEUX_MAX", 2)
	perso = _perso()
	for i in range(4):
		journal.noter_rencontres(perso, [_monstre()], f"lieu:l{i}", f"Lieu {i}")
	assert [l["id"] for l in perso["bestiaire"]["espece:loup"]["lieux"]] == ["lieu:l0", "lieu:l1"]


def test_un_monstre_sans_espece_id_est_ignore():
	perso = _perso()
	assert journal.noter_rencontres(perso, [{"id": "monstre_0"}], "lieu:auxerre", "Auxerre") is False
	assert "bestiaire" not in perso


def test_un_combat_sans_monstre_ne_touche_pas_le_doc():
	perso = _perso()
	assert journal.noter_rencontres(perso, [], "lieu:auxerre", "Auxerre") is False
	assert "bestiaire" not in perso


def test_deux_especes_dans_le_meme_combat_entrent_toutes_les_deux():
	perso = _perso()
	journal.noter_rencontres(
		perso, [_monstre("espece:loup"), _monstre("espece:ours")], "lieu:auxerre", "Auxerre")
	assert sorted(perso["bestiaire"]) == ["espece:loup", "espece:ours"]


# ── L'aiguillage qui évite de relire un doc `lieu:*` ──────────────────────────────

def test_lieux_a_nommer_est_vrai_la_PREMIERE_fois_et_faux_ensuite():
	"""⚠️ C'est cet aiguillage qui rend le hook gratuit : les docs `lieu:*` sont les plus
	gros du jeu et sont exclus du cache de requête. Un combat répété au même endroit ne doit
	coûter AUCUNE lecture supplémentaire."""
	perso = _perso()
	monstres = [_monstre()]
	assert journal.lieux_a_nommer(perso, monstres, "lieu:auxerre") is True
	journal.noter_rencontres(perso, monstres, "lieu:auxerre", "Auxerre")
	assert journal.lieux_a_nommer(perso, monstres, "lieu:auxerre") is False
	# Un lieu neuf le redemande.
	assert journal.lieux_a_nommer(perso, monstres, "lieu:foret") is True


def test_lieux_a_nommer_est_faux_quand_le_quota_de_lieux_est_plein(monkeypatch):
	monkeypatch.setattr(character_stats, "JOURNAL_BESTIAIRE_LIEUX_MAX", 1)
	perso = _perso()
	journal.noter_rencontres(perso, [_monstre()], "lieu:auxerre", "Auxerre")
	assert journal.lieux_a_nommer(perso, [_monstre()], "lieu:foret") is False


def test_lieux_a_nommer_est_faux_sans_lieu():
	assert journal.lieux_a_nommer(_perso(), [_monstre()], "") is False


def test_lieu_connu_repond_par_espece_et_par_lieu():
	perso = _perso()
	journal.noter_rencontres(perso, [_monstre("espece:loup")], "lieu:auxerre", "Auxerre")
	assert journal.lieu_connu(perso, "espece:loup", "lieu:auxerre") is True
	assert journal.lieu_connu(perso, "espece:loup", "lieu:foret") is False
	assert journal.lieu_connu(perso, "espece:ours", "lieu:auxerre") is False


# ── Payloads ─────────────────────────────────────────────────────────────────────

def test_le_payload_du_bestiaire_ne_publie_JAMAIS_les_stats():
	"""⚠️ Projection contrôlée (patron `montures._offre_view`), jamais le doc brut : le
	carnet d'un aventurier n'est pas une feuille de stats, et publier `base_attributes`
	livrerait l'équilibrage au joueur."""
	perso = _perso()
	journal.noter_rencontres(perso, [_monstre(vivant=False)], "lieu:auxerre", "Auxerre")
	vue = journal.bestiaire_payload(perso, _get_doc)[0]
	assert "base_attributes" not in vue
	assert vue == {
		"id": "espece:loup", "nom": "Loup", "image": "loup_transparent.png",
		"description": "Prédateur agile chassant en meute.",
		"tags": ["animal", "predateur"], "lieux": ["Auxerre"],
		"combats": 1, "tues": 1, "vu_at": vue["vu_at"],
	}


def test_une_espece_supprimee_en_admin_disparait_du_payload():
	"""On ne réinvente pas un nom : la fiche s'efface, le carnet ne ment pas."""
	perso = _perso()
	journal.noter_rencontres(perso, [_monstre("espece:disparue")], "lieu:auxerre", "Auxerre")
	assert journal.bestiaire_payload(perso, _get_doc) == []


def test_le_bestiaire_relit_le_doc_frais_et_suit_un_renommage():
	"""Les `espece:*` sont dans le cache de requête : les relire est amorti, et une espèce
	renommée en admin se corrige d'elle-même dans tous les carnets."""
	perso = _perso()
	journal.noter_rencontres(perso, [_monstre()], "lieu:auxerre", "Auxerre")
	docs = dict(CATALOGUE)
	docs["espece:loup"] = {**LOUP, "nom": "Loup gris"}
	assert journal.bestiaire_payload(perso, docs.get)[0]["nom"] == "Loup gris"


def test_le_payload_rend_les_entrees_de_la_PLUS_RECENTE_a_la_plus_ancienne():
	"""C'est l'ordre de lecture d'un carnet ; le client ne réordonne rien."""
	perso = _perso()
	journal.nouvelle_entree(perso, "vieille", now=1)
	journal.nouvelle_entree(perso, "fraiche", now=2)
	bloc = journal.journal_payload(perso, _get_doc)
	assert [e["texte"] for e in bloc["entrees"]] == ["fraiche", "vieille"]


def test_le_payload_porte_le_releve_DETAILLE_des_fournitures():
	"""Détail et non booléen : le refus doit pouvoir dire CE QUI manque, sinon le joueur ne
	sait pas quoi aller acheter."""
	perso = _perso(inventaire=["item:Papier"])
	bloc = journal.journal_payload(perso, _get_doc)
	assert bloc["fournitures"] == {"papier": True, "encre": False, "plume_a_ecrire": False}
	assert bloc["longueur_max"] == character_stats.JOURNAL_LONGUEUR_MAX


def test_le_payload_d_un_perso_vierge_ne_casse_pas():
	bloc = journal.journal_payload(_perso(), _get_doc)
	assert bloc["entrees"] == [] and bloc["bestiaire"] == []


# ── L'endpoint POST /api/journal ─────────────────────────────────────────────────

@pytest.fixture
def monde(monkeypatch):
	"""`routers/user` câblé sur une base en mémoire. Renvoie {docs, ru}."""
	from routers import user as ru

	docs = dict(CATALOGUE)
	docs["lieu:auxerre"] = {"_id": "lieu:auxerre", "type": "lieu", "label": "Auxerre"}

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	for mod in (ru, journal):
		monkeypatch.setattr(mod, "get_doc", get_doc_fn, raising=False)
		monkeypatch.setattr(mod, "save_doc", save_doc_fn, raising=False)
	# `auberge` porte la règle des fournitures : il lit les docs items par le getter injecté,
	# mais `resolve_item_ref` de `routers/user` passe par SON `get_doc`, déjà remplacé.
	monkeypatch.setattr(ru, "get_selected_character", lambda _u: docs["character:moi"],
						raising=False)
	return {"docs": docs, "ru": ru}


def _ecrire(monde, character, texte):
	monde["docs"][character["_id"]] = character
	return asyncio.run(monde["ru"].ecrire_journal({"_id": "user:u"}, {"texte": texte}))


def _sac_complet():
	return ["item:Papier", "item:Encre", "item:Plume_d_oie"]


def test_endpoint_ecrit_l_entree_et_DEPENSE_papier_et_encre_mais_PAS_la_plume(monde):
	"""La plume est un `outil` : elle sert et ressert. Le papier et l'encre sont des
	`composant` : ils partent avec la page. La règle ne fait que suivre la donnée — et c'est
	celle de l'auberge, réutilisée telle quelle."""
	perso = _perso(inventaire=_sac_complet())
	data = _ecrire(monde, perso, "Premier jour de route.\n\n\nRien à signaler.")
	assert [e["texte"] for e in data["entrees"]] == ["Premier jour de route.\n\nRien à signaler."]
	assert perso["inventaire"] == ["item:Plume_d_oie"]
	assert data["consomme"] == ["papier", "encre"]
	# ⚠️ Le sac a bougé : le payload doit le republier (Convention §10).
	assert "inventaire_payload" in data


def test_endpoint_consigne_le_LIBELLE_du_lieu_et_non_son_id(monde):
	perso = _perso(inventaire=_sac_complet())
	data = _ecrire(monde, perso, "Ici.")
	assert data["entrees"][0]["lieu"] == "Auxerre"


def test_endpoint_refuse_sans_fournitures_EN_NOMMANT_ce_qui_manque(monde):
	from fastapi import HTTPException
	perso = _perso(inventaire=["item:Papier"])
	with pytest.raises(HTTPException) as e:
		_ecrire(monde, perso, "essai")
	assert e.value.status_code == 422
	assert "encre" in e.value.detail and "plume" in e.value.detail


def test_une_page_blanche_NE_DEPENSE_RIEN(monde):
	"""⚠️ Le contrôle du texte passe AVANT la dépense (miroir exact de la règle de
	l'annonce) : un carnet ouvert par erreur ne coûte pas une feuille."""
	from fastapi import HTTPException
	sac = _sac_complet()
	perso = _perso(inventaire=list(sac))
	with pytest.raises(HTTPException) as e:
		_ecrire(monde, perso, "   \n  \n ")
	assert e.value.status_code == 422
	assert perso["inventaire"] == sac


def test_une_seconde_entree_est_refusee_faute_de_papier(monde):
	"""La dépense a un effet observable : on n'écrit pas deux fois avec une seule feuille."""
	from fastapi import HTTPException
	perso = _perso(inventaire=_sac_complet())
	_ecrire(monde, perso, "premier")
	with pytest.raises(HTTPException) as e:
		_ecrire(monde, perso, "second")
	assert e.value.status_code == 422
	assert "papier" in e.value.detail


def test_le_texte_est_BORNE_a_la_longueur_reglee(monde, monkeypatch):
	monkeypatch.setattr(character_stats, "JOURNAL_LONGUEUR_MAX", 20)
	perso = _perso(inventaire=_sac_complet())
	data = _ecrire(monde, perso, "x" * 500)
	assert len(data["entrees"][0]["texte"]) == 20


def test_le_payload_de_l_endpoint_resynchronise_les_fournitures(monde):
	"""Après l'écriture il ne reste plus de papier : le client doit pouvoir griser son bouton
	sans recharger la page."""
	perso = _perso(inventaire=_sac_complet())
	data = _ecrire(monde, perso, "une page")
	assert data["fournitures"] == {"papier": False, "encre": False, "plume_a_ecrire": True}

# ── Le hook dans finalize_combat ─────────────────────────────────────────────────
# ⚠️ Le bestiaire s'écrit là et PAS dans `start_combat` : celui-ci ne sauve jamais le doc
# personnage, alors que cette zone-ci est déjà sous le garde exactly-once
# `combats_recompenses` et sera persistée par le `_finalize_membre` du principal. Coût zéro.

def _combat_doc(monstres, status="victoire", cid="character:moi"):
	joueur = {
		"id": "joueur_0", "character_id": cid, "nom": "Greta",
		"currentPV": 30, "pv_max": 50, "currentPM": 10, "pm_max": 20,
		"butin_ramasse": [], "effets_actifs": [],
	}
	return {
		"_id": "combat:test", "type": "combat", "user_id": "user:u",
		"character_id": cid, "status": status, "tour": 1,
		"joueurs": [joueur], "monstres": monstres, "log": [], "xp_gagnee": 5,
	}


@pytest.fixture
def combat_db(monkeypatch):
	"""Base en mémoire branchée sur combat + characters (gabarit test_combat_groupe)."""
	from utils import combat as combat_util
	from utils import characters as characters_util

	docs = dict(CATALOGUE)
	docs["lieu:auxerre"] = {"_id": "lieu:auxerre", "type": "lieu", "label": "Auxerre"}
	lectures = []

	def get_doc_fn(doc_id):
		lectures.append(doc_id)
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		return doc

	monkeypatch.setattr(combat_util, "get_doc", get_doc_fn)
	monkeypatch.setattr(combat_util, "save_doc", save_doc_fn)
	monkeypatch.setattr(characters_util, "get_doc", get_doc_fn)
	return {"docs": docs, "lectures": lectures, "combat": combat_util}


def test_finalize_note_le_bestiaire_avec_le_libelle_du_lieu(combat_db):
	perso = _perso(currentPV=30, currentPM=10, xp_total=0, combats_recompenses=[],
				   caracteristiques_current={"V": 5, "F": 30, "R": 30, "Ag": 30,
											 "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
				   vocations_niveaux={}, voc="guerrier", equipment_bonus={},
				   effets_actifs=[], quetes_actives=[])
	combat_db["docs"][perso["_id"]] = perso
	doc = _combat_doc([_monstre(vivant=False)])
	assert combat_db["combat"].finalize_combat(doc) is True
	assert perso["bestiaire"]["espece:loup"] == {
		"vu_at": perso["bestiaire"]["espece:loup"]["vu_at"],
		"combats": 1, "tues": 1,
		"lieux": [{"id": "lieu:auxerre", "label": "Auxerre"}],
	}


def test_finalize_note_AUSSI_une_bete_qu_on_a_FUIE(combat_db):
	"""⚠️ La sémantique « vue » : `status == "fuite"` finalise comme les autres issues, et
	le monstre est encore VIVANT. Sans ce hook-là, une bête qu'on n'a pas su affronter ne
	figurerait jamais au carnet."""
	perso = _perso(currentPV=30, currentPM=10, xp_total=0, combats_recompenses=[],
				   caracteristiques_current={"V": 5, "F": 30, "R": 30, "Ag": 30,
											 "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
				   vocations_niveaux={}, voc="guerrier", equipment_bonus={},
				   effets_actifs=[], quetes_actives=[])
	combat_db["docs"][perso["_id"]] = perso
	doc = _combat_doc([_monstre(vivant=True)], status="fuite")
	assert combat_db["combat"].finalize_combat(doc) is True
	assert perso["bestiaire"]["espece:loup"]["combats"] == 1
	assert perso["bestiaire"]["espece:loup"]["tues"] == 0


def test_finalize_n_ecrit_le_bestiaire_QU_UNE_FOIS(combat_db):
	"""Le garde `combats_recompenses` protège le bestiaire comme il protège l'XP : /play
	re-finalise en filet de sécurité, un second passage ne doit rien compter deux fois."""
	perso = _perso(currentPV=30, currentPM=10, xp_total=0, combats_recompenses=[],
				   caracteristiques_current={"V": 5, "F": 30, "R": 30, "Ag": 30,
											 "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
				   vocations_niveaux={}, voc="guerrier", equipment_bonus={},
				   effets_actifs=[], quetes_actives=[])
	combat_db["docs"][perso["_id"]] = perso
	doc = _combat_doc([_monstre(vivant=False)])
	assert combat_db["combat"].finalize_combat(doc) is True
	assert combat_db["combat"].finalize_combat(doc) is False
	assert perso["bestiaire"]["espece:loup"]["combats"] == 1


def test_finalize_ne_RELIT_PAS_le_doc_lieu_quand_la_paire_est_deja_connue(combat_db):
	"""⚠️ Les `lieu:*` sont les plus GROS documents du jeu et sont exclus du cache de
	requête. Un combat répété au même endroit ne doit coûter AUCUNE lecture de plus — c'est
	tout l'objet de l'aiguillage `lieux_a_nommer`."""
	perso = _perso(currentPV=30, currentPM=10, xp_total=0, combats_recompenses=[],
				   caracteristiques_current={"V": 5, "F": 30, "R": 30, "Ag": 30,
											 "Vol": 20, "Int": 20, "Cha": 20, "Ch": 20},
				   vocations_niveaux={}, voc="guerrier", equipment_bonus={},
				   effets_actifs=[], quetes_actives=[])
	combat_db["docs"][perso["_id"]] = perso

	doc = _combat_doc([_monstre(vivant=False)])
	combat_db["combat"].finalize_combat(doc)
	assert "lieu:auxerre" in combat_db["lectures"]      # 1re fois : on nomme le lieu

	# Second combat, même lieu, même espèce : plus aucune lecture du doc lieu.
	combat_db["lectures"].clear()
	doc2 = dict(doc, _id="combat:test2")
	combat_db["combat"].finalize_combat(doc2)
	assert "lieu:auxerre" not in combat_db["lectures"]
	assert perso["bestiaire"]["espece:loup"]["combats"] == 2
