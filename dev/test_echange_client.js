// dev/test_echange_client.js
//
// Tests d'EXÉCUTION du ciblage d'un ÉCHANGE DE PLACE côté client (combat_telluris.html) —
// miroir de `combat._verifier_echange` (`effets.echange`, « Attention, messire ! »).
//
//   node dev/test_echange_client.js     # sort en code 1 au premier échec
//
// POURQUOI : `allyTargets` décide quels alliés la case d'une capacité offre en ciblage vert.
// Proposer un allié avec qui le serveur refusera de permuter fait payer un clic pour un
// message d'erreur ; en écarter un valable grise la case à tort.
//
// MÉTHODE : extraction par NOM depuis le template puis `vm.runInThisContext` (cf.
// dev/test_saut_client.js). `echangePossible` (scripts/deplacement.js) et `estGrand` /
// `couvreActeur` (scripts/jetons.js) sont les VRAIS scripts de la page ; les voisins
// (`me`, `capaPortee`, `chebyJM`, `vueActeurs`) sont des bouchons posés en globales.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'combat_telluris.html');
const srcTpl = fs.readFileSync(TEMPLATE, 'utf8');
const jsTpl = (srcTpl.match(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/i) || [])[1];
assert.ok(jsTpl, 'aucun bloc <script> inline dans ' + TEMPLATE);

for (const f of ['deplacement.js', 'jetons.js']) {
	const p = path.join(__dirname, '..', 'templates', 'scripts', f);
	vm.runInThisContext(fs.readFileSync(p, 'utf8'), { filename: p });
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

vm.runInThisContext(extraire('echangeOffert') + '\n' + extraire('allyTargets'), { filename: TEMPLATE });

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

const FALAISE = 3;
function scene() {
	const garde = { id: 'joueur_0', pos: { x: 3, y: 5 }, currentPV: 50 };
	const ecuyer = { id: 'joueur_1', pos: { x: 4, y: 5 }, currentPV: 50 };
	global.GRID = { dims: { x: 12, y: 9 }, cells: Array.from({ length: 9 }, () => Array(12).fill(1)) };
	global.state = { joueurs: [garde, ecuyer], monstres: [{ id: 'monstre_0', vivant: true, pos: { x: 9, y: 5 } }] };
	global.me = () => garde;
	global.capaPortee = (s) => ({ portee: s.portee || 1, ranged: false });
	global.chebyJM = (j, m) => Math.max(Math.abs(j.pos.x - m.pos.x), Math.abs(j.pos.y - m.pos.y));
	global.vueActeurs = () => true;
	return { garde, ecuyer };
}
const ECHANGE = { cible: 'allie', portee: 1, effets: { echange: 1 } };
const ids = (l) => l.map(p => p.id);

t('un allié adjacent est proposé', () => {
	scene();
	assert.deepStrictEqual(ids(allyTargets(ECHANGE)), ['joueur_1']);
});

t('la portée décide de la distance (aucune limite propre à l\'échange)', () => {
	const { ecuyer } = scene();
	ecuyer.pos = { x: 6, y: 5 };
	assert.deepStrictEqual(ids(allyTargets(ECHANGE)), []);
	assert.deepStrictEqual(ids(allyTargets({ ...ECHANGE, portee: 3 })), ['joueur_1']);
});

t('une grande créature n\'est pas proposée', () => {
	const { ecuyer } = scene();
	ecuyer.jeton = { largeur: 2, profondeur: 2, forme: 'ellipse' };
	ecuyer.cap = 'bas';
	assert.deepStrictEqual(ids(allyTargets(ECHANGE)), []);
});

t('un allié qui ne tiendrait pas sur la case du lanceur n\'est pas proposé', () => {
	const { garde } = scene();
	GRID.cells[5][3] = FALAISE;
	garde.volant = true;
	assert.deepStrictEqual(ids(allyTargets(ECHANGE)), []);
});

t('un tiers sur l\'une des deux cases bloque l\'échange', () => {
	scene();
	state.joueurs.push({ id: 'joueur_2', pos: { x: 2, y: 4 }, currentPV: 30,
		jeton: { largeur: 2, profondeur: 2, forme: 'ellipse' }, cap: 'bas' });
	assert.deepStrictEqual(ids(allyTargets(ECHANGE)), []);
});

t('sans `echange`, le ciblage allié est inchangé', () => {
	const { ecuyer } = scene();
	ecuyer.jeton = { largeur: 2, profondeur: 2, forme: 'ellipse' };
	ecuyer.cap = 'bas';
	assert.deepStrictEqual(ids(allyTargets({ cible: 'allie', portee: 1, effets: { pv: 10 } })), ['joueur_1']);
});

console.log(`\n${passes} passé(s), ${echecs} échec(s)`);
process.exit(echecs ? 1 : 0);
