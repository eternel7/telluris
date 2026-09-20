// dev/test_charge_magie_client.js
//
// Tests d'EXÉCUTION du miroir client de la charge magique.
//
//   node dev/test_charge_magie_client.js     # sort en code 1 au premier échec
//
// POURQUOI : `coutPmCharge` (combat_telluris.html) et `_coutPmCharge` (play_town) ne sont
// PAS la règle — le serveur tranche (utils/charge_magie.cout_pm_effectif). Mais ils
// pilotent le GRISAGE d'une case et l'étiquette « 8 → 11 PM ». Un miroir qui ment est pire
// que pas de miroir : la case paraît jouable et le moteur la refuse, ou elle part à un prix
// qui n'est pas celui affiché.
//
// Ce que le miroir reproduit : seulement la MULTIPLICATION finale et l'ARRONDI. La courbe
// f(ratio) ne vit que côté serveur et arrive déjà résolue dans `penalite`.
//
// MÉTHODE : extraction par nom depuis les deux templates (comme test_slots_client), puis
// `vm.runInThisContext` — un contexte séparé est un autre realm. Les VALEURS attendues sont
// les mêmes que celles de tests/test_charge_magie.py (§ arrondi), pour que les deux fichiers
// se lisent en vis-à-vis.
//
// HORS DE PORTÉE (à vérifier en jeu) : le rendu du libellé, la couleur violette, et le fait
// que le palier affiché soit bien celui que le serveur a calculé.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

// Extrait une fonction nommée d'un template, accolades équilibrées (même méthode que les
// autres harnais : on ne charge pas la page, on prend la fonction).
function extraireFonction(source, nom) {
	const debut = source.indexOf('function ' + nom + '(');
	assert.notStrictEqual(debut, -1, 'fonction introuvable : ' + nom);
	let i = source.indexOf('{', debut), profondeur = 0;
	for (let j = i; j < source.length; j++) {
		if (source[j] === '{') profondeur++;
		else if (source[j] === '}') {
			profondeur--;
			if (profondeur === 0) return source.slice(debut, j + 1);
		}
	}
	throw new Error('accolades non équilibrées pour ' + nom);
}

const COMBAT = fs.readFileSync(
	path.join(__dirname, '..', 'templates', 'combat_telluris.html'), 'utf8');
const VILLE = fs.readFileSync(
	path.join(__dirname, '..', 'templates', 'play_town_telluris.html'), 'utf8');

// Les deux miroirs, sous des noms distincts pour pouvoir les comparer l'un à l'autre.
vm.runInThisContext(extraireFonction(COMBAT, 'coutPmCharge'), { filename: 'combat' });
vm.runInThisContext(extraireFonction(COMBAT, 'pmTexte'), { filename: 'combat' });
vm.runInThisContext(extraireFonction(VILLE, '_coutPmCharge'), { filename: 'ville' });

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

// Les deux miroirs lisent une globale différente (CHARGE_MAGIE en combat, _chargeMagie en
// ville) : on les pose toutes les deux, comme la page le ferait.
function bloc(penalite, modificateur, sensibiliteDefaut) {
	const b = {
		penalite: penalite,
		modificateur: modificateur === undefined ? 1 : modificateur,
		sensibilite_defaut: sensibiliteDefaut === undefined ? 0.5 : sensibiliteDefaut,
		palier_label: 'importante',
	};
	globalThis.CHARGE_MAGIE = b;
	globalThis._chargeMagie = b;
	return b;
}

console.log('\n── Tarif de base quand rien ne pèse ────────────────────────────────────────');

t('aucun bloc de charge ⇒ coût de base, à la lettre', () => {
	globalThis.CHARGE_MAGIE = null;
	globalThis._chargeMagie = null;
	assert.strictEqual(coutPmCharge({ cout_pm: 12 }), 12);
	assert.strictEqual(_coutPmCharge({ cout_pm: 12 }), 12);
});

t('pénalité nulle ⇒ coût de base', () => {
	bloc(0);
	assert.strictEqual(coutPmCharge({ cout_pm: 12 }), 12);
});

t('coût de base nul ⇒ reste nul (compétence martiale)', () => {
	bloc(2.0);
	assert.strictEqual(coutPmCharge({ cout_pm: 0 }), 0);
	assert.strictEqual(coutPmCharge({}), 0);
});

console.log('\n── Sensibilité ─────────────────────────────────────────────────────────────');

t('sensibilité 0 ÉCRITE ⇒ insensible, même en surcharge', () => {
	bloc(3.0);
	assert.strictEqual(coutPmCharge({ cout_pm: 10, sensibilite_charge: 0 }), 10);
});

t('sensibilité absente ⇒ défaut publié par le serveur, jamais une valeur en dur', () => {
	bloc(1.0, 1, 0.5);   // 10 × (1 + 1×0,5) = 15
	assert.strictEqual(coutPmCharge({ cout_pm: 10 }), 15);
	bloc(1.0, 1, 1.0);   // 10 × (1 + 1×1) = 20
	assert.strictEqual(coutPmCharge({ cout_pm: 10 }), 20);
});

t('sensibilité pleine ⇒ pénalité entière', () => {
	bloc(0.6);
	assert.strictEqual(coutPmCharge({ cout_pm: 10, sensibilite_charge: 1 }), 16);
});

console.log('\n── Aide à la canalisation ──────────────────────────────────────────────────');

t('le modificateur réduit la pénalité, jamais le coût sous sa base', () => {
	bloc(0.6, 0.5);
	assert.strictEqual(coutPmCharge({ cout_pm: 10, sensibilite_charge: 1 }), 13);
	bloc(0.6, 0);        // réduction totale (le serveur la borne, le miroir l'accepte)
	assert.strictEqual(coutPmCharge({ cout_pm: 10, sensibilite_charge: 1 }), 10);
});

console.log('\n── Arrondi — les mêmes cas que tests/test_charge_magie.py ──────────────────');

t('au PLUS PROCHE, pas au supérieur', () => {
	bloc(0.02, 1, 1);
	assert.strictEqual(coutPmCharge({ cout_pm: 10 }), 10);   // 10,2 → 10
	bloc(0.06, 1, 1);
	assert.strictEqual(coutPmCharge({ cout_pm: 10 }), 11);   // 10,6 → 11
});

t('les demis montent (floor(x+0.5)), jamais l\'arrondi au pair', () => {
	bloc(0.05, 1, 1);
	assert.strictEqual(coutPmCharge({ cout_pm: 10 }), 11);   // 10,5 → 11, pas 10
	bloc(0.5, 1, 1);
	assert.strictEqual(coutPmCharge({ cout_pm: 3 }), 5);     // 4,5 → 5, pas 4
});

console.log('\n── Les deux miroirs doivent dire la MÊME chose ─────────────────────────────');

t('combat et ville s\'accordent sur toute la grille de cas', () => {
	for (const pen of [0, 0.02, 0.05, 0.1, 0.5, 0.6, 1.0, 3.0]) {
		for (const modif of [0, 0.1, 0.5, 1]) {
			for (const sens of [null, 0, 0.25, 0.5, 1]) {
				bloc(pen, modif, 0.5);
				const capa = { cout_pm: 7, sensibilite_charge: sens };
				assert.strictEqual(coutPmCharge(capa), _coutPmCharge(capa),
					`divergence à pen=${pen} modif=${modif} sens=${sens}`);
			}
		}
	}
});

console.log('\n── Étiquette ───────────────────────────────────────────────────────────────');

t('« 8 PM » à vide, « 8 → 11 PM » sous la charge', () => {
	bloc(0);
	assert.strictEqual(pmTexte({ cout_pm: 8 }), '8 PM');
	bloc(0.6, 1, 1);
	assert.strictEqual(pmTexte({ cout_pm: 8 }), '8 → 13 PM');
});

t('jamais de flèche quand le coût ne bouge pas', () => {
	bloc(0.6, 1, 1);
	assert.strictEqual(pmTexte({ cout_pm: 8, sensibilite_charge: 0 }), '8 PM');
});

console.log(`\n${passes} réussite(s), ${echecs} échec(s).\n`);
process.exit(echecs ? 1 : 0);
