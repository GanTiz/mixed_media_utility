"""Assemble la note commentable de la revue Epic 7.

Reprend les deux gabarits du skill `note-decision-commentable` sans les
recopier : le style de la page, le style et le script de la couche de
commentaires sont extraits a la construction. Seul `corps.html` est ecrit a
la main.
"""

from pathlib import Path
import json
import re

RACINE = Path("/home/user/mixed_media_utility")
GABARITS = RACINE / ".claude/skills/note-decision-commentable/templates"
ICI = Path(__file__).parent
SORTIE = ICI / "note-revue-epic7.html"

TITRE = "Trois lectures de l'interface"


def bloc(texte: str, balise: str, occurrence: int = 0) -> str:
    """Rend la n-ieme paire <balise>...</balise> du texte, bornes comprises."""
    motif = re.compile(rf"<{balise}(?:\s[^>]*)?>.*?</{balise}>", re.S)
    trouves = motif.findall(texte)
    if len(trouves) <= occurrence:
        raise SystemExit(f"bloc <{balise}> n{occurrence} introuvable")
    return trouves[occurrence]


page = (GABARITS / "page-modele.html").read_text(encoding="utf-8")
couche = (GABARITS / "couche-commentaires.html").read_text(encoding="utf-8")
corps = (ICI / "corps.html").read_text(encoding="utf-8")

style_page = bloc(page, "style")
# Les complements propres a cette note, ajoutes apres le style du gabarit.
style_page = style_page.replace(
    "</style>", (ICI / "note-css-extra.css").read_text(encoding="utf-8") + "</style>", 1
)
style_couche = bloc(couche, "style")
script_couche = bloc(couche, "script")

# La seule constante a personnaliser dans la couche (section 5 du workflow).
avant = script_couche
script_couche = script_couche.replace(
    'var TITRE = "Note de decision";', f'var TITRE = "{TITRE}";', 1
)
if script_couche == avant:
    raise SystemExit("la constante TITRE n'a pas ete substituee")

# Les notes deja deposees par Egan dans la page publiee. Republier sans les
# reinjecter les EFFACERAIT : le bloc durable vit dans le HTML publie et nulle
# part ailleurs. Elles sont aussi transcrites au depot, dans
# `retours-note-revue-epic7-2026-08-23.md`, mais la page doit les garder.
durable = ""
fichier_notes = ICI / "notes-durables.json"
if fichier_notes.exists():
    charge = json.loads(fichier_notes.read_text(encoding="utf-8"))
    if charge.get("notes"):
        durable = (
            '<script type="application/json" id="c-durable">'
            + json.dumps(charge, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
            + "</" + "script>"
        )
        print(f"bloc durable reinjecte : {len(charge['notes'])} note(s)")

# La balise viewport va DANS le fichier publie : sans elle un telephone met la
# page en page sur 980 px puis reduit l'ensemble (piege paye le 2026-08-19).
sortie = "\n".join([
    f"<title>{TITRE}</title>",
    '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">',
    "",
    style_page,
    "",
    style_couche,
    "",
    corps.rstrip(),
    "",
    durable,
    script_couche,
    "",
])

SORTIE.write_text(sortie, encoding="utf-8")
print(f"{SORTIE} : {len(sortie.splitlines())} lignes, {len(sortie)} octets")
