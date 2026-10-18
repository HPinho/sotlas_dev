"""Native inline record-array fields, copies, calls and rejected resource forms."""
import unittest
import signal
import sys
from pathlib import Path
import test_sotlas_native_i32 as previous


class NativeRecordArrayFieldTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute
    windows_process_exit_code = previous.NativeI32Tests.windows_process_exit_code

    def program(self, name, body):
        self.execute(self.compile(name, body))

    def test_checked_in_inventory_example_executes(self):
        example = Path(__file__).resolve().parents[1] / 'examples/record_table/main.sotlas'
        self.program('field_record_inventory_example', example.read_text(encoding='utf-8').split(';',1)[1])

    def test_literal_indexing_and_independent_element_mutation(self):
        self.program('field_record_literals', '''
struct Item{pub value:u32;}struct Table{pub items:[Item;2];}
pub fn main_entry()->u32{
let mut table:Table=Table{items:[Item{value:20},Item{value:22}]};
table.items[0].value=19;table.items[1].value=23;
return table.items[0].value+table.items[1].value;}''')

    def test_repetition_evaluates_once_and_copies_by_value(self):
        self.program('field_record_repeat', '''
struct Item{pub value:u32;}struct Table{pub items:[Item;3];}
static mut calls:u32=0;
fn make()->Item{unsafe{calls=calls+1;}return Item{value:14};}
pub fn main_entry()->u32{let mut table:Table=Table{items:[make();3]};
table.items[0].value=10;table.items[2].value=18;
if unsafe{calls}!=1{return 1;}
return table.items[0].value+table.items[1].value+table.items[2].value;}''')

    def test_nested_layout_and_whole_record_copy_are_independent(self):
        self.program('field_record_nested', '''
struct Item{pub marker:u8;pub value:u64;}
struct Table{pub tag:u8;pub items:[Item;2];pub tail:u16;}
struct Outer{pub prefix:u8;pub table:Table;}
pub fn main_entry()->u32{
let original:Outer=Outer{prefix:1,table:Table{tag:2,
items:[Item{marker:3,value:20},Item{marker:4,value:22}],tail:5}};
let mut copied:Outer=original;copied.table.items[0].value=1;
if original.prefix!=1||original.table.tag!=2||original.table.tail!=5
||copied.table.items[1].marker!=4{return 1;}
return (original.table.items[0].value+original.table.items[1].value) as u32;}''')

    def test_record_array_fields_can_nest_recursively(self):
        self.program('field_record_matrix', '''
struct Cell{pub value:u32;}struct Row{pub cells:[Cell;2];}struct Grid{pub rows:[Row;2];}
pub fn main_entry()->u32{let mut grid:Grid=Grid{rows:[Row{cells:[Cell{value:10};2]};2]};
grid.rows[1].cells[1].value=12;
return grid.rows[0].cells[0].value+grid.rows[0].cells[1].value
+grid.rows[1].cells[0].value+grid.rows[1].cells[1].value;}''')

    def test_record_returns_borrows_and_element_returns(self):
        self.program('field_record_calls', '''
struct Item{pub value:u32;}struct Table{pub items:[Item;2];}
fn make()->Table{return Table{items:[Item{value:20},Item{value:22}]};}
fn sum(table:direct Table)->u32{return table.items[0].value+table.items[1].value;}
fn second(table:direct Table)->Item{return table.items[1];}
pub fn main_entry()->u32{let table:Table=make();let item:Item=second(table);
if item.value!=22{return 1;}return sum(table);}''')

    def test_copy_local_array_and_other_field(self):
        self.program('field_record_array_copy', '''
struct Item{pub value:u32;}struct Table{pub items:[Item;2];}
pub fn main_entry()->u32{let mut values:[Item;2]=[Item{value:20},Item{value:22}];
let first:Table=Table{items:values};let mut second:Table=Table{items:first.items};
values[0].value=1;second.items[1].value=2;
return first.items[0].value+first.items[1].value;}''')

    def test_whole_element_and_whole_field_assignment(self):
        self.program('field_record_assign', '''
struct Item{pub value:u32;}struct Table{pub items:[Item;2];}
pub fn main_entry()->u32{let mut table:Table=Table{items:[Item{value:1};2]};
table.items[0]=Item{value:20};let saved:Table=table;
table.items=[Item{value:21};2];
if saved.items[0].value!=20||saved.items[1].value!=1{return 1;}
return table.items[0].value+table.items[1].value;}''')

    def test_whole_field_swap_snapshots_the_rhs_before_assignment(self):
        self.program('field_record_swap', '''
struct Item{pub value:u32;}struct Table{pub items:[Item;2];}
pub fn main_entry()->u32{let mut table:Table=Table{items:[Item{value:20},Item{value:22}]};
table.items=[table.items[1],table.items[0]];
if table.items[0].value!=22||table.items[1].value!=20{return 1;}
return table.items[0].value+table.items[1].value;}''')

    def test_large_repetition_with_loops_and_dynamic_index(self):
        self.program('field_record_large', '''
struct Item{pub value:u32;}struct Table{pub items:[Item;128];}
pub fn main_entry()->u32{let mut table:Table=Table{items:[Item{value:1};128]};
let mut i:u32=0;while i<128{table.items[i].value=i;i=i+1;}
let index:u32=42;return table.items[index].value;}''')

    def test_local_arrays_of_records_containing_record_array_fields(self):
        self.program('field_record_outer_array', '''
struct Item{pub value:u32;}struct Table{pub items:[Item;2];}
pub fn main_entry()->u32{let mut tables:[Table;2]=[Table{items:[Item{value:21};2]};2];
tables[1].items[0].value=1;
return tables[0].items[0].value+tables[0].items[1].value;}''')

    def test_reject_mismatched_element_record_or_count(self):
        cases = (
            'Table{items:[Other{value:21};2]}',
            'Table{items:[Item{value:42}]}',
            'Table{items:[Item{value:14};3]}',
            'Table{items:[Item{value:14},Item{value:14},Item{value:14}]}',
            'Table{items:0}',
        )
        for index, value in enumerate(cases):
            with self.subTest(value=value):
                self.compile('field_record_bad_' + str(index),
                    'struct Item{pub value:u32;}struct Other{pub value:u32;}'
                    'struct Table{pub items:[Item;2];}'
                    'pub fn main_entry()->u32{let table:Table=' + value + ';return 42;}', success=False)

    def test_reject_pointer_and_owned_payloads_and_capacity_exhaustion(self):
        cases = (
            'struct Item{pub ptr:*const u8;}struct Table{pub items:[Item;2];}',
            'struct Item{pub value:sole u32;}struct Table{pub items:[Item;2];}',
            'struct Item{pub value:u32;}struct Table{pub items:[Item;0];}',
            'struct Item{pub value:u32;}struct Table{pub items:[Item;257];}',
            'struct Item{pub data:[u64;256];}struct Table{pub items:[Item;256];}',
        )
        for index, declarations in enumerate(cases):
            with self.subTest(index=index):
                self.compile('field_record_storage_bad_' + str(index),
                    declarations + 'pub fn main_entry()->u32{return 42;}', success=False)

    def test_reject_immutable_and_borrowed_mutation(self):
        cases = (
            'pub fn main_entry()->u32{let table:Table=Table{items:[Item{value:21};2]};'
            'table.items[0].value=0;return 42;}',
            'fn alter(table:whisper Table)->void{table.items[0].value=0;}'
            'pub fn main_entry()->u32{return 42;}',
        )
        for index, body in enumerate(cases):
            with self.subTest(index=index):
                self.compile('field_record_mutation_bad_' + str(index),
                    'struct Item{pub value:u32;}struct Table{pub items:[Item;2];}' + body, success=False)

    def test_owned_container_transfers_and_borrowed_reads(self):
        self.program('field_record_owned_container', '''
struct Item{pub value:u32;}struct Table{pub items:[Item;2];}
fn make()->sole Table{return Table{items:[Item{value:21};2]};}
fn transfer(value:sole Table)->sole Table{return value;}
fn read(value:whisper Table)->u32{return value.items[0].value+value.items[1].value;}
pub fn main_entry()->u32{let first:sole Table=make();
if read(first)!=42{return 1;}let second:sole Table=transfer(first);return read(second);}''')

    def test_reject_use_after_move_and_record_pointer_erasure(self):
        prefix = 'struct Item{pub value:u32;}struct Table{pub items:[Item;2];}'
        cases = (
            'fn consume(value:sole Table)->void{return;}pub fn main_entry()->u32{'
            'let value:sole Table=Table{items:[Item{value:21};2]};consume(value);return value.items[0].value;}',
            'pub fn main_entry()->u32{let value:Table=Table{items:[Item{value:21};2]};'
            'let ptr:*const Item=value.items[0];return 42;}',
            'pub fn main_entry()->u32{let value:Table=Table{items:[Item{value:21};2]};'
            'return value.items[2].value;}',
        )
        for index, source in enumerate(cases):
            with self.subTest(index=index):
                self.compile('field_record_escape_bad_' + str(index), prefix + source, success=False)

    def test_dynamic_index_traps_before_the_element_is_read(self):
        source = '''struct Item{pub value:u32;}struct Table{pub items:[Item;2];}
fn index()->u32{return 2;}
pub fn main_entry()->u32{let table:Table=Table{items:[Item{value:21};2]};
return table.items[index()].value;}'''
        obj = self.compile('field_record_dynamic_bounds', source)
        if sys.platform == 'win32':
            code, stderr = self.windows_process_exit_code(self.link_image(obj))
            self.assertEqual(code, 0xc000001d, stderr)
        else:
            self.execute(obj, expected=-signal.SIGILL)

    def test_deep_element_layout_overflow_and_oversize_fail_closed(self):
        for depth in (20,29):
            with self.subTest(depth=depth):
                source = 'struct R0{pub value:u64;}'
                for index in range(1,depth+1):
                    source += 'struct R'+str(index)+'{pub left:R'+str(index-1)+';pub right:R'+str(index-1)+';}'
                source += 'struct Table{pub items:[R'+str(depth)+';1];}pub fn main_entry()->u32{return 42;}'
                self.compile('field_record_layout_overflow_'+str(depth),source,success=False)


if __name__ == '__main__':
    unittest.main()
