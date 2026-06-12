@echo off
echo ===== LISTENING ports 5000-5099 ===== > "C:\Users\louisb\Documents\GitHub\Lumamask\_ports.txt"
netstat -ano | findstr LISTENING | findstr ":50" >> "C:\Users\louisb\Documents\GitHub\Lumamask\_ports.txt"
echo. >> "C:\Users\louisb\Documents\GitHub\Lumamask\_ports.txt"
echo ===== python processes ===== >> "C:\Users\louisb\Documents\GitHub\Lumamask\_ports.txt"
tasklist | findstr /i python >> "C:\Users\louisb\Documents\GitHub\Lumamask\_ports.txt"
echo DONE
