// dev/test_dos_client.js
//
// Tests d'EXÉCUTION du ciblage d'attaque côté client (combat_telluris.html) — miroir de
// `combat._dans_le_dos` / `_peut_frapper` :
//   • ligne de vue pour TOUTE arme (un fouet, mêlée à 2 cases, ne frappe pas à travers un mur) ;
//   • pas de frappe dans le dos : devant et les cases directement à gauche/droite oui, dès
//     une rangée en arrière non ; le `facing` du joueur (0 = Nord) tourne ce devant.
//
//   node dev/test_dos_client.js     # sort en code 1 au premier échec
//
// POURQUOI : `targetableMonsters` décide quelles cibles la case d'attaque offre. S'il propose
// une cible dans le dos ou derrière un mur, le joueur paie un clic pour un refus du serveur.
//
// MÉTHODE : extraction par NOM depuis le template puis `vm.runInThisContext` (cf.
// dev/test_saut_client.js) ; `scripts/jetons.js` est le VRAI script de la page (emprises,
// caps, distance) ; `me`, `attackProfile`, `isEngaged` sont des bouchons posés en globales.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'combat_telluris.html');
const srcTpl = fs.readFileSync(TEMPLATE, 'utf8');
const jsTpl = (srcTpl.match(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/i) || [])[1];
assert.ok(jsTpl, 'aucun bloc <script> inline dans ' + TEMPLATE);

const JETONS = path.join(__dirname, '..', 'templates', 'scripts', 'jetons.js');
vm.runInThisContext(fs.readFileSync(JETONS, 'utf8'), { filename: JETONS });

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

vm.runInThisContext(['rot', 'seeThroughCell', 'lineOfSight', 'vueActeurs', 'chebyJM',
	'axeActeur', 'dansLeDos', 'peutFrapper', 'targetableMonsters'].map(extraire).join('\n'),
	{ filename: TEMPLATE });

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

const FOUET = { mode: 'cac', portee: 2, ranged: false };
// Le joueur en (3,5), orienté au Nord sauf `facing` ; un loup en `xy`.
function scene(xy, facing = 0, mur = null) {
	const j = { id: 'joueur_0', pos: { x: 3, y: 5 }, facing };
	const loup = { id: 'monstre_0', vivant: true, pos: { x: xy[0], y: xy[1] } };
	const cells = Array.from({ length: 9 }, () => Array(12).fill(1));
	if (mur) cells[mur[1]][mur[0]] = 0;
	global.GRID = { dims: { x: 12, y: 9 }, cells };
	global.state = { joueurs: [j], monstres: [loup] };
	global.me = () => j;
	global.attackProfile = () => FOUET;
	global.isEngaged = () => false;
	return { j, loup };
}
const ids = (l) => l.map(m => m.id);

t('un fouet ne propose pas une cible derrière un mur', () => {
	scene([3, 3], 0, [3, 4]);
	assert.deepStrictEqual(ids(targetableMonsters('cac')), []);
});

t('sans mur, le fouet porte à deux cases', () => {
	scene([3, 3]);
	assert.deepStrictEqual(ids(targetableMonsters('cac')), ['monstre_0']);
});

t('devant, sur les côtés et en diagonale avant : proposé', () => {
	for (const xy of [[3, 4], [4, 4], [4, 5], [2, 5], [5, 5]]) {
		scene(xy);
		assert.deepStrictEqual(ids(targetableMonsters('cac')), ['monstre_0'], JSON.stringify(xy));
	}
});

t('une rangée en arrière : jamais proposé', () => {
	for (const xy of [[3, 6], [4, 6], [2, 6], [3, 7]]) {
		scene(xy);
		assert.deepStrictEqual(ids(targetableMonsters('cac')), [], JSON.stringify(xy));
	}
});

t('le facing tourne le devant (quart de tour : le dos passe sur le côté)', () => {
	scene([3, 6], 90);
	assert.deepStrictEqual(ids(targetableMonsters('cac')), ['monstre_0']);
	scene([3, 6], 180);
	assert.deepStrictEqual(ids(targetableMonsters('cac')), ['monstre_0']);
	scene([3, 4], 180);
	assert.deepStrictEqual(ids(targetableMonsters('cac')), []);
});

t('un monstre lit son cap ; un grand jeton se mesure sur son emprise', () => {
	const bete = { id: 'monstre_0', pos: { x: 5, y: 5 }, cap: 'haut', jeton: { largeur: 2, profondeur: 2 } };
	assert.strictEqual(dansLeDos(bete, { pos: { x: 7, y: 6 } }), false);
	assert.strictEqual(dansLeDos(bete, { pos: { x: 5, y: 7 } }), true);
	assert.strictEqual(dansLeDos({ id: 'monstre_1', pos: { x: 5, y: 5 }, cap: 'gauche' },
		{ pos: { x: 6, y: 5 } }), true);
});

console.log(`\n${passes} passé(s), ${echecs} échec(s)`);
process.exit(echecs ? 1 : 0);
