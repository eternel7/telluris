// templates/scripts/transmettre.js — menu « ⇄ Transmettre » de /play (routers/transmission.py).
//
// Un objet que le groupe a en main — sac d'un porteur (vous, compagnon, monture, guide),
// contenant porté, sol du lieu — passe à n'importe quel autre emplacement du groupe, sol
// compris, en UN geste : un menu contextuel posé à l'endroit du clic. Remplace « Poser »,
// le 🤝 du sol (et son calque centré), le ⬇ des contenants ; s'ajoute aux sacs du panneau 👥
// et à la colonne de gauche des rangements (coffre d'une propriété, implantation).
//
// Adresse d'un emplacement (même forme que le corps de POST api/transmettre) :
//   { sol: true } | { porteur_id } | { porteur_id, contenant_index, contenant_item_id }
//
// Le client ne fait que griser ce que le serveur refuserait (charge, place, contenant dans un
// contenant) ; le serveur tranche. Dépendances de /play : escapeHtml, showToast, _actionBody,
// _assurerGroupe, _grpEtat, _applyInventoryPayload, _appliquerFiche, et les rafraîchissements
// facultatifs (renderGroupeInventaire, _majPiedMonture, ouvrirContenant, _pcfAppliquer, _aubFetch).

// ── Pur ─────────────────────────────────────────────────────────────────────────

// Deux adresses désignent-elles le même tas ?
function trmMemeEmplacement(a, b) {
	if (!a || !b) return false;
	if (a.sol || b.sol) return !!a.sol && !!b.sol;
	if (a.porteur_id !== b.porteur_id) return false;
	const ca = a.contenant_index != null, cb = b.contenant_index != null;
	if (ca !== cb) return false;
	return !ca || (+a.contenant_index === +b.contenant_index && a.contenant_item_id === b.contenant_item_id);
}

// Où l'objet peut aller : tout le groupe porteur, ses contenants, puis le sol — SAUF son
// emplacement actuel. `grp` = payload de GET api/groupe. Un emplacement qui refuserait reste
// listé, grisé, avec sa raison : on voit pourquoi.
function destinationsTransmettre(grp, source, item) {
	const d = grp || {};
	const sacs = d.sacs || {};
	const poids = +((item && item.poids) || 0);
	const nomDe = c => `${c.prenom || ''} ${c.nom || ''}`.trim() || '?';
	const out = [];
	const porteur = (c, icon, sac) => {
		if (!c || !c.id || !sac) return;
		const cible = { porteur_id: c.id };
		if (trmMemeEmplacement(source, cible)) return;
		const libre = +(sac.charge_max || 0) - +(sac.charge || 0);
		const rentre = poids <= libre + 1e-6;
		out.push({ cle: c.id, icon, nom: nomDe(c), libre, rentre, raison: rentre ? '' : 'trop lourd', cible });
	};
	porteur(d.principal, '👤', d.principal);
	(d.groupe || []).forEach(c => porteur(c, '🧑‍🤝‍🧑', sacs[c.id]));
	(d.montures || []).forEach(m => porteur(m, '🐴', sacs[m.id]));
	if (d.guide) porteur(d.guide, '🧭', sacs[d.guide.id]);
	// Contenants : l'objet y est rangé et ne pèse rien pour son porteur. `libre` null = marée
	// basse, place inconnue : le serveur tranche. Jamais un contenant dans un autre.
	(d.contenants || []).forEach(c => {
		const cible = { porteur_id: c.porteur_id, contenant_index: c.index, contenant_item_id: c.item_id };
		if (trmMemeEmplacement(source, cible)) return;
		const libre = c.libre == null ? null : +c.libre;
		const emboite = !!(item && item.contenant);
		const rentre = !emboite && (libre == null || poids <= libre + 1e-6);
		out.push({ cle: c.cle, icon: c.icon || '👜', nom: `${c.nom || 'Contenant'} (${c.porteur_nom || '?'})`,
			libre, rentre, raison: emboite ? 'pas un contenant dans un autre' : rentre ? '' : 'plein', cible });
	});
	if (!(source && source.sol)) out.push({ cle: 'sol', icon: '⬇️', nom: 'Au sol', libre: null, rentre: true,
		raison: '', sol: true, cible: { sol: true } });
	return out;
}

// Texte de place d'une destination.
function trmPlaceTexte(dst) {
	if (dst.sol) return 'perdu si vous partez';
	if (dst.libre == null) return 'place inconnue (marée basse)';
	return `${Math.max(0, dst.libre).toFixed(1)} kg libres`;
}

// Bouton qui ouvre le menu. Adresse et objet en data-* (Conventions §9) — jamais dans l'onclick.
// `opts.compact` : icône seule (lignes serrées des panneaux à deux colonnes).
function transmettreBtn(source, index, item, opts) {
	const o = opts || {};
	const cls = o.classe || (o.compact ? 'grp-move-btn trm-btn' : 'sh-drop-btn trm-btn');
	const iid = (item && (item._id || item.item || item.item_id)) || '';
	return `<button type="button" class="${cls}" title="Transmettre à…" aria-haspopup="menu"
		data-trm-src="${escapeHtml(JSON.stringify(source))}" data-idx="${+index}" data-item="${escapeHtml(iid)}"
		data-poids="${+((item && item.poids) || 0)}" data-ctn="${item && item.contenant ? 1 : ''}"
		data-nom="${escapeHtml((item && item.nom) || '')}" data-icon="${escapeHtml((item && item.icon) || '📦')}"
		onclick="ouvrirTransmettre(event, this)">${o.compact ? '⇄' : '⇄ Transmettre'}</button>`;
}

// Position du menu : au point du clic, ramené dans la fenêtre (retourné au-dessus s'il
// déborde en bas, collé au bord droit s'il déborde à droite). Pur : mesures injectées.
function trmPosition(x, y, w, h, vw, vh) {
	const marge = 8;
	let left = x, top = y;
	if (left + w > vw - marge) left = Math.max(marge, vw - w - marge);
	if (top + h > vh - marge) top = y - h >= marge ? y - h : Math.max(marge, vh - h - marge);
	return { left: Math.max(marge, left), top: Math.max(marge, top) };
}

// ── Menu ────────────────────────────────────────────────────────────────────────

let _trm = null;   // { el, btn, source, index, itemId, item, x, y, dests }

function fermerTransmettre() {
	if (!_trm) return;
	_trm.el.remove();
	document.removeEventListener('mousedown', _trmDehors, true);
	document.removeEventListener('touchstart', _trmDehors, true);
	document.removeEventListener('keydown', _trmClavier, true);
	window.removeEventListener('resize', fermerTransmettre);
	window.removeEventListener('scroll', _trmDefile, true);
	_trm = null;
}
// Clic hors du menu = ANNULER sans rien engager (Conventions §8). Le bouton d'origine se
// referme par son propre clic (bascule dans `ouvrirTransmettre`).
function _trmDehors(ev) {
	if (!_trm || _trm.el.contains(ev.target) || _trm.btn.contains(ev.target)) return;
	fermerTransmettre();
}
function _trmClavier(ev) {
	if (ev.key === 'Escape') { ev.stopPropagation(); ev.preventDefault(); fermerTransmettre(); }
}
function _trmDefile(ev) { if (_trm && !_trm.el.contains(ev.target)) fermerTransmettre(); }

async function ouvrirTransmettre(ev, btn) {
	if (ev) ev.stopPropagation();
	if (_trm && _trm.btn === btn) { fermerTransmettre(); return; }
	fermerTransmettre();
	let source;
	try { source = JSON.parse(btn.dataset.trmSrc || '{}'); } catch (e) { return; }
	// Clavier (Entrée/Espace) : pas de coordonnées de clic → sous le bouton.
	const r = btn.getBoundingClientRect();
	const auClic = ev && (ev.clientX || ev.clientY);
	const el = document.createElement('div');
	el.className = 'trm-menu';
	el.setAttribute('role', 'menu');
	document.body.appendChild(el);
	_trm = {
		el, btn, source, index: +btn.dataset.idx, itemId: btn.dataset.item,
		item: { poids: +btn.dataset.poids || 0, contenant: !!btn.dataset.ctn, nom: btn.dataset.nom, icon: btn.dataset.icon },
		x: auClic ? ev.clientX : r.left, y: auClic ? ev.clientY : r.bottom, dests: null,
	};
	document.addEventListener('mousedown', _trmDehors, true);
	document.addEventListener('touchstart', _trmDehors, true);
	document.addEventListener('keydown', _trmClavier, true);
	window.addEventListener('resize', fermerTransmettre);
	window.addEventListener('scroll', _trmDefile, true);
	const moi = _trm;
	// Tout de suite avec le groupe en mémoire, puis avec les charges RELUES (un ramassage ou
	// un achat depuis le dernier chargement les a peut-être changées).
	if (typeof _grpEtat !== 'undefined' && _grpEtat) _trmRendre();
	else _trmRendre(true);
	_grpEtat = null;
	await _assurerGroupe();
	if (_trm === moi) _trmRendre();
}

function _trmRendre(chargement) {
	const st = _trm;
	if (!st) return;
	st.dests = chargement ? [] : destinationsTransmettre(_grpEtat, st.source, st.item);
	const titre = `<div class="trm-titre">${escapeHtml(st.item.icon || '📦')} ${escapeHtml(st.item.nom || '—')}`
		+ ` <span class="trm-poids">${(+st.item.poids || 0).toFixed(1)} kg</span></div>`;
	const lignes = chargement ? '<div class="trm-vide">…</div>'
		: st.dests.map((dst, i) => `${dst.sol ? '<div class="trm-sep"></div>' : ''}<button type="button" role="menuitem"
			class="trm-item" ${dst.rentre ? '' : 'disabled'} onclick="_trmChoisir(${i})">
			<span class="trm-icone">${escapeHtml(dst.icon)}</span><span class="trm-nom">${escapeHtml(dst.nom)}</span>
			<span class="trm-place${dst.rentre ? '' : ' trm-refus'}">${dst.rentre ? trmPlaceTexte(dst) : escapeHtml(dst.raison)}</span>
		</button>`).join('');
	st.el.innerHTML = titre + (lignes || '<div class="trm-vide">Personne d\'autre ne peut le prendre.</div>');
	const p = trmPosition(st.x, st.y, st.el.offsetWidth, st.el.offsetHeight, window.innerWidth, window.innerHeight);
	st.el.style.left = p.left + 'px';
	st.el.style.top = p.top + 'px';
	const premier = st.el.querySelector('.trm-item:not([disabled])');
	if (premier && !chargement) premier.focus({ preventScroll: true });
}

async function _trmChoisir(i) {
	const st = _trm;
	if (!st || !st.dests || !st.dests[i]) return;
	const dst = st.dests[i];
	fermerTransmettre();
	try {
		const res = await fetch('api/transmettre', {
			method: 'POST', headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(_actionBody({ source: st.source, cible: dst.cible, index: st.index, item_id: st.itemId })),
		});
		const data = await res.json();
		if (!res.ok) { showToast('Erreur : ' + data.detail); return; }
		// La fiche d'objet ouverte adressait l'ancien index : périmée.
		const fiche = document.getElementById('item-detail-overlay');
		if (fiche && !fiche.classList.contains('item-detail-hidden') && typeof closeItemDetail === 'function') closeItemDetail();
		_applyInventoryPayload(data);
		(data.fiches || []).forEach(f => _appliquerFiche(f));
		const t = data.transmis || {};
		showToast(`${t.icon || '📦'} ${t.nom || 'Objet'} → ${dst.nom}`);
		await _trmRafraichir();
	} catch (err) { console.error('Erreur transmission', err); }
}

// Après une transmission : tout panneau qui montre un sac du groupe est relu (Conventions §10).
async function _trmRafraichir() {
	_grpEtat = null;
	await _assurerGroupe();
	if (typeof renderGroupeInventaire === 'function') renderGroupeInventaire();
	if (_grpEtat && typeof _majPiedMonture === 'function') {
		[...(_grpEtat.montures || []), ...(_grpEtat.guide ? [_grpEtat.guide] : [])].forEach(m => _majPiedMonture(m));
	}
	const ctn = document.getElementById('contenant-overlay');
	if (ctn && !ctn.classList.contains('item-detail-hidden') && typeof _ctnEtat !== 'undefined' && _ctnEtat) {
		await ouvrirContenant(_ctnEtat.index, _ctnEtat.item_id);
	}
	const pcf = document.getElementById('prop-coffre-panel');
	if (pcf && !pcf.classList.contains('panel-hidden') && typeof _pcfEtat !== 'undefined' && _pcfEtat) {
		const d = await _aubFetch(_pcfEtat.colonie ? 'api/colonisation/rangements' : 'api/proprietes/coffre');
		if (d) _pcfAppliquer(d);
	}
}
