"""Chasses légendaires (`docs/conception_trophees_legendaires.md`) — logique pure.

Ce que ces tests verrouillent :
1. Matériau d'armure : une matière `fabrication_armure_metal` n'entre que dans une armure
   `armure_metal` ; `fabrication_armure` reste ouverte à toutes.
2. Pouvoir d'un objet PORTÉ (`utils/pouvoirs_objets`) : actif équipé, absent au sac, exigence
   lue BRUTE, aucune écriture sur le personnage ; listé `accorde_par`, case de barre honorée.
3. Panoplie : seul le plus haut seuil atteint, pièces DISTINCTES, pseudo-objet sans zone.
4. Signature du chasseur : bête rare+ seule, suit la découpe, la référence de butin, la commande.
5. Mur des trophées : réveil `requiert_trophee` seulement si le coffre expose un trophée.
6. Collectionneur : pièce signée vendue d'abord, avec sa prime ; flag `rachat_possible`.
7. Table légendaire : chaque bloc dans le budget de son palier (barème de gen_fabrication_matieres).
"""

import json
import os
import sys

from utils import carcasse
from utils import characters
from utils import chasse_signee
from utils import commande
from utils import competences as competences_util
from utils import lint_dialogues
from utils import pnj
from utils import pouvoirs_objets
from utils import proprietes
from utils import slots_actions
from utils import sorts as sorts_util
from utils.combat import ref_de_butin

DEV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev")


# ── 1. Matériau d'armure ────────────────────────────────────────────────────────

def test_une_matiere_de_metal_n_entre_que_dans_le_metal():
	ecailles = {"_id": "item:ecailles", "tags": ["fabrication_armure_metal"],
				"fabrication": {"nom": "aux Écailles", "modificateurs": {"bonus_pa": 3}}}
	heaume = {"categorie": "armure", "tags": ["armure_metal"]}
	robe = {"categorie": "armure", "tags": ["armure_tissu"]}
	lieu = {"categorie": "grand_arsenal"}
	assert "fabrication_armure_metal" in commande.tags_fabrication(heaume)
	assert commande.matiere_acceptee(lieu, ecailles, heaume)
	assert not commande.matiere_acceptee(lieu, ecailles, robe)
	# La porte large reste ouverte à toute armure.
	cuir = dict(ecailles, tags=["fabrication_armure"])
	assert commande.matiere_acceptee(lieu, cuir, robe)


def test_un_tag_ordinaire_n_ouvre_aucune_famille():
	assert commande.tags_fabrication({"categorie": "armure", "tags": ["harnachement"]}) == {"fabrication_armure"}


# ── 2. Pouvoirs d'objet porté ───────────────────────────────────────────────────

SORT = {"_id": "sort:souffle_de_feu", "type": "sort", "nom": "Souffle de feu", "cout_pm": 14,
		"cible": "ennemi", "effets": {"degats": "2D6"}, "niveau": 1}
EPEE = {"_id": "item:epee_croc", "nom": "Épée-croc", "categorie": "arme",
		"competences": [{"id": "sort:souffle_de_feu", "restriction": {"Vol": 30}}]}
DOCS = {SORT["_id"]: SORT, EPEE["_id"]: EPEE}


def _perso(vol=40, porte=True, buff=0):
	return {"_id": "character:x", "sorts_connus": [], "competences_connues": [],
			"caracteristiques_current": {"Vol": vol},
			"effets_actifs": [{"buffs": {"Vol": buff}}] if buff else [],
			"slots": {"main_droite": {"item": EPEE["_id"]} if porte else None},
			"inventaire": [] if porte else [{"item": EPEE["_id"]}]}


def test_le_pouvoir_ne_vit_que_tant_que_l_objet_est_porte():
	assert pouvoirs_objets.connait(_perso(), "sort:souffle_de_feu", DOCS.get)
	assert not pouvoirs_objets.connait(_perso(porte=False), "sort:souffle_de_feu", DOCS.get)


def test_l_exigence_se_lit_sur_la_caracteristique_brute():
	faible = _perso(vol=20, buff=20)            # un buff n'éveille jamais un pouvoir
	assert not pouvoirs_objets.connait(faible, "sort:souffle_de_feu", DOCS.get)
	ligne = pouvoirs_objets.pouvoirs_objets(faible, DOCS.get)[0]
	assert ligne["actif"] is False and ligne["manque"] == {"Vol": 30}


def test_rien_n_est_appris_ni_ecrit():
	moi = _perso()
	docs = sorts_util.sorts_connus_docs(moi, DOCS.get)
	assert [s["id"] for s in docs] == ["sort:souffle_de_feu"]
	assert docs[0]["accorde_par"] == "Épée-croc"
	assert moi["sorts_connus"] == []


def test_un_sort_deja_appris_n_est_pas_double():
	moi = _perso()
	moi["sorts_connus"] = ["sort:souffle_de_feu"]
	docs = sorts_util.sorts_connus_docs(moi, DOCS.get)
	assert len(docs) == 1 and "accorde_par" not in docs[0]


def test_deux_mains_et_deux_objets_ne_comptent_qu_une_fois():
	moi = _perso()
	moi["slots"]["main_gauche"] = {"item": EPEE["_id"]}
	assert len(pouvoirs_objets.pouvoirs_objets(moi, DOCS.get)) == 1


def test_une_competence_accordee_est_listee_avec_son_objet():
	comp = {"_id": "competence:terreur", "type": "competence", "nom": "Terreur", "mode": "active", "vocation": "necromancien",
			"cible": "ennemi", "cout_pm": 10, "effets": {"buffs": {"Vol": -2}, "duree": 2}}
	sceptre = {"_id": "item:sceptre", "nom": "Sceptre", "competences": ["competence:terreur"]}
	docs = {comp["_id"]: comp, sceptre["_id"]: sceptre}
	moi = {"competences_connues": [], "caracteristiques_current": {}, "slots": {"main_droite": "item:sceptre"}}
	connues = competences_util.competences_connues_docs(moi, docs.get)
	assert [c["id"] for c in connues] == ["competence:terreur"] and connues[0]["accorde_par"] == "Sceptre"


def test_la_case_de_barre_revient_au_reequipement():
	entree = {"type": "sort", "ref": "sort:souffle_de_feu"}
	assert slots_actions._entree_possedee(entree, _perso(), DOCS.get)
	assert not slots_actions._entree_possedee(entree, _perso(porte=False), DOCS.get)


def test_un_id_hors_sort_ou_competence_est_ignore():
	objet = {"_id": "item:o", "competences": ["item:autre", {"id": 3}, "sort:ok"]}
	moi = {"slots": {"cou": "item:o"}, "caracteristiques_current": {}}
	assert [l["id"] for l in pouvoirs_objets.pouvoirs_objets(moi, {"item:o": objet}.get)] == ["sort:ok"]


# ── 3. Panoplie ─────────────────────────────────────────────────────────────────

RULES = {"panoplies": {"dragon": {"nom": "Panoplie du Dragon", "seuils": {
	"2": {"bonus_pv": 10}, "3": {"bonus_pv": 20, "bonus_pa": 4, "slots": ["torse"]}}}}}


def test_seul_le_plus_haut_seuil_compte():
	assert characters.panoplies_actives({"dragon": {"a"}}, RULES) == []
	deux = characters.panoplies_actives({"dragon": {"a", "b"}}, RULES)
	assert deux[0]["bonus_pv"] == 10 and "bonus_pa" not in deux[0]
	trois = characters.panoplies_actives({"dragon": {"a", "b", "c"}}, RULES)
	assert trois[0]["bonus_pv"] == 20 and trois[0]["bonus_pa"] == 4
	assert "slots" not in trois[0]          # un seuil n'apporte que des champs de bonus
	assert characters.panoplies_actives({"inconnue": {"a", "b"}}, RULES) == []


def test_la_panoplie_s_ajoute_au_bonus_d_equipement_hors_zone(monkeypatch):
	docs = {"item:heaume": {"_id": "item:heaume", "nom": "Heaume", "categorie": "armure",
							"bonus_pa": 3, "panoplie": "dragon"},
			"item:epee": {"_id": "item:epee", "nom": "Épée", "categorie": "arme", "panoplie": "dragon"},
			"rules:panoplies": {"panoplies": {"dragon": {"nom": "Panoplie", "seuils": {"2": {"bonus_pa": 4}}}}}}
	monkeypatch.setattr(characters, "get_doc", lambda i: docs.get(i))
	bonus = characters.recompute_equipment_bonus({"tete": "item:heaume", "main_droite": "item:epee"})
	assert bonus.pa == 7 and bonus.pa_hors_zone == 4 and bonus.pa_zones.get("tete") == 3
	seul = characters.recompute_equipment_bonus({"tete": "item:heaume"})
	assert seul.pa == 3


# ── 4. Signature du chasseur ────────────────────────────────────────────────────

def test_seule_une_bete_rare_est_signee():
	assert chasse_signee.signature({"rarete": "commun"}, "Loup", 1) is None
	assert chasse_signee.signature({"rarete": "legendaire"}, "Dragon rouge", 7)["espece"] == "Dragon rouge"


def test_le_nom_du_chasseur_et_le_libelle():
	lignes = [{"chasse": {"par": "", "espece": "Tarasque", "quand": 1}}, {"item_id": "item:x"}]
	chasse_signee.signer_par(lignes, ["Aldric"])
	assert chasse_signee.libelle(lignes[0]["chasse"]) == "Abattu par Aldric — Tarasque"
	assert chasse_signee.nom_des_chasseurs(["A", "B", "C", "D"]) == "A, B, C et leurs compagnons"


def test_la_signature_suit_la_reference_et_la_decoupe():
	ref = ref_de_butin({"item_id": "item:dragon_rouge_tete", "poids": 200.0,
						"chasse": {"par": "Aldric", "espece": "Dragon rouge", "quand": 1}})
	tete = {"_id": "item:dragon_rouge_tete", "decoupe_poids_min": 100.0,
			"decoupe": [{"item": "item:dragon_rouge_tete_morceau", "quantite": 2, "fraction": 1.0}]}
	morceaux = carcasse.decouper_ref(ref, tete)
	assert all(m["chasse"]["par"] == "Aldric" for m in morceaux)
	morceaux[0]["chasse"]["par"] = "x"           # deux portions ne partagent jamais un dict
	assert morceaux[1]["chasse"]["par"] == "Aldric"


def test_la_signature_passe_sur_la_piece_commandee():
	chasse = chasse_signee.chasse_des_refs([{"item": "item:fer"}, {"item": "item:t", "chasse": {"par": "A"}}])
	cmd = commande.nouvelle_commande({"_id": "lieu:a"}, "item:epee", {"total": 10}, now=1, chasse=chasse)
	assert commande.ref_livree(cmd)["chasse"] == {"par": "A"}


# ── 5. Mur des trophées ─────────────────────────────────────────────────────────

CAT_MUR = {"types": {"maison": {}}, "amenagements": [
	{"id": "mur_trophees", "nom": "Mur", "types_autorises": ["maison"],
	 "effets": {"reveil": {"duree": 25, "nom": "Fierté", "buffs": {"Cha": 3}, "requiert_trophee": True}}}]}
DOCS_MUR = {"item:tete_naturalisee": {"tags": ["trophee_expose"]}, "item:pain": {"tags": []}}


def test_le_mur_ne_joue_qu_avec_un_trophee_au_coffre():
	moi = {"_id": "character:moi"}
	vide = {"amenagements": ["mur_trophees"], "coffre": [{"item": "item:pain"}]}
	proprietes.appliquer_reveil(vide, CAT_MUR, [], [moi], [], maintenant=10, get_doc_fn=DOCS_MUR.get)
	assert not moi.get("effets_actifs")
	expose = {"amenagements": ["mur_trophees"], "coffre": [{"item": "item:tete_naturalisee"}]}
	bilan = proprietes.appliquer_reveil(expose, CAT_MUR, [], [moi], [], maintenant=10, get_doc_fn=DOCS_MUR.get)
	assert bilan and moi["effets_actifs"][0]["buffs"] == {"Cha": 3}


# ── 6. Collectionneur ───────────────────────────────────────────────────────────

COLLECTIONNEUR = {"services": {"rachat": {
	"articles": [{"item": "item:tete", "cout_cuivre": 1000}, {"item": "item:x", "cout_cuivre": 0}],
	"noeuds": {"fait": "f", "sans_objet": "r"}}}}


def test_le_collectionneur_paie_d_abord_la_piece_signee_avec_sa_prime():
	article = pnj.article_rachete(COLLECTIONNEUR, "item:tete")
	assert pnj.article_rachete(COLLECTIONNEUR, "item:x") is None       # prix nul : refusé
	sacs = [{"inventaire": [{"item": "item:tete"}]},
			{"inventaire": [{"item": "item:pain"}, {"item": "item:tete", "chasse": {"par": "A"}}]}]
	assert pnj.exemplaire_a_racheter(sacs, "item:tete", characters.item_ref_id) == (1, 1)
	assert pnj.prix_rachat(article, sacs[1]["inventaire"][1]) == 1500
	assert pnj.prix_rachat(article, sacs[0]["inventaire"][0]) == 1000
	assert pnj.rachat_possible(COLLECTIONNEUR, sacs, characters.item_ref_id)
	assert not pnj.rachat_possible(COLLECTIONNEUR, [{"inventaire": []}], characters.item_ref_id)


def test_le_linter_connait_le_service_rachat():
	assert "rachat_possible" in lint_dialogues.FLAGS_CONNUS
	doc = {"_id": "pnj:c", "services": COLLECTIONNEUR["services"], "dialogue": {
		"noeud_depart": "a", "noeuds": {
			"a": {"texte": "x", "choix": [{"id": "v", "label": "v", "condition": {"rachat_possible": True},
										   "action": {"service": "rachat", "op": "vendre"}}]},
			"f": {"texte": "{objet} {prix}", "choix": [{"id": "o", "label": "o", "next": "a"}]},
			"r": {"texte": "rien", "choix": [{"id": "o", "label": "o", "next": "a"}]}}}}
	fautes = lint_dialogues.analyser_doc(doc)
	assert not [f for f in fautes if "rachat" in f], fautes


# ── 7. Table légendaire ─────────────────────────────────────────────────────────

def test_chaque_bloc_legendaire_tient_dans_son_palier():
	sys.path.insert(0, DEV)
	import gen_fabrication_matieres as gfm
	import legendaires_table as table
	entrees = table.entrees_fabrication(gfm._partie, gfm._matiere)
	assert gfm.erreurs_de_forme(entrees) + gfm.erreurs_de_budget(entrees) + gfm.effets_mal_diriges(entrees) == []
	# Une entrée par partie déclarée, plus une matière nommée par espèce.
	attendu = sum(len(p) for p in table.PARTIES.values()) + len(table.ESPECES)
	assert len(entrees) == attendu
	# Un morceau porte le MÊME bloc que sa partie (décision du 13/11).
	assert entrees["item:dragon_rouge_tete_morceau"]["modificateurs"] == entrees["item:dragon_rouge_tete"]["modificateurs"]
	# Toutes reprises par la table de gen_fabrication_matieres : sa relance ne les défait pas.
	assert set(entrees) <= set(gfm.MATIERES)
