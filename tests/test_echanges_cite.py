"""Échanges des ateliers d'un bien avec les boutiques de SA cité (`utils/echanges_cite.py`).

Ce que ces tests verrouillent (décisions de l'Auteur, 12/11/2026) :
1. **Le temps** : une passe par période (±aléa), plafond de rattrapage, reste conservé, aucune
   passe rétroactive au premier passage.
2. **Chaque boutique est un acheteur distinct** : prix du PROPRIÉTAIRE chez elle (sa relation),
   refus dès que son stock atteint sa cible, plus offrant d'abord, marchandise posée chez elle.
3. **Négociant** : décote sans lui, bonus de niveau avec lui (jamais au-delà de pmax) ; achats
   seulement avec lui, seulement aux boutiques qui ont TROP, en réserve (jamais revendus tels
   quels) ; niveau dérivé ; « Tenir les livres » réservé au Lettré ; formation payée.
4. **Bornes** : portage, caisse pleine, crieur au plancher, option `vente_cite`.
5. **Ce qui produit seul** : jardinier (réserve seule, plafonnée), récoltes vers le négociant ou
   le Rangement (plein ⇒ elle attend).

Recettes et docs en mémoire (gabarit `tests/test_proprietes_ateliers.py`), hasard injecté.
"""

import pytest

from models import character_stats
from utils import echanges_cite as ec
from utils import marche
from utils import negoce
from utils import proprietes


def _item(ident, valeur=(10, 20), poids=1.0, cat="composant"):
	return {"_id": f"item:{ident}", "type": "item", "nom": ident.capitalize(), "categorie": cat,
			"sous_categorie": ident, "slots": [], "poids": poids, "rarete": "commun",
			"valeur": [{"cu": valeur[0]}, {"cu": valeur[1]}]}


PEAU, TENDON, ARC = _item("peau", (4, 8)), _item("tendon"), _item("arc", (100, 300), cat="arme")
GRAINES, HERBE = _item("graines", (1, 2), 0.1), _item("herbe", (2, 4), 0.2)

RECETTES = [
	{"_id": "recette:tendon", "type": "recette", "lieu_categorie": "tannerie_test",
	 "objet_final": "tendon", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "peau", "quantite": 1}]},
	{"_id": "recette:arc", "type": "recette", "lieu_categorie": "armurerie_test",
	 "objet_final": "arc", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "tendon", "quantite": 2}]},
	{"_id": "recette:peau", "type": "recette", "lieu_categorie": "boucherie_test",
	 "objet_final": "peau", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "os", "quantite": 1}]},
	{"_id": "recette:herbe", "type": "recette", "lieu_categorie": "jardin_test",
	 "objet_final": "herbe", "quantite_produite": 1,
	 "matieres_premieres": [{"sous_categorie": "graines", "quantite": 1}]},
]

VILLE = {"_id": "lieu:ville", "type": "lieu", "categorie": "ville"}
CIBLE = 25          # STOCK_CIBLE_DEFAUT, fixé par la fixture
DOCS = {}

CAT = {
	"types": [{"id": "maison", "label": "Maison", "occupants_max": 2, "personnel_max": 9, "stockage_kg": 2}],
	"amenagements": [
		{"id": "tannerie", "nom": "Tannerie", "types_autorises": ["maison"], "capacite": {"postes": {"tanneur": 1}},
		 "activite": {"metier": "tanneur", "label": "Tannerie", "categories": ["tannerie_test"]}},
		{"id": "bureau", "nom": "Bureau", "types_autorises": ["maison"], "capacite": {"postes": {"marchand": 1}},
		 "activite": {"metier": "marchand", "label": "Négoce", "categories": ["negociant"]},
		 "effets_poste": {"achats_cite": True}},
		{"id": "jardin", "nom": "Jardin", "types_autorises": ["maison"], "capacite": {"postes": {"jardinier": 1}},
		 "activite": {"metier": "jardinier", "label": "Jardinage", "categories": ["jardin_test"]},
		 "effets_poste": {"autoproduction": True}},
		{"id": "remise", "nom": "Remise", "types_autorises": ["maison"], "capacite": {"postes": {"charretier": 1}},
		 "effets_poste": {"portage_kg": 200}},
		{"id": "etal", "nom": "Étal", "types_autorises": ["maison"], "capacite": {"postes": {"crieur": 1}},
		 "effets_poste": {"crieur": {"unites": 2}}},
		{"id": "potager", "nom": "Petit jardin", "types_autorises": ["maison"],
		 "effets": {"recolte": {"items": ["item:herbe"], "quantite": 2, "delai_s": 86400}}},
	],
	"metiers": [{"id": m, "label": m.capitalize()} for m in ("tanneur", "marchand", "jardinier", "charretier", "crieur")],
	"reglages": {},
}


class _Rand:
	"""Hasard déterministe : `random()` constant, `sample` = les k premiers (ordre donné)."""
	def __init__(self, v=0.0):
		self.v = v

	def random(self):
		return self.v

	def sample(self, seq, k):
		return list(seq)[:k]

	def choice(self, seq):
		return seq[0]


@pytest.fixture(autouse=True)
def _monde(monkeypatch):
	DOCS.clear()
	DOCS.update({d["_id"]: d for d in (PEAU, TENDON, ARC, GRAINES, HERBE, VILLE)})
	resoudre = lambda i: (dict(DOCS[i], item=i) if isinstance(i, str) and i in DOCS
						  else (dict(DOCS[i["item"]], item=i["item"]) if isinstance(i, dict) and i.get("item") in DOCS else None))
	monkeypatch.setattr(marche, "_all_recettes", lambda: RECETTES)
	monkeypatch.setattr(marche, "get_doc", lambda i: DOCS.get(i))
	for mod in (marche, proprietes, ec, negoce):
		monkeypatch.setattr(mod, "resolve_item_ref", resoudre, raising=False)
	monkeypatch.setattr(ec, "item_ref_weight", lambda r: (resoudre(r) or {}).get("poids", 0))
	monkeypatch.setattr(proprietes, "item_ref_weight", lambda r: (resoudre(r) or {}).get("poids", 0))
	monkeypatch.setattr(marche.random, "random", lambda: 0.0)
	monkeypatch.setattr(character_stats, "ATELIER_TRANSFO_PROBA", 1.0)
	monkeypatch.setattr(character_stats, "STOCK_CIBLE_DEFAUT", CIBLE)
	monkeypatch.setattr(character_stats, "APPRO_DEBIT_DEFAUT", 5)
	monkeypatch.setattr(character_stats, "FLUX_SURPLUS_PART", 0.0)
	monkeypatch.setattr(character_stats, "LIEU_CATEGORIES_FUSION", {})
	marche.reset_prix_cache()
	yield
	marche.reset_prix_cache()


def boutique(ident, categorie, **champs):
	b = {"_id": f"lieu:{ident}", "type": "lieu", "label": ident, "categorie": categorie,
		 "lieu_parent": VILLE["_id"], "stock_matieres": {}, "stock_vente": []}
	b.update(champs)
	DOCS[b["_id"]] = b
	return b


def propriete(**champs):
	p = {"_id": "propriete:maison_1", "type": "propriete", "type_propriete": "maison", "mode": "achat",
		 "statut": "possedee", "proprietaire": "character:a", "lieu_parent": VILLE["_id"],
		 "amenagements": ["tannerie", "bureau", "jardin", "remise", "etal"], "employes": [], "coffre": []}
	p.update(champs)
	DOCS[p["_id"]] = p
	return p


def employe(prop, poste, metier, categorie, **champs):
	cand = {"id": "c", "amenagement": poste, "metier": metier, "prenom": metier, "nom": "X",
			"categorie": categorie, "modele": proprietes.MODELE_PREFIXE + categorie}
	e = proprietes.creer_employe(prop, cand, {"_id": prop["proprietaire"]})
	e["_id"] = f"employe:{metier}"
	e.update(champs)
	DOCS[e["_id"]] = e
	proprietes.engager(prop, e)
	return e


def contexte(prop, employes, boutiques, rand=None):
	return ec.Contexte(prop, CAT, employes, boutiques, DOCS.get, rand or _Rand(0.0), 1_000_000)


def _rayon(doc, item_id):
	return next((e["qty"] for e in doc.get("stock_vente") or [] if e["item_id"] == item_id), 0)


# ── 1. Le temps ───────────────────────────────────────────────────────────────────

def test_premier_passage_aucune_passe_retroactive():
	assert ec.passes_ecoulees({}, ec.ECHANGES_DEFAUT, 10_000, _Rand(0.5)) == (0, 10_000)


def test_une_passe_par_periode_et_le_reste_conserve():
	periode = ec.ECHANGES_DEFAUT["periode_s"]
	now = 1_000_000
	# random 0.5 ⇒ période exacte ; 3,5 périodes écoulées ⇒ 3 passes, la demie reste à courir.
	n, at = ec.passes_ecoulees({"echanges_at": now - int(3.5 * periode)}, ec.ECHANGES_DEFAUT, now, _Rand(0.5))
	assert n == 3 and at == now - int(0.5 * periode)


def test_rattrapage_plafonne():
	regl = ec.ECHANGES_DEFAUT
	n, _at = ec.passes_ecoulees({"echanges_at": 1}, regl, 10_000_000, _Rand(0.5))
	assert n == regl["rattrapage_max_s"] // regl["periode_s"]


def test_la_periode_varie_avec_le_hasard():
	regl, now = ec.ECHANGES_DEFAUT, 1_000_000
	debut = now - 6 * regl["periode_s"]
	courtes = ec.passes_ecoulees({"echanges_at": debut}, regl, now, _Rand(0.0))[0]
	longues = ec.passes_ecoulees({"echanges_at": debut}, regl, now, _Rand(0.99))[0]
	assert courtes > 6 > longues


# ── 2. Chaque boutique est un acheteur distinct ───────────────────────────────────

def test_refus_des_que_le_stock_atteint_la_cible():
	prop = propriete()
	pleine = boutique("arm_b", "armurerie_test", stock_matieres={"tendon": CIBLE})
	manque = boutique("arm_a", "armurerie_test", stock_matieres={"tendon": 2})
	ctx = contexte(prop, [], [pleine, manque])
	assert ec.prix_vente_boutique(ctx, pleine, dict(TENDON, item=TENDON["_id"])) is None
	assert ec.prix_vente_boutique(ctx, manque, dict(TENDON, item=TENDON["_id"])) is not None


def test_celle_qui_manque_paie_plus_que_celle_qui_a_presque_assez():
	prop = propriete()
	a = boutique("arm_a", "armurerie_test", stock_matieres={"tendon": 2})
	c = boutique("arm_c", "armurerie_test", stock_matieres={"tendon": CIBLE - 2})
	ctx = contexte(prop, [], [a, c])
	t = dict(TENDON, item=TENDON["_id"])
	assert ec.prix_vente_boutique(ctx, a, t) > ec.prix_vente_boutique(ctx, c, t)


def test_prix_du_proprietaire_sa_relation_compte():
	prop = propriete()
	a = boutique("arm_a", "armurerie_test", stock_matieres={"tendon": CIBLE - 1})
	t = dict(TENDON, item=TENDON["_id"])
	neutre = ec.prix_vente_boutique(contexte(prop, [], [a]), a, t)
	DOCS[marche.relation_doc_id({"_id": "character:a"}, a)] = {"value": 100}
	ami = ec.prix_vente_boutique(contexte(prop, [], [a]), a, t)
	assert ami > neutre


def test_decote_sans_negociant_bonus_borne_avec():
	prop = propriete()
	a = boutique("arm_a", "armurerie_test", stock_matieres={"tendon": CIBLE - 1})
	t = dict(TENDON, item=TENDON["_id"])
	seul = ec.prix_vente_boutique(contexte(prop, [], [a]), a, t)
	neg = employe(prop, "bureau", "marchand", "negociant", negoce_xp=10 ** 9)
	avec = ec.prix_vente_boutique(contexte(prop, [neg], [a]), a, t)
	pmin, pmax, _s = marche.params_vente_lieu(a, t, TENDON["_id"])
	assert seul < avec <= pmax


def test_vente_au_plus_offrant_marchandise_chez_l_acheteur_cuivre_en_caisse():
	prop = propriete()
	a = boutique("arm_a", "armurerie_test", stock_matieres={"tendon": CIBLE - 3})
	c = boutique("arm_c", "armurerie_test", stock_matieres={"tendon": 0})
	pleine = boutique("arm_b", "armurerie_test", stock_matieres={"tendon": CIBLE + 5})
	tan = employe(prop, "tannerie", "tanneur", "tannerie_test", stock_vente=[{"item_id": TENDON["_id"], "qty": 5}])
	ctx = contexte(prop, [tan], [a, pleine, c])
	ec.vendre(ctx, tan)
	# 4 vendus (réserve 1), tous chez celle qui manque le plus, qui paie le mieux.
	assert _rayon(tan, TENDON["_id"]) == ec.ECHANGES_DEFAUT["reserve"]
	assert c["stock_matieres"]["tendon"] == 4 and a["stock_matieres"]["tendon"] == CIBLE - 3
	assert pleine["stock_matieres"]["tendon"] == CIBLE + 5
	assert tan["caisse_cuivre"] == ctx.gain > 0 and set(ctx.touchees) == {c["_id"]}


def test_portage_borne_la_passe():
	prop = propriete(amenagements=["tannerie"])
	a = boutique("arm_a", "armurerie_test")
	tan = employe(prop, "tannerie", "tanneur", "tannerie_test", stock_vente=[{"item_id": TENDON["_id"], "qty": 99}])
	ctx = contexte(prop, [tan], [a])
	ec.vendre(ctx, tan)
	assert a["stock_matieres"]["tendon"] == int(ec.ECHANGES_DEFAUT["portage_kg"] // TENDON["poids"])


def test_caisse_pleine_ventes_en_pause():
	prop = propriete()
	a = boutique("arm_a", "armurerie_test")
	tan = employe(prop, "tannerie", "tanneur", "tannerie_test", caisse_cuivre=10 ** 9,
				  stock_vente=[{"item_id": TENDON["_id"], "qty": 5}])
	ec.vendre(contexte(prop, [tan], [a]), tan)
	assert _rayon(tan, TENDON["_id"]) == 5


def test_vente_interdite_ni_cite_ni_crieur():
	prop = propriete()
	a = boutique("arm_a", "armurerie_test")
	crieur = employe(prop, "etal", "crieur", "")
	tan = employe(prop, "tannerie", "tanneur", "tannerie_test", vente_cite=False,
				  stock_vente=[{"item_id": TENDON["_id"], "qty": 5}])
	ctx = contexte(prop, [tan, crieur], [a])
	inv = ec.vendre(ctx, tan)
	ec.crier(ctx, tan, {TENDON["_id"]}, [5])
	assert inv == set() and _rayon(tan, TENDON["_id"]) == 5 and not tan["caisse_cuivre"]


def test_crieur_vend_au_plancher_ce_que_nulle_boutique_ne_prend():
	prop = propriete()
	pleine = boutique("arm_b", "armurerie_test", stock_matieres={"tendon": CIBLE})
	crieur = employe(prop, "etal", "crieur", "")
	tan = employe(prop, "tannerie", "tanneur", "tannerie_test", stock_vente=[{"item_id": TENDON["_id"], "qty": 9}])
	ctx = contexte(prop, [tan, crieur], [pleine])
	inv = ec.vendre(ctx, tan)
	ec.crier(ctx, tan, inv, [ctx.crieur])
	plancher = round(TENDON["valeur"][0]["cu"] * character_stats.RACHAT_FACTEUR)
	assert inv == {TENDON["_id"]} and ctx.crieur == 2
	assert _rayon(tan, TENDON["_id"]) == 7 and tan["caisse_cuivre"] == 2 * plancher


# ── 3. Acheter : seulement avec un négociant, aux boutiques qui ont trop ──────────

def _monde_achat(negociant=True):
	prop = propriete()
	trop = boutique("bou_a", "boucherie_test", stock_vente=[{"item_id": PEAU["_id"], "qty": CIBLE + 10}])
	juste = boutique("bou_b", "boucherie_test", stock_vente=[{"item_id": PEAU["_id"], "qty": CIBLE}])
	tan = employe(prop, "tannerie", "tanneur", "tannerie_test", caisse_cuivre=1000)
	emps = [tan] + ([employe(prop, "bureau", "marchand", "negociant")] if negociant else [])
	return prop, tan, trop, juste, contexte(prop, emps, [juste, trop])


def test_sans_negociant_aucun_achat():
	_p, tan, trop, _j, ctx = _monde_achat(negociant=False)
	ec.acheter(ctx, tan)
	assert not tan["stock_matieres"] and _rayon(trop, PEAU["_id"]) == CIBLE + 10


def test_achat_aux_seules_boutiques_qui_ont_trop_en_reserve_paye_par_la_caisse():
	_p, tan, trop, juste, ctx = _monde_achat()
	ec.acheter(ctx, tan)
	cible = ec.ECHANGES_DEFAUT["achat_cible"]
	assert tan["stock_matieres"] == {"peau": cible}
	assert _rayon(trop, PEAU["_id"]) == CIBLE + 10 - cible and _rayon(juste, PEAU["_id"]) == CIBLE
	assert tan["caisse_cuivre"] < 1000 and not tan["stock_vente"]           # jamais en rayon


def test_jamais_sous_la_cible_du_vendeur():
	prop = propriete()
	peu = boutique("bou_a", "boucherie_test", stock_vente=[{"item_id": PEAU["_id"], "qty": CIBLE + 2}])
	tan = employe(prop, "tannerie", "tanneur", "tannerie_test", caisse_cuivre=1000)
	ec.acheter(contexte(prop, [tan, employe(prop, "bureau", "marchand", "negociant")], [peu]), tan)
	assert _rayon(peu, PEAU["_id"]) == CIBLE and tan["stock_matieres"]["peau"] == 2


def test_achat_puis_revente_jamais_gagnant():
	"""Le prix d'achat ne descend jamais sous pmin ; ce qui est acheté entre en RÉSERVE, et
	la vente ne puise que le rayon : la même matière ne peut pas repartir plus cher."""
	_p, tan, trop, _j, ctx = _monde_achat()
	p = dict(PEAU, item=PEAU["_id"])
	prix = ec.prix_achat_boutique(ctx, trop, p)
	assert prix >= marche.prix_achat_lieu(trop, p, PEAU["_id"])[0]
	ec.acheter(ctx, tan)
	assert ec.vendre(ctx, tan) == set() and _rayon(tan, PEAU["_id"]) == 0


def test_caisse_vide_aucun_achat():
	_p, tan, trop, _j, ctx = _monde_achat()
	tan["caisse_cuivre"] = 0
	ec.acheter(ctx, tan)
	assert not tan["stock_matieres"]


# ── Le négociant progresse ────────────────────────────────────────────────────────

def test_niveau_derive_de_l_experience():
	regln = ec.NEGOCIANT_DEFAUT
	assert ec.niveau_negociant({}, regln) == 1
	assert ec.niveau_negociant({"negoce_xp": regln["seuils_xp"][2]}, regln) == 3
	assert ec.niveau_negociant({"negoce_xp": 10 ** 9}, regln) == len(regln["seuils_xp"])


def test_tenir_les_livres_reserve_au_lettre_une_fois_par_delai():
	prop = propriete()
	neg = employe(prop, "bureau", "marchand", "negociant")
	regln = ec.NEGOCIANT_DEFAUT
	assert not ec.tenir_les_livres({"voc": "guerrier"}, neg, regln, now=1000)[0]
	ok, _r, pts = ec.tenir_les_livres({"voc": "lettre"}, neg, regln, now=1000)
	assert ok and pts == ec.gain_seance({}, regln) and neg["negoce_xp"] == pts
	assert not ec.tenir_les_livres({"voc": "lettre"}, neg, regln, now=1001)[0]
	assert ec.tenir_les_livres({"voc": "lettre"}, neg, regln, now=1000 + regln["seance_delai_s"])[0]


def test_formation_delai_distinct_et_cout():
	prop = propriete()
	neg = employe(prop, "bureau", "marchand", "negociant")
	regln = ec.NEGOCIANT_DEFAUT
	cout = ec.cout_formation(neg, regln)
	assert cout == ec.gain_seance(neg, regln) * regln["formation_cout_par_xp"]
	assert ec.tenir_les_livres({"voc": "lettre"}, neg, regln, now=1000)[0]
	assert ec.former(neg, regln, now=1000)[0]                 # délai distinct
	assert not ec.former(neg, regln, now=1001)[0]


def test_negociant_au_niveau_maximal_n_apprend_plus():
	neg = {"type": "employe", "categorie": "negociant", "statut": "employe", "negoce_xp": 10 ** 9}
	assert ec.gain_seance(neg, ec.NEGOCIANT_DEFAUT) == 0
	assert not ec.former(neg, ec.NEGOCIANT_DEFAUT, now=1)[0]


# ── 5. Ce qui produit seul ────────────────────────────────────────────────────────

def test_jardinier_autoproduit_en_reserve_plafonnee_jamais_au_comptoir():
	prop = propriete()
	jar = employe(prop, "jardin", "jardinier", "jardin_test")
	assert ec.autoproduit(jar, CAT) and not ec.autoproduit(employe(prop, "tannerie", "tanneur", "tannerie_test"), CAT)
	for _ in range(20):
		ec.autoproduire(jar)
	assert jar["stock_matieres"] == {"graines": CIBLE} and jar["stock_vente"] == []


def test_recolte_vers_le_rangement_et_plein_elle_attend():
	prop = propriete(amenagements=["potager"])
	lignes = ec.cueillir(prop, CAT, None, None, DOCS.get, _Rand(0.0), 1000)
	assert len(prop["coffre"]) == 2 and lignes[0]["lieu"] == "Rangement"
	# Rangement de 2 kg : 2 herbes de 0,2 kg passent encore, puis plus rien.
	prop["coffre"] = ["item:arc"] * 10                     # 10 kg : plein
	prop["recoltes_at"] = {}
	assert ec.cueillir(prop, CAT, None, None, DOCS.get, _Rand(0.0), 2000) == []
	assert prop["recoltes_at"] == {} and len(prop["coffre"]) == 10


def test_recolte_confiee_au_negociant_si_sa_vente_est_autorisee():
	prop = propriete(amenagements=["potager", "bureau"])
	neg = employe(prop, "bureau", "marchand", "negociant")
	flux = proprietes.flux_propriete(prop)
	ec.cueillir(prop, CAT, neg, flux, DOCS.get, _Rand(0.0), 1000)
	assert prop["coffre"] == [] and (neg["caisse_cuivre"] or neg["stock_vente"] or flux["pool"])
	neg["vente_cite"] = False
	prop["recoltes_at"] = {}
	ec.cueillir(prop, CAT, neg, flux, DOCS.get, _Rand(0.0), 2000)
	assert len(prop["coffre"]) == 2


# ── Le chokepoint ─────────────────────────────────────────────────────────────────

def test_rattraper_produit_vend_et_avance_l_horloge():
	periode = ec.ECHANGES_DEFAUT["periode_s"]
	now = 1_000_000
	prop = propriete(amenagements=["tannerie"], echanges_at=now - 3 * periode)
	a = boutique("arm_a", "armurerie_test")
	tan = employe(prop, "tannerie", "tanneur", "tannerie_test", stock_matieres={"peau": 6})
	bilan = ec.rattraper(prop, CAT, DOCS.get, lambda q: [a] if q.get("lieu_parent") == VILLE["_id"] else [],
						 _Rand(0.49), now)
	assert bilan["passes"] == 3 and bilan["gain"] > 0 and a["stock_matieres"]["tendon"] > 0
	assert bilan["a_sauver"][-1] is prop and a in bilan["a_sauver"] and tan in bilan["a_sauver"]
	assert prop["echanges_at"] > now - periode and prop["echanges_journal"][0]["sens"] == "vente"


def test_rattraper_sans_passe_ne_sauve_que_le_premier_passage():
	prop = propriete()
	assert ec.rattraper(prop, CAT, DOCS.get, lambda q: [], _Rand(0.5), 5000)["a_sauver"] == [prop]
	assert ec.rattraper(prop, CAT, DOCS.get, lambda q: [], _Rand(0.5), 5001)["a_sauver"] == []


def test_boutiques_de_la_cite_sans_negociant_ni_revendeur():
	b = boutique("arm_a", "armurerie_test")
	neg = boutique("neg", "negociant")
	assert ec.boutiques_cite(VILLE["_id"], lambda q: [b, neg, VILLE]) == [b]


def test_biens_a_rattraper_de_la_cite_courante():
	prop = propriete()
	ailleurs = dict(propriete(), _id="propriete:maison_2", lieu_parent="lieu:autre")
	DOCS[ailleurs["_id"]] = ailleurs
	perso = {"_id": "character:a", "proprietes": [prop["_id"], ailleurs["_id"]]}
	dans_la_ville = boutique("arm_a", "armurerie_test")
	ids = [p["_id"] for p in ec.biens_a_rattraper(perso, dans_la_ville, DOCS.get)]
	assert ids == [prop["_id"]]
	assert [p["_id"] for p in ec.biens_a_rattraper(perso, VILLE, DOCS.get)] == [prop["_id"]]


def test_est_cite_predicat_unique():
	assert marche.est_cite(VILLE) and not marche.est_cite({"categorie": "pays"}) and not marche.est_cite(None)
