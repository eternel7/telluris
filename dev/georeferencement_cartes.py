"""Géoréférencement des cartes de pays (pur) : repères (lon, lat) ↔ case, calage de paires.

POURQUOI : `dev/calage_cartes.py` cale deux cartes voisines par des repères lus À LA MAIN sur
les DEUX images (même lieu vu deux fois). Les cartes d'Europe du Nord et de l'Est et d'Afrique
(02/11/2026) sont trop nombreuses (une cinquantaine de frontières) et partagent peu de repères
visibles des deux côtés. Chaque carte reçoit donc SES repères géographiques réels (`REPERES` :
nom → ((lon, lat), (x, y) en cases, lus sur l'image)), et la paire se cale en passant par la
géographie.

Les cartes dessinées DÉFORMENT la géographie (la Kola de la Laponie est démesurée, Kiev est au
nord du Pripiat…) : aucun ajustement global ne tient. Le passage (lon, lat) → case est donc
LOCAL (`vers_case`) : moindres carrés pondérés par la distance aux repères (gaussienne de
`SIGMA` degrés), lon → x et lat → y séparément. Une paire (`paire`) échantillonne la zone
commune des deux cartes (ou la bande entre elles quand elles ne se recouvrent pas), projette
chaque point sur les deux grilles, et rend des repères au format de `calage_cartes.PAIRES`
(px de la carte posée, px du fond) — `calage_cartes.ajuster` en tire la similitude, et tout
le reste (`frontieres_calees`, `superposer_cartes`) fonctionne tel quel.

Repères des cartes déjà calées (France, plaine, Italie, Pannonie, Roumanie, Égypte, Afrique du
Nord) : ceux de `calage_cartes.PAIRES` (px → case), complétés.
"""

import math

CASE_PX = 16
SIGMA = 2.5
POIDS_MIN = 0.02


def _px(x, y):
	return (x / CASE_PX, y / CASE_PX)


# lieu → {nom : ((lon, lat), (x, y) en cases)}
REPERES = {
	# ── Cartes déjà en jeu ──────────────────────────────────────────────────────────────
	"lieu:france": {
		"Lutecia": ((2.35, 48.85), _px(715, 212)),
		"embouchure de la Seine": ((0.2, 49.45), _px(560, 160)),
		"pas de Calais": ((1.5, 51.0), _px(660, 20)),
		"Ardenne": ((5.5, 50.0), _px(950, 190)),
		"Lyon": ((4.83, 45.76), (57.5, 28.5)),
		"lac Léman": ((6.5, 46.45), _px(1040, 395)),
		"lac Majeur": ((8.6, 45.95), _px(1215, 415)),
		"lac de Garde": ((10.7, 45.6), _px(1370, 455)),
		"golfe de Gênes": ((8.9, 44.4), _px(1240, 545)),
		"cap Corse": ((9.4, 43.0), _px(1285, 648)),
		"coin basque": ((-1.8, 43.35), _px(405, 628)),
		"cap de Creus": ((3.3, 42.3), _px(792, 700)),
		"Strasbourg": ((7.75, 48.58), (72, 12)),
	},
	"lieu:plaine_europeenne": {
		"embouchure de la Seine": ((0.2, 49.45), _px(148, 597)),
		"Lutecia": ((2.35, 48.85), _px(258, 705)),
		"pas de Calais": ((1.5, 51.0), _px(215, 550)),
		"Ardenne": ((5.5, 50.0), _px(500, 620)),
		"Amsterdam": ((4.9, 52.37), (27, 23)),
		"Hambourg": ((10.0, 53.55), (51, 20)),
		"Copenhague": ((12.57, 55.68), (58, 9)),
		"Berlin": ((13.4, 52.52), (63, 24)),
		"Stettin": ((14.55, 53.43), (69, 17)),
		"Skagen": ((10.6, 57.7), (47, 2)),
	},
	"lieu:espagne": {
		"coin basque": ((-1.8, 43.35), _px(845, 95)),
		"cap de Creus": ((3.3, 42.3), _px(1175, 180)),
		"golfe du Lion": ((3.0, 43.2), _px(1180, 105)),
		"Barcelone": ((2.17, 41.4), (65, 15)),
		"Tolède": ((-4.0, 39.86), (41, 26)),
		"Lisbonne": ((-9.1, 38.7), (16, 31)),
		"cap Saint-Vincent": ((-9.0, 37.0), (18, 40)),
		"cap de Gata": ((-2.2, 36.7), (49, 41)),
		"Gibraltar": ((-5.6, 36.0), (35, 45)),
		"Majorque": ((2.9, 39.6), (72, 27)),
	},
	"lieu:italie": {
		"Venise": ((12.33, 45.44), _px(735, 180)),
		"pointe de l'Istrie": ((13.85, 44.87), _px(858, 222)),
		"lac Balaton": ((17.7, 46.8), _px(1062, 112)),
		"bouches de Kotor": ((18.77, 42.42), _px(1082, 393)),
		"lac Léman": ((6.5, 46.45), _px(277, 95)),
		"lac Majeur": ((8.6, 45.95), _px(432, 180)),
		"lac de Garde": ((10.7, 45.6), _px(621, 168)),
		"golfe de Gênes": ((8.9, 44.4), _px(487, 262)),
		"cap Corse": ((9.4, 43.0), _px(527, 353)),
		"Rome": ((12.5, 41.9), (48, 26)),
		"Naples": ((14.25, 40.85), (55, 31)),
		"Otrante": ((18.5, 40.1), (75, 32)),
		"Marsala": ((12.4, 37.8), (46, 42)),
		"Sardaigne sud": ((9.0, 39.0), (30, 37)),
		"cap Bon": ((11.05, 37.1), (36, 47)),
	},
	"lieu:pannonie": {
		"Venise": ((12.33, 45.44), _px(235, 405)),
		"pointe de l'Istrie": ((13.85, 44.87), _px(358, 487)),
		"lac Balaton": ((17.7, 46.8), _px(660, 285)),
		"bouches de Kotor": ((18.77, 42.42), _px(785, 742)),
		"Portes de Fer": ((22.65, 44.63), _px(1075, 565)),
		"confluent de l'Olt": ((24.8, 43.73), _px(1190, 575)),
		"défilé de Turnu Roșu": ((24.3, 45.6), _px(1185, 415)),
		"Budapest": ((19.05, 47.5), (48, 15)),
		"Vienne": ((16.37, 48.2), (36, 11)),
	},
	"lieu:roumanie": {
		"Portes de Fer": ((22.65, 44.63), _px(410, 615)),
		"confluent de l'Olt": ((24.8, 43.73), _px(615, 700)),
		"défilé de Turnu Roșu": ((24.3, 45.6), _px(605, 430)),
		"Bucarest": ((26.1, 44.43), (51, 36)),
		"delta du Danube": ((29.5, 45.2), (80, 30)),
		"Cluj": ((23.6, 46.77), (33, 15)),
		"Suceava": ((26.25, 47.65), (62, 13)),
	},
	"lieu:egypte": {
		"Le Caire": ((31.24, 30.05), _px(800, 265)),
		"Siwa": ((25.5, 29.2), _px(205, 330)),
		"Nil à Louxor": ((32.64, 25.7), _px(988, 645)),
		"Port-Saïd": ((32.3, 31.26), _px(955, 150)),
		"tête du golfe de Suez": ((32.55, 29.95), _px(978, 268)),
	},
	"lieu:afrique_du_nord": {
		"Le Caire": ((31.24, 30.05), _px(1180, 265)),
		"Siwa": ((25.5, 29.2), _px(948, 315)),
		"Nil à Louxor": ((32.64, 25.7), _px(1225, 429)),
		"Abou Simbel": ((31.6, 22.34), (76, 32)),
		"Gibraltar": ((-5.6, 36.0), (19, 5)),
		"Hoggar": ((5.5, 23.3), (37, 28)),
		"Tibesti": ((18.5, 21.0), (53, 30)),
		"lac Tchad": ((14.0, 13.0), (49, 45)),
		"Cap-Vert": ((-17.4, 14.7), (2, 41)),
		"golfe de Syrte": ((18.5, 30.5), (52, 13)),
		"Tombouctou": ((-3.0, 16.8), (27, 42)),
	},
	# ── Europe du Nord et de l'Est ──────────────────────────────────────────────────────
	"lieu:scandinavie_meridionale": {
		"Trondheim": ((10.4, 63.4), (31, 4)),
		"Bergen": ((5.3, 60.4), (17, 19)),
		"Lindesnes": ((7.05, 58.0), (25, 29)),
		"Oslo": ((10.75, 59.9), (37, 22)),
		"Skagen": ((10.6, 57.7), (34, 33)),
		"Vänern": ((13.2, 58.9), (41, 26)),
		"Vättern": ((14.5, 58.3), (47, 30)),
		"Stockholm": ((18.07, 59.33), (57, 23)),
		"Gotland": ((18.5, 57.5), (59, 32)),
		"Åland": ((20.0, 60.2), (60, 22)),
		"Turku": ((22.3, 60.45), (66, 20)),
		"Vaasa": ((21.6, 63.1), (68, 4)),
		"Gävle": ((17.1, 60.7), (53, 15)),
		"Scanie": ((13.0, 55.4), (46, 42)),
	},
	"lieu:laponie": {
		"Lofoten": ((12.9, 67.9), (9, 20)),
		"Narvik": ((17.4, 68.4), (21, 23)),
		"Tromsø": ((18.9, 69.6), (24, 14)),
		"cap Nord": ((25.8, 71.1), (46, 10)),
		"Varanger": ((30.0, 69.7), (56, 15)),
		"Mourmansk": ((33.1, 69.0), (59, 18)),
		"Kola est": ((41.0, 67.2), (84, 22)),
		"Kandalaksha": ((32.4, 67.15), (61, 30)),
		"Belomorsk": ((34.8, 64.5), (70, 36)),
		"Tornio": ((24.2, 65.85), (34, 35)),
		"Luleå": ((22.1, 65.6), (29, 38)),
		"Oulu": ((25.5, 65.0), (37, 41)),
	},
	"lieu:germanie_du_sud": {
		"Francfort": ((8.68, 50.11), (20, 11)),
		"Strasbourg": ((7.75, 48.58), (11, 27)),
		"Bâle": ((7.59, 47.56), (10, 36)),
		"lac de Constance": ((9.4, 47.65), (25, 38)),
		"Munich": ((11.58, 48.14), (41, 32)),
		"Ratisbonne": ((12.1, 49.0), (45, 23)),
		"Passau": ((13.46, 48.57), (56, 29)),
		"Prague": ((14.42, 50.08), (64, 13)),
		"Vienne": ((16.37, 48.2), (77, 32)),
	},
	"lieu:baltique_orientale": {
		"Tallinn": ((24.75, 59.44), (40, 9)),
		"Riga": ((24.1, 56.95), (36, 23)),
		"Saaremaa": ((22.5, 58.4), (23, 12)),
		"Klaipėda": ((21.1, 55.7), (22, 31)),
		"baie de Gdańsk": ((18.8, 54.5), (10, 34)),
		"lacs de Mazurie": ((21.7, 53.8), (18, 41)),
		"Kaunas": ((23.9, 54.9), (37, 34)),
		"Vilnius": ((25.3, 54.7), (49, 37)),
		"lac Peïpous": ((27.5, 58.7), (54, 16)),
		"Novgorod": ((31.3, 58.5), (69, 20)),
		"lac Ilmen": ((31.3, 58.3), (71, 23)),
		"lac Ladoga": ((31.5, 61.0), (73, 6)),
		"fond du golfe de Finlande": ((30.3, 59.9), (60, 7)),
	},
	"lieu:pologne_ruthenie": {
		"Gdańsk": ((18.65, 54.35), (22, 7)),
		"Toruń": ((18.6, 53.0), (19, 14)),
		"lacs de Mazurie": ((21.7, 53.8), (31, 9)),
		"Varsovie": ((21.0, 52.2), (31, 19)),
		"Cracovie": ((19.94, 50.06), (25, 30)),
		"Wrocław": ((17.03, 51.1), (8, 22)),
		"Białowieża": ((23.8, 52.7), (48, 7)),
		"Pripiat": ((27.0, 52.0), (55, 25)),
		"Kiev": ((30.5, 50.45), (74, 20)),
		"Lviv": ((24.0, 49.8), (45, 42)),
		"Dniepr aval": ((32.0, 49.0), (80, 32)),
	},
	"lieu:balkans": {
		"Otrante": ((18.5, 40.1), (5, 16)),
		"Corfou": ((19.9, 39.6), (16, 21)),
		"Olympe": ((22.35, 40.1), (33, 18)),
		"golfe de Thessalonique": ((22.9, 40.6), (37, 15)),
		"Athènes": ((23.7, 38.0), (44, 27)),
		"cap Matapan": ((22.5, 36.4), (38, 36)),
		"Crète": ((24.9, 35.2), (55, 41)),
		"Dardanelles": ((26.4, 40.2), (60, 16)),
		"Constantinople": ((28.98, 41.0), (73, 10)),
		"Rhodes": ((28.0, 36.2), (77, 35)),
		"Danube": ((25.0, 43.8), (45, 5)),
	},
	"lieu:steppe_pontique": {
		"delta du Danube": ((29.6, 45.2), (14, 35)),
		"estuaire du Dniestr": ((30.3, 46.1), (20, 30)),
		"Odessa": ((30.7, 46.5), (22, 29)),
		"estuaire du Dniepr": ((32.6, 46.6), (36, 26)),
		"Perekop": ((33.7, 46.15), (40, 29)),
		"Sébastopol": ((33.5, 44.6), (40, 38)),
		"rapides du Dniepr": ((35.1, 47.9), (47, 17)),
		"détroit de Kertch": ((36.5, 45.3), (56, 35)),
		"mer d'Azov": ((36.5, 46.0), (60, 31)),
		"embouchure du Don": ((39.4, 47.2), (71, 27)),
	},
	"lieu:moscovie": {
		"Smolensk": ((32.0, 54.8), (14, 31)),
		"collines du Valdaï": ((33.0, 57.0), (19, 13)),
		"Tver": ((35.9, 56.9), (33, 20)),
		"Moscou": ((37.6, 55.75), (39, 23)),
		"Kalouga": ((36.3, 54.5), (35, 35)),
		"Vladimir": ((40.4, 56.1), (50, 33)),
		"Nijni Novgorod": ((44.0, 56.3), (78, 21)),
	},
	"lieu:grand_nord": {
		"Kola est": ((41.0, 67.2), (22, 16)),
		"mer Blanche": ((37.0, 65.5), (13, 27)),
		"Arkhangelsk": ((40.5, 64.55), (22, 30)),
		"cap Kanin": ((43.3, 68.6), (33, 14)),
		"delta de la Petchora": ((54.0, 68.2), (51, 19)),
		"Nouvelle-Zemble": ((54.0, 70.8), (57, 7)),
		"Oural polaire": ((60.0, 65.5), (70, 35)),
		"Petchora amont": ((56.5, 65.0), (54, 33)),
	},
	"lieu:volga_oural": {
		"Vyatka": ((49.7, 58.6), (19, 9)),
		"Kazan": ((49.1, 55.8), (21, 25)),
		"Perm": ((56.25, 58.0), (49, 19)),
		"Iekaterinbourg": ((60.6, 56.8), (64, 31)),
		"Samara": ((50.1, 53.2), (14, 37)),
	},
	"lieu:basse_volga": {
		"Saratov": ((46.0, 51.5), (37, 5)),
		"Volgograd": ((44.5, 48.7), (31, 14)),
		"Astrakhan": ((48.0, 46.35), (52, 30)),
		"Ouralsk": ((51.4, 51.2), (70, 7)),
		"embouchure de l'Oural": ((51.9, 47.1), (76, 28)),
		"Don": ((42.0, 49.0), (9, 19)),
	},
	"lieu:caucase": {
		"Novorossiisk": ((37.8, 44.7), (14, 9)),
		"Stavropol": ((42.0, 45.05), (34, 8)),
		"Elbrouz": ((42.45, 43.35), (42, 17)),
		"Koutaïssi": ((42.7, 42.25), (40, 26)),
		"Batoumi": ((41.6, 41.65), (31, 31)),
		"Tbilissi": ((44.8, 41.7), (50, 31)),
		"lac Sevan": ((45.0, 40.4), (54, 41)),
		"Makhatchkala": ((47.5, 43.0), (63, 22)),
		"Derbent": ((48.3, 42.05), (68, 28)),
		"Bakou": ((49.9, 40.4), (77, 35)),
	},
	# ── Afrique ─────────────────────────────────────────────────────────────────────────
	"lieu:maroc": {
		"Gibraltar": ((-5.6, 36.0), (45, 9)),
		"Teide": ((-16.6, 28.3), (19, 13)),
		"Rabat": ((-6.8, 34.0), (34, 20)),
		"Toubkal": ((-7.9, 31.06), (45, 27)),
		"Oran": ((-0.64, 35.7), (59, 15)),
		"Tarfaya": ((-12.9, 27.9), (25, 40)),
	},
	"lieu:ifriqiya": {
		"Sardaigne sud": ((9.0, 39.0), (8, 4)),
		"Marsala": ((12.4, 37.8), (49, 9)),
		"Malte": ((14.4, 35.9), (56, 14)),
		"cap Bon": ((11.05, 37.1), (45, 13)),
		"Carthage": ((10.3, 36.85), (43, 17)),
		"golfe de Gabès": ((10.1, 34.0), (40, 23)),
		"chott el-Djerid": ((8.4, 33.7), (28, 24)),
		"Tripoli": ((13.2, 32.9), (57, 27)),
		"fond du golfe de Syrte": ((18.5, 30.4), (77, 31)),
	},
	"lieu:senegambie": {
		"îles du Cap-Vert": ((-24.0, 15.5), (10, 20)),
		"Saint-Louis": ((-16.5, 16.0), (24, 15)),
		"Cap-Vert": ((-17.4, 14.7), (19, 23)),
		"embouchure de la Gambie": ((-16.6, 13.5), (21, 30)),
		"Fouta-Djalon": ((-12.0, 11.0), (35, 37)),
		"Ségou": ((-6.3, 13.45), (49, 29)),
		"Djenné": ((-4.55, 13.9), (55, 31)),
		"delta intérieur": ((-4.0, 15.0), (62, 22)),
		"Tombouctou": ((-3.0, 16.77), (66, 11)),
	},
	"lieu:cote_de_guinee": {
		"Sierra Leone": ((-13.2, 8.5), (5, 22)),
		"cap des Palmes": ((-7.7, 4.4), (24, 33)),
		"Ashanti": ((-1.6, 6.69), (44, 21)),
		"embouchure de la Volta": ((0.6, 5.8), (50, 30)),
		"Bénin": ((5.6, 6.34), (63, 20)),
		"delta du Niger": ((6.2, 4.6), (73, 32)),
	},
	"lieu:lac_tchad": {
		"lac Tchad": ((14.0, 13.0), (40, 9)),
		"N'Djamena": ((15.0, 12.1), (38, 13)),
		"Garoua": ((13.4, 9.3), (16, 25)),
		"mont Cameroun": ((9.2, 4.2), (30, 30)),
		"Douala": ((9.7, 4.05), (26, 35)),
		"Bangui": ((18.6, 4.4), (61, 34)),
	},
	"lieu:nubie": {
		"deuxième cataracte": ((31.3, 21.8), (45, 11)),
		"Méroé": ((33.75, 16.9), (58, 17)),
		"Khartoum": ((32.55, 15.6), (52, 23)),
		"Souakin": ((37.3, 19.1), (77, 22)),
		"Djebel Marra": ((24.3, 13.0), (17, 30)),
		"Sudd": ((30.5, 7.5), (45, 38)),
		"lac Tana": ((37.3, 12.0), (68, 35)),
	},
	"lieu:abyssinie": {
		"lac Tana": ((37.3, 12.0), (29, 17)),
		"Aksoum": ((38.7, 14.1), (31, 13)),
		"Adulis": ((39.6, 15.6), (44, 7)),
		"Erta Ale": ((40.7, 13.6), (57, 17)),
		"Bab-el-Mandeb": ((43.4, 12.6), (60, 12)),
		"Djibouti": ((43.1, 11.6), (63, 15)),
		"cap Guardafui": ((51.3, 11.8), (80, 15)),
		"lacs du Rift": ((38.8, 8.0), (38, 36)),
		"chutes du Nil Bleu": ((37.6, 11.5), (29, 27)),
	},
	"lieu:bassin_du_congo": {
		"Libreville": ((9.45, 0.4), (5, 12)),
		"pool Malebo": ((15.3, -4.3), (28, 32)),
		"Kisangani": ((25.2, 0.5), (59, 18)),
		"Ruwenzori": ((29.9, 0.4), (73, 25)),
		"lac Albert": ((31.0, 1.7), (78, 16)),
		"Tanganyika nord": ((29.5, -4.0), (82, 40)),
		"embouchure du Congo": ((12.3, -6.0), (16, 38)),
	},
	"lieu:grands_lacs": {
		"lac Victoria": ((33.0, -1.0), (35, 10)),
		"lac Tanganyika": ((29.5, -6.0), (19, 25)),
		"Kilimandjaro": ((37.35, -3.07), (43, 28)),
		"Lamu": ((40.9, -2.27), (72, 7)),
		"Mombasa": ((39.66, -4.05), (60, 24)),
		"Zanzibar": ((39.2, -6.1), (61, 30)),
		"Kilwa": ((39.5, -8.9), (60, 42)),
		"lac Malawi": ((34.5, -11.0), (39, 43)),
	},
	"lieu:angola": {
		"embouchure du Congo": ((12.3, -6.0), (19, 9)),
		"Luanda": ((13.2, -8.8), (20, 21)),
		"Benguela": ((13.4, -12.6), (16, 30)),
		"Namibe": ((12.15, -15.2), (15, 41)),
		"haut Zambèze": ((22.5, -14.0), (45, 42)),
		"Katanga": ((27.5, -11.6), (77, 28)),
		"lac Moero": ((28.7, -9.0), (80, 13)),
	},
	"lieu:zambeze": {
		"delta de l'Okavango": ((22.5, -19.3), (5, 20)),
		"chutes Victoria": ((25.85, -17.92), (15, 23)),
		"Grand Zimbabwe": ((30.93, -20.27), (40, 25)),
		"lac Malawi": ((34.5, -11.5), (57, 4)),
		"Tete": ((33.6, -16.15), (49, 8)),
		"delta du Zambèze": ((36.3, -18.8), (68, 20)),
		"Sofala": ((34.75, -20.15), (65, 28)),
		"Limpopo": ((31.0, -22.5), (40, 43)),
	},
	"lieu:namib_kalahari": {
		"embouchure du Cunene": ((11.8, -17.25), (16, 4)),
		"Walvis Bay": ((14.5, -22.95), (25, 21)),
		"canyon de la Fish": ((17.6, -27.6), (39, 30)),
		"embouchure de l'Orange": ((16.45, -28.6), (33, 43)),
		"delta de l'Okavango": ((22.5, -19.3), (57, 10)),
		"pan de Makgadikgadi": ((25.5, -20.7), (69, 17)),
	},
	"lieu:le_cap": {
		"embouchure de l'Orange": ((16.45, -28.6), (9, 5)),
		"montagne de la Table": ((18.4, -33.9), (19, 32)),
		"cap de Bonne-Espérance": ((18.5, -34.35), (19, 37)),
		"cap des Aiguilles": ((20.0, -34.8), (27, 37)),
		"Port Elizabeth": ((25.6, -33.96), (54, 35)),
		"Drakensberg": ((29.3, -29.5), (65, 12)),
		"Durban": ((31.0, -29.85), (76, 17)),
	},
	"lieu:madagascar": {
		"Beira": ((34.8, -19.8), (8, 26)),
		"Comores": ((43.3, -11.7), (24, 4)),
		"cap d'Ambre": ((49.3, -12.0), (52, 3)),
		"Antananarivo": ((47.5, -18.9), (44, 21)),
		"cap Sainte-Marie": ((45.15, -25.6), (40, 44)),
		"La Réunion": ((55.5, -21.1), (66, 29)),
		"Maurice": ((57.5, -20.25), (73, 29)),
	},
}


def _poids(reperes, lon, lat, sigma):
	c = math.cos(math.radians(lat))
	return [max(POIDS_MIN, math.exp(-(((lo - lon) * c) ** 2 + (la - lat) ** 2) / (2 * sigma ** 2)))
		for (lo, la), _ in reperes]


def _droite(xs, ys, ws):
	"""(a, b) minimisant Σ w (a·x + b − y)²."""
	sw = sum(ws)
	mx = sum(w * x for w, x in zip(ws, xs)) / sw
	my = sum(w * y for w, y in zip(ws, ys)) / sw
	den = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs))
	a = sum(w * (x - mx) * (y - my) for w, x, y in zip(ws, xs, ys)) / den
	return a, my - a * mx


def _lineaire(lieu, lon, lat, sigma):
	reperes = list(REPERES[lieu].values())
	ws = _poids(reperes, lon, lat, sigma)
	ax, bx = _droite([r[0][0] for r in reperes], [r[1][0] for r in reperes], ws)
	ay, by = _droite([r[0][1] for r in reperes], [r[1][1] for r in reperes], ws)
	return ax * lon + bx, ay * lat + by


def vers_case(lieu, lon, lat, sigma=SIGMA):
	"""(x, y) en cases (flottants) du point (lon, lat) sur la carte `lieu` : ajustement LOCAL
	(lon → x, lat → y, pondéré par la distance), puis les RÉSIDUS des repères interpolés en
	inverse du carré de la distance — la projection passe exactement par chaque repère, et suit
	les déformations du dessin entre eux (Kiev dessinée au nord du Pripiat)."""
	x, y = _lineaire(lieu, lon, lat, sigma)
	c = math.cos(math.radians(lat))
	num_x = num_y = den = 0.0
	for (lo, la), (rx, ry) in REPERES[lieu].values():
		d2 = ((lo - lon) * c) ** 2 + (la - lat) ** 2
		px, py = _lineaire(lieu, lo, la, sigma)
		if d2 < 1e-9:
			return rx, ry
		w = 1.0 / d2
		num_x += w * (rx - px)
		num_y += w * (ry - py)
		den += w
	return x + num_x / den, y + num_y / den


def emprise(lieu, cols, rows):
	"""(lon_min, lon_max, lat_min, lat_max) de la carte entière (ajustement global)."""
	reperes = list(REPERES[lieu].values())
	ws = [1.0] * len(reperes)
	ax, bx = _droite([r[0][0] for r in reperes], [r[1][0] for r in reperes], ws)
	ay, by = _droite([r[0][1] for r in reperes], [r[1][1] for r in reperes], ws)
	lons = sorted(((0 - bx) / ax, (cols - bx) / ax))
	lats = sorted(((0 - by) / ay, (rows - by) / ay))
	return lons[0], lons[1], lats[0], lats[1]


def _bande(a0, a1, b0, b1):
	"""Intervalle commun de [a0, a1] et [b0, b1] ; sans recouvrement, la bande entre les deux
	élargie d'un degré de part et d'autre."""
	lo, hi = max(a0, b0), min(a1, b1)
	if lo < hi:
		return lo, hi
	return hi - 1.0, lo + 1.0


def paire(fond, pose, dims_fond=(88, 48), dims_pose=(86, 48), n=4):
	"""Repères au format `calage_cartes.PAIRES` : nom → (px sur la carte POSÉE, px du FOND),
	`n × n` points de la zone commune des deux cartes, chacun projeté localement sur les deux."""
	ef = emprise(fond, *dims_fond)
	ep = emprise(pose, *dims_pose)
	lon0, lon1 = _bande(ef[0], ef[1], ep[0], ep[1])
	lat0, lat1 = _bande(ef[2], ef[3], ep[2], ep[3])
	reperes = {}
	for i in range(n):
		for j in range(n):
			lon = lon0 + (lon1 - lon0) * (i + 0.5) / n
			lat = lat0 + (lat1 - lat0) * (j + 0.5) / n
			xp, yp = vers_case(pose, lon, lat)
			xf, yf = vers_case(fond, lon, lat)
			reperes[f"{lon:.2f}, {lat:.2f}"] = ((xp * CASE_PX, yp * CASE_PX),
				(xf * CASE_PX, yf * CASE_PX))
	return reperes


def _centrer(reperes):
	"""Une case lue à la main (entiers) désigne la case entière : son centre est à +0,5."""
	for lieu, rs in reperes.items():
		for nom, (geo, (x, y)) in list(rs.items()):
			if isinstance(x, int) and isinstance(y, int):
				rs[nom] = (geo, (x + 0.5, y + 0.5))


_centrer(REPERES)


def enregistrer(paires, dimensions):
	"""Ajoute à `calage_cartes.PAIRES` une paire géoréférencée par (fond, pose) de `paires`
	(`dimensions[lieu]` = (colonnes, rangées)) ; une paire déjà calée à la main est gardée."""
	from dev import calage_cartes
	for fond, pose in paires:
		try:
			calage_cartes.paire_de(fond, pose)
			continue
		except KeyError:
			pass
		nom = f"{pose.split(':')[1]}_{fond.split(':')[1]}"
		calage_cartes.PAIRES[nom] = {"fond": fond, "pose": pose,
			"reperes": paire(fond, pose, dimensions[fond], dimensions[pose]), "geo": True}
