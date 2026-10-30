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


def verify_text_buffer(compiler, output):
    verify_numeric_pipeline(compiler, output, 'native_text_buffer', ('results', 'text', 'unicode', 'utf8_buffer'))


def verify_arena_text(compiler, output):
    verify_numeric_pipeline(compiler, output, 'native_arena_text', ('results', 'managed', 'text', 'unicode', 'utf8_buffer', 'arena_text'))


def verify_pool_text(compiler, output):
    verify_numeric_pipeline(compiler, output, 'native_pool_text',
                            ('results', 'managed', 'text', 'unicode', 'utf8_buffer', 'pool', 'pool_text'))


def verify_config_map(compiler, output):
    verify_numeric_pipeline(compiler, output, 'native_config_map',
                            ('results', 'managed', 'text', 'unicode', 'utf8_buffer', 'pool', 'pool_text', 'text_map'))


def verify_record_storage(compiler, output):
    verify_numeric_pipeline(compiler, output, 'native_record_storage', ('managed', 'pool'))


def verify_projected_storage(compiler, output):
    verify_numeric_pipeline(compiler, output, 'native_projected_storage', ('managed', 'pool'))


def verify_layout_queries(compiler, output):
    verify_numeric_pipeline(compiler, output, 'native_layout_queries', ('managed', 'pool'))


if __name__ == '__main__':
    choices = {'layout': verify_layout_queries, 'places': verify_projected_storage, 'records': verify_record_storage, 'map': verify_config_map, 'pool': verify_pool_text, 'arena': verify_arena_text, 'buffer': verify_text_buffer, 'text': verify_text_pipeline}
    verify = choices.get(sys.argv[3] if len(sys.argv) > 3 else '', verify_numeric_pipeline)
    verify(sys.argv[1], sys.argv[2])
