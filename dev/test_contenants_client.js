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

// ── Poser au sol depuis le contenu (⬇) : aucune garde de charge côté client non plus ──
// Classe de bug : le bouton greffé hors de la ligne, ou désactivé par la charge du sac.
for (const nom of ['_pcfLigne', '_ctnBoutonPoser']) vm.runInThisContext(extraire(nom));
globalThis.escapeHtml = s => String(s).replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);

test('ligne du contenu : ← sortir ET ⬇ poser, dans la même ligne', () => {
	const it = { idx: 2, item: 'item:pierre', nom: 'Pierre', poids: 40 };
	const html = _pcfLigne(it, it.idx, '←', '_ctnSortir', false, 'Trop lourd', 'gauche', null, null, null, _ctnBoutonPoser(it));
	assert.ok(/^<div class="sh-inv-item">[\s\S]*_ctnSortir[\s\S]*_ctnPoser\(this\)">⬇<\/button><\/div>$/.test(html));
	const poser = _ctnBoutonPoser(it);
	assert.ok(!/disabled/.test(poser), 'trop lourd pour le sac ne bloque pas la pose au sol');
	assert.ok(/data-idx="2"/.test(poser) && /data-item="item:pierre"/.test(poser));
});

// ── Contenants comme DESTINATAIRES (sol 🤝, panneau 👥, butin de combat) ─────────
// Classes de bug : un contenant oublié de la liste (celui du porteur de la fiche compris),
// un contenant proposé comme destination d'un autre contenant, une place masquée (marée
// basse) prise pour « plein » ou « vide ».
for (const nom of ['_grpRentre', '_porteursPourRamasser']) vm.runInThisContext(extraire(nom));

globalThis.porteurActifId = () => 'character:moi';
globalThis._grpEtat = {
	principal: { id: 'character:moi', prenom: 'Moi', nom: '', charge: 10, charge_max: 20 },
	groupe: [], montures: [], sacs: {},
	contenants: [
		{ cle: 'character:moi#2', porteur_id: 'character:moi', porteur_nom: 'Moi', index: 2,
		  item_id: 'item:besace', nom: 'Besace', libre: 3, accessible: true },
		{ cle: 'monture:ane#0', porteur_id: 'monture:ane', porteur_nom: 'Grison', index: 0,
		  item_id: 'item:sac_maree', nom: 'Sac de Manannán', libre: null, accessible: false },
	],
};

test('sol 🤝 : les contenants du groupe, celui de la fiche ouverte compris', () => {
	const out = _porteursPourRamasser({ poids: 4 });
	assert.deepStrictEqual(out.map(p => p.id), ['character:moi#2', 'monture:ane#0']);
	assert.strictEqual(out[0].rentre, false, 'besace : 3 kg libres pour 4 kg');
	assert.strictEqual(out[1].rentre, true, 'marée basse : place inconnue, le serveur tranche');
	assert.strictEqual(out[1].contenant.porteur_id, 'monture:ane');
});

test('sol 🤝 : un contenant ne va jamais dans un autre', () => {
	assert.ok(_porteursPourRamasser({ poids: 0.5, contenant: {} }).every(p => !p.rentre));
});

test('panneau 👥 : _grpRentre vers un contenant', () => {
	const dest = { charge: 7, charge_max: 10, contenant: { accessible: true } };
	assert.strictEqual(_grpRentre({ poids: 3 }, dest), true);
	assert.strictEqual(_grpRentre({ poids: 3.5 }, dest), false);
	assert.strictEqual(_grpRentre({ poids: 1, contenant: {} }, dest), false);
	assert.strictEqual(_grpRentre({ poids: 999 }, { charge: 0, charge_max: 5, contenant: { accessible: false } }), true);
	// Sac ordinaire : arithmétique inchangée.
	assert.strictEqual(_grpRentre({ poids: 10 }, { charge: 10, charge_max: 20 }), true);
});

// Combat : clés d'attribution et jauges (templates/combat_telluris.html).
const COMBAT = path.join(__dirname, '..', 'templates', 'combat_telluris.html');
const jsCombat = scriptsInline(lireAvecIncludes(COMBAT));
for (const nom of ['lootMembers', 'lootContenants', 'lootCle', 'lootJauge', '_lootEsc']) {
	vm.runInThisContext(extraire(nom, jsCombat));
}
globalThis.state = {
	joueurs: [{ id: 'joueur_0', character_id: 'character:moi', nom: 'Moi', charge: 5, charge_max: 50 },
			  { id: 'joueur_1', character_id: 'protege:x', est_protege: true }],
	contenants_butin: [
		{ character_id: 'character:moi', index: 1, nom: 'Besace', charge_kg: 2, capacite_kg: 10, libre: 8 },
		{ character_id: 'protege:x', index: 0, nom: 'Sac', charge_kg: 0, capacite_kg: 10, libre: 10 },
	],
};

test('butin : un contenant d\'un non-bénéficiaire (escorté) n\'est pas proposé', () => {
	assert.deepStrictEqual(lootContenants().map(c => c.character_id), ['character:moi']);
});

test('butin : clé membre vs contenant, jauge du contenant', () => {
	assert.strictEqual(lootCle('character:moi', ''), 'character:moi');
	assert.strictEqual(lootCle('character:moi', '1'), 'character:moi#1');
	assert.strictEqual(lootCle('', '1'), '');
	const g = lootJauge('character:moi#1');
	assert.strictEqual(g.base, 2); assert.strictEqual(g.max, 10); assert.strictEqual(g.inconnu, false);
	assert.strictEqual(lootJauge('character:moi').max, 50);
});

test('butin : le nom d\'un contenant est échappé', () => {
	assert.strictEqual(_lootEsc('<b>"Fonte" d\'Ané</b>'), '&lt;b&gt;&quot;Fonte&quot; d&#39;Ané&lt;/b&gt;');
});

console.log(`OK — ${ok} tests contenants (client).`);
