"""Native consuming receivers, value semantics and deferred method cleanup."""
import unittest
import test_sotlas_native_i32 as harness


class NativeConsumingMethodTests(unittest.TestCase):
    setUpClass = classmethod(harness.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(harness.NativeI32Tests.tearDownClass.__func__)
    compile = harness.NativeI32Tests.compile
    link_image = harness.NativeI32Tests.link_image
    execute = harness.NativeI32Tests.execute

    def test_scalar_and_owned_returns_forward_self(self):
        source = """struct Token{pub value:u32;}
impl Token{
fn forward(self:sole Self)->sole Self{return self;}
fn take(self:sole Self,extra:u32)->u32{return self.value+extra;}}
pub fn main_entry()->u32{
let first:sole Token=Token{value:40};let next:sole Token=first.forward();
return next.take(2);}"""
        self.execute(self.compile("consuming_self_return", source))

    def test_consuming_receivers_copy_unqualified_values_in_both_call_paths(self):
        source = """struct Token{pub value:u32;}
impl Token{
fn number(mut self:sole Token)->u32{self.value=1;return self.value;}
fn clear(mut self:sole Self)->void{self.value=0;return;}}
pub fn main_entry()->u32{
let mut value:Token=Token{value:42};if value.number()!=1{return 1;}
value.clear();return value.value;}"""
        self.execute(self.compile("consuming_receiver_copy", source))

    def test_self_forwards_to_named_parameters_and_associated_self_parameters(self):
        source = """struct Token{pub value:u32;}static mut total:u32=0;
fn read(value:whisper Token)->u32{return value.value;}
fn dispose(value:sole Token)->void{unsafe{total=value.value;}return;}
impl Token{
fn peek(self:whisper Self)->u32{return read(self);}
fn close(self:sole Self)->void{dispose(self);return;}
fn forward(value:sole Self)->sole Self{return value;}}
pub fn main_entry()->u32{
let first:sole Token=Token{value:42};let next:sole Token=Token::forward(first);
if next.peek()!=42{return 1;}{defer next.close();}
if unsafe{total}!=42{return 2;}return 42;}"""
        self.execute(self.compile("consuming_method_self_forward", source))

    def test_nested_fields_and_array_payloads_survive_owned_method_returns(self):
        source = """struct Inner{pub value:u32;}struct Token{pub data:[u8;3];pub inner:Inner;}
impl Token{
fn forward(self:sole Self)->sole Self{return self;}
fn take(self:sole Self)->u32{return (self.data[0] as u32)+(self.data[2] as u32)+self.inner.value;}}
pub fn main_entry()->u32{
let data:[u8;3]=[10,0,12];let first:sole Token=Token{data:data,inner:Inner{value:20}};
let next:sole Token=first.forward();return next.take();}"""
        self.execute(self.compile("consuming_method_aggregate", source))

    def test_methods_and_associated_cleanup_preserve_lifo(self):
        source = """struct Token{pub value:u32;}static mut trace:u32=0;
impl Token{
fn read(self:whisper Self)->u32{return self.value;}
fn close(self:sole Self)->void{unsafe{trace=trace*10+self.value;}return;}
fn dispose(value:sole Token)->void{value.close();return;}}
fn work(early:bool)->u32{
let a:sole Token=Token{value:1};let b:sole Token=Token{value:2};
let c:sole Token=Token{value:3};defer Token::dispose(c);
defer{a.read();a.close();b.close();}
if unsafe{trace}!=0{return 1;}if early{return 7;}return 9;}
pub fn main_entry()->u32{
if work(true)!=7 || unsafe{trace}!=123{return 1;}unsafe{trace=0;}
if work(false)!=9 || unsafe{trace}!=123{return 2;}return 42;}"""
        self.execute(self.compile("consuming_method_defer", source))

    def test_deferred_receiver_on_loop_jumps(self):
        source = """struct Token{pub value:u32;}static mut total:u32=0;
impl Token{fn close(self:sole Token)->void{unsafe{total+=self.value;}return;}}
pub fn main_entry()->u32{let mut i:u32=0;
while i<5{i+=1;let owner:sole Token=Token{value:i};defer owner.close();
if i==1{continue;}if i==3{break;}}
if unsafe{total}!=6{return 1;}return 42;}"""
        self.execute(self.compile("consuming_method_loop", source))

    def test_moved_borrowed_and_deferred_receivers_cannot_be_consumed_again(self):
        prefix = """struct Token{pub value:u32;}impl Token{
fn read(self:whisper Self)->u32{return self.value;}
fn take(self:sole Self)->u32{return self.value;}
fn close(self:sole Self)->void{return;}
fn overlap(self:sole Self,other:whisper Token)->u32{return other.value;}}"""
        bodies = (
            "owner.take();return owner.read();",
            "defer owner.close();return owner.read();",
            "defer owner.close();defer owner.close();return 42;",
            "defer{owner.close();owner.read();}return 42;",
            "defer owner.close();owner=Token{value:9};return 42;",
            "return owner.overlap(owner);",
            "if flag{owner.close();}return owner.read();",
        )
        for index, body in enumerate(bodies):
            with self.subTest(body=body):
                self.compile("consuming_method_reject_" + str(index), prefix +
                             "fn work(flag:bool)->u32{let mut owner:sole Token=Token{value:42};" +
                             body + "}pub fn main_entry()->u32{return work(true);}", False)
        self.compile("consuming_borrowed_receiver", prefix +
                     "fn wrong(owner:whisper Token)->u32{return owner.take();}"
                     "pub fn main_entry()->u32{return 42;}", False)

    def test_wrong_receiver_types_and_nonvoid_deferred_consumers_are_rejected(self):
        cases = (
            "struct Other{pub value:u32;}impl Token{fn bad(self:sole Other)->void{return;}}",
            "struct Other{pub value:u32;}fn use_other(value:sole Other)->void{return;}"
            "impl Token{fn bad(self:sole Self)->void{use_other(self);return;}}",
            "impl Token{fn take(self:sole Self)->u32{return self.value;}}"
            "fn wrong()->void{let owner:sole Token=Token{value:42};defer owner.take();return;}",
        )
        for index, source in enumerate(cases):
            self.compile("consuming_method_boundary_" + str(index),
                         "struct Token{pub value:u32;}" + source +
                         "pub fn main_entry()->u32{return 42;}", False)
