// dev/test_traversee_client.js
//
// Tests d'EXÉCUTION du mode voyage d'une traversée maritime (play_town_telluris.html).
//
//   node dev/test_traversee_client.js     # sort en code 1 au premier échec
//
// POURQUOI : `_traverseeDecision` aiguille chaque réponse d'`/api/traversee/avancer` —
// débarquer, partir au combat, ou faire le pas suivant. Une branche inversée (le combat lu
// AVANT l'arrivée, un événement non combat pris pour un combat) ne se voit qu'en mer, au bout
// d'une traversée entière. `_traverseeLibelle` borne le compteur du bandeau.
//
// MÉTHODE : extraction par NOM depuis le template puis `vm.runInThisContext` (cf.
// dev/test_passages_client.js).
//
// HORS DE PORTÉE (à vérifier en jeu) : la boucle elle-même (`setTimeout`, `visibilitychange`,
// garde « un seul pas en vol »), la caméra (`_ecrireCarte`) et le rechargement d'arrivée.

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

vm.runInThisContext(extraire('_traverseeDecision'));
vm.runInThisContext(extraire('_traverseeLibelle'));

console.log('Décision après un pas');
t('arrivée l’emporte sur tout (même un événement)', () => {
	assert.strictEqual(_traverseeDecision({arrive: true, zone_event: {type: 'combat'}}), 'arrivee');
});
t('un combat part au combat', () => {
	assert.strictEqual(_traverseeDecision({arrive: false, zone_event: {type: 'combat'}}), 'combat');
});
t('un événement non combat ne fait rien', () => {
	assert.strictEqual(_traverseeDecision({arrive: false, zone_event: {type: 'meteo'}}), 'suite');
	assert.strictEqual(_traverseeDecision({arrive: false, zone_event: null}), 'suite');
});
t('réponse vide : on continue', () => {
	assert.strictEqual(_traverseeDecision(null), 'suite');
});

console.log('Bandeau');
t('étape 0 = case 1 sur N', () => {
	assert.strictEqual(_traverseeLibelle({destination: 'Douvres', etape: 0, total: 26}),
		'⛵ Traversée vers Douvres — 1/26');
});
t('le compteur ne dépasse jamais le total', () => {
	assert.strictEqual(_traverseeLibelle({destination: 'Calais', etape: 25, total: 26}),
		'⛵ Traversée vers Calais — 26/26');
	assert.strictEqual(_traverseeLibelle({destination: 'Calais', etape: 40, total: 26}),
		'⛵ Traversée vers Calais — 26/26');
});

console.log(`\n${passes} OK, ${echecs} échec(s)`);
process.exit(echecs ? 1 : 0);
