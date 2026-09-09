# -*- coding: utf-8 -*-
"""Vague 2 de la revue, lot B : les trois findings du coeur de maintenance.

Ce banc ferme ce que `project_maintenance.py` laissait ouvert, et il est
ecrit a part des trois bancs existants (`test_suppression_des_frames_extraites`,
`test_suppression_element_de_projet`, `test_suppression_d_un_groupe`) parce que
deux autres agents travaillent sur la meme branche : un fichier neuf ne se
dispute avec personne.

* `C2-2` -- CRITIQUE. `_refuser_le_chevauchement` ne comparait que
  `frames_dir` et `output_frames_dir`. Un `frames_dir` valant `"outputs"`
  passait la garde, `rglob` y ramassait le master encode du lot, et
  `--frames-extraites` -- la cible qui existe PRECISEMENT pour epargner les
  masters, les planches et les scans -- les detruisait pendant que le
  manifeste continuait de les declarer ;
* `C2-9` -- CRITIQUE. `_famille_des_frames_extraites.retirer()` deliait
  TOUTES les entrees de meme `lot_id`, sans regarder laquelle designait le
  dossier supprime. Son jumeau `_famille_du_lot_scanne.retirer()` se garde
  ainsi depuis toujours ;
* `C2-5` / `C3-6` -- TOLERANCE DOCUMENTEE devenue mesure. `remove_project_group`
  n'attrapait que `ProjectMaintenanceError` : un `OSError` traversait la
  boucle et emportait le compte rendu des lignes DEJA detruites, et un refus
  SANS MESSAGE faisait lever `LigneDeGroupe.__post_init__` hors du `try`,
  avortant le groupe entier.

**Regle des fabriques.** La fabrique produit TROIS lots distinguables (des
`frames_dir` differents, des contenus differents), la cible par defaut est au
MILIEU, et chaque garde est aussi jouee en TETE et en QUEUE : une garde qui
balaierait `lots` en sautant un bord reste verte sur une cible du milieu.

**Regle des drapeaux.** Chaque garde est jouee sous `dry_run=True` ET
`dry_run=False`. C'est la cause commune des huit survivants de la couche 1 :
une garde lue en apercu et jamais sur la branche qui ECRIT.
"""
from __future__ import annotations

import json

import pytest

from mixed_media_utility.io import project_layout
from mixed_media_utility.project_maintenance import (
    LigneDeGroupe,
    ProjectMaintenanceError,
    RapportSuppression,
    remove_project_element,
    remove_project_group,
)

RACINE = project_layout.EXTRACT_FRAMES_DIRNAME
SCANNEES = project_layout.SCAN_FRAMES_DIRNAME
OUTPUTS = project_layout.OUTPUTS_DIRNAME
PLANCHES = project_layout.PLANCHES_DIRNAME
SCANS = project_layout.SCANS_DIRNAME


# ---------------------------------------------------------------------------
# La fabrique : TROIS lots distinguables, la cible au milieu.
# ---------------------------------------------------------------------------


def _lot(lot_id: str, rush_id: str, cardinal: int) -> dict:
    """Un lot dont chaque objet declare porte SON identifiant.

    Les cardinaux et les contenus different d'un lot a l'autre : un
    appariement inverse entre deux lots ne se voit pas sur un remplissage
    uniforme (regle des fabriques, point 1).
    """
    return {
        "lot_id": lot_id,
        "rush_id": rush_id,
        "state": "extraction",
        "fps_target": 12.5,
        "frames_dir": f"{RACINE}/{lot_id}",
        "output_frames_dir": f"{SCANNEES}/{lot_id}",
        "expected_frame_count": cardinal,
        "encoded_masters": [{"path": f"{OUTPUTS}/{lot_id}.mov",
                             "profile": "prores_422"}],
        "sheets_pdfs": [{"path": f"{PLANCHES}/{lot_id}.pdf"}],
        "reconstructions": [{"ingest_slug": f"scan-{lot_id}"}],
    }


def _manifeste() -> dict:
    return {
        "schema_version": "2.1",
        "project_id": "projet",
        "rushes": [{"rush_id": "rush-a"}, {"rush_id": "rush-b"}],
        "lots": [
            _lot("rush-a_24", "rush-a", 2),   # <- BORD DE TETE
            _lot("rush-b_12", "rush-b", 3),   # <- la cible par defaut, AU MILIEU
            _lot("rush-a_5", "rush-a", 4),    # <- BORD DE QUEUE
        ],
    }


def _ecrire_projet(tmp_path, manifest: dict):
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    for entree in manifest["lots"]:
        lot_id = entree["lot_id"]
        for numero in range(entree.get("expected_frame_count") or 1):
            for champ in ("frames_dir", "output_frames_dir"):
                relatif = entree.get(champ)
                if not relatif:
                    continue
                dossier = projet / relatif
                dossier.mkdir(parents=True, exist_ok=True)
                (dossier / f"{lot_id}_{numero:04d}.tiff").write_bytes(
                    f"{lot_id}-{champ}-{numero}".encode())
        for entree_master in entree.get("encoded_masters") or []:
            chemin = projet / entree_master["path"]
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_bytes(f"master-{lot_id}".encode())
        for entree_pdf in entree.get("sheets_pdfs") or []:
            chemin = projet / entree_pdf["path"]
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_bytes(f"planche-{lot_id}".encode())
        for reconstruction in entree.get("reconstructions") or []:
            dossier = projet / SCANS / reconstruction["ingest_slug"]
            dossier.mkdir(parents=True, exist_ok=True)
            (dossier / "page_0001.tiff").write_bytes(f"scan-{lot_id}".encode())
    return projet


def _projet(tmp_path):
    return _ecrire_projet(tmp_path, _manifeste())


def _manifeste_relu(projet) -> dict:
    return json.loads((projet / "project.json").read_text(encoding="utf-8"))


def _tout_le_disque(projet) -> set[str]:
    return {c.relative_to(projet).as_posix()
            for c in projet.rglob("*") if c.is_file()}


# ---------------------------------------------------------------------------
# `C2-2` : les QUATRE familles d'objets declares, aux DEUX regimes de drapeau.
# ---------------------------------------------------------------------------


#: `(nom de la famille, `frames_dir` qui l'engloutit, mot attendu du refus)`.
#: Les quatre familles que le manifeste continue de declarer apres coup.
FAMILLES = [
    ("master", OUTPUTS, "le master"),
    ("planche", PLANCHES, "la planche"),
    ("scan", SCANS, "le dossier de scan"),
    ("frames scannees", SCANNEES, "le dossier"),
]


@pytest.mark.parametrize("cible", ["rush-a_24", "rush-b_12", "rush-a_5"])
@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("famille,ancetre,mot", FAMILLES)
def test_C2_2_un_frames_dir_qui_ENGLOUTIT_un_objet_declare_est_refuse(
        tmp_path, famille, ancetre, mot, dry_run, cible):
    """Le coeur du finding, joue aux TROIS positions et aux DEUX drapeaux.

    Regime mesure AVANT correctif, sur la famille `master` :
    `remove_project_element(..., frames_extraites=True, dry_run=False)` rendait
    `supprime=True`, la liste portait bien `outputs/<lot>.mov` -- l'apercu ne
    mentait pas --, le fichier disparaissait du disque et
    `encoded_masters[].path` continuait de le declarer.

    **Le drapeau varie parce que la garde pourrait ne vivre que d'un cote.**
    Une garde posee sur la seule branche qui ECRIT laisserait l'apercu
    promettre une destruction que l'execution refuse ; posee sur le seul
    apercu, elle laisserait ecrire. Les deux sens sont donc mesures, et le
    controle porte sur ce qui RESTE.
    """
    manifest = _manifeste()
    vise = next(l for l in manifest["lots"] if l["lot_id"] == cible)
    vise["frames_dir"] = ancetre
    projet = _ecrire_projet(tmp_path, manifest)
    avant = _tout_le_disque(projet)

    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id=cible, frames_extraites=True, dry_run=dry_run)

    message = str(erreur.value)
    assert mot in message, message
    assert "continue de declarer" in message
    assert "aucune suppression n'a eu lieu" in message
    # Rien n'a bouge, ni sur le disque ni au manifeste -- le refus est une
    # ISSUE nommee, pas une destruction a moitie faite.
    assert _tout_le_disque(projet) == avant
    relu = next(l for l in _manifeste_relu(projet)["lots"]
                if l["lot_id"] == cible)
    assert relu["frames_dir"] == ancetre


@pytest.mark.parametrize("dry_run", [True, False])
def test_C2_2_le_master_d_un_AUTRE_lot_est_protege_du_lot_entier(
        tmp_path, dry_run):
    """La garde vaut aussi pour la suppression du LOT ENTIER.

    Le chemin du lot entier supprime les annexes du lot VISE -- c'est son
    travail. Ce qu'il n'a pas le droit d'emporter, c'est le master d'un AUTRE
    lot tombe sous son `frames_dir`, et rien ne le lui interdisait.
    """
    manifest = _manifeste()
    # La cible est en TETE ; l'objet a epargner appartient au lot de QUEUE.
    manifest["lots"][0]["frames_dir"] = OUTPUTS
    projet = _ecrire_projet(tmp_path, manifest)
    avant = _tout_le_disque(projet)

    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="rush-a_24", dry_run=dry_run)

    assert "le master du lot" in str(erreur.value)
    assert _tout_le_disque(projet) == avant


@pytest.mark.parametrize("dry_run", [True, False])
def test_C2_2_le_cas_NOMINAL_passe_toujours(tmp_path, dry_run):
    """Frontiere symetrique : la garde ne doit RIEN refuser d'un projet sain.

    Sans ce controle, la facon la plus simple de rendre les tests ci-dessus
    verts serait de tout refuser -- un blocage sec, exactement ce
    qu'`EPIC11-ARB-89` interdit. La cible est au MILIEU, et le lot declare les
    quatre familles a la fois.
    """
    projet = _projet(tmp_path)
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True, dry_run=dry_run)
    assert rapport.fichiers_a_supprimer == tuple(
        f"{RACINE}/rush-b_12/rush-b_12_{n:04d}.tiff" for n in range(3))
    # Les objets des trois autres familles ne sont ni nommes ni touches.
    for chemin in (f"{OUTPUTS}/rush-b_12.mov", f"{PLANCHES}/rush-b_12.pdf",
                   f"{SCANS}/scan-rush-b_12/page_0001.tiff",
                   f"{SCANNEES}/rush-b_12/rush-b_12_0000.tiff"):
        assert chemin not in rapport.fichiers_a_supprimer
        assert (projet / chemin).is_file()


def test_C2_2_une_planche_DEDUITE_ne_bloque_pas_un_projet_sain(tmp_path):
    """Un manifeste anterieur a `sheets_pdfs` : les noms sont RECALCULES.

    Le repli produit 99 chemins candidats par lot, dont aucun n'existe. Les
    opposer sans discernement ferait refuser tout `frames_dir` place sous
    `planches/` -- mais surtout, il ne faut pas qu'ils fassent refuser le cas
    ordinaire. Frontiere de non-regression du cout de la garde.
    """
    manifest = _manifeste()
    for entree in manifest["lots"]:
        entree.pop("sheets_pdfs")
    projet = _ecrire_projet(tmp_path, manifest)
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    assert rapport.supprime is True
    assert "frames_dir" not in next(
        l for l in _manifeste_relu(projet)["lots"] if l["lot_id"] == "rush-b_12")


# ---------------------------------------------------------------------------
# `C2-9` : delier PAR IDENTITE, jamais par ressemblance d'identifiant.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("position", [0, 1, 2])
def test_C2_9_seule_l_entree_qui_DECLARE_le_dossier_supprime_est_deliee(
        tmp_path, position, dry_run):
    """Deux entrees de meme `lot_id`, de `frames_dir` DIFFERENTS et disjoints.

    Le chevauchement ne les refuse donc pas -- elles ne se contiennent pas --,
    et c'est ce qui rend le defaut atteignable : un seul dossier etait
    supprime, les DEUX entrees etaient deliees, et les frames de la seconde
    restaient sur le disque, orphelines, sans un mot.

    Le jumeau `_famille_du_lot_scanne.retirer()` se garde ainsi depuis
    toujours ; le fait que les deux moities du meme mecanisme aient diverge est
    exactement ce qu'une garde par IDENTITE ferme.

    La jumelle est inseree aux trois positions du listing : une boucle qui
    s'arreterait a la premiere correspondance, ou qui sauterait un bord, ne se
    demasque pas autrement.
    """
    manifest = _manifeste()
    jumelle = _lot("rush-b_12", "rush-b", 5)
    jumelle["frames_dir"] = f"{RACINE}/rush-b_12_bis"
    # La jumelle ne redeclare AUCUNE annexe : deux entrees declarant le meme
    # master seraient refusees par une autre garde, et masqueraient celle-ci.
    for cle in ("encoded_masters", "sheets_pdfs", "reconstructions",
                "output_frames_dir"):
        jumelle.pop(cle, None)
    manifest["lots"].insert(position, jumelle)
    projet = _ecrire_projet(tmp_path, manifest)

    rapport = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True, dry_run=dry_run)

    # Le lot vise est le PREMIER `rush-b_12` du listing -- celui que le
    # resolveur trouve --, et lui seul est nomme.
    vise = manifest["lots"][
        min(i for i, l in enumerate(manifest["lots"])
            if l["lot_id"] == "rush-b_12")]["frames_dir"]
    assert all(c.startswith(vise + "/") for c in rapport.fichiers_a_supprimer), (
        rapport.fichiers_a_supprimer)

    entrees = [l for l in _manifeste_relu(projet)["lots"]
               if l["lot_id"] == "rush-b_12"]
    assert len(entrees) == 2
    if dry_run:
        assert [l.get("frames_dir") for l in entrees].count(None) == 0, (
            "un apercu n'ecrit rien")
        return
    # L'entree visee est deliee, l'AUTRE garde son `frames_dir` -- et le
    # dossier qu'elle declare est toujours la.
    survivantes = [l.get("frames_dir") for l in entrees]
    assert survivantes.count(None) == 1, survivantes
    (restante,) = [c for c in survivantes if c]
    assert restante != vise
    assert (projet / restante).is_dir(), (
        "les frames de la seconde entree ne doivent pas devenir orphelines")


# ---------------------------------------------------------------------------
# `C2-5` : une PANNE devient une ligne, elle n'emporte plus le compte rendu.
# ---------------------------------------------------------------------------


def _cibles(*lots) -> list[tuple[str, dict]]:
    return [(f"frames de {lot}", {"lot_id": lot, "frames_extraites": True})
            for lot in lots]


class _CoeurQuiTombe:
    """Un double de `remove_project_element` qui LEVE sur les libelles nommes.

    Il enregistre l'ordre des appels : le cardinal des lignes rendues ne dit
    pas si la boucle a continue apres la panne -- un arret precoce peut rendre
    autant de lignes qu'il en a traitees.
    """

    def __init__(self, panne: dict[str, BaseException]):
        self.panne = panne
        self.appels: list[str] = []

    def __call__(self, project_dir, *, dry_run=True, **cible):
        lot = cible["lot_id"]
        self.appels.append(lot)
        if lot in self.panne:
            raise self.panne[lot]
        return RapportSuppression(
            cible=lot, fichiers_a_supprimer=(f"{RACINE}/{lot}/f.tiff",),
            dry_run=dry_run, supprime=not dry_run)


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("rang", [0, 1, 2])
def test_C2_5_un_OSError_devient_une_LIGNE_et_le_groupe_continue(
        tmp_path, rang, dry_run):
    """`EPIC11-ARB-264`, verbatim : « au mieux, ligne par ligne ».

    Regime mesure AVANT correctif : le coeur leve
    `OSError(28, "No space left on device")` sur la ligne *k* -- ce que
    `_ecrire_manifeste` releve bel et bien, volume plein ou montage passe en
    lecture seule --, l'exception traversait `remove_project_group`, et les
    lignes 1..*k*-1 DEJA DETRUITES disparaissaient de tout compte rendu. C'est
    le tout-ou-rien que l'arbitrage refuse, obtenu par accident.

    La panne est jouee en TETE, au MILIEU et en QUEUE : un balayage qui
    s'arreterait a la premiere panne reste vert sur « la derniere tombe ».
    """
    lots = ["rush-a_24", "rush-b_12", "rush-a_5"]
    coeur = _CoeurQuiTombe({lots[rang]: OSError(28, "No space left on device")})

    rapport = remove_project_group(
        tmp_path, _cibles(*lots), dry_run=dry_run, retirer=coeur)

    assert coeur.appels == lots, "les lignes suivantes doivent etre TENTEES"
    assert len(rapport.lignes) == 3
    (interrompue,) = rapport.interrompues
    assert interrompue.libelle == f"frames de {lots[rang]}"
    assert "OSError" in interrompue.refus
    assert "No space left on device" in interrompue.refus
    assert "peut-etre detruit" in interrompue.refus
    # Une interruption n'est pas une ligne partie, et elle EST comptee par
    # `refusees` -- le seul lecteur de cette liste s'en sert pour decider si le
    # groupe est parti en entier.
    assert interrompue.passee is False
    assert interrompue in rapport.refusees
    assert [l.libelle for l in rapport.passees] == [
        f"frames de {lot}" for lot in lots if lot != lots[rang]]


def test_C2_5_une_interruption_se_DISTINGUE_d_un_refus(tmp_path):
    """Frontiere de NATURE : `refusees` les compte, `interrompues` les separe.

    Un refus garantit que rien n'a ete detruit ; une interruption ne le promet
    pas -- un volume plein pendant la RESTAURATION du manifeste laisse des
    fichiers detruits ET un manifeste deja ecrit. Confondre les deux ferait
    annoncer « rien n'a bouge » sur un objet a moitie parti.
    """
    coeur = _CoeurQuiTombe({
        "rush-a_24": ProjectMaintenanceError("ce lot refuse, et il le dit"),
        "rush-a_5": OSError(30, "Read-only file system"),
    })
    rapport = remove_project_group(
        tmp_path, _cibles("rush-a_24", "rush-b_12", "rush-a_5"),
        dry_run=False, retirer=coeur)

    assert [l.libelle for l in rapport.refusees] == [
        "frames de rush-a_24", "frames de rush-a_5"]
    assert [l.libelle for l in rapport.interrompues] == ["frames de rush-a_5"]
    refus_prononce = rapport.refusees[0]
    assert refus_prononce.interrompue is False
    assert refus_prononce.refus == "ce lot refuse, et il le dit", (
        "le message du coeur voyage VERBATIM")


def test_C2_5_un_KeyboardInterrupt_ARRETE_le_groupe(tmp_path):
    """Frontiere NEGATIVE : `Exception`, jamais `BaseException`.

    Un Ctrl-C est une demande d'arret de l'operateur, pas une panne de ligne.
    L'avaler ferait continuer le groupe apres l'interruption, c'est-a-dire
    detruire exactement ce qu'on vient de demander d'epargner. Aucun test
    positif ne verrait apparaitre un `except BaseException` de confort.
    """
    coeur = _CoeurQuiTombe({"rush-b_12": KeyboardInterrupt()})
    with pytest.raises(KeyboardInterrupt):
        remove_project_group(
            tmp_path, _cibles("rush-a_24", "rush-b_12", "rush-a_5"),
            dry_run=False, retirer=coeur)
    assert coeur.appels == ["rush-a_24", "rush-b_12"], (
        "la ligne qui SUIT le Ctrl-C ne doit pas etre tentee")


def test_C2_5_la_panne_du_VRAI_coeur_traverse_le_meme_chemin(tmp_path,
                                                             monkeypatch):
    """Le double ne mesure pas que le VRAI coeur leve bien hors domaine.

    `_ecrire_manifeste` releve ses `OSError` -- c'est ecrit dans son corps, et
    c'est le regime de terrain d'un projet sur disque externe. Ce banc le joue
    sur le vrai `remove_project_element`, sans double, pour que la garde ne
    tienne pas seulement contre une fabrique complaisante.
    """
    from mixed_media_utility import project_maintenance

    projet = _projet(tmp_path)
    vrai = project_maintenance._ecrire_manifeste

    def _plein(manifest_path, manifest):
        if manifest_path.parent.name == "projet":
            raise OSError(28, "No space left on device")
        return vrai(manifest_path, manifest)

    monkeypatch.setattr(project_maintenance, "_ecrire_manifeste", _plein)
    rapport = remove_project_group(
        projet, _cibles("rush-a_24", "rush-b_12"), dry_run=False)

    assert len(rapport.lignes) == 2, "aucune exception ne traverse la boucle"
    assert len(rapport.interrompues) == 2
    assert all("No space left on device" in l.refus for l in rapport.lignes)


# ---------------------------------------------------------------------------
# `C3-6` : un refus MUET reste une ligne.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("rang", [0, 1, 2])
def test_C3_6_un_refus_SANS_MESSAGE_ne_fait_plus_avorter_le_groupe(
        tmp_path, rang, dry_run):
    """`refus: str = ""` prend la VACUITE pour discriminant.

    Regime mesure AVANT correctif : un `ProjectMaintenanceError("")` faisait
    lever `LigneDeGroupe.__post_init__` -- « Ligne de groupe incoherente » --
    HORS du `try`, et `remove_project_group` rendait ZERO ligne. Une exception
    de compte rendu detruisait le compte rendu.

    Aucun site du coeur ne leve aujourd'hui sans message : le risque est
    STRUCTUREL, pas actif. Il se ferme au seul endroit qui fabrique une ligne
    a partir d'une exception, plutot qu'en affaiblissant l'invariant de
    `LigneDeGroupe` -- qui est juste, et que le banc ci-dessous garde.
    """
    lots = ["rush-a_24", "rush-b_12", "rush-a_5"]
    coeur = _CoeurQuiTombe({lots[rang]: ProjectMaintenanceError("")})
    rapport = remove_project_group(
        tmp_path, _cibles(*lots), dry_run=dry_run, retirer=coeur)

    assert coeur.appels == lots
    assert len(rapport.lignes) == 3
    (muette,) = rapport.refusees
    assert muette.libelle == f"frames de {lots[rang]}"
    assert "sans message" in muette.refus
    assert "Rejouer la cible seule" in muette.refus
    assert muette.interrompue is False, (
        "un refus muet reste un REFUS : le coeur n'a rien detruit")


def test_C3_6_l_invariant_de_la_ligne_reste_INTACT():
    """Frontiere NEGATIVE : le correctif de `C3-6` n'affaiblit pas l'invariant.

    La sortie facile aurait ete d'admettre une ligne sans refus ni rapport dans
    `__post_init__`. Elle aurait rendu le banc vert et fait mentir toutes les
    lignes du produit. Aucun test positif ne verrait cet affaiblissement.
    """
    with pytest.raises(ProjectMaintenanceError) as erreur:
        LigneDeGroupe(cible={}, libelle="une cible", refus="")
    assert "SOIT un rapport, SOIT un refus" in str(erreur.value)


# ---------------------------------------------------------------------------
# `C2-2`, les deux bords de la garde : ce qu'elle voit encore, ce qu'elle
# refuse de transformer en refus.
# ---------------------------------------------------------------------------


def test_C2_2_une_planche_DEDUITE_d_un_autre_lot_est_protegee_aussi(tmp_path):
    """Le `manifest` passe a la garde n'est pas du confort : il PORTE une famille.

    Sur un manifeste anterieur a `sheets_pdfs`, la filiation des planches
    passe par le RECALCUL du nom, qui a besoin du `project_id` -- donc du
    manifeste. Sans lui, la garde couvre les masters et les scans des autres
    lots et rate leurs planches : une couverture reduite qu'aucun banc ne
    verrait, les masters suffisant a rendre verts les autres tests de `C2-2`.

    La cible est en QUEUE, l'objet a epargner appartient au lot de TETE.
    """
    manifest = _manifeste()
    for entree in manifest["lots"]:
        entree.pop("sheets_pdfs")
    manifest["lots"][-1]["frames_dir"] = PLANCHES
    projet = _ecrire_projet(tmp_path, manifest)
    avant = _tout_le_disque(projet)

    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="rush-a_5", dry_run=False)

    message = str(erreur.value)
    assert "la planche du lot" in message
    assert "rush-a_24" in message, (
        "le lot NOMME doit etre celui qu'on epargne, pas la cible")
    assert _tout_le_disque(projet) == avant


@pytest.mark.parametrize("dry_run", [True, False])
def test_C2_2_un_slug_de_scan_CORROMPU_ailleurs_ne_bloque_pas_la_cible(
        tmp_path, dry_run):
    """Frontiere NEGATIVE : la garde neuve n'invente pas de refus.

    `_slug_valide` LEVE sur un `ingest_slug` qui n'est pas un segment -- un
    `../frames/<autre lot>` reste sous le projet et ferait supprimer les
    frames d'un tiers, c'est l'incident du 2026-08-27. Mais cette corruption
    appartient a un AUTRE lot : la faire remonter ici transformerait la
    suppression demandee en refus sur un probleme qui ne la concerne pas, et
    l'operateur n'aurait aucune issue -- un blocage sec, ce qu'`EPIC11-ARB-89`
    interdit. La cible est au MILIEU, la corruption en QUEUE.
    """
    manifest = _manifeste()
    manifest["lots"][-1]["reconstructions"] = [{"ingest_slug": "../evasion"}]
    projet = _ecrire_projet(tmp_path, manifest)

    rapport = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True, dry_run=dry_run)
    assert rapport.fichiers_a_supprimer == tuple(
        f"{RACINE}/rush-b_12/rush-b_12_{n:04d}.tiff" for n in range(3))
    # Et la corruption reste VISIBLE la ou elle mord : sur son propre lot.
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="rush-a_5", dry_run=True)
    assert "Slug d'ingestion invalide" in str(erreur.value)


# ---------------------------------------------------------------------------
# `C2-2`, la moitie que le mutant `M05` a demasquee : les objets du lot VISE.
# ---------------------------------------------------------------------------


#: `(famille, chemin PRIVE de l'objet, `frames_dir` qui l'engloutit, mot du refus)`
#: Chaque chemin est PROPRE au lot vise : aucun autre lot n'en declare sous cet
#: ancetre, faute de quoi c'est la garde des AUTRES lots qui rendrait le test
#: vert -- ce qui est exactement ce que `M05` a survecu.
FAMILLES_DU_LOT_VISE = [
    ("master", "sorties-{lot}/{lot}.mov", "sorties-{lot}", "le master"),
    ("planche", "tirages-{lot}/{lot}.pdf", "tirages-{lot}", "la planche"),
    ("scan", None, f"{SCANS}/scan-{{lot}}", "le dossier de scan"),
    ("frames scannees", None, f"{SCANNEES}/{{lot}}", "le dossier"),
]


@pytest.mark.parametrize("cible", ["rush-a_24", "rush-b_12", "rush-a_5"])
@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("famille,prive,ancetre,mot", FAMILLES_DU_LOT_VISE)
def test_C2_2_le_lot_VISE_ne_s_emporte_pas_lui_meme(
        tmp_path, famille, prive, ancetre, mot, dry_run, cible):
    """Mutant `M05`, SURVIVANT au premier tour : ce banc le tue.

    `M05` remplacait la copie du lot vise -- lui-meme, prive de son seul
    `frames_dir` -- par la redaction d'avant, qui ne reprenait que
    `output_frames_dir`. Les masters, planches et scans DU LOT VISE
    retombaient donc sans garde, et c'est le cas le plus probable : le
    `frames_dir` d'un lot est bien plus vraisemblablement place au-dessus de
    SES propres sorties qu'au-dessus de celles d'un tiers.

    Les autres tests de `C2-2` restaient verts parce que la fabrique range les
    trois lots sous les MEMES ancetres (`outputs/`, `planches/`, `scans/`) :
    c'est alors la garde des AUTRES lots qui prononce le refus, et le mutant
    passe. Ici l'objet est range dans un dossier PROPRE au lot vise, et
    l'assertion porte sur l'identifiant que le refus NOMME -- sans quoi le
    banc reste incapable de dire laquelle des deux gardes a parle.
    """
    manifest = _manifeste()
    vise = next(l for l in manifest["lots"] if l["lot_id"] == cible)
    if famille == "master":
        vise["encoded_masters"] = [{"path": prive.format(lot=cible),
                                    "profile": "prores_422"}]
    elif famille == "planche":
        vise["sheets_pdfs"] = [{"path": prive.format(lot=cible)}]
    vise["frames_dir"] = ancetre.format(lot=cible)
    projet = _ecrire_projet(tmp_path, manifest)
    avant = _tout_le_disque(projet)

    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id=cible, frames_extraites=True, dry_run=dry_run)

    message = str(erreur.value)
    assert mot in message, message
    assert f"du lot {cible!r}" in message, (
        "c'est bien le lot VISE que le refus doit nommer, pas un tiers")
    for autre in ("rush-a_24", "rush-b_12", "rush-a_5"):
        if autre != cible:
            assert f"du lot {autre!r}" not in message
    assert _tout_le_disque(projet) == avant
