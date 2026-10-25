"""Les cinq portes de la Chapelle Palatine d'Aix-la-Chapelle en jeu : à chaque SORTIE, un temple
et un Templier gardien — UN fichier à importer (CLAUDE.md §18).

Lore : docs/lore/cites/20260824_decrire_aix_la_chapelle.md et docs/lore/systemes/20260826_completer_le_tableau.md
(Auteur) — cinq portes en pentagramme, œuvre d'un frère venu en Europe, à DESTINATION FIXE,
intactes après la Vague : Sydney, Tokyo, Teotihuacan, Pichao (Machu Picchu), Abou Simbel.
Les fenêtres de `towns/chapelle_palatine.jpg` fixent ce qu'on voit de l'autre côté : falaises
ocre, toits de bois sous les cerisiers, pyramide au bout d'une allée, terrasses dans les nuages,
colosses assis au bord d'un fleuve.

- Portails : `connection` `metadata.type == "portail"` chapelle ↔ temple (le tableau des seuils
  de Notre-Dame les prend d'office, `utils/portails.py`). Nœuds sans grille : `pos` [0, 0].
- Temples : `categorie: "portail"`, `sous_categorie: "temple"` (forme d'ad-Deir et de la Khazneh),
  barrière `acces` rang A de Lutecia sur le TEMPLE (destination ; aucune barrière sur la chapelle,
  dont la gardienne parle à tous). Un Templier par temple (dialogue seul, aucun service).
- Cité d'arrivée : connexion `temple` temple ↔ cité, case relevée sur la carte (`REPERES`), la
  plus proche praticable dans la plus grande zone. Pichao n'a pas de `lieu:*` : son temple
  n'a que la porte (cul-de-sac assumé, à relier quand la cité existera).

REJOUABLE : un `_id` déjà au dump est signalé et le fichier n'est pas écrit (PUT complet, §11).

Usage : python dev/gen_portails_aix.py [--dump jsons/telluris-dump-….json]
Sortie : jsons/portails_aix_a_importer.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dev import gen_grille_image as ggi  # noqa: E402
from dev.gen_petra import choix, connexion, noeud, plus_proche, pnj_doc, zone_de  # noqa: E402

SORTIE = os.path.join(ggi.DOSSIER_JSONS, "portails_aix_a_importer.json")
CHAPELLE, LUTECIA = "lieu:chapelle_palatine", "lieu:lutecia"
ACCES = {"refus": "Un Templier vous arrête au bord du seuil : on ne le franchit qu'avec le rang A de la "
	"Guilde de Lutecia.", "cycle": 1, "conditions": [{"rang_min": {"cite": LUTECIA, "rang": "A"}}]}
RETOUR = choix("retour", "Une autre question…", "accueil")

# Repère de chaque temple sur la carte de sa cité (cases de 16 px) : Sensō-ji = la pagode au
# nord-est du château ; Serpent à plumes = la Ciudadela, place carrée à l'est de l'allée ;
# Sydney = les falaises de grès à l'entrée de la baie ; Abou Simbel = la petite porte au pied
# de la falaise, à gauche du Grand Temple.
REPERES = {"lieu:sydney": (70, 25), "lieu:tokyo": (53, 16), "lieu:teotihuacan": (62, 26),
	"lieu:abou_simbel": (13, 19)}

TEMPLES = [
	{
		"slug": "sydney", "cite": "lieu:sydney", "porte": "la porte de Sydney",
		"lieu": "lieu:sanctuaire_de_baiame", "label": "Le Sanctuaire de Baiame",
		"image": "sanctuaire_de_baiame_sydney.jpg",
		"texte": "Sur le promontoire de grès ocre qui garde l'entrée de la baie, la roche plate est couverte de "
			"gravures : des baleines, des poissons, des chasseurs, et une grande silhouette aux bras ouverts. "
			"Les Templiers ont élevé autour une enceinte basse de pierre sèche, sans toit : le ciel en est la "
			"voûte. Au centre, une arche de grès nu encadre un voile de lumière tranquille — la porte d'Aix.",
		"templier": ("templiere_barangaroo_sydney", "Barangaroo", "humain", "templier_humain_f_sydney01.jpg",
			"Templière du Sanctuaire de Baiame, gardienne de la porte d'Aix à Sydney. Pêcheuse avant d'être "
			"Templière, elle lit la mer mieux que les registres, et ne laisse personne marcher sur les gravures."),
		"accueil": "Le vent de la mer couche l'herbe rase du promontoire. Au bord de l'enceinte de pierre "
			"sèche, une femme en manteau blanc, les pieds nus sur la roche gravée, enroule une ligne de pêche "
			"autour de son poignet. {pnj} vous regarde arriver par l'arche. « Vous venez de l'autre bout du "
			"monde. Marchez sur la pierre nue, pas sur les gravures : elles étaient là avant nous tous. »",
		"lore": "« La grande silhouette, c'est Baiame, le père du ciel. Les autres, personne ne s'accorde. » Elle "
			"désigne trois petites figures côte à côte. « Les anciens disent que ce sont les trois frères, et "
			"que l'un d'eux est parti d'ici pour aller poser les portes de l'autre côté du monde. Les "
			"Architectes d'Aix disent que la porte a été bâtie depuis là-bas, et que nos gravures n'y sont "
			"pour rien. Moi, je pêche ici depuis l'enfance : la porte n'a jamais bougé, et les gravures non "
			"plus. »",
		"cite_txt": "« La ville est derrière le promontoire, au bord de la baie. Suivez le sentier des "
			"falaises ; et regardez la mer en marchant, ce qui y nage ne reste pas toujours dedans. »",
	},
	{
		"slug": "tokyo", "cite": "lieu:tokyo", "porte": "la porte de Tokyo",
		"lieu": "lieu:temple_de_senso_ji", "label": "Le temple de Sensō-ji",
		"image": "temple_de_senso_ji_tokyo.jpg",
		"texte": "Au nord-est du château, au bord de la rivière Sumida, le temple de Sensō-ji dresse sa "
			"pagode à cinq toits au-dessus des cerisiers. Passé la grande porte de bois laqué de rouge, la "
			"salle principale ne garde ni autel ni statue visible : seulement, au fond, une arche de bois "
			"sombre où tremble un voile de lumière — la porte d'Aix.",
		"templier": ("templier_haji_no_nakatomo_tokyo", "Haji no Nakatomo", "nain",
			"templier_nain_m_tokyo01.jpg",
			"Templier gardien de Sensō-ji, à Tokyo. Il porte le nom du chef de village qui bâtit le premier "
			"sanctuaire, et balaie lui-même les pétales devant la porte d'Aix."),
		"accueil": "Des pétales de cerisier glissent sur le plancher ciré. Un nain en manteau blanc passé "
			"sur une armure de lamelles laquées pose son balai contre un pilier et s'incline, juste assez. "
			"« Bienvenue à Sensō-ji. Je suis {pnj}. Ôtez la poussière d'Aix de vos bottes : ici, on balaie "
			"deux fois par jour. »",
		"lore": "« Deux frères pêchaient dans la Sumida. Un matin, leur filet a remonté une petite statue d'or, "
			"pas plus haute qu'une main. Ils l'ont rejetée ; elle est revenue dans le filet, trois fois. » "
			"{pnj} sourit. « Le chef de leur village, celui dont je porte le nom, a bâti un sanctuaire autour. "
			"Bien plus tard, la porte s'est ouverte à côté de la statue. Les uns disent que la statue l'a "
			"appelée ; les autres, que la porte était là avant tout, et que c'est elle qui a mis la statue "
			"dans le filet. La statue, plus personne ne la montre. »",
		"cite_txt": "« Le château est au sud-ouest, derrière les douves. Ne traînez pas sur les quais à la nuit "
			"tombée : la baie a ses propres gardiens, et ils ne sont pas des nôtres. »",
	},
	{
		"slug": "teotihuacan", "cite": "lieu:teotihuacan", "porte": "la porte de Teotihuacan",
		"lieu": "lieu:temple_du_serpent_a_plumes", "label": "Le temple du Serpent à plumes",
		"image": "temple_du_serpent_a_plumes_teotihuacan.jpg",
		"texte": "Au fond de la Ciudadela, la grande place carrée à l'est de l'allée, le temple du Serpent à "
			"plumes monte en degrés ornés de têtes de serpents emplumés. Sous lui, un long tunnel creusé dans "
			"la roche descend vers une salle où des flaques de métal liquide brillent comme des lacs "
			"minuscules ; au bout, une arche de pierre noire encadre un voile de lumière — la porte d'Aix.",
		"templier": ("templier_ocelotl_teotihuacan", "Ocelotl", "ogre", "templier_ogre_m_teotihuacan01.jpg",
			"Templier gardien du temple du Serpent à plumes, à Teotihuacan. Il porte une peau de jaguar sur "
			"son manteau blanc, en signe d'alliance avec les guerriers-jaguars qui gardent la forêt."),
		"accueil": "Le tunnel sent la pierre froide et le métal. Dans la lueur des flaques argentées, un ogre "
			"immense en manteau blanc, une peau de jaguar jetée sur les épaules, se déplie lentement. « Je suis "
			"{pnj}. Ne touchez pas aux lacs d'argent : ils boivent la chaleur des doigts, et parfois le reste. »",
		"lore": "« Ceux d'ici disent que le Serpent à plumes a enseigné la porte au frère venu de loin, et "
			"qu'il a choisi ce temple parce qu'il est le sien. » {pnj} hausse ses énormes épaules. « Les "
			"Architectes d'Aix disent que le frère n'a eu besoin de personne. Les guerriers-jaguars, eux, ne "
			"disent rien : ils montent la garde dans la forêt et nous laissent le tunnel. Les lacs d'argent "
			"étaient là avant la porte. Pourquoi, personne ne le sait. »",
		"cite_txt": "« Remontez le tunnel, traversez la Ciudadela : l'allée mène aux deux grandes pyramides. "
			"Saluez les guerriers-jaguars si vous en croisez. Ils vous rendront le salut… ou pas. »",
	},
	{
		"slug": "pichao", "cite": None, "porte": "la porte de Pichao",
		"lieu": "lieu:temple_du_soleil_de_pichao", "label": "Le temple du Soleil de Pichao",
		"image": "temple_du_soleil_de_pichao.jpg",
		"texte": "Accroché aux terrasses de Pichao, sur la montagne verte noyée de nuages, le temple du Soleil "
			"est une tour de pierre courbe aux blocs ajustés sans mortier. Sous elle, une grotte taillée garde "
			"une arche de granit où flotte un voile de lumière — la porte d'Aix. Plus haut, sur la crête, la "
			"pierre où l'on attache le soleil projette son ombre sur les nuages.",
		"templier": ("templiere_cusi_coyllur_pichao", "Cusi Coyllur", "hobbit",
			"templier_hobbit_f_pichao01.jpg",
			"Templière gardienne du temple du Soleil, à Pichao. Elle connaît chaque marche des terrasses et "
			"compte les nuages comme d'autres comptent les passants."),
		"accueil": "L'air est rare et froid. Une hobbit en manteau blanc, un châle de laine aux couleurs vives "
			"noué par-dessus, vous tend une gourde avant même de vous saluer. « Buvez. Tout le monde a le "
			"souffle court en arrivant d'Aix. Je suis {pnj}, et vous êtes au temple du Soleil. »",
		"lore": "« Là-haut, sur la crête, il y a la pierre où l'on attache le soleil. Au plus court jour de "
			"l'année, les prêtres l'y lient pour qu'il ne s'en aille pas. » {pnj} pointe la grotte du doigt. "
			"« Certains disent que c'est la pierre qui tient la porte ouverte, et que si on la brisait, la "
			"porte s'éteindrait. D'autres, que la porte tient la pierre debout. Personne n'a essayé de savoir, "
			"et personne ne devrait. »",
		"cite_txt": "« Les terrasses descendent jusqu'à la forêt. Plus bas, dans les vallées chaudes, des "
			"hommes se couvrent de peaux de jaguar pour un rite que je ne vous conseille pas d'interrompre. »",
	},
	{
		"slug": "abou_simbel", "cite": "lieu:abou_simbel", "porte": "la porte d'Abou Simbel",
		"lieu": "lieu:petit_temple_d_abou_simbel", "label": "Le Petit Temple d'Abou Simbel",
		"image": "petit_temple_d_abou_simbel.jpg",
		"texte": "Au pied de la falaise, à l'écart du Grand Temple, le Petit Temple ouvre sa façade taillée dans "
			"le grès : six colosses debout, Néfertiti et Akhénaton tour à tour, encadrent une porte basse. "
			"Dans la salle hypostyle, des piliers à visage de femme aux oreilles de vache veillent sur une "
			"arche de pierre où tremble un voile de lumière — la porte d'Aix.",
		"templier": ("templier_nakhtmin_abou_simbel", "Nakhtmin", "elfe", "templier_elfe_m_abou_simbel01.jpg",
			"Templier gardien du Petit Temple d'Abou Simbel. Mort depuis longtemps et fort bien conservé, il "
			"sert la porte d'Aix comme il servait la cour, sans hâte et sans fatigue."),
		"accueil": "La salle est fraîche, presque froide, et sent la résine et le lin. Un elfe en manteau blanc "
			"sur une cuirasse dorée vous regarde sortir de l'arche ; sa peau est sèche et brune comme un "
			"parchemin, ses yeux parfaitement vivants. « Je suis {pnj}. Bienvenue au royaume de la Reine. Ici, "
			"les vivants sont des invités : comportez-vous comme tels. »",
		"lore": "« La Reine régnait déjà quand le frère est venu. » {pnj} effleure un pilier. « Certains de la "
			"cour disent qu'elle a obtenu la porte en échange d'un secret de longue vie ; d'autres, que le "
			"frère la lui a donnée pour qu'elle ne vienne jamais la chercher elle-même. J'étais là, et je ne "
			"sais pas lequel est vrai. Ne le répétez pas : à la cour, on aime les questions qui durent. »",
		"cite_txt": "« L'esplanade est devant, le Grand Temple sur votre droite. Ne vous étonnez pas de ceux "
			"que vous croiserez : la plupart ont votre âge depuis plusieurs siècles. »",
	},
]


def templier(t: dict) -> dict:
	slug, nom, race, portrait, description = t["templier"]
	accueil = [choix("lore", "« Qui a bâti cette porte ? »", "lore")]
	noeuds = {"lore": noeud(t["lore"], RETOUR)}
	if t["cite"]:
		accueil.append(choix("cite", "« Par où gagner la ville ? »", "cite"))
		noeuds["cite"] = noeud(t["cite_txt"], RETOUR)
	else:
		accueil.append(choix("cite", "« Il y a une ville, en bas ? »", "cite"))
		noeuds["cite"] = noeud(t["cite_txt"] + " « Pour l'heure, on ne descend pas sans un guide : "
			"revenez par la porte. »", RETOUR)
	accueil.append(choix("fin", "(Prendre congé.)"))
	noeuds["accueil"] = noeud(t["accueil"], *accueil)
	return pnj_doc(slug, nom, race, "garde", portrait, description, noeuds)


def docs_portails(par_id: dict, erreurs: list) -> list:
	out = []
	for t in TEMPLES:
		pnj = templier(t)
		temple = {"_id": t["lieu"], "type": "lieu", "label": t["label"], "image": t["image"],
			"categorie": "portail", "sous_categorie": "temple", "texte": t["texte"], "acces": ACCES,
			"pnj": [{"character": pnj["_id"], "nom": pnj["nom"], "portrait": pnj["portrait"], "probabilite": 1,
				"description": pnj["description"].split(". ")[0] + "."}]}
		if t["cite"]:
			temple["lieu_parent"] = t["cite"]
		out += [temple, pnj, connexion(f"link:chapelle_palatine_to_{t['slug']}", CHAPELLE, (0, 0), t["lieu"],
			(0, 0), "portail", "Aix-la-Chapelle — repasser le seuil", "Franchir " + t["porte"])]
		if not t["cite"]:
			continue
		cite = par_id.get(t["cite"])
		if not cite or not cite.get("cells"):
			erreurs.append(f"{t['cite']} absente du dump ou sans grille")
			continue
		cells, nav = cite["cells"], cite.get("nav")
		zones, vues = [], set()
		for y, ligne in enumerate(cells):
			for x, v in enumerate(ligne):
				if v in (1, 5) and (x, y) not in vues:
					z = zone_de(cells, (x, y), nav)
					vues |= z
					zones.append(z)
		case = plus_proche(max(zones, key=len), REPERES[t["cite"]])
		out.append(connexion(f"link:{t['cite'].split(':', 1)[1]}_to_{t['lieu'].split(':', 1)[1]}", t["cite"], case,
			t["lieu"], (0, 0), "temple", "Ressortir dans la ville", t["label"]))
	return out


def main() -> int:
	args = sys.argv[1:]
	chemin_dump = args[args.index("--dump") + 1] if "--dump" in args else None
	par_id = {d.get("_id"): d for d in ggi.charger_dump(chemin_dump)}
	if CHAPELLE not in par_id:
		print(f"✗ {CHAPELLE} absente du dump")
		return 1
	erreurs = []
	sortie = docs_portails(par_id, erreurs)
	ids = [d["_id"] for d in sortie]
	erreurs += [f"_id en double : {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
	deja = [i for i in ids if i in par_id]
	if deja:
		erreurs.append("déjà en base : " + ", ".join(deja))
	if erreurs:
		print("✗ " + "\n✗ ".join(erreurs))
		return 1
	with open(SORTIE, "w", encoding="utf-8", newline="\n") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	compte = {}
	for d in sortie:
		t = d["_id"].split(":", 1)[0]
		compte[t] = compte.get(t, 0) + 1
	print(" · ".join(f"{n} {t}" for t, n in sorted(compte.items())) + f" → {os.path.relpath(SORTIE, ggi.RACINE)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
