"""Checked page-span allocation and Multiboot map import in native Sotlas."""
from pathlib import Path
import struct
import unittest
import test_sotlas_native_i32 as previous
ROOT=Path(__file__).resolve().parents[1]

class NativePagesTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,body):
        source=(ROOT/'runtime/native/pages.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        self.execute(self.compile(name,source+'''pub fn main_entry()->u32{
let mut states:[u8;64]=0;let mut tags:[u64;64]=0;let mut allocator:NativePages=native_pages_empty();
let p:*mut NativePages=unsafe{(&mut allocator) as *mut NativePages};
if !native_pages_open(p,unsafe{states as *mut u8},unsafe{tags as *mut u64},64,1048576){return 90;}
'''+body+'}'))

    def test_alignment_contiguous_pages_and_exact_release(self):
        self.program('pages_span','''native_pages_configure(p,1048576,1310720,true);native_pages_seal(p);
let first:NativePageSpan=native_pages_allocate(p,3,4);
if !native_pages_current(first) || native_page_address(first)%16384!=0 || allocator.free!=61{return 1;}
let mut partial:NativePageSpan=first;partial.count=2;if native_pages_release(partial){return 2;}
partial=first;partial.first+=1;partial.count=2;if native_pages_release(partial){return 3;}
if !native_pages_release(first) || native_pages_release(first) || allocator.free!=64 || allocator.allocated!=0{return 4;}return 42;''')

    def test_generation_reuse_and_sealed_reservations(self):
        self.program('pages_reuse','''native_pages_configure(p,1048576,1310720,true);
native_pages_configure(p,1048577,1052671,false);
if native_pages_allocate(p,1,1).owner!=null || !native_pages_seal(p){return 1;}
let first:NativePageSpan=native_pages_allocate(p,1,1);
if native_page_address(first)!=1052672 || !native_pages_release(first){return 2;}
let again:NativePageSpan=native_pages_allocate(p,1,1);
if again.first!=first.first || again.generation==first.generation || native_pages_current(first)
|| native_pages_release(first) || native_pages_configure(p,1048576,1310720,true){return 3;}return 42;''')

    def test_exhaustion_and_invalid_requests_preserve_counts(self):
        self.program('pages_full','''native_pages_configure(p,1048576,1056768,true);native_pages_seal(p);
let all:NativePageSpan=native_pages_allocate(p,2,1);
if all.owner==null || allocator.free!=0 || native_pages_allocate(p,1,1).owner!=null
|| native_pages_allocate(p,0,1).owner!=null || native_pages_allocate(p,1,3).owner!=null{return 1;}
if !native_pages_release(all) || allocator.free!=2{return 2;}
allocator.sequence=18446744073709551615;
if native_pages_allocate(p,1,1).owner!=null || allocator.free!=2{return 3;}return 42;''')

    def test_partial_available_pages_are_not_granted(self):
        self.program('pages_rounding','''native_pages_configure(p,1048577,1060863,true);native_pages_seal(p);
if allocator.free!=1{return 1;}let span:NativePageSpan=native_pages_allocate(p,1,1);
if native_page_address(span)!=1052672{return 2;}return 42;''')

    def map_body(self,records):
        data=b''.join(struct.pack('<IQQI',20,start,length,kind) for start,length,kind in records)
        return 'let map:[u8;'+str(len(data))+']=['+','.join(map(str,data))+'];\n'

    def test_reserved_map_entries_override_overlapping_available_ranges(self):
        body=self.map_body(((1048576,262144,1),(1052673,1,2),(1048576,262144,1)))
        self.program('pages_map',body+'''if !native_pages_import_map(p,unsafe{map as *const u8},72) || allocator.free!=63{return 1;}
native_pages_seal(p);let a:NativePageSpan=native_pages_allocate(p,1,1);let b:NativePageSpan=native_pages_allocate(p,1,1);
if a.first!=0 || b.first!=2{return 2;}return 42;''')

    def test_malformed_maps_do_not_publish_available_pages(self):
        for i,data in enumerate((b'\0'*24,struct.pack('<IQQI',20,1048576,4096,1)+b'\x14',
                                 struct.pack('<IQQI',20,0xffffffffffffffff,2,1))):
            body='let map:[u8;'+str(len(data))+']=['+','.join(map(str,data))+'];'
            with self.subTest(index=i):
                self.program('pages_badmap_'+str(i),body+f'''if native_pages_import_map(p,unsafe{{map as *const u8}},{len(data)})
|| allocator.free!=0 || allocator.allocated!=0{{return 1;}}return 42;''')

    def test_metadata_overlap_and_reinitialization_are_rejected(self):
        self.program('pages_metadata','''let mut other:NativePages=native_pages_empty();
let q:*mut NativePages=unsafe{(&mut other) as *mut NativePages};
let address:usize=unsafe{q as usize};let overlap:*mut u8=unsafe{address as *mut u8};
if native_pages_open(q,overlap,unsafe{tags as *mut u64},64,1048576)
|| native_pages_open(p,unsafe{states as *mut u8},unsafe{tags as *mut u64},64,1048576){return 1;}
if other.live || allocator.free!=0{return 2;}return 42;''')

    def test_fragmentation_does_not_create_a_noncontiguous_span(self):
        self.program('pages_fragments','''native_pages_configure(p,1048576,1069056,true);
native_pages_configure(p,1056768,1060864,false);native_pages_seal(p);
let a:NativePageSpan=native_pages_allocate(p,2,1);let b:NativePageSpan=native_pages_allocate(p,2,1);
if a.first!=0 || b.first!=3 || allocator.free!=0{return 1;}
native_pages_release(a);native_pages_release(b);
if native_pages_allocate(p,4,1).owner!=null || allocator.free!=4{return 2;}
let c:NativePageSpan=native_pages_allocate(p,2,1);if c.first!=0{return 3;}return 42;''')

    def test_map_extensions_and_unmanaged_high_memory(self):
        data=struct.pack('<IQQI',28,1048576,4096,1)+b'extended'+struct.pack('<IQQI',20,1<<40,4096,1)
        # The extension is exactly size-20 bytes; records are not fixed strides.
        body='let map:[u8;'+str(len(data))+']=['+','.join(map(str,data))+'];'
        self.program('pages_extended_map',body+f'''if !native_pages_import_map(p,unsafe{{map as *const u8}},{len(data)})
|| allocator.free!=1{{return 1;}}native_pages_seal(p);
let a:NativePageSpan=native_pages_allocate(p,1,1);if a.first!=0{{return 2;}}return 42;''')
