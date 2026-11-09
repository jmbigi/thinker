from crdt import CRDTText

def test_insert_at_end():
    crdt = CRDTText()
    crdt.insert('a')
    crdt.insert('b')
    assert crdt.to_string() == 'ab'

def test_insert_at_position():
    crdt = CRDTText()
    crdt.insert('a')
    crdt.insert('c')
    crdt.insert('b', 1)
    assert crdt.to_string() == 'abc'

def test_insert_invalid_position():
    crdt = CRDTText()
    crdt.insert('a')
    crdt.insert('b', 10)  # Position out of range, should be ignored
    assert crdt.to_string() == 'a'

def test_delete():
    crdt = CRDTText()
    crdt.insert('a')
    crdt.insert('b')
    crdt.delete(0)
    assert crdt.to_string() == 'b'

def test_delete_invalid_position():
    crdt = CRDTText()
    crdt.insert('a')
    crdt.delete(5)  # Invalid position, should do nothing
    assert crdt.to_string() == 'a'

def test_merge_ordering():
    crdt1 = CRDTText()
    crdt1.insert('a')
    crdt1.insert('b')
    
    crdt2 = CRDTText()
    crdt2.insert('c')
    crdt2.insert('d')
    
    crdt1.merge(crdt2)
    # Nodes should be sorted by timestamp (insertion order)
    assert crdt1.to_string() in ['abcd', 'acbd', 'acdb', 'cabd', 'cadb', 'cdab']

def test_merge_with_gaps():
    crdt1 = CRDTText()
    crdt1.insert('x')
    
    crdt2 = CRDTText()
    crdt2.insert('y')
    crdt2.insert('z')
    
    crdt1.merge(crdt2)
    assert len(crdt1.nodes) == 3
    assert crdt1.to_string() in ['xyz', 'xzy', 'yxz', 'yzx', 'zxy', 'zyx']

def test_empty_crdt():
    crdt = CRDTText()
    assert crdt.to_string() == ''

def test_single_character():
    crdt = CRDTText()
    crdt.insert('hello')
    assert crdt.to_string() == 'hello'

def test_multiple_inserts_and_deletes():
    crdt = CRDTText()
    for char in 'abcde':
        crdt.insert(char)
    crdt.delete(2)  # Remove 'c'
    crdt.insert('X', 1)
    assert crdt.to_string() == 'aXbde'
