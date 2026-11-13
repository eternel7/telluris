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

const COL_AXES = { eau: '💧 Eau', nourriture: '🌾 Nourriture', materiaux: '🪵 Matériaux',
	commerce: '⚖️ Commerce', defense: '⛰️ Défense', danger: '🐺 Danger' };
const COL_FACTEURS = {
	defense_physique: 'Défense physique', defense_humaine: 'Défense humaine', environnement: 'Environnement',
	logistique: 'Logistique', connaissance_territoire: 'Connaissance du territoire',
	nourriture: 'Nourriture', logement: 'Logement', soignant: 'Soignant présent', attaques: 'Attaques récentes',
	morts: 'Morts récentes', prosperite: 'Prospérité', expeditions: 'Expéditions réussies',
	reputation: 'Réputation du fondateur', feu: 'Feu', securite: 'Sécurité' };
const COL_ROLES = { fondateur: 'Fondateur', associe: 'Associé', soutien: 'Soutien', visiteur: 'Visiteur' };
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
		const note = chiffres && b.note !== undefined ? ` <span class="q-desc">(${_colE(b.note)}/3)</span>` : '';
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
		<span class="q-desc">Rang ${_colE(r.rang_min)} au moins · ${_colE(r.distance_cite_min)} cases de toute Cité-État ·
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
	</div></section>`;
}

function colBesoinsHtml(d) {
	const b = (d.besoins || []).map(x => `<span>⚠️ ${_colE(x.label)}</span>`).join('');
	return `<section class="prop-section"><h3>📋 Tableau des besoins</h3>
		${b ? `<div class="prop-caps">${b}</div>` : '<div class="sell-empty">Le lieu ne manque de rien.</div>'}</section>`;
}

function colDonsHtml(d) {
	const lignes = (d.dons_possibles || []).map(o => `<div class="prop-ligne"><div class="prop-txt">
		<strong>${_colE(o.icon)} ${_colE(o.nom)}</strong>
		<span class="q-desc">${_colE(o.stock_label)} +${_colE(o.unites)}</span></div>
		<button class="sh-drop-btn" data-index="${_colE(o.index)}" data-item="${_colE(o.item_id)}" onclick="colDonner(this)">Donner</button></div>`).join('');
	return `<section class="prop-section"><h3>🎁 ${d.role === 'fondateur' ? 'Verser aux réserves' : 'Donner au lieu'}</h3>
		<div class="prop-liste">${lignes || '<div class="sell-empty">Rien dans votre sac dont le lieu ait l\'usage.</div>'}</div></section>`;
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

function colOngletSiteHtml(d) {
	let html = colSiteHtml(d.site, _colGere(d)) + colSousLieuxHtml(d) + colBesoinsHtml(d) + colDonsHtml(d) + colAssociationHtml(d);
	if (d.role === 'fondateur' && (d.journal || []).length) {
		html += `<section class="prop-section"><h3>📓 Carnet</h3><div class="prop-liste">`
			+ d.journal.slice(0, 20).map(j => `<div class="prop-ligne"><div class="prop-txt"><span class="q-desc">${_colE(new Date(j.at * 1000).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }))} — ${_colE(j.texte)}</span></div></div>`).join('')
			+ `</div></section>`;
	}
	return html;
}

function colOngletPopulationHtml(d) {
	const stocks = (d.stocks || []).map(s => `<span>${s.quantite < s.seuil ? '⚠️ ' : ''}${_colE(s.label)} : ${_colE(s.quantite)} / ${_colE(s.capacite)}</span>`).join('');
	let html = `<section class="prop-section"><h3>👥 Habitants</h3><div class="prop-caps">
		<span>Population comptée : ${_colE(d.population)}</span><span>PNJ nommés : ${_colE(d.nommes)}</span>
		<span>Logements : ${_colE(d.population + d.nommes)} / ${_colE(d.logements)}</span>
		<span>Blessés et malades : ${_colE(d.souffrants)}</span></div></section>
		<section class="prop-section"><h3>📦 Réserves</h3><div class="prop-caps">${stocks}</div></section>
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

function colChantierHtml(d) {
	const c = d.chantier;
	if (!c) return '';
	let html = `<section class="prop-section"><h3>🏗️ Chantier : ${_colE(c.label)}</h3><div class="prop-ligne"><div class="prop-txt">
		<span class="q-desc">Versé : ${_prixTexte(c.verse)} sur ${_prixTexte(c.cout)}${c.reste ? ` — reste ${_prixTexte(c.reste)}` : ''}</span></div>`;
	if (c.reste) html += `<button class="sh-drop-btn" data-montant="${_colE(c.reste)}" onclick="colFinancer(this)">Verser ce que je peux</button>`;
	html += `</div>`;
	if (!c.reste && c.genre === 'statut' && d.role === 'fondateur') {
		html += `${colModelesHtml(d.modeles)}<div class="prop-ligne"><div class="prop-txt"><span class="q-desc">Le lieu change d'image et de carte ; chaque bâtiment est replacé au plus près.</span></div>
			<button class="sh-drop-btn" ${(d.modeles || []).length ? '' : 'disabled'} onclick="colPalier()">Changer de palier</button></div>`;
	}
	return html + `</section>`;
}

function colOngletBatimentsHtml(d) {
	const peutPoser = _colGere(d);
	const bat = (d.batiments || []).map(b => {
		const tenu = t => _colE(t.nom) + (t.vend === null || t.vend === undefined || d.role !== 'fondateur' ? ''
			: ` <button class="sh-drop-btn" data-id="${_colE(t.id)}" data-vente="${t.vend ? '' : '1'}" onclick="colVente(this)">${t.vend ? '💰 vend' : '🔒 garde'}</button>`);
		const postes = (b.postes || []).map(p => `${_colE(p.label)} ${p.tenus.length}/${_colE(p.places)}${p.tenus.length ? ' (' + p.tenus.map(tenu).join(', ') + ')' : ''}`).join(' · ');
		return `<div class="prop-ligne"><div class="prop-txt">
			<strong>${_colE(b.icone)} ${_colE(b.label)}${b.endommage ? ' — endommagé' : ''}</strong>
			<span class="q-desc">${b.pos ? `case ${_colE(b.pos[0])}, ${_colE(b.pos[1])}` : '⚠️ à poser'}${postes ? ' · ' + postes : ''}</span></div>
			${peutPoser ? `<button class="sh-drop-btn" data-batiment="${_colE(b.id)}" onclick="colPoser(this)">${b.pos ? 'Déplacer ici' : 'Poser ici'}</button>` : ''}
			${b.endommage && d.role === 'fondateur' ? `<button class="sh-drop-btn" data-batiment="${_colE(b.id)}" onclick="colReparer(this)">Réparer</button>` : ''}
		</div>`;
	}).join('');
	let html = `<section class="prop-section"><h3>🏘️ Bâtiments</h3>
		<span class="q-desc">« Poser ici » pose le bâtiment sous vos pieds (case ${_colE((d.position || {}).x)}, ${_colE((d.position || {}).y)}).</span>
		<div class="prop-liste">${bat || '<div class="sell-empty">Aucun bâtiment.</div>'}</div></section>`;
	if (d.role === 'fondateur') {
		const bourse = _purseEnCuivre(d.purse);
		html += `<section class="prop-section"><h3>🛠️ Construire</h3><div class="prop-liste">` + (d.catalogue || []).map(c => `<div class="prop-ligne"><div class="prop-txt">
			<strong>${_colE(c.icone)} ${_colE(c.label)}</strong><span class="q-desc">${_colE(c.description)}</span>
			<span class="sell-prix">💰 ${_prixTexte(c.prix)} · 🪵 ${_colE(c.bois)} · 🧱 ${_colE(c.materiaux)}</span>
			${c.refus ? `<span class="q-desc">⚠️ ${_colE(c.refus)}</span>` : ''}</div>
			${(c.categories || []).length ? `<select class="col-categorie" data-type="${_colE(c.id)}">${c.categories.map(k => `<option value="${_colE(k.id)}">${_colE(k.label)}</option>`).join('')}</select>` : ''}
			<button class="sh-drop-btn" data-type="${_colE(c.id)}" ${c.refus || c.prix > bourse ? 'disabled' : ''} onclick="colConstruire(this)">Construire</button></div>`).join('') + `</div></section>`;
		html += colNegoceHtml(d);
	}
	return html;
}

// Caisse du lieu et journal du négoce (fondateur) : la production vendue aux boutiques du lieu.
function colNegoceHtml(d) {
	const n = d.negoce;
	if (!n) return '';
	const lignes = (n.journal || []).map(j => `<div class="prop-ligne"><div class="prop-txt"><span class="q-desc">${j.sens === 'crieur' ? '📣' : '⚖️'} ${_colE(j.qty)} × ${_colE(j.item)} → ${_colE(j.lieu)} : ${_prixTexte(j.cuivre)}</span></div></div>`).join('');
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
		<section class="prop-section"><h3>🐺 Menace</h3><div class="prop-caps"><span>${_colE(d.menace.mot)}</span><span>${_colE(d.palier.menace)}</span></div></section>
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

const COL_ONGLETS = [['site', '🧭 Site'], ['population', '👥 Population'], ['batiments', '🏘️ Bâtiments'], ['defense', '🛡️ Défense']];

// Rendu complet (pure : rend une chaîne). Le visiteur n'a que la lecture : site en mots,
// tableau des besoins, dons (§ 12.7).
function colImplantationHtml(d, onglet) {
	if (!_colGere(d)) return colEnteteHtml(d) + colOngletSiteHtml(d);
	const tabs = `<div class="col-onglets">` + COL_ONGLETS.map(([id, nom]) =>
		`<button class="sheet-tab-btn${id === onglet ? ' active' : ''}" data-onglet="${id}" onclick="colOnglet(this)">${nom}</button>`).join('') + `</div>`;
	const corps = onglet === 'population' ? colOngletPopulationHtml(d)
		: onglet === 'batiments' ? colOngletBatimentsHtml(d)
		: onglet === 'defense' ? colOngletDefenseHtml(d) : colOngletSiteHtml(d);
	return colEnteteHtml(d) + tabs + corps;
}

function colRendre(d) {
	if (!d) return;
	_colData = d; _colVue = 'ici';
	updatePurse(d.purse);
	if (d.inventaire_payload) _applyInventoryPayload(d.inventaire_payload);
	(d.evenements || []).forEach(t => showToast(t));
	_colEcrire('🏕️ ' + (d.label || 'Implantation'), colImplantationHtml(d, _colOnglet));
}

function colOnglet(btn) { _colOnglet = btn.dataset.onglet; colRendre(Object.assign({}, _colData, { evenements: [] })); }

async function openColonie() {
	const d = await _aubFetch('api/colonisation/ici');
	if (!d) return;
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
	_colAction('api/colonisation/donner', { index: +btn.dataset.index, item_id: btn.dataset.item },
		d => d.don && showToast(`${d.don.nom} : ${d.don.stock} +${d.don.unites}`));
}
function colFeu(btn) { _colAction('api/colonisation/feu', { reglage: btn.dataset.reglage }); }
function colConstruire(btn) {
	// Le métier d'un sous-lieu est LU dans son sélecteur (jamais interpolé dans un onclick).
	const sel = document.querySelector(`select.col-categorie[data-type="${btn.dataset.type}"]`);
	_colAction('api/colonisation/construire', { type: btn.dataset.type, categorie: sel ? sel.value : null },
		() => showToast('Bâtiment prêt : marchez jusqu\'à sa case, puis « Poser ici ».'));
}
function colVente(btn) { _colAction('api/colonisation/employe/vente', { employe_id: btn.dataset.id, vente: !!btn.dataset.vente }); }
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
function colReparer(btn) { _colAction('api/colonisation/reparer', { batiment: btn.dataset.batiment }); }
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
