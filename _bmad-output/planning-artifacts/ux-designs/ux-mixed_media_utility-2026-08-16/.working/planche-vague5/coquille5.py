# -*- coding: utf-8 -*-
"""Coquille de la vague 5 : elle etend celle de la vague 4, sans la recopier."""
import pathlib, sys

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / 'planche-vague4'))

from coquille4 import (MOCKUPS, I, P, barre_vue, onglets, rail, noeud,  # noqa: E402,F401
                       chutier, lg, groupe, avis, replier, transport, carte)
from coquille4 import CSS as CSS_V4                                      # noqa: E402

CSS = CSS_V4 + (ICI / 'v5-css.css').read_text(encoding='utf-8')


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


def entree(libelle, *, raccourci='', coche=None, sous=False, gris=False,
           separateur_avant=False, fleche=False):
    """Une entree de menu -- contextuel ou barre de menus.

    Un seul rendu pour les deux : ce sont les memes objets, et les ecrire deux
    fois garantissait qu'ils divergent.
    """
    sep = '<div class="msep"></div>' if separateur_avant else ''
    c = ''
    if coche is True:
        c = '<span class="mck">&#10003;</span>'
    elif coche is False:
        c = '<span class="mck"></span>'
    r = f'<span class="mrc">{raccourci}</span>' if raccourci else ''
    f = '<span class="mfl">&rsaquo;</span>' if fleche else ''
    cls = 'mi' + (' gris' if gris else '') + (' sous' if sous else '')
    return f'{sep}<div class="{cls}">{c}<span class="ml">{libelle}</span>{r}{f}</div>'


def menu(titre, *entrees, largeur=250):
    t = f'<div class="mtitre">{titre}</div>' if titre else ''
    return (f'<div class="menu2" style="width:{largeur}px">{t}'
            + ''.join(entrees) + '</div>')
