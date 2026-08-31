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

import os
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
			"démarrage du chaînage (1re pièce à la visite 5 au lieu de 10). Dérivé du graphe de "
			"recettes, relit le dump figé et n'injecte que `stock_cible` : idempotent.",
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
		"id": "test_resize_client",
		"label": "🧪 Tests d'exécution du redimensionnement de grille (node)",
		"argv": _node("test_resize_client.js"),
		"ecrit": "Lecture seule.",
		"description": "⚠️ Exige `node` (cf. ci-dessus). Exécute les fonctions PURES du "
			"redimensionnement de carte (éditeur /admin/editor) : rééchantillonnage de `cells`, "
			"remappage du dict creux `nav`, recalage des zones et des portes.",
	},
]

_PAR_ID = OrderedDict((o["id"], o) for o in CATALOGUE)


def catalogue_payload() -> list:
	"""Le catalogue tel que l'écran l'affiche — SANS l'argv : le client n'a aucune raison de
	connaître la ligne de commande, et la publier inviterait à la renvoyer."""
	return [{k: v for k, v in outil.items() if k != "argv"} for outil in CATALOGUE]


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


def lancer(outil_id: str):
	"""Démarre un outil. Renvoie `(run, erreur)` — `erreur` = `(code HTTP, message)`."""
	global _RUN
	outil = _PAR_ID.get(outil_id)
	if not outil:
		return None, (404, f"Outil inconnu : {outil_id}")
	with _VERROU:
		if _RUN is not None and not _RUN["fini"]:
			return None, (409, f"« {_RUN['label']} » est encore en cours.")
		run = _nouvelle_execution(outil, f"{outil_id}-{int(time.time() * 1000)}")
		# ⚠️ Environnement : dans une image slim la locale est POSIX, donc le stdout d'un fils
		# redirigé vers un tube s'encode en ASCII — le premier `print` accentué (tous les
		# scripts du projet parlent français) lèverait un UnicodeEncodeError et l'outil
		# semblerait planter tout seul. PYTHONIOENCODING ferme ce cas.
		env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
		_emettre(run, "$ " + " ".join(outil["argv"]))
		_emettre(run, "")
		try:
			run["proc"] = subprocess.Popen(
				outil["argv"],                 # LISTE : aucun shell, rien n'est interprété
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
			_emettre(run, f"[introuvable] {outil['argv'][0]} — cet exécutable n'existe pas "
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
