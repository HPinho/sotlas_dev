"""Native kernel image, rejection and optional required QEMU boot integration."""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def verify_kernel_image(compiler,output,run_qemu=False,interrupts=False,memory=False):
    assert not (interrupts and memory), 'Choose one kernel profile'
    compiler=Path(compiler).resolve();output=Path(output).resolve()
    environment={'PATH':str(output/'no-host-tools')}
    if os.name=='nt':environment['SystemRoot']=os.environ.get('SystemRoot','C:\\Windows')

    def run(arguments,success=True):
        result=subprocess.run(list(map(str,arguments)),env=environment,capture_output=True,timeout=30)
        if (result.returncode==0)!=success:
            raise AssertionError(f'{arguments}: exit {result.returncode}; {result.stdout!r}; {result.stderr!r}')
        return result

    project=output/'project'
    example='native_kernel_memory' if memory else 'native_kernel_interrupts' if interrupts else 'native_kernel_boot'
    if run_qemu:
        arguments=['bash',str(ROOT/'scripts/build_kernel.sh'),str(compiler),str(project),'--run']
        if interrupts:arguments.append('--interrupts')
        if memory:arguments.append('--memory')
        result=subprocess.run(arguments,
                              cwd=ROOT,capture_output=True,timeout=45)
        if result.returncode:raise AssertionError(f'{result.stdout!r}\n{result.stderr!r}')
        sys.stdout.write(result.stdout.decode('utf-8',errors='replace'))
    else:
        runtime=project/'src/sotlas/runtime';runtime.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'runtime/native/kernel_x86.sotlas',runtime/'kernel_x86.sotlas')
        if memory:
            for name in ('pages','kernel_memory'):
                shutil.copyfile(ROOT/f'runtime/native/{name}.sotlas',runtime/(name+'.sotlas'))
        shutil.copyfile(ROOT/('examples/'+example+'/main.sotlas'),project/'src/main.sotlas')
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
    has_interrupts=interrupts or memory
    prefix=36864 if has_interrupts else 8192
    boot_size=32768 if has_interrupts else 4096
    assert struct.unpack_from('<IIIIIIII',image,52)==(1,4096,0x100000,0x100000,boot_size,0x20000,7,4096)
    second=struct.unpack_from('<IIIIIIII',image,84)
    assert second[0:4]==(1,prefix,0x400000,0x400000)
    assert second[4]==len(image)-prefix and second[5]>=second[4] and second[6:]==(7,4096)
    assert struct.unpack_from('<Q',image,4656)[0]==struct.unpack_from('<Q',image,prefix+24)[0]
    assert struct.unpack_from('<IIQQQ',image,4928)==(0x314d454d,1,0x400000,0x400000+second[5],1<<30)
    if memory and run_qemu:
        # One image must discover available RAM rather than assume QEMU's size.
        for ram in ('32M','128M'):
            args=['qemu-system-x86_64','-machine','pc','-accel','tcg','-cpu','qemu64',
                  '-m',ram,'-kernel',str(project/'kernel.elf'),'-initrd',str(project/'boot-module.bin'),
                  '-display','none','-serial','stdio','-monitor','none','-no-reboot',
                  '-device','isa-debug-exit,iobase=0xf4,iosize=0x04']
            result=subprocess.run(args,capture_output=True,timeout=15)
            assert result.returncode==85,(ram,result.returncode,result.stdout,result.stderr)
            for marker in (b'SOTLAS: page allocation and reuse OK\n',b'SOTLAS: memory map and exhaustion OK\n',
                           b'SOTLAS: boot module preserved\n',b'SOTLAS: IRQ-safe page metadata OK\n'):
                assert marker in result.stdout,(ram,result.stdout,result.stderr)
            print('Kernel memory boot verified with '+ram+' RAM.')
    if has_interrupts:
        assert struct.unpack_from('<HQ',image,4896)==(4095,0x104000)
        assert image[4912:4916]==b'IRQ1'
        handler=struct.unpack_from('<Q',image,32768+71)[0]
        assert 0x400000+120<=handler<0x400000+second[4]
        for vector in range(256):
            low,selector,ist,flags,high,upper,reserved=struct.unpack_from('<HHBBHII',image,20480+vector*16)
            assert low|(high<<16)|(upper<<32)==0x105000+vector*32
            assert (selector,ist,flags,reserved)==(8,0,0x8e,0)
            stub=24576+vector*32
            has_error=vector in (8,10,11,12,13,14,17,21,29,30)
            if not has_error:
                assert image[stub:stub+2]==b'\x6a\x00';stub+=2
            assert image[stub]==0x68 and struct.unpack_from('<I',image,stub+1)[0]==vector
            assert image[stub+5]==0xe9
            relative=struct.unpack_from('<i',image,stub+6)[0]
            assert 0x100000+stub-4096+10+relative==0x107000
    else:
        assert image[4912:4916]==b'\0'*4
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
    for platform in ('linux','darwin'):
        source=project/(platform+'_syscall.sotlas');obj=source.with_suffix('.o')
        source.write_text('module wrong;@extern(C) fn sotlas_'+platform+'''_close(fd:u64)->i64;
pub fn kernel_main(magic:u32,info:u32)->u32{let code:i64=sotlas_'''+platform+'''_close(0);return 42;}''',encoding='utf-8')
        run([compiler,source,obj,'--object'])
        bad=source.with_suffix('.elf');run([compiler,'--link-kernel',obj,bad,'kernel_main'],False)
        assert not bad.exists()
    for index,signature in enumerate(('(vector:u32,error:u64,frame:*mut u64)->u64{return 0;}',
        '(vector:u64,error:u64,frame:*mut u64)->u32{return 0;}',
        '(vector:u32,error:u32,frame:*mut u64)->u32{return 0;}',
        '(vector:u32,error:u64,frame:u64)->u32{return 0;}',
        '(vector:u32,error:u64)->u32{return 0;}')):
        source=project/f'wrong_irq_{index}.sotlas';obj=source.with_suffix('.o')
        source.write_text('module wrong;pub fn kernel_main(magic:u32,info:u32)->u32{return 42;}'
                          +'pub fn kernel_interrupt'+signature,encoding='utf-8')
        run([compiler,source,obj,'--object'])
        bad=source.with_suffix('.elf');bad.write_bytes(b'preserve IRQ output')
        run([compiler,'--link-kernel',obj,bad,'kernel_main'],False)
        assert bad.read_bytes()==b'preserve IRQ output'


if __name__=='__main__':
    verify_kernel_image(sys.argv[1],sys.argv[2],'--run' in sys.argv[3:],'--interrupts' in sys.argv[3:],'--memory' in sys.argv[3:])
    print('Native kernel image and rejection contracts verified.'+(' QEMU boot verified.' if '--run' in sys.argv[3:] else ''))
