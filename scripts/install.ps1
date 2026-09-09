<#
.SYNOPSIS
    Installation en une commande de mixed_media_utility (Windows).

.DESCRIPTION
    Pendant Windows de scripts/install.sh, et meme dialogue : le script POSE
    DES QUESTIONS au clavier, en options numerotees validees par Entree seule.
    Aucune syntaxe a connaitre. Les parametres restent disponibles pour qui les
    connait, et un parametre donne SUPPRIME la question correspondante.

    CINQ QUESTIONS depuis la story 8.8, qui a ajoute le raccourci du menu
    Demarrer (`EPIC8-ARB-19`). Elles etaient QUATRE et pas six apres les
    arbitrages d'Egan du 2026-09-07 sur la note de release de la story 8.6 --
    ce qui a ete RETIRE du menu a cette occasion :

      * l'interface graphique -- verbatim : « Interface graphique : plus tard ».
        La question 1 n'a plus que deux options. L'extra [gui] reste
        installable A LA MAIN, par -Gui ou par
        `pipx inject --force <application> "mmu-cli[gui]"` ;
      * l'apercu video en fenetre -- verbatim : « Inclus par defaut. Retrait
        manuel ». La question disparait, l'affichage est DETECTE a la place ;
      * le choix de version -- verbatim : « C'est quoi la version d'essai ? ».
        -Version et -TestPyPI restent des parametres, pour nous.

    ---------------------------------------------------------------------------
    CE QUI A ETE MESURE, ET POURQUOI CE FICHIER N'EST PAS UNE TRANSPOSITION
    ---------------------------------------------------------------------------
    Mesures jouees le 2026-09-07 sous **PowerShell 7.5.9** (une mesure de
    comportement nomme la version sous laquelle elle a ete prise). Quatre
    sondes, meme script de quatre lignes a chaque fois :

      1. `Get-Content sonde.ps1 -Raw | Invoke-Expression`, soit la plomberie
         exacte de `irm ... | iex`, avec une reponse sur stdin :

             AVANT le read
             question: REPONSE_DEPUIS_STDIN
             reponse lue = [REPONSE_DEPUIS_STDIN]
             cette ligne est du SCRIPT, pas une reponse

         Aucune ligne perdue. `iex` recoit le texte par le pipeline d'OBJETS,
         stdin reste libre, `Read-Host` y lit l'utilisateur. C'est la
         difference de fond avec `curl | bash`, ou stdin EST le script ;

      2. `pwsh -Command -` avec le script sur STDIN, soit l'analogue exact de
         `curl | bash` :

             AVANT le read
             question: cette ligne est du SCRIPT, pas une reponse

         La ligne `reponse lue = [...]` a DISPARU : PowerShell mange lui aussi
         la ligne suivante du script quand le script arrive par stdin. Le piege
         existe donc bien ici, il n'est simplement pas sur le chemin nominal ;

      3. sans console (stdin sur /dev/null) : `Read-Host` rend la chaine VIDE
         et le code de sortie **0**. Silencieux, exactement comme le
         `read < /dev/tty` de bash. Un test explicite est donc obligatoire,
         jamais le code de sortie ;

      4. stdin FERME : `Read-Host` BLOQUE indefiniment -- il a fallu un SIGKILL
         (code 137) pour en sortir. C'est le blocage sec qu'on refuse.

    Le discriminant, mesure dans les trois regimes :

        pipe    -> [Console]::IsInputRedirected = True
        devnull -> [Console]::IsInputRedirected = True
        console -> [Console]::IsInputRedirected = False

    C'est lui, et rien d'autre, qui decide si l'on pose les questions.

    DEUX FORMES POUR LA COMMANDE D'UNE LIGNE, mesurees elles aussi :

        irm <url> | iex                                     -> tous les defauts
        & ([scriptblock]::Create((irm <url>))) -Gui -Version 1.2.3

    Un bloc `param()` traverse `iex` sans erreur, mais `iex` n'a aucun moyen de
    lui passer des arguments : il applique les defauts. La seconde forme, elle,
    passe bien -Gui et -Version (mesure : `Gui=True Version=[1.2.3]`).
    ---------------------------------------------------------------------------

    POURQUOI pipx ET NON `pip install --user` : pipx cree un venv dedie par
    application et expose la commande sur le PATH. Sur Windows le motif est
    moins la PEP 668 que l'isolation.

    winget EST INSTALLE S'IL MANQUE, via le module PowerShell officiel
    Microsoft.WinGet.Client (Repair-WinGetPackageManager), et seulement quand
    il y a reellement quelque chose a installer avec.

    CE SCRIPT NE CONNAIT PAS SA PROPRE URL, volontairement.

.PARAMETER Cli
    La ligne de commande seule (commande `mmu`).

.PARAMETER Tui
    `mmu` + l'interface terminal. C'est le defaut.

.PARAMETER Gui
    Ajoute l'extra graphique [gui] (Qt : ~270 Mo de plus). Hors menu,
    sur arbitrage d'Egan.
    Le paquet pese 91 Mo telecharges et 297 Mo sur disque, mesure du
    2026-09-06 sur l'environnement pipx que ce script cree (un venv
    ordinaire en rend ~28 de plus : `pip` et `setuptools`). La roue OpenCV
    est la variante -headless : les autres exigent des bibliotheques systeme
    graphiques qu'une machine vierge n'a pas. Seule la fenetre de lecture
    previz est perdue, et la TUI le dit.

.PARAMETER TestPyPI
    Installe depuis TestPyPI (distributions suffixees -test). Hors menu.

.PARAMETER Version
    Version precise a installer (ex. 0.2.0). Hors menu.

.PARAMETER MettreAJour
    Sur une installation existante : la mettre a jour sans rien redemander.

    Elle met a jour la distribution pipx ET le mmu greffe dedans -- c'est ce
    que `--include-injected` garantit, sans quoi la greffe resterait a son
    ancienne version. Elle ne met a jour ni Python, ni ffmpeg, ni pipx : ce
    sont des dependances du systeme, et elles se mettent a jour par le systeme
    (`EPIC11-ARB-277`).

    La voie manuelle equivalente :  pipx upgrade mmu-tui --include-injected

.PARAMETER Reinstaller
    Sur une installation existante : tout refaire de zero.

.PARAMETER NonInteractif
    Prend tous les defauts et ne pose aucune question.

.PARAMETER Raccourci
    Pose le raccourci du menu Demarrer sans poser la question.

.PARAMETER SansRaccourci
    Ne pose aucun raccourci, sans poser la question.

.PARAMETER Desinstaller
    Retire l'application -- et il DEMANDE jusqu'ou aller (`EPIC11-ARB-274`).

    Trois issues, jamais deux, jamais un blocage sec. Le defaut est la
    premiere, et -NonInteractif prend ce defaut : une machine muette ne retire
    jamais plus que l'application.

      1) l'application seule -- les quatre distributions, l'entree que pipx a
         ajoutee au PATH utilisateur, le raccourci du menu Demarrer. Ni
         Python, ni ffmpeg, ni pipx ;
      2) l'application ET ce que CE SCRIPT a pose -- l'issue 1, plus pipx si
         c'est ce script qui l'a pose. Il ne retire QUE ce qu'un recu
         enregistre, et seulement si le chemin existe encore ;
      3) rien n'est retire : les voies officielles de retrait de Python, de
         ffmpeg et de pipx sont AFFICHEES.

.PARAMETER IgnorerHorsDuPath
    Ne consulte AUCUN emplacement usuel : ce qui n'est pas sur le PATH est
    tenu pour absent. Pre-repond l'issue 2 de `EPIC11-ARB-279`.

.PARAMETER DryRun
    Affiche le plan sans rien executer.

.EXAMPLE
    irm https://raw.githubusercontent.com/<owner>/<depot>/main/scripts/install.ps1 | iex

.EXAMPLE
    & ([scriptblock]::Create((irm https://.../install.ps1))) -Cli
#>

[CmdletBinding()]
param(
    [switch] $Cli,
    [switch] $Tui,
    [switch] $Gui,
    [switch] $Ffmpeg,
    [switch] $SansFfmpeg,
    [string] $Version = "",
    [switch] $TestPyPI,
    [switch] $AjouterAuPath,
    [switch] $SansPath,
    [switch] $Raccourci,
    [switch] $SansRaccourci,
    [switch] $Verifier,
    [switch] $SansVerification,
    [switch] $MettreAJour,
    [switch] $Reinstaller,
    [switch] $NonInteractif,
    [switch] $IgnorerHorsDuPath,
    [switch] $Desinstaller,
    [switch] $DryRun
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------ parametres

$PythonMinimum = [version]"3.11"

# Les deux distributions (story 8.5). Le nom de DISTRIBUTION n'est pas le nom
# de la COMMANDE : `mmu` est pris sur PyPI, la distribution s'appelle donc
# `mmu-cli` et sa commande console reste `mmu`.
$DistCli     = "mmu-cli"
$DistTui     = "mmu-tui"
$CommandeCli = "mmu"
$CommandeTui = "mmu-tui"

# Les deux roues OpenCV. Elles livrent le MEME module `cv2` et ne se
# connaissent pas l'une l'autre : pip ne verra jamais leur conflit, c'est a
# nous de ne pas les empiler.
$RoueCvSansFenetres = "opencv-python-headless"
$RoueCvAvecFenetres = "opencv-python"

# Reponses aux questions. 0 = pas encore repondu, donc la question se pose.
$ChoixReprise      = 0   # 1 = mettre a jour, 2 = tout reinstaller, 3 = sortir
$ChoixComposants   = 0   # 1 = cli seule, 2 = cli + interface terminal
$ChoixFfmpeg       = 0   # 1 = l'installer, 2 = je m'en occupe
$ChoixPath         = 0   # 1 = oui, 2 = non
$ChoixRaccourci    = 0   # 1 = oui, 2 = non   (story 8.8)
$ChoixVerification = 0   # 1 = oui, 2 = non

$AvecGui      = [bool] $Gui
$ChoixVersion = 1        # 1 = derniere stable, 2 = version precise, 3 = TestPyPI

# LES TROIS ISSUES DE LA DESINSTALLATION (`EPIC11-ARB-274`), en constantes.
# Elles sont les MEMES que celles d'`install.sh`, MOT POUR MOT : une frontiere
# du banc les compare, exactement comme elle le fait deja des cinq libelles du
# raccourci. Un libelle recopie dans une invite diverge de son jumeau sans que
# personne le voie.
$IntituleDuRetrait           = "Que faut-il retirer ?"
$IssueApplicationSeule       = "l'application seule -- ni Python, ni ffmpeg, ni pipx"
$IssueToutCeQueLeScriptAPose = "l'application ET ce que CE SCRIPT a pose (ffmpeg, ffprobe, pipx)"
$IssueMontrerLesCommandes    = "rien pour l'instant -- montre-moi les commandes pour le reste"

# LES TROIS ISSUES DE CE QUI EST POSE HORS DU `PATH` (`EPIC11-ARB-279`, story
# 8.14). Meme discipline et meme frontiere : `install.sh` les porte MOT POUR
# MOT. Le defaut est l'issue 1 -- celle qui ne pose rien, ne compile rien et ne
# demande aucun mot de passe --, et `-NonInteractif` prend ce defaut.
$IntituleHorsDuPath                   = "Que faut-il en faire ?"
$IssueExposerPourCetteInstallation    = "l'utiliser pour cette installation, et me donner la ligne a ajouter a mon profil"
$IssueIgnorerEtPoserQuandMeme         = "l'ignorer et installer quand meme une autre copie"
$IssueLigneSeuleEtSortir              = "rien pour l'instant -- montre-moi la ligne de PATH et sors"

# Le drapeau qui eteint la recherche, jumeau de `--ignorer-hors-du-path`.
$ChercherHorsDuPath = (-not $IgnorerHorsDuPath)

if ($Cli)               { $ChoixComposants = 1 }
if ($Tui -or $Gui)      { $ChoixComposants = 2 }
if ($Ffmpeg)            { $ChoixFfmpeg = 1 }
if ($SansFfmpeg)        { $ChoixFfmpeg = 2 }
if ($TestPyPI)          { $ChoixVersion = 3 }
if ($Version)           { $ChoixVersion = 2 }
if ($AjouterAuPath)     { $ChoixPath = 1 }
if ($SansPath)          { $ChoixPath = 2 }
if ($Raccourci)         { $ChoixRaccourci = 1 }
if ($SansRaccourci)     { $ChoixRaccourci = 2 }
if ($Verifier)          { $ChoixVerification = 1 }
if ($SansVerification)  { $ChoixVerification = 2 }

# ---------------------------------------------------------------------------
#  Le suffixe du BAC A SABLE, et il porte sur QUATRE noms, pas deux.
# ---------------------------------------------------------------------------
# TestPyPI heberge les memes distributions sous un nom suffixe, POINTS D'ENTREE
# COMPRIS : `publish.yml` reecrit les `[project.scripts]` en meme temps que le
# `name`. Mesure le 2026-09-08 sur les roues REELLEMENT publiees en 0.1.0 :
#
#   mmu_cli_test-0.1.0-py3-none-any.whl   -> console_scripts : mmu-test
#   mmu_tui_test-0.1.0-py3-none-any.whl   -> console_scripts : mmu-tui-test
#
# Le defaut que ce bloc ferme : le suffixe n'etait applique qu'aux PAQUETS, si
# bien qu'apres `-TestPyPI -Verifier` le script lancait `mmu --version` -- une
# commande que cette installation n'a jamais posee. Deux issues, toutes deux
# fausses : l'echec, ou -- pire -- le succes annonce sur un `mmu` REEL deja
# present sur la machine, qui aurait fait passer pour verifiee une installation
# de bac a sable jamais exercee.
#
# Le suffixe se derive donc ICI, en un seul point, des que `$ChoixVersion` est
# arrete -- il l'est : aucune invite ne le change plus bas. Le recapitulatif et
# les invites qui suivent nomment alors les commandes REELLES.
$Suffixe = ""
if ($ChoixVersion -eq 3) { $Suffixe = "-test" }
$PaquetCli   = "$DistCli$Suffixe"
$PaquetTui   = "$DistTui$Suffixe"
$CommandeCli = "$CommandeCli$Suffixe"
$CommandeTui = "$CommandeTui$Suffixe"
if ($MettreAJour)       { $ChoixReprise = 1 }
if ($Reinstaller)       { $ChoixReprise = 2 }

# ------------------------------------------------------------------- affichage

function Write-Etape  { param($m) Write-Host ""; Write-Host "==> $m" -ForegroundColor Blue }
function Write-Info   { param($m) Write-Host "    $m" }
function Write-Succes { param($m) Write-Host "    ok " -ForegroundColor Green -NoNewline; Write-Host $m }
function Write-Alerte { param($m) Write-Host "    !  " -ForegroundColor Red -NoNewline; Write-Host $m }
function Stop-Avec    { param($m) Write-Host ""; Write-Host "Echec : $m" -ForegroundColor Red; exit 1 }

# Execute une commande, ou l'affiche seulement en mode -DryRun.
function Invoke-Etape {
    param([string] $Fichier, [string[]] $Arguments)
    if ($DryRun) {
        Write-Info "[simulation] $Fichier $($Arguments -join ' ')"
        return 0
    }
    Write-Info "> $Fichier $($Arguments -join ' ')"
    # `| Out-Host` et non un appel nu : sans lui, la sortie de la commande
    # entre dans le pipeline de la fonction et `return $LASTEXITCODE` rend un
    # TABLEAU (sortie + code). Le `-ne 0` de l'appelant serait alors toujours
    # vrai, et toute installation reussie signalee en echec.
    & $Fichier @Arguments | Out-Host
    return $LASTEXITCODE
}

# Vrai sur Windows -- y compris sous Windows PowerShell 5.1, ou $IsWindows
# n'existe pas du tout (il a ete introduit avec PowerShell Core).
function Test-SurWindows {
    return ($null -eq $IsWindows) -or $IsWindows
}

# Recharge le PATH depuis le registre. Indispensable : winget et pipx posent
# leurs repertoires dans le PATH PERSISTANT, invisible du processus courant.
function Update-CheminSession {
    if (-not (Test-SurWindows)) { return }
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $utilisateur = [Environment]::GetEnvironmentVariable("Path", "User")
    $parties = @($machine, $utilisateur) | Where-Object { $_ }
    $env:Path = ($parties -join ';')
}

function Test-Commande {
    param([string] $Nom)
    return [bool] (Get-Command $Nom -ErrorAction SilentlyContinue)
}

# Y a-t-il un affichage graphique ? Ce n'est PAS une question posee a
# l'utilisateur (arbitrage d'Egan : « Inclus par defaut. Retrait manuel »),
# c'est une detection -- et elle existe parce qu'`EPIC11-ARB-253` a mesure ce
# que coute l'erreur : la roue OpenCV avec fenetres exige DOUZE bibliotheques
# systeme absentes d'un serveur nu, d'un conteneur ou d'un WSL sans X, ou
# `import cv2` echoue AVANT la premiere ligne du produit.
function Test-AffichageDisponible {
    if (Test-SurWindows) { return $true }
    if ($IsMacOS) { return $true }
    return [bool] ($env:DISPLAY -or $env:WAYLAND_DISPLAY)
}

# Le repertoire ou pipx expose ses applications. On le demande a pipx plutot
# que de le deviner : il change selon la plateforme et selon PIPX_HOME.
function Get-RepertoireBinPipx {
    if (Test-Commande "pipx") {
        try {
            $valeur = (& pipx environment --value PIPX_BIN_DIR 2>$null)
            if ($LASTEXITCODE -eq 0 -and $valeur) { return "$valeur".Trim() }
        } catch { }
    }
    return (Join-Path $HOME ".local\bin")
}

# Le raccourci du menu Demarrer (story 8.8). Pose ICI, avant le bloc de
# desinstallation, parce que c'est lui qui s'en sert le premier.
# `GetFolderPath('Programs')` est le menu Demarrer de l'UTILISATEUR : aucun
# droit administrateur, propre au compte qui installe. Jamais `CommonPrograms`,
# qui poserait un fichier pour tous les comptes de la machine, ni le Bureau.
function Get-RaccourciDossier {
    return [Environment]::GetFolderPath('Programs')
}
$RaccourciDossier = Get-RaccourciDossier
$RaccourciFichier = if ($RaccourciDossier) {
    Join-Path $RaccourciDossier "mmu-tui.lnk"
} else { "" }

# ---------------------------------------------------------------------------
#  LE RECU : ce que ce script a pose HORS pipx, et rien d'autre
# ---------------------------------------------------------------------------
# `EPIC11-ARB-274`, jumeau exact de celui d'`install.sh`. L'issue 2 de la
# desinstallation ne peut reprendre que ce qu'elle SAIT avoir ete pose ; rien
# ne l'enregistrait.
#
# `%LOCALAPPDATA%\mmu` est l'equivalent Windows du repertoire d'etat XDG,
# exactement comme l'entree de `PATH` du registre est deja l'equivalent Windows
# de la ligne de profil. Meme garde de chemin ABSOLU que du cote bash : un
# `LOCALAPPDATA` relatif ecrirait le recu dans le repertoire COURANT de qui a
# lance la commande, ou aucune desinstallation ne le retrouverait.
#
# CE QUE LE RECU N'EST PAS : ni un manifeste, ni un etat, ni une source de
# verite sur la machine. Il enregistre un GESTE PASSE, et le desinstalleur
# verifie toujours l'existence avant de retirer.
#
# TROIS champs par ligne, separes par une tabulation : nature, chemin absolu,
# date. Lisible a l'oeil, relu sans aucun outil.
function Get-RacineEtat {
    $racine = $env:LOCALAPPDATA
    if (-not $racine) {
        $racine = [Environment]::GetFolderPath('LocalApplicationData')
    }
    if (-not $racine -or -not [System.IO.Path]::IsPathRooted($racine)) {
        $racine = Join-Path $HOME ".local\state"
    }
    return $racine
}
$RecuDossier = Join-Path (Get-RacineEtat) "mmu"
$RecuFichier = Join-Path $RecuDossier "pose-par-installeur.txt"

# Note un objet pose. N'ECHOUE JAMAIS : un recu qui ne peut pas s'ecrire ne
# doit pas faire echouer une installation qui, elle, a reussi -- il le DIT, et
# la desinstallation se degradera plus tard en issue 1.
#
# LE RECU S'ECRIT APRES LA REUSSITE, jamais avant.
function Write-DansLeRecu {
    param([string] $Nature, [string] $Chemin)

    if (-not $Chemin -or -not [System.IO.Path]::IsPathRooted($Chemin)) {
        Write-Alerte "Chemin non absolu, non note dans le recu : $Chemin"
        return
    }
    if ($DryRun) {
        Write-Info "[simulation] noter $Nature dans $RecuFichier"
        return
    }
    try {
        if (-not (Test-Path -LiteralPath $RecuDossier)) {
            New-Item -ItemType Directory -Path $RecuDossier -Force | Out-Null
        }
        $date = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        Add-Content -LiteralPath $RecuFichier -Value "$Nature`t$Chemin`t$date" -Encoding UTF8
    } catch {
        Write-Alerte "Le recu $RecuFichier n'a pas pu etre complete."
        Write-Info   "L'installation continue ; la desinstallation ne saura pas"
        Write-Info   "reprendre $Chemin toute seule."
    }
}

# Relit le recu et rend les entrees dont le chemin EXISTE ENCORE, sous forme
# d'objets { Nature; Chemin }. Rend `$null` quand il n'y a pas de recu du
# tout : c'est la DEGRADATION de l'AC4, pas une erreur.
#
# UNE ENTREE DISPARUE EST DITE ET SAUTEE : quelqu'un a deja retire le fichier
# a la main, et le lui dire vaut mieux que de faire comme si le recu avait
# raison.
function Read-LeRecu {
    if (-not (Test-Path -LiteralPath $RecuFichier)) { return $null }
    $retenues = @()
    foreach ($ligne in (Get-Content -LiteralPath $RecuFichier -ErrorAction SilentlyContinue)) {
        if (-not $ligne) { continue }
        $champs = $ligne -split "`t"
        if ($champs.Count -lt 2) { continue }
        $nature = $champs[0]
        $chemin = $champs[1]
        $date = if ($champs.Count -ge 3) { $champs[2] } else { "date-inconnue" }
        if (-not $nature -or -not $chemin) { continue }
        # UN CHEMIN DU RECU DOIT ETRE ABSOLU, ET LA GARDE N'EXISTAIT QU'A
        # L'ECRITURE (finding 2 de la couche 2 de la revue 8.12, 2026-09-08 --
        # mesure cote bash, ou un recu portant `victime.txt` faisait effacer ce
        # fichier dans le repertoire courant de l'appelant). L'asymetrie etait
        # la meme ici, et l'AC11 exige le MEME contrat, pas un contrat voisin.
        #
        # Le recu n'est PAS une source de verite : il etait pourtant cru sur
        # parole pour la seule chose qui compte, l'adresse de ce qu'on efface.
        # Un recu ne se signe pas ; la garde vit donc du cote qui AGIT.
        if (-not [System.IO.Path]::IsPathRooted($chemin)) {
            Write-Alerte "Chemin non absolu au recu, rien n'est retire : $chemin"
            continue
        }
        if (Test-Path -LiteralPath $chemin) {
            $retenues += [pscustomobject] @{ Nature = $nature; Chemin = $chemin }
        } else {
            Write-Info "deja disparu, rien a retirer : $chemin ($nature, note le $date)"
        }
    }
    return ,$retenues
}

# Retire ce que le recu enregistre, CHAQUE NATURE SELON SA POLITIQUE -- les
# memes trois politiques que du cote bash :
#
#   * `pipx-pip-utilisateur` : pose par CE script, par pip. On repasse par pip,
#     jamais par un effacement de fichier -- retirer sous un gestionnaire ce
#     qu'il croit posseder est la raison 2 d'`EPIC11-ARB-274` ;
#   * `python-winget` : JAMAIS retire (AC6). Il est NOMME, et la voie
#     officielle est donnee. Retirer le Python du systeme casse le systeme ;
#   * une nature inconnue ne declenche AUCUN effacement : un recu ecrit par une
#     version future ne doit pas faire retirer n'importe quoi par une ancienne.
function Remove-SelonLeRecu {
    param($Entrees)
    foreach ($entree in $Entrees) {
        switch -Wildcard ($entree.Nature) {
            "pipx-pip-utilisateur" {
                Write-Info "pipx a ete pose par ce script (pip --user) : $($entree.Chemin)"
                $interprete = Get-PythonConvenable
                if (-not $interprete) {
                    Write-Alerte "Aucun Python convenable : pipx n'a pas pu etre retire."
                    Write-CommandeDeRetrait "pipx"
                } else {
                    $argv = $interprete.Arguments + @("-m", "pip", "uninstall", "-y", "pipx")
                    if ((Invoke-Etape $interprete.Fichier $argv) -ne 0) {
                        Write-Alerte "pip n'a pas retire pipx."
                    }
                }
            }
            "python*" {
                # LA FRONTIERE DE L'AC6, ECRITE DANS LE PRODUIT. Une entree
                # `python` traverse le recu, l'existence et l'annonce -- et ne
                # devient jamais un retrait.
                Write-Alerte "Python n'est PAS retire, meme s'il figure au recu : $($entree.Chemin)"
                Write-CommandeDeRetrait "python"
            }
            default {
                Write-Alerte "Nature inconnue au recu, rien n'est retire : $($entree.Nature) ($($entree.Chemin))"
            }
        }
    }
}

# AC5 -- LE RECU SE RETIRE LUI-MEME, par l'issue 1 comme par l'issue 2. Une
# story qui ajoute un fichier sur la machine de quelqu'un et l'oublie au
# retrait ajoute la fuite qu'elle pretend fermer.
function Remove-RepertoireDEtat {
    if (-not ($RecuDossier -like "*mmu")) {
        Write-Alerte "Chemin d'etat inattendu, rien n'est retire : $RecuDossier"
        return
    }
    if (-not (Test-Path -LiteralPath $RecuDossier)) {
        Write-Info "Aucun recu en $RecuDossier : rien a y retirer."
        return
    }
    if ($DryRun) {
        Write-Info "[simulation] retrait de $RecuDossier"
    } else {
        Remove-Item -LiteralPath $RecuDossier -Recurse -Force
        Write-Succes "Recu retire : $RecuDossier"
    }
}

# La voie de RETRAIT la plus officielle par dependance, sur Windows -- le
# pendant exact de la table `commande_de_secours … retrait` d'`install.sh`, et
# la septieme ligne du tableau d'`EPIC11-ARB-271` vit deja ici pour la pose.
#
# LA LIGNE PYTHON N'EST PAS UNE COMMANDE, volontairement : c'est un renvoi a
# la documentation officielle, avec son motif. Une frontiere negative du banc
# balaie les DEUX scripts pour s'assurer qu'aucun retrait automatique de
# Python n'y est jamais ecrit.
# LA TABLE DE POSE, jumelle de celle de `commande_de_secours` cote bash
# (`EPIC11-ARB-271`). Elle n'existait pas ici : la seule commande officielle
# de pose que ce script portait vivait EN LITTERAL dans l'etape ffmpeg, ce qui
# est exactement le « remede recopie a cinq endroits » que l'arbitrage nomme.
# La story 8.14 en a besoin -- un binaire trop ancien doit dire par ou en
# prendre un a jour -- et elle la pose plutot que de recopier une sixieme fois.
function Write-CommandeDeSecours {
    param([string] $Dependance)
    Write-Info ""
    Write-Info "La commande de secours pour $Dependance, la plus officielle disponible :"
    switch ($Dependance) {
        "ffmpeg" {
            Write-Info "  winget install --id Gyan.FFmpeg -e"
            Write-Info "  ou https://www.gyan.dev/ffmpeg/builds/ (build ""essentials"")"
        }
        "pipx"   { Write-Info "  python -m pip install --user pipx" }
        "python" { Write-Info "  https://www.python.org/downloads/windows/" }
        default  {
            Write-Info "  $Dependance n'a pas de commande officielle epinglee dans ce script."
            Write-Info "  https://gantiz.github.io/mixed_media_utility/"
        }
    }
}

function Write-CommandeDeRetrait {
    param([string] $Dependance)
    Write-Info ""
    Write-Info "Pour RETIRER $Dependance, la voie la plus officielle disponible :"
    switch ($Dependance) {
        "ffmpeg" { Write-Info "  winget uninstall --id Gyan.FFmpeg -e" }
        "pipx"   {
            Write-Info "  pipx uninstall-all      (les autres applications posees par pipx)"
            Write-Info "  python -m pip uninstall pipx"
        }
        "python" {
            Write-Info "  ce script ne donne AUCUNE commande de retrait pour Python."
            Write-Info "  Le retirer casse ce qui en depend, et l'interpreteur du"
            Write-Info "  systeme n'a pas ete pose par cette installation."
            Write-Info "  La voie officielle, si vous savez ce que vous faites :"
            Write-Info "  https://www.python.org/downloads/"
        }
        default  {
            Write-Info "  $Dependance n'a pas de voie de retrait epinglee dans ce script."
            Write-Info "  https://gantiz.github.io/mixed_media_utility/"
        }
    }
}

# ------------------------------------------------------ le dialogue au clavier

# Y a-t-il une console au bout ? Voir l'entete : c'est
# `[Console]::IsInputRedirected` qui le dit, mesure dans les trois regimes.
# Ni le code de sortie de `Read-Host` (toujours 0), ni la valeur rendue
# (chaine vide, indistinguable d'un Entree) ne repondent a la question.
$script:Interactif = (-not $NonInteractif) -and (-not [Console]::IsInputRedirected)
if ($NonInteractif) {
    $script:RaisonMuette = "mode non interactif"
} else {
    $script:RaisonMuette = "pas de console"
}

# Pose une question a choix numerotes et rend le numero choisi.
#
# Trois garanties, les memes que du cote bash :
#   - une TOUCHE, jamais une syntaxe : un chiffre, ou Entree seule ;
#   - une saisie non reconnue REPOSE la question, elle n'echoue pas ;
#   - sans console, jamais un blocage sec : le defaut est pris ET ANNONCE.
function Demander {
    param([int] $Defaut, [string] $Intitule, [string[]] $Options)

    if (-not $script:Interactif) {
        Write-Host ""
        Write-Host $Intitule
        Write-Info ("$script:RaisonMuette : je prends $Defaut) " + $Options[$Defaut - 1])
        return $Defaut
    }

    while ($true) {
        Write-Host ""
        Write-Host $Intitule
        for ($i = 1; $i -le $Options.Count; $i++) {
            if ($i -eq $Defaut) {
                Write-Host ("      $i) " + $Options[$i - 1] + " [defaut]")
            } else {
                Write-Host ("      $i) " + $Options[$i - 1])
            }
        }
        $saisie = Read-Host "    Ton choix [$Defaut] puis Entree"
        $saisie = ($saisie -replace '\s', '')
        if ($saisie -eq "") { return $Defaut }
        if ($saisie -match '^[0-9]+$') {
            $numero = [int] $saisie
            if ($numero -ge 1 -and $numero -le $Options.Count) { return $numero }
        }
        Write-Alerte "Je n'ai pas compris `"$saisie`". Repondre par un chiffre de 1 a $($Options.Count), ou Entree."
    }
}

# CETTE FONCTION A ETE DEPLACEE ICI, ET LE CHOIX SE DIT PLUTOT QUE DE SE
# TAIRE (story 8.12). Elle vivait dans l'etat des lieux, c'est-a-dire APRES le
# bloc de desinstallation. PowerShell ne definit une fonction qu'au moment ou
# sa definition s'EXECUTE : appelee depuis la desinstallation, elle aurait rendu
# « n'est pas reconnu comme nom d'applet de commande » -- une panne d'ordre, pas
# de logique, et le jumeau exact de ce que `set -u` produit du cote bash quand
# on y cite une variable posee plus bas.
#
# L'issue 2 en a besoin : retirer un pipx pose par `pip install --user` passe
# par le meme interpreteur, jamais par un effacement de fichier.
# Le lanceur `py` sait enumerer les Python installes ; on lui demande d'abord
# une version assez recente, puis on retombe sur `python` du PATH. Un `python`
# present ne suffit pas : Windows expose un alias Store qui n'est pas un
# interpreteur, et de vieilles 3.9/3.10 trainent souvent.
# ============================================================================
#  CE QUI EST POSE HORS DU `PATH` (`EPIC11-ARB-279`, story 8.14)
# ============================================================================
#
# Le MEME contrat que `install.sh`, pas un contrat voisin : les trois issues,
# la liste bornee, le lancement du binaire trouve.
#
# CES FONCTIONS SONT DEFINIES ICI, AVANT L'ETAT DES LIEUX QUI LES APPELLE, et
# c'est la meme panne d'ORDRE que `Get-PythonConvenable` a payee : PowerShell
# ne definit une fonction qu'au moment ou sa definition s'EXECUTE.
#
# CE QU'ELLES NE FONT PAS (AC12) : elles ne cherchent rien hors de la liste,
# elles n'ecrivent dans AUCUN profil ni dans le PATH persistant du registre --
# `Update-CheminSession` le RELIT, il ne l'ecrit pas --, et elles n'ecrivent
# rien au recu : un binaire pose par l'utilisateur n'appartient pas a ce
# script.

# UN CRAN, ET UN SEUL. Rend le conteneur lui-meme PLUS ses sous-repertoires
# immediats et leur `Scripts\` -- c'est la ou python.org et `pip --user`
# posent reellement. `-Depth` n'existe pas ici : il n'y a aucune recursion, un
# seul `Get-ChildItem -Directory` non recursif, borne par construction.
function Expand-ConteneurDePython {
    param([string] $Conteneur)
    $trouves = @()
    if (-not $Conteneur) { return $trouves }
    if (-not (Test-Path -LiteralPath $Conteneur -PathType Container)) { return $trouves }
    $trouves += $Conteneur
    $sous = @(Get-ChildItem -LiteralPath $Conteneur -Directory -ErrorAction SilentlyContinue)
    foreach ($enfant in $sous) {
        $trouves += $enfant.FullName
        $scripts = Join-Path $enfant.FullName "Scripts"
        if (Test-Path -LiteralPath $scripts -PathType Container) { $trouves += $scripts }
    }
    return $trouves
}

# LA LISTE BORNEE, A UN SEUL ENDROIT. Jamais un `Get-ChildItem -Recurse`,
# jamais un `where.exe /R` : une recherche non bornee sur un disque plein est
# un temps infini, et c'est la famille de panne que ce depot a deja payee.
function Get-EmplacementsUsuels {
    $emplacements = @()
    if (Test-SurWindows) {
        # TROIS DES QUATRE ENTREES DE CETTE LISTE NE POUVAIENT RIEN TROUVER
        # (finding `C1-6` de la couche 1, 2026-09-09). `…\Programs`,
        # `…\Programs\Python` et `$env:ProgramFiles` sont des repertoires
        # CONTENEURS, jamais des repertoires de binaires : python.org pose
        # dans `…\Programs\Python\Python3xx\`, un cran plus bas. La seule
        # utile, `WindowsApps`, ne porte que l'alias du Store -- et les deux
        # emplacements canoniques d'un pipx pose a la main manquaient.
        # Autrement dit le defaut que cette story existe pour fermer restait
        # OUVERT sur Windows, sous une liste qui avait l'air fournie.
        #
        # Le remede reste BORNE : on descend d'UN cran dans les conteneurs
        # connus, par un `Get-ChildItem` non recursif -- jamais un
        # `-Recurse`, jamais un `where.exe /R`, qui est la famille de panne
        # que ce depot a deja payee.
        if ($env:LOCALAPPDATA) {
            # Le repertoire de LIENS de winget : il porte les raccourcis des
            # paquets poses par winget, et c'est le premier a manquer d'un
            # PATH qui n'a pas ete recharge.
            $emplacements += (Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps")
            $emplacements += (Expand-ConteneurDePython (Join-Path $env:LOCALAPPDATA "Programs\Python"))
            $emplacements += (Expand-ConteneurDePython (Join-Path $env:LOCALAPPDATA "Programs"))
        }
        if ($env:ProgramFiles) {
            $emplacements += (Expand-ConteneurDePython $env:ProgramFiles)
        }
        # LES DEUX EMPLACEMENTS CANONIQUES D'UN PIPX POSE A LA MAIN, qui
        # manquaient tous les deux : `pip install --user pipx` ecrit ses
        # scripts sous `%APPDATA%\Python\Python3xx\Scripts`.
        if ($env:APPDATA) {
            $emplacements += (Expand-ConteneurDePython (Join-Path $env:APPDATA "Python"))
        }
    } else {
        # Le meme script sert a mesurer depuis Linux et macOS (le banc le joue
        # ainsi) : la liste y est celle d'`install.sh`, pour que les deux
        # scripts ne divergent pas sur un chemin. `flatpak` en faisait partie
        # cote bash et manquait ici, alors que ce commentaire affirmait deja
        # l'identite (finding `C1-7` de la couche 1).
        $emplacements += "/usr/local/bin"
        if ($HOME) { $emplacements += (Join-Path $HOME ".local/bin") }
        $emplacements += "/snap/bin"
        $emplacements += "/var/lib/flatpak/exports/bin"
    }
    return $emplacements
}

# Le drapeau qui fait dire sa version a un binaire, jumeau de
# `drapeau_de_version`.
function Get-DrapeauDeVersion {
    param([string] $Nom)
    if ($Nom -in @("ffmpeg", "ffprobe")) { return "-version" }
    return "--version"
}

# UN BINAIRE TROUVE N'EST CRU QUE S'IL DEMARRE (AC2), et il est lance sous un
# PLAFOND DE TEMPS -- le meme que celui d'`install.sh`, et pour la meme raison :
# un binaire non signe dont l'evaluation part au reseau suspend l'installateur
# sans un mot.
#
# ON TUE PAR OBJET DE PROCESSUS, jamais par motif : `Start-Process -PassThru`
# rend LE processus lance, et `Stop-Process` prend cet objet-la. Il n'y a pas
# un seul `Get-Process -Name` dans cette fonction (regle 6 de `CLAUDE.md`).
$PlafondDeLancement = 30
function Invoke-AvecPlafond {
    param([string] $Fichier, [string[]] $Arguments, [string] $Sortie)
    try {
        $processus = Start-Process -FilePath $Fichier -ArgumentList $Arguments `
            -RedirectStandardOutput $Sortie -RedirectStandardError "$Sortie.err" `
            -NoNewWindow -PassThru
    } catch {
        return $false
    }
    if (-not $processus.WaitForExit($PlafondDeLancement * 1000)) {
        try { Stop-Process -InputObject $processus -Force } catch { }
        return $false
    }
    return ($processus.ExitCode -eq 0)
}

# Le plancher, quand il y en a un : `Python >= 3.11`, `ffmpeg >= 5.0`. Une
# version illisible est ACCEPTEE -- refuser ce qu'on ne sait pas mesurer
# reintroduirait le faux negatif que cette story ferme.
$FfmpegMajeurMinimum = 5
function Test-PlancherTenu {
    param([string] $Nom, [string] $Chemin, [string] $Version)
    if ($Nom -like "python*") {
        try {
            $sortie = & $Chemin -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -ne 0 -or -not $sortie) { return $false }
            return ([version]$sortie -ge $PythonMinimum)
        } catch { return $false }
    }
    if ($Nom -eq "ffmpeg") {
        if ($Version -match 'version\s+n?(\d+)') {
            return ([int]$Matches[1] -ge $FfmpegMajeurMinimum)
        }
        return $true
    }
    return $true
}

# LE BALAYAGE. Rend un objet { Chemin ; Repertoire ; Version } quand il a
# trouve, $null sinon, et pose $script:TropAncienHorsDuPath quand il n'a vu que
# du trop ancien (AC3).
$script:TropAncienHorsDuPath = ""
function Find-HorsDuPath {
    param([string] $Nom)

    $script:TropAncienHorsDuPath = ""
    if (-not $ChercherHorsDuPath) { return $null }
    $drapeau = Get-DrapeauDeVersion $Nom
    $journal = Join-Path ([System.IO.Path]::GetTempPath()) ("mmu-version-" + [guid]::NewGuid().ToString() + ".txt")

    foreach ($repertoire in (Get-EmplacementsUsuels)) {
        if (-not $repertoire) { continue }
        foreach ($suffixe in @("", ".exe", ".cmd", ".bat")) {
            $candidat = Join-Path $repertoire ($Nom + $suffixe)
            if (-not (Test-Path -LiteralPath $candidat -PathType Leaf)) { continue }
            if (-not (Invoke-AvecPlafond $candidat @($drapeau) $journal)) { continue }
            $version = ""
            if (Test-Path -LiteralPath $journal) {
                $version = (Get-Content -LiteralPath $journal -TotalCount 1 -ErrorAction SilentlyContinue)
            }
            if (Test-PlancherTenu $Nom $candidat $version) {
                return [pscustomobject]@{
                    Chemin = $candidat; Repertoire = $repertoire; Version = $version }
            }
            if (-not $script:TropAncienHorsDuPath) {
                $script:TropAncienHorsDuPath = "$candidat ($version)"
            }
        }
    }
    return $null
}

# LES NOMS D'INTERPRETEUR, ecrits UNE fois -- jumeau de `NOMS_DE_PYTHON`.
# Deux listes divergeraient au premier Python 3.14, et le commentaire du bash
# le disait deja pendant qu'elles divergeaient : celle-ci portait `python` que
# le bash n'a pas (finding `C1-7` de la couche 1, 2026-09-09).
$script:NomsDePython = @("python3.13", "python3.12", "python3.11", "python3")

# LA MEME RECHERCHE QUE `Find-HorsDuPath`, PARCOURUE SUR LES NOMS -- jumeau
# exact de `chercher_python_hors_du_path`.
#
# CE QU'ELLE FERME, ET C'ETAIT UNE AC3 MUETTE DANS 4 REGIMES SUR 5 (finding
# `C1-5` de la couche 1, 2026-09-09) : `Find-HorsDuPath` remet
# `$script:TropAncienHorsDuPath` a `""` A CHAQUE APPEL. L'appelant l'appelait
# une fois par nom, donc le « trop ancien » n'etait conserve que si le
# DERNIER nom en etait le porteur. Pour les autres, l'utilisateur lisait
# « Python : absent, il sera installe » alors qu'un Python trop ancien avait
# ete vu et nomme -- l'inverse exact de ce que l'AC3 promet.
#
# Le remede est celui du bash : accumuler le PREMIER trop ancien a travers la
# boucle, et le reposer une fois la boucle finie.
function Find-PythonHorsDuPath {
    $premierTropAncien = ""
    foreach ($nom in $script:NomsDePython) {
        $trouvaille = Find-HorsDuPath $nom
        if ($trouvaille) { return $trouvaille }
        if ($script:TropAncienHorsDuPath -and -not $premierTropAncien) {
            $premierTropAncien = $script:TropAncienHorsDuPath
        }
    }
    $script:TropAncienHorsDuPath = $premierTropAncien
    return $null
}

# LA LIGNE DE PROFIL EST DONNEE, JAMAIS ECRITE (AC5). Aucun `setx`, aucun
# `[Environment]::SetEnvironmentVariable(..., 'User')`, aucune ecriture dans
# `$PROFILE` : ce bloc ne touche que le PATH du PROCESSUS.
function Show-LigneDeProfil {
    param([string[]] $Repertoires)
    Write-Info ""
    Write-Info "La ligne a ajouter a ton PATH pour que ta machine cesse de l'ignorer :"
    foreach ($repertoire in $Repertoires) {
        Write-Info ("  " + '$env:Path' + " = `"$repertoire;" + '$env:Path' + "`"")
    }
    # OU LA POSER, ET C'ETAIT LA MOITIE QUI MANQUAIT (finding `C3-3` de la
    # couche 3, 2026-09-09). Le jumeau bash nomme `${PROFIL}` ; celui-ci
    # rendait une ligne de SESSION sans jamais dire ou l'ecrire, donc
    # l'utilisateur Windows perdait sa ligne a la fermeture du terminal.
    # C'est la phrase de valeur meme de la story -- « que je sache quelle
    # ligne ajouter a MON PROFIL ».
    Write-Info ""
    Write-Info ("Pour qu'elle survive au terminal, la poser dans ton profil : " + '$PROFILE')
    Write-Info "Ce script ne l'ecrit pas lui-meme."
}

# LES TROIS ISSUES (`EPIC11-ARB-89`). Rend $true quand l'utilisateur a choisi
# d'EXPOSER, $false quand il a choisi d'ignorer. L'issue 3 donne la ligne et
# sort -- le meme geste que l'issue 3 du desinstalleur, qui affiche et ne fait
# pas.
function Invoke-TroisIssuesHorsDuPath {
    param([string[]] $Repertoires)
    $issue = Demander 1 $IntituleHorsDuPath @(
        $IssueExposerPourCetteInstallation,
        $IssueIgnorerEtPoserQuandMeme,
        $IssueLigneSeuleEtSortir)
    if ($issue -eq 1) {
        foreach ($repertoire in $Repertoires) {
            $env:Path = "$repertoire;$env:Path"
        }
        Show-LigneDeProfil $Repertoires
        return $true
    }
    if ($issue -eq 2) {
        Write-Info "Tres bien : cette copie est ignoree, l'installation posera la sienne."
        return $false
    }
    Show-LigneDeProfil $Repertoires
    Write-Etape "Termine"
    Write-Info "Rien n'a ete change. Ajoute la ligne ci-dessus, ouvre un nouveau"
    Write-Info "terminal, puis relance cette commande."
    exit 0
}

# AC3 -- un binaire TROUVE mais TROP ANCIEN est traite comme absent, EN LE
# DISANT. Il reemploie `Write-CommandeDeSecours`, la table officielle, plutot
# que de recopier une commande.
function Show-TropAncien {
    param([string] $Dependance, [string] $Trouvaille)
    Write-Alerte "$Trouvaille est pose hors du PATH, mais trop ancien pour cet outil."
    Write-Info "Il est donc traite comme absent, et $Dependance sera pose quand meme."
    Write-CommandeDeSecours $Dependance
}

function Get-PythonConvenable {
    foreach ($essai in @(
        @{ Fichier = "py";      Arguments = @("-3.13") },
        @{ Fichier = "py";      Arguments = @("-3.12") },
        @{ Fichier = "py";      Arguments = @("-3.11") },
        @{ Fichier = "python";  Arguments = @() },
        @{ Fichier = "python3"; Arguments = @() }
    )) {
        if (-not (Test-Commande $essai.Fichier)) { continue }
        try {
            $argv = $essai.Arguments + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
            $sortie = & $essai.Fichier @argv 2>$null
            if ($LASTEXITCODE -eq 0 -and $sortie -and ([version]$sortie -ge $PythonMinimum)) {
                return $essai
            }
        } catch { continue }
    }
    return $null
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

if ($Desinstaller) {
    Write-Etape "Desinstallation"

    # LA QUESTION VIENT AVANT TOUT RETRAIT (`EPIC11-ARB-274`, AC1), et elle a
    # TROIS issues -- jamais deux, jamais une, jamais un blocage sec
    # (`EPIC11-ARB-89`). Les libelles sont les MEMES que ceux d'`install.sh`,
    # MOT POUR MOT, et une frontiere du banc les compare.
    #
    # CE QUI A CHANGE : avant cette story, `-Desinstaller` ne posait rien, et
    # le commentaire disait « avoir tape -Desinstaller EST l'acte conscient ».
    # C'etait vrai d'un desinstalleur qui ne retirait que l'application ; ca ne
    # l'est plus d'un qui peut reprendre pipx. « Tout supprimer » et « juste
    # mmu » ne sont pas le meme acte.
    #
    # LE DEFAUT EST L'ISSUE 1, et `-NonInteractif` le prend : une machine
    # muette ne retire jamais plus que l'application.
    $issueDeRetrait = Demander 1 $IntituleDuRetrait @(
        $IssueApplicationSeule,
        $IssueToutCeQueLeScriptAPose,
        $IssueMontrerLesCommandes)

    # ISSUE 3 : ELLE AFFICHE ET NE FAIT PAS (AC6). Elle sort AVANT le premier
    # retrait, et c'est ce qui la rend mesurable sur l'etat de la machine :
    # apres elle, rien n'a bouge -- ni les distributions, ni le PATH, ni le
    # raccourci, ni le recu lui-meme.
    if ($issueDeRetrait -eq 3) {
        Write-Info ""
        Write-Info "RIEN n'est retire. Voici les voies officielles de retrait, pour la"
        Write-Info "voie par laquelle chaque dependance est arrivee sur cette machine."
        Write-CommandeDeRetrait "ffmpeg"
        Write-CommandeDeRetrait "pipx"
        Write-CommandeDeRetrait "python"
        Write-Info ""
        Write-Info "Pour retirer l'application elle-meme, relancer et choisir 1 ou 2."
        Write-Succes "Termine."
        exit 0
    }

    # ISSUE 2 : elle a besoin du recu, et un recu absent DEGRADE (AC4). Une
    # installation anterieure a ce mecanisme, ou un recu efface, ne fait pas
    # echouer la desinstallation -- elle se rabat sur l'issue 1 EN LE DISANT,
    # et l'issue 3 reste entiere.
    $recuLu = $null
    if ($issueDeRetrait -eq 2) {
        Write-Info "Lecture du recu $RecuFichier :"
        $recuLu = Read-LeRecu
        if ($null -eq $recuLu) {
            Write-Alerte "Aucun recu en $RecuFichier : ce script ne sait pas ce qu'il a pose ici."
            Write-Info "Je me rabats sur l'issue 1 : l'application seule."
            Write-Info "Pour retirer Python, ffmpeg ou pipx a la main, relancer et choisir 3."
            $issueDeRetrait = 1
        }
    }

    # L'ANNONCE DIT CE QUI PART, AVANT QUE CA PARTE (AC7), et elle enumere les
    # CHEMINS REELS plutot qu'une categorie.
    $binPipx = Get-RepertoireBinPipx
    Write-Info "Vont etre retires, s'ils existent : $DistTui, $DistCli"
    Write-Info "Ainsi que l'entree $binPipx du PATH utilisateur."
    if ((Test-SurWindows) -and $RaccourciFichier) {
        Write-Info "Et le raccourci du menu Demarrer : $RaccourciFichier"
    }
    # AC5 : le recu part lui aussi, par l'issue 1 comme par l'issue 2.
    Write-Info "Ainsi que le recu de ce que ce script a pose : $RecuDossier"

    if ($null -ne $recuLu) {
        if ($recuLu.Count -gt 0) {
            Write-Info "Et, d'apres le recu, ce que CE SCRIPT a pose :"
            foreach ($entree in $recuLu) {
                if ($entree.Nature -like "python*") {
                    Write-Info "  $($entree.Chemin) ($($entree.Nature)) -- NON retire, voir plus bas"
                } else {
                    Write-Info "  $($entree.Chemin) ($($entree.Nature))"
                }
            }
        } else {
            Write-Info "Le recu ne designe plus aucun objet present : rien de plus a retirer."
        }
    } else {
        Write-Info "Ni Python, ni ffmpeg, ni pipx ne sont touches."
    }

    if (Test-Commande "pipx") {
        foreach ($distribution in @($DistTui, $DistCli, "$DistTui-test", "$DistCli-test")) {
            # Une distribution absente n'est pas une erreur : un desinstalleur
            # qui echoue parce qu'il n'y avait rien a desinstaller est un
            # blocage sec pour rien.
            Invoke-Etape "pipx" @("uninstall", $distribution) | Out-Null
        }
    } else {
        Write-Alerte "pipx est absent : aucun paquet a retirer."
    }

    # L'equivalent Windows de « la ligne ajoutee au profil » est une entree du
    # PATH utilisateur, dans le registre. On garde une COPIE de l'ancienne
    # valeur avant d'y toucher : editer le PATH de quelqu'un sans filet est
    # exactement le genre de geste qu'on ne rattrape pas.
    if (Test-SurWindows) {
        $ancien = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($ancien -and $ancien.Split(';') -contains $binPipx) {
            $sauvegarde = Join-Path $HOME "mmu-path-utilisateur-avant-desinstallation.txt"
            $nouveau = ($ancien.Split(';') | Where-Object { $_ -and $_ -ne $binPipx }) -join ';'
            if ($DryRun) {
                Write-Info "[simulation] copie de l'ancien PATH utilisateur dans $sauvegarde"
                Write-Info "[simulation] retrait de $binPipx du PATH utilisateur"
            } else {
                Set-Content -Path $sauvegarde -Value $ancien -Encoding UTF8
                Write-Info "Ancien PATH utilisateur conserve dans $sauvegarde"
                [Environment]::SetEnvironmentVariable("Path", $nouveau, "User")
                Update-CheminSession
            }
        } else {
            Write-Info "Aucune entree pipx dans le PATH utilisateur : rien a y retirer."
        }
    } else {
        Write-Info "Hors Windows : le PATH se nettoie par scripts/install.sh --desinstaller."
    }

    # Le raccourci (story 8.8). Retrait INCONDITIONNEL sous Windows : ni
    # l'affichage ni les composants ne sont connus ici -- l'etat des lieux
    # vient APRES ce bloc. Un fichier qu'on a pu poser doit pouvoir etre retire
    # quelle que soit la machine sur laquelle on le retire (`EPIC11-ARB-89`).
    if ((Test-SurWindows) -and $RaccourciFichier) {
        if (Test-Path -LiteralPath $RaccourciFichier) {
            if ($DryRun) {
                Write-Info "[simulation] retrait de $RaccourciFichier"
            } else {
                Remove-Item -LiteralPath $RaccourciFichier -Force
                Write-Succes "Raccourci retire : $RaccourciFichier"
            }
        } else {
            Write-Info "Aucun raccourci en $RaccourciFichier : rien a y retirer."
        }
    }

    # ISSUE 2 : ce que le recu enregistre, et RIEN d'autre. La politique par
    # nature vit dans `Remove-SelonLeRecu` -- notamment le refus, jamais
    # negociable, de retirer Python (AC6).
    if ($issueDeRetrait -eq 2 -and $null -ne $recuLu) {
        Remove-SelonLeRecu $recuLu
    }

    # AC5 -- et il vient APRES la lecture, jamais avant : retirer le recu
    # d'abord reviendrait a oublier ce qu'on s'apprete a reprendre.
    Remove-RepertoireDEtat

    Write-Succes "Termine."
    exit 0
}

# ============================================================================
#  1. etat des lieux -- on regarde AVANT de demander
# ============================================================================

Write-Etape "Etat des lieux"


$python = Get-PythonConvenable
$PythonPresent = [bool] $python
if ($PythonPresent) {
    Write-Succes "Python : $($python.Fichier) $($python.Arguments -join ' ')"
} else {
    # `Get-Command` ne regarde que le PATH. On consulte la liste BORNEE avant
    # de conclure « absent » (`EPIC11-ARB-279`).
    $trouvaille = Find-PythonHorsDuPath
    if ($trouvaille) {
        Write-Alerte "Python est POSE hors du PATH : $($trouvaille.Chemin)"
        Write-Info   "  $($trouvaille.Version)"
        Write-Info   "Ton shell ne l'expose pas ; sans cela il serait reinstalle par-dessus."
        if (Invoke-TroisIssuesHorsDuPath @($trouvaille.Repertoire)) {
            $python = @{ Fichier = $trouvaille.Chemin; Arguments = @() }
            $PythonPresent = $true
            Write-Succes "Python : $($trouvaille.Version) -> $($trouvaille.Chemin)"
        }
    } elseif ($script:TropAncienHorsDuPath) {
        Show-TropAncien "python" $script:TropAncienHorsDuPath
    }
    if (-not $PythonPresent) {
        Write-Info "Python >= $PythonMinimum : absent, il sera installe."
    }
}

# ffprobe est verifie separement : le projet lit les metadonnees video avec
# ffprobe (video_metadata.py), et un paquet qui ne fournirait que ffmpeg
# echouerait plus tard, a l'usage seulement.
#
# LA RECHERCHE HORS DU PATH LES CHERCHE AUSSI SEPAREMENT (AC7), et le desaccord
# se DIT : trouver l'un sans l'autre n'est PAS une detection reussie.
$FfmpegSurLePath  = Test-Commande "ffmpeg"
$FfprobeSurLePath = Test-Commande "ffprobe"
$FfmpegPresent = $FfmpegSurLePath -and $FfprobeSurLePath
if ($FfmpegPresent) {
    Write-Succes ((ffmpeg -version 2>$null | Select-Object -First 1))
} else {
    $ffmpegHors = $null
    $ffprobeHors = $null
    $ffmpegTropAncien = ""
    if (-not $FfmpegSurLePath) {
        $ffmpegHors = Find-HorsDuPath "ffmpeg"
        if (-not $ffmpegHors) {
            $ffmpegTropAncien = $script:TropAncienHorsDuPath
            # AC3 -- la CAUSE se dit avant sa consequence, comme cote bash.
            if ($ffmpegTropAncien) { Show-TropAncien "ffmpeg" $ffmpegTropAncien }
        }
    }
    if (-not $FfprobeSurLePath) { $ffprobeHors = Find-HorsDuPath "ffprobe" }

    $ffmpegDisponible  = $FfmpegSurLePath  -or [bool] $ffmpegHors
    $ffprobeDisponible = $FfprobeSurLePath -or [bool] $ffprobeHors
    if (($ffmpegHors -or $ffprobeHors) -and $ffmpegDisponible -and $ffprobeDisponible) {
        Write-Alerte "ffmpeg / ffprobe sont POSES hors du PATH."
        $repertoires = @()
        if ($ffmpegHors)  { $repertoires += $ffmpegHors.Repertoire }
        if ($ffprobeHors -and ($repertoires -notcontains $ffprobeHors.Repertoire)) {
            $repertoires += $ffprobeHors.Repertoire
        }
        if (Invoke-TroisIssuesHorsDuPath $repertoires) {
            $FfmpegPresent = $true
            Write-Succes "ffmpeg : $(if ($ffmpegHors) { $ffmpegHors.Version } else { 'deja sur le PATH' })"
        }
    } elseif ($ffmpegHors -or $ffprobeHors) {
        if ($ffmpegHors) {
            Write-Alerte "ffmpeg est pose hors du PATH ($($ffmpegHors.Chemin)), mais ffprobe reste introuvable."
        } elseif ($ffmpegTropAncien) {
            Write-Alerte "ffprobe est pose hors du PATH ($($ffprobeHors.Chemin)), mais aucun ffmpeg retenu ne l'accompagne."
        } else {
            Write-Alerte "ffprobe est pose hors du PATH ($($ffprobeHors.Chemin)), mais ffmpeg reste introuvable."
        }
        Write-Info "L'outil a besoin des DEUX : ce n'est donc pas une detection reussie."
    }
    if (-not $FfmpegPresent) { Write-Info "ffmpeg / ffprobe : absent." }
}

$PipxPresent = Test-Commande "pipx"
if ($PipxPresent) {
    Write-Succes "pipx : present"
} else {
    # LE CAS D'EGAN, MOT POUR MOT : pipx pose a la main, hors du PATH, non
    # detecte, et RECOMPILE (2026-09-08).
    $pipxHors = Find-HorsDuPath "pipx"
    if ($pipxHors) {
        Write-Alerte "pipx est POSE hors du PATH : $($pipxHors.Chemin)"
        Write-Info   "  $($pipxHors.Version)"
        Write-Info   "Ton shell ne l'expose pas ; sans cela il serait reinstalle par-dessus."
        if (Invoke-TroisIssuesHorsDuPath @($pipxHors.Repertoire)) {
            $PipxPresent = $true
            Write-Succes "pipx : present ($($pipxHors.Chemin))"
        }
    }
    if (-not $PipxPresent) { Write-Info "pipx : absent, il sera installe." }
}

$Affichage = Test-AffichageDisponible
if ($Affichage) {
    Write-Succes "affichage graphique : detecte -- apercu video en fenetre disponible"
} else {
    Write-Info "affichage graphique : aucun -- roue OpenCV sans fenetres ($RoueCvSansFenetres)"
}

# Une installation deja posee ? On la NOMME plutot que de la recouvrir en
# silence (arbitrage d'Egan : la relance est une mise a jour, pas une
# reinstallation).
$InstallationExistante = ""
$VersionExistante = ""
if ($PipxPresent) {
    try {
        $lignes = @(& pipx list --short 2>$null)
        foreach ($ligne in $lignes) {
            if ("$ligne" -match "^($DistCli|$DistTui)(-test)?\s+(\S+)") {
                $InstallationExistante = $Matches[1] + $Matches[2]
                $VersionExistante = $Matches[3]
                break
            }
        }
    } catch { }
}
if ($InstallationExistante) {
    Write-Succes "deja installe : $InstallationExistante $VersionExistante"
}

# ============================================================================
#  2. les questions
# ============================================================================

# --- reprise : posee SEULEMENT si quelque chose est deja installe ------------
if ($InstallationExistante -and $ChoixReprise -eq 0) {
    $ChoixReprise = Demander 1 "$InstallationExistante $VersionExistante est deja installe." @(
        "le mettre a jour (rapide : seul ce qui a change est retelecharge)",
        "tout reinstaller de zero",
        "ne rien changer et sortir")
}

if ($ChoixReprise -eq 3) {
    Write-Etape "Termine"
    Write-Info "Rien n'a ete change. $InstallationExistante $VersionExistante reste en place."
    exit 0
}

$MiseAJour = $false
if ($InstallationExistante -and $ChoixReprise -eq 1) {
    $MiseAJour = $true
    # Les composants sont deja tranches par ce qui est installe. Un parametre
    # EXPLICITE reste plus fort que le disque.
    if ($ChoixComposants -eq 0) {
        if ($InstallationExistante -like "$DistCli*") { $ChoixComposants = 1 } else { $ChoixComposants = 2 }
    }
}

# --- question 1 : que veux-tu installer ? ------------------------------------
if ($ChoixComposants -eq 0) {
    $ChoixComposants = Demander 2 "Que veux-tu installer ?" @(
        "$CommandeCli seul -- la ligne de commande",
        "$CommandeCli + l'interface terminal ($CommandeTui)")
}

# --- question 2 : ffmpeg (seulement s'il manque) -----------------------------
if ((-not $FfmpegPresent) -and $ChoixFfmpeg -eq 0) {
    # Le second libelle DIT SA CONSEQUENCE (Egan, 2026-09-07) -- voir le meme
    # commentaire dans install.sh.
    $ChoixFfmpeg = Demander 1 "ffmpeg est absent. C'est la seule dependance systeme de l'outil." @(
        "l'installer maintenant",
        "non - necessite d'installer manuellement ffmpeg")
}
if ($ChoixFfmpeg -eq 0) { $ChoixFfmpeg = 1 }

# --- question 3 : ajouter les commandes au PATH ? ----------------------------
# On nomme les COMMANDES : Egan a demande que l'on annonce qu'il y en a
# potentiellement deux.
if ($ChoixComposants -eq 1) {
    $CommandesPosees = $CommandeCli
} else {
    $CommandesPosees = "$CommandeCli et $CommandeTui"
}
if ($ChoixPath -eq 0) {
    $ChoixPath = Demander 1 "Ajouter les commandes au PATH ? ($CommandesPosees ; cela ecrit dans le PATH utilisateur, via pipx ensurepath)" @(
        "oui",
        "non, ne touche pas a mon PATH")
}

# --- question 4 : un raccourci hors du terminal ? ----------------------------
# Story 8.8, `EPIC8-ARB-19`. Egan, 2026-09-07 : « Essaye ... on verra bien si ca
# marche ».
#
# Le garde est `Test-SurWindows`, JAMAIS `$Affichage` :
# `Test-AffichageDisponible` rend vrai sur macOS aussi, ou cette story ne fait
# rien -- macOS n'a aucun format de raccourci pour une application terminal, il
# y faudrait une application enveloppe, qui est un autre livrable. Poser la
# question la-bas serait poser une question dont la reponse ne change rien.
$RaccourciPossible = ((Test-SurWindows) -and $ChoixComposants -ne 1 -and $RaccourciFichier)
if ($RaccourciPossible -and $ChoixRaccourci -eq 0) {
    $ChoixRaccourci = Demander 1 "Ajouter un raccourci pour lancer $CommandeTui hors du terminal ? (un fichier dans $RaccourciDossier)" @(
        "oui",
        "non")
}
if ($ChoixRaccourci -eq 0) { $ChoixRaccourci = 1 }

# --- question 5 : verifier l'installation ? ----------------------------------
# On dit CE QUI SERA VERIFIE, pas seulement qu'il y aura une verification.
if ($ChoixComposants -eq 1) {
    $LibelleVerification = "$CommandeCli --version, puis ffmpeg -version"
} else {
    $LibelleVerification = "$CommandeCli --version, $CommandeTui sur le PATH, puis ffmpeg -version"
}
if ($ChoixVerification -eq 0) {
    $ChoixVerification = Demander 1 "Verifier l'installation a la fin ? ($LibelleVerification)" @("oui", "non")
}

# ============================================================================
#  3. le plan, puis son recapitulatif
# ============================================================================

# Application est le paquet PRINCIPAL du venv pipx : c'est lui qui donne son
# nom au venv et c'est dans lui qu'on greffe le reste.
if ($ChoixComposants -eq 1) {
    $Application = $PaquetCli
    $LibelleComposants = "$CommandeCli seul"
} else {
    $Application = $PaquetTui
    $LibelleComposants = "$CommandeCli + $CommandeTui"
}

$Extra = ""
if ($AvecGui) {
    $Extra = "[gui]"
    $LibelleComposants = "$LibelleComposants + extra graphique"
}

$Epingle = ""
if ($ChoixVersion -eq 2 -and $Version) { $Epingle = "==$Version" }

switch ($ChoixVersion) {
    1 { $LibelleVersion = "la derniere stable publiee" }
    2 { $LibelleVersion = $Version }
    3 { $LibelleVersion = "TestPyPI (pre-publication)" }
}

Write-Etape "Recapitulatif"
if ($MiseAJour) {
    Write-Info "operation ....... mise a jour de $InstallationExistante $VersionExistante"
} else {
    Write-Info "operation ....... installation"
}
Write-Info "composants ...... $LibelleComposants"
if ($ChoixComposants -eq 1) {
    Write-Info "paquets ......... $PaquetCli$Extra"
} else {
    Write-Info "paquets ......... $PaquetTui, avec $PaquetCli$Extra greffe dedans"
}
if ($Affichage) {
    Write-Info "apercu video .... oui, un affichage est detecte ($RoueCvAvecFenetres)"
} else {
    Write-Info "apercu video .... non, aucun affichage detecte ($RoueCvSansFenetres)"
}
Write-Info "version ......... $LibelleVersion"
if ($FfmpegPresent) {
    Write-Info "ffmpeg .......... deja present"
} elseif ($ChoixFfmpeg -eq 1) {
    Write-Info "ffmpeg .......... a installer"
} else {
    Write-Info "ffmpeg .......... laisse a ta charge"
}
if ($ChoixPath -eq 1) {
    Write-Info "PATH ............ oui, pour $CommandesPosees"
} else {
    Write-Info "PATH ............ non, le PATH n'est pas touche"
}
# Les cinq libelles PARTAGES sont repris MOT POUR MOT de install.sh ;
# le sixieme est propre a ce script (voir plus bas) : une divergence de
# recapitulatif entre les deux scripts serait invisible autrement -- la seule
# comparaison croisee qui existe ne porte que sur les lignes `pipx `.
if ($ChoixComposants -eq 1) {
    Write-Info "raccourci ....... sans objet (ligne de commande seule)"
} elseif ($IsMacOS) {
    Write-Info "raccourci ....... sans objet (pas de raccourci terminal sur macOS)"
} elseif (-not (Test-SurWindows)) {
    # SIXIEME libelle, propre a ce script, et il existe parce que la revue a
    # mesure le contraire : `-not (Test-SurWindows)` couvre macOS ET Linux,
    # si bien qu'`install.ps1` annoncait « pas de raccourci terminal sur
    # macOS » en tournant sous pwsh 7 SUR LINUX (`C3-4` / `C1-8` / `C2-9`).
    # C'est le motif faux que le cinquieme libelle avait justement ete cree
    # pour eviter, et l'exigence d'identite MOT POUR MOT avec `install.sh`
    # etait ce qui le tenait en place -- le corriger faisait rougir la
    # frontiere de parite. Celle-ci compare desormais les libelles PARTAGES,
    # et connait celui-ci comme propre a `install.ps1`.
    Write-Info "raccourci ....... sans objet (hors Windows, passer par scripts/install.sh)"
} elseif (-not $RaccourciPossible) {
    Write-Info "raccourci ....... sans objet (aucun affichage detecte)"
} elseif ($ChoixRaccourci -eq 1) {
    Write-Info "raccourci ....... oui, dans $RaccourciFichier"
} else {
    Write-Info "raccourci ....... non"
}
if ($ChoixVerification -eq 1) {
    Write-Info "verification .... $LibelleVerification"
} else {
    Write-Info "verification .... non"
}

# ============================================================================
#  4. execution
# ============================================================================

# --- winget ------------------------------------------------------------------
# Il n'est necessaire que pour installer ce qui manque. Quand Python et ffmpeg
# sont deja la, on ne va pas chercher un gestionnaire de paquets pour rien.
$BesoinDeWinget = (-not $PythonPresent) -or ((-not $FfmpegPresent) -and $ChoixFfmpeg -eq 1)
if ($BesoinDeWinget -and -not (Test-Commande "winget")) {
    Write-Etape "winget (gestionnaire de paquets Windows)"
    Write-Info "winget absent, tentative d'installation par le module officiel..."
    if ($DryRun) {
        Write-Info "[simulation] Install-Module Microsoft.WinGet.Client ; Repair-WinGetPackageManager"
    } else {
        try {
            $ProgressPreference = "SilentlyContinue"
            Install-PackageProvider -Name NuGet -Force -Scope CurrentUser | Out-Null
            Install-Module -Name Microsoft.WinGet.Client -Force -Scope CurrentUser -Repository PSGallery | Out-Null
            Repair-WinGetPackageManager -AllUsers -ErrorAction Stop
            Update-CheminSession
        } catch {
            Write-Info "Le module officiel n'a pas abouti : $($_.Exception.Message)"
        }
        if (-not (Test-Commande "winget")) {
            Stop-Avec @"
winget reste indisponible sur ce poste.
   C'est attendu sur Windows Server, les editions LTSC et certains postes
   d'entreprise. Installer les prerequis a la main, puis relancer :
     - Python >= 3.11 : https://www.python.org/downloads/windows/
                        (cocher "Add python.exe to PATH" a l'installation)
     - ffmpeg         : https://www.gyan.dev/ffmpeg/builds/ (build "essentials"),
                        puis ajouter son dossier bin\ au PATH.
   Le script reprendra ensuite tout seul a l'etape pipx.
"@
        }
    }
}

# --- Python -------------------------------------------------------------------

if (-not $PythonPresent) {
    Write-Etape "Python (>= $PythonMinimum)"
    Invoke-Etape "winget" @("install", "--id", "Python.Python.3.12", "-e",
                            "--source", "winget", "--accept-package-agreements",
                            "--accept-source-agreements") | Out-Null
    Update-CheminSession
    if ($DryRun) {
        $python = @{ Fichier = "python"; Arguments = @() }
    } else {
        $python = Get-PythonConvenable
        if (-not $python) {
            Stop-Avec "Python >= $PythonMinimum toujours introuvable apres installation.
   Fermer et rouvrir PowerShell, puis relancer ce script."
        }
        Write-Succes "Python installe"
    }
    # PYTHON N'ENTRE PAS AU RECU ICI, ET C'EST LA MEME REGLE QUE DU COTE BASH.
    # Le recu n'enregistre que ce que CE script a pose de bout en bout ; ce
    # que winget pose appartient a winget, exactement comme ce qu'`apt` pose
    # appartient a `apt` -- c'est la raison 2 d'`EPIC11-ARB-274`, et c'est
    # pourquoi `install.sh` ne note pas davantage un ffmpeg venu du
    # gestionnaire de paquets. Ce que l'issue 3 AFFICHE couvre ce cas ; le
    # recu ne le double pas.
    #
    # `Remove-SelonLeRecu` garde tout de meme sa branche `python*` : le FORMAT
    # du recu est commun aux deux scripts, et une machine peut porter les deux
    # (WSL a cote de Windows). Une entree `python` ne doit devenir un retrait
    # d'aucun cote, jamais.
}

# --- ffmpeg -------------------------------------------------------------------

if (-not $FfmpegPresent) {
    Write-Etape "ffmpeg et ffprobe"
    if ($ChoixFfmpeg -eq 1) {
        Invoke-Etape "winget" @("install", "--id", "Gyan.FFmpeg", "-e",
                                "--source", "winget", "--accept-package-agreements",
                                "--accept-source-agreements") | Out-Null
        Update-CheminSession
        if (-not $DryRun) {
            if ((Test-Commande "ffmpeg") -and (Test-Commande "ffprobe")) {
                $FfmpegPresent = $true
                Write-Succes ((ffmpeg -version 2>$null | Select-Object -First 1))
            } else {
                # Pas d'echec sec : le reste de l'installation reste utile, et
                # le bilan final redira quoi faire.
                Write-Alerte "ffmpeg/ffprobe reste introuvable dans CETTE session."
                Write-Alerte "winget a pose les binaires ; fermer et rouvrir PowerShell suffit souvent."
            }
        }
    } else {
        # Choix 2 ("non - necessite d'installer manuellement ffmpeg") : on sort
        # de l'ETAPE ffmpeg sans drame -- on dit quoi installer, et on continue.
        # Interrompre ici priverait l'utilisateur de l'installation qu'il est
        # venu chercher, alors que ffmpeg peut s'ajouter apres coup sans rien
        # refaire.
        Write-Info "Tres bien. A installer quand tu voudras, avant le premier encodage :"
        Write-Info "  winget install --id Gyan.FFmpeg -e"
        Write-Info "  ou https://www.gyan.dev/ffmpeg/builds/ (build ""essentials"")"
        Write-Info "Il faut ffmpeg ET ffprobe : certains paquets minimalistes n'ont que le premier."
    }
}

# --- pipx ---------------------------------------------------------------------

if (-not $PipxPresent) {
    Write-Etape "pipx (environnement isole pour l'application)"
    $argvPip = $python.Arguments + @("-m", "pip", "install", "--user", "pipx")
    Invoke-Etape $python.Fichier $argvPip | Out-Null
    $argvChemin = $python.Arguments + @("-m", "pipx", "ensurepath")
    Invoke-Etape $python.Fichier $argvChemin | Out-Null
    Update-CheminSession
    if (-not $DryRun -and -not (Test-Commande "pipx")) {
        Stop-Avec "pipx introuvable apres installation.
   Fermer et rouvrir PowerShell, puis relancer ce script."
    }
    Write-Succes "pipx installe"

    # LE RECU (AC2). Il n'est ecrit que dans CETTE branche : quand pipx etait
    # deja la, ce script ne l'a pas pose et n'a donc rien a reprendre. C'est la
    # difference exacte que l'issue 2 doit voir.
    #
    # La nature porte la VOIE -- `pip --user` est la seule sur Windows --,
    # parce que c'est elle qui decidera du retrait : on repasse par pip, jamais
    # par un effacement de fichier.
    $cheminDePipx = (Get-Command pipx -ErrorAction SilentlyContinue)
    if ($DryRun) {
        Write-DansLeRecu "pipx-pip-utilisateur" (Join-Path (Get-RepertoireBinPipx) "pipx.exe")
    } elseif ($cheminDePipx) {
        Write-DansLeRecu "pipx-pip-utilisateur" $cheminDePipx.Source
    }
}

# --- les paquets --------------------------------------------------------------

if ($MiseAJour) { Write-Etape "Mise a jour" } else { Write-Etape "Installation" }

# TestPyPI n'heberge pas les dependances (textual, numpy, Pillow...) : sans
# index supplementaire vers le vrai PyPI, la resolution echoue.
$ArgumentsPip = @()
if ($ChoixVersion -eq 3) {
    $ArgumentsPip = @("--pip-args=--index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple")
}

if ($MiseAJour) {
    # `--include-injected` : sans lui, pipx met a jour l'application et laisse
    # les paquets greffes -- dont `mmu-cli` -- a leur ancienne version, ce qui
    # est exactement la divergence que `mmu-tui` epingle pour l'eviter.
    $code = Invoke-Etape "pipx" (@("upgrade") + $ArgumentsPip + @("--include-injected", $Application))
    if (-not $DryRun -and $code -ne 0) { Stop-Avec "pipx n'a pas pu mettre a jour $Application." }
} elseif ($ChoixComposants -eq 1) {
    # La ligne de commande seule : `mmu-cli` est le paquet principal, donc pipx
    # expose `mmu` de lui-meme. Aucune greffe n'est necessaire.
    $code = Invoke-Etape "pipx" (@("install") + $ArgumentsPip + @("--force", "$PaquetCli$Extra$Epingle"))
    if (-not $DryRun -and $code -ne 0) { Stop-Avec "pipx n'a pas pu installer $PaquetCli$Extra$Epingle." }
} else {
    $code = Invoke-Etape "pipx" (@("install") + $ArgumentsPip + @("--force", "$PaquetTui$Epingle"))
    if (-not $DryRun -and $code -ne 0) { Stop-Avec "pipx n'a pas pu installer $PaquetTui$Epingle." }
}

# LE PIEGE PIPX, mesure le 2026-09-07. `pipx install mmu-tui` installe bien
# `mmu-cli` dans le venv -- le binaire mmu existe dans le venv -- mais pipx
# N'EXPOSE QUE LES SCRIPTS DU PAQUET PRINCIPAL : `mmu` n'arrive pas sur le
# PATH, et `pipx expose` n'y change rien. Le seul geste qui marche :
#   - `--include-apps` : c'est lui qui enregistre `mmu` sur le PATH ;
#   - `--force`        : sans lui, pipx repond "already seems to be installed"
#                        (mmu-cli EST deja la, en dependance) et ne
#                        reenregistre pas les applications.
# Retirer l'un des deux rend la commande `mmu` introuvable apres une
# installation reussie. La greffe vaut aussi apres une MISE A JOUR :
# `pipx upgrade` ne reenregistre rien.
if ($ChoixComposants -ne 1) {
    $code = Invoke-Etape "pipx" (@("inject") + $ArgumentsPip + @("--include-apps", "--force", $Application, "$PaquetCli$Extra$Epingle"))
    if (-not $DryRun -and $code -ne 0) { Stop-Avec "pipx n'a pas pu greffer $PaquetCli dans $Application." }
}

# --- la roue OpenCV, selon l'affichage detecte --------------------------------
# On REMPLACE, on n'empile pas : les deux roues livrent le meme module `cv2` et
# pip ne connait pas leur conflit. Installer la seconde par-dessus la premiere
# laisserait deux distributions se disputer les memes fichiers, et le prochain
# `pip install --upgrade` de l'une ecraserait l'autre sans un mot.
if ($Affichage) {
    Invoke-Etape "pipx" @("runpip", $Application, "uninstall", "-y", $RoueCvSansFenetres) | Out-Null
    Invoke-Etape "pipx" @("inject", "--force", $Application, $RoueCvAvecFenetres) | Out-Null
    Write-Info "Pour revenir a la roue sans fenetres :"
    Write-Info "  pipx inject --force $Application $RoueCvSansFenetres"
} else {
    Write-Info "Aucun affichage : $RoueCvSansFenetres est conservee (elle n'exige"
    Write-Info "aucune bibliotheque graphique, ce qui est ce qu'il faut sur un serveur)."
}

# --- le raccourci du menu Demarrer (story 8.8) --------------------------------
# Ecrit APRES l'installation : le chemin absolu de la commande n'existe pas
# avant. `Invoke-Etape` ne peut pas porter ce geste -- il fait
# `& $Fichier @Arguments`, un objet COM n'y passe pas --, la garde `-DryRun`
# est donc posee ici.
#
# NON MESURE DANS CE DEPOT, et il faut le dire : il n'y a pas de Windows ou
# jouer ce chemin. Ce qui est mesure de ce cote, c'est la FORME du code -- la
# presence des gardes, la symetrie des drapeaux et des libelles avec
# install.sh -- jamais l'effet. C'est le sens exact de la reserve d'Egan :
# « on verra bien si ca marche ».
if ($RaccourciPossible -and $ChoixRaccourci -eq 1) {
    # Le chemin ABSOLU : la variable PATH utilisateur n'est pas forcement
    # rechargee dans la session qui double-clique sur le raccourci.
    $CibleTui = $null
    $commande = Get-Command $CommandeTui -ErrorAction SilentlyContinue
    if ($commande) { $CibleTui = $commande.Source }
    if (-not $CibleTui) {
        $candidat = Join-Path (Get-RepertoireBinPipx) "$CommandeTui.exe"
        if (Test-Path -LiteralPath $candidat) { $CibleTui = $candidat }
    }

    if (-not $CibleTui -and -not $DryRun) {
        # Une issue NOMMEE plutot qu'un raccourci mort : un lien qui pointe
        # vers rien echoue chez l'utilisateur, longtemps apres, sans rien dire
        # de pourquoi.
        Write-Alerte "Raccourci non pose : $CommandeTui est introuvable sur cette machine."
    } elseif ($DryRun) {
        Write-Info "[simulation] ecrire $RaccourciFichier"
    } else {
        try {
            if (-not (Test-Path -LiteralPath $RaccourciDossier)) {
                New-Item -ItemType Directory -Path $RaccourciDossier -Force | Out-Null
            }
            # `WScript.Shell` est present d'origine sur Windows : rien a
            # installer pour ecrire un .lnk.
            $shell = New-Object -ComObject WScript.Shell
            $lien = $shell.CreateShortcut($RaccourciFichier)
            $lien.TargetPath = $CibleTui
            $lien.Description = "Interface terminal de mixed_media_utility"
            $lien.Save()
            Write-Succes "Raccourci pose : $RaccourciFichier"
        } catch {
            # Jamais un echec sec : le reste de l'installation reste utile, et
            # le raccourci se repose en relancant.
            Write-Alerte "Raccourci non pose ($($_.Exception.Message)). L'installation continue."
        }
    }
}
if ($ChoixPath -eq 1) {
    Invoke-Etape "pipx" @("ensurepath") | Out-Null
    Update-CheminSession
} else {
    Write-Info "PATH non modifie, comme demande."
}

# ============================================================================
#  5. bilan
# ============================================================================

Write-Etape "Termine"

if ($DryRun) {
    Write-Info "Mode simulation : rien n'a ete installe."
    exit 0
}

if ($ChoixVerification -eq 1) {
    if (Test-Commande $CommandeCli) {
        Write-Succes "$CommandeCli --version : $(& $CommandeCli --version 2>&1 | Select-Object -First 1)"
    } else {
        Write-Alerte "$CommandeCli n'est pas encore sur le PATH de CETTE session."
    }
    if ($ChoixComposants -ne 1) {
        if (Test-Commande $CommandeTui) {
            Write-Succes "$CommandeTui est sur le PATH"
        } else {
            Write-Alerte "$CommandeTui n'est pas encore sur le PATH de CETTE session."
        }
    }
    if ((Test-Commande "ffmpeg") -and (Test-Commande "ffprobe")) {
        Write-Succes ((ffmpeg -version 2>$null | Select-Object -First 1))
    } else {
        Write-Alerte "ffmpeg ou ffprobe manque : l'encodage echouera tant qu'il n'est pas la."
    }
}

Write-Host ""
Write-Host "    Lancer la ligne de commande : $CommandeCli --help"
if ($ChoixComposants -ne 1) {
    Write-Host "    Lancer l'interface terminal : $CommandeTui"
}
Write-Host ""
Write-Host "    Si une commande reste introuvable, ouvrir un NOUVEAU PowerShell."
Write-Host ""
