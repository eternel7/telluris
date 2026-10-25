#!/usr/bin/env python
# dev/gen_portail_notre_dame.py
# Le portail de Notre-Dame et sa commanderesse, Aénor de Sully (Auteur, 25/10) :
#   - Aénor de Sully, Templière elfe magicienne, cheffe des Templiers de Notre-Dame, tient le
#     TABLEAU DES SEUILS (`services.portail`, utils/portails.py) : Notre-Dame n'a AUCUN lien,
#     l'ancrage court-circuite un portail du monde et prend son point d'arrivée, contre un
#     cristal de mana jaune ;
#   - le puits de Chartres devient un donjon À ÉTAGES avec le coffre du Minotaure (seconde
#     source du cristal jaune) : on descend au treuil, on remonte par la chaîne du puits. La
#     GRILLE du labyrinthe est celle du dump (peinte dans /admin/editor), jamais réécrite :
#     le générateur vérifie seulement que le bas du puits et le coffre y sont praticables ;
#   - Aélis aux Archives des Seuils (l'Institut, aux Invalides) prend son portrait des Invalides.
#
# 100 % DONNÉE. ⚠️ UN SEUL FICHIER À IMPORTER (CLAUDE.md §18), DELTA SEUL :
# jsons/portail_notre_dame_a_importer.json. Les docs existants sont RELUS du dernier dump et
# seuls les champs de la demande bougent (PUT complet à l'import, §11). Régénération idempotente.
#
# Usage : python dev/gen_portail_notre_dame.py [jsons/telluris-dump-….json]
import copy
import importlib.util
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "portail_notre_dame_a_importer.json")


def _missions():
	chemin = os.path.join(RACINE, "dev", "gen_missions_rang_b_a_lutecia.py")
	spec = importlib.util.spec_from_file_location("gen_missions_rang_b_a_lutecia", chemin)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


M = _missions()

ANCRAGE = "lieu:notre_dame_portail"
AENOR = "pnj:aenor_de_sully"
PORTRAIT_AENOR = "templier_elfe_f_magicienne_notre_dame01.jpg"
ARCHIVES = "lieu:les_archives_des_seuils"
AELIS_ARCHIVES = "pnj:aelis_de_montfaucon_archives"
PORTRAIT_AELIS_INVALIDES = "architecte_Aélis_de_Montfaucon_dans_les_invalides.jpg"
LIEN_PUITS = M.id_lien(M.CRYPTE, M.LABYRINTHE)
# Bas du puits, au centre de la carte, sous la chaîne qui pend (image du labyrinthe) : on y
# arrive au treuil et l'on en remonte — point d'apparition ET passage vers la crypte.
LABY_PUITS = (14, 10)
# Coffre du Minotaure : la litière du coin sud-ouest, au plus loin du puits.
LABY_COFFRE = (3, 13)
# Calqué sur le coffre de l'ossuaire, une marche au-dessus (grade 4-5 contre 3-4). Piège sans
# `alarme` : dans une salle à deux Minotaures, des renforts de l'étage seraient deux de plus.
TRESOR_LABY = {
	"nom": "Coffre du Minotaure", "icon": "🧰", "pos": list(LABY_COFFRE),
	"garanti": [{"item": M.CRISTAL_JAUNE, "quantite": 1}],
	"bourse": [80, 200],
	"tirage": {"nb": 2, "table": [
		{"item": "item:gemmes", "poids": 3}, {"item": "item:anneau", "poids": 3},
		{"item": "item:bague", "poids": 2}, {"item": "item:Cristal_canalisation", "poids": 2}]},
	"piege": {"chance": 40, "danger": 3, "effets": ["degats", "mimique"], "mimique": "espece:mimique"},
}

REQUIS = (ANCRAGE, ARCHIVES, AELIS_ARCHIVES, M.CRISTAL_JAUNE,
		  M.LABYRINTHE, M.DONJON_PUITS, M.TEMPLIER_CRYPTE, M.CRYPTE, "espece:mimique",
		  "item:gemmes", "item:anneau", "item:bague", "item:Cristal_canalisation")


def fin(label="(Prendre congé.)"):
	return {"id": "fin", "label": label, "next": "fin"}


def aenor():
	return {
		"_id": AENOR, "type": "pnj", "nom": "Aénor de Sully",
		"race": "elfe", "vocation": "magicien", "portrait": PORTRAIT_AENOR,
		"description": "Commanderesse des Templiers de Notre-Dame. Elfe et magicienne, elle tient l'autel d'ancrage et sait sur quel seuil du monde il peut prendre pied, et pour combien de temps.",
		# Tableau des seuils (utils/portails.py) : `choix` = le gabarit que le router remplace par
		# une réplique par seuil ouvert ; le cristal est consommé au passage.
		"services": {"portail": {
			"ancrage": ANCRAGE,
			"cout": {"item": M.CRISTAL_JAUNE, "quantite": 1},
			"choix": "franchir",
			"noeuds": {"ouvert": "ouvert", "ferme": "ferme", "refus_cristal": "refus_cristal"},
		}},
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Au pied de l'autel d'ancrage, une elfe en manteau blanc de Templière garde une main posée sur la roue de pierre, comme on sent battre un pouls. Elle ne se retourne qu'une fois la roue immobile. « Aénor de Sully. Je commande ceux qui gardent ce cercle. Vous êtes venu pour le seuil. »",
					"choix": [
						{"id": "seuils", "label": "« Où peut-on aller, en ce moment ? »", "next": "seuils"},
						{"id": "comment", "label": "« Comment ce portail choisit-il où il mène ? »", "next": "comment"},
						{"id": "retour", "label": "« Et pour revenir ? »", "next": "retour"},
						fin(),
					],
				},
				"comment": {
					"texte": "« Il ne choisit pas. Les portails du monde vont chacun d'un lieu à un autre, toujours le même. Celui-ci n'a pas d'autre bout. » Elle fait tourner la roue d'un cran. « La gemme violette tient l'ancrage ouvert. Quand quelqu'un, ailleurs, franchit son propre seuil, l'ancrage peut se glisser dans son passage et en prendre l'arrivée, le temps que ce seuil reste chaud. Le cristal jaune tient votre prise sur le passage d'un autre. Sans lui, vous n'arriveriez nulle part. »",
					"choix": [
						{"id": "seuils", "label": "« Montrez-moi les seuils. »", "next": "seuils"},
						{"id": "accueil", "label": "« Autre chose. »", "next": "accueil"},
					],
				},
				"retour": {
					"texte": "« Rien ne ramène ici. » Aénor le dit sans regret. « Presque personne n'arrive à Notre-Dame : un seul lieu y mène, et je ne vous dirai pas lequel. Vous rentrerez par les routes, ou par le portail que vous trouverez là-bas. Arrivé de l'autre côté, vous serez où arrivent ceux qui l'ont pris, et pas ailleurs. »",
					"choix": [
						{"id": "seuils", "label": "« Montrez-moi les seuils. »", "next": "seuils"},
						{"id": "accueil", "label": "« Autre chose. »", "next": "accueil"},
					],
				},
				"seuils": {
					"texte": "Aénor pose les deux mains sur la roue. Les runes s'allument une à une, puis s'éteignent, sauf quelques-unes. « Voilà ceux qu'on franchit ailleurs, en ce moment. Je peux vous y glisser encore {fermeture}. Ensuite viendront {seuils_suivants}. Le passage coûte un {cristal}, et il fond dans la roue. »",
					"choix": [
						{"id": "franchir", "label": "Franchir un seuil.", "condition": {"cristal_jaune_porte": True},
						 "action": {"service": "portail", "op": "franchir"}},
						{"id": "sans_cristal", "label": "« Je n'ai pas de cristal jaune. »",
						 "condition": {"cristal_jaune_porte": False}, "next": "refus_cristal"},
						{"id": "attendre", "label": "« J'attends les suivants. »", "next": "seuils"},
						{"id": "accueil", "label": "« Pas maintenant. »", "next": "accueil"},
					],
				},
				"ouvert": {
					"texte": "Le cristal jaune fond au creux de la roue. Une lumière jaune tient le vortex immobile le temps d'un pas. Vous arrivez à {destination}, là où arrivent ceux qui ont pris ce portail.",
					"choix": [fin("Avancer.")],
				},
				"ferme": {
					"texte": "« Trop tard. » La rune s'éteint sous la main d'Aénor. « Ce seuil s'est refroidi derrière les derniers qui l'ont pris. D'autres s'ouvrent. »",
					"choix": [
						{"id": "seuils", "label": "« Lesquels ? »", "next": "seuils"},
						fin(),
					],
				},
				"refus_cristal": {
					"texte": "« Sans cristal jaune, la roue ne tient rien, et vous non plus. » Aénor retire ses mains. « On en trouve tout au fond des catacombes, et, dit-on, dans le coffre du puits de Chartres. Revenez avec un cristal. »",
					"choix": [
						{"id": "accueil", "label": "« Autre chose. »", "next": "accueil"},
						fin(),
					],
				},
			},
		},
	}


def ancrage(dump_doc):
	"""Le portail de Notre-Dame RELU : seule l'entrée d'Aénor s'ajoute (idempotent)."""
	doc = M.sans_rev(copy.deepcopy(dump_doc))
	entrees = [e for e in doc.get("pnj") or [] if e.get("character") != AENOR]
	entrees.append({
		"character": AENOR, "nom": "Aénor de Sully", "portrait": PORTRAIT_AENOR, "probabilite": 1,
		"description": "Une elfe en manteau blanc de Templière, une main posée sur la roue de pierre de l'autel d'ancrage.",
	})
	doc["pnj"] = entrees
	return doc


def archives(dump_doc):
	"""Les Archives des Seuils RELUES : Aélis y prend son portrait des Invalides."""
	doc = M.sans_rev(copy.deepcopy(dump_doc))
	for e in doc.get("pnj") or []:
		if e.get("character") == AELIS_ARCHIVES:
			e["portrait"] = PORTRAIT_AELIS_INVALIDES
	return doc


def puits(par_id):
	"""Le puits de Chartres en donjon à étages : champs posés sur les docs RELUS. Le labyrinthe
	n'est PAS réémis — sa grille (dump) est la vérité ; elle doit seulement porter le bas du
	puits et le coffre sur des cases praticables."""
	cells = par_id[M.LABYRINTHE]["cells"]
	for nom, (x, y) in (("bas du puits", LABY_PUITS), ("coffre", LABY_COFFRE)):
		if cells[y][x] != 1:
			sys.exit(f"ERREUR : {nom} ({x}, {y}) sur une case non praticable du labyrinthe")

	donjon_doc = M.sans_rev(copy.deepcopy(par_id[M.DONJON_PUITS]))
	donjon_doc["mode"] = "etages"
	salle = next(b for b in donjon_doc["battle_maps"] if b.get("lieu") == M.LABYRINTHE)
	salle["tresor"] = copy.deepcopy(TRESOR_LABY)

	templier = M.sans_rev(copy.deepcopy(par_id[M.TEMPLIER_CRYPTE]))
	choix = next(c for c in templier["dialogue"]["noeuds"]["seuil"]["choix"] if c["id"] == "descendre")
	choix["deplacer"] = M.LABYRINTHE

	# Le treuil : descente (donjon à étages → le combat s'ouvre au bas du puits) et remontée par
	# la chaîne, passage `surface` de l'unique étage.
	lien = {"_id": LIEN_PUITS, "type": "connection",
			"nodes": [{"lieu": M.CRYPTE, "pos": [0, 0], "label": "Descendre dans le puits"},
					  {"lieu": M.LABYRINTHE, "pos": list(LABY_PUITS), "label": "Remonter par la chaîne"}],
			"metadata": {"type": "descente", "status": "ouvert"}}
	return [donjon_doc, templier, lien]


def generer(par_id):
	for requis in REQUIS:
		if requis not in par_id:
			sys.exit(f"ERREUR : {requis} absent du dump")
	return [aenor(), ancrage(par_id[ANCRAGE]), archives(par_id[ARCHIVES])] + puits(par_id)


def main(argv):
	dump = M.charger(M.dernier_dump(argv))
	par_id = {d["_id"]: d for d in dump["docs"]}
	docs = generer(par_id)
	neufs = [d["_id"] for d in docs if d["_id"] not in par_id]
	print("Neufs :", ", ".join(neufs) or "aucun")
	M.ecrire(SORTIE, docs)
	print(f"{len(docs)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main(sys.argv)
