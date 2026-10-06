#!/usr/bin/env python
# dev/gen_animations_capacites.py
# PROPOSE une animation (image + son) à chaque sort et compétence ACTIVE qui n'en a pas.
#
# Deux étages :
#   1. THÈMES — un doc `animation:capa_<thème>` par thème (lame, saignée, feu, givre, soin
#      sacré, portail infernal…). Chacun est la COPIE d'une feuille déjà réglée à l'aperçu de
#      /admin/animations (grille, découpe, durée, échelle, décalages) à laquelle on ajoute un
#      son de `templates/resources/sounds`, plus quelques retouches (`retouches`) : trajectoire
#      d'un projectile, orientation sur l'axe lanceur → cible, échelle d'une zone.
#   2. AFFECTATION — `animation: "animation:capa_<thème>"` posé sur chaque capacité de la table.
#
# ⚠️ LA TABLE EST EXHAUSTIVE : chaque sort et chaque compétence `active` du dump SANS
# `animation` doit y figurer. Le script ÉCHOUE sur une capacité non classée, ou sur une entrée
# de la table absente du dump. Une capacité qui a DÉJÀ une animation n'est jamais touchée (le
# choix fait en base l'emporte), même si la table la cite. Les compétences PASSIVES sont hors
# table : aucune résolution de coup ne les joue.
#
# ⚠️ Un thème déjà présent en base n'est PAS réécrit : ses réglages ont pu être retouchés à
# l'aperçu, et `admin_import_bulk` fait un PUT COMPLET. Seuls les thèmes neufs sont émis.
#
# ⚠️ POURQUOI UN SCRIPT : même raison que les autres `gen_*` — chaque capacité est RELUE depuis
# le dump le plus récent et on n'y injecte que `animation` (placé après `icon`) : régénération
# idempotente, à relancer sur un dump FRAIS.
#
# ⚠️ Le son n'a pas été écouté : sons et découpes (`son_debut_ms`/`son_fin_ms`) sont choisis
# sur le nom et l'enveloppe des fichiers. À valider à l'oreille dans /admin/animations.
#
# Usage : python dev/gen_animations_capacites.py
# Sortie (à coller dans /admin → Import en masse) :
#   jsons/animations_capacites_a_importer.json

import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = "jsons/animations_capacites_a_importer.json"
SONS = os.path.join(RACINE, "templates", "resources", "sounds")
PREFIXE = "animation:capa_"

# Sons de la sonothèque (durées mesurées : 17.mp3 1,4 s ; power_up v1-v3 ≈ 0,9 s de signal
# puis silence ; power_up v0 ≈ 2,8 s, coupé à 1,5 s ; foom 1,7 s ; les autres < 0,7 s).
SON_LAME = "sword sound.wav"
SON_CHOC = "melee sound.wav"
SON_BETE = "animal melee sound.wav"
SON_ARC = "Bow.wav"
SON_FEU = "foom_0.wav"
SON_MAGIE = "17.mp3"
SON_SOUFFLE_COURT = "swish_2.wav"
SON_SOUFFLE = "swish_3.wav"
SON_SIFFLEMENT = "swish_4.wav"
SON_POUVOIR_LONG = "power_up_sound_v0.ogg"
SON_POUVOIR_CLAIR = "power_up_sound_v1.ogg"
SON_POUVOIR_DOUX = "power_up_sound_v2.ogg"
SON_POUVOIR_SOMBRE = "power_up_sound_v3.ogg"

# Orienté sur l'axe lanceur → cible, sans trajectoire (cône, éclair, jet).
ORIENTE = {"rotation_auto": True}

# thème → (nom, feuille de base, son, son_fin_ms, volume, retouches)
# `son_fin_ms = 0` = jusqu'au bout du fichier.
THEMES = {
	# ── Armes et corps ───────────────────────────────────────────────────────────
	"lame": ("Lame : estafilade et éclat", "animation:256_b", SON_LAME, 0, 0.9, {}),
	"saignee": ("Lame : plaie qui gicle", "animation:blood_hit_06_a", SON_LAME, 0, 0.9, {}),
	"coup_lourd": ("Coup lourd : impact étoilé", "animation:shards02_a", SON_CHOC, 0, 1.0, {}),
	"balayage": ("Balayage : croissant de lame", "animation:hit10_a", SON_SOUFFLE, 0, 1.0, {}),
	"poing": ("Poing : onde d'impact", "animation:splash04_a", SON_CHOC, 0, 1.0, {}),
	"tir": ("Tir : trait qui frappe", "animation:hit_yellow_b", SON_ARC, 0, 1.0, {}),
	"griffe": ("Griffe : lacération", "animation:hit11_a", SON_BETE, 0, 1.0, {}),
	"poudre": ("Poudre jetée au visage", "animation:smoke15frames_a", SON_SOUFFLE_COURT, 0, 1.0, {}),
	"garde": ("Garde fermée : cercle d'acier", "animation:circle02_a", SON_LAME, 0, 0.7, {}),
	"lame_sacree": ("Lame sacrée : éclat doré", "animation:hit_yellow_a", SON_LAME, 0, 1.0, {}),
	"tueur_demon": ("Tueur de démon : vague tranchante", "animation:shockwave_magic_a",
					SON_LAME, 0, 1.0, ORIENTE),
	# ── Éléments ─────────────────────────────────────────────────────────────────
	"feu": ("Feu : brasier qui éclate", "animation:explosion25_a", SON_FEU, 0, 0.9, {}),
	"explosion_feu": ("Feu : explosion de zone", "animation:boom3_a", SON_FEU, 0, 1.0, {}),
	"meteore": ("Feu : impact du ciel", "animation:exp2_0_a", SON_FEU, 0, 1.0, {"echelle": 2.2}),
	"souffle_feu": ("Feu : nappe soufflée", "animation:shockwave_fire_a", SON_FEU, 0, 0.9, ORIENTE),
	"soufre": ("Soufre : haleine d'en bas", "animation:shockwave_fire_smoke_a", SON_FEU, 0, 0.8,
			   ORIENTE),
	# La comète est dessinée tête À GAUCHE : 180° la fait voler tête en avant.
	"projectile_infernal": ("Feu infernal : comète lancée",
							"animation:spritesheet_512px_by_197px_per_frame_red_a", SON_FEU, 0, 0.9,
							{"depart_ancrage": "acteur", "duree_trajet_ms": 500, "rotation": 180,
							 "rotation_auto": True, "duree_ms": 400}),
	"manteau_feu": ("Feu : manteau de braise", "animation:particlefx_10_a", SON_FEU, 0, 0.7, {}),
	"givre": ("Givre : cristaux qui saisissent", "animation:19_freezing_spritesheet_a", SON_MAGIE, 0,
			  0.8, {}),
	"eau": ("Eau : jet sous pression", "animation:preset_shockwave_blueish_a", SON_SOUFFLE, 0, 1.0,
			ORIENTE),
	"vent": ("Vent : lame d'air", "animation:14_phantom_spritesheet_a", SON_SIFFLEMENT, 0, 1.0, {}),
	"roc": ("Roc : éclats de pierre", "animation:shards01_a", SON_CHOC, 0, 1.0, {}),
	"foudre": ("Foudre : arc électrique", "animation:shock_a", SON_MAGIE, 0, 0.9, ORIENTE),
	# ── Arcanes, illusions, ombres ───────────────────────────────────────────────
	"arcane": ("Arcanes : implosion violette", "animation:17_implode002purple_b", SON_MAGIE, 0, 0.9,
			   {}),
	"illusion": ("Illusion : boucle hypnotique", "animation:2_magic8_spritesheet_a",
				 SON_POUVOIR_SOMBRE, 0, 0.7, {}),
	"illusion_zone": ("Illusion : scène en alvéoles", "animation:31_000j_instaroutarea4infinity_a",
					  SON_POUVOIR_SOMBRE, 0, 0.7, {}),
	"eblouissant": ("Éclat éblouissant", "animation:fx_a", SON_MAGIE, 0, 0.9, {}),
	"spectre": ("Spectre : apparition", "animation:18_midnight_spritesheet_a", SON_MAGIE, 0, 0.8, {}),
	"ombre": ("Ombre : implosion grise", "animation:17_implode002darkgrey_b", SON_MAGIE, 0, 0.8, {}),
	"drain": ("Drain : tourbillon de sang", "animation:13_vortex_spritesheet_a", SON_MAGIE, 0, 0.9, {}),
	"tombeau": ("Tombeau : anneau de poussière", "animation:particlefx_02_a", SON_MAGIE, 0, 0.8, {}),
	"poison": ("Poison : corruption verdâtre", "animation:17_felspell_spritesheet_a", SON_MAGIE, 0,
			   0.7, {}),
	"marque": ("Marque du traqueur", "animation:0_a", SON_MAGIE, 0, 0.8, {}),
	# ── Sainte ───────────────────────────────────────────────────────────────────
	"lumiere": ("Lumière : implosion dorée", "animation:17_implode002yellow_b", SON_MAGIE, 0, 0.9, {}),
	"lumiere_zone": ("Lumière : couronne de zone", "animation:particlefx_13_a", SON_MAGIE, 0, 0.9, {}),
	"soin_sacre": ("Soin sacré : étincelles", "animation:heal_a", SON_POUVOIR_CLAIR, 0, 0.8, {}),
	"soin_vague": ("Soin : onde de lumière", "animation:effect95_a", SON_POUVOIR_CLAIR, 0, 0.8, {}),
	"aura_sacree": ("Aura sacrée : ailes dorées", "animation:wing_part_2_a", SON_POUVOIR_LONG, 1500,
					0.7, {}),
	"lien": ("Lien de vie : fil d'or", "animation:particlefx_01_a", SON_POUVOIR_CLAIR, 0, 0.8, {}),
	# ── Nature et totems ─────────────────────────────────────────────────────────
	"soin_nature": ("Soin : sève verte", "animation:17_implode002green_b", SON_POUVOIR_DOUX, 0, 0.8,
					{}),
	"nature_buff": ("Nature : souffle de feuilles", "animation:green_effect_b", SON_POUVOIR_DOUX, 0,
					0.7, {}),
	"source": ("Source vive : bulles", "animation:air_bubbles_01_a", SON_POUVOIR_CLAIR, 0, 0.7, {}),
	"totem": ("Totem : esprit qui monte", "animation:effect47_a", SON_POUVOIR_DOUX, 0, 0.8, {}),
	# ── Soi : auras, gardes, transes ─────────────────────────────────────────────
	"bouclier": ("Bouclier : cercle de protection", "animation:8_protectioncircle_spritesheet_a",
				 SON_POUVOIR_DOUX, 0, 0.8, {}),
	"rage": ("Rage : implosion rouge", "animation:17_implode002red_b", SON_POUVOIR_SOMBRE, 0, 0.8, {}),
	"aura_bataille": ("Aura de bataille : colonne", "animation:aura38_a", SON_POUVOIR_LONG, 1500, 0.7,
					  {}),
	"demon_buff": ("Démon : anneau d'ombre", "animation:particlefx_12_a", SON_POUVOIR_SOMBRE, 0, 0.8,
				   {}),
	"furtif": ("Furtivité : fondu dans la fumée", "animation:smoke30frames_a", SON_SOUFFLE_COURT, 0,
			   0.8, {}),
	"double": ("Doubles : alvéoles miroitantes", "animation:31_000j_instaroutarea4darkgrey_a",
			   SON_SOUFFLE_COURT, 0, 0.8, {}),
	"chant": ("Chant : notes en bulles", "animation:20_magicbubbles_spritesheet_a", SON_POUVOIR_CLAIR,
			  0, 0.7, {}),
	"meditation": ("Méditation : lueur intérieure", "animation:light_glow_effect_b",
				   SON_POUVOIR_CLAIR, 0, 0.7, {}),
	"alchimie": ("Alchimie : fiole bue", "animation:magic_effect_a", SON_POUVOIR_CLAIR, 0, 0.7, {}),
	"enchantement": ("Enchantement : anneau d'arcanes", "animation:particlefx_07_a", SON_POUVOIR_LONG,
					 1500, 0.7, {}),
	"saut": ("Saut : téléportation", "animation:teleporter_01_a", SON_SIFFLEMENT, 0, 1.0, {}),
	# ── Invocations (jouées sur le lanceur) ──────────────────────────────────────
	"portail_infernal": ("Invocation : portail de braise", "animation:particlefx_09_a", SON_FEU, 0,
						 0.9, {}),
	"appel_sauvage": ("Invocation : la bête accourt", "animation:particlefx_05_a", SON_BETE, 0, 1.0,
					  {}),
	"levee_morts": ("Invocation : la terre rend ses morts", "animation:particlefx_04_a", SON_MAGIE, 0,
					0.9, {}),
	"descente_celeste": ("Invocation : descente céleste", "animation:wing_part_1_a",
						 SON_POUVOIR_LONG, 2000, 0.8, {}),
}

_INVOC_DEMON = ("conclave_de_la_destinee", "contrat_mineur", "couronne_de_l_enfer",
				"couvee_infernale", "ecuries_de_l_abime", "essaim_de_besiens", "gardien_des_portes",
				"ifrit_enchaine", "legion_de_l_abime", "main_de_la_destinee", "murmure_de_la_succube",
				"pacte_du_servant", "rupture_du_sceau", "serment_du_demon_guerrier",
				"songe_des_incubes")
_INVOC_NATURE = ("anneaux_du_serpent_geant", "charge_du_sanglier", "ciel_de_serres",
				 "envol_du_griffon", "eveil_de_l_homme_arbre", "fauve_totem", "hurlement_du_loup",
				 "marche_des_mammouths", "meute_grise", "reveil_de_l_ours", "serres_de_l_aigle_geant",
				 "tetes_de_l_hydre")
_INVOC_NECRO = ("ailes_de_charogne", "bandelettes_du_tombeau", "chant_de_la_lhamia",
				"cortege_des_fantomes", "faim_de_la_goule", "horde_des_fosses", "lamentation",
				"le_comte_s_eveille", "levee_des_ossements", "ordre_sanglant", "seigneurie_du_sang",
				"soif_du_nosferatu", "soif_liee", "visage_de_l_horreur", "volee_funebre")
_INVOC_SAINTE = ("descente_du_seraphin", "destrier_celeste", "gardien_du_temple",
				 "incarnation_divine", "la_tarasque_domptee", "licorne_immaculee", "main_de_l_ordre",
				 "messager_aile", "sentence_de_justice", "sentinelle_du_parvis", "temoin_celeste",
				 "verite_gravee")

# _id de capacité → thème.
AFFECTATION = {
	# ── Compétences actives, par vocation ────────────────────────────────────────
	"competence:execution": "saignee",
	"competence:frappe_sournoise": "saignee",
	"competence:furtivite": "furtif",
	"competence:maitre_lames": "lame",
	"competence:venin_de_contact": "poison",
	"competence:annonce_de_sang": "rage",
	"competence:frenesie": "rage",
	"competence:spasme_de_furie": "coup_lourd",
	"competence:tourbillon_de_lames": "balayage",
	"competence:esprit_antique": "totem",
	"competence:esprit_protecteur": "soin_nature",
	"competence:forme_esprit_totem": "totem",
	"competence:homme_bete": "totem",
	"competence:griffe_du_familier": "griffe",
	"competence:invocation_majeure": "portail_infernal",
	"competence:pacte_de_sang": "rage",
	"competence:homme_tempete": "foudre",
	"competence:seve_vive": "soin_nature",
	"competence:trait_du_chasseur": "tir",
	"competence:botte_de_mousquetaire": "lame",
	"competence:coup_de_l_executeur": "saignee",
	"competence:fente": "lame",
	"competence:parade_de_maitre": "garde",
	"competence:courroux_des_elements": "meteore",
	"competence:decharge_primordiale": "foudre",
	"competence:manteau_elementaire": "manteau_feu",
	"competence:baume_de_campagne": "soin_nature",
	"competence:fleche_de_franc_archer": "tir",
	"competence:tir_d_elite": "tir",
	"competence:tir_precis": "tir",
	"competence:trait_du_chasseur_de_monstres": "tir",
	"competence:balayage": "balayage",
	"competence:brise_ligne": "coup_lourd",
	"competence:coup_de_mercenaire": "lame",
	"competence:cri_de_ralliement": "aura_bataille",
	"competence:frappe_puissante": "coup_lourd",
	"competence:garde_de_fer": "garde",
	"competence:double_illusoire": "double",
	"competence:mirage_paralysant": "illusion",
	"competence:theatre_des_ombres": "illusion_zone",
	"competence:elixir_du_maitre_artisan": "alchimie",
	"competence:formule_de_l_alchimiste": "alchimie",
	"competence:oeuvre_de_l_enchanteur": "enchantement",
	"competence:egide_arcanique": "bouclier",
	"competence:lame_enchantee": "aura_bataille",
	"competence:rupture_arcanique": "arcane",
	"competence:ballade_inspirante": "chant",
	"competence:chant_du_prodige": "illusion_zone",
	"competence:hymne_de_l_etoile": "chant",
	"competence:mort_de_rire": "illusion",
	"competence:refrain_de_ralliement": "chant",
	"competence:garde_du_pelerin": "garde",
	"competence:paume_de_force": "poing",
	"competence:poing_de_legende": "poing",
	"competence:souffle_du_sensei": "meditation",
	"competence:souffle_partage": "meditation",
	"competence:drain_vital": "drain",
	"competence:etreinte_du_tombeau": "tombeau",
	"competence:toucher_du_sepulcre": "ombre",
	"competence:frappe_du_champion": "lame_sacree",
	"competence:imposition_des_mains": "soin_sacre",
	"competence:lumiere_du_purificateur": "lumiere_zone",
	"competence:serment_du_martyr": "lien",
	"competence:benediction_du_prophete": "soin_sacre",
	"competence:main_du_guerisseur": "soin_sacre",
	"competence:oracle": "aura_sacree",
	"competence:fer_de_l_inquisiteur": "lame_sacree",
	"competence:marque_du_traqueur": "marque",
	"competence:tueur_de_demon": "tueur_demon",
	"competence:arme_de_justice": "aura_sacree",
	"competence:bras_divin": "lame_sacree",
	"competence:litanie_protectrice": "bouclier",
	"competence:verdict": "lame_sacree",
	"competence:coup_de_coupe_jarret": "saignee",
	"competence:coup_du_bandit": "lame",
	"competence:fuite_de_maraudeur": "furtif",
	"competence:poudre_aveuglante": "poudre",
	# ── Sorts : Bataille ─────────────────────────────────────────────────────────
	"sort:aura_de_devotion": "aura_bataille",
	"sort:bouclier_magique": "bouclier",
	"sort:eclair_siphonnant": "foudre",
	"sort:flammerole": "feu",
	"sort:force_partagee": "aura_bataille",
	"sort:garde_parfaite": "bouclier",
	"sort:jugement_sacre": "arcane",
	"sort:maladresse": "illusion",
	"sort:saut": "saut",
	"sort:sommeil_pesant": "illusion",
	# ── Sorts : Démonologie ──────────────────────────────────────────────────────
	**{f"sort:{s}": "portail_infernal" for s in _INVOC_DEMON},
	"sort:ecailles_du_servant": "demon_buff",
	"sort:flamme_infernale": "projectile_infernal",
	"sort:flegme_demoniaque": "demon_buff",
	"sort:malediction_mineure": "poison",
	"sort:pacte_de_sang": "rage",
	"sort:souffle_de_soufre": "soufre",
	"sort:vigueur_demoniaque": "rage",
	# ── Sorts : Illusoire ────────────────────────────────────────────────────────
	"sort:eclat_eblouissant": "eblouissant",
	"sort:formule_de_clairvoyance": "meditation",
	"sort:leurre_spectral": "spectre",
	"sort:meditation_profonde": "meditation",
	"sort:mot_de_pouvoir": "arcane",
	"sort:silhouettes_trompeuses": "double",
	"sort:trouble_magique": "illusion",
	"sort:zone_de_silence": "furtif",
	# ── Sorts : Nature ───────────────────────────────────────────────────────────
	**{f"sort:{s}": "appel_sauvage" for s in _INVOC_NATURE},
	"sort:amitie_des_betes": "nature_buff",
	"sort:antidote_sylvestre": "nature_buff",
	"sort:baume_de_seve": "soin_nature",
	"sort:fracas_tellurique": "foudre",
	"sort:guerison_des_animaux": "soin_nature",
	"sort:morsure_de_ronces": "griffe",
	"sort:morsure_totemique": "griffe",
	"sort:oeil_de_la_chouette": "nature_buff",
	"sort:regain_sylvestre": "soin_nature",
	"sort:seve_vivifiante": "soin_nature",
	"sort:souffle_ancestral": "soin_nature",
	"sort:source_vive": "source",
	"sort:transe_du_totem": "totem",
	# ── Sorts : Nécromancie ──────────────────────────────────────────────────────
	**{f"sort:{s}": "levee_morts" for s in _INVOC_NECRO},
	"sort:baiser_du_vampire": "drain",
	"sort:etreinte_sepulcrale": "ombre",
	"sort:main_de_venin": "poison",
	"sort:mortis": "furtif",
	"sort:regard_glacial": "givre",
	"sort:toucher_devitalisant": "ombre",
	"sort:trait_mortifere": "ombre",
	# ── Sorts : Sainte ───────────────────────────────────────────────────────────
	**{f"sort:{s}": "descente_celeste" for s in _INVOC_SAINTE},
	"sort:benir": "aura_sacree",
	"sort:fer_et_priere": "lame_sacree",
	"sort:feu_purificateur": "lumiere",
	"sort:grace_divine": "aura_sacree",
	"sort:lien_du_paladin": "lien",
	"sort:lumiere_purificatrice": "lumiere",
	"sort:revigore": "soin_sacre",
	"sort:sceau_de_protection": "bouclier",
	"sort:vague_de_soin": "soin_vague",
	"sort:verdict_de_lumiere": "lame_sacree",
	# ── Sorts : Élémentaire ──────────────────────────────────────────────────────
	"sort:boule_de_feu": "explosion_feu",
	"sort:eclat_de_givre": "givre",
	"sort:eclat_rocheux": "roc",
	"sort:jet_d_eau": "eau",
	"sort:lame_de_vent": "vent",
	"sort:meteore": "meteore",
	"sort:souffle_de_feu": "souffle_feu",
}


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	return dumps[-1]


def charger(chemin: str) -> list:
	"""Docs d'un export admin ou d'un dump : tableau nu, ou {"docs": [...]}."""
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def _est_cible(doc: dict) -> bool:
	"""Une capacité que le combat peut JOUER : tout sort, toute compétence active."""
	if doc.get("type") == "sort":
		return True
	return doc.get("type") == "competence" and doc.get("mode") == "active"


def _avec_animation(doc: dict, anim_id: str) -> dict:
	"""Copie du doc avec `animation` juste après `icon` (ou en fin de doc sans icône)."""
	out = {}
	for cle, valeur in doc.items():
		if cle == "animation":
			continue
		out[cle] = valeur
		if cle == "icon":
			out["animation"] = anim_id
	out.setdefault("animation", anim_id)
	return out


def _doc_theme(theme: str, base: dict) -> dict:
	nom, _base_id, son, son_fin, volume, retouches = THEMES[theme]
	doc = {k: v for k, v in base.items() if k != "_rev"}
	doc.update({
		"_id": PREFIXE + theme,
		"type": "animation",
		"nom": f"{nom} (capacités)",
		"son": son,
		"son_debut_ms": 0,
		"son_fin_ms": son_fin,
		"son_volume": volume,
		"actif": True,
	})
	doc.update(retouches)
	return doc


def main() -> None:
	erreurs = []
	for theme, (_nom, _base, son, _fin, volume, _r) in THEMES.items():
		if not os.path.isfile(os.path.join(SONS, son)):
			erreurs.append(f"thème {theme} : son introuvable {son}")
		if not 0 <= volume <= 1:
			erreurs.append(f"thème {theme} : volume hors [0,1]")
	inconnus = sorted({t for t in AFFECTATION.values() if t not in THEMES})
	if inconnus:
		erreurs.append("thèmes inconnus dans AFFECTATION : " + ", ".join(inconnus))
	orphelins = sorted(set(THEMES) - set(AFFECTATION.values()))
	if orphelins:
		erreurs.append("thèmes jamais affectés : " + ", ".join(orphelins))

	source = _dump_le_plus_recent()
	docs = charger(source)
	par_id = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("_id")}

	for theme, (_nom, base_id, *_reste) in THEMES.items():
		base = par_id.get(base_id)
		if not base or base.get("type") != "animation":
			erreurs.append(f"thème {theme} : feuille de base absente du dump ({base_id})")
		elif not base.get("actif") or not base.get("fichier"):
			erreurs.append(f"thème {theme} : feuille de base inactive ou sans image ({base_id})")

	capacites = {i: d for i, d in par_id.items() if _est_cible(d)}
	a_classer = sorted(i for i, d in capacites.items() if not d.get("animation"))
	manquantes = [i for i in a_classer if i not in AFFECTATION]
	fantomes = sorted(i for i in AFFECTATION if i not in capacites)
	if manquantes:
		erreurs.append("capacités SANS animation absentes de la table (à classer) :\n   "
					   + ", ".join(manquantes))
	if fantomes:
		erreurs.append("capacités de la table absentes du dump (ou passives) :\n   "
					   + ", ".join(fantomes))
	if erreurs:
		print("\n".join("ERREUR : " + e for e in erreurs))
		sys.exit(1)

	sortie, themes_emis, themes_existants, compte = [], [], [], {}
	for theme in sorted(THEMES):
		anim_id = PREFIXE + theme
		if anim_id in par_id:
			themes_existants.append(anim_id)
			continue
		sortie.append(_doc_theme(theme, par_id[THEMES[theme][1]]))
		themes_emis.append(anim_id)
	deja = 0
	for cap_id in sorted(AFFECTATION):
		doc = capacites[cap_id]
		if doc.get("animation"):
			deja += 1
			continue
		theme = AFFECTATION[cap_id]
		sortie.append(_avec_animation(doc, PREFIXE + theme))
		compte[theme] = compte.get(theme, 0) + 1

	chemin = os.path.join(RACINE, SORTIE)
	with open(chemin, "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"relu {os.path.relpath(source, RACINE)} ({len(capacites)} sorts + compétences actives)")
	print(f"écrit {SORTIE} : {len(themes_emis)} thème(s) d'animation, "
		  f"{sum(compte.values())} capacité(s) liée(s)")
	if themes_existants:
		print(f"   {len(themes_existants)} thème(s) déjà en base, non réécrit(s)")
	if deja:
		print(f"   {deja} capacité(s) de la table déjà animée(s) en base, laissée(s) telle(s)")
	for theme in sorted(compte, key=lambda t: (-compte[t], t)):
		print(f"   {theme:20s} {compte[theme]:3d}  ← {THEMES[theme][1]} + {THEMES[theme][2]}")


if __name__ == "__main__":
	main()
