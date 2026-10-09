"""Catalogue des propriétés résidentielles : `rules:proprietes` + les 5 zones habitables.

    python dev/gen_proprietes.py

Sortie :
    jsons/proprietes_a_importer.json   (à coller dans la carte d'import de /admin)

Docs NEUFS (aucun ne préexiste dans le dump) : le PUT complet de l'import ne peut rien écraser
d'autre. Relancer régénère le fichier à l'identique (idempotent). Le détail du système :
compétence `telluris-proprietes`."""

import json
import os

SORTIE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jsons", "proprietes_a_importer.json")

C, L, M, D, Do = "chambre", "logement", "maison", "demeure", "domaine"
TOUS = [C, L, M, D, Do]

types = [
	{"id": C, "label": "Chambre", "rang": 1, "image": "chambre.jpg",
	 "description": "Petite unité individuelle : repos, récupération, petit espace personnel et stockage très limité.",
	 "prix_cuivre": 5000, "revente_facteur": 0.5, "occupants_max": 1, "personnel_max": 1, "stockage_kg": 20,
	 "location": {"prix_cuivre": 150, "duree_s": 7 * 86400}},
	{"id": L, "label": "Logement", "rang": 2, "image": "logement.jpg",
	 "description": "Petit logement indépendant : un ou deux occupants, quelques espaces simples, un PNJ accueilli ponctuellement.",
	 "prix_cuivre": 20000, "revente_facteur": 0.6, "occupants_max": 2, "personnel_max": 2, "stockage_kg": 60},
	{"id": M, "label": "Maison", "rang": 3, "image": "maison.jpg",
	 "description": "Habitation individuelle : plusieurs pièces, un véritable foyer, du personnel en nombre limité.",
	 "prix_cuivre": 80000, "revente_facteur": 0.6, "occupants_max": 5, "personnel_max": 4, "stockage_kg": 150},
	{"id": D, "label": "Demeure", "rang": 4, "image": "demeure.jpg",
	 "description": "Propriété importante : nombreuses pièces, personnel domestique, accueil d'invités.",
	 "prix_cuivre": 300000, "revente_facteur": 0.6, "occupants_max": 10, "personnel_max": 10, "stockage_kg": 400},
	{"id": Do, "label": "Domaine", "rang": 5, "image": "domaine.jpg",
	 "description": "Propriété foncière : une demeure principale, des dépendances, des terrains privés et de nombreuses activités.",
	 "prix_cuivre": 1000000, "revente_facteur": 0.6, "occupants_max": 20, "personnel_max": 25, "stockage_kg": 1000},
]


def am(id, nom, cat, types_, cout, capacite=None, activite=None, prerequis=None, effets=None, description=""):
	d = {"id": id, "nom": nom, "categorie": cat, "types_autorises": types_, "cout_cuivre": cout,
		 "prerequis": prerequis or [], "capacite": capacite or {}}
	if activite:
		d["activite"] = activite
	if effets:
		d["effets"] = effets
	if description:
		d["description"] = description
	return d


def poste(metier, n=1):
	return {"postes": {metier: n}}


amenagements = [
	# Tous types — la loge du gardien : le vol devient impossible dès qu'un gardien y est.
	am("loge_gardien", "Loge du gardien", "defense", TOUS, 1500, poste("gardien"), effets={"garde": True},
	   description="Un gardien y veille : plus personne ne se sert dans le coffre."),
	# Chambre
	am("lit_ameliore", "Lit amélioré", "vie", [C, L], 400),
	am("petit_coffre", "Petit coffre", "vie", [C, L], 300, {"stockage_kg": 15}),
	am("rangement", "Petit espace de rangement", "vie", [C], 200, {"stockage_kg": 10}),
	am("bureau", "Table ou bureau", "gestion", [C, L, M, D], 300),
	am("etagere", "Étagère", "vie", [C], 150, {"stockage_kg": 5}),
	am("eclairage", "Éclairage", "vie", [C, L], 100),
	am("decoration", "Décoration", "vie", TOUS, 200),
	# Logement
	am("chambre_amelioree", "Chambre améliorée", "vie", [L], 1500),
	am("reserve", "Coffre ou réserve", "vie", [L, M, D], 1000, {"stockage_kg": 40}),
	am("petite_cuisine", "Petite cuisine", "service", [L], 1200, poste("cuisinier"),
	   {"metier": "cuisinier", "label": "Cuisine"}),
	am("petite_salle_a_manger", "Petite salle à manger", "vie", [L], 800),
	am("petite_bibliotheque", "Petite bibliothèque", "gestion", [L], 1000),
	am("espace_medical", "Espace médical simple", "service", [L], 2000, poste("medecin"),
	   {"metier": "medecin", "label": "Soins"}),
	am("lit_supplementaire", "Lit supplémentaire", "vie", [L], 500, {"occupants": 1}),
	am("coin_resident", "Petit espace pour un PNJ résident", "service", [L], 800, poste("domestique"),
	   {"metier": "domestique", "label": "Service domestique"}),
	# Dès le Logement (la Chambre n'a qu'un poste : celui du gardien) — un boucher y dépèce et vend.
	am("salle_depecage", "Salle de dépeçage", "activite", [L, M, D, Do], 2500, poste("boucher"),
	   {"metier": "boucher", "label": "Dépeçage"},
	   description="Crocs, billot et rigoles : un boucher y dépèce les carcasses de monstres rapportées de la chasse."),
	# Maison
	am("chambres_multiples", "Chambres multiples", "vie", [M, D], 4000, {"occupants": 2}),
	am("grande_cuisine", "Grande cuisine", "service", [M, D, Do], 5000, poste("cuisinier"),
	   {"metier": "cuisinier", "label": "Cuisine"}),
	am("salle_a_manger", "Salle à manger", "vie", [M, D], 2500),
	am("salon", "Salon", "vie", [M], 2000),
	am("bibliotheque", "Bibliothèque", "gestion", [M, D], 4000),
	am("cave", "Cave", "vie", [M], 2500, {"stockage_kg": 60}),
	am("salle_de_soins", "Salle de soins", "service", [M], 4000, poste("medecin"),
	   {"metier": "medecin", "label": "Soins"}),
	am("salle_etude", "Salle d'étude", "service", [M, D, Do], 3500, poste("erudit"),
	   {"metier": "erudit", "label": "Étude"}),
	am("salle_entrainement", "Salle d'entraînement", "defense", [M, D], 4500),
	am("petit_laboratoire", "Petit laboratoire d'alchimie", "activite", [M], 6000, poste("alchimiste"),
	   {"metier": "alchimiste", "label": "Alchimie"}),
	am("petit_atelier", "Petit atelier d'artisan", "activite", [M], 5000, poste("artisan"),
	   {"metier": "artisan", "label": "Artisanat"}),
	am("bureau_professionnel", "Bureau pour un PNJ professionnel", "activite", [M], 3000, poste("marchand"),
	   {"metier": "marchand", "label": "Négoce"}),
	am("chambre_domestique", "Chambre de domestique", "service", [M], 2000, poste("domestique"),
	   {"metier": "domestique", "label": "Service domestique"}),
	am("cour_interieure", "Cour intérieure", "exterieur", [M], 2500),
	am("petit_jardin", "Petit jardin", "exterieur", [M], 2000),
	# Demeure
	am("quartiers_personnel", "Quartiers du personnel", "vie", [D, Do], 8000, poste("domestique", 3),
	   {"metier": "domestique", "label": "Service domestique"}),
	am("appartement_invites", "Appartement pour invités", "vie", [D], 8000, {"occupants": 2}),
	am("salle_reunion", "Salle de réunion", "gestion", [D, Do], 4000),
	am("archives", "Salle d'archives", "gestion", [D, Do], 4000, {"stockage_kg": 100}),
	am("salon_reception", "Salon de réception", "service", [D], 6000),
	am("salle_medicale", "Salle médicale", "service", [D], 8000, poste("medecin"),
	   {"metier": "medecin", "label": "Soins"}),
	am("infirmerie", "Infirmerie", "service", [D, Do], 9000, poste("medecin"),
	   {"metier": "medecin", "label": "Soins"}),
	am("laboratoire_alchimie", "Laboratoire d'alchimie", "activite", [D, Do], 12000, poste("alchimiste"),
	   {"metier": "alchimiste", "label": "Alchimie"}),
	am("atelier_artisan", "Atelier d'artisan", "activite", [D, Do], 10000, poste("artisan"),
	   {"metier": "artisan", "label": "Artisanat"}),
	am("cabinet_medecin", "Cabinet de médecin", "activite", [D, Do], 10000, poste("medecin"),
	   {"metier": "medecin", "label": "Médecine"}),
	am("cabinet_apothicaire", "Cabinet d'apothicaire", "activite", [D], 10000, poste("apothicaire"),
	   {"metier": "apothicaire", "label": "Apothicairerie"}),
	am("bureau_marchand", "Bureau de marchand", "activite", [D, Do], 8000, poste("marchand"),
	   {"metier": "marchand", "label": "Négoce"}),
	am("salle_recherche", "Salle d'étude et de recherche", "activite", [D, Do], 8000, poste("erudit"),
	   {"metier": "erudit", "label": "Recherche"}, prerequis=["salle_etude"]),
	am("salle_armes", "Salle d'armes", "defense", [D, Do], 8000),
	am("cour_entrainement", "Cour d'entraînement", "defense", [D, Do], 6000, poste("garde"),
	   {"metier": "garde", "label": "Entraînement des gardes"}),
	am("jardin", "Jardin", "exterieur", [D, Do], 4000, poste("jardinier"),
	   {"metier": "jardinier", "label": "Jardinage"}),
	am("cour", "Cour", "exterieur", [D, Do], 3000),
	am("ecurie_limitee", "Écurie limitée", "exterieur", [D], 10000, poste("palefrenier"),
	   {"metier": "palefrenier", "label": "Soins aux bêtes"}),
	# Domaine
	am("nombreuses_chambres", "Nombreuses chambres", "vie", [Do], 12000, {"occupants": 6}),
	am("appartements_invites", "Appartements pour invités", "vie", [Do], 15000, {"occupants": 4}),
	am("bureau_administratif", "Bureau administratif", "gestion", [Do], 8000, poste("intendant"),
	   {"metier": "intendant", "label": "Administration"}),
	am("grande_bibliotheque", "Grande bibliothèque", "gestion", [Do], 12000),
	am("salle_gestion", "Salle de gestion des ressources", "gestion", [Do], 8000, poste("intendant"),
	   {"metier": "intendant", "label": "Gestion des ressources"}, prerequis=["bureau_administratif"]),
	am("grande_salle_a_manger", "Grande salle à manger", "vie", [Do], 8000),
	am("buanderie", "Buanderie", "service", [Do], 5000, poste("domestique", 2),
	   {"metier": "domestique", "label": "Blanchisserie"}),
	am("apothicairerie", "Apothicairerie", "activite", [Do], 14000, poste("apothicaire", 2),
	   {"metier": "apothicaire", "label": "Apothicairerie"}),
	am("ateliers_specialises", "Ateliers spécialisés", "activite", [Do], 20000, poste("artisan", 3),
	   {"metier": "artisan", "label": "Artisanat spécialisé"}),
	am("cabinets_specialistes", "Cabinets de spécialistes", "activite", [Do], 15000, poste("erudit", 2),
	   {"metier": "erudit", "label": "Consultations"}, prerequis=["cabinet_medecin"]),
	am("poste_de_garde", "Poste de garde", "defense", [Do], 8000, poste("garde", 2),
	   {"metier": "garde", "label": "Garde du domaine"}),
	am("quartiers_gardes", "Quartiers des gardes", "defense", [Do], 12000, poste("garde", 4),
	   prerequis=["poste_de_garde"]),
	am("dispositifs_defensifs", "Dispositifs défensifs privés", "defense", [Do], 15000,
	   prerequis=["poste_de_garde"], description="Compatibles avec les règlements de la ville."),
	am("potager", "Potager", "exterieur", [Do], 3000, poste("jardinier"),
	   {"metier": "jardinier", "label": "Potager"}),
	am("verger", "Verger", "exterieur", [Do], 5000, poste("jardinier"),
	   {"metier": "jardinier", "label": "Verger"}),
	am("ecuries", "Écuries", "exterieur", [Do], 15000, poste("palefrenier", 2),
	   {"metier": "palefrenier", "label": "Soins aux bêtes"}),
	am("grange", "Grange", "exterieur", [Do], 8000, {"stockage_kg": 300}),
	am("dependances", "Dépendances", "exterieur", [Do], 10000, {"stockage_kg": 200, "occupants": 4}),
	am("terrain_prive", "Terrain privé", "exterieur", [Do], 6000),
]

metiers = [
	{"id": "gardien", "label": "Gardien", "cout_embauche_cuivre": 600, "description": "Veille sur les lieux : empêche le vol."},
	{"id": "domestique", "label": "Domestique", "cout_embauche_cuivre": 300},
	{"id": "cuisinier", "label": "Cuisinier", "cout_embauche_cuivre": 500},
	{"id": "medecin", "label": "Médecin", "cout_embauche_cuivre": 2000},
	{"id": "apothicaire", "label": "Apothicaire", "cout_embauche_cuivre": 1500},
	{"id": "alchimiste", "label": "Alchimiste", "cout_embauche_cuivre": 2000},
	{"id": "artisan", "label": "Artisan", "cout_embauche_cuivre": 1500},
	{"id": "marchand", "label": "Marchand", "cout_embauche_cuivre": 1200},
	{"id": "erudit", "label": "Érudit", "cout_embauche_cuivre": 1200},
	{"id": "garde", "label": "Garde", "cout_embauche_cuivre": 800},
	{"id": "intendant", "label": "Intendant", "cout_embauche_cuivre": 1500},
	{"id": "jardinier", "label": "Jardinier", "cout_embauche_cuivre": 300},
	{"id": "palefrenier", "label": "Palefrenier", "cout_embauche_cuivre": 300},
	{"id": "boucher", "label": "Boucher", "cout_embauche_cuivre": 800},
	{"id": "bibliothecaire", "label": "Bibliothécaire", "cout_embauche_cuivre": 600,
	 "description": "Tient la bibliothèque : on peut y écrire comme au scriptorium."},
]

# Postes MARCHANDS : catégories de boutique qu'un employé peut y exercer. Les grandes maisons
# (LIEU_CATEGORIES_FUSION) n'apparaissent que sur des aménagements de Demeure/Domaine.
CATEGORIES = {
	"petite_cuisine": ["cuisine"],
	"grande_cuisine": ["cuisine", "boulangerie"],
	"petit_laboratoire": ["laboratoire_d_alchimie"],
	"laboratoire_alchimie": ["laboratoire_d_alchimie", "grand_laboratoire_alchimique"],
	"petit_atelier": ["atelier_d_artisan", "tabletterie"],
	"atelier_artisan": ["atelier_d_artisan", "tabletterie", "grande_maison_des_arts"],
	"ateliers_specialises": ["atelier_d_artisan", "tabletterie", "savonnerie", "grande_maison_des_arts"],
	"cabinet_medecin": ["institut_medico_alchimique"],
	"cabinet_apothicaire": ["apothicairerie"],
	"apothicairerie": ["apothicairerie", "grande_apothicairerie"],
	"salle_depecage": ["boucherie"],
	# Négociant (« marchand pur », utils/negoce.py) : le poste marchand existant, Demeure et Domaine.
	"bureau_marchand": ["negociant"],
	"jardin": ["jardinier"],
	"potager": ["jardinier"],
	"verger": ["jardinier"],
	# Érudits : copistes (scriptorium) et naturalistes ; le bureau « professionnel » de la
	# Maison reçoit le négociant, comme le Bureau de marchand.
	"salle_etude": ["scriptorium"],
	"salle_recherche": ["scriptorium"],
	"cabinets_specialistes": ["cabinet_des_specimens", "taxidermie"],
	"bureau_professionnel": ["negociant"],
}
GRANDES = {"grand_laboratoire_alchimique", "grande_maison_des_arts", "institut_medico_alchimique",
		   "grande_apothicairerie", "cabinet_des_specimens"}
for a in amenagements:
	if a["id"] in CATEGORIES:
		a["activite"]["categories"] = CATEGORIES[a["id"]]
		if GRANDES & set(CATEGORIES[a["id"]]):
			assert set(a["types_autorises"]) <= {D, Do}, a["id"]


# ── Effets des aménagements (utils/proprietes.py § Effets) ──────────────────────────
# `effets`       : actifs dès l'installation.
# `effets_poste` : actifs seulement si un employé du métier tient le poste (activité exercée).
# ⚠️ NON-CUMUL. Les effets à durée posés au réveil (`reveil`, `reveil_montures`) passent par
# `consommables.poser_effet` sous la clé `amenagement:<id>` : une nuit REMPLACE la précédente,
# et `cumul_effets` ne retient que le meilleur bonus par caractéristique — d'où une
# caractéristique DISTINCTE par aménagement d'un même type de bien. Les autres effets sont des
# états binaires du bien (actif ou non), jamais une somme.
def reveil(duree, nom=None, icon="🌅", buffs=None, regen_pv=0, regen_pm=0, esquive=0, **extra):
	d = {"duree": duree, "icon": icon}
	if nom:
		d["nom"] = nom
	if buffs:
		d["buffs"] = buffs
	for cle, val in (("regen_pv", regen_pv), ("regen_pm", regen_pm), ("esquive", esquive)):
		if val:
			d[cle] = val
	d.update(extra)
	return d


# Barème : petite +2 / 15 tours, normale +3 / 20, grande +4 / 25 (tours monde = déplacements).
EFFETS = {
	"lit_ameliore": {"reveil": reveil(15, "Bien dormi", "🛏️", regen_pv=2)},
	"eclairage": {"reveil": reveil(15, "Lecture du soir", "🕯️", regen_pm=2)},
	"chambre_amelioree": {"reveil": reveil(15, "Sommeil profond", "🌙", buffs={"Vol": 2})},
	# Les salles à manger ne nourrissent que si un cuisinier tient une cuisine du bien.
	"petite_salle_a_manger": {"reveil": reveil(15, "Bien nourri", "🍲", buffs={"R": 2}, requiert_metier="cuisinier")},
	"salle_a_manger": {"reveil": reveil(20, "Bien nourri", "🍲", buffs={"R": 3}, requiert_metier="cuisinier")},
	"grande_salle_a_manger": {"reveil": reveil(25, "Festin", "🍖", buffs={"R": 4}, requiert_metier="cuisinier")},
	"salle_entrainement": {"reveil": reveil(20, "Entraîné", "🏋️", buffs={"F": 3})},
	"salon": {"reveil": reveil(20, "Esprit reposé", "🛋️", buffs={"Vol": 3})},
	"salle_armes": {"reveil": reveil(20, "Garde affûtée", "⚔️", esquive=2)},
	"salon_reception": {"reveil": reveil(25, "Bonne réputation", "🎩", buffs={"Cha": 4})},
	"salle_reunion": {"reveil": reveil(20, "Plans préparés", "🗺️", buffs={"Ch": 3})},
	# Défense : le métier `garde` protège le coffre comme le gardien de la loge.
	"poste_de_garde": {"garde": True},
	"cour_entrainement": {"garde": True},
	"quartiers_gardes": {"garde": True},
	"dispositifs_defensifs": {"vol_limite": {"fraction": 0.25, "delai_s": 86400}},
	# Bien lui-même.
	"decoration": {"revente_bonus": 0.05},
	"bureau": {"registre": True},
	"petite_bibliotheque": {"grimoires_coffre": True},
	"bibliotheque": {"grimoires_coffre": True},
	"grande_bibliotheque": {"grimoires_coffre": True},
	"petit_jardin": {"recolte": {"items": ["item:Herbes_aromatiques", "item:Herbes_medicinales"],
								 "quantite": 2, "delai_s": 86400}},
	"terrain_prive": {"recolte": {"items": [f"item:Branche_de_{e}" for e in (
		"Alisier", "Bouleau", "Charme", "Chataignier", "Erable", "Orme", "Tilleul", "Tremble")],
								  "quantite": 3, "delai_s": 86400}},
}
DISSIPE = {"dissipe_malus": ["dormeurs"]}
EFFETS_POSTE = {
	"buanderie": {"reveil": reveil(20, "Habits propres", "🧺", buffs={"Cha": 3})},
	# Médecins : la nuit soigne déjà PV et PM — eux retirent ce qu'elle laisse (poisons, malus).
	"espace_medical": dict(DISSIPE),
	"salle_de_soins": dict(DISSIPE, reveil=reveil(20, "Convalescence", "🩺", regen_pv=2)),
	# Régén. PM et non PV : l'Infirmerie, ouverte AUSSI à la Demeure, donne déjà les PV.
	"salle_medicale": dict(DISSIPE, reveil=reveil(25, "Fortifiant", "🧪", regen_pm=3)),
	"infirmerie": {"dissipe_malus": ["dormeurs", "montures"],
				   "reveil": reveil(25, "Convalescence", "🩺", regen_pv=3),
				   "reveil_montures": reveil(25, "Convalescence", "🩺", regen_pv=3)},
	# Domestiques : un compagnon bien logé ne quitte pas le groupe de lui-même.
	"coin_resident": {"reveil": reveil(30, "Bien logé", "🏠", fidele=True, compagnons_seuls=True)},
	"chambre_domestique": {"reveil": reveil(30, "Bien logé", "🏠", fidele=True, compagnons_seuls=True)},
	"quartiers_personnel": {"reveil": reveil(30, "Bien logé", "🏠", fidele=True, compagnons_seuls=True)},
	# Intendants.
	"bureau_administratif": {"releve_auto": True},
	"salle_gestion": {"candidats_bonus": 1},
	# Bibliothécaires : le bien devient un scriptorium (`scriptorium.lieu_est_scriptorium`).
	"petite_bibliotheque": {"scriptorium": True},
	"bibliotheque": {"scriptorium": True},
	"grande_bibliotheque": {"scriptorium": True},
	# Palefreniers.
	"ecurie_limitee": {"reveil_montures": reveil(20, "Bien pansée", "🐴", buffs={"R": 3, "Ag": 3})},
	"ecuries": {"reveil_montures": reveil(20, "Bien pansée", "🐴", buffs={"R": 3, "Ag": 3})},
}
# Écurie : places où LAISSER une monture (elle reste comptée dans le plafond du troupeau).
ECURIE = {"cour_interieure": 1, "cour": 1, "ecurie_limitee": 2, "ecuries": 4}
# Postes et activités ajoutés : bibliothécaires, et l'activité qui manquait aux Quartiers des gardes.
POSTES = {"petite_bibliotheque": ("bibliothecaire", 1, "Bibliothèque"),
		  "bibliotheque": ("bibliothecaire", 1, "Bibliothèque"),
		  "grande_bibliotheque": ("bibliothecaire", 2, "Bibliothèque")}
for a in amenagements:
	if a["id"] in POSTES:
		metier, n, label = POSTES[a["id"]]
		a["capacite"]["postes"] = {metier: n}
		a["activite"] = {"metier": metier, "label": label}
	if a["id"] == "quartiers_gardes":
		a["activite"] = {"metier": "garde", "label": "Garde du domaine"}
	if a["id"] in ECURIE:
		a["capacite"]["ecurie"] = ECURIE[a["id"]]
	if a["id"] in EFFETS:
		a["effets"] = dict(a.get("effets") or {}, **EFFETS[a["id"]])
	if a["id"] in EFFETS_POSTE:
		a["effets_poste"] = EFFETS_POSTE[a["id"]]
		assert a.get("activite"), a["id"]           # un effet de poste exige un poste à tenir
assert set(EFFETS) | set(EFFETS_POSTE) | set(ECURIE) <= {a["id"] for a in amenagements}


def termes_reveil(bloc):
	"""Ce qu'un réveil modifie : une caractéristique, une régén, l'esquive, la fidélité."""
	return set(bloc.get("buffs") or {}) | {k for k in ("regen_pv", "regen_pm", "esquive", "fidele") if bloc.get(k)}


# NON-CUMUL : dans un même type de bien, deux aménagements ne touchent jamais le même terme
# au réveil — sinon le meilleur seul compterait et l'autre serait payé pour rien.
for t in TOUS:
	for cle in ("reveil", "reveil_montures"):
		vus = {}
		for a in amenagements:
			if t not in a["types_autorises"]:
				continue
			for bloc in (a.get("effets") or {}, a.get("effets_poste") or {}):
				for terme in termes_reveil(bloc.get(cle) or {}):
					assert terme not in vus, (t, cle, terme, vus.get(terme), a["id"])
					vus[terme] = a["id"]

reglages = {"candidats_duree_s": 86400,
			"vente_auto": {"proba": 0.5, "fraction": 0.34, "reserve": 1},
			# Prix d'achat majoré : MIROIR de `utils.proprietes.PRIX_ACHAT_DEFAUT` (verrouillé par
			# tests/test_proprietes.py) — l'éditer ici suffit à retoucher les valeurs en jeu.
			"prix_achat": {"rayon": 4,
						   "bonus": {"marchand": 0.05, "grand_marchand": 0.20, "guilde": 0.20},
						   "plafond_voisinage": 1.5, "multiplicateur_occupation": 2}}

# Cohérence interne : tout métier référencé existe, tout prérequis est installable sur au
# moins les types de l'aménagement qui l'exige, aucun doublon d'id.
ids = [a["id"] for a in amenagements]
assert len(ids) == len(set(ids))
mids = {m["id"] for m in metiers}
par_id = {a["id"]: a for a in amenagements}
for a in amenagements:
	for m in (a["capacite"].get("postes") or {}):
		assert m in mids, (a["id"], m)
	if "activite" in a:
		assert a["activite"]["metier"] in (a["capacite"].get("postes") or {}), a["id"]
	for p in a["prerequis"]:
		assert set(a["types_autorises"]) <= set(par_id[p]["types_autorises"]), (a["id"], p)
	for bloc in (a.get("effets") or {}, a.get("effets_poste") or {}):
		for cle in ("reveil", "reveil_montures"):
			if cle in bloc and "requiert_metier" in bloc[cle]:
				assert bloc[cle]["requiert_metier"] in mids, (a["id"], cle)

zones = [{
	"_id": f"zone:habitable_{t['id']}",
	"type": "zone_influence",
	"nom": f"Zone habitable — {t['label']}",
	"type_propriete": t["id"],
	"terrain_tags": ["ville", "urbain"],
	# 0 : la zone ne pèse sur AUCUN tirage d'événement (ni terrain ni profil) ; son
	# appartenance géométrique, elle, est testée à intensité pleine (zones.est_dans_zone).
	"intensite_max": 0,
	"table_evenements": [],
	"modificateurs": {},
} for t in types]

docs = [{"_id": "rules:proprietes", "type": "rules",
		 "value": {"types": types, "amenagements": amenagements, "metiers": metiers, "reglages": reglages}}] + zones
with open(SORTIE, "w", encoding="utf-8") as f:
	json.dump({"docs": docs}, f, ensure_ascii=False, indent=2)
	f.write("\n")
print(len(amenagements), "aménagements,", len(metiers), "métiers,", len(zones), "zones")
