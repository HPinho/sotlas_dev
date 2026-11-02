"""Native value-producing if-let decisions share match value semantics."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous
import test_sotlas_native_error_composition as library


class NativePatternValueTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,source):
        self.execute(self.compile(name,source))

    def test_local_return_and_call_argument_positions(self):
        self.program('pattern_value_positions','''enum V{None,Some(u32)}
fn select(v:V)->u32{return if let V::Some(n)=v{n}else{20};}
fn add(a:u32,b:u32)->u32{return a+b;}
pub fn main_entry()->u32{let n:u32=if let V::Some(x)=V::Some(22){x}else{0};
return add(n,if let V::None=V::None{select(V::None)}else{0});}''')

    def test_subject_once_and_lazy_branches(self):
        self.program('pattern_value_once','''enum V{None,Some(u32)}static mut calls:u32=0;
fn source()->V{unsafe{calls=calls+1;}return V::Some(42);}fn bad()->u32{unsafe{calls=100;}return 0;}
pub fn main_entry()->u32{let n:u32=if let V::Some(x)=source(){x}else{bad()};
if unsafe{calls}!=1{return 1;}return n;}''')

    def test_value_blocks_with_locals_and_lifo_defers(self):
        self.program('pattern_value_blocks','''enum V{None,Some(u32)}static mut trace:u32=0;
pub fn main_entry()->u32{let n:u32=if let V::Some(x)=V::Some(40){
let result:u32=x+2;defer{unsafe{trace=trace*10+1;}}defer{unsafe{trace=trace*10+2;}}result
}else{defer{unsafe{trace=999;}}0};if unsafe{trace}!=21{return 1;}return n;}''')

    def test_shadowing_and_parenthesized_nested_value(self):
        self.program('pattern_value_shadow','''enum V{None,Some(u32)}pub fn main_entry()->u32{
let x:u32=22;let n:u32=if let V::Some(x)=V::Some(20){
(if let V::Some(y)=V::Some(x){y}else{0})}else{x};return n+x;}''')

    def test_else_if_chains_and_unselected_conditions(self):
        self.program('pattern_value_chain','''enum V{None,Some(u32)}
fn read(v:V)->u32{return if let V::Some(n)=v{n}else if false{1}else if let V::None=v{22}else{0};}
pub fn main_entry()->u32{return read(V::Some(20))+read(V::None);}''')

    def test_records_returned_by_value(self):
        self.program('pattern_value_record','''struct Pair{pub a:u32;pub b:u32;}enum V{None,Some(Pair)}
fn read(v:V)->Pair{return if let V::Some(p)=v{p}else{Pair{a:20,b:22}};}
pub fn main_entry()->u32{let a:Pair=read(V::Some(Pair{a:20,b:22}));let b:Pair=read(V::None);
if b.a+b.b!=42{return 1;}return a.a+a.b;}''')

    def test_array_returns_assignment_and_iteration(self):
        self.program('pattern_value_array','''enum V{None,Some([u32;2])}
fn read(v:V)->[u32;2]{return if let V::Some(items)=v{items}else{[20,22]};}
pub fn main_entry()->u32{let mut items:[u32;2]=[1,1];items=if let V::Some(xs)=V::Some([20,22]){xs}else{read(V::None)};
let mut sum:u32=0;for n in items{sum=sum+n;}return sum;}''')

    def test_explicit_tags_and_aggregate_enum_results(self):
        self.program('pattern_value_enum','''enum V{None=97,Some(u32)=11}enum R{Bad(u32)=91,Good([u32;2])=3}
fn read(v:V)->R{return if let V::Some(n)=v{R::Good([n,2])}else{R::Bad(42)};}
pub fn main_entry()->u32{if let R::Bad(e)=read(V::None){if e!=42{return 1;}}else{return 2;}
return match read(V::Some(40)){R::Good(xs)=>xs[0]+xs[1],R::Bad(e)=>0};}''')

    def test_scalar_widths_floats_and_boolean_values(self):
        for typ,value,condition in (('u8','42','n==42'),('i64','-4294967297','n==-4294967297'),
                                    ('u64','18446744073709551615','n==18446744073709551615'),
                                    ('f32','1.5','n==1.5'),('f64','2.5','n==2.5'),('bool','true','n')):
            with self.subTest(typ=typ):
                self.program('pattern_value_'+typ,'enum V{None,Some('+typ+')}'
                             'fn read(v:V)->'+typ+'{return if let V::Some(n)=v{n}else{'+value+'};}'
                             'pub fn main_entry()->u32{let n:'+typ+'=read(V::Some('+value+'));if '+condition+'{return 42;}return 1;}')

    def test_early_return_from_selected_value_block(self):
        self.program('pattern_value_return','''enum V{None,Some(u32)}static mut trace:u32=0;
fn read(v:V)->u32{defer{unsafe{trace=trace+10;}}let n:u32=if let V::Some(x)=v{
defer{unsafe{trace=trace+1;}}return x;}else{20};return n;}
pub fn main_entry()->u32{let a:u32=read(V::Some(22));let b:u32=read(V::None);
if unsafe{trace}!=21{return 1;}return a+b;}''')

    def test_error_propagation_from_subject_and_selected_body(self):
        self.program('pattern_value_try','''enum V{None,Some(u32)}enum A{Ok(V),Err(u32)}enum B{Ok(u32),Err(u32)}
fn read(a:A)->B{let n:u32=if let V::Some(x)=a?{x}else{20};return B::Ok(n);}
pub fn main_entry()->u32{let r:B=if let B::Ok(n)=read(A::Ok(V::Some(42))){B::Ok(n)}else{B::Err(1)};
if let B::Err(e)=read(A::Err(42)){if e!=42{return 1;}}else{return 2;}
return match r{B::Ok(n)=>n,B::Err(e)=>0};}''')

    def test_expression_result_can_feed_question_mark(self):
        self.program('pattern_value_outer_try','''enum V{None,Some(u32)}enum R{Ok(u32),Err(u32)}
fn read(v:V)->R{let n:u32=(if let V::Some(x)=v{R::Ok(x)}else{R::Err(42)})?;return R::Ok(n);}
pub fn main_entry()->u32{if let R::Err(e)=read(V::None){return e;}return 1;}''')

    def test_payload_snapshot_survives_source_mutation(self):
        self.program('pattern_value_snapshot','''enum V{None,Some([u32;2])}pub fn main_entry()->u32{
let mut source:V=V::Some([20,22]);let result:[u32;2]=if let V::Some(xs)=source{source=V::None;xs}else{[0,0]};
return result[0]+result[1];}''')

    def test_alternatives_record_fields_and_array_patterns(self):
        self.program('pattern_value_shapes','''struct Pair{pub xs:[u32;2];}enum V{A(Pair),B(Pair),None}
fn read(v:V)->u32{return if let V::A(Pair{xs:[a,b]})|V::B(Pair{xs:[a,b]})=v{a+b}else{0};}
pub fn main_entry()->u32{return read(V::B(Pair{xs:[20,22]}));}''')

    def test_owned_result_moves_on_only_the_selected_branch(self):
        self.program('pattern_value_owner','''struct Box{pub n:u32;}enum V{None,Some(u32)}
fn select(v:V,a:sole Box,b:sole Box)->sole Box{return if let V::Some(n)=v{a}else{b};}
pub fn main_entry()->u32{let a:sole Box=Box{n:42};let b:sole Box=Box{n:0};
let result:sole Box=select(V::Some(1),a,b);return result.n;}''')

    def test_missing_else_tail_and_mismatched_types_reject(self):
        for i,expression in enumerate(('if let V::Some(x)=v{x}',
                                       'if let V::Some(x)=v{let y:u32=x;}else{0}',
                                       'if let V::Some(x)=v{x}else{true}',
                                       'if let V::Some(x)=v{true}else{x}')):
            with self.subTest(expression=expression):
                self.compile('pattern_value_bad_'+str(i),'enum V{None,Some(u32)}pub fn main_entry()->u32{let v:V=V::Some(42);let n:u32='+expression+';return n;}',False)

    def test_scoped_bindings_cannot_escape_to_else_or_after_expression(self):
        for i,body in enumerate(('let n:u32=if let V::Some(x)=v{x}else{x};return n;',
                                'let n:u32=if let V::Some(x)=v{x}else{0};return x;')):
            self.compile('pattern_value_scope_'+str(i),'enum V{None,Some(u32)}pub fn main_entry()->u32{let v:V=V::Some(42);'+body+'}',False)

    def test_incompatible_nominal_results_and_owner_merges_reject(self):
        self.compile('pattern_value_nominal','''struct A{pub n:u32;}struct B{pub n:u32;}enum V{None,Some(u32)}
pub fn main_entry()->u32{let a:A=if let V::Some(x)=V::Some(42){A{n:x}}else{B{n:0}};return 42;}''',False)
        self.compile('pattern_value_move','''struct Box{pub n:u32;}enum V{None,Some(u32)}fn take(v:sole Box)->u32{return v.n;}
pub fn main_entry()->u32{let owner:sole Box=Box{n:42};let n:u32=if let V::Some(x)=V::Some(1){take(owner)}else{0};return owner.n;}''',False)

    def test_unscoped_jumps_and_resource_payloads_reject(self):
        self.compile('pattern_value_break','''enum V{None,Some(u32)}pub fn main_entry()->u32{
return if let V::Some(x)=V::Some(42){break;x}else{0};}''',False)
        self.compile('pattern_value_pointer','''enum V{None,Some(*const u32)}pub fn main_entry()->u32{
return if let V::Some(x)=V::None{42}else{0};}''',False)

    def test_native_readings_application(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'examples/native_pattern_values/main.sotlas').read_text(encoding='utf-8')
        library.NativeErrorCompositionTests.library(self,'pattern_value_readings',
            '\n'.join(line for line in source.splitlines() if not line.startswith(('module ','import '))))


if __name__ == '__main__':
    unittest.main()
