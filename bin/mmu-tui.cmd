@echo off
setlocal
rem Raccourci "mmu-tui" -> `python -m mixed_media_utility.tui`, sans install.
rem
rem Jumeau de `bin\mmu.cmd` (story 11.0). Fonctionne dans cmd.exe, PowerShell
rem et Git Bash sous Windows. Le chemin de src\ se calcule depuis %~dp0, la
rem position de CE fichier -- jamais depuis le repertoire courant.
rem
rem Prepend, jamais ecrase : %PYTHONPATH% deja pose survit a cet appel.
set "PYTHONPATH=%~dp0..\src;%PYTHONPATH%"

rem `Echap` emet le meme octet que le PREFIXE de toute sequence d'echappement :
rem le parseur de `textual` ne peut les distinguer qu'en attendant ESCDELAY
rem millisecondes. Le defaut vaut 100, ce qui met 100 ms de latence sur chaque
rem `Echap` -- une touche de navigation, tapee sans arret. Sous Windows, tous
rem les caracteres d'une sequence arrivent dans le MEME ReadConsoleInputW, donc
rem le delai ne protege rien localement.
rem
rem Un ESCDELAY pose par l'operateur SURVIT : on ne pose le notre que s'il est
rem absent.
if not defined ESCDELAY set "ESCDELAY=25"
python -m mixed_media_utility.tui %*
exit /b %ERRORLEVEL%
