# ADF LAB — Banco de investigación de software embebido

Proyecto de desarrollo real que integra aplicación local con backend Python, interfaz JavaScript, matriz de pruebas, control de evidencias y modelos de estados con tests reproducibles.

**Código real; datos públicos anonimizados.** Esta copia no contiene firmware Bosch, archivos BIN/FLS, registros del vehículo, series de hardware, mediciones reales ni archivos de diagnóstico.

## Ejecutar aplicación

~~~powershell
cd site
python servidor_local.py --sin-navegador
~~~

Abrir http://127.0.0.1:8765.

## Ejecutar pruebas

~~~powershell
python work/build_release_core_20261102.py
python -m unittest discover -s work -p "test_*.py" -v
python -m unittest discover -s tests -p "test_*.py" -v
node --check site/assets/app.js
node --check site/assets/seed.js
~~~

Estas pruebas no utilizan el automóvil ni flashean la ECU. El código C166 generado es una pieza aislada de prueba para un intérprete limitado; no debe confundirse con un firmware funcional.

## Estado y límites

- La aplicación local y los modelos son software comprobable.
- El estado público del panel es demostrativo, no resultado de una campaña nueva de pruebas físicas.
- La exclusividad de SRAM, los accesos indirectos, DPP efectivo y temporización de ISR siguen pendientes de validación completa.
- La conexión activa de FTDI exige fixture TTL aislado y validación eléctrica previa.
- El proyecto puede utilizar Git incluido en GitHub Desktop. Se conserva un historial auténtico, sin commits retroactivos ficticios.

Este proyecto se presenta como software de investigación, no como una modificación de ECU lista para flashear.
