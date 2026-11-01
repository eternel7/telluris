"""Ce que montre le MARQUEUR d'une connexion sur la carte de /play (pur).

Un marqueur de passage (`lieux.passages_carte`) est un point qui pulse. Sa couleur dit la
FAMILLE du lieu où il mène, son pictogramme le MÉTIER, et le toast de proximité dit
« Une boucherie est proche. ». Sans métier connu (route, porte, ville, pays…), c'est le
point bleu d'origine, sans pictogramme.

Résolution, dans l'ordre (`icone_lieu`) :
1. `categorie` du lieu dans `METIERS` ;
2. capacité accordée par TAG (taverne, étable, scriptorium, guilde), relue par
   `capacites.capacites_de` : un lieu de n'importe quelle catégorie peut l'avoir ;
3. grande maison de `LIEU_CATEGORIES_FUSION` absente de `METIERS` : famille et pictogramme
   de sa PREMIÈRE catégorie fusionnée (relue à chaque appel, réglable à chaud) ;
4. sinon `route`.

Libellés : ceux de `dev/gabarits_metiers.py` (« tient une boucherie »), avec leur article,
pour accorder sans règle de grammaire.
"""

from models import character_stats
from utils import capacites

# Teinte du halo, « r, g, b » (le CSS l'emploie en `rgba(var(--passage-rgb), a)`).
FAMILLES = {
	"route":     "110, 185, 255",   # bleu d'origine des passages
	"vivres":    "245, 175, 70",
	"armes":     "235, 95, 85",
	"soins":     "110, 210, 125",
	"savoir":    "185, 140, 255",
	"artisanat": "205, 155, 105",
}

# categorie → (famille, pictogramme, libellé avec article)
METIERS = {
	# Vivres et taverne
	"auberge":                ("vivres", "🍺", "une auberge"),
	"boucherie":              ("vivres", "🥩", "une boucherie"),
	"boulangerie":            ("vivres", "🍞", "une boulangerie"),
	"cave":                   ("vivres", "🍷", "une cave"),
	"cuisine":                ("vivres", "🍲", "une cuisine"),
	"fumoir":                 ("vivres", "🍖", "un fumoir"),
	"jardinier":              ("vivres", "🌱", "une jardinerie"),
	"salaison":               ("vivres", "🧂", "une salaison"),
	"grande_boulangerie":     ("vivres", "🍞", "une grande boulangerie"),
	"grandes_halles_alimentaires": ("vivres", "🧺", "des halles"),
	"maison_des_conserves":   ("vivres", "🫙", "une maison des conserves"),
	# Armes et armures
	"armurerie":              ("armes", "🛡️", "une armurerie"),
	"fletcher":               ("armes", "🏹", "une archerie"),
	"atelier_de_l_empenneur": ("armes", "🎯", "un atelier d'empenneur"),
	"grand_arsenal":          ("armes", "⚔️", "un arsenal"),
	"grand_atelier_d_empennage": ("armes", "🎯", "un grand atelier d'empennage"),
	# Soins et alchimie
	"apothicairerie":         ("soins", "🌿", "une apothicairerie"),
	"laboratoire_d_alchimie": ("soins", "⚗️", "un laboratoire d'alchimie"),
	"savonnerie":             ("soins", "🧼", "une savonnerie"),
	"grande_apothicairerie":  ("soins", "🌿", "une grande apothicairerie"),
	"institut_medico_alchimique": ("soins", "⚕️", "un institut médico-alchimique"),
	"grand_laboratoire_alchimique": ("soins", "⚗️", "un grand laboratoire alchimique"),
	"manufacture_des_savons_et_parfums": ("soins", "🧼", "une manufacture de savons"),
	# Savoir, magie et guilde
	"scriptorium":            ("savoir", "📜", "un scriptorium"),
	"grand_scriptorium":      ("savoir", "📜", "un grand scriptorium"),
	"necromancie":            ("savoir", "💀", "une boutique de nécromancie"),
	"institut_de_thanaturgie": ("savoir", "💀", "un institut de thanaturgie"),
	"guilde_aventurier":      ("savoir", "⚜️", "la guilde des aventuriers"),
	"guilde_aventurier_comptoir": ("savoir", "⚜️", "le comptoir de la guilde"),
	"guilde_aventurier_exterieur": ("savoir", "⚜️", "la guilde des aventuriers"),
	"bureau_maitre_guilde":   ("savoir", "⚜️", "le bureau du maître de guilde"),
	# Artisanat, commerce et services
	"atelier_d_artisan":      ("artisanat", "🔨", "un atelier d'artisan"),
	"atelier_de_cirier":      ("artisanat", "🕯️", "un atelier de cirier"),
	"bijouterie":             ("artisanat", "💍", "une bijouterie"),
	"bourrellerie":           ("artisanat", "🏇", "une bourrellerie"),
	"boyauderie":             ("artisanat", "🦴", "une boyauderie"),
	"brosserie":              ("artisanat", "🪥", "une brosserie"),
	"corderie":               ("artisanat", "🪢", "une corderie"),
	"cordonnerie":            ("artisanat", "👢", "une cordonnerie"),
	"etable":                 ("artisanat", "🐎", "une étable"),
	"lutherie":               ("artisanat", "🎻", "une lutherie"),
	"maroquinerie":           ("artisanat", "👜", "une maroquinerie"),
	"negociant":              ("artisanat", "⚖️", "une maison de négoce"),
	"plumasserie":            ("artisanat", "🪶", "une plumasserie"),
	"tabletterie":            ("artisanat", "🎲", "une tabletterie"),
	"tannerie":               ("artisanat", "🐂", "une tannerie"),
	"taxidermie":             ("artisanat", "🦉", "un cabinet de taxidermie"),
	"tissage":                ("artisanat", "🧶", "un atelier de tissage"),
	"grande_manufacture_du_cuir": ("artisanat", "👜", "une manufacture du cuir"),
	"grande_manufacture_textile": ("artisanat", "🧶", "une manufacture textile"),
	"grande_orfevrerie":      ("artisanat", "💎", "une orfèvrerie"),
	"manufacture_des_instruments": ("artisanat", "🎻", "une manufacture d'instruments"),
	"grande_maison_des_arts": ("artisanat", "🎨", "une maison des arts"),
	"cabinet_des_specimens":  ("artisanat", "🦉", "un cabinet des spécimens"),
	"grande_corderie":        ("artisanat", "🪢", "une grande corderie"),
}

# Capacité accordée par TAG → catégorie de `METIERS` qui la représente.
CAPACITE_METIER = {
	"taverne": "auberge",
	"montures": "etable",
	"scriptorium": "scriptorium",
	"guilde": "guilde_aventurier",
	"recrutement": "guilde_aventurier",
}

# Libellé d'une grande maison ajoutée à LIEU_CATEGORIES_FUSION sans entrée dans `METIERS`.
LIBELLE_GRANDE_MAISON = "une grande maison"

ROUTE = {"famille": "route", "rgb": FAMILLES["route"], "icone": None, "metier": None}


def _bloc(famille, icone, metier) -> dict:
	return {"famille": famille, "rgb": FAMILLES[famille], "icone": icone, "metier": metier}


def icone_lieu(doc) -> dict:
	"""`{famille, rgb, icone, metier}` du marqueur qui mène à ce lieu (cf. docstring du module)."""
	doc = doc or {}
	categorie = str(doc.get("categorie") or "")
	if categorie in METIERS:
		return _bloc(*METIERS[categorie])
	caps = capacites.capacites_de(doc)
	for cap, cat in CAPACITE_METIER.items():
		if caps.get(cap):
			return _bloc(*METIERS[cat])
	fusion = (character_stats.LIEU_CATEGORIES_FUSION or {}).get(categorie)
	for incluse in fusion or []:
		if incluse in METIERS:
			famille, icone, _ = METIERS[incluse]
			return _bloc(famille, icone, LIBELLE_GRANDE_MAISON)
	return dict(ROUTE)
