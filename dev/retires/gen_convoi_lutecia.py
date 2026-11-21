# dev/gen_convoi_lutecia.py
# Mission scénarisée « Le convoi de Lutecia » → jsons/convoi_lutecia_a_importer.json
#
# Suite des bûcherons d'Auxerre : Dame Éléonore de Rochefort conduit la dernière livraison de
# cristaux de mana jusqu'à Notre-Dame, à Lutecia. Aélis de Montfaucon voyage avec le convoi.
# C'est une quête d'ESCORTE ÉCRITE (`services.escorte.offre`) à TROIS protégés, dont deux paladins
# qui SAVENT SE DÉFENDRE (`se_defend` + `equipement` : plates complètes et épée longue d'ordre) —
# ils frappent l'ennemi au contact sans jamais se déplacer.
#
# ⚠️ Idempotent PARCE QU'IL RELIT LE DUMP (source unique, CLAUDE.md §11) : `admin_import_bulk`
# fait un PUT COMPLET. Les docs déjà en base (les deux paladins, la cathédrale, Notre-Dame) sont
# recopiés et seuls les champs AJOUTÉS y sont injectés ; régénérer depuis un dump qui contient
# déjà ce contenu redonne exactement la même sortie.
#
# Six documents :
#   · pnj:dame_eleonore_de_rochefort, pnj:frere_martin_de_clairvaux — l'offre (la MÊME, depuis
#     une seule constante) + deux choix greffés et deux nœuds chacun ;
#   · lieu:la_cathedrale_saint_etienne_d_auxerre — présence des paladins, masqués PENDANT et
#     APRÈS le convoi (clause `quete_reussie` de `utils/acces.py`) ;
#   · lieu:notre_dame — les mêmes paladins, présents APRÈS la réussite ;
#   · pnj:dame_eleonore_de_rochefort_lutecia, pnj:frere_martin_de_clairvaux_lutecia — leurs
#     docs à Lutecia : leur accueil d'Auxerre décrit le parvis, un doc ne s'ouvre pas sur deux
#     décors.
#
# Notre-Dame (13/09) : son portail FONCTIONNE — les cristaux du convoi y sont taillés en gemmes de
# mana qui l'alimentent (plus de « sceau » ni de porte fermée) — et sa nef est gardée par un
# templier : les paladins attendent donc sur le PARVIS. La garde elle-même (templier, nef, porte)
# vit dans `dev/gen_garde_notre_dame.py`, qui réemploie ce module et écrit l'import complet.
# ⚠️ Ne plus réimporter `convoi_lutecia_a_importer.json` : son `lieu:notre_dame` pointe encore le
# templier sur le doc de George Dourdan.
#
# ⚠️ AUCUN nœud `services.escorte.noeuds.accepte` — et le linter ne le réclame pas : une
# acceptation qui porte `deplacer` en est dispensée (`utils/lint_dialogues`, branche escorte).
# La présence d'un PNJ est revérifiée à CHAQUE requête de dialogue (`routers/pnj._pnj_du_lieu`) et
# la condition masque les paladins dès l'acceptation : un nœud de réponse ferait échouer le clic
# suivant en « Personne à qui parler ici ». À la place, le choix d'acceptation porte `deplacer`,
# résolu APRÈS l'action : le client quitte le parvis avec le convoi (`moveTo`, page rechargée,
# groupe et fiche 📜 à jour) et aucune requête de dialogue ne suit.

import copy
import json
import os
import sys

DUMP = "jsons/telluris-dump-20260913-090240.json"
SORTIE = "jsons/convoi_lutecia_a_importer.json"

QUETE = "quete:escorte_convoi_de_lutecia"
BUCHERONS = "quete:escorte_bucherons_d_auxerre"
AUXERRE = "lieu:auxerre"
CATHEDRALE = "lieu:la_cathedrale_saint_etienne_d_auxerre"
NOTRE_DAME = "lieu:notre_dame"
ELEONORE = "pnj:dame_eleonore_de_rochefort"
MARTIN = "pnj:frere_martin_de_clairvaux"
ELEONORE_LUTECIA = "pnj:dame_eleonore_de_rochefort_lutecia"
MARTIN_LUTECIA = "pnj:frere_martin_de_clairvaux_lutecia"

PORTRAIT_ELEONORE = "paladin_Dame_Eleonore_de_Rochefort_elfe_f.jpg"
PORTRAIT_MARTIN = "paladin_Frere_Martin_de_Clairvaux_hobbit_m.jpg"
PORTRAIT_AELIS = "architecte_Aélis_de_Montfaucon_humain_f03.jpg"


def charger():
	with open(DUMP, encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"] if d.get("_id")}


def nu(doc):
	"""Doc du dump sans son `_rev` : il est de toute façon réattaché depuis la base."""
	return {k: v for k, v in copy.deepcopy(doc).items() if k != "_rev"}


def fin(label):
	return {"id": "fin", "label": label, "next": "fin"}


def _greffer(noeud: dict, ajouts: list) -> None:
	"""Insère `ajouts` juste avant le dernier choix (celui de sortie) du nœud, en RETIRANT
	d'abord toute version antérieure des mêmes ids — c'est ce qui rend la greffe idempotente
	quand le dump relu contient déjà ces choix (cf. `gen_mission_bucherons._greffer`)."""
	neufs = {c["id"] for c in ajouts}
	choix = [c for c in noeud["choix"] if c.get("id") not in neufs]
	noeud["choix"] = choix[:-1] + ajouts + choix[-1:]


# ---------------------------------------------------------------------------
# Les trois personnes du convoi — specs de `services.escorte.offre.proteges`
# ---------------------------------------------------------------------------
# Emplacements vérifiés contre le dump du 12/09 : 53 PA au total (l'épée n'en porte aucun).
# ⚠️ Les épaulières et l'épée portent chacune `bonus_malus_depl: -1` ⇒ −2 V ⇒ une action de
# moins (3 → 2). Aucune `caracteristiques` : stats de base raciales, comme tout protégé.
EQUIPEMENT_PLATES = {
	"torse": "item:Armure_plates_surcoat",
	"tete": "item:Heaume_de_plates",
	"epaules": "item:Epaulieres_de_plates",
	"mains": "item:Gantelets_de_plates",
	"jambes": "item:Jambières_de_plates",
	"pieds": "item:Bottes_de_plates",
	"main_droite": "item:Epee_longue_ordre",
}

PROTEGES = [
	{
		"prenom": "Aélis", "nom": "de Montfaucon", "race": "humain", "sex": "F",
		"image": PORTRAIT_AELIS,
		"description": "Architecte et chercheuse en cristaux de mana. Elle suit le convoi jusqu'à "
					   "Notre-Dame pour étudier le portail des Frères Aborigènes. Elle ne sait pas "
					   "se battre.",
	},
	{
		"prenom": "Éléonore", "nom": "de Rochefort", "race": "elfe", "sex": "F",
		"image": PORTRAIT_ELEONORE,
		"description": "Paladine, commandante du convoi. En plates complètes, l'épée d'ordre au "
					   "poing, elle frappe quiconque l'approche — mais ne quitte pas sa place.",
		"se_defend": True,
		"equipement": dict(EQUIPEMENT_PLATES),
	},
	{
		"prenom": "Martin", "nom": "de Clairvaux", "race": "hobbit", "sex": "M",
		"image": PORTRAIT_MARTIN,
		"description": "Paladin hobbit, second du convoi. Il ferme la marche en plates complètes, "
					   "l'épée d'ordre au poing, et ne court après personne.",
		"se_defend": True,
		"equipement": dict(EQUIPEMENT_PLATES),
	},
]

# ⚠️ UNE seule constante pour les deux donneurs : celui des deux paladins que le tirage de
# présence retient pose l'offre, et le même id garantit qu'on ne mène le convoi qu'une fois.
# Aucun `rencontre` : les trois rejoignent le groupe À L'ACCEPTATION, sur le parvis.
# ⚠️ La destination est le PARVIS (`lieu:notre_dame`), jamais la nef gardée : le convoi se solde
# en franchissant la porte, et une nef réservée au rang A de Lutecia rendrait la dépose impossible.
OFFRE = {
	"id": QUETE,
	"titre": "Le convoi de Lutecia",
	"description": "Dame Éléonore de Rochefort conduit la dernière livraison de cristaux de mana "
				   "d'Auxerre jusqu'à Notre-Dame, à Lutecia, où ils alimenteront le portail. Aélis "
				   "de Montfaucon voyage avec le convoi. Les deux paladins savent se défendre ; "
				   "l'architecte, non. Amenez-les tous les trois vivants sur le parvis de Notre-Dame.",
	"destination": NOTRE_DAME,
	"proteges": PROTEGES,
	"unique": True,
	"proba": 1,
	"rang_min": {"cite": AUXERRE, "rang": "D"},
	"recompenses": {"xp": 120, "cuivre": 30000},
}


# ---------------------------------------------------------------------------
# Présence : masqués PENDANT et APRÈS le convoi à Auxerre, présents APRÈS à Notre-Dame
# ---------------------------------------------------------------------------
# ⚠️ `giver_categorie` en plus de `cible` : une autre escorte vers Notre-Dame, confiée ailleurs,
# ne doit pas vider le parvis. Le donneur d'une offre écrite est le LIEU où elle est posée.
CONVOI_A_VENIR = [
	{"quete_active": {"types": ["escorte"], "cible": NOTRE_DAME,
					  "giver_categorie": "cathedral", "attendu": False}},
	{"quete_reussie": {"id": QUETE, "attendu": False}},
]
CONVOI_ARRIVE = [{"quete_reussie": {"id": QUETE}}]


def _choix_convoi():
	"""Les deux choix greffés chez chaque paladin. Conditions EXCLUSIVES : l'offre n'est posée
	qu'au rang requis (`poser_escorte_offerte`), et le refus parlé ne vaut que sous ce rang."""
	return [
		{
			"id": "convoi_offre",
			"label": "« Quand partons-nous, exactement ? »",
			"condition": {"escorte_offerte": True},
			"next": "convoi_propose",
		},
		{
			"id": "convoi_rang",
			"label": "« Quand partons-nous, exactement ? »",
			"condition": {"escorte_rang_insuffisant": True},
			"next": "convoi_rang_insuffisant",
		},
	]


def _accepter(label):
	"""⚠️ `deplacer` n'est PAS décoratif : c'est lui qui évite l'échec du clic suivant (cf.
	en-tête). Il est résolu après l'acceptation, le lien parvis → cité existe dans le dump."""
	return {
		"id": "convoi_accepter",
		"label": label,
		"action": {"service": "escorte", "op": "accepter"},
		"deplacer": AUXERRE,
	}


def eleonore(base):
	doc = nu(base[ELEONORE])
	doc.setdefault("services", {})["escorte"] = {"offre": copy.deepcopy(OFFRE)}
	noeuds = doc["dialogue"]["noeuds"]
	for nid in ("voyage_offre", "depart"):
		_greffer(noeuds[nid], _choix_convoi())
	noeuds.update({
		"convoi_propose": {
			"texte": "Elle referme le registre sur son pouce. « Aujourd'hui. » Pas de date annoncée "
					 "la veille : c'est ainsi qu'elle l'avait dit. « Sept caisses, mademoiselle de "
					 "Montfaucon, Frère Martin, moi — et vous, {prenom}, si vous tenez parole. Nous "
					 "ne livrons pas à un entrepôt de la capitale : nous livrons Notre-Dame. » Elle "
					 "voit la question venir et la devance. « Oui, Notre-Dame a un portail, et il "
					 "tourne jour et nuit. C'est le plus ancien qui fonctionne encore, et il se nourrit "
					 "de pierres de mana : ces cristaux-ci y seront taillés en gemmes, et chaque gemme "
					 "ouvrira un chemin. La demoiselle veut voir comment il a été bâti — l'Institut des "
					 "Architectes n'est à Lutecia que pour cela. » Un temps. « {xp} points "
					 "d'expérience et {prime} pièces de cuivre à l'arrivée. Frère Martin et moi "
					 "tiendrons nos lames si l'on vient nous chercher. La demoiselle, non. Ne la "
					 "laissez jamais seule. »",
			"choix": [
				_accepter("« Alors partons. » — Quitter le parvis avec le convoi."),
				{"id": "retour", "label": "« Pas encore. »", "next": "accueil"},
			],
		},
		"convoi_rang_insuffisant": {
			"texte": "« Pas encore. » Le registre reste ouvert, mais elle ne vous regarde plus. « Ce "
					 "que vous avez fait dans les bois du nord, je le sais. Ce que la guilde écrit de "
					 "vous, je le lis : il faut le rang {rang_requis} pour marcher à côté de ces "
					 "caisses. Ce n'est pas moi qui fixe la règle, et je ne la plierai pas pour une "
					 "route aussi longue. »",
			"choix": [
				{"id": "retour", "label": "« Je reviendrai avec le rang. »", "next": "accueil"},
				fin("« Je vous laisse à vos registres. »"),
			],
		},
	})
	return doc


def martin(base):
	doc = nu(base[MARTIN])
	doc.setdefault("services", {})["escorte"] = {"offre": copy.deepcopy(OFFRE)}
	noeuds = doc["dialogue"]["noeuds"]
	for nid in ("voyage_offre", "consignes"):
		_greffer(noeuds[nid], _choix_convoi())
	noeuds.update({
		"convoi_propose": {
			"texte": "Il se relève, frotte la craie de ses genoux et referme son carnet de sceaux. "
					 "« Aujourd'hui. Sept caisses, sept sceaux, trois personnes, et une paire de bras "
					 "de plus : la vôtre. » Il compte sur ses doigts. « Destination : Notre-Dame. Ne "
					 "faites pas cette tête, {prenom} — le portail ne mord personne, il mange des "
					 "pierres. Une gemme de mana par passage, et ces caisses-là en feront beaucoup. » "
					 "Il tapote la garde de son épée. « Dame Éléonore et moi, nous nous défendrons si "
					 "l'on vient nous chercher au contact. Nous ne courrons après personne : sur une "
					 "route, celui qui court après une bête laisse les caisses derrière lui. La "
					 "demoiselle, elle, ne sait tenir qu'un carnet. {xp} points d'expérience et "
					 "{prime} pièces de cuivre au bout, si vous nous amenez tous les trois jusqu'au "
					 "parvis. »",
			"choix": [
				_accepter("« En route, frère. » — Quitter le parvis avec le convoi."),
				{"id": "retour", "label": "« Laissez-moi un instant. »", "next": "accueil"},
			],
		},
		"convoi_rang_insuffisant": {
			"texte": "« Dame Éléonore signe les départs, et elle ne signera pas le vôtre. » Il se "
					 "remet à sa craie. « Rang {rang_requis} au registre de la guilde, au minimum. Ce "
					 "n'est pas de la méfiance, c'est de l'écriture : je n'ai pas de case pour vous "
					 "tant que la guilde n'en a pas rempli une. »",
			"choix": [
				{"id": "retour", "label": "« Compris. »", "next": "accueil"},
				fin("« Bonne journée, frère. »"),
			],
		},
	})
	return doc


# ---------------------------------------------------------------------------
# Les deux paladins à Lutecia (docs neufs)
# ---------------------------------------------------------------------------
# Ils se tiennent sur le PARVIS, au pied de la nef que garde le templier : ni eux ni le joueur n'y
# entrent sans y être autorisés. Leurs textes parlent de la garde SANS la conditionner — les flags
# `acces_*` ne sont calculés que pour le PNJ qui porte `services.acces`.

def eleonore_lutecia():
	return {
		"_id": ELEONORE_LUTECIA,
		"type": "pnj",
		"nom": "Dame Éléonore de Rochefort",
		"race": "elfe",
		"vocation": "paladin",
		"portrait": PORTRAIT_ELEONORE,
		"description": "Paladine, commandante des convois de cristaux d'Auxerre. Depuis l'arrivée du "
					   "dernier convoi, elle attend ses ordres sur le parvis de Notre-Dame, à Lutecia.",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Au pied des marches de la nef, Dame Éléonore regarde deux templiers faire "
							 "entrer une dernière caisse par les grandes portes. Tout au fond, la lueur du "
							 "portail tourne sans fin, et son bourdonnement fait trembler l'encre de son "
							 "registre ouvert. Elle vous reconnaît avant que vous ayez fait trois pas. "
							 "« {prenom}. Les sept sont entrées, comptées deux fois — Frère Martin y a "
							 "veillé. » Elle referme le registre. « L'ordre nous garde ici jusqu'à nouvel "
							 "ordre. »",
					"choix": [
						{"id": "portail", "label": "« Pourquoi porter à un portail ce qui appelle ? »",
						 "next": "portail"},
						{"id": "garde", "label": "« Le templier des marches ne laisse passer personne. »",
						 "next": "garde"},
						{"id": "aelis", "label": "« Et mademoiselle de Montfaucon ? »", "next": "aelis"},
						fin("« Je vous laisse à votre garde. »"),
					],
				},
				"portail": {
					"texte": "« Parce qu'ici, ce qui appelle est enfin employé. » Elle désigne la lueur, "
							 "au fond de la nef. « Une caisse de cristaux qui dort dans un entrepôt attire "
							 "les bêtes à trois lieues. La même caisse, taillée en gemmes violettes par les "
							 "ateliers du quartier, fait tourner cette arche : une gemme de deux cent "
							 "cinquante grammes, et le passage s'ouvre vers n'importe quel point du monde "
							 "connu. » Un temps. « À Auxerre, on cache le mana. Lutecia n'en a presque pas, "
							 "alors elle l'achète, et elle en fait des chemins. C'est toute la différence "
							 "entre un coffre et une route. »",
					"choix": [
						{"id": "garde", "label": "« Et qui garde ces chemins ? »", "next": "garde"},
						{"id": "aelis", "label": "« Et la demoiselle, dans tout cela ? »", "next": "aelis"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"garde": {
					"texte": "« Bouzereau ? » L'ombre d'un sourire. « Il ne laisse entrer que les porteurs "
							 "d'une carte de la guilde de Lutecia, et seulement au rang A. Moi-même, je n'ai "
							 "passé ces portes que derrière mes caisses, un ordre écrit du chapitre à la main, "
							 "et il l'a lu deux fois. » Elle suit du regard un voyageur qui ressort de la nef "
							 "en titubant, les cheveux encore dressés par l'orage du passage. « Un chemin qui "
							 "mène partout mène aussi à ce qu'on ne voudrait pas voir revenir. Je ne lui en "
							 "veux pas d'être prudent : je fais le même métier, sur les routes. »",
					"choix": [
						{"id": "portail", "label": "« Ce portail vaut tant de précautions ? »",
						 "next": "portail"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"aelis": {
					"texte": "« L'Institut des Architectes l'a réclamée dès le premier soir. » L'ombre d'un "
							 "sourire. « Elle a mesuré l'autel d'ancrage avant même d'avoir retiré son "
							 "manteau. Les Architectes ne sont à Lutecia que pour ce portail : un Frère "
							 "Aborigène l'a bâti, la grande vague ne l'a pas dérangé, et personne depuis n'a "
							 "su en faire un pareil. Elle dit que ses bâtisseurs savaient ce qu'ils "
							 "faisaient, et qu'ils ne l'ont écrit nulle part. Je crois qu'elle compte réparer "
							 "cet oubli. »",
					"choix": [
						{"id": "portail", "label": "« Et ce portail, justement ? »", "next": "portail"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
			},
		},
	}


def martin_lutecia():
	return {
		"_id": MARTIN_LUTECIA,
		"type": "pnj",
		"nom": "Frère Martin de Clairvaux",
		"race": "hobbit",
		"vocation": "paladin",
		"portrait": PORTRAIT_MARTIN,
		"description": "Paladin hobbit, second de Dame Éléonore. Il tient sur le parvis de Notre-Dame "
					   "le registre des caisses du dernier convoi d'Auxerre, jusqu'à nouvel ordre.",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Assis sur la dernière marche du parvis, dos aux grandes portes de la nef, "
							 "Frère Martin compare une empreinte de cire à celle qu'il a relevée à Auxerre, "
							 "puis la range dans son carnet avec un soin de relique. Chaque fois que le "
							 "bourdonnement du portail enfle derrière lui, son fusain tremble et il "
							 "grommelle. « Sept. » Il lève le nez. « Sept parties, sept arrivées, sept "
							 "intactes, et pas un essieu de cassé entre l'Yonne et la Seine. J'ai failli ne "
							 "pas le croire. Asseyez-vous, {prenom} — pas sur la craie. »",
					"choix": [
						{"id": "route", "label": "« Que retenez-vous de la route ? »", "next": "route"},
						{"id": "bruit", "label": "« Ce grondement ne vous gêne pas ? »", "next": "bruit"},
						{"id": "garde", "label": "« Qui garde ces portes ? »", "next": "garde"},
						{"id": "ordre", "label": "« Combien de temps restez-vous ici ? »", "next": "ordre"},
						fin("« Bonne garde, frère. »"),
					],
				},
				"route": {
					"texte": "Il compte sur ses doigts. « Un : les bêtes sentent les caisses bien avant "
							 "qu'on les voie. Deux : un paladin qui ne quitte pas sa place vaut mieux "
							 "qu'un paladin qui court. Trois : la demoiselle avait raison sur le point "
							 "trois, et je ne le lui dirai jamais. »",
					"choix": [
						{"id": "ordre", "label": "« Et maintenant ? »", "next": "ordre"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"bruit": {
					"texte": "« Il me gêne depuis notre arrivée, et il gênera encore mes petits-enfants. » "
							 "Il pointe son fusain par-dessus son épaule. « C'est le portail qui tourne. Un "
							 "bourdonnement pour dire qu'il tient, un claquement pour dire que quelqu'un "
							 "arrive, et une odeur d'orage pour dire d'où — les habitués reconnaissent la mer "
							 "ou la neige rien qu'au nez. » Il souffle sur son carnet. « Nos cristaux passent "
							 "chez les tailleurs du quartier et en ressortent en gemmes violettes de deux cent "
							 "cinquante grammes. Une gemme, un voyage. J'ai fait le calcul pour les sept "
							 "caisses. Je ne vous dirai pas le résultat : vous ne dormiriez plus. »",
					"choix": [
						{"id": "garde", "label": "« Et qui décide qui voyage ? »", "next": "garde"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"garde": {
					"texte": "« Bouzereau. » Il baisse la voix, par prudence plus que par crainte. « Un "
							 "ogre qui sait lire, ce qui est rare, et qui lit tout, ce qui est pire. Carte "
							 "de la guilde de Lutecia, rang A, et rien d'autre — pas de recommandation, pas "
							 "de sceau d'Auxerre, pas même le mien. » Il tapote son carnet. « J'ai essayé, "
							 "avec mon sceau d'ordre. Il l'a regardé longtemps, puis il m'a demandé où je "
							 "comptais aller. J'ai dit : nulle part. Il a dit : alors vous n'avez pas besoin "
							 "d'entrer. » Il range son fusain. « Je n'ai rien trouvé à répondre. C'est la "
							 "première fois depuis Clairvaux. »",
					"choix": [
						{"id": "bruit", "label": "« Et ce grondement, d'où vient-il ? »", "next": "bruit"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"ordre": {
					"texte": "« Jusqu'à nouvel ordre, nous restons sur ce parvis. » Il hausse les épaules. "
							 "« Dame Éléonore tient le registre du convoi, je tiens celui des caisses, et le "
							 "chapitre tient les deux. Quand Auxerre aura une autre livraison, on nous le "
							 "fera savoir — tard, comme d'habitude. »",
					"choix": [
						{"id": "route", "label": "« Parlez-moi encore de la route. »", "next": "route"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
			},
		},
	}


# ---------------------------------------------------------------------------
# Lieux
# ---------------------------------------------------------------------------

def cathedrale(base):
	"""Martin EN PREMIER (30 %), Éléonore ensuite (100 %) : quelqu'un est toujours là pour
	proposer le convoi (le tirage retient la première entrée qui gagne), Éléonore dans ~70 % des
	visites. Les entrées sont RECONSTRUITES par `character` depuis le dump — nom, portrait, image
	et description survivent — et toute autre entrée est gardée à la suite."""
	doc = nu(base[CATHEDRALE])
	entrees = {e.get("character"): e for e in doc.get("pnj") or [] if isinstance(e, dict)}
	autres = [e for e in doc.get("pnj") or []
			  if not (isinstance(e, dict) and e.get("character") in (ELEONORE, MARTIN))]
	doc["pnj"] = [
		dict(entrees[MARTIN], probabilite=0.3, conditions=copy.deepcopy(CONVOI_A_VENIR)),
		dict(entrees[ELEONORE], probabilite=1, conditions=copy.deepcopy(CONVOI_A_VENIR)),
	] + autres
	return doc


def notre_dame(base):
	"""Les deux paladins APRÈS la réussite, placés avant le templier. Présences cumulables : chaque
	entrée tire sa propre probabilité, et le templier (sans `probabilite`, donc 1) garde toujours
	les marches. Toute autre entrée est conservée telle quelle à la suite."""
	doc = nu(base[NOTRE_DAME])
	autres = [e for e in doc.get("pnj") or []
			  if not (isinstance(e, dict) and e.get("character") in (ELEONORE_LUTECIA, MARTIN_LUTECIA))]
	doc["pnj"] = [
		{
			"character": ELEONORE_LUTECIA,
			"nom": "Dame Éléonore de Rochefort",
			"portrait": PORTRAIT_ELEONORE,
			"probabilite": 0.25,
			"conditions": copy.deepcopy(CONVOI_ARRIVE),
			"description": "Une paladine en haubert clair, au pied des marches de la nef.",
		},
		{
			"character": MARTIN_LUTECIA,
			"nom": "Frère Martin de Clairvaux",
			"portrait": PORTRAIT_MARTIN,
			"probabilite": 0.25,
			"conditions": copy.deepcopy(CONVOI_ARRIVE),
			"description": "Un paladin hobbit assis sur la dernière marche du parvis, un carnet de "
						   "sceaux sur les genoux.",
		},
	] + autres
	return doc


# ---------------------------------------------------------------------------

def verifier_collisions(base):
	"""Refuse d'écrire si le contenu ÉCRASERAIT autre chose que lui-même : `admin_import_bulk`
	fait un PUT complet, une collision d'`_id` passerait inaperçue (CLAUDE.md §11)."""
	for pid, d in base.items():
		offre = (((d.get("services") or {}).get("escorte") or {}).get("offre") or {})
		if offre.get("id") == QUETE and pid not in (ELEONORE, MARTIN):
			sys.exit(f"{QUETE} est déjà confiée par {pid} : génération refusée.")
	for neuf in (eleonore_lutecia(), martin_lutecia()):
		ancien = base.get(neuf["_id"])
		if ancien and (ancien.get("type") != "pnj" or ancien.get("nom") != neuf["nom"]):
			sys.exit(f"{neuf['_id']} existe déjà pour un autre PNJ ({ancien.get('nom')!r}) : "
					 f"génération refusée.")


def main():
	base = charger()
	verifier_collisions(base)
	docs = [
		eleonore(base), martin(base),
		cathedrale(base), notre_dame(base),
		eleonore_lutecia(), martin_lutecia(),
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
