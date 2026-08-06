# tests/test_cites_depart.py
# `lieux.cites_de_depart` / `est_cite_de_depart` : la SOURCE UNIQUE des cités où un
# personnage peut naître — la grille de l'écran de création (main.py, /embleme) ET la
# garde 422 d'`add_character` (routers/user.py) en dépendent.
#
# La règle mêle DEUX sources : un nommage de fichier (`<nom>_start_*.<ext>` dans
# templates/resources/towns) et l'existence du doc `lieu:<nom>`. Le disque est donc lu
# pour de vrai (les images sont committées) ; seule la base est injectée.
#
# Le test qui compte est `test_le_client_et_le_serveur_proposent_la_MEME_liste` : si les
# deux divergeaient, le joueur choisirait une cité que le serveur refuse — ou pire, le
# serveur en accepterait une que le client n'offre pas.

from utils.lieux import cites_de_depart, est_cite_de_depart

# Getter permissif : TOUT doc demandé existe. C'est donc le disque seul qui décide, ce qui
# rend le test indépendant du contenu réellement importé en base.
TOUT_EXISTE = lambda doc_id: {"_id": doc_id, "type": "lieu"}
RIEN_EXISTE = lambda doc_id: None


def test_une_cite_de_depart_a_une_image_start_et_un_doc_lieu():
	cites = cites_de_depart(TOUT_EXISTE)
	assert cites, "aucune image `*_start_*` dans templates/resources/towns"
	for c in cites:
		assert c["id"] == "lieu:" + c["label"]
		assert "_start_" in c["filename"]


def test_sans_doc_lieu_aucune_cite_nest_proposee():
	"""L'image ne suffit pas : le doc `lieu:<nom>` doit exister. Sinon la création
	enverrait le personnage dans un lieu introuvable."""
	assert cites_de_depart(RIEN_EXISTE) == []


def test_le_client_et_le_serveur_proposent_la_MEME_liste():
	for c in cites_de_depart(TOUT_EXISTE):
		assert est_cite_de_depart(c["id"], TOUT_EXISTE)


def test_un_lieu_qui_existe_mais_sans_image_start_est_refuse():
	"""Le cœur de la garde : `get_doc` répond pour TOUT id ici, donc seul le nommage
	`_start_` distingue une cité de départ d'une boutique ou d'une salle de donjon."""
	assert est_cite_de_depart("lieu:le_saloir", TOUT_EXISTE) is False
	assert est_cite_de_depart("lieu:donjon_mine", TOUT_EXISTE) is False


def test_une_cite_vide_ou_absente_est_refusee():
	"""⚠️ Le cas qui a créé un personnage hors du monde : `get_doc("")` ne rend PAS None
	(couchdb2 interroge alors la racine de la base et rend son document d'info)."""
	for cite in ("", None, 0, [], {"id": "lieu:auxerre"}):
		assert est_cite_de_depart(cite, TOUT_EXISTE) is False
