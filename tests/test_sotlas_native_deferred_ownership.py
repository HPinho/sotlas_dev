"""Native ownership transfer to deferred void cleanup."""
import unittest
import test_sotlas_native_i32 as harness


PREFIX = """struct Token{pub value:u32;}
static mut trace:u32=0;
fn close(value:sole Token)->void{unsafe{trace=trace*10+value.value;}return;}
fn read(value:whisper Token)->u32{return value.value;}
"""


class NativeDeferredOwnershipTests(unittest.TestCase):
    setUpClass = classmethod(harness.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(harness.NativeI32Tests.tearDownClass.__func__)
    compile = harness.NativeI32Tests.compile
    link_image = harness.NativeI32Tests.link_image
    execute = harness.NativeI32Tests.execute

    def test_cleanup_is_delayed_and_lifo_on_normal_and_early_returns(self):
        source = PREFIX + """
fn work(early:bool)->u32{
let first:sole Token=Token{value:1};let second:sole Token=Token{value:2};
defer close(first);defer close(second);
if unsafe{trace}!=0{return 1;}if early{return 7;}return 9;}
pub fn main_entry()->u32{
if work(true)!=7 || unsafe{trace}!=21{return 1;}
unsafe{trace=0;}if work(false)!=9 || unsafe{trace}!=21{return 2;}return 42;}
"""
        self.execute(self.compile("deferred_owner_lifo", source))

    def test_local_owners_close_on_backedge_continue_and_break(self):
        source = PREFIX + """
pub fn main_entry()->u32{
let mut i:u32=0;while i<5{
i+=1;let owner:sole Token=Token{value:i};defer close(owner);
if i==1{continue;}if i==3{break;}}
if unsafe{trace}!=123{return 1;}return 42;}
"""
        self.execute(self.compile("deferred_owner_loop", source))

    def test_nested_scope_and_two_consuming_arguments(self):
        source = PREFIX + """
fn pair(a:sole Token,b:sole Token)->void{close(a);close(b);return;}
pub fn main_entry()->u32{
let a:sole Token=Token{value:1};let b:sole Token=Token{value:2};
{defer pair(a,b);if unsafe{trace}!=0{return 1;}}
if unsafe{trace}!=12{return 2;}return 42;}
"""
        self.execute(self.compile("deferred_owner_pair", source))

    def test_reserved_owner_cannot_be_read_moved_reassigned_or_closed_twice(self):
        bodies = (
            "defer close(owner);return read(owner);",
            "defer close(owner);close(owner);return 42;",
            "defer close(owner);defer close(owner);return 42;",
            "defer close(owner);owner=Token{value:9};return 42;",
            "defer close(owner);owner.value=9;return 42;",
            "if flag{defer close(owner);}return read(owner);",
        )
        for index, body in enumerate(bodies):
            with self.subTest(body=body):
                self.compile("deferred_owner_reject_" + str(index), PREFIX +
                             "fn work(flag:bool)->u32{let mut owner:sole Token=Token{value:4};" +
                             body + "}pub fn main_entry()->u32{return work(true);}", False)

    def test_existing_borrow_reservation_and_nonvoid_cleanup_remain_rejected(self):
        cases = (
            "defer observe(owner);defer close(owner);",
            "defer take(owner);",
            "defer {close(owner);}",
            "defer close(identity(owner));",
        )
        helpers = """fn observe(value:whisper Token)->void{return;}
fn take(value:sole Token)->u32{return value.value;}
fn identity(value:sole Token)->sole Token{return value;}"""
        for index, body in enumerate(cases):
            with self.subTest(body=body):
                self.compile("deferred_owner_boundary_" + str(index), PREFIX + helpers +
                             "pub fn main_entry()->u32{let owner:sole Token=Token{value:1};" +
                             body + "return 42;}", False)
