# Temporary transport runner; excluded from the resulting source commit.
import base64
import hashlib
from pathlib import Path
import sys
import zlib

folder = Path(__file__).parent / 'loader-payload'
parts = [(folder / f'{index:02}.txt').read_text().strip() for index in range(8)]
# Correct two known transcription insertions. Verify the complete source.
parts[5] = parts[5].replace('+4Y8c8fv', '+4Y8fv').replace('5Off+v30', '5Off+30')
source = zlib.decompress(base64.b64decode(''.join(parts), validate=True))
assert hashlib.sha256(source).hexdigest() == 'ca8760b9fa97a309fe9c668d562ef37b95d1fdef50535c99a9eb5752dff5d12d'
source = source.decode('utf-8')
old = "write('README.md',s)"
new = """updated_prefixes = (
    'V3.8X2 ships `H3DecodeCacheHelper`',
    'The package registers ten node IDs,',
    '- **H3 Continuum Load Audio** (legacy',
    '- **H3 Continuum Load Video** (legacy',
)
s = ''.join(line.rstrip() + '\\n' if line.startswith(updated_prefixes) else line
            for line in s.splitlines(keepends=True))
write('README.md',s)"""
assert source.count(old) == 1
source = source.replace(old, new)
expected = 'a16e2dca892c1a4520418d859a3c22b43fcf48190afa1ff9cfad5175567c60dc'
assert hashlib.sha256(source.encode()).hexdigest() == expected
print('Verified repair source SHA256:', expected, flush=True)
if '--check' not in sys.argv:
    exec(compile(source, '<verified-loader-repair>', 'exec'))
