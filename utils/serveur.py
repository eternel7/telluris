"""Mise à jour du code et redémarrage de FastAPI depuis `/admin` (carte « 🖥 Serveur »).

POURQUOI ICI : même partage que `utils/dev_tools.py` — `main.py` ne garde que des endpoints
minces ; l'exécuteur (`run_fn`) et l'`exec` sont injectés, donc tout se teste sans git réel.

⚠️ **AUCUNE PERTE DE MODIFICATION LOCALE, PAR CONSTRUCTION.** La mise à jour est un
`git merge --ff-only` sur l'amont de la branche courante : jamais de commit de fusion, jamais
de `reset`, de `checkout --`, de `clean` ni de `stash pop`. Avant de fusionner :
  1. instantané de sécurité des modifs SUIVIES (`stash create` + `stash store`) — il ne touche
     PAS l'arbre de travail : c'est une copie récupérable (`git stash list`), rien de plus ;
  2. pré-contrôle : un fichier que l'amont modifie ET qui est modifié / non suivi localement
     → refus AVANT toute écriture, avec la liste. (git refuserait de toute façon d'écraser
     une modif locale ; le pré-contrôle rend le refus lisible.)

⚠️ **JAMAIS RIEN DU CLIENT DANS L'ARGV.** Les commandes sont écrites ici, en LISTE, sans shell.

⚠️ **PROPRIÉTAIRE DU DÉPÔT.** Le conteneur tourne en root alors que le dépôt monté appartient
à l'utilisateur de l'hôte : git y refuserait de travailler (« dubious ownership ») et, pire,
écrirait dans `.git` des objets possédés par root qui casseraient ensuite le git de l'hôte.
D'où git lancé SOUS L'IDENTITÉ du propriétaire de `.git/HEAD` (`_identite`) — pas de la racine :
sur un partage réseau (NAS), le dossier a pu être créé par un autre compte que celui qui fait
tourner git sur l'hôte, et `fetch` échouait alors sur `.git/FETCH_HEAD: Permission denied`.

⚠️ **REDÉMARRAGE = RE-EXEC DU PROCESS** (`os.execv` sur `sys.argv`) : uvicorn repart dans le
même conteneur, sans repasser par l'apt-get + pip du compose. Une NOUVELLE dépendance pip
exige donc toujours de recréer le conteneur. Suppose un uvicorn à process unique, sans
`--reload` ni `--workers` (le compose actuel).
"""

import os
import subprocess
import sys
import tempfile
import threading
import time

# Racine du dépôt (ce fichier est dans utils/) — même définition que `dev_tools.RACINE`.
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Horodatage du process : change à chaque redémarrage — le client sonde jusqu'à le voir bouger.
DEMARRE_A = time.time()

# Commits en retard listés au plus (l'état doit rester lisible sur un téléphone).
COMMITS_MAX = 30
# Fichiers modifiés par une mise à jour renvoyés au plus.
FICHIERS_MAX = 200
# Dossiers Python compilés avant un redémarrage (une erreur de syntaxe y tuerait l'app).
SOURCES_PY = ("main.py", "routers", "utils", "db", "models")

# Identité des commits d'instantané : `stash create` fabrique un commit, et le conteneur n'a
# ni `user.name` ni `user.email` configurés.
_IDENTITE_STASH = ("-c", "user.name=Telluris admin", "-c", "user.email=admin@telluris.invalid")

_VERROU = threading.Lock()


class GitAbsent(RuntimeError):
	"""L'exécutable git n'est pas installé dans le conteneur."""


def _identite(racine=None):
	"""(uid, gid) sous lesquels lancer git : quand on est root, le propriétaire de ce qu'écrit
	le git de l'hôte — `.git/HEAD`, à défaut `.git`, à défaut la racine — s'il n'est pas root ;
	sinon None (on reste soi-même)."""
	if not hasattr(os, "geteuid") or os.geteuid() != 0:
		return None
	racine = racine or RACINE
	for chemin in (os.path.join(racine, ".git", "HEAD"), os.path.join(racine, ".git"), racine):
		try:
			st = os.stat(chemin)
			break
		except OSError:
			continue
	else:
		return None
	if st.st_uid == 0:
		return None
	return st.st_uid, st.st_gid


def diagnostic_droits(racine=None) -> str:
	"""Qui lance git et à qui appartiennent les fichiers qu'un fetch écrit — affiché sous un
	fetch en échec, pour régler les droits du partage sans ouvrir de terminal."""
	racine = racine or RACINE
	euid = os.geteuid() if hasattr(os, "geteuid") else None
	ident = _identite(racine)
	morceaux = [f"process uid={euid}", f"git lancé en uid:gid={ident[0]}:{ident[1]}" if ident else "git lancé sans changer d'identité"]
	for rel in ("", ".git", ".git/HEAD", ".git/FETCH_HEAD", ".git/objects", ".git/refs/remotes"):
		chemin = os.path.join(racine, rel) if rel else racine
		try:
			st = os.stat(chemin)
			morceaux.append(f"{rel or '/'} {st.st_uid}:{st.st_gid} {oct(st.st_mode & 0o7777)}")
		except OSError as e:
			morceaux.append(f"{rel or '/'} ? ({e.strerror})")
	return " · ".join(morceaux)


def executer(argv, timeout=60):
	"""Exécuteur réel : `(code, sortie)` — stdout et stderr fusionnés, jamais d'exception
	sur un code non nul. `GitAbsent` si l'exécutable manque."""
	env = dict(os.environ)
	env["GIT_TERMINAL_PROMPT"] = "0"                       # jamais d'attente d'un mot de passe
	env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"        # ni d'une clé d'hôte à accepter
	kwargs = {}
	ident = _identite()
	if ident:
		kwargs["user"], kwargs["group"] = ident
		# HOME de root illisible pour cet utilisateur : git s'y casserait sur ~/.gitconfig.
		env["HOME"] = tempfile.gettempdir()
		env.pop("XDG_CONFIG_HOME", None)
	try:
		p = subprocess.run(argv, cwd=RACINE, env=env, stdout=subprocess.PIPE,
						   stderr=subprocess.STDOUT, timeout=timeout, **kwargs)
	except FileNotFoundError as e:
		raise GitAbsent(str(e)) from e
	except subprocess.TimeoutExpired:
		return 124, f"délai dépassé ({timeout} s) : {' '.join(a for a in argv[1:] if a != '-c' and '=' not in a)[:80]}"
	return p.returncode, p.stdout.decode("utf-8", "replace")


def _git(*args):
	"""argv git : `safe.directory` en ligne de commande (configuration « protégée », seule
	que git écoute pour ce réglage) au cas où l'identité ne serait pas celle du propriétaire.
	`core.autocrlf=true` : l'arbre est partagé avec le Git for Windows de l'hôte, qui écrit en
	CRLF un dépôt stocké en LF — sans ce réglage, le git du conteneur voit TOUT fichier modifié
	(et un merge réécrirait en LF des fichiers que l'hôte attend en CRLF)."""
	return ["git", "-c", f"safe.directory={RACINE}", "-c", "core.autocrlf=true", *args]


def _ok(run_fn, *args, timeout=60):
	code, out = run_fn(_git(*args), timeout=timeout)
	return code == 0, out


def _z(sortie: str) -> list:
	return [x for x in sortie.split("\0") if x]


def fichiers_locaux(sortie_status_z: str) -> list:
	"""Chemins modifiés / non suivis d'après `git status --porcelain=v1 -z`. Un renommage
	porte DEUX chemins (le nouveau, puis l'ancien en entrée séparée) : les deux comptent."""
	res, morceaux, i = [], sortie_status_z.split("\0"), 0
	while i < len(morceaux):
		m = morceaux[i]
		i += 1
		if len(m) < 4:
			continue
		xy, chemin = m[:2], m[3:]
		res.append({"etat": xy.strip() or xy, "chemin": chemin})
		if "R" in xy or "C" in xy:
			if i < len(morceaux) and morceaux[i]:
				res.append({"etat": xy.strip(), "chemin": morceaux[i]})
			i += 1
	return res


def _commits(run_fn, plage):
	ok, out = _ok(run_fn, "log", "--no-color", f"--max-count={COMMITS_MAX}",
				  "--format=%h %s", plage)
	return [l for l in out.splitlines() if l.strip()] if ok else []


def _branche(run_fn):
	"""(branche, amont) — l'un ou l'autre None (HEAD détaché, pas d'amont)."""
	ok, out = _ok(run_fn, "symbolic-ref", "--quiet", "--short", "HEAD")
	branche = out.strip() if ok and out.strip() else None
	ok, out = _ok(run_fn, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
	amont = out.strip() if ok and out.strip() else None
	return branche, amont


def _head(run_fn):
	ok, out = _ok(run_fn, "log", "-1", "--no-color", "--format=%h%x00%s%x00%ci")
	if not ok:
		return None
	parts = (out.strip().split("\0") + ["", "", ""])[:3]
	return {"hash": parts[0], "titre": parts[1], "date": parts[2]}


def _fetch(run_fn):
	return _ok(run_fn, "fetch", "--quiet", "--prune", timeout=120)


def etat(run_fn=executer, fetch=True, diag_fn=diagnostic_droits) -> dict:
	"""État du dépôt pour la carte : branche, amont, HEAD, fichiers locaux, retard/avance.
	`erreur` seule si git ne peut pas lire le dépôt (droits, pas de `.git` monté…)."""
	ok, out = _ok(run_fn, "rev-parse", "--git-dir")
	if not ok:
		return {"erreur": out.strip()[-800:]}
	branche, amont = _branche(run_fn)
	res = {
		"branche": branche, "amont": amont, "head": _head(run_fn),
		"locaux": [], "retard": None, "avance": None, "commits_retard": [],
		"fetch_ok": None, "fetch_erreur": "",
	}
	ok, out = _ok(run_fn, "status", "--porcelain=v1", "-z", "--untracked-files=all")
	if ok:
		res["locaux"] = fichiers_locaux(out)
	if not amont:
		return res
	if fetch:
		ok, out = _fetch(run_fn)
		res["fetch_ok"] = ok
		if not ok:
			res["fetch_erreur"] = out.strip()[-800:] + " — droits : " + diag_fn()
	ok, out = _ok(run_fn, "rev-list", "--left-right", "--count", "HEAD...@{u}")
	if ok and len(out.split()) == 2:
		res["avance"], res["retard"] = (int(x) for x in out.split())
		res["commits_retard"] = _commits(run_fn, "HEAD..@{u}") if res["retard"] else []
	return res


def mettre_a_jour(run_fn=executer, maintenant=time.time) -> tuple:
	"""`(résultat, erreur)` — erreur = `(statut HTTP, message)`. Non destructif : cf. docstring
	du module. Un seul à la fois (409)."""
	if not _VERROU.acquire(blocking=False):
		return None, (409, "Une mise à jour est déjà en cours.")
	try:
		return _mettre_a_jour(run_fn, maintenant)
	finally:
		_VERROU.release()


def _mettre_a_jour(run_fn, maintenant):
	ok, out = _ok(run_fn, "rev-parse", "--git-dir")
	if not ok:
		return None, (500, "git ne peut pas lire le dépôt : " + out.strip()[-800:])
	branche, amont = _branche(run_fn)
	if not branche:
		return None, (409, "HEAD détaché : aucune branche à mettre à jour.")
	if not amont:
		return None, (409, f"La branche « {branche} » n'a pas d'amont (git branch -u …).")

	ok, out = _fetch(run_fn)
	if not ok:
		return None, (502, "git fetch a échoué : " + out.strip()[-800:])

	ok, out = _ok(run_fn, "rev-list", "--left-right", "--count", "HEAD...@{u}")
	if not ok or len(out.split()) != 2:
		return None, (500, "Impossible de comparer HEAD à l'amont : " + out.strip()[-400:])
	avance, retard = (int(x) for x in out.split())
	avant = _head(run_fn)
	if retard == 0:
		return {"a_jour": True, "avant": avant, "apres": avant, "commits": [], "fichiers": [],
				"instantane": None, "redemarrage_conseille": False}, None
	if avance:
		return None, (409, f"La branche a {avance} commit(s) local(aux) absent(s) de {amont} : "
						   "fusion en avance rapide impossible, rien n'a été modifié.")

	ok, out = _ok(run_fn, "status", "--porcelain=v1", "-z", "--untracked-files=all")
	if not ok:
		return None, (500, "git status a échoué : " + out.strip()[-400:])
	locaux = fichiers_locaux(out)

	ok, out = _ok(run_fn, "diff", "--name-only", "-z", "HEAD", "@{u}")
	if not ok:
		return None, (500, "git diff a échoué : " + out.strip()[-400:])
	amont_modifie = _z(out)
	conflits = sorted({f["chemin"] for f in locaux} & set(amont_modifie))
	if conflits:
		return None, (409, "Mise à jour refusée, rien n'a été modifié : ces fichiers ont des "
						   "changements locaux non commités ET sont modifiés par la mise à jour — "
						   + ", ".join(conflits[:20]) + (" …" if len(conflits) > 20 else ""))

	instantane = None
	if locaux:
		ok, h = _ok(run_fn, *_IDENTITE_STASH, "stash", "create")
		h = h.strip()
		if ok and h:
			stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(maintenant()))
			ok2, out = _ok(run_fn, *_IDENTITE_STASH, "stash", "store", "-m",
						   f"admin-maj {stamp} (instantané avant mise à jour)", h)
			if not ok2:
				return None, (500, "Instantané de sécurité impossible, rien n'a été modifié : "
								   + out.strip()[-400:])
			instantane = h[:12]
		elif not ok:
			return None, (500, "Instantané de sécurité impossible, rien n'a été modifié : "
							   + h[-400:])

	commits = _commits(run_fn, "HEAD..@{u}")
	ok, out = _ok(run_fn, "merge", "--ff-only", "--no-edit", "@{u}")
	if not ok:
		return None, (409, "git merge --ff-only a refusé (arbre de travail intact) : "
						   + out.strip()[-800:])
	return {
		"a_jour": False, "avant": avant, "apres": _head(run_fn), "commits": commits,
		"fichiers": amont_modifie[:FICHIERS_MAX], "nb_fichiers": len(amont_modifie),
		"instantane": instantane,
		# Code Python ET templates : Jinja2 garde ses templates compilés en cache.
		"redemarrage_conseille": bool(amont_modifie),
	}, None


def verifier_code(racine=None, sources=SOURCES_PY) -> list:
	"""Erreurs de syntaxe des sources Python — `compile()` en mémoire : rien n'est écrit, et
	un `import main` n'est pas envisageable (il ouvrirait la connexion CouchDB)."""
	racine = racine or RACINE
	erreurs = []
	for src in sources:
		chemin = os.path.join(racine, src)
		fichiers = [chemin] if os.path.isfile(chemin) else [
			os.path.join(d, f) for d, _, fs in os.walk(chemin) for f in fs if f.endswith(".py")]
		for f in sorted(fichiers):
			try:
				with open(f, "rb") as fh:
					compile(fh.read(), f, "exec")
			except SyntaxError as e:
				erreurs.append(f"{os.path.relpath(f, racine)}:{e.lineno} : {e.msg}")
			except (OSError, ValueError) as e:
				erreurs.append(f"{os.path.relpath(f, racine)} : {e}")
	return erreurs


def argv_redemarrage() -> list:
	"""Même interpréteur, mêmes arguments : `uvicorn main:app --host … --port …`."""
	return [sys.executable, *sys.argv]


def programmer_redemarrage(exec_fn=os.execv, delai=1.0, sleep=time.sleep):
	"""Re-exec du process dans `delai` secondes (la réponse HTTP part d'abord). Les sockets
	Python ne sont pas hérités par l'exec (PEP 446) : le nouvel uvicorn rebinde son port."""
	argv = argv_redemarrage()

	def _go():
		sleep(delai)
		try:
			sys.stdout.flush()
			sys.stderr.flush()
		except Exception:
			pass
		exec_fn(argv[0], argv)

	t = threading.Thread(target=_go, name="telluris-redemarrage", daemon=True)
	t.start()
	return t
