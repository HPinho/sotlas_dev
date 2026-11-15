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

    def test_rectangular_matrix_product_and_shared_readonly_inputs(self):
        self.program('tensor_gemm', '''let a:[f32;6]=[1.0,2.0,3.0,4.0,5.0,6.0];
let b:[f32;6]=[1.0,2.0,3.0,4.0,5.0,6.0];let mut c:[f32;4]=0;
let left:NativeF32View=NativeF32View{data:unsafe{a as *const f32},length:6};
let right:NativeF32View=NativeF32View{data:unsafe{b as *const f32},length:6};
let out:NativeF32MutView=NativeF32MutView{data:unsafe{c as *mut f32},length:4};
if native_f32_gemm_cpu(out,left,right,2,3,2)!=0
|| c[0]!=22.0 || c[1]!=28.0 || c[2]!=49.0 || c[3]!=64.0{return 1;}
let square:[f32;4]=[1.0,2.0,3.0,4.0];
let input:NativeF32View=NativeF32View{data:unsafe{square as *const f32},length:4};
if native_f32_gemm_cpu(out,input,input,2,2,2)!=0
|| c[0]!=7.0 || c[1]!=10.0 || c[2]!=15.0 || c[3]!=22.0{return 2;}return 42;''')

    def test_batched_bias_is_applied_after_dot_before_relu(self):
        self.program('tensor_linear', '''let input:[f32;4]=[1.0,2.0,-1.0,0.0];
let weights:[f32;4]=[2.0,-1.0,3.0,4.0];let bias:[f32;2]=[1.0,-8.0];
let mut data:[f32;4]=0;
let x:NativeF32View=NativeF32View{data:unsafe{input as *const f32},length:4};
let w:NativeF32View=NativeF32View{data:unsafe{weights as *const f32},length:4};
let b:NativeF32View=NativeF32View{data:unsafe{bias as *const f32},length:2};
let y:NativeF32MutView=NativeF32MutView{data:unsafe{data as *mut f32},length:4};
if native_f32_linear_cpu(y,x,w,b,2,2,2)!=0
|| data[0]!=9.0 || data[1]!=-1.0 || data[2]!=-1.0 || data[3]!=-7.0{return 1;}
if native_f32_relu_cpu(y)!=0 || data[0]!=9.0 || data[1]!=0.0
|| data[2]!=0.0 || data[3]!=0.0{return 2;}return 42;''')

    def test_transpose_round_trip_rectangular_storage(self):
        self.program('tensor_transpose', '''let a:[f32;6]=[1.0,2.0,3.0,4.0,5.0,6.0];
let mut b:[f32;6]=0;let mut c:[f32;6]=0;
let x:NativeF32View=NativeF32View{data:unsafe{a as *const f32},length:6};
let y:NativeF32MutView=NativeF32MutView{data:unsafe{b as *mut f32},length:6};
if native_f32_transpose_cpu(y,x,2,3)!=0 || b[0]!=1.0 || b[1]!=4.0
|| b[2]!=2.0 || b[3]!=5.0 || b[4]!=3.0 || b[5]!=6.0{return 1;}
let back:NativeF32MutView=NativeF32MutView{data:unsafe{c as *mut f32},length:6};
let read:NativeF32View=NativeF32View{data:unsafe{b as *const f32},length:6};
if native_f32_transpose_cpu(back,read,3,2)!=0{return 2;}
let mut i:usize=0;while i<6{if a[i]!=c[i]{return 3;}i+=1;}return 42;''')

    def test_gemm_overlap_rejection_includes_both_inputs_and_partial_ranges(self):
        self.program('tensor_gemm_alias', '''let mut data:[f32;8]=[1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0];
let p:*mut f32=unsafe{data as *mut f32};
let a:NativeF32View=NativeF32View{data:unsafe{p as *const f32},length:4};
let b:NativeF32View=NativeF32View{data:unsafe{(p+4) as *const f32},length:4};
let exact:NativeF32MutView=NativeF32MutView{data:p,length:4};
let partial:NativeF32MutView=NativeF32MutView{data:unsafe{p+1},length:4};
if native_f32_gemm_cpu(exact,a,b,2,2,2)!=3 || native_f32_gemm_cpu(exact,b,a,2,2,2)!=3
|| native_f32_gemm_cpu(partial,a,b,2,2,2)!=3
|| native_f32_transpose_cpu(exact,a,2,2)!=3 || native_f32_transpose_cpu(partial,a,2,2)!=3{return 1;}
let mut i:usize=0;while i<8{if data[i]!=(i+1) as f32{return 2;}i+=1;}return 42;''')

    def test_bias_failure_preserves_entire_output_before_product(self):
        self.program('tensor_bias_failure', '''let mut data:[f32;4]=[7.0,8.0,9.0,10.0];
let a:[f32;4]=[1.0,2.0,3.0,4.0];let bias:[f32;1]=[1.0];
let p:*mut f32=unsafe{data as *mut f32};
let output:NativeF32MutView=NativeF32MutView{data:p,length:4};
let x:NativeF32View=NativeF32View{data:unsafe{a as *const f32},length:4};
let short:NativeF32View=NativeF32View{data:unsafe{bias as *const f32},length:1};
let invalid:NativeF32View=NativeF32View{data:null,length:2};
let overlap:NativeF32View=NativeF32View{data:unsafe{(p+1) as *const f32},length:2};
if native_f32_linear_cpu(output,x,x,short,2,2,2)!=2
|| native_f32_linear_cpu(output,x,x,invalid,2,2,2)!=1
|| native_f32_linear_cpu(output,x,x,overlap,2,2,2)!=3{return 1;}
if data[0]!=7.0 || data[1]!=8.0 || data[2]!=9.0 || data[3]!=10.0{return 2;}return 42;''')

    def test_gemm_shape_overflow_and_invalid_ranges_do_not_write(self):
        self.program('tensor_gemm_invalid', '''let mut data:[f32;4]=[7.0,8.0,9.0,10.0];
let out:NativeF32MutView=NativeF32MutView{data:unsafe{data as *mut f32},length:4};
let empty:NativeF32View=NativeF32View{data:null,length:0};
let invalid:NativeF32View=NativeF32View{data:null,length:1};
if native_f32_gemm_cpu(out,invalid,empty,2,2,2)!=1
|| native_f32_gemm_cpu(out,empty,empty,2,2,2)!=2
|| native_f32_gemm_cpu(out,empty,empty,18446744073709551615,2,0)!=2
|| native_f32_gemm_cpu(out,empty,empty,0,18446744073709551615,2)!=2
|| native_f32_gemm_cpu(out,empty,empty,18446744073709551615,0,2)!=2
|| native_f32_transpose_cpu(out,empty,18446744073709551615,2)!=2{return 1;}
let bad:NativeF32MutView=NativeF32MutView{data:unsafe{5 as *mut f32},length:1};
if native_f32_relu_cpu(bad)!=1 || native_f32_transpose_cpu(bad,empty,1,1)!=1{return 2;}
if data[0]!=7.0 || data[1]!=8.0 || data[2]!=9.0 || data[3]!=10.0{return 3;}return 42;''')

    def test_zero_shapes_finish_without_visiting_phantom_rows(self):
        self.program('tensor_gemm_zero', '''let empty:NativeF32View=NativeF32View{data:null,length:0};
let none:NativeF32MutView=NativeF32MutView{data:null,length:0};
if native_f32_gemm_cpu(none,empty,empty,18446744073709551615,0,0)!=0
|| native_f32_gemm_cpu(none,empty,empty,0,0,18446744073709551615)!=0
|| native_f32_transpose_cpu(none,empty,18446744073709551615,0)!=0
|| native_f32_relu_cpu(none)!=0{return 1;}
let mut data:[f32;4]=[7.0;4];
let output:NativeF32MutView=NativeF32MutView{data:unsafe{data as *mut f32},length:4};
if native_f32_gemm_cpu(output,empty,empty,2,0,2)!=0 || data[0]!=0.0 || data[3]!=0.0{return 2;}
let bias:[f32;2]=[2.0,-1.0];let b:NativeF32View=NativeF32View{data:unsafe{bias as *const f32},length:2};
if native_f32_linear_cpu(output,empty,empty,b,2,0,2)!=0
|| data[0]!=2.0 || data[1]!=-1.0 || data[2]!=2.0 || data[3]!=-1.0{return 3;}
if native_f32_linear_cpu(none,empty,empty,empty,18446744073709551615,0,0)!=0{return 4;}return 42;''')

    def test_relu_preserves_nan_infinity_and_signed_zero(self):
        self.program('tensor_relu_special', '''let nan:f32=0.0/0.0;let inf:f32=1.0/0.0;
let mut data:[f32;6]=[nan,inf,-inf,-0.0,-2.0,3.0];
let output:NativeF32MutView=NativeF32MutView{data:unsafe{data as *mut f32},length:6};
if native_f32_relu_cpu(output)!=0 || data[0]==data[0] || data[1]!=inf || data[2]!=0.0
|| 1.0/data[3]!=-inf || data[4]!=0.0 || data[5]!=3.0{return 1;}return 42;''')

    def test_gemm_and_linear_preserve_f32_accumulation_then_bias_order(self):
        self.program('tensor_gemm_order', '''let a:[f32;3]=[16777216.0,1.0,-16777216.0];
let b:[f32;3]=[1.0;3];let bias:[f32;1]=[1.0];let mut data:[f32;1]=0;
let left:NativeF32View=NativeF32View{data:unsafe{a as *const f32},length:3};
let right:NativeF32View=NativeF32View{data:unsafe{b as *const f32},length:3};
let offset:NativeF32View=NativeF32View{data:unsafe{bias as *const f32},length:1};
let output:NativeF32MutView=NativeF32MutView{data:unsafe{data as *mut f32},length:1};
if native_f32_gemm_cpu(output,left,right,1,3,1)!=0 || data[0]!=0.0{return 1;}
if native_f32_linear_cpu(output,left,right,offset,1,3,1)!=0 || data[0]!=1.0{return 2;}return 42;''')
