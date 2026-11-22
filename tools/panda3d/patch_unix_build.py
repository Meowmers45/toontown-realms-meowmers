"""Update build inputs of the pinned Panda3D fork before packaging Unix wheels."""
import sys
from pathlib import Path


def replace(path, replacements):
    source = path.read_text(encoding='utf-8')
    for old, new, count in replacements:
        if source.count(old) != count:
            raise SystemExit(f'{path}: expected {count} occurrences of {old!r}')
        source = source.replace(old, new)
    path.write_text(source, encoding='utf-8')


root = Path(sys.argv[1])
makepanda = root / 'makepanda/makepanda.py'
replace(makepanda, [
    ("    PyTargetAdd('toontown.pyd', input='libp3interrogatedb.dll')\n", '', 1),
])
replace(root / 'panda/src/toontown/marginManager.cxx', [
    ('#include <algorithm>', '#include <algorithm>\n#include <cstdlib>\n#include <random>', 1),
    ('random_shuffle(empty_cells.begin(), empty_cells.end());',
     'std::shuffle(empty_cells.begin(), empty_cells.end(), std::mt19937(std::rand()));', 2),
])
if sys.platform == 'darwin':
    replace(makepanda, [
        ('MACOSX_DEPLOYMENT_TARGET"] = "10.13"', 'MACOSX_DEPLOYMENT_TARGET"] = "11.0"', 1),
        ("'macosx-10.13-'", "'macosx-11.0-'", 1),
        ('-mmacosx-version-min=10.13', '-mmacosx-version-min=11.0', 2),
    ])
