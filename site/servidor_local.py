#!/usr/bin/env python3
"""Sitio de auditoría FTDI, sólo localhost. API local sin conexión con ECU por defecto."""
import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs

from ftdi_banco import ports_list, run_loopback

HOME = Path(__file__).resolve().parent
STATE = HOME / 'datos' / 'estado.json'
EVID = HOME / 'evidencias'
BACKUPS = HOME / 'backups'
LOCK = threading.Lock()
VALID_UPLOADS = {'.csv','.json','.log','.txt','.md','.png','.jpg','.jpeg','.pdf','.webp'}
MAX_UPLOAD = 12 * 1024 * 1024

class Handler(BaseHTTPRequestHandler):
    server_version = 'BancoFTDI/1.0'
    def log_message(self, fmt, *args):
        print('[%s] %s' % (datetime.now().strftime('%H:%M:%S'), fmt % args))

    def headers_security(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")

    def send_json(self, status, data):
        bs = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(bs)))
        self.headers_security()
        self.end_headers()
        self.wfile.write(bs)

    def read_bytes(self, max_size=MAX_UPLOAD):
        try: length = int(self.headers.get('Content-Length','-1'))
        except ValueError: raise ValueError('Longitud de datos inválida')
        if length < 0 or length > max_size: raise ValueError('Longitud supera límite permitido')
        return self.rfile.read(length)

    def path_file(self, raw):
        norm = unquote(raw).split('?',1)[0].lstrip('/')
        if norm == '': norm='index.html'
        check = (HOME / norm).resolve()
        if HOME not in check.parents and check != HOME: return None
        if not check.is_file(): return None
        if check.suffix.lower() in {'.py','.bat','.ps1','.fls','.bin'}: return None
        if '/backups/' in check.as_posix() or '/datos/' in check.as_posix(): return None
        return check

    def do_GET(self):
        raw=urlsplit(self.path).path
        if raw=='/api/estado':
            try: self.send_json(200,json.loads(STATE.read_text(encoding='utf8')))
            except Exception as e: self.send_json(500,{'error':str(e)})
            return
        if raw=='/api/puertos': self.send_json(200,ports_list());return
        if raw=='/api/salud': self.send_json(200,{'modo':'local','persistencia':'JSON en disco','sin_ecu':True});return
        f=self.path_file(raw)
        if f is None: self.send_error(404,'No encontrado');return
        ctype=mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
        size=f.stat().st_size
        self.send_response(200)
        self.send_header('Content-Type',ctype+('; charset=utf-8' if ctype.startswith(('text/','application/javascript','application/json')) else ''))
        self.send_header('Content-Length',str(size))
        self.headers_security()
        self.end_headers()
        with f.open('rb') as stream: shutil.copyfileobj(stream,self.wfile)

    def do_POST(self):
        path=urlsplit(self.path).path
        try:
            if path=='/api/estado':
                raw=self.read_bytes(max_size=4*1024*1024)
                data=json.loads(raw.decode('utf-8'))
                if not isinstance(data,dict) or data.get('schema')!=3 or not isinstance(data.get('pruebas'),list) or not isinstance(data.get('versiones'),list):
                    raise ValueError('Estructura de estado no válida')
                with LOCK:
                    # Backup diario adicional + anterior antes de sobreescritura (máx. una copia por 10 min)
                    BACKUPS.mkdir(exist_ok=True)
                    latest=sorted(BACKUPS.glob('estado_*.json'),key=lambda x:x.stat().st_mtime,reverse=True)
                    if STATE.exists() and (not latest or (datetime.now().timestamp()-latest[0].stat().st_mtime)>600):
                        shutil.copy2(STATE,BACKUPS/('estado_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'))
                        all_backups=sorted(BACKUPS.glob('estado_*.json'),key=lambda x:x.stat().st_mtime,reverse=True)
                        for old in all_backups[30:]: old.unlink(missing_ok=True)
                    temp=STATE.with_suffix('.json.tmp')
                    temp.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
                    os.replace(temp,STATE)
                self.send_json(200,{'guardado':True,'pruebas':len(data['pruebas']),'bytes':STATE.stat().st_size})
                return
            if path=='/api/subir':
                q=parse_qs(urlsplit(self.path).query)
                filename=Path(unquote(q.get('nombre',['evidencia.txt'])[0])).name
                filename=re.sub(r'[^a-zA-Z0-9_.-]','_',filename)[:140]
                ext=Path(filename).suffix.lower()
                if ext not in VALID_UPLOADS:raise ValueError('Formato no admitido; solo CSV, JSON, LOG, TXT, MD, PNG, JPG, PDF y WEBP')
                content=self.read_bytes()
                if not content:raise ValueError('El archivo está vacío')
                EVID.mkdir(exist_ok=True)
                target=EVID/filename
                if target.exists():
                    filename=datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+filename
                    target=EVID/filename
                target.write_bytes(content)
                self.send_json(200,{'nombre':filename,'ruta':'evidencias/'+filename,'sha256':hashlib.sha256(content).hexdigest(),'tamano':len(content)})
                return
            if path=='/api/banco':
                body=json.loads(self.read_bytes(3000).decode('utf-8'))
                if body.get('modo')=='enumerar': self.send_json(200,ports_list());return
                if body.get('modo')!='loopback':raise ValueError('Solo se permite enumeración o loopback físico')
                if not body.get('sin_ecu') or not body.get('fixture_ttl'):
                    raise ValueError('Debes confirmar cable aislado sin ECU y circuito TTL físicamente validado')
                self.send_json(200,run_loopback(str(body.get('puerto','')),int(body.get('baud',10400)),int(body.get('intentos',10)),True,True))
                return
            self.send_json(404,{'error':'Ruta no encontrada'})
        except Exception as e:
            self.send_json(400,{'error':str(e)})


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--puerto',type=int,default=8765)
    parser.add_argument('--sin-navegador',action='store_true')
    args=parser.parse_args()
    with ThreadingHTTPServer(('127.0.0.1',args.puerto),Handler) as s:
        url=f'http://127.0.0.1:{args.puerto}'
        print('SITE FTDI disponible en:',url,flush=True)
        print('Sólo localhost. Datos: datos/estado.json. Pulsar Ctrl+C para cerrar.',flush=True)
        if not args.sin_navegador:
            threading.Timer(0.7, lambda:webbrowser.open(url)).start()
        try:s.serve_forever()
        except KeyboardInterrupt:pass

if __name__=='__main__':main()
