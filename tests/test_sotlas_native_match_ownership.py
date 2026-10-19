"""Branch-sensitive native match ownership, including value-block cleanup."""
import unittest
import test_sotlas_native_i32 as previous


class NativeMatchOwnershipTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_exclusive_result_moves_on_selected_arm(self):
        self.program('match_owner_result', '''struct Box{pub value:u32;}
fn choose(flag:bool,a:sole Box,b:sole Box)->sole Box{return match flag{true=>a,false=>b};}
pub fn main_entry()->u32{let a:sole Box=Box{value:42};let b:sole Box=Box{value:1};
let result:sole Box=choose(true,a,b);return result.value;}''')

    def test_same_owner_in_disjoint_arms(self):
        self.program('match_owner_disjoint', '''struct Box{pub value:u32;}
fn consume(v:sole Box)->u32{return v.value;}
pub fn main_entry()->u32{let v:sole Box=Box{value:42};
return match true{true=>consume(v),false=>consume(v)};}''')

    def test_maybe_moved_capture_rejected(self):
        self.compile('match_owner_maybe', '''struct Box{pub value:u32;}
fn consume(v:sole Box)->u32{return v.value;}
pub fn main_entry()->u32{let v:sole Box=Box{value:42};
let result:u32=match true{true=>consume(v),false=>0};return v.value;}''', False)

    def test_guard_cannot_move_before_fallthrough(self):
        self.compile('match_owner_guard', '''struct Box{pub value:u32;}
fn consume(v:sole Box)->bool{return true;}
pub fn main_entry()->u32{let v:sole Box=Box{value:42};
return match true{true if consume(v)=>42,_=>0};}''', False)

    def test_borrowing_guard_and_owner_projection(self):
        self.program('match_owner_borrow', '''struct Box{pub value:u32;}
fn read(v:whisper Box)->u32{return v.value;}
pub fn main_entry()->u32{let v:sole Box=Box{value:42};
return match true{true if read(v)==42=>v.value,_=>0};}''')

    def test_value_block_moves_and_lifo_cleanup(self):
        self.program('match_owner_block', '''struct Box{pub value:u32;}
fn consume(v:sole Box)->u32{return v.value;}
pub fn main_entry()->u32{let v:sole Box=Box{value:40};let mut trace:u32=0;
let answer:u32=match true{true=>{defer{trace=trace+2;}let n:u32=consume(v);n},false=>0};
return answer+trace;}''')

    def test_value_block_yields_owned_record(self):
        self.program('match_owner_block_result', '''struct Box{pub value:u32;}
pub fn main_entry()->u32{let a:sole Box=Box{value:42};let b:sole Box=Box{value:0};
let chosen:sole Box=match true{true=>{a},false=>{b}};return chosen.value;}''')

    def test_reserved_defer_prevents_move_in_arm(self):
        self.compile('match_owner_defer', '''struct Box{pub value:u32;}
fn read(v:whisper Box)->u32{return v.value;}fn consume(v:sole Box)->u32{return v.value;}
pub fn main_entry()->u32{let v:sole Box=Box{value:42};defer read(v);
return match true{true=>consume(v),false=>0};}''', False)

    def test_local_owner_does_not_escape_into_plain_result(self):
        self.compile('match_owner_local_escape', '''struct Box{pub value:u32;}
pub fn main_entry()->u32{let chosen:Box=match true{
true=>{let owner:sole Box=Box{value:42};owner},false=>Box{value:0}};return chosen.value;}''', False)

    def test_returning_arm_does_not_poison_live_successor(self):
        self.program('match_owner_return_edge', '''struct Box{pub value:u32;}
fn consume(v:sole Box)->u32{return v.value;}
fn read(flag:bool,v:sole Box)->u32{let extra:u32=match flag{
true=>{return consume(v);},false=>0};return v.value+extra;}
pub fn main_entry()->u32{let a:sole Box=Box{value:42};let b:sole Box=Box{value:42};
if read(true,a)!=42{return 1;}return read(false,b);}''')

    def test_branch_local_owner_is_moved_once(self):
        self.program('match_owner_local_yield', '''struct Box{pub value:u32;}
pub fn main_entry()->u32{let chosen:sole Box=match false{
true=>{let owner:sole Box=Box{value:0};owner},
false=>{let owner:sole Box=Box{value:42};owner}};return chosen.value;}''')


if __name__ == '__main__':
    unittest.main()
