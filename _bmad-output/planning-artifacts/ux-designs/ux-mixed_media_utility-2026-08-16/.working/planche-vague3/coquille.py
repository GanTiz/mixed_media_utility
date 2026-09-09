# -*- coding: utf-8 -*-
"""Coquille commune des maquettes, vague 3.

La vague 2 a paye deux fois le meme prix : une correction appliquee dans un
seul ecran, et l'ecran voisin qui garde l'ancienne forme. Ce module est donc le
seul endroit ou vivent la barre de vue, le chutier, le rail et les feuilles de
style -- les builders de la vague 3 n'en recopient rien.
"""
import pathlib, sys

ICI = pathlib.Path(__file__).resolve().parent
V2 = ICI.parent / 'planche-vague2'
sys.path.insert(0, str(V2))

from picto import PICTOS as P          # noqa: E402
from icones import ICONES as _I        # noqa: E402
from icones_v3 import ICONES_V3 as _I3  # noqa: E402

I = dict(_I, **_I3)
from transport import transport        # noqa: E402

MOCKUPS = ICI.parents[1] / 'mockups'

TOKENS = (V2 / 'tokens.css').read_text(encoding='utf-8')
CSS_V2 = (V2 / 'v2-css.css').read_text(encoding='utf-8')
CSS_V3 = (ICI / 'v3-css.css').read_text(encoding='utf-8')
CSS = TOKENS + CSS_V2 + CSS_V3


def barre_vue(*, ajuster=True, loupe=True, pas=True, balayage=None, extra=''):
    """La barre de reglage de vue.

    EPIC7-ARB-17 : le bouton s'intitule « ajuster », jamais « largeur ». Il est
    ici et nulle part ailleurs, pour que la correction ne se perde pas en route
    d'un ecran a l'autre.
    """
    b = []
    if loupe:
        b.append(f'<span class="b">{I["loupe"]}</span>')
        # les pas de zoom n'ont d'objet que sur une image fixe : en lecture on
        # ajuste, ou l'on ouvre la loupe. Les retirer degage aussi la barre,
        # qui debordait sur le panneau dans l'atelier Scan.
        if pas:
            b += ['<span class="b">&minus;</span>', '<span class="b">+</span>']
    if ajuster:
        b.append('<span class="b">Ajuster</span>')
    # EPIC7-ARB-24 : le balayage s'actionne en haut de l'affichage, pas depuis
    # le bus de transport. Et sans le rush natif il reste GRISE au lieu de
    # disparaitre : il redeviendra actionnable au relink -- c'est un controle
    # temporairement indisponible, pas un onglet sans objet.
    if balayage is not None:
        cls = {'on': 'b on', 'off': 'b', 'gris': 'b gris'}[balayage]
        b.append(f'<span class="{cls}" title="Balayage">{I["balayage"]}</span>')
    return f'<div class="vue">{"".join(b)}{extra}</div>'


def replier():
    """La commande de retrait du panneau lateral (EPIC7-ARB-25).

    Elle est la meme sur les quatre ateliers, et une vue qui n'a rien a mettre
    dans le panneau s'ouvre deja retractee.
    """
    return '<span class="replier" title="Retirer le panneau">&rsaquo;</span>'


def onglets(actif, *noms):
    """Les onglets d'un atelier.

    Retour 10 et 11 du 22 aout : les onglets sont « page, galerie, lecteur »,
    et un onglet sans objet est ABSENT -- on ne le grise pas, on ne l'ecrit
    pas. L'appelant ne passe donc que les onglets qui existent sur son ecran.
    """
    return ('<div class="seg">' + ''.join(
        f'<span class="{"on" if n == actif else ""}">{n}</span>' for n in noms)
        + '</div>')


def rail(actif):
    """Le rail des quatre ateliers, celui en cours allume."""
    ordre = [('dossier', 'Projet'), ('rush', 'Extraction'),
             ('planche', 'Scan'), ('encode', 'Exports')]
    return '<div class="rail">' + ''.join(
        (f'<span class="on">{P[k]}</span>' if k == actif else P[k])
        for k, _ in ordre) + '</div>'


def noeud(kind, nom, meta='', *, ouvert=None, puce=None, sel=False, enfants=''):
    exp = '<span class="exp none"></span>'
    if ouvert is True:
        exp = '<span class="exp">&minus;</span>'
    elif ouvert is False:
        exp = '<span class="exp">+</span>'
    pu = f'<span class="puce {puce}"></span>' if puce is not None else ''
    m = f'<span class="meta">{meta}</span>' if meta else ''
    return (f'<div class="node"><div class="row{" sel" if sel else ""}">'
            f'{exp}{pu}{P[kind]}<span class="nm">{nom}</span>{m}</div>'
            + (f'<div class="kids">{enfants}</div>' if enfants else '')
            + '</div>')


def chutier(portee, meta, arbre):
    return f'''      <div class="bin">
        <div class="bin-head"><span class="bin-scope">Chutier</span><span class="meta">{meta}</span></div>
        <div class="portee">Contenu de <b>{portee}</b></div>
        <div class="tree">{arbre}</div>
      </div>'''


def page(titre, sous_titre, corps, commentaire, *, css_extra=''):
    return f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titre} — maquette d'ecran cle</title>
<style>
{CSS}
{css_extra}
</style>
</head>
<body>
<div class="sheet">
  <h1>{titre}</h1>
  <p class="sub">{sous_titre}</p>
{corps}
{commentaire}
</div>
</body>
</html>
'''


def lg(cle, valeur, *, menu=True, libre=False, off=False):
    """Une ligne de reglage : libelle a gauche, valeur a droite.

    EPIC7-ARB-22 : un panneau porte des controles, pas de la prose. Cette
    fonction n'accepte donc pas de texte d'explication -- si un motif doit
    etre dit, il passe par `avis()`, qui est visuellement autre chose.
    """
    car = '<span class="car">&#9662;</span>' if menu else ''
    cls = 'v libre' if libre else 'v'
    return (f'<div class="lg2{" off" if off else ""}"><span class="k">{cle}</span>'
            f'<span class="{cls}">{valeur}{car}</span></div>')


def groupe(titre, *lignes):
    return f'<div class="grp"><span class="tl">{titre}</span>{"".join(lignes)}</div>'


def avis(texte):
    """Le seul texte legitime dans un panneau : un motif qu'aucun controle ne
    peut porter -- pourquoi une action est impossible, pourquoi un nombre a
    change."""
    return f'<div class="avis"><span class="pt"></span><span>{texte}</span></div>'
