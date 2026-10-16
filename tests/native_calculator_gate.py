"""Process-level test adapter. Calculator parsing/formatting lives in Sotlas."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def verify_calculator(compiler, output):
    compiler = Path(compiler).resolve()
    output = Path(output).resolve()
    source = output / 'src'
    (source / 'calculator').mkdir(parents=True, exist_ok=True)
    (source / 'sotlas/runtime').mkdir(parents=True, exist_ok=True)
    platform = 'windows' if os.name == 'nt' else 'darwin' if sys.platform == 'darwin' else 'linux'
    suffix = '.exe' if os.name == 'nt' else ''
    build = '--build-win' if os.name == 'nt' else '--build-mac' if sys.platform == 'darwin' else '--build'
    for original, target in (
        ('examples/calculator/src/calculator/main.sotlas', 'calculator/main.sotlas'),
        (f'examples/calculator/platform/{platform}.sotlas', 'calculator/platform.sotlas'),
        ('runtime/native/calculator.sotlas', 'sotlas/runtime/calculator.sotlas'),
        ('tests/native/calculator/model.sotlas', 'calculator/model.sotlas'),
    ):
        shutil.copyfile(ROOT / original, source / target)
    environment = {'PATH': str(output / 'no-host-tools')}
    if os.name == 'nt':
        environment['SystemRoot'] = os.environ.get('SystemRoot', 'C:\\Windows')

    def run(arguments, expected=0, input_data=b'', stdout=None):
        result = subprocess.run(list(map(str, arguments)), input=input_data, capture_output=True,
                                env=environment, timeout=30)
        if result.returncode != expected or (stdout is not None and result.stdout != stdout):
            raise AssertionError(f'{arguments}: exit {result.returncode}, expected {expected}; '
                                 f'stdout={result.stdout!r}; stderr={result.stderr!r}')
        return result

    for name in ('model', 'main'):
        entry = source / 'calculator' / f'{name}.sotlas'
        image = output / (name + suffix)
        run([compiler, '--check-build', source, entry])
        run([compiler, build, image, source, entry])
    run([output / ('model' + suffix)], expected=42)
    application = output / ('main' + suffix)
    cases = [
        (b'2+3*4\n(2+3)*4\n-1.25+2.5\n\t\v\f1/3\r\n', 0, b'14\n20\n1.25\n0.333333\n'),
        (b'1/0\n42\n', 2, b'error: division by zero at byte 1\n42\n'),
        (b'1+\n(2\n', 2, b'error: expected a number or opening parenthesis at byte 2\nerror: expected closing parenthesis at byte 2\n'),
        (b'1e3\n', 2, b'error: unexpected trailing input at byte 1\n'),
        (b'1\x00+2\n', 2, b'error: unexpected trailing input at byte 1\n'),
        (b'\xff\n', 2, b'error: expected a number or opening parenthesis at byte 0\n'),
        (b' '*1023 + b'1\r\n', 0, b'1\n'),
        (b'0'*1025 + b'\n42\n', 2, b'error: input exceeds 1024 bytes or has invalid storage at byte 1024\n42\n'),
        (b'\n', 2, b'error: expected a number or opening parenthesis at byte 0\n'),
        (b'', 0, b''),
        (b'40+2', 0, b'42\n'),
        ((b'0.1+0.2\n'*100), 0, b'0.3\n'*100),
    ]
    for data, expected, text in cases:
        run([application], expected=expected, input_data=data, stdout=text)
    print(f'Calculator: native model and {len(cases)} CLI cases passed ({platform}).')


if __name__ == '__main__':
    verify_calculator(sys.argv[1], sys.argv[2])
