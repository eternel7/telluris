// dev/test_vocation_client.js
//
// Tests d'EXÉCUTION du JS du changement de vocation (templates/play_town_telluris.html) :
// « Aspirant » à la place de « Niv.0 », ligne d'une vocation proposée, texte de confirmation.
//
//   node dev/test_vocation_client.js     # sort en code 1 au premier échec
//
// HORS DE PORTÉE (à vérifier en jeu) : l'overlay, l'appel serveur, la resync de la fiche.

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

['_nivVocTexte', '_vocLigne', '_texteConfirmationVocation'].forEach(n => vm.runInThisContext(extraire(n)));
globalThis.escapeHtml = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
globalThis.VOC_LABELS = { guerrier: { icon: '⚔️', label: 'Guerrier' }, templier: { icon: '⚜️', label: 'Templier' } };

let ok = 0;
function test(nom, fn) { fn(); ok++; console.log('ok -', nom); }

test('niveau 0 = Aspirant, sinon Niv.N', () => {
	assert.strictEqual(_nivVocTexte(0), 'Aspirant');
	assert.strictEqual(_nivVocTexte(undefined), 'Aspirant');
	assert.strictEqual(_nivVocTexte(3), 'Niv.3');
	assert.strictEqual(_nivVocTexte('10'), 'Niv.10');
});

test('ligne : retour avec son niveau, nouvelle voie en aspirant, bouton grisé sans les points', () => {
	globalThis._vocChoix = { attribute_points: 9, voc: 'guerrier', voc_niveau: 4, options: [] };
	const retour = _vocLigne({ id: 'templier', label: 'Templier', icon: '⚜️', connue: true, niveau: 2, cout: 5, magie: '' });
	assert.ok(retour.includes('retour · Niv.2') && !retour.includes('disabled'));
	const neuve = _vocLigne({ id: 'paladin', label: 'Paladin', icon: '🛡', connue: false, niveau: 0, cout: 25, magie: 'Sainte' });
	assert.ok(neuve.includes('nouvelle voie · Aspirant') && neuve.includes('disabled') && neuve.includes('magie Sainte'));
	// L'id part par data-attribut, jamais dans une chaîne JS d'un onclick (CLAUDE.md §9).
	assert.ok(neuve.includes('data-voc="paladin"') && neuve.includes('this.dataset.voc'));
});

test('confirmation d\'une voie NOUVELLE : on reste ce qu\'on était aux yeux du monde', () => {
	globalThis._vocChoix = { attribute_points: 30, voc: 'guerrier', voc_niveau: 4, options: [] };
	const t = _texteConfirmationVocation({ id: 'templier', label: 'Templier', connue: false, niveau: 0 });
	assert.ok(t.includes('Devenir Templier'));
	assert.ok(t.includes('vous restez Guerrier de niveau 4'));
	assert.ok(t.includes('la seule personne à y croire') && t.includes('aspirant'));
	assert.ok(t.includes('Vous gardez tout ce que vous avez acquis'));
});

test('confirmation depuis un niveau 0 : déjà aspirant', () => {
	globalThis._vocChoix = { attribute_points: 30, voc: 'guerrier', voc_niveau: 0, options: [] };
	const t = _texteConfirmationVocation({ id: 'templier', label: 'Templier', connue: false, niveau: 0 });
	assert.ok(t.includes("au rang d'aspirant Guerrier") && !t.includes('de niveau 0'));
});

test('confirmation d\'un RETOUR : la voie reprend à son niveau', () => {
	globalThis._vocChoix = { attribute_points: 30, voc: 'templier', voc_niveau: 1, options: [] };
	const t = _texteConfirmationVocation({ id: 'guerrier', label: 'Guerrier', connue: true, niveau: 4 });
	assert.ok(t.includes('Reprendre la voie de Guerrier') && t.includes('Niv.4'));
});

console.log(`✓ ${ok} tests vocation`);
