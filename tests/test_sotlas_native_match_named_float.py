"""Native named record patterns and IEEE float-pattern execution contracts."""
import unittest
import test_sotlas_native_i32 as previous


class NativeMatchNamedFloatTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_root_record_reorders_fields_and_binds_shorthand(self):
        self.program('named_root', '''struct Point{pub x:u32;pub y:u32;}
pub fn main_entry()->u32{let p:Point=Point{x:20,y:22};return match p{Point{y,x}=>x+y};}''')

    def test_rest_and_renamed_fields(self):
        self.program('named_rest', '''struct Point{pub x:u32;pub y:u32;}
fn read(p:Point)->u32{return match p{Point{x:n,..}=>n};}
pub fn main_entry()->u32{return read(Point{x:42,y:1});}''')
        self.program('named_empty_rest', '''struct Point{pub x:u32;pub y:u32;}
pub fn main_entry()->u32{return match Point{x:0,y:1}{Point{..}=>42};}''')
        self.program('named_integer_open_end', '''struct Point{pub x:u32;}pub fn main_entry()->u32{
let p:Point=Point{x:42};return match p{Point{x:0..}=>42};}''')

    def test_named_fields_inside_variants_and_nested_records(self):
        self.program('named_nested', '''struct Point{pub x:u32;pub y:bool;}
struct Wrapper{pub point:Point;pub ignored:u32;}enum V{Empty,Data(Wrapper)}
fn read(v:V)->u32{return match v{
V::Data(Wrapper{point:Point{y:true,x:n},..})=>n,
V::Data(Wrapper{point:Point{y:false,..},..})=>0,V::Empty=>0};}
pub fn main_entry()->u32{return read(V::Data(Wrapper{point:Point{x:42,y:true},ignored:9}));}''')
        declarations=['struct R0{pub value:u32;}']
        value='R0{value:42}'
        pattern='R0{value:n}'
        for depth in range(1,21):
            declarations.append('struct R'+str(depth)+'{pub child:R'+str(depth-1)+';}')
            value='R'+str(depth)+'{child:'+value+'}'
            pattern='R'+str(depth)+'{child:'+pattern+'}'
        self.program('named_deep_binding',''.join(declarations)+'pub fn main_entry()->u32{let value:R20='+value+';return match value{'+pattern+'=>n};}')

    def test_named_product_coverage_and_holes(self):
        self.program('named_products', '''struct Pair{pub x:bool;pub y:bool;}
fn read(p:Pair)->u32{return match p{Pair{x:true,y:_}=>20,
Pair{y:true,x:false}=>22,Pair{x:false,y:false}=>0};}
pub fn main_entry()->u32{return read(Pair{x:true,y:false})+read(Pair{x:false,y:true});}''')
        self.compile('named_product_hole', '''struct Pair{pub x:bool;pub y:bool;}
pub fn main_entry()->u32{let p:Pair=Pair{x:true,y:false};return match p{
Pair{x:true,y:true}=>42,Pair{x:false,y:false}=>42};}''', False)

    def test_named_alternatives_group_and_share_typed_bindings(self):
        self.program('named_choices', '''struct Point{pub x:u32;pub flag:bool;}
enum V{Left(Point),Right(Point)}fn read(v:V)->u32{return match v{
V::Left((Point{flag:true|false,x:n}))|V::Right(Point{x:n,..})=>n};}
pub fn main_entry()->u32{return read(V::Left(Point{x:20,flag:false}))+read(V::Right(Point{x:22,flag:true}));}''')
        self.program('named_array_type_spacing', '''struct A{pub values:[u32;2];}struct B{pub values:[u32; 2];}
enum V{Left(A),Right(B)}fn read(v:V)->u32{return match v{
V::Left(A{values:n})|V::Right(B{values:n})=>n[0]+n[1]};}
pub fn main_entry()->u32{return read(V::Right(B{values:[20,22]}));}''')

    def test_guard_runs_once_and_bindings_do_not_escape(self):
        self.program('named_guard', '''static mut calls:u32=0;struct Pair{pub x:u32;pub y:u32;}
fn reject(n:u32)->bool{calls=calls+1;return false;}
pub fn main_entry()->u32{let p:Pair=Pair{x:40,y:1};let n:u32=match p{
Pair{x:a,y:b}|Pair{y:a,x:b} if reject(a)=>0,Pair{x,..}=>x};return n+calls+1;}''')
        self.compile('named_escape', '''struct Point{pub x:u32;}pub fn main_entry()->u32{
let p:Point=Point{x:42};match p{Point{x}=>{}}return x;}''', False)

    def test_shorthand_shadows_module_constant(self):
        self.program('named_constant_shadow', '''const x:u32=1;struct Point{pub x:u32;}
pub fn main_entry()->u32{let p:Point=Point{x:42};return match p{Point{x}=>x};}''')
        self.program('named_constant_filter', '''const KEY:u32=7;struct Point{pub x:u32;}
pub fn main_entry()->u32{let p:Point=Point{x:7};return match p{Point{x:KEY}=>42,Point{..}=>0};}''')

    def test_inline_array_captures_can_be_indexed(self):
        self.program('named_array', '''struct Data{pub numbers:[u32;2];pub pad:u32;}
pub fn main_entry()->u32{let d:Data=Data{numbers:[20,22],pad:0};
return match d{Data{numbers:n,..}=>n[0]+n[1]};}''')
        self.program('named_record_array', '''struct Item{pub value:u32;}struct Data{pub items:[Item;2];}
pub fn main_entry()->u32{let d:Data=Data{items:[Item{value:20},Item{value:22}]};
return match d{Data{items}=>items[0].value+items[1].value};}''')
        self.program('named_array_copy', '''struct Data{pub numbers:[u32;2];}
fn poison(p:*mut u32)->bool{unsafe{*p=0;}return false;}
pub fn main_entry()->u32{let d:Data=Data{numbers:[20,22]};return match d{
Data{numbers:n} if poison(unsafe{n as *mut u32})=>0,Data{numbers:n}=>n[0]+n[1]};}''')

    def test_record_results_and_defer(self):
        self.program('named_record_results', '''static mut trace:u32=0;struct Point{pub x:u32;}
struct Data{pub point:Point;}fn read(d:Data)->Point{return match d{Data{point}=>{
defer{trace=trace+1;}point}};}
pub fn main_entry()->u32{let p:Point=read(Data{point:Point{x:41}});return p.x+trace;}''')

    def test_invalid_fields_rest_arity_and_binding_sets(self):
        for pattern in ('Point{x}', 'Point{z:_,..}', 'Point{x:_,x:_,..}',
                        'Point{x:n,y:n}', 'Point{..,x:_}', 'Point{..,..}',
                        'Point{x:n,..}|Point{y:_,..}'):
            with self.subTest(pattern=pattern):
                self.compile('named_bad_fields', '''struct Point{pub x:u32;pub y:u32;}
pub fn main_entry()->u32{let p:Point=Point{x:1,y:2};return match p{'''+pattern+'=>42};}', False)

    def test_nominal_record_types_and_pointer_fields_remain_checked(self):
        self.compile('named_wrong_type', '''struct A{pub x:u32;}struct B{pub x:u32;}
pub fn main_entry()->u32{let p:A=A{x:42};return match p{B{x}=>x};}''', False)
        self.compile('named_pointer', '''struct Data{pub pointer:*const u32;}
pub fn main_entry()->u32{let d:Data=Data{pointer:null};return match d{Data{..}=>42};}''', False)
        self.compile('named_immutable', '''struct Point{pub x:u32;}pub fn main_entry()->u32{
let p:Point=Point{x:42};match p{Point{x}=>{x=1;}}return 42;}''', False)
        self.compile('named_layout_capacity', '''struct Data{pub a:[u64;256];pub b:[u64;256];pub flag:bool;}
pub fn main_entry()->u32{let d:Data=Data{a:[0;256],b:[0;256],flag:true};return match d{Data{..}=>42};}''', False)

    def test_float_equality_both_widths_and_signed_zero(self):
        for typ in ('f32','f64'):
            self.program('float_points_'+typ, 'fn read(n:'+typ+''')->u32{return match n{-1.5|0.0|1.5=>21,_=>0};}
pub fn main_entry()->u32{if read(0.0)!=21{return 1;}return read(-1.5)+read(-0.0);}''')
            self.compile('float_zero_overlap_'+typ, 'pub fn main_entry()->u32{let n:'+typ+'''=0.0;
return match n{0.0=>42,-0.0=>42,_=>0};}''', False)

    def test_float_intervals_include_infinities_but_not_nan(self):
        for typ in ('f32','f64'):
            self.program('float_special_'+typ, 'fn divide(a:'+typ+',b:'+typ+')->'+typ+'''{return a/b;}
fn read(n:'''+typ+''')->u32{return match n{..0.0=>10,0.0..=>20,_=>12};}
pub fn main_entry()->u32{return read(divide(-1.0,0.0))+read(divide(1.0,0.0))+read(divide(0.0,0.0));}''')

    def test_nan_and_unknown_float_values_need_fallback(self):
        for pattern in ('0.0', '..', '..0.0 | 0.0..'):
            self.compile('float_no_fallback', '''pub fn main_entry()->u32{let n:f64=0.0;return match n{
'''+pattern+'=>42};}', False)
        self.compile('float_field_nan_hole', '''struct Data{pub f:f64;}
pub fn main_entry()->u32{let d:Data=Data{f:0.0};return match d{Data{f:..}=>42};}''', False)

    def test_float_interval_boundaries(self):
        for typ in ('f32','f64'):
            self.program('float_boundaries_'+typ, 'fn read(n:'+typ+''')->u32{return match n{1.5..2.0=>20,2.0..=2.5=>22,_=>0};}
pub fn main_entry()->u32{if read(1.0)!=0||read(2.5)!=22||read(3.0)!=0{return 1;}return read(1.5)+read(2.0);}''')
            for pattern in ('2.0..1.0','1.0..1.0','-0.0..0.0'):
                self.compile('float_empty_'+typ, 'pub fn main_entry()->u32{let n:'+typ+'=0.0;return match n{'+pattern+'=>42,_=>0};}', False)

    def test_float_patterns_inside_named_fields_and_payloads(self):
        self.program('named_float', '''struct Data{pub number:f64;pub flag:bool;}enum V{Empty,Data(Data)}
fn read(v:V)->u32{return match v{
V::Data(Data{flag:true,number:-1.5|0.0})=>20,
V::Data(Data{number:1.0..=2.0,flag:true})=>22,
V::Data(Data{flag:true,..})=>0,V::Data(Data{flag:false,..})=>0,V::Empty=>0};}
pub fn main_entry()->u32{return read(V::Data(Data{number:-0.0,flag:true}))+read(V::Data(Data{number:2.0,flag:true}));}''')
        self.program('named_float_open_end', '''struct Data{pub value:f64;}
fn divide(a:f64,b:f64)->f64{return a/b;}
fn read(d:Data)->u32{return match d{Data{value:..}=>42,Data{..}=>0};}
pub fn main_entry()->u32{if read(Data{value:divide(0.0,0.0)})!=0{return 1;}
return read(Data{value:divide(1.0,0.0)});}''')

    def test_float_constants_keep_types_and_rounded_identity(self):
        self.program('float_constants', '''const KEY:f32=1.5;fn read(n:f32)->u32{return match n{KEY=>42,_=>0};}
pub fn main_entry()->u32{return read(1.5);}''')
        self.compile('float_rounding_overlap', '''pub fn main_entry()->u32{let n:f32=16777216.0;
return match n{16777216.0=>42,16777217.0=>42,_=>0};}''', False)
        self.compile('float_constant_type', '''const KEY:f64=1.5;pub fn main_entry()->u32{let n:f32=1.5;
return match n{KEY=>42,_=>0};}''', False)

    def test_float_subject_literal_and_binding_guard(self):
        self.program('float_literal_subject', '''pub fn main_entry()->u32{return match 1.5{1.5=>42,_=>0};}''')
        self.program('float_statement_subject', '''pub fn main_entry()->u32{match 1.5{_=>{}}return 42;}''')
        self.program('float_guard_binding', '''fn read(n:f64)->u32{return match n{x if x>1.0=>42,_=>0};}
pub fn main_entry()->u32{return read(1.5);}''')

    def test_named_boolean_products_against_independent_oracle(self):
        import itertools
        values=(None,False,True)
        rectangles=list(itertools.product(values,repeat=2))
        domain=set(itertools.product((False,True),repeat=2))
        for mask in range(512):
            selected=[rectangle for bit,rectangle in enumerate(rectangles) if mask & (1<<bit)]
            selected.sort(key=lambda pair: pair==(None,None))
            covered=set()
            patterns=[]
            for a,b in selected:
                covered.update((x,y) for x,y in domain if (a is None or a==x) and (b is None or b==y))
                left='_' if a is None else str(a).lower()
                right='_' if b is None else str(b).lower()
                patterns.append('Pair{y:'+right+',x:'+left+'}=>42')
            self.compile('named_oracle_'+str(mask), '''struct Pair{pub x:bool;pub y:bool;}
pub fn main_entry()->u32{let p:Pair=Pair{x:true,y:false};return match p{'''+','.join(patterns)+'};}',covered==domain)


if __name__ == '__main__':
    unittest.main()
