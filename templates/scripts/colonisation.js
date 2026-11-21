// templates/scripts/colonisation.js
//
// Panneau de la VOIE DE COLONISATION de /play : fonder (carte d'un pays) et gérer / lire une
// implantation (onglets Site, Population, Bâtiments, Défense).
// Décisions : docs/lore/systemes/20261112_voie_de_colonisation.md § 10 et § 12.7.
//
// Le client ne reconstruit AUCUN état : chaque réponse de /api/colonisation/* porte le bloc
// recalculé (Convention §10), `colRendre` le redessine. Toute chaîne venue du serveur passe
// par `escapeHtml` (Convention §9) ; les identifiants voyagent en `data-*`, jamais dans un
// `onclick="…('${x}')"`.
//
// Globales attendues de la page : escapeHtml, showToast, _aubFetch, _prixTexte,
// _purseEnCuivre, updatePurse, _majLiens, _applyInventoryPayload.
// Harnais : dev/test_colonisation_client.js (fonctions `col*Html`, pures).

let _colData = null;      // dernier bloc reçu (implantation)
let _colOnglet = 'site';
let _colVue = null;       // 'site' (fonder) | 'ici' | 'embauche'
let _colDonsFiltre = '';  // stock choisi aux pastilles des dons ('' = tous)
let _colCarnetFiltre = '';// genre choisi aux pastilles du carnet ('' = tout)

const COL_AXES = { eau: '💧 Eau', nourriture: '🌾 Nourriture', materiaux: '🪵 Matériaux',
	commerce: '⚖️ Commerce', defense: '⛰️ Défense', danger: '🐺 Danger' };
const COL_FACTEURS = {
	defense_physique: 'Défense physique', defense_humaine: 'Défense humaine', environnement: 'Environnement',
	logistique: 'Logistique', connaissance_territoire: 'Connaissance du territoire',
	nourriture: 'Nourriture', logement: 'Logement', soignant: 'Soignant présent', attaques: 'Attaques récentes',
	morts: 'Morts récentes', prosperite: 'Prospérité', expeditions: 'Expéditions réussies',
	reputation: 'Réputation du fondateur', feu: 'Feu', securite: 'Sécurité' };
const COL_ROLES = { fondateur: 'Fondateur', associe: 'Associé', soutien: 'Soutien', visiteur: 'Visiteur' };
// Genres des lignes du carnet (`colonisation.GENRES_JOURNAL`) ; sans genre ⇒ « divers ».
const COL_GENRES = { association: '🤝 Association', population: '👥 Population', batiment: '🏘️ Bâtiments',
	chantier: '🏗️ Chantiers', personnel: '🧑‍🔧 Personnel', don: '🎁 Dons', feu: '🔥 Feu', evenement: '📜 Vie du lieu',
	caisse: '💰 Caisse', guilde: '🏰 Guilde', attaque: '⚔️ Attaques', entrepot: '📦 Entrepôt', divers: '· Divers' };
const COL_APPORTS = { nourriture: 'nourriture', bois: 'bois', materiaux: 'matériaux', medicaments: 'médicaments', cuivre: 'cu' };

function _colE(s) { return escapeHtml(String(s === null || s === undefined ? '' : s)); }

function _colAfficher() {
	document.getElementById('game-container').classList.add('panel-hidden');
	document.getElementById('colonie-panel').classList.remove('panel-hidden');
	window.scrollTo({ top: 0, behavior: 'instant' });
}

function closeColonie() {
	document.getElementById('game-container').classList.remove('panel-hidden');
	document.getElementById('colonie-panel').classList.add('panel-hidden');
	window.scrollTo({ top: 0, behavior: 'smooth' });
}

function _colEcrire(titre, html) {
	document.getElementById('colonie-titre').textContent = titre;
	document.getElementById('colonie-contenu').innerHTML = html;
}

// ── Fiche de site (pure) ────────────────────────────────────────────────────────────
// `chiffres` : le fondateur et l'associé voient la note et le détail ; le visiteur, les mots.
function colSiteHtml(site, chiffres) {
	const lignes = Object.keys(COL_AXES).filter(a => site && site[a]).map(a => {
		const b = site[a];
		const detail = chiffres && (b.details || []).length ? ` — ${b.details.map(_colE).join(', ')}` : '';
		const note = chiffres && b.note !== undefined ? ` <span class="q-desc">(${_colE(b.note)}/${_colE(b.max ?? 3)})</span>` : '';
		return `<div class="prop-ligne"><div class="prop-txt"><strong>${COL_AXES[a]}${note}</strong>
			<span class="q-desc">${_colE(b.mots)}${detail}</span></div></div>`;
	}).join('');
	return `<section class="prop-section"><h3>🧭 Fiche de site</h3><div class="prop-liste">${lignes}</div></section>`;
}

// Vignettes de choix d'un modèle (pure) : la première est présélectionnée.
function colModelesHtml(modeles) {
	if (!(modeles || []).length) return '<div class="sell-empty">Aucun lieu modèle n\'est disponible pour ce palier.</div>';
	return `<div class="col-modeles">` + modeles.map((m, i) => `<label class="col-modele">
		<input type="radio" name="col-modele" value="${_colE(m.id)}" ${i === 0 ? 'checked' : ''}>
		<img src="/${_colE(m.route)}/${encodeURIComponent(m.image)}" alt="" loading="lazy">
		<strong>${_colE(m.label)}</strong>
		<span class="q-desc">${m.generique ? 'modèle générique' : (m.partages || []).map(_colE).join(', ') || 'aucun tag partagé'}</span>
	</label>`).join('') + `</div>`;
}

function _colModeleChoisi() {
	const r = document.querySelector('input[name="col-modele"]:checked');
	return r ? r.value : null;
}

// ── Fonder ──────────────────────────────────────────────────────────────────────────
function colFonderHtml(d) {
	const cites = (d.cites || []).map(c => _colE(c.label)).join(' ou ');
	let html = colSiteHtml(d.site, true);
	html += `<section class="prop-section"><h3>📜 Charte</h3><div class="prop-ligne"><div class="prop-txt">
		<span class="q-desc">${d.charte ? `Charte signée à ${_colE(d.charte.label)}.` : 'Aucune charte en main.'}
			Ici, elle doit l'être par le maître de guilde${cites ? ' de ' + cites : ''}.</span>
		${d.peut_fonder ? '' : `<span class="q-desc">⚠️ ${_colE(d.refus)}</span>`}
	</div></div></section>`;
	if (d.peut_fonder) {
		html += `<section class="prop-section"><h3>🏕️ ${_colE(d.palier.label)} — choisir le lieu</h3>
			${colModelesHtml(d.modeles)}
			<div class="prop-ligne"><div class="prop-txt">
				<input type="text" id="col-nom" maxlength="40" placeholder="Nom du lieu (facultatif)">
			</div>
			<button class="sh-drop-btn" ${!(d.modeles || []).length ? 'disabled' : ''} onclick="colFonder()">Fonder ici</button></div>
		</section>`;
	}
	const miennes = (d.mes_implantations || []).map(i => `<div class="prop-ligne"><div class="prop-txt">
		<strong>${_colE(i.label)}</strong><span class="q-desc">${_colE(i.palier)}</span></div></div>`).join('');
	html += `<section class="prop-section"><h3>🗺️ Mes implantations</h3><div class="prop-liste">
		${miennes || '<div class="sell-empty">Vous n\'avez fondé aucun lieu.</div>'}</div></section>`;
	return html;
}

// ── La charte, au bureau d'un maître de guilde ──────────────────────────────────────
function colCharteHtml(d) {
	const r = d.reglages || {};
	const tenue = d.charte ? `<span class="q-desc">📜 Vous tenez une charte signée à ${_colE(d.charte.label)}.</span>` : '';
	return `<section class="prop-section"><h3>📜 Charte de colonisation — ${_colE(d.cite)}</h3><div class="prop-ligne"><div class="prop-txt">
		<span class="q-desc">${d.maitre ? _colE(d.maitre) + ' signe' : 'Le maître de guilde signe'} la charte qui autorise à fonder une implantation en pleine contrée,
			sur une case dont ${_colE(d.cite)} est la cité la plus proche.</span>
		<span class="q-desc">Rang ${_colE(r.rang_min)} au moins · une case libre, hors de tout point de connexion ·${(+r.distance_cite_min || 0) > 1 ? ` ${_colE(r.distance_cite_min)} cases de toute Cité-État ·` : ''}
			${_colE(r.distance_implantation_min)} cases d'une autre implantation · ${_colE(r.implantations_par_pays)} par pays.</span>
		${tenue}${!d.peut_acheter && d.refus && !d.charte ? `<span class="q-desc">⚠️ ${_colE(d.refus)}</span>` : ''}
		<span class="sell-prix">💰 ${_prixTexte(d.prix)}</span></div>
		<button class="sh-drop-btn" ${!d.peut_acheter || d.prix > _purseEnCuivre(d.purse) ? 'disabled' : ''} onclick="colAcheterCharte()">Acheter la charte</button>
	</div></section>`;
}

async function openColonieCharte() {
	const d = await _aubFetch('api/colonisation/charte');
	if (!d) return;
	updatePurse(d.purse);
	_colEcrire('📜 Charte de colonisation', colCharteHtml(d));
	_colAfficher();
}

async function colAcheterCharte() {
	const d = await _aubFetch('api/colonisation/charte/acheter', {});
	if (!d) return;
	updatePurse(d.purse);
	if (d.achetee) showToast(`Charte signée à ${d.cite}.`, { major: true });
	_colEcrire('📜 Charte de colonisation', colCharteHtml(d));
}

async function openColonieSite() {
	const d = await _aubFetch('api/colonisation/site');
	if (!d) return;
	_colVue = 'site';
	updatePurse(d.purse);
	if (typeof _majColonieOffre === 'function') _majColonieOffre(!!d.peut_fonder);
	_colEcrire('🏕️ Fonder une implantation', colFonderHtml(d));
	_colAfficher();
}

async function colFonder() {
	// Le nom est LU dans son champ (Convention §9 : jamais interpolé dans un onclick).
	const nom = (document.getElementById('col-nom') || {}).value || '';
	const d = await _aubFetch('api/colonisation/fonder', { modele: _colModeleChoisi(), nom });
	if (!d) return;
	updatePurse(d.purse);
	_majLiens(d);
	// La case fondée devient un point de connexion : le bouton s'efface.
	if (typeof _majColonieOffre === 'function') _majColonieOffre(!!d.peut_fonder);
	if (d.fondee) showToast(`${d.fondee.label} est fondé.`, { major: true });
	_colEcrire('🏕️ Fonder une implantation', colFonderHtml(d));
}

// ── L'implantation ──────────────────────────────────────────────────────────────────
function _colGere(d) { return d.role === 'fondateur' || d.role === 'associe'; }

function colEnteteHtml(d) {
	return `<section class="prop-section"><div class="prop-caps">
		<span>🏷️ ${_colE(d.palier.label)}</span>
		<span>👤 Fondé par ${_colE(d.fondateur_nom)}</span>
		<span>🛡️ Sécurité : ${_colE(d.securite.mot)}</span>
		<span>🙂 Moral : ${_colE(d.moral.mot)}</span>
		<span>🔥 ${d.feu === 'grand' ? 'Grand feu' : 'Feu réduit'}</span>
		<span>🎭 ${COL_ROLES[d.role] || ''}</span>
		${_colGere(d) ? `<button class="sh-drop-btn" onclick="openColonieRangements()" title="Entrepôt commun${d.role === 'associe' ? ' et votre petit coffre' : ''}">📦 Rangements</button>` : ''}
	</div></section>`;
}

function colBesoinsHtml(d) {
	const b = (d.besoins || []).map(x => `<span>⚠️ ${_colE(x.label)}</span>`).join('');
	return `<section class="prop-section"><h3>📋 Tableau des besoins</h3>
		${b ? `<div class="prop-caps">${b}</div>` : '<div class="sell-empty">Le lieu ne manque de rien.</div>'}</section>`;
}

// Dons : un objet identique d'un même sac = une ligne « × N » (Donner 1 / Tout donner) ;
// pastilles par stock, celles d'un stock sous le seuil bas mises en avant.
function colDonsHtml(d) {
	const groupes = [];
	const parCle = {};
	(d.dons_possibles || []).forEach(o => {
		const cle = `${o.sac || ''}|${o.item_id}`;
		if (!parCle[cle]) { parCle[cle] = Object.assign({}, o, { n: 0, total: 0 }); groupes.push(parCle[cle]); }
		parCle[cle].n += 1;
		parCle[cle].total = Math.round((parCle[cle].total + (+o.unites || 0)) * 10) / 10;
	});
	const bas = new Set((d.besoins || []).map(b => b.stock));
	const presents = (d.stocks_ouverts || []).filter(st => groupes.some(g => g.stock === st.stock));
	if (_colDonsFiltre && !presents.some(st => st.stock === _colDonsFiltre)) _colDonsFiltre = '';
	const filtres = presents.length > 1 ? `<div class="col-filtres" role="group" aria-label="Filtrer par réserve">`
		+ `<button type="button" class="col-filtre" data-stock="" aria-pressed="${!_colDonsFiltre}" onclick="colDonsFiltre(this)">Tout</button>`
		+ presents.map(st => `<button type="button" class="col-filtre${bas.has(st.stock) ? ' bas' : ''}" data-stock="${_colE(st.stock)}" aria-pressed="${_colDonsFiltre === st.stock}" onclick="colDonsFiltre(this)">${bas.has(st.stock) ? '⚠️ ' : ''}${_colE(st.label)}</button>`).join('')
		+ `</div>` : '';
	const lignes = groupes.filter(g => !_colDonsFiltre || g.stock === _colDonsFiltre).map(o => `<div class="prop-ligne"><div class="prop-txt">
		<strong>${_colE(o.icon)} ${_colE(o.nom)}${o.n > 1 ? ` <span class="sh-inv-qty">× ${o.n}</span>` : ''}</strong>
		<span class="q-desc">${o.porteur ? `🎒 ${_colE(o.porteur)} · ` : ''}${_colE(o.stock_label)} +${_colE(o.unites)}${o.n > 1 ? ` (tout : +${_colE(o.total)})` : ''}</span></div>
		<button class="sh-drop-btn" data-sac="${_colE(o.sac || '')}" data-index="${_colE(o.index)}" data-item="${_colE(o.item_id)}" onclick="colDonner(this)">Donner</button>
		${o.n > 1 ? `<button class="sh-drop-btn" data-sac="${_colE(o.sac || '')}" data-index="${_colE(o.index)}" data-item="${_colE(o.item_id)}" data-tout="1" onclick="colDonner(this)">Tout donner</button>` : ''}</div>`).join('');
	return `<section class="prop-section"><h3>🎁 ${d.role === 'fondateur' ? 'Verser aux réserves' : 'Donner au lieu'}</h3>
		${filtres}<div class="prop-liste">${lignes || '<div class="sell-empty">Rien dans les sacs du groupe dont le lieu ait l\'usage.</div>'}</div></section>`;
}

function _colFacteurs(bloc) {
	return (bloc.facteurs || []).map(f => `<span>${_colE(COL_FACTEURS[f.id] || f.id)} : ${f.valeur > 0 && f.max === undefined ? '+' : ''}${_colE(f.valeur)}${f.max !== undefined ? '/' + _colE(f.max) : ''}</span>`).join('');
}

function colAssociationHtml(d) {
	if (d.role === 'fondateur') {
		const dem = (d.demandes || []).map(x => `<div class="prop-ligne"><div class="prop-txt">
			<strong>${_colE(x.nom)}</strong><span class="q-desc">${_colE(x.texte)}</span></div>
			<button class="sh-drop-btn" data-id="${_colE(x.id)}" data-ok="1" onclick="colRepondre(this)">Accepter</button>
			<button class="sh-drop-btn" data-id="${_colE(x.id)}" data-ok="" onclick="colRepondre(this)">Refuser</button></div>`).join('');
		const ass = (d.associes || []).map(a => `<div class="prop-ligne"><div class="prop-txt">
			<strong>${_colE(a.nom)}</strong><span class="q-desc">${_colApports(a.apports) || 'aucun apport'}</span></div>
			<button class="sh-drop-btn" data-id="${_colE(a.id)}" onclick="colExclure(this)">Exclure</button></div>`).join('');
		const sou = (d.soutiens || []).map(s => `<div class="prop-ligne"><div class="prop-txt">
			<strong>${_colE(s.nom)}</strong><span class="q-desc">${_colApports(s.dons)}</span></div></div>`).join('');
		return `<section class="prop-section"><h3>🤝 Associés (${(d.associes || []).length} · ${_colE(d.places_associes)} place(s) libre(s))</h3>
			<div class="prop-liste">${dem}${ass || (dem ? '' : '<div class="sell-empty">Aucun associé.</div>')}</div></section>
			${sou ? `<section class="prop-section"><h3>🎁 Soutiens</h3><div class="prop-liste">${sou}</div></section>` : ''}`;
	}
	if (d.role === 'associe') {
		return `<section class="prop-section"><h3>🤝 Association</h3><div class="prop-ligne"><div class="prop-txt">
			<span class="q-desc">Vous êtes associé à ce lieu. Vos apports y restent si vous partez.</span></div>
			<button class="sh-drop-btn" onclick="colQuitter()">Quitter l'association</button></div></section>`;
	}
	if (d.demande_en_attente) {
		return `<section class="prop-section"><h3>🤝 Association</h3><div class="sell-empty">Votre demande attend la réponse du fondateur.</div></section>`;
	}
	if (!d.peut_demander) return '';
	return `<section class="prop-section"><h3>🤝 Demander à s'associer</h3><div class="prop-ligne"><div class="prop-txt">
		<input type="text" id="col-demande" maxlength="300" placeholder="Quelques mots pour le fondateur">
		</div><button class="sh-drop-btn" onclick="colDemander()">Envoyer</button></div></section>`;
}

function _colApports(a) {
	return Object.keys(a || {}).map(k => `${_colE(a[k])} ${COL_APPORTS[k] || _colE(k)}`).join(' · ');
}

function colSousLieuxHtml(d) {
	const l = (d.sous_lieux || []).map(x => `<span>${x.ouvert ? '🟢' : '⚫'} ${_colE(x.label)}${x.metier && x.metier !== x.label ? ' — ' + _colE(x.metier) : ''}${x.pos ? '' : ' (à poser)'}</span>`).join('');
	return l ? `<section class="prop-section"><h3>🚪 Où entrer</h3><div class="prop-caps">${l}</div></section>` : '';
}

// 🏷️ Icône sur la carte du pays (fondateur, pure) : `d.icone_carte = {courante, choix, obligatoire}`.
// « Aucune » n'est offerte que tant que l'icône n'est pas imposée (serveur : `choisir_icone`).
function colIconeHtml(ic) {
	if (!ic) return '';
	const choix = ic.choix || [];
	const corps = choix.length ? `<div class="prop-images">`
		+ (ic.obligatoire ? '' : `<button type="button" class="prop-image" data-fichier="" aria-pressed="${!ic.courante}" onclick="colIcone(this)">
			<span style="aspect-ratio:16/9;display:flex;align-items:center;justify-content:center;font-size:1.6em;">∅</span><span>Aucune</span></button>`)
		+ choix.map(c => `<button type="button" class="prop-image" data-fichier="${_colE(c.fichier)}" aria-pressed="${c.fichier === ic.courante}" onclick="colIcone(this)">
			<img src="/towns/${encodeURIComponent(c.fichier)}" alt="" loading="lazy" style="object-fit:contain;"><span>${_colE(c.label)}</span></button>`).join('')
		+ `</div>` : `<div class="sell-empty">Aucune icône n'existe encore pour ce palier.</div>`;
	const note = ic.obligatoire ? 'À ce palier, une icône est toujours montrée.' : 'Facultative : vous pouvez ne pas en montrer.';
	return `<section class="prop-section"><h3>🏷️ Icône sur la carte du pays</h3>
		<div class="prop-ligne"><div class="prop-txt"><span class="q-desc">Elle situe votre implantation pour tous les voyageurs. ${note}</span></div></div>
		${corps}</section>`;
}

function colOngletSiteHtml(d) {
	let html = colSiteHtml(d.site, _colGere(d)) + colSousLieuxHtml(d) + colReservesHtml(d) + colApproHtml(d)
		+ colBesoinsHtml(d) + colDonsHtml(d) + colAssociationHtml(d);
	if (d.role === 'fondateur') html += colIconeHtml(d.icone_carte);
	return html;
}

function _colDate(at) {
	return new Date(at * 1000).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
}

// 📓 Carnet (fondateur) : son onglet, filtré par genre (`COL_GENRES`), toutes les lignes gardées.
function colCarnetHtml(d) {
	const journal = d.journal || [];
	const genre = j => (j.genre && COL_GENRES[j.genre]) ? j.genre : 'divers';
	const presents = Object.keys(COL_GENRES).filter(g => journal.some(j => genre(j) === g));
	if (_colCarnetFiltre && !presents.includes(_colCarnetFiltre)) _colCarnetFiltre = '';
	const filtres = presents.length > 1 ? `<div class="col-filtres" role="group" aria-label="Filtrer le carnet">`
		+ `<button type="button" class="col-filtre" data-genre="" aria-pressed="${!_colCarnetFiltre}" onclick="colCarnetFiltre(this)">Tout</button>`
		+ presents.map(g => `<button type="button" class="col-filtre" data-genre="${g}" aria-pressed="${_colCarnetFiltre === g}" onclick="colCarnetFiltre(this)">${COL_GENRES[g]}</button>`).join('')
		+ `</div>` : '';
	const lignes = journal.filter(j => !_colCarnetFiltre || genre(j) === _colCarnetFiltre).map(j => `<div class="prop-ligne"><div class="prop-txt">
		<span class="q-desc">${COL_GENRES[genre(j)].split(' ')[0]} ${_colE(_colDate(j.at))} — ${_colE(j.texte)}</span></div></div>`).join('');
	return `<section class="prop-section"><h3>📓 Carnet</h3>${filtres}
		<div class="prop-liste">${lignes || '<div class="sell-empty">Rien n\'est encore noté.</div>'}</div></section>`;
}

// Jauge (pure) : barre remplie à `valeur / max`, repère au `seuil` s'il y en a un.
function _colBarre(valeur, max, seuil, label) {
	const pct = x => (max > 0 ? Math.max(0, Math.min(100, x / max * 100)) : 0).toFixed(1);
	const bas = seuil > 0 && valeur < seuil;
	return `<div class="col-barre${bas ? ' bas' : ''}" role="meter" aria-label="${_colE(label)}" aria-valuemin="0" aria-valuemax="${_colE(max)}" aria-valuenow="${_colE(valeur)}">
		<span class="col-plein" style="width:${pct(valeur)}%"></span>${seuil > 0 ? `<span class="col-seuil" style="left:${pct(seuil)}%" title="Seuil bas : ${_colE(seuil)}"></span>` : ''}</div>`;
}

function _colJours(j) {
	if (j < 1) return 'moins d\'un jour';
	if (j > 60) return 'plus de 60 jours';
	const n = Math.round(j);
	return `${n} jour${n > 1 ? 's' : ''}`;
}

// 📦 Réserves (gérants seulement — le visiteur n'a pas `stocks`) : une jauge par stock, repère
// du seuil bas, solde estimé par jour et autonomie (`par_jour`, `jours` du serveur).
function colReservesHtml(d) {
	const stocks = d.stocks || [];
	if (!stocks.length) return '';
	const jauges = stocks.map(s => {
		const pj = s.par_jour;
		const solde = pj === undefined || pj === null ? '' : `${pj > 0 ? '+' + pj : pj < 0 ? '−' + (-pj) : '±0'} / jour`;
		const autonomie = pj === undefined || pj === null ? ''
			: s.jours !== null && s.jours !== undefined ? `≈ ${_colJours(s.jours)}` : (pj > 0 ? 'se remplit' : 'stable');
		return `<div class="col-jauge"><div class="col-jauge-tete">
			<span>${s.quantite < s.seuil ? '⚠️ ' : ''}${_colE(s.label)} : ${_colE(s.quantite)} / ${_colE(s.capacite)}</span>
			<span class="q-desc">${[solde, autonomie].filter(Boolean).map(_colE).join(' · ')}</span></div>
			${_colBarre(+s.quantite || 0, +s.capacite || 0, +s.seuil || 0, s.label)}</div>`;
	}).join('');
	return `<section class="prop-section"><h3>📦 Réserves</h3><div class="col-jauges">${jauges}</div>
		<span class="q-desc">Solde estimé : métiers, glanage et simples, moins les bouches et le feu — hors convois, achats, soins et attaques.</span></section>`;
}

function colOngletPopulationHtml(d) {
	let html = `<section class="prop-section"><h3>👥 Habitants</h3><div class="prop-caps">
		<span>Population comptée : ${_colE(d.population)}</span><span>PNJ nommés : ${_colE(d.nommes)}</span>
		<span>Logements : ${_colE(d.population + d.nommes)} / ${_colE(d.logements)}</span>
		<span>Blessés et malades : ${_colE(d.souffrants)}</span></div></section>
		<section class="prop-section"><h3>🙂 Moral : ${_colE(d.moral.mot)} (${_colE(d.moral.valeur)})</h3><div class="prop-caps">${_colFacteurs(d.moral)}</div></section>`;
	if (d.role === 'fondateur') {
		html += `<section class="prop-section"><h3>🔥 Feu</h3><div class="prop-ligne"><div class="prop-txt">
			<span class="q-desc">Grand feu : confort, moral, dissuasion — visible de loin, gourmand en bois. Feu réduit : discret, économe — vie plus dure.</span></div>
			<button class="sh-drop-btn" data-reglage="grand" ${d.feu === 'grand' ? 'disabled' : ''} onclick="colFeu(this)">Grand feu</button>
			<button class="sh-drop-btn" data-reglage="reduit" ${d.feu === 'reduit' ? 'disabled' : ''} onclick="colFeu(this)">Feu réduit</button></div></section>
			<section class="prop-section"><h3>🤝 Personnel</h3><div class="prop-ligne"><div class="prop-txt">
			<span class="q-desc">Chaque poste d'un bâtiment se tient par un PNJ nommé, que vous engagez.</span></div>
			<button class="sh-drop-btn" onclick="colOuvrirEmbauche()">Tableau d'embauche</button></div></section>`;
	}
	const s = d.palier_suivant;
	if (s) {
		const conds = s.conditions.map(c => `<span>${c.ok ? '✅' : '⬜'} ${_colE(c.label)}${c.cible !== null && c.cible !== undefined ? ` : ${_colE(c.valeur)} / ${_colE(c.cible)}` : ''}</span>`).join('');
		html += `<section class="prop-section"><h3>⬆️ Vers ${_colE(s.palier.label)}</h3><div class="prop-caps">${conds}</div>
			<div class="prop-ligne"><div class="prop-txt"><span class="sell-prix">💰 Aménagement de statut : ${_prixTexte(s.prix)}</span></div>
			${d.role === 'fondateur' && !d.chantier ? `<button class="sh-drop-btn" data-genre="statut" ${s.pret ? '' : 'disabled'} onclick="colChantier(this)">Ouvrir le chantier</button>` : ''}</div></section>`;
	}
	return html + colChantierHtml(d);
}

// Autonomie des approvisionnements : production des métiers au poste et glanage / simples
// (lecture, mêmes formules que le solde des Réserves), consignes d'achat de
// l'intendant (fondateur), convois du charretier en route.
function colApproHtml(d) {
	const a = d.approvisionnement;
	if (!a) return '';
	const libelles = {};
	(d.stocks || []).forEach(s => { libelles[s.stock] = s.label; });
	const parJour = bloc => Object.entries(bloc || {}).map(([s, v]) => `<span>${_colE(libelles[s] || s)} +${_colE(v)} / jour</span>`).join('');
	const metiers = parJour(a.metiers);
	const auto = parJour(a.autonome);
	const fondateur = d.role === 'fondateur';
	const consignes = (a.consignes || []).map(c => `<div class="prop-ligne"><div class="prop-txt">
		<strong>${_colE(c.label)}</strong>
		<span class="q-desc">${c.acheter ? `L'intendant achète, ${_prixTexte(c.plafond_jour)} par jour au plus.` : 'Pas d\'achat automatique.'}</span></div>
		${fondateur ? `<label class="q-desc"><input type="checkbox" class="col-consigne-acheter" data-stock="${_colE(c.stock)}" ${c.acheter ? 'checked' : ''}> acheter</label>
		<input type="number" min="0" step="10" class="col-consigne-plafond" data-stock="${_colE(c.stock)}" value="${_colE(c.plafond_jour)}" style="width:6em" aria-label="Plafond par jour (cuivre)">
		<button class="sh-drop-btn" data-stock="${_colE(c.stock)}" onclick="colConsigne(this)">Enregistrer</button>` : ''}</div>`).join('');
	const temps = t => { const m = Math.max(0, Math.round((t * 1000 - Date.now()) / 60000)); return m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`; };
	const convois = (a.livraisons || []).map(l => `<span>🛒 ${_colE(l.label)} +${_colE(l.unites)} de ${_colE(l.cite)} — dans ${_colE(temps(l.arrivee))}</span>`).join('');
	const qui = a.intendant
		? `L'intendant comble les réserves en consigne jusqu'au seuil bas : boutiques du lieu d'abord${a.charretier ? ', puis convoi du charretier vers la cité' : ''}, enfin troc d'un surplus. Payé sur la caisse du lieu.`
		: 'Sans intendant au poste (entrepôt), personne n\'achète ni ne troque pour le lieu.';
	return `<section class="prop-section"><h3>🧺 Approvisionnement</h3>
		${metiers ? `<span class="q-desc">Métiers au poste (selon le site) :</span><div class="prop-caps">${metiers}</div>` : ''}
		${auto ? `<span class="q-desc">Sans métier : glanage des habitants, simples des soignants.</span><div class="prop-caps">${auto}</div>` : ''}
		<span class="q-desc">${qui}</span>
		<div class="prop-liste">${consignes}</div>
		${convois ? `<div class="prop-caps">${convois}</div>` : ''}</section>`;
}

function colChantierHtml(d) {
	const c = d.chantier;
	if (!c) return '';
	let html = `<section class="prop-section"><h3>🏗️ Chantier : ${_colE(c.label)}</h3>
		${_colBarre(+c.verse || 0, +c.cout || 0, 0, 'Chantier : ' + (c.label || ''))}
		<div class="prop-ligne"><div class="prop-txt">
		<span class="q-desc">Versé : ${_prixTexte(c.verse)} sur ${_prixTexte(c.cout)} (${c.cout ? Math.floor(Math.min(1, c.verse / c.cout) * 100) : 100} %)${c.reste ? ` — reste ${_prixTexte(c.reste)}` : ''}</span></div>`;
	if (c.reste) html += `<button class="sh-drop-btn" data-montant="${_colE(c.reste)}" onclick="colFinancer(this)">Verser ce que je peux</button>`;
	html += `</div>`;
	if (!c.reste && c.genre === 'statut' && d.role === 'fondateur') {
		html += `${colModelesHtml(d.modeles)}<div class="prop-ligne"><div class="prop-txt"><span class="q-desc">Le lieu change d'image et de carte ; chaque bâtiment est replacé au plus près.</span></div>
			<button class="sh-drop-btn" ${(d.modeles || []).length ? '' : 'disabled'} onclick="colPalier()">Changer de palier</button></div>`;
	}
	return html + `</section>`;
}

// « Vend son surplus aux boutiques » d'un PNJ producteur (fondateur) : un interrupteur dont le
// libellé reste fixe — seul l'état (coché / non) dit ce qui se passe. Éteint : le surplus reste
// aux réserves. (L'ancien bouton « 💰 vend / 🔒 garde » montrait l'état ET basculait au clic.)
function colInterrupteurVente(t) {
	return `<label class="col-interrupteur" title="${t.vend ? 'Son surplus est vendu aux boutiques du lieu (recette dans la caisse)' : 'Éteint : son surplus reste dans les réserves du lieu'}">
		<input type="checkbox" role="switch" data-id="${_colE(t.id)}" ${t.vend ? 'checked' : ''} onchange="colVente(this)">
		<span class="col-interrupteur-piste" aria-hidden="true"></span><span>Vend son surplus aux boutiques</span></label>`;
}

// État d'un bâtiment (pur) : à poser, endommagé (postes à l'arrêt), ou en service.
function _colEtatBatiment(b) {
	if (!b.pos) return '⚠️ à poser';
	if (b.endommage) return '🔴 endommagé — postes à l\'arrêt';
	return '🟢 en service';
}

function colOngletBatimentsHtml(d) {
	const peutPoser = _colGere(d);
	const bat = (d.batiments || []).map(b => {
		const tenu = t => _colE(t.nom);
		// PNJ producteurs (`vend` non nul) : une ligne chacun, l'interrupteur au fondateur seul.
		const ventes = d.role !== 'fondateur' ? '' : (b.postes || []).flatMap(p => p.tenus.filter(t => t.vend !== null && t.vend !== undefined)
			.map(t => `<span class="col-vente">${_colE(t.nom)} — ${_colE(p.label)} ${colInterrupteurVente(t)}</span>`)).join('');
		const vacants = (b.postes || []).reduce((n, p) => n + Math.max(0, (+p.places || 0) - p.tenus.length), 0);
		const postes = (b.postes || []).map(p => `${p.tenus.length < p.places ? '⬜' : '✅'} ${_colE(p.label)} ${p.tenus.length}/${_colE(p.places)}${p.tenus.length ? ' (' + p.tenus.map(tenu).join(', ') + ')' : ''}`).join(' · ');
		return `<div class="prop-ligne"><div class="prop-txt">
			<strong>${_colE(b.icone)} ${_colE(b.label)}</strong>
			<span class="q-desc">${_colEtatBatiment(b)}${b.pos ? ` · case ${_colE(b.pos[0])}, ${_colE(b.pos[1])}` : ''}${vacants ? ` · ${vacants} poste${vacants > 1 ? 's' : ''} vacant${vacants > 1 ? 's' : ''}` : ''}</span>
			${postes ? `<span class="q-desc">${postes}</span>` : ''}${ventes}</div>
			${peutPoser ? `<button class="sh-drop-btn" data-batiment="${_colE(b.id)}" onclick="colPoser(this)">${b.pos ? 'Déplacer ici' : 'Poser ici'}</button>` : ''}
			${vacants && d.role === 'fondateur' ? '<button class="sh-drop-btn" onclick="colOuvrirEmbauche()">Engager</button>' : ''}
			${b.endommage && d.role === 'fondateur' ? `<button class="sh-drop-btn" data-batiment="${_colE(b.id)}" onclick="colReparer(this)">Réparer</button>` : ''}
		</div>`;
	}).join('');
	let html = colPlanHtml(d) + `<section class="prop-section"><h3>🏘️ Bâtiments</h3>
		<span class="q-desc">« Poser ici » pose le bâtiment sous vos pieds (case ${_colE((d.position || {}).x)}, ${_colE((d.position || {}).y)}).</span>
		<div class="prop-liste">${bat || '<div class="sell-empty">Aucun bâtiment.</div>'}</div></section>`;
	if (d.role === 'fondateur') {
		const bourse = _purseEnCuivre(d.purse);
		// Une ligne par achat (Auteur, 13/11) : chaque bâtiment, puis chaque boutique de cité.
		const ligne = c => `<div class="prop-ligne"><div class="prop-txt">
			<strong>${_colE(c.icone)} ${_colE(c.label)}${c.grande ? ' — grande maison' : ''}</strong>${c.categorie ? '' : `<span class="q-desc">${_colE(c.description)}</span>`}
			<span class="sell-prix">💰 ${_prixTexte(c.prix)}${c.bois || c.materiaux ? ` · 🪵 ${_colE(c.bois)} · 🧱 ${_colE(c.materiaux)}` : ''}</span>
			${c.refus ? `<span class="q-desc">⚠️ ${_colE(c.refus)}</span>` : ''}</div>
			<button class="sh-drop-btn" data-type="${_colE(c.id)}" data-categorie="${_colE(c.categorie || '')}" ${c.refus || c.prix > bourse ? 'disabled' : ''} onclick="colConstruire(this)">${c.nature === 'sous_lieu' ? 'Acheter' : 'Construire'}</button></div>`;
		const batiments = (d.catalogue || []).filter(c => c.nature !== 'sous_lieu');
		const boutiques = (d.catalogue || []).filter(c => c.nature === 'sous_lieu');
		html += `<section class="prop-section"><h3>🛠️ Construire</h3><div class="prop-liste">${batiments.map(ligne).join('')}</div></section>`;
		if (boutiques.length) html += `<section class="prop-section"><h3>🏪 Boutiques — comme en ville</h3>
			<span class="q-desc">Achetées une par une, posées sous vos pieds ; leur marchand les tient aussitôt.</span>
			<div class="prop-liste">${boutiques.map(ligne).join('')}</div></section>`;
		html += colNegoceHtml(d);
	}
	return html;
}

// 🗺️ Mini-plan (pur) : l'image du lieu, ses entrées 🚪, les bâtiments posés et vous (●).
// Une case = une unité du viewBox ; le cadre a les proportions de la grille.
function colPlanHtml(d) {
	const p = d.plan;
	if (!p || !p.dimensions) return '';
	const X = +p.dimensions.x || 0, Y = +p.dimensions.y || 0;
	if (!X || !Y) return '';
	const t = Math.max(1.2, Math.min(X, Y) / 14);   // taille des repères, en cases
	const repere = (x, y, txt, titre) => `<g><title>${_colE(titre)}</title><circle cx="${+x + .5}" cy="${+y + .5}" r="${t * .62}" fill="rgba(20,16,10,.72)" stroke="#ffd700" stroke-width="${t * .08}"/>
		<text x="${+x + .5}" y="${+y + .5}" font-size="${t * .8}" text-anchor="middle" dominant-baseline="central">${txt}</text></g>`;
	const entrees = (p.entrees || []).map((e, i) => repere(e[0], e[1], '🚪', i ? `Entrée ${i + 1}` : 'Arrivée')).join('');
	const bats = (d.batiments || []).filter(b => b.pos).map(b => repere(b.pos[0], b.pos[1], _colE(b.icone || '🏠'), b.label + (b.endommage ? ' (endommagé)' : ''))).join('');
	const moi = d.position && d.position.x !== undefined
		? `<g><title>Vous</title><circle cx="${+d.position.x + .5}" cy="${+d.position.y + .5}" r="${t * .45}" fill="#4aa3ff" stroke="#fff" stroke-width="${t * .1}"/></g>` : '';
	return `<section class="prop-section"><h3>🗺️ Plan</h3>
		<div class="col-plan" style="aspect-ratio:${X} / ${Y};background-image:url('${_colE(encodeURI(p.image))}')" role="img" aria-label="Plan de l'implantation">
		<svg viewBox="0 0 ${X} ${Y}" preserveAspectRatio="none">${entrees}${bats}${moi}</svg></div>
		<span class="q-desc">● vous · 🚪 entrées · chaque bâtiment posé à sa case.</span></section>`;
}

// Caisse du lieu et journal du négoce (fondateur) : la production vendue aux boutiques du lieu.
function colNegoceHtml(d) {
	const n = d.negoce;
	if (!n) return '';
	const lignes = (n.journal || []).map(j => `<div class="prop-ligne"><div class="prop-txt"><span class="q-desc">${({ crieur: '📣', achat: '🛒', convoi: '🐴', troc: '🔁' })[j.sens] || '⚖️'} ${_colE(j.qty)} × ${_colE(j.item)} → ${_colE(j.lieu)} : ${_prixTexte(j.cuivre)}</span></div></div>`).join('');
	return `<section class="prop-section"><h3>⚖️ Négoce</h3><div class="prop-ligne"><div class="prop-txt">
		<span class="q-desc">${n.negociant ? 'Le négociant vend le surplus de production aux boutiques du lieu.' : 'Sans négociant au comptoir, le surplus se vend moins cher.'}</span>
		<span class="sell-prix">💰 Caisse : ${_prixTexte(n.caisse)} / ${_prixTexte(n.caisse_max)}</span></div>
		<button class="sh-drop-btn" ${n.caisse ? '' : 'disabled'} onclick="colReleverCaisse()">Relever la caisse</button>
		${n.negociant ? `<button class="sh-drop-btn" onclick="colNegociant('former')">Former le négociant</button>
		<button class="sh-drop-btn" onclick="colNegociant('livres')">📒 Tenir les livres</button>` : ''}</div>
		<div class="prop-liste">${lignes}</div></section>`;
}

function colOngletDefenseHtml(d) {
	let html = `<section class="prop-section"><h3>🛡️ Sécurité : ${_colE(d.securite.mot)} (${_colE(d.securite.valeur)})</h3><div class="prop-caps">${_colFacteurs(d.securite)}</div></section>
		<section class="prop-section"><h3>🐺 Menace</h3><div class="prop-ligne"><div class="prop-txt"><div class="prop-caps"><span>${_colE(d.menace.mot)}</span><span>${_colE(d.palier.menace)}</span></div></div>
			${d.attaque_en_cours ? '<button class="sh-drop-btn" onclick="colDefendre()">⚔️ Repousser l\'attaque</button>' : ''}
			${d.menace.taniere ? '<button class="sh-drop-btn" onclick="colTaniere()">🐺 Vider la tanière</button>' : ''}</div></section>
		<section class="prop-section"><h3>🧱 Fortifications</h3><div class="prop-liste">`;
	html += (d.fortifications || []).map(f => `<div class="prop-ligne"><div class="prop-txt">
		<strong>${f.en_place ? '✅ ' : ''}${_colE(f.label)}</strong>
		<span class="q-desc">Défense +${_colE(f.defense)}${f.requis_pour ? ` · exigée pour ${_colE(f.requis_pour)}` : ''}</span>
		${f.en_place ? '' : `<span class="sell-prix">💰 ${_prixTexte(f.prix)} · 🪵 ${_colE(f.bois)} · 🧱 ${_colE(f.materiaux)}</span>`}
		${!f.en_place && f.refus ? `<span class="q-desc">⚠️ ${_colE(f.refus)}</span>` : ''}</div>
		${d.role === 'fondateur' && !f.en_place ? `<button class="sh-drop-btn" data-genre="fortification" data-objet="${_colE(f.id)}" ${f.refus || d.chantier ? 'disabled' : ''} onclick="colChantier(this)">Ouvrir le chantier</button>` : ''}
	</div>`).join('');
	return html + `</div></section>` + colChantierHtml(d);
}

const COL_ONGLETS = [['site', '🧭 Site'], ['population', '👥 Population'], ['batiments', '🏘️ Bâtiments'], ['defense', '🛡️ Défense'], ['guilde', '🏰 Guilde'], ['carnet', '📓 Carnet']];

// Pastilles d'alerte (pure) : `{onglet: raison}` — attaque ou tanière (Défense), chantier de
// statut prêt à ouvrir ou à conclure (Population, fondateur), stock sous le seuil (Site).
function colAlertes(d) {
	const a = {};
	if ((d.besoins || []).length) a.site = 'Une réserve est sous le seuil bas';
	const c = d.chantier;
	if (d.role === 'fondateur' && ((!c && d.palier_suivant && d.palier_suivant.pret) || (c && !c.reste && c.genre === 'statut')))
		a.population = 'Le chantier de statut attend votre décision';
	if (d.attaque_en_cours) a.defense = 'Le lieu est attaqué';
	else if (d.menace && d.menace.taniere) a.defense = 'La tanière peut être vidée';
	return a;
}

// Dernier onglet consulté, par implantation (stockage du navigateur ; absent ⇒ Site).
function _colOngletCle(id) { return 'telluris.colonie.onglet.' + (id || ''); }
function _colOngletLu(id) { try { return localStorage.getItem(_colOngletCle(id)) || 'site'; } catch (e) { return 'site'; } }
function _colOngletEcrit(id, onglet) { try { localStorage.setItem(_colOngletCle(id), onglet); } catch (e) {} }
const COL_TITRES = { maitre: 'Maître', fondateur: 'Membre fondateur', membre: 'Membre' };
const COL_FONCTIONS = { recrutement: 'tableau de recrues', expeditions: 'expéditions', missions: 'missions et contrats',
	specialistes: 'spécialistes', coffre: 'matériel commun', donjons: 'donjons alentour', defense: 'défense du lieu',
	attraction: 'attire les habitants' };

// La guilde du joueur (pure) : échelon, membres, missions, expéditions, matériel commun. `role`
// = rôle dans l'IMPLANTATION (le fondateur ouvre les échelons) ; le titre dans la guilde décide du reste.
function colGuildeHtml(g, role, purse) {
	if (!g) return '';
	let html = '';
	if (!g.existe) {
		const s = g.suivant;
		if (!s) return '';
		html += `<section class="prop-section"><h3>🏰 Fonder la guilde</h3><div class="prop-ligne"><div class="prop-txt">
			<span class="q-desc">${_colE(s.label)}. Les associés d'alors en seront membres fondateurs.</span>
			<span class="sell-prix">💰 ${_prixTexte(s.prix)}</span>
			${s.refus ? `<span class="q-desc">⚠️ ${_colE(s.refus)}</span>` : ''}
			${role === 'fondateur' && !s.refus ? '<input type="text" id="col-guilde-nom" maxlength="40" placeholder="Nom de la guilde (facultatif)">' : ''}</div>
			${role === 'fondateur' ? `<button class="sh-drop-btn" ${s.refus ? 'disabled' : ''} onclick="colOuvrirGuilde()">Ouvrir le chantier</button>` : ''}</div></section>`;
		return html;
	}
	const membres = (g.membres || []).map(m => `<span>${_colE(m.nom)} — ${_colE(COL_TITRES[m.titre] || m.titre)}</span>`).join('');
	html += `<section class="prop-section"><h3>🏰 ${_colE(g.nom)} — ${_colE(g.echelon)}</h3>
		<div class="prop-caps"><span>${(g.fonctions || []).map(f => _colE(COL_FONCTIONS[f] || f)).join(' · ')}</span></div>
		<div class="prop-ligne"><div class="prop-txt"><div class="prop-caps">${membres}</div></div>
		${g.titre ? (g.titre !== 'maitre' ? '<button class="sh-drop-btn" onclick="colGuilde(\'quitter\')">Quitter la guilde</button>' : '')
			: '<button class="sh-drop-btn" onclick="colGuilde(\'rejoindre\')">Rejoindre la guilde</button>'}</div></section>`;
	if (g.suivant && role === 'fondateur') {
		html += `<section class="prop-section"><div class="prop-ligne"><div class="prop-txt">
			<strong>⬆️ ${_colE(g.suivant.label)}</strong><span class="sell-prix">💰 ${_prixTexte(g.suivant.prix)}</span>
			${g.suivant.refus ? `<span class="q-desc">⚠️ ${_colE(g.suivant.refus)}</span>` : ''}</div>
			<button class="sh-drop-btn" ${g.suivant.refus ? 'disabled' : ''} onclick="colOuvrirGuilde()">Ouvrir le chantier</button></div></section>`;
	}
	const exps = (g.expeditions || []).map(e => `<div class="prop-ligne"><div class="prop-txt">
		<strong>${_colE(e.mission)}</strong><span class="q-desc">${_colE(e.par)} · ${e.revenue ? 'de retour' : 'retour le ' + _colE(new Date(e.retour * 1000).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }))} · chances ${Math.round((e.chance || 0) * 100)} %</span></div>
		${e.mienne && e.revenue ? `<button class="sh-drop-btn" data-id="${_colE(e.id)}" onclick="colAccueillir(this)">Accueillir le groupe</button>` : ''}</div>`).join('');
	if (exps) html += `<section class="prop-section"><h3>🧭 Expéditions</h3><div class="prop-liste">${exps}</div></section>`;
	if ((g.missions || []).length) {
		const comp = (g.compagnons || []).map(c => `<label><input type="checkbox" class="col-comp" value="${_colE(c.id)}"> ${_colE(c.nom)} (niv. ${_colE(c.niveau)})</label>`).join(' ');
		html += `<section class="prop-section"><h3>📜 Missions</h3>
			<div class="prop-caps">${comp || '<span>Aucun compagnon dans votre groupe.</span>'}</div><div class="prop-liste">`
			+ g.missions.map(m => `<div class="prop-ligne"><div class="prop-txt"><strong>${_colE(m.label)}</strong>
				<span class="q-desc">${Math.round(m.duree_s / 3600)} h · difficulté ${_colE(m.difficulte)}</span>
				<span class="sell-prix">💰 ${_prixTexte(m.recompense)}</span></div>
				<button class="sh-drop-btn" data-mission="${_colE(m.id)}" ${(g.compagnons || []).length ? '' : 'disabled'} onclick="colEnvoyer(this)">Envoyer</button></div>`).join('')
			+ `</div></section>`;
	}
	if (g.coffre) {
		const objets = g.coffre.map(o => `<div class="prop-ligne"><div class="prop-txt"><strong>${_colE(o.icon)} ${_colE(o.nom)}</strong></div>
			${g.peut_retirer ? `<button class="sh-drop-btn" data-index="${_colE(o.index)}" onclick="colCoffreRetirer(this)">Prendre</button>` : ''}</div>`).join('');
		const sac = (g.sac || []).map(o => `<div class="prop-ligne"><div class="prop-txt"><span class="q-desc">${_colE(o.icon)} ${_colE(o.nom)}</span></div>
			<button class="sh-drop-btn" data-index="${_colE(o.index)}" data-item="${_colE(o.item_id)}" onclick="colCoffreDeposer(this)">Déposer</button></div>`).join('');
		html += `<section class="prop-section"><h3>📦 Matériel commun</h3><div class="prop-liste">${objets || '<div class="sell-empty">Le coffre est vide.</div>'}</div>
			${sac ? `<h3>🎒 Votre sac</h3><div class="prop-liste">${sac}</div>` : ''}</section>`;
	}
	return html;
}

// Rendu complet (pure : rend une chaîne). Le visiteur n'a que la lecture : site en mots,
// tableau des besoins, dons (§ 12.7).
function colImplantationHtml(d, onglet) {
	// `.col-corps` = la seule partie qui défile : en-tête et onglets restent en place (CSS).
	if (!_colGere(d)) return colEnteteHtml(d) + `<div class="col-corps">${colOngletSiteHtml(d)}${d.guilde && d.guilde.existe ? colGuildeHtml(d.guilde, d.role, d.purse) : ''}</div>`;
	// L'onglet Guilde n'existe qu'une fois la guilde fondée ou fondable au palier courant.
	const avecGuilde = !!(d.guilde && (d.guilde.existe || d.guilde.suivant));
	const avecCarnet = Array.isArray(d.journal);   // le carnet est au fondateur
	const present = id => (id !== 'guilde' || avecGuilde) && (id !== 'carnet' || avecCarnet);
	if (!COL_ONGLETS.some(([id]) => id === onglet) || !present(onglet)) onglet = 'site';
	const alertes = colAlertes(d);
	const tabs = `<div class="col-onglets">` + COL_ONGLETS.filter(([id]) => present(id)).map(([id, nom]) =>
		`<button class="sheet-tab-btn${id === onglet ? ' active' : ''}" data-onglet="${id}" onclick="colOnglet(this)"${alertes[id] ? ` title="${_colE(alertes[id])}"` : ''}>${nom}${alertes[id] ? '<span class="col-alerte" aria-label="alerte">⚠️</span>' : ''}</button>`).join('') + `</div>`;
	const corps = onglet === 'population' ? colOngletPopulationHtml(d)
		: onglet === 'carnet' ? colCarnetHtml(d)
		: onglet === 'guilde' ? colGuildeHtml(d.guilde, d.role, d.purse)
		: onglet === 'batiments' ? colOngletBatimentsHtml(d)
		: onglet === 'defense' ? colOngletDefenseHtml(d) : colOngletSiteHtml(d);
	return colEnteteHtml(d) + tabs + `<div class="col-corps" data-onglet="${onglet}">${corps}</div>`;
}

function colRendre(d) {
	if (!d) return;
	_colData = d; _colVue = 'ici';
	updatePurse(d.purse);
	if (d.inventaire_payload) _applyInventoryPayload(d.inventaire_payload);
	// Don puisé dans le sac d'un compagnon / d'une monture (ou d'un contenant qu'il porte).
	if (d.compagnon_id) _resyncSacPorteur(d.compagnon_id, d.compagnon);
	(d.evenements || []).forEach(t => showToast(t));
	// Redessiner après une action (don, filtre…) garde la position de défilement de l'onglet ;
	// changer d'onglet repart en haut.
	const avant = document.querySelector('#colonie-contenu > .col-corps');
	const garde = avant && avant.dataset.onglet === _colOnglet ? avant.scrollTop : 0;
	_colEcrire('🏕️ ' + (d.label || 'Implantation'), colImplantationHtml(d, _colOnglet));
	const apres = garde && document.querySelector('#colonie-contenu > .col-corps');
	if (apres) apres.scrollTop = garde;
}

function _colRedessiner() { colRendre(Object.assign({}, _colData, { evenements: [] })); }
function colOnglet(btn) {
	_colOnglet = btn.dataset.onglet;
	_colOngletEcrit(_colData && _colData.id, _colOnglet);
	_colRedessiner();
}
function colDonsFiltre(btn) { _colDonsFiltre = btn.dataset.stock || ''; _colRedessiner(); }
function colCarnetFiltre(btn) { _colCarnetFiltre = btn.dataset.genre || ''; _colRedessiner(); }

async function openColonie() {
	const d = await _aubFetch('api/colonisation/ici');
	if (!d) return;
	_colOnglet = _colOngletLu(d.id);
	colRendre(d);
	_colAfficher();
}

async function _colAction(url, corps, apres) {
	const d = await _aubFetch(url, corps || {});
	if (!d) return;
	if (apres) apres(d);
	colRendre(d);
}

function colDonner(btn) {
	_colAction('api/colonisation/donner', { sac: btn.dataset.sac || null, index: +btn.dataset.index, item_id: btn.dataset.item, tout: !!btn.dataset.tout },
		d => d.don && showToast(`${d.don.nom}${d.don.nombre > 1 ? ' × ' + d.don.nombre : ''} : ${d.don.stock} +${d.don.unites}`));
}
function colFeu(btn) { _colAction('api/colonisation/feu', { reglage: btn.dataset.reglage }); }
function colConstruire(btn) {
	// Le métier voyage en `data-*` (jamais interpolé dans un onclick).
	_colAction('api/colonisation/construire', { type: btn.dataset.type, categorie: btn.dataset.categorie || null },
		() => showToast('Acheté : marchez jusqu\'à sa case, puis « Poser ici ».'));
}
// Combat joué (§ 6) : la défense du lieu attaqué, la tanière localisée. On part au combat.
async function colDefendre() {
	const d = await _aubFetch('api/colonisation/defendre', {});
	if (d && d.combat_id) window.location.href = '/combat/' + encodeURIComponent(d.combat_id);
}
async function colTaniere() {
	const d = await _aubFetch('api/colonisation/taniere', {});
	if (d && d.combat_id) window.location.href = '/combat/' + encodeURIComponent(d.combat_id);
}
// L'interrupteur DIT l'état (coché = vend) ; le libellé ne change jamais.
// Refus du serveur : on redessine, l'interrupteur reprend l'état réel.
async function colVente(input) {
	const d = await _aubFetch('api/colonisation/employe/vente', { employe_id: input.dataset.id, vente: !!input.checked });
	if (d) colRendre(d); else _colRedessiner();
}
function colConsigne(btn) {
	// Valeurs lues dans le DOM (jamais interpolées dans un onclick).
	const stock = btn.dataset.stock;
	const pick = cls => Array.from(document.querySelectorAll('.' + cls)).find(el => el.dataset.stock === stock);
	const acheter = pick('col-consigne-acheter');
	const plafond = pick('col-consigne-plafond');
	_colAction('api/colonisation/consigne', { stock, acheter: !!(acheter && acheter.checked), plafond_jour: parseInt(plafond && plafond.value, 10) || 0 },
		() => showToast('Consigne enregistrée.'));
}
function colReleverCaisse() {
	_colAction('api/colonisation/caisse/relever', {}, d => showToast(`Caisse relevée : ${_prixTexte(d.releve)}.`));
}
function colNegociant(seance) {
	_colAction('api/colonisation/negociant/' + seance, {}, () => showToast('Le négociant progresse.'));
}
function colPoser(btn) {
	// La carte porte les repères : on recharge pour voir l'icône à sa case.
	_colAction('api/colonisation/poser', { batiment: btn.dataset.batiment }, () => { window.location.reload(); });
}
function colIcone(btn) {
	if (btn.getAttribute('aria-pressed') === 'true') return;
	_colAction('api/colonisation/icone', { fichier: btn.dataset.fichier || null },
		() => showToast('🏷️ Icône de la carte changée.'));
}
function colReparer(btn) { _colAction('api/colonisation/reparer', { batiment: btn.dataset.batiment }); }
function _colGuildeRendre(d) {
	if (!d) return;
	updatePurse(d.purse);
	if (d.inventaire_payload) _applyInventoryPayload(d.inventaire_payload);
	if (d.issue) showToast(d.issue.reussie ? `Mission réussie : ${_prixTexte(d.issue.gain)} pour vous, ${_prixTexte(d.issue.commission)} pour la guilde.`
		: 'Mission manquée : le groupe revient blessé.', { major: true });
	if (_colVue === 'guilde') { _colEcrire('🏰 ' + (d.guilde.nom || 'Guilde'), colGuildeHtml(d.guilde, null, d.purse)); return; }
	if (_colData) colRendre(Object.assign({}, _colData, { guilde: d.guilde, purse: d.purse, evenements: [] }));
}
async function _colGuildeAction(url, corps) { _colGuildeRendre(await _aubFetch(url, corps || {})); }
function colGuilde(geste) { _colGuildeAction('api/colonisation/guilde/' + geste); }
function colEnvoyer(btn) {
	const ids = [...document.querySelectorAll('input.col-comp:checked')].map(c => c.value);
	_colGuildeAction('api/colonisation/guilde/envoyer', { mission: btn.dataset.mission, compagnons: ids });
}
function colAccueillir(btn) { _colGuildeAction('api/colonisation/guilde/accueillir', { expedition: btn.dataset.id }); }
function colCoffreDeposer(btn) { _colGuildeAction('api/colonisation/guilde/coffre/deposer', { index: +btn.dataset.index, item_id: btn.dataset.item }); }
function colCoffreRetirer(btn) { _colGuildeAction('api/colonisation/guilde/coffre/retirer', { index: +btn.dataset.index }); }
function colOuvrirGuilde() {
	const nom = (document.getElementById('col-guilde-nom') || {}).value || '';
	_colAction('api/colonisation/chantier/ouvrir', { genre: 'guilde', nom });
}
// ── Rangements : entrepôt commun, petit coffre de l'associé (§ 10) ─────────────────
// Même panneau que le coffre d'une propriété (`#prop-coffre-panel`, `renderCoffre` de /play) :
// à gauche votre sac, celui d'un compagnon, d'une monture ou d'un contenant ; à droite
// l'entrepôt commun ou votre petit coffre. Seules les autorisations de retrait (fondateur)
// sont propres à la colonie : `colAutorisationsHtml`, rendu sous les deux colonnes.
function colRangementsExtraHtml(d) {
	let html = '';
	if (d.associes) html += `<section class="prop-section"><h3>🤝 Retrait de l'entrepôt</h3><div class="prop-liste">` + (d.associes.map(a => `<div class="prop-ligne"><div class="prop-txt"><strong>${_colE(a.nom)}</strong>
		<span class="q-desc">${a.retrait ? 'peut prendre' : 'dépôt seulement'}</span></div>
		<button class="sh-drop-btn" data-id="${_colE(a.id)}" data-retrait="${a.retrait ? '' : '1'}" onclick="colAutoriser(this)">${a.retrait ? 'Retirer l\'autorisation' : 'Autoriser'}</button></div>`).join('')
		|| '<div class="sell-empty">Aucun associé.</div>') + `</div></section>`;
	// Journal des mouvements de l'entrepôt (fondateur) : qui a déposé ou pris quoi.
	if (d.mouvements) html += `<section class="prop-section"><h3>📒 Mouvements de l'entrepôt</h3><div class="prop-liste">`
		+ (d.mouvements.map(j => `<div class="prop-ligne"><div class="prop-txt"><span class="q-desc">${_colE(_colDate(j.at))} — ${_colE(j.texte)}</span></div></div>`).join('')
		|| '<div class="sell-empty">Aucun mouvement noté.</div>') + `</div></section>`;
	return html;
}
// « 🎁 → Réserves » sur une ligne du sac de gauche (`renderCoffre`, mode colonie) : l'objet est
// de ceux qu'un stock accepte (`reserves[item_id]` = son libellé). `sac` = '' (vous), l'id d'un
// porteur ou la clé `porteur#index` d'un contenant — l'adresse des dons (`_sacs_dons`).
function colVerserBtn(item, sac, index, reserves) {
	const stock = (reserves || {})[item && item._id];
	if (!stock) return '';
	return `<button class="sh-drop-btn" data-sac="${_colE(sac || '')}" data-idx="${_colE(index)}" data-item="${_colE(item._id)}"
		title="Verser aux réserves : ${_colE(stock)}" onclick="colVerserReserves(this)">🎁 ${_colE(stock)}</button>`;
}
async function colVerserReserves(btn) {
	const d = await _aubFetch('api/colonisation/donner', { sac: btn.dataset.sac || null, index: +btn.dataset.idx, item_id: btn.dataset.item });
	if (!d) return;
	if (d.don) showToast(`${d.don.nom} : ${d.don.stock} +${d.don.unites}`);
	const r = await _aubFetch('api/colonisation/rangements');
	if (r) _pcfAppliquer(r);
}
async function openColonieRangements() {
	const d = await _aubFetch('api/colonisation/rangements');
	if (!d) return;
	_pcfAppliquer(d);
	document.getElementById('colonie-panel').classList.add('panel-hidden');
	_pcfAfficher();
}
async function colAutoriser(btn) {
	const d = await _aubFetch('api/colonisation/rangements/autoriser', { id: btn.dataset.id, retrait: !!btn.dataset.retrait });
	if (d) _pcfAppliquer(d);
}

// ── Colons, à l'auberge d'une cité (§ 10) ───────────────────────────────────────────
function colColonsHtml(d) {
	const c = d.convoi;
	const convoi = c ? `<section class="prop-section"><div class="sell-empty">Vous escortez ${_colE(c.nombre)} colon(s) vers ${_colE(c.label)} : ils s'installeront à votre arrivée — une défaite les disperse.</div></section>` : '';
	return convoi + `<section class="prop-section"><h3>🏕️ Colons à ${_colE(d.cite)}</h3><div class="prop-liste">` + (d.offres || []).map(o => `<div class="prop-ligne"><div class="prop-txt">
		<strong>${_colE(o.label)}</strong><span class="q-desc">${o.refus ? '⚠️ ' + _colE(o.refus) : _colE(o.nombre) + ' famille(s) prête(s) à partir'}</span></div>
		<button class="sh-drop-btn" data-id="${_colE(o.id)}" ${o.refus ? 'disabled' : ''} onclick="colRecruterColons(this)">Les escorter</button></div>`).join('') + `</div></section>`;
}
async function openColonieColons() {
	const d = await _aubFetch('api/colonisation/colons');
	if (!d) return;
	_colEcrire('🏕️ Colons', colColonsHtml(d));
	_colAfficher();
}
async function colRecruterColons(btn) {
	const d = await _aubFetch('api/colonisation/colons/recruter', { implantation: btn.dataset.id });
	if (!d) return;
	if (d.recrutes) showToast(`${d.recrutes} colon(s) vous suivent.`, { major: true });
	_colEcrire('🏕️ Colons', colColonsHtml(d));
}

// Depuis la maison de guilde (sous-lieu) : la guilde seule.
async function openColonieGuilde() {
	const d = await _aubFetch('api/colonisation/guilde');
	if (!d) return;
	_colVue = 'guilde';
	updatePurse(d.purse);
	_colEcrire('🏰 ' + (d.guilde.nom || 'Guilde'), colGuildeHtml(d.guilde, null, d.purse));
	_colAfficher();
}
function colChantier(btn) {
	_colAction('api/colonisation/chantier/ouvrir', { genre: btn.dataset.genre, objet: btn.dataset.objet || null });
}
function colFinancer(btn) {
	_colAction('api/colonisation/chantier/financer', { montant: +btn.dataset.montant },
		d => showToast(d.acheve ? 'Chantier achevé.' : `Versé : ${_prixTexte(d.verse)}.`));
}
async function colPalier() {
	const d = await _aubFetch('api/colonisation/palier', { modele: _colModeleChoisi() });
	if (!d) return;
	if (d.recharger) window.location.reload();
}
function colDemander() {
	const texte = (document.getElementById('col-demande') || {}).value || '';
	_colAction('api/colonisation/association/demander', { texte }, () => showToast('Demande envoyée au fondateur.'));
}
function colRepondre(btn) {
	_colAction('api/colonisation/association/repondre', { id: btn.dataset.id, accepter: !!btn.dataset.ok });
}
function colExclure(btn) { _colAction('api/colonisation/association/exclure', { id: btn.dataset.id }); }
function colQuitter() { _colAction('api/colonisation/association/quitter', {}); }

// ── Embauche des PNJ nommés ─────────────────────────────────────────────────────────
function colEmbaucheHtml(d) {
	const bourse = _purseEnCuivre(d.purse);
	const cands = (d.candidats || []).map(c => `<div class="prop-ligne"><div class="prop-txt">
		<strong>${_colE(c.prenom)} ${_colE(c.nom)}</strong>
		<span class="q-desc">${_colE(c.metier_label)} · ${_colE(c.poste_nom)}</span>
		<span class="sell-prix">💰 ${_prixTexte(c.cout)}</span></div>
		<button class="sh-drop-btn" data-id="${_colE(c.id)}" ${c.cout > bourse ? 'disabled' : ''} onclick="colEngager(this)">Engager</button></div>`).join('');
	const emp = (d.employes || []).map(e => `<div class="prop-ligne"><div class="prop-txt">
		<strong>${_colE(e.nom)}</strong><span class="q-desc">${_colE(e.metier_label)}</span></div>
		<button class="sh-drop-btn" data-id="${_colE(e.id)}" onclick="colRenvoyer(this)">Renvoyer</button></div>`).join('');
	return `<section class="prop-section"><div class="prop-ligne"><div class="prop-txt"></div>
			<button class="sh-drop-btn" onclick="openColonie()">⟵ L'implantation</button></div></section>
		<section class="prop-section"><h3>🤝 Candidats</h3><div class="prop-liste">${cands || '<div class="sell-empty">Aucun poste libre : construisez un bâtiment qui en ouvre.</div>'}</div></section>
		<section class="prop-section"><h3>👥 En poste</h3><div class="prop-liste">${emp || '<div class="sell-empty">Personne encore.</div>'}</div></section>`;
}

function _colRendreEmbauche(d) {
	if (!d) return;
	_colVue = 'embauche';
	updatePurse(d.purse);
	if (d.engage) showToast(`${d.engage} rejoint le lieu.`);
	_colEcrire('🤝 Embauche', colEmbaucheHtml(d));
}
async function colOuvrirEmbauche() { _colRendreEmbauche(await _aubFetch('api/colonisation/embauche')); }
async function colEngager(btn) { _colRendreEmbauche(await _aubFetch('api/colonisation/engager', { candidat_id: btn.dataset.id })); }
async function colRenvoyer(btn) {
	const d = await _aubFetch('api/colonisation/renvoyer', { employe_id: btn.dataset.id });
	if (d) colOuvrirEmbauche();
}
