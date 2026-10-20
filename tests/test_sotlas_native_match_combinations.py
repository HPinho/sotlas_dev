"""Exact product coverage checked against finite independent set oracles."""
import itertools
import os
import random
import subprocess
import unittest
import test_sotlas_native_i32 as previous


class NativeMatchCombinationTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute
    windows_process_exit_code = previous.NativeI32Tests.windows_process_exit_code

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_boolean_product_without_fallback(self):
        self.program('coverage_bool_product', '''enum V{Pair(bool,bool)}
fn read(v:V)->u32{return match v{V::Pair(true,true)=>10,V::Pair(true,false)=>11,
V::Pair(false,true)=>12,V::Pair(false,false)=>9};}
pub fn main_entry()->u32{return read(V::Pair(true,true))+read(V::Pair(true,false))+
read(V::Pair(false,true))+read(V::Pair(false,false));}''')

    def test_integer_intervals_cover_full_width(self):
        self.program('coverage_integer_intervals', '''enum V{N(u64)}
fn read(v:V)->u32{return match v{V::N(..42)=>20,V::N(42..)=>22};}
pub fn main_entry()->u32{return read(V::N(0))+read(V::N(18446744073709551615));}''')

    def test_signed_extrema_and_open_ranges(self):
        self.program('coverage_signed', '''enum V{N(i64)}
fn read(v:V)->u32{return match v{V::N(..0)=>20,V::N(0..)=>22};}
pub fn main_entry()->u32{return read(V::N(-9223372036854775808))+read(V::N(9223372036854775807));}''')

    def test_nested_sum_and_product_coverage(self):
        self.program('coverage_nested', '''enum Inner{Empty,Flag(bool)}enum Outer{None,Pair(Inner,bool)}
fn read(v:Outer)->u32{return match v{Outer::None=>0,
Outer::Pair(Inner::Empty,_)=>1,Outer::Pair(Inner::Flag(true),true)=>20,
Outer::Pair(Inner::Flag(true),false)=>22,Outer::Pair(Inner::Flag(false),_)=>0};}
pub fn main_entry()->u32{return read(Outer::Pair(Inner::Flag(true),true))+
read(Outer::Pair(Inner::Flag(true),false));}''')

    def test_scalar_enum_cartesian_product(self):
        self.program('coverage_enum_product', '''enum Code{A=7,B=100}enum V{Pair(Code,Code)}
fn read(v:V)->u32{return match v{V::Pair(Code::A,_)=>20,
V::Pair(Code::B,Code::A)=>22,V::Pair(Code::B,Code::B)=>0};}
pub fn main_entry()->u32{return read(V::Pair(Code::A,Code::B))+read(V::Pair(Code::B,Code::A));}''')

    def test_independent_marginal_coverage_does_not_cover_diagonal_holes(self):
        self.compile('coverage_diagonal_hole', '''enum V{Pair(bool,bool)}pub fn main_entry()->u32{
let v:V=V::Pair(true,false);return match v{V::Pair(true,true)=>42,V::Pair(false,false)=>42};}''',False)

    def test_integer_boundary_holes_are_rejected(self):
        for arms in ('V::N(..41)=>42,V::N(42..)=>42',
                     'V::N(..18446744073709551615)=>42'):
            with self.subTest(arms=arms):
                self.compile('coverage_hole_'+str(len(arms)), '''enum V{N(u64)}pub fn main_entry()->u32{
let v:V=V::N(42);return match v{'''+arms+'''};}''',False)

    def test_guarded_rows_never_supply_coverage(self):
        self.compile('coverage_guard_hole', '''enum V{N(bool)}pub fn main_entry()->u32{
let v:V=V::N(true);return match v{V::N(true) if true=>42,V::N(false)=>0};}''',False)

    def test_pod_and_float_captures_do_not_need_value_enumeration(self):
        self.program('coverage_opaque_captures', '''struct Box{pub value:u32;}enum V{Data(Box,f64,bool)}
pub fn main_entry()->u32{let v:V=V::Data(Box{value:40},2.0,true);return match v{
V::Data(box,n,true)=>box.value+(n as u32),V::Data(_,_,false)=>0};}''')

    def test_wide_product_does_not_enumerate_every_value(self):
        self.program('coverage_wide_product', '''enum V{Data(u64,u64,u64,u64,bool)}
pub fn main_entry()->u32{let v:V=V::Data(1,2,3,4,true);return match v{
V::Data(_,_,_,_,true)=>42,V::Data(_,_,_,_,false)=>0};}''')

    def test_all_boolean_rectangle_unions_against_independent_oracle(self):
        # All 512 unions of the nine rectangles in a two-Boolean product.
        # A total row is kept last to preserve the existing unreachable-arm rule.
        rectangles=list(itertools.product(('true','false','_'),repeat=2))
        universe=set(itertools.product((True,False),repeat=2))
        for mask in range(512):
            selected=[p for i,p in enumerate(rectangles) if mask & (1<<i)]
            covered={v for v in universe if any(all(p=='_' or (p=='true')==x
                       for p,x in zip(pattern,v)) for pattern in selected)}
            arms=','.join('V::Pair('+','.join(p)+')=>42' for p in selected)
            with self.subTest(mask=mask):
                self.compile('coverage_oracle_'+str(mask), '''enum V{Pair(bool,bool)}
pub fn main_entry()->u32{let v:V=V::Pair(true,true);return match v{'''+arms+'''};}''',covered==universe)

    def test_signed_unsigned_rectangle_unions_against_cell_oracle(self):
        rng=random.Random(17823)
        domain=set(itertools.product(range(4),repeat=2))
        for case in range(64):
            boxes=[]
            for _ in range(1+case%12):
                a,b=sorted((rng.randrange(4),rng.randrange(4)))
                c,d=sorted((rng.randrange(4),rng.randrange(4)))
                boxes.append((a,b,c,d))
            covered={(x,y) for x,y in domain if any(a<=x<=b and c<=y<=d for a,b,c,d in boxes)}
            arms=','.join(f'V::Pair({a*64-128}..={b*64-65},{c*64}..={d*64+63})=>42'
                          for a,b,c,d in boxes)
            with self.subTest(case=case):
                self.compile('coverage_rectangles_'+str(case), '''enum V{Pair(i8,u8)}
pub fn main_entry()->u32{let v:V=V::Pair(0,0);return match v{'''+arms+'''};}''',covered==domain)

    def test_nested_axes_are_independent(self):
        self.program('coverage_nested_axes', '''enum Inner{No,Flag(bool)}enum V{Pair(Inner,Inner)}
fn read(v:V)->u32{return match v{V::Pair(Inner::No,_)=>0,
V::Pair(Inner::Flag(true),Inner::No)=>0,V::Pair(Inner::Flag(true),Inner::Flag(_))=>42,
V::Pair(Inner::Flag(false),_)=>0};}
pub fn main_entry()->u32{return read(V::Pair(Inner::Flag(true),Inner::Flag(false)));}''')
        self.compile('coverage_nested_diagonal','''enum Inner{No,Flag(bool)}enum V{Pair(Inner,Inner)}
pub fn main_entry()->u32{let v:V=V::Pair(Inner::No,Inner::Flag(true));return match v{
V::Pair(Inner::No,Inner::No)=>42,V::Pair(Inner::Flag(_),Inner::Flag(_))=>42};}''',False)

    def test_all_scalar_width_domains(self):
        for typ in ('u8','u16','u32','u64','i8','i16','i32','i64'):
            with self.subTest(typ=typ):
                self.program('coverage_width_'+typ, 'enum V{N('+typ+''')}
pub fn main_entry()->u32{let v:V=V::N(42);return match v{V::N(..42)=>0,V::N(42..)=>42};}''')

    def test_sixty_four_arm_mask_and_last_interval(self):
        arms=','.join(f'V::N({n}..={n+3})=>42' for n in range(0,256,4))
        self.program('coverage_mask64','''enum V{N(u8)}pub fn main_entry()->u32{
let v:V=V::N(255);return match v{'''+arms+'''};}''')
        self.compile('coverage_mask64_hole','''enum V{N(u8)}pub fn main_entry()->u32{
let v:V=V::N(255);return match v{'''+arms.replace('252..=255','252..=254')+'''};}''',False)

    def test_guard_failure_uses_later_coverage_rows(self):
        self.program('coverage_guard_fallback','''enum V{N(bool)}
pub fn main_entry()->u32{let v:V=V::N(true);return match v{
V::N(true) if false=>1,V::N(true)=>42,V::N(false)=>0};}''')

    def test_statement_combinations_with_early_return(self):
        self.program('coverage_statement', '''enum V{Pair(bool,bool)}
fn read(v:V)->u32{match v{
V::Pair(true,true)=>{return 10;},V::Pair(true,false)=>{return 11;},
V::Pair(false,true)=>{return 12;},V::Pair(false,false)=>{return 9;}}}
pub fn main_entry()->u32{return read(V::Pair(true,true))+read(V::Pair(true,false))+
read(V::Pair(false,true))+read(V::Pair(false,false));}''')

    def test_invalid_raw_field_cannot_select_last_refutable_arm(self):
        obj = self.compile('coverage_invalid_representation', '''enum Code{A=1,B=2}
enum V{N(Code)}pub fn main_entry()->u32{
let code:Code=3;
let v:V=V::N(code);
return match v{V::N(Code::A)=>0,V::N(Code::B)=>42};}''')
        image = self.link_image(obj)
        if os.name == 'nt':
            status, error = self.windows_process_exit_code(image)
            self.assertEqual(status, 0xc000001d, error)
        else:
            import resource
            import signal
            result = subprocess.run([str(image)], cwd=self.directory,
                                    capture_output=True, timeout=15,
                                    preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
            self.assertEqual(result.returncode, -signal.SIGILL, result.stderr)


if __name__ == '__main__':
    unittest.main()
