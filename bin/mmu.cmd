@echo off
setlocal
rem Raccourci "mmu" -> `python -m mixed_media_utility.cli`, sans installation pip.
rem
rem Fonctionne dans cmd.exe, PowerShell et Git Bash sous Windows (les trois
rem retrouvent un .cmd sur PATH quand on tape "mmu"). Le chemin de src/ se
rem calcule depuis %~dp0, la position de CE fichier -- jamais depuis le
rem repertoire courant -- pour marcher qu'on l'appelle d'ou que ce soit une
rem fois bin\ ajoute au PATH (voir scripts\install-mmu.ps1).
set "PYTHONPATH=%~dp0..\src;%PYTHONPATH%"
python -m mixed_media_utility.cli %*
exit /b %ERRORLEVEL%
