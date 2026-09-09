# -*- coding: utf-8 -*-
"""L'installateur d'une ligne pose des questions, et son dialogue se MESURE.

`scripts/install.sh` et `scripts/install.ps1` sont les deux seuls fichiers du
depot qu'un utilisateur execute AVANT d'avoir le depot. Ils n'ont pas de suite
de tests derriere eux au moment ou ils tournent : ce banc est le seul endroit
ou leur comportement est verifie.

## Le piege qui fonde ce fichier, et pourquoi il ne se voit pas

Sous `curl -fsSL ... | bash`, **stdin EST le script**. Un `read` nu n'attend
donc pas l'utilisateur : il consomme la LIGNE SUIVANTE DU SCRIPT. Ce n'est pas
un blocage -- un blocage serait visible -- c'est une corruption silencieuse.
Sonde de la story, script de cinq lignes canalise dans `bash` :

    AVANT le read
    APRES le read              <- la ligne "reponse lue = [...]" a DISPARU
    cette ligne est du SCRIPT, pas une reponse

Et `read < /dev/tty` sans terminal rend un code de sortie **0** que `set -e`
n'attrape pas. Le code de sortie ne repond donc jamais a la question « y a-t-il
quelqu'un ? ».

## Ce que ce banc a MESURE lui-meme, et qui a corrige la story

L'AC2 prescrivait `[ -r /dev/tty ]` comme test d'existence du terminal.
**C'est faux**, mesure le 2026-09-07 :

    sans terminal de controle (setsid) :  test -r /dev/tty  -> VRAI
                                          exec 3</dev/tty   -> faux
    dans un pseudo-terminal            :  test -r /dev/tty  -> VRAI
                                          exec 3</dev/tty   -> VRAI

`/dev/tty` est un noeud `crw-rw-rw-` toujours present et `test -r` n'interroge
que les droits (`access(2)`) : il rend VRAI meme quand l'ouverture est
impossible. Seule l'OUVERTURE distingue, et c'est ce que les scripts font.
`test_le_terminal_se_detecte_par_une_OUVERTURE` rejoue la mesure : si un jour
`test -r` devenait discriminant, le banc le dirait au lieu de le supposer.

## Le menu que ce banc mesure est celui du 2026-09-07, pas celui de la story

Egan a tranche sur la note de release : **six questions passent a quatre**.
Sont sorties du menu l'interface graphique (« plus tard »), l'apercu video en
fenetre (« inclus par defaut, retrait manuel » -- remplace par une DETECTION
d'affichage) et le choix de version (« c'est quoi la version d'essai ? »). Se
sont ajoutees la desinstallation complete -- paquets ET ligne de profil -- et
la relance qui devient une mise a jour.

**Puis quatre repassent a CINQ** : la story 8.8 (`EPIC8-ARB-19`, verbatim
d'Egan : « Essaye ... on verra bien si ca marche ») ajoute en quatrieme
position le raccourci hors terminal. Le cardinal se lit dans
`ORDRE_DES_QUESTIONS`, pas dans cette prose.

Les frontieres qui mesuraient les deux questions retirees n'ont pas ete
supprimees : elles ont ete REPRISES sur ce qui les remplace, c'est-a-dire la
detection d'affichage, mesuree dans ses deux sens.

## Pourquoi ce banc fabrique sa machine au lieu de lire la vraie

Trois des cinq questions dependent de l'etat du poste : ffmpeg present ou non,
une installation deja posee ou non, un affichage ou non. Un banc qui lirait la
machine reelle mesurerait le conteneur, changerait de verdict d'une machine a
l'autre, et rendrait vert sur celle qui n'a rien. Chaque parcours part donc
d'un PATH fabrique, avec un `pipx` factice dont la sortie est ecrite par le
banc. C'est la meme raison qui fait qu'on ne mesure pas une installation
reelle : elle modifierait la machine de qui joue la suite.

## Les mutations jouees, et leur verdict

Chaque frontiere de ce fichier a ete VUE ROUGIR, en cassant volontairement ce
qu'elle garde puis en restaurant depuis une copie prise avant. Verdicts du
2026-09-07 (le detail est dans le compte rendu de la story) :

**14 mutations jouees, 14 rouges, zero survivant.**

| mutation jouee sur les scripts | frontiere qui rougit |
|---|---|
| M1 -- `read -r saisie < /dev/tty` devient `read -r saisie` | `..._passe_par_dev_tty` |
| M2 -- la detection redevient `[ -r /dev/tty ]` | `..._par_une_OUVERTURE` |
| M3 -- `--include-apps` retire de la greffe pipx | `..._prend_le_defaut_et_le_DIT` |
| M4 -- `--force` retire de la greffe pipx | `..._prend_le_defaut_et_le_DIT` |
| M5 -- le repli sans terminal lit quand meme le clavier | `..._prend_le_defaut_et_le_DIT` |
| M6 -- une saisie non reconnue echoue au lieu de reposer la question | `..._REPOSE_la_question` |
| M7 -- l'option 1 greffe quand meme `mmu-cli` | `..._REPOSE_la_question` |
| M8 -- le cout annonce de `[gui]` passe de 265 a 500 Mo | `..._celui_qui_a_ete_MESURE` |
| M9 -- un `Read-Host` pose hors de la fonction gardee (ps1) | `..._hors_des_fonctions_gardees` |
| M10 -- la question ffmpeg se pose meme quand ffmpeg est la | `..._QUE_s_il_manque` |
| M11 -- la detection d'affichage rend toujours vrai | `..._prend_le_defaut_et_le_DIT` |
| M12 -- la roue avec fenetres est EMPILEE au lieu de remplacer | `..._REMPLACE_l_autre` |
| M13 -- la relance reinstalle au lieu de mettre a jour | `..._MET_A_JOUR_au_lieu_de...` |
| M14 -- `--desinstaller` ne touche plus au profil | `..._retire_AUSSI_la_ligne...` |

Les frontieres nommees sont celles qui rougissent EN PREMIER (`pytest -x`) ;
plusieurs mutations en font tomber d'autres derriere.

## Ce que ce banc NE mesure PAS, dit plutot que tu

* **il ne mesure presque aucune installation reelle.** Tout passe par
  `--dry-run`, a QUATRE exceptions pres depuis la story 8.8 : les frontieres du
  raccourci jouent une installation sans `--dry-run`, parce qu'un validateur ne
  peut rien dire d'un fichier qui n'existe pas. Elles restent inoffensives --
  `pipx` y est factice et le `HOME` est jetable (`_maison_neuve`). Pour tout le
  reste, le plan est verifie et pas son execution : installer reellement
  supposerait des distributions publiees (`mmu-cli` et `mmu-tui` rendent 404 sur
  PyPI au 2026-09-07) et modifierait la machine de qui joue la suite ;
* **il ne mesure pas Windows.** `install.ps1` est joue sous `pwsh` quand il est
  installe -- PowerShell 7 sur Linux --, jamais sous Windows PowerShell 5.1.
  Ce qui distingue les deux (le registre, winget, le PATH utilisateur) reste
  hors de portee, et c'est precisement la ou vit le retrait de PATH du
  desinstalleur PowerShell ;
* **l'analyse des fonctions PowerShell compte les accolades**, elle n'analyse
  pas la grammaire : une accolade dans une chaine de caracteres la mettrait en
  defaut. Il n'y en a aucune aujourd'hui dans la fonction concernee, et
  `test_les_deux_fonctions_gardees_existent` rougit si elle disparait.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import pty
import re
import select
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
INSTALL_SH = RACINE / "scripts" / "install.sh"
INSTALL_PS1 = RACINE / "scripts" / "install.ps1"

#: Delai au-dela duquel un dialogue est declare pendu. Genereux : le script
#: interroge `python3 --version` et `ffmpeg -version`, qui coutent quelques
#: dizaines de millisecondes chacun sur une machine chargee.
DELAI = 120.0

#: Les codes ANSI, retires avant toute comparaison de texte. Le script les pose
#: quand sa sortie est un terminal -- ce qui est le cas dans un pseudo-terminal.
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

#: Reponse "Entree seule" : une ligne vide vaut le defaut. Huit lignes couvrent
#: largement les cinq questions, meme quand la reprise s'ajoute.
ENTREE_SEULE = [""] * 8

#: Les binaires dont les scripts ont reellement besoin. Tout PATH fabrique par
#: ce banc ne contient QUE ceux-la, plus ce que le cas mesure ajoute.
OUTILS_DE_BASE = (
    "bash", "sh", "env", "uname", "id", "basename", "tr", "head", "cat",
    "sed", "grep", "sudo",
    # `mkdir` et `rm` : poses par la story 8.8, et il faut le dire parce que
    # leur absence ne se voit pas a la lecture. Ce ne sont PAS des builtins
    # bash (mesure : `type -t rm mkdir` -> `file file`), et sous
    # `set -euo pipefail` un `executer rm -f ...` introuvable rend 127 et TUE
    # le script -- les deux tests de desinstallation, qui jouent sans
    # `--dry-run`, mouraient alors avant leur `assert "Termine"`.
    "mkdir", "rm",
    # `sleep` : `lancer_avec_plafond` en fait un par seconde d'attente. Sans
    # lui sur le PATH fabrique, la boucle rend `sleep: command not found` a
    # chaque tour et le plafond cesse d'etre un plafond de TEMPS -- il devient
    # un compte de tours. Constate a l'ecriture de la story 8.14, sur la
    # premiere fonction qui appelle ce plafond en dehors du repli macOS.
    "sleep",
    # `date` : posee par la story 8.12, meme famille et meme motif. Le recu
    # horodate chaque objet pose ; sans `date` sur le PATH fabrique, le produit
    # se degrade proprement en `date-inconnue` -- ce qui est le bon
    # comportement, mais fait mesurer la degradation la ou l'AC2 demande de
    # mesurer la date. Constate a l'ecriture du banc, pas suppose.
    "date",
    # Les SEPT outils du repli precompile (story 8.11, AC11). Ils sont poses
    # AVANT le produit, et l'ordre compte : sans eux, un `command -v curl` qui
    # echoue dans la machine factice se lirait comme un defaut du produit alors
    # qu'il ne dirait que l'etat du banc. Aucun n'etait la avant le 2026-09-08.
    #
    # `xattr` n'y figure PAS, et ce n'est pas un oubli : il n'existe pas sous
    # Linux (`shutil.which` rend None), donc le lien serait silencieusement
    # saute. Il se depose explicitement, par `_deposer_outil`, dans les cas qui
    # le demandent -- ce qui le rend variable dans les deux sens (AC9).
    "curl", "unzip", "shasum", "sha256sum", "mktemp", "chmod", "mv",
    "python3", "python3.11", "python3.12", "python3.13",
    "apt-get", "dnf", "pacman", "zypper", "apk", "brew",
)

#: Les outils que le repli precompile appelle, nommes a part pour qu'un test
#: puisse en RETIRER un et mesurer le chemin d'echec correspondant (AC6/AC9).
OUTILS_DU_REPLI = ("curl", "unzip", "shasum", "sha256sum", "mktemp", "chmod", "mv")


#: LE DRAPEAU QUI REND UNE MACHINE FABRIQUEE HERMETIQUE (story 8.14).
#:
#: Depuis `EPIC11-ARB-279`, un `command -v` qui echoue fait consulter une liste
#: BORNEE d'emplacements usuels -- dont `/usr/local/bin`, qui est un chemin
#: ABSOLU du conteneur et qu'aucun `PATH` fabrique ne gouverne. Mesure dans ce
#: conteneur-ci : `/usr/local/bin/python3` existe, c'est un lien vers
#: `/usr/bin/python3.11`, et il tient le plancher. Une machine fabriquee
#: `avec_python=False` cesse donc d'etre une machine sans Python : le produit
#: en trouve un, et il a RAISON de le trouver -- c'est litteralement ce que la
#: story ferme.
#:
#: C'est la meme famille que `XDG_DATA_HOME` et `XDG_STATE_HOME`, retires par
#: `_fabriquer_machine` pour le meme motif : l'environnement d'un banc ne se
#: suppose pas. La difference est qu'aucune variable ne gouverne un chemin
#: absolu -- le seul levier est celui du PRODUIT, et il existe pour un besoin
#: reel (une installation reproductible qui n'emprunte rien a ce qui traine
#: dans `/usr/local/bin`).
#:
#: Il ne se pose QUE la ou le banc a besoin d'une machine sans Python. Les
#: parcours qui mesurent la recherche elle-meme ne le portent evidemment pas,
#: et le regime « trouve » se joue par `${HOME}/.local/bin`, que le banc
#: gouverne.
IGNORER_HORS_DU_PATH = "--ignorer-hors-du-path"

#: LES SEULES variables de l'environnement REEL qu'une machine fabriquee
#: herite. Tout le reste est ecarte -- voir `_fabriquer_machine`.
#:
#: Elles sont ici parce qu'elles ne changent RIEN a ce que le produit decide :
#: ni un chemin, ni une capacite, ni une destination. Une variable qui
#: gouvernerait une decision du script n'a rien a faire dans cette liste, et
#: c'est le critere -- pas « ca marchait avant ».
VARIABLES_HERITEES = frozenset({
    "TZ",                            # l'horodatage du recu
})

#: CE QUI SE POSE PLUTOT QUE DE S'HERITER, et la nuance a coute un rouge de CI
#: (2026-09-09). Une machine « entierement maitrisee » qui HERITE une variable
#: n'est maitrisee que sur les machines qui la portent : ce conteneur a `TERM`,
#: le runner GitHub ne l'a pas, et `test_l_issue_2_retire_pipx_PAR_SA_VOIE`
#: passait ici en echouant la-bas -- le dialogue de retrait ne rendait que
#: l'echo de la reponse.
#:
#: Une liste blanche repond a « quoi laisser passer ». Elle ne repond pas a
#: « et si ce n'est pas la ? ». Ces trois-la se POSENT, donc la machine est la
#: MEME partout -- ce qui est le seul sens defendable de « maitrisee ».
VARIABLES_POSEES = {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "TERM": "xterm-256color",
}


# ---------------------------------------------------------------- outillage

def sans_ansi(texte: str) -> str:
    """Retire les codes de mise en forme, qui ne sont pas du contenu."""
    return ANSI.sub("", texte)


def lignes_de_plan(sortie: str) -> list[str]:
    """Les commandes que `--dry-run` annonce, normalisees.

    C'est le PLAN au sens de l'AC8 : ce que le script ferait. On ne compare
    jamais un resume en prose -- un resume peut mentir sur ce qui suit, une
    ligne `[simulation]` est la commande elle-meme.
    """
    lignes = []
    for ligne in sans_ansi(sortie).splitlines():
        ligne = ligne.strip()
        if ligne.startswith("[simulation]"):
            lignes.append(" ".join(ligne[len("[simulation]"):].split()))
    return lignes


def plan_pipx(sortie: str) -> list[str]:
    """Le plan restreint aux appels a pipx.

    Le reste du plan (apt-get, winget) depend de ce qui manque sur la machine :
    le comparer melangerait le produit et l'environnement.
    """
    return [ligne for ligne in lignes_de_plan(sortie) if ligne.startswith("pipx ")]


def _lire_jusqu_a_la_fin(maitre: int, delai: float) -> str:
    """Vide le pseudo-terminal jusqu'a la mort du fils, ou jusqu'au delai.

    Le delai n'est pas une precaution de confort : c'est la frontiere qui
    distingue « le script a pris le defaut » de « le script attend une reponse
    que personne ne donnera ». Un blocage sec se voit ici, et nulle part
    ailleurs.
    """
    morceaux: list[bytes] = []
    limite = time.monotonic() + delai
    while True:
        reste = limite - time.monotonic()
        if reste <= 0:
            raise AssertionError(
                "le dialogue n'a pas rendu la main en %.0f s -- blocage sec.\n"
                "Sortie partielle :\n%s"
                % (delai, b"".join(morceaux).decode("utf-8", "replace"))
            )
        prets, _, _ = select.select([maitre], [], [], min(reste, 1.0))
        if not prets:
            continue
        try:
            bloc = os.read(maitre, 65536)
        except OSError:
            # EIO : le fils a ferme son cote du pseudo-terminal. C'est la fin
            # normale, pas une panne.
            break
        if not bloc:
            break
        morceaux.append(bloc)
    return b"".join(morceaux).decode("utf-8", "replace")


def jouer_le_dialogue(arguments, reponses, environnement, delai=DELAI, cwd=None):
    """Joue `install.sh` dans un VRAI pseudo-terminal et y tape les reponses.

    `pty.fork` -- et non `subprocess` avec un tube -- parce que le script ouvre
    `/dev/tty`, ce qui exige un terminal de CONTROLE, pas seulement un stdin
    branche quelque part. `pty.fork` fait le `setsid` et l'acquisition du
    terminal de controle en une fois ; un `openpty` + `start_new_session` ne
    donnerait qu'un stdin, et `/dev/tty` echouerait.

    Les reponses sont ecrites d'un bloc : la discipline de ligne du terminal
    les met en file, et chaque `read` en consomme une.

    **`cwd` est JETABLE, et il existe pour le meme motif que celui de
    `jouer_sans_terminal`** : le repertoire courant du banc est la RACINE DU
    DEPOT, et tout parcours qui mesure un chemin RELATIF y ecrirait. Le
    2026-09-08, la frontiere de l'atelier relatif (`C2-3`) l'a paye
    d'avance : sans la garde du produit, `curl -o` depose un `.pkg` de 46 Mo
    dans le repertoire courant, et la jambe Python de ce parcours ne peut se
    jouer QUE dans un pseudo-terminal -- son mot de passe se refuse par
    defaut en non-interactif. Le `chdir` est fait dans le FILS, avant
    l'`execve`, pour que le pere garde le sien.
    """
    fils, maitre = pty.fork()
    if fils == 0:  # pragma: no cover -- ce code vit dans le processus fils
        try:
            if cwd is not None:
                os.chdir(str(cwd))
            os.execve("/bin/bash", ["bash", str(INSTALL_SH), *arguments],
                      dict(environnement))
        except BaseException:
            os._exit(127)
    try:
        if reponses:
            os.write(maitre, ("\n".join(reponses) + "\n").encode())
        sortie = _lire_jusqu_a_la_fin(maitre, delai)
    finally:
        try:
            os.close(maitre)
        except OSError:
            pass
        try:
            rendu, _statut = os.waitpid(fils, os.WNOHANG)
            if rendu == 0:
                os.kill(fils, 9)
                os.waitpid(fils, 0)
        except (ChildProcessError, ProcessLookupError):
            pass
    return sortie


def jouer_sans_terminal(arguments, environnement, delai=DELAI, cwd=None):
    """Joue `install.sh` SANS terminal de controle : le regime CI, conteneur, nohup.

    `start_new_session=True` fait le `setsid` : le fils perd le terminal de
    controle, et `/dev/tty` devient inouvrable. C'est exactement le regime que
    l'AC2 decrit, et il est reproduit -- pas simule.

    `cwd` existe parce qu'un chemin RELATIF se resout contre le repertoire
    courant du PROCESSUS, et que celui du banc est la racine du depot. La
    campagne de mutation l'a mesure : le mutant « XDG relatif accepte » a fait
    ecrire un `donnees-relatives/applications/mmu-tui.desktop` **dans le
    depot**, ou un crochet de fin de tour l'a trouve en fichier non suivi. Un
    test qui mesure un chemin relatif se joue donc dans un repertoire jetable.
    """
    acheve = subprocess.run(
        ["/bin/bash", str(INSTALL_SH), *arguments],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=dict(environnement),
        cwd=str(cwd) if cwd is not None else None,
        timeout=delai,
    )
    return acheve.returncode, acheve.stdout.decode("utf-8", "replace")


# ------------------------------------------------------- machines fabriquees

#: Les gestionnaires de paquets systeme, retires ensemble ou pas du tout : une
#: machine qui en garderait un seul n'est pas une machine « sans gestionnaire ».
GESTIONNAIRES = ("apt-get", "dnf", "pacman", "zypper", "apk", "brew")

#: Les interpreteurs Python, meme discipline.
INTERPRETEURS = ("python3", "python3.11", "python3.12", "python3.13")


def _fabriquer_machine(dossier: Path, *, avec_ffmpeg: bool, liste_pipx: str,
                       avec_affichage: bool, avec_gestionnaire: bool = True,
                       avec_python: bool = True, avec_pipx: bool = True) -> dict:
    """Un PATH et un environnement entierement maitrises.

    Trois axes, tous les trois joues DANS LES DEUX SENS par le banc : ffmpeg
    present ou non, une installation deja posee ou non, un affichage ou non.
    Un `pipx` factice porte le troisieme -- il ne sait rien faire d'autre que
    repondre a `list --short`, et c'est tout ce dont la detection a besoin.
    """
    binaires = dossier / "bin"
    binaires.mkdir(exist_ok=True)
    ecartes: tuple = ()
    if not avec_gestionnaire:
        ecartes += GESTIONNAIRES
    if not avec_python:
        ecartes += INTERPRETEURS
    for nom in OUTILS_DE_BASE:
        if nom in ecartes:
            continue
        chemin = shutil.which(nom)
        if chemin and not (binaires / nom).exists():
            (binaires / nom).symlink_to(chemin)
    if avec_ffmpeg:
        for nom in ("ffmpeg", "ffprobe"):
            chemin = shutil.which(nom)
            assert chemin, "ce banc a besoin d'un vrai %s pour le cas « present »" % nom
            if not (binaires / nom).exists():
                (binaires / nom).symlink_to(chemin)

    inventaire = dossier / "liste_pipx.txt"
    inventaire.write_text(liste_pipx)
    if not avec_pipx:
        # Sans pipx, l'ETAPE pipx existe -- et c'est la seule facon de mesurer
        # son repli. Toutes les autres machines en portent un factice, si bien
        # que cette etape y est SAUTEE : une frontiere posee sur elle y serait
        # verte en ne voyant rien.
        # UN ENVIRONNEMENT MINIMAL ET EXPLICITE, pas l'environnement REEL
        # avec trois cles ecrasees (corrige le 2026-09-09, et c'est la cause
        # des 92 rouges de la premiere CI publique).
        #
        # `dict(os.environ)` faisait heriter la machine « entierement
        # maitrisee » de TOUT l'environnement de qui joue la suite. Sur un
        # runner GitHub, `PIPX_BIN_DIR=/opt/pipx_bin` passait donc au travers,
        # et `repertoire_binaire_de_pipx` le lit -- ce que la story 8.11 lui a
        # justement appris a faire.
        #
        # CONSEQUENCE MESUREE, et elle depasse de loin le banc : le repli
        # precompile posait son ffmpeg FACTICE dans le VRAI `/opt/pipx_bin` du
        # runner, qui est sur son `PATH`. Tout ce qui suivait sondait donc un
        # ffmpeg qui ne fait rien -- « Sortie ffprobe illisible », « Fichier
        # video introuvable », des fixtures vides. Quatre-vingt-trois tests de
        # bancs que cette branche n'a JAMAIS touches, verts la veille sur le
        # meme runner et le meme ffmpeg, rougissaient a cause de ce banc-ci.
        #
        # Le sens du correctif compte : on n'ecarte pas `PIPX_BIN_DIR` par une
        # liste noire -- il faudrait la tenir a jour a chaque variable que le
        # produit apprend a lire, et le silence serait le meme. On part d'un
        # environnement VIDE et on ajoute ce qu'on veut. Ce qui n'est pas
        # nomme ici n'atteint pas la machine.
        env = {cle: valeur for cle, valeur in os.environ.items()
               if cle in VARIABLES_HERITEES}
        env["PATH"] = str(binaires)
        env["HOME"] = str(dossier)
        env["SHELL"] = "/bin/bash"
        env.update(VARIABLES_POSEES)
        for parasite in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_DATA_HOME",
                         "XDG_STATE_HOME"):
            env.pop(parasite, None)
        if avec_affichage:
            env["DISPLAY"] = ":0"
        return env
    faux_pipx = binaires / "pipx"
    faux_pipx.write_text(
        "#!/bin/sh\n"
        "# pipx factice : il ne sait que dire ce qui est installe.\n"
        "if [ \"$1\" = \"list\" ] && [ \"$2\" = \"--short\" ]; then\n"
        "    cat '%s'\n"
        "fi\n"
        "exit 0\n" % inventaire
    )
    faux_pipx.chmod(0o755)

    # LE SECOND CHEMIN, et c'est CELUI-LA qui fuyait (2026-09-09). Le premier
    # a ete referme quelques minutes plus tot, et la machine heritait encore de
    # 138 cles reelles -- dont `PIPX_BIN_DIR`. Deux fabriques d'environnement
    # dans le meme module, une seule corrigee : le defaut que ce depot nomme
    # « un remede recopie a cinq endroits diverge », pour la deuxieme fois
    # dans la meme journee.
    #
    # Le `pop` explicite de `DISPLAY` ci-dessous en etait le symptome : on
    # ecartait UNE variable genante a la fois, a mesure qu'elle mordait. La
    # liste blanche renverse la charge -- ce qui n'est pas nomme n'entre pas.
    env = {cle: valeur for cle, valeur in os.environ.items()
           if cle in VARIABLES_HERITEES}
    env["PATH"] = str(binaires)
    env["HOME"] = str(dossier)
    env["SHELL"] = "/bin/bash"
    env.update(VARIABLES_POSEES)
    # `XDG_DATA_HOME` DOIT partir, et ce n'est pas une precaution de confort.
    # `install.sh` respecte XDG : tant que la variable traversait, le `HOME`
    # jetable de `_maison_neuve` ne gouvernait RIEN, et le banc ecrivait un
    # vrai `mmu-tui.desktop` dans le menu d'applications de qui joue la suite
    # -- en ECRASANT ce qui s'y trouvait, le desinstalleur `rm -f` visant
    # ensuite la meme cible. Les trois couches de la revue l'ont trouve
    # independamment (`C1-5`, `C2-4`, `C3-2`), et la couche 1 l'a mesure en
    # perdant son propre fichier temoin. Deux frontieres restaient vertes dans
    # ce regime EN NE VOYANT RIEN : elles assertaient l'absence d'un fichier a
    # un chemin ou le script n'ecrivait plus.
    env.pop("XDG_DATA_HOME", None)
    # `XDG_STATE_HOME` PART POUR EXACTEMENT LE MEME MOTIF, et il est pose ici
    # AVANT d'avoir mordu plutot qu'apres (story 8.12). Le recu de l'AC2 vit
    # sous `${XDG_STATE_HOME:-${HOME}/.local/state}` : tant que la variable
    # traverserait, le `HOME` jetable de `_maison_neuve` ne gouvernerait pas
    # le recu, et un banc qui asserte « le recu a ete retire » serait vert en
    # ne mesurant rien -- ou, pire, retirerait le repertoire d'etat de qui joue
    # la suite. C'est litteralement le defaut `C1-5`/`C2-4`/`C3-2` de la revue
    # 8.8, transpose d'une variable XDG a l'autre.
    #
    # Le conteneur de cette session n'en porte AUCUNE : la garde ne se mesure
    # donc pas ici par son absence, elle se pose parce que l'environnement
    # d'un banc ne se suppose pas.
    env.pop("XDG_STATE_HOME", None)
    if avec_affichage:
        env["DISPLAY"] = ":0"
    return env


@pytest.fixture(scope="module")
def machine_vierge(tmp_path_factory):
    """Rien d'installe, ffmpeg present, aucun affichage. Le cas nominal."""
    return _fabriquer_machine(tmp_path_factory.mktemp("vierge"),
                              avec_ffmpeg=True, liste_pipx="", avec_affichage=False)


@pytest.fixture(scope="module")
def machine_sans_ffmpeg(tmp_path_factory):
    """Le seul cas ou la question ffmpeg a le droit d'exister."""
    return _fabriquer_machine(tmp_path_factory.mktemp("sans_ffmpeg"),
                              avec_ffmpeg=False, liste_pipx="", avec_affichage=False)


@pytest.fixture(scope="module")
def machine_sans_gestionnaire(tmp_path_factory):
    """Un Mac sans Homebrew, ou un Linux verrouille : rien pour poser un paquet.

    Python est LA, ffmpeg non. C'est la combinaison exacte du parcours reel du
    2026-09-08 -- la seule dependance manquante est facultative.
    """
    return _fabriquer_machine(tmp_path_factory.mktemp("sans_gestionnaire"),
                              avec_ffmpeg=False, liste_pipx="",
                              avec_affichage=False, avec_gestionnaire=False,
                              avec_pipx=False)


@pytest.fixture(scope="module")
def machine_sans_gestionnaire_ni_python(tmp_path_factory):
    """La meme, privee de Python : la dependance qui n'est PAS facultative."""
    return _fabriquer_machine(tmp_path_factory.mktemp("sans_gest_ni_python"),
                              avec_ffmpeg=False, liste_pipx="",
                              avec_affichage=False, avec_gestionnaire=False,
                              avec_python=False)


@pytest.fixture(scope="module")
def machine_avec_affichage(tmp_path_factory):
    """L'autre sens du drapeau d'affichage : un poste de bureau."""
    return _fabriquer_machine(tmp_path_factory.mktemp("avec_affichage"),
                              avec_ffmpeg=True, liste_pipx="", avec_affichage=True)


@pytest.fixture(scope="module")
def machine_affichage_sans_ffmpeg(tmp_path_factory):
    """Les DEUX questions conditionnelles a la fois : ffmpeg et le raccourci.

    Sans elle, l'ordre des cinq questions ne serait jamais mesure : la seule
    machine sans ffmpeg n'a pas d'affichage, donc la question du raccourci ne
    s'y pose pas, et un test de l'ordre resterait vert EN NE VOYANT RIEN.
    """
    return _fabriquer_machine(tmp_path_factory.mktemp("affichage_sans_ffmpeg"),
                              avec_ffmpeg=False, liste_pipx="", avec_affichage=True)


@pytest.fixture(scope="module")
def machine_deja_installee(tmp_path_factory):
    """Une relance : `mmu-tui 0.1.0` est deja pose."""
    return _fabriquer_machine(tmp_path_factory.mktemp("deja_installee"),
                              avec_ffmpeg=True, liste_pipx="mmu-tui 0.1.0\n",
                              avec_affichage=False)


@pytest.fixture(scope="module")
def machine_cli_deja_installee(tmp_path_factory):
    """La MEME relance, mais sur l'autre distribution.

    Deux fabriques distinguables plutot qu'une : un `head -n1` qui rendrait
    toujours la premiere entree, ou une derivation des composants qui
    repondrait toujours « la TUI », ne se demasque pas autrement.
    """
    return _fabriquer_machine(tmp_path_factory.mktemp("cli_deja_installee"),
                              avec_ffmpeg=True, liste_pipx="mmu-cli 0.1.0\n",
                              avec_affichage=False)


#: Le plan par defaut, sur une machine vierge sans affichage. Il sert de
#: reference a plusieurs bancs : l'ecrire une fois evite qu'ils divergent.
PLAN_PAR_DEFAUT = [
    "pipx install --force mmu-tui",
    "pipx inject --include-apps --force mmu-tui mmu-cli",
    "pipx ensurepath",
]


# ================================================================== AC1 + AC2
#  Les frontieres NEGATIVES : celles qui attrapent une REINTRODUCTION.
#  Aucun test positif ne verrait revenir un `read` nu -- le script marcherait
#  parfaitement pour qui l'execute depuis un fichier local, et se corromprait
#  silencieusement pour qui le colle depuis la documentation.
# ============================================================================

#: Un appel au `read` du shell, en position de commande. On ne cherche pas le
#: mot n'importe ou : `# une lecture` ou `spread` ne sont pas des appels.
APPEL_A_READ = re.compile(
    r"(?:^|[;&|(]|\bif\s+!?\s*|\bwhile\s+|\buntil\s+|\bthen\s+|\bdo\s+|\belse\s+)"
    r"\s*read\b(?P<reste>[^\n]*)"
)

#: Le bloc de commentaire de PowerShell, `<# ... #>`. Il porte tout l'entete
#: mesure de `install.ps1` -- donc cinq occurrences de `Read-Host` et le nom du
#: discriminant. Le laisser passer rendrait la frontiere negative FAUSSEMENT
#: verte (elle compterait des citations) et la frontiere positive faussement
#: verte aussi (elle trouverait le discriminant dans sa propre explication).
BLOC_DE_COMMENTAIRE_PS = re.compile(r"<#.*?#>", re.S)


def _lignes_de_code(texte: str) -> str:
    """Le texte sans ses lignes de commentaire pur.

    Necessaire parce que l'entete du script CITE `read` en toutes lettres pour
    expliquer le piege : un grep sur le fichier entier rougirait sur sa propre
    explication. Meme precaution que `test_politique_lfs.py`.
    """
    return "\n".join(
        ligne for ligne in texte.splitlines() if not ligne.lstrip().startswith("#")
    )


#: `inject` en tant que MOT. Sans la borne de mot, `--include-injected` -- le
#: drapeau de la mise a jour -- serait pris pour une greffe, et la frontiere
#: rougirait sur du code juste. Constate sur ce banc meme, le 2026-09-07.
APPEL_A_INJECT = re.compile(r"\binject\b")


def appels_a_inject(code: str) -> list[str]:
    """Les lignes qui greffent un paquet dans un venv pipx.

    Les continuations de ligne du shell (`\\` en fin de ligne) sont recollees
    d'abord : la greffe de bash tient sur deux lignes, et une lecture ligne a
    ligne verrait ses drapeaux d'un cote et ses paquets de l'autre.
    """
    recolle = re.sub(r"\\\s*\n\s*", " ", code)
    return [ligne.strip() for ligne in recolle.splitlines()
            if APPEL_A_INJECT.search(ligne)]


def code_du_script(script: Path) -> str:
    """Le code executable d'un script, ses commentaires retires.

    Un `.ps1` a DEUX formes de commentaire ; n'en retirer qu'une laisse passer
    l'entete entier, qui est justement l'endroit ou les pieges sont cites.
    """
    texte = script.read_text()
    if script.suffix == ".ps1":
        texte = BLOC_DE_COMMENTAIRE_PS.sub("", texte)
    return _lignes_de_code(texte)


def test_toute_lecture_clavier_passe_par_dev_tty():
    """AC1 -- frontiere NEGATIVE : un `read` nu ne peut pas revenir en silence."""
    code = code_du_script(INSTALL_SH)
    appels = list(APPEL_A_READ.finditer(code))
    assert appels, (
        "aucun appel a `read` trouve dans install.sh : soit le dialogue a "
        "disparu, soit l'expression qui les reconnait ne reconnait plus rien."
    )
    nus = [m.group(0).strip() for m in appels if "/dev/tty" not in m.group("reste")]
    assert nus == [], (
        "un `read` sans `< /dev/tty` est revenu dans install.sh. Sous "
        "`curl | bash`, stdin EST le script : ce read mangera la ligne "
        "suivante du script au lieu d'attendre l'utilisateur, sans une seule "
        "trace. Lignes fautives : %r" % (nus,)
    )


def test_le_nombre_de_points_de_lecture_reste_petit_et_connu():
    """AC1 -- un seul point de lecture, et un seul.

    Une seconde lecture apparue sans que personne ne la remarque est exactement
    la facon dont la garde precedente finit par etre contournee : elle serait
    juste, jusqu'au jour ou elle ne le serait plus.
    """
    code = code_du_script(INSTALL_SH)
    assert len(list(APPEL_A_READ.finditer(code))) == 1, (
        "install.sh doit avoir exactement un point de lecture clavier, dans "
        "`demander`. Le choix de version ayant quitte le menu le 2026-09-07, "
        "il n'y a plus de saisie libre."
    )


def test_le_terminal_se_detecte_par_une_OUVERTURE():
    """AC2 -- le discriminant de l'AC2 est mesure, pas recopie.

    L'AC2 prescrit `[ -r /dev/tty ]`. La mesure ci-dessous dit que ce test rend
    VRAI meme sans terminal de controle : il ne discrimine rien. Ce banc rejoue
    la mesure au lieu de la citer -- si un jour elle s'inversait, il le dirait.
    """
    sonde = (
        'if [ -r /dev/tty ]; then echo "R=VRAI"; else echo "R=faux"; fi\n'
        'if { exec 3</dev/tty; } 2>/dev/null; then echo "O=VRAI"; exec 3<&-; '
        'else echo "O=faux"; fi\n'
    )
    acheve = subprocess.run(
        ["bash", "-c", sonde],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        start_new_session=True, timeout=30,
    )
    mesure = acheve.stdout.decode()
    assert "O=faux" in mesure, (
        "sans terminal de controle, l'OUVERTURE de /dev/tty doit echouer -- si "
        "elle reussit ici, ce banc ne mesure pas le regime qu'il croit."
    )
    assert "R=VRAI" in mesure, (
        "mesure inattendue : `test -r /dev/tty` a rendu faux sans terminal de "
        "controle. Si cela devient vrai partout, l'AC2 avait raison et le "
        "commentaire d'install.sh doit etre corrige."
    )

    code = code_du_script(INSTALL_SH)
    assert "exec 9</dev/tty" in code, "install.sh doit OUVRIR /dev/tty pour le detecter."
    assert "-r /dev/tty" not in code, (
        "install.sh utilise `[ -r /dev/tty ]`, qui rend VRAI sans terminal de "
        "controle (mesure ci-dessus) : chaque question bloquerait en CI."
    )


def test_sans_terminal_l_installateur_prend_le_defaut_et_le_DIT(machine_vierge):
    """AC2 -- jamais un blocage sec : le defaut est pris ET annonce."""
    code, sortie = jouer_sans_terminal(["--dry-run"], machine_vierge)
    assert code == 0, "sans terminal, l'installateur doit rendre 0 :\n%s" % sortie
    assert "pas de terminal : je prends 2)" in sortie, (
        "la question 1 doit annoncer le defaut qu'elle prend :\n%s" % sortie
    )
    assert sortie.count("pas de terminal : je prends") >= 3, (
        "chaque question posee doit annoncer son repli, pas seulement la "
        "premiere :\n%s" % sortie
    )
    assert plan_pipx(sortie) == PLAN_PAR_DEFAUT, sortie


def test_le_mode_non_interactif_annonce_une_AUTRE_raison(machine_vierge):
    """AC2 + AC6 -- le drapeau et l'absence de terminal sont deux motifs distincts.

    C'est la regle « une garde fait varier son drapeau » : le repli est le meme,
    mais l'utilisateur doit savoir POURQUOI on ne lui a rien demande. Un
    conteneur qui dit « mode non interactif » alors que personne ne l'a demande
    est un diagnostic faux.
    """
    sortie = sans_ansi(jouer_le_dialogue(["--dry-run", "--non-interactif"], [], machine_vierge))
    assert "mode non interactif : je prends" in sortie, sortie
    assert "pas de terminal" not in sortie, (
        "dans un vrai terminal, le motif du silence est le drapeau, pas "
        "l'absence de terminal :\n%s" % sortie
    )


# ====================================================================== AC3
#  Une touche, jamais une syntaxe.
# ==========================================================================

def test_entree_seule_prend_le_defaut(machine_vierge):
    """AC3 -- valider par Entree, sans rien taper, donne le plan par defaut."""
    sortie = jouer_le_dialogue(["--dry-run"], ENTREE_SEULE, machine_vierge)
    assert plan_pipx(sortie) == PLAN_PAR_DEFAUT, sans_ansi(sortie)


def test_une_saisie_non_reconnue_REPOSE_la_question(machine_vierge):
    """AC3 -- une reponse absurde ne fait pas echouer l'installation.

    Deux saisies fautives de natures differentes : du texte (`oui`), et un
    chiffre HORS BORNE (`9`). La seconde est celle qu'un `case` trop laxiste
    laisserait passer -- elle est un chiffre, apres tout.
    """
    sortie = sans_ansi(jouer_le_dialogue(
        ["--dry-run"], ["oui", "9", "1"] + ENTREE_SEULE, machine_vierge))
    assert sortie.count("Je n'ai pas compris") == 2, sortie
    assert 'Je n\'ai pas compris "oui"' in sortie, sortie
    assert 'Je n\'ai pas compris "9"' in sortie, sortie
    # ... et la question a bien ete REPOSEE, puisque le "1" qui suit est pris.
    assert plan_pipx(sortie) == ["pipx install --force mmu-cli", "pipx ensurepath"], sortie


def test_le_defaut_est_montre_entre_crochets(machine_vierge):
    """AC3 -- le defaut se lit, il ne se devine pas."""
    sortie = sans_ansi(jouer_le_dialogue(["--dry-run"], ENTREE_SEULE, machine_vierge))
    assert "[defaut]" in sortie, sortie
    assert "Ton choix [2] puis Entree" in sortie, (
        "la question 1 a pour defaut l'option 2 :\n%s" % sortie
    )


# ====================================================================== AC4
#  Les CINQ questions (arbitrages d'Egan du 2026-09-07, `EPIC8-ARB-19` pour la
#  cinquieme), leur ordre, et ce qu'elles annoncent.
# ==========================================================================

#: L'ordre impose. On ne cherche pas l'intitule complet -- il peut etre
#: reformule -- mais son sujet, dans l'ordre.
ORDRE_DES_QUESTIONS = (
    "Que veux-tu installer ?",
    "ffmpeg est absent",
    "Ajouter les commandes au PATH ?",
    "Ajouter un raccourci",
    "Verifier l'installation a la fin ?",
)

#: Ce que le menu ne doit PLUS proposer. Frontiere NEGATIVE : une question
#: retiree qui reviendrait par une reconciliation malheureuse ne se verrait pas
#: autrement -- le plan resterait juste, et le menu aurait grossi.
QUESTIONS_RETIREES = (
    "Apercu video en fenetre ?",
    "Quelle version ?",
    "l'interface graphique",
)


def test_les_cinq_questions_sont_posees_DANS_L_ORDRE(machine_affichage_sans_ffmpeg):
    """AC4 de la 8.6, AC1 de la 8.8 -- ce qu'on veut d'abord, ce qui coute apres.

    La machine porte les DEUX conditions a la fois : pas de ffmpeg (question 2)
    et un affichage (question 4). Jouee sur `machine_sans_ffmpeg`, qui n'a pas
    d'affichage, cette frontiere ne verrait jamais la quatrieme question et
    serait verte pour la pire des raisons.
    """
    sortie = sans_ansi(jouer_le_dialogue(
        ["--dry-run"], ENTREE_SEULE, machine_affichage_sans_ffmpeg))
    positions = []
    for question in ORDRE_DES_QUESTIONS:
        indice = sortie.find(question)
        assert indice != -1, "question absente : %r\n%s" % (question, sortie)
        positions.append(indice)
    assert positions == sorted(positions), (
        "les cinq questions ne sont pas dans l'ordre impose : %r\n%s"
        % (positions, sortie)
    )


def test_le_menu_ne_propose_PLUS_ce_qui_en_a_ete_retire(machine_sans_ffmpeg):
    """AC4 -- frontiere NEGATIVE sur les trois questions sorties du menu.

    Egan, 2026-09-07 : « Interface graphique : plus tard », « Inclus par defaut.
    Retrait manuel », « C'est quoi la version d'essai ? ». Les trois capacites
    restent accessibles par drapeau ; c'est le MENU qui ne les propose plus.
    """
    sortie = sans_ansi(jouer_le_dialogue(["--dry-run"], ENTREE_SEULE, machine_sans_ffmpeg))
    menu = "\n".join(l for l in sortie.splitlines() if re.match(r"\s+\d\) ", l))
    for retiree in QUESTIONS_RETIREES:
        assert retiree not in sortie or retiree not in menu, (
            "%r est revenu dans le menu :\n%s" % (retiree, sortie)
        )
    # Le premier menu a exactement DEUX options depuis le 2026-09-07.
    assert "3) " not in menu, (
        "le menu des composants a retrouve une troisieme option :\n%s" % menu
    )


def test_la_question_ffmpeg_ne_se_pose_QUE_s_il_manque(machine_sans_ffmpeg, machine_vierge):
    """AC4 -- le drapeau varie dans les DEUX sens.

    Cette question demande le mot de passe administrateur. La poser quand la
    reponse ne peut rien changer est une friction gratuite -- et un banc qui ne
    jouerait qu'un cote de la condition ne verrait jamais l'autre.
    """
    absent = sans_ansi(jouer_le_dialogue(["--dry-run"], ENTREE_SEULE, machine_sans_ffmpeg))
    assert "ffmpeg est absent" in absent, absent

    present = sans_ansi(jouer_le_dialogue(["--dry-run"], ENTREE_SEULE, machine_vierge))
    assert "ffmpeg est absent" not in present, (
        "ffmpeg est present : la question ne doit pas etre posee.\n%s" % present
    )
    assert "ffmpeg .......... deja present" in present, present


def test_ffmpeg_refuse_ne_bloque_pas_et_dit_quoi_installer(machine_sans_ffmpeg):
    """AC4 -- « je m'en occupe moi-meme » sort de l'etape, pas de l'installation.

    Interrompre ici priverait l'utilisateur de ce qu'il est venu chercher, alors
    que ffmpeg s'ajoute apres coup sans rien refaire. Ce qu'on lui doit, c'est
    la commande exacte -- pas un renvoi a la documentation.
    """
    sortie = sans_ansi(jouer_le_dialogue(
        ["--dry-run", "--sans-ffmpeg"], ENTREE_SEULE, machine_sans_ffmpeg))
    assert "ffmpeg .......... laisse a ta charge" in sortie, sortie
    assert "ffprobe" in sortie, (
        "il faut dire qu'il faut ffmpeg ET ffprobe : les paquets minimalistes "
        "n'ont que le premier.\n%s" % sortie
    )
    assert plan_pipx(sortie), (
        "refuser ffmpeg ne doit pas annuler l'installation des paquets :\n%s" % sortie
    )


def test_la_question_du_PATH_nomme_le_fichier_ET_les_commandes(machine_vierge):
    """AC4 -- Egan : « il faut annoncer que ce sont potentiellement DEUX commandes ».

    Les deux cas sont joues, parce que le nombre de commandes depend du choix
    precedent : demander la permission d'exposer « les commandes » sans dire
    lesquelles, c'est demander une signature en bas d'une page blanche.
    """
    deux = sans_ansi(jouer_le_dialogue(["--dry-run"], ["2"] + ENTREE_SEULE, machine_vierge))
    assert "Ajouter les commandes au PATH ? (mmu et mmu-tui ;" in deux, deux
    assert ".bashrc" in deux, "le fichier touche doit etre nomme :\n%s" % deux

    une = sans_ansi(jouer_le_dialogue(["--dry-run"], ["1"] + ENTREE_SEULE, machine_vierge))
    assert "Ajouter les commandes au PATH ? (mmu ;" in une, une


def test_la_question_de_VERIFICATION_dit_ce_qu_elle_verifiera(machine_vierge):
    """AC4 -- Egan : « Faisable ca ? ». Oui, et on dit quoi.

    Les deux cas de nouveau : la TUI n'est verifiee que si elle est installee.
    Un libelle fixe promettrait une verification qui n'aura pas lieu.
    """
    deux = sans_ansi(jouer_le_dialogue(["--dry-run"], ["2"] + ENTREE_SEULE, machine_vierge))
    assert "mmu --version, mmu-tui sur le PATH, puis ffmpeg -version" in deux, deux

    une = sans_ansi(jouer_le_dialogue(["--dry-run"], ["1"] + ENTREE_SEULE, machine_vierge))
    assert "mmu --version, puis ffmpeg -version" in une, une
    assert "mmu-tui sur le PATH" not in une, (
        "la TUI n'est pas installee : ne pas promettre de la verifier.\n%s" % une
    )


#: Le cout de l'extra `[gui]`, EN MEGAOCTETS SUR LE DISQUE, et le seul chiffre
#: que ce depot ait le droit d'annoncer pour lui.
#:
#: Mesure du 2026-09-07, `venv` neuf, Linux x86_64, `du -sm` avant/apres sur les
#: paquets CONSTRUITS : `mmu-cli` pese 305 Mo, `mmu-cli[gui]` en pese 576 --
#: soit **271 Mo** de plus, annonces 270. C'est la mesure du DELTA D'ENVIRONNEMENT,
#: c'est-a-dire ce que l'utilisateur paie reellement en posant le drapeau ; elle
#: englobe les transitives de PySide6, la ou une mesure des deux seules roues
#: (`PySide6-Essentials` + `shiboken6` = 264 Mo) en rend moins.
COUT_MESURE_DE_L_EXTRA_GUI = 270

#: Les cinq fichiers qui annoncent ce cout a un humain. Les trois pages
#: d'installation le portent dans leur tableau de poids, les deux installateurs
#: dans l'aide de leur drapeau.
ANNONCEURS_DU_COUT_GUI = (
    "scripts/install.sh",
    "scripts/install.ps1",
    "docs/installation/linux.md",
    "docs/installation/macos.md",
    "docs/installation/windows.md",
)

#: Un cout ANNONCE se reconnait a sa marque de delta -- `~270 Mo`, `+270 Mo` --
#: et jamais a un nombre nu : `**576 Mo**` dans le meme tableau est un TOTAL,
#: pas un surcout, et le confondre ferait rougir la frontiere sur du juste.
_MOTIF_DE_DELTA = re.compile(r"[~+]\s*(\d+)\s*Mo")


def _couts_gui_annonces() -> dict[str, list[tuple[int, int]]]:
    """`{fichier: [(ligne, megaoctets), ...]}` pour chaque surcout `[gui]` ecrit.

    Ne retient que les lignes qui NOMMENT l'extra graphique : le meme tableau
    porte la ligne `mmu-tui` et son `+28 Mo`, qui est un autre cout et doit le
    rester.
    """
    releves: dict[str, list[tuple[int, int]]] = {}
    for relatif in ANNONCEURS_DU_COUT_GUI:
        chemin = RACINE / relatif
        trouves: list[tuple[int, int]] = []
        for numero, ligne in enumerate(
                chemin.read_text(encoding="utf-8").splitlines(), 1):
            if "gui" not in ligne.lower():
                continue
            for marque in _MOTIF_DE_DELTA.finditer(ligne):
                trouves.append((numero, int(marque.group(1))))
        releves[relatif] = trouves
    return releves


def test_le_cout_annonce_de_l_extra_graphique_est_celui_qui_a_ete_MESURE():
    """AC4 -- « annoncer son cout mesure, et non un ordre de grandeur invente ».

    **Volet A : aucun chiffre annonce ne s'ecarte de la mesure.** Une fourchette
    (« ~265 a 270 Mo ») EST l'ordre de grandeur que l'AC interdit, et un second
    chiffre mesure sur une autre base en est un aussi des lors qu'il cohabite
    avec le premier : le lecteur n'a aucun moyen de savoir lequel le concerne.

    Le defaut que ce volet ferme a ete PAYE, et par cette branche. La fusion de
    `dev/main` du 2026-09-07 a reconcilie deux redactions -- `~265 Mo` d'un cote,
    `~270 Mo` de l'autre -- en ecrivant leur FOURCHETTE dans `install.ps1`, et
    l'ancienne redaction de ce banc, qui ne cherchait que le litteral
    « 265 Mo », a rougi sans dire pourquoi. Elle mesurait un mot, pas un
    chiffre, et sur un seul des cinq fichiers qui l'annoncent.
    """
    ecarts = [
        f"{fichier}:{ligne} annonce {valeur} Mo"
        for fichier, releve in _couts_gui_annonces().items()
        for ligne, valeur in releve
        if valeur != COUT_MESURE_DE_L_EXTRA_GUI
    ]
    assert not ecarts, (
        "le cout de l'extra [gui] est mesure a %d Mo : tout autre chiffre "
        "annonce est un ordre de grandeur (AC4).\n  %s"
        % (COUT_MESURE_DE_L_EXTRA_GUI, "\n  ".join(ecarts))
    )


def test_les_CINQ_annonceurs_du_cout_gui_le_portent_VRAIMENT():
    """Volet symetrique -- sans lui, le volet A serait vert sur le silence.

    Il l'a d'ailleurs ete : `install.ps1`, avec sa fourchette « ~265 a 270 Mo »,
    ne rendait AUCUN delta au motif ci-dessus -- « 265 a » n'est pas suivi de
    « Mo », et « 270 Mo » n'y porte pas de marque de delta. Un banc qui ne
    mesurerait que l'ecart aurait donc declare conforme le fichier
    precisement fautif.
    """
    muets = [fichier for fichier, releve in _couts_gui_annonces().items()
             if not releve]
    assert not muets, (
        "ces fichiers doivent annoncer le surcout de l'extra [gui] et ne "
        "l'annoncent plus (redaction changee, ou marque de delta perdue) :\n  "
        + "\n  ".join(muets)
    )


# ==================================================== la detection d'affichage
#  Ce qui REMPLACE la question retiree. Deux sens, jamais un seul.
# ==========================================================================

def test_sans_affichage_la_roue_SANS_fenetres_est_conservee(machine_vierge):
    """La roue avec fenetres exige douze bibliotheques absentes d'un serveur nu.

    `EPIC11-ARB-253` a mesure ce que coute l'erreur : `import cv2` echoue AVANT
    la premiere ligne du produit. « Inclus par defaut » ne peut donc pas vouloir
    dire « toujours », et c'est pour ca que la question est devenue une
    detection plutot qu'un choix impose.
    """
    sortie = sans_ansi(jouer_le_dialogue(["--dry-run"], ENTREE_SEULE, machine_vierge))
    assert "aucun affichage detecte" in sortie, sortie
    plan = " ".join(plan_pipx(sortie))
    assert "opencv-python" not in plan, (
        "sans affichage, aucune roue OpenCV ne doit etre remplacee :\n%s" % sortie
    )


def test_avec_affichage_la_roue_AVEC_fenetres_REMPLACE_l_autre(machine_avec_affichage):
    """Et l'autre sens du meme drapeau -- avec le geste propre, pas l'empilement.

    Les deux roues livrent le meme module `cv2` et ne se declarent pas en
    conflit : pip les installerait toutes les deux sans un mot, et le prochain
    `--upgrade` de l'une ecraserait les fichiers de l'autre. Le retrait doit
    donc PRECEDER l'ajout.
    """
    sortie = sans_ansi(jouer_le_dialogue(["--dry-run"], ENTREE_SEULE, machine_avec_affichage))
    assert "un affichage est detecte" in sortie, sortie
    plan = plan_pipx(sortie)
    assert "pipx runpip mmu-tui uninstall -y opencv-python-headless" in plan, sortie
    assert "pipx inject --force mmu-tui opencv-python" in plan, sortie
    assert plan.index("pipx runpip mmu-tui uninstall -y opencv-python-headless") < \
           plan.index("pipx inject --force mmu-tui opencv-python"), (
        "le retrait doit PRECEDER l'ajout, sinon les deux roues coexistent :\n%s" % sortie
    )
    assert "pipx inject --force mmu-tui opencv-python-headless" in sortie, (
        "le retrait manuel doit etre documente dans la sortie :\n%s" % sortie
    )


def test_la_detection_d_affichage_lit_les_DEUX_variables():
    """Wayland n'a pas de `DISPLAY`, et un poste Wayland pur n'en pose aucun.

    Ne lire que `DISPLAY` classerait tout poste Wayland recent en « serveur nu »
    et le priverait de l'apercu video -- silencieusement, puisque le repli
    fonctionne.
    """
    code = code_du_script(INSTALL_SH)
    assert "WAYLAND_DISPLAY" in code, code[:200]
    assert "WAYLAND_DISPLAY" in code_du_script(INSTALL_PS1)


# ====================================================================== AC5
#  Le piege pipx : `mmu` n'arrive pas sur le PATH tout seul.
# ==========================================================================

def test_la_greffe_de_la_cli_porte_include_apps_ET_force(machine_vierge):
    """AC5 -- les deux drapeaux, chacun pour un motif different.

    `pipx install mmu-tui` installe bien `mmu-cli` dans le venv, mais pipx
    n'expose QUE les scripts du paquet principal : `mmu` n'arrive pas sur le
    PATH. `--include-apps` est ce qui l'enregistre ; `--force` est ce qui
    empeche pipx de repondre « already seems to be installed » et de ne rien
    faire. Retirer l'un OU l'autre rend la commande introuvable apres une
    installation reussie -- et rien ne le signale.
    """
    for arguments in (["--dry-run", "--tui"], ["--dry-run", "--gui"]):
        sortie = jouer_le_dialogue(arguments, ENTREE_SEULE, machine_vierge)
        greffes = [l for l in plan_pipx(sortie)
                   if l.startswith("pipx inject") and "mmu-cli" in l]
        assert len(greffes) == 1, "%r\n%s" % (arguments, sans_ansi(sortie))
        assert "--include-apps" in greffes[0], (
            "sans --include-apps, `mmu` n'arrive jamais sur le PATH : %r" % greffes[0]
        )
        assert "--force" in greffes[0], (
            "sans --force, pipx repond « already seems to be installed » et ne "
            "reenregistre pas les applications : %r" % greffes[0]
        )


def test_la_ligne_de_commande_SEULE_ne_greffe_rien(machine_vierge):
    """AC5 + AC8 -- cible au PREMIER bord du menu.

    `mmu-cli` est alors le paquet principal : pipx expose `mmu` de lui-meme, et
    une greffe serait au mieux inutile, au pire une reinstallation.
    """
    sortie = jouer_le_dialogue(["--dry-run"], ["1"] + ENTREE_SEULE, machine_vierge)
    assert plan_pipx(sortie) == ["pipx install --force mmu-cli", "pipx ensurepath"], \
        sans_ansi(sortie)


def test_aucune_greffe_de_cli_ne_se_passe_de_include_apps():
    """AC5 -- frontiere NEGATIVE, sur les deux scripts et sur leur TEXTE.

    Le banc precedent mesure le plan de quelques chemins. Celui-ci attrape une
    greffe ajoutee sur un chemin qu'aucun test ne jouerait encore -- et il y en
    a maintenant un de plus depuis que la mise a jour existe.
    """
    vues = 0
    for script in (INSTALL_SH, INSTALL_PS1):
        for appel in appels_a_inject(code_du_script(script)):
            if not re.search(r"mmu-cli|PaquetCli|PAQUET_CLI", appel):
                continue  # la greffe d'OpenCV n'expose aucune application
            vues += 1
            assert "include-apps" in appel, (
                "%s greffe la CLI sans --include-apps : %r" % (script.name, appel)
            )
    # Trois : les deux branches de bash (avec et sans les arguments TestPyPI)
    # et l'unique de PowerShell, qui assemble ses arguments en tableau. Le
    # cardinal est epingle parce qu'une frontiere qui ne trouve RIEN a mesurer
    # est verte pour la pire des raisons.
    assert vues == 3, (
        "trois appels de greffe attendus, %d trouves. Zero rendrait cette "
        "frontiere verte sans rien mesurer." % vues
    )


# ====================================================================== AC6
#  Les drapeaux : les anciens tiennent, les nouveaux s'ajoutent, et un
#  drapeau donne SUPPRIME sa question.
# ==========================================================================

def test_les_drapeaux_historiques_marchent_encore(machine_vierge):
    """AC6 -- `--gui`, `--testpypi`, `--version`, `--dry-run` n'ont pas bouge de sens.

    Ils ont quitte le MENU le 2026-09-07 ; ils n'ont pas quitte le script. Une
    capacite retiree du menu et supprimee du code n'est pas la meme decision, et
    Egan n'a tranche que la premiere.
    """
    _, gui = jouer_sans_terminal(["--dry-run", "--gui"], machine_vierge)
    assert "mmu-cli[gui]" in " ".join(plan_pipx(gui)), gui

    _, testpypi = jouer_sans_terminal(["--dry-run", "--testpypi"], machine_vierge)
    plan = " ".join(plan_pipx(testpypi))
    assert "mmu-tui-test" in plan and "mmu-cli-test" in plan, testpypi
    assert "test.pypi.org" in plan, (
        "TestPyPI n'heberge pas les dependances : sans index supplementaire "
        "vers le vrai PyPI, la resolution echoue.\n%s" % testpypi
    )

    _, version = jouer_sans_terminal(["--dry-run", "--version", "0.2.0"], machine_vierge)
    plan = plan_pipx(version)
    assert "pipx install --force mmu-tui==0.2.0" in plan, version
    assert any("mmu-cli==0.2.0" in l for l in plan), (
        "les deux distributions doivent partir a la MEME version : c'est ce que "
        "`mmu-tui` epingle de son cote.\n%s" % version
    )


def test_le_suffixe_du_BAC_A_SABLE_porte_AUSSI_sur_les_COMMANDES(machine_vierge):
    """`--testpypi` renomme les paquets ET les commandes console.

    **Le defaut que cette frontiere ferme, et il a ete paye le 2026-09-08.**
    La frontiere d'a cote fait varier `--testpypi` et n'assert que sur le PLAN
    PIPX : elle voyait `mmu-cli-test` partir, et restait verte pendant que le
    script annoncait verifier l'installation par `mmu --version`. Faire varier
    un drapeau ne suffit pas -- encore faut-il asserter sur la surface qu'il
    change.

    Ce que le renommage fait vraiment, mesure sur les roues REELLEMENT publiees
    en 0.1.0 sur TestPyPI (`publish.yml` reecrit les `[project.scripts]` en
    meme temps que le `name`) :

        mmu_cli_test-0.1.0-py3-none-any.whl   -> console_scripts : mmu-test
        mmu_tui_test-0.1.0-py3-none-any.whl   -> console_scripts : mmu-tui-test

    Et pourquoi le silence coutait plus cher que l'echec : sur une machine qui
    porte deja un `mmu` REEL -- celle de quelqu'un qui repete l'installation --
    `mmu --version` REPOND. La verification annoncait alors un succes en
    exercant une installation de production, jamais celle du bac a sable.

    Les DEUX sens sont poses, et par des egalites de presence/absence : sans le
    drapeau, aucune commande suffixee ne doit apparaitre. Une frontiere qui ne
    jouerait que le regime TestPyPI resterait verte si le suffixe etait pose
    inconditionnellement.
    """
    _, sans = jouer_sans_terminal(
        ["--dry-run", "--tui", "--verifier", "--sans-ffmpeg", "--sans-path",
         "--sans-raccourci"], machine_vierge)
    _, avec = jouer_sans_terminal(
        ["--dry-run", "--testpypi", "--tui", "--verifier", "--sans-ffmpeg",
         "--sans-path", "--sans-raccourci"], machine_vierge)

    sans, avec = sans_ansi(sans), sans_ansi(avec)

    def ligne_de_verification(sortie):
        for brute in sortie.splitlines():
            if "verification ...." in brute:
                return brute
        raise AssertionError(
            "le recapitulatif ne porte plus de ligne de verification :\n" + sortie)

    nominale, bac = ligne_de_verification(sans), ligne_de_verification(avec)

    # Le regime NOMINAL nomme les commandes reelles, et AUCUNE suffixee.
    assert "mmu --version" in nominale, nominale
    assert "mmu-tui sur le PATH" in nominale, nominale
    assert "-test" not in nominale, (
        "le suffixe du bac a sable a fuite dans le regime nominal : " + nominale)

    # Le regime BAC A SABLE nomme les commandes que la roue de test POSE.
    assert "mmu-test --version" in bac, (
        "la verification lance une commande que l'installation TestPyPI n'a "
        "jamais posee : " + bac)
    assert "mmu-tui-test sur le PATH" in bac, bac

    # Et le plan pipx reste, lui, sur les PAQUETS suffixes -- les deux surfaces
    # bougent ensemble ou la frontiere ne mesure qu'une moitie du renommage.
    plan = " ".join(plan_pipx(avec))
    assert "mmu-cli-test" in plan and "mmu-tui-test" in plan, plan


def test_install_ps1_derive_les_QUATRE_noms_du_SUFFIXE_en_UN_seul_point():
    """Le pendant Windows du precedent, mesure sur le TEXTE.

    **Pourquoi textuellement, dit plutot que tu** : ce banc ne joue pas
    `install.ps1` -- `pwsh` n'est pas garanti present, et le module le declare
    deja (« il ne mesure pas Windows »). Le mesurer par son texte est plus
    faible que de le jouer ; c'est neanmoins ce qui distingue une frontiere
    d'une absence de frontiere, et le defaut du 2026-09-08 etait exactement
    de cette forme -- deux derivations sur quatre, ecrites.

    Deux volets, dont un NEGATIF :

    * les quatre noms se derivent bien du suffixe ;
    * et le suffixe ne se derive QU'UNE fois. Un second point de derivation
      est ce qui a produit le defaut : les commandes etaient figees en tete de
      fichier, le suffixe calcule 400 lignes plus bas, et rien ne reliait les
      deux.
    """
    texte = INSTALL_PS1.read_text(encoding="utf-8")

    for attendu in ('$PaquetCli   = "$DistCli$Suffixe"',
                    '$PaquetTui   = "$DistTui$Suffixe"',
                    '$CommandeCli = "$CommandeCli$Suffixe"',
                    '$CommandeTui = "$CommandeTui$Suffixe"'):
        assert attendu in texte, (
            "install.ps1 ne derive plus ce nom du suffixe du bac a sable : "
            + attendu)

    combien = texte.count('$Suffixe = ""')
    assert combien == 1, (
        "le suffixe du bac a sable se derive en %d endroits : deux points de "
        "derivation divergent, c'est le defaut du 2026-09-08" % combien)


def test_un_paquet_FACULTATIF_impossible_a_poser_n_arrete_PAS_l_installation(
        machine_sans_gestionnaire):
    """`EPIC11-ARB-270` -- Egan, 2026-09-08, par invite.

    **Le parcours reel qui l'a etabli.** Sur un Mac sans Homebrew, l'etape
    ffmpeg rendait `Echec :` et un code 1 -- APRES le recapitulatif, sans que
    `mmu` ait ete pose. Or ffmpeg est la SEULE dependance systeme, elle est
    facultative par construction (`--sans-ffmpeg`, et une question dediee), et
    tout ce qui ne touche pas a la video marche sans elle.

    Deux incoherences internes le disaient avant qu'on le mesure :

    * l'appelant ffmpeg portait deja le commentaire « Pas d'echec sec : le
      reste de l'installation reste utile » -- donc un `brew install` qui
      ECHOUE laissait continuer, mais un Homebrew ABSENT tuait tout ;
    * l'appelant pipx portait un repli `pip --user` **inatteignable** :
      `echouer` sortait du script avant que le `if !` puisse lire son code.

    Ce que cette frontiere pose, et le troisieme point est le plus utile :

    1. le script va au bout -- code 0, et « Termine » ;
    2. il le DIT plutot que de le taire : l'absence de gestionnaire est
       annoncee et le remede nomme ;
    3. le repli pipx est REELLEMENT atteint. Sans lui, la machine repartirait
       sans pipx, donc sans rien d'installe -- un succes de facade.
    """
    code, sortie = jouer_sans_terminal(
        ["--dry-run", "--non-interactif", "--cli", "--sans-path",
         "--sans-raccourci", "--sans-verification",
         # Voir `IGNORER_HORS_DU_PATH` : une machine « sans gestionnaire »
         # trouve sinon le `pipx` REEL du conteneur -- les runners GitHub en
         # portent un dans `/usr/local/bin` --, et le repli `pip --user` que ce
         # test mesure n'est jamais atteint.
         IGNORER_HORS_DU_PATH], machine_sans_gestionnaire)
    sortie = sans_ansi(sortie)

    assert code == 0, (
        "un paquet FACULTATIF impossible a poser arrete encore toute "
        "l'installation :\n" + sortie)
    assert "Termine" in sortie, sortie

    # 2 -- l'issue est nommee, pas tue.
    assert "Aucun gestionnaire de paquets reconnu" in sortie, sortie

    # 3 -- le repli que `echouer` rendait inatteignable.
    assert "repli par pip --user" in sortie, (
        "le repli pipx n'est toujours pas atteint : la fonction sort encore "
        "avant que son appelant puisse decider.\n" + sortie)


def test_mais_PYTHON_impossible_a_poser_arrete_TOUJOURS(
        machine_sans_gestionnaire_ni_python):
    """Le volet symetrique, et sans lui le precedent serait un blanc-seing.

    `EPIC11-ARB-270` ne dit pas « plus jamais d'echec » : il dit que
    l'APPELANT decide. Un seul appelant a une raison de refuser -- Python
    n'est pas facultatif, et une installation qui continuerait sans lui ne
    poserait rien du tout tout en annoncant « Termine ».

    Une frontiere qui ne jouerait que le cas facultatif resterait verte si la
    fonction cessait d'echouer PARTOUT.
    """
    code, sortie = jouer_sans_terminal(
        ["--dry-run", "--non-interactif", "--cli", "--sans-ffmpeg",
         "--sans-path", "--sans-raccourci", "--sans-verification",
         # Voir `IGNORER_HORS_DU_PATH` : « sans Python » ne se fabrique pas
         # sans lui depuis la story 8.14.
         IGNORER_HORS_DU_PATH],
        machine_sans_gestionnaire_ni_python)
    sortie = sans_ansi(sortie)

    assert code == 1, (
        "Python indisponible ne doit PAS laisser l'installation continuer :\n"
        + sortie)
    assert "Termine" not in sortie, sortie
    # Jamais un blocage sec : l'echec nomme ou aller chercher Python.
    assert "python.org/downloads" in sortie, (
        "l'arret ne nomme aucune issue :\n" + sortie)


def _machine_macos(dossier: Path, *, majeur: str, arch: str = "arm64",
                   avec_python: bool = True) -> dict:
    """Une machine macOS jouable depuis Linux : `uname`, `sw_vers`, `brew`.

    Les trois sont factices et c'est le seul moyen d'atteindre la branche --
    le conteneur qui joue ce banc est un Linux sans Homebrew. `_deposer_outil`
    plutot que `write_text` : la PATH fabriquee est faite de LIENS, et ecrire
    a travers l'un d'eux ecrase le vrai binaire du systeme (finding `C2-3`).

    `majeur` ET `arch` sont des PARAMETRES, pas des constantes : la garde
    depend de DEUX drapeaux, et chacun doit varier seul pour qu'on sache
    lequel a mordu. Une fabrique qui figerait l'architecture ferait passer la
    frontiere de version pour la seule cause -- ce qu'elle a ete, a tort,
    pendant une demi-journee.
    """
    env = _fabriquer_machine(dossier, avec_ffmpeg=False, liste_pipx="",
                             avec_affichage=False, avec_python=avec_python)
    binaires = Path(env["PATH"].split(os.pathsep)[0])
    _deposer_outil(binaires, "uname",
                   "#!/bin/sh\n"
                   "# `uname -s` donne le systeme, `uname -m` l'architecture.\n"
                   "# Les deux sont lus par install.sh, et pour deux gardes\n"
                   "# differentes : un `uname` factice qui ne repondrait qu'a\n"
                   "# `-s` rendrait « Darwin » a `-m`, donc jamais x86_64, donc\n"
                   "# une garde Intel verte en ne voyant rien.\n"
                   "case \"$1\" in\n"
                   "    -m) echo %s ;;\n"
                   "    *)  echo Darwin ;;\n"
                   "esac\n" % arch)
    _deposer_outil(binaires, "sw_vers",
                   "#!/bin/sh\n"
                   "# `sw_vers -productVersion` : le script n'en lit que le majeur.\n"
                   "echo %s.7.6\n" % majeur)
    _deposer_outil(binaires, "brew",
                   "#!/bin/sh\n"
                   "# Homebrew factice : sa presence suffit a elire GESTIONNAIRE.\n"
                   "exit 0\n")
    return env


def test_macOS_12_AVERTIT_avant_des_HEURES_de_compilation_et_CONTINUE(tmp_path):
    """Le parcours reel d'Egan, 2026-09-08, et il etait bloque dessus.

    Sa trace, verbatim : `Warning: You are using macOS 12.` puis
    `==> Would install 1 formula: python@3.12` et une suite de
    `Already downloaded: ...--mpdecimal.rb` -- des RECETTES, pas des bouteilles
    `.bottle.tar.gz`. Homebrew ne sert plus de binaires precompiles pour
    macOS 12 : il compile depuis les sources, et sur ffmpeg et son arbre ca se
    compte en heures. Rien dans le script ne le disait : il lancait.

    Ce que le produit DECLARE n'etait pas en cause -- les roues Python de
    macOS 12 existent sur les deux architectures (mesure du 2026-09-08). C'est
    le CHEMIN D'INSTALLATION qui ne tenait pas le plancher, et c'est un defaut
    different de celui que le plancher declare.

    Trois choses, et la troisieme est la seule qui distingue cette garde d'un
    blocage sec (`EPIC11-ARB-89`) :

    1. l'avertissement NOMME la version et la cause ;
    2. il donne la voie SANS compilation, propre a ce paquet-la ;
    3. il laisse une issue dans les deux sens, et le DEFAUT ne consomme pas
       des heures a l'insu de qui lance.

    **Le point 3 a change de MECANISME le 2026-09-08, pas de nature**
    (`EPIC11-ARB-271`). Jusque-la, le defaut REFUSAIT la compilation et
    l'etape se terminait sur « ffmpeg n'a pas pu etre pose. L'installation
    continue. » -- ce qui renvoyait au terminal un outil que la machine ne
    detecterait ensuite pas, defaut qu'Egan a constate en vrai le meme jour.
    Le defaut EMPRUNTE desormais la voie sans compilation au lieu de
    l'afficher. Ce que la frontiere mesure est donc : aucune compilation n'est
    lancee, le repli l'est, et l'installation va au bout.

    Ce test garde son nom : c'est le meme regime -- macOS 12, ffmpeg, un
    avertissement, pas d'heures perdues -- et le renommer perdrait le lien
    avec le parcours d'Egan qu'il rejoue.
    """
    # `arm64` EXPLICITE : sans lui, on ne saurait pas lequel des deux bras de
    # la garde a mordu, et la frontiere resterait verte si le bras version
    # disparaissait.
    env = _machine_macos(tmp_path, majeur="12", arch="arm64")
    code, brut = jouer_sans_terminal(
        ["--dry-run", "--non-interactif", "--cli", "--sans-path",
         "--sans-raccourci", "--sans-verification"], env)
    sortie = sans_ansi(brut)

    assert code == 0, ("macOS 12 ne doit pas arreter l'installation :\n"
                       + sortie)
    assert "Termine" in sortie, sortie

    # 1 -- la version et la cause, pas un motif generique.
    assert "macOS 12" in sortie, (
        "l'avertissement ne nomme pas la version lue :\n" + sortie)
    assert "ne fournit plus de binaires precompiles" in sortie, sortie

    # 2 -- la voie sans compilation, celle de ffmpeg et pas une autre.
    assert "evermeet.cx" in sortie, (
        "aucune voie sans compilation n'est nommee pour ffmpeg :\n" + sortie)

    # 3 -- le defaut ne consomme pas des heures a l'insu de qui lance : AUCUN
    #      `brew install ffmpeg` dans le plan, et le repli a sa place.
    assert "brew install ffmpeg" not in lignes_de_plan(brut), (
        "le defaut lance encore une compilation Homebrew :\n" + sortie)
    assert "[simulation] verifier le condensat SHA-256 des deux archives" in sortie, (
        "le defaut n'emprunte pas la voie sans compilation, il se contente "
        "encore de l'afficher :\n" + sortie)


def test_macOS_13_ne_declenche_RIEN_de_cette_garde(tmp_path):
    """Le volet symetrique : sans lui, la garde pourrait mordre PARTOUT.

    C'est la regle « une garde fait VARIER le drapeau dont elle depend »
    (CLAUDE.md, 2026-09-06) appliquee ici : un banc qui ne jouerait que
    macOS 12 resterait vert si `homebrew_compile_depuis_les_sources` rendait
    vrai sans condition -- et tous les Mac modernes verraient une question
    inutile devant chaque paquet.

    13 est le plancher parce que c'est la premiere version que Homebrew sert
    encore en bouteilles.
    """
    env = _machine_macos(tmp_path, majeur="13", arch="arm64")
    code, brut = jouer_sans_terminal(
        ["--dry-run", "--non-interactif", "--cli", "--sans-path",
         "--sans-raccourci", "--sans-verification"], env)
    sortie = sans_ansi(brut)

    assert code == 0, sortie
    assert "ne fournit plus de binaires precompiles" not in sortie, (
        "la garde mord sur une version que Homebrew sert en bouteilles :\n"
        + sortie)
    assert "evermeet.cx" not in sortie, sortie


def test_un_Mac_INTEL_RECENT_declenche_la_garde_ET_NOMME_SA_CAUSE(tmp_path):
    """Le contre-exemple d'Egan, 2026-09-08, et il a demoli ma premiere garde.

    J'avais ecrit, la veille : « macOS 13 et au-dela sont toujours servis en
    bouteilles, votre monteuse n'aura probablement pas ce probleme ». Sa
    machine -- un **Intel 2018 en Sequoia (15)**, donc trois versions au-dessus
    du plancher -- restait bloquee sur `==> make`. La garde, qui ne lisait que
    la VERSION, n'avait rien annonce.

    La cause, mesuree sur l'API de Homebrew le jour meme : une etiquette macOS
    Intel s'ecrit sans prefixe (`sonoma`, `ventura`), et `python@3.12`,
    `openssl@3` et `mpdecimal` n'en ont AUCUNE -- seulement des `arm64_*`.
    `ffmpeg` n'en a qu'une, pour Sonoma. Sur un Mac Intel, Homebrew n'a
    pratiquement plus rien a servir.

    La frontiere porte sur DEUX choses, et la seconde compte autant :

    1. la garde se declenche sur une version RECENTE, donc par le bras
       architecture et par lui seul ;
    2. le message nomme la BONNE cause. Dire « macOS 15 est trop ancien » a
       quelqu'un en Sequoia l'enverrait chercher au mauvais endroit -- c'est
       le meme defaut qu'un motif faux dans un ecran.
    """
    env = _machine_macos(tmp_path, majeur="15", arch="x86_64")
    code, brut = jouer_sans_terminal(
        ["--dry-run", "--non-interactif", "--cli", "--sans-path",
         "--sans-raccourci", "--sans-verification"], env)
    sortie = sans_ansi(brut)

    assert code == 0, sortie
    # 1 -- le bras architecture mord seul, sur une version tres au-dessus du
    #      plancher.
    assert "ne publie plus de binaires precompiles" in sortie, (
        "un Mac Intel recent ne declenche pas la garde : elle ne lit encore "
        "que la version :\n" + sortie)
    assert "evermeet.cx" in sortie, sortie

    # 2 -- la cause NOMMEE, et surtout pas l'autre.
    assert "Mac Intel" in sortie, (
        "la garde se declenche sans dire pourquoi :\n" + sortie)
    assert "macOS 15 :" not in sortie, (
        "la garde impute a la version ce qui vient de l'architecture :\n"
        + sortie)


def test_un_Mac_APPLE_SILICON_RECENT_ne_declenche_RIEN(tmp_path):
    """Le volet symetrique du bras architecture, et sans lui la garde mordrait
    sur tous les Mac.

    Meme version que la frontiere precedente -- Sequoia -- et seule
    l'architecture change. C'est la regle « une garde fait VARIER le drapeau
    dont elle depend » prise au mot : les deux frontieres ne different que
    par `arch`, si bien qu'un `mac_intel_sans_bouteilles` rendant vrai sans
    condition fait rougir celle-ci et elle seule.

    Apple Silicon est le cas ou Homebrew a EFFECTIVEMENT ses bouteilles
    (`arm64_sequoia` existe pour les quatre formules mesurees) : y poser une
    question serait une friction sans information.
    """
    env = _machine_macos(tmp_path, majeur="15", arch="arm64")
    code, brut = jouer_sans_terminal(
        ["--dry-run", "--non-interactif", "--cli", "--sans-path",
         "--sans-raccourci", "--sans-verification"], env)
    sortie = sans_ansi(brut)

    assert code == 0, sortie
    assert "binaires precompiles" not in sortie, (
        "la garde mord sur une plateforme que Homebrew sert en bouteilles :\n"
        + sortie)
    assert "evermeet.cx" not in sortie, sortie


def test_une_version_de_macOS_INCONNUE_n_avertit_sur_RIEN(tmp_path):
    """On n'avertit pas sur une supposition.

    `sw_vers` peut etre absent, ou rendre autre chose qu'un nombre. La garde
    laisse alors `MACOS_MAJEUR` vide et ne se declenche PAS -- plutot que de
    traiter l'inconnu comme un vieux systeme, ce qu'un `-lt` sur une chaine
    vide ferait en shell POSIX (`[ "" -lt 13 ]` est une ERREUR, pas un faux).

    Sans cette frontiere, la garde rendrait une erreur `sh` visible a
    l'utilisateur sur toute machine ou `sw_vers` manque.
    """
    env = _fabriquer_machine(tmp_path, avec_ffmpeg=False, liste_pipx="",
                             avec_affichage=False)
    binaires = Path(env["PATH"].split(os.pathsep)[0])
    _deposer_outil(binaires, "uname", "#!/bin/sh\necho Darwin\n")
    _deposer_outil(binaires, "brew", "#!/bin/sh\nexit 0\n")
    # Pas de `sw_vers` du tout : le cas d'une version illisible.

    code, brut = jouer_sans_terminal(
        ["--dry-run", "--non-interactif", "--cli", "--sans-path",
         "--sans-raccourci", "--sans-verification"], env)
    sortie = sans_ansi(brut)

    assert code == 0, sortie
    assert "ne fournit plus de binaires precompiles" not in sortie, sortie
    for bruit in ("integer expression expected", "unary operator expected",
                  "not found"):
        assert bruit not in sortie, (
            "la garde fuit une erreur de shell quand la version est "
            "illisible :\n" + sortie)


def test_un_drapeau_donne_SUPPRIME_sa_question(machine_sans_ffmpeg):
    """AC6 -- on ne demande pas ce qu'on a deja dit.

    Le banc ne fournit AUCUNE reponse : si une seule question survivait a son
    drapeau, le dialogue attendrait et le delai rougirait.
    """
    sortie = sans_ansi(jouer_le_dialogue(
        ["--dry-run", "--cli", "--testpypi", "--sans-path",
         "--sans-verification", "--sans-ffmpeg"],
        [], machine_sans_ffmpeg,
    ))
    assert "Ton choix" not in sortie, "une question a survecu a son drapeau :\n%s" % sortie
    assert plan_pipx(sortie) == [
        "pipx install --pip-args=--index-url https://test.pypi.org/simple/ "
        "--extra-index-url https://pypi.org/simple --force mmu-cli-test"
    ], sortie


def test_une_option_inconnue_rend_2_et_renvoie_a_l_aide():
    """AC6 -- une faute de frappe n'installe rien au hasard."""
    acheve = subprocess.run(
        ["bash", str(INSTALL_SH), "--nawak"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True, timeout=30,
    )
    assert acheve.returncode == 2, acheve.stdout
    assert b"--help" in acheve.stdout, acheve.stdout


def test_l_aide_ne_lit_pas_le_script_par_son_chemin():
    """AC6 -- `--help` doit marcher sous `curl | bash`, ou `$0` vaut `bash`.

    L'ancienne aide faisait `sed -n '2,30p' "$0"` : sous `curl | bash`, `$0`
    n'est pas le script et l'aide rendait le contenu de `bash` ou rien du tout.
    """
    code = code_du_script(INSTALL_SH)
    assert '"$0"' not in code, (
        "install.sh lit encore son propre chemin : sous `curl | bash`, il n'en a pas."
    )
    acheve = subprocess.run(
        ["bash", "-c", "cat %s | bash -s -- --help" % INSTALL_SH],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True, timeout=60,
    )
    assert acheve.returncode == 0, acheve.stdout
    assert b"--non-interactif" in acheve.stdout, acheve.stdout


# =========================================== la relance devient une mise a jour
#  Egan, 2026-09-07, sur la proposition : « Superbe ».
# ==========================================================================

def test_sur_une_machine_vierge_aucune_question_de_reprise(machine_vierge):
    """L'autre sens du drapeau : rien d'installe, rien a reprendre."""
    sortie = sans_ansi(jouer_le_dialogue(["--dry-run"], ENTREE_SEULE, machine_vierge))
    assert "est deja installe" not in sortie, sortie
    assert "operation ....... installation" in sortie, sortie


def test_la_relance_NOMME_ce_qui_est_deja_pose(machine_deja_installee):
    """« Une seconde execution detecte la version deja posee, la NOMME. »

    Nommer plutot que « quelque chose est deja installe » : c'est la difference
    entre un utilisateur qui sait ce qu'il a et un utilisateur qui devine.
    """
    sortie = sans_ansi(jouer_le_dialogue(["--dry-run"], ENTREE_SEULE, machine_deja_installee))
    assert "deja installe : mmu-tui 0.1.0" in sortie, sortie
    assert "mmu-tui 0.1.0 est deja installe." in sortie, sortie


def test_la_relance_MET_A_JOUR_au_lieu_de_tout_refaire(machine_deja_installee):
    """« ... et propose la mise a jour au lieu de tout refaire. »

    `--include-injected` n'est pas un ornement : sans lui, pipx met a jour
    l'application et laisse `mmu-cli` a son ancienne version, ce qui est
    exactement la divergence que `mmu-tui` epingle pour l'eviter. Et la greffe
    est rejouee, parce que `pipx upgrade` ne reenregistre aucune application.
    """
    sortie = jouer_le_dialogue(["--dry-run"], ENTREE_SEULE, machine_deja_installee)
    assert plan_pipx(sortie) == [
        "pipx upgrade --include-injected mmu-tui",
        "pipx inject --include-apps --force mmu-tui mmu-cli",
        "pipx ensurepath",
    ], sans_ansi(sortie)
    assert "operation ....... mise a jour de mmu-tui 0.1.0" in sans_ansi(sortie)


def test_la_relance_derive_les_composants_de_CE_QUI_EST_POSE(machine_cli_deja_installee):
    """Deuxieme fabrique, distinguable de la premiere.

    Une derivation qui rendrait toujours « la TUI » -- ou un `head -n1` qui
    rendrait toujours la premiere entree -- resterait verte sur la seule
    machine ou `mmu-tui` est pose. Il en faut donc une seconde, ou c'est
    `mmu-cli`.
    """
    sortie = jouer_le_dialogue(["--dry-run"], ENTREE_SEULE, machine_cli_deja_installee)
    assert plan_pipx(sortie) == [
        "pipx upgrade --include-injected mmu-cli",
        "pipx ensurepath",
    ], sans_ansi(sortie)


def test_la_relance_offre_de_TOUT_REFAIRE(machine_deja_installee):
    """Jamais une seule issue : la mise a jour est le defaut, pas la seule voie."""
    sortie = jouer_le_dialogue(["--dry-run"], ["2"] + ENTREE_SEULE, machine_deja_installee)
    assert plan_pipx(sortie) == PLAN_PAR_DEFAUT, sans_ansi(sortie)


def test_la_relance_offre_de_NE_RIEN_CHANGER(machine_deja_installee):
    """Et la troisieme issue : sortir sans avoir rien touche, en le disant."""
    sortie = sans_ansi(jouer_le_dialogue(["--dry-run"], ["3"], machine_deja_installee))
    assert "Rien n'a ete change" in sortie, sortie
    assert plan_pipx(sortie) == [], sortie


def test_un_drapeau_de_reprise_supprime_la_question(machine_deja_installee):
    """AC6 applique aux deux drapeaux neufs, dans les deux sens."""
    maj = sans_ansi(jouer_le_dialogue(["--dry-run", "--mettre-a-jour"],
                                      ENTREE_SEULE, machine_deja_installee))
    assert "est deja installe." not in maj, (
        "la question de reprise a survecu a --mettre-a-jour :\n%s" % maj
    )
    assert plan_pipx(maj)[0] == "pipx upgrade --include-injected mmu-tui", maj

    refaire = sans_ansi(jouer_le_dialogue(["--dry-run", "--reinstaller"],
                                          ENTREE_SEULE, machine_deja_installee))
    assert "est deja installe." not in refaire, (
        "la question de reprise a survecu a --reinstaller :\n%s" % refaire
    )
    assert plan_pipx(refaire) == PLAN_PAR_DEFAUT, refaire


def test_un_drapeau_de_composants_EXPLICITE_gagne_sur_le_disque(machine_deja_installee):
    """`--cli` sur une machine qui porte la TUI ne doit pas etre avale.

    C'est le defaut exact que la premiere ecriture de la mise a jour portait :
    l'etat du disque ecrasait le drapeau, en silence. Un drapeau donne qui ne
    change rien est pire qu'un drapeau refuse.
    """
    sortie = jouer_le_dialogue(["--dry-run", "--cli", "--mettre-a-jour"],
                               ENTREE_SEULE, machine_deja_installee)
    assert plan_pipx(sortie) == [
        "pipx upgrade --include-injected mmu-cli",
        "pipx ensurepath",
    ], sans_ansi(sortie)


# ======================================================== la desinstallation
#  Egan : « Oui c'est bien. Possible des la release ? » -- oui, et elle retire
#  aussi la ligne de profil, sinon elle laisse la moitie du degat.
# ==========================================================================

#: Les TROIS issues de la desinstallation (`EPIC11-ARB-274`, story 8.12), mot
#: pour mot. Elles doivent etre les MEMES dans les deux scripts, pour la meme
#: raison que les cinq libelles du raccourci : la seule comparaison croisee qui
#: existe ne porte que sur les lignes `pipx `, donc une divergence d'invite y
#: est invisible.
LIBELLES_DES_TROIS_ISSUES = (
    "l'application seule -- ni Python, ni ffmpeg, ni pipx",
    "l'application ET ce que CE SCRIPT a pose (ffmpeg, ffprobe, pipx)",
    "rien pour l'instant -- montre-moi les commandes pour le reste",
)

#: L'intitule de la question, meme discipline.
INTITULE_DES_TROIS_ISSUES = "Que faut-il retirer ?"


def test_la_desinstallation_offre_TROIS_issues_et_le_DEFAUT_est_la_premiere(
        machine_deja_installee):
    """AC1 -- et ce banc REMPLACE `test_desinstaller_ne_pose_aucune_question`.

    L'ancien contrat -- « avoir tape `--desinstaller` EST l'acte conscient,
    aucune question » -- etait juste d'un desinstalleur qui ne retirait que
    l'application. `EPIC11-ARB-274` le renverse, et pour un motif mesure :
    depuis `EPIC11-ARB-271` le script pose LUI-MEME 52 Mo de binaires, si bien
    que « tout supprimer » et « juste mmu » ne sont plus le meme acte. Un seul
    drapeau ne peut pas vouloir dire les deux.

    Trois issues, jamais deux, jamais une (`EPIC11-ARB-89`), et le DEFAUT est
    la premiere -- celle qui ne peut rien casser. Entree seule le prend.
    """
    sortie = sans_ansi(jouer_le_dialogue(["--dry-run", "--desinstaller"], [""],
                                         machine_deja_installee))
    assert INTITULE_DES_TROIS_ISSUES in sortie, sortie
    for rang, libelle in enumerate(LIBELLES_DES_TROIS_ISSUES, start=1):
        assert "%d) %s" % (rang, libelle) in sortie, (
            "l'issue %d manque, ou son libelle a bouge :\n%s" % (rang, sortie))
    # Le defaut se MONTRE, il ne se devine pas -- meme discipline que les cinq
    # questions de l'installation.
    assert "1) %s [defaut]" % LIBELLES_DES_TROIS_ISSUES[0] in sortie, sortie
    # ... et Entree seule l'a bien pris : l'issue 1 annonce les distributions.
    assert "mmu-tui" in sortie and "mmu-cli" in sortie, sortie
    assert "Ni Python, ni ffmpeg, ni pipx ne sont touches" in sortie, (
        "l'issue 1 doit dire ce qu'elle NE touche PAS :\n%s" % sortie)


def test_sans_terminal_la_desinstallation_prend_l_ISSUE_1_et_le_DIT(
        machine_deja_installee):
    """AC1, l'autre sens du drapeau -- « une machine muette ne retire jamais
    plus que l'application ».

    C'est le regime du `curl | bash` sans terminal, de la CI, du conteneur. La
    question ne peut pas se poser : le defaut est pris ET ANNONCE, jamais un
    blocage sec.
    """
    _, brut = jouer_sans_terminal(["--dry-run", "--desinstaller"],
                                  machine_deja_installee)
    sortie = sans_ansi(brut)
    assert "pas de terminal : je prends 1)" in sortie, sortie
    assert LIBELLES_DES_TROIS_ISSUES[0] in sortie, sortie

    # Et le mode explicite dit une AUTRE raison, pour le meme defaut : les deux
    # regimes muets sont distingues, comme ils le sont deja a l'installation.
    _, brut = jouer_sans_terminal(
        ["--dry-run", "--desinstaller", "--non-interactif"], machine_deja_installee)
    assert "mode non interactif : je prends 1)" in sans_ansi(brut), sans_ansi(brut)


def test_l_annonce_du_desinstalleur_nomme_les_QUATRE_distributions(
        machine_deja_installee):
    """Ce qu'il RETIRE et ce qu'il ANNONCE doivent etre le meme ensemble.

    La boucle retire quatre distributions -- les reelles et celles du bac a
    sable -- et l'annonce n'en nommait que deux. Le regime ou ca mord est
    exactement celui de la pre-release : quelqu'un installe `mmu-cli-test`,
    lit « vont etre retires : mmu-tui, mmu-cli », en conclut que la commande
    ne le concerne pas, et garde un `mmu-test` qui traine a cote de la vraie
    version.

    La frontiere est posee sur les DEUX suffixes, sinon un desinstalleur qui
    cesserait de retirer les paquets de test resterait vert : c'est le meme
    piege qu'un `find` fautif rendant toujours le premier element.
    """
    sortie = sans_ansi(jouer_le_dialogue(["--dry-run", "--desinstaller"], ["1"],
                                         machine_deja_installee))
    for distribution in ("mmu-tui", "mmu-cli", "mmu-tui-test", "mmu-cli-test"):
        assert distribution in sortie, (
            "le desinstalleur retire %s sans l'annoncer :\n%s"
            % (distribution, sortie))


def test_desinstaller_retire_AUSSI_la_ligne_de_profil(tmp_path, machine_deja_installee):
    """La moitie du degat n'est pas une desinstallation.

    Sans ce retrait, le PATH de l'utilisateur garde une entree vers un
    repertoire vide, indefiniment, et rien ne le lui dit. Le fichier est copie
    avant d'etre edite : on ne touche pas au profil de quelqu'un sans filet.
    """
    env = dict(machine_deja_installee)
    maison = tmp_path / "maison"
    maison.mkdir()
    env["HOME"] = str(maison)
    profil = maison / ".bashrc"
    profil.write_text(
        "export EDITOR=vim\n"
        "\n"
        "# Created by `pipx` on 2026-09-07 16:00:00\n"
        'export PATH="$PATH:/root/.local/bin"\n'
        "alias ll='ls -l'\n"
    )

    sortie = sans_ansi(jouer_le_dialogue(["--desinstaller"], ["1"], env))
    assert "Termine" in sortie, sortie

    reste = profil.read_text()
    assert "Created by `pipx`" not in reste, reste
    assert '.local/bin' not in reste, reste
    # ... et le reste du profil est intact, ce qui est le vrai enjeu.
    assert "export EDITOR=vim" in reste, reste
    assert "alias ll='ls -l'" in reste, reste
    # ... avec une copie de secours, parce qu'editer un profil ne se defait pas.
    assert (maison / ".bashrc.mmu-sauvegarde").exists(), sorted(
        p.name for p in maison.iterdir()
    )


def test_desinstaller_ne_touche_a_rien_quand_il_n_y_a_rien(tmp_path, machine_deja_installee):
    """L'autre sens : un profil sans ligne pipx sort indemne, et sans copie.

    Une desinstallation qui reecrirait un fichier auquel elle n'a rien a
    changer laisserait derriere elle une copie de secours inutile et une date
    de modification fausse -- deux signaux qui mentent.
    """
    env = dict(machine_deja_installee)
    maison = tmp_path / "maison_propre"
    maison.mkdir()
    env["HOME"] = str(maison)
    profil = maison / ".bashrc"
    profil.write_text("export EDITOR=vim\n")

    sortie = sans_ansi(jouer_le_dialogue(["--desinstaller"], ["1"], env))
    assert "rien a y retirer" in sortie, sortie
    assert profil.read_text() == "export EDITOR=vim\n"
    assert not (maison / ".bashrc.mmu-sauvegarde").exists()


# ====================================================================== AC8
#  Les plans, et la regle des fabriques.
# ==========================================================================

#: Deux jeux de reponses DISTINGUABLES, cibles aux deux BORDS du premier menu.
#: Un jeu uniforme ne verrait ni une permutation des questions, ni un balayage
#: qui saute la derniere option.
JEUX_DE_REPONSES = {
    "cli_seule_bord_de_tete": (
        ["1", "1", "1"],
        ["pipx install --force mmu-cli", "pipx ensurepath"],
    ),
    "cli_et_tui_bord_de_queue": (
        ["2", "1", "1"],
        PLAN_PAR_DEFAUT,
    ),
    "cli_et_tui_sans_path_ni_verification": (
        ["2", "2", "2"],
        [
            "pipx install --force mmu-tui",
            "pipx inject --include-apps --force mmu-tui mmu-cli",
        ],
    ),
}


@pytest.mark.parametrize("nom", sorted(JEUX_DE_REPONSES))
def test_le_dialogue_produit_le_plan_attendu(nom, machine_vierge):
    """AC8 -- le plan de chaque parcours, joue au clavier dans un vrai terminal.

    Les trois jeux different par CHAQUE reponse, pas seulement par la premiere :
    un appariement inverse entre les questions et leurs reponses ne se voit pas
    autrement. Le premier prend l'option 1 du menu, le deuxieme sa DERNIERE
    option, et le troisieme refuse les deux dernieres questions -- des bords que
    le jeu « tout a 1 » ne toucherait jamais.
    """
    reponses, plan_attendu = JEUX_DE_REPONSES[nom]
    sortie = jouer_le_dialogue(["--dry-run"], reponses, machine_vierge)
    assert plan_pipx(sortie) == plan_attendu, sans_ansi(sortie)


def test_le_recapitulatif_dit_la_meme_chose_que_le_plan(machine_avec_affichage):
    """AC8 -- le resume en prose ne peut pas mentir sur les commandes qui suivent.

    Deux surfaces qui decrivent le meme choix divergent des qu'on n'en corrige
    qu'une : c'est le defaut que ce depot a paye plusieurs fois sur ses propres
    documents.
    """
    sortie = sans_ansi(jouer_le_dialogue(["--dry-run", "--gui"], ENTREE_SEULE,
                                         machine_avec_affichage))
    assert "composants ...... mmu + mmu-tui + extra graphique" in sortie, sortie
    assert "apercu video .... oui" in sortie, sortie
    plan = " ".join(plan_pipx(sortie))
    assert "mmu-cli[gui]" in plan and "opencv-python" in plan, sortie


# ============================================================ mise en forme
#  « Une garde qui ne fait varier AUCUN de ses drapeaux ne mesure qu'un seul
#  chemin » -- la sortie est lue par un humain devant un terminal ET par des
#  journaux de CI, et les deux n'ont pas les memes besoins.
# ==========================================================================

def test_aucun_code_ANSI_quand_la_sortie_est_CANALISEE(machine_vierge):
    """La couleur dans un journal n'est pas de la mise en forme, c'est du bruit."""
    _, sortie = jouer_sans_terminal(["--dry-run", "--non-interactif"], machine_vierge)
    assert "\x1b[" not in sortie, (
        "des codes ANSI sont partis dans une sortie canalisee :\n%r" % sortie[:400]
    )


def test_des_codes_ANSI_dans_un_VRAI_terminal(machine_vierge):
    """Et l'autre sens du meme drapeau : devant un humain, la couleur sert."""
    sortie = jouer_le_dialogue(["--dry-run", "--non-interactif"], [], machine_vierge)
    assert "\x1b[" in sortie, (
        "aucune mise en forme dans un vrai terminal : la garde de couleur ne "
        "joue plus qu'un seul cote."
    )


# ====================================================================== AC7
#  PowerShell : le meme dialogue, sur une plomberie DIFFERENTE et mesuree.
# ==========================================================================

#: La seule fonction de `install.ps1` autorisee a appeler `Read-Host`. Toute
#: autre occurrence est une lecture clavier non gardee.
FONCTIONS_DE_LECTURE = ("Demander",)


def _corps_de_fonction(texte: str, nom: str):
    """Le corps d'une fonction PowerShell, par comptage d'accolades.

    Approximation assumee : une accolade dans une chaine de caracteres la
    mettrait en defaut. Il n'y en a aucune dans la fonction visee, et
    `test_les_deux_fonctions_gardees_existent` rougit si elle disparait.
    """
    debut = re.search(r"^function\s+" + re.escape(nom) + r"\s*\{", texte, re.MULTILINE)
    if debut is None:
        return None
    ouverture = texte.index("{", debut.start())
    profondeur = 0
    for indice in range(ouverture, len(texte)):
        if texte[indice] == "{":
            profondeur += 1
        elif texte[indice] == "}":
            profondeur -= 1
            if profondeur == 0:
                return texte[ouverture:indice + 1]
    return None


def test_les_deux_fonctions_gardees_existent():
    """AC7 -- sans elles, la frontiere suivante ne mesurerait plus rien."""
    texte = INSTALL_PS1.read_text()
    for nom in FONCTIONS_DE_LECTURE:
        assert _corps_de_fonction(texte, nom) is not None, (
            "la fonction %s a disparu de install.ps1" % nom
        )


def test_aucun_Read_Host_hors_des_fonctions_gardees():
    """AC7 -- frontiere NEGATIVE : la garde ne se contourne pas par un ajout.

    PowerShell n'a pas de `/dev/tty` : la garde n'est pas une redirection, c'est
    la CONDITION `[Console]::IsInputRedirected` qui precede la lecture. Un
    `Read-Host` pose ailleurs echapperait a cette condition -- et, mesure du
    2026-09-07, `Read-Host` sans console rend la chaine VIDE avec le code de
    sortie 0 : la panne serait muette.
    """
    texte = INSTALL_PS1.read_text()
    total = len(re.findall(r"\bRead-Host\b", code_du_script(INSTALL_PS1)))
    dans_les_gardes = 0
    for nom in FONCTIONS_DE_LECTURE:
        corps = _corps_de_fonction(texte, nom)
        assert corps is not None, nom
        assert "IsInputRedirected" in corps or "$script:Interactif" in corps, (
            "la fonction %s lit le clavier sans consulter la garde" % nom
        )
        dans_les_gardes += len(re.findall(r"\bRead-Host\b", corps))
    assert total == dans_les_gardes == 1, (
        "install.ps1 doit porter exactement un `Read-Host`, dans %r. Trouves : "
        "%d au total, %d dans les fonctions gardees."
        % (list(FONCTIONS_DE_LECTURE), total, dans_les_gardes)
    )


def test_le_discriminant_powershell_est_celui_qui_a_ete_mesure():
    """AC7 -- ni le code de sortie de `Read-Host`, ni sa valeur, ne repondent.

    Mesure du 2026-09-07 (PowerShell 7.5.9) : `Read-Host` sans console rend "" et
    le code 0 ; stdin ferme, il BLOQUE (SIGKILL, code 137). Seul
    `[Console]::IsInputRedirected` distingue -- True sur un tube et sur
    /dev/null, False sur une console.
    """
    code = code_du_script(INSTALL_PS1)
    assert "[Console]::IsInputRedirected" in code, (
        "le discriminant a disparu du CODE de install.ps1 -- le trouver dans "
        "son entete ne prouverait rien."
    )


PWSH = shutil.which("pwsh")


@pytest.mark.skipif(PWSH is None, reason="pwsh absent de cette machine")
def test_powershell_sans_console_prend_le_defaut_et_le_DIT(machine_vierge):
    """AC7 -- le repli de l'AC2, verifie du cote PowerShell plutot que transpose."""
    acheve = subprocess.run(
        [PWSH, "-NoProfile", "-Command",
         "& ([scriptblock]::Create((Get-Content '%s' -Raw))) -DryRun" % INSTALL_PS1],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True, timeout=DELAI, env=dict(machine_vierge),
    )
    sortie = acheve.stdout.decode("utf-8", "replace")
    assert acheve.returncode == 0, sortie
    assert "pas de console : je prends 2)" in sortie, sortie


@pytest.mark.skipif(PWSH is None, reason="pwsh absent de cette machine")
@pytest.mark.parametrize(
    "drapeaux_bash, drapeaux_ps",
    [
        (["--cli"], ["-Cli"]),
        (["--tui"], ["-Tui"]),
        (["--gui"], ["-Gui"]),
        (["--testpypi", "--cli"], ["-TestPyPI", "-Cli"]),
        (["--version", "0.2.0"], ["-Version", "0.2.0"]),
        (["--tui", "--sans-path"], ["-Tui", "-SansPath"]),
    ],
)
def test_les_deux_scripts_produisent_le_MEME_plan(drapeaux_bash, drapeaux_ps, machine_vierge):
    """AC7 -- la parite se mesure, elle ne se decrete pas.

    Six jeux de drapeaux, tous distinguables les uns des autres, et couvrant les
    deux bords du menu de composants. Deux scripts ecrits separement divergent
    des qu'on n'en corrige qu'un ; c'est ce que cette frontiere attrape.
    """
    _, cote_bash = jouer_sans_terminal(["--dry-run"] + drapeaux_bash, machine_vierge)
    acheve = subprocess.run(
        [PWSH, "-NoProfile", "-Command",
         "& ([scriptblock]::Create((Get-Content '%s' -Raw))) -DryRun %s"
         % (INSTALL_PS1, " ".join(drapeaux_ps))],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True, timeout=DELAI, env=dict(machine_vierge),
    )
    cote_ps = acheve.stdout.decode("utf-8", "replace")
    assert acheve.returncode == 0, cote_ps
    assert plan_pipx(cote_bash) == plan_pipx(cote_ps), (
        "les deux installateurs divergent sur %r :\n  bash : %r\n  ps1  : %r"
        % (drapeaux_bash, plan_pipx(cote_bash), plan_pipx(cote_ps))
    )


# ==========================================================================
#  Le raccourci hors du terminal -- story 8.8
# ==========================================================================
#
# Egan, 2026-09-07, note 2 sur la v2 de la planche de release, verbatim :
# « Essaye ... on verra bien si ca marche ». Un feu vert avec sa reserve.
#
# CE QUI EST MESURE ICI, ET CE QUI NE L'EST PAS. Le fichier `.desktop` est
# reellement ECRIT par le script, dans un `HOME` neuf, puis passe au validateur
# OFFICIEL `desktop-file-validate`. Le raccourci Windows, lui, n'est mesure que
# sur sa FORME : il n'y a pas de Windows ici pour le cliquer, et c'est
# exactement le sens de la reserve d'Egan.
#
# DEUX MESURES DU 2026-09-07 changent ce que ces frontieres doivent faire :
#
#   * `desktop-file-validate` rend EXIT=0 sur une erreur qu'il appelle
#     lui-meme « error: (will be fatal in the future) » -- une categorie
#     fautive passe. Une ligne franchement cassee, elle, rend 1. Le verdict se
#     lit donc sur la SORTIE, jamais sur le code de retour ;
#   * une entree SANS `Exec=` est declaree VALIDE, sortie vide. Le validateur
#     officiel ne reclame pas la seule cle qui fait demarrer quelque chose : un
#     raccourci qui ne lance rien le passerait. Le banc mesure donc la ligne
#     `Exec` lui-meme.

#: Les chemins qu'aucun des deux scripts n'a le droit de toucher. Frontiere
#: NEGATIVE a jetons NOMMES : un grep large sur « desktop » rougirait sur le
#: code juste, qui porte `[Desktop Entry]` et `mmu-tui.desktop`.
CHEMINS_INTERDITS_BASH = (
    "/usr/share/applications",
    "xdg-user-dir",
    "${HOME}/Desktop",
    "/Bureau",
)
#: L'ouverture du bloc d'ecriture du raccourci dans `install.sh`, mot pour mot.
#: Elle sert a SCOPER la cinquieme interdiction de l'AC8 -- « tout `sudo` sur le
#: chemin du raccourci » --, celle que la revue a laissee ouverte (`C3-6`).
#:
#: Elle ne pouvait pas rejoindre `CHEMINS_INTERDITS_BASH` : ce registre est un
#: grep GLOBAL, et `${SUDO}` sert LEGITIMEMENT ffmpeg et les paquets systeme
#: quelques centaines de lignes plus haut. Un jeton `sudo` ajoute la aurait
#: rougi sur du code juste -- exactement le piege que l'AC8 nomme elle-meme a
#: propos de `Desktop`.
OUVERTURE_DU_BLOC_RACCOURCI = (
    'if [ "${RACCOURCI_POSSIBLE}" -eq 1 ] && [ "${CHOIX_RACCOURCI}" -eq 1 ]; then'
)

CHEMINS_INTERDITS_PS = (
    "CommonPrograms",
    "CommonStartMenu",
    "CommonDesktopDirectory",
    "ALLUSERSPROFILE",
)

#: Le repertoire utilisateur du menu, tel qu'`install.sh` l'ECRIT -- pas tel
#: qu'on l'imaginerait. Le script respecte XDG et REJETTE un `XDG_DATA_HOME`
#: relatif (le spec le veut invalide), si bien que le chemin se construit en
#: deux temps : une racine validee par un `case`, puis `/applications`. La
#: sous-chaine `.local/share/applications` n'apparait donc nulle part.
#:
#: Deux rouges mesures ont deja porte sur ce jeton -- l'un a l'ecriture de la
#: story (il nommait `.local/share/applications`), l'autre a la revue quand le
#: `case` de validation a scinde l'expression. Il se relit dans le code,
#: jamais de memoire.
REPERTOIRE_MENU_BASH = "${RACINE_DONNEES}/applications"
DEFAUT_MENU_BASH = "${HOME}/.local/share"

#: Les cinq libelles du recapitulatif, mot pour mot. Ils doivent etre les MEMES
#: dans les deux scripts : la seule comparaison croisee qui existe
#: (`test_les_deux_scripts_produisent_le_MEME_plan`) ne porte que sur les lignes
#: `pipx `, donc une divergence de recapitulatif y est invisible.
LIBELLES_RACCOURCI = (
    "raccourci ....... oui, dans ",
    "raccourci ....... non",
    "raccourci ....... sans objet (ligne de commande seule)",
    "raccourci ....... sans objet (aucun affichage detecte)",
    "raccourci ....... sans objet (pas de raccourci terminal sur macOS)",
)

#: Le SIXIEME libelle, propre a `install.ps1`. Il existe parce que la revue a
#: mesure le contraire : `-not (Test-SurWindows)` couvre macOS ET Linux, si
#: bien que le script PowerShell annoncait « pas de raccourci terminal sur
#: macOS » en tournant sous pwsh 7 SUR LINUX. Et l'exigence d'identite MOT POUR
#: MOT tenait ce motif faux en place -- le corriger faisait rougir la parite.
LIBELLE_PS1_HORS_WINDOWS = (
    "raccourci ....... sans objet (hors Windows, passer par scripts/install.sh)")


def _maison_neuve(tmp_path, machine, *, avec_commande_tui: bool) -> dict:
    """Un `HOME` NEUF greffe sur une machine fabriquee, et pourquoi.

    Les fixtures de machine sont `scope="module"` : un test qui ecrit vraiment
    `~/.local/share/applications/mmu-tui.desktop` y laisserait le fichier, et
    le test « --dry-run n'ecrit rien » deviendrait vert ou rouge SELON L'ORDRE
    DE COLLECTE. C'est une flakiness d'ordre, le pire des rouges a diagnostiquer.

    `avec_commande_tui` fait varier le drapeau dont depend le repli de l'AC6 :
    sans `mmu-tui` nulle part, le script doit ALERTER et n'ecrire aucun fichier.
    Une garde qui ne ferait pas varier ce drapeau ne mesurerait qu'un chemin.
    """
    maison = tmp_path / "maison"
    (maison / ".local" / "bin").mkdir(parents=True)
    if avec_commande_tui:
        faux = maison / ".local" / "bin" / "mmu-tui"
        faux.write_text("#!/bin/sh\nexit 0\n")
        faux.chmod(0o755)
    env = dict(machine)
    env["HOME"] = str(maison)

    # Le PATH aussi est NEUF, et c'est le meme motif que le `HOME` -- decouvert
    # une seconde fois, a la revue, en payant exactement ce que ce docstring
    # annonce. Les fixtures de machine sont `scope="module"` : leur repertoire
    # de binaires est PARTAGE. Un test qui y depose un `uname` factice rendant
    # `Darwin`, ou un `mmu-tui` non executable, contamine TOUS les tests
    # suivants qui emploient la meme machine -- ordre de collecte compris. La
    # premiere redaction de ce lot l'a fait, et 36 tests ont rougi d'un coup.
    #
    # Les binaires sont donc COPIES, pas partages : chaque test peut deposer ce
    # que son regime demande sans que personne d'autre le voie.
    binaires_partages = Path(machine["PATH"].split(os.pathsep)[0])
    binaires = tmp_path / "binaires"
    binaires.mkdir()
    for outil in binaires_partages.iterdir():
        copie = binaires / outil.name
        copie.write_bytes(outil.read_bytes())
        copie.chmod(outil.stat().st_mode)
    env["PATH"] = str(binaires)
    return env


def _deposer_outil(binaires: Path, nom: str, contenu: str, mode: int = 0o755) -> Path:
    """Depose un outil factice dans une PATH fabriquee, sans suivre de lien.

    **Le piege que cette fonction ferme a ete paye pendant la revue de 8.8, et
    il a casse le conteneur.** La PATH fabriquee par `_fabriquer_machine` est
    faite de LIENS SYMBOLIQUES vers les vrais binaires du systeme
    (`(binaires / nom).symlink_to(chemin)`, l. 301). Un test qui y ecrit un
    `uname` factice par `write_text` ecrit donc **dans `/usr/bin/uname`** : la
    vraie commande du conteneur a ete remplacee, `uname -s` a rendu `Darwin`
    pendant vingt minutes, et 36 tests ont rougi -- `install.sh` se croyant sur
    un Mac. Il a fallu reinstaller `coreutils` pour la retablir.

    C'est litteralement le finding `C2-3` de cette meme revue, celui que le
    produit venait de fermer, reproduit dans l'outil de mesure quelques minutes
    plus tard. On retire donc le lien AVANT d'ecrire, toujours.
    """
    cible = binaires / nom
    if cible.is_symlink() or cible.exists():
        cible.unlink()
    cible.write_text(contenu)
    cible.chmod(mode)
    return cible


def _fichier_raccourci(env: dict) -> Path:
    """Le chemin que le SCRIPT emploie, jamais celui qu'on lui prete.

    Coder `HOME/.local/share` en dur rendait cette fonction fausse des que
    `XDG_DATA_HOME` etait pose -- et une assertion `not ...exists()` portant
    sur un chemin ou le script n'ecrit pas est verte sans rien mesurer. C'est
    la moitie « faux vert » du defaut que `_fabriquer_machine` ferme par
    ailleurs ; les deux se posent ensemble, l'une sans l'autre laisserait le
    regime a moitie ouvert.
    """
    racine = env.get("XDG_DATA_HOME", "")
    if not racine.startswith("/"):
        # Un `XDG_DATA_HOME` RELATIF est invalide au sens du spec, et le script
        # retombe alors sur le defaut : le banc suit la meme regle.
        racine = str(Path(env["HOME"]) / ".local" / "share")
    return Path(racine) / "applications" / "mmu-tui.desktop"


def test_le_raccourci_ecrit_passe_le_validateur_OFFICIEL(tmp_path, machine_avec_affichage):
    """AC5 -- et le verdict se lit sur la SORTIE, jamais sur le code de retour.

    Le seul test de ce fichier qui joue une installation REELLE (sans
    `--dry-run`) : le validateur ne peut rien dire d'un fichier qui n'existe
    pas. Elle reste inoffensive parce que `pipx` est factice et que le `HOME`
    est jetable.
    """
    validateur = shutil.which("desktop-file-validate")
    if not validateur:
        pytest.skip("desktop-file-validate absent : le verdict serait invente")

    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=True)
    _, sortie = jouer_sans_terminal(["--sans-path", "--sans-verification"], env)
    cible = _fichier_raccourci(env)
    assert cible.exists(), "aucun raccourci ecrit :\n%s" % sortie

    acheve = subprocess.run([validateur, str(cible)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=DELAI)
    verdict = acheve.stdout.decode("utf-8", "replace").strip()
    # LES DEUX, et la sortie d'abord : `desktop-file-validate` rend 0 sur une
    # erreur qu'il annonce lui-meme comme bientot fatale (mesure du 2026-09-07,
    # `Categories=Graphics;Video;Utility;`). Un test qui ne lirait que `$?`
    # laisserait passer exactement ce cas-la.
    assert verdict == "", "le validateur a quelque chose a dire :\n%s" % verdict
    assert acheve.returncode == 0, verdict


def test_la_ligne_Exec_du_raccourci_est_un_chemin_ABSOLU(tmp_path, machine_avec_affichage):
    """AC6 -- et le banc la mesure LUI-MEME, parce que le validateur ne le fait pas.

    Mesure du 2026-09-07 : une entree `.desktop` SANS `Exec=` est declaree
    valide, sortie vide, exit 0. Le validateur officiel ne reclame pas la seule
    cle qui fait demarrer quelque chose.

    Le chemin doit etre absolu : la ligne que `pipx ensurepath` ecrit dans le
    profil n'est lue que par un SHELL, et une session graphique lancee par le
    gestionnaire de connexion ne la voit pas.
    """
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=True)
    jouer_sans_terminal(["--sans-path", "--sans-verification"], env)
    lignes = _fichier_raccourci(env).read_text().splitlines()

    execs = [l for l in lignes if l.startswith("Exec=")]
    assert len(execs) == 1, "une ligne Exec et une seule : %r" % execs
    brut = execs[0][len("Exec="):]

    # LA CITATION, et le validateur officiel ne la reclame pas -- mesure de la
    # revue (`C1-6` / `C2-7`) : un `Exec=` non cite portant un chemin a espace
    # passe `desktop-file-validate` avec exit 0 et sortie VIDE, et n'est lance
    # par aucun bureau. Seul `gio launch` le voyait. La forme citee passe le
    # validateur aussi : elle est donc toujours prise, pour qu'un seul chemin
    # de code existe et soit mesure.
    assert brut.startswith('"') and brut.endswith('"'), (
        "Exec doit etre cite, sans quoi un chemin a espace produit une entree "
        "que le validateur accepte et qu'aucun bureau ne lance : %r" % brut)
    cible = brut[1:-1]
    assert cible.startswith("/"), "Exec n'est pas absolu : %r" % cible
    assert cible.endswith("/mmu-tui"), "Exec ne nomme pas la commande : %r" % cible
    assert os.access(cible, os.X_OK), "Exec pointe vers un fichier non executable : %r" % cible

    # Une seule categorie principale (mesure du 2026-09-07 : trois rendent un
    # « hint » sur la duplication dans le menu), et le terminal reste ouvert --
    # sans quoi une application Textual n'a nulle part ou s'afficher.
    assert "Terminal=true" in lignes
    categories = [l for l in lignes if l.startswith("Categories=")]
    assert len(categories) == 1, categories
    assert categories[0].rstrip(";").count(";") == 0, (
        "plus d'une categorie : %r" % categories[0])


def test_SANS_la_commande_le_raccourci_ALERTE_au_lieu_d_ecrire(tmp_path, machine_avec_affichage):
    """AC6, l'autre sens du drapeau -- jamais un fichier mort, jamais un silence.

    C'est le symetrique exige par la regle « une garde qui ne fait varier AUCUN
    de ses drapeaux ne mesure qu'un seul chemin ». Un raccourci qui pointe vers
    rien est PIRE que pas de raccourci : il echoue chez l'utilisateur, longtemps
    apres, sans rien dire de pourquoi.
    """
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=False)
    _, sortie = jouer_sans_terminal(["--sans-path", "--sans-verification"], env)
    assert not _fichier_raccourci(env).exists(), (
        "un raccourci a ete ecrit alors que mmu-tui est introuvable")
    assert "Raccourci non pose" in sans_ansi(sortie), sortie


def test_la_SIMULATION_annonce_le_raccourci_sans_l_ecrire(tmp_path, machine_avec_affichage):
    """AC9 -- un plan qui pose un fichier n'est plus un plan."""
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=True)
    _, sortie = jouer_sans_terminal(["--dry-run"], env)
    sortie = sans_ansi(sortie)
    assert "[simulation] ecrire" in sortie, sortie
    assert not _fichier_raccourci(env).exists(), (
        "--dry-run a ecrit un fichier :\n%s" % sortie)


def test_desinstaller_retire_AUSSI_le_raccourci(tmp_path, machine_avec_affichage):
    """AC2 -- `EPIC11-ARB-89` : tout objet pose par l'outil doit pouvoir partir.

    Et le retrait est joue DANS LES DEUX SENS : le fichier present part et est
    nomme, le fichier absent ne fait pas echouer le desinstalleur. Un
    desinstalleur qui echoue parce qu'il n'y avait rien a desinstaller est un
    blocage sec pour rien.
    """
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=True)
    jouer_sans_terminal(["--sans-path", "--sans-verification"], env)
    cible = _fichier_raccourci(env)
    assert cible.exists(), "rien a retirer : la mise en place a echoue"

    _, sortie = jouer_sans_terminal(["--desinstaller"], env)
    sortie = sans_ansi(sortie)
    assert not cible.exists(), "le raccourci a survecu au desinstalleur :\n%s" % sortie
    # L'annonce le NOMME, avec son chemin : sinon un fichier disparait du menu
    # de quelqu'un sans qu'on le lui ait dit.
    assert str(cible) in sortie, sortie
    assert "Termine" in sortie, sortie

    _, encore = jouer_sans_terminal(["--desinstaller"], env)
    encore = sans_ansi(encore)
    assert "rien a y retirer" in encore, encore
    assert "Termine" in encore, encore


def test_la_question_du_raccourci_ne_se_pose_PAS_la_ou_elle_ne_change_rien(
        machine_avec_affichage, machine_vierge):
    """AC1 -- les deux sens de chacune des deux conditions.

    `machine_vierge` n'a PAS d'affichage, `machine_avec_affichage` en a : c'est
    le meme drapeau joue dans les deux sens, et non deux fois le meme cas.
    """
    intitule = "Ajouter un raccourci"

    avec = sans_ansi(jouer_le_dialogue(["--dry-run"], ENTREE_SEULE, machine_avec_affichage))
    assert intitule in avec, "avec affichage et TUI, la question doit se poser :\n%s" % avec

    _, cli = jouer_sans_terminal(["--dry-run", "--cli"], machine_avec_affichage)
    cli = sans_ansi(cli)
    assert intitule not in cli, "un raccourci vers une ligne de commande n'a pas de sens :\n%s" % cli
    assert "sans objet (ligne de commande seule)" in cli, cli

    _, sans_ecran = jouer_sans_terminal(["--dry-run"], machine_vierge)
    sans_ecran = sans_ansi(sans_ecran)
    assert intitule not in sans_ecran, (
        "sans affichage, ce serait proposer une entree dans un menu qui n'existe pas :\n%s"
        % sans_ecran)
    assert "sans objet (aucun affichage detecte)" in sans_ecran, sans_ecran


def test_aucun_chemin_SYSTEME_dans_les_deux_scripts():
    """AC8 -- frontiere NEGATIVE a jetons nommes, ET son pendant positif.

    Aucun test positif ne verrait revenir un `sudo cp` vers
    `/usr/share/applications`. Mais une frontiere negative seule serait verte
    AVANT que la story n'ecrive une ligne -- verte pour la pire des raisons.
    D'ou le cardinal epingle qui l'accompagne : le chemin utilisateur apparait
    une fois, et une seule, dans chaque script.
    """
    bash = code_du_script(INSTALL_SH)
    ps = code_du_script(INSTALL_PS1)

    for jeton in CHEMINS_INTERDITS_BASH:
        assert jeton not in bash, (
            "install.sh touche a un chemin qui n'est pas le sien : %r" % jeton)
    for jeton in CHEMINS_INTERDITS_PS:
        assert jeton not in ps, (
            "install.ps1 touche a un chemin qui n'est pas le sien : %r" % jeton)

    # Le litteral est celui du code, pas celui qu'on aurait ecrit : install.sh
    # respecte XDG, donc `${XDG_DATA_HOME:-${HOME}/.local/share}/applications`
    # -- la sous-chaine `.local/share/applications` n'y figure JAMAIS, l'accolade
    # fermante separant les deux moities. Une premiere redaction de ce test
    # l'attendait et rougissait sur un code correct.
    assert bash.count(REPERTOIRE_MENU_BASH) == 1, (
        "le repertoire utilisateur du menu doit etre nomme une fois et une seule ;"
        " s'il vient de changer, c'est ce jeton-ci qu'il faut reprendre")
    assert bash.count(DEFAUT_MENU_BASH) == 1, (
        "le defaut XDG doit etre nomme une fois et une seule")
    assert ps.count("GetFolderPath('Programs')") == 1, (
        "le menu Demarrer utilisateur doit etre nomme une fois et une seule")


def bloc_du_raccourci(code: str) -> list:
    """Les lignes du bloc d'ecriture du raccourci, son `fi` compris.

    Le bloc se ferme sur le PREMIER `fi` en colonne zero. C'est le seul repere
    qui ne depende pas de ce que le bloc CONTIENT -- `code_du_script` conserve
    l'indentation, elle ne retire que les lignes de commentaire pur.

    Le decoupage echoue bruyamment plutot que de rendre un bloc vide : une
    frontiere qui ne trouve plus son perimetre serait verte pour la pire des
    raisons.
    """
    lignes = code.splitlines()
    debuts = [i for i, l in enumerate(lignes)
              if l.strip() == OUVERTURE_DU_BLOC_RACCOURCI]
    assert len(debuts) == 1, (
        "le bloc d'ecriture du raccourci ne s'ouvre plus comme ce banc "
        "l'attend (%d occurrence(s)) : c'est le DECOUPAGE qu'il faut reprendre "
        "ici, pas la mesure qu'il porte." % len(debuts))
    for fin in range(debuts[0] + 1, len(lignes)):
        if lignes[fin] == "fi":
            return lignes[debuts[0]:fin + 1]
    raise AssertionError(
        "le bloc d'ecriture du raccourci ne se referme jamais en colonne zero")


def test_AUCUN_sudo_dans_le_BLOC_d_ecriture_du_raccourci():
    """AC8, sa CINQUIEME interdiction -- finding `C3-6`, ferme ici.

    Ce que l'elevation couterait, et c'est pourquoi l'interdit est nomme : le
    raccourci vit sous `${HOME}`. Un `sudo` y ecrirait un fichier appartenant a
    root -- que l'utilisateur ne peut plus retirer, et que `--desinstaller`
    echouerait a supprimer sans un mot, puisque le retrait, lui, n'est pas
    eleve. Le raccourci serait pose pour le compte root plutot que pour le sien.

    La mesure porte sur le BLOC et non sur le fichier : c'est tout ce qui
    separait cette interdiction des quatre autres, et c'est ce qui manquait.
    """
    bloc = bloc_du_raccourci(code_du_script(INSTALL_SH))
    assert len(bloc) > 20, (
        "le bloc d'ecriture du raccourci rendu fait %d lignes : trop court "
        "pour etre celui qu'on croit mesurer" % len(bloc))
    fautives = [l.strip() for l in bloc if "sudo" in l.lower()]
    assert fautives == [], (
        "une elevation de droits est apparue dans le bloc du raccourci, qui "
        "ecrit sous ${HOME} : %r" % (fautives,))


def test_AUCUNE_ligne_nommant_le_chemin_du_raccourci_n_eleve_les_droits():
    """Le volet qui suit la VARIABLE plutot que le bloc.

    Le chemin du raccourci est aussi nomme HORS du bloc d'ecriture : au retrait
    (`--desinstaller`), a la question 4 et au recapitulatif. Un `sudo` pose a
    l'un de ces trois endroits serait invisible au test ci-dessus, qui ne
    regarde qu'un bloc -- et le plus dangereux des trois est justement le
    retrait, ou une elevation effacerait un fichier qu'on n'a pas ecrit.
    """
    lignes = [l for l in code_du_script(INSTALL_SH).splitlines()
              if "RACCOURCI_DOSSIER" in l or "RACCOURCI_FICHIER" in l]
    assert len(lignes) >= 5, (
        "seules %d lignes nomment le chemin du raccourci : le perimetre de "
        "cette frontiere a fondu, elle ne mesure plus grand-chose" % len(lignes))
    fautives = [l.strip() for l in lignes if "sudo" in l.lower()]
    assert fautives == [], (
        "une ligne touchant au chemin du raccourci eleve les droits : %r"
        % (fautives,))


def test_les_deux_scripts_emploient_les_MEMES_libelles_de_raccourci():
    """AC4 -- une divergence de recapitulatif est invisible autrement.

    `test_les_deux_scripts_produisent_le_MEME_plan` ne compare que les lignes
    `pipx ` : le recapitulatif n'y entre pas. Les cinq libelles sont donc
    compares ici, litteral par litteral, dans les deux fichiers.
    """
    # `code_du_script`, PAS `read_text` : mesure de la revue (`C1-4` / `C3-3`)
    # -- ce test lisait le fichier BRUT, contrairement a ses deux voisines. Un
    # libelle DEPLACE dans un commentaire le laissait vert, alors qu'il est le
    # seul garant de la parite des recapitulatifs. Le mutant qui EFFACAIT le
    # litteral mourait ; celui qui le deplacait vivait.
    bash = code_du_script(INSTALL_SH)
    ps = code_du_script(INSTALL_PS1)
    for libelle in LIBELLES_RACCOURCI:
        assert libelle in bash, "libelle absent du CODE d'install.sh : %r" % libelle
        assert libelle in ps, "libelle absent du CODE d'install.ps1 : %r" % libelle
    # Le SIXIEME libelle est propre a `install.ps1` et doit le rester : il dit
    # a qui joue le script PowerShell sous Linux d'employer `install.sh`. Le
    # porter dans `install.sh` serait un contresens.
    assert LIBELLE_PS1_HORS_WINDOWS in ps, (
        "install.ps1 doit nommer le cas « hors Windows » : %r" % LIBELLE_PS1_HORS_WINDOWS)
    assert LIBELLE_PS1_HORS_WINDOWS not in bash, (
        "ce libelle n'a aucun sens dans install.sh : %r" % LIBELLE_PS1_HORS_WINDOWS)


def test_le_garde_powershell_du_raccourci_n_est_PAS_l_affichage():
    """AC1 -- macOS reste dehors, et c'est ce qui l'y garde.

    `Test-AffichageDisponible` rend VRAI sur macOS (`$IsMacOS`). Un garde
    transpose litteralement de bash (`TUI && affichage`) poserait donc la
    question sous `pwsh` sur un Mac, ou cette story ne fait rien.

    Second defaut mesure et ferme ici : en PowerShell, `Test-SurWindows -and $x`
    passe `-and` comme PARAMETRE positionnel a la fonction, qui l'ignore. La
    condition se reduit alors silencieusement a `Test-SurWindows` seul -- aucune
    erreur, aucun message. Les parentheses ne sont donc pas cosmetiques.
    """
    ps = code_du_script(INSTALL_PS1)
    ligne = [l for l in ps.splitlines() if "$RaccourciPossible =" in l]
    assert len(ligne) == 1, ligne
    garde = ligne[0]
    assert "(Test-SurWindows)" in garde, (
        "sans parentheses, `-and` devient un parametre et le reste de la "
        "condition disparait en silence : %r" % garde)
    assert "Affichage" not in garde, (
        "Test-AffichageDisponible rend vrai sur macOS : %r" % garde)
    # `C2-8` : le mutant qui retirait le test des composants survivait. Sur
    # Windows, `-Cli` aurait alors pose un raccourci vers un `mmu-tui` jamais
    # installe.
    assert "$ChoixComposants" in garde, (
        "sans le test des composants, -Cli poserait un raccourci vers une "
        "interface non installee : %r" % garde)


# ====================================================== revue 8.8, triage
#  Les frontieres nees des NEUF mutants survivants de la revue en trois
#  couches. Chacune porte, a sa ligne, le finding qu'elle ferme.
#
#  Ce que ce lot apprend, et il vaut plus que les tests eux-memes : la campagne
#  de l'implementation avait rendu « 11 mutants, 0 survivant ». C'etait vrai, et
#  ca ne mesurait que la SOLIDITE des onze frontieres deja ecrites -- jamais
#  l'ETENDUE de ce qu'elles couvrent. Les onze mutations visaient exactement les
#  onze chemins deja assertes. Un score de mutation ne dit rien de ce que
#  personne n'a pense a asserter.
# ==========================================================================


def _sortie_reelle(env, *arguments):
    """Une installation REELLE (sans `--dry-run`), sa sortie nettoyee."""
    _, sortie = jouer_sans_terminal(["--sans-path", "--sans-verification", *arguments], env)
    return sans_ansi(sortie)


def test_la_reponse_NON_au_raccourci_est_REELLEMENT_respectee(tmp_path, machine_avec_affichage):
    """`C1-2` / `C2-1` / `C3-1` -- les quatre drapeaux n'etaient joues par RIEN.

    Un `grep` de `--sans-raccourci` dans ce banc rendait ZERO. Deux mutants
    survivaient : `--sans-raccourci` posant le raccourci, et la garde
    d'ecriture ne consultant plus la reponse. Autrement dit l'utilisateur qui
    REFUSE l'obtenait quand meme, banc vert -- l'exact contraire de ce que la
    story existe pour offrir.

    C'est la regle du depot « une garde qui ne fait varier AUCUN de ses
    drapeaux » : `CHOIX_RACCOURCI` est lu a deux endroits et un seul cote etait
    joue.
    """
    non = _maison_neuve(tmp_path / "non", machine_avec_affichage, avec_commande_tui=True)
    sortie = _sortie_reelle(non, "--sans-raccourci")
    assert not _fichier_raccourci(non).exists(), (
        "l'utilisateur a REFUSE le raccourci et il a ete pose :\n%s" % sortie)
    assert "raccourci ....... non" in sortie, sortie

    oui = _maison_neuve(tmp_path / "oui", machine_avec_affichage, avec_commande_tui=True)
    sortie = _sortie_reelle(oui, "--raccourci")
    assert _fichier_raccourci(oui).exists(), (
        "l'utilisateur a DEMANDE le raccourci et il n'a pas ete pose :\n%s" % sortie)
    assert "raccourci ....... oui, dans " in sortie, sortie


def test_le_recapitulatif_du_raccourci_dit_CE_QUI_EST_ECRIT(tmp_path, machine_avec_affichage):
    """`C3-3` -- le recapitulatif pouvait mentir sur la seule ligne non mesuree.

    Un mutant inversant la branche du recapitulatif annoncait « oui, dans ... »
    sans rien ecrire, et « non » en ecrivant -- 61 tests verts. C'est la faute
    precise que `test_le_recapitulatif_dit_la_meme_chose_que_le_plan` existe
    pour attraper, sur la ligne qu'il ne regarde pas.

    La frontiere croise donc les DEUX : ce que le recapitulatif annonce, et ce
    que le disque porte.
    """
    for drapeau, attendu, doit_exister in (("--raccourci", "raccourci ....... oui, dans ", True),
                                           ("--sans-raccourci", "raccourci ....... non", False)):
        env = _maison_neuve(tmp_path / drapeau.strip("-"), machine_avec_affichage,
                            avec_commande_tui=True)
        sortie = _sortie_reelle(env, drapeau)
        assert attendu in sortie, "%s : %s" % (drapeau, sortie)
        assert _fichier_raccourci(env).exists() is doit_exister, (
            "%s : le recapitulatif et le disque se contredisent :\n%s" % (drapeau, sortie))


def test_la_garde_d_ECRITURE_est_celle_du_RECAPITULATIF(tmp_path, machine_vierge,
                                                        machine_avec_affichage):
    """`C1-3` / `C2-1` -- seule la garde de la QUESTION etait mesuree.

    `test_la_question_du_raccourci_ne_se_pose_PAS_la_ou_elle_ne_change_rien`
    verifie l'absence de l'intitule et la presence du libelle « sans objet ».
    Il ne regarde ni le disque, ni l'annonce de simulation. Un mutant retirant
    `RACCOURCI_POSSIBLE` de la garde d'ECRITURE posait donc le fichier pendant
    que le recapitulatif disait « sans objet », et rien ne bougeait.
    """
    sans_ecran = _maison_neuve(tmp_path / "sans-ecran", machine_vierge, avec_commande_tui=True)
    sortie = _sortie_reelle(sans_ecran, "--raccourci")
    assert not _fichier_raccourci(sans_ecran).exists(), (
        "un raccourci a ete pose sans affichage :\n%s" % sortie)
    assert "sans objet (aucun affichage detecte)" in sortie, sortie

    cli = _maison_neuve(tmp_path / "cli", machine_avec_affichage, avec_commande_tui=True)
    sortie = _sortie_reelle(cli, "--cli", "--raccourci")
    assert not _fichier_raccourci(cli).exists(), (
        "un raccourci vers la TUI a ete pose alors qu'elle n'est pas installee :\n%s" % sortie)
    assert "sans objet (ligne de commande seule)" in sortie, sortie


def test_un_ECHEC_d_ecriture_du_raccourci_NE_TUE_PAS_l_installation(tmp_path,
                                                                    machine_avec_affichage):
    """`C1-1` / `C2-2` -- le defaut le plus cher de cette revue.

    `mkdir` et la redirection etaient nus sous `set -euo pipefail`. Un
    `~/.local/share` inutilisable tuait le script APRES la pose des paquets :
    pas de `pipx ensurepath`, pas de bilan, pas un mot. L'utilisateur repartait
    avec des commandes introuvables et aucune explication.

    Le jumeau PowerShell faisait deja ce qu'il faut (`try/catch` + « Raccourci
    non pose ... L'installation continue »). Le cote qui suivait la doctrine
    etait celui qui n'etait pas mesure.
    """
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=True)
    # `~/.local/share` est un FICHIER ordinaire : `mkdir -p` ne peut pas passer.
    partage = Path(env["HOME"]) / ".local" / "share"
    partage.parent.mkdir(parents=True, exist_ok=True)
    partage.write_text("je ne suis pas un repertoire\n")

    acheve, brut = jouer_sans_terminal(["--sans-verification", "--raccourci"], env)
    sortie = sans_ansi(brut)
    assert acheve == 0, "l'installateur est mort sur un raccourci impossible :\n%s" % sortie
    assert "Raccourci non pose" in sortie, sortie
    assert "L'installation continue" in sortie, sortie
    # Ce qui suit le raccourci doit avoir eu lieu : c'est tout l'enjeu.
    assert "Termine" in sortie, sortie


def test_le_raccourci_ne_SUIT_PAS_un_lien_symbolique(tmp_path, machine_avec_affichage):
    """`C2-3` -- la destruction que seule la couche 2 a atteinte.

    `> fichier` ecrit dans la CIBLE d'un lien. Un utilisateur dont le raccourci
    est un lien vers ses dotfiles voyait le fichier vise ecrase, puis
    `--desinstaller` retirait le lien en laissant derriere lui son fichier
    detruit et orphelin.

    Le voisin immediat dans le meme script fait l'inverse : le profil du shell
    est COPIE avant d'etre touche. Cette frontiere aligne le raccourci dessus.
    """
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=True)
    cible = _fichier_raccourci(env)
    cible.parent.mkdir(parents=True, exist_ok=True)
    ailleurs = Path(env["HOME"]) / "dotfiles" / "mon-lanceur.desktop"
    ailleurs.parent.mkdir(parents=True, exist_ok=True)
    ailleurs.write_text("[Desktop Entry]\nName=MON LANCEUR A MOI\n")
    cible.symlink_to(ailleurs)

    _sortie_reelle(env, "--raccourci")
    assert "MON LANCEUR A MOI" in ailleurs.read_text(), (
        "le fichier VISE par le lien a ete ecrase : c'est le fichier de "
        "l'utilisateur, pas le notre")
    assert not cible.is_symlink(), "le lien aurait du etre remplace par notre fichier"


def test_la_REINSTALLATION_DIT_qu_elle_remplace(tmp_path, machine_avec_affichage):
    """`C2-3` / `C3-5` -- `EPIC11-ARB-89` veut une ecriture destructive CONSCIENTE.

    Verbatim : « la rigueur de l'outil ne doit pas empecher une ecriture
    destructive CONSCIENTE (apres avertissement) ». L'ecrasement lui-meme est
    conforme -- un raccourci n'est aucun des cinq objets versionnables
    d'`EPIC11-ARB-104` --, mais il se faisait sous un message IDENTIQUE a celui
    d'une premiere pose. Un `.desktop` edite a la main disparaissait sans un mot.

    Et la table d'arbitrages de la story annoncait cette moitie « mesuree par
    AC2 » alors qu'aucun test ne jouait deux installations.
    """
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=True)
    premiere = _sortie_reelle(env, "--raccourci")
    assert "Raccourci pose" in premiere, premiere
    assert "REMPLACE" not in premiere, premiere

    seconde = _sortie_reelle(env, "--raccourci")
    assert "Raccourci REMPLACE" in seconde, (
        "une reinstallation ecrase le fichier sans le dire :\n%s" % seconde)


def test_une_commande_NON_EXECUTABLE_sur_le_PATH_ne_pose_pas_de_raccourci(tmp_path,
                                                                          machine_avec_affichage):
    """`C2-5` -- `command -v` n'est pas un test de validite.

    Mesure de la couche 2, refaite en root ET sous uid 1000 : `command -v` de
    bash rend un fichier present sur le PATH meme SANS bit d'execution. Le
    repli testait `-x`, la branche nominale ne testait rien -- le seul chemin
    non garde etait celui qui sert le plus souvent, et il ecrivait le « fichier
    mort » que le commentaire du code dit exister pour eviter.
    """
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=False)
    binaires = Path(env["PATH"].split(os.pathsep)[0])
    # present, trouvable, NON executable
    _deposer_outil(binaires, "mmu-tui", "#!/bin/sh\nexit 0\n", mode=0o644)

    sortie = _sortie_reelle(env, "--raccourci")
    assert not _fichier_raccourci(env).exists(), (
        "un raccourci a ete pose vers un fichier non executable :\n%s" % sortie)
    assert "Raccourci non pose" in sortie, sortie


def test_un_XDG_DATA_HOME_RELATIF_retombe_sur_le_DEFAUT(tmp_path, machine_avec_affichage):
    """`C2-10` -- un objet pose qu'on ne peut plus retirer.

    Le spec XDG dit qu'un chemin relatif doit etre tenu pour INVALIDE et le
    defaut employe. Sans ce test, `XDG_DATA_HOME=donnees-relatives` ecrivait le
    raccourci dans le repertoire COURANT de l'appelant -- hors de tout menu, et
    introuvable par un `--desinstaller` lance d'ailleurs. C'est exactement ce
    qu'`EPIC11-ARB-89` interdit.
    """
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=True)
    env["XDG_DATA_HOME"] = "donnees-relatives"
    # Le repertoire courant est JETABLE : un chemin relatif se resout contre
    # lui, et celui du banc est la racine du depot. Mesure pendant la campagne
    # de mutation -- le mutant qui accepte un XDG relatif a fait ecrire dans le
    # depot, et le crochet de fin de tour l'a trouve.
    courant = tmp_path / "repertoire-courant"
    courant.mkdir()
    _, brut = jouer_sans_terminal(
        ["--sans-path", "--sans-verification", "--raccourci"], env, cwd=courant)
    sortie = sans_ansi(brut)

    par_defaut = Path(env["HOME"]) / ".local" / "share" / "applications" / "mmu-tui.desktop"
    assert par_defaut.exists(), (
        "un XDG_DATA_HOME relatif doit etre ignore, pas suivi :\n%s" % sortie)
    egare = courant / "donnees-relatives"
    assert not egare.exists(), (
        "un chemin relatif a ete suivi : le raccourci est tombe dans le "
        "repertoire courant de l'appelant, ou aucun desinstalleur ne le "
        "retrouvera (%s)" % egare)


def test_desinstaller_en_SIMULATION_n_affirme_AUCUN_retrait(tmp_path, machine_avec_affichage):
    """`C1-7` / `C2-6` -- un `succes` affirme une action PASSEE.

    `executer rm -f` respectait bien la simulation ; le `succes` qui le suivait
    etait inconditionnel. Le mode dont l'unique raison d'etre est de dire ce qui
    *arriverait* affirmait ce qui *etait arrive*, sur un fichier toujours la.
    Le jumeau PowerShell distinguait deja correctement.
    """
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=True)
    _sortie_reelle(env, "--raccourci")
    cible = _fichier_raccourci(env)
    assert cible.exists(), "la mise en place a echoue"

    _, brut = jouer_sans_terminal(["--desinstaller", "--dry-run"], env)
    sortie = sans_ansi(brut)
    assert cible.exists(), "un --dry-run a retire le fichier :\n%s" % sortie
    assert "[simulation] rm -f" in sortie, sortie
    assert "Raccourci retire" not in sortie, (
        "la simulation affirme un retrait qui n'a pas eu lieu :\n%s" % sortie)


def test_la_branche_macOS_du_recapitulatif_est_REELLEMENT_jouee(tmp_path,
                                                                machine_avec_affichage):
    """`C2-9` -- une branche grepee comme litteral n'est pas une branche mesuree.

    Un mutant rendant la condition macOS inatteignable
    (`[ "${SYSTEME}" != "linux" ]` -> `[ "${SYSTEME}" = "__jamais__" ]`)
    survivait aux 61 frontieres : un vrai macOS aurait alors annonce « aucun
    affichage detecte », motif FAUX puisque Quartz est toujours la -- ce que le
    commentaire du code dit lui-meme.

    Or la branche EST jouable ici : un `uname` factice suffit. Le banc n'en
    truquait aucun, et sa section « ce qu'il ne mesure pas » declarait Windows,
    pas macOS.
    """
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=True)
    binaires = Path(env["PATH"].split(os.pathsep)[0])
    _deposer_outil(binaires, "uname",
                   "#!/bin/sh\n"
                   "# `uname` factice : ce banc tourne sous Linux, la branche macOS\n"
                   "# du script ne serait jamais atteinte autrement.\n"
                   "echo Darwin\n")

    _, brut = jouer_sans_terminal(["--dry-run"], env)
    sortie = sans_ansi(brut)
    assert "sans objet (pas de raccourci terminal sur macOS)" in sortie, (
        "la branche macOS n'a pas ete atteinte :\n%s" % sortie)
    assert "aucun affichage detecte" not in sortie, (
        "macOS a toujours un affichage : ce motif y serait faux :\n%s" % sortie)
    assert "Ajouter un raccourci" not in sortie, (
        "la question ne doit pas se poser sur macOS :\n%s" % sortie)


@pytest.mark.skipif(PWSH is None, reason="pwsh absent de cette machine")
def test_install_ps1_n_annonce_PAS_macOS_quand_il_tourne_sous_LINUX(machine_vierge):
    """`C3-4` / `C1-8` / `C2-9` -- le motif faux, sur la machine qui le joue.

    `-not (Test-SurWindows)` couvre macOS ET Linux. `install.ps1` sait tourner
    hors Windows -- il porte une branche « Hors Windows : le PATH se nettoie par
    scripts/install.sh --desinstaller » -- et il annoncait pourtant « pas de
    raccourci terminal sur macOS » sous pwsh 7 sur Linux.

    C'est precisement le motif faux que le cinquieme libelle avait ete cree pour
    eviter, et c'est la frontiere de parite qui le tenait en place.
    """
    acheve = subprocess.run(
        [PWSH, "-NoProfile", "-Command",
         "& ([scriptblock]::Create((Get-Content '%s' -Raw))) -DryRun -Tui" % INSTALL_PS1],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True, timeout=DELAI, env=dict(machine_vierge),
    )
    sortie = sans_ansi(acheve.stdout.decode("utf-8", "replace"))
    assert acheve.returncode == 0, sortie
    assert "pas de raccourci terminal sur macOS" not in sortie, (
        "install.ps1 annonce macOS alors qu'il tourne sous Linux :\n%s" % sortie)
    assert LIBELLE_PS1_HORS_WINDOWS in sortie, sortie


def test_la_machine_fabriquee_NEUTRALISE_xdg_data_home(tmp_path, monkeypatch):
    """`C1-5` / `C2-4` / `C3-2` -- la frontiere qui garde le banc lui-meme.

    Les trois couches de la revue ont trouve independamment que
    `_fabriquer_machine` laissait passer `XDG_DATA_HOME`. Comme `install.sh`
    respecte XDG, le `HOME` jetable ne protegeait alors RIEN : le banc ecrivait
    un vrai `mmu-tui.desktop` dans le menu d'applications de qui joue la suite,
    en ECRASANT ce qui s'y trouvait -- la couche 1 l'a mesure en perdant son
    propre fichier temoin --, et le desinstalleur y `rm -f` la meme cible.

    Ce n'est pas une frontiere sur le produit mais sur l'OUTIL DE MESURE, et
    elle est ici parce qu'aucune des autres ne peut la porter : les tests du
    raccourci restaient VERTS dans ce regime, en assertant l'absence d'un
    fichier a un chemin ou le script n'ecrivait plus. Verts en ne voyant rien.
    """
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/ce-chemin-ne-doit-pas-traverser")
    env = _fabriquer_machine(tmp_path, avec_ffmpeg=True, liste_pipx="",
                             avec_affichage=True)
    assert "XDG_DATA_HOME" not in env, (
        "XDG_DATA_HOME traverse : le banc ecrirait dans le menu "
        "d'applications REEL de qui joue la suite")
    # Et le corollaire, sur le calcul du chemin attendu : les deux moities du
    # correctif se posent ensemble.
    env["HOME"] = str(tmp_path / "maison")
    attendu = Path(env["HOME"]) / ".local" / "share" / "applications" / "mmu-tui.desktop"
    assert _fichier_raccourci(env) == attendu, _fichier_raccourci(env)


def test_chaque_maison_neuve_a_sa_PROPRE_path(tmp_path, machine_avec_affichage):
    """La seconde moitie de la lecon du 2026-09-07, et elle se mesure a part.

    Les fixtures de machine sont `scope="module"` : leur repertoire de binaires
    est PARTAGE. Un test qui y depose un outil factice -- un `uname` rendant
    `Darwin`, un `mmu-tui` non executable -- contamine tous les tests suivants
    qui emploient la meme machine.

    Cette frontiere est ecrite APRES avoir mesure que la regression ne se voit
    PAS par le banc joue dans l'ordre du fichier : les tests qui deposent un
    outil sont en fin de fichier, et leurs victimes potentielles sont avant.
    Elle ne se verrait qu'a certains tirages de `pytest-randomly` -- c'est-a-dire
    au pire moment, et pas chez celui qui a introduit le defaut. Un mutant qui
    rend la PATH partagee laisse le banc VERT dans l'ordre du fichier ; il meurt
    ici.
    """
    a = _maison_neuve(tmp_path / "a", machine_avec_affichage, avec_commande_tui=True)
    b = _maison_neuve(tmp_path / "b", machine_avec_affichage, avec_commande_tui=True)
    partagee = machine_avec_affichage["PATH"].split(os.pathsep)[0]
    for nom, env in (("a", a), ("b", b)):
        propre = env["PATH"].split(os.pathsep)[0]
        assert propre != partagee, (
            "%s partage le repertoire de binaires de la fixture : y deposer un "
            "outil factice contaminerait les autres tests" % nom)
    assert a["PATH"] != b["PATH"], "deux maisons neuves partagent leur PATH"

    # Et la copie est REELLE, pas un lien : `_deposer_outil` retire le lien
    # avant d'ecrire, mais un `write_text` naif ailleurs ne le ferait pas -- et
    # la cible serait le vrai binaire du systeme.
    outil = Path(a["PATH"].split(os.pathsep)[0]) / "uname"
    assert outil.exists() and not outil.is_symlink(), (
        "les binaires de la PATH fabriquee doivent etre des COPIES : un lien "
        "ferait ecrire dans /usr/bin, ce qui a deja casse ce conteneur")


def test_le_recapitulatif_powershell_DISTINGUE_macos_de_linux():
    """`C3-4`, la moitie que ce conteneur ne peut pas jouer.

    `test_install_ps1_n_annonce_PAS_macOS_quand_il_tourne_sous_LINUX` mesure le
    cas Linux pour de vrai. Le cas macOS, lui, est inatteignable ici -- et un
    mutant remplacant la condition macOS par `$false` SURVIT au banc dynamique,
    parce que sous Linux les deux branches rendent la meme chose.

    D'ou cette frontiere STATIQUE, sur la forme : le recapitulatif doit
    consulter `$IsMacOS`, et la branche « hors Windows » doit venir APRES --
    l'ordre est ce qui distingue les deux motifs. C'est la meme mecanique que
    `test_le_garde_powershell_du_raccourci_n_est_PAS_l_affichage`, pour la meme
    raison : mesurer ce qu'on ne peut pas executer, plutot que de le supposer.
    """
    ps = code_du_script(INSTALL_PS1)
    macos = ps.find('elseif ($IsMacOS)')
    assert macos != -1, (
        "le recapitulatif doit distinguer macOS de Linux : sans `$IsMacOS`, "
        "`-not (Test-SurWindows)` couvre les deux et le motif macOS est faux "
        "sur une machine Linux")
    hors_windows = ps.find(LIBELLE_PS1_HORS_WINDOWS)
    assert hors_windows != -1, "le libelle « hors Windows » a disparu"
    assert macos < hors_windows, (
        "la branche macOS doit venir AVANT la branche « hors Windows » : "
        "sinon la seconde absorbe la premiere et le motif macOS ne sort jamais")


def test_deposer_un_outil_factice_ne_SUIT_PAS_le_lien(tmp_path):
    """La garde de dernier recours, et elle a un cout reel a l'appui.

    `_maison_neuve` donne desormais a chaque test sa propre COPIE des binaires,
    si bien que `_deposer_outil` ne rencontre plus de lien en pratique. Une
    campagne de mutation l'a mesure : retirer l'`unlink` laisse le banc vert --
    mutant EQUIVALENT tant que la copie tient.

    On mesure donc la garde LA OU elle mord, c'est-a-dire sur un repertoire qui
    porte encore des liens. Ce n'est pas de la ceinture-et-bretelles : la PATH
    des fixtures `scope="module"` est faite de liens vers les vrais binaires du
    systeme, et un test qui l'emploierait directement -- comme le premier jet de
    ce lot l'a fait -- ecrirait dans `/usr/bin`. Ce conteneur y a perdu son
    `uname` pendant vingt minutes, et 36 tests avec.
    """
    binaires = tmp_path / "bin"
    binaires.mkdir()
    vrai = tmp_path / "le-vrai-binaire"
    vrai.write_text("#!/bin/sh\necho VRAI\n")
    vrai.chmod(0o755)
    (binaires / "uname").symlink_to(vrai)

    _deposer_outil(binaires, "uname", "#!/bin/sh\necho Darwin\n")

    assert vrai.read_text() == "#!/bin/sh\necho VRAI\n", (
        "le depot a ecrit A TRAVERS le lien : c'est le vrai binaire du systeme "
        "qui vient d'etre remplace")
    assert not (binaires / "uname").is_symlink()
    assert "Darwin" in (binaires / "uname").read_text()


# ==========================================================================
#  Le repli precompile est POSE, il n'est plus AFFICHE (story 8.11)
# ==========================================================================
#
# `EPIC11-ARB-271`, Egan le 2026-09-08, verbatim : « Je penche pour le repli
# automatique de notre script. Avec une condition : en cas d'echec (url, erreur
# etc) le script donne toujours la commande alternative a taper dans le
# terminal, et si possible la plus "officielle" pour chaque dependance
# necessaire. »
#
# CE QUE CE LOT NE MESURE PAS, dit plutot que tu, et c'est structurel :
#
#   * **aucun telechargement reel** (AC10). Le `curl` de ces machines est
#     factice et ne va sur AUCUN reseau : il recopie un fichier que le banc a
#     prepare. Motif ecrit par ce module lui-meme, l. 64-67 : « on ne mesure
#     pas une installation reelle : elle modifierait la machine de qui joue la
#     suite ». Le telechargement REEL appartient a `macos-15-intel` de la story 8.10 ;
#   * **aucun condensat reellement CALCULE** sur l'archive servie. Le `shasum`
#     de ces machines lit une table ecrite par le banc. Il ne pouvait pas en
#     etre autrement : fabriquer une archive dont le SHA-256 vaut la constante
#     epinglee demanderait les 26 Mo d'origine. Ce que le banc mesure est donc
#     « le produit COMPARE, et il refuse sur ecart » -- pas « le produit sait
#     calculer un SHA-256 ». La VALEUR des trois constantes est mesuree a part,
#     par `test_les_TROIS_condensats_epingles_sont_ceux_qui_ont_ete_MESURES`,
#     et les deux ensemble ne sont pas tautologiques : l'une porte sur le
#     comportement, l'autre sur la constante ;
#   * **rien de Gatekeeper en vrai.** Qu'un fichier tire par `curl` porte
#     `com.apple.quarantine` n'est PAS etabli, et le produit ne l'affirme pas :
#     il retire l'attribut defensivement puis LANCE le binaire, le lancement
#     etant le seul verdict. La mesure appartient a `macos-15-intel`/`macos-14` de la
#     story 8.10, qui lira `xattr -l` sur le binaire pose.

#: Le binaire factice que le repli depose : il ne sait que DEMARRER, et il dit
#: son nom en le faisant. Les deux membres sont donc DISTINGUABLES -- regle des
#: fabriques, point 1 : une permutation ffmpeg/ffprobe ne se verrait pas si les
#: deux rendaient la meme chose.
BINAIRE_QUI_DEMARRE = (
    "#!/bin/sh\n"
    "# Binaire factice pose par le repli precompile. Il ne fait que demarrer.\n"
    "if [ \"$1\" = \"-version\" ]; then\n"
    "    echo '%s version 9.0.1-factice'\n"
    "    exit 0\n"
    "fi\n"
    "exit 0\n"
)

#: Le meme, mais il NE DEMARRE PAS -- le regime « pose mais inutilisable »,
#: qui est exactement ce que Gatekeeper ou une architecture incompatible
#: produisent, et que le retrait d'attribut seul ne prouverait jamais.
BINAIRE_QUI_NE_DEMARRE_PAS = (
    "#!/bin/sh\n"
    "# Binaire factice qui refuse de demarrer (Gatekeeper, signature, arch).\n"
    "echo '%s: killed' >&2\n"
    "exit 137\n"
)

def condensat_voisin(valeur: str) -> str:
    """Un condensat faux qui ne differe qu'au DERNIER caractere.

    **Mesure de la campagne de mutation, mutant `M4`, survivant a la premiere
    redaction.** Ce banc employait une valeur entierement differente
    (`"0" * 63 + "1"`). Un produit qui ne comparerait que le PREMIER caractere
    du condensat -- `${obtenu:0:1}` contre `${attendu:0:1}` -- refusait quand
    meme cette valeur-la, et les deux frontieres du condensat restaient vertes
    sur une verification qui ne verifie plus rien.

    C'est la regle des fabriques (point 4, le bord de QUEUE) transposee d'une
    collection a une CHAINE : une cible au debut ne demasque pas un balayage
    tronque. Le voisin ci-dessous ne differe qu'a la toute fin, et il tue le
    mutant.
    """
    assert len(valeur) == 64, valeur
    dernier = "0" if valeur[-1] != "0" else "f"
    return valeur[:-1] + dernier


def condensat_epingle(nom_de_constante: str) -> str:
    """Le condensat que `install.sh` EPINGLE, lu dans le script.

    Lu plutot que recopie : si quelqu'un met la version a jour, le banc suit
    la constante au lieu de rougir sur une valeur qu'il aurait figee de son
    cote. La valeur elle-meme est mesuree par une AUTRE frontiere -- celle-ci
    ne mesure que le comportement de comparaison.
    """
    trouve = re.search(r'^%s="([0-9a-f]{64})"$' % nom_de_constante,
                       INSTALL_SH.read_text(), re.M)
    assert trouve, (
        "install.sh ne porte plus la constante %s sous la forme attendue : "
        "c'est l'epinglage de l'AC4 qui a bouge, pas ce banc" % nom_de_constante)
    return trouve.group(1)


def version_epinglee(nom_de_constante: str) -> str:
    """La version que `install.sh` EPINGLE, lue dans le script.

    Meme geste que `condensat_epingle`, et pour le meme motif (finding `C3-1`
    de la revue du 2026-09-08) : le depot factice codait `9.0.1` et `3.12.8` en
    dur, si bien qu'une mise a jour de version -- exactement ce que
    l'engagement de maintenance de l'AC12 prescrit -- aurait fait servir au
    banc des fichiers que le produit ne demande plus. Le `curl` factice aurait
    rendu 6 (« Could not resolve host ») et une quinzaine de bancs seraient
    devenus rouges sur « le telechargement a echoue », c'est-a-dire sur un
    message qui accuse le produit.
    """
    trouve = re.search(r'^%s="([0-9][0-9A-Za-z.+-]*)"$' % nom_de_constante,
                       INSTALL_SH.read_text(), re.M)
    assert trouve, (
        "install.sh ne porte plus la constante %s sous la forme attendue : "
        "c'est l'epinglage de l'AC12 qui a bouge, pas ce banc" % nom_de_constante)
    return trouve.group(1)


#: Les constantes de version que les URL epinglees developpent.
VERSIONS_EPINGLEES = ("FFMPEG_VERSION_EPINGLEE", "PYTHON_PKG_VERSION_EPINGLEE")


def nom_de_fichier_epingle(nom_de_constante_url: str) -> str:
    """Le nom du fichier que `install.sh` ira REELLEMENT chercher.

    Lu dans l'URL et non reconstruit a partir de la version seule, parce que
    c'est l'URL qui fait le contrat avec le `curl` factice : celui-ci sert
    `<depot>/${adresse##*/}`. La FORME du nom est donc aussi couplee que la
    version -- `python-<v>-macos11.pkg` porte un `-macos11` qu'aucune constante
    de version ne contient, et une source qui passerait a `-macos12` casserait
    un banc qui n'aurait lu que la version.

    L'assertion finale est la garde qui rend cette lecture sure : si une
    variable NEUVE entre dans une URL epinglee, ce banc le DIT au lieu de
    servir en silence un fichier que personne ne demande.
    """
    trouve = re.search(r'^%s="([^"]+)"$' % nom_de_constante_url,
                       INSTALL_SH.read_text(), re.M)
    assert trouve, (
        "install.sh ne porte plus l'URL %s sous la forme attendue"
        % nom_de_constante_url)
    url = trouve.group(1)
    for constante in VERSIONS_EPINGLEES:
        url = url.replace("${%s}" % constante, version_epinglee(constante))
    assert "${" not in url, (
        "l'URL %s porte une expansion que ce banc ne sait pas resoudre (%r) : "
        "le depot factice servirait un fichier que le produit ne demande pas, "
        "et le `curl` factice rendrait 6 sur tous les bancs du repli."
        % (nom_de_constante_url, url))
    return url.rsplit("/", 1)[-1]


def _archive_a_un_membre(chemin: Path, membre: str, contenu: str,
                         *, executable: bool = False) -> None:
    """Une archive REELLE, a UN seul membre, place a la RACINE.

    C'est la forme MESUREE des archives d'evermeet le 2026-09-08 : un seul
    membre, `ffmpeg` ou `ffprobe`, a la racine -- pas de sous-dossier a
    traverser. Une fixture qui en mettrait deux, ou un sous-dossier, mesurerait
    une archive que la source ne produit pas.

    **`executable` vaut FAUX par defaut, et c'est une mesure de la campagne**
    (mutant `M11`, survivant a la premiere redaction). L'archive donnait alors
    `0o755` a son membre, si bien que le fichier sortait deja executable
    d'`unzip` : retirer le `chmod +x` du produit ne changeait rien et aucune
    frontiere ne le voyait. Le cas adverse -- une archive dont le membre n'a
    PAS le bit -- est celui qui rend `chmod +x` porteur, et rien ne garantit
    qu'une source le pose : un zip peut venir d'un systeme qui ignore les
    droits POSIX.
    """
    with zipfile.ZipFile(chemin, "w") as archive:
        entree = zipfile.ZipInfo(membre)
        entree.external_attr = (0o755 if executable else 0o644) << 16
        archive.writestr(entree, contenu)


def _curl_factice(depot: Path) -> str:
    """Un `curl` qui ne va sur AUCUN reseau (AC10).

    Il recopie `<depot>/<dernier segment de l'URL>` vers la cible de `-o`, et
    rend 6 -- le code de `Could not resolve host` -- quand ce fichier n'existe
    pas. C'est ce qui donne au banc ses trois regimes sans un octet de reseau :
    archive juste (fichier prepare), archive fausse (fichier prepare mais
    corrompu), echec reseau (fichier absent).

    `--retry` et `--connect-timeout` sont reconnus NOMMEMENT parce qu'ils
    prennent une valeur : un `-*) shift` naif prendrait leur `2` et leur `20`
    pour l'URL, et le factice recopierait un fichier nomme `2`.
    """
    return (
        "#!/bin/sh\n"
        "# curl factice : aucun reseau, il recopie un fichier prepare.\n"
        "depot='%s'\n"
        "destination=''\n"
        "adresse=''\n"
        "while [ $# -gt 0 ]; do\n"
        "    case \"$1\" in\n"
        "        -o) destination=\"$2\"; shift 2 ;;\n"
        "        --retry|--connect-timeout) shift 2 ;;\n"
        "        -*) shift ;;\n"
        "        *) adresse=\"$1\"; shift ;;\n"
        "    esac\n"
        "done\n"
        "source=\"${depot}/${adresse##*/}\"\n"
        "if [ ! -f \"$source\" ]; then\n"
        "    echo 'curl: (6) Could not resolve host' >&2\n"
        "    exit 6\n"
        "fi\n"
        "[ -n \"$destination\" ] || exit 2\n"
        "cat \"$source\" > \"$destination\"\n"
    ) % depot


def _calculateur_factice(table: Path, avec_option_a: bool) -> str:
    """Un `shasum`/`sha256sum` qui LIT une table au lieu de calculer.

    Voir l'entete de section : fabriquer une archive dont le SHA-256 vaut la
    constante epinglee demanderait les 26 Mo d'origine. La table donne au banc
    les deux sens du drapeau -- condensat juste, condensat faux -- sur la meme
    archive, ce qu'un vrai calcul ne permettrait pas.

    `avec_option_a` distingue les deux familles : macOS livre `shasum -a 256`
    et PAS `sha256sum` ; les Linux livrent l'inverse. Le produit lit les deux,
    et le banc joue les deux.
    """
    consomme_a = "        -a) shift 2 ;;\n" if avec_option_a else ""
    return (
        "#!/bin/sh\n"
        "# Calculateur de condensat factice : il lit une table du banc.\n"
        "table='%s'\n"
        "fichier=''\n"
        "while [ $# -gt 0 ]; do\n"
        "    case \"$1\" in\n"
        "%s"
        "        -*) shift ;;\n"
        "        *) fichier=\"$1\"; shift ;;\n"
        "    esac\n"
        "done\n"
        # LE FICHIER EST OUVERT, ET C'EST TOUTE LA DIFFERENCE (finding `C2-2`
        # de la revue du 2026-09-08). Sans cette ligne, ce factice repond a
        # partir du seul NOM -- `${fichier##*/}` --, si bien que la propriete
        # centrale de l'AC4 se mesurait sur une chaine de caracteres et jamais
        # sur un octet. Mutant mesure ce jour-la : `condensat_sha256`
        # recevant `/inexistant/<nom>.zip` au lieu de l'archive telechargee ;
        # les 116 tests restaient VERTS, c'est-a-dire qu'un produit qui
        # verifie le condensat d'un fichier qui n'existe pas etait declare
        # conforme. Un `shasum` reel echoue sur un fichier absent : le factice
        # doit echouer aussi, sinon il ment sur le seul point ou il remplace
        # l'outil.
        "if [ ! -f \"$fichier\" ]; then\n"
        "    echo \"calculateur factice : $fichier est introuvable\" >&2\n"
        "    exit 1\n"
        "fi\n"
        "base=\"${fichier##*/}\"\n"
        "while IFS=' ' read -r nom valeur; do\n"
        "    if [ \"$nom\" = \"$base\" ]; then\n"
        "        printf '%%s  %%s\\n' \"$valeur\" \"$fichier\"\n"
        "        exit 0\n"
        "    fi\n"
        "done < \"$table\"\n"
        "exit 1\n"
    ) % (table, consomme_a)


def _xattr_factice(journal: Path) -> str:
    """Un `xattr` qui journalise et rend 1, comme le vrai sur un attribut ABSENT.

    C'est le cas NOMINAL attendu -- rien n'etablit que `curl` pose
    `com.apple.quarantine` --, et c'est precisement pourquoi il faut le jouer :
    le produit doit survivre a un `xattr` qui echoue, sinon le repli casserait
    sur toutes les machines ou l'attribut n'est pas la, c'est-a-dire
    peut-etre toutes.
    """
    return (
        "#!/bin/sh\n"
        "# xattr factice : journalise l'appel, et rend 1 (attribut absent).\n"
        "echo \"xattr $*\" >> '%s'\n"
        "exit 1\n"
    ) % journal


def _pipx_factice(inventaire: Path, bin_dir) -> str:
    """Le `pipx` factice, etendu a `environment --value PIPX_BIN_DIR` (AC2).

    `bin_dir=None` reproduit le pipx d'origine du banc : il ne repond RIEN a
    `environment`, ce qui est le regime « PIPX_BIN_DIR absent » et doit faire
    retomber le produit sur `${HOME}/.local/bin`. Une valeur reproduit le
    regime « pipx expose un autre repertoire », ou un depot dans
    `~/.local/bin` serait invisible au PATH -- le defaut meme qu'Egan decrit.
    """
    reponse = ""
    if bin_dir is not None:
        reponse = (
            "if [ \"$1\" = \"environment\" ]; then\n"
            "    echo '%s'\n"
            "    exit 0\n"
            "fi\n" % bin_dir
        )
    return (
        "#!/bin/sh\n"
        "# pipx factice : il ne sait que dire ce qui est installe, et ou il\n"
        "# expose ses applications.\n"
        "%s"
        "if [ \"$1\" = \"list\" ] && [ \"$2\" = \"--short\" ]; then\n"
        "    cat '%s'\n"
        "fi\n"
        "exit 0\n"
    ) % (reponse, inventaire)


def machine_du_repli(tmp_path: Path, *,
                     majeur: str = "15",
                     arch: str = "x86_64",
                     casses: tuple = (),
                     condensats_faux: tuple = (),
                     qui_ne_demarrent_pas: tuple = (),
                     absents_du_depot: tuple = (),
                     sans_outils: tuple = (),
                     avec_xattr: bool = True,
                     pipx_bin_dir=None,
                     avec_python: bool = True,
                     membre_executable: bool = False,
                     gestes_en_echec: tuple = ()) -> dict:
    """La machine sur laquelle le repli precompile se joue POUR DE VRAI.

    Un Mac Intel en Sequoia par defaut -- le contre-exemple d'Egan, celui ou
    Homebrew n'a plus rien a servir. Tous les leviers d'AC9 passent par des
    parametres, et chacun se joue DANS LES DEUX SENS quelque part dans ce lot :
    un banc qui ne jouerait que le chemin heureux mesurerait la moitie du
    produit et l'annoncerait vert.

    Les trois familles de membres nommes (`casses`, `condensats_faux`,
    `qui_ne_demarrent_pas`, `absents_du_depot`) prennent des noms de BINAIRE
    -- `ffmpeg` ou `ffprobe` --, et c'est la regle des fabriques : la cible
    doit pouvoir se placer en TETE comme en QUEUE. Un repli qui s'arreterait
    apres le premier membre resterait vert si le banc ne cassait jamais que le
    premier ; un repli qui ne verifierait que le premier resterait vert si le
    banc ne cassait jamais que le second.

    `gestes_en_echec` casse le SEUL geste privilegie du script -- `sudo` et
    `installer`, nommes separement (finding `C2-5`). Il vient plus tard que les
    autres parce qu'il manquait : les deux factices rendaient toujours 0, et
    l'echec de l'unique ligne qui reclame un mot de passe administrateur
    n'etait mesure nulle part. Il se joue DANS LES DEUX SENS, comme tous les
    autres.

    Rend un dictionnaire plutot qu'un environnement seul : le test a besoin de
    la DESTINATION et du journal `xattr` pour lire l'etat de la machine apres
    coup, et un verdict ne se lit pas sur la seule sortie.
    """
    environnement = _fabriquer_machine(tmp_path, avec_ffmpeg=False,
                                       liste_pipx="", avec_affichage=False,
                                       avec_python=avec_python)
    binaires = Path(environnement["PATH"].split(os.pathsep)[0])

    _deposer_outil(binaires, "uname",
                   "#!/bin/sh\n"
                   "case \"$1\" in\n"
                   "    -m) echo %s ;;\n"
                   "    *)  echo Darwin ;;\n"
                   "esac\n" % arch)
    _deposer_outil(binaires, "sw_vers", "#!/bin/sh\necho %s.7.6\n" % majeur)
    _deposer_outil(binaires, "brew", "#!/bin/sh\nexit 0\n")

    # Le depot du curl factice : les archives et le paquet que le banc « sert ».
    depot = tmp_path / "depot"
    depot.mkdir()
    table = tmp_path / "condensats.txt"
    lignes = []

    # Les trois noms de fichier sont LUS dans les URL epinglees, jamais
    # recopies (finding `C3-1`). Une version mise a jour dans `install.sh` est
    # alors suivie par le banc, au lieu de le faire rougir sur un
    # « telechargement echoue » qui accuserait le produit.
    for nom, constante, constante_url in (
            ("ffmpeg", "FFMPEG_ZIP_SHA256", "FFMPEG_ZIP_URL"),
            ("ffprobe", "FFPROBE_ZIP_SHA256", "FFPROBE_ZIP_URL")):
        archive = depot / nom_de_fichier_epingle(constante_url)
        if nom in absents_du_depot:
            continue
        if nom in casses:
            # Pas une archive du tout : `unzip` echouera pour de vrai.
            archive.write_bytes(b"ceci n'est pas une archive zip\n" * 8)
        else:
            modele = (BINAIRE_QUI_NE_DEMARRE_PAS if nom in qui_ne_demarrent_pas
                      else BINAIRE_QUI_DEMARRE)
            _archive_a_un_membre(archive, nom, modele % nom,
                                 executable=membre_executable)
        epingle = condensat_epingle(constante)
        valeur = condensat_voisin(epingle) if nom in condensats_faux else epingle
        # La cle de la table est le nom du fichier TELECHARGE, pas celui du
        # fichier SERVI : `curl -o` ecrit `<atelier>/ffmpeg.zip`, la ou le
        # depot porte `ffmpeg-9.0.1.zip`. Les deux ont ete confondus a la
        # premiere redaction, et le repli abandonnait sur « condensat non
        # calculable » -- un rouge qui ressemblait a un defaut du produit.
        lignes.append("%s.zip %s" % (nom, valeur))

    paquet_python = depot / nom_de_fichier_epingle("PYTHON_PKG_URL")
    if "python" not in absents_du_depot:
        paquet_python.write_bytes(b"paquet python factice\n")
        epingle = condensat_epingle("PYTHON_PKG_SHA256")
        lignes.append("%s %s" % (
            paquet_python.name,
            condensat_voisin(epingle) if "python" in condensats_faux else epingle))
    table.write_text("\n".join(lignes) + "\n")

    _deposer_outil(binaires, "curl", _curl_factice(depot))
    _deposer_outil(binaires, "shasum", _calculateur_factice(table, True))
    _deposer_outil(binaires, "sha256sum", _calculateur_factice(table, False))

    journal_xattr = tmp_path / "appels_xattr.txt"
    if avec_xattr:
        _deposer_outil(binaires, "xattr", _xattr_factice(journal_xattr))

    inventaire = tmp_path / "liste_pipx.txt"
    _deposer_outil(binaires, "pipx", _pipx_factice(inventaire, pipx_bin_dir))

    # `installer` n'existe pas sous Linux : sans lui, le repli Python echouerait
    # sur un `command not found` plutot que sur ce qu'on veut mesurer.
    # `installer` factice : il journalise SI L'ELEVATION A EU LIEU, et pas
    # seulement ses arguments. **Mesure de la campagne, mutant `M29`** : un
    # `sudo` factice transparent (`exec "$@"`) rendait la meme trace qu'on
    # passe par lui ou non, si bien que remplacer `executer sudo installer` par
    # `executer installer` -- le defaut MEME que cette story a corrige sur
    # `${SUDO}` vide -- restait vert. Le marqueur d'environnement est ce qui
    # distingue les deux.
    # L'ECHEC DE L'UNIQUE GESTE PRIVILEGIE DU SCRIPT (finding `C2-5` de la revue
    # du 2026-09-08). Ces deux factices rendaient TOUJOURS 0 : le seul chemin
    # ou `install.sh` demande un mot de passe administrateur n'avait donc
    # aucune mesure de son echec, et le mutant
    # `executer sudo installer ... || true` survivait en annoncant « ok Python
    # 3.12.8 pose par l'installeur officiel » alors que rien n'etait installe.
    # `docs/installation/macos.md` promet nommement le « refus de mot de
    # passe » parmi les echecs qui donnent la commande de secours.
    #
    # DEUX gestes distincts et distinguables, plutot qu'un drapeau unique --
    # regle des fabriques, point 1 : le produit ne voit qu'un code de sortie
    # (`if ! executer sudo installer ...`), mais les deux causes ne laissent
    # PAS la meme trace, et c'est ce qui permet de verifier qu'on mesure bien
    # celle qu'on croit :
    #
    #   * `sudo` en echec    -> `installer` n'est JAMAIS lance (mot de passe
    #                           refuse : le journal reste absent) ;
    #   * `installer` en echec -> il est lance et rend 1 (paquet rejete,
    #                           droits insuffisants : le journal existe).
    _deposer_outil(binaires, "installer",
                   "#!/bin/sh\n"
                   "# `installer` factice : il dit ce qu'on lui a demande, et\n"
                   "# s'il a ete lance a travers `sudo`.\n"
                   "echo \"installer sudo=${MMU_PASSE_PAR_SUDO:-non} $*\" >> '%s'\n"
                   "%s"
                   "exit 0\n" % (
                       tmp_path / "appels_installer.txt",
                       ("echo 'installer: Error - the package was rejected' >&2\n"
                        "exit 1\n") if "installer" in gestes_en_echec else ""))
    # `sudo` factice : JAMAIS le vrai. Un test qui accepterait l'elevation
    # lancerait le sudo du conteneur sur `installer -pkg` -- c'est la famille
    # du `/usr/bin/uname` remplace, en pire.
    _deposer_outil(binaires, "sudo",
                   "#!/bin/sh\n"
                   "# sudo factice : il n'eleve rien, il LAISSE UNE TRACE de\n"
                   "# son passage, puis execute.\n"
                   "%s"
                   "MMU_PASSE_PAR_SUDO=1\n"
                   "export MMU_PASSE_PAR_SUDO\n"
                   "exec \"$@\"\n" % (
                       ("echo 'sudo: 3 incorrect password attempts' >&2\n"
                        "exit 1\n") if "sudo" in gestes_en_echec else ""))

    for outil in sans_outils:
        cible = binaires / outil
        if cible.is_symlink() or cible.exists():
            cible.unlink()

    destination = (Path(pipx_bin_dir) if pipx_bin_dir is not None
                   else Path(environnement["HOME"]) / ".local" / "bin")
    return {
        "env": environnement,
        "destination": destination,
        "journal_xattr": journal_xattr,
        "appels_installer": tmp_path / "appels_installer.txt",
        "depot": depot,
    }


#: Le parcours nominal du repli : un Mac Intel, ffmpeg absent, et rien d'autre
#: a faire. `--sans-verification` parce que la verification finale lancerait
#: `mmu --version`, qui n'existe pas ici ; `--sans-path` et `--sans-raccourci`
#: parce qu'ils n'ont rien a voir avec ce qu'on mesure.
DRAPEAUX_DU_REPLI = ["--non-interactif", "--cli", "--sans-path",
                     "--sans-raccourci", "--sans-verification",
                     # Voir `IGNORER_HORS_DU_PATH` : sans lui, une machine du
                     # repli fabriquee sans Python en trouve un dans le
                     # `/usr/local/bin` du conteneur, et le repli Python n'est
                     # plus jamais atteint.
                     IGNORER_HORS_DU_PATH]


def jouer_le_repli(machine, drapeaux=None):
    """Joue `install.sh` SANS `--dry-run` sur une machine du repli.

    Sans `--dry-run`, parce qu'un repli qui depose un fichier ne se mesure pas
    sur un plan : le verdict est l'etat de la machine. C'est la cinquieme
    exception a la regle « tout passe par --dry-run » de ce module, et elle
    reste inoffensive pour la meme raison que les quatre autres -- `pipx`,
    `curl`, `sudo` et `installer` sont factices, et le `HOME` est jetable.

    **`cwd` est JETABLE, et ca a ete paye le 2026-09-08.** Le repertoire
    courant de pytest est la RACINE DU DEPOT. Un mutant de la campagne (`M22`,
    la garde d'atelier temporaire retiree) a fait ecrire un binaire `ffmpeg` de
    175 octets **a la racine du depot**, non suivi et non ignore. C'est le
    defaut `C1-5`/`C2-4`/`C3-2` de la revue 8.8 -- le banc qui ecrit dans
    l'arbre reel de qui joue la suite --, retrouve par un autre chemin, et
    `jouer_sans_terminal` porte deja son parametre `cwd` pour ce motif exact.

    Ce que la mesure a etabli au passage, et qui change ou est le rempart :
    ni `cd ""` ni `unzip -d ""` ne REFUSENT une destination vide -- les deux
    reussissent et emploient le repertoire courant. Le seul rempart est donc la
    garde d'atelier du produit, cote `install.sh`.
    """
    courant = Path(machine["env"]["HOME"]) / "repertoire_courant_jetable"
    courant.mkdir(exist_ok=True)
    code, brut = jouer_sans_terminal(
        list(drapeaux if drapeaux is not None else DRAPEAUX_DU_REPLI),
        machine["env"], cwd=courant)
    machine["courant"] = courant
    return code, sans_ansi(brut)


# ------------------------------------------------ AC1/AC2/AC3 : le repli POSE

def test_le_repli_POSE_REELLEMENT_ffmpeg_ET_ffprobe(tmp_path):
    """AC1 -- et c'est le renversement que la story porte.

    Jusqu'au 2026-09-08, `install.sh` AFFICHAIT la voie sans compilation
    (`info "  curl -fLO ..."`, l. 564-568) et ne l'empruntait jamais. Aucune
    ligne du depot ne telechargeait, ne dezippait ni n'installait un binaire
    precompile. Ce test est ce qui distingue « le script le dit » de « le
    script le FAIT » : le verdict se lit sur l'ETAT DE LA MACHINE -- deux
    fichiers presents, executables, et qui DEMARRENT --, jamais sur la sortie.

    Les DEUX membres sont mesures, et ils sont distinguables : `ffprobe` est
    aussi necessaire que `ffmpeg` (le produit lit les deux), et un repli qui
    s'arreterait au premier laisserait une machine a moitie posee en
    annoncant un succes.
    """
    machine = machine_du_repli(tmp_path)
    code, sortie = jouer_le_repli(machine)

    assert code == 0, sortie
    for nom in ("ffmpeg", "ffprobe"):
        pose = machine["destination"] / nom
        assert pose.is_file(), (
            "le repli n'a POSE aucun %s : il affiche encore la voie sans "
            "compilation au lieu de l'emprunter.\n%s" % (nom, sortie))
        assert os.access(pose, os.X_OK), (
            "%s a ete pose sans bit d'execution : il ne servira a rien" % nom)
        # Le binaire pose est bien CELUI-LA : les deux membres se distinguent
        # par ce qu'ils disent, faute de quoi une permutation resterait verte.
        rendu = subprocess.run([str(pose), "-version"], stdout=subprocess.PIPE,
                               timeout=30).stdout.decode()
        assert nom in rendu, (
            "le binaire pose sous le nom %s en rend un autre : %r" % (nom, rendu))


def test_le_repli_n_ECRIT_JAMAIS_dans_le_REPERTOIRE_COURANT(tmp_path):
    """Frontiere NEGATIVE -- et elle vient d'un fichier trouve a la racine du depot.

    **Ce qui l'a fait ecrire, le 2026-09-08.** Un `ffmpeg` de 175 octets,
    executable, non suivi et non ignore, a la RACINE du depot. Diagnostic fait
    avant tout menage : il vient d'un mutant de la campagne (`M22`, la garde
    d'atelier temporaire retiree), pas du produit -- mais le mecanisme qu'il
    revele est reel et il est SILENCIEUX.

    Les archives d'evermeet ne portent qu'UN membre, **a la racine** : `unzip`
    le depose donc dans le repertoire de travail. Si l'atelier temporaire est
    vide ou relatif, ce repertoire devient celui de l'utilisateur -- son home,
    son bureau, un depot. Et rien ne le dirait, mesure le meme jour :

        cd "" && pwd              -> REUSSIT, on reste dans le courant
        unzip -o -q -d "" a.zip   -> REUSSIT, extrait dans le courant

    La ligne 567 d'origine (`sudo mv ffmpeg ffprobe /usr/local/bin/`) supposait
    exactement ce comportement, ce qui explique qu'il ait pu se propager.

    Cette frontiere mesure le PRODUIT dans son parcours nominal : apres une
    pose reussie, le repertoire courant n'a rien gagne. La garde de
    non-vacuite est indispensable ici -- un repli qui n'aurait rien fait du
    tout laisserait aussi un repertoire vide.
    """
    machine = machine_du_repli(tmp_path)
    code, sortie = jouer_le_repli(machine)

    # Non-vacuite : le repli a REELLEMENT travaille.
    assert code == 0, sortie
    assert (machine["destination"] / "ffmpeg").is_file(), (
        "le repli n'a rien pose : cette frontiere serait verte en ne mesurant "
        "rien.\n" + sortie)

    restes = sorted(p.name for p in machine["courant"].iterdir())
    assert restes == [], (
        "le repli a laisse %r dans le repertoire courant de qui l'a lance : "
        "l'atelier temporaire n'est plus etanche." % (restes,))


#: Un `mktemp -d` qui rend un chemin RELATIF ET EXISTANT -- le seul regime qui
#: mesure la garde de chemin absolu du produit.
#:
#: **Pourquoi `.` et pas `atelier_relatif`** (mesure du 2026-09-08, finding
#: `C2-3`) : un relatif INEXISTANT est deja attrape par le `[ ! -d ... ]` qui
#: suit la garde, si bien qu'un banc bati sur lui laisse les deux mutants
#: « la garde retiree » VIVANTS -- il croit mesurer la garde et mesure le test
#: d'existence. Un `.` passe `[ -d ]` sans difficulte : il ne reste alors que
#: la garde entre le produit et 80 Mo deposes dans le repertoire de qui a lance
#: la commande.
#:
#: `TMPDIR=.` produit ce regime POUR DE VRAI avec le `mktemp` du systeme -- ce
#: factice ne fabrique donc pas une panne que le terrain n'aurait pas.
MKTEMP_QUI_REND_UN_CHEMIN_RELATIF = (
    "#!/bin/sh\n"
    "# mktemp factice : il rend un chemin RELATIF et EXISTANT ('.'), ce que le\n"
    "# vrai mktemp rend sous TMPDIR=. -- et que la garde du produit doit refuser.\n"
    "echo .\n"
)


#: Les deux jambes du repli, et la garde d'atelier vit sur les DEUX. Nommees
#: ici plutot qu'ecrites en dur dans le test : c'est la regle des fabriques,
#: point 2 -- la cible se place en tete ET en queue, sinon une garde retiree
#: d'un seul cote reste verte.
JAMBES_DU_REPLI = ("ffmpeg", "python")


@pytest.mark.parametrize("jambe", JAMBES_DU_REPLI)
def test_un_ATELIER_RELATIF_mais_EXISTANT_fait_REFUSER_le_repli(tmp_path, jambe):
    """Finding `C2-3` -- la garde de chemin absolu de l'atelier ne mesurait RIEN.

    `install.sh` porte, sur les DEUX jambes, un
    `case "${atelier_du_repli}" in /*) ;; *) atelier_du_repli="" ;; esac` et
    quinze lignes de commentaire pour l'expliquer. Les deux mutants qui le
    retirent SURVIVAIENT : la garde etait nee du defaut `M22` -- un `ffmpeg`
    factice ecrit a la racine du depot -- et elle etait partie SANS SA MESURE.
    C'est le defaut symetrique que `CLAUDE.md` nomme a la liaison du
    2026-08-30 : un module porte sans son banc et un banc porte sans son
    module se valent.

    Le regime porteur est etroit et il faut le nommer : un atelier RELATIF
    **et EXISTANT**. Le relatif inexistant est deja refuse par le `[ ! -d ]`
    qui suit, donc un banc bati sur lui serait vert avec ou sans la garde.

    Ce qui se passe sans elle, mesure : `unzip` depose son membre unique dans
    le repertoire de travail et `curl -o` y ecrit ses archives -- c'est-a-dire
    le home, le bureau ou le depot de qui a colle la commande --, et le repli
    ANNONCE UNE REUSSITE. Le produit sain, lui, refuse en nommant la panne et
    donne la commande de secours : jamais un blocage sec (`EPIC11-ARB-271`).

    Les deux jambes sont jouees parce que la garde est ecrite DEUX FOIS. Une
    seule d'entre elles laisserait l'autre mutant vivant, ce qui est
    litteralement le defaut que ce finding decrit.
    """
    machine = machine_du_repli(tmp_path, avec_python=(jambe != "python"))
    binaires = Path(machine["env"]["PATH"].split(os.pathsep)[0])
    _deposer_outil(binaires, "mktemp", MKTEMP_QUI_REND_UN_CHEMIN_RELATIF)

    if jambe == "ffmpeg":
        code, sortie = jouer_le_repli(machine)
    else:
        # La jambe Python ne s'atteint QUE dans un vrai terminal : son mot de
        # passe se refuse par defaut en non-interactif, et le refus sort avant
        # l'atelier. « 2 » prend le repli precompile, « 1 » accepte le mot de
        # passe -- les memes deux reponses que
        # `test_le_repli_PYTHON_ACCEPTE_lance_REELLEMENT_l_installeur_officiel`.
        courant = Path(machine["env"]["HOME"]) / "repertoire_courant_jetable"
        courant.mkdir(exist_ok=True)
        machine["courant"] = courant
        sortie = sans_ansi(jouer_le_dialogue(
            ["--cli", "--sans-ffmpeg", "--sans-path", "--sans-raccourci",
             "--sans-verification", IGNORER_HORS_DU_PATH],
            ["2", "1"] + [""] * 6, machine["env"], cwd=courant))

    assert "aucun repertoire de travail temporaire n'a pu etre cree" in sortie, (
        "un atelier RELATIF a ete accepte sur la jambe %s : les archives "
        "atterrissent dans le repertoire courant de qui a lance la "
        "commande.\n%s" % (jambe, sortie))

    # Rien n'est pose, et c'est la moitie du verdict : un refus qui poserait
    # quand meme serait pire qu'une acceptation franche.
    if jambe == "ffmpeg":
        assert not (machine["destination"] / "ffmpeg").exists(), sortie
        assert "brew install ffmpeg" in sortie, (
            "le refus ne donne aucune commande de secours.\n" + sortie)
    else:
        assert not machine["appels_installer"].exists(), (
            "l'atelier refuse n'a pas empeche `installer` de tourner.\n" + sortie)
        assert "python.org/downloads" in sortie, (
            "le refus ne donne aucune commande de secours.\n" + sortie)

    # LE VERDICT QUI COMPTE : le repertoire courant n'a rien gagne. C'est lui
    # que la garde protege, et c'est lui qu'un mutant salit.
    restes = sorted(p.name for p in machine["courant"].iterdir())
    assert restes == [], (
        "la jambe %s a laisse %r dans le repertoire courant : l'atelier "
        "relatif a bien ete employe." % (jambe, restes))


def test_le_repli_ffmpeg_ne_demande_AUCUN_mot_de_passe(tmp_path):
    """AC1 -- « Aucun `sudo`, aucune ecriture hors du compte de l'utilisateur ».

    Le volet COMPORTEMENTAL de la frontiere negative qui suit. La ligne 567
    disait `sudo mv ffmpeg ffprobe /usr/local/bin/` : elle demandait un mot de
    passe pour un geste qui n'en a pas besoin, et visait un repertoire que le
    script ne pose PAS sur le PATH.

    Le `sudo` de cette machine est factice et journalise ; l'assertion porte
    sur le fait qu'il n'est jamais appele -- et sur le fait que le fichier
    pose appartient bien a l'arborescence de l'utilisateur.
    """
    machine = machine_du_repli(tmp_path)
    binaires = Path(machine["env"]["PATH"].split(os.pathsep)[0])
    trace = tmp_path / "appels_sudo.txt"
    _deposer_outil(binaires, "sudo",
                   "#!/bin/sh\necho \"sudo $*\" >> '%s'\nexec \"$@\"\n" % trace)

    code, sortie = jouer_le_repli(machine)

    assert code == 0, sortie
    assert (machine["destination"] / "ffmpeg").is_file(), sortie
    assert not trace.exists(), (
        "le repli ffmpeg a eleve les droits : %r" % trace.read_text())
    assert str(machine["destination"]).startswith(machine["env"]["HOME"]), (
        "la destination du repli est hors du compte de l'utilisateur : %s"
        % machine["destination"])


#: Les six fonctions de la jambe FFMPEG du repli. `lancer_avec_plafond` en fait
#: partie parce qu'elle n'est appelee que de la (mesure : deux occurrences dans
#: le script, sa definition et son unique appel, dans
#: `poser_un_membre_precompile`).
#:
#: La jambe PYTHON n'y est PAS, et c'est le coeur de la frontiere : elle DOIT
#: porter `sudo`, `installer -pkg ... -target /` etant la seule voie officielle
#: sur macOS. Un balayage global rougirait donc sur du code juste.
FONCTIONS_DE_LA_JAMBE_FFMPEG = (
    "repli_precompile_ffmpeg",
    "poser_un_membre_precompile",
    "repertoire_binaire_de_pipx",
    "lancer_avec_plafond",
    "condensat_sha256",
    "condensat_calculable",
)

#: Les deux fonctions de la jambe PYTHON, qui portent l'elevation. Elles
#: servent de garde de non-vacuite SYMETRIQUE : un decoupage qui rendrait zero
#: ligne serait vert des deux cotes, et c'est le seul defaut qu'une frontiere
#: negative ne voit jamais toute seule.
FONCTIONS_DE_LA_JAMBE_PYTHON = (
    "repli_precompile_python",
    "_poser_le_paquet_python",
)


def test_AUCUN_sudo_dans_la_jambe_FFMPEG_du_repli():
    """AC1 -- la frontiere negative que les *testing standards* de la story
    EXIGENT, et qui n'existait pas (finding `C3-2`).

    Verbatim de la story : « Frontieres negatives exigees : [...] aucun `sudo`
    dans le repli ffmpeg (AC1) ». Le regresseur mesure le 2026-09-08, qui
    SURVIVAIT -- un repli sur `sudo mv` ajoute quand le `mv` ordinaire
    echoue :

        if ! mv -f "${atelier}/${nom}" "${cible}/${nom}"; then
            if ! sudo mv -f "${atelier}/${nom}" "${cible}/${nom}"; then

    Ce que l'elevation couterait, et c'est pourquoi l'interdit est nomme : la
    destination du repli ffmpeg est le repertoire binaire de pipx, sous
    `${HOME}`. Un `sudo` y deposerait un `ffmpeg` appartenant a root -- que
    l'utilisateur ne peut plus remplacer, et que le retrait du binaire qui ne
    demarre pas (`rm -f`, non eleve) echouerait a supprimer SANS UN MOT. Le
    correctif `C1-1` du meme jour deviendrait inoperant.

    C'est aussi ce qui distingue les deux jambes : la jambe Python DOIT porter
    l'elevation, `sudo installer -pkg ... -target /` etant la seule voie
    officielle sur macOS. Une frontiere globale rougirait sur du code juste ;
    c'est le PERIMETRE qui porte la mesure, comme pour
    `test_AUCUN_sudo_dans_le_BLOC_d_ecriture_du_raccourci` dont ce test copie
    la forme.

    **Les deux gardes de non-vacuite valent autant que l'assertion.** Sans
    elles, un decoupage qui rendrait zero ligne serait vert des deux cotes :
    la jambe ffmpeg sans `sudo` parce qu'elle est vide, et personne pour dire
    que la jambe Python a perdu le sien.
    """
    code = code_du_script(INSTALL_SH)

    lignes = [ligne for nom in FONCTIONS_DE_LA_JAMBE_FFMPEG
              for ligne in corps_de_fonction(code, nom)]
    assert len(lignes) > 150, (
        "les six fonctions de la jambe ffmpeg ne font que %d lignes : ce n'est "
        "pas le perimetre que cette frontiere croit balayer" % len(lignes))

    fautives = [ligne.strip() for ligne in lignes if "sudo" in ligne.lower()]
    assert fautives == [], (
        "une elevation de droits est apparue dans la jambe FFMPEG du repli, "
        "qui ecrit sous ${HOME} : %r" % (fautives,))

    # NON-VACUITE SYMETRIQUE : la jambe Python porte bien son elevation. Si
    # elle la perdait, ce balayage-ci resterait vert alors que le produit
    # serait casse -- l'annonce du mot de passe aurait menti et `installer`
    # tournerait nu.
    elevations = [ligne.strip() for nom in FONCTIONS_DE_LA_JAMBE_PYTHON
                  for ligne in corps_de_fonction(code, nom)
                  if "sudo" in ligne.lower()]
    assert len(elevations) >= 2, (
        "la jambe PYTHON ne nomme plus `sudo` que %d fois : ce test ne mesure "
        "plus une DIFFERENCE entre les deux jambes" % len(elevations))
    assert any("executer sudo installer" in ligne for ligne in elevations), (
        "la jambe PYTHON ne lance plus `installer` A TRAVERS `sudo` : "
        "`installer` tournerait nu, apres 46 Mo telecharges et une annonce de "
        "mot de passe qui aurait menti. %r" % (elevations,))


def test_la_destination_est_celle_que_pipx_EXPOSE_et_pas_un_chemin_devine(tmp_path):
    """AC2 -- le premier des deux sens, et c'est celui qui mordait.

    `install.ps1:298-302` interroge deja pipx (`pipx environment --value
    PIPX_BIN_DIR`) ; `install.sh` etait le SEUL des deux a coder le chemin en
    dur. Deposer ffmpeg dans un repertoire que pipx n'expose pas reproduirait
    EXACTEMENT le defaut qu'Egan decrit le 2026-09-08 -- verbatim : « l'outil
    n'est pas forcement ajoute au path et donc pas forcement detecte ».

    Le repertoire choisi ici n'est PAS `~/.local/bin`, et c'est tout l'objet :
    un produit qui coderait le chemin en dur poserait ailleurs et ce test le
    dirait.
    """
    ailleurs = tmp_path / "pipx_a_lui" / "bin"
    machine = machine_du_repli(tmp_path, pipx_bin_dir=str(ailleurs))
    code, sortie = jouer_le_repli(machine)

    assert code == 0, sortie
    assert (ailleurs / "ffmpeg").is_file(), (
        "le repli n'a pas suivi le repertoire que pipx EXPOSE : il code encore "
        "un chemin en dur.\n" + sortie)
    assert not (Path(machine["env"]["HOME"]) / ".local" / "bin" / "ffmpeg").exists(), (
        "le repli a pose dans ~/.local/bin alors que pipx expose ailleurs : "
        "l'outil serait pose sans etre detecte.\n" + sortie)


def test_sans_PIPX_BIN_DIR_le_repli_retombe_sur_local_bin(tmp_path):
    """AC2 -- le SECOND sens du meme drapeau, sans lequel le precedent serait
    un blanc-seing.

    Un produit qui rendrait TOUJOURS la valeur de pipx, sans repli, casserait
    la ou pipx n'est pas encore installe -- c'est-a-dire au premier passage
    d'une machine vierge, qui est le parcours nominal de ce script. Le `pipx`
    de cette machine ne repond RIEN a `environment`, exactement comme celui du
    banc d'origine.
    """
    machine = machine_du_repli(tmp_path, pipx_bin_dir=None)
    code, sortie = jouer_le_repli(machine)

    assert code == 0, sortie
    defaut = Path(machine["env"]["HOME"]) / ".local" / "bin"
    assert (defaut / "ffmpeg").is_file(), (
        "sans PIPX_BIN_DIR, le repli n'a rien pose : il n'a plus de defaut.\n"
        + sortie)


def test_GATEKEEPER_est_traite_ET_le_binaire_est_LANCE(tmp_path):
    """AC3 -- les DEUX gestes, et le second est le seul verdict.

    **Angle mort COMPLET avant cette story** : les mots `quarantine`, `xattr`,
    `spctl`, `codesign` et `Gatekeeper` n'apparaissaient dans AUCUN fichier de
    `scripts/`, `tests/` ni `docs/` (recherche insensible a la casse,
    2026-09-08).

    **Ce que ce test N'ETABLIT PAS** : que `curl` pose reellement
    `com.apple.quarantine`. Rien ne l'etablit, l'attribut etant pose par les
    applications qui s'y inscrivent. Le `xattr` de cette machine rend donc 1,
    comme le vrai sur un attribut absent -- et le repli doit y survivre, sans
    quoi il casserait sur toutes les machines ou l'attribut n'est pas la.
    La mesure de terrain appartient a `macos-15-intel` de la story 8.10.
    """
    machine = machine_du_repli(tmp_path)
    code, sortie = jouer_le_repli(machine)

    assert code == 0, sortie
    assert machine["journal_xattr"].exists(), (
        "le repli n'a jamais appele `xattr` : la quarantaine n'est pas traitee.\n"
        + sortie)
    appels = machine["journal_xattr"].read_text()
    assert "com.apple.quarantine" in appels, appels
    assert appels.count("com.apple.quarantine") >= 2, (
        "l'attribut n'est retire que sur UN des deux binaires : %r" % appels)
    assert (machine["destination"] / "ffmpeg").is_file(), (
        "un `xattr` qui rend 1 -- l'attribut etant absent -- a fait echouer le "
        "repli : le retrait doit etre inoffensif.\n" + sortie)


def test_le_bit_d_EXECUTION_est_pose_par_le_repli_quand_l_archive_ne_le_donne_pas(tmp_path):
    """AC1/AC9 -- le second sens d'un drapeau que la campagne a revele MUET.

    Un zip ne porte pas forcement les droits POSIX de ses membres : cree sous
    Windows, ou par un outil qui les ignore, le membre sort d'`unzip` en
    `0o644`. Le repli doit alors poser le bit lui-meme, sinon il depose un
    fichier que rien ne peut lancer -- et le controle de lancement (AC3)
    echouerait pour une raison qui n'a rien a voir avec Gatekeeper.

    Le sens « l'archive donne deja le bit » est joue ici ; le sens « elle ne le
    donne pas » est le DEFAUT de la fabrique depuis le mutant `M11`. Les deux
    doivent rendre un binaire executable, et c'est la meme assertion.
    """
    machine = machine_du_repli(tmp_path, membre_executable=True)
    code, sortie = jouer_le_repli(machine)

    assert code == 0, sortie
    pose = machine["destination"] / "ffmpeg"
    assert pose.is_file() and os.access(pose, os.X_OK), (
        "une archive qui DONNE deja le bit d'execution ne pose plus rien "
        "d'executable.\n" + sortie)


def test_SANS_xattr_sur_la_machine_le_repli_pose_QUAND_MEME(tmp_path):
    """AC3/AC9 -- le second sens du drapeau `xattr`.

    Une garde qui ne ferait pas varier ce drapeau ne mesurerait qu'un chemin.
    `xattr` est un outil macOS : il peut manquer d'un PATH restreint, et son
    absence ne doit pas coûter le repli -- c'est un geste DEFENSIF, pas une
    dependance.
    """
    machine = machine_du_repli(tmp_path, avec_xattr=False)
    code, sortie = jouer_le_repli(machine)

    assert code == 0, sortie
    assert (machine["destination"] / "ffmpeg").is_file(), (
        "l'absence de `xattr` a fait echouer le repli.\n" + sortie)
    assert not machine["journal_xattr"].exists()


@pytest.mark.parametrize("fautif", ["ffmpeg", "ffprobe"])
def test_un_binaire_qui_NE_DEMARRE_PAS_fait_ABANDONNER_le_repli(tmp_path, fautif):
    """AC3 -- « le lancement est le seul verdict », et il se joue AUX DEUX BORDS.

    Un attribut retire ne prouve pas qu'un binaire demarre. Sur Apple Silicon,
    c'est la signature -- pas la quarantaine -- qui decide.

    Les deux bords, et c'est la regle des fabriques (point 4, 2026-09-03) :
    `ffmpeg` est en TETE du balayage, `ffprobe` en QUEUE. Un repli qui ne
    lancerait que le premier binaire resterait vert sur le cas `ffmpeg` seul ;
    un repli qui s'arreterait apres le premier membre resterait vert sur le
    cas `ffprobe` seul. Les deux sont donc joues.
    """
    machine = machine_du_repli(tmp_path, qui_ne_demarrent_pas=(fautif,))
    code, sortie = jouer_le_repli(machine)

    assert "ne demarre pas" in sortie, (
        "un binaire pose qui rend un code non nul n'a pas fait abandonner le "
        "repli : le lancement n'est pas le verdict.\n" + sortie)
    assert "Repli precompile abandonne" in sortie, sortie
    assert "brew install ffmpeg" in sortie, (
        "l'abandon ne donne aucune commande de secours.\n" + sortie)


# ---------------------------------------------- AC4 : le condensat EPINGLE

def test_les_TROIS_condensats_epingles_sont_ceux_qui_ont_ete_MESURES():
    """AC4/AC12 -- la VALEUR des constantes, mesuree a part du comportement.

    Le banc du repli fait lire son condensat a un `shasum` factice : il mesure
    donc que le produit COMPARE et refuse sur ecart, jamais que la constante
    est la bonne. Sans cette frontiere-ci, remplacer les trois condensats par
    trois zeros laisserait tout le lot vert -- le factice suivant la constante,
    quelle qu'elle soit. C'est le motif du test tautologique de la 5.9.

    Les trois valeurs ont ete relevees le 2026-09-08, archives en main. Elles
    ne sont SERVIES par aucune source : l'API d'evermeet rend `url`, `size` et
    `sig` sans champ de condensat, et `python-3.12.8-macos11.pkg.sha256` rend
    HTTP 404. C'est ce qui les rend fortes -- une source compromise ne peut pas
    changer a la fois l'archive et une constante qui vit dans notre depot -- et
    c'est aussi ce qui en fait l'engagement de maintenance de l'AC12.
    """
    attendus = {
        "FFMPEG_ZIP_SHA256":
            "8a8c9e549983409fe6604b9aa665648b7a5def9407fe814c39c8b2ea7f64a48f",
        "FFPROBE_ZIP_SHA256":
            "d13f35db03456b7f65b7edb6437c86e23810fbfe91795e571f5b77211343b4f1",
        "PYTHON_PKG_SHA256":
            "c411b5372d563532f5e6b589af7eb16e95613d61bd5af7bfe78563467130bbff",
    }
    for constante, valeur in attendus.items():
        assert condensat_epingle(constante) == valeur, (
            "%s a change sans que la mesure qui l'a etabli soit refaite. Un "
            "condensat se releve archive en main, jamais de memoire." % constante)
    assert len(set(attendus.values())) == 3, "deux condensats identiques"

    # Et les URL vont avec : un condensat juste sur une URL changee ne verifie
    # plus rien. Les deux se posent ensemble ou ni l'un ni l'autre.
    code = code_du_script(INSTALL_SH)
    for morceau in ("https://evermeet.cx/ffmpeg/ffmpeg-",
                    "https://evermeet.cx/ffmpeg/ffprobe-",
                    "https://www.python.org/ftp/python/"):
        assert morceau in code, (
            "l'URL %r a quitte install.sh : le condensat epingle ne verifie "
            "plus rien." % morceau)


@pytest.mark.parametrize("fautif", ["ffmpeg", "ffprobe"])
def test_un_condensat_FAUX_fait_ABANDONNER_sans_rien_poser(tmp_path, fautif):
    """AC4 -- « il ne fait jamais poser le binaire "quand meme" ».

    Le volet le plus important du lot : un condensat qui ne correspond pas est
    la seule chose qui separe « telecharger un binaire » de « executer
    n'importe quoi ». L'issue est la commande de secours, jamais un
    avertissement suivi d'une pose.

    Joue AUX DEUX BORDS pour la meme raison que le lancement : un produit qui
    ne verifierait que la premiere archive resterait vert sur `ffmpeg` seul.
    """
    machine = machine_du_repli(tmp_path, condensats_faux=(fautif,))
    code, sortie = jouer_le_repli(machine)

    assert "condensat SHA-256" in sortie and "ne correspond pas" in sortie, (
        "un condensat faux n'a pas fait abandonner le repli.\n" + sortie)
    assert not (machine["destination"] / fautif).exists(), (
        "%s a ete POSE malgre un condensat qui ne correspond pas.\n%s"
        % (fautif, sortie))
    assert "brew install ffmpeg" in sortie, sortie


def test_le_condensat_se_verifie_AVANT_le_dezippage(tmp_path):
    """AC4 -- « condensat verifie AVANT dezippage ».

    Une archive fausse ne s'ouvre pas « pour voir ». Le regime est mesure par
    une archive qui n'en est PAS une (des octets quelconques) ET dont le
    condensat est faux : si le produit dezippait d'abord, le message parlerait
    d'une archive illisible ; s'il verifie d'abord, il parle du condensat.

    C'est un ORDRE qui se mesure, et un ordre ne se relit pas -- les deux
    versions du code passent la meme suite si personne ne l'epingle.
    """
    machine = machine_du_repli(tmp_path, casses=("ffmpeg",),
                               condensats_faux=("ffmpeg",))
    code, sortie = jouer_le_repli(machine)

    assert "ne correspond pas" in sortie, (
        "le produit a dezippe avant de verifier : il annonce une archive "
        "illisible la ou il devrait annoncer un condensat faux.\n" + sortie)
    assert "n'a pas pu etre ouverte" not in sortie, sortie


def test_une_archive_CORROMPUE_au_condensat_JUSTE_est_nommee_pour_ce_qu_elle_est(tmp_path):
    """AC6/AC9 -- « archive complete / archive tronquee », le chemin propre.

    Ce cas ne peut pas arriver en vrai -- une archive corrompue n'a pas le bon
    condensat -- et c'est justement pourquoi il faut le jouer : il est le SEUL
    moyen d'atteindre le chemin d'echec du dezippage, qui existe dans le
    produit et qui doit, lui aussi, nommer sa panne et donner la commande.

    Un chemin d'echec qu'aucun test n'atteint est un chemin d'echec dont
    personne ne sait s'il parle.
    """
    machine = machine_du_repli(tmp_path, casses=("ffprobe",))
    code, sortie = jouer_le_repli(machine)

    assert "n'a pas pu etre ouverte" in sortie, (
        "le dezippage d'une archive illisible n'est pas nomme.\n" + sortie)
    assert "Repli precompile abandonne" in sortie, sortie
    assert "brew install ffmpeg" in sortie, sortie
    assert not (machine["destination"] / "ffprobe").exists(), sortie


# --------------------------------------- AC5 : le repli Python et son sudo

def test_le_repli_PYTHON_ANNONCE_le_mot_de_passe_AVANT_de_le_demander(tmp_path):
    """AC5 -- « un `curl | bash` qui reclame un mot de passe sans prevenir est
    un motif que beaucoup refusent a vue ».

    Trois choses, et la troisieme est celle qui distingue une annonce d'une
    surprise :

    1. le mot de passe administrateur est NOMME avant tout `sudo` ;
    2. la question laisse REFUSER, et son defaut est le refus -- un defaut qui
       ne consomme ni des heures ni un mot de passe (AC7) ;
    3. le refus mene a la commande de secours, jamais a un blocage sec.
    """
    machine = machine_du_repli(tmp_path, avec_python=False)
    code, sortie = jouer_le_repli(
        machine, DRAPEAUX_DU_REPLI + ["--dry-run", "--sans-ffmpeg"])

    assert "mot de passe administrateur" in sortie, (
        "le repli Python lance `sudo` sans l'annoncer.\n" + sortie)
    assert "Lancer l'installeur officiel Python" in sortie, sortie
    # Le defaut est le REFUS : en non-interactif, personne ne peut taper un
    # mot de passe, et le script le prend ET le dit.
    assert "je prends 2)" in sortie, (
        "le defaut de la question du mot de passe n'est pas le refus.\n" + sortie)
    assert "python.org/downloads" in sortie, (
        "le refus ne donne aucune commande de secours.\n" + sortie)


def test_le_repli_PYTHON_ACCEPTE_lance_REELLEMENT_l_installeur_officiel(tmp_path):
    """AC5/AC9 -- le SECOND sens du drapeau `sudo`, et sans lui le precedent
    mesurerait un refus permanent.

    Un produit dont la question rendrait TOUJOURS « non » passerait le test
    precedent sans jamais poser Python. La reponse est donc tapee dans un VRAI
    pseudo-terminal, et le verdict se lit sur ce que `installer` a recu.

    `sudo` et `installer` sont factices : accepter l'elevation ici lancerait
    sinon le `sudo` du conteneur sur un `installer -pkg`, ce qui est la famille
    du `/usr/bin/uname` remplace, en pire.
    """
    machine = machine_du_repli(tmp_path, avec_python=False)
    brut = jouer_le_dialogue(
        ["--cli", "--sans-ffmpeg", "--sans-path", "--sans-raccourci",
         "--sans-verification", IGNORER_HORS_DU_PATH],
        # « 2 » : poser le binaire precompile. Puis « 1 » : oui, je tape mon
        # mot de passe. Les drapeaux suppriment toutes les autres questions,
        # si bien que ces deux reponses-la vont bien a ces deux questions-la.
        ["2", "1"] + [""] * 6, machine["env"])
    sortie = sans_ansi(brut)

    assert machine["appels_installer"].exists(), (
        "l'acceptation n'a lance aucun installeur : la question ne mene nulle "
        "part.\n" + sortie)
    trace = machine["appels_installer"].read_text()
    assert "-pkg" in trace and "-target /" in trace, trace
    # L'ELEVATION a bien eu lieu. `${SUDO}` est VIDE sur macOS -- il n'est pose
    # que sous Linux -- et l'ecrire ici lancerait `installer` NU : il echouerait
    # sur un refus de droits APRES 46 Mo telecharges, et l'annonce du mot de
    # passe aurait menti. C'est le defaut que cette story a corrige, et sans
    # cette ligne il reviendrait sans qu'aucune frontiere le voie (mutant `M29`).
    assert "sudo=1" in trace, (
        "l'installeur officiel a ete lance SANS elevation : %r" % trace)
    assert nom_de_fichier_epingle("PYTHON_PKG_URL") in trace, (
        "l'installeur n'a pas recu le paquet epingle : %r" % trace)


#: Les trois regimes du geste PRIVILEGIE, et il n'y en a qu'un dans tout le
#: script : `sudo installer -pkg ... -target /`. Chaque entree porte les
#: gestes qu'on casse, puis ce que le produit doit rendre.
#:
#: **Le drapeau varie DANS LES DEUX SENS, et c'est la moitie de la mesure** :
#: un banc qui ne jouerait que l'echec ne vaudrait pas mieux que celui qui ne
#: jouait que la reussite -- un produit qui refuserait TOUJOURS passerait l'un,
#: un produit qui accepterait TOUJOURS passait l'autre, et c'est exactement ce
#: qui a laisse vivre le mutant `|| true`.
REGIMES_DU_GESTE_PRIVILEGIE = (
    ((),              True,  True),
    (("installer",),  False, True),
    (("sudo",),       False, False),
)


@pytest.mark.parametrize("gestes_en_echec, doit_reussir, installer_lance",
                         REGIMES_DU_GESTE_PRIVILEGIE,
                         ids=["rien_ne_casse", "paquet_rejete", "mot_de_passe_refuse"])
def test_un_installeur_QUI_ECHOUE_ne_s_annonce_PAS_pose(tmp_path, gestes_en_echec,
                                                        doit_reussir, installer_lance):
    """Finding `C2-5` -- l'echec du SEUL geste privilegie du script.

    `sudo installer -pkg ... -target /` est la seule ligne de tout
    `install.sh` qui reclame un mot de passe administrateur, et son echec
    n'etait mesure NULLE PART : les factices `sudo` et `installer` rendaient
    toujours 0. Mutant qui survivait le 2026-09-08 -- `|| true` ajoute a la
    fin de cette ligne : le produit annoncait « Python 3.12.8 pose par
    l'installeur officiel » alors que rien n'avait ete installe, et les 116
    tests restaient verts.

    Ce n'est pas un cas de laboratoire : `docs/installation/macos.md` promet
    nommement le « refus de mot de passe » parmi les echecs qui donnent la
    commande de secours, et un mot de passe se refuse tous les jours.

    Trois verdicts, dont le troisieme distingue les deux causes que le produit
    ne peut PAS distinguer lui-meme (il ne voit qu'un code de sortie) :

    1. le produit n'annonce pas une pose qui n'a pas eu lieu ;
    2. il NOMME la panne puis donne la commande de secours python.org --
       jamais un blocage sec (`EPIC11-ARB-271`) ;
    3. `installer` est lance quand `sudo` passe, et ne l'est PAS quand le mot
       de passe est refuse. Sans ce troisieme point, un banc pourrait croire
       mesurer le refus de mot de passe en mesurant tout autre chose.
    """
    machine = machine_du_repli(tmp_path, avec_python=False,
                               gestes_en_echec=gestes_en_echec)
    sortie = sans_ansi(jouer_le_dialogue(
        ["--cli", "--sans-ffmpeg", "--sans-path", "--sans-raccourci",
         "--sans-verification", IGNORER_HORS_DU_PATH],
        # « 2 » : poser le binaire precompile. « 1 » : oui, je tape mon mot de
        # passe. Les memes deux reponses que le parcours nominal.
        ["2", "1"] + [""] * 6, machine["env"]))

    # « pose par l'installeur officiel » et non « l'installeur officiel » tout
    # court : cette derniere forme vit AUSSI dans la commande de secours, si
    # bien qu'une assertion negative dessus serait rouge sur le chemin d'echec
    # pour la mauvaise raison.
    annonce_de_pose = "pose par l'installeur officiel" in sortie
    assert annonce_de_pose is doit_reussir, (
        "gestes casses %r : le produit %s une pose de Python.\n%s"
        % (gestes_en_echec, "n'annonce pas" if doit_reussir else "annonce",
           sortie))

    assert machine["appels_installer"].exists() is installer_lance, (
        "gestes casses %r : `installer` %s ete lance, l'inverse de ce que ce "
        "regime reproduit.\n%s"
        % (gestes_en_echec, "n'a pas" if installer_lance else "a", sortie))

    if doit_reussir:
        trace = machine["appels_installer"].read_text()
        assert "sudo=1" in trace and "-target /" in trace, trace
        assert "l'installeur a echoue" not in sortie, sortie
    else:
        assert "l'installeur a echoue" in sortie, (
            "l'echec du geste privilegie ne NOMME pas sa panne : c'est "
            "l'echec muet qu'`EPIC11-ARB-271` interdit.\n" + sortie)
        assert "python.org/downloads" in sortie, (
            "l'echec du geste privilegie ne donne aucune commande de "
            "secours.\n" + sortie)


def test_un_condensat_FAUX_sur_le_paquet_PYTHON_n_installe_RIEN(tmp_path):
    """AC4 sur l'autre dependance : un paquet systeme installe `-target /`.

    Le risque n'est pas du meme ordre que pour ffmpeg -- ce paquet-la s'ecrit
    dans `/Library/Frameworks`, en root. Un condensat faux doit donc arreter
    AVANT le `sudo`, et pas seulement avant la pose.
    """
    machine = machine_du_repli(tmp_path, avec_python=False,
                               condensats_faux=("python",))
    brut = jouer_le_dialogue(
        ["--cli", "--sans-ffmpeg", "--sans-path", "--sans-raccourci",
         "--sans-verification", IGNORER_HORS_DU_PATH], ["2", "1"] + [""] * 6, machine["env"])
    sortie = sans_ansi(brut)

    assert "ne correspond pas" in sortie, sortie
    assert not machine["appels_installer"].exists(), (
        "un condensat faux n'a pas empeche `installer` de tourner en root.\n"
        + sortie)
    assert "python.org/downloads" in sortie, sortie


# ------------------- AC6 : aucun chemin d'echec ne se termine SANS commande

#: Les cinq fonctions ou le repli DECIDE d'echouer. Le perimetre est nomme
#: plutot que global : `installer_paquet_systeme` porte des `return 1` qui ne
#: sont pas des echecs de repli (Homebrew absent, pas de sudo), et les melanger
#: rendrait la frontiere fausse pour la mauvaise raison.
FONCTIONS_DU_REPLI = (
    "poser_un_membre_precompile",
    "repli_precompile_ffmpeg",
    "repli_precompile_python",
    "_poser_le_paquet_python",
    "repli_precompile",
)


#: Le CARDINAL des sorties en echec des cinq fonctions du repli, MESURE le
#: 2026-09-08 : vingt-trois.
#:
#: **Un plancher lache ne mesure pas le perimetre, il le laisse fondre**
#: (finding `C2-12`). Ce compte valait `>= 18` : il absorbait donc la
#: suppression de CINQ chemins d'echec sur vingt-trois -- c'est-a-dire que la
#: garde de non-vacuite du balayage acceptait de balayer 78 % du produit en
#: se declarant verte. Le precedent du depot est `PIRE_CAS_FACTURE_TOLERE`,
#: serre de 400 a 360 apres qu'un mutant eut survecu a l'ecart.
#:
#: Un compte EXACT plutot qu'un plancher, comme
#: `test_le_nombre_de_points_de_lecture_reste_petit_et_connu` : une sortie
#: ajoutee est une bonne nouvelle et elle se declare ici, dans le meme commit.
#: Ce qui se mesure se tient ; ce qui se rappelle se perd.
NOMBRE_DE_SORTIES_EN_ECHEC_DU_REPLI = 23


def corps_de_fonction(code: str, nom: str) -> list:
    """Les lignes d'une fonction shell, de sa signature a son `}` en colonne 0.

    Meme patron que `bloc_du_raccourci` : une frontiere qui balaie un
    perimetre doit pouvoir DIRE que ce perimetre existe encore, sinon elle
    devient verte en ne mesurant rien le jour ou le decoupage change.
    """
    lignes = code.splitlines()
    debuts = [i for i, ligne in enumerate(lignes) if ligne == "%s() {" % nom]
    assert len(debuts) == 1, (
        "install.sh ne definit plus `%s` comme ce banc l'attend (%d "
        "occurrence(s)) : c'est le DECOUPAGE qu'il faut reprendre ici, pas la "
        "mesure qu'il porte." % (nom, len(debuts)))
    for fin in range(debuts[0] + 1, len(lignes)):
        if lignes[fin] == "}":
            return lignes[debuts[0]:fin + 1]
    raise AssertionError("`%s` ne se referme jamais en colonne zero" % nom)


def test_AUCUN_chemin_d_echec_du_repli_ne_se_termine_SANS_commande():
    """AC6 -- la frontiere de BALAYAGE, et c'est celle que l'arbitrage exige.

    `EPIC11-ARB-271`, verbatim : « tout echec de ce repli -- URL morte, archive
    corrompue, refus de sudo, reseau coupe -- affiche la commande de secours.
    **Jamais un blocage sec, jamais un echec muet** ».

    Un test par chemin d'echec ne suffirait pas : il mesurerait les chemins
    qu'on a pense a ecrire, jamais celui qu'on ajoutera demain. Cette
    frontiere-ci balaie le CODE -- toute sortie en echec des cinq fonctions du
    repli nomme sa panne (`echec_du_repli`) ou donne la commande
    (`commande_de_secours`), sur la ligne meme.

    Les deux gardes de non-vacuite valent autant que l'assertion : sans elles,
    un decoupage qui rendrait zero ligne serait vert.
    """
    code = code_du_script(INSTALL_SH)
    lignes = [ligne for nom in FONCTIONS_DU_REPLI
              for ligne in corps_de_fonction(code, nom)]
    assert len(lignes) > 80, (
        "les cinq fonctions du repli ne font que %d lignes : ce n'est pas le "
        "perimetre que cette frontiere croit balayer" % len(lignes))

    sorties = [ligne.strip() for ligne in lignes if "return 1" in ligne]
    assert len(sorties) == NOMBRE_DE_SORTIES_EN_ECHEC_DU_REPLI, (
        "%d sorties en echec dans le repli, %d attendues. Une sortie EN MOINS "
        "et le balayage ne la verifie plus ; une sortie EN PLUS et ce compte "
        "se releve DELIBEREMENT, dans le commit qui l'ajoute -- c'est ce que "
        "l'ancien plancher `>= 18` ne demandait pas, et il absorbait la "
        "disparition de CINQ chemins sur vingt-trois sans rougir.\n%r"
        % (len(sorties), NOMBRE_DE_SORTIES_EN_ECHEC_DU_REPLI, sorties))

    muettes = [ligne for ligne in sorties
               if "echec_du_repli" not in ligne and "commande_de_secours" not in ligne]
    assert muettes == [], (
        "un chemin d'echec du repli sort SANS nommer sa panne ni donner de "
        "commande de secours -- c'est exactement l'echec muet que "
        "`EPIC11-ARB-271` interdit : %r" % (muettes,))


def test_echec_du_repli_DONNE_TOUJOURS_la_commande():
    """AC6 -- le maillon que la frontiere precedente suppose.

    Elle mesure que chaque sortie appelle `echec_du_repli` ; elle ne mesure pas
    que `echec_du_repli` fait quelque chose. Un mutant qui le viderait de son
    `commande_de_secours` la laisserait VERTE -- et vingt-trois chemins
    d'echec deviendraient muets d'un coup.
    """
    corps = corps_de_fonction(code_du_script(INSTALL_SH), "echec_du_repli")
    assert len(corps) >= 4, (
        "`echec_du_repli` ne fait que %d lignes" % len(corps))
    joint = "\n".join(corps)
    assert "alerte" in joint, "l'echec ne NOMME plus sa panne"
    assert "commande_de_secours" in joint, (
        "`echec_du_repli` n'affiche plus de commande de secours : les chemins "
        "d'echec du repli sont redevenus muets")


#: Les six lignes du tableau de l'AC6, et « la plus OFFICIELLE » n'est pas « la
#: plus pratique » : `brew install ffmpeg` plutot qu'un binaire tiers, le depot
#: RPM Fusion nomme pour Fedora, et le build que la page officielle FFmpeg
#: designe pour Windows.
COMMANDES_DE_SECOURS_ATTENDUES = (
    ("ffmpeg", "macOS", "brew install ffmpeg"),
    ("ffmpeg", "macOS", "https://ffmpeg.org/download.html"),
    ("ffmpeg", "Debian/Ubuntu", "sudo apt-get install ffmpeg"),
    ("ffmpeg", "Fedora/RHEL", "sudo dnf install ffmpeg"),
    ("ffmpeg", "Fedora/RHEL", "RPM Fusion"),
    ("python", "macOS", "https://www.python.org/downloads/"),
    ("python", "Linux", "paquet Python de votre distribution"),
)


def test_le_TABLEAU_des_commandes_de_secours_est_celui_de_l_arbitrage():
    """AC6 -- « La plus officielle et non la plus pratique ».

    Le tableau vit dans une SEULE fonction, `commande_de_secours`, et la
    frontiere le mesure la : un remede recopie a cinq endroits diverge, et
    c'est ce que le bloc d'origine faisait deja (l. 556-574 d'un cote,
    l. 1004-1010 de l'autre, avec deux formulations differentes pour ffmpeg).
    """
    corps = "\n".join(corps_de_fonction(code_du_script(INSTALL_SH),
                                        "commande_de_secours"))
    assert len(corps.splitlines()) >= 15, (
        "`commande_de_secours` a fondu : elle ne peut plus porter le tableau")
    for dependance, systeme, commande in COMMANDES_DE_SECOURS_ATTENDUES:
        assert commande in corps, (
            "la commande de secours de %s sur %s a disparu de install.sh : %r"
            % (dependance, systeme, commande))


def test_la_ligne_WINDOWS_du_tableau_vit_deja_dans_install_ps1():
    """AC6, septieme ligne -- mesuree la ou elle est, sans toucher a `install.ps1`.

    L'AC8 interdit nommement d'ecrire dans `install.ps1`, et l'AC6 demande la
    commande officielle de ffmpeg sur Windows. Les deux tiennent ensemble
    parce que la ligne EXISTE deja (`install.ps1:783`) : ce test la mesure en
    LECTURE, ce qui est ce que ce banc fait de `install.ps1` depuis toujours.

    Sans cette frontiere, la septieme ligne du tableau ne serait mesuree nulle
    part -- et disparaitrait un jour sans que personne le voie.
    """
    ps = code_du_script(INSTALL_PS1)
    assert "winget install --id Gyan.FFmpeg -e" in ps, (
        "la commande officielle de ffmpeg sur Windows a quitte install.ps1 : "
        "la septieme ligne du tableau de l'AC6 n'est plus mesuree nulle part")


# ------------------------------------- AC7 : TROIS issues, jamais une seule

def test_la_question_de_compilation_offre_TROIS_issues(tmp_path):
    """AC7 -- `EPIC11-ARB-89` : jamais une seule sortie, jamais un blocage sec.

    Elles etaient DEUX -- compiler, ou se debrouiller. Elles sont trois, et la
    troisieme est celle qui manquait : laisser le script faire le travail.
    """
    machine = machine_du_repli(tmp_path)
    # Dans un VRAI terminal, et pas en non-interactif : `demander` n'ENUMERE
    # ses options que quand quelqu'un peut y repondre -- sans terminal il
    # annonce le defaut et rien d'autre. Un test qui compterait les issues sur
    # une sortie non interactive en verrait UNE, toujours, quoi qu'on ecrive.
    brut = jouer_le_dialogue(
        ["--dry-run", "--cli", "--ffmpeg", "--sans-path", "--sans-raccourci",
         "--sans-verification"], [""] * 8, machine["env"])
    sortie = sans_ansi(brut)

    assert "Comment poser ffmpeg sans y passer des heures ?" in sortie, sortie
    for issue in ("compiler avec Homebrew maintenant",
                  "poser le binaire precompile officiel",
                  "ne rien poser : donne-moi la commande"):
        assert issue in sortie, (
            "une des trois issues a disparu de la question : %r\n%s"
            % (issue, sortie))
    # Le DEFAUT ne consomme ni des heures ni un mot de passe : c'est l'issue 2
    # qui porte le marqueur, et Entree seule la prend.
    assert "2) poser le binaire precompile officiel -- je m'en charge [defaut]" in sortie, (
        "le defaut n'est plus le repli precompile.\n" + sortie)


def test_l_issue_COMPILER_lance_REELLEMENT_Homebrew(tmp_path):
    """AC7, premiere issue -- « une ecriture destructive CONSCIENTE » reste
    possible, meme quand l'outil la deconseille.

    Sans ce test, un produit qui aurait purement SUPPRIME la voie Homebrew
    passerait tout le reste du lot : c'est la moitie de l'arbitrage
    `EPIC11-ARB-89` qui disparaitrait en silence.
    """
    machine = machine_du_repli(tmp_path)
    binaires = Path(machine["env"]["PATH"].split(os.pathsep)[0])
    trace = tmp_path / "appels_brew.txt"
    _deposer_outil(binaires, "brew",
                   "#!/bin/sh\necho \"brew $*\" >> '%s'\nexit 0\n" % trace)

    brut = jouer_le_dialogue(
        ["--cli", "--ffmpeg", "--sans-path", "--sans-raccourci",
         "--sans-verification"],
        ["1"] * 8, machine["env"])
    sortie = sans_ansi(brut)

    assert trace.exists(), (
        "l'issue « compiler » ne lance plus Homebrew.\n" + sortie)
    assert "install ffmpeg" in trace.read_text(), trace.read_text()
    assert not (machine["destination"] / "ffmpeg").exists(), (
        "l'issue « compiler » a quand meme pose le binaire precompile.\n"
        + sortie)


def test_l_issue_NE_RIEN_POSER_ne_pose_rien_ET_donne_la_commande(tmp_path):
    """AC7, troisieme issue -- et c'est `EPIC11-ARB-271` litteralement.

    Un refus qui n'offre aucune issue est aussi fautif qu'une destruction
    silencieuse. Le verdict porte sur les DEUX moities : rien n'est pose, ET
    la commande est donnee.
    """
    machine = machine_du_repli(tmp_path)
    brut = jouer_le_dialogue(
        ["--cli", "--ffmpeg", "--sans-path", "--sans-raccourci",
         "--sans-verification"],
        ["3"] * 8, machine["env"])
    sortie = sans_ansi(brut)

    assert not (machine["destination"] / "ffmpeg").exists(), (
        "l'issue « ne rien poser » a quand meme pose quelque chose.\n" + sortie)
    assert "brew install ffmpeg" in sortie, (
        "l'issue « ne rien poser » ne donne aucune commande : c'est le blocage "
        "sec que l'arbitrage interdit.\n" + sortie)


#: Les deux formes d'IMPASSE que la commande de secours ne doit JAMAIS rendre
#: sur une dependance que le script installe lui-meme.
#:
#: La premiere est HISTORIQUE : la branche par defaut de `commande_de_secours`
#: rendait « aucune commande officielle connue » jusqu'au 2026-09-08, ce qui
#: est litteralement le blocage sec qu'`EPIC11-ARB-89` interdit. Elle est
#: gardee ici pour qu'elle ne revienne pas -- une frontiere negative est le
#: seul moyen d'attraper la reintroduction d'un defaut. La seconde est la
#: forme d'aujourd'hui : legitime pour une dependance INCONNUE, fautive pour
#: une dependance que le script pose lui-meme.
FORMES_D_IMPASSE = (
    "aucune commande officielle connue",
    "n'a pas de commande officielle epinglee",
)

#: `installer_paquet_systeme "<formule>"`, la formule Homebrew en premier
#: argument. La definition (`installer_paquet_systeme() {`) ne correspond pas :
#: il faut une espace puis un guillemet.
FORMULE_INSTALLEE = re.compile(r'installer_paquet_systeme\s+"([^"]+)"')


def formules_passees_a_installer_paquet_systeme() -> list[str]:
    """Les noms de formule que `install.sh` passe REELLEMENT, lus dans le script.

    Extraits plutot que recopies : une formule ajoutee demain entre d'elle-meme
    dans le balayage, et le banc rougit tant qu'on ne lui a pas dit comment la
    jouer. Une liste recopiee, elle, derive sans que rien ne le dise -- c'est
    le defaut exact que `CLAUDE.md` nomme dans « les politiques de ce fichier
    se MESURENT ».
    """
    return FORMULE_INSTALLEE.findall(code_du_script(INSTALL_SH))


def alternatives_du_repli_precompile() -> list[str]:
    """Les motifs de formule auxquels `un_repli_precompile_existe` repond OUI."""
    for ligne in corps_de_fonction(code_du_script(INSTALL_SH),
                                   "un_repli_precompile_existe"):
        trouve = re.match(r"\s*([^)]+)\)\s*return 0", ligne)
        if trouve:
            return [motif.strip() for motif in trouve.group(1).split("|")]
    raise AssertionError(
        "`un_repli_precompile_existe` n'a plus de branche `return 0` : c'est "
        "le DECOUPAGE qu'il faut reprendre ici, pas la mesure qu'il porte.")


#: Comment JOUER l'issue 3 de chaque formule qui a un repli precompile, et ce
#: que la commande de secours doit alors contenir.
#:
#: **La collection compte DEUX elements distinguables, et la cible se place aux
#: DEUX bords** -- regle des fabriques, points 1, 2 et 4. C'est tout le sujet
#: du finding `C1-2`/`C2-4` : le banc ne jouait les issues 1 et 3 que sur
#: `ffmpeg`, si bien que la jambe PYTHON de la question a trois issues n'etait
#: JAMAIS jouee. Dans l'ordre ou `install.sh` les appelle, `python@3.12` est en
#: TETE et `ffmpeg` en QUEUE ; le balayage prend les deux.
#:
#: `dependance` est ce que `dependance_du_paquet` doit rendre : c'est la
#: DEPENDANCE et non la FORMULE -- `python@3.12` et `python@3.13` sont le meme
#: Python, et la commande de secours ne se choisit pas sur un numero de
#: version. Le produit l'affiche en toutes lettres (« La commande de secours
#: pour <dependance> »), ce qui rend la resolution MESURABLE de l'exterieur.
RECETTES_DE_L_ISSUE_TROIS = {
    "python@3.12": dict(
        fabrique=dict(avec_python=False),
        drapeaux=["--cli", "--sans-ffmpeg", "--sans-path", "--sans-raccourci",
                  "--sans-verification", IGNORER_HORS_DU_PATH],
        dependance="python",
        commande="https://www.python.org/downloads/",
    ),
    "ffmpeg": dict(
        fabrique=dict(),
        drapeaux=["--cli", "--ffmpeg", "--sans-path", "--sans-raccourci",
                  "--sans-verification"],
        dependance="ffmpeg",
        commande="brew install ffmpeg",
    ),
}

#: Les formules SANS repli precompile : la question a trois issues ne leur est
#: pas posee, donc aucune commande de secours ne leur est due. Refuser sur
#: `pipx` fait basculer l'installation sur `pip --user`, qui ne compile rien --
#: c'est ce que `test_pipx_ne_recoit_AUCUN_repli_precompile` mesure a la source.
FORMULES_SANS_REPLI_PRECOMPILE = ("pipx",)


def test_le_RECENSEMENT_des_formules_du_banc_est_celui_DU_SCRIPT():
    """La garde qui empeche le balayage ci-dessous de fondre en silence.

    Une formule ajoutee a `install.sh` sans recette ici ferait un balayage qui
    ne la joue pas -- et rien ne le dirait. C'est le meme motif que la garde de
    non-vacuite de `bloc_du_raccourci` : une frontiere qui perd son perimetre
    devient verte pour la pire des raisons.

    Le second volet verifie que le partage entre « avec repli » et « sans
    repli » est celui du PRODUIT et non une croyance du banc : les motifs sont
    lus dans `un_repli_precompile_existe`, qui est le seul endroit ou
    l'aiguillage se decide.
    """
    formules = formules_passees_a_installer_paquet_systeme()
    assert len(formules) >= 3, (
        "seulement %d formule(s) passee(s) a `installer_paquet_systeme` : "
        "l'extraction ne trouve plus ce qu'elle croit trouver -- c'est le "
        "DECOUPAGE qu'il faut reprendre, pas la mesure. %r"
        % (len(formules), formules))
    connues = set(RECETTES_DE_L_ISSUE_TROIS) | set(FORMULES_SANS_REPLI_PRECOMPILE)
    assert set(formules) == connues, (
        "le banc et le script ne recensent plus les memes formules.\n"
        "  script : %r\n  banc   : %r\n"
        "Une formule NEUVE se joue : lui ecrire sa recette d'issue 3, ou la "
        "declarer sans repli precompile -- jamais la laisser hors du balayage."
        % (sorted(formules), sorted(connues)))

    motifs = alternatives_du_repli_precompile()
    for formule in RECETTES_DE_L_ISSUE_TROIS:
        assert any(fnmatch.fnmatch(formule, motif) for motif in motifs), (
            "le banc joue l'issue 3 sur %r, mais `un_repli_precompile_existe` "
            "ne lui reconnait aucun repli (%r) : la question a trois issues ne "
            "lui est jamais posee." % (formule, motifs))
    for formule in FORMULES_SANS_REPLI_PRECOMPILE:
        assert not any(fnmatch.fnmatch(formule, motif) for motif in motifs), (
            "%r a gagne un repli precompile (%r) : il lui faut desormais une "
            "recette d'issue 3, sans quoi le balayage l'ignore." % (formule, motifs))


@pytest.mark.parametrize("formule", sorted(RECETTES_DE_L_ISSUE_TROIS))
def test_CHAQUE_formule_a_repli_rend_une_commande_de_secours_REELLE(tmp_path, formule):
    """Findings `C1-2` et `C2-4` -- le BALAYAGE, trouve par deux couches
    independantes.

    Le banc ne jouait les issues 1 et 3 que sur `ffmpeg` : la collection
    `{python@3.12, ffmpeg}` avait TOUJOURS sa cible en premiere position, ce
    qui est litteralement le point 2 de la regle des fabriques. La jambe
    PYTHON de la question a trois issues n'etait jamais jouee, et le mutant
    qui retire `python@*)` de `dependance_du_paquet` survivait.

    **Ce test appelle le SCRIPT, il ne relit pas sa source.** C'est la seule
    facon d'attraper « l'argument ne se resout pas » : une frontiere de texte
    verrait `commande_de_secours "$(dependance_du_paquet ...)"` et le
    declarerait conforme sans jamais savoir ce que cette substitution rend.
    `install.sh` s'EXECUTE de bout en bout -- son analyse d'arguments est en
    l. 152, avant meme la definition des deux fonctions --, donc un
    `source install.sh` puis un appel isole n'est pas possible : le parcours
    complet est le seul acces.

    Le verdict porte sur les DEUX moities d'`EPIC11-ARB-271` : rien n'est
    pose, ET une commande REELLE est donnee -- jamais une forme d'impasse.
    """
    recette = RECETTES_DE_L_ISSUE_TROIS[formule]
    machine = machine_du_repli(tmp_path, **recette["fabrique"])
    sortie = sans_ansi(jouer_le_dialogue(recette["drapeaux"], ["3"] * 8,
                                         machine["env"]))

    assert "Tres bien, rien n'est pose." in sortie, (
        "l'issue 3 n'a pas ete atteinte sur %r : ce test ne mesure pas ce "
        "qu'il croit.\n%s" % (formule, sortie))

    # LA RESOLUTION DE LA FORMULE EN DEPENDANCE, rendue visible par le produit
    # lui-meme. C'est le mutant du finding `C1-2` : sans `python@*)` dans
    # `dependance_du_paquet`, cette ligne annonce « pour python@3.12 » -- un
    # numero de version dans une commande de secours, la ou deux formules sont
    # le meme Python.
    assert ("La commande de secours pour %s, la plus officielle"
            % recette["dependance"]) in sortie, (
        "la formule %r ne se resout pas en la dependance %r : la commande de "
        "secours se choisit sur un numero de version.\n%s"
        % (formule, recette["dependance"], sortie))

    assert recette["commande"] in sortie, (
        "l'issue « ne rien poser » sur %r ne donne aucune commande reelle : "
        "c'est le blocage sec qu'`EPIC11-ARB-89` interdit.\n%s"
        % (formule, sortie))
    for impasse in FORMES_D_IMPASSE:
        assert impasse not in sortie, (
            "la formule %r tombe dans la branche d'impasse (%r) : le script "
            "installe cette dependance et ne sait pas dire comment la poser a "
            "la main.\n%s" % (formule, impasse, sortie))

    # Rien n'est pose, l'autre moitie du verdict -- sur les DEUX jambes a la
    # fois, puisqu'un refus ne doit rien ecrire nulle part.
    assert not (machine["destination"] / "ffmpeg").exists(), sortie
    assert not machine["appels_installer"].exists(), (
        "l'issue « ne rien poser » a lance l'installeur officiel.\n" + sortie)


def test_l_issue_NE_RIEN_POSER_sur_PYTHON_donne_l_INSTALLEUR_OFFICIEL(tmp_path):
    """Findings `C1-2`/`C2-4`, volet COMPORTEMENTAL -- le pendant PYTHON de
    `test_l_issue_NE_RIEN_POSER_ne_pose_rien_ET_donne_la_commande`.

    Le balayage ci-dessus dit qu'AUCUNE formule n'est oubliee ; celui-ci dit ce
    que la jambe Python rend precisement, et il le dit sur la voie la plus
    officielle de macOS -- l'installeur python.org, pas Homebrew, pas pyenv.

    Ce que sa disparition couterait : sur un Mac Intel sans bouteille, Python
    est INDISPENSABLE (`installer_paquet_systeme` echoue et le script rend
    `Echec : Python >= 3.11 est indispensable`). Un utilisateur qui refuse la
    compilation d'une heure part alors avec, pour tout viatique, « python@3.12
    n'a pas de commande officielle epinglee dans ce script » -- un refus sans
    issue, c'est-a-dire ce qu'`EPIC11-ARB-89` met sur le meme plan qu'une
    destruction silencieuse.
    """
    machine = machine_du_repli(tmp_path, avec_python=False)
    sortie = sans_ansi(jouer_le_dialogue(
        ["--cli", "--sans-ffmpeg", "--sans-path", "--sans-raccourci",
         "--sans-verification", IGNORER_HORS_DU_PATH], ["3"] * 8, machine["env"]))

    assert "Comment poser python@3.12 sans y passer des heures ?" in sortie, (
        "la question a trois issues ne se pose pas sur Python.\n" + sortie)
    assert "Tres bien, rien n'est pose." in sortie, sortie
    assert "l'installeur officiel python.org" in sortie, (
        "la jambe PYTHON de l'issue 3 ne nomme pas la voie la plus "
        "officielle.\n" + sortie)
    assert "https://www.python.org/downloads/" in sortie, sortie
    for impasse in FORMES_D_IMPASSE:
        assert impasse not in sortie, (
            "l'issue 3 sur Python rend une impasse (%r).\n%s" % (impasse, sortie))

    assert not machine["appels_installer"].exists(), (
        "« ne rien poser » a quand meme lance l'installeur officiel.\n" + sortie)


def test_pipx_ne_recoit_AUCUN_repli_precompile():
    """AC8 -- la portee est BORNEE, et le cas `pipx` ne change pas.

    Refuser sur `pipx` fait basculer l'installation sur `pip --user`, qui ne
    compile rien : lui inventer une URL serait un engagement de maintenance
    pour rien (AC12). La frontiere porte sur l'aiguillage, a UN seul endroit,
    pour que la question posee et le repli reellement disponible ne puissent
    pas diverger.
    """
    corps = "\n".join(corps_de_fonction(code_du_script(INSTALL_SH),
                                        "un_repli_precompile_existe"))
    assert "ffmpeg" in corps and "python@" in corps, corps
    assert "pipx" not in corps, (
        "un repli precompile a ete ouvert a pipx : chaque URL de plus est un "
        "engagement de maintenance que personne n'a signe.\n" + corps)


# --------- AC8 : frontiere NEGATIVE, aucune URL precompilee dans install.ps1

#: Ce qui n'a RIEN a faire dans `install.ps1`. Rien du comportement Windows
#: n'est mesure dans ce depot -- `install.ps1:869-873` le declare lui-meme --
#: et il n'y existe aujourd'hui aucune garde de compilation. Un repli
#: precompile pose la serait du code jamais joue, jamais mesure, et qui
#: telecharge des binaires.
JETONS_DE_REPLI_INTERDITS_PS = (
    "evermeet.cx",
    "python.org/ftp/",
    "-macos11.pkg",
    "com.apple.quarantine",
)


def test_AUCUNE_url_de_binaire_precompile_n_entre_dans_install_ps1():
    """AC8 -- frontiere NEGATIVE, et son pendant positif.

    Une frontiere negative seule serait verte AVANT que la story n'ecrive une
    ligne -- verte pour la pire des raisons. Le pendant : `install.ps1` porte
    toujours sa voie officielle a lui (winget), et il fait toujours sa taille.
    """
    ps = code_du_script(INSTALL_PS1)
    assert len(ps.splitlines()) > 400, (
        "install.ps1 rendu fait %d lignes de code : ce n'est pas le fichier "
        "que cette frontiere croit mesurer" % len(ps.splitlines()))
    assert "winget install --id Python.Python.3.12" in ps or "Python.Python.3.12" in ps, (
        "install.ps1 a perdu sa voie officielle Windows : la frontiere "
        "negative ci-dessous serait verte sur un fichier vide")

    fautifs = [jeton for jeton in JETONS_DE_REPLI_INTERDITS_PS if jeton in ps]
    assert fautifs == [], (
        "un repli precompile est entre dans install.ps1, que l'AC8 exclut "
        "nommement : %r" % (fautifs,))


def test_le_repli_precompile_ne_touche_QUE_macOS(tmp_path):
    """AC8 -- « Linux garde ses gestionnaires de paquets, qui ne compilent pas ».

    La porte du repli est `homebrew_compile_depuis_les_sources`, qui exige
    `GESTIONNAIRE = brew`. Un Linux ordinaire ne doit donc voir NI la question
    a trois issues, NI une URL d'archive precompilee.
    """
    machine = _fabriquer_machine(tmp_path, avec_ffmpeg=False,
                                 liste_pipx="", avec_affichage=False)
    code, brut = jouer_sans_terminal(
        ["--dry-run", "--non-interactif", "--cli", "--sans-path",
         "--sans-raccourci", "--sans-verification"], machine)
    sortie = sans_ansi(brut)

    assert code == 0, sortie
    assert "evermeet.cx" not in sortie, (
        "un Linux se voit proposer le repli precompile macOS.\n" + sortie)
    assert "Comment poser" not in sortie, sortie


# ------------------------- AC9 : chaque drapeau joue dans les DEUX sens

def test_un_RESEAU_COUPE_nomme_la_panne_et_donne_la_commande(tmp_path):
    """AC6/AC9 -- « URL morte, reseau coupe », le chemin le plus probable.

    Le `curl` de cette machine rend 6 -- `Could not resolve host` --, ce qui
    est ce qu'un reseau coupe produit vraiment. C'est aussi ce que rendra une
    URL epinglee qui aurait disparu, et c'est la reponse de l'AC12 a « qu'est-ce
    qui rougit quand la version epinglee disparait ? » : rien ne rougit ici, le
    repli DEGRADE proprement chez l'utilisateur.
    """
    machine = machine_du_repli(tmp_path, absents_du_depot=("ffmpeg", "ffprobe"))
    code, sortie = jouer_le_repli(machine)

    assert code == 0, (
        "ffmpeg est FACULTATIF (`EPIC11-ARB-270`) : un repli qui echoue ne "
        "doit pas arreter l'installation.\n" + sortie)
    assert "le telechargement de ffmpeg a echoue" in sortie, sortie
    assert "brew install ffmpeg" in sortie, (
        "un reseau coupe ne donne aucune commande de secours.\n" + sortie)
    assert not (machine["destination"] / "ffmpeg").exists(), sortie


@pytest.mark.parametrize("manquant, morceau_du_message", [
    ("curl", "curl est absent"),
    ("unzip", "unzip est absent"),
    ("mktemp", "repertoire de travail temporaire"),
])
def test_un_OUTIL_manquant_nomme_lequel_et_donne_la_commande(
        tmp_path, manquant, morceau_du_message):
    """AC6/AC9/AC11 -- les outils du repli varient dans les deux sens.

    Le sens « present » est joue par tout le reste du lot. Celui-ci joue
    l'absence, un outil a la fois : `curl`, `unzip` et `mktemp` ne sont
    garantis sur aucune machine, et un `command -v` qui echoue doit rendre une
    panne NOMMEE plutot qu'un `127: command not found` sous `set -euo pipefail`
    -- qui tuerait l'installateur au lieu de degrader.
    """
    machine = machine_du_repli(tmp_path, sans_outils=(manquant,))
    code, sortie = jouer_le_repli(machine)

    assert code == 0, (
        "l'absence de %s a TUE l'installation au lieu de degrader.\n%s"
        % (manquant, sortie))
    assert "Termine" in sortie, sortie
    assert morceau_du_message in sortie, (
        "l'absence de %s n'est pas nommee.\n%s" % (manquant, sortie))
    assert "brew install ffmpeg" in sortie, (
        "l'absence de %s ne donne aucune commande de secours.\n%s"
        % (manquant, sortie))


def test_SANS_aucun_calculateur_de_condensat_le_repli_refuse_de_commencer(tmp_path):
    """AC4/AC9 -- « un repli qui ne peut pas verifier ne doit pas commencer ».

    Les DEUX familles retirees ensemble : macOS livre `shasum` et pas
    `sha256sum`, les Linux livrent l'inverse, et un produit qui n'en lirait
    qu'une casserait sur l'autre moitie du parc. Le refus intervient AVANT le
    telechargement -- 52 Mo qu'on ne pourrait de toute facon pas verifier.
    """
    machine = machine_du_repli(tmp_path, sans_outils=("shasum", "sha256sum"))
    code, sortie = jouer_le_repli(machine)

    assert "ni shasum ni sha256sum" in sortie, sortie
    assert "brew install ffmpeg" in sortie, sortie
    assert "Telechargement de ffmpeg" not in sortie, (
        "le repli a telecharge avant de constater qu'il ne pourrait pas "
        "verifier.\n" + sortie)


def test_le_repli_sait_lire_sha256sum_quand_shasum_MANQUE(tmp_path):
    """AC9 -- le second sens du meme drapeau, et il vaut mieux que sa moitie.

    `shasum` est l'outil de macOS ; `sha256sum` celui des Linux. Le produit lit
    les deux, et sans ce test le second bras ne serait jamais joue -- une
    branche de code vivante que rien ne mesure.
    """
    machine = machine_du_repli(tmp_path, sans_outils=("shasum",))
    code, sortie = jouer_le_repli(machine)

    assert code == 0, sortie
    assert (machine["destination"] / "ffmpeg").is_file(), (
        "sans `shasum`, le repli n'a pas su employer `sha256sum`.\n" + sortie)
    assert "condensat SHA-256 de ffmpeg verifie" in sortie, sortie


def test_une_DESTINATION_INCREABLE_nomme_la_panne(tmp_path):
    """AC6 -- le chemin d'echec qu'on n'anticipe pas, et qui arrive quand meme.

    Un `PIPX_BIN_DIR` inutilisable ferait echouer `mv` bien apres le
    telechargement, sur un message de `mv`. La garde repond AVANT et nomme le
    repertoire.

    **La panne est fabriquee par un FICHIER en travers du chemin, et pas par
    des droits** : ce banc tourne en root dans le conteneur, ou `chmod 500` ne
    protege rien (`[ -w ]` rend VRAI pour root, `mkdir` reussit). Une frontiere
    posee sur les droits serait donc verte EN NE VOYANT RIEN ici, et rouge
    ailleurs -- le pire des deux. `ENOTDIR` ne se negocie avec personne, pas
    meme avec root.
    """
    obstacle = tmp_path / "un_fichier_en_travers"
    obstacle.write_text("je ne suis pas un repertoire\n")
    machine = machine_du_repli(tmp_path, pipx_bin_dir=str(obstacle / "bin"))
    code, sortie = jouer_le_repli(machine)

    assert code == 0, sortie
    assert "n'a pas pu etre cree" in sortie, (
        "une destination inutilisable n'est pas nommee.\n" + sortie)
    assert "brew install ffmpeg" in sortie, sortie
    assert "Telechargement de ffmpeg" not in sortie, (
        "le repli a telecharge avant de savoir ou deposer.\n" + sortie)


@pytest.mark.skipif(os.geteuid() == 0,
                    reason="en root, `[ -w ]` rend VRAI sur un repertoire en "
                           "lecture seule : le bras mesure ici ne serait pas "
                           "celui qu'on croit")
def test_une_DESTINATION_NON_INSCRIPTIBLE_nomme_la_panne(tmp_path):
    """Le SECOND bras de la meme garde, et il ne se mesure pas en root.

    `mkdir -p` reussit -- le repertoire existe deja --, et c'est `[ -w ]` qui
    doit refuser. Les deux bras ne sont pas redondants : un produit qui
    n'aurait que le `mkdir` poserait le fichier a travers un `mv` en echec, et
    un produit qui n'aurait que le `-w` casserait sur un chemin absent.

    Le saut est STRUCTUREL et non un drapeau qu'on oublie de rallumer : sous
    l'uid 0, ce regime n'existe simplement pas.
    """
    interdit = tmp_path / "interdit"
    interdit.mkdir()
    interdit.chmod(0o500)
    try:
        machine = machine_du_repli(tmp_path, pipx_bin_dir=str(interdit))
        code, sortie = jouer_le_repli(machine)
        assert code == 0, sortie
        assert "n'est pas inscriptible" in sortie, (
            "une destination en lecture seule n'est pas nommee.\n" + sortie)
        assert "brew install ffmpeg" in sortie, sortie
    finally:
        interdit.chmod(0o700)


def test_le_repli_reussi_met_ffmpeg_sur_le_PATH_du_PROCESSUS(tmp_path):
    """Le defaut d'Egan, ferme jusqu'au bout -- verbatim : « l'outil n'est pas
    forcement ajoute au path et donc pas forcement detecte ».

    Poser le binaire ne suffit pas : le controle qui SUIT l'etape ffmpeg fait
    `command -v ffmpeg`, et il tournerait dans le PATH d'avant. Le repli
    exporterait le repertoire pour rien si le bilan continuait d'annoncer
    ffmpeg absent -- l'outil serait pose ET declare manquant dans la meme
    execution, ce qui est le defaut d'origine avec une etape de plus.

    Le verdict porte donc sur ce que le SCRIPT dit avoir trouve, et pas
    seulement sur le fichier.
    """
    machine = machine_du_repli(tmp_path)
    code, sortie = jouer_le_repli(machine)

    assert code == 0, sortie
    assert "ffmpeg version 9.0.1-factice" in sortie, (
        "le script n'a pas detecte le ffmpeg qu'il vient de poser : il est "
        "pose sans etre sur le PATH du processus.\n" + sortie)
    # Le litteral est CELUI du message d'echec de l'etape ffmpeg, pas la
    # sous-chaine « reste introuvable » : le bilan final porte « Si une
    # commande reste introuvable, ouvrir un NOUVEAU terminal », et une
    # frontiere qui l'attraperait rougirait sur un produit juste.
    assert "ffmpeg ou ffprobe reste introuvable" not in sortie, (
        "le script annonce ffmpeg introuvable APRES l'avoir pose.\n" + sortie)


# ============================================================================
#  Story 8.12 -- le RECU, les TROIS issues, et ce que la mise a jour NE touche PAS
#  `EPIC11-ARB-274` et `EPIC11-ARB-277`.
#
#  TOUT CE QUI SUIT SE MESURE SUR L'ETAT DE LA MACHINE (AC12) : un fichier
#  present ou absent, un binaire retire ou non. Les bancs de message existent
#  en plus, jamais a la place -- c'est la lecon de la 8.10, ou « abandonner »
#  etait mesure comme une phrase.
# ============================================================================

def _recu_fichier(env: dict) -> Path:
    """Le chemin que le SCRIPT emploie pour le recu, jamais celui qu'on lui prete.

    Meme geste que `_fichier_raccourci`, et pour le meme motif : coder
    `HOME/.local/state` en dur rendrait cette fonction fausse des que
    `XDG_STATE_HOME` est pose, et une assertion `not ...exists()` portant sur un
    chemin ou le script n'ecrit pas est VERTE sans rien mesurer.
    """
    racine = env.get("XDG_STATE_HOME", "")
    if not racine.startswith("/"):
        # Un `XDG_STATE_HOME` RELATIF est invalide au sens du spec, et le
        # script retombe alors sur le defaut : le banc suit la meme regle.
        racine = str(Path(env["HOME"]) / ".local" / "state")
    return Path(racine) / "mmu" / "pose-par-installeur.txt"


def _lignes_du_recu(env: dict) -> list:
    """Le recu relu comme le produit le relit : trois champs par tabulation."""
    cible = _recu_fichier(env)
    if not cible.exists():
        return []
    return [ligne.split("\t") for ligne in cible.read_text().splitlines() if ligne]


def _ecrire_un_recu(env: dict, entrees) -> Path:
    """Ecrit un recu de reference, et c'est une FABRIQUE au sens de la regle.

    Elle prend une LISTE ORDONNEE : c'est l'ordre qui fait la mesure. Un
    balayage tronque -- qui sauterait la derniere entree -- ne se demasque que
    si la cible se place tantot en tete, tantot en queue (regle des fabriques,
    point 4, posee le 2026-09-03 sur un mutant survivant du lot A de la 11.11).

    Elle ecrit le fichier DIRECTEMENT plutot que de le faire produire par une
    installation, et c'est voulu : l'AC4 dit qu'un recu peut venir d'ailleurs
    -- d'une version anterieure, d'un fichier a moitie efface --, et le
    desinstalleur doit le relire sans jamais lui faire confiance.
    """
    cible = _recu_fichier(env)
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(
        "".join("%s\t%s\t%s\n" % (nature, chemin, date)
                for nature, chemin, date in entrees))
    return cible


#: Les deux ORDRES du recu de reference. Les DEUX portent le meme ensemble
#: d'entrees -- donc le meme etat de machine attendu -- et ne different que par
#: la place des cibles retirables : `ffmpeg` en tete dans l'un, en queue dans
#: l'autre. Quatre entrees, TROIS natures distinguables, et une entree dont le
#: chemin a disparu (AC3, AC10).
ORDRES_DU_RECU = ("cible_en_tete", "cible_en_queue")


def _machine_avec_un_recu(tmp_path, machine, *, ordre):
    """Une maison neuve, trois objets sur le disque, et un recu qui en nomme deux.

    Le TEMOIN est la moitie negative de l'AC3 : un binaire present sur le
    disque et ABSENT du recu ne doit JAMAIS etre touche. Sans lui, un
    desinstalleur qui balaierait le repertoire entier serait vert.

    Le cadre Python est un REPERTOIRE qui existe : sans cela, `lire_le_recu`
    l'ecarterait comme « deja disparu » et la politique de l'AC6 -- « une
    entree python ne devient jamais un retrait » -- ne serait jamais atteinte.
    Une frontiere qu'on n'atteint pas est verte en ne mesurant rien.
    """
    env = _maison_neuve(tmp_path, machine, avec_commande_tui=True)
    binaires = Path(env["HOME"]) / ".local" / "bin"
    binaires.mkdir(parents=True, exist_ok=True)
    poses = {}
    for nom in ("ffmpeg", "ffprobe", "temoin"):
        chemin = binaires / nom
        chemin.write_text("#!/bin/sh\nexit 0\n")
        chemin.chmod(0o755)
        poses[nom] = chemin
    cadre_python = Path(env["HOME"]) / "Python.framework"
    cadre_python.mkdir()
    poses["python"] = cadre_python
    disparu = binaires / "jamais-pose"
    poses["disparu"] = disparu

    entrees = [
        ("ffmpeg", str(poses["ffmpeg"]), "2026-09-08T01:00:00Z"),
        ("python", str(cadre_python), "2026-09-08T01:00:01Z"),
        ("ffmpeg", str(disparu), "2026-09-08T01:00:02Z"),
        ("ffprobe", str(poses["ffprobe"]), "2026-09-08T01:00:03Z"),
    ]
    if ordre == "cible_en_queue":
        entrees.reverse()
    _ecrire_un_recu(env, entrees)
    return env, poses


def _desinstaller_avec_l_issue(env, issue, drapeaux=None, tmp_path=None):
    """Joue `--desinstaller` dans un VRAI terminal et repond a la question.

    Le `cwd` est JETABLE, pour le motif que `jouer_le_dialogue` documente : le
    repertoire courant du banc est la racine du depot.
    """
    courant = Path(env["HOME"]) / "repertoire_courant_jetable"
    courant.mkdir(exist_ok=True)
    arguments = ["--desinstaller"] + list(drapeaux or [])
    return sans_ansi(jouer_le_dialogue(arguments, [str(issue)], env, cwd=courant))


# ------------------------------------------------- AC2 : le recu, cote POSE

def test_le_repli_precompile_ECRIT_un_recu_APRES_avoir_pose(tmp_path):
    """AC2 -- et le verdict se lit sur le FICHIER, pas sur un message.

    DEUX entrees distinguables, `ffmpeg` et `ffprobe`, parce que ce sont deux
    objets : un retrait qui n'en connaitrait qu'un laisserait l'autre sur le
    disque a jamais. C'est la regle des fabriques, point 1, appliquee la ou
    l'ecriture a lieu et pas seulement a la relecture.

    Et les chemins notes sont ceux de la DESTINATION QUE PIPX EXPOSE : le recu
    ne devine pas plus la destination que le repli ne l'a devinee a l'aller.
    """
    ailleurs = tmp_path / "bin_de_pipx"
    machine = machine_du_repli(tmp_path, pipx_bin_dir=str(ailleurs))
    code, sortie = jouer_le_repli(machine)
    assert code == 0, sortie
    assert (machine["destination"] / "ffmpeg").exists(), sortie

    lignes = _lignes_du_recu(machine["env"])
    natures = [ligne[0] for ligne in lignes]
    assert natures == ["ffmpeg", "ffprobe"], (
        "le recu doit porter les DEUX binaires, distinguables :\n%r\n%s"
        % (lignes, sortie))
    chemins = [ligne[1] for ligne in lignes]
    assert chemins == [str(ailleurs / "ffmpeg"), str(ailleurs / "ffprobe")], (
        "le recu note un chemin DEVINE au lieu de celui que pipx expose :\n%r"
        % (chemins,))
    for ligne in lignes:
        assert len(ligne) == 3, ("trois champs par ligne : %r" % (ligne,))
        assert ligne[1].startswith("/"), ("chemin non absolu : %r" % (ligne,))
        assert ligne[2].endswith("Z"), ("date manquante : %r" % (ligne,))


def test_un_repli_qui_ECHOUE_n_ecrit_AUCUN_recu(tmp_path):
    """AC2, l'AUTRE sens -- « apres la reussite, jamais avant ».

    C'est le piege exact que ce chemin porte : `repli_precompile_ffmpeg` RETIRE
    le `ffmpeg` deja pose quand `ffprobe` echoue (finding `C1-1` de la revue
    8.11). Un recu ecrit d'avance nommerait donc un fichier que le produit
    vient lui-meme de retirer, et l'issue 2 le chercherait a jamais.

    La cible est en QUEUE -- c'est `ffprobe`, le second membre, qui echoue :
    un recu ecrit membre par membre resterait vert si seul le premier cassait.
    """
    machine = machine_du_repli(tmp_path, condensats_faux=("ffprobe",))
    code, sortie = jouer_le_repli(machine)
    assert code == 0, sortie
    assert not (machine["destination"] / "ffmpeg").exists(), (
        "le produit a bien retire ce qu'il avait pose :\n%s" % sortie)
    assert _lignes_du_recu(machine["env"]) == [], (
        "un recu a ete ecrit pour des binaires que le produit a retires :\n%s"
        % sortie)
    assert not _recu_fichier(machine["env"]).exists(), sortie


def test_le_recu_n_est_ECRIT_pour_pipx_QUE_si_CE_script_l_a_pose(tmp_path):
    """AC2 + AC9 -- le drapeau « pipx deja la / pose par nous » dans les deux sens.

    Quand pipx est deja present, ce script ne l'a pas pose et n'a donc rien a
    reprendre : aucune ligne. Quand il l'installe, la ligne porte la VOIE dans
    sa nature, parce que c'est elle qui decidera du retrait.
    """
    # Sens 1 : pipx est deja la (machine du repli ordinaire, pipx factice).
    (tmp_path / "avec_pipx").mkdir()
    machine = machine_du_repli(tmp_path / "avec_pipx")
    code, sortie = jouer_le_repli(machine)
    assert code == 0, sortie
    natures = [ligne[0] for ligne in _lignes_du_recu(machine["env"])]
    assert not [n for n in natures if n.startswith("pipx")], (
        "pipx etait deja la : rien ne devait etre note :\n%r" % (natures,))

    # Sens 2 : le PLAN d'une machine SANS pipx annonce la note, avec sa voie.
    (tmp_path / "sans_pipx").mkdir()
    sans = _fabriquer_machine(tmp_path / "sans_pipx", avec_ffmpeg=True,
                              liste_pipx="", avec_affichage=False,
                              avec_pipx=False)
    # `IGNORER_HORS_DU_PATH` : sans lui, une machine fabriquee « sans pipx »
    # trouve le `pipx` REEL du conteneur -- les runners GitHub en portent un
    # dans `/usr/local/bin`, premier emplacement de la liste bornee --, et le
    # produit prend la branche « pose hors du PATH » au lieu de poser. Mesure
    # de la premiere CI publique : dix-huit rouges de cette famille.
    _, brut = jouer_sans_terminal(
        ["--dry-run", "--cli", "--sans-path", "--sans-verification",
         IGNORER_HORS_DU_PATH], sans,
        cwd=tmp_path)
    plan = sans_ansi(brut)
    assert "noter pipx-" in plan, (
        "la pose de pipx ne dit pas qu'elle sera notee :\n%s" % plan)


# ------------------------------- AC3 + AC7 + AC10 : le recu, cote RETRAIT

@pytest.mark.parametrize("ordre", ORDRES_DU_RECU)
def test_l_issue_2_retire_CE_QUE_LE_RECU_DESIGNE_et_rien_d_autre(
        tmp_path, machine_avec_affichage, ordre):
    """AC3, AC7, AC10 -- et le verdict est l'ETAT DE LA MACHINE.

    Trois assertions qui ne disent pas la meme chose :

    * ce que le recu designe ET qui existe PART -- `ffmpeg` et `ffprobe` ;
    * ce que le recu NE designe PAS reste -- le temoin. Un desinstalleur qui
      balaierait le repertoire serait vert sans lui ;
    * ce que le recu designe mais qui a DISPARU est dit et saute, sans faire
      echouer quoi que ce soit.

    Les deux ORDRES portent le meme ensemble : seule la place des cibles
    change. Un balayage qui sauterait la derniere entree passerait l'un et
    echouerait sur l'autre -- c'est le seul moyen de le voir.
    """
    env, poses = _machine_avec_un_recu(tmp_path, machine_avec_affichage, ordre=ordre)
    sortie = _desinstaller_avec_l_issue(env, 2)

    assert not poses["ffmpeg"].exists(), (
        "%s designe par le recu a survecu (%s) :\n%s" % ("ffmpeg", ordre, sortie))
    assert not poses["ffprobe"].exists(), (
        "%s designe par le recu a survecu (%s) :\n%s" % ("ffprobe", ordre, sortie))
    assert poses["temoin"].exists(), (
        "un binaire ABSENT du recu a ete retire -- le desinstalleur balaie au "
        "lieu de lire :\n%s" % sortie)
    assert "deja disparu, rien a retirer" in sortie, (
        "une entree disparue doit etre DITE, pas tue :\n%s" % sortie)
    assert str(poses["disparu"]) in sortie, sortie
    assert "Termine" in sortie, sortie


def test_l_annonce_de_l_issue_2_est_EXACTEMENT_ce_qui_part(tmp_path,
                                                           machine_avec_affichage):
    """AC7 -- l'annonce et le retrait sont le MEME ensemble, mesure des deux cotes.

    Un desinstalleur qui annoncerait plus qu'il ne retire ment ; un qui retire
    plus qu'il n'annonce est pire. On compare donc l'ensemble des chemins
    ANNONCES a l'ensemble des chemins qui ont REELLEMENT disparu -- et non le
    texte a lui-meme.
    """
    env, poses = _machine_avec_un_recu(tmp_path, machine_avec_affichage,
                                       ordre="cible_en_tete")
    avant = {nom: chemin for nom, chemin in poses.items() if chemin.exists()}
    sortie = _desinstaller_avec_l_issue(env, 2)

    # L'annonce vient AVANT le premier retrait : le bloc « Vont etre retires »
    # precede la premiere ligne « Retire : ».
    assert "Vont etre retires" in sortie, sortie
    assert sortie.index("Vont etre retires") < sortie.index("ok Retire :"), (
        "le retrait a commence avant l'annonce :\n%s" % sortie)

    annonces = {nom for nom, chemin in avant.items()
                if "  %s (" % chemin in sortie}
    disparus = {nom for nom, chemin in avant.items() if not chemin.exists()}
    assert annonces == disparus | {"python"}, (
        "l'annonce et le retrait ne recouvrent pas le meme ensemble.\n"
        "annonce : %r\ndisparu : %r\n%s" % (sorted(annonces), sorted(disparus), sortie))
    # ... et Python est annonce SANS partir, ce que l'annonce dit en toutes lettres.
    assert "NON retire" in sortie, sortie


def test_l_issue_2_en_SIMULATION_n_affirme_AUCUN_retrait(tmp_path,
                                                         machine_avec_affichage):
    """`C1-7` / `C2-6`, applique au retrait NEUF de cette story.

    `succes` affirme une action PASSEE ; en `--dry-run` elle n'a pas eu lieu.
    Le defaut a deja ete paye sur le raccourci de la 8.8 -- bash affirmait
    « Raccourci retire » sur un fichier toujours present. Toute annonce de
    retrait neuve se place donc sous le `else` de la simulation.
    """
    env, poses = _machine_avec_un_recu(tmp_path, machine_avec_affichage,
                                       ordre="cible_en_tete")
    sortie = _desinstaller_avec_l_issue(env, 2, drapeaux=["--dry-run"])

    assert poses["ffmpeg"].exists(), (
        "un --dry-run a retire un fichier :\n%s" % sortie)
    assert _recu_fichier(env).exists(), (
        "un --dry-run a retire le recu :\n%s" % sortie)
    assert "[simulation] rm -f" in sortie, sortie
    assert "[simulation] rm -rf" in sortie, sortie
    assert "ok Retire :" not in sortie, (
        "la simulation affirme un retrait qui n'a pas eu lieu :\n%s" % sortie)
    assert "ok Recu retire" not in sortie, sortie


# ---------------------------------------- AC4 : un recu absent DEGRADE

def test_un_recu_ABSENT_degrade_en_issue_1_au_lieu_de_BLOQUER(tmp_path,
                                                              machine_avec_affichage):
    """AC4 -- « Un recu absent n'est pas une erreur » (`EPIC11-ARB-274`).

    C'est le cas d'une installation anterieure a ce mecanisme, ou d'un recu
    efface. Jamais un blocage sec (`EPIC11-ARB-89`) : l'issue 2 se rabat sur
    l'issue 1 EN LE DISANT, et elle renvoie a l'issue 3 pour le reste.

    Le verdict se lit sur l'etat : le temoin et les binaires sont TOUS encore
    la, parce qu'il n'y avait rien qui dise qu'on les avait poses.
    """
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=True)
    binaires = Path(env["HOME"]) / ".local" / "bin"
    intact = binaires / "ffmpeg"
    intact.write_text("#!/bin/sh\nexit 0\n")
    intact.chmod(0o755)
    assert not _recu_fichier(env).exists(), "ce banc part d'un recu ABSENT"

    sortie = _desinstaller_avec_l_issue(env, 2)
    assert "Aucun recu" in sortie, sortie
    assert "Je me rabats sur l'issue 1" in sortie, sortie
    assert "choisir 3" in sortie, (
        "la degradation doit renvoyer a l'issue 3, qui reste entiere :\n%s" % sortie)
    assert intact.exists(), (
        "sans recu, le desinstalleur a retire un binaire dont il ne savait "
        "RIEN :\n%s" % sortie)
    assert "Termine" in sortie, sortie


# ------------------------------------- AC5 : le recu se retire LUI-MEME

@pytest.mark.parametrize("issue", (1, 2))
def test_le_recu_se_retire_LUI_MEME_par_les_DEUX_issues(tmp_path,
                                                        machine_avec_affichage, issue):
    """AC5 -- une story qui ajoute un fichier et l'oublie au retrait ajoute la
    fuite qu'elle pretend fermer.

    Les DEUX issues qui retirent quelque chose le retirent : le drapeau joue
    dans les deux sens, et l'issue 1 -- celle qui ne lit meme pas le recu --
    est la plus facile a oublier.

    Le verdict est le REPERTOIRE, pas le message : c'est ce que l'AC5 demande
    mot pour mot.
    """
    env, _poses = _machine_avec_un_recu(tmp_path, machine_avec_affichage,
                                        ordre="cible_en_tete")
    dossier = _recu_fichier(env).parent
    assert dossier.is_dir(), "ce banc part d'un recu PRESENT"

    sortie = _desinstaller_avec_l_issue(env, issue)
    assert not dossier.exists(), (
        "l'issue %d a laisse le repertoire d'etat derriere elle :\n%s"
        % (issue, sortie))
    # ... et le repertoire d'etat de l'utilisateur, lui, survit : on ne retire
    # que le sous-repertoire `mmu`, jamais la racine qui porte l'etat de tout
    # le monde.
    assert dossier.parent.exists(), (
        "le retrait a emporte la RACINE d'etat, pas seulement `mmu` :\n%s" % sortie)


def test_l_issue_1_ne_retire_JAMAIS_ce_que_le_recu_designe(tmp_path,
                                                           machine_avec_affichage):
    """AC1 + AC5, l'autre sens de l'issue -- « le defaut ne peut rien casser ».

    L'issue 1 retire son propre recu (AC5) mais AUCUN des objets qu'il nomme.
    Sans ce banc, un desinstalleur qui retirerait toujours tout serait vert sur
    l'issue 2 et personne ne verrait que le defaut est devenu destructif.
    """
    env, poses = _machine_avec_un_recu(tmp_path, machine_avec_affichage,
                                       ordre="cible_en_queue")
    sortie = _desinstaller_avec_l_issue(env, 1)
    for nom in ("ffmpeg", "ffprobe", "temoin", "python"):
        assert poses[nom].exists(), (
            "l'issue 1 a retire %s : le DEFAUT est devenu destructif :\n%s"
            % (nom, sortie))
    assert "Ni Python, ni ffmpeg, ni pipx ne sont touches" in sortie, sortie


def test_le_mode_NON_INTERACTIF_ne_retire_jamais_plus_que_l_application(
        tmp_path, machine_avec_affichage):
    """AC1 -- « une machine muette ne retire jamais plus que l'application ».

    Le meme verdict que ci-dessus, mais par le regime qui compte vraiment : un
    `curl | bash` sans terminal, une CI, un conteneur. C'est la ou un defaut
    mal pose retirerait 52 Mo sans que personne ait rien choisi.
    """
    env, poses = _machine_avec_un_recu(tmp_path, machine_avec_affichage,
                                       ordre="cible_en_tete")
    courant = Path(env["HOME"]) / "courant"
    courant.mkdir()
    _, brut = jouer_sans_terminal(["--desinstaller", "--non-interactif"], env,
                                  cwd=courant)
    sortie = sans_ansi(brut)
    assert poses["ffmpeg"].exists(), (
        "le mode muet a retire un binaire que personne n'a demande de "
        "retirer :\n%s" % sortie)
    assert "mode non interactif : je prends 1)" in sortie, sortie


# ---------------------------------- AC6 : l'issue 3 AFFICHE et ne FAIT PAS

def test_l_issue_3_ne_retire_ABSOLUMENT_RIEN(tmp_path, machine_avec_affichage):
    """AC6 -- mesure sur l'etat, et sur TOUT ce que les deux autres issues
    retirent.

    Le recu lui-meme en fait partie : une issue qui « n'affiche que » et
    emporterait quand meme le repertoire d'etat serait fausse d'exactement un
    objet, et c'est le genre d'ecart qu'aucun test de message ne voit.
    """
    env, poses = _machine_avec_un_recu(tmp_path, machine_avec_affichage,
                                       ordre="cible_en_tete")
    profil = Path(env["HOME"]) / ".bashrc"
    profil.write_text(
        "# Created by `pipx` on 2026-09-07 16:00:00\n"
        'export PATH="$PATH:/root/.local/bin"\n')
    dossier_du_recu = _recu_fichier(env).parent

    sortie = _desinstaller_avec_l_issue(env, 3)

    assert "RIEN n'est retire" in sortie, sortie
    for nom in ("ffmpeg", "ffprobe", "temoin", "python"):
        assert poses[nom].exists(), (
            "l'issue 3 a retire %s alors qu'elle n'AFFICHE que :\n%s" % (nom, sortie))
    assert dossier_du_recu.is_dir(), (
        "l'issue 3 a retire le recu :\n%s" % sortie)
    assert "Created by `pipx`" in profil.read_text(), (
        "l'issue 3 a touche au profil :\n%s" % sortie)
    # Et elle donne les TROIS voies, dont celle de Python qui n'est pas une
    # commande -- c'est le pendant POSITIF de la frontiere negative ci-dessous.
    assert "Pour RETIRER ffmpeg" in sortie, sortie
    assert "Pour RETIRER pipx" in sortie, sortie
    assert "AUCUNE commande de retrait pour Python" in sortie, sortie
    assert "https://www.python.org/downloads/" in sortie, sortie


def test_une_entree_PYTHON_du_recu_ne_devient_JAMAIS_un_retrait(
        tmp_path, machine_avec_affichage):
    """AC6 -- la frontiere la plus importante de cette story, mesuree sur l'etat.

    Une entree `python` traverse le recu, l'epreuve d'existence et l'annonce --
    et ne devient jamais un retrait. C'est la raison 1 d'`EPIC11-ARB-274` :
    retirer le Python du systeme casse le systeme, et le « Python » qu'un
    utilisateur croit avoir installe est presque toujours celui qui etait deja
    la.

    ET LA PREUVE EST DANS LES DEUX SENS, sur la MEME course : le cadre Python
    survit pendant que `ffmpeg`, entree voisine du meme recu, part. Une
    frontiere dont on n'a pas mesure qu'elle rougit sur son contre-exemple
    n'est pas une frontiere -- ici, le contre-exemple est un objet qui, lui,
    DOIT partir.
    """
    env, poses = _machine_avec_un_recu(tmp_path, machine_avec_affichage,
                                       ordre="cible_en_tete")
    sortie = _desinstaller_avec_l_issue(env, 2)

    assert poses["python"].exists(), (
        "une entree `python` du recu a ete retiree :\n%s" % sortie)
    assert not poses["ffmpeg"].exists(), (
        "le contre-exemple n'a pas joue : rien n'a ete retire du tout, et la "
        "frontiere ci-dessus serait verte en ne mesurant rien :\n%s" % sortie)
    assert "Python n'est PAS retire" in sortie, sortie
    assert "AUCUNE commande de retrait pour Python" in sortie, sortie


#: Les formes de RETRAIT AUTOMATIQUE de Python, par gestionnaire. `python` y est
#: reconnu comme un JETON : sans la double garde de fin, `python3-pipx` et
#: `python-pipx` -- les noms du paquet pipx sur openSUSE et sur Arch -- seraient
#: pris pour Python, et la frontiere rougirait sur du code juste.
_JETON_PYTHON = r"python[0-9.]*(?![0-9.])(?!-pipx)"
RETRAITS_DE_PYTHON_INTERDITS = tuple(re.compile(motif, re.I) for motif in (
    r"\b(?:apt|apt-get|dnf|yum|zypper)\s+(?:remove|purge|erase)\b[^\n]*" + _JETON_PYTHON,
    r"\bpacman\s+-R\w*\b[^\n]*" + _JETON_PYTHON,
    r"\bapk\s+del\b[^\n]*" + _JETON_PYTHON,
    r"\bbrew\s+uninstall\b[^\n]*" + _JETON_PYTHON,
    # `winget` et `uninstall` ne se touchent pas dans le code reel :
    # `Invoke-Etape "winget" @("uninstall", ...)`. Un motif qui les
    # exigeait colles ne reconnaissait AUCUN appel PowerShell -- trouve
    # par le contre-exemple, et c'est exactement a quoi il sert.
    r"winget[^\n]{0,30}\buninstall\b[^\n]*python",
    r"\brm\s+-[rf]{1,2}\b[^\n]*Python\.framework",
    r"\bRemove-Item\b[^\n]*Python\.framework",
))

#: Les contre-exemples qui prouvent que chaque motif MORD. Une frontiere
#: negative dont on n'a pas mesure qu'elle rougit est verte pour la pire des
#: raisons : elle ne reconnait plus rien.
RETRAITS_DE_PYTHON_QUI_DOIVENT_MORDRE = (
    "    executer ${SUDO} apt-get remove -y python3",
    "    executer ${SUDO} apt remove python3.12",
    "    executer ${SUDO} dnf remove -y python3",
    "    executer ${SUDO} zypper remove -y python311",
    "    executer ${SUDO} pacman -R --noconfirm python",
    "    executer ${SUDO} apk del python3",
    "    executer brew uninstall python@3.12",
    '    Invoke-Etape "winget" @("uninstall", "--id", "Python.Python.3.12")',
    '    rm -rf "/Library/Frameworks/Python.framework/Versions/3.12"',
    '    Remove-Item -LiteralPath "/Library/Frameworks/Python.framework" -Recurse',
)

#: Et ceux qui NE doivent PAS mordre : le retrait de pipx nomme `python-pipx`
#: sur Arch et `python3-pipx` sur openSUSE, et c'est du code juste.
RETRAITS_QUI_NE_DOIVENT_PAS_MORDRE = (
    "    executer ${SUDO} pacman -R --noconfirm python-pipx",
    "    executer ${SUDO} zypper remove -y python3-pipx",
    "    executer ${SUDO} apt-get remove -y pipx",
    "    executer brew uninstall ffmpeg",
    '    Write-Info "  python -m pip uninstall pipx"',
)


def test_AUCUN_retrait_automatique_de_PYTHON_dans_les_DEUX_scripts():
    """AC6 -- frontiere NEGATIVE, et sa preuve dans les deux sens.

    Aucun test positif ne verrait revenir un `apt remove python3` : le script
    marcherait parfaitement pour qui ne choisit jamais l'issue 2, et casserait
    la machine de qui la choisit. C'est exactement le genre de defaut qu'une
    frontiere negative existe pour attraper.

    Les deux jeux de contre-exemples valent autant que l'assertion elle-meme :
    l'un prouve que les motifs MORDENT, l'autre qu'ils ne mordent pas sur le
    retrait de pipx -- dont le paquet s'appelle `python-pipx` sur Arch. Sans le
    second, la frontiere aurait rougi sur du code juste ; sans le premier, elle
    aurait pu ne plus rien reconnaitre sans que personne le voie.
    """
    for exemple in RETRAITS_DE_PYTHON_QUI_DOIVENT_MORDRE:
        assert any(motif.search(exemple) for motif in RETRAITS_DE_PYTHON_INTERDITS), (
            "aucun motif ne reconnait ce retrait de Python : la frontiere ne "
            "mesure plus rien -- %r" % exemple)
    for exemple in RETRAITS_QUI_NE_DOIVENT_PAS_MORDRE:
        coupable = [motif.pattern for motif in RETRAITS_DE_PYTHON_INTERDITS
                    if motif.search(exemple)]
        assert not coupable, (
            "la frontiere rougit sur du code JUSTE (%r) a cause de %r"
            % (exemple, coupable))

    for script in (INSTALL_SH, INSTALL_PS1):
        code = code_du_script(script)
        for motif in RETRAITS_DE_PYTHON_INTERDITS:
            trouve = motif.findall(code)
            assert not trouve, (
                "%s retire Python automatiquement : c'est ce qu'`EPIC11-ARB-274` "
                "interdit -- l'issue 3 AFFICHE et ne FAIT PAS. %r"
                % (script.name, trouve))


# ------------------------------- AC11 : install.ps1 recoit le MEME contrat

def test_les_deux_scripts_emploient_les_MEMES_libelles_des_TROIS_issues():
    """AC11 -- mot pour mot, comme les cinq libelles du raccourci.

    La seule comparaison croisee qui existe entre les deux scripts
    (`test_les_deux_scripts_produisent_le_MEME_plan`) ne porte que sur les
    lignes `pipx ` : une divergence d'invite y est parfaitement invisible. Deux
    utilisateurs qui lisent la meme documentation et voient deux menus
    differents n'ont pas le meme produit.
    """
    bash = INSTALL_SH.read_text()
    ps = INSTALL_PS1.read_text()
    for libelle in LIBELLES_DES_TROIS_ISSUES + (INTITULE_DES_TROIS_ISSUES,):
        assert libelle in bash, ("install.sh ne porte plus %r" % libelle)
        assert libelle in ps, (
            "install.ps1 a derive du libelle de bash : %r" % libelle)


def test_install_ps1_porte_le_MEME_CONTRAT_de_recu_et_de_degradation():
    """AC11 -- « pas un contrat voisin ».

    Mesure en LECTURE, ce que ce banc fait de `install.ps1` depuis toujours :
    aucun `pwsh` n'existe dans le conteneur de session, et les bancs qui en
    demandent un se sautent d'eux-memes. Ce qui est mesure ici est donc la
    PRESENCE du mecanisme, pas son execution -- dit plutot que tu.
    """
    ps = code_du_script(INSTALL_PS1)
    # le chemin d'etat Windows, equivalent du repertoire XDG
    assert "pose-par-installeur.txt" in ps, "install.ps1 n'a pas de recu"
    assert "LOCALAPPDATA" in ps, (
        "le recu Windows doit vivre sous %LOCALAPPDATA%, l'equivalent du "
        "repertoire d'etat XDG")
    # les quatre gestes du mecanisme
    for fonction in ("Write-DansLeRecu", "Read-LeRecu", "Remove-SelonLeRecu",
                     "Remove-RepertoireDEtat", "Write-CommandeDeRetrait"):
        assert "function %s" % fonction in ps, (
            "install.ps1 n'a pas %s : le contrat est voisin, pas le meme" % fonction)
    # la degradation de l'AC4, et le refus de l'AC6
    assert "Je me rabats sur l'issue 1" in ps, (
        "install.ps1 ne degrade pas quand le recu manque")
    assert "Python n'est PAS retire" in ps, (
        "install.ps1 peut retirer Python : c'est ce que l'AC6 interdit")


def test_install_ps1_definit_Get_PythonConvenable_AVANT_de_desinstaller():
    """AC11 -- une panne d'ORDRE, jumelle exacte de celle de `set -u`.

    PowerShell ne definit une fonction qu'au moment ou sa definition
    s'EXECUTE. `Get-PythonConvenable` vivait dans l'etat des lieux, c'est-a-dire
    APRES le bloc de desinstallation ; l'issue 2 s'en sert pour retirer un pipx
    pose par `pip --user`, et l'aurait appelee avant qu'elle existe.

    Aucun `pwsh` ne tourne ici pour le montrer a l'execution : la frontiere
    mesure donc l'ORDRE dans le fichier, qui est ce qui decide.
    """
    texte = INSTALL_PS1.read_text()
    definition = texte.index("function Get-PythonConvenable")
    desinstallation = texte.index("if ($Desinstaller) {")
    assert definition < desinstallation, (
        "`Get-PythonConvenable` est definie APRES le bloc de desinstallation : "
        "l'issue 2 l'appellerait avant qu'elle existe")


# ----------------------------- AC8 : la mise a jour DIT ce qu'elle ne touche pas

def test_les_deux_scripts_DISENT_ce_que_la_mise_a_jour_NE_touche_PAS():
    """AC8 -- `EPIC11-ARB-277`, et la liste NEGATIVE compte autant que l'autre.

    « Un utilisateur qui lit "mise a jour" sans precision suppose que tout est
    mis a jour, puis conclut a un bogue quand un ffmpeg de 2019 refuse une
    option. Le dire coute deux lignes. »

    Cote bash, la mesure porte sur ce que le PRODUIT affiche (`--help` joue
    pour de vrai) et non sur le fichier ; cote PowerShell, l'aide EST un bloc
    de commentaire `<# ... #>` -- c'est sa forme normale --, donc elle se lit
    dans le texte brut. `code_du_script` la retirerait.
    """
    acheve = subprocess.run(["/bin/bash", str(INSTALL_SH), "--help"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=DELAI)
    aide = acheve.stdout.decode("utf-8", "replace")
    assert acheve.returncode == 0, aide

    ps = INSTALL_PS1.read_text()
    for texte, ou in ((aide, "l'aide de install.sh"), (ps, "install.ps1")):
        assert "ne met a jour ni Python, ni ffmpeg, ni pipx" in texte, (
            "%s ne dit pas ce que la mise a jour NE touche PAS :\n%s" % (ou, texte))
        assert "--include-injected" in texte, (
            "%s ne dit pas que la greffe est mise a jour elle aussi" % ou)
        assert "pipx upgrade mmu-tui --include-injected" in texte, (
            "%s ne donne pas la voie manuelle equivalente" % ou)


def test_l_aide_de_bash_DECRIT_les_trois_issues_de_la_desinstallation():
    """AC8 + AC1 -- ce que `--desinstaller` fait doit se lire sans l'essayer.

    Le drapeau existait et sa ligne d'aide decrivait l'ANCIEN contrat (« retire
    les paquets ET la ligne de profil »). Une aide qui decrit un produit qu'on
    vient de remplacer est pire qu'une aide absente.
    """
    acheve = subprocess.run(["/bin/bash", str(INSTALL_SH), "--help"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=DELAI)
    aide = acheve.stdout.decode("utf-8", "replace")
    assert "TROIS issues" in aide, aide
    assert "--non-interactif" in aide and "defaut" in aide, aide
    for fragment in ("l'application seule", "ce que CE SCRIPT a pose",
                     "commandes officielles de retrait"):
        assert fragment in aide, (
            "l'aide ne decrit pas l'issue %r :\n%s" % (fragment, aide))


# ------------------- AC1 issue 2 + AC9 : pipx se retire PAR SA VOIE, pas par un rm

def _machine_avec_un_pipx_pose(tmp_path, machine, *, nature):
    """Une maison neuve ou le recu dit que CE script a pose pipx, par une voie.

    Les deux gestionnaires que ce banc peut atteindre sont RENDUS FACTICES et
    JOURNALISENT, et ce n'est pas du confort : la PATH que `_maison_neuve`
    fabrique est faite de COPIES des vrais binaires du conteneur, et le banc
    tourne en uid 0. Un `apt-get remove -y pipx` ou un
    `python3 -m pip uninstall -y pipx` reels retireraient pipx DU CONTENEUR --
    c'est la famille exacte du `/usr/bin/uname` remplace pendant la revue 8.8,
    et elle a coute vingt minutes ce jour-la.
    """
    env = _maison_neuve(tmp_path, machine, avec_commande_tui=True)
    binaires = Path(env["PATH"].split(os.pathsep)[0])
    journal = tmp_path / "voie_de_retrait.txt"
    # LE `sudo` FACTICE, ET SON ABSENCE A COUTE LE DERNIER ROUGE DE LA CI
    # (2026-09-09). Le `PATH` fabrique est fait de LIENS vers les vrais
    # binaires du systeme -- `sudo` compris. Ce conteneur tourne en **root**,
    # donc le vrai `sudo` y passait ; le runner GitHub tourne sous `runner`,
    # et le vrai `sudo` invoque a travers un lien hors de son emplacement
    # setuid REFUSE :
    #
    #   sudo: .../binaires/sudo must be owned by uid 0 and have the setuid bit
    #
    # `apt-get` n'etait donc jamais atteint, le journal jamais ecrit, et le
    # test passait ici en echouant la-bas. C'est la meme famille que `TERM` et
    # que `PIPX_BIN_DIR` : une machine « fabriquee » qui touche encore le
    # systeme reel n'est fabriquee que sur la machine ou ca ne se voit pas.
    _deposer_outil(binaires, "sudo",
                   "#!/bin/sh\n"
                   "# sudo factice : il n'eleve rien, il execute.\n"
                   "exec \"$@\"\n")
    _deposer_outil(binaires, "apt-get",
                   "#!/bin/sh\necho \"apt-get $*\" >> '%s'\nexit 0\n" % journal)
    _deposer_outil(binaires, "python3",
                   "#!/bin/sh\necho \"python3 $*\" >> '%s'\nexit 0\n" % journal)
    # Un pipx factice qui declare UNE AUTRE application. C'est le seul objet du
    # recu dont le retrait mord HORS du perimetre du script -- retirer pipx
    # emporte les commandes de tout ce qu'il gere --, et `EPIC11-ARB-89` exige
    # un AVERTISSEMENT avant une ecriture destructive consciente. Sans cette
    # autre application, le chemin d'avertissement ne serait jamais atteint et
    # une frontiere posee dessus serait verte en ne voyant rien.
    inventaire = tmp_path / "autres_applications.txt"
    inventaire.write_text("poetry 1.8.3\nblack 24.4.2\n")
    faux_pipx = _deposer_outil(
        binaires, "pipx",
        "#!/bin/sh\n"
        "if [ \"$1\" = \"list\" ] && [ \"$2\" = \"--short\" ]; then\n"
        "    cat '%s'\n"
        "fi\n"
        "exit 0\n" % inventaire)
    _ecrire_un_recu(env, [(nature, str(faux_pipx), "2026-09-08T02:00:00Z")])
    return env, journal, faux_pipx


def test_l_issue_2_retire_pipx_PAR_SA_VOIE_et_JAMAIS_par_un_rm(tmp_path,
                                                               machine_avec_affichage):
    """AC1 issue 2 + AC9 -- la voie est ECRITE DANS LA NATURE du recu.

    C'est la raison 2 d'`EPIC11-ARB-274` appliquee a nous-memes : « le script
    ne possede pas ce qu'il n'a pas pose », et surtout, ce qu'il a fait poser
    par un gestionnaire, il le lui fait reprendre. Effacer le fichier qu'apt
    croit posseder le laisserait avec un paquet fantome.

    Les DEUX voies sont jouees -- paquet systeme et `pip --user` -- parce
    qu'elles sont les deux sens du meme drapeau, et parce qu'elles ne laissent
    PAS la meme trace : c'est ce qui permet de verifier qu'on mesure bien celle
    qu'on croit (meme geste que le `sudo` factice du repli, mutant `M29`).

    Et dans les deux cas, le binaire pipx est TOUJOURS LA apres coup : le
    verdict « jamais par un rm » se lit sur l'etat de la machine, pas sur le
    texte -- les gestionnaires factices ne retirent rien, donc un `rm` du
    produit serait le seul moyen que le fichier disparaisse.
    """
    env, journal, faux_pipx = _machine_avec_un_pipx_pose(
        tmp_path / "systeme", machine_avec_affichage, nature="pipx-paquet-systeme")
    sortie = _desinstaller_avec_l_issue(env, 2)
    assert journal.exists(), (
        "aucune voie de retrait n'a ete empruntee pour pipx :\n%s" % sortie)
    trace = journal.read_text()
    assert "apt-get remove -y pipx" in trace, (
        "pipx n'a pas ete repris par le gestionnaire qui l'a pose : %r\n%s"
        % (trace, sortie))
    assert "python3" not in trace, (
        "la mauvaise voie a ete empruntee : %r" % trace)
    assert faux_pipx.exists(), (
        "pipx a ete efface par un `rm` au lieu d'etre repris par son "
        "gestionnaire -- c'est le paquet fantome qu'`EPIC11-ARB-274` "
        "interdit :\n%s" % sortie)
    # L'AVERTISSEMENT vient AVANT le retrait, et il NOMME ce qui sera perdu :
    # une ecriture destructive consciente se fait « apres avertissement »
    # (`EPIC11-ARB-89`), pas apres coup.
    assert "pipx gere encore d'autres applications" in sortie, sortie
    for autre in ("poetry 1.8.3", "black 24.4.2"):
        assert autre in sortie, (
            "l'avertissement ne nomme pas %r : l'utilisateur decouvrirait la "
            "perte apres coup :\n%s" % (autre, sortie))
    assert sortie.index("pipx gere encore") < sortie.index("apt-get remove -y pipx"), (
        "le retrait a commence avant l'avertissement :\n%s" % sortie)

    env, journal, faux_pipx = _machine_avec_un_pipx_pose(
        tmp_path / "pip", machine_avec_affichage, nature="pipx-pip-utilisateur")
    sortie = _desinstaller_avec_l_issue(env, 2)
    assert journal.exists(), (
        "aucune voie de retrait n'a ete empruntee pour pipx :\n%s" % sortie)
    trace = journal.read_text()
    assert "-m pip uninstall -y pipx" in trace, (
        "un pipx pose par pip doit se reprendre par pip : %r\n%s" % (trace, sortie))
    assert "apt-get remove" not in trace, (
        "la mauvaise voie a ete empruntee : %r" % trace)
    assert faux_pipx.exists(), (
        "pipx a ete efface par un `rm` :\n%s" % sortie)


def test_une_NATURE_INCONNUE_au_recu_ne_retire_RIEN(tmp_path, machine_avec_affichage):
    """AC3 -- « on ne retire que l'intersection », et la politique decide seule.

    Un recu ecrit par une version FUTURE du script ne doit pas faire retirer
    n'importe quoi par une version ancienne : une nature qu'on ne connait pas
    n'est pas une invitation a effacer le chemin qu'elle porte. C'est la meme
    prudence que le refus de Python, appliquee a ce qu'on ne sait pas lire.

    Le contre-exemple est dans la MEME course : l'entree `ffmpeg`, elle, part.
    Sans lui, ce banc serait vert sur un desinstalleur qui ne retire jamais
    rien du tout.
    """
    env = _maison_neuve(tmp_path, machine_avec_affichage, avec_commande_tui=True)
    binaires = Path(env["HOME"]) / ".local" / "bin"
    binaires.mkdir(parents=True, exist_ok=True)
    inconnu = binaires / "objet-d-une-version-future"
    inconnu.write_text("x")
    connu = binaires / "ffmpeg"
    connu.write_text("#!/bin/sh\nexit 0\n")
    _ecrire_un_recu(env, [
        ("nature-que-cette-version-ne-connait-pas", str(inconnu), "2026-09-08T03:00:00Z"),
        ("ffmpeg", str(connu), "2026-09-08T03:00:01Z"),
    ])

    sortie = _desinstaller_avec_l_issue(env, 2)
    assert inconnu.exists(), (
        "une nature inconnue a fait retirer un fichier a l'aveugle :\n%s" % sortie)
    assert "Nature inconnue au recu" in sortie, sortie
    assert not connu.exists(), (
        "le contre-exemple n'a pas joue : rien n'a ete retire du tout :\n%s" % sortie)


# ------------------------- triage de la revue 8.12, couche 1 (2026-09-08)
#
# Trois findings `critique`. `C1-3` etait un defaut du PRODUIT et se ferme dans
# `install.sh` ; les deux qui suivent sont des frontieres qui manquaient.


def test_un_XDG_STATE_HOME_RELATIF_retombe_sur_le_DEFAUT(tmp_path, machine_vierge):
    """`C1-1` -- et il ROUVRAIT le finding que la story 8.12 existe pour fermer.

    La garde jumelle sur `XDG_DATA_HOME` est mesuree depuis la story 8.8
    (`test_un_XDG_DATA_HOME_RELATIF_retombe_sur_le_DEFAUT`, l. 2665). Celle sur
    `XDG_STATE_HOME` ne l'etait pas, alors qu'elle decide de l'ADRESSE DU
    RECU -- c'est-a-dire du mecanisme central de la story.

    Ce que la couche 1 a mesure en la retirant :

        sain    : Ainsi que le recu ... : /root/.local/state/mmu
        mutant  : Ainsi que le recu ... : etat-relatif/mmu

    Le recu part alors dans le repertoire COURANT de qui a lance
    l'installation. Un `--desinstaller` lance d'ailleurs ne le retrouve jamais,
    degrade en silence vers l'issue 1, et laisse les 52 Mo du repli precompile
    en place : le finding `C2-9` de la revue 8.11, rouvert par une variable
    d'environnement.

    Le repertoire courant est JETABLE, et ce n'est pas du confort : celui du
    banc est la racine du depot, et un chemin relatif s'y resout. Le meme
    defaut a deja fait ecrire un `ffmpeg` factice a la racine (`M22`, revue
    8.11).
    """
    env = dict(machine_vierge)
    env["XDG_STATE_HOME"] = "etat-relatif"
    courant = tmp_path / "repertoire-courant-jetable"
    courant.mkdir()
    _, brut = jouer_sans_terminal(
        ["--desinstaller", "--non-interactif", "--dry-run"], env, cwd=courant)
    sortie = sans_ansi(brut)

    attendu = str(Path(env["HOME"]) / ".local" / "state" / "mmu")
    assert attendu in sortie, (
        "un XDG_STATE_HOME relatif doit etre ignore et le defaut employe ; le "
        "recu est annonce ailleurs :\n%s" % sortie)
    assert "etat-relatif" not in sortie, (
        "le chemin relatif a ete SUIVI : le recu tombe dans le repertoire "
        "courant de l'appelant, ou aucun desinstalleur ne le retrouvera. "
        "C'est le finding C2-9 de la revue 8.11, rouvert.\n%s" % sortie)
    assert not (courant / "etat-relatif").exists(), (
        "un repertoire d'etat a ete cree dans le repertoire courant")


#: Les six noms de paquet de `pipx`, un par gestionnaire, dans l'ordre des
#: parametres d'`installer_paquet_systeme` : brew, apt, dnf, pacman, zypper, apk.
GESTIONNAIRES_DE_PIPX = ("brew", "apt-get", "dnf", "pacman", "zypper", "apk")


def _noms_de_paquet_a_la_pose(code: str) -> list:
    """Les six noms que `install.sh` emploie pour POSER pipx."""
    # SIX arguments EN TOUT, `"pipx"` compris -- pas six APRES lui. La
    # premiere redaction comptait mal et rendait `None` ; c'est l'assertion de
    # forme juste en dessous qui l'a dit, pas la relecture.
    trouve = re.search(r'installer_paquet_systeme\s+("pipx"(?:\s+"[^"]+"){5})', code)
    assert trouve, "l'appel de pose de pipx a change de forme ; ce banc le lisait"
    return re.findall(r'"([^"]+)"', trouve.group(1))


def _noms_de_paquet_au_retrait(code: str) -> list:
    """Les six noms que `retirer_pipx_du_systeme` emploie pour le RETIRER.

    Lus dans l'ordre des gestionnaires, jamais dans l'ordre du fichier : un
    `case` se reordonne sans changer de sens, et une frontiere qui dependrait
    de l'ordre des lignes rougirait sur un remaniement innocent.
    """
    corps = "\n".join(corps_de_fonction(code, "retirer_pipx_du_systeme"))
    noms = []
    for gestionnaire in GESTIONNAIRES_DE_PIPX:
        motif = r'^\s*%s\)\s+executer.*?(\S+)\s+\|\|' % re.escape(gestionnaire)
        trouve = re.search(motif, corps, re.M)
        assert trouve, (
            "la branche %r du retrait de pipx a change de forme ; ce banc la "
            "lisait" % gestionnaire)
        noms.append(trouve.group(1))
    return noms


def test_les_SIX_noms_de_paquet_de_pipx_sont_les_MEMES_a_la_pose_et_au_retrait():
    """`C1-2` -- l'invariant etait ecrit en COMMENTAIRE et tenu par rien.

    `install.sh` l'affirme lui-meme : « Les recopier ici est deliberement
    symetrique -- poser et retirer nomment le meme paquet, ou l'un des deux se
    trompe. » Mesure de la couche 1 : remplacer `python-pipx` par `pipx` sur la
    branche pacman **passait les 149 tests**.

    C'est un appariement entre DEUX TABLES, la classe que la politique du depot
    nomme critique, et il derivera au premier renommage amont. Ce que ca
    couterait a l'utilisateur : `pacman -R --noconfirm pipx` rend « target not
    found » sur Arch, ou le paquet s'appelle `python-pipx` -- un retrait qui
    annonce avoir echoue sans dire pourquoi.

    Le nom de chaque paquet n'est PAS epingle ici : c'est le nom du paquet
    amont, il peut changer legitimement. Ce qui est epingle est leur EGALITE
    entre les deux tables -- la propriete, pas la valeur.
    """
    code = code_du_script(INSTALL_SH)
    pose = _noms_de_paquet_a_la_pose(code)
    retrait = _noms_de_paquet_au_retrait(code)

    assert len(pose) == 6 and len(retrait) == 6, (
        "six gestionnaires attendus de chaque cote, %d et %d releves : le "
        "perimetre a fondu, cette frontiere ne mesure plus rien"
        % (len(pose), len(retrait)))
    assert len(set(pose)) >= 2, (
        "les six noms de pose sont identiques : une frontiere d'egalite ne "
        "mesure rien sur une table uniforme (regle des fabriques, point 1)")

    ecarts = [(g, p, r) for g, p, r in zip(GESTIONNAIRES_DE_PIPX, pose, retrait)
              if p != r]
    assert ecarts == [], (
        "poser et retirer pipx ne nomment pas le meme paquet, donc l'un des "
        "deux se trompe -- et le commentaire d'`install.sh` le dit deja : %r"
        % (ecarts,))


def test_cette_frontiere_MORD_sur_un_nom_DIVERGENT():
    """Le volet negatif, sur la forme EXACTE du mutant `M22` qui survivait.

    Sans lui, la frontiere ci-dessus serait verte par construction : elle l'a
    ete tout le temps qu'elle n'existait pas. Le mutant est joue sur le CODE
    lu, jamais sur le fichier -- rien ne touche le disque.
    """
    code = code_du_script(INSTALL_SH)
    mute = code.replace(
        "pacman)  executer ${SUDO} pacman -R --noconfirm python-pipx",
        "pacman)  executer ${SUDO} pacman -R --noconfirm pipx")
    assert mute != code, (
        "la ligne pacman du retrait a change de forme ; ce volet negatif la "
        "rejouait telle quelle")
    assert _noms_de_paquet_au_retrait(mute) != _noms_de_paquet_a_la_pose(code), (
        "le mutant M22 passe encore : la frontiere ne mesure pas ce qu'elle "
        "croit mesurer")


# ------------------------- triage de la revue 8.12, couche 3 (2026-09-08)
#
# Cinq findings `critique`, et ils partagent une forme : ce ne sont pas des
# chemins oublies, ce sont des tests qui mesurent AUTRE CHOSE que ce que leur
# nom annonce.


def _natures_ecrites_pour_pipx(code: str) -> set:
    """Les etiquettes de recu que le producteur peut ECRIRE pour pipx.

    Elles se forment par interpolation (`"pipx-${ROUTE_DE_PIPX}"`), donc elles
    ne se trouvent nulle part en toutes lettres du cote producteur : il faut
    relever les valeurs de la variable.
    """
    routes = set(re.findall(r'ROUTE_DE_PIPX="([^"]+)"', code))
    return {"pipx-%s" % route for route in routes}


def _natures_LUES_par_le_retrait(code: str) -> set:
    """Les etiquettes que le consommateur reconnait, lues dans son `case`."""
    corps = "\n".join(corps_de_fonction(code, "retirer_selon_le_recu"))
    etiquettes = set()
    for ligne in re.findall(r'^\s*([a-z0-9|*-]+)\)', corps, re.M):
        etiquettes.update(m for m in ligne.split("|") if m and m != "*")
    return etiquettes


def test_CHAQUE_nature_de_recu_ECRITE_est_une_nature_LUE():
    """`C3-1` -- un appariement entre un producteur et un consommateur.

    Mesure de la couche 3 : renommer `paquet-systeme` en `paquet-du-systeme`
    du cote producteur laisse **159 verts**. Si le defaut existait, l'issue 2
    tomberait dans « Nature inconnue au recu, rien n'est retire » et **pipx ne
    serait jamais repris**, en silence -- c'est-a-dire le mandat d'Egan (« tout
    supprimer ») non tenu sans un rouge.

    Ce qui l'avait rendu invisible : aucun banc ne porte `pipx-paquet-systeme`
    autrement que dans un recu **fabrique**. Un recu fabrique mesure le
    consommateur ; il ne mesure jamais que le producteur ecrit la meme chose.

    C'est la meme classe que `C1-2` (les six noms de paquet), et c'est la
    troisieme fois de la soiree qu'un appariement entre deux tables du meme
    fichier passe entre les mailles.
    """
    code = code_du_script(INSTALL_SH)
    ecrites = _natures_ecrites_pour_pipx(code)
    lues = _natures_LUES_par_le_retrait(code)

    assert len(ecrites) >= 2, (
        "moins de deux routes de pipx relevees (%r) : une frontiere "
        "d'appariement ne mesure rien sur une collection d'un seul element "
        "(regle des fabriques, point 1)" % (ecrites,))
    assert len(lues) >= 4, (
        "seulement %d etiquettes lues par le retrait (%r) : le perimetre a "
        "fondu" % (len(lues), lues))

    orphelines = sorted(ecrites - lues)
    assert orphelines == [], (
        "le recu peut porter une nature que le retrait ne reconnait pas : "
        "l'issue 2 tomberait dans « Nature inconnue » et pipx ne serait jamais "
        "repris, EN SILENCE. %r ecrites, %r lues" % (orphelines, sorted(lues)))

    # Les natures des DEUX autres producteurs, litterales celles-la.
    for nature in ("ffmpeg", "ffprobe", "python"):
        assert nature in lues, (
            "la nature %r est ecrite au recu et le retrait ne la reconnait "
            "pas" % nature)


def test_cet_appariement_MORD_sur_une_etiquette_renommee():
    """Le volet negatif, sur la forme EXACTE du mutant qui survivait.

    Joue sur le code LU, jamais sur le fichier -- rien ne touche le disque.
    """
    code = code_du_script(INSTALL_SH)
    mute = code.replace('ROUTE_DE_PIPX="paquet-systeme"',
                        'ROUTE_DE_PIPX="paquet-du-systeme"')
    assert mute != code, "la ligne du producteur a change de forme"
    assert _natures_ecrites_pour_pipx(mute) - _natures_LUES_par_le_retrait(mute), (
        "le mutant passe encore : cette frontiere ne mesure pas l'appariement")


#: Les appels PowerShell dont l'absence ferait disparaitre l'issue 2 et l'AC5
#: cote Windows, SANS qu'aucune definition de fonction ne manque.
APPELS_ATTENDUS_DANS_PS1 = ("Read-LeRecu", "Remove-SelonLeRecu",
                            "Remove-RepertoireDEtat")


def test_install_ps1_APPELLE_ses_fonctions_de_recu_et_pas_seulement_les_DEFINIT():
    """`C3-4` -- le contrat Windows etait mesure en definitions, jamais en appels.

    Mesure de la couche 3 : commenter `Remove-SelonLeRecu $recuLu` ou
    `Remove-RepertoireDEtat` rend **0 rouge**. L'AC5 et l'issue 2 cote Windows
    pouvaient disparaitre **entierement** pendant que le banc restait vert,
    parce que la frontiere existante verifie que cinq `function X` EXISTENT.

    **Ce n'est pas une limite d'environnement.** `pwsh` est absent du conteneur,
    mais la story prouve elle-meme qu'on mesure un cablage en LECTURE :
    `test_install_ps1_definit_Get_PythonConvenable_AVANT_de_desinstaller` le
    fait deja. Une fonction definie et jamais appelee est du code mort -- c'est
    la signature exacte du defaut central de la revue 8.10, ou `_etapes()`
    etait ecrit, documente, porteur de sa propre anti-vacuite, et appele par
    AUCUN test.
    """
    code = code_du_script(INSTALL_PS1)
    for nom in APPELS_ATTENDUS_DANS_PS1:
        definitions = len(re.findall(r'^\s*function\s+%s\b' % re.escape(nom),
                                     code, re.M | re.I))
        assert definitions == 1, (
            "%s : %d definition(s), une seule attendue" % (nom, definitions))
        # Un appel est une occurrence QUI N'EST PAS la definition.
        occurrences = len(re.findall(r'\b%s\b' % re.escape(nom), code))
        assert occurrences >= 2, (
            "`%s` est DEFINIE et jamais APPELEE dans install.ps1 : l'issue 2 "
            "ou l'AC5 y sont du code mort, et aucune frontiere de definition "
            "ne le verrait" % nom)


def test_le_balayage_de_l_AC6_n_est_pas_VIDE():
    """`T3-1` -- mordre et etre non vacante sont deux proprietes DISTINCTES.

    La frontiere negative de l'AC6 mord bien sur ses dix contre-exemples --
    la couche 3 l'a mesure. Elle reste **verte sur un perimetre balaye vide** :
    `code_du_script` rendu vide fait rougir 23 tests voisins, et pas elle.

    Le voisin `test_AUCUN_sudo_dans_le_BLOC_d_ecriture_du_raccourci` porte la
    garde d'une ligne qui manquait ici. Une frontiere negative sans garde de
    non-vacuite est verte par construction, et c'est le mode de panne le plus
    silencieux qu'une frontiere puisse avoir.
    """
    for chemin, plancher in ((INSTALL_SH, 1000), (INSTALL_PS1, 500)):
        code = code_du_script(chemin)
        lignes = [l for l in code.splitlines() if l.strip()]
        assert len(lignes) > plancher, (
            "%s : %d lignes non vides apres retrait des commentaires, moins "
            "que le plancher de %d. Le perimetre que balaye la frontiere "
            "negative de l'AC6 a fondu -- elle serait verte sans rien "
            "mesurer." % (chemin.name, len(lignes), plancher))


# ------------------------- triage de la revue 8.12, couche 2 (2026-09-08)
#
# Deux findings `critique` qui font PERDRE ou DETRUIRE des donnees. Ils ne sont
# pas de la meme famille que les autres : les autres laissaient une propriete
# non mesuree, ceux-la laissaient le produit se tromper.


def test_la_DERNIERE_ligne_du_recu_est_traitee_MEME_SANS_saut_de_ligne_final(
        tmp_path, machine_vierge):
    """Couche 2, finding 1 -- une perte SILENCIEUSE et DEFINITIVE.

    `read` rend non nul en EOF sans `\\n`, **apres avoir pourtant rempli ses
    variables** : la boucle s'arretait sans traiter cette entree-la. Mesure de
    la couche : deux entrees, la derniere non terminee -> `ffmpeg` retire,
    `ffprobe` NI RETIRE NI MENTIONNE, puis le repertoire d'etat efface. L'objet
    devient **irrecuperable** -- plus personne ne sait ou il est.

    Le regime est atteignable **par le produit lui-meme** : un `printf >>` sur
    un disque plein ecrit une ligne tronquee. Ce n'est pas un recu hostile,
    c'est le notre.

    La fabrique de reference varie l'ORDRE des entrees ; elle ne varie pas la
    TERMINAISON du fichier. C'est l'axe que ce test ajoute -- et c'est
    exactement ce que la couche 2 a nomme : « une garde qui ne fait varier
    aucun de ses drapeaux ne mesure qu'un seul chemin ».
    """
    env = _maison_neuve(tmp_path, machine_vierge, avec_commande_tui=True)
    binaires = Path(env["HOME"]) / ".local" / "bin"
    binaires.mkdir(parents=True, exist_ok=True)
    poses = {}
    for nom in ("ffmpeg", "ffprobe"):
        poses[nom] = binaires / nom
        poses[nom].write_text("#!/bin/sh\nexit 0\n")
        poses[nom].chmod(0o755)

    recu = _recu_fichier(env)
    recu.parent.mkdir(parents=True, exist_ok=True)
    # SANS `\n` FINAL sur la derniere ligne : c'est tout le test.
    recu.write_text(
        "ffmpeg\t%s\t2026-09-08T01:00:00Z\n"
        "ffprobe\t%s\t2026-09-08T01:00:01Z" % (poses["ffmpeg"], poses["ffprobe"]))

    sortie = _desinstaller_avec_l_issue(env, 2, tmp_path=tmp_path)

    assert not poses["ffmpeg"].exists(), (
        "la premiere entree n'a pas ete traitee :\n%s" % sortie)
    assert not poses["ffprobe"].exists(), (
        "la DERNIERE entree d'un recu sans saut de ligne final a ete PERDUE. "
        "Elle n'est ni retiree ni mentionnee, et le recu est efface juste "
        "apres : l'objet devient irrecuperable.\n%s" % sortie)


def test_un_chemin_NON_ABSOLU_au_recu_ne_fait_JAMAIS_retirer_quoi_que_ce_soit(
        tmp_path, machine_vierge):
    """Couche 2, finding 2 -- la garde n'existait qu'a l'ECRITURE.

    Mesure de la couche : un recu portant `ffmpeg<TAB>victime.txt`, lance
    depuis un repertoire qui contient ce fichier -- **supprime**, et annonce
    « ok Retire : victime.txt (ffmpeg, pose par ce script) ».

    C'est la doctrine du module retournee contre elle-meme. `lire_le_recu`
    ecrit noir sur blanc que « le recu n'est PAS une source de verite », et il
    etait pourtant cru sur parole pour la seule chose qui compte : l'adresse de
    ce qu'on efface. Un recu ne se signe pas ; la garde doit donc vivre du cote
    qui AGIT, pas seulement du cote qui ECRIT.

    Le regime n'a rien d'hostile : un recu ecrit par une version future, un
    fichier a moitie recopie, une entree tronquee suffisent.
    """
    env = _maison_neuve(tmp_path, machine_vierge, avec_commande_tui=True)
    courant = Path(env["HOME"]) / "repertoire_courant_jetable"
    courant.mkdir(parents=True, exist_ok=True)
    victime = courant / "victime.txt"
    victime.write_text("un fichier qui n'a rien demande\n")

    recu = _recu_fichier(env)
    recu.parent.mkdir(parents=True, exist_ok=True)
    recu.write_text("ffmpeg\tvictime.txt\t2026-09-08T01:00:00Z\n")

    sortie = _desinstaller_avec_l_issue(env, 2, tmp_path=tmp_path)

    assert victime.exists(), (
        "un chemin RELATIF du recu a ete suivi : le desinstalleur a efface un "
        "fichier du repertoire courant de l'appelant, qu'il n'avait jamais "
        "pose.\n%s" % sortie)
    assert "rien n'est retire" in sortie, (
        "le chemin relatif doit etre NOMME et ecarte, pas ignore en "
        "silence.\n%s" % sortie)


def test_ces_deux_gardes_du_recu_MORDENT_sur_leur_contre_exemple():
    """Le volet negatif des deux precedents, sur le CODE et pas sur le disque.

    Une frontiere dont on n'a pas mesure qu'elle rougit sur son contre-exemple
    n'est pas une frontiere. Les deux mutants sont joues sur le code LU.
    """
    code = code_du_script(INSTALL_SH)
    corps = "\n".join(corps_de_fonction(code, "lire_le_recu"))

    assert '|| [ -n "${nature}" ]' in corps, (
        "la garde de derniere ligne a disparu de `lire_le_recu` : un recu sans "
        "saut de ligne final perd son entree de queue, en silence")
    assert "/*)" in corps, (
        "la garde de chemin absolu a disparu de `lire_le_recu` : un chemin "
        "relatif du recu ferait effacer un fichier du repertoire courant")


def test_une_ENTREE_FERMEE_sur_un_VRAI_terminal_prend_le_DEFAUT_et_le_DIT(
        tmp_path, machine_vierge):
    """Couche 2, finding 6 (`M38`) -- la garantie existe et n'etait pas mesuree.

    Le regime est le plus etroit des trois, et c'est pour ca qu'il manquait :
    ce n'est ni « pas de terminal » (deja mesure par `jouer_sans_terminal`, qui
    passe par `RAISON_MUETTE`), ni une saisie invalide (mesuree, elle repose la
    question). C'est un terminal **present** dont l'entree est **fermee** --
    un `Ctrl+D` au prompt, ou un pipeline dont l'amont se termine.

    Sans la garde, `read` echoue a chaque tour et la boucle `while true`
    **repose la question indefiniment** : l'installateur pend, sur le parcours
    le plus interactif du produit. C'est ce que la couche 2 a mesure en la
    retirant.

    Le `\\x04` est un EOT ecrit en tete de ligne : la discipline canonique du
    pseudo-terminal le traduit en fin de fichier, ce qu'aucun tube ne sait
    faire tant que le script ouvre `/dev/tty`.
    """
    env = _maison_neuve(tmp_path, machine_vierge, avec_commande_tui=True)
    courant = Path(env["HOME"]) / "repertoire_courant_jetable"
    courant.mkdir(parents=True, exist_ok=True)
    sortie = sans_ansi(jouer_le_dialogue(
        ["--desinstaller"], ["\x04"], env, cwd=courant))

    assert "entree fermee" in sortie, (
        "une entree fermee sur un vrai terminal doit prendre le defaut ET LE "
        "DIRE ; sans cette garde la boucle repose la question a l'infini et "
        "l'installateur pend.\n%s" % sortie)
    assert "Termine" in sortie, (
        "le parcours ne va pas jusqu'au bout apres une entree fermee.\n%s"
        % sortie)


def test_le_recu_ecarte_un_LIEN_CASSE_plutot_que_de_le_LAISSER(tmp_path, machine_vierge):
    """`C3-5` -- la garde `-L` existait, et aucune fabrique ne la traversait.

    `lire_le_recu` garde `[ -e ] || [ -L ]`, et son commentaire invoque
    nommement la lecon `-f`/`-L` du raccourci de la story 8.8. Mesure de la
    couche 3 : retirer `|| [ -L "${chemin}" ]` rend **0 rouge** -- la lecon
    etait dans le code, pas dans la fabrique. `_machine_avec_un_recu` ne
    produit aucun lien casse.

    Ce que ca coute quand ca mord : un binaire du repli remplace par un lien
    dont la cible a disparu n'est ni un fichier ni « deja disparu ». Sans la
    garde, il est ecarte comme absent et **reste en place a jamais** -- dans un
    repertoire prefixe au PATH, ou il masque ce que la commande de secours
    recommande. C'est le finding `C1-1` de la revue 8.11, par une autre porte.
    """
    env = _maison_neuve(tmp_path, machine_vierge, avec_commande_tui=True)
    binaires = Path(env["HOME"]) / ".local" / "bin"
    binaires.mkdir(parents=True, exist_ok=True)
    casse = binaires / "ffmpeg"
    casse.symlink_to(binaires / "une-cible-qui-n-existe-pas")
    assert casse.is_symlink() and not casse.exists(), (
        "la fabrique n'a pas produit un lien CASSE ; le test ne mesurerait rien")

    _ecrire_un_recu(env, [("ffmpeg", str(casse), "2026-09-08T01:00:00Z")])
    sortie = _desinstaller_avec_l_issue(env, 2, tmp_path=tmp_path)

    assert not casse.is_symlink(), (
        "un lien CASSE inscrit au recu n'a pas ete retire : il n'est ni un "
        "fichier ni « deja disparu », et il reste en place a jamais dans un "
        "repertoire prefixe au PATH.\n%s" % sortie)
    assert "deja disparu" not in sortie, (
        "le lien casse a ete pris pour un objet deja disparu ; il existe "
        "pourtant, et c'est justement le piege.\n%s" % sortie)


def test_TOUTE_sortie_de_retrait_passe_par_commande_de_secours_et_ne_la_RECOPIE_pas():
    """`C3-3` -- l'interdit de la 8e ligne du pare-arbitrage n'avait aucune frontiere.

    La cellule dit : « `commande_de_secours` est reemployee et non recopiee ».
    Mesure de la couche 3 : recopier les trois appels en `info` litteraux
    equivalents rend **0 rouge** -- la sortie visible est identique, seule une
    frontiere de STRUCTURE le verrait.

    Meme classe que « aucun `sudo` dans le repli ffmpeg » de la 8.11 : un
    interdit nomme dans le pare-arbitrage, avec un test en face, et le test ne
    mesurait pas cet interdit-la.

    Ce que la recopie couterait : la table des commandes officielles vit a UN
    endroit et `EPIC11-ARB-271` l'exige ainsi. Deux tables divergent au premier
    changement amont, et le desinstalleur donnerait alors une commande que
    l'installateur ne donne plus.
    """
    code = code_du_script(INSTALL_SH)
    appels = re.findall(r'commande_de_secours\s+"([a-z]+)"\s+"retrait"', code)
    assert len(appels) >= 5, (
        "seulement %d appels de retrait a `commande_de_secours` releves : le "
        "perimetre a fondu, cette frontiere ne mesure plus rien" % len(appels))
    assert set(appels) == {"ffmpeg", "pipx", "python"}, (
        "les trois dependances doivent toutes passer par la table unique : %r"
        % (sorted(set(appels)),))

    # LE VOLET NEGATIF : aucune URL ni commande officielle ne doit etre
    # RECOPIEE dans le bloc de desinstallation. Elles vivent dans la table.
    # LE PERIMETRE SE COMPOSE, il ne se decoupe pas. Deux tentatives ont
    # gliss avant celle-ci, et chacune a ete dite par un rouge plutot que par
    # la relecture :
    #
    #   * borner par `# ---` prend tout le reste du fichier -- `code_du_script`
    #     retire les commentaires, donc la borne n'existe plus. La table de
    #     `commande_de_secours` entrait dans le balayage, et la frontiere
    #     rougissait sur du code juste ;
    #   * borner par le premier `exit 0` ne prend que 20 lignes : c'est la
    #     sortie de l'ISSUE 3, pas la fin du bloc.
    #
    # On prend donc l'aiguillage ET les fonctions qu'il appelle, nommement.
    debut = code.index('if [ "${DESINSTALLER}" -eq 1 ]')
    aiguillage = code[debut:]
    aiguillage = aiguillage[:aiguillage.index("exit 0") + len("exit 0")]
    lignes = aiguillage.splitlines()
    for fonction in ("retirer_selon_le_recu", "retirer_pipx_du_systeme",
                     "retirer_pipx_de_pip_utilisateur",
                     "retirer_le_repertoire_d_etat",
                     "avertir_du_cout_du_retrait_de_pipx"):
        lignes.extend(corps_de_fonction(code, fonction))
    bloc = "\n".join(lignes)
    assert len(lignes) > 40, (
        "le perimetre du retrait ne fait que %d lignes : le decoupage a "
        "glisse" % len(lignes))
    # ON NE BALAYE QUE CE QUI EST **AFFICHE**, jamais ce qui est EXECUTE. La
    # distinction n'est pas un raffinement : `executer brew uninstall pipx` est
    # le retrait reel et il DOIT vivre ici ; `info "  brew uninstall pipx"`
    # serait une recopie de la table. Ma premiere redaction confondait les
    # deux et accusait le produit d'un defaut qu'il n'a pas -- c'est le rouge
    # qui l'a dit.
    affichees = [l for l in lignes
                 if re.match(r'\s*(info|alerte|succes)\s', l)]
    assert len(affichees) >= 15, (
        "seulement %d lignes affichees dans le perimetre du retrait : le "
        "decoupage a glisse" % len(affichees))
    texte_affiche = "\n".join(affichees)
    for recopie in ("python.org/downloads", "https://ffmpeg.org",
                    "apt-get remove ffmpeg", "brew install"):
        assert recopie not in texte_affiche, (
            "une commande officielle est RECOPIEE dans un message du retrait "
            "(%r) au lieu de passer par `commande_de_secours` -- deux tables "
            "divergent au premier changement amont" % recopie)


def test_les_QUATRE_sites_d_ecriture_du_recu_APPELLENT_reellement_la_fonction():
    """`C3-2` -- la moitie pipx de l'AC2 n'etait mesuree que sur un MESSAGE.

    Mesure de la couche 3 : remplacer l'appel reel par `:` au site pipx laisse
    **159 verts**, parce que la seule assertion qui le couvre lit
    `"noter pipx-" in plan` -- c'est-a-dire la ligne `[simulation]`, pas
    l'ecriture. Idem cote PowerShell. Cela **contredit l'AC12 mot pour mot** :
    « rien de ce que la story ajoute n'est mesure sur du texte seul ».

    Le regime reel n'est pas exercable ici -- ecrire le recu pour pipx demande
    une installation reelle de pipx --, donc la frontiere est de STRUCTURE et
    le dit. Elle mesure ce qu'une frontiere de structure peut mesurer : que
    chacun des quatre producteurs APPELLE la fonction, dans une branche qui
    n'est PAS celle de la simulation.

    Le defaut qu'elle attrape est exactement celui de la revue 8.10 : une
    fonction ecrite, documentee, porteuse de sa propre anti-vacuite, et appelee
    par personne.
    """
    code = code_du_script(INSTALL_SH)
    appels = re.findall(r'^\s*noter_dans_le_recu\s+"([^"]+)"', code, re.M)
    assert len(appels) == 4, (
        "quatre sites d'ecriture du recu attendus (ffmpeg, ffprobe, python, "
        "pipx), %d releves : %r" % (len(appels), appels))
    assert {"ffmpeg", "ffprobe", "python"} <= set(appels), (
        "un producteur litteral a disparu : %r" % (appels,))
    assert any(a.startswith("pipx-") for a in appels), (
        "le site pipx n'appelle plus `noter_dans_le_recu` : l'issue 2 ne "
        "saurait plus que ce script a pose pipx, et le mandat d'Egan « tout "
        "supprimer » ne serait pas tenu. %r" % (appels,))

    # Cote PowerShell, la meme propriete -- et c'est la lecon de `C3-4` :
    # une fonction DEFINIE et jamais APPELEE est du code mort.
    ps1 = code_du_script(INSTALL_PS1)
    ecritures = len(re.findall(r'\bWrite-DansLeRecu\b', ps1))
    assert ecritures >= 3, (
        "`Write-DansLeRecu` est definie et presque jamais appelee dans "
        "install.ps1 (%d occurrences, definition comprise) : le recu Windows "
        "serait vide et l'issue 2 n'y retirerait rien" % ecritures)


# ============================================================================
#  STORY 8.14 -- detecter ce qui est POSE HORS DU `PATH` (`EPIC11-ARB-279`)
#
#  Le defaut d'Egan, verbatim : « si on choisi dans l'outil de faire la voie
#  "manuelle" pour toutes les dependances, le souci est que l'outil n'est pas
#  forcement ajoute au path et donc pas forcement detecte. » Constate en vrai
#  le 2026-09-08 : pipx pose a la main, non detecte, RECOMPILE.
# ============================================================================

#: Les fonctions du balayage, dans l'ordre ou elles doivent etre definies pour
#: pouvoir tourner seules. Le banc les EXTRAIT du produit -- il n'en recopie
#: aucune : une copie mesurerait la copie.
FONCTIONS_DU_BALAYAGE = (
    "lancer_avec_plafond",
    "drapeau_de_version",
    "python_assez_recent",
    "demarre_et_dit_sa_version",
    "plancher_tenu",
    "emplacements_usuels",
    "chercher_hors_du_path",
)

#: Les fonctions et les appelants qui composent le bloc « hors du PATH » cote
#: bash. Les frontieres NEGATIVES de l'AC1 et de l'AC5 balaient ce perimetre-la,
#: et il porte sa propre garde de non-vacuite : mordre sur son contre-exemple
#: et n'etre pas vide sont deux proprietes DISTINCTES (`T3-1` de la revue 8.12).
FONCTIONS_HORS_DU_PATH_BASH = FONCTIONS_DU_BALAYAGE + (
    "donner_la_ligne_de_profil",
    "offrir_les_trois_issues",
    "dire_le_trop_ancien",
    "chercher_python_hors_du_path",
)

#: Les fonctions du jumeau PowerShell. `pwsh` est absent du conteneur : elles
#: se mesurent en LECTURE, ce que ce banc fait d'`install.ps1` depuis toujours.
FONCTIONS_HORS_DU_PATH_PS = (
    "Get-EmplacementsUsuels",
    "Get-DrapeauDeVersion",
    "Invoke-AvecPlafond",
    "Find-HorsDuPath",
    "Test-PlancherTenu",
    "Show-LigneDeProfil",
    "Invoke-TroisIssuesHorsDuPath",
    "Show-TropAncien",
    "Write-CommandeDeSecours",
)

#: Les TROIS libelles et leur intitule, MOT POUR MOT des deux cotes (AC11).
LIBELLES_HORS_DU_PATH = (
    "l'utiliser pour cette installation, et me donner la ligne a ajouter a mon profil",
    "l'ignorer et installer quand meme une autre copie",
    "rien pour l'instant -- montre-moi la ligne de PATH et sors",
)
INTITULE_HORS_DU_PATH = "Que faut-il en faire ?"

#: Ce qu'une recherche NON BORNEE ressemblerait, des deux cotes. La frontiere
#: negative de l'AC1 les cherche dans le bloc, et le test qui suit verifie
#: qu'elle MORD sur chacune -- sans quoi elle serait verte par construction.
FORMES_DE_RECHERCHE_NON_BORNEE = (
    r"\bfind\s",
    r"\bls\s+-[a-zA-Z]*R",
    r"-exec\b",
    r"Get-ChildItem[^\n]*-Recurse",
    r"\bwhere\.exe\b",
    r"\bfd\s",
    r"globstar",
)

#: Ce qu'une ECRITURE DE PROFIL ressemblerait. Meme discipline : l'AC5 est une
#: frontiere negative, donc elle doit mordre ET balayer quelque chose.
FORMES_D_ECRITURE_DE_PROFIL = (
    r">>\s*\"?\$\{?PROFIL",
    # LE `>` SEUL, ET SEULEMENT SEUL. Sans le `(?<!>)`, ce motif attrape aussi
    # les `>>` du motif precedent, qui devient alors mort : le casser ne
    # rougirait nulle part. C'est le defaut `C1-7` retrouve DANS la liste
    # elle-meme, par la garde d'appariement, quelques minutes apres qu'elle
    # ait ete posee -- une redondance ne se voit pas a la relecture.
    r"(?<!>)>\s*\"?\$\{?PROFIL",
    r"\btee\b",
    r"\bensurepath\b",
    r"\bsetx\b",
    r"SetEnvironmentVariable",
    # `$PROFILE` NOMME n'est pas `$PROFILE` ECRIT (finding `C3-3` de la couche
    # 3, 2026-09-09). La premiere redaction interdisait le litteral, donc elle
    # interdisait aussi de DIRE a l'utilisateur ou poser sa ligne -- et
    # `Show-LigneDeProfil` rendait par consequent une ligne de SESSION
    # (`$env:Path = ...`) sans jamais nommer le fichier, la ou son jumeau bash
    # nomme `${PROFIL}`. L'AC11 promet le MEME contrat, et c'etait la moitie
    # qui EST le livrable de la story : « que je sache quelle ligne ajouter a
    # mon profil ».
    #
    # Ce qui est interdit est l'ECRITURE : `Add-Content`, `Set-Content`,
    # `Out-File` et les redirections vers `$PROFILE`. Le nommer dans un
    # message est ce que la story demande.
    r"(Add-Content|Set-Content|Out-File|>>?)\s*[^\n]*\$PROFILE",
    r"\$PROFILE\s*(\+=|=[^=])",
)


def _sans_commentaires(texte: str, dialecte: str) -> str:
    """Le meme texte, ses commentaires retires -- et RIEN d'autre.

    Les lignes sont conservees (VIDEES, pas supprimees) pour que les gardes de
    non-vacuite comptent le meme perimetre qu'avant : deballaster ne doit pas
    faire fondre le compte de lignes sous le plancher, ce qui transformerait
    une correction en panne de garde.

    Elle ne connait qu'un dialecte de commentaire, le `#`, qui est celui de
    `sh` ET de PowerShell ligne a ligne. Le bloc `<# ... #>` de PowerShell ne
    figure dans aucune des fonctions balayees ; s'il y entrait un jour, cette
    fabrique le laisserait passer -- dit ici plutot que tu.
    """
    sortie = []
    for ligne in texte.splitlines():
        sortie.append("" if ligne.strip().startswith("#") else ligne)
    return "\n".join(sortie)


def _fonction_bash_brute(nom: str) -> str:
    """Le TEXTE du produit pour une fonction, commentaires compris.

    Brut et non `code_du_script` : ce texte-la est REJOUE par le harnais de
    l'AC8, et un commentaire de bash n'a jamais gene bash. Ce qui compte est
    que ce soit le code DU PRODUIT et pas une copie -- une copie mesurerait
    la copie, ce qui est exactement le mode de panne que la story 5.8 a paye.
    """
    lignes = INSTALL_SH.read_text().splitlines()
    debuts = [i for i, ligne in enumerate(lignes) if ligne == "%s() {" % nom]
    assert len(debuts) == 1, (
        "install.sh ne definit plus `%s` comme ce banc l'attend (%d "
        "occurrence(s))." % (nom, len(debuts)))
    for fin in range(debuts[0] + 1, len(lignes)):
        if lignes[fin] == "}":
            return "\n".join(lignes[debuts[0]:fin + 1])
    raise AssertionError("`%s` ne se referme jamais en colonne zero" % nom)


def _fin_de_la_decision(lignes: list, depart: int) -> int:
    """L'indice de fin du bloc `if ... fi` qui suit `depart`, borne comprise.

    Rend `depart + 26` -- l'ancien nombre magique -- quand aucun `if` ne suit
    dans les dix lignes : un site d'appel qui ne decide de rien garde alors le
    comportement d'avant, plutot qu'un balayage vide.
    """
    profondeur = 0
    vu_un_if = False
    for j in range(depart, min(len(lignes), depart + 200)):
        nu = lignes[j].strip()
        if not vu_un_if and j > depart + 10:
            break
        if nu.startswith("if ") or nu.startswith("if["):
            profondeur += 1
            vu_un_if = True
        elif nu == "fi" or nu.startswith("fi "):
            profondeur -= 1
            if vu_un_if and profondeur <= 0:
                return j + 1
    return depart + 26


def _appelants_hors_du_path_bash() -> str:
    """Le BLOC APPELANT de l'etat des lieux, entre son etape et l'affichage.

    `C3-1` de la couche 3 (2026-09-09) -- et c'est le trou que le commentaire
    de `FONCTIONS_HORS_DU_PATH_BASH` annoncait pourtant fermer : il promet
    « les fonctions ET LES APPELANTS », et le perimetre ne portait que les
    onze fonctions.

    Mesure de la couche : un `find / -name pipx` ecrit dans le bloc appelant
    de pipx rend **zero rouge sur trente-trois**. C'est nommement ce
    qu'`EPIC11-ARB-279` interdit, et aucun test positif ne le verrait revenir
    -- une frontiere negative qui ne balaye pas la ou le defaut peut vivre est
    verte par construction, ce qui est le mode de panne le plus silencieux
    qu'une frontiere puisse avoir.
    """
    # LE PERIMETRE SE PREND AUTOUR DES APPELS, PAS SUR L'ETAPE ENTIERE. Ma
    # premiere redaction bornait de `etape "Etat des lieux"` a
    # `if affichage_disponible` : elle avalait toute l'installation, qui
    # contient legitimement un `find`, un `pipx ensurepath` et un
    # `noter_dans_le_recu`. Trois frontieres ont rougi sur du code juste --
    # et un rouge qui se trompe est pire que pas de frontiere, ce que
    # l'en-tete de ce module dit deja.
    #
    # On prend donc, autour de CHAQUE site d'appel de la recherche, la fenetre
    # qui porte sa decision. C'est la ou le defaut de `C3-1` peut vivre.
    lignes = INSTALL_SH.read_text().splitlines()
    sites = [i for i, l in enumerate(lignes)
             if "chercher_hors_du_path" in l or "chercher_python_hors_du_path" in l]
    sites = [i for i in sites if not lignes[i].rstrip().endswith("() {")]
    assert len(sites) >= 4, (
        "seulement %d site(s) d'appel de la recherche hors du PATH releve(s) : "
        "le perimetre a fondu" % len(sites))
    # LA FENETRE VA JUSQU'AU BOUT DE LA DECISION, ET NON A UN NOMBRE DE LIGNES
    # (finding `C1-3` / mutant `M26` de la couche 1, 2026-09-09). Un `+ 26`
    # est un nombre magique : il tombait juste sur les quatre sites du jour et
    # ratait la branche Python, plus longue que les autres. Une ecriture de
    # profil glissee la survivait aux 196.
    #
    # La regle exacte, qui ne se regle pas : on part six lignes avant l'appel,
    # on avance jusqu'au premier `if` qui suit, puis on suit sa PROFONDEUR
    # jusqu'au `fi` qui la referme. Ce qui borne le balayage est la structure
    # du produit, pas un compte que la prochaine branche fera mentir.
    fenetres = []
    for i in sites:
        fin = _fin_de_la_decision(lignes, i)
        fenetres.extend(lignes[max(0, i - 6):fin])
    return "\n".join(fenetres)


def _bloc_hors_du_path_bash() -> str:
    """Le perimetre balaye par les frontieres negatives de l'AC1 et de l'AC5.

    Les onze fonctions **ET** le bloc appelant : le defaut peut vivre dans
    l'un comme dans l'autre, et il vivait dans celui que le perimetre sautait.
    """
    return "\n".join([_fonction_bash_brute(nom)
                      for nom in FONCTIONS_HORS_DU_PATH_BASH]
                     + [_appelants_hors_du_path_bash()])


def _bloc_hors_du_path_ps() -> str:
    """Le meme perimetre cote PowerShell, decoupe sur ses `function`."""
    lignes = INSTALL_PS1.read_text().splitlines()
    morceaux = []
    for nom in FONCTIONS_HORS_DU_PATH_PS:
        debuts = [i for i, ligne in enumerate(lignes)
                  if ligne.startswith("function %s " % nom)
                  or ligne == "function %s {" % nom]
        assert len(debuts) == 1, (
            "install.ps1 ne definit plus `%s` comme ce banc l'attend (%d "
            "occurrence(s))." % (nom, len(debuts)))
        for fin in range(debuts[0] + 1, len(lignes)):
            if lignes[fin] == "}":
                morceaux.append("\n".join(lignes[debuts[0]:fin + 1]))
                break
        else:
            raise AssertionError("`%s` ne se referme jamais en colonne zero" % nom)

    # LE BLOC APPELANT AUSSI, comme cote bash (finding `C1-3` de la couche 1).
    # Le perimetre ne portait que les fonctions enumerees ; le code appelant en
    # ligne -- ou vit la branche Python hors du PATH -- en etait dehors, et une
    # ecriture de profil glissee la y survivait.
    sites = [i for i, l in enumerate(lignes)
             if ("Find-HorsDuPath" in l or "Find-PythonHorsDuPath" in l)
             and not l.startswith("function ")]
    assert len(sites) >= 3, (
        "seulement %d site(s) d'appel de la recherche hors du PATH releve(s) "
        "dans install.ps1 : le perimetre a fondu" % len(sites))
    for i in sites:
        morceaux.append("\n".join(lignes[max(0, i - 6):i + 30]))
    return "\n".join(morceaux)


# ------------------------------------------- AC1 : la liste BORNEE, a UN endroit

def test_la_liste_des_emplacements_vit_a_UN_SEUL_endroit():
    """AC1 -- « et elle vit a UN SEUL endroit dans le script ».

    Le motif est celui qui a fait naitre `commande_de_secours` : un remede
    recopie a cinq endroits diverge. Ici c'est pire qu'une divergence de
    message -- deux listes d'emplacements qui divergent, c'est un outil trouve
    par un chemin du script et pas par l'autre.
    """
    code = code_du_script(INSTALL_SH)
    corps = _fonction_bash_brute("emplacements_usuels")

    # Les emplacements de l'arbitrage, par systeme.
    for emplacement in ("/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin",
                        "/snap/bin", "/var/lib/flatpak/exports/bin",
                        "${HOME}/.local/bin"):
        assert emplacement in corps, (
            "`emplacements_usuels` ne porte plus %r : la liste "
            "d'`EPIC11-ARB-279` a fondu" % emplacement)

    # ... et NULLE PART AILLEURS dans le script. `${HOME}/.local/bin` est la
    # seule exception, et elle est nommee : `repertoire_binaire_de_pipx` et le
    # repli pipx l'emploient comme DEFAUT DE PIPX, ce qui est un autre role.
    hors_de_la_liste = code.replace(corps, "")
    for emplacement in ("/opt/homebrew/bin", "/opt/local/bin", "/snap/bin",
                        "/var/lib/flatpak/exports/bin"):
        assert emplacement not in hors_de_la_liste, (
            "%r est ecrit AILLEURS que dans `emplacements_usuels` : la liste "
            "est desormais a deux endroits, et ils divergeront" % emplacement)


def test_AUCUNE_recherche_recursive_dans_le_bloc_hors_du_PATH():
    """AC1, frontiere NEGATIVE -- « Jamais un `find`, jamais une recherche
    recursive », verbatim d'`EPIC11-ARB-279`.

    Le motif n'est pas le gout : une recherche non bornee sur une machine
    pleine est un temps infini, et ce depot a deja paye cette famille -- la
    boucle de sauvetage non bornee de `decode_qr_image_resilient` partait en
    temps infini quand les images etaient des pointeurs LFS, et la dette
    « `test_scan_detect_command.py` suspend » n'a jamais ete une dette de code.

    Aucun test POSITIF ne verrait revenir un `find` : le script marcherait, et
    il suspendrait l'installation d'un utilisateur dont le disque est plein.
    """
    # NOMMER LA CHOSE INTERDITE N'EST PAS LA FAIRE (finding `C1-8`, 2026-09-09,
    # et c'est la DEUXIEME occurrence de cette famille apres `C3-3` : la
    # premiere redaction de l'AC5 interdisait le litteral `$PROFILE`, donc elle
    # interdisait de DIRE a l'utilisateur ou poser sa ligne). Ici, le
    # commentaire qui explique pourquoi `where.exe /R` est proscrit faisait
    # rougir la frontiere qui le proscrit. Un commentaire ne balaie aucun
    # disque et n'ecrit aucun profil : le perimetre se lit deballaste.
    perimetres = {"install.sh": _sans_commentaires(_bloc_hors_du_path_bash(), "sh"),
                  "install.ps1": _sans_commentaires(_bloc_hors_du_path_ps(), "ps1")}
    for nom, perimetre in perimetres.items():
        # LA GARDE DE NON-VACUITE, et elle vaut autant que l'assertion.
        lignes = [l for l in perimetre.splitlines() if l.strip()]
        assert len(lignes) > 60, (
            "%s : le perimetre balaye ne fait que %d lignes. La frontiere "
            "negative serait verte sans rien mesurer." % (nom, len(lignes)))
        for forme in FORMES_DE_RECHERCHE_NON_BORNEE:
            assert re.search(forme, perimetre) is None, (
                "%s : une recherche non bornee (%r) est revenue dans le bloc "
                "hors du PATH -- c'est ce qu'`EPIC11-ARB-279` interdit "
                "nommement" % (nom, forme))


#: **Un `any` couple les CARDINAUX, jamais les PAIRES** (finding `C1-7` de la
#: couche 1, 2026-09-09). Les deux tests « MORD » ci-dessous se contentaient
#: d'`assert len(contre_exemples) == len(FORMES)` puis d'un `any(...)` : casser
#: `-exec\b` ou `>>\s*"?\$\{?PROFIL` les laissait VERTS, un autre motif
#: mordant a la place du motif casse. C'est la regle des fabriques appliquee
#: aux motifs -- un appariement positionnel qu'aucun test ne verifie.
#:
#: La propriete qui tient, et c'est celle que le mutant teste : **retirer le
#: motif d'indice `i` doit laisser passer le contre-exemple d'indice `i`**.
#: Elle exige que chaque contre-exemple ISOLE son motif -- c'est pourquoi le
#: contre-exemple d'`-exec` ne peut plus porter un `find`, qui le couvrait.
def _chaque_motif_est_NECESSAIRE(formes, contre_exemples, quoi):
    assert len(contre_exemples) == len(formes), (
        "%s : %d contre-exemples pour %d motifs -- l'appariement est rompu"
        % (quoi, len(contre_exemples), len(formes)))
    for i, (forme, contre_exemple) in enumerate(zip(formes, contre_exemples)):
        assert re.search(forme, contre_exemple), (
            "%s : le motif %r ne mord pas sur SON contre-exemple %r"
            % (quoi, forme, contre_exemple))
        sans_lui = [f for j, f in enumerate(formes) if j != i]
        assert not any(re.search(f, contre_exemple) for f in sans_lui), (
            "%s : le contre-exemple %r est attrape par un AUTRE motif que %r. "
            "Casser %r laisserait donc le banc vert -- c'est le defaut `C1-7`."
            % (quoi, contre_exemple, forme, forme))


def test_cette_frontiere_de_BALAYAGE_MORD_sur_ses_contre_exemples():
    """`T3-1` -- mordre et etre non vacante sont deux proprietes DISTINCTES.

    La frontiere ci-dessus est negative : elle est verte quand tout va bien,
    donc rien ne prouve d'elle-meme qu'elle sait rougir. On lui donne les sept
    formes, une par une, dans un perimetre par ailleurs sain.
    """
    sain = _bloc_hors_du_path_bash()
    contre_exemples = (
        'find / -name pipx 2>/dev/null',
        'ls -R /usr',
        # ISOLE, sans `find` : il portait `find "${HOME}" -exec ...`, donc
        # `\bfind\s` le couvrait et `-exec\b` pouvait etre casse sans que
        # rien ne rougisse.
        r'-exec echo {} \;',
        'Get-ChildItem -Path C:\\ -Recurse -Filter pipx.exe',
        'where.exe /R C:\\ pipx.exe',
        'fd pipx /',
        'shopt -s globstar; echo /**/pipx',
    )
    _chaque_motif_est_NECESSAIRE(FORMES_DE_RECHERCHE_NON_BORNEE, contre_exemples,
                                 "balayage")
    # ... et le perimetre SAIN, lui, reste muet : un contre-exemple qui mordrait
    # deja sans pollution ne mesurerait rien.
    for contre_exemple in contre_exemples:
        pollue = _sans_commentaires(sain, "sh") + "\n" + contre_exemple + "\n"
        assert any(re.search(forme, pollue) for forme in FORMES_DE_RECHERCHE_NON_BORNEE), (
            "la frontiere de balayage ne mord pas sur %r : elle est verte par "
            "construction" % contre_exemple)


# ------------------------------- AC5 : n'ECRIT JAMAIS dans un profil de shell

def test_le_bloc_hors_du_PATH_n_ECRIT_dans_AUCUN_profil():
    """AC5, frontiere NEGATIVE -- « le script n'ECRIT JAMAIS dans un profil de
    lui-meme sur ce chemin ».

    Il met le repertoire sur le `PATH` du PROCESSUS et DONNE la ligne. La seule
    ecriture de profil du produit reste celle de `pipx ensurepath`, qui vit
    ailleurs et que l'utilisateur a explicitement acceptee par la question du
    PATH -- laquelle NOMME le fichier touche.

    Cote Windows la meme chose s'ecrirait `setx`, `$PROFILE` ou
    `[Environment]::SetEnvironmentVariable(..., 'User')` : les trois sont
    cherchees, parce qu'un jumeau qui divergerait sur ce point-la donnerait
    deux produits differents a deux utilisateurs qui lisent la meme page.
    """
    # NOMMER LA CHOSE INTERDITE N'EST PAS LA FAIRE (finding `C1-8`, 2026-09-09,
    # et c'est la DEUXIEME occurrence de cette famille apres `C3-3` : la
    # premiere redaction de l'AC5 interdisait le litteral `$PROFILE`, donc elle
    # interdisait de DIRE a l'utilisateur ou poser sa ligne). Ici, le
    # commentaire qui explique pourquoi `where.exe /R` est proscrit faisait
    # rougir la frontiere qui le proscrit. Un commentaire ne balaie aucun
    # disque et n'ecrit aucun profil : le perimetre se lit deballaste.
    perimetres = {"install.sh": _sans_commentaires(_bloc_hors_du_path_bash(), "sh"),
                  "install.ps1": _sans_commentaires(_bloc_hors_du_path_ps(), "ps1")}
    for nom, perimetre in perimetres.items():
        lignes = [l for l in perimetre.splitlines() if l.strip()]
        assert len(lignes) > 60, (
            "%s : le perimetre balaye ne fait que %d lignes -- la frontiere "
            "serait verte sans rien mesurer." % (nom, len(lignes)))
        for forme in FORMES_D_ECRITURE_DE_PROFIL:
            assert re.search(forme, perimetre) is None, (
                "%s : le bloc hors du PATH ecrit dans un profil (%r). L'AC5 "
                "l'interdit : il DONNE la ligne, il ne la pose pas." % (nom, forme))


def test_cette_frontiere_de_PROFIL_MORD_sur_ses_contre_exemples():
    """L'autre sens, sans lequel la precedente serait verte par construction."""
    sain = _bloc_hors_du_path_bash()
    contre_exemples = (
        'printf "export PATH=..." >> "${PROFIL}"',
        'printf "export PATH=..." > "${PROFIL}"',
        'echo "export PATH=..." | tee -a ~/.bashrc',
        'pipx ensurepath',
        'setx PATH "$env:Path;C:\\outils"',
        "[Environment]::SetEnvironmentVariable('Path', $p, 'User')",
        'Add-Content -Path $PROFILE -Value $ligne',
        # La seconde forme d'ECRITURE de profil, ajoutee avec la distinction
        # nommer / ecrire (`C3-3`) : une AFFECTATION au profil.
        '$PROFILE = "C:\\ailleurs\\profil.ps1"',
    )
    _chaque_motif_est_NECESSAIRE(FORMES_D_ECRITURE_DE_PROFIL, contre_exemples,
                                 "profil")
    for contre_exemple in contre_exemples:
        pollue = _sans_commentaires(sain, "sh") + "\n" + contre_exemple + "\n"
        assert any(re.search(forme, pollue) for forme in FORMES_D_ECRITURE_DE_PROFIL), (
            "la frontiere de profil ne mord pas sur %r" % contre_exemple)

    # LE VOLET SYMETRIQUE, et il vaut autant : NOMMER un profil n'est pas y
    # ECRIRE. Sans lui, la frontiere se durcirait jusqu'a interdire ce que la
    # story EXIGE -- dire a l'utilisateur ou poser sa ligne. C'est le defaut
    # exact que `C3-3` a mesure : le litteral etait interdit, donc
    # `Show-LigneDeProfil` rendait une ligne de session sans jamais nommer le
    # fichier, et l'utilisateur Windows la perdait a la fermeture du terminal.
    for forme_juste in ('Write-Info ("... la poser dans ton profil : " + \'$PROFILE\')',
                        'info "  La ligne a ajouter dans ${PROFIL} :"'):
        assert not any(re.search(forme, forme_juste)
                       for forme in FORMES_D_ECRITURE_DE_PROFIL), (
            "la frontiere accuse une ligne qui NOMME le profil sans y ecrire : "
            "%r. C'est ce que la story demande, pas ce qu'elle interdit."
            % forme_juste)


# ---------------------------- AC12 : ce que la story NE fait PAS, mesure aussi

def test_la_recherche_hors_du_PATH_n_ecrit_RIEN_au_RECU():
    """AC12 -- un binaire pose par l'UTILISATEUR n'appartient pas a ce script.

    C'est la raison 2 d'`EPIC11-ARB-274` : l'issue 2 de la desinstallation ne
    retire QUE ce qu'un recu enregistre, et elle ne doit jamais reprendre un
    outil que le script n'a pas pose. Un `noter_dans_le_recu` glisse dans ce
    bloc rendrait la desinstallation destructrice pour un tiers.
    """
    perimetre = _bloc_hors_du_path_bash()
    assert "noter_dans_le_recu" not in perimetre, (
        "la recherche hors du PATH ecrit au recu : la desinstallation "
        "reprendrait un binaire que l'utilisateur a pose lui-meme")
    ps = _bloc_hors_du_path_ps()
    assert "Write-DansLeRecu" not in ps, (
        "install.ps1 ecrit au recu depuis la recherche hors du PATH")


def test_la_recherche_hors_du_PATH_REEMPLOIE_le_plafond_de_lancement():
    """AC2 -- « sous le meme plafond de temps que le repli precompile ».

    `lancer_avec_plafond` EXISTE depuis le triage de la story 8.11. En ecrire
    une seconde la ferait diverger -- et celle-ci porte la regle 6 de
    `CLAUDE.md` : elle tue par PID capture au lancement, jamais par motif. Une
    copie ecrite a la va-vite reintroduirait un `pkill`.
    """
    code = code_du_script(INSTALL_SH)
    assert code.count("lancer_avec_plafond() {") == 1, (
        "il y a plus d'une definition de `lancer_avec_plafond` : elles vont "
        "diverger, et l'une des deux tuera par motif")
    # `code_du_script` ET NON le texte brut : le brut garde les commentaires,
    # et la couche 3 l'a mesure -- un appel direct au binaire, les deux noms
    # laisses en `# jadis : lancer_avec_plafond ...`, rendait ZERO rouge.
    # Une frontiere qu'un commentaire satisfait ne mesure pas le produit,
    # elle mesure sa prose.
    corps = "\n".join(corps_de_fonction(code, "demarre_et_dit_sa_version"))
    assert len(corps.splitlines()) > 5, (
        "le corps de `demarre_et_dit_sa_version` ne fait que %d lignes une "
        "fois les commentaires retires : le decoupage a glisse"
        % len(corps.splitlines()))
    assert "lancer_avec_plafond" in corps, (
        "le binaire trouve hors du PATH n'est plus lance sous plafond : un "
        "binaire qui suspend suspendra l'installateur, sans un mot")
    assert "PLAFOND_DE_LANCEMENT" in corps, (
        "le plafond employe n'est plus celui du repli precompile")
    # Et jamais par motif, des deux cotes (regle 6).
    for nom, perimetre in (("install.sh", _bloc_hors_du_path_bash()),
                           ("install.ps1", _bloc_hors_du_path_ps())):
        for motif in (r"\bpkill\b", r"killall", r"Get-Process\s+-Name"):
            assert re.search(motif, perimetre) is None, (
                "%s : le bloc hors du PATH tue par RESSEMBLANCE (%r) -- "
                "c'est la regle 6 de CLAUDE.md" % (nom, motif))


# ------------------------------- AC11 : install.ps1 recoit le MEME contrat

def test_les_deux_scripts_emploient_les_MEMES_libelles_hors_du_PATH():
    """AC11 -- « Les LIBELLES des issues sont les memes des deux cotes ».

    Meme frontiere que celle des trois issues de la desinstallation, et pour
    la meme raison : deux utilisateurs qui lisent la meme documentation et
    voient deux menus differents n'ont pas le meme produit.
    """
    bash = INSTALL_SH.read_text()
    ps = INSTALL_PS1.read_text()
    for libelle in LIBELLES_HORS_DU_PATH + (INTITULE_HORS_DU_PATH,):
        assert libelle in bash, "install.sh ne porte plus %r" % libelle
        assert libelle in ps, (
            "install.ps1 a derive du libelle de bash : %r" % libelle)


def test_install_ps1_APPELLE_ses_fonctions_hors_du_PATH_et_pas_seulement_les_DEFINIT():
    """AC11 -- `C3-4` de la revue 8.12, applique a cette story.

    `pwsh` est absent du conteneur, mais un CABLAGE se mesure en LECTURE : une
    fonction DEFINIE et jamais APPELEE est du code mort, et le banc de la 8.12
    a mesure que commenter l'appel rendait ZERO rouge. Le contrat Windows de
    cette story serait sinon un decor.
    """
    code = code_du_script(INSTALL_PS1)
    for nom in FONCTIONS_HORS_DU_PATH_PS:
        definitions = len(re.findall(r'^\s*function\s+%s\b' % re.escape(nom),
                                     code, re.M | re.I))
        assert definitions == 1, (
            "%s : %d definition(s), une seule attendue" % (nom, definitions))
        occurrences = len(re.findall(r'\b%s\b' % re.escape(nom), code))
        assert occurrences >= 2, (
            "`%s` est DEFINIE et jamais APPELEE dans install.ps1 : le contrat "
            "de la story 8.14 y est du code mort" % nom)


def test_install_ps1_definit_ses_fonctions_hors_du_PATH_AVANT_de_s_en_servir():
    """AC11 -- la panne d'ORDRE, jumelle de celle de `Get-PythonConvenable`.

    PowerShell ne definit une fonction qu'au moment ou sa definition
    s'EXECUTE. Une fonction du balayage ecrite APRES l'etat des lieux rendrait
    « n'est pas reconnu comme nom d'applet de commande » -- une panne d'ordre,
    pas de logique, et qu'aucune frontiere de DEFINITION ne verrait.
    """
    lignes = INSTALL_PS1.read_text().splitlines()
    etat_des_lieux = [i for i, l in enumerate(lignes)
                      if l.strip() == 'Write-Etape "Etat des lieux"']
    assert len(etat_des_lieux) == 1, (
        "le decoupage d'install.ps1 a change : %d « Etat des lieux »"
        % len(etat_des_lieux))
    for nom in FONCTIONS_HORS_DU_PATH_PS:
        definition = [i for i, l in enumerate(lignes)
                      if l.startswith("function %s " % nom)
                      or l == "function %s {" % nom]
        assert definition, "install.ps1 ne definit plus `%s`" % nom
        assert definition[0] < etat_des_lieux[0], (
            "`%s` est definie APRES l'etat des lieux qui l'appelle : "
            "PowerShell rendrait « n'est pas reconnu »" % nom)


# --------- AC8 : la regle des fabriques, appliquee a la COLLECTION balayee

#: Un binaire factice qui DIT d'ou il vient. Deux emplacements ne sont
#: « distinguables » que si ce qu'ils portent differe : un remplissage
#: uniforme rend invisible toute erreur d'appariement (regle des fabriques,
#: point 1). Ici la difference est la VERSION annoncee, et le verdict porte
#: dessus autant que sur le chemin.
#: `__MARQUE__` est substitue par `.replace` et non par un `%` : ce texte
#: porte une directive `printf` du shell (`%s`), qu'un formatage Python
#: mangerait -- mesure a l'ecriture de ce banc.
BINAIRE_QUI_DIT_D_OU_IL_VIENT = (
    "#!/bin/sh\n"
    "case \"$1\" in\n"
    "  --version|-version) printf 'outil %s\\n' '__MARQUE__' ;;\n"
    "esac\n"
    "exit 0\n"
)


def _binaire_marque(marque: str) -> str:
    """Un binaire factice qui ANNONCE d'ou il vient."""
    return BINAIRE_QUI_DIT_D_OU_IL_VIENT.replace("__MARQUE__", marque)


def _declarations_du_produit(*noms) -> str:
    """Les lignes d'affectation du PRODUIT pour ces constantes, verbatim.

    Une seule occurrence exigee par nom : deux affectations d'une meme
    constante dans `install.sh` rendraient le harnais dependant de laquelle
    gagne, ce qui est precisement l'ambiguite qu'on veut interdire.
    """
    texte = INSTALL_SH.read_text()
    lignes = []
    for nom in noms:
        trouvees = re.findall(r"^%s=.*$" % re.escape(nom), texte, re.M)
        assert len(trouvees) == 1, (
            "`%s` est affectee %d fois dans install.sh : le harnais ne sait "
            "plus laquelle rejouer" % (nom, len(trouvees)))
        lignes.append(trouvees[0])
    return "\n".join(lignes) + "\n"


def _texte_du_harnais(emplacements, nom="outil") -> str:
    """Le script qui rejoue le balayage DU PRODUIT sur une collection donnee.

    Aucun operateur `%` n'est applique a ce texte : il porte des directives
    `printf` du shell (`%s`), et un formatage Python les mangerait. La seule
    interpolation est celle de la liste, faite par concatenation.
    """
    liste = " ".join("'" + str(chemin) + "'" for chemin in emplacements)
    extraits = "\n\n".join(_fonction_bash_brute(nom)
                            for nom in FONCTIONS_DU_BALAYAGE)
    return (
        "set -euo pipefail\n"
        # LES CONSTANTES SE LISENT DANS LE PRODUIT, ELLES NE SE RECOPIENT PAS
        # (2026-09-09, decouvert en derivant le plancher de Python de
        # `PYTHON_MINIMUM` : le harnais rejouait `python_assez_recent` sans
        # jamais porter la constante dont il depend, donc `int('')` levait et
        # tout Python passait pour trop ancien).
        #
        # Ce que ca a revele est plus large que la panne : `PLAFOND_DE_LANCEMENT`
        # et `FFMPEG_MAJEUR_MINIMUM` etaient RECOPIES ici. Le produit pouvait
        # donc changer son plancher ffmpeg sans qu'un seul test bouge -- le
        # harnais aurait continue de mesurer 5. C'est litteralement « un remede
        # recopie a cinq endroits diverge », applique a un banc.
        + _declarations_du_produit("PLAFOND_DE_LANCEMENT",
                                   "FFMPEG_MAJEUR_MINIMUM",
                                   "PYTHON_MINIMUM")
        + "CHERCHER_HORS_DU_PATH=1\n"
        "SYSTEME=linux\n"
        "TROUVE_HORS_DU_PATH=''\n"
        "REPERTOIRE_HORS_DU_PATH=''\n"
        "TROP_ANCIEN_HORS_DU_PATH=''\n"
        "VERSION_HORS_DU_PATH=''\n"
        + extraits + "\n\n"
        # LA SUBSTITUTION, apres les definitions du produit.
        "emplacements_usuels() { printf '%s\\n' " + liste + "; }\n"
        "issue=0\n"
        "chercher_hors_du_path " + nom + " || issue=$?\n"
        "printf 'ISSUE=%s\\n' \"${issue}\"\n"
        "printf 'TROUVE=%s\\n' \"${TROUVE_HORS_DU_PATH}\"\n"
        "printf 'VERSION=%s\\n' \"${VERSION_HORS_DU_PATH}\"\n"
        "printf 'ANCIEN=%s\\n' \"${TROP_ANCIEN_HORS_DU_PATH}\"\n"
    )


def _harnais_du_balayage(tmp_path: Path, marques, ou_est_la_cible):
    """Joue LE balayage DU PRODUIT sur une collection d'emplacements fabriquee.

    **Le code joue est celui du produit, extrait de `install.sh`** -- pas une
    copie. `install.sh` s'execute de bout en bout et ne peut pas se `source`
    (son analyse d'arguments est en tete), donc le seul acces a une FONCTION
    isolee est l'extraction de son texte. C'est ce que fait
    `_fonction_bash_brute`, et la garde de non-vacuite est dans cette fonction :
    elle exige exactement une definition et un `}` en colonne zero.

    `emplacements_usuels` est REDEFINIE apres coup, et c'est le seul point ou
    ce harnais s'ecarte du produit : la vraie liste porte des chemins ABSOLUS
    du systeme (`/usr/local/bin`, `/snap/bin`) qu'aucun banc ne gouverne. La
    substitution ne change ni le balayage, ni le lancement, ni le plancher --
    c'est-a-dire rien de ce que l'AC8 mesure.

    `marques` nomme les emplacements dans l'ORDRE ; `ou_est_la_cible` dit
    lesquels portent le binaire.
    """
    racine = tmp_path / "collection"
    racine.mkdir(exist_ok=True)
    emplacements = []
    for marque in marques:
        repertoire = racine / marque
        repertoire.mkdir(exist_ok=True)
        emplacements.append(repertoire)
        if marque in ou_est_la_cible:
            cible = repertoire / "outil"
            cible.write_text(_binaire_marque(marque))
            cible.chmod(0o755)

    harnais = tmp_path / "harnais.sh"
    harnais.write_text(_texte_du_harnais(emplacements))
    acheve = subprocess.run(["/bin/bash", str(harnais)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=DELAI, cwd=str(tmp_path))
    sortie = acheve.stdout.decode("utf-8", "replace")
    rendu = {}
    for ligne in sortie.splitlines():
        if "=" in ligne and ligne.split("=", 1)[0] in ("ISSUE", "TROUVE",
                                                       "VERSION", "ANCIEN"):
            cle, valeur = ligne.split("=", 1)
            rendu[cle] = valeur
    assert set(rendu) == {"ISSUE", "TROUVE", "VERSION", "ANCIEN"}, (
        "le harnais du balayage n'a pas rendu son verdict -- il ne mesure "
        "rien :\n" + sortie)
    return rendu


#: Trois emplacements DISTINGUABLES, et la cible se place a chacun d'eux.
#: `tete` demasque un balayage qui rendrait toujours le dernier ; `milieu`
#: demasque un `find` fautif qui rendrait toujours le premier (point 2) ;
#: `queue` demasque un balayage TRONQUE, qui est un AUTRE mode de panne
#: (point 4, pose le 2026-09-03). « Au milieu » ne suffit pas seul.
MARQUES_DE_LA_COLLECTION = ("tete", "milieu", "queue")


@pytest.mark.parametrize("ou", MARQUES_DE_LA_COLLECTION)
def test_le_balayage_trouve_la_cible_a_CHAQUE_position(tmp_path, ou):
    """AC8 -- regle des fabriques, points 1, 2 et 4.

    Trois elements DISTINGUABLES : chaque binaire annonce le nom de son
    emplacement, donc le verdict ne porte pas seulement sur « quelque chose a
    ete trouve » mais sur LEQUEL. Un remplissage uniforme rendrait la
    permutation invisible -- c'est le mutant `M33` de la story 5.6.
    """
    rendu = _harnais_du_balayage(tmp_path, MARQUES_DE_LA_COLLECTION, {ou})
    assert rendu["ISSUE"] == "0", (
        "la cible en %s n'a pas ete trouvee : le balayage saute cette "
        "position" % ou)
    assert rendu["TROUVE"].endswith("/%s/outil" % ou), rendu
    assert rendu["VERSION"] == "outil %s" % ou, (
        "le balayage rend un chemin de %s mais la version d'un autre "
        "emplacement : l'appariement est faux" % ou)


def test_le_balayage_prend_LE_PREMIER_quand_plusieurs_portent_la_cible(tmp_path):
    """AC8 -- l'autre sens : l'ORDRE de la liste decide.

    Sans ce cas, un balayage qui rendrait le DERNIER trouve passerait les trois
    precedents -- chacun n'a qu'une cible, donc « premier » et « dernier » y
    sont le meme element. C'est exactement le remplissage uniforme, deguise.
    """
    rendu = _harnais_du_balayage(tmp_path, MARQUES_DE_LA_COLLECTION,
                                 set(MARQUES_DE_LA_COLLECTION))
    assert rendu["TROUVE"].endswith("/tete/outil"), (
        "le balayage ne respecte pas l'ordre de la liste bornee : %r" % rendu)
    assert rendu["VERSION"] == "outil tete", rendu


def test_le_balayage_rend_RIEN_quand_la_collection_ne_porte_RIEN(tmp_path):
    """La garde de NON-VACUITE des trois cas ci-dessus.

    Un harnais casse -- extraction vide, substitution qui ne prend pas --
    rendrait « rien trouve » partout, et les assertions de position
    rougiraient. Celle-ci ferme l'autre moitie : elle prouve que « rien
    trouve » est un verdict que ce harnais sait rendre, et non son seul
    verdict possible.
    """
    rendu = _harnais_du_balayage(tmp_path, MARQUES_DE_LA_COLLECTION, set())
    assert rendu["ISSUE"] == "1", rendu
    assert rendu["TROUVE"] == "", rendu


def test_le_balayage_ECARTE_un_lien_CASSE_et_un_binaire_qui_ne_DEMARRE_PAS(tmp_path):
    """AC2 -- « un fichier present ne prouve ni son architecture, ni sa
    version, ni qu'il n'est pas un lien casse ».

    Deux formes de la meme panne, et la cible valide est en QUEUE : un
    balayage qui s'arreterait au premier fichier PRESENT -- sans le lancer --
    rendrait le lien casse et s'arreterait la.
    """
    racine = tmp_path / "collection"
    racine.mkdir()
    casse = racine / "casse"
    casse.mkdir()
    (casse / "outil").symlink_to(racine / "nulle_part")
    muet = racine / "muet"
    muet.mkdir()
    (muet / "outil").write_text("#!/bin/sh\nexit 3\n")
    (muet / "outil").chmod(0o755)
    bon = racine / "bon"
    bon.mkdir()
    (bon / "outil").write_text(_binaire_marque("bon"))
    (bon / "outil").chmod(0o755)

    harnais = tmp_path / "harnais_ecarte.sh"
    harnais.write_text(_texte_du_harnais([casse, muet, bon]))
    acheve = subprocess.run(["/bin/bash", str(harnais)], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=DELAI, cwd=str(tmp_path))
    sortie = acheve.stdout.decode("utf-8", "replace")
    assert "ISSUE=0" in sortie, sortie
    assert "TROUVE=%s/outil" % bon in sortie, (
        "un lien casse ou un binaire qui ne demarre pas a ete cru :\n" + sortie)


def test_le_balayage_ECARTE_un_emplacement_NON_ABSOLU(tmp_path):
    """Le piege des chemins relatifs, paye trois findings la nuit du 2026-09-08.

    Un emplacement relatif se resout contre le REPERTOIRE COURANT, donc son
    sens change a chaque `cd` -- et le repertoire courant d'un banc est la
    RACINE DU DEPOT. La cible valide est en QUEUE, derriere le relatif : sans
    la garde, le relatif serait retenu et le verdict porterait sur un chemin
    qui ne veut rien dire.
    """
    racine = tmp_path / "collection"
    racine.mkdir()
    relatif = tmp_path / "relatif"
    relatif.mkdir()
    (relatif / "outil").write_text(_binaire_marque("relatif"))
    (relatif / "outil").chmod(0o755)
    bon = racine / "bon"
    bon.mkdir()
    (bon / "outil").write_text(_binaire_marque("bon"))
    (bon / "outil").chmod(0o755)

    harnais = tmp_path / "harnais_relatif.sh"
    harnais.write_text(_texte_du_harnais(["relatif", bon]))
    # Le harnais tourne DANS tmp_path : « relatif » y existe reellement, donc
    # le regime porteur est bien « relatif ET existant » -- le relatif
    # inexistant serait ecarte par le `[ -f ]` avec ou sans la garde.
    acheve = subprocess.run(["/bin/bash", str(harnais)], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=DELAI, cwd=str(tmp_path))
    sortie = acheve.stdout.decode("utf-8", "replace")
    assert "TROUVE=%s/outil" % bon in sortie, (
        "un emplacement RELATIF a ete retenu :\n" + sortie)


# ------------------- le parcours REEL : une machine qui porte un outil
#                     hors du PATH, et un `~/.local/bin` que le banc gouverne

#: `~/.local/bin` est le SEUL emplacement de la liste bornee qu'un banc puisse
#: gouverner : `HOME` est jetable, `/usr/local/bin` et `/snap/bin` sont des
#: chemins absolus du conteneur. Les parcours ci-dessous s'y jouent donc tous,
#: et l'AC8 -- la cible a chaque bord de la collection -- se mesure par le
#: harnais ci-dessus, qui rejoue le balayage du produit sur une collection
#: fabriquee.
PIPX_FACTICE_HORS_DU_PATH = (
    "#!/bin/sh\n"
    "case \"$1\" in\n"
    "  --version) printf '1.4.3\\n' ;;\n"
    "esac\n"
    "exit 0\n"
)

FFMPEG_FACTICE = (
    "#!/bin/sh\n"
    "case \"$1\" in\n"
    "  -version) printf 'ffmpeg version __VERSION__ Copyright (c) the FFmpeg developers\\n' ;;\n"
    "esac\n"
    "exit 0\n"
)


def _ffmpeg_factice(version: str) -> str:
    return FFMPEG_FACTICE.replace("__VERSION__", version)


def _machine_avec_un_outil_hors_du_PATH(tmp_path, *, avec_ffmpeg=True,
                                        avec_pipx=True, poses=()):
    """Une machine fabriquee, PLUS un `~/.local/bin` que le `PATH` n'expose pas.

    C'est exactement le regime d'Egan : l'outil est la, le shell l'ignore. Le
    `PATH` fabrique ne contient que `<HOME>/bin` -- jamais `<HOME>/.local/bin`
    --, donc `command -v` echoue et la liste bornee est la seule voie.
    """
    env = _fabriquer_machine(tmp_path, avec_ffmpeg=avec_ffmpeg, liste_pipx="",
                             avec_affichage=False, avec_pipx=avec_pipx)
    hors = Path(env["HOME"]) / ".local" / "bin"
    hors.mkdir(parents=True, exist_ok=True)
    assert str(hors) not in env["PATH"].split(os.pathsep), (
        "le banc ne mesure rien : `~/.local/bin` est deja sur le PATH")
    for nom, contenu in poses:
        (hors / nom).write_text(contenu)
        (hors / nom).chmod(0o755)
        _aucun_HOMONYME_dans_la_liste_bornee(nom, hors)
    return env, hors


def _aucun_HOMONYME_dans_la_liste_bornee(nom: str, fabrique: Path) -> None:
    """Le banc n'est HERMETIQUE que si la liste bornee ne porte pas d'homonyme.

    `C1-4` de la couche 1 (2026-09-09), et c'est une mesure, pas une crainte :
    `/usr/local/bin` est le PREMIER emplacement de la liste sous Linux, il est
    ABSOLU, et aucun `PATH` fabrique ne le gouverne -- le balayage y va pour de
    vrai. Un `pipx` factice pose la fait rougir deux tests, le produit rendant
    `/usr/local/bin/pipx` au lieu du factice attendu.

    Autrement dit le vert de ces tests tient a l'ABSENCE ACCIDENTELLE de pipx
    dans ce conteneur. Ce n'est pas une propriete du produit, c'est une
    propriete de la machine -- et une mesure qui depend d'une propriete non
    dite de la machine finira par mesurer autre chose sans le dire.

    Cette garde ne rend pas le banc hermetique : elle le rend BRUYANT quand il
    cesse de l'etre. C'est ce qui est tenable ici -- l'hermeticite vraie
    demanderait que le produit accepte un prefixe de racine, ce qui est une
    surface de test dans le produit et un arbitrage qui n'est pas le mien.
    Consigne dans `deferred-work.md`.
    """
    for emplacement in _emplacements_usuels_du_produit():
        candidat = Path(emplacement) / nom
        if Path(emplacement) == fabrique:
            continue
        if candidat.exists():
            # ON SAUTE, ON N'ACCUSE PAS -- corrige le 2026-09-09 sur la
            # premiere course de CI publique, qui a rendu DIX-HUIT rouges de
            # cette famille. Ma premiere redaction faisait `assert`, et c'etait
            # une faute de conception : un rouge accuse le PRODUIT, or le
            # produit n'a rien fait. Les runners GitHub portent `pipx` dans
            # `/usr/local/bin` -- le premier emplacement de la liste bornee --,
            # donc le banc y mesure la machine et non l'outil.
            #
            # Un test qui ne PEUT PAS mesurer ce qu'il annonce se saute en le
            # DISANT. C'est la seule issue qui ne mente ni dans un sens ni dans
            # l'autre : verte, elle affirmerait une mesure qui n'a pas eu lieu ;
            # rouge, elle imputerait au produit une propriete de la machine.
            pytest.skip(
                "banc NON HERMETIQUE sur cette machine : %s existe et est "
                "balaye AVANT le %s factice de %s. Le balayage rendrait la "
                "copie du systeme, pas celle du banc (`C1-4`)."
                % (candidat, nom, fabrique))


def _emplacements_usuels_du_produit():
    """La liste bornee REELLE, jouee depuis `install.sh` -- jamais recopiee.

    Recopier la liste ici serait le defaut que `_declarations_du_produit`
    vient de fermer sur les constantes : la garde d'hermeticite deviendrait
    aveugle a un emplacement ajoute au produit.
    """
    script = ("SYSTEME=linux\n" + _fonction_bash_brute("emplacements_usuels")
              + "\nemplacements_usuels\n")
    acheve = subprocess.run(["/bin/sh", "-c", script], capture_output=True,
                            timeout=DELAI)
    lignes = acheve.stdout.decode("utf-8", "replace").split()
    assert len(lignes) >= 3, (
        "la liste bornee du produit ne rend que %d emplacement(s) : la garde "
        "d'hermeticite ne mesurerait presque rien" % len(lignes))
    return lignes


DRAPEAUX_MUETS = ["--dry-run", "--non-interactif", "--cli", "--sans-path",
                  "--sans-raccourci", "--sans-verification"]


# ------------------------------------- AC6 : la question ne se pose PAS pour rien

def test_sur_une_machine_VIERGE_aucune_question_hors_du_PATH(tmp_path):
    """AC6 -- « la question ne se pose PAS sur une machine vierge ».

    Le parcours nominal ne gagne AUCUNE question : c'est ce que
    `EPIC11-ARB-279` met explicitement dans ce qu'il coute (« une question de
    plus ... mais seulement dans le regime ou quelque chose a ete trouve »).
    Un arbitrage qui ajouterait une question a tout le monde ne serait pas
    celui-la.
    """
    env, _ = _machine_avec_un_outil_hors_du_PATH(tmp_path)
    code, brut = jouer_sans_terminal(DRAPEAUX_MUETS, env, cwd=tmp_path)
    sortie = sans_ansi(brut)
    assert code == 0, sortie
    assert INTITULE_HORS_DU_PATH not in sortie, (
        "une machine vierge gagne une question qu'elle n'a aucune raison de "
        "recevoir :\n" + sortie)
    for libelle in LIBELLES_HORS_DU_PATH:
        assert libelle not in sortie, sortie


def test_un_pipx_pose_HORS_DU_PATH_est_TROUVE_et_NOMME(tmp_path):
    """L'autre sens, et c'est LE defaut d'Egan -- constate en vrai le
    2026-09-08 : pipx pose a la main, non detecte, RECOMPILE.

    Sans ce test, le precedent serait vert sur un produit qui ne chercherait
    jamais rien.
    """
    env, hors = _machine_avec_un_outil_hors_du_PATH(
        tmp_path, avec_pipx=False, poses=[("pipx", PIPX_FACTICE_HORS_DU_PATH)])
    code, brut = jouer_sans_terminal(DRAPEAUX_MUETS, env, cwd=tmp_path)
    sortie = sans_ansi(brut)
    assert code == 0, sortie
    assert "pipx est POSE hors du PATH" in sortie, (
        "pipx pose a la main n'est toujours pas detecte -- c'est le defaut "
        "que la story ferme :\n" + sortie)
    assert str(hors / "pipx") in sortie, (
        "le chemin trouve n'est pas NOMME :\n" + sortie)
    assert INTITULE_HORS_DU_PATH in sortie, sortie


# ------------------------------------ AC4 + AC10 : les TROIS issues, et le defaut

def test_le_mode_NON_INTERACTIF_prend_l_ISSUE_1_et_ne_POSE_RIEN(tmp_path):
    """AC10 -- « le defaut ne pose rien ».

    L'issue « exposer » est celle qui ne consomme ni reseau, ni heures, ni mot
    de passe. Le verdict ne porte pas sur l'annonce mais sur le PLAN : une
    ligne `[simulation]` est la commande elle-meme, un resume peut mentir sur
    ce qui suit.
    """
    env, _ = _machine_avec_un_outil_hors_du_PATH(
        tmp_path, avec_pipx=False, poses=[("pipx", PIPX_FACTICE_HORS_DU_PATH)])
    code, brut = jouer_sans_terminal(DRAPEAUX_MUETS, env, cwd=tmp_path)
    sortie = sans_ansi(brut)
    assert code == 0, sortie
    assert "je prends 1) " + LIBELLES_HORS_DU_PATH[0] in sortie, (
        "le defaut n'est pas l'issue 1 :\n" + sortie)
    pose_pipx = [ligne for ligne in lignes_de_plan(sortie)
                 if "pipx" in ligne and ("install" in ligne or "add" in ligne)
                 and not ligne.startswith("pipx ")]
    assert pose_pipx == [], (
        "le defaut POSE pipx alors qu'il vient d'en trouver un : %r\n%s"
        % (pose_pipx, sortie))
    assert "pipx : present (" in sortie, sortie


def test_l_ISSUE_2_ignore_la_trouvaille_et_POSE_quand_meme(tmp_path):
    """AC4, deuxieme issue -- « l'utilisateur a peut-etre une raison de ne pas
    vouloir de cette copie-la ».

    Elle se joue dans un VRAI pseudo-terminal : c'est le seul regime ou une
    reponse AUTRE que le defaut existe, et un banc qui ne jouerait que le
    non-interactif mesurerait la moitie du produit.
    """
    env, _ = _machine_avec_un_outil_hors_du_PATH(
        tmp_path, avec_pipx=False, poses=[("pipx", PIPX_FACTICE_HORS_DU_PATH)])
    courant = tmp_path / "courant_jetable"
    courant.mkdir()
    sortie = sans_ansi(jouer_le_dialogue(
        ["--dry-run", "--cli", "--sans-path", "--sans-raccourci",
         "--sans-verification"],
        ["2"] + [""] * 7, env, cwd=courant))
    assert "cette copie est ignoree" in sortie, sortie
    assert "pipx : absent, il sera installe." in sortie, (
        "l'issue 2 n'a pas rendu la main a l'installation normale :\n" + sortie)


def test_l_ISSUE_3_donne_la_LIGNE_et_ne_POSE_ABSOLUMENT_RIEN(tmp_path):
    """AC4, troisieme issue -- « ne rien faire et recevoir la ligne ».

    Elle AFFICHE et ne FAIT PAS, comme l'issue 3 du desinstalleur, et elle
    sort AVANT toute pose : c'est ce qui la rend mesurable sur le plan, qui
    doit etre VIDE. « Ne rien faire » ne peut pas vouloir dire « poser quand
    meme ».
    """
    env, hors = _machine_avec_un_outil_hors_du_PATH(
        tmp_path, avec_pipx=False, poses=[("pipx", PIPX_FACTICE_HORS_DU_PATH)])
    courant = tmp_path / "courant_jetable"
    courant.mkdir()
    sortie = sans_ansi(jouer_le_dialogue(
        ["--dry-run", "--cli", "--sans-path", "--sans-raccourci",
         "--sans-verification"],
        ["3"] + [""] * 7, env, cwd=courant))
    assert 'export PATH="%s:$PATH"' % hors in sortie, (
        "l'issue 3 ne donne pas la ligne de PATH :\n" + sortie)
    assert "Rien n'a ete change" in sortie, sortie
    assert lignes_de_plan(sortie) == [], (
        "l'issue 3 a pose quelque chose : %r" % lignes_de_plan(sortie))


def test_les_TROIS_issues_sont_OFFERTES_et_le_defaut_est_la_PREMIERE(tmp_path):
    """AC4 -- `EPIC11-ARB-89` : jamais une seule sortie, jamais un blocage sec.

    Les trois libelles sont dans l'invite, dans l'ordre, et le premier porte
    la marque du defaut.
    """
    env, _ = _machine_avec_un_outil_hors_du_PATH(
        tmp_path, avec_pipx=False, poses=[("pipx", PIPX_FACTICE_HORS_DU_PATH)])
    courant = tmp_path / "courant_jetable"
    courant.mkdir()
    sortie = sans_ansi(jouer_le_dialogue(
        ["--dry-run", "--cli", "--sans-path", "--sans-raccourci",
         "--sans-verification"],
        ["2"] + [""] * 7, env, cwd=courant))
    for numero, libelle in enumerate(LIBELLES_HORS_DU_PATH, start=1):
        assert "%d) %s" % (numero, libelle) in sortie, (
            "l'issue %d manque ou a derive :\n%s" % (numero, sortie))
    assert "1) %s [defaut]" % LIBELLES_HORS_DU_PATH[0] in sortie, (
        "le defaut n'est pas la premiere issue :\n" + sortie)


# ---------------- AC5, mesure sur la MACHINE : aucun profil n'est ecrit

def test_l_issue_1_EXPOSE_sans_ECRIRE_dans_le_profil(tmp_path):
    """AC5, l'autre moitie -- la frontiere statique dit que le code ne l'ecrit
    pas ; celle-ci dit que la MACHINE ne l'a pas.

    Les deux se posent ensemble : une frontiere de texte peut rater une forme
    d'ecriture qu'on n'a pas prevue, et une mesure sur la machine ne verrait
    pas une ecriture sur un chemin ou l'on n'est pas alle regarder. Le fichier
    regarde est celui que le PRODUIT nomme (`profil_du_shell` -> `.bashrc`,
    `SHELL` valant `/bin/bash` dans toute machine fabriquee).
    """
    env, hors = _machine_avec_un_outil_hors_du_PATH(
        tmp_path, avec_pipx=False, poses=[("pipx", PIPX_FACTICE_HORS_DU_PATH)])
    profil = Path(env["HOME"]) / ".bashrc"
    assert not profil.exists(), "le banc part deja avec un profil : il ne mesure rien"

    code, brut = jouer_sans_terminal(DRAPEAUX_MUETS, env, cwd=tmp_path)
    sortie = sans_ansi(brut)
    assert code == 0, sortie
    # La ligne est DONNEE...
    assert 'export PATH="%s:$PATH"' % hors in sortie, (
        "l'issue 1 n'a pas donne la ligne de profil :\n" + sortie)
    assert str(profil) in sortie, (
        "la ligne ne dit pas OU l'ajouter :\n" + sortie)
    # ... et elle n'est PAS ecrite.
    assert not profil.exists(), (
        "le script a ECRIT dans le profil : c'est exactement ce que l'AC5 "
        "interdit")


# ---------------------- AC7 : ffmpeg et ffprobe, cherches SEPAREMENT

def test_ffmpeg_ET_ffprobe_hors_du_PATH_sont_une_detection_REUSSIE(tmp_path):
    """AC7, premier sens -- les deux sont la, la detection tient."""
    env, hors = _machine_avec_un_outil_hors_du_PATH(
        tmp_path, avec_ffmpeg=False,
        poses=[("ffmpeg", _ffmpeg_factice("6.1.1")),
               ("ffprobe", _ffmpeg_factice("6.1.1"))])
    code, brut = jouer_sans_terminal(DRAPEAUX_MUETS + ["--ffmpeg"], env, cwd=tmp_path)
    sortie = sans_ansi(brut)
    assert code == 0, sortie
    assert "ffmpeg / ffprobe sont POSES hors du PATH" in sortie, sortie
    assert "ffmpeg .......... deja present" in sortie, (
        "les deux binaires ont ete trouves et le recapitulatif dit encore "
        "qu'il faut les poser :\n" + sortie)


@pytest.mark.parametrize("present, absent", [("ffmpeg", "ffprobe"),
                                             ("ffprobe", "ffmpeg")])
def test_l_un_SANS_l_autre_n_est_PAS_une_detection_reussie(tmp_path, present, absent):
    """AC7, second sens -- « Trouver l'un sans l'autre est un regime reel [...]
    et il ne doit pas passer pour une detection reussie ».

    Certains paquets minimalistes ne livrent que `ffmpeg`. Le projet lit les
    metadonnees video avec `ffprobe` (`video_metadata.py`) : un `ffmpeg` seul
    echouerait plus tard, a l'usage -- c'est-a-dire au pire moment.

    LES DEUX SENS SONT JOUES parce que la garde est ecrite deux fois : un
    produit qui ne chercherait que `ffmpeg` resterait vert sur la moitie
    « ffprobe seul », et reciproquement.
    """
    env, _ = _machine_avec_un_outil_hors_du_PATH(
        tmp_path, avec_ffmpeg=False,
        poses=[(present, _ffmpeg_factice("6.1.1"))])
    code, brut = jouer_sans_terminal(DRAPEAUX_MUETS + ["--ffmpeg"], env, cwd=tmp_path)
    sortie = sans_ansi(brut)
    assert code == 0, sortie
    assert "%s reste introuvable" % absent in sortie, (
        "le desaccord entre ffmpeg et ffprobe n'est pas DIT :\n" + sortie)
    assert "pas une detection reussie" in sortie, sortie
    assert "ffmpeg .......... deja present" not in sortie, (
        "trouver %s seul est passe pour une detection reussie :\n%s"
        % (present, sortie))


# ------------------- AC3 + AC9 : le plancher de version, DANS LES DEUX SENS

def test_un_ffmpeg_TROP_ANCIEN_est_NOMME_puis_traite_comme_absent(tmp_path):
    """AC3 -- « Un refus muet serait la panne que la story existe pour fermer,
    retournee. »

    Il est NOMME, sa VERSION est donnee, le script dit qu'il posera quand
    meme, et le remede REEMPLOIE `commande_de_secours` (`EPIC11-ARB-271`)
    plutot que de recopier une commande.
    """
    env, hors = _machine_avec_un_outil_hors_du_PATH(
        tmp_path, avec_ffmpeg=False,
        poses=[("ffmpeg", _ffmpeg_factice("4.4.2")),
               ("ffprobe", _ffmpeg_factice("4.4.2"))])
    code, brut = jouer_sans_terminal(DRAPEAUX_MUETS + ["--ffmpeg"], env, cwd=tmp_path)
    sortie = sans_ansi(brut)
    assert code == 0, sortie
    assert "trop ancien pour cet outil" in sortie, sortie
    assert str(hors / "ffmpeg") in sortie, "le binaire trop ancien n'est pas NOMME"
    assert "4.4.2" in sortie, "sa version n'est pas donnee"
    assert "ffmpeg sera pose quand meme" in sortie, sortie
    # Le remede vient de la table officielle, pas d'une recopie.
    assert "La commande de secours pour ffmpeg" in sortie, (
        "le message du trop-ancien ne reemploie pas `commande_de_secours` :\n"
        + sortie)
    assert "ffmpeg .......... deja present" not in sortie, (
        "un ffmpeg trop ancien est passe pour present :\n" + sortie)


def test_un_ffmpeg_ASSEZ_RECENT_est_ACCEPTE(tmp_path):
    """L'AUTRE sens du meme drapeau (AC9).

    Sans lui, un produit qui refuserait TOUTES les versions passerait le test
    precedent -- et la story n'aurait rien ferme du tout.
    """
    env, _ = _machine_avec_un_outil_hors_du_PATH(
        tmp_path, avec_ffmpeg=False,
        poses=[("ffmpeg", _ffmpeg_factice("5.0")),
               ("ffprobe", _ffmpeg_factice("5.0"))])
    code, brut = jouer_sans_terminal(DRAPEAUX_MUETS + ["--ffmpeg"], env, cwd=tmp_path)
    sortie = sans_ansi(brut)
    assert code == 0, sortie
    assert "trop ancien" not in sortie, (
        "ffmpeg 5.0 est AU plancher (>= 5.0) et il est refuse :\n" + sortie)
    assert "ffmpeg .......... deja present" in sortie, sortie


# ----------------------------- AC9 : le drapeau de la recherche, DANS LES DEUX SENS

def test_le_drapeau_qui_ETEINT_la_recherche_l_eteint_VRAIMENT(tmp_path):
    """AC9 -- « un drapeau donne SUPPRIME la question correspondante ».

    Il pre-repond l'issue 2. Le regime est reel : une installation
    reproductible qui ne doit rien emprunter a ce qui traine dans
    `/usr/local/bin`.
    """
    env, _ = _machine_avec_un_outil_hors_du_PATH(
        tmp_path, avec_pipx=False, poses=[("pipx", PIPX_FACTICE_HORS_DU_PATH)])
    code, brut = jouer_sans_terminal(DRAPEAUX_MUETS + [IGNORER_HORS_DU_PATH],
                                     env, cwd=tmp_path)
    sortie = sans_ansi(brut)
    assert code == 0, sortie
    assert "pipx est POSE hors du PATH" not in sortie, (
        "le drapeau n'eteint pas la recherche :\n" + sortie)
    assert INTITULE_HORS_DU_PATH not in sortie, sortie
    assert "pipx : absent, il sera installe." in sortie, sortie


# ------------- AC2/AC3 : le PLANCHER de version, mesure sur le balayage lui-meme

#: Un Python factice qui DEMARRE mais dont le plancher n'est pas tenu. Les deux
#: gestes sont separes a dessein : `--version` rend 0 (donc le binaire demarre,
#: AC2), et le `-c` du plancher rend 1 (donc il est trop ancien, AC3). Un
#: produit qui confondrait les deux passerait l'un des deux sens.
PYTHON_TROP_ANCIEN = (
    "#!/bin/sh\n"
    "case \"$1\" in\n"
    "  --version) printf 'Python 3.9.18\\n'; exit 0 ;;\n"
    "  -c)        exit 1 ;;\n"
    "esac\n"
    "exit 0\n"
)

PYTHON_ASSEZ_RECENT = (
    "#!/bin/sh\n"
    "case \"$1\" in\n"
    "  --version) printf 'Python 3.12.4\\n'; exit 0 ;;\n"
    "  -c)        exit 0 ;;\n"
    "esac\n"
    "exit 0\n"
)


def _harnais_sur_un_python(tmp_path, contenu):
    """Le balayage DU PRODUIT sur un `python3` fabrique, liste maitrisee.

    Cette voie-la, et pas le parcours complet : la liste bornee REELLE porte
    `/usr/local/bin`, qui contient un `python3` 3.11.15 dans ce conteneur, et
    il passe le plancher. Le regime « trouve mais trop ancien » ne s'atteint
    donc PAS de l'exterieur ici -- dit plutot que tu. Le harnais substitue la
    collection, et rien d'autre.
    """
    repertoire = tmp_path / "un_seul"
    repertoire.mkdir()
    (repertoire / "python3").write_text(contenu)
    (repertoire / "python3").chmod(0o755)
    harnais = tmp_path / "harnais_python.sh"
    harnais.write_text(_texte_du_harnais([repertoire], nom="python3"))
    acheve = subprocess.run(["/bin/bash", str(harnais)], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=DELAI,
                            cwd=str(tmp_path))
    sortie = acheve.stdout.decode("utf-8", "replace")
    rendu = {}
    for ligne in sortie.splitlines():
        if "=" in ligne and ligne.split("=", 1)[0] in ("ISSUE", "TROUVE",
                                                       "VERSION", "ANCIEN"):
            cle, valeur = ligne.split("=", 1)
            rendu[cle] = valeur
    assert set(rendu) == {"ISSUE", "TROUVE", "VERSION", "ANCIEN"}, (
        "le harnais n'a pas rendu son verdict -- il ne mesure rien :\n" + sortie)
    return rendu, repertoire


def test_un_PYTHON_trop_ancien_est_rendu_COMME_TEL_et_non_comme_trouve(tmp_path):
    """AC3 -- « traite comme absent, en le disant ».

    Le balayage rend 2 -- ni 0 (trouve) ni 1 (rien) --, et il NOMME le binaire
    avec sa version. C'est cette troisieme valeur qui permet a l'appelant de
    dire la chose plutot que de la taire : un refus muet serait la panne que
    la story existe pour fermer, retournee.
    """
    rendu, repertoire = _harnais_sur_un_python(tmp_path, PYTHON_TROP_ANCIEN)
    assert rendu["ISSUE"] == "2", (
        "un Python trop ancien n'est pas distingue d'une absence : %r" % rendu)
    assert rendu["TROUVE"] == "", (
        "un Python trop ancien est rendu comme TROUVE : %r" % rendu)
    assert rendu["ANCIEN"] == "%s/python3 (Python 3.9.18)" % repertoire, (
        "le binaire trop ancien n'est ni nomme ni date : %r" % rendu)


def test_un_PYTHON_assez_recent_est_RETENU(tmp_path):
    """L'AUTRE sens du plancher (AC9).

    Sans lui, un produit qui refuserait TOUS les Python passerait le test
    precedent -- et la moitie utile de la story serait morte.
    """
    rendu, repertoire = _harnais_sur_un_python(tmp_path, PYTHON_ASSEZ_RECENT)
    assert rendu["ISSUE"] == "0", rendu
    assert rendu["TROUVE"] == "%s/python3" % repertoire, rendu
    assert rendu["VERSION"] == "Python 3.12.4", (
        "la version lue n'est pas celle du binaire retenu : %r" % rendu)
    assert rendu["ANCIEN"] == "", (
        "un Python retenu laisse quand meme une trace de trop-ancien : %r" % rendu)


def test_le_plancher_de_PYTHON_vit_a_UN_SEUL_endroit():
    """Tache 3 -- « reemploie la comparaison que `trouver_python` fait deja ;
    en ecrire une seconde serait la faire diverger ».

    C'est le motif qui a fait naitre `commande_de_secours` : un remede recopie
    a cinq endroits diverge. Ici la divergence serait pire qu'un message --
    deux planchers, donc un Python accepte par un chemin du script et refuse
    par l'autre.
    """
    code = code_du_script(INSTALL_SH)
    comparaisons = re.findall(r"sys\.version_info\[:2\]\s*>=", code)
    assert len(comparaisons) == 1, (
        "le plancher de Python est ecrit %d fois dans install.sh : il va "
        "diverger" % len(comparaisons))
    assert "python_assez_recent" in "\n".join(
        corps_de_fonction(code, "trouver_python")), (
        "`trouver_python` n'emploie plus le plancher partage : les deux "
        "chemins de detection vont diverger")
    assert "python_assez_recent" in _fonction_bash_brute("plancher_tenu"), (
        "la recherche hors du PATH n'emploie plus le plancher partage")


def test_le_plancher_de_PYTHON_REFUSE_bien_la_version_d_EN_DESSOUS():
    """`C1-1` / mutant `M12` -- la VALEUR du plancher, pas seulement son unicite.

    Le test ci-dessus mesure que la comparaison est ecrite une seule fois. Il
    ne mesure pas ce qu'elle COMPARE : ramener `(3, 11)` a `(3, 10)` laissait
    **196 tests verts**, sous une annonce « Python >= 3.11 » -- un 3.10 aurait
    ete retenu par `trouver_python` comme par le balayage hors du PATH.
    `PYTHON_MINIMUM` n'etait qu'un libelle d'affichage, et rien ne le
    confrontait au calcul.

    Le correctif produit DERIVE le tuple de `PYTHON_MINIMUM` : ce qui se
    derive ne peut pas diverger. Ce test mesure alors la seule chose qui
    reste a mesurer -- que le programme embarque REFUSE effectivement la
    version d'en dessous et ACCEPTE le plancher.

    C'est la regle du 2026-09-06 appliquee a un nombre plutot qu'a un
    drapeau : une garde qui ne joue qu'une valeur mesure la moitie du produit
    et l'annonce verte. On joue donc les DEUX bords, et un au-dessus.
    """
    code = code_du_script(INSTALL_SH)

    # Le plancher DECLARE, et les deux scripts doivent porter le meme.
    declare = re.search(r'PYTHON_MINIMUM="([0-9]+\.[0-9]+)"', code)
    assert declare, "`PYTHON_MINIMUM` a disparu d'install.sh"
    plancher = declare.group(1)
    ps1 = code_du_script(INSTALL_PS1)
    jumeau = re.search(r'\$PythonMinimum\s*=\s*\[version\]"([0-9]+\.[0-9]+)"', ps1)
    assert jumeau, "`$PythonMinimum` a disparu d'install.ps1"
    assert jumeau.group(1) == plancher, (
        "les deux scripts n'annoncent pas le meme plancher de Python : %r "
        "contre %r. L'AC11 promet le MEME contrat, pas un contrat voisin."
        % (plancher, jumeau.group(1)))

    # Le calcul est DERIVE du libelle, jamais recopie : c'est ce qui ferme
    # `M12` structurellement plutot que par une mesure qu'on peut oublier.
    corps = "\n".join(corps_de_fonction(code, "python_assez_recent"))
    assert "PYTHON_MINIMUM" in corps, (
        "`python_assez_recent` ne derive plus son plancher de "
        "`PYTHON_MINIMUM` : le nombre est recopie, et il divergera du libelle "
        "sans que rien ne rougisse -- c'est le mutant `M12`.")
    assert not re.search(r">=\s*\(\s*\d+\s*,", corps), (
        "un tuple litteral est revenu dans `python_assez_recent` : le "
        "plancher est de nouveau ecrit a deux endroits")

    # ... ET LE PROGRAMME EMBARQUE FAIT CE QU'IL DIT. On extrait le `-c` du
    # produit et on le rejoue en faisant VARIER `sys.version_info` -- qui est
    # assignable sur le module -- de part et d'autre du plancher.
    programme = re.search(r'"\$1" -c "([^"]+)"', corps)
    assert programme, (
        "le programme embarque de `python_assez_recent` ne se lit plus : "
        "c'est le DECOUPAGE qu'il faut reprendre ici, pas la mesure")
    source = programme.group(1).replace("${PYTHON_MINIMUM}", plancher)

    majeur, mineur = (int(n) for n in plancher.split("."))
    attendus = {(majeur, mineur - 1): 1,   # le bord d'EN DESSOUS : refuse
                (majeur, mineur): 0,       # le plancher lui-meme : accepte
                (majeur, mineur + 1): 0}   # au-dessus : accepte
    for version, code_attendu in attendus.items():
        rendu = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.version_info = %r; %s" % (version, source)],
            capture_output=True)
        assert rendu.returncode == code_attendu, (
            "le plancher de Python ne discrimine pas : version_info=%r rend "
            "%d au lieu de %d. Annonce « Python >= %s »."
            % (version, rendu.returncode, code_attendu, plancher))


def test_la_liste_des_NOMS_DE_PYTHON_porte_ses_deux_BORDS():
    """`C1-2` / mutant `M14` -- la regle des fabriques, point 4, sur les NOMS.

    La liste des EMPLACEMENTS respecte le point 4 : la couche 1 a tue les
    mutants qui l'inversaient (`M08`) et qui la tronquaient en queue (`M09`).
    La liste des NOMS ne le respectait pas -- l'amputer de `python3`, son
    dernier element et de tres loin le nom le plus frequent sur le terrain,
    laissait **196 tests verts**.

    Un balayage tronque est un autre mode de panne qu'un `find` fautif, et il
    ne se demasque que par une cible A CHAQUE BORD (2026-09-03).
    """
    code = code_du_script(INSTALL_SH)
    declare = re.search(r'NOMS_DE_PYTHON="([^"]+)"', code)
    assert declare, "`NOMS_DE_PYTHON` a disparu d'install.sh"
    noms = declare.group(1).split()

    assert len(noms) >= 3, (
        "`NOMS_DE_PYTHON` ne porte plus que %d nom(s) : la liste a fondu"
        % len(noms))
    # LES DEUX BORDS, NOMMES. `python3` est le generique et il est en QUEUE ;
    # le plancher declare est en TETE. Les nommer l'un et l'autre est ce qui
    # attrape une troncature, dans les deux sens.
    plancher = re.search(r'PYTHON_MINIMUM="([0-9]+\.[0-9]+)"', code).group(1)
    assert noms[-1] == "python3", (
        "la queue de `NOMS_DE_PYTHON` n'est plus `python3` mais %r : le nom "
        "generique est celui qu'on trouve sur la plupart des machines, et "
        "l'amputer ne faisait rougir personne" % noms[-1])
    assert noms[0] == "python%s" % plancher or noms[0].startswith("python3."), (
        "la tete de `NOMS_DE_PYTHON` n'est pas une version explicite : %r"
        % noms[0])
    assert "python%s" % plancher in noms, (
        "`NOMS_DE_PYTHON` ne porte pas le plancher declare (`python%s`) : un "
        "utilisateur dont c'est le seul Python ne serait pas trouve"
        % plancher)
    # DECROISSANTE : le plus recent d'abord, sinon un vieux Python encore
    # convenable serait prefere a un neuf.
    versionnes = [n for n in noms if re.match(r"python3\.\d+$", n)]
    assert versionnes == sorted(versionnes, key=lambda n: int(n.split(".")[1]),
                                reverse=True), (
        "`NOMS_DE_PYTHON` n'est plus decroissante : %r" % versionnes)

    # ET LE JUMEAU PORTE LA MEME LISTE (AC11).
    ps1 = code_du_script(INSTALL_PS1)
    jumelle = re.search(r'\$script:NomsDePython\s*=\s*@\(([^)]*)\)', ps1)
    assert jumelle, "`$script:NomsDePython` a disparu d'install.ps1"
    noms_ps = re.findall(r'"([^"]+)"', jumelle.group(1))
    assert noms_ps == noms, (
        "les deux scripts ne cherchent pas les memes interpretes : %r contre "
        "%r. Le commentaire d'install.sh previent lui-meme que « deux listes "
        "divergeraient au premier Python 3.14 »." % (noms, noms_ps))


def _harnais_de_la_boucle_python(tmp_path, pythons) -> dict:
    """Rejoue `chercher_python_hors_du_path` DU PRODUIT sur des noms fabriques.

    `C2-1` / `C3-1c` -- deux couches sur trois ont trouve, par des chemins
    differents, que cette boucle-la n'etait jouee par AUCUN test : le harnais
    existant appelle `chercher_hors_du_path` (UN nom) et jamais
    `chercher_python_hors_du_path` (la BOUCLE sur les noms). Un mutant qui
    faisait qu'un Python pose hors du PATH n'etait jamais retenu laissait
    206 tests verts -- la moitie Python de la story etait morte et verte.

    `pythons` apparie un nom d'interprete au contenu du faux binaire, ce qui
    permet de placer la cible n'importe ou dans `NOMS_DE_PYTHON`.
    """
    repertoire = tmp_path / "les_pythons"
    repertoire.mkdir()
    for nom, contenu in pythons.items():
        (repertoire / nom).write_text(contenu)
        (repertoire / nom).chmod(0o755)

    extraits = "\n\n".join(_fonction_bash_brute(nom) for nom in
                            FONCTIONS_DU_BALAYAGE + ("chercher_python_hors_du_path",))
    script = (
        "set -euo pipefail\n"
        + _declarations_du_produit("PLAFOND_DE_LANCEMENT", "FFMPEG_MAJEUR_MINIMUM",
                                   "PYTHON_MINIMUM", "NOMS_DE_PYTHON")
        + "CHERCHER_HORS_DU_PATH=1\n"
        "SYSTEME=linux\n"
        "TROUVE_HORS_DU_PATH=''\n"
        "REPERTOIRE_HORS_DU_PATH=''\n"
        "TROP_ANCIEN_HORS_DU_PATH=''\n"
        "VERSION_HORS_DU_PATH=''\n"
        + extraits + "\n\n"
        "emplacements_usuels() { printf '%s\\n' '" + str(repertoire) + "'; }\n"
        "issue=0\n"
        "chercher_python_hors_du_path || issue=$?\n"
        "printf 'ISSUE=%s\\n' \"${issue}\"\n"
        "printf 'TROUVE=%s\\n' \"${TROUVE_HORS_DU_PATH}\"\n"
        "printf 'ANCIEN=%s\\n' \"${TROP_ANCIEN_HORS_DU_PATH}\"\n"
    )
    chemin = tmp_path / "harnais_boucle.sh"
    chemin.write_text(script)
    acheve = subprocess.run(["/bin/bash", str(chemin)], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=DELAI,
                            cwd=str(tmp_path))
    sortie = acheve.stdout.decode("utf-8", "replace")
    rendu = {}
    for ligne in sortie.splitlines():
        if "=" in ligne and ligne.split("=", 1)[0] in ("ISSUE", "TROUVE", "ANCIEN"):
            cle, valeur = ligne.split("=", 1)
            rendu[cle] = valeur
    assert rendu, "le harnais de la boucle n'a rien rendu :\n%s" % sortie
    return rendu


def test_la_boucle_SUR_LES_NOMS_retient_un_Python_place_EN_QUEUE(tmp_path):
    """`C2-1` -- la cible au dernier nom de la liste, qui est le cas du terrain.

    `NOMS_DE_PYTHON` va du plus recent au generique : sur la plupart des
    machines, le seul interprete pose s'appelle `python3` -- c'est-a-dire le
    DERNIER de la liste. Une boucle tronquee en queue rate donc exactement le
    cas le plus frequent, et c'est le point 4 de la regle des fabriques.

    On place en plus un nom PLUS PRIORITAIRE mais trop ancien : la boucle doit
    le sauter et continuer, et non s'arreter au premier trouve.
    """
    rendu = _harnais_de_la_boucle_python(tmp_path, {
        "python3.12": PYTHON_TROP_ANCIEN,   # plus prioritaire, mais refuse
        "python3": PYTHON_ASSEZ_RECENT,     # la cible, EN QUEUE
    })
    assert rendu["ISSUE"] == "0", (
        "la boucle n'a pas retenu le `python3` pose hors du PATH (issue=%s) : "
        "elle s'arrete au premier nom trouve au lieu du premier nom VALIDE, "
        "ou elle ne va pas jusqu'a la queue de `NOMS_DE_PYTHON`"
        % rendu["ISSUE"])
    assert rendu["TROUVE"].endswith("/python3"), (
        "la boucle rend %r au lieu du `python3` valide" % rendu["TROUVE"])


def test_la_boucle_SUR_LES_NOMS_retient_un_Python_place_EN_TETE(tmp_path):
    """L'autre BORD, sans lequel le precedent ne dit rien d'un balayage inverse."""
    rendu = _harnais_de_la_boucle_python(tmp_path, {
        "python3.13": PYTHON_ASSEZ_RECENT,  # la cible, EN TETE
        "python3": PYTHON_TROP_ANCIEN,
    })
    assert rendu["ISSUE"] == "0" and rendu["TROUVE"].endswith("/python3.13"), (
        "la boucle ne prefere pas le nom le plus recent : %r (issue=%s)"
        % (rendu["TROUVE"], rendu["ISSUE"]))


def test_la_boucle_SUR_LES_NOMS_garde_le_PREMIER_trop_ancien(tmp_path):
    """`C2-7` cote bash -- l'AC3, et c'est la moitie qui manquait au jumeau.

    Quand la boucle n'a vu que du trop ancien, elle rend 2 et NOMME le
    premier. C'est ce que `install.ps1` ne faisait pas : son memo etait remis
    a vide a chaque nom, donc l'utilisateur Windows lisait « Python : absent »
    d'un Python parfaitement vu. Le mesurer ici tient le contrat du cote ou il
    s'execute, et la frontiere de parite tient l'autre.
    """
    rendu = _harnais_de_la_boucle_python(tmp_path, {
        "python3.12": PYTHON_TROP_ANCIEN,
        "python3": PYTHON_TROP_ANCIEN,
    })
    assert rendu["ISSUE"] == "2", (
        "la boucle rend %s au lieu de 2 : un Python trop ancien n'est plus "
        "distingue d'une absence, et l'AC3 est muette" % rendu["ISSUE"])
    assert rendu["ANCIEN"].startswith("/") and "python3.12" in rendu["ANCIEN"], (
        "le PREMIER trop ancien n'est pas garde : %r. Il est ecrase par les "
        "noms suivants, ce qui est exactement le defaut `C2-7` du jumeau "
        "PowerShell" % rendu["ANCIEN"])


def test_la_boucle_SUR_LES_NOMS_ne_trouve_RIEN_quand_il_n_y_a_rien(tmp_path):
    """Le troisieme rendu, sans lequel les deux autres ne prouvent pas qu'elle
    discrimine : 1 quand elle n'a rien vu du tout."""
    rendu = _harnais_de_la_boucle_python(tmp_path, {"perl": PYTHON_ASSEZ_RECENT})
    assert rendu["ISSUE"] == "1", (
        "la boucle rend %s au lieu de 1 sur un repertoire sans aucun Python"
        % rendu["ISSUE"])
    assert rendu["TROUVE"] == "" and rendu["ANCIEN"] == "", (
        "la boucle laisse des restes d'un appel precedent : TROUVE=%r ANCIEN=%r"
        % (rendu["TROUVE"], rendu["ANCIEN"]))


def test_le_JUMEAU_PowerShell_accumule_le_trop_ancien_lui_aussi():
    """`C2-7` / `C1-5` -- la frontiere STATIQUE, seule tenable sans `pwsh`.

    Le defaut : `Find-HorsDuPath` remet `$script:TropAncienHorsDuPath` a `""`
    en ENTREE, et l'appelant parcourait cinq noms. Le memo n'etait donc garde
    que si le DERNIER nom en etait le porteur -- AC3 muette dans 4 regimes sur
    5. Le bash accumule (`premier_trop_ancien`), le jumeau non : deux scripts
    qui divergent sur une AC, ce que l'AC11 interdit nommement.

    `pwsh` etant absent du conteneur, cette propriete se tient en LECTURE ou
    pas du tout -- dit plutot que tu.
    """
    ps1 = code_du_script(INSTALL_PS1)

    # 1. La boucle sur les noms est une FONCTION, et l'appelant l'emploie --
    #    une boucle deroulee chez l'appelant est ce qui a produit le defaut.
    assert "function Find-PythonHorsDuPath" in ps1, (
        "`Find-PythonHorsDuPath` a disparu : la boucle sur les noms est "
        "revenue chez l'appelant, et le memo du trop-ancien y sera de nouveau "
        "ecrase a chaque nom")
    assert not re.search(r'foreach\s*\(\s*\$nom\s+in\s+@\(', ps1), (
        "une boucle sur des noms d'interprete litteraux est revenue dans "
        "install.ps1 : la liste doit rester centralisee")

    # 2. ET ELLE ACCUMULE. C'est la propriete, pas la presence de la fonction.
    corps = ps1[ps1.index("function Find-PythonHorsDuPath"):]
    corps = corps[:corps.index("\n}")]
    assert re.search(r'\$premierTropAncien\s*=\s*\$script:TropAncienHorsDuPath',
                     corps), (
        "`Find-PythonHorsDuPath` ne retient plus le premier trop-ancien a "
        "travers la boucle : `Find-HorsDuPath` le remet a vide a chaque nom, "
        "donc seul le DERNIER nom pourrait le porter -- c'est le defaut "
        "`C2-7`, et l'AC3 redevient muette sous Windows")
    assert re.search(r'\$script:TropAncienHorsDuPath\s*=\s*\$premierTropAncien',
                     corps), (
        "le premier trop-ancien accumule n'est jamais REPOSE : l'appelant "
        "lira toujours la valeur du dernier nom")


def test_la_liste_bornee_WINDOWS_descend_d_UN_cran(tmp_path):
    """`C2-8` / `C1-6` -- trois entrees sur quatre ne pouvaient rien trouver.

    `…\\Programs`, `…\\Programs\\Python` et `$env:ProgramFiles` sont des
    repertoires CONTENEURS : python.org pose dans
    `…\\Programs\\Python\\Python3xx\\`, un cran plus bas, et `pip --user`
    ecrit ses scripts dans `%APPDATA%\\Python\\Python3xx\\Scripts`. Seul
    `WindowsApps` pouvait rendre quelque chose, et il ne porte que l'alias du
    Store : la moitie Windows de la story etait inerte, sous une liste qui
    avait l'air fournie.

    La frontiere tient les deux cotes de la correction : que la descente
    existe, et qu'elle reste BORNEE -- un `-Recurse` ici serait le temps
    infini qu'`EPIC11-ARB-279` interdit.
    """
    ps1 = code_du_script(INSTALL_PS1)
    assert "function Expand-ConteneurDePython" in ps1, (
        "la descente d'un cran a disparu : les repertoires conteneurs sont de "
        "nouveau joints directement au nom du binaire, et ne trouveront rien")

    corps = ps1[ps1.index("function Expand-ConteneurDePython"):]
    corps = corps[:corps.index("\n}")]
    assert "-Recurse" not in corps, (
        "`Expand-ConteneurDePython` recurse : c'est le temps infini "
        "qu'`EPIC11-ARB-279` interdit nommement")
    assert "Scripts" in corps, (
        "la descente ne regarde plus les `Scripts\\` : c'est la ou "
        "`pip install --user pipx` ecrit, et c'est l'emplacement canonique "
        "d'un pipx pose a la main")

    # LES CONTENEURS SONT TOUS DEVELOPPES, aucun n'est reste joint en direct.
    liste = ps1[ps1.index("function Get-EmplacementsUsuels"):]
    liste = liste[:liste.index("\n}")]
    for conteneur in ("Programs\\Python", "ProgramFiles", "APPDATA"):
        motif = r'Expand-ConteneurDePython[^\n]*%s' % re.escape(conteneur)
        assert re.search(motif, liste), (
            "le conteneur %r n'est pas developpe : il est joint directement au "
            "nom du binaire, et ne trouvera donc jamais rien" % conteneur)


def test_le_plancher_de_FFMPEG_est_le_MEME_sur_le_PATH_et_hors_du_PATH():
    """`C2-5` -- l'asymetrie qui rouvrait le defaut dans l'autre sens.

    Le plancher ffmpeg lisait le global `VERSION_HORS_DU_PATH`, donc il ne
    pouvait servir QU'au balayage hors du PATH. Consequence mesuree : un
    ffmpeg 4 POSE hors du PATH etait refuse comme trop ancien, et le meme
    ffmpeg 4 SUR le PATH etait accepte sans qu'aucune version soit lue --
    l'outil etait plus severe avec ce qu'il trouve lui-meme qu'avec ce que le
    systeme lui presente, et l'utilisateur recevait « ffmpeg : ok » avant
    d'echouer au premier encodage.

    Ce test mesure les DEUX moities de la symetrie : que le plancher est une
    fonction appelee des deux cotes, et qu'il DISCRIMINE reellement.
    """
    code = code_du_script(INSTALL_SH)

    # 1. Le plancher est ecrit UNE fois, et il prend sa version en ARGUMENT --
    #    ce qui depend d'un global ne peut pas etre reemploye.
    corps = "\n".join(corps_de_fonction(code, "ffmpeg_assez_recent"))
    assert "VERSION_HORS_DU_PATH" not in corps, (
        "`ffmpeg_assez_recent` relit le global `VERSION_HORS_DU_PATH` : il "
        "redevient inutilisable depuis le chemin du PATH, et l'asymetrie de "
        "`C2-5` revient")
    assert "FFMPEG_MAJEUR_MINIMUM" in corps, (
        "`ffmpeg_assez_recent` n'emploie plus le plancher declare")

    # 2. LES DEUX APPELANTS. C'est la garde de symetrie : un seul appel
    #    signifie qu'un des deux chemins ne verifie plus rien.
    # Le motif exige une ESPACE apres le nom, donc il compte les APPELS et non
    # la definition (`ffmpeg_assez_recent() {`, sans espace). Deux appels : un
    # par chemin de detection. Ma premiere redaction exigeait trois en croyant
    # compter la definition -- et elle rougissait sur du code juste, ce qui est
    # pire que pas de frontiere.
    appels = re.findall(r"ffmpeg_assez_recent\s", code)
    assert len(appels) >= 2, (
        "`ffmpeg_assez_recent` n'est appele que %d fois dans install.sh : un "
        "des deux chemins de detection ne verifie plus la version, et c'est "
        "exactement le defaut `C2-5`" % len(appels))
    assert "ffmpeg_assez_recent" in "\n".join(
        corps_de_fonction(code, "plancher_tenu")), (
        "le balayage hors du PATH n'emploie plus le plancher partage")
    # ... et le chemin du PATH, qui est celui qui ne verifiait RIEN.
    assert re.search(r'command -v ffmpeg[\s\S]{0,600}?ffmpeg_assez_recent', code), (
        "le ffmpeg trouve SUR le PATH n'est plus confronte au plancher : il "
        "sera annonce « ok » quelle que soit sa version")

    # 3. ET IL DISCRIMINE, aux deux bords. On rejoue la fonction DU PRODUIT.
    plancher = int(re.search(r"FFMPEG_MAJEUR_MINIMUM=(\d+)", code).group(1))
    cas = {
        "ffmpeg version %d.1.2 Copyright (c) 2000-2024" % (plancher - 1): 1,
        "ffmpeg version %d.0 Copyright (c) 2000-2024" % plancher: 0,
        "ffmpeg version %d.2 Copyright (c) 2000-2024" % (plancher + 1): 0,
        # Le `n` des tirages git, et une version ILLISIBLE : acceptee des deux
        # cotes, et c'est le meme choix qui doit valoir des deux cotes.
        "ffmpeg version n%d.1 Copyright" % plancher: 0,
        "ffmpeg version inconnue": 0,
    }
    for version, attendu in cas.items():
        script = ("FFMPEG_MAJEUR_MINIMUM=%d\n" % plancher) + corps + (
            '\nffmpeg_assez_recent "%s"\n' % version)
        rendu = subprocess.run(["/bin/sh", "-c", script], capture_output=True,
                               timeout=DELAI)
        assert rendu.returncode == attendu, (
            "le plancher ffmpeg ne discrimine pas : %r rend %d au lieu de %d"
            % (version, rendu.returncode, attendu))


def test_une_machine_FABRIQUEE_n_herite_RIEN_du_systeme_reel(tmp_path):
    """La frontiere de la fuite qui a coute quatre-vingt-douze rouges.

    Les deux fabriques d'environnement de ce module partaient de
    `dict(os.environ)` : la machine « entierement maitrisee » heritait en fait
    de 138 cles reelles, dont trois seulement etaient ensuite ecrasees.

    CE QUE CA A COUTE, mesure sur la premiere CI publique : les runners
    GitHub exportent `PIPX_BIN_DIR=/opt/pipx_bin`, un repertoire REEL et sur
    leur `PATH`. `repertoire_binaire_de_pipx` le lit -- ce que la story 8.11
    lui a appris a faire --, donc le repli precompile posait son ffmpeg
    FACTICE la. Tout ce qui suivait dans la suite sondait un ffmpeg qui ne
    fait rien : 83 tests de bancs que cette branche n'a JAMAIS touches,
    verts la veille sur le meme runner et le meme ffmpeg, rougissaient a
    cause de ce banc-ci.

    Le banc ne se contentait donc pas de mal mesurer : il ABIMAIT la machine
    pour les autres. C'est la faute la plus grave qu'un banc puisse commettre,
    et aucune mesure ne la disait.

    Cette frontiere la dit. Elle compte les cles, plutot que d'interdire une
    variable a la fois -- l'ancien `env.pop("DISPLAY")` etait exactement cette
    liste noire qu'on allonge a mesure qu'elle mord.
    """
    machine = machine_du_repli(tmp_path)
    env = machine["env"]

    # Les variables POSEES ne sont pas des intrus : elles ne viennent pas du
    # systeme, elles sont ecrites par la fabrique et valent la MEME chose
    # partout. C'est precisement ce qui les distingue de l'heritage -- et ce
    # que la CI a impose le 2026-09-09, `TERM` etant present ici et absent du
    # runner.
    intrus = sorted(set(env) - VARIABLES_HERITEES - set(VARIABLES_POSEES)
                    - {"PATH", "HOME", "SHELL", "DISPLAY", "TMPDIR"})
    assert intrus == [], (
        "la machine fabriquee herite %d variable(s) du systeme REEL : %r. "
        "Chacune peut gouverner une decision du produit, et `PIPX_BIN_DIR` l'a "
        "fait -- le repli a pose son binaire dans le vrai `/opt/pipx_bin` du "
        "runner, sur son PATH, et a casse 83 tests d'autres bancs."
        % (len(intrus), intrus[:8]))

    # LE VOLET QUI MORD SUR LE CAS REEL : la variable qui a coute la course.
    assert "PIPX_BIN_DIR" not in env, (
        "`PIPX_BIN_DIR` du systeme reel atteint la machine fabriquee : le "
        "repli posera son binaire hors de la destination du banc")

    # ... ET LA GARDE DE NON-VACUITE. Un `env` vide passerait tout ce qui
    # precede en ne mesurant rien.
    assert env.get("PATH") and env.get("HOME"), (
        "la machine fabriquee n'a plus ni PATH ni HOME : la frontiere serait "
        "verte sur un environnement qui ne lance rien")


# ------------------------- triage de la revue 8.14, couche 2 (2026-09-09)


def test_un_binaire_qui_SUSPEND_A_LA_VERSION_ne_suspend_pas_l_installateur(tmp_path,
                                                                          machine_vierge):
    """`C2-6` -- la panne que `lancer_avec_plafond` ferme, rouverte deux lignes plus bas.

    Le produit lancait le candidat DEUX fois : une premiere sous plafond pour
    savoir s'il demarre, une seconde SANS plafond pour lire sa version. Un
    binaire qui repond au premier appel et suspend au second suspendait donc
    l'installateur -- mesure a 90 s par la couche 2, sans qu'il rende jamais la
    main.

    Le correctif ne rajoute pas un second plafond : il supprime le second
    APPEL. La version se lit dans le journal du premier, capture par
    REDIRECTION et non par une enveloppe `sh -c` -- sans quoi `$!` serait le
    PID du `sh` et le `kill` laisserait le petit-fils courir, ce qui est le
    « tuer par ressemblance » de la regle 6 transpose a la parente.

    Ce test mesure le SEUL regime qui distingue les deux formes : un binaire
    dont le premier appel rend, et dont un second appel dormirait.
    """
    code = code_du_script(INSTALL_SH)
    corps = "\n".join(corps_de_fonction(code, "demarre_et_dit_sa_version"))
    assert len(corps.splitlines()) > 5, (
        "le corps de `demarre_et_dit_sa_version` a fondu : le decoupage a glisse")
    lancements = corps.count('"${candidat}" "${drapeau}"')
    assert lancements <= 1, (
        "le candidat est lance %d fois dans `demarre_et_dit_sa_version` : le "
        "second appel n'est pas plafonne, et un binaire qui suspend au second "
        "suspendra l'installateur SANS UN MOT. La version se lit dans le "
        "journal du premier lancement." % lancements)

    # Et la capture se fait par REDIRECTION, jamais par une enveloppe : le PID
    # capture doit rester celui du BINAIRE.
    plafond = "\n".join(corps_de_fonction(code, "lancer_avec_plafond"))
    assert "JOURNAL_DU_LANCEMENT" in plafond, (
        "`lancer_avec_plafond` ne sait plus capturer la sortie : son appelant "
        "va relancer le binaire une seconde fois, hors plafond")
    for enveloppe in (r'sh\s+-c', r'bash\s+-c', r'eval\b'):
        assert not re.search(enveloppe, plafond), (
            "`lancer_avec_plafond` lance a travers une enveloppe (%r) : `$!` "
            "n'est plus le PID du binaire, et le `kill` laisserait le "
            "petit-fils courir" % enveloppe)


def test_l_issue_1_met_REELLEMENT_le_repertoire_sur_le_PATH_du_processus():
    """`C2-4` -- « exposer » pouvait ne rien exposer, et 206 tests restaient verts.

    Le test de comportement de l'issue 1 mesure que le profil n'est PAS ecrit
    et que la ligne est AFFICHEE. Il ne mesure pas que le repertoire arrive sur
    le `PATH` du processus -- qui est la seule chose que l'issue 1 promette.
    Sous le mutant qui retire l'`export`, le produit posait `PIPX_PRESENT=1`
    sans que `pipx` soit atteignable : les etapes suivantes, qui passent par
    `command -v`, auraient echoue.

    **Ce que ce test NE mesure PAS, dit plutot que tu** : il lit la STRUCTURE,
    pas l'etat du processus. Un `export` vers une variable qui ne serait pas
    `PATH`, ou vers un repertoire qui ne serait pas celui trouve, lui
    echapperait. La mesure de comportement demanderait d'observer le `PATH`
    d'un processus deja termine, ce que le banc ne sait pas faire aujourd'hui
    -- c'est une dette, pas une propriete tenue.
    """
    code = code_du_script(INSTALL_SH)
    corps = "\n".join(corps_de_fonction(code, "offrir_les_trois_issues"))
    assert len(corps.splitlines()) > 10, (
        "le corps des trois issues a fondu : le decoupage a glisse")
    # Un `export` REEL, en tete de ligne -- et non la ligne de profil que
    # `donner_la_ligne_de_profil` AFFICHE, qui porte les memes mots dans une
    # chaine. Confondre les deux serait la meme faute que le premier jet de
    # `test_TOUTE_sortie_de_retrait...`, qui accusait une commande affichee.
    assert re.search(r'^\s*export PATH=', corps, re.M), (
        "l'issue 1 n'exporte plus le repertoire trouve : elle annonce qu'elle "
        "expose et n'expose rien. Les etapes suivantes passent par "
        "`command -v` et ne le trouveraient pas.")


def test_AUCUNE_machine_fabriquee_n_expose_le_VRAI_sudo(tmp_path,
                                                        machine_avec_affichage):
    """Le dernier rouge de la CI publique, ferme par classe et non par cas.

    Le `PATH` d'une machine fabriquee est fait de LIENS vers les vrais
    binaires du conteneur. Pour `sudo`, ca veut dire que le produit peut
    ELEVER POUR DE VRAI -- et le comportement depend alors de qui joue la
    suite : root ici, `runner` sur la CI, ou le vrai `sudo` refuse parce qu'il
    n'est pas setuid a ce chemin-la.

    Une machine dont le comportement depend de l'uid de qui la joue n'est pas
    une machine fabriquee. C'est la troisieme forme du meme defaut en une
    journee -- apres `PIPX_BIN_DIR` herite et `TERM` herite --, et celle-ci
    est la plus dangereuse : les deux autres faussaient une mesure, celle-ci
    donne au banc le droit d'elever des privileges sur la machine de qui joue.

    La frontiere est POSITIVE et non negative : elle exige que `sudo` soit un
    fichier REGULIER que le banc a ecrit, pas un lien. Une frontiere negative
    (« pas de lien vers /usr/bin/sudo ») se contournerait par une copie.
    """
    (tmp_path / "repli").mkdir()
    (tmp_path / "pipx").mkdir()
    for nom, machine in (("repli", machine_du_repli(tmp_path / "repli")),
                         ("pipx pose", _machine_avec_un_pipx_pose(
                             tmp_path / "pipx", machine_avec_affichage,
                             nature="pipx-paquet-systeme")[0])):
        # `machine_du_repli` rend un dict portant `env` ; la fabrique du pipx
        # pose rend directement l'environnement. On accepte les deux plutot
        # que de recopier une des deux formes.
        env = machine.get("env", machine)
        binaires = Path(env["PATH"].split(os.pathsep)[0])
        sudo = binaires / "sudo"
        if not sudo.exists():
            continue
        assert not sudo.is_symlink(), (
            "la machine %r expose le VRAI sudo par un lien (%s -> %s) : le "
            "produit peut y elever pour de vrai, et son comportement depend "
            "de l'uid de qui joue la suite -- root ici, `runner` sur la CI."
            % (nom, sudo, os.readlink(sudo)))
        texte = sudo.read_text(errors="replace")
        assert texte.startswith("#!"), (
            "le `sudo` de la machine %r n'est pas un script du banc : c'est "
            "une copie du binaire reel, ce qui rend la meme elevation "
            "possible" % nom)
