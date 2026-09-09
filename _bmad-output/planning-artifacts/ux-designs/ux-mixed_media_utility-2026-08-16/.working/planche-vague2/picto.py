# -*- coding: utf-8 -*-
"""Pictogrammes de l'arbre. Egan : « Remplacer les lettres par des pictogrammes :
dossier, fichier video, fichiers multiples (extract), fichier pdf, scan (fichier
avec une barre de scan), fichiers multiples (lot reconstruit), fichier video. »
Trace au trait, jamais en aplat : un aplat concurrencerait une image jugee."""
def svg(inner, cls=''):
    return (f'<svg class="pi {cls}" viewBox="0 0 16 16" width="15" height="15" fill="none" '
            f'stroke="currentColor" stroke-width="1.2" stroke-linejoin="round" stroke-linecap="round" '
            f'aria-hidden="true">{inner}</svg>')

FICHIER = '<path d="M4 2h5l3 3v9H4z"/><path d="M9 2v3h3"/>'
PICTOS = {
 # dossier de travail
 'dossier': svg('<path d="M2 4.5h4l1.2 1.5H14v7.5H2z"/>'),
 # rush : fichier video
 'rush': svg(FICHIER + '<path d="M6.4 8.2v3.2l2.8-1.6z"/>'),
 # extraction : fichiers multiples
 'extr': svg('<path d="M2.5 4.5h4.5l1.2 1.4H11v7.6H2.5z"/><path d="M5.5 4.5V3h4l3 3v7.5"/>'),
 # planche : fichier pdf
 'planche': svg(FICHIER + '<path d="M5.8 8.6h4.4M5.8 10.6h3"/>'),
 # scan : fichier avec une barre de scan
 'scan': svg(FICHIER + '<path d="M3 9.6h10" stroke-dasharray="1.6 1.2"/>'),
 # lot reconstruit : fichiers multiples, contour tirete parce qu'il est rebati
 'lotr': svg('<path d="M2.5 4.5h4.5l1.2 1.4H11v7.6H2.5z" stroke-dasharray="2 1.4"/><path d="M5.5 4.5V3h4l3 3v7.5" stroke-dasharray="2 1.4"/>'),
 # rush encode : fichier video
 'encode': svg(FICHIER + '<path d="M6.4 8.2v3.2l2.8-1.6z"/>'),
}
