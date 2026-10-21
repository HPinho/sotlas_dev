"""Execution gates for native frontend closure and explicit runtime rejection."""
import unittest
import struct
import os
import sys
import signal
import re
import test_sotlas_native_i32 as integer


class NativeFrontendClosureTests(unittest.TestCase):
    setUpClass = classmethod(integer.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(integer.NativeI32Tests.tearDownClass.__func__)
    compile = integer.NativeI32Tests.compile
    link_image = integer.NativeI32Tests.link_image
    execute = integer.NativeI32Tests.execute
    assert_c11_reference = integer.NativeI32Tests.assert_c11_reference
    windows_process_exit_code = integer.NativeI32Tests.windows_process_exit_code

    def test_native_array_fields_copy_local_and_record_arrays_independently(self):
        source='''struct Packet{pub values:[u32;3];pub flags:[bool;2];}
pub fn main_entry()->u32{let mut input:[u32;3]=[10,12,20];let flags:[bool;2]=[true,false];
let mut first:Packet=Packet{values:input,flags:flags};input[0]=99;
let mut second:Packet=Packet{values:first.values,flags:first.flags};first.values[1]=99;
if second.values[0]!=10 || second.values[1]!=12 || !second.flags[0]{return 1;}
second.values=input;if second.values[0]!=99 || input[1]!=12{return 2;}
second.values[0]=10;return second.values[0]+second.values[1]+second.values[2];}'''
        self.execute(self.compile('array_field_value_copies',source))

    def test_native_array_field_value_copies_reject_length_and_element_mismatch(self):
        for index,typ in enumerate(('[u32;2]','[u16;3]','[bool;3]')):
            self.compile('array_field_copy_type_'+str(index),
                'struct Packet{pub values:[u32;3];}pub fn main_entry()->u32{let input:'+typ+'=0;'
                'let value:Packet=Packet{values:input};return 42;}',success=False)

    def test_native_method_results_preserve_types_in_nested_calls(self):
        source='''struct Token{pub value:u32;}impl Token{
fn number(self:&Self)->u32{return self.value;}fn truth(self:&Self)->bool{return self.value==42;}}
fn identity(value:u32)->u32{return value;}
pub fn main_entry()->u32{let value:Token=Token{value:42};if !value.truth(){return 1;}return identity(value.number());}'''
        self.execute(self.compile('method_result_inference',source))
        self.compile('method_result_mismatch',
            'struct Token{pub value:u32;}impl Token{fn number(self:&Self)->u32{return self.value;}}'
            'fn wrong()->bool{let value:Token=Token{value:42};return value.number();}',success=False)

    def test_native_direct_and_whisper_receivers_forward_without_consumption(self):
        source='''struct Token{pub value:u32;}impl Token{
fn read(self:direct Token)->u32{return self.value;}
fn observe(self:whisper Token)->u32{return self.value;}
fn forward(self:direct Token,extra:u32)->u32{return self.observe()+extra;}}
fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let value:sole Token=Token{value:21};
if value.read()!=21 || value.forward(21)!=42{return 1;}return value.observe()+consume(value);}'''
        self.execute(self.compile('borrowed_receivers',source))

    def test_native_borrowed_receivers_reject_foreign_types_mutation_and_overlap(self):
        prefix='struct Token{pub value:u32;}struct Other{pub value:u32;}'
        cases=('impl Token{fn wrong(self:direct Other)->u32{return 42;}}',
               'impl Token{fn wrong(mut self:direct Token)->u32{self.value=42;return 42;}}',
               'impl Token{fn wrong(self:whisper Token)->Token{return self;}}',
               'impl Token{fn read(self:direct Token,extra:u32)->u32{return self.value+extra;}}'
               'fn consume(value:sole Token)->u32{return value.value;}'
               'fn wrong()->u32{let value:sole Token=Token{value:21};return value.read(consume(value));}')
        for index,body in enumerate(cases):
            self.compile('borrowed_receiver_error_'+str(index),prefix+body,success=False)

    def test_native_owned_scalar_projections_cast_without_alias_escape(self):
        source='''struct Token{pub number:u16;pub data:[u16;2];pub decimal:f32;}
fn read(value:direct Token)->u32{return (value.number as u32)+(value.data[1] as u32);}
fn float_read(value:whisper Token)->f64{return value.decimal as f64;}
pub fn main_entry()->u32{let value:sole Token=Token{number:21,data:[21;2],decimal:1.5};
if float_read(value)!=1.5{return 1;}return read(value);}'''
        self.execute(self.compile('owned_projection_casts',source))
        for index,cast in enumerate(('value as *const Token','value.data as *const u16','(&value.number) as *const u16')):
            self.compile('projection_escape_'+str(index),
                'struct Token{pub number:u16;pub data:[u16;2];}'
                'fn wrong(value:direct Token)->*const u16{return unsafe{'+cast+'};}',success=False)

    def test_native_deferred_borrows_read_current_storage_and_release_at_scope_exit(self):
        source='''struct Token{pub value:u32;}static mut total:u32=0;
fn observe(value:direct Token)->void{unsafe{total=total*10+value.value;}}
fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let mut value:sole Token=Token{value:1};
{defer observe(value);defer observe(value);value.value=4;}
if unsafe{total}!=44{return 1;}return consume(value)+38;}'''
        self.execute(self.compile('deferred_borrow_scope',source))

    def test_native_deferred_borrows_reject_consumption_before_cleanup(self):
        prefix='''struct Token{pub value:u32;}fn observe(value:direct Token)->void{return;}
fn consume(value:sole Token)->u32{return value.value;}'''
        for index,body in enumerate(('defer observe(value);return consume(value);',
                                     'defer observe(value);let other:sole Token=value;return 42;',
                                     'defer consume(value);return 42;')):
            self.compile('deferred_borrow_move_'+str(index),prefix+
                'pub fn main_entry()->u32{let value:sole Token=Token{value:42};'+body+'}',success=False)

    def test_native_owned_defer_blocks_execute_checked_read_calls_in_order(self):
        """A native deferred block may read qualified POD owners without moving them."""
        source='''struct Token{pub value:u32;}static mut total:u32=0;
fn observe(value:direct Token)->void{unsafe{total=total*10+value.value;}}
fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let mut value:sole Token=Token{value:1};
{defer{observe(value);observe(value);}value.value=4;}
if unsafe{total}!=44{return 1;}
let moved:sole Token=value;return consume(moved)+38;}'''
        self.execute(self.compile('owned_defer_block_two_calls',source))

    def test_native_owned_defer_blocks_preserve_lifo_and_scope_release(self):
        """Block cleanup remains LIFO with ordinary defers; moves resume after exit."""
        source='''struct Token{pub value:u32;}static mut order:u32=0;
fn observe(value:whisper Token)->void{unsafe{order=order*10+value.value;}}
pub fn main_entry()->u32{let value:sole Token=Token{value:2};
{defer{observe(value);observe(value);}defer observe(value);}
if unsafe{order}!=222{return 1;}
let moved:sole Token=value;return moved.value+40;}'''
        self.execute(self.compile('owned_defer_block_lifo',source))

    def test_native_owned_defer_blocks_reject_consumption_mutation_and_noncall_payloads(self):
        """Unsupported owned captures cannot masquerade as safe deferred blocks."""
        prefix='''struct Token{pub value:u32;}
fn observe(value:direct Token)->void{return;}
fn consume(value:sole Token)->u32{return value.value;}'''
        cases=(
            'defer{observe(value);consume(value);}return 42;',
            'defer{observe(value);value.value=9;}return 42;',
            'defer{observe(value);}let other:sole Token=value;return 42;',
            'defer{observe(value);}return consume(value);',
            'defer{consume(value);}return 42;',
            'defer{if true{observe(value);}}return 42;',
            'defer{observe(value);defer observe(value);}return 42;',
            'defer{let copy:Token=value;}return 42;',
        )
        for index,body in enumerate(cases):
            with self.subTest(index=index):
                self.compile('owned_defer_block_reject_'+str(index),prefix+
                    'pub fn main_entry()->u32{let mut value:sole Token=Token{value:42};'+body+'}',
                    success=False)

    def test_native_deferred_owned_argument_pure_calls_execute_transitively(self):
        """Nested local arithmetic is certified before cleanup-time evaluation."""
        source='''struct Token{pub value:u32;}static mut total:u32=0;
fn increment(v:u32)->u32{return v+1;}
fn twice(v:u32)->u32{return increment(v)+increment(v);}
fn observe(owner:direct Token,extra:u32)->void{
unsafe{total=total*10+owner.value+extra;}}
pub fn main_entry()->u32{let value:sole Token=Token{value:2};
{defer{observe(value,increment(1));observe(value,twice(1));}}
if unsafe{total}!=46{return 1;}
let moved:sole Token=value;return moved.value+40;}'''
        self.execute(self.compile('defer_effect_pure_transitive',source))

    def test_native_deferred_owned_argument_pure_call_in_single_defer(self):
        """Standalone defer uses the same effect verifier as deferred blocks."""
        source='''struct Token{pub value:u32;}static mut total:u32=0;
fn add(v:u32)->u32{return v+2;}
fn observe(owner:whisper Token,extra:u32)->void{unsafe{total=owner.value+extra;}}
pub fn main_entry()->u32{let value:sole Token=Token{value:38};
{defer observe(value,add(2));}
if unsafe{total}!=42{return 1;}return 42;}'''
        self.execute(self.compile('defer_effect_pure_single',source))

    def test_native_deferred_owned_argument_effects_fail_closed(self):
        """Unknown global writes, unsafe argument calls and pointer escapes are not pure."""
        prefix='''struct Token{pub value:u32;}static mut hits:u32=0;
fn observe(owner:direct Token,extra:u32)->void{return;}
fn change()->u32{unsafe{hits=hits+1;}return 1;}
fn forward()->u32{return change();}
fn local_write()->u32{let mut v:u32=0;v=1;return v;}'''
        cases=(
            'defer observe(value,change());',
            'defer{observe(value,forward());}',
            'defer observe(value,local_write());',
            'defer{observe(value,unsafe{change()});}',
        )
        for index,body in enumerate(cases):
            with self.subTest(index=index):
                self.compile('defer_effect_reject_'+str(index),prefix+
                    'pub fn main_entry()->u32{let value:sole Token=Token{value:42};'
                    +body+'return 42;}',success=False)

    def test_sv847_frontend_lexical_local_effects_execute(self):
        """Transitive deferred helpers understand parameters and prior lets."""
        source='''struct Packet{pub value:u32;}static mut result:u32=0;
fn local_extra(v:u32)->u32{let next:u32=v+1;return next+1;}
fn observe(value:direct Packet,extra:u32)->void{unsafe{result=value.value+extra;}}
pub fn main_entry()->u32{let owner:sole Packet=Packet{value:38};
{defer observe(owner,local_extra(2));}
if unsafe{result}!=42{return 1;}return 42;}'''
        self.execute(self.compile('sv847_lexical_effect_helper',source))

    def test_sv847_frontend_method_effects_execute(self):
        """A checked instance method may compute a deferred borrowed argument."""
        source='''struct Packet{pub value:u32;}struct Offset{pub value:u32;}
static mut result:u32=0;
impl Offset{fn plus(self:&Self,number:u32)->u32{return self.value+number;}}
fn observe(value:whisper Packet,extra:u32)->void{unsafe{result=value.value+extra;}}
pub fn main_entry()->u32{let owner:sole Packet=Packet{value:38};
let offset:Offset=Offset{value:2};{defer observe(owner,offset.plus(2));}
if unsafe{result}!=42{return 1;}return 42;}'''
        self.execute(self.compile('sv847_method_effect_helper',source))

    def test_sv847_frontend_unproven_effect_forms_fail_closed(self):
        """Impure, recursive, opaque and unsupported helper forms fail closed."""
        prefix='''struct Packet{pub value:u32;}static mut total:u32=0;
fn observe(owner:direct Packet,extra:u32)->void{return;}
fn side_effect()->u32{unsafe{total=total+1;}return 2;}
fn forwarded()->u32{return side_effect();}
fn recursive()->u32{return recursive();}
fn looped()->u32{while true{return 2;}return 1;}'''
        forms=('defer observe(owner,side_effect());',
               'defer observe(owner,forwarded());',
               'defer observe(owner,recursive());',
               'defer observe(owner,looped());',
               'defer observe(owner,unsafe{side_effect()});')
        for index,body in enumerate(forms):
            with self.subTest(case=index):
                self.compile('sv847_effect_reject_'+str(index),prefix+
                    'pub fn main_entry()->u32{let owner:sole Packet=Packet{value:40};'
                    +body+'return 42;}',success=False)

    def test_sv847_ownership_indexed_borrow_cannot_be_consumed_in_same_call(self):
        """An indexed projection must reserve the underlying owner."""
        prefix='''struct Packet{pub values:[u32;2];}
fn overlap(a:direct u32,b:sole Packet)->u32{return a+b.values[0];}'''
        self.compile('sv847_borrow_index_overlap',prefix+
            'fn wrong()->u32{let owner:sole Packet=Packet{values:[21;2]};'
            'return overlap(owner.values[0],owner);}',success=False)

    def test_sv847_ownership_conditional_guard_borrow_cannot_be_consumed(self):
        """The condition of a direct argument also carries borrowed roots."""
        prefix='''struct Packet{pub value:u32;}
fn overlap(a:direct u32,b:sole Packet)->u32{return a+b.value;}'''
        self.compile('sv847_borrow_guard_overlap',prefix+
            'fn wrong()->u32{let owner:sole Packet=Packet{value:21};'
            'return overlap(if owner.value==21 { 1 } else { 2 },owner);}',success=False)

    def test_sv847_nested_read_result_does_not_retain_spurious_borrow(self):
        """The result of an internal scalar read is independent of its owner."""
        source='''struct Token{pub value:u32;}
impl Token{fn read(value:direct Token)->u32{return value.value;}}
fn number(v:direct u32)->u32{return v+1;}
pub fn main_entry()->u32{let owner:sole Token=Token{value:41};
return number(Token::read(owner));}'''
        self.execute(self.compile('sv847_nested_call_borrow_identity',source))

    def test_sv847_deferred_direct_scalar_cannot_escape_to_global(self):
        """Reject stored direct aliases for the exact location of CI's failure."""
        source='''static mut total:u32=0;
fn read(v:direct u32)->void{unsafe{total=v;}}
pub fn main_entry()->u32{return 42;}'''
        self.compile('sv847_direct_scalar_escape_rejected', source, success=False)
        path = self.directory / 'sv847_direct_scalar_escape_rejected.sotlas'
        output = path.with_suffix('.o')
        result = integer.subprocess.run(
            [str(self.producer), '--compile-obj', str(path), str(output)],
            capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 10, result.stderr)
        self.assertIn(b'err line 3, col 42', result.stderr)
        self.assertFalse(output.exists())

    def test_sv847_ownership_projected_defer_reservation_and_scope_release(self):
        """Projecting an array field retains its owner through lexical cleanup."""
        source='''struct Packet{pub values:[u32;2];}static mut total:u32=0;
fn read(v:direct u32)->void{unsafe{total=total+v;}}
pub fn main_entry()->u32{let values:[u32;2]=[20,21];
let source:Packet=Packet{values:values};
let mut owner:sole Packet=source;
{defer read(owner.values[1]);owner.values[1]=42;}
if unsafe{total}!=42{return 1;}
let moved:sole Packet=owner;return moved.values[1];}'''
        self.execute(self.compile('sv847_projected_defer',source))
        self.compile('sv847_projected_defer_early_move',
            '''struct Packet{pub values:[u32;2];}
fn read(v:direct u32)->void{return;}
fn wrong()->u32{let owner:sole Packet=Packet{values:[21;2]};
{defer read(owner.values[0]);let moved:sole Packet=owner;}
return 42;}''',success=False)

    def test_sv848_deferred_helper_borrowed_input_is_effect_free(self):
        """A readonly direct helper remains valid during deferred cleanup."""
        source='''struct Token{pub value:u32;}static mut total:u32=0;
fn peek(value:direct Token)->u32{return value.value;}
fn observe(value:whisper Token,extra:u32)->void{
unsafe{total=total+value.value+extra;}}
pub fn main_entry()->u32{let owner:sole Token=Token{value:21};
{defer observe(owner,peek(owner));}
if unsafe{total}!=42{return 1;}
let moved:sole Token=owner;return moved.value+21;}'''
        self.execute(self.compile('sv848_direct_helper_capability',source))

    def test_sv848_deferred_helper_sole_input_cannot_be_pure(self):
        """Even a readonly body is not pure when the call consumes sole."""
        source='''struct Token{pub value:u32;}
fn take(value:sole Token)->u32{return value.value;}
fn observe(value:direct Token,extra:u32)->void{return;}
pub fn main_entry()->u32{let owner:sole Token=Token{value:41};
let other:sole Token=Token{value:1};
{defer observe(owner,take(other));}return 42;}'''
        self.compile('sv848_consuming_helper_reject',source,success=False)

    def test_sv848b_target_ir_call_capabilities_preserve_owned_borrowed_and_plain(self):
        """Native lowering carries source call domains without changing execution."""
        source='''struct Token{pub value:u32;}
fn read(value:direct Token)->u32{return value.value;}
fn consume(value:sole Token)->u32{return value.value;}
fn sum(a:u32,b:u32)->u32{return a+b;}
pub fn main_entry()->u32{
let read_owner:sole Token=Token{value:20};
let moved_owner:sole Token=Token{value:22};
let first:u32=read(read_owner);
return sum(first,consume(moved_owner));}'''
        self.execute(self.compile('sv848b_call_capability_domains',source))

    def test_sv848b_target_ir_hidden_record_return_keeps_call_abi(self):
        """SRet hidden pointer stays plain while source parameters retain domains."""
        source='''struct Token{pub value:u32;}
fn build(value:u32)->Token{return Token{value:value};}
fn read(value:direct Token)->u32{return value.value;}
pub fn main_entry()->u32{
let value:Token=build(42);return read(value);}'''
        self.execute(self.compile('sv848b_call_capability_sret',source))

    def test_sv848c_typed_void_observers_preserve_borrow_and_effects(self):
        """Void observer calls keep typed direct, whisper and value ABI."""
        source='''struct Token{pub value:u32;}static mut total:u32=0;
fn observe(value:whisper Token,bonus:u32)->void{
unsafe{total=total+value.value+bonus;}}
fn relay(value:direct Token)->void{observe(value,1);}
pub fn main_entry()->u32{let owner:sole Token=Token{value:20};
relay(owner);observe(owner,1);
if unsafe{total}!=42{return 1;}
let moved:sole Token=owner;return moved.value+22;}'''
        self.execute(self.compile('sv848c_typed_void_borrow',source))

    def test_sv848c_void_observer_cannot_erase_sole_move(self):
        """A void callee's consuming capability still moves sole storage."""
        source='''struct Token{pub value:u32;}
fn take(value:sole Token)->void{return;}
pub fn main_entry()->u32{let owner:sole Token=Token{value:42};
take(owner);return owner.value;}'''
        self.compile('sv848c_void_sole_move',source,success=False)

    def test_sv848d_sole_sret_is_plain_call_destination(self):
        """Sole result survives sret, and its former owner stays moved."""
        source='''struct Token{pub value:u32;}
fn make(value:u32)->sole Token{return Token{value:value};}
fn forward(value:sole Token)->sole Token{return value;}
fn read(value:direct Token)->u32{return value.value;}
pub fn main_entry()->u32{let first:sole Token=make(21);
let second:sole Token=forward(first);return read(second)+21;}'''
        self.execute(self.compile('sv848d_sole_sret', source))
        self.compile('sv848d_sole_sret_moved', source.replace(
            'return read(second)+21;', 'return read(first)+21;'),
            success=False)

    def test_sv848d_elf_boundary_accepts_typed_mixed_calls_with_cfg(self):
        """Emit one program with sret, void borrow, sole move and Phi branches."""
        source='''struct Token{pub value:u32;}static mut total:u32=0;
fn make(value:u32)->Token{return Token{value:value};}
fn observe(value:direct Token,extra:u32)->void{
unsafe{total=total+value.value+extra;}}
fn take(value:sole Token)->u32{return value.value;}
fn add(a:u32,b:u32)->u32{return a+b;}
pub fn main_entry()->u32{
let plain:Token=make(20);observe(plain,2);
let owner:sole Token=Token{value:20};let result:u32=take(owner);
if unsafe{total}!=22{return 1;}
return add(result,22);}'''
        self.execute(self.compile('sv848d_elf_typed_calls_and_cfg',source))

    def test_native_short_circuit_ownership_preserves_statically_skipped_owners(self):
        source='''struct Token{pub value:u32;}static mut calls:u32=0;
fn consume(value:sole Token)->bool{unsafe{calls=calls+1;}return value.value==42;}
fn read(value:direct Token)->u32{return value.value;}
pub fn main_entry()->u32{let first:sole Token=Token{value:42};let second:sole Token=Token{value:42};
let a:bool=false&&consume(first);let b:bool=true||consume(second);
if a || !b || unsafe{calls}!=0{return 1;}return (read(first)+read(second))/2;}'''
        self.execute(self.compile('short_circuit_move_skipped',source))

    def test_native_short_circuit_ownership_rejects_moved_and_maybe_moved_paths(self):
        prefix='struct Token{pub value:u32;}fn consume(value:sole Token)->bool{return true;}'
        for index,condition in enumerate(('flag&&consume(value)','flag||consume(value)',
                                          'true&&consume(value)','false||consume(value)')):
            self.compile('short_circuit_move_error_'+str(index),prefix+
                'fn wrong(flag:bool)->u32{let value:sole Token=Token{value:42};let result:bool='+condition+';return value.value;}',success=False)

    def test_native_owned_array_records_move_return_and_borrow(self):
        source='''struct Packet{pub values:[u32;3];pub flags:[bool;2];}
fn create()->sole Packet{return Packet{values:[14;3],flags:[true;2]};}
fn read(value:direct Packet)->u32{if !value.flags[1]{return 1;}
let mut i:u32=0;let mut sum:u32=0;while i<3{sum=sum+value.values[i];i=i+1;}return sum;}
fn observe(value:whisper Packet)->u32{return value.values[0];}
fn transfer(value:sole Packet)->sole Packet{return value;}
pub fn main_entry()->u32{let first:sole Packet=create();
if read(first)!=42 || observe(first)!=14{return 1;}
let second:sole Packet=transfer(first);return read(second);}'''
        self.execute(self.compile('owned_array_record_transfer',source))

    def test_native_owned_nested_array_records_keep_value_storage_independent(self):
        source='''struct Inner{pub data:[u32;3];}struct Packet{pub inner:Inner;pub ratio:[f64;2];}
fn read(value:direct Packet)->u32{return value.inner.data[2];}
fn consume(value:sole Packet)->u32{return read(value);}
pub fn main_entry()->u32{let original:Packet=Packet{inner:Inner{data:[21;3]},ratio:[1.5;2]};
let mut owner:sole Packet=original;owner.inner.data[2]=42;owner.ratio[1]=2.5;
if original.inner.data[2]!=21 || original.ratio[1]!=1.5 || owner.ratio[1]!=2.5{return 1;}
return consume(owner);}'''
        self.execute(self.compile('owned_nested_array_record',source))

    def test_native_owned_array_records_reject_moved_and_maybe_moved_reads(self):
        prefix='''struct Packet{pub values:[u32;3];}fn consume(value:sole Packet)->u32{return value.values[0];}
fn read(value:direct Packet)->u32{return value.values[0];}'''
        cases=('let other:sole Packet=value;return value.values[0];',
               'if flag{consume(value);}return read(value);',
               'consume(value);value.values[1]=42;return 42;',
               'let plain:Packet=value;return plain.values[0];')
        for index,body in enumerate(cases):
            self.compile('owned_array_moved_'+str(index),prefix+
                'fn wrong(flag:bool)->u32{let mut value:sole Packet=Packet{values:[14;3]};'+body+'}',success=False)

    def test_native_borrowed_array_records_reject_mutation_and_escape(self):
        for domain in ('direct','whisper'):
            for index,body in enumerate((
                'value.values[0]=42;return 42;',
                'let copy:Packet=value;return 42;',
                'let ptr:*const u32=unsafe{value.values as *const u32};return 42;',
                'defer{let copy:Packet=value;}return 42;',
            )):
                source='struct Packet{pub values:[u32;3];}fn read(value:'+domain+' Packet)->u32{'+body+'}'
                self.compile('borrow_array_escape_'+domain+str(index),source,success=False)

    def test_native_owned_array_record_field_limits_fail_closed(self):
        for index,typ in enumerate(('[u32;0]','[u32;257]','[*mut u32;3]',
                                   '[[u32;2];3]','[sole u32;3]','[Raw;3]')):
            self.compile('owned_array_field_limit_'+str(index),
                'struct Inner{pub value:u32;}struct Raw{pub pointer:*mut u32;}'
                'struct Packet{pub values:'+typ+';}'
                'fn read(value:direct Packet)->u32{return 42;}',success=False)

    def test_native_owned_array_record_boundary_and_scalar_layouts_execute(self):
        source='''struct Packet{pub bytes:[u8;256];pub numbers:[i16;2];pub ratios:[f32;2];}
fn read(value:direct Packet)->u32{let expected:f32=1.5;
if value.bytes[255]!=42 || value.numbers[1]!=-7 || value.ratios[0]!=expected{return 1;}return 42;}
pub fn main_entry()->u32{let value:sole Packet=Packet{bytes:[42;256],numbers:[-7;2],ratios:[1.5;2]};return read(value);}'''
        self.execute(self.compile('owned_array_field_boundary',source))

    def test_native_record_array_lists_evaluate_in_order_once_and_copy(self):
        source='''struct Packet{pub values:[u32;3];pub flags:[bool;2];pub floats:[f64;2];}
static mut calls:u32=0;fn next()->u32{unsafe{calls=calls+1;}return unsafe{calls};}
fn read(value:direct Packet)->u32{if value.values[0]!=1 || value.values[1]!=2 || value.values[2]!=3
|| !value.flags[0] || value.flags[1] || value.floats[0]+value.floats[1]!=4.0{return 1;}return 42;}
pub fn main_entry()->u32{let plain:Packet=Packet{values:[next(),next(),next()],flags:[true,false],floats:[1.5,2.5]};
let owner:sole Packet=plain;if unsafe{calls}!=3{return 2;}return read(owner);}'''
        obj=self.compile('record_array_field_lists',source)
        self.execute(obj)

    def test_native_record_array_fields_reject_shape_and_scalar_type_errors(self):
        for index,initializer in enumerate(('[1,2]','[1,2,3,4]','[1,true,3]',
                                            '[1,256,3]','[true;3]','[1;2]','[256;3]')):
            self.compile('record_array_field_type_'+str(index),
                'struct Packet{pub values:[u8;3];}pub fn main_entry()->u32{'
                'let value:sole Packet=Packet{values:'+initializer+'};return 42;}',success=False)

    def test_native_array_element_arithmetic_infers_elements_for_returns_and_calls(self):
        source='''struct Packet{pub values:[u32;3];}fn add(value:u32)->u32{return value;}
fn read(value:direct Packet)->u32{return add(value.values[0]+value.values[1]+value.values[2]);}
pub fn main_entry()->u32{let value:sole Packet=Packet{values:[10,12,20]};return read(value);}'''
        self.execute(self.compile('array_field_element_inference',source))
        self.compile('array_field_element_mismatch',
            'struct Packet{pub values:[u32;3];}fn read(value:direct Packet)->bool{'
            'return value.values[0]+value.values[1];}',success=False)

    def test_native_direct_forwarding_and_read_aliases_preserve_the_owner(self):
        source='''struct Token{pub value:u32;}fn read(value:direct Token)->u32{return value.value;}
fn whisper_read(value:whisper Token)->u32{return value.value;}
fn forward(value:direct Token)->u32{return whisper_read(value);}
fn pair(left:direct Token,right:direct Token)->u32{return left.value+right.value;}
fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let value:sole Token=Token{value:21};
if read(value)!=21 || forward(value)!=21 || pair(value,value)!=42{return 1;}
return read(value)+consume(value);}'''
        self.execute(self.compile('native_direct_read_forward',source))

    def test_native_direct_scalar_and_static_calls_execute_with_typed_results(self):
        source='''struct Token{pub value:u32;}impl Token{fn read(value:direct Token)->u32{return value.value;}}
fn number(value:direct u32)->u32{return value+1;}
fn boolean(value:direct bool)->bool{return value==true;}
fn decimal(value:direct f32)->f32{return value*2.0;}
pub fn main_entry()->u32{let value:sole Token=Token{value:41};let expected:f32=3.0;
if !boolean(true) || decimal(1.5)!=expected{return 1;}return number(Token::read(value));}'''
        self.execute(self.compile('native_direct_types_static',source))

    def test_native_direct_loops_branches_and_void_forwarding_do_not_consume(self):
        source='''struct Token{pub value:u32;}static mut total:u32=0;
fn observe(value:direct Token)->void{unsafe{total=total+value.value;}}
fn forward(value:direct Token)->void{observe(value);}
fn repeat(value:direct Token)->u32{let mut count:u32=0;while count<2{
if count==0{forward(value);}else{observe(value);}count=count+1;}return value.value;}
fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let value:sole Token=Token{value:21};
if repeat(value)!=21 || unsafe{total}!=42{return 1;}return consume(value)+21;}'''
        self.execute(self.compile('native_direct_structured',source))

    def test_native_direct_rejects_mutation_storage_returns_ffi_and_overlap(self):
        prefix='struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}'
        cases=('fn wrong(mut value:direct Token)->u32{value.value=1;return 42;}',
               'fn wrong(value:direct Token)->u32{let copy:Token=value;return 42;}',
               'fn wrong(value:direct Token)->Token{return value;}',
               'fn wrong(value:direct Token)->u32{return consume(value);}',
               'fn wrong(value:direct Token)->*const Token{return unsafe{value as *const Token};}',
               'fn wrong(value:direct Token)->u32{defer consume(value);return 42;}',
               'fn wrong()->direct Token{return Token{value:42};}',
               'fn wrong()->u32{let value:direct Token=Token{value:42};return 42;}',
               'struct Stored{pub value:direct Token;}',
               'static mut stored:direct u32=0;',
               '@extern(C) fn foreign(value:Token)->u32;fn wrong(value:direct Token)->u32{return unsafe{foreign(value)};}',
               '@extern(C) fn wrong(value:direct Token)->u32;')
        for index,source in enumerate(cases):
            with self.subTest(index=index):self.compile('native_direct_bad_'+str(index),prefix+source+'pub fn main_entry()->u32{return 42;}',success=False)
        self.compile('native_direct_overlap',prefix+'fn pair(value:direct Token,bias:u32)->u32{return value.value+bias;}pub fn main_entry()->u32{let value:sole Token=Token{value:42};return pair(value,consume(value));}',success=False)

    def test_native_direct_ir_preserves_domain_and_borrows_original_record_storage(self):
        class Capture:
            def compile(self,name,source):self.source=source;return None
            def execute(self,obj):pass
        capture=Capture()
        NativeFrontendClosureTests.test_native_lowering_preserves_parameter_binding_and_return_domains(capture)
        source=capture.source.replace('whisper Token','direct Token').replace('domain==4','domain==6').replace('!=1024','!=1536')
        source=re.sub(r'let input:\*const u8="([^"]+)";let length:usize=\d+;',
                      lambda match:'let input:*const u8="'+match.group(1)+'";let length:usize='+str(len(match.group(1).encode('utf-8')))+';',source)
        probe='''index=0;let mut found:bool=false;
while index<ir.instruction_count as usize{let instruction:TargetInstruction=unsafe{*(instructions as *const TargetInstruction+index)};
if instruction.opcode==TargetOpcode::Call && sema.source_slice_equals(text,unsafe{g_extended_len},instruction.symbol.offset,instruction.symbol.length,"read",4){
let input:TargetOperand=unsafe{*(operands as *const TargetOperand+instruction.first_operand as usize)};
if unsafe{(*(vals+input.value_id as usize-1)).flags}!=256{return 8;}found=true;}index=index+1;}
if !found{return 9;}return 42;}'''
        source=source[:-len('return 42;}')]+probe
        self.execute(self.compile('native_direct_ir_storage',source))

    def test_native_match_proves_boolean_and_enum_coverage_without_wildcards(self):
        source='''enum Code{First=1,Last=9}const DONE:Code=Code::Last;
fn boolean(value:bool)->u32{match value{false=>return 1;true=>return 42;}}
fn code(value:Code)->u32{match value{DONE=>return 42;Code::First=>return 1;}}
pub fn main_entry()->u32{if boolean(true)!=42 || code(Code::Last)!=42{return 2;}return 42;}'''
        self.execute(self.compile('native_match_exhaustive',source))

    def test_native_match_finite_coverage_preserves_cleanup_and_ownership(self):
        source='''enum Code{First=1,Last=9}struct Token{pub value:u32;}static mut trace:u32=0;
fn append(value:u32)->void{unsafe{trace=trace*10+value;}}
fn consume(value:sole Token)->u32{return value.value;}
fn select(code:Code,value:sole Token)->u32{defer append(9);match code{
Code::First=>{defer append(4);return consume(value);},Code::Last=>{}}return consume(value);}
pub fn main_entry()->u32{let value:u32=select(Code::First,Token{value:42});if unsafe{trace}!=49{return 1;}return value;}'''
        self.execute(self.compile('native_match_exhaustive_cleanup',source))
        self.compile('native_match_exhaustive_maybe_moved',source.replace('return consume(value);},Code::Last','consume(value);},Code::Last'),success=False)

    def test_native_match_missing_cases_and_nominal_constant_mismatches_fail(self):
        cases=('enum Code{First=1,Last=9}fn select(value:Code)->u32{match value{Code::First=>return 42;}}',
               'fn select(value:bool)->u32{match value{true=>return 42;}}',
               'enum Code{First=1}enum Other{First=1}const WRONG:Other=Other::First;fn select(value:Code)->u32{match value{WRONG=>return 42;}}',
               'enum Code{First=1}const RAW:u32=1;fn select(value:Code)->u32{match value{RAW=>return 42;}}',
               'enum Code{First=1}const SAME:Code=Code::First;fn select(value:Code)->u32{match value{SAME=>return 42;Code::First=>return 42;}}',
               'enum Code{First=1}const VALUE:Code=Code::First;fn select(value:u32)->u32{match value{VALUE=>return 42;_=>return 1;}}')
        for index,source in enumerate(cases):
            with self.subTest(index=index):self.compile('native_match_missing_'+str(index),source+'pub fn main_entry()->u32{return 42;}',success=False)

    def test_native_match_complete_enum_capacity_executes_the_last_case(self):
        variants=','.join(f'V{i}={i*2+1}' for i in range(64))
        arms=' '.join(f'Code::V{i}=>return 42;' for i in range(64))
        prefix='enum Code{'+variants+'}fn select(value:Code)->u32{match value{'
        suffix='}}pub fn main_entry()->u32{return select(Code::V63);}'
        self.execute(self.compile('native_match_all_variants',prefix+arms+suffix))
        self.compile('native_match_one_variant_missing',prefix+arms.replace('Code::V63=>return 42;','')+suffix,success=False)

    def test_native_match_invalid_enum_representation_traps_before_an_arm(self):
        source='''enum Code{First=1,Last=9}fn select(value:Code)->u32{
match value{Code::First=>return 42;Code::Last=>return 7;}}
pub fn main_entry()->u32{return select(unsafe{99 as Code});}'''
        obj=self.compile('native_match_invalid_representation',source)
        if getattr(self,'native_execution_platform',sys.platform)=='win32':
            code,stderr=self.windows_process_exit_code(self.link_image(obj))
            self.assertEqual(code,0xc000001d,stderr)
        else:
            self.execute(obj,expected=-signal.SIGILL)

    def test_record_array_nonpower_and_large_strides_execute_checked_indexing(self):
        source='''struct Triple{pub a:u32;pub b:u32;pub c:u32;}struct Packet{pub bytes:[u8;32];}
pub fn main_entry()->u32{let mut rows:[Triple;64]=[Triple{a:0,b:20,c:22};64];
let mut packets:[Packet;32]=[Packet{bytes:[0;32]};32];
rows[63].a=9;packets[31].bytes[31]=42;
if packets[0].bytes[31]!=0 || packets[31].bytes[31]!=42{return 1;}
match rows[63].a{9=>return rows[63].b+rows[63].c;_=>return 2;}}'''
        self.execute(self.compile('native_record_strides',source))

    def test_native_match_selects_once_and_executes_only_one_arm(self):
        source='''static mut calls:u32=0;static mut trace:u32=0;
fn input()->u32{unsafe{calls=calls+1;}return 7;}
fn select()->u32{match input(){0=>{unsafe{trace=1;}return 1;},7=>{unsafe{trace=42;}return 42;},_=>{return 2;}}}
pub fn main_entry()->u32{let value:u32=select();if unsafe{calls}!=1 || unsafe{trace}!=42{return 3;}return value;}'''
        self.execute(self.compile('native_match_once',source))

    def test_native_match_signed_boolean_and_enum_selectors(self):
        source='''enum Color{Red=1,Blue=9}fn color(value:Color)->u32{
match value{Color::Red=>{return 1;},Color::Blue=>{return 42;},_=>{return 2;}}}
fn signed(value:i8)->u32{match value{-128=>{return 42;},0=>{return 1;},_=>{return 2;}}}
fn boolean(value:bool)->u32{match value{false=>{return 1;},true=>{return 42;},_=>{return 2;}}}
pub fn main_entry()->u32{if signed(-128)!=42 || boolean(true)!=42 || color(Color::Blue)!=42{return 1;}return 42;}'''
        self.execute(self.compile('native_match_types',source))

    def test_native_match_nested_scopes_loops_and_lexical_cleanup(self):
        source='''static mut trace:u32=0;fn append(value:u32)->void{unsafe{trace=trace*10+value;}}
pub fn main_entry()->u32{let mut index:u32=0;let mut total:u32=0;
while index<3{index=index+1;defer append(index);match index{
1=>{defer append(4);continue;},2=>{defer append(5);match true{true=>{total=42;},_=>{total=1;}}},_=>{break;}}}
if unsafe{trace}!=41523{return 1;}return total;}'''
        self.execute(self.compile('native_match_loop_cleanup',source))

    def test_native_match_record_returns_snapshot_before_cleanup(self):
        source='''struct Token{pub value:u32;}fn create(value:u32)->Token{
let mut token:Token=Token{value:42};defer token.value=1;
match value{0=>{return token;},_=>{return Token{value:9};}}}
pub fn main_entry()->u32{let token:Token=create(0);return token.value;}'''
        self.execute(self.compile('native_match_record_return',source))

    def test_native_match_merges_exclusive_states_and_excludes_returned_paths(self):
        prefix='''struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}'''
        source=prefix+'''fn select(flag:u32,value:sole Token)->u32{match flag{
0=>{return consume(value);},_=>{}}return consume(value);}
pub fn main_entry()->u32{return select(1,Token{value:42});}'''
        self.execute(self.compile('native_match_live_owner',source))
        self.compile('native_match_maybe_moved',prefix+'''pub fn main_entry()->u32{
let value:sole Token=Token{value:42};match 0 as u32{0=>{consume(value);},_=>{}}return consume(value);}''',success=False)

    def test_native_match_rejects_coverage_patterns_and_selector_types(self):
        cases=('match 0 as u32{0=>{return 42;}}',
               'match 0 as u32{0=>{},0=>{},_=>{}}',
               'match 0 as u32{_=>{},0=>{}}',
               'match 0 as u32{1 as u32=>{},_=>{}}',
               'match true{1=>{},_=>{}}',
               'match 0 as u8{256=>{},_=>{}}',
               'match 1.5{1.5=>{}}','match 0 as u32{unknown=>{},_=>{}}',
               'match 0 as u32{}','match 0 as u32{0=>42,_=>{}}',
               'match 0 as u32{0=>{},_=>{},_=>{}}')
        for index,body in enumerate(cases):
            with self.subTest(index=index):self.compile('native_match_bad_'+str(index),'pub fn main_entry()->u32{'+body+'return 42;}',success=False)
        self.compile('native_match_wrong_enum','enum Color{Red=1}enum Other{Red=1}pub fn main_entry()->u32{let value:Color=Color::Red;match value{Other::Red=>{},_=>{}}return 42;}',success=False)

    def test_native_match_arm_capacity_is_bounded(self):
        arms=','.join(f'{i}=>{{}}' for i in range(63))
        self.execute(self.compile('native_match_capacity','pub fn main_entry()->u32{match 0 as u32{'+arms+',_=>{}}return 42;}'))
        self.compile('native_match_capacity_overflow','pub fn main_entry()->u32{match 0 as u32{'+arms+',63=>{},_=>{}}return 42;}',success=False)

    def test_native_match_integer_widths_and_constant_patterns(self):
        cases=(('u8','255'),('i8','-128'),('u16','65535'),('i16','-32768'),
               ('u32','4294967295'),('i32','-2147483648'),
               ('u64','18446744073709551615'),('i64','-9223372036854775808'))
        for typ,value in cases:
            with self.subTest(typ=typ):
                source=f'const EXPECTED:{typ}={value};fn select(value:{typ})->u32{{match value{{EXPECTED=>{{return 42;}},_=>{{return 1;}}}}}}pub fn main_entry()->u32{{return select(EXPECTED);}}'
                self.execute(self.compile('native_match_width_'+typ,source))
        self.execute(self.compile('native_match_negative_literal','pub fn main_entry()->u32{match -1{-1=>{return 42;},_=>{return 1;}}}'))
        self.execute(self.compile('native_match_enum_literal','enum Color{Red=1}pub fn main_entry()->u32{match Color::Red{Color::Red=>{return 42;},_=>{return 1;}}}'))

    def test_native_match_scopes_mutated_subject_and_rejected_forms(self):
        source='''static mut trace:u32=0;pub fn main_entry()->u32{let mut value:u32=0;
match value{0=>{let scoped:u32=42;value=7;unsafe{trace=scoped;}},7=>{unsafe{trace=1;}},_=>{}}
return unsafe{trace};}'''
        self.execute(self.compile('native_match_mutated_subject',source))
        self.compile('native_match_scope_escape',source.replace('return unsafe{trace};','return scoped;'),success=False)
        self.compile('native_match_pattern_call','fn pattern()->u32{return 0;}pub fn main_entry()->u32{match 0{pattern()=>{},_=>{}}return 42;}',success=False)
        self.compile('native_match_owned_subject','pub fn main_entry()->u32{let value:sole u32=42;match value{42=>{return 42;},_=>{return 1;}}}',success=False)
        self.compile('native_match_payload_binding','enum Color{Red=1}pub fn main_entry()->u32{let value:Color=Color::Red;match value{Color::Red(payload)=>{},_=>{}}return 42;}',success=False)

    def test_native_match_legacy_statement_arm_syntax(self):
        source='''fn select(value:u32)->u32{match value{
0=>return 42; 1=>{return 1;} _=>return 2;}}
pub fn main_entry()->u32{return select(0);}'''
        self.execute(self.compile('native_match_statement_arms',source))

    def test_local_record_array_lists_copy_and_mutate_nested_payloads(self):
        source='''struct Inner{pub value:u32;}struct Packet{pub inner:Inner;pub flags:[bool;2];}
fn read(packet:Packet)->u32{return packet.inner.value;}
pub fn main_entry()->u32{let original:Packet=Packet{inner:Inner{value:21},flags:[false;2]};
let mut packets:[Packet;2]=[original,Packet{inner:Inner{value:9},flags:[false;2]}];
packets[0].inner.value=42;packets[0].flags[1]=true;packets[1].flags[0]=true;
let mut copy:Packet=packets[0];copy.inner.value=7;
if original.inner.value!=21 || packets[0].inner.value!=42 || copy.inner.value!=7{return 1;}
if !packets[0].flags[1] || !packets[1].flags[0]{return 2;}
packets[1]=packets[0];packets[0].inner.value=3;return read(packets[1]);}'''
        self.execute(self.compile('record_array_lists',source))

    def test_local_record_array_repetition_evaluates_once_and_copies_each_slot(self):
        source='''struct Token{pub value:u32;}static mut calls:u32=0;
fn create()->Token{unsafe{calls=calls+1;}return Token{value:42};}
pub fn main_entry()->u32{let mut items:[Token;64]=[create();64];items[0].value=7;
let mut index:u64=1;while index<64{if items[index].value!=42{return 1;}index=index+1;}
if unsafe{calls}!=1{return 2;}return items[63].value;}'''
        self.execute(self.compile('record_array_repeat',source))

    def test_local_record_arrays_cross_return_conditional_and_defer_paths(self):
        source='''struct Token{pub value:u32;}static mut trace:u32=0;
fn choose(flag:bool)->Token{let mut items:[Token;2]=[Token{value:42};2];
defer {items[0].value=7;unsafe{trace=items[1].value;}}
return if flag{items[0]}else{items[1]};}
pub fn main_entry()->u32{let value:Token=choose(true);if unsafe{trace}!=42{return 1;}return value.value;}'''
        self.execute(self.compile('record_array_return_cleanup',source))

    def test_local_record_array_element_returns_preserve_value_storage(self):
        source='''struct Token{pub value:i32;}fn create()->Token{
let items:[Token;2]=[Token{value:-21},Token{value:42}];return items[1];}
fn read(value:Token)->i32{return value.value;}
pub fn main_entry()->u32{let mut items:[Token;2]=[create();2];
let copy=items[0];items[0].value=7;
if copy.value!=42 || read(items[1])!=42{return 1;}return copy.value as u32;}'''
        self.execute(self.compile('record_array_element_return',source))

    def test_native_object_call_patch_table_accepts_compiler_sized_workloads(self):
        prefix='fn noop()->void{}pub fn main_entry()->u32{'
        self.execute(self.compile('native_many_call_patches',prefix+'noop();'*4100+'return 42;}'))
        self.execute(self.compile('native_call_patch_capacity_exact',prefix+'noop();'*8192+'return 42;}'))
        self.compile('native_call_patch_capacity',prefix+'noop();'*8193+'return 42;}',success=False)

    def test_local_record_arrays_reject_layout_type_and_escape_errors(self):
        prefix='struct Token{pub value:u32;}struct Other{pub value:u32;}'
        cases=('let items:[Token;2]=[Token{value:1}];',
               'let items:[Token;2]=[Token{value:1},Other{value:2}];',
               'let items:[Token;2]=[Other{value:1};2];',
               'let items:[Token;2]=0;',
               'let mut items:[Token;2]=[Token{value:1};2];items[0]=Other{value:2};',
               'let items:[Token;2]=[Token{value:1};2];let bad:Other=items[0];',
               'let items:[Token;2]=[Token{value:1};2];let bad:u32=items[0];',
               'let items:[Token;2]=[Token{value:1};2];let bad:*mut Token=items[0];',
               'let items:[Token;2]=[Token{value:1};2];let bad:Token=items[2];')
        for index,body in enumerate(cases):
            with self.subTest(index=index):self.compile('record_array_bad_'+str(index),prefix+'pub fn main_entry()->u32{'+body+'return 42;}',success=False)
        self.compile('record_array_pointer_payload','struct Ptr{pub value:*mut u8;}pub fn main_entry()->u32{let items:[Ptr;2]=[Ptr{value:null};2];return 42;}',success=False)
        self.compile('record_array_immutable_mutation',prefix+'pub fn main_entry()->u32{let items:[Token;2]=[Token{value:42};2];items[0].value=1;return 42;}',success=False)
        self.compile('record_array_foreign_escape',prefix+'@extern(C) fn escape(value:*mut Token)->u32;pub fn main_entry()->u32{let items:[Token;2]=[Token{value:42};2];return unsafe{escape(items[0])};}',success=False)
        self.compile('record_array_owned_erasure',prefix+'pub fn main_entry()->u32{let value:sole Token=Token{value:42};let items:[Token;2]=[value;2];return 42;}',success=False)
        self.compile('record_array_frame_capacity','struct Large{pub bytes:[u8;32];}pub fn main_entry()->u32{let items:[Large;4096]=[Large{bytes:[0;32]};4096];return 42;}',success=False)

    def test_static_lists_fold_forward_constants_and_preserve_mutable_storage(self):
        source='''static mut TABLE:[u32;4]=[0,BASE,BASE+2,if READY{42}else{1/0}];
static mut FLAGS:[bool;3]=[false,READY,!READY];static mut ZERO:[u32;3]=[0,0,0];
static mut REPEATED:[u16;2]=[7;2];static mut COUNT:u32=3;
const READY:bool=true;const BASE:u32=20;
pub fn main_entry()->u32{if unsafe{TABLE[0]}!=0 || unsafe{TABLE[1]}!=20 || unsafe{TABLE[2]}!=22{return 1;}
if unsafe{FLAGS[0]} || !unsafe{FLAGS[1]} || unsafe{FLAGS[2]} || unsafe{ZERO[2]}!=0{return 2;}
unsafe{TABLE[0]=TABLE[1]+TABLE[2];ZERO[1]=9;FLAGS[2]=true;COUNT=COUNT+1;}
if unsafe{REPEATED[1]}!=7 || unsafe{ZERO[1]}!=9 || !unsafe{FLAGS[2]} || unsafe{COUNT}!=4{return 3;}
return unsafe{TABLE[0]};}'''
        self.execute(self.compile('static_list_constant_storage',source))

    def test_static_lists_preserve_scalar_widths_signedness_and_float_bits(self):
        cases=(('u8','0,21,255','255'),('i8','0,-21,-128','-128'),
               ('u16','0,21,65535','65535'),('i16','0,-21,-32768','-32768'),
               ('u32','0,21,4294967295','4294967295'),('i32','0,-21,-2147483648','-2147483648'),
               ('u64','0,21,18446744073709551615','18446744073709551615'),
               ('i64','0,-21,-9223372036854775808','-9223372036854775808'),
               ('f32','0.0,1.25,-2.5','-2.5'),('f64','0.0,1.25,-2.5','-2.5'))
        for typ,values,last in cases:
            with self.subTest(typ=typ):
                source=f'''static mut DATA:[{typ};3]=[{values}];
pub fn main_entry()->u32{{let last:{typ}=unsafe{{DATA[2]}};let expected:{typ}={last};if last!=expected{{return 1;}}
unsafe{{DATA[0]=last;}}if unsafe{{DATA[0]}}!=last{{return 2;}}return 42;}}'''
                obj=self.compile('static_list_'+typ,source)
                self.execute(obj)
                self.assert_c11_reference(obj)

    def test_static_list_object_bytes_and_zero_section_are_distinct(self):
        source='''static mut DATA:[u16;4]=[0,4660,65535,42];static mut ZERO:[u16;3]=[0,0,0];
pub fn main_entry()->u32{if unsafe{ZERO[1]}!=0{return 1;}return unsafe{DATA[3]} as u32;}'''
        obj=self.compile('static_list_sections',source)
        self.execute(obj)
        raw=obj.read_bytes()
        shoff=struct.unpack_from('<Q',raw,40)[0]
        entry_size,count,names_index=struct.unpack_from('<HHH',raw,58)
        headers=[struct.unpack_from('<IIQQQQIIQQ',raw,shoff+i*entry_size) for i in range(count)]
        names=raw[headers[names_index][4]:headers[names_index][4]+headers[names_index][5]]
        sections={names[h[0]:names.index(b'\0',h[0])].decode():h for h in headers}
        data=sections['.data'];zero=sections['.bss']
        self.assertEqual(raw[data[4]:data[4]+data[5]],struct.pack('<4H',0,4660,65535,42))
        self.assertEqual(zero[1],8)  # SHT_NOBITS stores no initialized bytes.
        self.assertEqual(zero[5],6)

    def test_static_lists_reject_shape_type_runtime_and_pointer_initializers(self):
        cases=('static mut DATA:[u8;3]=[1,2];','static mut DATA:[u8;2]=[1,2,3];',
               'static mut DATA:[u8;2]=[1,256];','static mut DATA:[u32;2]=[1,true];',
               'static mut DATA:[bool;2]=[false,2];','static mut DATA:[f32;2]=[1.0,true];',
               'static mut DATA:[u32;2]=[1,UNKNOWN];','static mut DATA:[u32;2]=[1,1/0];',
               'fn value()->u32{return 2;}static mut DATA:[u32;2]=[1,value()];',
               'static mut DATA:[*mut u8;2]=[null,null];',
               'struct Token{pub value:*mut u32;}static mut DATA:[Token;1]=[Token{value:null}];')
        for index,source in enumerate(cases):
            with self.subTest(index=index):
                self.compile('bad_static_list_'+str(index),source+'pub fn main_entry()->u32{return 42;}',success=False)

    def test_static_list_capacity_is_shared_across_declarations(self):
        values=','.join('0' for _ in range(2048))
        prefix=f'static mut FIRST:[u8;2048]=[{values}];static mut SECOND:[u8;2048]=[{values}];'
        self.execute(self.compile('static_list_capacity_exact',prefix+'pub fn main_entry()->u32{return 42;}'))
        self.compile('static_list_capacity_overflow',prefix+'static mut THIRD:[u8;1]=[1];pub fn main_entry()->u32{return 42;}',success=False)

    def test_standalone_blocks_preserve_scope_without_defer(self):
        source='''pub fn main_entry()->u32{let mut value:u32=0;
{let scoped:u32=42;value=scoped;}return value;}'''
        self.execute(self.compile('native_standalone_block',source))
        self.compile('native_standalone_scope_escape',source.replace('return value;','return scoped;'),success=False)

    def test_native_defer_calls_run_lifo_on_scope_and_early_return(self):
        source='''static mut trace:u32=0;fn append(value:u32)->void{unsafe{trace=trace*10+value;}}
fn perform(flag:bool)->void{let mut value:u32=1;defer append(value);value=2;
{defer append(3);}if flag{defer append(4);return;}defer append(5);}
pub fn main_entry()->u32{perform(true);if unsafe{trace}!=342{return 1;}unsafe{trace=0;}
perform(false);if unsafe{trace}!=352{return 2;}return 42;}'''
        self.execute(self.compile('native_defer_lifo',source))

    def test_native_defer_blocks_preserve_shadowed_bindings_and_live_locals(self):
        source='''static mut trace:u32=0;fn append(value:u32)->void{unsafe{trace=trace*10+value;}}
fn perform()->void{let value:u32=2;defer {let scratch:u32=1;if scratch==1{append(value);}}
{let value:u32=9;defer append(value);}let later:u32=7;append(later);}
pub fn main_entry()->u32{perform();if unsafe{trace}!=972{return 1;}return 42;}'''
        self.execute(self.compile('native_defer_binding_identity',source))

    def test_native_defer_assignments_run_after_return_value_evaluation(self):
        source='''struct Token{pub value:u32;}
fn scalar()->u32{let mut value:u32=42;defer value=0;return value;}
fn record()->Token{let mut value:Token=Token{value:42};defer value.value=0;return value;}
pub fn main_entry()->u32{let value:Token=record();if scalar()!=42 || value.value!=42{return 1;}return value.value;}'''
        self.execute(self.compile('native_defer_return_snapshot',source))

    def test_sv849a_native_owned_uniform_loop_jumps_execute(self):
        """Both if arms can transfer identically without abandoning ownership."""
        prefix='''struct Token{pub value:u32;}
fn consume(value:sole Token)->u32{return value.value;}'''
        cases=(
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;
if count<2{continue;}else{continue;}}
return consume(owner);}''',
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;
if count==1{break;}else{break;}}
return consume(owner);}''',
        )
        for index,body in enumerate(cases):
            with self.subTest(index=index):
                self.execute(self.compile('sv849a_uniform_jump_'+str(index),prefix+body))

    def test_sv849a_native_owned_loop_jump_states_fail_closed(self):
        """Reject conditional moved owners, backedge moves and opaque exits."""
        prefix='''struct Token{pub value:u32;}
fn consume(value:sole Token)->u32{return value.value;}'''
        cases=(
            # The break exit may contain an owner only on one arm.
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;
if count==1{let moved:sole Token=owner;break;}else{break;}}
return consume(owner);}''',
            # A next iteration cannot revive an owner consumed before continue.
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;
if count==1{let moved:sole Token=owner;continue;}else{continue;}}
return 42;}''',
            # A consumed condition cannot feed a live continue backedge.
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;
if consume(owner)==42{break;}else{continue;}}
return consume(owner);}''',
            # A partial break must not consume an owner still visible after the loop.
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;
if count==1{consume(owner);break;}else{count=count+1;}}
return consume(owner);}''',
        )
        for index,body in enumerate(cases):
            with self.subTest(index=index):
                self.compile('sv849a_owned_jump_reject_'+str(index),
                    prefix+body,success=False)

    def test_sv849b_native_mixed_loop_edges_preserve_sole_owner(self):
        """Break/continue branch snapshots keep the surrounding owner live."""
        prefix='''struct Token{pub value:u32;}
fn consume(value:sole Token)->u32{return value.value;}'''
        cases=(
            # Exact former SV8.49a rejection: SV8.49b proves both states live.
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;
if count==1{break;}else{continue;}}
return consume(owner);}''',
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<4{count=count+1;
if count==1{continue;}else{break;}}
return consume(owner);}''',
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<4{count=count+1;
if count==2{break;}else{continue;}}
return consume(owner);}''',
        )
        for index,body in enumerate(cases):
            with self.subTest(index=index):
                self.execute(self.compile('sv849b_mixed_jump_'+str(index),prefix+body))

    def test_sv849b_native_mixed_edges_preserve_owned_defer_cleanup(self):
        """Each branch must execute its lexical defer before jumping."""
        source='''struct Token{pub value:u32;}static mut trace:u32=0;
fn read(value:direct Token)->void{unsafe{trace=trace*10+value.value;}}
fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{
let owner:sole Token=Token{value:2};let mut step:u32=0;
while step<3{step=step+1;
if step==1{defer read(owner);continue;}else{defer read(owner);break;}}
if unsafe{trace}!=22{return 1;}return consume(owner)+40;}'''
        self.execute(self.compile('sv849b_mixed_owned_defer',source))

    def test_sv849b_native_mixed_edges_reject_owner_moves_and_opaque_joins(self):
        """Never silently join consumed owners on break/continue edges."""
        prefix='''struct Token{pub value:u32;}
fn consume(value:sole Token)->u32{return value.value;}'''
        cases=(
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;
if count==1{let moved:sole Token=owner;break;}else{continue;}}
return consume(owner);}''',
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;
if count==1{break;}else{let moved:sole Token=owner;continue;}}
return consume(owner);}''',
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;
if count==1{let moved:sole Token=owner;continue;}else{break;}}
return consume(owner);}''',
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;
if count==1{continue;}else{let moved:sole Token=owner;break;}}
return consume(owner);}''',
            # A consumed break edge remains maybe-moved after a mixed match.
            '''pub fn main_entry()->u32{
let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;
match count{1=>{if count==1{consume(owner);break;}else{continue;}},_=>{break;}}}
return consume(owner);}''',
        )
        for index,body in enumerate(cases):
            with self.subTest(index=index):
                self.compile('sv849b_mixed_owned_reject_'+str(index),
                    prefix+body,success=False)

    def test_sv849c_break_only_consumption_executes_on_both_branch_orders(self):
        prefix='''struct Token{pub value:u32;}static mut calls:u32=0;
fn consume(value:sole Token)->void{unsafe{calls=calls+1;}}
fn read(value:direct Token)->u32{return value.value;}'''
        for index,body in enumerate((
            'if count==2{consume(owner);break;}else{if read(owner)!=42{return 1;}continue;}',
            'if count<2{if read(owner)!=42{return 1;}continue;}else{consume(owner);break;}',
        )):
            source=prefix+'pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let mut count:u32=0;'
            source+='while count<3{count=count+1;'+body+'}if unsafe{calls}!=1{return 2;}return 42;}'
            self.execute(self.compile('sv849c_break_consume_'+str(index),source))

    def test_sv849c_match_loop_edges_execute_and_cleanup_once(self):
        source='''struct Token{pub value:u32;}static mut trace:u32=0;
fn observe(value:direct Token)->void{unsafe{trace=trace*10+value.value;}}
fn consume(value:sole Token)->void{return;}
pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let witness:sole Token=Token{value:2};
let mut count:u32=0;while count<3{count=count+1;match count{
1=>{defer observe(witness);continue;},_=>{defer observe(witness);consume(owner);break;}}}
if unsafe{trace}!=22{return 1;}return 42;}'''
        self.execute(self.compile('sv849c_match_owned_edges',source))

    def test_sv849c_uniform_match_loop_exits_preserve_live_owners(self):
        prefix='struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}'
        for index,jump in enumerate(('break','continue')):
            source=prefix+'pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let mut count:u32=0;'
            source+='while count<3{count=count+1;match count{1=>{'+jump+';},_=>{'+jump+';}}}return consume(owner);}'
            self.execute(self.compile('sv849c_uniform_match_'+str(index),source))

    def test_sv849c_nested_loop_exit_summaries_do_not_leak(self):
        source='''struct Token{pub value:u32;}static mut calls:u32=0;
fn consume(value:sole Token)->void{unsafe{calls=calls+1;}}
pub fn main_entry()->u32{let outer:sole Token=Token{value:42};let mut count:u32=0;
while count<2{count=count+1;let inner:sole Token=Token{value:1};let mut step:u32=0;
while step<2{step=step+1;if step==1{continue;}else{consume(inner);break;}}
if count==1{continue;}else{consume(outer);break;}}
if unsafe{calls}!=3{return 1;}return 42;}'''
        self.execute(self.compile('sv849c_nested_edge_summaries',source))

    def test_sv849c_consumed_exit_and_continue_paths_fail_closed(self):
        prefix='struct Token{pub value:u32;}fn consume(value:sole Token)->void{return;}'
        cases=(
            'if count==1{consume(owner);break;}else{continue;}',
            'if count==1{continue;}else{consume(owner);break;}',
            'match count{1=>{consume(owner);break;},_=>{continue;}}',
            'match count{1=>{continue;},_=>{consume(owner);break;}}',
            'match count{1=>{consume(owner);continue;},_=>{break;}}',
            'match count{1=>{break;},_=>{consume(owner);continue;}}',
            'match count{1=>{consume(owner);break;},_=>{count=count+1;}}',
        )
        for index,body in enumerate(cases):
            self.compile('sv849c_edge_state_reject_'+str(index),prefix+
                'pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let mut count:u32=0;'
                'while count<3{count=count+1;'+body+'}return owner.value;}',success=False)

    def test_native_defer_loop_jumps_cleanup_once_before_backedge(self):
        source='''static mut trace:u32=0;fn append(value:u32)->void{unsafe{trace=trace*10+value;}}
fn perform()->void{defer append(9);let mut index:u32=0;
while index<3{index=index+1;defer append(index);{defer append(4);if index==1{continue;}if index==2{break;}}}}
pub fn main_entry()->u32{perform();if unsafe{trace}!=41429{return 1;}return 42;}'''
        self.execute(self.compile('native_defer_loop_cleanup',source))

    def test_native_defer_rejects_nonlocal_jumps_nested_defers_and_owned_capture(self):
        cases=(
            'pub fn main_entry()->u32{defer {return;}return 42;}',
            'pub fn main_entry()->u32{while true{defer {break;}break;}return 42;}',
            'pub fn main_entry()->u32{defer {defer {}}return 42;}',
            'pub fn main_entry()->u32{let value:u32=42;defer value;return 42;}',
            'struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}pub fn main_entry()->u32{let value:sole Token=Token{value:42};defer consume(value);return 42;}',
            'struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}pub fn main_entry()->u32{defer {let value:sole Token=Token{value:42};consume(value);consume(value);}return 42;}',
        )
        for index,source in enumerate(cases):
            with self.subTest(index=index):self.compile('native_defer_rejection_'+str(index),source,success=False)

    def test_native_defer_capacity_fails_closed(self):
        source='fn cleanup()->void{}pub fn main_entry()->u32{'+('defer cleanup();'*129)+'return 42;}'
        self.compile('native_defer_capacity',source,success=False)

    def test_record_conditional_values_copy_nested_fields_and_select_one_arm(self):
        source='''struct Inner{pub number:u32;pub factor:f32;}
struct Packet{pub inner:Inner;pub flags:[bool;4];}
static mut calls:u32=0;
fn make(number:u32)->Packet{unsafe{calls=calls+1;}return Packet{inner:Inner{number:number,factor:2.0},flags:[false;4]};}
fn choose(flag:bool)->Packet{return if flag{make(21)}else{make(99)};}
fn score(packet:Packet)->u32{if packet.inner.factor!=2.0 || packet.flags[2]{return 1;}return packet.inner.number;}
pub fn main_entry()->u32{let mut original:Packet=make(21);
let mut selected=if true{original}else{make(99)};original.inner.number=7;
selected.flags[2]=true;if selected.inner.number!=21 || !selected.flags[2] || original.flags[2]{return 1;}
let answer:u32=score(if false{make(99)}else{choose(true)});
if unsafe{calls}!=2{return 2;}return answer*2;}'''
        self.execute(self.compile('record_conditional_values',source))

    def test_record_conditional_values_execute_in_loops_and_assignments(self):
        source='''struct Token{pub value:u32;}
fn read(value:Token)->u32{return value.value;}
pub fn main_entry()->u32{let mut count:u32=0;let mut sum:u32=0;let mut value:Token=Token{value:0};
while count<2{value=if count==0{Token{value:21}}else{Token{value:7}};
sum=sum+read(if count==1{Token{value:21}}else{value});count=count+1;}return sum;}'''
        self.execute(self.compile('record_conditional_loop',source))

    def test_exclusive_conditional_values_move_owners_per_path(self):
        source='''struct Token{pub value:u32;}
fn create(value:u32)->sole Token{return Token{value:value};}
fn select(flag:bool,value:sole Token)->sole Token{return if flag{value}else{create(42)};}
fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let first:sole Token=create(42);
let second:sole Token=if true{first}else{create(1)};
let third:sole Token=select(false,second);return consume(if true{third}else{create(1)});}'''
        self.execute(self.compile('exclusive_conditional_results',source))
        self.compile('exclusive_conditional_maybe_moved_result',source.replace('let third:sole Token=select(false,second);','let third:sole Token=select(false,second);let bad:u32=first.value;'),success=False)
        self.compile('exclusive_conditional_domain_erasure',source.replace('let second:sole Token=','let second:Token='),success=False)

    def test_conditional_records_reject_type_and_pointer_erasure(self):
        prefix='struct First{pub value:u32;}struct Second{pub value:u32;}'
        cases=(
            'pub fn main_entry()->u32{let value:First=if true{First{value:42}}else{Second{value:42}};return value.value;}',
            'fn read(value:Second)->u32{return value.value;}pub fn main_entry()->u32{return read(if true{First{value:42}}else{First{value:42}});}',
            'fn escape()->*mut First{return if true{First{value:42}}else{First{value:42}};}pub fn main_entry()->u32{return 42;}',
            '@extern(C) fn read(value:*const First)->u32;pub fn main_entry()->u32{return read(if true{First{value:42}}else{First{value:42}});}',
            'pub fn main_entry()->u32{let value:*mut First=if true{First{value:42}}else{First{value:42}};return 42;}',
        )
        for index,body in enumerate(cases):
            with self.subTest(index=index):self.compile('conditional_record_rejection_'+str(index),prefix+body,success=False)

    def test_conditional_pointer_values_preserve_reference_identity(self):
        source='''struct Token{pub value:u32;}
fn choose(flag:bool,left:*mut Token,right:*mut Token)->*mut Token{return if flag{left}else{right};}
pub fn main_entry()->u32{let mut left:Token=Token{value:0};let mut right:Token=Token{value:1};
let selected:*mut Token=choose(true,unsafe{(&mut left) as *mut Token},unsafe{(&mut right) as *mut Token});
unsafe{(*selected).value=42;}if left.value!=42 || right.value!=1{return 1;}return left.value;}'''
        self.execute(self.compile('conditional_pointer_identity',source))

    def test_conditional_borrow_cannot_overlap_owner_consumption(self):
        source='''struct Token{pub value:u32;}
fn overlap(borrowed:whisper Token,owned:sole Token)->u32{return borrowed.value+owned.value;}
pub fn main_entry()->u32{let first:sole Token=Token{value:21};let second:sole Token=Token{value:21};
return overlap(if true{first}else{second},first);}'''
        self.compile('conditional_borrow_overlap',source,success=False)

    def test_constant_validation_preserves_null_identity_cast_and_unsafe_values(self):
        source='''static mut empty:*mut u8=null;const FIRST:u32=5 as u32;
const SECOND:u32=unsafe{37};pub fn main_entry()->u32{
if unsafe{empty}!=null{return 1;}return FIRST+SECOND;}'''
        self.execute(self.compile('constant_existing_forms',source))

    def test_constant_conditional_and_boolean_arms_evaluate_lazily(self):
        source='''static mut answer:u32=VALUE;
const VALUE:u32=if ENABLED{if FLAG{BASE+21}else{1/0}}else{1/0};
const SAFE:bool=false && (1/0>0);const READY:bool=true || (1/0==0);
const ENABLED:bool=READY && !SAFE;const BASE:u32=21;const FLAG:bool=true;
const SCALE:f32=if FLAG{1.5+0.5}else{1.0/0.0};
pub fn main_entry()->u32{if unsafe{answer}!=42 || SCALE!=2.0 || SAFE || !READY{return 1;}return VALUE;}'''
        self.execute(self.compile('lazy_constant_control',source))

    def test_inactive_conditional_dependency_keeps_its_real_cached_value(self):
        source='''const FIRST:u32=if true{42}else{SECOND};
const SECOND:u32=if FLAG{21*2}else{7};const FLAG:bool=true;
const ZERO:u8=MAX+1;const MAX:u8=255;
pub fn main_entry()->u32{if FIRST!=42 || SECOND!=42 || ZERO!=0{return 1;}return SECOND;}'''
        self.execute(self.compile('constant_validation_cache',source))

    def test_constant_inactive_arms_still_check_types_names_and_calls(self):
        cases=(
            'const A:u32=if true{42}else{1.5};',
            'const A:bool=true || 42;',
            'const A:u32=if true{42}else{UNKNOWN};',
            'fn compute()->u32{return 7;}const A:u32=if true{42}else{compute()};',
            'const A:u32=if true{42}else{A};',
            'const A:u32=if false{42}else{1/0};',
            'const A:bool=true && (1/0==0);',
        )
        for index,source in enumerate(cases):
            with self.subTest(index=index):
                self.compile('constant_inactive_rejection_'+str(index),source+'pub fn main_entry()->u32{return 42;}',success=False)

    def test_constant_dependency_capacity_and_nested_depth_are_bounded(self):
        for count,success in ((64,True),(65,False)):
            declarations=''.join('const C'+str(index)+':u32='+('C'+str(index+1) if index+1<count else '42')+';' for index in range(count))
            with self.subTest(count=count):
                obj=self.compile('constant_chain_'+str(count),declarations+'pub fn main_entry()->u32{return C0;}',success=success)
                if success:self.execute(obj)
        deep='42'
        for _ in range(70):deep='if true{'+deep+'}else{42}'
        self.compile('constant_depth_exhaustion','const A:u32='+deep+';pub fn main_entry()->u32{return 42;}',success=False)

    def test_forward_constants_initialize_storage_before_functions(self):
        source='''static mut answer:u32=TOTAL;static mut samples:[f32;2]=[SCALE;2];
const TOTAL:u32=BASE*2;const SCALE:f32=OFFSET+0.5;const BASE:u32=21;const OFFSET:f32=1.5;
pub fn main_entry()->u32{if unsafe{answer}!=42 || unsafe{samples[1]}!=2.0{return 1;}return TOTAL;}'''
        self.execute(self.compile('forward_constant_storage',source))

    def test_constant_cycles_and_invalid_forward_dependencies_fail_closed(self):
        cases=(
            'const A:u32=A;',
            'const A:u32=B;const B:u32=A;',
            'const A:u32=B;const B:u32=C;const C:u32=A;',
            'const A:u32=B;const B:f32=1.5;',
            'const A:i8=B+1;const B:i8=127;',
            'const A:u32=MISSING;',
            'const A:u32=1;const A:u32=2;',
        )
        for index,source in enumerate(cases):
            with self.subTest(index=index):
                self.compile('constant_dependency_rejection_'+str(index),source+'pub fn main_entry()->u32{return 42;}',success=False)

    def test_native_lowering_preserves_parameter_binding_and_return_domains(self):
        program='module unit;struct Token{pub value:u32;}fn read(value:whisper Token)->u32{return value.value;}fn make()->sole Token{return Token{value:42};}fn transfer(value:sole Token)->sole Token{return value;}pub fn main_entry()->u32{let owner:sole Token=make();return read(owner);}'
        source='''import sotlas::compiler::token::*;
import sotlas::compiler::ast::*;import sotlas::compiler::lexer::*;
import sotlas::compiler::parser::*;import sotlas::compiler::sema::*;
import sotlas::compiler::backend::target_ir::*;
import sotlas::compiler::backend::lower_scalar::*;
static mut text_bytes:[u8;4194304]=0;
static mut tokens:[Token;1024]=0;static mut nodes:[AstNode;1024]=0;
static mut values:[TargetValue;256]=0;static mut parameters:[TargetParameter;32]=0;
static mut instructions:[TargetInstruction;512]=0;static mut operands:[TargetOperand;512]=0;
static mut incoming:[TargetPhiInput;64]=0;static mut blocks:[TargetBlock;128]=0;
static mut edges:[u32;256]=0;static mut functions:[TargetFunction;16]=0;
pub fn main_entry()->u32{
let input:*const u8="PROGRAM";let length:usize=LENGTH;
let text:*mut u8=unsafe{text_bytes as *mut u8};let mut index:usize=0;
while index<length{unsafe{*(text+index)=*(input+index);}index=index+1;}
unsafe{g_extended_len=length;}
let tok:*mut Token=unsafe{tokens as *mut Token};let ast:*mut AstNode=unsafe{nodes as *mut AstNode};
let vals:*mut TargetValue=unsafe{values as *mut TargetValue};
let pars:*mut TargetParameter=unsafe{parameters as *mut TargetParameter};
let mut lexer:Lexer=Lexer::new(text,length);let mut count:usize=0;
while count<1024{let token:Token=lexer.next_token();unsafe{*(tok+count)=token;}count=count+1;if token.kind==TokenKind::Eof{break;}}
if lexer.error_count!=0 || count==1024{return 1;}
let mut parser:Parser=Parser::new(tok,count,ast,1024);let unit:usize=parser.parse_module();
if unit==0 || parser.error_count!=0{return 2;}
let mut sema:Sema=Sema::new();
if !sema.check_top_level_declarations(ast,parser.node_count,unit,text,length){return 3;}
let mut lowering:ScalarLowering=ScalarLowering::new(ast,parser.node_count,text,length,
vals,256,pars,32,unsafe{instructions as *mut TargetInstruction},512,
unsafe{operands as *mut TargetOperand},512,unsafe{incoming as *mut TargetPhiInput},64,
unsafe{blocks as *mut TargetBlock},128,unsafe{edges as *mut u32},256,
unsafe{functions as *mut TargetFunction},16);
let mut ir:TargetModule=TargetModule{version:1,function_count:0,parameter_count:0,
block_count:0,instruction_count:0,value_count:0,operand_count:0,phi_input_count:0,target_count:0};
if !lower_scalar_module(&mut lowering,unit,&mut ir){return 4;}
let mut exclusive:usize=0;let mut borrowed_values:usize=0;index=0;
while index<ir.value_count as usize{let flags:u32=unsafe{(*(vals+index)).flags};
let domain:u32=(flags&TARGET_VALUE_DOMAIN_MASK)>>TARGET_VALUE_DOMAIN_SHIFT;
if domain==1{exclusive=exclusive+1;}else if domain==4{borrowed_values=borrowed_values+1;}else if domain!=0{return 5;}index=index+1;}
if exclusive<4 || borrowed_values!=1{return 6;}
let first:TargetParameter=unsafe{*pars};
if first.type_tag!=TargetTypeTag::Pointer || unsafe{(*(vals+first.value_id as usize-1)).flags}!=1024{return 7;}
return 42;}'''.replace('PROGRAM',program).replace('LENGTH',str(len(program)))
        self.execute(self.compile('native_owned_ir_domains',source))

    def test_native_whisper_reads_and_forwarding_preserve_owner(self):
        source='''struct Token{pub value:u32;}
fn read(value:whisper Token)->u32{return value.value;}
fn forward(value:whisper Token)->u32{return read(value);}
fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let owner:sole Token=Token{value:21};
if forward(owner)!=21 || read(owner)!=21{return 1;}return consume(owner)+21;}'''
        self.execute(self.compile('whisper_internal_forward',source))

    def test_native_exclusive_static_and_receiver_calls_preserve_transfers(self):
        source='''struct Token{pub value:u32;}struct Factory{pub initial:u32;}
impl Token{pub fn create()->sole Token{return Token{value:21};}
pub fn consume(value:sole Token)->u32{return value.value;}}
impl Factory{pub fn build(self:&Self)->sole Token{return Token{value:self.initial};}}
pub fn main_entry()->u32{let factory:Factory=Factory{initial:21};
let first:sole Token=Token::create();let second:sole Token=factory.build();
return Token::consume(first)+Token::consume(second);}'''
        self.execute(self.compile('exclusive_method_transfers',source))
        self.compile('exclusive_method_moved',source.replace('return Token::consume(first)+Token::consume(second);','Token::consume(first);return first.value+second.value;'),success=False)
        self.compile('exclusive_receiver_erasure',source.replace('let second:sole Token=factory.build();','let second:Token=factory.build();'),success=False)

    def test_native_exclusive_unsafe_wrapper_preserves_consumption(self):
        source='''struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let first:sole Token=Token{value:42};let second:sole Token=unsafe{first};return consume(second);}'''
        self.execute(self.compile('exclusive_unsafe_transfer',source))
        self.compile('exclusive_unsafe_moved',source.replace('return consume(second);','return first.value+consume(second);'),success=False)

    def test_unsafe_pod_value_bindings_keep_independent_storage(self):
        source='''struct Token{pub value:u32;}
pub fn main_entry()->u32{let mut original:Token=Token{value:42};
let copied:Token=unsafe{original};original.value=99;return copied.value;}'''
        self.execute(self.compile('unsafe_pod_value_copy',source))

    def test_native_whisper_rejects_mutation_escape_and_overlapping_move(self):
        prefix='struct Token{pub value:u32;}'
        cases=(
            'fn write(value:whisper Token)->u32{value.value=0;return value.value;}',
            'fn erase(value:whisper Token)->Token{return value;}',
            'fn escape(value:whisper Token)->u32{let copied:Token=value;return copied.value;}',
            'fn escape(value:whisper Token)->u32{let copied:Token=unsafe{value};return copied.value;}',
            'fn escape(value:whisper Token)->*const Token{return unsafe{(&value) as *const Token};}',
            'fn consume(value:sole Token)->u32{return value.value;}fn bad(value:whisper Token)->u32{return consume(value);}',
            'fn overlap(borrowed:whisper Token,owned:sole Token)->u32{return borrowed.value+owned.value;}pub fn main_entry()->u32{let owner:sole Token=Token{value:21};return overlap(owner,owner);}',
            'fn overlap(borrowed:whisper Token,owned:sole Token)->u32{return borrowed.value+owned.value;}pub fn main_entry()->u32{let owner:sole Token=Token{value:21};return overlap(unsafe{owner},owner);}',
            'fn overlap(owned:sole Token,borrowed:whisper Token)->u32{return borrowed.value+owned.value;}pub fn main_entry()->u32{let owner:sole Token=Token{value:21};return overlap(owner,owner);}',
            'pub fn main_entry()->u32{let value:whisper Token=Token{value:42};return value.value;}',
            '@extern(C) fn escape(value:whisper Token)->u32;',
        )
        for index,body in enumerate(cases):
            with self.subTest(index=index):
                self.compile('whisper_native_reject_'+str(index),prefix+body,success=False)

    def test_native_exclusive_conditional_consumption_has_path_states(self):
        source='''struct Token{pub value:u32;}
fn consume(value:sole Token)->u32{return value.value;}
fn choose(flag:bool)->u32{let value:sole Token=Token{value:42};
let answer:u32=if flag{consume(value)}else{consume(value)};return answer;}
pub fn main_entry()->u32{if choose(true)!=42 || choose(false)!=42{return 1;}return 42;}'''
        self.execute(self.compile('exclusive_conditional_calls',source))
        invalid=source.replace('else{consume(value)}','else{42}').replace('return answer;','return value.value;')
        self.compile('exclusive_conditional_maybe_moved',invalid,success=False)

    def test_native_exclusive_else_if_merges_only_reachable_paths(self):
        source='''struct Token{pub value:u32;}
fn consume(value:sole Token)->u32{return value.value;}
fn choose(n:u32)->u32{let value:sole Token=Token{value:42};
if n==0{return consume(value);}else if n==1{return consume(value);}return value.value;}
pub fn main_entry()->u32{if choose(0)!=42 || choose(1)!=42 || choose(2)!=42{return 1;}return 42;}'''
        self.execute(self.compile('exclusive_else_if_returns',source))
        self.compile('exclusive_else_if_moved',source.replace('else if n==1{return consume(value);}','else if n==1{consume(value);}'),success=False)

    def test_native_exclusive_rejects_erasure_through_returned_values(self):
        prefix='''struct Token{pub value:u32;}fn create()->sole Token{return Token{value:42};}'''
        cases=(
            'pub fn main_entry()->u32{let value:Token=create();return value.value;}',
            'pub fn main_entry()->u32{let value:Token=unsafe{create()};return value.value;}',
            'pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let value:Token=unsafe{owner};return value.value;}',
            'fn erase()->Token{return create();}pub fn main_entry()->u32{return erase().value;}',
            'impl Token{pub fn create()->sole Token{return Token{value:42};}}pub fn main_entry()->u32{let value:Token=Token::create();return value.value;}',
            'pub fn main_entry()->u32{let mut value:Token=Token{value:0};value=create();return value.value;}',
            'pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let mut value:Token=Token{value:0};value=owner;return value.value;}',
            'struct Box{pub inner:Token;}pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let value:Box=Box{inner:owner};return value.inner.value;}',
        )
        for index,body in enumerate(cases):
            with self.subTest(index=index):
                self.compile('exclusive_domain_erasure_'+str(index),prefix+body,success=False)

    def test_native_exclusive_pod_call_binding_and_return_transfers(self):
        source='''struct Token{pub value:u32;}
fn create()->sole Token{return Token{value:42};}
fn forward(value:sole Token)->sole Token{return value;}
fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let first:sole Token=create();let second:exclusive Token=first;
let third:sole Token=forward(second);return consume(third);}'''
        obj=self.compile('exclusive_pod_transfers',source)
        self.execute(obj)
        # The reference grammar spells exclusive POD values with a sole
        # declaration. Compare layout and execution through that equivalent
        # spelling; native move violations have separate rejection gates.
        path=obj.with_suffix('.sotlas')
        original=path.read_text(encoding='utf-8')
        reference=original.replace('struct Token{','sole struct Token{').replace('sole Token','Token').replace('exclusive Token','Token')
        path.write_text(reference,encoding='utf-8')
        try:
            self.assert_c11_reference(obj)
        finally:
            path.write_text(original,encoding='utf-8')

    def test_native_exclusive_branch_merge_and_live_return_path(self):
        source='''struct Token{pub value:u32;}
fn consume(value:sole Token)->u32{return value.value;}
fn select(flag:bool)->u32{let value:sole Token=Token{value:42};
if flag{return consume(value);}return value.value;}
pub fn main_entry()->u32{if select(true)!=42 || select(false)!=42{return 1;}return 42;}'''
        self.execute(self.compile('exclusive_live_paths',source))
        invalid='''struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let value:sole Token=Token{value:42};if true{consume(value);}return value.value;}'''
        self.compile('exclusive_maybe_moved',invalid,success=False)

    def test_native_exclusive_loop_rejects_repeated_outer_consumption(self):
        source='''struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let value:sole Token=Token{value:42};let mut index:u32=0;
while index<2{consume(value);index=index+1;}return 42;}'''
        self.compile('exclusive_loop_move',source,success=False)

    def test_native_exclusive_pod_rejects_moves_aliases_and_pointer_escapes(self):
        prefix='struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}'
        cases=(
            'let first:sole Token=Token{value:42};consume(first);return first.value;',
            'let first:sole Token=Token{value:42};let second:sole Token=first;return first.value;',
            'let first:sole Token=Token{value:42};consume(first);return consume(first);',
            'let first:sole Token=Token{value:42};let alias:Token=first;return alias.value;',
            'let first:sole Token=Token{value:42};let alias:*const Token=unsafe{(&first) as *const Token};return 42;',
        )
        for index,body in enumerate(cases):
            self.compile('exclusive_violation_'+str(index),prefix+'pub fn main_entry()->u32{'+body+'}',success=False)

    def test_constant_folding_preserves_operand_and_destination_types(self):
        cases=(
            'const F:f64=1.5;const BAD:u32=F;',
            'const F:f64=1.5;static mut BAD:u32=F;',
            'const F:f64=1.5;const BAD:u32=F+1;',
            'const B:bool=true;static mut BAD:u32=B;',
            'const F:f32=1.5;static mut BAD:[u32;2]=[F;2];',
            'const BAD:bool=0;',
        )
        for index,declaration in enumerate(cases):
            self.compile('constant_type_error_'+str(index),declaration+'pub fn main_entry()->u32{return 42;}',success=False)

    def test_boolean_array_fields_preserve_layout_copy_and_mutation(self):
        source='''struct Flags{pub values:[bool;4];pub total:u32;}
fn create()->Flags{return Flags{values:[false;4],total:42};}
pub fn main_entry()->u32{let original:Flags=create();let mut copy:Flags=original;
copy.values[2]=true;if original.values[2] || !copy.values[2] || copy.values[1]{return 1;}return copy.total;}'''
        obj=self.compile('boolean_array_fields',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_boolean_constants_compare_typed_values_and_initialize_arrays(self):
        source='''const NEG:i8=-7;const POS:i8=2;const REAL:f64=-1.5;
const READY:bool=(NEG<POS)&&!(REAL>=1.5)&&true;
pub fn main_entry()->u32{let flags:[bool;3]=[READY,false,!false];
if !flags[0] || flags[1] || !flags[2]{return 1;}return 42;}'''
        obj=self.compile('boolean_constant_comparisons',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_conditional_expressions_select_one_arm_in_loops_calls_and_returns(self):
        source='''static mut COUNT:u32=0;
fn arm(x:u32)->u32{unsafe{COUNT=COUNT+1;}return x;}
fn choose(flag:bool)->u32{return if flag {arm(40)} else {arm(2)};}
fn floating(flag:bool)->f64{return if flag {1.5} else if !flag {2.5} else {9.0};}
pub fn main_entry()->u32{let mut index:u32=0;let mut sum:u32=0;
while index<2{sum=sum+choose(index==0);index=index+1;}
let count:u32=unsafe{COUNT};if count!=2 || floating(true)+floating(false)!=4.0{return 1;}
let yes:bool=if sum==42 {true} else {false};if !yes{return 2;}return sum;}'''
        obj=self.compile('conditional_values',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_conditional_expressions_reject_missing_else_and_type_mismatch(self):
        for index,expression in enumerate(('if true {42}', 'if 7 {42} else {1}', 'if true {42} else {false}')):
            self.compile('bad_conditional_'+str(index),'pub fn main_entry()->u32{return '+expression+';}',success=False)

    def test_unsafe_same_width_integer_float_memory_reinterpretation(self):
        source='''pub fn main_entry()->u32{
let mut small:[u32;1]=[1069547520];let mut wide:[u64;1]=[4609434218613702656];
let small_words:*mut u32=unsafe{small as *mut u32};let wide_words:*mut u64=unsafe{wide as *mut u64};
let small_float:*mut f32=unsafe{small_words as *mut f32};let wide_float:*mut f64=unsafe{wide_words as *mut f64};
let a:f32=unsafe{*small_float};let expected:f32=1.5;let b:f64=unsafe{*wide_float};
if a!=expected || b!=1.5{return 1;}
unsafe{*small_float=2.5;*wide_float=2.5;}
if small[0]!=1075838976 || wide[0]!=4612811918334230528{return 2;}return 42;}'''
        self.execute(self.compile('memory_reinterpretation',source))

    def test_integer_float_memory_reinterpretation_requires_unsafe_and_equal_width(self):
        cases=(
            'let x:*mut f64=words as *mut f64;',
            'let x:*mut f32=unsafe{words as *mut f32};',
        )
        for index,cast in enumerate(cases):
            source='pub fn main_entry()->u32{let mut data:[u64;1]=0;let words:*mut u64=unsafe{data as *mut u64};'+cast+'return 42;}'
            self.compile('bad_reinterpret_'+str(index),source,success=False)

    def test_local_array_lists_and_runtime_repetition_execute(self):
        source='''fn calculate()->u32{let values:[i32;3]=[-7,20,29];
let mut copies:[u32;32]=[values[1] as u32;32];let floats:[f64;2]=[1.5,2.5];
copies[31]=22;let mut index:u32=0;let mut sum:u32=0;
while index<32{sum=sum+copies[index];index=index+1;}
if sum!=642 || floats[0]+floats[1]!=4.0{return 1;}return (values[0]+values[1]+values[2]) as u32;}
pub fn main_entry()->u32{return calculate();}'''
        obj=self.compile('initialized_local_arrays',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_array_initializers_reject_shape_and_element_type_errors(self):
        for index,initializer in enumerate((
            'let values:[u32;3]=[1,2];','let values:[u32;2]=[1,2,3];',
            'let values:[u32;2]=[1,true];','let values:[u8;2]=[1,256];',
            'let values:[u32;3]=[7;2];',
        )):
            self.compile('bad_array_'+str(index),'pub fn main_entry()->u32{'+initializer+'return 42;}',success=False)

    def test_float_and_boolean_constant_expressions_execute(self):
        source='''const A:f32=1.25;const B:f32=A+A;
const SCALE:f64=(1.5+2.5)*3.0/2.0;const READY:bool=true&&false||true;
static mut VALUES:[f32;3]=[B;3];static mut TOTAL:f64=SCALE+0.5;
pub fn main_entry()->u32{let b:f32=B;let expected:f32=2.5;
let last:f32=unsafe{VALUES[2]};let total:f64=unsafe{TOTAL};
if b!=expected || last!=expected || SCALE!=6.0 || total!=6.5 || !READY{return 1;}return 42;}'''
        obj=self.compile('folded_float_boolean',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_float_constant_overflow_is_rejected_before_output(self):
        self.compile('float_constant_overflow','const BAD:f32=1e17*1e17*1e17;pub fn main_entry()->u32{return 42;}',success=False)

    def test_integer_constant_expressions_are_folded_before_emission(self):
        source='''const BASE:u32=6*7;const NEXT:u32=(BASE+5)-5;
const NEG:i16=(-6*7)/2;const BITS:u32=((NEXT<<2)|3)&255;
static mut COUNT:u32=NEXT+1;
pub fn main_entry()->u32{let count:u32=unsafe{COUNT};
if BASE!=42 || NEXT!=42 || NEG!=-21 || BITS!=171 || count!=43{return 1;}return NEXT;}'''
        obj=self.compile('folded_constants',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_invalid_integer_constant_expressions_fail_even_when_unused(self):
        for index,declaration in enumerate((
            'const BAD:i8=127+1;','const BAD:i8=-128-1;',
            'const BAD:i16=300*300;','const BAD:i64=-9223372036854775808/-1;',
            'const BAD:u32=4/0;','const BAD:u32=4%0;',
            'const BAD:u32=1<<32;','const BAD:i32=1<<31;',
        )):
            self.compile('bad_fold_'+str(index),declaration+'pub fn main_entry()->u32{return 42;}',success=False)

    def test_scientific_literals_in_calls_constants_and_static_storage(self):
        source='''const FACTOR:f64=1.5e+1;static mut INPUT:f32=1.25E-1;
fn calculate(x:f64)->f64{return x*FACTOR;}
pub fn main_entry()->u32{let small:f32=unsafe{INPUT};let expected:f32=0.125;
if small!=expected || calculate(2e0)!=3.0e1{return 1;}
let tiny:f64=1e-18;if tiny<=0.0{return 2;}return 42;}'''
        obj=self.compile('scientific_literals',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_scientific_literals_reject_bad_exponents_before_output(self):
        for index,literal in enumerate(('1e','1e+','1e-','1e19','1e-19','1.0e99999')):
            self.compile('bad_exponent_'+str(index),'pub fn value()->f64{return '+literal+';}',success=False)

    def test_initialized_scalar_storage_and_repeated_arrays_execute(self):
        source='''static mut COUNT:u32=41;static mut SMALL:i8=-128;
static mut RATIO:f64=-1.5;static mut FLAGS:bool=true;
static mut WORDS:[u16;4]=[7;4];static mut ZEROS:[u32;4]=0;
pub fn main_entry()->u32{
let count:u32=unsafe{COUNT};let small:i8=unsafe{SMALL};let ratio:f64=unsafe{RATIO};let flags:bool=unsafe{FLAGS};
if count!=41 || small!=-128 || ratio!=-1.5 || !flags{return 1;}
let first:u16=unsafe{WORDS[0]};let last:u16=unsafe{WORDS[3]};let zero:u32=unsafe{ZEROS[2]};
if first!=7 || last!=7 || zero!=0{return 2;}
unsafe{COUNT=count+1;WORDS[1]=9;}
let changed:u16=unsafe{WORDS[1]};if changed!=9{return 3;}return unsafe{COUNT};}'''
        obj=self.compile('initialized_storage',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_invalid_static_initializers_do_not_become_zero_storage(self):
        for index,declaration in enumerate((
            'static mut BAD:i8=128;','static mut BAD:u32=-1;',
            'static mut BAD:bool=7;','static mut BAD:f64=true;',
            'static mut BAD:[u8;3]=[4;2];','static mut BAD:[u8;3]=[256;3];',
            'static mut BAD:[u8;3]=9;',
        )):
            self.compile('bad_static_'+str(index),declaration+'pub fn main_entry()->u32{return 42;}',success=False)

    def test_typed_module_constants_include_float_bool_and_signed_minimum(self):
        source='''const FRACTION:f32=0.125;const SCALE:f64=-1.5;
const READY:bool=true;const LOW:i8=-128;const MINIMUM:i64=-9223372036854775808;
fn scale(x:f64)->f64{return x*SCALE;}
pub fn main_entry()->u32{let b:bool=READY;let a:f32=FRACTION;let n:i8=LOW;let wide:i64=MINIMUM;
let expected:f32=0.125;if !b || a!=expected || n!=-128 || wide!=-9223372036854775808{return 1;}
if scale(2.0)!=-3.0{return 2;}return 42;}'''
        obj=self.compile('scalar_constants',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_invalid_unused_constants_fail_closed(self):
        for index,declaration in enumerate((
            'const BAD:i8=-129;', 'const BAD:u8=256;',
            'const BAD:bool=42;', 'const BAD:f32=true;',
            'const BAD:f64=0.0000000000000000001;',
            'const BAD:f64=1.0/0.0;',
        )):
            self.compile('unused_bad_'+str(index),declaration+'pub fn main_entry()->u32{return 42;}',success=False)

    def test_unused_constants_do_not_leak_literal_ir_into_functions(self):
        source=''.join(f'const UNUSED{i}:f64=-1.25;' for i in range(40))
        source+='pub fn main_entry()->u32{return 42;}'
        self.execute(self.compile('constant_rollback',source))

    def test_semantic_runtime_markers_are_preserved_but_never_emitted_as_noops(self):
        source = '''import sotlas::compiler::backend::target_ir::*;
import sotlas::compiler::backend::x86_64_scalar::*;
static mut gate_output:[u8;8192]=0;
static mut gate_values:[TargetValue;1]=0;static mut gate_functions:[TargetFunction;1]=0;
static mut gate_blocks:[TargetBlock;1]=0;static mut gate_instructions:[TargetInstruction;3]=0;
static mut gate_operands:[TargetOperand;1]=0;
fn check_runtime_op(op:u32)->u32{
let v:*mut TargetValue=unsafe{gate_values as *mut TargetValue};
let f:*mut TargetFunction=unsafe{gate_functions as *mut TargetFunction};
let b:*mut TargetBlock=unsafe{gate_blocks as *mut TargetBlock};
let i:*mut TargetInstruction=unsafe{gate_instructions as *mut TargetInstruction};
let a:*mut TargetOperand=unsafe{gate_operands as *mut TargetOperand};
let mut value:TargetValue=TargetValue::empty();value.id=1;value.type_tag=TargetTypeTag::U32;
let mut function:TargetFunction=TargetFunction::empty();function.name=TargetSourceSlice{offset:0,length:4};
function.return_type=TargetTypeTag::U32;function.block_count=1;
let mut block:TargetBlock=TargetBlock::empty();block.id=1;block.instruction_count=2;
let mut constant:TargetInstruction=TargetInstruction::new(TargetOpcode::ConstInt);
constant.result_value=1;constant.type_tag=TargetTypeTag::U32;constant.immediate_bits=42;
let argument:TargetOperand=TargetOperand::new(1);
unsafe{*v=value;*f=function;*i=constant;*a=argument;}
let mut last:usize=1;let mut count:u32=2;
if op!=0{let mut marker:TargetInstruction=TargetInstruction::new(op as TargetOpcode);
marker.type_tag=TargetTypeTag::Void;marker.flags=TARGET_FLAG_SEMANTIC_ONLY;
unsafe{*(i+1)=marker;}block.instruction_count=3;last=2;count=3;}
let mut ending:TargetInstruction=TargetInstruction::new(TargetOpcode::Return);
ending.type_tag=TargetTypeTag::U32;ending.operand_count=1;
unsafe{*(i+last)=ending;*b=block;}
let ir:TargetModule=TargetModule{version:1,function_count:1,parameter_count:0,
block_count:1,instruction_count:count,value_count:1,operand_count:1,phi_input_count:0,target_count:0};
let fc:*const TargetFunction=unsafe{f as *const TargetFunction};
let vc:*const TargetValue=unsafe{v as *const TargetValue};
let bc:*const TargetBlock=unsafe{b as *const TargetBlock};
let ic:*const TargetInstruction=unsafe{i as *const TargetInstruction};
let ac:*const TargetOperand=unsafe{a as *const TargetOperand};
let m:*const TargetModule=unsafe{(&ir) as *const TargetModule};
if !target_module_validate_cfg(m,fc,null,vc,bc,ic,ac,null,null){return 1;}
let mut length:usize=999;unsafe{gate_output[0]=77;}
let accepted:bool=emit_elf64_module_object("unit",4,m,fc,null,vc,bc,ic,ac,null,null,
unsafe{gate_output as *mut u8},8192,unsafe{(&mut length) as *mut usize});
if op==0{if !accepted || length==0{return 2;}return 0;}
if accepted || length!=0 || unsafe{gate_output[0]}!=77{return 3;}
if unsafe{(*(i+1)).opcode as u32}!=op{return 4;}return 0;}
pub fn main_entry()->u32{if check_runtime_op(0)!=0{return 1;}
let mut op:u32=15;while op<=25{if check_runtime_op(op)!=0{return op;}op=op+1;}return 42;}'''
        self.execute(self.compile('semantic_gate',source))


if __name__=='__main__':
    unittest.main()
