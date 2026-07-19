// dev/test_slots_client.js
//
// Tests d'EXÉCUTION du JavaScript de la barre d'action de combat
// (templates/combat_telluris.html, cf. § « Barre d'action de combat » de CLAUDE.md).
//
//   node dev/test_slots_client.js      # sort en code 1 au premier échec
//
// POURQUOI : le bug du 2026-07-19 — la barre d'un compagnon écrite sur le doc du
// personnage principal — vivait entièrement côté client. Aucun test pytest ne pouvait
// l'atteindre, et il n'a été trouvé qu'en jouant. Ces assertions ferment cette classe
// de défaut : « à qui appartient ce que j'affiche et ce que j'écris ? ».
//
// MÉTHODE : on extrait du template les fonctions PURES (celles qui ne lisent que les
// globales de données) et on les exécute dans un contexte `vm` avec des fixtures. Pas de
// DOM, donc AUCUNE dépendance — le rendu, le clic long et l'ordre inversé en mobile
// restent hors de portée et doivent être vérifiés en jeu (il faudrait jsdom pour aller
// plus loin, et donc un package.json que le projet n'a pas).
//
// ⚠️ L'extraction se fait par NOM de fonction : renommer une fonction ici visée fait
// échouer le test avec « fonction introuvable » — c'est voulu, pas un faux positif.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'combat_telluris.html');
const src = fs.readFileSync(TEMPLATE, 'utf8');
const js = (src.match(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/i) || [])[1];
assert.ok(js, 'aucun bloc <script> trouvé dans ' + TEMPLATE);

// Extrait une fonction nommée par équilibrage des accolades (pas de regex sur le corps :
// une accolade dans une chaîne ou un littéral de gabarit fausserait le compte).
function extraire(nom) {
	const debut = js.indexOf('function ' + nom + '(');
	assert.ok(debut >= 0, 'fonction ' + nom + ' introuvable dans le template');
	let prof = 0;
	for (let j = js.indexOf('{', debut); j < js.length; j++) {
		if (js[j] === '{') prof++;
		else if (js[j] === '}' && --prof === 0) return js.slice(debut, j + 1);
	}
	throw new Error('accolades déséquilibrées dans ' + nom);
}

const ctx = { state: null, SERVER_DATA: null, SORTS: [], console };
vm.createContext(ctx);
for (const f of ['activePlayer', 'acteurCompagnonId', 'slotSort', 'slotCompoPlus', 'slotComposants']) {
	vm.runInContext(extraire(f), ctx);
}

// ── Fixtures : un groupe (principal + compagnon) face à un monstre ───────────────
const PRINCIPAL = { id: 'joueur_0', character_id: 'character:moi' };
const COMPAGNON = { id: 'joueur_1', character_id: 'aventurier:brann' };
ctx.SERVER_DATA = { character_id: 'character:moi' };

const combat = (acteurCourantIndex) => ({
	ordre_initiative: ['joueur_0', 'joueur_1', 'monstre_0'],
	acteur_courant_index: acteurCourantIndex,
	joueurs: [PRINCIPAL, COMPAGNON],
});

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

// ── À QUI appartient la barre affichée / écrite ──────────────────────────────────
// RÉGRESSION : `/api/slot_action` passe par le chokepoint `_acteur`, qui SANS
// `compagnon_id` retombe silencieusement sur le principal. Réorganiser la barre d'un
// compagnon écrivait alors sur le mauvais doc, ET la réponse renvoyait la barre du
// principal, affichée comme celle du compagnon : les deux finissaient mélangées.
console.log('\n— À qui appartient la barre —');

t('tour du principal → aucun compagnon_id (sinon _acteur renverrait 403)', () => {
	ctx.state = combat(0);
	assert.strictEqual(ctx.acteurCompagnonId(), null);
});

t('tour du compagnon → SON doc est visé, pas celui du principal', () => {
	ctx.state = combat(1);
	assert.strictEqual(ctx.acteurCompagnonId(), 'aventurier:brann');
});

t('tour du monstre → repli sur le principal, pas sur le dernier acteur joué', () => {
	// Le client replie sur joueurs[0], le serveur sur combat["character_id"] : les deux
	// doivent désigner le MÊME personnage (cf. tests/test_combat_slots.py), sinon la
	// barre affichée et la cible d'écriture divergent.
	ctx.state = combat(2);
	assert.strictEqual(ctx.acteurCompagnonId(), null);
});

// ── Badge « + » et composants réellement engagés ─────────────────────────────────
// Le flag `composants` d'une case ne gouverne QUE les composants consommés ; les
// catalyseurs partent toujours (ils ne se consomment pas, s'en priver n'aurait aucune
// contrepartie). Le badge s'éteint quand il ne reste plus rien à dépenser.
console.log('\n— Badge « + » et composants engagés —');

ctx.SORTS = [{
	sort_id: 'sort:trait', nom: 'Trait de feu',
	composants: [
		{ item: 'item:soufre',   consomme: true,  disponible: true },
		{ item: 'item:cendre',   consomme: true,  disponible: false },
		{ item: 'item:amulette', consomme: false, disponible: true },
	],
}];
const avec = { type: 'sort', ref: 'sort:trait', composants: true };
const sans = { type: 'sort', ref: 'sort:trait', composants: false };

t('« + » affiché quand un composant consommé est disponible', () => {
	assert.strictEqual(ctx.slotCompoPlus(avec), true);
});

t('« + » absent sur la variante configurée sans composants', () => {
	assert.strictEqual(ctx.slotCompoPlus(sans), false);
});

t('« + » s\'éteint quand il ne reste plus de consommé disponible', () => {
	ctx.SORTS[0].composants[0].disponible = false;
	assert.strictEqual(ctx.slotCompoPlus(avec), false);
	ctx.SORTS[0].composants[0].disponible = true;
});

t('« + » jamais sur un type non-sort', () => {
	assert.strictEqual(ctx.slotCompoPlus({ type: 'consommable', ref: 'item:potion' }), false);
});

t('avec composants : les consommés disponibles ET les catalyseurs', () => {
	assert.deepStrictEqual(ctx.slotComposants(avec, ctx.SORTS[0]), ['item:soufre', 'item:amulette']);
});

t('sans composants : les CATALYSEURS partent quand même', () => {
	assert.deepStrictEqual(ctx.slotComposants(sans, ctx.SORTS[0]), ['item:amulette']);
});

t('un composant indisponible n\'est jamais engagé', () => {
	assert.ok(!ctx.slotComposants(avec, ctx.SORTS[0]).includes('item:cendre'));
});

console.log('\n' + passes + ' passé(s), ' + echecs + ' échec(s).');
process.exit(echecs ? 1 : 0);
