#!/usr/bin/env python
"""Contenu des PIÈGES (utils/pieges.py) : compétences, objets, recettes, animations.

    python dev/gen_pieges.py [--dump jsons/telluris-dump-*.json]

Sortie :
    jsons/pieges_a_importer.json   (carte d'import de /admin)

CE QUE LE FICHIER CONTIENT :
  1. Voleur, forestier ET assassin (une compétence = une vocation, d'où un doc par
     vocation) : « Détection des pièges » (`effets.detection_pieges`) et « Désamorçage des
     pièges » (`effets.desamorcage`), passives — niveau 1 pour le voleur et le forestier,
     2 et 4 pour l'assassin (`NIVEAUX_PASSIVES`).
  2. Une compétence de POSE par niveau et par vocation (bloc `pose_piege`) — 2 → 8 pour le
     voleur et le forestier, 5 → 8 pour l'assassin —, chacune consommant un objet
     DIFFÉRENT, de plus en plus dangereuse ou couvrant une zone plus grande (`POSES` — la
     table à retoucher). Les pièges de l'assassin IMMOBILISENT plus qu'ils ne tuent :
     entraves de V (et d'Ag), dégâts symboliques (`degats` explicite) ; son métier reste le
     coup unique au contact et le poison à distance, jamais le piège.
  3. Les objets consommés qui n'existent pas encore, et leur RECETTE dans un atelier dont les
     métiers consomment DÉJÀ chaque intrant (pas de fausse feuille). Deux objets existants
     sont réutilisés : `item:Piege_a_collet` et `item:Filet_de_capture`.
  4. Trois animations sprite + son, à partir de fichiers déjà présents : déclenchement,
     désamorçage réussi, désamorçage raté (`utils/pieges.ANIM_*`).

⚠️ Garde-fous — rien n'est écrit si l'un d'eux échoue :
  · un `_id` déjà pris en base (ou dans un autre `jsons/*_a_importer.json`) par un doc
    DIFFÉRENT fait tout refuser ; identique ⇒ sauté (idempotent) ;
  · chaque objet consommé existe (base ou lot) et deux compétences ne consomment jamais le
    même ; chaque objet neuf a sa recette ;
  · chaque intrant de recette (`item:*` ou sous-catégorie) existe et est déjà consommé par
    une recette de la même catégorie d'atelier ; la catégorie a des recettes en base ;
  · chaque vocation existe dans `rules:vocations` ; chaque bloc `pose_piege` est accepté tel
    quel par `pieges.normaliser_pose` (aucune clé perdue) ;
  · chaque animation source existe dans la base avec son fichier.
"""

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils import pieges  # noqa: E402  (module pur : aucune base)

DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "pieges_a_importer.json")

VOCATIONS = ("voleur", "forestier", "assassin")

# Niveau d'apprentissage de (détection, désamorçage) par vocation — demande explicite pour
# l'assassin : détection au 2, désamorçage au 4.
NIVEAUX_PASSIVES = {
	"voleur": {"detection_des_pieges": 1, "desamorcage_des_pieges": 1},
	"forestier": {"detection_des_pieges": 1, "desamorcage_des_pieges": 1},
	"assassin": {"detection_des_pieges": 2, "desamorcage_des_pieges": 4},
}

# ── 1. Détection et désamorçage ──────────────────────────────────────────────
# Bonus de compétence ajouté au seuil d100 (50 + Int|Ag + bonus − danger × 15).
BONUS_DETECTION = 20
BONUS_DESAMORCAGE = 20

PASSIVES = {
	"detection_des_pieges": {
		"nom": "Détection des pièges", "icon": "👁️",
		"effets": {"detection_pieges": BONUS_DETECTION},
		"description": {
			"voleur": "Une dalle trop propre, un fil qui accroche la lumière : il sent le "
					  "piège avant d'y poser le pied. Repère les pièges à deux pas, et peut "
					  "fouiller les environs (1 action).",
			"forestier": "Une branche cassée au mauvais endroit, une terre retournée de "
						 "frais : rien n'échappe à l'œil du traqueur. Repère les pièges à deux "
						 "pas, et peut fouiller les environs (1 action).",
			"assassin": "Qui pose des pièges dans l'ombre apprend vite à flairer ceux des "
						"autres. Repère les pièges à deux pas, et peut fouiller les environs "
						"(1 action).",
		},
	},
	"desamorcage_des_pieges": {
		"nom": "Désamorçage des pièges", "icon": "🛠️",
		"effets": {"desamorcage": BONUS_DESAMORCAGE},
		"description": {
			"voleur": "Une lame glissée sous la plaque, un ressort retenu du bout de l'ongle. "
					  "Désamorce un piège détecté au contact (1 action).",
			"forestier": "Il sait quelle corde trancher et quelle branche caler. Désamorce "
						 "un piège détecté au contact (1 action).",
			"assassin": "Des doigts qui savent enduire une lame savent aussi retenir un "
						"ressort. Désamorce un piège détecté au contact (1 action).",
		},
	},
}

# ── 2. Niveaux 2 → 8 : pose de pièges ────────────────────────────────────────
# (niveau, slug, nom, icon, item, danger, zone, effets, description[, degats])
# danger 1-5 → dégâts `<danger>D6` (pieges.degats_de) sauf `degats` explicite ; zone = rayon
# du carré couvert.
# Effets : `buffs` signés, `regen_pv`/`regen_pm` signées (négatif = POISON) + `duree`
# (cf. pieges.normaliser_pose). Échelle des buffs : V 1-10 (|delta| ≤ 5), les autres ×10.
POSES = {
	"forestier": [
		(2, "collet", "Collet", "🪢", "item:Piege_a_collet", 1, 0,
		 {"buffs": {"V": -3}, "duree": 2},
		 "Un nœud coulant caché sous les feuilles : la proie s'y prend la patte et reste sur place."),
		(3, "fosse_a_pieux", "Fosse à pieux", "🕳️", "item:Pieux_de_fosse", 2, 0, {},
		 "Quelques pieux durcis au feu, une fosse sommaire, un lit de branchages par-dessus."),
		(4, "filet_de_capture", "Filet de capture", "🕸️", "item:Filet_de_capture", 1, 1,
		 {"buffs": {"V": -3}, "duree": 2},
		 "Un filet tendu entre deux troncs, qui tombe sur tout ce qui passe dessous."),
		(5, "piege_a_machoires", "Piège à mâchoires", "🦷", "item:Piege_a_machoires", 3, 0,
		 {"buffs": {"V": -2}, "duree": 2},
		 "Deux arcs de fer dentelés qu'un ressort referme sur la jambe imprudente."),
		(6, "arbre_ressort", "Arbre-ressort", "🌳", "item:Ressort_de_branche", 3, 1, {},
		 "Un jeune arbre courbé jusqu'au sol, qu'un fil libère à toute volée."),
		(7, "eboulis", "Éboulis", "🪨", "item:Declencheur_d_eboulis", 4, 1, {},
		 "Un étai retiré au bon moment, et la pente entière dégringole sur les assaillants."),
		(8, "abattis_piege", "Abattis piégé", "🪵", "item:Abattis_piege", 5, 2,
		 {"buffs": {"V": -2}, "duree": 2},
		 "Un enchevêtrement de troncs et de pointes qui s'effondre d'un bloc sur un large pan de terrain."),
	],
	"voleur": [
		(2, "chausse_trappes", "Chausse-trappes", "📌", "item:Chausse_trappes", 1, 1,
		 {"buffs": {"V": -2}, "duree": 1},
		 "Une poignée de pointes de fer semées au sol : toujours une vers le haut."),
		(3, "aiguille_empoisonnee", "Aiguille empoisonnée", "💉", "item:Aiguille_empoisonnee", 2, 0,
		 {"regen_pv": -4, "duree": 3},
		 "Une aiguille enduite, montée sur une plaque : le poison ronge sa victime plusieurs tours durant."),
		(4, "fil_a_carreau", "Fil à carreau", "🎯", "item:Fil_a_carreau", 3, 0, {},
		 "Un fil tendu à hauteur de cheville relié à une arbalète cachée."),
		(5, "poudre_aveuglante", "Sachet de poudre aveuglante", "💨", "item:Sachet_de_poudre_aveuglante", 2, 1,
		 {"buffs": {"Ag": -15}, "duree": 2},
		 "Un sachet qui crève sous le pas et emplit l'air d'une poudre qui brûle les yeux."),
		(6, "machoire_d_acier", "Mâchoire d'acier", "⚙️", "item:Machoire_d_acier", 4, 0,
		 {"buffs": {"V": -3}, "duree": 2},
		 "Un piège d'acier trempé, plus lourd et plus mordant qu'aucun piège de trappeur."),
		(7, "feu_gregeois", "Pot de feu grégeois", "🔥", "item:Pot_de_feu_gregeois", 4, 1, {},
		 "Un pot de terre scellé posé sur une plaque : le feu prend et colle à tout ce qu'il touche."),
		(8, "mine_de_poudre", "Mine de poudre noire", "💥", "item:Mine_de_poudre_noire", 5, 2, {},
		 "Une charge de poudre enterrée, une mèche à friction : tout saute dans un grand rayon."),
	],
	# Assassin : des pièges qui IMMOBILISENT. `danger` y règle surtout la discrétion (seuils
	# de détection, de désamorçage et de flair des monstres) ; les dégâts sont fixés bas par
	# une 10ᵉ colonne `degats` — la proie doit rester entière et sur place pour la lame ou
	# la sarbacane. Aucun poison : il se porte au contact ou à distance, pas dans un piège.
	"assassin": [
		(5, "lacet_d_entrave", "Lacet d'entrave", "🧵", "item:Lacet_d_entrave", 2, 0,
		 {"buffs": {"V": -4}, "duree": 2},
		 "Un lacet de crin tressé, invisible dans la pénombre, qui se resserre sur la cheville "
		 "et la cloue au sol.", "1D2"),
		(6, "bolas_a_ressort", "Bolas à ressort", "🪀", "item:Bolas_a_ressort", 2, 1,
		 {"buffs": {"V": -3, "Ag": -10}, "duree": 2},
		 "Des poids lestés qu'un ressort lance au ras du sol : les jambes s'emmêlent, on tombe, "
		 "on se relève mal.", "1D3"),
		(7, "glu_de_nuit", "Glu de nuit", "🫙", "item:Glu_de_nuit", 3, 1,
		 {"buffs": {"V": -5}, "duree": 3},
		 "Une glu sombre étalée sur les dalles : qui y pose le pied n'en repart plus de "
		 "sitôt.", "1D2"),
		(8, "brume_de_pavot", "Brume de pavot", "😶‍🌫️", "item:Brume_de_pavot", 3, 2,
		 {"buffs": {"V": -5, "Ag": -20}, "duree": 2},
		 "Une vessie crevée sous le pas libère une brume lourde de pavot : les membres "
		 "s'engourdissent, la garde tombe — juste le temps qu'il faut.", "1D3"),
	],
}

# ── 3. Objets neufs et leurs recettes ────────────────────────────────────────
# item_id → (nom, icon, poids, rarete, description, atelier, intrants, quantite_produite)
# Intrant : "item:*" ou une sous-catégorie, déjà consommés par l'atelier (garde-fou).
OBJETS = {
	"item:Pieux_de_fosse": ("Pieux de fosse", "🪵", 2.0, "commun",
		"Un fagot de pieux durcis au feu, de quoi garnir une fosse.",
		"armurerie", [("manche", 3), ("fer", 1)], 1),
	"item:Piege_a_machoires": ("Piège à mâchoires", "🦷", 1.5, "commun",
		"Deux arcs de fer dentelés montés sur un ressort.",
		"armurerie", [("fer", 2), ("tendons", 1)], 1),
	"item:Ressort_de_branche": ("Ressort de branche", "🌳", 1.0, "peu_commun",
		"Cordages, cales et déclencheur pour bander un jeune arbre en piège.",
		"armurerie", [("tendons", 2), ("manche", 1)], 1),
	"item:Declencheur_d_eboulis": ("Déclencheur d'éboulis", "🪨", 3.0, "peu_commun",
		"Un étai à goupille et sa corde de tirage : il suffit d'une pente.",
		"armurerie", [("rondin", 1), ("tendons", 2)], 1),
	"item:Abattis_piege": ("Abattis piégé", "🪵", 5.0, "rare",
		"Troncs, pointes et liens d'un abattis à monter en travers d'un passage.",
		"armurerie", [("gros_rondin", 1), ("petit_rondin", 2), ("fer", 2)], 1),
	"item:Chausse_trappes": ("Chausse-trappes", "📌", 0.5, "commun",
		"Une bourse de pointes de fer à quatre branches.",
		"armurerie", [("fer", 1)], 3),
	"item:Aiguille_empoisonnee": ("Aiguille empoisonnée", "💉", 0.1, "peu_commun",
		"Une plaque à ressort armée d'une aiguille enduite de suc de pavot.",
		"laboratoire_d_alchimie", [("item:Capsules_de_pavot", 1), ("reactif_brut", 1)], 2),
	"item:Fil_a_carreau": ("Fil à carreau", "🎯", 1.5, "peu_commun",
		"Une petite arbalète à déclencheur, son fil et ses carreaux.",
		"armurerie", [("fer", 1), ("tendons", 1), ("manche", 1)], 1),
	"item:Sachet_de_poudre_aveuglante": ("Sachet de poudre aveuglante", "💨", 0.2, "peu_commun",
		"Un sachet fin bourré d'une poudre qui brûle les yeux.",
		"laboratoire_d_alchimie", [("item:Herbes_a_bruler", 2), ("poudre_d_os", 1)], 2),
	"item:Machoire_d_acier": ("Mâchoire d'acier", "⚙️", 2.5, "rare",
		"Un piège d'acier trempé à double ressort.",
		"armurerie", [("acier", 2), ("fer", 1)], 1),
	"item:Pot_de_feu_gregeois": ("Pot de feu grégeois", "🔥", 1.5, "rare",
		"Un pot de terre scellé, plein d'un feu qui ne s'éteint pas dans l'eau.",
		"laboratoire_d_alchimie", [("reactif_brut", 2), ("graisse", 1)], 1),
	"item:Mine_de_poudre_noire": ("Mine de poudre noire", "💥", 3.0, "rare",
		"Une charge de poudre en coffret, sa mèche à friction.",
		"laboratoire_d_alchimie", [("reactif_brut", 3), ("poudre_d_os", 1), ("graisse", 1)], 1),
	"item:Lacet_d_entrave": ("Lacet d'entrave", "🧵", 0.2, "peu_commun",
		"Un lacet de crin noirci, tressé avec un nœud coulant à déclencheur.",
		"armurerie", [("crins", 2), ("tendons", 1)], 2),
	"item:Bolas_a_ressort": ("Bolas à ressort", "🪀", 1.5, "peu_commun",
		"Trois poids de plomb, leurs cordes et une plaque à ressort qui les lance au ras du sol.",
		"armurerie", [("plomb", 2), ("item:corde", 1), ("tendons", 1)], 1),
	"item:Glu_de_nuit": ("Glu de nuit", "🫙", 1.0, "rare",
		"Un pot de glu sombre tirée de la sève de chêne, qui ne sèche jamais tout à fait.",
		"laboratoire_d_alchimie", [("item:Seve_de_chene", 2), ("reactif_brut", 1)], 1),
	"item:Brume_de_pavot": ("Brume de pavot", "😶‍🌫️", 0.5, "rare",
		"Une vessie fine gonflée d'une brume de pavot et de mandragore.",
		"laboratoire_d_alchimie", [("item:Capsules_de_pavot", 2), ("item:Extrait_de_mandragore", 1)], 1),
}
TAG_OBJET = "piege"

# ── 4. Animations : sprite d'un doc existant + son d'un doc existant ─────────
# id → (nom, doc sprite source, doc son source)
ANIMATIONS = {
	pieges.ANIM_DECLENCHEMENT: ("Piège déclenché", "animation:break01_a", "animation:foom_0_a"),
	pieges.ANIM_DESAMORCAGE_REUSSI: ("Désamorçage réussi", "animation:sparks_effect_a",
									 "animation:power_up_sound_v1_a"),
	pieges.ANIM_DESAMORCAGE_RATE: ("Désamorçage raté", "animation:smoke15frames_a",
								   "animation:swish_2_a"),
}
CHAMPS_SPRITE = ("fichier", "largeur", "hauteur", "colonnes", "lignes", "sens_lignes",
				 "sens_colonnes", "debut", "fin", "duree_ms", "echelle", "decalage_y")
CHAMPS_SON = ("son", "son_debut_ms", "son_fin_ms", "son_volume")


def _affiche(chemin) -> str:
	"""Chemin relatif au dépôt pour l'affichage. ⚠️ Sous Windows, `relpath` LÈVE si le chemin
	est sur un autre lecteur que le dépôt (sortie dans un dossier temporaire sur C:, dépôt
	sur Z:) : on montre alors le chemin absolu plutôt que d'échouer après avoir écrit."""
	try:
		return os.path.relpath(chemin, RACINE)
	except ValueError:
		return os.path.abspath(chemin)


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(DOSSIER_JSONS, "telluris-dump-*.json")))
	if not dumps:
		sys.exit("Aucun dump jsons/telluris-dump-*.json")
	return dumps[-1]


def docs_des_autres_imports() -> dict:
	"""`_id` → doc des `jsons/*_a_importer.json` committés (hors notre sortie) : le dump
	retarde sur le contenu livré, un `_id` réutilisé y écraserait en silence."""
	out = {}
	for chemin in glob.glob(os.path.join(DOSSIER_JSONS, "*_a_importer.json")):
		if os.path.abspath(chemin) == os.path.abspath(SORTIE):
			continue
		try:
			contenu = json.load(open(chemin, encoding="utf-8"))
		except (json.JSONDecodeError, OSError):
			continue
		for doc in (contenu if isinstance(contenu, list) else [contenu]):
			if isinstance(doc, dict) and doc.get("_id"):
				out[doc["_id"]] = doc
	return out


# ── Construction ─────────────────────────────────────────────────────────────

def docs_competences() -> list:
	out = []
	for voc in VOCATIONS:
		for slug, spec in PASSIVES.items():
			out.append({
				"_id": f"competence:{slug}_{voc}", "type": "competence",
				"nom": spec["nom"], "icon": spec["icon"],
				"description": spec["description"][voc],
				"vocation": voc, "niveau": NIVEAUX_PASSIVES[voc][slug], "mode": "passive",
				"effets": dict(spec["effets"]),
			})
		for niveau, slug, nom, icon, item, danger, zone, effets, desc, *degats in POSES[voc]:
			bloc = {"item": item, "danger": danger, "zone": zone, "portee": 1,
					"nom": nom, "icon": icon}
			if degats:
				bloc["degats"] = degats[0]
			if effets:
				bloc["effets"] = effets
			out.append({
				"_id": f"competence:pose_{slug}", "type": "competence",
				"nom": f"Pose : {nom}", "icon": icon, "description": desc,
				# PASSIVE qui ouvre l'action 🪤 (comme le désamorçage) : une active serait
				# épinglée dans la barre de slots, où `_lancer_capacite` ne sait pas la jouer.
				"vocation": voc, "niveau": niveau, "mode": "passive",
				"pose_piege": bloc,
			})
	return out


def docs_objets() -> list:
	out = []
	for item_id, (nom, icon, poids, rarete, desc, atelier, intrants, qte) in OBJETS.items():
		slug = item_id[len("item:"):]
		out.append({
			"_id": item_id, "type": "item", "nom": nom, "icon": icon, "description": desc,
			"rarete": rarete, "categorie": "outil", "sous_categorie": "", "slots": [],
			"poids": poids, "tags": [TAG_OBJET],
		})
		out.append({
			"_id": f"recette:{atelier}_{slug.lower()}", "type": "recette",
			"lieu_categorie": atelier, "objet_final": slug, "quantite_produite": qte,
			"matieres_premieres": [
				({"item": i, "quantite": q} if i.startswith("item:")
				 else {"sous_categorie": i, "quantite": q})
				for i, q in intrants],
		})
	return out


def docs_animations(base: dict) -> list:
	out = []
	for aid, (nom, sprite_id, son_id) in ANIMATIONS.items():
		sprite, son = base.get(sprite_id) or {}, base.get(son_id) or {}
		doc = {"_id": aid, "type": "animation", "nom": nom, "ancrage": "cible", "actif": True}
		doc.update({k: sprite[k] for k in CHAMPS_SPRITE if k in sprite})
		doc.update({k: son[k] for k in CHAMPS_SON if k in son})
		out.append(doc)
	return out


# ── Garde-fous ───────────────────────────────────────────────────────────────

def verifier(lot: list, base: dict) -> list:
	erreurs = []
	ids_lot = {}
	for doc in lot:
		if doc["_id"] in ids_lot:
			erreurs.append(f"`_id` en double dans le lot : {doc['_id']}")
		ids_lot[doc["_id"]] = doc

	vocs = {v.get("id") for v in (base.get("rules:vocations") or {}).get("value") or []}
	consommes = {}
	recettes_lot = {d["objet_final"] for d in lot if d["type"] == "recette"}
	recettes_base = [d for d in base.values() if d.get("type") == "recette"
					 and not d.get("sur_commande")]
	sous_cats = {d.get("sous_categorie") for d in base.values() if d.get("type") == "item"}
	intrants_atelier: dict = {}
	for r in recettes_base:
		ens = intrants_atelier.setdefault(r.get("lieu_categorie"), set())
		for m in r.get("matieres_premieres") or []:
			ens.add(m.get("item") or m.get("sous_categorie"))
		if r.get("matiere_premiere_sous_categorie"):
			ens.add(r["matiere_premiere_sous_categorie"])

	for doc in lot:
		if doc["type"] == "competence":
			if doc["vocation"] not in vocs:
				erreurs.append(f"{doc['_id']} : vocation `{doc['vocation']}` absente de rules:vocations")
			bloc = doc.get("pose_piege")
			if bloc:
				lu = pieges.normaliser_pose(bloc)
				if lu is None:
					erreurs.append(f"{doc['_id']} : bloc pose_piege rejeté par normaliser_pose")
					continue
				for cle, val in bloc.items():
					if lu.get(cle) != val:
						erreurs.append(f"{doc['_id']} : `{cle}` lu {lu.get(cle)!r} ≠ écrit {val!r}")
				item = bloc["item"]
				if item in consommes:
					erreurs.append(f"{doc['_id']} : objet {item} déjà consommé par {consommes[item]}")
				consommes[item] = doc["_id"]
				if item not in base and item not in ids_lot:
					erreurs.append(f"{doc['_id']} : objet {item} introuvable (base et lot)")
				slug = item[len("item:"):]
				if item in ids_lot and slug not in recettes_lot:
					erreurs.append(f"{item} : objet neuf sans recette")
		elif doc["type"] == "recette":
			atelier = doc["lieu_categorie"]
			if atelier not in intrants_atelier:
				erreurs.append(f"{doc['_id']} : atelier `{atelier}` sans aucune recette en base")
				continue
			for m in doc["matieres_premieres"]:
				ref = m.get("item") or m.get("sous_categorie")
				if ref.startswith("item:"):
					if ref not in base:
						erreurs.append(f"{doc['_id']} : intrant {ref} introuvable")
				elif ref not in sous_cats:
					erreurs.append(f"{doc['_id']} : sous-catégorie `{ref}` portée par aucun objet")
				if ref not in intrants_atelier[atelier]:
					erreurs.append(f"{doc['_id']} : `{ref}` n'est consommé par aucune recette "
								   f"de `{atelier}` (fausse feuille)")
		elif doc["type"] == "animation":
			if not doc.get("fichier") or not doc.get("son"):
				erreurs.append(f"{doc['_id']} : sprite ou son source introuvable")
	return erreurs


def _sans_rev(doc: dict) -> dict:
	return {k: v for k, v in (doc or {}).items() if k != "_rev"}


def main(argv=None) -> int:
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args(argv)
	chemin = args.dump or dernier_dump()
	base = {d["_id"]: d for d in json.load(open(chemin, encoding="utf-8"))["docs"]}
	lot = docs_competences() + docs_objets() + docs_animations(base)

	erreurs = verifier(lot, base)
	autres = docs_des_autres_imports()
	a_ecrire, sautes = [], []
	for doc in lot:
		for source, existants in (("base", base), ("import", autres)):
			existant = existants.get(doc["_id"])
			if existant is None:
				continue
			if _sans_rev(existant) == doc:
				sautes.append(doc["_id"])
			else:
				erreurs.append(f"{doc['_id']} : `_id` déjà pris ({source}) par un doc différent")
			break
		else:
			a_ecrire.append(doc)
	if erreurs:
		print("REFUS — rien n'est écrit :")
		for e in erreurs:
			print("  ·", e)
		return 1
	with open(args.sortie, "w", encoding="utf-8", newline="\n") as f:
		json.dump(a_ecrire, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print(f"Dump lu : {_affiche(chemin)}")
	print(f"{len(a_ecrire)} doc(s) écrits dans {_affiche(args.sortie)}"
		  + (f", {len(sautes)} déjà en base à l'identique" if sautes else ""))
	return 0


if __name__ == "__main__":
	sys.exit(main())
