// dev/test_lecture_lore_client.js
//
// Tests d'EXÉCUTION de la lecture à voix haute du lore (templates/admin_lore.html).
//
//   node dev/test_lecture_lore_client.js     # sort en code 1 au premier échec
//
// POURQUOI : la synthèse vocale du navigateur prononce tout ce qu'on lui donne — un emoji
// devient « visage souriant », un énoncé trop long est coupé net par Chrome — et le filtre
// « Auteur seulement » doit garder exactement les messages de l'Auteur d'une séance.
//
// MÉTHODE : extraction par nom (accolades équilibrées), `runInThisContext`.
//
// HORS DE PORTÉE (à vérifier à l'écran, CLAUDE.md §15) : `speechSynthesis` lui-même, les voix,
// le surlignage du bloc lu, la reprise au clic.

const path = require('path');
const assert = require('assert');
const vm = require('vm');
const { lireAvecIncludes, scriptsInline } = require('./_template_js');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'admin_lore.html');
const js = scriptsInline(lireAvecIncludes(TEMPLATE));
assert.ok(js, 'aucun bloc <script> dans ' + TEMPLATE);

function extraire(nom) {
	const debut = js.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable');
	let prof = 0;
	for (let j = js.indexOf('{', debut); j < js.length; j++) {
		if (js[j] === '{') prof++;
		else if (js[j] === '}' && --prof === 0) return js.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}

const FONCTIONS = ['lectureNettoyer', 'lectureDecouper', 'lectureSelection'];
vm.runInThisContext(FONCTIONS.map(extraire).join('\n') + '\nglobalThis.F = {' + FONCTIONS.join(',') + '};');

let echecs = 0, n = 0;
function t(nom, fn) {
	n++;
	try { fn(); console.log('  ok  ' + nom); }
	catch (e) { echecs++; console.log('  ÉCHEC ' + nom + '\n       ' + (e && e.stack || e)); }
}

t('nettoyer : pictogrammes retirés, en-têtes de séance lus en clair', () => {
	assert.strictEqual(F.lectureNettoyer('✍️ Auteur'), "L'Auteur");
	assert.strictEqual(F.lectureNettoyer('🤖 ChatGPT'), 'ChatGPT');
	assert.strictEqual(F.lectureNettoyer('🏰  Cités-États\n et lieux ⚜'), 'Cités-États et lieux');
	assert.strictEqual(F.lectureNettoyer('Lutecia → Mu'), 'Lutecia Mu');
	assert.strictEqual(F.lectureNettoyer(''), '');
});

t('nettoyer : lettres accentuées, chiffres et ponctuation gardés', () => {
	const s = "Il y a 750 ans, l'Âge des Remparts : « Néfertiti » !";
	assert.strictEqual(F.lectureNettoyer(s), s);
});

t('découper : phrases regroupées sous le plafond, aucune perte de texte', () => {
	const texte = 'Une phrase. Une autre ! Encore une ? Et la dernière.';
	assert.deepStrictEqual(F.lectureDecouper(texte, 200), [texte]);
	const parts = F.lectureDecouper(texte, 25);
	assert.ok(parts.every(p => p.length <= 25), parts);
	assert.strictEqual(parts.join(' '), texte);
});

t('découper : une phrase trop longue est coupée aux mots, jamais au milieu d\'un mot', () => {
	const mots = Array.from({ length: 80 }, (_, i) => 'mot' + i);
	const texte = mots.join(' ') + '.';
	const parts = F.lectureDecouper(texte, 60);
	assert.ok(parts.length > 1 && parts.every(p => p.length <= 60), parts);
	assert.strictEqual(parts.join(' '), texte);
	assert.deepStrictEqual(F.lectureDecouper('anticonstitutionnellement', 5), ['anticonstitutionnellement']);
	assert.deepStrictEqual(F.lectureDecouper('', 200), []);
});

t('sélection : tout, ou seulement ce qui suit un h2 de l\'Auteur', () => {
	const blocs = [
		{ h2: false }, // h1 de la séance
		{ h2: true, auteur: true }, { h2: false }, { h2: false },
		{ h2: true, auteur: false }, { h2: false },
		{ h2: true, auteur: true }, { h2: false }
	];
	assert.deepStrictEqual(F.lectureSelection(blocs, false), [0, 1, 2, 3, 4, 5, 6, 7]);
	assert.deepStrictEqual(F.lectureSelection(blocs, true), [1, 2, 3, 6, 7]);
	assert.deepStrictEqual(F.lectureSelection([{ h2: false }, { h2: true }], true), []);
});

console.log(`\n${n - echecs} / ${n} tests passés`);
process.exit(echecs ? 1 : 0);
