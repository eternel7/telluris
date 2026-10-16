# tests/test_correctifs_dialogues.py
# Correctifs de cohérence des dialogues (dev/gen_correctifs_dialogues.py) : rejoués contre le
# DERNIER dump, puis contrôlés état par état — choix visibles avant / pendant / après, présences,
# accords neutres du joueur, tutoiement tenu par Borin.

import importlib.util
import json
import os
import re

import pytest

from utils import acces, pnj
from utils.lint_dialogues import analyser

RACINE = os.path.join(os.path.dirname(__file__), "..")
CONVOI = "quete:escorte_convoi_de_lutecia"
BUCHERONS = "quete:escorte_bucherons_d_auxerre"


def _gen():
	chemin = os.path.join(RACINE, "dev", "gen_correctifs_dialogues.py")
	spec = importlib.util.spec_from_file_location("gen_correctifs_dialogues", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


GEN = _gen()
BASE, _NOM = GEN.dernier_dump()
DOCS = {d["_id"]: d for d in GEN.corriger(BASE)}


def _visibles(pnj_id, noeud="accueil", actives=(), reussies=(), flags=None):
	contexte = {"quetes_actives": set(actives), "quetes_reussies": set(reussies), "flags": flags or {}}
	return {c["id"] for c in pnj._choix_visibles(DOCS[pnj_id], noeud, contexte)}


# Donneurs des deux escortes, pour le sous-filtre `giver_categorie` des barrières.
GIVERS = {"lieu:cathedrale": {"categorie": "cathedral"}, "lieu:bureau": {"categorie": "bureau_maitre_guilde"}}
CONVOI_ACTIF = {"id": CONVOI, "giver": "lieu:cathedrale",
				"objectif": {"type": "escorte", "cible": "lieu:notre_dame"}}
BUCHERONS_ACTIF = {"id": BUCHERONS, "giver": "lieu:bureau",
				   "objectif": {"type": "escorte", "cible": "lieu:bureau_du_maitre_de_guilde_d_auxerre"}}


def _perso(actives=(), reussies=()):
	return {"quetes_actives": list(actives), "quetes_terminees": [{"id": q, "echec": False} for q in reussies]}


def _present(lieu_id, pnj_id, character):
	entree = next(e for e in DOCS[lieu_id]["pnj"] if e["character"] == pnj_id)
	return acces.clauses_remplies(character, entree.get("conditions"), GIVERS.get)


# ── Le fichier ────────────────────────────────────────────────────────────────────

def test_le_correctif_passe_le_linter():
	rapport = analyser(list(DOCS.values()))
	assert rapport["erreurs"] == 0, [t for t in rapport["trouvailles"] if t.get("niveau") == "erreur"]


def test_regeneration_idempotente():
	"""Rejoué sur un dump qui porte déjà les correctifs : plus rien à écrire."""
	corrige = dict(BASE)
	corrige.update(DOCS)
	assert GEN.corriger(corrige) == []


def test_conditions_de_presence_lisibles():
	for lid in ("lieu:la_cour_des_arches", "lieu:auberge_de_la_tour_de_l_horloge"):
		assert acces.conditions_pnj_invalides(DOCS[lid]) == []


# ── Rang C de Lutecia : avec ou sans l'arc d'Auxerre ──────────────────────────────

def test_aelis_retrouvailles_ou_premiere_rencontre():
	aelis = "pnj:aelis_de_montfaucon_cour_des_arches"
	assert DOCS[aelis]["dialogue"]["noeud_depart"] == "cour"
	assert _visibles(aelis, "cour") == {"approcher_inconnu", "fin"}
	assert _visibles(aelis, "cour", reussies=[CONVOI]) == {"approcher", "fin"}
	# La conclusion qui parle de la grotte n'est servie qu'à qui l'a vécue.
	assert _visibles(aelis, "retrouvailles_05") == {"conclure_inconnu"}
	assert _visibles(aelis, "retrouvailles_05", reussies=[CONVOI]) == {"conclure"}
	assert _visibles(aelis, "lettre_lue") == {"mission"}
	assert _visibles(aelis, "lettre_lue", reussies=[CONVOI]) == {"connu", "mission"}
	for nid in ("inconnu_01", "inconnu_02", "inconnu_fin", "lettre_lue", "mission_acceptee"):
		assert "grotte" not in DOCS[aelis]["dialogue"]["noeuds"][nid]["texte"], nid
		assert "Vous le savez" not in DOCS[aelis]["dialogue"]["noeuds"][nid]["texte"], nid


def test_aelis_absente_de_lutecia_pendant_l_arc_d_auxerre():
	lieu, aelis = "lieu:la_cour_des_arches", "pnj:aelis_de_montfaucon_cour_des_arches"
	assert _present(lieu, aelis, _perso())                                      # jamais allé à Auxerre
	assert not _present(lieu, aelis, _perso(actives=[BUCHERONS_ACTIF]))         # dans la grotte
	assert not _present(lieu, aelis, _perso(reussies=[BUCHERONS]))              # à Auxerre, avant le convoi
	assert not _present(lieu, aelis, _perso(actives=[CONVOI_ACTIF], reussies=[BUCHERONS]))   # sur la route
	assert _present(lieu, aelis, _perso(reussies=[BUCHERONS, CONVOI]))          # arrivée avec le convoi


def test_maelys_ne_suppose_pas_qu_on_connait_aelis():
	maelys = "pnj:maelys"
	sans = _visibles(maelys, flags={"transport_offert": True})
	assert "rang_c_offre_inconnu" in sans and "rang_c_offre" not in sans and "auxerre" not in sans
	avec = _visibles(maelys, reussies=[CONVOI], flags={"transport_offert": True})
	assert "rang_c_offre" in avec and "rang_c_offre_inconnu" not in avec
	assert "Vaugirard m'a parlé de vous." in DOCS[maelys]["dialogue"]["noeuds"]["accueil"]["texte"]
	texte = DOCS[maelys]["dialogue"]["noeuds"]["rang_c_propose_inconnu"]["texte"]
	assert "vous la connaissez" not in texte


# ── Répliques figées après la quête ───────────────────────────────────────────────

def test_milo_la_veille_du_convoi_puis_parti_avec_lui():
	milo = "pnj:milo_cartographe"
	assert "s4" in _visibles(milo, reussies=[BUCHERONS])
	assert "s4" not in _visibles(milo, reussies=[BUCHERONS], actives=[CONVOI])
	lieu = "lieu:auberge_de_la_tour_de_l_horloge"
	assert _present(lieu, milo, _perso(reussies=[BUCHERONS]))
	assert not _present(lieu, milo, _perso(actives=[CONVOI_ACTIF], reussies=[BUCHERONS]))
	assert not _present(lieu, milo, _perso(reussies=[BUCHERONS, CONVOI]))


def test_gautier_ne_rejoue_plus_le_retour_des_bucherons():
	g = "pnj:gautier_de_valcroix"
	flags = {"escorte_accomplie": True}
	assert {"bucherons_rapport"} <= _visibles(g, flags=flags)
	assert "bucherons_souvenir" not in _visibles(g, flags=flags)
	pendant = _visibles(g, actives=[CONVOI], flags=flags)
	apres = _visibles(g, reussies=[CONVOI], flags=flags)
	assert "bucherons_rapport" not in pendant and "bucherons_souvenir" in pendant
	assert "bucherons_rapport" not in apres and "bucherons_souvenir_apres" in apres


def test_bouchard_accueil_neutre_et_bon_compte():
	b = DOCS["pnj:bouchard_de_clignancourt_route_silencieuse"]
	assert "jamais arrivée" not in b["dialogue"]["noeuds"]["accueil"]["texte"]
	assert _visibles(b["_id"], flags={"escorte_accomplie": True}) >= {"route_rapport", "preparation"}
	assert "route_annonce" not in _visibles(b["_id"], flags={"escorte_accomplie": True})
	assert "route_annonce" in _visibles(b["_id"], flags={"escorte_offerte": True})
	assert "« Deux. Sur quatre. »" in b["dialogue"]["noeuds"]["route_rapport"]["texte"]


@pytest.mark.parametrize("flags, attendu", [
	({"acces_menace": True}, "registre"),
	({"acces_libere": True}, "registre_libre"),
	({"acces_menace": True, "acces_reinfeste": True}, "registre_reinfeste"),
	({"acces_accompli": True}, "registre_open"),
])
def test_le_registre_d_armand_suit_l_etat_de_la_mine(flags, attendu):
	visibles = _visibles("pnj:templier_armand_de_vaucremont_01", flags=flags)
	registres = {c for c in visibles if c.startswith("registre")}
	assert registres == {attendu}


# ── Écriture ──────────────────────────────────────────────────────────────────────

# Accords masculins du JOUEUR relevés dans la revue du 16/10 : aucun ne doit survivre.
MASCULINS = [
	"Tenez-vous prêt", "vous êtes allé", "Vous êtes celui du nord", "planté là", "reviendrai plus léger", "reviens plus léger",
	"revenez vivant", "reviens entier", "Vous serez inscrit", "depuis que vous êtes passé",
	"Bonjour, voyageur", "Halte, voyageur", "soit sur toi, voyageur", "un nouveau venu", "l'ami",
	"tu es revenu", "Tu es revenu", "Tu es passé", "rester entier", "tu es fatigué",
	"Tu n'es pas obligé", "n'es pas sûr", "ne sois sûr de", "m'avez déjà soigné", "revenir vivant",
	"toujours le bienvenu", "enfant vivant", "Je vous le ramènerai", "chargé comme un mulet",
	"vous a déjà mandaté", "qu'on vous a chargé", ", petit.",
]


def test_aucun_accord_masculin_du_joueur():
	for doc in DOCS.values():
		brut = json.dumps(doc.get("dialogue", {}), ensure_ascii=False)
		for motif in MASCULINS:
			assert motif not in brut, (doc["_id"], motif)


def test_borin_tutoie_partout_et_raconte_au_vous():
	for nid, nd in DOCS["pnj:borin_barbe_de_jais"]["dialogue"]["noeuds"].items():
		for replique in re.findall(r"«([^»]*)»", nd["texte"]):
			assert not re.search(r"\b(vous|votre|vos)\b", replique, re.I), (nid, replique)
		narration = re.sub(r"«[^»]*»", "", nd["texte"])
		# « le ton », « d'un ton » : le nom, pas le possessif.
		narration = re.sub(r"\b(le|un) ton\b", "", narration, flags=re.I)
		assert not re.search(r"(?<![\w'])(tu|te|toi|ton|ta|tes)(?![\w])|(?<![\w])t'", narration), (nid, narration)
