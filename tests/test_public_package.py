import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/"site"

class PublicPackageTests(unittest.TestCase):
    def test_demonstration_state(self):
        s=json.loads((SITE/"datos/estado.json").read_text(encoding="utf-8"))
        self.assertEqual(s["schema"],3)
        self.assertTrue(s["pruebas"])
        self.assertEqual(s["evidencias"],[])
        self.assertIn("DEMO",s["project"]["titulo"])
        self.assertTrue(all(t["estado"]=="pendiente" for t in s["pruebas"]))

    def test_server_scoped_file_serving(self):
        sys.path.insert(0,str(SITE))
        try:
            spec=importlib.util.spec_from_file_location("adf_server",SITE/"servidor_local.py")
            mod=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            handler=object.__new__(mod.Handler)
            self.assertEqual(handler.path_file("/"),SITE/"index.html")
            for path in ("/datos/estado.json","/backups/secret.txt","/original.fls","/secret.bin","/../../Windows/win.ini"):
                self.assertIsNone(handler.path_file(path),path)
        finally:
            sys.path.remove(str(SITE))

    def test_no_proprietary_firmware_or_captures(self):
        banned={".bin",".fls",".hex",".eep",".epr",".mpc",".p12",".pem",".key",".exe",".dll",".asar",".csv"}
        found=[]
        for p in ROOT.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in banned: continue
            rel=p.relative_to(ROOT).as_posix()
            # A synthetic isolated core is generated on demand. It is never published.
            if rel.startswith("work/release_core_20261102/"): continue
            found.append(rel)
        self.assertFalse(found,found)

    def test_private_identifiers_removed(self):
        for p in (SITE/"datos/estado.json",SITE/"assets/seed.js",SITE/"index.html"):
            content=p.read_text(encoding="utf-8").lower()
            for pattern in ("a50285bi","3dea8f4e981ef25c","c:\\users\\usuari",
                            "624557849","1595antonio@gmail.com"):
                self.assertNotIn(pattern,content,str(p))

if __name__=="__main__":
    unittest.main()
