# -*- coding: utf-8 -*-
"""Maquettes zone C : ateliers Exports et Pdf.

**Aucun identifiant de ce fichier n'est ecrit a la main.** Tous les `lot_id`,
noms de PDF de planches et noms de master sortent des fonctions du produit
(`io.naming`), appelees ici a la generation. C'est la reponse aux notes 2 et 3
d'Egan du 2026-09-01 (« `lot_hiver` n'existe toujours pas non ? ») : une valeur
inventee ne peut plus entrer dans ces maquettes, parce que personne ne les tape
plus.

Ce que la mesure disait, et qui donnait raison a Egan sur les trois points :

* `build_lot_id(rush, cadence)` compose `<rush_id>_<cadence-courte>`, plus un
  suffixe hache de huit hexa **seulement** si l'extraction est bornee par
  timecodes. `lot_hiver` est donc **impossible** -- aucun chemin ne rend un
  identifiant sans cadence ;
* `format_fps_short` rend `25`, `12p5`, `8` -- **jamais** `25fps` ni `08fps`.
  Toute la famille `lot_<n>fps` etait inventee au meme titre, et le suffixe
  `_ingest01` avec elle : ce qui suit la cadence est un condensat de huit hexa,
  ou rien ;
* `build_master_filename` rend `<lot_id>_mmu_<profil>[_<resolution>].<conteneur>`
  et **ne porte aucun prefixe de projet** : `projet_demo_..._mmu_prores_hq`
  etait faux d'un fragment entier, sur quatre maquettes d'Exports.

Le rush de demonstration s'appelle donc `plan-04`, la passe d'hiver `hiver`, et
les identifiants s'en deduisent.
"""
from construire_maquette import (maquette, barre, barre_double, cartouche,
                                 regle, ecrire, elider)

from mixed_media_utility import codec_profiles, encode, page_templates
from mixed_media_utility.io import naming
from mixed_media_utility.tui import jetons

PROJET = "projet_demo"
RUSH = "plan-04"
RUSH_HIVER = "hiver"
#: Un rush au nom LONG, pour que la colonne des noms se mesure sur un cas reel
#: et non sur les noms courts de la demonstration (note 1 d'Egan du 2026-09-01 :
#: « les noms sont bien plus longs dans mes projets »). Il n'est coche nulle
#: part : les ecrans en aval de `E5-1` ne le voient donc jamais, et la passe de
#: demonstration reste celle de deux lots.
RUSH_LONG = "sequence-12-atelier-fonderie-prise-3"

#: Les cinq lots de demonstration, **construits** et non ecrits.
LOT_25 = naming.build_lot_id(RUSH, 25)
LOT_12P5 = naming.build_lot_id(RUSH, 12.5)
LOT_8 = naming.build_lot_id(RUSH, 8)
LOT_HIVER = naming.build_lot_id(RUSH_HIVER, 24)
LOT_LONG = naming.build_lot_id(RUSH_LONG, 12.5)

#: **La largeur du champ de nom est la BORNE DU PRODUIT, pas la plus longue des
#: valeurs affichees** -- `CANONICAL_ID_MAX_LENGTH`, lue a `io.naming`. C'est la
#: reponse a la note 1 : une colonne dimensionnee sur la demonstration se
#: retrecit des que la demonstration change, et c'est exactement ce qu'Egan a
#: constate. Une colonne dimensionnee sur la borne tient tout identifiant que
#: l'outil accepte d'ecrire, par construction. CLAUDE.md le demande aussi dans
#: l'autre sens : on NOMME la constante, on ne recopie pas sa valeur.
LARGEUR_NOM = naming.CANONICAL_ID_MAX_LENGTH

#: La chaine de scan de demonstration. Le nom du PDF de la mire en DECOULE
#: (`build_calibration_pdf_filename`), condensat compris : il n'est nulle part
#: recopie.
CHAINE = "hp-envy-4520-tiff-600-dpi-auto-corr-off"


def planches(lot: str, rang: int | None = None, rush: str = RUSH,
             gabarit: str | None = None) -> str:
    """Le nom du PDF de planches, par la fonction du produit.

    `rang=None` est l'ORIGINE : `build_sheets_pdf_filename` n'ecrit alors aucun
    fragment `_vN` (`EPIC11-ARB-88`), et c'est cette absence qui dit « premier
    tirage ». Le rang 1 ne s'ecrit donc jamais.

    **`template_id` est desormais EXIGE** (`EPIC11-ARB-171`, livre le
    2026-09-02) : le mot `planches` a quitte le nom et la mise en page a pris
    sa place. Le fragment n'est plus compose ici -- c'est
    `naming.sheets_layout_fragment` qui le derive du gabarit --, et tout ce que
    ce module en dit vit desormais dans le produit.
    """
    return naming.build_sheets_pdf_filename(
        PROJET, rush, lot, version_rank=rang,
        template_id=gabarit or page_templates.build_template_id("paysage", 6, "0"))


#: **Le fragment de MISE EN PAGE d'un nom de tirage : `6f-pay`, `4f-por`.**
#:
#: `N7` (note 7 d'Egan, v5) : « Il n'y a pas le nombre de frames dans les noms
#: de planches ? » Non -- et deux mises en page du MEME lot rendaient alors le
#: MEME nom, ce qui rendait le motif du conflit opaque : l'ecran disait « ce
#: tirage existe deja » sans dire que c'est une AUTRE forme.
#:
#: **C'etait un dessin le 2026-09-01 ; c'est le produit depuis le 2026-09-02.**
#: `EPIC11-ARB-171` a retire le mot `planches` du nom et mis la mise en page a
#: sa place, `build_sheets_pdf_filename` exigeant desormais un `template_id`.
#: Tout ce que ce module composait a la main -- l'echange cardinal/orientation,
#: l'abreviation a trois lettres, le retrait de la version de geometrie -- vit
#: maintenant dans `naming.sheets_layout_fragment`, avec ses motifs. Les deux
#: constantes qui portaient cette recette ici sont retirees avec elle : une
#: seconde redaction d'une regle que le produit possede est exactement ce que
#: le depot paie quand elle diverge.


def mise_en_page(orientation: str, cardinal: int, marge: str = "0") -> str:
    """Le fragment de mise en page du NOM DE FICHIER : `6f-pay`, `4f-por`.

    **Il n'est plus compose ici.** Ces maquettes le fabriquaient a la main tant
    que le produit ne savait pas le faire ; depuis `EPIC11-ARB-171` (livre le
    2026-09-02) c'est `naming.sheets_layout_fragment` qui le derive du gabarit,
    et le dessin lit la fonction plutot que de redire sa regle -- une seconde
    redaction divergerait a la premiere retouche du vocabulaire des gabarits.
    """
    return naming.sheets_layout_fragment(
        page_templates.build_template_id(orientation, cardinal, marge))


def planches_mep(lot: str, orientation: str = "paysage", cardinal: int = 6,
                 rang: int | None = None, marge: str = "0") -> str:
    """Le nom de tirage, **entierement rendu par la fonction du produit**.

    Il ne reste ici aucune chirurgie de chaine : le gabarit est construit, passe
    a `build_sheets_pdf_filename`, et c'est elle qui place le fragment et le
    rang. La forme qu'Egan a demandee le 2026-09-02 -- « retirer le mot
    planches et mettre 4f-por ou 4f-pay a la place » -- est donc celle que le
    produit ECRIT, plus celle que la maquette dessine.
    """
    return planches(
        lot, rang,
        gabarit=page_templates.build_template_id(orientation, cardinal, marge))


def master(lot: str, profil: str = "prores_hq", conteneur: str = "mov",
           rang: int | None = None) -> str:
    """Le nom du master video, par la fonction du produit.

    `rang=None` est l'ORIGINE : `build_master_filename` n'ecrit alors aucun
    fragment `_vN` (`EPIC11-ARB-88`), exactement comme pour les tirages. Le
    rang 1 ne s'ecrit donc jamais, et `E4-3b` obtient `_v2` de la fonction du
    produit plutot que par concatenation -- c'est la meme regle de rangs pour
    les CINQ objets versionnables (`EPIC11-ARB-108`).
    """
    return naming.build_master_filename(
        lot_id=lot, profile_id=profil, container=conteneur, version_rank=rang)


def calibration(chaine: str) -> str:
    """Le nom de la page de calibration, par la fonction du produit."""
    return naming.build_calibration_pdf_filename(PROJET, chaine)

# ---------------------------------------------------------------- Exports ----
#
# **DEUXIEME PASSE, 2026-09-03 (story 11.8, lot A).** La passe du 2026-09-02
# avait porte les trente-deux passages faux mesures par la fiche ; Egan a relu
# la planche qui en est sortie et pose dix-huit notes. Elles ont donne sept
# arbitrages (`EPIC11-ARB-186` a `-192`) et deux stories neuves (6.8 et 11.12),
# et **ce bloc porte les sept**. Les trois plus lourds, pour que la relecture
# sache ou elle met les pieds :
#
# * **`E4-2b` change de NATURE une seconde fois** (`EPIC11-ARB-192`). Le champ
#   s'appelle desormais **« cadence du rushe source »** -- libelle d'Egan,
#   verbatim -- et c'est une DECLARATION de la vraie cadence du rushe, jamais
#   un choix de cadence de sortie. La passe precedente confondait encore
#   `fps_target` (12,5 -- la decimation, un parametre de SELECTION) et
#   `timecode_base_fps` (25 -- la seule cadence qui muxe) : pour un lot 12p5
#   issu d'un rushe 25p, la cadence source EST 25, rien n'est ecarte, et
#   l'ecran posait un ▲ orange sur le cas NOMINAL. L'ecran devient donc l'etat
#   du champ **quand le lot n'en porte aucune** ;
# * **les pastilles de completude viennent du DISQUE** (`EPIC11-ARB-186`),
#   avec un glyphe de chargement pendant le balayage -- c'est cet etat-la que
#   `E4-1` dessine desormais, l'option que la planche ne recommandait pas et
#   qu'Egan a retenue en ajoutant le glyphe qui la rend tenable ;
# * **on n'encode pas un lot, on encode un lot RECONSTRUIT** (`EPIC11-ARB-190`,
#   verbatim d'Egan : « Avec le versionnage je peux, pour un meme lot,
#   reconstruire plusieurs fois le lot avec des versions differentes »).
#   `E4-1` designe donc un lot PUIS sa reconstruction des qu'il en porte
#   plusieurs. Le coeur qui le permet est la story 6.8, lancee en parallele :
#   l'ecran est dessine, rien n'est code.
#
# Les quatre autres, en une ligne chacun : plus de famille de profil, seulement
# `defaut` sur le profil par defaut (`-187`) ; l'ecran de conflit annonce ce
# qui sera DETRUIT et cesse de conseiller un usage (`-188`) ; la ligne d'etat
# de l'execution perd « aucun compte n'est emis », qui est de la tuyauterie
# (`-189`) ; et l'atelier encode UN lot, la file d'attente etant la story 11.12
# (`-191`).
#
# Ce que la passe du 2026-09-02 avait deja porte et qui TIENT : la cadence du
# master est la cadence source et non `fps_target` ; le champ « Nom du master »
# et sa touche `e` sont retires (`EPIC11-ARB-141`, confirme par Egan : « On
# affiche le nom du master. Il n'est pas modifiable ») ; les `( )` des listes
# d'issues tombent sous `-45` / `-126` ; le curseur quitte toute issue qui
# ecrit (`-7`) ; et aucun ecran ne porte plus `Q quitter` (`-140`, livre).

#: Le glyphe de CHARGEMENT des pastilles de completude (`EPIC11-ARB-186`).
#: Il est lu du produit -- `jetons.rotor` --, jamais dessine ici : c'est le
#: meme signe que celui des ecrans d'execution, et il ne porte aucune couleur
#: d'etat, ce qui est exactement ce qu'on veut d'un verdict PAS ENCORE RENDU.
CHARGEMENT = jetons.rotor(0)

#: Les deux glyphes d'un champ EXCLUSIF, lus de la table du produit. La liste
#: des reconstructions de `E4-1` est un champ de formulaire, pas une liste
#: d'issues : elle porte donc la puce. Elle ne porte PAS la fleche parce que le
#: focus est ailleurs -- `EPIC11-ARB-180` ne donne les deux glyphes qu'au champ
#: exclusif QUI A LE FOCUS.
RETENU = jetons.GLYPHES["exclusif-retenu"]
LIBRE = jetons.GLYPHES["exclusif-libre"]

#: La largeur de la colonne des libelles des cartes et des formulaires. Elle
#: est calee sur le libelle le plus long, qui est celui d'Egan : « Cadence du
#: rushe source ». Une colonne calee sur un libelle plus court aurait oblige a
#: abreger le sien, ce qui est exactement ce que `EPIC11-ARB-192` interdit --
#: le libelle EST la decision, il dit que le champ declare et ne choisit pas.
LIBELLE = len("Cadence du rushe source") + 4


#: Le nom des colonnes de la liste deroulee est **lu** du produit, jamais
#: recopie : le conteneur sort de `codec_profiles.PROFILES`, qui est fige
#: (`EPIC11-ARB-33`, aucun profil personnalise en v1). Le mot `defaut` sort de
#: `DEFAULT_PROFILE_ID` et non d'un litteral : changer le defaut du coeur
#: deplace la mention toute seule.
def liste_deroulee_des_profils(indent: int = 26) -> list[str]:
    """Les sept profils, tels que le produit les porte.

    **La liste n'est pas ecrite, elle est construite.** C'est ce qui ferme le
    defaut #9 de la fiche 11.8 : le dessin d'origine annoncait des categories
    (`mezzanine`, `mezzanine leger`, `mezzanine 12 bits`, `diffusion`) dont
    AUCUNE n'existe dans `codec_profiles.PROFILES`, et un `dnxhr_hqx` « 12
    bits » quand son `pix_fmt` est `yuv422p10le`. Une maquette qui lit le
    produit ne peut plus dire cela.

    **La colonne de FAMILLE est retiree le 2026-09-03** (`EPIC11-ARB-187`,
    Egan : « Juste `defaut` sur le profil par defaut. `secondary` n'apporte
    aucune information »). Le profil par defaut porte la mention `defaut` ; les
    six autres ne portent RIEN. Ni `primary`/`secondary` -- deux mots anglais
    qui n'apprennent rien --, ni traduction, qui serait un mot de plus a l'ecran
    pouvant diverger de l'outil. La categorie reste LUE du produit ailleurs
    (c'est elle qui designe le defaut), elle n'est simplement plus AFFICHEE.

    **`EPIC11-ARB-180` (2026-09-02) commande la forme** : un champ exclusif de
    formulaire QUI A LE FOCUS porte les deux glyphes -- la fleche dit ou est le
    curseur, la puce ce qui est retenu. `EPIC11-ARB-126` (« Fleche seule ! »)
    n'est pas renverse : il ne regit que les listes d'ISSUES, et celle-ci n'en
    est pas une.
    """
    marge = " " * indent
    lignes = []
    for identifiant, profil in codec_profiles.PROFILES.items():
        vise = identifiant == codec_profiles.DEFAULT_PROFILE_ID
        tete = f"{jetons.GLYPHES['curseur']} {RETENU}" if vise else f"  {LIBRE}"
        defaut = " · défaut" if vise else ""
        lignes.append(f"{marge}{tete} {identifiant:<17}.{profil.container}{defaut}")
    return lignes


#: Le glose de resolution, **lu** du coeur. `known_resolution_ids()` rend le
#: couple, `NATIVE_RESOLUTION_KEYWORD` le mot-cle, et la forme personnalisee
#: `<largeur>x<hauteur>` est celle que `_parse_custom_resolution` accepte --
#: la maquette d'origine ne la montrait pas, ce qui aurait fait de la TUI une
#: surface MOINS capable que la CLI sans qu'aucune decision ne le demande (Q3).
#: La forme personnalisee est ecrite `<l>x<h>` -- le `x` est un ASCII et non
#: un `×` typographique, parce que c'est ce que `_parse_custom_resolution`
#: accepte : un glyphe plus joli ferait saisir une valeur que le coeur refuse.
GLOSE_RESOLUTION = " · ".join(
    (*encode.known_resolution_ids(), encode.NATIVE_RESOLUTION_KEYWORD,
     "<l>x<h>"))

#: La colorimetrie est portee par le PROFIL, pas par le manifest -- mesure :
#: `codec_profiles.PROFILES['prores_hq'].colorspace`. Le dessin d'origine
#: disait « reinjecte depuis le manifest », ce qui designait la mauvaise
#: source ; c'est le trente-troisieme ecart, trouve en dessinant.
COLORIMETRIE = codec_profiles.PROFILES[codec_profiles.DEFAULT_PROFILE_ID].colorspace


# `E4-1` -- **TROIS changements le 2026-09-03, et deux viennent d'une story de
# coeur qui n'existait pas hier.**
#
# 1. **Les pastilles viennent du DISQUE** (`EPIC11-ARB-186`, decision D1). La
#    planche recommandait le manifest, au motif que le disque coute un balayage
#    par lot liste ; Egan a retenu le disque **en ajoutant le glyphe de
#    chargement**, que personne n'avait propose. C'est cet etat-la qui est
#    dessine : deux lots comptes, trois en cours de balayage. Un verdict
#    toujours exact, et le prix rendu visible plutot que subi.
# 2. **On designe un lot PUIS sa reconstruction** (`EPIC11-ARB-190`). Mesure
#    qui l'a fait naitre : `lots[].output_frames_dir` est un champ SCALAIRE,
#    reecrit a chaque passe, si bien que les versions `_vN` d'un lot rescanne
#    sont sur le disque, inscrites a `lots[].reconstructions`, et
#    **inatteignables a l'export**. La story de coeur 6.8 les rend joignables ;
#    cet ecran les montre. Le champ ne porte PAS la fleche : le focus est sur
#    la liste des lots, et `EPIC11-ARB-180` ne donne les deux glyphes qu'au
#    champ exclusif qui l'a.
# 3. **`Q quitter` part** (`EPIC11-ARB-140`, tranche le 2026-09-02 et LIVRE) :
#    c'etait le dernier ecran `E4-*` a le porter.
#
# Le libelle « Cadence source » devient « Cadence du rushe source » ici comme
# ailleurs (`EPIC11-ARB-192`) : le meme champ porte le meme nom sur les quatre
# ecrans qui l'affichent, sans quoi l'operateur croit en voir deux.
ecrire("E4-1-exports-lot.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Exports",
    bandeau_droite="",
    centre=[
        "",
        "  Quel lot encoder ?",
        "",
        f"   ▸ {LOT_25:<{LARGEUR_NOM}}● complet",
        f"     {LOT_12P5:<{LARGEUR_NOM}}● complet",
        f"     {LOT_8:<{LARGEUR_NOM}}{CHARGEMENT} balayage",
        f"     {LOT_HIVER:<{LARGEUR_NOM}}{CHARGEMENT} balayage",
        f"     {LOT_LONG:<{LARGEUR_NOM}}{CHARGEMENT} balayage",
        "",
        regle("Le lot désigné"),
        "",
        f"     {'Reconstruction':<{LIBELLE}}{RETENU} v2  02/09 · 8 planches · 124 frames",
        f"     {'':<{LIBELLE}}{LIBRE} v1  26/08 · 6 planches · 118 frames",
        f"     {'Frames retenues':<{LIBELLE}}124 sur 124 attendues     ● complet",
        f"     {'Cadence du rushe source':<{LIBELLE}}25 fps        lue au manifest",
        f"     {'Géométrie · bits':<{LIBELLE}}1920×1080 · 16 bits",
    ],
    etat="2 lots comptés sur 5 · plan-04_25 : 124 frames sur 124, 2 reconstructions",
    raccourcis="⏎ choisir  ↑↓ naviguer  Tab reconstruction  Échap ateliers  F1 aide",
))

# **`E4-2` -- la colonne de FAMILLE disparait** (`EPIC11-ARB-187`). C'etait la
# derniere chose que cet ecran affichait sans qu'elle apprenne quoi que ce
# soit : un profil d'un cote, six de l'autre, dans deux mots anglais. Ce qui
# reste est ce sur quoi on choisit vraiment -- l'identifiant, le conteneur, et
# la mention `defaut` sur celui que le coeur retient sans qu'on lui demande.
#
# **Et le champ de cadence prend son nom definitif** : « Cadence du rushe
# source » (`EPIC11-ARB-192`, libelle d'Egan verbatim, « rushe » compris). Le
# nom fait le travail que trois lignes d'avertissement faisaient mal : il dit
# que le champ DECLARE la cadence du rushe d'origine, et qu'il ne choisit
# aucune cadence de sortie. La valeur affichee est celle que le lot porte --
# c'est le cas nominal, et un cas nominal ne s'avertit pas.
ecrire("E4-2-exports-reglages.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Exports",
    bandeau_droite=f"{LOT_25} · 124 f",
    centre=[
        "",
        "  Réglages d'encodage",
        "",
        f"     {'Profil':<{LIBELLE}}{'prores_hq':<19}▾  .mov",
        *liste_deroulee_des_profils(),
        "",
        f"     {'Résolution':<{LIBELLE}}{'hd1080':<8}{GLOSE_RESOLUTION}",
        f"     {'Cadence du rushe source':<{LIBELLE}}{'25 fps':<8}déclarée par le lot",
        f"     {'Espace couleur':<{LIBELLE}}{COLORIMETRIE:<8}porté par le profil",
    ],
    etat="prores_hq · .mov · 1920×1080 à 25 fps — 124 échantillons, ~ 1,4 Go",
    raccourcis="⏎ retenir  Tab champ suivant  ↑↓ choisir  Échap retour  F1 aide",
))

# **`E4-2b` change de NATURE une SECONDE fois, et c'est `EPIC11-ARB-192` qui le
# commande.** La passe du 2026-09-02 l'avait deja retourne -- d'« ecran cible »
# a « quand le papier ment sur la cadence ». Egan a mesure que cet ecran-la
# n'existait pas non plus, et il a raison :
#
# > « Je ne comprends pas : le papier ne ment pas sur la cadence. Le lot 12p5 a
# > probablement ete extrait a partir d'un rushe 25p. On reconstruit le rushe
# > 25p a partir des images en 12p5 en tenant les images 2 frames. Cet ecran
# > presente comme une erreur un comportement normal non ? »
#
# La chaine, mesuree : rushe 25 fps, 125 images, 5,000 s ; extraction a
# `fps_target = 12,5` -> **63 frames**, qui portent leur timecode dans la base
# du RUSHE (`timecode_base = "source"`, `timecode_base_fps = 25`). A
# l'encodage, chaque frame est tenue `index(tc[n+1]) - index(tc[n])` fois, soit
# **2** -- 125 echantillons, 5,000 s, **duree conservee exactement**. C'est le
# NOMINAL, et l'ecran y posait un ▲ orange.
#
# Ce qui reste a dessiner est donc l'autre cas, celui que la planche disait
# elle-meme n'avoir pas dessine : **le lot qui ne porte AUCUNE cadence de
# rushe** (payload 2.0, ne avant que la planche ne l'imprime). Le coeur refuse
# alors par `ENCODE_SOURCE_RATE_MISSING`, et ce champ est le seul endroit d'ou
# la declaration peut venir. L'avertissement est orange parce qu'il AVERTIT --
# la teinte suit ce que le message fait --, et il est colorise ENTIEREMENT, ses
# deux lignes etant un seul objet (`EPIC11-ARB-71`).
#
# `Ctrl+R cadence du lot` part **parce que le lot n'en porte pas** : annoncer
# un raccourci qui ne peut rien remettre est la meme faute que le
# `--nouvelle-version` du refus de coeur, en plus petit. La correction
# d'`EPIC11-ARB-68` qui l'avait fait naitre (une lettre nue n'est pas un
# raccourci sur un ecran a champ de saisie) tient toujours : il ne reste aucune
# lettre nue sur les huit ecrans.
ecrire("E4-2b-exports-cadence-modifiee.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Exports",
    bandeau_droite=f"{LOT_12P5} · 63 f",
    centre=[
        "",
        "  Réglages d'encodage",
        "",
        f"     {'Profil':<{LIBELLE}}{'prores_hq':<19}▾  .mov",
        f"     {'Résolution':<{LIBELLE}}{'hd1080':<8}{GLOSE_RESOLUTION}",
        f"     {'Cadence du rushe source':<{LIBELLE - 2}}> {'25':<8}le lot n'en déclare aucune",
        f"     {'Espace couleur':<{LIBELLE}}{COLORIMETRIE:<8}porté par le profil",
        "",
        "     ▲ Ce lot vient d'une planche 2.0, qui n'imprimait pas la cadence",
        "       du rushe. Sans cette déclaration, l'encodage n'a rien à muxer.",
    ],
    etat="plan-04_12p5 · 63 frames · maintiens de 2 · 125 échantillons · 5 s 00",
    raccourcis="⏎ retenir  Tab champ suivant  Échap retour  F1 aide",
), hauteurs_de_message={"Ce lot vient d'une planche 2.0": 2})

# **`E4-3` : le cartouche est derive de `encode.render_summary`**, famille de
# valeur par famille de valeur -- c'est ce que l'AC 7.1 exige, et c'est ce qui
# fait tomber le champ « Nom du master » editable : le recapitulatif du coeur
# porte une SORTIE, pas un nom modifiable. Egan l'a confirme le 2026-09-03 :
# « On affiche le nom du master. Il n'est pas modifiable. »
#
# **`Mires` fusionne avec `Frames`** (Egan, 2026-09-03 : « `Mires` est redondant
# avec `frames` : si c'est complet on n'a pas de mires, si c'est incomplet on a
# des mires. Lecture sur la meme ligne. ») C'est du dessin, pas un arbitrage --
# les deux lignes disaient la meme chose deux fois, et separement.
#
# **La RECONSTRUCTION entre au recapitulatif** (`EPIC11-ARB-190`) : ce qui
# s'encode n'est pas un lot mais une passe de reconstruction datee, et un
# recapitulatif d'avant-ecriture qui ne la nomme pas laisse choisir a l'aveugle
# entre deux versions du meme lot.
#
# Deux corrections de forme de la passe precedente, et elles tiennent :
# * les `( )` disparaissent -- `panneau.ChoixExclusif.rendu()` ne pose que la
#   fleche (`EPIC11-ARB-45`, `-126`), les cases etant reservees aux listes a
#   cocher. `EPIC11-ARB-180` ne rouvre PAS ce cas : une liste d'issues n'a
#   aucune selection persistante a marquer ;
# * le curseur quitte `Encoder` -- `ChoixExclusif.__post_init__` le DEPLACE au
#   montage hors de toute issue qui ecrit (`EPIC11-ARB-7`, `panneau.py:187`).
#   L'etat dessine est donc celui d'ARRIVEE, pas un instant posterieur.
ecrire("E4-3-exports-confirmation.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Exports",
    bandeau_droite=f"{LOT_25} · 124 f",
    centre=[
        "",
        *cartouche("À écrire", [
            f"Master                 {master(LOT_25)}",
            "Lot                    plan-04_25 · état reconstruction",
            "Reconstruction         v2 · 8 planches scannées le 02/09",
            "Profil                 prores_hq → .mov · bt709",
            "Résolution             1920 × 1080          source 1920 × 1080",
            "Cadence du rushe       25 im/s     124 échantillons · 124 frames",
            "Frames · mires         124 conformes sur 124 · 0 mire   ● complet",
            "Timecode de départ     00:00:04:12",
            "Poids attendu          ~ 1,4 Go                    (majorant)",
            "Destination            projet_demo/outputs/",
        ]),
        "",
        "      Encoder",
        "    ▸ Modifier les réglages",
        "      Annuler",
    ],
    etat="124 frames · ~ 1,4 Go — rien n'a encore été écrit",
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
))

# ECRAN NEUF le 2026-09-02 -- **son absence etait un defaut d'arbitrage.**
# `EPIC11-ARB-89` : « toujours proposer un versionnage [...] Mais toujours
# permettre une reecriture plutot qu'un blocage sec. » Les six maquettes `E4-*`
# n'en portaient AUCUN, alors que le coeur refuse deja par
# `ENCODE_MASTER_ALREADY_PRESENT` -- et que son refus nomme `--nouvelle-version`,
# **une option qui n'existe pas**. Cet ecran habille les issues que le lot B0 de
# la story branche ; il n'en invente aucune.
#
# **`EPIC11-ARB-188` (2026-09-03) tranche les trois points qui restaient
# ouverts, et l'un d'eux RETIRE du texte** :
#
# * **trois issues**, comme dessine. Pas de quatrieme issue de suppression : le
#   menu Projet la sert, avec sa propre confirmation ;
# * **curseur sur `Annuler`** (Egan : « Ok sur annuler ») -- la seule issue qui
#   n'ecrit rien, lecture stricte d'`EPIC11-ARB-7`. Ca tranche du meme coup
#   l'incoherence signalee entre les trois ecrans de conflit du produit ;
# * **le message « si ce master a deja ete livre, ne l'ecrasez pas » PART.**
#   Egan : « On propose juste d'ecraser avec l'avertissement de ce qui sera
#   supprime ou de versionner. » Ce qui le remplace annonce ce qui sera
#   DETRUIT -- un fait, verifiable a l'octet pres -- et cesse de conseiller un
#   usage que l'ecran ne peut pas connaitre.
#
# L'avertissement reste colorise ENTIEREMENT, ses deux lignes etant un seul
# objet (`EPIC11-ARB-71`), et en orange parce qu'il avertit.
ecrire("E4-3b-exports-master-existe.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Exports",
    bandeau_droite="master présent · rang 2 libre",
    centre=[
        "",
        *cartouche("Ce master existe déjà", [
            f"▲ {master(LOT_25)}",
            "Lot                plan-04_25           aucun rang encore posé",
            "Écrit le           26/08 à 16:22",
            "Contient           124 échantillons · 25 fps · 4 s 96 · 1,38 Go",
            "Profil · cible     prores_hq · 1920×1080     la même clé qu'ici",
            "",
            "▲ Remplacer efface les 1,38 Go écrits le 26/08, et le rapport",
            "  ffprobe qui les accompagne. Rien d'autre n'est touché.",
        ]),
        "",
        "      Créer la v2",
        f"        · écrit {master(LOT_25, rang=2)}, sans rien effacer",
        "      Remplacer ce master",
        "        ▲ efface les 1,38 Go écrits le 26/08",
        "    ▸ Annuler",
    ],
    etat="▲  1,38 Go écrits le 26/08 · le prochain rang est 2 · rien n'est effacé",
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
), hauteurs_de_message={"Remplacer efface les 1,38 Go": 2})

# **`E4-4b` -- la PRE-VERIFICATION, et elle ne se dessine PLUS comme un ecran
# chiffre** (`EPIC11-ARB-184`, tranche par Egan le 2026-09-03). C'est une
# quatrieme issue qu'il a ecrite contre les trois proposees : « Livrer avec un
# rotor mais preparer une story de progression dans l'epic approprie qui pourra
# etre lancee en parallele et recablee en temps voulu. »
#
# La mesure qui rendait la barre tentante tient toujours -- `deferred-work.md` :
# `ensure_uniform_frame_shapes` (`codec_profiles.py:1054`) sonde une frame a la
# fois, en serie, **76 ms par frame**, soit « environ 76 minutes de
# pre-verification pour 1 h de master a 25 im/s ». Cette phase EST comptable.
# Mais le canal qui la compterait est la story 6.7, et cet atelier se livre
# avant elle : dessiner la barre ici la ferait passer pour livree.
#
# **La forme FUTURE du raccord est preparee sans etre dessinee comme livree**,
# et c'est Egan qui l'a precisee : « pendant la preverification la barre
# progresse de 0 a 100 avec la mention etape 1 au-dessus ; pendant l'encodage
# la barre repartirait a 0 avec la mention etape 2 ; pendant la verification du
# master on laisse juste le glyphe ; l'etape 4 n'a pas de temps de chargement. »
# Ce que l'ecran porte donc DES AUJOURD'HUI est la mention **`etape 1 sur 4`**
# -- un fait sur ou l'on en est, pas un compte d'avancement --, a la place
# exacte ou la barre viendra. Le jour ou la 6.7 se raccorde, la barre s'ajoute
# au-dessous de cette mention sans qu'aucune autre ligne bouge.
ecrire("E4-4b-exports-preverification.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Exports",
    bandeau_droite=f"{LOT_25} · 124 f",
    centre=[
        "",
        "  Pré-vérification des frames",
        "",
        f"     {jetons.rotor(0)} Pré-vérification    {'124 frames à ouvrir':<30}en cours",
        f"     · Encodage            {master(LOT_25):<30}en attente",
        "     · Vérification        ffprobe sur le fichier écrit  en attente",
        "     · Bascule             vers projet_demo/outputs/     en attente",
    ],
    etat="Étape 1 sur 4 · lecture des 124 frames",
    raccourcis="Échap interrompre  F1 aide",
))

# **`E4-4` -- l'ENCODAGE, et il ne sait PAS compter.** Le chiffre
# `64 %  79/124 frames  reste ~ 22 s` de la maquette d'origine n'existe pas et
# les cinq lignes de journal `frame 000079 encodee` etaient fabriquees : rien
# n'emet une ligne par frame, et `run_encode` fait un unique `subprocess.run`
# bloquant. Ce qui le remplace est le ROTOR (`jetons.rotor`), pour la raison
# exacte que `DESIGN.md` §9 nomme depuis le 2026-09-02 : l'interdit porte sur
# l'animation qui remplace un COMPTE REEL, et il n'y en a aucun a remplacer.
#
# **La ligne d'etat PERD « aucun compte n'est emis »** (`EPIC11-ARB-189`, Egan
# le 2026-09-03 : « On enleve cette information de tuyauterie »). Elle disait
# vrai, et c'est justement ce qui la rendait inutile : elle parlait de la
# MACHINE la ou cette ligne porte une mesure du TRAVAIL. Ce qui la remplace est
# le seul compte reellement disponible -- les echantillons a monter et le poids
# attendu --, plus la mention d'etape qui prepare le raccord de la story 6.7.
#
# Le journal part aussi, et pour la meme mesure : entre le recapitulatif emis
# AVANT (`render_summary`) et le rapport `ffprobe` emis APRES, le chemin
# d'encodage n'ecrit **rien**. Annoncer `Tab journal` ouvrirait une page vide.
ecrire("E4-4-exports-execution.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Exports",
    bandeau_droite=f"{LOT_25} · 124 f",
    centre=[
        "",
        "  Encodage en cours",
        "",
        f"     ● Pré-vérification    {'124 frames sur 124':<30}conforme",
        f"     {jetons.rotor(0)} Encodage            {master(LOT_25):<30}en cours",
        "     · Vérification        ffprobe sur le fichier écrit  en attente",
        "     · Bascule             vers projet_demo/outputs/     en attente",
    ],
    etat="Étape 2 sur 4 · encodage des 124 échantillons · env. 1,4 Go attendus",
    raccourcis="Échap interrompre  F1 aide",
))

# `E4-5` : le panneau porte ce que `EncodeOutcome` et
# `io.encode_manifest.PersistedEncode` rendent, jamais un recalcul (AC 10.1) --
# dont `state_written`, l'etat que la declaration au manifest a pose.
#
# `Tab journal` **reste** ici alors qu'il part de `E4-4`, et ce n'est pas une
# incoherence : il y a quelque chose a lire APRES l'encodage -- le rapport de
# `video_metadata.verify_technical_metadata`, champ a champ -- la ou il n'y
# avait rien PENDANT. `EPIC11-ARB-189` precise ce que ce journal EST : la
# sortie de ffmpeg, gardee **en memoire**, montree puis perdue. Egan a ecarte
# l'ecriture sur disque ; l'ecran ne promet donc aucun fichier de journal, et
# la ligne de raccourcis ne nomme qu'une lecture.
#
# **La RECONSTRUCTION est rappelee ici** (`EPIC11-ARB-190`) : c'est la seule
# facon de savoir, en relisant un master six mois plus tard, de quelle passe de
# reconstruction il sort.
ecrire("E4-5-exports-resultat.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Exports",
    bandeau_droite=f"{LOT_25} · 124 f",
    centre=[
        "",
        *cartouche("Écrit", [
            f"● {master(LOT_25)}",
            "",
            "Taille                  1,38 Go",
            "Durée                   4 s 96 · 124 échantillons · 25 fps",
            "Timecode de départ      00:00:04:12",
            "Emplacement             projet_demo/outputs/",
            "Reconstruction          v2 · 8 planches scannées le 02/09",
            "État du lot             encode        déclaré au manifest",
            "Durée d'encodage        1 min 04",
        ]),
        "",
        "   ▸ Ouvrir le dossier",
        "     Ouvrir le fichier",
        "     Encoder un autre lot",
        "     Retour aux ateliers",
    ],
    etat="●  1,38 Go écrits · métadonnées vérifiées par ffprobe · aucun refus",
    raccourcis="⏎ choisir  ↑↓ naviguer  Tab journal  Échap ateliers  F1 aide",
))

# -------------------------------------------------------------------- Pdf ----

# ============================================================================
# LA GEOMETRIE EST **MESUREE**, jamais recopiee -- et elle a ete fausse deux
# fois avant cette passe.
#
# Ce bloc lit `page_templates` au moment ou il dessine : `frame_zones_mm` (la
# source que la composition passe au rendu) puis `frame_image_rect_mm`, qui rend
# le plus grand 16:9 inscrit -- c'est-a-dire EXACTEMENT la surface de dessin,
# celle que le scan recalcule ensuite depuis le QR.
#
# **Le defaut paye deux fois** : une premiere table melangeait deux geometries
# (`portrait 6f` venait de la v1, gelee, pendant que `portrait 8f` venait de la
# v2, courante). `portrait 6f` **n'existe pas en v2** -- le vocabulaire v2 est
# `1 · 2 · 3 · 4 · 8` en portrait et `1 · 2 · 4 · 6 · 8` en paysage. Une table
# ecrite a la main ne peut pas se tromper autrement ; une table calculee ne peut
# pas se tromper du tout.
#
# `EPIC11-ARB-154` (Egan, 2026-09-01) -- **la liste proposee PAR DEFAUT est
# celle des non dominees, et les dominees restent atteignables.** Une
# combinaison est dominee quand une autre rend au moins autant de surface pour
# au plus autant de pages. La mesure qui autorise le classement : les DIX zones
# v2 portent exactement le meme rapport de forme (1,7778, ecart 0,0), donc un
# rush qui n'est pas en 16:9 est encadre par le **meme** facteur partout et le
# classement ne bouge pas. C'est verifie ici, a la generation.
#
# **Et le coeur dit deja que le retrait ne marche pas.** Le commentaire de
# `_RETIRED_CARDINALS` a mesure la cascade : retirer les cardinaux domines du
# portrait ferait tomber son vocabulaire a `2, 3, 8` -- « exactement l'issue
# qu'EPIC5-ARB-64 ecarte ». Or `2, 3, 8` est precisement le front des non
# dominees en portrait, calcule ici par un tout autre chemin. Les deux mesures
# se rejoignent, et elles disent la meme chose : **on guide, on n'interdit
# pas**. `ARB-154` est donc la forme TUI d'un arbitrage que le coeur avait deja
# tranche dans l'autre sens pour son vocabulaire.
# ============================================================================

#: Les deux lots coches de `E5-1`, **separement**. Le cardinal de la passe est
#: leur somme, mais les PAGES ne se comptent pas sur cette somme : chaque lot
#: ouvre sa propre page (`pdf_composition.page_count_du_lot` pagine un lot, et
#: la passe additionne). La difference n'est pas theorique -- a 3 f/page,
#: `ceil(164/3)` rend 55 pages quand la passe en imprime 42 + 14 = **56**.
FRAMES_PAR_LOT_DEMO = (124, 40)
FRAMES_DEMO = sum(FRAMES_PAR_LOT_DEMO)  # 164


def pages_du_lot(frames: int, cardinal: int) -> int:
    """`ceil(frames / cardinal)` -- la pagination d'UN lot."""
    return -(-frames // cardinal)


def pages_de_la_passe(cardinal: int) -> int:
    """Les pages de la passe : la SOMME des pages de chaque lot, jamais la
    pagination du cardinal total.

    Defaut corrige le 2026-09-01 (lot V5-A) : `-(-FRAMES_DEMO // cardinal)`
    rendait 55 pages a 3 f/page la ou la passe en imprime 56, parce qu'il
    autorisait une page a porter des frames de DEUX lots. Le classement des
    dominations n'en bougeait pas, mais un chiffre affiche a l'operateur ne se
    verifie pas par ses consequences.
    """
    return sum(pages_du_lot(frames, cardinal) for frames in FRAMES_PAR_LOT_DEMO)


def _zone_utile(orientation: str, cardinal: int) -> tuple[float, float]:
    """Largeur et hauteur en mm de la surface de dessin d'une frame.

    Lue a `frame_zones_mm` puis a `frame_image_rect_mm`, jamais derivee d'un
    format de page : c'est le couple exact que la composition passe au rendu.
    """
    spec = page_templates.template_for(orientation, cardinal, "0")
    zones = spec.frame_zones_mm
    assert len(zones) == cardinal, (orientation, cardinal, len(zones))
    _, _, largeur, hauteur = page_templates.frame_image_rect_mm(zones[0], 0.0)
    return largeur, hauteur


def _combinaisons() -> dict[tuple[str, int], dict]:
    """Les dix combinaisons v2, mesurees, avec surface, pages et domination."""
    table: dict[tuple[str, int], dict] = {}
    rapports = set()
    for orientation in ("paysage", "portrait"):
        for cardinal in page_templates.frames_per_page_vocabulary(orientation):
            largeur, hauteur = _zone_utile(orientation, cardinal)
            rapports.add(round(largeur / hauteur, 6))
            table[(orientation, cardinal)] = {
                "largeur": largeur,
                "hauteur": hauteur,
                "surface": largeur * hauteur / 100.0,   # cm²
                "pages": pages_de_la_passe(cardinal),
                "gabarit": page_templates.build_template_id(
                    orientation, cardinal, "0"),
            }
    # La mesure qui autorise `EPIC11-ARB-154` : un seul rapport de forme.
    assert len(rapports) == 1, f"les zones v2 ne portent plus un rapport unique : {rapports}"
    for cle, fait in table.items():
        dominants = [
            autre for autre_cle, autre in table.items()
            if autre_cle != cle
            and autre["surface"] >= fait["surface"] and autre["pages"] <= fait["pages"]
            and (autre["surface"] > fait["surface"] or autre["pages"] < fait["pages"])
        ]
        fait["dominants"] = dominants
        fait["dominee"] = bool(dominants)
    return table


COMBINAISONS = _combinaisons()


def cardinaux_offerts(orientation: str) -> tuple[int, ...]:
    """**Le vocabulaire ENTIER de l'orientation, dans son ordre**, et une seule
    liste -- `EPIC11-ARB-173` (Egan, note 2 de la relecture v5 : « une seule
    liste »).

    Le rang de domination ne SEPARE plus rien : il se lit sur la ligne, au
    glyphe. `EPIC11-ARB-154` tient a l'identique -- aucun cardinal n'est retire,
    on guide, on n'interdit pas -- et c'est la meme mesure qui le dit, prise au
    meme endroit.
    """
    return page_templates.frames_per_page_vocabulary(orientation)


def verdict(orientation: str, cardinal: int) -> tuple[str, str] | None:
    """Le conseil de la note 11 d'Egan : **un seul**, et le plus optimal.

    Forme imposee, verbatim : « x frames - [orientation] est plus optimal :
    [motif] ». Le motif se CALCULE -- « surface de dessin superieure » quand le
    nombre de pages ne change pas, « ... et gain de pages » quand il baisse --,
    il n'est pas une chaine fixe. C'est ce que la mesure permet de montrer :
    des deux ecrans de reglages, l'un rend chacune des deux formes.

    Rend ``None`` quand la combinaison courante n'est dominee par personne : il
    n'y a alors **rien** a conseiller, et un ecran qui conseillerait quand meme
    serait un ecran qui meuble. Egan : « on affiche UNIQUEMENT le conseil le
    plus optimal ».
    """
    fait = COMBINAISONS[(orientation, cardinal)]
    if not fait["dominants"]:
        return None
    # « Le plus optimal » : la plus grande surface, et a surface egale le moins
    # de pages. Un seul est rendu, jamais une liste.
    meilleur_cle, meilleur = max(
        ((cle, val) for cle, val in COMBINAISONS.items() if val in fait["dominants"]),
        key=lambda item: (item[1]["surface"], -item[1]["pages"]),
    )
    motif = "surface de dessin supérieure"
    if meilleur["pages"] < fait["pages"]:
        motif += " et gain de pages"
    tete = (f"▲ {meilleur_cle[1]} frames {meilleur_cle[0]} est plus optimal :")
    mesure = (f"{meilleur['surface']:.1f}".replace(".", ",")
              + f" cm² · {meilleur['pages']} pages")
    return tete, f"{motif}#{mesure}"


def ligne_verdict(orientation: str, cardinal: int) -> list[str]:
    """Les deux lignes du verdict, la mesure calee a droite de la grille."""
    rendu = verdict(orientation, cardinal)
    if rendu is None:
        return []
    tete, corps = rendu
    motif, mesure = corps.split("#")
    creux = 76 - 7 - len(motif) - len(mesure)
    return [f"     {tete}", f"       {motif}{' ' * creux}{mesure}"]


def mm(orientation: str, cardinal: int) -> str:
    fait = COMBINAISONS[(orientation, cardinal)]
    return (f"{fait['largeur']:.1f} × {fait['hauteur']:.1f} mm"
            .replace(".", ","))


def cm2(orientation: str, cardinal: int) -> str:
    return f"{COMBINAISONS[(orientation, cardinal)]['surface']:.1f} cm²".replace(".", ",")


#: **Le marqueur des non dominees EST le glyphe `complete`, et ce n'est pas un
#: choix esthetique** (`EPIC11-ARB-173`, notes 2 et 4 d'Egan : « les choix
#: optimises en vert + asterisque pour la lecture monochrome », puis « juste le
#: code couleur + glyphe »).
#:
#: `DESIGN.md` section 6 : `●` vaut `state-complete` -- le VERT -- et son repli
#: ASCII est `*` -- l'ASTERISQUE. Les deux canaux qu'Egan demande sont donc le
#: MEME jeton, deja dans la table, deja replie. Ecrire un `*` litteral en UTF-8
#: aurait fait deux fautes d'un coup : un glyphe hors table (interdit section 6)
#: et une collision avec le repli de `●` en mode ASCII.
MARQUE_NON_DOMINEE = jetons.GLYPHES["complete"]

#: La legende, que la note 2 demande explicitement. Elle porte le glyphe
#: elle-meme, donc elle se replie avec lui : `●` en UTF-8, `*` en ASCII. Elle
#: n'a pas a nommer les deux dessins -- elle EST l'un ou l'autre.
#:
#: **Trois mots, et c'est tout** (Egan, 2026-09-02, verbatim : « La legende :
#: **choix optimal** (c'est tout). »). Elle disait « non dominé : aucune autre
#: ne fait mieux en surface ET en pages » -- la DEFINITION de la mesure, pas ce
#: que le glyphe veut dire pour celui qui choisit. Les deux criteres restent
#: sous les yeux, chiffres, sur chaque ligne de la liste : la legende n'a pas a
#: les redire.
LEGENDE_NON_DOMINEE = f"     {MARQUE_NON_DOMINEE} choix optimal"


def ligne_de_cardinal(orientation: str, cardinal: int, retenu: int,
                      curseur: bool = False) -> str:
    """Une ENTREE de la liste unique des mises en page.

    Elle porte les deux criteres de la domination cote a cote -- surface par
    frame et pages -- pour que le glyphe de tete de colonne droite se LISE au
    lieu de se croire : un operateur qui voit `311,5 cm² · 164 pages` en face de
    `43,9 cm² · 28 pages` n'a pas besoin qu'on lui dise laquelle domine l'autre.

    **Le glyphe est colle au CHIFFRE, jamais cale a droite** (Egan, 2026-09-02,
    verbatim : « une **asterisque** (directement a cote du chiffre du nombre de
    frames) **et** la couleur. **Pas une pastille tout a droite.** »). Une
    pastille en bout de ligne demande a l'oeil de traverser quatre colonnes de
    chiffres pour revenir au cardinal qu'elle qualifie ; collee au chiffre, elle
    qualifie ce qu'elle touche.
    Le glyphe reste `●` -- donc `*` en repli ASCII -- et c'est ce qui accorde
    l'asterisque demandee a la table plutot que de la doubler : `DESIGN.md` §6
    fait deja de `*` le repli de `●`, si bien qu'un `*` litteral aurait ete un
    glyphe hors table ET une collision avec ce repli.

    **Consequence a cabler au developpement, et elle est nommee ici parce que
    la maquette ne peut pas la porter seule** : colle au chiffre, le glyphe
    n'ouvre plus de colonne, donc `jetons.jeton_d_etat` ne le voit plus. La
    ligne prend sa couleur par l'etat DONNE (`jetons.peindre(etats=...)`,
    `EPIC11-ARB-71`), exactement comme la maquette la declare. C'est le chemin
    que le produit possede deja ; ce n'en est pas un neuf.
    """
    fait = COMBINAISONS[(orientation, cardinal)]
    tete = f"   {jetons.GLYPHES['curseur']} " if curseur else "     "
    puce = jetons.GLYPHES[
        "exclusif-retenu" if cardinal == retenu else "exclusif-libre"]
    dims = (f"{fait['largeur']:5.1f} × {fait['hauteur']:5.1f} mm"
            .replace(".", ","))
    surface = f"{fait['surface']:5.1f}".replace(".", ",") + " cm²"
    pages = f"{fait['pages']:3d} pages"
    marque = MARQUE_NON_DOMINEE if not fait["dominee"] else " "
    return f"{tete}{puce} {cardinal}{marque}   {dims}   {surface}   {pages}"


def liste_de_cardinaux(orientation: str, retenu: int,
                       curseur: int | None = None) -> list[str]:
    """La liste UNIQUE, dans l'ordre du vocabulaire -- `EPIC11-ARB-173`."""
    return [ligne_de_cardinal(orientation, c, retenu, curseur == c)
            for c in cardinaux_offerts(orientation)]


def messages_de_reglages(orientation: str) -> dict[str, int]:
    """Les lignes d'etat que ces deux ecrans DECLARENT, et pourquoi il le faut.

    Le glyphe de choix optimal est colle au chiffre depuis le retour du
    2026-09-02 : il n'ouvre donc plus de colonne, et ni `jetons.jeton_d_etat` ni
    le colorisateur ne peuvent plus le VOIR. C'est le regime normal d'un etat
    connu du seul ecran, et le produit le sert par `jetons.peindre(etats=...)`
    (`EPIC11-ARB-71`) ; la maquette le declare de la meme facon, sans quoi elle
    dessinerait une couleur que le produit ne saurait pas poser.

    Les fragments sont **derives de la mesure**, jamais ecrits : ce sont les
    combinaisons non dominees de l'orientation, celles-la memes qui portent le
    glyphe. Une liste ecrite a la main divergerait au premier gabarit qui
    change.
    """
    messages = {f"{cardinal}{MARQUE_NON_DOMINEE}": 1
                for cardinal in cardinaux_offerts(orientation)
                if not COMBINAISONS[(orientation, cardinal)]["dominee"]}
    return messages


def ligne_valider(focus: bool) -> str:
    """Le bouton **Valider**, dernier champ du formulaire.

    `EPIC11-ARB-173`, note 3 d'Egan verbatim : « Enter vaut donc selectionner ».
    Des lors `⏎` ne peut plus valider le formulaire depuis un champ -- il y
    retient une valeur --, et il faut un endroit ou `⏎` VALIDE. C'est ce bouton,
    atteint par `Tab` comme n'importe quel autre champ.

    Il se dessine comme un champ : rien a gauche, la valeur a la colonne des
    valeurs, et le glyphe `>` quand il a le focus (`DESIGN.md` section 7.3).
    Aucun dessin de bouton n'est invente -- la table de glyphes est close.

    **La seconde colonne part** (Egan, 2026-09-02 : « enlever la deuxieme
    colonne "compose les planches ..." a cote de valider »). Elle disait ce que
    fait un bouton nomme `Valider` sur un ecran nomme « Reglages des planches »,
    et `DESIGN.md` §7.3 l'interdit d'ailleurs deja en toutes lettres : « pas de
    seconde colonne, jamais ». Une glose qui repete le libelle qu'elle jouxte
    n'ajoute rien et coute une colonne a tout le monde.
    """
    tete = "                        > " if focus else "                          "
    return f"{tete}Valider"


# `P1` -- le nom du PDF etait INVENTE. `projet_demo_lot_25fps_8f.pdf` ne sort
# d'aucun chemin du produit : `io.naming.build_sheets_pdf_filename` compose
# `<projet-court>_<lot_id>_planches.pdf` (`EPIC4-ARB-3`, cardinal retire du nom
# par `EPIC7-ARB-91`). Le cardinal `8f` vit dans le gabarit, pas dans le nom.
# `P2` -- le rang de tirage n'apparaissait nulle part (`EPIC11-ARB-91`).
# `P3` -- `v2-paysage-8f` n'est pas un identifiant de gabarit du depot :
# `page_templates.build_template_id` rend `tpl-a4-paysage-8f-v2`, et le `v2`
# final est la VERSION DE GEOMETRIE, pas un rang de tirage.
#
# `N1` (note 1 de la relecture v3) -- `hauteur_du_curseur` declare combien de
# lignes l'entree du curseur occupe (`EPIC11-ARB-125`). Sans declaration, le
# colorisateur retombe sur le repli par MOTIF, qui ne trouve qu'un rang.
ecrire("E5-0-pdf-menu.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf",
    bandeau_droite="5 lots · 3 tirages produits",
    centre=[
        "",
        "  Atelier Pdf",
        "",
        "   ▸ Composer des planches      Mettre un ou plusieurs lots en pages",
        "                                imprimables. Le parcours principal.",
        "",
        "     Planche de calibration     Générer la mire à imprimer avec les",
        "                                planches, pour calibrer le scanner.",
        "",
        regle(),
        "",
        # **Cet ecran ne figurait pas dans les cinq que le retour du 2026-09-02
        # nomme, et il portait pourtant le mot `planches` dans un nom de
        # fichier.** Il le perd ici comme les cinq autres : le mot disparait du
        # NOM, pas seulement des noms de la passe de demonstration.
        f"     Dernier tirage produit      "
        f"{planches_mep(LOT_25, cardinal=8, rang=3)}",
        "                                 26/08 · 16 pages · tirage 3",
        "                                 tpl-a4-paysage-8f-v2",
    ],
    etat="",
    raccourcis="⏎ entrer  ↑↓ naviguer  Échap ateliers  F1 aide  Q quitter",
), hauteur_du_curseur=2)

# ------------------------------------------------------- E5-1, notes 1 2 3 ---
#
# `N1` (note 1, 2026-09-01 v4) -- « l'espace pour le nom d'un lot est tres
# limite [...] les noms sont bien plus longs dans mes projets ». Deux gestes,
# et le second est celui qu'Egan a nomme :
#
#   1. **le champ de nom se dimensionne sur `CANONICAL_ID_MAX_LENGTH`**, la
#      borne du produit, et non sur la plus longue des valeurs de la
#      demonstration. Une colonne calee sur la demonstration se retrecit des
#      que la demonstration change : c'est exactement la panne constatee ;
#   2. **les faits techniques du lot SURVOLE descendent en bas de l'ecran**,
#      dans un bloc sous filet -- « les infos techniques du lot survole peuvent
#      aller en bas de l'interface ». La forme n'est pas inventee ici : c'est
#      celle de `E4-1` (« Le lot designe »), deja approuvee.
#
# Un cinquieme lot au nom long entre dans la liste pour que la colonne se
# **voie** tenir un cas reel. Il n'est coche nulle part : les ecrans en aval ne
# le rencontrent jamais et la passe de demonstration reste a deux lots.
#
# `N2` (note 2) -- « remets ca dans le pied ». Le compte quitte la zone
# centrale, dont le bas est desormais pris par le survol, et redevient la ligne
# d'etat. C'est aussi ce que `DESIGN.md` §7.2 demande : « le compte des coches
# est toujours rappele ».
#
# `N3` (note 3) -- « Enleve ce chiffre. Ce n'est pas l'objet de cet ecran. » Le
# cardinal des geometries distinctes (« les deux en 1920×1080 ») part. Il etait
# calculable -- la geometrie vit sur le RUSH, `rushes[].resolution_source`, et
# un lot porte `rush_id` --, mais calculable n'est pas pertinent : cet ecran
# choisit des lots, il ne juge pas leur compatibilite.
ecrire("E5-1-pdf-lots.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf",
    bandeau_droite="",
    centre=[
        "",
        "  Quels lots mettre en planches ?",
        "",
        f"   ▸ [x] {LOT_25:<{LARGEUR_NOM}}● complet",
        f"     [ ] {LOT_12P5:<{LARGEUR_NOM}}● complet",
        f"     [x] {LOT_8:<{LARGEUR_NOM}}● complet",
        f"     [ ] {LOT_HIVER:<{LARGEUR_NOM}}● complet",
        f"     [ ] {LOT_LONG:<{LARGEUR_NOM}}● complet",
        "",
        regle("Le lot survolé"),
        "",
        f"     Frames               {FRAMES_PAR_LOT_DEMO[0]}"
        f"              extraites le 26/08",
    ],
    etat=f"2 lots cochés · {FRAMES_DEMO} frames",
    raccourcis="Espace cocher  ⏎ continuer  ↑↓ naviguer  Échap menu Pdf  F1 aide",
))

# ------------------------------- E5-2 / E5-2b, relecture v5, notes 1 a 4 ---
#
# `N2` + `N3` + `EPIC11-ARB-173` -- **UNE seule liste, `⏎` selectionne, et un
# bouton `Valider` en bas.** Egan, verbatim : « une seule liste, les choix
# optimises en vert + asterisque pour la lecture monochrome, avec une legende »,
# puis « Enter vaut donc selectionner ».
#
# **Le deroulant qu'il proposait d'abord est ecarte, et il a lui-meme tranche**
# (« Ok ca me convainc finalement [...] je veux essayer cette forme »). La
# mesure qui fonde le refus, pour qu'elle ne se reperde pas : `tui/jetons`
# ne porte AUCUN glyphe de deroulant et `DESIGN.md` §7.3 ne connait que la
# saisie libre et le choix exclusif `(•)`/`( )`. Le cout n'est pas technique --
# Textual sait ouvrir un panneau flottant -- il est de charte : un deroulant
# RECOUVRE, et toute la TUI est batie sur une grille 80x24 ou rien ne recouvre,
# avec un repli ASCII qui doit rendre la meme information. Il faudrait donc un
# glyphe neuf, une regle de recouvrement, et un equivalent ASCII des trois.
#
# **La liste verticale, elle, ne coute RIEN de neuf, et elle rend le vert
# exprimable.** C'est le point mesure qui a decide la forme : `jetons.peindre`
# peint **par LIGNE**, jamais par fragment de ligne -- ses deux regles portent
# sur « la ligne du curseur » et sur « une ligne qui porte un glyphe d'etat »,
# et `etats` est un `Mapping[int, str]`, un jeton PAR RANG. Le vert d'Egan sur
# quelques puces d'une meme rangee n'etait donc pas exprimable sans changer le
# contrat de peinture. Une entree par ligne le rend exprimable **par la regle
# qui existe deja**, sans une ligne de produit en plus.
#
# `N4` -- « les deux rangees tombent : juste le code couleur + glyphe ». Les
# rangees « proposes d'office » / « et aussi » etaient l'ANCIENNE maniere de
# dire la domination : une separation spatiale. Le glyphe la dit maintenant sur
# la ligne, et `EPIC11-ARB-154` tient sans changer d'un iota -- aucun cardinal
# n'est retire, on guide, on n'interdit pas.
#
# `N1` -- « on enleve compression de gamut ». Retiree des deux ecrans. Ce n'est
# pas seulement une preference : `cli.py` (`--gamut-map`) documente que « la
# compression reelle s'active explicitement: la decompression G^-1 est post-MVP
# (story 5.4b) ». Le seul reglage sur lequel la TUI pouvait poser ce champ
# aujourd'hui est donc son defaut, et un champ dont une seule valeur est sure
# n'est pas un reglage. La ligne libere sert a la liste.
#
# **Ce que le retrait de « Ce qui en decoule » ne perd pas.** La surface de
# dessin et les pages vivent desormais SUR chaque entree de la liste, pour les
# dix mises en page et non pour la seule retenue -- c'est ce qui rend le glyphe
# de domination lisible au lieu d'etre a croire. Le `template_id`, lui, n'a
# jamais ete un reglage : il se lit a la confirmation `E5-3`, qui le porte deja,
# et sur la planche imprimee.
#
# `N11` de la relecture v4 survit intact : « x frames - [orientation] est plus
# optimal : [motif] », un seul conseil, calcule. Il reste **necessaire** malgre
# la liste, et pour un motif precis : le glyphe se calcule sur le PRODUIT des
# deux orientations (`EPIC11-ARB-154`), alors que la liste n'en montre qu'une.
# Une entree peut donc etre sans glyphe a cause d'une combinaison de l'AUTRE
# orientation, que la liste ne montre pas -- le conseil est le seul endroit qui
# la nomme.
#
# **Pourquoi ces deux reglages-la.** `E5-2` montre `paysage 6 f`, la SEULE
# combinaison dont le dominant fasse gagner des pages : c'est donc le seul
# endroit ou la forme longue du motif peut se voir, et c'est mot pour mot
# l'exemple d'Egan. `E5-2b` montre `portrait 4 f`, son second exemple.
#
# **Le focus est reparti entre les deux ecrans, et c'est voulu.** `E5-2` le pose
# sur `Valider` -- le mecanisme neuf de la note 3, qu'il faut voir au moins une
# fois --, `E5-2b` dans la liste -- le mecanisme neuf de la note 2. Chacun rend
# sa ligne de raccourcis contextuelle : `⏎ valider` sur le bouton, `⏎
# selectionner` dans la liste. C'est litteralement la reponse d'Egan mise en
# dessin.
_PAGES_6F = pages_de_la_passe(6)
_PAGES_25_6F = pages_du_lot(124, 6)
_PAGES_8_6F = pages_du_lot(40, 6)

ecrire("E5-2-pdf-reglages.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf",
    bandeau_droite="2 lots · 164 frames",
    centre=[
        "",
        "  Réglages des planches",
        "",
        "     Orientation          (•) paysage      ( ) portrait",
        "     Format · DPI         A4 · 600",
        "     Marge de travail     0            0 · 2 · 5 mm",
        "",
        regle("Frames par page"),
        *liste_de_cardinaux("paysage", 6),
        LEGENDE_NON_DOMINEE,
        *ligne_verdict("paysage", 6),
        ligne_valider(focus=True),
    ],
    etat=f"{_PAGES_6F} pages — {LOT_25} {_PAGES_25_6F} · {LOT_8} {_PAGES_8_6F}"
         f" · 164 frames sur {_PAGES_6F * 6} emplacements",
    raccourcis="⏎ valider  Tab champ  ↑↓ naviguer  Échap retour  F1 aide",
), hauteurs_de_message={**messages_de_reglages("paysage"),
                        "est plus optimal": 2})

# `E5-2b` -- **le focus est DANS la liste**, sur l'entree que le produit a
# imposee : une valeur a ete changee sans que l'operateur la choisisse, et le
# focus va la ou la correction se fait.
#
# **`⏎` SORT du choix** (Egan, 2026-09-02, verbatim : « appuyer sur Entree
# "saute" ensuite en dehors du choix pour valider »). La contrainte de la note 3
# de la v5 tenait -- `⏎` ne valide plus le formulaire depuis un champ -- mais
# elle laissait `Tab` seul chemin vers le bouton, et Egan corrige : `⏎` retient
# la valeur PUIS pose le curseur sur `Valider`. C'est `E5-2` qui montre l'etat
# d'arrivee de ce saut, curseur sur le bouton ; cette ligne-ci en nomme la
# destination, comme `EPIC11-ARB-68` l'exige de `Tab`.
# `↑↓ choisir` remplace `↑↓ naviguer` pour une raison de grille et non de sens :
# la ligne repliee en ASCII fait alors exactement 76 colonnes, la zone utile.
# `Tab champ` reste : la touche n'est pas inerte, elle mene aux trois champs du
# haut, et annoncer une touche qui existe n'a jamais ete le defaut -- annoncer
# celle qui n'existe pas l'est.
#
# **LE REPLI MONTE, ET IL ETAIT DESSINE FAUX** (`EPIC11-ARB-179`, Egan le
# 2026-09-02 : « On economise le papier »). Cet ecran montrait un repli de `6`
# vers `4`. Le seul repli paysage -> portrait du depot est `6 -> 8` : `6` est
# le SEUL cardinal du vocabulaire paysage absent du portrait, et la regle
# tranchee fait monter au cardinal offert immediatement superieur. Descendre a
# `4` depensait 15 feuilles de plus (31 contre 16 sur un lot de 124) pour
# +5 % de surface par frame -- l'inverse exact de ce qu'Egan a tranche.
#
# **Le coeur disait deja la meme chose**, et c'est ce qui rend la correction
# sure plutot que seulement obeissante : le message de
# `page_templates.retired_cardinal_reason("v2", 6, "portrait")` nomme lui-meme
# son remplacant -- « Utiliser 8 pour la meme surface par frame sur moins de
# papier ».
#
# **CE QUE LA CORRECTION COUTE A CET ECRAN, dit plutot que tu** : `8` porte le
# glyphe de choix optimal, donc `ligne_verdict` ne rend plus rien et la
# demonstration « une entree SANS glyphe a cause de l'autre orientation »
# quitte cet ecran. Elle n'est pas perdue pour autant -- `E5-2` la porte
# entiere : `paysage 6 f` y est retenu, sans glyphe, sous le conseil
# « ▲ 8 frames portrait est plus optimal ». La planche la montrait deux fois ;
# elle la montre une fois, sur l'ecran ou elle est vraie.
#
# **LA LIGNE D'ETAT GARDE SA FORME VALIDEE, et ma reecriture est RETIREE**
# (Egan, 2026-09-02, verbatim : « Non, on laisse la ligne du bas avec les
# infos. Pas besoin de nouvelle validation pour ca. »). J'avais propose qu'elle
# annonce « cardinal demande, retenu, motif » -- refuse. `EPIC11-ARB-56`, qu'il
# a lui-meme pose, veut de la ligne d'etat des CONSTATS et non des explications
# de mecanisme, et « retenu 8 : moins de papier » en etait une.
#
# **La seule chose qu'`EPIC11-ARB-179` change dans cette ligne est un chiffre**,
# et une clause tombe avec lui : la forme validee disait « meme surface qu'a
# 8 f, ramene a 4 » -- elle nommait `8` pour justifier une descente vers `4`.
# Le repli montant retient `8`, donc la clause et le cardinal retenu se
# confondent, et la garder ecrirait deux fois le meme chiffre dans la meme
# phrase. Il reste le constat, mot pour mot celui de la maquette validee.
ecrire("E5-2b-pdf-cardinal-refiltre.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf",
    bandeau_droite="2 lots · 164 frames",
    centre=[
        "",
        "  Réglages des planches",
        "",
        "     Orientation          ( ) paysage      (•) portrait",
        "     Format · DPI         A4 · 600",
        "     Marge de travail     0            0 · 2 · 5 mm",
        "",
        regle("Frames par page"),
        *liste_de_cardinaux("portrait", 8, curseur=8),
        LEGENDE_NON_DOMINEE,
        *ligne_verdict("portrait", 8),
        ligne_valider(focus=False),
    ],
    etat="▲  6 f/page n'existe pas en portrait — ramené à 8",
    raccourcis="⏎ sélectionner et Valider  Tab champ  ↑↓ choisir  Échap retour  F1 aide",
), hauteurs_de_message=messages_de_reglages("portrait"))

# ----------------------------------------------------------- E5-3, note 6 ---
#
# CINQ ecarts d'origine, tous nommes.
# `P5` -- les trois issues etaient sur UNE ligne, avec des cases `( )` et sans
# fleche : `EPIC11-ARB-126` (« Fleche seule ! ») et `panneau.ChoixExclusif`,
# qui rend une ligne par issue.
# `P6` -- `E editer les noms` : annule par `EPIC11-ARB-141`.
# `P7` -- le glyphe de focus `>` hors mode edition.
# `P8` -- ligne d'etat : deux touches et un conseil d'usage (`EPIC11-ARB-56`).
# `P9` -- au rang 1 aucun fragment `_vN` n'entre dans le nom (`EPIC11-ARB-88`).
#
# `N6` (note 6, v4) -- « retirer "lot par lot -- le rang se compte par lot" et
# "l'origine n'ecrit aucun vN" : de la tuyauterie interne, pas du produit. »
# **Les deux lignes partent, et rien ne les remplace.** Ce qu'elles disaient
# reste vrai et reste VISIBLE, mais par le dessin plutot que par la prose : un
# rang par ligne de lot dit deja qu'il se compte par lot, et l'absence de `_vN`
# en face de `tirage 1` dit deja que l'origine n'en ecrit pas. Une legende qui
# explique ce que la colonne d'a cote montre est une legende de trop.
#
# Le curseur se pose sur `Modifier les reglages` -- issue qui n'ecrit pas
# (`ChoixExclusif.__post_init__` l'exige) et point d'entree du retour arriere
# de la note 12.
#
# `N5` (note 5, v5) -- « comment sait-on deja que cela va etre le lot 4 si on
# n'a pas tranche pour l'ecrasement ou le versionnage ? Ce choix arrive avant
# non ? Ecran supplementaire ou meilleure idee ? »
#
# **Egan a raison, et le code le dit.** `cli.py:3520` porte le commentaire
# verbatim « Le rang de version se resout AVANT la composition »
# (`EPIC11-ARB-91`) : le rang entre dans le nom, dans l'etiquette imprimee et
# dans le payload QR, donc il doit etre connu quand le plan se construit. Cet
# ecran-ci annoncait donc « tirage 4 » -- la CONSEQUENCE d'un choix que
# l'operateur n'avait pas encore fait, puisque `E5-3b` etait dessine apres lui.
#
# **La reponse n'ajoute aucun ecran : elle en INVERSE deux.** Detecter le
# conflit ne demande pas la composition, seulement de savoir si un tirage
# existe -- et les deux mesures necessaires se font sans composer :
# `naming.build_sheets_pdf_filename` ne prend que des identifiants, et
# `pdf_composition.page_count_du_lot(manifest, lot_id, frames_per_page=...)`
# (`pdf_composition.py:647`) rend le nombre de pages « SANS composer », ce que
# la fiche 11.7 inventorie deja a sa ligne 204. L'ordre devient :
#
#     E5-2 reglages -> E5-3b conflit (SI un tirage existe) -> E5-3 -> E5-4
#
# Quand cet ecran s'affiche, le rang EST tranche. « tirage 4 » devient un fait,
# et la colonne de droite dit d'ou il vient -- choisi juste avant, ou aucun
# tirage anterieur. C'est la seule chose que la note 5 demandait.
#
# **La grille commande un resserrement, dit plutot que subi** : les noms
# gagnent leur mise en page (note 7) et passent de 37 a 49 colonnes, donc ils
# ne tiennent plus sur la ligne du lot. Le nom descend d'une ligne, et
# `Frames par page` + `Marge de travail` fusionnent en une seule ligne
# `Mise en page` -- le meme resserrement qu'`E5-2` a deja fait sur
# `Format · DPI`. Le compte de lignes est conserve a une pres.
ecrire("E5-3-pdf-confirmation.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf",
    bandeau_droite="2 lots · 164 frames",
    centre=[
        "",
        *cartouche("À écrire", [
            f"Planches                 2 PDF · {_PAGES_6F} pages",
            "Mise en page             6 f/page · paysage · A4 · 600 dpi · marge 0",
            "Taille                   ~ 470 Mo                     (majorant)",
            "Destination              projet_demo/patches/",
            "",
            # **Juste la liste, a plat** (Egan, 2026-09-02, verbatim : « mets
            # juste la liste de toutes les planches produites. Ne regroupe pas
            # par lot et tirage, c'est trop lourd a lire. »). Le regroupement
            # posait quatre lignes et trois colonnes pour dire deux noms.
            #
            # **La meme retouche ferme la seconde**, et c'est ce qui la rend
            # sure : « enleve la phrase qui dit que l'origine n'ecrit aucun vN,
            # tuyauterie interne ». Cette phrase etait la colonne de droite --
            # « aucun tirage anterieur » en face de `tirage 1` --, et elle part
            # avec le regroupement qui la portait.
            #
            # **Rien n'est perdu, et c'est mesurable** : le rang se relit dans
            # le nom, `_v4` pour le lot qui en a trois, RIEN pour celui qui part
            # a l'origine (`EPIC11-ARB-88`). Le nom est d'ailleurs le seul
            # endroit ou il se relira apres coup, sur le disque.
            f"  {planches_mep(LOT_25, rang=4)}",
            f"  {planches_mep(LOT_8)}",
        ]),
        "",
        "     Générer",
        "   ▸ Modifier les réglages",
        "     Annuler",
    ],
    etat=f"2 PDF · {_PAGES_6F} pages · ~ 470 Mo — rien n'a encore été écrit",
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
))

# `P17` -- ECRAN NEUF (2026-09-01). AUCUNE des huit maquettes `E5-*` ne disait
# ce qui se passe quand le PDF existe deja, alors qu'`EPIC11-ARB-89` l'interdit
# nommement. La forme vient de `T4-1` (approuve par Egan le 2026-08-27), avec
# une issue par ligne, la fleche seule, et aucune lettre en raccourci.
# Le curseur se pose sur l'issue NON destructive.
# Le rang vient d'`io/version_ranks.py` et de nulle part ailleurs
# (`EPIC11-ARB-108`) : cet ecran AFFICHE `prochain_rang(ligne_d_eau)`, il ne le
# recalcule pas -- et il ne le consomme pas non plus (`EPIC11-ARB-92`).
#
# **C'est le patron que la note 10 designe** : « l'ecran pour ce refus et pour
# ces issues est le meme que partout ailleurs ». `E5-6d` le reprend tel quel
# pour la mire, sans en redessiner un second.
#
# `N5` (note 5, v5) -- **cet ecran passe AVANT `E5-3`**, et il change de lot.
# Le motif complet est au bloc `E5-3` ci-dessus : le rang se resout avant la
# composition, donc le conflit se tranche avant la confirmation qui l'annonce.
# Consequence directe sur ce dessin : il ne peut plus illustrer un lot « hors
# de la passe », comme l'edition precedente s'y resolvait. Il montre le lot de
# la passe qui a deja des tirages -- `plan-04_25`, celui dont `E5-3` dit
# « tirage 4 » --, et son plus recent tirage est donc le troisieme.
#
# **Le bandeau droit porte la portee du conflit** (`1 lot sur 2`) plutot que le
# lot seul : la question « et les autres lots ? » se pose des qu'une passe en
# porte plusieurs, et le rang etant un fait DU LOT
# (`resolve_sheets_version_rank` prend un `lot_id`), l'ecran est par lot.
#
# `N6` (note 6, v5) -- « **Sorti a l'imprimante : on retire !** Rien n'en parle
# nulle part ». **Verifie, et la note avait raison au-dela de la ligne.** Une
# entree de l'inventaire des tirages ne porte que DEUX champs :
# `_merge_sheets_inventory` (`io/pdf_manifest.py:260`) ecrit
# `SHEETS_INVENTORY_KEY` (le chemin) et, au-dela du rang 1, `version_rank`.
# Il n'existe ni date, ni taille, ni etat d'impression -- un `grep` de
# `printed`, `imprime`, `sorti` sur le coeur ne rend que de la prose de
# commentaire, aucun champ.
#
# Donc la ligne part, **et le paragraphe qui en decoulait part avec elle** :
# « Une feuille deja sortie garde le meme numero que la neuve » raisonnait
# entierement sur une notion que l'outil n'a pas. Ce qui le remplace ne dit que
# ce que l'outil SAIT -- N megaoctets ecrits a telle date, et ce que chaque
# issue en fait.
#
# La date et la taille, elles, restent legitimes : elles ne viennent pas du
# manifeste mais du FICHIER (`stat`), que l'ecran a sous la main.
#
# `N7` -- **et c'est ici que le fragment de mise en page se voit le mieux.**
# Le nom portant `paysage-6f`, ce conflit-ci est celui d'un meme lot dans la
# MEME mise en page : une autre mise en page ecrirait un autre fichier et cet
# ecran ne se monterait pas. Le motif cesse d'etre opaque.
#
# La taille n'est pas tapee : c'est la densite des `~ 470 Mo` d'`E5-3` (28
# pages) appliquee aux 21 pages de ce lot -- une seule valeur d'origine dans
# ces deux ecrans, et non deux ordres de grandeur qui deriveraient.
_MO_PAR_PAGE = 470 / _PAGES_6F
_MO_LOT_25 = round(_PAGES_25_6F * _MO_PAR_PAGE)

# ------------------------------------- E5-3b / E5-3c, retour du 2026-09-02 ---
#
# **La regle d'ecrasement, et elle se dedouble en deux ecrans.** Verbatim :
# « La deduction tient et ca me va. **S'il est scanne on ne peut de fait pas
# l'ecraser.** Si la planche n'est pas encore scannee un message avertit
# l'utilisateur.ice au moment du choix de l'ecrasement. On y ajoute la mention
# "Si cette page a deja ete imprimee, n'ecrasez pas cette planche sous peine de
# generer des conflits de version". On fait confiance a l'operateur.ice. »
#
# Ca ferme `EPIC11-ARB-174`, qui laissait ouverte la question « etat declare ou
# consequence deduite ». Egan tranche la DEDUCTION, et il en tire une regle
# **plus forte** que ce qui etait propose : un interdit, pas un avertissement.
#
# Deux etats du meme ecran, donc deux maquettes, et le lot montre est le MEME
# des deux cotes (`plan-04_25`, tirage 3) pour que la difference se lise sur la
# seule ligne qui change -- `Scanne`.
#
# **Ce que la deduction sait, et elle sait desormais le RANG.** Au moment ou
# ces deux ecrans ont ete dessines, le manifeste ne portait que l'etat de scan
# **du LOT** (`scan_manifest.SCAN_LOT_STATE = "scan"`) : « ce lot a ete
# scanne » etait deductible, « ce tirage-la a ete scanne » ne l'etait pas.
# C'est ce que la note de la maquette nommait comme un cout a payer.
#
# **Il est paye** (`EPIC11-ARB-176`, tranche par Egan le 2026-09-02 et ecrit le
# jour meme) : le scan persiste `lots[].scanned_version_ranks` -- l'ensemble
# trie et dedoublonne des rangs effectivement lus au QR --, par UNION et jamais
# par ecrasement. `payload_version_rank`, qui n'avait aucun site d'appel dans
# `src/`, en a deux. Les deux ecrans lisent donc le RANG, et le glose de la
# ligne `Scanne` de `E5-3b` le dit : « aucun scan ne cite ce TIRAGE ».
#
# **`EPIC11-ARB-104` n'est pas contredit** (« tout doit etre versionnable OU
# ecrase ») : sur un tirage scanne l'objet reste versionnable -- `Creer la v4`
# est offert --, c'est l'ECRASEMENT seul qui tombe. Et `EPIC11-ARB-89` tient
# aussi : deux issues restent offertes, il n'y a pas de blocage sec.
#
# **Le curseur de `E5-3b` se pose sur `Remplacer ce tirage`, et c'est un
# MOMENT, pas le montage.** Egan demande l'avertissement « au moment du choix
# de l'ecrasement » : c'est cet instant-la que la maquette dessine.
# `ChoixExclusif.__post_init__` place le curseur au montage sur une issue qui
# n'ecrit pas, et le deplacer ensuite est le fonctionnement normal.
# **L'ISSUE DE MASSE** (`EPIC11-ARB-177`, Egan le 2026-09-02 : « Excellente
# proposition : le choix 3 »). L'ecran reste PAR LOT et gagne « appliquer ce
# choix aux N conflits restants ». Les trois contraintes que l'arbitrage tire
# d'`EPIC11-ARB-89`, et ou chacune se voit dans le dessin :
#
#   1. **jamais la premiere issue atteinte** : elle est posee APRES l'issue
#      unitaire, et le curseur au montage ne vise jamais une issue qui ecrit
#      (`EPIC11-ARB-7`) -- a plus forte raison une qui ecrit N fois ;
#   2. **elle nomme ce qu'elle emporte, en cardinal ET en poids** : sa ligne de
#      consequence porte les deux (`3 lots · 1 056 Mo`), comme l'issue unitaire
#      porte deja « efface les 352 Mo ecrits ». Un « appliquer aux 4 restants »
#      muet sur les megaoctets serait MOINS informatif que l'ecran qu'il
#      remplace ;
#   3. **elle reste une issue parmi d'autres** : les deux unitaires et
#      l'annulation sont intactes.
#
# **Elle SAUTE les tirages scannes, en le disant.** C'est la seule forme
# compatible avec `EPIC11-ARB-89` -- refuser l'issue en bloc ferait perdre les
# N-1 autres pour un seul -- et `EPIC11-ARB-174`/`-176` interdisent d'ecraser
# celui-la. Le saut est ecrit sur la ligne, pas deduit d'un cardinal qui ne
# tomberait pas juste.
#
# **La passe dessinee porte cinq conflits, pas deux, et c'est un choix assume**
# (meme geste qu'`E5-5b`, qui montre sept lots quand la demonstration en a
# deux) : une issue de masse ne se voit pas sur un seul conflit restant, et le
# saut du tirage scanne ne se voit pas du tout.
#
# Le poids de la masse est DERIVE, jamais tape : trois lots de la taille du lot
# montre. C'est un ordre de grandeur, comme tous les megaoctets de cette
# planche.
_MO_MASSE_3_LOTS = f"{_MO_LOT_25 * 3:,}".replace(",", " ")

ecrire("E5-3b-pdf-tirage-existe.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf",
    bandeau_droite="1 conflit sur 5 · tirage présent",
    centre=[
        *cartouche("Ce tirage existe déjà", [
            f"▲ {planches_mep(LOT_25, rang=3)}",
            f"Lot                {LOT_25:<17}3e tirage, le plus récent",
            "Écrit le           26/08 à 16:22",
            f"Contient           {_PAGES_25_6F} pages · 124 frames · {_MO_LOT_25} Mo",
            "Mise en page       6 f/page · paysage      la même qu'aujourd'hui",
            # `·` et non `✕` : un tirage non scanne n'est ni un manque ni un
            # refus, c'est le cas courant. `DESIGN.md` §6 donne `·` pour
            # « neutre », et il se peint en `muted` -- une ligne rouge ici
            # sonnerait l'alarme sur le seul etat qui autorise l'ecrasement.
            #
            # **Le glose dit « ce tirage », plus « ce lot »** : depuis
            # `EPIC11-ARB-176` le manifeste porte `lots[].scanned_version_ranks`
            # et la deduction se fait AU RANG. Un lot dont le `v1` a ete scanne
            # ne rend plus son `v3` inecrasable.
            "Scanné             · non            aucun scan ne cite ce tirage",
            "",
            # La mention d'Egan, **mot pour mot**. Elle n'est coupee que par la
            # largeur du cartouche ; aucun mot n'est change ni abrege.
            "▲ Si cette page a déjà été imprimée, n'écrasez pas cette",
            "  planche sous peine de générer des conflits de version",
        ]),
        "     Créer la v4",
        "   ▸ Remplacer ce tirage",
        f"       ▲ efface les {_MO_LOT_25} Mo écrits",
        "     Appliquer ce choix aux 4 conflits restants",
        f"       ▲ 3 lots · {_MO_MASSE_3_LOTS} Mo effacés — 1 sauté, il est scanné",
        "     Annuler",
    ],
    etat=f"▲  {_PAGES_25_6F} pages · {_MO_LOT_25} Mo écrits le 26/08 · ce tirage n'est pas scanné",
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
), hauteurs_de_message={"Si cette page": 2})

# ECRAN NEUF -- l'autre moitie du retour : **le tirage scanne ne s'ecrase
# plus**. Meme lot, meme tirage, meme date que `E5-3b` : seule la ligne
# `Scanne` change, et avec elle la liste des issues, qui perd `Remplacer ce
# tirage`. L'ecran dit pourquoi plutot que de faire disparaitre une ligne sans
# explication -- une issue qui manque sans motif se lit comme un bug.
# **L'issue de masse est ici aussi, et ce qu'elle porte n'est PAS la meme
# chose** -- c'est le meilleur endroit de la planche pour le voir. `Remplacer`
# est tombe, donc « ce choix » ne peut designer que `Creer la v4` : la masse
# n'efface rien, ne saute personne, et sa ligne de consequence le dit avec le
# glyphe NEUTRE. Une meme entree, deux poids, selon l'issue qu'elle prolonge.
ecrire("E5-3c-pdf-tirage-scanne.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf",
    bandeau_droite="1 conflit sur 5 · tirage scanné",
    centre=[
        *cartouche("Ce tirage existe déjà, et il a été scanné", [
            f"▲ {planches_mep(LOT_25, rang=3)}",
            "",
            f"Lot                {LOT_25:<17}3e tirage, le plus récent",
            "Écrit le           26/08 à 16:22",
            f"Contient           {_PAGES_25_6F} pages · 124 frames · {_MO_LOT_25} Mo",
            "Scanné             ▲ oui            scan-WIN, le 27/08",
            "",
            # **REECRIT par Egan le 2026-09-02 au soir**, mot pour mot :
            # « ce tirage a deja ete imprime. Vous ne pouvez pas l'ecraser car
            # cela pourrait causer des conflits de version. »
            #
            # Ce qui tombe avec l'ancienne redaction, et c'est le point : elle
            # expliquait le MECANISME -- la feuille porte son rang dans son QR,
            # le remplacer ferait dire deux choses au meme numero. Egan :
            # « **le mecanisme n'est pas la raison qu'un operateur a besoin de
            # lire** ». Il vit dans `EPIC11-ARB-174` et `-176`, pas a l'ecran.
            # Deux phrases contre quatre lignes de cartouche.
            "▲ Ce tirage a déjà été imprimé. Vous ne pouvez pas l'écraser",
            "  car cela pourrait causer des conflits de version.",
        ]),
        "",
        "   ▸ Créer la v4",
        "     Appliquer ce choix aux 4 conflits restants",
        "       · 4 versions créées — rien n'est effacé",
        "     Annuler",
    ],
    etat="✕  Remplacer n'est pas offert — ce tirage a été scanné le 27/08",
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
), hauteurs_de_message={"Ce tirage a déjà": 2})

# `P10` -- « QR version 14 » etait faux, et la correction precedente (« 18 »)
# l'etait aussi : **18 est la version du PIRE cas** (cinq identifiants a la
# borne des 48 caracteres, rang 99), pas celle de cette page. Mesure ici par le
# chemin de PRODUCTION -- `page_payload.plan_page_payload` puis
# `qr_codes.symbol_version(encode_qr_image(...))`, jamais un `cv2.QRCodeEncoder`
# nu, qui rendait des versions decroissantes quand les octets montaient
# (piege paye le 2026-08-30). Sur le payload reellement dessine ici, cardinal 6,
# le symbole est en **version 16**.
# `P11` -- le journal nomme le TIRAGE : `EPIC11-ARB-91` le fait entrer dans le
# payload QR, et une passe qui n'ecrit pas quel rang elle grave laisse la seule
# trace de ce fait au fond du symbole.
_QR_CARDINAL_6 = 16  # mesure, voir ci-dessus

# `N7` (note 7, v5) -- « Il n'y a pas le nombre de frames dans les noms de
# planches ? » **Non, et c'etait le defaut ; les noms de cet ecran le portent
# desormais** (le fragment et son motif complet sont documentes a
# `planches_mep`, en tete de ce fichier). L'ecart est instructif : le JOURNAL
# de cet ecran nommait deja le gabarit -- `tpl-a4-paysage-6f-v2` --, donc la
# mise en page etait dite au moment ou elle s'ecrivait et perdue au moment ou
# on la relisait sur le disque.
ecrire("E5-4-pdf-execution.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf",
    bandeau_droite="2 lots · 164 frames",
    centre=[
        "",
        "  Génération en cours — lot 2 sur 2",
        "",
        f"     ● {planches_mep(LOT_25, rang=4):<51}{_PAGES_25_6F:>2} pages  écrit",
        f"       {planches_mep(LOT_8):<51}{_PAGES_8_6F:>2} pages  en cours",
        "",
        regle("Journal"),
        "",
        f"     16:22:41  {LOT_8} : {COMBINAISONS[('paysage', 6)]['gabarit']}, tirage 1",
        f"     16:22:41  page 1/{_PAGES_8_6F} : 6 emplacements, QR version {_QR_CARDINAL_6}",
        f"     16:22:44  page 2/{_PAGES_8_6F} : 6 emplacements, QR version {_QR_CARDINAL_6}",
        f"     16:22:47  page 3/{_PAGES_8_6F} : 6 emplacements, QR version {_QR_CARDINAL_6}",
    ],
    etat=barre_double(_PAGES_25_6F + 3, _PAGES_6F,
                      f"lot 2/2 · page 3/{_PAGES_8_6F}", "8 s"),
    raccourcis="Tab journal  Échap interrompre  F1 aide",
))

# ----------------------------------------------------------- E5-5, note 8 ---
#
# `N8` (note 8) -- « Prochain rang ne tient pas quand on aura plus que 2 lots
# d'un coup, idem pour tirage ecrit. **Pas la place !** Comment faire ? »
#
# **Le diagnostic, avant la reponse.** Les deux lignes fautives etaient
# `Tirage ecrit  plan-04_25 → 4 · plan-04_8 → 1` et sa jumelle `Prochain
# tirage`. Leur forme est celle d'un **fait de la passe** : un libelle, une
# valeur. Or le rang n'est pas un fait de la passe, c'est un fait DU LOT
# (`pdf_composition.resolve_sheets_version_rank` prend un `lot_id`). Une ligne
# unique qui doit enumerer tous les lots croit lineairement avec eux, et deux
# lignes de ce genre croissent deux fois -- d'ou « pas la place », a deux lots
# deja.
#
# **La reponse dessinee : le rang devient une COLONNE, pas une ligne.** La
# liste des PDF ecrits porte deja une ligne par lot ; elle gagne deux colonnes
# etroites, `tirage` et `puis`. Le cout par lot supplementaire passe de « deux
# lignes qui s'allongent » a « une ligne de plus », c'est-a-dire au meme cout
# que la liste elle-meme. Une ligne d'en-tete nomme les colonnes, sans quoi
# deux nombres nus seraient illisibles.
#
# Les deux lignes globales disparaissent donc, et avec elles le pluriel
# impossible. Le rang ECRIT reste lisible deux fois -- dans la colonne et dans
# le suffixe `_vN` du nom, dont l'absence dit l'origine.
#
# **Ce que cette forme ne resout pas, et `E5-5b` le montre** : elle borne le
# cout par lot, elle ne le supprime pas. Passe une dizaine de lots, la liste
# deborde la grille de 24 lignes quoi qu'on fasse -- c'est alors le defilement
# qui prend le relais, avec le marqueur `…  n-m sur N` deja employe par `E2-2`.
# `N8` (note 8, v5) -- « Garder juste **tirage**. Enlever "puis". C'est
# inutile ». **La colonne part, et elle part des DEUX ecrans** : `E5-5` et
# `E5-5b` partagent `table_des_ecrits`, donc une seule redaction les corrige
# tous les deux -- c'est la raison d'etre de cette fabrique.
#
# Ce que le retrait rend, et qui n'est pas rien : **six colonnes**, reversees
# a la colonne des noms. Elle passe de 41 a 49, ce qui absorbe exactement le
# fragment de mise en page de la note 7 -- les quatre noms de la demonstration
# tiennent entiers, alors qu'ils auraient tous ete elides sans ce retrait.
#
# Ce que la colonne `puis` disait reste accessible : le prochain rang est
# annonce par `E5-3b`, au moment ou il commande quelque chose.
_COLONNE_NOM = 49  # la plus longue des lignes de fichier tenues par le cartouche


def table_des_ecrits(lignes: list[tuple[str, int, int]]) -> list[str]:
    """La liste des PDF ecrits, une ligne par lot, rang en colonne.

    `lignes` : `(nom de fichier, pages, tirage ecrit)`.
    """
    rendu = [f"{'fichier':<{_COLONNE_NOM + 2}}{'pages':>7}{'tirage':>9}"]
    for nom, pages, ecrit in lignes:
        rendu.append(f"● {nom:<{_COLONNE_NOM}}{pages:>7}{ecrit:>9}")
    return rendu


ecrire("E5-5-pdf-resultat.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf",
    bandeau_droite="2 lots · 164 frames",
    centre=[
        "",
        *cartouche("Écrit", [
            *table_des_ecrits([
                (planches_mep(LOT_25, rang=4), _PAGES_25_6F, 4),
                (planches_mep(LOT_8), _PAGES_8_6F, 1),
            ]),
            "",
            f"Gabarit                     {COMBINAISONS[('paysage', 6)]['gabarit']}",
            "Emplacement                 projet_demo/patches/",
            "Manifest mis à jour         projet_demo/manifest.json",
        ]),
        "",
        "   ▸ Ouvrir le dossier",
        "     Générer une planche de calibration          (à imprimer avec)",
        "     Mettre d'autres lots en planches",
        "     Retour aux ateliers",
    ],
    etat=f"●  {_PAGES_6F} pages écrites · 164 frames placées · ~ 470 Mo · aucun refus",
    # **`Tab journal` part, et c'est une correction, pas une perte.** La ligne
    # du PRODUIT pour un ecran de compte rendu est
    # `atelier_scan_parcours.RACCOURCIS_RAPPORT` (`:127`), et elle ne porte
    # aucun `Tab` -- son commentaire dit pourquoi, verbatim : « aucun ecran de
    # journal n'est monte par le temps 1, et `CoqueTui.BINDINGS` n'a pas de
    # liaison `tab` [...] la maquette se corrige avec la 11.6 ». Le retrait
    # aligne donc la maquette sur le code livre, et il LIBERE `Tab` pour la
    # bascule de zone que `E5-5b` introduit -- sans quoi la meme touche aurait
    # deux sens sur deux etats du meme ecran.
    raccourcis="⏎ choisir  ↑↓ naviguer  Échap ateliers  F1 aide",
))

# ---------------------------------------------------- E5-5b, note 8 (suite) ---
#
# ECRAN NEUF. Egan pose une question -- « comment faire ? » --, donc la reponse
# se dessine plutot qu'elle ne s'explique. Cet ecran est le meme que `E5-5` sur
# la passe qu'il redoutait : **sept lots d'un coup**, dont un au nom long.
#
# Trois mecanismes, tous empruntes au depot, aucun invente :
#
#   1. **une ligne par lot**, colonnes `tirage` / `puis` -- la forme d'`E5-5` ;
#   2. **l'ellipse dans le SLUG**, jamais sur le condensat ni sur le suffixe :
#      c'est la regle deja posee pour le nom de la mire en `E5-6` ;
#   3. **le marqueur de position `…  n-m sur N`**, celui d'`E2-2`
#      (`…    1-4 sur 8 cadences`).
#
# `N9` (note 9, v5) -- « Les fleches ne peuvent pas faire defiler si elles
# naviguent... solution ? » **Egan a vu juste, et le defaut etait dans le
# marqueur, pas dans le mecanisme.** La ligne portait
# `1-4 sur 7 PDF écrits · ↑↓ fait défiler` alors que le pied de ce meme ecran
# dit `↑↓ naviguer` -- pour la liste des ISSUES, qui est la seule a porter un
# curseur `▸`. `DESIGN.md` §7.5 tranche la question : « il n'y a donc **jamais
# deux curseurs** a l'ecran » (`EPIC11-ARB-50`). Deux listes ne peuvent pas se
# disputer `↑↓` ; la promesse etait donc fausse, et c'est elle qui part.
#
# **Le mecanisme, lui, existe et n'a rien a inventer** -- il repond a la
# question la ou elle se pose vraiment, c'est-a-dire sur une liste qui A le
# curseur (`E5-1`, `E2-2`, l'explorateur) :
# `jetons.fenetre_de_liste(total, premier_visible, hauteur)` rend les rangs
# visibles, `jetons.recadrer_la_fenetre(premier_visible, curseur, total,
# hauteur)` ramene la fenetre sur le curseur, **un rang a la fois**. Les
# fleches deplacent donc le curseur et la fenetre SUIT : elles ne defilent
# jamais. Cinq surfaces du depot s'en servent deja -- `explorateur.py:608`,
# `cadences.py:669`, `rushes.py:620`, `atelier_scan.py:1015`,
# `atelier_scan_calibration.py:509`. Et la ligne `…` se reserve **avant** le
# decoupage, sans quoi la derniere entree se cacherait derriere le `…` qui
# annonce justement qu'elle existe.
#
# Ici, le marqueur redevient ce qu'il est : une **position**, pas une touche.
# Ce qui manque a l'ecran se lit au journal (`Tab`) et dans le dossier
# (`Ouvrir le dossier`), qui sont deja les deux issues de cet ecran.
#
# Le bloc du bas ne grandit pas avec les lots : il porte des faits communs a la
# passe. C'est ce qui rend la forme tenable -- la seule partie qui croit est
# celle qui doit croitre.
_LOTS_NOMBREUX = [
    (naming.build_lot_id("plan-01", 25), 124, 2),
    (naming.build_lot_id("plan-02", 12.5), 96, 1),
    (naming.build_lot_id("plan-03", 8), 51, 5),
    (LOT_LONG, 78, 1),
]
_TOTAL_LOTS_NOMBREUX = 7
_FRAMES_NOMBREUX = 512


#: Ce qu'un nom de mire ne perd jamais : `-<condensat 8 hexa>_calibration.pdf`.
#: **Derive du nom produit**, pas compte a la main : le dernier tiret du nom est
#: celui qui ouvre le condensat, donc ce qui le suit est exactement la queue
#: incompressible. Un litteral aurait a etre corrige le jour ou le condensat
#: change de longueur, et personne ne le verrait.
_NOM_MIRE = calibration(CHAINE)
QUEUE_MIRE = len(_NOM_MIRE) - _NOM_MIRE.rindex("-")


#: Ce qu'un nom de tirage ne perd jamais a l'ellipse : tout ce qui suit le
#: fragment de mise en page -- la mise en page elle-meme et le rang. **Derive
#: du nom produit** (position du fragment), jamais compte a la main : il
#: s'allonge tout seul le jour ou le fragment change de forme. Il valait 20
#: quand le marqueur etait `_planches` ; il vaut 15 depuis que le fragment
#: prend sa place, donc l'ellipse rend cinq colonnes au slug.
_NOM_PLANCHES = planches_mep(LOT_25, rang=99)
_FRAGMENT_MEP = "_" + mise_en_page("paysage", 6)
QUEUE_PLANCHES = len(_NOM_PLANCHES) - _NOM_PLANCHES.index(_FRAGMENT_MEP)


# ------------------------------- E5-5b / E5-5c, retour du 2026-09-02 ---------
#
# **« Donc si on fait 100 lots d'un coup on doit tout faire defiler avant
# d'atteindre les choix ? Non **il faut basculer d'une zone a l'autre si
# possible. TAB ?** »** Egan REFUSE la reponse precedente -- le marqueur de
# defilement seul -- et il a raison : ce marqueur disait ou on est dans la
# liste, il ne donnait aucun moyen d'y entrer ni d'en sortir.
#
# **Ce que le depot fait deja, cherche avant d'inventer.** Trois paires
# d'ecrans emploient `Tab` exactement pour ca, et aucune n'invente de glyphe :
#
#   * `X1`/`X5` -- l'explorateur : `Tab chemin` entre dans la barre d'adresse,
#     `Tab liste` en sort. C'est ecrit noir sur blanc au `DESIGN.md` §7.5 :
#     « `Tab` entre dans la barre d'adresse et en sort -- et rien d'autre » ;
#   * `E2-3`/`E2-3b` -- la confirmation d'extraction : `Tab editer les noms`
#     entre dans le bloc des noms, `Tab les choix` revient a la liste des
#     issues. C'est le patron le plus proche d'ici : un bloc de contenu en
#     haut, des issues en bas, une seule des deux zones eclairee a la fois ;
#   * `E6-1`/`E6-1b` -- `Tab ecarts` / `Tab inventaire`.
#
# **`EPIC11-ARB-50` ne s'y oppose pas, et c'est mesure plutot que suppose.**
# Le principe dit « il n'y a donc **jamais deux curseurs** a l'ecran » ; il
# interdit deux curseurs SIMULTANES, pas deux zones navigables. `Tab` ne
# duplique pas le curseur : il le DEPLACE. Les trois paires ci-dessus sont
# exactement ca, et l'une d'elles (`X1`/`X5`) est le paragraphe meme ou
# `ARB-50` est ecrit. La reponse precedente confondait « deux listes se
# disputent `↑↓` » -- vrai, et toujours vrai -- avec « une seule zone peut etre
# navigable » -- faux.
#
# **Consequence de dessin, et elle commande la forme.** La zone du haut porte
# le curseur dans `E5-5c` : elle ne peut donc plus etre un cartouche. Le
# colorisateur ne reconnait l'entree du curseur que si le glyphe `▸` ouvre la
# ligne une fois `strip()` faite (`coloriser_maquette._segments_du_centre`), et
# `construire_maquette._declarer_le_curseur` cherche le meme motif : un `▸`
# pose DANS un cartouche est precede du bord `│`, donc invisible aux deux, et
# la ligne se peindrait en vert d'etat au lieu de l'accent du curseur. La liste
# des ecrits devient donc une **liste §7.1**, sous un filet, et le bloc chiffre
# du bas garde ses deux faits communs a la passe. `E5-5` (deux lots, liste qui
# tient) garde son cartouche §7.4 : sa liste ne se parcourt pas, il n'y a rien
# a y entrer.
#
# **Ce que chaque etat montre.** `E5-5b` est l'ETAT D'ARRIVEE et il repond seul
# a la question d'Egan : le curseur est sur les issues, tout en bas, sans avoir
# rien fait defiler -- « on doit tout faire defiler avant d'atteindre les
# choix ? » non, on y est deja. `E5-5c` est l'etat apres `Tab` : le curseur est
# dans la liste, la fenetre a suivi (`3-5 sur 7`), et les issues restent
# dessinees, entieres et sans curseur -- elles ne disparaissent pas, elles
# perdent la main.
#
# Le mecanisme de fenetre reste celui du depot, inchange :
# `jetons.fenetre_de_liste(total, premier_visible, hauteur)` rend les rangs
# visibles et **reserve la ligne `…` avant le decoupage**, `↑` et `↓`
# deplacent le curseur et la fenetre SUIT (`jetons.recadrer_la_fenetre`, un
# rang a la fois). Cinq surfaces s'en servent deja -- `explorateur.py:608`,
# `cadences.py:669`, `rushes.py:620`, `atelier_scan.py:1015`,
# `atelier_scan_calibration.py:509`.
#
# La fenetre de `E5-5c` est posee au MILIEU de la liste (rangs 3 a 5 sur 7),
# donc les deux `…` sont visibles a la fois -- celui du haut nu, celui du bas
# porteur du compte, la forme de `X4`. Une fenetre calee en tete ou en queue
# n'en montrerait qu'un, et le dessin dirait moins que le mecanisme.

#: La largeur du nom dans la liste **hors cartouche** : 76 colonnes utiles
#: moins l'indentation (5), le glyphe d'etat et son espace (2), les pages (7)
#: et le tirage (9). Elle vaut donc quatre colonnes de plus que dans le
#: cartouche de `E5-5`, ou les deux bords en prennent leur part.
_COLONNE_NOM_LISTE = 76 - 5 - 2 - 7 - 9


def liste_des_ecrits(lignes: list[tuple[str, int, int]],
                     curseur: str | None = None) -> list[str]:
    """La liste des PDF ecrits, en **liste §7.1** : une ligne par lot.

    `lignes` : `(nom de fichier, pages, tirage ecrit)`. `curseur` nomme le
    fichier sous le curseur, ou `None` quand la zone n'a pas la main -- et
    c'est la seule difference entre les deux etats de l'ecran.
    """
    rendu = [f"     {'fichier':<{_COLONNE_NOM_LISTE + 2}}"
             f"{'pages':>7}{'tirage':>9}"]
    for nom, pages, ecrit in lignes:
        tete = "   ▸ " if nom == curseur else "     "
        rendu.append(f"{tete}● {nom:<{_COLONNE_NOM_LISTE}}{pages:>7}{ecrit:>9}")
    return rendu


def marqueur(texte: str) -> str:
    """La ligne `…` de position, calee a droite -- la forme de `X4` et d'`E2-2`."""
    return f"     …{texte:>70}"


_ECRITS_NOMBREUX = [
    (elider(planches_mep(lot, rang=rang if rang > 1 else None),
            _COLONNE_NOM_LISTE, QUEUE_PLANCHES),
     pages_du_lot(frames, 6), rang)
    for lot, frames, rang in _LOTS_NOMBREUX
]

#: Les trois entrees visibles quand la fenetre est au milieu de la liste. Les
#: rangs 3 a 5 d'une liste de 7 : la cible n'est ni en tete ni en queue, ce que
#: CLAUDE.md exige de toute fabrique de collection.
_ECRITS_AU_MILIEU = [
    (naming.build_lot_id("plan-03", 8), 51, 5),
    (LOT_LONG, 78, 1),
    (naming.build_lot_id("plan-05", 25), 63, 3),
]
_FENETRE_AU_MILIEU = [
    (elider(planches_mep(lot, rang=rang if rang > 1 else None),
            _COLONNE_NOM_LISTE, QUEUE_PLANCHES),
     pages_du_lot(frames, 6), rang)
    for lot, frames, rang in _ECRITS_AU_MILIEU
]

ecrire("E5-5b-pdf-resultat-nombreux.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf",
    bandeau_droite=f"{_TOTAL_LOTS_NOMBREUX} lots · {_FRAMES_NOMBREUX} frames",
    centre=[
        "",
        regle(f"Écrit — {_TOTAL_LOTS_NOMBREUX} PDF, {_FRAMES_NOMBREUX} frames"),
        "",
        *liste_des_ecrits(_ECRITS_NOMBREUX),
        marqueur(f"1-4 sur {_TOTAL_LOTS_NOMBREUX} PDF écrits"),
        "",
        f"     Gabarit                     {COMBINAISONS[('paysage', 6)]['gabarit']}",
        "     Emplacement                 projet_demo/patches/",
        "",
        "   ▸ Ouvrir le dossier",
        "     Générer une planche de calibration          (à imprimer avec)",
        "     Mettre d'autres lots en planches",
        "     Retour aux ateliers",
    ],
    etat="●  7 PDF écrits · 512 frames placées · aucun refus",
    raccourcis="⏎ choisir  ↑↓ naviguer  Tab champ  Échap ateliers  F1 aide",
))

# ECRAN NEUF -- l'autre cote de la bascule. Meme passe, meme ecran, `Tab`
# appuye une fois : le curseur est passe dans la liste, la fenetre s'est
# recadree sur lui, et les issues restent la, dessinees et inertes.
#
# **Le pied est contextuel, et il perd `⏎`.** Dans la liste, `Entree` n'a rien
# a valider -- un fichier ecrit n'est pas une issue --, et `DESIGN.md` §4 dit
# que la ligne « ne montre que ce qui marche sur l'ecran courant ». Annoncer
# une touche inerte est exactement le defaut que la story 11.5 a paye quarante
# fois.
ecrire("E5-5c-pdf-resultat-liste-parcourue.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf",
    bandeau_droite=f"{_TOTAL_LOTS_NOMBREUX} lots · {_FRAMES_NOMBREUX} frames",
    centre=[
        "",
        regle(f"Écrit — {_TOTAL_LOTS_NOMBREUX} PDF, {_FRAMES_NOMBREUX} frames"),
        "",
        liste_des_ecrits(_FENETRE_AU_MILIEU)[0],
        "     …",
        *liste_des_ecrits(_FENETRE_AU_MILIEU,
                          curseur=_FENETRE_AU_MILIEU[1][0])[1:],
        marqueur(f"3-5 sur {_TOTAL_LOTS_NOMBREUX} PDF écrits"),
        "",
        f"     Gabarit                     {COMBINAISONS[('paysage', 6)]['gabarit']}",
        "     Emplacement                 projet_demo/patches/",
        "",
        "     Ouvrir le dossier",
        "     Générer une planche de calibration          (à imprimer avec)",
        "     Mettre d'autres lots en planches",
        "     Retour aux ateliers",
    ],
    etat="●  7 PDF écrits · 512 frames placées · aucun refus",
    raccourcis="↑↓ naviguer  Tab champ  Échap ateliers  F1 aide",
))

# ------------------------------------------------- E5-6 & suite, notes 9 10 ---
#
# QUATRE ecarts d'origine, tous nommes.
# `P13` -- DEUX glyphes de focus `>` sur le meme ecran (`DESIGN.md` §6).
# `P14` -- `E editer le nom` : il n'y a rien a editer, le nom sort de
# `build_calibration_pdf_filename`.
# `P15` -- ligne d'etat : motif de conception sans chiffre, et une commande de
# CLI nommee dans la TUI.
# `P16` -- le nom de fichier laissait tomber le CONDENSAT ; l'ellipse se place
# DANS le slug. Le nom entier est desormais **construit** par la fonction du
# produit, jamais recopie : `73881cda` n'est plus une valeur tapee mais le
# condensat que `build_calibration_pdf_filename` rend pour cette chaine.
#
# `N9` (note 9) -- « il faudrait ici encore un ecran de confirmation avant
# ecriture, conformement a la logique de tous les autres ecrans qui ecrivent.
# Et un ecran de progression ». **Cet ecran cesse donc d'ecrire.** Son `⏎` ne
# genere plus : il mene a `E5-6b`. La sequence de la mire devient celle de tous
# les autres chemins ecrivants du depot -- reglages, confirmation chiffree,
# progression, resultat --, et les trois ecrans neufs REPRENNENT les patrons
# existants au lieu d'en inventer : `E5-3` pour la confirmation, `E5-4` pour la
# progression, `E5-5` pour le resultat, `E5-3b` pour le refus.
ecrire("E5-6-pdf-calibration-page.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf · Calibration",
    bandeau_droite="temps 1 sur 2 · régler",
    centre=[
        "",
        "  Générer une planche de calibration",
        "",
        f"     Nom de la chaîne   > {CHAINE}",
        "     Commentaire          passe du 27/08, papier mat",
        "",
        regle("Imposé par la fonction de calibration"),
        "",
        "     Pastilles            164          130 au treillis + 34 témoins",
        "     Jeu de patchs        patches-17-v4    les 34 témoins du bandeau",
        "     Format · DPI         A4 · 600",
        "",
        regle("Ce qui sera écrit"),
        "",
        f"     Fichier              {elider(calibration(CHAINE), 50, QUEUE_MIRE)}",
        "     Destination          projet_demo/patches/",
    ],
    etat="1 page · 164 pastilles · aucun fichier de ce nom sous patches/",
    raccourcis="⏎ continuer  Tab champ  Échap menu Pdf  F1 aide",
))

# ECRAN NEUF -- `N9`, la confirmation. **Aucune forme neuve** : c'est `E5-3`,
# au caractere pres. Meme cartouche `À écrire`, meme ordre (ce qui sort, puis
# ou ca va, puis le nom du fichier en dernier -- `DESIGN.md` §7.4), memes trois
# issues, meme curseur pose sur celle qui n'ecrit pas.
#
# `N12` (note 12 : le maintien des reglages « a systematiser si possible ») --
# **c'est ici que la systematisation se voit.** L'issue mediane porte le meme
# libelle qu'en `E5-3`, `Modifier les reglages`, et le curseur s'y pose au
# montage. Deux ecrans de confirmation d'ateliers differents offrent donc
# litteralement le meme retour, au meme rang, sous le meme mot -- ce qui est la
# forme dessinable de « systematiser ». Ce qui reste a faire vit dans le code et
# non ici : `panneau` ne porte aucune garde qui MESURE que le retour conserve
# les valeurs. Le dire plutot que le taire.
#
# **Aucune taille de fichier n'est annoncee, et c'est deliberé.** Les `~ 470 Mo`
# des planches sont un ordre de grandeur herite du 27/08 ; pour la mire il n'y
# en a aucun, et l'inventer serait pire que l'absence. La confirmation reste
# chiffree par ce qui EST mesure : une page, 164 pastilles.
ecrire("E5-6b-pdf-calibration-confirmation.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf · Calibration",
    bandeau_droite="temps 2 sur 2 · écrire",
    centre=[
        "",
        *cartouche("À écrire", [
            "Planche de calibration   1 PDF · 1 page",
            f"Chaîne                   {CHAINE}",
            "Commentaire              passe du 27/08, papier mat",
            "Pastilles                164          130 treillis + 34 témoins",
            "Jeu de patchs            patches-17-v4",
            "Format · marge · DPI     A4 · 0 mm · 600",
            "Destination              projet_demo/patches/",
            "",
            "Nom du fichier",
            f"  {elider(calibration(CHAINE), 52, QUEUE_MIRE)}",
        ]),
        "",
        "     Générer",
        "   ▸ Modifier les réglages",
        "     Annuler",
    ],
    etat="1 PDF · 1 page · 164 pastilles — rien n'a encore été écrit",
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
))

# ECRAN NEUF -- `N9`, la progression. Forme d'`E5-4` : une ligne par objet
# ecrit et un journal sous filet -- **mais sans barre**.
#
# **Retour du 2026-09-02, verbatim : « Un jalon par page mais pas le detail du
# QR et des pastilles generees donc. »** Les `130/164 pastilles` de l'edition
# precedente etaient exactement ce detail, et la barre disparait avec lui.
#
# **Elle disparait parce que le coeur ne peut pas l'alimenter, pas parce
# qu'on l'a jugee inutile** -- la nuance compte, parce qu'elle dit ce qu'il
# faudrait pour la rendre. Le canal livre emet **un jalon par page**,
# `total = plan.page_count` ; une mire tient sur une page, donc la seule barre
# alimentable ici aurait DEUX etats, 0 % puis 100 %. Une barre a deux etats
# n'informe pas, elle occupe. La compter en pastilles demanderait un jalon
# d'une autre granularite, que ni la tache B4 ni l'AC 2.6 ne prevoient -- et
# c'est precisement ce qu'Egan vient d'ecarter.
#
# Ce qui reste dit ce que l'ecran SAIT : une page, 164 pastilles, rien d'ecrit
# encore, et le journal qui nomme ce qui se fait au fur et a mesure. Aucun
# `reste ~ 3 s` non plus : personne n'a chronometre la composition, et
# `EPIC7-ARB-67` interdit de rendre un temps tant qu'aucune mesure n'existe.
#
# `N10` (note 10, v5) -- « Cette progression existe au coeur ? » **NON, et la
# mesure va plus loin que la question.**
#
# Ce qui est mesure, `grep` de `rappel_progression` sur `src/` : **38
# occurrences dans 11 modules** -- sept de coeur (`extraction`, `scan_write`,
# `scan_detect`, `scan_detection`, `scan_output_frames`, `ffmpeg_utils`,
# `progression`) et quatre surfaces (`gui/executeur`,
# `tui/atelier_scan_detection`, `tui/atelier_scan_ecriture`,
# `tui/atelier_extraction_ecriture`). **Zero dans `pdf_composition.py`, zero
# dans `pdf_render.py`, zero sur le chemin `makepdf` de `cli.py`.**
# `pdf_render.render_lot_pdf` (`:370`) porte bien la seule boucle qui pourrait
# jalonner -- `for page in plan.pages` -- et elle n'emet rien.
#
# La fiche 11.7 le nomme deja, tache **B4** du lot de coeur, verbatim :
# « `rappel_progression` sur le rendu (AC 2.6), contrat identique a celui
# d'`ecrire_le_lot_detecte` : un jalon par page, `total = plan.page_count`,
# aucun jalon avant la premiere page, optionnel mais **jamais silencieusement
# eteint** ».
#
# **Et le retour du 2026-09-02 tranche la question que cette note laissait
# ouverte.** L'edition precedente proposait deux issues -- etendre le contrat
# de B4 a un cardinal fourni par le plan, ou renoncer a la barre pour la mire
# et n'y laisser que le journal. C'est la SECONDE qu'Egan retient, et il la
# formule comme une regle et non comme un pis-aller : un jalon par page, pas
# le detail des pastilles. Le contrat de B4 reste donc tel quel.
#
# **LE JOURNAL PART AUSSI, et c'est la reponse a la question qu'Egan pose** :
# « remplacer par un glyphe qui tourne le temps de la generation. Car je crois
# qu'il n'y aura rien a voir cote journal, non ? » **Il a raison, et c'est
# mesure sur le chemin de production plutot que suppose.** La generation d'une
# mire passe par `cli.makepdf_calibration_page_command` (`cli.py:3797`) puis
# `pdf_render.render_lot_pdf` : entre le `logger.info("Demarrage de la
# generation de page de calibration...")` d'AVANT et le
# `logger.info("Page de calibration ecrite: %s")' d'APRES, **aucun appel de
# journalisation n'existe** -- ni dans `render_lot_pdf`, ni dans `_render_page`,
# ni dans `compose_calibration_page_plan`. Les quatre lignes que cet ecran
# affichait -- chaine, treillis, bandeau de temoins, marqueurs ArUco -- etaient
# donc DESSINEES : aucun de ces evenements n'est emis par quoi que ce soit. Un
# journal qui montre ce que le coeur n'ecrit pas est pire qu'un journal vide.
#
# **Ce qui le remplace est un ROTOR**, et il a le droit de tourner ici pour la
# raison exacte que `DESIGN.md` §9 nomme desormais : l'interdit porte sur
# l'animation qui remplace un COMPTE REEL, et il n'y en a aucun a remplacer --
# un jalon par page, une seule page. Le dessin sort de `jetons.rotor()`, donc
# il se replie en ASCII comme le reste ; la maquette en fige le premier pas.
# C'est le seul ecran du depot qui montre a quoi ressemble une attente honnete
# quand le seul jalon disponible tombe a la fin.
ecrire("E5-6c-pdf-calibration-execution.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf · Calibration",
    bandeau_droite="temps 2 sur 2 · écrire",
    centre=[
        "",
        "  Génération en cours — planche de calibration",
        "",
        f"     {jetons.rotor(0)} "
        f"{elider(calibration(CHAINE), 50, QUEUE_MIRE):<52}1 page   en cours",
    ],
    # **Aucune barre, et c'est le retour du 2026-09-02 qui la retire** :
    # « Un jalon par page mais **pas le detail du QR et des pastilles**
    # generees donc. » Les `130/164 pastilles` etaient exactement ce detail.
    #
    # Ce qui reste est ce que l'ecran SAIT : une page, 164 pastilles, et rien
    # d'ecrit encore. Pas de `0/1 page` -- un compteur a deux etats n'informe
    # pas, il occupe --, pas de `reste ~ 3 s` -- personne n'a chronometre.
    etat="1 page · 164 pastilles — la page n'est pas encore écrite",
    # `Tab journal` part avec le journal : la mesure ci-dessus dit qu'il
    # n'y a rien a y lire pendant la generation d'une mire, et annoncer une
    # touche qui ouvrirait une page vide est le defaut qu'`E5-5` a deja paye.
    raccourcis="Échap interrompre  F1 aide",
))

# ECRAN NEUF -- `N10` : « L'ecran pour ce refus et pour ces issues est le meme
# que partout ailleurs : l'ecran de confirmation non ? » **Oui, et c'est
# exactement `E5-3b` qu'on reprend** : meme cartouche d'avertissement, meme
# ordre des trois issues, curseur sur la non destructive, aucune lettre en
# raccourci.
#
# Les trois issues sont celles que la CLI nomme deja (`cli.py`, refus de
# `makepdf calibration-page` quand le fichier existe et que `--overwrite` est
# absent) : donner un autre `--chaine`, qui entre dans le nom et laisse
# l'existant intact ; remplacer sciemment ; supprimer le fichier. La TUI n'en
# invente aucune -- elle habille celles du coeur.
#
# **Une seule divergence avec `E5-3b`, et elle est mesuree** : il n'y a pas de
# `Creer la v2` ici. La mire ne declare ni rush, ni lot, ni cadence
# (`EPIC5-ARB-82`), donc elle n'a pas de lot dont numeroter les tirages, et
# `version_ranks` n'a rien a resoudre. La sortie non destructive est le
# changement de chaine, parce que le libelle de chaine ENTRE dans le nom.
#
# Le motif du refus n'est pas une prose rassurante : huit parametres de
# geometrie plus le commentaire font varier la page **sans entrer dans son
# nom**, donc deux mires de la meme chaine reglees autrement se disputent
# reellement ce fichier.
ecrire("E5-6d-pdf-calibration-existe.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf · Calibration",
    bandeau_droite="temps 2 sur 2 · écrire",
    centre=[
        "",
        *cartouche("Cette mire existe déjà", [
            f"▲ {elider(calibration(CHAINE), 52, QUEUE_MIRE)}",
            "",
            "Écrit le           27/08 à 09:14",
            "Contient           1 page · 164 pastilles",
            "",
            "Le nom ne porte que le projet et la chaîne. La géométrie, le",
            "jeu de patchs et le commentaire n'y entrent pas : deux mires",
            "de la même chaîne réglées autrement se disputent ce fichier.",
        ]),
        "",
        "   ▸ Changer le nom de la chaîne     écrit à côté, sans rien effacer",
        "     Remplacer cette mire            ▲ efface celle du 27/08",
        "     Annuler",
    ],
    etat="▲  1 page · 164 pastilles écrites le 27/08 · aucun rang pour cet objet",
    raccourcis="⏎ valider  ↑↓ choisir  Échap retour  F1 aide",
))

# ECRAN NEUF -- la fin de la sequence, forme d'`E5-5`. Il ferme la boucle que
# `E5-5` ouvre (« Générer une planche de calibration — à imprimer avec ») et
# renvoie la ou la mire sert : l'atelier Scan, qui en tire le profil.
#
# **Aucune ligne `Manifest mis a jour` ici, contrairement a `E5-5`.** Je n'ai
# pas mesure ce que la generation de la mire ecrit au manifeste, et une ligne
# affirmee sans mesure est precisement ce que cette passe existe pour retirer.
ecrire("E5-6e-pdf-calibration-resultat.txt", maquette(
    bandeau_gauche="mmu · projet_demo · Pdf · Calibration",
    bandeau_droite="",
    centre=[
        "",
        *cartouche("Écrit", [
            f"● {elider(calibration(CHAINE), 52, QUEUE_MIRE):<54}1 page",
            "",
            f"Chaîne                {CHAINE}",
            "Pastilles             164            130 treillis + 34 témoins",
            "Emplacement           projet_demo/patches/",
            "",
            "À imprimer AVEC les planches, puis à scanner UNE fois : c'est",
            "l'atelier Scan qui en tire le profil de cette chaîne.",
        ]),
        "",
        "   ▸ Ouvrir le dossier",
        "     Générer une autre mire",
        "     Mettre des lots en planches",
        "     Retour aux ateliers",
    ],
    etat="●  1 page écrite · 164 pastilles · aucun refus",
    raccourcis="⏎ choisir  ↑↓ naviguer  Tab journal  Échap ateliers  F1 aide",
))
