"""Los assets estaticos vendoreados no pueden referenciar sourcemaps ausentes.

``collectstatic`` con ``CompressedManifestStaticFilesStorage`` (el backend de
produccion) reescribe cada ``sourceMappingURL`` y lanza ``MissingFileError`` si
el archivo referenciado no existe. Un bundle minificado copiado sin su ``.map``
rompe el deploy en el ultimo paso, despues de aplicar migraciones, asi que el
control vive aca y no en el servidor.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BASE_DIR = Path(settings.BASE_DIR)

# Mismos comentarios que post-procesa HashedFilesMixin.patterns.
SOURCE_MAP_REFERENCE_PATTERNS = {
    '.js': re.compile(r'(?m)^//# (?-i:sourceMappingURL)=(?P<url>.*)$'),
    '.css': re.compile(r'(?m)^/\*#[ \t](?-i:sourceMappingURL)=(?P<url>.*)[ \t]*\*/$'),
}

EXTERNAL_PREFIXES = ('data:', 'http:', 'https:', '//')


class StaticSourceMapReferenceTests(SimpleTestCase):
    def test_every_source_map_reference_resolves(self):
        static_root = BASE_DIR / 'static'
        scanned = 0
        for path in static_root.rglob('*'):
            pattern = SOURCE_MAP_REFERENCE_PATTERNS.get(path.suffix)
            if pattern is None or not path.is_file():
                continue
            scanned += 1
            content = path.read_text(encoding='utf-8', errors='ignore')
            for match in pattern.finditer(content):
                url = match.group('url').strip()
                if not url or url.startswith(EXTERNAL_PREFIXES):
                    continue
                target = (path.parent / url).resolve()
                self.assertTrue(
                    target.is_file(),
                    msg=(
                        f'{path.relative_to(BASE_DIR)} referencia {url}, que no existe: '
                        'collectstatic falla en produccion. Quite el comentario '
                        'sourceMappingURL del asset vendoreado.'
                    ),
                )
        # Guarda contra un recorrido vacio: el arbol trae decenas de .js/.css.
        self.assertGreater(scanned, 50)
