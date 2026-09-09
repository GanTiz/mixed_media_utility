# -*- coding: utf-8 -*-
"""Icones ajoutees a la vague 3, dans le meme trait que celles de la vague 2.

Le fichier de la vague 2 n'est pas retouche : il porte les icones telles
qu'Egan les a validees le 22 aout, et une maquette deja publiee ne doit pas
changer sous lui.
"""
from icones import i

ICONES_V3 = {
 # balayage : deux moities d'un meme cadre, separees par la poignee
 'balayage': i('<rect x="2.4" y="3.4" width="11.2" height="9.2" rx="1"/>'
               '<path d="M8 3.4v9.2"/>'
               '<path d="M9.6 6.4h3.2M9.6 8h3.2M9.6 9.6h3.2"/>'),
}
