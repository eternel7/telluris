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
# La guilde : deux lieux, dont un IMBRIQUÉ. Le comptoir n'ouvre pas sur la ville (on y accède
# par la réception) et sa catégorie n'a aucune recette → ce n'est PAS un magasin. C'est le
# donneur d'une course écrite, portée par son réceptionniste.
GUILDE = {
	"_id": "lieu:guilde", "type": "lieu", "categorie": "guilde_aventurier", "label": "Le Bastion",
	"lieu_parent": "lieu:ville",
}
COMPTOIR = {
	"_id": "lieu:guilde_comptoir", "type": "lieu", "categorie": "guilde_aventurier_comptoir",
	"label": "Le comptoir", "lieu_parent": "lieu:ville",
}

VIANDE = {"_id": "item:viande", "type": "item", "nom": "Viande", "sous_categorie": "viande", "poids": [2, 2]}
ENCLUME = {"_id": "item:enclume", "type": "item", "nom": "Enclume", "sous_categorie": "viande", "poids": [500, 500]}

# Le réceptionniste porte une course ÉCRITE ; le tenancier d'une boutique, non (la sienne est
# tirée au hasard) — c'est toute la différence entre les deux chemins de `poser_transport_offert`.
BORIN = {
	"_id": "pnj:borin", "type": "pnj", "nom": "Borin",
	"services": {"transport": {
		"offre": {
			"id": "quete:transport_borin",
			"destination": "lieu:fumoir",
			"cargaison": [{"item": "item:viande", "quantite": 2, "poids": 5.0}],
			"duree": 3600,
			"unique": True,
			"titre": "Première mission",
			"recompenses": {"xp": 30, "cuivre": 200},
		},
		"noeuds": {"accepte": "transport_accepte"},
	}},
}
TENANCIER = {
	"_id": "pnj:marchand_boucherie", "type": "pnj", "nom": "Le boucher",
	"services": {"transport": {"noeuds": {"accepte": "transport_accepte"}}},
}

DOCS = {d["_id"]: d for d in (VILLE, BOUCHERIE, SALAISON, FUMOIR, TEMPLE, GUILDE, COMPTOIR,
							  VIANDE, ENCLUME, BORIN, TENANCIER)}

# Portes des boutiques dans la grille de la ville : la boucherie au centre, la salaison
# plein nord, le fumoir plein est, la guilde plein sud. Le comptoir, lui, n'a de porte que
# sur la réception de la guilde (lieu imbriqué).
CONNECTIONS = [
	{"_id": "link:b", "type": "connection",
	 "nodes": [{"lieu": "lieu:ville", "pos": [20, 20]}, {"lieu": "lieu:boucherie", "pos": [0, 0]}]},
	{"_id": "link:s", "type": "connection",
	 "nodes": [{"lieu": "lieu:ville", "pos": [20, 5]}, {"lieu": "lieu:salaison", "pos": [0, 0]}]},
	{"_id": "link:f", "type": "connection",
	 "nodes": [{"lieu": "lieu:ville", "pos": [40, 20]}, {"lieu": "lieu:fumoir", "pos": [0, 0]}]},
	{"_id": "link:t", "type": "connection",
	 "nodes": [{"lieu": "lieu:ville", "pos": [22, 6]}, {"lieu": "lieu:temple", "pos": [0, 0]}]},
	{"_id": "link:g", "type": "connection",
	 "nodes": [{"lieu": "lieu:ville", "pos": [20, 40]}, {"lieu": "lieu:guilde", "pos": [0, 0]}]},
	{"_id": "link:gc", "type": "connection",
	 "nodes": [{"lieu": "lieu:guilde", "pos": [0, 0]}, {"lieu": "lieu:guilde_comptoir", "pos": [0, 0]}]},
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


# ── Confiance : pas de colis à qui l'on voit d'un mauvais œil ────────────────────

def get_doc_relation(valeur, bloque_jusqu=0):
	"""get_doc_fn semant une relation de la valeur voulue entre Alia et la boucherie —
	`bloque_jusqu` = blocage de marchandage (crit d'échec) encore actif jusqu'à cette epoch."""
	rel_id = marche.relation_doc_id(character(), BOUCHERIE)

	def _get(doc_id):
		if doc_id == rel_id:
			return {"_id": rel_id, "type": "relation", "value": valeur,
					"marchandage_bloque_jusqu": bloque_jusqu}
		return DOCS.get(doc_id)
	return _get


def test_pas_d_offre_si_la_relation_est_sous_le_seuil(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_PROBA", 1.0)
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 50)
	c = character()
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc_relation(49),
									 rand_fn=lambda: 0.0)
	# Le tirage a bien eu lieu (le champ est posé, un refresh ne re-tirera pas) : le marchand
	# n'a simplement rien confié.
	assert c["transport_offert"] == {"lieu": "lieu:boucherie", "quete": None}


def test_offre_des_le_seuil_atteint(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_PROBA", 1.0)
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 50)
	c = character()
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc_relation(50),
									 rand_fn=lambda: 0.0)
	assert transport.offre_courante(c, BOUCHERIE) is not None


def test_relation_absente_vaut_neutre_donc_offre(monkeypatch):
	"""Cas du tout-venant : aucun doc relation en base → valeur neutre (50), le marchand propose."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_PROBA", 1.0)
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 50)
	c = character()
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc, rand_fn=lambda: 0.0)
	assert transport.offre_courante(c, BOUCHERIE) is not None


def test_seuil_a_zero_desactive_le_garde_fou(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_PROBA", 1.0)
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 0)
	c = character()
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc_relation(0),
									 rand_fn=lambda: 0.0)
	assert transport.offre_courante(c, BOUCHERIE) is not None


# ── Confiance : la brouille d'un marchandage raté ferme aussi la porte ───────────

def test_pas_d_offre_pendant_un_blocage_de_marchandage(monkeypatch):
	"""Crit d'échec au marchandage : le tenancier ne veut plus rien savoir — ni négocier, ni
	confier ses colis. La cote (ici bonne) n'y change rien : la brouille est un état daté."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_PROBA", 1.0)
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 50)
	c = character()
	fache = get_doc_relation(80, bloque_jusqu=quetes.now_epoch() + 600)
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, fache, rand_fn=lambda: 0.0)
	assert transport.offre_courante(c, BOUCHERIE) is None
	assert transport.mefiance(c, BOUCHERIE, TENANCIER, fache)


def test_blocage_expire_rouvre_la_porte(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_PROBA", 1.0)
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 50)
	c = character()
	passe = get_doc_relation(50, bloque_jusqu=quetes.now_epoch() - 1)
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, passe, rand_fn=lambda: 0.0)
	assert transport.offre_courante(c, BOUCHERIE) is not None


def test_blocage_ferme_la_porte_meme_garde_fou_desactive(monkeypatch):
	"""Le seuil de relation à 0 désactive SON garde-fou, pas la brouille : les deux règles ont
	leur propre réglage (`MARCHANDAGE_BLOCAGE_SECONDES` pour celle-ci)."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 0)
	c = character()
	fache = get_doc_relation(50, bloque_jusqu=quetes.now_epoch() + 600)
	assert not transport.confiance_suffisante(c, BOUCHERIE, fache)


def test_course_ecrite_ignore_le_seuil_de_relation(monkeypatch):
	"""Une course ÉCRITE est confiée par son scénario : la mission d'initiation de la guilde ne
	dépend pas de la cote du joueur auprès du donneur."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 50)
	c = character()
	rel_id = marche.relation_doc_id(c, COMPTOIR)
	get_doc_hostile = lambda doc_id: (
		{"_id": rel_id, "type": "relation", "value": 0} if doc_id == rel_id else DOCS.get(doc_id))
	transport.poser_transport_offert(c, COMPTOIR, find_docs, get_doc_hostile,
									 rand_fn=lambda: 0.0, pnj_doc=BORIN)
	assert transport.offre_courante(c, COMPTOIR)["id"] == "quete:transport_borin"


# ── Méfiance : le refus est PARLÉ (flag de dialogue) ─────────────────────────────

def test_mefiance_du_marchand_sous_le_seuil(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 50)
	c = character()
	assert transport.mefiance(c, BOUCHERIE, TENANCIER, get_doc_relation(30))


def test_pas_de_mefiance_au_dessus_du_seuil(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 50)
	c = character()
	assert not transport.mefiance(c, BOUCHERIE, TENANCIER, get_doc_relation(50))


def test_pas_de_mefiance_sur_une_course_ecrite(monkeypatch):
	"""Le donneur d'une course écrite la confie parce que le scénario le dit — même à un joueur
	détesté (et le comptoir n'est de toute façon pas un magasin)."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 50)
	c = character()
	rel_id = marche.relation_doc_id(c, COMPTOIR)
	get_doc_hostile = lambda doc_id: (
		{"_id": rel_id, "type": "relation", "value": 0} if doc_id == rel_id else DOCS.get(doc_id))
	assert not transport.mefiance(c, COMPTOIR, BORIN, get_doc_hostile)


def test_pas_de_mefiance_pendant_une_course(monkeypatch):
	"""Une course déjà en cours ne serait pas remplacée par une nouvelle : le refus n'aurait plus
	rien à voir avec la réputation, il induirait le joueur en erreur."""
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 50)
	c = character()
	transport.accepter_transport(c, offre(), now=1000)
	assert not transport.mefiance(c, BOUCHERIE, TENANCIER, get_doc_relation(10))


def test_pas_de_mefiance_hors_magasin(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_RELATION_MIN", 50)
	assert not transport.mefiance(character(), VILLE, None, get_doc_relation(0))


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


# ── Offres AUTHORÉES portées par un PNJ (n'importe quel PNJ, magasin ou non) ──────

def test_offre_spec_distingue_le_pnj_authore_du_tenancier():
	assert transport.offre_spec(BORIN)["destination"] == "lieu:fumoir"
	# Le tenancier d'une boutique n'a pas de course écrite : la sienne est tirée au hasard.
	assert transport.offre_spec(TENANCIER) is None
	assert transport.offre_spec(None) is None


def test_course_authoree_depuis_un_lieu_qui_n_est_pas_un_magasin():
	assert not transport.est_magasin(COMPTOIR)
	c = character()
	# rand=0.99 : aucune probabilité ne s'y oppose (proba par défaut = 1.0), contrairement au
	# tirage des marchands — la mission écrite est toujours là pour qui entre.
	assert transport.poser_transport_offert(c, COMPTOIR, find_docs, get_doc,
											rand_fn=lambda: 0.99, pnj_doc=BORIN)
	q = transport.offre_courante(c, COMPTOIR)
	assert q["id"] == "quete:transport_borin"          # id STABLE (gate de `unique`)
	assert q["titre"] == "Première mission"
	assert q["giver"] == "lieu:guilde_comptoir"
	assert q["objectif"] == {"type": "transport", "cible": "lieu:fumoir", "quantite": 1}
	assert q["cargaison"] == [{"item": "item:viande", "poids": 5.0}] * 2
	assert transport.poids_cargaison(q["cargaison"]) == 10.0
	assert q["recompenses"] == {"xp": 30, "cuivre": 200, "items": []}


def test_sans_pnj_le_comptoir_ne_donne_rien():
	c = character()
	transport.poser_transport_offert(c, COMPTOIR, find_docs, get_doc,
									 rand_fn=lambda: 0.0, pnj_doc=None)
	assert transport.offre_courante(c, COMPTOIR) is None


def test_le_magasin_sans_spec_garde_son_tirage_aleatoire(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_PROBA", 0.10)
	c = character()
	# Non-régression : le tenancier ne porte pas de course écrite → chemin aléatoire, seuil compris.
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc,
									 rand_fn=lambda: 0.5, pnj_doc=TENANCIER)
	assert transport.offre_courante(c, BOUCHERIE) is None
	c = character()
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc,
									 rand_fn=lambda: 0.05, pnj_doc=TENANCIER)
	assert transport.offre_courante(c, BOUCHERIE) is not None


def test_une_course_ecrite_prime_sur_le_tirage_du_magasin(monkeypatch):
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_PROBA", 0.0)  # aucun tirage possible
	c = character()
	transport.poser_transport_offert(c, BOUCHERIE, find_docs, get_doc,
									 rand_fn=lambda: 0.5, pnj_doc=BORIN)
	q = transport.offre_courante(c, BOUCHERIE)
	assert q["id"] == "quete:transport_borin"


def test_unique_reproposee_apres_un_echec_mais_pas_apres_une_reussite():
	reussie = character(quetes_terminees=[{"id": "quete:transport_borin", "echec": False}])
	transport.poser_transport_offert(reussie, COMPTOIR, find_docs, get_doc,
									 rand_fn=lambda: 0.0, pnj_doc=BORIN)
	assert transport.offre_courante(reussie, COMPTOIR) is None

	# Un retard n'est pas une condamnation : Borin reconfie ses caisses.
	echouee = character(quetes_terminees=[{"id": "quete:transport_borin", "echec": True}])
	transport.poser_transport_offert(echouee, COMPTOIR, find_docs, get_doc,
									 rand_fn=lambda: 0.0, pnj_doc=BORIN)
	assert transport.offre_courante(echouee, COMPTOIR) is not None


def test_deja_reussie():
	c = character(quetes_terminees=[{"id": "quete:x", "echec": False}])
	assert transport.deja_reussie(c, "quete:x")
	assert not transport.deja_reussie(c, "quete:y")
	assert not transport.deja_reussie(c, None)


def test_la_cargaison_ecrite_ignore_les_bornes_de_poids_et_de_nombre(monkeypatch):
	# Les bornes du tirage aléatoire ne s'appliquent pas à une intention écrite : la spec dit
	# exactement ce qu'elle pèse (seul le contrôle de charge à l'acceptation joue encore).
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_POIDS_MAX", 1.0)
	monkeypatch.setattr(character_stats, "QUETE_TRANSPORT_NB_MAX", 1)
	q = transport.generer_transport_authore(transport.offre_spec(BORIN), COMPTOIR, find_docs, get_doc)
	assert len(q["cargaison"]) == 2
	assert transport.poids_cargaison(q["cargaison"]) == 10.0


def test_cargaison_authoree_sans_poids_prend_le_poids_mini_de_l_item():
	spec = {"destination": "lieu:fumoir", "cargaison": [{"item": "item:viande", "quantite": 3}]}
	assert transport.cargaison_authoree(spec, get_doc) == [{"item": "item:viande", "poids": 2}] * 3


def test_cargaison_authoree_ignore_un_item_introuvable():
	spec = {"destination": "lieu:fumoir", "cargaison": [{"item": "item:fantome", "quantite": 2}]}
	assert transport.cargaison_authoree(spec, get_doc) == []
	assert transport.generer_transport_authore(spec, COMPTOIR, find_docs, get_doc) is None


def test_une_course_ecrite_se_livre_comme_une_autre():
	c = character()
	q = transport.generer_transport_authore(transport.offre_spec(BORIN), COMPTOIR, find_docs, get_doc)
	snap = transport.accepter_transport(c, q, now=1000)
	assert len(c["inventaire"]) == 2                       # les deux caisses sont dans le sac
	assert snap["expire_at"] == 1000 + 3600
	assert transport.transport_a_livrer(c, "lieu:fumoir") == snap
	assert transport.livrer_transport(c, snap) is True
	assert c["inventaire"] == []


def test_course_du_donneur():
	c = character()
	q = transport.generer_transport_authore(transport.offre_spec(BORIN), COMPTOIR, find_docs, get_doc)
	transport.accepter_transport(c, q, now=1000)
	# Le donneur peut relancer le joueur tant qu'il n'a pas livré ; le destinataire, lui, attend.
	assert transport.course_du_donneur(c, "lieu:guilde_comptoir")["id"] == "quete:transport_borin"
	assert transport.course_du_donneur(c, "lieu:fumoir") is None


# ── Géographie des lieux imbriqués ───────────────────────────────────────────────

def test_porte_effective_remonte_jusqu_a_la_porte_sur_la_ville():
	graphe = focalisation.charger_graphe(find_docs)
	portes = transport.portes_du_parent(graphe, "lieu:ville")
	# Le comptoir n'a pas de porte sur la ville : on sort par la réception de la guilde.
	assert "lieu:guilde_comptoir" not in portes
	assert transport.porte_effective(graphe, portes, "lieu:guilde_comptoir") == (20, 40)
	assert transport.porte_effective(graphe, portes, "lieu:fumoir") == (40, 20)


def test_indice_depuis_un_lieu_imbrique_donne_une_direction():
	indice = transport.indice_destination(COMPTOIR, "lieu:fumoir", find_docs, get_doc)
	assert indice["meme_ville"] is True
	# Sans le repli de `porte_effective`, la direction serait perdue (« à deux pas d'ici »).
	assert indice["direction"] == "nord-est"
	assert "au nord-est d'ici" in transport.texte_indice(indice)


# ── Courses à RETOUR : c'est le donneur qui solde, pas le destinataire ────────────

def _offre_retour():
	spec = dict(transport.offre_spec(BORIN), retour=True)
	spec["recompenses"] = {
		"xp": 30, "cuivre": 200,
		# La carte d'aventurier : objet générique, localisé à la volée par la cité du donneur.
		"items": [{"item": "item:carte", "poids": 0.05,
				   "lieu_parent": transport.LIEU_PARENT_AUTO}],
	}
	return transport.generer_transport_authore(spec, COMPTOIR, find_docs, get_doc)


def test_le_destinataire_d_une_course_a_retour_ne_paie_pas():
	c = character()
	sauves = []
	snap = transport.accepter_transport(c, _offre_retour(), now=1000)
	assert transport.livrer_transport(c, snap) is True      # la marchandise sort du sac
	recap = transport.livrer_en_attente_de_retour(c, snap, FUMOIR, get_doc, sauves.append, now=2000)
	assert "rayon" in recap
	assert c["xp_total"] == 0                               # rien n'est payé ici
	assert transport.transports_actifs(c) == [snap]         # la quête reste active
	assert snap["livree_at"] == 2000
	assert "expire_at" not in snap                          # le délai portait sur la livraison
	# Elle n'est plus « à livrer » (sinon le tenancier la reproposerait, cargaison en moins).
	assert transport.transport_a_livrer(c, "lieu:fumoir") is None
	assert transport.retour_attendu(c, "lieu:guilde_comptoir") == snap
	assert transport.retour_attendu(c, "lieu:fumoir") is None


def test_le_donneur_solde_la_course_a_retour_et_remet_ses_items():
	c = character()
	sauves = []
	snap = transport.accepter_transport(c, _offre_retour(), now=1000)
	transport.livrer_transport(c, snap)
	transport.livrer_en_attente_de_retour(c, snap, FUMOIR, get_doc, sauves.append, now=2000)

	recap = transport.rapporter_transport(c, snap, get_doc, sauves.append, now=3000)
	assert recap["xp"]["xp_gain"] == 30
	assert recap["relation"] == character_stats.RELATION_INITIALE + 1   # +1 chez le DONNEUR
	# La carte d'aventurier entre au sac en INSTANCE localisée : le comptoir relève de la ville,
	# c'est donc la carte de CETTE guilde-là que Borin remet.
	assert c["inventaire"] == [{"item": "item:carte", "poids": 0.05, "lieu_parent": "lieu:ville"}]
	assert transport.transports_actifs(c) == []
	assert c["quetes_terminees"][0]["echec"] is False
	# Course soldée → `unique` la scelle : Borin ne la repropose plus.
	assert transport.deja_reussie(c, snap["id"])


def test_une_course_sans_retour_se_solde_toujours_chez_le_destinataire():
	# Non-régression : les courses des marchands (pas de `retour`) paient sur place.
	c = character()
	sauves = []
	snap = transport.accepter_transport(c, offre(), now=1000)
	assert snap["retour"] is False
	transport.livrer_transport(c, snap)
	recap = transport.reussir_transport(c, snap, SALAISON, get_doc, sauves.append, now=2000)
	assert recap["xp"]["xp_gain"] > 0
	assert transport.transports_actifs(c) == []
	assert transport.retour_attendu(c, "lieu:boucherie") is None


# ── Le nom du PNJ vient du LIEU, jamais du doc générique ──────────────────────────

def test_nom_effectif_le_lieu_prime_sur_le_doc():
	doc = {"_id": "pnj:marchand_fumoir", "nom": "Maître Colin"}
	# La boutique rebaptise son tenancier : c'est CE nom que le dialogue doit prononcer.
	assert pnj.nom_effectif({"character": "pnj:marchand_fumoir", "nom": "Hermine Valcorbe"}, doc) \
		== "Hermine Valcorbe"
	# Sans surcharge, le doc générique fait repli (comportement historique).
	assert pnj.nom_effectif({"character": "pnj:marchand_fumoir"}, doc) == "Maître Colin"
	assert pnj.nom_effectif({}, {}) == "???"


def test_nom_pnj_du_lieu_sans_y_etre():
	# Magasin sans champ `pnj` : le tenancier implicite de la catégorie (nom du doc générique).
	docs = dict(DOCS, **{"pnj:marchand_fumoir": {"_id": "pnj:marchand_fumoir", "nom": "Maître Colin"}})
	get = docs.get
	assert pnj.nom_pnj_du_lieu(FUMOIR, get, transport.entree_marchand) == "Maître Colin"
	# Le même magasin, mais qui nomme sa tenancière : c'est elle qu'on annonce au joueur.
	fumoir_nomme = dict(FUMOIR, pnj=[{"character": "pnj:marchand_fumoir", "nom": "Hermine Valcorbe"}])
	assert pnj.nom_pnj_du_lieu(fumoir_nomme, get, transport.entree_marchand) == "Hermine Valcorbe"
	# Un lieu que personne ne tient (ni entrée `pnj`, ni recettes → pas de tenancier).
	assert pnj.nom_pnj_du_lieu(VILLE, get, transport.entree_marchand) is None


def test_un_dialogue_generique_prononce_le_nom_du_lieu():
	# Le doc est partagé par tous les fumoirs : son texte ne peut citer que {pnj}, jamais un nom.
	doc = {
		"_id": "pnj:marchand_fumoir", "nom": "Maître Colin",
		"dialogue": {"noeuds": {"accueil": {
			"texte": "{pnj} hume la viande en connaisseur.",
			"choix": [{"id": "ok", "label": "Merci, {pnj}."}],
		}}},
	}
	entree = {"character": "pnj:marchand_fumoir", "nom": "Hermine Valcorbe"}
	ctx = pnj.contexte_dialogue(character(), doc, lambda _l: 50,
								placeholders={"pnj": pnj.nom_effectif(entree, doc)})
	noeud = pnj.noeud_client(doc, "accueil", ctx)
	assert noeud["texte"] == "Hermine Valcorbe hume la viande en connaisseur."
	assert noeud["choix"][0]["label"] == "Merci, Hermine Valcorbe."   # les labels aussi


# ── Récompenses : l'objet remis est une INSTANCE, localisée par la guilde qui la délivre ──

def test_items_recompense_resout_la_sentinelle_auto():
	# Le comptoir relève de la ville → la carte remise est celle de la guilde de CETTE cité.
	items = transport.items_recompense(
		[{"item": "item:carte", "poids": 0.05, "lieu_parent": transport.LIEU_PARENT_AUTO}],
		COMPTOIR,
	)
	assert items == [{"item": "item:carte", "poids": 0.05, "lieu_parent": "lieu:ville"}]


def test_items_recompense_laisse_le_reste_intact():
	# Id littéral : recopié tel quel. Pas de clé : rien n'est ajouté — une épée n'est d'aucune ville.
	items = transport.items_recompense([
		{"item": "item:carte", "lieu_parent": "lieu:ailleurs"},
		{"item": "item:enclume", "poids": 500.0},
	], COMPTOIR)
	assert items == [
		{"item": "item:carte", "lieu_parent": "lieu:ailleurs"},
		{"item": "item:enclume", "poids": 500.0},
	]
	assert transport.items_recompense(None, COMPTOIR) == []


def test_items_recompense_donneur_sans_lieu_parent():
	# Un donneur qui EST déjà une ville est son propre parent.
	assert transport.items_recompense(
		[{"item": "item:carte", "lieu_parent": "auto"}], VILLE,
	) == [{"item": "item:carte", "lieu_parent": "lieu:ville"}]
	# Aucun lieu à nommer : on retire la clé plutôt que de laisser « auto » filer en base.
	assert transport.items_recompense(
		[{"item": "item:carte", "lieu_parent": "auto"}], {},
	) == [{"item": "item:carte"}]
