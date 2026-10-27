"""Native typed record-pointer receivers without pointer/value conflation."""
import unittest
import test_sotlas_native_i32 as previous


class NativePointerProjectionTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,source):self.execute(self.compile(name,source))

    def test_nested_pointer_read_uses_pointee_not_pointer_slot(self):
        self.program('projection_read','''struct Leaf{pub n:u32;}struct Root{pub pad:u64;pub child:*mut Leaf;}
pub fn main_entry()->u32{let mut leaf:Leaf=Leaf{n:42};let p:*mut Leaf=unsafe{(&mut leaf) as *mut Leaf};
let mut root:Root=Root{pad:99,child:p};let mut r:*mut Root=unsafe{(&mut root) as *mut Root};return unsafe{r.child.n};}''')
        self.program('projection_unsafe_wrapper','''struct Leaf{pub n:u32;}struct Root{pub child:*mut Leaf;}
pub fn main_entry()->u32{let mut leaf:Leaf=Leaf{n:42};let p:*mut Leaf=unsafe{(&mut leaf) as *mut Leaf};
let root:Root=Root{child:p};return unsafe{(unsafe{root.child}).n};}''')

    def test_nested_pointer_write_updates_original_storage(self):
        self.program('projection_write','''struct Leaf{pub n:u32;}struct Root{pub child:*mut Leaf;}
pub fn main_entry()->u32{let mut leaf:Leaf=Leaf{n:1};let p:*mut Leaf=unsafe{(&mut leaf) as *mut Leaf};
let mut root:Root=Root{child:p};let mut r:*mut Root=unsafe{(&mut root) as *mut Root};unsafe{r.child.n=42;}return leaf.n;}''')

    def test_mixed_inline_records_and_pointer_chain(self):
        self.program('projection_mixed','''struct Leaf{pub n:u32;}struct Holder{pub pad:u64;pub leaf:*mut Leaf;}
struct Root{pub holder:Holder;}struct Top{pub root:*mut Root;}
pub fn main_entry()->u32{let mut leaf:Leaf=Leaf{n:1};let p:*mut Leaf=unsafe{(&mut leaf) as *mut Leaf};
let mut root:Root=Root{holder:Holder{pad:99,leaf:p}};let mut r:*mut Root=unsafe{(&mut root) as *mut Root};
let mut top:Top=Top{root:r};unsafe{top.root.holder.leaf.n=42;}return leaf.n;}''')

    def test_pointer_local_from_projection_stays_a_pointer(self):
        self.program('projection_pointer_value','''struct Leaf{pub n:u32;}struct Root{pub child:*mut Leaf;}
pub fn main_entry()->u32{let mut leaf:Leaf=Leaf{n:1};let p:*mut Leaf=unsafe{(&mut leaf) as *mut Leaf};
let mut root:Root=Root{child:p};let mut q:*mut Leaf=root.child;unsafe{q.n=42;}
if q!=p{return 1;}return leaf.n;}''')

    def test_reassigned_pointer_field_is_loaded_again(self):
        self.program('projection_retarget','''struct Leaf{pub n:u32;}struct Root{pub child:*mut Leaf;}
pub fn main_entry()->u32{let mut a:Leaf=Leaf{n:20};let mut b:Leaf=Leaf{n:22};
let pa:*mut Leaf=unsafe{(&mut a) as *mut Leaf};let pb:*mut Leaf=unsafe{(&mut b) as *mut Leaf};
let mut root:Root=Root{child:pa};let mut r:*mut Root=unsafe{(&mut root) as *mut Root};
let first:u32=unsafe{r.child.n};unsafe{r.child=pb;}return first+unsafe{r.child.n};}''')

    def test_recursive_record_pointer_chain(self):
        self.program('projection_recursive','''struct Node{pub n:u32;pub next:*mut Node;}
pub fn main_entry()->u32{let mut tail:Node=Node{n:42,next:null};let t:*mut Node=unsafe{(&mut tail) as *mut Node};
let mut head:Node=Node{n:1,next:t};let h:*mut Node=unsafe{(&mut head) as *mut Node};
unsafe{tail.next=h;}return unsafe{h.next.next.next.n};}''')

    def test_pointer_returning_receiver_evaluated_once_before_rhs(self):
        self.program('projection_call','''struct Leaf{pub n:u32;}struct Root{pub child:*mut Leaf;}
static mut trace:u32=0;
fn receiver(p:*mut Root)->*mut Root{unsafe{trace=trace*10+1;}return p;}
fn value()->u32{unsafe{trace=trace*10+2;}return 42;}
pub fn main_entry()->u32{let mut leaf:Leaf=Leaf{n:0};let p:*mut Leaf=unsafe{(&mut leaf) as *mut Leaf};
let mut root:Root=Root{child:p};let mut r:*mut Root=unsafe{(&mut root) as *mut Root};
unsafe{receiver(r).child.n=value();}if unsafe{trace}!=12{return 1;}return leaf.n;}''')

    def test_scalar_widths_and_float_fields(self):
        self.program('projection_widths','''struct Leaf{pub small:i8;pub wide:u64;pub value:f64;pub ok:bool;}
struct Root{pub leaf:*mut Leaf;}
pub fn main_entry()->u32{let mut leaf:Leaf=Leaf{small:-7,wide:4294967297,value:1.5,ok:true};
let p:*mut Leaf=unsafe{(&mut leaf) as *mut Leaf};let mut root:Root=Root{leaf:p};
if unsafe{root.leaf.small}!=-7 || unsafe{root.leaf.wide}!=4294967297 || !unsafe{root.leaf.ok}{return 1;}
unsafe{root.leaf.value=root.leaf.value*2.0;}if leaf.value!=3.0{return 2;}return 42;}''')

    def test_inline_record_projection_is_copied_as_a_value(self):
        self.program('projection_inline_copy','''struct Item{pub n:u32;}struct Leaf{pub item:Item;}struct Root{pub leaf:*mut Leaf;}
pub fn main_entry()->u32{let mut leaf:Leaf=Leaf{item:Item{n:42}};let p:*mut Leaf=unsafe{(&mut leaf) as *mut Leaf};
let mut root:Root=Root{leaf:p};let copy:Item=unsafe{root.leaf.item};unsafe{root.leaf.item.n=1;}return copy.n;}''')

    def test_record_dereference_copy_and_whole_field_assignment(self):
        self.program('projection_record_copy','''struct Item{pub n:u32;}struct Leaf{pub item:Item;}struct Root{pub leaf:*mut Leaf;}
pub fn main_entry()->u32{let mut leaf:Leaf=Leaf{item:Item{n:42}};let p:*mut Leaf=unsafe{(&mut leaf) as *mut Leaf};
let mut root:Root=Root{leaf:p};let copy:Leaf=unsafe{*root.leaf};unsafe{root.leaf.item=Item{n:1};}return copy.item.n;}''')

    def test_plain_record_dereference_is_an_independent_snapshot(self):
        self.program('projection_plain_snapshot','''struct Item{pub n:u32;}
pub fn main_entry()->u32{let mut item:Item=Item{n:42};let mut p:*mut Item=unsafe{(&mut item) as *mut Item};
let snapshot:Item=unsafe{*p};unsafe{p.n=1;}return snapshot.n;}''')

    def test_record_snapshot_is_captured_each_loop_iteration(self):
        self.program('projection_loop_snapshot','''struct Item{pub n:u32;}
pub fn main_entry()->u32{let mut item:Item=Item{n:0};let mut p:*mut Item=unsafe{(&mut item) as *mut Item};
let mut i:u32=0;let mut sum:u32=0;while i<7{let snapshot:Item=unsafe{*p};unsafe{p.n=p.n+1;}
sum=sum+snapshot.n;i=i+1;}return sum*2;}''')

    def test_inline_array_field_through_pointer_chain(self):
        self.program('projection_array','''struct Leaf{pub values:[u32;2];}struct Root{pub leaf:*mut Leaf;}
pub fn main_entry()->u32{let mut leaf:Leaf=Leaf{values:[20,1]};let p:*mut Leaf=unsafe{(&mut leaf) as *mut Leaf};
let mut root:Root=Root{leaf:p};unsafe{root.leaf.values[1]=22;}return unsafe{root.leaf.values[0]+root.leaf.values[1]};}''')

    def test_pointer_bearing_record_arrays_remain_rejected(self):
        self.compile('projection_array_record','''struct Leaf{pub n:u32;}struct Holder{pub leaf:*mut Leaf;}
pub fn main_entry()->u32{let mut leaf:Leaf=Leaf{n:42};let p:*mut Leaf=unsafe{(&mut leaf) as *mut Leaf};
let holders:[Holder;2]=[Holder{leaf:p};2];return unsafe{holders[1].leaf.n};}''',False)

    def test_const_pointee_read_is_allowed(self):
        self.program('projection_const_read','''struct Leaf{pub n:u32;}struct Root{pub leaf:*const Leaf;}
pub fn main_entry()->u32{let leaf:Leaf=Leaf{n:42};let p:*const Leaf=unsafe{(&leaf) as *const Leaf};
let mut root:Root=Root{leaf:p};return unsafe{root.leaf.n};}''')

    def test_unsafe_and_const_rejections_are_preserved(self):
        for i,(pointer,operation) in enumerate((('*mut Leaf','return root.leaf.n;'),
                                                ('*const Leaf','unsafe{root.leaf.n=42;}return 42;'),
                                                ('*mut Leaf','root.leaf.n=42;return 42;'))):
            self.compile('projection_invalid_'+str(i),'''struct Leaf{pub n:u32;}struct Root{pub leaf:TYPE;}
pub fn main_entry()->u32{let mut root:Root=Root{leaf:null};OP}'''.replace('TYPE',pointer).replace('OP',operation),False)
        self.compile('projection_const_call','''struct Leaf{pub n:u32;}struct Root{pub leaf:*mut Leaf;}
fn get()->*const Root{return null;}
pub fn main_entry()->u32{unsafe{get().leaf.n=42;}return 42;}''',False)
        self.compile('projection_unsafe_call','''struct Leaf{pub n:u32;}struct Root{pub leaf:*mut Leaf;}
fn get()->*mut Root{return null;}
pub fn main_entry()->u32{return get().leaf.n;}''',False)
        self.compile('projection_unsafe_scope','''struct Leaf{pub n:u32;}struct Root{pub leaf:*mut Leaf;}
pub fn main_entry()->u32{let root:Root=Root{leaf:null};return (unsafe{root.leaf}).n;}''',False)


if __name__=='__main__':unittest.main()
