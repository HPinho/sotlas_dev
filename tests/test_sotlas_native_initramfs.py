"""Execute checked boot archive lookups with the native Sotlas backend."""
from pathlib import Path
import unittest

import test_sotlas_native_i32 as harness


ROOT = Path(__file__).resolve().parents[1]


def member(name, payload=b"", *, mode=0o100644, links=1):
    name += b"\0"
    fields = (1, mode, 0, 0, links, 0, len(payload), 0, 0, 0, 0, len(name), 0)
    header = b"070701" + b"".join(f"{value:08x}".encode("ascii") for value in fields)
    record = header + name
    return record + b"\0" * (-len(record) % 4) + payload + b"\0" * (-len(payload) % 4)


TRAILER = member(b"TRAILER!!!", mode=0)


class NativeInitramfsTests(unittest.TestCase):
    setUpClass = classmethod(harness.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(harness.NativeI32Tests.tearDownClass.__func__)
    compile = harness.NativeI32Tests.compile
    link_image = harness.NativeI32Tests.link_image
    execute = harness.NativeI32Tests.execute

    def lookup(self, name, archive, body):
        library = (ROOT / "runtime/native/initramfs.sotlas").read_text(encoding="utf-8").split(";", 1)[1]
        values = ",".join(map(str, archive))
        source = library + f"""
pub fn main_entry()->u32 {{
    let archive:[u8;{len(archive)}]=[{values}];
    let data:*const u8=unsafe{{archive as *const u8}};
    let file:NativeArchiveFile=native_initramfs_find(data,{len(archive)},"cfg",3);
    {body}
    return 42;
}}
"""
        self.execute(self.compile(name, source))

    def test_binary_file_empty_file_and_missing_path(self):
        archive = member(b"cfg", b"\x80\x00\xff") + member(b"empty") + TRAILER + bytes(8)
        self.lookup("archive_valid", archive, f"""
    if !file.valid || !file.found || file.length!=3 {{ return 1; }}
    if unsafe{{*file.data}}!=128 || unsafe{{*(file.data+1)}}!=0
        || unsafe{{*(file.data+2)}}!=255 {{ return 2; }}
    let empty:NativeArchiveFile=native_initramfs_find(data,{len(archive)},"empty",5);
    if !empty.valid || !empty.found || empty.length!=0 {{ return 3; }}
    let missing:NativeArchiveFile=native_initramfs_find(data,{len(archive)},"missing",7);
    if !missing.valid || missing.found || missing.data!=null {{ return 4; }}
""")

    def test_invalid_archive_never_publishes_a_match(self):
        good = member(b"cfg", b"x")
        cases = {
            "missing_trailer": good,
            "truncated_header": good + TRAILER[:109],
            "trailing_data": good + TRAILER + b"x",
            "duplicate": good + good + TRAILER,
            "parent_path": good + member(b"dir/../bad") + TRAILER,
            "hardlink": good + member(b"alias", links=2) + TRAILER,
            "symlink": good + member(b"link", b"cfg", mode=0o120777) + TRAILER,
            "padding": good[:-1] + b"x" + TRAILER,
            "bad_hex": good + TRAILER[:6] + b"g" + TRAILER[7:],
            "oversize_payload": good[:54] + b"ffffffff" + good[62:] + TRAILER,
        }
        for name, archive in cases.items():
            with self.subTest(name=name):
                self.lookup(
                    "archive_" + name,
                    archive,
                    "if file.valid || file.found || file.data!=null || file.length!=0 { return 1; }",
                )
