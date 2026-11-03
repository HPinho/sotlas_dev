"""SV8.57 native compound assignments: operator parity with fail-closed ownership."""
import unittest
import test_sotlas_native_migration_sv856 as previous

class NativeMigrationSV857Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMigrationSV856Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMigrationSV856Tests.tearDownClass.__func__)
    compile=previous.NativeMigrationSV856Tests.compile
    execute=previous.NativeMigrationSV856Tests.execute
    # The shared executor links each compiled object through self.link_image.
    # Keep the native execution gate, including Windows and Intel macOS.
    link_image=previous.NativeMigrationSV856Tests.link_image

    def verify_operator(self,op,initial,operand,name):
        valid='pub fn main_entry()->u32{let mut value:u32='+str(initial)+';value'+op+str(operand)+';return value;}'
        self.execute(self.compile(name,valid))
        invalid='fn bad()->u32{let value:u32='+str(initial)+';value'+op+str(operand)+';return value;}'
        self.compile(name+'_immutable',invalid,success=False)

    def test_native_modulo_compound_assignment_and_immutability(self):
        self.verify_operator('%=',86,44,'compound_rem')

    def test_native_bitwise_and_compound_assignment_and_immutability(self):
        self.verify_operator('&=',63,42,'compound_and')

    def test_native_bitwise_or_compound_assignment_and_immutability(self):
        self.verify_operator('|=',40,2,'compound_or')

    def test_native_bitwise_xor_compound_assignment_and_immutability(self):
        self.verify_operator('^=',40,2,'compound_xor')

    def test_native_left_shift_compound_assignment_and_immutability(self):
        self.verify_operator('<<=',21,1,'compound_shl')

    def test_native_right_shift_compound_assignment_and_immutability(self):
        self.verify_operator('>>=',84,1,'compound_shr')

    def test_native_compound_rhs_is_evaluated_only_once(self):
        source='''static mut calls:u32=0;
fn increment()->u32{unsafe{calls=calls+1;}return 2;}
pub fn main_entry()->u32{let mut value:u32=40;value|=increment();
if unsafe{calls}!=1{return 1;}return value;}'''
        self.execute(self.compile('compound_or_once',source))

    def test_native_compound_indexed_scalars_execute_and_preserve_immutability(self):
        cases=(('%=',86,44),('&=',63,42),('|=',40,2),('^=',40,2),('<<=',21,1),('>>=',84,1))
        for index,(operator,initial,operand) in enumerate(cases):
            with self.subTest(operator=operator):
                body='values[0]'+operator+str(operand)+';if values[1]!=99{return 1;}return values[0];}'
                source='pub fn main_entry()->u32{let mut values:[u32;2]=['+str(initial)+',99];'+body
                self.execute(self.compile('compound_index_'+str(index),source))
                self.compile('compound_index_immutable_'+str(index),
                             source.replace('let mut values:','let values:'),success=False)

    def test_native_compound_rejects_owned_aggregate_erasure(self):
        for index,operator in enumerate(('%=','&=','|=','^=','<<=','>>=')):
            with self.subTest(operator=operator):
                owned='''struct Token{pub value:u32;}
pub fn main_entry()->u32{let mut token:sole Token=Token{value:42};
token'''+operator+'''1;return 42;}'''
                self.compile('compound_owned_aggregate_reject_'+str(index),owned,success=False)

if __name__=='__main__':unittest.main()
