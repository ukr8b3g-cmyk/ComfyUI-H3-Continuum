# Temporary transport runner; excluded from the resulting source commit.
import base64
import hashlib
from pathlib import Path
import sys
import zlib

folder = Path(__file__).parent / 'loader-payload'
parts = [(folder / f'{index:02}.txt').read_text().strip() for index in range(8)]
# Correct two known transcription insertions; the full-source digest below
# verifies the reconstructed program against the locally validated original.
parts[5] = parts[5].replace('+4Y8c8fv', '+4Y8fv').replace('5Off+v30', '5Off+30')
source = zlib.decompress(base64.b64decode(''.join(parts), validate=True))
expected = 'ca8760b9fa97a309fe9c668d562ef37b95d1fdef50535c99a9eb5752dff5d12d'
assert hashlib.sha256(source).hexdigest() == expected
print('Verified repair source SHA256:', expected, flush=True)
if '--check' not in sys.argv:
    exec(compile(source, '<verified-loader-repair>', 'exec'))
