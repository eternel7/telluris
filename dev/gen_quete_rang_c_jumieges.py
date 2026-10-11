#!/usr/bin/env python
# dev/gen_quete_rang_c_jumieges.py
# Épreuve du RANG C de Lutecia : Maëlys → Aélis (Cour des Arches) → le portail de l'abbaye
# de Jumièges → retour aux Archives des Seuils → rapport à Maëlys.
#
# 100 % DONNÉE, aucune ligne de moteur :
#   · `quete:rang_c_lettre_a_l_institut` = transport ÉCRIT à `retour` (Maëlys → la Cour des
#     Arches), `recompenses.rang_guilde: "C"` — c'est LUI qui monte le rang (précédent : la
#     première mission de Borin). Son `rapporter` exige en plus l'escorte réussie.
#   · `quete:escorte_aelis_abbaye_de_jumieges` = escorte écrite d'Aélis, offerte à la Cour une
#     fois la lettre remise ; DESTINATION les Archives des Seuils, fermées (`combat_gagne`)
#     tant que la nef n'est pas gagnée : on ne peut pas la déposer sans être passé à Jumièges.
#   · la nef (battle_map) s'ouvre par le service `acces` de la voix d'Aélis devant l'abbaye.
#
# ⚠️ UN SEUL FICHIER À IMPORTER (demande de l'Auteur) : jsons/quete_rang_c_abbaye_de_jumieges_a_importer.json
# porte TOUS les docs, neufs ET retouchés, chacun COMPLET (l'import est un PUT, CLAUDE.md §11).
# Les retouches partent du doc RELU : `pnj:maelys` depuis son fichier source (pas encore au
# dump), la Cour et son Aélis depuis le DERNIER DUMP. Les deux fichiers source reçoivent la même
# version, pour qu'un ré-import ne défasse pas la quête (verrouillé par
# tests/test_quete_rang_c_jumieges.py). Régénération idempotente.
#
# Usage : python dev/gen_quete_rang_c_jumieges.py [jsons/telluris-dump-….json]

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(JSONS, "quete_rang_c_abbaye_de_jumieges_a_importer.json")
SOURCE_MAELYS = os.path.join(JSONS, "maelys_maitresse_de_guilde_a_importer.json")
SOURCE_COUR = os.path.join(JSONS, "cour_des_arches_lutecia_a_importer.json")

LETTRE = "quete:rang_c_lettre_a_l_institut"
ESCORTE = "quete:escorte_aelis_abbaye_de_jumieges"
COUR = "lieu:la_cour_des_arches"
ARCHIVES = "lieu:les_archives_des_seuils"
ABBAYE = "lieu:abbaye_de_jumieges"
NEF = "lieu:nef_de_l_abbaye_de_jumieges"
ITEM_LETTRE = "item:lettre_de_mission_de_la_guilde"
AELIS_COUR = "pnj:aelis_de_montfaucon_cour_des_arches"
AELIS_JUMIEGES = "pnj:aelis_de_montfaucon_jumieges"
AELIS_ARCHIVES = "pnj:aelis_de_montfaucon_archives"
PORTRAIT_AELIS = "architecte_Aélis_de_Montfaucon_humain_f03.jpg"
# Image 3 de l'Auteur (Aélis devant l'Institut) : PORTRAIT du dialogue à la Cour tant que la
# mission n'est pas faite — l'image du lieu reste celle SANS elle.
PORTRAIT_AELIS_COUR = "architecte_Aélis_de_Montfaucon_cour_des_arches.jpg"
# Case de la carte de France : boucle de la Seine en aval de Rouen.
POS_FRANCE = [37, 11]
# « Ne plus rejouer » une scène d'ouverture : même valeur que les retrouvailles de la Cour.
DELAI_UNE_FOIS = 315360000

# ── Grille de la nef (image 1 : 720×1456, quadrillage mesuré de 19 × 36 cases) ──────────────
# '#' = 0 (mur, pilier, portail, herbe hors les murs) · '.' = 1 (dalles) · 'x' = 3 (bancs,
# éboulis, arcs effondrés : on ne marche pas dessus, un volant les survole).
GRILLE_NEF = [
	"###################",  # 0
	"###################",
	"###################",
	"###################",
	"###################",
	"#######.....#######",  # 5  abside
	"####..#.....#..####",
	"####x.#.....#.x####",
	"####..#....x#.x####",
	"####..#.....#.x####",
	"###...#.....#..####",  # 10 marches du chœur
	"#...x..x..x.....x.#",  # 11 transept
	"#..xx..x...x.xx...#",
	"#.xxx......x...x..#",
	"#..x......xx..xx..#",
	"####..#......######",  # 15 mur de la chapelle du portail
	"####........#######",  #    portail : x13-16, lignes 16-19
	"####........#######",
	"###.........#######",
	"###.........#######",
	"###...#.....#...###",  # 20 piliers
	"###xx.#x..x.#..x###",
	"###xxx.x...x...x###",
	"###.x.#x..x.#...###",
	"###...#x...x#...###",
	"###x...........x###",  # 25
	"###x..#.....#...###",
	"###...#.....#...###",
	"###.............###",
	"###...#.....#...###",
	"###x..#.....#.xx###",  # 30
	"###.x........xxx###",
	"########...########",  #    escalier d'entrée, au sud
	"########...########",
	"########...########",
	"########...########",  # 35
]
CODES = {"#": 0, ".": 1, "x": 3}


def cells_nef() -> list:
	return [[CODES[c] for c in ligne] for ligne in GRILLE_NEF]


def charger(chemin):
	with open(chemin, encoding="utf-8") as f:
		return json.load(f)


def ecrire(chemin, docs):
	with open(chemin, "w", encoding="utf-8", newline="\n") as f:
		f.write(json.dumps(docs, ensure_ascii=False, indent=2) + "\n")


def dernier_dump(argv):
	if len(argv) > 1:
		return argv[1]
	dumps = sorted(glob.glob(os.path.join(JSONS, "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump jsons/telluris-dump-*.json")
	return dumps[-1]


def sans_rev(doc):
	doc = copy.deepcopy(doc)
	doc.pop("_rev", None)
	return doc


def poser_choix(noeud: dict, choix: list, avant: str | None = None):
	"""Ajoute les choix ABSENTS (par id) au nœud — avant le choix `avant` s'il existe, sinon
	en fin. Idempotent : un choix déjà là est REMPLACÉ en place (texte régénéré)."""
	liste = noeud.setdefault("choix", [])
	for c in choix:
		idx = next((i for i, x in enumerate(liste) if x.get("id") == c["id"]), None)
		if idx is not None:
			liste[idx] = c
			continue
		pos = next((i for i, x in enumerate(liste) if x.get("id") == avant), len(liste))
		liste.insert(pos, c)


# ── Maëlys : l'épreuve, la lettre, le rapport ─────────────────────────────────────────────

def maelys(doc: dict) -> dict:
	doc = sans_rev(doc)
	doc.setdefault("services", {})["transport"] = {
		"offre": {
			"id": LETTRE,
			"destination": COUR,
			"cargaison": [{"item": ITEM_LETTRE, "quantite": 1, "poids": 0.05}],
			# Le délai ne porte que sur la LETTRE (Lutecia intra-muros) : il est levé à la
			# livraison d'une course `retour` (`livrer_en_attente_de_retour`), le voyage à
			# Jumièges n'est pas couru d'avance.
			"duree": 172800,
			"proba": 1,
			"unique": True,
			"retour": True,
			"rang": "C",
			"titre": "Rang C : le portail de Jumièges",
			"description": (
				"Maëlys, maîtresse de la Guilde, vous confie un pli scellé pour l'Institut "
				"des Architectes, à la Cour des Arches. L'architecte qui le recevra part pour "
				"les ruines de l'abbaye de Jumièges, en Normandie, où un portail s'est ouvert : "
				"escortez-la, ramenez-la vivante, puis revenez rendre compte au bureau de la "
				"maîtresse. Le rang C est au bout."),
			"recompenses": {"xp": 150, "cuivre": 20000, "rang_guilde": "C"},
		},
		"noeuds": {
			"propose": "rang_c_propose",
			"infos": "rang_c_infos",
			"accepte": "rang_c_accepte",
			"trop_charge": "rang_c_trop_charge",
			"rapporte": "rang_c_rapporte",
		},
	}
	noeuds = doc["dialogue"]["noeuds"]
	poser_choix(noeuds["accueil"], [
		{"id": "rang_c_offre", "label": "« On dit que l'épreuve du rang C, c'est vous qui la donnez. »",
		 "condition": {"transport_offert": True}, "next": "rang_c_propose"},
		{"id": "rang_c_relance", "label": "« Au sujet de la lettre pour l'Institut… »",
		 "condition": {"transport_en_cours": True}, "next": "rang_c_relance"},
		{"id": "rang_c_attente", "label": "« La lettre est remise. »",
		 "condition": {"transport_a_rapporter": True,
					   "quete_reussie": {"id": ESCORTE, "attendu": False}},
		 "next": "rang_c_pas_encore"},
		{"id": "rang_c_rapport",
		 "label": "« L'architecte est rentrée à la Cour des Arches, saine et sauve. »",
		 "condition": {"transport_a_rapporter": True, "quete_reussie": {"id": ESCORTE}},
		 "action": {"service": "transport", "op": "rapporter"}},
		{"id": "rang_c_souvenir", "label": "« Jumièges… »",
		 "condition": {"quete_reussie": {"id": LETTRE}}, "next": "rang_c_souvenir"},
	], avant="rien")
	noeuds.update({
		"rang_c_propose": {
			"texte": "Maëlys ne s'assied pas. Elle tire d'un casier un pli déjà scellé — la cire porte la porte ouverte de la Guilde — et le pose à plat sur la table, entre vous. « Le rang C, {prenom}, ne se gagne pas sur une bête abattue. Il se gagne le jour où je peux confier à quelqu'un la vie d'une personne qui ne sait pas se défendre, et le regarder partir sans compter les jours. » Elle tapote le pli du bout de l'index. « L'Institut des Architectes me demande une escorte. En Normandie, en aval de Rouen, dans les ruines de l'abbaye de Jumièges, un portail s'est ouvert. Personne ne l'a bâti. Ils envoient l'une des leurs l'examiner : Aélis de Montfaucon. Je crois que vous la connaissez. Portez-lui cette lettre à {destination}, faites ce qu'elle vous demandera, ramenez-la vivante. Ensuite seulement, revenez ici. »",
			"choix": [
				{"id": "rang_c_infos", "label": "« Que sait-on de ce portail ? »", "next": "rang_c_infos"},
				{"id": "rang_c_accepter", "label": "« Donnez-moi cette lettre. »",
				 "action": {"service": "transport", "op": "accepter"}},
				{"id": "rang_c_plus_tard", "label": "« Pas aujourd'hui. »", "next": "accueil"},
			],
		},
		"rang_c_infos": {
			"texte": "« Ce qu'en dit un berger, et ce qu'en devinent trois maîtres de la Cour qui ne l'ont pas vu. » Elle hausse une épaule. « De la lumière dans la nef, la nuit. Des choses qui bougent sur les dalles. Pour le reste, l'abbaye est sur une boucle de la Seine, deux tours encore debout : suivez le fleuve vers la mer, vous ne la manquerez pas. » Elle vous regarde droit dans les yeux. « Ce qui sort d'un portail que personne n'a bâti, je ne le sais pas. C'est précisément pour cela que je n'y envoie pas n'importe qui. Et ne traînez pas avec la lettre : l'Institut attend ma réponse avant de faire partir quelqu'un d'autre. »",
			"choix": [
				{"id": "rang_c_accepter", "label": "« Donnez-moi cette lettre. »",
				 "action": {"service": "transport", "op": "accepter"}},
				{"id": "rang_c_plus_tard", "label": "« Laissez-moi y réfléchir. »", "next": "accueil"},
			],
		},
		"rang_c_accepte": {
			"texte": "Elle vous tend le pli. Il ne pèse rien ; elle le retient pourtant un instant avant de le lâcher. « {destination}. En main propre. » Puis, déjà retournée vers ses cartes : « Et, {prenom} — là-bas, c'est elle qui décide quand on s'approche. Vous, vous décidez quand on recule. »",
			"choix": [{"id": "ok", "label": "« Compris. »", "next": "fin"}],
		},
		"rang_c_trop_charge": {
			"texte": "Maëlys regarde votre sac, puis vous. « Une lettre, {prenom}. Une seule. Si vous ne pouvez plus la glisser dans votre barda, vous ne pourrez pas non plus courir quand il le faudra. Allégez-vous. »",
			"choix": [{"id": "ok", "label": "« Je reviens plus léger. »", "next": "fin"}],
		},
		"rang_c_relance": {
			"texte": "« Le pli n'est pas arrivé. » Ce n'est pas une question. « {destination}. L'Institut n'enverra personne à Jumièges tant qu'il n'aura pas ma réponse — et le portail, lui, n'attend personne. »",
			"choix": [{"id": "ok", "label": "« J'y vais. »", "next": "fin"}],
		},
		"rang_c_pas_encore": {
			"texte": "Elle lève les yeux de ses registres. « Remise, oui. On me l'a fait savoir. » Un temps. « Je ne vous ai pas envoyé porter une lettre, {prenom}. Je vous ai envoyé ramener quelqu'un. Revenez quand l'architecte sera de retour à la Cour des Arches — pas avant. »",
			"choix": [{"id": "ok", "label": "« Elle le sera. »", "next": "fin"}],
		},
		"rang_c_rapporte": {
			"texte": "Maëlys vous écoute sans vous interrompre : la Seine, les deux tours, la nef, ce qui est sorti du portail et la façon dont c'est tombé. Elle ne prend aucune note. Quand vous vous taisez, elle ouvre le registre des rangs, y trace une ligne, puis fait glisser vers vous {prime} pièces de cuivre. « Rang C. » Elle referme le registre. « L'Institut m'a écrit ce matin. Leur architecte est rentrée avec plus de questions qu'elle n'en avait en partant. Chez eux, c'est un compliment. » Un temps. « Chez moi aussi. »",
			"choix": [{"id": "ok", "label": "« Merci, maîtresse. »", "next": "fin"}],
		},
		"rang_c_souvenir": {
			"texte": "« Jumièges. » Maëlys hoche la tête, une fois. « La Cour y a renvoyé des relevés. Le portail est toujours là, et personne ne sait encore vers où il ouvre. Ceux qui prétendent le savoir ne sont pas d'accord entre eux — ce qui, d'ordinaire, est bon signe : ils cherchent encore. »",
			"choix": [
				{"id": "retour", "label": "« Une autre question… »", "next": "accueil"},
				{"id": "fin", "label": "« Je ne vous retiens pas plus. »", "next": "conge"},
			],
		},
	})
	return doc


# ── Aélis à la Cour des Arches : la lettre, la mission, l'escorte ─────────────────────────

PROTEGEE = {
	"prenom": "Aélis",
	"nom": "de Montfaucon",
	"race": "humain",
	"sex": "F",
	"image": PORTRAIT_AELIS,
	"description": "Architecte de l'Institut, chercheuse en cristaux de mana. Elle part mesurer le portail de Jumièges, un carnet, un compas et trois rouleaux de vélin pour tout bagage. Elle ne sait pas se battre.",
}


def aelis_cour(doc: dict) -> dict:
	doc = sans_rev(doc)
	services = doc.setdefault("services", {})
	# Destinataire de la lettre (rôle « destinataire » d'un transport : livre / incomplet).
	services["transport"] = {"noeuds": {"livre": "lettre_lue", "incomplet": "lettre_absente"}}
	services["escorte"] = {
		"offre": {
			"id": ESCORTE,
			"titre": "Le portail de Jumièges",
			"description": "L'Institut des Architectes envoie Aélis de Montfaucon examiner un portail ouvert dans les ruines de l'abbaye de Jumièges, en Normandie, sur une boucle de la Seine en aval de Rouen. Conduisez-la jusqu'à la nef, protégez-la pendant qu'elle mesure, puis ramenez-la vivante aux Archives des Seuils, à la Cour des Arches. Elle ne sait pas se battre.",
			"destination": ARCHIVES,
			"proteges": [dict(PROTEGEE)],
			"unique": True,
			"proba": 1,
			"rang_min": {"cite": "lieu:lutecia", "rang": "D"},
			"recompenses": {"xp": 120, "cuivre": 10000},
		},
		"noeuds": {"accepte": "mission_acceptee"},
	}
	noeuds = doc["dialogue"]["noeuds"]
	choix_mission = [
		{"id": "lettre", "label": "Lui tendre le pli scellé de la Guilde.",
		 "condition": {"transport_a_livrer": True},
		 "action": {"service": "transport", "op": "livrer"}},
		{"id": "jumieges", "label": "« Quand partons-nous pour Jumièges ? »",
		 "condition": {"escorte_offerte": True, "transport_a_livrer": False,
					   "quete_active": {"id": LETTRE}},
		 "next": "mission_01"},
	]
	poser_choix(noeuds["retrouvailles_fin"], choix_mission, avant="fin")
	poser_choix(noeuds["accueil_suivant"], choix_mission, avant="travaux")
	noeuds.update({
		"lettre_lue": {
			"texte": "Aélis reconnaît le sceau avant même d'avoir le pli en main — la porte ouverte de la Guilde. Elle le rompt de l'ongle du pouce et lit debout, vite, puis une seconde fois, lentement. « {donneur} vous envoie. » Elle replie la lettre en quatre et la glisse dans son carnet. « J'avais demandé quelqu'un de sûr. Je n'avais pas osé demander quelqu'un que je connaisse. »",
			"choix": [
				{"id": "mission", "label": "« De quoi s'agit-il ? »", "next": "mission_01"},
			],
		},
		"lettre_absente": {
			"texte": "Aélis tend la main, puis la laisse retomber. « Le pli de la Guilde ? Vous ne l'avez plus. » Elle fronce les sourcils, plus inquiète que fâchée. « Retrouvez-le. Sans lui, l'Institut ne me laissera pas partir avec vous. »",
			"choix": [{"id": "fin", "label": "« Je reviens avec. »", "next": "fin"}],
		},
		"mission_01": {
			"texte": "Elle déroule sur la table un relevé couvert de cotes, d'une écriture qui n'est pas la sienne. « Jumièges. Une abbaye sur une boucle de la Seine, en aval de Rouen, en ruine depuis plus longtemps que la Cour ne tient de registres. Il y a vingt jours, un berger a vu de la lumière dans la nef. Un portail. » Elle pose le doigt sur un carré, au flanc nord du chœur. « Là. Où il n'y a ni autel d'ancrage, ni cristal, ni rien de ce que nous savons poser pour en faire tenir un. »",
			"choix": [
				{"id": "qui", "label": "« Qui l'a bâti ? »", "next": "mission_02"},
			],
		},
		"mission_02": {
			"texte": "« Personne. C'est tout le problème. » Elle s'interdit de sourire, et n'y parvient qu'à moitié. « Ou quelqu'un, il y a si longtemps que la pierre a oublié son nom. Ou la Vague, qui n'a pas fini de remuer ce qu'elle a remué. Trois maîtres de la Cour, trois réponses, et pas un ne veut aller voir. » Elle roule le relevé. « Moi, je veux aller voir. L'Institut m'y autorise si la Guilde m'accompagne. Il faut que j'approche à moins de dix pas pour mesurer — et le berger dit que quelque chose bouge sur les dalles, la nuit. »",
			"choix": [
				{"id": "accepter", "label": "« Je vous y conduis. »",
				 "action": {"service": "escorte", "op": "accepter"}},
				{"id": "attendre", "label": "« Laissez-moi me préparer. »", "next": "fin"},
			],
		},
		"mission_acceptee": {
			"texte": "Aélis ferme son carnet, glisse son compas à sa ceinture et cale trois rouleaux de vélin sous son bras. « Je suis prête. Je l'étais depuis vingt jours. » Elle marque un temps. « Je ne sais pas me battre, {prenom}. Vous le savez. Là-bas, je mesure ; vous, vous m'empêchez de mourir pendant que je mesure. C'est un partage honnête. » Puis, plus bas, avec un regard vers la table des apprentis : « Ils vont croire que je fugue. Laissons-les croire. »",
			"choix": [{"id": "ok", "label": "« En route. »", "next": "fin"}],
		},
	})
	return doc


def cour(doc: dict) -> dict:
	doc = sans_rev(doc)
	doc["pnj"] = [{
		"character": AELIS_COUR,
		"nom": "Aélis",
		"portrait": PORTRAIT_AELIS_COUR,
		# Toujours là tant que la mission n'est ni en cours (elle vous suit) ni faite (elle
		# est aux Archives). `quete_active` des barrières n'a pas de filtre `id` : la
		# destination de l'escorte la nomme.
		"probabilite": 1,
		"conditions": [
			{"quete_reussie": {"id": ESCORTE, "attendu": False}},
			{"quete_active": {"types": ["escorte"], "cible": ARCHIVES, "attendu": False}},
		],
		"description": "Une jeune architecte penchée sur un plan, un compas dans une main et un carnet épais sous le bras.",
	}]
	return doc


# ── Docs neufs ────────────────────────────────────────────────────────────────────────────

def docs_neufs() -> list:
	escorte_active = {"quete_active": {"types": ["escorte"], "cible": ARCHIVES}}
	return [
		{
			"_id": ITEM_LETTRE,
			"type": "item",
			"nom": "Lettre de mission de la Guilde",
			"sous_categorie": "",
			"icon": "✉️",
			"description": "Pli scellé à la porte ouverte, le sceau de la maîtresse de la Guilde de Lutecia, adressé à l'Institut des Architectes.",
			"rarete": "commun",
			"categorie": "document",
			"slots": [],
			"poids": 0.05,
		},
		{
			"_id": ARCHIVES,
			"type": "lieu",
			"label": "Les Archives des Seuils",
			"image": "archives_des_seuils_lutecia01.jpg",
			"categorie": "institut_des_architectes",
			"lieu_parent": "lieu:lutecia",
			"acces": {
				"refus": "Un archiviste referme la porte vitrée devant vous, poliment mais sans appel : les Archives des Seuils ne s'ouvrent qu'aux Architectes, et à ceux qui reviennent d'un seuil avec eux.",
				"cycle": 1,
				"conditions": [{"combat_gagne": {"lieu": NEF}}],
			},
			"pnj": [{
				"character": AELIS_ARCHIVES,
				"nom": "Aélis",
				"portrait": PORTRAIT_AELIS,
				"probabilite": 1,
				"conditions": [{"quete_reussie": {"id": ESCORTE}}],
				"description": "Une jeune architecte au milieu de relevés étalés, une plume entre les dents et un compas à la main.",
			}],
		},
		{
			"_id": "link:la_cour_des_arches_to_les_archives_des_seuils",
			"type": "connection",
			"nodes": [
				{"lieu": COUR, "pos": [0, 0], "label": "Retourner dans la cour"},
				{"lieu": ARCHIVES, "pos": [0, 0], "label": "Monter aux Archives des Seuils"},
			],
			"metadata": {"type": "institut_des_architectes", "status": "ouvert"},
		},
		{
			"_id": AELIS_ARCHIVES,
			"type": "pnj",
			"nom": "Aélis de Montfaucon",
			"race": "humain",
			"vocation": "lettre",
			"portrait": PORTRAIT_AELIS,
			"description": "Jeune architecte de l'Institut, rentrée de Jumièges avec un carnet plein de mesures qu'aucune théorie n'explique entièrement.",
			"dialogue": {
				"noeud_depart": "retour_01",
				"noeud_attente": "accueil",
				"noeuds": {
					"retour_01": {
						"texte": "Les Archives des Seuils montent sur trois étages de galeries, sous une coupole peinte. Aélis a fait vider une table entière : ses relevés de Jumièges y sont étalés, tenus aux coins par des presse-papiers de cristal. Autour, des architectes de toutes les Lignées se penchent, discutent, se contredisent. Elle vous aperçoit et, sans un mot, vous fait signe d'approcher.",
						"choix": [{"id": "disent", "label": "« Qu'en disent-ils ? »", "next": "retour_02"}],
					},
					"retour_02": {
						"texte": "« Ce que disent toujours les gens savants : trois choses incompatibles, chacune avec certitude. » Elle compte sur ses doigts. « Le vieux maître des Seuils jure qu'un portail des Frères dormait sous l'abbaye, et que la Vague l'a réveillé. Ses élèves répondent que les Frères n'ont rien bâti si loin de leurs routes, et qu'un portail peut naître seul, comme celui de Rome. Et l'archiviste en chef rappelle que personne n'a jamais vu un portail naître seul — il en conclut que quelqu'un l'a ouvert, et qu'il l'a ouvert exprès. »",
						"choix": [{"id": "vous", "label": "« Et vous ? »", "next": "retour_03"}],
					},
					"retour_03": {
						"texte": "Elle regarde longtemps son carnet ouvert. « Moi, j'ai mesuré. Les trois hypothèses tiennent dans mes chiffres, et aucune ne les explique tous. » Elle le referme. « La Cour a écrit aux Templiers ; quelqu'un gardera la nef. J'y retournerai un jour, avec de meilleurs instruments — et, si vous le voulez bien, avec vous. » Puis, d'un ton plus léger : « Allez voir la Guilde, {prenom}. La maîtresse attend votre récit, et je crois savoir ce que vous y gagnerez. »",
						"delai_min": DELAI_UNE_FOIS,
						"choix": [{"id": "fin", "label": "« À bientôt, Aélis. »", "next": "fin"}],
					},
					"accueil": {
						"texte": "Aélis lève les yeux d'une pile de relevés de Jumièges, une plume entre les dents qu'elle retire pour parler. « Vous. Asseyez-vous, si vous trouvez une chaise qui ne porte pas de vélin. »",
						"choix": [
							{"id": "nouveau", "label": "« Du nouveau sur le portail ? »", "next": "nouveau"},
							{"id": "fin", "label": "(Prendre congé.)", "next": "fin"},
						],
					},
					"nouveau": {
						"texte": "« Du nouveau, non. Du différent, toujours. » Elle tourne une feuille vers vous : deux tracés presque identiques. « Le même portail, relevé à dix jours d'écart. Il a changé d'une ligne. Un vivant aurait grandi ; une pierre aurait bougé. Je ne sais pas encore lequel des deux il est. »",
						"choix": [
							{"id": "retour", "label": "Revenir.", "next": "accueil"},
							{"id": "fin", "label": "(Prendre congé.)", "next": "fin"},
						],
					},
				},
			},
		},
		{
			"_id": ABBAYE,
			"type": "lieu",
			"label": "Les ruines de l'abbaye de Jumièges",
			"image": "abbaye_de_jumieges.jpg",
			"categorie": "chemin",
			"lieu_parent": "lieu:france",
			"pnj": [{
				"character": AELIS_JUMIEGES,
				"nom": "Aélis",
				"portrait": PORTRAIT_AELIS,
				"probabilite": 1,
				"conditions": [escorte_active],
				"description": "Aélis, au bord du sentier, son carnet ouvert sur les ruines.",
			}],
		},
		{
			"_id": "link:abbaye_de_jumieges_to_france",
			"type": "connection",
			"nodes": [
				{"lieu": "lieu:france", "pos": list(POS_FRANCE), "label": "Les ruines de Jumièges"},
				{"lieu": ABBAYE, "pos": [0, 0], "label": "Reprendre la route"},
			],
			"metadata": {"type": "chemin", "status": "ouvert"},
		},
		{
			"_id": AELIS_JUMIEGES,
			"type": "pnj",
			"nom": "Aélis de Montfaucon",
			"race": "humain",
			"vocation": "lettre",
			"portrait": PORTRAIT_AELIS,
			"description": "Aélis, devant les ruines de Jumièges, entre son carnet et le portail.",
			"services": {
				"acces": {"lieu": NEF, "noeuds": {"ouvre": "nef_ouverte", "refus": "nef_close"}},
			},
			"dialogue": {
				"noeud_depart": "accueil",
				"noeuds": {
					"accueil": {
						"texte": "Les deux tours de l'abbaye tiennent encore, ouvertes au ciel. Le chemin monte entre les haies jusqu'au portail effondré de la nef. Aélis s'est arrêtée au bord du sentier, carnet ouvert, et compte à mi-voix. « Quarante-deux pas de la porte à la croisée, d'après les vieux relevés. » Elle lève le menton vers les ruines. « Écoutez. »",
						"choix": [
							{"id": "ecouter", "label": "Tendre l'oreille.",
							 "condition": {"acces_ouvrable": True}, "next": "seuil"},
							{"id": "apres", "label": "« C'est fini. Vous avez vos mesures ? »",
							 "condition": {"acces_libere": True}, "next": "apres"},
							{"id": "fin", "label": "(S'éloigner des ruines.)", "next": "fin"},
						],
					},
					"seuil": {
						"texte": "Rien, d'abord. Puis un bourdonnement très bas, qui ne vient d'aucune direction et vous serre les dents. Entre les arcs du chœur, une lueur violette pulse, lente comme une respiration. Aélis a pâli, mais sa main n'a pas lâché le crayon. « Il n'a pas la couleur d'un portail entretenu. Il n'a la couleur d'aucun portail que je connaisse. » Quelque chose racle les dalles, dans la nef. Plusieurs choses. « Ils sont sortis de là. Il faut que j'approche à moins de dix pas. »",
						"choix": [
							{"id": "entrer", "label": "« Restez derrière moi. On entre. »",
							 "condition": {"acces_ouvrable": True},
							 "action": {"service": "acces", "op": "passer"}},
							{"id": "attendre", "label": "« Pas encore. »", "next": "accueil"},
						],
					},
					"nef_ouverte": {
						"texte": "Vous franchissez le seuil effondré. Trois silhouettes se retournent ensemble, cornes basses, et la lueur du portail allume dans leurs yeux un reflet de braise. « Des démons », souffle Aélis — puis, parce qu'elle ne peut pas s'en empêcher : « Ils ne s'éloignent pas du portail. Ils le gardent. »",
						"choix": [{"id": "ok", "label": "Tirer votre arme.", "next": "fin"}],
					},
					"nef_close": {
						"texte": "Aélis secoue la tête sans quitter la nef des yeux. « Pas maintenant. »",
						"choix": [{"id": "ok", "label": "Reculer.", "next": "fin"}],
					},
					"apres": {
						"texte": "Aélis est assise sur une marche du chœur, à dix pas du portail, le carnet couvert de chiffres jusque dans les marges. La lueur violette n'a pas faibli ; elle respire toujours. « J'ai mes mesures. J'en ai même trop : aucune ne ressemble à ce qu'on m'a appris. » Elle referme le carnet sur son crayon. « Il est stable. Pas d'ancrage, pas de cristal, personne pour l'entretenir — et il est stable. » Elle se lève, s'époussette. « Ramenez-moi à la Cour, {prenom}. Il faut que je pose tout cela à plat aux Archives avant de ne plus me souvenir que de ce que j'ai noté. »",
						"choix": [{"id": "ok", "label": "« En route pour Lutecia. »", "next": "fin"}],
					},
				},
			},
		},
		{
			"_id": NEF,
			"type": "lieu",
			"label": "La nef de l'abbaye de Jumièges",
			"image": "abbaye_de_jumieges_nef.jpg",
			"categorie": "battle_map",
			"dimensions": {"x": len(GRILLE_NEF[0]), "y": len(GRILLE_NEF)},
			"cells": cells_nef(),
			"nav": {},
			"tags": ["ruines", "abbaye", "portail", "donjon"],
			"acces": {
				"gardien": AELIS_JUMIEGES,
				"refus": "La nef est silencieuse. Le portail respire dans le chœur, et rien ne vous y attend.",
				"cycle": 1,
				"conditions": [escorte_active, {"combat_gagne": {"lieu": NEF, "attendu": False}}],
			},
		},
		{
			"_id": "donjon:abbaye_de_jumieges",
			"type": "donjon",
			"nom": "Le portail de Jumièges",
			"description": "Dans le chœur en ruine de l'abbaye de Jumièges, un portail s'est ouvert sans que personne l'ait bâti. Trois démons mineurs en sont sortis, et ne s'en éloignent pas.",
			"portail": ABBAYE,
			# Calibré au simulateur de duel contre les personnages de rang D du dump : à grade
			# égal, le démon mineur vaut un peu moins qu'un loup géant (les bûcherons, entrée
			# au rang D, grades 2-3) — d'où un cran au-dessus pour l'épreuve D → C.
			"niveau_min": 4,
			"niveau_max": 5,
			"battle_maps": [{
				"lieu": NEF,
				"especes": ["espece:demon_mineur"],
				"nb_monstres": 3,
				"niveau_min": 4,
				"niveau_max": 5,
			}],
		},
	]


def remplacer(docs: list, nouveau: dict) -> list:
	return [nouveau if d.get("_id") == nouveau["_id"] else d for d in docs]


def main(argv):
	dump = charger(dernier_dump(argv))
	par_id = {d["_id"]: d for d in dump["docs"]}
	source_maelys = charger(SOURCE_MAELYS)
	source_cour = charger(SOURCE_COUR)
	base_maelys = next(d for d in source_maelys if d["_id"] == "pnj:maelys")
	base_aelis = par_id.get(AELIS_COUR) or next(d for d in source_cour if d["_id"] == AELIS_COUR)
	base_cour = par_id.get(COUR) or next(d for d in source_cour if d["_id"] == COUR)

	retouches = [maelys(base_maelys), aelis_cour(base_aelis), cour(base_cour)]
	neufs = docs_neufs()
	collisions = [d["_id"] for d in neufs if d["_id"] in par_id]
	if collisions:
		print("⚠️ ids déjà présents au dump (écrasés par l'import) :", ", ".join(collisions))

	ecrire(SORTIE, retouches + neufs)
	for chemin, docs in ((SOURCE_MAELYS, source_maelys), (SOURCE_COUR, source_cour)):
		for r in retouches:
			docs = remplacer(docs, r)
		ecrire(chemin, docs)
	print(f"{len(retouches) + len(neufs)} docs → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main(sys.argv)
