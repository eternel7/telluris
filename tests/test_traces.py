# tests/test_traces.py
# Traces de monstres (`utils/traces.py`) : la pire menace possible à une position — pool de
# rencontres des zones actives, grades qui PEUVENT sortir — et le texte, libellé seul ou espèce
# + grade si un forestier est du groupe. Menace injectée (`menace_fn`) : aucun simulateur.

from utils import potentiel, traces, zones

ZONE = {"_id": "zone:foret", "intensite_max": 0.3}
ZONE_B = {"_id": "zone:marais", "intensite_max": 0.3}
ZONE_DEFS = {"zone:foret": ZONE, "zone:marais": ZONE_B}
# Forêt : rectangle centré (5,5) de 4×4 ; marais : centré (20,20).
LIEU = {
	"_id": "lieu:pays",
	"zone_influences": [
		{"zone": "zone:foret", "x": 5, "y": 5, "w": 4, "h": 4, "forme": "rectangle"},
		{"zone": "zone:marais", "x": 20, "y": 20, "w": 4, "h": 4, "forme": "rectangle"},
	],
	"rencontres": [
		{"espece": "espece:loup", "zones": ["zone:foret"]},
		{"espece": "espece:ours", "zones": ["zone:foret"]},
		{"espece": "espece:dragon", "zones": ["zone:marais"]},
	],
}
ESPECES = {
	"espece:loup": {"_id": "espece:loup", "nom": "Loup", "genre": "m", "tags": ["animal"]},
	"espece:ours": {"_id": "espece:ours", "nom": "Ours", "genre": "m", "tags": ["animal"]},
	"espece:dragon": {"_id": "espece:dragon", "nom": "Dragon", "genre": "m", "tags": ["vol"]},
}
PROFILS = [
	{"_id": "profil:novice", "nom": "Novice", "niveau": 1},
	{"_id": "profil:heros", "nom": "Héros", "niveau": 5},
	{"_id": "profil:archer", "nom": "Archer", "niveau": 2, "restriction_tags": ["distance"]},
]
BASE = {"espece:loup": 30.0, "espece:ours": 45.0, "espece:dragon": 300.0}
GRADE = {None: 1.0, "profil:novice": 1.0, "profil:heros": 2.0, "profil:archer": 50.0}


def menace(espece, profil, _get):
	return BASE[espece["_id"]] * GRADE[(profil or {}).get("_id")]


def _pire(pos, lieu=LIEU, **kw):
	return traces.pire_menace(lieu, pos, ZONE_DEFS, ESPECES, PROFILS, None, menace_fn=menace, **kw)


def test_hors_zone_aucune_trace():
	assert _pire({"x": 12, "y": 12}) is None


def test_seules_les_especes_des_zones_actives():
	m = _pire({"x": 5, "y": 5})
	assert m["espece"]["_id"] == "espece:ours"   # le dragon est au marais


def test_grade_le_plus_haut_possible_sans_poids():
	"""Sans poids de grade : tous les profils COMPATIBLES peuvent sortir — l'archer, réservé au
	tag `distance`, est écarté ; le héros l'emporte."""
	m = _pire({"x": 5, "y": 5})
	assert m["profil"]["_id"] == "profil:heros" and m["potentiel"] == 90.0
	assert m["rang"] == potentiel.rang_de_potentiel(90.0)


def test_poids_de_zone_restreignent_les_grades():
	lieu = {**LIEU, "zone_influences": [{**LIEU["zone_influences"][0],
										 "profil_weights": {"profil:novice": 1}}]}
	m = _pire({"x": 5, "y": 5}, lieu=lieu)
	assert m["profil"]["_id"] == "profil:novice" and m["potentiel"] == 45.0


def test_cap_de_ville():
	m = _pire({"x": 5, "y": 5}, cap_niveau=2)
	assert m["profil"]["_id"] == "profil:novice"


def test_candidats_partages_avec_le_tirage_du_combat():
	"""Le tirage (`combat._pick_profil`) et les traces lisent `zones.profils_candidats`."""
	cands, poids = zones.profils_candidats(PROFILS, {"profil:heros": 2, "profil:inconnu": 5})
	assert [p["_id"] for p in cands] == ["profil:heros"] and poids == [2]
	cands, poids = zones.profils_candidats(PROFILS, {"profil:inconnu": 5})
	assert len(cands) == len(PROFILS) and poids is None


def test_sans_forestier_libelle_seul():
	m = _pire({"x": 5, "y": 5})
	p = traces.payload(m, None)
	assert p["cle"] == "rang|" + m["rang"]
	assert potentiel.RANG_LIBELLES[m["rang"]] in p["texte"] and "Ours" not in p["texte"]


def test_forestier_nomme_espece_et_grade():
	m = _pire({"x": 5, "y": 5})
	p = traces.payload(m, {"voc": "forestier", "prenom": "Aubin"})
	assert "Aubin" in p["texte"] and "Ours" in p["texte"] and "Héros" in p["texte"]
	assert p["espece"] == "Ours" and p["profil"] == "Héros"
	assert p["cle"] != traces.payload(m, None)["cle"]


def test_pisteur_principal_puis_compagnon():
	principal = {"voc": "guerrier", "nom": "Moi"}
	compagnon = {"voc": "forestier", "prenom": "Aubin"}
	assert traces.pisteur([principal, compagnon]) is compagnon
	assert traces.pisteur([principal]) is None
	assert traces.pisteur([{"voc": "forestier", "nom": "Moi"}, compagnon])["nom"] == "Moi"


def test_aucune_menace_aucun_bloc():
	assert traces.payload(None, {"voc": "forestier"}) is None


def test_espece_au_pluriel_accorde_le_verbe():
	m = {"espece": {"_id": "espece:fauves", "nom": "Fauves", "pluriel": True}, "profil": None,
		 "potentiel": 40.0, "rang": "E"}
	assert "des Fauves peuvent rôder" in traces.payload(m, {"voc": "forestier", "nom": "A"})["texte"]
