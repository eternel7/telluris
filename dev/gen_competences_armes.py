#!/usr/bin/env python
# dev/gen_competences_armes.py
# Pose l'EXIGENCE D'ARME (champ `arme`, lu par `utils/exigence_arme.py`) sur les compétences
# de vocation, range en `sous_categorie: bouclier` les boucliers qui ne l'avaient pas, et
# réaligne les variantes sur mesure sur les tags de leur base (`tags_manquants` : dagues sans
# `legere`, armures sans `armure_cuir`… créées avant que la base ne reçoive le tag).
#
#     "arme": {"mode": "tir" | ["tir", "jet"], "tags": ["arc"]}
#
# RÈGLES PAR DÉFAUT (décisions de l'Auteur, 14/11/2026) :
#   - active `cible: ennemi`, `jet: cc`, à dés      → {"mode": "cac"} (frappe portée avec l'arme) ;
#   - active `cible: ennemi`, `jet: cd`             → {"mode": "tir"}, + tag `arc` si le texte
#                                                      parle de flèche / d'arc / de décocher ;
#   - tout le reste (magique, soutien, passive)     → aucune exigence.
# puis la table `EXCEPTIONS` (slug → bloc, ou None = aucune exigence) : moine, cris, coups de
# pied / tête / épaule, fioles, poudres, poisons, vols, armes de jet, deux armes, boucliers,
# lames courtes, postures et passives liées à une arme. Monstres (`vocation: monstre`) exclus.
#
# ⚠️ La table est VÉRIFIÉE : un slug qu'elle cite et que le dump n'a pas fait échouer le script
# (une compétence renommée ne garde pas en silence une exception orpheline).
#
# ⚠️ POURQUOI UN SCRIPT : `admin_import_bulk` fait un PUT COMPLET. On RELIT chaque doc dans le
# dump le plus récent et on n'y pose que `arme` (ou `sous_categorie`) : régénération idempotente,
# seuls les docs qui CHANGENT sont écrits.
#
# Usage : python dev/gen_competences_armes.py
# Sorties :
#   jsons/competences_armes_a_importer.json   (à importer depuis /admin, APRÈS relecture)
#   docs/competences_armes.md                  (GÉNÉRÉ : la proposition à relire)

import glob
import json
import os
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from utils import exigence_arme   # noqa: E402

SORTIE = "jsons/competences_armes_a_importer.json"
DOC = "docs/competences_armes.md"

CAC = {"mode": "cac"}
LAME = {"mode": "cac", "tags": ["tranchant"]}      # dague, couteau, surin : `legere` n'est
# pas fiable (20 dagues sur 35 ne le portent pas), toutes portent `tranchant`.
TIR = {"mode": "tir"}
ARC = {"mode": "tir", "tags": ["arc"]}
JET = {"mode": "jet"}
BOUCLIER = {"mode": "bouclier"}
DEUX = {"mode": "deux_armes"}

# Slug (`competence:<slug>`) → exigence, ou None (aucune), avec le motif affiché au doc.
EXCEPTIONS = {
	# ── Assassin ──
	"coup_de_dague": (LAME, "une dague"),
	"lame_enduite": (LAME, "venin sur le fil d'une lame"),
	"venin_de_contact": (LAME, "venin sur le fil d'une lame"),
	"cigue": (LAME, "deux poisons dans la même entaille"),
	"double_lame": (DEUX, "« ses deux lames »"),
	"fleur_de_lames": (DEUX, "« ses deux lames »"),
	"danse_des_dagues": (LAME, "dagues ; reste une frappe de mêlée (un mode `jet` la rendrait interdite engagé)"),
	"eventail_de_dagues": (LAME, "couteaux lancés ; reste une frappe de mêlée (même raison)"),
	"fiole_de_belladone": (None, "fiole"),
	"garrot": (None, "cordelette"),
	"poudre_de_pavot": (None, "poudre"),
	"venin_d_aspic": (None, "poison"),
	"toxine_paralysante": (None, "poison"),
	"essence_de_mandragore": (None, "poison"),
	"marque_de_mort": (None, "marque"),
	"nuage_toxique": (None, "fiole lancée"),
	"voler_le_souffle": (None, "coup au plexus"),
	"venin_du_scorpion_noir": (None, "poison"),
	"poudre_de_sommeil": (None, "poudre"),
	"venin_de_l_ame": (None, "poison"),
	"brume_empoisonnee": (None, "brume"),
	"peste_noire": (None, "fiole"),
	"fiole_du_maitre_empoisonneur": (None, "fiole"),
	# ── Barbare ──
	"hurlement": (None, "cri"),
	"rugissement": (None, "cri"),
	"terreur_des_steppes": (None, "regard"),
	"tete_la_premiere": (None, "coup de tête"),
	"charge_du_sanglier": (None, "charge du corps"),
	# ── Chaman : griffes et crocs d'esprit ──
	"griffe_du_loup": (None, "griffes d'esprit"),
	"ruee_du_sanglier_esprit": (None, "ruée"),
	"crocs_de_l_esprit": (None, "esprit-loup"),
	"esprit_du_sanglier": (None, "fureur d'esprit"),
	# ── Druide ──
	"trait_du_chasseur": ({"mode": ["tir", "jet"]}, "« arc, fronde, javelot, lance »"),
	# ── Duelliste ──
	"coup_de_pied_de_salle": (None, "coup de botte"),
	"en_garde": (CAC, "posture de la lame"),
	"garde_de_soie": (CAC, "posture de la lame"),
	"parade_de_maitre": (CAC, "parade"),
	"garde_absolue": (CAC, "« il détourne toutes les lames »"),
	"fleche": (CAC, "course pointe en avant"),
	"poignet_souple": (CAC, "« la lame tourne dans sa main »"),
	"lame_vivante": (CAC, "« l'épée … pare d'elle-même »"),
	"maitre_d_armes": (CAC, "« l'arme … c'est le bout de son bras »"),
	# ── Forestier ──
	"coup_de_couteau": (LAME, "couteau de chasse"),
	"couteau_du_depeceur": (LAME, "couteau"),
	"cri_du_faucon": (None, "sifflement"),
	# ── Guerrier ──
	"bousculade": (None, "coup d'épaule"),
	"coup_de_belier": (None, "coup d'épaule"),
	"defi": (BOUCLIER, "« il frappe son bouclier »"),
	"garde_haute": (BOUCLIER, "« le bouclier remonte »"),
	"mur_de_boucliers": (BOUCLIER, "« il lève le bouclier »"),
	"garde_de_fer": (CAC, "garde fermée"),
	# ── Mage ──
	"lame_de_mana": (None, "lame de mana pur"),
	"lame_enchantee": (CAC, "« il enchante sa propre arme »"),
	# ── Ménestrel ──
	"coup_de_luth": ({"mode": "cac", "tags": ["instrument"]}, "le luth"),
	"lame_du_conteur": (LAME, "une dague"),
	# ── Moine : mains nues admises, donc aucune exigence ──
	**{s: (None, "moine : mains nues ou bâton") for s in (
		"paume_de_force", "balayage_de_jambe", "paume_tranchante", "coup_du_dragon",
		"toucher_des_meridiens", "roue_du_vent", "souffle_interieur", "frappe_du_tigre",
		"poing_de_pierre", "coup_du_serpent", "mille_poings", "poing_de_legende",
		"pied_du_phenix", "onde_de_choc", "point_de_pression", "danse_des_mille_mains",
		"poing_du_ciel", "paume_du_neant")},
	"garde_du_pelerin": (CAC, "« le bâton tenu en travers »"),
	# ── Paladin ──
	"heros": (BOUCLIER, "« maître du bouclier »"),
	"croisade": (CAC, "« il lève sa masse »"),
	# ── Répurgateur ──
	"sel_et_cendre": (None, "poignée de sel"),
	"eau_lustrale": (None, "fiole"),
	"chaines_d_argent": (None, "chaînes"),
	"marque_du_traqueur": (None, "marque"),
	"fouet_de_flammes": (None, "lanière de feu"),
	"marque_d_argent": (None, "marque"),
	"haleine_de_l_abime": (None, "souffle"),
	"pacte_rompu": (None, "rupture de pacte"),
	# ── Templier ──
	"ordre_de_halte": (None, "commandement"),
	"dissipation": (None, "étendard planté"),
	"bouclier_repoussant": (BOUCLIER, "coup de bouclier"),
	"garde_de_l_ordre": (CAC, "garde réglementaire"),
	"arme_de_justice": (CAC, "« sa lame »"),
	# ── Voleur ──
	"lame_de_poche": (LAME, "canif"),
	"surin": (LAME, "surin"),
	"coup_de_surin": (LAME, "surin"),
	"lame_cachee": (LAME, "lame de manche"),
	"lame_dans_la_manche": (LAME, "lame de manche"),
	"fiel_de_crapaud": (LAME, "lame trempée"),
	"poudre_aveuglante": (LAME, "« puis la dague »"),
	"tempete_de_couteaux": (LAME, "couteaux ; reste une frappe de mêlée (même raison que l'éventail)"),
	"couteaux_de_lancer": (JET, "couteaux de lancer"),
	"coup_bas": (None, "coup de genou"),
	"sable_aux_yeux": (None, "poignée de sable"),
	"bourse_lestee": (None, "coup de veine"),
	"croc_en_jambe": (None, "croc-en-jambe"),
	"coup_du_pave": (None, "ce qui traîne dans la rue"),
	"pickpocket_de_combat": (None, "vol"),
	"poivre_des_quais": (None, "poivre"),
	"bombe_fumigene": (None, "bombe"),
	"cordelette": (None, "cordelette"),
	"sale_coup": (None, "vol"),
	"coup_du_lapin": (None, "coup à la nuque"),
	"pluie_de_clous": (None, "clous jetés"),
	"vol_a_l_arrache": (None, "vol"),
	"cendre_au_visage": (None, "cendre"),
	"mauvaise_fiole": (None, "fiole"),
	"chausse_trappe_lancee": (None, "pointes semées"),
	"detrousser_l_ame": (None, "vol"),
	"feu_gregeois_de_poche": (None, "fiole"),
	"nuage_de_poivre": (None, "poivre"),
	"voleur_d_ombres": (None, "vol"),
	# ── Assassin (passive) ──
	"surineur": (LAME, "« sa dague trouve l'ouverture »"),
}

# FORESTIER (et Carreau béni du répurgateur) : ces tirs acceptent toute arme de TIR ou de JET (Auteur, 14/11), et
# leur texte ne parle plus de flèche mais de TRAIT (terme générique du jeu : flèche, carreau,
# javelot). Slug → (nouveau nom, nouvelle description) ; None = inchangé. Exceptions
# EXPLICITES, jamais déduites du texte : une fois renommées, elles ne parleraient plus de
# flèche et la règle `ARC_TEXTE` les rétrograderait en simple tir à la régénération suivante.
TIR_OU_JET = {"mode": ["tir", "jet"]}
TRAITS = {
	"tir_precis": (None, "Il retient son souffle, laisse passer un battement de cœur, puis lâche son trait."),
	"fleche_rapide": ("Trait rapide", "Vise, lâche : un seul souffle."),
	"tir_aux_jambes": (None, "Un trait bas qui ralentit la course de la proie."),
	"fleche_barbelee": ("Trait barbelé", None),
	"double_fleche": (None, "Un trait qui file plus loin que l'œil ne suit — pour qui a la main assez sûre."),
	"volee": (None, "Une pluie de traits sur une petite clairière."),
	"fleche_de_franc_archer": ("Tir dans la mêlée", None),
	"fleche_perforante": ("Trait perforant", None),
	"fleche_de_chasse": ("Trait de chasse", "Un trait à large fer, qui handicape plus qu'il ne tue."),
	"tir_a_l_il": (None, "Un trait qui cherche le seul point que l'armure ne couvre pas."),
	"fleche_longue": ("Trait lointain", None),
	"fleche_venimeuse": ("Trait venimeux", None),
	"pluie_de_fleches": ("Pluie de traits", None),
	"clouer_au_sol": (None, "Le trait traverse le pied et s'enfonce dans la terre."),
	"fleche_epuisante": ("Trait épuisant", None),
	"tir_mortel": (None, "Un trait qu'on n'entend qu'une fois."),
	"volee_en_eventail": (None, "Trois traits à la fois, ouverts en éventail."),
	"fleche_aveuglante": ("Trait aveuglant", None),
	"grele_de_fleches": ("Grêle de traits", None),
	"tir_transpercant": (None, "Le projectile traverse le premier et cherche le second."),
	"fleche_du_roi_des_bois": ("Trait du roi des bois", "Le trait que l'on garde pour le monstre de la forêt."),
	"tir_de_suppression": (None, "Un barrage de traits qui force l'ennemi à se terrer."),
	"ciel_de_fleches": ("Ciel de traits", None),
	"fleche_de_legende": ("Trait de légende", "Le trait dont parlent les chansons de chasse."),
	"trait_du_chasseur_de_monstres": (None, "Un projectile taillé pour ce qui n'a pas de nom, lancé par "
										   "quelqu'un que cela n'effraie plus."),
	"maitrise_de_l_arc": ("Maîtrise du trait", "Arc, fronde ou javelot : l'arme qui porte loin est "
											  "devenue une partie de son corps."),
	# Tirs du forestier dont le texte ne parlait pas d'arc (Auteur, 14/11) : tir ou jet aussi,
	# texte déjà générique.
	"tir_d_elite": (None, None),
	"marque_du_gibier": (None, None),
	"saignee_de_cerf": (None, None),
	"venin_du_marais": (None, None),
	"proie_epuisee": (None, None),
	# Répurgateur (Auteur, 14/11) : même passage à toute arme de tir ou de jet.
	"carreau_beni": ("Trait béni", "Un trait trempé dans l'eau bénite."),
}
EXCEPTIONS.update({s: (TIR_OU_JET, "toute arme de tir ou de jet (trait)") for s in TRAITS})

# Boucliers sans `sous_categorie: bouclier` : `exigence_arme` ne les reconnaîtrait pas.
BOUCLIERS_A_RANGER = ("item:Bouclier_de_croupon", "item:Targe_a_enarmes")

TYPOLOGIES = ("legere", "lourde")


def tags_manquants(variante: dict, base: dict) -> list:
	"""Tags de la BASE absents de la variante sur mesure (`fabrication.base_item`), dans l'ordre
	de la base. Une variante recopie les tags de sa base À SA CRÉATION : un tag posé ensuite sur
	la base (typologie `legere` du 10/11, `armure_cuir`…) lui manque. Ajout seulement ; une
	typologie contraire déjà portée par la variante n'est pas contredite."""
	propres = list(variante.get("tags") or [])
	out = []
	for t in base.get("tags") or []:
		if t in propres or t in out:
			continue
		if t in TYPOLOGIES and any(o in propres for o in TYPOLOGIES):
			continue
		# Matériau d'armure (`commande.TAGS_MATERIAU_ARMURE`) : exclusif, comme la typologie.
		if t.startswith("armure_") and any(o.startswith("armure_") for o in propres):
			continue
		out.append(t)
	return out


ARC_TEXTE = re.compile(r"fl[eè]che|\barc\b|d[ée]coch|encoch|vol[ée]e", re.I)


def _dump_le_plus_recent() -> str:
	dumps = sorted(glob.glob(os.path.join(RACINE, "jsons", "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("ERREUR : aucun jsons/telluris-dump-*.json — exporter la base d'abord.")
	return dumps[-1]


def charger(chemin: str) -> list:
	with open(chemin, encoding="utf-8") as f:
		data = json.load(f)
	return data["docs"] if isinstance(data, dict) and "docs" in data else data


def regle(doc: dict) -> tuple:
	"""(exigence ou None, motif) d'après les règles par défaut."""
	if doc.get("mode") != "active" or doc.get("cible") != "ennemi":
		return None, ""
	jet = doc.get("jet") or "cc"
	if jet == "cd":
		texte = f"{doc.get('nom', '')} {doc.get('description', '')}"
		return (ARC, "tir à l'arc") if ARC_TEXTE.search(texte) else (TIR, "tir")
	if jet == "cc" and (doc.get("effets") or {}).get("degats"):
		return CAC, "frappe portée avec l'arme"
	return None, ""


def exigence_de(doc: dict) -> tuple:
	"""(exigence, motif, origine) — origine « exception » ou « règle »."""
	slug = doc["_id"].split(":", 1)[1]
	if slug in EXCEPTIONS:
		arme, motif = EXCEPTIONS[slug]
		return arme, motif, "exception"
	arme, motif = regle(doc)
	return arme, motif, "règle"


def _avec_arme(doc: dict, arme) -> dict:
	"""Copie du doc avec `arme` juste après `jet` (sinon `cible`, sinon à la fin) ; retiré si None."""
	out = {k: v for k, v in doc.items() if k != "arme"}
	if arme is None:
		return out
	ancre = "jet" if "jet" in out else "cible" if "cible" in out else None
	if ancre is None:
		out["arme"] = arme
		return out
	res = {}
	for k, v in out.items():
		res[k] = v
		if k == ancre:
			res["arme"] = arme
	return res


def textes_reecrits(doc: dict) -> dict:
	"""Copie du doc avec le nom / la description de `TRAITS` (inchangé sinon)."""
	slug = str(doc.get("_id", "")).split(":", 1)[-1]
	if slug not in TRAITS:
		return doc
	nom, description = TRAITS[slug]
	out = dict(doc)
	if nom:
		out["nom"] = nom
	if description:
		out["description"] = description
	return out


def _libelle(arme) -> str:
	return exigence_arme.libelle(exigence_arme.normaliser_arme(arme)) or "—"


def main() -> None:
	source = _dump_le_plus_recent()
	docs = charger(source)
	comps = {d["_id"]: d for d in docs if isinstance(d, dict) and d.get("type") == "competence"
			 and str(d.get("_id", "")).startswith("competence:") and d.get("vocation") != "monstre"}
	items = {d["_id"]: d for d in docs if isinstance(d, dict) and str(d.get("_id", "")).startswith("item:")}

	orphelins = sorted(s for s in EXCEPTIONS if f"competence:{s}" not in comps)
	if orphelins:
		sys.exit("ERREUR : EXCEPTIONS cite des compétences absentes du dump : " + ", ".join(orphelins))
	for arme, _ in EXCEPTIONS.values():
		if arme is not None and exigence_arme.normaliser_arme(arme) is None:
			sys.exit(f"ERREUR : exigence invalide dans EXCEPTIONS : {arme}")
	for iid in BOUCLIERS_A_RANGER:
		if iid not in items:
			sys.exit(f"ERREUR : bouclier absent du dump : {iid}")

	orphelins = sorted(s for s in TRAITS if f"competence:{s}" not in comps)
	if orphelins:
		sys.exit("ERREUR : TRAITS cite des compétences absentes du dump : " + ", ".join(orphelins))
	# Un nom neuf ne doit pas doubler un nom de la même vocation.
	for voc in {comps[f"competence:{s}"].get("vocation") for s in TRAITS}:
		noms = [textes_reecrits(d).get("nom") for d in comps.values() if d.get("vocation") == voc]
		doublons = sorted({n for n in noms if noms.count(n) > 1})
		if doublons:
			sys.exit(f"ERREUR : noms de {voc} en double après réécriture : {doublons}")

	sortie, lignes, deja, renommes = [], {}, 0, []
	for cid in sorted(comps):
		doc = comps[cid]
		arme, motif, origine = exigence_de(doc)
		cible = textes_reecrits(_avec_arme(doc, arme))
		if arme is not None or origine == "exception":
			lignes.setdefault(doc.get("vocation") or "?", []).append((cible, arme, motif, origine))
		if cible == doc:
			deja += 1
			continue
		sortie.append(cible)
		if (cible.get("nom"), cible.get("description")) != (doc.get("nom"), doc.get("description")):
			renommes.append((doc, cible))
	# Items retouchés (boucliers rangés, variantes réalignées) : UN doc par _id, les deux
	# corrections cumulées sur la même copie.
	retouches: dict = {}
	boucliers = []
	for iid in BOUCLIERS_A_RANGER:
		item = items[iid]
		if item.get("sous_categorie") != "bouclier":
			retouches[iid] = dict(item, sous_categorie="bouclier")
			boucliers.append(item.get("nom", iid))
	variantes = []
	for iid in sorted(items):
		item = items[iid]
		base = items.get(((item.get("fabrication") or {}).get("base_item")) or "")
		if not base:
			continue
		manque = tags_manquants(item, base)
		if manque:
			doc = retouches.setdefault(iid, dict(item))
			doc["tags"] = list(item.get("tags") or []) + manque
			variantes.append((item.get("nom", iid), base.get("nom", ""), manque))
	sortie.extend(retouches[i] for i in sorted(retouches))

	ids = [d["_id"] for d in sortie]
	if len(ids) != len(set(ids)):
		sys.exit("ERREUR : _id en double dans la sortie")

	with open(os.path.join(RACINE, SORTIE), "w", encoding="utf-8") as f:
		json.dump(sortie, f, ensure_ascii=False, indent=2)
		f.write("\n")
	_ecrire_doc(lignes, boucliers, variantes, renommes, os.path.relpath(source, RACINE))

	n_comp = len(sortie) - len(retouches)
	print(f"relu {os.path.relpath(source, RACINE)} ({len(comps)} compétences hors monstres)")
	print(f"écrit {SORTIE} : {n_comp} compétence(s) + {len(retouches)} item(s) "
		  f"({len(boucliers)} bouclier(s) rangé(s), {len(variantes)} variante(s) réalignée(s))")
	print(f"écrit {DOC}")
	if deja:
		print(f"   dont {deja} compétence(s) déjà à jour (non réécrites)")


def _ecrire_doc(lignes: dict, boucliers: list, variantes: list, renommes: list, source: str) -> None:
	n_exig = sum(1 for v in lignes.values() for _, a, _, _ in v if a is not None)
	n_libres = sum(1 for v in lignes.values() for _, a, _, _ in v if a is None)
	out = [
		"# Exigence d'arme des compétences — proposition",
		"",
		f"GÉNÉRÉ par `dev/gen_competences_armes.py` depuis `{source}` — ne pas éditer à la main :",
		"corriger la table `EXCEPTIONS` du script, puis le relancer.",
		"",
		"Règles par défaut : frappe `cc` à dés → arme de mêlée ; tir `cd` → arme de tir "
		"(arc si le texte parle de flèche) ; magie, soutiens et passives → rien.",
		"Les **exceptions** (⭐) sont écrites à la main : cris, coups de pied ou d'épaule, fioles, "
		"poudres, vols, moine, jet, deux armes, boucliers, lames courtes, postures, passives.",
		"",
		f"- **{n_exig}** compétences reçoivent une exigence.",
		f"- **{n_libres}** frappes martiales restent **sans exigence** (dernière colonne « — »).",
	]
	if boucliers:
		out.append(f"- Boucliers rangés en `sous_categorie: bouclier` : {', '.join(boucliers)}.")
	out += ["", "⚠️ À relire en priorité : « Héros » (paladin, R +10) devient inactive sans bouclier, "
			"« Maîtrise du trait » sans arme de tir ou de jet ; les frappes aux couteaux lancés "
			"(éventail, danse, tempête) restent des frappes de MÊLÉE exigeant une lame, pour ne pas "
			"devenir interdites au contact.", ""]
	for voc in sorted(lignes):
		out += [f"## {voc}", "", "| niv. | compétence | mode | exige | motif |", "|---|---|---|---|---|"]
		for doc, arme, motif, origine in sorted(lignes[voc], key=lambda t: (t[0].get("niveau") or 0, t[0].get("nom", ""))):
			mode = "passive" if doc.get("mode") == "passive" else (doc.get("jet") or "cc") \
				if doc.get("cible") == "ennemi" else f"{doc.get('cible') or 'soi'}"
			etoile = "⭐ " if origine == "exception" else ""
			out.append(f"| {doc.get('niveau', 0)} | {doc.get('nom', doc['_id'])} | {mode} | "
					   f"{_libelle(arme)} | {etoile}{motif} |")
		out.append("")
	if renommes:
		out += ["## De la flèche (ou du carreau) au trait", "",
				"Ces tirs (forestier, Carreau béni) acceptent toute arme de tir ou de jet : leur texte parle désormais de "
				"**trait** (flèche, carreau, javelot). L'`_id` ne change pas (barre d'action et "
				"compétences connues intactes).", "",
				"| avant | après | description (après) |", "|---|---|---|"]
		for avant, apres in sorted(renommes, key=lambda t: (t[0].get("niveau") or 0, t[0].get("nom", ""))):
			nom = apres["nom"] if apres["nom"] != avant.get("nom") else f"{apres['nom']} (inchangé)"
			desc = apres.get("description", "") if apres.get("description") != avant.get("description") \
				else "(inchangée)"
			out.append(f"| {avant.get('nom', '')} | {nom} | {desc} |")
		out.append("")
	if variantes:
		out += ["## Variantes sur mesure réalignées sur leur base", "",
				"Une variante recopie les tags de sa base à sa création : ceux posés ensuite sur la "
				"base (typologie `legere` du 10/11, `armure_cuir` / `armure_tissu`) lui manquaient. "
				"Ajout seulement.", "", "| variante | base | tags ajoutés |", "|---|---|---|"]
		out += [f"| {nom} | {base} | {', '.join(manque)} |" for nom, base, manque in variantes]
		out.append("")
	with open(os.path.join(RACINE, DOC), "w", encoding="utf-8") as f:
		f.write("\n".join(out))


if __name__ == "__main__":
	main()
