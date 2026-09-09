# -*- coding: utf-8 -*-
"""Catalogue des chaines utilisateur de la GUI (NFR2, ``EPIC7-ARB-52``).

Interface en francais en v1, aucune traduction livree : le catalogue rend
l'EXTRACTION des chaines faite (une future langue remplacera ce module par
un mecanisme de traduction), pas la traduction elle-meme. C'est un module
Python -- dict de chaines, cles ASCII -- et non un couple ``.ts``/``.qm``
Qt Linguist : l'outillage Linguist s'ajoutera quand l'anglais reviendra
(hors v1). Decision portee par la fiche 7.0.

Regles :

* les CLES sont en ASCII (identifiants techniques) ; les VALEURS sont les
  libelles affiches, en francais, accents compris ;
* aucun composant de ``gui/`` n'affiche une chaine en dur : tout libelle
  visible se lit ici (AC 6, teste par substitution de catalogue) ;
* aucune boite n'est calee sur la largeur d'une chaine : toute chaine peut
  s'allonger de 40 % sans troncature (regle i18n de ``DESIGN.md``, testee
  par catalogue gonfle) ;
* les codes du coeur (``LOT_INCOMPLETE``, ``sha256-v1:``...) ne se
  traduisent JAMAIS : ils s'affichent verbatim a cote de leur phrase, ils
  n'entrent donc pas dans ce catalogue.
"""

CHAINES = {
    # Fenetre et en-tete.
    "app-titre": "mixed_media_utility",
    # Les quatre ateliers, dans l'ordre du flux (EXPERIENCE.md, par. IA).
    "atelier-extraction": "Extraction",
    "atelier-pdf": "Pdf",
    "atelier-scan": "Scan",
    "atelier-exports": "Exports",
    # Zones de chrome reservees par la coquille (contenus : 7.1 a 7.3).
    "zone-arborescence": "Arborescence",
    "zone-chutier": "Chutier",
    "zone-panneau-lateral": "Réglages",
    "zone-reservee": "Zone réservée",
    # Rail de l'arborescence repliee : le bouton qui rouvre.
    "rail-rouvrir-arborescence": "Rouvrir l'arborescence",
    "replier-arborescence": "Replier l'arborescence",
    # Etats de l'executeur de taches (FR4 ; cartes visibles en 7.3).
    "etat-tache-en-cours": "En cours",
    "etat-tache-terminee": "Terminée",
    "etat-tache-echouee": "Échouée",
}

# ---------------------------------------------------------------------------
# Ecran de gestion de projet (story 7.1). Bloc ajoute en fin de fichier pour
# ne pas croiser les editions d'une autre story sur ce meme module.
# ---------------------------------------------------------------------------

CHAINES.update({
    "ecran-projet-accroche": "Ouvrez un projet, ou créez-en un nouveau.",
    # Les trois actions de la surface (EPIC7-ARB-60 : l'import est maintenu).
    "ecran-projet-creer": "Créer un projet",
    "ecran-projet-ouvrir-dossier": "Ouvrir un dossier",
    "ecran-projet-importer": "Importer un projet existant",
    "ecran-projet-ouvrir": "Ouvrir",
    # Tri et recherche.
    "ecran-projet-recherche": "Rechercher un projet",
    "ecran-projet-tri": "Trier par",
    "ecran-projet-tri-nom": "Nom",
    "ecran-projet-tri-creation": "Date de création",
    "ecran-projet-tri-modification": "Date de modification",
    # Epingle : le geste vit SUR la ligne (EPIC7-ARB-37 -- le menu
    # contextuel n'arrive qu'en 7.11, et aucune commande ne doit exister
    # uniquement au clic droit en attendant).
    "ecran-projet-epingler": "Épingler ce projet",
    "ecran-projet-desepingler": "Désépingler ce projet",
    # Retirer : même raison que l'épingle, et l'inventaire des menus
    # contextuels d'`EXPERIENCE.md` le formule déjà — « Retirer de la liste
    # *(les fichiers ne sont pas touchés)* ». La parenthèse de la spine est
    # portée telle quelle : c'est la seule chose que l'utilisatrice a besoin
    # de savoir avant de cliquer, et c'est ce qui dispense de confirmer.
    "ecran-projet-retirer": "Retirer ce projet de la liste",
    "ecran-projet-retirer-detail": "Les fichiers du projet ne sont pas touchés.",
    # Reperes de ligne.
    "ecran-projet-dernier-ouvert": "Dernier projet ouvert",
    "ecran-projet-cree-le": "Créé le",
    "ecran-projet-modifie-le": "Modifié le",
    # Etat vide : les deux actions restent offertes.
    "ecran-projet-liste-vide": "Aucun projet dans la liste.",
    # Echecs. La phrase est du catalogue, le MOTIF qui la suit est lu de
    # l'exception du coeur et affiché verbatim -- il n'entre jamais ici.
    "ecran-projet-illisible": "Ce projet ne peut pas être lu :",
    "ecran-projet-nom-refuse": "Ce nom de dossier ne donne aucun identifiant de projet valide.",
    # Titre de la fenêtre une fois un projet ouvert (un seul à la fois).
    "fenetre-titre-projet": "{projet} — mixed_media_utility",
})

# ---------------------------------------------------------------------------
# Chutier a deux panneaux (story 7.2). Bloc ajoute en fin de fichier pour ne
# pas croiser les editions d'une autre story sur ce meme module.
#
# Les CARDINAUX et les LIBELLES D'ACTION vivent au catalogue et non dans les
# composants (NFR2) : « l'action porte son cardinal en toutes lettres,
# jamais un verbe nu » (`EPIC7-ARB-10`), et l'accord singulier/pluriel est
# une affaire de langue. Ils entrent dans `CHAINES` -- et non dans un
# dictionnaire a part -- pour que la substitution de catalogue les couvre
# comme le reste : un libelle qui echapperait a la substitution echapperait
# aussi a la traduction le jour ou l'anglais reviendra.
# ---------------------------------------------------------------------------

CHAINES.update({
    # En-tete du chutier : la PORTEE de ce qu'il montre.
    "chutier-portee": "Contenu de {objet} · {cardinaux}",
    "chutier-portee-projet": "Contenu du projet · {cardinaux}",
    "chutier-cardinal-vide": "vide",
    "chutier-cardinal-separateur": " · ",
    "chutier-plein-ecran": "Chutier en plein écran",
    "chutier-quitter-plein-ecran": "Quitter le plein écran du chutier",
    # Lignes de planche et de scan. `rang` est le rang de LECTURE du fichier
    # et `planche` le numero declare par le QR : les deux sont affiches, et
    # jamais l'un deduit de l'autre -- « le 3e fichier du dossier declare
    # etre la page 1 » (contrat de `scan_previz`, porte dans la GUI par E14).
    "chutier-planche": "Planche {planche}",
    "chutier-scan": "Fichier lu {rang} · planche {planche}",
    "chutier-scan-non-rattache": "Fichier lu {rang} · planche inconnue",
    # Cardinaux, par type de noeud : singulier et pluriel.
    "cardinal-rush-un": "{n} rush",
    "cardinal-rush-pluriel": "{n} rushes",
    "cardinal-rush-encode-un": "{n} rush encodé",
    "cardinal-rush-encode-pluriel": "{n} rushes encodés",
    "cardinal-lot-un": "{n} lot",
    "cardinal-lot-pluriel": "{n} lots",
    "cardinal-lot-reconstruit-un": "{n} lot reconstruit",
    "cardinal-lot-reconstruit-pluriel": "{n} lots reconstruits",
    "cardinal-planche-un": "{n} planche",
    "cardinal-planche-pluriel": "{n} planches",
    "cardinal-scan-un": "{n} scan",
    "cardinal-scan-pluriel": "{n} scans",
    # Badges de complétude (famille 1 : « que manque-t-il dans ce lot ? »).
    "badge-complet": "Complet",
    "badge-complet-avec-mires": "Complet avec mires",
    "badge-incomplet": "Incomplet",
    # Glyphes de rattachement (famille 2 : « que dois-je faire de cet
    # objet ? »). Chaque bulle dit le GESTE (`EPIC7-ARB-12`), jamais l'état.
    "glyphe-delie": "Fichier source introuvable : le retrouver et le relier",
    "glyphe-non-rattache": "Rattachement inconnu : identifier cet objet",
    "glyphe-incomplet": "Il manque des pièces : compléter ce lot",
    # Actions a cardinal. Trois formes par action : zéro (l'action est
    # inactive et le libellé le DIT), un, pluriel.
    "action-generer-planches-zero": "Générer des planches — aucun lot sélectionné",
    "action-generer-planches-un": "Générer 1 planche",
    "action-generer-planches-pluriel": "Générer {n} planches",
    "action-extraire-frames-zero": "Extraire les frames — aucun scan sélectionné",
    "action-extraire-frames-un": "Extraire 1 frame",
    "action-extraire-frames-pluriel": "Extraire {n} frames",
})


def cardinal(type_de_noeud, nombre, chaines=None):
    """Le cardinal d'un type de noeud, accorde, en toutes lettres.

    `type_de_noeud` est un des types du modele d'arbre
    (``modele_chutier.TYPES_DE_NOEUD``) ; le pluriel se prend a partir de
    deux, le singulier a un. Le cas zero n'est pas rendu ici : il ne se dit
    pas « 0 lot » mais par le libelle d'action, qui porte sa propre forme.
    """
    catalogue_actif = CHAINES if chaines is None else chaines
    forme = "un" if nombre == 1 else "pluriel"
    return catalogue_actif[f"cardinal-{type_de_noeud}-{forme}"].format(n=nombre)


def libelle_action(action, nombre, chaines=None):
    """Le libelle d'une action, portant son cardinal (`EPIC7-ARB-10`).

    « L'action porte son cardinal en toutes lettres ("Generer 3 planches"),
    jamais un verbe nu, parce qu'une selection implicite qui declenche un
    travail lourd sans le dire est un piege. » A zero objet, l'action est
    inactive **et le libelle le dit** -- c'est une forme a part entiere du
    catalogue, pas un verbe nu remis a la place.
    """
    catalogue_actif = CHAINES if chaines is None else chaines
    if nombre == 0:
        forme = "zero"
    elif nombre == 1:
        forme = "un"
    else:
        forme = "pluriel"
    return catalogue_actif[f"action-{action}-{forme}"].format(n=nombre)


# ---------------------------------------------------------------------------
# Atelier Scan -- le jugement : mode PDF, galerie, vue vignette unique
# (story 7.4). Bloc ajoute en fin de fichier pour ne pas croiser les editions
# d'une autre story sur ce meme module.
#
# Rappel du contrat de ce module, et il mord ici plus qu'ailleurs : **les
# codes du coeur ne se traduisent jamais**. Le code de refus enumere, le
# `template_source`, le `qr_status` et le motif verbatim de `refusal_reason`
# s'affichent tels que le document les porte, en typographie `data`, a COTE
# de la phrase du catalogue -- jamais a sa place, jamais reformules.
# ---------------------------------------------------------------------------

CHAINES.update({
    # Onglets de vue. L'onglet `lecteur` n'existe pas ici : c'est 7.6.
    "scan-onglet-page": "Page",
    "scan-onglet-galerie": "Galerie",
    "scan-onglet-frame": "Frame",
    # Barre de controles de vue -- UN composant pour toutes les surfaces
    # d'image (A10). « ajuster », et non « largeur » (EPIC7-ARB-17).
    "vue-zoom": "Zoom",
    "vue-ajuster": "Ajuster",
    "vue-pleine-largeur": "Pleine largeur",
    "vue-pleine-hauteur": "Pleine hauteur",
    "vue-taille-reelle": "100 %",
    # Les deux verrous (A8). Deux libelles distincts, jamais un signe unique.
    "scan-verrou-identite": "Identité (QR)",
    "scan-verrou-geometrie": "Géométrie (ArUco)",
    "scan-verrou-identite-detail": "Quel lot, quelle planche",
    "scan-verrou-geometrie-detail": "Où se trouvent les zones",
    "scan-verrou-tenu": "Tenu",
    "scan-verrou-rompu": "Rompu",
    "scan-verrou-indetermine": "Indéterminé",
    # Pourquoi aucune zone n'est proposée. La clé est celle que rend
    # `lecture_detection.motif_de_non_proposition`.
    "scan-motif-identite": "Aucune zone proposée : le QR n'a pas livré l'identité de cette planche.",
    "scan-motif-geometrie": "Aucune zone proposée : la géométrie de la page n'est pas résolue.",
    "scan-motif-aucune-zone": "Aucune zone proposée : ce document n'en porte aucune pour cette page.",
    # `EPIC7-ARB-75` : la phrase NEUTRE. Elle ne nomme aucun verrou parce que
    # le document ne dit pas lequel a lache -- et une phrase fausse envoie
    # l'operatrice verifier le mauvais element. Le detail reel arrive par
    # `refusal_reason`, affiche verbatim juste a cote.
    "scan-motif-refus-au-scan": "Aucune zone proposée : cette planche a été refusée au scan.",
    # Marqueurs. Les manquants sont NOMMÉS par identifiant, jamais dessinés.
    "scan-marqueurs-manquants": "Marqueurs de coin manquants : {identifiants}",
    "scan-marqueurs-tous-presents": "Les quatre marqueurs de coin sont lus.",
    "scan-marqueurs-etrangers": "Marqueurs étrangers détectés (listés, non placés) :",
    "scan-marqueur-etranger-ligne": "{identifiant} — {role}",
    # Refus de page. La phrase du coeur suit, VERBATIM.
    "scan-refus-motif": "Planche refusée :",
    "scan-refus-code": "Code :",
    # Valeurs par zone (A9). Hors du contenu d'image ET hors du panneau
    # latéral (EPIC7-ARB-22, EPIC7-ARB-68) : elles vivent sous la vignette.
    "scan-zone-taille": "{largeur} × {hauteur} px",
    "scan-zone-timecode-absent": "Timecode absent",
    "scan-zone-legende": "Emplacement {slot}",
    # Galerie.
    "scan-galerie-planche": "Planche {planche}",
    "scan-galerie-planche-inconnue": "Planche inconnue (fichier lu {rang})",
    "scan-galerie-page-manquante": "Planche {planche} — absente du scan",
    "scan-case-absente": "Aucune image ici",
    "scan-case-mire": "Mire de remplacement",
    "scan-case-sans-apercu": "Aperçu indisponible",
    "scan-galerie-zoom": "Taille des vignettes",
    # Vue vignette unique (EPIC7-ARB-18).
    "scan-frame-titre": "Emplacement {slot} — planche {planche}",
    "scan-panneau-deplier": "Déplier le panneau latéral",
    "scan-panneau-replier": "Replier le panneau latéral",
    # Bascule brut / corrigé, portée par la coquille (EPIC7-ARB-69).
    "image-bascule-brut-corrige": "Afficher l'image corrigée",
    "image-bascule-indisponible": "Aucune image corrigée pour ce lot : la bascule reste inactive.",
    "image-variante-brute": "Image brute",
    "image-variante-corrigee": "Image corrigée",
    # Aperçu de page indisponible (le raster n'est pas lisible ici).
    "scan-apercu-page-indisponible": "Aperçu de la page indisponible.",
})


# ---------------------------------------------------------------------------
# Atelier Scan, premier temps : deposer, detecter, annoncer (story 7.3).
# Bloc ajoute en fin de fichier pour ne pas croiser les editions d'une autre
# story sur ce meme module.
#
# **Ce qui n'entre PAS ici, et c'est la moitie de la regle** (P9) : aucun code
# ni aucun motif du coeur. Un motif d'echec de tache, un motif de reliquat
# (`scan_sorting.MOTIFS_DE_RELIQUAT`), un motif d'arret de passe s'affichent
# VERBATIM a cote de leur phrase -- la GUI les lit, elle ne les traduit ni ne
# les recopie. Une entree de catalogue pour l'un d'eux serait une seconde
# redaction, qui divergerait le jour ou le coeur change la sienne.
# ---------------------------------------------------------------------------

CHAINES.update({
    # La file, en haut du chutier (`A2`, `DESIGN.md` `bin-buffer`).
    # « Une file se vide, un fond de tiroir se remplit » : le titre dit
    # l'attente, jamais le stockage.
    "zone-tampon-titre": "En attente de lecture",
    "zone-tampon-vide": "Déposez ici un fichier, une sélection ou un dossier.",
    # Le bouton Detecter vit ICI, au chutier, jamais dans la previz
    # (`EPIC7-ARB-40`). Ses deux formes inactives DISENT pourquoi elles le
    # sont : un bouton grise sans phrase est une impasse.
    "zone-tampon-detecter": "Détecter",
    # Les deux motifs d'inactivite sont des PHRASES posees a cote du bouton,
    # jamais son libelle : un libelle de bouton qui s'allonge cale la boite sur
    # la longueur de la chaine, ce que la regle i18n de `DESIGN.md` interdit
    # (« aucune boite n'est calee sur la largeur d'une chaine »).
    "zone-tampon-detecter-sans-dpi": "Indiquez le dpi de numérisation pour lancer la détection.",
    "zone-tampon-detecter-sans-entree": "Cochez au moins une entrée pour lancer la détection.",
    # Le dpi est obligatoire et SANS DEFAUT (`EPIC7-ARB-44`) : le champ part
    # vide, et rien dans la GUI n'en propose un.
    "zone-tampon-dpi": "dpi de numérisation",
    # Le geste explicite, et le seul, qui retire une entree de la file.
    "zone-tampon-retirer": "Retirer de la file",
    # Les deux formes qu'une entree peut prendre. Elles nomment ce que le
    # coeur ingere : un dossier ou un PDF de plusieurs planches, ou une
    # planche seule.
    "zone-tampon-forme-scan": "Pile de planches",
    "zone-tampon-forme-planche": "Planche seule",
    # La deduction n'est JAMAIS silencieuse (`EPIC7-ARB-13` : « ce qui est
    # exclu : deviner en silence »). Elle s'annonce, et se corrige d'un geste.
    # Aucun BADGE de deduction n'est introduit (`EPIC7-ARB-14`) : c'est une
    # phrase de ligne, pas un signe de plus dans le vocabulaire du chutier.
    "zone-tampon-forme-deduite": "Forme déduite : {forme}",
    "zone-tampon-corriger-la-forme": "Corriger la forme",
    # Le reliquat : ce que la detection n'a rattaché à aucun lot RESTE ici,
    # nommé. `page` est le localisateur lu du rapport de tri, `motif` le code
    # du coeur, verbatim.
    "zone-tampon-reliquat": "Non rattaché : {page} — {motif}",
    # F14 (revue de vague 3) : la page d'un AUTRE projet. Classe disjointe du
    # reliquat dans la partition de 5.24, donc phrase disjointe -- le lot B
    # avait du reutiliser celle du reliquat faute de pouvoir toucher ce
    # fichier, et l'avait signale comme pis-aller.
    #
    # Deux formes, parce que le document porte ou ne porte pas le projet :
    # quand il le porte, on le NOMME. `EPIC5-ARB-105` pose que l'operateur
    # « ne doit pas avoir a le deviner », et c'est la raison d'etre du champ
    # `projet_a_utiliser` de `EntreeHorsPerimetre`.
    "zone-tampon-hors-perimetre": "Autre projet : {page} — {motif}",
    "zone-tampon-hors-perimetre-projet": "Projet {projet} : {page} — {motif}",
    # Le panneau des cartes de tâche (FR4).
    "panneau-taches-titre": "Tâches",
    "panneau-taches-vide": "Aucune tâche en cours.",
    # L'objet d'une carte : l'entrée déposée, puis — une fois la détection
    # faite — l'entrée ET le lot que le cœur y a trouvé.
    "carte-objet": "{objet}",
    "carte-objet-lot": "{objet} · lot {lot}",
    # L'annonce de complétude, AVANT toute écriture (FR7, V3.a).
    "atelier-scan-titre": "Scan — ce que la détection a trouvé",
    "atelier-scan-annonce": "Avant écriture — ce qui manque",
    "atelier-scan-annonce-vide": "Aucune détection pour l'instant.",
    "atelier-scan-completude": "Lot {lot} · {badge}",
    "atelier-scan-planches-manquantes": "Planches manquantes : {planches}",
    "atelier-scan-aucune-planche-manquante": "Aucune planche manquante",
    "atelier-scan-separateur": ", ",
})


# ---------------------------------------------------------------------------
# Retours de terrain du 2026-08-27 (`decisions-2026-08-27-epic-7-retours-terrain.md`).
#
# Bloc pose en un seul geste, AVANT les trois lots de correction, pour que
# ceux-ci n'aient a editer aucun fichier en commun. Les cles suivent la
# convention du module : ASCII, prefixees par la surface qui les affiche.
# ---------------------------------------------------------------------------

CHAINES.update({
    # --- EPIC7-ARB-92 : le bouton d'accueil, permanent dans l'en-tete. -----
    "coquille-accueil": "Revenir à l'écran des projets",

    # --- EPIC7-ARB-85 : la racine du projet, position atteignable. ---------
    # Le nom du projet est de la DONNEE (il vient du dossier ouvert) ; seule
    # l'enveloppe est un libelle. Sans projet ouvert, la ligne le dit.
    "arborescence-racine": "{projet}",
    "arborescence-racine-sans-projet": "Aucun projet ouvert",

    # --- EPIC7-ARB-82 : creer un projet, dossier parent + nom. -------------
    "ecran-projet-creer-titre": "Nouveau projet",
    "ecran-projet-creer-dossier-parent": "Dossier de destination",
    "ecran-projet-creer-choisir-dossier": "Choisir…",
    "ecran-projet-creer-nom": "Nom du projet",
    "ecran-projet-creer-apercu": "Le projet sera créé dans :",
    "ecran-projet-creer-apercu-incomplet":
        "Choisissez un dossier de destination et saisissez un nom.",
    "ecran-projet-creer-valider": "Créer",
    "ecran-projet-creer-annuler": "Annuler",
    "ecran-projet-creation-dossier-occupe":
        "Ce dossier existe déjà et porte un projet. Ouvrez-le plutôt que de le créer.",

    # --- EPIC7-ARB-87 : importer un scan par l'explorateur. ----------------
    # Libelles COURTS, et c'est une contrainte mesuree, pas un gout : la
    # colonne du chutier a pour plancher `bin-min-width` (250 px), et
    # « Importer un fichier » demande deja 242 px a lui seul -- 326 px une
    # fois la chaine gonflee de 40 %, comme la regle i18n de `DESIGN.md`
    # l'exige. Deux boutons de cette largeur poussaient la scene HORS de la
    # fenetre (`stage-min-width` franchi, mesure du 2026-08-27). Le verbe
    # complet vit dans l'infobulle, qui n'a pas de largeur a tenir.
    "zone-tampon-importer-fichier": "Des fichiers…",
    "zone-tampon-importer-dossier": "Un dossier…",
    "zone-tampon-selecteur-fichiers": "Choisir un ou plusieurs fichiers à lire",
    "zone-tampon-selecteur-dossier": "Choisir un dossier à lire",
    # Filtre du selecteur de fichiers. `{extensions}` est rempli avec les
    # extensions que le COEUR reconnait (`scan_ingest`), jamais avec une
    # seconde liste ecrite dans la GUI.
    "zone-tampon-filtre-fichiers": "Scans lisibles ({extensions})",

    # --- EPIC7-ARB-88 : une selection multiple est UN lot. -----------------
    # L'entree de file qui porte plusieurs fichiers dit combien, et sous quel
    # nom de lot elle partira.
    "zone-tampon-entree-selection": "{nom} · {pages} fichiers",

    # --- EPIC7-ARB-90 : remplacer une detection existante. -----------------
    "zone-tampon-detection-existante-titre": "Une détection existe déjà",
    "zone-tampon-detection-existante":
        "« {objet} » a déjà été détecté. Souhaitez-vous lancer une nouvelle "
        "détection sur ce fichier ? L'ancienne détection sera écrasée.",
    "zone-tampon-detection-existante-oui": "Oui, refaire la détection",
    "zone-tampon-detection-existante-non": "Non",
})
