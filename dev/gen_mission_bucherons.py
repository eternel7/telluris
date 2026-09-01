# dev/gen_mission_bucherons.py
# Mission scénarisée « Retrouver les bûcherons d'Auxerre » → jsons/mission_bucherons_a_importer.json
#
# ⚠️ Idempotent PARCE QU'IL RELIT LE DUMP (source unique) : `admin_import_bulk` fait un PUT
# COMPLET, jamais un merge — éditer un champ oblige à reproduire tout le doc. Les docs déjà
# en base (Gautier, Borin, les trois lieux de la grotte, la battle map, le Bastion) sont donc
# recopiés à l'identique et seuls les champs AJOUTÉS y sont injectés. Une retouche faite à la
# main en base survit tant qu'on régénère depuis un dump à jour.
#
# La mission est une quête d'ESCORTE ÉCRITE (`services.escorte.offre`) — la seule famille du
# moteur dont la réussite dépend de ce que le joueur EMPÊCHE, et la seule qui accepte
# nativement PLUSIEURS `proteges`. Rien n'est inventé :
#   · l'offre est posée à l'entrée du bureau (`poser_escorte_offerte`), réservée au rang D
#     (`rang_min`, même vocabulaire que la barrière de lieu) et `unique` ;
#   · le rendez-vous (`rencontre.lieu`) fait naître les quatre `protege:*` à l'entrée de la
#     grotte — ils suivent alors le groupe, ciblables en combat, et leur mort fait échouer la
#     quête (`ESCORTE_MORT_DEFINITIVE`) ;
#   · la dépose se solde toute seule en franchissant la porte du bureau
#     (`escorte.traiter_deplacement`) : XP, prime, objet et +1 de réputation chez le donneur ;
#   · le combat des trois loups géants est une SALLE DE DONJON (`categorie: battle_map` gardée
#     par un bloc `acces`) : franchir la porte OUVRE LE COMBAT (`_declencher_combat_donjon`,
#     `nb_monstres = 3` pour un joueur seul, pool d'espèces curaté).

import json
import os

DUMP = "jsons/telluris-dump-20260901-205218.json"
SORTIE = "jsons/mission_bucherons_a_importer.json"
# Sortie CIBLÉE : les deux paladins seuls, pour réimporter le seul morceau qui bouge sans
# repasser les quatorze autres docs. Bâtie par les MÊMES fonctions que le bundle complet —
# les deux fichiers ne peuvent donc pas diverger.
SORTIE_PALADINS = "jsons/paladins_cathedrale_a_importer.json"
# Sortie CIBLÉE : le correctif des abords de la grotte — les deux connexions de la clairière
# (libellés remis dans le bon sens), les trois lieux gardés et Armand. Mêmes fonctions que le
# bundle, donc aucune divergence possible.
SORTIE_GROTTE = "jsons/correctif_grotte_a_importer.json"

QUETE = "quete:escorte_bucherons_d_auxerre"
CITE = "lieu:auxerre"
BUREAU = "lieu:bureau_du_maitre_de_guilde_d_auxerre"
COMPTOIR = "lieu:le_bastion_de_l_yonne_comptoir"
GROTTE = "lieu:grotte_dans_foret_humide"
GROTTE_IN = "lieu:grotte_dans_foret_humide_interieur01"
GROTTE_VIDE = "lieu:grotte_dans_foret_humide_interieur"
CLAIRIERE = "lieu:clairiere_de_la_grotte_liberee"
BATAILLE = "lieu:grotte_en_foret"
DONJON = "donjon:les_loups_de_la_grotte_humide"

# La barrière qui commande TOUT le décor de la mission : la grotte habitée, la clairière
# dégagée et la salle de combat n'existent que le temps de la quête (la grotte VIDE,
# `..._interieur`, reste ouverte le reste du temps). ⚠️ Recopiée telle quelle aux trois
# endroits — un filtre qui divergerait ouvrirait l'un des trois hors mission.
_FILTRE_QUETE = {
	"types": ["escorte"],
	"cible": BUREAU,
	"giver_categorie": "bureau_maitre_guilde",
}
CONDITION_QUETE = [{"quete_active": dict(_FILTRE_QUETE)}]
# La NÉGATION : « tant que la mission n'est pas en cours ». C'est elle qui fait disparaître la
# grotte VIDE le temps de la quête — sans quoi deux boutons « Penetrer dans la grotte »
# cohabitent et le joueur entre dans la mauvaise, où il ne trouve personne.
CONDITION_HORS_QUETE = [{"quete_active": dict(_FILTRE_QUETE, attendu=False)}]
# La victoire sur les trois loups. `attendu: False` = « tant qu'ils tiennent le seuil ».
CONDITION_LOUPS_ABATTUS = {"combat_gagne": {"lieu": BATAILLE}}
CONDITION_LOUPS_DEBOUT = {"combat_gagne": {"lieu": BATAILLE, "attendu": False}}
# La clairière est un PASSAGE UNIQUE : elle s'efface derrière celui qui l'a traversée.
# `lieux_visites` est écrit par le déplaceur à la première arrivée — on ne mémorise rien de
# neuf, on lit une trace qui existait déjà.
CONDITION_CLAIRIERE_NEUVE = {"lieu_visite": {"lieu": CLAIRIERE, "attendu": False}}


def charger():
	with open(DUMP, encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"] if d.get("_id")}


def nu(doc):
	"""Doc du dump sans son `_rev` : il est de toute façon réattaché depuis la base."""
	return {k: v for k, v in doc.items() if k != "_rev"}


def fin(label="Je m'en vais."):
	return {"id": "fin", "label": label, "next": "fin"}


# ---------------------------------------------------------------------------
# Ouvrir le combat des loups depuis N'IMPORTE QUEL PNJ de la grotte
# ---------------------------------------------------------------------------
# ⚠️ `services.acces` est porté par le PNJ, pas par le lieu, et `_resoudre_acces` ne lit le
# lieu gardé QUE sur le doc du PNJ à qui l'on parle : aucune contrainte sur la position du
# joueur. Les trois réfugiés peuvent donc ouvrir la même porte qu'Armand, chacun à sa façon —
# le joueur n'a plus à ressortir et à retrouver le bon interlocuteur pour en finir.
#
# ⚠️ CHAQUE PNJ doit porter SES PROPRES nœuds `ouvre` et `refus` (le linter les exige, et le
# router va les chercher dans le doc de celui qui parle) : le service ne se partage pas, seul
# le lieu gardé est commun.
# ⚠️ Pas de nœud `deja` : le lieu gardé est une `battle_map`, aucun laissez-passer n'y est
# jamais posé — la branche est structurellement inatteignable.
# ⚠️ Le choix qui déclenche DOIT être conditionné par `acces_ouvrable` (`ACTIONS_A_CONDITIONNER`
# du linter) : sinon il s'afficherait aussi quand il n'y a plus rien à affronter.
#
# Effet de bord recherché : déclarer le service donne AUSSI à ces trois-là les flags
# `acces_libere` / `acces_menace`, que `donjon_purge` sait maintenant dériver d'une victoire.
# Ils peuvent donc réagir APRÈS la bataille — sans le service, ils n'ont aucun flag et
# resteraient à parler de loups déjà morts.

SERVICE_LOUPS = {
	"acces": {
		"lieu": BATAILLE,
		"noeuds": {"ouvre": "loups_charge", "refus": "loups_absents"},
	}
}


# ⚠️ Les trois occupants de l'INTÉRIEUR conduisent au SEUIL (`deplacer: GROTTE`) et pas à la
# clairière : `_lien_vers` cherche une connexion depuis le lieu COURANT, et il n'en existe
# aucune entre la grotte habitée et la clairière. Un `deplacer` sans lien est SILENCIEUX — le
# choix paraîtrait cassé. C'est Armand, au seuil, qui mène ensuite à la clairière.

def choix_loups(label_charger, label_apres):
	"""Les deux choix d'accueil que tout occupant de la grotte partage : en finir, et en
	parler une fois que c'est fait. Conditions complémentaires — jamais les deux à la fois."""
	return [
		{
			"id": "charger",
			"label": label_charger,
			"condition": {"acces_ouvrable": True},
			"action": {"service": "acces", "op": "passer"},
		},
		{
			"id": "apres",
			"label": label_apres,
			"condition": {"acces_libere": True},
			"next": "apres_les_loups",
		},
	]


# ---------------------------------------------------------------------------
# Les quatre personnes à ramener — specs de `services.escorte.offre.proteges`
# ---------------------------------------------------------------------------
# ⚠️ Le portrait d'un `protege:*` est servi par le mount /characters (`_protege_view`
# n'expose aucun `image_base`), là où le `portrait` d'un doc `pnj:*` vient de /pnj : les
# mêmes fichiers sont donc copiés dans les deux dossiers, sous le MÊME nom.
# ⚠️ Aucune clé `caracteristiques` : `creer_protege` retombe sur les stats de BASE de la race
# (`rules:races`), c'est-à-dire aucun point dépensé — ce sont des civils, pas des aventuriers.

PROTEGES = [
	{
		"prenom": "Armand", "nom": "Renaud", "race": "humain", "sex": "M",
		"image": "bucheron_Armand_Renaud_humain_m.jpg",
		"description": "Chef de fait des trois bûcherons d'Auxerre. Vingt ans de coupe dans les "
					   "futaies du nord, et la voix qu'on écoute quand la forêt se tait.",
	},
	{
		"prenom": "Étienne", "nom": "Morel", "race": "nain", "sex": "M",
		"image": "bucheron_Étienne_Morel_nain_m.jpg",
		"description": "Bûcheron nain, la jambe ouverte pendant la fuite. Il marche encore, mais "
					   "il ne courra pas deux fois.",
	},
	{
		"prenom": "Matthieu", "nom": "Perrin", "race": "ogre", "sex": "M",
		"image": "bucheron_Matthieu_Perrin_ogre_m.jpg",
		"description": "Bûcheron ogre. C'est lui qui connaissait la grotte, et lui qui y a poussé "
					   "les autres quand les crocs sont sortis des fougères.",
	},
	{
		"prenom": "Aélis", "nom": "de Montfaucon", "race": "humain", "sex": "F",
		"image": "architecte_Aélis_de_Montfaucon_humain_f03.jpg",
		"description": "Jeune architecte, chercheuse en cristaux de mana. Elle voyageait vers "
					   "Auxerre sous escorte paladine ; il ne lui reste que son carnet et son "
					   "obstination.",
	},
]


# ---------------------------------------------------------------------------
# 1. Armand Renaud — la voix derrière l'éboulis, et le gardien du combat
# ---------------------------------------------------------------------------
# ⚠️ Son `services.acces` vise une salle de `categorie: battle_map` : franchir la porte
# n'ouvre AUCUN laissez-passer, elle ouvre le COMBAT. `noeuds.deja` y est donc
# structurellement inatteignable — ne pas l'écrire.
# ⚠️ Ce qui referme la porte après la victoire, c'est la condition `combat_gagne` de la salle,
# PAS un délai de dialogue : une escorte ne fait jamais monter `progress`, donc
# `objectif_atteint: false` — le filtre qui ferme la boucle d'un donjon commissionné — n'a
# aucune prise ici. Le `delai_min` de 30 min qui tenait ce rôle a été retiré : il ne faisait
# qu'espacer les répétitions, et son `noeud_attente` rendait Armand muet pendant une demi-heure.
# ⚠️ Ses trois branches d'accueil couvrent les trois états du seuil, et sont EXCLUSIVES :
#   · `acces_ouvrable`            → les loups tiennent le seuil, on peut charger ;
#   · `acces_refuse` + `acces_menace` → hors mission : la grotte est muette ;
#   · `acces_libere`              → les loups sont abattus (`donjon_purge` lit la victoire).
# Sans le `acces_menace` sur la deuxième, Armand réciterait « vous n'entendez que l'eau qui
# suinte » APRÈS la bataille : la porte fermée rend `acces_refuse` vrai de nouveau.

def pnj_armand():
	return {
		"_id": "pnj:armand_renaud",
		"type": "pnj",
		"nom": "Armand Renaud",
		"race": "humain",
		"vocation": "forestier",
		"portrait": "bucheron_Armand_Renaud_humain_m.jpg",
		"description": "Bûcheron d'Auxerre, chef de fait de l'équipe partie couper au nord "
					   "de la cité. Une voix rauque, une hache ébréchée, et deux nuits sans "
					   "dormir derrière un éboulis.",
		"services": {
			"acces": {
				"lieu": BATAILLE,
				"noeuds": {"ouvre": "loups_charge", "refus": "grotte_silencieuse"},
			}
		},
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "L'entrée de la grotte n'est qu'une fente noire entre deux dalles de "
							 "roche, à demi mangée par les fougères. Quelque chose remue "
							 "là-dedans. Puis une voix d'homme, basse, râpée par la soif : "
							 "« Ne bougez plus. Ne bougez surtout plus. »",
					"choix": [
						{
							"id": "parler",
							"label": "« Qui êtes-vous ? Je viens de la Guilde d'Auxerre. »",
							"condition": {"acces_ouvrable": True},
							"next": "presentation",
						},
						{
							"id": "sortis",
							"label": "« C'est fini. Sortez de là. »",
							"condition": {"acces_libere": True},
							"next": "apres_les_loups",
						},
						{
							"id": "ecouter",
							"label": "Tendre l'oreille vers la fente.",
							"condition": {"acces_refuse": True, "acces_menace": True},
							"next": "grotte_silencieuse",
						},
						fin("Reculer sans un bruit."),
					],
				},
				"presentation": {
					"texte": "Un raclement de pierre, et un visage apparaît dans l'ombre — barbu, "
							 "creusé, les yeux rouges de fumée. « D'Auxerre… » Il ferme un instant "
							 "les paupières. « Par les anciens chemins. Armand Renaud, bûcheron. "
							 "Nous sommes trois là-dedans. Trois, et la demoiselle. » Sa main se "
							 "crispe sur un manche de hache qu'il ne lâche visiblement plus depuis "
							 "deux jours. « Ne restez pas planté là, {prenom}. Elles vous ont déjà "
							 "senti. »",
					"choix": [
						{"id": "recit", "label": "« Que s'est-il passé ? »", "next": "recit"},
						{"id": "demoiselle", "label": "« Quelle demoiselle ? »", "next": "aelis_evoquee"},
						{"id": "loups", "label": "« Qui, elles ? »", "next": "les_loups"},
					],
				},
				"recit": {
					"texte": "« On coupait du charme, à trois cents pas d'ici. Un chantier propre, "
							 "du bois marqué, rien qui appelle les ennuis. » Il crache de la "
							 "poussière. « Elles sont sorties des fougères sans un aboiement. "
							 "Trois. Grosses comme des veaux. Matthieu connaissait ce trou dans la "
							 "roche — c'est lui qui nous y a poussés, et il a bien fait : "
							 "l'ouverture est trop étroite pour elles. » Un silence. « Nos outils "
							 "sont restés là-bas. Étienne a la jambe ouverte. Et voilà deux nuits "
							 "qu'on écoute respirer des bêtes qui ne partent pas. »",
					"choix": [
						{"id": "demoiselle", "label": "« Et la demoiselle ? »", "next": "aelis_evoquee"},
						{"id": "loups", "label": "« Elles sont toujours dehors ? »", "next": "les_loups"},
						{"id": "retour", "label": "« Tenez bon. »", "next": "accueil"},
					],
				},
				"aelis_evoquee": {
					"texte": "« Elle est arrivée sur notre chantier la veille, seule, la robe en "
							 "loques et un carnet serré contre elle comme un enfant. » Armand "
							 "baisse la voix. « Elle voyageait avec deux hommes en armes — des "
							 "paladins, à ce qu'elle dit. Elle est la seule des trois à être encore "
							 "debout. Nous n'allions pas la laisser dans ce bois. » Il hausse une "
							 "épaule. « On l'a prise avec nous. Une heure après, les bêtes étaient "
							 "sur nous. Faites-en ce que vous voudrez : moi, je n'ai pas d'avis. »",
					"choix": [
						{"id": "recit", "label": "« Reprenons depuis le début. »", "next": "recit"},
						{"id": "loups", "label": "« Parlez-moi de ces bêtes. »", "next": "les_loups"},
						{"id": "retour", "label": "« J'entrerai la voir. »", "next": "accueil"},
					],
				},
				"les_loups": {
					"texte": "« Des loups géants. Trois, toujours les trois mêmes. » Sa voix "
							 "descend encore d'un ton. « Elles ne s'éloignent jamais de plus de "
							 "trente pas de la fente. Elles ne hurlent pas, elles ne creusent pas : "
							 "elles attendent. C'est ce qui est le pire. Une bête qui attend, ça "
							 "sait compter. » Le raclement d'une griffe sur la pierre, quelque part "
							 "derrière vous. « Tant qu'elles tiennent ce seuil, personne ne sort "
							 "d'ici vivant. Ni nous. Ni vous, si vous restez à découvert. »",
					"choix": [
						{
							"id": "charger",
							"label": "« Alors elles ne le tiendront plus. » — Dégainer.",
							"condition": {"acces_ouvrable": True},
							"action": {"service": "acces", "op": "passer"},
						},
						{"id": "attendre", "label": "« Restez à l'abri. Je reviens. »", "next": "accueil"},
						fin("S'écarter du seuil."),
					],
				},
				"loups_charge": {
					"texte": "Vous vous écartez de l'éboulis et les fougères s'ouvrent d'un coup. "
							 "Trois masses grises se lèvent du couvert, l'échine hérissée, et le "
							 "grondement qui monte de la clairière n'a plus rien d'un "
							 "avertissement. Derrière vous, la voix d'Armand, dans la pierre : "
							 "« Que les anciens chemins vous portent, {prenom} ! »",
					"choix": [fin("Faire face.")],
				},
				"grotte_silencieuse": {
					"texte": "Vous approchez l'oreille de la fente. Rien — l'eau qui suinte, l'écho "
							 "d'une goutte quelque part très bas, et le froid de la roche sur votre "
							 "joue. Si quelqu'un s'est abrité là, ce n'était pas aujourd'hui.",
					"choix": [fin("Se relever.")],
				},
				"apres_les_loups": {
					"texte": "Le vacarme est retombé sur la clairière. Armand écarte la dalle du "
							 "seuil et sort en clignant des yeux, la hache pendante au bout du "
							 "bras, incapable pour l'instant de dire autre chose que : « … Voilà. "
							 "Voilà. » Derrière lui, on entend les autres bouger dans l'ombre, et "
							 "une voix de femme qui répète qu'il ne faut pas oublier le carnet, "
							 "surtout pas le carnet.",
					"choix": [
						{"id": "route", "label": "« Debout. On rentre à Auxerre. »", "next": "route"},
						fin("Leur laisser un instant."),
					],
				},
				"route": {
					"texte": "« À Auxerre. » Armand répète le mot comme s'il en vérifiait le poids. "
							 "« Étienne ne tiendra pas un long détour, alors nous prendrons la "
							 "clairière et la route basse. » Il jette un regard aux fougères "
							 "écrasées, puis à vous. « Menez, {prenom}. Nous vous suivons — et "
							 "cette fois, nous ne nous arrêterons pas pour couper du bois. »",
					# ⚠️ Le hook `deplacer` ne DÉPLACE PAS ici : il rend au client le `link_id`,
					# qui rappelle `moveTo` — donc l'unique déplaceur, avec ses quinze effets de
					# bord et sa garde 403. Il ne peut pas forcer une porte fermée : clairière
					# non ouverte ⇒ `_lien_vers` rend None et le champ est simplement omis.
					# ⚠️ Sur ARMAND seul : `_lien_vers` cherche une connexion depuis le lieu
					# COURANT, et seul le seuil en a une vers la clairière.
					"choix": [
						{"id": "fin", "label": "Prendre la tête.", "next": "fin",
						 "deplacer": CLAIRIERE},
					],
				},
			},
		},
	}


# ---------------------------------------------------------------------------
# 2. Étienne Morel — le blessé
# ---------------------------------------------------------------------------

def pnj_etienne():
	return {
		"_id": "pnj:etienne_morel",
		"type": "pnj",
		"nom": "Étienne Morel",
		"race": "nain",
		"vocation": "forestier",
		"portrait": "bucheron_Étienne_Morel_nain_m.jpg",
		"description": "Bûcheron nain d'Auxerre, la jambe ouverte depuis la fuite. Il tient le feu "
					   "de la grotte parce que c'est la seule chose qu'il puisse encore tenir.",
		"services": SERVICE_LOUPS,
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "Assis contre la paroi, le nain nourrit un feu maigre de brindilles "
							 "comptées une à une. Sa jambe est serrée dans une manche de chemise "
							 "nouée trop haut. « Ne me demandez pas de me lever, l'ami. Je me "
							 "lèverai quand il faudra marcher, et pas une heure avant. »",
					"choix": [
						{"id": "blessure", "label": "« Montrez-moi cette jambe. »", "next": "blessure"},
						{"id": "fuite", "label": "« Comment êtes-vous arrivés jusqu'ici ? »", "next": "fuite"},
						{"id": "feu", "label": "« Vous gardez ce feu depuis deux nuits ? »", "next": "feu"},
						*choix_loups("« Gardez ce feu. Je vais chasser les loups. »",
									 "« Vous pouvez vous lever, maintenant. »"),
						fin("« Reposez-vous. »"),
					],
				},
				"loups_charge": {
					"texte": "Le nain lâche ses brindilles. « Attendez — » Il essaie de se "
							 "redresser, retombe, et jure entre ses dents. « Trois. Elles ne "
							 "chargent jamais ensemble, c'est leur seule faute : il y en a toujours "
							 "une qui reste en arrière à vous regarder. C'est celle-là qu'il faut "
							 "prendre en premier. » Il vous saisit le poignet. « Je ne peux pas "
							 "vous suivre. Je ne peux même pas vous regarder faire. »",
					"choix": [fin("Sortir.")],
				},
				"loups_absents": {
					"texte": "« Chasser quoi ? » Le nain remue une braise sans lever les yeux. "
							 "« Il n'y a plus rien dehors qui vaille qu'on se lève. Et croyez-moi, "
							 "je suis le premier à le vérifier. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"apres_les_loups": {
					"texte": "Il a déjà défait le garrot pour le renouer plus bas, proprement. "
							 "« Deux nuits à compter des brindilles. » Il éteint le feu d'un revers "
							 "de botte, ce qui lui arrache une grimace. « Je marcherai. Lentement, "
							 "et en jurant beaucoup, mais je marcherai jusqu'à Auxerre. »",
					"choix": [
						{"id": "retour", "label": "« Prenez votre temps. »", "next": "accueil"},
						{"id": "fin", "label": "« Alors en route. »", "next": "fin", "deplacer": GROTTE},
					],
				},
				"blessure": {
					"texte": "Il écarte le tissu sans un mot. Quatre entailles parallèles, propres, "
							 "profondes, déjà mauvaises sur les bords. « La deuxième bête m'a eu au "
							 "moment où je passais la fente. Un demi-pas de plus et elle m'avait la "
							 "hanche. » Il rabat la manche. « Je ne me plains pas : Matthieu m'a "
							 "tiré dedans par le col comme un sac de son. »",
					"choix": [
						{"id": "fuite", "label": "« Et les autres ? »", "next": "fuite"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"fuite": {
					"texte": "« On courait mal. On courait avec des haches, ce qui est la meilleure "
							 "façon de courir lentement. » Il remue une braise. « Armand a fait "
							 "passer la demoiselle d'abord, puis moi, puis Matthieu s'est mis en "
							 "travers du trou avec un tronçon de charme jusqu'à ce qu'elles "
							 "renoncent à y enfoncer la gueule. » Un silence. « Elles n'ont pas "
							 "renoncé au reste. »",
					"choix": [
						{"id": "feu", "label": "« Et depuis ? »", "next": "feu"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"feu": {
					"texte": "« Deux nuits. » Il montre du menton un tas de brindilles ridicule. "
							 "« Il y a de l'eau au fond, c'est toujours ça. Pour le bois, nous "
							 "sommes trois bûcherons enfermés dans une caverne de pierre — riez, "
							 "allez. La demoiselle a ri aussi. C'est même la seule fois. »",
					"choix": [
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
						fin("« Tenez bon. »"),
					],
				},
			},
		},
	}


# ---------------------------------------------------------------------------
# 3. Matthieu Perrin — celui qui connaissait la grotte
# ---------------------------------------------------------------------------

def pnj_matthieu():
	return {
		"_id": "pnj:matthieu_perrin",
		"type": "pnj",
		"nom": "Matthieu Perrin",
		"race": "ogre",
		"vocation": "forestier",
		"portrait": "bucheron_Matthieu_Perrin_ogre_m.jpg",
		"description": "Bûcheron ogre d'Auxerre. Il connaît les creux de roche du nord mieux "
					   "que les chemins, et c'est ce qui a sauvé trois vies.",
		"services": SERVICE_LOUPS,
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"loups_charge": {
					"texte": "L'ogre se lève, et le boyau paraît soudain deux fois plus étroit. "
							 "« Enfin. » Il pèse son tronçon de charme, hésite, puis vous le tend "
							 "des deux mains comme on passe un flambeau. « Prenez ça. Moi je reste "
							 "au seuil : si l'une d'elles vous contourne, elle voudra entrer, et "
							 "il faudra bien que quelqu'un soit assis là. » Un grondement bas. "
							 "« Ne les laissez pas vous séparer de la fente. »",
					"choix": [fin("Sortir.")],
				},
				"loups_absents": {
					"texte": "L'ogre ne bouge pas d'un pouce. « Il n'y a rien à charger. Écoutez "
							 "donc : plus un souffle, plus une griffe sur la pierre. Ce silence-là, "
							 "je le connais — c'est celui d'avant. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"apres_les_loups": {
					"texte": "Pour la première fois en deux jours, l'ogre a tourné le dos à "
							 "l'entrée. Le tronçon de charme est posé en travers de ses genoux, "
							 "inutile. « Vous pouvez vous asseoir, maintenant », dit-il, et il "
							 "faut un moment pour comprendre qu'il se parle à lui-même. Puis, en "
							 "vous regardant : « Elles ont attendu deux nuits. Vous, une heure. »",
					"choix": [
						{"id": "retour", "label": "« Levez-vous. On rentre. »", "next": "accueil"},
						{"id": "fin", "label": "« Dehors. Tout de suite. »", "next": "fin", "deplacer": GROTTE},
					],
				},
				"accueil": {
					"texte": "L'ogre occupe à lui seul la moitié du boyau. Il est assis face à "
							 "l'entrée, dos à ses compagnons, un tronçon de charme en travers des "
							 "genoux — la place de celui qui a décidé que rien ne passerait. Il "
							 "vous jauge longuement. « Vous sentez le dehors. C'est bien. »",
					"choix": [
						{"id": "grotte", "label": "« Comment connaissiez-vous ce trou ? »", "next": "grotte"},
						{"id": "seuil", "label": "« Vous montez la garde depuis deux jours ? »", "next": "seuil"},
						{"id": "sortie", "label": "« Y a-t-il une autre sortie ? »", "next": "sortie"},
						*choix_loups("« Tenez le seuil. Je m'occupe d'elles. »",
									 "« Vous pouvez poser ce tronçon. »"),
						fin("« Gardez le seuil. »"),
					],
				},
				"grotte": {
					"texte": "« Je ramasse la pierre autant que le bois. Les creux de roche du "
							 "nord, je les ai tous ouverts un jour ou l'autre. » Il tapote la "
							 "paroi d'un doigt large comme un manche. « Celui-ci, je l'avais noté "
							 "parce que la fente est étroite et la salle grande. Un bon abri de "
							 "pluie. » Un grondement bref, qui pourrait être un rire. « Il s'avère "
							 "que c'est aussi un bon abri de crocs. »",
					"choix": [
						{"id": "seuil", "label": "« Et vous tenez le seuil. »", "next": "seuil"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"seuil": {
					"texte": "« Quelqu'un doit être assis là. » Il ne bouge pas d'un pouce. « Elles "
							 "ne peuvent pas entrer, c'est vrai. Mais un museau passe. Un museau, "
							 "ça suffit pour prendre une jambe, et Étienne n'a plus de jambe à "
							 "donner. » Il soulève à peine le tronçon de charme. « Alors je suis "
							 "assis là. Je serai assis là jusqu'à ce que quelqu'un me dise que je "
							 "peux me lever. »",
					"choix": [
						{"id": "sortie", "label": "« Bientôt. »", "next": "sortie"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"sortie": {
					"texte": "« Non. » L'ogre secoue lentement la tête. « J'ai cherché, la première "
							 "nuit, avec une torche. Ça descend, ça se resserre, et ça s'arrête sur "
							 "de l'eau noire. » Il fixe l'ouverture éclairée. « Il n'y a qu'une "
							 "porte à cette maison, et il y a trois loups dessus. C'est simple. "
							 "C'est ce qui est terrible. »",
					"choix": [
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
						fin("« Je m'en occupe. »"),
					],
				},
			},
		},
	}


# ---------------------------------------------------------------------------
# 4. Aélis de Montfaucon — la révélation, son histoire, les cristaux
# ---------------------------------------------------------------------------

def pnj_aelis():
	return {
		"_id": "pnj:aelis_de_montfaucon",
		"type": "pnj",
		"nom": "Aélis de Montfaucon",
		"race": "humain",
		"vocation": "lettre",
		"portrait": "architecte_Aélis_de_Montfaucon_humain_f03.jpg",
		"description": "Jeune architecte et chercheuse, spécialiste des cristaux de mana et de "
					   "leur emploi dans la structure des bâtiments. Elle devait rejoindre Auxerre "
					   "pour y étudier les cristaux de la cité ; elle n'y est jamais arrivée.",
		"services": SERVICE_LOUPS,
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"loups_charge": {
					"texte": "Elle referme son carnet d'un coup sec et se lève, très pâle. « Alors "
							 "écoutez-moi d'abord, parce que c'est la seule chose utile que je "
							 "puisse vous donner. » Elle parle vite, sans trembler. « Je les "
							 "observe depuis deux jours et je note leurs allées et venues. Elles "
							 "tournent par la gauche — toujours par la gauche, sans exception, "
							 "même quand le terrain s'y prête mal. Et elles ne dépassent jamais "
							 "les grands hêtres : au-delà, elles reviennent. » Un souffle. "
							 "« Voilà. Je n'ai que ça. »",
					"choix": [fin("Sortir.")],
				},
				"loups_absents": {
					"texte": "« Il n'y a plus rien à charger. » Elle a rouvert son carnet, et sa "
							 "main est redevenue sûre. « J'ai compté trois carcasses et vérifié "
							 "deux fois. Je crois que je vais dormir, pour changer. »",
					"choix": [{"id": "retour", "label": "Revenir.", "next": "accueil"}],
				},
				"apres_les_loups": {
					"texte": "Elle est déjà à l'entrée, penchée sur la roche, à mesurer du pouce "
							 "l'écartement de la fente comme si la question restait d'actualité. "
							 "« Onze pouces. J'avais raison. » Puis elle se redresse et vous "
							 "regarde enfin. « Excusez-moi. C'est ce que je fais quand je ne sais "
							 "pas quoi dire. » Elle serre le carnet contre elle. « Merci. Je vous "
							 "suis, et je ne me plaindrai pas de la marche. »",
					"choix": [
						{"id": "retour", "label": "« Rassemblez vos affaires. »", "next": "accueil"},
						{"id": "fin", "label": "« En route, alors. »", "next": "fin", "deplacer": GROTTE},
					],
				},
				"accueil": {
					"texte": "Un peu à l'écart du feu, une jeune femme est assise sur une dalle, "
							 "les genoux ramenés, un carnet épais serré contre elle. Ses vêtements "
							 "de voyage sont gris de poussière et déchirés à l'ourlet. Elle vous "
							 "regarde entrer sans crier, sans se lever — elle vous regarde comme on "
							 "vérifie un calcul. Puis quelque chose cède dans ses épaules. « Vous "
							 "n'êtes pas d'ici. Vous venez de la cité. »",
					"choix": [
						{"id": "nom", "label": "« Qui êtes-vous ? »", "next": "presentation"},
						{"id": "histoire", "label": "« Comment êtes-vous arrivée dans cette grotte ? »", "next": "voyage"},
						{"id": "carnet", "label": "« Ce carnet ne vous quitte pas. »", "next": "cristaux"},
						*choix_loups("« Restez au fond. Je sors les affronter. »",
									 "« Vous pouvez respirer : elles sont mortes. »"),
						fin("« Restez ici. Je reviens. »"),
					],
				},
				"presentation": {
					"texte": "Elle se lève enfin, et le fait proprement, comme on se présente dans "
							 "une salle de conseil et non au fond d'un trou. « Aélis de Montfaucon. "
							 "Architecte. » Une seconde d'hésitation. « On m'attend à Auxerre. On "
							 "m'y attendait, du moins — j'ai six jours de retard et je doute qu'on "
							 "m'attende encore. »",
					"choix": [
						{"id": "attendue", "label": "« On vous attend toujours. La Guilde vous cherche. »", "next": "attendue"},
						{"id": "histoire", "label": "« Que vous est-il arrivé ? »", "next": "voyage"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"attendue": {
					"texte": "Elle reste un instant sans rien dire, et il faut la regarder de près "
							 "pour voir sa mâchoire trembler une fois. « On me cherche. » Elle "
							 "rouvre les yeux, parfaitement calme. « Bien. Alors nous n'avons pas "
							 "perdu deux jours pour rien. Excusez-moi — je m'étais convaincue qu'il "
							 "ne fallait compter que sur nous. C'était plus simple à tenir. »",
					"choix": [
						{"id": "histoire", "label": "« Racontez-moi la route. »", "next": "voyage"},
						{"id": "carnet", "label": "« Pourquoi Auxerre ? »", "next": "cristaux"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"voyage": {
					"texte": "« Je ne voyageais pas seule. » Elle dit cela d'abord, avant tout le "
							 "reste, et elle y met du soin. « Deux paladins m'escortaient depuis la "
							 "vallée. Des gens sérieux. Ils ont vu les bêtes bien avant moi. » Ses "
							 "doigts se referment sur la couverture du carnet. « Ce n'était pas une "
							 "attaque. C'était une traque. Trois jours. Le premier est tombé au "
							 "gué ; le second la nuit suivante, en me disant de courir vers la "
							 "fumée d'un chantier. J'ai couru vers la fumée. C'étaient eux. » Elle "
							 "désigne les bûcherons d'un mouvement de tête. « Ils auraient pu me "
							 "renvoyer. Ils m'ont donné une capuche et un quignon de pain, et une "
							 "heure plus tard les loups nous tenaient tous. »",
					"choix": [
						{"id": "loups", "label": "« Et depuis, elles attendent dehors. »", "next": "les_loups"},
						{"id": "carnet", "label": "« Qu'est-ce qui vaut trois jours de traque ? »", "next": "cristaux"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"les_loups": {
					"texte": "« Elles attendent, oui. Et elles ont raison d'attendre. » Le ton est "
							 "presque professionnel. « Nous avons de l'eau et pas de vivres ; elles "
							 "ont la forêt entière. Le calcul ne joue pas pour nous : il leur "
							 "suffit de tenir. » Elle relève la tête. « J'ai mesuré la fente le "
							 "premier soir, faute de mieux. Onze pouces au plus étroit. C'est tout "
							 "ce qui nous sépare d'elles, et c'est tout ce qui nous garde ici. »",
					"choix": [
						{"id": "sortir", "label": "« Elles ne tiendront pas ce seuil longtemps. »", "next": "sortir"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"cristaux": {
					"texte": "« Des cristaux de mana. » Elle ouvre le carnet sur ses genoux et le "
							 "tourne vers vous sans hésiter, comme si le sujet la sortait "
							 "physiquement de la grotte. « Je ne les étudie pas comme une "
							 "magicienne : je les étudie comme une pierre de taille. Un cristal pur "
							 "ne se contente pas d'alimenter — il porte. On peut bâtir autour de "
							 "lui. »",
					"choix": [
						{"id": "plans", "label": "Regarder les plans.", "next": "plans"},
						{"id": "auxerre", "label": "« Et les cristaux d'Auxerre ? »", "next": "auxerre"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"plans": {
					"texte": "Des coupes de bâtiments, tracées d'une main nette : une salle voûtée "
							 "dont toutes les nervures convergent vers un fût de cristal planté au "
							 "centre ; une courtine dont les créneaux sont chaînés par une veine "
							 "lumineuse ; un pont sans pile centrale, avec une note en marge — "
							 "« tient si la charge reste sous le seuil de saturation ; à "
							 "vérifier ». « Des systèmes de protection, des adductions, des "
							 "ouvrages d'art », dit-elle. « Tout ce qu'on fait aujourd'hui avec "
							 "trois fois plus de pierre. »",
					"choix": [
						{"id": "auxerre", "label": "« Pourquoi venir jusqu'ici pour cela ? »", "next": "auxerre"},
						{"id": "retour", "label": "Refermer le carnet.", "next": "accueil"},
					],
				},
				"auxerre": {
					"texte": "« Parce que les vôtres sont différents. » Elle referme le carnet d'un "
							 "geste sec. « J'ai travaillé sur des cristaux de trois provinces. Ceux "
							 "d'Auxerre ont une pureté que je n'explique pas — et une pureté, en "
							 "architecture, cela ne veut pas dire joli : cela veut dire qu'on peut "
							 "leur demander de porter des structures beaucoup plus complexes. » Un "
							 "temps. « Je veux voir comment vos bâtisseurs les emploient. Et, avec "
							 "de la chance, comprendre comment améliorer leur rendement. »",
					"choix": [
						{"id": "sortir", "label": "« Vous les verrez. Nous partons d'ici. »", "next": "sortir"},
						{"id": "retour", "label": "Revenir.", "next": "accueil"},
					],
				},
				"sortir": {
					"texte": "« Vous allez sortir. » Ce n'est pas une question ; c'est une "
							 "conclusion, et elle a l'air de lui coûter. « Alors écoutez-moi une "
							 "fois, {prenom} : elles sont trois, elles ne fuient pas et elles ne se "
							 "fatiguent pas. Je ne sais pas me battre — je ne serai d'aucun secours "
							 "et je serai probablement dans le chemin. » Elle glisse le carnet "
							 "contre sa poitrine. « Mais si vous ouvrez ce seuil, nous vous "
							 "suivrons jusqu'à Auxerre, et je ne me plaindrai pas une seule fois de "
							 "la marche. »",
					"choix": [
						{"id": "retour", "label": "« Tenez-vous prête. »", "next": "accueil"},
						fin("Ressortir vers la lumière."),
					],
				},
			},
		},
	}


# ---------------------------------------------------------------------------
# 5. Gautier de Valcroix — le donneur (doc du dump + service escorte + nœuds)
# ---------------------------------------------------------------------------
# ⚠️ Ses choix sont greffés sur `accueil` ET sur `commission_repos` — le nœud d'attente servi
# pendant les 30 minutes qui suivent un rapport de commission. Sans cela, la mission serait
# injoignable juste après le fait d'armes qui la déclenche.

def choix_gautier():
	return [
		{
			"id": "bucherons_offre",
			"label": "« Vous me faites chercher, messire ? »",
			"condition": {"escorte_offerte": True},
			"next": "bucherons_propose",
		},
		{
			"id": "bucherons_rang",
			"label": "« Vous me faites chercher, messire ? »",
			"condition": {"escorte_rang_insuffisant": True},
			"next": "bucherons_rang_insuffisant",
		},
		{
			"id": "bucherons_relance",
			"label": "« Au sujet de {protege}… »",
			"condition": {"escorte_en_cours": True},
			"next": "bucherons_relance",
		},
		{
			"id": "bucherons_rapport",
			"label": "« Vous avez vu qui je vous ramène. »",
			"condition": {"escorte_accomplie": True},
			"next": "bucherons_rapport",
		},
	]


def noeuds_gautier():
	return {
		"bucherons_propose": {
			"texte": "« Je vous fais chercher depuis avant-hier. » Il repousse la carte des "
					 "galeries et en déroule une autre : la cité, ses routes, la forêt du "
					 "nord. Trois marques à l'encre rouge y forment un triangle serré. "
					 "« Trois bûcherons. Partis couper au nord, attendus il y a deux jours, "
					 "jamais rentrés. Leur employeur est venu réclamer de l'aide, et je n'aime pas "
					 "ce que je ne comprends pas : ces hommes-là connaissent le bois mieux que mes "
					 "éclaireurs. Une battue ordinaire aurait dû les ramener. »",
			"choix": [
				{"id": "absence", "label": "« Pourquoi ne pas envoyer une troupe ? »", "next": "bucherons_absence"},
				{"id": "architecte", "label": "« Y a-t-il autre chose ? »", "next": "bucherons_architecte"},
				{"id": "instructions", "label": "« Où dois-je commencer ? »", "next": "bucherons_instructions"},
				{"id": "refus", "label": "« Ce n'est pas pour moi, messire. »", "next": "accueil"},
			],
		},
		"bucherons_absence": {
			"texte": "« Parce qu'une troupe piétine, s'annonce à une lieue et rentre bredouille en "
					 "ayant coûté trois jours de solde. » Il appuie un doigt sur la marque du "
					 "milieu. « Et parce que si ces hommes sont vivants, ils sont terrés quelque "
					 "part à attendre qu'on vienne — pas qu'on batte les fourrés autour d'eux. Une "
					 "personne qui regarde vaut mieux que vingt qui marchent. C'est ma conviction, "
					 "et elle m'a rarement trompé. »",
			"choix": [
				{"id": "architecte", "label": "« Y a-t-il autre chose ? »", "next": "bucherons_architecte"},
				{"id": "instructions", "label": "« Où dois-je commencer ? »", "next": "bucherons_instructions"},
			],
		},
		"bucherons_architecte": {
			"texte": "Il hésite — chose rare — puis ouvre un pli posé au coin du bureau. « Il y a "
					 "autre chose, oui, et j'ignore si cela a le moindre rapport. Une voyageuse "
					 "devait rejoindre Auxerre cette semaine. Une architecte, recommandée par un "
					 "chapitre du sud : elle venait étudier nos cristaux de mana et la façon dont "
					 "nos bâtisseurs les emploient. » Il referme le pli. « Elle n'est jamais "
					 "arrivée. Je ne prétends rien. Je constate que deux disparitions tombent dans "
					 "la même semaine et dans la même direction. Si vous la trouvez, ramenez-la "
					 "aussi — et protégez-la : ce n'est pas une aventurière. »",
			"choix": [
				{"id": "instructions", "label": "« Où dois-je commencer ? »", "next": "bucherons_instructions"},
				{"id": "absence", "label": "« Pourquoi pas une troupe ? »", "next": "bucherons_absence"},
			],
		},
		"bucherons_instructions": {
			"texte": "« Suivez la route forestière vers le nord. Leur dernier chantier connu "
					 "est à une demi-journée de marche des murs. » Son doigt court le long d'un "
					 "trait d'encre. « Cherchez leurs traces : des coupes fraîches, des outils "
					 "laissés, un campement froid, des empreintes qui ne sont pas les leurs. Ce que "
					 "la forêt vous montrera vaudra mieux que tout ce que je peux vous en dire "
					 "d'ici. » Il vous regarde enfin vraiment. « S'ils vivent, ramenez-les-moi ici, "
					 "dans ce bureau, sur leurs jambes. {xp} points d'expérience et {prime} pièces "
					 "de cuivre à leur retour. Et ne prenez pas de risque inutile : nous ignorons "
					 "encore ce qui les a empêchés de rentrer. »",
			"choix": [
				{
					"id": "accepter",
					"label": "« Je vous les ramènerai. »",
					"action": {"service": "escorte", "op": "accepter"},
				},
				{"id": "refus", "label": "« Laissez-moi y réfléchir. »", "next": "accueil"},
			],
		},
		"bucherons_acceptee": {
			"texte": "Il note une ligne dans son registre, souffle sur l'encre et referme le "
					 "volume. « Alors c'est votre affaire, {prenom}. Une dernière chose, qui n'est "
					 "pas dans le contrat : ce ne sont pas des trophées. Une personne qu'on escorte "
					 "ne se bat pas, ne fuit pas, et ne survit qu'à la mesure de ce que vous "
					 "arrêtez avant elle. » Il vous rend votre salut. « Ramenez-les vivants. Le "
					 "reste ne m'intéresse pas. »",
			"choix": [{"id": "ok", "label": "« Ce sera fait. »", "next": "fin"}],
		},
		"bucherons_rang_insuffisant": {
			"texte": "« Je vous fais chercher, en effet. Et je vais vous décevoir. » Il croise les "
					 "mains sur la carte. « Ce que j'ai là demande qu'on réponde de vous, et "
					 "aujourd'hui la Guilde ne répond pas encore assez fort. Prenez les contrats du "
					 "Bastion, montez jusqu'au rang {rang_requis}, et revenez me voir. » Une pause "
					 "sans dureté. « Des hommes attendent quelque part dans ce bois. Je préfère les "
					 "faire attendre un jour de plus que d'y envoyer quelqu'un qui n'en reviendra "
					 "pas non plus. »",
			"choix": [
				{"id": "retour", "label": "« J'y travaillerai. »", "next": "accueil"},
				{"id": "fin", "label": "« Je reviendrai. »", "next": "fin"},
			],
		},
		"bucherons_relance": {
			"texte": "Il suit du doigt la ligne de son registre. « {protege}. » Il relève les yeux. "
					 "« Toujours dans ce bois, donc. » Il repousse la carte vers vous, la forêt du "
					 "nord bien au centre. « Ne me rapportez pas une histoire, {prenom}. "
					 "Rapportez-moi des gens. »",
			"choix": [{"id": "ok", "label": "« J'y retourne. »", "next": "fin"}],
		},
		"bucherons_rapport": {
			"texte": "Gautier vous a écouté jusqu'au bout sans vous couper une seule fois — les "
					 "loups, la fente de roche, les deux nuits, la demoiselle. Puis il prend une "
					 "épingle blanche et la plante sur la forêt du nord, à la place des trois "
					 "marques rouges. « Trois hommes vivants, et une voyageuse que je croyais "
					 "perdue. » Il se tourne vers l'architecte, qui se tient très droite malgré la "
					 "poussière. « Mademoiselle de Montfaucon. Votre voyage aura été plus mouvementé "
					 "que prévu. » — « Je le reconnais. » — « Vous êtes arrivée à Auxerre. C'est "
					 "l'essentiel. » Il revient à vous. « Quant à vous : bon travail. Mais cette "
					 "histoire tombe à un moment particulier. »",
			"choix": [
				{"id": "livraison", "label": "« Particulier comment ? »", "next": "bucherons_livraison"},
				{"id": "fin", "label": "« Je vous laisse à vos cartes. »", "next": "fin"},
			],
		},
		"bucherons_livraison": {
			"texte": "Il ouvre un registre à couverture noire. « Auxerre doit encore envoyer une "
					 "dernière livraison de cristaux de mana à Lutecia. » — « Lutecia ? » "
					 "L'architecte a relevé la tête si vite que Gautier marque un temps. « Lutecia, "
					 "mademoiselle. » Il referme le registre. « Elle devait partir avec une "
					 "caravane marchande. Les cristaux sont trop précieux pour voyager sans "
					 "protection, et les événements de cette semaine ne me disposent pas à "
					 "l'optimisme. »",
			"choix": [
				{"id": "proposition", "label": "« Et vous pensez à moi. »", "next": "bucherons_proposition"},
				{"id": "retour", "label": "Revenir.", "next": "bucherons_rapport"},
			],
		},
		"bucherons_proposition": {
			"texte": "« Je pense à vous, oui. » Il s'appuie des deux mains sur le bureau. « Nous "
					 "avons une livraison à conduire et, depuis ce matin, une personne de plus qui "
					 "doit se rendre dans la même cité. » — « Je souhaite en effet poursuivre mon "
					 "voyage », dit-elle, très posément. « Alors nous ferons d'une pierre deux "
					 "coups. Vous accompagnerez la livraison jusqu'à Lutecia. » Vous demandez si ce "
					 "sera seul. Gautier secoue la tête. « Non. Cette fois, la Guilde ne prendra "
					 "aucun risque. »",
			"choix": [
				{"id": "paladins", "label": "« Qui d'autre ? »", "next": "bucherons_paladins"},
			],
		},
		"bucherons_paladins": {
			"texte": "La porte s'ouvre. Deux paladins entrent — une elfe en haubert clair, un "
					 "hobbit en cotte de mailles — et saluent sans un mot de trop. « Une escorte de "
					 "l'ordre accompagnera le convoi », dit Gautier. « Leur charge : les cristaux "
					 "et mademoiselle de Montfaucon, jusqu'à Lutecia. » Il revient à vous. « La "
					 "vôtre : les accompagner, et veiller à ce que ce voyage se déroule "
					 "correctement. » L'architecte esquisse un sourire. « Il semblerait que je sois "
					 "arrivée à Auxerre au meilleur moment. » — « Ou au pire », répond Gautier sans "
					 "se retourner. « Cela dépendra de ce que vous trouverez sur la route de "
					 "Lutecia. »",
			"choix": [
				{"id": "depart", "label": "« Quand partons-nous ? »", "next": "bucherons_depart"},
			],
		},
		"bucherons_depart": {
			"texte": "« Dès que les caisses seront sanglées. » Gautier reprend sa plume, ce qui est "
					 "chez lui une façon de congédier. « Le convoi se forme dans la cour du "
					 "Bastion : allez vous présenter à la commandante, elle vous dira le reste "
					 "mieux que moi. » Puis, sans lever les yeux : « Et {prenom}… trois bûcherons "
					 "ont dormi chez eux cette nuit parce que quelqu'un est allé regarder au lieu "
					 "de battre les fourrés. Je le note aussi dans mes registres. »",
			"choix": [{"id": "ok", "label": "« Messire. »", "next": "fin"}],
		},
	}


def gautier(base):
	doc = nu(base["pnj:gautier_de_valcroix"])
	doc.setdefault("services", {})["escorte"] = {
		"offre": {
			"id": QUETE,
			"titre": "Les bûcherons disparus",
			"description": "Trois bûcherons d'Auxerre ne sont pas revenus d'une coupe au "
						   "nord de la cité, et une voyageuse attendue à la même date n'y "
						   "est jamais arrivée. Retrouvez-les, protégez-les, et ramenez-les "
						   "vivants au bureau du maître de la Guilde.",
			"destination": BUREAU,
			# Rendez-vous À L'ENTRÉE du lieu (aucune clé `zones` : la grotte n'a pas de grille,
			# `position_de_rencontre` rendrait None de toute façon) — les quatre `protege:*`
			# naissent au premier pas franchi dans la caverne.
			"rencontre": {"lieu": GROTTE_IN},
			"proteges": PROTEGES,
			"unique": True,
			"proba": 1,
			"rang_min": {"cite": CITE, "rang": "D"},
			"recompenses": {
				"xp": 120,
				"cuivre": 30000,
				"items": [{"item": "item:Cristal_canalisation", "poids": 0.1}],
			},
		},
		"noeuds": {"accepte": "bucherons_acceptee"},
	}
	noeuds = doc["dialogue"]["noeuds"]
	# Greffe des choix : juste AVANT le choix de sortie des deux nœuds d'entrée.
	for nid in ("accueil", "commission_repos"):
		_greffer(noeuds[nid], choix_gautier())
	noeuds.update(noeuds_gautier())
	return doc


def _greffer(noeud: dict, ajouts: list) -> None:
	"""Insère `ajouts` juste avant le dernier choix (celui de sortie) du nœud, en RETIRANT
	d'abord toute version antérieure des mêmes ids.

	⚠️ C'est ce retrait qui rend la greffe IDEMPOTENTE, et il n'est pas théorique : dès que
	la mission est importée une fois, le dump que ce générateur relit contient DÉJÀ ces
	choix. Une greffe naïve les ajoutait une seconde fois, et `choix_valide` ne rend que le
	premier d'un id dupliqué — le doublon serait mort, et la seule chose qui l'a signalé est
	le linter. Même exigence que pour tous les autres docs repris du dump : régénérer ne doit
	jamais dégrader la base."""
	neufs = {c["id"] for c in ajouts}
	choix = [c for c in noeud["choix"] if c.get("id") not in neufs]
	noeud["choix"] = choix[:-1] + ajouts + choix[-1:]


# ---------------------------------------------------------------------------
# 6. Borin Barbe-de-Jais — le déclencheur (doc du dump + nœuds)
# ---------------------------------------------------------------------------
# ⚠️ AUCUN `services.escorte.offre` ici : Borin porte déjà `services.escorte.recherche` (le
# registre des disparitions de la cité) et la branche ÉCRITE de `poser_escorte_offerte` est
# PRIORITAIRE — lui donner l'offre éteindrait son registre. Il annonce, il ne confie pas.
#
# ⚠️ Le rang D est tenu par le MOTEUR en deux endroits (le `rang_min` de l'offre et la
# barrière `acces` du bureau) ; ici il ne s'agit que d'afficher la réplique au bon moment,
# d'où deux choix de MÊME LABEL aux conditions complémentaires (`acces_ouvrable` = le rang est
# atteint mais l'escalier jamais monté ; `acces_ouvert` = il l'a déjà été). Le `relation_min`
# sur le comptoir exige en plus qu'au moins un contrat de la Guilde ait déjà été rendu :
# `recompenser_donneur` verse +1 à chaque turn-in et la cote neutre est 50.

def choix_borin():
	gate = {"lieux": [COMPTOIR], "seuil": 51}
	return [
		{
			"id": "bucherons_appel",
			"label": "« On me dit que le maître de la Guilde me cherche ? »",
			"condition": {"acces_ouvrable": True, "relation_min": gate},
			"next": "bucherons_appel",
		},
		{
			"id": "bucherons_appel_habitue",
			"label": "« On me dit que le maître de la Guilde me cherche ? »",
			"condition": {"acces_ouvert": True, "relation_min": gate},
			"next": "bucherons_appel",
		},
	]


def noeuds_borin():
	return {
		"bucherons_appel": {
			"texte": "« Hé ! Vous. Oui, vous. » Le nain pose le registre qu'il compulsait et se "
					 "penche par-dessus le comptoir. « Le maître de la guilde vous cherche. » Il "
					 "lève une main avant que vous ayez ouvert la bouche. « Et avant que vous "
					 "demandiez : non, ce n'est ni une histoire de dette, ni une bagarre de "
					 "taverne, ni un poulet volé. » Il marque un temps. « Cette fois, c'est "
					 "sérieux. »",
			"choix": [
				{"id": "quoi", "label": "« Que me veut-il ? »", "next": "bucherons_appel_qui"},
				{"id": "plus_tard", "label": "« Il attendra. »", "next": "accueil"},
			],
		},
		"bucherons_appel_qui": {
			"texte": "« Il ne m'a rien expliqué. Il a seulement dit de vous envoyer le voir dès que "
					 "vous mettriez les pieds ici. » Le ton descend d'un cran, et la malice avec. "
					 "« Ça concerne des gens qui ne sont pas revenus de la forêt. »",
			"choix": [
				{"id": "aventuriers", "label": "« Des aventuriers ? »", "next": "bucherons_appel_escalier"},
				{"id": "monter", "label": "« J'y vais. »", "next": "accueil"},
			],
		},
		"bucherons_appel_escalier": {
			"texte": "« Des bûcherons. Trois hommes. » Borin referme le registre d'un geste. « Ils "
					 "coupent pour plusieurs exploitants de la région, ils connaissent ces bois "
					 "depuis toujours, et voilà deux jours qu'on les attend. Ça commence à faire "
					 "beaucoup de temps, pour des gens qui ne se perdent pas. » Il désigne du "
					 "pouce l'escalier du fond. « Le maître de la guilde est dans son bureau. "
					 "Montez. Il vous dira le reste. »",
			"choix": [
				{"id": "retour", "label": "« Merci, Borin. »", "next": "accueil"},
				{"id": "fin", "label": "Monter l'escalier.", "next": "fin"},
			],
		},
	}


def borin(base):
	doc = nu(base["pnj:borin_barbe_de_jais"])
	noeuds = doc["dialogue"]["noeuds"]
	_greffer(noeuds["accueil"], choix_borin())
	noeuds.update(noeuds_borin())
	return doc


# ---------------------------------------------------------------------------
# 8. Lieux
# ---------------------------------------------------------------------------
# ⚠️ Un bloc `acces` SANS gardien est parfaitement opérant : `acces_autorise` teste le
# laissez-passer PUIS les conditions — un lieu dont les conditions sont remplies s'ouvre tout
# seul, le service PNJ ne servant qu'à délivrer un laissez-passer. C'est ce qui fait
# apparaître la grotte habitée et la clairière PENDANT la mission, et disparaître ensuite,
# sans qu'aucun PNJ n'ait à ouvrir quoi que ce soit.

def lieu_grotte(base):
	"""Le seuil de la grotte : Armand parle à travers la fente. ⚠️ Aucune `probabilite` — il
	est le gardien du combat, et un gardien absent au tirage rendrait la suite injouable."""
	doc = nu(base[GROTTE])
	doc["pnj"] = [{
		"character": "pnj:armand_renaud",
		"nom": "Armand Renaud",
		"portrait": "bucheron_Armand_Renaud_humain_m.jpg",
		"description": "Une voix d'homme, derrière l'éboulis qui ferme à demi l'entrée.",
	}]
	return doc


def lieu_grotte_interieur(base):
	"""La grotte HABITÉE — n'existe que le temps de la mission (`..._interieur`, la version
	vide, reste ouverte le reste du temps, exactement comme demandé). Trois entrées `pnj` : le
	tirage change à chaque entrée, c'est ce qui laisse reconstituer l'histoire par morceaux."""
	doc = nu(base[GROTTE_IN])
	doc["pnj"] = [
		{
			"character": "pnj:aelis_de_montfaucon",
			"nom": "Aélis de Montfaucon",
			"portrait": "architecte_Aélis_de_Montfaucon_humain_f03.jpg",
			"probabilite": 0.5,
			"description": "Une jeune femme assise à l'écart du feu, un carnet serré contre elle.",
		},
		{
			"character": "pnj:etienne_morel",
			"nom": "Étienne Morel",
			"portrait": "bucheron_Étienne_Morel_nain_m.jpg",
			"probabilite": 0.5,
			"description": "Un nain adossé à la paroi, la jambe serrée dans un garrot de fortune.",
		},
		{
			"character": "pnj:matthieu_perrin",
			"nom": "Matthieu Perrin",
			"portrait": "bucheron_Matthieu_Perrin_ogre_m.jpg",
			"description": "Un ogre assis face à l'entrée, un tronçon de charme en travers des genoux.",
		},
	]
	doc["acces"] = {
		"refus": "La fente est trop étroite pour qu'on s'y glisse sans raison, et rien ne bouge "
				 "au fond de l'ombre.",
		"cycle": 1,
		"conditions": CONDITION_QUETE,
	}
	return doc


def lieu_grotte_vide(base):
	"""La grotte VIDE — celle qu'on visite hors mission. ⚠️ Masquée PENDANT la quête : sans
	cela, deux boutons « Penetrer dans la grotte » cohabitent au seuil, et rien ne distingue
	le bon du mauvais. Ce n'est pas cosmétique — le joueur est entré dans celle-ci, n'y a
	trouvé personne, et le rendez-vous de l'escorte ne s'est jamais déclenché."""
	doc = nu(base[GROTTE_VIDE])
	doc["acces"] = {
		"refus": "Des voix montent du fond de la grotte : ce n'est pas le moment d'y entrer "
				 "en curieux.",
		"cycle": 1,
		"conditions": CONDITION_HORS_QUETE,
	}
	return doc


def lieu_bataille(base):
	"""La salle de combat. ⚠️ `categorie: battle_map` ⇒ franchir la porte n'ouvre pas un lieu,
	elle OUVRE LE COMBAT — aucun doc `connection` n'est requis (ni souhaitable) ici."""
	doc = nu(base[BATAILLE])
	doc["acces"] = {
		"gardien": "pnj:armand_renaud",
		"refus": "Rien ne rôde devant cette grotte, et rien ne vous y attend.",
		"cycle": 1,
		# ⚠️ La seconde condition est ce qui empêche de REJOUER le combat indéfiniment. Une
		# escorte ne fait jamais monter `progress`, donc `objectif_atteint: false` — le filtre
		# qui ferme la boucle d'un donjon commissionné — n'a aucune prise ici. Le frein était
		# un `delai_min` de 30 min chez Armand : un pansement, remplacé par la victoire elle-même.
		"conditions": CONDITION_QUETE + [dict(CONDITION_LOUPS_DEBOUT)],
	}
	return doc


def lieu_clairiere():
	"""La clairière DÉGAGÉE : elle n'existe qu'une fois les trois loups abattus — c'est tout
	son sens, et c'est ce que le moteur ne savait pas exprimer avant le marqueur de victoire.

	⚠️ PASSAGE UNIQUE : la troisième condition l'efface dès qu'on y a mis les pieds. On la
	traverse en sortant du combat (Armand y conduit par le hook `deplacer` de son nœud
	d'après-bataille), et elle ne revient plus encombrer la liste du seuil.
	⚠️ Elle reste QUITTABLE une fois refermée : `get_lieu_links` ne filtre jamais le lieu
	COURANT, et la garde 403 du déplaceur porte sur la destination — on entre, la porte se
	referme derrière, on ressort vers Auxerre ou vers le seuil.
	⚠️ Elle se referme aussi à la fin de la quête (la condition de quête reste dans le ET) :
	le chapitre de la grotte est clos, les abords redeviennent une caverne vide."""
	return {
		"_id": CLAIRIERE,
		"type": "lieu",
		"label": "La clairière devant la grotte",
		"image": "Retrouver_les_bûcherons_d_Auxerre_victoire_combat.jpg",
		"categorie": "grotte",
		"lieu_parent": CITE,
		"acces": {
			"refus": "Les fougères ont repris la clairière ; il n'y a plus rien à y voir.",
			"cycle": 1,
			"conditions": CONDITION_QUETE + [dict(CONDITION_LOUPS_ABATTUS),
											 dict(CONDITION_CLAIRIERE_NEUVE)],
		},
	}


# ---------------------------------------------------------------------------
# 9. Connexions de la clairière
# ---------------------------------------------------------------------------
# ⚠️ Un bloc `acces` n'est PAS une porte : sans doc `connection`, la clairière serait
# structurellement inatteignable — et sans le moindre message d'erreur.
#
# ⚠️ SENS DU LABEL, le piège de cette section : le `label` d'un nœud nomme le GESTE POUR
# ARRIVER AU LIEU DE CE NŒUD — jamais pour en partir. C'est ce que `buildLocationslist`
# (play_town_telluris.html) impose : au lieu courant, elle affiche le nœud DESTINATION
# (`l.lieu !== lieu_courant`) et rend son label. Les deux connexions ci-dessous les ont eus
# inversés : depuis le seuil de la grotte, le bouton vers la clairière annonçait « Remonter
# vers le seuil de la grotte » — c'est-à-dire l'endroit où l'on se trouvait déjà.
# ⚠️ La `pos` d'un lieu SANS grille est [0, 0] ; celle du nœud `lieu:auxerre` doit être la case
# de la cité où le lien s'ouvre — reprise de la porte de la grotte, à laquelle la clairière est
# adossée, plutôt que codée en dur.

def connexions(base):
	porte = next(
		(n.get("pos") for n in base["link:grotte_dans_foret_humide_to_auxerre"]["nodes"]
		 if n.get("lieu") == CITE),
		[61, 1],
	)
	return [
		{
			"_id": "link:clairiere_de_la_grotte_liberee_to_grotte_dans_foret_humide",
			"type": "connection",
			"nodes": [
				{"lieu": CLAIRIERE, "pos": [0, 0], "label": "Gagner la clairière dégagée"},
				{"lieu": GROTTE, "pos": [0, 0], "label": "Remonter vers le seuil de la grotte"},
			],
			"metadata": {"type": "grotte", "status": "ouvert"},
		},
		{
			"_id": "link:clairiere_de_la_grotte_liberee_to_auxerre",
			"type": "connection",
			"nodes": [
				{"lieu": CLAIRIERE, "pos": [0, 0], "label": "Revenir à la clairière"},
				{"lieu": CITE, "pos": list(porte), "label": "Prendre la route basse vers la cité"},
			],
			"metadata": {"type": "grotte", "status": "ouvert"},
		},
	]


# ---------------------------------------------------------------------------
# 10. Le donjon d'une seule salle : les trois loups géants
# ---------------------------------------------------------------------------
# ⚠️ `niveau_max` n'est pas décoratif : une salle de donjon n'a AUCUNE zone d'influence pour
# borner ses grades — sans plafond, les trois loups seraient tirés parmi tous les profils de
# la base (jusqu'au niveau 6) et rendraient la rencontre imbattable au rang D.
# `_declencher_combat_donjon` pose `nb_monstres = 3 + len(compagnons) // 2` : trois loups pour
# un joueur seul, exactement la meute décrite.

# Fourchette de grade PAR DÉFAUT, posée à la seule création du doc. ⚠️ Elle n'est PAS
# réimposée à la régénération : c'est le bouton d'équilibrage, il se règle en base ou dans
# `/admin`, et un générateur qui le réécrirait annulerait le réglage EN SILENCE — exactement
# ce que la relecture du dump évite pour tous les autres docs de ce fichier.
# ⚠️ `nb_monstres: 3` n'est PAS un réglage d'équilibrage, c'est une contrainte de RÉCIT :
# Armand dit « Trois. Toujours les trois mêmes », Aélis en a compté trois, Matthieu parle de
# trois bêtes. Sans ce champ le moteur applique `3 + compagnons // 2` et un quatrième loup
# dément les trois dialogues sous les yeux du joueur. Le baisser ou le monter, c'est réécrire
# ces répliques.
BORNES_DEFAUT = {"niveau_max": 2, "nb_monstres": 3}

# Ce que l'on considère comme du RÉGLAGE : posé une fois, puis réglé à la main en base ou
# dans /admin. Le générateur ne le réimpose jamais — il réécrit le CONTENU (nom, description,
# portail, pool d'espèces) et laisse la barre à l'auteur.
REGLAGES_DONJON = ("niveau_max", "niveau_min", "nb_monstres")


def donjon(base):
	"""Le donjon d'une seule salle. Les défauts d'auteur sont posés d'abord, puis ce qui est
	déjà en base les écrase : un réglage retouché à la main survit à la régénération, et un
	champ neuf (comme `nb_monstres`) arrive quand même sur un doc déjà importé."""
	doc = _neuf_donjon()
	doc["battle_maps"][0].update(BORNES_DEFAUT)
	ancien = base.get(DONJON)
	if ancien:
		bornes_salle = (nu(ancien).get("battle_maps") or [{}])[0]
		for cle in REGLAGES_DONJON:
			if cle in ancien:
				doc[cle] = ancien[cle]
			if cle in bornes_salle:
				doc["battle_maps"][0][cle] = bornes_salle[cle]
	return doc


def _neuf_donjon():
	return {
		"_id": DONJON,
		"type": "donjon",
		"nom": "La meute du seuil",
		"description": "Trois loups géants ont fait de l'entrée d'une grotte du nord "
					   "d'Auxerre leur territoire. Ils ne creusent pas, ils ne hurlent pas : "
					   "l'ouverture est trop étroite pour leurs corps, alors ils attendent que ce "
					   "qui s'est terré à l'intérieur finisse par en sortir.",
		"portail": GROTTE,
		"battle_maps": [
			{"lieu": BATAILLE, "especes": ["espece:loup_geant"]},
		],
	}


def main():
	base = charger()
	docs = [
		pnj_armand(), pnj_etienne(), pnj_matthieu(), pnj_aelis(),
		gautier(base), borin(base),
		lieu_grotte(base), lieu_grotte_interieur(base), lieu_grotte_vide(base),
		lieu_bataille(base),
		lieu_clairiere(),
		*connexions(base),
		donjon(base),
	]
	os.makedirs("jsons", exist_ok=True)
	_ecrire(SORTIE, docs)
	# Correctif ciblé des abords de la grotte : tout ce qui décide de ce que le joueur VOIT
	# au seuil (les deux connexions, les trois lieux gardés) plus Armand, qui commande le
	# combat. ⚠️ Bâti par les MÊMES fonctions que le bundle ci-dessus : les deux fichiers ne
	# peuvent pas diverger.
	_ecrire(SORTIE_GROTTE, [
		# Les QUATRE qui peuvent désormais ouvrir le combat : Armand depuis le seuil, et les
		# trois réfugiés depuis l'intérieur (`services.acces` est porté par le PNJ).
		pnj_armand(), pnj_etienne(), pnj_matthieu(), pnj_aelis(),
		lieu_grotte_interieur(base), lieu_grotte_vide(base), lieu_bataille(base),
		lieu_clairiere(),
		*connexions(base),
	])


def _ecrire(chemin, docs):
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{chemin} : {len(docs)} documents")
	for d in docs:
		print("  ", d["_id"])


if __name__ == "__main__":
	main()
