"""Épreuve du rang C de Lutecia — Maëlys → Aélis → le portail de Jumièges.

Contenu pur (`dev/gen_quete_rang_c_jumieges.py` → UN fichier d'import) : on verrouille ici ce
qu'aucun symptôme ne trahirait en jeu — un id de quête mal recopié cache un choix pour
toujours (fail-closed), une barrière mal posée ouvre les Archives avant la nef, une grille
trouée enferme le groupe, et un ancien fichier source réimporté défait la quête."""

import glob
import json
import os

from utils import acces, chasse, lint_dialogues, transport

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONS = os.path.join(RACINE, "jsons")
CONTENU = os.path.join(JSONS, "quete_rang_c_abbaye_de_jumieges_a_importer.json")
SOURCES = [os.path.join(JSONS, "maelys_maitresse_de_guilde_a_importer.json"),
		   os.path.join(JSONS, "cour_des_arches_lutecia_a_importer.json")]
RESSOURCES = os.path.join(RACINE, "templates", "resources")

LETTRE = "quete:rang_c_lettre_a_l_institut"
ESCORTE = "quete:escorte_aelis_abbaye_de_jumieges"
ARCHIVES = "lieu:les_archives_des_seuils"
NEF = "lieu:nef_de_l_abbaye_de_jumieges"
BUREAU = "lieu:le_grand_relais_des_frontieres_bureau_du_maitre"


def _charger(chemin):
	with open(chemin, encoding="utf-8") as f:
		return json.load(f)


def _docs():
	return {d["_id"]: d for d in _charger(CONTENU)}


def _dump():
	dumps = sorted(glob.glob(os.path.join(JSONS, "telluris-dump-*.json")))
	return {d["_id"]: d for d in _charger(dumps[-1])["docs"]}


def _escorte_active():
	return {"id": ESCORTE, "type_quete": "escorte",
			"objectif": {"type": "escorte", "cible": ARCHIVES}}


def test_dialogues_sans_faute():
	rapport = lint_dialogues.analyser(list(_docs().values()))
	assert rapport["erreurs"] == 0 and rapport["avertissements"] == 0, rapport["trouvailles"]


def test_un_doc_partage_avec_un_fichier_source_y_est_identique():
	"""Le fichier unique ET les anciens fichiers source portent les docs retouchés : réimporter
	l'un des anciens ne doit jamais défaire la quête."""
	docs = _docs()
	communs = 0
	for chemin in SOURCES:
		for d in _charger(chemin):
			if d["_id"] in docs:
				communs += 1
				assert d == docs[d["_id"]], (chemin, d["_id"])
	# pnj:maelys, l'Aélis de la Cour et la Cour elle-même.
	assert communs == 3


def test_les_ids_de_quete_sont_ceux_des_offres():
	docs = _docs()
	offre_lettre = transport.offre_spec(docs["pnj:maelys"])
	offre_escorte = docs["pnj:aelis_de_montfaucon_cour_des_arches"]["services"]["escorte"]["offre"]
	assert offre_lettre["id"] == LETTRE and offre_escorte["id"] == ESCORTE
	texte = json.dumps(list(docs.values()), ensure_ascii=False)
	# Toute quête nommée par une condition est l'une des deux offres.
	for qid in {LETTRE, ESCORTE}:
		assert qid in texte
	cites = {m for m in texte.split('"') if m.startswith("quete:")}
	assert cites == {LETTRE, ESCORTE}
	# La lettre va à la Cour, où l'Aélis destinataire est présente ; l'escorte finit aux Archives.
	assert offre_lettre["destination"] == "lieu:la_cour_des_arches"
	assert offre_escorte["destination"] == ARCHIVES


def test_conditions_de_presence_et_d_acces_lisibles():
	for doc in _docs().values():
		if doc.get("type") != "lieu":
			continue
		assert acces.conditions_invalides(doc) == [], doc["_id"]
		assert acces.conditions_pnj_invalides(doc) == [], doc["_id"]


def test_presences_d_aelis_selon_l_etat_de_la_mission():
	"""Exactement UNE Aélis à la fois : à la Cour avant, devant l'abbaye pendant (elle vous
	suit), aux Archives après."""
	docs = _docs()
	lieux = {"cour": docs["lieu:la_cour_des_arches"], "abbaye": docs["lieu:abbaye_de_jumieges"],
			 "archives": docs[ARCHIVES]}

	def presente(character, lieu):
		return all(acces.clauses_remplies(character, e.get("conditions") or [], lambda _id: None)
				   for e in lieu["pnj"])

	avant = {"quetes_actives": [], "quetes_terminees": []}
	pendant = {"quetes_actives": [_escorte_active()], "quetes_terminees": []}
	apres = {"quetes_actives": [], "quetes_terminees": [{"id": ESCORTE}]}
	attendu = {"avant": "cour", "pendant": "abbaye", "apres": "archives"}
	for etat, c in (("avant", avant), ("pendant", pendant), ("apres", apres)):
		assert [k for k, l in lieux.items() if presente(c, l)] == [attendu[etat]], etat


def test_archives_fermees_tant_que_la_nef_n_est_pas_gagnee():
	"""La dépose d'Aélis (destination de l'escorte) exige d'être passé par Jumièges ; la nef ne
	s'ouvre qu'escorte en cours, et plus après la victoire."""
	docs = _docs()
	c = {"quetes_actives": [_escorte_active()], "battle_maps_gagnees": []}
	assert acces.acces_autorise(c, docs[NEF], lambda _id: None)[0]
	assert not acces.acces_autorise(c, docs[ARCHIVES], lambda _id: None)[0]
	c["battle_maps_gagnees"] = [NEF]
	assert not acces.acces_autorise(c, docs[NEF], lambda _id: None)[0]
	assert acces.acces_autorise(c, docs[ARCHIVES], lambda _id: None)[0]
	sans_mission = {"quetes_actives": [], "battle_maps_gagnees": []}
	assert not acces.acces_autorise(sans_mission, docs[NEF], lambda _id: None)[0]


def test_la_nef_est_une_salle_de_donjon_jouable():
	docs = _docs()
	nef = docs[NEF]
	donjon = docs["donjon:abbaye_de_jumieges"]
	assert donjon["portail"] == "lieu:abbaye_de_jumieges"
	assert [b["lieu"] for b in donjon["battle_maps"]] == [NEF]
	assert docs["pnj:aelis_de_montfaucon_jumieges"]["services"]["acces"]["lieu"] == NEF
	base = _dump()
	for b in donjon["battle_maps"]:
		assert all(e in base for e in b["especes"])
	cells = nef["cells"]
	w, h = nef["dimensions"]["x"], nef["dimensions"]["y"]
	assert len(cells) == h and all(len(r) == w for r in cells)
	# Toutes les cases praticables en combat (>= 1, hors falaise) se rejoignent : le
	# placement tire le groupe ET les monstres dans la région du central.
	ok = lambda x, y: 0 <= x < w and 0 <= y < h and cells[y][x] >= 1 and cells[y][x] != 3
	praticables = {(x, y) for y in range(h) for x in range(w) if ok(x, y)}
	depart = next(iter(sorted(praticables)))
	vues, pile = {depart}, [depart]
	while pile:
		x, y = pile.pop()
		for dx in (-1, 0, 1):
			for dy in (-1, 0, 1):
				n = (x + dx, y + dy)
				if n in praticables and n not in vues:
					vues.add(n)
					pile.append(n)
	assert vues == praticables


def test_images_presentes():
	docs = _docs()
	chemins = [
		os.path.join(RESSOURCES, "battle_maps", docs[NEF]["image"]),
		os.path.join(RESSOURCES, "towns", docs[ARCHIVES]["image"]),
		os.path.join(RESSOURCES, "towns", docs["lieu:abbaye_de_jumieges"]["image"]),
		os.path.join(RESSOURCES, "towns", docs["lieu:la_cour_des_arches"]["image"]),
	]
	for d in docs.values():
		for e in d.get("pnj") or []:
			chemins.append(os.path.join(RESSOURCES, "pnj", e["portrait"]))
		if d.get("type") == "pnj":
			chemins.append(os.path.join(RESSOURCES, "pnj", d["portrait"]))
	for p in chemins:
		assert os.path.exists(p), p
	# La Cour garde son image SANS Aélis ; l'image où elle pose devant l'Institut est le
	# portrait de son dialogue, pas l'image du lieu.
	entree = docs["lieu:la_cour_des_arches"]["pnj"][0]
	assert "image" not in entree and entree["portrait"] != docs["lieu:la_cour_des_arches"]["image"]


def test_le_rapport_a_maelys_monte_au_rang_c():
	docs = _docs()
	spec = transport.offre_spec(docs["pnj:maelys"])
	bureau = {"_id": BUREAU, "lieu_parent": "lieu:lutecia", "label": "Bureau"}
	cour = docs["lieu:la_cour_des_arches"]
	get = {BUREAU: bureau, cour["_id"]: cour, "lieu:lutecia": {"_id": "lieu:lutecia"},
		   "item:lettre_de_mission_de_la_guilde": docs["item:lettre_de_mission_de_la_guilde"]}.get
	offre = transport.generer_transport_authore(spec, bureau, lambda *a, **k: [], get,
												 rand_fn=lambda: 0.0)
	assert offre["recompenses"]["rang_guilde"] == {"cite": "lieu:lutecia", "rang": "C"}
	c = {"rangs_guilde": {"lieu:lutecia": "D"}, "inventaire": [], "quetes_actives": [],
		 "quetes_terminees": [], "xp_total": 0, "cuivre": 0}
	q = transport.accepter_transport(c, offre)
	assert transport.livrer_transport(c, q)
	transport.livrer_en_attente_de_retour(c, q, dict(cour), get, lambda d: d)
	assert transport.retour_attendu(c, BUREAU) is q
	transport.rapporter_transport(c, q, get, lambda d: d)
	assert chasse.rang_de(c, "lieu:lutecia") == "C"
