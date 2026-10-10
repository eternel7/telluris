// Texte d'une capacité CONNUE (sort ou compétence) — libellés de l'onglet ⚡ de /play,
// partagés avec les catalogues /admin/sorts et /admin/competences : un même sort se lit
// donc mot pour mot pareil des deux côtés.
//
// Contrat de l'hôte :
// - `libelleZone` / `normaliserZone` (scripts/zones_effet.js) chargés AVANT ;
// - `_coutPmCharge(capa)` défini (coût sous la charge portée — /play le calcule, un
//   catalogue sans porteur renvoie la base) ;
// - `CAPA_FORMULES_SEULES` (facultatif, défaut faux) : sans personnage, une formule à
//   caractéristiques n'a pas de valeur — vrai ⇒ « 1D{Int/5} » au lieu de « 1D{Int/5} → 1D8 ».
//   Les champs de temps / portée formulés arrivent alors en CHAÎNE (la formule elle-même).

function _formulesSeules() {
	return typeof CAPA_FORMULES_SEULES !== 'undefined' && !!CAPA_FORMULES_SEULES;
}

// « 8 PM » à vide, « 8 → 11 PM » sous la charge : le joueur voit la facture AVANT de cliquer.
function _pmLabel(capa) {
	const base = +(capa && capa.cout_pm) || 0;
	const eff = _coutPmCharge(capa);
	if (eff <= base) return `${base} PM`;
	return `${base} <span class="sh-sort-pm-charge">→ ${eff}</span> PM`;
}

// Régén SIGNÉE : négative = POISON (perte par tour) — « ☠ −n PV/tour », jamais « +-n ».
function regenTexte(v, unite) {
	return v < 0 ? `☠ −${-v} ${unite}/tour` : `+${v} ${unite}/tour`;
}

// `prefixeDegats` : '+' pour une compétence de corps à corps, dont les dés S'AJOUTENT à ceux
// de l'arme (cf. combat._degats_competence). Sans lui le joueur lirait le bonus comme un total.
// Formule à caractéristiques d'ORIGINE (`1D{Int/5}`) devant sa valeur RÉSOLUE par le
// serveur pour ce personnage (`effets.formules_texte`, cf. sorts.apercu_effets) — le client
// ne calcule rien. Sans formule, la valeur seule.
function _fx(e, cle, val) {
	const f = ((e && e.formules_texte) || {})[cle];
	if (!f) return `${val}`;
	if (!_formulesSeules()) return `${f} → ${val}`;
	// Un buff s'écrit signé (« +4 R ») : la formule seule garde le signe de sa valeur.
	return String(val).startsWith('+') && !/^[+-]/.test(f) ? `+${f}` : `${f}`;
}
// Régén : la formule suit la valeur entre parenthèses ; sans personnage, elle la remplace.
function _regenFx(e, cle, unite) {
	const f = ((e && e.formules_texte) || {})[cle];
	if (f && _formulesSeules()) return `${e[cle] < 0 ? '☠ ' : '+'}${f} ${unite}/tour`;
	return regenTexte(e[cle], unite) + (f ? ` (${f})` : '');
}
function _sortEffetsLabel(e, prefixeDegats) {
	if (!e) return '';
	const parts = [];
	if (e.degats) parts.push(`${prefixeDegats || ''}${_fx(e, 'degats', e.degats)} dég.`);
	if (e.soin) parts.push(`soin ${_fx(e, 'soin', e.soin)} PV`);
	if (e.pv) parts.push(`+${_fx(e, 'pv', e.pv)} PV`);
	if (e.pm) parts.push(`+${_fx(e, 'pm', e.pm)} PM`);
	// Partage de soin : la part des PV rendus aux AUTRES qui revient au lanceur.
	if (e.partage_soin) parts.push(`↺ ${_fx(e, 'partage_soin', e.partage_soin)} % au lanceur`);
	for (const [k, v] of Object.entries(e.buffs || {})) parts.push(`${_fx(e, 'buffs.' + k, (v > 0 ? '+' : '') + v)} ${k}`);
	if (e.regen_pv) parts.push(_regenFx(e, 'regen_pv', 'PV'));
	if (e.regen_pm) parts.push(_regenFx(e, 'regen_pm', 'PM'));
	if (e.esquive) parts.push(`esquive +${_fx(e, 'esquive', e.esquive)}`);
	if (e.furtivite) parts.push(`🥷 furtivité`);
	// Les six clés d'effet du « temps magique ». ⚠️ Sans elles, un sort de drain ou de saut
	// s'afficherait sans le moindre effet annoncé — même défaut que les invocations avant
	// `_invocationLabel`, et le TACTILE n'a pas de survol pour compenser.
	if (e.degats_pm) parts.push(`${_fx(e, 'degats_pm', e.degats_pm)} dég. aux PM`);
	if (e.cout_pv) parts.push(`🩸 −${_fx(e, 'cout_pv', e.cout_pv)} PV`);
	if (e.drain_pv) parts.push(`🧛 drain ${e.drain_pv} % en PV`);
	if (e.drain_pm) parts.push(`🧛 drain ${e.drain_pm} % en PM`);
	if (e.saut) parts.push(`💨 saut ${_fx(e, 'saut', e.saut)} cases`);
	if (e.provocation) parts.push('📢 provocation');
	if (e.echange) parts.push('🔄 échange de place');
	if (e.vol) parts.push('🪽 vol (eau, falaises)');
	if (e.lien_vie) {
		parts.push(`🔗 lien de vie ${_fx(e, 'lien_vie.part', e.lien_vie.part)} %`
			+ (e.lien_vie.reduction ? ` (−${e.lien_vie.reduction} % absorbés)` : ''));
	}
	// Renforts de composant d'une invocation ou d'un sort maintenu (cf. sorts.doc_effectif).
	if (e.invocation_nombre) parts.push(`🐾 +${e.invocation_nombre} créature${e.invocation_nombre > 1 ? 's' : ''}`);
	if (e.invocation_duree) parts.push(`🐾 +${e.invocation_duree} tour${e.invocation_duree > 1 ? 's' : ''} d'invocation`);
	if (e.maintien_reduction) parts.push(`🔄 −${e.maintien_reduction} PM/round d'entretien`);
	if (e.duree) parts.push(`${_fx(e, 'duree', e.duree)} tours`);
	return parts.join(', ');
}

// Étiquette des autres notions de coût, à côté des PM de lancement : le temps
// d'incantation (PA, sorts uniquement) et l'entretien par round. Vide pour une capacité
// ordinaire — l'écrasante majorité —, donc le catalogue ne s'alourdit que là où il y a
// quelque chose à dire. ⚠️ Le tactile n'a pas de survol : ce libellé est le SEUL canal.
// Une valeur en CHAÎNE est une formule non résolue (catalogue sans personnage).
function _sortTempsLabel(s) {
	const parts = [];
	if (typeof s.incantation === 'string' || (s.incantation || 1) > 1) parts.push(`⏱ ${s.incantation} PA`);
	if (s.maintien) {
		// Même traitement que le coût de lancement : la charge renchérit aussi l'entretien,
		// et c'est là qu'elle se sent le plus (on le paie à CHAQUE round).
		const eff = _coutPmCharge({cout_pm: s.maintien, sensibilite_charge: s.sensibilite_charge});
		parts.push(eff > s.maintien
			? `🔄 ${s.maintien} <span class="sh-sort-pm-charge">→ ${eff}</span> PM/round`
			: `🔄 ${s.maintien} PM/round`);
	}
	return parts.length ? ` · ${parts.join(' · ')}` : '';
}
// Étiquette de ZONE D'EFFET d'un sort ou d'une compétence, préfixée pour s'accrocher à la
// ligne d'effets. Vide quand il n'y en a pas : hors combat il n'y a pas de grille, donc
// rien à dessiner — le catalogue se contente d'annoncer la forme. `libelleZone` vient de
// scripts/zones_effet.js.
function _zoneLabel(capa) {
	// Une passive à zone est une AURA, toujours ancrée sur son porteur (`cible` ignorée).
	const aura = (capa || {}).mode === 'passive';
	const txt = libelleZone(normaliserZone((capa || {}).zone), aura ? 'soi' : (capa || {}).cible);
	return txt ? ' · ' + (aura ? 'aura ' : '') + txt : '';
}
// Étiquette d'un sort d'INVOCATION. Elle REMPLACE `_sortEffetsLabel` plutôt que de s'y
// ajouter : une invocation n'a aucun `effets` (elle fait apparaître une créature, elle ne
// pose rien sur personne), sa ligne de description resterait vide.
// ⚠️ Sort MAINTENU : la créature ne décompte pas ses tours, l'entretien la tient (cf.
// `combat._enregistrer_concentration`) — sa `duree` est inerte, l'annoncer serait faux.
function _invocationLabel(s) {
	const inv = s && s.invocation;
	if (!inv) return '';
	return `🐾 invoque ${inv.nombre > 1 ? inv.nombre + ' créatures' : 'une créature'}`
		+ (s.maintien ? ' tant que vous l\'entretenez' : ` pendant ${inv.duree} tours`);
}

// Portée d'un sort, pour la fiche dépliée des DEUX listes (connus + à apprendre).
// ⚠️ Rien pour `cible:"soi"` : se viser soi-même n'a pas de distance — même règle que
// `compLabel` (combat_telluris.html), un seul critère dans tout le jeu.
// ⚠️ `Math.max(1, …)` comme le moteur (`sort_portee`, utils/combat.py) : le champ `portee` est
// ABSENT sur les sorts `cible:"soi"` et vaut alors 0 — un « portée 0 » affiché serait faux.
// ⚠️ Pour un SORT, portée déclarée == portée EFFECTIVE : contrairement à une compétence
// `jet:"cc"` à dés, un sort n'emprunte JAMAIS l'allonge de l'arme en main
// (`combat._portee_competence` ne vise que les compétences). Ne pas « harmoniser » vers
// `capaPortee`, qui n'existe qu'en combat et ajouterait une allonge qui ne s'applique pas ici.
function _sortPorteeTexte(s) {
	if (!s || s.cible === 'soi') return '';
	if (typeof s.portee === 'string') return `📏 Portée : ${s.portee} cases`;   // formule
	const p = Math.max(1, s.portee || 1);
	return p > 1 ? `📏 Portée : ${p} cases` : '📏 Portée : au contact (1 case)';
}

// ── Lignes d'une capacité CONNUE (onglet ⚡) ─────────────────────────────────
// Ligne d'effets d'un sort connu, sous son nom.
function _sortLigneDesc(s) {
	return `${_invocationLabel(s) || _sortEffetsLabel(s.effets)}${_sortTempsLabel(s)}`
		+ `${s.cible === 'ennemi' ? ' · portée ' + s.portee : ''}${_zoneLabel(s)}`
		+ `${s.cible === 'allie' ? ' · 🤝 sur un allié' : ''}`;
}
// Pastilles des composants d'un sort connu (`.sh-sort-compo`, grisée si indisponible).
function _sortComposHtml(s) {
	return (s.composants || []).map(c =>
		`<span class="sh-sort-compo${c.disponible ? '' : ' off'}" title="${c.consomme ? 'Consommé au lancement' : 'Catalyseur (non consommé, il suffit de le porter)'}">${c.consomme ? '⚗️' : '💎'} ${c.icon || ''} ${c.nom}${_sortEffetsLabel(c.bonus) ? ' → ' + _sortEffetsLabel(c.bonus) : ''}</span>`
	).join('');
}
// Frappe martiale : ses dés s'ajoutent à ceux de l'arme équipée — de mêlée en `cc`,
// arc ou arme de lancer en `cd` (cf. combat._profil_emprunte).
function _compArme(c) {
	return !!(c.mode === 'active' && c.cible === 'ennemi' && (c.jet === 'cc' || c.jet === 'cd')
		&& c.effets && c.effets.degats);
}
function _compArmeTitre(c) {
	return !_compArme(c) ? ''
		: c.jet === 'cd' ? ' title="Ces dés s\'ajoutent aux dégâts de votre arc ou arme de lancer"'
		: ' title="Ces dés s\'ajoutent aux dégâts de votre arme"';
}
// Type de JET d'une compétence offensive (`cc` / `cd` / `magique`, cf. combat._resoudre_toucher) :
// deux compétences aux mêmes dés peuvent se résoudre tout autrement — défense opposée,
// armure, arme empruntée. Vide pour une passive ou une compétence d'entraide, sans jet.
const COMP_JETS = {
	cc: ['⚔️ jet de corps à corps', 'Contre l\'Agilité et l\'esquive de la cible ; son armure réduit les dégâts'],
	cd: ['🏹 jet à distance', 'Contre l\'Agilité et l\'esquive de la cible ; son armure réduit les dégâts'],
	magique: ['🔮 jet magique', 'Contre la défense magique de la cible ; l\'armure ne compte pas'],
};
function _compJetLabel(c) {
	if (!c || c.mode !== 'active' || c.cible !== 'ennemi') return '';
	const j = COMP_JETS[c.jet];
	return j ? ` · <span title="${j[1]}">${j[0]}</span>` : '';
}
// Ligne d'effets d'une compétence connue, sous sa description.
function _compLigneDesc(c) {
	let portee = '';
	if (c.mode === 'active' && c.cible === 'ennemi') portee = ` · portée ${c.portee}`;
	else if (c.mode === 'active' && c.cible === 'allie') portee = ' · 🤝 sur un allié';
	return `${_sortEffetsLabel(c.effets, _compArme(c) ? '+' : '')}${_sortTempsLabel(c)}${portee}${_zoneLabel(c)}`;
}
