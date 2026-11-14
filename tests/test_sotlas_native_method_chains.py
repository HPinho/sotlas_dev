"""Native method chains over returned records and selected POD places."""
import unittest
import test_sotlas_native_i32 as harness


class NativeMethodChainTests(unittest.TestCase):
    setUpClass = classmethod(harness.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(harness.NativeI32Tests.tearDownClass.__func__)
    compile = harness.NativeI32Tests.compile
    link_image = harness.NativeI32Tests.link_image
    execute = harness.NativeI32Tests.execute

    def test_owned_factory_and_method_results_chain_into_scalar_and_void_calls(self):
        source = """struct Token{pub value:u32;}static mut closed:u32=0;
fn make(n:u32)->sole Token{return Token{value:n};}
impl Token{
fn add(self:sole Self,n:u32)->sole Self{return Token{value:self.value+n};}
fn take(self:sole Self)->u32{return self.value;}
fn close(self:sole Self)->void{unsafe{closed=self.value;}return;}}
pub fn main_entry()->u32{
if make(10).add(12).add(20).take()!=42{return 1;}
make(40).add(2).close();if unsafe{closed}!=42{return 2;}return 42;}"""
        self.execute(self.compile("method_chain_owned", source))

    def test_receiver_then_arguments_evaluate_once_in_source_order(self):
        source = """struct Token{pub value:u32;}static mut trace:u32=0;
fn make()->Token{unsafe{trace=trace*10+1;}return Token{value:40};}
fn argument()->u32{unsafe{trace=trace*10+2;}return 2;}
impl Token{fn read(self:&Self,n:u32)->u32{unsafe{trace=trace*10+3;}return self.value+n;}}
pub fn main_entry()->u32{
let answer:u32=make().read(argument());if unsafe{trace}!=123{return 1;}return answer;}"""
        self.execute(self.compile("method_chain_order", source))

    def test_fields_and_indexed_records_preserve_mutable_places(self):
        source = """struct Token{pub value:u32;}struct Outer{pub item:Token;pub items:[Token;2];}
static mut calls:u32=0;
fn index()->u32{unsafe{calls+=1;}return 1;}
impl Token{
fn bump(self:&mut Self,n:u32)->u32{self.value+=n;return self.value;}
fn read(self:&Self)->u32{return self.value;}}
pub fn main_entry()->u32{
let items:[Token;2]=[Token{value:1},Token{value:20}];
let mut outer:Outer=Outer{item:Token{value:10},items:items};
let first:u32=outer.item.bump(2);let second:u32=outer.items[index()].bump(10);
if first!=12 || second!=30 || unsafe{calls}!=1{return 1;}
return outer.item.read()+outer.items[1].read();}"""
        self.execute(self.compile("method_selected_places", source))

    def test_borrowed_methods_on_returned_records_and_owned_results(self):
        source = """struct Token{pub value:u32;}
fn make()->Token{return Token{value:40};}
impl Token{
fn copy(self:&Self)->Token{return Token{value:self.value};}
fn read(self:whisper Self,n:u32)->u32{return self.value+n;}}
pub fn main_entry()->u32{return make().copy().read(2);}"""
        self.execute(self.compile("method_borrowed_temporary", source))

    def test_receiver_consumption_and_immutable_roots_remain_checked(self):
        prefix = """struct Token{pub value:u32;}impl Token{
fn forward(self:sole Self)->sole Self{return self;}
fn read(self:whisper Self)->u32{return self.value;}
fn change(self:&mut Self)->u32{self.value=0;return 0;}
fn close(self:sole Self)->void{return;}}"""
        cases = (
            "fn wrong()->u32{let owner:sole Token=Token{value:42};owner.forward().close();return owner.read();}",
            "fn wrong(owner:whisper Token)->u32{return owner.forward().read();}",
            "struct Outer{pub item:Token;}const VALUE:Outer=Outer{item:Token{value:42}};"
            "fn wrong()->u32{return VALUE.item.change();}",
            "fn wrong()->u32{let owner:sole Token=Token{value:42};defer owner.forward().close();return 42;}",
            "fn make()->Token{return Token{value:42};}"
            "fn wrong()->u32{return make().missing();}",
            "struct Outer{pub items:[Token;1];}"
            "fn wrong()->u32{let items:[Token;1]=[Token{value:42}];"
            "let outer:Outer=Outer{items:items};return outer.items[1].read();}",
        )
        for index, source in enumerate(cases):
            with self.subTest(source=source):
                self.compile("method_chain_reject_" + str(index), prefix + source +
                             "pub fn main_entry()->u32{return 42;}", False)

    def test_deferred_factory_creates_and_closes_once_at_cleanup(self):
        source = """struct Token{pub value:u32;}static mut trace:u32=0;
fn make()->sole Token{unsafe{trace=trace*10+1;}return Token{value:42};}
impl Token{fn close(self:sole Self)->void{unsafe{trace=trace*10+2;}return;}}
fn work()->u32{defer make().close();if unsafe{trace}!=0{return 1;}return 7;}
pub fn main_entry()->u32{if work()!=7 || unsafe{trace}!=12{return 1;}return 42;}"""
        self.execute(self.compile("method_factory_defer", source))
