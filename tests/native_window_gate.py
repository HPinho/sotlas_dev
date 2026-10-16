"""Windows process adapter: native Sotlas owns the platform implementation."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def verify_window(compiler, output):
    if os.name != 'nt':
        raise RuntimeError('Windows desktop execution required')
    compiler = Path(compiler).resolve()
    output = Path(output).resolve()
    source = output / 'src'
    (source / 'sotlas/runtime').mkdir(parents=True, exist_ok=True)
    (source / 'probe').mkdir(parents=True, exist_ok=True)
    for original, target in (
        ('runtime/native/window_windows.sotlas', 'sotlas/runtime/window_windows.sotlas'),
        ('tests/native/window_windows/smoke.sotlas', 'probe/smoke.sotlas'),
        ('examples/native_window/src/probe/main.sotlas', 'probe/main.sotlas'),
    ):
        shutil.copyfile(ROOT / original, source / target)
    environment = {'PATH': str(output / 'no-host-tools'),
                   'SystemRoot': os.environ.get('SystemRoot', 'C:\\Windows')}

    def run(arguments, expected=0):
        result = subprocess.run(list(map(str, arguments)), capture_output=True,
                                env=environment, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode != expected:
            raise AssertionError(f'{arguments}: exit {result.returncode}, expected {expected}; {result.stderr!r}')

    for name in ('main', 'smoke'):
        entry = source / 'probe' / f'{name}.sotlas'
        run([compiler, '--check-build', source, entry])
        run([compiler, '--build-win', output / f'{name}.exe', source, entry])
    run([output / 'smoke.exe'], 42)
    # A Windows-only foreign ABI object must remain rejected by other targets.
    sentinel = b'preserve existing non-Windows image'
    image = output / 'rejected-image'
    image.write_bytes(sentinel)
    run([compiler, '--build-mac', image, source, source / 'probe/main.sotlas'], 9)
    if image.read_bytes() != sentinel:
        raise AssertionError('Rejected cross-target build replaced an existing image')
    print('Windows GUI: native lifecycle, drawing, resize, input, cleanup and target rejection passed.')


if __name__ == '__main__':
    verify_window(sys.argv[1], sys.argv[2])
