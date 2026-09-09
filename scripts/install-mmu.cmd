@echo off
rem Lance install-mmu.ps1 sans se heurter a la politique d'execution PowerShell
rem par defaut de Windows (Restricted), qui bloque tout script .ps1 local non
rem signe. -ExecutionPolicy Bypass ne s'applique qu'AU PROCESS powershell.exe
rem lance ici: pas de droits admin requis, aucun changement permanent, aucun
rem effet sur les autres terminaux.
rem
rem Utilisable en double-clic (Explorateur Windows) ou depuis cmd.exe / PowerShell.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-mmu.ps1"
echo.
pause
endlocal
