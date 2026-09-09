# Installe la commande "mmu" pour l'utilisateur courant, sans pip install.
#
# Ce script ne fait qu'une chose: ajouter <depot>\bin au PATH utilisateur
# (registre Windows, persistant entre sessions), de facon idempotente --
# relancable sans dupliquer l'entree. Le raccourci lui-meme -- bin\mmu.cmd --
# porte deja tout ce qu'il faut (PYTHONPATH calcule depuis sa propre position,
# cf. son en-tete), et fonctionne dans cmd.exe, PowerShell et Git Bash.
#
# A lancer UNE FOIS, depuis PowerShell: .\scripts\install-mmu.ps1
# (si le lancement est bloque par la politique d'execution: powershell -ExecutionPolicy Bypass -File scripts\install-mmu.ps1)

$repoRoot = Split-Path -Parent $PSScriptRoot
$binDir = Join-Path $repoRoot "bin"

if (-not (Test-Path (Join-Path $binDir "mmu.cmd"))) {
    Write-Error "bin\mmu.cmd introuvable sous $binDir. Depot incomplet ?"
    exit 1
}

$currentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$entries = @()
if ($currentUserPath) {
    $entries = $currentUserPath -split ';' | Where-Object { $_ -ne '' }
}

if ($entries -contains $binDir) {
    Write-Host "Deja installe: $binDir est deja present dans le PATH utilisateur."
} else {
    $newPath = if ($currentUserPath) { "$currentUserPath;$binDir" } else { $binDir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Installe: $binDir ajoute au PATH utilisateur."
}

Write-Host ""
Write-Host "Ouvre un NOUVEAU terminal (PowerShell ou cmd.exe -- les fenetres deja"
Write-Host "ouvertes ne voient pas le changement), puis teste:"
Write-Host "    mmu --help"
