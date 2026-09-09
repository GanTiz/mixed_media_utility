"""Story 5.23, AC 11 -- les substituts **actifs** des quatre proprietes endormies.

Ce fichier ne reveille rien. **Les 35 tests que l'AC 11 avait endormis ont depuis ete
statues par la story 5.24** (AC 8): 19 rebases sur le regime de profil designe, 15
reecrits contre le tri par QR, 1 supprime avec son motif. Le registre et son
constructeur ont ete retires dans le meme mouvement, et
`test_aucun_test_endormi.py` porte ce qui leur survivait -- « aucun test du depot ne
dort en silence ». Les quatre substituts ci-dessous, eux, restent: ils mesurent des
proprietes qui n'ont jamais dependu du vrac.

Ce qu'il ecrit est autre chose: **quatre tests neufs** qui reprennent, dans un regime
valide aujourd'hui, quatre proprietes que l'endormissement a fait taire sans substitut
ni declaration. Les deux couches 3 de la revue du 2026-08-19 les ont trouvees en
mappant par AST chaque `read_bytes()` sur sa fonction et son decorateur, et le fait
mesure etait: **toutes** les assertions d'octets prises apres un `scan` reel sont
endormies, les deux seules actives etant unitaires. C'est la moitie de l'AC 11 -- «
aucune assertion perdue en silence » -- qui n'etait pas tenue.

Les quatre proprietes reprises ici:

1. les frames de la planche **deviante** sont corrigees **dans les octets** (AC 3, que
   son test endormi annoncait lui-meme comme « la plus importante de la story »);
2. la correction va **vers** la reference -- pas « elle change quelque chose », mais «
   elle change dans le bon sens », donc l'ecart apres est **plus petit** qu'avant;
3. `--cc off` ecrit **vraiment** du brut, mesure sur les fichiers et non sur le champ de
   manifest que le logiciel ecrit lui-meme;
4. le defaut de `--cc` est `on` et son vocabulaire est **ferme**, mesures par le **vrai**
   parseur -- c'est dans `argparse` que vivent le defaut et le refus, pas dans la
   fonction appelee directement.

**Le regime, et c'est tout l'enjeu du fichier: aucune pile mixte.** Les tests endormis
s'appuyaient sur une page de calibration posee au scanner **parmi** les planches, ce que
l'AC 10 refuse desormais. Depuis `EPIC5-ARB-82`, une planche ordinaire recoit sa
correction du **profil de sa chaine** (`correction_source = chain_profile`) sans qu'aucune
page de calibration ne soit dans la passe: la chaine est calibree une fois par
`scan calibrate` sur sa page seule, puis chaque scan **designe** son profil par `--profil`
(`EPIC5-ARB-83`). Ce regime porte les quatre proprietes sans en affaiblir aucune.

**Ce qui est asserte est un octet ou un pixel de fichier ecrit, jamais un champ de
manifest** (`EPIC5-ARB-39`: « un test d'integration contre le vrai producteur ne suffit
pas s'il n'asserte pas sur chaque famille de valeurs projetee »). Un test qui lit
`entree["status"]` ne prouve rien: c'est le champ que le logiciel ecrit lui-meme. Les
champs de manifest n'apparaissent ici que comme **temoins de domaine** -- « la planche
diverge reellement », « le lot se declare corrige » --, jamais comme preuve de la
correction.

Regle des fabriques (CLAUDE.md), appliquee des deux cotes:

* le lot nominal porte **deux** planches imprimees sous des presses **differentes**: un
  appariement planche -> correction permute se verrait, et deux entrees identiques au
  chiffre pres ne prouveraient rien;
* le lot deviant porte **trois** planches et la deviante est la **deuxieme** -- ni
  premiere ni derniere. Une garde qui ne regarderait que la premiere planche se demasque,
  et une qui ne regarderait que la derniere aussi;
* les quatre zones de frame portent quatre couleurs **distinctes**, et l'assertion de
  direction porte sur chacune: une correction qui ne marcherait que sur un bleu passerait
  un test a une couleur.

Cout: le banc partage calibre la chaine **une fois** et lance six scans, mesures a ~25 s
en tout. Les quatre tests lisent ses fichiers sans rien rescanner.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import cli  # noqa: E402

import test_calibration_page_source as couleur  # noqa: E402
import test_chain_profile_scan as chaine  # noqa: E402
import test_scan_calibration_application as app  # noqa: E402


# ---------------------------------------------------------------------------
# Les litteraux du contrat, epingles ici et nulle part ailleurs
# ---------------------------------------------------------------------------

#: Les couleurs **imprimees** dans les quatre zones de frame, en litteral.
#:
#: Ce n'est pas une redite de la fabrique: c'en est l'epinglage. La direction de la
#: correction se mesure contre la couleur qui a ete posee sur le papier, et si cette
#: couleur changeait, un test qui la relirait dans la fabrique se re-etalonnerait tout
#: seul sur la nouvelle valeur -- il resterait vert en ayant cesse de mesurer quoi que ce
#: soit. Ecrite ici, une divergence entre les deux se voit (garde ci-dessous) et se relit
#: par un humain.
_COULEURS_IMPRIMEES_BGR = ((40, 90, 200), (180, 60, 45), (60, 170, 90), (150, 150, 60))

#: Le prefixe et le separateur du nom de frame ecrite. Le **reste** du nom vient du
#: payload que le test a lui-meme fait imprimer au QR (`slots[i]["frame_timecode"]`),
#: donc l'appariement frame -> planche n'est pas devine par un tri: il est lu dans le
#: contrat de la page. Un changement de nomenclature fait echouer ce fichier au lieu de
#: re-apparier en silence, et c'est le comportement voulu.
_PREFIXE_FRAME = "scan_"
_SUFFIXE_FRAME = ".tiff"

#: Le vocabulaire de `--cc`, en litteral **et non par les constantes de `cli`**: ce qui
#: est mesure ici est ce que l'operateur tape, pas ce que le module se dit a lui-meme.
_CC = "--cc"
_CC_ON = "on"
_CC_OFF = "off"
_PROFIL = "--profil"

#: Les deux valeurs de statut de lot, en litteral, pour la meme raison. Elles ne servent
#: que de temoins de domaine.
_APPLIED = "applied"
_NOT_APPLIED = "not_applied"


# ---------------------------------------------------------------------------
# Le banc partage
# ---------------------------------------------------------------------------


class _Passe:
    """Une passe de scan achevee: son code de sortie, son projet, ses frames."""

    def __init__(self, code: int, project_dir: Path) -> None:
        self.code = code
        self.project_dir = project_dir
        self.document = app.manifest_of(project_dir)
        self.frames = {chemin.name: chemin
                       for chemin in app.written_frames(project_dir, self.document)}

    @property
    def statut(self) -> str:
        return self.document["color"]["color_calibration_status"]


class _Banc:
    """Ce que les quatre tests lisent: deux lots, six passes, aucune pile mixte."""

    def __init__(self) -> None:
        self.profil = ""
        self.nominal_payloads: list = []
        self.deviant_payloads: list = []


def _noms_de_page(payload: dict) -> list[str]:
    """Les noms des frames d'**une** planche, lus dans le payload de sa page.

    Le timecode de chaque emplacement est ce que le QR porte et ce que la reconstruction
    projette dans le nom du fichier. Le lire ici plutot que de trier les fichiers evite
    l'appariement positionnel implicite qui a produit `M33` et `M25` dans ce depot.
    """
    return [_PREFIXE_FRAME + payload["lot_id"] + "_"
            + emplacement["frame_timecode"].replace(":", "-") + _SUFFIXE_FRAME
            for emplacement in payload["slots"]]


@pytest.fixture(scope="module")
def banc(tmp_path_factory) -> _Banc:
    """Une chaine calibree une fois, deux lots, six passes.

    Les six passes sont lancees ici et non dans les tests: une passe coute ~3 a 5 s et
    quatre tests qui rescanneraient chacun leur lot paieraient quatre fois la meme
    mesure. Le banc n'assert que les codes de sortie -- tout ce qui est propriete de la
    story est asserte dans les tests, ou un echec se lit comme un echec.
    """
    base = tmp_path_factory.mktemp("substituts-ac11")
    resultat = _Banc()

    # 1. La chaine est calibree sur sa page **seule**: c'est le regime de `EPIC5-ARB-83`,
    #    et c'est ce qui garantit qu'aucune page de calibration n'entrera dans les passes
    #    qui suivent.
    projet_chaine = base / "projet-chaine"
    assert chaine._calibrate_chain(projet_chaine, base) == 0
    resultat.profil = chaine._profil_de(projet_chaine)

    # 2. Le lot nominal: deux planches, deux presses **distinctes** du meme tirage.
    lot_nominal = base / "lot-nominal"
    resultat.nominal_payloads = chaine._write_images_lot(lot_nominal)

    # 3. Le lot deviant: trois planches, la deviante en **deuxieme** position -- ni
    #    premiere ni derniere. Les deux autres sont distinguables entre elles.
    lot_deviant = base / "lot-deviant"
    resultat.deviant_payloads = chaine._write_images_lot(
        lot_deviant, sheet_count=3,
        presses=(app.PRESSES_DU_TIRAGE[0], couleur._DEVIANT_PRESS,
                 app.PRESSES_DU_TIRAGE[1]))

    def passe(nom: str, dossier: Path, *args: str) -> _Passe:
        project_dir = base / f"projet-{nom}"
        code = app.run_scan(project_dir, dossier, *args)
        assert code == 0, (nom, code)
        return _Passe(code, project_dir)

    # Le defaut: **aucun** `--cc` sur la ligne de commande.
    resultat.nominal_defaut = passe("nominal-defaut", lot_nominal, _PROFIL, resultat.profil)
    resultat.nominal_on = passe("nominal-on", lot_nominal, _PROFIL, resultat.profil,
                                _CC, _CC_ON)
    resultat.nominal_off = passe("nominal-off", lot_nominal, _PROFIL, resultat.profil,
                                 _CC, _CC_OFF)
    # Le temoin brut: le **meme** lot, les memes rasters, sans profil designe -- donc
    # livre tel quel (`EPIC5-ARB-83`: aucun profil n'est choisi automatiquement).
    resultat.nominal_brut = passe("nominal-brut", lot_nominal)

    resultat.deviant_corrige = passe("deviant-corrige", lot_deviant,
                                     _PROFIL, resultat.profil)
    resultat.deviant_brut = passe("deviant-brut", lot_deviant)

    resultat.lot_nominal = lot_nominal
    return resultat


def _ecart_max(chemin: Path, couleur_bgr) -> float:
    """L'ecart maximal, en codes 8 bits, entre le centre d'une frame et sa couleur.

    La couleur de reference est celle qui a ete **imprimee**; l'ecart mesure donc ce que
    la chaine impression+scan a deforme, et la correction est censee le reduire.
    """
    vraie = np.asarray(couleur_bgr, dtype=np.float64) / 255.0
    return float(np.abs(app._frame_centre(chemin) - vraie).max()) * 255.0


# ---------------------------------------------------------------------------
# Propriete 1 -- la planche deviante est corrigee DANS LES OCTETS (AC 3)
# ---------------------------------------------------------------------------


def test_substitut_les_frames_de_la_planche_deviante_sont_corrigees_dans_les_octets(
        banc) -> None:
    """AC 3, sur les octets: la bascule d'`EPIC5-ARB-82` pose des pixels, elle ne se
    contente pas de l'ecrire au manifest.

    Le test endormi qui portait cette preuve la mesurait sur un lot qui portait sa propre
    page de calibration. Ici le meme fait est mesure dans le regime de chaine: le **meme**
    lot, aux **memes** rasters, est scanne deux fois -- profil designe, puis sans profil
    designe --, et tout ecart entre les fichiers vient de la correction et de rien d'autre.

    Ce que la story a change et qui se verifie ici: la planche deviante n'est plus
    amputee de sa correction. Un code qui ne corrigerait que les planches nominales tombe
    sur le volet de la deviante; un code qui ne corrigerait personne tombe sur les deux.
    """
    corrige, brut = banc.deviant_corrige, banc.deviant_brut

    # -- Domaine: la planche du milieu diverge **reellement**, les deux autres non.
    entrees = app.calibration_entries(corrige.document)
    assert sorted(entrees) == [0, 1, 2], entrees
    divergentes = [index for index, entree in entrees.items()
                   if (entree.get("divergence") or {}).get("diverges") is True]
    # La deviante est en **deuxieme** position: une garde qui rendrait la premiere
    # planche, ou la derniere, se demasque ici.
    assert divergentes == [1], entrees
    divergence = entrees[1]["divergence"]
    assert divergence["excess_residual_de76"] > divergence["threshold_de76"], divergence
    assert divergence["threshold_de76"] > 0.0, divergence
    # Elle est livree corrigee et non refusee: les deux cles d'absence de correction sont
    # **absentes**, pas seulement d'une autre valeur.
    assert entrees[1]["status"] == _APPLIED, entrees[1]
    assert "failure_reason" not in entrees[1], entrees[1]
    assert "not_applied_reason" not in entrees[1], entrees[1]

    # -- L'appariement frame -> planche est lu dans le payload, pas devine par un tri.
    attendus = {payload["page_index"]: _noms_de_page(payload)
                for payload in banc.deviant_payloads}
    tous = sorted(nom for noms in attendus.values() for nom in noms)
    assert len(tous) == 12, tous
    assert sorted(corrige.frames) == tous, sorted(corrige.frames)
    assert sorted(brut.frames) == tous, sorted(brut.frames)

    # -- La preuve: les octets de la planche deviante.
    for nom in attendus[1]:
        assert corrige.frames[nom].read_bytes() != brut.frames[nom].read_bytes(), (
            f"{nom}: la planche deviante doit etre corrigee elle aussi -- c'est la "
            "bascule d'`EPIC5-ARB-82`, et elle se verifie dans les octets")

    # -- Et les deux planches nominales le sont aussi: sans ce volet, « la deviante est
    #    corrigee » serait tenu par un code qui ecrirait n'importe quoi partout.
    for page_index in (0, 2):
        for nom in attendus[page_index]:
            assert corrige.frames[nom].read_bytes() != brut.frames[nom].read_bytes(), (
                f"{nom}: la planche ordinaire {page_index} doit etre corrigee")

    # -- Temoin de domaine: le lot corrige se declare corrige, le temoin ne l'est pas.
    assert corrige.statut == _APPLIED
    assert brut.statut == _NOT_APPLIED


# ---------------------------------------------------------------------------
# Propriete 2 -- la correction va VERS la reference (AC 3)
# ---------------------------------------------------------------------------


def test_substitut_la_correction_va_vers_la_reference_sur_les_fichiers_ecrits(
        banc) -> None:
    """AC 3: la correction ne change pas seulement les octets, elle les change **dans le
    bon sens**.

    C'est la propriete qu'un simple « les fichiers different » ne tient pas: un code qui
    degraderait la couleur passerait ce test-la et tomberait ici. Trois clauses, et la
    troisieme est celle qui interdit la correction identite:

    1. l'ecart a la couleur imprimee est **plus petit** apres correction;
    2. il est plus petit **d'un facteur 3 au moins** -- sans quoi « plus proche » serait
       tenu par une correction qui rapproche d'un centieme de code;
    3. il est petit **dans l'absolu**, borne en litteral.

    La borne relative d'abord, l'absolue ensuite: c'est l'ordre retenu par la story 5.21,
    parce qu'un rapport ne se redate pas a chaque changement de forme de correction.

    Les huit frames sont mesurees, sur **quatre** couleurs distinctes et **deux** planches
    imprimees sous des presses differentes: une correction qui ne marcherait que sur un
    bleu, ou que sur la premiere planche, tombe.
    """
    # Garde d'epinglage: la fabrique et le litteral de ce fichier doivent dire la meme
    # chose. S'ils divergent, la reference de la mesure a bouge et cela se relit a la
    # main -- ce test ne se re-etalonne pas tout seul.
    assert app.FRAME_COLOURS_BGR == _COULEURS_IMPRIMEES_BGR, app.FRAME_COLOURS_BGR

    corrige, brut = banc.nominal_defaut, banc.nominal_brut
    mesures = 0
    for payload in banc.nominal_payloads:
        for rang, nom in enumerate(_noms_de_page(payload)):
            couleur_bgr = _COULEURS_IMPRIMEES_BGR[rang % len(_COULEURS_IMPRIMEES_BGR)]
            ecart_corrige = _ecart_max(corrige.frames[nom], couleur_bgr)
            ecart_brut = _ecart_max(brut.frames[nom], couleur_bgr)
            # Domaine: le brut est reellement deforme. Sans cette clause, « plus proche »
            # se jouerait dans le bruit d'une frame deja juste. Mesure du 2026-08-19:
            # 19 a 28 codes de deformation brute sur ce banc.
            assert ecart_brut > 10.0, (nom, ecart_brut)
            assert ecart_corrige < ecart_brut, (nom, ecart_corrige, ecart_brut)
            assert ecart_corrige < ecart_brut / 3.0, (nom, ecart_corrige, ecart_brut)
            # Borne absolue, en litteral. Mesure du 2026-08-19 sur ce banc: 1,2 a 5,4
            # codes corriges. La borne laisse la marge d'un changement de forme sans
            # laisser passer une correction qui n'aurait plus rien corrige.
            assert ecart_corrige < 8.0, (nom, ecart_corrige)
            mesures += 1
    # Le cardinal **avant** la conclusion: une boucle vide passerait tout.
    assert mesures == 8, mesures


# ---------------------------------------------------------------------------
# Propriete 3 -- `--cc off` ecrit vraiment du brut (`EPIC5-ARB-78`, AC 8)
# ---------------------------------------------------------------------------


def test_substitut_le_drapeau_cc_off_ecrit_reellement_des_frames_non_corrigees(
        banc) -> None:
    """`EPIC5-ARB-78`, mot pour mot d'Egan: « si le resultat est rate l'utilisateur peut
    relancer la commande avec un flag --cc off ».

    Le test endormi nommait d'avance ce qui resterait sans lui: « un test qui ne lirait
    que le manifest passerait sur une implementation qui declare `not_applied` et corrige
    quand meme ». C'etait exactement l'etat du depot -- le seul test actif qui exerce
    `--cc off` de bout en bout n'assert que des champs de manifest.

    Ce que ce substitut mesure sur les fichiers, et qui est plus fort qu'un simple « les
    frames different »: `--cc off` ecrit **exactement** les octets qu'ecrit une passe qui
    n'a aucun profil a appliquer. Pas « quelque chose d'autre que la correction »: le brut
    lui-meme, octet pour octet.

    Le temoin est indispensable et il est pris sur le **meme** lot: sans lui, l'egalite
    ci-dessus serait tenue par une chaine ou le profil ne corrige rien du tout.
    """
    off, brut, corrige = banc.nominal_off, banc.nominal_brut, banc.nominal_defaut

    attendus = sorted(nom for payload in banc.nominal_payloads
                      for nom in _noms_de_page(payload))
    assert len(attendus) == 8, attendus
    assert sorted(off.frames) == attendus, sorted(off.frames)
    assert sorted(brut.frames) == attendus, sorted(brut.frames)
    assert sorted(corrige.frames) == attendus, sorted(corrige.frames)

    for nom in attendus:
        assert off.frames[nom].read_bytes() == brut.frames[nom].read_bytes(), (
            f"{nom}: `--cc off` doit ecrire le brut, octet pour octet")

    # Temoin: sur ce meme lot et ce meme profil, la passe par defaut corrige reellement.
    # Sans lui, l'egalite ci-dessus serait vraie d'un profil inerte.
    differentes = [nom for nom in attendus
                   if off.frames[nom].read_bytes()
                   != corrige.frames[nom].read_bytes()]
    assert differentes == attendus, (
        f"toutes les frames doivent differer de la passe corrigee, seules "
        f"{differentes} different")

    # Temoins de domaine, jamais preuve: le document separe les deux regimes.
    assert off.statut == _NOT_APPLIED
    assert corrige.statut == _APPLIED


# ---------------------------------------------------------------------------
# Propriete 4 -- defaut `on` et vocabulaire ferme, par le VRAI parseur
# ---------------------------------------------------------------------------


def test_substitut_le_defaut_du_drapeau_cc_est_on_et_son_vocabulaire_est_ferme(
        banc, tmp_path) -> None:
    """Deux proprietes que `EPIC5-ARB-78` impose, et qui se perdent l'une sans l'autre.

    * le **defaut** est `on`: une option nouvelle ne change pas ce que fait une commande
      deja tapee. Mesure en comparant une invocation **sans** le drapeau a une invocation
      `--cc on`, sur les octets, et pas en lisant le code;
    * le vocabulaire est **ferme** a deux valeurs, et il n'existe aucun reglage numerique
      a cote. Mesure par le **point d'entree reel**: le defaut et le refus vivent dans
      `argparse`, et un parseur reconstruit par le test ne prouverait rien de celui que
      l'operateur rencontre. C'est aussi pourquoi les trois chaines `--cc`, `on` et `off`
      sont ecrites en litteral ici plutot que reprises des constantes de `cli`: ce qui est
      mesure est ce que l'operateur tape.

    La troisieme clause est le temoin: les octets du defaut different de ceux de
    `--cc off`. Sans elle, « defaut == on » serait tenu par une chaine ou les deux
    invocations ne corrigeraient rien.
    """
    defaut, explicite, off = banc.nominal_defaut, banc.nominal_on, banc.nominal_off

    attendus = sorted(nom for payload in banc.nominal_payloads
                      for nom in _noms_de_page(payload))
    assert len(attendus) == 8, attendus
    assert sorted(defaut.frames) == attendus, sorted(defaut.frames)
    assert sorted(explicite.frames) == attendus, sorted(explicite.frames)

    for nom in attendus:
        assert defaut.frames[nom].read_bytes() == explicite.frames[nom].read_bytes(), (
            f"{nom}: sans `--cc`, la commande doit faire ce que fait `--cc on`")

    # Temoin: le defaut n'est pas `off`. Les huit frames different de la passe `off`.
    differentes = [nom for nom in attendus
                   if defaut.frames[nom].read_bytes() != off.frames[nom].read_bytes()]
    assert differentes == attendus, differentes
    assert defaut.statut == _APPLIED
    assert explicite.statut == _APPLIED
    assert off.statut == _NOT_APPLIED

    # -- Le vocabulaire, exerce par le vrai parseur. Les deux valeurs licites ont ete
    #    acceptees par ce meme parseur au banc (codes de sortie 0 ci-dessous): sans ce
    #    volet positif, les trois refus seraient tenus par un parseur qui refuse tout.
    assert (defaut.code, explicite.code, off.code) == (0, 0, 0)

    for refuse in (["--cc", "peut-etre"], ["--cc", "ON"], ["--cc-reglage", "2.5"],
                   ["--cc"]):
        with pytest.raises(SystemExit) as sortie:
            cli.main(["scan", "--project", str(tmp_path / "refus"),
                      "--scan", str(banc.lot_nominal), "--dpi", str(app.DPI), *refuse])
        assert sortie.value.code == 2, refuse
