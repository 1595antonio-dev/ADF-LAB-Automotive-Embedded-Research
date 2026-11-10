import importlib.util
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

SITE=Path(__file__).resolve().parents[1]/"site"

class LocalServerTests(unittest.TestCase):
    def test_local_read_only_api(self):
        sys.path.insert(0,str(SITE))
        try:
            spec=importlib.util.spec_from_file_location("adf_test_server",SITE/"servidor_local.py")
            mod=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            server=ThreadingHTTPServer(("127.0.0.1",0),mod.Handler)
            th=threading.Thread(target=server.serve_forever,daemon=True)
            th.start()
            try:
                base="http://127.0.0.1:%d"%server.server_port
                with urllib.request.urlopen(base+"/api/salud",timeout=3) as response:
                    self.assertEqual(response.status,200)
                    self.assertTrue(json.load(response)["sin_ecu"])
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(base+"/datos/estado.json",timeout=3)
                self.assertEqual(error.exception.code,404)
                error.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                th.join(timeout=2)
        finally:
            sys.path.remove(str(SITE))

if __name__=="__main__":
    unittest.main()
