// dev/test_sons_client.js
//
// Tests d'EXÉCUTION de la brique sonore partagée (templates/scripts/sons.js) :
//   • `cleSonApi` : URL relative/absolue/avec query → clé de son, `*` = un segment ;
//   • `choisirFichier` : variante bornée quel que soit l'aléa ;
//   • le catalogue ne cite QUE des fichiers présents dans templates/resources/sounds ;
//   • chaque route de `SONS_API` est une VRAIE route POST des routers (une faute de frappe
//     rendrait l'action muette sans un mot) et pointe une clé de `SONS_UI` ;
//   • `SONS_JOURNAL` (combat_telluris.html) ne cite que des clés de `SONS_UI`.
//
//   node dev/test_sons_client.js     # sort en code 1 au premier échec
//
// MÉTHODE : le script est chargé tel quel par `vm.runInThisContext` (il ne touche au DOM
// qu'à l'appel) ; `SONS_JOURNAL` est extrait du template par expression régulière.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const RACINE = path.join(__dirname, '..');
const SCRIPT = path.join(RACINE, 'templates', 'scripts', 'sons.js');
// `const` de premier niveau : invisibles comme globales d'un autre script, on les expose.
vm.runInThisContext(fs.readFileSync(SCRIPT, 'utf8')
	+ '\nglobalThis.SONS_UI = SONS_UI; globalThis.SONS_API = SONS_API;', { filename: SCRIPT });

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

const TABLE = { 'equip': 'equiper', 'quetes/accepter': 'valider', 'combat/*/collect': 'pieces' };

t('URL relative, absolue, avec / et query', () => {
	assert.strictEqual(cleSonApi('api/equip', TABLE), 'equiper');
	assert.strictEqual(cleSonApi('/api/equip', TABLE), 'equiper');
	assert.strictEqual(cleSonApi('https://x.fr/api/equip?y=1#z', TABLE), 'equiper');
	assert.strictEqual(cleSonApi('api/quetes/accepter/', TABLE), 'valider');
});
t('aucune correspondance partielle', () => {
	assert.strictEqual(cleSonApi('api/equipement', TABLE), '');
	assert.strictEqual(cleSonApi('api/unequip', TABLE), '');
	assert.strictEqual(cleSonApi('api/quetes', TABLE), '');
	assert.strictEqual(cleSonApi('/equip', TABLE), '');
	assert.strictEqual(cleSonApi('', TABLE), '');
});
t('`*` vaut UN segment', () => {
	assert.strictEqual(cleSonApi('/api/combat/combat:abc/collect', TABLE), 'pieces');
	assert.strictEqual(cleSonApi('/api/combat/collect', TABLE), '');
	assert.strictEqual(cleSonApi('/api/combat/a/b/collect', TABLE), '');
});
t('choisirFichier reste dans la liste', () => {
	const e = { fichiers: ['a', 'b', 'c'] };
	assert.strictEqual(choisirFichier(e, () => 0), 'a');
	assert.strictEqual(choisirFichier(e, () => 0.5), 'b');
	assert.strictEqual(choisirFichier(e, () => 0.9999), 'c');
	assert.strictEqual(choisirFichier(e, () => 1), 'c');      // borne haute défensive
	assert.strictEqual(choisirFichier({ fichiers: [] }, () => 0), '');
	assert.strictEqual(choisirFichier(null, () => 0), '');
});

t('urlSon encode chaque segment, garde le /', () => {
	assert.strictEqual(urlSon('a b.mp3'), '/sounds/a%20b.mp3');
	assert.strictEqual(urlSon('taverne/Ambiance Taverne !.mp3'), '/sounds/taverne/Ambiance%20Taverne%20!.mp3');
	assert.strictEqual(urlSon('taverne/Médiévale #1.mp3'), '/sounds/taverne/M%C3%A9di%C3%A9vale%20%231.mp3');
});
t('morceauSuivant ne rejoue pas le même morceau', () => {
	const l = ['a', 'b', 'c'];
	for (const r of [0, 0.4, 0.9999]) assert.notStrictEqual(morceauSuivant(l, 'b', () => r), 'b');
	assert.strictEqual(morceauSuivant(['a'], 'a', () => 0), 'a');           // liste d'un seul
	assert.strictEqual(morceauSuivant(l, undefined, () => 0), 'a');         // premier tirage
	assert.strictEqual(morceauSuivant([], 'a', () => 0), '');
});

t('_rampe : durée nulle = volume posé, rampe récente prioritaire', () => {
	const a = { volume: 0.8 };
	_rampe(a, 0.3, 0);
	assert.strictEqual(a.volume, 0.3);
	_rampe(a, 0, 10000);            // rampe longue en cours…
	const j = a._rampe;
	_rampe(a, 0.5, 0);              // …la plus récente gagne
	assert.ok(a._rampe > j);
	assert.strictEqual(a.volume, 0.5);
	_rampe(a, 2, 0);
	assert.strictEqual(a.volume, 1);   // borné à [0, 1]
});

const SONS = new Set(fs.readdirSync(path.join(RACINE, 'templates', 'resources', 'sounds')));
t('chaque fichier de SONS_UI existe', () => {
	const manquants = [];
	Object.entries(SONS_UI).forEach(([cle, e]) => {
		assert.ok(e.fichiers.length, cle + ' sans fichier');
		assert.ok(e.volume > 0 && e.volume <= 1, cle + ' : volume hors ]0,1]');
		e.fichiers.forEach(f => { if (!SONS.has(f)) manquants.push(cle + ' → ' + f); });
	});
	assert.deepStrictEqual(manquants, []);
});

// Routes POST des routers, montés sous /api (`{param}` → `*`).
const ROUTES = new Set();
const DIR_ROUTERS = path.join(RACINE, 'routers');
fs.readdirSync(DIR_ROUTERS).filter(f => f.endsWith('.py')).forEach(f => {
	const src = fs.readFileSync(path.join(DIR_ROUTERS, f), 'utf8');
	for (const m of src.matchAll(/\.post\(\s*"\/([^"]+)"/g)) ROUTES.add(m[1].replace(/\{[^}]+\}/g, '*'));
});
t('chaque route de SONS_API existe et pointe une clé de SONS_UI', () => {
	assert.ok(ROUTES.size > 0, 'aucune route lue dans routers/');
	const fautes = [];
	Object.entries(SONS_API).forEach(([route, cle]) => {
		if (!ROUTES.has(route)) fautes.push('route inconnue : ' + route);
		if (!SONS_UI[cle]) fautes.push(route + ' → clé inconnue ' + cle);
	});
	assert.deepStrictEqual(fautes, []);
});

t('SONS_JOURNAL du combat ne cite que des clés de SONS_UI', () => {
	const tpl = fs.readFileSync(path.join(RACINE, 'templates', 'combat_telluris.html'), 'utf8');
	const m = tpl.match(/const SONS_JOURNAL = (\{[^}]*\});/);
	assert.ok(m, 'SONS_JOURNAL introuvable dans combat_telluris.html');
	const table = vm.runInThisContext('(' + m[1] + ')');
	Object.values(table).forEach(cle => assert.ok(SONS_UI[cle], 'clé inconnue ' + cle));
	// Les clés jouées en dur par les deux pages.
	['victoire', 'defaite', 'degainer', 'pas', 'porte', 'choix', 'sac', 'onglet', 'ouvrir', 'fermer']
		.forEach(cle => assert.ok(SONS_UI[cle], 'clé ' + cle + ' absente de SONS_UI'));
});

console.log(`\n${passes} passé(s), ${echecs} échec(s)`);
process.exit(echecs ? 1 : 0);
