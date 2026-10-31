// dev/test_guide_client.js
//
// Tests d'EXÉCUTION du JS du guide local (templates/play_town_telluris.html) :
// tarifs affichés, pied et actions de carte, avertissement de départ.
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

['_prixTexte', '_guideTarifTexte', '_guideSujetTexte', '_guidePied', '_guideActions', '_guideDepartEtat']
	.forEach(n => vm.runInThisContext(extraire(n)));
globalThis.escapeHtml = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');

function test(nom, fn) { fn(); console.log('ok -', nom); }

test('tarifs lisibles', () => {
	assert.strictEqual(_guideTarifTexte({ arrhes_cuivre: 50, question_cuivre: 10 }), "50 cu d'arrhes · 10 cu la question");
});

test('le prix n\'est annoncé que sur une réponse payante', () => {
	const g = { question_cuivre: 10 };
	assert.ok(_guideSujetTexte({ titre: 'Loups', connu: true }, g).includes('(10 cu)'));
	assert.ok(!_guideSujetTexte({ titre: 'Loups', connu: false }, g).includes('cu)'));
	assert.ok(!_guideSujetTexte({ titre: 'Loups', connu: true, ici: true }, g).includes('cu)'));
});

test('pied : métier échappé et prix de la question', () => {
	const html = _guidePied({ metier_label: '<b>', question_cuivre: 5 });
	assert.ok(html.includes('&lt;b>') && html.includes('5 cu la question'));
});

test('départ : le sac plein retient le joueur', () => {
	assert.deepStrictEqual(_guideDepartEtat({ sac_plein: false }), { peutPartir: true, note: '' });
	const plein = _guideDepartEtat({ sac_plein: true });
	assert.strictEqual(plein.peutPartir, false);
	assert.ok(plein.note.includes('Reprenez'));
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
