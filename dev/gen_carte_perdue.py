#!/usr/bin/env python
# dev/gen_carte_perdue.py
# Carte d'aventurier PERDUE : l'inscrit revient au comptoir, le ou la réceptionniste se moque,
# puis refait la carte au même rang (le rang vit dans `rangs_guilde`, jamais sur la carte).
#
# Moteur : flag `don_a_remplacer` (`pnj.don_a_remplacer` : don `unique` localisé, carte absente
# du sac, personnage déjà inscrit dans cette cité) et nœud optionnel `services.don.noeuds.
# remplacement` (repli sur `fait`). Ce script n'écrit que la DONNÉE :
#   - les réceptionnistes qui inscrivent par un don (`services.don.item == carte`) : choix
#     « J'ai… perdu ma carte » (condition `don_a_remplacer`), l'inscription masquée pour un
#     inscrit, nœud `carte_remplacee` ;
#   - Borin (Bastion de l'Yonne) remet la carte par sa PREMIÈRE MISSION, pas par un don : il
#     reçoit un `don` dont le seul choix est conditionné par `don_a_remplacer` — la condition
#     est revalidée au serveur (`pnj.choix_valide`), la mission reste donc la seule porte
#     d'entrée à Auxerre. Son `rang_guilde` est celui de la récompense de la mission.
#
# Relit le dump le plus récent, n'écrit que les docs qui CHANGENT (CLAUDE.md §11, §18) →
# jsons/carte_perdue_a_importer.json. Rejouable : un second passage ne change plus rien.
#
# Usage : python dev/gen_carte_perdue.py

import copy
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "jsons", "carte_perdue_a_importer.json")

CARTE = "item:carte_aventurier"
BORIN = "pnj:borin_barbe_de_jais"
NOEUD = "carte_remplacee"
CHOIX_ID = "carte_perdue"
FLAG = "don_a_remplacer"
LABEL = "« J'ai… perdu ma carte d'aventurier. »"

# Une moquerie par réceptionniste, dans sa voix (descriptions et accueils du dump). Le joueur
# au neutre, narration au « vous » ; Borin tutoie. `{rang}` = le rang du registre, inchangé.
MOQUERIES = {
	"pnj:alienor_cheapside": (
		"Aliénor repose son bâton de cire et vous dévisage un long moment. « Perdue. » Le mot tombe "
		"comme un sceau mal pris. « Vous affrontez des monstres pour gagner votre pain, {prenom}, et "
		"une plaque de cuir vous échappe des poches. » Un soupir qui en dit long sur ses journées. Elle "
		"retrouve votre nom dans la charte, rédige une carte neuve et la scelle de rouge. « Rang {rang}, "
		"comme avant. La charte n'égare jamais rien. Essayez de l'imiter. »"),
	"pnj:ana_bucur": (
		"Ana éclate d'un rire si franc que la flamme de sa lanterne en tremble. « Perdue ? Vous l'avez "
		"peut-être mangée avec le reste, sur la route ! » Elle s'essuie les yeux du revers de sa manche "
		"brodée, ouvre le registre et retrouve votre nom du premier coup. « Rang {rang} : de ce côté-là, "
		"rien n'est perdu. Tenez. Et cousez-vous une poche, {prenom}. Ma grand-mère vous dirait la même "
		"chose, en moins poli. »"),
	"pnj:andecombe_coteaux": (
		"Andécombe vous fixe sans ciller, comme un témoin qui vient de se contredire. « Votre "
		"sauf-conduit. Perdu. Sur la route. Au carrefour où passe toute la Champagne. » Le coin de sa "
		"bouche se relève à peine : chez elle, c'est un éclat de rire. Elle recopie votre nom d'une plume "
		"sèche. « Rang {rang}, le registre l'atteste. Votre carte, {prenom}. La prochaine, je vous la "
		"cloue au ceinturon. »"),
	"pnj:berenice_du_phare": (
		"Bérénice pose son astrolabe et se mord la lèvre pour ne pas rire, sans grand succès. « Je sais "
		"calculer où sera une étoile qu'on ne voit pas encore, {prenom}. Mais une carte d'aventurier "
		"perdue entre ici et le désert, aucun traité ne dit où la chercher. » Elle déroule son papyrus et "
		"retrouve votre nom. « Rang {rang}, inchangé. Les astres sont plus fidèles que vos poches. »"),
	BORIN: (
		"Borin te regarde longuement, puis sa barbe se met à trembler. Le rire finit par sortir, énorme, "
		"et deux aventuriers se retournent au fond de la salle. « Perdue ! Vous entendez ça, là-bas ? Ça "
		"m'a porté des caisses de sanglier jusqu'au fumoir sans en lâcher une, et ça me perd une plaque "
		"de cuir grande comme ma main ! » Il s'essuie les yeux, tire le registre à lui et grave une carte "
		"neuve sans même chercher ton nom : il le connaît. « Rang {rang}, comme avant. Ça, personne ne te "
		"le prendra. Mais attache-la, {prenom}. La prochaine que je refais, tu paies la tournée. »"),
	"pnj:cornelia_sept_collines": (
		"Cornélia efface sa tablette d'un geste lent, en savourant l'instant. « L'or, la gloire ou la "
		"disgrâce, disais-je. Vous avez choisi la troisième, {prenom}. » Elle laisse passer un silence. "
		"« J'ai connu un sénateur qui avait égaré son anneau au Colisée. On en rit encore sur les sept "
		"collines. » Elle grave votre nom sur une carte neuve. « Rang {rang}, rien n'a changé. Sauf la "
		"rumeur, qui court déjà. »"),
	"pnj:cynan_de_winchester": (
		"Cynan plante une épingle dans sa carte, à un endroit précis, sans un mot. « Là. C'est là que je "
		"mets ce qu'on perd, d'ordinaire : des moutons, des hameaux, des porteurs de lanterne. Pas des "
		"cartes de la Guilde. » Il grogne, ce qui pourrait passer pour un rire. Une plaque neuve frappée "
		"du cor de chasse glisse vers vous. « Rang {rang}. Le registre ne perd rien, lui. Si quelqu'un "
		"me rapporte l'autre, {prenom}, je saurai où vous l'avez semée. »"),
	"pnj:edith_des_cinq_ports": (
		"Édith fait sonner sa cloche trois fois, très fort. Toute la salle se retourne. « Avis à "
		"l'équipage ! {prenom} a perdu sa carte ! » Elle laisse rire les marins tout leur soûl, puis "
		"vous tend une plaque neuve frappée de la falaise et de la vague. « Rang {rang}, comme c'était "
		"écrit. Voilà. Maintenant, tout Douvres la cherchera avec vous. C'est le prix, et il est doux. »"),
	"pnj:eginhard_palatin": (
		"Éginhard trempe sa plume, l'air ravi. « Attendez, je note. » Il écrit lentement, à mi-voix : "
		"« En ce jour, {prenom}, rang {rang}, égara sa carte… » Il relève les yeux. « Les chroniques "
		"ont besoin de ce genre de détail. Sans eux, tous les héros se ressemblent. » Une plaque frappée "
		"de l'octogone glisse sur le comptoir. « Votre carte. Le rang n'a pas bougé. La chronique, elle, "
		"gardera tout. »"),
	"pnj:eleonore_de_vaugirard": (
		"Éléonore ne dit rien. Elle repose sa plume, croise les mains sur le registre et vous regarde "
		"jusqu'à ce que le silence devienne gênant. « Perdue. » Le mot sonne comme une ligne de plus "
		"dans le registre. « Je vous avais dit de revenir me voir si cela arrivait, {prenom}. Je n'avais "
		"pas dit que je l'espérais. » L'ombre d'un sourire, aussitôt rangée. Elle trace une carte neuve "
		"d'une écriture nette. « Rang {rang}, comme hier. Je n'ai rien oublié de vous. Tâchez de ne pas "
		"oublier celle-ci. »"),
	"pnj:eustache_bourgeois": (
		"Eustache lève sa longue-vue, la braque sur vous, puis sur la mer, puis de nouveau sur vous. "
		"« Non. Je ne la vois nulle part. Ni sur le quai, ni au fond du détroit. » Il range l'instrument, "
		"hilare. « Une carte de la Guilde, ça ne flotte pas, {prenom}. C'est le genre de chose qu'on "
		"devrait savoir, quand on vit d'aventure. » Une plaque neuve frappée du fanal passe le comptoir. "
		"« Rang {rang}. Ça, la mer ne vous le prendra pas. »"),
	"pnj:fulberte_du_tertre": (
		"Fulberte arase sa mesure à grain sans se presser, puis vous la tend, vide. « Voilà ce qu'il "
		"reste de votre carte. » Elle rit, d'un rire court et sec de comptable. « Ici, on compte chaque "
		"grain qui sort du grenier, {prenom}, et vous perdez la seule chose que la maison vous ait "
		"confiée. » Elle retrouve votre ligne au registre. « Rang {rang}, exact au grain près. Tenez. Et "
		"ne la semez pas dans la Beauce : elle n'y repoussera pas. »"),
	"pnj:karli_de_la_baie": (
		"Karli manque de renverser sa corne à boire tant il rit. « Perdue ! Sur l'île, on perd des bottes "
		"dans la boue chaude, des bonnets dans le vent, parfois un doigt dans la glace. Mais une carte ? » "
		"Il ouvre le registre et retrouve votre nom, avec un sourire qui ne veut pas partir. « Rang "
		"{rang}, rien n'a fondu. Tenez, {prenom}. Gardez-la au chaud, contre vous : ici, c'est ce qu'on "
		"fait de tout ce qui compte. »"),
	"pnj:lieven_buerse": (
		"Lieven prend le temps de reposer son échantillon de cuir. « Perdue. Ou vendue. » Il vous "
		"détaille de la tête aux pieds. « À Bruges, une carte de la Guilde se négocie dans les ruelles "
		"derrière la Bourse. Si c'est le cas, vous l'avez mal vendue, {prenom}, puisque vous voilà à me "
		"la redemander. » Un rire bref, sans chaleur. Il vous tend une plaque neuve. « Rang {rang}. Ne "
		"m'obligez pas à en graver une troisième : celle-là, je vous la facturerais. »"),
	"pnj:liu_bowen": (
		"Liu Bowen fait claquer une boule de son boulier, puis une autre. « Une carte remise. Une carte "
		"perdue. » Il pousse une troisième boule, l'air ravi. « Une carte refaite. Le compte est juste, "
		"{prenom}, mais le bénéfice est pour moi : je raconterai ça ce soir. » Il retrouve votre nom au "
		"registre et vous tend la plaque. « Rang {rang}, inchangé. Neuf portes pour venir jusqu'ici, et "
		"pas une pour retrouver ce qu'on a perdu. »"),
	"pnj:louise_labe": (
		"Louise repose sa balance avec un soupir de théâtre. « Tout finit par passer devant ce comptoir. "
		"Même les aventuriers qui perdent leur carte. » Elle rit, d'un rire large qui fait danser son "
		"foulard. « Les bateliers me rapportent tout ce que charrient les deux fleuves, {prenom}. Une "
		"plaque de cuir, jamais. » Elle vous en tend une neuve. « Rang {rang}, toujours. Et passez-y un "
		"cordon : c'est le métier de ma famille, je vous le ferai à bon prix. »"),
	"pnj:ota_dokan": (
		"Ōta Dōkan pose son pinceau et sourit, las mais sincèrement amusé. Il récite à mi-voix : "
		"« Carte égarée — / sur le pont d'Edo le vent / ne rend jamais rien. » Il vous laisse un moment "
		"avec ces vers. « Je ne le montrerai à personne, {prenom}. Celui-là, peut-être, à quelques amis. » "
		"Une plaque neuve passe sous votre main. « Rang {rang}. Le registre, lui, ne s'envole pas. »"),
	"pnj:paser_des_deux_rives": (
		"Paser cesse de plier son bandeau et vous regarde d'un air faussement grave. « Ici, les morts "
		"gardent leurs bijoux des siècles durant. Et vous, bien vivant, vous n'avez pas su garder une carte "
		"une saison. » Un rire bref lui échappe, et il a l'air presque gêné de l'avoir laissé sortir. "
		"« Rang {rang}, toujours au registre. Voilà la nouvelle. Je peux vous l'emmailloter de lin, "
		"{prenom} : de l'autre côté du fleuve, ça conserve tout. »"),
	"pnj:patyegarang": (
		"Patyegarang rit si fort que les oiseaux de la véranda s'envolent. « Il faut que je vous apprenne "
		"un mot. Celui pour quelqu'un qui perd sa carte. » Elle réfléchit. « Il n'existe pas. Personne "
		"n'en avait eu besoin avant vous. » Elle grave votre nom sur une plaque neuve frappée de la bolas. "
		"« Rang {rang}, rien n'a changé. Tenez, {prenom}. Répétez après moi : je ne la perdrai plus. "
		"Encore. C'est pas grave, on a le temps. »"),
	"pnj:perrine_boucher": (
		"Perrine compte sur ses doigts, s'arrête, recommence. « Dix-huit sacs de sel ce matin, pas un de "
		"travers. Et vous, une carte. Une seule. » Elle soupire d'une lassitude qu'on dirait très "
		"ancienne, mais ses yeux rient. « Rang {rang}, au grain de sel près. La voilà, {prenom}. La "
		"prochaine fois, je vous la fais livrer par la barque, avec un connaissement. »"),
	"pnj:pytheas_de_massalia": (
		"Pythéas fait rouler sa plaque d'orichalque entre ses doigts, un sourire en coin. « J'ai "
		"traversé des mers que personne ne nomme, {prenom}, et je n'ai jamais perdu ceci. » Il la range. "
		"« Remarquez, à force de croiser des serpents de mer, on oublie ce qu'on a dans les poches. » "
		"Il retrouve votre nom au registre. « Rang {rang}, comme avant. Voilà la nouvelle. Et gardez-la "
		"loin du quai : ici, ce qui tombe à l'eau appartient à Poséidon. »"),
	"pnj:tarra_birrarung": (
		"Tarra coupe un brin d'osier d'un coup de dents et le pointe vers vous. « La Guilde ou un "
		"panier, je vous avais dit. Vous auriez dû prendre le panier. » Elle rit franchement, puis ouvre "
		"le registre. « Rang {rang}, toujours là. Voilà votre carte, {prenom}. Je vous tresserais bien un "
		"étui, si vous me promettiez de ne pas le perdre aussi. »"),
	"pnj:thorunn_hyrna": (
		"Thórunn s'arrête de compter ses pitons. Elle vous fixe, et un rire rauque lui échappe, comme "
		"une pierre qui dévale. « Dans une cordée, qui perd son piton reste au refuge. » Elle hausse les "
		"épaules. « Heureusement pour vous, nous ne sommes pas de la même cordée. » Une plaque neuve "
		"frappée de la hache claque sur le comptoir. « Rang {rang}, pareil. Sur vous, {prenom}, pas dans "
		"le sac : le sac, on le lâche quand ça glisse. »"),
	"pnj:tochtli_de_la_chaussee": (
		"Tochtli dénoue lentement une cordelette, puis y fait un autre nœud, très serré et très laid. "
		"« Celui-là, c'est vous. Le nœud de ceux qui perdent leur carte. Je n'en fais pas souvent. » Ses "
		"yeux vifs pétillent. Il retrouve votre ligne et vous tend une plaque neuve. « Rang {rang} : ce "
		"nœud-là n'a pas bougé, {prenom}. Celui de votre réputation, je le laisse quelque temps. »"),
	"pnj:yusuf_ibn_tulun": (
		"Yusuf pose une carte vierge sur un plateau de sa balance, rien sur l'autre. Le plateau descend à "
		"peine. « Voyez : ça ne pèse presque rien. C'est peut-être pour ça que vous ne l'avez pas sentie "
		"partir. » Il rit de bon cœur, la main sur le ventre. « Ici, tout se pèse, {prenom}, même la "
		"honte. La vôtre est légère, rassurez-vous. » Il grave votre nom. « Rang {rang}, comme au "
		"registre. Que la paix garde celle-ci mieux que l'autre. »"),
	"pnj:zaydu_caravanserail_des_seuils": (
		"Zaydu vous tend d'abord un gobelet d'eau, comme toujours, et seulement ensuite il éclate de rire. "
		"« Buvez, buvez, ça aide à avaler. C'est la première fois de la saison qu'on perd sa carte avant "
		"sa gourde. » Il essuie ses mains sur son gilet et ouvre le registre. « Rang {rang}, recopié comme "
		"au premier jour. Tenez, {prenom}. À Petra, on garde la clé d'une citerne toute une vie : essayez "
		"de garder ceci jusqu'à la prochaine saison. »"),
}

# Borin n'a ni inscription ni nœuds de don : on les lui pose (il tutoie).
BORIN_DON = {
	"item": CARTE, "quantite": 1, "cout_cuivre": 0, "lieu_parent": "auto", "unique": True,
	"noeuds": {"fait": NOEUD, "remplacement": NOEUD,
			   "sans_fonds": "carte_sans_fonds", "trop_charge": "carte_trop_charge"},
}
BORIN_NOEUDS = {
	"carte_trop_charge": {
		"texte": "« Pas même la place d'une carte dans ton sac, {prenom} ? Allège-toi d'abord. Ton nom ne bougera pas du registre. »",
		"choix": [{"id": "ok", "label": "Je reviens le sac plus léger.", "next": "fin"}]},
	"carte_sans_fonds": {
		"texte": "« Une carte refaite ne coûte rien au Bastion, {prenom}. Si quelqu'un t'a dit le contraire, envoie-le-moi. »",
		"choix": [{"id": "ok", "label": "Je reviendrai.", "next": "fin"}]},
}


def dernier_dump():
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		sys.exit("ERREUR : aucun dump jsons/telluris-dump-*.json")
	with open(dumps[-1], encoding="utf-8") as f:
		return {d["_id"]: d for d in json.load(f)["docs"]}, os.path.basename(dumps[-1])


def receptionnistes(docs):
	"""Ids des PNJ qui refont la carte : ceux qui l'inscrivent par un don, plus Borin."""
	ids = sorted(i for i, d in docs.items() if i.startswith("pnj:")
				 and ((d.get("services") or {}).get("don") or {}).get("item") == CARTE)
	return ids + ([BORIN] if BORIN in docs and BORIN not in ids else [])


def appliquer(doc):
	"""Mute `doc` (copie) pour la carte perdue. Idempotent."""
	pid = doc["_id"]
	if pid not in MOQUERIES:
		sys.exit(f"ERREUR : aucune moquerie écrite pour {pid}")
	services = doc.setdefault("services", {})
	dialogue = doc["dialogue"]
	noeuds = dialogue["noeuds"]
	depart = noeuds[dialogue["noeud_depart"]]
	if pid == BORIN:
		services["don"] = copy.deepcopy(BORIN_DON)
		# Même rang d'inscription que la première mission, RELU dans sa récompense (jamais recopié) :
		# un inscrit dont `rangs_guilde` est resté vide (archives d'avant `crediter_rang`) y est
		# posé ; tout autre garde son rang, `crediter_rang` ne rétrogradant pas.
		rang_mission = ((((services.get("transport") or {}).get("offre") or {})
						 .get("recompenses") or {}).get("rang_guilde"))
		if not rang_mission:
			sys.exit(f"ERREUR : {pid} sans `rang_guilde` dans la récompense de sa première mission")
		services["don"]["rang_guilde"] = rang_mission
		noeuds.update(copy.deepcopy(BORIN_NOEUDS))
		suite = [{"id": "merci", "label": "« Merci, Borin. »", "next": "fin"},
				 {"id": "retour", "label": "Autre chose…", "next": "accueil"}]
	else:
		services["don"].setdefault("noeuds", {})["remplacement"] = NOEUD
		suite = [{"id": "merci", "label": "« Merci. Je ferai attention. »", "next": "fin"},
				 {"id": "retour", "label": "Une autre question…", "next": "accueil"}]
	noeuds[NOEUD] = {"texte": MOQUERIES[pid], "choix": suite}

	choix = depart["choix"]
	nouveau = {"id": CHOIX_ID, "label": LABEL, "condition": {FLAG: True}, "action": {"service": "don"}}
	ids = [c.get("id") for c in choix]
	if CHOIX_ID in ids:
		choix[ids.index(CHOIX_ID)] = nouveau
	elif "inscription" in ids:
		choix.insert(ids.index("inscription") + 1, nouveau)
	else:
		# Borin : juste avant « Je ne faisais que passer », toujours en dernier.
		choix.insert(ids.index("rien") if "rien" in ids else len(choix), nouveau)
	for c in choix:
		if c.get("id") == "inscription":
			# Un inscrit qui a perdu sa carte ne se RÉ-inscrit pas : il a son propre choix.
			c.setdefault("condition", {})[FLAG] = False
	return doc


def main():
	docs, nom_dump = dernier_dump()
	sortie = []
	for pid in receptionnistes(docs):
		avant = docs[pid]
		apres = appliquer(copy.deepcopy(avant))
		if apres != avant:
			apres.pop("_rev", None)
			sortie.append(apres)
	inconnus = set(MOQUERIES) - set(receptionnistes(docs))
	if inconnus:
		sys.exit(f"ERREUR : moqueries pour des PNJ absents du dump : {sorted(inconnus)}")
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"{len(sortie)} PNJ modifiés (dump {nom_dump}) → {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
	main()
