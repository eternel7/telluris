// dev/test_deplacement_client.js
//
// Tests d'EXÉCUTION des règles de marche partagées (templates/scripts/deplacement.js).
//
//   node dev/test_deplacement_client.js     # sort en code 1 au premier échec
//
// POURQUOI : IL N'Y A AUCUNE RÈGLE DE MARCHE CÔTÉ SERVEUR. La branche x/y de
// `move_character` ne valide que les bornes — ni terrain, ni `nav`. `deplacement.js` n'est
// donc pas un double du serveur, IL EST la règle du jeu, et ce harnais en est le SEUL test :
// pytest ne peut pas l'atteindre, et `check_js.js` ne prouve que la syntaxe.
//
// MÉTHODE : contrairement à `test_slots_client` et `test_resize_client`, il n'y a rien à
// extraire d'un template — on charge DIRECTEMENT le `.js`, avec `nav.js` dont il dépend.
// `vm.runInThisContext` et non `vm.createContext` : un contexte séparé est un autre realm,
// donc ses objets ont d'autres prototypes et `deepStrictEqual` les refuse (même raison que
// dans `test_resize_client`).
//
// HORS DE PORTÉE (à vérifier en jeu) : `majFleches`/`verrouillerFleches` touchent le DOM.
// Un faux `querySelectorAll` suffit à éprouver leur PARCOURS, pas leur rendu.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const SCRIPTS = path.join(__dirname, '..', 'templates', 'scripts');
for (const f of ['nav.js', 'deplacement.js']) {
	const p = path.join(SCRIPTS, f);
	assert.ok(fs.existsSync(p), 'fichier introuvable : ' + p);
	vm.runInThisContext(fs.readFileSync(p, 'utf8'), { filename: p });
}

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

// Grille de référence 5×4. Terrain : 1 libre, 2 difficile, 3 falaise, 0 mur.
//        x=0  1  2  3  4
const CELLS = [
	[1, 1, 1, 1, 1],   // y=0
	[1, 2, 3, 0, 1],   // y=1
	[1, 1, 1, 1, 1],   // y=2
	[1, 1, 1, 1, 1],   // y=3
];
const DIMS = { x: 5, y: 4 };

console.log('\n── Les TROIS règles de case ────────────────────────────────────────────────');

t('caseType1 : seul le terrain EXACTEMENT 1 (règle d’EXPLORATION)', () => {
	assert.strictEqual(caseType1(CELLS, 0, 0), true);
	assert.strictEqual(caseType1(CELLS, 1, 1), false, 'terrain difficile 2 refusé à pied');
	assert.strictEqual(caseType1(CELLS, 2, 1), false, 'falaise 3');
	assert.strictEqual(caseType1(CELLS, 3, 1), false, 'mur 0');
});

t('caseType1 : hors grille et lignes absentes ne lèvent pas', () => {
	assert.strictEqual(caseType1(CELLS, -1, 0), false);
	assert.strictEqual(caseType1(CELLS, 0, 99), false);
	assert.strictEqual(caseType1(CELLS, 99, 0), false);
	assert.strictEqual(caseType1(null, 0, 0), false);
});

t('caseFranchissable : >= 1 sauf falaise (règle de COMBAT)', () => {
	assert.strictEqual(caseFranchissable(CELLS, 1, 1), true, 'le terrain difficile se franchit en combat');
	assert.strictEqual(caseFranchissable(CELLS, 2, 1), false, 'la falaise, non');
	assert.strictEqual(caseFranchissable(CELLS, 2, 1, true), true, '… sauf pour un volant');
	assert.strictEqual(caseFranchissable(CELLS, 3, 1), false, 'mur 0');
});

t('les deux règles DIVERGENT bien sur le terrain difficile — c’est tout l’objet du mode test', () => {
	assert.strictEqual(caseType1(CELLS, 1, 1), false);
	assert.strictEqual(caseFranchissable(CELLS, 1, 1), true);
});

console.log('\n── pasAutoriseLocal : le MOTIF, pas un booléen ─────────────────────────────');

t('un pas ordinaire est autorisé', () => {
	const r = pasAutoriseLocal(CELLS, {}, DIMS, 0, 0, 1, 0);
	assert.deepStrictEqual(r, { ok: true, raison: '' });
});

t('hors carte : motif « hors carte »', () => {
	assert.deepStrictEqual(pasAutoriseLocal(CELLS, {}, DIMS, 0, 0, -1, 0),
		{ ok: false, raison: 'hors carte' });
	assert.deepStrictEqual(pasAutoriseLocal(CELLS, {}, DIMS, 4, 3, 1, 1),
		{ ok: false, raison: 'hors carte' });
});

t('terrain refusé : le motif NOMME la valeur de la case', () => {
	assert.deepStrictEqual(pasAutoriseLocal(CELLS, {}, DIMS, 0, 1, 1, 0),
		{ ok: false, raison: 'terrain 2' });
	assert.deepStrictEqual(pasAutoriseLocal(CELLS, {}, DIMS, 1, 1, 1, 0),
		{ ok: false, raison: 'terrain 3' });
	assert.deepStrictEqual(pasAutoriseLocal(CELLS, {}, DIMS, 2, 1, 1, 0),
		{ ok: false, raison: 'terrain 0' });
});

t('bornes en < dims (0..dim-1) et non <= : la colonne dims.x est HORS carte', () => {
	// Le garde serveur teste `<= dimensions.x` — borne inclusive, donc il laisse passer une
	// colonne qui n'existe pas dans `cells`. Le mode test suit ce que le joueur peut cliquer.
	assert.strictEqual(pasAutoriseLocal(CELLS, {}, DIMS, 4, 0, 1, 0).raison, 'hors carte');
});

t('une ligne ABSENTE de cells est refusée sans lever (doc où dimensions ment)', () => {
	const courtes = [[1, 1, 1, 1, 1], [1, 1, 1, 1, 1]];  // 2 lignes, dims en annonce 4
	const r = pasAutoriseLocal(courtes, {}, DIMS, 2, 1, 0, 1);
	assert.strictEqual(r.ok, false);
	assert.strictEqual(r.raison, 'case absente de cells');
});

console.log('\n── nav : bidirectionnel, jamais un « mask & bit » maison ───────────────────');

t('un mur posé sur la case SOURCE ferme la direction', () => {
	const nav = { '0,0': 4 };   // DROITE interdite depuis (0,0)
	assert.deepStrictEqual(pasAutoriseLocal(CELLS, nav, DIMS, 0, 0, 1, 0),
		{ ok: false, raison: 'mur nav' });
	assert.strictEqual(pasAutoriseLocal(CELLS, nav, DIMS, 0, 0, 0, 1).ok, true, 'les autres passent');
});

t('⚠️ un mur posé sur la case CIBLE ferme AUSSI la direction (bidirectionnel)', () => {
	// C'est le piège : la source n'interdit rien, mais (1,0) refuse qu'on entre par la
	// gauche. Un `mask & bit` lu sur la seule source laisserait traverser.
	const nav = { '1,0': 64 };  // GAUCHE interdite depuis (1,0) = l'entrée par la droite
	assert.deepStrictEqual(pasAutoriseLocal(CELLS, nav, DIMS, 0, 0, 1, 0),
		{ ok: false, raison: 'mur nav' });
});

t('nav vide ⇒ tout est permis', () => {
	assert.strictEqual(pasAutoriseLocal(CELLS, {}, DIMS, 0, 2, 1, 1).ok, true);
	assert.strictEqual(pasAutoriseLocal(CELLS, null, DIMS, 0, 2, 1, 1).ok, true);
});

t('l’ordre des contrôles : le TERRAIN prime sur nav (le motif le plus parlant gagne)', () => {
	const nav = { '0,0': 4 };
	// (1,1) est du terrain 2 ET fermé par nav en diagonale ; on nomme le terrain.
	assert.strictEqual(pasAutoriseLocal(CELLS, nav, DIMS, 0, 0, 1, 1).raison, 'terrain 2');
});

console.log('\n── majFleches / verrouillerFleches : le PARCOURS du DOM ────────────────────');

// Faux boutons : juste ce que les deux fonctions touchent (dataset, disabled, classList).
function faussesFleches(dirs) {
	const btns = dirs.map(([dx, dy]) => {
		const b = { dataset: { sdx: String(dx), sdy: String(dy) }, disabled: false, classes: new Set() };
		// `classList.toggle` doit viser SON bouton : la fermeture le capture.
		b.classList = { toggle: (c, on) => on ? b.classes.add(c) : b.classes.delete(c) };
		return b;
	});
	return { querySelectorAll: () => btns, _btns: btns };
}

const HUIT = [[-1,-1],[0,-1],[1,-1],[-1,0],[1,0],[-1,1],[0,1],[1,1]];

t('majFleches grise les directions refusées et rouvre les autres', () => {
	const racine = faussesFleches(HUIT);
	majFleches(racine, { autorise: (dx, dy) => pasAutoriseLocal(CELLS, {}, DIMS, 0, 0, dx, dy) });
	const etat = {};
	racine._btns.forEach(b => { etat[`${b.dataset.sdx},${b.dataset.sdy}`] = !b.disabled; });
	// Depuis (0,0) : trois directions seulement existent — DROITE (1,0) et BAS (0,1) sont du
	// type 1, mais BAS_DROITE tombe sur (1,1), du terrain difficile 2 : elle reste grise.
	assert.deepStrictEqual(etat, {
		'-1,-1': false, '0,-1': false, '1,-1': false, '-1,0': false,
		'1,0': true, '-1,1': false, '0,1': true, '1,1': false,
	});
});

t('majFleches accepte aussi un prédicat qui rend un simple booléen', () => {
	const racine = faussesFleches(HUIT);
	majFleches(racine, { autorise: (dx) => dx === 1 });
	racine._btns.forEach(b => {
		assert.strictEqual(b.disabled, b.dataset.sdx !== '1');
	});
});

t('⚠️ sans `exergue`, .btn-highlight n’est JAMAIS touchée', () => {
	// Ni le combat ni l'éditeur n'ont de guidage — et l'éditeur ne définit même pas la classe.
	const racine = faussesFleches(HUIT);
	racine._btns[0].classes.add('btn-highlight');   // posée par ailleurs : elle doit survivre
	majFleches(racine, { autorise: () => true });
	assert.ok(racine._btns[0].classes.has('btn-highlight'));
});

t('avec `exergue`, une seule flèche s’allume — et jamais une flèche grisée', () => {
	const racine = faussesFleches(HUIT);
	majFleches(racine, {
		autorise: (dx, dy) => pasAutoriseLocal(CELLS, {}, DIMS, 0, 0, dx, dy),
		exergue: (dx, dy) => dx === 1 && dy === 0,
	});
	const allumees = racine._btns.filter(b => b.classes.has('btn-highlight'));
	assert.strictEqual(allumees.length, 1);
	assert.strictEqual(allumees[0].dataset.sdx, '1');
});

t('l’exergue ne s’allume pas sur une direction refusée', () => {
	const racine = faussesFleches(HUIT);
	majFleches(racine, {
		autorise: () => ({ ok: false, raison: 'mur nav' }),
		exergue: () => true,
	});
	assert.strictEqual(racine._btns.filter(b => b.classes.has('btn-highlight')).length, 0);
});

t('verrouillerFleches ferme puis rouvre tout le pavé', () => {
	const racine = faussesFleches(HUIT);
	verrouillerFleches(racine, true);
	assert.ok(racine._btns.every(b => b.disabled));
	verrouillerFleches(racine, false);
	assert.ok(racine._btns.every(b => !b.disabled));
});

console.log(`\n${passes} test(s) OK, ${echecs} échec(s).`);
process.exit(echecs ? 1 : 0);
