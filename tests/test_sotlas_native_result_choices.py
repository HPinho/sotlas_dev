"""Native propagation from conditional/match choices and inferred bindings."""
import unittest
import test_sotlas_native_i32 as previous


class NativeResultChoiceTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,work,checks=''):
        self.execute(self.compile(name,'''struct R{pub status:u32;pub value:u32;pub detail:u32;}
static mut trace:u32=0;
fn read(ok:bool)->R{if ok{return R{status:0,value:42,detail:0};}return R{status:7,value:0,detail:99};}
'''+work+'''pub fn main_entry()->u32{let good:R=work(true);let bad:R=work(false);
if good.status!=0 || good.value!=42 || bad.status!=7 || bad.detail!=99{return 1;}'''+checks+'return 42;}'))

    def test_direct_conditional_propagation(self):
        self.program('choice_if','''fn work(ok:bool)->R{let n:u32=(if ok{read(true)}else{read(false)})?;
return R{status:0,value:n,detail:0};}''')

    def test_direct_match_propagation(self):
        self.program('choice_match','''fn work(ok:bool)->R{let n:u32=(match ok{true=>read(true),false=>read(false)})?;
return R{status:0,value:n,detail:0};}''')

    def test_inferred_choice_binding(self):
        self.program('choice_inferred','''fn work(ok:bool)->R{let selected=if ok{read(true)}else{read(false)};
let n:u32=selected?;return R{status:0,value:n,detail:0};}''')

    def test_inferred_match_binding(self):
        self.program('choice_match_inferred','''fn work(ok:bool)->R{let selected=match ok{true=>read(true),false=>read(false)};
let n:u32=selected?;return R{status:0,value:n,detail:0};}''')

    def test_nested_choices_and_static_self_constructors(self):
        self.program('choice_nested','''impl R{fn yes()->Self{return R{status:0,value:42,detail:0};}}
fn work(ok:bool)->R{let n:u32=(if ok{match true{true=>R::yes(),false=>read(false)}}else{read(false)})?;
return R{status:0,value:n,detail:0};}''')

    def test_value_block_cleanup_precedes_propagation_cleanup(self):
        self.program('choice_cleanup','''fn work(ok:bool)->R{defer{unsafe{trace=trace*10+1;}}
let n:u32=(match ok{true=>{defer{unsafe{trace=trace*10+2;}}read(true)},
false=>{defer{unsafe{trace=trace*10+3;}}read(false)}})?;
return R{status:0,value:n,detail:0};}''','if unsafe{trace}!=2131{return 2;}')

    def test_unselected_calls_are_not_evaluated(self):
        self.program('choice_once','''fn observed(ok:bool)->R{unsafe{trace=trace+1;}return read(ok);}
fn work(ok:bool)->R{let n:u32=(if ok{observed(true)}else{observed(false)})?;
if unsafe{trace}!=1{return R{status:1,value:0,detail:0};}return R{status:0,value:n,detail:0};}''',
                     'if unsafe{trace}!=2{return 2;}')

    def test_nominal_mismatch_rejected_even_in_unselected_branch(self):
        self.compile('choice_nominal','''struct A{pub status:u32;pub value:u32;}struct B{pub status:u32;pub value:u32;}
fn work()->A{let n:u32=(if true{A{status:0,value:42}}else{B{status:0,value:42}})?;
return A{status:0,value:n};}pub fn main_entry()->u32{return 42;}''',False)


if __name__=='__main__':unittest.main()
