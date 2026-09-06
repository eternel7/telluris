"""Sanction de réputation d'un renoncement (utils/quetes.py) — logique pure, sans DB.

Renoncer à une quête (abandon volontaire ou délai laissé filer) fâche le donneur ET toute sa
MAISON : les lieux qui partagent sa `sous_categorie` ET son `lieu_parent`. Les dépendances DB
sont injectées (get_doc_fn / save_doc_fn / find_docs_fn), comme dans test_transport.py.
"""

import pytest

from models import character_stats
from utils import marche, quetes, transport


# ── Monde de test ────────────────────────────────────────────────────────────────
# Une guilde éclatée en trois lieux d'une même ville : la réception et le comptoir portent la
# `sous_categorie` (ils sont la maison), la façade non (extérieur inerte). Une boucherie partage
# leur `lieu_parent` — c'est le piège que la conjonction doit écarter. Une seconde guilde, dans
# une autre ville, porte la MÊME `sous_categorie` : le `lieu_parent` doit l'écarter à son tour.

RECEPTION = {
	"_id": "lieu:bastion_interieur", "type": "lieu", "label": "Le Bastion - réception",
	"categorie": "guilde_aventurier", "sous_categorie": "guilde_aventurier",
	"lieu_parent": "lieu:auxerre",
}
COMPTOIR = {
	"_id": "lieu:bastion_comptoir", "type": "lieu", "label": "Le comptoir du Bastion",
	"categorie": "guilde_aventurier_comptoir", "sous_categorie": "guilde_aventurier",
	"lieu_parent": "lieu:auxerre",
}
FACADE = {
	"_id": "lieu:bastion", "type": "lieu", "label": "Le Bastion",
	"categorie": "guilde_aventurier_exterieur",  # pas de `sous_categorie` → hors maison
	"lieu_parent": "lieu:auxerre",
}
BOUCHERIE = {
	"_id": "lieu:boucherie", "type": "lieu", "label": "L'Étal",
	"categorie": "boucherie", "lieu_parent": "lieu:auxerre",
}
GUILDE_AILLEURS = {
	"_id": "lieu:guilde_rhemi", "type": "lieu", "label": "La guilde de Rhemi",
	"categorie": "guilde_aventurier", "sous_categorie": "guilde_aventurier",
	"lieu_parent": "lieu:rhemi",  # autre cité
}

MONDE = [RECEPTION, COMPTOIR, FACADE, BOUCHERIE, GUILDE_AILLEURS]


def make_find_docs(monde=MONDE):
	"""find_docs injecté : ne sait filtrer que sur le sélecteur qu'utilise `lieux_solidaires`."""
	def find_docs_fn(selector):
		return [
			d for d in monde
			if d.get("type") == selector.get("type")
			and d.get("lieu_parent") == selector.get("lieu_parent")
		]
	return find_docs_fn


@pytest.fixture
def perso():
	return {"_id": "character:test", "quetes_actives": [], "inventaire": []}


@pytest.fixture
def db():
	"""Base en mémoire : `docs` sert de get_doc, `sauves` enregistre les save_doc."""
	docs, sauves = {}, []

	def get_doc_fn(doc_id):
		return docs.get(doc_id)

	def save_doc_fn(doc):
		docs[doc["_id"]] = doc
		sauves.append(doc)
		return doc

	return {"docs": docs, "sauves": sauves, "get": get_doc_fn, "save": save_doc_fn}


def ids(lieux):
	return sorted(l["_id"] for l in lieux)


# ── sous_categorie_lieu ──────────────────────────────────────────────────────────

def test_sous_categorie_lue_sur_le_lieu():
	assert quetes.sous_categorie_lieu(RECEPTION) == "guilde_aventurier"


def test_sous_categorie_absente_ou_doc_vide():
	assert quetes.sous_categorie_lieu(BOUCHERIE) == ""
	assert quetes.sous_categorie_lieu(None) == ""


# ── lieux_solidaires ─────────────────────────────────────────────────────────────

def test_magasin_nest_solidaire_que_de_lui_meme():
	"""Sans `sous_categorie`, pas de maison : le comportement historique est préservé."""
	assert quetes.lieux_solidaires(BOUCHERIE, make_find_docs()) == [BOUCHERIE]


def test_guilde_regroupe_ses_lieux_sans_ramasser_la_ville():
	"""Réception + comptoir. NI la boucherie (même `lieu_parent`, pas la maison),
	NI la façade (pas de `sous_categorie`), NI la guilde de l'autre cité."""
	lieux = quetes.lieux_solidaires(RECEPTION, make_find_docs())
	assert ids(lieux) == ["lieu:bastion_comptoir", "lieu:bastion_interieur"]


def test_la_maison_se_reconstitue_depuis_nimporte_lequel_de_ses_lieux():
	"""Le comptoir (donneur de la mission de Borin) retrouve la réception, et réciproquement."""
	assert ids(quetes.lieux_solidaires(COMPTOIR, make_find_docs())) == ids(
		quetes.lieux_solidaires(RECEPTION, make_find_docs())
	)


def test_le_giver_est_toujours_en_tete():
	assert quetes.lieux_solidaires(COMPTOIR, make_find_docs())[0]["_id"] == "lieu:bastion_comptoir"


def test_giver_absent_du_resultat_de_find_docs_nest_pas_perdu():
	"""find_docs muet (index absent, base en vrac) → on retombe sur le donneur seul, sans crash."""
	assert quetes.lieux_solidaires(RECEPTION, lambda selector: None) == [RECEPTION]


def test_giver_sans_lieu_parent():
	orphelin = {"_id": "lieu:orphelin", "sous_categorie": "guilde_aventurier"}
	assert quetes.lieux_solidaires(orphelin, make_find_docs()) == [orphelin]


def test_une_CITE_nest_solidaire_daucune_autre():
	"""⚠️ Depuis que les cités pendent au pays (portée géographique des recettes,
	`marche.portees_lieu`), deux villes de même `sous_categorie` sont sœurs au sens du
	sélecteur — et ce qui les écartait jusque-là était leur absence de `lieu_parent`.
	Sans garde explicite, un renoncement à Auxerre sanctionnerait la réputation à Reims."""
	auxerre = {"_id": "lieu:auxerre", "type": "lieu", "categorie": "ville",
			   "sous_categorie": "ville", "lieu_parent": "lieu:france"}
	rhemi = {"_id": "lieu:rhemi", "type": "lieu", "categorie": "ville",
			 "sous_categorie": "ville", "lieu_parent": "lieu:france"}
	find_docs_fn = make_find_docs([auxerre, rhemi])
	assert quetes.lieux_solidaires(auxerre, find_docs_fn) == [auxerre]
	# Et une cité ne se fait pas non plus ramasser par la maison d'un lieu qui la partagerait.
	voisin = {"_id": "lieu:halle", "type": "lieu", "categorie": "boucherie",
			  "sous_categorie": "ville", "lieu_parent": "lieu:france"}
	assert ids(quetes.lieux_solidaires(voisin, make_find_docs([voisin, auxerre, rhemi]))) == [
		"lieu:halle"]


# ── sanctionner_renoncement ──────────────────────────────────────────────────────

def test_sanction_frappe_toute_la_maison(perso, db, monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)

	valeurs = quetes.sanctionner_renoncement(perso, COMPTOIR, db["get"], db["save"], make_find_docs())

	assert valeurs == {"lieu:bastion_comptoir": 49, "lieu:bastion_interieur": 49}
	# Un doc `relation` persisté par lieu — ce sont des docs ANNEXES, hors character.
	assert len(db["sauves"]) == 2
	assert all(d["type"] == "relation" for d in db["sauves"])


def test_le_giver_nest_pas_decremente_deux_fois(perso, db, monkeypatch):
	"""Il est en tête de la liste ET rendu par find_docs : la déduplication doit tenir."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)

	quetes.sanctionner_renoncement(perso, RECEPTION, db["get"], db["save"], make_find_docs())

	relation = db["docs"][marche.relation_doc_id(perso, RECEPTION)]
	assert marche.relation_value(relation) == 49


def test_sanction_repart_de_la_relation_existante(perso, db, monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	db["docs"][marche.relation_doc_id(perso, RECEPTION)] = {
		"_id": marche.relation_doc_id(perso, RECEPTION), "type": "relation",
		"character_id": perso["_id"], "lieu_id": RECEPTION["_id"], "value": 72,
	}
	valeurs = quetes.sanctionner_renoncement(perso, RECEPTION, db["get"], db["save"], make_find_docs())
	assert valeurs["lieu:bastion_interieur"] == 71


def test_relation_bornee_a_zero(perso, db, monkeypatch):
	"""Un banni ne peut pas descendre plus bas (`ajuster_relation` clampe 0–100)."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	db["docs"][marche.relation_doc_id(perso, RECEPTION)] = {
		"_id": marche.relation_doc_id(perso, RECEPTION), "type": "relation",
		"character_id": perso["_id"], "lieu_id": RECEPTION["_id"], "value": 0,
	}
	valeurs = quetes.sanctionner_renoncement(perso, RECEPTION, db["get"], db["save"], make_find_docs())
	assert valeurs["lieu:bastion_interieur"] == 0


def test_sanction_dun_magasin_ne_touche_que_lui(perso, db, monkeypatch):
	"""Une course confiée par une boutique reste une affaire entre elle et le joueur."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)

	valeurs = quetes.sanctionner_renoncement(perso, BOUCHERIE, db["get"], db["save"], make_find_docs())

	assert valeurs == {"lieu:boucherie": 49}
	assert len(db["sauves"]) == 1


# ── Expiration d'une course (utils/transport.py) ─────────────────────────────────

def test_expiration_dune_course_de_guilde_fache_toute_la_maison(perso, db, monkeypatch):
	"""Laisser filer le délai de la mission du comptoir doit coûter autant que l'abandonner —
	et la réception l'apprend aussi."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)
	db["docs"][COMPTOIR["_id"]] = COMPTOIR
	perso["quetes_actives"] = [{
		"id": "quete:mission", "titre": "Deux caisses de viande",
		"giver": "lieu:bastion_comptoir",
		"objectif": {"type": "transport"},
		"expire_at": 1000,
		"cargaison": [{"item": "item:viande", "poids": 2}],
	}]

	echues = transport.traiter_expirations(perso, 1001, db["get"], db["save"], make_find_docs())

	assert len(echues) == 1
	assert perso["quetes_actives"] == []
	relations = {d["lieu_id"]: marche.relation_value(d) for d in db["sauves"] if d["type"] == "relation"}
	assert relations == {"lieu:bastion_comptoir": 49, "lieu:bastion_interieur": 49}
	# La cargaison reste dans le sac : le joueur garde la marchandise, seule sa réputation paie.
	assert echues[0]["cargaison"] == [{"item": "item:viande", "poids": 2}]


# ══════════════════════════════════════════════════════════════════════════════════
# Consolidation : `relation_lieu` fait porter par UN lieu la réputation de plusieurs
# ══════════════════════════════════════════════════════════════════════════════════
# Même monde, mais façade / réception / bureau délèguent leur relation au COMPTOIR. Le bureau
# du maître n'a PAS de `sous_categorie` (il n'est solidaire que de lui-même) : c'est
# `relation_lieu` — et lui seul — qui le fait encaisser chez le comptoir.

RECEPTION_C = {**RECEPTION, "relation_lieu": COMPTOIR["_id"]}
FACADE_C = {**FACADE, "relation_lieu": COMPTOIR["_id"]}
BUREAU_C = {
	"_id": "lieu:bureau_du_maitre", "type": "lieu", "label": "Le bureau du maître de guilde",
	"categorie": "bureau_maitre_guilde",  # ⚠️ pas de `sous_categorie`, et il n'en faut pas
	"lieu_parent": "lieu:auxerre",
	"relation_lieu": COMPTOIR["_id"],
}

MONDE_CONSOLIDE = [RECEPTION_C, COMPTOIR, FACADE_C, BUREAU_C, BOUCHERIE, GUILDE_AILLEURS]


# ── lieu_de_relation / relation_doc_id ───────────────────────────────────────────

def test_sans_relation_lieu_un_lieu_porte_sa_propre_relation():
	"""Champ absent ⇒ comportement d'avant, aucune migration."""
	assert marche.lieu_de_relation(BOUCHERIE) == "lieu:boucherie"
	assert marche.lieu_de_relation(COMPTOIR) == COMPTOIR["_id"]


def test_relation_lieu_deplace_la_relation_sur_le_porteur():
	assert marche.lieu_de_relation(BUREAU_C) == COMPTOIR["_id"]
	assert marche.lieu_de_relation(RECEPTION_C) == COMPTOIR["_id"]


def test_un_seul_saut_jamais_de_chaine():
	"""Le porteur ne relaie pas : un cycle A vers B vers A ferait boucler TOUTE lecture."""
	a = {"_id": "lieu:a", "relation_lieu": "lieu:b"}
	b = {"_id": "lieu:b", "relation_lieu": "lieu:a"}
	assert marche.lieu_de_relation(a) == "lieu:b"
	assert marche.lieu_de_relation(b) == "lieu:a"


def test_valeur_illisible_ou_auto_reference_ignoree():
	"""Fail-soft : on retombe sur le lieu lui-même plutôt que de fabriquer un doc orphelin."""
	assert marche.lieu_de_relation({"_id": "lieu:x", "relation_lieu": "lieu:x"}) == "lieu:x"
	assert marche.lieu_de_relation({"_id": "lieu:x", "relation_lieu": "pnj:borin"}) == "lieu:x"
	assert marche.lieu_de_relation({"_id": "lieu:x", "relation_lieu": ""}) == "lieu:x"
	assert marche.lieu_de_relation({"_id": "lieu:x", "relation_lieu": None}) == "lieu:x"


def test_deux_lieux_consolides_partagent_UN_doc_relation(perso):
	assert marche.relation_doc_id(perso, BUREAU_C) == marche.relation_doc_id(perso, COMPTOIR)
	assert marche.relation_doc_id(perso, RECEPTION_C) == marche.relation_doc_id(perso, COMPTOIR)
	# Un magasin garde le sien.
	assert marche.relation_doc_id(perso, BOUCHERIE) != marche.relation_doc_id(perso, COMPTOIR)


def test_doc_relation_frais_nomme_le_lieu_PORTEUR(perso):
	"""`relations_lieux_payload` indexe par `lieu_id` : un doc frais qui nommerait le délégant
	y serait orphelin, et l'onglet Relations afficherait la valeur neutre."""
	rel = marche.get_relation(perso, BUREAU_C, lambda _id: None)
	assert rel["lieu_id"] == COMPTOIR["_id"]


# ── LE test qui compte : la sanction ne doit pas compter DOUBLE ──────────────────

def test_la_sanction_ne_frappe_quUNE_fois_par_doc_relation(perso, db, monkeypatch):
	"""Réception et comptoir résolvent vers le MÊME doc. Sans dédup par doc, le second
	`get_relation` relirait celui que le premier vient de sauver : −2 pour un seul abandon."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)

	valeurs = quetes.sanctionner_renoncement(
		perso, RECEPTION_C, db["get"], db["save"], make_find_docs(MONDE_CONSOLIDE))

	# UN seul doc sauvé, celui du comptoir, à 49 — et NON 48.
	assert len(db["sauves"]) == 1
	assert db["sauves"][0]["_id"] == marche.relation_doc_id(perso, COMPTOIR)
	assert marche.relation_value(db["sauves"][0]) == 49
	# Le retour reste indexé par LIEU : les deux lieux montrent la même cote, c'est exact.
	assert valeurs == {"lieu:bastion_interieur": 49, "lieu:bastion_comptoir": 49}


def test_abandonner_une_commission_du_bureau_frappe_le_comptoir(perso, db, monkeypatch):
	"""Le bureau n'a pas de `sous_categorie` : sans `relation_lieu`, il encaisserait seul dans
	son coin et la guilde ne s'apercevrait de rien."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)

	valeurs = quetes.sanctionner_renoncement(
		perso, BUREAU_C, db["get"], db["save"], make_find_docs(MONDE_CONSOLIDE))

	assert len(db["sauves"]) == 1
	assert db["sauves"][0]["_id"] == marche.relation_doc_id(perso, COMPTOIR)
	assert valeurs == {"lieu:bureau_du_maitre": 49}


# ── recompenser_donneur ──────────────────────────────────────────────────────────

def test_le_gain_ne_va_quAU_donneur(perso, db, monkeypatch):
	"""Asymétrie VOULUE : la maison punit collectivement, elle ne remercie pas collectivement."""
	monkeypatch.setattr(character_stats, "QUETE_REUSSITE_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)

	assert quetes.recompenser_donneur(perso, RECEPTION, db["get"], db["save"]) == 51

	assert len(db["sauves"]) == 1
	assert db["sauves"][0]["_id"] == marche.relation_doc_id(perso, RECEPTION)


def test_le_gain_repart_de_la_relation_existante(perso, db, monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_REUSSITE_RELATION_DELTA", 1)
	doc_id = marche.relation_doc_id(perso, COMPTOIR)
	db["docs"][doc_id] = {"_id": doc_id, "type": "relation", "character_id": perso["_id"],
						  "lieu_id": COMPTOIR["_id"], "value": 72}
	assert quetes.recompenser_donneur(perso, COMPTOIR, db["get"], db["save"]) == 73


def test_le_gain_est_borne_a_cent(perso, db, monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_REUSSITE_RELATION_DELTA", 1)
	doc_id = marche.relation_doc_id(perso, COMPTOIR)
	db["docs"][doc_id] = {"_id": doc_id, "type": "relation", "character_id": perso["_id"],
						  "lieu_id": COMPTOIR["_id"], "value": 100}
	assert quetes.recompenser_donneur(perso, COMPTOIR, db["get"], db["save"]) == 100


def test_pas_de_donneur_pas_de_gain(perso, db):
	"""Une quête sans donneur (ou dont le doc a disparu) ne doit rien créer ni planter."""
	assert quetes.recompenser_donneur(perso, None, db["get"], db["save"]) is None
	assert db["sauves"] == []


def test_le_gain_suit_la_consolidation(perso, db, monkeypatch):
	"""Réussir au tableau (réception) puis une commission (bureau) : MÊME doc, +2."""
	monkeypatch.setattr(character_stats, "QUETE_REUSSITE_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)

	quetes.recompenser_donneur(perso, RECEPTION_C, db["get"], db["save"])
	assert quetes.recompenser_donneur(perso, BUREAU_C, db["get"], db["save"]) == 52
	assert len(db["docs"]) == 1
	assert marche.relation_doc_id(perso, COMPTOIR) in db["docs"]


# ── Affichage : les 4 lignes du Bastion montrent la MÊME cote ────────────────────

def test_les_lieux_consolides_affichent_la_meme_valeur(perso, monkeypatch):
	"""Sans passer par `lieu_de_relation`, la façade / la réception / le bureau afficheraient
	la valeur neutre pendant que le comptoir en montre une autre."""
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)
	docs = {d["_id"]: d for d in MONDE_CONSOLIDE}
	rel_id = marche.relation_doc_id(perso, COMPTOIR)
	relation = {"_id": rel_id, "type": "relation", "character_id": perso["_id"],
				"lieu_id": COMPTOIR["_id"], "value": 55}

	monkeypatch.setattr(marche, "get_doc", lambda doc_id: docs.get(doc_id))
	monkeypatch.setattr(marche, "find_docs", lambda selector: [relation])

	perso["lieux_visites"] = [FACADE_C["_id"], RECEPTION_C["_id"], COMPTOIR["_id"],
							  BUREAU_C["_id"], BOUCHERIE["_id"]]
	payload = {r["lieu_id"]: r["value"] for r in marche.relations_lieux_payload(perso)}

	assert payload[FACADE_C["_id"]] == 55
	assert payload[RECEPTION_C["_id"]] == 55
	assert payload[COMPTOIR["_id"]] == 55
	assert payload[BUREAU_C["_id"]] == 55
	# Un lieu qui ne délègue pas garde sa cote propre (ici : neutre, aucune relation en base).
	assert payload[BOUCHERIE["_id"]] == 50


def test_une_ligne_sans_label_s_intitule_par_son_slug_jamais_par_son_id(perso, monkeypatch):
	"""Le titre d'une ligne de l'onglet 🤝 retombait sur l'identifiant brut (`label` par
	défaut du `.get`). Tous les lieux en base portent un `label`, mais un import qui
	l'oublierait afficherait « lieu:sans_enseigne » au joueur."""
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)
	muet = {"_id": "lieu:sans_enseigne", "type": "lieu", "categorie": "boucherie",
			"lieu_parent": "lieu:nulle_part"}
	docs = {muet["_id"]: muet, "lieu:nulle_part": {"_id": "lieu:nulle_part", "type": "lieu",
													"categorie": "ville"}}

	monkeypatch.setattr(marche, "get_doc", lambda doc_id: docs.get(doc_id))
	monkeypatch.setattr(marche, "find_docs", lambda selector: [])

	perso["lieux_visites"] = [muet["_id"]]
	ligne = marche.relations_lieux_payload(perso)[0]

	assert ligne["nom"] == "sans_enseigne"
	assert ligne["parent_nom"] == "nulle_part"
	assert "lieu:" not in ligne["nom"]
