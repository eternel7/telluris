#!/usr/bin/env python
"""Invocations MAINTENUES : la créature reste tant que le lanceur paie son entretien.

    python dev/gen_sorts_invocation_maintenue.py [--dump jsons/telluris-dump-*.json] [--sortie …]

Sortie : jsons/sorts_invocation_maintenue_a_importer.json (carte d'import de /admin) —
les `sort:*` neufs, puis le grimoire UNIQUE et la recette de scriptorium de chacun
(`utils/grimoires.grimoires_manquants`, sans quoi un sort ne s'apprend pas).

POURQUOI. Le moteur tient une invocation par concentration depuis longtemps (`maintien`
sur un sort à bloc `invocation` : compteur de tours GELÉ, dissipation à la rupture —
`combat._enregistrer_concentration`), mais aucun sort ne s'en servait. Les échelles à durée
de `dev/gen_sorts_invocation.py` restent intactes : celles-ci les complètent avec des
espèces que RIEN n'invoquait encore.

ESTIMATION (règle complète : compétence telluris-magie § Invocations — estimer un appel) :
  · puissance par round  P = (F + R + Ag + V×10)² × nombre / 100, caractéristiques MOYENNES
    du profil (médian de l'espèce sans profil) — la formule de l'échelle à durée, sans le
    facteur durée puisque la durée est ici ce que le lanceur accepte de payer ;
  · entretien  = clamp(round(P / K), MAINTIEN_MIN, MAINTIEN_PM_MAX), K = K_BASE, ou
    K_BASE / FACTEUR_FAVORISE pour les écoles d'invocation (Démonologie, Nécromancie) :
    à créature égale, leur entretien coûte ~40 % de moins ;
  · lancement  = PART_LANCEMENT × le sort À DURÉE de même école et même niveau (relu du
    dump) — le reste du prix est l'entretien ; RITUEL : × RITUEL_LANCEMENT, armé sur
    RITUEL_INCANTATION PA.

TROIS IDÉES, toutes avec le moteur actuel :
  · `nuee`   — la nuée qui ENFLE : le composant consommé ajoute une créature
               (`invocation_nombre`). Réservée aux écoles favorisées.
  · `rituel` — capstone : `incantation` en PA, l'appel s'arme sur plusieurs tours et ne
               s'abandonne pas, puis se tient pour un entretien modeste.
  · grands jetons tenus tout le combat (la Tarasque, 3×2).

GARDES — une violation arrête tout, rien n'est écrit :
  · l'école de chaque ligne est la `magie` d'une vocation de `rules:vocations` ;
  · l'espèce existe (dump, ou un `jsons/*_a_importer.json` : AVERTISSEMENT, importer le
    bestiaire d'abord) et AUCUN autre sort ne l'invoque déjà ;
  · le profil existe et est compatible (`zones.profil_compatible`) ;
  · nombre ≤ INVOCATION_NOMBRE_MAX ; Nature n'appelle plusieurs créatures que parmi les
    ANIMAUX ; `nuee` seulement pour une école favorisée ;
  · un sort à durée de même école et même niveau existe (il fixe le lancement) ;
  · les objets de composants sont ceux qu'emploient DÉJÀ les invocations de l'école ;
  · un `_id` déjà pris (dump ou autre import) par un doc DIFFÉRENT fait tout refuser ;
    identique ⇒ sauté (idempotent).
"""

import argparse
import glob
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
DOSSIER_JSONS = os.path.join(RACINE, "jsons")
SORTIE = os.path.join(DOSSIER_JSONS, "sorts_invocation_maintenue_a_importer.json")

from utils import grimoires  # noqa: E402
from utils.combat import _espece_midpoint  # noqa: E402
from utils.sorts import INVOCATION_NOMBRE_MAX, MAINTIEN_PM_MAX  # noqa: E402
from utils.zones import profil_compatible  # noqa: E402

FAMILLE_INVOCATION = "invocation"
# Écoles dont la magie est AXÉE sur l'invocation (même parti pris que la courbe
# FAVORISÉE de gen_sorts_invocation) : leur entretien est divisé par FACTEUR_FAVORISE.
ECOLES_FAVORISEES = {"Démonologie", "Nécromancie"}
K_BASE = 90                  # P par PM d'entretien, écoles non favorisées
FACTEUR_FAVORISE = 0.6       # entretien favorisé = 60 % du tarif de base
K_FAVORISEE = K_BASE / FACTEUR_FAVORISE
MAINTIEN_MIN = 2             # sous 2, le composant de réduction n'aurait plus rien à retrancher
PART_LANCEMENT = 0.5         # du coût du sort à durée de même niveau
RITUEL_INCANTATION = 3       # PA d'armement d'un rituel
RITUEL_LANCEMENT = 1.3       # surcoût de lancement d'un rituel (payé par tranches)
# Ignorée une fois la créature tenue (compteur gelé), mais `invocation_de` exige ≥ 1.
DUREE = 3
# Vocations dont l'école n'appelle PLUSIEURS créatures que parmi les animaux.
ECOLES_NUEES_ANIMALES = {"Nature"}
TAG_ANIMAL = "animal"

# (consommé, catalyseur) par école — vérifiés contre les composants des invocations de
# l'école en base (garde), jamais inventés.
COMPOSANTS = {
	"Démonologie": ("item:Sang_demon_seche", "item:Sel_noir"),
	"Nécromancie": ("item:Sel_des_sepultures", "item:os"),
	"Sainte": ("item:Eau_benite", "item:encens"),
	"Nature": ("item:Fiole_sang_bete", "item:Branche_de_Chene"),
}

# (école, niveau, slug, nom, icon, espèce, profil, nombre, idée, description)
SORTS = [
	# ── Démonologie (favorisée) ─────────────────────────────────────────────────────
	("Démonologie", 2, "essaim_de_besiens", "Essaim de besiens", "🦇", "besien", None, 3, "nuee",
	 "Une poignée de petits démons ricanants dégringole d'une fissure. Ils ne sont rien seuls ; "
	 "tant que vous les nourrissez de votre volonté, ils sont partout à la fois."),
	("Démonologie", 4, "songe_des_incubes", "Songe des incubes", "🌙", "incube", "veteran", 2, "",
	 "Deux silhouettes trop belles sortent d'un rêve que personne n'a fait. Elles restent tant "
	 "que vous tenez le songe — et pas une seconde de plus."),
	("Démonologie", 6, "ifrit_enchaine", "Ifrit enchaîné", "🔥", "ifrit", None, 1, "",
	 "Un ifrit surgit d'une colonne de braise, une chaîne d'ombre au cou. Il hait ce lien, et "
	 "c'est toute cette haine qu'il déverse sur vos ennemis."),
	("Démonologie", 8, "main_de_la_destinee", "Main de la destinée", "🎲", "demon_majeur_de_la_destinee", "heros", 1, "",
	 "Un démon majeur de la destinée daigne poser la main sur le cours du combat. Tant que vous "
	 "tenez le pacte, chaque coup qu'il porte semble écrit d'avance."),
	("Démonologie", 10, "conclave_de_la_destinee", "Conclave de la destinée", "♾️", "demon_majeur_de_la_destinee", "seigneur", 2, "rituel",
	 "Un rituel qui se trace en plusieurs souffles, et qu'on ne peut plus interrompre. Au "
	 "dernier mot, deux seigneurs de la destinée siègent à vos côtés."),
	# ── Nécromancie (favorisée) ─────────────────────────────────────────────────────
	("Nécromancie", 2, "cortege_des_fantomes", "Cortège des fantômes", "👻", "fantome", None, 3, "nuee",
	 "Des formes pâles se lèvent du sol et glissent vers l'ennemi sans toucher terre. Chaque "
	 "âme que vous retenez ici grossit le cortège."),
	("Nécromancie", 4, "lamentation", "Lamentation", "😱", "banshee", "heros", 2, "",
	 "Deux banshees répondent à votre appel en hurlant. Leur cri ne cesse que lorsque vous "
	 "relâchez le fil qui les retient en ce monde."),
	("Nécromancie", 6, "soif_liee", "Soif liée", "🧛", "vampire", "heros", 1, "",
	 "Un vampire s'arrache à son cercueil, lié à vous par le sang. Il combat avec la faim de "
	 "ceux qui n'ont plus rien à perdre — tant que vous le nourrissez."),
	("Nécromancie", 8, "volee_funebre", "Volée funèbre", "🐦‍⬛", "corneille_noire", "champion", 2, "",
	 "Deux corneilles mortes, larges comme des hommes, tournoient au-dessus du champ de "
	 "bataille et fondent sur qui vous désignez."),
	("Nécromancie", 10, "le_comte_s_eveille", "Le comte s'éveille", "🦇", "comte_vampire", "seigneur", 1, "rituel",
	 "Le rituel s'étire sur plusieurs souffles, et rien ne doit l'interrompre. Puis le "
	 "couvercle glisse : le comte se lève, et pour un temps il consent à vous servir."),
	# ── Sainte ──────────────────────────────────────────────────────────────────────
	("Sainte", 5, "la_tarasque_domptee", "La Tarasque domptée", "🐢", "tarasque", "veteran", 1, "",
	 "Comme jadis sainte Marthe, vous passez votre ceinture au cou de la bête. La Tarasque "
	 "vous suit, docile, et broie ce que votre prière lui désigne."),
	("Sainte", 9, "destrier_celeste", "Destrier céleste", "🪽", "monture_angelique", "veteran", 1, "",
	 "Un destrier ailé descend d'un rai de lumière et charge à vos côtés. Il ne reste qu'autant "
	 "que dure votre ferveur."),
	# ── Nature ──────────────────────────────────────────────────────────────────────
	("Nature", 5, "fauve_totem", "Fauve totem", "🐆", "fauves", "champion", 1, "",
	 "Vous appelez l'esprit du grand fauve, et la bête vient en chair et en griffes. Elle "
	 "chasse avec vous tant que vous gardez le lien."),
	("Nature", 9, "ciel_de_serres", "Ciel de serres", "🦅", "rapaces", "champion", 2, "",
	 "Deux grands rapaces tournoient au-dessus de vous, puis piquent ensemble. Ils resteront "
	 "tant que votre regard porte sur le ciel."),
]


def _affiche(chemin) -> str:
	"""Relatif au dépôt ; absolu si l'autre lecteur (Windows) rend `relpath` impossible."""
	try:
		return os.path.relpath(chemin, RACINE)
	except ValueError:
		return os.path.abspath(chemin)


def dernier_dump() -> str:
	dumps = sorted(glob.glob(os.path.join(DOSSIER_JSONS, "telluris-dump-*.json")))
	if not dumps:
		raise SystemExit("Aucun telluris-dump-*.json dans jsons/ — passez --dump.")
	return dumps[-1]


def docs_des_autres_imports() -> dict:
	"""Docs des `jsons/*_a_importer.json`, par `_id` — HORS la sortie de ce script."""
	out = {}
	for chemin in sorted(glob.glob(os.path.join(DOSSIER_JSONS, "*_a_importer.json"))):
		if os.path.basename(chemin) == os.path.basename(SORTIE):
			continue
		try:
			contenu = json.load(open(chemin, encoding="utf-8"))
		except (json.JSONDecodeError, OSError):
			continue
		for doc in (contenu if isinstance(contenu, list) else [contenu]):
			if isinstance(doc, dict) and doc.get("_id"):
				out.setdefault(doc["_id"], doc)
	return out


def caracts_moyennes(espece: dict, profil: dict | None) -> dict:
	"""Caractéristiques MOYENNES d'une créature invoquée.

	Sans profil : le médian de l'espèce (`combat._espece_midpoint`, celui de l'invocation).
	Avec : l'espérance du tirage de `combat.roll_monster_stats` — chaque caractéristique vaut
	`max(min, min(max, min + delta))`, delta uniforme dans le modificateur du profil (0 s'il
	n'en a pas). Moyenne EXACTE par énumération : le budget ne doit dépendre d'aucun tirage.
	"""
	if not profil:
		m = _espece_midpoint(espece)
		return {"F": m.f, "R": m.r, "Ag": m.ag, "V": m.v}
	base = espece.get("base_attributes") or {}
	mods = profil.get("attributs_modifier") or {}
	out = {}
	for cle in ("F", "R", "Ag", "V"):
		bmin = base.get(cle, {}).get("min", 1)
		bmax = base.get(cle, {}).get("max", 5)
		mod = mods.get(cle)
		deltas = range(mod.get("min", 0), mod.get("max", 0) + 1) if mod else [0]
		valeurs = [max(bmin, min(bmax, bmin + d)) for d in deltas]
		out[cle] = sum(valeurs) / len(valeurs)
	return out


def puissance(espece: dict, profil: dict | None, nombre: int) -> float:
	"""P par round = (F + R + Ag + V×10)² × nombre / 100 (V vit à l'échelle 1-20)."""
	c = caracts_moyennes(espece, profil)
	return (c["F"] + c["R"] + c["Ag"] + c["V"] * 10) ** 2 * nombre / 100


def entretien(p: float, ecole: str) -> int:
	k = K_FAVORISEE if ecole in ECOLES_FAVORISEES else K_BASE
	return max(MAINTIEN_MIN, min(MAINTIEN_PM_MAX, round(p / k)))


def composants(ecole: str, idee: str) -> list:
	consomme, catalyseur = COMPOSANTS[ecole]
	bonus_consomme = {"invocation_nombre": 1} if idee == "nuee" else {"maintien_reduction": 2}
	return [
		{"item": consomme, "consomme": True, "bonus": bonus_consomme},
		{"item": catalyseur, "consomme": False, "bonus": {"maintien_reduction": 1}},
	]


def construire(base: dict, autres: dict) -> tuple:
	"""`(sorts, lignes, erreurs, avertissements)` — docs complets, sans rien écrire."""
	erreurs, avertissements, lignes, sorts = [], [], [], []
	ecoles_pratiquees = {v.get("magie") for v in (base.get("rules:vocations") or {}).get("value") or []}
	tous = {**autres, **base}
	invoquees = {}
	for d in tous.values():
		if d.get("type") == "sort" and d.get("invocation"):
			invoquees.setdefault((d.get("invocation") or {}).get("espece"), d["_id"])
	# Lancement : le sort À DURÉE de même école et niveau, relu (jamais retapé).
	a_duree = {(d.get("magie"), d.get("niveau")): d for d in tous.values()
			   if d.get("type") == "sort" and d.get("invocation") and not d.get("maintien")}
	composants_ecole = {}
	for d in base.values():
		if d.get("type") == "sort" and d.get("invocation"):
			for c in d.get("composants") or []:
				composants_ecole.setdefault(d.get("magie"), set()).add(c.get("item"))

	vus = set()
	for (ecole, niveau, slug, nom, icon, espece_slug, profil_slug, nombre, idee, description) in SORTS:
		sid = "sort:" + slug
		if ecole not in ecoles_pratiquees:
			erreurs.append(f"{sid} : école « {ecole} » pratiquée par aucune vocation")
		if (ecole, niveau) in vus:
			erreurs.append(f"{sid} : deux sorts {ecole} de niveau {niveau}")
		vus.add((ecole, niveau))
		espece_id = "espece:" + espece_slug
		espece = base.get(espece_id)
		if espece is None and (autres.get(espece_id) or {}).get("type") == "espece":
			espece = autres[espece_id]
			avertissements.append(f"{sid} : {espece_id} n'existe que dans un import — "
								  f"importer le bestiaire AVANT ce sort")
		if not espece or espece.get("type") != "espece":
			erreurs.append(f"{sid} : {espece_id} absent du bestiaire")
			continue
		deja = invoquees.get(espece_id)
		if deja and deja != sid:
			erreurs.append(f"{sid} : {espece_id} est déjà invoquée par {deja}")
		profil = None
		if profil_slug:
			profil = base.get("profil:" + profil_slug)
			if not profil:
				erreurs.append(f"{sid} : profil:{profil_slug} absent du dump")
				continue
			if not profil_compatible(profil, espece):
				erreurs.append(f"{sid} : profil:{profil_slug} incompatible avec {espece_id}")
		if not 1 <= nombre <= INVOCATION_NOMBRE_MAX:
			erreurs.append(f"{sid} : nombre {nombre} hors de [1, {INVOCATION_NOMBRE_MAX}]")
		if (ecole in ECOLES_NUEES_ANIMALES and nombre > 1
				and TAG_ANIMAL not in (espece.get("tags") or [])):
			erreurs.append(f"{sid} : {ecole} appelle {nombre}× {espece_id}, qui n'est pas un animal")
		if idee == "nuee" and ecole not in ECOLES_FAVORISEES:
			erreurs.append(f"{sid} : la nuée qui enfle est réservée aux écoles favorisées")
		for item in COMPOSANTS.get(ecole, ()):
			if item not in composants_ecole.get(ecole, set()):
				erreurs.append(f"{sid} : {item} n'est le composant d'aucune invocation {ecole}")
		reference = a_duree.get((ecole, niveau))
		if not reference:
			erreurs.append(f"{sid} : aucun sort d'invocation à durée {ecole} de niveau {niveau}")
			continue

		p = puissance(espece, profil, nombre)
		maintien = entretien(p, ecole)
		cout_pm = round(int(reference.get("cout_pm") or 0) * PART_LANCEMENT
						* (RITUEL_LANCEMENT if idee == "rituel" else 1))
		invocation = {"espece": espece_id, "nombre": nombre, "duree": DUREE}
		if profil_slug:
			invocation["profil"] = "profil:" + profil_slug
		doc = {
			"_id": sid,
			"type": "sort",
			"nom": nom,
			"icon": icon,
			"description": description,
			"magie": ecole,
			"famille": FAMILLE_INVOCATION,
			"niveau": niveau,
			"cout_pm": cout_pm,
			"maintien": maintien,
			"cible": "soi",
			"portee": 0,
			"effets": {},
			"invocation": invocation,
			"composants": composants(ecole, idee),
		}
		if idee == "rituel":
			doc["incantation"] = RITUEL_INCANTATION
		sorts.append(doc)
		lignes.append(f"{sid:38} {ecole:12} niv {niveau:2}  {nombre}× {espece.get('nom', espece_slug):30} "
					  f"{profil_slug or '(médian)':9}  P {p:6.0f}  lance {cout_pm:3} PM  "
					  f"entretien {maintien:2} PM/round{'  rituel' if idee == 'rituel' else ''}"
					  f"{'  nuée' if idee == 'nuee' else ''}")
	return sorts, lignes, erreurs, avertissements


def _sans_rev(doc: dict) -> dict:
	return {k: v for k, v in (doc or {}).items() if k != "_rev"}


def main(argv=None) -> int:
	try:
		sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	except Exception:
		pass
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("--dump", default=None)
	ap.add_argument("--sortie", default=SORTIE)
	args = ap.parse_args(argv)
	chemin = args.dump or dernier_dump()
	base = {d["_id"]: d for d in json.load(open(chemin, encoding="utf-8"))["docs"]
			if isinstance(d, dict) and d.get("_id")}
	autres = docs_des_autres_imports()

	sorts, lignes, erreurs, avertissements = construire(base, autres)
	neufs, sautes = [], []
	for doc in sorts:
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
			neufs.append(doc)

	print(f"Dump lu : {_affiche(chemin)}\n\n== Invocations maintenues")
	for ligne in lignes:
		print("   " + ligne)
	grim_docs, grim_lignes, grim_erreurs = grimoires.grimoires_manquants(base, neufs)
	erreurs.extend(grim_erreurs)
	# `grimoires_manquants` ne connaît que la base : un autre import peut avoir pris l'`_id`.
	for doc in grim_docs:
		existant = autres.get(doc["_id"])
		if existant is not None and _sans_rev(existant) != doc:
			erreurs.append(f"{doc['_id']} : `_id` déjà pris (import) par un doc différent")
	print("\n== Grimoires et recettes manquants")
	for ligne in grim_lignes:
		print("   " + ligne)
	for a in avertissements:
		print("⚠️ " + a)
	if erreurs:
		print(f"\nREFUS — {len(erreurs)} erreur(s), rien n'est écrit :")
		for e in erreurs:
			print("  · " + e)
		return 1

	docs = neufs + grim_docs
	with open(args.sortie, "w", encoding="utf-8", newline="\n") as f:
		json.dump(docs, f, ensure_ascii=False, indent=2)
		f.write("\n")
	print(f"\n{len(docs)} doc(s) écrits dans {_affiche(args.sortie)} — {len(neufs)} sort(s), "
		  f"{sum(1 for d in grim_docs if d['type'] == 'item')} grimoire(s), "
		  f"{sum(1 for d in grim_docs if d['type'] == 'recette')} recette(s)"
		  + (f", {len(sautes)} déjà en base à l'identique" if sautes else ""))
	return 0


if __name__ == "__main__":
	sys.exit(main())
