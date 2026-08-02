# utils/animations.py
# Animations d'attaque en combat — feuilles de sprites jouées SUR LA CIBLE d'un coup.
#
# Trois contraintes dictent l'architecture, et il faut les avoir en tête avant de
# toucher à ce module :
#
#  1. **Le journal de combat ne porte aucun id** — une entrée est
#     `{tour, acteur (un NOM), kind, texte}`. Le client ne peut donc pas déduire qui a
#     été touché par quoi : c'est le SERVEUR qui pose la charge d'animation, sous la
#     clé `vfx` de l'entrée de journal (cf. `vfx()`).
#  2. **Les tours de monstres sont entièrement résolus côté serveur** avant la réponse
#     HTTP : le client ne les voit passer qu'à travers le journal. Il n'y a rien d'autre
#     à intercepter — le journal est le SEUL canal possible.
#  3. **Les feuilles sont hétérogènes** au point que l'auto-détection de grille est
#     impossible (bandes de 22 cases, planches carrées, « 512px-by197px-per-frame »,
#     49 cases pour 45 images…). `deviner_grille` ne fait que SEMER une hypothèse :
#     rien n'est jamais actif sans confirmation humaine à l'aperçu (cf. /admin/animations).
#
# Module PUR : aucune DB, aucun I/O (le scan de répertoire et la lecture des dimensions
# vivent dans `routers/animations.py`, qui importe Pillow PARESSEUSEMENT).
#
# ⚠️ Les défauts par canal se lisent VIA LE MODULE (`character_stats.COMBAT_ANIMATIONS_DEFAUT`)
# et jamais par `from … import` : la world-var est réglable à chaud, une valeur figée à
# l'import ne bougerait plus.

import re

from models import character_stats

# Sens de lecture des LIGNES dans la feuille. `haut_bas` (le DÉFAUT) = la première image
# est sur la ligne du HAUT, cas de la grande majorité des feuilles du commerce ; `bas_haut`
# lit la dernière ligne en premier. Se tromper joue l'animation à l'envers, sans message
# d'erreur — d'où un CHAMP et non une constante, whitelisté comme `cible` dans
# normaliser_sort. ⚠️ Source unique du défaut : le formulaire d'admin, le scan, la
# normalisation et le rendu de combat en dépendent tous.
SENS_LIGNES = ("haut_bas", "bas_haut")
SENS_DEFAUT = "haut_bas"

# Sens de lecture des COLONNES à l'intérieur d'une ligne, strict miroir horizontal du
# précédent : `gauche_droite` (le DÉFAUT) lit la première image à gauche, `droite_gauche`
# la lit à droite. Deux AXES SÉPARÉS et non un champ unique à quatre valeurs — une feuille
# peut avoir besoin des deux à la fois, et les combiner (`bas_haut` + `droite_gauche`)
# revient à jouer la planche entière à l'envers. ⚠️ Champ absent ⇒ `gauche_droite`, donc
# exactement le comportement d'avant : aucune migration.
SENS_COLONNES = ("gauche_droite", "droite_gauche")
SENS_COLONNES_DEFAUT = "gauche_droite"

# Sur qui le sprite est posé : la CIBLE du coup (défaut) ou l'acteur qui agit
# (consommable, buff sur soi). Avec une trajectoire, c'est le point d'ARRIVÉE.
ANCRAGES = ("cible", "acteur")
ANCRAGE_DEFAUT = "cible"

# Point de DÉPART d'une animation qui VOYAGE (flèche, boule de feu, caillou lancé).
# ⚠️ La chaîne VIDE est le défaut et vaut « aucune trajectoire » : le sprite est posé sur
# son ancrage d'arrivée, exactement comme avant. C'est ce qui rend tout ce dispositif sans
# migration — un doc qui ne porte pas le champ ne bouge pas d'un pixel.
DEPART_ANCRAGES = ("", "cible", "acteur")
DEPART_ANCRAGE_DEFAUT = ""

DUREE_DEFAUT_MS = 600
ECHELLE_DEFAUT = 1.5

# Décalage vertical de BASE, en cases, appliqué à TOUTES les animations. Un sprite calé sur
# le sol de sa case flotte au-dessus du personnage : la demi-case le ramène sur lui.
#
# ⚠️ C'est un décalage de RENDU, posé sur le PAYLOAD et jamais écrit dans un doc : le champ
# `decalage_y` d'un document reste exactement ce que l'auteur a saisi, et son zéro EST cette
# base. Aucune donnée à retoucher, aucune migration — un doc déjà réglé se décale d'une
# demi-case vers le bas, ce qui est précisément l'effet voulu.
DECALAGE_Y_BASE = -0.5

# Miroir horizontal du précédent, en cases. Base **0** : un sprite est déjà centré sur la
# case de son porteur, il n'y a rien à corriger par défaut — le champ ne sert qu'aux
# feuilles dont le dessin n'est pas centré dans sa frame. Même règle que pour Y : décalage
# de RENDU appliqué au payload, jamais écrit dans un doc, champ absent ⇒ 0.
DECALAGE_X_BASE = 0.0

# Orientation du sprite. `rotation` corrige le sens dans lequel la PLANCHE est dessinée —
# ⚠️ convention : **0° = le dessin pointe vers la DROITE de l'écran**, donc une flèche
# dessinée vers le haut se corrige par `rotation: 90`. `rotation_auto` y ajoute l'angle
# départ → arrivée (à défaut de trajectoire, l'angle acteur → cible : un impact peut vouloir
# se tourner vers celui qui frappe) ; si l'un des deux bouts manque, l'angle vaut 0.
ROTATION_DEFAUT = 0.0

EXTENSIONS_IMAGE = (".png", ".jpg", ".jpeg", ".webp")
# Sons servis par le mount `/sounds` (`templates/resources/sounds`). Une animation peut
# n'être QU'un son : c'est ainsi que se traitent les canaux qui n'ont rien à montrer
# (`miss`, `fumble`) — un coup qui rate ne mérite pas un sprite, mais mérite un bruit.
EXTENSIONS_SON = (".mp3", ".ogg", ".wav", ".m4a")
VOLUME_DEFAUT = 1.0

# Clés publiées au client (catalogue de `/combat/{id}` et aperçu de l'éditeur) : tout ce
# qu'il faut pour découper et jouer la feuille, rien de plus.
CLES_PAYLOAD = (
	"fichier", "largeur", "hauteur", "colonnes", "lignes", "sens_lignes", "sens_colonnes",
	"debut", "fin", "duree_ms", "echelle", "decalage_x", "decalage_y", "ancrage",
	# Trajectoire + orientation. Champs absents ⇒ sprite posé, droit : le comportement
	# d'avant, sans migration.
	"depart_ancrage", "depart_decalage_x", "depart_decalage_y",
	"duree_trajet_ms", "arc", "rotation", "rotation_auto",
	# Son. Champ absent ⇒ animation muette, comme avant.
	"son", "son_debut_ms", "son_fin_ms", "son_volume",
)


def _as_int(valeur, defaut: int = 0) -> int:
	try:
		return int(valeur)
	except (TypeError, ValueError):
		return defaut


def _as_float(valeur, defaut: float = 0.0) -> float:
	try:
		return float(valeur)
	except (TypeError, ValueError):
		return defaut


# ── Catalogue ────────────────────────────────────────────────────────────────────

def normaliser_animation(doc) -> dict | None:
	"""Vue normalisée d'un doc `animation:*`, ou None si ce n'en est pas un.

	Borne tout ce qui pourrait faire diverger le rendu : `colonnes`/`lignes` ≥ 1,
	`debut ≤ fin < colonnes×lignes`, `duree_ms` > 0, `echelle` > 0. `sens_lignes`,
	`sens_colonnes`, `ancrage` et `depart_ancrage` sont WHITELISTÉS (miroir de
	`normaliser_sort`) — une faute de frappe retombe sur le défaut au lieu de créer un
	troisième comportement silencieux. ⚠️ Pour `depart_ancrage`, ce défaut est la chaîne
	vide, donc « pas de trajectoire » : une valeur illisible ne peut pas faire VOLER un
	sprite qui devait rester posé.

	⚠️ **Ni image NI son ⇒ rien à jouer** : c'est la seule condition de rejet. Une animation
	peut n'être qu'un SON (canaux `miss`/`fumble`, qui n'ont rien à montrer) — la grille et
	les décalages restent alors sans objet, mais ils ne gênent pas."""
	d = doc if isinstance(doc, dict) else {}
	fichier = str(d.get("fichier") or "").strip()
	son = str(d.get("son") or "").strip()
	if not fichier and not son:
		return None

	colonnes = max(1, _as_int(d.get("colonnes"), 1))
	lignes = max(1, _as_int(d.get("lignes"), 1))
	total = colonnes * lignes

	sens = str(d.get("sens_lignes") or SENS_DEFAUT)
	if sens not in SENS_LIGNES:
		sens = SENS_DEFAUT
	sens_cols = str(d.get("sens_colonnes") or SENS_COLONNES_DEFAUT)
	if sens_cols not in SENS_COLONNES:
		sens_cols = SENS_COLONNES_DEFAUT
	ancrage = str(d.get("ancrage") or ANCRAGE_DEFAUT)
	if ancrage not in ANCRAGES:
		ancrage = ANCRAGE_DEFAUT
	depart = str(d.get("depart_ancrage") or DEPART_ANCRAGE_DEFAUT)
	if depart not in DEPART_ANCRAGES:
		depart = DEPART_ANCRAGE_DEFAUT

	debut = min(max(0, _as_int(d.get("debut"), 0)), total - 1)
	# `fin` absent ⇒ toute la feuille : c'est ce que le scan sème, et c'est la lecture
	# la plus utile d'une planche dont on vient de deviner la grille.
	fin = min(max(debut, _as_int(d.get("fin"), total - 1)), total - 1)

	echelle = _as_float(d.get("echelle"), ECHELLE_DEFAUT)
	if echelle <= 0:
		echelle = ECHELLE_DEFAUT

	# Temps de VOL, distinct de la durée d'une passe d'images (les images bouclent pendant
	# le trajet — un projectile de 4 images peut voler une seconde sans défiler au ralenti).
	# ⚠️ 0 ou illisible ⇒ repli sur `duree_ms` : c'est le réglage naturel d'une animation
	# qu'on vient de faire voyager, et le champ peut rester vide dans l'éditeur.
	duree_ms = max(1, _as_int(d.get("duree_ms"), DUREE_DEFAUT_MS))
	duree_trajet = _as_int(d.get("duree_trajet_ms"), 0)
	if duree_trajet <= 0:
		duree_trajet = duree_ms

	# Points de lecture DANS LE FICHIER son, en ms comme toutes les durées du document.
	# ⚠️ `son_fin_ms = 0` (le défaut) vaut « jusqu'au bout du fichier » et NON « ne rien
	# jouer » : la durée réelle d'un son n'est connue que du navigateur, le serveur ne peut
	# pas la borner. Une fin AVANT le début est ramenée au début (segment vide plutôt
	# qu'inversé), même règle que `debut`/`fin` des images.
	son_debut = max(0, _as_int(d.get("son_debut_ms"), 0))
	son_fin = max(0, _as_int(d.get("son_fin_ms"), 0))
	if son_fin and son_fin < son_debut:
		son_fin = son_debut
	volume = _as_float(d.get("son_volume"), VOLUME_DEFAUT)
	volume = min(1.0, max(0.0, volume))

	return {
		"id": str(d.get("_id") or ""),
		# Un doc son-seul n'a pas de `fichier` : son nom de repli est celui du SON, sinon la
		# liste de l'éditeur afficherait une ligne vide.
		"nom": str(d.get("nom") or fichier or son),
		"fichier": fichier,
		# Dimensions de la FEUILLE, lues par le scan (Pillow) et jamais saisies. Le client
		# en dérive le rapport d'aspect d'une frame, pour ne pas déformer le sprite.
		"largeur": max(0, _as_int(d.get("largeur"), 0)),
		"hauteur": max(0, _as_int(d.get("hauteur"), 0)),
		"colonnes": colonnes,
		"lignes": lignes,
		"sens_lignes": sens,
		"sens_colonnes": sens_cols,
		"debut": debut,
		"fin": fin,
		"duree_ms": duree_ms,
		"echelle": echelle,
		"decalage_x": _as_float(d.get("decalage_x"), 0.0),
		"decalage_y": _as_float(d.get("decalage_y"), 0.0),
		"ancrage": ancrage,
		# ── Trajectoire ──
		"depart_ancrage": depart,
		"depart_decalage_x": _as_float(d.get("depart_decalage_x"), 0.0),
		"depart_decalage_y": _as_float(d.get("depart_decalage_y"), 0.0),
		"duree_trajet_ms": duree_trajet,
		# Hauteur de la cloche en CASES (0 = ligne droite) : c'est ce qui distingue une
		# flèche tendue d'un caillou lancé. Négatif = cloche vers le bas, assumé.
		"arc": _as_float(d.get("arc"), 0.0),
		"rotation": _as_float(d.get("rotation"), ROTATION_DEFAUT),
		"rotation_auto": bool(d.get("rotation_auto")),
		# ── Son ──
		"son": son,
		"son_debut_ms": son_debut,
		"son_fin_ms": son_fin,
		"son_volume": volume,
		# Brouillon tant qu'un humain n'a pas confirmé la découpe à l'aperçu : absent du
		# catalogue servi au combat.
		"actif": bool(d.get("actif")),
	}


def frame_position(anim: dict, i: int) -> tuple:
	"""Position (colonne, ligne EN PIXELS) de la i-ème image dans l'ordre de lecture.

	Ordre de lecture : GAUCHE → DROITE (`sens_colonnes: "gauche_droite"`, le défaut) ou
	droite → gauche, puis HAUT → BAS (`sens_lignes: "haut_bas"`, le défaut) ou bas → haut.
	Les deux axes sont INDÉPENDANTS : les inverser tous les deux joue la feuille entière
	à l'envers. Source unique de l'arithmétique : le client la rejoue en
	`background-position`, les tests la vérifient ici.

	`i` est borné à la grille — une plage mal saisie ne doit pas produire une position
	hors feuille (fond transparent, animation muette et inexplicable)."""
	a = anim or {}
	colonnes = max(1, _as_int(a.get("colonnes"), 1))
	lignes = max(1, _as_int(a.get("lignes"), 1))
	i = min(max(0, _as_int(i, 0)), colonnes * lignes - 1)
	rang_col = i % colonnes
	rang = i // colonnes
	# Tout ce qui n'est pas explicitement inversé se lit dans le sens du défaut.
	col = (colonnes - 1 - rang_col) if a.get("sens_colonnes") == "droite_gauche" else rang_col
	ligne = (lignes - 1 - rang) if a.get("sens_lignes") == "bas_haut" else rang
	return col, ligne


def decalage_y_effectif(decalage_y) -> float:
	"""Décalage vertical RÉELLEMENT joué = base commune + réglage du doc.

	Source unique de l'arithmétique : le payload de combat passe par ici, et l'aperçu de
	`/admin/animations` rejoue la même addition côté client (la base lui est publiée par
	`GET /api/admin/animations`) — sinon on réglerait un décalage que le jeu ne montrerait
	pas."""
	return DECALAGE_Y_BASE + _as_float(decalage_y, 0.0)


def decalage_x_effectif(decalage_x) -> float:
	"""Miroir horizontal de `decalage_y_effectif`. Base nulle ⇒ le champ absent ne décale
	rien, mais il passe par le même chemin : le jour où la base bougerait, elle bougerait
	pour tout le monde d'un seul endroit."""
	return DECALAGE_X_BASE + _as_float(decalage_x, 0.0)


def catalogue_payload(docs) -> dict:
	"""`{id: {…clés de rendu…}}` des animations ACTIVES seulement.

	Un brouillon (grille non confirmée) reste invisible du jeu : le contenu qui le
	référencerait ne jouerait rien, ce qui est le comportement voulu — mieux vaut aucun
	sprite qu'une découpe fantaisiste.

	⚠️ `decalage_x`/`decalage_y` y sont les décalages EFFECTIFS (base comprise), pas les
	valeurs du doc : le client rend ce qu'on lui donne, il n'a pas à connaître la règle.
	⚠️ Les décalages de DÉPART passent par les mêmes bases — les deux bouts d'un vol doivent
	se poser sur un personnage de la même façon, sinon le sprite sauterait au décollage."""
	catalogue = {}
	for doc in docs or []:
		anim = normaliser_animation(doc)
		if not anim or not anim["actif"] or not anim["id"]:
			continue
		charge = {cle: anim[cle] for cle in CLES_PAYLOAD}
		charge["decalage_x"] = decalage_x_effectif(anim["decalage_x"])
		charge["decalage_y"] = decalage_y_effectif(anim["decalage_y"])
		charge["depart_decalage_x"] = decalage_x_effectif(anim["depart_decalage_x"])
		charge["depart_decalage_y"] = decalage_y_effectif(anim["depart_decalage_y"])
		catalogue[anim["id"]] = charge
	return catalogue


# ── Liaison contenu → animation ──────────────────────────────────────────────────

def animation_pour(canal: str, source_anim: str | None = None) -> str:
	"""Cascade de résolution : animation portée par le DOC de contenu (sort, compétence,
	arme, espèce, consommable), sinon défaut du CANAL, sinon rien.

	Chaîne vide ⇒ pas d'animation, à tous les étages. C'est ce qui rend l'ensemble sans
	migration : un contenu non configuré et une world-var vide se comportent comme avant."""
	directe = str(source_anim or "").strip()
	if directe:
		return directe
	defauts = character_stats.COMBAT_ANIMATIONS_DEFAUT or {}
	return str(defauts.get(str(canal or ""), "") or "").strip()


def defauts_canaux() -> dict:
	"""Copie de la table des défauts par CANAL, pour l'AFFICHER (rappel de `/admin/animations`).

	⚠️ Lue **via le module** comme `animation_pour`, jamais par `from … import` : la world-var
	est réglable à chaud, une valeur figée à l'import n'aurait jamais l'air de bouger — et un
	rappel qui ment est pire que pas de rappel. ⚠️ COPIE, jamais l'exemplaire mémorisé : ce
	dict est muté EN PLACE au chargement des variables de monde, un appelant qui écrirait
	dedans changerait le comportement du combat depuis un écran de lecture."""
	defauts = character_stats.COMBAT_ANIMATIONS_DEFAUT or {}
	return {str(cle): str(val or "") for cle, val in defauts.items()}


def vfx(canal: str, cible_id: str, source_anim: str | None = None,
		acteur_id: str | None = None) -> dict | None:
	"""Charge d'animation à poser sur une entrée de journal, ou None si rien n'est résolu.

	`None` est le cas NORMAL (aucun contenu configuré) : l'appelant n'ajoute alors pas la
	clé `vfx`, et les combats déjà en base continuent de tourner à l'identique.

	`cible` est l'ID DE SNAPSHOT (`monstre_N` / `joueur_N`), le seul identifiant que le
	texte du journal ne porte pas et dont le client a besoin pour placer le sprite.

	`acteur` n'est présent que s'il DIFFÈRE de la cible : c'est ce qui donne son sens au
	champ `ancrage` du doc d'animation — une lame enflammée peut vouloir s'allumer sur la
	main qui la tient plutôt que sur la chair qu'elle ouvre. Le client choisit ; le serveur
	ne peut pas trancher ici sans relire le doc `animation:*`, ce qu'aucune résolution de
	coup ne doit faire."""
	anim = animation_pour(canal, source_anim)
	cible = str(cible_id or "")
	if not anim or not cible:
		return None
	charge = {"anim": anim, "cible": cible}
	acteur = str(acteur_id or "")
	if acteur and acteur != cible:
		charge["acteur"] = acteur
	return charge


# ── Scan du répertoire (hypothèses de découpe) ───────────────────────────────────

# « spritesheet-512px-by-197px-per-frame-red.png » et « …-by197px-… » (les deux graphies
# existent dans le dossier) : la taille d'UNE image est donnée, la grille s'en déduit.
_RE_PER_FRAME = re.compile(r"(\d+)\s*px[-_ ]*by[-_ ]*(\d+)\s*px[-_ ]*per[-_ ]*frame", re.I)
# « Smoke45Frames.png » : le NOMBRE d'images est donné, la grille reste à trouver.
_RE_NB_FRAMES = re.compile(r"(\d+)\s*frames", re.I)


def _grille_pour_n(n: int, largeur: int, hauteur: int) -> tuple:
	"""Meilleure grille (colonnes, lignes) contenant `n` images sur une feuille donnée.

	Critère PRINCIPAL : des cases aussi CARRÉES que possible — c'est ce qui distingue
	7×7 (49 cases, cases carrées) de 5×9 (45 cases pile mais cases étirées) sur
	`Smoke45Frames` 1792×1792. Le gaspillage ne départage qu'à égalité de forme."""
	meilleur = None
	for colonnes in range(1, max(1, n) + 1):
		lignes = -(-n // colonnes)   # ceil
		cw, ch = largeur / colonnes, hauteur / lignes
		if cw <= 0 or ch <= 0:
			continue
		score = (round(abs(cw / ch - 1.0), 6), colonnes * lignes - n, colonnes)
		if meilleur is None or score < meilleur[0]:
			meilleur = (score, colonnes, lignes)
	return (meilleur[1], meilleur[2]) if meilleur else (1, 1)


def deviner_grille(nom: str, largeur: int, hauteur: int) -> tuple:
	"""`(colonnes, lignes, devinee)` — hypothèse de découpe semée par le scan.

	⚠️ `devinee` n'est PAS `actif` : le scan écrit `actif: False` dans TOUS les cas. Le
	drapeau dit seulement si une heuristique a mordu (grille plausible à vérifier) ou si
	l'on est retombé sur le repli 1×1 — une image fixe, honnête, plutôt qu'un découpage
	inventé. Rien n'est jamais actif sans confirmation humaine à l'aperçu."""
	nom = str(nom or "")
	largeur, hauteur = max(0, _as_int(largeur)), max(0, _as_int(hauteur))
	if largeur <= 0 or hauteur <= 0:
		return 1, 1, False

	# 1. Taille d'une frame annoncée dans le nom du fichier.
	m = _RE_PER_FRAME.search(nom)
	if m:
		fw, fh = _as_int(m.group(1)), _as_int(m.group(2))
		if fw > 0 and fh > 0:
			return max(1, largeur // fw), max(1, hauteur // fh), True

	# 2. Nombre d'images annoncé dans le nom du fichier.
	m = _RE_NB_FRAMES.search(nom)
	if m:
		n = _as_int(m.group(1))
		if n > 0:
			colonnes, lignes = _grille_pour_n(n, largeur, hauteur)
			return colonnes, lignes, True

	# 3. Bande simple : très allongée ET la petite dimension divise la grande.
	if hauteur > 0 and largeur >= 4 * hauteur and largeur % hauteur == 0:
		return largeur // hauteur, 1, True
	if largeur > 0 and hauteur >= 4 * largeur and hauteur % largeur == 0:
		return 1, hauteur // largeur, True

	# 4. Planche carrée découpable en cases carrées « raisonnables » (32–256 px, au plus
	#    près de 128 : la taille de case la plus fréquente du commerce).
	if largeur == hauteur:
		meilleur = None
		for n in range(1, 33):
			if largeur % n:
				continue
			cote = largeur // n
			if cote < 32 or cote > 256:
				continue
			ecart = abs(cote - 128)
			if meilleur is None or ecart < meilleur[0]:
				meilleur = (ecart, n)
		if meilleur:
			return meilleur[1], meilleur[1], True

	# 5. Repli : une seule image. Se règle à l'aperçu.
	return 1, 1, False


def slug_animation(fichier: str, suffixe: str = "a") -> str:
	"""`"Slash Small Sheet.png"` → `"animation:slash_small_sheet_a"`.

	Le suffixe permet DEUX animations sur une même feuille (une planche en contient
	souvent plusieurs) et sert d'échappatoire au scan quand deux noms de fichiers
	différents produisent le même slug (« Hit-Yellow.png » et « hit - yellow.png »)."""
	base = re.sub(r"\.[A-Za-z0-9]+$", "", str(fichier or ""))
	slug = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_") or "animation"
	suffixe = re.sub(r"[^a-z0-9]+", "", str(suffixe or "a").lower()) or "a"
	return f"animation:{slug}_{suffixe}"


def est_image(nom: str) -> bool:
	"""Extension servable par le mount `/icons` (le dossier contient aussi un Thumbs.db)."""
	return str(nom or "").lower().endswith(EXTENSIONS_IMAGE)


def est_son(nom: str) -> bool:
	"""Extension servable par le mount `/sounds`, miroir d'`est_image` : le dossier peut
	contenir autre chose (licences, .txt), et un fichier non jouable ne doit pas devenir un
	doc d'animation."""
	return str(nom or "").lower().endswith(EXTENSIONS_SON)
