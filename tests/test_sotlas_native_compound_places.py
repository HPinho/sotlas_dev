"""Native numeric read-modify-write places evaluate their address exactly once."""
import signal
import subprocess
import sys
import unittest
import test_sotlas_native_i32 as previous


class NativeCompoundPlaceTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute
    windows_process_exit_code=previous.NativeI32Tests.windows_process_exit_code

    def program(self,name,source):
        self.execute(self.compile(name,source))

    def test_fixed_array_numeric_operators(self):
        self.program('place_array','''pub fn main_entry()->u32{let mut xs:[u32;2]=[10,20];
xs[0]+=4;xs[0]*=3;xs[1]-=2;xs[1]/=3;xs[1]%=4;
if xs[0]!=42||xs[1]!=2{return 1;}return xs[0];}''')

    def test_nested_fields_and_inline_array_fields(self):
        self.program('place_fields','''struct Inner{pub values:[f64;2];pub n:u32;}struct Outer{pub inner:Inner;}
pub fn main_entry()->u32{let mut item:Outer=Outer{inner:Inner{values:[1.5,2.5],n:40}};
item.inner.values[0]+=0.5;item.inner.values[1]*=2.0;item.inner.n+=2;
if item.inner.values[0]!=2.0||item.inner.values[1]!=5.0{return 1;}return item.inner.n;}''')

    def test_pointer_f32_buffer_updates(self):
        self.program('place_pointer','''fn scale(p:*mut f32,n:usize){let mut i:usize=0;unsafe{while i<n{*(p+i)*=2.0;*(p+i)+=1.0;i+=1;}}}
pub fn main_entry()->u32{let mut xs:[f32;3]=[1.0,2.0,3.0];scale(unsafe{xs as *mut f32},3);
if xs[0]!=3.0||xs[1]!=5.0||xs[2]!=7.0{return 1;}return 42;}''')

    def test_index_once_and_old_value_before_rhs_effects(self):
        self.program('place_index_once','''static mut values:[u32;2]=[10,20];static mut calls:u32=0;
fn index()->usize{unsafe{calls+=1;}return 0;}fn rhs()->u32{unsafe{values[0]=100;}return 2;}
pub fn main_entry()->u32{unsafe{values[index()]+=rhs();if calls!=1||values[0]!=12||values[1]!=20{return 1;}}return 42;}''')

    def test_pointer_call_and_rhs_retarget_do_not_repeat_address(self):
        self.program('place_address_once','''static mut data:[u32;2]=[10,100];static mut calls:u32=0;
static mut selected:*mut u32=null;
fn address()->*mut u32{unsafe{calls+=1;return selected;}}
fn rhs()->u32{unsafe{selected=(&mut data[1])as *mut u32;}return 2;}
pub fn main_entry()->u32{unsafe{selected=(&mut data[0])as *mut u32;*address()+=rhs();
if calls!=1||data[0]!=12||data[1]!=100{return 1;}}return 42;}''')

    def test_pointer_returning_record_receiver_once(self):
        self.program('place_receiver_once','''struct Cell{pub value:u32;}struct Wrap{pub cell:Cell;}
static mut data:Wrap=Wrap{cell:Cell{value:40}};static mut calls:u32=0;
fn address()->*mut Cell{unsafe{calls+=1;return (&mut data.cell)as *mut Cell;}}
pub fn main_entry()->u32{unsafe{address().value+=2;if calls!=1||data.cell.value!=42{return 1;}}return 42;}''')

    def test_bitwise_and_shift_updates(self):
        self.program('place_bits','''struct R{pub n:u32;}pub fn main_entry()->u32{let mut r:R=R{n:255};
r.n&=15;r.n|=16;r.n^=5;r.n<<=1;r.n>>=1;if r.n!=26{return 1;}r.n+=16;return r.n;}''')

    def test_scalar_widths_and_narrow_normalization(self):
        for typ,start,delta,check in (('u8','250','10','n==4'),('u16','65530','10','n==4'),
                                     ('i8','-20','2','n==-18'),('i16','-200','2','n==-198'),
                                     ('i32','-40000','2','n==-39998'),('i64','-4294967297','2','n==-4294967295'),
                                     ('u64','4294967297','2','n==4294967299'),('usize','40','2','n==42')):
            with self.subTest(typ=typ):
                self.program('place_width_'+typ,'struct R{pub n:'+typ+';}pub fn main_entry()->u32{let mut r:R=R{n:'+start+'};r.n+='+delta+';let n:'+typ+'=r.n;if '+check+'{return 42;}return 1;}')

    def test_signed_division_and_remainder(self):
        self.program('place_signed_div','''pub fn main_entry()->u32{let mut xs:[i32;2]=[-21,-23];
xs[0]/=2;xs[1]%=5;if xs[0]!=-10||xs[1]!=-3{return 1;}return 42;}''')

    def test_compound_updates_in_deferred_blocks(self):
        self.program('place_defer','''struct R{pub n:u32;}static mut result:u32=0;
fn work(){let mut r:R=R{n:10};defer{unsafe{result=r.n;}}defer{r.n+=2;}defer{r.n*=4;}}
pub fn main_entry()->u32{work();return unsafe{result};}''')

    def test_rhs_propagation_preserves_destination_on_failure(self):
        self.program('place_try','''enum R{Ok(f32),Err(u32)}static mut cleanups:u32=0;
fn value(ok:bool)->R{if ok{return R::Ok(2.0);}return R::Err(42);}
fn update(p:*mut f32,ok:bool)->R{defer{unsafe{cleanups+=1;}}unsafe{*p+=value(ok)?;return R::Ok(*p);}}
pub fn main_entry()->u32{let mut number:f32=2.0;let p:*mut f32=unsafe{(&mut number)as *mut f32};
let bad:R=update(p,false);if number!=2.0{return 1;}let good:R=update(p,true);
if number!=4.0||unsafe{cleanups}!=2{return 2;}if let R::Err(e)=bad{return e;}return 3;}''')

    def test_constant_fields_and_arrays_reject_mutation(self):
        for i,body in enumerate(('DATA.n+=1;','TABLE[0]+=1;')):
            self.compile('place_const_'+str(i),'struct R{pub n:u32;}const DATA:R=R{n:42};const TABLE:[u32;2]=[20,22];pub fn main_entry()->u32{'+body+'return 42;}',False)

    def test_readonly_pointer_stores_are_rejected(self):
        for i,update in enumerate(('*p+=1.0;','*(p+1)*=2.0;','*p=1.0;')):
            self.compile('place_readonly_'+str(i),'fn bad(p:*const f32){unsafe{'+update+'}}pub fn main_entry()->u32{return 42;}',False)

    def test_raw_pointer_update_requires_unsafe(self):
        self.compile('place_safe_pointer','fn bad(p:*mut f32){*p+=1.0;}pub fn main_entry()->u32{return 42;}',False)

    def test_nonnumeric_and_aggregate_updates_reject(self):
        for i,source in enumerate((
            'struct R{pub n:bool;}pub fn main_entry()->u32{let mut r:R=R{n:true};r.n+=false;return 42;}',
            'struct R{pub xs:[u32;2];}pub fn main_entry()->u32{let mut r:R=R{xs:[20,22]};r.xs+=[1,1];return 42;}',
            'struct R{pub n:u32;}pub fn main_entry()->u32{let mut xs:[R;1]=[R{n:42}];xs[0]+=R{n:1};return 42;}',
            'struct R{pub n:f32;}pub fn main_entry()->u32{let mut r:R=R{n:1.0};r.n%=1.0;return 42;}',
            'enum E{A=0,B=1}struct R{pub e:E;}pub fn main_entry()->u32{let mut r:R=R{e:E::A};r.e+=1;return 42;}',
        )):
            with self.subTest(source=source):
                self.compile('place_bad_'+str(i),source,False)

    def test_known_invalid_shifts_and_types_reject(self):
        for i,update in enumerate(('xs[0]<<=32;','xs[0]>>=32;','xs[0]+=false;')):
            self.compile('place_invalid_'+str(i),'pub fn main_entry()->u32{let mut xs:[u32;1]=[42];'+update+'return 42;}',False)

    def test_fixed_array_bounds_trap_before_rhs_division(self):
        obj=self.compile('place_bounds','''fn update(index:usize,divisor:u32)->u32{let mut xs:[u32;2]=[20,22];xs[index]+=1/divisor;return xs[0];}
pub fn main_entry()->u32{return update(2,0);}''')
        image=self.link_image(obj)
        if sys.platform=='win32':
            code,stderr=self.windows_process_exit_code(image)
            self.assertEqual(code,0xC000001D,stderr)
        else:
            result=subprocess.run([str(image)],capture_output=True,timeout=15)
            self.assertEqual(result.returncode,-signal.SIGILL,result.stderr)


if __name__ == '__main__':
    unittest.main()
