// dev/test_transmettre_client.js
//
// Tests d'EXÉCUTION du menu « ⇄ Transmettre » (templates/scripts/transmettre.js).
//
//   node dev/test_transmettre_client.js     # sort en code 1 au premier échec
//
// POURQUOI : le menu remplace « Poser », le 🤝 du sol et le ⬇ des contenants ; il grise ce que
// POST api/transmettre refuserait (routers/transmission.py). Classes de bug :
//
//   1. L'emplacement de l'objet proposé comme destination (le serveur répond 422).
//   2. Un porteur ou un contenant oublié ; le sol absent, ou proposé pour un objet déjà au sol.
//   3. Une place mal calculée (trop lourd pris pour « rentre », marée basse prise pour « plein »).
//   4. Un menu posé hors de la fenêtre (débord à droite / en bas).
//   5. Une adresse ou un nom saisi injecté dans l'attribut (Conventions §9).
//   6. Un « Poser » resté dans /play à côté du menu.
//
// MÉTHODE : le VRAI script, chargé tel quel (`runInThisContext`) ; `escapeHtml` semé.

const path = require('path');
const fs = require('fs');
const assert = require('assert');
const vm = require('vm');

const SCRIPT = path.join(__dirname, '..', 'templates', 'scripts', 'transmettre.js');
globalThis.escapeHtml = s => String(s).replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);
vm.runInThisContext(fs.readFileSync(SCRIPT, 'utf8'));

let ok = 0;
function test(nom, fn) {
	try { fn(); ok++; }
	catch (e) { console.error('✗ ' + nom + '\n  ' + e.message); process.exit(1); }
}

const GRP = {
	principal: { id: 'character:moi', prenom: 'Moi', nom: 'Même', charge: 10, charge_max: 20 },
	groupe: [{ id: 'aventurier:aldric', prenom: 'Aldric', nom: 'Ferrant' },
			 { id: 'aventurier:escorte', prenom: 'Escortée', nom: '' }],   // sans sac : ne porte rien
	montures: [{ id: 'monture:ane', prenom: '', nom: 'Grison' }],
	guide: { id: 'monture:guide', prenom: 'Odon', nom: '' },
	sacs: {
		'aventurier:aldric': { charge: 48, charge_max: 50 },
		'monture:ane': { charge: 0, charge_max: 400 },
		'monture:guide': { charge: 0, charge_max: 30 },
	},
	contenants: [
		{ cle: 'character:moi#3', porteur_id: 'character:moi', porteur_nom: 'Moi', index: 3,
		  item_id: 'item:besace', nom: 'Besace', icon: '👜', libre: 6 },
		{ cle: 'monture:ane#0', porteur_id: 'monture:ane', porteur_nom: 'Grison', index: 0,
		  item_id: 'item:sac_maree', nom: 'Sac de Manannán', libre: null },
	],
};
const cles = l => l.map(d => d.cle);

test('depuis votre sac : tout le groupe porteur, ses contenants, puis le sol — pas vous', () => {
	const out = destinationsTransmettre(GRP, { porteur_id: 'character:moi' }, { poids: 4 });
	assert.deepStrictEqual(cles(out), ['aventurier:aldric', 'monture:ane', 'monture:guide',
		'character:moi#3', 'monture:ane#0', 'sol']);
	assert.deepStrictEqual(out[out.length - 1].cible, { sol: true });
	assert.deepStrictEqual(out[3].cible, { porteur_id: 'character:moi', contenant_index: 3, contenant_item_id: 'item:besace' });
});

test('depuis le sol : vous compris, jamais le sol', () => {
	const out = destinationsTransmettre(GRP, { sol: true }, { poids: 1 });
	assert.strictEqual(out[0].cle, 'character:moi');
	assert.ok(!out.some(d => d.sol));
});

test('depuis un contenant : lui seul est exclu, son porteur reste une destination', () => {
	const src = { porteur_id: 'character:moi', contenant_index: 3, contenant_item_id: 'item:besace' };
	const out = destinationsTransmettre(GRP, src, { poids: 1 });
	assert.ok(cles(out).includes('character:moi'));
	assert.ok(!cles(out).includes('character:moi#3'));
	assert.ok(cles(out).includes('monture:ane#0') && cles(out).includes('sol'));
});

test('place : trop lourd grisé avec sa raison, égalité admise, marée basse laissée au serveur', () => {
	const out = destinationsTransmettre(GRP, { sol: true }, { poids: 6 });
	const par = Object.fromEntries(out.map(d => [d.cle, d]));
	assert.strictEqual(par['aventurier:aldric'].rentre, false);
	assert.strictEqual(par['aventurier:aldric'].raison, 'trop lourd');
	assert.strictEqual(par['character:moi#3'].rentre, true, '6 kg pour 6 libres');
	assert.strictEqual(par['monture:ane#0'].rentre, true);
	assert.strictEqual(trmPlaceTexte(par['monture:ane#0']), 'place inconnue (marée basse)');
	assert.strictEqual(trmPlaceTexte(par['aventurier:aldric']), '2.0 kg libres');
});

test('un contenant ne va dans aucun contenant, mais va partout ailleurs', () => {
	const out = destinationsTransmettre(GRP, { porteur_id: 'monture:ane' }, { poids: 0.5, contenant: true });
	assert.ok(out.filter(d => d.cible.contenant_index != null).every(d => !d.rentre && /contenant/.test(d.raison)));
	assert.ok(out.filter(d => d.cible.contenant_index == null).every(d => d.rentre));
});

test('sans groupe : le sol reste, et les contenants du joueur', () => {
	const seul = { principal: GRP.principal, contenants: [GRP.contenants[0]] };
	assert.deepStrictEqual(cles(destinationsTransmettre(seul, { porteur_id: 'character:moi' }, { poids: 1 })),
		['character:moi#3', 'sol']);
	assert.deepStrictEqual(cles(destinationsTransmettre(null, { porteur_id: 'character:moi' }, {})), ['sol']);
});

test('même emplacement', () => {
	assert.ok(trmMemeEmplacement({ sol: true }, { sol: true }));
	assert.ok(!trmMemeEmplacement({ sol: true }, { porteur_id: 'x' }));
	assert.ok(!trmMemeEmplacement({ porteur_id: 'x' }, { porteur_id: 'x', contenant_index: 0, contenant_item_id: 'i' }));
	assert.ok(trmMemeEmplacement({ porteur_id: 'x', contenant_index: '0', contenant_item_id: 'i' },
		{ porteur_id: 'x', contenant_index: 0, contenant_item_id: 'i' }));
});

test('position : au clic, ramenée dans la fenêtre', () => {
	assert.deepStrictEqual(trmPosition(100, 100, 200, 150, 1000, 800), { left: 100, top: 100 });
	assert.deepStrictEqual(trmPosition(900, 100, 200, 150, 1000, 800), { left: 792, top: 100 }, 'collé à droite');
	assert.deepStrictEqual(trmPosition(100, 750, 200, 150, 1000, 800), { left: 100, top: 600 }, 'retourné au-dessus');
	assert.deepStrictEqual(trmPosition(100, 100, 200, 790, 1000, 800), { left: 100, top: 8 }, 'plus haut que la fenêtre');
});

test('bouton : adresse et objet en data-*, échappés ; compact = icône seule', () => {
	const xss = '"><img src=x onerror=alert(1)>';
	const html = transmettreBtn({ porteur_id: 'aventurier:a' }, 4, { _id: 'item:x', nom: xss, poids: 2.5, contenant: {} });
	assert.ok(!/<img/.test(html));
	assert.ok(/onclick="ouvrirTransmettre\(event, this\)"/.test(html));
	assert.ok(/data-idx="4"/.test(html) && /data-poids="2.5"/.test(html) && /data-ctn="1"/.test(html));
	assert.ok(/>⇄ Transmettre<\/button>$/.test(html));
	assert.ok(/>⇄<\/button>$/.test(transmettreBtn({ sol: true }, 0, {}, { compact: true })));
});

test('/play : plus aucun « Poser », chaque sac du groupe porte le menu', () => {
	const { lireAvecIncludes } = require('./_template_js');
	const page = lireAvecIncludes(path.join(__dirname, '..', 'templates', 'play_town_telluris.html'));
	assert.ok(!/>Poser<\/button>/.test(page) && !/dropItem\(/.test(page) && !/donnerDuSol\(/.test(page));
	assert.ok(page.includes("script_url('transmettre.js')"));
	for (const site of ['{ porteur_id: porteurActifId() }, idx, item', '{ sol: true }, idx, item',
		'_grpSourceTrm(', '_pcfSourceTrm(ctnG)', 'contenant_index: st.index']) {
		assert.ok(page.includes('transmettreBtn(' + site) || page.includes(site), 'site absent : ' + site);
	}
});

console.log(`OK — ${ok} tests transmettre (client).`);
