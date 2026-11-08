"""La route de Saint-Denis — l'escorte du rang C, 4ᵉ de la chaîne de Bouchard (Montmartre →
le Chemin du Saint → le coude → le Relais de Saint-Denis → Montmartre).

Contenu pur (`dev/gen_route_saint_denis.py` → UN fichier d'import) : on verrouille ce qu'aucun
symptôme ne trahirait en jeu — deux Bouchard à la fois ou aucun, une offre visible avant le
rang C, un relais qu'on atteint sans passer le coude, un coude qui se rouvre sur un second
serpent, un PNJ qui récite l'affaire avant qu'on la lui confie."""

import copy
import glob
import json
import os

from dev import gen_genres_especes, gen_jetons_especes
from dev import gen_route_saint_denis as gen
from models import character_stats
from utils import acces, lint_dialogues, pnj

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONS = os.path.join(RACINE, "jsons")
CONTENU = os.path.join(JSONS, "route_saint_denis_a_importer.json")

CHARTRES = "quete:escorte_montmartre_convoi_de_chartres"
REIMS = "quete:escorte_montmartre_pelerins_de_reims"
BOUCHARDS = ("pnj:bouchard_de_clignancourt", "pnj:bouchard_de_clignancourt_reims",
			 gen.BOUCHARD_PRECEDENT, gen.BOUCHARD)


def _charger(chemin):
	with open(chemin, encoding="utf-8") as f:
		return json.load(f)


def _docs():
	return {d["_id"]: d for d in _charger(CONTENU)}


def _dump():
	dumps = sorted(glob.glob(os.path.join(JSONS, "telluris-dump-*.json")))
	return {d["_id"]: d for d in _charger(dumps[-1])["docs"]}


def _perso(reussies=(), escorte=False, coude=False):
	"""Un personnage dans un état de la chaîne : quêtes réussies, escorte en cours, coude gagné."""
	actives = [{"id": gen.QUETE, "objectif": {"type": "escorte", "cible": gen.RELAIS, "quantite": 1}}] if escorte else []
	return {"quetes_actives": actives,
			"quetes_terminees": [{"id": q} for q in reussies],
			"battle_maps_gagnees": [gen.COUDE] if coude else [],
			"inventaire": []}


def _sans_db(_id):
	return None


def test_dialogues_sans_faute():
	rapport = lint_dialogues.analyser(list(_docs().values()))
	assert rapport["erreurs"] == 0 and rapport["avertissements"] == 0, rapport["trouvailles"]


def test_le_fichier_est_celui_que_produit_le_generateur():
	"""Le fichier livré suit le générateur rejoué contre le DERNIER dump (pas un état figé)."""
	assert gen.generer(_dump()) == _charger(CONTENU)


def test_toute_quete_nommee_est_une_offre():
	docs = _docs()
	# Les docs RELUS (Montmartre, Geneviève) citent déjà leurs propres quêtes : on contrôle
	# ce que la demande ajoute — les docs neufs et les nœuds `saint_denis_*` de Geneviève.
	neufs = [d for i, d in docs.items() if i not in (gen.MONTMARTRE, gen.GENEVIEVE)]
	neufs += [gen.CHOIX_GENEVIEVE, gen.NOEUDS_GENEVIEVE]
	neufs += [e for e in docs[gen.MONTMARTRE]["pnj"] if e["character"] == gen.BOUCHARD]
	cites = {m for m in json.dumps(neufs, ensure_ascii=False).split('"') if m.startswith("quete:")}
	assert cites == {gen.QUETE, gen.QUETE_PRECEDENTE}
	assert docs[gen.BOUCHARD]["services"]["escorte"]["offre"]["id"] == gen.QUETE
	assert _dump()[gen.BOUCHARD_PRECEDENT]["services"]["escorte"]["offre"]["id"] == gen.QUETE_PRECEDENTE


def test_l_offre_est_une_escorte_du_rang_c_vers_le_relais():
	offre = _docs()[gen.BOUCHARD]["services"]["escorte"]["offre"]
	assert offre["destination"] == gen.RELAIS
	assert offre["rang_min"] == {"cite": "lieu:lutecia", "rang": "C"}
	assert offre["unique"] and offre["recompenses"] == gen.RECOMPENSES
	assert "rencontre" not in offre  # les protégés partent de Montmartre, avec le joueur
	assert [p.get("se_defend", False) for p in offre["proteges"]] == [False, True, False]


def test_le_novice_ne_porte_qu_un_nom():
	"""Prénom vide : `escorte.creer_protege` recopierait le prénom dans un nom vide."""
	(ysore,) = [p for p in gen.offre_bouchard()["proteges"] if p["nom"] == "Ysoré"]
	assert ysore["prenom"] == ""


def test_un_seul_bouchard_a_montmartre_a_chaque_etape():
	"""Chartres → Reims → route silencieuse → Saint-Denis : à chaque étape, exactement le
	Bouchard de la quête suivante (la variante précédente part dès sa quête réussie)."""
	lieu = _docs()[gen.MONTMARTRE]
	etapes = [
		((), "pnj:bouchard_de_clignancourt"),
		((CHARTRES,), "pnj:bouchard_de_clignancourt_reims"),
		((CHARTRES, REIMS), gen.BOUCHARD_PRECEDENT),
		((CHARTRES, REIMS, gen.QUETE_PRECEDENTE), gen.BOUCHARD),
		((CHARTRES, REIMS, gen.QUETE_PRECEDENTE, gen.QUETE), gen.BOUCHARD),
	]
	for reussies, attendu in etapes:
		perso = _perso(reussies)
		presents = [e["character"] for e in pnj.entrees_pnj(
			lieu, condition_fn=lambda conds: acces.clauses_remplies(perso, conds, _sans_db))]
		assert [p for p in presents if p in BOUCHARDS] == [attendu], reussies


def test_montmartre_garde_ses_autres_pnj():
	"""Transformation du doc RELU : seules les entrées des deux Bouchard bougent."""
	avant = _dump()[gen.MONTMARTRE]
	apres = gen.montmartre(avant)
	garde = lambda doc: [e for e in doc["pnj"] if e["character"] not in (gen.BOUCHARD_PRECEDENT, gen.BOUCHARD)]
	assert garde(apres) == garde(avant)
	assert {k: v for k, v in apres.items() if k != "pnj"} == {k: v for k, v in avant.items() if k not in ("pnj", "_rev")}
	assert gen.montmartre(apres) == apres  # idempotent


def test_genevieve_garde_ses_services_et_choix():
	avant = _dump()[gen.GENEVIEVE]
	apres = gen.genevieve(avant)
	assert apres["services"] == avant["services"]
	for nid, noeud in avant["dialogue"]["noeuds"].items():
		ids_avant = [c["id"] for c in noeud.get("choix", [])]
		ids_apres = [c["id"] for c in apres["dialogue"]["noeuds"][nid].get("choix", [])]
		assert [i for i in ids_apres if i in ids_avant] == ids_avant, nid
		if ids_avant:
			assert ids_apres[-1] == ids_avant[-1], nid
	assert gen.genevieve(apres) == apres  # idempotent


def test_les_scenes_de_la_route_silencieuse_suivent_bouchard():
	"""Recopiées du doc précédent relu : la variante précédente a quitté Montmartre."""
	ancien = _dump()[gen.BOUCHARD_PRECEDENT]["dialogue"]["noeuds"]
	neuf = _docs()[gen.BOUCHARD]["dialogue"]["noeuds"]
	for nid in ("route_rapport", "passe", "principes"):
		assert neuf[nid] == ancien[nid], nid
	assert neuf["route_suite"]["texte"] == ancien["route_suite"]["texte"]


def _accueil(pnj_id, actives=(), reussies=(), flags=None):
	contexte = {"quetes_actives": set(actives), "quetes_reussies": set(reussies), "flags": flags or {}}
	doc = _docs()[pnj_id]
	return {c["id"] for c in pnj._choix_visibles(doc, doc["dialogue"]["noeud_depart"], contexte)}


def test_hilduin_dans_les_trois_etats():
	assert _accueil(gen.HILDUIN) == {"bonjour", "denis", "fin"}
	assert _accueil(gen.HILDUIN, actives=[gen.QUETE]) == {"convoi", "denis", "fin"}
	assert _accueil(gen.HILDUIN, reussies=[gen.QUETE]) == {"apres", "denis", "fin"}


def test_genevieve_ne_parle_de_la_route_que_pendant_et_apres():
	neufs = {c["id"] for c in gen.CHOIX_GENEVIEVE}
	assert not (_accueil(gen.GENEVIEVE) & neufs)
	assert _accueil(gen.GENEVIEVE, actives=[gen.QUETE]) & neufs == {"saint_denis_pendant"}
	assert _accueil(gen.GENEVIEVE, reussies=[gen.QUETE]) & neufs == {"saint_denis_apres"}


def test_perrine_ouvre_le_coude_puis_le_dit_libre():
	assert _accueil(gen.PERRINE, flags={"acces_ouvrable": True}) == {"ici", "fin"}
	assert _accueil(gen.PERRINE, flags={"acces_libere": True}) == {"libre", "fin"}
	assert _docs()[gen.PERRINE]["services"]["acces"]["lieu"] == gen.COUDE


def test_conditions_de_presence_et_d_acces_lisibles():
	for doc in _docs().values():
		if doc.get("type") != "lieu":
			continue
		assert acces.conditions_invalides(doc) == [], doc["_id"]
		assert acces.conditions_pnj_invalides(doc) == [], doc["_id"]


def test_le_chemin_n_existe_que_pendant_l_escorte():
	chemin = _docs()[gen.CHEMIN]
	assert not acces.acces_autorise(_perso(), chemin, _sans_db)[0]
	assert acces.acces_autorise(_perso(escorte=True), chemin, _sans_db)[0]
	assert not acces.acces_autorise(_perso(reussies=[gen.QUETE]), chemin, _sans_db)[0]


def test_le_coude_ne_s_ouvre_qu_une_fois_escorte_en_route():
	coude = _docs()[gen.COUDE]
	assert not acces.acces_autorise(_perso(), coude, _sans_db)[0]
	assert acces.acces_autorise(_perso(escorte=True), coude, _sans_db)[0]
	assert not acces.acces_autorise(_perso(escorte=True, coude=True), coude, _sans_db)[0]


def test_le_relais_ne_s_atteint_qu_apres_le_coude():
	"""Sinon on déposerait le convoi sans jamais passer le serpent."""
	relais = _docs()[gen.RELAIS]
	assert not acces.acces_autorise(_perso(escorte=True), relais, _sans_db)[0]
	assert acces.acces_autorise(_perso(escorte=True, coude=True), relais, _sans_db)[0]


def test_le_coude_garantit_un_seul_serpent_avec_les_proteges():
	docs = _docs()
	donjon = docs[gen.DONJON]
	assert donjon["portail"] == gen.CHEMIN
	(salle,) = donjon["battle_maps"]
	assert salle["lieu"] == gen.COUDE and salle["especes"] == [gen.SERPENT] and salle["nb_monstres"] == 1
	# Escorter, c'est protéger : les trois voyageurs entrent dans le combat.
	assert not docs[gen.COUDE].get("proteges_restent_dehors")


def test_le_serpent_est_une_menace_du_rang_c():
	"""Potentiel aux deux grades de la salle entre les planchers C et B, relus au module."""
	from utils import potentiel
	vue = {**_dump(), **_docs()}
	get = lambda i: copy.deepcopy(vue.get(i))
	planchers = character_stats.QUETE_RANG_POTENTIEL_MIN
	profils = [p for p in vue.values() if p.get("type") == "profil"]
	(salle,) = vue[gen.DONJON]["battle_maps"]
	grades = [p["_id"] for p in profils if salle["niveau_min"] <= p.get("niveau", 0) <= salle["niveau_max"]
			  and not p.get("restriction_tags")]
	assert grades
	for profil in grades:
		valeur, _fuite = potentiel.potentiel_menace(gen.SERPENT, profil, get)
		assert planchers["C"] <= valeur < planchers["B"], (profil, valeur)


def test_l_espece_est_dans_les_tables_exhaustives():
	assert gen.SLUG_SERPENT in gen_jetons_especes.TABLE
	assert gen.SLUG_SERPENT in gen_genres_especes.MASCULINS
	espece = _docs()[gen.SERPENT]
	assert espece["genre"] == "m" and "nom_propre" not in espece
	carcasse = _docs()["item:" + gen.SLUG_SERPENT]
	assert carcasse["source_espece"] == gen.SERPENT and carcasse["decoupe"]


def test_le_coude_est_une_salle_jouable():
	coude = _docs()[gen.COUDE]
	cells = coude["cells"]
	w, h = coude["dimensions"]["x"], coude["dimensions"]["y"]
	assert len(cells) == h and all(len(r) == w for r in cells)
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


def test_le_chemin_et_le_relais_sur_des_cases_libres_de_la_carte_de_france():
	docs, base = _docs(), _dump()
	liens = (gen.LIEN_CHEMIN, gen.LIEN_RELAIS)
	prises = {tuple(n["pos"]) for d in base.values()
			  if d.get("type") == "connection" and d.get("_id") not in liens
			  for n in d.get("nodes", []) if n.get("lieu") == "lieu:france"}
	positions = []
	for lien in liens:
		(noeud,) = [n for n in docs[lien]["nodes"] if n["lieu"] == "lieu:france"]
		x, y = noeud["pos"]
		assert base["lieu:france"]["cells"][y][x] >= 1, lien
		assert (x, y) not in prises, lien
		positions.append((x, y))
	assert len(set(positions)) == len(positions)


def test_images_presentes():
	docs = _docs()
	ressources = os.path.join(RACINE, "templates", "resources")
	chemins = [
		os.path.join(ressources, "battle_maps", docs[gen.COUDE]["image"]),
		os.path.join(ressources, "towns", docs[gen.CHEMIN]["image"]),
		os.path.join(ressources, "towns", docs[gen.RELAIS]["image"]),
		os.path.join(ressources, "monsters", docs[gen.SERPENT]["image"]),
	]
	for d in docs.values():
		if d.get("type") == "pnj":
			chemins.append(os.path.join(ressources, "pnj", d["portrait"]))
		for e in d.get("pnj") or [] if d.get("type") == "lieu" else []:
			chemins.append(os.path.join(ressources, "pnj", e["portrait"]))
	for p in chemins:
		assert os.path.exists(p), p
