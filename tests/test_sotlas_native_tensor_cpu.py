"""Caller-backed f32 CPU reference kernels, compiled and executed natively."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous

ROOT = Path(__file__).resolve().parents[1]


class NativeTensorCpuTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, body):
        runtime = (ROOT / 'runtime/native/tensor_cpu.sotlas').read_text(encoding='utf-8')
        runtime = '\n'.join(line for line in runtime.splitlines() if not line.startswith('module '))
        self.execute(self.compile(name, runtime + '\npub fn main_entry()->u32{\n' + body + '}'))

    def test_projection_residual_and_scale(self):
        runtime = (ROOT / 'runtime/native/tensor_cpu.sotlas').read_text(encoding='utf-8')
        example = (ROOT / 'examples/native_numeric_projection/main.sotlas').read_text(encoding='utf-8')
        source = '\n'.join(line for line in (runtime + '\n' + example).splitlines()
                           if not line.startswith(('module ', 'import ')))
        self.execute(self.compile('projection', source))

    def test_dynamic_buffer_beyond_snapshot_limit(self):
        self.program('tensor_large', '''let mut data:[f32;1024]=[1.0;1024];
let p:*mut f32=unsafe{data as *mut f32};
let output:NativeF32MutView=NativeF32MutView{data:p,length:1024};
let input:NativeF32View=NativeF32View{data:unsafe{p as *const f32},length:1024};
if native_f32_scale_cpu(output,2.0)!=0 || native_f32_axpy_cpu(output,input,0.5)!=0{return 1;}
let sum:NativeF32Result=native_f32_dot_cpu(input,input);
if sum.status!=0 || sum.value!=9216.0 || unsafe{*(p+1023)}!=3.0{return 2;}return 42;''')

    def test_metadata_rejection_does_not_dereference_invalid_ranges(self):
        self.program('tensor_invalid', '''let null_view:NativeF32View=NativeF32View{data:null,length:1};
let null_out:NativeF32MutView=NativeF32MutView{data:null,length:1};
if native_f32_scale_cpu(null_out,1.0)!=1 || native_f32_dot_cpu(null_view,null_view).status!=1{return 1;}
if native_f32_range_valid(unsafe{5 as *const f32},1)
|| native_f32_range_valid(unsafe{18446744073709551612 as *const f32},1)
|| native_f32_range_valid(unsafe{4 as *const f32},4611686018427387904){return 2;}return 42;''')

    def test_shapes_and_dimension_overflow_preserve_output(self):
        self.program('tensor_shapes', '''let mut data:[f32;3]=[7.0,8.0,9.0];let p:*mut f32=unsafe{data as *mut f32};
let out:NativeF32MutView=NativeF32MutView{data:p,length:2};
let input:NativeF32View=NativeF32View{data:unsafe{p as *const f32},length:3};
let empty:NativeF32View=NativeF32View{data:null,length:0};
if native_f32_gemv_cpu(out,input,empty,2,3)!=2
|| native_f32_gemv_cpu(out,empty,empty,18446744073709551615,2)!=2
|| native_f32_axpy_cpu(out,input,2.0)!=2 || native_f32_dot_cpu(input,empty).status!=2{return 1;}
if data[0]!=7.0 || data[1]!=8.0 || data[2]!=9.0{return 2;}return 42;''')

    def test_overlap_rejection_and_readonly_input_alias(self):
        self.program('tensor_overlap', '''let mut data:[f32;4]=[1.0,2.0,3.0,4.0];let p:*mut f32=unsafe{data as *mut f32};
let out:NativeF32MutView=NativeF32MutView{data:unsafe{p+1},length:2};
let input:NativeF32View=NativeF32View{data:unsafe{p as *const f32},length:2};
let weights:NativeF32View=NativeF32View{data:unsafe{p as *const f32},length:4};
if native_f32_axpy_cpu(out,input,1.0)!=3 || native_f32_gemv_cpu(out,input,weights,2,2)!=3{return 1;}
if data[0]!=1.0 || data[1]!=2.0 || data[2]!=3.0 || data[3]!=4.0{return 2;}
let mut result:[f32;2]=[0.0,0.0];let separate:NativeF32MutView=NativeF32MutView{data:unsafe{result as *mut f32},length:2};
if native_f32_gemv_cpu(separate,input,weights,2,2)!=0 || result[0]!=5.0 || result[1]!=11.0{return 3;}return 42;''')

    def test_zero_dimensions_and_empty_dot(self):
        self.program('tensor_zero', '''let input:NativeF32View=NativeF32View{data:null,length:0};
let empty:NativeF32MutView=NativeF32MutView{data:null,length:0};
if native_f32_scale_cpu(empty,2.0)!=0 || native_f32_axpy_cpu(empty,input,1.0)!=0
|| native_f32_gemv_cpu(empty,input,input,0,0)!=0{return 1;}
let dot:NativeF32Result=native_f32_dot_cpu(input,input);if dot.status!=0 || dot.value!=0.0{return 2;}
let mut values:[f32;2]=[8.0,9.0];let out:NativeF32MutView=NativeF32MutView{data:unsafe{values as *mut f32},length:2};
if native_f32_gemv_cpu(out,input,input,2,0)!=0 || values[0]!=0.0 || values[1]!=0.0{return 3;}return 42;''')

    def test_f32_order_is_sequential_and_not_reassociated(self):
        self.program('tensor_order', '''let values:[f32;3]=[16777216.0,1.0,-16777216.0];
let ones:[f32;3]=[1.0,1.0,1.0];
let x:NativeF32View=NativeF32View{data:unsafe{values as *const f32},length:3};
let y:NativeF32View=NativeF32View{data:unsafe{ones as *const f32},length:3};
let result:NativeF32Result=native_f32_dot_cpu(x,y);
if result.status!=0 || result.value!=0.0{return 1;}return 42;''')
