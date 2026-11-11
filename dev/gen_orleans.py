"""Orléans en jeu : quatre temples-donjons, deux portails transversaux, Charles d'Orléans,
l'Architecte en résidence, le mandat d'Agnan — UN fichier à importer (CLAUDE.md §18).

Lore : docs/lore/cites/20261111_histoire_d_orleans.md (arbitrage de l'Auteur, 11/11/2026).
- `lieu:orleans` existe déjà (grille, guilde du Relais de la Loire) : il n'est PAS réécrit ;
  les nouveaux lieux s'y raccrochent par des connexions sur des cases praticables de sa grille.
- Donjons (rangs d'Orléans, Auteur) : Saint-Loup = forêt (D), les Tourelles = l'aval de la Crue (C,
  réinfestée à chaque crue), Saint-Jean-le-Blanc = ciel (B), Sainte-Croix = la Croix (B).
  Grades : D 2-3, C 3-4, B 4-5 (même échelle que le puits de Chartres, rang B, 4-5).
- Agnan le Gabarrier (bureau, rang D d'Orléans) mandate les quatre donjons : son doc du dump est
  RELU et complété (mandat, donjons, Jeanne), jamais réécrit de mémoire (PUT complet, §11).
- Natiru (Petra, l'Urne) : seule sa réplique sur l'avant-Vague change — le seuil menait à Orléans
  (portail des deux crues, Auteur, 11/11).
- Transversaux : port du Châtelet → Lyon, porte de Bourgogne → Bruges, au rang A de Lutecia
  (Auteur : le joueur au rang A, comme le reste du monde). Aucun vers Lutecia.
- Cartes de combat : quadrillage DESSINÉ — la Croix et la Crue 60 × 33 (23 px), le ciel et la
  forêt 30 × 17 (46 px). Relevé en polygones à l'œil : première passe, à valider en jeu.

REJOUABLE : un `_id` déjà au dump est refusé, sauf les deux docs RELUS et complétés
(`MODIFIES`).

Usage : python dev/gen_orleans.py [--dump jsons/telluris-dump-….json] [--apercu]
Sortie : jsons/orleans_a_importer.json (+ aperçus des salles dans jsons/ avec --apercu)
"""

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_petra import (choix, connexion, grille_salle, noeud, peindre, peindre_polyligne,  # noqa: E402
	plus_proche, pnj_doc, zone_de)

SORTIE = os.path.join(ggi.DOSSIER_JSONS, "orleans_a_importer.json")
CITE, LUTECIA, LYON, BRUGES = "lieu:orleans", "lieu:lutecia", "lieu:lyon", "lieu:bruges"
AGNAN, NATIRU = "pnj:agnan_gabarrier", "pnj:templier_natiru_petra"
MODIFIES = (AGNAN, NATIRU)
GIVER = "bureau_maitre_guilde"

# Repères sur la carte d'Orléans (cases de 16 px ; la connexion prend la case praticable la plus proche).
REPERES = {
	"sainte_croix": (38, 20),        # parvis, au sud de la cathédrale
	"tourelles": (56, 33),           # bout sud du vieux pont
	"saint_jean_le_blanc": (74, 40), # rive gauche, à l'est du bourg du pont
	"saint_loup": (76, 8),           # dehors, à l'est, lisière de la forêt
	"chatelet": (52, 28),            # quais de la rive droite, porte du pont
	"bourgogne": (66, 18),           # porte est
}
DEPART_ORLEANS = (26, 36)            # case de la guilde : la zone praticable de la ville en part
# Arrivées des transversaux : (case de départ d'une zone connue = la guilde, repère visé).
ARRIVEES = {LYON: ((42, 28), (44, 24)), BRUGES: ((45, 8), (44, 26))}


def salle_id(nom: str) -> str:
	return f"lieu:orleans_donjon_{nom}"


def rang_min(rang: str) -> dict:
	return {"rang_min": {"cite": CITE, "rang": rang}}


def mandat(salle: str) -> dict:
	return {"quete_active": {"lieu": salle_id(salle), "types": ["chasse"], "giver_categorie": GIVER,
		"objectif_atteint": False}}


# ── Cartes de combat ──────────────────────────────────────────────────────────────────────
def rect(x1, y1, x2, y2):
	return ((x1, y1), (x2, y1), (x2, y2), (x1, y2))


SALLES = {
	# La Croix — 60 × 33 : lande praticable, murets de pierre sèche (difficiles), bornes et potence (0).
	"croix": {"dim": (60, 33), "base": 1,
		"eau": (),
		"murs": (rect(13.6, 2.6, 15, 4), rect(29.4, 2.6, 30.8, 4), rect(45.4, 2.6, 46.8, 4),
			rect(8.6, 15.4, 10, 17), rect(29.2, 15, 30.6, 17), rect(50.4, 15.4, 51.8, 17),
			rect(37.8, 6, 39, 9.4), rect(15.6, 22, 19.4, 24)),
		"obstacles": (rect(11, 18.6, 12.6, 20), rect(52.8, 7.4, 54, 9), rect(39, 7.6, 41.4, 8.8)),
		"lignes": (
			(((2, 10.2), (12.6, 10.2)), 3), (((12.6, 4.2), (28, 4.2)), 3), (((28, 4.2), (28, 13)), 3),
			(((13, 4.2), (13, 14)), 3), (((32.2, 4.2), (45, 4.2)), 3), (((32.2, 4.2), (32.2, 11.6)), 3),
			(((44.4, 4.2), (44.4, 13)), 3), (((37.4, 14.4), (48, 14.4)), 3), (((51.4, 4.2), (51.4, 13)), 3),
			(((10.4, 19.2), (23, 19.2)), 3), (((10.4, 19.2), (10.4, 32)), 3), (((26, 22.4), (26, 32)), 3),
			(((39.6, 19.2), (49.6, 19.2)), 3), (((34, 19.6), (34, 32)), 3), (((49, 19.6), (49, 32)), 3),
			(((0, 19.2), (6.4, 19.2)), 3),
			(((19, 14.2), (22.6, 10.8)), 5), (((38.2, 26.4), (44, 28.6), (50, 31.4)), 5)),
	},
	# Le ciel — 30 × 17 : les nuées tout autour (0, on n'y marche pas), plateaux, arches et pont de cordes.
	"ciel": {"dim": (30, 17), "base": 0,
		"sols": (
			((0, 10.5), (5, 10.3), (8, 10.5), (10.3, 11.3), (10.3, 13.5), (9.5, 17), (0, 17)),
			((6, 4), (13, 4.5), (13, 7.5), (10.5, 9), (6.5, 9), (6, 6.5)),
			((13.5, 7.2), (15.2, 5), (17.4, 4.8), (20.7, 5.9), (21.7, 7.2), (23.5, 6.5), (27.4, 7.2),
			 (28, 8.7), (26, 11.3), (23, 13), (19.6, 12.2), (16.5, 13), (13.9, 10.2)),
			((20.7, 1.5), (24.8, 1.3), (24.8, 4.1), (21.3, 4.8)),
			rect(12, 6.2, 14.5, 7.4),
			((21, 4.2), (22.6, 4.2), (22.2, 6.4), (20.8, 6.2))),
		"murs": (rect(14.5, 1.5, 17.5, 6.2),),
		"obstacles": (rect(23.5, 4.8, 27.8, 7.2), rect(0, 10.6, 2.2, 12)),
		"lignes": ((((9.8, 10.9), (12.5, 9.8), (15.2, 8.7)), 1),),
	},
	# L'aval de la Crue — 60 × 33 : eau brune (5), berges et bancs de sable (1), saules et barque (3), pieux (0).
	"crue": {"dim": (60, 33), "base": 5,
		"sols": (
			((0, 0), (36, 0), (34.8, 5.2), (26, 6.1), (17.4, 4.8), (7.4, 2.6), (0, 2.2)),
			((0, 2.6), (6.5, 3.5), (7, 7.4), (0, 8.5)),
			((0, 10.9), (4.8, 11.3), (5, 13.9), (0, 14.3)),
			((16, 14.3), (19.6, 11.7), (26, 10.9), (34, 12.2), (37, 15.2), (36, 18.7), (30.4, 21.7),
			 (21.7, 20.9), (16.5, 18.3)),
			((0, 18.3), (8.7, 19.1), (17.4, 24.3), (27.8, 26.1), (31.3, 27.8), (31.3, 33), (0, 33)),
			((31.3, 27.8), (39.1, 25.7), (50, 24.3), (60, 24.3), (60, 33), (31.3, 33)),
			((41.7, 0), (60, 0), (60, 13.9), (55.7, 13), (50, 9.6), (44.3, 7))),
		"murs": (rect(38.6, 5.6, 39.6, 6.6), rect(40.6, 5.6, 41.6, 6.6), rect(38.6, 8.6, 39.6, 9.6),
			rect(40.6, 8.6, 41.6, 9.6), rect(41.8, 8.8, 42.8, 9.8), rect(42.6, 10.2, 43.6, 11.2)),
		"obstacles": (rect(9.6, 2.6, 12, 5), rect(17.6, 0.6, 20, 2.6), rect(22, 0.6, 24.4, 2.6),
			rect(55.4, 4.6, 58, 7), rect(55.6, 9.4, 58, 11.6), rect(8.6, 12.2, 11.4, 14.6),
			rect(28, 19, 33, 21.7), rect(22.6, 13.2, 24.6, 15)),
	},
	# La forêt — 30 × 17 : clairière (1), troncs et rochers (0), ruisseau (5), ronces, souille et toiles (3).
	"foret": {"dim": (30, 17), "base": 1,
		"murs": (rect(0, 0, 2, 4.3), rect(18.5, 0, 20.7, 4.3), rect(25, 0, 27.2, 5.4), rect(0, 11, 1.5, 17),
			rect(12.8, 13, 14.8, 15.2), rect(14, 15.2, 16.3, 17), rect(23.5, 8.5, 26.7, 10.4),
			rect(27.4, 9.4, 30, 15.2)),
		"obstacles": (rect(17.2, 9.8, 19.1, 12.2), rect(6.3, 5.9, 10.9, 8.7), rect(20.7, 2.8, 25, 7.2),
			rect(25.4, 13.4, 27.4, 15.4)),
		"lignes": (
			(((3.7, 3), (7.7, 4.7), (11, 6.7), (13.3, 8.7), (15.2, 10), (16.3, 11.8), (17, 14.2), (17.4, 16.9)), 5),
			(((11.5, 9.8), (18.3, 4.8)), 3)),
	},
}


def grille(spec: dict) -> list:
	"""`grille_salle` de Petra, plus des SOLS (praticable sur fond infranchissable) et des
	tracés (murets, ruisseau, pont de cordes) à valeur donnée."""
	base = dict(spec)
	base.setdefault("base", 1)
	cells = grille_salle({k: v for k, v in base.items() if k not in ("sols", "lignes")})
	if spec.get("sols"):
		cells = [[spec["base"]] * spec["dim"][0] for _ in range(spec["dim"][1])]
		peindre(cells, spec["sols"], 1)
		peindre(cells, spec.get("eau", ()), 5)
		peindre(cells, spec.get("murs", ()), 0)
		peindre(cells, spec.get("obstacles", ()), 3)
	for trace, valeur in spec.get("lignes", ()):
		peindre_polyligne(cells, trace, valeur, demi=0.6)
	return cells


# ── Temples et donjons ────────────────────────────────────────────────────────────────────
# slug → lieu du temple, donjon, rang, grades, espèces, nombre de monstres, Templier.
TEMPLES = {
	"saint_loup": {"label": "Le temple de Saint-Loup", "image": "temple_orleans_saint_loup.jpg",
		"salle": "foret", "rang": "D", "grades": (2, 3), "nb": 3,
		"especes": ["espece:loup_geant", "espece:grand_sanglier", "espece:araignee_geante", "espece:homme_arbre"],
		"donjon": "La forêt de Saint-Loup",
		"description": "Derrière la palissade de Saint-Loup, une forêt sans fin dont les arbres sont plus grands "
			"que ceux du dehors. À la Vague, ce portail a changé de couleur ; quelques années plus tard, les bêtes "
			"en sont sorties jusqu'aux murs d'Orléans. C'était la première des vagues que Jeanne a brisées.",
		"salle_label": "La clairière de Saint-Loup", "tags": ["donjon", "foret"],
		"templier": "florent_d_illiers"},
	"tourelles": {"label": "Le temple des Tourelles", "image": "temple_orleans_tourelles.jpg",
		"salle": "crue", "rang": "C", "grades": (3, 4), "nb": 4,
		"especes": ["espece:marid", "espece:ondin", "espece:naiade", "espece:serpent_geant"],
		"donjon": "La Crue des Tourelles",
		"description": "Sous une arche murée du vieux pont, l'eau remonte contre le courant. Le seuil ouvre sur "
			"l'aval d'un fleuve en crue qui n'est pas la Loire : le même monde que le tombeau de l'Urne, à Petra, "
			"dit-on, dont ce portail fut le frère avant la Vague. Chaque crue ramène ses créatures.",
		"salle_label": "L'aval de la Crue", "tags": ["donjon", "fleuve", "eau"],
		"templier": "raoul_de_gaucourt", "reinfestation": True},
	"saint_jean_le_blanc": {"label": "Le temple de Saint-Jean-le-Blanc",
		"image": "temple_orleans_saint_jean_le_blanc.jpg",
		"salle": "ciel", "rang": "B", "grades": (4, 5), "nb": 4,
		"especes": ["espece:harpie", "espece:wyvern", "espece:griffon", "espece:gargouille"],
		"donjon": "Le ciel de Saint-Jean-le-Blanc",
		"description": "Au sommet de la tour sans toit de Saint-Jean-le-Blanc, les nuées tournent. Le seuil ouvre "
			"sur des falaises suspendues au-dessus d'une mer de nuages, d'où sortirent les nuées volantes que "
			"Jeanne abattit de sa Lance. Les Paladins s'y exercent encore au-dessus de la Loire.",
		"salle_label": "Les falaises des nuées", "tags": ["donjon", "montagne", "ciel"],
		"templier": "archambaud_de_villars"},
	"sainte_croix": {"label": "La cathédrale Sainte-Croix", "image": "temple_orleans_sainte_croix.jpg",
		"salle": "croix", "rang": "B", "grades": (4, 5), "nb": 5,
		"especes": ["espece:doppleganger", "espece:revenant", "espece:spectre", "espece:demon_mineur"],
		"donjon": "La Croix",
		"description": "Sous la cathédrale Sainte-Croix, un portail du cœur de la ville est devenu donjon à la "
			"Vague. Il ouvre sur la Croix : un carrefour de chemins qui ne mènent nulle part, où chaque borne "
			"ressemble à la précédente et où l'on croise parfois quelqu'un qui vous ressemble.",
		"salle_label": "La Croix", "tags": ["donjon", "lande", "brume"],
		"templier": "jamet_du_tillay"},
}

# Templiers : (nom, Lignée, portrait réemployé, présentation, porte, lore).
TEMPLIERS = {
	"florent_d_illiers": ("Florent d'Illiers", "nain", "templier_nain_m_garde_temple01.png",
		"Templier nain de la garde de Saint-Loup. Fils de forestier, il connaît les bêtes du dehors et se méfie "
		"de celles du dedans, qui sont toujours un peu plus grandes.",
		"Devant la palissade de Saint-Loup, des chasseurs déchargent une peau de loup trop grande pour être "
		"vraie. {pnj}, un nain en haubert, note le poids sur une tablette. « Halte. Derrière, les arbres "
		"poussent plus vite que les hommes ne les coupent. »",
		"« À la Vague, ce portail a changé de couleur. Quelques années après, les bêtes sont sorties, des loups "
		"grands comme des chevaux, des sangliers qui renversaient les charrettes. Elles sont venues jusqu'aux "
		"murs. » Il tapote la palissade. « C'est ici que Jeanne a commencé. Ma famille dit qu'elle était d'un "
		"village des marches. La moitié d'Orléans dit autre chose. Moi, je dis qu'elle savait où frapper. »"),
	"raoul_de_gaucourt": ("Raoul de Gaucourt", "humain", "templier_humain_m_garde_temple01.png",
		"Templier de la garde des Tourelles, au bout du vieux pont. Il porte le nom d'un gouverneur des temps "
		"de Jeanne, et compte les crues de la Loire comme celles de l'autre côté.",
		"Sur le tablier du vieux pont, une muraille neuve ferme l'accès des Tourelles ; sous une arche murée, "
		"l'eau tourne d'une couleur plus sombre que le fleuve. {pnj}, en haubert taché de limon, garde la "
		"poterne. « Halte. Ici, l'eau remonte. »",
		"« Les Tourelles, c'est le dernier foyer que Jeanne a pris. On fête encore le jour, le 8 mai, sur ce "
		"pont. » Il regarde l'arche murée. « Derrière, un fleuve en crue, et des marids qui la mènent. Les "
		"Architectes disent que c'est le même monde qu'au tombeau de l'Urne, à Petra : avant la Vague, ce seuil "
		"y menait. Le vieux Charles dit qu'il a vu la source, là-bas. Moi, j'ai vu ce qui en remonte. »"),
	"archambaud_de_villars": ("Archambaud de Villars", "ogre", "templier_ogre_m_garde_temple01.jpg",
		"Templier ogre de la garde de Saint-Jean-le-Blanc. Il partage ses murs avec les Paladins du guet, qui "
		"regardent le ciel pendant qu'il regarde la porte.",
		"Sous la tour sans toit de Saint-Jean-le-Blanc, des plumes grandes comme des rames jonchent la cour. "
		"{pnj}, un ogre aux épaules couvertes de mailles, garde la poterne sans lever les yeux vers les nuées. "
		"« Halte. Ce qui descend de là-haut ne s'annonce pas. »",
		"« Les nuées sont sorties d'ici. Elles plongeaient sur les quais, sur les gabarres, sur le bétail. » "
		"Il désigne les terrasses où guettent les Paladins. « Jeanne les a abattues avec un trait que personne "
		"ne savait lancer : le Rayon, qu'on apprenait dans les livres, devenu Lance. Elle l'a appris aux "
		"Paladins de Lutecia, et ceux de Montmartre le transmettent encore de maître à élève. »"),
	"jamet_du_tillay": ("Jamet du Tillay", "ogre", "templier_ogre_m_garde_temple02.jpg",
		"Templier ogre de la garde de Sainte-Croix. Il ne quitte pas des yeux la borne du parvis, comme s'il "
		"craignait qu'elle change de place.",
		"Les portes de la cathédrale Sainte-Croix sont closes et barrées ; seule la poterne du parvis s'ouvre. "
		"{pnj}, un ogre en haubert, se tient près de la borne où quatre chemins s'effacent après quelques pas. "
		"« Halte. Ne suivez aucun de ces chemins. »",
		"« Ce portail était au cœur de la ville avant la cathédrale. À la Vague, il a tourné, mais il n'a pas "
		"débordé comme les autres. On a bâti Sainte-Croix autour, après Jeanne. » Il baisse la voix. « Derrière, "
		"des chemins qui se croisent et ne mènent nulle part. Ceux qui en reviennent disent qu'ils ont croisé "
		"quelqu'un qui leur ressemblait. Certains ne savent plus très bien lequel des deux est revenu. »"),
}


def templier(slug: str, temple: dict) -> dict:
	nom, race, portrait, description, porte, lore = TEMPLIERS[slug]
	rang = temple["rang"]
	consigne = f"« Un mandat de la Guilde, et le rang {rang} d'Orléans. Agnan délivre l'un, le comptoir inscrit l'autre. » "
	accueil = [
		choix("passer", "« J'ai un mandat de la Guilde. »", condition={"acces_ouvrable": True},
			action={"service": "acces", "op": "passer"}),
		choix("accompli", "« C'est fait. Ce qui commandait est tombé. »", "acces_accompli", {"acces_accompli": True}),
		choix("pourquoi", "« Pourquoi cette porte est-elle fermée ? »", "acces_refus",
			{"acces_refuse": True, "acces_libere": False}),
		choix("pourquoi_libre", "« Pourquoi cette porte est-elle fermée ? »", "acces_refus_libre",
			{"acces_refuse": True, "acces_libere": True}),
	]
	noeuds = {
		"lore": noeud(lore, choix("retour", "Revenir.", "accueil")),
		"acces_ouvre": noeud(
			"{pnj} compare le sceau de la Guilde à son registre et trace un trait à côté de votre nom. « Mandat "
			"enregistré. » La poterne s'ouvre sur {portail}. « Revenez par où vous êtes entré, ou ne revenez pas. »",
			choix("fin", "Franchir le seuil.")),
		"acces_refus": noeud("« Pas de mandat, pas de passage. » " + consigne, choix("fin", "S'écarter.")),
		"acces_refus_libre": noeud(
			"« Ce qui commandait là-dessous est tombé, et la porte reste close jusqu'au prochain mandat. » " + consigne,
			choix("fin", "S'écarter.")),
		"acces_accompli": {**noeud(
			"{pnj} referme son registre. « On l'a senti, d'ici. Puis plus rien — c'est à ce silence qu'on reconnaît "
			"le travail fait. » Il montre le chemin du Relais de la Loire. « Portez votre rapport à Agnan. C'est lui "
			"qui paie. »", choix("fin", "« J'y vais. »")), "relation": {"delta": 1}},
	}
	if temple.get("reinfestation"):
		accueil.append(choix("remonte", "« L'eau est remontée ? »", "remonte", {"acces_reinfeste": True}))
		noeuds["remonte"] = noeud(
			"« Elle remonte toujours. » {pnj} montre la marque de la dernière crue sur la pile du pont. « Les bêtes "
			"sont revenues avec l'eau. C'est la loi de cette porte : on la vide, elle se remplit. »",
			choix("retour", "Revenir.", "accueil"))
	accueil += [choix("lore", "« Qu'y a-t-il derrière ? »", "lore"), choix("rien", "« Rien. Je passais. »")]
	noeuds["accueil"] = noeud(porte, *accueil)
	return pnj_doc(f"templier_{slug}_orleans", nom, race, "garde", portrait, description, noeuds,
		{"acces": {"lieu": salle_id(temple["salle"]), "noeuds": {"ouvre": "acces_ouvre", "refus": "acces_refus"}}})


# ── PNJ propres à Orléans ─────────────────────────────────────────────────────────────────
def charles() -> dict:
	return pnj_doc("charles_d_orleans", "Charles d'Orléans", "humain", "noble", "pnj_humain_m_charles_d_orleans01.jpg",
		"Héritier d'une vieille famille d'Orléans, sans charge ni siège au conseil. Poète. Emporté par la Crue "
		"des Tourelles, il en est revenu vingt-cinq ans plus tard, le manteau encore taché de limon. Il passe ses "
		"journées sur le pont à regarder l'eau.",
		{
			"accueil": noeud(
				"Un homme âgé, mince, en houppelande de velours passé, regarde l'arche murée des Tourelles comme on "
				"regarde une porte qui va s'ouvrir. Il se retourne lentement. « Pardonnez-moi. On me dit que je fixe "
				"l'eau trop longtemps. On a sans doute raison. » Il serre contre lui une liasse de feuillets. "
				"« {pnj}. Ou ce qu'il en reste. »",
				choix("crue", "« On dit que vous êtes revenu de la Crue. »", "crue"),
				choix("source", "« Qu'avez-vous vu, là-bas ? »", "source"),
				choix("jeanne", "« Parlez-moi de Jeanne. »", "jeanne"),
				choix("gilles", "« Et ses compagnons ? »", "gilles"),
				choix("poeme", "« Que contiennent ces feuillets ? »", "poeme"),
				choix("rien", "« Rien. Je vous laisse à votre fleuve. »")),
			"crue": noeud(
				"« Une crue, un soir. Le pont, l'arche, et puis l'eau qui m'a pris par les chevilles. » Il sourit sans "
				"joie. « Vingt-cinq ans. Pour moi, c'était une longue marche le long d'un fleuve qui ne finissait pas. "
				"Quand je suis ressorti, mes bagues étaient trop grandes et ma maison vendue. » Il tourne une bague "
				"sur son doigt maigre. « Je ne me plains pas. Peu en reviennent. »",
				choix("retour", "Une autre question…", "accueil"), choix("fin", "« Je suis désolé. »")),
			"source": noeud(
				"« J'ai remonté le fleuve. Longtemps. À la fin, il n'y avait plus de rives, mais des falaises de "
				"pierre rose, une gorge étroite, et l'eau qui en jaillissait comme d'une urne renversée. » Il baisse "
				"la voix. « Les Architectes disent que c'est Petra, de l'autre côté du monde. La Guilde dit que je "
				"radote et que personne n'a jamais traversé la Crue d'un seuil à l'autre. » Il hausse les épaules. "
				"« Je ne suis pas sorti à Petra. Je suis sorti ici. Alors qui sait ? »",
				choix("retour", "Une autre question…", "accueil"), choix("fin", "« Personne, sans doute. »")),
			"jeanne": noeud(
				"« Une paladine sortie de nulle part, à une époque où les portails d'Orléans vomissaient des bêtes, "
				"des nuées et des créatures du fleuve. » Il compte sur ses doigts. « Les uns disent qu'elle était "
				"bergère dans un village des marches. D'autres, qu'elle obéissait à ses voix. D'autres encore, "
				"qu'elle est venue d'un portail et qu'elle y est retournée. » Il regarde le pont. « Ce qu'on sait, "
				"c'est qu'elle a pris les Tourelles un 8 mai, qu'elle a donné la Lance à Lutecia, et qu'un jour elle "
				"est repartie comme elle était venue. Personne ne sait où. »",
				choix("retour", "Une autre question…", "accueil"), choix("fin", "« Merci. »")),
			"gilles": noeud(
				"« Dunois, le Bâtard, qui tenait la ville quand elle est arrivée. La Hire et Xaintrailles, qui "
				"juraient comme des bateliers. » Il hésite. « Et Gilles de Rais. On raconte qu'après elle il a mal "
				"tourné, qu'il serait le Barbe-Bleue des contes. On raconte beaucoup. Rien n'a jamais été prouvé, et "
				"il y a encore des familles pour le défendre. » Il pince les lèvres. « Je n'aime pas qu'on juge les "
				"absents. J'en ai été un. »",
				choix("retour", "Une autre question…", "accueil"), choix("fin", "« Je comprends. »")),
			"poeme": noeud(
				"Il déplie un feuillet couvert d'une écriture fine et lit à mi-voix : « Le temps a laissié son manteau "
				"/ De vent, de froidure et de pluye, / Et s'est vestu de brouderie, / De soleil luyant, cler et "
				"beau. » Il replie la page. « Je l'ai écrit en remontant la Crue, pour ne pas oublier le printemps. "
				"Là-bas, il pleut toujours. »",
				choix("retour", "Une autre question…", "accueil"), choix("fin", "« C'est beau. »")),
		})


def architecte() -> dict:
	return pnj_doc("ermengarde_des_arches", "Maîtresse Ermengarde des Arches", "nain", "architecte",
		"architecte_nain_f_orleans01.jpg",
		"Architecte des portails de l'institut de Lutecia, en résidence à Orléans au port du Châtelet, selon le "
		"pacte de Jeanne. Une naine aux tresses rousses et aux lunettes relevées, qui parle au portail de Lyon "
		"comme à une mule têtue.",
		{
			"accueil": noeud(
				"Sous la halle du port, une naine en tablier de cuir règle la monture d'un cristal jaune au pied de "
				"l'arche. Le voile hésite entre le bleu et le jaune. « Pas maintenant, ma belle… » Elle s'aperçoit "
				"de votre présence. « Pas vous, le portail. {pnj}, de l'institut de Lutecia. Vous passez ou vous "
				"regardez ? »",
				choix("lyon", "« Ce portail mène à Lyon ? »", "lyon"),
				choix("pacte", "« Que fait une Architecte de Lutecia à Orléans ? »", "pacte"),
				choix("eaux", "« Orléans n'a pas ses propres Architectes ? »", "eaux"),
				choix("rien", "« Je regardais. »")),
			"lyon": noeud(
				"« À Lyon, oui : la Loire jusqu'au Rhône, et la mer du Midi sans prendre la mer. » Elle tapote le "
				"cristal. « Il a été bâti par les héritiers des frères, bien avant la Vague. Depuis, il vire avec les "
				"crues : sa couleur hésite, et il faut des cristaux jaunes pour le tenir. Celui de Bourgogne, vers "
				"Bruges, est plus sage. » Elle ajoute : « On ne le franchit qu'avec le rang A de Lutecia. Ce n'est pas "
				"moi qui le décide, c'est l'institut. »",
				choix("retour", "Une autre question…", "accueil"), choix("fin", "« Merci. »")),
			"pacte": noeud(
				"« Le pacte de Jeanne. Lutecia fournit les Architectes, Orléans ouvre ses voies : le fleuve, ce "
				"portail, celui de Bruges. » Elle essuie ses lunettes. « Personne n'y a jamais mis de couronne ni de "
				"mariage. Juste un intérêt commun, qui dure depuis des siècles. C'est plus solide que la plupart des "
				"mariages que je connais. »",
				choix("retour", "Une autre question…", "accueil"), choix("fin", "« Je vois. »")),
			"eaux": noeud(
				"« L'École des Turcies ? Les meilleurs bâtisseurs de levées et de fondations noyées que je "
				"connaisse. Elle a le veto sur l'eau au conseil, et personne ne s'y frotte. » Elle sourit. « Mais "
				"les portails, c'est mon métier, pas le leur. Elles échangent leurs maîtres avec les gardiens des "
				"sources de Petra : deux écoles sœurs, dit-on, depuis le temps où un portail les reliait. »",
				choix("retour", "Une autre question…", "accueil"), choix("fin", "« Merci. »")),
		})


def agnan(dump_doc: dict) -> dict:
	"""Le doc du dump, RELU : le mandat devient la commission des quatre donjons, + deux répliques."""
	doc = {k: v for k, v in copy.deepcopy(dump_doc).items() if k != "_rev"}
	noeuds = doc["dialogue"]["noeuds"]
	accueil = noeuds["accueil"]
	anciens = [c for c in accueil["choix"] if c["id"] != "mandat"]
	commission = [
		choix("commission", "« Vous avez un mandat pour moi ? »", "commission_propose", {"commission_offerte": True}),
		choix("commission_rapport", "« C'est fait. Ce qui commandait là-dessous est tombé. »",
			condition={"commission_a_rapporter": True}, action={"service": "commission", "op": "rapporter"}),
		choix("commission_relance", "« Où en est mon mandat ? »", "commission_relance", {"commission_en_cours": True}),
		choix("mandat", "« Vous avez un mandat pour moi ? »", "aucun_mandat",
			{"commission_offerte": False, "commission_en_cours": False, "commission_a_rapporter": False}),
	]
	extra = [choix("donjons", "« Que gardent les Templiers d'Orléans ? »", "donjons"),
		choix("jeanne", "« On parle beaucoup de Jeanne, ici. »", "jeanne")]
	rien = [c for c in anciens if c["id"] == "rien"]
	accueil["choix"] = commission + [c for c in anciens if c["id"] != "rien"] + extra + rien
	noeuds["aucun_mandat"]["texte"] = (
		"« Rien pour vous aujourd'hui. » Il repose sa maquette. « Je mandate pour les quatre temples : Saint-Loup "
		"au rang D, les Tourelles au rang C, Saint-Jean-le-Blanc et Sainte-Croix au rang B. Faites inscrire votre "
		"rang au comptoir, ou gagnez-le. Les temples ne vont nulle part. »")
	noeuds.update({
		"commission_propose": noeud(
			"Il sort un mandat scellé d'un coffre, à côté de la maquette. « Une commission d'éradication. Les "
			"Templiers me signalent {lieu}. Ce qui y commande : un {espece} hors du commun. Abattez-le et revenez me "
			"le dire. {xp} points d'expérience et {prime} pièces de cuivre. Le Templier de la porte lira ce sceau, "
			"pas votre nom. »",
			choix("details", "« Qui garde les portes ? »", "commission_details"),
			choix("accepter", "« Donnez-moi ce mandat. »", action={"service": "commission", "op": "accepter"}),
			choix("refuser", "« Pas celui-là. »", "accueil")),
		"commission_details": noeud(
			"« Florent d'Illiers à Saint-Loup, Raoul de Gaucourt aux Tourelles, Archambaud de Villars à "
			"Saint-Jean-le-Blanc, Jamet du Tillay à Sainte-Croix. Un mandat, et le rang que le temple exige : D, C, "
			"B et B. » Il hausse une épaule énorme. « Je ne vous propose que ce que vous pouvez franchir. »",
			choix("accepter", "« Donnez-moi ce mandat. »", action={"service": "commission", "op": "accepter"}),
			choix("refuser", "« Je réfléchis. »", "accueil")),
		"commission_accepte": noeud(
			"Il presse le sceau dans la cire avec son pouce, qui couvre tout le cachet. « {espece}, dans {lieu}. "
			"Et ne faites pas comme moi : ne vous endettez pas en route. »", choix("ok", "« Ce sera fait. »")),
		"commission_relance": noeud(
			"« {espece}, dans {lieu}. Le mandat court toujours, {prenom}. Le Templier compte les jours, et moi je "
			"compte le cuivre. »", choix("ok", "« J'y retourne. »")),
		"commission_rapporte": noeud(
			"Il vous écoute jusqu'au bout, puis pousse vers vous {prime} pièces de cuivre ; {xp} points sont portés à "
			"votre nom. « Une cargaison livrée entière. C'est tout ce qu'on demande, sur ce fleuve. »",
			choix("ok", "« Merci, maître. »")),
		"donjons": noeud(
			"« Quatre portails ont tourné à la Vague. » Il les compte sur ses doigts épais. « La forêt de Saint-Loup. "
			"Le fleuve en crue sous les Tourelles. Le ciel de Saint-Jean-le-Blanc. Et la Croix, sous la cathédrale, "
			"qui n'a jamais débordé, ce qui m'inquiète plus que le reste. » Il grogne. « Les trois premiers ont "
			"failli prendre la ville. C'est Jeanne qui les a fermés, foyer par foyer. Depuis, les Templiers les "
			"gardent, et moi je paie ceux qui les vident. »",
			choix("retour", "Une autre question…", "accueil"), choix("fin", "« Merci. »")),
		"jeanne": noeud(
			"« On ne parle que d'elle le 8 mai, et le reste de l'année on en parle quand même. » Il sourit. « Elle a "
			"pris les Tourelles, donné la Lance aux Paladins de Lutecia, et signé un pacte qui tient encore : leurs "
			"Architectes, nos voies. Le conseil n'a jamais eu de duc depuis, juste des marchands, l'École des "
			"Turcies qui a le dernier mot sur l'eau, et le maître de la Guilde. » Il se désigne. « Moi, donc. Ce qui "
			"ne m'a toujours pas donné un tabouret à ma taille. »",
			choix("retour", "Une autre question…", "accueil"), choix("fin", "« Merci. »")),
	})
	doc["services"] = {**(doc.get("services") or {}), "commission": {
		"donjons": [f"donjon:orleans_{t}" for t in TEMPLES],
		"noeuds": {"accepte": "commission_accepte", "rapporte": "commission_rapporte"}}}
	return doc


def natiru(dump_doc: dict) -> dict:
	doc = {k: v for k, v in copy.deepcopy(dump_doc).items() if k != "_rev"}
	lore = doc["dialogue"]["noeuds"]["lore"]
	ancien = "« Avant la Vague, on y menait les caravanes vers une cité de l'autre côté du désert. »"
	nouveau = ("« Avant la Vague, ce seuil menait à Orléans, une cité de bateliers sur un fleuve du Couchant : "
		"nos gardiens des sources y échangeaient leurs citernes contre leurs levées. »")
	if ancien in lore["texte"]:
		lore["texte"] = lore["texte"].replace(ancien, nouveau)
	elif nouveau not in lore["texte"]:
		raise ValueError("réplique de Natiru introuvable : relire le dump")
	return doc


# ── Assemblage ────────────────────────────────────────────────────────────────────────────
PORTAILS = {
	"chatelet": {"label": "Le port du Châtelet", "image": "orleans_chatelet_portail.jpg", "vers": LYON,
		"texte": "Sous la halle du port du Châtelet, une arche ancienne aux motifs usés encadre un voile dont la "
			"couleur hésite entre le bleu et le jaune. Des cristaux jaunes le tiennent ; il mène à Lyon, où la "
			"Saône rejoint le Rhône.",
		"arrivee": "Orléans — par le port du Châtelet",
		"pnj": [{"character": "pnj:ermengarde_des_arches", "nom": "Maîtresse Ermengarde des Arches",
			"portrait": "architecte_nain_f_orleans01.jpg", "probabilite": 1,
			"description": "Une naine en tablier de cuir règle un cristal jaune au pied de l'arche."}]},
	"bourgogne": {"label": "La porte de Bourgogne", "image": "orleans_bourgogne_portail.jpg", "vers": BRUGES,
		"texte": "Dans la cour de la porte de Bourgogne, entre deux tours rondes, un voile d'un bleu limpide tient "
			"sans faiblir. Les charrettes de grain et de vin y partent pour Bruges ; les draps de Flandre en "
			"arrivent.",
		"arrivee": "Orléans — par la porte de Bourgogne"},
}


def docs_orleans(par_id: dict, erreurs: list) -> list:
	cite = par_id[CITE]
	zone = zone_de(cite["cells"], DEPART_ORLEANS, cite.get("nav"))
	if not zone:
		erreurs.append(f"{CITE} : case de départ {DEPART_ORLEANS} non praticable")
		return []
	prises = set()

	def case(slug):
		c = plus_proche(zone, REPERES[slug], prises)
		prises.add(c)
		return c

	docs = []
	porte_monde = {"refus": "Un Architecte vous arrête au bord du seuil : on ne le franchit qu'avec le rang A de la "
		"Guilde de Lutecia.", "cycle": 1, "conditions": [{"rang_min": {"cite": LUTECIA, "rang": "A"}}]}
	for slug, p in PORTAILS.items():
		lid = f"lieu:orleans_{slug}"
		doc = {"_id": lid, "type": "lieu", "label": p["label"], "image": p["image"], "categorie": "portail",
			"sous_categorie": "temple", "lieu_parent": CITE, "texte": p["texte"], "acces": dict(porte_monde)}
		if p.get("pnj"):
			doc["pnj"] = p["pnj"]
		docs.append(doc)
		docs.append(connexion(f"link:orleans_to_{slug}", CITE, case(slug), lid, (0, 0), "temple",
			"ressortir dans la cité", f"entrer dans {p['label'][0].lower() + p['label'][1:]}"))
		vers = par_id[p["vers"]]
		depart, repere = ARRIVEES[p["vers"]]
		z = zone_de(vers["cells"], depart, vers.get("nav"))
		if not z:
			erreurs.append(f"{p['vers']} : case de départ {depart} non praticable")
			continue
		docs.append(connexion(f"link:orleans_{slug}_to_{p['vers'].split(':', 1)[1]}", lid, (0, 0), p["vers"],
			plus_proche(z, repere), "portail", p["arrivee"], f"franchir le seuil vers {vers.get('label')}"))
	docs.append(architecte())

	for slug, t in TEMPLES.items():
		tid = f"lieu:orleans_temple_{slug}"
		tpl = templier(t["templier"], t)
		pnj = [{"character": tpl["_id"], "nom": tpl["nom"], "portrait": tpl["portrait"], "probabilite": 1,
			"description": tpl["description"].split(".")[0] + "."}]
		if slug == "tourelles":
			pnj.append({"character": "pnj:charles_d_orleans", "nom": "Charles d'Orléans",
				"portrait": "pnj_humain_m_charles_d_orleans01.jpg", "probabilite": 0.7,
				"description": "Un vieil homme en velours passé regarde l'arche murée, une liasse de feuillets contre lui."})
		docs.append({"_id": tid, "type": "lieu", "label": t["label"], "image": t["image"],
			"categorie": "temple_portail", "sous_categorie": "temple", "lieu_parent": CITE, "pnj": pnj})
		docs.append(tpl)
		docs.append(connexion(f"link:orleans_to_temple_{slug}", CITE, case(slug), tid, (0, 0), "temple_portail",
			"ressortir dans la cité", "entrer dans le temple"))
		salle = t["salle"]
		docs.append({"_id": f"donjon:orleans_{slug}", "type": "donjon", "nom": t["donjon"],
			"description": t["description"], "portail": tid, "niveau_min": t["grades"][0], "niveau_max": t["grades"][1],
			"battle_maps": [{"lieu": salle_id(salle), "especes": list(t["especes"]), "nb_monstres": t["nb"]}]})
		cells = grille(SALLES[salle])
		lieu = {"_id": salle_id(salle), "type": "lieu", "label": t["salle_label"],
			"image": f"orleans_donjon_{salle}.jpg", "categorie": "battle_map",
			"dimensions": {"x": len(cells[0]), "y": len(cells)}, "cells": cells, "nav": {}, "tags": list(t["tags"]),
			"acces": {"gardien": tpl["_id"],
				"refus": f"{tpl['nom']} barre le seuil : il faut un mandat de la Guilde d'Orléans et le rang {t['rang']}.",
				"cycle": 1, "conditions": [mandat(salle), rang_min(t["rang"])]}}
		if t.get("reinfestation"):
			lieu["reinfestation"] = True
		praticables = sum(v in (1, 3, 5) for l in cells for v in l)
		if praticables < 40:
			erreurs.append(f"{salle_id(salle)} : {praticables} cases praticables seulement")
		docs.append(lieu)
	docs.append(charles())
	docs.append(agnan(par_id[AGNAN]))
	docs.append(natiru(par_id[NATIRU]))
	return docs


def main() -> int:
	args = sys.argv[1:]
	chemin_dump = args[args.index("--dump") + 1] if "--dump" in args else None
	par_id = {d.get("_id"): d for d in ggi.charger_dump(chemin_dump)}
	manquants = [i for i in (CITE, LUTECIA, LYON, BRUGES, AGNAN, NATIRU) + tuple(
		e for t in TEMPLES.values() for e in t["especes"]) if i not in par_id]
	if manquants:
		print("✗ absents du dump : " + ", ".join(manquants))
		return 1
	erreurs = []
	sortie = docs_orleans(par_id, erreurs)
	ids = [d["_id"] for d in sortie]
	erreurs += [f"_id en double : {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
	deja = [i for i in ids if i in par_id and i not in MODIFIES]
	if deja:
		erreurs.append("déjà en base : " + ", ".join(deja))
	if erreurs:
		print("✗ " + "\n✗ ".join(erreurs))
		return 1
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	if "--apercu" in args:
		for nom in SALLES:
			d = next(x for x in sortie if x["_id"] == salle_id(nom))
			ggi.ecrire_apercu(ggi.trouver_image(d["image"]), d["cells"],
				os.path.join(ggi.DOSSIER_JSONS, f"orleans_{nom}_grille_apercu.png"))
	compte = {}
	for d in sortie:
		t = d["_id"].split(":", 1)[0]
		compte[t] = compte.get(t, 0) + 1
	print(" · ".join(f"{n} {t}" for t, n in sorted(compte.items())) + f" → {os.path.relpath(SORTIE, ggi.RACINE)}"
		+ f" (relus et complétés : {', '.join(MODIFIES)})")
	return 0


if __name__ == "__main__":
	sys.exit(main())
