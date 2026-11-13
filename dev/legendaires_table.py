"""Données des chasses légendaires (pur, sans import) — `docs/conception_trophees_legendaires.md`.

Relu par DEUX générateurs :
  · dev/gen_fabrication_matieres.py (sa table `MATIERES` est la vérité des blocs `fabrication` :
    les parties et matières nommées d'ici y entrent par `entrees_fabrication`, sinon sa relance
    les listerait en orphelins) ;
  · dev/gen_trophees_legendaires.py (items, recettes, panoplies, mur, collectionneur).

`PALIER` et les parties sont relevés sur le dump du 13/11/2026 (`gen_trophees.palier_espece`,
parties rare+ sans bloc). Un MORCEAU porte le MÊME bloc que sa partie (décision de l'Auteur,
13/11 : « un morceau suffit ») — dérogation assumée à la règle « un palier de moins ».
"""

# espece → (palier, thème, « du »-forme, matière : (slug, nom, icône, sorte), évocation)
# Sorte de matière : ecailles · cuir · peau · plumes · soie · os · cendre (maison et familles).
ESPECES = {
	"espece:bete_du_gevaudan": (3, "bete", "de la Bête du Gévaudan",
		("pelage_bete_du_gevaudan", "Pelage de la Bête du Gévaudan", "🐺", "cuir"),
		"Loup, loup-garou ou autre chose : dans le Gévaudan, personne n'a jamais su."),
	"espece:cath_palug": (3, "bete", "de Cath Palug",
		("fourrure_cath_palug", "Fourrure de Cath Palug", "🐈‍⬛", "cuir"),
		"Le chat monstrueux d'Anglesey, né, dit-on, d'une truie de Cornouailles."),
	"espece:geant_de_ad": (3, "terre", "du Géant de ʿĀd",
		("os_geant_de_ad", "Os du Géant de ʿĀd", "🦴", "os"),
		"Le peuple de ʿĀd bâtissait des colonnes à sa taille ; le désert en a gardé les os."),
	"espece:geant_du_mont_saint_michel": (3, "terre", "du Géant du Mont-Saint-Michel",
		("os_geant_du_mont_saint_michel", "Os du Géant du Mont-Saint-Michel", "🦴", "os"),
		"Arthur l'aurait affronté sur le mont, au récit des vieux conteurs bretons."),
	"espece:hydre": (3, "venin", "de l'Hydre",
		("ecailles_hydre", "Écailles de l'Hydre", "🐍", "ecailles"),
		"Coupez une tête, deux repoussent : on ne vient à bout d'une hydre que par le feu."),
	"espece:tarasque": (3, "terre", "de la Tarasque",
		("carapace_tarasque", "Éclats de carapace de la Tarasque", "🐢", "ecailles"),
		"Les riverains du Rhône jurent que rien de ce qui l'a frappée ne l'a jamais percée."),
	"espece:archange_de_l_ordre": (4, "celeste", "de l'Archange de l'Ordre",
		("plumes_archange_de_l_ordre", "Plumes de l'Archange de l'Ordre", "🪶", "plumes"),
		"Ce qui vient du ciel ne dit pas d'où il vient ; ses plumes ne ternissent pas."),
	"espece:archange_du_savoir": (4, "celeste", "de l'Archange du Savoir",
		("plumes_archange_du_savoir", "Plumes de l'Archange du Savoir", "🪶", "plumes"),
		"Les érudits qui en possèdent une affirment lire plus vite à sa lueur. D'autres en rient."),
	"espece:balaur": (4, "feu", "du Balaur",
		("ecailles_balaur", "Écailles du Balaur", "🐉", "ecailles"),
		"Le dragon des Carpates aux têtes multiples : c'est un balaur, sorti d'un donjon, qui ravagea les terres de Vlad."),
	"espece:bete_glatissante": (4, "bete", "de la Bête glatissante",
		("peau_bete_glatissante", "Peau de la Bête glatissante", "🦌", "cuir"),
		"Pellinore l'a traquée toute sa vie ; de son ventre montait le bruit d'une meute."),
	"espece:demon_majeur_de_la_destinee": (4, "infernal", "du Démon majeur de la Destinée",
		("cendre_demon_destinee", "Cendre du Démon majeur de la Destinée", "🌑", "cendre"),
		"Une poignée de cendre tiède qui ne retombe jamais tout à fait au fond du flacon."),
	"espece:demon_majeur_de_la_destruction": (4, "infernal", "du Démon majeur de la Destruction",
		("cendre_demon_destruction", "Cendre du Démon majeur de la Destruction", "🌋", "cendre"),
		"Elle noircit le verre qui la contient ; les alchimistes la manient avec des pinces."),
	"espece:dragon": (4, "feu", "du Dragon",
		("ecailles_dragon", "Écailles de Dragon", "🐲", "ecailles"),
		"Sigurd se serait baigné dans le sang d'un dragon ; ses écailles, elles, se portent."),
	"espece:dragon_hydre": (4, "venin", "du Dragon-hydre",
		("ecailles_dragon_hydre", "Écailles du Dragon-hydre", "🐲", "ecailles"),
		"Plusieurs cous, un seul souffle : ses écailles repoussent quand on les arrache."),
	"espece:grand_phenix": (4, "feu", "du Grand Phénix",
		("plumes_grand_phenix", "Plumes du Grand Phénix", "🔥", "plumes"),
		"Elles restent tièdes, et nul ne sait si elles se consumeront un jour pour renaître ailleurs."),
	"espece:grootslang": (4, "venin", "du Grootslang",
		("ecailles_grootslang", "Écailles du Grootslang", "🐍", "ecailles"),
		"Le serpent-éléphant des gouffres du Richtersveld, gardien de diamants, disent les chercheurs."),
	"espece:illuyanka": (4, "terre", "d'Illuyanka",
		("ecailles_illuyanka", "Écailles d'Illuyanka", "🐉", "ecailles"),
		"Le serpent d'Anatolie qui vainquit le dieu de l'orage avant d'être pris au piège d'un festin."),
	"espece:kraken": (4, "eau", "du Kraken",
		("peau_kraken", "Peau du Kraken", "🐙", "peau"),
		"Les marins de Norvège l'ont pris pour une île ; certains y ont même accosté."),
	"espece:ladon": (4, "venin", "de Ladon",
		("ecailles_ladon", "Écailles de Ladon", "🐍", "ecailles"),
		"Le gardien du jardin des Hespérides, né de Cétô ou d'Échidna : les récits se disputent."),
	"espece:polar_kraken": (4, "gel", "du Kraken polaire",
		("peau_kraken_polaire", "Peau du Kraken polaire", "🦑", "peau"),
		"Pris sous la banquise, il remonte quand la glace craque, et la mer gèle sur son passage."),
	"espece:serpent_de_marcel": (4, "eau", "du Serpent de Marcel",
		("ecailles_serpent_de_marcel", "Écailles du Serpent de Marcel", "🐍", "ecailles"),
		"Le serpent qui terrorisait Lutecia jusqu'à ce que l'évêque Marcel le chasse, selon les récits du faubourg."),
	"espece:twrch_trwyth": (4, "bete", "de Twrch Trwyth",
		("soies_twrch_trwyth", "Soies de Twrch Trwyth", "🐗", "cuir"),
		"Le sanglier-roi qu'Arthur poursuivit d'Irlande en Cornouailles, entre ses oreilles un peigne et des ciseaux."),
	"espece:vers_des_sables": (4, "terre", "des Vers des Sables",
		("peau_vers_des_sables", "Peau des Vers des Sables", "🪱", "peau"),
		"Le désert tremble avant qu'ils ne surgissent ; leur peau ne craint ni le sable ni le soleil."),
	"espece:avatar": (5, "celeste", "de l'Avatar",
		("poussiere_avatar", "Poussière de l'Avatar", "✨", "cendre"),
		"Ce qui reste d'un dieu incarné tient dans une fiole, et pèse plus lourd qu'il ne devrait."),
	"espece:bete_de_l_apocalypse": (5, "infernal", "de la Bête de l'Apocalypse",
		("cuir_bete_apocalypse", "Cuir de la Bête de l'Apocalypse", "🐲", "cuir"),
		"Sept têtes, dix cornes, disent les visions ; le cuir, lui, ne ment pas sur sa dureté."),
	"espece:dragon_blanc": (5, "gel", "du Dragon blanc",
		("ecailles_dragon_blanc", "Écailles du Dragon blanc", "❄️", "ecailles"),
		"Le dragon blanc des récits bretons, que Merlin vit combattre le rouge sous la colline."),
	"espece:dragon_empereur": (5, "terre", "du Dragon Empereur",
		("ecailles_dragon_empereur", "Écailles du Dragon Empereur", "🐉", "ecailles"),
		"Plus vieux que les Anthropes, disent certains ; d'autres jurent qu'il n'en reste aucun."),
	"espece:dragon_rouge": (5, "feu", "du Dragon rouge",
		("ecailles_dragon_rouge", "Écailles du Dragon rouge", "🔥", "ecailles"),
		"Le dragon rouge que Merlin vit vaincre le blanc sous la colline de Dinas Emrys."),
	"espece:grand_dragon": (5, "feu", "du Grand Dragon",
		("ecailles_grand_dragon", "Écailles du Grand Dragon", "🐲", "ecailles"),
		"Fáfnir couvait son or ; celui-ci couvait des donjons, à en croire ceux qui en sont revenus."),
	"espece:gwyn_ap_nudd": (5, "fee", "de Gwyn ap Nudd",
		("brume_gwyn_ap_nudd", "Brume de Gwyn ap Nudd", "🌫️", "soie"),
		"Le roi de l'Annwn mène la Chasse sauvage ; ce qu'il laisse derrière lui se tisse comme de la soie."),
	"espece:leviathan": (5, "eau", "du Léviathan",
		("ecailles_leviathan", "Écailles du Léviathan", "🌊", "ecailles"),
		"Sa carapace est faite de boucliers serrés, dit le vieux texte, et le fer n'y entre pas."),
	"espece:prince_demon": (5, "infernal", "du Prince Démon",
		("cendre_prince_demon", "Cendre du Prince Démon", "🔥", "cendre"),
		"Une cendre qui sent le soufre, et que la lumière du jour ne parvient pas à éclaircir."),
	"espece:seraphin": (5, "celeste", "du Séraphin",
		("plumes_seraphin", "Plumes du Séraphin", "🪽", "plumes"),
		"Six ailes, disent les prophètes : deux pour voler, deux pour se voiler la face, deux pour les pieds."),
	"espece:yamata_no_orochi": (5, "venin", "de Yamata no Orochi",
		("ecailles_yamata_no_orochi", "Écailles de Yamata no Orochi", "🐍", "ecailles"),
		"Huit têtes, huit queues, enivrées par Susanoo à Izumo ; dans l'une d'elles dormait une épée."),
	"espece:zmey_gorynych": (5, "feu", "de Zmeï Gorynytch",
		("ecailles_zmey_gorynych", "Écailles de Zmeï Gorynytch", "🐉", "ecailles"),
		"Le dragon à trois têtes du pont Kalinov, sur la rivière de feu des contes russes."),
}

# Parties rare+ sans bloc (dump du 13/11) : espece → [(partie, morceau ?)].
PARTIES = {
	"espece:bete_du_gevaudan": ["corps", "corps*", "patte", "queue", "tete"],
	"espece:cath_palug": ["corps", "corps*", "patte", "queue", "tete"],
	"espece:geant_de_ad": ["bras", "corps", "corps*", "jambe", "jambe*", "tete"],
	"espece:geant_du_mont_saint_michel": ["bras", "corps", "corps*", "jambe", "jambe*", "tete"],
	"espece:hydre": ["corps", "corps*", "patte", "patte*", "queue", "queue*", "tete*"],
	"espece:tarasque": ["corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:archange_de_l_ordre": ["corps", "jambe"],
	"espece:archange_du_savoir": ["bras", "corps", "jambe"],
	"espece:balaur": ["aile", "aile*", "corps", "corps*", "patte", "queue", "queue*", "tete", "tete*"],
	"espece:bete_glatissante": ["corps", "corps*", "queue", "tete"],
	"espece:demon_majeur_de_la_destinee": ["bras", "corps", "jambe", "tete"],
	"espece:demon_majeur_de_la_destruction": ["bras", "corps", "corps*", "jambe", "tete"],
	"espece:dragon": ["aile", "corps", "corps*", "patte", "queue", "tete"],
	"espece:dragon_hydre": ["corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:grand_phenix": ["corps", "corps*", "patte", "queue", "tete"],
	"espece:grootslang": ["corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:illuyanka": ["corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:kraken": ["corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:ladon": ["corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:polar_kraken": ["corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:serpent_de_marcel": ["corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:twrch_trwyth": ["corps", "corps*", "queue", "queue*", "tete", "tete*"],
	"espece:vers_des_sables": ["corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:avatar": ["corps", "jambe"],
	"espece:bete_de_l_apocalypse": ["corps", "corps*"],
	"espece:dragon_blanc": ["aile", "aile*", "corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:dragon_empereur": ["aile", "aile*", "corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:dragon_rouge": ["aile", "aile*", "corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:grand_dragon": ["aile", "aile*", "corps", "corps*", "patte", "queue", "queue*", "tete", "tete*"],
	"espece:gwyn_ap_nudd": ["bras", "corps", "jambe", "tete"],
	"espece:leviathan": ["corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:prince_demon": ["bras", "corps", "corps*", "jambe", "jambe*", "tete"],
	"espece:seraphin": ["aile", "bras", "corps", "corps*", "jambe", "tete"],
	"espece:yamata_no_orochi": ["corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
	"espece:zmey_gorynych": ["aile", "aile*", "corps", "corps*", "patte", "patte*", "queue", "queue*", "tete", "tete*"],
}

# Caractéristiques et débuff d'arme d'un thème. Jamais de V : la Vitesse ne se cumule pas,
# elle a sa propre table (dev/gen_vitesse_matieres.py).
THEMES = {
	"feu": ("F", "Vol", "R"),
	"gel": ("R", "Vol", "Ag"),
	"eau": ("R", "Ag", "Ag"),
	"venin": ("Ag", "R", None),          # None : le débuff d'arme est un POISON
	"celeste": ("Vol", "Int", "Vol"),
	"infernal": ("F", "Vol", "Vol"),
	"terre": ("R", "F", "Ag"),
	"bete": ("F", "Ag", "R"),
	"fee": ("Int", "Cha", "Vol"),
}

# Cible de score d'une PARTIE par palier (dans le budget de gen_fabrication_matieres.PALIERS) ;
# une matière nommée vaut deux points de moins (≈ 80 %), toujours dans le budget.
CIBLE = {3: 7, 4: 11, 5: 16}
CIBLE_MATIERE = {3: 6, 4: 10, 5: 14}
PLAFOND_CARAC = 6
PLAFOND_DEGATS = 10

TAG_ARME, TAG_ARMURE = "fabrication_arme", "fabrication_armure"
TAG_CATA, TAG_CONSO = "fabrication_catalyseur", "fabrication_consommable"
TAG_METAL, TAG_CUIR, TAG_TISSU = ("fabrication_armure_metal", "fabrication_armure_cuir",
								  "fabrication_armure_tissu")

# Matériau des ailes et des corps selon la sorte de matière de l'espèce.
MATERIAU_SORTE = {"ecailles": [TAG_METAL, TAG_CUIR], "cuir": [TAG_CUIR], "peau": [TAG_CUIR],
				  "plumes": [TAG_TISSU], "soie": [TAG_TISSU], "os": [TAG_METAL], "cendre": [TAG_TISSU]}

# Fragment de nom de la pièce façonnée, par partie (sorte pour le corps).
NOM_PARTIE = {"tete": "aux Crocs", "patte": "à la Griffe", "bras": "au Poing", "jambe": "à la Foulée",
			  "queue": "à l'Épine", "aile": "à l'Aile"}
NOM_SORTE = {"ecailles": "aux Écailles", "cuir": "au Cuir", "peau": "à la Peau", "plumes": "aux Plumes",
			 "soie": "à la Brume", "os": "aux Os", "cendre": "à la Cendre"}


def _score(mods: dict, conso: bool = False) -> float:
	"""Miroir de gen_fabrication_matieres.score_matiere (vérifié par lui à la relance)."""
	poids = {"bonus_degats": 1, "bonus_cc": 1, "bonus_cd": 1, "bonus_pa": 1, "bonus_initiative": 1,
			 "bonus_pm": 0.5, "bonus_pv": 0.5}
	s = sum(mods.get(k, 0) * w for k, w in poids.items())
	s += sum((mods.get("bonus") or {}).values())
	eff = mods.get("effets") or {}
	duree = eff.get("duree", 0)
	for k in ("regen_pv", "regen_pm"):
		v = eff.get(k, 0)
		s += abs(v) * duree / 2 if v < 0 else 2 * v
	s += eff.get("esquive", 0) + eff.get("canalisation", 0)
	s += sum(abs(v) * duree / 2 if v < 0 else v for v in (eff.get("buffs") or {}).values())
	if conso:
		s += (max(0, eff.get("pv", 0)) + max(0, eff.get("pm", 0))) / 5
	return s


def _caracs(theme: str, palier: int) -> dict:
	c1, c2, _deb = THEMES[theme]
	return {c1: min(PLAFOND_CARAC, palier - 1), c2: max(1, palier - 3)}


def _arme_effets(theme: str, palier: int) -> dict:
	_c1, _c2, deb = THEMES[theme]
	if deb is None:
		return {"regen_pv": -(palier - 1), "duree": 2}        # poison : (p−1) × 2 / 2
	return {"buffs": {deb: -(1 if palier < 5 else 2)}, "duree": 2}


def _completer(mods: dict, cible: float, cle: str, poids: float, plafond=None, conso=False) -> dict:
	"""Comble l'écart à la cible sur `cle` (points entiers)."""
	ecart = cible - _score(mods, conso)
	n = int(round(ecart / poids))
	if plafond is not None:
		n = min(n, plafond - mods.get(cle, 0))
	if n > 0:
		mods[cle] = mods.get(cle, 0) + n
	return mods


def mods_partie(partie: str, theme: str, palier: int, sorte: str) -> tuple[dict, list]:
	"""(modificateurs, tags fabrication_*) d'une partie — score visé `CIBLE[palier]`."""
	cible = CIBLE[palier]
	venin = THEMES[theme][2] is None
	if partie == "tete":
		mods = {"bonus": _caracs(theme, palier), "effets": _arme_effets(theme, palier)}
		mods = _completer(mods, cible, "bonus_degats", 1, PLAFOND_DEGATS)
		return mods, [TAG_ARME] if venin else [TAG_ARME, TAG_ARMURE]
	if partie in ("patte", "bras"):
		mods = {"bonus": {THEMES[theme][0]: min(PLAFOND_CARAC, palier - 1)}, "bonus_cc": 1 if palier < 4 else 2}
		return _completer(mods, cible, "bonus_degats", 1, PLAFOND_DEGATS), [TAG_ARME]
	if partie == "queue":
		if venin:
			mods = {"effets": {"regen_pv": -palier, "duree": palier - 1}}   # dard : venin d'abord
			return _completer(mods, cible, "bonus_degats", 1, PLAFOND_DEGATS), [TAG_ARME]
		mods = {"bonus_cd": 1 if palier < 4 else 2, "effets": _arme_effets(theme, palier),
				"bonus": {THEMES[theme][1]: max(1, palier - 3)}}
		return _completer(mods, cible, "bonus_degats", 1, PLAFOND_DEGATS), [TAG_ARME]
	if partie == "jambe":
		mods = {"bonus": _caracs(theme, palier), "bonus_initiative": 1}
		return _completer(mods, cible, "bonus_pa", 1), [TAG_ARMURE]
	if partie == "aile":
		mods = {"bonus": _caracs(theme, palier), "effets": {"esquive": 1}}
		if theme in ("celeste", "fee"):
			mods["effets"]["regen_pm"] = 1
		return _completer(mods, cible, "bonus_pm", 0.5), [TAG_CATA] + MATERIAU_SORTE[sorte]
	# corps : armure de la sorte de l'espèce + consommable (soin à l'ingestion)
	mods = {"bonus": {THEMES[theme][0]: min(PLAFOND_CARAC, palier - 1)},
			"bonus_pv": 2 * palier, "effets": {"pv": 5 * palier}}
	tags = MATERIAU_SORTE[sorte] + [TAG_CONSO]
	return _completer(mods, cible, "bonus_pa", 1, conso=True), tags


def mods_matiere(sorte: str, theme: str, palier: int) -> tuple[dict, list]:
	"""(modificateurs, tags) d'une MATIÈRE NOMMÉE — score visé `CIBLE_MATIERE[palier]`."""
	cible = CIBLE_MATIERE[palier]
	c1, c2, _deb = THEMES[theme]
	if sorte in ("ecailles", "cuir", "peau"):
		mods = {"bonus": {c1: min(PLAFOND_CARAC, palier - 1)}, "bonus_pv": 2 * palier}
		if sorte != "ecailles":
			mods["effets"] = {"esquive": 1}
		return _completer(mods, cible, "bonus_pa", 1), list(MATERIAU_SORTE[sorte])
	if sorte in ("plumes", "soie"):
		mods = {"bonus": {c1: palier - 2, c2: 1}, "effets": {"esquive": 1, "canalisation": 1}}
		return _completer(mods, cible, "bonus_pm", 0.5), [TAG_TISSU, TAG_CATA]
	if sorte == "os":
		mods = {"bonus": {c1: palier - 1}, "bonus_pa": 2}
		return _completer(mods, cible, "bonus_degats", 1, PLAFOND_DEGATS), [TAG_ARME, TAG_METAL]
	# cendre : catalyseur et consommable
	mods = {"bonus": {c1: palier - 2, c2: 1}, "effets": {"canalisation": 1, "pm": 5 * palier}}
	return _completer(mods, cible, "bonus_pm", 0.5, conso=True), [TAG_CATA, TAG_CONSO]


def item_partie(espece_id: str, entree: str) -> str:
	partie, morceau = entree.rstrip("*"), entree.endswith("*")
	return "item:%s_%s%s" % (espece_id.split(":", 1)[1], partie, "_morceau" if morceau else "")


def nom_partie(espece_id: str, partie: str) -> str:
	_p, _t, du, (_slug, _nom, _icon, sorte), _ev = ESPECES[espece_id]
	return "%s %s" % (NOM_SORTE[sorte] if partie == "corps" else NOM_PARTIE[partie], du)


def entrees_fabrication(_partie, _matiere) -> dict:
	"""Entrées au format de gen_fabrication_matieres.MATIERES (helpers injectés)."""
	out = {}
	for esp, (palier, theme, du, (slug, nom, _icon, sorte), _ev) in ESPECES.items():
		for entree in PARTIES.get(esp, []):
			partie = entree.rstrip("*")
			mods, tags = mods_partie(partie, theme, palier, sorte)
			out[item_partie(esp, entree)] = _partie(nom_partie(esp, partie), palier, "tete", mods, tags)
		mods, tags = mods_matiere(sorte, theme, palier)
		out["item:" + slug] = _matiere("%s %s" % (NOM_SORTE[sorte], du), palier, mods, tags)
	return out
