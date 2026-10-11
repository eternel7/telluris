// dev/test_passages_client.js
//
// Tests d'EXÉCUTION du halo de proximité des passages d'une carte de pays
// (play_town_telluris.html).
//
//   node dev/test_passages_client.js     # sort en code 1 au premier échec
//
// POURQUOI : `passagesProches` décide quels marqueurs pulsent et quels toasts partent ; une
// borne fausse (`<` au lieu de `<=`, distance euclidienne au lieu de Tchebychev) ne se voit
// qu'en jeu, en marchant jusqu'au bon endroit.
//
// MÉTHODE : extraction par NOM depuis le template puis `vm.runInThisContext` (cf.
// dev/test_saut_client.js).
//
// HORS DE PORTÉE (à vérifier en jeu) : le voile (canvas), la position des marqueurs et leur
// glissement avec la carte (règle CSS partagée avec #bg-image).

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'play_town_telluris.html');
const src = fs.readFileSync(TEMPLATE, 'utf8');

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

function extraire(nom) {
	const debut = src.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable dans le template');
	let prof = 0;
	for (let j = src.indexOf('{', debut); j < src.length; j++) {
		if (src[j] === '{') prof++;
		else if (src[j] === '}' && --prof === 0) return src.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}

vm.runInThisContext(extraire('passagesProches'));

const P = [
	{ x: 10, y: 10, label: 'a' },
	{ x: 13, y: 7, label: 'diagonale à 3' },
	{ x: 14, y: 10, label: 'à 4' },
];

t('Tchebychev : la diagonale à 3 cases est proche', () => {
	assert.deepStrictEqual(passagesProches(P, 10, 10, 3).map(p => p.label), ['a', 'diagonale à 3']);
});
t('la borne est INCLUSE', () => {
	assert.deepStrictEqual(passagesProches(P, 11, 10, 3).map(p => p.label), ['a', 'diagonale à 3', 'à 4']);
});
t('rayon 0 : seulement la case même', () => {
	assert.deepStrictEqual(passagesProches(P, 14, 10, 0).map(p => p.label), ['à 4']);
});
t('liste vide ou absente', () => {
	assert.deepStrictEqual(passagesProches([], 0, 0, 3), []);
	assert.deepStrictEqual(passagesProches(null, 0, 0, 3), []);
});

vm.runInThisContext(extraire('directionFrontiere'));

// Voile 5×5 : colonne de droite voilée (frontière à l'est).
const EST = ['00001', '00001', '00001', '00001', '00001'];
t('frontière à l\'est → 0°', () => {
	assert.strictEqual(Math.round(directionFrontiere(EST, 2, 2, 2)), 0);
});
t('le hors-carte compte comme frontière (bord nord) → -90°', () => {
	const vide = ['00000', '00000', '00000', '00000', '00000'];
	assert.strictEqual(Math.round(directionFrontiere(vide, 2, 0, 1)), -90);
});
t('rien dans le rayon → null (passage intérieur)', () => {
	const vide = ['00000', '00000', '00000', '00000', '00000'];
	assert.strictEqual(directionFrontiere(vide, 2, 2, 2), null);
	assert.strictEqual(directionFrontiere(null, 2, 2, 2), null);
});
t('la frontière la plus proche l\'emporte', () => {
	// voilé à l'ouest tout près (x=0), à l'est plus loin (hors carte à x=5) depuis x=1
	const v = ['10000', '10000', '10000', '10000', '10000'];
	const a = directionFrontiere(v, 1, 2, 4);
	assert.ok(Math.abs(Math.abs(a) - 180) < 1, 'attendu ~180°, obtenu ' + a);
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).\n`);
process.exit(echecs ? 1 : 0);
