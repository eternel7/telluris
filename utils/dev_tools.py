"""Lancement des outils de `dev/` depuis l'écran d'administration.

POURQUOI ICI ET PAS DANS UN ROUTER : le CATALOGUE est de la donnée pure (aucune DB, aucun
I/O au chargement) et `main.py` ne garde que des endpoints minces — même partage que
`utils/lint_dialogues.py`, dont la logique sert à la fois au CLI `dev/` et au bouton de
`/admin`.

⚠️ **LISTE BLANCHE, JAMAIS UN CHEMIN VENU DU CLIENT.** Le client n'envoie qu'un `id` du
catalogue ; l'argv est écrit ici, en dur. Un endpoint qui accepterait un nom de fichier —
même « juste sous dev/ » — serait une exécution de code arbitraire derrière un cookie admin.
Aucun `shell=True` non plus : `Popen` reçoit une LISTE, donc rien n'est interprété.

⚠️ **UN SEUL RUN À LA FOIS** (`_VERROU`) : deux générateurs écrivent volontiers le même
`jsons/*_a_importer.json`, et le journal est un tampon unique. Le second départ est refusé
(409) tant que le premier n'est pas terminé.
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import OrderedDict

# Racine du dépôt (ce fichier est dans utils/) — cwd de tout ce qu'on lance : les scripts
# écrivent dans `jsons/` en chemin RELATIF, les lancer d'ailleurs les ferait échouer.
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Tampon de journal : au-delà, les plus VIEILLES lignes tombent (`base` mémorise combien,
# pour que les offsets du client restent absolus et qu'il sache qu'il a perdu du texte).
MAX_LIGNES = 4000


def _py(script: str, *args: str) -> list:
	"""argv d'un script Python du dépôt.

	⚠️ **`-u` n'est pas décoratif** : le stdout d'un processus fils redirigé vers un tube est
	BLOC-bufférisé, donc un `print` par doc traité n'arriverait qu'à la toute fin — un « tail »
	muet pendant deux minutes puis tout d'un coup. C'est le piège nº 1 de ce genre d'écran.
	⚠️ `sys.executable` et non « python » : c'est l'interpréteur qui fait tourner l'app."""
	return [sys.executable, "-u", os.path.join("dev", script), *args]


def _node(script: str, *args: str) -> list:
	return ["node", os.path.join("dev", script), *args]


def _module(mod: str, *args: str) -> list:
	"""argv d'un module Python lancé par `-m` (pytest) — même `-u` que `_py`, même raison."""
	return [sys.executable, "-u", "-m", mod, *args]


# ── Outils PARAMÉTRÉS (/admin/lieux) ─────────────────────────────────────────
# Une entrée à `params` reçoit des valeurs du client — et c'est précisément ce que la liste
# blanche interdisait jusqu'ici. Elle le reste : le client n'envoie JAMAIS un chemin ni un
# morceau d'argv. Chaque valeur est typée et VALIDÉE ici (`valider_params`), l'argv est bâti
# par `argv_fn` depuis ces valeurs, et les fichiers qu'un outil lit (dump, spec) sont écrits
# par le SERVEUR sous un nom qu'il choisit (`preparer`, injecté par main.py).
#
#   ville  → un `lieu:*` qui passe `ID_LIEU` ET figure parmi les villes connues
#   lieux  → liste non vide de `lieu:*` (≤ LIEUX_MAX), dédoublonnée, ordre gardé
#   json   → un OBJET JSON (≤ JSON_OCTETS_MAX), écrit dans un fichier par le serveur
#
# ⚠️ `dump_frais` : un générateur relit un DUMP pour n'injecter que son champ (CLAUDE.md §11) —
# relu sur un dump périmé, son import (PUT complet) écraserait les retouches faites depuis.
ID_LIEU = re.compile(r"^lieu:[a-z0-9_]{1,120}$")
LIEUX_MAX = 500
JSON_OCTETS_MAX = 256_000
_TYPES_PARAM = ("ville", "lieux", "json")


def est_ville(doc: dict) -> bool:
	"""Une cité gérable sur /admin/lieux. ⚠️ Lutèce n'a PAS de `categorie` (vide) : seule sa
	`sous_categorie` « capitale » la désigne — un filtre sur `categorie` seule l'oublierait."""
	return (doc.get("categorie") == "ville"
			or doc.get("sous_categorie") in ("ville", "capitale"))


def valider_params(outil: dict, brut, villes_connues=()) -> tuple:
	"""Valeurs typées d'un outil paramétré. Rend `(valeurs, None)` ou `(None, message)`."""
	attendus = {p["nom"]: p["type"] for p in outil.get("params") or []}
	if not attendus:
		return ({}, None) if not brut else (None, "Cet outil ne prend aucun paramètre.")
	if not isinstance(brut, dict):
		return None, "Paramètres : un objet est attendu."
	inconnus = sorted(set(brut) - set(attendus))
	if inconnus:
		return None, f"Paramètre(s) inconnu(s) : {', '.join(inconnus)}."
	villes = set(villes_connues or ())
	valeurs = {}
	for nom, typ in attendus.items():
		v = brut.get(nom)
		if typ == "ville":
			if not isinstance(v, str) or not ID_LIEU.match(v):
				return None, f"`{nom}` : identifiant de lieu invalide."
			if v not in villes:
				return None, f"`{nom}` : {v} n'est pas une ville connue."
		elif typ == "lieux":
			if not isinstance(v, list) or not v:
				return None, f"`{nom}` : une liste non vide d'identifiants est attendue."
			if len(v) > LIEUX_MAX:
				return None, f"`{nom}` : {len(v)} lieux, au plus {LIEUX_MAX}."
			if not all(isinstance(x, str) and ID_LIEU.match(x) for x in v):
				return None, f"`{nom}` : identifiant de lieu invalide dans la liste."
			v = list(dict.fromkeys(v))
		elif typ == "json":
			if not isinstance(v, dict):
				return None, f"`{nom}` : un objet JSON est attendu."
			if len(json.dumps(v, ensure_ascii=False).encode("utf-8")) > JSON_OCTETS_MAX:
				return None, f"`{nom}` : plus de {JSON_OCTETS_MAX // 1000} Ko."
		else:
			return None, f"Type de paramètre inconnu : {typ}."
		valeurs[nom] = v
	return valeurs, None


def spec_a_ecrire(outil: dict, valeurs: dict):
	"""Contenu du fichier de spec d'un outil à paramètre `json`, ou None.
	⚠️ La cité de la spec est la VILLE VALIDÉE, jamais celle que le JSON prétend : la spec
	collée à la main ne peut pas viser une autre ville que celle affichée."""
	nom = next((p["nom"] for p in outil.get("params") or [] if p["type"] == "json"), None)
	if not nom:
		return None
	spec = dict(valeurs[nom])
	if "ville" in valeurs:
		spec["cite"] = valeurs["ville"]
	return spec


# ── Catalogue ────────────────────────────────────────────────────────────────
# `ecrit` = ce que l'outil produit, affiché sous le sélecteur : un admin doit savoir AVANT
# de lancer si le geste est en lecture seule, s'il écrit un fichier, ou s'il touche la base.
# `danger` = confirmation exigée côté client (et seul cas qui écrit en base).
CATALOGUE = [
	{
		"id": "lint_dialogues",
		"label": "🔍 Lint des dialogues — tous les jsons/",
		"argv": _py("lint_dialogues.py"),
		"ecrit": "Lecture seule.",
		"description": "Références mortes, nœuds inatteignables, conditions inconnues, noms "
			"de PNJ en dur. Sort en code 1 s'il reste une erreur. ⚠️ Les telluris-dump-*.json "
			"sont ignorés : ce sont des archives d'états passés.",
	},
	{
		"id": "export_bestiaire",
		"label": "🐉 Export bestiaire (.xlsx)",
		"argv": _py("export_bestiaire.py"),
		"ecrit": "Écrit bestiaire.xlsx à la racine du dépôt. Lit la base.",
		"description": "Feuille d'équilibrage : attributs min/max + dérivées de combat "
			"calculées, espèces et races jouables côte à côte.",
	},
	{
		"id": "gen_marchands",
		"label": "🧑‍🌾 Générer les tenanciers génériques (pnj:marchand_*)",
		"argv": _py("gen_marchands.py"),
		"ecrit": "Écrit jsons/marchands_a_importer.json.",
		"description": "Un tenancier par catégorie de lieu marchand, avec l'arbre de dialogue "
			"de la quête de transport.",
	},
	{
		"id": "gen_jetons_especes",
		"label": "🐉 Gabarits des jetons de combat (espèces)",
		"argv": _py("gen_jetons_especes.py"),
		"ecrit": "Écrit jsons/jetons_especes_a_importer.json.",
		"description": "Pose `jeton: {taille, forme}` sur les espèces qui occupent plus d'une "
			"case (dragon 3x2, cheval 1x2…). Table exhaustive : échoue si une espèce du dump n'y "
			"est pas classée. Relit le dump le plus récent et n'injecte que ce champ : "
			"régénération idempotente.",
	},
	{
		"id": "gen_escorte_marchands",
		"label": "🧵 Ouvrir l'escorte de progéniture chez les tenanciers",
		"argv": _py("gen_escorte_marchands.py"),
		"ecrit": "Écrit jsons/marchands_escorte_a_importer.json.",
		"description": "Pose les nœuds de dialogue de l'escorte sur les 29 `pnj:marchand_*`. "
			"Relit les docs depuis le dump figé et n'y injecte que ce fragment : régénération "
			"idempotente. Sans familles écrites, ces nœuds restent inatteignables.",
	},
	{
		"id": "gen_progeniture",
		"label": "👪 Donner une famille aux tenanciers d'Auxerre",
		"argv": _py("gen_progeniture.py"),
		"ecrit": "Écrit jsons/progeniture_a_importer.json.",
		"description": "Pose le bloc `progeniture` sur l'entrée `pnj` d'une dizaine de "
			"boutiques : c'est le contenu qui allume les escortes d'enfants perdus, chez le "
			"parent comme au comptoir de la guilde.",
	},
	{
		"id": "gen_escorte_guilde",
		"label": "📖 Ouvrir le registre des disparitions au comptoir",
		"argv": _py("gen_escorte_guilde.py"),
		"ecrit": "Écrit jsons/borin_recherche_escorte_a_importer.json.",
		"description": "Pose `services.escorte.recherche` sur Borin : la guilde recense les "
			"familles de la cité qui attendent un enfant et en confie la recherche.",
	},
	{
		"id": "gen_acces_donjon",
		"label": "🗝️ Générer la chaîne d'accès du donjon-mine",
		"argv": _py("gen_acces_donjon.py"),
		"ecrit": "Écrit 3 fichiers jsons/*_a_importer.json.",
		"description": "Rang D → Borin → Gautier → George → Armand. Relit les docs depuis le "
			"dump figé et n'y injecte que le champ ajouté : régénération idempotente.",
	},
	{
		"id": "gen_relation_guilde",
		"label": "🏛️ Consolider la réputation de la guilde sur son comptoir",
		"argv": _py("gen_relation_guilde.py"),
		"ecrit": "Écrit jsons/relation_guilde_a_importer.json.",
		"description": "Pose `relation_lieu` sur la façade, la réception et le bureau du maître "
			"du Bastion : les quatre lieux partagent alors UNE cote. Relit les docs depuis le "
			"dump figé et n'y injecte que ce champ : régénération idempotente.",
	},
	{
		"id": "gen_stock_cible_ateliers",
		"label": "🏺 Débloquer le chaînage des ateliers (stock_cible)",
		"argv": _py("gen_stock_cible_ateliers.py"),
		"ecrit": "Écrit jsons/stock_cible_ateliers_a_importer.json.",
		"description": "Abaisse à 12 la cible de vitrine des intermédiaires qu'un atelier "
			"fabrique pour lui-même (manche, Table_d_harmonie, saumure…), sous le défaut de 25 : "
			"un intermédiaire est un en-cours, pas de la marchandise. Divise encore par deux le "
			"démarrage du chaînage (1re pièce à la visite 5 au lieu de 10). La BOYAUDERIE, seul "
			"métier sans aucune feuille d'appro, descend à 2 (CIBLE_PAR_CATEGORIE). Dérivé du "
			"graphe de recettes, relit le dump figé et n'injecte que `stock_cible` : idempotent.",
	},
	{
		"id": "gen_repurgateur_noire",
		"label": "🔱 Basculer le répurgateur en magie noire (+ invocations)",
		"argv": _py("gen_repurgateur_noire.py"),
		"ecrit": "Écrit jsons/repurgateur_magie_noire_a_importer.json (3 docs).",
		"description": "Le répurgateur quitte la magie Sainte pour la Démonologie du démoniste, "
			"dont il est exclu des INVOCATIONS (`familles_exclues` de rules:vocations). Recopie "
			"le doc de vocations ENTIER (PUT complet) et ajoute un sort d'invocation par école "
			"noire — sans quoi l'exclusion ne mordrait sur rien. ⚠️ Ses 3 sorts Saints ne sont PAS "
			"repris : ils restent tels quels et sortent de son répertoire (le script les liste "
			"avant l'import). Relit le dump figé : régénération idempotente.",
	},
	{
		"id": "gen_depecage_tags",
		"label": "🍖 Publier la table de dépeçage (DEPECAGE_TAGS)",
		"argv": _py("gen_depecage_tags.py"),
		"ecrit": "Écrit jsons/depecage_tags_a_importer.json (doc rules:world_variables).",
		"description": "Pousse `DEPECAGE_TAGS` + les réglages de découpe des carcasses du défaut "
			"de code vers `rules:world_variables` — le doc GAGNE toujours, donc éditer le code "
			"seul ne change rien en jeu. Imprime le diff avant d'écrire. ⚠️ Après l'import, "
			"/admin → Recharger les variables de monde, PUIS relancer la génération des "
			"portions de carcasse (leur dépeçage est baké).",
	},
	{
		"id": "gen_fabrication_matieres",
		"label": "⚒️ Ce qu'une matière apporte sur mesure (bloc `fabrication`)",
		"argv": _py("gen_fabrication_matieres.py"),
		"ecrit": "Écrit jsons/fabrication_matieres_a_importer.json (docs item enrichis).",
		"description": "Pose le bloc `fabrication` (fragment de nom + modificateurs) sur une "
			"douzaine de matières premières : c'est ce qu'elles confèrent à une pièce commandée "
			"SUR MESURE chez un grand magasin. Sans ce bloc, une matière reste utilisable mais "
			"n'apporte rien — comportement d'avant, aucune migration. ⚠️ Ne touche AUCUNE "
			"recette : ajouter un intrant ouvrirait un point de vente pour lui et risquerait la "
			"fausse feuille. Relit le dump, réémet le doc complet avec le seul champ ajouté : "
			"régénération idempotente.",
	},
	{
		"id": "gen_carcasses_parties",
		"label": "🔪 Débiter les grosses carcasses en portions",
		"argv": _py("gen_carcasses_parties.py"),
		"ecrit": "Écrit jsons/carcasses_parties_a_importer.json.",
		"description": "Les 20 carcasses de plus de 100 kg sont intransportables (charge = F×5) "
			"et ne rapportaient donc RIEN. Crée une portion par partie du corps (tête, corps, "
			"pattes, queue, ailes) avec sa propre table de dépeçage, et pose `decoupe` sur la "
			"carcasse source — le champ qui la rend découpable en jeu, à l'arme tranchante.",
	},
	{
		"id": "gen_armes_tranchantes",
		"label": "🗡️ Taguer les armes qui ont un fil (tranchant)",
		"argv": _py("gen_armes_tranchantes.py"),
		"ecrit": "Écrit jsons/armes_tranchantes_a_importer.json.",
		"description": "Pose `tranchant` sur les 40 armes capables d'ouvrir une bête (épées, "
			"couteaux, haches, lames de jet, hast à fer tranchant). Liste explicite : les armes "
			"n'ont ni sous-catégorie ni description d'où « a un fil » se déduirait.",
	},
	{
		"id": "gen_coherence_france",
		"label": "🗺️ Corriger la cohérence de lieu:france",
		"argv": _py("gen_coherence_france.py"),
		"ecrit": "Écrit jsons/france_coherence_a_importer.json et …/profils_tag_magique_….",
		"description": "La carte du monde n'avait AUCUNE ressource récoltable (tout événement "
			"`ressource` était un no-op) et trois zones posées — marais, collines, glacier — "
			"n'avaient aucune espèce, donc aucun combat. Ajoute les deux, dédoublonne les "
			"placements, et corrige `restriction_tags: [\"magie\"]` → `[\"magique\"]` sur les "
			"4 profils concernés (aucune espèce ne portait `magie`). Relit les docs depuis les "
			"sources figées : régénération idempotente.",
	},
	{
		"id": "gen_grades_france",
		"label": "⚔️ Confiner les hauts grades à la zone dangereuse (France)",
		"argv": _py("gen_grades_france.py"),
		"ecrit": "Écrit jsons/france_grades_a_importer.json.",
		"description": "Les 6 profils de niveau 5-6 étaient dans le `profil_weights` du LIEU : "
			"23 % de TOUS les monstres de la France, gobelins de la plaine compris. Les descend "
			"sur les 36 placements de `zone:tres_dangereuse` — seul endroit où "
			"`resolve_profil_weights` les lira. ⚠️ La table d'un placement REMPLACE celle du "
			"lieu, elle doit donc rester complète.",
	},
	{
		"id": "gen_lutecia",
		"label": "🏰 Donner ses zones à la capitale Lutèce",
		"argv": _py("gen_lutecia.py"),
		"ecrit": "Écrit jsons/lutecia_zones_a_importer.json.",
		"description": "Lutèce n'avait que 10 placements de forêt (6 % de la carte) et ses "
			"rencontres, copiées d'Auxerre, citaient des zones jamais posées. Ajoute les zones "
			"urbaines de capitale (cœur, politique, bas quartiers, remparts), la Seine, les "
			"faubourgs et la campagne, calés sur paris_capital.png — et contrôle que les "
			"4 portes venant de la France tombent bien dans une zone.",
	},
	{
		"id": "gen_armures",
		"label": "🛡️ Générer la passe « armures »",
		"argv": _py("gen_armures.py"),
		"ecrit": "Écrit jsons/armures_recettes_a_importer.json et …_bonus_pa_….",
		"description": "item:peaux (matière feuille) + recettes de fabrication, et bonus_pa "
			"renseigné sur les docs armure.",
	},
	{
		"id": "gen_epaulieres",
		"label": "🛡️ Générer les pièces d'épaules",
		"argv": _py("gen_epaulieres.py"),
		"ecrit": "Écrit jsons/epaulieres_a_importer.json.",
		"description": "L'emplacement « Epaules » de la silhouette n'avait AUCUN item à "
			"porter : 21 pièces (plates, mailles, cuir, fourrure, os, plumes) + leurs "
			"recettes, sur des matières auto-approvisionnées pour que les ateliers "
			"puissent réellement les produire.",
	},
	{
		"id": "gen_jardinerie",
		"label": "🌱 Générer la filière végétale (jardinerie)",
		"argv": _py("gen_jardinerie.py"),
		"ecrit": "Écrit jsons/jardinerie_a_importer.json.",
		"description": "Graines → plantes cultivées → fruits/simples → remèdes et philtres "
			"(jardinier, apothicaire, alchimiste).",
	},
	{
		"id": "gen_magasins_auxerre",
		"label": "🏪 Générer les magasins manquants d'Auxerre",
		"argv": _py("gen_magasins_auxerre.py"),
		"ecrit": "Écrit jsons/magasins_auxerre_a_importer.json (+ la liste des images manquantes).",
		"description": "Porte Auxerre à deux magasins de chaque type possible. N'écrit que ce "
			"qui manque : relancer sur un dump plus récent est idempotent.",
	},
	{
		"id": "gen_specialites_france",
		"label": "🥐 Générer les spécialités de terroir (recettes portées)",
		"argv": _py("gen_specialites_france.py"),
		"ecrit": "Écrit jsons/specialites_france_a_importer.json.",
		"description": "Dix spécialités françaises de fournil et de cuisine, portées par un "
			"lieu (`recette.lieu_portee`) : elles ne se cuisent que sous ce lieu, la remontée "
			"se faisant par `lieu_parent`. ⚠️ Rattache aussi les trois cités à `lieu:france` — "
			"sans quoi la chaîne s'arrête à la ville et aucune portée « pays » n'aboutit. Le "
			"script REFUSE d'écrire une recette portée par un lieu sans atelier du métier "
			"(morte-née), et dit recette par recette ce qui arrive au rayon sans le joueur.",
	},
	{
		"id": "gen_magasins_superieurs",
		"label": "🏛️ Générer les grandes manufactures de Lutèce",
		"argv": _py("gen_magasins_superieurs.py"),
		"ecrit": "Écrit jsons/magasins_superieurs_a_importer.json (+ la liste des images manquantes).",
		"description": "Les 18 magasins de niveau supérieur : enseignes, portes, tenanciers et "
			"items exclusifs. La FUSION des métiers n'est pas écrite ici — elle vit dans la "
			"variable de monde LIEU_CATEGORIES_FUSION et se résout à la lecture. ⚠️ Le script "
			"rebranche db.config sur le dump avant d'importer utils.marche : il REFUSE d'écrire "
			"une recette dont un métier réuni ferait tout à lui seul, ou dont un intrant est "
			"hors de portée de la maison. Le rapport dit, recette par recette, ce qui arrive au "
			"rayon sans le joueur. RELANÇABLE : ce qui est déjà en base est sauté, jamais réémis "
			"(un PUT complet écraserait une retouche faite à la main) ; sans rien à créer, aucun "
			"fichier n'est écrit.",
	},
	{
		"id": "gen_matieres_generiques_bois",
		"label": "🪵 Générer les matières génériques de bois",
		"argv": _py("gen_matieres_generiques_bois.py"),
		"ecrit": "Écrit jsons/matieres_generiques_bois_a_importer.json.",
		"description": "Un doc générique par calibre (branche, petit_rondin, rondin, "
			"gros_rondin) — sans lui le prix retombe au plancher de 1 cu, sans aucune erreur.",
	},
	{
		"id": "gen_loot_immateriel",
		"label": "🦴 Donner un débouché aux butins immatériels",
		"argv": _py("gen_loot_immateriel.py"),
		"ecrit": "Écrit jsons/loot_immateriel_a_importer.json.",
		"description": "32 butins d'espèces (esprits, morts-vivants, constructs) ont une "
			"sous_categorie VIDE : aucune recette ne les consomme, donc aucun marchand ne "
			"les rachète. Leur pose une sous-catégorie par famille + les recettes qui les "
			"transforment.",
	},
	{
		"id": "gen_recettes_empenneur_archerie",
		"label": "🏹 Croiser les recettes empenneur ↔ archerie",
		"argv": _py("gen_recettes_empenneur_archerie.py"),
		"ecrit": "Écrit jsons/recettes_empenneur_archerie_a_importer.json.",
		"description": "Les deux métiers travaillent la même matière : ce qu'on sait faire "
			"chez l'un, on sait le faire chez l'autre.",
	},
	{
		"id": "gen_encre_scriptorium",
		"label": "🖋️ Donner au scriptorium une encre au pigment",
		"argv": _py("gen_encre_scriptorium.py"),
		"ecrit": "Écrit jsons/encre_scriptorium_a_importer.json.",
		"description": "Sans encre au-dessus de sa cible, le scriptorium ne fabrique aucun "
			"livre (sort, recette, carte). Sa seule encre venait du sang, qu'aucun appro ne "
			"livre : recette pigment ×1 → encre ×2. ⚠️ L'encre passe de 12-36 cu à 30-90 cu.",
	},
	{
		"id": "gen_grimoires",
		"label": "📖 Générer les grimoires des sorts qui n'en ont pas",
		# Sans paramètre, mais `dump_frais` : l'import est un PUT complet, relire le dump committé
		# réémettrait un grimoire retouché depuis — et l'écraserait.
		"argv_fn": lambda v, f: _py("gen_grimoires.py", "--dump", f["dump"]),
		"dump_frais": True,
		"sortie": "jsons/grimoires_a_importer.json",
		"ecrit": "Régénère un dump, écrit jsons/grimoires_a_importer.json. Rien en base avant 📥 Importer.",
		"description": "Un grimoire UNIQUE (`sorts: [le sort]`) et sa recette de scriptorium pour "
			"chaque sort qui n'en a pas — un sort que seul un grimoire multiple cite reçoit quand "
			"même le sien. Prix et rareté par niveau (5-15 ag au niveau 0, 10n-30n ag au niveau n), "
			"matières reprises de la recette de grimoire la plus répandue. ⚠️ Chaque recette neuve "
			"entre au tirage de TOUS les scriptoriums. Signale aussi les grimoires qu'aucune recette "
			"ne produit. Refuse tout le lot sur un `_id` déjà pris par autre chose ; sans rien à "
			"créer, n'écrit aucun fichier.",
	},
	{
		"id": "gen_grimoires_sans_plume",
		"label": "🪶 Retirer la plume d'oie des recettes de grimoire",
		# Même raison que gen_grimoires : l'import est un PUT complet et ces recettes sont
		# réémises ENTIÈRES — relire le dump committé écraserait tout ajustement fait depuis.
		"argv_fn": lambda v, f: _py("gen_grimoires_sans_plume.py", f["dump"]),
		"dump_frais": True,
		"sortie": "jsons/grimoires_sans_plume_a_importer.json",
		"ecrit": "Régénère un dump, écrit jsons/grimoires_sans_plume_a_importer.json. "
			"Rien en base avant 📥 Importer.",
		"description": "`item:Plume_d_oie` n'est pas une feuille d'appro (une recette de "
			"scriptorium la produit) et sa matière `plumes` non plus : elle n'arrive que par le "
			"flux de la cité, où l'armurerie et la plumasserie puisent avant. Sans plume au "
			"rayon AU-DESSUS de la cible, aucune recette de grimoire n'est applicable — cinq "
			"grimoires produits dans le monde en six jours au dump du 20/09, pendant que "
			"l'encre et le papier s'entassaient. Les grimoires s'alignent sur les livres de "
			"contenu : papier + encre + pigment. ⚠️ Le scriptorium cesse d'acheter la plume "
			"comme matière (il la rachète toujours : il la produit).",
	},
	{
		"id": "gen_terrain_tags",
		"label": "🌲 Générer les terrain_tags des zones d'influence",
		"argv": _py("gen_terrain_tags.py"),
		"ecrit": "Écrit un jsons/*_a_importer.json.",
		"description": "Vocabulaire de DÉCOR lu par select_battle_map — à ne pas confondre "
			"avec les tags d'une entrée de table_evenements, qui sont des créatures.",
	},
	{
		"id": "purge_quetes_simulation",
		"label": "🧹 Purge des quêtes acceptées — SIMULATION",
		"argv": _py("purge_quetes_acceptees.py"),
		"ecrit": "Lecture seule (aperçu).",
		"description": "Compte les docs quete:* générés déjà acceptés — du poids mort que "
			"offres_du_giver rapatrie à chaque ouverture du tableau de guilde.",
	},
	{
		"id": "purge_quetes_appliquer",
		"label": "🧹 Purge des quêtes acceptées — APPLIQUER (supprime en base)",
		"argv": _py("purge_quetes_acceptees.py", "--appliquer"),
		"ecrit": "⚠️ SUPPRIME des documents en base. Irréversible.",
		"danger": True,
		"description": "One-shot destiné à solder l'arriéré. Seules les quêtes source=genere "
			"sont supprimées ; une quête AUTHORÉE n'est jamais touchée.",
	},
	{
		"id": "audit_economy",
		"label": "⚖️ Audit économique — recettes, rayons, marges",
		# `--dernier` et pas un chemin figé : l'argv d'une entrée est écrit ICI, en dur, et
		# `Popen` ne branche aucun stdin — le bouton ne peut donc pas poser la question que le
		# script pose en CLI (sans dump il sortirait en code 2). Le rapport nomme en tête le
		# dump retenu : le choix est automatique, il n'est pas caché.
		"argv": _py("audit_economy.py", "--dernier"),
		"ecrit": "Lecture seule. Lit le dump le plus récent de jsons/, jamais la base.",
		"description": "Indicateurs d'équilibrage : part des items qu'aucune recette "
			"atteignable ne produit, part des recettes dont le produit n'entre jamais en rayon "
			"(flux de cité compris), marge médiane d'un objet fabriqué, et les matières RACINES "
			"que seul l'aventurier apporte (ce que chacune débloque, ce qu'on perd sans elle). "
			"Rebranche `db.config` sur le dump avant d'importer `utils.marche` : les prix et "
			"coûts de revient sortent du moteur du jeu, pas d'une réimplémentation. ⚠️ "
			"Hypothèses de référence documentées en tête de dev/audit_economy.py (A à I) — "
			"notamment « en rayon » = sans le joueur ravitailleur.",
	},
	# ── /admin/lieux : outils PARAMÉTRÉS par la ville et les lignes affichées ──────────
	# Absents de /admin/dev-tools (qui ne sait pas saisir de paramètre, cf. `catalogue_payload`).
	# Tous `dump_frais` : le dump relu est écrit par le serveur à l'instant du lancement.
	{
		"id": "lieux_magasins_json",
		"portee": "lieux",
		"label": "🏪 Magasins depuis un JSON",
		"params": [{"nom": "ville", "type": "ville"}, {"nom": "spec", "type": "json"}],
		"argv_fn": lambda v, f: _py("gen_magasins.py", "--dump", f["dump"], "--spec", f["spec"]),
		"dump_frais": True,
		"sortie": "jsons/magasins_a_importer.json",
		"ecrit": "Régénère un dump, écrit jsons/magasins_a_importer.json. Rien en base avant 📥 Importer.",
		"description": "Un lieu + sa connexion par entrée de la spec, même forme que le lot de lieux "
			"de l'éditeur. `cite` est forcée à la ville affichée. Refuse TOUT le lot sur un `_id` "
			"déjà pris, une case absente, hors grille, de terrain ≠ 1 ou déjà porteuse du même "
			"métier. « 📍 Compléter les positions » propose des cases de la région principale.",
	},
	{
		"id": "lieux_progeniture",
		"portee": "lieux",
		"label": "👪 Progéniture des marchands affichés",
		"params": [{"nom": "lieux", "type": "lieux"}],
		"argv_fn": lambda v, f: _py("gen_progeniture.py", "--dump", f["dump"],
									"--lieux", ",".join(v["lieux"])),
		"dump_frais": True,
		"sortie": "jsons/progeniture_lieux_a_importer.json",
		"ecrit": "Régénère un dump, écrit jsons/progeniture_lieux_a_importer.json. Rien en base avant 📥 Importer.",
		"description": "Pose un bloc `progeniture` sur la 1re entrée `pnj` des boutiques affichées "
			"dont le tenancier est un `pnj:marchand_*` explicite. Prénoms et noms du répertoire du "
			"recrutement, portraits empruntés à `characters/`, tirage déterministe par lieu. Une "
			"famille déjà écrite n'est JAMAIS réécrite (le prénom fait l'id de la quête).",
	},
	{
		"id": "lieux_audit_economy",
		"portee": "lieux",
		"label": "⚖️ Audit économique de la ville",
		"params": [{"nom": "ville", "type": "ville"}],
		"argv_fn": lambda v, f: _py("audit_economy.py", f["dump"], "--ville", v["ville"]),
		"dump_frais": True,
		"ecrit": "Régénère un dump (jsons/telluris-dump-*.json) et l'audite. Rien d'autre.",
		"description": "Les trois indicateurs de l'audit économique, restreints aux ateliers de la "
			"ville, aux recettes que l'un d'eux peut cuire et aux objets qu'elles visent — plus "
			"une ligne par atelier (recettes, en rayon sans le joueur, matières manquantes).",
	},
	{
		"id": "pytest",
		"label": "🧪 Suite de tests pure (pytest)",
		# `--color=no` : sans tty pytest se décolore déjà tout seul, mais un PY_COLORS/FORCE_COLOR
		# traînant dans l'environnement suffirait à cracher des séquences ANSI dans le notepad,
		# qui les afficherait telles quelles (il écrit en textContent).
		# `-p no:cacheprovider` : sans lui, pytest écrit un dossier .pytest_cache — l'outil ne
		# serait alors plus « lecture seule », ce que la fiche promet.
		"argv": _module("pytest", "tests/", "-q", "--color=no", "-p", "no:cacheprovider"),
		"ecrit": "Lecture seule.",
		"description": "Logique Python PURE : stats, combat, marché/recettes, consommables, "
			"sorts, quêtes, escortes… Aucune dépendance base (db/config tolère l'absence de "
			"CouchDB à l'import). `pytest` est dans le pip install du docker-compose : "
			"l'entrée tourne depuis cette page.",
	},
	{
		"id": "check_js",
		"label": "🧪 Contrôle syntaxique du JS des templates (node)",
		"argv": _node("check_js.js"),
		"ecrit": "Lecture seule.",
		"description": "⚠️ Exige `node`, qui n'est PAS installé dans l'image python:3.11-slim "
			"du conteneur : depuis cette page, l'outil échouera tant que ce sera le cas. "
			"À lancer côté poste de développement.",
	},
	{
		"id": "test_slots_client",
		"label": "🧪 Tests d'exécution de la barre de slots (node)",
		"argv": _node("test_slots_client.js"),
		"ecrit": "Lecture seule.",
		"description": "⚠️ Exige `node` (cf. ci-dessus). Exécute les fonctions PURES extraites "
			"du template de combat dans un contexte vm.",
	},
	{
		"id": "test_saut_client",
		"label": "🧪 Tests d'exécution du ciblage de saut (node)",
		"argv": _node("test_saut_client.js"),
		"ecrit": "Lecture seule.",
		"description": "⚠️ Exige `node` (cf. ci-dessus). Éprouve le SEUL ciblage de la page "
			"qui porte sur une CASE et non sur un acteur : cases d'arrivée offertes (miroir "
			"de `_verifier_saut`, mur franchi compris) et parcours du mode `pendingSaut`.",
	},
	{
		"id": "test_resize_client",
		"label": "🧪 Tests d'exécution du redimensionnement de grille (node)",
		"argv": _node("test_resize_client.js"),
		"ecrit": "Lecture seule.",
		"description": "⚠️ Exige `node` (cf. ci-dessus). Exécute les fonctions PURES du "
			"redimensionnement de carte (éditeur /admin/editor) : rééchantillonnage de `cells`, "
			"remappage du dict creux `nav`, recalage des zones et des portes.",
	},
	{
		"id": "test_deplacement_client",
		"label": "🧪 Tests d'exécution des règles de marche (node)",
		"argv": _node("test_deplacement_client.js"),
		"ecrit": "Lecture seule.",
		"description": "⚠️ Exige `node` (cf. ci-dessus). Exécute `templates/scripts/deplacement.js`, "
			"partagé par play_town, le combat et le mode test de l'éditeur. C'est son SEUL test : "
			"la règle de marche (terrain, `nav`, bornes) n'existe NULLE PART côté serveur.",
	},
	{
		"id": "test_portes_client",
		"label": "🧪 Tests d'exécution des portes de rempart (node)",
		"argv": _node("test_portes_client.js"),
		"ecrit": "Lecture seule.",
		"description": "⚠️ Exige `node` (cf. ci-dessus). Exécute les fonctions PURES du flux "
			"« porte de rempart » de /admin/editor : les cinq documents d'une paire, la fusion "
			"préservant les clés inconnues, l'ordre des nœuds (permuter changerait la porte de "
			"côté), et la reconstitution d'une paire depuis l'un ou l'autre de ses deux lieux.",
	},
	{
		"id": "test_dialogues_client",
		"label": "🧪 Tests d'exécution de l'éditeur de dialogues (node)",
		"argv": _node("test_dialogues_client.js"),
		"ecrit": "Lecture seule.",
		"description": "⚠️ Exige `node` (cf. ci-dessus). Exécute les fonctions PURES de "
			"/admin/dialogues : fusion préservant les clés inconnues (doc, nœud, choix), "
			"atteignabilité des nœuds (nœuds de service compris), offres de transport et "
			"d'escorte, placement du graphe.",
	},
]

_PAR_ID = OrderedDict((o["id"], o) for o in CATALOGUE)


# Jamais publié : le client n'a aucune raison de connaître la ligne de commande, et la publier
# inviterait à la renvoyer. (`argv_fn` est une fonction : pas du JSON, de toute façon.)
_PRIVES = ("argv", "argv_fn")


def catalogue_payload(portee: str | None = None) -> list:
	"""Le catalogue tel qu'un écran l'affiche, sans `_PRIVES`.

	`portee=None` → /admin/dev-tools : les seules entrées SANS `params` (l'écran ne sait pas en
	saisir, les lancer sans valeur les ferait refuser). `portee="lieux"` → /admin/lieux."""
	if portee is None:
		choisis = [o for o in CATALOGUE if not o.get("params")]
	else:
		choisis = [o for o in CATALOGUE if o.get("portee") == portee]
	return [{k: v for k, v in o.items() if k not in _PRIVES} for o in choisis]


# ── Exécution ────────────────────────────────────────────────────────────────
_VERROU = threading.Lock()
_RUN = None   # dict de l'exécution courante (la dernière lancée, terminée ou non)


def _nouvelle_execution(outil: dict, run_id: str) -> dict:
	return {
		"run_id": run_id,
		"outil": outil["id"],
		"label": outil["label"],
		"lignes": [],
		"base": 0,          # index absolu de lignes[0] — ce qui précède est tombé du tampon
		"fini": False,
		"code": None,
		"proc": None,
		"debut": time.time(),
	}


def _emettre(run: dict, texte: str) -> None:
	run["lignes"].append(texte)
	trop = len(run["lignes"]) - MAX_LIGNES
	if trop > 0:
		del run["lignes"][:trop]
		run["base"] += trop


def _lire_sortie(run: dict) -> None:
	"""Thread de pompage : stdout+stderr fusionnés, ligne à ligne, jusqu'à la fin du fils."""
	proc = run["proc"]
	try:
		for ligne in proc.stdout:
			_emettre(run, ligne.rstrip("\n"))
	except Exception as err:      # tube cassé, décodage… : on le DIT plutôt que de finir muet
		_emettre(run, f"[erreur de lecture] {err}")
	finally:
		try:
			code = proc.wait()
		except Exception:
			code = None
		run["code"] = code
		duree = time.time() - run["debut"]
		_emettre(run, "")
		_emettre(run, f"── terminé en {duree:.1f} s — code de sortie {code} "
			+ ("✓" if code == 0 else "✗"))
		run["fini"] = True


def lancer(outil_id: str, params=None, preparer=None, villes_connues=()):
	"""Démarre un outil. Renvoie `(run, erreur)` — `erreur` = `(code HTTP, message)`.

	Outil PARAMÉTRÉ : `params` est validé AVANT le verrou (un refus ne bloque personne), puis
	`preparer(outil, valeurs)` — injecté par main.py, seul à toucher la base et le disque —
	écrit le dump et la spec, et rend leurs chemins RELATIFS à la racine, que `argv_fn` place.
	⚠️ La préparation a lieu SOUS le verrou et APRÈS le contrôle « déjà en cours » : on n'écrit
	pas un dump de plusieurs Mo pour se voir refuser le lancement."""
	global _RUN
	outil = _PAR_ID.get(outil_id)
	if not outil:
		return None, (404, f"Outil inconnu : {outil_id}")
	valeurs, refus = valider_params(outil, params, villes_connues)
	if refus:
		return None, (422, refus)
	if outil.get("argv_fn") and preparer is None:
		return None, (500, "Cet outil exige une préparation (dump, spec) que l'appelant ne fournit pas.")
	with _VERROU:
		if _RUN is not None and not _RUN["fini"]:
			return None, (409, f"« {_RUN['label']} » est encore en cours.")
		fichiers = {}
		if outil.get("argv_fn"):
			try:
				fichiers = preparer(outil, valeurs) or {}
			except Exception as err:
				return None, (500, f"Préparation impossible : {err}")
			argv = outil["argv_fn"](valeurs, fichiers)
		else:
			argv = outil["argv"]
		# ⚠️ Créé APRÈS la préparation : `debut` sert à dater le fichier produit (`sortie_fraiche`),
		# le dump qu'on vient d'écrire ne doit pas passer pour la sortie du run.
		run = _nouvelle_execution(outil, f"{outil_id}-{int(time.time() * 1000)}")
		# ⚠️ Environnement : dans une image slim la locale est POSIX, donc le stdout d'un fils
		# redirigé vers un tube s'encode en ASCII — le premier `print` accentué (tous les
		# scripts du projet parlent français) lèverait un UnicodeEncodeError et l'outil
		# semblerait planter tout seul. PYTHONIOENCODING ferme ce cas.
		env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
		for cle, chemin in fichiers.items():
			_emettre(run, f"# {cle} écrit par le serveur : {chemin}")
		_emettre(run, "$ " + " ".join(argv))
		_emettre(run, "")
		try:
			run["proc"] = subprocess.Popen(
				argv,                          # LISTE : aucun shell, rien n'est interprété
				cwd=RACINE,
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT,      # un seul flux : l'ordre des lignes est celui du script
				text=True,
				encoding="utf-8",
				errors="replace",
				bufsize=1,
				env=env,
			)
		except FileNotFoundError:
			_emettre(run, f"[introuvable] {argv[0]} — cet exécutable n'existe pas "
				"dans le conteneur.")
			run["fini"], run["code"] = True, 127
			_RUN = run
			return run, None
		except Exception as err:
			_emettre(run, f"[échec du lancement] {err}")
			run["fini"], run["code"] = True, 1
			_RUN = run
			return run, None
		_RUN = run
	threading.Thread(target=_lire_sortie, args=(run,), daemon=True).start()
	return run, None


def journal(offset: int = 0) -> dict:
	"""Tranche du journal à partir d'`offset` (index ABSOLU depuis le début du run).

	Le client renvoie l'offset qu'on lui a donné : c'est ce qui rend le tail insensible à une
	requête perdue ou doublée. `perdu` > 0 signale un débordement du tampon — mieux vaut le
	dire que de laisser croire à une sortie continue."""
	run = _RUN
	if run is None:
		return {"actif": False, "lignes": [], "offset": 0, "fini": True, "code": None}
	debut = max(offset, run["base"])
	i = debut - run["base"]
	lignes = run["lignes"][i:] if i >= 0 else list(run["lignes"])
	return {
		"actif": True,
		"run_id": run["run_id"],
		"outil": run["outil"],
		"label": run["label"],
		"lignes": lignes,
		"offset": run["base"] + len(run["lignes"]),
		"perdu": max(0, run["base"] - offset) if offset else 0,
		"fini": run["fini"],
		"code": run["code"],
	}


def sortie_fraiche(outil_id: str, mtime_fn=os.path.getmtime):
	"""Chemin RELATIF du fichier produit par le DERNIER run de cet outil — seulement s'il a fini
	en code 0 et que le fichier est plus récent que son départ. `(chemin, None)` ou
	`(None, (code HTTP, message))`.

	⚠️ Sans ce contrôle, 📥 Importer enverrait le fichier d'un run PRÉCÉDENT : un générateur qui
	refuse le lot ou n'a rien à écrire laisse l'ancien fichier en place — et l'import est un PUT
	complet (CLAUDE.md §11)."""
	outil = _PAR_ID.get(outil_id)
	if not outil or not outil.get("sortie"):
		return None, (404, "Cet outil ne produit aucun fichier à importer.")
	run = _RUN
	if run is None or run.get("outil") != outil_id or not run.get("fini"):
		return None, (409, "Aucun run terminé de cet outil.")
	if run.get("code") != 0:
		return None, (409, f"Le dernier run a échoué (code {run.get('code')}) : rien à importer.")
	chemin = outil["sortie"]
	try:
		mtime = mtime_fn(os.path.join(RACINE, chemin))
	except OSError:
		return None, (404, f"{chemin} n'a pas été écrit.")
	if mtime < run["debut"]:
		return None, (409, f"{chemin} date d'avant ce run : le générateur n'a rien écrit.")
	return chemin, None


def arreter() -> bool:
	"""Demande l'arrêt du run courant (SIGTERM). Le thread de pompage conclura tout seul."""
	run = _RUN
	if run is None or run["fini"] or not run.get("proc"):
		return False
	try:
		run["proc"].terminate()
		return True
	except Exception:
		return False
