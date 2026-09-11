"""Resolution du coeur, DES DEUX COTES du sdist (`EPIC8-ARB-21`).

Cette distribution ne porte pas son code : `mixed_media_utility/tui/` vit sous
`src/` a la racine du depot, deux crans plus haut que ce fichier. Deux
declarations de `pyproject.toml` doivent donc le designer -- le `force-include`
de la roue et le chemin de `[tool.hatch.version]` --, et toutes deux l'ecrivaient
en dur, en `../../`.

C'EST CETTE ASYMETRIE, ET ELLE SEULE, qui a force `EPIC8-ARB-18` a publier
`mmu-tui` en ROUE SEULE : `python -m build` construit le sdist PUIS la roue
DEPUIS ce sdist, et dans un sdist extrait il n'y a rien deux crans plus haut.
Mesure du 2026-09-07 : « Forced include not found: <...>/src/mixed_media_utility/tui ».

Le present module ferme l'asymetrie en cherchant le coeur LA OU IL EST plutot
qu'en supposant ou il est : l'arbre de travail le porte en `../../src`, le sdist
en `src/` -- ou le `force-include` du sdist l'a depose. Les deux contextes
repondent, donc `python -m build` nu reussit et l'archive source devient
exploitable.

CE QUE CE MODULE NE FAIT PAS, dit plutot que tu : il ne rend pas `mmu-tui`
autonome. La roue ne porte toujours QUE `tui/`, et le reste du coeur arrive par
`mmu-cli`, dont elle depend a l'unite pres (`EPIC8-ARB-5`). Ce qui change est
qu'une archive source existe et se compile ; pas le decoupage des deux paquets.
"""

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

#: Les deux emplacements possibles du `src/` qui porte le coeur, dans l'ordre
#: ou on les essaie : l'arbre de travail d'abord, le sdist extrait ensuite.
#: L'ordre compte -- une construction faite dans l'arbre de travail doit lire
#: l'arbre de travail, meme si un `src/` traine dans le dossier de packaging.
EMPLACEMENTS = ("../../src", "src")


def racine_du_coeur(racine):
    """Rend le `src/` qui porte `mixed_media_utility/tui`, ou leve en le disant.

    On mesure la presence de `tui` plutot que celle de `src` : un `src/` vide --
    ce qu'un checkout partiel produit -- rendrait sinon un chemin qui echouerait
    plus loin, sur un message de `force-include` que rien ne relie a sa cause.
    """
    racine = Path(racine)
    for emplacement in EMPLACEMENTS:
        candidat = (racine / emplacement).resolve()
        if (candidat / "mixed_media_utility" / "tui").is_dir():
            return candidat
    essayes = ", ".join(str((racine / e).resolve()) for e in EMPLACEMENTS)
    raise FileNotFoundError(
        "le coeur `mixed_media_utility/tui` est introuvable. Essayes : "
        f"{essayes}. Dans l'arbre de travail il vit deux crans plus haut ; dans "
        "un sdist il est embarque sous `src/` par le `force-include` de "
        "`[tool.hatch.build.targets.sdist.force-include]`. Si aucun des deux ne "
        "repond, le checkout est partiel ou le sdist a ete construit sans ce "
        "force-include."
    )


def version_du_coeur():
    """La version se LIT dans le coeur (`EPIC8-ARB-10`), des deux cotes.

    `[tool.hatch.version] path` ne sait pas etre conditionnel : un chemin ecrit
    en dur vaut dans un contexte et pas dans l'autre -- le meme defaut que le
    `force-include`, et il se ferme de la meme facon.

    La source `code` de hatchling IMPORTE ce fichier et evalue une expression,
    sans lui passer de racine : celle-ci se deduit donc de la place de ce
    fichier-ci, qui est par construction le dossier du backend.
    """
    fichier = (racine_du_coeur(Path(__file__).resolve().parent)
               / "mixed_media_utility" / "__init__.py")
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("__version__"):
            return ligne.split("=", 1)[1].strip().strip("\"'")
    raise ValueError(
        f"aucun `__version__` en colonne zero dans {fichier} : c'est la source "
        "UNIQUE de version des deux distributions (EPIC8-ARB-10)")


class CustomBuildHook(BuildHookInterface):
    """Porte `tui/` dans la roue, depuis l'emplacement qui existe.

    Remplace le `[tool.hatch.build.targets.wheel.force-include]` statique, dont
    le chemin ne valait que dans l'arbre de travail.
    """

    def initialize(self, version, build_data):
        source = racine_du_coeur(self.root) / "mixed_media_utility" / "tui"
        build_data["force_include"][str(source)] = "mixed_media_utility/tui"
