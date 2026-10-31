// dev/test_guide_client.js
//
// Tests d'EXÉCUTION du JS du guide local (templates/play_town_telluris.html) :
// toasts de tours, pied et actions de carte, forfait affiché.
//
//   node dev/test_guide_client.js     # sort en code 1 au premier échec
//
// HORS DE PORTÉE (à vérifier en jeu) : le rendu du panneau et de l'overlay.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const src = fs.readFileSync(path.join(__dirname, '..', 'templates', 'play_town_telluris.html'), 'utf8');

function extraire(nom) {
	const debut = src.indexOf(`function ${nom}(`);
	assert(debut >= 0, `fonction ${nom} introuvable`);
	let i = src.indexOf('{', src.indexOf(')', debut));
	let prof = 0;
	let chaine = null;
	for (; i < src.length; i++) {
		const c = src[i];
		if (chaine) {
			if (c === '\\') i++;
			else if (c === chaine) chaine = null;
			continue;
		}
		if (c === "'" || c === '"' || c === '`') { chaine = c; continue; }
		if (c === '{') prof++;
		if (c === '}' && --prof === 0) return src.slice(debut, i + 1);
	}
	throw new Error(`fonction ${nom} non fermée`);
}

['_prixTexte', '_guideForfaitTexte', '_guidePied', '_guideActions', '_texteGuideTour']
	.forEach(n => vm.runInThisContext(extraire(n)));
globalThis.escapeHtml = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');

function test(nom, fn) { fn(); console.log('ok -', nom); }

test('toast seulement sur une alerte', () => {
	assert.strictEqual(_texteGuideTour(null), null);
	assert.strictEqual(_texteGuideTour({ tours_restants: 40, alerte: null }), null);
	assert.ok(_texteGuideTour({ tours_restants: 0, alerte: 'epuise' }).includes('épuisé'));
	assert.ok(_texteGuideTour({ tours_restants: 10, alerte: 'bientot' }).includes('10 tours'));
});

test('forfait lisible', () => {
	assert.strictEqual(_guideForfaitTexte({ forfait_cuivre: 50, forfait_tours: 100 }), '50 cu / 100 tours');
});

test('pied : tours restants, ou épuisé, métier échappé', () => {
	assert.ok(_guidePied({ metier_label: 'Marin', tours_restants: 7 }).includes('7 tours restants'));
	assert.ok(_guidePied({ metier_label: 'Marin', epuise: true }).includes('épuisé'));
	assert.ok(_guidePied({ metier_label: '<b>' }).includes('&lt;b>'));
});

test('congédier grisé hors auberge ou sac plein, interroger toujours offert', () => {
	globalThis.EST_AUBERGE = false;
	let html = _guideActions({ charge: 0 });
	assert.ok(html.includes('ouvrirGuide'));
	assert.ok(/disabled[^>]*onclick="congedierGuide/.test(html));
	globalThis.EST_AUBERGE = true;
	assert.ok(/disabled[^>]*onclick="congedierGuide/.test(_guideActions({ charge: 2 })));
	assert.ok(!/disabled/.test(_guideActions({ charge: 0 })));
});

console.log('test_guide_client : tout passe');
