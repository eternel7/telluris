#!/usr/bin/env python
# dev/gen_sons.py
# Sonorise le combat et deux donjons avec la sonothèque de `templates/resources/sounds`
# (Fantasy Sound Library + RPG Sound Pack ajoutés au 29/10).
#
# Quatre passes, chacune n'émet que ce qui MANQUE (le choix fait en base l'emporte toujours) :
#   1. CANAUX — un doc `animation:son_<canal>` SANS IMAGE (son seul, la forme voulue pour
#      `miss`/`fumble`) par canal de `COMBAT_ANIMATIONS_DEFAUT`, et la world-var renseignée
#      pour les seuls canaux encore VIDES. Sans eux, un coup d'épée ou une parade ratée
#      restaient muets : tous les défauts du dump étaient vides.
#   2. ESPÈCES — `animation: "animation:son_<famille>_<n>"` sur chaque espèce sans
#      animation, d'après sa FAMILLE (`famille_de`, première règle qui s'applique) : cris de
#      gobelin, grognements d'ogre et de géant, souffles de spectre, morsures d'insecte,
#      bruits visqueux, rugissements de dragon, grognements de bête. Les variantes d'une
#      famille sont réparties sur ses espèces par ordre d'`_id` (déterministe). Une famille
#      `None` (anges, humanoïdes armés, esprits de la nature) garde le défaut `monstre`.
#      ⚠️ Lu par `combat` APRÈS l'animation de l'arme du monstre : une arme animée prime.
#   3. PIÈGES — `animation:piege_declenche` passe de `foom_0.wav` au déclic de piège.
#   4. DONJONS — `musique` (+ `musique_volume`) sur le puits de Chartres (Minotaure) et les
#      catacombes de Lutécia : jouée en boucle par la page de combat (`donjon.musique_du_donjon`).
#
# ⚠️ `rules:world_variables` part ENTIER (PUT complet de `admin_import_bulk`) depuis le dump :
# un réglage fait dans /admin APRÈS l'export serait écrasé. Relancer sur un dump FRAIS.
# ⚠️ Les sons n'ont pas été écoutés : choisis sur leur nom ; le volume vient du niveau moyen
# MESURÉ (`ffmpeg -af volumedetect`, table `NIVEAUX_DB`), ramené vers `CIBLE_DB`. À valider à
# l'oreille dans /admin/animations.
#
# Usage : python dev/gen_sons.py
# Sortie (à coller dans /admin → Import en masse) : jsons/sons_a_importer.json

import glob
import json
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = "jsons/sons_a_importer.json"
SONS = os.path.join(RACINE, "templates", "resources", "sounds")
PREFIXE = "animation:son_"

# Niveau moyen (dB) mesuré des fichiers utilisés ici.
NIVEAUX_DB = {
	"sword sound.wav": -20.5, "battle-swing2.wav": -17.7, "Bow.wav": -27.0,
	"melee sound.wav": -20.4, "Spell_00.mp3": -26.8, "battle-sword-unsheathe2.wav": -18.2,
	"inventory-bottle.wav": -18.1, "Spell_02.mp3": -10.1, "battle-magic1.wav": -15.6,
	"Spell_04.mp3": -9.8, "battle-swing.wav": -19.9, "inventory-metal-ringing.wav": -15.8,
	"Spell_01.mp3": -25.1, "Trap_01.mp3": -18.9,
	"Dragon_Growl_00.mp3": -18.6, "Dragon_Growl_01.mp3": -21.9,
	"Goblin_00.mp3": -19.6, "Goblin_01.mp3": -20.6, "Goblin_02.mp3": -22.2,
	"Goblin_03.mp3": -23.8, "Goblin_04.mp3": -19.8,
	"npc-ogre1.wav": -16.8, "npc-ogre2.wav": -17.7, "npc-ogre3.wav": -14.8,
	"npc-ogre4.wav": -15.5, "npc-ogre5.wav": -18.8,
	"npc-giant1.wav": -17.5, "npc-giant2.wav": -16.1, "npc-giant3.wav": -19.9,
	"npc-giant4.wav": -14.6, "npc-giant5.wav": -15.2,
	"npc-wolfman.wav": -17.4, "animal melee sound.wav": -20.3,
	"npc-beetle-bite1.wav": -23.5, "npc-beetle-bite2.wav": -27.2, "npc-beetle-bite3.wav": -26.4,
	**{f"npc-shade{i}.wav": v for i, v in enumerate(
		(-17.8, -18.4, -17.9, -18.2, -20.0, -20.6, -18.0, -18.9, -17.9,
		 -20.0, -18.5, -16.7, -17.9, -17.8, -18.3), start=1)},
	**{f"npc-slime{i}.wav": v for i, v in enumerate(
		(-24.8, -26.6, -27.5, -25.1, -21.8, -25.1, -25.3, -25.2, -24.9, -23.3), start=1)},
	**{f"npc-beast{i}.wav": v for i, v in enumerate(
		(-18.9, -19.7, -19.7, -22.0, -18.6, -19.6, -18.0, -20.3, -19.0,
		 -19.1, -20.0, -18.4, -18.0, -19.4, -18.6), start=1)},
}
CIBLE_DB = -21.0


def volume_de(fichier: str) -> float:
	"""Gain qui ramène le niveau mesuré vers la cible, plafonné à 1 (on ne fait qu'atténuer)."""
	gain = 10 ** ((CIBLE_DB - NIVEAUX_DB[fichier]) / 20)
	return round(min(1.0, max(0.1, gain)), 2)


# ── 1. Canaux ────────────────────────────────────────────────────────────────────
# canal → (nom, fichier)
CANAUX = {
	"cac": ("Coup de lame", "sword sound.wav"),
	"jet": ("Arme lancée", "battle-swing2.wav"),
	"tir": ("Trait d'arc", "Bow.wav"),
	"monstre": ("Coup encaissé", "melee sound.wav"),
	"sort": ("Sortilège", "Spell_00.mp3"),
	"competence": ("Technique d'arme", "battle-sword-unsheathe2.wav"),
	"consommable": ("Fiole débouchée", "inventory-bottle.wav"),
	"soin": ("Soin", "Spell_02.mp3"),
	"buff": ("Renfort", "battle-magic1.wav"),
	"debuff": ("Malédiction", "Spell_04.mp3"),
	"miss": ("Coup dans le vide", "battle-swing.wav"),
	"fumble": ("Arme qui sonne au sol", "inventory-metal-ringing.wav"),
	"dissipation": ("Effet qui se dissipe", "Spell_01.mp3"),
}

# ── 2. Espèces ───────────────────────────────────────────────────────────────────
FAMILLES = {
	"dragon": ("Rugissement de dragon", ["Dragon_Growl_00.mp3", "Dragon_Growl_01.mp3"]),
	"gobelin": ("Cri de gobelin", [f"Goblin_0{i}.mp3" for i in range(5)]),
	"ogre": ("Grognement d'ogre", [f"npc-ogre{i}.wav" for i in range(1, 6)]),
	"geant": ("Grondement de géant", [f"npc-giant{i}.wav" for i in range(1, 6)]),
	"spectre": ("Souffle de spectre", [f"npc-shade{i}.wav" for i in range(1, 16)]),
	"insecte": ("Morsure d'insecte", [f"npc-beetle-bite{i}.wav" for i in range(1, 4)]),
	"loup": ("Grondement de loup", ["npc-wolfman.wav", "animal melee sound.wav"]),
	"visqueux": ("Bruit visqueux", [f"npc-slime{i}.wav" for i in range(1, 11)]),
	"bete": ("Grognement de bête", [f"npc-beast{i}.wav" for i in range(1, 16)]),
}
GOBELINS = {"gnome", "leprechaun", "troglodyte", "besien", "familier"}
OGRES = {"orc", "troll", "cyclope"}
GEANTS = {"minotaure", "golem_de_chair", "golem_de_fer", "golem_de_pierre", "mammouth",
		  "homme_arbre", "taureau"}
SPECTRES = {"banshee", "revenant", "horreur", "penanggalan", "sirene", "nosferatu"}
INSECTES = {"araignee", "araignee_geante", "scorpion_geant", "nuee_de_scarabees"}
LOUPS = {"lycaon", "faoladh", "ulfhedinn", "cwn_annwn", "cu_sidhe", "bete_du_gevaudan",
		 "failinis", "renard", "fauves", "cerbere", "dobhar_chu"}
VISQUEUX = {"vers_des_sables", "hydre"}


def famille_de(espece: dict) -> str | None:
	"""Famille sonore d'une espèce, ou None (le défaut `monstre` suffit). Première règle gagne."""
	slug = espece["_id"].split(":", 1)[1]
	tags = set(espece.get("tags") or [])
	if tags & {"ange", "celeste"}:
		return None
	if "draconique" in tags:
		return "dragon"
	if slug.startswith("gobelin") or slug in GOBELINS:
		return "gobelin"
	if slug in OGRES:
		return "ogre"
	if "geant" in tags or slug in GEANTS:
		return "geant"
	# Morts-vivants qui PARLENT (vampires, liches, lamies) : un souffle, pas un grognement.
	if ("incorporel" in tags or slug in SPECTRES
			or ("non_mort" in tags and "humanoide" in tags and tags & {"magique", "seduction"})):
		return "spectre"
	if "insecte" in tags or slug in INSECTES:
		return "insecte"
	if "loup" in slug or slug in LOUPS:
		return "loup"
	if slug in VISQUEUX or ("aquatique" in tags and "monstre" in tags
							and not tags & {"reptile", "humanoide"}):
		return "visqueux"
	if "non_mort" in tags or "mort_vivant" in tags:
		return "bete"
	if "humanoide" in tags or tags & {"esprit", "elementaire", "feerique"}:
		return None
	return "bete"


# ── 3-4. Pièges et donjons ───────────────────────────────────────────────────────
PIEGE = ("animation:piege_declenche", "foom_0.wav", "Trap_01.mp3")
# Musiques : une ambiance déjà en sonothèque (`dungeon_ambient_1.ogg`, 94 s) pour le
# labyrinthe, la grotte qui goutte du pack Fantasy (`Ambience_Cave_00.mp3`, 55 s) pour les
# catacombes humides. Volumes : niveaux mesurés −29,7 et −22,7 dB.
MUSIQUES = {
	"donjon:puits_de_chartres": ("dungeon_ambient_1.ogg", 0.6),
	"donjon:catacombes_de_lutecia": ("Ambience_Cave_00.mp3", 0.45),
}


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	return dumps[-1]


def charger(chemin: str) -> list:
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def animation_son(_id: str, nom: str, fichier: str) -> dict:
	"""Doc `animation:*` SANS image : le tempo du journal reste `duree_ms`, le son sonne
	par-dessus (cf. `combat_telluris.jouerVfx`)."""
	return {
		"_id": _id, "type": "animation", "nom": nom + " (sons)", "fichier": "",
		"colonnes": 1, "lignes": 1, "debut": 0, "fin": 0, "duree_ms": 600,
		"ancrage": "cible", "actif": True,
		"son": fichier, "son_debut_ms": 0, "son_fin_ms": 0, "son_volume": volume_de(fichier),
	}


def _sans_rev(doc: dict) -> dict:
	return {k: v for k, v in doc.items() if k != "_rev"}


def generer(docs: list) -> list:
	base = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}
	sortie = []

	def emettre_animation(doc):
		if doc["_id"] in base:     # déjà en base : ses réglages ont pu être retouchés
			return
		sortie.append(doc)

	# 1. Canaux
	for canal, (nom, fichier) in CANAUX.items():
		emettre_animation(animation_son(f"{PREFIXE}{canal}", nom, fichier))
	wv = base.get("rules:world_variables")
	if not wv or not isinstance(wv.get("value"), dict):
		raise SystemExit("ERREUR : rules:world_variables absent du dump.")
	wv = json.loads(json.dumps(wv))
	defauts = dict(wv["value"].get("COMBAT_ANIMATIONS_DEFAUT") or {})
	change = False
	for canal in CANAUX:
		if not str(defauts.get(canal) or "").strip():
			defauts[canal] = f"{PREFIXE}{canal}"
			change = True
	if change:
		wv["value"]["COMBAT_ANIMATIONS_DEFAUT"] = defauts
		sortie.append(_sans_rev(wv))

	# 2. Espèces
	par_famille = {}
	for d in sorted((d for d in base.values() if d.get("type") == "espece"), key=lambda d: d["_id"]):
		if str(d.get("animation") or "").strip():
			continue
		f = famille_de(d)
		if f:
			par_famille.setdefault(f, []).append(d)
	for f, especes in sorted(par_famille.items()):
		nom, fichiers = FAMILLES[f]
		utilises = set()
		for i, e in enumerate(especes):
			n = i % len(fichiers)
			utilises.add(n)
			e = json.loads(json.dumps(e))
			e["animation"] = f"{PREFIXE}{f}_{n + 1:02d}"
			sortie.append(_sans_rev(e))
		for n in sorted(utilises):
			emettre_animation(animation_son(f"{PREFIXE}{f}_{n + 1:02d}", nom, fichiers[n]))

	# 3. Pièges
	piege = base.get(PIEGE[0])
	if piege and piege.get("son") == PIEGE[1]:
		piege = json.loads(json.dumps(piege))
		piege["son"] = PIEGE[2]
		piege["son_volume"] = volume_de(PIEGE[2])
		sortie.append(_sans_rev(piege))

	# 4. Donjons
	for did, (fichier, volume) in MUSIQUES.items():
		d = base.get(did)
		if not d:
			raise SystemExit(f"ERREUR : {did} absent du dump.")
		if d.get("musique"):
			continue
		d = json.loads(json.dumps(d))
		d["musique"] = fichier
		d["musique_volume"] = volume
		sortie.append(_sans_rev(d))
	return sortie


def verifier(sortie: list):
	"""Tout fichier cité existe ; aucun `_id` en double."""
	presents = set(os.listdir(SONS))
	cites = {d["son"] for d in sortie if d.get("type") == "animation"}
	cites |= {d["musique"] for d in sortie if d.get("type") == "donjon"}
	manquants = sorted(cites - presents)
	if manquants:
		raise SystemExit(f"ERREUR : sons absents de templates/resources/sounds : {manquants}")
	ids = [d["_id"] for d in sortie]
	if len(ids) != len(set(ids)):
		raise SystemExit("ERREUR : _id en double dans la sortie.")


def main():
	dump = _dump_le_plus_recent()
	sortie = generer(charger(dump))
	verifier(sortie)
	if not sortie:
		print(f"Rien à émettre ({os.path.basename(dump)}) : tout est déjà sonorisé.")
		return
	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	compte = {}
	for d in sortie:
		compte[d.get("type")] = compte.get(d.get("type"), 0) + 1
	print(f"{SORTIE} : {len(sortie)} docs {compte} (depuis {os.path.basename(dump)})")


if __name__ == "__main__":
	main()
