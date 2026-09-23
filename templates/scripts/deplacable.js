// ── Panneaux flottants déplaçables ─────────────────────────────────────────
// Brique partagée par les mini-outils et le pavé du test de déplacement de l'éditeur, et
// par le pavé flottant de play_town : tous flottent au-dessus de la carte et finissent par
// recouvrir la case qu'on veut voir.
//
// ⚠️ La position de départ vient du CSS et n'est PAS ancrée au même coin selon le
// panneau (`top/right` pour les mini-outils, `bottom/right` pour les pavés). Au
// premier glisser on repasse donc tout en `top/left` et on remet les autres ancres à
// `auto` : deux contraintes opposées sur le même axe se battraient et le panneau
// s'étirerait au lieu de se déplacer.
// ⚠️ `transform` est remis à `none` : la règle mobile de part-move-panel centre le pavé
// par `translateX(-50%)`, qui le décalerait d'une demi-largeur sous le pointeur.
// ⚠️ Un `pointerdown` sur un BOUTON de la poignée (le ✕ du pavé de test) n'amorce aucun
// glisser — la capture de pointeur détournerait le clic censé fermer le mode.
// `onFin(pos)` (optionnel) reçoit `{ left, top }` au lâcher d'un glisser — play_town y
// mémorise la position.
function rendreDeplacable(el, poignee, onFin) {
	if (!el || !poignee) return;
	let drag = null;   // { dx, dy } écart pointeur → coin haut-gauche
	poignee.addEventListener('pointerdown', e => {
		if (e.target && e.target.closest && e.target.closest('button')) return;
		const r = el.getBoundingClientRect();
		drag = { dx: e.clientX - r.left, dy: e.clientY - r.top };
		placerPanneau(el, r.left, r.top);
		poignee.setPointerCapture(e.pointerId);
		e.preventDefault();
	});
	poignee.addEventListener('pointermove', e => {
		if (!drag) return;
		placerPanneau(el, e.clientX - drag.dx, e.clientY - drag.dy);
	});
	poignee.addEventListener('pointerup', () => {
		if (drag && typeof onFin === 'function') {
			onFin({ left: parseFloat(el.style.left) || 0, top: parseFloat(el.style.top) || 0 });
		}
		drag = null;
	});
	poignee.addEventListener('pointercancel', () => { drag = null; });
}

// Pose le panneau en `top/left` (ancres opposées et `transform` neutralisés, cf. ci-dessus),
// BORNÉ à la fenêtre : lâché hors écran, la poignée deviendrait inatteignable. Sert aussi à
// restaurer une position mémorisée, et à re-borner après un redimensionnement.
function placerPanneau(el, left, top) {
	const maxX = Math.max(0, window.innerWidth  - el.offsetWidth);
	const maxY = Math.max(0, window.innerHeight - el.offsetHeight);
	el.style.right = 'auto';
	el.style.bottom = 'auto';
	el.style.transform = 'none';
	el.style.left = Math.max(0, Math.min(maxX, left)) + 'px';
	el.style.top  = Math.max(0, Math.min(maxY, top)) + 'px';
}
