"""Native kernel image, rejection and optional required QEMU boot integration."""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def verify_kernel_image(compiler,output,run_qemu=False,interrupts=False,memory=False,heap=False,collections=False,vm=False,foundation=False):
    assert sum((interrupts,memory,heap,collections,vm,foundation))<=1, 'Choose one kernel profile'
    compiler=Path(compiler).resolve();output=Path(output).resolve()
    environment={'PATH':str(output/'no-host-tools')}
    if os.name=='nt':environment['SystemRoot']=os.environ.get('SystemRoot','C:\\Windows')

    def run(arguments,success=True):
        result=subprocess.run(list(map(str,arguments)),env=environment,capture_output=True,timeout=30)
        if (result.returncode==0)!=success:
            raise AssertionError(f'{arguments}: exit {result.returncode}; {result.stdout!r}; {result.stderr!r}')
        return result

    project=output/'project'
    example='native_kernel_foundation' if foundation else 'native_kernel_vm' if vm else 'native_kernel_collections' if collections else 'native_kernel_heap' if heap else 'native_kernel_memory' if memory else 'native_kernel_interrupts' if interrupts else 'native_kernel_boot'
    if run_qemu:
        arguments=['bash',str(ROOT/'scripts/build_kernel.sh'),str(compiler),str(project),'--run']
        if interrupts:arguments.append('--interrupts')
        if memory:arguments.append('--memory')
        if heap:arguments.append('--heap')
        if collections:arguments.append('--collections')
        if vm:arguments.append('--vm')
        if foundation:arguments.append('--foundation')
        result=subprocess.run(arguments,
                              cwd=ROOT,capture_output=True,timeout=45)
        if result.returncode:raise AssertionError(f'{result.stdout!r}\n{result.stderr!r}')
        sys.stdout.write(result.stdout.decode('utf-8',errors='replace'))
    else:
        runtime=project/'src/sotlas/runtime';runtime.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'runtime/native/kernel_x86.sotlas',runtime/'kernel_x86.sotlas')
        if memory or heap or collections or vm or foundation:
            for name in ('pages','kernel_memory'):
                shutil.copyfile(ROOT/f'runtime/native/{name}.sotlas',runtime/(name+'.sotlas'))
        if memory or foundation:
            shutil.copyfile(ROOT/'runtime/native/initramfs.sotlas',runtime/'initramfs.sotlas')
        if vm or foundation:
            shutil.copyfile(ROOT/'runtime/native/kernel_vm.sotlas',runtime/'kernel_vm.sotlas')
        if heap or collections or foundation:
            for name in ('managed','heap','kernel_heap'):
                shutil.copyfile(ROOT/f'runtime/native/{name}.sotlas',runtime/(name+'.sotlas'))
        if foundation:
            shutil.copyfile(ROOT/'runtime/native/kernel_owned_heap.sotlas',runtime/'kernel_owned_heap.sotlas')
        if collections or foundation:
            for name in ('vector','results','text','unicode','utf8_buffer','heap_text','word_map'):
                shutil.copyfile(ROOT/f'runtime/native/{name}.sotlas',runtime/(name+'.sotlas'))
        shutil.copyfile(ROOT/('examples/'+example+'/main.sotlas'),project/'src/main.sotlas')
        run([compiler,'--check-build',project/'src',project/'src/main.sotlas'])
        run([compiler,'--build-obj',project/'kernel.o',project/'src',project/'src/main.sotlas'])
        run([compiler,'--link-kernel',project/'kernel.o',project/'kernel.elf','kernel_main'])
    image=(project/'kernel.elf').read_bytes()
    if foundation:
        # Exercise the production resource API through both normal frontend
        # entry points. These programs must fail before publishing an object.
        cases=(
            'let owner:sole NativeOwnedPages=native_kernel_pages_acquire(1,1,true);'
            'native_kernel_owned_pages_release(owner);return native_kernel_owned_pages_address(owner) as u32;',
            'let owner:sole NativeOwnedPages=native_kernel_pages_acquire(1,1,true);'
            'defer native_kernel_owned_pages_close(owner);return native_kernel_owned_pages_load(owner,0);',
            'let mut owner:sole NativeOwnedPages=native_kernel_pages_acquire(1,1,true);'
            'defer native_kernel_owned_pages_close(owner);owner=native_kernel_pages_acquire(1,1,true);return 42;',
            'let owner:sole NativeOwnedBuffer=native_kernel_buffer_acquire(null,8,8,true);'
            'native_kernel_buffer_release(owner,true);return native_kernel_buffer_length(owner) as u32;',
            'let owner:sole NativeOwnedBuffer=native_kernel_buffer_acquire(null,8,8,true);'
            'let resized:sole NativeOwnedBuffer=native_kernel_buffer_resize(owner,16,8,true);'
            'return native_kernel_buffer_length(owner) as u32;',
            'let mut owner:sole NativeOwnedBuffer=native_kernel_buffer_acquire(null,8,8,true);'
            'defer native_kernel_buffer_close(owner);owner=native_kernel_buffer_acquire(null,8,8,true);return 42;',
            'let owner:sole NativeOwnedPages=native_kernel_pages_acquire(1,1,true);'
            'defer{native_kernel_owned_pages_close(owner);}return native_kernel_owned_pages_load(owner,0);',
            'let owner:sole NativeOwnedPages=native_kernel_pages_acquire(1,1,true);'
            'defer{native_kernel_owned_pages_close(owner);native_kernel_owned_pages_close(owner);}return 42;',
            'let mut owner:sole NativeOwnedBuffer=native_kernel_buffer_acquire(null,8,8,true);'
            'defer{native_kernel_buffer_close(owner);}owner=native_kernel_buffer_acquire(null,8,8,true);return 42;',
        )
        for index,body in enumerate(cases):
            source=project/'src'/f'reject_owned_pages_{index}.sotlas'
            source.write_text('barecore;module reject_owned_pages;import sotlas::runtime::kernel_memory::*;'
                              +'import sotlas::runtime::kernel_owned_heap::*;'
                              +'pub fn main_entry()->u32{'+body+'}',encoding='utf-8')
            run([compiler,'--check-build',project/'src',source],False)
            rejected=project/f'reject_owned_pages_{index}.o'
            run([compiler,'--build-obj',rejected,project/'src',source],False)
            assert not rejected.exists()
    assert image[:7]==b'\x7fELF\x01\x01\x01'
    assert struct.unpack_from('<HHI',image,16)==(2,3,1)
    assert struct.unpack_from('<I',image,24)[0]==0x100010
    assert struct.unpack_from('<H',image,44)[0]==2
    magic,flags,checksum=struct.unpack_from('<III',image,4096)
    assert magic==0x1badb002 and flags==3 and (magic+flags+checksum)&0xffffffff==0
    has_interrupts=interrupts or memory or heap or collections or vm or foundation
    prefix=36864 if has_interrupts else 8192
    boot_size=32768 if has_interrupts else 4096
    assert struct.unpack_from('<IIIIIIII',image,52)==(1,4096,0x100000,0x100000,boot_size,0x20000,7,4096)
    second=struct.unpack_from('<IIIIIIII',image,84)
    assert second[0:4]==(1,prefix,0x400000,0x400000)
    assert second[4]==len(image)-prefix and second[5]>=second[4] and second[6:]==(7,4096)
    assert struct.unpack_from('<Q',image,4656)[0]==struct.unpack_from('<Q',image,prefix+24)[0]
    assert struct.unpack_from('<IIQQQ',image,4928)==(0x314d454d,1,0x400000,0x400000+second[5],1<<30)
    if (memory or heap or collections or vm or foundation) and run_qemu:
        # One image must discover available RAM rather than assume QEMU's size.
        for ram in ('32M','128M'):
            args=['qemu-system-x86_64','-machine','pc','-accel','tcg','-cpu','qemu64',
                  '-m',ram,'-kernel',str(project/'kernel.elf'),
                  '-display','none','-serial','stdio','-monitor','none','-no-reboot',
                  '-device','isa-debug-exit,iobase=0xf4,iosize=0x04']
            # Multiboot module filenames are parsed again inside QEMU. Keep
            # that filename free of separators even when project has spaces.
            if memory or foundation:args+=['-initrd','boot-module.bin']
            result=subprocess.run(args,cwd=project,capture_output=True,timeout=15)
            assert result.returncode==85,(ram,result.returncode,result.stdout,result.stderr)
            markers=(b'SOTLAS: foundation initramfs and VM OK\n',
                     b'SOTLAS: foundation IRQ and data OK\n',
                     b'SOTLAS: foundation reclaim and ownership OK\n') if foundation else (b'SOTLAS: read-only and NX faults verified\n',b'SOTLAS: unmap and remap verified\n') if vm else (
                     b'SOTLAS: dynamic words and checked views OK\n',b'SOTLAS: collections IRQ and heap reclamation OK\n',
                     b'SOTLAS: growing UTF-8 report OK\n',b'SOTLAS: dynamic map histogram OK\n',
                     'Sotlas: é events=2000 min=-9223372036854775808\n'.encode('utf-8')) if collections else (
                     b'SOTLAS: heap resize and failure preservation OK\n',b'SOTLAS: heap IRQ allocation and exhaustion OK\n',
                     b'SOTLAS: heap pages returned and stale handles rejected\n') if heap else (
                     b'SOTLAS: page allocation and reuse OK\n',b'SOTLAS: memory map and exhaustion OK\n',
                     b'SOTLAS: boot module preserved\n',b'SOTLAS: IRQ-safe page metadata OK\n')
            for marker in markers:
                assert marker in result.stdout,(ram,result.stdout,result.stderr)
            print('Kernel '+('foundation' if foundation else 'VM' if vm else 'collections' if collections else 'heap' if heap else 'memory')+' boot verified with '+ram+' RAM.')
    if vm and run_qemu:
        result=subprocess.run(
            ['qemu-system-x86_64','-machine','pc','-accel','tcg','-cpu','qemu64,-nx',
             '-m','64M','-kernel',str(project/'kernel.elf'),'-display','none','-serial','stdio',
             '-monitor','none','-no-reboot','-device','isa-debug-exit,iobase=0xf4,iosize=0x04'],
            cwd=project,capture_output=True,timeout=15,
        )
        assert result.returncode==87 and b'SOTLAS: NX unavailable; allocator unchanged\n' in result.stdout,(
            result.returncode,result.stdout,result.stderr)
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
    verify_kernel_image(sys.argv[1],sys.argv[2],'--run' in sys.argv[3:],'--interrupts' in sys.argv[3:],'--memory' in sys.argv[3:],'--heap' in sys.argv[3:],'--collections' in sys.argv[3:],'--vm' in sys.argv[3:],'--foundation' in sys.argv[3:])
    print('Native kernel image and rejection contracts verified.'+(' QEMU boot verified.' if '--run' in sys.argv[3:] else ''))
