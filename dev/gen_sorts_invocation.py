#!/usr/bin/env python
# dev/gen_sorts_invocation.py
# Une échelle d'INVOCATIONS par école : un sort par niveau, de 1 à 10, pour le démoniste
# (Démonologie), le nécromancien (Nécromancie), le prêtre (Sainte) et le druide (Nature) —
# puis le GRIMOIRE et sa RECETTE de scriptorium de tout sort qui n'en a pas.
#
# CE QUE LE FICHIER D'IMPORT CONTIENT, et rien d'autre :
#   1. Les `sort:*` d'invocation neufs. Démoniste et nécromancien ont déjà leur niveau 1
#      (`pacte_du_servant`, `levee_des_ossements`) : ils reçoivent les niveaux 2 à 10, qui
#      prolongent cette échelle. Prêtre et druide reçoivent 1 à 10.
#   2. Pour CHAQUE sort sans grimoire — les neufs ET ceux déjà en base — un
#      `item:grimoire_<slug>` et un `recette:grimoire_<slug>`. Sans la recette, le grimoire
#      n'arrive jamais en rayon : les 61 grimoires en base sont tous produits par les
#      scriptoriums, aucun n'est approvisionné.
#
# CALIBRAGE. Une invocation n'a pas de magie (elle ne lance rien) : comptent F, R, Ag et la
# vitesse V de l'espèce. Budget grossier = (F + R + Ag + V×10)² × nombre × durée / 100.
#   - V × 10 : V vit à SON échelle (1-20), les autres caractéristiques à la leur (×10) ; et
#     c'est elle qui fait le nombre d'actions (`combat._compute_actions_max` : Ag/40 + V/2).
#     Une espèce qui vole (V 14-19) joue 9 à 12 actions par tour contre 3 à 6 à pied.
#   - le carré : une créature forte vaut plus que deux faibles (plus de PV à entamer, des
#     coups qui passent l'armure).
# Deux courbes :
#   - BASE (prêtre, druide) : ~550 au niveau 1, ×1,3 par niveau, ~5800 au niveau 10 ;
#   - FAVORISÉE (démoniste, nécromancien, dont la magie est AXÉE sur l'invocation) : un
#     niveau d'avance, soit la base × 1,3 à chaque niveau (~7600 au niveau 10).
#
# RÈGLES DE CONTENU (gardes du script — une violation arrête tout, rien n'est écrit) :
#   - DURÉE ≥ 3 TOURS (`DUREE_MIN`) : une créature rapide paie ses actions en rang, pas en tours ;
#   - NUÉES ANIMALES (`NUEES_ANIMALES_SEULEMENT`) : le druide n'appelle PLUSIEURS créatures
#     que si l'espèce porte le tag `animal` — jamais deux monstres mythologiques ensemble ;
#   - PROFIL COMPATIBLE : `zones.profil_compatible` (restriction_tags ⊆ tags de l'espèce),
#     la règle unique qui décide déjà du grade d'un monstre rencontré ;
#   - ESPÈCES EXCLUES (`ESPECES_EXCLUES`) : la vouivre, confondue avec la wyverne, à revoir.
#
# PROFILS. Tous les profils compatibles sont permis. Sans `profil`, la créature est le point
# médian de l'espèce (déterministe). Un profil tire chaque caractéristique dans
# [min de l'espèce + delta], bornée au max (`combat.roll_monster_stats`) — il part du
# MINIMUM : `novice` et `combattant` sont en général SOUS le médian, `champion`, `heros` et
# `seigneur` au-dessus. Ils servent à caler le budget ET à donner à une échelle une
# progression lisible (vétéran → champion → héros → seigneur chez les démons et les morts).
# Le budget noté est la MOYENNE des tirages : l'invocation n'est plus déterministe.
#
# PRIX DES GRIMOIRES. Les 61 grimoires en base enseignent tous un sort de niveau 0 et
# valent 5-15 argent, peu communs. Un grimoire de niveau n vaut 10n-30n argent, et sa
# rareté monte par paliers (`rarete_grimoire`). La recette reprend les matières des
# recettes de grimoire déjà en base (relues du dump, jamais retapées).
#
# IDEMPOTENT : un sort déjà en base avec la même espèce invoquée, un grimoire qui enseigne
# déjà le sort, une recette qui produit déjà ce grimoire ne sont pas réémis. Un `_id` pris
# par AUTRE CHOSE arrête tout, sans rien écrire — un import (PUT complet) l'écraserait.
#
# Usage : python dev/gen_sorts_invocation.py [chemin/vers/telluris-dump-*.json]
#         (sans argument : le dump le plus récent de jsons/)
# Sortie (à coller dans /admin -> Import en masse) :
#   jsons/sorts_invocation_a_importer.json

import json
import os
import sys
from collections import Counter

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "sorts_invocation_a_importer.json")

# `utils/zones.py` est une feuille de l'arbre d'imports (math/random seuls) : la règle de
# compatibilité profil/espèce est lue à sa source, jamais recopiée.
from utils.zones import profil_compatible  # noqa: E402

FAMILLE_INVOCATION = "invocation"
# Miroir de `utils/sorts.INVOCATION_NOMBRE_MAX` : au-delà, `invocation_de` rabote en silence.
INVOCATION_NOMBRE_MAX = 4
# Plancher de durée voulu pour ce contenu (le moteur, lui, accepte 1).
DUREE_MIN = 3
# Vocations qui n'appellent plusieurs créatures à la fois que parmi les ANIMAUX.
NUEES_ANIMALES_SEULEMENT = {"druide"}
TAG_ANIMAL = "animal"

ESPECES_EXCLUES = {
	"espece:vouivre": "confondue avec la wyverne — à revoir avant tout usage",
}

# École attendue par vocation — vérifiée contre `rules:vocations` du dump.
ECOLES = {
	"demoniste": "Démonologie",
	"necromancien": "Nécromancie",
	"pretre": "Sainte",
	"druide": "Nature",
}

# (vocation, niveau, slug, nom, icon, espece, profil, nombre, duree, cout_pm, description)
# `profil` : suffixe d'un `profil:*` (None = point médian de l'espèce).
# En fin de ligne : budget moyen (F+R+Ag+V×10)² × nombre × durée / 100, et la cible de sa courbe.
SORTS = [
	# ── Démoniste — Démonologie, courbe FAVORISÉE (niveau 1 en base : pacte_du_servant, 492) ──
	("demoniste", 2, "murmure_de_la_succube", "Murmure de la succube", "💋", "succube", "veteran", 1, 4, 28,  # ~940 / 930
	 "Un nom doux, soufflé comme un aveu. La succube sort de l'ombre en souriant et se jette sur ce que vous lui désignez, pour le seul plaisir du pacte."),
	("demoniste", 3, "contrat_mineur", "Contrat mineur", "👿", "demon_mineur", "veteran", 1, 4, 36,  # ~1156 / 1208
	 "Une signature de sang au bas d'un parchemin qui brûle aussitôt. Le démon mineur honore sa part du marché à coups de griffes, et pas une clause de plus."),
	("demoniste", 4, "couvee_infernale", "Couvée infernale", "👹", "rejeton_demoniaque", "novice", 2, 4, 46,  # ~1512 / 1571
	 "La fêlure s'ouvre sur un nid. Deux rejetons démoniaques à peine éclos en tombent, affamés, et se disputent la première proie venue."),
	("demoniste", 5, "serment_du_demon_guerrier", "Serment du démon guerrier", "🗡️", "demon_guerrier", "veteran", 1, 5, 55,  # ~2125 / 2042
	 "Un guerrier des cercles inférieurs répond à l'appel, lame au poing. Il a juré de combattre à vos côtés le temps du pacte, et il tient parole comme on tient une gorge."),
	("demoniste", 6, "ecuries_de_l_abime", "Écuries de l'Abîme", "🐎", "monture_demoniaque", "veteran", 2, 3, 65,  # ~2520 / 2655
	 "Deux montures démoniaques jaillissent au galop d'une porte de braise, sans cavalier, et chargent tout ce qui se tient entre vous et la sortie."),
	("demoniste", 7, "gardien_des_portes", "Gardien des portes", "🐕", "cerbere", "heros", 1, 5, 76,  # ~3510 / 3451
	 "Le chien aux trois gueules quitte un instant le seuil qu'il garde depuis toujours. Pour lui, vos ennemis ne sont que des âmes qui tentent de s'enfuir."),
	("demoniste", 8, "legion_de_l_abime", "Légion de l'Abîme", "🔥", "demon_guerrier", "heros", 2, 4, 88,  # ~4712 / 4486
	 "Deux guerriers d'élite de l'Abîme marchent au pas, épaule contre épaule. Ce n'est que l'avant-garde, et ils tiennent à ce que cela se sache."),
	("demoniste", 9, "rupture_du_sceau", "Rupture du sceau", "💥", "demon_majeur_de_la_destruction", "seigneur", 1, 5, 100,  # ~5760 / 5832
	 "Un sceau millénaire se fend sous vos mots. Ce qui en sort n'a qu'un seul désir, détruire, et vous venez de lui indiquer par où commencer."),
	("demoniste", 10, "couronne_de_l_enfer", "Couronne de l'Enfer", "👑", "prince_demon", "seigneur", 1, 5, 115,  # ~7615 / 7582
	 "Vous ne l'invoquez pas : vous l'invitez. Un prince démon franchit la couture du monde, et le champ de bataille devient pour un temps une province de son royaume."),

	# ── Nécromancien — Nécromancie, courbe FAVORISÉE (niveau 1 en base : levee_des_ossements, 739) ──
	("necromancien", 2, "faim_de_la_goule", "Faim de la goule", "🧟", "goule", "veteran", 1, 4, 30,  # ~880 / 930
	 "Une odeur de terre retournée, puis des griffes qui grattent par en dessous. La goule remonte à l'air libre avec une seule idée : manger."),
	("necromancien", 3, "bandelettes_du_tombeau", "Bandelettes du tombeau", "⚱️", "momie", "champion", 1, 4, 38,  # ~1116 / 1208
	 "Des bandelettes jaunies se déroulent d'elles-mêmes autour du corps d'un ancien gardien de tombeau. La momie avance lentement, mais elle a gardé les gestes de celui qui défendait les rois."),
	("necromancien", 4, "horde_des_fosses", "Horde des fosses", "🪦", "zombie", "champion", 3, 3, 48,  # ~1710 / 1571
	 "La fosse commune se vide d'un coup. Trois cadavres encore sanglés dans leurs vieilles armures titubent vers l'ennemi : de vieux soldats, qui n'ont pas oublié comment on frappe."),
	("necromancien", 5, "chant_de_la_lhamia", "Chant de la lhamia", "🐍", "lhamia", "champion", 1, 5, 58,  # ~2000 / 2042
	 "Un chant sans souffle monte d'une crypte oubliée. La lhamia répond, mi-femme mi-serpent, et enserre de ses anneaux morts ce qu'on lui livre."),
	("necromancien", 6, "visage_de_l_horreur", "Visage de l'horreur", "😱", "horreur", "heros", 1, 5, 68,  # ~2770 / 2655
	 "Vous tirez du néant une chose que personne ne sait nommer. Même vos alliés évitent de la regarder en face ; vos ennemis, eux, n'ont pas le choix."),
	("necromancien", 7, "soif_du_nosferatu", "Soif du nosferatu", "🦇", "nosferatu", "champion", 1, 6, 80,  # ~3534 / 3451
	 "Une silhouette voûtée se déplie dans l'ombre, les crocs déjà découverts. Le nosferatu frappe vite et sans bruit, comme la bête qu'il est resté."),
	("necromancien", 8, "seigneurie_du_sang", "Seigneurie du sang", "🩸", "seigneur_du_sang", "seigneur", 1, 5, 92,  # ~4515 / 4486
	 "Un seigneur du sang répond à votre appel comme on répond à un vassal : de haut. Il combat pourtant, parce que le sang versé ici lui revient."),
	("necromancien", 9, "ordre_sanglant", "Ordre sanglant", "⚔️", "chevalier_du_sang", "heros", 3, 3, 104,  # ~5643 / 5832
	 "Trois chevaliers du sang se lèvent dans leurs armures rouillées, fidèles à un serment prêté à un roi mort. Aujourd'hui, c'est vous qu'ils servent."),
	("necromancien", 10, "ailes_de_charogne", "Ailes de charogne", "🐉", "dragon_zombie", "seigneur", 1, 5, 118,  # ~7370 / 7582
	 "Le ciel s'assombrit sous des ailes percées. Un dragon mort depuis des siècles s'abat sur le champ de bataille, et ses os gardent la mémoire de la chasse."),

	# ── Prêtre — Sainte, courbe de BASE ─────────────────────────────────────────────
	("pretre", 1, "messager_aile", "Messager ailé", "👼", "cupidon", None, 1, 3, 20,  # 523 / 550
	 "Un petit messager céleste descend dans un rai de lumière. Il n'a rien d'un guerrier, mais il sait où frapper et ne connaît pas la peur."),
	("pretre", 2, "verite_gravee", "Vérité gravée", "🪨", "golem_de_pierre", "novice", 1, 3, 28,  # ~699 / 715
	 "Vous tracez un seul mot sur un front de glaise durcie : vérité. Le golem de pierre se lève, lourd et sans malice, et protège les siens tant que le mot reste lisible."),
	("pretre", 3, "gardien_du_temple", "Gardien du temple", "🦁", "sphinx", "novice", 1, 4, 36,  # ~932 / 930
	 "Le sphinx qui garde le seuil des temples anciens répond à la prière. Il ne pose pas d'énigme aujourd'hui : il se contente de barrer la route."),
	("pretre", 4, "licorne_immaculee", "Licorne immaculée", "🦄", "licorne", None, 1, 3, 46,  # 1164 / 1208
	 "Seul un cœur sans souillure peut l'appeler. La licorne surgit au galop, et sa corne s'abat sur ce qui menace celui qui l'a priée."),
	("pretre", 5, "temoin_celeste", "Témoin céleste", "📜", "ange_de_la_connaissance", "novice", 1, 3, 55,  # ~1623 / 1571
	 "Un ange de la connaissance se tient à vos côtés, un livre de lumière contre la poitrine. Il est venu consigner la bataille ; il ne refuse pas pour autant d'y prendre part."),
	("pretre", 6, "sentinelle_du_parvis", "Sentinelle du parvis", "🗿", "gargouille", "novice", 1, 3, 65,  # ~1989 / 2042
	 "La pierre d'une cathédrale lointaine s'éveille et vient à vous. La gargouille ne recule pas : elle a veillé des siècles sur des portes plus précieuses que la vôtre."),
	("pretre", 7, "sentence_de_justice", "Sentence de justice", "⚖️", "ange_de_la_justice", None, 1, 3, 76,  # 2864 / 2655
	 "Un ange de la justice se pose, balance et épée en main. Il ne juge pas vos ennemis : la sentence est déjà rendue."),
	("pretre", 8, "main_de_l_ordre", "Main de l'Ordre", "🛡️", "archange_de_l_ordre", "novice", 1, 3, 88,  # ~3219 / 3451
	 "L'archange de l'Ordre descend en armure d'or, et le chaos du combat semble reculer d'un pas. Là où il frappe, rien ne se relève."),
	("pretre", 9, "incarnation_divine", "Incarnation divine", "✨", "avatar", "heros", 1, 4, 100,  # ~4724 / 4486
	 "Pour un bref instant, le divin prend chair. L'avatar marche à vos côtés, et chacun de ses coups porte le poids d'une volonté qui dépasse les mortels."),
	("pretre", 10, "descente_du_seraphin", "Descente du séraphin", "🔆", "seraphin", None, 1, 3, 115,  # 6265 / 5832
	 "Six ailes de feu déchirent la voûte du ciel. Le séraphin ne vient qu'aux prières les plus pures, et ce qu'il trouve sur son chemin ne survit pas à sa lumière."),

	# ── Druide — Nature, courbe de BASE (plusieurs créatures : animaux seulement) ─────
	("druide", 1, "charge_du_sanglier", "Charge du sanglier", "🐗", "sanglier", None, 1, 3, 18,  # 555 / 550
	 "Un grognement dans les fourrés, puis la bête déboule. Le sanglier fonce droit sur l'ennemi, tête basse, sans jamais se demander pourquoi."),
	("druide", 2, "hurlement_du_loup", "Hurlement du loup", "🐺", "loup", None, 1, 3, 26,  # 684 / 715
	 "Vous hurlez comme la meute, et un loup gris vous répond depuis la lisière. Il tourne autour de sa proie, cherche le flanc, et mord."),
	("druide", 3, "reveil_de_l_ours", "Réveil de l'ours", "🐻", "ours", "veteran", 1, 3, 34,  # ~918 / 930
	 "Vous tirez un ours de son sommeil, et il ne vous en veut pas : il en veut à tout le reste."),
	("druide", 4, "eveil_de_l_homme_arbre", "Éveil de l'homme-arbre", "🌳", "homme_arbre", None, 1, 4, 44,  # 1211 / 1208
	 "Les racines craquent, l'écorce se fend. Un homme-arbre s'arrache au sol et avance, lent comme les saisons et aussi difficile à arrêter."),
	("druide", 5, "meute_grise", "Meute grise", "🌫️", "loup", "veteran", 2, 3, 54,  # ~1518 / 1571
	 "Deux vieux loups gris, balafrés par cent hivers, sortent de la brume à votre appel. Ils chassent à deux depuis toujours, et savent qui prendre à revers."),
	("druide", 6, "anneaux_du_serpent_geant", "Anneaux du serpent géant", "🐍", "serpent_geant", None, 1, 5, 64,  # 2101 / 2042
	 "Quelque chose d'épais glisse sous les feuilles mortes. Le serpent géant se dresse, enserre la première proie à sa portée et ne la lâche plus."),
	("druide", 7, "serres_de_l_aigle_geant", "Serres de l'aigle géant", "🦅", "aigle_geant", "novice", 1, 4, 75,  # ~2552 / 2655
	 "Une ombre immense passe sur le champ de bataille. L'aigle géant plonge, serres en avant, sur la proie que vous lui désignez du doigt."),
	("druide", 8, "marche_des_mammouths", "Marche des mammouths", "🦣", "mammouth", None, 2, 4, 86,  # 3428 / 3451
	 "Le sol tremble bien avant qu'ils n'apparaissent. Deux mammouths venus d'un âge oublié piétinent tout ce qui se trouve sur leur passage."),
	("druide", 9, "envol_du_griffon", "Envol du griffon", "🪶", "griffon", "champion", 1, 4, 98,  # ~4432 / 4486
	 "Mi-aigle, mi-lion, le griffon descend des cimes où il niche. Il ne sert personne ; il accepte seulement, pour un temps, de chasser avec vous."),
	("druide", 10, "tetes_de_l_hydre", "Têtes de l'hydre", "🐲", "hydre", "seigneur", 1, 8, 112,  # ~5776 / 5832
	 "Des marais les plus profonds monte une hydre aux têtes innombrables. Le druide ne la commande pas : il lui ouvre simplement le chemin."),
]


def rarete_grimoire(niveau: int) -> str:
	"""Paliers de rareté d'un grimoire selon le niveau du sort qu'il enseigne. Le niveau 0
	garde celle des 61 grimoires en base."""
	if niveau <= 3:
		return "peu_commun"
	if niveau <= 6:
		return "rare"
	if niveau <= 9:
		return "tres_rare"
	return "legendaire"


def valeur_grimoire(niveau: int) -> list:
	"""Fourchette de prix (min, max) : 5-15 argent au niveau 0 (valeur des grimoires en
	base), 10n-30n argent au niveau n."""
	if niveau <= 0:
		return [{"ag": 5}, {"ag": 15}]
	return [{"ag": 10 * niveau}, {"ag": 30 * niveau}]


def charger_dump(chemin=None) -> dict:
	if chemin:
		return json.load(open(chemin, encoding="utf-8"))
	dumps = sorted(
		f for f in os.listdir(DOSSIER_JSONS)
		if f.startswith("telluris-dump-") and f.endswith(".json")
	)
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez le chemin en argument.")
	print("source : jsons/%s" % dumps[-1])
	return json.load(open(os.path.join(DOSSIER_JSONS, dumps[-1]), encoding="utf-8"))


def sort_doc(spec) -> dict:
	vocation, niveau, slug, nom, icon, espece, profil, nombre, duree, cout_pm, description = spec
	invocation = {"espece": "espece:" + espece, "nombre": nombre, "duree": duree}
	if profil:
		invocation["profil"] = "profil:" + profil
	return {
		"_id": "sort:" + slug,
		"type": "sort",
		"nom": nom,
		"icon": icon,
		"description": description,
		"vocation": vocation,
		"magie": ECOLES[vocation],
		"famille": FAMILLE_INVOCATION,
		"niveau": niveau,
		"cout_pm": cout_pm,
		"cible": "soi",
		"portee": 0,
		# Vide ET sans `composants` : une invocation n'applique aucun effet (branche exclusive
		# de `resolve_action`), des bonus de composant y seraient inertes.
		"effets": {},
		"invocation": invocation,
	}


def matieres_grimoire(base: dict) -> list:
	"""Matières de la recette de grimoire la plus répandue en base — relues, jamais retapées."""
	signatures = Counter(
		json.dumps(d.get("matieres_premieres"), sort_keys=True, ensure_ascii=False)
		for d in base.values()
		if d.get("type") == "recette" and str(d.get("objet_final") or "").startswith("grimoire_")
		and d.get("matieres_premieres")
	)
	if not signatures:
		raise SystemExit("ERREUR : aucune recette de grimoire dans le dump — pas de modèle à reprendre.")
	return json.loads(signatures.most_common(1)[0][0])


def grimoire_doc(sort: dict) -> dict:
	slug = sort["_id"][len("sort:"):]
	niveau = int(sort.get("niveau") or 0)
	nom = sort.get("nom") or slug
	return {
		"_id": "item:grimoire_" + slug,
		"type": "item",
		"nom": "Grimoire : " + nom,
		"icon": "📖",
		"description": "Un grimoire relié qui enseigne le sort « %s » (%s). Il n'est pas consumé par l'étude."
					   % (nom, sort.get("vocation") or ""),
		"rarete": rarete_grimoire(niveau),
		"categorie": "livre",
		"sous_categorie": "grimoire",
		"slots": [],
		"tags": ["grimoire"],
		"poids": 1,
		"sorts": [sort["_id"]],
		"valeur": valeur_grimoire(niveau),
	}


def recette_doc(sort: dict, matieres: list) -> dict:
	slug = sort["_id"][len("sort:"):]
	return {
		"_id": "recette:grimoire_" + slug,
		"type": "recette",
		"lieu_categorie": "scriptorium",
		"objet_final": "grimoire_" + slug,
		"quantite_produite": 1,
		"matieres_premieres": [dict(m) for m in matieres],
	}


def verifier_regles(base: dict) -> list:
	"""Règles de contenu de chaque ligne de `SORTS` contre le dump — liste d'erreurs."""
	erreurs = []
	vocations = {v.get("id"): v for v in ((base.get("rules:vocations") or {}).get("value") or [])}
	for voc, ecole in ECOLES.items():
		magie = (vocations.get(voc) or {}).get("magie")
		if magie != ecole:
			erreurs.append("rules:vocations : %s pratique « %s », attendu « %s »" % (voc, magie, ecole))
	vus = set()
	for spec in SORTS:
		voc, niveau, slug, espece_slug, profil_slug, nombre, duree = (
			spec[0], spec[1], spec[2], spec[5], spec[6], spec[7], spec[8])
		espece_id = "espece:" + espece_slug
		espece = base.get(espece_id) or {}
		if (voc, niveau) in vus:
			erreurs.append("deux sorts de niveau %d pour %s" % (niveau, voc))
		vus.add((voc, niveau))
		if not 1 <= nombre <= INVOCATION_NOMBRE_MAX:
			erreurs.append("sort:%s : nombre %d hors de [1, %d]" % (slug, nombre, INVOCATION_NOMBRE_MAX))
		if duree < DUREE_MIN:
			erreurs.append("sort:%s : durée %d < %d tours" % (slug, duree, DUREE_MIN))
		if espece_id in ESPECES_EXCLUES:
			erreurs.append("sort:%s invoque %s, exclue : %s" % (slug, espece_id, ESPECES_EXCLUES[espece_id]))
		if voc in NUEES_ANIMALES_SEULEMENT and nombre > 1 and TAG_ANIMAL not in (espece.get("tags") or []):
			erreurs.append("sort:%s : %s appelle %d× %s, qui n'est pas un animal"
						   % (slug, voc, nombre, espece_id))
		if profil_slug:
			profil = base.get("profil:" + profil_slug) or {}
			if profil.get("type") != "profil":
				erreurs.append("sort:%s : profil:%s absent du dump" % (slug, profil_slug))
			elif espece and not profil_compatible(profil, espece):
				erreurs.append("sort:%s : profil:%s incompatible avec %s (restriction_tags %s)"
							   % (slug, profil_slug, espece_id, profil.get("restriction_tags")))
	return erreurs


def main() -> None:
	# Console Windows en cp1252 : sans cela, le premier accent fait planter le script.
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass

	dump = charger_dump(sys.argv[1] if len(sys.argv) > 1 else None)
	base = {d["_id"]: d for d in dump["docs"] if isinstance(d, dict) and d.get("_id")}
	erreurs = verifier_regles(base)
	sortie = []

	# ── 1. Sorts d'invocation ──────────────────────────────────────────────────────
	print("\n== Sorts d'invocation")
	neufs = []
	for spec in SORTS:
		doc = sort_doc(spec)
		inv = doc["invocation"]
		espece = base.get(inv["espece"])
		if not espece or espece.get("type") != "espece":
			erreurs.append("%s invoque %s, absent du bestiaire" % (doc["_id"], inv["espece"]))
			continue
		existant = base.get(doc["_id"])
		if existant is not None:
			if (existant.get("invocation") or {}).get("espece") == inv["espece"]:
				print("   %-36s déjà en base" % doc["_id"])
			else:
				erreurs.append("%s existe déjà et n'est pas cette invocation — un import l'écraserait" % doc["_id"])
			continue
		neufs.append(doc)
		print("   %-36s niv %2d  %-12s %d× %-32s %-18s %d t  %3d PM" % (
			doc["_id"], doc["niveau"], doc["vocation"], inv["nombre"], espece.get("nom"),
			inv.get("profil", "(médian)"), inv["duree"], doc["cout_pm"]))

	# Une autre invocation déjà en base (hors de ce script) : signalée, pas bloquante — c'est
	# le cas voulu des deux niveaux 1 existants.
	ids_script = {sort_doc(s)["_id"] for s in SORTS}
	for d in base.values():
		if d.get("type") == "sort" and d.get("invocation") and d["_id"] not in ids_script:
			inv = d.get("invocation") or {}
			note = ""
			if int(inv.get("duree") or 0) < DUREE_MIN:
				note = "  ⚠️ durée %s < %d, non retouchée par ce script" % (inv.get("duree"), DUREE_MIN)
			print("   (en base : %s — %s niveau %s)%s" % (d["_id"], d.get("magie"), d.get("niveau"), note))

	# ── 2. Grimoires + recettes manquants ──────────────────────────────────────────
	print("\n== Grimoires et recettes manquants")
	matieres = matieres_grimoire(base)
	couverts = {
		s for d in base.values()
		if d.get("type") == "item" and d.get("sous_categorie") == "grimoire"
		for s in (d.get("sorts") or [])
	}
	tous = [d for d in base.values() if d.get("type") == "sort"] + neufs
	nb_grimoires = 0
	for sort in sorted(tous, key=lambda d: (str(d.get("magie") or ""), int(d.get("niveau") or 0), d["_id"])):
		if sort["_id"] in couverts:
			continue
		grimoire = grimoire_doc(sort)
		recette = recette_doc(sort, matieres)
		if grimoire["_id"] in base:
			# Il existe, mais n'enseigne PAS ce sort (sinon il serait dans `couverts`).
			erreurs.append("%s existe déjà et n'enseigne pas %s" % (grimoire["_id"], sort["_id"]))
			continue
		sortie.append(grimoire)
		nb_grimoires += 1
		etat_recette = "neuve"
		existante = base.get(recette["_id"])
		if existante is not None:
			if existante.get("objet_final") == recette["objet_final"]:
				etat_recette = "déjà en base"
			else:
				erreurs.append("%s existe déjà et ne produit pas %s" % (recette["_id"], grimoire["_id"]))
				continue
		else:
			sortie.append(recette)
		print("   %-44s niv %2d  %-10s %s-%s ag  recette %s" % (
			grimoire["_id"], int(sort.get("niveau") or 0), grimoire["rarete"],
			grimoire["valeur"][0]["ag"], grimoire["valeur"][1]["ag"], etat_recette))

	if erreurs:
		print("\n⚠️ %d erreur(s) — RIEN n'est écrit :" % len(erreurs))
		for e in erreurs:
			print("   " + e)
		sys.exit(1)

	docs = neufs + sortie
	with open(SORTIE, "w", encoding="utf-8") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print("\nécrit jsons/%s : %d doc(s) — %d sort(s), %d grimoire(s), %d recette(s)" % (
		os.path.basename(SORTIE), len(docs), len(neufs), nb_grimoires,
		sum(1 for d in sortie if d["type"] == "recette")))
	if not docs:
		print("   rien à importer : tout est déjà en base.")


if __name__ == "__main__":
	main()
