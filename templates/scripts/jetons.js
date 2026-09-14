// jetons.js — MIROIR CLIENT de l'emprise des jetons de taille variable (`utils/jetons.py`).
//
// Un grand acteur (dragon 3x2, cheval 1x2…) occupe un RECTANGLE de cases : `pos` en est le
// coin haut-gauche, `jeton` ses dimensions ({largeur, profondeur, forme}) et `cap` la
// direction de marche, qui fait pivoter l'emprise. La VÉRITÉ reste au serveur (portées,
// cases prises, zones) ; ce fichier sert le ciblage, le grisage des flèches et le dessin, qui
// doivent s'accorder avec lui — d'où `dev/test_jetons_client.js`, qui rejoue les mêmes cas
// que `tests/test_jetons.py`.
//
// Aucun pathfinding ici : seul le serveur déplace un grand acteur (les joueurs sont 1x1).
//
// Chargé en <script> classique, sans dépendance. Un acteur SANS `jeton` rend exactement ce
// que rendaient les anciens calculs case à case.

const JETON_TAILLES = { '1x1': [1, 1], '2x1': [2, 1], '1x2': [1, 2], '2x2': [2, 2], '3x2': [3, 2] };
const JETON_FORMES = ['ellipse', 'rectangle', 'triangle'];
const JETON_CAPS = { haut: [0, -1], bas: [0, 1], gauche: [-1, 0], droite: [1, 0] };
const JETON_CAP_DEFAUT = 'bas';
const JETON_DIMENSION_MAX = 3;

// Miroir de `normaliser_jeton` : null = 1x1 rond (comportement d'avant).
function normaliserJeton(raw) {
	if (!raw || typeof raw !== 'object') return null;
	const taille = String(raw.taille || '').trim().toLowerCase().replace('×', 'x');
	const dims = JETON_TAILLES[taille] || [1, 1];
	let forme = String(raw.forme || '').trim().toLowerCase();
	if (JETON_FORMES.indexOf(forme) < 0) forme = '';
	if (dims[0] * dims[1] === 1 && !forme) return null;
	return { largeur: dims[0], profondeur: dims[1], forme: forme || 'ellipse' };
}

function _jetonDimension(v) {
	const n = parseInt(v, 10);
	return isFinite(n) ? Math.max(1, Math.min(JETON_DIMENSION_MAX, n)) : 1;
}

// [largeur, profondeur] d'un snapshot — [1, 1] sans jeton.
function dimsJeton(a) {
	const j = a && a.jeton;
	if (!j || typeof j !== 'object') return [1, 1];
	return [_jetonDimension(j.largeur), _jetonDimension(j.profondeur)];
}

function estGrand(a) {
	const d = dimsJeton(a);
	return d[0] * d[1] > 1;
}

function capDe(a) {
	return (a && JETON_CAPS[a.cap]) ? a.cap : JETON_CAP_DEFAUT;
}

// [w, h] monde : la profondeur suit la marche.
function dimsOrientees(largeur, profondeur, cap) {
	return (cap === 'gauche' || cap === 'droite') ? [profondeur, largeur] : [largeur, profondeur];
}

// [x0, y0, w, h] : le rectangle occupé, coin haut-gauche = `pos`.
function empriseActeur(a) {
	const pos = (a && a.pos) || {};
	const d = dimsJeton(a);
	const wh = dimsOrientees(d[0], d[1], capDe(a));
	return [pos.x | 0, pos.y | 0, wh[0], wh[1]];
}

// Cases de l'emprise, triées par (y, x) comme côté serveur.
function casesActeur(a) {
	const e = empriseActeur(a);
	const out = [];
	for (let y = e[1]; y < e[1] + e[3]; y++) {
		for (let x = e[0]; x < e[0] + e[2]; x++) out.push([x, y]);
	}
	return out;
}

function couvreActeur(a, x, y) {
	const e = empriseActeur(a);
	return x >= e[0] && x < e[0] + e[2] && y >= e[1] && y < e[1] + e[3];
}

function _jetonEcart(a0, aw, b0, bw) {
	return Math.max(0, b0 - (a0 + aw - 1), a0 - (b0 + bw - 1));
}

// Miroir de `distance` : Chebyshev entre EMPRISES (0 = chevauchement, 1 = contact).
function distanceActeurs(a, b) {
	const ea = empriseActeur(a), eb = empriseActeur(b);
	return Math.max(_jetonEcart(ea[0], ea[2], eb[0], eb[2]), _jetonEcart(ea[1], ea[3], eb[1], eb[3]));
}

// Miroir de `case_proche` : la case de l'emprise la plus proche de (x, y).
function caseProche(a, x, y) {
	const e = empriseActeur(a);
	return [Math.max(e[0], Math.min(e[0] + e[2] - 1, x)), Math.max(e[1], Math.min(e[1] + e[3] - 1, y))];
}

// Centre géométrique de l'emprise, en cases (demi-cases possibles) : c'est là que se pose le
// jeton et que visent les animations.
function centreActeur(a) {
	const e = empriseActeur(a);
	return [e[0] + (e[2] - 1) / 2, e[1] + (e[3] - 1) / 2];
}
