# -*- coding: utf-8 -*-
"""Icones du transport. Egan, 22 aout : « Placer tous les controles sous
l'image. En une seule ligne. Pas de texte, que des icones. » Tracees au trait,
16x16, jamais en aplat."""
def i(inner, cls=''):
    return (f'<svg class="ic {cls}" viewBox="0 0 16 16" width="14" height="14" fill="none" '
            f'stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round" '
            f'aria-hidden="true">{inner}</svg>')

TRI_D = 'M6 4.4 11.4 8 6 11.6z'
TRI_G = 'M10 4.4 4.6 8 10 11.6z'
ICONES = {
 # aller au point d'entree / de sortie : les deux boutons extremes
 'au_in':   i('<path d="M3.6 4v8"/><path d="M11.6 4.4 5.6 8l6 3.6z" fill="currentColor" stroke="none"/>'),
 'au_out':  i('<path d="M12.4 4v8"/><path d="M4.4 4.4 10.4 8l-6 3.6z" fill="currentColor" stroke="none"/>'),
 # lecture arriere et avant, avec multiplicateur
 'arriere': i('<path d="M8.2 4.6 3.6 8l4.6 3.4z" fill="currentColor" stroke="none"/><path d="M13 4.6 8.4 8 13 11.4z" fill="currentColor" stroke="none"/>'),
 'avant':   i('<path d="M7.8 4.6 12.4 8l-4.6 3.4z" fill="currentColor" stroke="none"/><path d="M3 4.6 7.6 8 3 11.4z" fill="currentColor" stroke="none"/>'),
 # image par image
 'img_p':   i('<path d="M4.2 4.5v7"/><path d="M11.5 4.8 6.6 8l4.9 3.2z" fill="currentColor" stroke="none"/>'),
 'img_s':   i('<path d="M11.8 4.5v7"/><path d="M4.5 4.8 9.4 8l-4.9 3.2z" fill="currentColor" stroke="none"/>'),
 'lecture': i('<path d="M5 3.6 12.6 8 5 12.4z" fill="currentColor" stroke="none"/>'),
 'pause':   i('<path d="M5.8 4v8M10.2 4v8"/>'),
 # poser l'entree, poser la sortie
 'poser_in':  i('<path d="M4 3.6v8.8"/><path d="M4 3.6h4.6M4 12.4h4.6"/><path d="M11.2 8h1.6"/>'),
 'poser_out': i('<path d="M12 3.6v8.8"/><path d="M7.4 3.6H12M7.4 12.4H12"/><path d="M3.2 8h1.6"/>'),
 'retirer': i('<path d="M4 4l8 8M12 4l-8 8"/>'),
 'marqueur': i('<path d="M4.6 2.8h6.8v10.4L8 10.6l-3.4 2.6z"/><path d="M8 5.2v3M6.5 6.7h3"/>'),
 'boucle':  i('<path d="M3.4 7.2a4.6 4.6 0 0 1 4.6-4.4h4.6"/><path d="M10.4 1.2 12.8 2.8 10.4 4.4"/><path d="M12.6 8.8a4.6 4.6 0 0 1-4.6 4.4H3.4"/><path d="M5.6 14.8 3.2 13.2l2.4-1.6"/>'),
 'son':     i('<path d="M3.4 6.2h2.2l3-2.4v8.4l-3-2.4H3.4z"/><path d="M10.8 6a3 3 0 0 1 0 4"/>'),
 'loupe':   i('<circle cx="7" cy="7" r="4.2"/><path d="M10.2 10.2 13.6 13.6"/>'),
}
