// templates/scripts/enigmes.js — panneau d'énigme de /play (docs/conception_enigmes.md).
//
// Le SERVEUR tranche (routers/enigmes.py) : ce fichier n'a jamais la solution, il envoie des
// essais et rend la vue reçue. Rendu « les deux » (Auteur, 19/11) : scène illustrée à zones
// cliquables quand `vue.image` existe, et toujours, dessous, les commandes parchemin + SVG —
// une énigme se joue avant que son image soit faite.
//
// ⚠️ Overlay de décision : ✕ / Échap / clic sur le fond FERMENT sans rien envoyer
// (CLAUDE.md, convention 8). Le brouillon local (crans tournés, symboles posés…) n'est
// envoyé qu'au bouton « Essayer ».
//
// Fonctions de rendu PURES (`enigmeCorps`, `enigmeScene`, `enigmeJournal`, `enigmeVoix`,
// `enigmeBrouillonInitial`, `enigmesIciHtml`) : exécutées par dev/test_enigmes_client.js.
//
// Une RÉSOLUTION ne recharge pas /play : la réponse porte le resync du lieu (portes, énigmes à
// bouton, lignes 🗣, journal), appliqué par `_appliquerResyncLieu` de la page ; un dialogue
// resté ouvert sous le panneau est rouvert à sa fermeture (ses choix ont pu changer).

let _enigme = null;   // { vue, brouillon, outil, selection, resolue_ici }

function _eniEsc(s) {
	if (typeof escapeHtml === 'function') return escapeHtml(s);
	return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
		({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function _eniLabel(liste, id) {
	const x = (liste || []).find(e => e && e.id === id);
	return x ? (x.label || x.texte || id) : id;
}

// Brouillon local tiré de l'état serveur : ce que le joueur manipule avant d'essayer.
function enigmeBrouillonInitial(vue) {
	const etat = (vue && vue.etat) || {};
	const b = {};
	if (vue.famille === 'crans') b.positions = Object.assign({}, etat.positions || {});
	if (vue.famille === 'placement') b.placement = Object.assign({}, etat.placement || {});
	if (vue.famille === 'reseau') {
		b.actives = (etat.actives || []).slice();
		b.ancrees = (etat.ancrees || []).slice();
	}
	return b;
}

// ── Rendu par famille (chaînes HTML ; tout texte de donnée est échappé) ──────────────

function _eniIndices(vue) {
	const el = vue.elements || {};
	const vus = (vue.etat && vue.etat.examines) || [];
	const indices = (el.indices || []).map(i =>
		`<button type="button" class="eni-btn${vus.includes(i.id) ? ' eni-vu' : ''}" data-eni-cle="${_eniEsc(i.id)}">`
		+ `${vus.includes(i.id) ? '✓ ' : ''}${_eniEsc(i.label)}</button>`).join('');
	return `<h4>Examiner</h4><div class="eni-grille">${indices}</div>`;
}

function _eniDeduction(vue) {
	const el = vue.elements || {};
	const conclusions = (el.conclusions || []).map(c =>
		`<button type="button" class="eni-btn eni-conclure" data-eni-conclure="${_eniEsc(c.id)}">${_eniEsc(c.label)}</button>`).join('');
	return _eniIndices(vue)
		+ `<h4>Conclure</h4><div class="eni-grille">${conclusions}</div>`;
}

function _eniCrans(vue, b) {
	const pieces = (vue.elements && vue.elements.pieces) || [];
	const lignes = pieces.map(p => {
		const v = (b.positions || {})[p.id] || 0;
		return `<div class="eni-cran"><span>${_eniEsc(p.label || p.id)}</span>`
			+ `<button type="button" class="eni-btn" data-eni-cran="${_eniEsc(p.id)}" data-eni-pas="-1" aria-label="Cran précédent">−</button>`
			+ `<output>${v + 1} / ${p.crans || 1}</output>`
			+ `<button type="button" class="eni-btn" data-eni-cran="${_eniEsc(p.id)}" data-eni-pas="1" aria-label="Cran suivant">+</button></div>`;
	}).join('');
	return lignes + `<button type="button" class="eni-btn eni-essayer" data-eni-essayer="1">Essayer</button>`;
}

function _eniGraphe(vue) {
	const el = vue.elements || {};
	const etat = vue.etat || {};
	const arches = (etat.arches_ici || []).map(a => {
		const arche = (el.arches || []).find(x => x.id === a) || { id: a };
		return `<button type="button" class="eni-btn eni-arche" data-eni-cle="${_eniEsc(a)}">`
			+ `${arche.symbole ? _eniEsc(arche.symbole) + ' ' : ''}${_eniEsc(arche.label || a)}</button>`;
	}).join('');
	return `<p class="eni-ici">Vous êtes : <strong>${_eniEsc(_eniLabel(el.salles, etat.position))}</strong></p>`
		+ `<div class="eni-grille">${arches}</div>`
		+ (etat.position !== el.depart
			? `<button type="button" class="eni-btn eni-secondaire" data-eni-recommencer="1">Revenir à l'entrée</button>` : '');
}

function _eniAssociation(vue, sel) {
	const el = vue.elements || {};
	const trouvees = (vue.etat && vue.etat.paires) || {};
	const choisi = sel || {};
	const col = (liste, cote) => (liste || []).map(x => {
		const fait = cote === 'gauche' ? x.id in trouvees : Object.values(trouvees).includes(x.id);
		return `<button type="button" class="eni-btn${fait ? ' eni-vu' : ''}${choisi[cote] === x.id ? ' eni-choisi' : ''}"`
			+ ` data-eni-assoc="${cote}" data-eni-id="${_eniEsc(x.id)}"${fait ? ' disabled' : ''}>${_eniEsc(x.texte || x.label || x.id)}</button>`;
	}).join('');
	return `<div class="eni-deux"><div class="eni-col">${col(el.gauche, 'gauche')}</div>`
		+ `<div class="eni-col">${col(el.droite, 'droite')}</div></div>`;
}

function _eniPlacement(vue, b) {
	const el = vue.elements || {};
	const options = id => `<option value="">—</option>` + (el.symboles || []).map(s =>
		`<option value="${_eniEsc(s.id)}"${(b.placement || {})[id] === s.id ? ' selected' : ''}>`
		+ `${s.icone ? _eniEsc(s.icone) + ' ' : ''}${_eniEsc(s.label || s.id)}</option>`).join('');
	const lignes = (el.emplacements || []).map(e =>
		`<label class="eni-cran"><span>${_eniEsc(e.label || e.id)}</span>`
		+ `<select data-eni-place="${_eniEsc(e.id)}">${options(e.id)}</select></label>`).join('');
	return lignes + `<button type="button" class="eni-btn eni-essayer" data-eni-essayer="1">Essayer</button>`;
}

// Carte de liaisons : nœuds sur un cercle, liaisons en traits (SVG). Clé = ouvrir une liaison,
// pierre = l'ancrer, miroir = révéler les liens cachés d'un lieu.
function _eniReseau(vue, b, outil) {
	const el = vue.elements || {};
	const noeuds = el.noeuds || [];
	const n = Math.max(noeuds.length, 1);
	const pos = {};
	noeuds.forEach((x, i) => {
		const a = -Math.PI / 2 + 2 * Math.PI * i / n;
		pos[x.id] = [150 + 110 * Math.cos(a), 130 + 100 * Math.sin(a)];
	});
	const actives = b.actives || [], ancrees = b.ancrees || [];
	const traits = (el.liaisons || []).filter(l => pos[l.a] && pos[l.b]).map(l => {
		const cls = ['eni-lien', actives.includes(l.id) ? 'eni-ouvert' : '', ancrees.includes(l.id) ? 'eni-ancre' : '',
			l.revelee ? 'eni-revele' : ''].filter(Boolean).join(' ');
		return `<line class="${cls}" data-eni-lien="${_eniEsc(l.id)}" x1="${pos[l.a][0]}" y1="${pos[l.a][1]}" x2="${pos[l.b][0]}" y2="${pos[l.b][1]}"/>`;
	}).join('');
	// Libellé ancré du côté du nœud : centré, un long libellé à gauche ou à droite déborde du viewBox
	// et y est rogné (« ogement du cristal »). À gauche, il part du nœud vers le centre ; à droite, il y finit.
	const points = noeuds.map(x => {
		const [cx, cy] = pos[x.id];
		const [tx, ancre] = cx < 110 ? [cx - 9, 'start'] : cx > 190 ? [cx + 9, 'end'] : [cx, 'middle'];
		return `<g class="eni-noeud" data-eni-noeud="${_eniEsc(x.id)}"><circle cx="${cx}" cy="${cy}" r="9"/>`
			+ `<text x="${tx}" y="${cy - 14}" text-anchor="${ancre}">${_eniEsc(x.label || x.id)}</text></g>`;
	}).join('');
	const outils = [['cle', '🗝️ Clé'], ['pierre', '🪨 Pierre'], ['miroir', '🪞 Miroir']].map(([k, l]) =>
		`<button type="button" class="eni-btn${outil === k ? ' eni-choisi' : ''}" data-eni-outil="${k}">${l}</button>`).join('');
	const liste = (el.liaisons || []).map(l =>
		`<button type="button" class="eni-btn${actives.includes(l.id) ? ' eni-choisi' : ''}" data-eni-lien="${_eniEsc(l.id)}">`
		+ `${ancrees.includes(l.id) ? '🪨 ' : ''}${_eniEsc(_eniLabel(noeuds, l.a))} — ${_eniEsc(_eniLabel(noeuds, l.b))}</button>`).join('');
	return `<div class="eni-grille">${outils}</div>`
		+ `<svg class="eni-carte" viewBox="0 0 300 260" role="img" aria-label="Carte des liaisons">${traits}${points}</svg>`
		+ `<div class="eni-grille">${liste}</div>`
		+ `<button type="button" class="eni-btn eni-essayer" data-eni-essayer="1">Essayer</button>`;
}

function enigmeCorps(vue, brouillon, outil, selection) {
	if (!vue) return '';
	if (vue.resolue) {
		const fait = `<p class="eni-reussite">${_eniEsc(vue.reussite || '')}</p>`;
		// Une déduction résolue s'examine encore : un indice laissé de côté reste à noter.
		return vue.famille === 'deduction' ? fait + _eniIndices(vue) : fait;
	}
	const b = brouillon || {};
	switch (vue.famille) {
		case 'deduction': return _eniDeduction(vue);
		case 'crans': return _eniCrans(vue, b);
		case 'graphe': return _eniGraphe(vue);
		case 'association': return _eniAssociation(vue, selection);
		case 'placement': return _eniPlacement(vue, b);
		case 'reseau': return _eniReseau(vue, b, outil || 'cle');
		default: return '';
	}
}

// Scène illustrée : l'image et ses zones (en % de l'image) ; vide sans image.
function enigmeScene(vue) {
	if (!vue || !vue.image) return '';
	const zones = (vue.zones || []).map(z =>
		`<button type="button" class="eni-zone" data-eni-zone="${_eniEsc(z.cle)}" title="${_eniEsc(z.label || '')}"`
		+ ` style="left:${+z.x || 0}%;top:${+z.y || 0}%;width:${+z.w || 0}%;height:${+z.h || 0}%"></button>`).join('');
	return `<div class="eni-scene"><img src="/enigmes/${encodeURIComponent(vue.image)}" alt=""`
		+ ` onerror="this.parentNode.remove()">${zones}</div>`;
}

function enigmeJournal(vue) {
	const j = (vue && vue.journal) || [];
	if (!j.length) return '';
	return `<details class="eni-journal" open><summary>Journal (${j.length})</summary><ul>`
		+ j.map(f => `<li>${_eniEsc(f)}</li>`).join('') + `</ul></details>`;
}

function enigmeVoix(commentaires) {
	return (commentaires || []).map(c =>
		`<p class="eni-voix"><strong>${_eniEsc(c.qui)}</strong> : « ${_eniEsc(c.texte)} »</p>`).join('');
}

// ── Panneau ────────────────────────────────────────────────────────────────────

const _ENI_CSS = `
#enigme-overlay { position: fixed; inset: 0; z-index: 9350; background: rgba(10, 8, 5, .8);
	display: flex; align-items: center; justify-content: center; padding: 1rem; }
#enigme-overlay[hidden] { display: none; }
#enigme-overlay .eni-carte-panneau { position: relative; width: min(760px, 100%); max-height: 92vh; overflow: auto;
	background: #2a2418; color: #eadfc8; border: 1px solid #6b5a3a; border-radius: 12px;
	padding: 1.1rem 1.2rem; box-shadow: 0 10px 40px rgba(0,0,0,.6); font-family: inherit; }
#enigme-overlay h3 { margin: 0 2rem .4rem 0; color: #e2c58a; }
#enigme-overlay h4 { margin: .8rem 0 .3rem; font-size: .9rem; color: #c8a96e; }
.eni-fermer { position: absolute; top: .5rem; right: .6rem; background: none; border: 0; color: #eadfc8;
	font-size: 1.3rem; cursor: pointer; }
.eni-texte { font-style: italic; margin: 0 0 .6rem; line-height: 1.45; }
.eni-grille { display: flex; flex-wrap: wrap; gap: .35rem; margin: .3rem 0; }
.eni-btn { background: #3b3122; color: #eadfc8; border: 1px solid #6b5a3a; border-radius: 6px;
	padding: .4rem .65rem; cursor: pointer; font: inherit; min-height: 2.2rem; }
.eni-btn:hover:not(:disabled) { border-color: #e2c58a; }
.eni-btn:disabled { opacity: .55; cursor: default; }
.eni-vu { border-color: #7d9a5a; }
.eni-choisi { background: #5a4a2a; border-color: #e2c58a; }
.eni-essayer { margin-top: .6rem; background: #6b5a2a; }
.eni-secondaire { margin-top: .4rem; opacity: .85; }
.eni-cran { display: flex; align-items: center; gap: .5rem; margin: .3rem 0; }
.eni-cran > span { flex: 1 1 auto; }
.eni-cran output { min-width: 3.5rem; text-align: center; }
.eni-cran select { background: #3b3122; color: #eadfc8; border: 1px solid #6b5a3a; border-radius: 6px; padding: .3rem; }
.eni-deux { display: grid; grid-template-columns: 1fr 1fr; gap: .6rem; }
.eni-col { display: flex; flex-direction: column; gap: .35rem; }
.eni-carte { width: 100%; max-width: 420px; display: block; margin: .3rem auto; }
.eni-lien { stroke: #7a6a4a; stroke-width: 3; stroke-dasharray: 6 5; cursor: pointer; }
.eni-lien.eni-ouvert { stroke: #e2c58a; stroke-dasharray: none; }
.eni-lien.eni-ancre { stroke-width: 5; }
.eni-lien.eni-revele { stroke: #9ab0d8; }
/* Une liaison cachée, révélée par le miroir, TREMBLE : c'est elle que « ce qui tremble se tient à la
   pierre » désigne. La pierre posée la fige. */
.eni-lien.eni-revele:not(.eni-ancre) { animation: eni-tremble .18s linear infinite alternate; }
@keyframes eni-tremble { from { transform: translate(-1.2px, .8px); } to { transform: translate(1.2px, -.8px); } }
@media (prefers-reduced-motion: reduce) { .eni-lien.eni-revele:not(.eni-ancre) { animation: none; stroke-dasharray: 2 3; } }
.eni-noeud circle { fill: #3b3122; stroke: #e2c58a; stroke-width: 2; cursor: pointer; }
.eni-noeud text { fill: #eadfc8; font-size: 11px; }
.eni-scene { position: relative; margin: .4rem 0; }
.eni-scene img { width: 100%; display: block; border-radius: 8px; }
.eni-zone { position: absolute; background: transparent; border: 1px dashed transparent; border-radius: 6px; cursor: pointer; padding: 0; }
.eni-zone:hover, .eni-zone:focus-visible { border-color: rgba(226, 197, 138, .8); background: rgba(226, 197, 138, .12); }
.eni-message { margin: .6rem 0 0; min-height: 1.2rem; }
/* Verdict d'un essai (_eniVerdict) : le texte d'échec est le même d'un essai à l'autre, donc le
   compteur et l'animation, rejouée à CHAQUE essai, disent que la tentative a été prise en compte. */
.eni-verdict { margin: .6rem 0 0; font-weight: bold; transform-origin: left center; }
/* La secousse décale #eni-corps de quelques px : sans ceci, le panneau (overflow:auto) affiche une
   barre horizontale le temps de l'animation. */
#enigme-overlay .eni-carte-panneau { overflow-x: hidden; }
.eni-verdict:empty { display: none; }
.eni-verdict.eni-echec { color: #e89a8a; }
.eni-verdict.eni-succes { color: #e2c58a; }
.eni-verdict.eni-joue { animation: eni-flash .7s ease-out; }
.eni-corps-secoue { animation: eni-secoue .45s ease-in-out; }
.eni-corps-brille { animation: eni-brille 1.2s ease-out; border-radius: 8px; }
.eni-essayer.eni-envoi { opacity: .7; cursor: progress; }
@keyframes eni-flash { 0% { opacity: 0; transform: scale(1.15); } 40% { opacity: 1; } 100% { transform: none; } }
@keyframes eni-secoue { 0%, 100% { transform: none; } 20%, 60% { transform: translateX(-7px); } 40%, 80% { transform: translateX(7px); } }
@keyframes eni-brille { 0% { box-shadow: 0 0 0 0 rgba(226, 197, 138, .8); } 100% { box-shadow: 0 0 0 18px rgba(226, 197, 138, 0); } }
@media (prefers-reduced-motion: reduce) { .eni-verdict.eni-joue, .eni-corps-secoue, .eni-corps-brille { animation: none; } }
.eni-voix { margin: .3rem 0; padding: .35rem .6rem; border-left: 3px solid #c8a96e; background: rgba(0,0,0,.18); }
.eni-reussite { font-size: 1.05rem; color: #e2c58a; }
.eni-journal { margin-top: .8rem; font-size: .9rem; }
.eni-journal ul { margin: .3rem 0 0 1.1rem; padding: 0; }
@media (max-width: 520px) { .eni-deux { grid-template-columns: 1fr; } }
`;

function _eniPanneau() {
	let o = document.getElementById('enigme-overlay');
	if (o) return o;
	const style = document.createElement('style');
	style.textContent = _ENI_CSS;
	document.head.appendChild(style);
	o = document.createElement('div');
	o.id = 'enigme-overlay';
	o.hidden = true;
	o.setAttribute('role', 'dialog');
	o.setAttribute('aria-modal', 'true');
	o.innerHTML = `<div class="eni-carte-panneau">
		<button type="button" class="eni-fermer" title="Fermer" aria-label="Fermer">✕</button>
		<h3 id="eni-nom"></h3><p class="eni-texte" id="eni-texte"></p>
		<div id="eni-scene"></div><div id="eni-corps"></div>
		<div class="eni-verdict" id="eni-verdict" aria-live="polite"></div>
		<div class="eni-message" id="eni-message" aria-live="polite"></div>
		<div id="eni-voix"></div><div id="eni-journal"></div></div>`;
	document.body.appendChild(o);
	o.addEventListener('click', ev => {
		if (ev.target === o || ev.target.closest('.eni-fermer')) { fermerEnigme(); return; }
		_eniClic(ev);
	});
	o.addEventListener('change', ev => {
		const s = ev.target.closest('[data-eni-place]');
		if (s && _enigme) {
			if (s.value) _enigme.brouillon.placement[s.dataset.eniPlace] = s.value;
			else delete _enigme.brouillon.placement[s.dataset.eniPlace];
		}
	});
	document.addEventListener('keydown', ev => {
		if (ev.key === 'Escape' && !o.hidden) { ev.stopPropagation(); fermerEnigme(); }
	});
	return o;
}

// Sans argument (brouillon manipulé localement), garde la dernière remarque et les voix.
function _eniRendre(message, commentaires) {
	const o = _eniPanneau();
	if (message === undefined) ({ message, commentaires } = _enigme.dernier || {});
	else _enigme.dernier = { message, commentaires };
	const vue = _enigme.vue;
	o.querySelector('#eni-nom').textContent = vue.nom || '';
	o.querySelector('#eni-texte').textContent = vue.texte || '';
	o.querySelector('#eni-scene').innerHTML = vue.resolue ? '' : enigmeScene(vue);
	o.querySelector('#eni-corps').innerHTML = enigmeCorps(vue, _enigme.brouillon, _enigme.outil, _enigme.selection);
	o.querySelector('#eni-message').textContent = message || '';
	// Le verdict ne survit pas à une manipulation : la tentative suivante n'est pas encore jugée.
	const verdict = o.querySelector('#eni-verdict');
	verdict.textContent = '';
	verdict.className = 'eni-verdict';
	o.querySelector('#eni-voix').innerHTML = enigmeVoix(commentaires);
	o.querySelector('#eni-journal').innerHTML = enigmeJournal(vue);
}

// Bloc « Énigmes » de la sidebar de /play — MIROIR du markup Jinja de `#enigmes-ici-bloc`.
// `liste` = `enigmes.enigmes_du_lieu` ([{id, nom, resolue}]) ; vide ⇒ bloc vide.
function enigmesIciHtml(liste) {
	if (!Array.isArray(liste) || !liste.length) return '';
	return '<h3>Énigmes</h3><ul class="sub-locations-list" id="enigmes-ici">'
		+ liste.map(e => `<li><button class="sub-loc-btn" data-enigme="${_eniEsc(e.id)}" `
			+ `onclick="ouvrirEnigme(this.dataset.enigme)">${e.resolue ? '✓' : '🔍'} ${_eniEsc(e.nom)}</button></li>`).join('')
		+ '</ul>';
}

function _majEnigmesIci(liste) {
	const bloc = document.getElementById('enigmes-ici-bloc');
	if (bloc) bloc.innerHTML = enigmesIciHtml(liste);
}

async function ouvrirEnigme(id) {
	try {
		const res = await fetch('api/enigme?id=' + encodeURIComponent(id));
		const data = await res.json();
		if (!res.ok) { if (typeof showToast === 'function') showToast(data.detail || 'Énigme indisponible.'); return; }
		_enigme = { vue: data.enigme, brouillon: enigmeBrouillonInitial(data.enigme), outil: 'cle', selection: {} };
		_eniRendre('', data.commentaires);
		_eniPanneau().hidden = false;
	} catch (err) { console.error('Erreur ouverture énigme', err); }
}

function fermerEnigme() {
	const o = document.getElementById('enigme-overlay');
	if (o) o.hidden = true;
	const resolue = !!(_enigme && _enigme.resolue_ici);
	_enigme = null;
	// Dialogue resté ouvert dessous : ses choix (`enigme_resolue`) ont pu changer — on lui
	// reparle, comme le joueur cliquerait de nouveau sur 🗣.
	const panneau = document.getElementById('pnj-panel');
	if (resolue && panneau && !panneau.classList.contains('panel-hidden')
		&& typeof openPnjDialogue === 'function' && typeof _pnjCourant !== 'undefined') {
		const btn = Array.from(document.querySelectorAll('.pnj-talk-btn')).find(b => b.dataset.pnj === _pnjCourant);
		openPnjDialogue(btn || { dataset: { pnj: _pnjCourant } });
	}
}

// Rejoue une animation CSS même si la classe est déjà posée (essais faux enchaînés).
function _eniRejouer(el, cls) {
	if (!el) return;
	el.classList.remove(cls);
	void el.offsetWidth;
	el.classList.add(cls);
}

// Verdict visible d'un essai jugé par le serveur : ✗ + total des essais faux (`vue.echecs`),
// secousse des commandes ; ✓ + lueur à la réussite.
function _eniVerdict(echec, n) {
	const o = _eniPanneau();
	const verdict = o.querySelector('#eni-verdict');
	const corps = o.querySelector('#eni-corps');
	verdict.textContent = echec ? `✗ Tentative ${n} : échec` : '✓ Réussi !';
	verdict.className = 'eni-verdict ' + (echec ? 'eni-echec' : 'eni-succes');
	_eniRejouer(verdict, 'eni-joue');
	corps.classList.remove('eni-corps-secoue', 'eni-corps-brille');
	_eniRejouer(corps, echec ? 'eni-corps-secoue' : 'eni-corps-brille');
}

async function _eniEnvoyer(action, extra) {
	if (!_enigme) return;
	// Prise en compte immédiate : le bouton s'occupe le temps de la réponse (re-rendu ensuite).
	const bouton = action === 'essayer' ? _eniPanneau().querySelector('[data-eni-essayer]') : null;
	if (bouton) { bouton.disabled = true; bouton.classList.add('eni-envoi'); bouton.textContent = 'Essai…'; }
	try {
		const res = await fetch('api/enigme/action', {
			method: 'POST', headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(Object.assign({ id: _enigme.vue.id, action }, extra || {})),
		});
		const data = await res.json();
		if (!res.ok) {
			if (bouton) { bouton.disabled = false; bouton.classList.remove('eni-envoi'); bouton.textContent = 'Essayer'; }
			if (typeof showToast === 'function') showToast(data.detail || 'Erreur.');
			return;
		}
		const garde = _enigme;
		const r = data.resultat || {};
		const evts = r.evenements || [];
		const echec = evts.includes('echec');
		_enigme = { vue: data.enigme, brouillon: enigmeBrouillonInitial(data.enigme),
			outil: garde.outil, selection: {},
			resolue_ici: garde.resolue_ici || (r.resolue && Array.isArray(data.links)) };
		_eniRendre(r.resolue ? '' : (r.texte || ''), data.commentaires);
		// Total des essais faux tenu par le SERVEUR (`vue.echecs`), toutes ouvertures confondues.
		if (echec) _eniVerdict(true, (data.enigme || {}).echecs || 0);
		else if (evts.includes('reussite')) _eniVerdict(false);
		// Onglet 📖 : les notes 🧩 de la quête viennent de bouger (convention 10).
		if (data.journal && typeof renderFicheJournal === 'function') renderFicheJournal(data.journal);
		// Résolution : portes, énigmes à bouton (✓), lignes 🗣 — servis SEULEMENT à la
		// première résolution (routers/enigmes.py), absents sinon.
		if (typeof _appliquerResyncLieu === 'function') _appliquerResyncLieu(data);
		// XP de résolution (10 du premier coup, 5 du deuxième) : fiche resynchronisée.
		if (data.fiche && typeof _appliquerFiche === 'function') _appliquerFiche(data.fiche);
		if (data.xp && data.xp.xp_gain && typeof showToast === 'function') {
			showToast(`+${data.xp.xp_gain} XP` + (data.xp.niveau_up ? ` — niveau ${data.xp.niveau_apres} !` : ''));
		}
	} catch (err) {
		console.error('Erreur action énigme', err);
		if (bouton && bouton.isConnected) { bouton.disabled = false; bouton.classList.remove('eni-envoi'); bouton.textContent = 'Essayer'; }
	}
}

function _eniClic(ev) {
	if (!_enigme) return;
	const vue = _enigme.vue;
	const t = ev.target.closest('[data-eni-cle],[data-eni-conclure],[data-eni-cran],[data-eni-essayer],'
		+ '[data-eni-recommencer],[data-eni-assoc],[data-eni-outil],[data-eni-lien],[data-eni-noeud],[data-eni-zone]');
	if (!t) return;
	const d = t.dataset;
	if (d.eniZone !== undefined) return _eniZone(d.eniZone);
	if (d.eniCle !== undefined) return _eniEnvoyer(vue.famille === 'deduction' ? 'examiner' : 'passer', { cle: d.eniCle });
	if (d.eniConclure !== undefined) return _eniEnvoyer('conclure', { cle: d.eniConclure });
	if (d.eniRecommencer !== undefined) return _eniEnvoyer('recommencer');
	if (d.eniCran !== undefined) return _eniTourner(d.eniCran, +d.eniPas || 1);
	if (d.eniEssayer !== undefined) return _eniEssayer();
	if (d.eniAssoc !== undefined) return _eniAssocier(d.eniAssoc, d.eniId);
	if (d.eniOutil !== undefined) { _enigme.outil = d.eniOutil; return _eniRendre(); }
	if (d.eniLien !== undefined) return _eniLien(d.eniLien);
	if (d.eniNoeud !== undefined && _enigme.outil === 'miroir') return _eniEnvoyer('reveler', { cle: d.eniNoeud });
}

function _eniTourner(id, pas) {
	const p = ((_enigme.vue.elements || {}).pieces || []).find(x => x.id === id);
	if (!p) return;
	const n = Math.max(+p.crans || 1, 1);
	const v = ((_enigme.brouillon.positions[id] || 0) + pas + n) % n;
	_enigme.brouillon.positions[id] = v;
	_eniRendre();
}

function _eniEssayer() {
	const f = _enigme.vue.famille, b = _enigme.brouillon;
	if (f === 'crans') return _eniEnvoyer('essayer', { positions: b.positions });
	if (f === 'placement') return _eniEnvoyer('essayer', { placement: b.placement });
	if (f === 'reseau') return _eniEnvoyer('essayer', { actives: b.actives, ancrees: b.ancrees });
}

function _eniAssocier(cote, id) {
	const s = _enigme.selection;
	s[cote] = id;
	if (s.gauche && s.droite) return _eniEnvoyer('associer', { gauche: s.gauche, droite: s.droite });
	_eniRendre();
}

function _eniLien(id) {
	const b = _enigme.brouillon;
	if (_enigme.outil === 'pierre') {
		if (!b.actives.includes(id)) return;   // la pierre ancre une liaison OUVERTE
		b.ancrees = b.ancrees.includes(id) ? b.ancrees.filter(x => x !== id) : b.ancrees.concat(id);
	} else if (_enigme.outil === 'cle') {
		if (b.actives.includes(id)) {
			b.actives = b.actives.filter(x => x !== id);
			b.ancrees = b.ancrees.filter(x => x !== id);
		} else b.actives = b.actives.concat(id);
	}
	_eniRendre();
}

// Une zone de l'image désigne un élément de l'énigme : même effet que sa commande.
function _eniZone(cle) {
	const vue = _enigme.vue, el = vue.elements || {};
	const a = (liste) => (liste || []).some(x => x.id === cle);
	if (vue.famille === 'deduction') return _eniEnvoyer(a(el.conclusions) ? 'conclure' : 'examiner', { cle });
	if (vue.famille === 'graphe') return _eniEnvoyer('passer', { cle });
	if (vue.famille === 'crans') return _eniTourner(cle, 1);
	if (vue.famille === 'reseau' && _enigme.outil === 'miroir') return _eniEnvoyer('reveler', { cle });
	if (vue.famille === 'placement') {
		const syms = (el.symboles || []).map(s => s.id);
		const i = syms.indexOf(_enigme.brouillon.placement[cle]);
		const suivant = syms[(i + 1) % (syms.length + 1)];
		if (suivant) _enigme.brouillon.placement[cle] = suivant; else delete _enigme.brouillon.placement[cle];
		return _eniRendre();
	}
}
