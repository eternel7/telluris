"""utils/serveur.py — mise à jour du code et redémarrage depuis /admin.

Verrouille la promesse de la carte « 🖥 Serveur » : AUCUNE modification locale non commitée
n'est perdue. Refus SANS écriture quand un fichier local est touché par l'amont ; jamais
autre chose qu'un `merge --ff-only` ; instantané de sécurité quand l'arbre est sale.
Deux niveaux : un exécuteur factice (séquence des commandes) et un vrai dépôt git temporaire.
"""

import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import serveur as srv


# ── Exécuteur factice ────────────────────────────────────────────────────────

class Faux:
	"""Répond selon la sous-commande git (premier argument après les `-c …`)."""

	def __init__(self, status="", diff="", compte="0\t2", amont="origin/main", stash="abc123"):
		self.appels = []
		self.rep = {"status": status, "diff": diff, "rev-list": compte, "stash": stash}
		self.amont = amont

	def __call__(self, argv, timeout=60):
		self.appels.append(argv)
		assert argv[0] == "git" and argv[1] == "-c" and argv[2].startswith("safe.directory=")
		args = argv[3:]
		while args and args[0] == "-c":
			args = args[2:]
		cmd = args[0]
		if cmd == "symbolic-ref":
			return 0, "main\n"
		if cmd == "rev-parse" and "--git-dir" in args:
			return 0, ".git\n"
		if cmd == "rev-parse":
			return (0, self.amont + "\n") if self.amont else (128, "fatal: no upstream\n")
		if cmd == "log":
			return 0, "abc1234\0titre\x002026-01-01\n" if "-1" in args else "d1 un\nd2 deux\n"
		if cmd == "stash":
			return 0, (self.rep["stash"] + "\n") if args[1] == "create" else ""
		if cmd in self.rep:
			return 0, self.rep[cmd]
		return 0, ""

	def cmds(self):
		out = []
		for a in self.appels:
			args = a[3:]
			while args and args[0] == "-c":
				args = args[2:]
			out.append(args)
		return out


def test_fichiers_locaux_lit_le_format_z_renommages_compris():
	sortie = " M a.py\0?? neuf.txt\0R  nouveau.py\0ancien.py\0"
	assert [f["chemin"] for f in srv.fichiers_locaux(sortie)] == ["a.py", "neuf.txt", "nouveau.py", "ancien.py"]


def test_conflit_local_refuse_sans_merge_ni_stash():
	f = Faux(status=" M main.py\0", diff="main.py\0utils/x.py\0")
	res, err = srv.mettre_a_jour(f)
	assert res is None and err[0] == 409 and "main.py" in err[1]
	assert not any(c[0] in ("merge", "stash") for c in f.cmds())


def test_untracked_ecrase_par_l_amont_est_un_conflit():
	f = Faux(status="?? jsons/neuf.json\0", diff="jsons/neuf.json\0")
	res, err = srv.mettre_a_jour(f)
	assert err[0] == 409
	assert not any(c[0] == "merge" for c in f.cmds())


def test_arbre_sale_sans_conflit_instantane_puis_ff_only():
	f = Faux(status=" M local.py\0", diff="autre.py\0")
	res, err = srv.mettre_a_jour(f)
	assert err is None and res["instantane"] == "abc123"
	cmds = f.cmds()
	i_store = next(i for i, c in enumerate(cmds) if c[:2] == ["stash", "store"])
	i_merge = next(i for i, c in enumerate(cmds) if c[0] == "merge")
	assert i_store < i_merge
	assert "--ff-only" in cmds[i_merge]
	# Jamais une commande qui toucherait l'arbre de travail.
	interdits = {"reset", "checkout", "clean", "pull", "rebase", "restore"}
	assert not any(c[0] in interdits for c in cmds)
	assert not any(c[:2] in (["stash", "pop"], ["stash", "apply"], ["stash", "push"]) for c in cmds)


def test_arbre_propre_pas_d_instantane():
	f = Faux(status="", diff="a.py\0")
	res, err = srv.mettre_a_jour(f)
	assert err is None and res["instantane"] is None
	assert not any(c[0] == "stash" for c in f.cmds())
	assert res["redemarrage_conseille"] is True


def test_divergence_refusee():
	f = Faux(compte="1\t2")
	res, err = srv.mettre_a_jour(f)
	assert err[0] == 409
	assert not any(c[0] == "merge" for c in f.cmds())


def test_deja_a_jour():
	f = Faux(compte="0\t0")
	res, err = srv.mettre_a_jour(f)
	assert err is None and res["a_jour"] is True
	assert not any(c[0] == "merge" for c in f.cmds())


def test_depot_illisible_ni_merge_ni_stash():
	appels = []
	def run(argv, timeout=60):
		appels.append(argv)
		return 128, "fatal: detected dubious ownership\n"
	res, err = srv.mettre_a_jour(run)
	assert err[0] == 500 and "dubious" in err[1] and len(appels) == 1
	assert "dubious" in srv.etat(run)["erreur"]


def test_sans_amont_refuse():
	res, err = srv.mettre_a_jour(Faux(amont=None))
	assert err[0] == 409


def test_verrou_une_seule_mise_a_jour():
	assert srv._VERROU.acquire(blocking=False)
	try:
		res, err = srv.mettre_a_jour(Faux())
		assert err[0] == 409
	finally:
		srv._VERROU.release()


def test_redemarrage_reexec_meme_argv():
	vu = []
	t = srv.programmer_redemarrage(exec_fn=lambda p, a: vu.append((p, a)), delai=0, sleep=lambda s: None)
	t.join(2)
	assert vu == [(sys.executable, [sys.executable, *sys.argv])]


def test_verifier_code_signale_une_erreur_de_syntaxe(tmp_path):
	(tmp_path / "pkg").mkdir()
	(tmp_path / "pkg" / "ok.py").write_text("x = 1\n", encoding="utf-8")
	(tmp_path / "pkg" / "ko.py").write_text("def f(:\n", encoding="utf-8")
	erreurs = srv.verifier_code(str(tmp_path), ("pkg",))
	assert len(erreurs) == 1 and erreurs[0].startswith(os.path.join("pkg", "ko.py"))


def test_verifier_code_du_depot_est_propre():
	assert srv.verifier_code() == []


# ── Vrai dépôt git ───────────────────────────────────────────────────────────

pytestmark_git = pytest.mark.skipif(shutil.which("git") is None, reason="git absent")


def _g(cwd, *args):
	subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
				   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@pytest.fixture
def depots(tmp_path, monkeypatch):
	"""amont (bare) ← auteur (pousse) ; serveur = clone suivi, RACINE pointée dessus."""
	amont, auteur, serveur = tmp_path / "amont.git", tmp_path / "auteur", tmp_path / "serveur"
	subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(amont)], check=True)
	subprocess.run(["git", "clone", "-q", str(amont), str(auteur)], check=True, stderr=subprocess.DEVNULL)
	_g(auteur, "checkout", "-q", "-b", "main")
	(auteur / "a.py").write_text("a = 1\n", encoding="utf-8")
	(auteur / "b.py").write_text("b = 1\n", encoding="utf-8")
	_g(auteur, "add", ".")
	_g(auteur, "commit", "-q", "-m", "init")
	_g(auteur, "push", "-q", "-u", "origin", "main")
	subprocess.run(["git", "clone", "-q", str(amont), str(serveur)], check=True, stderr=subprocess.DEVNULL)
	monkeypatch.setattr(srv, "RACINE", str(serveur))
	return auteur, serveur


def _pousser(auteur, fichier, contenu):
	(auteur / fichier).write_text(contenu, encoding="utf-8")
	_g(auteur, "commit", "-q", "-am", f"maj {fichier}")
	_g(auteur, "push", "-q")


@pytestmark_git
def test_git_reel_modif_locale_conservee(depots):
	auteur, serveur = depots
	_pousser(auteur, "a.py", "a = 2\n")
	(serveur / "b.py").write_text("b = 'local'\n", encoding="utf-8")
	(serveur / "notes.txt").write_text("non suivi\n", encoding="utf-8")

	assert srv.etat()["retard"] == 1
	res, err = srv.mettre_a_jour()
	assert err is None, err
	assert (serveur / "a.py").read_text(encoding="utf-8") == "a = 2\n"
	assert (serveur / "b.py").read_text(encoding="utf-8") == "b = 'local'\n"
	assert (serveur / "notes.txt").read_text(encoding="utf-8") == "non suivi\n"
	assert res["instantane"]
	stash = subprocess.run(["git", "stash", "list"], cwd=serveur, capture_output=True, text=True).stdout
	assert "admin-maj" in stash


@pytestmark_git
def test_git_reel_conflit_refuse_et_rien_ne_bouge(depots):
	auteur, serveur = depots
	_pousser(auteur, "a.py", "a = 2\n")
	(serveur / "a.py").write_text("a = 'local'\n", encoding="utf-8")
	head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=serveur, capture_output=True, text=True).stdout

	res, err = srv.mettre_a_jour()
	assert res is None and err[0] == 409 and "a.py" in err[1]
	assert (serveur / "a.py").read_text(encoding="utf-8") == "a = 'local'\n"
	assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=serveur, capture_output=True, text=True).stdout == head


def test_git_aligne_les_fins_de_ligne_sur_git_for_windows():
	# Sans autocrlf, le conteneur voit modifié tout fichier que l'hôte Windows a écrit en CRLF.
	argv = srv._git("status")
	i = argv.index("core.autocrlf=true")
	assert argv[i - 1] == "-c" and i < argv.index("status")


# ── Identité de git ──────────────────────────────────────────────────────────

def _stat_par_chemin(monkeypatch, proprietaires):
	"""Root simulé ; `os.stat` répond l'uid donné par nom de fichier, OSError s'il est absent."""
	class St:
		def __init__(self, uid):
			self.st_uid, self.st_gid = uid, uid + 1000
	def faux_stat(chemin):
		cle = os.path.basename(chemin) or chemin
		if cle not in proprietaires:
			raise FileNotFoundError(chemin)
		return St(proprietaires[cle])
	monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
	monkeypatch.setattr(os, "stat", faux_stat)


def test_identite_suit_le_git_de_l_hote_pas_la_racine(monkeypatch):
	# Racine créée par un compte du NAS, dépôt manipulé par un autre : c'est ce dernier qui
	# peut écrire `.git/FETCH_HEAD` (le cas « Permission denied » du fetch).
	_stat_par_chemin(monkeypatch, {"depot": 1024, ".git": 1026, "HEAD": 1026})
	assert srv._identite("depot") == (1026, 2026)


def test_identite_repli_sur_la_racine_puis_root(monkeypatch):
	_stat_par_chemin(monkeypatch, {"depot": 1024})
	assert srv._identite("depot") == (1024, 2024)
	_stat_par_chemin(monkeypatch, {"depot": 1024, "HEAD": 0})
	assert srv._identite("depot") is None


# ── Publication d'un dump : branche + PR ─────────────────────────────────────

def test_depot_github_https_et_ssh():
	assert srv.depot_github("https://github.com/eternel7/telluris") == ("eternel7", "telluris")
	assert srv.depot_github("https://x@github.com/eternel7/telluris.git") == ("eternel7", "telluris")
	assert srv.depot_github("git@github.com:eternel7/telluris.git") == ("eternel7", "telluris")
	assert srv.depot_github("/srv/amont.git") is None


def test_nom_branche():
	assert srv.nom_branche("telluris-dump-20260929-101500.json") == "admin/dump-20260929-101500"


def test_jeton_passe_par_l_environnement_jamais_l_argv():
	env = srv._env_auth("secret")
	assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
	assert "secret" not in env["GIT_CONFIG_VALUE_0"]   # encodé base64
	assert srv._env_auth("") == {}


def _publier(serveur, pr_fn=None, token=""):
	contenu = b'{"db": "telluris", "docs": []}'
	return srv.publier_dump(contenu, "telluris-dump-20260929-101500.json", 0,
							pr_fn=pr_fn or (lambda *a: pytest.fail("PR sans jeton")), token=token)


def _sortie(cwd, *args):
	return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout


@pytestmark_git
def test_git_reel_dump_sur_nouvelle_branche_sans_toucher_l_arbre(depots, tmp_path):
	auteur, serveur = depots
	_pousser(auteur, "a.py", "a = 2\n")                     # le main distant a avancé
	(serveur / "b.py").write_text("b = 'local'\n", encoding="utf-8")
	head = _sortie(serveur, "rev-parse", "HEAD")

	res, err = _publier(serveur)
	assert err is None, err
	assert res["branche"] == "admin/dump-20260929-101500" and res["pr_url"] is None
	assert "hors GitHub" in res["pr_erreur"]
	# Arbre de travail, index et branche courante intacts ; aucun dump déposé dans jsons/.
	assert _sortie(serveur, "rev-parse", "HEAD") == head
	assert (serveur / "b.py").read_text(encoding="utf-8") == "b = 'local'\n"
	assert not (serveur / "jsons").exists()
	assert _sortie(serveur, "status", "--porcelain") == " M b.py\n"
	assert not any(p.name == srv._INDEX_TEMP for p in (serveur / ".git").iterdir())
	# La branche distante = main distant + le seul dump.
	amont = tmp_path / "amont.git"
	assert _sortie(amont, "rev-parse", "admin/dump-20260929-101500~1") == _sortie(amont, "rev-parse", "main")
	assert _sortie(amont, "diff", "--name-only", "main", "admin/dump-20260929-101500") \
		== "jsons/telluris-dump-20260929-101500.json\n"
	assert _sortie(amont, "show", "admin/dump-20260929-101500:jsons/telluris-dump-20260929-101500.json") \
		== '{"db": "telluris", "docs": []}'

	res, err = _publier(serveur)
	assert res is None and err[0] == 409                   # la branche existe déjà


@pytestmark_git
def test_git_reel_pr_ouverte_vers_main(depots, monkeypatch):
	auteur, serveur = depots
	monkeypatch.setattr(srv, "depot_github", lambda url: ("o", "r"))
	appels = []

	def pr(proprio, depot, tete, base, titre, corps, token):
		appels.append((proprio, depot, tete, base, token))
		return "https://github.com/o/r/pull/7"

	res, err = _publier(serveur, pr_fn=pr, token="jeton")
	assert err is None, err
	assert res["pr_url"] == "https://github.com/o/r/pull/7"
	assert appels == [("o", "r", "admin/dump-20260929-101500", "main", "jeton")]


@pytestmark_git
def test_git_reel_echec_de_la_pr_n_annule_pas_le_push(depots, monkeypatch):
	auteur, serveur = depots
	monkeypatch.setattr(srv, "depot_github", lambda url: ("o", "r"))

	def pr(*a):
		raise RuntimeError("GitHub a répondu 403")

	res, err = _publier(serveur, pr_fn=pr, token="jeton")
	assert err is None and res["pr_url"] is None and "403" in res["pr_erreur"]
	assert res["compare_url"].endswith("/compare/main...admin/dump-20260929-101500?expand=1")
