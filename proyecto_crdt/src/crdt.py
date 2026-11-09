import uuid

class Node:
    __slots__ = ('id', 'value', 'timestamp', 'is_deleted')
    def __init__(self, id, value, timestamp, is_deleted=False):
        self.id = id
        self.value = value
        self.timestamp = timestamp
        self.is_deleted = is_deleted

    def __repr__(self):
        return f"Node(id={self.id}, value='{self.value}', timestamp={self.timestamp}, deleted={self.is_deleted})"

class CRDTText:
    _clock = 0  # Lamport clock

    def __init__(self):
        self.nodes = []  # list of Node objects

    def _increment_clock(self):
        self._clock += 1
        return self._clock, uuid.uuid4()

    def insert(self, value, position=None):
        timestamp, node_id = self._increment_clock()
        node = Node(node_id, value, timestamp)
        if position is None:
            self.nodes.append(node)
        else:
            if 0 <= position <= len(self.nodes):
                self.nodes.insert(position, node)
            # else ignore out-of-range position

    def delete(self, position):
        if 0 <= position < len(self.nodes):
            self.nodes.pop(position)

    def merge(self, other):
        # Combine nodes from both CRDTs and sort by (timestamp, id)
        combined = self.nodes + other.nodes
        combined.sort(key=lambda n: (n.timestamp, n.id))
        self.nodes = combined

    def to_string(self):
        return ''.join(node.value for node in self.nodes if not node.is_deleted)
