@echo off
title Aether - Stopping...
echo Stopping all Aether services...
taskkill /f /fi "WINDOWTITLE eq Aether Backend*" > nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Aether Voice*" > nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Aether Frontend*" > nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Aether Float*" > nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Aether Clipboard*" > nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Aether Setup*" > nul 2>&1
echo Aether stopped.
timeout /t 2 /nobreak > nul
exit
