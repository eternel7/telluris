// dev/test_partage_client.js
//
// Tests d'EXÉCUTION de templates/scripts/partage.js (bouton 🔗 Partager des pages du lore) :
//   • feuille de partage native quand elle existe ; fermée par l'utilisateur ⇒ rien d'autre ;
//   • sinon (ou refusée) copie au presse-papiers, puis repli `execCommand('copy')` ;
//   • les trois pages du lore chargent le script et portent un bouton `data-partager`.
//   ⚠️ Le filtre de l'index (fichiers masqués par `hidden`) : contrôle de la règle CSS qui
//   empêche `display:block` de l'emporter sur l'attribut.
//
//   node dev/test_partage_client.js     # sort en code 1 au premier échec
//
// MÉTHODE : script chargé tel quel (`vm.runInThisContext`, sans `document` : il ne s'installe
// pas) ; `navigator` et `document` sont des doublures passées en argument.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const RACINE = path.join(__dirname, '..');
const SCRIPT = path.join(RACINE, 'templates', 'scripts', 'partage.js');
vm.runInThisContext(fs.readFileSync(SCRIPT, 'utf8'), { filename: SCRIPT });

let passes = 0, echecs = 0;
const taches = [];
function t(nom, fn) { taches.push([nom, fn]); }

function faux_doc(copieOk) {
	const journal = { copies: 0, ajoutes: 0, retires: 0 };
	return {
		journal,
		body: { appendChild() { journal.ajoutes++; }, removeChild() { journal.retires++; } },
		createElement() { return { style: {}, setAttribute() {}, select() {} }; },
		execCommand(cmd) { assert.strictEqual(cmd, 'copy'); journal.copies++; return copieOk; },
	};
}
const URL_ = 'http://localhost:8000/admin/lore/x.md#section';

t('partage natif disponible ⇒ partage, sans copie', async () => {
	let recu = null;
	const nav = { share: async d => { recu = d; }, clipboard: { writeText: async () => assert.fail('copie') } };
	assert.strictEqual(await partagerLien(URL_, 'Titre', nav, faux_doc(true)), 'partage');
	assert.deepStrictEqual(recu, { title: 'Titre', url: URL_ });
});

t('feuille fermée (AbortError) ⇒ annulé, aucune copie', async () => {
	const err = Object.assign(new Error('x'), { name: 'AbortError' });
	const nav = { share: async () => { throw err; }, clipboard: { writeText: async () => assert.fail('copie') } };
	assert.strictEqual(await partagerLien(URL_, 'T', nav, faux_doc(true)), 'annule');
});

t('partage refusé autrement ⇒ copie', async () => {
	let copie = null;
	const err = Object.assign(new Error('x'), { name: 'NotAllowedError' });
	const nav = { share: async () => { throw err; }, clipboard: { writeText: async s => { copie = s; } } };
	assert.strictEqual(await partagerLien(URL_, 'T', nav, faux_doc(true)), 'copie');
	assert.strictEqual(copie, URL_);
});

t('pas de partage natif ⇒ presse-papiers (ancre comprise)', async () => {
	let copie = null;
	const nav = { clipboard: { writeText: async s => { copie = s; } } };
	assert.strictEqual(await partagerLien(URL_, 'T', nav, faux_doc(false)), 'copie');
	assert.strictEqual(copie, URL_);
});

t('sans clipboard (http hors localhost) ⇒ repli execCommand, zone retirée', async () => {
	const doc = faux_doc(true);
	assert.strictEqual(await partagerLien(URL_, 'T', {}, doc), 'copie');
	assert.deepStrictEqual(doc.journal, { copies: 1, ajoutes: 1, retires: 1 });
});

t('clipboard qui échoue puis execCommand refusé ⇒ échec', async () => {
	const nav = { clipboard: { writeText: async () => { throw new Error('refus'); } } };
	assert.strictEqual(await partagerLien(URL_, 'T', nav, faux_doc(false)), 'echec');
});

t('les pages du lore chargent partage.js et portent un bouton data-partager', () => {
	for (const f of ['admin_lore.html', 'admin_lore_chronologie.html']) {
		const html = fs.readFileSync(path.join(RACINE, 'templates', f), 'utf8');
		assert.ok(html.includes("script_url('partage.js')"), f + ' : script absent');
		assert.ok(/<button[^>]*data-partager/.test(html), f + ' : bouton absent');
	}
	// La lecture d'un fichier et l'index partagent admin_lore.html : bouton HORS de tout {% if %}.
	const html = fs.readFileSync(path.join(RACINE, 'templates', 'admin_lore.html'), 'utf8');
	const nav = html.slice(html.indexOf('<nav>'), html.indexOf('</nav>'));
	const bouton = nav.indexOf('data-partager');
	assert.ok(bouton > nav.lastIndexOf('{% endif %}'), 'bouton conditionné');
});

t('filtre de l\'index : un fichier `hidden` est vraiment masqué malgré display:block', () => {
	const html = fs.readFileSync(path.join(RACINE, 'templates', 'admin_lore.html'), 'utf8');
	assert.ok(/a\.fichier\s*\{[^}]*display:\s*block/.test(html), 'prémisse : a.fichier en display:block');
	assert.ok(/a\.fichier\[hidden\][^{]*\{\s*display:\s*none/.test(html), 'règle a.fichier[hidden] absente');
});

(async () => {
	for (const [nom, fn] of taches) {
		try { await fn(); console.log('  OK   ' + nom); passes++; }
		catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
	}
	console.log(`\n${passes} OK, ${echecs} échec(s)`);
	process.exit(echecs ? 1 : 0);
})();
