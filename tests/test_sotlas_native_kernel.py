"""Native privileged instructions and executable kernel image contracts."""
from pathlib import Path
import struct
import subprocess
import unittest
import test_sotlas_native_i32 as previous

ROOT=Path(__file__).resolve().parents[1]
DECLARATIONS='''@extern(C) fn sotlas_x86_out8(port:u16,value:u8)->i64;
@extern(C) fn sotlas_x86_in8(port:u16)->i64;
@extern(C) fn sotlas_x86_out32(port:u16,value:u32)->i64;
@extern(C) fn sotlas_x86_halt()->i64;
'''
IRQ_DECLARATIONS='''@extern(C) fn sotlas_x86_irq_save()->i64;
@extern(C) fn sotlas_x86_sti()->i64;
@extern(C) fn sotlas_x86_lidt(descriptor:*const u8)->i64;
@extern(C) fn sotlas_x86_int3()->i64;
@extern(C) fn sotlas_x86_load_ds(selector:u16)->i64;
@extern(C) fn sotlas_x86_wait_irq()->i64;
'''


class NativeKernelTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def test_privileged_instructions_have_bare_object_flag(self):
        source=DECLARATIONS+'''pub fn kernel_main(magic:u32,info:u32)->u32{unsafe{
let a:i64=sotlas_x86_out8(1016,42);let b:i64=sotlas_x86_in8(1021);
let c:i64=sotlas_x86_out32(244,42);let d:i64=sotlas_x86_halt();}return magic+info;}'''
        obj=self.compile('privileged',source)
        data=obj.read_bytes()
        self.assertEqual(struct.unpack_from('<I',data,48)[0],4)
        headers=struct.unpack_from('<Q',data,40)[0]
        text=next((data[struct.unpack_from('<Q',data,h+24)[0]:struct.unpack_from('<Q',data,h+24)[0]+struct.unpack_from('<Q',data,h+32)[0]]
                   for h in range(headers,headers+struct.unpack_from('<H',data,60)[0]*64,64)
                   if struct.unpack_from('<Q',data,h+8)[0]&4),b'')
        for opcode in (b'\xee\x31\xc0',b'\x31\xc0\xec',b'\xef\x31\xc0',b'\xf4\x31\xc0'):
            self.assertIn(opcode,text)

    def test_privileged_calls_require_unsafe(self):
        for i,call in enumerate(('sotlas_x86_out8(1016,42)','sotlas_x86_in8(1021)',
                                 'sotlas_x86_out32(244,42)','sotlas_x86_halt()')):
            with self.subTest(call=call):
                self.compile('privileged_safe_'+str(i),DECLARATIONS+
                             'pub fn main_entry()->u32{let result:i64='+call+';return 42;}',False)

    def test_interrupt_operations_require_unsafe(self):
        for i,call in enumerate(('sotlas_x86_irq_save()','sotlas_x86_sti()',
                                 'sotlas_x86_lidt(null)','sotlas_x86_int3()',
                                 'sotlas_x86_load_ds(16)','sotlas_x86_wait_irq()')):
            with self.subTest(call=call):
                self.compile('irq_unsafe_'+str(i),IRQ_DECLARATIONS+
                             'pub fn main_entry()->u32{let result:i64='+call+';return 42;}',False)

    def test_interrupt_operations_emit_native_instructions(self):
        obj=self.compile('irq_instructions',IRQ_DECLARATIONS+'''pub fn main_entry()->u32{unsafe{
sotlas_x86_irq_save();sotlas_x86_sti();sotlas_x86_lidt(null);sotlas_x86_int3();
sotlas_x86_load_ds(16);sotlas_x86_wait_irq();}return 42;}''')
        data=obj.read_bytes();self.assertEqual(struct.unpack_from('<I',data,48)[0],4)
        headers=struct.unpack_from('<Q',data,40)[0]
        text=next((data[struct.unpack_from('<Q',data,h+24)[0]:struct.unpack_from('<Q',data,h+24)[0]+struct.unpack_from('<Q',data,h+32)[0]]
                   for h in range(headers,headers+struct.unpack_from('<H',data,60)[0]*64,64)
                   if struct.unpack_from('<Q',data,h+8)[0]&4),b'')
        for opcode in (b'\x9c\x58\xfa',b'\xfb\x31\xc0',b'\x0f\x01\x18',
                       b'\xcc\x31\xc0',b'\x8e\xd8',b'\xfb\xf4\xfa'):
            self.assertIn(opcode,text)

    def test_interrupt_operations_reject_wrong_machine_signatures(self):
        for i,(declaration,call) in enumerate((
            ('@extern(C) fn sotlas_x86_lidt(descriptor:u64)->i64;','sotlas_x86_lidt(0)'),
            ('@extern(C) fn sotlas_x86_irq_save(value:u16)->i64;','sotlas_x86_irq_save(0)'),
            ('@extern(C) fn sotlas_x86_load_ds(selector:u32)->i64;','sotlas_x86_load_ds(16)'),
            ('@extern(C) fn sotlas_x86_wait_irq()->u32;','sotlas_x86_wait_irq()'),
        )):
            with self.subTest(declaration=declaration):
                self.compile('irq_signature_'+str(i),declaration+
                             'pub fn main_entry()->u32{unsafe{'+call+';}return 42;}',False)

    def test_privileged_constants_fit_the_declared_port_and_value_widths(self):
        for i,call in enumerate(('sotlas_x86_out8(65536,1)',
                                 'sotlas_x86_out8(1,256)',
                                 'sotlas_x86_out32(1,4294967296)')):
            with self.subTest(call=call):
                self.compile('privileged_width_'+str(i),DECLARATIONS+
                             'pub fn main_entry()->u32{unsafe{'+call+';}return 42;}',False)

    def test_privileged_names_reject_wrong_signatures_and_bodies(self):
        for i,source in enumerate((
            '@extern(C) fn sotlas_x86_out8(port:u32,value:u8)->i64;',
            '@extern(C) fn sotlas_x86_out8(port:u16,value:u32)->i64;',
            '@extern(C) fn sotlas_x86_out8(port:u16,value:u8)->u32;',
            'fn sotlas_x86_out8(port:u16,value:u8)->i64{return 0;}',
        )):
            with self.subTest(source=source):
                self.compile('privileged_signature_'+str(i),source+
                    'pub fn main_entry()->u32{unsafe{sotlas_x86_out8(1016,42);}return 42;}',False)

    def test_host_linkers_reject_privileged_objects(self):
        obj=self.compile('privileged_host',DECLARATIONS+
                         'pub fn main_entry()->u32{unsafe{sotlas_x86_out8(1016,42);}return 42;}')
        for mode in ('--link-exe','--link-pe','--link-macho'):
            output=obj.with_suffix('.'+mode[2:])
            result=subprocess.run([str(self.producer),mode,str(obj),str(output),'main_entry'],capture_output=True,timeout=30)
            self.assertNotEqual(result.returncode,0,result.stderr)
            self.assertFalse(output.exists())
