"""Standalone fixed-array match subjects through the Sotlas native compiler."""
import itertools
import os
import subprocess
import unittest
import test_sotlas_native_i32 as previous


class NativeMatchArraySubjectTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_local_array_exact_bindings_all_scalar_widths(self):
        for typ, value in (('u8','21'),('u16','21'),('u32','21'),('u64','21'),
                           ('i8','21'),('i16','21'),('i32','21'),('i64','21'),
                           ('f32','21.0'),('f64','21.0')):
            with self.subTest(typ=typ):
                self.program('array_subject_'+typ,f'''pub fn main_entry()->u32{{
let values:[{typ};2]=[{value};2];return match values{{[a,b]=>(a+b) as u32}};}}''')

    def test_prefix_suffix_and_statement_forms(self):
        self.program('array_subject_rest','''pub fn main_entry()->u32{
let values:[u32;3]=[20,99,22];match values{[a,..,b]=>{return a+b;}}}''')

    def test_whole_capture_without_element_patterns(self):
        self.program('array_subject_whole','''pub fn main_entry()->u32{
let values:[u32;2]=[20,22];return match values{all=>all[0]+all[1]};}''')

    def test_guarded_whole_capture_cannot_mutate_next_arm_snapshot(self):
        self.program('array_subject_whole_guard','''fn reject(p:*mut u32)->bool{unsafe{*p=0;}return false;}
pub fn main_entry()->u32{let values:[u32;2]=[20,22];
return match values{all if reject(unsafe{all as *mut u32})=>0,[a,b]=>a+b};}''')

    def test_guard_mutating_original_does_not_change_snapshot(self):
        self.program('array_subject_original_guard','''fn reject(p:*mut u32)->bool{unsafe{*p=0;}return false;}
pub fn main_entry()->u32{let mut values:[u32;2]=[20,22];let p:*mut u32=unsafe{values as *mut u32};
let result:u32=match values{[20,_] if reject(p)=>0,[a,b]=>a+b};
if values[0]!=0{return 1;}return result;}''')

    def test_record_array_subject_and_nested_fields(self):
        self.program('array_subject_records','''struct Row{pub value:u32;pub flags:[bool;2];}
pub fn main_entry()->u32{let values:[Row;2]=[Row{value:20,flags:[true,false]},Row{value:22,flags:[true,true]}];
return match values{[Row{value:a,flags:[true,..]},Row{value:b,..}]=>a+b,_=>0};}''')

    def test_whole_record_array_capture_can_be_indexed(self):
        self.program('array_subject_record_whole','''struct Row{pub value:u32;}
pub fn main_entry()->u32{let values:[Row;2]=[Row{value:21};2];
return match values{all=>all[0].value+all[1].value};}''')
        self.program('array_subject_record_container','''struct Row{pub value:u32;}
struct Table{pub rows:[Row;2];}pub fn main_entry()->u32{let values:[Row;2]=[Row{value:21};2];
let copy:Table=match values{all=>Table{rows:all}};
return copy.rows[0].value+copy.rows[1].value;}''')

    def test_field_subject_evaluates_receiver_once(self):
        self.program('array_subject_receiver','''static mut calls:u32=0;
struct Table{pub items:[u32;2];}fn table()->Table{unsafe{calls=calls+1;}return Table{items:[20,22]};}
pub fn main_entry()->u32{let n:u32=match table().items{[a,b]=>a+b};
if unsafe{calls}!=1{return 1;}return n;}''')

    def test_nested_field_and_captured_record_subjects(self):
        self.program('array_subject_nested_fields','''struct Row{pub items:[u32;2];}
struct Table{pub row:Row;}pub fn main_entry()->u32{
let t:Table=Table{row:Row{items:[20,22]}};
return match t{Table{row}=>match row.items{[a,b]=>a+b}};}''')

    def test_borrowed_record_field_subject(self):
        self.program('array_subject_borrowed_field','''struct Table{pub items:[u32;2];}
fn read(t:whisper Table)->u32{return match t.items{[a,b]=>a+b};}
pub fn main_entry()->u32{let t:sole Table=Table{items:[20,22]};return read(t);}''')

    def test_array_capture_can_be_matched_again(self):
        self.program('array_subject_nested','''enum Data{Values([u32;2]),}
pub fn main_entry()->u32{let d:Data=Data::Values([20,22]);
return match d{Data::Values(values)=>match values{whole=>match whole{[a,b]=>a+b}}};}''')

    def test_nested_subject_in_alternative_arm(self):
        self.program('array_subject_nested_or','''enum Data{Left([u32;2]),Right([u32;2]),}
pub fn main_entry()->u32{let d:Data=Data::Right([20,22]);
return match d{Data::Left(values)|Data::Right(values)=>match values{[a,b]=>a+b}};}''')

    def test_alternatives_run_guard_once(self):
        self.program('array_subject_or_guard','''static mut calls:u32=0;
fn reject()->bool{unsafe{calls=calls+1;}return false;}
pub fn main_entry()->u32{let values:[u32;2]=[0,42];return match values{
([0,n]|[n,42]) if reject()=>0,[a,b]=>a+b+unsafe{calls}-1};}''')
        self.program('array_subject_whole_or_guard','''static mut calls:u32=0;
fn reject()->bool{unsafe{calls=calls+1;}return false;}
pub fn main_entry()->u32{let values:[u32;2]=[20,22];return match values{
all|all if reject()=>0,[a,b]=>a+b+unsafe{calls}-1};}''')

    def test_typed_capture_and_shadowing(self):
        self.program('array_subject_shadow','''fn sum(a:u16,b:u16)->u32{return (a+b) as u32;}
pub fn main_entry()->u32{let a:u64=1;let values:[u16;2]=[20,22];
let result:u32=match values{[a,b]=>sum(a,b)};return result+a as u32-1;}''')

    def test_float_zero_and_nan_fallback(self):
        self.program('array_subject_float','''pub fn main_entry()->u32{let values:[f64;2]=[-0.0,1.5];
return match values{[0.0,1.0..=2.0]=>42,_=>0};}''')
        self.program('array_subject_nan','''pub fn main_entry()->u32{let values:[f32;2]=[0.0/0.0,1.5];
return match values{[(..),1.0..=2.0]=>0,[a,b]=>if a!=a && b==1.5{42}else{0}};}''')

    def test_array_match_cleanup_and_loop_edges(self):
        self.program('array_subject_defer','''pub fn main_entry()->u32{let values:[u32;2]=[20,22];
let mut trace:u32=0;let mut i:u32=0;while i<2{i=i+1;match values{
[a,b]=>{defer{trace=trace+1;}if i==1{continue;}if a+b!=42{return 0;}break;}}}
return trace+40;}''')

    def test_maximum_subject_and_sparse_pattern(self):
        self.program('array_subject_256','''pub fn main_entry()->u32{let values:[u64;256]=[21;256];
return match values{[a,..,b]=>(a+b) as u32};}''')

    def test_whole_capture_indexing_keeps_runtime_bounds(self):
        obj=self.compile('array_subject_bounds','''fn index()->u32{return 2;}
pub fn main_entry()->u32{let values:[u32;2]=[20,22];return match values{all=>all[index()]};}''')
        image=self.link_image(obj)
        if os.name == 'nt':
            code,_=previous.NativeI32Tests.windows_process_exit_code(self,image)
        else:
            code=subprocess.run([str(image)],capture_output=True,timeout=15).returncode
        self.assertNotEqual(code,0)
        self.assertNotEqual(code,42)

    def test_global_subject_preserves_checked_static_access(self):
        self.program('array_subject_global','''static mut values:[u32;2]=0;
pub fn main_entry()->u32{unsafe{values[0]=20;values[1]=22;}
return unsafe{match values{[a,b]=>a+b}};}''')

    def test_boolean_array_coverage_against_all_512_rectangle_unions(self):
        domain=set(itertools.product((False,True),repeat=2));rectangles=[]
        for a,b in itertools.product(('true','false','_'),repeat=2):
            covered={p for p in domain if (a=='_' or p[0]==(a=='true')) and (b=='_' or p[1]==(b=='true'))}
            rectangles.append((a,b,covered))
        for mask in range(512):
            rows=[r for index,r in enumerate(rectangles) if mask&(1<<index)]
            covered=set().union(*(r[2] for r in rows))
            arms=','.join('['+a+','+b+']=>42' for a,b,_ in rows)
            source='pub fn main_entry()->u32{let values:[bool;2]=[true,false];return match values{'+arms+'};}'
            with self.subTest(mask=mask):
                self.compile('array_subject_oracle_'+str(mask),source,covered==domain)

    def test_invalid_shapes_types_scope_and_scalar_patterns_rejected(self):
        prefix='pub fn main_entry()->u32{let values:[u32;2]=[20,22];'
        for index,body in enumerate((
            'return match values{[a]=>a};}',
            'return match values{[a,b,c]=>a};}',
            'return match values{42=>42,_=>0};}',
            'return match values{0..=>42,_=>0};}',
            'return match values{[true,_]=>42,_=>0};}',
            'return match values{[a,a]=>a};}',
            'match values{[a,b]=>{}}return a;}',
            'return match values{all=>{all[0]=42;all[0]}};}',
            'return match values{[a,b]=>{a=42;a+b}};}',
        )):
            with self.subTest(index=index):
                self.compile('array_subject_invalid_'+str(index),prefix+body,False)

    def test_general_array_abi_and_resource_subjects_remain_rejected(self):
        cases=(
            'fn read(v:[u32;2])->u32{return match v{[a,b]=>a+b};}pub fn main_entry()->u32{return 42;}',
            'fn make()->[u32;2]{let a:[u32;2]=[20,22];return a;}pub fn main_entry()->u32{return 42;}',
            'pub fn main_entry()->u32{let p:[*mut u8;2]=0;return match p{[..]=>42};}',
            'struct R{pub p:*mut u8;}pub fn main_entry()->u32{let a:[R;2]=[R{p:null};2];return match a{[..]=>42};}',
            'pub fn main_entry()->u32{let a:[u32;257]=[0;257];return match a{[..]=>42};}',
            'pub fn main_entry()->u32{return match [20,22]{[a,b]=>a+b};}',
            'pub fn main_entry()->u32{let a:[u32;2]=[20,22];let b:[u32;2]=[21;2];return match if true{a}else{b}{[x,y]=>x+y};}',
        )
        for index,source in enumerate(cases):
            with self.subTest(index=index):
                self.compile('array_subject_abi_invalid_'+str(index),source,False)


if __name__ == '__main__':
    unittest.main()
