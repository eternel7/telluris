// dev/test_jetons_client.js
//
// Tests d'EXÉCUTION du miroir client des jetons de taille variable (templates/scripts/jetons.js).
//
//   node dev/test_jetons_client.js     # sort en code 1 au premier échec
//
// POURQUOI : la vérité est au serveur (utils/jetons.py), mais le client s'en sert pour DÉCIDER
// ce qui est cliquable — cibles à portée, flèches grisées, ancre de l'aperçu de zone. Un écart
// ferait proposer une attaque que le serveur refuse, ou griser un pas qu'il accepte. Les cas
// d'emprise, de distance, de case proche et de centre sont donc les MÊMES que ceux de
// tests/test_jetons.py, valeurs comprises.
//
// MÉTHODE : comme test_zones_effet_client, on charge DIRECTEMENT le `.js` (runInThisContext :
// même realm, `deepStrictEqual` accepte ses tableaux). La dernière section extrait EN PLUS
// `cellOccupied` / `occupantEchangeable` / `vueActeurs` de combat_telluris.html et les joue
// contre un `state` semé — la règle de TRAVERSÉE d'un grand allié non jouable, miroir de
// `_occupied_set(traversant=…)`.
//
// HORS DE PORTÉE (à vérifier en jeu) : le RENDU des gabarits (`_placerGabarit`, clip-path des
// triangles, contre-rotation du portrait).

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const SCRIPTS = path.join(__dirname, '..', 'templates', 'scripts');
['nav.js', 'deplacement.js', 'jetons.js'].forEach(nom => {
	const f = path.join(SCRIPTS, nom);
	assert.ok(fs.existsSync(f), 'fichier introuvable : ' + f);
	vm.runInThisContext(fs.readFileSync(f, 'utf8'), { filename: f });
});

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

function acteur(x, y, taille, forme, cap) {
	const a = { pos: { x: x, y: y } };
	const j = (taille || forme) ? normaliserJeton({ taille: taille, forme: forme }) : null;
	if (j) a.jeton = j;
	if (cap) a.cap = cap;
	return a;
}
function dragon(x, y, cap) { return acteur(x === undefined ? 2 : x, y === undefined ? 2 : y, '3x2', 'triangle', cap || 'bas'); }

console.log('\n── Normalisation ───────────────────────────────────────────────────────────');

t('absent ou 1x1 rond ⇒ null (aucune migration)', () => {
	assert.strictEqual(normaliserJeton(null), null);
	assert.strictEqual(normaliserJeton({}), null);
	assert.strictEqual(normaliserJeton({ taille: '1x1' }), null);
	assert.strictEqual(normaliserJeton('3x2'), null);
});

t('gabarit normalisé, forme par défaut', () => {
	assert.deepStrictEqual(normaliserJeton({ taille: '3x2' }), { largeur: 3, profondeur: 2, forme: 'ellipse' });
	assert.deepStrictEqual(normaliserJeton({ taille: '2×2', forme: 'TRIANGLE' }),
		{ largeur: 2, profondeur: 2, forme: 'triangle' });
});

t('taille inconnue ⇒ 1x1, forme seule gardée', () => {
	assert.strictEqual(normaliserJeton({ taille: '4x4' }), null);
	assert.deepStrictEqual(normaliserJeton({ taille: '4x4', forme: 'triangle' }),
		{ largeur: 1, profondeur: 1, forme: 'triangle' });
	assert.strictEqual(normaliserJeton({ taille: '2x2', forme: 'etoile' }).forme, 'ellipse');
});

console.log('\n── Emprise ─────────────────────────────────────────────────────────────────');

t('l’emprise suit le cap (la profondeur suit la marche)', () => {
	assert.deepStrictEqual(empriseActeur(dragon(2, 2, 'bas')), [2, 2, 3, 2]);
	assert.deepStrictEqual(empriseActeur(dragon(2, 2, 'haut')), [2, 2, 3, 2]);
	assert.deepStrictEqual(empriseActeur(dragon(2, 2, 'droite')), [2, 2, 2, 3]);
	assert.deepStrictEqual(empriseActeur(dragon(2, 2, 'gauche')), [2, 2, 2, 3]);
	assert.deepStrictEqual(empriseActeur({ pos: { x: 2, y: 2 }, jeton: { largeur: 3, profondeur: 2 } }),
		[2, 2, 3, 2], 'cap absent ⇒ bas');
	assert.deepStrictEqual(empriseActeur(acteur(2, 2)), [2, 2, 1, 1]);
});

t('cases et couverture', () => {
	const d = dragon();
	assert.deepStrictEqual(casesActeur(d), [[2, 2], [3, 2], [4, 2], [2, 3], [3, 3], [4, 3]]);
	assert.strictEqual(couvreActeur(d, 4, 3), true);
	assert.strictEqual(couvreActeur(d, 5, 3), false);
	assert.strictEqual(estGrand(d), true);
	assert.strictEqual(estGrand(acteur(0, 0, null, 'triangle')), false);
});

t('distance 1x1 = l’ancien écart case à case', () => {
	[[0, 0, 3, 1], [5, 5, 5, 5], [2, 7, 0, 0], [1, 1, 2, 2]].forEach(c => {
		assert.strictEqual(distanceActeurs(acteur(c[0], c[1]), acteur(c[2], c[3])),
			Math.max(Math.abs(c[0] - c[2]), Math.abs(c[1] - c[3])));
	});
});

t('distance entre emprises : un grand jeton se touche par n’importe quel bord', () => {
	const d = dragon();
	assert.strictEqual(distanceActeurs(d, acteur(5, 4)), 1);
	assert.strictEqual(distanceActeurs(acteur(5, 4), d), 1);
	assert.strictEqual(distanceActeurs(d, acteur(6, 2)), 2);
	assert.strictEqual(distanceActeurs(d, acteur(3, 3)), 0);
	assert.strictEqual(distanceActeurs(d, acteur(1, 1)), 1);
	assert.strictEqual(distanceActeurs(d, acteur(0, 5)), 2);
	assert.strictEqual(distanceActeurs(d, acteur(5, 1, '2x2')), 1, 'deux grands jetons au contact');
	assert.strictEqual(distanceActeurs(d, acteur(6, 1, '2x2')), 2);
});

t('case la plus proche et centre', () => {
	const d = dragon();
	assert.deepStrictEqual(caseProche(d, 0, 0), [2, 2]);
	assert.deepStrictEqual(caseProche(d, 3, 10), [3, 3]);
	assert.deepStrictEqual(caseProche(d, 9, 2), [4, 2]);
	assert.deepStrictEqual(caseProche(acteur(5, 5), 0, 0), [5, 5]);
	assert.deepStrictEqual(centreActeur(d), [3, 2.5]);
	assert.deepStrictEqual(centreActeur(acteur(4, 1)), [4, 1]);
});

console.log('\n── Occupation et traversée (combat_telluris.html) ──────────────────────────');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'combat_telluris.html');
const srcTpl = fs.readFileSync(TEMPLATE, 'utf8');
const jsTpl = (srcTpl.match(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/i) || [])[1];
assert.ok(jsTpl, 'aucun bloc <script> inline dans ' + TEMPLATE);

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

globalThis.GRID = { dims: { x: 9, y: 9 }, cells: Array.from({ length: 9 }, () => Array(9).fill(1)) };
globalThis.state = { joueurs: [], monstres: [] };
vm.runInThisContext(['cellOccupied', 'occupantEchangeable', 'lineOfSight', 'seeThroughCell', 'vueActeurs']
	.map(extraire).join('\n'), { filename: 'combat_telluris.html:jetons' });

const GRAND = { largeur: 2, profondeur: 2, forme: 'ellipse' };

t('toutes les cases d’un monstre vivant bloquent', () => {
	state.joueurs = [{ id: 'joueur_0', pos: { x: 5, y: 3 }, currentPV: 50 }];
	state.monstres = [Object.assign(dragon(), { id: 'monstre_0', vivant: true })];
	assert.strictEqual(cellOccupied(4, 3), true);
	assert.strictEqual(cellOccupied(2, 2), true);
	assert.strictEqual(cellOccupied(5, 2), false);
	state.monstres[0].vivant = false;
	assert.strictEqual(cellOccupied(4, 3), false, 'une carcasse ne bloque rien');
});

t('un grand allié NON JOUABLE se traverse, un 1x1 reste un occupant', () => {
	state.monstres = [];
	state.joueurs = [
		{ id: 'joueur_0', pos: { x: 2, y: 2 }, currentPV: 50 },
		{ id: 'joueur_1', pos: { x: 3, y: 2 }, currentPV: 50, jouable: false, jeton: GRAND },
		{ id: 'joueur_2', pos: { x: 6, y: 6 }, currentPV: 50, jouable: false },
	];
	assert.strictEqual(cellOccupied(4, 3), false, 'le cheval 2x2 se traverse');
	assert.strictEqual(cellOccupied(6, 6), true, 'l’âne 1x1 occupe (il s’échange)');
	state.joueurs[1].jouable = undefined;
	assert.strictEqual(cellOccupied(4, 3), true, 'un grand acteur JOUABLE bloque');
});

t('échange 1x1 accepté, refusé avec un grand allié ou depuis l’intérieur de l’un d’eux', () => {
	const j = { id: 'joueur_0', pos: { x: 3, y: 2 }, currentPV: 50 };
	state.joueurs = [
		j,
		{ id: 'joueur_1', pos: { x: 3, y: 2 }, currentPV: 50, jouable: false, jeton: GRAND },
		{ id: 'joueur_2', pos: { x: 2, y: 2 }, currentPV: 50, jouable: false },
	];
	assert.strictEqual(occupantEchangeable(j, 2, 2), false, 'le joueur est DANS le cheval');
	assert.strictEqual(occupantEchangeable(j, 4, 3), false, 'un grand allié ne s’échange pas');
	j.pos = { x: 1, y: 2 };
	assert.strictEqual(occupantEchangeable(j, 2, 2), true, 'hors du cheval, l’âne s’échange');
});

t('vueActeurs : au moins une paire de cases se voit', () => {
	GRID.cells = Array.from({ length: 9 }, () => Array(9).fill(1));
	for (let y = 0; y < 3; y++) GRID.cells[y][4] = 0;
	const tireur = { pos: { x: 6, y: 3 } };
	const bete = { pos: { x: 1, y: 2 }, jeton: GRAND };
	assert.strictEqual(vueActeurs(tireur, bete), true);
	GRID.cells[3][4] = 0;
	assert.strictEqual(vueActeurs(tireur, bete), false);
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).\n`);
process.exit(echecs ? 1 : 0);
