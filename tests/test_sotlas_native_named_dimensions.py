"""Module constants resolve fixed native shapes without runtime lengths."""
import unittest
import test_sotlas_native_i32 as previous


class NativeNamedDimensionTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_module_constant_in_local_type_and_repetition(self):
        self.program('named_dimension_local', '''const COUNT:usize=6;
pub fn main_entry()->u32{let a:[u32;COUNT]=[7;COUNT];return a[5]*6;}''')

    def test_forward_constant_dependencies_and_arithmetic(self):
        self.program('named_dimension_forward', '''const COUNT:usize=HALF*2;const HALF:usize=THREE;const THREE:usize=3;
pub fn main_entry()->u32{let a:[u32;COUNT+2-2]=[7;HALF+THREE];return a[5]*6;}''')

    def test_each_unsigned_constant_width(self):
        for typ in ('u8','u16','u32','u64','usize'):
            with self.subTest(typ=typ):
                self.program('named_dimension_'+typ,'const COUNT:'+typ+'=6;pub fn main_entry()->u32{let a:[u32;COUNT]=[7;COUNT];return a[5]*6;}')

    def test_constants_can_follow_their_type_use(self):
        self.program('named_dimension_later', '''struct Row{pub a:[u32;COUNT];}
const COUNT:u16=6;pub fn main_entry()->u32{let row:Row=Row{a:[7;COUNT]};return row.a[5]*6;}''')

    def test_internal_parameters_and_return_shapes(self):
        self.program('named_dimension_calls', '''const COUNT:usize=6;
fn make()->[u32;COUNT]{return [7;COUNT];}fn use(a:[u32;3*2])->u32{return a[5]*6;}
pub fn main_entry()->u32{return use(make());}''')

    def test_static_scalar_and_record_tables(self):
        self.program('named_dimension_static', '''const COUNT:usize=2;struct Cell{pub n:u32;}
static mut VALUES:[u32;COUNT*3]=[7;COUNT*3];static CELLS:[Cell;COUNT]=[Cell{n:7};COUNT];
pub fn main_entry()->u32{unsafe{VALUES[5]=35;}return unsafe{VALUES[5]+CELLS[1].n};}''')

    def test_named_dimensions_in_payloads_and_match(self):
        self.program('named_dimension_payload', '''const COUNT:usize=6;enum Message{Empty,Values([u32;COUNT])}
fn make()->Message{return Message::Values([7;COUNT]);}
pub fn main_entry()->u32{return match make(){Message::Empty=>1,Message::Values(a)=>a[5]*6};}''')

    def test_named_record_arrays_and_nested_fields(self):
        self.program('named_dimension_nested', '''const COUNT:usize=2;struct Cell{pub a:[u32;COUNT*3];}
struct Batch{pub cells:[Cell;COUNT];}
pub fn main_entry()->u32{let mut b:Batch=Batch{cells:[Cell{a:[7;COUNT*3]};COUNT]};
b.cells[1].a[5]=42;if b.cells[0].a[5]!=7 || span_of::<Batch>()!=48{return 1;}return b.cells[1].a[5];}''')

    def test_layout_queries_and_constants_use_named_shapes(self):
        self.program('named_dimension_query', '''const COUNT:usize=6;const BYTES:usize=span_of::<[u64;COUNT]>();
pub fn main_entry()->u32{if BYTES!=48 || align_of::<[u64;COUNT]>()!=8{return 1;}return 42;}''')

    def test_owned_moves_and_deferred_borrows(self):
        self.program('named_dimension_cleanup', '''const COUNT:usize=6;static mut trace:u32=0;
fn observe(a:whisper [u32;COUNT])->void{unsafe{trace=trace+a[5]*6;}return;}
fn work()->u32{let a:sole [u32;COUNT]=[7;COUNT];defer observe(a);return 0;}
pub fn main_entry()->u32{let ignored:u32=work();return unsafe{trace};}''')
        self.compile('named_dimension_moved', '''const COUNT:usize=6;fn consume(a:sole [u32;COUNT])->u32{return a[5];}
pub fn main_entry()->u32{let a:sole [u32;COUNT]=[7;COUNT];let n:u32=consume(a);return a[0];}''',False)

    def test_local_and_parameter_shadows_are_not_constant_dimensions(self):
        for index,body in enumerate(('let COUNT:usize=6;let a:[u32;COUNT]=[7;6];',
                                     'let COUNT:usize=6;let a:[u32;6]=[7;COUNT];')):
            self.compile('named_dimension_shadow_'+str(index),'const COUNT:usize=6;pub fn main_entry()->u32{'+body+'return 42;}',False)
        self.compile('named_dimension_param','''const COUNT:usize=6;
fn bad(COUNT:usize)->u32{let a:[u32;COUNT]=[7;6];return 42;}pub fn main_entry()->u32{return 42;}''',False)

    def test_only_unsigned_module_constants_are_accepted(self):
        for index,declaration in enumerate(('let COUNT:usize=6;', 'static COUNT:usize=6;',
                                            'const COUNT:i32=6;', 'const COUNT:bool=true;',
                                            'const COUNT:f64=6.0;', 'const COUNT:u8=256;')):
            self.compile('named_dimension_kind_'+str(index),declaration+'pub fn main_entry()->u32{let a:[u32;COUNT]=[7;6];return 42;}',False)

    def test_cycles_and_invalid_initializers_are_rejected(self):
        for index,declaration in enumerate(('const COUNT:usize=COUNT;',
                                            'const COUNT:usize=OTHER;const OTHER:usize=COUNT;',
                                            'const COUNT:usize=1/0;', 'const COUNT:usize=1-2;',
                                            'const COUNT:usize=18446744073709551615+7;',
                                            'const COUNT:usize=0;', 'const COUNT:usize=4097;')):
            self.compile('named_dimension_invalid_'+str(index),declaration+'pub fn main_entry()->u32{let a:[u32;COUNT]=[7;6];return 42;}',False)

    def test_unreachable_named_dimensions_still_require_valid_constants(self):
        self.compile('named_dimension_dead','''const COUNT:usize=0;
pub fn main_entry()->u32{return 42;let a:[u32;COUNT]=[7;6];}''',False)


if __name__ == '__main__':
    unittest.main()
