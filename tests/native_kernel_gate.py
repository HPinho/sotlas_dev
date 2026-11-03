"""Native kernel image, rejection and optional required QEMU boot integration."""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def verify_kernel_image(compiler,output,run_qemu=False):
    compiler=Path(compiler).resolve();output=Path(output).resolve()
    environment={'PATH':str(output/'no-host-tools')}
    if os.name=='nt':environment['SystemRoot']=os.environ.get('SystemRoot','C:\\Windows')

    def run(arguments,success=True):
        result=subprocess.run(list(map(str,arguments)),env=environment,capture_output=True,timeout=30)
        if (result.returncode==0)!=success:
            raise AssertionError(f'{arguments}: exit {result.returncode}; {result.stdout!r}; {result.stderr!r}')
        return result

    project=output/'project'
    if run_qemu:
        result=subprocess.run(['bash',str(ROOT/'scripts/build_kernel.sh'),str(compiler),str(project),'--run'],
                              cwd=ROOT,capture_output=True,timeout=45)
        if result.returncode:raise AssertionError(f'{result.stdout!r}\n{result.stderr!r}')
        sys.stdout.write(result.stdout.decode('utf-8',errors='replace'))
    else:
        runtime=project/'src/sotlas/runtime';runtime.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'runtime/native/kernel_x86.sotlas',runtime/'kernel_x86.sotlas')
        shutil.copyfile(ROOT/'examples/native_kernel_boot/main.sotlas',project/'src/main.sotlas')
        run([compiler,'--check-build',project/'src',project/'src/main.sotlas'])
        run([compiler,'--build-obj',project/'kernel.o',project/'src',project/'src/main.sotlas'])
        run([compiler,'--link-kernel',project/'kernel.o',project/'kernel.elf','kernel_main'])
    image=(project/'kernel.elf').read_bytes()
    assert image[:7]==b'\x7fELF\x01\x01\x01'
    assert struct.unpack_from('<HHI',image,16)==(2,3,1)
    assert struct.unpack_from('<I',image,24)[0]==0x100010
    assert struct.unpack_from('<H',image,44)[0]==2
    magic,flags,checksum=struct.unpack_from('<III',image,4096)
    assert magic==0x1badb002 and flags==3 and (magic+flags+checksum)&0xffffffff==0
    assert struct.unpack_from('<IIIIIIII',image,52)==(1,4096,0x100000,0x100000,4096,0x20000,7,4096)
    second=struct.unpack_from('<IIIIIIII',image,84)
    assert second[0:4]==(1,8192,0x400000,0x400000)
    assert second[4]==len(image)-8192 and second[5]>=second[4] and second[6:]==(7,4096)
    assert struct.unpack_from('<Q',image,4656)[0]==struct.unpack_from('<Q',image,8192+24)[0]
    again=project/'again.elf'
    run([compiler,'--link-kernel',project/'kernel.o',again,'kernel_main'])
    assert again.read_bytes()==image
    for bad_entry in ('missing_entry','native_kernel_halt'):
        preserved=project/(bad_entry+'.elf');preserved.write_bytes(b'preserve existing image')
        run([compiler,'--link-kernel',project/'kernel.o',preserved,bad_entry],False)
        assert preserved.read_bytes()==b'preserve existing image'
    for index,signature in enumerate(('()->u32{return 42;}',
        '(magic:u64,info:u32)->u32{return 42;}',
        '(magic:u32,info:u32)->f64{return 42.0;}')):
        source=project/f'wrong_abi_{index}.sotlas';obj=source.with_suffix('.o')
        source.write_text('module wrong;pub fn kernel_main'+signature,encoding='utf-8')
        run([compiler,source,obj,'--object'])
        bad=source.with_suffix('.elf');run([compiler,'--link-kernel',obj,bad,'kernel_main'],False)
        assert not bad.exists()
    source=project/'hosted_syscall.sotlas';obj=source.with_suffix('.o')
    source.write_text('''module wrong;@extern(C) fn sotlas_linux_close(fd:u64)->i64;
pub fn kernel_main(magic:u32,info:u32)->u32{let code:i64=sotlas_linux_close(0);return 42;}''',encoding='utf-8')
    run([compiler,source,obj,'--object'])
    bad=source.with_suffix('.elf');run([compiler,'--link-kernel',obj,bad,'kernel_main'],False)
    assert not bad.exists()


if __name__=='__main__':
    verify_kernel_image(sys.argv[1],sys.argv[2],'--run' in sys.argv[3:])
    print('Native kernel image and rejection contracts verified.'+(' QEMU boot verified.' if '--run' in sys.argv[3:] else ''))
