// dev/test_filtres_boutique_client.js
//
// Tests de l'ENTONNOIR du panneau marchand (play_town_telluris.html, utils/filtres_boutique.py).
//
//   node dev/test_filtres_boutique_client.js     # sort en code 1 au premier échec
//
// POURQUOI : les clés `filtres` sont calculées par le serveur ; le client ne fait que garder
// ou écarter une ligne. Classes de bug :
//
//   1. Inclusion inversée en intersection : « Tête » + « Tranchante » doit montrer les DEUX
//      familles, pas les seuls casques tranchants (il n'y en a aucun).
//   2. Filtre qui casse l'adressage : l'ordre filtré doit rester des INDEX D'ORIGINE (la fiche
//      et les boutons relisent `MARCHAND.<liste>[idx]`).
//   3. Pastille absente du panneau proposée quand même (un entonnoir d'armurerie qui affiche
//      « Bougies »), ou pastille ACTIVE qui disparaît (impossible à désactiver hors « reset »).
//   4. Texte saisi injecté tel quel : les libellés passent par `escapeHtml`.
//
// HORS DE PORTÉE (sans jsdom) : l'overlay, le halo, la remise à zéro à l'ouverture du
// panneau — vérifiés dans un vrai navigateur (CLAUDE.md §15).

const path = require('path');
const assert = require('assert');
const vm = require('vm');

const { lireAvecIncludes, scriptsInline } = require('./_template_js');
const play = lireAvecIncludes(path.join(__dirname, '..', 'templates', 'play_town_telluris.html'));
const js = scriptsInline(play);
assert.ok(js, 'aucun bloc <script> dans play_town_telluris.html');

function extraire(nom, source) {
	const debut = source.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable');
	let prof = 0;
	for (let j = source.indexOf('{', debut); j < source.length; j++) {
		if (source[j] === '{') prof++;
		else if (source[j] === '}' && --prof === 0) return source.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}

['_fbGarde', '_fbComptes', '_fbGroupesHtml', '_fbOrdre', '_sortedOrder', 'escapeHtml']
	.forEach(n => vm.runInThisContext(extraire(n, js)));
// Globale lue par `_fbOrdre` (semée ; `let` dans la page).
globalThis._fbActifs = new Set();

let ok = 0;
function test(nom, fn) {
	try { fn(); ok++; }
	catch (e) { console.error('✗ ' + nom + '\n  ' + e.message); process.exit(1); }
}

const CASQUE = { nom: 'Casque', filtres: ['armure.tete'] };
const HACHE = { nom: 'Hache', filtres: ['arme.cac', 'arme.tranchant', 'prise.une', 'prise.gauche'] };
const ARC = { nom: 'Arc', filtres: ['arme.tir', 'prise.deux'] };
const PAIN = { nom: 'Pain', filtres: ['conso.nourriture', 'conso.soin'] };
const BOUGIE = { nom: 'Bougie' };   // aucune clé : écartée dès qu'un filtre est actif

test('sans filtre actif, tout passe (même une ligne sans clé)', () => {
	[CASQUE, HACHE, BOUGIE].forEach(e => assert.ok(_fbGarde(e, new Set())));
	assert.ok(_fbGarde(BOUGIE, null));
});

test('inclusion : Tête + Tranchante montre les casques ET les armes tranchantes', () => {
	const actifs = new Set(['armure.tete', 'arme.tranchant']);
	assert.deepStrictEqual([CASQUE, HACHE, ARC, PAIN, BOUGIE].filter(e => _fbGarde(e, actifs)), [CASQUE, HACHE]);
});

test('une ligne sans clé disparaît dès qu’un filtre est actif', () => {
	assert.ok(!_fbGarde(BOUGIE, new Set(['conso.soin'])));
});

test('l’ordre filtré reste en index d’origine, tri compris', () => {
	const liste = [PAIN, CASQUE, ARC, HACHE];
	globalThis._fbActifs = new Set(['arme.tir', 'arme.tranchant']);
	assert.deepStrictEqual(_fbOrdre(liste, 'asc'), [2, 3]);    // Arc, Hache
	assert.deepStrictEqual(_fbOrdre(liste, 'desc'), [3, 2]);   // Hache, Arc
	assert.deepStrictEqual(_fbOrdre(liste, null), [2, 3]);
	globalThis._fbActifs = new Set();
	assert.deepStrictEqual(_fbOrdre(liste, null), [0, 1, 2, 3]);
});

test('les comptes s’additionnent sur plusieurs listes', () => {
	const n = _fbComptes([[CASQUE, HACHE], [HACHE, BOUGIE], null]);
	assert.strictEqual(n['armure.tete'], 1);
	assert.strictEqual(n['arme.tranchant'], 2);
	assert.strictEqual(n['conso.soin'], undefined);
});

const CATALOGUE = [
	{ cle: 'armure', icon: '🛡️', nom: 'Armure', pastilles: [{ cle: 'armure.tete', nom: 'Tête' }, { cle: 'armure.pieds', nom: 'Pieds' }] },
	{ cle: 'conso', icon: '🧪', nom: 'Consommable', pastilles: [{ cle: 'conso.soin', nom: 'Soin' }] },
	{ cle: 'arme', icon: '⚔️', nom: 'Arme', pastilles: [{ cle: 'arme.tranchant', nom: 'Tranchante <b>' }] },
];

test('seules les pastilles présentes dans le panneau sont proposées ; un groupe vide disparaît', () => {
	const presents = _fbComptes([[CASQUE]]);
	const html = _fbGroupesHtml(CATALOGUE, presents, presents, new Set());
	assert.ok(html.includes('armure.tete'));
	assert.ok(!html.includes('armure.pieds'), 'pastille sans objet proposée');
	assert.ok(!html.includes('Consommable'), 'groupe vide affiché');
});

test('une pastille ACTIVE reste affichée même sans objet (pour pouvoir la désactiver)', () => {
	const html = _fbGroupesHtml(CATALOGUE, {}, {}, new Set(['conso.soin']));
	assert.ok(html.includes("basculerFiltreBoutique('conso.soin')"));
	assert.ok(html.includes('is-on'));
	assert.ok(html.includes('aria-pressed="true"'));
});

test('présente ailleurs mais absente de la section : estompée, compte 0', () => {
	const html = _fbGroupesHtml(CATALOGUE, {}, { 'armure.tete': 3 }, new Set());
	assert.ok(/class="fb-pill is-vide"[^>]*armure\.tete/.test(html), html);
	assert.ok(html.includes('<span class="fb-n">0</span>'));
});

test('les libellés sont échappés', () => {
	const html = _fbGroupesHtml(CATALOGUE, { 'arme.tranchant': 1 }, { 'arme.tranchant': 1 }, new Set());
	assert.ok(html.includes('Tranchante &lt;b&gt;'));
});

console.log(`OK — ${ok} test(s) de l'entonnoir du panneau marchand.`);
