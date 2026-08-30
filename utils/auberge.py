# utils/auberge.py
# Tavernes : ce qu'on FAIT dans une auberge — s'asseoir à une table et s'y parler, épingler
# une annonce au tableau d'information, et passer la nuit.
#
# ⚠️ C'est le PREMIER canal entre JOUEURS du jeu (les docs `character:*` sont cloisonnés par
# la garde d'appartenance de `get_selected_character`). Tout ce qui vient d'un joueur est donc
# BORNÉ ici et ÉCHAPPÉ au rendu — Convention §9. ⚠️ `nettoyer_ligne`/`nettoyer_texte`
# n'échappent RIEN : échapper au serveur ET au client produirait un double échappement.
#
# ⚠️ AUCUNE horloge, AUCUN temps partagé : « passer la nuit » est un geste LOCAL au
# personnage, sans le moindre lien avec `waitTurn()`. Les messages périment PARESSEUSEMENT
# sur l'epoch réel, comme les offres de quêtes — aucun tick de fond, ici pas plus qu'ailleurs.
#
# Logique pure : accès base injectés (`find_docs_fn`/`get_doc_fn`/`delete_doc_fn`), on MUTE
# sans sauver — l'appelant persiste. World-vars lues VIA le module `character_stats`, jamais
# en `from … import` (la valeur serait figée à l'import, le réglage à chaud sans effet).

import time
import uuid

from models import character_stats
from models.character_stats import BaseStats, compute_derived_stats
from utils.characters import sync_equipment_bonus, item_ref_id, item_sous_categorie
from utils.consommables import caracts_avec_buffs
from utils import expedition

TYPE_TABLE = "table"
TYPE_MESSAGE = "message"

SUPPORT_TABLE = "table"
SUPPORT_TABLEAU = "tableau"

# Sous-catégories exigées pour épingler une annonce, et celles qui se DÉPENSENT. La
# distinction est déjà dans la donnée et on ne fait que la suivre : `item:Papier` et
# `item:Encre` sont des `composant` — ils partent avec l'avis —, `item:Plume_d_oie` est un
# `outil`, il sert et ressert. Écrire coûte donc quelque chose à chaque fois, et le
# scriptorium (qui produit le papier et approvisionne l'encre) y gagne un débouché.
# ⚠️ `FOURNITURES_CONSOMMEES` doit rester un SOUS-ENSEMBLE de `FOURNITURES_ANNONCE` : on ne
# dépense que ce qu'on a d'abord exigé.
FOURNITURES_ANNONCE = ("papier", "encre", "plume_a_ecrire")
FOURNITURES_CONSOMMEES = ("papier", "encre")

# Nombre de lignes du log de la nuit. Assez pour couvrir l'attente des dizaines d'étals,
# assez peu pour ne pas lasser à la troisième nuit. ⚠️ Ici et non dans le router : `/play`
# sert le même log au bouton de la sidebar, les deux doivent tirer le même nombre de lignes.
NUIT_LOG_LIGNES = 7

# Repli du log de la nuit. ⚠️ Le champ `nuit_messages` du doc `lieu:*` PRIME (cf.
# `messages_nuit`) : le défaut de code rend la mécanique jouable sans aucun import, la donnée
# donne ensuite sa couleur à chaque auberge.
MESSAGES_NUIT = [
	"On pousse les bancs contre le mur ; la salle se vide par petits groupes.",
	"Le feu tombe en braises et personne ne le relance.",
	"Quelqu'un chante faux dans l'escalier, puis se tait.",
	"La paillasse sent le foin sec et la fumée froide.",
	"Dehors, une charrette passe sur les pavés et s'éloigne.",
	"Un convive ronfle derrière la cloison.",
	"Les volets battent une fois, deux fois, et se calment.",
	"Le tenancier compte sa recette à voix basse.",
	"On tire l'eau du puits dans la cour ; le seau cogne la margelle.",
	"Les premiers chariots des étals roulent vers la place, avant l'aube.",
	"Une odeur de pain chaud monte des cuisines.",
	"Le jour se lève gris sur les toits ; la nuit vous a lavé les jambes.",
	"Le dernier client éteint sa chandelle et monte l'escalier.",
	"Une chaise grince dans la salle commune, puis tout redevient silencieux.",
	"Le bois humide crépite faiblement dans l'âtre.",
	"Une porte se ferme doucement à l'autre bout du couloir.",
	"On entend les pas lourds du tenancier vérifier les chambres.",
	"Une odeur de bière renversée flotte encore près du comptoir.",
	"Quelqu'un tousse derrière une cloison avant de retomber dans le sommeil.",
	"Le vent siffle sous la porte et fait trembler la flamme de votre bougie.",
	"Un cheval tape du sabot dans l'écurie située sous la fenêtre.",
	"Les chaînes d'une armure suspendue tintent lorsque quelqu'un passe dans le couloir.",
	"Un rat détale sous les planches avant de disparaître dans l'ombre.",
	"Le plancher craque régulièrement sous les pas du tenancier qui fait sa ronde.",
	"Dans la chambre voisine, on chuchote encore avant que les voix ne s'éteignent.",
	"Une odeur de soupe refroidie flotte dans l'escalier.",
	"Quelqu'un descend chercher de l'eau, puis remonte en faisant grincer les marches.",
	"Une bûche s'effondre dans l'âtre avec un bref nuage d'étincelles.",
	"Les chevaux soufflent doucement dans l'écurie tandis que la nuit avance.",
	"Un volet mal fermé claque contre son battant avant d'être finalement attaché.",
	"Au loin, une cloche sonne l'heure et réveille brièvement les dormeurs.",
	"Le ronflement d'un voyageur traverse les murs trop fins de l'auberge.",
	"Une goutte tombe régulièrement d'une gouttière sur la pierre de la cour.",
	"Le tenancier range les dernières chopes avant de monter se coucher.",
	"Une faible lumière filtre sous la porte de la cuisine, puis disparaît.",
	"Les premières voix du matin montent de la rue tandis que l'auberge s'éveille.",
]


def now_epoch() -> int:
	"""Epoch entier — miroir de `montures.now_epoch`. Local et non emprunté à `utils.quetes`
	(sa `now_epoch` est la source unique du jeu) : ce module doit rester léger, et importer
	`quetes` tirerait bois + expedition + recrutement + marche derrière lui."""
	return int(time.time())


def lieu_est_taverne(lieu_doc: dict) -> bool:
	"""Une taverne = `categorie: "auberge"` OU tag `"taverne"`. Miroir exact de
	`montures.lieu_vend_montures` : le OU évite toute migration et permet d'ouvrir la salle
	commune à un autre lieu (une salle de guilde, une halte) sans une ligne de code."""
	if not lieu_doc:
		return False
	return (lieu_doc.get("categorie") == "auberge"
			or "taverne" in (lieu_doc.get("tags") or []))


# ── Bornage des saisies joueur ──────────────────────────────────────────────────
# ⚠️ On BORNE, on n'ÉCHAPPE PAS (Convention §9). `<`, `&`, `'` traversent intacts ; c'est
# `escapeHtml` au rendu qui les neutralise. Calqués sur `recrutement.nettoyer_nom_compagnie`.

def nettoyer_ligne(brut, max_len: int) -> str:
	"""Borne une saisie d'UNE ligne : coercition `str`, retrait des non-imprimables (dont
	les zero-width), écrasement des blancs en espaces simples, troncature dure.
	Rend `""` s'il ne reste rien — à l'appelant d'en faire un 422."""
	texte = "" if brut is None else str(brut)
	texte = "".join(" " if c in "\t\n\r\f\v" else c
					for c in texte if c.isprintable() or c in "\t\n\r\f\v")
	return " ".join(texte.split())[:max(0, int(max_len or 0))]


def nettoyer_texte(brut, max_len: int, max_lignes: int = 20) -> str:
	"""Borne une saisie MULTI-LIGNE (une annonce de 800 signes en est une) en PRÉSERVANT les
	sauts de ligne — c'est toute la différence avec `nettoyer_ligne`, qui les écraserait.
	Chaque ligne est normalisée séparément, les lignes vides consécutives sont réduites à une
	seule, et le tout est borné en nombre de lignes PUIS en longueur totale."""
	texte = "" if brut is None else str(brut)
	texte = texte.replace("\r\n", "\n").replace("\r", "\n")
	lignes: list[str] = []
	for brute in texte.split("\n"):
		ligne = nettoyer_ligne(brute, max_len)
		if ligne:
			lignes.append(ligne)
		elif lignes and lignes[-1]:
			lignes.append("")          # une seule ligne vide de séparation, jamais deux
	while lignes and not lignes[-1]:
		lignes.pop()
	return "\n".join(lignes[:max(1, int(max_lignes or 1))])[:max(0, int(max_len or 0))]


def nom_affichable(character: dict) -> str:
	"""Le nom que le message portera aux yeux des AUTRES joueurs. ⚠️ Dénormalisé à
	l'écriture, et ce n'est pas une commodité : relire le `character:*` de l'auteur au rendu
	serait N lectures par sondage ET buterait sur la garde d'appartenance (on n'a pas le
	droit de lire le personnage d'un autre joueur). Re-borné ici par ceinture — le champ est
	déjà borné à la création du personnage."""
	brut = f"{(character or {}).get('prenom', '')} {(character or {}).get('nom', '')}"
	return nettoyer_ligne(brut, 61) or "Un inconnu"


def portrait_de(character: dict) -> dict:
	"""Le portrait que le message portera — miroir de `nom_affichable`, et dénormalisé pour
	les MÊMES deux raisons : relire le `character:*` de l'auteur à chaque sondage serait N
	lectures d'un type EXCLU du cache de requête, et on n'a pas le droit de lire le
	personnage d'un autre joueur.

	Le cadrage voyage avec (`portrait_zoom`, `portrait_translate`) : un avatar de chat doit
	montrer le cadrage que le joueur s'est choisi, pas sa silhouette entière. ⚠️ Côté client,
	cela n'a d'effet que parce que la carte passe `cadre: true` — une carte en lecture seule
	jette le cadrage par défaut (cf. `makePortraitViewport.setSujet`).

	⚠️ Clés ABSENTES quand le personnage n'a pas de portrait : `nouveau_message` ne les pose
	alors pas, et le client retombe sur la silhouette générique. Aucune migration — les
	messages déjà en base restent lisibles."""
	image = (character or {}).get("image") or ""
	if not image:
		return {}
	out = {"auteur_image": image}
	zoom = (character or {}).get("portrait_zoom")
	if zoom is not None:
		out["auteur_zoom"] = zoom
	translate = (character or {}).get("portrait_translate")
	# ⚠️ `portrait_translate` est un DICT {x, y} (cf. update_character_portrait), pas la
	# chaîne CSS : c'est `defaultOffset` qui en dérive l'offset, en valeur absolue.
	if isinstance(translate, dict):
		out["auteur_translate"] = {"x": translate.get("x", 0), "y": translate.get("y", 0)}
	return out


# ── Lecture de la salle ─────────────────────────────────────────────────────────
# ⚠️ `find_docs` renvoie None sur exception (db/config.py) : toujours `or []`. Il n'expose ni
# `sort` ni `skip` — le tri se fait ici, en Python.

def tables_du_lieu(lieu_id: str, find_docs_fn) -> list:
	"""Tables d'une auberge, par numéro croissant. Servi par l'index `["type","lieu"]`."""
	docs = find_docs_fn({"type": TYPE_TABLE, "lieu": lieu_id}) or []
	return sorted(docs, key=lambda t: int(t.get("numero", 0) or 0))


def messages_du_lieu(lieu_id: str, find_docs_fn) -> list:
	"""TOUS les messages d'une auberge — table ET tableau — du plus ancien au plus récent.
	Une seule requête pour les deux supports : l'index porte sur `(type, lieu)`, pas sur le
	support, et le panneau a de toute façon besoin des deux à chaque sondage."""
	docs = find_docs_fn({"type": TYPE_MESSAGE, "lieu": lieu_id}) or []
	return sorted(docs, key=lambda m: int(m.get("cree_at", 0) or 0))


def de_support(messages: list, support: str, table_id: str | None = None) -> list:
	"""Filtre par support, et par table quand elle est précisée."""
	out = [m for m in messages or [] if m.get("support") == support]
	if table_id is not None:
		out = [m for m in out if m.get("table") == table_id]
	return out


# ── Péremption PARESSEUSE ───────────────────────────────────────────────────────

def message_perime(message: dict, now: int) -> bool:
	"""Un message de TABLE meurt au bout d'`AUBERGE_MESSAGE_DUREE_SECONDES`. ⚠️ Une annonce
	du TABLEAU n'expire JAMAIS : elle ne part qu'à la main. C'est ce qui distingue le
	tableau, durable, des tables, éphémères. Repli sans `expire_at` : `cree_at` + durée."""
	if (message or {}).get("support") != SUPPORT_TABLE:
		return False
	echeance = message.get("expire_at")
	if echeance is None:
		echeance = (int(message.get("cree_at", 0) or 0)
					+ int(character_stats.AUBERGE_MESSAGE_DUREE_SECONDES))
	return int(now) >= int(echeance)


def purger_messages_perimes(messages: list, now: int, delete_doc_fn=None) -> list:
	"""Retire les messages échus et renvoie ceux qui restent. Calqué sur
	`quetes.purger_offres_perimees` : le doc est SUPPRIMÉ, personne ne le référence."""
	restants = []
	for m in messages or []:
		if message_perime(m, now):
			if delete_doc_fn:
				delete_doc_fn(m)
		else:
			restants.append(m)
	return restants


def messages_en_trop(messages: list, maximum: int | None = None) -> list:
	"""Les messages d'une table AU-DELÀ du plafond, les plus ANCIENS d'abord — ce sont eux
	qui sautent. `messages` est supposé trié par `cree_at` (cf. `messages_du_lieu`)."""
	plafond = int(character_stats.AUBERGE_TABLE_MESSAGES_MAX if maximum is None else maximum)
	surplus = len(messages or []) - max(0, plafond)
	return list(messages or [])[:surplus] if surplus > 0 else []


# ── Tables ──────────────────────────────────────────────────────────────────────

def table_du_personnage(tables: list, character_id: str) -> dict | None:
	"""La table où ce personnage est assis, ou None. Un personnage n'occupe QU'UNE table à la
	fois : c'est `asseoir` qui tient l'invariante."""
	return next((t for t in tables or []
				 if character_id in (t.get("participants") or [])), None)


def table_fermee_pour(table: dict, character_id: str) -> bool:
	"""True si ce personnage a DORMI depuis qu'il s'est assis là : la nuit l'a versé dans
	`anciens`, la table ne lui est plus accessible. Les autres convives, eux, la voient
	toujours — la soirée ne s'achève que pour celui qui est monté se coucher."""
	return character_id in ((table or {}).get("anciens") or [])


def nouvelle_table(lieu_id: str, tables: list, now: int | None = None) -> dict | None:
	"""Ouvre une table. `numero` = 1 + le plus grand présent (jamais un trou réutilisé : deux
	tables successives ne doivent pas porter le même nom dans la mémoire des joueurs).
	None si la salle est pleine — `AUBERGE_TABLES_MAX`."""
	if len(tables or []) >= int(character_stats.AUBERGE_TABLES_MAX):
		return None
	instant = now_epoch() if now is None else int(now)
	numero = 1 + max([int(t.get("numero", 0) or 0) for t in tables or []] or [0])
	return {
		"_id": f"{TYPE_TABLE}:{uuid.uuid4().hex[:12]}",
		"type": TYPE_TABLE,
		"lieu": lieu_id,
		"numero": numero,
		"participants": [],
		"anciens": [],
		"noms": {},
		"cree_at": instant,
		"activite_at": instant,
	}


def asseoir(table: dict, character: dict, now: int | None = None) -> tuple[bool, str]:
	"""Assoit un personnage à `table`. Mute sans sauver ; renvoie `(ok, raison)`.

	⚠️ Ne lève PLUS de la table précédente — c'est `quitter_tables` qui s'en charge, parce
	que partir emporte désormais les messages : les deux gestes ne peuvent plus être le même.

	Pose `character["taverne_table"]` : c'est le marqueur qui permettra de le relever quand il
	sortira de l'auberge, sans coûter un `find_docs` à chaque pas de chaque joueur.

	Pose aussi son nom dans `noms` : c'est ce qui permettra aux AUTRES convives de lire qui est
	attablé. ⚠️ Dénormalisé pour les mêmes deux raisons qu'`auteur_nom` sur un message — relire
	le `character:*` de chaque participant à chaque sondage serait N lectures d'un type exclu du
	cache de requête, ET on n'a pas le droit de lire le personnage d'un autre joueur."""
	character_id = (character or {}).get("_id", "")
	if not table:
		return False, "Cette table n'existe plus."
	if table_fermee_pour(table, character_id):
		return False, "Vous avez quitté cette table au petit matin ; elle ne vous est plus ouverte."
	participants = list(table.get("participants") or [])
	if character_id not in participants:
		participants.append(character_id)
	table["participants"] = participants
	noms = dict(table.get("noms") or {})
	noms[character_id] = nom_affichable(character)
	table["noms"] = noms
	table["activite_at"] = now_epoch() if now is None else int(now)
	character["taverne_table"] = table.get("_id", "")
	return True, ""


def quitter_tables(character: dict, tables: list, messages: list,
				   sauf: str | None = None, definitif: bool = False) -> tuple[list, list]:
	"""Lève le personnage des tables où il est assis — `(tables_modifiees, messages_a_supprimer)`.

	⚠️ **SES MESSAGES MEURENT AVEC SA PRÉSENCE** : une conversation appartient à ceux qui sont
	attablés, et laisser ses propos derrière soi les ferait lire à des convives à qui l'on ne
	peut plus répondre.

	`sauf` épargne une table (celle où l'on vient s'asseoir : sans quoi se rasseoir chez soi
	effacerait ce qu'on vient d'y dire). `definitif` (la nuit) verse en plus dans `anciens` :
	la table ne sera plus jamais montrée à ce personnage.

	Mute sans sauver — l'appelant persiste et supprime."""
	character_id = (character or {}).get("_id", "")
	modifiees, a_supprimer = [], []
	for table in tables or []:
		tid = table.get("_id")
		if sauf is not None and tid == sauf:
			continue
		if character_id not in (table.get("participants") or []):
			continue
		table["participants"] = [p for p in (table.get("participants") or [])
								 if p != character_id]
		# Le nom part avec la présence : plus personne ne doit lire dans la tête de cette
		# table quelqu'un qui n'y est plus. ⚠️ Il ne suit PAS dans `anciens`, qui ne sert qu'au
		# filtrage de visibilité et n'affiche rien.
		noms = dict(table.get("noms") or {})
		if noms.pop(character_id, None) is not None:
			table["noms"] = noms
		if definitif:
			anciens = list(table.get("anciens") or [])
			if character_id not in anciens:
				anciens.append(character_id)
			table["anciens"] = anciens
		modifiees.append(table)
		a_supprimer += [m for m in messages or []
						if m.get("support") == SUPPORT_TABLE and m.get("table") == tid
						and m.get("auteur") == character_id]
		if (character or {}).get("taverne_table") == tid:
			character.pop("taverne_table", None)
	return modifiees, a_supprimer


def table_vide(table: dict) -> bool:
	"""Une table où PERSONNE n'est assis n'existe plus : elle est supprimée, avec tout ce
	qu'elle porte encore.

	⚠️ Ce n'est plus « ni participant NI message » : des propos flottant dans une salle
	déserte n'ont aucun sens, et l'ancien critère faisait survivre indéfiniment une table que
	tout le monde avait quittée. C'est aussi ce qui fait disparaître `anciens` avec elle —
	la liste ne grossit jamais sans borne."""
	return not ((table or {}).get("participants") or [])


def noms_attables(table: dict) -> list:
	"""Les noms des personnes ASSISES à cette table, dans leur ordre d'arrivée — source unique
	de ce que la salle lit dans la tête d'une table.

	⚠️ L'ordre vient de `participants` et jamais des clés de `noms` : c'est `participants` qui
	porte l'ordre d'arrivée, le dict n'est qu'un répertoire.

	⚠️ Un participant dont le nom n'est pas connu est **OMIS** (table déjà en base, assise avant
	que le champ n'existe) : aucune migration, et c'est cette liste plus courte que le nombre
	d'occupants qui fait retomber le client sur son ancien « N attablé(s) »."""
	noms = (table or {}).get("noms") or {}
	sortie = []
	for pid in (table or {}).get("participants") or []:
		nom = noms.get(pid)
		if nom:
			sortie.append(nom)
	return sortie


def rafraichir_mon_nom(tables: list, character: dict) -> list:
	"""Répare À LA LECTURE le nom du personnage COURANT sur les tables où il est assis —
	rend les tables modifiées, mute sans sauver.

	⚠️ Sans cette réparation, `asseoir` n'écrit le nom que de CELUI QUI S'ASSIED : quelqu'un
	déjà attablé avant que le champ n'existe n'aurait **jamais** été rattrapé, et sa table
	serait restée à moitié muette jusqu'à ce qu'il se relève. C'est le même remède qu'ailleurs
	dans le projet (`slots_effectifs` → `_reparer_obligatoires`) : aucune migration, on répare
	au moment où quelqu'un regarde.

	⚠️ On ne peut réparer QUE le sien : le nom d'autrui demanderait de lire son `character:*`,
	ce que la garde d'appartenance interdit. Chaque convive répare le sien en ouvrant la salle,
	donc une table héritée se recompose d'elle-même en une visite par personne.

	⚠️ Ne rend une table que si elle a VRAIMENT changé : appelée sur le chemin du sondage
	(toutes les 4 s), elle ne doit écrire qu'une fois."""
	character_id = (character or {}).get("_id", "")
	if not character_id:
		return []
	nom = nom_affichable(character)
	modifiees = []
	for table in tables or []:
		if character_id not in (table.get("participants") or []):
			continue
		if (table.get("noms") or {}).get(character_id) == nom:
			continue
		noms = dict(table.get("noms") or {})
		noms[character_id] = nom
		table["noms"] = noms
		modifiees.append(table)
	return modifiees


# ── Écriture ────────────────────────────────────────────────────────────────────

def nouveau_message(lieu_id: str, character: dict, texte: str,
					support: str = SUPPORT_TABLE, table_id: str | None = None,
					now: int | None = None) -> dict:
	"""Construit le doc message. `texte` est supposé DÉJÀ borné par l'appelant (c'est lui qui
	sait s'il s'agit d'une ligne de table ou d'une annonce multi-ligne, et qui doit lever le
	422 sur un texte vide)."""
	instant = now_epoch() if now is None else int(now)
	doc = {
		"_id": f"{TYPE_MESSAGE}:{uuid.uuid4().hex[:16]}",
		"type": TYPE_MESSAGE,
		"lieu": lieu_id,
		"support": support,
		"auteur": (character or {}).get("_id", ""),
		"auteur_nom": nom_affichable(character),
		**portrait_de(character),
		"texte": texte,
		"cree_at": instant,
	}
	if support == SUPPORT_TABLE:
		doc["table"] = table_id
		doc["expire_at"] = instant + int(character_stats.AUBERGE_MESSAGE_DUREE_SECONDES)
	return doc


def fournitures_presentes(get_doc_fn, porteurs: list) -> dict:
	"""Quelles fournitures d'écriture sont là — `{sous_categorie: bool}`. On rend le DÉTAIL et
	pas un simple booléen : le refus doit pouvoir dire ce qui manque, sinon le joueur ne sait
	pas quoi acheter."""
	return {sc: expedition.porteur_avec_sous_categorie(get_doc_fn, porteurs, sc)
			for sc in FOURNITURES_ANNONCE}


def fournitures_manquantes(get_doc_fn, porteurs: list) -> list:
	"""Les sous-catégories qui font défaut, dans l'ordre de `FOURNITURES_ANNONCE`."""
	presentes = fournitures_presentes(get_doc_fn, porteurs)
	return [sc for sc in FOURNITURES_ANNONCE if not presentes.get(sc)]


def _emplacement_fourniture(get_doc_fn, porteur: dict, sous_categorie: str):
	"""Où se trouve le PREMIER exemplaire : `("inventaire", index)`, `("slots", nom)`, ou
	None. Même parcours et même prédicat que `expedition.porteur_avec_sous_categorie` —
	c'est délibéré : le contrôle et la dépense doivent voir exactement la même chose, sinon
	l'annonce serait acceptée puis rien ne serait retiré, et écrire redeviendrait gratuit."""
	besoin = str(sous_categorie or "").lower()
	if not besoin:
		return None
	def _est(ref):
		item_id = item_ref_id(ref)
		if not item_id:
			return False
		doc = get_doc_fn(item_id)
		return bool(doc) and str(item_sous_categorie(doc) or "").lower() == besoin
	for i, ref in enumerate((porteur or {}).get("inventaire", []) or []):
		if _est(ref):
			return ("inventaire", i)
	for nom, ref in ((porteur or {}).get("slots", {}) or {}).items():
		if ref and _est(ref):
			return ("slots", nom)
	return None


def retirer_fournitures(get_doc_fn, character: dict, sous_categories=None) -> tuple[bool, list]:
	"""Dépense UN exemplaire de chaque sous-catégorie — `(ok, retirees)`. Mute le personnage
	sans le sauver ; l'appelant persiste.

	⚠️ TOUT OU RIEN : on repère d'abord les emplacements, on ne retire qu'ensuite. Retirer au
	fil de l'eau amputerait le sac du papier avant de découvrir qu'il n'y a pas d'encre.

	⚠️ Les index d'inventaire SE DÉCALENT à chaque retrait : on supprime du plus grand au
	plus petit, sinon le second retrait ne porterait pas sur l'item repéré."""
	voulues = tuple(FOURNITURES_CONSOMMEES if sous_categories is None else sous_categories)
	emplacements = []
	for sc in voulues:
		place = _emplacement_fourniture(get_doc_fn, character, sc)
		if place is None:
			return False, []
		emplacements.append(place)

	inventaire = list(character.get("inventaire", []) or [])
	for i in sorted([c for src, c in emplacements if src == "inventaire"], reverse=True):
		inventaire.pop(i)
	character["inventaire"] = inventaire

	# Branche morte avec le contenu actuel (papier et encre ont `slots: []`, donc
	# `equip_item` les refuse) mais tenue par cohérence avec le contrôle, qui scanne les
	# slots : le jour où un encrier s'accrochera à la ceinture, la dépense suivra.
	if any(src == "slots" for src, _ in emplacements):
		slots = dict(character.get("slots", {}) or {})
		for src, cle in emplacements:
			if src == "slots":
				slots[cle] = None
		character["slots"] = slots
		sync_equipment_bonus(character)      # un slot vidé périme l'agrégat dénormalisé
	return True, list(voulues)


# ── La nuit ─────────────────────────────────────────────────────────────────────

def cout_nuit(lieu_doc: dict | None = None) -> int:
	"""Prix de la chambre. `AUBERGE_NUIT_COUT_CUIVRE` — 0 = gratuit, sans toucher au code."""
	return max(0, int(character_stats.AUBERGE_NUIT_COUT_CUIVRE))


def messages_nuit(lieu_doc: dict | None, nombre: int = 6, rand_fn=None) -> list:
	"""Le log de la nuit : `nombre` lignes tirées sans répétition. Le champ `nuit_messages` du
	doc lieu PRIME sur `MESSAGES_NUIT` — patron du projet (défaut de code, donnée qui
	l'emporte), pour qu'une auberge puisse raconter sa propre nuit."""
	source = [str(m) for m in ((lieu_doc or {}).get("nuit_messages") or []) if str(m).strip()]
	if not source:
		source = list(MESSAGES_NUIT)
	voulu = max(1, min(int(nombre or 1), len(source)))
	if rand_fn is None:
		import random
		rand_fn = random.sample
	retenus = set(rand_fn(source, voulu))
	# ⚠️ On restitue l'ORDRE de la liste d'origine : les lignes racontent une nuit qui avance,
	# de la salle qui se vide aux chariots d'avant l'aube. Les rendre dans l'ordre du tirage
	# casserait le récit — on tire QUOI montrer, pas DANS QUEL ORDRE.
	return [m for m in source if m in retenus]


def reposer(porteur: dict) -> dict:
	"""PV/PM au MAXIMUM. ⚠️ S'applique telle quelle à un `character:*`, un `aventurier:*` et
	un `monture:*` : les trois sont des miroirs du personnage (c'est déjà ce qui permet à
	`_apply_world_turn_regen` de les traiter ensemble).

	⚠️ `effets_actifs` n'est PAS touché : la nuit remet les points, elle ne dissipe pas les
	buffs. Rien à migrer, aucune surprise pour une potion bue avant de monter."""
	equipment = sync_equipment_bonus(porteur)
	stats = caracts_avec_buffs(porteur)
	base = BaseStats(
		v=stats.get("V", 0), f=stats.get("F", 0), r=stats.get("R", 0),
		ag=stats.get("Ag", 0), vol=stats.get("Vol", 0), int_=stats.get("Int", 0),
		cha=stats.get("Cha", 0), ch=stats.get("Ch", 0),
	)
	niveau = ((porteur or {}).get("vocations_niveaux") or {}).get((porteur or {}).get("voc", ""), 0)
	derived = compute_derived_stats(base, niveau=niveau, equipment=equipment)
	porteur["currentPV"] = derived.pv_max
	porteur["currentPM"] = derived.pm_max
	return {"currentPV": derived.pv_max, "pv_max": derived.pv_max,
			"currentPM": derived.pm_max, "pm_max": derived.pm_max}


def fermer_soiree(character: dict, tables: list, messages: list) -> tuple[list, list]:
	"""Fin de soirée d'UN personnage — le cas DÉFINITIF de `quitter_tables`.

	Ses messages de table s'effacent, il quitte les tables où il était assis, et il y est versé
	dans `anciens` : elles ne lui seront **plus jamais montrées**. ⚠️ Les autres convives ne
	perdent rien — la table vit sa vie, seule la soirée du dormeur s'achève. ⚠️ Les annonces
	du TABLEAU survivent : elles ne partent qu'à la main."""
	return quitter_tables(character, tables, messages, definitif=True)


def traiter_deplacement(character: dict, get_doc_fn, save_doc_fn,
						delete_doc_fn, find_docs_fn) -> bool:
	"""Le personnage a bougé : s'il était attablé dans une taverne qu'il vient de QUITTER, il
	se lève — ses messages partent avec lui, et la table s'efface si elle se vide. Renvoie
	True si quelque chose a changé.

	⚠️ Sans ce traitement, rien ne relèverait jamais quelqu'un qui sort simplement de
	l'auberge : les tables ne se videraient donc jamais, et ses propos resteraient affichés à
	des convives à qui il ne peut plus répondre.

    ⚠️ Repose sur le marqueur `character["taverne_table"]`, posé par `asseoir`. Champ absent
	⇒ **sortie immédiate, coût nul** — sans lui il faudrait un `find_docs` à chaque pas de
	chaque joueur pour une situation rare. Miroir de `escorte.traiter_deplacement`, appelé au
	même endroit et pour la même raison : aucun tick de fond n'existe dans le jeu."""
	table_id = (character or {}).get("taverne_table")
	if not table_id:
		return False
	table = get_doc_fn(table_id)
	if not table:
		character.pop("taverne_table", None)      # table déjà effacée : le marqueur ment
		return True
	if table.get("lieu") == character.get("lieu"):
		return False                              # toujours dans la même auberge : il y reste

	lieu_id = table.get("lieu", "")
	tables = tables_du_lieu(lieu_id, find_docs_fn)
	messages = messages_du_lieu(lieu_id, find_docs_fn)
	modifiees, a_supprimer = quitter_tables(character, tables, messages)
	for m in a_supprimer:
		delete_doc_fn(m)
	efface = {m.get("_id") for m in a_supprimer}
	messages = [m for m in messages if m.get("_id") not in efface]
	# ⚠️ Le test de vacuité se fait sur `messages` DÉJÀ amputé : une table qu'il occupait seul
	# doit partir avec tout ce qu'elle portait, pas survivre à ses propres messages morts.
	for t in modifiees:
		if table_vide(t):
			for m in de_support(messages, SUPPORT_TABLE, t.get("_id")):
				delete_doc_fn(m)
			delete_doc_fn(t)
		else:
			save_doc_fn(t)
	character.pop("taverne_table", None)
	return True
