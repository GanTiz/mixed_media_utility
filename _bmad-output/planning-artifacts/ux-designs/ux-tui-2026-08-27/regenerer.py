# -*- coding: utf-8 -*-
"""Regenere les 3 zones SANS perdre les annotations posees en pied de maquette.

Ne jamais lancer `_gen_*.py` directement quand des annotations sont en place: la
garde d'`ecrire()` les protege, donc la campagne echoue -- et si la garde etait
retiree, elles seraient effacees (c'est l'incident du 2026-08-27).

Ce script fait le cycle complet et sur:

1. il **releve** ce que chaque maquette porte au-dela de la grille (annotation
   d'Egan + ligne de traitement) et l'ecrit dans `_notes_sauvegarde.json`;
2. il retire ces lignes, ce qui **desarme** la garde;
3. il relance les trois generateurs, puis le verificateur de grille;
4. il **repose** les lignes relevees, a l'identique.

Si une etape echoue, les notes restent dans le JSON: rien n'est perdu, il suffit
de relancer.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

RACINE = pathlib.Path(__file__).parent
MAQUETTES = RACINE / "maquettes"
SAUVEGARDE = RACINE / "_notes_sauvegarde.json"
HAUTEUR = 24


def relever() -> dict[str, list[str]]:
    """Tout ce qui depasse la grille, maquette par maquette."""
    notes: dict[str, list[str]] = {}
    for chemin in sorted(MAQUETTES.glob("*.txt")):
        lignes = chemin.read_text(encoding="utf-8").rstrip("\n").split("\n")
        queue = lignes[HAUTEUR:]
        if any(l.strip() for l in queue):
            notes[chemin.name] = queue
    return notes


def retirer(notes: dict[str, list[str]]) -> None:
    for nom in notes:
        chemin = MAQUETTES / nom
        lignes = chemin.read_text(encoding="utf-8").rstrip("\n").split("\n")
        chemin.write_text("\n".join(lignes[:HAUTEUR]) + "\n", encoding="utf-8", newline="\n")


def reposer(notes: dict[str, list[str]]) -> int:
    poses = 0
    for nom, queue in notes.items():
        chemin = MAQUETTES / nom
        if not chemin.exists():
            print(f"  [!] {nom} n'existe plus -- sa note reste dans {SAUVEGARDE.name}")
            continue
        lignes = chemin.read_text(encoding="utf-8").rstrip("\n").split("\n")[:HAUTEUR]
        chemin.write_text(
            "\n".join(lignes + queue).rstrip("\n") + "\n", encoding="utf-8", newline="\n"
        )
        poses += 1
    return poses


def sauvegarde_existante() -> dict:
    """Ce que le fichier de sauvegarde porte AVANT que cette passe l'ecrase."""
    if not SAUVEGARDE.exists():
        return {}
    try:
        return json.loads(SAUVEGARDE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def main() -> int:
    notes = relever()
    ancien = sauvegarde_existante()

    # **Ce garde-fou ferme une PERTE DE DONNEES mesuree le 2026-09-02**, pendant
    # la refonte des maquettes `E4-*`.
    #
    # Le mecanisme, et il ne se voit pas a la lecture : l'etape 2 RETIRE les
    # annotations du disque, et l'etape 3 peut echouer apres (une ligne trop
    # large suffit). Le script sort alors en disant, a juste titre, que les
    # annotations sont intactes dans la sauvegarde. Mais au SECOND passage,
    # `relever()` lit des maquettes qui n'en portent plus : il rend un
    # dictionnaire VIDE, et la ligne suivante ecrasait avec ce vide la seule
    # copie qui restait. Trente-huit maquettes ont perdu leurs annotations
    # d'un coup, et rien ne l'a signale -- le script a affiche « 1. relevees :
    # 0 maquettes annotees » comme un constat banal.
    #
    # C'est la meme famille que les faux verts que `CLAUDE.md` collectionne :
    # une operation qui detruit son propre filet en croyant le poser. Le geste
    # correct est de refuser d'ecraser un releve NON VIDE par un releve VIDE --
    # ce cas-la n'est jamais legitime, puisqu'il signifie exactement que les
    # annotations sont deja retirees du disque.
    if ancien and not notes:
        print(f"ABANDON : {SAUVEGARDE.name} porte {len(ancien)} maquettes annotees")
        print("  et le releve du disque est VIDE -- donc les annotations ont deja")
        print("  ete retirees par une passe precedente qui a echoue.")
        print(f"  Les reposer d'abord (`python3 regenerer.py --reposer`), sinon")
        print("  cette passe detruirait la seule copie qui reste.")
        return 2

    SAUVEGARDE.write_text(json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"1. relevees : {len(notes)} maquettes annotees -> {SAUVEGARDE.name}")

    retirer(notes)
    print("2. annotations retirees (garde desarmee)")

    # `_gen_explorateur.py` et `_gen_extraction.py` ne figuraient pas ici : le
    # premier par oubli (il est ne apres ce script), le second parce qu'il
    # n'existait pas. Une maquette produite par un generateur que le cycle sur
    # ne lance pas est une maquette qu'aucune regeneration ne remet a jour --
    # exactement l'ecart que ce script existe pour fermer.
    # `_gen_selection.py` manquait ENCORE a cette liste au 2026-09-01, pour la
    # meme raison que les deux precedents et avec la meme consequence : les
    # trois maquettes `X10`/`X11`/`X11b` ne passaient par aucune regeneration.
    # Verifie avant de l'ajouter -- il rend aujourd'hui exactement ce qui est
    # sur le disque, donc l'ajout ne change aucun octet ; c'est la PROCHAINE
    # retouche du selecteur qu'il fait descendre dans les maquettes.
    for generateur in ("_gen_a.py", "_gen_b.py", "_gen_c.py",
                       "_gen_explorateur.py", "_gen_extraction.py",
                       "_gen_selection.py"):
        issue = subprocess.run(
            [sys.executable, str(RACINE / generateur)], cwd=RACINE, capture_output=True, text=True
        )
        if issue.returncode:
            print(f"3. ECHEC sur {generateur} :\n{issue.stderr}")
            print(f"   Les annotations sont intactes dans {SAUVEGARDE.name}.")
            return 1
    print("3. six generateurs relances (3 zones + explorateur + extraction\n   + selection)")

    controle = subprocess.run(
        [sys.executable, str(RACINE / "verifier_maquettes.py")],
        cwd=RACINE, capture_output=True, text=True,
    )
    print("4. " + controle.stdout.strip().splitlines()[-1])

    print(f"5. annotations reposees sur {reposer(notes)} maquettes")
    return controle.returncode


if __name__ == "__main__":
    # `--reposer` est l'issue que l'abandon ci-dessus nomme. Sans elle, le
    # garde-fou refuserait sans rien offrir -- un blocage sec, exactement ce
    # qu'`EPIC11-ARB-89` proscrit ailleurs dans ce depot.
    if "--reposer" in sys.argv[1:]:
        anciennes = sauvegarde_existante()
        if not anciennes:
            print(f"Rien a reposer : {SAUVEGARDE.name} est vide ou absent.")
            sys.exit(1)
        print(f"annotations reposees sur {reposer(anciennes)} maquettes")
        sys.exit(0)
    sys.exit(main())
