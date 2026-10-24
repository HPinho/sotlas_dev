"""Native inline array patterns, product coverage and independent captures."""
import itertools
import unittest
import test_sotlas_native_i32 as previous


class NativeMatchArrayPatternTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_exact_scalar_bindings_preserve_every_width(self):
        for typ, value in (('u8','21'),('u16','21'),('u32','21'),('u64','21'),
                           ('i8','21'),('i16','21'),('i32','21'),('i64','21'),
                           ('f32','21.0'),('f64','21.0')):
            with self.subTest(typ=typ):
                self.program('array_pattern_'+typ,f'''enum V{{Data([{typ};2]),}}
pub fn main_entry()->u32{{let v:V=V::Data([{value};2]);
return match v{{V::Data([a,b])=>(a+b) as u32}};}}''')

    def test_prefix_suffix_and_empty_rest(self):
        for pattern, result in (('[a,..,b]','a+b'),('[..,a,b]','a+b-3'),
                                ('[a,b,..]','a+b-1'),('[..]','42'),
                                ('[a,b,c,..]','a+b+c-23'),('[a,..,b,c]','a+b+c-23')):
            with self.subTest(pattern=pattern):
                self.program('array_rest_'+str(len(pattern))+str(len(result)),'''enum V{Data([u32;3]),}
pub fn main_entry()->u32{let v:V=V::Data([20,23,22]);
return match v{V::Data('''+pattern+')=>'+result+'''};}''')

    def test_named_record_field_and_nested_record_elements(self):
        self.program('array_record_pattern','''struct Point{pub x:u32;pub y:u32;}
struct Table{pub rows:[Point;2];pub active:bool;}
pub fn main_entry()->u32{let t:Table=Table{rows:[Point{x:20,y:1},Point{x:22,y:2}],active:true};
return match t{Table{rows:[Point{x:a,..},Point{x:b,..}],..}=>a+b};}''')

    def test_nested_enum_and_array_combinations(self):
        self.program('array_nested','''enum Inner{Data([u32;2]),}enum Outer{None,Some(Inner),}
pub fn main_entry()->u32{let v:Outer=Outer::Some(Inner::Data([20,22]));
return match v{Outer::Some(Inner::Data([a,b]))=>a+b,Outer::None=>0};}''')

    def test_array_of_records_with_nested_array_patterns(self):
        self.program('array_nested_record_arrays','''struct Row{pub data:[u32;2];}
enum V{Rows([Row;2]),}pub fn main_entry()->u32{
let v:V=V::Rows([Row{data:[20,22]};2]);
return match v{V::Rows([Row{data:[a,b]},..])=>a+b};}''')

    def test_filters_constants_and_open_ranges(self):
        self.program('array_filter','''const LIMIT:u32=20;enum V{Data([u32;2]),}
fn read(v:V)->u32{return match v{V::Data([..LIMIT,_])=>0,
V::Data([LIMIT..,0..=21])=>0,V::Data([LIMIT..,22..])=>42};}
pub fn main_entry()->u32{return read(V::Data([20,22]));}''')

    def test_alternatives_distribute_and_guard_runs_once(self):
        self.program('array_or_guard','''static mut calls:u32=0;
fn reject()->bool{unsafe{calls=calls+1;}return false;}
enum V{Data([u32;2]),}
pub fn main_entry()->u32{let v:V=V::Data([20,22]);return match v{
V::Data([(20|20),n]) if reject()=>0,V::Data([a,b])=>a+b+unsafe{calls}-1};}''')

    def test_array_alternatives_bind_same_typed_names_at_different_positions(self):
        self.program('array_or_positions','''enum V{Data([u32;2]),}
pub fn main_entry()->u32{let v:V=V::Data([0,42]);
return match v{V::Data(([0,n]|[n,0]))=>n,_=>0};}''')

    def test_record_capture_copy_survives_guard_mutation(self):
        self.program('array_record_guard_copy','''struct R{pub n:u32;}enum V{Data([R;2]),}
fn reject(p:*mut R)->bool{unsafe{(*p).n=0;}return false;}
pub fn main_entry()->u32{let v:V=V::Data([R{n:20},R{n:22}]);
return match v{V::Data([a,_]) if reject(unsafe{(&mut a) as *mut R})=>0,
V::Data([R{n:a},R{n:b}])=>a+b};}''')

    def test_element_binding_has_type_in_call_and_record_access(self):
        self.program('array_binding_type','''struct R{pub n:u32;}enum V{Data([R;2]),}
fn read(r:R)->u32{return r.n;}fn add(a:u16,b:u16)->u32{return (a+b) as u32;}
enum N{Data([u16;2]),}
pub fn main_entry()->u32{let v:V=V::Data([R{n:20},R{n:22}]);
let result:u32=match v{V::Data([a,b])=>read(a)+b.n};
let n:N=N::Data([20,22]);if match n{N::Data([a,b])=>add(a,b)}!=42{return 1;}return result;}''')

    def test_owned_subject_and_value_block_defer(self):
        self.program('array_owner_cleanup','''static mut trace:u32=0;enum V{Data([u32;2]),}
fn consume(v:sole V)->u32{return match v{V::Data([a,b])=>a+b};}
pub fn main_entry()->u32{let v:sole V=V::Data([20,22]);let n:u32=match v{
V::Data([a,b])=>{defer{unsafe{trace=1;}}a+b}};
if unsafe{trace}!=1 || n!=42{return 1;}return consume(v);}''')

    def test_boolean_product_coverage_checks_all_512_unions(self):
        domain=set(itertools.product((False,True),repeat=2))
        rectangles=[]
        for left,right in itertools.product(('true','false','_'),repeat=2):
            values={pair for pair in domain
                    if (left=='_' or pair[0]==(left=='true'))
                    and (right=='_' or pair[1]==(right=='true'))}
            rectangles.append((left,right,values))
        for mask in range(512):
            rows=[r for index,r in enumerate(rectangles) if mask&(1<<index)]
            covered=set().union(*(r[2] for r in rows))
            source='enum V{Data([bool;2]),}pub fn main_entry()->u32{let v:V=V::Data([true,false]);return match v{'
            source+=','.join('V::Data(['+a+','+b+'])=>42' for a,b,_ in rows)+'};}'
            with self.subTest(mask=mask):
                self.compile('array_coverage_'+str(mask),source,covered==domain)

    def test_float_patterns_preserve_nan_fallback(self):
        self.program('array_float','''enum V{Data([f64;2]),}
pub fn main_entry()->u32{let v:V=V::Data([-0.0,1.5]);return match v{
V::Data([0.0,1.0..=2.0])=>42,V::Data([_,_])=>0};}''')
        self.compile('array_float_nan_gap','''enum V{Data([f32;2]),}pub fn main_entry()->u32{
let v:V=V::Data([0.0;2]);return match v{V::Data([(..),(..)])=>42};}''',False)
        self.program('array_float_nan_runtime','''enum V{Data([f64;2]),}
pub fn main_entry()->u32{let v:V=V::Data([0.0/0.0,1.5]);return match v{
V::Data([(..),1.0..=2.0])=>0,V::Data([a,b])=>if a!=a && b==1.5{42}else{0}};}''')

    def test_rest_coverage_tracks_actual_suffix_offset(self):
        self.program('array_rest_coverage','''enum V{Data([bool;3]),}
fn read(v:V)->u32{return match v{
V::Data([true,..,true])=>1,V::Data([true,..,false])=>20,
V::Data([false,..,true])=>22,V::Data([false,..,false])=>2};}
pub fn main_entry()->u32{return read(V::Data([true,true,false]))+
read(V::Data([false,false,true]));}''')
        self.compile('array_rest_hole','''enum V{Data([bool;3]),}pub fn main_entry()->u32{
let v:V=V::Data([true,false,false]);return match v{
V::Data([true,..,true])=>42,V::Data([false,..,false])=>0};}''',False)

    def test_maximum_array_length_uses_sparse_pattern_view(self):
        self.program('array_rest_256','''enum V{Data([u32;256]),}
pub fn main_entry()->u32{let v:V=V::Data([21;256]);
return match v{V::Data([a,..,b])=>a+b};}''')

    def test_element_constants_and_record_field_arrays_keep_scope(self):
        self.program('array_constant_and_scope','''const EXPECTED:u16=21;
struct R{pub data:[u16;2];}pub fn main_entry()->u32{let a:u32=1;
let r:R=R{data:[21;2]};let n:u32=match r{R{data:[EXPECTED,a]}=>a as u32,_=>0};
return n+20+a;}''')

    def test_statement_match_and_continue_cleanup(self):
        self.program('array_statement_loop','''enum V{Data([u32;2]),}
pub fn main_entry()->u32{let v:sole V=V::Data([20,22]);let mut step:u32=0;
let mut trace:u32=0;while step<2{step=step+1;match v{
V::Data([a,b])=>{defer{trace=trace+1;}if step==1{continue;}if a+b!=42{return 0;}}}}
return trace+40;}''')

    def test_total_rest_unreachable_arm_and_guard_holes_rejected(self):
        prefix='enum V{Data([bool;2]),}pub fn main_entry()->u32{let v:V=V::Data([true;2]);return match v{'
        for index, arms in enumerate((
            'V::Data([..])=>42,V::Data([true,_])=>0',
            'V::Data([true,_]) if true=>42,V::Data([false,_])=>0',
        )):
            with self.subTest(index=index):
                self.compile('array_unreachable_'+str(index),prefix+arms+'};}',False)

    def test_shape_binding_scope_and_type_errors_rejected(self):
        prefix='enum V{Data([u32;2]),}pub fn main_entry()->u32{let v:V=V::Data([21;2]);'
        for index, body in enumerate((
            'return match v{V::Data([])=>42};}',
            'return match v{V::Data([a])=>a};}',
            'return match v{V::Data([a,b,c])=>a};}',
            'return match v{V::Data([a,..,b,c])=>a};}',
            'return match v{V::Data([..,..])=>42};}',
            'return match v{V::Data([a,a])=>a};}',
            'return match v{V::Data(([a,b]|[a,_]))=>a};}',
            'return match v{V::Data([true,_])=>42,_=>0};}',
            'match v{V::Data([a,b])=>{}}return a;}',
            'return match v{V::Data([a,b])=>{a=42;a+b}};}',
            'return match v{V::Data([a;2])=>a};}',
        )):
            with self.subTest(index=index):
                self.compile('array_invalid_'+str(index),prefix+body,False)

    def test_nominal_elements_and_alternative_binding_types_rejected(self):
        cases=(
            '''struct A{pub n:u32;}struct B{pub n:u32;}enum V{Data([A;2]),}
pub fn main_entry()->u32{let v:V=V::Data([A{n:21};2]);
return match v{V::Data([B{n:a},B{n:b}])=>a+b};}''',
            '''enum V{A([u32;2]),B([f32;2]),}pub fn main_entry()->u32{
let v:V=V::A([21;2]);return match v{V::A([a,..])|V::B([a,..])=>42};}''',
            '''pub fn main_entry()->u32{let a:[u32;2]=0;return match a{[x,y]=>x+y};}''',
        )
        for index,source in enumerate(cases):
            with self.subTest(index=index):
                self.compile('array_nominal_invalid_'+str(index),source,False)


if __name__ == '__main__':
    unittest.main()
