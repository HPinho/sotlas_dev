"""Native conditional cleanup, path-specific ownership and late conditions."""
import unittest
import test_sotlas_native_i32 as harness


PREFIX = """struct Token{pub value:u32;}static mut trace:u32=0;
impl Token{
fn read(self:whisper Self)->u32{return self.value;}
fn close(self:sole Self)->void{unsafe{trace=trace*10+self.value;}return;}}
fn close(value:sole Token)->void{value.close();return;}
fn take(value:sole Token)->u32{return value.value;}
fn observe(value:whisper Token)->void{unsafe{trace=trace*10+value.value;}return;}
"""


class NativeConditionalCleanupTests(unittest.TestCase):
    setUpClass = classmethod(harness.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(harness.NativeI32Tests.tearDownClass.__func__)
    compile = harness.NativeI32Tests.compile
    link_image = harness.NativeI32Tests.link_image
    execute = harness.NativeI32Tests.execute

    def test_both_branches_release_multiple_owners_before_outer_lifo_cleanup(self):
        source = PREFIX + """
fn work(flag:bool,early:bool)->u32{
let a:sole Token=Token{value:1};let b:sole Token=Token{value:2};let c:sole Token=Token{value:3};
defer c.close();
defer{if flag{observe(a);a.close();b.close();}else{observe(b);b.close();a.close();}}
if unsafe{trace}!=0{return 1;}if early{return 7;}return 9;}
pub fn main_entry()->u32{
if work(true,true)!=7 || unsafe{trace}!=1123{return 1;}unsafe{trace=0;}
if work(false,false)!=9 || unsafe{trace}!=2213{return 2;}return 42;}"""
        self.execute(self.compile("cleanup_conditional_lifo", source))

    def test_conditions_run_on_exit_and_allow_else_if_and_nested_blocks(self):
        source = PREFIX + """
fn work()->void{
let mut flag:bool=false;let owner:sole Token=Token{value:4};
defer{if flag{{owner.close();}}else if false{close(owner);}else{owner.close();}}
flag=true;return;}
pub fn main_entry()->u32{work();if unsafe{trace}!=4{return 1;}return 42;}"""
        self.execute(self.compile("cleanup_condition_late", source))

    def test_branch_cleanup_on_loop_backedge_break_and_continue(self):
        source = PREFIX + """
pub fn main_entry()->u32{
let mut i:u32=0;while i<5{
i+=1;let owner:sole Token=Token{value:i};
defer{if i%2==0{close(owner);}else{owner.close();}}
if i==1{continue;}if i==3{break;}}
if unsafe{trace}!=123{return 1;}return 42;}"""
        self.execute(self.compile("cleanup_conditional_loop", source))

    def test_no_else_borrow_and_owner_conditions_remain_nonconsuming(self):
        source = PREFIX + """
pub fn main_entry()->u32{
let owner:sole Token=Token{value:4};
{defer{if owner.value==4{observe(owner);}}}
if owner.read()!=4 || unsafe{trace}!=4{return 1;}
owner.close();if unsafe{trace}!=44{return 2;}return 42;}"""
        self.execute(self.compile("cleanup_conditional_borrow", source))

    def test_invalid_paths_and_post_capture_uses_are_rejected(self):
        bodies = (
            "defer{if flag{owner.close();}else{owner.close();}owner.read();}return 42;",
            "defer{if flag{owner.close();}owner.close();}return 42;",
            "defer{if flag{owner.close();}}return owner.read();",
            "defer{if flag{owner.close();}else{owner.close();}}owner=Token{value:9};return 42;",
            "defer{if flag{take(owner);}else{owner.close();}}return 42;",
            "defer{if flag{owner.close();owner.close();}}return 42;",
            "defer{if flag{return;}}return 42;",
            "defer{if flag{let copy:sole Token=owner;copy.close();}}return 42;",
        )
        for index, body in enumerate(bodies):
            with self.subTest(body=body):
                self.compile("cleanup_conditional_reject_" + str(index), PREFIX +
                             "fn work(flag:bool)->u32{let mut owner:sole Token=Token{value:4};" +
                             body + "}pub fn main_entry()->u32{return work(true);}", False)

    def test_conditions_cannot_consume_or_produce_side_effects(self):
        helpers = """fn consume(value:sole Token)->bool{return true;}
fn mutate()->bool{unsafe{trace+=1;}return true;}"""
        for index, condition in enumerate(("consume(owner)", "mutate()")):
            self.compile("cleanup_condition_effect_" + str(index), PREFIX + helpers +
                         "pub fn main_entry()->u32{let owner:sole Token=Token{value:4};"
                         "defer{if " + condition + "{owner.close();}else{close(owner);}}return 42;}", False)
