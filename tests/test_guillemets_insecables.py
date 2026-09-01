# tests/test_guillemets_insecables.py
# Typographie des guillemets français, posée AU RENDU du dialogue et jamais dans la donnée.
#
# ⚠️ Le point le plus important de ce fichier : le caractère produit doit être U+00A0, PAS
# l'entité `&nbsp;`. Le texte du nœud est écrit par le client en `textContent`
# (`renderPnjNoeud`, play_town_telluris.html) — une entité HTML y serait affichée en toutes
# lettres. Les libellés de choix, eux, partent en `innerHTML`. Seul le caractère rend
# correctement dans les DEUX chemins.

from utils import pnj


NBSP = " "


def _ctx(**placeholders):
	return {"prenom": "Greta", "placeholders": dict(placeholders)}


# ── La transformation elle-même ─────────────────────────────────────────────────

def test_les_guillemets_collent_a_ce_qu_ils_encadrent():
	assert pnj._espaces_insecables("« Bonjour »") == f"«{NBSP}Bonjour{NBSP}»"
	assert pnj._espaces_insecables("Il dit : « entrez », puis se tait.") \
		== f"Il dit : «{NBSP}entrez{NBSP}», puis se tait."


def test_c_est_bien_le_CARACTERE_et_jamais_l_entite():
	"""⚠️ `&nbsp;` s'afficherait littéralement dans le texte du nœud (écrit en
	`textContent`). C'est la seule raison pour laquelle cette constante existe."""
	assert pnj.ESPACE_INSECABLE == " "
	rendu = pnj._espaces_insecables("« Ah »")
	assert "&nbsp;" not in rendu
	assert " " in rendu


def test_idempotent():
	"""Un texte déjà pourvu d'insécables (ou repassé deux fois) ne bouge plus : après la
	première passe il ne reste aucune espace ORDINAIRE adjacente à un guillemet."""
	une = pnj._espaces_insecables("« Bonjour »")
	assert pnj._espaces_insecables(une) == une


def test_ne_touche_que_les_espaces_ADJACENTES():
	# Guillemets déjà collés : rien à faire.
	assert pnj._espaces_insecables("«Bonjour»") == "«Bonjour»"
	# Espaces ailleurs dans la phrase : intactes.
	assert pnj._espaces_insecables("un deux trois") == "un deux trois"
	# Un guillemet en toute fin, sans espace avant, n'est pas concerné.
	assert pnj._espaces_insecables("Il cria «") == "Il cria «"


def test_texte_vide_ou_absent():
	assert pnj._espaces_insecables("") == ""
	assert pnj._espaces_insecables(None) is None


# ── Le chokepoint de rendu ──────────────────────────────────────────────────────

def test_applique_APRES_la_substitution_des_placeholders():
	"""Un placeholder qui injecte des guillemets doit en bénéficier — c'est le cas des
	qualificatifs de chasse (« Impitoyable ») et des enseignes."""
	rendu = pnj._substituer("La bête dite {espece}.", _ctx(espece='le Loup « Impitoyable »'),
							None)
	assert rendu == f"La bête dite le Loup «{NBSP}Impitoyable{NBSP}»."


def test_le_prenom_injecte_ne_casse_pas_la_typographie():
	assert pnj._substituer("« Bonjour, {prenom}. »", _ctx(), None) \
		== f"«{NBSP}Bonjour, Greta.{NBSP}»"


def _doc():
	return {
		"_id": "pnj:test", "type": "pnj", "nom": "Test",
		"dialogue": {
			"noeud_depart": "accueil",
			"noeuds": {
				"accueil": {
					"texte": "« Entrez donc, {prenom}. »",
					"choix": [{"id": "a", "label": "« Merci. »", "next": "fin"}],
				},
			},
		},
	}


def test_le_TEXTE_du_noeud_ET_les_LIBELLES_sont_traites():
	"""Les deux passent par `_substituer` — et les deux atteignent le joueur par des chemins
	différents (`textContent` / `innerHTML`), d'où l'exigence du caractère."""
	ctx = pnj.contexte_dialogue({"prenom": "Greta"}, _doc(), lambda _l: 50)
	vue = pnj.noeud_client(_doc(), "accueil", ctx)
	assert vue["texte"] == f"«{NBSP}Entrez donc, Greta.{NBSP}»"
	assert vue["choix"][0]["label"] == f"«{NBSP}Merci.{NBSP}»"


def test_la_DONNEE_n_est_jamais_modifiee():
	"""« lors du rendu, pas dans la donnée » : le doc doit ressortir intact, sans quoi une
	sauvegarde ultérieure persisterait la typographie et /admin deviendrait illisible."""
	doc = _doc()
	ctx = pnj.contexte_dialogue({"prenom": "Greta"}, doc, lambda _l: 50)
	pnj.noeud_client(doc, "accueil", ctx)
	noeud = doc["dialogue"]["noeuds"]["accueil"]
	assert noeud["texte"] == "« Entrez donc, {prenom}. »"
	assert noeud["choix"][0]["label"] == "« Merci. »"
	assert NBSP not in str(doc)
