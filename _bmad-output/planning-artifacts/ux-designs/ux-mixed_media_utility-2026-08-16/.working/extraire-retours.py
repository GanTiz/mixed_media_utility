# -*- coding: utf-8 -*-
"""Extrait les retours d'Egan d'une planche publiee, vignette par vignette.

Structure visee : .note-block[data-key] > .notes > p.note >
span.body > span.when + texte. Le `when` est IMBRIQUE dans le `body` :
c'est exactement le piege qui avait produit des retours vides le 21 aout
avec une regex non gourmande. On lit donc l'arbre, pas le texte.
"""
import json, sys
from html.parser import HTMLParser


class Planche(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.retours = {}
        self.cle = None
        self.pile = []           # (tag, role)
        self.body = None         # tampon du corps de la note courante
        self.when = None         # tampon de la date de la note courante
        self.dans_when = 0

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cl = d.get('class', '').split()
        role = None
        if 'note-block' in cl:
            self.cle = d.get('data-key') or '?'
            role = 'bloc'
        elif 'body' in cl and self.body is None:
            role = 'body'; self.body = []
        elif 'when' in cl and self.body is not None:
            role = 'when'; self.when = []; self.dans_when += 1
        self.pile.append((tag, role))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        while self.pile:
            t, role = self.pile.pop()
            if t == tag:
                break
        else:
            return
        if role == 'when':
            self.dans_when -= 1
        elif role == 'body':
            texte = ''.join(self.body).strip()
            quand = ''.join(self.when or []).strip()
            if texte.startswith(quand) and quand:
                texte = texte[len(quand):].strip()
            if texte:
                self.retours.setdefault(self.cle or '?', []).append(
                    {'when': quand, 'text': texte})
            self.body = None
            self.when = None

    def handle_data(self, data):
        if self.dans_when:
            self.when.append(data)
        if self.body is not None:
            self.body.append(data)


p = Planche()
p.feed(open(sys.argv[1], encoding='utf-8', errors='replace').read())
print(json.dumps(p.retours, ensure_ascii=False, indent=1))
