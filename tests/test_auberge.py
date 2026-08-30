# tests/test_auberge.py
# Ce que ce fichier protège : la salle commune d'une taverne est le PREMIER endroit du jeu
# où un joueur écrit un texte que d'AUTRES joueurs liront. Deux classes de bug y coûtent
# cher, et aucune ne se voit à l'œil nu :
#
#   1. Le bornage. `nettoyer_ligne`/`nettoyer_texte` doivent borner SANS échapper — la
#      doctrine du projet est « on BORNE au serveur, on ÉCHAPPE au rendu » (Convention §9).
#      Un helper qui se mettrait à échapper produirait un double échappement, et le joueur
#      lirait `&amp;lt;` dans son propre message. Le test qui l'épingle est le miroir exact de
#      `test_nettoyer_nom_compagnie_n_echappe_pas_le_html`.
#
#   2. Le nettoyage nocturne. Passer la nuit efface les messages de table DU DORMEUR et lui
#      ferme ses tables — sans toucher à ce que les autres convives voient, ni aux annonces
#      du tableau, qui sont durables. Se tromper de périmètre effacerait la soirée de tout
#      le monde, en silence.
#
# Tests PURS : aucune base, les accès sont injectés (`find_docs_fn`, `get_doc_fn`).

import pytest

from models import character_stats
from utils import auberge
from utils import expedition


# ── Catalogue d'items (monde de test) ────────────────────────────────────────────
PAPIER = {"_id": "item:Papier", "type": "item", "nom": "Papier",
		  "categorie": "composant", "sous_categorie": "papier"}
ENCRE = {"_id": "item:Encre", "type": "item", "nom": "Encre",
		 "categorie": "composant", "sous_categorie": "encre"}
PLUME = {"_id": "item:Plume_d_oie", "type": "item", "nom": "Plume d'oie",
		 "categorie": "outil", "sous_categorie": "plume_a_ecrire"}
# ⚠️ Sous-catégorie VIDE : `item_sous_categorie` retombe alors sur la `categorie`. C'est
# l'état dans lequel étaient les encres avant qu'on ne leur en donne une.
SANS_SOUS_CAT = {"_id": "item:Bidule", "type": "item", "nom": "Bidule",
				 "categorie": "composant", "sous_categorie": ""}

CATALOGUE = {d["_id"]: d for d in (PAPIER, ENCRE, PLUME, SANS_SOUS_CAT)}


def _get_doc(item_id):
	return CATALOGUE.get(item_id)


def _perso(pid="character:moi", **kw):
	base = {"_id": pid, "type": "character", "prenom": "Greta", "nom": "Hazgard",
			"inventaire": [], "slots": {}}
	base.update(kw)
	return base


def _table(tid, numero=1, participants=None, anciens=None, noms=None):
	# ⚠️ `noms` n'est posé QUE s'il est demandé : sans lui, le doc a la forme d'une table déjà
	# en base — c'est le cas « aucune migration » qu'il faut pouvoir tester.
	doc = {"_id": tid, "type": "table", "lieu": "lieu:auberge", "numero": numero,
		   "participants": list(participants or []), "anciens": list(anciens or []),
		   "cree_at": 100, "activite_at": 100}
	if noms is not None:
		doc["noms"] = dict(noms)
	return doc


def _message(mid, auteur="character:moi", support=auberge.SUPPORT_TABLE,
			 table="table:1", cree_at=100, expire_at=None):
	doc = {"_id": mid, "type": "message", "lieu": "lieu:auberge", "support": support,
		   "auteur": auteur, "auteur_nom": "Greta Hazgard", "texte": "bonsoir",
		   "cree_at": cree_at}
	if support == auberge.SUPPORT_TABLE:
		doc["table"] = table
		doc["expire_at"] = cree_at + 86400 if expire_at is None else expire_at
	return doc


# ── Le prédicat de lieu ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("doc, attendu", [
	({"categorie": "auberge"}, True),
	({"categorie": "taverne_du_coin", "tags": ["taverne"]}, True),
	({"categorie": "etable"}, False),
	({}, False),
	(None, False),
])
def test_lieu_est_taverne(doc, attendu):
	assert auberge.lieu_est_taverne(doc) is attendu


# ── Bornage ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("brut, attendu", [
	("  Bonsoir   la   compagnie  ", "Bonsoir la compagnie"),
	("ligne\tavec\ttabulations", "ligne avec tabulations"),
	("saut\nde\nligne", "saut de ligne"),          # nettoyer_ligne ÉCRASE les sauts
	("zero​width", "zerowidth"),              # non-imprimable retiré
	(None, ""),
	(12345, "12345"),
])
def test_nettoyer_ligne(brut, attendu):
	assert auberge.nettoyer_ligne(brut, 200) == attendu


def test_nettoyer_ligne_tronque_dur():
	assert auberge.nettoyer_ligne("a" * 50, 10) == "a" * 10


def test_nettoyer_ligne_n_echappe_pas_le_html():
	"""⚠️ Miroir de `test_nettoyer_nom_compagnie_n_echappe_pas_le_html`. On BORNE au
	serveur, on ÉCHAPPE au rendu : échapper ici produirait un double échappement et le
	joueur lirait `&amp;lt;script&amp;gt;` dans son propre message."""
	brut = "<script>alert('x')</script> & \"guillemets\""
	assert auberge.nettoyer_ligne(brut, 200) == brut


def test_nettoyer_texte_preserve_les_sauts_de_ligne():
	"""C'est TOUTE la différence avec `nettoyer_ligne` : une annonce est multi-ligne."""
	assert auberge.nettoyer_texte("premier\nsecond\ntroisieme", 800) == "premier\nsecond\ntroisieme"


def test_nettoyer_texte_ecrase_les_lignes_vides_consecutives():
	assert auberge.nettoyer_texte("a\n\n\n\nb", 800) == "a\n\nb"


def test_nettoyer_texte_supprime_les_lignes_vides_de_tete_et_de_queue():
	assert auberge.nettoyer_texte("\n\n  a  \n\n", 800) == "a"


def test_nettoyer_texte_normalise_les_fins_de_ligne_windows():
	assert auberge.nettoyer_texte("a\r\nb\rc", 800) == "a\nb\nc"


def test_nettoyer_texte_n_echappe_pas_le_html():
	brut = "<b>avis</b>\n& autre"
	assert auberge.nettoyer_texte(brut, 800) == brut


def test_nettoyer_texte_borne_la_longueur_totale():
	assert len(auberge.nettoyer_texte("mot " * 500, 800)) <= 800


def test_nettoyer_texte_borne_le_nombre_de_lignes():
	assert auberge.nettoyer_texte("\n".join(str(i) for i in range(50)), 800, max_lignes=3) == "0\n1\n2"


def test_portrait_de_porte_l_image_et_son_cadrage():
	"""Le cadrage voyage avec l'image : un avatar de chat doit montrer le cadrage que le
	joueur s'est choisi, pas sa silhouette entière."""
	perso = _perso(image="guerriere_h_02.png", portrait_zoom=120,
				   portrait_translate={"x": -12.0, "y": -30.0})
	assert auberge.portrait_de(perso) == {
		"auteur_image": "guerriere_h_02.png",
		"auteur_zoom": 120,
		"auteur_translate": {"x": -12.0, "y": -30.0},
	}


def test_portrait_de_sans_image_ne_pose_RIEN():
	"""⚠️ Clés absentes ⇒ le client retombe sur la silhouette générique. Aucune migration :
	les messages déjà en base restent lisibles."""
	assert auberge.portrait_de(_perso()) == {}
	assert auberge.portrait_de({}) == {}
	assert auberge.portrait_de(None) == {}


def test_portrait_de_omet_un_cadrage_absent_sans_poser_de_None():
	"""Un personnage qui n'a jamais recadré son portrait : on pose l'image seule."""
	assert auberge.portrait_de(_perso(image="a.png")) == {"auteur_image": "a.png"}


def test_portrait_de_ignore_un_translate_qui_n_est_pas_un_dict():
	"""⚠️ `portrait_translate` est un DICT {x, y}, pas la chaîne CSS enregistrée par le
	client. Une valeur d'une autre forme est écartée plutôt que propagée."""
	perso = _perso(image="a.png", portrait_translate="translate(-12px,-30px)")
	assert auberge.portrait_de(perso) == {"auteur_image": "a.png"}


def test_un_message_porte_le_portrait_de_son_auteur():
	perso = _perso(image="a.png", portrait_zoom=110)
	doc = auberge.nouveau_message("lieu:auberge", perso, "bonsoir",
								  support=auberge.SUPPORT_TABLEAU, now=1000)
	assert doc["auteur_image"] == "a.png" and doc["auteur_zoom"] == 110


def test_un_message_d_un_personnage_sans_portrait_reste_valide():
	doc = auberge.nouveau_message("lieu:auberge", _perso(), "bonsoir", now=1000)
	assert "auteur_image" not in doc
	assert doc["auteur_nom"] == "Greta Hazgard"


def test_nom_affichable_replie_sur_un_inconnu():
	"""Un personnage sans nom ne doit pas produire une ligne d'auteur vide."""
	assert auberge.nom_affichable({"prenom": "", "nom": ""}) == "Un inconnu"
	assert auberge.nom_affichable({"prenom": "Greta", "nom": "Hazgard"}) == "Greta Hazgard"


# ── Péremption ───────────────────────────────────────────────────────────────────

def test_un_message_de_table_perime():
	m = _message("message:1", cree_at=0, expire_at=100)
	assert auberge.message_perime(m, 99) is False
	assert auberge.message_perime(m, 100) is True


def test_une_annonce_du_tableau_ne_perime_JAMAIS():
	"""⚠️ C'est ce qui distingue le tableau, durable, des tables, éphémères : une annonce
	ne part qu'à la main."""
	m = _message("message:1", support=auberge.SUPPORT_TABLEAU, cree_at=0)
	assert auberge.message_perime(m, 10 ** 12) is False


def test_message_sans_expire_at_replie_sur_cree_at_plus_duree():
	m = {"support": auberge.SUPPORT_TABLE, "cree_at": 0}
	duree = int(character_stats.AUBERGE_MESSAGE_DUREE_SECONDES)
	assert auberge.message_perime(m, duree - 1) is False
	assert auberge.message_perime(m, duree) is True


def test_purger_supprime_et_rend_le_reste():
	vivants = _message("message:vif", cree_at=0, expire_at=10 ** 12)
	mort = _message("message:mort", cree_at=0, expire_at=1)
	supprimes = []
	restants = auberge.purger_messages_perimes([vivants, mort], 100, supprimes.append)
	assert restants == [vivants]
	assert supprimes == [mort]


def test_messages_en_trop_sacrifie_les_plus_anciens():
	msgs = [_message(f"message:{i}", cree_at=i) for i in range(13)]
	trop = auberge.messages_en_trop(msgs, 10)
	assert [m["_id"] for m in trop] == ["message:0", "message:1", "message:2"]


def test_aucun_message_en_trop_sous_le_plafond():
	assert auberge.messages_en_trop([_message("message:1")], 10) == []


# ── Tables ───────────────────────────────────────────────────────────────────────

def test_nouvelle_table_prend_le_numero_suivant():
	tables = [_table("table:a", 1), _table("table:b", 4)]
	neuve = auberge.nouvelle_table("lieu:auberge", tables, now=500)
	assert neuve["numero"] == 5
	assert neuve["participants"] == [] and neuve["anciens"] == []


def test_nouvelle_table_refusee_quand_la_salle_est_pleine():
	pleine = [_table(f"table:{i}", i) for i in range(int(character_stats.AUBERGE_TABLES_MAX))]
	assert auberge.nouvelle_table("lieu:auberge", pleine) is None


def test_s_asseoir_pose_le_marqueur_de_table():
	"""⚠️ `taverne_table` est ce qui permettra de le relever quand il sortira de l'auberge,
	sans coûter un `find_docs` à chaque pas de chaque joueur."""
	a = _table("table:a", 1)
	perso = _perso()
	ok, _ = auberge.asseoir(a, perso, now=500)
	assert ok is True
	assert a["participants"] == ["character:moi"]
	assert perso["taverne_table"] == "table:a"


def test_s_asseoir_denormalise_le_nom():
	"""⚠️ Pour les mêmes deux raisons qu'`auteur_nom` sur un message : relire le `character:*`
	de chaque participant à chaque sondage serait N lectures d'un type exclu du cache de
	requête, ET on n'a pas le droit de lire le personnage d'un autre joueur."""
	a = _table("table:a", 1)
	auberge.asseoir(a, _perso(), now=500)
	assert a["noms"] == {"character:moi": "Greta Hazgard"}


def test_s_asseoir_est_idempotent():
	a = _table("table:a", 1, participants=["character:moi"],
			   noms={"character:moi": "Greta Hazgard"})
	auberge.asseoir(a, _perso(), now=500)
	assert a["participants"] == ["character:moi"]
	assert a["noms"] == {"character:moi": "Greta Hazgard"}


def test_les_noms_suivent_l_ordre_d_arrivee():
	"""⚠️ L'ordre vient de `participants` et jamais des clés de `noms` : c'est `participants`
	qui porte l'ordre d'arrivée, le dict n'est qu'un répertoire."""
	t = _table("table:a", 1)
	auberge.asseoir(t, _perso("character:moi"), now=500)
	auberge.asseoir(t, _perso("character:bran", prenom="Bran", nom="Osier"), now=501)
	assert auberge.noms_attables(t) == ["Greta Hazgard", "Bran Osier"]


def test_un_participant_sans_nom_connu_est_omis():
	"""Table déjà en base, assise avant que le champ n'existe : aucune migration. La liste est
	plus courte que `participants` — c'est au client de compter le reste, pas de tout jeter."""
	t = _table("table:a", 1, participants=["character:ancien", "character:moi"],
			   noms={"character:moi": "Greta Hazgard"})
	assert auberge.noms_attables(t) == ["Greta Hazgard"]
	# Et une table entièrement héritée ne lève pas : elle ne dit simplement aucun nom.
	assert auberge.noms_attables(_table("table:b", 2, participants=["character:x"])) == []


def test_rafraichir_mon_nom_repare_une_table_heritee():
	"""⚠️ `asseoir` n'écrit le nom que de CELUI QUI S'ASSIED : sans cette réparation à la
	lecture, quelqu'un déjà attablé ne serait jamais rattrapé."""
	t = _table("table:a", 1, participants=["character:autre", "character:moi"])
	assert auberge.rafraichir_mon_nom([t], _perso()) == [t]
	assert t["noms"] == {"character:moi": "Greta Hazgard"}
	# ⚠️ On ne répare QUE le sien : lire le `character:*` d'autrui est interdit.
	assert auberge.noms_attables(t) == ["Greta Hazgard"]


def test_rafraichir_mon_nom_n_ecrit_rien_quand_c_est_deja_bon():
	"""⚠️ Appelée sur le chemin du SONDAGE (toutes les 4 s) : elle ne doit écrire qu'une fois."""
	t = _table("table:a", 1, participants=["character:moi"],
			   noms={"character:moi": "Greta Hazgard"})
	assert auberge.rafraichir_mon_nom([t], _perso()) == []


def test_rafraichir_mon_nom_ignore_les_tables_ou_l_on_n_est_pas():
	t = _table("table:a", 1, participants=["character:autre"])
	assert auberge.rafraichir_mon_nom([t], _perso()) == []
	assert "noms" not in t


def test_une_table_ou_l_on_a_dormi_est_refusee():
	"""⚠️ `anciens` est la mémoire de la nuit : elle ferme la table POUR LUI SEUL."""
	t = _table("table:a", 1, anciens=["character:moi"])
	ok, raison = auberge.asseoir(t, _perso())
	assert ok is False and raison
	assert t["participants"] == []
	# …mais elle reste grande ouverte pour quelqu'un d'autre.
	assert auberge.asseoir(t, _perso("character:autre"))[0] is True


def test_une_table_est_vide_des_que_PERSONNE_n_y_est_assis():
	"""⚠️ Ce n'est plus « ni participant NI message » : des propos flottant dans une salle
	déserte n'ont aucun sens, et l'ancien critère faisait survivre indéfiniment une table
	que tout le monde avait quittée."""
	assert auberge.table_vide(_table("table:a", 1)) is True
	assert auberge.table_vide(_table("table:b", 2, participants=["character:moi"])) is False


# ── Quitter une table ────────────────────────────────────────────────────────────

def test_quitter_une_table_emporte_SES_messages():
	"""⚠️ Une conversation appartient à ceux qui sont attablés : laisser ses propos derrière
	soi les ferait lire à des convives à qui l'on ne peut plus répondre."""
	t = _table("table:a", 1, participants=["character:moi", "character:autre"])
	messages = [
		_message("message:mien", auteur="character:moi", table="table:a"),
		_message("message:sien", auteur="character:autre", table="table:a"),
	]
	modifiees, a_supprimer = auberge.quitter_tables(_perso(), [t], messages)
	assert modifiees == [t]
	assert [m["_id"] for m in a_supprimer] == ["message:mien"]
	assert t["participants"] == ["character:autre"]
	assert t["anciens"] == []          # partir n'est pas dormir : la table reste ouverte


def test_quitter_emporte_SON_nom_mais_pas_celui_des_autres():
	"""Le nom part avec la présence : personne ne doit lire dans la tête d'une table quelqu'un
	qui n'y est plus."""
	t = _table("table:a", 1, participants=["character:moi", "character:autre"],
			   noms={"character:moi": "Greta Hazgard", "character:autre": "Bran Osier"})
	auberge.quitter_tables(_perso(), [t], [])
	assert t["noms"] == {"character:autre": "Bran Osier"}
	assert auberge.noms_attables(t) == ["Bran Osier"]


def test_fermer_soiree_emporte_aussi_le_nom():
	"""⚠️ Le nom ne suit PAS dans `anciens`, qui ne sert qu'au filtrage de visibilité et
	n'affiche rien : les convives restés attablés ne doivent plus voir le dormeur."""
	t = _table("table:a", 1, participants=["character:moi", "character:autre"],
			   noms={"character:moi": "Greta Hazgard", "character:autre": "Bran Osier"})
	auberge.fermer_soiree(_perso(), [t], [])
	assert t["noms"] == {"character:autre": "Bran Osier"}
	assert t["anciens"] == ["character:moi"]


def test_quitter_une_table_heritee_ne_leve_pas():
	"""Table déjà en base, sans le champ `noms` : aucune migration."""
	t = _table("table:a", 1, participants=["character:moi"])
	auberge.quitter_tables(_perso(), [t], [])
	assert t["participants"] == []


def test_quitter_efface_le_marqueur_de_table():
	t = _table("table:a", 1, participants=["character:moi"])
	perso = _perso(taverne_table="table:a")
	auberge.quitter_tables(perso, [t], [])
	assert "taverne_table" not in perso


def test_sauf_epargne_la_table_ou_l_on_vient_s_asseoir():
	"""⚠️ Sans `sauf`, se rasseoir à SA propre table effacerait ce qu'on vient d'y dire."""
	t = _table("table:a", 1, participants=["character:moi"])
	messages = [_message("message:mien", auteur="character:moi", table="table:a")]
	modifiees, a_supprimer = auberge.quitter_tables(_perso(), [t], messages, sauf="table:a")
	assert modifiees == [] and a_supprimer == []
	assert t["participants"] == ["character:moi"]


def test_quitter_n_emporte_PAS_les_annonces_du_tableau():
	messages = [_message("message:avis", auteur="character:moi",
						 support=auberge.SUPPORT_TABLEAU)]
	t = _table("table:a", 1, participants=["character:moi"])
	_, a_supprimer = auberge.quitter_tables(_perso(), [t], messages)
	assert a_supprimer == []


# ── La fin de soirée ─────────────────────────────────────────────────────────────

def test_fermer_soiree_n_efface_que_les_messages_du_dormeur():
	tables = [_table("table:a", 1, participants=["character:moi", "character:autre"])]
	messages = [
		_message("message:mien", auteur="character:moi", table="table:a"),
		_message("message:sien", auteur="character:autre", table="table:a"),
		_message("message:avis", auteur="character:moi", support=auberge.SUPPORT_TABLEAU),
	]
	modifiees, a_supprimer = auberge.fermer_soiree(_perso(), tables, messages)

	assert [m["_id"] for m in a_supprimer] == ["message:mien"]
	assert modifiees == tables
	# L'autre convive reste attablé : la soirée ne s'achève que pour le dormeur.
	assert tables[0]["participants"] == ["character:autre"]
	assert tables[0]["anciens"] == ["character:moi"]


def test_fermer_soiree_epargne_les_annonces_du_tableau():
	"""⚠️ Le tableau est DURABLE : dormir n'y décroche rien."""
	messages = [_message("message:avis", auteur="character:moi",
						 support=auberge.SUPPORT_TABLEAU)]
	_, a_supprimer = auberge.fermer_soiree(_perso(), [], messages)
	assert a_supprimer == []


def test_fermer_soiree_ignore_les_tables_ou_l_on_n_etait_pas():
	tables = [_table("table:a", 1, participants=["character:autre"])]
	modifiees, _ = auberge.fermer_soiree(_perso(), tables, [])
	assert modifiees == []
	assert tables[0]["anciens"] == []


# ── Le log de la nuit ────────────────────────────────────────────────────────────

def test_le_log_du_lieu_prime_sur_le_defaut_de_code():
	lieu = {"nuit_messages": ["une", "deux", "trois"]}
	assert set(auberge.messages_nuit(lieu, 3)) <= {"une", "deux", "trois"}


def test_le_log_replie_sur_le_defaut_quand_le_lieu_n_en_porte_pas():
	sortie = auberge.messages_nuit({}, 4)
	assert len(sortie) == 4
	assert set(sortie) <= set(auberge.MESSAGES_NUIT)


def test_le_log_garde_l_ordre_de_la_liste_d_origine():
	"""⚠️ On tire QUOI montrer, pas DANS QUEL ORDRE : les lignes racontent une nuit qui
	avance, de la salle qui se vide aux chariots d'avant l'aube."""
	lieu = {"nuit_messages": ["a", "b", "c", "d"]}
	# Un tirage qui rend les éléments à l'envers doit quand même sortir dans l'ordre.
	sortie = auberge.messages_nuit(lieu, 3, rand_fn=lambda src, n: ["d", "b", "a"])
	assert sortie == ["a", "b", "d"]


def test_le_log_ne_demande_jamais_plus_que_la_source():
	lieu = {"nuit_messages": ["seule"]}
	assert auberge.messages_nuit(lieu, 10) == ["seule"]


# ── Le repos ─────────────────────────────────────────────────────────────────────

def test_reposer_remet_pv_et_pm_au_maximum():
	perso = _perso(caracteristiques_current={"V": 5, "F": 40, "R": 40, "Ag": 40,
											 "Vol": 40, "Int": 40, "Cha": 40, "Ch": 40},
				   currentPV=1, currentPM=0)
	vitaux = auberge.reposer(perso)
	assert perso["currentPV"] == vitaux["pv_max"] > 1
	assert perso["currentPM"] == vitaux["pm_max"] > 0


def test_reposer_ne_dissipe_pas_les_effets_actifs():
	"""⚠️ La nuit remet les points, elle ne lève pas les buffs — une potion bue avant de
	monter se cuve pendant le sommeil."""
	effets = [{"nom": "Potion", "buffs": {"F": 5}, "restants": 3}]
	perso = _perso(caracteristiques_current={"V": 5, "F": 40, "R": 40, "Ag": 40,
											 "Vol": 40, "Int": 40, "Cha": 40, "Ch": 40},
				   currentPV=1, effets_actifs=effets)
	auberge.reposer(perso)
	assert perso["effets_actifs"] == effets


# ── Possession des fournitures ───────────────────────────────────────────────────

def test_porteur_avec_sous_categorie_trouve_dans_le_sac():
	perso = _perso(inventaire=["item:Papier"])
	assert expedition.porteur_avec_sous_categorie(_get_doc, [perso], "papier") is True
	assert expedition.porteur_avec_sous_categorie(_get_doc, [perso], "encre") is False


def test_porteur_avec_sous_categorie_trouve_dans_les_slots():
	"""Une plume est le plus souvent EN MAIN, pas rangée — les slots comptent autant que
	l'inventaire (même raison que la hache de `porteur_avec_tag`)."""
	perso = _perso(slots={"main_droite": {"item": "item:Plume_d_oie", "poids": 0.01}})
	assert expedition.porteur_avec_sous_categorie(_get_doc, [perso], "plume_a_ecrire") is True


def test_porteur_avec_sous_categorie_accepte_une_ref_objet():
	perso = _perso(inventaire=[{"item": "item:Encre", "poids": 0.1}])
	assert expedition.porteur_avec_sous_categorie(_get_doc, [perso], "encre") is True


def test_porteur_avec_sous_categorie_replie_sur_la_categorie():
	"""⚠️ `item_sous_categorie` retombe sur la `categorie` quand la sous-catégorie est vide.
	C'est l'état dans lequel étaient les encres avant qu'on leur en donne une — et c'est
	pourquoi ce helper doit traverser ce chokepoint plutôt que lire le champ à la main."""
	perso = _perso(inventaire=["item:Bidule"])
	assert expedition.porteur_avec_sous_categorie(_get_doc, [perso], "composant") is True


def test_porteur_avec_sous_categorie_refuse_une_sous_categorie_vide():
	perso = _perso(inventaire=["item:Papier"])
	assert expedition.porteur_avec_sous_categorie(_get_doc, [perso], "") is False


def test_retirer_fournitures_depense_papier_et_encre_et_garde_la_plume():
	perso = _perso(inventaire=["item:Papier", "item:Encre", "item:Plume_d_oie"])
	ok, retirees = auberge.retirer_fournitures(_get_doc, perso)
	assert ok is True and retirees == ["papier", "encre"]
	assert perso["inventaire"] == ["item:Plume_d_oie"]


def test_retirer_fournitures_est_TOUT_OU_RIEN():
	"""⚠️ On repère d'abord, on retire ensuite : sinon le sac serait amputé du papier avant
	qu'on découvre qu'il n'y a pas d'encre — le joueur paierait pour rien."""
	perso = _perso(inventaire=["item:Papier", "item:Plume_d_oie"])
	ok, retirees = auberge.retirer_fournitures(_get_doc, perso)
	assert ok is False and retirees == []
	assert perso["inventaire"] == ["item:Papier", "item:Plume_d_oie"]


def test_retirer_fournitures_ne_prend_qu_UN_exemplaire_de_chaque():
	perso = _perso(inventaire=["item:Papier", "item:Papier", "item:Encre", "item:Encre"])
	auberge.retirer_fournitures(_get_doc, perso)
	assert perso["inventaire"] == ["item:Papier", "item:Encre"]


def test_retirer_fournitures_ne_se_trompe_pas_d_index_apres_decalage():
	"""⚠️ Les index se décalent à chaque retrait : on supprime du plus grand au plus petit.
	Avec le papier en tête et l'encre en queue, l'ordre naïf retirerait le mauvais objet."""
	perso = _perso(inventaire=["item:Papier", "item:Plume_d_oie", "item:Bidule", "item:Encre"])
	ok, _ = auberge.retirer_fournitures(_get_doc, perso)
	assert ok is True
	assert perso["inventaire"] == ["item:Plume_d_oie", "item:Bidule"]


def test_retirer_fournitures_accepte_une_ref_objet():
	perso = _perso(inventaire=[{"item": "item:Papier", "poids": 0.05},
							   {"item": "item:Encre", "poids": 0.1}])
	ok, _ = auberge.retirer_fournitures(_get_doc, perso)
	assert ok is True and perso["inventaire"] == []


def test_le_controle_et_la_depense_voient_la_MEME_chose():
	"""⚠️ Si le contrôle scannait les slots et la dépense seulement le sac, l'annonce serait
	acceptée sans que rien ne soit retiré : écrire redeviendrait gratuit, en silence."""
	perso = _perso(slots={"main_droite": "item:Papier"}, inventaire=["item:Encre"])
	assert auberge.fournitures_manquantes(_get_doc, [perso]) == ["plume_a_ecrire"]
	ok, _ = auberge.retirer_fournitures(_get_doc, perso)
	assert ok is True
	assert perso["slots"]["main_droite"] is None
	assert perso["inventaire"] == []


def test_les_fournitures_consommees_sont_un_sous_ensemble_des_exigees():
	"""On ne dépense que ce qu'on a d'abord exigé."""
	assert set(auberge.FOURNITURES_CONSOMMEES) <= set(auberge.FOURNITURES_ANNONCE)


def test_fournitures_manquantes_nomme_ce_qui_manque():
	"""On rend le DÉTAIL et pas un booléen : le refus doit dire quoi aller acheter."""
	perso = _perso(inventaire=["item:Papier"])
	assert auberge.fournitures_manquantes(_get_doc, [perso]) == ["encre", "plume_a_ecrire"]

	complet = _perso(inventaire=["item:Papier", "item:Encre", "item:Plume_d_oie"])
	assert auberge.fournitures_manquantes(_get_doc, [complet]) == []


# ── Qui tient la plume ───────────────────────────────────────────────────────────

def _compagnon(pid="aventurier:bran", principal="character:moi", **kw):
	base = {"_id": pid, "type": "aventurier", "statut": "embauche",
			"embauche_par": principal, "prenom": "Bran", "nom": "Osier",
			"inventaire": [], "slots": {}}
	base.update(kw)
	return base


def test_les_ecrivains_sont_le_principal_PUIS_ses_compagnons():
	"""L'ordre compte : le joueur ouvre la liste, c'est lui le choix par défaut."""
	bran = _compagnon()
	perso = _perso(groupe=[bran["_id"]])
	docs = {bran["_id"]: bran}
	assert auberge.ecrivains(perso, docs.get) == [perso, bran]


def test_une_MONTURE_n_est_JAMAIS_un_ecrivain():
	"""⚠️ `expedition.membres` et non `recrutement.porteurs_effectifs` (Convention §7) : une
	bête PORTE le papier, elle ne l'écrit pas. Les confondre mettrait une mule dans le
	sélecteur — et lui ferait signer un avis."""
	mule = {"_id": "monture:mule", "type": "monture", "statut": "acquise",
			"acquise_par": "character:moi", "nom": "Mule",
			"inventaire": ["item:Papier", "item:Encre", "item:Plume_d_oie"], "slots": {}}
	perso = _perso(montures=[mule["_id"]])
	docs = {mule["_id"]: mule}
	assert auberge.ecrivains(perso, docs.get) == [perso]


def test_le_principal_figure_comme_LE_MEME_dict_et_non_une_relecture():
	"""⚠️ Deux dicts d'un même document, ce sont deux `save_doc` sur le même `_rev` — et,
	ici, un relevé de fournitures pris AVANT la dépense qu'on vient de faire."""
	perso = _perso(inventaire=["item:Papier"])
	assert auberge.ecrivains(perso, lambda _id: None)[0] is perso


def test_ecrivain_view_ne_publie_PAS_l_id_du_principal():
	"""⚠️ Un `_id` de personnage s'écrit `character:user:<email>_<uuid>` : le tenir hors des
	payloads est la règle de ce module. `""` = le principal, convention du `compagnon_id`."""
	perso = _perso(inventaire=["item:Papier", "item:Encre", "item:Plume_d_oie"])
	vue = auberge.ecrivain_view(_get_doc, perso, perso)
	assert vue["id"] == "" and vue["compagnon"] is False
	assert vue["nom"] == "Greta Hazgard"
	assert vue["peut_ecrire"] is True and vue["manquantes"] == []


def test_ecrivain_view_dit_CE_QUI_manque_a_un_compagnon():
	perso = _perso()
	bran = _compagnon(inventaire=["item:Papier"])
	vue = auberge.ecrivain_view(_get_doc, bran, perso)
	assert vue["id"] == "aventurier:bran" and vue["compagnon"] is True
	assert vue["peut_ecrire"] is False
	assert vue["manquantes"] == ["encre", "plume_a_ecrire"]
	assert vue["fournitures"] == {"papier": True, "encre": False, "plume_a_ecrire": False}


def test_ecrivain_view_voit_les_slots_comme_le_sac():
	"""Une plume est le plus souvent EN MAIN — le relevé offert au choix doit voir
	exactement ce que verra la dépense, sinon le sélecteur mentirait."""
	perso = _perso()
	bran = _compagnon(inventaire=["item:Papier", "item:Encre"],
					  slots={"main_droite": "item:Plume_d_oie"})
	assert auberge.ecrivain_view(_get_doc, bran, perso)["peut_ecrire"] is True


def test_manquantes_de_est_la_source_unique_du_ce_qui_manque():
	"""Un seul « ce qui manque », lu par le refus comme par le sélecteur : deux formulations
	divergentes finiraient par ne pas nommer la même chose."""
	presentes = auberge.fournitures_presentes(_get_doc, [_perso(inventaire=["item:Encre"])])
	assert auberge.manquantes_de(presentes) == ["papier", "plume_a_ecrire"]
	assert auberge.manquantes_de({}) == list(auberge.FOURNITURES_ANNONCE)


# ── Lecture de la salle ──────────────────────────────────────────────────────────

def test_find_docs_qui_echoue_ne_fait_pas_tomber_la_salle():
	"""⚠️ `find_docs` renvoie None sur exception : sans le `or []`, la salle exploserait."""
	assert auberge.tables_du_lieu("lieu:auberge", lambda s: None) == []
	assert auberge.messages_du_lieu("lieu:auberge", lambda s: None) == []


def test_les_tables_sortent_triees_par_numero():
	docs = [_table("table:c", 3), _table("table:a", 1), _table("table:b", 2)]
	tries = auberge.tables_du_lieu("lieu:auberge", lambda s: docs)
	assert [t["numero"] for t in tries] == [1, 2, 3]


def test_les_messages_sortent_du_plus_ancien_au_plus_recent():
	docs = [_message("message:b", cree_at=20), _message("message:a", cree_at=10)]
	tries = auberge.messages_du_lieu("lieu:auberge", lambda s: docs)
	assert [m["_id"] for m in tries] == ["message:a", "message:b"]


def test_de_support_separe_le_tableau_des_tables():
	msgs = [
		_message("message:t1", table="table:a"),
		_message("message:t2", table="table:b"),
		_message("message:avis", support=auberge.SUPPORT_TABLEAU),
	]
	assert [m["_id"] for m in auberge.de_support(msgs, auberge.SUPPORT_TABLEAU)] == ["message:avis"]
	assert [m["_id"] for m in auberge.de_support(msgs, auberge.SUPPORT_TABLE, "table:a")] == ["message:t1"]


# ── Construction d'un message ────────────────────────────────────────────────────

def test_un_message_de_table_porte_son_echeance_et_sa_table():
	doc = auberge.nouveau_message("lieu:auberge", _perso(), "bonsoir",
								  support=auberge.SUPPORT_TABLE, table_id="table:a", now=1000)
	assert doc["table"] == "table:a"
	assert doc["expire_at"] == 1000 + int(character_stats.AUBERGE_MESSAGE_DUREE_SECONDES)
	assert doc["auteur_nom"] == "Greta Hazgard"
	assert doc["_id"].startswith("message:")


def test_une_annonce_ne_porte_ni_table_ni_echeance():
	doc = auberge.nouveau_message("lieu:auberge", _perso(), "avis",
								  support=auberge.SUPPORT_TABLEAU, now=1000)
	assert "table" not in doc and "expire_at" not in doc
