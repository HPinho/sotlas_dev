"""Native source-backed JSON parsing, navigation, Unicode and failure atomicity."""
from pathlib import Path
import json
import unittest
import test_sotlas_native_i32 as harness

ROOT = Path(__file__).resolve().parents[1]


class NativeJsonTests(unittest.TestCase):
    setUpClass = classmethod(harness.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(harness.NativeI32Tests.tearDownClass.__func__)
    compile = harness.NativeI32Tests.compile
    link_image = harness.NativeI32Tests.link_image
    execute = harness.NativeI32Tests.execute

    def runtime(self):
        return '\n'.join(line for module in ('text', 'unicode', 'results', 'json')
                         for line in (ROOT / f'runtime/native/{module}.sotlas').read_text(encoding='utf-8').splitlines()
                         if not line.startswith(('module ', 'import ')))

    def input(self, raw, name='input'):
        data = raw.encode('utf-8') if isinstance(raw, str) else raw
        if not data:
            return f'let {name}:NativeByteSlice=native_text_open(null,0);\n'
        return (f'let {name}_bytes:[u8;{len(data)}]=[' + ','.join(map(str, data)) + '];\n' +
                f'let {name}:NativeByteSlice=native_text_open(unsafe{{{name}_bytes as *const u8}},{len(data)});\n')

    def program(self, name, body):
        self.execute(self.compile(name, self.runtime() + '\npub fn main_entry()->u32{\n' + body + '}'))

    def test_nested_objects_arrays_and_scalar_kinds(self):
        raw = '{"model":{"layers":[20,22],"live":true,"unused":null},"off":false}'
        self.program('json_nested', self.input(raw) + '''
let root:NativeJsonResult=native_json_parse(input);if root.status!=0 || root.value.kind!=1{return 1;}
let model:NativeJsonResult=native_json_object_get(root.value,native_text_open("model",5));
let layers:NativeJsonResult=native_json_object_get(model.value,native_text_open("layers",6));
let a:NativeJsonResult=native_json_array_at(layers.value,0);let b:NativeJsonResult=native_json_array_at(layers.value,1);
if !a.found || !b.found || native_json_u32(a.value).value+native_json_u32(b.value).value!=42{return 2;}
if native_json_object_get(model.value,native_text_open("live",4)).value.kind!=5
|| native_json_object_get(model.value,native_text_open("unused",6)).value.kind!=7
|| native_json_object_get(root.value,native_text_open("off",3)).value.kind!=6{return 3;}
let missing:NativeJsonResult=native_json_array_at(layers.value,2);
if missing.status!=0 || missing.found || missing.value.valid{return 4;}
let absent:NativeJsonResult=native_json_object_get(root.value,native_text_open("missing",7));
if absent.status!=0 || absent.found{return 5;}return 42;''')

    def test_top_level_values_numbers_and_json_whitespace(self):
        valid = ('0', '-0', '1.25', '-10.5e+12', '9E-3', '1e999999', 'true', 'false', 'null',
                 '[]', '{}', '""', '  \t\r\n[1, {"x": []}] \n')
        body = ''
        for index, raw in enumerate(valid):
            name = f'v{index}'
            body += self.input(raw, name) + f'if native_json_parse({name}).status!=0{{return 1;}}\n'
        self.program('json_values', body + 'return 42;')

    def test_syntax_rejections_and_original_byte_offsets(self):
        invalid = ('', ' ', '+1', '01', '-01', '-', '1.', '1e', '1e+', '.1', 'NaN', 'Infinity',
                   '[1,]', '{"a":1,}', '{"a" 1}', '{a:1}', '[1 2]', '{"a":}',
                   'true false', 'TRUE', 'nullx', '[}', '"unterminated', '\ufeff{}', '\v0')
        body = ''
        for index, raw in enumerate(invalid):
            name = f'v{index}'
            body += self.input(raw, name) + f'if native_json_parse({name}).status==0{{return 1;}}\n'
        body += self.input(' {"a": [1,]}', 'offset') + '''
let result:NativeJsonResult=native_json_parse(offset);
if result.status!=2 || result.offset!=10 || result.found || result.value.valid{return 2;}return 42;'''
        self.program('json_invalid', body)

    def test_unicode_escapes_decoding_and_embedded_nul(self):
        raw = r'"A\u00e9\uD83D\uDE42\u0000\n\t\b\f\r\/\\\""'
        decoded = json.loads(raw).encode('utf-8')
        body = self.input(raw) + '''let result:NativeJsonResult=native_json_parse(input);
if result.status!=0{return 1;}let mut out:[u8;32]=[77;32];
let copied:NativeJsonStringResult=native_json_string_copy(result.value,unsafe{out as *mut u8},32);
'''
        body += f'if copied.status!=0 || copied.length!={len(decoded)}{{return 2;}}\n'
        body += ''.join(f'if out[{i}]!={b}{{return 3;}}\n' for i, b in enumerate(decoded))
        body += f'if out[{len(decoded)}]!=77{{return 4;}}return 42;'
        self.program('json_unicode', body)

    def test_raw_utf8_keys_escaped_keys_and_first_duplicate(self):
        raw = '{"caf\\u00e9":20,"café":99,"\\uD83D\\uDE42":22,"":0}'
        self.program('json_keys', self.input(raw) + self.input('café', 'key') + self.input('🙂', 'face') + '''
let root:NativeJsonResult=native_json_parse(input);if root.status!=0{return 1;}
let a:NativeJsonResult=native_json_object_get(root.value,key);let b:NativeJsonResult=native_json_object_get(root.value,face);
if !a.found || !b.found || native_json_u32(a.value).value!=20 || native_json_u32(b.value).value!=22{return 2;}
if !native_json_object_get(root.value,native_text_open(null,0)).found{return 3;}return 42;''')

    def test_bad_unicode_and_control_bytes_fail_closed(self):
        invalid = (b'"\xc0\x80"', b'"\xed\xa0\x80"', b'"\xf4\x90\x80\x80"', b'"\xe2\x82"',
                   b'"\x00"', b'"\n"', b'"\\x"', b'"\\uZZZZ"', b'"\\uD800"', b'"\\uDC00"',
                   b'"\\uD800\\u0041"', b'"\\u"', b'"\\')
        body = ''
        for index, raw in enumerate(invalid):
            name = f'v{index}'
            body += self.input(raw, name) + f'if native_json_parse({name}).status==0{{return 1;}}\n'
        self.program('json_unicode_bad', body + 'return 42;')

    def test_nesting_limit_and_wide_arrays(self):
        body = self.input('[' * 64 + '0' + ']' * 64, 'good')
        body += self.input('[' * 65 + '0' + ']' * 65, 'deep')
        body += self.input('[' + ','.join(str(i) for i in range(100)) + ']', 'wide')
        body += '''if native_json_parse(good).status!=0 || native_json_parse(deep).status!=5{return 1;}
let root:NativeJsonResult=native_json_parse(wide);if root.status!=0{return 2;}
if native_json_u32(native_json_array_at(root.value,99).value).value!=99{return 3;}return 42;'''
        self.program('json_depth', body)

    def test_string_capacity_and_overlap_fail_before_writes(self):
        body = self.input('"\\u00e9"') + '''
let root:NativeJsonResult=native_json_parse(input);let mut out:[u8;4]=[77;4];
let p:*mut u8=unsafe{out as *mut u8};
let small:NativeJsonStringResult=native_json_string_copy(root.value,p,1);
if small.status!=6 || small.length!=2 || out[0]!=77 || out[3]!=77{return 1;}
let overlap:*mut u8=unsafe{input.data as *mut u8};
if native_json_string_copy(root.value,overlap,input.length).status!=7{return 2;}
if native_json_string_copy(root.value,null,2).status!=1{return 3;}
if native_json_parse(input).status!=0 || native_json_string_copy(root.value,p,2).status!=0
|| out[0]!=195 || out[1]!=169 || out[2]!=77{return 4;}return 42;'''
        self.program('json_copy_fail', body)

    def test_raw_number_preserves_precision_and_u32_is_strict(self):
        body = self.input('[4294967295,4294967296,-1,1.5,1e2,123456789012345678901234567890]') + '''
let root:NativeJsonResult=native_json_parse(input);if root.status!=0{return 1;}
if native_json_u32(native_json_array_at(root.value,0).value).value!=4294967295{return 2;}
let overflow:NativeU32Result=native_json_u32(native_json_array_at(root.value,1).value);
if overflow.status!=4 || overflow.error.offset!=21{return 3;}
let mut i:usize=2;while i<5{if native_json_u32(native_json_array_at(root.value,i).value).status==0{return 4;}i+=1;}
let raw:NativeByteSlice=native_json_raw(native_json_array_at(root.value,5).value);
if !raw.valid || raw.length!=30 || unsafe{*(raw.data)}!=49{return 5;}return 42;'''
        self.program('json_numbers', body)

    def test_invalid_descriptors_and_wrong_value_types(self):
        body = self.input('42') + '''
if native_json_parse(native_text_open(null,1)).status!=1{return 1;}
let root:NativeJsonResult=native_json_parse(input);
if native_json_array_at(root.value,0).status!=4
|| native_json_object_get(root.value,native_text_open("x",1)).status!=4{return 2;}
let forged:NativeJsonValue=NativeJsonValue{source:input,start:0,end:3,kind:4,valid:true};
if native_json_raw(forged).valid || native_json_u32(forged).status==0{return 3;}
let mut out:[u8;2]=[77;2];
if native_json_string_copy(root.value,unsafe{out as *mut u8},2).status!=4 || out[0]!=77{return 4;}return 42;'''
        self.program('json_metadata', body)

    def test_forged_string_span_cannot_include_leading_whitespace(self):
        body = self.input(' "x"') + '''
let forged:NativeJsonValue=NativeJsonValue{source:input,start:0,end:4,kind:3,valid:true};
let mut out:[u8;4]=[77;4];
if native_json_raw(forged).valid || native_json_string_copy(forged,unsafe{out as *mut u8},4).status!=1
|| out[0]!=77 || out[3]!=77{return 1;}return 42;'''
        self.program('json_forged_string', body)

    def test_empty_string_and_empty_collections_have_distinct_missing_results(self):
        body = self.input('["",{},[]]') + '''
let root:NativeJsonResult=native_json_parse(input);
let empty:NativeJsonResult=native_json_array_at(root.value,0);
let copied:NativeJsonStringResult=native_json_string_copy(empty.value,null,0);
if !empty.found || copied.status!=0 || copied.length!=0{return 1;}
let object:NativeJsonResult=native_json_array_at(root.value,1);
let array:NativeJsonResult=native_json_array_at(root.value,2);
let key:NativeJsonResult=native_json_object_get(object.value,native_text_open(null,0));
let item:NativeJsonResult=native_json_array_at(array.value,18446744073709551615);
if key.status!=0 || key.found || item.status!=0 || item.found{return 2;}return 42;'''
        self.program('json_empty', body)
