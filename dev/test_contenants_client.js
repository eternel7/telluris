// dev/test_contenants_client.js
//
// Tests d'EXÉCUTION du JavaScript des CONTENANTS (templates/play_town_telluris.html).
//
//   node dev/test_contenants_client.js     # sort en code 1 au premier échec
//
// POURQUOI : la fenêtre 👜 grise les flèches que le serveur refuserait (utils/contenants.py,
// routers/contenants.py) et annonce la marée du Sac de Manannán. Classes de bug :
//
//   1. Un contenant proposé au rangement dans un autre (le serveur répond 409).
//   2. Un objet trop lourd pour la place restante, ou pour la charge du porteur à la sortie.
//   3. Hors marée, la charge est MASQUÉE (0) : le client ne doit pas en déduire « vide, tout
//      rentre » ni « plein » — il laisse le serveur trancher.
//   4. Le texte de marée lit des epochs en SECONDES (Date.now() / 1000).
//
// MÉTHODE : identique à dev/test_fiche_objet_client.js — extraction par nom, `runInThisContext`.

const path = require('path');
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

for (const nom of ['_dureeCourte', '_mareeTexte', '_contenanceTexte', '_ctnPeutRanger', '_ctnPeutSortir']) {
	vm.runInThisContext(extraire(nom));
}

let ok = 0;
function test(nom, fn) {
	try { fn(); ok++; }
	catch (e) { console.error('✗ ' + nom + '\n  ' + e.message); process.exit(1); }
}

const besace = { capacite_kg: 100, accessible: true, charge_kg: 95, nb: 3, maree: false };
const pierre = { nom: 'Pierre', poids: 4 };
const lingot = { nom: 'Lingot', poids: 6 };

test('un contenant ne se range pas dans un autre', () => {
	const r = _ctnPeutRanger({ nom: 'Urne', poids: 8, contenant: { capacite_kg: 300 } }, besace);
	assert.strictEqual(r.ok, false);
	assert.ok(/autre/.test(r.titre));
});

test('place restante : 4 kg rentrent dans 5, 6 kg non', () => {
	assert.strictEqual(_ctnPeutRanger(pierre, besace).ok, true);
	assert.strictEqual(_ctnPeutRanger(lingot, besace).ok, false);
});

test('hors marée la charge est masquée : le client ne refuse pas sur la place', () => {
	const sac = { capacite_kg: 5, accessible: false, charge_kg: 0, nb: 0, maree: true };
	assert.strictEqual(_ctnPeutRanger(lingot, sac).ok, true);
	assert.strictEqual(_contenanceTexte(sac), '? / 5 kg');
});

test('sortir est borné par la charge du porteur (égalité admise, comme le serveur)', () => {
	assert.strictEqual(_ctnPeutSortir(pierre, 16, 20).ok, true);
	assert.strictEqual(_ctnPeutSortir(pierre, 16.5, 20).ok, false);
});

test('texte de contenance', () => {
	assert.strictEqual(_contenanceTexte(besace), '95.0 / 100 kg — 3 objets');
	assert.strictEqual(_contenanceTexte({ capacite_kg: 100, accessible: true, charge_kg: 0, nb: 0 }), '0.0 / 100 kg');
	assert.strictEqual(_contenanceTexte({ capacite_kg: 100, accessible: true, charge_kg: 0.2, nb: 1 }), '0.2 / 100 kg — 1 objet');
});

test('marée : rien pour un contenant ordinaire, durées en secondes epoch', () => {
	assert.strictEqual(_mareeTexte(besace, 1000), '');
	const basse = { maree: true, accessible: false, prochaine_maree_at: 1000 + 4 * 3600 + 12 * 60 };
	assert.ok(_mareeTexte(basse, 1000).includes('dans 4 h 12'));
	const haute = { maree: true, accessible: true, fin_maree_at: 1000 + 25 * 60 };
	assert.ok(_mareeTexte(haute, 1000).includes('dans 25 min'));
});

test('durée courte : jamais « 0 min » ni négatif', () => {
	assert.strictEqual(_dureeCourte(10), '1 min');
	assert.strictEqual(_dureeCourte(-5), '1 min');
	assert.strictEqual(_dureeCourte(3600), '1 h 00');
});

console.log(`OK — ${ok} tests contenants (client).`);
