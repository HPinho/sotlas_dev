"""Interior storage addresses preserve type, mutability and evaluation order."""
import unittest
import os
import subprocess
import signal
import test_sotlas_native_i32 as previous


class NativeProjectedAddressTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute
    windows_process_exit_code = previous.NativeI32Tests.windows_process_exit_code

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_scalar_field_mutation_updates_original_record(self):
        self.program('place_field', '''struct Row{pub pad:u64;pub n:u32;}
pub fn main_entry()->u32{let mut row:Row=Row{pad:99,n:1};
let mut p:*mut u32=unsafe{(&mut row.n) as *mut u32};unsafe{*p=42;}
if row.pad!=99{return 1;}return row.n;}''')

    def test_immutable_field_can_produce_readonly_address(self):
        self.program('place_readonly', '''struct Row{pub n:u32;}
pub fn main_entry()->u32{let row:Row=Row{n:42};let p:*const u32=unsafe{(&row.n) as *const u32};return unsafe{*p};}''')

    def test_nested_inline_record_address(self):
        self.program('place_nested', '''struct Cell{pub n:u32;}struct Row{pub pad:u64;pub cell:Cell;}
pub fn main_entry()->u32{let mut row:Row=Row{pad:99,cell:Cell{n:1}};
let mut p:*mut Cell=unsafe{(&mut row.cell) as *mut Cell};unsafe{p.n=42;}return row.cell.n;}''')

    def test_array_scalar_element_address(self):
        self.program('place_element', '''pub fn main_entry()->u32{let mut values:[u32;3]=[1,2,3];
let mut p:*mut u32=unsafe{(&mut values[1]) as *mut u32};unsafe{*p=42;}
if values[0]!=1 || values[2]!=3{return 1;}return values[1];}''')

    def test_record_array_element_address(self):
        self.program('place_record_element', '''struct Cell{pub pad:u64;pub n:u32;}
pub fn main_entry()->u32{let mut cells:[Cell;3]=[Cell{pad:99,n:1};3];
let mut p:*mut Cell=unsafe{(&mut cells[1]) as *mut Cell};unsafe{p.n=42;}
if cells[0].n!=1 || cells[2].n!=1 || cells[1].pad!=99{return 1;}return cells[1].n;}''')

    def test_inline_array_element_address(self):
        self.program('place_array_field', '''struct Row{pub pad:u32;pub values:[u16;3];}
pub fn main_entry()->u32{let mut row:Row=Row{pad:99,values:[1;3]};
let mut p:*mut u16=unsafe{(&mut row.values[2]) as *mut u16};unsafe{*p=42;}
if row.values[0]!=1 || row.pad!=99{return 1;}return row.values[2] as u32;}''')

    def test_scalar_field_in_record_array(self):
        self.program('place_record_field', '''struct Row{pub pad:u64;pub n:u32;}
pub fn main_entry()->u32{let mut rows:[Row;2]=[Row{pad:99,n:1};2];
let mut p:*mut u32=unsafe{(&mut rows[1].n) as *mut u32};unsafe{*p=42;}
if rows[0].n!=1 || rows[1].pad!=99{return 1;}return rows[1].n;}''')

    def test_index_evaluated_once_before_mutating_call(self):
        self.program('place_order', '''static mut trace:u32=0;
fn index()->u32{unsafe{trace=trace*10+1;}return 1;}
fn set(mut p:*mut u32)->u32{unsafe{trace=trace*10+2;*p=42;}return 0;}
pub fn main_entry()->u32{let mut a:[u32;2]=[1;2];set(unsafe{(&mut a[index()]) as *mut u32});
if unsafe{trace}!=12 || a[0]!=1{return 1;}return a[1];}''')

    def test_pointer_projection_reaches_pointee_not_pointer_slot(self):
        self.program('place_pointer', '''struct Cell{pub n:u32;}struct Root{pub cell:*mut Cell;}
pub fn main_entry()->u32{let mut cell:Cell=Cell{n:1};let p:*mut Cell=unsafe{(&mut cell) as *mut Cell};
let mut root:Root=Root{cell:p};let mut q:*mut u32=unsafe{(&mut root.cell.n) as *mut u32};unsafe{*q=42;}return cell.n;}''')

    def test_readonly_pointer_projection(self):
        self.program('place_const_pointer', '''struct Cell{pub n:u32;}
pub fn main_entry()->u32{let cell:Cell=Cell{n:42};let p:*const Cell=unsafe{(&cell) as *const Cell};
let q:*const u32=unsafe{(&p.n) as *const u32};return unsafe{*q};}''')

    def test_field_widths_signed_float_bool(self):
        for typ, old, new in (('u8','1','42'),('i16','-1','42'),('u64','1','42'),
                              ('f32','1.0','42.0'),('f64','1.0','42.0'),('bool','false','true')):
            with self.subTest(typ=typ):
                self.program('place_width_'+typ,'struct Row{pub pad:u64;pub value:'+typ+';}'
                             'pub fn main_entry()->u32{let mut row:Row=Row{pad:99,value:'+old+'};'
                             'let mut p:*mut '+typ+'=unsafe{(&mut row.value) as *mut '+typ+'};'
                             'unsafe{*p='+new+';}if row.pad!=99 || row.value!='+new+'{return 1;}return 42;}')

    def test_invalid_mutability_type_and_temporary_addresses_are_rejected(self):
        cases = (
            'let row:Row=Row{n:1};let p:*mut u32=unsafe{(&mut row.n) as *mut u32};',
            'let mut row:Row=Row{n:1};let p:*mut u32=unsafe{(&row.n) as *mut u32};',
            'let mut row:Row=Row{n:1};let p:*mut u32=(&mut row.n) as *mut u32;',
            'let mut row:Row=Row{n:1};let p:*mut u64=unsafe{(&mut row.n) as *mut u64};',
            'let mut a:[Row;2]=[Row{n:1};2];let p:*mut Other=unsafe{(&mut a[0]) as *mut Other};',
            'let mut a:[u32;2]=[1;2];let p:*mut u32=unsafe{(&a[0]) as *mut u32};',
            'let a:[u32;2]=[1;2];let p:*const u32=unsafe{(&mut a[0]) as *const u32};',
            'let row:Row=Row{n:1};let p:*const Row=unsafe{(&row) as *const Row};let q:*mut u32=unsafe{(&mut p.n) as *mut u32};',
            'let p:*const u32=unsafe{(&make().n) as *const u32};',
            'let p:*const u32=unsafe{(&[1,2][0]) as *const u32};',
            'let mut owner:sole Row=Row{n:1};let p:*mut u32=unsafe{(&mut owner.n) as *mut u32};',
        )
        for index, body in enumerate(cases):
            with self.subTest(index=index):
                self.compile('place_reject_'+str(index),'struct Row{pub n:u32;}struct Other{pub n:u32;}'
                             'fn make()->Row{return Row{n:42};}pub fn main_entry()->u32{'+body+'return 42;}',False)

    def test_mut_qualifier_survives_whitespace_and_comments(self):
        for index, spelling in enumerate(('& mut','&\nmut','& /* explicit capability */ mut')):
            with self.subTest(spelling=spelling):
                self.program('place_qualifier_'+str(index),'struct Row{pub n:u32;}'
                             'pub fn main_entry()->u32{let mut row:Row=Row{n:1};'
                             'let mut p:*mut u32=unsafe{('+spelling+' row.n) as *mut u32};'
                             'unsafe{*p=42;}return row.n;}')

    def test_nested_const_pointer_cannot_become_mutable_interior_pointer(self):
        for destination, borrow in (('*mut u32','&mut'),('*const u32','&mut')):
            with self.subTest(destination=destination):
                self.compile('place_nested_const_'+str(len(destination)),'''struct Cell{pub n:u32;}struct Root{pub cell:*const Cell;}
pub fn main_entry()->u32{let cell:Cell=Cell{n:42};let p:*const Cell=unsafe{(&cell) as *const Cell};
let mut root:Root=Root{cell:p};let q:DEST=unsafe{(BORROW root.cell.n) as DEST};return 42;}
'''.replace('DEST',destination).replace('BORROW',borrow),False)

    def test_scalar_array_widths(self):
        for typ, value in (('u8','42'),('i8','42'),('i16','42'),('u64','42'),('f32','42.0'),('f64','42.0'),('bool','true')):
            with self.subTest(typ=typ):
                zero='false' if typ=='bool' else '0.0' if typ.startswith('f') else '0'
                self.program('place_array_width_'+typ,'pub fn main_entry()->u32{let mut a:['+typ+';3]=['+zero+';3];'
                             'let mut p:*mut '+typ+'=unsafe{(&mut a[1]) as *mut '+typ+'};'
                             'unsafe{*p='+value+';}if a[0]!='+zero+' || a[2]!='+zero+' || a[1]!='+value+'{return 1;}return 42;}')

    def test_address_is_recomputed_each_loop_iteration(self):
        self.program('place_loop', '''struct Row{pub n:u32;}
pub fn main_entry()->u32{let mut rows:[Row;3]=[Row{n:0};3];let mut i:usize=0;
while i<3{let mut p:*mut u32=unsafe{(&mut rows[i].n) as *mut u32};unsafe{*p=14;}i=i+1;}
return rows[0].n+rows[1].n+rows[2].n;}''')

    def test_two_distinct_interior_arguments(self):
        self.program('place_two_arguments', '''fn fill(mut a:*mut u32,mut b:*mut u32)->u32{unsafe{*a=20;*b=22;}return 0;}
pub fn main_entry()->u32{let mut a:[u32;3]=0;fill(unsafe{(&mut a[0]) as *mut u32},unsafe{(&mut a[2]) as *mut u32});
if a[1]!=0{return 1;}return a[0]+a[2];}''')

    def test_dynamic_out_of_bounds_address_traps_before_access(self):
        obj=self.compile('place_bounds', '''fn index()->usize{return 3;}
pub fn main_entry()->u32{let mut a:[u32;3]=0;let mut p:*mut u32=unsafe{(&mut a[index()]) as *mut u32};
unsafe{*p=42;}return 42;}''')
        image=self.link_image(obj)
        if os.name=='nt':
            code,error=self.windows_process_exit_code(image)
            self.assertEqual(code,0xc000001d,error)
        else:
            import resource
            result=subprocess.run([str(image)],capture_output=True,timeout=15,
                                  preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE,(0,0)))
            code=result.returncode
            self.assertEqual(code,-signal.SIGILL,result.stderr)

    def test_explicit_record_dereference_projection(self):
        self.program('place_explicit_deref', '''struct Row{pub n:u32;}
pub fn main_entry()->u32{let mut row:Row=Row{n:1};let mut p:*mut Row=unsafe{(&mut row) as *mut Row};
let mut q:*mut u32=unsafe{(&mut (*p).n) as *mut u32};unsafe{*q=42;}return row.n;}''')

    def test_captured_interior_address_survives_receiver_retargeting(self):
        self.program('place_capture', '''struct Cell{pub n:u32;}struct Root{pub cell:*mut Cell;}
pub fn main_entry()->u32{let mut a:Cell=Cell{n:1};let mut b:Cell=Cell{n:2};
let pa:*mut Cell=unsafe{(&mut a) as *mut Cell};let pb:*mut Cell=unsafe{(&mut b) as *mut Cell};
let mut root:Root=Root{cell:pa};let mut q:*mut u32=unsafe{(&mut root.cell.n) as *mut u32};
root.cell=pb;unsafe{*q=42;}if b.n!=2{return 1;}return a.n;}''')

    def test_static_record_and_array_storage(self):
        self.program('place_static', '''struct Row{pub n:u32;}static mut row:Row=Row{n:1};static mut values:[u32;2]=[1;2];
pub fn main_entry()->u32{let mut a:*mut u32=unsafe{(&mut row.n) as *mut u32};
let mut b:*mut u32=unsafe{(&mut values[1]) as *mut u32};unsafe{*a=20;*b=22;}
return unsafe{row.n+values[1]};}''')


if __name__ == '__main__':
    unittest.main()
