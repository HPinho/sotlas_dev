"""Run the numeric example through a rebuilt native compiler and import resolver."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def verify_numeric_pipeline(compiler, output, example='native_numeric_pipeline', modules=('results',)):
    compiler = Path(compiler).resolve()
    output = Path(output).resolve()
    source = output / 'src'
    runtime = source / 'sotlas/runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    for module in modules:
        shutil.copyfile(ROOT / ('runtime/native/' + module + '.sotlas'), runtime / (module + '.sotlas'))
    entry = source / 'main.sotlas'
    shutil.copyfile(ROOT / ('examples/' + example + '/main.sotlas'), entry)
    environment = {'PATH': str(output / 'no-host-tools')}
    if os.name == 'nt':
        environment['SystemRoot'] = os.environ.get('SystemRoot', 'C:\\Windows')

    def run(arguments, expected=0):
        result = subprocess.run(list(map(str, arguments)), capture_output=True,
                                env=environment, timeout=30)
        if result.returncode != expected:
            raise AssertionError(f'{arguments}: exit {result.returncode}, expected {expected}; '
                                 f'stdout={result.stdout!r}; stderr={result.stderr!r}')
        return result

    run([compiler, '--check-build', source, entry])
    obj = output / 'pipeline.o'
    run([compiler, '--build-obj', obj, source, entry])
    formats = (('elf', '.elf', b'\x7fELF'), ('pe', '.exe', b'MZ'),
               ('macho', '.macho', b'\xcf\xfa\xed\xfe'))
    host = 'pe' if os.name == 'nt' else 'macho' if sys.platform == 'darwin' else 'elf'
    build = '--build-win' if host == 'pe' else '--build-mac' if host == 'macho' else '--build'
    application = output / ('application.exe' if host == 'pe' else 'application')
    run([compiler, build, application, source, entry])
    run([application], expected=42)
    for target, suffix, magic in formats:
        image = output / ('pipeline' + suffix)
        run([compiler, '--link-' + target + '-libraries', image, 'main_entry', obj])
        assert image.read_bytes().startswith(magic), target
        if target == host:
            run([image], expected=42)


def verify_text_pipeline(compiler, output):
    verify_numeric_pipeline(compiler, output, 'native_text_pipeline', ('results', 'text', 'utf8'))


if __name__ == '__main__':
    verify = verify_text_pipeline if len(sys.argv) > 3 and sys.argv[3] == 'text' else verify_numeric_pipeline
    verify(sys.argv[1], sys.argv[2])
