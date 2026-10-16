#!/usr/bin/env python
# dev/gen_correctifs_dialogues.py
# Correctifs de cohérence des dialogues PNJ (revue du dump du 16/10/2026, arbitrages de l'Auteur) :
#   - rang C de Lutecia SANS l'arc d'Auxerre : Aélis (Cour des Arches) et Maëlys ont une variante
#     « inconnu » ; la version qui suppose la grotte et le convoi reste réservée au convoi réussi ;
#   - Aélis n'est plus à la Cour pendant l'arc d'Auxerre (grotte, bureau, convoi) ;
#   - répliques figées après la quête : Milo (la « veille » du convoi, puis parti avec lui),
#     Gautier (retour des bûcherons), Bouchard (route silencieuse), Armand de Vaucremont (registre) ;
#   - écriture : joueur accordé au NEUTRE (aucun masculin forcé), narration toujours au « vous »,
#     un PNJ qui tutoie s'y tient (Borin) ;
#   - coquilles (George, capitaines, « Deux. Sur six. »).
#
# Relit le dump le plus récent et n'écrit que les docs qui CHANGENT (CLAUDE.md §11, §18) →
# jsons/correctifs_dialogues_a_importer.json. Rejouable : un remplacement déjà appliqué est
# reconnu (nouveau texte présent, ancien absent) et sauté ; un texte introuvable est une ERREUR,
# jamais un saut silencieux.
#
# ⚠️ Les anciens fichiers d'import et générateurs qui écrivent ces PNJ (gen_quete_rang_c_jumieges,
# gen_enquete_morvan, gen_mission_bucherons, gen_convoi_lutecia, gen_ports_manche, gen_marchands,
# pnj_elise_herboriste / pnj_milo_cartographe / pnj_bouchard_* _a_importer.json…) portent encore
# l'ancien texte : les réimporter effacerait ces correctifs.
#
# Usage : python dev/gen_correctifs_dialogues.py

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "correctifs_dialogues_a_importer.json")

CONVOI = "quete:escorte_convoi_de_lutecia"
BUCHERONS = "quete:escorte_bucherons_d_auxerre"
DELAI_UNE_FOIS = 315360000   # dix ans : la scène ne se rejoue pas (même valeur que retrouvailles_fin)

# Filtres de BARRIÈRE (présence d'un PNJ) : les barrières n'ont pas de sous-filtre `id`, une
# escorte se reconnaît à sa destination — mêmes filtres que les présences déjà en jeu.
CONVOI_ACTIF_FILTRE = {"types": ["escorte"], "cible": "lieu:notre_dame", "giver_categorie": "cathedral"}
BUCHERONS_ACTIF_FILTRE = {"types": ["escorte"], "cible": "lieu:bureau_du_maitre_de_guilde_d_auxerre",
						  "giver_categorie": "bureau_maitre_guilde"}


def dernier_dump():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun dump jsons/telluris-dump-*.json")
	with open(dumps[-1], encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}, os.path.basename(dumps[-1])


# ── Primitives (idempotentes) ────────────────────────────────────────────────────

def noeud(doc, nid):
	try:
		return doc["dialogue"]["noeuds"][nid]
	except KeyError:
		sys.exit(f"ERREUR : nœud {nid!r} absent de {doc['_id']}")


def choix(doc, nid, cid):
	for c in noeud(doc, nid).get("choix", []):
		if c.get("id") == cid:
			return c
	sys.exit(f"ERREUR : choix {cid!r} absent de {doc['_id']}#{nid}")


def _remplacer(cible, cle, ancien, nouveau, ou):
	texte = cible.get(cle, "")
	if ancien in texte:
		cible[cle] = texte.replace(ancien, nouveau, 1)
	elif nouveau not in texte:
		sys.exit(f"ERREUR : « {ancien} » introuvable dans {ou}")


def texte(doc, nid, ancien, nouveau):
	_remplacer(noeud(doc, nid), "texte", ancien, nouveau, f"{doc['_id']}#{nid}")


def libelle(doc, nid, cid, ancien, nouveau):
	_remplacer(choix(doc, nid, cid), "label", ancien, nouveau, f"{doc['_id']}#{nid}/{cid}")


def condition(doc, nid, cid, cond):
	"""Fusionne `cond` dans la condition du choix (les clés existantes sont gardées)."""
	c = choix(doc, nid, cid)
	c["condition"] = {**(c.get("condition") or {}), **cond}


def poser_choix(doc, nid, nouveau, apres=None):
	"""Ajoute (ou remplace, même `id`) un choix ; `apres` = id du choix qu'il suit."""
	liste = noeud(doc, nid).setdefault("choix", [])
	liste[:] = [c for c in liste if c.get("id") != nouveau["id"]]
	ids = [c.get("id") for c in liste]
	i = ids.index(apres) + 1 if apres in ids else len(liste)
	liste.insert(i, nouveau)


def poser_noeud(doc, nid, contenu):
	doc["dialogue"]["noeuds"][nid] = contenu


def partout(doc, ancien, nouveau, champ="texte"):
	"""Remplace dans TOUS les nœuds (champ `texte`) ou tous les libellés (`label`). Renvoie le
	nombre de remplacements faits (0 si déjà appliqué)."""
	n = 0
	for nd in doc["dialogue"]["noeuds"].values():
		cibles = [nd] if champ == "texte" else nd.get("choix", [])
		for c in cibles:
			if ancien in c.get(champ, ""):
				c[champ] = c[champ].replace(ancien, nouveau)
				n += 1
	return n


def q_reussie(qid, attendu=True):
	return {"id": qid} if attendu else {"id": qid, "attendu": False}


def q_active(qid, attendu=True):
	return {"id": qid} if attendu else {"id": qid, "attendu": False}


# ── Borin : il TUTOIE, partout ; la narration reste au « vous » ───────────────────

def borin(doc):
	texte(doc, "premiere_mission", "y inscrit soigneusement ton nom", "y inscrit soigneusement votre nom")
	texte(doc, "transport_propose", "Il glisse un jeton de cuivre dans ta main.",
		  "Il glisse un jeton de cuivre dans votre main.")
	texte(doc, "transport_lecon", "Il se penche vers toi.", "Il se penche vers vous.")
	texte(doc, "transport_accepte", "Borin contourne le comptoir et t'aide à charger",
		  "Borin contourne le comptoir et vous aide à charger")
	texte(doc, "transport_accepte", "que tous les vétérans connaissent, petit. » Il t'adresse",
		  "que tous les vétérans connaissent. » Il vous adresse")
	texte(doc, "transport_rapporte", "trace une ligne à côté de ton nom", "trace une ligne à côté de votre nom")
	texte(doc, "transport_rapporte", "« Rang Cuivre — le premier échelon,",
		  "« Rang F, le cuivre — le premier échelon,")
	texte(doc, "transport_trop_charge", "Le nain soupèse ton barda", "Le nain soupèse votre barda")
	libelle(doc, "transport_trop_charge", "ok", "Je reviendrai plus léger.", "Je reviendrai le sac plus léger.")
	# Réplique « vétéran » : rejouable à tout rang, elle ne promet plus le tableau à un ancien.
	texte(doc, "transport_veteran",
		  "Il désigne du menton le grand tableau couvert de parchemins, dans la salle commune. "
		  "« Va donc voir ce qu'on y épingle. Tu as gagné le droit de choisir. »",
		  "Il tapote la couverture de son registre. « Ton nom y est toujours. Ceux qui tiennent "
		  "parole, je ne les raye jamais. »")
	texte(doc, "rang_propose", "Borin referme son registre et te jauge", "Borin referme son registre et vous jauge")
	texte(doc, "rang_accepte", "à côté de ton nom", "à côté de votre nom")
	texte(doc, "rang_accepte", "et reviens entier, {prenom}, ce serait un comble",
		  "et reviens en un seul morceau, {prenom} : ce serait un comble")
	texte(doc, "rang_rapporte", "sur ta plaque de cuir bouilli", "sur votre plaque de cuir bouilli")
	texte(doc, "escorte_propose", "On l'a vu du côté de {lieu_rencontre}.", "On a vu l'enfant du côté de {lieu_rencontre}.")
	texte(doc, "escorte_details", "« Vous rendrez l'enfant à sa famille", "« Tu rendras l'enfant à sa famille")
	texte(doc, "escorte_acceptee", "« C'est noté à votre nom. »", "« C'est noté à ton nom. »")
	texte(doc, "escorte_acceptee", "ramenez l'enfant, pas son panier.", "ramène l'enfant, pas son panier.")
	texte(doc, "escorte_relance", "« Cherchez {direction}. Et souvenez-vous :", "« Cherche {direction}. Et souviens-toi :")
	texte(doc, "bucherons_appel", "« Hé ! Vous. Oui, vous. »", "« Hé ! Toi. Oui, toi. »")
	texte(doc, "bucherons_appel", "« Le maître de la guilde vous cherche. »", "« Le maître de la guilde te cherche. »")
	texte(doc, "bucherons_appel", "« Et avant que vous demandiez :", "« Et avant que tu demandes :")
	texte(doc, "bucherons_appel_qui", "de vous envoyer le voir dès que vous mettriez les pieds ici.",
		  "de t'envoyer le voir dès que tu mettrais les pieds ici.")
	texte(doc, "bucherons_appel_escalier", "Montez. Il vous dira le reste.", "Monte. Il te dira le reste.")
	# Le joueur vouvoie Borin partout ailleurs (« Vous vous souvenez de moi ? »).
	libelle(doc, "morvan_propose", "details", "« Et toi, tu y crois ? »", "« Et vous, vous y croyez ? »")


# ── Gautier : la scène du retour ne se rejoue plus après le départ du convoi ───────

BUCHERONS_SOUVENIR = (
	"Gautier lève les yeux de sa carte. « Étienne remarche — mal, mais il marche. Armand est "
	"retourné couper au nord, et il n'y va plus jamais à moins de quatre. » Il effleure l'épingle "
	"blanche plantée sur la forêt. « Matthieu, lui, n'a plus remis les pieds dans une grotte. Il dit "
	"que c'est le froid. Je ne lui ai pas demandé lequel. »")


def gautier(doc):
	for nid in ("accueil", "commission_repos"):
		condition(doc, nid, "bucherons_rapport",
				  {"quete_active": q_active(CONVOI, False), "quete_reussie": q_reussie(CONVOI, False)})
		poser_choix(doc, nid, {"id": "bucherons_souvenir", "label": "« Des nouvelles des bûcherons ? »",
							   "condition": {"quete_active": q_active(CONVOI)}, "next": "bucherons_souvenir"},
					apres="bucherons_rapport")
		poser_choix(doc, nid, {"id": "bucherons_souvenir_apres", "label": "« Des nouvelles des bûcherons ? »",
							   "condition": {"quete_reussie": q_reussie(CONVOI)}, "next": "bucherons_souvenir"},
					apres="bucherons_souvenir")
	poser_noeud(doc, "bucherons_souvenir", {"texte": BUCHERONS_SOUVENIR, "choix": [
		{"id": "retour", "label": "Revenir.", "next": "accueil"}]})
	texte(doc, "commission_details", "c'est bien de CE chantier qu'on vous a chargé.",
		  "c'est bien CE chantier qu'on vous a confié.")
	texte(doc, "bucherons_proposition", "Vous demandez si ce sera seul.",
		  "Vous demandez si vous partirez sans renfort.")


# ── Maëlys : une épreuve du rang C pour qui n'a pas fait l'arc d'Auxerre ──────────

def maelys(doc):
	# « Éléonore » prêtait à confusion avec Dame Éléonore de Rochefort, rencontrée au convoi.
	texte(doc, "accueil", "Éléonore m'a parlé de vous.", "Vaugirard m'a parlé de vous.")
	condition(doc, "accueil", "auxerre", {"quete_reussie": q_reussie(CONVOI)})
	condition(doc, "accueil", "rang_c_offre", {"quete_reussie": q_reussie(CONVOI)})
	base = noeud(doc, "rang_c_propose")
	poser_choix(doc, "accueil", {
		"id": "rang_c_offre_inconnu", "label": choix(doc, "accueil", "rang_c_offre")["label"],
		"condition": {"transport_offert": True, "quete_reussie": q_reussie(CONVOI, False)},
		"next": "rang_c_propose_inconnu"}, apres="rang_c_offre")
	inconnu = copy.deepcopy(base)
	ancien = "Aélis de Montfaucon. Je crois que vous la connaissez. Portez-lui"
	nouveau = ("Aélis de Montfaucon : une architecte qui ne sait pas se battre — et qui le sait, ce qui "
			   "vaut mieux. Portez-lui")
	if ancien not in inconnu["texte"] and nouveau not in inconnu["texte"]:
		sys.exit("ERREUR : pnj:maelys#rang_c_propose a changé")
	inconnu["texte"] = inconnu["texte"].replace(ancien, nouveau)
	poser_noeud(doc, "rang_c_propose_inconnu", inconnu)
	libelle(doc, "rang_c_trop_charge", "ok", "« Je reviens plus léger. »", "« Je reviens le sac plus léger. »")


# ── Aélis à la Cour des Arches : retrouvailles OU première rencontre ──────────────

COUR = ("Au milieu de la cour, près d'une table où plusieurs apprentis examinent des tracés, une jeune "
		"femme penche la tête sur un plan déroulé, un compas dans une main, un carnet épais calé sous le bras.")
RETROUVAILLES_01 = ("Elle se redresse pour changer de feuille, vous voit, et reste figée une seconde, le compas "
					"en l'air. Puis elle pose tout sur la table sans regarder où, et vient droit vers vous.")
INCONNU_01 = ("Elle ne relève la tête qu'à la fin de sa ligne, et vous regarde comme elle mesurerait un mur. "
			  "« Vous cherchez l'Institut ? Il est tout autour de vous. Vous cherchez un architecte ? Vous en "
			  "avez trouvé une. »")
INCONNU_02 = ("« Aélis de Montfaucon. » Elle couche son compas en travers du plan. « Les cristaux de mana, "
			  "d'abord ; le portail de Notre-Dame, maintenant. Les Architectes ne sont à Lutecia que pour lui : "
			  "un Frère Aborigène l'a bâti, la grande vague ne l'a pas dérangé, et personne depuis n'a su en "
			  "faire un pareil. » Elle hausse une épaule. « Quand on étudie la pierre, on finit par vouloir voir "
			  "la maison. »")
INCONNU_FIN = ("« Une place, non. Un point de départ. » Elle reprend son compas sur la table et le fait tourner "
			   "entre ses doigts, comme pour vérifier qu'il est resté droit. « Vous, vous allez dehors, vous voyez "
			   "des portails, des donjons, des choses que je ne connais que par des relevés. Quand vous en "
			   "reviendrez, passez par la Cour. Ici, on a de quoi écouter, et je préfère l'entendre de quelqu'un "
			   "qui y était plutôt que de l'apprendre dans un rapport. » Elle se penche de nouveau sur son plan. "
			   "« Bonne route, {prenom}. »")
LETTRE_CONNU = ("« Je n'avais pas osé le demander. » Un coin de sa bouche se relève. « J'aurais dû : on me "
				"l'aurait peut-être accordé plus tôt. »")


def aelis_cour(doc):
	connu = {"quete_reussie": q_reussie(CONVOI)}
	inconnu = {"quete_reussie": q_reussie(CONVOI, False)}
	doc["dialogue"]["noeud_depart"] = "cour"
	poser_noeud(doc, "cour", {"texte": COUR, "choix": [
		{"id": "approcher", "label": "(S'approcher de la table.)", "condition": connu, "next": "retrouvailles_01"},
		{"id": "approcher_inconnu", "label": "(S'approcher de la table.)", "condition": inconnu,
		 "next": "inconnu_01"},
		{"id": "fin", "label": "(Passer votre chemin.)", "next": "fin"}]})
	noeud(doc, "retrouvailles_01")["texte"] = RETROUVAILLES_01
	fin = noeud(doc, "retrouvailles_fin")
	lettre = copy.deepcopy(next(c for c in fin["choix"] if c["id"] == "lettre"))
	jumieges = copy.deepcopy(next(c for c in fin["choix"] if c["id"] == "jumieges"))
	poser_noeud(doc, "inconnu_01", {"texte": INCONNU_01, "choix": [
		{"id": "qui", "label": "« À qui ai-je l'honneur ? »", "next": "inconnu_02"},
		copy.deepcopy(lettre),
		{"id": "fin", "label": "« Je ne fais que passer. »", "next": "fin"}]})
	poser_noeud(doc, "inconnu_02", {"texte": INCONNU_02, "choix": [
		{"id": "ici", "label": "« Que faites-vous, exactement, ici ? »", "next": "retrouvailles_04"},
		copy.deepcopy(lettre)]})
	condition(doc, "retrouvailles_05", "conclure", connu)
	poser_choix(doc, "retrouvailles_05", {"id": "conclure_inconnu", "label": "« Vous avez trouvé votre place. »",
										  "condition": inconnu, "next": "inconnu_fin"}, apres="conclure")
	poser_noeud(doc, "inconnu_fin", {"texte": INCONNU_FIN, "delai_min": DELAI_UNE_FOIS, "choix": [
		copy.deepcopy(lettre), copy.deepcopy(jumieges),
		{"id": "fin", "label": "« Je repasserai. »", "next": "fin"}]})
	texte(doc, "lettre_lue", " « J'avais demandé quelqu'un de sûr. Je n'avais pas osé demander quelqu'un que "
		  "je connaisse. »", " « J'avais demandé quelqu'un de sûr. »")
	poser_choix(doc, "lettre_lue", {"id": "connu", "label": "« Quelqu'un de sûr, et que vous connaissez. »",
									"condition": connu, "next": "lettre_connu"})
	noeud(doc, "lettre_lue")["choix"].sort(key=lambda c: c["id"] != "connu")
	poser_noeud(doc, "lettre_connu", {"texte": LETTRE_CONNU, "choix": [
		{"id": "mission", "label": "« De quoi s'agit-il ? »", "next": "mission_01"}]})
	texte(doc, "mission_acceptee", "« Je ne sais pas me battre, {prenom}. Vous le savez. Sur la route,",
		  "« Je ne sais pas me battre, {prenom}. Autant que vous le sachiez avant la route. En chemin,")


def cour_des_arches(lieu):
	"""Aélis n'est pas à Lutecia pendant l'arc d'Auxerre (grotte, bureau, convoi) : présente si le
	convoi est réussi, ou si l'arc n'a pas commencé — deux `ou`, le complément d'une conjonction."""
	entree = next(e for e in lieu.get("pnj", []) if e.get("character") == "pnj:aelis_de_montfaucon_cour_des_arches")
	conds = [c for c in entree.get("conditions", []) if "ou" not in c]
	conds += [
		{"ou": [{"quete_reussie": q_reussie(CONVOI)}, {"quete_active": {**BUCHERONS_ACTIF_FILTRE, "attendu": False}}]},
		{"ou": [{"quete_reussie": q_reussie(CONVOI)}, {"quete_reussie": q_reussie(BUCHERONS, False)}]},
	]
	entree["conditions"] = conds


# ── Milo : la veille du convoi, puis parti avec lui ───────────────────────────────

def milo(doc):
	condition(doc, "accueil", "s4", {"quete_active": q_active(CONVOI, False),
									 "quete_reussie": q_reussie(BUCHERONS)})
	libelle(doc, "accueil", "s3", "Lui raconter ta dernière mission.", "Lui raconter votre dernière mission.")
	texte(doc, "s1_03", "« Tu es passé par la vieille route ? »", "« Tu as pris la vieille route ? »")
	texte(doc, "s1_21", "« Oui. Mais toi, tu es revenu vivant. »", "« Oui. Mais toi, tu en reviens. »")
	texte(doc, "s2_01", "« Tu es revenu ! »", "« Te revoilà ! »")


def auberge_horloge(lieu):
	"""Milo part AVEC le convoi (« Je viens avec vous ») : absent dès qu'il est en route."""
	entree = next(e for e in lieu.get("pnj", []) if e.get("character") == "pnj:milo_cartographe")
	conds = entree.setdefault("conditions", [])
	clause = {"quete_active": {**CONVOI_ACTIF_FILTRE, "attendu": False}}
	if clause not in conds:
		conds.append(clause)


# ── Élise : elle tutoie ; narration au « vous » ; accords neutres ─────────────────

def elise(doc):
	libelle(doc, "accueil", "s2", "(Poser ton sac près de sa table.)", "(Poser votre sac près de sa table.)")
	texte(doc, "apport_accepte", "la pose dans ta paume", "la pose dans votre paume")
	texte(doc, "apport_accepte", "Et si tu n'es pas sûr… »", "Et au moindre doute… »")
	texte(doc, "apport_rappel", "Et pas une que tu ne sois sûr de reconnaître. »",
		  "Et pas une que tu ne saches reconnaître à coup sûr. »")
	texte(doc, "s1_01", "Elle lève les yeux, voit ta main,", "Elle lève les yeux, voit votre main,")
	texte(doc, "s1_05", "« Tu peux commencer par revenir vivant.", "« Tu peux commencer par revenir en un seul morceau.")
	texte(doc, "s2_02", "combien de temps tu allais réussir à rester entier. »",
		  "combien de temps tu tiendrais sans te faire recoudre. »")
	texte(doc, "s2_04", "quand tu es fatigué. »", "quand tu n'en peux plus. »")
	texte(doc, "s2_08", "Elle pointe sur toi une pince à échardes.", "Elle pointe sur vous une pince à échardes.")
	libelle(doc, "s2_08", "soin", "(Lui tendre ton bras.)", "(Lui tendre votre bras.)")
	texte(doc, "s3_05", "« Tu n'es pas obligé. »", "« Rien ne t'y oblige. »")
	libelle(doc, "s3_06", "suite", "« Parce que vous m'avez déjà soigné gratuitement. »",
			"« Parce que vous me soignez sans jamais rien demander. »")
	texte(doc, "s3_10", "« Tu ne la cueilles pas si tu n'es pas sûr. »", "« Au moindre doute, tu ne la cueilles pas. »")
	libelle(doc, "depart", "fin", "(Retourner à ta chope.)", "(Retourner à votre chope.)")
	# Élise est une femme : l'accord se rapporte à elle.
	texte(doc, "soin_inutile", "Elle t'examine des pieds à la tête, l'air presque déçu.",
		  "Elle vous examine des pieds à la tête, l'air presque déçue.")


# ── Bouchard, route silencieuse : un accueil neutre, et le bon compte ─────────────

BOUCHARD_ACCUEIL = ("Bouchard n'est pas sous l'auvent. Il se tient près de la porte fortifiée, les bras croisés, "
					"les yeux sur la route du nord. Il vous entend venir sans se retourner. « {prenom}. »")
BOUCHARD_ANNONCE = ("« Les pèlerins sont arrivés à Rhemi. Tous les trois. » Un temps. « Il y a une autre escorte "
					"qui devait y arriver. Elle n'y est jamais arrivée. »")


def bouchard_route(doc):
	noeud(doc, "accueil")["texte"] = BOUCHARD_ACCUEIL
	acc = noeud(doc, "accueil")["choix"]
	anciens = {c["id"]: c for c in acc if c["id"] in ("route_offre", "route_rang")}
	acc[:] = [c for c in acc if c["id"] not in ("route_offre", "route_rang", "route_annonce", "route_annonce_rang")]
	acc.insert(0, {"id": "route_annonce_rang", "label": "« Vous guettez quelque chose ? »",
				   "condition": {"escorte_rang_insuffisant": True}, "next": "route_annonce"})
	acc.insert(0, {"id": "route_annonce", "label": "« Vous guettez quelque chose ? »",
				   "condition": {"escorte_offerte": True}, "next": "route_annonce"})
	if "route_annonce" not in doc["dialogue"]["noeuds"]:
		poser_noeud(doc, "route_annonce", {"texte": BOUCHARD_ANNONCE, "choix": [
			anciens["route_offre"], anciens["route_rang"],
			{"id": "retour", "label": "Revenir.", "next": "accueil"}]})
	texte(doc, "route_rapport", "« Deux. Sur six. »", "« Deux. Sur quatre. »")


# ── Armand de Vaucremont : le registre suit l'état de la mine ─────────────────────

REGISTRE_REMONTE = ("« Deux colonnes. » Il tourne le registre vers vous. « Elles ont fini par avoir la même "
					"longueur, et c'est bien ce qui m'inquiète : depuis que ça remonte, personne ne descend plus. "
					"Rien à gauche, rien à droite. » Il referme le volume. « Un registre vide n'est pas un registre "
					"tranquille. »")


def armand_vaucremont(doc):
	condition(doc, "accueil", "registre", {"acces_libere": False, "acces_reinfeste": False})
	poser_choix(doc, "accueil", {"id": "registre_libre", "label": "« Que notez-vous dans ce registre ? »",
								 "condition": {"acces_accompli": False, "acces_libere": True},
								 "next": "registre_open"}, apres="registre_open")
	poser_choix(doc, "accueil", {"id": "registre_reinfeste", "label": "« Que notez-vous dans ce registre ? »",
								 "condition": {"acces_reinfeste": True}, "next": "registre_remonte"},
				apres="registre_libre")
	poser_noeud(doc, "registre_remonte", {"texte": REGISTRE_REMONTE, "choix": [
		{"id": "retour", "label": "Revenir.", "next": "accueil"}]})


# ── Accords neutres et petites coquilles, PNJ par PNJ ─────────────────────────────

def eleonore_vaugirard(doc):
	texte(doc, "inscription_propose", "Vous serez inscrit au premier échelon, celui d'où tout le monde est parti.",
		  "Si votre nom est déjà dans ce registre, je vous referai la carte ; sinon, il entrera au premier "
		  "échelon, celui d'où tout le monde est parti.")
	libelle(doc, "inscription_trop_charge", "ok", "Je reviens plus léger.", "Je reviens le sac plus léger.")
	texte(doc, "rang_accepte", "Et revenez vivant, {prenom}", "Et revenez en vie, {prenom}")
	texte(doc, "acces_ouvre", "Frappez une fois, et soyez bref", "Frappez une fois, et allez droit au but")


def rochefort(doc):
	texte(doc, "voyage_offre", "« On m'a rapporté ce que vous êtes allé chercher dans les bois du nord, et dans quel "
		  "état vous l'avez ramené : entier. C'est le seul mot qui m'intéresse dans un rapport. »",
		  "« On m'a rapporté qui vous avez ramené des bois du nord, et dans quel état : debout, tous. C'est la "
		  "seule ligne qui m'intéresse dans un rapport. »")
	texte(doc, "depart", "« Tenez-vous prêt. Je vous l'ai dit", "« Ne vous éloignez pas. Je vous l'ai dit")


def frere_martin(doc):
	texte(doc, "voyage_offre", "« Vous êtes celui du nord.", "« C'est vous, l'affaire du nord.")


def armand_renaud(doc):
	texte(doc, "presentation", "« Ne restez pas planté là, {prenom}. Elles vous ont déjà senti. »",
		  "« Ne restez pas à découvert, {prenom}. Elles ont déjà votre odeur. »")


def etienne(doc):
	texte(doc, "accueil", "« Ne me demandez pas de me lever, l'ami. ", "« Ne me demandez pas de me lever. ")


def margot(doc):
	texte(doc, "apres", "« Plus une bête de perdue depuis que vous êtes passé. »",
		  "« Plus une bête de perdue depuis votre passage. »")


def jacotte(doc):
	texte(doc, "accueil", "« Bonjour, voyageur. N'aie pas peur", "« Bonjour à toi. N'aie pas peur")


def george(doc):
	texte(doc, "accueil", "« Halte, voyageur. »", "« Halte. »")
	texte(doc, "acces_refus", "Présentez-vous une commission d'éradication", "Présentez une commission d'éradication")
	texte(doc, "acces_deja", "La guilde vous a déjà mandaté — passez", "Votre mandat de la guilde, je l'ai déjà lu — passez")


def malakor(doc):
	texte(doc, "accueil", "soit sur toi, voyageur.", "soit sur toi.")
	libelle(doc, "accueil", "conseils", "Auriez-vous un conseil pour un nouveau venu ?",
			"Auriez-vous un conseil pour qui arrive en ville ?")


def capitaine_calais(doc):
	texte(doc, "accueil", "Pour vous tous — {passagers} à bord —, ce sera {tarif}.",
		  "Places à bord : {passagers}. Ce sera {tarif}.")


def capitaine_douvres(doc):
	texte(doc, "accueil", "Avec vous tous — {passagers} à bord —, le passage coûte {tarif}.",
		  "Places à bord : {passagers}. Le passage coûte {tarif}.")


# Tenanciers génériques (`pnj:marchand_*`) : mêmes formules d'un doc à l'autre.
MARCHANDS_TEXTE = [
	("« Vous êtes déjà chargé comme un mulet, {prenom} ! »", "« Vous portez déjà la charge d'un mulet, {prenom} ! »"),
	("« Je ne vous dois rien, l'ami : c'est {donneur}", "« Je ne vous dois rien : c'est {donneur}"),
	("On l'a vu prendre le chemin qui sort de {lieu_rencontre}, et personne ne l'a revu depuis.",
	 "Quelqu'un a vu partir mon enfant par le chemin qui sort de {lieu_rencontre}. Depuis, plus rien."),
	("Ramenez-moi mon enfant vivant", "Ramenez-moi mon enfant en vie"),
	("et vous serez toujours le bienvenu sous ce toit", "et cette maison vous sera toujours ouverte"),
]
MARCHANDS_LIBELLES = [
	("Je vous le ramènerai.", "Je vous ramènerai {protege}."),
	("Je reviendrai plus léger.", "Je reviendrai le sac plus léger."),
]


def marchand(doc):
	for ancien, nouveau in MARCHANDS_TEXTE:
		partout(doc, ancien, nouveau, "texte")
	for ancien, nouveau in MARCHANDS_LIBELLES:
		partout(doc, ancien, nouveau, "label")


CORRECTIFS = {
	"pnj:borin_barbe_de_jais": borin,
	"pnj:gautier_de_valcroix": gautier,
	"pnj:maelys": maelys,
	"pnj:aelis_de_montfaucon_cour_des_arches": aelis_cour,
	"lieu:la_cour_des_arches": cour_des_arches,
	"pnj:milo_cartographe": milo,
	"lieu:auberge_de_la_tour_de_l_horloge": auberge_horloge,
	"pnj:elise_herboriste": elise,
	"pnj:bouchard_de_clignancourt_route_silencieuse": bouchard_route,
	"pnj:templier_armand_de_vaucremont_01": armand_vaucremont,
	"pnj:eleonore_de_vaugirard": eleonore_vaugirard,
	"pnj:dame_eleonore_de_rochefort": rochefort,
	"pnj:frere_martin_de_clairvaux": frere_martin,
	"pnj:armand_renaud": armand_renaud,
	"pnj:etienne_morel": etienne,
	"pnj:bergere_margot_gueneau": margot,
	"pnj:meneuse_de_loups_jacotte": jacotte,
	"pnj:templier_nain_m_01": george,
	"pnj:reverend_malakor": malakor,
	"pnj:capitaine_calais": capitaine_calais,
	"pnj:capitaine_douvres": capitaine_douvres,
}


def corriger(base: dict) -> list:
	"""Docs corrigés qui DIFFÈRENT de `base` (ids du dump), dans un ordre stable."""
	sortie = []
	cibles = dict(CORRECTIFS)
	for did in sorted(base):
		if did.startswith("pnj:marchand_") and base[did].get("dialogue"):
			cibles[did] = marchand
	for did, fn in sorted(cibles.items()):
		if did not in base:
			sys.exit(f"ERREUR : {did} absent du dump")
		doc = copy.deepcopy(base[did])
		doc.pop("_rev", None)
		fn(doc)
		avant = {k: v for k, v in base[did].items() if k != "_rev"}
		if doc != avant:
			sortie.append(doc)
	return sortie


def main():
	base, nom = dernier_dump()
	docs = corriger(base)
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(docs)} docs ({nom}) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()
