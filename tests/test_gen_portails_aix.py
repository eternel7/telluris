# tests/test_gen_portails_aix.py
# Les cinq portes de la Chapelle Palatine (dev/gen_portails_aix.py), rejouées contre le dernier
# dump : un portail par temple de sortie, entré au tableau des seuils de Notre-Dame, temple gardé
# au rang A, case d'arrivée en ville praticable et jointe aux autres entrées de la cité.

import importlib.util
import os

from utils import acces, lint_dialogues, portails

RACINE = os.path.join(os.path.dirname(__file__), "..")


def _gen():
	chemin = os.path.join(RACINE, "dev", "gen_portails_aix.py")
	spec = importlib.util.spec_from_file_location("gen_portails_aix", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


GEN = _gen()
DUMP = {d["_id"]: d for d in GEN.ggi.charger_dump()}
ERREURS = []
DOCS = {d["_id"]: d for d in GEN.docs_portails(DUMP, ERREURS)
		+ [GEN.gardienne(DUMP[GEN.GARDIENNE])] + GEN.corrections(DUMP, ERREURS)}
LIENS = [d for d in DOCS.values() if d.get("type") == "connection"]


def test_aucune_erreur_ni_id_en_double():
	assert ERREURS == []
	assert len(DOCS) == len(GEN.docs_portails(DUMP, [])) + 1 + len(GEN.CORRECTIONS)


def test_une_porte_par_temple_et_toutes_au_tableau_des_seuils():
	portes = [l for l in LIENS if l["metadata"]["type"] == portails.TYPE_PORTAIL]
	assert len(portes) == len(GEN.TEMPLES)
	assert all(l["nodes"][0]["lieu"] == GEN.CHAPELLE for l in portes)
	arrivees = {a["lieu"] for a in portails.arrivees_candidates(portes, "lieu:notre_dame_portail")}
	assert arrivees == {t["lieu"] for t in GEN.TEMPLES} | {GEN.CHAPELLE}


def test_temples_gardes_au_rang_a_avec_leur_templier():
	for t in GEN.TEMPLES:
		temple = DOCS[t["lieu"]]
		assert acces.rang_min_du_lieu(temple) == "A"
		assert acces.conditions_invalides(temple) == []
		assert temple["pnj"][0]["character"] in DOCS
		assert temple.get("lieu_parent") == t["cite"] if t["cite"] else "lieu_parent" not in temple


def test_case_d_arrivee_praticable_et_jointe_aux_entrees_de_la_cite():
	for t in GEN.TEMPLES:
		if not t["cite"]:
			continue
		cite = DUMP[t["cite"]]
		lien = next(l for l in LIENS if l["metadata"]["type"] == "temple" and l["nodes"][1]["lieu"] == t["lieu"])
		x, y = lien["nodes"][0]["pos"]
		zone = GEN.zone_de(cite["cells"], (x, y), cite.get("nav"))
		assert (x, y) in zone
		autres = [tuple(n["pos"]) for d in DUMP.values() if d.get("type") == "connection"
			for n in d["nodes"] if n["lieu"] == t["cite"] and n.get("pos")]
		if autres:   # Tokyo et Teotihuacan n'ont encore aucune entrée : rien à rejoindre
			assert any(p in zone for p in autres), t["cite"]


def test_dialogues_des_templiers_sans_faute():
	rapport = lint_dialogues.analyser(list(DOCS.values()))
	assert rapport["analyses"] >= len(GEN.TEMPLES)
	assert rapport["erreurs"] == 0 and rapport["avertissements"] == 0, rapport["trouvailles"]


RETOUR = ("Retourner", "Ressortir", "Remonter", "Revenir", "Aix-la-Chapelle — repasser")


def test_label_d_un_noeud_mene_a_ce_noeud():
	"""Le bouton affiché est le label du nœud DESTINATION : un label de retour se pose sur le
	nœud du lieu où l'on RETOURNE (la cité, la chapelle, la crypte), jamais sur le sous-lieu."""
	assert set(GEN.CORRECTIONS) <= set(DOCS)
	for lien in LIENS:
		for k, n in enumerate(lien["nodes"]):
			autre = lien["nodes"][1 - k]
			if (n.get("label") or "").startswith(RETOUR):
				parent = (DOCS.get(n["lieu"]) or DUMP.get(n["lieu"]) or {}).get("lieu_parent")
				assert parent != autre["lieu"], (lien["_id"], n)
	portes = [l for l in LIENS if l["metadata"]["type"] == portails.TYPE_PORTAIL]
	assert all(l["nodes"][0]["bouton"] is False and "bouton" not in l["nodes"][1] for l in portes)
	assert all(l["nodes"][1]["label"].startswith("Franchir") for l in portes)


def test_la_gardienne_tient_le_tableau_fixe_au_rang_a():
	g = DOCS[GEN.GARDIENNE]
	conf = g["services"]["portail"]
	assert conf["fixe"] is True and conf["ancrage"] == GEN.CHAPELLE and "cout" not in conf
	choix = next(c for c in g["dialogue"]["noeuds"]["accueil"]["choix"] if c["id"] == "seuils")
	assert choix["condition"] == GEN.RANG_A
	# Rien du dump n'est perdu (PUT complet) : le dialogue d'avant est toujours là.
	assert set(DUMP[GEN.GARDIENNE]["dialogue"]["noeuds"]) <= set(g["dialogue"]["noeuds"])
