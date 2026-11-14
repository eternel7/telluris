// Harnais d'EXÉCUTION de templates/scripts/capacites_texte.js : libellés d'une capacité
// (onglet ⚡ de /play, catalogues /admin/sorts et /admin/competences).
// Usage : node dev/test_capacites_texte_client.js — code 1 en échec.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const src = fs.readFileSync(path.join(__dirname, '..', 'templates', 'scripts', 'capacites_texte.js'), 'utf8');
// Contrat de l'hôte : zones_effet.js chargé avant, `_coutPmCharge` défini.
globalThis.libelleZone = () => '';
globalThis.normaliserZone = z => z || null;
globalThis._coutPmCharge = c => +(c && c.cout_pm) || 0;
vm.runInThisContext(src);

let ok = 0;
function test(nom, fn) {
	try { fn(); ok++; }
	catch (e) { console.error('✗ ' + nom + '\n  ' + e.message); process.exit(1); }
}

// Docs du dump : Furtivité (assassin niv. 0) et Pas feutrés (assassin niv. 1).
const furtivite = { mode: 'active', cible: 'soi', cout_pm: 0, effets: { furtivite: 1 } };
const pasFeutres = { mode: 'passive', effets: { furtivite: 4 },
	condition: { battle_map_tags: ['sous-terrain', 'grotte', 'mine'] } };

test('la valeur de furtivité est affichée', () => {
	assert.strictEqual(_sortEffetsLabel(furtivite.effets), '🥷 furtivité +1');
	assert.strictEqual(_sortEffetsLabel(pasFeutres.effets), '🥷 furtivité +4');
});
test('formule de furtivité : formule puis valeur résolue', () => {
	assert.strictEqual(_sortEffetsLabel({ furtivite: 6, formules_texte: { furtivite: '{Ag/10}' } }),
		'🥷 furtivité +{Ag/10} → 6');
});
test('condition de terrain listée sous la compétence', () => {
	assert.strictEqual(_compLigneDesc(pasFeutres),
		'🥷 furtivité +4 · 🗺️ seulement en terrain : sous-terrain, grotte, mine');
});
test('sans condition : rien d\'ajouté', () => {
	assert.strictEqual(_conditionLabel(furtivite), '');
	assert.strictEqual(_conditionLabel({ condition: {} }), '');
	assert.strictEqual(_compLigneDesc(furtivite), '🥷 furtivité +1');
});

test('passive Ambidextre : son effet est annoncé (dev/gen_ambidextre.py)', () => {
	assert.strictEqual(_compLigneDesc({ mode: 'passive', effets: { ambidextre: 1 } }),
		'⚔️ seconde arme sans malus');
});

test('passive Lecture des traces : son effet est annoncé (dev/gen_pistage.py)', () => {
	assert.strictEqual(_compLigneDesc({ mode: 'passive', effets: { pistage: 1 } }),
		'🐾 lit les traces (espèce et grade)');
});

test('pouvoir d\'un objet porté : « 🏆 accordé par », nom échappé (utils/pouvoirs_objets)', () => {
	const s = { effets: { degats: '2D6' }, cible: 'soi', accorde_par: 'Épée <b>croc</b>' };
	assert.ok(_sortLigneDesc(s).includes('🏆 accordé par Épée &lt;b&gt;croc&lt;/b&gt;'));
	assert.ok(_compLigneDesc({ mode: 'active', cible: 'soi', effets: {}, accorde_par: 'Sceptre' }).includes('🏆 accordé par Sceptre'));
	assert.ok(!_sortLigneDesc({ effets: {}, cible: 'soi' }).includes('🏆'));
});

test('exigence d\'arme : neutre, ⛔ si manquante, « inactive » pour une passive (utils/exigence_arme)', () => {
	assert.strictEqual(_armeLabel({ arme_requise: '' }), '');
	assert.strictEqual(_armeLabel({}), '');
	// Catalogue d'admin : aucun porteur, donc pas d'`arme_ok` ⇒ neutre.
	assert.ok(_armeLabel({ arme_requise: 'une arme de tir (arc)' }).includes('🗡 exige une arme de tir (arc)'));
	assert.ok(_armeLabel({ mode: 'active', arme_requise: 'un bouclier', arme_ok: true }).includes('🗡 exige un bouclier'));
	const manque = _armeLabel({ mode: 'active', arme_requise: 'un bouclier', arme_ok: false });
	assert.ok(manque.includes('⛔ exige un bouclier') && manque.includes('capa-arme-manque'));
	assert.ok(_armeLabel({ mode: 'passive', arme_requise: 'une arme de tir', arme_ok: false })
		.includes('⛔ inactive : exige une arme de tir'));
	// Libellé servi par le serveur, échappé quand même (innerHTML).
	assert.ok(_armeLabel({ arme_requise: 'x <b>' }).includes('x &lt;b&gt;'));
	assert.ok(_compLigneDesc({ mode: 'active', cible: 'soi', effets: {}, arme_requise: 'un bouclier' })
		.includes('🗡 exige un bouclier'));
});

console.log(`✓ ${ok} tests capacites_texte`);
