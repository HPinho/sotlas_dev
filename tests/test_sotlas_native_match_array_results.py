"""Contextual inline array results with native branch/copy/cleanup semantics."""
import unittest
import test_sotlas_native_i32 as previous


class NativeMatchArrayResultTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self,name,source):
        self.execute(self.compile(name,source))

    def test_match_results_from_stored_arrays(self):
        self.program('array_result_select','''pub fn main_entry()->u32{
let a:[u32;2]=[20,22];let b:[u32;2]=[1,2];
let chosen:[u32;2]=match true{true=>a,false=>b};return match chosen{[x,y]=>x+y};}''')
        self.program('array_result_array_subject','''pub fn main_entry()->u32{
let source:[u32;2]=[20,22];let chosen:[u32;2]=match source{[0,_]=>[0;2],all=>all};
return chosen[0]+chosen[1];}''')

    def test_literals_and_repetition_for_all_scalar_types(self):
        for typ,value,result in (('u8','21','(a+b) as u32'),('i8','-21','(-a-b) as u32'),
                                ('u16','21','(a+b) as u32'),('i16','-21','(-a-b) as u32'),
                                ('u32','21','a+b'),('i32','-21','(-a-b) as u32'),
                                ('u64','21','(a+b) as u32'),('i64','-21','(-a-b) as u32'),
                                ('f32','21.0','(a+b) as u32'),('f64','21.0','(a+b) as u32'),
                                ('bool','true','if a && b{42}else{0}')):
            with self.subTest(typ=typ):
                self.program('array_result_'+typ,f'''pub fn main_entry()->u32{{
let chosen:[{typ};2]=match false{{true=>[{value};2],false=>[{value},{value}]}};
return match chosen{{[a,b]=>{result}}};}}''')

    def test_conditional_array_results_and_nested_matches(self):
        self.program('array_result_conditional','''pub fn main_entry()->u32{
let chosen:[u32;2]=if false{[1,2]}else{match true{true=>[20,22],false=>[0;2]}};
let other:[u32;2]=match true{true=>if true{chosen}else{[0;2]},false=>[0;2]};
return match other{[a,b]=>a+b};}''')

    def test_only_selected_branch_runs_and_repeat_evaluates_once(self):
        self.program('array_result_order','''static mut calls:u32=0;
fn next()->u32{unsafe{calls=calls+1;return calls;}}
pub fn main_entry()->u32{let a:[u32;2]=match true{true=>[next();2],false=>[next(),next()]};
let b:[u32;2]=if false{[next();2]}else{[next(),next()]};
if a[0]!=1 || a[1]!=1 || b[0]!=2 || b[1]!=3 || unsafe{calls}!=3{return 1;}return 42;}''')

    def test_result_copy_is_independent_from_source(self):
        self.program('array_result_copy','''pub fn main_entry()->u32{
let mut source:[u32;2]=[20,22];let copy:[u32;2]=match true{_=>source};
source[0]=0;return copy[0]+copy[1];}''')

    def test_value_block_copies_result_before_defer(self):
        self.program('array_result_defer','''pub fn main_entry()->u32{
let mut source:[u32;2]=[20,22];let mut trace:u32=0;
let copy:[u32;2]=match true{true=>{defer{trace=trace*10+1;}
defer{source[0]=0;trace=trace*10+2;}source},false=>[0;2]};
if source[0]!=0 || trace!=21{return 1;}return copy[0]+copy[1];}''')

    def test_value_block_locals_and_nested_array_yields(self):
        self.program('array_result_block','''pub fn main_entry()->u32{
let selected:[u32;2]=match true{true=>{let local:[u32;2]=[20,22];
match false{true=>[0;2],false=>local}},false=>[0;2]};
return selected[0]+selected[1];}''')

    def test_early_return_uses_enclosing_scalar_abi(self):
        self.program('array_result_early','''fn choose(early:bool)->u32{
let selected:[u32;2]=match early{true=>{return 42;},false=>[20,22]};
return selected[0]+selected[1];}
pub fn main_entry()->u32{if choose(true)!=42{return 1;}return choose(false);}''')

    def test_all_arms_return_without_a_fake_array_value(self):
        self.program('array_result_all_return','''fn choose(flag:bool)->u32{
let selected:[u32;2]=match flag{true=>{return 42;},false=>{return 42;}};
return 0;}pub fn main_entry()->u32{return choose(false);}''')

    def test_record_array_results_preserve_nominal_type_and_copy(self):
        self.program('array_result_records','''struct Row{pub n:u32;}
pub fn main_entry()->u32{let mut rows:[Row;2]=[Row{n:20},Row{n:22}];
let selected:[Row;2]=match true{true=>rows,false=>[Row{n:0};2]};
rows[0].n=0;return match selected{[Row{n:a},Row{n:b}]=>a+b};}''')

    def test_contextual_struct_field_at_nonzero_offset(self):
        self.program('array_result_field','''struct Packet{pub prefix:u8;pub data:[u32;2];pub suffix:u64;}
pub fn main_entry()->u32{let p:Packet=Packet{prefix:7,data:match false{true=>[0;2],false=>[20,22]},suffix:9};
if p.prefix!=7 || p.suffix!=9{return 1;}return p.data[0]+p.data[1];}''')

    def test_record_array_field_conditional_and_internal_return(self):
        self.program('array_result_return_container','''struct Row{pub n:u32;}struct Table{pub rows:[Row;2];}
fn table(flag:bool)->Table{return Table{rows:if flag{[Row{n:21};2]}else{[Row{n:0};2]}};}
pub fn main_entry()->u32{let t:Table=table(true);return t.rows[0].n+t.rows[1].n;}''')

    def test_enum_constructor_array_argument(self):
        self.program('array_result_payload','''enum Packet{None,Data([u32;2]),}
pub fn main_entry()->u32{let p:Packet=Packet::Data(match true{true=>[20,22],false=>[0;2]});
return match p{Packet::Data([a,b])=>a+b,Packet::None=>0};}''')
        self.program('array_result_payload_subject','''enum Source{None,Value(u32),}
pub fn main_entry()->u32{let selected:[u32;2]=match Source::Value(21){
Source::None=>[0;2],Source::Value(n)=>[n;2]};return selected[0]+selected[1];}''')

    def test_record_field_and_global_array_sources(self):
        self.program('array_result_sources','''static mut numbers:[u32;2]=0;
struct Row{pub values:[u32;2];}pub fn main_entry()->u32{unsafe{numbers[0]=20;numbers[1]=22;}
let row:Row=Row{values:[20,22]};let selected:[u32;2]=match false{true=>row.values,false=>unsafe{numbers}};
return selected[0]+selected[1];}''')

    def test_guard_fallthrough_and_alternatives(self):
        self.program('array_result_guard','''static mut calls:u32=0;
fn reject()->bool{unsafe{calls=calls+1;}return false;}
pub fn main_entry()->u32{let selected:[u32;2]=match 1 as u32{
0|1|2 if reject()=>[0;2],_=>[20,22]};if unsafe{calls}!=1{return 1;}return selected[0]+selected[1];}''')

    def test_array_result_elements_keep_branch_sensitive_owner_moves(self):
        prefix='struct Box{pub n:u32;}fn consume(b:sole Box)->u32{return b.n;}'
        self.program('array_result_owner',prefix+'''pub fn main_entry()->u32{
let b:sole Box=Box{n:42};let result:[u32;2]=match true{
true=>[consume(b),0],false=>[consume(b),0]};return result[0]+result[1];}''')
        self.compile('array_result_maybe_moved',prefix+'''pub fn main_entry()->u32{
let b:sole Box=Box{n:42};let result:[u32;2]=match true{
true=>[consume(b),0],false=>[0;2]};return b.n;}''',False)

    def test_maximum_array_result_bound(self):
        self.program('array_result_256','''pub fn main_entry()->u32{
let chosen:[u64;256]=match true{true=>[21;256],false=>[0;256]};
return match chosen{[a,..,b]=>(a+b) as u32};}''')

    def test_wrong_arms_are_rejected_even_when_not_selected(self):
        for index,arm in enumerate(('[1]','[1,2,3]','[1;3]','[true,false]','[1.0,2.0]')):
            with self.subTest(arm=arm):
                self.compile('array_result_wrong_'+str(index),'''pub fn main_entry()->u32{
let a:[u32;2]=match true{true=>[20,22],false=>'''+arm+'''};return 42;}''',False)
        self.compile('array_result_nominal','''struct A{pub n:u32;}struct B{pub n:u32;}
pub fn main_entry()->u32{let a:[A;2]=match true{true=>[A{n:21};2],false=>[B{n:21};2]};return 42;}''',False)

    def test_non_exhaustive_non_boolean_and_missing_yield_rejected(self):
        for index,expression in enumerate(('match true{true=>[20,22]}',
                                          'if 1{[20,22]}else{[0;2]}',
                                          'match true{true=>{let n:u32=42;},false=>[0;2]}')):
            with self.subTest(expression=expression):
                self.compile('array_result_control_'+str(index),'pub fn main_entry()->u32{let a:[u32;2]='+expression+';return 42;}',False)

    def test_resource_arrays_and_general_array_abi_remain_rejected(self):
        cases=(
            'pub fn main_entry()->u32{let p:[*mut u8;2]=match true{_=>[null;2]};return 42;}',
            'pub fn main_entry()->u32{let a:[u32;257]=match true{_=>[0;257]};return 42;}',
            'fn make()->[u32;2]{return match true{_=>[20,22]};}pub fn main_entry()->u32{return 42;}',
            'pub fn main_entry()->u32{let mut a:[u32;2]=0;a=match true{_=>[20,22]};return 42;}',
        )
        for index,source in enumerate(cases):
            with self.subTest(index=index):
                self.compile('array_result_unsupported_'+str(index),source,False)


if __name__ == '__main__':
    unittest.main()
