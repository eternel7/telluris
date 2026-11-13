// dev/test_colonisation_client.js
//
// Tests d'EXÉCUTION du panneau de la VOIE DE COLONISATION (templates/scripts/colonisation.js).
//
//   node dev/test_colonisation_client.js     # sort en code 1 au premier échec
//
// POURQUOI : le panneau rend en `innerHTML` des chaînes SAISIES par des joueurs (nom du lieu,
// nom du fondateur, texte d'une demande d'association) et venues du catalogue d'admin. Hors
// de portée de pytest :
//   1. une chaîne non échappée ;
//   2. un visiteur à qui l'on montre un bouton de gestion (§ 10 : il lit et donne) ;
//   3. un associé à qui l'on offre ce qui est réservé au fondateur (§ 12.8).
//
// MÉTHODE : le script est un fichier à part — chargé tel quel par `runInThisContext`, globales
// de la page semées. HORS DE PORTÉE : réseau, ouverture du panneau, rechargement après pose.

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

globalThis.escapeHtml = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
	.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
globalThis._prixTexte = c => `${c} cu`;
globalThis._purseEnCuivre = p => (p || {}).cuivre || 0;
const toasts = [];
globalThis.showToast = t => toasts.push(t);
globalThis.updatePurse = () => {};
globalThis.document = { getElementById: () => ({}), querySelector: () => null };

vm.runInThisContext(fs.readFileSync(path.join(__dirname, '..', 'templates', 'scripts', 'colonisation.js'), 'utf8'),
	{ filename: 'colonisation.js' });

const MECHANT = '<script>alert(1)</script>';
let n = 0;
function test(nom, fn) {
	try { fn(); n++; } catch (e) { console.error('✗ ' + nom + '\n  ' + e.message); process.exit(1); }
}

const SITE_MOTS = { eau: { mots: 'un point d\'eau' }, danger: { mots: MECHANT } };
const SITE_CHIFFRES = { eau: { note: 2, mots: 'de l\'eau', details: ['riviere', MECHANT] } };

function visiteur(extra) {
	return Object.assign({
		role: 'visiteur', label: MECHANT, fondateur_nom: MECHANT, feu: 'grand',
		palier: { id: 'campement', label: 'Campement', menace: 'danger permanent' },
		securite: { mot: 'précaire' }, moral: { mot: 'stable' }, site: SITE_MOTS,
		besoins: [{ stock: 'bois', label: 'Bois' }],
		dons_possibles: [{ index: 0, item_id: 'item:pain', nom: MECHANT, icon: '🍞', stock: 'nourriture', stock_label: 'Nourriture', unites: 2 }],
		peut_demander: true, demande_en_attente: false, places_associes: 1, position: { x: 1, y: 2 }, purse: { cuivre: 0 },
	}, extra || {});
}

function gerant(role, extra) {
	return Object.assign(visiteur(), {
		role, site: SITE_CHIFFRES,
		securite: { mot: 'précaire', valeur: 30, facteurs: [{ id: 'defense_physique', valeur: 4, max: 20 }] },
		moral: { mot: 'stable', valeur: 55, facteurs: [{ id: 'feu', valeur: 5 }, { id: 'morts', valeur: -8 }] },
		stocks: [{ stock: 'bois', label: 'Bois', quantite: 1, capacite: 60, seuil: 18 }],
		population: 3, nommes: 1, logements: 7, souffrants: 0,
		batiments: [
			{ id: 'b_1', type: 'habitation', label: 'Habitation', icone: '🏠', pos: [3, 3], endommage: true, postes: [] },
			{ id: 'b_2', type: 'entrepot', label: 'Entrepôt', icone: '📦', pos: null, endommage: false,
				postes: [{ metier: 'intendant', label: 'Intendant', places: 1, tenus: [{ id: 'employe:x', nom: MECHANT }] }] }],
		catalogue: [{ id: 'ferme', label: 'Ferme', icone: '🌾', description: '', prix: 100, bois: 20, materiaux: 5, refus: 'Ce bâtiment s\'ouvre au palier Hameau.' }],
		fortifications: [{ id: 'palissade', label: 'Palissade', prix: 20000, bois: 40, materiaux: 5, defense: 4, en_place: false, requis_pour: 'Hameau', refus: '' }],
		chantier: null,
		palier_suivant: { palier: { id: 'hameau', label: 'Hameau' }, prix: 160000, pret: false,
			conditions: [{ label: 'Population', valeur: 3, cible: 5, ok: false }, { label: 'Palissade', valeur: null, cible: null, ok: true }] },
		menace: { etape: 2, mot: 'la bête a remarqué le lieu' },
		associes: [{ id: 'character:b', nom: MECHANT, apports: { bois: 4 } }],
		journal: [{ at: 1, texte: MECHANT }], demandes: [{ id: 'character:c', nom: 'Cy', texte: MECHANT }], soutiens: [],
	}, extra || {});
}

const tout = (d) => ['site', 'population', 'batiments', 'defense'].map(o => colImplantationHtml(d, o)).join('');

test('aucune chaîne saisie ne sort sans échappement', () => {
	for (const html of [tout(visiteur()), tout(gerant('fondateur')), tout(gerant('associe')),
		colFonderHtml({ site: SITE_CHIFFRES, charte: { cite: 'c', label: MECHANT }, cites: [{ id: 'c', label: MECHANT }], peut_fonder: false, refus: MECHANT,
			palier: { label: 'Campement' }, modeles: [], mes_implantations: [{ label: MECHANT, palier: MECHANT }], purse: {} }),
		colModelesHtml([{ id: MECHANT, label: MECHANT, image: 'a b.png', route: 'maps', partages: [MECHANT] }]),
		colEmbaucheHtml({ candidats: [{ id: MECHANT, prenom: MECHANT, nom: MECHANT, metier_label: MECHANT, poste_nom: MECHANT, cout: 1 }],
			employes: [{ id: MECHANT, nom: MECHANT, metier_label: MECHANT }], purse: {} })]) {
		assert.ok(!html.includes('<script>'), 'balise script non échappée');
	}
});

test('le visiteur lit le site en mots, les besoins, peut donner et demander — rien d\'autre', () => {
	const html = tout(visiteur());
	assert.ok(html.includes('un point d&#39;eau') && html.includes('Tableau des besoins') && html.includes('colDonner(this)'));
	assert.ok(html.includes('colDemander()'));
	assert.ok(!html.includes('/3)'), 'la note chiffrée du site reste au fondateur');
	for (const interdit of ['colConstruire', 'colPoser', 'colChantier', 'colFeu', 'colOuvrirEmbauche', 'colExclure',
		'colRepondre', 'colFinancer', 'colReparer', 'col-onglets', 'Carnet'])
		assert.ok(!html.includes(interdit), 'le visiteur voit ' + interdit);
});

test('une demande en attente remplace le champ de demande', () => {
	const html = tout(visiteur({ demande_en_attente: true, peut_demander: false }));
	assert.ok(html.includes('attend la réponse') && !html.includes('colDemander()'));
});

test('le fondateur a tous les onglets, les chiffres et toutes les décisions', () => {
	const d = gerant('fondateur');
	assert.strictEqual((colImplantationHtml(d, 'site').match(/data-onglet=/g) || []).length, COL_ONGLETS.length);
	const html = tout(d);
	for (const attendu of ['colConstruire', 'colPoser', 'colChantier', 'colFeu', 'colOuvrirEmbauche', 'colExclure',
		'colRepondre', 'colReparer', 'Carnet', '(2/3)', 'Défense physique : 4/20', 'Morts récentes : -8', 'Feu : +5'])
		assert.ok(html.includes(attendu), 'le fondateur ne voit pas ' + attendu);
	assert.ok(colOngletBatimentsHtml(d).includes('Déplacer ici') && colOngletBatimentsHtml(d).includes('Poser ici'));
	assert.ok(colOngletBatimentsHtml(d).includes('⚠️ à poser'));
});

test('l\'associé pose et finance, sans rien décider', () => {
	const d = gerant('associe', { chantier: { genre: 'fortification', label: 'Palissade', cout: 100, verse: 40, reste: 60 } });
	const html = tout(d);
	assert.ok(html.includes('colPoser') && html.includes('colFinancer') && html.includes('colQuitter()'));
	for (const interdit of ['colConstruire', 'colChantier(', 'colFeu', 'colOuvrirEmbauche', 'colExclure', 'colRepondre', 'colReparer', 'Carnet'])
		assert.ok(!html.includes(interdit), 'l\'associé voit ' + interdit);
});

test('un chantier ouvert ferme les autres ; un statut payé repropose les modèles au fondateur', () => {
	const ouvert = gerant('fondateur', { chantier: { genre: 'fortification', label: 'Palissade', cout: 100, verse: 0, reste: 100 } });
	assert.ok(/data-objet="palissade" disabled/.test(colOngletDefenseHtml(ouvert)));
	assert.ok(!colOngletPopulationHtml(ouvert).includes('data-genre="statut"'));
	const paye = gerant('fondateur', { chantier: { genre: 'statut', label: 'Statut de Hameau', cout: 100, verse: 100, reste: 0 },
		modeles: [{ id: 'lieu:m1', label: 'Hameau', image: 'h.png', route: 'maps', partages: [], generique: true },
			{ id: 'lieu:m2', label: 'Hameau des bois', image: 'b.png', route: 'towns', partages: ['foret'], generique: false }] });
	const html = colOngletPopulationHtml(paye);
	assert.ok(html.includes('colPalier()') && !html.includes('colFinancer'));
	assert.strictEqual((html.match(/checked/g) || []).length, 1, 'le premier modèle seul est présélectionné');
	assert.ok(html.indexOf('lieu:m1') < html.indexOf('lieu:m2') && html.includes('src="/towns/b.png"'));
	assert.ok(!colOngletPopulationHtml(gerant('associe', { chantier: paye.chantier, modeles: paye.modeles })).includes('colPalier()'));
});

test('fonder : le refus se dit, le bouton attend un modèle', () => {
	const base = { site: SITE_CHIFFRES, charte: { cite: 'c', label: 'Auxerre' }, cites: [{ id: 'c', label: 'Auxerre' }, { id: 'd', label: 'Sens' }],
		palier: { label: 'Campement' }, mes_implantations: [],
		modeles: [{ id: 'lieu:m1', label: 'Campement', image: 'c.jpg', route: 'battle_maps', partages: [], generique: true }] };
	const refuse = colFonderHtml(Object.assign({}, base, { peut_fonder: false, refus: 'Trop près d\'une Cité-État', purse: { cuivre: 99999 } }));
	assert.ok(refuse.includes('Trop près') && !refuse.includes('colFonder()') && refuse.includes('Auxerre ou Sens'));
	const riche = colFonderHtml(Object.assign({}, base, { peut_fonder: true, purse: { cuivre: 40000 } }));
	assert.ok(riche.includes('colFonder()') && !/<button class="sh-drop-btn" disabled/.test(riche) && riche.includes('id="col-nom"'));
});

test('charte : prix, règles, bouton fermé sans les fonds ou avec une charte en main', () => {
	const base = { cite: MECHANT, maitre: MECHANT, prix: 40000, peut_acheter: true, refus: '', charte: null,
		reglages: { rang_min: 'C', distance_cite_min: 6, distance_implantation_min: 4, implantations_par_pays: 1 } };
	const ok = colCharteHtml(Object.assign({}, base, { purse: { cuivre: 40000 } }));
	assert.ok(!ok.includes('<script>') && ok.includes('colAcheterCharte()') && !/disabled/.test(ok) && ok.includes('Rang C'));
	assert.ok(/disabled/.test(colCharteHtml(Object.assign({}, base, { purse: { cuivre: 1 } }))));
	const tenue = colCharteHtml(Object.assign({}, base, { peut_acheter: false, refus: 'déjà', charte: { label: 'Sens' }, purse: { cuivre: 99999 } }));
	assert.ok(/disabled/.test(tenue) && tenue.includes('signée à Sens'));
});

test('guilde : le visiteur la rejoint, le maître ouvre l\'échelon, seuls les retours se reçoivent', () => {
	const g = { existe: true, nom: MECHANT, echelon: 'Auberge', fonctions: ['recrutement', 'expeditions', 'coffre'], titre: null,
		membres: [{ nom: MECHANT, titre: 'maitre' }], missions: [], compagnons: [], expeditions: [], coffre: null, suivant: null };
	const vis = colGuildeHtml(g, 'visiteur', {});
	assert.ok(!vis.includes('<script>') && vis.includes("colGuilde('rejoindre')") && !vis.includes('colOuvrirGuilde'));
	const maitre = colGuildeHtml(Object.assign({}, g, { titre: 'maitre', suivant: { label: 'Maison', prix: 1, refus: '' },
		missions: [{ id: 'patrouille', label: MECHANT, duree_s: 3600, difficulte: 5, recompense: 10 }],
		compagnons: [{ id: 'aventurier:1', nom: MECHANT, niveau: 2 }],
		expeditions: [{ id: 'x1', mission: MECHANT, par: MECHANT, retour: 1, revenue: true, chance: 0.5, mienne: true },
			{ id: 'x2', mission: 'm', par: 'p', retour: 1, revenue: false, chance: 0.5, mienne: true }],
		coffre: [{ index: 0, nom: MECHANT, icon: '' }], peut_retirer: true, sac: [{ index: 0, item_id: 'item:a', nom: MECHANT, icon: '' }] }), 'fondateur', {});
	assert.ok(!maitre.includes('<script>') && maitre.includes('colOuvrirGuilde()') && !maitre.includes("colGuilde('quitter')"));
	assert.strictEqual((maitre.match(/colAccueillir/g) || []).length, 1, 'seul le groupe revenu se reçoit');
	assert.ok(maitre.includes('colEnvoyer(this)') && maitre.includes('colCoffreRetirer') && maitre.includes('colCoffreDeposer'));
	const avant = colGuildeHtml({ existe: false, suivant: { label: 'Auberge', prix: 1, palier: 'Village', refus: 'palier' } }, 'associe', {});
	assert.ok(avant.includes('Fonder la guilde') && !avant.includes('colOuvrirGuilde'));
});

console.log(`OK — ${n} tests du panneau de colonisation.`);
