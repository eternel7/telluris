// dev/test_saut_client.js
//
// Tests d'EXÉCUTION du ciblage de SAUT côté client (combat_telluris.html).
//
//   node dev/test_saut_client.js     # sort en code 1 au premier échec
//
// POURQUOI : le saut est le SEUL ciblage de la page qui porte sur une CASE et non sur un
// acteur. Tout le reste du combat désigne des jetons ou des badges ; ici le joueur clique
// le sol. Deux choses peuvent donc mal tourner en silence, et aucune ne se voit dans les
// tests Python :
//   • la liste des cases offertes (miroir de `_verifier_saut`) — offrir une case que le
//     serveur refusera fait payer un clic pour un message d'erreur ;
//   • le PARCOURS du mode `pendingSaut` — cases rangées dans le bon registre, effacées au
//     bon moment, et surtout `pointer-events` rouvert (le calque `#tokens-layer` est en
//     `none`, c'est l'oubli qui a longtemps rendu `.ally-token.spellcast` muet).
//
// MÉTHODE : extraction par NOM depuis le template puis `vm.runInThisContext`, exactement
// comme dev/test_zones_effet_client.js — renommer une de ces fonctions fait échouer ici, et
// c'est voulu. `runInThisContext` et non `createContext` : un contexte séparé est un autre
// realm, donc `deepStrictEqual` refuserait ses tableaux.
//
// HORS DE PORTÉE (à vérifier en jeu) : le RENDU — la trigonométrie de `_placerToken` (ici
// un espion), la superposition des calques, et le fait qu'une case d'arrivée soit bien
// cliquable au doigt par-dessus un jeton (c'est ce que règle `z-index: 2`).

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'combat_telluris.html');
const srcTpl = fs.readFileSync(TEMPLATE, 'utf8');
const jsTpl = (srcTpl.match(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/i) || [])[1];
assert.ok(jsTpl, 'aucun bloc <script> inline dans ' + TEMPLATE);

// `caseFranchissable` (règle de terrain partagée) vient du script de déplacement, comme
// dans la page : `cellWalkable` s'appuie dessus.
const DEPL = path.join(__dirname, '..', 'templates', 'scripts', 'deplacement.js');
vm.runInThisContext(fs.readFileSync(DEPL, 'utf8'), { filename: DEPL });
const JETONS = path.join(__dirname, '..', 'templates', 'scripts', 'jetons.js');
vm.runInThisContext(fs.readFileSync(JETONS, 'utf8'), { filename: JETONS });

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

function extraire(nom) {
	const debut = jsTpl.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable dans le template');
	let prof = 0;
	for (let j = jsTpl.indexOf('{', debut); j < jsTpl.length; j++) {
		if (jsTpl[j] === '{') prof++;
		else if (jsTpl[j] === '}' && --prof === 0) return jsTpl.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}

// ── DOM et état factices ────────────────────────────────────────────────────────

function elementFactice() {
	const el = { className: '', style: {}, enfants: [], parent: null, onclick: undefined };
	el.appendChild = (c) => { c.parent = el; el.enfants.push(c); return c; };
	el.remove = () => {
		if (!el.parent) return;
		el.parent.enfants = el.parent.enfants.filter(c => c !== el);
		el.parent = null;
	};
	return el;
}
const LAYER = elementFactice();
globalThis.document = { createElement: () => elementFactice(),
						getElementById: (id) => (id === 'tokens-layer' ? LAYER : null) };

const PLACEMENTS = [];
globalThis._placerToken = (el, wx, wy) => {
	assert.strictEqual(el.parent, null, 'placé AVANT insertion : pas de transition à la naissance');
	PLACEMENTS.push([wx, wy]);
};

// Grille 9×7, toute praticable sauf un mur vertical en x = 4 (c'est lui qu'un saut franchit).
const DIMS = { x: 9, y: 7 };
const CELLS = [];
for (let y = 0; y < DIMS.y; y++) {
	CELLS.push(Array.from({ length: DIMS.x }, (_, x) => (x === 4 ? 0 : 1)));
}
globalThis.GRID = { dims: DIMS, cells: CELLS };

let MOI = { id: 'joueur_0', pos: { x: 2, y: 3 }, facing: 0, currentPV: 40, currentPM: 40 };
let OCCUPEES = new Set();
globalThis.me = () => MOI;
// Miroirs du moteur, extraits ailleurs dans la page : on ne les réimplémente pas, on les
// stubbe — leur propre exactitude est couverte par test_deplacement_client / test_jetons_client.
globalThis.cellWalkable = (x, y) => {
	if (x < 0 || y < 0 || x >= DIMS.x || y >= DIMS.y) return false;
	return caseFranchissable(CELLS, x, y, false);
};
globalThis.cellOccupied = (x, y) => OCCUPEES.has(x + ',' + y);

const ENVOIS = [];
globalThis.doAction = (...args) => { ENVOIS.push(args); };
globalThis.refreshBadgeTargets = () => {};
globalThis.renderTokens = () => {};

// ⚠️ UN SEUL script : `_apercuZoneCases` et `pendingSaut` sont des liaisons lexicales de
// script, invisibles depuis des fonctions chargées séparément.
vm.runInThisContext([
	'const _apercuZoneCases = [];',
	'let pendingSaut = null;',
	extraire('casesSaut'),
	extraire('peindreCasesSaut'),
	extraire('effacerApercuZone'),
	'globalThis.__setPendingSaut = (v) => { pendingSaut = v; };',
	'globalThis.__getPendingSaut = () => pendingSaut;',
	'globalThis.__casesRestantes = () => _apercuZoneCases.length;',
].join('\n'), { filename: 'combat_telluris.html:saut' });

function armer(portee, extra) {
	const s = Object.assign({ sort_id: 'sort:saut', cible: 'soi', effets: { saut: portee } },
							extra || {});
	__setPendingSaut({ sort: s, composants: [], sauteur: MOI, cible_id: null });
	return s;
}

function cases(portee, extra) { return casesSaut(armer(portee, extra)); }
function ens(liste) { return new Set(liste.map(c => c[0] + ',' + c[1])); }

// ── La liste des cases offertes ─────────────────────────────────────────────────

console.log('\n── Cases offertes (miroir de _verifier_saut) ───────────────────────────────');

t('un saut de portée 1 offre les 8 cases autour (Chebyshev), jamais la sienne', () => {
	MOI = { id: 'joueur_0', pos: { x: 2, y: 3 }, facing: 0 };
	OCCUPEES = new Set();
	const c = cases(1);
	assert.strictEqual(c.length, 8);
	assert.ok(!ens(c).has('2,3'), 'sa propre case ne se propose pas');
	assert.deepStrictEqual(ens(c), ens([[1, 2], [2, 2], [3, 2],
										[1, 3], [3, 3],
										[1, 4], [2, 4], [3, 4]]));
});

t('la portée est bien du Chebyshev (carré), pas du Manhattan', () => {
	MOI = { id: 'joueur_0', pos: { x: 2, y: 3 }, facing: 0 };
	OCCUPEES = new Set();
	assert.ok(ens(cases(2)).has('0,1'), 'le coin du carré de rayon 2 est atteignable');
});

t('le mur est FRANCHI : les cases au-delà sont offertes, celle du mur ne l’est pas', () => {
	MOI = { id: 'joueur_0', pos: { x: 2, y: 3 }, facing: 0 };
	OCCUPEES = new Set();
	const c = ens(cases(4));
	assert.ok(!c.has('4,3'), 'on n’atterrit pas DANS le mur');
	assert.ok(c.has('5,3'), 'mais on saute par-dessus — toute la raison d’être du sort');
	assert.ok(c.has('6,3'));
});

t('une case occupée n’est pas offerte', () => {
	MOI = { id: 'joueur_0', pos: { x: 2, y: 3 }, facing: 0 };
	OCCUPEES = new Set(['3,3']);
	assert.ok(!ens(cases(2)).has('3,3'));
	assert.ok(ens(cases(2)).has('3,2'), 'les voisines restent offertes');
});

t('les cases hors grille sont écartées', () => {
	MOI = { id: 'joueur_0', pos: { x: 0, y: 0 }, facing: 0 };
	OCCUPEES = new Set();
	const c = ens(cases(2));
	assert.ok(![...c].some(k => k.split(',').some(n => Number(n) < 0)));
	assert.ok(!c.has('0,7'), 'y = 7 est hors de la grille 9×7');
});

t('sans `effets.saut`, aucune case (le sort n’est pas un saut)', () => {
	MOI = { id: 'joueur_0', pos: { x: 2, y: 3 }, facing: 0 };
	OCCUPEES = new Set();
	assert.deepStrictEqual(cases(0), []);
});

t('un saut sur ALLIÉ se mesure depuis l’allié, pas depuis le lanceur', () => {
	MOI = { id: 'joueur_0', pos: { x: 0, y: 3 }, facing: 0 };
	OCCUPEES = new Set();
	const brann = { id: 'joueur_1', pos: { x: 6, y: 3 } };
	const s = { sort_id: 'sort:saut', cible: 'allie', effets: { saut: 1 } };
	__setPendingSaut({ sort: s, composants: [], sauteur: brann, cible_id: 'joueur_1' });
	const c = ens(casesSaut(s));
	assert.ok(c.has('6,2'), 'voisine de BRANN');
	assert.ok(!c.has('1,3'), 'et non voisine du lanceur');
});

// ── Le parcours de peinture ─────────────────────────────────────────────────────

console.log('\n── Peinture des cases de destination ───────────────────────────────────────');

t('chaque case offerte donne un élément .zone-case.destination placé en MONDE', () => {
	MOI = { id: 'joueur_0', pos: { x: 2, y: 3 }, facing: 0 };
	OCCUPEES = new Set();
	effacerApercuZone();
	PLACEMENTS.length = 0;
	armer(1);
	peindreCasesSaut();

	assert.strictEqual(LAYER.enfants.length, 8);
	assert.ok(LAYER.enfants.every(e => e.className === 'zone-case destination'),
			  'le modificateur `destination` porte pointer-events/z-index : sans lui, le clic '
			  + 'ne serait jamais reçu (#tokens-layer est en pointer-events:none)');
	// Écarts MONDE relatifs au lanceur, jamais des coordonnées absolues ni de l'écran.
	assert.deepStrictEqual(
		new Set(PLACEMENTS.map(p => p.join(','))),
		new Set(['-1,-1', '0,-1', '1,-1', '-1,0', '1,0', '-1,1', '0,1', '1,1']));
});

t('cliquer une case envoie le sort avec les coordonnées ABSOLUES', () => {
	MOI = { id: 'joueur_0', pos: { x: 2, y: 3 }, facing: 0 };
	OCCUPEES = new Set();
	effacerApercuZone();
	ENVOIS.length = 0;
	armer(1);
	peindreCasesSaut();

	LAYER.enfants.forEach(e => assert.strictEqual(typeof e.onclick, 'function'));
	LAYER.enfants[0].onclick();
	assert.strictEqual(ENVOIS.length, 1);
	const [type, cibleId, dx, dy, sens, mode, extra] = ENVOIS[0];
	assert.strictEqual(type, 'sort');
	assert.strictEqual(cibleId, null, 'un saut sur soi ne désigne aucun acteur');
	assert.ok(Number.isInteger(dx) && Number.isInteger(dy));
	assert.ok(dx >= 0 && dy >= 0, 'coordonnées ABSOLUES, pas des deltas −1..1');
	assert.strictEqual(extra.sort_id, 'sort:saut');
});

t('un saut sur allié envoie SON id en cible', () => {
	MOI = { id: 'joueur_0', pos: { x: 2, y: 3 }, facing: 0 };
	OCCUPEES = new Set();
	effacerApercuZone();
	ENVOIS.length = 0;
	const brann = { id: 'joueur_1', pos: { x: 3, y: 3 } };
	__setPendingSaut({ sort: { sort_id: 'sort:saut', cible: 'allie', effets: { saut: 1 } },
					   composants: [], sauteur: brann, cible_id: 'joueur_1' });
	peindreCasesSaut();
	LAYER.enfants[0].onclick();
	assert.strictEqual(ENVOIS[0][1], 'joueur_1');
});

t('les cases vivent dans le registre d’aperçu, donc s’effacent avec lui', () => {
	MOI = { id: 'joueur_0', pos: { x: 2, y: 3 }, facing: 0 };
	OCCUPEES = new Set();
	effacerApercuZone();
	armer(1);
	peindreCasesSaut();
	assert.ok(__casesRestantes() > 0);

	effacerApercuZone();
	assert.strictEqual(__casesRestantes(), 0);
	assert.strictEqual(LAYER.enfants.length, 0,
					   'renderTokens efface ce registre en tête : une case oubliée resterait '
					   + 'cliquable et lancerait un sort déjà abandonné');
});

t('sans pendingSaut, peindreCasesSaut ne peint rien', () => {
	effacerApercuZone();
	__setPendingSaut(null);
	peindreCasesSaut();
	assert.strictEqual(LAYER.enfants.length, 0);
});

t('repeindre ne double pas les cases', () => {
	MOI = { id: 'joueur_0', pos: { x: 2, y: 3 }, facing: 0 };
	OCCUPEES = new Set();
	effacerApercuZone();
	armer(1);
	peindreCasesSaut();
	const n = LAYER.enfants.length;
	effacerApercuZone();
	peindreCasesSaut();
	assert.strictEqual(LAYER.enfants.length, n);
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).\n`);
process.exit(echecs ? 1 : 0);
