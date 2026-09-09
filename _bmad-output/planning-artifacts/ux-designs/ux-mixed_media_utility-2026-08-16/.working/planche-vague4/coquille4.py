# -*- coding: utf-8 -*-
"""Coquille de la vague 4 : elle etend celle de la vague 3, sans la copier.

Meme motif que `planche-vague3/coquille.py`, pour la meme raison : une
correction appliquee dans un seul ecran est une correction perdue.
"""
import pathlib, sys

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / 'planche-vague3'))

from coquille import (MOCKUPS, I, P, barre_vue, onglets, rail, noeud,  # noqa: E402,F401
                      chutier, lg, groupe, avis, replier, transport)
from coquille import CSS as CSS_V3                                      # noqa: E402

CSS = CSS_V3 + (ICI / 'v4-css.css').read_text(encoding='utf-8')


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


def carte(fonction, objet, *, etat='cours', pct=0, fait='', total='',
          passe='', reste='', motif='', boutons=()):
    """Une carte de tache. EPIC7-ARB-23, et l'ordre vient de la spine :

        nom de la fonction, nom du lot, barre, frames/total, temps passe,
        temps restant. Terminee : boutons dossier et fichier -- dossier seul
        quand le resultat est une collection de frames.

    Cet ordre est un contrat, pas une preference de mise en page : c'est ce
    qu'on lit en diagonale quand trois taches tournent.
    """
    if etat == 'cours':
        barre = f'<div class="jauge2"><i style="width:{pct}%"></i></div>'
        chiffres = (f'<div class="tk-nb"><span>{fait} / {total}</span>'
                    f'<span class="tk-t">{passe} &middot; reste {reste}</span></div>')
        pied = ''
    elif etat == 'fini':
        barre = '<div class="jauge2 ok"><i style="width:100%"></i></div>'
        chiffres = (f'<div class="tk-nb"><span>{fait} / {total}</span>'
                    f'<span class="tk-t">en {passe}</span></div>')
        pied = ('<div class="tk-btn">'
                + ''.join(f'<span class="tb2">{b}</span>' for b in boutons)
                + '</div>')
    else:  # 'echec'
        barre = '<div class="jauge2 ko"><i style="width:100%"></i></div>'
        chiffres = (f'<div class="tk-nb"><span>{fait} / {total}</span>'
                    f'<span class="tk-t">arrete apres {passe}</span></div>')
        # le motif vient du coeur, affiche verbatim : on ne traduit pas un
        # code en formule vague.
        pied = f'<div class="tk-motif"><code>{motif}</code></div>'
    return (f'<div class="tk {etat}">'
            f'<div class="tk-h"><span class="tk-f">{fonction}</span>'
            f'<span class="tk-o">{objet}</span></div>'
            f'{barre}{chiffres}{pied}</div>')
