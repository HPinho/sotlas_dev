"""Native target layout queries agree with actual generated storage."""
import unittest
import test_sotlas_native_i32 as previous


class NativeLayoutQueryTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self,name,source):
        self.execute(self.compile(name,source))

    def test_scalar_size_stride_and_alignment(self):
        for typ,size in (('bool',1),('u8',1),('i8',1),('u16',2),('i16',2),('u32',4),
                         ('i32',4),('f32',4),('u64',8),('i64',8),('usize',8),('f64',8)):
            with self.subTest(typ=typ):
                self.program('layout_scalar_'+typ,'pub fn main_entry()->u32{'
                             'if span_of::<'+typ+'>()!='+str(size)+' || stride_of::<'+typ+'>()!='+str(size)+
                             ' || align_of::<'+typ+'>()!='+str(size)+'{return 1;}return 42;}')

    def test_record_padding_and_zero_first_offset(self):
        self.program('layout_record','''struct Row{pub first:u8;pub wide:u64;pub tail:u16;}
pub fn main_entry()->u32{if span_of::<Row>()!=24 || stride_of::<Row>()!=24 || align_of::<Row>()!=8
|| field_offset!(Row,first)!=0 || field_offset!(Row,wide)!=8 || field_offset!(Row,tail)!=16{return 1;}return 42;}''')

    def test_arrays_use_full_element_stride(self):
        self.program('layout_arrays','''struct Row{pub byte:u8;pub wide:u64;}
pub fn main_entry()->u32{if span_of::<[u8;7]>()!=7 || align_of::<[u16;3]>()!=2
|| span_of::<[Row;3]>()!=48 || stride_of::<[Row;3]>()!=48 || align_of::<[Row;3]>()!=8{return 1;}return 42;}''')

    def test_nested_records_and_array_fields(self):
        self.program('layout_nested','''struct Cell{pub byte:u8;pub wide:u64;}struct Row{pub first:u8;pub cells:[Cell;2];pub last:u32;}
pub fn main_entry()->u32{if span_of::<Row>()!=48 || align_of::<Row>()!=8
|| field_offset!(Row,cells)!=8 || field_offset!(Row,last)!=40{return 1;}return 42;}''')

    def test_raw_record_and_scalar_pointer_layout(self):
        self.program('layout_pointer','''struct Node{pub n:u32;pub next:*mut Node;}
pub fn main_entry()->u32{if span_of::<*mut Node>()!=8 || align_of::<*const u8>()!=8
|| span_of::<Node>()!=16 || field_offset!(Node,next)!=8{return 1;}return 42;}''')

    def test_module_constants_and_compile_time_comparison(self):
        self.program('layout_constants','''struct Row{pub n:u64;pub byte:u8;}
const SIZE:usize=span_of::<Row>();const OFFSET:usize=field_offset!(Row,byte);
const TOTAL:usize=SIZE*2+OFFSET;const VALID:bool=align_of::<Row>()==8;
pub fn main_entry()->u32{if !VALID || TOTAL!=40{return 1;}return (TOTAL+2) as u32;}''')

    def test_return_argument_and_explicit_numeric_conversion(self):
        self.program('layout_calls','''struct Row{pub n:u64;pub byte:u8;}
fn size()->usize{return span_of::<Row>();}fn plus(value:usize)->usize{return value+26;}
pub fn main_entry()->u32{return plus(size()) as u32;}''')

    def test_direct_layout_query_argument(self):
        self.program('layout_argument','''fn plus(value:usize)->usize{return value+34;}
pub fn main_entry()->u32{return plus(span_of::<u64>()) as u32;}''')

    def test_both_existing_generic_spellings(self):
        self.program('layout_spellings','''struct Row{pub n:u64;}
pub fn main_entry()->u32{if span_of<u64>()!=8 || align_of<Row>()!=8 || stride_of<Row>()!=8{return 1;}return 42;}''')

    def test_offsets_match_actual_generated_addresses(self):
        self.program('layout_actual_offsets','''struct Row{pub first:u8;pub wide:u64;pub tail:u16;}
pub fn main_entry()->u32{let mut row:Row=Row{first:1,wide:2,tail:3};
let base:*mut Row=unsafe{(&mut row) as *mut Row};let field:*mut u64=unsafe{(&mut row.wide) as *mut u64};
let a:usize=unsafe{base as usize};let b:usize=unsafe{field as usize};
if b-a!=field_offset!(Row,wide){return 1;}return 42;}''')

    def test_stride_matches_actual_array_addresses(self):
        self.program('layout_actual_stride','''struct Row{pub first:u8;pub wide:u64;pub tail:u16;}
pub fn main_entry()->u32{let mut rows:[Row;2]=[Row{first:1,wide:2,tail:3};2];
let a:*mut Row=unsafe{(&mut rows[0]) as *mut Row};let b:*mut Row=unsafe{(&mut rows[1]) as *mut Row};
let first:usize=unsafe{a as usize};let second:usize=unsafe{b as usize};
if second-first!=stride_of::<Row>(){return 1;}return 42;}''')

    def test_self_type_in_method(self):
        self.program('layout_self','''struct Row{pub n:u64;pub byte:u8;}
impl Row{pub fn bytes()->usize{return span_of::<Self>();}}
pub fn main_entry()->u32{if Row::bytes()!=16{return 1;}return 42;}''')

    def test_simple_and_payload_enum_layout(self):
        self.program('layout_enums','''enum Flag{Off,On}enum Event{Empty,Value(u64)}
pub fn main_entry()->u32{if span_of::<Flag>()!=4 || align_of::<Flag>()!=4
|| span_of::<Event>()!=16 || align_of::<Event>()!=8 || stride_of::<Event>()!=16{return 1;}return 42;}''')

    def test_forward_record_constant_and_control_flow(self):
        self.program('layout_forward','''const SIZE:usize=span_of::<Later>();
struct Later{pub first:u8;pub wide:u64;}
pub fn main_entry()->u32{let mut total:usize=0;let mut i:u32=0;
while i<2{if align_of::<Later>()==8{total=total+SIZE;}else{return 1;}i=i+1;}
return (total+10) as u32;}''')

    def test_layout_query_does_not_call_constructors(self):
        self.program('layout_pure','''struct Row{pub n:u64;}static mut calls:u32=0;
fn make()->Row{unsafe{calls=calls+1;}return Row{n:0};}
pub fn main_entry()->u32{let size:usize=span_of::<Row>();
if size!=8 || unsafe{calls}!=0{return 1;}return 42;}''')

    def test_array_bound_and_whitespace_in_types(self):
        self.program('layout_array_bound','''struct Row{pub n:u64;}
pub fn main_entry()->u32{if span_of::<[u8;4096]>()!=4096
|| span_of::<[ Row ; 2 ]>()!=16 || align_of::<[ Row ; 2 ]>()!=8{return 1;}return 42;}''')

    def test_native_runtime_layout_constants_match_actual_descriptors(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        sources=[]
        for module in ('results','managed','text','unicode','utf8_buffer','pool','pool_text','text_map'):
            source=(root/f'runtime/native/{module}.sotlas').read_text(encoding='utf-8')
            sources.append('\n'.join(line for line in source.splitlines() if not line.startswith(('module ','import '))))
        self.program('layout_runtime','\n'.join(sources)+'''
pub fn main_entry()->u32{if NATIVE_POOL_SLOT_SIZE!=32 || NATIVE_POOL_CONTROL_SIZE!=56
|| NATIVE_POOL_SLOT_ALIGN!=8 || NATIVE_POOL_CONTROL_ALIGN!=8 || NATIVE_TEXT_MAP_CONTROL_SIZE!=48
|| NATIVE_TEXT_MAP_CONTROL_ALIGN!=8 || NATIVE_TEXT_MAP_ENTRY_SIZE!=56
|| field_offset!(NativePoolSlot,revision)!=8 || field_offset!(NativePoolSlot,length)!=16
|| field_offset!(NativePoolSlot,live)!=24 || field_offset!(NativeTextMap,revision)!=32{return 1;}return 42;}''')

    def test_unknown_layout_is_rejected_in_unreachable_and_uncalled_code(self):
        cases=(
            'pub fn main_entry()->u32{return 42;let n:usize=span_of::<Missing>();}',
            'fn unused()->usize{return align_of::<Missing>();}pub fn main_entry()->u32{return 42;}',
            'const VALUE:usize=if true{8}else{span_of::<Missing>()};pub fn main_entry()->u32{return 42;}',
            'struct Row{pub n:u32;}pub fn main_entry()->u32{return 42;let n:usize=field_offset!(Row,absent);}',
        )
        for index,source in enumerate(cases):
            with self.subTest(index=index):self.compile('layout_dead_'+str(index),source,False)

    def test_ordinary_function_call_with_similar_name_is_preserved(self):
        self.program('layout_ordinary_name','''fn span_of(value:u32)->u32{return value+2;}
pub fn main_entry()->u32{return span_of(40);}''')

    def test_unsupported_layout_annotations_are_not_silently_ignored(self):
        for index,prefix in enumerate(('@packed','@aligned(16)','pub @packed','pub @aligned(32)',
                                       '@repr(packed)','@repr(align(16))')):
            with self.subTest(prefix=prefix):
                self.compile('layout_attribute_'+str(index),prefix+' struct Row{pub a:u8;pub b:u64;}'
                             'pub fn main_entry()->u32{let n:usize=span_of::<Row>();return 42;}',False)

    def test_invalid_types_fields_and_result_types_fail_closed(self):
        for index,expression in enumerate(('span_of::<Missing>()','align_of::<void>()',
                                          'field_offset!(Row,missing)','field_offset!(u32,n)',
                                          'span_of::<[u8;0]>()','span_of::<[Missing;2]>()',
                                          'span_of::<[u8;4097]>()','span_of::<[u8;18446744073709551615]>()',
                                          'field_offset!(Event,tag)','span_of::<[u8;-1]>()',
                                          'span_of::<sole Row>()','span_of::<*mut Missing>()',
                                          'field_offset!(Row,n,extra)','span_of::<u32>(1)')):
            with self.subTest(expression=expression):
                self.compile('layout_reject_'+str(index),'struct Row{pub n:u64;}enum Event{None,Value(u64)}'
                             'pub fn main_entry()->u32{let n:usize='+expression+';return 42;}',False)
        for typ in ('u32','bool','f64'):
            with self.subTest(typ=typ):
                self.compile('layout_result_'+typ,'pub fn main_entry()->u32{let n:'+typ+'=span_of::<u64>();return 42;}',False)


if __name__=='__main__':
    unittest.main()
