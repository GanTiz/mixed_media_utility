# -*- coding: utf-8 -*-
"""Reduction des captures pour la planche : 1700 px de large, 256 couleurs.

Le tramage est desactive volontairement : sur des aplats de gris R=G=B, il
salit exactement ce que la planche sert a montrer.
"""
import pathlib, sys
from PIL import Image

S = pathlib.Path(sys.argv[1])
for src in sorted(S.glob('hi-key-*.png')):
    slug = src.name[3:]
    dst = S / ('z-' + slug)
    im = Image.open(src).convert('RGB')
    if im.width > 1700:
        im = im.resize((1700, round(im.height * 1700 / im.width)), Image.LANCZOS)
    im.quantize(colors=256, dither=Image.NONE).save(dst, optimize=True)
    print(f'{dst.name}  {dst.stat().st_size/1024:.0f} Ko')
