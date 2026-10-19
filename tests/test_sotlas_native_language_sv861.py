"""SV8.61 new control-flow syntax and implicit enum values."""
import unittest
import test_sotlas_native_migration_sv860 as previous

class NativeLanguageSV861Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMigrationSV860Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMigrationSV860Tests.tearDownClass.__func__)
    compile=previous.NativeMigrationSV860Tests.compile
    execute=previous.NativeMigrationSV860Tests.execute
    link_image=previous.NativeMigrationSV860Tests.link_image

    def program(self,name,body,prefix=''):
        self.execute(self.compile(name,prefix+'pub fn main_entry()->u32{'+body+'}'))

    def test_loop_statement_executes_until_break(self):
        self.program('native_loop','let mut n:u32=0;loop{n+=1;if n==42{break;}}return n;')

    def test_for_range_iterates_exclusive_integer_bounds(self):
        self.program('native_for','let mut total:u32=0;for i in 0..7{total+=i;}return total*2;')

    def test_implicit_enum_discriminants_begin_at_zero(self):
        self.program('implicit_enum','let c:Code=Code::Answer;match c{Code::Zero=>return 1;Code::Answer=>return 42;Code::Next=>return 2;}','enum Code{Zero,Answer=42,Next}')

    def test_loop_continue_rechecks_the_unconditional_header(self):
        self.program('loop_continue','let mut n:u32=0;loop{n+=1;if n<42{continue;}break;}return n;')

    def test_loop_nesting_targets_the_innermost_loop(self):
        self.program('loop_nested','let mut n:u32=0;let mut outer:u32=0;loop{outer+=1;loop{n+=21;break;}if outer==2{break;}}return n;')

    def test_loop_early_return_preserves_the_function_result(self):
        self.program('loop_return','return finish();','fn finish()->u32{loop{return 42;}}')
        self.compile('loop_missing_return','fn bad(flag:bool)->u32{loop{if flag{break;}return 42;}}',success=False)

    def test_loop_defer_runs_on_continue_and_break_in_lifo_order(self):
        self.program('loop_cleanup','let mut n:u32=0;loop{n+=1;defer append(2);defer append(1);if n==1{continue;}break;}if unsafe{trace}==1212{return 42;}return 1;',
                     'static mut trace:u32=0;fn append(v:u32)->void{unsafe{trace=trace*10+v;}}')

    def test_loop_preserves_owner_borrows_and_rejects_use_after_transfer(self):
        prefix='struct Token{pub value:u32;}fn consume(v:sole Token)->void{return;}'
        self.program('loop_owner','let owner:sole Token=Token{value:42};loop{if owner.value==42{break;}}return owner.value;',prefix)
        self.compile('loop_owner_moved',prefix+'fn bad()->u32{let owner:sole Token=Token{value:42};loop{consume(owner);break;}return owner.value;}',success=False)

    def test_for_range_accepts_integer_variable_bounds(self):
        self.program('for_variables','let first:u32=4;let last:u32=7;let mut n:u32=0;for i in first..last{n+=i;}return n+27;')

    def test_for_range_evaluates_both_bound_calls_once(self):
        self.program('for_calls','let mut n:u32=0;for i in first()..last(){n+=i;}if unsafe{calls}!=12{return 1;}return n*2;',
                     'static mut calls:u32=0;fn first()->u32{unsafe{calls=calls*10+1;}return 0;}fn last()->u32{unsafe{calls=calls*10+2;}return 7;}')

    def test_for_range_accepts_matching_signed_bounds(self):
        self.program('for_signed','let first:i32=-2;let last:i32=3;let mut n:i32=0;let mut count:u32=0;for i in first..last{n+=i;count+=1;}if count!=5 || n!=0{return 1;}return 42;')

    def test_for_nested_ranges_keep_hidden_cursors_independent(self):
        self.program('for_nested','let mut n:u32=0;for i in 0..3{for j in 0..7{n+=2;}}return n;')

    def test_for_iteration_binding_is_lexical_and_shadows_outer_names(self):
        self.program('for_scope','let i:u32=42;for i in 0..2{let seen:u32=i;}return i;')
        self.compile('for_scope_escape','fn bad()->u32{for i in 0..2{}return i;}',success=False)

    def test_for_default_binding_is_immutable_and_mut_binding_is_a_copy(self):
        self.compile('for_immutable','fn bad()->u32{for i in 0..2{i=42;}return 42;}',success=False)
        self.program('for_mut','let mut n:u32=0;for mut i in 0..2{i=21;n+=i;}return n;')

    def test_for_continue_advances_the_hidden_cursor(self):
        self.program('for_continue','let mut n:u32=0;for i in 0..8{if i==7{continue;}n+=i;}return n*2;')

    def test_for_break_runs_defer_before_exiting(self):
        self.program('for_break_cleanup','for i in 0..8{defer append(21);if i==1{break;}}return unsafe{trace};',
                     'static mut trace:u32=0;fn append(v:u32)->void{unsafe{trace=trace+v;}}')

    def test_for_empty_and_descending_ranges_skip_the_body_and_reject_nonintegers(self):
        self.program('for_empty','let mut n:u32=42;for i in 7..7{n=1;}for j in 8..2{n=2;}return n;')
        self.compile('for_float','fn bad()->u32{for i in 0.0..2.0{}return 42;}',success=False)

    def test_implicit_enum_successors_have_distinct_match_values(self):
        self.program('enum_successors','let c:Code=Code::Last;match c{Code::First=>return 1;Code::Middle=>return 2;Code::Last=>return 42;}','enum Code{First,Middle,Last}')

    def test_explicit_enum_values_reset_following_implicit_values(self):
        self.program('enum_resets','let c:Code=Code::Next;match c{Code::First=>return 1;Code::Reset=>return 2;Code::Next=>return 42;}','enum Code{First=9,Reset=40,Next}')

    def test_implicit_enum_successors_follow_radix_discriminants(self):
        self.program('enum_radix','let c:Code=Code::Next;match c{Code::First=>return 1;Code::Next=>return 42;}','enum Code{First=0x29,Next}')

    def test_implicit_enums_pass_through_fields_parameters_and_returns(self):
        self.program('enum_transport','let p:Packet=Packet{code:choose()};return read(p.code);',
                     'enum Code{First,Last}struct Packet{pub code:Code;}fn choose()->Code{return Code::Last;}fn read(c:Code)->u32{match c{Code::First=>return 1;Code::Last=>return 42;}}')

    def test_implicit_enum_overflow_is_rejected_but_explicit_reset_is_valid(self):
        self.compile('enum_overflow','enum Code{Last=4294967295,Overflow}fn bad()->u32{return 42;}',success=False)
        self.compile('enum_pointer_payload_closed','enum Code{Some(*mut u32),None}fn bad()->u32{return 42;}',success=False)
        self.program('enum_max_reset','let c:Code=Code::Next;match c{Code::Max=>return 1;Code::Reset=>return 2;Code::Next=>return 42;}','enum Code{Max=4294967295,Reset=0,Next}')

    def test_scalar_payload_enums_now_execute_in_the_native_backend(self):
        self.program('enum_payload_supported',
                     'let value:Code=Code::Some(42);return match value{Code::Some(n)=>n,Code::None=>0};',
                     'enum Code{Some(u32),None}')

if __name__=='__main__':unittest.main()
