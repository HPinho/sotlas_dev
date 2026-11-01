"""Native scoped if-let/while-let decisions and structured cleanup."""
import unittest
import test_sotlas_native_i32 as previous


class NativePatternControlTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_if_let_some_none_and_else_if_chain(self):
        self.program('pattern_if', '''enum V{None,Some(u32)}
fn read(v:V)->u32{if let V::Some(n)=v{return n;}else if let V::None=v{return 2;}else{return 1;}}
pub fn main_entry()->u32{if read(V::None)!=2{return 1;}return read(V::Some(42));}''')

    def test_no_else_and_both_unselected_bodies(self):
        self.program('pattern_no_else', '''enum V{None,Some(u32)}
pub fn main_entry()->u32{let mut n:u32=40;if let V::Some(x)=V::None{n=x;}
if let V::Some(x)=V::Some(2){n=n+x;}return n;}''')

    def test_subject_is_evaluated_once_and_payload_is_a_copy(self):
        self.program('pattern_once', '''struct Pair{pub x:u32;}enum V{None,Some(Pair)}
static mut calls:u32=0;fn make()->V{unsafe{calls=calls+1;}return V::Some(Pair{x:40});}
pub fn main_entry()->u32{let mut answer:u32=0;if let V::Some(p)=make(){answer=p.x;}
return answer+unsafe{calls}+1;}''')

    def test_bindings_shadow_outer_names_and_end_before_else(self):
        self.program('pattern_shadow', '''enum V{None,Some(u32)}
pub fn main_entry()->u32{let n:u32=22;let mut sum:u32=0;
if let V::Some(n)=V::Some(20){sum=n;}else{sum=n;}
if let V::Some(n)=V::None{sum=0;}else{sum=sum+n;}return sum;}''')

    def test_nested_payloads_and_refutable_fields(self):
        self.program('pattern_nested', '''enum Inner{N(u32,bool)}enum Outer{Empty,Wrap(Inner)}
fn read(v:Outer)->u32{if let Outer::Wrap(Inner::N(n,true))=v{return n;}else{return 0;}}
pub fn main_entry()->u32{if read(Outer::Wrap(Inner::N(10,false)))!=0{return 1;}
return read(Outer::Wrap(Inner::N(42,true)));}''')

    def test_named_record_array_and_float_patterns(self):
        self.program('pattern_shapes', '''struct R{pub items:[u32;2];pub flag:bool;}
pub fn main_entry()->u32{let mut sum:u32=0;
if let R{items:[a,b],flag:true}=R{items:[20,20],flag:true}{sum=a+b;}
if let 1.5=1.5{sum=sum+2;}return sum;}''')

    def test_alternative_payload_bindings(self):
        self.program('pattern_alternatives', '''enum V{A(u32),B(u32),Empty}
fn read(v:V)->u32{if let V::A(n)|V::B(n)=v{return n;}else{return 0;}}
pub fn main_entry()->u32{return read(V::A(20))+read(V::B(22));}''')

    def test_while_let_rechecks_subject_and_stops_on_none(self):
        self.program('pattern_while', '''enum V{None,Some(u32)}static mut cursor:u32=0;
fn next()->V{unsafe{cursor=cursor+1;if cursor<4{return V::Some(cursor);}}return V::None;}
pub fn main_entry()->u32{let mut sum:u32=0;while let V::Some(n)=next(){sum=sum+n;}
if unsafe{cursor}!=4||sum!=6{return 1;}return 42;}''')

    def test_while_let_continue_break_and_defer(self):
        self.program('pattern_jumps', '''enum V{None,Some(u32)}static mut cursor:u32=0;static mut drops:u32=0;
fn next()->V{unsafe{cursor=cursor+1;return V::Some(cursor);}}
pub fn main_entry()->u32{let mut sum:u32=0;while let V::Some(n)=next(){
defer{unsafe{drops=drops+1;}}if n==1{continue;}sum=sum+n;if n==3{break;}}
if sum!=5||unsafe{cursor}!=3||unsafe{drops}!=3{return 1;}return 42;}''')

    def test_iteration_defer_observes_its_own_payload_snapshot(self):
        self.program('pattern_defer_payload', '''enum V{None,Some(u32)}static mut trace:u32=0;
pub fn main_entry()->u32{let mut v:V=V::Some(1);while let V::Some(n)=v{
defer{unsafe{trace=trace*10+n;}}if n==1{v=V::Some(2);continue;}v=V::None;}
if unsafe{trace}!=12{return 1;}return 42;}''')

    def test_while_let_return_cleanup_lifo(self):
        self.program('pattern_return', '''enum V{None,Some(u32)}static mut trace:u32=0;
fn read()->u32{defer{unsafe{trace=trace*10+1;}}while let V::Some(n)=V::Some(40){
defer{unsafe{trace=trace*10+2;}}return n;}return 0;}
pub fn main_entry()->u32{let n:u32=read();if unsafe{trace}!=21{return 1;}return n+2;}''')

    def test_pattern_failure_exits_inner_loop_only(self):
        self.program('pattern_nested_loops', '''enum V{None,Some(u32)}pub fn main_entry()->u32{
let mut sum:u32=0;for i in 0..2{let mut v:V=V::Some(21);
while let V::Some(n)=v{sum=sum+n;v=V::None;} }return sum;}''')

    def test_if_let_in_loop_jumps_target_the_outer_loop(self):
        self.program('pattern_outer_jumps', '''enum V{None,Some(u32)}pub fn main_entry()->u32{
let mut sum:u32=0;for i in 0..5{if let V::Some(n)=V::Some(i){
if n==0{continue;}if n==3{break;}sum=sum+n;}}return sum+39;}''')

    def test_question_mark_subject_preserves_early_return(self):
        self.program('pattern_try', '''enum V{None,Some(u32)}enum R{Ok(V),Err(u32)}
fn read(v:R)->R{if let V::Some(n)=v?{return R::Ok(V::Some(n));}return R::Ok(V::None);}
pub fn main_entry()->u32{if let R::Err(n)=read(R::Err(42)){return n;}return 1;}''')

    def test_while_returning_result_operand_runs_cleanup_on_failure(self):
        self.program('pattern_loop_try', '''enum V{None,Some(u32)}enum R{Ok(V),Err(u32)}
static mut calls:u32=0;static mut drops:u32=0;
fn next()->R{unsafe{calls=calls+1;if calls==1{return R::Ok(V::Some(1));}}return R::Err(42);}
fn read()->R{defer{unsafe{drops=drops+10;}}while let V::Some(n)=next()?{
defer{unsafe{drops=drops+1;}}continue;}return R::Ok(V::None);}
pub fn main_entry()->u32{let result:R=read();if unsafe{calls}!=2||unsafe{drops}!=11{return 1;}
if let R::Err(n)=result{return n;}return 2;}''')

    def test_subject_mutation_does_not_change_selected_payload(self):
        self.program('pattern_snapshot', '''enum V{None,Some([u32;2])}
pub fn main_entry()->u32{let mut source:V=V::Some([20,22]);
if let V::Some(items)=source{source=V::Some([1,1]);return items[0]+items[1];}return 1;}''')

    def test_ranges_constants_and_boolean_subjects(self):
        self.program('pattern_scalar_domains', '''const KEY:u32=20;
pub fn main_entry()->u32{let mut sum:u32=0;if let KEY=20{sum=sum+20;}
let negative:i32=-2;if let -10..=0=negative{sum=sum+20;}if let false=false{sum=sum+2;}return sum;}''')

    def test_ordinary_else_if_and_pattern_else_if_share_return_proof(self):
        self.program('pattern_mixed_chain', '''enum V{None,Some(u32)}
fn read(v:V,flag:bool)->u32{if let V::Some(n)=v{return n;}else if flag{return 40;}else{return 2;}}
pub fn main_entry()->u32{return read(V::None,true)+read(V::None,false);}''')

    def test_ordinary_if_can_chain_into_pattern_control(self):
        self.program('pattern_after_if', '''enum V{None,Some(u32)}
fn read(flag:bool,v:V)->u32{if flag{return 20;}else if let V::Some(n)=v{return n;}
else if let V::None=v{return 1;}else{return 0;}}
pub fn main_entry()->u32{return read(true,V::None)+read(false,V::Some(22));}''')

    def test_invalid_patterns_and_bindings_fail_closed(self):
        cases = (
            'if let V::Missing(n)=v{return n;}',
            'if let V::Some(a,b)=v{return a;}',
            'if let V::Some(n)=v{}return n;',
            'if let V::Some(n)=v{}else{return n;}',
            'while let V::Some(n)=v{break;}return n;',
            'if let V::Some(n)=v{n=1;}',
            'if let V::Some(n)=v{break;}',
            'if let V::Some(n)=v{continue;}',
            'if let V::Some(n)|V::None=v{return n;}',
            'if let V::Some(true)=v{return 1;}',
            'if let n=v{return 1;}',
            'while let _=v{break;}',
        )
        for i, body in enumerate(cases):
            with self.subTest(body=body):
                self.compile('pattern_bad_'+str(i),'enum V{None,Some(u32)}pub fn main_entry()->u32{let v:V=V::Some(42);'+body+'return 42;}',False)

    def test_pod_ownership_snapshot_does_not_consume_the_owner(self):
        self.program('pattern_owner', '''enum V{None,Some(u32)}
fn consume(v:sole V)->u32{if let V::Some(n)=v{return n;}return 0;}
pub fn main_entry()->u32{let v:sole V=V::Some(42);let mut seen:u32=0;
if let V::Some(n)=v{seen=n;}if seen!=42{return 1;}return consume(v);}''')

    def test_resource_payload_and_unavailable_owner_reject(self):
        self.compile('pattern_resource', '''enum V{None,Some(*const u32)}
pub fn main_entry()->u32{let v:V=V::None;if let V::Some(n)=v{return 1;}return 42;}''',False)
        self.compile('pattern_moved', '''enum V{None,Some(u32)}fn take(v:sole V)->u32{return 0;}
pub fn main_entry()->u32{let v:sole V=V::Some(42);let n:u32=take(v);
if let V::Some(x)=v{return x;}return n;}''',False)

    def test_returning_pattern_edge_preserves_the_other_owner_path(self):
        self.program('pattern_owner_return', '''struct Box{pub n:u32;}enum V{None,Some(u32)}
fn take(v:sole Box)->u32{return v.n;}
fn choose(tag:V,v:sole Box)->u32{if let V::Some(n)=tag{return take(v);}return v.n;}
pub fn main_entry()->u32{let a:sole Box=Box{n:20};let b:sole Box=Box{n:22};
return choose(V::Some(1),a)+choose(V::None,b);}''')

    def test_mixed_move_and_loop_backedge_stay_checked(self):
        for i, body in enumerate((
            'if let V::Some(n)=tag{let used:u32=take(v);}return v.n;',
            'while let V::Some(n)=tag{let used:u32=take(v);continue;}return 42;',
        )):
            with self.subTest(body=body):
                self.compile('pattern_move_edges_'+str(i),'''struct Box{pub n:u32;}enum V{None,Some(u32)}
fn take(v:sole Box)->u32{return v.n;}fn choose(tag:V,v:sole Box)->u32{'''+body+'''}
pub fn main_entry()->u32{let v:sole Box=Box{n:42};return choose(V::Some(1),v);}''',False)

    def test_malformed_pattern_control_is_rejected(self):
        for i, body in enumerate(('if let V::Some(n) V::Some(42){}',
                                 'if let V::Some(n)=V::Some(42){}else return 1;',
                                 'while let V::Some(n)=V::None{}else{}',
                                 'if let mut n=V::None{}')):
            with self.subTest(body=body):
                self.compile('pattern_syntax_'+str(i),'enum V{None,Some(u32)}pub fn main_entry()->u32{'+body+'return 42;}',False)


if __name__ == '__main__':
    unittest.main()
