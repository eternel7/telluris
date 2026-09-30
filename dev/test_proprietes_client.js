// dev/test_proprietes_client.js
//
// Tests d'EXÉCUTION du JavaScript du panneau 🏠 PROPRIÉTÉS (templates/play_town_telluris.html).
//
//   node dev/test_proprietes_client.js     # sort en code 1 au premier échec
//
// POURQUOI : le panneau rend en `innerHTML` des chaînes venues de trois sources — le catalogue
// d'admin (`rules:proprietes`), des noms TIRÉS (personnel) et des noms SAISIS (propriétaire,
// compagnons). Classes de bug hors de portée de pytest :
//
//   1. Une chaîne non échappée (`<script>` dans un nom de compagnon ou de propriétaire).
//   2. Les sections confondues : le cahier des charges exige de distinguer type, capacités,
//      aménagements installés / disponibles, PNJ présents et activités.
//   3. Un visiteur à qui l'on montre les boutons de gestion (vendre, installer, engager).
//
// MÉTHODE : identique à dev/test_guilde_client.js — extraction par nom, `runInThisContext`,
// `document` réduit à un `getElementById` qui capture l'`innerHTML` écrit.
//
// HORS DE PORTÉE (CLAUDE.md §15, à vérifier en jeu) : les appels réseau, l'ouverture du
// panneau et Échap.

const path = require('path');
const assert = require('assert');
const vm = require('vm');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'play_town_telluris.html');
const { lireAvecIncludes, scriptsInline } = require('./_template_js');
const js = scriptsInline(lireAvecIncludes(TEMPLATE));
assert.ok(js, 'aucun bloc <script> trouvé dans ' + TEMPLATE);

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

function extraireConst(nom) {
	const m = new RegExp('^\\s*const ' + nom + ' = .*$', 'm').exec(js);
	assert.ok(m, 'constante ' + nom + ' introuvable dans le template');
	return m[0];
}

// Globales semées : le DOM se réduit à des nœuds factices PAR ID (le panneau 🏠 n'écrit que
// dans `prop-contenu` ; le coffre écrit dans ses deux colonnes, son sélecteur et ses charges).
function noeud() {
	return { innerHTML: '', textContent: '', value: '',
		classList: { toggle() {} }, parentElement: { classList: { toggle() {} } } };
}
const noeuds = {};
const el = id => (noeuds[id] = noeuds[id] || noeud());
const cible = el('prop-contenu');
globalThis.document = { getElementById: el };
globalThis._inventaire = [];
globalThis._pcfSel = 'coffre';

vm.runInThisContext(extraireConst('_PROP_STATUTS'));
vm.runInThisContext(extraireConst('_PROP_CATEGORIES'));
vm.runInThisContext(extraireConst('INV_VISIBLE'));
for (const f of ['escapeHtml', '_propCategorie', '_purseEnCuivre', '_prixTexte', '_propCaps', '_propDate',
	'_propMesProprietes', '_propMajoration', 'renderProprietesOffre', 'renderPropriete',
	'_sortedOrder', '_grpCharge', '_grpRemplirSac', '_pcfLigne', 'renderCoffre']) {
	vm.runInThisContext(extraire(f));
}

let passes = 0, echecs = 0;
function t(nom, fn) {
	try { fn(); console.log('  OK   ' + nom); passes++; }
	catch (e) { console.error('  ÉCHEC ' + nom + '\n         ' + e.message); echecs++; }
}

const XSS = '<img src=x onerror=alert(1)>';

function ici(role, extra) {
	return Object.assign({
		role,
		propriete: { id: 'propriete:maison_1', label: 'Maison de ' + XSS, mode: 'achat',
			statut: 'possedee', expire_at: null, proprietaire_nom: XSS, residence: role === 'proprietaire' },
		type: { id: 'maison', label: 'Maison', rang: 3, description: 'Un foyer.' },
		capacites: { occupants_max: 5, personnel_max: 4, stockage_kg: 150, postes: {},
			occupants: 1, personnel: 1, stockage_utilise: 3 },
		installes: [{ id: 'petit_laboratoire', nom: "Petit laboratoire d'alchimie", categorie: 'activite', cout: 6000 }],
		disponibles: [{ id: 'cave', nom: 'Cave', categorie: 'vie', cout: 2500 }],
		heberges: [{ id: 'aventurier:x', nom: XSS, image: '' }],
		hebergeables: [],
		employes: [{ id: 'employe:alchimiste_1', nom: 'Jehan Ferrant', metier: 'alchimiste',
			metier_label: 'Alchimiste', poste_nom: "Petit laboratoire d'alchimie" }],
		embauches: [{ metier: 'gardien', metier_label: 'Gardien', amenagement: 'loge_gardien',
			amenagement_nom: 'Loge du gardien', cout: 600, libres: 1 }],
		activites: [{ amenagement: 'petit_laboratoire', nom: "Petit laboratoire d'alchimie",
			label: 'Alchimie', metier: 'alchimiste', exercee: true, employe: 'Jehan Ferrant' }],
		gardien: false,
		coffre: [{ item: 'item:a', nom: 'Pomme', poids: 1, idx: 0 }],
		coffre_visible: true,
		revente: { autorisee: role === 'proprietaire', raison: '', prix: 48000 },
		mes_proprietes: [],
		purse: { or: 10, argent: 0, cuivre: 0 },
	}, extra || {});
}

t('les sections exigées sont distinctes', () => {
	renderPropriete(ici('proprietaire'));
	const h = cible.innerHTML;
	for (const titre of ['Type : Maison', 'Capacités', 'Aménagements installés',
		'Aménagements disponibles', 'Occupants et PNJ', 'Activités']) {
		assert.ok(h.includes(titre), 'section absente : ' + titre);
	}
	assert.ok(h.includes('exercée par Jehan Ferrant'));
});

t('toute chaîne saisie est échappée', () => {
	renderPropriete(ici('proprietaire'));
	assert.ok(!cible.innerHTML.includes(XSS), 'nom injecté tel quel');
	assert.ok(cible.innerHTML.includes('&lt;img src=x'));
});

t('le visiteur ne voit aucun geste de gestion', () => {
	renderPropriete(ici('visiteur', { disponibles: [], embauches: [] }));
	const h = cible.innerHTML;
	for (const geste of ['propCeder', 'propInstaller', 'propEngager', 'propRenvoyer', 'propGeste',
		'Aménagements disponibles']) {
		assert.ok(!h.includes(geste), 'geste offert au visiteur : ' + geste);
	}
});

t('activité inactive sans PNJ', () => {
	renderPropriete(ici('proprietaire', { activites: [{ amenagement: 'x', nom: 'Labo',
		label: 'Alchimie', metier: 'alchimiste', exercee: false, employe: '' }] }));
	assert.ok(cible.innerHTML.includes('inactive'));
});

t('offre : types de la zone et chambre à louer', () => {
	renderProprietesOffre({
		types: [{ id: 'maison', label: 'Maison', description: '', prix: 80000,
			capacites: { occupants_max: 5, personnel_max: 4, stockage_kg: 150 }, amenagements: ['Cave'] }],
		location: { type: { description: '' }, prix: 150, duree_s: 7 * 86400, chambre: null },
		mes_proprietes: [{ id: 'p', label: XSS, type: 'Chambre', mode: 'location', statut: 'louee',
			expire_at: 0, residence: false }],
		purse: { or: 1, argent: 0, cuivre: 0 },
	});
	const h = cible.innerHTML;
	assert.ok(h.includes('data-type="maison"'));
	assert.ok(/data-type="maison" disabled/.test(h), 'achat hors budget non grisé');
	assert.ok(h.includes('Louer') && h.includes('Mes propriétés'));
	assert.ok(!h.includes(XSS));
});

t('offre : majoration expliquée seulement au-dessus de la base', () => {
	const offre = t => renderProprietesOffre({ types: [Object.assign({ id: 'maison', label: 'Maison',
		description: '', capacites: {}, amenagements: [] }, t)], location: null, mes_proprietes: [],
		purse: { or: 0, argent: 0, cuivre: 0 } });
	offre({ prix: 1000, prix_base: 1000, majoration: { voisinage_pct: 0, occupation_facteur: 1, proprietes_case: 0 } });
	assert.ok(!cible.innerHTML.includes('Base '), 'ligne de majoration au prix de base');
	offre({ prix: 2600, prix_base: 1000, majoration: { voisinage_pct: 30, occupation_facteur: 2, proprietes_case: 1 } });
	const h = cible.innerHTML;
	assert.ok(h.includes('quartier marchand +30 %') && h.includes('1 bien déjà ici ×2'), h);
});

// ── Coffre (présenté comme l'inventaire du groupe) ─────────────────────────────────
function coffre(role, extra) {
	return Object.assign({
		role, gardien: false,
		principal: { charge: 1, charge_max: 50, inventaire: [{ _id: 'item:a', item: 'item:a', nom: 'Pomme', poids: 1 }] },
		coffre: { visible: true, depot: role === 'proprietaire', charge: 2, charge_max: 20,
			inventaire: [{ _id: 'item:b', item: 'item:b', nom: XSS, poids: 2, idx: 0 }] },
		ateliers: [{ id: 'employe:x', nom: 'Jehan', metier_label: 'Alchimiste', grande: true,
			produits: [{ item_id: 'item:elixir', nom: 'Élixir', qty: 2 }],
			matieres: [{ cle: 'herbe', qty: 3 }], caisse: 40 }],
	}, extra || {});
}

t('coffre : sac à gauche, coffre à droite, noms échappés', () => {
	globalThis._pcfSel = 'coffre';
	renderCoffre(coffre('proprietaire'));
	assert.ok(noeuds['pcf-principal'].innerHTML.includes('coffreDeposer'));
	const d = noeuds['pcf-droite'].innerHTML;
	assert.ok(d.includes('coffrePrendre') && d.includes('Prendre'));
	assert.ok(!d.includes(XSS) && d.includes('&lt;img'));
	assert.ok(noeuds['pcf-select'].innerHTML.includes('employe:x'));
});

t('coffre : le visiteur dérobe mais ne dépose pas', () => {
	globalThis._pcfSel = 'coffre';
	renderCoffre(coffre('visiteur'));
	assert.ok(noeuds['pcf-droite'].innerHTML.includes('Dérober'));
	assert.ok(/coffreDeposer/.test(noeuds['pcf-principal'].innerHTML));
	assert.ok(/disabled[\s\S]*coffreDeposer/.test(noeuds['pcf-principal'].innerHTML), 'dépôt non grisé');
});

t('atelier : rayon repris, matières confiées, sur-mesure annoncé', () => {
	globalThis._pcfSel = 'employe:x';
	renderCoffre(coffre('proprietaire'));
	const d = noeuds['pcf-droite'].innerHTML;
	assert.ok(d.includes('atelierReprendre') && d.includes('Élixir') && d.includes('herbe'));
	assert.ok(d.includes('Grande maison'));
	assert.ok(noeuds['pcf-principal'].innerHTML.includes('atelierDonner'));
});

t('atelier : un visiteur ne confie rien', () => {
	globalThis._pcfSel = 'employe:x';
	renderCoffre(coffre('visiteur'));
	assert.ok(/disabled[\s\S]*atelierDonner/.test(noeuds['pcf-principal'].innerHTML), 'don non grisé');
});

// ── Panneau Achat-Vente d'un marchand employé : sections masquées au maître ──────────
// Nœuds propres (DOM factice isolé) : chaque en-tête `acc-head-<s>` a une `.acc-section`
// parente dont on lit `style.display` et la classe `open`.
function sectionsMarchand() {
	const dom = {};
	for (const s of ['vente', 'achat', 'commande', 'mes-commandes']) {
		const section = { style: { display: '' }, ouverte: false };
		section.classList = { toggle(_c, on) { section.ouverte = !!on; } };
		dom['acc-head-' + s] = { closest: () => section, parentElement: section };
	}
	return dom;
}
vm.runInThisContext(extraireConst('SELL_SECTIONS'));
for (const f of ['_sellSectionsVisibles', '_sellSectionsPresentes', '_sellRestaurerSection',
	'_accAppliquer', '_accRestaurer']) {
	vm.runInThisContext(extraire(f));
}

function avecSections(memo, fn) {
	const dom = sectionsMarchand();
	const docAvant = globalThis.document;
	globalThis.document = { getElementById: id => dom[id] || null };
	globalThis._accLsGet = () => memo;
	globalThis._sellOmbres = () => {};
	globalThis.SELL_SECTION_KEY = 'k';
	try { fn(dom); } finally { globalThis.document = docAvant; }
}
const ouverte = dom => Object.keys(dom).filter(k => dom[k].parentElement.ouverte).map(k => k.slice(9));

t('marchand employé : le maître ne voit ni Vente ni Achat, les commandes s\'ouvrent', () => {
	avecSections('vente', dom => {
		_sellSectionsVisibles({ vente: false, achat: false, commande: true });
		assert.deepStrictEqual(_sellSectionsPresentes(), ['commande', 'mes-commandes']);
		_sellRestaurerSection();
		assert.deepStrictEqual(ouverte(dom), ['commande'], 'section mémorisée masquée rouverte');
	});
});

t('marchand employé : un visiteur garde Vente et Achat, et sa section mémorisée', () => {
	avecSections('achat', dom => {
		_sellSectionsVisibles({ vente: true, achat: true, commande: false });
		assert.deepStrictEqual(_sellSectionsPresentes(), ['vente', 'achat']);
		_sellRestaurerSection();
		assert.deepStrictEqual(ouverte(dom), ['achat']);
	});
});

t('marchand employé : rien d\'offert ⇒ aucune section présente', () => {
	avecSections(null, () => {
		_sellSectionsVisibles({ vente: false, achat: false, commande: false });
		assert.deepStrictEqual(_sellSectionsPresentes(), []);
	});
});

console.log(`\n${passes} OK, ${echecs} échec(s)`);
process.exit(echecs ? 1 : 0);
