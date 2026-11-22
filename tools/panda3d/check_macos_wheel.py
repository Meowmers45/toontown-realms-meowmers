"""Reject a wheel with the wrong architecture or native code requiring macOS > 11."""
import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile


wheel, arch = Path(sys.argv[1]), sys.argv[2]
tag = f'macosx_11_0_{arch}'
if not wheel.name.endswith(f'-{tag}.whl'):
    raise SystemExit(f'Expected platform tag {tag}: {wheel.name}')

with ZipFile(wheel) as archive, TemporaryDirectory() as temp:
    archive.extractall(temp)
    checked = 0
    for path in Path(temp).rglob('*'):
        if not path.is_file():
            continue
        description = subprocess.check_output(['file', '-b', str(path)], text=True)
        if 'Mach-O' not in description:
            continue
        subprocess.run(['lipo', str(path), '-verify_arch', arch], check=True)
        commands = subprocess.check_output(['otool', '-arch', arch, '-l', str(path)], text=True)
        minimums = re.findall(
            r'cmd LC_BUILD_VERSION\s+cmdsize \d+\s+platform (?:1|macos)\s+minos ([\d.]+)'
            r'|cmd LC_VERSION_MIN_MACOSX\s+cmdsize \d+\s+version ([\d.]+)',
            commands, flags=re.IGNORECASE,
        )
        if not minimums or any(tuple(map(int, (a or b).split('.') + ['0', '0']))[:3] > (11, 0, 0)
                               for a, b in minimums):
            raise SystemExit(f'{path.name}: unsupported or missing macOS target {minimums}')
        checked += 1
    if not checked:
        raise SystemExit('No Mach-O binaries found in the wheel')
    print(f'Checked macOS deployment versions and {arch} in {checked} Mach-O binaries.')
