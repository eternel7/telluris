// deplacement.js — RÈGLES DE MARCHE et grisage des flèches, PARTAGÉS entre play_town,
// combat et le mode « test de déplacement » de l'éditeur de carte.
//
// ⚠️ IL N'Y A AUCUNE RÈGLE DE MARCHE CÔTÉ SERVEUR. La branche x/y de `move_character`
// (`routers/user.py`) ne valide QUE les bornes : ni terrain, ni `nav`. Ce fichier ne
// « double » donc pas une règle du serveur — IL EST LA RÈGLE, et `dev/test_deplacement_client.js`
// en est le seul test. (Corollaire : une requête forgée traverse les murs — à traiter avec
// les trous d'auth déjà listés, hors périmètre.)
//
// Chargé en <script> classique (pas de module), APRÈS `nav.js` dont `pasAutoriseLocal`
// dépend (`navAllows`). Ces const/function sont visibles dans le script inline de la page.
//
// TROIS règles de case coexistent dans le jeu, et elles sont VOLONTAIREMENT différentes :
//   • exploration      : `=== 1`            (ce fichier : `caseType1`)
//   • combat / guidage : `>= 1 && != 3`     (ce fichier : `caseFranchissable`)
//   • voile du mode Lieux (éditeur) : `>= 1` (`_caseAccessible`, dans le template)
// Un mode test bâti sur `>= 1` validerait des chemins que le joueur ne peut pas emprunter.

// Terrain « falaise » : franchissable en combat pour un volant seulement.
const TERRAIN_FALAISE = 3;

// Sol « normal » praticable — miroir de `combat._is_type1`. C'est LA RÈGLE D'EXPLORATION
// (destination exactement 1) ET celle du placement initial d'un acteur.
function caseType1(cells, x, y) {
	if (!cells) return false;
	const row = cells[y];
	return !!row && row[x] === 1;
}

// Miroir de `combat._walkable` : praticable (>= 1) et, sauf vol, pas une falaise.
// C'est la règle du COMBAT et celle du flood fill de placement (`_reachable_region`).
function caseFranchissable(cells, x, y, volant) {
	if (!cells) return true;
	const row = cells[y];
	if (!row || !(row[x] >= 1)) return false;
	return !!volant || row[x] !== TERRAIN_FALAISE;
}

// Le pas (dx,dy) depuis (x,y) est-il permis EN EXPLORATION ?
//
// ⚠️ Rend un MOTIF, pas un booléen. Toute la valeur du mode test est de répondre à
// « POURQUOI cette flèche est-elle grise ? » — un booléen jette justement la seule
// information qu'on est venu chercher. play_town ignore `raison`, l'éditeur l'affiche.
function pasAutoriseLocal(cells, nav, dims, x, y, dx, dy) {
	// Bornes en `< cols` : `cells` s'indexe 0..dim-1. (⚠️ Le garde serveur, lui, teste
	// `<= dimensions.x` — borne INCLUSIVE, donc une colonne hors grille y passe. Défaut
	// connu, documenté dans `utils/chasse.py` ; on suit ici ce que le joueur peut cliquer.)
	const nx = x + dx, ny = y + dy;
	if (!dims || nx < 0 || nx >= dims.x || ny < 0 || ny >= dims.y) {
		return { ok: false, raison: 'hors carte' };
	}
	if (!caseType1(cells, nx, ny)) {
		const row = (cells || [])[ny];
		const v = row ? row[nx] : undefined;
		return { ok: false, raison: v === undefined ? 'case absente de cells' : `terrain ${v}` };
	}
	// ⚠️ `nav` est BIDIRECTIONNEL (`getFinalMask` vérifie la source ET la cible) : toujours
	// passer par `navAllows` de nav.js, jamais par un `mask & bit` maison.
	if (!navAllows(nav, x, y, dx, dy)) return { ok: false, raison: 'mur nav' };
	return { ok: true, raison: '' };
}

// Grisage des flèches d'un pavé — LE SEUL JOINT partagé par les trois pages.
//
// ⚠️ Prend des PRÉDICATS, pas des données : play_town lit un masque et une matrice d'accès
// RÉSOLUS PAR LE SERVEUR (`ACCESS.access` / `ACCESS.nav`), le combat interroge son état de
// partie, l'éditeur lit `cells`/`nav` en local. Lui passer une grille obligerait play_town à
// en reconstruire une qu'il n'a pas. Ce qui est mutualisé, c'est le PARCOURS DU DOM —
// précisément ce qui était écrit deux fois dans play_town.
//
// ⚠️ `exergue` est OPTIONNEL : absent ⇒ `.btn-highlight` n'est pas touchée. Ni le combat ni
// l'éditeur n'ont de guidage, et l'éditeur ne définit même pas cette classe.
//
// ⚠️ `data-sdx`/`data-sdy` sont des directions d'ÉCRAN : on les repasse telles quelles au
// prédicat de la page, sans jamais les interpréter ici — les interpréter ferait mentir les
// flèches dès que la caméra de combat pivote.
function majFleches(racine, opts) {
	const o = opts || {};
	const scope = racine || document;
	scope.querySelectorAll('[data-sdx]').forEach(btn => {
		const dx = parseInt(btn.dataset.sdx, 10);
		const dy = parseInt(btn.dataset.sdy, 10);
		const r = o.autorise ? o.autorise(dx, dy, btn) : { ok: true };
		const ok = (r && typeof r === 'object') ? !!r.ok : !!r;
		btn.disabled = !ok;
		if (o.exergue) {
			btn.classList.toggle('btn-highlight', ok && !!o.exergue(dx, dy, btn));
		}
	});
}

// Verrouille (ou rouvre) toutes les flèches d'un pavé — le temps d'une requête en vol.
function verrouillerFleches(racine, bloque) {
	(racine || document).querySelectorAll('[data-sdx]').forEach(b => { b.disabled = !!bloque; });
}
