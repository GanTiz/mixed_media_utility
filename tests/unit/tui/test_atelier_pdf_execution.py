# -*- coding: utf-8 -*-
"""`E5-4` et `T6-1` -- la generation des planches (story 11.7, lot I, AC 9).

Ce banc mesure trois choses qu'aucune relecture ne voit :

* **le rotor est pose la ou l'ecran attend sans savoir compter**, et il y est
  pose par un critere -- `PasseDeGeneration.total_connu` --, pas par un cas
  particulier. Le volet symetrique est mesure : des que le total est connu, la
  barre reprend sa place et le rotor disparait. Une frontiere qui ne mesurerait
  que le premier regime serait verte sur un ecran qui aurait perdu sa barre ;
* **l'agregation porte sur la PASSE**, pas sur le lot courant. La fabrique
  porte **trois** lots, de cardinaux **distinguables** (21, 7, 5), et le lot
  courant est **au milieu** : ni en premiere position -- ou une somme fautive
  qui ne prendrait que le premier serait indiscernable --, ni en derniere -- ou
  une somme sur toute la liste le serait ;
* **le journal est COMPOSE par la TUI**, parce que le coeur n'emet rien pendant
  le rendu. La mesure de production est refaite ici, en frontiere : les trois
  modules du chemin de rendu ne portent aucun appel de journalisation.

Regle des fabriques, appliquee sur la liste que le CODE parcourt
-----------------------------------------------------------------

`pages_ecrites`, `mention_du_lot`, `etats_des_lots` et `lignes_des_lots`
bouclent tous sur `passe.lots`. C'est cette liste qui porte trois elements
distinguables et la cible au milieu -- et non une liste de fabrique que le code
trierait ou filtrerait avant de la parcourir.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from mixed_media_utility import qr_codes
from mixed_media_utility.tui import atelier_pdf_execution as generation
from mixed_media_utility.tui import atelier_pdf_resultat as resultat
from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.avancement import Journal
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.execution import EcranInterruption, SurfaceExecution

RACINE = pathlib.Path(__file__).resolve().parents[3]
MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")
SOURCE_DU_MODULE = pathlib.Path(generation.__file__)
SOURCE_DU_COEUR = SOURCE_DU_MODULE.parents[1]

#: Les trois lots de la fabrique. **Trois**, distinguables par leur nom, leur
#: cardinal de pages et leur rang de tirage ; la cible est le **second**,
#: c'est-a-dire ni le premier ni le dernier (`CLAUDE.md`, points 2 et 2 bis).
LOT_ECRIT = generation.LotEnGeneration(
    "projet_demo_plan-01_25_6f-pay_v4.pdf", 21, "tpl-a4-paysage-6f-v2", 4,
    "plan-01_25")
LOT_COURANT = generation.LotEnGeneration(
    "projet_demo_plan-02_8_6f-pay.pdf", 7, "tpl-a4-portrait-4f-v2", 1,
    "plan-02_8")
LOT_EN_ATTENTE = generation.LotEnGeneration(
    "projet_demo_plan-03_12p5_6f-pay_v2.pdf", 5, "tpl-a4-paysage-6f-v2", 2,
    "plan-03_12p5")

#: Le cardinal de pages de la passe entiere : 21 + 7 + 5. Il est **calcule
#: ici**, a partir des trois lots, et non recopie -- une constante recopiee
#: survivrait a un changement de fabrique.
PAGES_DE_LA_PASSE = sum(
    lot.pages for lot in (LOT_ECRIT, LOT_COURANT, LOT_EN_ATTENTE))


def passe(pages_du_lot_courant: int = 3, rang: int = 1,
          troisieme=LOT_EN_ATTENTE) -> generation.PasseDeGeneration:
    """La passe de la fabrique. Le lot courant est **au milieu** par defaut."""
    return generation.PasseDeGeneration(
        (LOT_ECRIT, LOT_COURANT, troisieme),
        rang_du_lot_courant=rang,
        pages_du_lot_courant=pages_du_lot_courant)


# ---------------------------------------------------------------------------
# AC 9.1 -- l'agregation porte sur la PASSE
# ---------------------------------------------------------------------------


def test_les_pages_ecrites_agregent_les_lots_PRECEDENTS_et_le_lot_courant():
    """21 pages du lot 1, plus 3 du lot 2 en cours : 24, jamais 3.

    C'est la propriete qu'`EPIC11-ARB-134` point 2 demande, et la seule que le
    lot courant au milieu de trois rend mesurable : une somme qui ne prendrait
    que le premier lot rendrait 21, une somme de toute la liste 36, et une
    remise a zero par lot 3.
    """
    assert passe().pages_ecrites == 24


def test_le_total_de_la_passe_est_la_somme_des_TROIS_lots():
    assert passe().pages_de_la_passe == PAGES_DE_LA_PASSE == 33


def test_le_pourcentage_est_celui_de_la_PASSE_et_non_du_lot_courant():
    """24/33 rend 73 %, pas 42 % (3/7 du lot courant).

    Les deux nombres sont distincts **par construction de la fabrique** : c'est
    l'inegalite des cardinaux de lots qui les separe.
    """
    ligne = passe().ligne_d_etat(pas=0)
    assert " 73 % " in ligne
    assert "42 %" not in ligne


def test_un_lot_de_la_passe_qui_n_est_pas_compose_rend_le_total_INCONNU():
    """Le cardinal d'un lot vient de `compose_lot_plan`, appele lot par lot."""
    inconnu = passe(troisieme=generation.LotEnGeneration(
        "projet_demo_plan-03_12p5_6f-pay_v2.pdf", None, "", 2, "plan-03"))
    assert not inconnu.total_connu
    assert inconnu.pages_de_la_passe == 0


def test_le_total_est_connu_quand_les_TROIS_lots_le_sont():
    """Volet symetrique : la frontiere ci-dessus mesure encore quelque chose."""
    assert passe().total_connu


# ---------------------------------------------------------------------------
# AC 9.1 -- LE GLYPHE DE CHARGEMENT, et son volet symetrique
# ---------------------------------------------------------------------------


def test_le_rotor_remplace_la_barre_quand_le_total_de_la_passe_est_INCONNU():
    """Le retour d'Egan, mesure : « il faudrait un glyphe de chargement ».

    La barre a `0/0` occupe 36 colonnes pour ne rien dire ; le rotor dit la
    seule chose vraie a cet instant.
    """
    inconnu = passe(troisieme=generation.LotEnGeneration("x.pdf", None))
    ligne = inconnu.ligne_d_etat(pas=0)
    assert ligne.startswith(jetons.ROTOR[0])
    assert jetons.GLYPHES["barre-vide"] not in ligne
    assert jetons.GLYPHES["barre-pleine"] not in ligne


def test_le_rotor_TOURNE_quand_le_total_est_inconnu():
    """Quatre pas, quatre dessins **distincts** : un rotor qui rendrait deux
    fois le meme signe aurait perdu toute son information."""
    inconnu = passe(troisieme=generation.LotEnGeneration("x.pdf", None))
    dessins = [inconnu.ligne_d_etat(pas=pas)[0] for pas in range(4)]
    assert len(set(dessins)) == 4
    assert tuple(dessins) == jetons.ROTOR


def test_le_rotor_tourne_AUSSI_en_repli_ascii():
    """`--ascii` doit garder le mouvement : quatre dessins distincts aussi."""
    inconnu = passe(troisieme=generation.LotEnGeneration("x.pdf", None))
    dessins = [inconnu.ligne_d_etat(pas=pas, ascii_seul=True)[0]
               for pas in range(4)]
    assert tuple(dessins) == jetons.ROTOR_ASCII


def test_la_BARRE_reprend_sa_place_des_que_le_total_est_connu():
    """**Le volet symetrique du rotor.** Sans lui, un ecran qui aurait perdu sa
    barre pour toujours resterait vert : `DESIGN.md` section 9 interdit une
    animation « a la place d'un compte reel », et il y a ici un compte reel."""
    ligne = passe().ligne_d_etat(pas=0)
    assert jetons.GLYPHES["barre-pleine"] in ligne
    for dessin in jetons.ROTOR:
        assert dessin not in ligne


def test_le_rotor_ne_fige_AUCUNE_duree():
    """`reste ~ 8 s` est une forme de la maquette, pas une promesse.

    Sans mesure de l'estimateur, la ligne ne porte aucun temps -- ni dans le
    regime du rotor, ni dans celui de la barre (`EPIC7-ARB-67`).
    """
    inconnu = passe(troisieme=generation.LotEnGeneration("x.pdf", None))
    assert "reste" not in inconnu.ligne_d_etat(pas=0)
    assert "reste" not in passe().ligne_d_etat(pas=0)


def test_le_temps_restant_est_rendu_quand_l_estimateur_en_DONNE_un():
    """Volet symetrique : le champ n'est pas mort, il attend une mesure."""
    mesuree = passe()
    mesuree.temps_restant = 8.0
    assert "reste ~ 8 s" in mesuree.ligne_d_etat(pas=0)
    inconnue = passe(troisieme=generation.LotEnGeneration("x.pdf", None))
    inconnue.temps_restant = 8.0
    assert "reste ~ 8 s" in inconnue.ligne_d_etat(pas=0)


def test_aucun_nombre_de_secondes_n_est_ecrit_dans_le_module():
    """Frontiere negative : personne n'a chronometre une generation.

    Le `8` de la maquette ne doit exister nulle part dans le produit -- et
    c'est bien un litteral qu'on cherche, pas une mention en commentaire.
    """
    import re
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    # **Les docstrings sont retirees**, et c'est ce qui rend la frontiere
    # utile plutot que penible : la prose a le droit de CITER la maquette
    # (« `reste ~ 8 s` est une forme, pas une promesse »), le code n'a pas le
    # droit d'ecrire la duree.
    docstrings = {id(ast.get_docstring(noeud, clean=False))
                  for noeud in ast.walk(arbre)
                  if isinstance(noeud, (ast.Module, ast.ClassDef,
                                        ast.FunctionDef))
                  and ast.get_docstring(noeud, clean=False) is not None}
    prose = {ast.get_docstring(noeud, clean=False)
             for noeud in ast.walk(arbre)
             if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef))
             and ast.get_docstring(noeud, clean=False) is not None}
    # Une duree ECRITE, dans n'importe quelle unite de la grammaire du
    # `DESIGN.md` section 8 : `~ 8 s`, `~ 1 min 10`, `~ 1 h 30`.
    motif = re.compile(r"~\s*\d+\s*(?:s|min|h)\b")
    coupables = [noeud.value for noeud in ast.walk(arbre)
                 if isinstance(noeud, ast.Constant)
                 and isinstance(noeud.value, str)
                 and noeud.value not in prose
                 and motif.search(noeud.value)]
    assert coupables == [], coupables
    # Volet symetrique : le motif sait trouver une duree quand il y en a une.
    assert motif.search("reste ~ 8 s")


# ---------------------------------------------------------------------------
# AC 9.2 -- le corps : titre, liste des lots, etats
# ---------------------------------------------------------------------------


def test_le_titre_porte_le_RANG_du_lot_courant():
    assert passe().titre() == "Génération en cours — lot 2 sur 3"


def test_les_TROIS_etats_de_lot_sont_rendus_dans_les_trois_positions():
    """Ecrit, en cours, en attente -- l'ensemble EXACT, dans l'ordre.

    La comparaison de rang porte des **deux** cotes : un `>=` fautif rendrait
    « en attente » pour le lot deja ecrit.
    """
    modele = passe()
    assert [modele.mention_du_lot(rang) for rang in range(3)] == [
        generation.MENTION_ECRIT, generation.MENTION_EN_COURS,
        generation.MENTION_EN_ATTENTE]


def test_seul_le_lot_ECRIT_porte_un_glyphe_d_etat():
    assert passe().etats_des_lots() == {0: generation.ETAT_DU_LOT_ECRIT}


def test_la_ligne_d_un_lot_porte_son_nom_son_compte_et_sa_mention():
    ligne = passe().ligne_du_lot(0, 76)
    assert jetons.GLYPHES["complete"] in ligne
    assert LOT_ECRIT.nom in ligne
    assert "21 pages" in ligne
    assert ligne.rstrip().endswith(generation.MENTION_ECRIT)


def test_la_ligne_du_lot_TIENT_la_largeur_dans_les_deux_regimes():
    """Un nom long ne deborde pas : il est abrege, jamais coupe par la fin."""
    long = generation.LotEnGeneration(
        "projet_demo_sequence-12-atelier-fondement_12p5_6f-pay_v3.pdf", 13,
        "tpl", 3, "seq-12")
    modele = generation.PasseDeGeneration((long, LOT_COURANT, LOT_EN_ATTENTE))
    for ascii_seul in (False, True):
        for utile in (76, 60):
            ligne = modele.ligne_du_lot(0, utile, ascii_seul)
            assert jetons.colonnes(ligne) <= utile, (ascii_seul, utile, ligne)


def test_la_colonne_des_mentions_ne_BOUGE_pas_quand_un_lot_change_d_etat():
    """Calee sur le jeu complet des trois mentions, jamais sur l'affiche.

    Sans quoi la colonne sauterait au moment precis ou un lot passe de « en
    cours » a « ecrit », c'est-a-dire pendant qu'on la regarde.
    """
    premiere = passe(rang=0).ligne_du_lot(0, 76)
    seconde = passe(rang=2).ligne_du_lot(0, 76)
    assert (premiere.index(generation.MENTION_EN_COURS)
            == seconde.index(generation.MENTION_ECRIT))


# ---------------------------------------------------------------------------
# AC 9.3 -- le journal, et ce que le coeur emet REELLEMENT
# ---------------------------------------------------------------------------


def test_le_chemin_de_RENDU_du_coeur_n_emet_AUCUNE_ligne_de_journal():
    """La mesure qui fonde la forme du journal de `E5-4`.

    Refaite en frontiere plutot que racontee : les trois modules du chemin de
    rendu ne portent **aucun** appel de journalisation. Le jour ou l'un en
    porterait un, cette frontiere rougirait et le journal de `E5-4` pourrait
    cesser d'etre compose ici.
    """
    for nom in ("pdf_render.py", "pdf_composition.py", "page_templates.py"):
        source = (SOURCE_DU_COEUR / nom).read_text(encoding="utf-8")
        arbre = ast.parse(source)
        appels = [noeud for noeud in ast.walk(arbre)
                  if isinstance(noeud, ast.Attribute)
                  and noeud.attr in ("info", "warning", "error", "debug")
                  and isinstance(noeud.value, ast.Name)
                  and "log" in noeud.value.id.lower()]
        assert appels == [], f"{nom} journalise desormais : {appels}"


def test_le_module_COMPOSE_le_journal_et_ne_pretend_pas_le_relayer():
    """Volet symetrique : la frontiere ci-dessus a bien un objet.

    Si le module cessait de composer ses lignes, la mesure du coeur ci-dessus
    resterait verte pour la mauvaise raison.
    """
    assert "{gabarit}" in generation.EN_TETE_DE_LOT
    assert "{version}" in generation.LIGNE_DE_PAGE


def test_l_en_tete_de_lot_NOMME_le_lot_son_gabarit_et_son_rang():
    assert (generation.en_tete_de_lot(LOT_COURANT)
            == "plan-02_8 : tpl-a4-portrait-4f-v2, tirage 1")


def test_la_version_du_QR_est_LUE_du_produit_et_jamais_recomposee():
    """`qr_codes.symbol_version` est la seule redaction de `4V + 17`.

    Le cote de 85 modules rend la version 17 -- valeur du produit, calculee par
    lui : la recopier ici en ferait une seconde verite.
    """
    class _Qr:
        module_side = 85

    class _Page:
        qr = _Qr()
        frames = (1, 2, 3, 4, 5, 6)

    assert generation.version_du_qr(_Page()) == qr_codes.symbol_version(85)


def test_la_ligne_de_page_lit_le_cardinal_d_emplacements_PAGE_PAR_PAGE():
    """La derniere page d'un lot mal rempli n'a pas le cardinal des autres.

    Recopier `frames_per_page` du lot ferait mentir la derniere ligne du
    journal de chaque lot -- exactement une page sur sept ici.
    """
    class _Qr:
        module_side = 81

    def page(emplacements):
        return type("P", (), {"qr": _Qr(), "frames": tuple(range(emplacements))})()

    pleine = generation.ligne_de_page(page(6), 6, 7)
    derniere = generation.ligne_de_page(page(2), 7, 7)
    assert "6 emplacements" in pleine
    assert "2 emplacements" in derniere


def test_l_horodatage_est_DONNE_jamais_lu_au_fond_de_la_fonction():
    from datetime import datetime
    assert (generation.horodater(datetime(2026, 9, 2, 16, 22, 41), "page 1/7")
            == "16:22:41  page 1/7")


def test_le_journal_n_est_PAS_remis_a_zero_entre_deux_lots():
    """`EPIC11-ARB-93` : les lignes du lot precedent restent visibles.

    Ce que la composition rend porte donc l'en-tete du lot 2 **et** des lignes
    du lot 1 -- la rupture se lit parce qu'elle est nommee, pas parce qu'elle
    est effacee.
    """
    journal = Journal()
    journal.inscrire(generation.en_tete_de_lot(LOT_ECRIT))
    journal.inscrire("page 21/21 : 6 emplacements, QR version 16")
    journal.inscrire(generation.en_tete_de_lot(LOT_COURANT))
    journal.inscrire("page 1/7 : 6 emplacements, QR version 16")
    lignes, _, _ = generation.corps_de_la_generation(
        passe(), journal, 80, 17)
    texte = "\n".join(lignes)
    assert "plan-01_25" in texte and "plan-02_8" in texte


# ---------------------------------------------------------------------------
# AC 9.2 / 9.3 -- la composition tient la zone centrale
# ---------------------------------------------------------------------------


def test_le_corps_TIENT_la_hauteur_de_la_zone_centrale():
    journal = Journal()
    for rang in range(1, 40):
        journal.inscrire(f"page {rang}/40 : 6 emplacements, QR version 16")
    for hauteur in (17, 12, 30):
        lignes, _, _ = generation.corps_de_la_generation(
            passe(), journal, 80, hauteur)
        assert len(lignes) <= hauteur, hauteur


def test_le_corps_TIENT_la_largeur_dans_les_deux_regimes():
    journal = Journal()
    journal.inscrire("page 3/7 : 6 emplacements, QR version 16")
    for ascii_seul in (False, True):
        lignes, _, _ = generation.corps_de_la_generation(
            passe(), journal, 80, 17, ascii_seul)
        for ligne in lignes:
            assert jetons.colonnes(ligne) <= 76, (ascii_seul, ligne)


def test_le_journal_DEPLIE_prend_la_place_de_la_liste_des_lots():
    """`Tab journal` tient sa promesse : il y a plus a lire apres.

    Sans cette substitution la touche serait annoncee et n'ajouterait qu'une
    ligne ou deux -- ce que la story 11.5 a paye quarante fois sous le nom
    « touche annoncee mais inerte ».
    """
    journal = Journal()
    for rang in range(1, 40):
        journal.inscrire(f"page {rang}/40")
    replie = generation.lignes_de_journal_visibles(17, 3, False)
    deplie = generation.lignes_de_journal_visibles(17, 3, True)
    assert deplie > replie
    lignes, _, _ = generation.corps_de_la_generation(
        passe(), journal, 80, 17, journal_deplie=True)
    assert LOT_ECRIT.nom not in "\n".join(lignes)


# ---------------------------------------------------------------------------
# AC 9.5 a 9.9 -- `T6-1`
# ---------------------------------------------------------------------------


def test_T6_1_est_obtenu_par_SOUS_CLASSEMENT_d_EcranInterruption():
    assert issubclass(generation.EcranInterruptionDeLaGeneration,
                      EcranInterruption)


def test_les_cles_des_issues_sont_EXACTEMENT_celles_du_patron():
    """Ensemble exact, ordre compris, et le drapeau `ecrit` avec (AC 9.9)."""
    chiffrees = generation.issues_chiffrees(passe())
    assert ([(issue.cle, issue.ecrit) for issue in chiffrees]
            == [(issue.cle, issue.ecrit) for issue in EcranInterruption.ISSUES])


def test_chaque_issue_qui_parle_de_ce_qui_est_ecrit_porte_son_CHIFFRE_reel():
    """AC 9.6 : `Interrompre et garder les 24 pages`, pas « ce qui est ecrit ».

    Le chiffre est celui de la **passe** -- 24 --, pas celui du lot courant.
    """
    chiffrees = generation.issues_chiffrees(passe())
    libelles = [issue.libelle for issue in chiffrees]
    assert "Interrompre et garder les 24 pages" in libelles
    assert "Interrompre et effacer les 24 pages" in libelles


def test_l_issue_qui_ne_parle_pas_d_ecriture_traverse_SANS_CHANGER():
    """« Reprendre l'execution » n'a pas de chiffre a porter.

    Volet symetrique de la substitution : elle ne doit pas mordre partout.
    """
    reprendre = [issue for issue in generation.issues_chiffrees(passe())
                 if issue.cle == EcranInterruption.REPRENDRE][0]
    origine = [issue for issue in EcranInterruption.ISSUES
               if issue.cle == EcranInterruption.REPRENDRE][0]
    assert reprendre.libelle == origine.libelle


def test_la_tournure_substituee_existe_bien_dans_les_libelles_du_patron():
    """**Le volet symetrique de la substitution.**

    Le jour ou le patron reformulerait ses libelles, la substitution
    deviendrait muette et deux issues resteraient « ce qui est deja ecrit »
    sans que rien ne rougisse. C'est ce test-la qui rougit.
    """
    porteuses = [issue for issue in EcranInterruption.ISSUES
                 if generation.TOURNURE_SANS_CHIFFRE in issue.libelle]
    assert len(porteuses) == 2


def test_le_chiffre_des_issues_EVOLUE_avec_la_passe():
    """AC 9.7 : le chiffre vieillit pendant qu'on lit la question.

    Mesure de l'**entrelacement** : deux etats de passe, deux libelles, et le
    second est bien celui du second etat -- pas seulement « ils different ».
    """
    modele = passe(pages_du_lot_courant=3)
    avant = generation.issues_chiffrees(modele)[0].libelle
    modele.pages_du_lot_courant = 5
    apres = generation.issues_chiffrees(modele)[0].libelle
    assert avant == "Interrompre et garder les 24 pages"
    assert apres == "Interrompre et garder les 26 pages"


def test_le_curseur_de_T6_1_est_REPORTE_quand_le_chiffre_se_rafraichit():
    """AC 9.7, la moitie qu'on oublie : le rafraichissement tombe **pendant**
    qu'on lit la question.

    Un curseur remis a zero a chaque jalon ferait sauter la fleche sous les
    yeux de l'operateur -- et sur `T6-1`, sauter veut dire passer d'une issue
    qui n'ecrit pas a une issue qui efface. C'est pire que de ne pas
    rafraichir du tout.
    """
    modele = passe()
    ecran = generation.EcranInterruptionDeLaGeneration(modele)
    # Le dessin est neutralise : ce test mesure l'etat du choix, pas la peinture.
    ecran._assez_grand_au_dernier_dessin = False
    depart = ecran.choix.curseur
    ecran.choix.deplacer(1)
    vise = ecran.choix.issues[ecran.choix.curseur].cle
    assert ecran.choix.curseur != depart

    modele.pages_du_lot_courant = 5
    ecran.rafraichir_les_chiffres()

    assert ecran.choix.issues[ecran.choix.curseur].cle == vise
    # ... et le chiffre a bien change, sans quoi le report serait vert pour la
    # mauvaise raison.
    assert "les 26 pages" in ecran.choix.issues[0].libelle
    assert ecran.panneau.lignes[0].valeur == 26


def test_le_panneau_de_la_passe_compte_les_pages_ECRITES_et_RESTANTES():
    panneau = generation.panneau_de_la_passe(passe())
    assert [(ligne.libelle, ligne.valeur) for ligne in panneau.lignes] == [
        (generation.LIBELLE_PAGES_ECRITES, 24),
        (generation.LIBELLE_PAGES_RESTANTES, 9)]
    assert not panneau.porte_un_majorant


def test_les_pages_restantes_disent_leur_ABSENCE_quand_le_total_est_inconnu():
    """Un `0` s'y lirait « fini », ce qui est l'inverse de la verite."""
    panneau = generation.panneau_de_la_passe(
        passe(troisieme=generation.LotEnGeneration("x.pdf", None)))
    assert (panneau.lignes[1].valeur == generation.RESTANTES_INCONNUES)


def test_la_ligne_d_etat_de_T6_1_est_une_MESURE_pas_un_motif_de_conception():
    """`EPIC11-ARB-56` : aucune touche, aucun conseil, aucun mecanisme.

    Le patron rend « L'execution continue tant qu'aucune issue n'est validee »,
    qui explique un mecanisme ; ce qui la remplace se compte.
    """
    ligne = generation.ligne_d_etat_de_l_interruption(passe())
    assert "lot 2/3" in ligne and "page 3/7" in ligne
    for interdit in ("Échap", "Entrée", "validée", "tant qu'"):
        assert interdit not in ligne


# ---------------------------------------------------------------------------
# AC 9.8 -- la granularite offerte est DITE, pas devinee
# ---------------------------------------------------------------------------
#
# **Ce que ce bloc mesurait, et ce qu'il pretendait mesurer** (finding C3-4 de
# la couche 3). Un seul test y portait le nom
# `test_la_granularite_offerte_par_le_coeur_est_la_PAGE` et etait rattache a
# l'AC 9.8. Or l'AC 9.8 parle de la granularite de l'**interruption**, et ce
# test assertait deux proprietes de l'**avancement** -- l'unite comptee et
# l'existence du canal. Deux faits differents, et le nom du test faisait dire
# au second ce que seul le premier aurait pu dire.
#
# Le produit consulte `interrompu` **entre deux lots**, jamais entre deux pages
# (`atelier_pdf_parcours.executer_les_lots`), et il le motive : le canal de
# progression du coeur est observationnel par contrat (`EPIC7-ARB-79`), il ne
# peut rien arreter. Le choix est bon et il est dit ; c'etait le rattachement
# du test qui etait faux, pas le code.
#
# Les deux moities sont donc mesurees separement, chacune la ou elle vit :
# l'unite d'avancement ici, la granularite effective de l'interruption par
# `test_atelier_pdf_parcours.test_I2_l_interruption_est_consultee_ENTRE_deux_lots`,
# et la moitie de l'AC 9.8 qui appartient a CE module -- « l'ecran ne promet
# jamais une interruption plus fine que ce que le coeur offre » -- par la
# frontiere negative ci-dessous.


def test_l_UNITE_D_AVANCEMENT_offerte_par_le_coeur_est_la_PAGE():
    """`render_lot_pdf` emet un jalon par page : c'est l'unite que la barre et
    le panneau comptent (AC 9.1).

    **Elle ne dit RIEN de la granularite de l'interruption** (AC 9.8) : un
    canal qui emet par page est observationnel, il n'offre aucun point d'arret.
    Le nom precedent de ce test le laissait croire.
    """
    assert generation.UNITE == "pages"
    source = (SOURCE_DU_COEUR / "pdf_render.py").read_text(encoding="utf-8")
    assert "rappel_progression" in source


#: Ce qu'un ecran d'interruption promettrait s'il annoncait un point d'arret
#: plus fin que celui du produit. Le produit s'arrete **entre deux lots** ; une
#: seule de ces tournures suffirait a faire attendre a l'operateur un arret qui
#: n'arrivera pas, et il l'attendrait au pire moment -- pendant un lot de 21
#: pages.
PROMESSES_D_UN_ARRET_TROP_FIN = ("entre deux pages", "a la page",
                                 "à la page", "page en cours",
                                 "apres la page", "après la page",
                                 "immediatement", "immédiatement",
                                 "tout de suite")


def test_T6_1_ne_PROMET_aucun_arret_plus_FIN_que_celui_du_produit():
    """La moitie de l'AC 9.8 qui appartient a ce module.

    `T6-1` **compte** ce qui est ecrit -- « Interrompre et garder les 12 pages »
    -- et c'est un constat, pas une promesse d'arret. Rien de ce que l'ecran
    rend ne doit annoncer un point d'arret a la page, alors que le produit
    s'arrete entre deux lots.

    **Volet symetrique**, sans lequel la frontiere serait verte pour la mauvaise
    raison : l'ecran parle bien de pages quelque part -- ce sont celles qui sont
    **deja ecrites**, et le compte est un fait du passe, pas une echeance.
    """
    modele = passe()
    rendus = [libelle_chiffre(issue, modele)
              for issue in generation.issues_chiffrees(modele)]
    rendus.append(generation.ligne_d_etat_de_l_interruption(modele))
    rendus.extend(ligne.libelle
                  for ligne in generation.panneau_de_la_passe(modele).lignes)
    rendus.append(generation.TITRE_DE_L_INTERRUPTION)
    entier = " ".join(rendus).lower()
    for promesse in PROMESSES_D_UN_ARRET_TROP_FIN:
        assert promesse not in entier, (promesse, entier)
    assert "pages" in entier, entier


def libelle_chiffre(issue, modele) -> str:
    """Le libelle tel que `T6-1` le rend -- lu du produit, jamais recompose."""
    return generation.libelle_chiffre_de_l_issue(issue, modele)


# ---------------------------------------------------------------------------
# AC 11 -- les frontieres du module, avec leur volet symetrique
# ---------------------------------------------------------------------------


def test_le_module_n_importe_JAMAIS_cli():
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    modules = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            modules.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            modules.add(noeud.module or "")
    assert not any("cli" in nom.split(".") for nom in modules), modules


def test_le_module_importe_BIEN_le_coeur_dont_il_lit_les_valeurs():
    """Volet symetrique : la frontiere ci-dessus a un objet a mesurer."""
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    assert "from .. import qr_codes" in source


def test_le_module_ne_porte_ni_print_ni_stdout_ni_subprocess():
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    for interdit in ("subprocess", "sys.stdout", "print("):
        assert interdit not in source, interdit


def test_le_module_ne_porte_AUCUN_mot_du_vocabulaire_des_RANGS():
    """La frontiere de la 11.6 compte a zero, prose et docstrings comprises.

    « Le rang est AFFICHE, jamais recalcule » (`EPIC11-ARB-92`) : ce module ne
    resout, ne libere et ne consomme aucun rang.
    """
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8").lower()
    for interdit in ("version_rank", "resolve_version_rank", "nouvelle_version",
                     "ligne d'eau", "watermark", "version_ranks"):
        assert interdit not in source, interdit


def test_aucun_glyphe_hors_de_la_table_n_entre_dans_le_module():
    """AC 11.6 : ni `*` litteral, ni glyphe de deroulant.

    Les quatre signes du rotor sont **attendus** : ils sont du produit
    (`jetons.ROTOR`), et ce module ne les ecrit pas -- il appelle `jetons.rotor`.
    """
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    for dessin in jetons.ROTOR:
        assert dessin not in source, dessin
    for deroulant in ("▾", "▼", "▸▸"):
        assert deroulant not in source, deroulant


def test_execution_py_n_est_PAS_modifie_par_ce_lot():
    """AC 9.5, mesure en frontiere : `T6-1` herite, il ne patche pas.

    Le module ne pose aucun attribut sur `execution`, ni sur ses classes.
    """
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Assign):
            continue
        for cible in noeud.targets:
            if isinstance(cible, ast.Attribute) and isinstance(
                    cible.value, ast.Name):
                assert cible.value.id not in ("EcranInterruption",
                                              "EcranExecution",
                                              "SurfaceExecution")


def test_la_ligne_de_raccourcis_tient_le_budget_dans_les_DEUX_regimes():
    """MESURE commentee dans le module, refaite ici. Zone utile de 76."""
    ligne = generation.RACCOURCIS_GENERATION
    assert jetons.colonnes(ligne) <= 76
    assert jetons.colonnes(jetons.replier_ascii(ligne)) <= 76


def test_la_ligne_de_raccourcis_est_celle_de_la_maquette():
    maquette = (MAQUETTES / "E5-4-pdf-execution.txt").read_text(
        encoding="utf-8").split("\n")
    cadre = [ligne for ligne in maquette[:24] if ligne.startswith("│")]
    assert cadre[-1][2:-1].rstrip() == generation.RACCOURCIS_GENERATION


def test_le_titre_du_bandeau_ne_porte_aucun_terme_de_CONCEPTION():
    """`EPIC11-ARB-28` : ni « palier », ni « parcours a part », ni « feuille »."""
    assert generation.PALIER_DE_LA_GENERATION == "Pdf"
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8").lower()
    for interdit in ("parcours a part", "feuille cli", "marge de recadrage"):
        assert interdit not in source


# ---------------------------------------------------------------------------
# Les gardes de la fabrique elle-meme
# ---------------------------------------------------------------------------


def test_la_fabrique_porte_TROIS_lots_DISTINGUABLES_cible_au_MILIEU():
    """La garde de la regle des fabriques, sur la liste que le code PARCOURT.

    Sans elle, une fabrique reduite a deux lots rendrait indiscernables une
    faute de `find` et une faute de terminaison de boucle, et personne ne le
    verrait.
    """
    modele = passe()
    assert len(modele.lots) == 3
    assert len({lot.pages for lot in modele.lots}) == 3
    assert len({lot.nom for lot in modele.lots}) == 3
    assert modele.rang_du_lot_courant == 1


def test_une_passe_SANS_lot_est_refusee_a_la_construction():
    with pytest.raises(ValueError):
        generation.PasseDeGeneration(())


# ---------------------------------------------------------------------------
# AC 9 -- le drapeau de tache, mesure dans les DEUX sens (finding C2-1)
# ---------------------------------------------------------------------------
#
# Le defaut ferme ici : `on_mount` posait `app.tache_en_cours = True` et rien ne
# le retirait. `descendre` DIFFERE le message `Mount`, et la passe est appelee
# **synchroniquement** dans la foulee -- elle occupe la boucle d'evenements du
# premier au dernier jalon. L'ordre reel etait donc :
#
#     False <- oublier_la_tache          (fin de passe, cote parcours)
#     True  <- on_mount                  et plus personne ne l'eteignait
#
# Ce qui restait : `Échap` ne depilait plus, `q` ne quittait plus. C'est le
# defaut deja paye par `atelier_scan_calibrate.py:946-980`, a l'identique.
#
# **Les deux sens sont mesures**, et le second l'est parce que la fermeture
# jumelle du 2026-09-01 l'a coute : poser le drapeau pour proteger la passe
# avait empeche `CoqueTui.action_remonter` de depiler, donc le filet du
# demontage de l'ecran de collision ne se declenchait plus jamais et le fil de
# travail attendait pour toujours. Un drapeau qui protege sans se rendre est un
# atelier mort ; un drapeau qui se rend sans proteger est un `Échap` qui fait
# disparaitre une tache de la vue.


def _coque_de_la_passe() -> CoqueTui:
    """Une coque a DEUX paliers, montee au second.

    Deux et non un : `CoqueTui.action_remonter` ne depile que si `rang > 0`, et
    un banc pose a la racine mesurerait « la pile n'a pas bouge » sur une coque
    qui n'avait rien a depiler -- c'est-a-dire ne mesurerait rien.
    """
    return CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"),
                             PalierTemoin("Pdf", "Q quitter")],
                    contexte=Contexte(projet="projet_demo"))


def _partir_en_passe(app):
    """Ce que `ParcoursPdf.generer` fait, dans le meme ordre et sans pause.

    L'absence de `pause` **est** la mesure : le parcours appelle le coeur dans
    la foulee du montage, sans rendre la main a la boucle d'evenements.
    """
    return generation.ouvrir_la_generation(
        app, SurfaceExecution(unite=generation.UNITE), passe(),
        sur_issue=lambda _issue: None)


def _table_du_compte_rendu() -> resultat.TableDesEcrits:
    """Le `E5-5` minimal que le parcours monte PAR-DESSUS `E5-4`."""
    return resultat.TableDesEcrits(
        planches=(resultat.PlancheEcrite(
            "projet_demo_plan-01_25_6f-pay_v4.pdf", 21, 4),),
        frames=124)


def test_pendant_la_passe_le_drapeau_PROTEGE_avant_meme_que_MOUNT_arrive(banc):
    """Premier sens : la tache en cours protege, **des que la passe part**.

    Un drapeau pose au montage n'est pas encore pose pendant la passe, et
    `Échap` y depilerait l'ecran d'une tache qui tourne -- il ferait disparaitre
    la tache de la vue au lieu de demander quoi en faire.
    """
    async def scenario(pilote):
        app = pilote.app
        app.descendre()
        await pilote.pause()
        hauteur = len(app.screen_stack)
        _partir_en_passe(app)
        pendant = app.tache_en_cours
        app.action_remonter()
        return pendant, hauteur, len(app.screen_stack), app.interruption_demandee

    pendant, hauteur, apres, interruption = banc(_coque_de_la_passe(), scenario)
    assert pendant is True
    assert apres == hauteur + 1, (hauteur, apres)
    assert interruption is True


def test_la_passe_FINIE_eteint_le_drapeau_meme_si_MOUNT_arrive_APRES(banc):
    """Second sens, et c'est le defaut mesure : l'ecran se demonte ensuite.

    La sequence est celle du parcours -- montage de `E5-4`, coeur synchrone,
    `oublier_la_tache`, montage de `E5-5` -- puis **deux** `pause`, qui sont ce
    qu'il faut pour que les messages `Mount` differes soient distribues. C'est
    la ou le drapeau se rallumait.
    """
    async def scenario(pilote):
        app = pilote.app
        app.descendre()
        await pilote.pause()
        _partir_en_passe(app)
        app.oublier_la_tache()
        resultat.ouvrir_le_resultat(app, _table_du_compte_rendu(),
                                    sur_suite=lambda _suite: None)
        await pilote.pause()
        await pilote.pause()
        avant = (app.tache_en_cours, len(app.screen_stack))
        app.action_remonter()
        await pilote.pause()
        return avant, len(app.screen_stack), app.interruption_demandee

    (drapeau, hauteur), apres, interruption = banc(_coque_de_la_passe(),
                                                   scenario)
    assert drapeau is False
    assert apres == hauteur - 1, (hauteur, apres)
    assert interruption is False


def test_le_DEMONTAGE_de_l_ecran_de_la_passe_REND_le_drapeau(banc):
    """Le filet, pour les chemins qui depilent au lieu de conclure.

    `atelier_scan_parcours.EcranCollisionDeLaPasse` a paye exactement ce cas :
    un ecran depile pendant qu'un drapeau protege, et le fil de travail qui
    attend derriere n'est jamais repris. Ici le demontage rend le drapeau, donc
    la coque redevient navigable sans que personne ait a y penser.
    """
    async def scenario(pilote):
        app = pilote.app
        app.descendre()
        await pilote.pause()
        _partir_en_passe(app)
        await pilote.pause()
        pendant = app.tache_en_cours
        app.pop_screen()
        await pilote.pause()
        return pendant, app.tache_en_cours

    pendant, apres = banc(_coque_de_la_passe(), scenario)
    assert pendant is True
    assert apres is False


def test_le_demontage_d_un_ecran_PRECEDENT_n_eteint_PAS_la_passe_SUIVANTE(banc):
    """L'extinction est CONDITIONNELLE, et ce second tour l'a impose ailleurs.

    `atelier_scan_calibrate` le dit mot pour mot : demonter l'ecran d'une passe
    finie puis lancer la suivante faisait tomber le drapeau de la passe NEUVE --
    fil vivant, garde de re-entrance desarmee. On n'eteint donc que si l'ecran
    demonte est **encore** celui de la tache.
    """
    async def scenario(pilote):
        app = pilote.app
        app.descendre()
        await pilote.pause()
        premier = _partir_en_passe(app)
        await pilote.pause()
        app.oublier_la_tache()
        _partir_en_passe(app)
        await pilote.pause()
        # Le premier ecran se demonte APRES que la passe suivante est partie.
        premier.on_unmount()
        return app.tache_en_cours

    assert banc(_coque_de_la_passe(), scenario) is True


def test_sur_le_COMPTE_RENDU_la_touche_Q_quitte_encore(banc):
    """L'autre consequence du drapeau inverse dans le temps (couche 1, `F2`).

    `CoqueTui.action_quitter` demande confirmation tant qu'une tache tourne.
    Le drapeau rallume par un `Mount` tardif faisait donc de `Q` une demande de
    confirmation **sur le compte rendu d'une passe finie**, alors que la ligne
    de raccourcis de `E5-5` annonce `Q quitter`.
    """
    async def scenario(pilote):
        app = pilote.app
        app.descendre()
        await pilote.pause()
        _partir_en_passe(app)
        app.oublier_la_tache()
        resultat.ouvrir_le_resultat(app, _table_du_compte_rendu(),
                                    sur_suite=lambda _suite: None)
        await pilote.pause()
        await pilote.pause()
        app.action_quitter()
        return app.confirmation_de_sortie_demandee

    assert banc(_coque_de_la_passe(), scenario) is False


def test_le_ROTOR_d_une_passe_CONCLUE_s_arrete__celui_d_une_passe_VIVE_tourne(banc):
    """`E5-5` se monte PAR-DESSUS `E5-4`, qui n'est donc jamais demonte.

    Un `on_unmount` seul laisserait derriere chaque passe un minuteur qui
    redessine un ecran que plus personne ne regarde et qu'aucun jalon
    n'alimente (couche 1, `F3`). Le volet symetrique est la seconde mesure :
    tant que la passe est la sienne, le rotor tourne -- sans quoi la frontiere
    serait verte sur un ecran qui n'aurait plus de rotor du tout.
    """
    async def scenario(pilote):
        app = pilote.app
        app.descendre()
        await pilote.pause()
        vive = _partir_en_passe(app)
        await pilote.pause()
        await pilote.pause()
        tourne = vive.minuteur is not None
        conclue = _partir_en_passe(app)
        app.oublier_la_tache()
        resultat.ouvrir_le_resultat(app, _table_du_compte_rendu(),
                                    sur_suite=lambda _suite: None)
        await pilote.pause()
        await pilote.pause()
        return tourne, conclue.minuteur

    tourne, minuteur = banc(_coque_de_la_passe(), scenario)
    assert tourne is True
    assert minuteur is None
