"""Deferred match selection with ownership, payloads and structured exits."""
import unittest
import test_sotlas_native_i32 as harness


PREFIX = """struct Token{pub value:u32;}static mut trace:u32=0;
impl Token{
fn read(self:whisper Self)->u32{return self.value;}
fn close(self:sole Self)->void{unsafe{trace=trace*10+self.value;}return;}}
fn observe(owner:whisper Token,n:u32)->void{unsafe{trace=trace*10+n;}return;}
fn take(owner:sole Token)->u32{return owner.value;}
"""


class NativeMatchCleanupTests(unittest.TestCase):
    setUpClass = classmethod(harness.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(harness.NativeI32Tests.tearDownClass.__func__)
    compile = harness.NativeI32Tests.compile
    link_image = harness.NativeI32Tests.link_image
    execute = harness.NativeI32Tests.execute

    def test_scalar_match_orders_consumption_and_outer_lifo(self):
        source = PREFIX + """
fn work(mode:u32,early:bool)->u32{
let a:sole Token=Token{value:1};let b:sole Token=Token{value:2};let c:sole Token=Token{value:3};
defer c.close();
defer{match mode{0=>{a.close();b.close();},1..=3=>{b.close();a.close();},_=>{a.close();b.close();}}}
if unsafe{trace}!=0{return 1;}if early{return 7;}return 9;}
pub fn main_entry()->u32{
if work(0,true)!=7 || unsafe{trace}!=123{return 1;}unsafe{trace=0;}
if work(2,false)!=9 || unsafe{trace}!=213{return 2;}unsafe{trace=0;}
if work(8,false)!=9 || unsafe{trace}!=123{return 3;}return 42;}"""
        self.execute(self.compile("cleanup_match_lifo", source))

    def test_payload_guards_shadowing_and_late_subject(self):
        source = PREFIX + """enum Choice{Number(u32),Empty}
fn work()->u32{
let owner:sole Token=Token{value:4};let mut selected:Choice=Choice::Empty;
defer{match selected{
Choice::Number(owner) if owner==2=>{observe(Token{value:0},owner);},
Choice::Number(n)=>{observe(Token{value:0},n);},Choice::Empty=>{observe(Token{value:0},9);}}
owner.close();}
selected=Choice::Number(2);return 7;}
pub fn main_entry()->u32{if work()!=7 || unsafe{trace}!=24{return 1;}return 42;}"""
        self.execute(self.compile("cleanup_match_payload", source))

    def test_match_borrows_owned_subject_without_consuming(self):
        source = PREFIX + """
pub fn main_entry()->u32{let owner:sole Token=Token{value:4};
{defer{match owner{Token{value:n} if n==4=>{observe(owner,n);},_=>{observe(owner,9);}}}}
if owner.read()!=4 || unsafe{trace}!=4{return 1;}
owner.close();if unsafe{trace}!=44{return 2;}return 42;}"""
        self.execute(self.compile("cleanup_match_snapshot", source))

    def test_nested_match_and_if_on_loop_exits(self):
        source = PREFIX + """
pub fn main_entry()->u32{let mut i:u32=0;while i<5{
let owner:sole Token=Token{value:i+1};
defer{match i{1=>{if true{owner.close();}else{owner.close();}},
_=>{match i%2{0=>{owner.close();},_=>{owner.close();}}}}}
i+=1;if i==1{continue;}if i==3{break;}}
if unsafe{trace}!=123{return 1;}return 42;}"""
        self.execute(self.compile("cleanup_match_loop", source))

    def test_invalid_owner_paths_and_cleanup_shapes_are_rejected(self):
        bodies = (
            "defer{match mode{0=>{owner.close();},_=>{owner.close();}}owner.read();}return 42;",
            "defer{match mode{0=>{owner.close();},_=>{owner.read();}}owner.close();}return 42;",
            "defer{match mode{0=>{owner.close();},_=>{owner.close();}}}return owner.read();",
            "defer{match mode{0=>{owner.close();},_=>{owner.close();}}}owner=Token{value:9};return 42;",
            "defer{match mode{0=>{take(owner);},_=>{owner.close();}}}return 42;",
            "defer{match mode{0=>{owner.close();owner.close();},_=>{owner.close();}}}return 42;",
            "defer{match mode{0=>{return;},_=>{owner.close();}}}return 42;",
            "defer{match mode{0=>{let copy:sole Token=owner;copy.close();},_=>{owner.close();}}}return 42;",
            "defer{match mode{0=>{owner.close();}}}return 42;",
        )
        for index, body in enumerate(bodies):
            with self.subTest(body=body):
                self.compile("cleanup_match_reject_" + str(index), PREFIX +
                             "fn work(mode:u32)->u32{let mut owner:sole Token=Token{value:4};" +
                             body + "}pub fn main_entry()->u32{return work(0);}", False)

    def test_error_propagation_runs_selected_cleanup_once(self):
        source = PREFIX + """enum Outcome{Ok(u32),Err(u32)}
fn result(failed:bool)->Outcome{if failed{return Outcome::Err(7);}return Outcome::Ok(42);}
fn work(failed:bool)->Outcome{
let owner:sole Token=Token{value:1};
defer{match failed{true=>{owner.close();},false=>{owner.close();}}}
let answer:u32=result(failed)?;return Outcome::Ok(answer);}
pub fn main_entry()->u32{
let a:u32=match work(true){Outcome::Ok(n)=>0,Outcome::Err(e)=>e};
if a!=7 || unsafe{trace}!=1{return 1;}
let b:u32=match work(false){Outcome::Ok(n)=>n,Outcome::Err(e)=>0};
if b!=42 || unsafe{trace}!=11{return 2;}return 42;}"""
        self.execute(self.compile("cleanup_match_propagate", source))

    def test_pattern_guards_and_calls_read_record_and_array_snapshots(self):
        source = PREFIX + """struct Pair{pub left:u32;pub right:u32;}
fn work()->void{
let owner:sole Token=Token{value:4};let values:[u32;2]=[1,2];
let pair:Pair=Pair{left:1,right:2};
defer{match pair{Pair{left:a,right:b} if a+b==3=>{
match values{[first,last] if first+last==3=>{observe(owner,last);owner.close();},
_=>{owner.close();}}},_=>{owner.close();}}}return;}
pub fn main_entry()->u32{work();if unsafe{trace}!=24{return 1;}return 42;}"""
        self.execute(self.compile("cleanup_match_patterns", source))

    def test_borrowed_owners_cannot_be_consumed_by_match_cleanup(self):
        self.compile("cleanup_match_borrowed", PREFIX + """
fn wrong(owner:whisper Token,mode:u32)->void{
defer{match mode{0=>{owner.close();},_=>{owner.close();}}}return;}
pub fn main_entry()->u32{return 42;}""", False)

    def test_pattern_declaration_does_not_reserve_shadowed_outer_owner(self):
        source = PREFIX + """enum Choice{Number(u32),Empty}
fn work()->void{
let owner:sole Token=Token{value:4};let cleanup:sole Token=Token{value:5};
let selected:Choice=Choice::Number(2);
defer{match selected{
Choice::Number(owner) if owner==2=>{observe(cleanup,owner);},
Choice::Number(n)=>{observe(cleanup,n);},Choice::Empty=>{observe(cleanup,9);}}
cleanup.close();}
owner.close();return;}
pub fn main_entry()->u32{work();if unsafe{trace}!=425{return 1;}return 42;}"""
        self.execute(self.compile("cleanup_match_outer_shadow", source))

    def test_subjects_and_guards_cannot_consume_or_mutate(self):
        helpers = """fn consume(owner:sole Token)->u32{return 0;}
fn mutate()->u32{unsafe{trace+=1;}return 0;}
fn effect()->bool{unsafe{trace+=1;}return true;}"""
        selections = (
            "match consume(owner){_=>{owner.close();}}",
            "match mutate(){_=>{owner.close();}}",
            "match mode{0 if effect()=>{owner.close();},_=>{owner.close();}}",
            "match mode{0 if consume(owner)==0=>{owner.close();},_=>{owner.close();}}",
        )
        for index, selection in enumerate(selections):
            self.compile("cleanup_match_effect_" + str(index), PREFIX + helpers +
                         "fn work(mode:u32)->u32{let owner:sole Token=Token{value:4};defer{" +
                         selection + "}return 42;}pub fn main_entry()->u32{return work(0);}", False)
