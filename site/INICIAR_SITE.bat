@echo off
setlocal
cd /d "%~dp0"
echo ===========================
echo  ADF / BANCO FTDI - C166
 echo ===========================
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 servidor_local.py
) else (
  where python >nul 2>&1
  if %errorlevel%==0 (
    python servidor_local.py
  ) else (
    echo ERROR: No se encuentra Python 3.
    echo Instala Python 3 y marca la opcion de anadirlo al PATH.
    pause
  )
)
endlocal
