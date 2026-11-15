// dev/test_defauts_zones_client.js
//
// Tests d'EXÉCUTION du JS des EXCLUSIONS de défauts de zones
// (templates/admin_map_editor.html, panneaux Rencontres / Ressources → « 🗺️ Défauts des zones »).
//
//   node dev/test_defauts_zones_client.js     # sort en code 1 au premier échec
//
// POURQUOI : une exclusion se lit côté serveur par `utils/zones._exclu` — entrée SANS `zones` =
// toutes les zones du lieu, sinon les zones listées. Le client bascule ces entrées clic par clic ;
// une bascule fausse retirerait ou rétablirait un défaut ailleurs qu'on ne l'a cliqué, sans
// qu'aucun test pytest ne le voie (la logique vit dans un template).
//
// MÉTHODE : extraction par nom (accolades équilibrées), `runInThisContext`, globales semées
// (`lieuExclusions`, `usedZoneDefs`) — comme dev/test_portes_client.js.
//
// HORS DE PORTÉE (à vérifier en jeu) : le rendu des puces et l'échange avec
// PUT /api/lieu/{id}/exclusions (verrouillé côté serveur par tests/test_zones_defauts.py).

const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'admin_map_editor.html');
const src = require('./_template_js').lireAvecIncludes(TEMPLATE);
const js = [...src.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)].map(m => m[1]).join('\n');

function extraire(nom) {
	const debut = js.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable dans le template');
	let prof = 0;
	for (let j = js.indexOf('{', debut); j < js.length; j++) {
		if (js[j] === '{') prof++;
		else if (js[j] === '}' && --prof === 0) return js.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}

vm.runInThisContext([extraire('estExcluDefaut'), extraire('basculerExclusion')].join('\n')
	+ '\nglobalThis.estExcluDefaut = estExcluDefaut; globalThis.basculerExclusion = basculerExclusion;');

globalThis.usedZoneDefs = () => [{ _id: 'zone:foret' }, { _id: 'zone:collines' }, { _id: 'zone:riviere' }];

let echecs = 0;
function test(nom, fn) {
	globalThis.lieuExclusions = [];
	try { fn(); console.log('  ✓ ' + nom); }
	catch (e) { echecs++; console.log('  ✗ ' + nom + '\n    ' + e.message); }
}

console.log('Exclusions de défauts de zones');

test('un clic exclut le défaut de CETTE zone seulement', () => {
	basculerExclusion('espece', 'espece:ours', 'zone:foret');
	assert.deepStrictEqual(lieuExclusions, [{ espece: 'espece:ours', zones: ['zone:foret'] }]);
	assert.ok(estExcluDefaut('espece', 'espece:ours', 'zone:foret'));
	assert.ok(!estExcluDefaut('espece', 'espece:ours', 'zone:collines'));
});

test('un second clic dans une autre zone rejoint la même entrée, un re-clic la rouvre', () => {
	basculerExclusion('espece', 'espece:ours', 'zone:foret');
	basculerExclusion('espece', 'espece:ours', 'zone:collines');
	assert.deepStrictEqual(lieuExclusions, [{ espece: 'espece:ours', zones: ['zone:foret', 'zone:collines'] }]);
	basculerExclusion('espece', 'espece:ours', 'zone:foret');
	basculerExclusion('espece', 'espece:ours', 'zone:collines');
	assert.deepStrictEqual(lieuExclusions, []);
});

test('une exclusion « toutes zones » (écrite à la main) se rouvre zone par zone', () => {
	lieuExclusions = [{ ressource: 'item:roseau' }];
	assert.ok(estExcluDefaut('ressource', 'item:roseau', 'zone:riviere'));
	basculerExclusion('ressource', 'item:roseau', 'zone:riviere');
	assert.deepStrictEqual(lieuExclusions, [{ ressource: 'item:roseau', zones: ['zone:foret', 'zone:collines'] }]);
	assert.ok(!estExcluDefaut('ressource', 'item:roseau', 'zone:riviere'));
	assert.ok(estExcluDefaut('ressource', 'item:roseau', 'zone:foret'));
});

test('espèce et ressource de même suffixe ne se confondent pas', () => {
	basculerExclusion('espece', 'espece:loup', 'zone:foret');
	assert.ok(!estExcluDefaut('ressource', 'espece:loup', 'zone:foret'));
});

if (echecs) { console.log(`\n${echecs} échec(s)`); process.exit(1); }
console.log('\nTous les tests passent.');
