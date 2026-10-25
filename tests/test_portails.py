# tests/test_portails.py
# Portail de Notre-Dame (utils/portails.py, service `portail` de routers/pnj.py) : l'ancrage
# court-circuite un lien portail du monde et prend son point d'arrivée, contre un cristal jaune.
# Tableau des seuils tiré par tranche de l'epoch réel (aucune horloge), puis le contenu
# (dev/gen_portail_notre_dame.py) rejoué contre le dernier dump.

import importlib.util
import json
import os

import pytest
from fastapi import HTTPException

from models import character_stats
from utils import lint_dialogues, portails

ANCRAGE = "lieu:notre_dame_portail"
CRISTAL = "item:cristal_de_mana_jaune"
RACINE = os.path.join(os.path.dirname(__file__), "..")
FICHIER = os.path.join(RACINE, "jsons", "portail_notre_dame_a_importer.json")


def _lien(lid, a, b, type_="portail", status="ouvert"):
	return {"_id": lid, "type": "connection",
			"nodes": [{"lieu": a[0], "pos": list(a[1])}, {"lieu": b[0], "pos": list(b[1])}],
			"metadata": {"type": type_, "status": status}}


LIENS = [
	_lien("link:petra_khazneh_to_alexandrie", ("lieu:petra_khazneh", (0, 0)), ("lieu:alexandrie", (28, 33))),
	_lien("link:petra_ad_deir_to_bucarest", ("lieu:petra_ad_deir", (0, 0)), ("lieu:bucarest", (50, 19))),
	_lien("link:mu_to_notre_dame", ("lieu:mu", (3, 4)), (ANCRAGE, (0, 0))),
	_lien("link:auberge_to_ville", ("lieu:auberge", (0, 0)), ("lieu:ville", (1, 1)), type_="auberge"),
	_lien("link:portail_ferme", ("lieu:x", (0, 0)), ("lieu:y", (1, 1)), status="ferme"),
]
ARRIVEES = portails.arrivees_candidates(LIENS, ANCRAGE)
FENETRE = portails.fenetre_secondes()


# ── Arrivées ─────────────────────────────────────────────────────────────────

def test_chaque_noeud_d_un_portail_ouvert_est_une_arrivee_sauf_l_ancrage():
	assert {a["lieu"] for a in ARRIVEES} == {
		"lieu:petra_khazneh", "lieu:alexandrie", "lieu:petra_ad_deir", "lieu:bucarest", "lieu:mu"}
	alex = next(a for a in ARRIVEES if a["lieu"] == "lieu:alexandrie")
	assert alex["pos"] == [28, 33] and alex["lien"] == "link:petra_khazneh_to_alexandrie"


def test_un_portail_cree_plus_tard_entre_au_tableau_de_lui_meme():
	plus = LIENS + [_lien("link:rome_to_bruges", ("lieu:rome", (1, 2)), ("lieu:bruges", (3, 4)))]
	assert len(portails.arrivees_candidates(plus, ANCRAGE)) == len(ARRIVEES) + 2


# ── Tirage par tranche ───────────────────────────────────────────────────────

def test_meme_tranche_meme_tableau_pour_tous():
	t0 = 1_000 * FENETRE
	a = portails.seuils_ouverts(ARRIVEES, ANCRAGE, t0)
	b = portails.seuils_ouverts(ARRIVEES, ANCRAGE, t0 + FENETRE - 1)
	assert [s["cle"] for s in a] == [s["cle"] for s in b]
	assert len(a) == min(character_stats.PORTAIL_SEUILS_OUVERTS, len(ARRIVEES))
	assert len({s["cle"] for s in a}) == len(a)
	assert a[0]["ferme_dans_s"] == FENETRE and b[0]["ferme_dans_s"] == 1


def test_le_tableau_tourne_et_annonce_la_tranche_suivante():
	t0 = 1_000 * FENETRE
	tableaux = {tuple(sorted(s["cle"] for s in portails.seuils_ouverts(ARRIVEES, ANCRAGE, t0 + k * FENETRE)))
				for k in range(20)}
	assert len(tableaux) > 1
	suivants = [s["cle"] for s in portails.seuils_suivants(ARRIVEES, ANCRAGE, t0)]
	assert suivants == [s["cle"] for s in portails.seuils_ouverts(ARRIVEES, ANCRAGE, t0 + FENETRE)]


def test_le_nombre_de_seuils_suit_la_variable_de_monde(monkeypatch):
	monkeypatch.setattr(character_stats, "PORTAIL_SEUILS_OUVERTS", 2)
	assert len(portails.seuils_ouverts(ARRIVEES, ANCRAGE, 0)) == 2
	monkeypatch.setattr(character_stats, "PORTAIL_SEUILS_OUVERTS", 50)
	assert len(portails.seuils_ouverts(ARRIVEES, ANCRAGE, 0)) == len(ARRIVEES)


def test_une_tranche_de_grace_puis_le_seuil_se_referme():
	t0 = 1_000 * FENETRE
	cle = portails.seuils_ouverts(ARRIVEES, ANCRAGE, t0)[0]["cle"]
	assert portails.seuil_franchissable(ARRIVEES, ANCRAGE, cle, t0)
	# Tranche suivante : encore franchissable (grâce), sauf s'il y est retiré — ce qui compte,
	# c'est qu'il ne le soit plus deux tranches plus tard s'il n'est tiré dans aucune des deux.
	plus_tard = next(t0 + k * FENETRE for k in range(2, 200)
					 if all(cle not in [s["cle"] for s in portails.seuils_ouverts(ARRIVEES, ANCRAGE, t0 + j * FENETRE)]
							for j in (k - 1, k)))
	assert portails.seuil_franchissable(ARRIVEES, ANCRAGE, cle, plus_tard) is None
	assert portails.seuil_franchissable(ARRIVEES, ANCRAGE, "inconnu", t0) is None


def test_texte_duree():
	assert portails.texte_duree(100) == "1 min 40"
	assert portails.texte_duree(35) == "35 s"
	assert portails.texte_duree(120) == "2 min"


# ── Service `portail` (routers/pnj.py) ──────────────────────────────────────

CONF = {"ancrage": ANCRAGE, "cout": {"item": CRISTAL, "quantite": 1}, "choix": "franchir",
		"noeuds": {"ouvert": "ouvert", "ferme": "ferme", "refus_cristal": "refus_cristal"}}
PNJ = {"_id": "pnj:aenor_de_sully", "services": {"portail": CONF}}


@pytest.fixture
def rp(monkeypatch):
	from routers import pnj as rp
	t0 = 1_000 * FENETRE
	arrivees = []
	monkeypatch.setattr(rp, "find_docs", lambda q: LIENS)
	monkeypatch.setattr(rp, "get_doc", lambda i: {"_id": i, "label": i.split(":")[1]})
	monkeypatch.setattr(rp.quetes, "now_epoch", lambda: t0)
	monkeypatch.setattr(rp, "carried_weight", lambda c: 0)
	monkeypatch.setattr(rp, "charge_max_of", lambda c: 10)

	def _arrivee(character, destination, pos, lieu_doc):
		character["lieu"], character["position"] = destination, pos
		arrivees.append(destination)
		return {"moved": 1}
	monkeypatch.setattr(rp, "_effets_arrivee", _arrivee)
	rp._t0, rp._arrivees = t0, arrivees
	return rp


def test_franchir_relocalise_au_point_d_arrivee_et_consomme_un_cristal(rp):
	seuil = portails.seuils_ouverts(ARRIVEES, ANCRAGE, rp._t0)[0]
	c = {"lieu": ANCRAGE, "position": {"x": 0, "y": 0}, "inventaire": [CRISTAL, CRISTAL, "item:pain"]}
	rep = {}
	assert rp._resoudre_portail(c, PNJ, {"_id": ANCRAGE}, "franchir", seuil["cle"], rep) == "ouvert"
	assert c["lieu"] == seuil["lieu"] and c["position"] == {"x": seuil["pos"][0], "y": seuil["pos"][1]}
	assert c["inventaire"].count(CRISTAL) == 1 and "item:pain" in c["inventaire"]
	assert rep["portail"]["arrivee"] == {"moved": 1}


def test_sans_cristal_rien_ne_bouge(rp):
	seuil = portails.seuils_ouverts(ARRIVEES, ANCRAGE, rp._t0)[0]
	c = {"lieu": ANCRAGE, "inventaire": ["item:pain"]}
	assert rp._resoudre_portail(c, PNJ, {"_id": ANCRAGE}, "franchir", seuil["cle"], {}) == "refus_cristal"
	assert c["lieu"] == ANCRAGE and not rp._arrivees


def test_seuil_referme_ou_inconnu(rp):
	c = {"lieu": ANCRAGE, "inventaire": [CRISTAL]}
	assert rp._resoudre_portail(c, PNJ, {"_id": ANCRAGE}, "franchir", "inconnu", {}) == "ferme"
	assert c["inventaire"] == [CRISTAL] and not rp._arrivees


def test_on_ne_franchit_que_depuis_l_ancrage(rp):
	with pytest.raises(HTTPException):
		rp._resoudre_portail({"inventaire": [CRISTAL]}, PNJ, {"_id": "lieu:ailleurs"}, "franchir", "x", {})


def test_le_gabarit_devient_une_replique_par_seuil_ouvert(rp):
	noeud = {"id": "seuils", "choix": [{"id": "franchir", "label": "Franchir"}, {"id": "accueil", "label": "Non"}]}
	rp._choix_portail({}, PNJ, noeud)
	ouverts = portails.seuils_ouverts(ARRIVEES, ANCRAGE, rp._t0)
	assert [c["rejouer"]["saisie"] for c in noeud["choix"][:-1]] == [s["cle"] for s in ouverts]
	assert all(c["id"] == "franchir" and c["rejouer"]["noeud"] == "seuils" for c in noeud["choix"][:-1])
	assert noeud["choix"][-1]["id"] == "accueil"


# ── Contenu ──────────────────────────────────────────────────────────────────

def _gen():
	chemin = os.path.join(RACINE, "dev", "gen_portail_notre_dame.py")
	spec = importlib.util.spec_from_file_location("gen_portail_notre_dame", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


GEN = _gen()
with open(GEN.M.dernier_dump([]), encoding="utf-8") as _f:
	DUMP = {d["_id"]: d for d in json.load(_f)["docs"]}
DOCS = {d["_id"]: d for d in GEN.generer(DUMP)}


def test_le_fichier_est_a_jour_et_passe_le_linter():
	with open(FICHIER, encoding="utf-8") as f:
		fichier = json.load(f)
	assert fichier == list(DOCS.values())
	rapport = lint_dialogues.analyser(fichier)
	assert rapport["erreurs"] == 0 and rapport["avertissements"] == 0, rapport["trouvailles"]


def test_delta_seul_et_aucun_id_neuf_ne_collisionne():
	neufs = {i for i in DOCS if i not in DUMP}
	assert neufs == {GEN.AENOR, GEN.LIEN_PUITS}
	# Les docs relus ne perdent aucune clé du dump (PUT complet à l'import).
	for i in set(DOCS) - neufs:
		assert set(DUMP[i]) - {"_rev"} <= set(DOCS[i]), i


def test_aenor_tient_le_tableau_de_notre_dame():
	entree = next(e for e in DOCS[GEN.ANCRAGE]["pnj"] if e["character"] == GEN.AENOR)
	assert entree["probabilite"] == 1
	conf = DOCS[GEN.AENOR]["services"]["portail"]
	assert conf["ancrage"] == GEN.ANCRAGE and conf["cout"]["item"] in DUMP
	# Notre-Dame n'a AUCUN lien portail : le tableau en court-circuite, il n'en crée pas.
	assert not any(d.get("type") == "connection" and any(n["lieu"] == GEN.ANCRAGE for n in d["nodes"])
				   and (d.get("metadata") or {}).get("type") == "portail" for d in DOCS.values())
	assert portails.arrivees_candidates([d for d in DUMP.values() if d.get("type") == "connection"], GEN.ANCRAGE)


def test_les_portraits_existent():
	pnj_dir = os.path.join(RACINE, "templates", "resources", "pnj")
	assert os.path.isfile(os.path.join(pnj_dir, GEN.PORTRAIT_AENOR))
	assert os.path.isfile(os.path.join(pnj_dir, GEN.PORTRAIT_AELIS_INVALIDES))
	entree = next(e for e in DOCS[GEN.ARCHIVES]["pnj"] if e["character"] == GEN.AELIS_ARCHIVES)
	assert entree["portrait"] == GEN.PORTRAIT_AELIS_INVALIDES


# ── Le puits de Chartres : donjon à étages, coffre, remontée par la chaîne ───

def test_le_coffre_du_minotaure_garantit_un_cristal_jaune():
	donjon_doc = DOCS[GEN.M.DONJON_PUITS]
	assert donjon_doc["mode"] == "etages"
	(salle,) = donjon_doc["battle_maps"]
	tresor = salle["tresor"]
	assert {"item": CRISTAL, "quantite": 1} in tresor["garanti"]
	# Pas d'alarme : deux Minotaures de plus achèveraient n'importe quel groupe.
	assert "alarme" not in tresor["piege"]["effets"]
	for item in [tresor["piege"]["mimique"]] + [l["item"] for l in tresor["tirage"]["table"]]:
		assert item in DUMP, item


def test_on_descend_et_remonte_par_la_chaine_au_centre_du_puits():
	"""Auteur, 25/10 : on remonte par le centre du donjon, au bas du puits. Une seule connexion,
	celle du treuil : point d'apparition ET passage vers la surface. La grille est celle du dump
	(peinte dans l'éditeur) : le bas du puits et le coffre sont dans SA région praticable."""
	from utils import combat, donjon
	labyrinthe = DUMP[GEN.M.LABYRINTHE]
	assert GEN.M.LABYRINTHE not in DOCS   # la grille n'est jamais réécrite
	liens = [d for d in list(DOCS.values()) + list(DUMP.values()) if d.get("type") == "connection"
			 and any(n["lieu"] == GEN.M.LABYRINTHE for n in d["nodes"])]
	assert {d["_id"] for d in liens} == {GEN.LIEN_PUITS}
	(passage,) = donjon.passages_de_l_etage(liens[:1], GEN.M.LABYRINTHE, DOCS[GEN.M.DONJON_PUITS], str)
	assert passage["surface"] and passage["vers_lieu"] == GEN.M.CRYPTE
	assert (passage["pos"]["x"], passage["pos"]["y"]) == GEN.LABY_PUITS
	dims = labyrinthe["dimensions"]
	x, y = GEN.LABY_PUITS
	assert abs(x - dims["x"] // 2) <= 1 and abs(y - dims["y"] // 2) <= 2
	region = combat._reachable_region(labyrinthe["cells"], dims, labyrinthe.get("nav") or {}, GEN.LABY_PUITS)
	assert GEN.LABY_COFFRE in region
	assert len(region) == sum(row.count(1) for row in labyrinthe["cells"])
	# Le Templier fait descendre : laissez-passer posé, puis le treuil (`deplacer`).
	seuil = DOCS[GEN.M.TEMPLIER_CRYPTE]["dialogue"]["noeuds"]["seuil"]
	descendre = next(c for c in seuil["choix"] if c["id"] == "descendre")
	assert descendre["deplacer"] == GEN.M.LABYRINTHE
	assert descendre["action"] == {"service": "acces", "op": "passer"}
