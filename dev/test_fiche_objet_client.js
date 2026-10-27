// dev/test_fiche_objet_client.js
//
// Tests d'EXÉCUTION du JavaScript de la FICHE OBJET (templates/play_town_telluris.html).
//
//   node dev/test_fiche_objet_client.js     # sort en code 1 au premier échec
//
// POURQUOI : la fiche ne doit afficher que ce que le moteur applique vraiment
// (utils/characters.recompute_equipment_bonus, combat._weapon_attacks). Classes de bug :
//
//   1. Le bloc `effets` d'une pièce PORTÉE (armure, catalyseur, livre) : seuls régén, esquive
//      et canalisation jouent, en permanence — +PV, +PM, buffs et ⏳ durée sont inertes.
//   2. Le bloc `effets` d'une arme À DURÉE part sur la CIBLE du coup, jamais sur le porteur :
//      ligne « Au coup → ennemi|soi », pas « Effets ».
//   3. Un consommable garde toute sa lecture (effet à l'ingestion).
//   4. La portée d'une arme de JET ajoute F // JET_PORTEE_F_DIV.
//
// MÉTHODE : identique à dev/test_proprietes_client.js — extraction par nom, `runInThisContext`.

const path = require('path');
const fs = require('fs');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'play_town_telluris.html');
const { lireAvecIncludes, scriptsInline } = require('./_template_js');
const js = scriptsInline(lireAvecIncludes(TEMPLATE));
assert.ok(js, 'aucun bloc <script> trouvé dans ' + TEMPLATE);

function extraire(nom, source = js) {
	const debut = source.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable');
	let prof = 0;
	for (let j = source.indexOf('{', debut); j < source.length; j++) {
		if (source[j] === '{') prof++;
		else if (source[j] === '}' && --prof === 0) return source.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}

const capacites = fs.readFileSync(path.join(__dirname, '..', 'templates', 'scripts', 'capacites_texte.js'), 'utf8');
vm.runInThisContext(extraire('regenTexte', capacites));
for (const nom of ['_itemMode', '_porteeArme', '_effetsLecture', '_effetsChips', '_cibleCoup', '_effetsRow']) {
	vm.runInThisContext(extraire(nom));
}
globalThis._charStats = { F: 30 };
globalThis._caractsDetail = { F: { base: 30, total: 45 } };
globalThis._JET_F_DIV = 20;

let ok = 0;
function test(nom, fn) {
	try { fn(); ok++; }
	catch (e) { console.error('✗ ' + nom + '\n  ' + e.message); process.exit(1); }
}

// Données tirées du dump (Calotte runée, Bolas, Tambour de guerre, focus magique).
const calotte = { categorie: 'armure', slots: ['tete'],
	effets: { regen_pm: 1, pv: 5, pm: 5, duree: 3 } };
const focus = { categorie: 'catalyseur', slots: ['main_gauche'],
	effets: { regen_pm: 2, pm: 8, canalisation: 1, pv: 5, duree: 3, buffs: { Vol: -1 } } };
const bolas = { categorie: 'arme', tags: ['jet'], portee: 3, cible: 'ennemi',
	effets: { buffs: { V: -2 }, duree: 2 } };
const tambour = { categorie: 'arme', cible: 'soi', effets: { buffs: { Cha: 2 }, duree: 2 } };
const baguette = { categorie: 'arme', portee: 1, effets: { regen_pm: 1 } };
const potion = { categorie: 'consommable', effets: { pv: 10, buffs: { F: 2 }, duree: 3 } };

test('pièce portée : seule la régén s\'affiche, sans durée', () => {
	assert.deepStrictEqual(_effetsChips(calotte), ['💧 +1 PM/tour']);
});
test('pièce portée : canalisation et esquive affichées, buffs/+PV/+PM/durée cachés', () => {
	const chips = _effetsChips({ ...focus, effets: { ...focus.effets, esquive: 2 } });
	assert.deepStrictEqual(chips, ['💧 +2 PM/tour', '🛡️ esquive +2', '🔮 canalisation +1 %']);
});
test('arme SANS durée : lecture portée (baguette qui régénère son porteur)', () => {
	assert.strictEqual(_effetsLecture(baguette), 'porte');
	assert.deepStrictEqual(_effetsChips(baguette), ['💧 +1 PM/tour']);
});
test('consommable : lecture complète inchangée', () => {
	assert.deepStrictEqual(_effetsChips(potion), ['❤️ +10 PV', '✨ +2 F', '⏳ 3 tours']);
});
test('arme à durée : ligne « Au coup → ennemi », jamais « Effets »', () => {
	const html = _effetsRow(bolas, null, false);
	assert.ok(html.includes('Au coup → ennemi'), html);
	assert.ok(!html.includes('>Effets<'), html);
	assert.ok(html.includes('✨ -2 V') && html.includes('⏳ 2 tours'), html);
});
test('arme à durée ciblant le porteur : « Au coup → soi »', () => {
	assert.ok(_effetsRow(tambour, null, false).includes('Au coup → soi'));
});
test('comparaison : cibles différentes → chaque cellule dit la sienne', () => {
	const html = _effetsRow(bolas, tambour, true);
	assert.ok(html.includes('>Au coup<') && html.includes('→ ennemi') && html.includes('→ soi'), html);
});
test('comparaison : pièce portée face à une arme à durée → deux lignes', () => {
	const html = _effetsRow(calotte, bolas, true);
	assert.ok(html.includes('>Effets<') && html.includes('Au coup → ennemi'), html);
});
test('aucun effet applicable → aucune ligne', () => {
	assert.strictEqual(_effetsRow({ categorie: 'armure', effets: { pv: 5, duree: 3 } }, null, false), '');
});
test('portée de jet : + F (buffs compris) // JET_PORTEE_F_DIV', () => {
	assert.strictEqual(_porteeArme(bolas), 3 + Math.floor(45 / _JET_F_DIV));
});
test('portée hors jet : celle de l\'objet ; hors arme : null', () => {
	assert.strictEqual(_porteeArme(baguette), 1);
	assert.strictEqual(_porteeArme({ categorie: 'arme', tags: ['tir'], portee: 8 }), 8);
	assert.strictEqual(_porteeArme(calotte), null);
});

console.log(`✓ ${ok} tests fiche objet`);
