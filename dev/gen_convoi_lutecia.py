# dev/gen_convoi_lutecia.py
# Mission scénarisée « Le convoi de Lutecia » → jsons/convoi_lutecia_a_importer.json
#
# Suite des bûcherons d'Auxerre : Dame Éléonore de Rochefort conduit la dernière livraison de
# cristaux de mana jusqu'aux cryptes de Notre-Dame, à Lutecia. Aélis de Montfaucon voyage avec
# le convoi. C'est une quête d'ESCORTE ÉCRITE (`services.escorte.offre`) à TROIS protégés, dont
# deux paladins qui SAVENT SE DÉFENDRE (`se_defend` + `equipement` : plates complètes et épée
# longue d'ordre) — ils frappent l'ennemi au contact sans jamais se déplacer.
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

DUMP = "jsons/telluris-dump-20260912-063741.json"
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
					   "Notre-Dame pour étudier le sceau des cryptes. Elle ne sait pas se battre.",
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
OFFRE = {
	"id": QUETE,
	"titre": "Le convoi de Lutecia",
	"description": "Dame Éléonore de Rochefort conduit la dernière livraison de cristaux de mana "
				   "d'Auxerre jusqu'aux cryptes de Notre-Dame, à Lutecia. Aélis de Montfaucon "
				   "voyage avec le convoi. Les deux paladins savent se défendre ; l'architecte, "
				   "non. Amenez-les tous les trois vivants sous la nef de Notre-Dame.",
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
					 "ne livrons pas à un entrepôt de la capitale : nous descendons aux cryptes de "
					 "Notre-Dame. » Elle voit la question venir et la devance. « Oui, Notre-Dame a un "
					 "portail. C'est pour cela que l'ordre l'a scellé, et c'est pour cela que le sceau "
					 "réclame des cristaux purs : ceux-ci iront nourrir ce qui tient la porte fermée. "
					 "La demoiselle veut voir comment il a été bâti ; elle dit que personne ne l'a "
					 "jamais mesuré. » Un temps. « {xp} points d'expérience et {prime} pièces de "
					 "cuivre à l'arrivée. Frère Martin et moi tiendrons nos lames si l'on vient nous "
					 "chercher. La demoiselle, non. Ne la laissez jamais seule. »",
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
					 "de plus : la vôtre. » Il compte sur ses doigts. « Destination : les cryptes de "
					 "Notre-Dame. Ne faites pas cette tête, {prenom} — le portail est fermé depuis "
					 "longtemps, et c'est justement pour qu'il le reste qu'on lui porte ces cristaux. » "
					 "Il tapote la garde de son épée. « Dame Éléonore et moi, nous nous défendrons si "
					 "l'on vient nous chercher au contact. Nous ne courrons après personne : sur une "
					 "route, celui qui court après une bête laisse les caisses derrière lui. La "
					 "demoiselle, elle, ne sait tenir qu'un carnet. {xp} points d'expérience et "
					 "{prime} pièces de cuivre au bout, si vous nous amenez tous les trois sous la nef. »",
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

def eleonore_lutecia():
	return {
		"_id": ELEONORE_LUTECIA,
		"type": "pnj",
		"nom": "Dame Éléonore de Rochefort",
		"race": "elfe",
		"vocation": "paladin",
		"portrait": PORTRAIT_ELEONORE,
		"description": "Paladine, commandante des convois de cristaux d'Auxerre. En garde à "
					   "Notre-Dame de Lutecia depuis l'arrivée du dernier convoi, jusqu'à nouvel ordre.",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Sous la nef, la lumière tombe en colonnes grises sur les dalles. Dame "
							 "Éléonore se tient près de l'escalier des cryptes, le registre ouvert, et "
							 "fait descendre une dernière caisse sous le regard d'un templier. Elle vous "
							 "reconnaît avant que vous ayez fait trois pas. « {prenom}. Les sept sont en "
							 "bas, scellées, comptées deux fois — Frère Martin y a veillé. » Elle "
							 "referme le registre. « L'ordre nous garde ici jusqu'à nouvel ordre. »",
					"choix": [
						{"id": "sceau", "label": "« Pourquoi porter à un portail ce qui appelle ? »",
						 "next": "sceau"},
						{"id": "aelis", "label": "« Et mademoiselle de Montfaucon ? »", "next": "aelis"},
						fin("« Je vous laisse à la garde du sceau. »"),
					],
				},
				"sceau": {
					"texte": "« Parce qu'un sceau s'use. » Elle désigne l'escalier. « Les cristaux ne "
							 "l'ouvrent pas : ils le nourrissent. Sous la prière, ils se taisent, et ce "
							 "qui se tait sous cette nef tient la porte fermée. » Un temps. « À Auxerre, "
							 "on les cache. Ici, on les emploie. C'est toute la différence entre un "
							 "coffre et un rempart. »",
					"choix": [
						{"id": "aelis", "label": "« Et la demoiselle, dans tout cela ? »", "next": "aelis"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"aelis": {
					"texte": "« Le chapitre lui a accordé les cryptes. » L'ombre d'un sourire. « Elle "
							 "a mesuré le premier pilier du sceau avant même d'avoir retiré son manteau. "
							 "Elle dit que les bâtisseurs de Notre-Dame savaient ce qu'ils faisaient, et "
							 "qu'ils ne l'ont écrit nulle part. Je crois qu'elle compte réparer cet oubli. »",
					"choix": [
						{"id": "sceau", "label": "« Et ce sceau, justement ? »", "next": "sceau"},
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
		"description": "Paladin hobbit, second de Dame Éléonore. Il tient à Notre-Dame le registre "
					   "des caisses du dernier convoi d'Auxerre, jusqu'à nouvel ordre.",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Assis sur la dernière marche de l'escalier des cryptes, Frère Martin "
							 "compare une empreinte de cire à celle qu'il a relevée à Auxerre, puis la "
							 "range dans son carnet avec un soin de relique. « Sept. » Il lève le nez. "
							 "« Sept parties, sept arrivées, sept intactes, et pas un essieu de cassé "
							 "entre l'Yonne et la Seine. J'ai failli ne pas le croire. Asseyez-vous, "
							 "{prenom} — pas sur la craie. »",
					"choix": [
						{"id": "route", "label": "« Que retenez-vous de la route ? »", "next": "route"},
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
				"ordre": {
					"texte": "« Jusqu'à nouvel ordre, nous restons sous cette nef. » Il hausse les "
							 "épaules. « Dame Éléonore tient le registre du sceau, je tiens celui des "
							 "caisses, et le chapitre tient les deux. Quand Auxerre aura une autre "
							 "livraison, on nous le fera savoir — tard, comme d'habitude. »",
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
	"""Les deux paladins APRÈS la réussite, placés AVANT le templier — sans quoi ils ne seraient
	jamais tirés (le templier n'a pas de `probabilite`, donc 1). ⚠️ Prix assumé : après le convoi,
	le templier n'est plus là que dans ~56 % des visites."""
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
			"description": "Une paladine en haubert clair, près de l'escalier des cryptes.",
		},
		{
			"character": MARTIN_LUTECIA,
			"nom": "Frère Martin de Clairvaux",
			"portrait": PORTRAIT_MARTIN,
			"probabilite": 0.25,
			"conditions": copy.deepcopy(CONVOI_ARRIVE),
			"description": "Un paladin hobbit assis sur les marches, un carnet de sceaux sur les genoux.",
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
