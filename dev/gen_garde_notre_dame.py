# dev/gen_garde_notre_dame.py
# Garde de Notre-Dame (Lutecia) → jsons/garde_notre_dame_a_importer.json
#
# Même système qu'au Temple-Portail de Saint-Austrelin (`dev/gen_acces_donjon.py`) : un templier
# se tient sur le PARVIS, la barrière est portée par le lieu de DESTINATION (la nef du portail),
# et la porte est un doc `connection` ordinaire. Florian Bouzereau tient à Notre-Dame le rôle que
# George Dourdan tient à Auxerre.
#
#   carte d'aventurier émise par la guilde de Lutecia  ET  rang A à Lutecia
#   → Florian Bouzereau pose le laissez-passer → la nef du portail s'ouvre
#
# ⚠️ Florian n'avait PAS de doc : son entrée sur `lieu:notre_dame` pointait `pnj:templier_nain_m_01`,
# c'est-à-dire George Dourdan — dont le service `acces` garde la nef d'AUXERRE. Lui parler à
# Lutecia aurait ouvert (ou refusé) le portail d'une autre cité. Il reçoit ici son propre doc, et
# George n'est pas touché.
#
# ⚠️ AUCUNE guilde n'existe encore à Lutecia (dump du 13/09) : ni la carte de Lutecia ni un rang à
# Lutecia ne peuvent s'obtenir. La nef est donc fermée à TOUS tant qu'aucun comptoir n'y est posé
# — c'est la règle voulue, pas un défaut du générateur.
#
# Huit documents, un seul fichier :
#   · pnj:templier_florian_bouzereau — neuf : gardien, service `acces`, dialogue ;
#   · lieu:notre_dame_portail — neuf : la nef du portail, porte le bloc `acces` ;
#   · link:notre_dame_portail_to_notre_dame — neuf : la porte parvis ↔ nef ;
#   · lieu:notre_dame — relu du dump : présences des paladins (gen_convoi_lutecia) + Florian
#     repointé sur son doc ;
#   · les quatre docs des paladins, construits par `gen_convoi_lutecia` — SOURCE UNIQUE de leurs
#     textes (le portail y fonctionne, la garde y est évoquée). Les recopier ici ferait diverger
#     les deux générateurs au premier rejeu.
#
# ⚠️ Idempotent parce qu'il relit le dump (CLAUDE.md §11) : la nef et la porte, une fois en base,
# sont relues telles quelles et seul `acces` y est réécrit ; le parvis n'y perd que l'id du
# mauvais gardien.
#
# Usage : python dev/gen_garde_notre_dame.py   (depuis la racine du dépôt)

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_convoi_lutecia as convoi  # noqa: E402

DUMP = "jsons/telluris-dump-20260913-090240.json"
SORTIE = "jsons/garde_notre_dame_a_importer.json"

LUTECIA = "lieu:lutecia"
NOTRE_DAME = convoi.NOTRE_DAME
NEF = "lieu:notre_dame_portail"
PORTE = "link:notre_dame_portail_to_notre_dame"
FLORIAN = "pnj:templier_florian_bouzereau"
GEORGE = "pnj:templier_nain_m_01"
CARTE = "item:carte_aventurier"

PORTRAIT_FLORIAN = "templier_ogre_m_garde_temple02.jpg"
IMAGE_NEF = "portail_de_temple_notre_dame.png"


# ---------------------------------------------------------------------------
# La barrière — portée par la NEF, jamais par la porte
# ---------------------------------------------------------------------------
# Les DEUX clauses, en ET : `rang_min` lit `rangs_guilde[lieu:lutecia]`, qui survit à la perte de
# la carte ; `item` lit le `lieu_parent` de l'INSTANCE en sac (`item_ref_lieu`), donc une carte
# d'Auxerre ne vaut rien ici. Ni l'une ni l'autre ne suffit seule.
ACCES_NEF = {
	"gardien": FLORIAN,
	"refus": "Un templier ogre barre les portes de la nef : le portail de Notre-Dame n'est ouvert "
			 "qu'aux aventuriers de rang A de la guilde de Lutecia.",
	"cycle": 1,
	"conditions": [
		{"item": {"item": CARTE, "lieu_parent": LUTECIA}},
		{"rang_min": {"cite": LUTECIA, "rang": "A"}},
	],
}

TEXTE_NEF = (
	"Sous les voûtes de Notre-Dame, au fond de la nef, une arche de pierre ouvragée s'ouvre dans le "
	"jubé sur un vortex d'un blanc bleuté qui ne cesse jamais de tourner. Un bourdonnement grave monte "
	"des dalles et fait trembler la flamme des cierges ; à intervalles irréguliers, un claquement sec "
	"et une odeur d'orage annoncent un voyageur venu de l'autre bout du monde connu.\n"
	"Devant l'arche, l'autel d'ancrage — une grande roue de pierre gravée de runes — porte en son cœur "
	"la gemme de mana violette qui alimente le passage : deux cent cinquante grammes, et le chemin "
	"demeure. Depuis les tribunes, des maîtres de l'Institut des Architectes entretiennent l'ancrage, "
	"tandis que les templiers tiennent le cercle autour de l'autel et contrôlent ceux qui en reviennent."
)


# ---------------------------------------------------------------------------
# Florian Bouzereau — doc neuf
# ---------------------------------------------------------------------------

def _retour(label="Revenir."):
	return {"id": "retour", "label": label, "next": "accueil"}


def _entrer():
	"""`deplacer` = résolution de la `connection` parvis → nef par `move_character` : la garde 403
	y est revérifiée, le laissez-passer qui vient d'être posé la satisfait."""
	return {"id": "fin", "label": "Entrer dans la nef.", "next": "fin", "deplacer": NEF}


def florian():
	return {
		"_id": FLORIAN,
		"type": "pnj",
		"nom": "Florian Bouzereau",
		"race": "ogre",
		"vocation": "garde",
		"portrait": PORTRAIT_FLORIAN,
		"description": "Templier ogre de la garde de Notre-Dame. Il se tient devant les portes de la "
					   "nef, là où le parvis cesse d'être à tout le monde, et ne laisse approcher le "
					   "portail des Frères Aborigènes qu'aux aventuriers de rang A de la guilde de Lutecia.",
		"services": {
			"acces": {
				"lieu": NEF,
				"noeuds": {"ouvre": "acces_ouvre", "refus": "acces_refus", "deja": "acces_deja"},
			},
		},
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Au sommet des marches, devant les grandes portes de la nef, {pnj} barre le "
							 "passage de toute sa carrure d'ogre, une épée parcourue d'éclairs plantée à côté de lui "
							 "comme une borne. Derrière lui, tout au fond, la lueur du portail tourne sans "
							 "fin, et un bourdonnement grave fait vibrer les dalles jusque sous vos pieds. "
							 "« Halte. Le parvis est à tout le monde. La nef, non. »",
					"choix": [
						{
							"id": "passer",
							"label": "« Laissez-moi passer. »",
							"condition": {"acces_ouvrable": True},
							"action": {"service": "acces", "op": "passer"},
						},
						{
							"id": "deja",
							"label": "« C'est encore moi. »",
							"condition": {"acces_ouvert": True},
							"next": "acces_deja",
						},
						{
							"id": "pourquoi",
							"label": "« Qui a le droit d'entrer ? »",
							"condition": {"acces_refuse": True},
							"next": "acces_refus",
						},
						{
							"id": "convoi",
							"label": "« Les caisses d'Auxerre sont entrées. Pourquoi pas moi ? »",
							"condition": {"quete_reussie": {"id": convoi.QUETE}, "acces_refuse": True},
							"next": "convoi",
						},
						{"id": "bruit", "label": "« Ce grondement, c'est le portail ? »", "next": "bruit"},
						{"id": "gemmes", "label": "« De quoi se nourrit-il ? »", "next": "gemmes"},
						{"id": "architectes", "label": "« Pourquoi tant d'architectes sur le parvis ? »",
						 "next": "architectes"},
						{"id": "rien", "label": "« Rien, je repars. »", "next": "fin"},
					],
				},
				"acces_ouvre": {
					"texte": "{pnj} prend votre carte d'aventurier, la retourne, suit d'un doigt énorme le "
							 "sceau de la guilde de Lutecia et le rang inscrit en marge, puis vous la rend. "
							 "Il s'écarte d'un pas, et le bourdonnement de la nef vous arrive d'un coup, "
							 "plein, comme une porte qu'on ouvre sur une forge. « Passez. Ne touchez pas à "
							 "l'autel, ne marchez pas dans les tracés des Architectes, et si l'arche change "
							 "de couleur, reculez sans discuter. »",
					"choix": [_entrer()],
				},
				"acces_refus": {
					"texte": "« {portail}, ce n'est pas un passage de foire. » Il ne bouge pas d'un pouce. "
							 "« Deux choses, et les deux ensemble : une carte de la guilde des aventuriers "
							 "de Lutecia — pas celle d'Auxerre, pas celle d'ailleurs — et le rang A inscrit "
							 "dessus. » Il désigne la lueur du fond d'un mouvement de menton. « Cette arche "
							 "vous pose n'importe où dans le monde connu. La guilde de Lutecia répond de "
							 "ceux qu'elle y envoie. Les autres, personne ne sait où ils finissent, ni ce "
							 "qu'ils ramènent avec eux. »",
					"choix": [_retour(), convoi.fin("S'en aller.")],
				},
				"acces_deja": {
					"texte": "« Vous, je vous connais. » {pnj} s'écarte avant que vous ayez sorti votre "
							 "carte. « Passez, {prenom}. L'autel est chargé : les Architectes ont posé une "
							 "gemme neuve ce matin. »",
					"choix": [_entrer(), _retour()],
				},
				"convoi": {
					"texte": "Il a un grognement qui ressemble à un rire. « Les caisses d'Auxerre, je les "
							 "ai fait porter jusqu'aux cryptes par mes propres templiers. Elles ne vont "
							 "nulle part, les caisses : on les taille en gemmes, et l'autel les mange. » Il "
							 "vous regarde de haut, ce qui ne lui demande aucun effort. « Vous, vous iriez "
							 "quelque part. Dame Éléonore répond de vous sur la route de l'Yonne, et je la "
							 "crois. Mais la route de l'Yonne n'est pas le monde. Revenez avec la carte de "
							 "Lutecia et le rang A. »",
					"choix": [
						{"id": "gemmes", "label": "« On les taille en gemmes ? »", "next": "gemmes"},
						_retour(),
					],
				},
				"bruit": {
					"texte": "« Le portail. » Il le dit comme on nomme un voisin bruyant. « Il tourne jour "
							 "et nuit. Le bourdonnement, c'est l'arche qui tient son ancrage. Le claquement "
							 "sec, de temps en temps, c'est quelqu'un qui arrive d'un bout du monde. » Il "
							 "tend l'oreille, et vous l'entendez aussi : un craquement bref, puis une odeur "
							 "d'orage qui descend les marches. « Tenez, en voilà un. Le jour où ça se tait, "
							 "on court tous. Ça ne s'est jamais tu. »",
					"choix": [
						{"id": "gemmes", "label": "« Et qu'est-ce qui le fait tourner ? »", "next": "gemmes"},
						_retour(),
					],
				},
				"gemmes": {
					"texte": "« Des pierres de mana. » Il lève un poing gros comme un melon. « Une gemme "
							 "violette de deux cent cinquante grammes, pas plus lourde que ça, posée au cœur "
							 "de l'autel, et l'arche vous ouvre un chemin jusqu'à l'autre bout du monde "
							 "connu. Les portails que la grande vague a dérangés en avalent des caisses "
							 "entières pour trois cités de distance, quand ils ne vous recrachent pas de "
							 "travers. » Il frappe le pavé du talon. « Celui-ci, la vague ne l'a pas touché : "
							 "il n'y a presque pas de mana par ici, et c'est justement ce qui l'a sauvé. Les "
							 "pierres, on les fait venir de loin, et on les garde en bas, dans les cryptes. »",
					"choix": [
						{"id": "architectes", "label": "« Qui les pose, ces pierres ? »",
						 "next": "architectes"},
						_retour(),
					],
				},
				"architectes": {
					"texte": "« L'Institut. » Il jette un regard vers un groupe en manteaux gris qui mesure "
							 "une colonne du porche à la chaîne d'arpenteur. « Les Architectes ne sont à "
							 "Lutecia que pour ce portail. Un des Frères Aborigènes l'a posé sur cette île "
							 "avant qu'il y ait une cité autour, et personne depuis n'a su en bâtir un "
							 "pareil. Alors ils viennent l'étudier : l'arche, les runes de l'autel, les "
							 "ancrages. Ceux qui finissent par comprendre partent entretenir les portails "
							 "des autres cités. » Il hausse les épaules, ce qui fait grincer ses plates. "
							 "« Ceux qui ne comprennent pas restent ici et mesurent mes colonnes. »",
					"choix": [
						{"id": "bruit", "label": "« Et ce grondement, ils savent l'expliquer ? »",
						 "next": "bruit"},
						_retour(),
					],
				},
			},
		},
	}


# ---------------------------------------------------------------------------
# La nef, la porte, le parvis
# ---------------------------------------------------------------------------

def nef(base):
	"""Miroir de `lieu:temple_portail_de_saint_austrelin_interieur`. Relue du dump si elle y est
	(une retouche de texte ou d'image faite en base survit), seul `acces` est réécrit."""
	if NEF in base:
		doc = convoi.nu(base[NEF])
	else:
		doc = {
			"_id": NEF,
			"type": "lieu",
			"label": "Le portail de Notre-Dame",
			"image": IMAGE_NEF,
			"categorie": "portail",
			"sous_categorie": "temple",
			"lieu_parent": LUTECIA,
			"texte": TEXTE_NEF,
		}
	doc["acces"] = copy.deepcopy(ACCES_NEF)
	return doc


def porte(base):
	"""⚠️ Un bloc `acces` n'est pas une porte : sans ce doc `connection`, la nef serait gardée
	mais inatteignable. Le `label` d'un nœud nomme le geste qui MÈNE à ce nœud (miroir de
	`link:temple_portail_saint_austrelin_interieur_to_exterieur`)."""
	if PORTE in base:
		return convoi.nu(base[PORTE])
	return {
		"_id": PORTE,
		"type": "connection",
		"nodes": [
			{"lieu": NOTRE_DAME, "pos": [0, 0], "label": "ressortir sur le parvis"},
			{"lieu": NEF, "pos": [0, 0], "label": "entrer dans la nef"},
		],
		"metadata": {"type": "temple", "status": "ouvert"},
	}


def parvis(base):
	"""Le parvis tel que le construit `gen_convoi_lutecia` (présences des paladins), dont l'entrée
	du templier est repointée sur SON doc. Nom et portrait de l'entrée — posés dans l'éditeur —
	sont gardés tels quels : `{pnj}` prend le nom de l'entrée (`pnj.nom_effectif`)."""
	doc = convoi.notre_dame(base)
	repointees = 0
	for entree in doc.get("pnj") or []:
		if isinstance(entree, dict) and entree.get("character") in (GEORGE, FLORIAN):
			entree["character"] = FLORIAN
			repointees += 1
	if repointees != 1:
		sys.exit(f"{NOTRE_DAME} : {repointees} entrée(s) de templier trouvée(s), 1 attendue — "
				 f"génération refusée (on ne réinvente pas un gardien absent du dump).")
	return doc


# ---------------------------------------------------------------------------

def verifier_collisions(base):
	"""PUT complet (CLAUDE.md §11) : refuser d'écrire plutôt qu'écraser un doc qui n'est pas le nôtre."""
	convoi.verifier_collisions(base)
	ancien = base.get(FLORIAN)
	if ancien and (ancien.get("type") != "pnj" or ancien.get("nom") != "Florian Bouzereau"):
		sys.exit(f"{FLORIAN} existe déjà pour un autre PNJ ({ancien.get('nom')!r}) : génération refusée.")
	ancien = base.get(NEF)
	if ancien and (ancien.get("type") != "lieu" or ancien.get("lieu_parent") != LUTECIA):
		sys.exit(f"{NEF} existe déjà hors de Lutecia : génération refusée.")
	ancien = base.get(PORTE)
	if ancien and {n.get("lieu") for n in ancien.get("nodes") or []} != {NOTRE_DAME, NEF}:
		sys.exit(f"{PORTE} existe déjà et relie autre chose : génération refusée.")
	if CARTE not in base:
		sys.exit(f"{CARTE} introuvable dans {DUMP} : la barrière ne pourrait jamais s'ouvrir.")
	for pid, d in base.items():
		gardien = (d.get("acces") or {}).get("gardien") if isinstance(d.get("acces"), dict) else None
		if gardien == FLORIAN and pid != NEF:
			sys.exit(f"{pid} est déjà gardé par {FLORIAN} : génération refusée.")


def main():
	with open(DUMP, encoding="utf-8") as f:
		base = {d["_id"]: d for d in json.load(f)["docs"] if d.get("_id")}
	verifier_collisions(base)
	docs = [
		florian(), nef(base), porte(base), parvis(base),
		convoi.eleonore_lutecia(), convoi.martin_lutecia(),
		convoi.eleonore(base), convoi.martin(base),
	]
	os.makedirs("jsons", exist_ok=True)
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{SORTIE} : {len(docs)} documents")
	for d in docs:
		print("  ", d["_id"])


if __name__ == "__main__":
	main()
