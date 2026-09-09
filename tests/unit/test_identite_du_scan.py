# -*- coding: utf-8 -*-
"""Story 11.4b, **lot S6** (AC 10) -- `mmu scan` n'a pas change de comportement.

AC 10.1, verbatim : « `mmu scan` et `mmu scan write` rendent, a arguments
equivalents, **les memes codes de sortie**, **les memes messages** et **les
memes artefacts** qu'au `baseline_commit`. »

**Ce banc ne verifie pas que les enveloppes appellent le coeur.** Ca, c'est un
cablage, et un cablage identique peut produire des artefacts differents --
dossier, nommage, ordre, octets. Il fait tourner les commandes **pour de vrai**,
par `cli.main([...])`, sur vingt-sept invocations qui couvrent les deux voies du
scan, les huit refus nommes de `scan write` et les **trois regimes de chacune de
ses deux invites `Y/N`** ; puis il compare tout ce qui en sort a un releve joue
par le **meme code** sous le `src/` du `baseline_commit` (`289f29d`, avant les
lots S1 a S5). **Quarante-deux** invocations, et **une seule** diverge : celle
qui pose a la main la couche `manual-corrections-v1`, changement de comportement
assume et documente du lot S3 (ligne L18 du document de liaison).

Le dernier bloc sort du scan et c'est voulu : `mmu extract` puis `mmu makepdf`,
parce que `pdf_composition.py` est le seul fichier de coeur touche par la vague
(lot S4) qu'aucune invocation de scan ne traverse -- le scan **relit** des
planches, il n'en imprime aucune --, et parce que `makepdf` produit l'artefact
**physique** dont toute la chaine de scan depend ensuite. Le PDF y est compare
**octet a octet**, comme n'importe quel autre artefact : voir le gel du rendu
dans `outils_identite_scan.geler_le_rendu_pdf`, dont la table de mesure dit
pourquoi il faut **deux** gels et pas un.

Ce qui est compare, scenario par scenario :

* le **code de sortie** ;
* `stdout` et `stderr`, **ligne par ligne, au caractere pres** -- les invites
  comprises, qui y figurent parce qu'elles sont imprimees sans passage a la
  ligne ;
* l'**arbre des artefacts**, chemin relatif -> condensat : les TIFF de sortie et
  les copies ingerees du scan, **octet a octet** ;
* chaque **document JSON** du projet -- manifest, document de detection, rapport
  d'ingestion, rapport de tri, profils --, **aplati**, donc compare cle a cle ;
* les lignes de `logs/scan.log`, horodate retiree.

Deux pieges de ce depot, payes ailleurs et non repayes ici :

1. **une assertion positive laisse passer toute divergence supplementaire.**
   « Ce champ diverge » ne vaut rien ; l'assertion est donc celle de
   l'**ensemble** : `chemins_divergents(...) == set()`, sur le dossier entier
   comme sur chaque scenario. Un aplatissement rend cet ensemble nommable ;
2. **un banc vert ne dit rien de ce qu'il ne mesure pas.** Cinq mesures de
   temoin ci-dessous rougissent si le releve cesse d'observer : le comparateur
   voit-il les trois formes de divergence, la reference sort-elle bien d'un
   arbre **d'avant** le lot S1, les invites sont-elles reellement posees dans
   les regimes qui les attendent et **absentes** partout ailleurs, et les
   regimes produisent-ils bien des artefacts differents.

Le releve et sa reference sont produits par `outils_identite_scan.py`, qui porte
le mode d'emploi de la **regeneration** de la reference.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path, PurePosixPath

import pytest

_RACINE = Path(__file__).resolve().parents[2]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import fabriquer_les_entrees_d_identite as fabriques   # noqa: E402
import outils_identite_scan as outils                  # noqa: E402
from sens_des_planches import PlanchesAuMemeSens        # noqa: E402

#: Le releve joue sous le `src/` du `baseline_commit` de la vague 3, sur les
#: **memes** entrees. Il est versionne : sans lui, l'AC 10.1 n'aurait plus de
#: cote gauche, et le banc mesurerait le depot d'aujourd'hui contre lui-meme.
REFERENCE = _RACINE / "tests" / "fixtures" / "identite-scan-289f29d.json"

#: Le commit d'ou la reference sort. Il est **le** `baseline_commit` de la
#: vague, celui d'ou partent les lots S1 a S5, et il est nomme ici parce que le
#: nom du fichier ne se relit pas dans un message d'echec.
BASELINE = "289f29d"

_ABSENT = object()


def _aplatir(valeur, prefixe: str = "") -> dict:
    """Un document -> `chemin pointe -> feuille` (meme forme que le releveur).

    Aplatir plutot que comparer deux `dict` : l'egalite de deux structures dit
    seulement qu'elles different, jamais **ou**. Le banc doit nommer l'ensemble
    exact des chemins divergents, donc il lui faut des chemins.
    """
    if isinstance(valeur, dict):
        aplati: dict = {}
        for cle, sous in valeur.items():
            aplati.update(_aplatir(sous, f"{prefixe}.{cle}" if prefixe else cle))
        return aplati or {prefixe: "<objet vide>"}
    if isinstance(valeur, list):
        aplati = {}
        for rang, sous in enumerate(valeur):
            aplati.update(_aplatir(sous, f"{prefixe}[{rang}]"))
        return aplati or {prefixe: "<liste vide>"}
    return {prefixe: valeur}


def chemins_divergents(gauche, droite) -> set:
    """L'**ensemble** des chemins ou les deux releves ne disent pas la meme
    chose -- cle manquante d'un cote comprise.

    C'est la forme que l'AC impose. Une assertion positive -- « le code de
    sortie coincide » -- laisserait passer une divergence de message, un fichier
    en trop, une cle de manifest apparue.
    """
    a, b = _aplatir(gauche), _aplatir(droite)
    return {chemin for chemin in set(a) | set(b)
            if not _memes_feuilles(a.get(chemin, _ABSENT),
                                   b.get(chemin, _ABSENT))}


#: La tolerance RELATIVE entre deux flottants. Elle n'est plus seule depuis le
#: run 7 du 2026-09-08 : `PLANCHER_ABSOLU_ENTRE_FLOTTANTS` la double d'un
#: plancher absolu, sans lequel une grandeur qui vaut zero n'etait comparable
#: par aucune tolerance relative. Les deux se lisent ensemble, et le plancher
#: porte sa propre justification.
#:
#: POURQUOI ELLE EXISTE, et ce qu'elle a coute de ne pas exister. Les
#: coefficients de calibration sortent d'un ajustement aux moindres carres, donc
#: de BLAS, qui n'est pas reproductible au bit pres d'une compilation a l'autre.
#: Le depot classe 3.11, 3.12 et 3.13 ; or **numpy 2.5 a laisse tomber 3.11**,
#: si bien que la version de Python entraine celle de numpy :
#:
#:     3.11.15 -> numpy 2.4.6      3.12.11 -> numpy 2.5.3
#:                                 3.13.7  -> numpy 2.5.3
#:
#: Mesure du 2026-09-08, meme machine, memes entrees, meme roue OpenCV 5.0.0 :
#: 33 bancs de ce fichier rougissent sous 3.12 et 3.13, et **aucun** ecart ne
#: porte sur autre chose que les derniers bits d'un flottant. Le plus large
#: mesure, en relatif :
#:
#:     coefficients.chroma_matrix[0][1]  9,864556887725939e-04
#:                                    -> 9,864556887726275e-04   ~3,4e-14
#:
#: LE CHOIX DU SEUIL est donc borne des deux cotes plutot que rond : 1e-12
#: laisse ~30x de marge au plus large ecart mesure, et reste dix ordres de
#: grandeur SOUS le plus petit ecart qui voudrait dire quelque chose du produit
#: -- un `mean_delta_e` qui passerait de 0,918 a 0,919 est un ecart relatif de
#: 1e-3, donc il diverge toujours. Les deux bornes sont mesurees, pas
#: supposees : un banc exige qu'un ecart de 1e-15 soit avale, un autre qu'un
#: ecart de 1e-9 fasse rougir.
#:
#: CE QU'ELLE NE COUVRE PAS, dit plutot que tu : un condensat SHA-256 de raster.
#: Si un jour une difference de dernier bit changeait un pixel, aucune tolerance
#: ne le rattraperait -- c'est un fait a mesurer ce jour-la, et il n'est pas
#: survenu ici : les 33 ecarts sont tous des feuilles de document JSON.
TOLERANCE_RELATIVE_ENTRE_FLOTTANTS = 1e-12

#: Le PLANCHER ABSOLU, et pourquoi une tolerance relative ne suffisait pas.
#:
#: LE FAIT QUI L'IMPOSE (run 7 de la CI publique, 2026-09-08). Trente-et-un
#: scenarios de ce banc ont rougi sur **un seul** champ,
#: `acceptance.neutral_axis_channel_spread_8bit` :
#:
#:     1.4362599927153497e-06  ->  1.436260077980478e-06
#:
#: soit 5,9e-08 en RELATIF -- trente fois au-dessus de la tolerance ci-dessus,
#: qui ne pouvait donc rien en faire. Mais 8,5e-14 en ABSOLU, dans l'unite du
#: champ, qui est le **code 8 bits**. Ce champ mesure le pire ecart entre canaux
#: sur des valeurs quasi neutres : c'est une soustraction de nombres presque
#: egaux, donc une cancellation, et elle transforme le dernier bit d'un float64
#: (8,5e-16 en relatif sur des canaux d'echelle ~1e2) en huitieme chiffre.
#:
#: UNE TOLERANCE RELATIVE N'A PAS DE SENS SUR UNE GRANDEUR QUI VAUT ZERO. C'est
#: la raison de fond : 1,4e-06 code 8 bits est une neutralite parfaite, et
#: exiger d'elle dix-sept chiffres significatifs mesure le bruit de la machine,
#: pas le produit.
#:
#: CE N'EST NI PYTHON NI NUMPY NI FFMPEG -- les trois ont ete releves des deux
#: cotes et sont IDENTIQUES (numpy 2.5.3, opencv 5.0.0.93, ffmpeg
#: 6.1.1-3ubuntu5) : la CI rendait 39 rouges la ou cette machine en rendait
#: zero. La seule variable restante est la MACHINE, ce que confirme le partage
#: observe -- les jobs 3.11 et 3.12 rendent des listes de verdicts identiques
#: au verdict pres, et le job 3.13 est vert, sur trois runners differents.
#:
#: LES DEUX BORNES SONT MESUREES DANS CE DEPOT, pas choisies :
#:
#:   borne basse   8,5e-14   le plus large ecart absolu reellement observe
#:   borne haute   1,4e-09   la plus petite feuille flottante non nulle de tout
#:                           le baseline (1,436e-06, et c'est ce champ meme),
#:                           multipliee par le seuil de sens produit de 1e-3
#:
#: 1e-11 tient au milieu : x117 au-dessus du bruit mesure, x144 sous le plus
#: petit ecart qui voudrait dire quelque chose. Un plancher de 1e-09 aurait
#: laisse x1,4 de marge haute -- trop juste pour etre defendable.
PLANCHER_ABSOLU_ENTRE_FLOTTANTS = 1e-11


def _memes_feuilles(gauche, droite) -> bool:
    """Deux feuilles egales -- au bit pres, sauf deux FLOTTANTS.

    La tolerance ne s'applique QUE lorsque les deux cotes sont des flottants :
    une chaine qui ressemble a un nombre, un entier, un booleen ou une cle
    absente retombent sur l'egalite stricte. `math.isclose` rend par ailleurs
    faux sur `NaN`, ce qui est la reponse voulue -- deux `NaN` ne sont pas la
    meme mesure.
    """
    if isinstance(gauche, float) and isinstance(droite, float):
        return math.isclose(gauche, droite,
                            rel_tol=TOLERANCE_RELATIVE_ENTRE_FLOTTANTS,
                            abs_tol=PLANCHER_ABSOLU_ENTRE_FLOTTANTS)
    return gauche == droite


# ---------------------------------------------------------------------------
# La tolerance de DERNIER BIT, mesuree aux deux bornes -- 2026-09-08
# ---------------------------------------------------------------------------

#: L'ecart relatif le plus large REELLEMENT mesure entre numpy 2.4.6 et 2.5.3,
#: sur les sept feuilles divergentes du scenario `01_calibrate`. Ecrit ici pour
#: que la borne basse de la tolerance soit confrontee a un fait plutot qu'a une
#: intention.
ECART_MESURE_ENTRE_NUMPY_2_4_ET_2_5 = 3.4e-14

#: Le plus petit ecart relatif qui voudrait dire quelque chose du produit : un
#: `mean_delta_e` qui bougerait de 0,918 a 0,919.
ECART_QUI_VEUT_DIRE_QUELQUE_CHOSE = 1e-3


def test_la_tolerance_est_ENCADREE_par_les_deux_faits_qui_la_fondent() -> None:
    """Le seuil n'est ni tire au sort ni rond : il tient entre deux mesures.

    Sans ce banc, `TOLERANCE_RELATIVE_ENTRE_FLOTTANTS` pourrait etre relachee
    d'un facteur mille sans que rien ne le dise -- et une tolerance qui derive
    est exactement ce qui transforme un dossier d'identite en decor.
    """
    assert (ECART_MESURE_ENTRE_NUMPY_2_4_ET_2_5
            < TOLERANCE_RELATIVE_ENTRE_FLOTTANTS
            < ECART_QUI_VEUT_DIRE_QUELQUE_CHOSE)


# ---------------------------------------------------------------------------
# Le rush du banc EPINGLE son encodage -- run 7 de la CI, 2026-09-08
# ---------------------------------------------------------------------------

#: Le compte de fils sous lequel le baseline `289f29d` a ete enregistre. Ce
#: n'est pas un reglage de confort : x264 multi-threade PAR FRAMES, et son
#: defaut vaut `1,5 x coeurs`, donc le rush depend de la machine.
FILS_D_ENCODAGE_DU_BASELINE = "6"


def _source_de_la_fabrique() -> str:
    return (_RACINE / "tests" / "unit"
            / "fabriquer_les_entrees_d_identite.py").read_text(encoding="utf-8")


def test_le_rush_du_banc_EPINGLE_son_nombre_de_fils() -> None:
    """La fabrique ne laisse AUCUN appel ffmpeg au defaut de la machine.

    Frontiere NEGATIVE : aucun test positif ne verrait revenir un appel qui
    omet `-threads`, et c'est precisement l'omission qui a fait rougir
    `60_extract_cadence_5` et `61_extract_cadence_12` sur le runner. Le rush
    y etait encode avec un autre compte de fils, donc d'autres octets, donc
    d'autres frames extraites -- sans qu'une seule ligne du produit ait bouge.
    """
    source = _source_de_la_fabrique()
    assert '"ffmpeg"' in source, (
        "l'anti-vacuite : si la fabrique cessait d'appeler ffmpeg, ce banc "
        "deviendrait vrai pour toujours sans plus rien mesurer")
    assert '"-threads"' in source
    assert f'"-threads", "{FILS_D_ENCODAGE_DU_BASELINE}"' in source, (
        "le compte de fils doit rester celui du baseline : le changer sans "
        "regenerer la reference ferait diverger les frames extraites")


def test_le_rush_du_banc_est_le_SEUL_appel_ffmpeg_de_la_fabrique() -> None:
    """Le volet symetrique : un second appel non epingle passerait inapercu.

    La frontiere ci-dessus se contente d'un `-threads` quelque part dans le
    fichier. Elle serait donc satisfaite par un appel epingle a cote d'un
    appel qui ne l'est pas -- ce banc-ci ferme cet ecart en comptant.
    """
    source = _source_de_la_fabrique()
    assert source.count('"ffmpeg"') == 1
    assert source.count('"-threads"') == 1


# ---------------------------------------------------------------------------
# Le PLANCHER ABSOLU, mesure aux deux bornes -- run 7 de la CI, 2026-09-08
# ---------------------------------------------------------------------------

#: Le plus large ecart ABSOLU reellement observe entre deux machines, sur le
#: champ `neutral_axis_channel_spread_8bit` du scenario `01_calibrate` :
#:
#:     1.4362599927153497e-06  ->  1.436260077980478e-06
#:
#: Ecrit ici pour que la borne basse du plancher soit confrontee a un fait.
ECART_ABSOLU_MESURE_ENTRE_MACHINES = 8.6e-14

#: La plus petite feuille flottante NON NULLE de tout le baseline -- releve sur
#: les 4 856 feuilles flottantes non nulles du fichier de reference. C'est ce
#: champ lui-meme : rien, dans ce releve, ne descend plus bas.
PLUS_PETITE_FEUILLE_FLOTTANTE_DU_BASELINE = 1.436260e-06


def test_le_PLANCHER_est_ENCADRE_par_les_deux_faits_qui_le_fondent() -> None:
    """Le plancher tient entre le bruit mesure et le premier ecart qui a un sens.

    La borne haute n'est pas un nombre rond : c'est la plus petite feuille du
    baseline multipliee par le seuil de sens produit. Un plancher au-dessus
    d'elle pourrait avaler une variation de 0,1 % de la plus petite grandeur
    que ce releve porte, ce qui est exactement ce qu'un dossier d'identite
    existe pour voir.
    """
    plafond = (PLUS_PETITE_FEUILLE_FLOTTANTE_DU_BASELINE
               * ECART_QUI_VEUT_DIRE_QUELQUE_CHOSE)
    assert (ECART_ABSOLU_MESURE_ENTRE_MACHINES
            < PLANCHER_ABSOLU_ENTRE_FLOTTANTS
            < plafond)


def test_le_PLANCHER_avale_l_ecart_ENTRE_MACHINES_reellement_mesure() -> None:
    """Le sens qui ferme la panne, sur les DEUX vraies valeurs du run 7."""
    ici = {"acceptance": {"neutral_axis_channel_spread_8bit":
                          1.4362599927153497e-06}}
    la_bas = {"acceptance": {"neutral_axis_channel_spread_8bit":
                             1.436260077980478e-06}}
    assert chemins_divergents(ici, la_bas) == set()

    # Anti-vacuite : sans lui, deux structures identiques rendraient vert.
    assert ici != la_bas
    # Et le volet qui dit POURQUOI la tolerance relative ne suffisait pas :
    # en relatif, cet ecart est trente fois au-dessus d'elle.
    gauche = ici["acceptance"]["neutral_axis_channel_spread_8bit"]
    droite = la_bas["acceptance"]["neutral_axis_channel_spread_8bit"]
    assert (abs(droite - gauche) / gauche) > TOLERANCE_RELATIVE_ENTRE_FLOTTANTS


def test_le_PLANCHER_ne_masque_PAS_un_ecart_qui_veut_dire_quelque_chose() -> None:
    """Le sens symetrique : sur la plus petite grandeur du releve, un ecart de
    0,1 % doit toujours faire rougir.

    C'est le volet qui interdit d'elargir le plancher « pour que ca passe » :
    le porter a 1e-09 rendrait ce banc rouge.
    """
    petit = PLUS_PETITE_FEUILLE_FLOTTANTE_DU_BASELINE
    ecart_qui_compte = petit * ECART_QUI_VEUT_DIRE_QUELQUE_CHOSE
    assert chemins_divergents(
        {"v": petit}, {"v": petit + ecart_qui_compte}) == {"v"}


def test_le_PLANCHER_ne_touche_a_AUCUNE_grandeur_d_echelle_ordinaire() -> None:
    """Sur une feuille d'echelle 1, c'est la tolerance RELATIVE qui commande.

    Le plancher est cent fois plus large que le relatif a cette echelle ; il
    reste six ordres de grandeur sous le premier ecart qui aurait un sens.
    """
    assert chemins_divergents({"v": 1.0}, {"v": 1.0 + 1e-3}) == {"v"}
    assert chemins_divergents({"v": 1.0}, {"v": 1.0 + 1e-13}) == set()


def test_la_tolerance_AVALE_un_ecart_de_dernier_bit() -> None:
    """Le sens qui ferme la panne, sur les VRAIES valeurs des deux numpy."""
    numpy_2_4 = {"coefficients": {"chroma_matrix": [[1.0729120347131051,
                                                     0.0009864556887725939]]},
                 "acceptance": {"mean_delta_e": 0.9180690447154056}}
    numpy_2_5 = {"coefficients": {"chroma_matrix": [[1.0729120347131054,
                                                     0.0009864556887726275]]},
                 "acceptance": {"mean_delta_e": 0.9180690447154066}}
    assert chemins_divergents(numpy_2_4, numpy_2_5) == set()

    # Le volet d'anti-vacuite : sans lui, deux structures IDENTIQUES rendraient
    # le banc vert et la tolerance pourrait etre morte.
    assert numpy_2_4 != numpy_2_5


def test_la_tolerance_NE_MASQUE_PAS_un_ecart_qui_veut_dire_quelque_chose(
) -> None:
    """Le volet symetrique, et c'est lui qui empeche la tolerance de tout avaler."""
    assert chemins_divergents({"d": 0.918}, {"d": 0.919}) == {"d"}
    # Un ecart relatif de 1e-9, mille fois plus fin que le precedent et mille
    # fois plus large que le seuil : il doit encore rougir.
    assert chemins_divergents({"d": 1.0}, {"d": 1.000000001}) == {"d"}


@pytest.mark.parametrize("gauche, droite", [
    # une chaine qui RESSEMBLE a un nombre : comparaison stricte
    ({"v": "0.5"}, {"v": "0.5000000000001"}),
    # un entier : comparaison stricte, et deux entiers voisins different
    ({"v": 1000000000000000}, {"v": 1000000000000001}),
    # un booleen face au flottant qui lui ressemble
    ({"v": True}, {"v": 1.0000000000001}),
    # une cle ABSENTE d'un cote (l'autre cle est la pour que le releve
    # compare ne soit pas VIDE, `_aplatir` ayant sa propre feuille pour ca)
    ({"v": 0.5, "temoin": 1}, {"temoin": 1}),
    # deux NaN : ce ne sont pas la meme mesure
    ({"v": float("nan")}, {"v": float("nan")}),
    # zero face a un nombre non nul, MAIS au-dessus du plancher absolu : le
    # couple `(0.0, 1e-300)` que ce volet portait jusqu'au 2026-09-08 est
    # desormais AVALE, et c'est voulu -- 1e-300 n'est pas une mesure, c'est un
    # zero ecrit autrement. Le volet garde son role en se posant la ou le
    # plancher ne va pas : un ecart cent fois au-dessus de lui.
    ({"v": 0.0}, {"v": 1e-9}),
])
def test_la_tolerance_ne_s_applique_QU_A_DEUX_FLOTTANTS(gauche, droite) -> None:
    """Ce que la tolerance ne doit surtout pas elargir en passant.

    Chacun de ces couples serait avale par une tolerance ecrite un cran trop
    large -- en convertissant les deux cotes en flottant, par exemple, ou en
    posant un `abs_tol` non nul « pour les petits nombres » -- le plancher pose
    le 2026-09-08 est borne, lui, et ces couples restent hors de sa portee.
    """
    assert chemins_divergents(gauche, droite) == {"v"}


#: **(f) LE VOCABULAIRE DES OBJETS** -- story 11.14, `EPIC11-ARB-214`, `-220`
#: et `-221`, tranches par Egan le 2026-09-04 : « Il faut qu'on tranche sur les
#: mots une bonne fois pour toutes. » Le dossier des frames rescannees
#: s'appelle desormais `frames-scannees/` et non plus `output-frames/` ; celui
#: des frames extraites `extract-frames/` et non plus `frames/`, « en symetrie
#: avec la commande `extract` qui les produit ».
#:
#: **C'est un renommage de SURFACE, et la reference ne se REGENERE PAS.** Elle
#: n'est pas un fichier d'or : c'est le releve joue sous le `src/` du
#: `baseline_commit` (`289f29d`), ou les dossiers portaient leurs anciens noms.
#: La rejouer produirait exactement les memes octets -- le baseline ne change
#: pas. Ce qu'il faut, c'est **traduire son releve dans les mots
#: d'aujourd'hui**, comme la famille (d) traduit deja le nom d'un tirage.
#:
#: **UNE LIGNE PAR SEGMENT RENOMME**, jamais un motif unique pour tous (meme
#: forme que l'AC 4.3 de la fiche : « une frontiere par nom renomme [...] un
#: test global serait vert des que le premier nom est couvert »). Chacune porte
#: son motif, son remplacant et le cardinal EXACT des substitutions qu'elle
#: opere sur la reference.
#:
#: **Les motifs sont bornes par des frontieres de SEGMENT, jamais par une
#: sous-chaine**, et c'est ce qui les rend etroits :
#:
#: * `output_frames_dir` -- la **cle** de manifeste -- n'est PAS touchee, et
#:   c'est `EPIC11-ARB-221` : « les cles JSON restent telles quelles [...] tu
#:   touches aux valeurs de chemin, jamais aux noms de cles ». Elle echappe au
#:   motif par le souligne, qui n'est pas le tiret ;
#: * le motif de `frames/` exige le **slash** : « 12 frames extraites » dans un
#:   message n'est pas un chemin et n'est pas traduit, `sheet_frames` non plus,
#:   et ni `output-frames/` ni `extract-frames/` ne le declenchent -- le tiret
#:   qui les precede est exclu par la garde arriere.
#:
#: **La troisieme ligne ne porte pas sur un chemin mais sur un nom de dossier
#: NU, et elle a ete trouvee par la mesure, pas prevue** : `artifacts.frames_dir`
#: vaut la chaine `"frames"` toute seule, sans slash, dans huit scenarios. Le
#: motif des deux premieres exige le slash -- a raison --, donc il ne la voyait
#: pas. Elle se traduit sur une egalite de chaine ENTIERE (`\Aframes\Z`), la
#: forme la plus etroite qui existe : une phrase ne peut pas y tomber. Elle
#: porte sur les **valeurs seulement**, jamais sur les cles, et c'est encore
#: `EPIC11-ARB-221` -- le manifeste POC porte une cle `"frames"` (`cli.py`,
#: `_build_sheet_manifest`) qui ne doit pas bouger. La reference n'en porte
#: aucune aujourd'hui (mesure faite : zero cle egale a `frames`), mais la
#: portee est **declaree** plutot que laissee au hasard du contenu de la
#: fixture.
#:
#: **Ce que la traduction NE couvre pas, dit plutot que tu** : une regression
#: qui changerait un condensat de frame, un cardinal, un code de sortie ou un
#: message reste entierement visible. La traduction ne renomme qu'un segment de
#: chemin, elle n'excuse aucune valeur. C'est exactement la relecture du `diff`
#: que la sous-tache C3 demande : « un scenario dont la sortie change AUTREMENT
#: que par le mot renomme est une regression, pas un effet du renommage ».
#:
#: Les cardinaux sont **mesures**, pas estimes, et ils bordent les DEUX cotes :
#: une traduction devenue muette ferait rougir la comparaison (donc elle se
#: verrait), mais une traduction devenue TROP LARGE la rendrait verte **en
#: cessant d'observer** -- et celle-la ne se verrait nulle part ailleurs.
#:
#: Le nom NEUF du dossier des frames rescannees est nomme une fois pour que la
#: table ci-dessous et les mesures qui la lisent ne puissent pas diverger.
DOSSIER_DES_FRAMES_SCANNEES = "frames-scannees"

#: Le nom que porte aujourd'hui le profil de calibration de la chaine du
#: dossier d'identite : le slug du libelle imprime sur le QR de sa page de
#: calibration. Au baseline, il portait l'identite de chaine
#: (`300-tiff-b2f54adf401c`) -- voir la traduction ci-dessous.
PROFIL_NOMME_PAR_LE_LIBELLE = "hp-envy-4520-tiff-600-dpi-auto-corr-off"

TRADUCTIONS_DU_VOCABULAIRE = (
    # (nom retire, motif structurel, motif dans le TEXTE brut du fichier,
    #  nom neuf, porte-t-elle sur les cles ?, cardinal exact,
    #  un exemple AVANT et son APRES -- ecrits ici parce que les temoins de
    #  bord doivent fabriquer une cible que CETTE ligne-la reconnait, et qu'une
    #  cible derivee du motif par inspection serait un second lieu ou la regle
    #  vivrait)
    ("output-frames", r"(?<![\w-])output-frames(?![\w-])",
     r"(?<![\w-])output-frames(?![\w-])", DOSSIER_DES_FRAMES_SCANNEES,
     True, 284,
     "output-frames/lot-a/scan_f.tiff",
     f"{DOSSIER_DES_FRAMES_SCANNEES}/lot-a/scan_f.tiff"),
    ("frames/", r"(?<![\w-])frames/", r"(?<![\w-])frames/",
     "extract-frames/", True, 177,
     "frames/lot-a/f.tiff", "extract-frames/lot-a/f.tiff"),
    ("frames (dossier NU)", r"\Aframes\Z", r'"frames"',
     "extract-frames", False, 8,
     "frames", "extract-frames"),
    # `EPIC11-ARB-225` -- le dossier des planches. Une seule forme, le
    # SEGMENT : la reference ne porte aucune occurrence nue (mesure : zero
    # `"patches"`), ce dossier n'ayant jamais eu de champ de manifeste a la
    # maniere d'`artifacts.frames_dir`. Une quatrieme ligne a cardinal nul
    # ferait croire a une couverture qui n'existe pas.
    ("patches/", r"(?<![\w-])patches/", r"(?<![\w-])patches/",
     "planches/", True, 38,
     "patches/demo_lot-a_2f-por.pdf", "planches/demo_lot-a_2f-por.pdf"),
    # Constat de terrain `D2` (2026-09-06) -- le profil de calibration porte le
    # LIBELLE DE CHAINE lu sur le QR, la ou le baseline le nommait de son
    # identite de chaine. Le raster reel d'Egan l'a impose : son profil
    # s'affichait sous un nom que rien sur la page ne portait.
    #
    # **Le motif exige `.json`, et c'est toute la mesure.** L'identite de chaine
    # n'a PAS change : elle reste la valeur de `chain_id` dans le document, de
    # `correction_chain_id` au manifeste, et de `color.calibration_chain_ids[]`.
    # Une substitution nue les traduirait toutes et rendrait ce banc aveugle a
    # un changement d'identite -- exactement le defaut que ce fichier existe
    # pour empecher. Mesure sur la reference : 466 occurrences du jeton, dont
    # 269 seulement suivies de `.json`. Les 197 autres restent telles quelles.
    ("300-tiff-b2f54adf401c (NOM DE FICHIER)",
     r"300-tiff-b2f54adf401c(?=\.json)",
     r"300-tiff-b2f54adf401c\.json",
     PROFIL_NOMME_PAR_LE_LIBELLE, True, 269,
     "versions/calibration/300-tiff-b2f54adf401c.json",
     f"versions/calibration/{PROFIL_NOMME_PAR_LE_LIBELLE}.json"),
)

_TRADUCTIONS = tuple(
    (ligne[0], re.compile(ligne[1]), ligne[3], ligne[4])
    for ligne in TRADUCTIONS_DU_VOCABULAIRE)


def _traduire_un_texte(texte: str, compteur: dict, *, cle: bool = False) -> str:
    """Appliquer les traductions a un texte, en comptant chacune a part.

    Comptees **separement** : un cardinal global serait juste alors qu'une des
    traductions serait morte et une autre deux fois trop large.

    `cle=True` restreint aux traductions declarees valables sur les cles --
    `EPIC11-ARB-221`, « tu touches aux valeurs de chemin, jamais aux noms de
    cles ».
    """
    for retire, motif, neuf, sur_les_cles in _TRADUCTIONS:
        if cle and not sur_les_cles:
            continue
        texte, mordu = motif.subn(neuf, texte)
        compteur[retire] = compteur.get(retire, 0) + mordu
    return texte


def _traduire_le_vocabulaire(valeur, compteur: dict):
    """Rendre un releve du baseline dans les mots d'aujourd'hui (story 11.14).

    Les **cles** de l'arbre des artefacts sont des chemins relatifs : c'est la
    que vit le nom du dossier, et c'est pourquoi la traduction porte sur les
    cles autant que sur les feuilles. Le compteur est rendu par la bande plutot
    que devine : un banc qui ne saurait pas combien de fois il a substitue ne
    saurait pas non plus quand il a cesse de le faire.
    """
    if isinstance(valeur, dict):
        return {_traduire_un_texte(str(cle), compteur, cle=True):
                _traduire_le_vocabulaire(sous, compteur)
                for cle, sous in valeur.items()}
    if isinstance(valeur, list):
        return [_traduire_le_vocabulaire(sous, compteur) for sous in valeur]
    if isinstance(valeur, str):
        return _traduire_un_texte(valeur, compteur)
    return valeur


def _reference_brute() -> dict:
    """La reference telle qu'elle est versionnee, sans traduction.

    Elle sert aux temoins : sans elle, « la traduction a mordu 284 fois » ne
    pourrait pas etre confronte a ce que le fichier porte reellement.
    """
    return json.loads(REFERENCE.read_text(encoding="utf-8"))


def _reference() -> dict:
    """La reference, **traduite** dans le vocabulaire d'aujourd'hui.

    Toute comparaison de ce banc passe par ici. **Elle ne se regenere pas** :
    la reference n'est pas un fichier d'or mais le releve joue sous le `src/`
    du `baseline_commit` (`289f29d`), ou les dossiers portaient leurs anciens
    noms. La rejouer produirait exactement les memes octets -- le baseline ne
    change pas. Ce qu'il faut, c'est traduire son releve dans les mots
    d'aujourd'hui, comme la famille (d) traduit deja le nom d'un tirage.
    """
    return _traduire_le_vocabulaire(_reference_brute(), {})


#: Les noms de scenarios, **lus de la reference** et jamais recopies : une liste
#: ecrite a la main en oublierait, et c'est l'oubli qui laisse passer une
#: commande devenue divergente.
NOMS = sorted(_reference()["scenarios"])


#: Le **seul** scenario dont la divergence est attendue, et son motif verbatim
#: (ligne L18 du document de liaison, story 11.4b lot S3) : « le refus d'une
#: couche `manual-corrections-v1` -- levier des rectangles retire par
#: `EPIC7-ARB-102` -- devient un refus de `scan write`, la ou c'etait un
#: silence ».
#:
#: Il est nomme ici plutot que tolere en silence, et le banc mesure **les deux
#: moities** : que ce scenario-la diverge bel et bien (sinon la ligne L18
#: mentirait), et qu'aucun autre ne diverge. Aucune commande de la CLI ne sait
#: POSER cette couche : le scenario l'ecrit a la main, ce qu'aucun parcours
#: reel ne fait.
DIVERGENCE_L18 = {"53_couche_manual_corrections_v1"}

#: Les scenarios que le **lot L** fait diverger, et leur motif verbatim (ligne
#: **L25** du document de liaison, story 11.4b lot L, `EPIC11-ARB-87`) : le pied
#: technique des planches passe de **six** a **dix** renseignements, sous des
#: cles courtes, pour que les huit `CHAMPS_NEUTRES_DU_LOT` soient tous relisables
#: sur le papier. **Ce qui est imprime change donc**, et c'est l'objet meme de
#: l'arbitrage -- pas un effet de bord.
#:
#: **Six scenarios pour deux planches, et l'ecart entre ces deux nombres est
#: instructif** : le releve capture l'arbre du projet **entier** a chaque
#: scenario, et les planches s'y accumulent. Un PDF imprime au scenario 62 est
#: encore la au 67, ou il diverge toujours. Les scenarios 66 et 67 sont des
#: **refus** : ils n'impriment rien, ils portent le residu des precedents.
#:
#: **Ce que la divergence n'est PAS**, et un banc le mesure plutot que de le
#: declarer (`test_le_pied_technique_ne_change_QUE_le_condensat_des_planches_v2`)
#: : aucun code de sortie, aucun message, aucun manifest, aucune frame, aucun
#: journal. **Le seul chemin qui bouge est le condensat d'un PDF de planches
#: imprime en v2** -- et le PDF imprime en **v1** revient au condensat du
#: baseline, ce qui est l'AC 6.4 mesuree de bout en bout sur la vraie CLI.
DIVERGENCE_L25 = {
    "62_makepdf_SECOND_lot_v2_portrait",
    "63_makepdf_premier_lot_v2_portrait",
    "64_makepdf_SECOND_lot_REJOUE_a_l_identique",
    "65_makepdf_v1_portrait",
    "66_makepdf_deja_present_REFUS",
    "67_makepdf_dpi_INSUFFISANT_REFUS",
}

#: Le scenario que la **story 11.4c, lot V2** fait diverger, et son motif
#: verbatim (AC 9 de la fiche `11-4c-sorties-nommees-du-coeur.md`) : « **cote
#: scan** : faire descendre l'inventaire d'avertissements **jusqu'au code de
#: sortie**, sur un ensemble ferme et mesure (D2 + D3) ».
#:
#: Ce que la divergence **n'est pas**, et c'est le coeur de la fiche (fait F7,
#: verbatim) : « La tracabilite de D3 est COMPLETE, et l'elargir serait le
#: defaut. [...] La correction porte sur **le code de sortie, pas sur la
#: tracabilite**. » Le releve le mesure plutot que de le declarer
#: (`test_le_pont_de_l_inventaire_ne_change_QUE_le_code_et_le_VERBE`) : ni
#: frame, ni manifest, ni journal, ni `stderr` ne bougent -- **deux** chemins
#: divergent, le code de sortie et la seule ligne de `stdout` qui portait le
#: mot « succes ».
#:
#: **Un seul scenario, et l'absence du `51b` est elle aussi une AC** (9.4) :
#: `OUTPUT_FRAME_OVERWRITTEN` sous un `--overwrite` explicite ne degrade rien,
#: l'operateur ayant demande l'ecrasement. Le scenario `51b_write_lot_deja_PDF`
#: garde donc son `0` **et ses octets**, et le test de caracterisation le
#: mesure a l'envers.
DIVERGENCE_V2 = {"52_source_ILLISIBLE"}

#: Les trois familles reunies. L'assertion d'ensemble porte sur celle-ci ; les
#: caracterisations, elles, portent chacune sur **sa** famille -- les
#: confondre rendrait vert un scenario qui aurait change de raison de diverger.
DIVERGENCE_ATTENDUE = DIVERGENCE_L18 | DIVERGENCE_L25 | DIVERGENCE_V2


#: CE QUE LA LIAISON DE `main` DU 2026-09-01 A LEGITIMEMENT CHANGE, et rien
#: d'autre. **Quatre** familles depuis la vague 5 (la troisieme est declaree
#: plus bas avec `CRITERES_D_IDENTITE_NEUFS`, la quatrieme avec
#: `CHAMP_DES_RANGS_SCANNES`), et chacune est reconnue a sa forme plutot qu'en
#: enumerant les scenarios ou elle tombe.
#:
#: **(a) Quatre champs neufs au manifest** -- `EPIC11-ARB-109`, « historique de
#: reconstruction PAR LOT : la section de tete est singuliere, un lot suivi
#: d'un autre perdait la trace de son scan » --, plus les deux chemins
#: qu'`EPIC11-ARB-91` fait bouger en faisant entrer le rang de version dans le
#: NOM du PDF de planches et au filigrane du manifest. Ils sont absents du
#: baseline `289f29d` parce qu'ils n'existaient pas encore le jour ou il a ete
#: releve.
#:
#: **(b) Les refus qui ont gagne des ISSUES** -- `EPIC11-ARB-89`, verbatim
#: d'Egan : « au lieu d'un overwrite destructif, toujours proposer un
#: versionnage [...] Mais toujours permettre une reecriture plutot qu'un
#: blocage sec. » Une dizaine de refus n'offraient qu'UNE issue ; ils en
#: offrent desormais deux ou trois.
#:
#: **La tolerance est posee au CHEMIN et a la VALEUR, jamais au scenario**, et
#: c'est tout le point. Declarer divergents les vingt-six scenarios concernes,
#: comme le font les lignes L18, L25 et l'AC 9, aurait cesse de mesurer tout le
#: RESTE de leur sortie -- codes de retour, frames ecrites, journaux --,
#: c'est-a-dire exactement ce que ce banc existe pour tenir. Ici, ce qui est
#: excuse est reconnu au champ pres et au mot pres ; tout le reste continue de
#: valoir `== set()`.
#:
#: **Ce que cette tolerance coute, dit plutot que tu** : une regression future
#: DANS l'un de ces champs, ou un refus qui gagnerait une issue sans qu'on
#: l'ait voulu, passerait ici sans rougir. Ni l'un ni l'autre n'est sans
#: mesure : `tests/unit/test_scan_write_noyau.py` compare l'entree de lot
#: ENTIERE entre les deux voies d'ecriture, et
#: `test_la_TOLERANCE_de_la_liaison_n_est_ni_MORTE_ni_TROP_LARGE` ci-dessous
#: mesure l'ensemble EXACT de ce que la tolerance avale.
CHAMPS_DE_LA_LIAISON = ("ingest_slug", "origin", "output_frames_dir", "status")

#: Les mots par lesquels une issue NEUVE se reconnait. Ce sont les deux gestes
#: qu'`EPIC11-ARB-89` ajoute a un refus qui n'en offrait qu'un : creer une
#: version voisine, ou supprimer proprement.
ISSUES_NEUVES_DE_LA_LIAISON = ("--nouvelle-version", "project remove")

_MOTIF_DE_LA_LIAISON = re.compile(
    r"\.lots\[\d+\]\.reconstructions\[\d+\]\.(?:%s)$"
    r"|\.sheets_pdfs\[\d+\]\.path$"
    r"|\.sheets_version_watermark$"
    % "|".join(CHAMPS_DE_LA_LIAISON))

#: **(c) Deux criteres d'identite neufs sur le RUSH** -- note 5 de la relecture
#: d'Egan du 2026-09-01, verbatim : « les criteres : duree, base, timecode
#: initial -- **a ajouter a la comparaison ET a stocker** ». La **duree** ne
#: vivait que sur `lots[].source_frame_count`, donc nulle part pour un rush
#: declare et pas encore extrait -- lequel n'a aucun lot. `rushes[]` la porte
#: desormais, avec son drapeau d'exactitude.
#:
#: Ils sont absents du baseline `289f29d` parce qu'ils n'existaient pas encore
#: le jour ou il a ete releve. La tolerance est donc posee **au chemin ET a
#: l'absence** : elle n'excuse qu'une cle que le baseline ne portait pas du
#: tout. Une valeur qui *changerait* sous l'un de ces deux noms -- un cardinal
#: source qui se mettrait a differer entre deux versions du code -- ne serait
#: pas une addition, et continue de rougir.
CRITERES_D_IDENTITE_NEUFS = ("source_frame_count", "source_frame_count_is_exact")

_MOTIF_DES_CRITERES_NEUFS = re.compile(
    r"\.rushes\[\d+\]\.(?:%s)$" % "|".join(CRITERES_D_IDENTITE_NEUFS))


def _critere_d_identite_neuf(chemin, avant) -> bool:
    """`chemin` est-il l'un des deux criteres neufs, ABSENT du baseline ?

    Les deux conditions sont exigees ensemble : sans la seconde, la tolerance
    excuserait aussi un cardinal source qui se serait mis a differer, ce qui
    est un defaut et non une addition.
    """
    return avant is _ABSENT and bool(_MOTIF_DES_CRITERES_NEUFS.search(chemin))


#: **(d) Le NOM d'un tirage porte sa mise en page** -- `EPIC11-ARB-171`
#: (retour A4 d'Egan, 2026-09-02) : `<projet>_<lot>_planches[_vN].pdf` devient
#: `<projet>_<lot>_<Nf-ori>[_vN].pdf`. Le mot `planches` disparait, la mise en
#: page prend sa place, et le nom ne grandit pas (38 caracteres avant, 36
#: apres, sur l'exemple des maquettes).
#:
#: Ce nom se lit a **trois** endroits du releve : le chemin du fichier dans
#: l'arbre du projet, et les lignes de `stdout`, de `stderr` et du journal
#: `makepdf.log` qui le citent. Les trois divergent donc du baseline, et il
#: fallait le dire plutot que d'elargir la comparaison.
#:
#: **La tolerance est posee au NOM, jamais a la ligne**, et c'est ce qui la
#: rend etroite : une ligne n'est excusee que si elle redevient **identique**
#: au baseline une fois les deux noms de tirage remplaces par un jeton. Un mot
#: change ailleurs dans la meme ligne, un chemin deplace, un compte de pages
#: different continuent de rougir.
_NOM_DE_TIRAGE = re.compile(
    r"[\w.\-]+_(?:planches|\d+f-(?:por|pay))(?:_v\d+)?\.pdf")


def _ne_diverge_que_par_le_NOM_du_tirage(avant, apres) -> bool:
    """`apres` est-il `avant` dont le seul ecart est le nom d'un tirage ?

    Le `!=` final n'est pas decoratif : sans lui, deux lignes qui ne portent
    aucun nom de tirage passeraient la tolerance des qu'elles seraient egales
    apres substitution -- c'est-a-dire des qu'elles seraient egales tout court,
    ce que le comparateur ne signale jamais. Il exige que la substitution ait
    reellement mordu.
    """
    if not (isinstance(avant, str) and isinstance(apres, str)):
        return False
    normalise_avant = _NOM_DE_TIRAGE.sub("<tirage>", avant)
    normalise_apres = _NOM_DE_TIRAGE.sub("<tirage>", apres)
    return normalise_avant == normalise_apres != apres


#: **(e) Le RANG DE TIRAGE SCANNE, persiste au manifeste** -- `EPIC11-ARB-176`,
#: tranche par Egan le 2026-09-02 : « un tirage scanne ne peut pas etre
#: ecrase » se mesure **au rang**, jamais au lot. L'etat `SCAN_LOT_STATE` dit
#: qu'un lot a ete scanne ; il ne dit pas **lequel de ses tirages**, si bien
#: que l'interdit refusait d'ecraser un `v4` jamais imprime au seul motif que
#: le `v3` du meme lot avait ete scanne -- le blocage sec sur un objet innocent
#: qu'`EPIC11-ARB-89` proscrit. `lots[].scanned_version_ranks` porte desormais
#: l'ensemble trie et dedoublonne des rangs effectivement lus au QR.
#:
#: **Le champ est ADDITIF, et c'est ce que la tolerance mesure** : elle est
#: posee au chemin **ET a l'absence**, exactement comme la famille (c). Le
#: baseline `289f29d` ne portait pas la cle -- elle n'existait pas le jour ou
#: il a ete releve --, donc son apparition est une addition. Une valeur qui
#: *changerait* sous ce nom, ou la cle disparue, ne sont pas des additions et
#: continuent de rougir.
#:
#: **Ce que la tolerance NE couvre pas, dit plutot que tu** : elle n'excuse
#: rien de ce que le champ pourrait entrainer ailleurs -- un etat de lot
#: bouge, une frame de moins, un code de sortie change resteraient visibles.
#: C'est mesure et non espere : l'ensemble EXACT des chemins qui divergeaient
#: du baseline apres `8fb443e5` etait, sur les vingt scenarios de scan
#: concernes, **exactement** des `lots[N].scanned_version_ranks[N]` et rien
#: d'autre.
CHAMP_DES_RANGS_SCANNES = "scanned_version_ranks"

_MOTIF_DES_RANGS_SCANNES = re.compile(
    r"\.lots\[\d+\]\.%s\[\d+\]$" % CHAMP_DES_RANGS_SCANNES)


def _rang_scanne_neuf(chemin, avant) -> bool:
    """`chemin` est-il un rang de tirage scanne, ABSENT du baseline ?

    Les deux conditions ensemble, pour le motif de `_critere_d_identite_neuf` :
    sans la seconde, la tolerance excuserait aussi un rang qui se serait mis a
    differer d'une version du code a l'autre, ce qui dirait que le depot a
    change d'avis sur QUELLE feuille est passee au scanner -- un defaut, pas
    une addition.
    """
    return avant is _ABSENT and bool(_MOTIF_DES_RANGS_SCANNES.search(chemin))


def _refus_enrichi(avant, apres) -> bool:
    """`apres` est-il `avant` a qui la liaison a AJOUTE une issue ?

    Strictement additif : la ligne doit nommer une issue neuve qu'elle ne
    nommait pas. Un refus devenu succes, un message raccourci ou un motif
    reecrit ne passent pas -- ils ne gagnent aucun de ces deux mots.
    """
    if not (isinstance(avant, str) and isinstance(apres, str)):
        return False
    return any(mot in apres and mot not in avant
               for mot in ISSUES_NEUVES_DE_LA_LIAISON)


#: **(g) LE CONDENSAT D'UNE PLANCHE DONT LE SENS N'A PAS BOUGE** --
#: `EPIC11-ARB-250`, 2026-09-06 : l'encodage QR quitte OpenCV pour `segno`,
#: parce que la ligne 4.10/4.11 d'OpenCV ENCODE un symbole malforme au-dela de
#: la version 7 -- illisible par tout lecteur, y compris `zxing-cpp`. Le papier
#: est perdu a l'impression, pas au scan.
#:
#: **Les deux encodeurs rendent le meme COTE de symbole et pas les memes
#: MODULES.** La geometrie d'impression ne bouge pas d'un module (mesure : 0
#: ecart sur 80 comparaisons cote a cote, quatre niveaux ECC, 1 octet au
#: plafond dur) ; le masque de donnees, lui, differe. L'encre change donc de
#: motif a charge utile, version, niveau ECC et geometrie identiques -- et
#: toute planche gelee OCTET A OCTET diverge.
#:
#: **Ce que cette famille remplace, et c'est le point.** Les deux issues
#: evidentes sont refusees ici, l'une par ce fichier lui-meme :
#:
#: * declarer divergents les scenarios concernes est ce que le commentaire de
#:   `CHAMPS_DE_LA_LIAISON` condamne mot pour mot -- « cesser de mesurer tout
#:   le RESTE de leur sortie, c'est-a-dire exactement ce que ce banc existe
#:   pour tenir » ;
#: * regenerer la reference detruirait ce qu'elle mesure : elle sort du `src/`
#:   du `baseline_commit`, et `test_la_reference_sort_bien_d_un_arbre_ANTERIEUR`
#:   mesure justement qu'elle en sort.
#:
#: La tolerance n'est donc PAS « ce condensat peut differer ». Elle est **« ce
#: condensat peut differer A CONDITION que la planche porte toujours la meme
#: charge utile »** -- une egalite de SENS a la place d'une egalite d'octets,
#: qui est ce que l'AC 10.1 voulait dire depuis le debut : « le scan n'a pas
#: change de comportement » n'a jamais voulu dire « l'encre a le meme motif ».
#:
#: **Elle se reconnait a la FORME**, jamais a une liste de chemins ecrite a la
#: main : un condensat d'artefact de l'arbre, dont le fichier se retrouve par
#: son condensat, dont le suffixe est lisible, et dont les symboles decodes
#: aujourd'hui redonnent **exactement** ce que le baseline a note avoir lu sur
#: cet artefact-la. Un artefact dont le baseline ne dit rien n'est pas excuse.
#:
#: **Ce que cette tolerance coute, dit plutot que tu.** C'est la plus large du
#: banc, et de loin : un condensat est opaque, donc elle ne protege plus les
#: octets de la planche. Une page en moins, une frame deplacee, un libelle
#: reecrit, une pastille de calibration bougee ne changent pas la charge utile
#: du QR et passeraient ici. Trois choses le rattrapent, et deux sont mesurees
#: dans ce fichier :
#:
#: * `test_un_contenu_de_planche_change_HORS_du_QR_fait_ROUGIR` greffe une
#:   planche dont le contenu change sans que le QR change, et verifie que la
#:   tolerance ne l'avale pas ;
#: * `test_la_TOLERANCE_de_la_liaison_n_est_ni_MORTE_ni_TROP_LARGE` mesure
#:   l'ensemble EXACT de ce que toutes les familles avalent ;
#: * la geometrie de la planche, elle, reste tenue ailleurs -- les documents de
#:   detection portent `frame_zones[].crop_rect_px` et `corner_markers[].center_*`
#:   au pixel pres, et ils sont compares champ a champ, hors tolerance. Une
#:   frame deplacee s'y verrait. Le profil de calibration, lui, est **calcule
#:   sur les pixels des pastilles** de la page de calibration : ses
#:   coefficients et son `acceptance` sont compares eux aussi.
#:
#: **Le mecanisme vit dans `sens_des_planches.py`**, pas ici : le banc de
#: `makepdf` porte la meme tolerance sur les memes planches, et une seconde
#: redaction du meme calcul aurait derive. Ce fichier garde la doctrine et sa
#: mesure ; `PlanchesAuMemeSens` garde la reconnaissance.
#: **(h) L'ETIQUETTE que le QR fournit desormais** -- constat de terrain `D2`
#: (2026-09-06). La traduction de vocabulaire ci-dessus rend le NOM du fichier ;
#: il reste ce que le nom vient de : l'etiquette elle-meme, qui etait vide au
#: baseline et qui vaut aujourd'hui le libelle lu sur le QR de la page de
#: calibration.
#:
#: Elle se lit a **trois** endroits du releve, et la famille les reconnait
#: separement plutot que par un motif large :
#:
#: * le champ `label` du document de profil, et son jumeau
#:   `color.calibration_profiles[].label` du manifeste : `""` au baseline,
#:   le libelle aujourd'hui ;
#: * les lignes de journal et de `stderr` qui disaient « sous l'etiquette
#:   `'(aucune)'` » et disent maintenant le libelle ;
#: * la ligne de `stdout` de `calibrate`, qui gagne une phrase entiere --
#:   `Etiquette: '<libelle>'. ` -- inseree devant le reste.
#:
#: **La reconnaissance se fait par RETOUR EN ARRIERE, jamais par « cette ligne
#: peut differer ».** On rend la ligne d'aujourd'hui dans les mots du baseline
#: -- l'insertion retiree, le libelle rendu a `(aucune)` -- et on exige
#: l'egalite **exacte** avec la ligne du baseline. Un mot change ailleurs dans
#: la meme ligne, un cardinal de pastilles qui bouge, un chemin deplace : rien
#: de tout cela ne survit au retour en arriere, et la tolerance ne l'avale pas.
LIBELLE_DE_CHAINE_DU_DOSSIER = "hp envy 4520 tiff 600 dpi auto corr off"

#: Ce que le baseline imprimait la ou il n'y avait pas d'etiquette.
ETIQUETTE_ABSENTE_AU_BASELINE = "(aucune)"

#: La phrase que `calibrate` insere aujourd'hui dans son `stdout`.
PHRASE_D_ETIQUETTE = f"Etiquette: '{LIBELLE_DE_CHAINE_DU_DOSSIER}'. "

_MOTIF_DU_CHAMP_D_ETIQUETTE = re.compile(r"\.label$")

#: La SECONDE lecture de la meme famille, employee par le temoin d'exactitude
#: et par lui seul. Elle **masque par expression reguliere** la ou
#: l'implementation ci-dessus rend en arriere par substitutions litterales, et
#: surtout elle **ignore laquelle des deux formes est l'ancienne** : elle
#: accepte n'importe quel libelle entre apostrophes dans la phrase d'etiquette.
#: C'est ce qui en fait une seconde redaction et non une recopie.
_PHRASE_D_ETIQUETTE_QUELCONQUE = re.compile(r"Etiquette: '[^']*'\. ")
_LIBELLE_OU_SON_ABSENCE = re.compile(
    r"'(?:%s|%s)'" % (re.escape(ETIQUETTE_ABSENTE_AU_BASELINE),
                      re.escape(LIBELLE_DE_CHAINE_DU_DOSSIER)))


def _sans_l_etiquette(texte: str) -> str:
    """Le texte prive de tout ce que `D2` y a mis.

    La phrase inseree est **retiree** et non tokenisee : le baseline ne porte
    rien a sa place, donc un jeton ne les rendrait jamais egaux -- c'est la
    difference entre une insertion et une substitution, et la premiere
    redaction de ce temoin s'y est trompee.
    """
    return _LIBELLE_OU_SON_ABSENCE.sub(
        "<ETIQUETTE>", _PHRASE_D_ETIQUETTE_QUELCONQUE.sub("", texte))


def _rendu_dans_les_mots_du_baseline(ligne: str) -> str:
    """La ligne d'aujourd'hui, l'etiquette remise dans l'etat du baseline."""
    return (ligne
            .replace(PHRASE_D_ETIQUETTE, "")
            .replace(f"'{LIBELLE_DE_CHAINE_DU_DOSSIER}'",
                     f"'{ETIQUETTE_ABSENTE_AU_BASELINE}'"))


def _etiquette_lue_sur_le_QR(chemin, avant, apres) -> bool:
    """`apres` est-il `avant` a qui `D2` a seulement ajoute l'etiquette ?"""
    if avant is _ABSENT or apres is _ABSENT:
        return False
    if not (isinstance(avant, str) and isinstance(apres, str)):
        return False
    if _MOTIF_DU_CHAMP_D_ETIQUETTE.search(chemin):
        return avant == "" and apres == LIBELLE_DE_CHAINE_DU_DOSSIER
    rendu = _rendu_dans_les_mots_du_baseline(apres)
    # `rendu != apres` interdit la vacuite : une ligne que le retour en arriere
    # ne touche pas ne doit rien a `D2`, et son ecart vient d'ailleurs.
    return rendu != apres and rendu == avant


#: **(h) LE DOSSIER DE SCAN QUE LE PROFIL DECLARE** -- `EPIC11-ARB-262`,
#: tranche par Egan le 2026-09-07 sur un constat de terrain, verbatim : « Le
#: scan de la page de calibration apparait en non declare alors que je l'ai
#: importe au projet. » Le document de profil porte desormais un champ de plus,
#: `scan_dir`, chemin relatif POSIX du dossier de scan dont il est issu. C'est
#: par lui que l'inventaire sort une mire de ses orphelins -- **par identite et
#: non par ressemblance** : le profil NOMME son dossier, la ou un fragment de
#: nom ou l'absence d'`ingest.json` auraient rendu invisible un vrai lot de
#: planches.
#:
#: Il est absent du baseline `289f29d` parce qu'il n'existait pas le jour ou il
#: a ete releve. La tolerance est donc posee **au chemin ET a l'absence**,
#: exactement comme les familles (c) et (e) : elle n'excuse qu'une cle que le
#: baseline ne portait pas du tout. Un `scan_dir` qui *changerait* de valeur
#: d'une version du code a l'autre dirait que le depot a change d'avis sur
#: **d'ou vient** un profil -- un defaut, pas une addition -- et continue de
#: rougir.
#:
#: **Et elle est posee a la FORME de la valeur, ce que (c) et (e) ne font
#: pas.** Les deux precedentes excusent un cardinal ou un rang, dont toute
#: valeur est plausible ; celle-ci excuse un CHEMIN, et un chemin a une forme
#: que l'arbitrage declare : relatif, POSIX, non vide. Les quatre refus sont
#: ceux que `_validate_scan_dir` oppose deja cote code -- absolu, lecteur
#: Windows, remontee `..`, antislash --, **reecrits ici** plutot que importes :
#: le jour ou la garde du module se relacherait, ce banc doit rougir au lieu
#: d'heriter du relachement. Une valeur vide est refusee aussi, pour un motif
#: distinct : `-262` promet d'ecrire le dossier, et un champ vide serait la
#: moitie du correctif qui manque -- exactement le faux orphelin qu'il ferme.
#:
#: **Ce que la tolerance NE couvre pas, dit plutot que tu** : elle n'excuse
#: rien de ce que le champ entraine ailleurs. L'entree autoportante du manifeste
#: ne le recopie pas -- `profile_designation.ENTRY_DOCUMENT_FIELDS` et
#: `ENTRY_OPTIONAL_DOCUMENT_FIELDS` sont une liste blanche ou `scan_dir` ne
#: figure pas, et la mesure le confirme : aucun chemin
#: `color.calibration_profiles[]` ne diverge. Le jour ou il y entrerait, ce
#: banc rougirait, et ce serait juste.
CHAMP_DU_DOSSIER_DE_SCAN = "scan_dir"

#: Le chemin, **ancre des deux bouts** : un document de profil du projet, sous
#: `versions/calibration/`, et le champ lui-meme en feuille. Un motif non ancre
#: aurait avale un `scan_dir` apparu n'importe ou ailleurs dans le releve --
#: dans un manifeste, dans un document de detection, dans une ligne de journal.
_MOTIF_DU_DOSSIER_DE_SCAN = re.compile(
    r"\Aprojet\.documents\.versions/calibration/[^/]+\.json\.%s\Z"
    % CHAMP_DU_DOSSIER_DE_SCAN)

#: Un lecteur Windows en tete (`C:`), refuse au meme titre qu'un chemin absolu.
_LECTEUR_WINDOWS = re.compile(r"\A[A-Za-z]:")


def _dossier_de_scan_declare(chemin, avant, apres) -> bool:
    """`chemin` est-il un `scan_dir` NEUF, portant un dossier relatif POSIX ?

    Les trois conditions sont exigees ensemble, et chacune ferme une facon pour
    la tolerance de devenir muette :

    * `avant is _ABSENT` -- sans elle, elle excuserait un dossier de scan qui
      se serait mis a differer, ce qui est un changement de provenance ;
    * le chemin ancre -- sans lui, un champ homonyme apparu ailleurs passerait ;
    * la forme de la valeur -- sans elle, un `scan_dir` absolu, vide ou
      remontant hors du projet passerait, alors que chacun de ces quatre-la
      rouvre le faux orphelin que `-262` ferme, et sur les machines ou personne
      ne le mesure.
    """
    if avant is not _ABSENT:
        return False
    if not _MOTIF_DU_DOSSIER_DE_SCAN.match(chemin):
        return False
    return _forme_par_DECOUPAGE(apres)


def _forme_par_DECOUPAGE(valeur) -> bool:
    """La PREMIERE redaction du predicat de forme : decoupage et motif ancre.

    Elle repond a « cette valeur nomme-t-elle un dossier du projet ? » en
    DECOUPANT la chaine sur les barres obliques et en appliquant une expression
    reguliere ancree au premier segment qui nomme quelque chose.
    :func:`_est_un_dossier_relatif_POSIX` repond a la meme question en decomposant
    par `PurePosixPath` et en interrogeant l'objet ; les deux sont confrontees sur
    une famille CONSTRUITE par
    :func:`test_la_TOLERANCE_du_DOSSIER_DE_SCAN_n_avale_QUE_le_dossier_declare`.

    **Le residu que cette redaction laissait passer** (finding `B3` de la revue du
    2026-09-07) : les segments qui ne NOMMENT rien. `'.'`, `'./'`, `'.//.'`
    designent le dossier projet, qui n'est aucun objet de l'inventaire -- les
    avaler revenait a excuser un `scan_dir` qui ne declare rien, c'est-a-dire le
    faux orphelin qu'`EPIC11-ARB-262` ferme. La derniere ligne l'exige donc
    explicitement : au moins un segment qui ne soit ni vide ni `'.'`.

    **Le lecteur Windows se juge sur le premier segment NOMMANT**, pas sur la tete
    de la chaine : `'./C:/scans'` est un lecteur tout autant que `'C:/scans'`, et
    la premiere redaction ne le voyait pas -- l'ancrage portait sur la chaine
    entiere.
    """
    if not isinstance(valeur, str) or not valeur:
        return False
    if valeur.startswith("/") or "\\" in valeur:
        return False
    segments = [segment for segment in valeur.split("/")
                if segment not in ("", ".")]
    if not segments:
        return False
    if ".." in segments:
        return False
    return not _LECTEUR_WINDOWS.match(segments[0])


#: **(h) LES OCTETS D'UNE FRAME EXTRAITE NE SE COMPARENT PAS D'UN CPU A
#: L'AUTRE** -- huitieme famille, posee le 2026-09-08 apres le run 8 de la CI
#: publique.
#:
#: LE FAIT, MESURE ICI et non suppose. ffmpeg choisit ses noyaux SIMD au
#: LANCEMENT, selon ce que le processeur annonce. Meme build 6.1.1-3ubuntu5,
#: meme rush, meme commande, `-cpuflags 0` pour seule difference :
#:
#:   * l'ENCODAGE du rush rend d'autres octets (487d1d47 contre bd8a1c9e),
#:     et cela A NOMBRE DE FILS IDENTIQUE -- c'est pourquoi epingler
#:     `-threads` etait necessaire mais pas suffisant ;
#:   * le DECODAGE des frames rend d'autres pixels : ecart maximal de
#:     **2 codes 8 bits**, sur **38 % des pixels**.
#:
#: Deux codes sur 255 sont invisibles a l'oeil, mais ils changent le
#: SHA-256 -- et c'est par un SHA-256 que ce banc compare un raster.
#:
#: POURQUOI UNE FAMILLE ET NON UNE TOLERANCE. Le baseline n'enregistre que des
#: CONDENSATS : il n'y a pas de pixels a comparer avec une tolerance, et il n'y
#: en aura qu'a la prochaine regeneration de la reference. Une tolerance
#: numerique n'est donc pas exprimable ici, la ou elle l'etait pour le plancher
#: des flottants.
#:
#: CE QUE CETTE FAMILLE PERD, dit plutot que tu : les OCTETS d'une frame
#: extraite ne sont plus mesures contre le baseline. Ce qui reste mesure : leur
#: PRESENCE, leur nom, leur compte, et tout le reste du scenario -- manifeste,
#: journaux, code de sortie, planches imprimees. La famille exige que les deux
#: cotes soient presents, si bien qu'une frame qui DISPARAIT ou qui APPARAIT
#: fait toujours rougir. L'entree `RUN8-N1` de `deferred-work.md` porte la
#: reprise : une signature tolerante, a la prochaine regeneration.
_MOTIF_DE_LA_FRAME_EXTRAITE = re.compile(r"(?:^|\.)arbre\.extract-frames/")

#: Les suffixes de raster que la famille (h) couvre, et eux seuls : un
#: manifeste JSON depose dans le meme dossier reste compare au bit pres.
SUFFIXES_DE_RASTER_EXTRAIT = (".tiff", ".tif", ".png")


def _frame_extraite_dont_le_DECODAGE_depend_du_CPU(chemin, gauche, droite):
    """La huitieme famille, et elle est ETROITE de trois facons.

    Elle exige : le dossier `extract-frames/`, un suffixe de raster, et les
    deux cotes PRESENTS et porteurs d'un condensat. Une frame absente d'un
    cote, un manifeste JSON du meme dossier, ou une valeur qui ne serait pas
    un condensat retombent tous sur la comparaison stricte.
    """
    if not _MOTIF_DE_LA_FRAME_EXTRAITE.search(chemin):
        return False
    if not chemin.lower().endswith(SUFFIXES_DE_RASTER_EXTRAIT):
        return False
    if gauche is _ABSENT or droite is _ABSENT:
        return False
    return bool(_MASQUE_D_UN_CONDENSAT.fullmatch(str(gauche))
                and _MASQUE_D_UN_CONDENSAT.fullmatch(str(droite)))


def divergents_hors_liaison(gauche, droite, planches=None) -> set:
    """Les chemins divergents, prives de ce que la liaison a legitimement
    change -- les **sept** familles ci-dessus, et elles seules.

    Le cardinal etait reste a « cinq » alors que le fichier en portait six
    (corrige le 2026-09-07, en posant la septieme) : un compte ecrit en prose
    ne se mesure pas, et celui-la avait deja peri. Ce qui se mesure, en
    revanche, c'est leur reunion -- `test_la_TOLERANCE_de_la_liaison_n_est_ni_
    MORTE_ni_TROP_LARGE` exige que ce que le filtre avale soit EXACTEMENT
    l'union des familles recalculees par des predicats ecrits autrement. Une
    famille ajoutee ici sans y etre ajoutee la-bas fait rougir.

    `planches` est la cinquieme et elle est **facultative** : sans elle, la
    tolerance de condensat n'existe pas. Les comparaisons de ce banc qui ne
    portent pas sur des planches (un code de sortie, un verbe d'inventaire) ne
    la passent donc pas, et ne peuvent pas en heriter par accident.
    """
    a, b = _aplatir(gauche), _aplatir(droite)
    return {chemin for chemin in chemins_divergents(gauche, droite)
            if not _MOTIF_DE_LA_LIAISON.search(chemin)
            and not _critere_d_identite_neuf(chemin, a.get(chemin, _ABSENT))
            and not _rang_scanne_neuf(chemin, a.get(chemin, _ABSENT))
            and not (planches is not None
                     and planches.au_meme_SENS(a.get(chemin, _ABSENT),
                                               b.get(chemin, _ABSENT)))
            and not _refus_enrichi(a.get(chemin, _ABSENT),
                                   b.get(chemin, _ABSENT))
            and not _etiquette_lue_sur_le_QR(chemin, a.get(chemin, _ABSENT),
                                             b.get(chemin, _ABSENT))
            and not _dossier_de_scan_declare(chemin, a.get(chemin, _ABSENT),
                                             b.get(chemin, _ABSENT))
            and not _frame_extraite_dont_le_DECODAGE_depend_du_CPU(
                chemin, a.get(chemin, _ABSENT), b.get(chemin, _ABSENT))}


@pytest.fixture(scope="module")
def passe(tmp_path_factory):
    """Le releve d'aujourd'hui, joue une seule fois pour tout le module.

    Les entrees sont refabriquees ici par les fabriques du depot : ce sont les
    memes octets que ceux qu'a lus la reference, la fabrique etant deterministe
    (verifie : deux passes rendent des TIFF identiques).

    Rend le couple `(dossier, travail)` : le second sert au parcours des codes
    de sortie plus bas, qui rejoue `mmu scan write` sur le socle deja monte
    plutot que d'en remonter un septieme.
    """
    base = tmp_path_factory.mktemp("identite-scan")
    entrees = fabriques.fabriquer(base / "entrees")
    travail = base / "travail"
    return outils.collecter(entrees, travail), travail


@pytest.fixture(scope="module")
def releve(passe) -> dict:
    return passe[0]


@pytest.fixture(scope="module")
def planches(passe) -> PlanchesAuMemeSens:
    """La cinquieme famille, dressee une fois pour tout le module.

    Elle decode les planches de l'arbre de travail : ~4 s pour les sept que la
    liaison fait diverger. La dresser par scenario couterait 42 fois ca pour
    le meme resultat -- une planche est un fichier, pas un scenario.

    **`ecarter` lui retire ce que la famille (h) tient deja.** Sans lui, elle
    se prononcerait aussi sur les frames extraites -- qui divergent sur une
    machine dont le CPU n'offre pas les memes noyaux SIMD a ffmpeg --, les
    REFUSERAIT faute de QR a y decoder, et ferait rougir sa propre mesure
    d'exactitude sur cette machine-la seulement. C'est ce qui est arrive au
    job 3.12 du run 34222962404, vert en 3.11 et 3.13 sur le meme arbre.
    """
    releve_du_jour, travail = passe
    return PlanchesAuMemeSens(_reference()["scenarios"],
                              releve_du_jour["scenarios"], travail,
                              aplatir=_aplatir,
                              ecarter=_frame_extraite_dont_le_DECODAGE_depend_du_CPU)


# ===========================================================================
# Les temoins : ce qui rougit si le banc cesse d'observer
# ===========================================================================

def test_le_COMPARATEUR_voit_les_TROIS_formes_de_divergence():
    """Le banc du banc. Sans lui, les egalites d'ensembles ci-dessous
    pourraient etre vertes parce que le comparateur ne voit rien.

    Les trois formes ne se confondent pas : une valeur changee, une cle
    **presente d'un seul cote**, et une **permutation** de liste -- l'ordre des
    lignes imprimees fait partie de ce que la commande dit, et un aplatissement
    qui l'ignorerait laisserait passer un message deplace.
    """
    reference = {"code": 0, "stdout": ["a", "b"]}

    assert chemins_divergents(reference, {"code": 1, "stdout": ["a", "b"]}) \
        == {"code"}
    assert chemins_divergents(reference,
                              {"code": 0, "stdout": ["a", "b"], "err": []}) \
        == {"err"}
    assert chemins_divergents(reference, {"code": 0, "stdout": ["b", "a"]}) \
        == {"stdout[0]", "stdout[1]"}
    assert chemins_divergents(reference, reference) == set()


def test_la_REFERENCE_sort_bien_d_un_arbre_D_AVANT_le_lot_S1():
    """Volet symetrique, et c'est le seul qui protege de la pire des erreurs.

    Une reference regeneree par megarde depuis le depot **d'aujourd'hui** serait
    identique a la passe d'aujourd'hui pour la plus mauvaise des raisons, et
    aucune comparaison de scenarios ne pourrait le voir. Deux faits la trahissent,
    et ce sont exactement ceux que le lot S1 a changes : `scan_write.py`
    **n'existe pas** avant lui, et `cli.py` y est plus long de la sequence
    entiere.
    """
    provenance = _reference()["provenance"]
    assert provenance["scan_write_present"] is False, (
        f"la reference {REFERENCE.name} porte deja le module de coeur du lot "
        "S1 : elle n'a pas ete jouee sous le src du baseline "
        f"{BASELINE}, et la comparaison ne mesure plus rien")
    assert provenance["lignes_de_cli"] > outils.provenance()["lignes_de_cli"], (
        "le `cli.py` de la reference doit etre PLUS LONG que celui "
        "d'aujourd'hui : c'est la sequence d'ecriture qui en est partie")
    assert outils.provenance()["scan_write_present"] is True
    assert provenance["rendu_pdf_gele"] is True, (
        "la reference a ete produite sans le gel du rendu PDF : ses PDF ne "
        "sont pas comparables octet a octet, et la comparaison du bloc "
        "`makepdf` divergerait pour une raison qui n'est pas le code")


@pytest.mark.parametrize(
    "retire,motif,brut,neuf,sur_les_cles,cardinal,avant,apres",
    TRADUCTIONS_DU_VOCABULAIRE)
def test_la_TRADUCTION_MORD_le_nombre_EXACT_de_fois(
        retire, motif, brut, neuf, sur_les_cles, cardinal, avant, apres):
    """Story 11.14, C3 -- la traduction se mesure, elle ne se declare pas.

    **Une mesure par segment renomme**, jamais une seule pour les deux : un
    cardinal global serait juste alors qu'une des deux traductions serait morte
    et l'autre deux fois trop large.

    Le cardinal est confronte au compte BRUT du litteral dans le fichier de
    reference. Les deux coincident parce que **toutes** les occurrences sont
    des segments de chemin ; si l'une cessait d'en etre un -- un mot du
    vocabulaire tombant dans une phrase plutot que dans un chemin --, les deux
    nombres divergeraient, et c'est exactement ce qu'il faudrait savoir.
    """
    compteur: dict = {}
    _traduire_le_vocabulaire(_reference_brute(), compteur)
    assert compteur.get(retire, 0) == cardinal, compteur

    dans_le_fichier = len(
        re.findall(brut, REFERENCE.read_text(encoding="utf-8")))
    assert dans_le_fichier == cardinal, (
        f"{dans_le_fichier} occurrences de {retire!r} dans le fichier pour "
        f"{cardinal} "
        "substitutions : une occurrence n'est pas un segment de chemin, et la "
        "traduction la laisse passer en silence")


@pytest.mark.parametrize(
    "retire,motif,brut,neuf,sur_les_cles,cardinal,avant,apres",
    TRADUCTIONS_DU_VOCABULAIRE)
def test_la_reference_TRADUITE_ne_porte_plus_AUCUN_nom_retire(
        retire, motif, brut, neuf, sur_les_cles, cardinal, avant, apres):
    """Volet symetrique du precedent : le compte pourrait etre juste et le
    travail inacheve si une occurrence echappait au motif."""
    traduite = json.dumps(_reference(), ensure_ascii=False, sort_keys=True)
    restants = re.findall(brut, traduite)
    assert restants == [], f"{len(restants)} occurrence(s) de {retire!r}"


@pytest.mark.parametrize("voisin", [
    # La CLE de manifeste, qui ne bouge PAS (`EPIC11-ARB-221`).
    "lots[0].output_frames_dir",
    # Les noms NEUFS, qui ne doivent pas etre traduits une seconde fois.
    "frames-scannees/rush-ident_5/scan.tiff",
    "extract-frames/rush_ident_5/f.tiff",
    # Des voisins de sous-chaine : une traduction par `str.replace` les
    # casserait.
    "output-frames-bis/rush-ident_5/scan.tiff",
    "vieux-output-frames/scan.tiff",
    # Le mot dans une PHRASE : ce n'est pas un chemin, il ne se traduit pas.
    "12 frames extraites dans <PROJET>",
    "sheet_frames",
])
def test_la_TRADUCTION_ne_touche_ni_les_CLES_ni_un_nom_VOISIN(voisin):
    """Une traduction par sous-chaine renommerait ces sept-la, et c'est le
    defaut n°2 du lot A -- `lot` attrapait `slot`, `patch` attrapait
    `patch_preset_id`. Ici la cle de manifeste echappe au motif par le
    souligne, les chemins voisins par la frontiere de segment, et la phrase par
    l'exigence du slash."""
    compteur: dict = {}
    assert _traduire_le_vocabulaire({voisin: voisin}, compteur) == {voisin: voisin}
    assert sum(compteur.values()) == 0, compteur


#: Cinq chemins **distinguables** -- pas un remplissage uniforme : une
#: permutation ou une troncature ne se voit pas autrement (regle des fabriques,
#: points 1 et 4 de `CLAUDE.md`).
def test_une_CLE_nommee_frames_ne_bouge_PAS_quand_sa_VALEUR_bouge():
    """`EPIC11-ARB-221` mesure a l'endroit exact ou il mord.

    Le manifeste POC de `cli.py` (`_build_sheet_manifest`) porte
    `"inputs": {"frames": "frames/"}` : **la cle et la valeur portent le meme
    mot et n'ont pas le meme sort**. Renommer la cle casserait la lecture des
    projets deja sur disque -- et aucune commande de conversion n'existe
    (`EPIC11-ARB-222`) ; laisser la valeur designerait un dossier qui n'existe
    plus.

    Sans ce test, la garde `sur_les_cles` de la table serait une declaration :
    la reference ne porte aujourd'hui aucune cle egale a `frames`, donc aucune
    mesure sur elle ne verrait la garde disparaitre.
    """
    compteur: dict = {}
    traduit = _traduire_le_vocabulaire(
        {"inputs": {"frames": "frames/", "raw": "inputs/"}}, compteur)
    assert set(traduit["inputs"]) == {"frames", "raw"}, (
        "la CLE `frames` a ete traduite : EPIC11-ARB-221 l'interdit")
    assert traduit["inputs"]["frames"] == "extract-frames/"
    assert traduit["inputs"]["raw"] == "inputs/"


_VALEURS_TEMOINS = (
    "scans/lot-a",
    "outputs",
    "12 frames extraites dans <PROJET>",
    "planches/mire.pdf",
    "versions/calibration",
)

#: Cinq chemins d'arbre, distinguables pour le meme motif.
_ARBRE_TEMOIN = (
    "scans/lot-a/page-01.tiff",
    "versions/calibration/alpha.json",
    "logs/scan.log",
    "outputs/rush-ident_5_mmu.mov",
    "planches/mire.pdf",
)


@pytest.mark.parametrize(
    "retire,motif,brut,neuf,sur_les_cles,cardinal,avant,apres",
    TRADUCTIONS_DU_VOCABULAIRE)
@pytest.mark.parametrize("position", [0, 2, 4])
def test_la_TRADUCTION_MORD_a_CHAQUE_BORD(
        retire, motif, brut, neuf, sur_les_cles, cardinal, avant, apres,
        position):
    """Regle des fabriques, point 4 (2026-09-03) -- en TETE et en QUEUE.

    « La cible au milieu demasque un `find` fautif ; elle ne demasque pas un
    balayage tronque. » Un parcours qui sauterait la premiere ou la derniere
    entree d'un document resterait vert sur une cible au milieu -- et l'arbre
    d'un scenario reel porte des dizaines d'entrees, dont celles des dossiers
    renommes ne sont ni les premieres ni les dernieres.

    La cible est posee en **valeur**, forme qui vaut pour les trois lignes : la
    troisieme ne porte que la, par `EPIC11-ARB-221`.
    """
    document = {
        f"champ_{rang}": (avant if rang == position else valeur)
        for rang, valeur in enumerate(_VALEURS_TEMOINS)
    }
    compteur: dict = {}
    traduit = _traduire_le_vocabulaire(document, compteur)
    assert compteur.get(retire, 0) == 1, compteur
    assert traduit[f"champ_{position}"] == apres, (
        f"la traduction de {retire!r} rate la cible en position {position} "
        f"sur {len(_VALEURS_TEMOINS)}")
    # ... et elle n'a touche a rien d'autre.
    for rang, valeur in enumerate(_VALEURS_TEMOINS):
        if rang != position:
            assert traduit[f"champ_{rang}"] == valeur


@pytest.mark.parametrize(
    "retire,motif,brut,neuf,sur_les_cles,cardinal,avant,apres",
    [ligne for ligne in TRADUCTIONS_DU_VOCABULAIRE if ligne[4]])
@pytest.mark.parametrize("position", [0, 2, 4])
def test_la_TRADUCTION_DES_CLES_MORD_aussi_a_CHAQUE_BORD(
        retire, motif, brut, neuf, sur_les_cles, cardinal, avant, apres,
        position):
    """Le meme bord, mais sur les CLES de l'arbre des artefacts.

    C'est la que vit le nom du dossier : l'arbre est un `chemin -> condensat`,
    et une traduction qui ne porterait que sur les feuilles laisserait chaque
    fichier renomme diverger deux fois -- absent d'un cote, present de l'autre.
    Seules les lignes declarees valables sur les cles sont parametrees ici.
    """
    arbre = {
        (avant if rang == position else chemin): f"condensat-{rang}"
        for rang, chemin in enumerate(_ARBRE_TEMOIN)
    }
    compteur: dict = {}
    traduit = _traduire_le_vocabulaire({"projet": {"arbre": arbre}}, compteur)
    assert compteur.get(retire, 0) == 1, compteur
    assert traduit["projet"]["arbre"][apres] == f"condensat-{position}", (
        f"la traduction de {retire!r} rate la cible en position {position} "
        f"sur {len(_ARBRE_TEMOIN)}")
    for rang, chemin in enumerate(_ARBRE_TEMOIN):
        if rang != position:
            assert traduit["projet"]["arbre"][chemin] == f"condensat-{rang}"


def test_le_RELEVE_d_aujourd_hui_observe_reellement_quelque_chose(releve):
    """Un releve vide comparerait deux riens et serait vert.

    Les cardinaux ne sont pas des seuils de confort : ils bornent par le bas ce
    que le dossier doit contenir pour que les egalites ci-dessous portent sur
    des artefacts, des messages et des journaux reels.
    """
    scenarios = releve["scenarios"]
    assert sorted(scenarios) == NOMS

    fichiers = sum(len(s["projet"]["arbre"]) for s in scenarios.values())
    lignes = sum(len(s["stdout"]) + len(s["stderr"])
                 for s in scenarios.values())
    journal = sum(len(v) for s in scenarios.values()
                  for v in s["projet"]["journaux"].values())
    feuilles = sum(len(v) for s in scenarios.values()
                   for v in s["projet"]["documents"].values())

    assert fichiers > 200, fichiers
    assert lignes > 150, lignes
    assert journal > 500, journal
    assert feuilles > 10000, feuilles
    # **Les trois codes que le dossier doit porter, ecrits en clair** (story
    # 11.4c, lot V2). Le `4` est le succes partiel : il est recopie ici plutot
    # que lu de `scan_write.CODE_SUCCES_PARTIEL`, pour la meme raison que
    # `CODE_DU_BASELINE` plus bas -- lire la constante que l'on mesure ferait un
    # test tautologique, exactement le defaut trouve par la campagne de la
    # story 5.9 sur la constante centrale de la calibration.
    #
    # L'assertion reste celle de l'**ensemble** : un quatrieme code apparu, ou
    # le succes partiel disparu, la fait rougir toutes les deux.
    assert {s["code"] for s in scenarios.values()} == {0, 1, 4}, (
        "le releve doit porter des succes, des refus ET le succes partiel : "
        "un dossier qui n'aurait que des succes ne mesurerait aucun code de "
        "refus, et un dossier sans le `4` ne mesurerait plus le pont entre "
        "l'inventaire d'avertissements et le code de sortie (AC 9)")


#: Les scenarios ou une invite `Y/N` **doit** etre posee, et laquelle. C'est la
#: table du temoin ci-dessous : elle est ecrite en toutes lettres pour que
#: l'absence d'une invite soit un echec, et non un silence.
INVITES_ATTENDUES = {
    "21_invite_TERMINAL_entree_vide": ("Appliquer la correction couleur",),
    "22_invite_TERMINAL_oui": ("Appliquer la correction couleur",),
    "23_invite_TERMINAL_non": ("Appliquer la correction couleur",),
    "42_ecrasement_TERMINAL_oui": ("Un profil porte deja ce nom",
                                   "Appliquer la correction couleur"),
    "43_ecrasement_TERMINAL_non": ("Un profil porte deja ce nom",
                                   "Appliquer la correction couleur"),
}

#: Les deux phrases d'invite du chemin de scan. Elles sont cherchees dans TOUS
#: les scenarios : c'est la moitie negative du temoin, celle qui mesure les
#: regimes 1 et 2 (drapeau explicite, hors terminal) -- une invite posee la
#: serait un blocage de script, et le banc doit la voir.
PHRASES_D_INVITE = ("Appliquer la correction couleur", "Un profil porte deja ce nom")


@pytest.mark.parametrize("nom", NOMS)
def test_les_invites_sont_posees_LA_OU_ELLES_DOIVENT_et_NULLE_PART_ailleurs(
        releve, nom):
    """AC 2.2, les trois regimes -- mesures sur ce qui est **imprime**.

    Sans ce temoin, les egalites de `stdout` ci-dessous seraient vertes meme si
    les deux invites avaient disparu **des deux cotes** : la comparaison ne
    distingue pas « la meme question » de « aucune question ». La table
    ci-dessus dit donc, scenario par scenario, quelle invite doit sortir -- et
    l'assertion porte sur l'**ensemble**, donc une invite en trop dans un
    regime non interactif la fait rougir aussi.
    """
    imprime = "\n".join(releve["scenarios"][nom]["stdout"])
    vues = {phrase for phrase in PHRASES_D_INVITE if phrase in imprime}
    assert vues == set(INVITES_ATTENDUES.get(nom, ())), (
        f"{nom} : invites vues {sorted(vues)}, attendues "
        f"{sorted(INVITES_ATTENDUES.get(nom, ()))}")


def test_les_REGIMES_de_l_invite_produisent_des_ARTEFACTS_differents(releve):
    """Le dernier temoin, et le plus important : les regimes se distinguent.

    Si repondre « non » a la correction produisait les memes octets que
    repondre « oui », les six scenarios du bloc 2 mesureraient six fois la meme
    chose et l'egalite avec la reference ne dirait rien de l'invite. La mesure
    porte sur les **frames produites**, pas sur l'objet de retour.

    Meme geste sur l'invite d'ecrasement : « oui » ecrase le profil en place,
    « non » et l'absence de terminal en ecrivent un second sous une empreinte
    differenciante -- ce sont deux **listes de fichiers** differentes.
    """
    scenarios = releve["scenarios"]
    applique = scenarios["21_invite_TERMINAL_entree_vide"]["projet"]["arbre"]
    brut = scenarios["23_invite_TERMINAL_non"]["projet"]["arbre"]
    assert set(applique) == set(brut), "les deux regimes ecrivent les memes noms"
    assert applique != brut, (
        "repondre « non » a l'invite de correction doit changer les octets des "
        "frames : sinon l'invite n'a aucun effet observable et le banc ne "
        "mesure rien")

    profils = lambda nom: sorted(
        chemin for chemin in scenarios[nom]["projet"]["documents"]
        if chemin.startswith("versions/calibration/"))
    assert len(profils("42_ecrasement_TERMINAL_oui")) == 2, (
        "« oui » ecrase le profil homonyme : le projet en garde deux")
    assert len(profils("43_ecrasement_TERMINAL_non")) == 3, (
        "« non » garde les deux profils sous deux noms : le projet en a trois")
    assert profils("41_ecrasement_HORS_TERMINAL") == \
        profils("43_ecrasement_TERMINAL_non"), (
        "hors terminal, le defaut est celui de « non » -- jamais l'ecrasement")


# ===========================================================================
# AC 10.1 -- l'identite, scenario par scenario puis en bloc
# ===========================================================================

@pytest.mark.parametrize("nom", NOMS)
def test_l_invocation_rend_EXACTEMENT_ce_qu_elle_rendait_au_baseline(
        releve, planches, nom):
    """AC 10.1, sur une invocation : code, messages, artefacts, journaux.

    L'assertion est celle de l'**ensemble** des chemins divergents, et elle est
    vide. Un test qui n'affirmerait que l'egalite des codes de sortie serait
    vert sur une commande dont chaque message aurait change ; un test qui
    comparerait les deux structures par `==` dirait qu'elles different sans
    jamais dire ou, sur un scenario qui porte jusqu'a mille feuilles de
    document.
    """
    attendu = _reference()["scenarios"][nom]
    obtenu = releve["scenarios"][nom]
    divergents = divergents_hors_liaison(attendu, obtenu, planches)
    if nom in DIVERGENCE_ATTENDUE:
        if nom in DIVERGENCE_L18:
            ligne = "L18"
        elif nom in DIVERGENCE_L25:
            ligne = "L25"
        else:
            ligne = "AC 9 de la story 11.4c"
        assert divergents, (
            f"{nom} est declare divergent (ligne {ligne} du document de "
            "liaison) et ne diverge plus : c'est la ligne de liaison qui ment, "
            "ou le scenario qui a cesse de faire ce qu'on lui demande")
        return
    assert divergents == set(), (
        f"{nom} : {len(divergents)} chemin(s) divergent du baseline "
        f"{BASELINE} -- " + "; ".join(
            f"{chemin}: {_aplatir(attendu).get(chemin, _ABSENT)!r} -> "
            f"{_aplatir(obtenu).get(chemin, _ABSENT)!r}"
            for chemin in sorted(divergents)[:8]))


def test_l_ENSEMBLE_des_scenarios_qui_divergent_est_EXACTEMENT_le_declare(
        releve, planches):
    """La mesure en bloc, et elle n'est pas redondante avec la precedente.

    Le parametrage ci-dessus ne peut comparer que les scenarios que la
    **reference** nomme. Celui-ci mesure en plus qu'aucun scenario n'a disparu
    ni n'est apparu -- un releve ampute passerait l'un sans passer l'autre --,
    et il pose l'assertion sous la seule forme qui vaille : l'**ensemble** des
    scenarios divergents, egal a l'ensemble declare. Une assertion positive
    (« celui-la diverge ») laisserait passer toute divergence supplementaire.
    """
    attendu = _reference()["scenarios"]
    obtenu = releve["scenarios"]
    assert sorted(attendu) == sorted(obtenu), (
        "le releve d'aujourd'hui et la reference ne portent pas les memes "
        "scenarios : "
        f"{sorted(set(attendu) ^ set(obtenu))}")

    divergents = {nom for nom in attendu
                  if divergents_hors_liaison(attendu[nom], obtenu[nom],
                                             planches)}
    assert divergents == DIVERGENCE_ATTENDUE, (
        f"scenarios divergents du baseline {BASELINE} : {sorted(divergents)}, "
        f"declares : {sorted(DIVERGENCE_ATTENDUE)}")


def test_la_LIAISON_n_a_qu_AJOUTE_des_ISSUES_aux_refus(releve):
    """Ce que la tolerance (b) excuse, mesure ligne par ligne.

    `EPIC11-ARB-89` exige qu'un refus offre **au moins deux issues** : « un
    refus qui n'offre aucune issue est aussi fautif qu'une destruction
    silencieuse ». La liaison a donc reecrit une famille de messages, et
    `_refus_enrichi` les laisse passer. Ce banc mesure que ce qui passe est
    bien ca, et **seulement** ca :

    1. la tolerance attrape quelque chose (sinon elle est morte, et une
       exception morte finit par excuser autre chose que ce qu'elle nommait) ;
    2. chaque ligne excusee gagne au moins une issue neuve **sans en perdre**
       -- ce que la ligne d'avant nommait, celle d'apres le nomme encore ;
    3. et rien d'autre ne bouge dans les scenarios concernes : leur code de
       retour est celui du baseline. Une assertion positive -- « le message a
       change » -- laisserait passer un refus devenu succes.
    """
    reference, obtenu = _reference()["scenarios"], releve["scenarios"]
    excusees: list = []
    for nom in sorted(reference):
        avant_plat = _aplatir(reference[nom])
        apres_plat = _aplatir(obtenu[nom])
        for chemin in chemins_divergents(reference[nom], obtenu[nom]):
            avant = avant_plat.get(chemin, _ABSENT)
            apres = apres_plat.get(chemin, _ABSENT)
            if _refus_enrichi(avant, apres):
                excusees.append((nom, chemin, avant, apres))
                # 2 -- strictement additif : `--overwrite`, la seule issue que
                # ces refus nommaient, est toujours la.
                if "--overwrite" in avant:
                    assert "--overwrite" in apres, (nom, chemin)
        if any(ligne[0] == nom for ligne in excusees):
            # 3 -- le code de retour n'a pas bouge sur ces scenarios-la.
            assert obtenu[nom]["code"] == reference[nom]["code"], (
                f"{nom} : la liaison ne devait ajouter que des ISSUES a un "
                "refus, pas changer son code de retour")

    # 1 -- la tolerance n'est pas morte.
    assert excusees, (
        "aucune ligne de refus n'a gagne d'issue : soit `EPIC11-ARB-89` a ete "
        "defait, soit la reference a ete rejouee -- dans les deux cas "
        "`_refus_enrichi` doit etre RETIREE, pas gardee au cas ou")


#: Un condensat, ecrit ici comme un **mot de 64 chiffres hexadecimaux**, la ou
#: `PlanchesAuMemeSens` le retrouve par substitution des paires qu'elle a
#: excusees. Deux redactions du meme predicat, jamais une recopie.
_MASQUE_D_UN_CONDENSAT = re.compile(r"[0-9a-f]{64}")


#: Le dossier ou vivent les documents de profil, ecrit ici en clair : la seconde
#: lecture de la septieme famille le cherche comme un SEGMENT du chemin aplati,
#: la ou l'implementation l'a dans un motif ancre.
CALIBRATION_DIRNAME_DU_PROJET = "calibration"

#: Les trois documents de profil que le dossier d'identite ecrit et qui declarent
#: leur dossier de scan. Ils sont **nommes** plutot que comptes, pour le motif de
#: `PLANCHES_AU_MEME_SENS` : le predicat, lui, ne connait aucun nom de fichier, si
#: bien qu'un quatrieme profil qui se mettrait a declarer -- ou un `scan_dir`
#: apparu sous un profil qui n'en avait pas -- le passerait sans rougir.
#:
#: Le troisieme porte le nom d'aujourd'hui, celui que la traduction de vocabulaire
#: rend a la reference : le releve du jour ecrit bel et bien
#: `hp-envy-4520-...json`, le baseline ecrivait l'identite de chaine.
DOCUMENTS_QUI_DECLARENT_LEUR_DOSSIER_DE_SCAN = (
    "versions/calibration/chaine-du-banc-4c1254c7.json",
    "versions/calibration/chaine-du-banc.json",
    f"versions/calibration/{PROFIL_NOMME_PAR_LE_LIBELLE}.json",
)

#: Le dossier que les trois declarent -- le meme, les trois profils du dossier
#: d'identite etant calibres sur la meme mire.
DOSSIER_DE_SCAN_DECLARE = "scans/calibration"

CHEMINS_DU_DOSSIER_DE_SCAN = frozenset(
    f"projet.documents.{document}.{CHAMP_DU_DOSSIER_DE_SCAN}"
    for document in DOCUMENTS_QUI_DECLARENT_LEUR_DOSSIER_DE_SCAN)


def _est_un_dossier_relatif_POSIX(valeur) -> bool:
    """La SECONDE lecture de la forme qu'`EPIC11-ARB-262` promet, et elle seule.

    Elle repond a la meme question que la garde de `_dossier_de_scan_declare`,
    **ecrite autrement** : celle-ci decompose par `PurePosixPath` et interroge
    l'objet (`is_absolute`, ses `parts`), la ou l'implementation cherche une barre
    oblique en tete, un motif de lecteur Windows, un antislash et un segment `..`
    dans une chaine. Deux redactions qui coincident valent une mesure ; une seule,
    recopiee, ne mesurerait que la copie.

    L'antislash est refuse **avant** la decomposition, et c'est necessaire :
    `PurePosixPath` le tient pour un caractere de nom ordinaire, donc
    `"scans\\calibration"` lui parait un segment unique parfaitement relatif. Le
    champ etant declare POSIX, un separateur Windows ne s'apparierait a aucun
    chemin de l'inventaire -- et le faux orphelin reviendrait exactement sur les
    machines ou personne ne le mesure.
    """
    if not isinstance(valeur, str) or not valeur or "\\" in valeur:
        return False
    chemin = PurePosixPath(valeur)
    if chemin.is_absolute() or not chemin.parts:
        return False
    if ".." in chemin.parts:
        return False
    # Un lecteur Windows (`C:/scans`) n'est pas absolu pour `PurePosixPath` : il en
    # fait un premier segment nomme `C:`. On le refuse par sa FORME -- une lettre
    # ASCII puis un deux-points --, la ou l'autre redaction emploie un motif ancre.
    #
    # **Corrige le 2026-09-07, et c'est la famille construite qui l'a trouve.** La
    # redaction d'avant refusait TOUT deux-points dans le premier segment, si bien
    # qu'un dossier legalement nomme `scans:x` divergeait des deux redactions --
    # 15 formes de la famille, qu'aucune des trois couches de revue n'avait vues :
    # le tirage de dix valeurs qu'elles confrontaient n'en portait aucune. Sur un
    # systeme POSIX, le deux-points est un caractere de nom ordinaire ; seule la
    # forme « lettre + deux-points » designe un lecteur.
    tete = chemin.parts[0]
    return not (len(tete) >= 2 and tete[1] == ":"
                and tete[0].isascii() and tete[0].isalpha())


def test_la_TOLERANCE_du_DOSSIER_DE_SCAN_n_avale_QUE_le_dossier_declare():
    """La septieme famille, mesuree cas par cas et **hors du releve**.

    Meme geste que pour l'etiquette, et pour le meme motif : le temoin
    d'exactitude ne peut rien dire des ecarts que le dossier d'identite ne
    contient pas -- un `scan_dir` devenu absolu, un `scan_dir` qui changerait de
    valeur, un champ homonyme apparu dans un manifeste. Ce sont pourtant
    exactement ceux qu'une tolerance trop large avalerait, et ils n'existeront
    dans le releve que le jour ou ils seront un vrai defaut.

    **Chaque forme refusee ci-dessous rouvre le faux orphelin qu'`EPIC11-ARB-262`
    ferme**, et pas seulement « une valeur bizarre » : un chemin absolu ne
    designe rien apres copie du projet sur une autre machine, un antislash ne
    s'apparie a aucun chemin de l'inventaire, une remontee `..` designe un dossier
    que rien ne balaie, un champ vide ne declare rien du tout. Les avaler
    reviendrait a declarer vert un correctif a moitie fait.
    """
    chemin = (f"projet.documents.versions/calibration/"
              f"{PROFIL_NOMME_PAR_LE_LIBELLE}.json.{CHAMP_DU_DOSSIER_DE_SCAN}")

    # Ce que `-262` fait, et que la famille doit avaler -- trois formes de dossier
    # relatif POSIX : celui du dossier d'identite, un dossier a un seul segment, un
    # dossier profond.
    assert _dossier_de_scan_declare(chemin, _ABSENT, DOSSIER_DE_SCAN_DECLARE)
    assert _dossier_de_scan_declare(chemin, _ABSENT, "scans")
    assert _dossier_de_scan_declare(chemin, _ABSENT, "scans/2026/mire-a")

    # Et tout le reste, qu'elle ne doit PAS avaler. Chaque ligne est un ecart qu'un
    # motif un peu plus large laisserait passer.
    autre = "projet.documents.versions/calibration/autre.json"
    refuses = (
        # une valeur qui CHANGE : ce n'est pas une addition, c'est un changement
        # de provenance -- le depot a change d'avis sur d'ou vient ce profil
        (chemin, "scans/calibration", "scans/autre-mire"),
        # le champ RETIRE : une disparition n'est pas une addition
        (chemin, "scans/calibration", _ABSENT),
        # un champ vide : `-262` promet d'ecrire le dossier, pas de poser la cle
        (chemin, _ABSENT, ""),
        # les quatre formes que `_validate_scan_dir` refuse deja cote code, et que
        # ce banc refuse a nouveau plutot que d'heriter de sa garde
        (chemin, _ABSENT, "/var/scans/calibration"),
        (chemin, _ABSENT, "C:/scans/calibration"),
        (chemin, _ABSENT, "../dehors/calibration"),
        (chemin, _ABSENT, "scans\\calibration"),
        # une valeur non textuelle
        (chemin, _ABSENT, 3),
        (chemin, _ABSENT, ["scans/calibration"]),
        # le meme champ apparu AILLEURS que dans un document de profil : le motif
        # est ancre des deux bouts, et c'est ce qui l'empeche d'excuser un
        # `scan_dir` apparu dans un manifeste ou dans un document de detection
        ("projet.documents.project.json.color.calibration_profiles[0].scan_dir",
         _ABSENT, DOSSIER_DE_SCAN_DECLARE),
        ("projet.documents.scans/lot-b/detections/detect-<HORODATE>.json.scan_dir",
         _ABSENT, DOSSIER_DE_SCAN_DECLARE),
        (f"stdout[0].{CHAMP_DU_DOSSIER_DE_SCAN}", _ABSENT, DOSSIER_DE_SCAN_DECLARE),
        # un document de profil, mais un AUTRE champ neuf : la famille nomme
        # `scan_dir`, elle n'excuse pas le prochain champ optionnel venu
        (f"{autre}.commentaire_neuf", _ABSENT, DOSSIER_DE_SCAN_DECLARE),
        # le champ bien place mais en SOUS-CLE : ce serait une autre forme de
        # document, pas le champ que l'arbitrage decrit
        (f"{autre}.{CHAMP_DU_DOSSIER_DE_SCAN}.chemin", _ABSENT,
         DOSSIER_DE_SCAN_DECLARE),
    )
    avales = [(c, avant, apres) for c, avant, apres in refuses
              if _dossier_de_scan_declare(c, avant, apres)]
    assert avales == [], (
        "la tolerance du dossier de scan avale des ecarts qui ne sont pas une "
        f"declaration de dossier : {avales}")

    # **La confrontation des deux redactions, sur une famille CONSTRUITE et non
    # sur un tirage** (finding `B3` de la revue du 2026-09-07). Elle vit dans
    # `test_les_DEUX_REDACTIONS_de_la_forme_coincident_sur_la_famille_CONSTRUITE`,
    # a cote, parce qu'elle mesure autre chose que ce banc-ci : celui-la mesure ce
    # que la tolerance avale, celle-la mesure qu'on l'a bien lue deux fois.
    for valeur in (DOSSIER_DE_SCAN_DECLARE, "scans", "scans/2026/mire-a", "",
                   "/var/scans", "C:/scans", "../dehors", "scans\\calibration",
                   3, ["scans"]):
        assert _est_un_dossier_relatif_POSIX(valeur) == _dossier_de_scan_declare(
            chemin, _ABSENT, valeur), valeur


#: Les briques de la famille de formes que les deux redactions doivent trancher
#: pareil. Elles ne sont pas choisies pour etre difficiles : ce sont les prefixes,
#: les corps et les suffixes qu'un operateur produit en recopiant un chemin depuis
#: un terminal, un explorateur de fichiers ou un autre projet -- plus les quatre
#: formes que la garde d'ecriture oppose. Le produit cartesien fait le reste, et
#: c'est tout l'objet : **une famille se construit, elle ne se choisit pas**.
_PREFIXES_DE_LA_FAMILLE = ("", "./", ".//", "/", "//", "C:/", "c:", "../", "..//",
                           "x:", "./C:/", "e:/")
_CORPS_DE_LA_FAMILLE = ("scans", "scans/mire", "scans/2026/mire", "scans//mire",
                        "scans/./mire", ".", "..", "", "mire", "scans:x/mire",
                        "a b/c-d", "scans\\mire", "C:")
_SUFFIXES_DE_LA_FAMILLE = ("", "/", "//", "/.", "/./", "\\", "/..")

#: Ce qui n'est pas une chaine du tout. Une famille de chaines ne les produirait
#: jamais, et ce sont pourtant les valeurs qu'un document JSON edite a la main
#: porte le plus facilement.
_VALEURS_NON_TEXTUELLES = (3, 3.5, None, True, False, ["scans"], {"a": 1},
                           b"scans", (), object())


def famille_construite_des_formes() -> list:
    """Le produit cartesien des briques ci-dessus, dedoublonne, plus le non-textuel.

    Ecrite comme une fonction et non comme une constante pour une seule raison :
    le banc mesure son CARDINAL, et un cardinal qui se calcule ne peut pas mentir
    sur ce qu'il compte.
    """
    formes = [prefixe + corps + suffixe
              for prefixe in _PREFIXES_DE_LA_FAMILLE
              for corps in _CORPS_DE_LA_FAMILLE
              for suffixe in _SUFFIXES_DE_LA_FAMILLE]
    return list(dict.fromkeys(formes)) + list(_VALEURS_NON_TEXTUELLES)


def test_les_DEUX_REDACTIONS_de_la_forme_coincident_sur_la_famille_CONSTRUITE():
    """`B3`, ferme : **la confrontation etait un TIRAGE, elle est une frontiere**.

    Le docstring de `_est_un_dossier_relatif_POSIX` pose la mesure depuis le
    2026-09-07 : « Deux redactions qui coincident valent une mesure ; une seule,
    recopiee, ne mesurerait que la copie. » Elle ne la tenait pas. La boucle qui
    les confrontait **echantillonnait dix valeurs choisies a la main**, et les deux
    redactions divergeaient sur des formes qui n'en faisaient pas partie.

    **Mesure du 2026-09-07, sur la famille construite ci-dessous** : 32 formes
    divergentes sur 704, en deux familles dont une seule avait ete trouvee a la
    main :

    * 17 formes qui ne NOMMENT rien -- `'.'`, `'./'`, `'.//.'`, `'././'`... La
      revue en avait trouve UNE, `'.'`, et c'est ce qui a ouvert le finding ;
    * 15 formes portant un deux-points hors position de lecteur --
      `'scans:x/mire'` et ses decorations. **Aucune des trois couches ne l'avait
      vue**, et pour la raison exacte que le finding nomme : un tirage ne peut pas
      attraper ce qu'il ne tire pas. C'est la famille construite qui l'a rendue.

    Les deux ont ete fermees dans les deux redactions -- l'une exige desormais un
    segment nommant, l'autre juge le lecteur Windows sur sa FORME plutot que sur la
    presence d'un deux-points.

    **Ce que ce banc ne mesure pas, dit plutot que tu** : il ne mesure pas que les
    deux redactions sont JUSTES, seulement qu'elles coincident. C'est
    `test_la_TOLERANCE_du_DOSSIER_DE_SCAN_n_avale_QUE_le_dossier_declare` qui
    tranche cas par cas ce que la famille doit avaler, et lui seul. Deux redactions
    fausses de la meme facon passeraient ici -- c'est pourquoi il y a deux bancs et
    non un.

    **Et il ne se confronte PAS a la garde du produit**
    (`calibration_profile.normaliser_le_dossier_de_scan`), volontairement : les
    deux redactions sont reecrites ici plutot qu'importees, « le jour ou la garde
    du module se relacherait, ce banc doit rougir au lieu d'heriter du
    relachement ». Elles sont d'ailleurs plus STRICTES que la normalisation du
    produit sur un point nomme -- le lecteur Windows, que la normalisation laisse
    passer parce que `C:` est un nom de dossier legal sur un systeme POSIX, et que
    la garde d'ECRITURE oppose pour la portabilite du manifeste v2. Un `scan_dir`
    en `C:/...` dans le releve serait donc un ecart a VOIR, jamais a excuser.
    """
    chemin = (f"projet.documents.versions/calibration/"
              f"{PROFIL_NOMME_PAR_LE_LIBELLE}.json.{CHAMP_DU_DOSSIER_DE_SCAN}")
    famille = famille_construite_des_formes()

    # Le cardinal, mesure : une famille qui se serait effondree a trois elements
    # rendrait ce banc vert pour rien -- c'est la regle des fabriques appliquee a
    # une famille de valeurs.
    assert len(famille) > 600, len(famille)

    divergentes = [valeur for valeur in famille
                   if _forme_par_DECOUPAGE(valeur)
                   != _est_un_dossier_relatif_POSIX(valeur)]
    assert divergentes == [], (
        "les deux redactions du predicat de forme ne coincident pas : "
        f"{divergentes[:10]}{' ...' if len(divergentes) > 10 else ''}")

    # **La famille n'est pas DEGENEREE**, et sans ce controle « les deux rendent
    # toujours False » serait un vert. Les deux verdicts doivent y etre nombreux.
    avales = [valeur for valeur in famille if _forme_par_DECOUPAGE(valeur)]
    refuses = [valeur for valeur in famille if not _forme_par_DECOUPAGE(valeur)]
    assert len(avales) > 100, len(avales)
    assert len(refuses) > 100, len(refuses)

    # Les deux familles qui divergeaient sont dans la famille construite, et elles
    # tranchent maintenant du bon cote. Sans ces lignes, une famille qui aurait
    # cesse de les produire rendrait le banc vert sans rien mesurer.
    for ne_nomme_rien in (".", "./", ".//.", "././"):
        assert ne_nomme_rien in famille, ne_nomme_rien
        assert not _forme_par_DECOUPAGE(ne_nomme_rien), ne_nomme_rien
    for deux_points_ordinaire in ("scans:x/mire", "./scans:x/mire"):
        assert deux_points_ordinaire in famille, deux_points_ordinaire
        assert _forme_par_DECOUPAGE(deux_points_ordinaire), deux_points_ordinaire
    for lecteur in ("C:/scans", "./C:/scans", "x:scans", "e:/scans"):
        assert lecteur in famille, lecteur
        assert not _forme_par_DECOUPAGE(lecteur), lecteur


def test_la_TOLERANCE_de_l_ETIQUETTE_n_avale_QUE_l_etiquette():
    """La sixieme famille, mesuree cas par cas et **hors du releve**.

    Le temoin d'exactitude ci-dessous mesure ce que les familles avalent sur le
    dossier reel ; il ne peut donc rien dire des ecarts que le dossier ne
    contient pas -- un cardinal de pastilles qui bougerait dans la meme ligne,
    une etiquette qui prendrait une AUTRE valeur que celle du QR. Ce sont
    pourtant ces ecarts-la qu'une tolerance trop large avalerait, et ils
    n'existeront dans le releve que le jour ou ils seront un vrai defaut.

    C'est le meme geste que `test_un_contenu_de_planche_change_HORS_du_QR_fait_ROUGIR`
    tient pour la cinquieme famille : on fabrique l'ecart que la tolerance ne
    doit PAS avaler, plutot que d'attendre qu'il arrive.
    """
    libelle = LIBELLE_DE_CHAINE_DU_DOSSIER
    absente = ETIQUETTE_ABSENTE_AU_BASELINE

    # Ce que `D2` fait, et que la famille doit avaler -- les trois formes.
    assert _etiquette_lue_sur_le_QR("profil.json.label", "", libelle)
    assert _etiquette_lue_sur_le_QR(
        "stderr[1]", f"sous l'etiquette '{absente}': 130 pastille(s)",
        f"sous l'etiquette '{libelle}': 130 pastille(s)")
    assert _etiquette_lue_sur_le_QR(
        "stdout[0]", "calibration ecrite: correction consignee",
        f"calibration ecrite: Etiquette: '{libelle}'. correction consignee")

    # Et tout le reste, qu'elle ne doit PAS avaler. Chaque ligne est un ecart
    # qu'un motif un peu plus large laisserait passer.
    refuses = (
        # une etiquette qui n'est pas celle du QR : ce serait un autre defaut
        ("profil.json.label", "", "autre chose"),
        # une etiquette qui en REMPLACE une : `D2` en ajoute une la ou il n'y
        # en avait pas, il n'en ecrase aucune
        ("profil.json.label", "deja nommee", libelle),
        # l'etiquette bien posee, mais un cardinal change dans la meme ligne
        ("stderr[1]", f"sous l'etiquette '{absente}': 130 pastille(s)",
         f"sous l'etiquette '{libelle}': 129 pastille(s)"),
        # la phrase bien inseree, mais un mot change ailleurs
        ("stdout[0]", "calibration ecrite: correction consignee",
         f"calibration ecrite: Etiquette: '{libelle}'. correction ANNULEE"),
        # un ecart qui n'a rien a voir avec l'etiquette
        ("stdout[0]", "planches/a.pdf", "planches/b.pdf"),
        # une apparition ou une disparition : deux chaines vides ne sont pas
        # une etiquette posee
        ("profil.json.comment", _ABSENT, ""),
        ("profil.json.comment", "", _ABSENT),
    )
    avales = [(chemin, avant, apres) for chemin, avant, apres in refuses
              if _etiquette_lue_sur_le_QR(chemin, avant, apres)]
    assert avales == [], (
        "la tolerance de l'etiquette avale des ecarts qui ne sont pas "
        f"l'etiquette : {avales}")


_CONDENSAT_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_CONDENSAT_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
_CHEMIN_D_UNE_FRAME = "projet.arbre.extract-frames/rush_ident_5/f_00-00-00-18.tiff"


def test_la_famille_des_frames_extraites_AVALE_deux_condensats_differents():
    """Le sens qui ferme la panne : deux decodages, deux condensats, un seul
    scenario -- et le banc ne doit plus rougir pour ca."""
    gauche = {"projet": {"arbre": {
        "extract-frames/rush_ident_5/f_00-00-00-18.tiff": _CONDENSAT_A}}}
    droite = {"projet": {"arbre": {
        "extract-frames/rush_ident_5/f_00-00-00-18.tiff": _CONDENSAT_B}}}
    assert divergents_hors_liaison(gauche, droite) == set()

    # Anti-vacuite : sans la famille, ce chemin divergeait bel et bien.
    assert chemins_divergents(gauche, droite) != set()


def test_une_frame_qui_DISPARAIT_fait_toujours_rougir():
    """Le premier volet symetrique, et le plus important.

    La famille excuse deux OCTETS differents, jamais une frame en moins. Sans
    ce volet, une extraction qui cesserait de produire ses frames passerait
    pour une divergence de decodage.
    """
    avec = {"projet": {"arbre": {"extract-frames/r/f.tiff": _CONDENSAT_A,
                                 "t": 1}}}
    sans = {"projet": {"arbre": {"t": 1}}}
    attendu = {"projet.arbre.extract-frames/r/f.tiff"}
    assert divergents_hors_liaison(avec, sans) == attendu
    assert divergents_hors_liaison(sans, avec) == attendu


def test_la_famille_ne_couvre_NI_un_autre_dossier_NI_un_autre_suffixe():
    """Les deux autres volets symetriques : le motif est etroit des deux cotes.

    Un raster de scan, et un manifeste JSON depose dans `extract-frames/`,
    restent compares au bit pres. Un motif ecrit un cran trop large les
    avalerait tous les deux.
    """
    ailleurs = ("scans/lot-a/page_01.tiff",
                "extract-frames/r/manifeste.json",
                "frames-scannees/r/f.tiff")
    for queue in ailleurs:
        gauche = {"projet": {"arbre": {queue: _CONDENSAT_A}}}
        droite = {"projet": {"arbre": {queue: _CONDENSAT_B}}}
        assert divergents_hors_liaison(gauche, droite) == {
            f"projet.arbre.{queue}"}, queue


def test_la_famille_n_avale_QUE_des_CONDENSATS():
    """Une valeur qui n'est pas un condensat retombe sur l'egalite stricte.

    Sans ce volet, la famille excuserait n'importe quelle feuille portee par
    un chemin de frame -- une taille, un horodatage, un chemin.
    """
    gauche = {"projet": {"arbre": {"extract-frames/r/f.tiff": "12 octets"}}}
    droite = {"projet": {"arbre": {"extract-frames/r/f.tiff": "13 octets"}}}
    assert divergents_hors_liaison(gauche, droite) == {
        "projet.arbre.extract-frames/r/f.tiff"}


def test_les_DEUX_redactions_du_predicat_de_frame_COINCIDENT():
    """Le predicat de l'implementation et celui de la contre-lecture disent la
    meme chose -- sinon la mesure d'union ne mesure que sa propre copie."""
    cas = ((_CHEMIN_D_UNE_FRAME, _CONDENSAT_A, _CONDENSAT_B, True),
           (_CHEMIN_D_UNE_FRAME, _CONDENSAT_A, _ABSENT, False),
           ("projet.arbre.extract-frames/r/m.json", _CONDENSAT_A,
            _CONDENSAT_B, False),
           ("projet.arbre.scans/r/f.tiff", _CONDENSAT_A, _CONDENSAT_B, False),
           (_CHEMIN_D_UNE_FRAME, "12 octets", "13 octets", False))
    for chemin, gauche, droite, attendu in cas:
        officiel = _frame_extraite_dont_le_DECODAGE_depend_du_CPU(
            chemin, gauche, droite)
        autrement = _est_une_frame_extraite_AUTREMENT(chemin, gauche, droite)
        assert officiel is attendu, (chemin, gauche, droite)
        assert autrement is attendu, (chemin, gauche, droite)


def _est_une_frame_extraite_AUTREMENT(chemin, gauche, droite) -> bool:
    """La huitieme famille relue par des segments, jamais par le motif."""
    if gauche is _ABSENT or droite is _ABSENT:
        return False
    segments_du_chemin = chemin.split(".arbre.", 1)
    if len(segments_du_chemin) != 2:
        return False
    queue = segments_du_chemin[1]
    if "extract-frames" not in queue:
        return False
    segments = PurePosixPath(queue).parts
    if not segments or segments[0] != "extract-frames":
        return False
    if PurePosixPath(queue).suffix.lower() not in SUFFIXES_DE_RASTER_EXTRAIT:
        return False
    return all(len(str(v)) == 64 and set(str(v)) <= set("0123456789abcdef")
               for v in (gauche, droite))


def test_la_TOLERANCE_de_la_liaison_n_est_ni_MORTE_ni_TROP_LARGE(releve, planches):
    """Le volet symetrique de la tolerance (a), sans lequel elle ne vaut rien.

    Une tolerance se mesure des DEUX cotes, exactement comme une ligne de
    divergence declaree : qu'elle attrape bel et bien quelque chose (sinon
    c'est une exception morte, qui survit a l'echeance qui l'a fait naitre et
    finira par excuser autre chose), et qu'elle n'attrape QUE ce qu'elle
    nomme.

    Le second volet est le plus important, et il est pose sous la seule forme
    qui vaille : l'ensemble de ce que la tolerance avale, sur TOUS les
    scenarios, est **exactement** la reunion de ses sept familles : les
    champs d'`EPIC11-ARB-109` sous `reconstructions`, les refus enrichis
    d'`EPIC11-ARB-89`, les deux criteres d'identite du rush, les rangs de
    tirage scannes d'`EPIC11-ARB-176`, les condensats de planche au meme
    SENS d'`EPIC11-ARB-250`, l'etiquette lue sur le QR du constat `D2` et le
    dossier de scan que le profil declare depuis `EPIC11-ARB-262`. Une
    assertion positive -- « elle avale bien ces chemins-la » -- laisserait
    passer un motif trop large qui en avalerait d'autres, c'est-a-dire
    precisement la panne qu'une tolerance peut causer.
    """
    attendu = _reference()["scenarios"]
    obtenu = releve["scenarios"]
    avales: set = set()
    for nom in attendu:
        bruts = chemins_divergents(attendu[nom], obtenu[nom])
        avales |= bruts - divergents_hors_liaison(attendu[nom], obtenu[nom],
                                                  planches)

    assert avales, (
        "la tolerance de la liaison n'attrape plus rien : soit "
        "`EPIC11-ARB-109` a ete defait, soit la reference a ete rejouee -- "
        "dans les deux cas elle doit etre RETIREE, pas gardee au cas ou")

    # Les deux familles, recalculees ICI par des predicats ecrits AUTREMENT
    # que ceux de l'implementation -- un suffixe de champ et une recherche de
    # mot, la ou `divergents_hors_liaison` emploie une expression reguliere.
    # Deux redactions du meme predicat qui coincident valent une mesure ; une
    # seule, recopiee, ne mesurerait que la copie.
    famille_des_champs, famille_des_refus = set(), set()
    famille_des_criteres, famille_des_rangs = set(), set()
    famille_du_sens, famille_de_l_etiquette = set(), set()
    famille_du_dossier_de_scan = set()
    famille_des_frames_extraites = set()
    for nom in attendu:
        avant_plat, apres_plat = _aplatir(attendu[nom]), _aplatir(obtenu[nom])
        for chemin in chemins_divergents(attendu[nom], obtenu[nom]):
            dernier = chemin.rsplit(".", 1)[-1]
            if ("reconstructions[" in chemin
                    and dernier in CHAMPS_DE_LA_LIAISON):
                famille_des_champs.add(chemin)
            elif dernier in ("sheets_version_watermark",) or (
                    "sheets_pdfs[" in chemin and dernier == "path"):
                famille_des_champs.add(chemin)
            elif ("rushes[" in chemin
                    and dernier in CRITERES_D_IDENTITE_NEUFS
                    and avant_plat.get(chemin, _ABSENT) is _ABSENT):
                famille_des_criteres.add(chemin)
            # Le rang de tirage scanne (`EPIC11-ARB-176`), reconnu ici par un
            # PREFIXE d'element de liste la ou l'implementation emploie une
            # expression reguliere ancree : deux redactions du meme predicat,
            # jamais une recopie.
            elif ("lots[" in chemin
                    and dernier.startswith(f"{CHAMP_DES_RANGS_SCANNES}[")
                    and avant_plat.get(chemin, _ABSENT) is _ABSENT):
                famille_des_rangs.add(chemin)
            # La cinquieme famille (`EPIC11-ARB-250`), reconnue ici par un
            # MASQUAGE : on remplace tout mot de 64 chiffres hexadecimaux par
            # un jeton et on compare ce qui reste. L'implementation, elle,
            # SUBSTITUE les condensats qu'elle a excuses un a un. Les deux
            # redactions ne coincident que si chaque condensat divergent a bel
            # et bien ete excuse -- un artefact refuse les separe aussitot, et
            # c'est ce qu'on veut voir.
            elif _MASQUE_D_UN_CONDENSAT.search(
                    str(avant_plat.get(chemin, ""))) and (
                    _MASQUE_D_UN_CONDENSAT.sub(
                        "<CONDENSAT>", str(avant_plat.get(chemin, "")))
                    == _MASQUE_D_UN_CONDENSAT.sub(
                        "<CONDENSAT>", str(apres_plat.get(chemin, "")))):
                famille_du_sens.add(chemin)
            # La septieme famille (`EPIC11-ARB-262`), reconnue ici en DECOUPANT le
            # chemin en segments et en passant la valeur a `PurePosixPath`, la ou
            # l'implementation emploie une expression reguliere ancree et des tests
            # de sous-chaine. Deux redactions du meme predicat, jamais une recopie :
            # celle-ci ne sait rien du motif de l'autre, et refuse un chemin absolu
            # parce que `PurePosixPath.is_absolute()` le dit, pas parce qu'elle
            # cherche une barre oblique en tete.
            elif (dernier == CHAMP_DU_DOSSIER_DE_SCAN
                    and avant_plat.get(chemin, _ABSENT) is _ABSENT
                    and chemin.split(".")[:2] == ["projet", "documents"]
                    and f"/{CALIBRATION_DIRNAME_DU_PROJET}/" in chemin
                    and _est_un_dossier_relatif_POSIX(
                        apres_plat.get(chemin, _ABSENT))):
                famille_du_dossier_de_scan.add(chemin)
            # La huitieme famille, reconnue ici en DECOUPANT le chemin d'arbre
            # en segments PurePosixPath et en verifiant que les deux valeurs
            # font 64 caracteres hexadecimaux -- la ou l'implementation emploie
            # une expression reguliere et un `fullmatch`. Deux redactions qui
            # coincident valent une mesure.
            elif _est_une_frame_extraite_AUTREMENT(
                    chemin, avant_plat.get(chemin, _ABSENT),
                    apres_plat.get(chemin, _ABSENT)):
                famille_des_frames_extraites.add(chemin)
            # La sixieme famille (`D2`), reconnue ici par un MASQUE d'expression
            # reguliere -- la phrase d'etiquette et les deux formes du libelle
            # remplacees par un jeton des deux cotes --, la ou l'implementation
            # fait un RETOUR EN ARRIERE par substitutions litterales. Deux
            # redactions du meme predicat, jamais une recopie : celle-ci ne sait
            # rien de laquelle des deux formes est l'ancienne.
            elif (dernier == "label"
                    and avant_plat.get(chemin, _ABSENT) == ""
                    and apres_plat.get(chemin, _ABSENT)
                    == LIBELLE_DE_CHAINE_DU_DOSSIER):
                famille_de_l_etiquette.add(chemin)
            # Les deux cotes doivent EXISTER : sans cette condition, un
            # chemin present d'un seul cote rendait deux chaines vides egales
            # et la famille avalait une apparition ou une disparition, ce qui
            # n'est pas ce que `D2` fait. Mesure : le `comment` de
            # `53_couche_manual_corrections_v1` y passait.
            elif (chemin in avant_plat and chemin in apres_plat
                    and _sans_l_etiquette(str(avant_plat[chemin]))
                    == _sans_l_etiquette(str(apres_plat[chemin]))):
                famille_de_l_etiquette.add(chemin)
            elif _refus_enrichi(avant_plat.get(chemin, _ABSENT),
                                apres_plat.get(chemin, _ABSENT)):
                famille_des_refus.add(chemin)

    # Chaque famille est vivante : une tolerance a deux volets dont un seul
    # sert est une tolerance dont l'autre moitie excuse dans le vide.
    assert famille_des_champs, "la tolerance des CHAMPS n'attrape plus rien"
    assert famille_des_refus, "la tolerance des REFUS n'attrape plus rien"
    assert famille_des_criteres, (
        "la tolerance des CRITERES D'IDENTITE n'attrape plus rien : soit la "
        "note 5 a ete defaite, soit la reference a ete rejouee -- dans les "
        "deux cas elle doit etre RETIREE, pas gardee au cas ou")
    assert famille_des_rangs, (
        "la tolerance des RANGS DE TIRAGE SCANNES n'attrape plus rien : soit "
        "`EPIC11-ARB-176` a ete defait et le scan ne persiste plus le rang lu "
        "au QR, soit la reference a ete rejouee -- dans les deux cas elle doit "
        "etre RETIREE, pas gardee au cas ou")

    assert famille_du_sens, (
        "la tolerance du SENS DES PLANCHES n'attrape plus rien : soit "
        "`EPIC11-ARB-250` a ete defait et l'encodage QR est revenu a OpenCV, "
        "soit la reference a ete rejouee -- dans les deux cas elle doit etre "
        "RETIREE, pas gardee au cas ou")

    assert famille_de_l_etiquette, (
        "la tolerance de l'ETIQUETTE n'attrape plus rien : soit le constat "
        "`D2` a ete defait et le profil ne prend plus le libelle lu sur le QR, "
        "soit la reference a ete rejouee -- dans les deux cas elle doit etre "
        "RETIREE, pas gardee au cas ou")

    assert famille_du_dossier_de_scan, (
        "la tolerance du DOSSIER DE SCAN DECLARE n'attrape plus rien : soit "
        "`EPIC11-ARB-262` a ete defait et le profil ne nomme plus le dossier "
        "dont il est issu -- donc le faux orphelin de la mire est revenu --, "
        "soit la reference a ete rejouee -- dans les deux cas elle doit etre "
        "RETIREE, pas gardee au cas ou")

    # Et l'ensemble EXACT, qui est la mesure la plus forte de cette famille : la
    # reunion des scenarios ne porte que TROIS chemins, un par document de profil
    # que le dossier d'identite ecrit. Un quatrieme document qui se mettrait a
    # declarer, ou un `scan_dir` apparu sous un autre profil, ferait rougir ici --
    # la ou le predicat seul, qui ne connait aucun nom de fichier, resterait vert.
    assert famille_du_dossier_de_scan == CHEMINS_DU_DOSSIER_DE_SCAN, (
        "les profils qui declarent leur dossier de scan ne sont plus les trois "
        f"nommes : {sorted(famille_du_dossier_de_scan ^ CHEMINS_DU_DOSSIER_DE_SCAN)}")

    # La VALEUR declaree, nommee elle aussi : les trois profils du dossier
    # d'identite sont calibres sur la meme mire, donc ils declarent le meme
    # dossier. Sans cette ligne, la famille avalerait n'importe quel chemin
    # relatif bien forme.
    declares = {apres_plat[chemin]
                for nom in attendu
                for apres_plat in (_aplatir(obtenu[nom]),)
                for chemin in famille_du_dossier_de_scan & set(apres_plat)}
    assert declares == {DOSSIER_DE_SCAN_DECLARE}, (
        f"les dossiers de scan declares ne sont plus le seul attendu : {sorted(declares)}")

    familles = (famille_des_champs | famille_des_refus
                | famille_des_criteres | famille_des_rangs | famille_du_sens
                | famille_de_l_etiquette | famille_du_dossier_de_scan
                | famille_des_frames_extraites)
    assert avales == familles, (
        "la tolerance de la liaison avale autre chose que ses huit familles "
        f"declarees : {sorted(avales ^ familles)}")


#: Deux condensats distincts, ecrits ici plutot que calcules : la frontiere
#: ci-dessous mesure un AIGUILLAGE, pas un hachage.
_CONDENSAT_A = "a" * 64
_CONDENSAT_B = "b" * 64


def test_l_ECARTEUR_de_la_cinquieme_famille_FAIT_VARIER_ce_qu_elle_recense(
        tmp_path):
    """`ecarter` retire de la cinquieme famille ce que la huitieme tient deja.

    **La frontiere fait varier son drapeau**, dans les deux sens, sur un cas ou
    il change quelque chose -- c'est la regle du depot, et c'est precisement son
    absence qui a coute le run 34222962404 : le job 3.12 y a rougi seul, sur un
    arbre que 3.11 et 3.13 ont rendu vert.

    Le montage est SYNTHETIQUE et n'ouvre aucun fichier : l'arbre de travail est
    vide, donc aucun condensat ne s'y retrouve et `porte_le_meme_SENS` refuse
    sans decoder. C'est le recensement qu'on mesure, pas la lecture.

    Ce qui est pose par EGALITE des deux cotes : sans ecarteur, la frame
    extraite ET la planche sont recensees ; avec, la planche SEULE l'est. Une
    frontiere qui ne jouerait que le second cas serait verte meme si l'ecarteur
    avalait tout.
    """
    reference = {"s": {"projet": {"arbre": {
        "extract-frames/rush_x/rush_x_00-00-00-01.tiff": _CONDENSAT_A,
        "scans/lot-a/page_01.tiff": _CONDENSAT_A}}}}
    releve = {"s": {"projet": {"arbre": {
        "extract-frames/rush_x/rush_x_00-00-00-01.tiff": _CONDENSAT_B,
        "scans/lot-a/page_01.tiff": _CONDENSAT_B}}}}

    sans = PlanchesAuMemeSens(reference, releve, tmp_path, aplatir=_aplatir)
    assert {artefact for artefact, _, _ in sans.verdicts} == {
        "extract-frames/rush_x/rush_x_00-00-00-01.tiff",
        "scans/lot-a/page_01.tiff"}, (
        "sans ecarteur, la cinquieme famille se prononce sur TOUT condensat "
        f"d'arbre qui diverge : {sorted(a for a, _, _ in sans.verdicts)}")

    avec = PlanchesAuMemeSens(
        reference, releve, tmp_path, aplatir=_aplatir,
        ecarter=_frame_extraite_dont_le_DECODAGE_depend_du_CPU)
    assert {artefact for artefact, _, _ in avec.verdicts} == {
        "scans/lot-a/page_01.tiff"}, (
        "l'ecarteur ne retire pas la frame extraite, ou il retire aussi la "
        f"planche : {sorted(a for a, _, _ in avec.verdicts)}")


def test_l_ECARTEUR_n_est_pas_un_INTERRUPTEUR_GENERAL(tmp_path):
    """Un ecarteur qui rendrait `True` partout viderait la cinquieme famille.

    Le volet symetrique du precedent : il mesure que le recensement obeit
    reellement au predicat qu'on lui passe, plutot que de traiter `ecarter` en
    drapeau booleen. Sans lui, un `ecarter` cable a l'envers -- qui ecarterait
    les planches et garderait les frames -- resterait invisible.
    """
    reference = {"s": {"projet": {"arbre": {"scans/lot-a/page_01.tiff":
                                            _CONDENSAT_A}}}}
    releve = {"s": {"projet": {"arbre": {"scans/lot-a/page_01.tiff":
                                         _CONDENSAT_B}}}}
    tout = PlanchesAuMemeSens(reference, releve, tmp_path, aplatir=_aplatir,
                              ecarter=lambda chemin, avant, apres: True)
    assert tout.verdicts == {} and tout.paires == {}, (
        "un ecarteur qui rend True partout laisse pourtant passer quelque "
        f"chose : {sorted(tout.verdicts)}")

    rien = PlanchesAuMemeSens(reference, releve, tmp_path, aplatir=_aplatir,
                              ecarter=lambda chemin, avant, apres: False)
    assert {artefact for artefact, _, _ in rien.verdicts} == {
        "scans/lot-a/page_01.tiff"}, (
        "un ecarteur qui rend False partout devrait laisser le recensement "
        f"intact : {sorted(a for a, _, _ in rien.verdicts)}")


#: Les planches que la cinquieme famille excuse, **nommees**. Elles ne servent
#: pas a la reconnaissance -- `PlanchesAuMemeSens` ne les lit jamais -- mais a
#: la MESURE de ce qu'elle avale : c'est la meme discipline que
#: `test_la_TOLERANCE_..._ni_MORTE_ni_TROP_LARGE`, et sans elle une tolerance
#: qui s'elargirait d'une planche resterait verte.
PLANCHES_AU_MEME_SENS = (
    "scans/calibration/page_01.tiff",
    "scans/lot-a/page_01.tiff",
    "scans/lot-a/page_02.tiff",
    "scans/lot-b/page_01.tiff",
    "scans/lot-b/page_02.tiff",
    "scans/lot-etranger/page_01.tiff",
    "scans/lot-etranger/page_02.tiff",
)

#: Les chemins que la cinquieme famille avale, sur les 42 scenarios reunis.
#: Sept condensats d'arbre, quatre `source_digest` que les documents de
#: detection en recopient, et trois messages qui les CITENT -- deux `stderr` et
#: une ligne de journal, tous trois du scenario `36`, ou le refus imprime le
#: condensat trouve et celui attendu.
CHEMINS_AU_MEME_SENS = frozenset(
    [f"projet.arbre.{planche}" for planche in PLANCHES_AU_MEME_SENS]
    + ["projet.documents.scans/lot-b/detections/"
       "detect-<HORODATE>.json.pages[0].source_digest",
       "projet.documents.scans/lot-b/detections/"
       "detect-<HORODATE>.json.pages[1].source_digest",
       "projet.documents.scans/lot-etranger/detections/"
       "detect-<HORODATE>.json.pages[0].source_digest",
       "projet.documents.scans/lot-etranger/detections/"
       "detect-<HORODATE>.json.pages[1].source_digest",
       "projet.journaux.logs/scan.log[14]",
       "stderr[1]",
       "stderr[2]"])


def test_la_CINQUIEME_famille_avale_EXACTEMENT_ce_qu_elle_NOMME(releve,
                                                                planches):
    """L'ensemble exact de la tolerance (g), a ses deux etages.

    Une tolerance de condensat est la plus large du banc : elle doit donc etre
    la plus etroitement mesuree. Deux ensembles, tous deux poses par egalite :

    * les **planches** qu'elle excuse -- sept fichiers, chacun avec un verdict
      VRAI. Une huitieme planche excusee, ou une septieme refusee, se voit ;
    * les **chemins** qu'elle avale -- quatorze, et pas un de plus. Les sept
      condensats d'arbre, plus les sept endroits ou ces memes condensats sont
      RECOPIES ou CITES ailleurs dans le releve.

    Le cardinal des couples est **huit** et non sept, et c'est une propriete du
    banc plutot qu'un detail : le scenario `36_source_REMPLACEE` ajoute un
    octet a `scans/lot-b/page_01.tiff` pour la rendre perimee, donc cette
    planche-la diverge sous **deux** couples de condensats distincts. Une
    tolerance qui n'aurait excuse que le couple nominal aurait laisse le
    scenario `36` rouge.
    """
    assert {artefact for artefact, _, _ in planches.verdicts} \
        == set(PLANCHES_AU_MEME_SENS), (
        "la cinquieme famille ne se prononce pas sur les planches declarees : "
        f"{sorted({a for a, _, _ in planches.verdicts} ^ set(PLANCHES_AU_MEME_SENS))}")
    refusees = sorted(cle for cle, verdict in planches.verdicts.items()
                      if not verdict)
    assert not refusees, (
        "une planche de la fixture ne porte plus le SENS que le baseline y a "
        f"lu : {refusees}")
    assert len(planches.verdicts) == 8, (
        "huit couples de condensats sont attendus pour sept planches -- le "
        "scenario 36 en mute une : " + str(sorted(planches.verdicts)))
    assert len(planches.paires) == 8

    attendu, obtenu = _reference()["scenarios"], releve["scenarios"]
    avales: set = set()
    for nom in attendu:
        a, b = _aplatir(attendu[nom]), _aplatir(obtenu[nom])
        for chemin in chemins_divergents(attendu[nom], obtenu[nom]):
            if planches.au_meme_SENS(a.get(chemin, _ABSENT),
                                     b.get(chemin, _ABSENT)):
                avales.add(chemin)
    assert avales == set(CHEMINS_AU_MEME_SENS), (
        "la cinquieme famille n'avale pas exactement ce qu'elle nomme : "
        f"{sorted(avales ^ set(CHEMINS_AU_MEME_SENS))}")


def test_un_contenu_de_planche_change_HORS_du_QR_fait_ROUGIR(releve, planches):
    """Le controle qui FERME la cinquieme famille : elle n'est pas un blanc-seing.

    Une tolerance de condensat pourrait, mal ecrite, excuser n'importe quel
    changement d'octets d'un artefact. Quatre greffes le mesurent, toutes sur
    des fichiers **reels** de l'arbre de travail plutot que sur des fabriques :

    1. **un artefact qui ne porte AUCUN symbole** -- une frame de sortie. Le
       baseline n'en dit rien et rien ne s'y decode : refus ;
    2. **une AUTRE planche sous le meme condensat** -- le fichier trouve porte
       un symbole parfaitement lisible, mais qui ne dit pas ce que le baseline
       a lu sur cette planche-la : refus. C'est le cas « le payload a change » ;
    3. **un artefact introuvable** -- un condensat qui ne designe aucun fichier
       de l'arbre : refus, plutot qu'une excuse par defaut ;
    4. **un suffixe qui n'est pas celui d'une planche** : refus.

    Et le cinquieme volet, qui est celui que l'arbitrage nomme -- « une page en
    moins, une frame deplacee, un libelle different » -- se mesure autrement,
    parce qu'il ne passe PAS par la tolerance : **la tolerance ne s'applique
    qu'a la valeur d'un condensat et aux chaines qui le citent**. Une paire de
    releves ou la planche a change d'octets ET ou une autre observable a bouge
    fait toujours nommer l'autre observable. C'est le dernier bloc du test.
    """
    planche = "scans/lot-b/page_01.tiff"
    (avant, apres), = [(a, b) for (art, a, b) in planches.verdicts
                       if art == planche and b in planches.paires.values()][:1]
    assert planches.porte_le_meme_SENS(planche, avant, apres), (
        "le temoin du test doit d'abord etre EXCUSE, sinon les quatre refus "
        "ci-dessous ne mesurent rien")

    # (1) une frame de sortie : elle est bien un `.tiff`, elle est bien dans
    # l'arbre, et elle ne porte aucun symbole.
    frames = sorted(chemin for chemin in planches.par_condensat.values()
                    if f"/{DOSSIER_DES_FRAMES_SCANNEES}/" in chemin.as_posix())
    assert frames, "l'arbre de travail doit porter des frames de sortie"
    condensat_de_frame, = [cle for cle, valeur in planches.par_condensat.items()
                           if valeur == frames[0]]
    assert not planches.porte_le_meme_SENS(
        f"{DOSSIER_DES_FRAMES_SCANNEES}/greffe.tiff", avant,
        condensat_de_frame), (
        "un artefact sans symbole a ete excuse : la tolerance ne verifie plus "
        "que la planche PARLE")

    # (2) une autre planche, parfaitement lisible, sous le meme condensat.
    autre = "scans/lot-b/page_02.tiff"
    (_, _, condensat_de_l_autre), = [cle for cle in planches.verdicts
                                     if cle[0] == autre]
    assert not planches.porte_le_meme_SENS(planche, avant,
                                           condensat_de_l_autre), (
        "la page 2 a ete acceptee a la place de la page 1 : la tolerance ne "
        "compare plus le payload aux faits du baseline")

    # (3) un condensat qui ne designe rien.
    assert not planches.porte_le_meme_SENS(planche, avant, "0" * 64)

    # (4) un suffixe qui n'est pas celui d'une planche.
    assert not planches.porte_le_meme_SENS("scans/lot-b/page_01.txt", avant,
                                           apres)

    # (5) ce que la tolerance laisse passer et ce qu'elle NE peut pas avaler :
    # elle n'excuse que la valeur d'un condensat et les chaines qui le citent.
    # On greffe, a cote du condensat qui change, trois changements de contenu
    # de la famille que l'arbitrage nomme, et les trois doivent etre NOMMES.
    hors_qr = {
        "projet.documents.d.json.pages[0].frame_zones[0].crop_rect_px.x": 909,
        "projet.documents.d.json.pages[0].page_count": 2,
        "projet.documents.d.json.pages[0].frame_zones[0].zone_name":
            "frame_zone_1",
    }
    deplace = {
        "projet.documents.d.json.pages[0].frame_zones[0].crop_rect_px.x": 910,
        "projet.documents.d.json.pages[0].page_count": 1,
        "projet.documents.d.json.pages[0].frame_zones[0].zone_name":
            "frame_zone_UN",
    }
    gauche = {"projet": {"arbre": {planche: avant}, "documents": {}}}
    droite = {"projet": {"arbre": {planche: apres}, "documents": {}}}
    for cle, valeur in hors_qr.items():
        gauche.setdefault("greffe", {})[cle] = valeur
    for cle, valeur in deplace.items():
        droite.setdefault("greffe", {})[cle] = valeur
    divergents = divergents_hors_liaison(gauche, droite, planches)
    assert divergents == {f"greffe.{cle}" for cle in hors_qr}, (
        "un contenu de planche change HORS du QR -- une frame deplacee, une "
        "page en moins, un libelle reecrit -- a ete avale par la tolerance : "
        f"{sorted(divergents)}")


def test_le_SEUL_changement_de_comportement_de_la_vague_est_CELUI_QUI_EST_ECRIT(
        releve):
    """Ce que la ligne L18 dit, mesure plutot que declare.

    « Le refus d'une couche `manual-corrections-v1` [...] devient un refus de
    `scan write`, la ou c'etait un silence » -- verbatim. Le scenario pose la
    couche a la main sur un document que `scan detect` vient d'ecrire, ce
    qu'aucune commande de la CLI ne sait faire : c'est ce qui rend le
    changement inatteignable par un parcours reel, et c'est aussi pourquoi il
    doit etre montre ici.

    Les trois moities du changement sont nommees : le code passe de `0` a `1`,
    le motif est **imprime** et nomme l'arbitrage qui a retire le levier, et
    **aucune frame** n'est ecrite la ou le baseline en ecrivait huit.
    """
    nom, = DIVERGENCE_L18
    avant = _reference()["scenarios"][nom]
    apres = releve["scenarios"][nom]

    assert (avant["code"], apres["code"]) == (0, 1)
    assert not any("manual-corrections-v1" in ligne
                   for ligne in avant["stdout"] + avant["stderr"]), (
        "au baseline la couche etait ignoree EN SILENCE : rien ne devait la "
        "nommer")
    assert any("EPIC7-ARB-102" in ligne for ligne in apres["stderr"]), (
        "le refus doit NOMMER l'arbitrage qui a retire le levier, pas rendre "
        "un desaccord de version opaque")

    # Le prefixe est celui d'AUJOURD'HUI des deux cotes : la reference est
    # traduite (story 11.14), et un prefixe fige au mot du baseline rendrait
    # cette mesure muette -- huit frames attendues, zero trouvee, pour une
    # raison qui n'est pas celle que le test annonce.
    frames = lambda etat: sorted(
        c for c in etat["projet"]["arbre"]
        if c.startswith(f"{DOSSIER_DES_FRAMES_SCANNEES}/"))
    assert len(frames(avant)) == 8, frames(avant)
    assert frames(apres) == [], (
        "le refus doit tomber AVANT toute ecriture : "
        f"{frames(apres)}")


#: Les champs qu'un lot de manifest et un payload de planche portent TOUS LES
#: DEUX. Ce sont eux qui font du manifest du baseline un temoin de ce que ses
#: tirages disaient : le manifest ne recopie pas le QR, il en garde ce dont il
#: se sert, et ce dont il se sert est ce qui est ecrit dessus.
CHAMPS_DU_LOT_DANS_LE_PAYLOAD = ("lot_id", "rush_id", "template_id",
                                 "patch_preset_id", "gamut_map_id",
                                 "fps_target", "timecode_base_fps")


def _faits_du_lot(scenario: dict, lot_id: str) -> dict:
    """Ce que le manifest de ce scenario dit du lot `lot_id`, champ a champ.

    Le lot se retrouve **par son identifiant** et non par son rang : deux lots
    du meme rush a deux cadences vivent cote a cote dans ce manifest, et un
    rang fige ferait mesurer l'un pour l'autre -- c'est litteralement le
    mutant `M25` de la story 5.7.
    """
    plat = scenario["projet"]["documents"]["project.json"]
    prefixe, = {cle.rsplit(".", 1)[0] for cle, valeur in plat.items()
                if cle.endswith(".lot_id") and valeur == lot_id}
    faits = {champ: plat[f"{prefixe}.{champ}"]
             for champ in CHAMPS_DU_LOT_DANS_LE_PAYLOAD
             if f"{prefixe}.{champ}" in plat}
    faits["project_id"] = plat["project_id"]
    return faits


def test_le_pied_technique_ne_change_QUE_le_condensat_des_planches_v2(
        releve, planches):
    """Ce que la ligne **L25** dit, mesure plutot que declare (`EPIC11-ARB-87`).

    Le pied technique des planches change : dix renseignements au lieu de six,
    sous des cles courtes, pour qu'une pile denuee de QR se retape a la main.
    C'est un changement de comportement **voulu**, et le seul de la vague en
    dehors de celui de L18 -- mais encore faut-il montrer qu'il ne traine rien
    d'autre avec lui.

    **L'assertion est celle de l'ensemble**, comme partout ici : les chemins qui
    divergent sont **exactement** des condensats de PDF de planches. Une
    assertion positive (« le PDF a change ») laisserait passer un message
    deplace, une cle de manifest apparue, un code de sortie bouge -- exactement
    ce que l'AC 10 interdit.

    **Et la v1 revient au condensat du baseline.** C'est l'AC 6.4 mesuree de bout
    en bout sur la vraie CLI, et non sur un plan compose en memoire : le scenario
    65 reimprime en `--geometrie v1` la planche que le 64 venait d'imprimer en
    v2, et son condensat **redevient** celui d'avant la story. Une geometrie
    gelee qui aurait bouge d'un octet se verrait ici, sur le PDF lui-meme.
    """
    reference, obtenu = _reference()["scenarios"], releve["scenarios"]
    a_plat_ref = {nom: _aplatir(etat) for nom, etat in reference.items()}
    a_plat_obt = {nom: _aplatir(etat) for nom, etat in obtenu.items()}
    # **Le 66 sort de cette boucle, et il sort NOMME.** Il ne diverge plus par
    # son seul PDF : depuis le decouplage de l'AC 2.10, il ne refuse plus du
    # tout -- code, `stdout`, `stderr`, journal et manifest bougent avec lui.
    # Le caracteriser ici l'aurait fait passer pour un pied technique qui
    # deborde ; il est mesure pour lui-meme quelques lignes plus bas.
    # Le 67 sort avec lui, et pour une raison DERIVEE : il ne se compare plus au
    # baseline sans porter le residu du 66, qui ecrit desormais un tirage la ou
    # il refusait. La propriete que le 67 doit tenir -- « un refus n'ecrit
    # rien » -- se mesure alors contre son PREDECESSEUR plutot que contre un
    # baseline devenu decale, et c'est plus fort : elle compare l'arbre entier.
    _CONFLIT_DISPARU = {"66_makepdf_deja_present_REFUS",
                        "67_makepdf_dpi_INSUFFISANT_REFUS"}
    for nom in sorted(DIVERGENCE_L25 - _CONFLIT_DISPARU):
        divergents = divergents_hors_liaison(reference[nom], obtenu[nom],
                                             planches)
        assert divergents, f"{nom} est declare divergent et ne diverge plus"
        etrangers = {
            chemin for chemin in divergents
            if not (chemin.startswith("projet.arbre.planches/")
                    and _NOM_DE_TIRAGE.search(chemin))
            and not _ne_diverge_que_par_le_NOM_du_tirage(
                a_plat_ref[nom].get(chemin, _ABSENT),
                a_plat_obt[nom].get(chemin, _ABSENT))
        }
        assert etrangers == set(), (nom, sorted(etrangers))

    # **Le scenario 66 ne refuse plus, et c'est l'AC 2.10d mesuree EN BANDE**
    # (`EPIC11-ARB-175`, consequence 3). Son nom porte encore le mot `REFUS` :
    # il est la cle d'un releve de reference deja versionne, et le renommer
    # ferait diverger la liste des scenarios elle-meme, ce qui masquerait tout
    # le reste. Ce que le scenario mesure a change, pas ce qu'il s'appelle.
    #
    # Le motif est celui du decouplage : le rang avance a chaque passe, donc le
    # nom differe, donc `output_path.exists()` est faux et il n'y a plus rien a
    # refuser. Une relance produit une VERSION -- ce qu'`EPIC11-ARB-104` veut
    # -- la ou elle produisait un blocage.
    assert reference["66_makepdf_deja_present_REFUS"]["code"] == 1
    assert obtenu["66_makepdf_deja_present_REFUS"]["code"] == 0, (
        "le scenario 66 refuse encore : le rang ne se decouple pas de "
        "`--nouvelle-version`, et une relance retombe sur le conflit")
    # Et il ecrit bien un tirage VOISIN, pas un ecrasement : le tirage de rang 1
    # du meme lot est toujours la, a cote du `_v2`.
    tirages = sorted(
        chemin for chemin in obtenu["66_makepdf_deja_present_REFUS"]["projet"]["arbre"]
        if chemin.endswith(".pdf") and "rush_ident_12" in chemin)
    assert len(tirages) == 2 and tirages[1].endswith("_v2.pdf"), tirages

    # Le refus qui RESTE un refus : son code est celui du baseline, et surtout
    # il n'ECRIT rien -- son arbre est celui du scenario qui le precede, a
    # l'octet. Sans ce volet, un refus devenu succes passerait.
    assert obtenu["67_makepdf_dpi_INSUFFISANT_REFUS"]["code"] == \
        reference["67_makepdf_dpi_INSUFFISANT_REFUS"]["code"] != 0
    assert (obtenu["67_makepdf_dpi_INSUFFISANT_REFUS"]["projet"]["arbre"]
            == obtenu["66_makepdf_deja_present_REFUS"]["projet"]["arbre"]), (
        "le refus de dpi a ecrit quelque chose : un refus qui arrive apres une "
        "ecriture n'est pas un refus")
    # Son `stderr` se compare **par la tolerance**, jamais par `==` : la liaison
    # a donne des issues aux refus (`EPIC11-ARB-89`), et c'est ce que
    # `_refus_enrichi` excuse. Une egalite nue mesurerait la liaison au lieu du
    # refus.
    assert divergents_hors_liaison(
        {"stderr": reference["67_makepdf_dpi_INSUFFISANT_REFUS"]["stderr"]},
        {"stderr": obtenu["67_makepdf_dpi_INSUFFISANT_REFUS"]["stderr"]}) == set()

    # **La v1 revient a la GEOMETRIE du baseline**, et cette mesure a change de
    # nature le 2026-09-06 (`EPIC11-ARB-250`). Elle comparait les OCTETS du PDF
    # au condensat du baseline ; l'encodage QR ayant quitte OpenCV pour
    # `segno`, le motif d'encre du symbole differe et cette egalite est
    # devenue inatteignable -- voir la famille (g) plus haut.
    #
    # Ce qu'elle mesure desormais, et pourquoi c'est la MEME propriete : le
    # manifest du baseline decrit le lot `rush_ident_12` du scenario 65 avec
    # `template_id` en **-v1**, et le `template_id` est un champ du QR. On
    # decode donc les quatre pages du tirage d'aujourd'hui et on exige qu'elles
    # redisent, champ a champ, ce que le manifest du baseline attendait
    # d'elles -- geometrie comprise. Le volet symetrique est pose juste apres :
    # ces memes pages ne doivent PAS redire les faits de la **v2** du meme lot,
    # sans quoi la mesure serait vraie d'un rendu devenu insensible a
    # `--geometrie`.
    #
    # **Ce que cette mesure a perdu, dit plutot que tu** : le gel a l'OCTET de
    # la geometrie v1 contre le baseline. Une planche dont l'encre changerait
    # sans que son QR change -- une frame deplacee de quelques dixiemes de
    # millimetre, un libelle reecrit -- ne se verrait plus ici. Aucun releve du
    # depot ne porte de temoin non-QR du rendu de cette planche : la dette est
    # ouverte sous `ARB250-N2` dans `deferred-work.md`.
    v1_obtenu = _pdf(obtenu["65_makepdf_v1_portrait"], "rush_ident_12")
    v1_reference = _pdf(reference["65_makepdf_v1_portrait"], "rush_ident_12")
    assert v1_obtenu != v1_reference, (
        "la planche v1 rend les memes octets que le baseline : `EPIC11-ARB-250` "
        "serait defait, et cette mesure doit alors REDEVENIR une egalite "
        "d'octets plutot que rester une egalite de sens")
    faits_v1 = _faits_du_lot(reference["65_makepdf_v1_portrait"], "rush_ident_12")
    assert faits_v1["template_id"].endswith("-v1"), faits_v1
    assert planches.porte_les_FAITS(v1_obtenu, faits_v1), (
        "la planche reimprimee en v1 ne redit pas ce que le manifest du "
        f"baseline attendait d'elle : {faits_v1}")
    faits_v2 = _faits_du_lot(
        reference["64_makepdf_SECOND_lot_REJOUE_a_l_identique"], "rush_ident_12")
    assert faits_v2["template_id"].endswith("-v2"), faits_v2
    assert not planches.porte_les_FAITS(v1_obtenu, faits_v2), (
        "la planche v1 redit aussi les faits de la v2 : le rendu est devenu "
        "insensible a `--geometrie`, ou la mesure ne regarde plus le bon champ")
    # Volet symetrique, sans lequel la ligne ci-dessus serait vraie d'un rendu
    # devenu insensible a `--geometrie` : la v2 du MEME lot, elle, diverge bien
    # du baseline.
    v2_obtenu = _pdf(obtenu["64_makepdf_SECOND_lot_REJOUE_a_l_identique"],
                     "rush_ident_12")
    v2_reference = _pdf(reference["64_makepdf_SECOND_lot_REJOUE_a_l_identique"],
                        "rush_ident_12")
    assert v2_obtenu != v2_reference, (
        "la v2 rend les memes octets que le baseline : le pied technique de "
        "`EPIC11-ARB-87` serait inerte")
    assert v1_obtenu != v2_obtenu, (v1_obtenu, v2_obtenu)


def test_le_pont_de_l_inventaire_ne_change_QUE_le_code_et_le_VERBE(
        releve, planches):
    """Ce que la story 11.4c (lot V2, AC 9 et AC 11.2) fait, et **rien d'autre**.

    Le defaut corrige est etroit, et la fiche insiste : « **Ce n'est PAS un
    manque de tracabilite** [...] c'est l'inventaire d'avertissements que la
    commande produit deja qui n'atteint pas le code de sortie. » Ce banc mesure
    donc les deux moities du meme fait :

    * ce qui **change** -- le code de sortie du scenario `52`, et la seule
      ligne imprimee qui disait « succes » sur un lot a moitie en mires ;
    * ce qui **ne change pas** -- l'ensemble des chemins divergents est
      **exactement** ces deux-la. Aucune frame, aucun octet de manifest, aucune
      ligne de journal, aucun `stderr`. Une assertion positive (« le code a
      change ») laisserait passer une tracabilite elargie au passage, ce que le
      fait F7 nomme comme etant *le* defaut a ne pas commettre.

    **Et le volet symetrique, qui est une AC a lui seul** (9.4) : le scenario
    `51b` ecrase un lot deja passe a `pdf` sous un `--overwrite` explicite. Il
    annonce `OUTPUT_FRAME_OVERWRITTEN` -- un avertissement, donc un inventaire
    non vide -- et **garde son `0`** : l'operateur a demande l'ecrasement, et
    le degrader casserait tout appelant legitime.
    """
    nom, = DIVERGENCE_V2
    avant = _reference()["scenarios"][nom]
    apres = releve["scenarios"][nom]

    # Les deux chemins, et **exactement** eux.
    assert divergents_hors_liaison(avant, apres, planches) == \
        {"code", "stdout[1]"}, \
        sorted(divergents_hors_liaison(avant, apres, planches))

    # Le code : `0` avant, degrade apres -- et le degrade n'est ni le succes ni
    # le refus, sans quoi « ecrit mais pas ce qui etait promis » se confondrait
    # avec « refuse, rien n'est ecrit ». Les valeurs sont ecrites en clair,
    # jamais lues de la constante mesuree.
    assert avant["code"] == 0
    assert apres["code"] == 4
    assert apres["code"] not in (0, 1)

    # Le verbe : la phrase ne dit plus « succes », elle **nomme** les motifs, et
    # elle porte toujours la meme mesure -- les deux cardinaux et le verdict de
    # completude sont ceux d'avant, au caractere pres.
    assert "avec succes" in avant["stdout"][1]
    assert "succes" not in apres["stdout"][1]
    for motif in ("FRAMES_SYNTHETIQUES_PRESENTES", "LOT_INCOMPLET"):
        assert motif in apres["stdout"][1], apres["stdout"][1]
    queue = avant["stdout"][1].split("succes.", 1)[1]
    assert apres["stdout"][1].endswith(queue), (
        "la phrase degradee doit dire la MEME mesure que celle d'avant : "
        f"{apres['stdout'][1]!r}")

    # Le volet symetrique de l'AC 9.4, sur le scenario voisin qui, lui, ne
    # bouge pas : inventaire non vide, code inchange, octets inchanges.
    surveille = "51b_write_lot_deja_PDF"
    assert surveille not in DIVERGENCE_ATTENDUE
    ecrase = releve["scenarios"][surveille]
    assert any("OUTPUT_FRAME_OVERWRITTEN" in ligne
               for lignes in ecrase["projet"]["journaux"].values()
               for ligne in lignes), (
        "le scenario de l'AC 9.4 doit bel et bien ANNONCER l'ecrasement : "
        "sans cet avertissement, son `0` ne mesurerait pas l'exception, "
        "seulement une passe sans inventaire")
    assert ecrase["code"] == 0
    assert divergents_hors_liaison(
        _reference()["scenarios"][surveille], ecrase, planches) == set()


# ===========================================================================
# La table des codes de sortie : les six entrees, pas seulement l'exercee
# ===========================================================================
#
# **Pourquoi ce parcours existe, et il est ne d'un survivant.** La campagne
# d'injection du lot S6 a change d'une unite le code de sortie de
# `ReconstructionError` dans `scan_write.CODES_DE_SORTIE` : le mutant a
# **survecu** au dossier de trente-quatre scenarios. Motif mesure : les refus
# reels de `scan write` ne font tomber que trois des six familles de la table
# (`ScanOutputError`, `ReconstructionError` depuis le bloc 5, et
# `CorrectionInvalide`), les trois autres n'ayant aucun chemin CLI qui les leve.
# Un dossier de scenarios ne peut donc pas fermer la table entiere ; ce parcours
# la ferme.

from mixed_media_utility import scan_write                # noqa: E402

#: Le code que **les quatre `except` nommes du baseline** rendaient, tous les
#: quatre, pour toutes les familles qu'ils attrapaient : `print(f"Erreur:
#: {exc}", file=sys.stderr)` puis `return 1` (`cli.py` a `289f29d`, quatre
#: sites). Il est ecrit **en clair** ici et non lu de `scan_write.CODE_ERREUR` :
#: lire la constante que l'on mesure ferait un test tautologique, exactement le
#: defaut que la campagne de la story 5.9 a trouve sur la constante centrale de
#: la calibration.
CODE_DU_BASELINE = 1

#: Le prefixe que le baseline posait devant le motif, au caractere pres. Meme
#: raison qu'au-dessus : il est recopie du code d'avant, pas lu de celui d'apres.
PREFIXE_DU_BASELINE = "Erreur: "

ENTREES_DE_LA_TABLE = [pytest.param(classe, id=classe.__name__)
                       for classe, _code in scan_write.CODES_DE_SORTIE]


@pytest.mark.parametrize("classe", ENTREES_DE_LA_TABLE)
def test_chaque_entree_de_la_table_rend_LE_CODE_ET_LE_MESSAGE_du_baseline(
        passe, monkeypatch, capsys, classe):
    """AC 10.1 sur les familles qu'aucun refus reel n'atteint.

    La table est **lue**, jamais recopiee : un parametrage ecrit a la main en
    oublierait une, et c'est l'oubli qui laisse passer un code divergent -- le
    survivant qui a fait ecrire ce parcours en est la preuve.

    Ce qui est attendu vient du **code d'avant** : au `baseline_commit`, la
    conversion exception -> code de sortie etait posee **par site**, quatre
    `except` nommes qui faisaient tous exactement `print(f"Erreur: {exc}",
    file=sys.stderr)` puis `return 1`. Elle est desormais posee **par type**,
    sur la table du coeur. Les deux doivent coincider sur chaque famille.

    Une seule entree n'a pas de cote gauche, et c'est assume :
    `CorrectionInvalide` est **neuve** (story 11.4b, lot S3) -- avant elle, une
    identite incompletable sortait en trace Python nue. Le code `1` qu'elle rend
    est celui qu'AC 4.5 exige, et le scenario `53` du dossier en mesure la
    moitie observable.
    """
    from mixed_media_utility import cli

    projet = passe[1] / "projets" / "socle"
    document, = sorted((projet / "scans").rglob("detections/*.json"))
    profil, = sorted((projet / "versions" / "calibration").glob("*.json"))
    panne = classe("panne simulee")

    def toujours_en_panne(*args, **kwargs):
        raise panne

    monkeypatch.setattr(scan_write, "ecrire_le_lot_detecte", toujours_en_panne)
    code = cli.main([outils.COMMANDE_ECRITURE, "--project", str(projet),
                     "--detection", str(document), "--profil", str(profil)])
    capture = capsys.readouterr()

    assert code == CODE_DU_BASELINE, (
        f"{classe.__name__} rend {code}, le baseline rendait "
        f"{CODE_DU_BASELINE}")
    assert PREFIXE_DU_BASELINE + str(panne) in capture.err.splitlines(), (
        f"{classe.__name__} : le motif du coeur doit sortir **prefixe et non "
        f"reecrit** sur stderr ; vu : {capture.err.splitlines()[-3:]}")


def test_la_panne_simulee_ATTEINT_bien_l_enveloppeur(passe, monkeypatch):
    """Volet symetrique : sans lui, le parcours ci-dessus pourrait etre vert
    parce que la commande refuse **avant** d'appeler le coeur.

    Si une garde de lecture du document tombait la premiere, les six cas
    rendraient `1` et le message d'un tout autre refus -- et la table ne serait
    pas mesuree du tout. La sonde compte donc les appels reellement recus.
    """
    from mixed_media_utility import cli

    projet = passe[1] / "projets" / "socle"
    document, = sorted((projet / "scans").rglob("detections/*.json"))
    profil, = sorted((projet / "versions" / "calibration").glob("*.json"))
    appels = []

    def sonde(*args, **kwargs):
        appels.append(kwargs)
        raise scan_write.ReconstructionError("panne simulee")

    monkeypatch.setattr(scan_write, "ecrire_le_lot_detecte", sonde)
    cli.main([outils.COMMANDE_ECRITURE, "--project", str(projet),
              "--detection", str(document), "--profil", str(profil)])
    assert len(appels) == 1, (
        "le coeur n'a pas ete appele : le parcours des codes de sortie "
        "mesurerait un refus de lecture de document, pas la table")


# ===========================================================================
# Le bloc `makepdf` -- l'artefact PHYSIQUE, compare octet a octet
# ===========================================================================

#: Les scenarios du bloc 6 qui produisent un PDF, et le lot que chacun imprime.
#: Le **second** lot est vise d'abord (regle des fabriques) : une pagination qui
#: rendrait toujours celle du premier lot ne se demasque pas autrement.
IMPRESSIONS = {
    "62_makepdf_SECOND_lot_v2_portrait": "rush_ident_12",
    "63_makepdf_premier_lot_v2_portrait": "rush_ident_5",
    "64_makepdf_SECOND_lot_REJOUE_a_l_identique": "rush_ident_12",
    "65_makepdf_v1_portrait": "rush_ident_12",
}


def _pdf(etat: dict, lot: str) -> str:
    """Le condensat du PDF de ce lot dans l'arbre d'un scenario."""
    chemins = [chemin for chemin in etat["projet"]["arbre"]
               if chemin.endswith(".pdf") and lot in chemin]
    assert len(chemins) == 1, (lot, sorted(etat["projet"]["arbre"]))
    return etat["projet"]["arbre"][chemins[0]]


def test_le_PDF_est_bien_dans_la_comparaison_OCTET_A_OCTET(releve):
    """Le PDF n'est pas decrit, il est **compare**.

    Il tombe dans `arbre` comme un TIFF -- chemin relatif -> condensat du
    contenu --, donc les tests d'identite ci-dessus le comparent deja octet a
    octet. Ce temoin existe pour que ce fait ne devienne pas faux en silence :
    si le bloc `makepdf` cessait de produire un PDF, ou si le releveur cessait
    de le condenser, l'egalite globale resterait verte en n'observant plus rien.
    """
    scenarios = releve["scenarios"]
    for nom, lot in IMPRESSIONS.items():
        assert _pdf(scenarios[nom], lot), nom
    # Et la reference en porte, elle aussi, avec les memes noms de fichier :
    # un PDF ecrit ailleurs ou nomme autrement se verrait ici.
    reference = _reference()["scenarios"]
    for nom, lot in IMPRESSIONS.items():
        attendus = sorted(c for c in reference[nom]["projet"]["arbre"]
                          if c.endswith(".pdf"))
        obtenus = sorted(c for c in scenarios[nom]["projet"]["arbre"]
                         if c.endswith(".pdf"))
        # **Les noms sont normalises avant d'etre compares** : depuis
        # `EPIC11-ARB-171` le nom d'un tirage porte sa mise en page, donc aucun
        # chemin de PDF de planches n'est plus celui du baseline. Ce qui reste
        # mesure -- et c'est ce que ce test veut -- est qu'il y a le meme
        # NOMBRE de PDF, aux memes emplacements, sans qu'aucun n'apparaisse ni
        # ne disparaisse.
        assert ([_NOM_DE_TIRAGE.sub("<tirage>", c) for c in obtenus]
                == [_NOM_DE_TIRAGE.sub("<tirage>", c) for c in attendus]), (
            nom, obtenus, attendus)
        # Et le renommage a bien EU LIEU : sans ce volet, la normalisation
        # ci-dessus rendrait ce test vert sur un `build_sheets_pdf_filename`
        # revenu a `_planches`, c'est-a-dire sur l'AC 2.9 annulee.
        planches = [c for c in obtenus if "rush_ident" in c and "calibration" not in c]
        assert planches and not any(c.endswith("_planches.pdf") for c in planches), (
            nom, obtenus)


def test_le_PDF_est_REPRODUCTIBLE_et_la_mesure_est_EN_BANDE(releve):
    """Le fait que la comparaison octet a octet du PDF soit **possible**.

    Mesure du 2026-08-30, quatre passes sur le meme lot et le meme commit : le
    PDF de `reportlab` n'est reproductible **ni** tel quel, **ni** avec la seule
    horloge figee (`reportlab` pose son propre `/ID` et son `/CreationDate`) ;
    il l'est avec `rl_config.invariant` seul, mais alors **seulement dans la
    meme minute**, la ligne « genere le ... » imprimee sur la planche ayant la
    minute pour granularite. Les deux gels sont donc necessaires ensemble, et
    c'est le second qui rend une reference **versionnee** valable au-dela de la
    minute ou elle a ete ecrite.

    Le temoin est **en bande** : le scenario `64` rejoue le `62` a l'identique,
    avec `--overwrite`, et les deux doivent rendre les memes octets. Si la
    reproductibilite cessait -- une version de `reportlab` qui ignore le
    reglage, un gel qui ne prend plus --, ce test rougirait **avant** que la
    comparaison au baseline ne devienne un faux positif.
    """
    scenarios = releve["scenarios"]
    rejoue = _pdf(scenarios["64_makepdf_SECOND_lot_REJOUE_a_l_identique"],
                  "rush_ident_12")
    assert _pdf(scenarios["62_makepdf_SECOND_lot_v2_portrait"],
                "rush_ident_12") == rejoue, (
        "deux `makepdf` identiques rendent des octets differents : le PDF "
        "n'est plus reproductible, et sa comparaison au baseline ne mesure "
        "plus le code")

    # Volet symetrique : un PDF qui serait reproductible parce qu'il ne depend
    # plus de ses options ne mesurerait rien non plus. La v1 et la v2 du meme
    # lot doivent differer.
    assert _pdf(scenarios["65_makepdf_v1_portrait"], "rush_ident_12") != rejoue, (
        "la v1 et la v2 du meme lot rendent les memes octets : le drapeau "
        "`--geometrie` serait inerte, et le bloc ne mesurerait pas la mise en "
        "page")


#: Ce que la pagination doit rendre, **ecrit ici** et non lu de
#: `pdf_composition.nombre_de_planches` : lire la fonction que l'on mesure
#: serait le test tautologique de la story 5.9. Les deux nombres sont ceux de
#: `ceil(frames / 4)` pose a la main -- 12 frames font 3 planches, et 5 frames
#: en font **2**, pas 1 : c'est le regime « qui ne tombe pas juste », celui que
#: le lot S4 a extrait de `compose_lot_plan`.
PLANCHES_ATTENDUES = {"62_makepdf_SECOND_lot_v2_portrait": 3,
                      "63_makepdf_premier_lot_v2_portrait": 2}


@pytest.mark.parametrize("nom", sorted(PLANCHES_ATTENDUES))
def test_les_DEUX_CADENCES_du_meme_rush_ne_paginent_PAS_pareil(releve, nom):
    """La formule de pagination, mesuree sur ce que la commande **imprime**.

    `EPIC11-ARB-84` / lot S4 : `page_count = ceil(frames / emplacements)` a
    quitte le milieu de `compose_lot_plan` pour `pdf_composition.
    nombre_de_planches`, afin que le chemin de scan la lise au lieu de la
    recopier. Le bloc 6 la traverse par les **deux** cadences du meme rush, a
    comptes differents (5 et 12 frames) : une pagination qui rendrait toujours
    celle du premier lot -- le mutant `M25` de la story 5.7 -- passe une mesure
    globale et pas celle-ci.
    """
    lignes = [ligne for ligne in releve["scenarios"][nom]["stdout"]
              if "makepdf termine avec succes" in ligne]
    assert len(lignes) == 1, lignes
    planches = int(re.search(r"(\d+) page\(s\)", lignes[0]).group(1))
    assert planches == PLANCHES_ATTENDUES[nom], lignes[0]
    # Et les deux cadences ne rendent pas le meme nombre : sans cette ligne, un
    # cardinal fige passerait les deux parametrages.
    assert len(set(PLANCHES_ATTENDUES.values())) == 2
