// dev/test_provocation_client.js
//
// Tests d'EXÉCUTION de l'exception « provoquer à distance même engagé » côté client
// (combat_telluris.html) — miroir de `sorts.provocation_pure` / garde `est_a_distance`.
//
//   node dev/test_provocation_client.js     # sort en code 1 au premier échec
//
// POURQUOI : `sortTargets` décide quelles cibles la case d'une capacité offre. S'il refuse
// une provocation pure engagé, la case est grisée alors que le serveur l'accepterait ; s'il
// accepte une frappe à distance engagé, le joueur paie un clic pour un refus.
//
// MÉTHODE : extraction par NOM depuis le template puis `vm.runInThisContext` (cf.
// dev/test_saut_client.js) ; les voisins (`me`, `capaPortee`, `isEngaged`, `chebyJM`,
// `vueActeurs`) sont des bouchons posés en globales.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

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

vm.runInThisContext(extraire('capaProvocationPure') + '\n' + extraire('sortTargets'),
					{ filename: TEMPLATE });

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

// Le joueur en (5,5), un loup au contact (6,5), un autre loin (9,5) ; portée 6, à distance.
const LOIN = { id: 'monstre_1', vivant: true, pos: { x: 9, y: 5 } };
global.state = { monstres: [{ id: 'monstre_0', vivant: true, pos: { x: 6, y: 5 } }, LOIN] };
global.me = () => ({ pos: { x: 5, y: 5 } });
global.capaPortee = () => ({ portee: 6, ranged: true });
global.chebyJM = (j, m) => Math.max(Math.abs(j.pos.x - m.pos.x), Math.abs(j.pos.y - m.pos.y));
global.isEngaged = () => true;
global.vueActeurs = (j, m) => m !== LOIN || global.vueSurLoin;
global.vueSurLoin = true;

const PROVOCATION = { effets: { provocation: 1, duree: 2 } };

t('une provocation pure se lance engagé', () => {
	assert.deepStrictEqual(sortTargets(PROVOCATION).map(m => m.id), ['monstre_0', 'monstre_1']);
});

t('une frappe à distance engagé reste interdite', () => {
	assert.deepStrictEqual(sortTargets({ effets: { degats: '2D6' } }), []);
});

t('une provocation qui porte des dégâts n\'est PAS pure : interdite engagé', () => {
	assert.deepStrictEqual(sortTargets({ effets: { provocation: 1, degats: '1D6', duree: 2 } }), []);
	assert.deepStrictEqual(sortTargets({ effets: { provocation: 1, degats_pm: '1D6', duree: 2 } }), []);
});

t('la ligne de vue reste exigée pour une provocation pure', () => {
	global.vueSurLoin = false;
	assert.deepStrictEqual(sortTargets(PROVOCATION).map(m => m.id), ['monstre_0']);
	global.vueSurLoin = true;
});

console.log(`\n${passes} passé(s), ${echecs} échec(s)`);
process.exit(echecs ? 1 : 0);
