# -*- coding: utf-8 -*-
"""Point d'entree de la TUI : `python -m mixed_media_utility.tui`.

Les deux scripts jumeaux `bin/mmu-tui` et `bin/mmu-tui.cmd` n'ont pas d'autre
role que d'appeler ce module avec `src/` sur le `PYTHONPATH` : le depot
n'installe rien (aucun `pip install`, aucun `console_scripts` -- `pyproject.toml`
ne porte que `[tool.mutmut]`).

**Les deux modes de repli suivent une convention plutot qu'une invention**
(question 2 de la fiche 11.0) :

* la couleur s'eteint par ``NO_COLOR`` -- la convention etablie, honoree par
  bien d'autres outils du terminal -- et l'option ``--sans-couleur`` n'en est
  que la forme explicite ;
* le repli ASCII n'a **pas** de convention d'environnement etablie, il n'en
  recoit donc pas une inventee : seule l'option ``--ascii`` l'active.

**ARBITRAGE ROUVERT le 2026-09-06, et il faut le dire plutot que le
contourner.** Le point precedent tient toujours pour les VARIABLES
D'ENVIRONNEMENT -- aucune n'est inventee, et ``--ascii`` reste la seule facon
de *demander* le repli. Ce qui change est autre chose : Egan a rapporte du
terrain deux glyphes illisibles sous console Windows (« le symbole "Enter"
[...] devient illisible », « le glyphe d'attente [...] n'est pas rendu par un
terminal windows natif ») et a demande explicitement « prevoyons un repli, si
possible automatique ». Le repli est donc **aussi** deduit de l'hote, par
:func:`repli_ascii_conseille`.

Trois choses le distinguent d'une convention inventee, et ce sont elles qui
rendent la reouverture soutenable :

* elle ne lit **aucune variable a nous** : elle lit ce que l'HOTE pose de
  lui-meme (``WT_SESSION``, ``TERM_PROGRAM``) et ce que ``rich`` sait deja de
  la console ;
* elle est **debrayable dans les DEUX sens** : ``--ascii`` force le repli,
  ``--utf8`` (alias ``--pas-d-ascii``) le refuse. Livrer une detection sans son
  echappatoire remplacerait un defaut visible par un defaut non contournable ;
* elle est **conservatrice et jamais une preuve** : aucune API ne repond a
  « cette police contient-elle U+23CE ? ». Voir le docstring de la fonction.

**« Forcer un PowerShell » ne peut rien y changer, par construction** (mesure
du 2026-09-06) : PowerShell est un *shell*, il ecrit des octets sur un handle
de console. Le glyphe est dessine par l'HOTE -- ``conhost.exe``, Windows
Terminal, le terminal de VS Code -- avec la police que cet hote a chargee. Le
facteur discriminant est le couple **hote + police**, pas le shell, ni meme
« Windows ».

**Ce point d'entree monte la chaine REELLE des paliers depuis la story 11.4**
(lot `E9`). Il construisait auparavant `CoqueTui()` **sans paliers**, donc
`coque.paliers_temoins()` : mesure du 2026-08-29,
``[type(p).__name__ for p in CoqueTui()._paliers]`` rendait
``['PalierTemoin', 'PalierTemoin', 'PalierTemoin']``. `mmu-tui` ouvrait donc
trois ecrans **temoins**, alors qu'`EcranProjet` (story 11.2) et `EcranAteliers`
(story 11.3) etaient livres et testes : ils n'etaient cables nulle part dans
l'application, seulement dans les bancs et dans `demo_vague_2.py`, qui assemble
la chaine a la main. C'est exactement ce qui a masque le manque pendant deux
vagues -- la recette manuelle passait par la demo, jamais par le produit.

Le montage lui-meme vit dans :class:`~mixed_media_utility.tui.\
atelier_extraction_ecriture.ChaineReelle` et non ici : ce module ne fait que
lire la ligne de commande, et le cablage des paliers se mesure sans lancer de
terminal.
"""
from __future__ import annotations

import argparse
import os
import sys
import unicodedata


def analyser(argv: list[str] | None = None) -> argparse.Namespace:
    """Lit la ligne de commande. Les valeurs par defaut lisent l'environnement."""
    analyseur = argparse.ArgumentParser(
        prog="mmu-tui",
        description="Interface en terminal de mixed_media_utility.",
    )
    analyseur.add_argument(
        "--sans-couleur", action="store_true",
        # `NO_COLOR` : la convention veut que la SEULE presence de la variable
        # compte, quelle que soit sa valeur -- y compris vide.
        default="NO_COLOR" in os.environ,
        help="n'emettre aucune couleur (l'information reste portee par les "
             "glyphes). Actif d'office si NO_COLOR est pose.",
    )
    # **Les deux sens du meme reglage, et ils s'excluent.** `--ascii` etait
    # seul jusqu'au 2026-09-06 : il n'y avait qu'un opt-in vers l'ASCII, donc
    # aucun moyen de refuser un repli qu'on n'avait pas demande. Depuis que le
    # repli se DEDUIT aussi de l'hote (voir `repli_ascii_conseille`), son
    # inverse est obligatoire -- un operateur dont l'heuristique se trompe doit
    # pouvoir recuperer ses glyphes sans lire le code.
    mode = analyseur.add_mutually_exclusive_group()
    mode.add_argument(
        "--ascii", action="store_true", dest="ascii_seul",
        help="remplacer les glyphes UTF-8 par leur repli ASCII, pour les "
             "consoles dont la police n'a pas les caracteres de la table.",
    )
    mode.add_argument(
        "--utf8", "--pas-d-ascii", action="store_true", dest="pas_d_ascii",
        help="garder les glyphes UTF-8 meme si la console a l'air de ne pas "
             "les rendre. C'est l'echappatoire quand la detection se trompe.",
    )
    analyseur.add_argument(
        "--diagnostic-chemin", action="store_true",
        help="afficher les chemins d'import vus par la TUI, puis sortir. "
             "C'est la mesure du lancement : elle dit ce que le script "
             "jumeau a reellement pose sur PYTHONPATH.",
    )
    return analyseur.parse_args(argv)


#: Ce que la detection lit de l'hote, **et rien de plus**. Aucune de ces
#: variables n'est a nous : elles sont posees par l'hote lui-meme.
#:
#: * ``WT_SESSION`` -- pose par Windows Terminal. **Fiable en presence, et
#:   HERITE par les sous-processus** : un `conhost` lance depuis un onglet
#:   Windows Terminal la verrait aussi, et serait alors classe a tort ;
#: * ``TERM_PROGRAM`` -- pose par le terminal de VS Code (``vscode``) et par
#:   quelques autres. Fiable ;
#: * ``TERM`` -- la convention POSIX. Presente sous Git Bash / MSYS.
VARIABLES_D_HOTE = ("WT_SESSION", "TERM_PROGRAM", "TERM", "ConEmuANSI",
                    "MSYSTEM")


def _legacy_windows() -> "bool | None":
    """Ce que ``rich`` sait de la console, ou `None` s'il ne peut pas le dire.

    **Evalue en PREMIER parmi les signaux**, et pour un motif de cout : `rich`
    est deja une dependance transitive de `textual`, deja maintenu, deja
    eprouve sur le parc Windows. Ecrire du `ctypes` a la main pour la meme
    question serait payer une seconde fois ce qui est deja installe.

    `True` designe la console **historique** de Windows (pas de sequences VT),
    qui est le cas le plus surement depourvu des glyphes. `False` ne prouve
    rien sur la police : une console moderne peut tres bien etre en Consolas,
    qui n'a pas U+23CE.

    Rend `None` plutot que de lever si `rich` manque -- le diagnostic doit
    repondre sur un environnement partiel, exactement comme pour `textual`.
    """
    try:
        from rich.console import Console
    except Exception:      # noqa: BLE001 -- rich absent ou casse
        return None
    try:
        return bool(Console().legacy_windows)
    except Exception:      # noqa: BLE001 -- pas de console attachee
        return None


def repli_ascii_conseille(environ=None, plateforme: str | None = None,
                          legacy: "bool | None" = None) -> tuple[bool, str]:
    """Faut-il replier en ASCII sans qu'on l'ait demande ? Rend `(oui, motif)`.

    **Ce que cette fonction PEUT garantir** : que l'hote a ete interroge, que
    la reponse est reproductible, et qu'elle est motivee -- le motif est
    imprime par le diagnostic, donc verifiable sur la machine de l'operateur.

    **Ce qu'elle ne peut PAS garantir, et il faut l'ecrire ici plutot que de le
    laisser croire.** Aucune API de Windows ne repond a « cette police
    contient-elle U+23CE ? ». On peut lire le NOM de la police de la console ;
    on ne peut lire ni sa couverture, ni le repli non documente que l'hote
    applique quand un glyphe manque (Windows Terminal en a un, `conhost` n'en a
    pas). **Toute detection est donc une heuristique conservatrice, jamais une
    preuve** -- et c'est pourquoi ``--utf8`` existe.

    Les signaux, par ordre d'amortissement :

    1. **hors Windows, on ne replie pas.** Le probleme est un probleme de
       police, il n'est en droit pas propre a Windows -- mais les deux plaintes
       de terrain viennent de la, et les polices de console usuelles de Linux
       et de macOS (DejaVu Sans Mono, SF Mono, Menlo) portent U+23CE. Replier
       ailleurs degraderait des millions de terminaux sains pour une hypothese
       que rien ne soutient ;
    2. **console historique** (`rich.legacy_windows`) -> repli. C'est le cas le
       plus sur ;
    3. **``WT_SESSION`` pose** -> pas de repli. Windows Terminal rend U+23CE, y
       compris par repli de police. Reserve deja dite : la variable est heritee,
       donc un `conhost` petit-fils d'un onglet WT passe a travers ;
    4. **``TERM_PROGRAM == "vscode"``** -> pas de repli. Le terminal de VS Code
       est un `xterm.js`, qui replie sur les polices du systeme ;
    5. **Windows sans aucun signal positif** -> repli. Il n'y a **aucun signal
       positif** de `conhost.exe` : on ne peut que l'obtenir par elimination,
       ce qui est la forme la moins robuste du lot. Le choix par defaut est
       donc le conservateur : un ecran en ASCII reste lisible, un ecran dont
       les glyphes tombent ne l'est pas.

    **``sys.stdout.encoding`` n'est PAS dans la liste, et c'est deliberate.**
    Depuis Python 3.6, quand la sortie est attachee a une console Windows,
    CPython ecrit en UTF-16 par ``WriteConsoleW`` et ``sys.stdout.encoding``
    rend ``utf-8`` **quelle que soit la page de code**. Il ne retombe sur
    ``cp1252`` que si la sortie est REDIRIGEE -- c'est-a-dire quand la TUI ne
    tourne pas. Il detecte la redirection, pas le probleme. Le diagnostic le
    rend quand meme, pour qu'on puisse le constater plutot que le croire.
    """
    environ = os.environ if environ is None else environ
    plateforme = sys.platform if plateforme is None else plateforme

    if not plateforme.startswith("win"):
        return False, f"hote non Windows ({plateforme}) -- glyphes conserves"
    if legacy is None:
        legacy = _legacy_windows()
    if legacy:
        return True, "console Windows historique (rich.legacy_windows)"
    if environ.get("WT_SESSION"):
        return False, "Windows Terminal (WT_SESSION) -- glyphes conserves"
    if environ.get("TERM_PROGRAM") == "vscode":
        return False, "terminal de VS Code (TERM_PROGRAM) -- glyphes conserves"
    return True, ("console Windows sans signal d'hote connu -- repli "
                  "conservateur, forcable par --utf8")


def echantillon_de_glyphes() -> str:
    """Les glyphes a risque, imprimes TELS QUELS, avec leur point de code.

    **C'est le seul livrable qui tranche.** Aucune detection ne sait ce qu'une
    police contient (voir :func:`repli_ascii_conseille`) ; un operateur qui
    regarde cette liste, lui, le sait en une seconde. Le repli ASCII est rendu
    en regard, pour qu'on voie ce que ``--ascii`` mettrait a la place.

    Les quatre dernieres entrees sont des **temoins CP437** : s'ils tombent
    aussi, le probleme n'est pas la couverture de la police mais l'encodage de
    la sortie, et ce sont deux reparations differentes.
    """
    from . import jetons

    lignes = ["glyphes=<caractere> <point de code> <repli --ascii> <role>"]
    for caractere, role in jetons.GLYPHES_A_RISQUE:
        try:
            nom = unicodedata.name(caractere)
        except ValueError:      # pragma: no cover -- tous nos points en ont un
            nom = "?"
        lignes.append(
            f"glyphe= {caractere}  U+{ord(caractere):04X}  "
            f"{jetons.replier_ascii(caractere)!r:<10} {role} [{nom}]")
    return "\n".join(lignes)


def diagnostic_de_la_console(environ=None) -> str:
    """Ce que la TUI voit de sa CONSOLE, ligne par ligne.

    Rubrique ajoutee le 2026-09-06 sur les deux plaintes de glyphes. Elle est
    **separee de** :func:`diagnostic` a dessein : ce dernier rend trois
    rubriques dont deux bancs lisent l'ordre exact (`test_modes.py` lit
    ``lignes[0]`` et ``lignes[-1]``), et glisser des lignes au milieu les
    ferait rougir pour une raison illisible. Les deux blocs sont imprimes a la
    suite par ``--diagnostic-chemin``.
    """
    environ = os.environ if environ is None else environ
    lignes = [f"sys.platform={sys.platform}"]
    for nom in VARIABLES_D_HOTE:
        lignes.append(f"{nom}={environ.get(nom, '')}")
    legacy = _legacy_windows()
    lignes.append("rich.legacy_windows="
                  + ("" if legacy is None else str(legacy)))
    # **Rendu, mais pas employe comme signal** : voir `repli_ascii_conseille`.
    # Le montrer permet de constater sa valeur plutot que de la croire.
    lignes.append(f"sys.stdout.encoding={getattr(sys.stdout, 'encoding', '')}"
                  " (n'est PAS un signal : voir repli_ascii_conseille)")
    lignes.append(f"sys.stdout.errors={getattr(sys.stdout, 'errors', '')}")
    lignes.append("console.page_de_code=" + _page_de_code())
    lignes.append("console.police=" + _police_de_la_console())
    repli, motif = repli_ascii_conseille(environ)
    lignes.append(f"repli_ascii_conseille={repli}")
    lignes.append(f"repli_ascii_motif={motif}")
    lignes.append(echantillon_de_glyphes())
    return "\n".join(lignes)


def _page_de_code() -> str:
    """La page de code de la console, ou une rubrique vide hors Windows.

    `GetConsoleOutputCP` n'existe que sur Windows ; ailleurs il n'y a pas de
    page de code du tout, et rendre une valeur inventee vaudrait moins que le
    silence.
    """
    try:
        import ctypes
        noyau = ctypes.windll.kernel32          # type: ignore[attr-defined]
        return f"{noyau.GetConsoleOutputCP()} (entree {noyau.GetConsoleCP()})"
    except Exception:      # noqa: BLE001 -- pas Windows, ou pas de console
        return ""


def _police_de_la_console() -> str:
    """Le nom de la police de la console, **quand `ctypes` le rend**.

    **Ce nom ne prouve rien.** Il dit ce que l'hote a charge, jamais ce que
    cette police COUVRE : Consolas est nomme de la meme facon qu'il porte ou ne
    porte pas U+23CE. Il est rendu parce qu'il est la seule piece objective
    qu'on puisse mettre en face de l'echantillon quand Egan le lira.
    """
    try:
        import ctypes
        from ctypes import wintypes

        class _Police(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.ULONG),
                        ("nFont", wintypes.DWORD),
                        ("dwFontSizeX", wintypes.SHORT),
                        ("dwFontSizeY", wintypes.SHORT),
                        ("FontFamily", wintypes.UINT),
                        ("FontWeight", wintypes.UINT),
                        ("FaceName", ctypes.c_wchar * 32)]

        noyau = ctypes.windll.kernel32          # type: ignore[attr-defined]
        sortie = noyau.GetStdHandle(-11)
        police = _Police()
        police.cbSize = ctypes.sizeof(_Police)
        if not noyau.GetCurrentConsoleFontEx(sortie, False,
                                             ctypes.byref(police)):
            return ""
        return f"{police.FaceName} {police.dwFontSizeY}px"
    except Exception:      # noqa: BLE001 -- pas Windows, API absente
        return ""


def diagnostic() -> str:
    """Rend ce que la TUI voit vraiment de son environnement, ligne par ligne.

    Les chemins d'import, et **le delai d'echappement**. Ce dernier n'est pas
    decoratif : `Echap` emet le meme octet que le prefixe de toute sequence
    d'echappement, et `ESCDELAY` est le temps que le parseur de `textual`
    attend avant de trancher. Il est donc a la fois la latence de `Echap` et
    la fenetre pendant laquelle une touche suivante lui est **collee**.

    Le rendre ici permet de le mesurer en EXECUTANT le lanceur plutot qu'en
    relisant son texte -- meme exigence que pour `PYTHONPATH` (AC 6.1) : un
    script qui contient la bonne ligne et un script dont le reglage atteint
    l'interpreteur ne sont pas la meme chose.
    """
    lignes = [f"PYTHONPATH={os.environ.get('PYTHONPATH', '')}"]
    lignes += [f"sys.path={chemin}" for chemin in sys.path]
    lignes.append("ESCDELAY=" + os.environ.get("ESCDELAY", ""))
    return "\n".join(lignes)


def mode_ascii(options, environ=None) -> tuple[bool, str]:
    """Le repli ASCII effectif, et **pourquoi**. Rend `(actif, motif)`.

    Les trois etats, dans cet ordre : ``--ascii`` force, ``--utf8`` refuse, et
    sinon l'hote decide. Une fonction plutot qu'une expression dans `main`
    parce que c'est la SEULE regle a trois branches du lanceur, et qu'elle doit
    se mesurer sans monter d'application.
    """
    if getattr(options, "ascii_seul", False):
        return True, "demande par --ascii"
    if getattr(options, "pas_d_ascii", False):
        return False, "refuse par --utf8"
    return repli_ascii_conseille(environ)


def main(argv: list[str] | None = None) -> int:
    options = analyser(argv)
    if options.diagnostic_chemin:
        print(diagnostic())
        print(diagnostic_de_la_console())
        return 0
    ascii_seul, _motif = mode_ascii(options)
    # Import tardif : `--diagnostic-chemin` doit repondre meme si `textual`
    # manque, sans quoi l'outil de diagnostic du chemin d'import serait la
    # premiere victime d'un chemin d'import casse.
    from .atelier_extraction_ecriture import construire_l_application

    construire_l_application(sans_couleur=options.sans_couleur,
                             ascii_seul=ascii_seul).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
