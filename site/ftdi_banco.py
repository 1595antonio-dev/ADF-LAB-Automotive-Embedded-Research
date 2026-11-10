#!/usr/bin/env python3
"""Prueba FTDI de bajo riesgo: SOLO lazo UART TTL aislado y sin ECU.

No emula el C166, no verifica K-Line 12 V ni SID 0x3D.
Requiere pyserial para usar puerto: python -m pip install pyserial
"""
import argparse
import csv
import hashlib
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
EVID = BASE / 'evidencias'
EVID.mkdir(exist_ok=True)


def ports_list():
    try:
        from serial.tools import list_ports
    except ImportError:
        return {'disponible': False, 'mensaje': 'No está instalado pyserial. Ejecuta: py -m pip install pyserial', 'puertos': []}
    return {'disponible': True, 'puertos': [
        {'dispositivo': p.device, 'descripcion': p.description,
         'hwid': p.hwid, 'serial': p.serial_number or '',
         'vid': f'{p.vid:04X}' if p.vid is not None else '',
         'pid': f'{p.pid:04X}' if p.pid is not None else ''}
        for p in list_ports.comports()]}


def run_loopback(port: str, baud: int, attempts: int, no_ecu: bool, ttl_fixture: bool):
    if not (no_ecu and ttl_fixture):
        raise ValueError('Requiere confirmación explícita: sin ECU y lazo TTL físicamente verificado.')
    if not port or len(port) > 80 or any(c in port for c in '\n\r\x00'):
        raise ValueError('Puerto inválido')
    if baud not in (9600, 10400, 115200):
        raise ValueError('Baudios no permitidos en el ensayo')
    if not (1 <= attempts <= 100):
        raise ValueError('Repeticiones fuera de 1..100')
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError('Falta pyserial: py -m pip install pyserial') from exc

    rows = []
    with serial.Serial(port=port, baudrate=baud, bytesize=8, parity='N', stopbits=1,
                       timeout=0.55, write_timeout=0.55) as sp:
        # No cambiar manualmente DTR/RTS o niveles de K-Line: solo transferencia UART
        for n in range(attempts):
            payload = bytes([0x55, 0xAA, n % 256, 0x00, 0xFF, 0x7E, 0x81])
            sp.reset_input_buffer()
            t0 = time.perf_counter_ns()
            sp.write(payload)
            sp.flush()
            received = sp.read(len(payload))
            millis = round((time.perf_counter_ns() - t0) / 1e6, 3)
            rows.append({
                'muestra': n + 1, 'tx_hex': payload.hex(' ').upper(),
                'rx_hex': received.hex(' ').upper(), 'tx_bytes': len(payload),
                'rx_bytes': len(received), 'igual': int(received == payload),
                'latencia_ms': millis,
            })
            time.sleep(0.015)
    ok = sum(v['igual'] for v in rows)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = f'FTDI_LOOPBACK_TTL_SOLO_CABLE_{stamp}.csv'
    dest = EVID / fname
    with dest.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    latency = [v['latencia_ms'] for v in rows]
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    return {
        'prueba': 'FTDI loopback UART TTL aislado', 'puerto': port, 'baudios': baud,
        'ensayos': attempts, 'correctos': ok, 'errores': attempts - ok,
        'latencia_min_ms': round(min(latency), 3),
        'latencia_mediana_ms': round(statistics.median(latency), 3),
        'latencia_max_ms': round(max(latency), 3),
        'archivo': fname, 'sha256': sha, 'tamano': dest.stat().st_size,
        'limites': 'Solo UART de cable FTDI; no mide temporización ISR/PEC de ECU ni confirma bus K-Line.',
        'satisfactorio': ok == attempts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--listar', action='store_true')
    parser.add_argument('--loopback', action='store_true')
    parser.add_argument('--puerto', default='')
    parser.add_argument('--baudios', type=int, default=10400)
    parser.add_argument('--repeticiones', type=int, default=10)
    parser.add_argument('--sin-ecu', action='store_true')
    parser.add_argument('--ttl-confirmado', action='store_true')
    a = parser.parse_args()
    if a.listar:
        result = ports_list()
    elif a.loopback:
        result = run_loopback(a.puerto, a.baudios, a.repeticiones, a.sin_ecu, a.ttl_confirmado)
    else:
        parser.error('Indica --listar o --loopback con las confirmaciones de seguridad.')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
