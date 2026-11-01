"""Allocation-free native delimiter cursor with checked optional ranges."""
from pathlib import Path
import unittest
import test_sotlas_native_pattern_control as previous


class NativeTextSplitTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativePatternControlTests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativePatternControlTests.tearDownClass.__func__)
    compile = previous.NativePatternControlTests.compile
    link_image = previous.NativePatternControlTests.link_image
    execute = previous.NativePatternControlTests.execute

    def program(self, name, body):
        root=Path(__file__).resolve().parents[1]
        sources=[]
        for module in ('results','text','optional','text_split'):
            source=(root/f'runtime/native/{module}.sotlas').read_text(encoding='utf-8')
            sources.append('\n'.join(line for line in source.splitlines() if not line.startswith(('module ','import '))))
        self.execute(self.compile(name,'\n'.join(sources)+'\npub fn main_entry()->u32{'+body+'}'))

    def test_multiple_delimiters_and_preserved_empty_fields(self):
        self.program('split_fields','''let s:NativeByteSlice=native_text_open("::a::::b::",10);
let d:NativeByteSlice=native_text_open("::",2);let mut r:NativeSplitResult=native_split_next(s,d,native_split_open());
let mut count:u32=0;let mut length:usize=0;while let NativeRangeOption::Some(field)=r.value{
if r.status!=0{return 1;}count=count+1;length=length+field.length;r=native_split_next(s,d,r.next);}
if r.status!=0||count!=5||length!=2||!r.next.finished{return 2;}return 42;''')

    def test_no_delimiter_yields_whole_source_once(self):
        self.program('split_whole','''let s:NativeByteSlice=native_text_open("answer",6);let d:NativeByteSlice=native_text_open("::",2);
let r:NativeSplitResult=native_split_next(s,d,native_split_open());if r.status!=0||!r.next.finished{return 1;}
if let NativeRangeOption::Some(field)=r.value{if field.start!=0||field.length!=6{return 2;}}else{return 3;}
let end:NativeSplitResult=native_split_next(s,d,r.next);if let NativeRangeOption::Some(field)=end.value{return 4;}
if end.status!=0||end.next.offset!=6{return 5;}return 42;''')

    def test_empty_source_has_one_empty_field(self):
        self.program('split_empty','''let s:NativeByteSlice=native_text_open("",0);let d:NativeByteSlice=native_text_open(",",1);
let r:NativeSplitResult=native_split_next(s,d,native_split_open());if r.status!=0||!r.next.finished{return 1;}
if let NativeRangeOption::Some(field)=r.value{if field.length!=0||field.start!=0{return 2;}}else{return 3;}
return 42;''')

    def test_error_preserves_cursor_and_is_distinct_from_end(self):
        self.program('split_errors','''let s:NativeByteSlice=native_text_open("a,b",3);let d:NativeByteSlice=native_text_open(",",1);
let cursor:NativeSplitCursor=NativeSplitCursor{offset:2,finished:false};
let a:NativeSplitResult=native_split_next(s,native_text_open("",0),cursor);
let b:NativeSplitResult=native_split_next(native_text_invalid(),d,cursor);
let c:NativeSplitResult=native_split_next(s,native_text_invalid(),cursor);
if a.status!=7||b.status!=7||c.status!=7||a.next.offset!=2||a.next.finished||a.error.offset!=2{return 1;}
if let NativeRangeOption::Some(field)=a.value{return 2;}
let end:NativeSplitResult=native_split_next(s,d,NativeSplitCursor{offset:3,finished:true});
if end.status!=0{return 3;}return 42;''')

    def test_bounds_are_checked_even_for_finished_cursor(self):
        self.program('split_bounds','''let s:NativeByteSlice=native_text_open("a",1);let d:NativeByteSlice=native_text_open(",",1);
let r:NativeSplitResult=native_split_next(s,d,NativeSplitCursor{offset:18446744073709551615,finished:true});
if r.status!=7||r.error.offset!=18446744073709551615||!r.next.finished{return 1;}return 42;''')

    def test_nonoverlapping_delimiters_and_resume(self):
        self.program('split_overlap','''let s:NativeByteSlice=native_text_open("aaaaa",5);let d:NativeByteSlice=native_text_open("aa",2);
let a:NativeSplitResult=native_split_next(s,d,NativeSplitCursor{offset:1,finished:false});
if a.next.offset!=3||a.next.finished{return 1;}
let b:NativeSplitResult=native_split_next(s,d,a.next);if b.next.offset!=5||b.next.finished{return 2;}
let c:NativeSplitResult=native_split_next(s,d,b.next);if !c.next.finished{return 3;}
if let NativeRangeOption::Some(field)=c.value{if field.length!=0||field.start!=5{return 4;}}else{return 5;}return 42;''')

    def test_raw_bytes_and_embedded_zero_delimiters(self):
        self.program('split_zero','''let bytes:[u8;3]=[65,0,66];let delimiter:[u8;1]=[0];
let s:NativeByteSlice=native_text_open(unsafe{(&bytes[0])as *const u8},3);
let d:NativeByteSlice=native_text_open(unsafe{(&delimiter[0])as *const u8},1);
let a:NativeSplitResult=native_split_next(s,d,native_split_open());let b:NativeSplitResult=native_split_next(s,d,a.next);
if let NativeRangeOption::Some(x)=a.value{if x.start!=0||x.length!=1{return 1;}}else{return 2;}
if let NativeRangeOption::Some(x)=b.value{if x.start!=2||x.length!=1{return 3;}}else{return 4;}
return 42;''')

    def test_example_runs_through_native_pattern_control(self):
        root=Path(__file__).resolve().parents[1]
        example=(root/'examples/native_pattern_control/main.sotlas').read_text(encoding='utf-8')
        # This example is also compiled with imports by the rebuilt-driver gates.
        modules=[]
        for name in ('results','text','optional','text_split'):
            modules.append((root/f'runtime/native/{name}.sotlas').read_text(encoding='utf-8'))
        source='\n'.join('\n'.join(line for line in part.splitlines() if not line.startswith(('module ','import '))) for part in modules+[example])
        self.execute(self.compile('split_application',source))


if __name__ == '__main__':
    unittest.main()
