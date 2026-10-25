"""Native array transfers and no-escape parameter contracts."""
import unittest
import test_sotlas_native_i32 as previous


class NativeOwnedArrayAbiTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_exclusive_array_parameter_return_and_local_move(self):
        self.program('owned_array_transfer', '''fn pass(a:sole [u32;2])->sole [u32;2]{return a;}
pub fn main_entry()->u32{let a:sole [u32;2]=[20,22];let b:sole [u32;2]=pass(a);
let c:sole [u32;2]=b;return c[0]+c[1];}''')

    def test_whisper_and_direct_forward_without_consuming(self):
        for domain in ('whisper', 'direct'):
            with self.subTest(domain=domain):
                self.program('owned_array_borrow_'+domain, '''fn read(a:DOMAIN [u32;2])->u32{return a[0]+a[1];}
fn forward(a:DOMAIN [u32;2])->u32{return read(a);}
fn consume(a:sole [u32;2])->u32{return match a{[x,y]=>x+y};}
pub fn main_entry()->u32{let a:sole [u32;2]=[20,22];if forward(a)!=42{return 1;}return consume(a);}'''.replace('DOMAIN', domain))

    def test_pod_record_array_transfer_and_borrow(self):
        self.program('owned_array_records', '''struct Item{pub n:u32;pub bytes:[u8;2];}
fn read(a:whisper [Item;2])->u32{return a[0].n+a[1].n;}
fn pass(a:sole [Item;2])->sole [Item;2]{return a;}
pub fn main_entry()->u32{let a:sole [Item;2]=[Item{n:20,bytes:[7;2]},Item{n:22,bytes:[9;2]}];
if read(a)!=42{return 1;}let b:sole [Item;2]=pass(a);return b[0].n+b[1].n;}''')

    def test_disjoint_moves_match_and_conditional_results(self):
        self.program('owned_array_branches', '''fn select(flag:bool,a:sole [u32;2],b:sole [u32;2])->sole [u32;2]{
return match flag{true=>a,false=>b};}
pub fn main_entry()->u32{let a:sole [u32;2]=[20,22];let b:sole [u32;2]=[0;2];
let c:sole [u32;2]=select(true,a,b);let d:sole [u32;2]=if true{c}else{[0;2]};return d[0]+d[1];}''')

    def test_void_borrow_and_lifo_defer(self):
        self.program('owned_array_defer', '''static mut trace:u32=0;
fn observe(a:whisper [u32;2])->void{unsafe{trace=trace+a[0]+a[1];}return;}
fn work()->u32{let a:sole [u32;2]=[20,22];defer observe(a);return 0;}
pub fn main_entry()->u32{let ignored:u32=work();return unsafe{trace};}''')

    def test_owned_return_captured_before_local_cleanup(self):
        self.program('owned_array_return_cleanup', '''static mut trace:u32=0;
fn make()->sole [u32;2]{defer{unsafe{trace=7;}}return [20,22];}
pub fn main_entry()->u32{let a:sole [u32;2]=make();if unsafe{trace}!=7{return 1;}return a[0]+a[1];}''')

    def test_exclusive_spelling_and_stack_parameter_roundtrip(self):
        self.program('owned_array_exclusive_stack', '''fn pass(a:u32,b:u32,c:u32,d:u32,e:u32,f:u32,g:u32,
values:exclusive [u32;2])->exclusive [u32;2]{return values;}
pub fn main_entry()->u32{let a:exclusive [u32;2]=[20,22];
let b:exclusive [u32;2]=pass(1,2,3,4,5,6,7,a);return b[0]+b[1];}''')

    def test_direct_temporaries_and_whisper_snapshots(self):
        self.program('owned_array_direct_temporary', '''fn read(a:direct [u32;2])->u32{return a[0]+a[1];}
pub fn main_entry()->u32{if read([20,22])!=42 || read([21;2])!=42{return 1;}
return read(match true{true=>[20,22],false=>[0;2]});}''')
        self.program('owned_array_borrow_storage', '''fn change(p:*mut u32)->u32{unsafe{*p=0;}return 0;}
fn snapshot(a:whisper [u32;2],ignored:u32)->u32{return a[0]+a[1];}
fn address(a:direct [u32;2],ignored:u32)->u32{return a[0]+a[1];}
pub fn main_entry()->u32{let mut a:[u32;2]=[20,22];let p:*mut u32=unsafe{a as *mut u32};
if snapshot(a,change(p))!=42{return 1;}a[0]=20;
if address(a,change(p))!=22{return 2;}return 42;}''')

    def test_raw_pointer_local_projection_tracks_current_pointer(self):
        self.program('resource_pointer_projection', '''struct Cell{pub n:u32;pub next:*mut u32;}
pub fn main_entry()->u32{let mut x:u32=20;let mut y:u32=22;
let mut a:Cell=Cell{n:1,next:unsafe{(&mut x) as *mut u32}};
let mut b:Cell=Cell{n:2,next:unsafe{(&mut y) as *mut u32}};
let mut p:*mut Cell=unsafe{(&mut a) as *mut Cell};
let q:*const Cell=unsafe{(&mut b) as *const Cell};
unsafe{if p.next==q.next{return 1;}p.n=20;}
p=unsafe{(&mut b) as *mut Cell};unsafe{p.n=22;}
if a.n!=20 || b.n!=22{return 2;}return a.n+b.n;}''')
        self.compile('resource_const_pointer_mutation', '''struct Cell{pub n:u32;}
pub fn main_entry()->u32{let mut c:Cell=Cell{n:42};
let mut p:*const Cell=unsafe{(&mut c) as *const Cell};unsafe{p.n=0;}return c.n;}''', False)

    def test_use_after_move_and_duplicate_consumption_rejected(self):
        for i,tail in enumerate(('consume(a);return a[0];','return both(a,a);',
                                 'let b:sole [u32;2]=a;return a[0];')):
            with self.subTest(tail=tail):
                self.compile('owned_array_moved_'+str(i), '''fn consume(a:sole [u32;2])->u32{return 42;}
fn both(a:sole [u32;2],b:sole [u32;2])->u32{return 42;}
pub fn main_entry()->u32{let a:sole [u32;2]=[20,22];'''+tail+'}', False)

    def test_maybe_moved_join_and_loop_backedge_rejected(self):
        cases=('if true{consume(a);}return a[0];',
               'let n:u32=match true{true=>consume(a),false=>0};return a[0];',
               'let mut n:u32=0;while n<2{consume(a);n=n+1;}return 42;')
        for i,body in enumerate(cases):
            self.compile('owned_array_join_'+str(i), '''fn consume(a:sole [u32;2])->u32{return 42;}
pub fn main_entry()->u32{let a:sole [u32;2]=[20,22];'''+body+'}', False)

    def test_borrow_cannot_escape_to_return_local_or_pointer(self):
        for domain in ('whisper', 'direct'):
            for i,body in enumerate(('return a;', 'let b:sole [u32;2]=a;return [20,22];',
                                     'let p:*const u32=unsafe{a as *const u32};return [20,22];')):
                self.compile('owned_array_escape_'+domain+str(i),
                    'fn bad(a:'+domain+' [u32;2])->sole [u32;2]{'+body+'}pub fn main_entry()->u32{return 42;}', False)

    def test_borrow_consumption_and_mutation_rejected(self):
        for domain in ('whisper', 'direct'):
            for i,body in enumerate(('return consume(a);','a[0]=0;return 42;')):
                self.compile('owned_array_borrow_bad_'+domain+str(i), '''fn consume(a:sole [u32;2])->u32{return 42;}
fn bad(mut a:DOMAIN [u32;2])->u32{BODY}pub fn main_entry()->u32{return 42;}'''.replace('DOMAIN',domain).replace('BODY',body), False)

    def test_reservation_and_same_call_borrow_move_conflicts_rejected(self):
        for i,body in enumerate(('defer read(a);return consume(a);', 'return both(a,a);')):
            self.compile('owned_array_reservation_'+str(i), '''fn read(a:whisper [u32;2])->u32{return 42;}
fn consume(a:sole [u32;2])->u32{return 42;}
fn both(a:whisper [u32;2],b:sole [u32;2])->u32{return 42;}
pub fn main_entry()->u32{let a:sole [u32;2]=[20,22];'''+body+'}', False)

    def test_plain_destination_and_foreign_owned_arrays_rejected(self):
        cases=('fn bad(a:sole [u32;2])->[u32;2]{return a;}',
               'fn bad()->u32{let a:sole [u32;2]=[20,22];let b:[u32;2]=a;return 42;}',
               '@extern(C) fn foreign(a:sole [u32;2])->u32;',
               'fn bad()->whisper [u32;2]{return [20,22];}',
               'fn bad(a:shared [u32;2])->u32{return 42;}')
        for i,source in enumerate(cases):
            self.compile('owned_array_boundary_'+str(i), source+'pub fn main_entry()->u32{return 42;}', False)


if __name__ == '__main__':
    unittest.main()
