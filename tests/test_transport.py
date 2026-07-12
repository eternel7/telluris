"""Quêtes de transport de marchandise (utils/transport.py) — logique pure, sans DB.

Toutes les dépendances externes sont injectées (get_doc_fn / find_docs_fn / rand_fn / now)
ou monkeypatchées sur le module, comme dans test_pnj.py et test_focalisation.py. La carte
des recettes (`marche._marche_map`) est semée directement : c'est elle qui décide, en
amont, ce qu'une catégorie de lieu achète et produit — donc quels lieux sont des magasins.
"""

import pytest

from models import character_stats
from utils import focalisation, marche, pnj, quetes, transport


# ── Monde de test ────────────────────────────────────────────────────────────────
# Une ville, trois boutiques. La boucherie produit de la viande ; la salaison et le fumoir
# la rachètent (leurs recettes la consomment). Le fumoir, lui, ne fournit rien.

VILLE = {"_id": "lieu:ville", "type": "lieu", "categorie": "ville", "label": "Bourgade"}

BOUCHERIE = {
	"_id": "lieu:boucherie", "type": "lieu", "categorie": "boucherie", "label": "L'Étal",
	"lieu_parent": "lieu:ville",
	"stock_vente": [{"item_id": "item:viande", "qty": 4}],
}
SALAISON = {
	"_id": "lieu:salaison", "type": "lieu", "categorie": "salaison", "label": "Le Saloir",
	"lieu_parent": "lieu:ville",
}
FUMOIR = {
	"_id": "lieu:fumoir", "type": "lieu", "categorie": "fumoir", "label": "Le Fumoir",
	"lieu_parent": "lieu:ville",
}
TEMPLE = {
	"_id": "lieu:temple", "type": "lieu", "categorie": "temple", "label": "Le Temple",
	"lieu_parent": "lieu:ville",
}

VIANDE = {"_id": "item:viande", "type": "item", "nom": "Viande", "sous_categorie": "viande", "poids": [2, 2]}
ENCLUME = {"_id": "item:enclume", "type": "item", "nom": "Enclume", "sous_categorie": "viande", "poids": [500, 500]}

DOCS = {d["_id"]: d for d in (VILLE, BOUCHERIE, SALAISON, FUMOIR, TEMPLE, VIANDE, ENCLUME)}

# Portes des boutiques dans la grille de la ville : la boucherie au centre, la salaison
# plein nord, le fumoir plein est.
CONNECTIONS = [
	{"_id": "link:b", "type": "connection",
	 "nodes": [{"lieu": "lieu:ville", "pos": [20, 20]}, {"lieu": "lieu:boucherie", "pos": [0, 0]}]},
	{"_id": "link:s", "type": "connection",
	 "nodes": [{"lieu": "lieu:ville", "pos": [20, 5]}, {"lieu": "lieu:salaison", "pos": [0, 0]}]},
	{"_id": "link:f", "type": "connection",
	 "nodes": [{"lieu": "lieu:ville", "pos": [40, 20]}, {"lieu": "lieu:fumoir", "pos": [0, 0]}]},
	{"_id": "link:t", "type": "connection",
	 "nodes": [{"lieu": "lieu:ville", "pos": [22, 6]}, {"lieu": "lieu:temple", "pos": [0, 0]}]},
]


def get_doc(doc_id):
	return DOCS.get(doc_id)


def find_docs(selector):
	if selector.get("type") == "connection":
		return list(CONNECTIONS)
	if selector.get("type") == "lieu":
		parent = selector.get("lieu_parent")
		return [d for d in DOCS.values()
				if d.get("type") == "lieu" and (parent is None or d.get("lieu_parent") == parent)]
	return []


@pytest.fixture(autouse=True)
def monde(monkeypatch):
	"""Sème la carte des recettes (source des « qui achète quoi ») et vide le cache de graphe."""
	monkeypatch.setattr(marche, "_marche_map", {
		"besoins": {"salaison": {"viande"}, "fumoir": {"viande"}, "boucherie": {"carcasse"}},
		"produits": {"boucherie": {"item:viande"}, "salaison": set(), "fumoir": set()},
		"feuilles": set(),
	})
	focalisation.reset_graphe_cache()
	yield
	focalisation.reset_graphe_cache()


def character(**extra):
	c = {
		"_id": "character:u_1", "prenom": "Alia",
		"inventaire": [], "quetes_actives": [], "quetes_terminees": [],
		"caracteristiques_current": {"F": 40},  # charge_max = F×5 = 200
		"slots": {}, "xp_total": 0, "vocations_niveaux": {}, "voc": "guerrier",
	}
	c.update(extra)
	return c


def offre(giver=BOUCHERIE, rand=lambda: 0.0):
	return transport.generer_transport(giver, find_docs, get_doc, rand_fn=rand)


# ── Magasins & tenancier ─────────────────────────────────────────────────────────

def test_est_magasin_suit_les_recettes():
	# Un lieu est marchand dès que sa catégorie consomme ou produit quelque chose.
	assert transport.est_magasin(BOUCHERIE)
	assert transport.est_magasin(SALAISON)
	assert not transport.est_magasin(VILLE)
	assert not transport.est_magasin(TEMPLE)


def test_tenancier_generique_derive_de_la_categorie():
	assert transport.entree_marchand(SALAISON) == {
		"character": "pnj:marchand_salaison", "probabilite": 1.0,
	}
	assert transport.entree_marchand(TEMPLE) is None


def test_une_boutique_peut_nommer_son_tenancier_sans_dupliquer_le_dialogue():
	# L'entrée du lieu pointe le doc GÉNÉRIQUE de la catégorie (donc son arbre de dialogue et
	# son service transport) mais surcharge l'identité → un tenancier propre à la boutique,
	# sans recopier un arbre de dialogue par magasin.
	entree = {"character": "pnj:marchand_fletcher", "nom": "Lucinda Mortecroix",
			  "portrait": "marchand_lucinda_mortecroix_fletcher.png"}
	doc = {"_id": "pnj:marchand_fletcher", "nom": "Le vieux Thibaut", "portrait": "generique.jpg"}
	paye = pnj.pnj_payload(entree, doc)
	assert paye["nom"] == "Lucinda Mortecroix"
	assert paye["portrait"] == "marchand_lucinda_mortecroix_fletcher.png"
	assert paye["character"] == "pnj:marchand_fletcher"  # le dialogue reste celui du générique
	# Sans surcharge, le doc fait foi (comportement historique inchangé).
	assert pnj.pnj_payload({"character": "pnj:marchand_fletcher"}, doc)["nom"] == "Le vieux Thibaut"


def test_le_champ_pnj_explicite_prime_sur_le_tenancier_implicite():
	# Un temple garde son PNJ authoré ; une boutique sans champ `pnj` reçoit son tenancier.
	temple = dict(TEMPLE, pnj=[{"character": "pnj:malakor", "probabilite": 1.0}])
	assert pnj.tirer_pnj_present(temple, lambda: 0.0, transport.entree_marchand) == "pnj:malakor"
	assert pnj.tirer_pnj_present(SALAISON, lambda: 0.0, transport.entree_marchand) == "pnj:marchand_salaison"
	# Sans marchand_fn (appelants historiques), rien ne change pour les lieux sans `pnj`.
	assert pnj.tirer_pnj_present(SALAISON, lambda: 0.0) is None


# ── Géographie ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("vers,attendu", [
	((20, 10), "nord"),        # y croît vers le BAS : plus petit y = plus au nord
	((20, 30), "sud"),
	((30, 20), "est"),
	((10, 20), "ouest"),
	((30, 10), "nord-est"),
	((10, 10), "nord-ouest"),
	((30, 30), "sud-est"),
	((10, 30), "sud-ouest"),
])
def test_direction_cardinale_huit_octants(vers, attendu):
	assert transport.direction_cardinale((20, 20), vers) == attendu


def test_direction_cardinale_sur_place():
	assert transport.direction_cardinale((20, 20), (20, 20)) is None


def test_indice_meme_ville_donne_direction_et_repere():
	indice = transport.indice_destination(BOUCHERIE, "lieu:salaison", find_docs, get_doc)
	assert indice["meme_ville"] is True
	assert indice["nom"] == "Le Saloir"
	# La salaison est plein nord de la boucherie (20,5) vs (20,20).
	assert indice["direction"] == "nord"
	# Le repère est le magasin le plus proche de la destination — pas le temple (pas un magasin).
	assert indice["repere"] == "Le Fumoir"
	assert "au nord d'ici" in transport.texte_indice(indice)


def test_repere_ignore_les_lieux_non_marchands():
	graphe = focalisation.charger_graphe(find_docs)
	portes = transport.portes_du_parent(graphe, "lieu:ville")
	# Le temple (22,6) est de loin le plus proche de la salaison (20,5) — mais on ne donne
	# comme repère qu'une boutique : le joueur ne s'oriente qu'aux enseignes.
	assert transport.repere_proche(
		"lieu:salaison", portes, get_doc, exclure={"lieu:boucherie"}
	) == "Le Fumoir"


# ── Choix de la destination & de la cargaison ────────────────────────────────────

def test_destination_exclut_le_donneur_et_exige_un_racheteur():
	q = offre()
	assert q is not None
	assert q["giver"] == "lieu:boucherie"
	assert q["objectif"]["cible"] in ("lieu:salaison", "lieu:fumoir")


def test_pas_d_offre_si_personne_ne_rachete(monkeypatch):
	# Le fumoir ne fournit rien (aucun produit, aucun rayon) → rien à faire porter.
	assert transport.generer_transport(FUMOIR, find_docs, get_doc, rand_fn=lambda: 0.0) is None


def test_cargaison_bornee_par_le_nombre_d_objets(monkeypatch):
	# 100 kg autorisés, viande à 2 kg → c'est la borne de NOMBRE qui coupe en premier.
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_POIDS_MAX", 100.0)
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_NB_MAX", 3)
	cargaison = transport.choisir_cargaison([VIANDE], rand_fn=lambda: 0.0)
	assert len(cargaison) == 3
	assert transport.poids_cargaison(cargaison) == 6.0


def test_cargaison_bornee_par_le_poids(monkeypatch):
	# 20 objets autorisés, viande à 2 kg, 9 kg max → 4 pièces (la 5e ferait 10 kg > 9).
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_POIDS_MAX", 9.0)
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_NB_MAX", 20)
	cargaison = transport.choisir_cargaison([VIANDE], rand_fn=lambda: 0.0)
	assert len(cargaison) == 4
	assert transport.poids_cargaison(cargaison) == 8.0


def test_cargaison_vide_si_un_seul_objet_depasse_deja(monkeypatch):
	# On s'arrête AVANT de franchir la borne — jamais après : une enclume de 500 kg ne part pas.
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_POIDS_MAX", 100.0)
	assert transport.choisir_cargaison([ENCLUME], rand_fn=lambda: 0.0) == []


def test_pas_d_offre_si_la_cargaison_est_vide(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_POIDS_MAX", 1.0)
	assert offre() is None


# ── Récompenses ──────────────────────────────────────────────────────────────────

def test_xp_de_base_dans_la_meme_ville(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_XP", 10)
	q = offre()
	assert q["recompenses"]["xp"] == 10


def test_xp_multipliee_hors_de_la_ville(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_XP", 10)
	indice_lointain = {"meme_ville": False, "distance": 3}
	assert transport._xp_transport(indice_lointain) == 40  # 10 × (1 + 3)


def test_prime_indexee_sur_l_xp(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_XP", 10)
	monkeypatch.setattr(character_stats, "QUETE_CUIVRE_PAR_XP", 3.0)
	assert offre()["recompenses"]["cuivre"] == 30


# ── Tirage de l'offre à l'entrée du magasin ──────────────────────────────────────

def test_offre_tiree_selon_la_probabilite(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_PROBA", 0.10)
	c = character()
	# Premier tirage au-dessus du seuil : le marchand n'a rien à faire porter.
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc, rand_fn=lambda: 0.5)
	assert c["transport_offert"] == {"lieu": "lieu:boucherie", "quete": None}
	assert transport.offre_courante(c, BOUCHERIE) is None

	c = character()
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc, rand_fn=lambda: 0.05)
	assert transport.offre_courante(c, BOUCHERIE) is not None


def test_un_refresh_ne_retire_pas(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_PROBA", 1.0)
	c = character()
	assert transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc, rand_fn=lambda: 0.0)
	premiere = transport.offre_courante(c, BOUCHERIE)
	# Re-rendu de la même page : aucun nouveau tirage, la même offre reste sur la table.
	assert not transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc, rand_fn=lambda: 0.9)
	assert transport.offre_courante(c, BOUCHERIE) == premiere


def test_pas_d_offre_avec_une_course_deja_en_cours(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_PROBA", 1.0)
	c = character()
	transport.accepter_transport(c, offre(), now=1000)
	# On repart de zéro sur le lieu (le champ transitoire a été vidé par l'acceptation).
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc, rand_fn=lambda: 0.0)
	assert transport.offre_courante(c, BOUCHERIE) is None


def test_sortir_du_magasin_efface_l_offre(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_PROBA", 1.0)
	c = character()
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc, rand_fn=lambda: 0.0)
	assert transport.poser_transport_offert(c, VILLE, find_docs, get_doc)
	assert c["transport_offert"] is None


# ── Acceptation ──────────────────────────────────────────────────────────────────

def test_accepter_met_la_cargaison_au_sac_et_pose_l_echeance(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_DUREE_SECONDES", 3600)
	c = character()
	q = offre()
	snap = transport.accepter_transport(c, q, now=1000)

	assert snap["expire_at"] == 1000 + 3600
	assert len(c["inventaire"]) == len(q["cargaison"])
	assert all(ref["item"] == "item:viande" for ref in c["inventaire"])
	assert c["quetes_actives"] == [snap]
	# L'offre est consommée : le marchand ne la reproposera pas.
	assert c["transport_offert"] is None


def test_transport_a_livrer_ne_repond_qu_a_la_destination():
	c = character()
	snap = transport.accepter_transport(c, offre(), now=1000)
	dest = snap["objectif"]["cible"]
	assert transport.transport_a_livrer(c, dest) == snap
	assert transport.transport_a_livrer(c, "lieu:boucherie") is None


# ── Livraison ────────────────────────────────────────────────────────────────────

def test_livrer_retire_exactement_la_cargaison():
	c = character()
	snap = transport.accepter_transport(c, offre(), now=1000)
	c["inventaire"].append({"item": "item:viande", "poids": 2})  # viande personnelle, à garder
	n_cargo = len(snap["cargaison"])

	assert transport.livrer_transport(c, snap) is True
	assert len(c["inventaire"]) == 1  # seule la viande personnelle reste
	assert snap["progress"] == 1


def test_livraison_refusee_si_la_cargaison_a_ete_vendue():
	c = character()
	snap = transport.accepter_transport(c, offre(), now=1000)
	c["inventaire"].pop()  # le joueur a bradé un colis en route

	assert transport.cargaison_manquante(c, snap) == {"item:viande": 1}
	assert transport.livrer_transport(c, snap) is False
	# La course reste active : le délai continue de courir.
	assert transport.transports_actifs(c) == [snap]


def test_reussite_paie_et_monte_la_relation(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)
	sauves = []
	c = character()
	snap = transport.accepter_transport(c, offre(), now=1000)
	transport.livrer_transport(c, snap)

	recap = transport.reussir_transport(c, snap, SALAISON, get_doc, sauves.append, now=2000)

	assert recap["relation"] == 51  # +1 chez le DONNEUR (la boucherie), pas le destinataire
	assert sauves[0]["_id"] == "relation:character:u_1::lieu:boucherie"
	assert recap["xp"]["xp_gain"] > 0
	assert transport.transports_actifs(c) == []
	assert c["quetes_terminees"][0]["echec"] is False


# ── Expiration ───────────────────────────────────────────────────────────────────

def test_expiration_archive_en_echec_et_laisse_la_marchandise():
	c = character()
	snap = transport.accepter_transport(c, offre(), now=1000)
	sac_avant = list(c["inventaire"])

	echues = transport.expirer_transports(c, now=1000 + 3601)

	assert echues == [snap]
	assert transport.transports_actifs(c) == []
	assert c["quetes_terminees"][0]["echec"] is True
	assert c["quetes_terminees"][0]["recompenses"] == {}
	# La cargaison RESTE dans le sac : le joueur garde la marchandise, seule sa réputation tombe.
	assert c["inventaire"] == sac_avant


# ── Mise en rayon chez le destinataire ───────────────────────────────────────────

def test_une_partie_de_la_cargaison_monte_en_rayon(monkeypatch):
	# La salaison PRODUIT de la viande (cf. la carte des recettes semée) : elle l'étale donc.
	monkeypatch.setattr(marche, "_marche_map", {
		"besoins": {"salaison": {"viande"}}, "produits": {"salaison": {"item:viande"}},
		"feuilles": set(),
	})
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_STOCK_PROBA", 0.5)
	dest = dict(SALAISON)
	cargaison = [{"item": "item:viande", "poids": 2} for _ in range(4)]
	# Deux tirages sous le seuil, deux au-dessus → 2 colis sur 4 finissent en rayon.
	tirages = iter([0.1, 0.9, 0.2, 0.99])

	ajouts = transport.deposer_en_rayon(dest, cargaison, get_doc, rand_fn=lambda: next(tirages))

	assert ajouts == {"item:viande": 2}
	assert dest["stock_vente"] == [{"item_id": "item:viande", "qty": 2}]


def test_le_rayon_existant_est_incrémenté(monkeypatch):
	monkeypatch.setattr(marche, "_marche_map", {
		"besoins": {}, "produits": {"salaison": {"item:viande"}}, "feuilles": set(),
	})
	dest = dict(SALAISON, stock_vente=[{"item_id": "item:viande", "qty": 7}])
	transport.deposer_en_rayon(dest, [{"item": "item:viande", "poids": 2}], get_doc,
							   rand_fn=lambda: 0.0)
	assert dest["stock_vente"] == [{"item_id": "item:viande", "qty": 8}]


def test_rien_en_rayon_si_le_magasin_ne_vend_pas_ce_produit(monkeypatch):
	# Le fumoir ACHÈTE la viande (matière première) mais ne la produit pas : elle part en
	# arrière-boutique, pas sur l'étal — même avec un tirage toujours gagnant.
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_STOCK_PROBA", 1.0)
	dest = dict(FUMOIR)
	ajouts = transport.deposer_en_rayon(dest, [{"item": "item:viande", "poids": 2}], get_doc,
										rand_fn=lambda: 0.0)
	assert ajouts == {}
	assert "stock_vente" not in dest


def test_la_livraison_garnit_l_etal_du_destinataire(monkeypatch):
	monkeypatch.setattr(marche, "_marche_map", {
		"besoins": {"salaison": {"viande"}}, "produits": {"boucherie": {"item:viande"},
														  "salaison": {"item:viande"}},
		"feuilles": set(),
	})
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_STOCK_PROBA", 1.0)
	sauves = []
	c = character()
	snap = transport.accepter_transport(c, offre(), now=1000)
	transport.livrer_transport(c, snap)
	dest = dict(SALAISON)

	recap = transport.reussir_transport(c, snap, dest, get_doc, sauves.append,
										now=2000, rand_fn=lambda: 0.0)

	n = len(snap["cargaison"])
	assert recap["rayon"] == {"item:viande": n}
	assert dest["stock_vente"] == [{"item_id": "item:viande", "qty": n}]
	# Le doc lieu est ANNEXE (hors character) → persisté par la fonction, comme la relation.
	assert dest in sauves


def test_une_course_n_est_pas_focalisable():
	# Le focus 🎯 guide ou biaise les tirages : une course a une destination nommée en ville,
	# il n'a rien à y faire. Le bouton doit disparaître, et le serveur refuse (cf. /api/focaliser).
	c = character()
	snap = transport.accepter_transport(c, offre(), now=1000)
	assert focalisation.quete_focalisable(snap) is False
	assert quetes.quete_detail(c, snap)["focalisable"] is False
	# Les autres types restent focalisables.
	assert focalisation.quete_focalisable({"objectif": {"type": "kill", "cible": "espece:loup"}})


def test_rien_n_expire_avant_l_echeance():
	c = character()
	transport.accepter_transport(c, offre(), now=1000)
	assert transport.expirer_transports(c, now=1000 + 3599) == []
	assert len(transport.transports_actifs(c)) == 1


def test_expiration_fait_chuter_la_relation_du_donneur(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_DELTA", 1)
	monkeypatch.setattr(character_stats, "RELATION_INITIALE", 50)
	sauves = []
	c = character()
	transport.accepter_transport(c, offre(), now=1000)

	echues = transport.traiter_expirations(c, 1000 + 3601, get_doc, sauves.append)

	assert len(echues) == 1
	assert sauves[0]["lieu_id"] == "lieu:boucherie"
	assert sauves[0]["value"] == 49


def test_relation_bornee_a_zero(monkeypatch):
	relation = {"value": 0}
	assert marche.ajuster_relation(relation, -5) == 0
	relation = {"value": 100}
	assert marche.ajuster_relation(relation, +5) == 100


# ── Conditions de dialogue ───────────────────────────────────────────────────────

def _noeud_accueil():
	return {
		"dialogue": {"noeud_depart": "accueil", "noeuds": {"accueil": {
			"texte": "Bonjour {prenom}. {destination} vous attend.",
			"choix": [
				{"id": "course", "label": "Une course ?", "next": "propose",
				 "condition": {"transport_offert": True}},
				{"id": "livraison", "label": "Une livraison.", "next": "livre",
				 "condition": {"transport_a_livrer": True}},
				{"id": "rien", "label": "Je passais.", "next": "fin"},
			],
		}}},
	}


def test_les_flags_filtrent_les_choix():
	doc = _noeud_accueil()
	ctx = pnj.contexte_dialogue(character(), doc, lambda _l: 50,
								flags={"transport_offert": True, "transport_a_livrer": False})
	ids = [c["id"] for c in pnj.noeud_client(doc, "accueil", ctx)["choix"]]
	assert ids == ["course", "rien"]

	ctx = pnj.contexte_dialogue(character(), doc, lambda _l: 50,
								flags={"transport_offert": False, "transport_a_livrer": True})
	ids = [c["id"] for c in pnj.noeud_client(doc, "accueil", ctx)["choix"]]
	assert ids == ["livraison", "rien"]


def test_un_flag_absent_masque_le_choix():
	doc = _noeud_accueil()
	ctx = pnj.contexte_dialogue(character(), doc, lambda _l: 50)
	ids = [c["id"] for c in pnj.noeud_client(doc, "accueil", ctx)["choix"]]
	assert ids == ["rien"]


def test_les_placeholders_sont_substitues():
	doc = _noeud_accueil()
	ctx = pnj.contexte_dialogue(character(), doc, lambda _l: 50,
								placeholders={"destination": "Le Saloir"})
	assert pnj.noeud_client(doc, "accueil", ctx)["texte"] == "Bonjour Alia. Le Saloir vous attend."


def test_choix_valide_revalide_le_flag_serveur():
	doc = _noeud_accueil()
	# Le client réclame la course alors que le marchand n'a rien à proposer : refusé.
	ctx = pnj.contexte_dialogue(character(), doc, lambda _l: 50, flags={"transport_offert": False})
	assert pnj.choix_valide(doc, "accueil", "course", ctx) is None
