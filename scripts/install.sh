#!/usr/bin/env bash
# Installation en une commande de mixed_media_utility (macOS et Linux).
#
# Ce script POSE DES QUESTIONS. On lui colle la commande trouvee dans la
# documentation, il demande au clavier ce qu'on veut installer, et il n'y a
# aucune syntaxe a connaitre -- ni `[extra]`, ni nom de paquet. Les drapeaux
# restent disponibles pour qui les connait : un drapeau donne en ligne de
# commande SUPPRIME la question correspondante.
#
# CINQ QUESTIONS depuis la story 8.8, qui a ajoute le raccourci hors terminal
# (`EPIC8-ARB-19`). Elles etaient QUATRE et pas six apres les arbitrages d'Egan
# du 2026-09-07 sur la note de release de la story 8.6 -- ce qui a ete RETIRE du
# menu a cette occasion, et pourquoi :
#
#   * l'interface graphique -- verbatim : « Interface graphique : plus tard ».
#     La question 1 n'a donc plus que deux options. L'extra `[gui]` reste
#     installable A LA MAIN, par le drapeau `--gui` ou par
#     `pipx inject --force <application> "mmu-cli[gui]"` ; il n'est plus
#     PROPOSE ;
#   * l'apercu video en fenetre -- verbatim : « Inclus par defaut. Retrait
#     manuel ». La question disparait, et l'installateur DETECTE l'affichage a
#     la place (voir `affichage_disponible` plus bas) ;
#   * le choix de version -- verbatim : « C'est quoi la version d'essai ? ».
#     La question ne parlait pas a un utilisateur. `--version` et `--testpypi`
#     restent des drapeaux, pour nous.
#
# Deroule, dans cet ordre et jamais autrement :
#
#   1. etat des lieux (Python, ffmpeg, pipx, installation deja posee) -- on
#      regarde AVANT de demander, parce que deux questions ne se posent que
#      selon ce qu'on trouve ;
#   2. les questions ;
#   3. un recapitulatif de ce qui va se passer ;
#   4. l'execution ;
#   5. le bilan.
#
# LE PIEGE QUE CE SCRIPT EXISTE POUR EVITER, mesure le 2026-09-07 :
# sous `curl -fsSL ... | bash`, STDIN EST LE SCRIPT. Un `read` nu n'attend pas
# l'utilisateur, il consomme la LIGNE SUIVANTE DU SCRIPT -- ce n'est pas un
# blocage (ce serait visible), c'est une corruption silencieuse. Toute lecture
# clavier de ce fichier passe donc par `< /dev/tty`, sans exception, et
# `tests/unit/test_installateur_interactif.py` rougit si un `read` nu
# reapparait.
#
# ET LE TEST D'EXISTENCE DU TERMINAL N'EST PAS `[ -r /dev/tty ]`, mesure le
# meme jour : `/dev/tty` est un noeud crw-rw-rw- toujours present, si bien que
# `test -r` (qui n'interroge que les droits, via access(2)) rend VRAI meme dans
# un `setsid` sans terminal de controle. Le seul test qui distingue est
# l'OUVERTURE reelle -- `{ exec 9</dev/tty; } 2>/dev/null` -- et c'est celui
# que ce script emploie.
#
# POURQUOI pipx ET NON `pip install --user` : depuis la PEP 668, les Python
# systeme de Debian 12+, Ubuntu 23.04+, Fedora, et le Python de Homebrew
# refusent `pip install` hors venv avec `error: externally-managed-environment`.
# pipx cree un venv dedie par application et expose la commande sur le PATH.
#
# CE SCRIPT NE CONNAIT PAS SA PROPRE URL, volontairement : il ne telecharge que
# des paquets, jamais lui-meme. Le lieu d'hebergement (depot public) ne vit donc
# que dans la documentation et dans scripts/public-repo.env -- deplacer le
# script d'un depot a l'autre ne demande aucune retouche ici.
#
# Usage :
#   bash install.sh                 # TUI seule
#   bash install.sh --gui           # + extra [gui] (Qt : ~270 Mo de plus)
#   bash install.sh --testpypi      # depuis TestPyPI (paquet mmu-tui-test)
#   bash install.sh --version 0.2.0 # version precise
#   bash install.sh --dry-run       # montre les commandes sans rien executer
#
# POIDS, mesure le 2026-09-06 sur l'environnement que CE SCRIPT cree, c'est-a-
# dire celui de pipx : 91 Mo telecharges et 297 Mo sur disque (un
# `python -m venv` ordinaire en rend ~28 de plus, la difference etant `pip` et
# `setuptools` que pipx ne met pas dans l'environnement de l'application). La
# roue OpenCV installee est la variante `-headless` : les autres exigent libGL,
# libX11 et dix autres bibliotheques systeme qu'une machine vierge n'a pas, et
# que CE SCRIPT N'INSTALLE PAS -- volontairement, le brief etant << aucun
# prerequis >>. La seule fonction perdue est la fenetre de lecture previz, que
# la TUI refuse alors en nommant l'issue
# (`pipx inject --force mmu-tui opencv-python`).

set -euo pipefail

# ---------------------------------------------------------------- parametres

PYTHON_MINIMUM="3.11"

# Les deux distributions (story 8.5). Le nom de DISTRIBUTION n'est pas le nom
# de la COMMANDE : `mmu` est pris sur PyPI, la distribution s'appelle donc
# `mmu-cli` et sa commande console reste `mmu`.
DIST_CLI="mmu-cli"
DIST_TUI="mmu-tui"
COMMANDE_CLI="mmu"
COMMANDE_TUI="mmu-tui"

# Les deux roues OpenCV. Elles livrent le MEME module `cv2` et ne se connaissent
# pas l'une l'autre : pip ne verra jamais leur conflit, c'est a nous de ne pas
# les empiler.
ROUE_CV_SANS_FENETRES="opencv-python-headless"
ROUE_CV_AVEC_FENETRES="opencv-python"

# Reponses aux questions. La valeur "" signifie "pas encore repondu, donc la
# question se pose" ; une valeur posee par un drapeau supprime la question.
CHOIX_REPRISE=""         # 1 = mettre a jour, 2 = tout reinstaller, 3 = sortir
CHOIX_COMPOSANTS=""      # 1 = cli seule, 2 = cli + interface terminal
CHOIX_FFMPEG=""          # 1 = l'installer, 2 = je m'en occupe
CHOIX_PATH=""            # 1 = oui, 2 = non
CHOIX_RACCOURCI=""       # 1 = oui, 2 = non   (story 8.8)
CHOIX_VERIFICATION=""    # 1 = oui, 2 = non

AVEC_GUI=0               # extra [gui] : plus dans le menu, seulement --gui
CHOIX_VERSION=1          # 1 = derniere stable, 2 = version precise, 3 = TestPyPI
VERSION=""
SIMULATION=0
NON_INTERACTIF=0
DESINSTALLER=0

# CHERCHER CE QUI EST POSE HORS DU `PATH` (`EPIC11-ARB-279`, story 8.14). Le
# defaut est OUI : c'est le defaut d'Egan que la story ferme -- un pipx pose a
# la main, non detecte, recompile.
#
# Le drapeau qui l'eteint existe pour la meme raison que `--sans-ffmpeg` : un
# drapeau donne SUPPRIME la question correspondante, et il y a un regime ou
# l'on veut la supprimer -- une installation reproductible qui ne doit rien
# emprunter a ce qui traine dans `/usr/local/bin`. Il PRE-REPOND l'issue 2.
CHERCHER_HORS_DU_PATH=1

# LES TROIS ISSUES DE LA DESINSTALLATION (`EPIC11-ARB-274`), en constantes et
# non en litteraux dans l'invite. Deux motifs, et le second est mesure :
#
#   * `install.ps1` porte les MEMES libelles, MOT POUR MOT, et une frontiere du
#     banc les compare -- exactement comme elle le fait deja des cinq libelles
#     du raccourci. Un libelle recopie dans une invite diverge de son jumeau
#     sans que personne le voie ;
#   * l'issue 1 est le DEFAUT, et un defaut se lit a un seul endroit.
INTITULE_DU_RETRAIT="Que faut-il retirer ?"
ISSUE_APPLICATION_SEULE="l'application seule -- ni Python, ni ffmpeg, ni pipx"
ISSUE_TOUT_CE_QUE_LE_SCRIPT_A_POSE="l'application ET ce que CE SCRIPT a pose (ffmpeg, ffprobe, pipx)"
ISSUE_MONTRER_LES_COMMANDES="rien pour l'instant -- montre-moi les commandes pour le reste"

# LES TROIS ISSUES DE CE QUI EST POSE HORS DU `PATH` (`EPIC11-ARB-279`, story
# 8.14). Meme discipline, meme motif : `install.ps1` les porte MOT POUR MOT et
# une frontiere du banc les compare.
#
# L'ISSUE 1 EST LE DEFAUT, ET C'EST CELLE QUI NE POSE RIEN. C'est ce que l'AC10
# demande : un `--non-interactif` prend le defaut, et le defaut ne consomme ni
# reseau, ni heures de compilation, ni mot de passe.
#
# L'ISSUE 3 SORT, comme `ISSUE_MONTRER_LES_COMMANDES` sort du desinstalleur --
# c'est le meme geste et c'est deliberement le meme vocabulaire. « Ne rien
# faire » ne peut pas vouloir dire « poser quand meme » ; l'utilisateur recoit
# sa ligne, corrige son profil, et relance. Ce n'est pas un blocage sec : c'est
# une issue qu'il a choisie, et les deux autres restent offertes.
INTITULE_HORS_DU_PATH="Que faut-il en faire ?"
ISSUE_EXPOSER_POUR_CETTE_INSTALLATION="l'utiliser pour cette installation, et me donner la ligne a ajouter a mon profil"
ISSUE_IGNORER_ET_POSER_QUAND_MEME="l'ignorer et installer quand meme une autre copie"
ISSUE_LIGNE_SEULE_ET_SORTIR="rien pour l'instant -- montre-moi la ligne de PATH et sors"

afficher_aide() {
    cat <<'AIDE'
Installation de mixed_media_utility (macOS et Linux).

  bash install.sh                   dialogue au clavier (defaut)
  bash install.sh --non-interactif  prend tous les defauts, ne pose rien
  bash install.sh --desinstaller    retire l'application -- il DEMANDE jusqu'ou
  bash install.sh --dry-run         montre le plan sans rien executer

La DESINSTALLATION pose une question a TROIS issues avant de retirer quoi que
ce soit (`EPIC11-ARB-274`). Le defaut est la premiere, et `--non-interactif`
prend ce defaut : une machine muette ne retire jamais plus que l'application.

  1) l'application seule -- les quatre distributions pipx, la ligne de profil
     et le raccourci. Ni Python, ni ffmpeg, ni pipx ;
  2) l'application ET ce que CE SCRIPT a pose -- l'issue 1, plus les
     ffmpeg/ffprobe deposes par le repli precompile, plus pipx si c'est ce
     script qui l'a pose. Il ne retire QUE ce qu'un recu enregistre ;
  3) rien n'est retire : les commandes officielles de retrait de Python, de
     ffmpeg et de pipx sont AFFICHEES, pour la voie par laquelle ils sont
     arrives.

La MISE A JOUR, et surtout ce qu'elle NE touche PAS (`EPIC11-ARB-277`) :

  bash install.sh --mettre-a-jour   met a jour l'application deja posee

Elle met a jour la distribution pipx ET le mmu greffe dedans -- c'est ce que
`--include-injected` garantit, sans quoi la greffe resterait a son ancienne
version. Elle ne met a jour ni Python, ni ffmpeg, ni pipx : ce sont des
dependances du systeme, et elles se mettent a jour par le systeme.
La voie manuelle equivalente :  pipx upgrade mmu-tui --include-injected

Un drapeau donne supprime la question correspondante :

  --cli                  la ligne de commande seule (mmu)
  --tui                  mmu + l'interface terminal          [defaut]
  --ffmpeg               installer ffmpeg s'il manque        [defaut]
  --sans-ffmpeg          ne pas y toucher, je m'en occupe
  --path                 ajouter les commandes au PATH       [defaut]
  --sans-path            ne pas toucher au profil du shell
  --raccourci            ajouter mmu-tui au menu des applications  [defaut]
  --sans-raccourci       ne poser aucun raccourci
  --verifier             verifier l'installation a la fin    [defaut]
  --sans-verification    ne rien verifier
  --hors-du-path         consulter les emplacements usuels si le PATH
                         n'expose pas Python, ffmpeg ou pipx  [defaut]
  --ignorer-hors-du-path ne consulter aucun emplacement : ce qui n'est pas
                         sur le PATH est tenu pour absent
  --mettre-a-jour        sur une installation existante : la mettre a jour
  --reinstaller          sur une installation existante : tout refaire

Ce que le menu ne propose PAS, et qui reste accessible ici :

  --gui                  ajoute l'extra graphique [gui] (~270 Mo de plus)
  --version 0.2.0        une version precise
  --testpypi             depuis TestPyPI (pre-publication)

L'apercu video en fenetre n'est plus une question : la roue OpenCV AVEC
fenetres est posee des qu'un affichage est detecte. Pour revenir a la roue
sans fenetres :  pipx inject --force <application> opencv-python-headless
AIDE
}

while [ $# -gt 0 ]; do
    case "$1" in
        --cli)                 CHOIX_COMPOSANTS=1 ;;
        --tui)                 CHOIX_COMPOSANTS=2 ;;
        --gui)                 CHOIX_COMPOSANTS=2 ; AVEC_GUI=1 ;;
        --ffmpeg)              CHOIX_FFMPEG=1 ;;
        --sans-ffmpeg)         CHOIX_FFMPEG=2 ;;
        --testpypi)            CHOIX_VERSION=3 ;;
        --version)             shift; VERSION="${1:-}"; CHOIX_VERSION=2 ;;
        --path)                CHOIX_PATH=1 ;;
        --sans-path)           CHOIX_PATH=2 ;;
        --raccourci)           CHOIX_RACCOURCI=1 ;;
        --sans-raccourci)      CHOIX_RACCOURCI=2 ;;
        --verifier)            CHOIX_VERIFICATION=1 ;;
        --sans-verification)   CHOIX_VERIFICATION=2 ;;
        --hors-du-path)        CHERCHER_HORS_DU_PATH=1 ;;
        --ignorer-hors-du-path) CHERCHER_HORS_DU_PATH=0 ;;
        --mettre-a-jour)       CHOIX_REPRISE=1 ;;
        --reinstaller)         CHOIX_REPRISE=2 ;;
        --non-interactif)      NON_INTERACTIF=1 ;;
        --desinstaller)        DESINSTALLER=1 ;;
        --dry-run)             SIMULATION=1 ;;
        -h|--help)             afficher_aide; exit 0 ;;
        *) printf 'Option inconnue : %s (voir --help)\n' "$1" >&2; exit 2 ;;
    esac
    shift
done

# ---------------------------------------------------------------------------
#  Le suffixe du BAC A SABLE, et il porte sur QUATRE noms, pas deux.
# ---------------------------------------------------------------------------
# TestPyPI heberge les memes distributions sous un nom suffixe -- pour ne pas
# squatter le nom definitif tant que la publication est un essai --, et le
# renommage porte AUSSI sur les points d'entree : `publish.yml` reecrit les
# `[project.scripts]` en meme temps que le `name`. Mesure le 2026-09-08 sur les
# roues REELLEMENT publiees en 0.1.0 :
#
#   mmu_cli_test-0.1.0-py3-none-any.whl   -> console_scripts : mmu-test
#   mmu_tui_test-0.1.0-py3-none-any.whl   -> console_scripts : mmu-tui-test
#
# Le defaut que ce bloc ferme : le suffixe n'etait applique qu'aux PAQUETS, si
# bien qu'apres `--testpypi --verifier` le script lancait `mmu --version` -- une
# commande que cette installation n'a jamais posee. Deux issues, toutes deux
# fausses : l'echec, ou -- pire -- le succes annonce sur un `mmu` REEL deja
# present sur la machine, qui aurait fait passer pour verifiee une installation
# de bac a sable jamais exercee.
#
# Le suffixe se derive donc ICI, en un seul point, des la fin de la lecture des
# options -- c'est le premier endroit ou `CHOIX_VERSION` est arrete, et c'est
# avant que la moindre invite ne nomme une commande a l'utilisateur.
SUFFIXE=""
[ "${CHOIX_VERSION}" -eq 3 ] && SUFFIXE="-test"
PAQUET_CLI="${DIST_CLI}${SUFFIXE}"
PAQUET_TUI="${DIST_TUI}${SUFFIXE}"
COMMANDE_CLI="${COMMANDE_CLI}${SUFFIXE}"
COMMANDE_TUI="${COMMANDE_TUI}${SUFFIXE}"

# ------------------------------------------------------------------ affichage

# Les couleurs ne servent qu'un humain devant un terminal. Quand la sortie est
# canalisee (CI, journal, banc de test), les codes ANSI ne sont plus de la mise
# en forme : ce sont des octets parasites au milieu du texte qu'on relit.
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    GRAS=$'\033[1m'; FAIBLE=$'\033[2m'; BLEU=$'\033[1;34m'
    VERT=$'\033[32m'; ROUGE=$'\033[1;31m'; FIN=$'\033[0m'
else
    GRAS=""; FAIBLE=""; BLEU=""; VERT=""; ROUGE=""; FIN=""
fi

etape()   { printf '\n%s==>%s %s%s%s\n' "${BLEU}" "${FIN}" "${GRAS}" "$*" "${FIN}"; }
info()    { printf '    %s\n' "$*"; }
succes()  { printf '    %sok%s %s\n' "${VERT}" "${FIN}" "$*"; }
alerte()  { printf '    %s!%s  %s\n' "${ROUGE}" "${FIN}" "$*"; }
echouer() { printf '\n%sEchec :%s %s\n' "${ROUGE}" "${FIN}" "$*" >&2; exit 1; }

# Execute une commande, ou l'affiche seulement en mode --dry-run.
executer() {
    if [ "${SIMULATION}" -eq 1 ]; then
        printf '    [simulation] %s\n' "$*"
    else
        info "\$ $*"
        "$@"
    fi
}

# ------------------------------------------------------ le dialogue au clavier

# Y a-t-il un humain au bout ? La reponse ne se devine pas, elle s'OUVRE.
# Voir l'entete : `[ -r /dev/tty ]` rend VRAI sans terminal de controle.
TERMINAL=0
if { exec 9</dev/tty; } 2>/dev/null; then
    TERMINAL=1
    exec 9<&-
fi

if [ "${NON_INTERACTIF}" -eq 1 ]; then
    RAISON_MUETTE="mode non interactif"
elif [ "${TERMINAL}" -eq 0 ]; then
    RAISON_MUETTE="pas de terminal"
else
    RAISON_MUETTE=""
fi

# Pose une question a choix numerotes. Rend son resultat dans REPONSE (et non
# sur stdout : l'intitule et les options sont eux aussi de la sortie, les
# capturer par $(...) les rendrait invisibles a l'utilisateur).
#
#   demander <defaut> <intitule> <option 1> [<option 2> ...]
#
# Trois garanties, dans l'ordre ou elles ont ete demandees :
#   - une TOUCHE, jamais une syntaxe : un chiffre, ou Entree seule ;
#   - une saisie non reconnue REPOSE la question, elle n'echoue pas ;
#   - sans terminal, jamais un blocage sec : le defaut est pris ET ANNONCE.
REPONSE=""
demander() {
    defaut="$1"; intitule="$2"; shift 2
    nombre_d_options=$#
    saisie=""
    numero=0

    if [ -n "${RAISON_MUETTE}" ]; then
        printf '\n%s%s%s\n' "${GRAS}" "${intitule}" "${FIN}"
        eval "defaut_libelle=\${$((defaut))}"
        printf '    %s : je prends %d) %s\n' "${RAISON_MUETTE}" "${defaut}" "${defaut_libelle}"
        REPONSE="${defaut}"
        return 0
    fi

    while true; do
        printf '\n%s%s%s\n' "${GRAS}" "${intitule}" "${FIN}"
        numero=1
        for libelle in "$@"; do
            if [ "${numero}" -eq "${defaut}" ]; then
                printf '      %s%d)%s %s %s[defaut]%s\n' \
                       "${GRAS}" "${numero}" "${FIN}" "${libelle}" "${FAIBLE}" "${FIN}"
            else
                printf '      %d) %s\n' "${numero}" "${libelle}"
            fi
            numero=$((numero + 1))
        done
        printf '    Ton choix [%d] puis Entree : ' "${defaut}"

        # LA ligne qui justifie tout ce fichier. `< /dev/tty` et pas autre
        # chose : sous `curl | bash`, stdin est le script lui-meme.
        if ! read -r saisie < /dev/tty; then
            printf '\n    entree fermee : je prends %d\n' "${defaut}"
            REPONSE="${defaut}"
            return 0
        fi

        saisie="$(printf '%s' "${saisie}" | tr -d '[:space:]')"
        if [ -z "${saisie}" ]; then
            REPONSE="${defaut}"
            return 0
        fi
        case "${saisie}" in
            *[!0-9]*) ;;
            *) if [ "${saisie}" -ge 1 ] && [ "${saisie}" -le "${nombre_d_options}" ]; then
                   REPONSE="${saisie}"
                   return 0
               fi ;;
        esac
        alerte "Je n'ai pas compris \"${saisie}\". Repondre par un chiffre de 1 a ${nombre_d_options}, ou Entree."
    done
}

# ---------------------------------------------------- detection de la machine

case "$(uname -s)" in
    Darwin) SYSTEME="macos" ;;
    Linux)  SYSTEME="linux" ;;
    *) echouer "Systeme non gere par ce script : $(uname -s).
   Sur Windows, utiliser scripts/install.ps1 (PowerShell)." ;;
esac

# ---------------------------------------------------------------------------
#  Quand Homebrew va-t-il COMPILER ? Deux causes, et l'architecture domine
# ---------------------------------------------------------------------------
# Homebrew n'installe vite que s'il a une BOUTEILLE (binaire precompile) pour
# la plateforme courante. Sinon il compile DEPUIS LES SOURCES, et sur Python
# comme sur ffmpeg et leur arbre de dependances, ca se compte en heures.
#
# DEUX CAUSES, mesurees toutes les deux, et la seconde a ete trouvee en
# renversant la premiere :
#
#  1. macOS 12 et en dessous. Homebrew l'annonce -- « You are using macOS 12.
#     We (and Apple) do not provide support for this old version. » -- puis
#     compile. Trouve par Egan le 2026-09-08 en jouant le parcours reel ;
#
#  2. TOUT Mac INTEL, quelle que soit la version de macOS. Trouve le meme jour,
#     sur une machine de sa monteuse -- un Intel 2018 en Sequoia (15), donc
#     tres au-dessus du plancher de la cause 1, et qui compilait quand meme.
#     La premiere redaction de cette garde predisait le contraire ; la mesure
#     l'a demolie.
#
# LA MESURE DE LA CAUSE 2, prise sur l'API de Homebrew (formulae.brew.sh),
# 2026-09-08. Une etiquette macOS Intel s'ecrit SANS prefixe (`sonoma`,
# `ventura`) ; `arm64_*` designe Apple Silicon :
#
#     python@3.12  arm64_linux arm64_sequoia arm64_sonoma arm64_tahoe x86_64_linux
#     openssl@3    (idem)
#     mpdecimal    (idem)
#     ffmpeg       (idem) + sonoma
#
# Aucune etiquette macOS Intel pour Python et son arbre. Une seule pour ffmpeg,
# et c'est Sonoma (14), pas Sequoia (15). Sur un Mac Intel, Homebrew n'a donc
# pratiquement plus rien a servir : il compile. Et `arm64_tahoe` existe sans
# `tahoe` -- la tendance ne s'inversera pas.
#
# Le produit, lui, DECLARE macOS 12 comme plancher et il le tient : les roues
# Python existent pour cette version-la (mesure du 2026-09-08 : opencv-python-
# headless 4.10.0.84 et pypdfium2 5.11.0, sur les DEUX architectures). Ce qui
# ne tenait pas, c'est le CHEMIN D'INSTALLATION -- un defaut different.
#
# CE QUE CETTE GARDE NE SAIT PAS, dit plutot que tu : elle ne consulte pas
# l'API au lancement -- ce serait un appel reseau avant d'avoir rien installe,
# et une panne de plus. Elle ne sait donc pas si telle formule a, ce jour-la,
# une bouteille. Sur un Intel en Sonoma, ffmpeg en a une, et la garde poserait
# quand meme sa question : elle est LEGEREMENT trop large de ce cote-la. Le
# cout de cet exces est une question dont la reponse par defaut mene a une
# voie plus rapide de toute facon ; le cout du defaut inverse etait des heures
# de compilation sans un mot.
MACOS_MAJEUR=""
MACOS_ARCH=""
MACOS_PLANCHER_BOUTEILLES=13
if [ "${SYSTEME}" = "macos" ] && command -v sw_vers >/dev/null 2>&1; then
    # Le majeur se prend par expansion de parametre, jamais par `cut` : la
    # garde tournerait alors dans un PATH qui ne le porte pas, et rendrait
    # `cut: command not found` + un code 127 -- mesure par le banc, qui
    # fabrique exactement une PATH pareille. Un avertissement facultatif n'a
    # aucune raison de dependre d'un binaire externe.
    MACOS_VERSION="$(sw_vers -productVersion 2>/dev/null)"
    MACOS_MAJEUR="${MACOS_VERSION%%.*}"
    case "${MACOS_MAJEUR}" in
        ''|*[!0-9]*) MACOS_MAJEUR="" ;;
    esac
fi
if [ "${SYSTEME}" = "macos" ]; then
    MACOS_ARCH="$(uname -m 2>/dev/null)"
fi

# Rend VRAI des qu'UNE des deux causes tient. Les deux sont lues separement --
# et non fondues en un seul test -- parce que le message doit nommer CELLE qui
# s'applique : « votre macOS est ancien » et « votre Mac est un Intel » ne se
# reparent pas de la meme facon.
macos_trop_ancien_pour_les_bouteilles() {
    [ -n "${MACOS_MAJEUR}" ] || return 1
    [ "${MACOS_MAJEUR}" -lt "${MACOS_PLANCHER_BOUTEILLES}" ]
}

mac_intel_sans_bouteilles() {
    [ "${MACOS_ARCH}" = "x86_64" ]
}

homebrew_compile_depuis_les_sources() {
    [ "${GESTIONNAIRE}" = "brew" ] || return 1
    macos_trop_ancien_pour_les_bouteilles || mac_intel_sans_bouteilles
}

# ============================================================================
#  Le repli precompile : le script POSE le binaire (`EPIC11-ARB-271`)
# ============================================================================
#
# Tranche par Egan le 2026-09-08, verbatim : « Je penche pour le repli
# automatique de notre script. Avec une condition : en cas d'echec (url, erreur
# etc) le script donne toujours la commande alternative a taper dans le
# terminal, et si possible la plus "officielle" pour chaque dependance
# necessaire. »
#
# LE DEFAUT QUE CA FERME, et il a ete constate en vrai le meme jour. La garde
# du matin prevenait avant une compilation Homebrew, puis renvoyait au
# terminal. Egan, verbatim : « si on choisi dans l'outil de faire la voie
# "manuelle" pour toutes les dependances, le souci est que l'outil n'est pas
# forcement ajoute au path et donc pas forcement detecte. » Ce jour-la, pipx a
# ete pose a la main, n'a pas ete detecte, et a du etre recompile : le repli
# manuel ne resout pas le probleme, il le DEPLACE -- d'une compilation vers une
# deuxieme compilation.
#
# CE QUE CE BLOC NE FAIT PAS, dit plutot que tu :
#
#   * il ne s'applique QU'A macOS, et seulement a ffmpeg/ffprobe et Python
#     (AC8). Linux garde ses gestionnaires de paquets, qui ne compilent pas ;
#     `install.ps1` ne gagne aucun repli precompile, n'ayant aucune garde de
#     compilation et rien de son comportement n'etant mesure dans ce depot ;
#   * il n'interroge AUCUNE source pour son condensat, parce qu'aucune ne le
#     sert -- mesure du 2026-09-08 : l'API d'evermeet rend `url`, `size` et
#     `sig` (GPG) sans champ de condensat, et `python-3.12.8-macos11.pkg.sha256`
#     rend HTTP 404 la ou `.asc` et `.sigstore` rendent 200. Le condensat se
#     prend UNE fois et vit ici en constante. C'est ce qui le rend fort : une
#     source compromise ne peut pas changer a la fois l'archive et une
#     constante qui vit dans notre depot ;
#   * il n'emploie PAS GPG, l'autre voie de verification. Elle exigerait `gpg`
#     sur la machine, qu'un Mac vierge n'a pas -- ce qui rouvrirait exactement
#     le probleme que ce bloc ferme.
#
# L'ENGAGEMENT DE MAINTENANCE (AC12), parce que trois URL et trois condensats
# vieilliront et que personne n'a signe pour les suivre s'il n'est pas ecrit :
#
#   * DEUX FICHIERS les portent, et il faut les reprendre ENSEMBLE. Cette
#     ligne-ci disait « ils vivent ICI et NULLE PART ailleurs » jusqu'au
#     2026-09-08 ; c'etait FAUX, et la couche 3 de la revue l'a mesure en
#     suivant la procedure a la lettre : 17 tests rouges que la procedure
#     n'annoncait pas. Les deux lieux sont :
#       1. les six constantes ci-dessous ;
#       2. `tests/unit/test_installateur_interactif.py`, dans le SEUL test qui
#          recopie les trois condensats
#          (`test_les_TROIS_condensats_epingles_sont_ceux_qui_ont_ete_MESURES`).
#          Il les recopie EXPRES : tout le reste du banc LIT la constante ici,
#          si bien qu'y mettre trois zeros laisserait le lot vert. C'est ce
#          test-la, et lui seul, qui dit qu'une valeur a ete relevee archive en
#          main plutot que de memoire ;
#   * pour les mettre a jour : relever la version courante
#     (`https://evermeet.cx/ffmpeg/info/ffmpeg/release` pour ffmpeg,
#     `https://www.python.org/downloads/macos/` pour Python), telecharger,
#     calculer `shasum -a 256`, remplacer la version ET le condensat ensemble,
#     DANS LES DEUX FICHIERS ;
#   * ce qui rougit quand la version epinglee disparait de la SOURCE : la jambe
#     `macos-15-intel` de la CI (`EPIC11-ARB-272`), et c'est une reponse qui a change
#     le 2026-09-08. Elle joue une installation REELLE, donc elle emprunte
#     reellement ce repli, et une etape exige ensuite que ffmpeg et ffprobe
#     DEMARRENT. Une archive injoignable ou un condensat change a la source la
#     fait rougir -- jusque-la, rien dans le depot ne l'aurait dit. En dehors
#     de cette jambe, aucune frontiere n'interroge le reseau, et c'est voulu :
#     ce serait une panne de plus sur le chemin d'installation. Chez
#     l'utilisateur, le repli DEGRADE proprement -- il nomme l'echec et donne
#     la commande de secours. La mesure du 2026-09-08 dit par ailleurs que les
#     deux sources gardent leur historique -- ffmpeg 6.1.1 et Python 3.11.0
#     repondent encore 200 --, donc une URL epinglee ne pourrit pas, elle
#     vieillit.

FFMPEG_VERSION_EPINGLEE="9.0.1"
FFMPEG_ZIP_URL="https://evermeet.cx/ffmpeg/ffmpeg-${FFMPEG_VERSION_EPINGLEE}.zip"
FFMPEG_ZIP_SHA256="8a8c9e549983409fe6604b9aa665648b7a5def9407fe814c39c8b2ea7f64a48f"
FFPROBE_ZIP_URL="https://evermeet.cx/ffmpeg/ffprobe-${FFMPEG_VERSION_EPINGLEE}.zip"
FFPROBE_ZIP_SHA256="d13f35db03456b7f65b7edb6437c86e23810fbfe91795e571f5b77211343b4f1"

PYTHON_PKG_VERSION_EPINGLEE="3.12.8"
PYTHON_PKG_URL="https://www.python.org/ftp/python/${PYTHON_PKG_VERSION_EPINGLEE}/python-${PYTHON_PKG_VERSION_EPINGLEE}-macos11.pkg"
PYTHON_PKG_SHA256="c411b5372d563532f5e6b589af7eb16e95613d61bd5af7bfe78563467130bbff"

# Le repertoire ou pipx expose ses applications. On le DEMANDE a pipx plutot
# que de le deviner -- c'est deja ce que fait `install.ps1` (`Get-RepertoireBinPipx`),
# et ce fichier etait le seul des deux a coder le chemin en dur.
#
# Ce que coute la devinette, et c'est le defaut meme qu'Egan decrit : avec un
# `PIPX_HOME` ou un `PIPX_BIN_DIR` poses, `${HOME}/.local/bin` vise le mauvais
# repertoire, et un ffmpeg depose la ne serait PAS sur le PATH -- un outil pose
# mais pas detecte. Le repli sur `${HOME}/.local/bin` reste, parce que c'est le
# defaut de pipx et la seule reponse possible quand pipx n'est pas encore la.
repertoire_binaire_de_pipx() {
    local repertoire
    repertoire=""
    if command -v pipx >/dev/null 2>&1; then
        repertoire="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || true)"
    fi

    # LA VARIABLE, QUAND PIPX N'EST PAS ENCORE LA (finding `C1-3` de la revue
    # du 2026-09-08, recoupe par `C2-1`). La question se pose bel et bien, et
    # elle se posait meme TOUJOURS avant ce triage : l'etape ffmpeg precedait
    # l'etape pipx, donc `command -v pipx` echouait a coup sur sur un Mac
    # vierge et cette fonction ne lisait JAMAIS son chemin nominal. L'ordre des
    # deux etapes a ete corrige dans le meme mouvement -- mais l'ordre seul ne
    # suffit pas : `--sans-ffmpeg`, un pipx pose apres coup, ou simplement une
    # machine ou pipx ne s'installe pas rouvrent le meme trou.
    #
    # `PIPX_BIN_DIR` est la variable que pipx lui-meme honore, documentee comme
    # telle. La lire est donc l'inverse d'une devinette : c'est la MEME source
    # que `pipx environment`, consultee sans pipx. Ce qui n'est PAS etabli, et
    # qu'on n'invente donc pas : le sort de `XDG_BIN_HOME`, honore par certaines
    # versions recentes de pipx et par aucune mesure de ce depot.
    if [ -z "${repertoire}" ]; then
        repertoire="${PIPX_BIN_DIR:-}"
    fi

    # UN CHEMIN RELATIF EST REFUSE, et c'est la meme garde que l'atelier porte
    # depuis l'origine de la story (finding `C2-1` : elle avait ete posee d'un
    # cote seulement). Mesure du 2026-09-08 avec un `PIPX_BIN_DIR` valant
    # `bin_relatif` : `mkdir -p` reussit, `[ -w ]` reussit, `mv` depose les
    # deux binaires DANS LE REPERTOIRE COURANT de qui a lance la commande, et
    # `export PATH="bin_relatif:${PATH}"` met ensuite une entree relative dans
    # le PATH du processus -- c'est-a-dire un PATH dont le sens change a chaque
    # `cd`. Le repli sur le defaut de pipx est la seule issue sure.
    case "${repertoire}" in
        /*) ;;
        *)  repertoire="" ;;
    esac

    if [ -z "${repertoire}" ]; then
        repertoire="${HOME}/.local/bin"
    fi
    printf '%s\n' "${repertoire}"
}

# La commande de secours LA PLUS OFFICIELLE de chaque dependance -- pas la plus
# pratique : la plus officielle (`EPIC11-ARB-271`). Elle s'affiche sur TOUS les
# chemins d'echec du repli, et aussi quand l'utilisateur choisit de ne rien
# poser : un refus qui n'offre aucune issue est aussi fautif qu'une destruction
# silencieuse (`EPIC11-ARB-89`).
#
# LE DEUXIEME ARGUMENT ETEND LA MEME TABLE AU RETRAIT (`EPIC11-ARB-274`,
# story 8.12) : `commande_de_secours <dependance> retrait`. C'est une
# EXTENSION et non une table neuve, et le motif est celui qui a fait naitre
# cette fonction -- « un remede recopie a cinq endroits diverge », mesure sur
# les deux formulations de ffmpeg qui coexistaient avant `EPIC11-ARB-271`. Les
# memes cles de dependance, les memes branches de gestionnaire, un seul
# endroit a corriger le jour ou Fedora change de depot.
#
# ET LA LIGNE PYTHON DU RETRAIT N'EST PAS UNE COMMANDE, volontairement : c'est
# un renvoi a la documentation officielle, avec son motif. Retirer le Python du
# systeme casse le systeme (raison 1 de l'arbitrage), et une frontiere negative
# du banc balaie les deux scripts pour s'assurer qu'aucun `apt remove python3`,
# `brew uninstall python` ou equivalent n'y est jamais ecrit.
commande_de_secours() {
    geste_de_secours="${2:-pose}"
    info ""

    # LA TABLE DE POSE VIENT EN PREMIER, ET CE N'EST PAS UN GOUT.
    # `tests/unit/test_conformite_de_la_documentation.py` releve la commande
    # ffmpeg de cette fonction en cherchant le PREMIER `ffmpeg)` qu'elle porte,
    # pour verifier que les pages d'installation ne divergent pas d'elle
    # (`EPIC11-ARB-276`). Depuis que la table porte AUSSI le retrait, l'ordre
    # decide de ce que ce releve lit : place derriere, la pose devenait
    # « brew uninstall ffmpeg » et six bancs de documentation rougissaient.
    # Mesure du 2026-09-08, a l'ecriture de la story 8.12.
    if [ "${geste_de_secours}" != "retrait" ]; then
        info "La commande de secours pour ${1}, la plus officielle disponible :"
        case "$1" in
            ffmpeg)
                case "${GESTIONNAIRE}" in
                    brew)    info "  brew install ffmpeg"
                             info "  ou les binaires du projet : https://ffmpeg.org/download.html" ;;
                    apt-get) info "  sudo apt-get install ffmpeg" ;;
                    dnf)     info "  sudo dnf install ffmpeg   (depot RPM Fusion sur Fedora/RHEL)" ;;
                    *)       info "  https://ffmpeg.org/download.html" ;;
                esac ;;
            python|python@*)
                if [ "${SYSTEME}" = "macos" ]; then
                    info "  l'installeur officiel python.org : https://www.python.org/downloads/"
                else
                    info "  le paquet Python de votre distribution"
                    info "  ou https://www.python.org/downloads/"
                fi ;;
            *)
                # JAMAIS UN BLOCAGE SEC, meme ici (`EPIC11-ARB-89`). Cette
                # branche ne connait pas la dependance ; elle nomme quand meme
                # une issue, plutot que de rendre un « aucune commande connue »
                # qui laisse l'utilisateur sans rien. Les deux couches de revue
                # du 2026-09-08 l'ont atteinte par deux chemins independants
                # (`C1-2` et `C2-4`) : `python@3.12` y tombait, parce que la
                # traduction du nom de formule vivait UNIQUEMENT chez
                # l'appelant. Elle vit desormais aussi dans le motif ci-dessus
                # -- deux endroits a casser au lieu d'un.
                info "  ${1} n'a pas de commande officielle epinglee dans ce script."
                info "  Les voies officielles par systeme sont dans la documentation :"
                # La racine, et PAS `…/installation/` : la section
                # « Installation » de `mkdocs.yml` (l. 69-73) n'a pas de page
                # d'index, donc ce chemin-la rendrait un 404. Verifie a
                # l'ecriture plutot que suppose -- une commande de secours qui
                # envoie sur une page morte est un blocage sec de plus, pas une
                # issue.
                info "  https://gantiz.github.io/mixed_media_utility/" ;;
        esac
        return 0
    fi

    # LE RETRAIT, MEME TABLE ET MEMES CLES (story 8.12, `EPIC11-ARB-274`).
    info "Pour RETIRER ${1}, la voie la plus officielle disponible :"
    case "$1" in
        ffmpeg)
            case "${GESTIONNAIRE}" in
                brew)    info "  brew uninstall ffmpeg" ;;
                apt-get) info "  sudo apt-get remove ffmpeg" ;;
                dnf)     info "  sudo dnf remove ffmpeg" ;;
                *)       info "  ffmpeg n'est pas venu d'un gestionnaire de paquets connu ici."
                         info "  S'il a ete pose par ce script, l'issue 2 le retire ;"
                         info "  sinon, retirer le binaire la ou il a ete depose." ;;
            esac ;;
        pipx)
            # `pipx uninstall-all` D'ABORD, et ce n'est pas du zele : retirer
            # pipx sans cela laisse sur la machine un venv par application
            # posee, plus aucune commande sur le PATH, et aucun outil pour les
            # retrouver.
            info "  pipx uninstall-all      (les autres applications posees par pipx)"
            case "${GESTIONNAIRE}" in
                brew)    info "  brew uninstall pipx" ;;
                apt-get) info "  sudo apt-get remove pipx" ;;
                dnf)     info "  sudo dnf remove pipx" ;;
                *)       info "  python3 -m pip uninstall pipx   (si pipx est venu de pip)" ;;
            esac ;;
        python|python@*)
            # JAMAIS UNE COMMANDE DE RETRAIT ICI (AC6). Sur Debian et Ubuntu,
            # le gestionnaire de paquets lui-meme depend du Python du systeme ;
            # sur macOS, `/usr/bin/python3` appartient aux outils d'Apple. Et le
            # Python qu'un utilisateur croit avoir installe est presque toujours
            # celui qui etait deja la.
            info "  ce script ne donne AUCUNE commande de retrait pour Python."
            info "  Le retirer casse le systeme sur la plupart des machines :"
            info "  le gestionnaire de paquets en depend, et l'interpreteur"
            info "  du systeme n'a pas ete pose par cette installation."
            info "  La voie officielle, si vous savez ce que vous faites :"
            info "  https://www.python.org/downloads/" ;;
        *)
            info "  ${1} n'a pas de voie de retrait epinglee dans ce script."
            info "  https://gantiz.github.io/mixed_media_utility/" ;;
    esac
    return 0
}

# La dependance derriere un nom de formule Homebrew. `python@3.12` et
# `python@3.13` sont la MEME dependance ; la commande de secours ne se choisit
# pas sur un numero de version.
dependance_du_paquet() {
    case "$1" in
        python@*) printf 'python\n' ;;
        *)        printf '%s\n' "$1" ;;
    esac
}

# La seule facon de sortir d'un repli en echec. Elle NOMME la panne puis donne
# la commande : jamais un blocage sec, jamais un echec muet.
echec_du_repli() {
    alerte "Repli precompile abandonne : $2."
    commande_de_secours "$1"
}

# Le condensat SHA-256 d'un fichier, sur les deux familles d'outils : macOS
# livre `shasum` (perl) et PAS `sha256sum` ; les Linux livrent l'inverse. Le
# premier champ se prend par expansion de parametre et non par `cut` ou `awk` :
# ni l'un ni l'autre n'est garanti dans la PATH d'une machine vierge, et c'est
# la meme lecon que le majeur de `sw_vers` a deja payee ici.
condensat_sha256() {
    local sortie_du_condensat
    if command -v shasum >/dev/null 2>&1; then
        sortie_du_condensat="$(shasum -a 256 "$1" 2>/dev/null)" || return 1
    elif command -v sha256sum >/dev/null 2>&1; then
        sortie_du_condensat="$(sha256sum "$1" 2>/dev/null)" || return 1
    else
        return 1
    fi
    [ -n "${sortie_du_condensat}" ] || return 1
    printf '%s\n' "${sortie_du_condensat%% *}"
}

# Y a-t-il de quoi calculer un condensat ? Question posee AVANT de telecharger
# 52 Mo : un repli qui ne peut pas verifier ne doit pas commencer.
condensat_calculable() {
    command -v shasum >/dev/null 2>&1 || command -v sha256sum >/dev/null 2>&1
}

# Le plafond de temps d'un lancement, en secondes. Il vaut 30 : de quoi laisser
# un binaire de 25 Mo demarrer sur une machine chargee, et pas de quoi
# suspendre une installation.
PLAFOND_DE_LANCEMENT=30

# LANCER UNE COMMANDE AVEC UN PLAFOND, ET SANS `timeout(1)` -- que macOS ne
# livre pas (finding `C2-6` de la revue du 2026-09-08). Le regime mesure ce
# jour-la : `"${cible}/ffmpeg" -version` sur un binaire qui n'en finit pas
# suspend l'installateur SANS UN MOT, derniere ligne « ok condensat verifie »,
# et les 52 Mo d'atelier ne sont jamais nettoyes. Le cas reel n'est pas
# theorique : premier lancement d'un binaire non notarise, evaluation
# Gatekeeper qui part au reseau, pare-feu qui *drop* au lieu de refuser.
#
# ON TUE PAR PID CAPTURE AU LANCEMENT, jamais par motif -- c'est la regle 6 de
# `CLAUDE.md`, posee le 2026-08-31 apres qu'un `pkill -f` eut emporte une
# mesure a 79 %. Il n'y a pas un seul motif dans cette fonction.
#
# Rend le code de la commande, ou 124 quand le plafond a ete atteint -- la
# meme convention que `timeout(1)`, pour qu'un lecteur qui connait l'un lise
# l'autre.
lancer_avec_plafond() {
    local plafond pid_du_lancement attente issue
    plafond="$1"; shift
    # LA SORTIE SE CAPTURE ICI OU NULLE PART (finding `C2-6` de la couche 2 de
    # la revue 8.14, 2026-09-09). L'appelant qui voulait la VERSION relancait
    # le binaire une seconde fois, SANS plafond -- donc un binaire qui repond
    # au premier appel et suspend au second suspendait l'installateur, mesure
    # a 90 s. C'est-a-dire la panne meme que cette fonction existe pour
    # fermer, rouverte deux lignes plus bas.
    #
    # La capture se fait par REDIRECTION et non par une enveloppe `sh -c` :
    # `$!` doit rester le PID DU BINAIRE. Avec une enveloppe, `kill` tuerait
    # le `sh` et laisserait le petit-fils courir -- ce qui est exactement le
    # « tuer par ressemblance » que la regle 6 interdit, transpose a la
    # parente.
    if [ -n "${JOURNAL_DU_LANCEMENT:-}" ]; then
        "$@" > "${JOURNAL_DU_LANCEMENT}" 2>/dev/null &
    else
        "$@" >/dev/null 2>&1 &
    fi
    pid_du_lancement=$!
    attente=0
    while [ "${attente}" -lt "${plafond}" ]; do
        kill -0 "${pid_du_lancement}" 2>/dev/null || break
        sleep 1
        attente=$((attente + 1))
    done
    if kill -0 "${pid_du_lancement}" 2>/dev/null; then
        kill -9 "${pid_du_lancement}" 2>/dev/null || true
        wait "${pid_du_lancement}" 2>/dev/null || true
        return 124
    fi
    issue=0
    wait "${pid_du_lancement}" || issue=$?
    return "${issue}"
}

# Un membre d'archive precompile, du telechargement jusqu'au depot.
#
#   $1 nom du binaire   $2 URL   $3 condensat attendu   $4 atelier   $5 cible
#
# L'archive d'evermeet ne contient QU'UN SEUL membre, a la racine (mesure du
# 2026-09-08) : `unzip -o` rend directement `ffmpeg` dans le repertoire
# courant, il n'y a pas de sous-dossier a traverser.
poser_un_membre_precompile() {
    local nom_du_binaire url condensat_attendu atelier cible archive condensat_obtenu issue_du_lancement cause_du_lancement
    nom_du_binaire="$1"; url="$2"; condensat_attendu="$3"; atelier="$4"; cible="$5"
    archive="${atelier}/${nom_du_binaire}.zip"

    info "Telechargement de ${nom_du_binaire} ${FFMPEG_VERSION_EPINGLEE} (~25 Mo)..."
    # `--max-time 900` FERME LE SYMETRIQUE DU PLAFOND DE LANCEMENT (`C2-6`) :
    # `--connect-timeout` ne borne que la POIGNEE DE MAIN. Un serveur qui
    # accepte la connexion puis debite un octet par minute tient l'installateur
    # indefiniment, et rien ne le dirait. 900 s laissent passer 25 Mo a 30 ko/s,
    # c'est-a-dire une ligne franchement mauvaise, et pas une ligne morte.
    if ! executer curl -fL --retry 2 --connect-timeout 20 --max-time 900 -o "${archive}" "${url}"; then
        echec_du_repli "ffmpeg" "le telechargement de ${nom_du_binaire} a echoue (URL morte, reseau coupe ou serveur indisponible)"; return 1
    fi

    # Le condensat AVANT le dezippage : une archive fausse ne s'ouvre pas
    # « pour voir ». Un condensat qui ne correspond pas fait ABANDONNER le
    # repli -- jamais poser le binaire « quand meme », meme avec un
    # avertissement.
    condensat_obtenu="$(condensat_sha256 "${archive}")" || condensat_obtenu=""
    if [ -z "${condensat_obtenu}" ]; then
        echec_du_repli "ffmpeg" "le condensat de ${nom_du_binaire} n'a pas pu etre calcule"; return 1
    fi
    if [ "${condensat_obtenu}" != "${condensat_attendu}" ]; then
        alerte "attendu ${condensat_attendu}"
        alerte "obtenu  ${condensat_obtenu}"
        echec_du_repli "ffmpeg" "le condensat SHA-256 de ${nom_du_binaire} ne correspond pas (archive tronquee, alteree, ou version changee a la source)"; return 1
    fi
    succes "condensat SHA-256 de ${nom_du_binaire} verifie"

    if ! (cd "${atelier}" && unzip -o -q "${archive}"); then
        echec_du_repli "ffmpeg" "l'archive de ${nom_du_binaire} n'a pas pu etre ouverte"; return 1
    fi
    if [ ! -f "${atelier}/${nom_du_binaire}" ]; then
        echec_du_repli "ffmpeg" "l'archive de ${nom_du_binaire} ne contient pas le binaire attendu"; return 1
    fi

    chmod +x "${atelier}/${nom_du_binaire}" 2>/dev/null || true
    if ! mv -f "${atelier}/${nom_du_binaire}" "${cible}/${nom_du_binaire}"; then
        echec_du_repli "ffmpeg" "${cible} n'a pas pu recevoir ${nom_du_binaire}"; return 1
    fi

    # GATEKEEPER, et c'etait un angle mort COMPLET de ce depot avant cette
    # story : les mots `quarantine`, `xattr`, `spctl`, `codesign` et
    # `Gatekeeper` n'apparaissaient dans AUCUN fichier de `scripts/`, `tests/`
    # ni `docs/` (recherche insensible a la casse, 2026-09-08).
    #
    # CE QUI N'EST PAS ETABLI, et il ne faut pas l'affirmer : qu'un fichier
    # tire par `curl` porte effectivement `com.apple.quarantine`. L'attribut
    # est pose par les applications qui s'y inscrivent -- navigateurs, clients
    # mail --, et curl n'en fait pas partie a notre connaissance. Le retrait
    # est donc DEFENSIF : inoffensif si l'attribut est absent, inoffensif si
    # `xattr` lui-meme manque. La mesure appartient a `macos-15-intel` et `macos-14`
    # de la story 8.10, qui lira `xattr -l` sur le binaire pose.
    #
    # C'est pourquoi il y a DEUX gestes et non un : le LANCEMENT ci-dessous est
    # le seul verdict qui vaille. Un attribut retire ne prouve pas qu'un
    # binaire demarre, et sur Apple Silicon c'est la signature, pas la
    # quarantaine, qui decide.
    #
    # LE `|| true` EST DEFENSIF ET SON EFFET EST MASQUE AUJOURD'HUI, ce qui est
    # dit plutot que tu -- la campagne de mutation de la story 8.11 l'a mesure
    # (mutant `M9`, survivant assume). `xattr -d` rend 1 quand l'attribut est
    # absent, ce qui est le cas nominal ; mais cette fonction est appelee
    # depuis un `if ... && ...`, et bash y SUSPEND `set -e` a l'interieur de la
    # fonction. Sonde :
    #
    #     interieur() { false; echo APRES; return 0; }
    #     if interieur; then ... fi   -> « APRES » s'affiche, EXIT=0
    #     interieur                   -> le script MEURT, EXIT=1, sans un mot
    #
    # Retirer le `|| true` ne change donc rien tant que l'appel reste dans une
    # condition, et TUE le script le jour ou il n'y sera plus. On le garde.
    if command -v xattr >/dev/null 2>&1; then
        xattr -d com.apple.quarantine "${cible}/${nom_du_binaire}" 2>/dev/null || true
    fi

    issue_du_lancement=0
    lancer_avec_plafond "${PLAFOND_DE_LANCEMENT}" "${cible}/${nom_du_binaire}" -version \
        || issue_du_lancement=$?
    if [ "${issue_du_lancement}" -ne 0 ]; then
        # LE BINAIRE QUI NE DEMARRE PAS EST RETIRE, et c'est le finding `C1-1`
        # de la revue du 2026-09-08. Ce qu'il coutait, mesure ce jour-la : un
        # `ffprobe` que le produit VIENT DE DECLARER « ne demarre pas » restait
        # en place et executable, et comme `~/.local/bin` est PREFIXE au PATH
        # par ce script, l'orphelin MASQUAIT le `brew install ffmpeg` que la
        # commande de secours affiche trois lignes plus bas. Le remede
        # recommande devenait inoperant a cause de la panne qu'il repare.
        rm -f "${cible}/${nom_du_binaire}" 2>/dev/null || true
        # La cause se calcule AVANT, pour que l'annonce et la sortie tiennent
        # sur UNE ligne : c'est la forme que balaye
        # `test_AUCUN_chemin_d_echec_du_repli_ne_se_termine_SANS_commande`, et
        # elle a rougi sur la premiere redaction de ce bloc. La frontiere a
        # fait son travail ; c'est le code qui s'aligne, pas elle.
        if [ "${issue_du_lancement}" -eq 124 ]; then
            cause_du_lancement="n'a pas rendu la main en ${PLAFOND_DE_LANCEMENT} s (evaluation Gatekeeper bloquee par un pare-feu, ou binaire qui suspend)"
        else
            cause_du_lancement="ne demarre pas (Gatekeeper, signature, ou architecture incompatible)"
        fi
        echec_du_repli "ffmpeg" "${nom_du_binaire} a ete pose mais ${cause_du_lancement} -- il a ete RETIRE"; return 1
    fi
    succes "${nom_du_binaire} pose dans ${cible} et il DEMARRE"
    return 0
}

# Le repli ffmpeg : le plus propre des deux, et c'est ce qui le rend defaut.
# Aucun `sudo`, aucune ecriture hors du compte de l'utilisateur, et la
# destination est deja celle que le script pose sur le PATH -- donc detecte
# immediatement, sans rouvrir de terminal.
repli_precompile_ffmpeg() {
    local cible_du_repli atelier_du_repli issue_du_repli poses_par_ce_repli nom_deja_pose
    if [ "${SIMULATION}" -eq 1 ]; then
        # Un plan qui tait une de ses etapes n'est plus un plan -- mais on ne
        # telecharge pas 52 Mo pour les jeter.
        printf '    [simulation] curl -fL -o <atelier>/ffmpeg.zip %s\n' "${FFMPEG_ZIP_URL}"
        printf '    [simulation] curl -fL -o <atelier>/ffprobe.zip %s\n' "${FFPROBE_ZIP_URL}"
        printf '    [simulation] verifier le condensat SHA-256 des deux archives\n'
        printf '    [simulation] unzip -o puis deposer ffmpeg et ffprobe dans %s\n' \
               "$(repertoire_binaire_de_pipx)"
        printf '    [simulation] xattr -d com.apple.quarantine sur les deux binaires\n'
        printf '    [simulation] ffmpeg -version pour verifier qu il demarre\n'
        printf '    [simulation] noter ffmpeg et ffprobe dans %s\n' "${RECU_FICHIER}"
        return 0
    fi

    if ! command -v curl >/dev/null 2>&1; then
        echec_du_repli "ffmpeg" "curl est absent de cette machine"; return 1
    fi
    if ! command -v unzip >/dev/null 2>&1; then
        echec_du_repli "ffmpeg" "unzip est absent de cette machine"; return 1
    fi
    if ! condensat_calculable; then
        echec_du_repli "ffmpeg" "ni shasum ni sha256sum n'est disponible, le condensat serait inverifiable"; return 1
    fi

    cible_du_repli="$(repertoire_binaire_de_pipx)"
    if ! mkdir -p "${cible_du_repli}" 2>/dev/null; then
        echec_du_repli "ffmpeg" "${cible_du_repli} n'a pas pu etre cree"; return 1
    fi
    if [ ! -w "${cible_du_repli}" ]; then
        echec_du_repli "ffmpeg" "${cible_du_repli} n'est pas inscriptible"; return 1
    fi

    # L'ATELIER DOIT ETRE UN CHEMIN ABSOLU, et ce n'est pas une precaution de
    # style. Les archives d'evermeet ne portent qu'UN membre, A LA RACINE :
    # `unzip` le depose donc dans le repertoire de travail, et un atelier vide
    # ou relatif ferait de ce repertoire CELUI DE L'UTILISATEUR -- son home,
    # son bureau, un depot. Un installateur qui laisse 80 Mo la ou on l'a lance
    # est de la meme famille que le raccourci de la 8.8 qui ecrivait dans le
    # vrai menu d'applications.
    #
    # Et RIEN ne le signalerait, mesure le 2026-09-08 :
    #
    #     cd "" && pwd                  -> REUSSIT, on reste dans le courant
    #     unzip -o -q -d "" a.zip       -> REUSSIT, extrait dans le courant
    #
    # Ni `cd` ni `-d` ne refusent une destination vide. Ce test-ci est donc le
    # seul rempart, et il refuse aussi le relatif, qui a le meme effet.
    atelier_du_repli="$(mktemp -d 2>/dev/null)" || atelier_du_repli=""
    case "${atelier_du_repli}" in
        /*) ;;
        *)  atelier_du_repli="" ;;
    esac
    if [ -z "${atelier_du_repli}" ] || [ ! -d "${atelier_du_repli}" ]; then
        echec_du_repli "ffmpeg" "aucun repertoire de travail temporaire n'a pu etre cree"; return 1
    fi

    # CE QUI A ETE POSE SE NOTE, POUR POUVOIR SE DEFAIRE (finding `C1-1`,
    # recoupe par `C2-10`). Avant ce triage, ce bloc ne nettoyait que
    # l'ATELIER : un condensat faux sur `ffprobe` laissait `ffmpeg` dans la
    # destination, code de sortie global 0, et le mot « abandonne » etait une
    # demi-verite. Un `ffmpeg` sans son `ffprobe` n'est pas une demi-victoire :
    # c'est un outil que le produit refusera, POSE DEVANT celui que la commande
    # de secours recommande.
    #
    # On ne retire que ce que CET appel a pose -- jamais un binaire qui etait
    # la avant, dont on ne sait rien.
    poses_par_ce_repli=""
    if poser_un_membre_precompile "ffmpeg" "${FFMPEG_ZIP_URL}" "${FFMPEG_ZIP_SHA256}" \
                                  "${atelier_du_repli}" "${cible_du_repli}"; then
        poses_par_ce_repli="ffmpeg"
        if poser_un_membre_precompile "ffprobe" "${FFPROBE_ZIP_URL}" "${FFPROBE_ZIP_SHA256}" \
                                      "${atelier_du_repli}" "${cible_du_repli}"; then
            poses_par_ce_repli="ffmpeg ffprobe"
            issue_du_repli=0
        else
            issue_du_repli=1
        fi
    else
        issue_du_repli=1
    fi
    rm -rf "${atelier_du_repli}" 2>/dev/null || true

    if [ "${issue_du_repli}" -ne 0 ] && [ -n "${poses_par_ce_repli}" ]; then
        for nom_deja_pose in ${poses_par_ce_repli}; do
            rm -f "${cible_du_repli}/${nom_deja_pose}" 2>/dev/null || true
        done
        info "Ce qui avait deja ete depose dans ${cible_du_repli} a ete retire :"
        info "un ffmpeg sans son ffprobe masquerait le paquet recommande ci-dessus."
    fi

    if [ "${issue_du_repli}" -eq 0 ]; then
        # LE RECU S'ECRIT ICI, ET NULLE PART PLUS HAUT (AC2). Deux entrees
        # DISTINGUABLES -- `ffmpeg` et `ffprobe` --, parce que ce sont deux
        # objets et que le retrait doit pouvoir en manquer un sans manquer
        # l'autre.
        #
        # APRES la reussite, jamais avant : `poser_un_membre_precompile` retire
        # le binaire qui ne demarre pas, et le bloc au-dessus retire `ffmpeg`
        # quand `ffprobe` echoue. Un recu ecrit d'avance nommerait des fichiers
        # que ce script vient lui-meme de retirer.
        #
        # La DESTINATION vient de `repertoire_binaire_de_pipx`, la meme
        # fonction qui l'a choisie a la pose : elle ne se devine pas plus au
        # retrait qu'a l'aller.
        noter_dans_le_recu "ffmpeg" "${cible_du_repli}/ffmpeg"
        noter_dans_le_recu "ffprobe" "${cible_du_repli}/ffprobe"
        # Le PATH du PROCESSUS, pour que le controle qui suit l'etape ffmpeg
        # trouve ce qu'on vient de poser. La ligne de profil, elle, reste
        # l'affaire de `pipx ensurepath` : ce script n'ecrit jamais dans un
        # profil lui-meme.
        export PATH="${cible_du_repli}:${PATH}"
        info "ffmpeg et ffprobe sont dans ${cible_du_repli}, que pipx expose deja."
    fi
    return "${issue_du_repli}"
}

# Le repli Python, et il est l'AUTRE cas : `sudo installer -pkg ... -target /`
# est la seule voie officielle sur macOS, et elle exige le mot de passe
# administrateur. Un `curl | bash` qui reclame un mot de passe sans prevenir
# est un motif que beaucoup refusent a vue -- donc on ANNONCE, on laisse
# refuser, et un refus mene a la commande de secours et jamais a un blocage.
repli_precompile_python() {
    local atelier_du_repli issue_du_repli
    # L'ANNONCE VIENT EN PREMIER, avant meme la simulation (AC5) : c'est ce
    # qu'on annonce AVANT de lancer, et un plan qui tairait la question la
    # plus intrusive du parcours ne serait pas un plan. Le defaut est de
    # REFUSER -- le defaut d'une question ne consomme ni des heures ni un mot
    # de passe, et sans terminal personne ne peut en taper un de toute facon.
    alerte "L'installeur officiel python.org s'installe pour TOUTE la machine."
    info   "Ce geste demande votre mot de passe administrateur (sudo installer)."
    info   "C'est la seule voie officielle sur macOS ; il n'y en a pas sans mot de passe."
    demander 2 "Lancer l'installeur officiel Python ${PYTHON_PKG_VERSION_EPINGLEE} ?" \
        "oui - lancer, et taper mon mot de passe administrateur" \
        "non - me donner la commande, je le ferai moi-meme"
    if [ "${REPONSE}" -ne 1 ]; then
        info "Tres bien, rien n'est lance."
        commande_de_secours "python"; return 1
    fi

    if [ "${SIMULATION}" -eq 1 ]; then
        printf '    [simulation] curl -fL -o <atelier>/python.pkg %s\n' "${PYTHON_PKG_URL}"
        printf '    [simulation] verifier le condensat SHA-256 du paquet\n'
        printf '    [simulation] sudo installer -pkg <atelier>/python.pkg -target /\n'
        printf '    [simulation] noter python dans %s\n' "${RECU_FICHIER}"
        return 0
    fi

    if ! command -v curl >/dev/null 2>&1; then
        echec_du_repli "python" "curl est absent de cette machine"; return 1
    fi
    if ! condensat_calculable; then
        echec_du_repli "python" "ni shasum ni sha256sum n'est disponible, le condensat serait inverifiable"; return 1
    fi
    # `${SUDO}` est VIDE sur macOS, et VOLONTAIREMENT : il n'est pose que sous
    # Linux (l. 834-841), parce que Homebrew refuse de tourner en root. Ce
    # `installer -pkg ... -target /` est le SEUL geste eleve du script sur
    # macOS, et il ne peut donc pas emprunter cette variable-la : ecrire
    # `${SUDO} installer` y lancerait `installer` NU, qui echouerait sur un
    # refus de droits apres avoir telecharge 46 Mo -- et l'annonce du mot de
    # passe aurait menti. L'elevation est donc nommee ici, en toutes lettres.
    if ! command -v sudo >/dev/null 2>&1; then
        echec_du_repli "python" "sudo est absent, l'installeur officiel ne peut pas etre lance"; return 1
    fi

    # Meme garde de chemin absolu que le repli ffmpeg, et pour le meme motif :
    # voir le commentaire la-bas. Ici c'est `curl -o` qui ecrirait un `.pkg` de
    # 46 Mo dans le repertoire courant de qui a lance la commande.
    atelier_du_repli="$(mktemp -d 2>/dev/null)" || atelier_du_repli=""
    case "${atelier_du_repli}" in
        /*) ;;
        *)  atelier_du_repli="" ;;
    esac
    if [ -z "${atelier_du_repli}" ] || [ ! -d "${atelier_du_repli}" ]; then
        echec_du_repli "python" "aucun repertoire de travail temporaire n'a pu etre cree"; return 1
    fi

    if _poser_le_paquet_python "${atelier_du_repli}"; then
        issue_du_repli=0
    else
        issue_du_repli=1
    fi
    rm -rf "${atelier_du_repli}" 2>/dev/null || true
    return "${issue_du_repli}"
}

# Le corps du repli Python, isole pour que l'atelier temporaire se nettoie a UN
# seul endroit plutot qu'a chacune des quatre sorties.
_poser_le_paquet_python() {
    local atelier paquet condensat_obtenu
    atelier="$1"
    paquet="${atelier}/python-${PYTHON_PKG_VERSION_EPINGLEE}-macos11.pkg"

    info "Telechargement de l'installeur python.org ${PYTHON_PKG_VERSION_EPINGLEE} (~46 Mo)..."
    if ! executer curl -fL --retry 2 --connect-timeout 20 --max-time 900 -o "${paquet}" "${PYTHON_PKG_URL}"; then
        echec_du_repli "python" "le telechargement de l'installeur a echoue (URL morte, reseau coupe ou serveur indisponible)"; return 1
    fi

    condensat_obtenu="$(condensat_sha256 "${paquet}")" || condensat_obtenu=""
    if [ -z "${condensat_obtenu}" ]; then
        echec_du_repli "python" "le condensat de l'installeur n'a pas pu etre calcule"; return 1
    fi
    if [ "${condensat_obtenu}" != "${PYTHON_PKG_SHA256}" ]; then
        alerte "attendu ${PYTHON_PKG_SHA256}"
        alerte "obtenu  ${condensat_obtenu}"
        echec_du_repli "python" "le condensat SHA-256 de l'installeur ne correspond pas (archive tronquee, alteree, ou version changee a la source)"; return 1
    fi
    succes "condensat SHA-256 de l'installeur python.org verifie"

    if ! executer sudo installer -pkg "${paquet}" -target /; then
        echec_du_repli "python" "l'installeur a echoue (mot de passe refuse, droits insuffisants, ou paquet rejete)"; return 1
    fi
    succes "Python ${PYTHON_PKG_VERSION_EPINGLEE} pose par l'installeur officiel python.org"
    # NOTE, ET JAMAIS POUR ETRE RETIRE (AC6). Le recu enregistre un geste
    # passe : celui-ci a bel et bien eu lieu, et l'utilisateur a le droit de
    # savoir ou. Mais `retirer_selon_le_recu` refuse toujours la nature
    # `python` -- retirer le Python du systeme casse le systeme, et l'issue 3
    # renvoie a la documentation officielle plutot qu'a une commande.
    #
    # Le chemin est celui que l'installeur officiel CIBLE, documente comme
    # tel ; on ne le sonde pas, parce qu'un recu n'est pas un etat.
    noter_dans_le_recu "python" "/Library/Frameworks/Python.framework"
    return 0
}

# L'aiguillage : quel repli pour quelle formule Homebrew. Une formule sans
# repli mesure n'en recoit pas -- on n'invente pas une URL de plus, chacune
# etant un engagement de maintenance (AC12).
repli_precompile() {
    case "$1" in
        ffmpeg)   repli_precompile_ffmpeg ;;
        python@*) repli_precompile_python ;;
        *)        echec_du_repli "$(dependance_du_paquet "$1")" "aucun binaire precompile n'est epingle pour $1"; return 1 ;;
    esac
}

# Y a-t-il un repli precompile pour cette formule ? Lu a UN seul endroit, pour
# que l'aiguillage ci-dessus et la question posee a l'utilisateur ne puissent
# pas diverger -- une question qui proposerait une voie que l'aiguillage ne
# connait pas serait une promesse creuse.
un_repli_precompile_existe() {
    case "$1" in
        ffmpeg|python@*) return 0 ;;
        *)               return 1 ;;
    esac
}

# Y a-t-il un affichage graphique ? Ce n'est PAS une question posee a
# l'utilisateur (arbitrage d'Egan : « Inclus par defaut. Retrait manuel »),
# c'est une detection -- et elle existe parce qu'`EPIC11-ARB-253` a mesure ce
# que coute l'erreur : la roue OpenCV avec fenetres exige DOUZE bibliotheques
# systeme absentes d'un serveur nu, d'un conteneur minimal ou d'un WSL sans X.
# Les poser la-bas ne donne pas un apercu video : ca fait echouer `import cv2`
# AVANT la premiere ligne du produit. La detection tient donc la demande sans
# rouvrir ce defaut.
affichage_disponible() {
    case "${SYSTEME}" in
        macos) return 0 ;;   # Quartz est toujours la, il n'y a rien a detecter
        *) [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ] ;;
    esac
}

# Gestionnaire de paquets, pour installer ce qui manque. Une seule detection,
# reutilisee pour Python, ffmpeg et pipx.
GESTIONNAIRE=""
if [ "${SYSTEME}" = "macos" ]; then
    command -v brew >/dev/null 2>&1 && GESTIONNAIRE="brew"
else
    for candidat in apt-get dnf pacman zypper apk; do
        if command -v "${candidat}" >/dev/null 2>&1; then
            GESTIONNAIRE="${candidat}"
            break
        fi
    done
fi

# `sudo` n'est requis que sur Linux, et seulement si l'on n'est pas deja root.
SUDO=""
if [ "${SYSTEME}" = "linux" ] && [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        SUDO="__PAS_DE_SUDO__"
    fi
fi

# Le fichier de profil que `pipx ensurepath` toucherait. Nomme dans la question
# du PATH : on ne demande pas la permission d'ecrire quelque part sans dire ou.
profil_du_shell() {
    case "$(basename "${SHELL:-/bin/sh}")" in
        zsh)  printf '%s' "${ZDOTDIR:-${HOME}}/.zshrc" ;;
        bash) printf '%s' "${HOME}/.bashrc" ;;
        fish) printf '%s' "${HOME}/.config/fish/config.fish" ;;
        *)    printf '%s' "${HOME}/.profile" ;;
    esac
}
PROFIL="$(profil_du_shell)"

# Le raccourci du menu des applications (story 8.8). Ces deux valeurs sont
# posees ICI, avant le bloc de desinstallation, parce que c'est lui qui s'en
# sert le premier -- et il s'execute AVANT l'etat des lieux. Toute variable
# citee la-bas et affectee plus loin serait « unbound » sous `set -u`.
#
# `~/.local/share/applications` : le repertoire UTILISATEUR du menu
# (freedesktop). Aucun droit administrateur, propre au compte qui installe --
# comme le venv pipx. Pas le Bureau, dont l'emplacement varie et se traduit ;
# pas `/usr/share/applications`, qui demanderait `sudo` et poserait un fichier
# pour tous les comptes de la machine.
#
# `XDG_DATA_HOME` RELATIF : la specification XDG dit qu'un chemin qui ne
# commence pas par `/` doit etre tenu pour INVALIDE et le defaut employe.
# Mesure de la revue (couche 2, `C2-10`) : sans ce test, un
# `XDG_DATA_HOME=donnees-relatives` ecrivait le raccourci dans le repertoire
# COURANT de l'appelant -- hors de tout menu, et introuvable par un
# `--desinstaller` lance d'ailleurs. Un objet pose qu'on ne peut plus retirer
# est exactement ce qu'`EPIC11-ARB-89` interdit.
RACINE_DONNEES="${XDG_DATA_HOME:-}"
case "${RACINE_DONNEES}" in
    /*) ;;
    *)  RACINE_DONNEES="${HOME}/.local/share" ;;
esac
RACCOURCI_DOSSIER="${RACINE_DONNEES}/applications"
RACCOURCI_FICHIER="${RACCOURCI_DOSSIER}/mmu-tui.desktop"

# ---------------------------------------------------------------------------
#  LE RECU : ce que ce script a pose HORS pipx, et rien d'autre
# ---------------------------------------------------------------------------
# `EPIC11-ARB-274`. L'issue 2 de la desinstallation ne peut reprendre que ce
# qu'elle sait avoir ete pose ; rien ne l'enregistrait, et c'est pourquoi
# `--desinstaller` laissait sur place les 52 Mo du repli precompile en
# affichant « Ni Python, ni ffmpeg, ni pipx ne sont touches » -- une phrase
# vraie devenue une demi-verite le jour ou le script s'est mis a poser ffmpeg
# lui-meme (finding `C2-9` de la revue 8.11).
#
# CE QUE LE RECU N'EST PAS, et c'est ce qui decide de sa forme : ni un
# manifeste, ni un etat, ni une source de verite sur la machine. Il enregistre
# un GESTE PASSE. Le desinstalleur verifie toujours l'existence avant de
# retirer -- un recu qui pretendrait savoir serait pire que pas de recu.
#
# Une ligne par objet, TROIS champs separes par une tabulation : la nature, le
# chemin absolu, la date. Lisible a l'oeil, et relu par un `while read` sans
# aucun outil.
#
# MEME GARDE DE CHEMIN ABSOLU QUE `XDG_DATA_HOME` VINGT LIGNES PLUS HAUT, et
# pour le meme motif exactement : la specification XDG tient un chemin relatif
# pour INVALIDE, et sans cette garde un `XDG_STATE_HOME=etat-relatif` ecrirait
# le recu dans le repertoire COURANT de qui a lance la commande -- introuvable
# par un `--desinstaller` lance d'ailleurs. C'est le troisieme chemin de cette
# famille dans ce script (l'atelier du repli, la destination du repli, le
# raccourci) : la garde se recopie parce que la valeur, elle, differe.
RACINE_ETAT="${XDG_STATE_HOME:-}"
case "${RACINE_ETAT}" in
    /*) ;;
    *)  RACINE_ETAT="${HOME}/.local/state" ;;
esac
RECU_DOSSIER="${RACINE_ETAT}/mmu"
RECU_FICHIER="${RECU_DOSSIER}/pose-par-installeur.txt"

# Note un objet pose. NE RETOURNE JAMAIS EN ECHEC : un recu qui ne peut pas
# s'ecrire ne doit pas faire echouer une installation qui, elle, a reussi. Il
# le DIT, et la desinstallation se degradera plus tard en issue 1 (AC4).
#
# LE RECU S'ECRIT APRES LA REUSSITE, jamais avant -- et ce n'est pas un gout.
# `poser_un_membre_precompile` RETIRE le binaire qui ne demarre pas, et
# `repli_precompile_ffmpeg` retire ce qui avait deja ete pose quand un membre
# suivant echoue. Un recu ecrit d'avance nommerait des fichiers que le produit
# vient lui-meme de retirer, et l'issue 2 les chercherait a jamais.
noter_dans_le_recu() {
    nature_posee="$1"; chemin_pose="$2"

    # UN CHEMIN RELATIF NE SE NOTE PAS. Le recu ne sert qu'a retrouver un
    # objet ; un chemin qui change de sens a chaque `cd` ne retrouve rien.
    case "${chemin_pose}" in
        /*) ;;
        *)  alerte "Chemin non absolu, non note dans le recu : ${chemin_pose}"
            return 0 ;;
    esac

    if ! mkdir -p "${RECU_DOSSIER}" 2>/dev/null; then
        alerte "Le recu n'a pas pu etre ecrit dans ${RECU_DOSSIER}."
        info   "L'installation continue ; la desinstallation ne saura pas"
        info   "reprendre ${chemin_pose} toute seule."
        return 0
    fi
    if ! printf '%s\t%s\t%s\n' "${nature_posee}" "${chemin_pose}" \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || printf 'date-inconnue')" \
            >> "${RECU_FICHIER}" 2>/dev/null; then
        alerte "Le recu ${RECU_FICHIER} n'a pas pu etre complete."
        return 0
    fi
    return 0
}

# Relit le recu et rend, dans RECU_RETENU, les entrees dont le chemin EXISTE
# ENCORE -- une par ligne, « nature<TAB>chemin ». Rend 1 quand il n'y a pas de
# recu du tout : c'est la degradation de l'AC4, pas une erreur.
#
# UNE ENTREE DISPARUE EST DITE ET SAUTEE (AC3). Elle n'est ni une erreur ni un
# silence : quelqu'un a deja retire le fichier a la main, et le lui dire vaut
# mieux que de faire comme si le recu avait raison.
#
# Le resultat passe par une VARIABLE et non par stdout, comme `demander` avec
# `REPONSE` : `info` ecrit lui aussi sur stdout, et une fonction qui rendrait
# ses lignes par `$(...)` avalerait ses propres annonces.
RECU_RETENU=""
lire_le_recu() {
    local nature chemin date_de_pose
    RECU_RETENU=""
    [ -f "${RECU_FICHIER}" ] || return 1
    # `|| [ -n "${nature}" ]` : LA DERNIERE LIGNE D'UN FICHIER SANS SAUT DE
    # LIGNE FINAL EST PERDUE AUTREMENT (finding 1 de la couche 2, 2026-09-08),
    # et elle l'est EN SILENCE ET DEFINITIVEMENT. `read` rend non nul en EOF
    # sans `\n` -- apres avoir pourtant rempli ses variables --, donc la boucle
    # s'arrete sans traiter cette entree.
    #
    # Mesure : deux entrees, la derniere non terminee -> `ffmpeg` retire,
    # `ffprobe` NI RETIRE NI MENTIONNE, puis `retirer_le_repertoire_d_etat`
    # efface le recu. L'objet devient IRRECUPERABLE : plus personne ne sait ou
    # il est. Atteignable par le produit lui-meme -- un `printf >>` sur un
    # disque plein ecrit une ligne tronquee.
    #
    # Le jumeau PowerShell n'avait pas ce defaut (`Get-Content` ignore la
    # terminaison) : l'AC11 « meme contrat » etait rompue du cote qui PERD des
    # donnees.
    while IFS="$(printf '\t')" read -r nature chemin date_de_pose || [ -n "${nature}" ]; do
        [ -n "${nature}" ] || continue
        [ -n "${chemin}" ] || continue
        # UN CHEMIN DU RECU DOIT ETRE ABSOLU, ET LA GARDE N'EXISTAIT QU'A
        # L'ECRITURE (finding 2 de la couche 2). Mesure : un recu portant
        # `ffmpeg<TAB>victime.txt`, lance depuis un repertoire qui contient ce
        # fichier -- SUPPRIME, et annonce « ok Retire : victime.txt (ffmpeg,
        # pose par ce script) ».
        #
        # C'est la doctrine du module retournee contre elle-meme : le recu
        # n'est PAS une source de verite, et il etait pourtant cru sur parole
        # pour la seule chose qui compte, l'adresse de ce qu'on efface. Un recu
        # ne se signe pas ; la garde doit donc vivre du cote qui AGIT.
        case "${chemin}" in
            /*) ;;
            *)  alerte "Chemin non absolu au recu, rien n'est retire : ${chemin}"
                continue ;;
        esac
        # `-e` ET `-L` : un binaire remplace par un lien casse n'est pas un
        # fichier, et resterait sinon en place a jamais. Meme lecon que le
        # `-f`/`-L` du raccourci de la story 8.8.
        if [ -e "${chemin}" ] || [ -L "${chemin}" ]; then
            RECU_RETENU="${RECU_RETENU}${nature}	${chemin}
"
        else
            info "deja disparu, rien a retirer : ${chemin} (${nature}, note le ${date_de_pose})"
        fi
    done < "${RECU_FICHIER}"
    return 0
}

# CE QUE RETIRER pipx COUTE, DIT AVANT DE LE FAIRE (`EPIC11-ARB-89` : « la
# rigueur de l'outil ne doit pas empecher une ecriture destructive CONSCIENTE
# (apres avertissement) »).
#
# C'est le seul objet du recu dont le retrait mord HORS du perimetre de ce
# script : pipx gere peut-etre d'autres applications, et les retirer de la
# machine avec lui n'a jamais ete demande. On les NOMME -- `pipx list --short`
# rend ce qui reste apres le retrait de nos quatre distributions -- plutot que
# de laisser l'utilisateur le decouvrir apres coup.
#
# Ce n'est PAS un blocage : l'issue 2 a ete choisie, elle s'execute. C'est
# l'avertissement qui manquait, pas un refus de plus.
avertir_du_cout_du_retrait_de_pipx() {
    local restantes
    restantes=""
    if command -v pipx >/dev/null 2>&1; then
        restantes="$(pipx list --short 2>/dev/null | tr -d '\r' || true)"
    fi
    if [ -n "${restantes}" ]; then
        alerte "pipx gere encore d'autres applications, qui perdront leurs commandes :"
        # Un `if` et non un `&&` : sous `set -e`, un `&&` dont le test echoue
        # rend 1 et fait sortir le sous-shell du tube -- la derniere ligne
        # vide couperait donc la liste sans un mot.
        printf '%s\n' "${restantes}" | while IFS= read -r ligne_restante; do
            if [ -n "${ligne_restante}" ]; then
                info "  ${ligne_restante}"
            fi
        done
        info "Pour les reprendre proprement avant : pipx uninstall-all"
    fi
    return 0
}

# Retire pipx PAR LA VOIE QUI L'A POSE, jamais par un `rm` sur son binaire.
#
# C'est la raison 2 d'`EPIC11-ARB-274`, appliquee a nous-memes : retirer sous
# un gestionnaire de paquets le fichier qu'il croit posseder le laisse avec un
# paquet fantome. La voie est connue parce qu'elle est ECRITE DANS LA NATURE
# du recu -- `pipx-paquet-systeme` ou `pipx-pip-utilisateur` --, notee au
# moment de la pose par la branche qui a reellement servi.
#
# Les six noms de paquet sont les MEMES que ceux passes a
# `installer_paquet_systeme` a la pose : `python-pipx` sur Arch,
# `python3-pipx` sur openSUSE. Les recopier ici est deliberement symetrique --
# poser et retirer nomment le meme paquet, ou l'un des deux se trompe.
#
# JAMAIS UN BLOCAGE SEC : tout echec NOMME sa panne et donne la commande.
retirer_pipx_du_systeme() {
    if [ "${SUDO}" = "__PAS_DE_SUDO__" ]; then
        alerte "Droits administrateur indisponibles : pipx n'a pas ete retire."
        commande_de_secours "pipx" "retrait"
        return 0
    fi
    case "${GESTIONNAIRE}" in
        brew)    executer brew uninstall pipx || alerte "brew n'a pas retire pipx." ;;
        apt-get) executer ${SUDO} apt-get remove -y pipx || alerte "apt-get n'a pas retire pipx." ;;
        dnf)     executer ${SUDO} dnf remove -y pipx || alerte "dnf n'a pas retire pipx." ;;
        pacman)  executer ${SUDO} pacman -R --noconfirm python-pipx || alerte "pacman n'a pas retire pipx." ;;
        zypper)  executer ${SUDO} zypper remove -y python3-pipx || alerte "zypper n'a pas retire pipx." ;;
        apk)     executer ${SUDO} apk del pipx || alerte "apk n'a pas retire pipx." ;;
        *)       alerte "Aucun gestionnaire de paquets reconnu : pipx n'a pas ete retire."
                 commande_de_secours "pipx" "retrait" ;;
    esac
    return 0
}

# L'autre voie : `pip install --user pipx`, le repli du script quand aucun
# paquet systeme n'etait disponible. On repasse par pip, pour la meme raison.
#
# `python3` se cherche ICI et pas plus haut : l'interpreteur retenu par
# l'installation (`PYTHON`) est choisi APRES ce bloc, et le citer ici tuerait
# le script sous `set -u`. Ce qu'on veut n'est de toute facon pas le meme
# objet -- c'est le python qui porte le site utilisateur ou pip a pose pipx.
retirer_pipx_de_pip_utilisateur() {
    local python_pour_pip
    python_pour_pip="$(command -v python3 2>/dev/null || true)"
    if [ -z "${python_pour_pip}" ]; then
        alerte "Aucun python3 sur le PATH : pipx n'a pas pu etre retire."
        commande_de_secours "pipx" "retrait"
        return 0
    fi
    executer "${python_pour_pip}" -m pip uninstall -y pipx \
        || alerte "pip n'a pas retire pipx."
    return 0
}

# Retire ce que le recu enregistre, CHAQUE NATURE SELON SA POLITIQUE. Trois
# politiques, et elles ne se ressemblent pas :
#
#   * `ffmpeg` / `ffprobe` -- des fichiers que CE script a ecrits, dans un
#     repertoire qu'il a choisi. Ils n'appartiennent a aucun gestionnaire : un
#     `rm` suffit et ne laisse personne dans un etat faux ;
#   * `pipx-*` -- pose par le script, mais PAR UNE VOIE. On repasse par elle ;
#   * `python` -- JAMAIS retire (AC6, raison 1 de l'arbitrage). Il est NOMME,
#     et la voie officielle est donnee. Une entree de recu ne suffit pas a
#     faire retirer quelque chose : c'est la politique qui decide, et pour
#     Python elle dit non, toujours.
#
# Le recu n'est PAS une source de verite : `lire_le_recu` a deja ecarte ce qui
# n'existe plus, et un binaire present mais absent du recu n'est jamais
# touche -- on ne retire que l'intersection.
retirer_selon_le_recu() {
    local nature chemin
    while IFS="$(printf '\t')" read -r nature chemin; do
        [ -n "${nature}" ] || continue
        case "${nature}" in
            ffmpeg|ffprobe)
                if [ "${SIMULATION}" -eq 1 ]; then
                    printf '    [simulation] rm -f %s\n' "${chemin}"
                elif rm -f "${chemin}"; then
                    succes "Retire : ${chemin} (${nature}, pose par ce script)"
                else
                    # LE SEUL APPEL DESTRUCTIF DU BLOC ETAIT LE SEUL SANS
                    # GARDE (finding `C1-3` de la couche 1, 2026-09-08), et
                    # `set -euo pipefail` n'est jamais relache ici : un `rm`
                    # qui echoue TUAIT la desinstallation en vol. Mesure, cible
                    # = un repertoire non vide :
                    #
                    #     rm: cannot remove '...': Is a directory
                    #     code de sortie 1, « Termine » jamais affiche
                    #
                    # Les consequences s'enchainaient : les entrees suivantes
                    # du recu n'etaient pas traitees, le retrait du repertoire
                    # d'etat n'etait JAMAIS atteint -- donc l'AC5 tombait et le
                    # recu survivait --, et l'utilisateur recevait un `rm:` nu
                    # SANS commande de secours. Un blocage sec au sens
                    # d'`EPIC11-ARB-89`, sur le chemin destructif, la ou tout
                    # le reste du bloc porte deja son `|| alerte`.
                    #
                    # Le regime reel est un repertoire non inscriptible
                    # (`~/.local/bin` possede par root), structurellement
                    # invisible au banc, qui tourne en uid 0.
                    alerte "Retrait impossible : ${chemin}"
                    info "  Le fichier est peut-etre protege, ouvert, ou dans un"
                    info "  repertoire dont vous n'etes pas proprietaire. A la main :"
                    info "    rm -f ${chemin}"
                    info "  ou, si le repertoire appartient a l'administrateur :"
                    info "    sudo rm -f ${chemin}"
                fi ;;
            pipx-paquet-systeme)
                info "pipx a ete pose par ce script (paquet systeme) : ${chemin}"
                avertir_du_cout_du_retrait_de_pipx
                retirer_pipx_du_systeme ;;
            pipx-pip-utilisateur)
                info "pipx a ete pose par ce script (pip --user) : ${chemin}"
                avertir_du_cout_du_retrait_de_pipx
                retirer_pipx_de_pip_utilisateur ;;
            python)
                # LA FRONTIERE DE L'AC6, ECRITE DANS LE PRODUIT. Une entree
                # `python` traverse le recu, l'existence et l'annonce -- et
                # ne devient jamais un retrait.
                alerte "Python n'est PAS retire, meme s'il figure au recu : ${chemin}"
                commande_de_secours "python" "retrait" ;;
            *)
                # Jamais un blocage sec ni un `rm` a l'aveugle sur une nature
                # qu'on ne connait pas : un recu ecrit par une version future
                # ne doit pas faire retirer n'importe quoi par une version
                # ancienne.
                alerte "Nature inconnue au recu, rien n'est retire : ${nature} (${chemin})" ;;
        esac
    done <<EOF_RECU
${RECU_RETENU}
EOF_RECU
    return 0
}

# AC5 -- LE RECU SE RETIRE LUI-MEME, par l'issue 1 comme par l'issue 2.
#
# Une story qui ajoute un fichier sur la machine de quelqu'un et l'oublie au
# retrait ajoute la fuite qu'elle pretend fermer. Seul le sous-repertoire
# `mmu` part -- jamais `${RACINE_ETAT}`, qui porte l'etat de tout le monde.
retirer_le_repertoire_d_etat() {
    case "${RECU_DOSSIER}" in
        /*/mmu) ;;
        *) alerte "Chemin d'etat inattendu, rien n'est retire : ${RECU_DOSSIER}"
           return 0 ;;
    esac
    if [ ! -d "${RECU_DOSSIER}" ]; then
        info "Aucun recu en ${RECU_DOSSIER} : rien a y retirer."
        return 0
    fi
    if [ "${SIMULATION}" -eq 1 ]; then
        printf '    [simulation] rm -rf %s\n' "${RECU_DOSSIER}"
    elif rm -rf "${RECU_DOSSIER}"; then
        succes "Recu retire : ${RECU_DOSSIER}"
    else
        # Meme garde que ci-dessus, meme motif (`C1-3`). Celle-ci est la
        # DERNIERE etape du bloc : sans elle, un echec ici emportait aussi le
        # `succes "Termine."` qui suit, et la desinstallation se terminait sur
        # un `rm:` nu apres avoir tout fait correctement.
        alerte "Le recu n'a pas pu etre retire : ${RECU_DOSSIER}"
        info "  A la main : rm -rf ${RECU_DOSSIER}"
    fi
    return 0
}

# Installe un paquet systeme via le gestionnaire detecte.
installer_paquet_systeme() {
    paquet_brew="$1"; paquet_apt="$2"; paquet_dnf="$3"
    paquet_pacman="$4"; paquet_zypper="$5"; paquet_apk="$6"

    # ----------------------------------------------------------------------
    #  Cette fonction REND UN CODE, elle n'arrete pas le script.
    # ----------------------------------------------------------------------
    # `EPIC11-ARB-270` (Egan, 2026-09-08, par invite) : ne pas pouvoir poser un
    # paquet systeme FACULTATIF ne doit pas emporter toute l'installation.
    #
    # Ce qu'elle faisait avant, et ce que ca coutait -- mesure le meme jour, sur
    # un PATH sans ffmpeg et sans gestionnaire de paquets : `Echec :` et un code
    # de sortie 1 a l'etape ffmpeg, APRES le recapitulatif, sans que `mmu` ait
    # ete pose. Sur un Mac sans Homebrew, c'etait le parcours nominal.
    #
    # Deux incoherences internes le disaient deja :
    #
    #   * douze lignes plus bas, l'appelant ffmpeg dit noir sur blanc
    #     « Pas d'echec sec : le reste de l'installation reste utile » -- donc
    #     un `brew install` qui ECHOUE laissait continuer, mais un Homebrew
    #     ABSENT tuait tout ;
    #   * l'appelant pipx porte un repli `if ! installer_paquet_systeme ... ;
    #     then ... pip --user`, qui etait INATTEIGNABLE : `echouer` sortait
    #     avant que le `if` puisse lire quoi que ce soit. Un repli ecrit pour
    #     ce cas precis, et que ce cas precis ne pouvait pas atteindre.
    #
    # L'appelant decide donc, et il n'y a qu'un seul appelant pour qui l'echec
    # est fatal : Python, qui n'est pas facultatif. Il le dit lui-meme.
    if [ -z "${GESTIONNAIRE}" ]; then
        if [ "${SYSTEME}" = "macos" ]; then
            alerte "Homebrew est absent, ${paquet_brew} ne peut pas etre pose ici."
            info   "Pour l'installer :"
            info   "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            info   "  (script officiel Homebrew ; il demande le mot de passe administrateur.)"
        else
            alerte "Aucun gestionnaire de paquets reconnu (apt-get, dnf, pacman, zypper, apk)."
            info   "Installer ${paquet_apt} manuellement."
        fi
        return 1
    fi

    if [ "${SUDO}" = "__PAS_DE_SUDO__" ]; then
        alerte "Droits administrateur indisponibles : ni root ni sudo."
        info   "Demander a un administrateur d'installer : ${paquet_apt}"
        return 1
    fi

    # ----------------------------------------------------------------------
    #  Homebrew compilerait : prevenir AVANT de lancer des heures de calcul,
    #  et POSER le binaire precompile plutot que de renvoyer au terminal.
    # ----------------------------------------------------------------------
    # Jamais un blocage sec, jamais un demarrage silencieux. Le 2026-09-08,
    # ce bloc AFFICHAIT la voie sans compilation et ne l'empruntait jamais :
    # `EPIC11-ARB-271` l'a renverse, parce qu'un outil pose a la main n'est
    # pas forcement sur le PATH -- donc pas forcement detecte, donc recompile
    # au tour suivant. Une compilation CONSCIENTE reste possible, c'est la
    # meme posture qu'`EPIC11-ARB-89`.
    if homebrew_compile_depuis_les_sources; then
        # Le MOTIF, pas seulement le fait. Les deux causes ne se reparent pas
        # de la meme facon, et un utilisateur a qui on dit « macOS trop
        # ancien » alors qu'il est en Sequoia cherchera au mauvais endroit.
        if mac_intel_sans_bouteilles; then
            alerte "Mac Intel : Homebrew ne publie plus de binaires precompiles."
            info   "Mesure sur formulae.brew.sh le 2026-09-08 : python@3.12, openssl@3"
            info   "et mpdecimal n'ont AUCUNE bouteille macOS Intel ; ffmpeg n'en a que"
            info   "pour Sonoma. Ce n'est pas un defaut de votre installation."
        else
            alerte "macOS ${MACOS_MAJEUR} : Homebrew ne fournit plus de binaires precompiles."
        fi
        info   "Poser ${paquet_brew} passerait donc par une COMPILATION depuis les"
        info   "sources -- de l'ordre de l'heure sur les gros paquets."
        info   ""

        # TROIS ISSUES quand un repli precompile existe, JAMAIS une seule et
        # jamais un blocage sec (`EPIC11-ARB-89`, `EPIC11-ARB-271`) :
        #
        #   1. compiler quand meme -- long, mais CONSCIENT, et c'est la voie
        #      Homebrew ; la rigueur de l'outil ne doit pas l'interdire ;
        #   2. laisser le script POSER le binaire precompile -- le DEFAUT, et
        #      c'est ce qui a change le 2026-09-08 : jusque-la, cette voie
        #      etait AFFICHEE et jamais empruntee, ce qui renvoyait au
        #      terminal un outil que la machine ne detecterait ensuite pas ;
        #   3. ne rien poser et recevoir la commande de secours.
        #
        # Le DEFAUT ne consomme ni des heures ni un mot de passe : l'issue 2
        # ne demande rien pour ffmpeg, et pour Python elle re-demande
        # explicitement avant tout `sudo` (voir `repli_precompile_python`).
        if un_repli_precompile_existe "${paquet_brew}"; then
            demander 2 "Comment poser ${paquet_brew} sans y passer des heures ?" \
                "compiler avec Homebrew maintenant (long, la voie Homebrew)" \
                "poser le binaire precompile officiel -- je m'en charge" \
                "ne rien poser : donne-moi la commande, je le ferai moi-meme"
            case "${REPONSE}" in
                1) : ;;   # on continue vers le `case` d'installation, plus bas
                2) if repli_precompile "${paquet_brew}"; then
                       return 0
                   fi
                   # Le repli a deja NOMME sa panne et donne la commande de
                   # secours : rien a ajouter ici, sinon un doublon.
                   return 1 ;;
                *) info "Tres bien, rien n'est pose."
                   commande_de_secours "$(dependance_du_paquet "${paquet_brew}")"
                   return 1 ;;
            esac
        else
            # `pipx` est le seul cas de cette branche, et il n'a besoin
            # d'AUCUN repli : refuser ici fait basculer l'installation sur
            # `pip --user`, qui ne compile rien. Lui inventer une URL serait
            # un engagement de maintenance pour rien.
            info "Rien a faire a la main : refuser ici fait basculer"
            info "l'installation sur \`pip --user\`, qui ne compile rien."
            demander 2 "Laisser Homebrew compiler ${paquet_brew} depuis les sources ?" \
                "oui - lancer la compilation maintenant (long)" \
                "non - je le pose a la main, continue sans"
            if [ "${REPONSE}" -ne 1 ]; then
                return 1
            fi
        fi
    fi

    case "${GESTIONNAIRE}" in
        brew)    executer brew install "${paquet_brew}" ;;
        apt-get) executer ${SUDO} apt-get update
                 executer ${SUDO} apt-get install -y "${paquet_apt}" ;;
        dnf)     executer ${SUDO} dnf install -y "${paquet_dnf}" ;;
        pacman)  executer ${SUDO} pacman -Sy --noconfirm "${paquet_pacman}" ;;
        zypper)  executer ${SUDO} zypper install -y "${paquet_zypper}" ;;
        apk)     executer ${SUDO} apk add "${paquet_apk}" ;;
    esac
}

# Quelle distribution de l'outil pipx porte-t-il deja, et en quelle version ?
# `pipx list --short` rend une ligne "<distribution> <version>" par application.
trouver_installation_existante() {
    command -v pipx >/dev/null 2>&1 || return 1
    pipx list --short 2>/dev/null \
        | grep -E "^(${DIST_CLI}|${DIST_TUI})(-test)? " \
        | head -n1
}

# ============================================================================
#  0. desinstallation -- un chemin a part, qui POSE UNE QUESTION A TROIS
#     ISSUES depuis `EPIC11-ARB-274` (2026-09-08). Ce bandeau disait
#     « qui ne pose aucune question » jusqu'a ce jour-la, et il l'a dit
#     encore quelques heures APRES que la story eut ferme exactement ce
#     defaut sur la ligne d'aide -- finding `T3-3` de la couche 3. Un
#     commentaire de haut de fichier n'est lu par personne au moment ou
#     il devient faux ; c'est pour ca qu'il faut le corriger avec le
#     code et non a la relecture.
# ============================================================================

if [ "${DESINSTALLER}" -eq 1 ]; then
    etape "Desinstallation"

    # LA QUESTION VIENT AVANT TOUT RETRAIT (`EPIC11-ARB-274`, AC1), et elle a
    # TROIS issues -- jamais deux, jamais une, jamais un blocage sec
    # (`EPIC11-ARB-89`).
    #
    # CE QUI A CHANGE, ET POURQUOI : avant cette story, `--desinstaller` ne
    # posait rien, et le commentaire disait « avoir tape `--desinstaller` EST
    # l'acte conscient ». C'etait vrai d'un desinstalleur qui ne retirait que
    # l'application. Ca ne l'est plus d'un qui peut reprendre 52 Mo de binaires
    # et pipx : « tout supprimer » et « juste mmu » ne sont pas le meme acte, et
    # taper un seul drapeau ne peut pas vouloir dire les deux.
    #
    # LE DEFAUT EST L'ISSUE 1, et `--non-interactif` le prend : une machine
    # muette ne retire jamais plus que l'application. C'est aussi ce que prend
    # un `curl | bash` sans terminal, ou une entree fermee.
    demander 1 "${INTITULE_DU_RETRAIT}" \
        "${ISSUE_APPLICATION_SEULE}" \
        "${ISSUE_TOUT_CE_QUE_LE_SCRIPT_A_POSE}" \
        "${ISSUE_MONTRER_LES_COMMANDES}"
    ISSUE_DE_RETRAIT="${REPONSE}"

    # ISSUE 3 : ELLE AFFICHE ET NE FAIT PAS (AC6). Elle sort AVANT le premier
    # retrait, et c'est ce qui la rend mesurable sur l'etat de la machine :
    # apres elle, rien n'a bouge -- ni les distributions, ni le profil, ni le
    # raccourci, ni le recu lui-meme.
    #
    # Les trois commandes sortent de `commande_de_secours`, la MEME table que
    # celle des echecs du repli (`EPIC11-ARB-271`) : un remede recopie diverge.
    if [ "${ISSUE_DE_RETRAIT}" -eq 3 ]; then
        info ""
        info "RIEN n'est retire. Voici les voies officielles de retrait, pour la"
        info "voie par laquelle chaque dependance est arrivee sur cette machine."
        commande_de_secours "ffmpeg" "retrait"
        commande_de_secours "pipx" "retrait"
        commande_de_secours "python" "retrait"
        info ""
        info "Pour retirer l'application elle-meme, relancer et choisir 1 ou 2."
        succes "Termine."
        exit 0
    fi

    # ISSUE 2 : elle a besoin du recu, et un recu absent DEGRADE (AC4).
    # Une installation anterieure a ce mecanisme, ou un recu efface, ne fait
    # pas echouer la desinstallation -- elle se rabat sur l'issue 1 EN LE
    # DISANT, et l'issue 3 reste entiere.
    RECU_LU=0
    if [ "${ISSUE_DE_RETRAIT}" -eq 2 ]; then
        info "Lecture du recu ${RECU_FICHIER} :"
        if lire_le_recu; then
            RECU_LU=1
        else
            alerte "Aucun recu en ${RECU_FICHIER} : ce script ne sait pas ce qu'il a pose ici."
            info "Je me rabats sur l'issue 1 : l'application seule."
            info "Pour retirer Python, ffmpeg ou pipx a la main, relancer et choisir 3."
            ISSUE_DE_RETRAIT=1
        fi
    fi

    # L'ANNONCE DIT CE QUI PART, AVANT QUE CA PARTE (AC7), et elle enumere les
    # CHEMINS REELS plutot qu'une categorie -- « ce que le script a pose » ne
    # dit rien a qui veut savoir si ses 52 Mo vont partir.
    # La boucle ci-dessous retire QUATRE distributions, pas deux : les reelles
    # et celles du bac a sable. L'annonce doit dire les quatre -- une monteuse
    # qui a installe `mmu-cli-test` et lit « vont etre retires : mmu-tui,
    # mmu-cli » conclut legitimement que le desinstalleur ne la concerne pas,
    # et garde une commande `mmu-test` qui traine.
    info "Vont etre retires, s'ils existent : ${DIST_TUI}, ${DIST_CLI},"
    info "  ainsi que leurs versions de bac a sable ${DIST_TUI}-test, ${DIST_CLI}-test."
    info "Ainsi que la ligne que pipx a ajoutee a ${PROFIL}."
    if [ "${SYSTEME}" = "linux" ]; then
        info "Et le raccourci du menu des applications : ${RACCOURCI_FICHIER}"
    fi
    # AC5 : le recu part lui aussi, par l'issue 1 comme par l'issue 2.
    info "Ainsi que le recu de ce que ce script a pose : ${RECU_DOSSIER}"

    if [ "${RECU_LU}" -eq 1 ]; then
        if [ -n "${RECU_RETENU}" ]; then
            info "Et, d'apres le recu, ce que CE SCRIPT a pose :"
            while IFS="$(printf '\t')" read -r nature_annoncee chemin_annonce; do
                [ -n "${nature_annoncee}" ] || continue
                case "${nature_annoncee}" in
                    python) info "  ${chemin_annonce} (${nature_annoncee}) -- NON retire, voir plus bas" ;;
                    *)      info "  ${chemin_annonce} (${nature_annoncee})" ;;
                esac
            done <<EOF_ANNONCE
${RECU_RETENU}
EOF_ANNONCE
        else
            info "Le recu ne designe plus aucun objet present : rien de plus a retirer."
        fi
    else
        info "Ni Python, ni ffmpeg, ni pipx ne sont touches."
    fi

    if command -v pipx >/dev/null 2>&1; then
        for distribution in "${DIST_TUI}" "${DIST_CLI}" "${DIST_TUI}-test" "${DIST_CLI}-test"; do
            # `|| true` : une distribution absente n'est pas une erreur. Un
            # desinstalleur qui echoue parce qu'il n'y avait rien a
            # desinstaller est un blocage sec pour rien.
            executer pipx uninstall "${distribution}" >/dev/null 2>&1 || true
        done
    else
        alerte "pipx est absent : aucun paquet a retirer."
    fi

    # La ligne du profil. On ne la retire que si elle porte la MARQUE de pipx,
    # et on garde une copie du fichier avant d'y toucher : editer le profil de
    # quelqu'un sans filet est exactement le genre de geste qu'on ne rattrape
    # pas. Meme famille qu'`EPIC11-ARB-89` -- jamais une seule issue.
    if [ -f "${PROFIL}" ] && grep -q 'Created by `pipx`' "${PROFIL}" 2>/dev/null; then
        info "Copie de sauvegarde : ${PROFIL}.mmu-sauvegarde"
        executer sed -i.mmu-sauvegarde \
                 -e '/^# Created by `pipx` on /d' \
                 -e '\#^export PATH="$PATH:.*\.local/bin"$#d' \
                 "${PROFIL}"
    else
        info "Aucune ligne pipx dans ${PROFIL} : rien a y retirer."
    fi

    # Le raccourci (story 8.8). Le retrait est INCONDITIONNEL sous Linux : il
    # ne consulte ni l'affichage ni les composants, parce qu'aucun des deux
    # n'est encore connu ici -- l'etat des lieux vient APRES ce bloc, et sous
    # `set -u` citer `AFFICHAGE` a cet endroit tuerait le script. Un fichier
    # qu'on a pu poser doit pouvoir etre retire quelle que soit la machine sur
    # laquelle on le retire (`EPIC11-ARB-89`).
    if [ "${SYSTEME}" = "linux" ]; then
        if [ -f "${RACCOURCI_FICHIER}" ] || [ -L "${RACCOURCI_FICHIER}" ]; then
            # `-L` autant que `-f` : un raccourci remplace par un lien casse
            # n'est pas un fichier, et resterait sinon en place a jamais.
            #
            # Le `succes` est sous le `else` de la simulation : un `succes`
            # affirme une action PASSEE, et en `--dry-run` elle n'a pas eu lieu
            # (`C2-6` / `C1-7` de la revue -- le jumeau PowerShell distinguait
            # deja correctement, bash affirmait « Raccourci retire » sur un
            # fichier toujours present).
            if [ "${SIMULATION}" -eq 1 ]; then
                printf '    [simulation] rm -f %s\n' "${RACCOURCI_FICHIER}"
            else
                rm -f "${RACCOURCI_FICHIER}"
                succes "Raccourci retire : ${RACCOURCI_FICHIER}"
            fi
        else
            info "Aucun raccourci en ${RACCOURCI_FICHIER} : rien a y retirer."
        fi
    fi

    # ISSUE 2 : ce que le recu enregistre, et RIEN d'autre. La politique par
    # nature vit dans `retirer_selon_le_recu` -- notamment le refus, jamais
    # negociable, de retirer Python (AC6).
    if [ "${ISSUE_DE_RETRAIT}" -eq 2 ] && [ "${RECU_LU}" -eq 1 ]; then
        retirer_selon_le_recu
    fi

    # AC5 -- et il vient APRES la lecture, jamais avant : retirer le recu
    # d'abord reviendrait a oublier ce qu'on s'apprete a reprendre.
    retirer_le_repertoire_d_etat

    succes "Termine."
    exit 0
fi

# ============================================================================
#  1. etat des lieux -- on regarde AVANT de demander
# ============================================================================

etape "Etat des lieux"

# ----------------------------------------------------------------------------
#  CE QUI EST POSE HORS DU `PATH` (`EPIC11-ARB-279`, story 8.14)
# ----------------------------------------------------------------------------
#
# LE DEFAUT QUE CE BLOC FERME, verbatim d'Egan : « si on choisi dans l'outil de
# faire la voie "manuelle" pour toutes les dependances, le souci est que
# l'outil n'est pas forcement ajoute au path et donc pas forcement detecte. »
# Constate en vrai le 2026-09-08 : pipx pose a la main, non detecte, RECOMPILE.
#
# `EPIC11-ARB-271` en avait ferme une moitie -- celle ou c'est le SCRIPT qui
# pose, et qui pose donc la ou pipx expose. Celle-ci est l'autre : quand c'est
# l'UTILISATEUR qui a pose.
#
# CE QUE CE BLOC NE FAIT PAS, et c'est ecrit plutot que tu (AC12) :
#   * il ne cherche RIEN hors de la liste bornee ci-dessous. Un outil pose
#     ailleurs reste invisible, et c'est assume ;
#   * il n'ecrit JAMAIS dans un profil de shell. Il met le repertoire sur le
#     `PATH` du PROCESSUS et DONNE la ligne. La seule ecriture de profil du
#     produit reste celle de `pipx ensurepath` ;
#   * il ne change pas ce que le script POSE, seulement ce qu'il CONCLUT avant
#     de poser ;
#   * il n'ecrit RIEN au recu (`noter_dans_le_recu`). Un binaire que
#     l'utilisateur a pose lui-meme n'appartient pas a ce script, et l'issue 2
#     de la desinstallation ne doit jamais le reprendre -- c'est la raison 2
#     d'`EPIC11-ARB-274`.

# LA LISTE BORNEE, ET ELLE VIT ICI, A UN SEUL ENDROIT (AC1). Aucun autre
# chemin d'emplacement n'est ecrit ailleurs dans ce script.
#
# JAMAIS UN `find`, JAMAIS UNE RECHERCHE RECURSIVE, et le dire est la moitie de
# l'arbitrage : un `find /` est un temps infini sur une machine pleine. Ce
# depot a deja paye cette famille de panne -- la boucle de sauvetage non bornee
# de `decode_qr_image_resilient` partait en temps infini quand les images
# etaient des pointeurs LFS. La liste EST la garde.
#
# Une liste bornee qui rate un cas vaut mieux qu'une recherche qui suspend
# l'installation.
emplacements_usuels() {
    case "${SYSTEME}" in
        macos)
            printf '%s\n' \
                "/opt/homebrew/bin" \
                "/usr/local/bin" \
                "${HOME}/.local/bin" \
                "/opt/local/bin"
            ;;
        *)
            printf '%s\n' \
                "/usr/local/bin" \
                "${HOME}/.local/bin" \
                "/snap/bin" \
                "/var/lib/flatpak/exports/bin"
            ;;
    esac
}

# LE PLANCHER DE VERSION DE PYTHON, ECRIT UNE SEULE FOIS. `trouver_python`
# l'appelait en litteral ; cette story avait besoin du MEME test, et en ecrire
# un second l'aurait fait diverger a la premiere retouche. C'est la meme
# discipline que `commande_de_secours` -- « un remede recopie a cinq endroits
# diverge ».
#
# ET IL EST DERIVE DE `PYTHON_MINIMUM`, PLUTOT QUE RECOPIE (finding `C1-1` /
# mutant `M12` de la couche 1, 2026-09-09). « Une seule fois » etait vrai de
# la COMPARAISON et faux du NOMBRE : le tuple `(3, 11)` etait ecrit ici, le
# libelle `3.11` vingt-cinq lignes plus haut, et rien ne les confrontait.
# Ramener le tuple a `(3, 10)` laissait 196 tests VERTS, sous une annonce
# « Python >= 3.11 » -- un Python 3.10 aurait ete retenu par `trouver_python`
# comme par le balayage. C'est la classe « constante centrale d'un calcul »,
# et le precedent du depot est le test tautologique de la 5.9.
#
# Derive plutot que mesure par un banc : ce qui se derive ne peut pas diverger,
# la ou ce qui se mesure peut voir sa mesure oubliee. Le jumeau PowerShell le
# faisait deja (`[version]$sortie -ge $PythonMinimum`).
python_assez_recent() {
    "$1" -c "import sys; sys.exit(0 if sys.version_info[:2] >= tuple(int(n) for n in '${PYTHON_MINIMUM}'.split('.')) else 1)" 2>/dev/null
}

# Le drapeau qui fait dire sa version a un binaire. `ffmpeg` et `ffprobe` n'ont
# qu'un tiret ; tout le reste en a deux.
drapeau_de_version() {
    case "$1" in
        ffmpeg|ffprobe) printf '%s\n' "-version" ;;
        *)              printf '%s\n' "--version" ;;
    esac
}

# UN BINAIRE TROUVE N'EST CRU QUE S'IL DEMARRE (AC2). C'est la lecon deja payee
# par l'AC3 de la story 8.11 : un fichier present ne prouve ni son
# architecture, ni sa version, ni qu'il n'est pas un lien casse.
#
# IL EST LANCE SOUS LE MEME PLAFOND QUE LE REPLI PRECOMPILE, et c'est la MEME
# fonction -- `lancer_avec_plafond`, qui tue par PID capture au lancement et
# jamais par motif (regle 6 de `CLAUDE.md`). Le regime qu'elle ferme n'est pas
# theorique : premier lancement d'un binaire non notarise, evaluation
# Gatekeeper qui part au reseau, pare-feu qui *drop* au lieu de refuser.
#
# LA VERSION SE LIT PAR UN SECOND APPEL, ET CE N'EST PAS UN OUBLI :
# `lancer_avec_plafond` jette la sortie de ce qu'elle lance (`>/dev/null 2>&1`),
# parce que ce qu'elle mesure est le fait de RENDRE LA MAIN, pas ce qui est
# ecrit. Lui faire porter une redirection demanderait de lancer une enveloppe
# `sh -c`, dont le PID ne serait plus celui du binaire -- et la tuer laisserait
# le binaire orphelin, c'est-a-dire exactement la panne que le plafond existe
# pour fermer. Le second appel n'est donc PAS sous plafond, et ce qui le borne
# est que le premier vient de rendre la main sous ce plafond. Un binaire qui
# repondrait une fois puis suspendrait est un regime qu'aucune mesure de ce
# depot ne porte -- dit plutot que tu.
VERSION_HORS_DU_PATH=""
demarre_et_dit_sa_version() {
    local candidat drapeau issue
    candidat="$1"; drapeau="$2"
    VERSION_HORS_DU_PATH=""
    # UN SEUL lancement, et il est plafonne (`C2-6`). Le second appel non
    # plafonne a disparu : la version se lit dans le journal du premier.
    JOURNAL_DU_LANCEMENT="$(mktemp 2>/dev/null)" || JOURNAL_DU_LANCEMENT=""
    issue=0
    lancer_avec_plafond "${PLAFOND_DE_LANCEMENT}" "${candidat}" "${drapeau}" || issue=$?
    if [ -n "${JOURNAL_DU_LANCEMENT}" ]; then
        if [ "${issue}" -eq 0 ]; then
            VERSION_HORS_DU_PATH="$(head -n1 "${JOURNAL_DU_LANCEMENT}" 2>/dev/null || true)"
        fi
        rm -f "${JOURNAL_DU_LANCEMENT}"
    fi
    JOURNAL_DU_LANCEMENT=""
    [ "${issue}" -eq 0 ] || return 1
    return 0
}

# Le plancher, quand il y en a un : `Python >= 3.11`, `ffmpeg >= 5.0`.
# `ffprobe` et `pipx` n'en ont pas -- demarrer leur suffit.
#
# UNE VERSION ILLISIBLE EST ACCEPTEE, volontairement. Les compilations de
# developpement de ffmpeg s'annoncent `ffmpeg version N-109000-g...`, sans
# majeur numerique. Refuser ce qu'on ne sait pas mesurer reintroduirait
# exactement le faux negatif que cette story ferme ; la version lue est de
# toute facon affichee, donc l'utilisateur voit ce qui a ete retenu.
FFMPEG_MAJEUR_MINIMUM=5
# LE PLANCHER DE VERSION DE FFMPEG, ECRIT UNE SEULE FOIS ET PRENANT SA VERSION
# EN ARGUMENT (finding `C2-5` de la couche 2, 2026-09-09). Il lisait le global
# `VERSION_HORS_DU_PATH`, donc il ne pouvait servir QU'au balayage hors du
# PATH -- et c'est ce qui rendait l'asymetrie invisible : un ffmpeg 4 POSE
# hors du PATH etait refuse comme trop ancien, le meme ffmpeg 4 SUR le PATH
# etait accepte sans qu'aucune version soit seulement lue.
#
# C'est-a-dire que le defaut que cette story existe pour fermer etait rouvert
# dans l'autre sens, et qu'un utilisateur dont le ffmpeg systeme est trop
# ancien recevait un « ffmpeg : ok » avant d'echouer plus loin, au premier
# encodage. Le plancher se prend en argument : ce qui depend d'un global ne
# peut pas etre reemploye.
#
# Une version ILLISIBLE est acceptee, comme cote hors du PATH -- on ne refuse
# pas un outil sur une lecture ratee. C'est un choix, et il est le meme des
# deux cotes, ce qui est le point.
ffmpeg_assez_recent() {
    local majeur
    majeur="${1#*version }"
    majeur="${majeur%%.*}"
    majeur="${majeur#n}"
    case "${majeur}" in
        ''|*[!0-9]*) return 0 ;;
        *) [ "${majeur}" -ge "${FFMPEG_MAJEUR_MINIMUM}" ] ;;
    esac
}

plancher_tenu() {
    local nom candidat
    nom="$1"; candidat="$2"
    case "${nom}" in
        python*)
            python_assez_recent "${candidat}"
            ;;
        ffmpeg)
            ffmpeg_assez_recent "${VERSION_HORS_DU_PATH}"
            ;;
        *) return 0 ;;
    esac
}

# LE BALAYAGE. Rend :
#   0  -- trouve, executable, DEMARRE, et son plancher est tenu ;
#   1  -- rien dans la liste ;
#   2  -- trouve et demarre, mais TROP ANCIEN (AC3). Le chemin et la version
#         sortent alors dans `TROP_ANCIEN_HORS_DU_PATH`, parce qu'un refus muet
#         serait la panne que cette story existe pour fermer, retournee.
#
# LE RESULTAT PASSE PAR DES VARIABLES ET NON PAR STDOUT, comme `demander` avec
# `REPONSE` et `lire_le_recu` avec `RECU_RETENU` : `info` et `alerte` ecrivent
# eux aussi sur stdout, et une fonction capturee par `$(...)` avalerait ses
# propres annonces.
#
# LE BALAYAGE NE S'ARRETE PAS AU PREMIER TROP ANCIEN : un emplacement suivant
# peut porter une version convenable. Il ne s'arrete qu'a la premiere
# TROUVAILLE VALIDE -- et c'est ce que la regle des fabriques mesure, cible en
# tete comme en queue.
TROUVE_HORS_DU_PATH=""
REPERTOIRE_HORS_DU_PATH=""
TROP_ANCIEN_HORS_DU_PATH=""
chercher_hors_du_path() {
    local nom repertoire candidat drapeau
    nom="$1"
    TROUVE_HORS_DU_PATH=""
    REPERTOIRE_HORS_DU_PATH=""
    TROP_ANCIEN_HORS_DU_PATH=""
    VERSION_HORS_DU_PATH=""
    [ "${CHERCHER_HORS_DU_PATH}" -eq 1 ] || return 1
    drapeau="$(drapeau_de_version "${nom}")"

    while IFS= read -r repertoire; do
        [ -n "${repertoire}" ] || continue
        # UN EMPLACEMENT NON ABSOLU EST ECARTE. Meme garde que l'atelier du
        # repli et que le recu : un chemin relatif se resout contre le
        # repertoire courant, donc son sens change a chaque `cd`. Un `HOME`
        # relatif suffirait a rendre cette liste-la relative.
        case "${repertoire}" in
            /*) ;;
            *)  continue ;;
        esac
        candidat="${repertoire}/${nom}"
        # `-f` et non `-e` : un lien symbolique CASSE echoue `-f`, et c'est
        # exactement ce qu'on veut ecarter.
        [ -f "${candidat}" ] || continue
        [ -x "${candidat}" ] || continue
        demarre_et_dit_sa_version "${candidat}" "${drapeau}" || continue
        if plancher_tenu "${nom}" "${candidat}"; then
            TROUVE_HORS_DU_PATH="${candidat}"
            REPERTOIRE_HORS_DU_PATH="${repertoire}"
            return 0
        fi
        if [ -z "${TROP_ANCIEN_HORS_DU_PATH}" ]; then
            TROP_ANCIEN_HORS_DU_PATH="${candidat} (${VERSION_HORS_DU_PATH})"
        fi
    done <<FIN_DES_EMPLACEMENTS
$(emplacements_usuels)
FIN_DES_EMPLACEMENTS

    [ -z "${TROP_ANCIEN_HORS_DU_PATH}" ] || return 2
    return 1
}

# LA LIGNE DE PROFIL EST DONNEE, JAMAIS ECRITE (AC5). C'est une frontiere
# NEGATIVE du banc : aucun chemin de ce bloc n'ouvre un fichier de profil en
# ecriture. Le motif n'est pas la prudence -- c'est qu'un script qui ecrit dans
# le profil de quelqu'un sans le lui demander est precisement ce que la
# question du PATH existe pour ne pas faire.
donner_la_ligne_de_profil() {
    local repertoire
    info ""
    info "La ligne a ajouter dans ${PROFIL} pour que ta machine cesse de l'ignorer :"
    for repertoire in "$@"; do
        info "  export PATH=\"${repertoire}:\$PATH\""
    done
    info "Ce script ne l'ecrit pas lui-meme."
}

# LES TROIS ISSUES (`EPIC11-ARB-89`), jamais une seule et jamais un blocage sec.
# Rend 0 quand l'utilisateur a choisi d'EXPOSER, 1 quand il a choisi d'ignorer.
# L'issue 3 ne rend pas : elle donne la ligne et sort, comme l'issue 3 du
# desinstalleur affiche et ne fait pas.
offrir_les_trois_issues() {
    local repertoire
    demander 1 "${INTITULE_HORS_DU_PATH}" \
        "${ISSUE_EXPOSER_POUR_CETTE_INSTALLATION}" \
        "${ISSUE_IGNORER_ET_POSER_QUAND_MEME}" \
        "${ISSUE_LIGNE_SEULE_ET_SORTIR}"
    case "${REPONSE}" in
        1)
            # LE `PATH` DU PROCESSUS, ET RIEN D'AUTRE. Il retombe a la mort du
            # script ; c'est la ligne donnee juste apres qui le rend durable,
            # et c'est l'utilisateur qui l'ecrit.
            for repertoire in "$@"; do
                export PATH="${repertoire}:${PATH}"
            done
            donner_la_ligne_de_profil "$@"
            return 0
            ;;
        2)
            info "Tres bien : cette copie est ignoree, l'installation posera la sienne."
            return 1
            ;;
        *)
            donner_la_ligne_de_profil "$@"
            etape "Termine"
            info "Rien n'a ete change. Ajoute la ligne ci-dessus, ouvre un nouveau"
            info "terminal, puis relance cette commande."
            exit 0
            ;;
    esac
}

# AC3 -- un binaire TROUVE mais TROP ANCIEN est traite comme absent, EN LE
# DISANT : il est nomme, sa version est donnee, et le script explique qu'il
# posera quand meme. Le remede REEMPLOIE `commande_de_secours` plutot que de
# recopier une commande (`EPIC11-ARB-271`).
dire_le_trop_ancien() {
    local dependance trouvaille
    dependance="$1"; trouvaille="$2"
    alerte "${trouvaille} est pose hors du PATH, mais trop ancien pour cet outil."
    info "Il est donc traite comme absent, et ${dependance} sera pose quand meme."
    commande_de_secours "${dependance}"
}

# LES NOMS D'INTERPRETEUR, ecrits UNE fois : `trouver_python` les parcourt sur
# le `PATH`, et la recherche hors du `PATH` les parcourt dans la liste bornee.
# Deux listes divergeraient au premier Python 3.14.
NOMS_DE_PYTHON="python3.13 python3.12 python3.11 python3"

trouver_python() {
    for binaire in ${NOMS_DE_PYTHON}; do
        chemin="$(command -v "${binaire}" 2>/dev/null)" || continue
        # Le plancher vit dans `python_assez_recent`, et nulle part ailleurs.
        if python_assez_recent "${chemin}"; then
            printf '%s' "${chemin}"
            return 0
        fi
    done
    return 1
}

# La MEME recherche, mais dans la liste bornee au lieu du `PATH` (AC1/AC2).
# Elle rend 0 et pose `TROUVE_HORS_DU_PATH` ; 2 quand elle n'a vu que du trop
# ancien ; 1 quand elle n'a rien vu.
chercher_python_hors_du_path() {
    local binaire issue premier_trop_ancien
    premier_trop_ancien=""
    for binaire in ${NOMS_DE_PYTHON}; do
        issue=0
        chercher_hors_du_path "${binaire}" || issue=$?
        [ "${issue}" -eq 0 ] && return 0
        if [ "${issue}" -eq 2 ] && [ -z "${premier_trop_ancien}" ]; then
            premier_trop_ancien="${TROP_ANCIEN_HORS_DU_PATH}"
        fi
    done
    TROUVE_HORS_DU_PATH=""
    REPERTOIRE_HORS_DU_PATH=""
    TROP_ANCIEN_HORS_DU_PATH="${premier_trop_ancien}"
    [ -z "${TROP_ANCIEN_HORS_DU_PATH}" ] || return 2
    return 1
}

PYTHON=""
PYTHON_PRESENT=0
if PYTHON="$(trouver_python)"; then
    PYTHON_PRESENT=1
    succes "Python : $(${PYTHON} --version 2>&1) -> ${PYTHON}"
else
    PYTHON=""
    # `command -v` a echoue -- et il ne regarde QUE le `PATH`. On consulte la
    # liste bornee AVANT de conclure « absent » (`EPIC11-ARB-279`).
    ISSUE_DE_LA_RECHERCHE=0
    chercher_python_hors_du_path || ISSUE_DE_LA_RECHERCHE=$?
    if [ "${ISSUE_DE_LA_RECHERCHE}" -eq 0 ]; then
        PYTHON_HORS_DU_PATH="${TROUVE_HORS_DU_PATH}"
        REPERTOIRE_DU_PYTHON="${REPERTOIRE_HORS_DU_PATH}"
        VERSION_DU_PYTHON="${VERSION_HORS_DU_PATH}"
        alerte "Python est POSE hors du PATH : ${PYTHON_HORS_DU_PATH}"
        info   "  ${VERSION_DU_PYTHON}"
        info   "Ton shell ne l'expose pas ; sans cela il serait reinstalle par-dessus."
        if offrir_les_trois_issues "${REPERTOIRE_DU_PYTHON}"; then
            PYTHON="${PYTHON_HORS_DU_PATH}"
            PYTHON_PRESENT=1
            succes "Python : ${VERSION_DU_PYTHON} -> ${PYTHON}"
        fi
    elif [ "${ISSUE_DE_LA_RECHERCHE}" -eq 2 ]; then
        dire_le_trop_ancien "python" "${TROP_ANCIEN_HORS_DU_PATH}"
    fi
    if [ "${PYTHON_PRESENT}" -eq 0 ]; then
        info "Python >= ${PYTHON_MINIMUM} : absent, il sera installe."
    fi
fi

# ffprobe est verifie separement : certains paquets minimalistes ne fournissent
# que ffmpeg, et le projet lit les metadonnees video avec ffprobe
# (video_metadata.py). Un ffmpeg seul echouerait plus tard, a l'usage.
#
# LA RECHERCHE HORS DU `PATH` LES CHERCHE AUSSI SEPAREMENT (AC7), et le
# desaccord se DIT. Trouver l'un sans l'autre est un regime reel -- c'est
# exactement pourquoi ce script les a toujours testes tous les deux -- et il ne
# doit pas passer pour une detection reussie.
FFMPEG_PRESENT=0
FFMPEG_SUR_LE_PATH=0
FFPROBE_SUR_LE_PATH=0
if command -v ffmpeg  >/dev/null 2>&1; then FFMPEG_SUR_LE_PATH=1; fi
if command -v ffprobe >/dev/null 2>&1; then FFPROBE_SUR_LE_PATH=1; fi

# LE MEME PLANCHER DES DEUX COTES (`C2-5`). Un ffmpeg trouve sur le PATH est
# traite comme absent s'il est trop ancien, EN LE DISANT -- exactement le
# contrat que l'AC3 pose pour la liste bornee. Sans cette symetrie, la story
# rendait l'outil PLUS severe avec ce qu'elle trouve elle-meme qu'avec ce que
# le systeme lui presente.
VERSION_FFMPEG_DU_PATH=""
if [ "${FFMPEG_SUR_LE_PATH}" -eq 1 ]; then
    VERSION_FFMPEG_DU_PATH="$(ffmpeg -version 2>/dev/null | head -n1)"
    if ! ffmpeg_assez_recent "${VERSION_FFMPEG_DU_PATH}"; then
        FFMPEG_SUR_LE_PATH=0
        dire_le_trop_ancien "ffmpeg" \
            "$(command -v ffmpeg 2>/dev/null) (${VERSION_FFMPEG_DU_PATH})"
    fi
fi

if [ "${FFMPEG_SUR_LE_PATH}" -eq 1 ] && [ "${FFPROBE_SUR_LE_PATH}" -eq 1 ]; then
    FFMPEG_PRESENT=1
    succes "ffmpeg : ${VERSION_FFMPEG_DU_PATH}"
else
    REPERTOIRE_DU_FFMPEG=""
    REPERTOIRE_DU_FFPROBE=""
    VERSION_DU_FFMPEG=""
    FFMPEG_TROP_ANCIEN=""
    if [ "${FFMPEG_SUR_LE_PATH}" -eq 0 ]; then
        ISSUE_DE_LA_RECHERCHE=0
        chercher_hors_du_path "ffmpeg" || ISSUE_DE_LA_RECHERCHE=$?
        if [ "${ISSUE_DE_LA_RECHERCHE}" -eq 0 ]; then
            REPERTOIRE_DU_FFMPEG="${REPERTOIRE_HORS_DU_PATH}"
            VERSION_DU_FFMPEG="${VERSION_HORS_DU_PATH}"
        elif [ "${ISSUE_DE_LA_RECHERCHE}" -eq 2 ]; then
            FFMPEG_TROP_ANCIEN="${TROP_ANCIEN_HORS_DU_PATH}"
            # AC3 -- LA CAUSE SE DIT AVANT SA CONSEQUENCE. Annoncee plus bas,
            # elle arrivait DERRIERE le desaccord de l'AC7, qui disait alors
            # « ffmpeg reste introuvable » d'un ffmpeg parfaitement trouve et
            # refuse sur sa version. Mesure a l'ecriture du banc.
            dire_le_trop_ancien "ffmpeg" "${FFMPEG_TROP_ANCIEN}"
        fi
    fi
    if [ "${FFPROBE_SUR_LE_PATH}" -eq 0 ]; then
        if chercher_hors_du_path "ffprobe"; then
            REPERTOIRE_DU_FFPROBE="${REPERTOIRE_HORS_DU_PATH}"
        fi
    fi

    # Les deux sont-ils disponibles une fois les repertoires exposes ?
    FFMPEG_DISPONIBLE=0
    FFPROBE_DISPONIBLE=0
    if [ "${FFMPEG_SUR_LE_PATH}"  -eq 1 ] || [ -n "${REPERTOIRE_DU_FFMPEG}"  ]; then FFMPEG_DISPONIBLE=1;  fi
    if [ "${FFPROBE_SUR_LE_PATH}" -eq 1 ] || [ -n "${REPERTOIRE_DU_FFPROBE}" ]; then FFPROBE_DISPONIBLE=1; fi

    if [ -n "${REPERTOIRE_DU_FFMPEG}${REPERTOIRE_DU_FFPROBE}" ] \
       && [ "${FFMPEG_DISPONIBLE}" -eq 1 ] && [ "${FFPROBE_DISPONIBLE}" -eq 1 ]; then
        alerte "ffmpeg / ffprobe sont POSES hors du PATH."
        [ -z "${REPERTOIRE_DU_FFMPEG}" ]  || info "  ${REPERTOIRE_DU_FFMPEG}/ffmpeg   ${VERSION_DU_FFMPEG}"
        [ -z "${REPERTOIRE_DU_FFPROBE}" ] || info "  ${REPERTOIRE_DU_FFPROBE}/ffprobe"
        if [ -n "${REPERTOIRE_DU_FFPROBE}" ] && [ "${REPERTOIRE_DU_FFPROBE}" != "${REPERTOIRE_DU_FFMPEG}" ] \
           && [ -n "${REPERTOIRE_DU_FFMPEG}" ]; then
            EXPOSE=0
            offrir_les_trois_issues "${REPERTOIRE_DU_FFMPEG}" "${REPERTOIRE_DU_FFPROBE}" || EXPOSE=1
        else
            EXPOSE=0
            offrir_les_trois_issues "${REPERTOIRE_DU_FFMPEG:-${REPERTOIRE_DU_FFPROBE}}" || EXPOSE=1
        fi
        if [ "${EXPOSE}" -eq 0 ]; then
            FFMPEG_PRESENT=1
            succes "ffmpeg : ${VERSION_DU_FFMPEG:-$(ffmpeg -version 2>/dev/null | head -n1)}"
        fi
    elif [ -n "${REPERTOIRE_DU_FFMPEG}${REPERTOIRE_DU_FFPROBE}" ]; then
        # AC7 -- LE DESACCORD SE DIT, et ne passe PAS pour une detection
        # reussie. Certains paquets minimalistes ne livrent que le premier.
        if [ -n "${REPERTOIRE_DU_FFMPEG}" ]; then
            alerte "ffmpeg est pose hors du PATH (${REPERTOIRE_DU_FFMPEG}/ffmpeg), mais ffprobe reste introuvable."
        elif [ -n "${FFMPEG_TROP_ANCIEN}" ]; then
            alerte "ffprobe est pose hors du PATH (${REPERTOIRE_DU_FFPROBE}/ffprobe), mais aucun ffmpeg retenu ne l'accompagne."
        else
            alerte "ffprobe est pose hors du PATH (${REPERTOIRE_DU_FFPROBE}/ffprobe), mais ffmpeg reste introuvable."
        fi
        info "L'outil a besoin des DEUX : ce n'est donc pas une detection reussie."
    fi
    if [ "${FFMPEG_PRESENT}" -eq 0 ]; then
        info "ffmpeg / ffprobe : absent."
    fi
fi

PIPX_PRESENT=0
if command -v pipx >/dev/null 2>&1; then
    PIPX_PRESENT=1
    succes "pipx : present"
else
    # LE CAS D'EGAN, MOT POUR MOT : pipx pose a la main, hors du PATH, non
    # detecte, et RECOMPILE. C'est le seul point de terrain dont ce depot
    # dispose, et il date du 2026-09-08.
    if chercher_hors_du_path "pipx"; then
        PIPX_HORS_DU_PATH="${TROUVE_HORS_DU_PATH}"
        REPERTOIRE_DU_PIPX="${REPERTOIRE_HORS_DU_PATH}"
        alerte "pipx est POSE hors du PATH : ${PIPX_HORS_DU_PATH}"
        info   "  ${VERSION_HORS_DU_PATH}"
        info   "Ton shell ne l'expose pas ; sans cela il serait reinstalle par-dessus."
        if offrir_les_trois_issues "${REPERTOIRE_DU_PIPX}"; then
            PIPX_PRESENT=1
            succes "pipx : present (${PIPX_HORS_DU_PATH})"
        fi
    fi
    if [ "${PIPX_PRESENT}" -eq 0 ]; then
        info "pipx : absent, il sera installe."
    fi
fi

if affichage_disponible; then
    AFFICHAGE=1
    succes "affichage graphique : detecte -- apercu video en fenetre disponible"
else
    AFFICHAGE=0
    info "affichage graphique : aucun -- roue OpenCV sans fenetres (${ROUE_CV_SANS_FENETRES})"
fi

# Une installation deja posee ? On la NOMME plutot que de la recouvrir en
# silence (arbitrage d'Egan : la relance est une mise a jour, pas une
# reinstallation).
INSTALLATION_EXISTANTE=""
VERSION_EXISTANTE=""
if ligne_existante="$(trouver_installation_existante)" && [ -n "${ligne_existante}" ]; then
    INSTALLATION_EXISTANTE="${ligne_existante%% *}"
    VERSION_EXISTANTE="${ligne_existante##* }"
    succes "deja installe : ${INSTALLATION_EXISTANTE} ${VERSION_EXISTANTE}"
fi

# ============================================================================
#  2. les questions
# ============================================================================

# --- reprise : posee SEULEMENT si quelque chose est deja installe ------------
if [ -n "${INSTALLATION_EXISTANTE}" ] && [ -z "${CHOIX_REPRISE}" ]; then
    demander 1 "${INSTALLATION_EXISTANTE} ${VERSION_EXISTANTE} est deja installe." \
        "le mettre a jour (rapide : seul ce qui a change est retelecharge)" \
        "tout reinstaller de zero" \
        "ne rien changer et sortir"
    CHOIX_REPRISE="${REPONSE}"
fi

if [ "${CHOIX_REPRISE:-0}" -eq 3 ]; then
    etape "Termine"
    info "Rien n'a ete change. ${INSTALLATION_EXISTANTE} ${VERSION_EXISTANTE} reste en place."
    exit 0
fi

MISE_A_JOUR=0
if [ -n "${INSTALLATION_EXISTANTE}" ] && [ "${CHOIX_REPRISE:-0}" -eq 1 ]; then
    MISE_A_JOUR=1
    # Les composants sont deja tranches par ce qui est installe : on ne repose
    # pas une question dont la reponse est sur le disque. Un drapeau EXPLICITE
    # reste plus fort que le disque -- sinon `--cli` sur une machine qui porte
    # la TUI serait ignore en silence, ce qui est le contraire de ce qu'un
    # drapeau donne veut dire.
    if [ -z "${CHOIX_COMPOSANTS}" ]; then
        case "${INSTALLATION_EXISTANTE}" in
            "${DIST_CLI}"|"${DIST_CLI}-test") CHOIX_COMPOSANTS=1 ;;
            *)                                CHOIX_COMPOSANTS=2 ;;
        esac
    fi
fi

# --- question 1 : que veux-tu installer ? ------------------------------------
# Deux options depuis le 2026-09-07. L'interface graphique n'est plus proposee
# (« Interface graphique : plus tard ») ; le drapeau `--gui` la pose encore.
if [ -z "${CHOIX_COMPOSANTS}" ]; then
    demander 2 "Que veux-tu installer ?" \
        "${COMMANDE_CLI} seul -- la ligne de commande" \
        "${COMMANDE_CLI} + l'interface terminal (${COMMANDE_TUI})"
    CHOIX_COMPOSANTS="${REPONSE}"
fi

# --- question 2 : ffmpeg (seulement s'il manque) -----------------------------
# Elle demande le mot de passe administrateur : on ne la pose donc que lorsque
# la reponse peut changer quelque chose.
if [ "${FFMPEG_PRESENT}" -eq 0 ] && [ -z "${CHOIX_FFMPEG}" ]; then
    # Le second libelle DIT SA CONSEQUENCE plutot que de decrire une intention.
    # Egan, 2026-09-07, sur la note de release : « Mettre juste "non -
    # necessite d'installer manuellement ffmpeg" ». « Je m'en occupe » se lit
    # comme un choix de confort ; il faut qu'on sache qu'on part avec un outil
    # incomplet tant que ce geste n'est pas fait. Meme exigence que pour la
    # question du PATH, qui nomme deja les commandes et le fichier touches.
    demander 1 "ffmpeg est absent. C'est la seule dependance systeme de l'outil, et l'installer demande le mot de passe administrateur." \
        "l'installer maintenant" \
        "non - necessite d'installer manuellement ffmpeg"
    CHOIX_FFMPEG="${REPONSE}"
fi
[ -z "${CHOIX_FFMPEG}" ] && CHOIX_FFMPEG=1

# --- question 3 : ajouter les commandes au PATH ? ----------------------------
# On nomme le fichier ET les commandes : Egan a demande que l'on annonce qu'il
# y en a potentiellement DEUX.
if [ "${CHOIX_COMPOSANTS}" -eq 1 ]; then
    COMMANDES_POSEES="${COMMANDE_CLI}"
else
    COMMANDES_POSEES="${COMMANDE_CLI} et ${COMMANDE_TUI}"
fi
if [ -z "${CHOIX_PATH}" ]; then
    demander 1 "Ajouter les commandes au PATH ? (${COMMANDES_POSEES} ; cela ecrit une ligne dans ${PROFIL})" \
        "oui" \
        "non, ne touche pas a mon profil"
    CHOIX_PATH="${REPONSE}"
fi

# --- question 4 : un raccourci hors du terminal ? ----------------------------
# Story 8.8, `EPIC8-ARB-19`. Egan, 2026-09-07, verbatim : « Essaye ... on verra
# bien si ca marche ».
#
# Elle ne se pose QUE la ou sa reponse change quelque chose -- meme discipline
# que la question ffmpeg, posee seulement s'il manque :
#   * il faut que l'interface terminal s'installe : un raccourci vers une
#     ligne de commande n'a pas de sens ;
#   * il faut un affichage : sur un serveur nu, ce serait proposer une entree
#     dans un menu d'applications qui n'existe pas ;
#   * et il faut Linux : macOS n'a aucun format de raccourci pour une
#     application terminal -- il y faudrait une application enveloppe, qui est
#     un autre livrable. On ne pose pas une question dont la reponse ne
#     changerait rien.
#
# Sa PLACE est fixee : PATH et raccourci repondent tous deux a « ou l'outil
# s'expose-t-il ? ». Elle ne peut de toute facon pas preceder la question 1,
# dont elle lit la reponse.
RACCOURCI_POSSIBLE=0
if [ "${SYSTEME}" = "linux" ] && [ "${AFFICHAGE}" -eq 1 ] \
   && [ "${CHOIX_COMPOSANTS}" -ne 1 ]; then
    RACCOURCI_POSSIBLE=1
fi
if [ "${RACCOURCI_POSSIBLE}" -eq 1 ] && [ -z "${CHOIX_RACCOURCI}" ]; then
    demander 1 "Ajouter un raccourci pour lancer ${COMMANDE_TUI} hors du terminal ? (un fichier dans ${RACCOURCI_DOSSIER})" \
        "oui" \
        "non"
    CHOIX_RACCOURCI="${REPONSE}"
fi
[ -z "${CHOIX_RACCOURCI}" ] && CHOIX_RACCOURCI=1

# --- question 5 : verifier l'installation ? ----------------------------------
# On dit CE QUI SERA VERIFIE, pas seulement qu'il y aura une verification.
if [ "${CHOIX_COMPOSANTS}" -eq 1 ]; then
    LIBELLE_VERIFICATION="${COMMANDE_CLI} --version, puis ffmpeg -version"
else
    LIBELLE_VERIFICATION="${COMMANDE_CLI} --version, ${COMMANDE_TUI} sur le PATH, puis ffmpeg -version"
fi
if [ -z "${CHOIX_VERIFICATION}" ]; then
    demander 1 "Verifier l'installation a la fin ? (${LIBELLE_VERIFICATION})" \
        "oui" \
        "non"
    CHOIX_VERIFICATION="${REPONSE}"
fi

# ============================================================================
#  3. le plan, puis son recapitulatif
# ============================================================================

# APPLICATION est le paquet PRINCIPAL du venv pipx : c'est lui qui donne son
# nom au venv et c'est dans lui qu'on greffe le reste.
if [ "${CHOIX_COMPOSANTS}" -eq 1 ]; then
    APPLICATION="${PAQUET_CLI}"
    LIBELLE_COMPOSANTS="${COMMANDE_CLI} seul"
else
    APPLICATION="${PAQUET_TUI}"
    LIBELLE_COMPOSANTS="${COMMANDE_CLI} + ${COMMANDE_TUI}"
fi

EXTRA=""
if [ "${AVEC_GUI}" -eq 1 ]; then
    EXTRA="[gui]"
    LIBELLE_COMPOSANTS="${LIBELLE_COMPOSANTS} + extra graphique"
fi

EPINGLE=""
[ "${CHOIX_VERSION}" -eq 2 ] && [ -n "${VERSION}" ] && EPINGLE="==${VERSION}"

case "${CHOIX_VERSION}" in
    1) LIBELLE_VERSION="la derniere stable publiee" ;;
    2) LIBELLE_VERSION="${VERSION}" ;;
    3) LIBELLE_VERSION="TestPyPI (pre-publication)" ;;
esac

etape "Recapitulatif"
if [ "${MISE_A_JOUR}" -eq 1 ]; then
    info "operation ....... mise a jour de ${INSTALLATION_EXISTANTE} ${VERSION_EXISTANTE}"
else
    info "operation ....... installation"
fi
info "composants ...... ${LIBELLE_COMPOSANTS}"
if [ "${CHOIX_COMPOSANTS}" -eq 1 ]; then
    info "paquets ......... ${PAQUET_CLI}${EXTRA}"
else
    info "paquets ......... ${PAQUET_TUI}, avec ${PAQUET_CLI}${EXTRA} greffe dedans"
fi
if [ "${AFFICHAGE}" -eq 1 ]; then
    info "apercu video .... oui, un affichage est detecte (${ROUE_CV_AVEC_FENETRES})"
else
    info "apercu video .... non, aucun affichage detecte (${ROUE_CV_SANS_FENETRES})"
fi
info "version ......... ${LIBELLE_VERSION}"
if [ "${FFMPEG_PRESENT}" -eq 1 ]; then
    info "ffmpeg .......... deja present"
elif [ "${CHOIX_FFMPEG}" -eq 1 ]; then
    info "ffmpeg .......... a installer"
else
    info "ffmpeg .......... laisse a ta charge"
fi
if [ "${CHOIX_PATH}" -eq 1 ]; then
    info "PATH ............ oui, pour ${COMMANDES_POSEES} (${PROFIL})"
else
    info "PATH ............ non, le profil n'est pas touche"
fi
# La ligne du raccourci est TOUJOURS imprimee, dans ses cinq sens -- comme
# `apercu video ....` l'est dans ses deux. Une ligne qui disparait est une
# information qu'on ne peut pas distinguer d'un oubli. Ces cinq libelles sont
# repris MOT POUR MOT dans install.ps1.
if [ "${CHOIX_COMPOSANTS}" -eq 1 ]; then
    info "raccourci ....... sans objet (ligne de commande seule)"
elif [ "${SYSTEME}" != "linux" ]; then
    # macOS a bien un affichage : dire « aucun affichage detecte » y serait
    # faux. Le motif est autre, et il se nomme.
    info "raccourci ....... sans objet (pas de raccourci terminal sur macOS)"
elif [ "${RACCOURCI_POSSIBLE}" -eq 0 ]; then
    info "raccourci ....... sans objet (aucun affichage detecte)"
elif [ "${CHOIX_RACCOURCI}" -eq 1 ]; then
    info "raccourci ....... oui, dans ${RACCOURCI_FICHIER}"
else
    info "raccourci ....... non"
fi
if [ "${CHOIX_VERIFICATION}" -eq 1 ]; then
    info "verification .... ${LIBELLE_VERIFICATION}"
else
    info "verification .... non"
fi

# ============================================================================
#  4. execution
# ============================================================================

# --- Python ------------------------------------------------------------------

if [ "${PYTHON_PRESENT}" -eq 0 ]; then
    etape "Python (>= ${PYTHON_MINIMUM})"
    # Python n'est PAS facultatif : c'est le seul appelant pour qui ne pas
    # pouvoir poser le paquet est fatal, et il le dit lui-meme depuis
    # `EPIC11-ARB-270` -- la fonction, elle, se contente de rendre un code.
    if ! installer_paquet_systeme "python@3.12" "python3 python3-venv" "python3" \
                                  "python" "python3" "python3"; then
        echouer "Python >= ${PYTHON_MINIMUM} est indispensable et n'a pas pu etre pose.
   Installer Python depuis https://www.python.org/downloads/ puis relancer."
    fi
    if [ "${SIMULATION}" -eq 1 ]; then
        PYTHON="python3"
    elif PYTHON="$(trouver_python)"; then
        succes "$(${PYTHON} --version 2>&1) -> ${PYTHON}"
    else
        echouer "Python >= ${PYTHON_MINIMUM} toujours introuvable apres installation.
   Installer Python manuellement depuis https://www.python.org/downloads/ puis relancer."
    fi
fi

# --- pipx ---------------------------------------------------------------------

if [ "${PIPX_PRESENT}" -eq 0 ]; then
    etape "pipx (environnement isole pour l'application)"
    # On privilegie le paquet systeme : il est deja compile pour le Python de
    # la machine et echappe a la PEP 668.
    #
    # LA VOIE EMPRUNTEE SE RETIENT, parce que c'est elle qui decidera du
    # retrait (AC2). Retirer un pipx pose par apt en effacant son binaire
    # laisserait apt avec un paquet fantome -- c'est la raison 2
    # d'`EPIC11-ARB-274`, et elle vaut pour nous comme pour Homebrew.
    ROUTE_DE_PIPX="paquet-systeme"
    if ! installer_paquet_systeme "pipx" "pipx" "pipx" "python-pipx" "python3-pipx" "pipx" 2>/dev/null; then
        info "Paquet pipx indisponible, repli par pip --user"
        executer "${PYTHON}" -m pip install --user pipx
        ROUTE_DE_PIPX="pip-utilisateur"
    fi
    if [ "${SIMULATION}" -eq 0 ] && ! command -v pipx >/dev/null 2>&1; then
        # pipx installe par pip atterrit dans ~/.local/bin, pas forcement dans
        # le PATH du shell courant : on l'y ajoute pour la suite du script.
        export PATH="${HOME}/.local/bin:${PATH}"
        command -v pipx >/dev/null 2>&1 || echouer "pipx introuvable apres installation."
    fi
    succes "pipx installe"

    # LE RECU, TROISIEME NATURE. Il n'est ecrit que dans CETTE branche : quand
    # pipx etait deja la, ce script ne l'a pas pose et n'a donc rien a
    # reprendre. C'est la difference exacte que l'issue 2 doit voir.
    if [ "${SIMULATION}" -eq 1 ]; then
        printf '    [simulation] noter pipx-%s dans %s\n' "${ROUTE_DE_PIPX}" "${RECU_FICHIER}"
    else
        CHEMIN_DE_PIPX="$(command -v pipx 2>/dev/null || true)"
        if [ -n "${CHEMIN_DE_PIPX}" ]; then
            noter_dans_le_recu "pipx-${ROUTE_DE_PIPX}" "${CHEMIN_DE_PIPX}"
        fi
    fi
fi

# --- ffmpeg -------------------------------------------------------------------
#
# CETTE ETAPE VIENT APRES PIPX, ET C'EST UNE CORRECTION, PAS UN GOUT (finding
# `C1-3` de la revue du 2026-09-08). Le repli precompile depose ffmpeg et
# ffprobe dans « le repertoire binaire que pipx expose », qu'il DEMANDE a pipx
# (`pipx environment --value PIPX_BIN_DIR`) plutot que de le deviner -- c'est
# l'AC2 de la story 8.11. Tant que cette etape precedait celle de pipx,
# `command -v pipx` echouait a coup sur sur un Mac vierge, la question n'etait
# jamais posee a pipx, et la destination etait DEVINEE a chaque fois. Mesure :
# zero binaire dans `PIPX_BIN_DIR`, deux dans le `~/.local/bin` devine.
#
# Autrement dit, l'AC ecrite pour fermer le defaut d'Egan -- « un outil pose
# mais pas detecte » -- le reconduisait par l'ORDRE des etapes. Une garde ne
# vaut rien la ou elle ne peut pas s'executer.
#
# Ce que l'inversion ne coute pas, verifie : ffmpeg ne conditionne rien dans
# l'etape pipx (aucune des deux ne lit l'autre), et l'etape pipx ne consomme
# que Python, pose plus haut.

if [ "${FFMPEG_PRESENT}" -eq 0 ]; then
    etape "ffmpeg et ffprobe"
    if [ "${CHOIX_FFMPEG}" -eq 1 ]; then
        # `|| true` : l'absence de gestionnaire rend 1, et ce n'est PAS une
        # raison d'arreter -- ffmpeg est facultatif, tout ce qui ne touche pas
        # a la video marche sans lui. Le bilan final redira quoi installer.
        installer_paquet_systeme "ffmpeg" "ffmpeg" "ffmpeg" "ffmpeg" "ffmpeg" "ffmpeg" \
            || alerte "ffmpeg n'a pas pu etre pose. L'installation continue."
        if [ "${SIMULATION}" -eq 0 ]; then
            if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
                FFMPEG_PRESENT=1
                succes "$(ffmpeg -version 2>/dev/null | head -n1)"
            else
                # Pas d'echec sec : le reste de l'installation reste utile, et
                # le bilan final redira quoi installer.
                alerte "ffmpeg ou ffprobe reste introuvable. L'installation continue."
                alerte "Sur Fedora/RHEL, ffmpeg complet vient du depot RPM Fusion."
            fi
        fi
    else
        # Choix 2 ("non - necessite d'installer manuellement ffmpeg") : on sort
        # de l'ETAPE ffmpeg sans drame -- on dit quoi installer, et on continue.
        # Interrompre ici priverait l'utilisateur de l'installation qu'il est
        # venu chercher, alors que ffmpeg peut s'ajouter apres coup sans rien
        # refaire.
        info "Tres bien. A installer quand tu voudras, avant le premier encodage :"
        case "${GESTIONNAIRE}" in
            brew)    info "  brew install ffmpeg" ;;
            apt-get) info "  sudo apt-get install ffmpeg" ;;
            dnf)     info "  sudo dnf install ffmpeg   (depot RPM Fusion sur Fedora/RHEL)" ;;
            pacman)  info "  sudo pacman -S ffmpeg" ;;
            zypper)  info "  sudo zypper install ffmpeg" ;;
            apk)     info "  sudo apk add ffmpeg" ;;
            *)       info "  https://ffmpeg.org/download.html" ;;
        esac
        info "Il faut ffmpeg ET ffprobe : certains paquets minimalistes n'ont que le premier."
    fi
fi

# --- les paquets --------------------------------------------------------------

if [ "${MISE_A_JOUR}" -eq 1 ]; then
    etape "Mise a jour"
else
    etape "Installation"
fi

# TestPyPI n'heberge pas les dependances (textual, numpy, Pillow...) : sans
# index supplementaire vers le vrai PyPI, la resolution echoue.
ARGUMENTS_PIP=""
if [ "${CHOIX_VERSION}" -eq 3 ]; then
    ARGUMENTS_PIP="--pip-args=--index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple"
fi

if [ "${MISE_A_JOUR}" -eq 1 ]; then
    # `--include-injected` : sans lui, pipx met a jour l'application et laisse
    # les paquets greffes -- dont `mmu-cli` -- a leur ancienne version, ce qui
    # est exactement la divergence que `mmu-tui` epingle pour l'eviter.
    if [ -n "${ARGUMENTS_PIP}" ]; then
        executer pipx upgrade "${ARGUMENTS_PIP}" --include-injected "${APPLICATION}"
    else
        executer pipx upgrade --include-injected "${APPLICATION}"
    fi
elif [ "${CHOIX_COMPOSANTS}" -eq 1 ]; then
    # La ligne de commande seule : `mmu-cli` est le paquet principal, donc pipx
    # expose `mmu` de lui-meme. Aucune greffe n'est necessaire.
    if [ -n "${ARGUMENTS_PIP}" ]; then
        executer pipx install "${ARGUMENTS_PIP}" --force "${PAQUET_CLI}${EXTRA}${EPINGLE}"
    else
        executer pipx install --force "${PAQUET_CLI}${EXTRA}${EPINGLE}"
    fi
else
    if [ -n "${ARGUMENTS_PIP}" ]; then
        executer pipx install "${ARGUMENTS_PIP}" --force "${PAQUET_TUI}${EPINGLE}"
    else
        executer pipx install --force "${PAQUET_TUI}${EPINGLE}"
    fi
fi

# LE PIEGE PIPX, mesure le 2026-09-07. `pipx install mmu-tui` installe bien
# `mmu-cli` dans le venv -- le binaire venvs/mmu-tui/bin/mmu existe -- mais
# pipx N'EXPOSE QUE LES SCRIPTS DU PAQUET PRINCIPAL : `mmu` n'arrive pas sur
# le PATH, et `pipx expose` n'y change rien. Le seul geste qui marche :
#   - `--include-apps` : c'est lui qui enregistre `mmu` sur le PATH ;
#   - `--force`        : sans lui, pipx repond "already seems to be installed"
#                        (mmu-cli EST deja la, en dependance) et ne
#                        reenregistre pas les applications.
# Retirer l'un des deux rend la commande `mmu` introuvable apres une
# installation reussie. C'est mesure par le banc, dans les deux sens. La greffe
# vaut aussi apres une MISE A JOUR : `pipx upgrade` ne reenregistre rien.
if [ "${CHOIX_COMPOSANTS}" -ne 1 ]; then
    if [ -n "${ARGUMENTS_PIP}" ]; then
        executer pipx inject "${ARGUMENTS_PIP}" --include-apps --force \
                 "${APPLICATION}" "${PAQUET_CLI}${EXTRA}${EPINGLE}"
    else
        executer pipx inject --include-apps --force \
                 "${APPLICATION}" "${PAQUET_CLI}${EXTRA}${EPINGLE}"
    fi
fi

# --- la roue OpenCV, selon l'affichage detecte --------------------------------
# On REMPLACE, on n'empile pas : les deux roues livrent le meme module `cv2` et
# pip ne connait pas leur conflit. Installer la seconde par-dessus la premiere
# laisserait deux distributions se disputer les memes fichiers, et le prochain
# `pip install --upgrade` de l'une ecraserait l'autre sans un mot.
if [ "${AFFICHAGE}" -eq 1 ]; then
    executer pipx runpip "${APPLICATION}" uninstall -y "${ROUE_CV_SANS_FENETRES}"
    executer pipx inject --force "${APPLICATION}" "${ROUE_CV_AVEC_FENETRES}"
    info "Pour revenir a la roue sans fenetres :"
    info "  pipx inject --force ${APPLICATION} ${ROUE_CV_SANS_FENETRES}"
else
    info "Aucun affichage : ${ROUE_CV_SANS_FENETRES} est conservee (elle n'exige"
    info "aucune bibliotheque graphique, ce qui est ce qu'il faut sur un serveur)."
fi

# --- le raccourci du menu des applications (story 8.8) ------------------------
# Ecrit APRES l'installation : le chemin absolu de la commande n'existe pas
# avant. Il n'y a pas de helper a reutiliser -- `executer` execute `"$@"` et ne
# peut donc porter ni redirection ni heredoc --, la garde `--dry-run` est donc
# posee ici, du meme gabarit que celle d'`ensurepath` juste en dessous.
if [ "${RACCOURCI_POSSIBLE}" -eq 1 ] && [ "${CHOIX_RACCOURCI}" -eq 1 ]; then
    # Le chemin ABSOLU, et il faut qu'il le soit : la ligne que
    # `pipx ensurepath` ecrit dans le profil n'est lue que par un SHELL. Une
    # session graphique lancee par le gestionnaire de connexion ne la voit pas,
    # si bien qu'un `Exec=mmu-tui` nu resoudrait sur une machine et pas sur une
    # autre. Repli sur le repertoire d'exposition de pipx, qui est ou la
    # commande vient d'etre posee meme si le PATH de CE terminal l'ignore
    # encore.
    #
    # `command -v` N'EST PAS un test de validite : mesure de la revue
    # (couche 2, `C2-5`, refaite en root ET sous uid 1000) -- il rend un
    # fichier present sur le PATH meme SANS bit d'execution. Le repli testait
    # `-x`, la branche nominale ne testait rien, si bien que le seul chemin non
    # garde etait celui qui sert le plus souvent. On revalide donc ce que
    # `command -v` rend, au lieu de lui faire confiance.
    CIBLE_TUI="$(command -v "${COMMANDE_TUI}" 2>/dev/null || true)"
    if [ -n "${CIBLE_TUI}" ] && [ ! -x "${CIBLE_TUI}" ]; then
        CIBLE_TUI=""
    fi
    if [ -z "${CIBLE_TUI}" ] && [ -x "${HOME}/.local/bin/${COMMANDE_TUI}" ]; then
        CIBLE_TUI="${HOME}/.local/bin/${COMMANDE_TUI}"
    fi

    if [ -z "${CIBLE_TUI}" ] && [ "${SIMULATION}" -eq 0 ]; then
        # Une issue NOMMEE plutot qu'un fichier mort : un raccourci qui pointe
        # vers rien est pire que pas de raccourci du tout -- il echoue chez
        # l'utilisateur, longtemps apres, sans rien dire de pourquoi.
        alerte "Raccourci non pose : ${COMMANDE_TUI} est introuvable sur cette machine."
    elif [ "${SIMULATION}" -eq 1 ]; then
        printf '    [simulation] ecrire %s\n' "${RACCOURCI_FICHIER}"
    else
        # `Terminal=true` : sans elle, le gestionnaire de bureau lance la
        # commande SANS terminal, et une application Textual n'a nulle part ou
        # s'afficher. C'est cette cle qui fait de ce raccourci un raccourci
        # « hors terminal » du point de vue de l'utilisateur -- precisement
        # parce qu'elle en ouvre un pour lui.
        #
        # `Icon=` porte un nom du theme d'icones, pas un fichier : le depot ne
        # livre aucune icone applicative, et en citer une du theme est ce qui
        # marche sans en livrer une.
        #
        # UNE SEULE categorie principale. Mesure du 2026-09-07 avec
        # desktop-file-utils 0.27 : `AudioVideo;`, `Graphics;` et `Utility;`
        # rendent chacun une sortie VIDE, tandis qu'une liste de trois rend un
        # « hint » sur la duplication dans le menu.
        #
        # TROIS gardes que la revue a payees, et aucune n'est cosmetique :
        #
        # 1. JAMAIS UN ECHEC SEC. `mkdir` et la redirection etaient nus sous
        #    `set -euo pipefail` : un `~/.local/share` inutilisable (fichier
        #    ordinaire, montage en lecture seule, quota, repertoire root apres
        #    un `sudo bash install.sh`) TUAIT le script -- apres que les
        #    paquets sont poses, donc sans `pipx ensurepath`, sans bilan et
        #    sans un mot (`C1-1` / `C2-2`). Le jumeau PowerShell faisait deja
        #    ce qu'il faut, en `try/catch` ; c'est bash qui n'avait pas la
        #    garde ;
        # 2. LE LIEN N'EST PAS SUIVI. `> fichier` ecrit dans la CIBLE d'un lien
        #    symbolique. Mesure de la revue (`C2-3`) : un utilisateur dont le
        #    raccourci est un lien vers ses dotfiles voyait le fichier vise
        #    ecrase, puis `--desinstaller` retirait le lien en laissant
        #    derriere lui son fichier detruit et orphelin. On retire donc le
        #    lien AVANT d'ecrire ;
        # 3. `Exec` EST CITE. Un chemin a espace produisait une ligne que
        #    `desktop-file-validate` accepte (exit 0, sortie vide) et
        #    qu'aucun bureau ne lance -- seul `gio launch` le voyait
        #    (`C1-6` / `C2-7`). La forme citee passe le validateur AUSSI :
        #    elle est donc toujours prise, pas seulement quand un espace
        #    apparait, pour qu'un seul chemin de code soit mesure.
        if ! mkdir -p "${RACCOURCI_DOSSIER}" 2>/dev/null; then
            alerte "Raccourci non pose : ${RACCOURCI_DOSSIER} n'a pas pu etre cree. L'installation continue."
        else
            if [ -e "${RACCOURCI_FICHIER}" ] || [ -L "${RACCOURCI_FICHIER}" ]; then
                RACCOURCI_ETAT="remplace"
            else
                RACCOURCI_ETAT="pose"
            fi
            rm -f "${RACCOURCI_FICHIER}" 2>/dev/null || true
            if printf '%s\n' \
                "[Desktop Entry]" \
                "Type=Application" \
                "Version=1.1" \
                "Name=mixed_media_utility" \
                "GenericName=Interface terminal" \
                "Comment=Interface terminal de mixed_media_utility" \
                "Exec=\"${CIBLE_TUI}\"" \
                "Icon=utilities-terminal" \
                "Terminal=true" \
                "Categories=AudioVideo;" \
                "StartupNotify=false" \
                > "${RACCOURCI_FICHIER}" 2>/dev/null
            then
                # « remplace » se DIT. `EPIC11-ARB-89` veut une ecriture
                # destructive CONSCIENTE, « apres avertissement » : un message
                # identique a celui d'une premiere pose laissait disparaitre en
                # silence un `.desktop` que l'utilisateur avait edite a la main
                # (`C2-3` / `C3-5`).
                if [ "${RACCOURCI_ETAT}" = "remplace" ]; then
                    succes "Raccourci REMPLACE (un fichier existait deja) : ${RACCOURCI_FICHIER}"
                else
                    succes "Raccourci pose : ${RACCOURCI_FICHIER}"
                fi
            else
                alerte "Raccourci non pose : ${RACCOURCI_FICHIER} n'a pas pu etre ecrit. L'installation continue."
            fi
        fi
    fi
fi

if [ "${CHOIX_PATH}" -eq 1 ]; then
    # `ensurepath` est idempotent et n'ecrit qu'une fois la ligne dans le profil.
    # En simulation on laisse la ligne s'afficher : un plan qui tait une de ses
    # etapes n'est plus un plan. Hors simulation on etouffe sa sortie, qui est
    # bavarde et sans interet, et son code de retour, qui n'a rien de fatal.
    if [ "${SIMULATION}" -eq 1 ]; then
        executer pipx ensurepath
    else
        executer pipx ensurepath >/dev/null 2>&1 || true
    fi
else
    info "PATH non modifie, comme demande."
fi

# ============================================================================
#  5. bilan
# ============================================================================

etape "Termine"

if [ "${SIMULATION}" -eq 1 ]; then
    info "Mode simulation : rien n'a ete installe."
    exit 0
fi

if [ "${CHOIX_VERIFICATION}" -eq 1 ]; then
    if command -v "${COMMANDE_CLI}" >/dev/null 2>&1; then
        succes "${COMMANDE_CLI} --version : $(${COMMANDE_CLI} --version 2>&1 | head -n1)"
    else
        alerte "${COMMANDE_CLI} ne repond pas encore dans CE terminal."
    fi
    if [ "${CHOIX_COMPOSANTS}" -ne 1 ]; then
        if command -v "${COMMANDE_TUI}" >/dev/null 2>&1; then
            succes "${COMMANDE_TUI} est sur le PATH"
        else
            alerte "${COMMANDE_TUI} n'est pas encore sur le PATH de CE terminal."
        fi
    fi
    if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
        succes "$(ffmpeg -version 2>/dev/null | head -n1)"
    else
        alerte "ffmpeg ou ffprobe manque : l'encodage echouera tant qu'il n'est pas la."
    fi
fi

printf '\n    Lancer la ligne de commande : %s%s --help%s\n' "${GRAS}" "${COMMANDE_CLI}" "${FIN}"
if [ "${CHOIX_COMPOSANTS}" -ne 1 ]; then
    printf '    Lancer l%sinterface terminal : %s%s%s\n' "'" "${GRAS}" "${COMMANDE_TUI}" "${FIN}"
fi
printf '\n    Si une commande reste introuvable, ouvrir un NOUVEAU terminal.\n\n'
