"""Native or-patterns: selection, binding contracts, guards and cleanup."""
import itertools
import unittest
import test_sotlas_native_i32 as previous


class NativeMatchAlternativeTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_scalar_choices_and_parentheses(self):
        self.program('or_scalar', '''fn read(n:u8)->u32{return match n{
(0 | (1 | 2))=>20,3..=>22};}
pub fn main_entry()->u32{return read(2)+read(255);}''')

    def test_overlapping_integer_choices_cover_full_domain(self):
        self.program('or_intervals', '''fn read(n:i64)->u32{return match n{
..0 | -2.. =>21};}pub fn main_entry()->u32{return read(-9223372036854775808)+read(9223372036854775807);}''')

    def test_boolean_enum_and_constant_choices(self):
        self.program('or_constants', '''const A:u8=1;const B:u8=2;enum Code{Left=7,Right=100}
fn flag(n:bool)->u32{return match n{true|false=>10};}
fn code(n:Code)->u32{return match n{Code::Left|Code::Right=>10};}
fn number(n:u8)->u32{return match n{A|B=>22,_=>0};}
pub fn main_entry()->u32{return flag(false)+code(Code::Right)+number(B);}''')

    def test_variant_choices_bind_at_different_offsets(self):
        self.program('or_bindings', '''enum V{Left(u32,bool),Right(bool,u32)}
fn read(v:V)->u32{return match v{V::Left(n,_) | V::Right(_,n)=>n};}
pub fn main_entry()->u32{return read(V::Left(20,true))+read(V::Right(false,22));}''')

    def test_nested_choices_distribute_cartesian_products(self):
        self.program('or_nested', '''enum Inner{None,Flag(bool)}enum V{Pair(Inner,bool)}
fn read(v:V)->u32{return match v{
V::Pair(Inner::None | Inner::Flag(true | false), true | false)=>7};}
pub fn main_entry()->u32{return read(V::Pair(Inner::None,true))+read(V::Pair(Inner::None,false))+
read(V::Pair(Inner::Flag(true),true))+read(V::Pair(Inner::Flag(true),false))+
read(V::Pair(Inner::Flag(false),true))+read(V::Pair(Inner::Flag(false),false));}''')

    def test_false_guard_runs_once_for_overlapping_alternatives(self):
        self.program('or_guard_once', '''static mut calls:u32=0;
fn guard()->bool{calls=calls+1;return false;}
pub fn main_entry()->u32{let n:u8=1;
let result:u32=match n{1 | 1 | 0..=2 if guard()=>0,_=>40};return result+calls+1;}''')

    def test_nested_false_guard_skips_all_distributed_rows(self):
        self.program('or_nested_guard', '''static mut calls:u32=0;enum V{N(u32,bool)}
fn guard(n:u32)->bool{calls=calls+1;return false;}
pub fn main_entry()->u32{let v:V=V::N(40,true);
let result:u32=match v{V::N(n,true | true | false) if guard(n)=>0,V::N(n,_)=>n};
return result+calls+1;}''')

    def test_guard_true_uses_first_binding_and_body_once(self):
        self.program('or_first_binding', '''static mut calls:u32=0;enum V{Pair(u32,u32)}
fn guard(n:u32)->bool{calls=calls+1;return true;}
pub fn main_entry()->u32{let v:V=V::Pair(40,1);
let result:u32=match v{V::Pair(n,_) | V::Pair(_,n) if guard(n)=>n,V::Pair(_,_)=>0};
return result+calls+1;}''')

    def test_record_bindings_and_defer_cleanup(self):
        self.program('or_record', '''static mut trace:u32=0;struct Data{pub value:u32;}
enum V{Left(Data),Right(Data)}
fn read(v:V)->Data{return match v{V::Left(data)|V::Right(data)=>{
defer{trace=trace+1;}data}};}
pub fn main_entry()->u32{let v:V=V::Right(Data{value:41});let d:Data=read(v);return d.value+trace;}''')

    def test_exclusive_moves_in_shared_source_body(self):
        self.program('or_moves', '''struct Data{pub value:u32;}
fn read(n:u8,owner:sole Data)->sole Data{return match n{0|1=>owner,_=>owner};}
pub fn main_entry()->u32{let owner:sole Data=Data{value:42};let result:sole Data=read(1,owner);return result.value;}''')
        prefix = '''struct Data{pub value:u32;}fn consume(owner:sole Data)->u32{return owner.value;}
pub fn main_entry()->u32{let owner:sole Data=Data{value:42};let n:u8=1;'''
        self.compile('or_maybe_moved', prefix+'''let result:u32=match n{0|1=>consume(owner),_=>0};
return owner.value;}''', False)
        self.compile('or_guard_consumes', prefix+'''return match n{
0|1 if consume(owner)==42=>42,_=>0};}''', False)

    def test_nested_match_groups_survive_body_cloning(self):
        self.program('or_cloned_nested_match', '''static mut calls:u32=0;
fn guard()->bool{calls=calls+1;return false;}
fn read(n:u8)->u32{return match n{0|1=>{let k:u8=1;match k{1|1 if guard()=>0,_=>20}},_=>0};}
pub fn main_entry()->u32{return read(0)+read(1)+calls;}''')

    def test_missing_or_unequal_bindings_are_rejected_even_if_unused(self):
        for patterns in ('V::Left(n,_)|V::Right(_,_)', 'V::Left(n,_)|V::Right(_,other)',
                         'V::Left(_,_)|V::Right(_,n)'):
            with self.subTest(patterns=patterns):
                self.compile('or_missing_binding', '''enum V{Left(u32,bool),Right(bool,u32)}
pub fn main_entry()->u32{let v:V=V::Left(1,true);return match v{'''+patterns+'=>42};}', False)

    def test_binding_nominal_types_must_agree(self):
        for fields in ('u32,u64', 'A,B'):
            left, right = fields.split(',')
            value = 'A::X' if left == 'A' else '0'
            self.compile('or_binding_type_'+left, 'enum A{X}enum B{X}enum V{Left('+left+'),Right('+right+')}'
                         'pub fn main_entry()->u32{let v:V=V::Left('+value+');return match v{V::Left(n)|V::Right(n)=>42};}', False)

    def test_guarded_alternatives_do_not_prove_coverage(self):
        self.compile('or_guarded_gap', '''enum V{N(bool)}pub fn main_entry()->u32{
let v:V=V::N(true);return match v{V::N(true|false) if true=>42,V::N(false)=>0};}''', False)

    def test_cross_arm_overlap_and_cartesian_holes_remain_rejected(self):
        self.compile('or_overlap', '''pub fn main_entry()->u32{let n:u8=1;
return match n{0|1=>42,1|2=>42,_=>0};}''', False)
        self.compile('or_product_hole', '''enum V{Pair(bool,bool)}pub fn main_entry()->u32{
let v:V=V::Pair(true,false);return match v{V::Pair(true,true)|V::Pair(false,false)=>42};}''', False)

    def test_alternative_budget_and_syntax_errors_fail_closed(self):
        for patterns in ('| 1', '1 |', '1 || 2', '(1 | 2', '1 | | 2',
                         '|'.join('1' for _ in range(65))):
            with self.subTest(patterns=patterns):
                self.compile('or_bad_syntax', 'pub fn main_entry()->u32{let n:u8=1;return match n{'+patterns+'=>42,_=>0};}', False)
        self.compile('or_product_budget', '''enum V{Bits(bool,bool,bool,bool,bool,bool,bool)}
pub fn main_entry()->u32{let v:V=V::Bits(true,true,true,true,true,true,true);return match v{
V::Bits(true|false,true|false,true|false,true|false,true|false,true|false,true|false)=>42};}''', False)

    def test_all_boolean_disjunctions_against_set_oracle(self):
        domain=set(itertools.product((False,True),repeat=2))
        points=sorted(domain)
        for mask in range(1,16):
            selected={point for bit,point in enumerate(points) if mask & (1<<bit)}
            patterns='|'.join('V::Pair('+str(a).lower()+','+str(b).lower()+')' for a,b in sorted(selected))
            self.compile('or_boolean_union_'+str(mask), '''enum V{Pair(bool,bool)}
pub fn main_entry()->u32{let v:V=V::Pair(true,true);return match v{'''+patterns+'=>42};}',selected==domain)

    def test_false_guard_does_not_retry_a_different_binding_permutation(self):
        self.program('or_guard_permutation', '''enum V{Pair(u32,u32)}
pub fn main_entry()->u32{let v:V=V::Pair(1,40);return match v{
V::Pair(a,b)|V::Pair(b,a) if a==40=>0,V::Pair(_,_)=>42};}''')

    def test_subject_evaluated_once_and_root_bindings(self):
        self.program('or_subject_once', '''static mut calls:u32=0;
fn subject()->u32{calls=calls+1;return 40;}
pub fn main_entry()->u32{let result:u32=match subject(){n|n if n==40=>n,_=>0};return result+calls+1;}''')

    def test_wildcard_alternatives_and_group_reachability(self):
        for patterns in ('_|1','1|_','(_)|(_)'):
            with self.subTest(patterns=patterns):
                self.program('or_wildcards_'+str(len(patterns)),
                             'pub fn main_entry()->u32{let n:u8=42;return match n{'+patterns+'=>42};}')
        self.compile('or_unreachable_source_arm', '''pub fn main_entry()->u32{
let n:u8=42;return match n{1|_=>42,2=>0};}''',False)

    def test_loop_break_and_continue_inside_alternative_body(self):
        self.program('or_loop_exits', '''pub fn main_entry()->u32{let mut n:u8=0;
while n<3{match n{0|1=>{n=n+1;continue;},_=>{break;}}}return 40+n as u32;}''')

    def test_sixty_four_rows_are_accepted_and_sixty_five_are_rejected(self):
        alternatives='|'.join(str(n) for n in range(63))
        self.program('or_rows64','pub fn main_entry()->u32{let n:u8=62;return match n{'+alternatives+'=>42,_=>0};}')
        alternatives='|'.join(str(n) for n in range(64))
        self.compile('or_rows65','pub fn main_entry()->u32{let n:u8=62;return match n{'+alternatives+'=>42,_=>0};}',False)

    def test_reordered_overlapping_unsigned_intervals(self):
        self.program('or_unsigned_union', '''fn read(n:u64)->u32{return match n{42.. | ..=42=>21};}
pub fn main_entry()->u32{return read(0)+read(18446744073709551615);}''')

    def test_sixty_four_cartesian_choices_execute_the_last_combination(self):
        self.program('or_cartesian64', '''enum V{Bits(bool,bool,bool,bool,bool,bool)}
pub fn main_entry()->u32{let v:V=V::Bits(false,false,false,false,false,false);return match v{
V::Bits(true|false,true|false,true|false,true|false,true|false,true|false)=>42};}''')

    def test_grouping_preserves_arithmetic_range_bounds(self):
        self.program('or_arithmetic_bounds', '''fn read(n:u8)->u32{return match n{
(6*7)..=(40+2) | ((40+3)..=255)=>21,_=>0};}
pub fn main_entry()->u32{return read(42)+read(255);}''')
        self.program('or_grouped_constructors', '''enum Inner{A(u32),B(u32)}enum V{Wrap(Inner)}
pub fn main_entry()->u32{let v:V=V::Wrap(Inner::B(42));return match v{
V::Wrap((Inner::A(n)) | (Inner::B(n)))=>n};}''')
        self.program('or_bitwise_range_bound', '''fn read(n:u8)->u32{return match n{
(40|2)..=(40+2)|((40+3)..=255)=>21,_=>0};}
pub fn main_entry()->u32{return read(42)+read(255);}''')


if __name__ == '__main__':
    unittest.main()
