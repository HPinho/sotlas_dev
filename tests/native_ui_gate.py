"""Native UI model and Windows renderer process gates; no UI implementation here."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def verify_ui(compiler, output):
    compiler = Path(compiler).resolve()
    output = Path(output).resolve()
    source = output / 'src'
    (source / 'sotlas/runtime').mkdir(parents=True, exist_ok=True)
    (source / 'calculator_app').mkdir(parents=True, exist_ok=True)
    for name in ('ui', 'ui_windows', 'window_windows', 'calculator', 'unicode'):
        shutil.copyfile(ROOT / f'runtime/native/{name}.sotlas', source / f'sotlas/runtime/{name}.sotlas')
    for name in ('main', 'model'):
        shutil.copyfile(ROOT / f'examples/graphical_calculator/src/calculator_app/{name}.sotlas',
                        source / f'calculator_app/{name}.sotlas')
    shutil.copyfile(ROOT / 'tests/native/ui/model.sotlas', source / 'calculator_app/tests.sotlas')
    shutil.copyfile(ROOT / 'tests/native/ui/render.sotlas', source / 'calculator_app/render_tests.sotlas')
    shutil.copyfile(ROOT / 'tests/native/ui/unicode.sotlas', source / 'calculator_app/unicode_tests.sotlas')
    environment = {'PATH': str(output / 'no-host-tools')}
    windows = os.name == 'nt'
    if windows:
        environment['SystemRoot'] = os.environ.get('SystemRoot', 'C:\\Windows')
    build = '--build-win' if windows else '--build-mac' if sys.platform == 'darwin' else '--build'
    suffix = '.exe' if windows else ''

    def run(arguments, expected=0):
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if windows else {}
        result = subprocess.run(list(map(str, arguments)), env=environment,
                                capture_output=True, timeout=30, **options)
        if result.returncode != expected:
            raise AssertionError(f'{arguments}: exit {result.returncode}, expected {expected}; {result.stderr!r}')

    names = ('tests', 'unicode_tests', 'render_tests', 'main') if windows else ('tests', 'unicode_tests')
    for name in names:
        entry = source / f'calculator_app/{name}.sotlas'
        image = output / (name + suffix)
        run([compiler, '--check-build', source, entry])
        run([compiler, build, image, source, entry])
        if name != 'main':
            run([image], 42)
    print('Native UI model passed' + ('; Windows render/cleanup gate passed.' if windows else '.'))


if __name__ == '__main__':
    verify_ui(sys.argv[1], sys.argv[2])
