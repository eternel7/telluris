# utils/recrutement.py
# Recrutement d'aventuriers (mode opportuniste) : un lieu recruteur (tag "recrutement"
# ou guilde d'aventuriers) tient un tableau de recrues GÉNÉRÉES — docs `aventurier:*`
# MIROIRS du character (mêmes champs que consomment build_joueur_snapshot,
# compute_derived_stats, grant_xp, carried_weight…) → tout le moteur de combat marche
# dessus tel quel. Le tableau tourne comme celui des quêtes (péremption paresseuse,
# durée jittée) ; un ancien compagnon apprécié (`statut:"parti"`, affinité ≥ seuil)
# y est RÉ-OFFERT — c'est là que les liens mémorisés influencent la disponibilité.
#
# Le contrat dure jusqu'au congédiement (+ départ de lui-même si l'affinité tombe sous
# AFFINITE_SEUIL_DEPART). Embauche gratuite ; la recrue exige une PART du butin,
# prélevée sur le cuivre des récompenses de quête au turn-in (`regler_part_butin`,
# chokepoint unique) — sauf s'il est engagé DURABLEMENT : au-delà d'AFFINITE_SEUIL_ENGAGEMENT
# il renonce à sa part, sort du plafond de groupe et rejoint la COMPAGNIE du joueur
# (`engager_permanent`), que seul un congédiement coûteux dénoue. Les clauses
# de conduite doivent être ACCEPTÉES pour que l'embauche ait lieu : les refuser retire la
# recrue du tableau (`retirer_du_tableau`). Leur respect n'est pas détecté en jeu (v1) —
# elles engagent le joueur moralement, pas mécaniquement.
#
# Comme utils/quetes.py : logique pure, ne sauvegarde jamais — SAUF
# `remplir_tableau_recrues`, qui persiste les recrues nouvellement générées (création
# des docs au tableau). Les helpers d'état mutent les docs en place ; l'endpoint
# persiste. World-vars lues via le module (jamais from-import).

import os
import random
import time
import uuid

from db.config import get_doc, save_doc, find_docs, delete_doc
from models import character_stats
from models.character_stats import BaseStats, compute_derived_stats, xp_seuil_niveau
from utils.characters import (
	item_ref_id, item_ref_lieu, item_ref_weight, resolve_item_ref, sync_equipment_bonus,
	credit_character, carried_weight, charge_max_of,
)
from utils.consommables import caracts_avec_buffs
from utils import montures


def now_epoch() -> int:
	return int(time.time())


# La carte d'aventurier est un objet GÉNÉRIQUE (un seul doc pour toutes les guildes) :
# c'est le `lieu_parent` de l'INSTANCE en sac qui dit de quelle cité on est membre.
CARTE_AVENTURIER_ITEM_ID = "item:carte_aventurier"

# Slots d'équipement d'un personnage (miroir exact d'add_character, routers/user.py).
SLOTS_PERSONNAGE = [
	"main_droite", "main_gauche", "torse", "tete", "jambes", "pieds",
	"mains", "anneau_1", "anneau_2", "cou", "ceinture",
]

# Rang affiché, dérivé du niveau (F = débutant, comme les quêtes générées).
RANGS = ["F", "E", "D", "C", "B", "A", "S", "S+"]

# Clauses de conduite types (données affichées, sans détection de violation en v1).
CLAUSES_TYPES = [
	"Ne pille pas les morts avant la fin du combat.",
	"Refuse de s'attaquer aux bêtes de somme.",
	"Exige un repas chaud par jour de contrat.",
	"Ne combat pas les morts-vivants de nuit.",
	"Garde toujours une monture ou une place de charrette.",
	"Refuse d'entrer dans les égouts.",
	"Ne travaille pas pour un employeur banni d'une guilde.",
	"Exige d'être payé rubis sur l'ongle, sans délai.",
	"Refuse de camper à moins d'une lieue d'un cimetière.",
	"Exige une part double si le contrat implique des dragons ou des wyvernes.",
	"Ne combat jamais sous une pluie battante.",
	"Exige d'avoir le dernier mot sur le choix de son propre équipement.",
	"Refuse catégoriquement de porter le moindre message secret.",
	"Ne travaille pas si le groupe compte plus d'un magicien.",
	"Garde toujours la moitié de sa prime d'embauche en cas de retraite anticipée.",
	"Exige un jour de repos complet après chaque affrontement majeur.",
	"Refuse d'attaquer une cible de dos ou par surprise.",
	"Ne franchit aucun portail magique sans une compensation financière.",
	"Exige que sa monture soit nourrie aux frais de l'employeur.",
	"Refuse de s'enfoncer dans un donjon sans une carte ou un guide local.",
	"Ne participe à aucune fouille de coffre potentiellement piégé.",
	"Exige d'être logé dans une vraie taverne, jamais à la belle étoile en ville.",
	"Refuse de lever l'épée contre un membre de son ancienne compagnie.",
	"Exige une prime de risque immédiate si la cible s'avère être un noble."
]

# Prénoms/noms par race (repli "defaut"). Constantes de module : le contenu peut être
# enrichi ici sans toucher à la logique.
#
# Les PRÉNOMS ne sont pas cloisonnés : les humains vivant partout, un nain ou un hobbit
# né en cité humaine peut porter un prénom humain (PRENOM_RACE_MUTUALISEE, tiré avec la
# proba PRENOM_MUTUALISE_PROBA). Les NOMS, eux, restent racialement stricts — un nom de
# famille dit une lignée, pas un voisinage.
PRENOMS = {
    "humain": {
        "M": ["Aldric", "Bertrand", "Corentin", "Enguerrand", "Gaultier", "Renaud", "Thibaut", "Amaury", "Baudouin", "Gautier", "Godefroy", "Josselin", "Lothaire", "Raoul"],
        "F": ["Adélaïde", "Blanche", "Clotilde", "Héloïse", "Mathilde", "Rosamonde", "Ysabeau", "Aliénor", "Béatrice", "Emmeline", "Geneviève", "Gisèle", "Hermine", "Isabeau"]
    },
    "elfe": {
        "M": ["Aelthir", "Caelun", "Faelor", "Lorandril", "Sylvarel", "Thalion", "Aerandir", "Earendil", "Finrod", "Haldir", "Lindir", "Valandil"],
        "F": ["Aelwen", "Elenwë", "Lithrielle", "Nimloth", "Sylvaine", "Yavielle", "Celebrian", "Galadriel", "Idril", "Laurelin", "Melian", "Tinuviel"]
    },
    "nain": {
        "M": ["Balrik", "Dorin", "Grimnur", "Kazrag", "Morgrim", "Thorgan", "Bofur", "Dwalin", "Gimli", "Gloin", "Kili", "Thorin"],
        "F": ["Berga", "Dagna", "Helga", "Runa", "Sigrun", "Thyra", "Dis", "Frida", "Gerd", "Hilda", "Ingrid", "Sif"]
    },
    "ogre": {
        "M": ["Brog", "Dhurk", "Gronk", "Krug", "Morg", "Thok", "Brag", "Gark", "Gor", "Krosh", "Ogg", "Urk"],
        "F": ["Brakka", "Gruna", "Morga", "Ruk", "Thura", "Urga", "Garka", "Groka", "Morka", "Rakka", "Ugra", "Zouga"]
    },
    "hobbit": {
        "M": ["Bingo", "Drogon", "Falco", "Milo", "Podo", "Tolman", "Bungo", "Fastolf", "Flourdelys", "Olo", "Rufus", "Wilco"],
        "F": ["Amaranthe", "Belladone", "Mirabelle", "Pervenche", "Primula", "Salvia", "Camélia", "Eglantine", "Lobelia", "Menthe", "Myrtille", "Pâquerette"]
    },
    "defaut": {
        "M": ["Jor", "Kel", "Mar", "Ren", "Dan", "Gor", "Mal", "Zor"],
        "F": ["Ana", "Isa", "Lena", "Mira", "Aya", "Eva", "Lia", "Nia"]
    },
}
NOMS = {
    "humain": ["de Hautterre", "Ferrant", "Leloup", "Morvan", "du Guet", "Vaillancourt",
		"Beauvisage", "Chassevent", "Dumont", "Grandpas", "Rochefort", "Valois"],
    "elfe": ["Feuillargent", "Lunevoile", "Sombrefrêne", "Ventelame", "Écorcelune",
        "Astrebrillant", "Briseflammes", "Cielazur", "Fleurépine", "Rondevalle"],
    "nain": ["Barbeforge", "Fendroc", "Grave-Enclume", "Piochefer", "Rudemarteau",
        "Brise-Mine", "Cœur-d'Acier", "Fort-Armure", "Fouille-Filons", "Lourde-Hache"],
    "ogre": ["Brise-Os", "Croque-Pierre", "Deux-Massues", "Grande-Faim", "Tord-Boyaux",
        "Avale-Tout", "Gros-Bide", "Lourde-Patte", "Mâche-Fer", "Pousse-Rocs"],
    "hobbit": ["Bonpré", "Fouilleterre", "Pied-Léger", "Souscolline", "Troisquarts",
        "Basse-Vallée", "Chaud-Chaudron", "Douce-Amande", "Petit-Pas", "Verte-Herbe"],
    "defaut": ["Sans-Terre", "l'Errant", "du Chemin",
        "l'Inconnu", "le Muet", "Sans-Nom"],
}

# Race dont le répertoire de prénoms déborde sur les autres, et fréquence du débordement.
PRENOM_RACE_MUTUALISEE = "humain"
PRENOM_MUTUALISE_PROBA = 0.25


def prenoms_possibles(race_id: str, sex: str) -> list:
	"""Pool de prénoms tirable pour (race, sexe). Toujours celui de la race — sauf tirage
	à PRENOM_MUTUALISE_PROBA pour une race AUTRE que PRENOM_RACE_MUTUALISEE, qui rend alors
	le pool humain : un aventurier non-humain élevé en cité humaine porte un prénom d'ici.
	Renvoie une liste non vide (replis : autre sexe du pool, puis "defaut")."""
	def pool(rid: str) -> list:
		p = PRENOMS.get(rid) or PRENOMS["defaut"]
		return p.get(sex) or p.get("M") or []

	if race_id != PRENOM_RACE_MUTUALISEE and random.random() < PRENOM_MUTUALISE_PROBA:
		emprunt = pool(PRENOM_RACE_MUTUALISEE)
		if emprunt:
			return emprunt
	return pool(race_id) or PRENOMS["defaut"].get(sex) or PRENOMS["defaut"]["M"]


# ── Éligibilité du lieu ──────────────────────────────────────────────────────────

def lieu_recrute(lieu_doc: dict) -> bool:
	"""Le lieu affiche-t-il un tableau de recrues ? Tag `recrutement` OU guilde
	d'aventuriers (le OU évite une migration : les guildes existantes recrutent sans
	réimport ; le tag permet d'ouvrir n'importe quel autre lieu — taverne, caserne…)."""
	lieu_doc = lieu_doc or {}
	return ("recrutement" in (lieu_doc.get("tags") or [])
			or lieu_doc.get("categorie") == "guilde_aventurier")


def offre_du_lieu(lieu_doc: dict, parent_doc: dict | None) -> dict:
	"""{nb, niveau_max} du tableau : entrée de RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE pour
	la `sous_categorie` de la CITÉ (repli "defaut"), surchargée champ à champ par
	`lieu.recrutement_restrictions` (un lieu peut brider son offre sans toucher la table)."""
	table = character_stats.RECRUTEMENT_OFFRE_PAR_SOUS_CATEGORIE
	sous_cat = (parent_doc or {}).get("sous_categorie")
	base = table.get(sous_cat) or table.get("defaut") or {"nb": 2, "niveau_max": 1}
	offre = {"nb": int(base.get("nb", 2)), "niveau_max": int(base.get("niveau_max", 1))}
	restrictions = (lieu_doc or {}).get("recrutement_restrictions")
	if isinstance(restrictions, dict):
		for k in ("nb", "niveau_max"):
			if k in restrictions:
				try:
					offre[k] = int(restrictions[k])
				except (TypeError, ValueError):
					pass
	return offre


def acces_autorise(character: dict, lieu_doc: dict) -> tuple[bool, str]:
	"""Le personnage peut-il consulter le tableau ? Si RECRUTEMENT_CARTE_REQUISE, il
	doit porter une carte d'aventurier dont l'instance vient de la CITÉ du lieu
	(`item_ref_lieu == lieu_parent`) — la carte générique d'une autre guilde ne vaut
	rien ici. Retourne (ok, raison)."""
	if not character_stats.RECRUTEMENT_CARTE_REQUISE:
		return True, ""
	cite = (lieu_doc or {}).get("lieu_parent")
	for ref in character.get("inventaire", []):
		if item_ref_id(ref) == CARTE_AVENTURIER_ITEM_ID and item_ref_lieu(ref) == cite:
			return True, ""
	return False, "La carte d'aventurier de cette cité est requise pour consulter le tableau."


# ── Génération procédurale d'une recrue ──────────────────────────────────────────

def decomposer_portrait(fichier: str) -> tuple | None:
	"""`{voc}_{sexe}_{race}NN.ext` → `(voc, sexe, race)`, en minuscules. None si le fichier
	ne suit pas la règle de nommage (il est alors ignoré, jamais tiré au hasard)."""
	base = os.path.splitext(fichier)[0].lower()
	morceaux = base.split("_")
	if len(morceaux) != 3:
		return None
	voc, sexe, reste = morceaux
	race = reste.rstrip("0123456789")
	if not voc or not sexe or not race:
		return None
	return voc, sexe, race


def choisir_portrait(voc: str, sex: str, race: str, portraits: list) -> str:
	"""Portrait par nommage `{voc}_{sexe}_{race}NN.jpg` (zéro asset nouveau).

	⚠️ SEXE et RACE sont STRICTS : ils sont écrits partout ailleurs sur la recrue (fiche,
	carte, jeton de combat), un portrait d'une autre race mentirait. Seule la VOCATION se
	relâche — elle ne se lit qu'à la tenue. Repli unique : même sexe + même race, autre
	vocation. Chaîne vide si ce couple n'a aucun portrait — un visage juste ou rien."""
	s = (sex or "M").lower()
	r = (race or "").lower()
	v = (voc or "").lower()
	memes, exacts = [], []
	for p in portraits:
		infos = decomposer_portrait(p)
		if not infos or infos[1] != s or infos[2] != r:
			continue
		memes.append(p)
		if infos[0] == v:
			exacts.append(p)
	pool = exacts or memes
	return random.choice(pool) if pool else ""


def portraits_disponibles() -> list:
	"""Fichiers du dossier des portraits (même dossier que la validation d'add_character)."""
	dossier = os.path.join(os.path.dirname(__file__), "..", "templates", "resources", "characters")
	try:
		return [f for f in os.listdir(dossier) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
	except OSError:
		return []


def _repartir_points(caract: dict, stats_max: dict, budget: int) -> None:
	"""Répartit `budget` points de création sur les caractéristiques (mute en place).
	Miroir du budget `bonusStats` d'add_character : le +N-ième point d'une stat coûte
	N × XP_COEFF (V coûte 10× — quasi inaccessible sur 10 points, comme un joueur)."""
	bonus: dict = {}
	for _ in range(200):
		candidats = []
		for k in caract:
			coeff = character_stats.XP_COEFF.get(k, 1)
			cout = (bonus.get(k, 0) + 1) * coeff
			if cout <= budget and caract[k] + 1 <= stats_max.get(k, caract[k] + 1):
				candidats.append((k, cout))
		if not candidats:
			break
		k, cout = random.choice(candidats)
		caract[k] += 1
		bonus[k] = bonus.get(k, 0) + 1
		budget -= cout


def _monter_niveaux(caract: dict, stats_max: dict, points: int) -> None:
	"""Dépense les points de montée de niveau (1 point = +1 sur une stat hors V,
	borné au max racial) — l'équivalent simplifié des spend_xp d'un joueur."""
	for _ in range(max(0, int(points))):
		candidats = [k for k in caract
					 if k != "V" and caract[k] + 1 <= stats_max.get(k, caract[k])]
		if not candidats:
			break
		caract[random.choice(candidats)] += 1


def _equiper_defaut(aventurier: dict) -> None:
	"""Équipe l'inventaire de départ dans les `slots` (mute en place) : chaque item est
	posé dans son premier slot compatible libre (champ item `slots`). Indispensable —
	`_weapon_attacks` et `recompute_equipment_bonus` ne lisent QUE les slots ; un item
	sans slot libre reste dans le sac."""
	restants = []
	for ref in aventurier.get("inventaire", []):
		item = resolve_item_ref(ref)
		place = None
		for slot in (item or {}).get("slots") or []:
			if slot in aventurier["slots"] and aventurier["slots"][slot] is None:
				place = slot
				break
		if place:
			aventurier["slots"][place] = ref
		else:
			restants.append(ref)
	aventurier["inventaire"] = restants


def _derives_de(aventurier: dict):
	"""Stats dérivées du doc aventurier (mêmes helpers que le character : équipement
	synchronisé puis buffs repliés). Mute `equipment_bonus` en place."""
	equipment = sync_equipment_bonus(aventurier)
	stats = caracts_avec_buffs(aventurier)
	base = BaseStats(
		v=stats.get("V", 0), f=stats.get("F", 0), r=stats.get("R", 0),
		ag=stats.get("Ag", 0), vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
		cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
	)
	voc_niveau = aventurier.get("vocations_niveaux", {}).get(aventurier.get("voc", ""), 0)
	return compute_derived_stats(base, niveau=voc_niveau, equipment=equipment)


def vitaux_de(aventurier: dict) -> dict:
	"""État vital d'un compagnon (courants + max dérivés) pour les payloads : le doc du
	compagnon est la source, ses max se recalculent comme ceux du joueur (jamais stockés)."""
	derived = _derives_de(aventurier)
	return {
		"currentPV": aventurier.get("currentPV", derived.pv_max),
		"pv_max": derived.pv_max,
		"currentPM": aventurier.get("currentPM", derived.pm_max),
		"pm_max": derived.pm_max,
	}


def _duree_de_vie_recrue() -> int:
	"""Durée d'affichage d'une recrue au tableau, jittée (miroir de quetes._duree_de_vie) :
	les recrues d'un même lot ne partent pas toutes en bloc."""
	base = int(character_stats.RECRUTEMENT_BOARD_DUREE_SECONDES)
	jitter = max(0.0, float(character_stats.RECRUTEMENT_BOARD_DUREE_JITTER))
	return max(1, int(base * random.uniform(1.0 - jitter, 1.0 + jitter)))


def _tirer_exigences(niveau: int) -> dict:
	"""Part de butin tirée dans [MIN, MAX], biaisée HAUT avec le niveau (un vétéran se
	vend plus cher), + 0-2 clauses de conduite. Objet OUVERT : la phase 2 y ajoutera
	`salaire_jour_cuivre` sans casser les lecteurs."""
	pmin = int(character_stats.RECRUTEMENT_PART_BUTIN_MIN)
	pmax = max(pmin, int(character_stats.RECRUTEMENT_PART_BUTIN_MAX))
	lo = min(pmax, pmin + 2 * max(0, niveau))
	part = random.randint(lo, pmax)
	clauses = random.sample(CLAUSES_TYPES, k=random.randint(0, 2))
	return {"part_butin_pct": part, "clauses": clauses}


def generer_aventurier(guild_doc: dict, parent_doc: dict | None, niveau_max: int,
					   portraits: list | None = None) -> dict | None:
	"""Doc `aventurier:*` procédural, MIROIR du character : race/sexe/vocation tirés sur
	rules:races / rules:vocations, stats = base raciale + budget de création (≈10 pts)
	+ points de niveau, équipement de base ÉQUIPÉ dans les slots, PV/PM = max dérivés.
	None si les rules sont absentes (contenu non importé)."""
	races = (get_doc("rules:races") or {}).get("value") or []
	vocations = (get_doc("rules:vocations") or {}).get("value") or []
	if not races or not vocations:
		return None

	race = random.choice(races)
	vocation = random.choice(vocations)
	sex = random.choice(["M", "F"])
	niveau = random.randint(0, max(0, int(niveau_max)))

	caract = dict(race.get("stats", {}))
	stats_max = race.get("stats_max", {})
	_repartir_points(caract, stats_max, 10)
	_monter_niveaux(caract, stats_max, niveau * character_stats.RECRUTEMENT_NIVEAU_POINTS_PAR_NIVEAU)

	# Équipement de départ de la vocation, validé (réf morte ignorée, comme add_character).
	inventaire = [ref for ref in vocation.get("equipement_de_base", []) if resolve_item_ref(ref)]

	if portraits is None:
		portraits = portraits_disponibles()
	prenoms = prenoms_possibles(race.get("id", ""), sex)
	noms = NOMS.get(race.get("id"), NOMS["defaut"])

	guild_id = guild_doc.get("_id", "")
	sub = guild_id.split(":", 1)[-1] if ":" in guild_id else guild_id
	now = now_epoch()
	aventurier = {
		"_id": f"aventurier:{sub}_{uuid.uuid4().hex[:12]}",
		"type": "aventurier",
		"statut": "offert",
		"giver": guild_id,
		"lieu_parent": (parent_doc or {}).get("_id"),
		"prenom": random.choice(prenoms),
		"nom": random.choice(noms),
		"sex": sex,
		"race": race.get("id", ""),
		"voc": vocation.get("id", ""),
		"image": choisir_portrait(vocation.get("id", ""), sex, race.get("id", ""), portraits),
		"caracteristiques_current": caract,
		"currentPV": 0,   # posés au max dérivé ci-dessous
		"currentPM": 0,
		"vocations_niveaux": {vocation.get("id", ""): niveau},
		# xp_total juste au-dessus du seuil → compute_character_level == niveau.
		"xp_total": xp_seuil_niveau(niveau) + (1 if niveau > 0 else 0),
		"attribute_points": 0,
		"inventaire": inventaire,
		"slots": {s: None for s in SLOTS_PERSONNAGE},
		"equipment_bonus": {},
		"sorts_connus": [],
		"competences_connues": [],
		"competences_bonus": {},
		"effets_actifs": [],
		"or": 0, "argent": 0, "cuivre": 0,
		"combats_recompenses": [],
		"rang": RANGS[min(niveau, len(RANGS) - 1)],
		"specialite": vocation.get("blurb", ""),
		"exigences": _tirer_exigences(niveau),
		"genere_at": now,
		"expire_at": now + _duree_de_vie_recrue(),
	}
	_equiper_defaut(aventurier)
	derived = _derives_de(aventurier)
	aventurier["currentPV"] = derived.pv_max
	aventurier["currentPM"] = derived.pm_max
	return aventurier


# ── Tableau de recrues (rotation paresseuse, miroir du board de quêtes) ─────────

def recrue_perimee(av: dict, now: int) -> bool:
	"""Une recrue encore OFFERTE dont l'échéance est passée : elle a trouvé un contrat
	ailleurs. Ne concerne jamais un compagnon embauché ni parti (leur doc porte la
	mémoire du lien). Repli sans `expire_at` : genere_at + durée nominale."""
	if av.get("statut") != "offert":
		return False
	expire_at = av.get("expire_at")
	if not expire_at:
		genere_at = int(av.get("genere_at", 0) or 0)
		expire_at = genere_at + int(character_stats.RECRUTEMENT_BOARD_DUREE_SECONDES) if genere_at else 0
	return now >= int(expire_at)


def retirer_du_tableau(av: dict) -> None:
	"""Retire définitivement une recrue du tableau — CHOKEPOINT unique des deux motifs :
	péremption de l'offre et refus des clauses par le joueur. Une recrue JAMAIS embauchée
	est supprimée de la base (personne ne la référence) ; un ANCIEN compagnon ré-offert
	repasse simplement `parti` (son doc porte l'affinité mémorisée — le détruire romprait
	le lien) et pourra revenir. PERSISTE lui-même (ou supprime), best-effort."""
	if av.get("embauche_par"):
		av["statut"] = "parti"
		av.pop("expire_at", None)
		save_doc(av)
	else:
		delete_doc(av)


def peut_refuser(av: dict) -> tuple[bool, str]:
	"""(ok, raison) : on ne refuse les conditions que d'une recrue encore OFFERTE — un
	compagnon déjà embauché se congédie, il ne se refuse pas."""
	if (av or {}).get("statut") != "offert":
		return False, "Cette recrue n'est plus disponible."
	return True, ""


def purger_recrues_perimees(recrues: list, now: int) -> list:
	"""Retire du tableau les recrues périmées (via `retirer_du_tableau`, qui tranche entre
	suppression et retour au statut `parti`). Renvoie les recrues qui restent."""
	restantes = []
	for av in recrues:
		if recrue_perimee(av, now):
			retirer_du_tableau(av)
		else:
			restantes.append(av)
	return restantes


def recrues_du_giver(guild_id: str) -> list:
	"""Recrues OFFERTES au tableau d'un lieu recruteur."""
	docs = find_docs({"type": "aventurier"}) or []
	return [d for d in docs if d.get("giver") == guild_id and d.get("statut") == "offert"]


def anciens_compagnons_disponibles(character: dict, guild_id: str) -> list:
	"""Anciens compagnons PARTIS de ce giver dont l'affinité avec CE personnage vaut le
	retour (≥ AFFINITE_SEUIL_REMISE) : les liens mémorisés influencent la disponibilité."""
	seuil = int(character_stats.AFFINITE_SEUIL_REMISE)
	affinites = character.get("affinites", {}) or {}
	docs = find_docs({"type": "aventurier"}) or []
	return [
		d for d in docs
		if d.get("giver") == guild_id and d.get("statut") == "parti"
		and int(affinites.get(d.get("_id"), 0) or 0) >= seuil
	]


def remplir_tableau_recrues(guild_doc: dict, character: dict) -> list:
	"""Purge les recrues périmées PUIS garantit `offre.nb` recrues au tableau : ré-offre
	d'abord les anciens compagnons appréciés (ils reprennent du service en priorité —
	nouvel `expire_at`, statut `offert`), complète avec des recrues générées, persiste,
	et renvoie le tableau."""
	guild_id = guild_doc.get("_id")
	parent_id = guild_doc.get("lieu_parent")
	parent_doc = get_doc(parent_id) if parent_id else None
	offre = offre_du_lieu(guild_doc, parent_doc)

	recrues = purger_recrues_perimees(recrues_du_giver(guild_id), now_epoch())
	manquantes = max(0, int(offre["nb"]) - len(recrues))

	for ancien in anciens_compagnons_disponibles(character, guild_id):
		if manquantes <= 0:
			break
		ancien["statut"] = "offert"
		ancien["expire_at"] = now_epoch() + _duree_de_vie_recrue()
		if save_doc(ancien) is None:
			continue
		recrues.append(ancien)
		manquantes -= 1

	for _ in range(manquantes):
		av = generer_aventurier(guild_doc, parent_doc, offre["niveau_max"])
		if av is None:
			break
		if save_doc(av) is None:
			continue
		recrues.append(av)
	return recrues


# ── Groupe, embauche & congédiement ──────────────────────────────────────────────

def taille_max_groupe() -> int:
	return int(character_stats.RECRUTEMENT_GROUPE_TAILLE_MAX)


def groupe_effectif(character: dict, get_doc_fn=None) -> list:
	"""Docs des compagnons ACTIFS du groupe : ids de `character["groupe"]` résolus,
	filtrés sur statut `embauche` + embauché PAR CE personnage (l'état du compagnon
	vit sur SON doc — un id périmé est ignoré silencieusement)."""
	lire = get_doc_fn or get_doc
	out = []
	for av_id in character.get("groupe", []) or []:
		av = lire(av_id)
		if av and av.get("statut") == "embauche" and av.get("embauche_par") == character.get("_id"):
			out.append(av)
	return out


def porteurs_effectifs(character: dict, get_doc_fn=None) -> list:
	"""Tous ceux qui portent des objets pour le joueur : compagnons PUIS montures.
	SOURCE UNIQUE de « qui porte pour moi » — la preuve d'appartenance est la même des
	deux côtés (statut + lien vers CE personnage : `embauche`/`embauche_par` pour un
	compagnon, `acquise`/`acquise_par` pour une monture). L'ordre compte : le client
	range les montures en fin de liste."""
	return (groupe_effectif(character, get_doc_fn)
			+ montures.montures_effectives(character, get_doc_fn))


# ── Inventaire du groupe : transfert d'objets ────────────────────────────────────

def _localiser_ref(refs: list, idx, item_id) -> int | None:
	"""Position de la référence ciblée dans une liste d'inventaire. On adresse par index
	(deux exemplaires d'un même item peuvent avoir des poids d'instance distincts), vérifié
	via `item_id` ; repli sur le premier exemplaire de l'item si l'index est désaligné.
	Miroir de `_take_ref` (routers/user.py) mais en LECTURE : le transfert doit pouvoir
	refuser AVANT de retirer quoi que ce soit de la source."""
	if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(refs) \
			and (item_id is None or item_ref_id(refs[idx]) == item_id):
		return idx
	if item_id is not None:
		return next((i for i, r in enumerate(refs) if item_ref_id(r) == item_id), None)
	return None


def peut_porter(porteur: dict, ref) -> bool:
	"""Le porteur peut-il encaisser CET exemplaire sans dépasser sa charge max ? On compare
	le poids d'instance (pas le minimum du doc item) au plafond du porteur — délégué à
	`montures.charge_max_porteur`, qui aiguille entre `charge_max_of` (F×5, non buffée) et
	la capacité démultipliée d'une monture. Le groupe contient les deux."""
	return carried_weight(porteur) + item_ref_weight(ref) <= montures.charge_max_porteur(porteur)


def transferer_ref(source: dict, cible: dict, idx, item_id) -> tuple[bool, str, object]:
	"""Passe un objet du sac de `source` à celui de `cible`. Refus DUR si la charge max du
	destinataire est dépassée — et dans ce cas la source n'est pas amputée (on localise
	avant de retirer). Mute les deux docs en place, NE SAUVEGARDE PAS (l'endpoint persiste).
	Renvoie (ok, raison, ref transférée|None). Seul l'inventaire est concerné : un objet
	équipé n'y est pas, il faut le déséquiper d'abord."""
	refs = source.get("inventaire", []) or []
	pos = _localiser_ref(refs, idx, item_id)
	if pos is None:
		return False, "Objet absent de l'inventaire", None

	ref = refs[pos]
	if not peut_porter(cible, ref):
		# Une monture n'a pas de `prenom` : replier sur `nom` avant le générique, sinon
		# elle serait toujours annoncée comme « Le destinataire ».
		qui = ((cible.get("prenom") or "").strip() or (cible.get("nom") or "").strip()
			   or "Le destinataire")
		return False, f"{qui} ne peut pas porter davantage.", None

	refs.pop(pos)
	source["inventaire"] = refs
	cible.setdefault("inventaire", []).append(ref)
	return True, "", ref


def affinite_de(character: dict, av_id: str) -> int:
	"""Affinité mémorisée avec un compagnon (neutre AFFINITE_INITIALE si inconnue)."""
	val = (character.get("affinites", {}) or {}).get(av_id)
	if val is None:
		return int(character_stats.AFFINITE_INITIALE)
	return int(val)


def conditions_effectives(av: dict, affinite: int) -> dict:
	"""Exigences EFFECTIVES pour ce personnage : la part de butin baisse de 1 point par
	AFFINITE_REDUC_PART points d'affinité au-dessus de 50 (plancher = PART_BUTIN_MIN) —
	un compagnon qui vous apprécie rogne moins la bourse. Clauses inchangées.

	⚠️ Un compagnon PERMANENT ne prend RIEN, et la sortie est immédiate : passer par le
	calcul ordinaire ferait remonter sa part au plancher PART_BUTIN_MIN. Ce chokepoint est
	traversé par `regler_part_butin` — il n'y a donc rien d'autre à brancher."""
	exigences = av.get("exigences", {}) or {}
	if (av or {}).get("permanent"):
		return {"part_butin_pct": 0, "clauses": list(exigences.get("clauses", []) or [])}
	part = int(exigences.get("part_butin_pct", character_stats.RECRUTEMENT_PART_BUTIN_MIN) or 0)
	reduc = max(0, int(affinite) - 50) // max(1, int(character_stats.AFFINITE_REDUC_PART))
	part = max(int(character_stats.RECRUTEMENT_PART_BUTIN_MIN), part - reduc)
	return {"part_butin_pct": part, "clauses": list(exigences.get("clauses", []) or [])}


def places_occupees(character: dict, get_doc_fn=None) -> int:
	"""Places du groupe RÉELLEMENT prises = compagnons actifs NON PERMANENTS.

	Un compagnon engagé durablement sort du plafond : il n'occupe plus une place de
	contrat, il fait partie de la compagnie. ⚠️ Compter sur les DOCS (et non sur
	`len(character["groupe"])`) est ce qui rend le plafond juste — le flag `permanent` vit
	sur le doc du compagnon, comme `statut`. Le client recopie ce nombre : la liste et le
	garde doivent bouger ENSEMBLE."""
	return sum(1 for av in groupe_effectif(character, get_doc_fn) if not av.get("permanent"))


def peut_embaucher(character: dict, av: dict, get_doc_fn=None) -> tuple[bool, str]:
	"""(ok, raison) : la recrue doit être offerte, et le groupe sous le plafond — plafond
	qui ne compte QUE les compagnons non permanents (cf. `places_occupees`).

	`get_doc_fn=None` retombe sur le `get_doc` du module (précédent exact :
	`montures.peut_acquerir`), ce qui laisse les appelants existants inchangés."""
	if (av or {}).get("statut") != "offert":
		return False, "Cette recrue n'est plus disponible."
	if places_occupees(character, get_doc_fn) >= taille_max_groupe():
		return False, "Votre groupe est au complet."
	return True, ""


def embaucher(character: dict, av: dict, get_doc_fn=None) -> tuple[bool, str]:
	"""Embauche (gratuite) : statuts + groupe + mémoire du lien. Mute les DEUX docs en
	place, NE SAUVEGARDE PAS (l'endpoint persiste : character puis av, best-effort)."""
	ok, raison = peut_embaucher(character, av, get_doc_fn)
	if not ok:
		return False, raison
	# ⚠️ Filet : un ancien permanent congédié puis ré-embauché repart sur un contrat
	# ORDINAIRE. Sans ce pop, le flag survivrait à la rupture du lien et l'engagement
	# (part nulle + hors plafond) se retrouverait gratuit à la deuxième signature.
	av.pop("permanent", None)
	av["statut"] = "embauche"
	av["embauche_par"] = character.get("_id")
	av["embauche_at"] = now_epoch()
	av.pop("expire_at", None)
	groupe = character.get("groupe", []) or []
	if av["_id"] not in groupe:
		groupe.append(av["_id"])
	character["groupe"] = groupe
	character.setdefault("affinites", {}).setdefault(av["_id"], int(character_stats.AFFINITE_INITIALE))
	memo_compagnon(character, av)
	return True, ""


def congedier(character: dict, av: dict) -> tuple[bool, str]:
	"""Congédie un compagnon actif : retiré du groupe, statut `parti` (doc CONSERVÉ —
	il porte la mémoire du lien et peut être ré-offert). Le renvoi froisse
	(AFFINITE_DELTA_CONGEDIE), davantage en pleine quête (…_EN_QUETE). Mute sans save.

	⚠️ Rompre un engagement DURABLE coûte AFFINITE_DELTA_CONGEDIE_PERMANENT, et les deltas
	NE SE CUMULENT PAS : un seul s'applique, priorité au permanent (renvoyer un compagnon
	engagé blesse davantage que d'interrompre un contrat, quête en cours ou non). Le flag
	`permanent` est retiré — le lien est rompu, la compagnie ne l'est pas
	(`character["compagnie"]` survit, cf. `engager_permanent`)."""
	groupe = character.get("groupe", []) or []
	if not av or av.get("_id") not in groupe:
		return False, "Ce compagnon ne fait pas partie de votre groupe."
	groupe.remove(av["_id"])
	character["groupe"] = groupe
	av["statut"] = "parti"
	if av.pop("permanent", None):
		delta = character_stats.AFFINITE_DELTA_CONGEDIE_PERMANENT
	else:
		delta = (character_stats.AFFINITE_DELTA_CONGEDIE_EN_QUETE
				 if character.get("quetes_actives") else character_stats.AFFINITE_DELTA_CONGEDIE)
	ajuster_affinite(character, av["_id"], delta)
	return True, ""


# ── Engagement durable (compagnie) ───────────────────────────────────────────────
# Au-delà d'AFFINITE_SEUIL_ENGAGEMENT (palier « Dévoué »), le compagnon cesse d'être un
# contrat : il renonce à sa part de butin (`conditions_effectives`), sort du plafond de
# groupe (`places_occupees`) et rejoint la COMPAGNIE du joueur, qu'il baptise au premier
# engagement. Le flag vit sur le doc du compagnon (comme `statut`), la compagnie sur celui
# du joueur — c'est une identité, elle survit au départ de tous ses membres.

def nettoyer_nom_compagnie(brut) -> str:
	"""Nom de compagnie assaini : caractères de contrôle retirés, blancs écrasés, borné à
	40 signes. Renvoie "" si rien d'affichable ne reste (l'endpoint en fait un 422).

	⚠️ On BORNE au serveur, on ÉCHAPPE au rendu : pas d'échappement HTML ici, sinon le nom
	serait doublement échappé à l'affichage (le client passe par escapeHtml avant de
	l'interpoler dans son innerHTML). `<`, `&` et `'` traversent donc intacts."""
	texte = "" if brut is None else str(brut)
	texte = "".join(" " if c in "\t\n\r\f\v" else c
					for c in texte if c.isprintable() or c in "\t\n\r\f\v")
	return " ".join(texte.split())[:40]


def peut_engager(character: dict, av: dict) -> tuple[bool, str]:
	"""(ok, raison) : compagnon actif, pas déjà permanent, confiance au seuil."""
	if (av or {}).get("permanent"):
		return False, "Ce compagnon est déjà engagé durablement."
	if not av or av.get("_id") not in (character.get("groupe", []) or []):
		return False, "Ce compagnon ne fait pas partie de votre groupe."
	if affinite_de(character, av["_id"]) < int(character_stats.AFFINITE_SEUIL_ENGAGEMENT):
		return False, "Ce compagnon ne vous est pas assez dévoué."
	return True, ""


def engager_permanent(character: dict, av: dict, nom_compagnie=None) -> tuple[bool, str]:
	"""Engage durablement un compagnon. Mute les DEUX docs, NE SAUVEGARDE PAS.

	La compagnie n'est BAPTISÉE qu'au premier engagement : `nom_compagnie` est ignoré si
	elle existe déjà (les suivants la REJOIGNENT — le renommage a son propre endpoint).
	Un nom est donc exigé par l'appelant seulement quand `character["compagnie"]` manque."""
	ok, raison = peut_engager(character, av)
	if not ok:
		return False, raison
	if not character.get("compagnie"):
		nom = nettoyer_nom_compagnie(nom_compagnie)
		if not nom:
			return False, "Donnez un nom à votre compagnie."
		character["compagnie"] = {"nom": nom, "fondee_at": now_epoch()}
	av["permanent"] = True
	return True, ""


def renommer_compagnie(character: dict, nom) -> tuple[bool, str]:
	"""Renomme une compagnie EXISTANTE (on ne fonde pas une compagnie sans membre)."""
	if not character.get("compagnie"):
		return False, "Vous n'avez pas de compagnie."
	nom = nettoyer_nom_compagnie(nom)
	if not nom:
		return False, "Donnez un nom à votre compagnie."
	character["compagnie"]["nom"] = nom
	return True, ""


def departs_volontaires(character: dict, get_doc_fn=None) -> list:
	"""Check PARESSEUX (board / /play) : tout compagnon actif dont l'affinité est
	tombée sous AFFINITE_SEUIL_DEPART quitte le groupe de lui-même (statut `parti`).
	Mute character + docs ; renvoie les docs partis (l'appelant les persiste + toast).

	⚠️ Un compagnon PERMANENT ne part JAMAIS de lui-même : l'engagement l'emporte sur
	l'humeur, et seul le joueur peut rompre (`congedier`). Sans cette exception, le flag
	quitterait le groupe avec lui et un ré-engagement serait gratuit."""
	seuil = int(character_stats.AFFINITE_SEUIL_DEPART)
	partis = []
	for av in groupe_effectif(character, get_doc_fn):
		if av.get("permanent"):
			continue
		if affinite_de(character, av["_id"]) < seuil:
			character["groupe"].remove(av["_id"])
			av["statut"] = "parti"
			partis.append(av)
	return partis


def memo_compagnon(character: dict, av: dict) -> None:
	"""Mémorise la carte d'identité du compagnon dans `compagnons_connus` (borné ~30,
	pattern combats_recompenses) — alimente l'onglet 👥 même quand le doc a disparu."""
	connus = character.get("compagnons_connus", {}) or {}
	connus[av["_id"]] = {
		"prenom": av.get("prenom", ""), "nom": av.get("nom", ""),
		"voc": av.get("voc", ""), "race": av.get("race", ""),
		"image": av.get("image", ""), "rang": av.get("rang", "F"),
	}
	if len(connus) > 30:
		# Écarte les plus anciens non actifs (ordre d'insertion des dicts Python).
		actifs = set(character.get("groupe", []) or [])
		for k in list(connus):
			if len(connus) <= 30:
				break
			if k not in actifs:
				del connus[k]
	character["compagnons_connus"] = connus


# ── Affinités ────────────────────────────────────────────────────────────────────

def ajuster_affinite(character: dict, av_id: str, delta: int) -> int:
	"""Ajuste l'affinité mémorisée (clamp 0-100, création au neutre si inconnue).
	Mute en place ; renvoie la nouvelle valeur."""
	affinites = character.setdefault("affinites", {})
	val = int(affinites.get(av_id, character_stats.AFFINITE_INITIALE) or 0)
	val = max(0, min(100, val + int(delta)))
	affinites[av_id] = val
	return val


def memoriser_liens_post_quete(character: dict, groupe_docs: list) -> None:
	"""Une quête réussie ENSEMBLE resserre les liens : +AFFINITE_DELTA_QUETE avec
	chaque compagnon du groupe. Mute le character seul (l'affinité vit chez lui)."""
	for av in groupe_docs:
		ajuster_affinite(character, av["_id"], character_stats.AFFINITE_DELTA_QUETE)


def affinites_detail_payload(character: dict, get_doc_fn=None) -> list:
	"""Payload de l'onglet 👥 : tous les compagnons CONNUS (mémo), l'affinité (échelle
	0-100, neutre 50 — même échelle que les relations de lieu), et leur état courant
	(actif dans le groupe / parti). Trié affinité décroissante, actifs d'abord."""
	lire = get_doc_fn or get_doc
	actifs = set(character.get("groupe", []) or [])
	out = []
	for av_id, memo in (character.get("compagnons_connus", {}) or {}).items():
		av = lire(av_id)
		entry = {
			"id": av_id,
			"prenom": (av or memo).get("prenom", ""),
			"nom": (av or memo).get("nom", ""),
			"voc": (av or memo).get("voc", ""),
			"race": (av or memo).get("race", ""),
			"image": (av or memo).get("image", ""),
			"rang": (av or memo).get("rang", "F"),
			"affinite": affinite_de(character, av_id),
			"actif": av_id in actifs,
		}
		if av and av_id in actifs:
			entry["exigences_effectives"] = conditions_effectives(av, entry["affinite"])
			# L'onglet 👥 offre le congédiement : il doit savoir s'il rompt un ENGAGEMENT
			# (confirmation et sanction différentes) — sans quoi la même croix ✕ ferait deux
			# choses très différentes sous le même libellé.
			entry["permanent"] = bool(av.get("permanent"))
			entry.update(vitaux_de(av))
		out.append(entry)
	out.sort(key=lambda e: (not e["actif"], -e["affinite"]))
	return out


# ── Règlement de la part de butin ────────────────────────────────────────────────

def regler_part_butin(character: dict, groupe_docs: list, cuivre_total: int) -> dict:
	"""Chokepoint UNIQUE du règlement des compagnons (la phase 2 « salaires » s'y
	branchera) : prélève sur `cuivre_total` la part EFFECTIVE de chaque compagnon
	(affinité déduite), créditée à SON doc ; le reste revient au joueur (non crédité
	ici — l'appelant le fait, il tient déjà la logique de récompense).

	Arrondi au SOL par part (le doute profite au payeur) ; renvoie
	{parts: {av_id: cuivre}, reste}. Mute les docs compagnons (bourse), pas le character."""
	total = max(0, int(cuivre_total or 0))
	parts: dict = {}
	reste = total
	for av in groupe_docs:
		part_pct = conditions_effectives(av, affinite_de(character, av["_id"]))["part_butin_pct"]
		montant = min(reste, total * max(0, part_pct) // 100)
		if montant > 0:
			credit_character(av, montant)
			reste -= montant
		parts[av["_id"]] = montant
	return {"parts": parts, "reste": reste}
