# -*- coding: utf-8 -*-
"""Jetons visuels de la GUI -- transcription du frontmatter de ``DESIGN.md``.

Source de verite : ``docs/guide-developpeur/DESIGN.md`` (statut ``final``,
deplace le 2026-09-07 depuis ``_bmad-output/planning-artifacts/``, mis a jour
le 2026-08-23). Ce module TRANSCRIT la spine, il n'invente aucune valeur ;
tout ecart entre ce fichier et la spine est un defaut de ce fichier.

Regles portees par la spine et mesurees par les tests (story 7.0, AC 3) :

* tous les neutres sont strictement neutres, R = G = B -- une coque teintee
  fausse le jugement colorimetrique fait dans l'interface ;
* tout texte sous 18 px tient 4,5:1 contre la surface reelle (WCAG 2.1 AA) ;
  les chromies pleines (``state-*``, ``accent``) sont des valeurs de TRAIT
  et d'APLAT (plancher 3:1 non textuel) et ne portent jamais de glyphe :
  le texte prend la variante ``-text`` ;
* les valeurs de geometrie du chrome (defauts, planchers, seuils) vivent
  ici et seulement ici : les composants les LISENT, aucun nombre de
  geometrie n'est ecrit en dur dans ``coquille.py``.

Aucune couleur hexadecimale n'existe dans ``gui/`` hors de ce module
(frontiere negative de l'AC 3, mesuree par grep).
"""

# ---------------------------------------------------------------------------
# Couleurs (DESIGN.md, frontmatter ``colors``).
# ---------------------------------------------------------------------------

# Neutres. Invariant absolu : R = G = B sur TOUTES les valeurs de ce
# dictionnaire (teste par iteration complete, jamais par echantillon).
NEUTRES = {
    # La coque, du plus enfonce au plus leve.
    "surface-sunken": "#0E0E0E",   # zone tampon, fosses
    "surface-canvas": "#141414",   # fond d'atelier
    "surface-panel": "#1C1C1C",    # chutier, panneau lateral, barres
    "surface-raised": "#242424",   # cartes, champs, boutons
    "surface-hover": "#2E2E2E",
    "border": "#383838",
    "border-strong": "#4A4A4A",
    "text-primary": "#E8E8E8",
    "text-secondary": "#9A9A9A",
    "text-disabled": "#6A6A6A",
    # Le mat : le neutre pose autour de toute zone d'image jugee.
    "image-mat": "#2B2B2B",
    # Papier : substrat d'une page (apercu PDF, scan). Blanc vrai, jamais casse.
    "paper": "#FFFFFF",
    "paper-ink": "#111111",
    # Surimpressions de scan : traits a halo, jamais aplats.
    "overlay-halo": "#000000",
    "overlay-handle": "#FFFFFF",
}

# Accent. Une seule chromie de coque : selection, focus, activite en cours.
# Jamais un verdict, jamais a moins de ESPACEMENTS["mat-min"] d'une image.
ACCENT = {
    "accent": "#4C7EF3",
    "accent-pressed": "#3A63C4",
    "accent-on": "#FFFFFF",
}

# Semantiques metier. Separees de l'accent, non interchangeables entre elles.
# Valeurs de TRAIT et d'APLAT (3:1 non textuel), jamais de texte.
SEMANTIQUES = {
    "state-complete": "#3FBF6F",     # vert : c'est fini, c'est complet
    "state-absent": "#E5484D",       # rouge : il n'y a rien ici
    "state-substitute": "#F5A623",   # ambre : present, mais pas ton image
}

# Variantes de TEXTE des chromies ci-dessus : meme teinte, clarte relevee,
# plancher 4,5:1 tenu sur les cinq neutres porteurs (DESIGN.md, "Plancher
# de contraste"). Tout texte sous 18 px portant une chromie prend ceci.
VARIANTES_TEXTE = {
    "state-complete-text": "#4EC57A",
    "state-absent-text": "#EE878A",
    "state-substitute-text": "#F5A623",   # inchangee : deja au-dessus du plancher
    "accent-text": "#8FAEF7",
}

# Dictionnaire complet, pour les emplois qui adressent un jeton par nom.
COULEURS = {**NEUTRES, **ACCENT, **SEMANTIQUES, **VARIANTES_TEXTE}

# Opacite du fond d'un badge d'etat : 16 % de la chromie pleine, compose
# sur la surface porteuse (DESIGN.md, ``badge-state``).
BADGE_FOND_OPACITE = 0.16

# ---------------------------------------------------------------------------
# Typographie (DESIGN.md, frontmatter ``typography``). L'echelle est courte
# et n'a aucune taille au-dessus de 18 px hors ``display`` : le plancher de
# 4,5:1 couvre donc tout le texte du produit.
# ---------------------------------------------------------------------------

FAMILLE_INTERFACE = '-apple-system, "Segoe UI", system-ui, sans-serif'
FAMILLE_DONNEES = '"SF Mono", Menlo, Consolas, "Cascadia Mono", monospace'

TYPOGRAPHIE = {
    # ecran de gestion de projet, uniquement
    "display": {"famille": FAMILLE_INTERFACE, "taille": 28, "graisse": 600, "interligne": 1.2},
    # titre d'atelier, en-tete de modale
    "title": {"famille": FAMILLE_INTERFACE, "taille": 15, "graisse": 600, "interligne": 1.3},
    # tout le reste
    "body": {"famille": FAMILLE_INTERFACE, "taille": 13, "graisse": 400, "interligne": 1.45},
    # en-tetes de section, capitales espacees (0.08em)
    "label": {"famille": FAMILLE_INTERFACE, "taille": 11, "graisse": 600, "interligne": 1.35,
              "espacement-lettres": 0.08},
    # donnees : monospace a chiffres tabulaires OBLIGATOIRES (tabular-nums)
    "data": {"famille": FAMILLE_DONNEES, "taille": 12, "graisse": 400, "interligne": 1.4},
    "data-lg": {"famille": FAMILLE_DONNEES, "taille": 16, "graisse": 400, "interligne": 1.3,
                "espacement-lettres": 0.04},
    "data-sm": {"famille": FAMILLE_DONNEES, "taille": 11, "graisse": 400, "interligne": 1.35},
}

# ---------------------------------------------------------------------------
# Rayons (DESIGN.md, frontmatter ``rounded``), en pixels.
# ---------------------------------------------------------------------------

RAYONS = {
    "none": 0,
    "sm": 4,
    "md": 6,      # DEFAULT de la spine
    "lg": 8,
    "xl": 10,
    "full": 9999,
}

# ---------------------------------------------------------------------------
# Espacements et largeurs de chrome (DESIGN.md, frontmatter ``spacing``),
# en pixels. Echelle de base 4 px ; rien au-dela de 32 : rien dans cet
# outil ne respire, tout se voit d'un coup.
# ---------------------------------------------------------------------------

ESPACEMENTS = {
    "1": 2, "2": 4, "3": 6, "4": 8, "5": 12, "6": 16, "7": 24, "8": 32,
    "gutter": 12,
    "panel-pad": 10,
    "mat-min": 16,          # bande de neutre minimale autour d'une image
    "row-height": 28,
    "hit-min": 24,          # cible de clic minimale
    "header-height": 44,
    "transport-height": 44,
    "tabbar-height": 54,
    # Largeurs du chrome (EPIC7-ARB-40) : DEFAUTS et PLANCHERS ; le plafond
    # de chaque poignee est DERIVE, jamais constant (largeur de fenetre -
    # chrome restant - stage-min-width). Voir coquille.py.
    "tree-panel-width": 196,       # panneau d'arborescence, defaut
    "tree-panel-min-width": 160,   # plancher de la poignee
    "tree-panel-rail": 42,         # meme panneau retracte : rail
    "splitter-width": 5,           # poignee de largeur, zone saisissable
    "bin-width": 330,              # chutier, defaut
    "bin-min-width": 250,          # plancher de la poignee
    "side-panel-width": 300,       # panneau lateral de reglages (droite)
    "queue-width": 320,            # panneau de progression / file des taches
    "stage-min-width": 640,        # scene : plancher, jamais franchi
    "window-min-width": 960,
    "window-min-height": 680,
    # Seuils de largeur de fenetre, ordonnes : 960 < 1180 < 1500.
    "queue-overlay-threshold": 1500,  # sous ce seuil la file passe en superposition (7.3)
    "tree-collapse-threshold": 1180,  # sous ce seuil l'arborescence se replie seule
}

# ---------------------------------------------------------------------------
# Planchers de contraste (DESIGN.md, "Plancher de contraste", pose le
# 2026-08-23). Les tests CALCULENT les ratios (WCAG 2.1) ; ces deux jetons
# ne portent que les seuils exiges.
# ---------------------------------------------------------------------------

CONTRASTE_TEXTE_MIN = 4.5      # tout texte sous 18 px (l'echelle n'en a pas au-dessus hors display)
CONTRASTE_NON_TEXTUEL_MIN = 3.0  # composants graphiques : bordures, barres, traits


# ---------------------------------------------------------------------------
# Iconographie (story 7.2). `DESIGN.md` ne fixe pas de jeu d'icones -- c'est
# une DEPENDANCE NOMMEE, sans titulaire --, mais il fixe la **boite** dans
# laquelle une story de chutier a le droit de partir avec des pictogrammes
# provisoires : « 15 x 15 px, trait 1,2 px, `currentColor`, jamais un aplat
# colore ». Ces deux valeurs vivent ici pour que la substitution future du
# jeu d'icones reste un remplacement d'ASSETS, jamais une reprise de mise en
# page.
# ---------------------------------------------------------------------------

ICONOGRAPHIE = {
    "boite-px": 15,        # cote de la boite d'un pictogramme
    "trait-px": 1.2,       # graisse du trait, en pixels
    "glyphe-px": 14,       # `state-glyph`, typographie `data`
    "glyphe-incomplet-px": 15,  # U+26A0, dont l'oeil est plus petit
}


def composer_sur(chromie, surface, opacite=BADGE_FOND_OPACITE):
    """Composer une chromie a `opacite` sur la surface qui la porte.

    Le fond d'un `badge-state` est « 16 % de la chromie pleine **compose sur
    la surface porteuse** » (`DESIGN.md`). Composer, et non poser une
    transparence : le plancher de contraste du texte du badge est mesure
    contre la couleur REELLEMENT obtenue, et une transparence rendrait cette
    couleur dependante de ce qui se trouve dessous.

    Les deux entrees sont des chaines `#RRGGBB` du dictionnaire de couleurs
    ci-dessus ; la sortie l'est aussi.
    """
    avant = [int(chromie[indice:indice + 2], 16) for indice in (1, 3, 5)]
    fond = [int(surface[indice:indice + 2], 16) for indice in (1, 3, 5)]
    melange = [
        round(opacite * canal + (1.0 - opacite) * base)
        for canal, base in zip(avant, fond)
    ]
    return "#" + "".join(f"{canal:02X}" for canal in melange)


# ---------------------------------------------------------------------------
# Geometrie des surimpressions de scan (story 7.4, AC 6). Bloc ajoute en fin
# de fichier pour ne pas croiser les editions d'une autre story sur ce meme
# module.
#
# TRANSCRIPTION, sans invention : chaque valeur est lue du frontmatter de
# `DESIGN.md` (`components.overlay-zone`, `components.overlay-handle`,
# `components.viewer-stage`, `components.frame-thumb`) et rien d'autre.
# Elles vivent ici parce que la docstring de ce module l'impose -- « les
# valeurs de geometrie du chrome (defauts, planchers, seuils) vivent ici et
# seulement ici » -- et parce qu'un litteral `1.5`, `3` ou `11` seme dans un
# module de dessin est precisement ce que le grep de frontiere de l'AC 6
# interdit.
# ---------------------------------------------------------------------------

SURIMPRESSIONS = {
    # `overlay-zone.stroke-width: 1.5px` -- trait, jamais aplat.
    "trait-px": 1.5,
    # `overlay-zone.halo-width: 3px` -- le halo passe SOUS le trait ; c'est
    # lui qui rend la surimpression lisible aussi bien sur une marge de
    # papier blanc que sur une zone peinte a la gouache.
    "halo-px": 3,
    # `overlay-handle.size: 11px` -- le carre d'une poignee de coin. La
    # poignee elle-meme est 7.5 : le jeton descend ici parce que la spine
    # le pose dans la meme famille et que l'AC 6 le nomme.
    "poignee-px": 11,
}

#: `viewer-stage.content-radius: {rounded.none}` -- l'exception de
#: `DESIGN.md` : « Le cadre autour de l'image peut etre arrondi ; l'image,
#: jamais. » Le cadre garde `viewer-stage.radius = {rounded.lg}`.
RAYON_CONTENU_IMAGE = RAYONS["none"]

#: `viewer-stage.radius: {rounded.lg}` -- le CADRE, lui, est arrondi.
RAYON_CADRE_SCENE = RAYONS["lg"]

#: `frame-thumb.opacity-deselected: 0.32` -- une vignette non designee
#: s'efface, elle ne disparait pas.
OPACITE_VIGNETTE_NON_DESIGNEE = 0.32


# ---------------------------------------------------------------------------
# Zone tampon et carte de tache (story 7.3). Bloc ajoute en fin de fichier
# pour ne pas croiser les editions d'une autre story sur ce meme module.
#
# TRANSCRIPTION, sans invention : chaque valeur est lue du frontmatter de
# `DESIGN.md` (`components.bin-buffer`, `spacing.queue-width`) et du corps de
# la spine (« Carte de tache (panneau de progression) »). Les deux
# dictionnaires composent des jetons deja definis plus haut plutot que de
# recopier une valeur : une chromie recopiee diverge le jour ou la spine la
# change, et le grep de frontiere ne verrait rien.
# ---------------------------------------------------------------------------

ZONE_TAMPON = {
    # `bin-buffer` : la file est une surface ENFONCEE, bordee en pointille --
    # c'est ce qui la dit provisoire, sans y ajouter le moindre libelle.
    "fond": NEUTRES["surface-sunken"],
    "bordure": NEUTRES["border"],
    "style-de-bordure": "dashed",
    "texte": NEUTRES["text-secondary"],
    "rayon": RAYONS["md"],
    # Combien de lignes la file montre avant de defiler. `DESIGN.md` ne fixe
    # pas ce cardinal -- il fixe la POSITION (« haut du chutier, au-dessus de
    # l'arbre »), donc la file ne doit jamais manger l'arbre. Six lignes est le
    # choix de la story 7.3, pose ICI parce que la docstring de ce module
    # l'exige : « les valeurs de geometrie du chrome vivent ici et seulement
    # ici ». C'est une DEPENDANCE NOMMEE a la spine, pas une transcription.
    "lignes-visibles": 6,
}

CARTE_DE_TACHE = {
    # « Carte de tache (panneau de progression) » : `surface-raised`,
    # `rounded.lg`, largeur `queue-width` (320).
    "fond": NEUTRES["surface-raised"],
    "rayon": RAYONS["lg"],
    "largeur": ESPACEMENTS["queue-width"],
    # Le nom de la fonction en `label` sur la VARIANTE DE TEXTE de l'accent :
    # l'accent plein n'atteint que 4,13:1 en 11 px sur cette surface, la
    # spine le dit explicitement.
    "titre": VARIANTES_TEXTE["accent-text"],
    # « Terminee : bordure et barre en `state-complete`. » L'echec n'est pas
    # decrit par la spine ; il prend la seule semantique qui dit « il n'y a
    # rien ici », et jamais l'accent -- une activite n'est pas un verdict.
    "bordure": NEUTRES["border"],
    "bordure-terminee": SEMANTIQUES["state-complete"],
    "bordure-echouee": SEMANTIQUES["state-absent"],
    # Le texte d'un motif d'echec : chromie de TEXTE, jamais l'aplat.
    "texte-echec": VARIANTES_TEXTE["state-absent-text"],
}


# ---------------------------------------------------------------------------
# Bascule brut / corrige de l'en-tete (story 7.4, AC 8, `EPIC7-ARB-69`).
#
# L'icone vit dans la table d'iconographie et **jamais en glyphe litteral
# dans un ecran** : c'est la condition posee par l'AC pour que la
# substitution future du jeu d'icones reste un remplacement d'ASSETS. Elle
# reste dans la boite provisoire fixee par `DESIGN.md` -- « 15 x 15 px,
# trait 1,2 px, `currentColor`, jamais un aplat colore ».
# ---------------------------------------------------------------------------

ICONOGRAPHIE.update({
    # Demi-disque : la meme image montree de deux facons, brut d'un cote,
    # corrige de l'autre.
    "glyphe-bascule-image": "◐",
    "glyphe-bascule-image-px": 14,
    # Croix de retrait, sur la ligne de l'ecran de projet (correctif du
    # 2026-08-26). Meme condition que ci-dessus : elle vit ici et pas en
    # litteral dans `ecran_projet.py`. Une croix MULTIPLICATIVE (U+2715) et
    # non la lettre x ni le signe de fermeture d'une fenetre -- le geste
    # retire une ligne d'une liste, il ne ferme rien et ne detruit rien.
    "glyphe-retirer": "✕",
    "glyphe-retirer-px": 14,
    # --- fin des fleches Qt natives (passe de chrome du 2026-08-26) -------
    # `QToolButton.setArrowType` posait de gros triangles bleus au STYLE DE LA
    # PLATEFORME a cinq endroits : l'epingle d'une ligne de projet, le repli et
    # la reouverture de l'arborescence, le plein ecran du chutier. Ce n'etait
    # pas un choix de design, c'etait un provisoire jamais repris -- « aucun
    # bouton », premier essai de terrain d'Egan. Les maquettes mettent a ces
    # endroits des pastilles compactes portant un signe.
    #
    # Comme les deux ci-dessus, ils vivent ICI et jamais en litteral dans un
    # ecran : c'est la condition posee par l'AC 8 de 7.4 pour que la
    # substitution future du jeu d'icones reste un remplacement d'assets.
    "glyphe-epingle": "◆",        # epingle posee : un plein, il retient
    "glyphe-epingle-absente": "◇",  # epingle libre : le meme, en creux
    "glyphe-replier": "⟨",        # vers la gauche : le panneau s'en va
    "glyphe-rouvrir": "⟩",        # vers la droite : il revient
    "glyphe-plein-ecran": "⤢",    # les deux diagonales : on prend la place
    "glyphe-plein-ecran-sortie": "⤡",  # la meme, rentree
})


# ---------------------------------------------------------------------------
# Les pictogrammes de l'arbre, TRANSCRITS des maquettes (2026-08-26).
#
# Jusqu'ici `chutier.pictogramme()` les dessinait a la main : un rectangle et
# deux traits pour un rush, deux rectangles decales pour un lot. C'etait un
# provisoire assume (« aucun jeu d'icones n'est arrete ») et il ne ressemblait a
# rien -- Egan : « les icones ne correspondent pas du tout a ce qui avait ete
# maquette ».
#
# Or les maquettes portent les tracés EXACTS, en SVG 16x16, trait 1,2 px,
# `currentColor` : `key-chutier-v2.html` les pose sur chaque noeud de son arbre.
# Ils sont donc recopies ici verbatim plutot que redessines -- c'est la seule
# facon que « conforme a la maquette » veuille dire quelque chose de verifiable.
#
# Ils vivent dans la table d'iconographie et **jamais en litteral dans un
# ecran** : condition posee par l'AC 8 de la story 7.4 pour que la substitution
# du jeu d'icones reste un remplacement d'assets. Un chemin est de la DONNEE,
# pas du dessin : le composant les rend, il ne les invente pas.
# ---------------------------------------------------------------------------

TRACES_DE_NOEUD = {
    # Un rush : la page a coin corne, traversee du triangle de lecture.
    "rush": ("M4 2h5l3 3v9H4z", "M9 2v3h3", "M6.4 8.2v3.2l2.8-1.6z"),
    # Un lot : deux dossiers decales -- une collection, pas un fichier.
    "lot": ("M2.5 4.5h4.5l1.2 1.4H11v7.6H2.5z", "M5.5 4.5V3h4l3 3v7.5"),
    # Une planche : la page, et les lignes de ce qui y est imprime.
    "planche": ("M4 2h5l3 3v9H4z", "M9 2v3h3", "M5.8 8.6h4.4M5.8 10.6h3"),
    # Un scan : la page, traversee de la ligne POINTILLEE du capteur.
    "scan": ("M4 2h5l3 3v9H4z", "M9 2v3h3", ("M3 9.6h10", "1.6 1.2")),
    # Un lot reconstruit : le lot, en POINTILLE -- il n'a pas ete filme, il a
    # ete refait. La maquette dit la reconstruction par le trait, pas par une
    # couleur : c'est la redondance non chromatique qu'exige `DESIGN.md`.
    "lot-reconstruit": (
        ("M2.5 4.5h4.5l1.2 1.4H11v7.6H2.5z", "2 1.4"),
        ("M5.5 4.5V3h4l3 3v7.5", "2 1.4"),
    ),
    # Un rush encode : c'est un rush, et la maquette lui donne la meme image
    # (`rush-12p5-reconstruit.mov` porte le trace du rush).
    "rush-encode": ("M4 2h5l3 3v9H4z", "M9 2v3h3", "M6.4 8.2v3.2l2.8-1.6z"),
}


def pictogrammes() -> frozenset:
    """Les glyphes de la table d'iconographie, tels qu'ils s'affichent.

    Un PICTOGRAMME n'est pas un libelle : il ne se traduit pas, et la regle
    ci-dessus lui impose meme de ne jamais vivre dans un ecran. Les tests de
    substitution de catalogue -- qui verifient qu'aucun texte affiche n'est
    ecrit en dur -- doivent donc l'exempter, sans quoi ils exigeraient de lui
    d'etre a la fois une chaine traduisible et un asset.

    La liste se DERIVE de la table plutot que d'etre recopiee dans les tests :
    une icone ajoutee ci-dessus est exemptee sans qu'on y pense, et une icone
    retiree cesse de l'etre. Deux fichiers de test la recopiaient a la main
    avant cette fonction.
    """
    return frozenset(
        valeur
        for cle, valeur in ICONOGRAPHIE.items()
        if cle.startswith("glyphe-") and isinstance(valeur, str)
    )


# ---------------------------------------------------------------------------
# Retours de terrain du 2026-08-27. Pose en un seul geste avant les trois lots
# de correction, pour qu'aucun d'eux n'ait a editer ce fichier.
# ---------------------------------------------------------------------------

ICONOGRAPHIE.update({
    # `EPIC7-ARB-92` -- la maison de l'en-tete. Un glyphe, jamais un aplat
    # colore : meme boite et meme regle que les autres (voir la docstring de
    # `pictogrammes`).
    "glyphe-accueil": "⌂",
    "glyphe-accueil-px": 15,
    # `EPIC7-ARB-94` -- les expandeurs de l'arborescence. Ils remplacent la
    # fleche native, qui se peint au style de la PLATEFORME (le meme defaut
    # que la passe de chrome du 2026-08-26 a corrige ailleurs).
    "glyphe-deplier": "+",
    "glyphe-replier-niveau": "−",  # U+2212, signe moins, jamais un trait d'union
    "glyphe-expandeur-px": 13,
})

#: `EPIC7-ARB-94` -- geometrie des traits de filiation de l'arborescence.
#: Aucune de ces valeurs n'est un litteral dans un module de dessin : la
#: docstring de ce module impose que la geometrie du chrome vive ici et
#: seulement ici.
ARBORESCENCE = {
    "trait-px": 1,          # graisse d'un trait de filiation
    "expandeur-boite-px": 11,  # cote de la boite carree de l'expandeur
    "lisere-selection-px": 2,  # largeur du lisere d'accent, colonne du libelle
}
