# -*- coding: utf-8 -*-
"""Deux conditions limites de l'ecran « Profil de calibration par defaut ».

**Bancs de la couche 2 (edge case hunter) de la revue du lot `99783416d`.**
Ils sont ecrits ici plutot que dans `test_palier_profil_defaut.py` pour que le
diff de revue reste isolable ; les fabriques, elles, sont **importees** de ce
banc-la, jamais recopiees -- une seconde fabrique divergerait au premier
ajustement, et c'est le defaut que ce depot paie le plus souvent.

Les deux defauts qu'ils demasquent ont ete **mesures** avant d'etre ecrits, et
chacun est mordant : retablir le code fautif les fait rougir.

1. **La ligne d'etat garde un REFUS apres une designation REUSSIE.**
   `_valider_l_explorateur` pose `_etat_a_dire` sur un refus et ne l'efface
   jamais quand la designation suivante passe. `traiter` ne l'efface que dans
   la zone LISTE, et la validation d'explorateur ne passe pas par la. Regime
   exact : un `.json` illisible, puis un `.json` valide **du meme dossier**.
   L'ecran retient bien le bon fichier -- et annonce `✕ ... n'est pas un JSON
   valide` en dessous. `EPIC11-ARB-56` veut une **mesure** sur cette ligne ;
   une mesure perimee n'en est pas une, et le glyphe `✕` dit litteralement
   l'inverse de ce qui vient de se passer.

2. **La colonne des noms est calee en CARACTERES, pas en COLONNES.**
   `ligne_d_entree` fait `f"{nom:<{LARGEUR_DU_NOM}}"`. Un ideogramme occupe
   **deux** colonnes : un nom de 16 ideogrammes vaut 32 colonnes (donc
   `abreger_nom` le laisse intact, il tient dans 33) mais 16 caracteres, si
   bien que le calage ajoute 17 espaces au lieu de 1. La mention part 13
   colonnes trop a droite, la ligne deborde des 76 colonnes utiles, et
   `jetons.ajuster` **ampute la mention** -- c'est-a-dire la seule chose qui
   dise ce que la ligne est.

   Ce n'est pas un defaut neuf pour le depot : `jetons.colonnes` porte le cas
   dans son propre docstring (« un nom de projet en japonais rendait un
   bandeau de 82 colonnes dans une zone de 76 »), et **quatre** modules ont
   deja pose le remede -- `atelier_exports_lot._a_gauche`, son jumeau
   d'`atelier_pdf_lots`, `cadences` et `projet_inventaire` : « un ideogramme
   occupe deux colonnes : `str.ljust` calerait un champ de dix caracteres sur
   vingt colonnes, et toutes les colonnes de droite partiraient avec ».
   `palier_profil_defaut` est le cinquieme site, et il cale en `len()`.

   Le banc existant `test_la_COLONNE_des_mentions_est_la_MEME_dans_les_deux_modes`
   ne le voit pas : il fait varier `ascii_seul`, jamais la **chasse** du nom.
   C'est la regle des drapeaux appliquee a un drapeau que personne n'avait
   recense -- la largeur d'un caractere.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

from mixed_media_utility.tui import jetons, palier_profil_defaut as ppd
from mixed_media_utility.tui.execution import EcranRefus

from test_palier_profil_defaut import (RANG_DU_MILIEU, _app, _ecran,
                                       _fichier_de_profil, _monte, _projet)

#: Un nom en double chasse qui **tient** dans la colonne des noms : seize
#: ideogrammes valent 32 colonnes, sous les 33 de `LARGEUR_DU_NOM`, donc
#: `abreger_nom` le rend intact. C'est le regime ou le defaut mord -- un nom
#: qui deborderait serait abrege, et l'abregement, lui, compte en colonnes.
NOM_EN_DOUBLE_CHASSE = "日" * 16


def test_la_ligne_d_etat_n_annonce_PLUS_le_refus_quand_le_fichier_SUIVANT_passe(
        tmp_path, banc):
    """Un refus efface se remplace ; un refus perime **ment**.

    Le geste de l'operateur est ordinaire : il se trompe de fichier, l'ecran
    le refuse en le nommant, il en designe un autre au rang d'a cote. L'ecran
    accepte le second -- la ligne apparait dans la liste et le curseur s'y
    pose -- et continue d'afficher le refus du premier sous le glyphe
    `absent`.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU)
    valide = _fichier_de_profil(tmp_path, chain_id="chaine-designee")
    illisible = valide.parent / "pas-un-profil.json"
    illisible.write_text("{ ceci n'est pas du json", encoding="utf-8")
    ecran, _ = _ecran(projet)

    def _viser(nom: str) -> None:
        for rang, entree in enumerate(ecran.explorateur.entrees):
            if entree.chemin.name == nom:
                ecran.explorateur.curseur = rang
                return
        raise AssertionError(f"{nom} absent de l'explorateur")

    async def scenario(_pilote):
        # La porte « autre fichier… » est la derniere entree de la liste.
        ecran.choix.curseur = len(ecran.choix.entrees) - 1
        ecran.traiter("enter")
        ecran.explorateur.dossier = valide.parent
        ecran.explorateur.relire()

        _viser(illisible.name)
        ecran.traiter("enter")
        refuse = ecran.etat()

        _viser(valide.name)
        ecran.traiter("enter")
        return refuse, ecran.etat(), ecran.zone, ecran.choix.fichier

    refuse, apres, zone, retenu = _monte(_app(ecran), scenario, banc)
    print("REFUSE=", repr(refuse), "\nAPRES=", repr(apres))

    # Volet 1 -- le refus a bien ete dit. Sans lui, le volet 2 passerait sur un
    # ecran qui ne refuse rien du tout.
    assert jetons.GLYPHES["absent"] in refuse, refuse
    assert str(illisible) in refuse, refuse

    # Volet 2 -- la designation suivante a REUSSI...
    assert retenu == valide, retenu
    assert zone == ppd.ZONE_LISTE
    assert ppd.CLE_FICHIER_DESIGNE in [e.cle for e in ecran.choix.entrees]

    # ... et la ligne d'etat ne doit plus porter le refus.
    assert str(illisible) not in apres, (
        "la ligne d'etat garde le refus du fichier precedent apres une "
        f"designation reussie : {apres!r}")
    assert jetons.GLYPHES["absent"] not in apres, apres


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_colonne_des_mentions_TIENT_sur_un_nom_en_DOUBLE_CHASSE(
        tmp_path, banc, ascii_seul):
    """Le calage se mesure en COLONNES, jamais en caracteres.

    Le drapeau qu'on fait varier ici n'est pas `ascii_seul` -- il est joue dans
    les deux sens par-dessus le marche -- mais **la chasse du nom** : un nom
    latin et un nom ideographique de la meme largeur en colonnes doivent
    ouvrir leur mention a la meme colonne. Sans cette variation, le banc
    existant mesure la moitie du produit et l'annonce verte.
    """
    projet = _projet(tmp_path, profils=(), nom="projet_chasse")
    ecran, _ = _ecran(projet)
    utile = jetons.largeur_utile(80)

    async def scenario(_pilote):
        # Une seule ligne de fichier designe : c'est la porte qui donne la
        # colonne de reference, et elle porte un nom latin.
        ecran.choix.poser_le_fichier(
            Path("/valise") / f"{NOM_EN_DOUBLE_CHASSE}.json")
        rendues = {}
        for rang, entree in enumerate(ecran.choix.entrees):
            ligne = ecran.ligne_d_entree(rang, utile)
            mention = (jetons.replier_ascii(entree.mention) if ascii_seul
                       else entree.mention)
            rendues[entree.cle] = (ligne, ligne.find(mention))
        return rendues

    rendues = _monte(_app(ecran, ascii_seul=ascii_seul), scenario, banc)

    ouvertures = set()
    for cle, (ligne, position) in rendues.items():
        assert position >= 0, (
            f"la mention de {cle} a ete AMPUTEE de la ligne : {ligne!r}")
        assert jetons.colonnes(ligne) <= utile, (cle, ligne)
        ouvertures.add(jetons.colonnes(ligne[:position]))

    assert len(ouvertures) == 1, (
        "la colonne des mentions glisse sur un nom en double chasse : "
        f"{ouvertures} -- {rendues}")


# ===========================================================================
# LES DEUX BORDS DE LA LISTE -- trois mutants survivants les demandaient
# ===========================================================================

def test_le_curseur_de_la_liste_est_BORNE_aux_DEUX_bouts(tmp_path, banc):
    """`ChoixDuProfil.deplacer` borne, et **rien ne le mesurait**.

    Trois mutants ont survecu au lot du 2026-09-07, tous sur cette seule
    ligne :

    * la borne **haute** retiree (`max(..., 0)` seul) : `↓` au dernier rang
      pose le curseur a `len(entrees)`, et `courante` leve `IndexError` au
      redessin suivant -- c'est-a-dire que le produit **tombe** sur une touche
      de navigation ordinaire ;
    * la borne **basse** retiree (`min(..., len - 1)` seul) : `↑` en tete pose
      le curseur a `-1`. Aucune exception, ce qui est pire : `courante` rend
      alors la **derniere** entree -- la porte « autre fichier… » --, et
      `rang_du_curseur` rend `None`, donc plus aucune ligne n'est peinte. `⏎`
      ouvre l'explorateur depuis un ecran qui ne montre plus ou l'on est ;
    * la valeur de retour figee a vrai : la touche est consommee alors que
      rien n'a bouge.

    C'est le quatrieme point de la regle des fabriques applique au **curseur**
    plutot qu'a la collection : la cible au milieu ne demasque jamais une
    borne. Les deux bords se frappent, et on frappe **au-dela** de chacun.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU)
    ecran, prises = _ecran(projet)

    async def scenario(_pilote):
        total = len(ecran.choix.entrees)
        # Au-dela de la QUEUE : trois frappes de trop.
        for _ in range(total + 3):
            ecran.traiter("down")
        queue = (ecran.choix.curseur, ecran.choix.deplacer(1),
                 ecran.choix.courante.cle, ecran.rang_du_curseur())
        # Au-dela de la TETE : trois frappes de trop.
        for _ in range(total + 3):
            ecran.traiter("up")
        tete = (ecran.choix.curseur, ecran.choix.deplacer(-1),
                ecran.choix.courante.cle, ecran.rang_du_curseur())
        return total, queue, tete

    total, queue, tete = _monte(_app(ecran), scenario, banc)

    curseur_queue, bouge_queue, cle_queue, rang_queue = queue
    assert curseur_queue == total - 1, curseur_queue
    assert bouge_queue is False, "deplacer pretend avoir bouge en queue"
    assert cle_queue == ppd.CLE_AUTRE_FICHIER, cle_queue
    assert rang_queue is not None, "le curseur n'est plus peint en queue"

    curseur_tete, bouge_tete, cle_tete, rang_tete = tete
    assert curseur_tete == 0, curseur_tete
    assert bouge_tete is False, "deplacer pretend avoir bouge en tete"
    assert cle_tete == f"{ppd.PREFIXE_DE_PROFIL}0", cle_tete
    assert rang_tete is not None, "le curseur n'est plus peint en tete"

    # Et rien n'a ete confirme par ces vingt frappes de navigation.
    assert prises == []


# ===========================================================================
# LE DEFILEMENT -- aucun banc du lot ne fait DEBORDER la liste
# ===========================================================================

#: Assez de profils pour que la liste deborde `HAUTEUR_DE_LA_LISTE` largement,
#: **et distinguables un a un** : vingt chaines, vingt sources, vingt cardinaux
#: de patchs, vingt dates. Une fabrique uniforme rendrait invisible toute
#: permutation entre une ligne rendue et le rang qu'elle croit porter, et c'est
#: exactement ce que le defilement peut casser.
BEAUCOUP_DE_PROFILS = tuple(
    {"chain_id": f"chaine-{rang:02d}", "patchs": 11 + rang,
     "source": f"profil-{rang:02d}.json",
     "date": f"2026-08-{rang + 1:02d}T10:00:00Z"}
    for rang in range(20))


def test_la_liste_qui_DEBORDE_tient_le_plancher_et_dit_ou_elle_est_coupee(
        tmp_path, banc):
    """`HAUTEUR_DE_LA_LISTE` est une constante centrale que RIEN ne mesurait.

    Les bancs du lot montent trois profils plus la porte : **quatre** entrees,
    donc la liste ne deborde jamais, donc le fenetrage n'est jamais joue et la
    hauteur n'est jamais atteinte. Mesure du 2026-09-07 : la porter de 8 a 12
    fait rendre **19 lignes** dans une zone centrale qui en tient 17 au
    plancher -- le pied et son filet partent par le bas, sans un mot -- et
    aucun des 53 tests du lot ne rougit.

    C'est le meme genre de trou que la regle des fabriques ferme sur les
    collections : une fabrique trop petite ne peut pas atteindre la borne
    qu'elle est censee mesurer.

    Trois proprietes se mesurent ici, aux **deux** bords du defilement :

    * la zone centrale ne deborde jamais `jetons.hauteur_centrale(24)` ;
    * le `…` dit de quel cote la liste est coupee -- en queue quand on est en
      tete, en tete quand on est en queue, et il n'y en a **pas** du cote ou
      il n'y a rien a cacher ;
    * `rang_du_curseur` designe la ligne qui porte reellement le curseur,
      `…` de tete compris -- un rang decale peindrait la couleur du curseur
      sur une AUTRE entree que celle que `⏎` retiendrait.
    """
    projet = _projet(tmp_path, profils=BEAUCOUP_DE_PROFILS,
                     rang_du_defaut=len(BEAUCOUP_DE_PROFILS) - 1,
                     nom="projet_qui_deborde")
    ecran, _ = _ecran(projet)
    utile = jetons.largeur_utile(80)
    curseur = jetons.GLYPHES["curseur"]

    async def scenario(_pilote):
        total = len(ecran.choix.entrees)
        assert total > ppd.HAUTEUR_DE_LA_LISTE, total
        tete = (list(ecran.lignes()), ecran.rang_du_curseur())
        for _ in range(total + 3):
            ecran.traiter("down")
        queue = (list(ecran.lignes()), ecran.rang_du_curseur())
        return total, tete, queue

    total, tete, queue = _monte(_app(ecran), scenario, banc)
    points = jetons.points_d_abregement(False)

    for nom, (lignes, rang) in (("tete", tete), ("queue", queue)):
        assert len(lignes) <= jetons.hauteur_centrale(24), (
            f"{nom} : {len(lignes)} lignes dans une zone qui en tient "
            f"{jetons.hauteur_centrale(24)} au plancher")
        for ligne in lignes:
            assert jetons.colonnes(ligne) <= utile, (nom, ligne)
        assert rang is not None, f"{nom} : le curseur n'est plus peint"
        assert curseur in lignes[rang], (nom, rang, lignes[rang])
        # Le pied survit au defilement : c'est lui qui part le premier quand la
        # liste prend trop de place.
        assert ppd.TITRE_DU_PIED in "".join(lignes), nom

    lignes_de_tete = tete[0]
    lignes_de_queue = queue[0]
    coupes_en_tete = [l for l in lignes_de_tete if l.strip() == points]
    coupes_en_queue = [l for l in lignes_de_queue if l.strip() == points]
    # En tete de liste, la coupure est en BAS et il n'y en a qu'une.
    assert len(coupes_en_tete) == 1, lignes_de_tete
    assert lignes_de_tete.index(coupes_en_tete[0]) > tete[1], (
        "le « … » de la liste non deroulee devrait etre SOUS le curseur")
    # En queue, elle est en HAUT.
    assert len(coupes_en_queue) == 1, lignes_de_queue
    assert lignes_de_queue.index(coupes_en_queue[0]) < queue[1], (
        "le « … » de la liste deroulee devrait etre AU-DESSUS du curseur")


# ===========================================================================
# LE COUT de l'issue qui ecrit -- il varie avec le drapeau, et rien ne le dit
# ===========================================================================

@pytest.mark.parametrize("remplace,mention,autre", [
    (False, ppd.MENTION_POSE, ppd.MENTION_REMPLACE),
    (True, ppd.MENTION_REMPLACE, ppd.MENTION_POSE),
])
def test_la_MENTION_de_l_issue_qui_ecrit_dit_ce_que_CE_geste_la_coute(
        remplace, mention, autre):
    """`EPIC11-ARB-89` : l'ecriture est possible, elle est **avertie**.

    Le banc du lot mesure que le **libelle** change avec le drapeau ; il ne
    mesure pas la **mention**, qui est pourtant la moitie qui dit ce que le
    geste coute. Mesure du 2026-09-07 : echanger les deux mentions --
    « Remplacer le profil par défaut — les scans le prendront sans le
    répéter » d'un cote, « Poser ce profil par défaut — l'ancien fichier reste
    sur le disque » de l'autre -- ne fait rougir aucun des 53 tests du lot.

    Or c'est exactement l'inverse de l'avertissement : la seule issue qui
    remplace quelque chose serait la seule a ne pas dire qu'il y a un ancien
    fichier, et celle qui ne remplace rien parlerait d'un ancien qui n'existe
    pas. Le libelle nomme l'ACTE, la mention nomme le COUT ; les deux doivent
    varier ensemble.
    """
    action = next(i for i in ppd.issues_de_la_pose(remplace).issues if i.ecrit)

    assert mention in action.libelle, action.libelle
    assert autre not in action.libelle, action.libelle


# ===========================================================================
# LE RETOUR sur l'ecran -- ce que `relire` promet de garder
# ===========================================================================

def test_le_fichier_DESIGNE_survit_au_retour_sur_l_ecran(tmp_path, banc):
    """`relire` promet de garder le fichier designe, et **rien ne le mesurait**.

    Le regime est celui de l'operateur qui se ravise : il designe un `.json`
    dans l'explorateur, il valide, il lit le point de jugement, il **annule**.
    L'annulation depile, l'ecran de choix reprend la main -- donc `reprendre`
    appelle `relire` -- et la ligne du fichier designe doit encore etre la,
    sans quoi il faut refaire toute la navigation pour retenter.

    Mesure du 2026-09-07 : retirer les trois lignes qui reposent le fichier
    designe apres la relecture ne fait rougir aucun des 53 tests du lot.
    `test_le_RETOUR_sur_l_ecran_relit_le_registre` monte bien `reprendre`,
    mais sur un ecran ou **aucun** fichier n'a jamais ete designe : il mesure
    la moitie de la methode.

    Volet symetrique dans le meme test : ce que `relire` doit au contraire
    **relire** -- un profil pose entre-temps entre dans la liste.
    """
    from mixed_media_utility.tui.palier_projet import poser_le_profil_par_defaut

    projet = _projet(tmp_path, profils=(), nom="projet_qui_revient")
    designe = _fichier_de_profil(tmp_path, chain_id="chaine-designee")
    pose_entre_temps = _fichier_de_profil(tmp_path, chain_id="chaine-posee")
    ecran, _ = _ecran(projet)

    async def scenario(_pilote):
        ecran.choix.poser_le_fichier(designe)
        avant = [e.cle for e in ecran.choix.entrees]
        # Un profil est pose par ailleurs pendant que cet ecran est en dessous.
        poser_le_profil_par_defaut(projet, pose_entre_temps)
        ecran.reprendre()
        return avant, [e.cle for e in ecran.choix.entrees], ecran.choix

    avant, apres, choix = _monte(_app(ecran), scenario, banc)

    assert avant == [ppd.CLE_FICHIER_DESIGNE, ppd.CLE_AUTRE_FICHIER], avant
    # Le fichier designe SURVIT...
    assert ppd.CLE_FICHIER_DESIGNE in apres, (
        f"le fichier designe a disparu au retour sur l'ecran : {apres}")
    assert choix.fichier == designe, choix.fichier
    assert choix.courante.cle == ppd.CLE_FICHIER_DESIGNE, choix.courante.cle
    # ... et le registre a bien ete RELU : le profil pose entre-temps est la.
    assert f"{ppd.PREFIXE_DE_PROFIL}0" in apres, apres
    assert apres == [f"{ppd.PREFIXE_DE_PROFIL}0", ppd.CLE_FICHIER_DESIGNE,
                     ppd.CLE_AUTRE_FICHIER], apres


# ===========================================================================
# CE QUI EST RENDU -- le modele etait mesure, le DESSIN ne l'etait pas
# ===========================================================================

def test_la_liste_qui_TIENT_rend_TOUTES_ses_entrees_dans_l_ORDRE(tmp_path,
                                                                 banc):
    """Aucun banc du lot ne confronte le DESSIN de la liste a son modele.

    Les bancs existants mesurent `entrees_du_profil` (le modele) ou
    `ligne_d_entree` (une ligne prise au rang qu'on lui donne) ; aucun ne
    mesure `lignes_de_la_liste`, c'est-a-dire **ce qui est reellement peint**.

    Mesure du 2026-09-07 : decaler d'un rang la borne haute de la fenetre --
    `range(premier, dernier)` au lieu de `range(premier, dernier + 1)` -- fait
    disparaitre la **derniere** entree de la liste. Sur un projet a trois
    profils, la ligne perdue est « autre fichier… », c'est-a-dire la porte
    dont l'existence est la reponse d'Egan a l'« ecran vide » -- et les 53
    tests du lot restent verts.

    C'est le quatrieme point de la regle des fabriques -- « au moins un test
    place une cible a CHAQUE BORD » -- applique au **rendu** et non au modele :
    la cible en queue est ici la porte elle-meme, et rien ne la voyait
    manquer. Il en va de meme d'un `…` rendu sur une liste qui tient : il
    annoncerait une coupure qui n'existe pas.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU)
    ecran, _ = _ecran(projet)
    utile = jetons.largeur_utile(80)

    async def scenario(_pilote):
        assert len(ecran.choix.entrees) <= ppd.HAUTEUR_DE_LA_LISTE, (
            "cette mesure porte sur une liste qui TIENT ; au-dela, c'est le "
            "banc de defilement qui s'applique")
        return list(ecran.lignes_de_la_liste(utile)), \
            [e.nom for e in ecran.choix.entrees]

    rendues, noms = _monte(_app(ecran), scenario, banc)

    assert noms[-1] == ppd.LIBELLE_AUTRE_FICHIER, noms
    assert len(rendues) == len(noms), (
        f"{len(rendues)} lignes rendues pour {len(noms)} entrees : {rendues}")
    # Chaque entree est rendue, a son rang, **la tete et la queue comprises**.
    for rang, nom in enumerate(noms):
        abrege = jetons.abreger_nom(nom, ppd.LARGEUR_DU_NOM, False)
        assert abrege in rendues[rang], (rang, nom, rendues[rang])
    # Et aucune coupure n'est annoncee sur une liste qui tient entiere.
    points = jetons.points_d_abregement(False)
    assert not any(l.strip() == points for l in rendues), rendues


# ===========================================================================
# LE SECOND CANAL -- le GLYPHE porte l'etat, et rien ne le mesurait
# ===========================================================================

def test_le_pied_porte_le_GLYPHE_de_l_etat_qu_il_annonce(tmp_path, banc):
    """`DESIGN.md` §6 : aucune information n'est portee par la couleur seule.

    Le pied dit trois etats ; le banc du lot mesure leur **texte** et jamais
    leur **glyphe**. Mesure du 2026-09-07 : echanger `complete` et
    `substitute` -- donc annoncer `●` sur un defaut dont le fichier a disparu
    et `▲` sur un defaut present -- ne fait rougir aucun des 53 tests.

    Or c'est le glyphe qui EST l'information : c'est le second canal, celui
    qui reste quand la couleur tombe, et `jetons.marque` existe precisement
    pour que « deux etats distincts rendent deux chaines distinctes meme sans
    couleur ».
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU)

    ecran_present, _ = _ecran(projet)
    present = _monte(_app(ecran_present),
                     lambda _p: _rendre(ecran_present.lignes_du_pied()), banc)

    # Le fichier du defaut disparait sous les pieds.
    ppd.entrees_du_profil(projet)[RANG_DU_MILIEU].chemin.unlink()
    ecran_perdu, _ = _ecran(projet)
    perdu = _monte(_app(ecran_perdu),
                   lambda _p: _rendre(ecran_perdu.lignes_du_pied()), banc)

    assert jetons.GLYPHES["complete"] in "".join(present), present
    assert jetons.GLYPHES["substitute"] not in "".join(present), present
    assert jetons.GLYPHES["substitute"] in "".join(perdu), perdu
    assert jetons.GLYPHES["complete"] not in "".join(perdu), perdu


def test_la_ligne_d_etat_du_SUCCES_porte_le_glyphe_du_SUCCES():
    """Un compte rendu de reussite sous le glyphe du REFUS dit l'inverse.

    Mesure du 2026-09-07 : remplacer `complete` par `absent` dans
    `ligne_d_etat_de_la_pose` -- donc annoncer « ✕ profil par défaut posé » --
    ne fait rougir aucun des 53 tests du lot. Les deux modes sont joues :
    `●`/`▲`/`✕` se replient en `*`/`!`/`x`, et le repli reste injectif, donc
    le canal tient aussi en `--ascii`.
    """
    from mixed_media_utility.tui.palier_projet import ProfilPose

    pose = ProfilPose(chaine="chaine-de-banc", forme="affine-par-canal-v2",
                      chemin=Path("versions/calibration/chaine-de-banc.json"))

    for ascii_seul in (False, True):
        table = jetons.glyphes(ascii_seul)
        ligne = ppd.ligne_d_etat_de_la_pose(pose, ascii_seul)
        assert ligne.startswith(table["complete"]), (ascii_seul, ligne)
        for autre in ("absent", "substitute"):
            assert table[autre] not in ligne, (ascii_seul, autre, ligne)


async def _rendre(valeur):
    """Rendre une valeur deja calculee depuis un scenario de banc."""
    return valeur


# ===========================================================================
# LE CABLAGE DE L'AVERTISSEMENT -- `EPIC11-ARB-89` mesure sur le PARCOURS
# ===========================================================================

def test_le_PARCOURS_nomme_le_defaut_qu_il_va_remplacer(tmp_path, banc):
    """L'avertissement se cable, et le cablage n'etait pas mesure.

    `test_le_cartouche_NOMME_le_defaut_remplace_et_SEULEMENT_alors` appelle
    `panneau_de_la_pose` **directement**, avec la chaine qu'il choisit :
    il mesure la fonction, jamais qui la remplit. Mesure du 2026-09-07 :
    remplacer `defaut_actuel=nom_du_profil(entree)` par `defaut_actuel=""`
    dans `_CablageDeLaPose.confirmer` -- donc ne JAMAIS nommer le profil que
    la pose ecrasera, et libeller l'issue « Poser » la ou elle remplace -- ne
    fait rougir aucun des 53 tests du lot.

    C'est `EPIC11-ARB-89` a la lettre : « toujours permettre une reecriture
    plutot qu'un blocage sec [...] apres avertissement ». Sans le cablage, il
    n'y a plus d'avertissement, et l'ecriture destructive cesse d'etre
    consciente.

    Le drapeau varie dans les DEUX sens : le meme parcours, sur un projet
    **sans** defaut, ne doit rien annoncer du tout.
    """
    avec = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU, nom="projet_avec")
    sans = _projet(tmp_path, profils=(), nom="projet_sans")
    source = _fichier_de_profil(tmp_path)

    def _jugement(dossier):
        montes = []
        cablage = ppd._CablageDeLaPose(_ApplicationTemoin(montes), dossier)
        cablage.confirmer(source)
        assert len(montes) == 1 and isinstance(montes[0], ppd.EcranPoseDuProfil), montes
        ecran = montes[0]
        action = next(i for i in ecran.choix.issues if i.ecrit)
        return ecran.defaut_actuel, "\n".join(ecran.panneau.rendu(80)), \
            action.libelle

    nomme, cartouche, libelle = _jugement(avec)
    assert nomme == "profil-beta.json", nomme
    assert ppd.LIBELLE_DEFAUT_ACTUEL in cartouche, cartouche
    assert "profil-beta.json" in cartouche, cartouche
    assert libelle.startswith(ppd.LIBELLE_REMPLACER), libelle

    muet, cartouche_sans, libelle_sans = _jugement(sans)
    assert muet == "", muet
    assert ppd.LIBELLE_DEFAUT_ACTUEL not in cartouche_sans, cartouche_sans
    assert libelle_sans.startswith(ppd.LIBELLE_POSER), libelle_sans


def test_un_profil_qui_DISPARAIT_entre_l_apercu_et_l_ecriture_rend_un_REFUS(
        tmp_path):
    """Le second temps a son propre chemin d'erreur, et il n'etait pas joue.

    `confirmer` (temps 1) et `poser` (temps 2) attrapent chacun **deux**
    familles de refus ; le banc du lot ne joue que `CibleSansProjet`, et
    seulement sur le temps 1. Mesure du 2026-09-07 : retirer
    `ProfileDesignationError` du `except` de `poser` ne fait rougir aucun des
    53 tests -- l'exception traverse alors la TUI et peint une trace de pile
    par-dessus l'interface.

    Le regime est reel et le module le nomme lui-meme : le profil est valide a
    l'apercu, puis il **change sous nos pieds** avant l'ecriture. C'est la
    famille du bloquant `C2` de la revue de 5.22 -- un chemin de trace qui
    fait perdre un travail deja fait.
    """
    projet = _projet(tmp_path, profils=(), nom="projet_qui_perd_sa_source")
    source = _fichier_de_profil(tmp_path)
    montes = []
    cablage = ppd._CablageDeLaPose(_ApplicationTemoin(montes), projet)

    cablage.confirmer(source)
    assert isinstance(montes[0], ppd.EcranPoseDuProfil), montes

    # La source disparait ENTRE l'apercu et l'ecriture.
    source.unlink()
    cablage.poser(source)

    assert len(montes) == 2, montes
    refus = montes[1]
    assert isinstance(refus, EcranRefus), type(refus).__name__
    assert refus.code == "PROFILE_DESIGNATION_ERROR", refus.code
    assert str(source) in refus.message, refus.message


def test_le_COMPTE_RENDU_monte_par_le_parcours_est_bien_celui_du_SUCCES(
        tmp_path):
    """Le parcours mesure le TYPE de l'ecran de succes, jamais son cartouche.

    `test_le_parcours_COMPLET_apercu_puis_pose_puis_compte_rendu` s'arrete a
    `isinstance(ecran, EcranProfilPose)` ; `test_l_ecran_de_SUCCES_...`
    construit le cartouche lui-meme. Entre les deux, **personne** ne verifie
    que le parcours passe le bon panneau. Mesure du 2026-09-07 : remplacer
    `panneau_du_profil_pose(pose)` par `panneau_de_la_pose(pose)` dans
    `_CablageDeLaPose.poser` ne fait rougir aucun des 53 tests -- l'ecran de
    succes reprend alors le titre « A ecrire » et perd sa ligne
    « Emplacement ».

    Or `TITRE_ECRIT` existe precisement pour ca : « un compte rendu qui
    garderait "A ecrire" ferait croire qu'il reste quelque chose a faire ».
    Et c'est le grief d'Egan lui-meme -- « pas d'ecran de succes [...]
    incoherent avec le reste ».
    """
    projet = _projet(tmp_path, profils=(), nom="projet_du_compte_rendu")
    source = _fichier_de_profil(tmp_path)
    montes = []
    cablage = ppd._CablageDeLaPose(_ApplicationTemoin(montes), projet)
    cablage.poser(source)

    assert len(montes) == 1, montes
    succes = montes[0]
    assert isinstance(succes, ppd.EcranProfilPose), type(succes).__name__
    assert succes.panneau.titre == ppd.TITRE_ECRIT, succes.panneau.titre
    libelles = [l.libelle for l in succes.panneau.lignes]
    assert ppd.LIBELLE_EMPLACEMENT in libelles, libelles
    # L'emplacement est le DOSSIER, jamais le fichier : le nom est deja au
    # cartouche, et le repeter ne situe rien de plus.
    emplacement = next(l.valeur for l in succes.panneau.lignes
                       if l.libelle == ppd.LIBELLE_EMPLACEMENT)
    assert not emplacement.endswith(".json"), emplacement
    # Et la ligne d'etat du succes est POSEE, apres le montage.
    assert ppd.ETAT_POSE in succes._etat_courant, succes._etat_courant


class _ApplicationTemoin:
    """Ce que `_CablageDeLaPose` attend d'une application : `descendre`.

    Un double **minimal et explicite** plutot qu'une application montee : ce
    qui se mesure ici est ce que le cablage EMPILE, pas ce que `textual` en
    dessine -- et les deux ecrans concernes ont deja leur banc de rendu.
    """

    ascii_seul = False

    def __init__(self, montes):
        self.montes = montes

    def descendre(self, ecran):
        self.montes.append(ecran)


# ===========================================================================
# LA LIGNE D'ETAT nomme le DEFAUT -- la moitie que la fabrique n'atteint pas
# ===========================================================================

@pytest.mark.parametrize("rang", (0, 1, 2))
def test_la_ligne_d_etat_NOMME_le_defaut_courant_a_chaque_rang(tmp_path, banc,
                                                               rang):
    """La ligne d'etat porte DEUX faits ; un seul etait mesure.

    `test_la_ligne_d_etat_est_une_MESURE_et_compte_les_trois_formes` monte ses
    trois projets **sans jamais poser de defaut** : `ETAT_SANS_DEFAUT` est donc
    la bonne reponse dans les trois cas, et la seconde moitie de la ligne n'est
    jamais confrontee a autre chose qu'elle-meme.

    Mesure du 2026-09-07, dans les deux sens : figer la seconde moitie a
    `ETAT_SANS_DEFAUT` -- ou, symetriquement, la figer a `ETAT_DEFAUT` --
    ne fait rougir aucun des 53 tests du lot.

    La cible passe par les **trois rangs**, tete et queue comprises : un
    aiguillage qui rendrait toujours le premier profil du registre resterait
    vert sur la cible du milieu.
    """
    projet = _projet(tmp_path, rang_du_defaut=rang, nom=f"projet_r{rang}")
    attendu = ("profil-alpha.json", "profil-beta.json",
               "profil-gamma.json")[rang]
    ecran, _ = _ecran(projet)
    etat = _monte(_app(ecran), lambda _p: _rendre(ecran.etat()), banc)

    assert ppd.ETAT_DEFAUT.format(nom=attendu) in etat, etat
    assert ppd.ETAT_SANS_DEFAUT not in etat, etat

    # Volet symetrique : sans defaut pose, la ligne le dit et ne nomme rien.
    neuf = _projet(tmp_path, nom=f"projet_neuf_r{rang}")
    ecran_neuf, _ = _ecran(neuf)
    sans = _monte(_app(ecran_neuf), lambda _p: _rendre(ecran_neuf.etat()),
                  banc)
    assert ppd.ETAT_SANS_DEFAUT in sans, sans
    assert "profil-" not in sans.split(ppd.SEPARATEUR_D_ETAT)[-1], sans


def test_les_TROIS_ecrans_du_parcours_NOMMENT_leur_objet_au_bandeau(tmp_path,
                                                                    banc):
    """Sans `objet`, les trois ecrans portent le bandeau du palier dont ils
    descendent -- donc trois ecrans indistinguables au bandeau.

    Mesure du 2026-09-07 : vider `OBJET_DU_BANDEAU` ne fait rougir aucun des
    53 tests du lot, alors que c'est la seule chose qui distingue ces trois
    ecrans du palier Projet au premier coup d'oeil. Les deux modes sont joues :
    le bandeau est la surface exacte ou le repli tardif a coute 11 ecrans sur
    14 le 2026-09-06.
    """
    from mixed_media_utility.tui.palier_projet import ProfilPose

    projet = _projet(tmp_path, profils=(), nom="projet_du_bandeau")
    pose = ProfilPose(chaine="chaine-de-banc", forme="affine-par-canal-v2",
                      chemin=Path("versions/calibration/chaine-de-banc.json"))
    fabriques = (
        lambda: _ecran(projet)[0],
        lambda: ppd.EcranPoseDuProfil(pose, Path("/valise/p.json"),
                                      poser=lambda _s: None),
        lambda: ppd.EcranProfilPose(ppd.panneau_du_profil_pose(pose),
                                    objet=ppd.OBJET_DU_BANDEAU),
    )

    from mixed_media_utility.tui.palier_projet import EcranPalierProjet

    for ascii_seul in (False, True):
        # **La reference est le bandeau du PALIER dont les trois descendent**,
        # jamais la constante : un test qui chercherait `OBJET_DU_BANDEAU` dans
        # le bandeau passerait sur la constante VIDE -- `"" in texte` est
        # toujours vrai --, c'est-a-dire exactement sur le mutant qu'il vise.
        palier = EcranPalierProjet(Path("/projet"), entrer=lambda _i: None)
        sans_objet = _monte(_app(palier, ascii_seul=ascii_seul),
                            lambda _p: _rendre(palier.bandeau(80)), banc)
        for fabrique in fabriques:
            ecran = fabrique()
            bandeau = _monte(_app(ecran, ascii_seul=ascii_seul),
                             lambda _p, e=ecran: _rendre(e.bandeau(80)), banc)
            assert bandeau != sans_objet, (
                f"{type(ecran).__name__} porte le meme bandeau que son palier "
                f"en ascii_seul={ascii_seul} : {bandeau!r}")
            assert jetons.colonnes(bandeau) <= jetons.largeur_utile(80), bandeau



# ===========================================================================
# `EPIC5-ARB-83` -- l'identite n'est PAS une cle de resolution
# ===========================================================================

def test_le_defaut_se_reconnait_au_CHEMIN_et_jamais_au_CHAIN_ID(tmp_path):
    """La propriete que le module cite trois fois, et que rien ne mesurait.

    `entrees_du_profil` marque le profil par defaut en comparant le **chemin
    ecrit a l'entree** (`ENTRY_PATH_KEY`), jamais le `chain_id`. Le docstring
    le dit et le motive : recomposer par l'identite marche « tant que les deux
    coincident », donc l'ecart ne se voit jamais en fabrique -- et c'est
    litteralement le cas, mesure du 2026-09-07 : comparer les `chain_id` au
    lieu des chemins ne fait rougir aucun des 53 tests du lot, parce que le
    registre reel associe un chemin a une chaine et un seul.

    Le regime qui les DISSOCIE est celui d'`EPIC5-ARB-83` : deux entrees de la
    **meme chaine** sous deux chemins, ce que le disque produit des qu'une
    chaine est recalibree et que l'ancien fichier reste. Le defaut est celui
    que le manifest DESIGNE, pas celui qui porte la bonne chaine -- et il est
    joue **au milieu**, jamais en tete.

    La fonction est pure : elle se mesure sans monter d'ecran, et ses deux
    points d'injection (`profils`, `defaut`) sont ici leur premier appelant.
    """
    chemins = ("versions/calibration/a.json", "versions/calibration/b.json",
               "versions/calibration/c.json")
    # Les fichiers EXISTENT : sans eux, `designated_profile_path` rend `None`
    # et la mention « son fichier a disparu » -- qui passe avant tout le reste
    # -- masquerait la mention du defaut, donc la moitie de ce qu'on mesure.
    for relatif in chemins:
        cible = tmp_path / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text("{}", encoding="utf-8")
    #: Trois entrees DISTINGUABLES par leur chemin, dont **deux partagent la
    #: chaine** : c'est ce qui dissocie identite et resolution.
    registre = [
        {"chain_id": "chaine-recalibree", "path": chemins[0],
         "designated_from": "vieux.json"},
        {"chain_id": "chaine-recalibree", "path": chemins[1],
         "designated_from": "neuf.json"},
        {"chain_id": "chaine-autre", "path": chemins[2],
         "designated_from": "autre.json"},
    ]
    # Le manifest designe le SECOND -- au milieu de la liste, et il partage sa
    # chaine avec le premier.
    defaut = dict(registre[1])

    entrees = ppd.entrees_du_profil(tmp_path, profils=registre, defaut=defaut)

    marques = [e.par_defaut for e in entrees]
    assert marques == [False, True, False, False], (
        "le defaut est reconnu par le chain_id : la premiere entree de la "
        f"meme chaine est marquee aussi -- {marques}")
    assert entrees[1].mention == ppd.MENTION_PAR_DEFAUT, entrees[1].mention
    # Volet symetrique : l'entree jumelle n'herite de rien.
    assert entrees[0].mention != ppd.MENTION_PAR_DEFAUT, entrees[0].mention


# ===========================================================================
# `K3` A L'ENVERS -- un point d'injection que le premier `reprendre()` jetait
# ===========================================================================


def test_l_INJECTION_du_registre_SURVIT_au_retour_sur_l_ecran(tmp_path, banc):
    """Troisieme condition limite : `relire()` jetait `profils=` et `defaut=`.

    Les deux mots-cles sont documentes « points d'injection du banc » depuis
    l'ecriture du module. Le constructeur les honorait ; :meth:`relire` -- que
    `reprendre()` appelle a chaque retour sur l'ecran -- rappelait
    `entrees_du_profil(self.dossier)` **sans eux**. Un banc qui injectait puis
    montait mesurait donc le DISQUE en croyant mesurer son injection, et il le
    faisait en silence : l'ecran se recomposait simplement sans elle.

    C'est le motif `K3` a l'envers -- non pas un rappel jamais cable, mais un
    point d'injection sans injecteur --, et la garde `test_rappels_cables.py`
    ne peut pas le voir : elle ne balaye que les `Callable | None`.

    **Le drapeau VARIE dans les deux sens.** L'injection est confrontee au
    disque, qui porte un registre DIFFERENT : mesurer la seule injection
    laisserait vert un `relire` qui rendrait toujours l'injection, et mesurer
    le seul disque laisserait vert celui d'avant.
    """
    injectes = ({"chain_id": "zeta-injecte",
                 "path": "versions/calibration/zeta-injecte.json"},
                {"chain_id": "omega-injecte",
                 "path": "versions/calibration/omega-injecte.json"})
    # Le disque porte AUTRE CHOSE : c'est ce qui rend la mesure discriminante.
    projet = _projet(tmp_path)
    ecran, _prises = _ecran(projet, profils=injectes)

    def _noms(ecr):
        return [entree.nom for entree in ecr.choix.profils]

    async def scenario(_pilote):
        avant = _noms(ecran)
        ecran.reprendre()
        return avant, _noms(ecran)

    avant, apres = _monte(_app(ecran), scenario, banc)
    assert apres == avant, (
        "l'injection doit survivre au retour sur l'ecran ; sinon un banc qui "
        f"injecte mesure le disque : avant={avant} apres={apres}")
    assert any("zeta-injecte" in nom for nom in apres), apres
    # Le volet symetrique : sans injection, c'est bien le disque qu'on lit, et
    # il ne porte rien de ce que l'injection nomme.
    du_disque, _ = _ecran(projet)
    assert _noms(du_disque) != avant
    assert not any("injecte" in nom for nom in _noms(du_disque))


def test_le_CABLAGE_de_la_pose_ne_porte_plus_de_champ_MORT():
    """Finding `F3` -- `_CablageDeLaPose.ecran` etait ecrit, jamais lu.

    Le champ portait un docstring qui lui pretait un role (« il sert a rendre
    la main dessus ») et une ligne l'ecrivait a l'ouverture. Aucun lecteur
    nulle part. Une surface morte a laquelle un commentaire prete une
    intention est pire qu'une surface absente : le prochain lecteur la croit
    portante et batit dessus.

    Frontiere negative : elle ne peut pas etre verte par accident, puisqu'elle
    nomme le champ retire.
    """
    import dataclasses

    champs = {champ.name
              for champ in dataclasses.fields(ppd._CablageDeLaPose)}
    assert "ecran" not in champs, champs
    # Anti-vacuite : la classe porte bien ses quatre champs vivants, donc la
    # mesure porte sur une dataclasse qui existe encore.
    assert {"application", "dossier", "apercevoir", "poser_au_coeur"} <= champs
