"""Checked compile-time arithmetic for native fixed-array shapes."""
import unittest
import test_sotlas_native_i32 as previous


class NativeArrayDimensionTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_local_type_and_repeat_arithmetic(self):
        self.program('dimension_local', '''pub fn main_entry()->u32{
let values:[u32;2*3]=[7;2+4];return values[0]+values[1]+values[2]+values[3]+values[4]+values[5];}''')

    def test_precedence_parentheses_and_left_associativity(self):
        for index, expression in enumerate(('2+2*2', '(1+2)*2', '12/2', '14%8', '10-3-1', '24/2/2', '0x2*0b11', '0o10-2')):
            with self.subTest(expression=expression):
                self.program('dimension_order_'+str(index), 'pub fn main_entry()->u32{let a:[u32;'+expression+']=[7;'+expression+'];return a[5]*6;}')

    def test_record_fields_and_record_array_repetitions(self):
        self.program('dimension_records', '''struct Cell{pub n:u32;}struct Batch{pub cells:[Cell;1+2];pub flags:[u8;2*3];}
pub fn main_entry()->u32{let mut b:Batch=Batch{cells:[Cell{n:7};6/2],flags:[0;8-2]};
b.cells[2].n=42;if span_of::<Batch>()!=20 || b.flags[5]!=0 || b.cells[0].n!=7{return 1;}return b.cells[2].n;}''')

    def test_array_parameters_and_returns_use_evaluated_shapes(self):
        self.program('dimension_calls', '''fn make()->[u32;2*3]{return [7;2+4];}
fn total(values:[u32;12/2])->u32{return values[0]+values[1]+values[2]+values[3]+values[4]+values[5];}
pub fn main_entry()->u32{return total(make());}''')

    def test_global_static_arrays(self):
        self.program('dimension_globals', '''static mut TABLE:[u32;2*3]=[7;12/2];
pub fn main_entry()->u32{unsafe{TABLE[5]=42;}return unsafe{TABLE[5]};}''')

    def test_layout_queries_share_shape_arithmetic(self):
        self.program('dimension_queries', '''const SIZE:usize=span_of::<[u64;(2+1)*2]>();
pub fn main_entry()->u32{if SIZE!=48 || align_of::<[u64;12/2]>()!=8{return 1;}return 42;}''')

    def test_repeat_value_evaluated_once(self):
        self.program('dimension_once', '''static mut calls:u32=0;
fn value()->u32{unsafe{calls=calls+1;}return 7;}
pub fn main_entry()->u32{let a:[u32;2*3]=[value();2+4];if unsafe{calls}!=1{return 1;}return a[5]*6;}''')

    def test_invalid_dimension_arithmetic_is_rejected(self):
        expressions=('0','1-2','1/0','1%0','18446744073709551615+1',
                     '18446744073709551615*2','4096+1','missing','1<<2','1.5',
                     'true','-1','(2+3','2+3)','2**3','(1+2)(3+4)')
        for index, expression in enumerate(expressions):
            with self.subTest(expression=expression):
                self.compile('dimension_bad_'+str(index),'pub fn main_entry()->u32{let a:[u32;'+expression+']=[0;6];return 42;}',False)

    def test_invalid_repeat_arithmetic_is_rejected(self):
        for index, expression in enumerate(('1/0','1%0','1-2','18446744073709551615+1','2+3','missing','size()')):
            with self.subTest(expression=expression):
                self.compile('dimension_repeat_bad_'+str(index),'fn size()->u32{return 6;}pub fn main_entry()->u32{let a:[u32;6]=[7;'+expression+'];return 42;}',False)

    def test_bounded_evaluation_depth(self):
        expression='('*65+'6'+')'*65
        self.compile('dimension_depth','pub fn main_entry()->u32{let a:[u8;'+expression+']=[0;6];return 42;}',False)

    def test_payload_and_match_array_values(self):
        self.program('dimension_payload', '''enum Batch{Empty,Values([u32;2*3])}
fn get()->Batch{return Batch::Values([7;12/2]);}
pub fn main_entry()->u32{return match get(){Batch::Empty=>1,Batch::Values(values)=>values[5]*6};}''')

    def test_conditional_arrays_and_whole_array_assignment(self):
        self.program('dimension_conditional', '''fn make(flag:bool)->[u32;2+4]{return if flag{[7;3*2]}else{[1;12/2]};}
pub fn main_entry()->u32{let mut a:[u32;3*2]=[0;6];a=make(true);return a[5]*6;}''')

    def test_owned_transfer_and_use_after_move(self):
        self.program('dimension_owned', '''fn take(values:sole [u32;2*3])->u32{return values[5]*6;}
pub fn main_entry()->u32{let owner:sole [u32;2+4]=[7;12/2];return take(owner);}''')
        self.compile('dimension_moved', '''fn take(values:sole [u32;2*3])->u32{return values[5];}
pub fn main_entry()->u32{let owner:sole [u32;2+4]=[7;12/2];let n:u32=take(owner);return owner[0];}''',False)

    def test_invalid_dimensions_in_dead_code_are_rejected(self):
        for index,source in enumerate((
            'pub fn main_entry()->u32{return 42;let a:[u32;1/0]=[0;1];}',
            'fn unused(a:[u32;1-2])->u32{return 0;}pub fn main_entry()->u32{return 42;}',
            'pub fn main_entry()->u32{return 42;let a:[u32;6]=[7;1/0];}',
        )):
            with self.subTest(index=index):self.compile('dimension_dead_'+str(index),source,False)

    def test_existing_capacity_limits_apply_after_evaluation(self):
        self.program('dimension_max','''pub fn main_entry()->u32{let a:[u8;64*64]=[7;8192/2];return a[4095] as u32*6;}''')
        self.compile('dimension_field_max','''struct Row{pub a:[u8;256+1];}
pub fn main_entry()->u32{return 42;}''',False)

    def test_wide_intermediates_are_unsigned_and_checked(self):
        self.program('dimension_wide','''pub fn main_entry()->u32{
let a:[u32;18446744073709551615-18446744073709551609]=[7;18446744073709551615-18446744073709551609];
return a[5]*6;}''')

    def test_borrowed_array_cleanup_keeps_evaluated_shape(self):
        self.program('dimension_defer','''static mut trace:u32=0;
fn observe(a:whisper [u32;2*3])->void{unsafe{trace=trace+a[5]*6;}return;}
fn work()->u32{let a:sole [u32;2+4]=[7;12/2];defer observe(a);return 0;}
pub fn main_entry()->u32{let ignored:u32=work();return unsafe{trace};}''')


if __name__ == '__main__':
    unittest.main()
