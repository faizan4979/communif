"""
Data Structures and Algorithms (DSA) Module for DDSS.
Handcrafted data structures and algorithms without built-in queue/deque/stack or list.sort().
"""

import time
from typing import Any, List, Optional, Tuple, Callable


# ============================================================================
# Singly Linked List
# ============================================================================

class Node:
    """A node in a singly linked list."""
    def __init__(self, data: Any, next_node: Optional['Node'] = None):
        self.data = data
        self.next = next_node


class SinglyLinkedList:
    """
    Singly Linked List for managing Member and Volunteer records.
    Supports insert at end, delete by ID, update, traverse, and find by ID.
    """
    def __init__(self):
        self.head: Optional[Node] = None
        self._size: int = 0

    # Time Complexity: O(n)
    def insert_at_end(self, data: Any) -> None:
        """Appends a new node with data to the end of the linked list."""
        new_node = Node(data)
        if self.head is None:
            self.head = new_node
        else:
            curr = self.head
            while curr.next is not None:
                curr = curr.next
            curr.next = new_node
        self._size += 1

    # Time Complexity: O(n)
    def find_by_id(self, target_id: Any, id_key: str = "id") -> Optional[Any]:
        """Finds an element by matching an ID key in data."""
        curr = self.head
        while curr is not None:
            item = curr.data
            val = item.get(id_key) if isinstance(item, dict) else getattr(item, id_key, None)
            if str(val).strip().lower() == str(target_id).strip().lower():
                return item
            curr = curr.next
        return None

    # Time Complexity: O(n)
    def delete_by_id(self, target_id: Any, id_key: str = "id") -> bool:
        """Deletes the node whose data matches target_id. Returns True if deleted."""
        curr = self.head
        prev = None
        while curr is not None:
            item = curr.data
            val = item.get(id_key) if isinstance(item, dict) else getattr(item, id_key, None)
            if str(val).strip().lower() == str(target_id).strip().lower():
                if prev is None:
                    self.head = curr.next
                else:
                    prev.next = curr.next
                self._size -= 1
                return True
            prev = curr
            curr = curr.next
        return False

    # Time Complexity: O(n)
    def update(self, target_id: Any, new_data: Any, id_key: str = "id") -> bool:
        """Updates the data of the node matching target_id."""
        curr = self.head
        while curr is not None:
            item = curr.data
            val = item.get(id_key) if isinstance(item, dict) else getattr(item, id_key, None)
            if str(val).strip().lower() == str(target_id).strip().lower():
                curr.data = new_data
                return True
            curr = curr.next
        return False

    # Time Complexity: O(n)
    def traverse(self) -> List[Any]:
        """Returns a Python list copy of all elements in the linked list."""
        elements = []
        curr = self.head
        while curr is not None:
            elements.append(curr.data)
            curr = curr.next
        return elements

    def __len__(self) -> int:
        return self._size

    def clear(self) -> None:
        self.head = None
        self._size = 0


# ============================================================================
# Linked List Per Member (Participation History)
# ============================================================================

class ParticipationNode:
    """Node representing a single event in a member's participation history."""
    def __init__(self, event_data: dict, next_node: Optional['ParticipationNode'] = None):
        self.event_data = event_data
        self.next = next_node


class MemberParticipationHistory:
    """
    Linked list dedicated to tracking participation history for a single member.
    """
    def __init__(self, roll_no: str):
        self.roll_no = roll_no
        self.head: Optional[ParticipationNode] = None
        self._count = 0

    # Time Complexity: O(n)
    def add_event(self, event_data: dict) -> None:
        """Adds an event to the end of the member's history list."""
        new_node = ParticipationNode(event_data)
        if self.head is None:
            self.head = new_node
        else:
            curr = self.head
            while curr.next is not None:
                curr = curr.next
            curr.next = new_node
        self._count += 1

    # Time Complexity: O(n)
    def traverse(self) -> List[dict]:
        """Returns the list of all participation records."""
        result = []
        curr = self.head
        while curr is not None:
            result.append(curr.event_data)
            curr = curr.next
        return result

    def __len__(self) -> int:
        return self._count


# ============================================================================
# Array (Python list used as an array) for Event Schedule
# ============================================================================

class EventScheduleArray:
    """
    Array structure for event and form schedule kept sorted by date.
    Operations: append, index access, binary search.
    """
    def __init__(self):
        self._data: List[dict] = []

    # Time Complexity: O(n) insertion to maintain sorted order
    def append(self, item: dict, date_key: str = "date") -> None:
        """
        Inserts item while keeping array sorted by date_key.
        """
        item_val = str(item.get(date_key, ""))
        idx = 0
        while idx < len(self._data) and str(self._data[idx].get(date_key, "")) <= item_val:
            idx += 1
        self._data.insert(idx, item)

    # Time Complexity: O(1)
    def index_access(self, idx: int) -> Optional[dict]:
        """Access item at a 0-based index."""
        if 0 <= idx < len(self._data):
            return self._data[idx]
        return None

    # Time Complexity: O(log n)
    def binary_search_by_date(self, target_date: str, date_key: str = "date") -> Tuple[Optional[dict], int]:
        """
        Performs binary search on the date-sorted array.
        Returns (item_or_none, comparisons_count).
        """
        target = str(target_date).strip()
        low = 0
        high = len(self._data) - 1
        comparisons = 0

        while low <= high:
            mid = (low + high) // 2
            comparisons += 1
            mid_val = str(self._data[mid].get(date_key, "")).strip()
            if mid_val == target:
                return self._data[mid], comparisons
            elif mid_val < target:
                low = mid + 1
            else:
                high = mid - 1

        return None, comparisons

    def get_all(self) -> List[dict]:
        return list(self._data)

    def set_all(self, items: List[dict], date_key: str = "date") -> None:
        self._data = []
        for it in items:
            self.append(it, date_key=date_key)

    def __len__(self) -> int:
        return len(self._data)


# ============================================================================
# Queue (FIFO) - Handcrafted
# ============================================================================

class QueueNode:
    """A node inside the FIFO Queue."""
    def __init__(self, data: Any):
        self.data = data
        self.next: Optional['QueueNode'] = None


class Queue:
    """
    FIFO Queue for form submissions waiting for approval, processed in arrival order.
    No collections.deque or built-in queue module used.
    Operations: enqueue, dequeue, peek, is_empty, size.
    """
    def __init__(self):
        self._front: Optional[QueueNode] = None
        self._rear: Optional[QueueNode] = None
        self._count: int = 0

    # Time Complexity: O(1)
    def enqueue(self, item: Any) -> None:
        """Adds an item to the rear of the queue."""
        new_node = QueueNode(item)
        if self._rear is None:
            self._front = self._rear = new_node
        else:
            self._rear.next = new_node
            self._rear = new_node
        self._count += 1

    # Time Complexity: O(1)
    def dequeue(self) -> Optional[Any]:
        """Removes and returns the item at the front of the queue."""
        if self.is_empty():
            return None
        removed_data = self._front.data
        self._front = self._front.next
        if self._front is None:
            self._rear = None
        self._count -= 1
        return removed_data

    # Time Complexity: O(1)
    def peek(self) -> Optional[Any]:
        """Returns the item at the front without removing it."""
        if self.is_empty():
            return None
        return self._front.data

    # Time Complexity: O(1)
    def is_empty(self) -> bool:
        """Returns True if queue is empty."""
        return self._front is None

    # Time Complexity: O(1)
    def size(self) -> int:
        """Returns the number of elements in the queue."""
        return self._count

    def to_list(self) -> List[Any]:
        """Traverses the queue without modifying it and returns all items."""
        result = []
        curr = self._front
        while curr is not None:
            result.append(curr.data)
            curr = curr.next
        return result

    def remove_by_id(self, target_id: Any, id_key: str = "submission_id") -> bool:
        """Helper to remove a specific item if approved/rejected directly."""
        curr = self._front
        prev = None
        while curr is not None:
            item = curr.data
            val = item.get(id_key) if isinstance(item, dict) else getattr(item, id_key, None)
            if str(val).strip().lower() == str(target_id).strip().lower():
                if prev is None:
                    self._front = curr.next
                    if self._front is None:
                        self._rear = None
                else:
                    prev.next = curr.next
                    if curr == self._rear:
                        self._rear = prev
                self._count -= 1
                return True
            prev = curr
            curr = curr.next
        return False


# ============================================================================
# Stack (LIFO) - Handcrafted
# ============================================================================

class StackNode:
    """A node inside the LIFO Stack."""
    def __init__(self, data: Any, next_node: Optional['StackNode'] = None):
        self.data = data
        self.next = next_node


class Stack:
    """
    LIFO Stack for Undo last action (add, update, delete).
    No built-in stack modules used.
    Operations: push, pop, peek, is_empty, size.
    """
    def __init__(self):
        self._top: Optional[StackNode] = None
        self._count: int = 0

    # Time Complexity: O(1)
    def push(self, item: Any) -> None:
        """Pushes an action onto the top of the stack."""
        new_node = StackNode(item, self._top)
        self._top = new_node
        self._count += 1

    # Time Complexity: O(1)
    def pop(self) -> Optional[Any]:
        """Pops and returns the action from the top of the stack."""
        if self.is_empty():
            return None
        popped_data = self._top.data
        self._top = self._top.next
        self._count -= 1
        return popped_data

    # Time Complexity: O(1)
    def peek(self) -> Optional[Any]:
        """Returns the top item without removing it."""
        if self.is_empty():
            return None
        return self._top.data

    # Time Complexity: O(1)
    def is_empty(self) -> bool:
        """Returns True if the stack has no items."""
        return self._top is None

    # Time Complexity: O(1)
    def size(self) -> int:
        """Returns current stack depth."""
        return self._count

    def to_list(self) -> List[Any]:
        """Returns all stack items from top to bottom."""
        result = []
        curr = self._top
        while curr is not None:
            result.append(curr.data)
            curr = curr.next
        return result


# ============================================================================
# Search Algorithms
# ============================================================================

# Time Complexity: O(n)
def linear_search(
    items: List[dict],
    key: str,
    query: str,
    partial: bool = True
) -> Tuple[List[dict], int]:
    """
    Performs a linear search over a list of dictionaries by key.
    Supports exact or case-insensitive partial match.
    Returns (matches, comparisons_count).
    """
    matches = []
    comparisons = 0
    q = query.strip().lower()

    for item in items:
        comparisons += 1
        val = str(item.get(key, "")).strip().lower()
        if partial:
            if q in val:
                matches.append(item)
        else:
            if q == val:
                matches.append(item)

    return matches, comparisons


# Time Complexity: O(log n)
def binary_search(
    items: List[dict],
    key: str,
    target_val: str
) -> Tuple[Optional[dict], int]:
    """
    Performs binary search on a sorted list of dictionaries.
    Assumes items are sorted by key in ascending order.
    Returns (matched_item_or_none, comparisons_count).
    """
    low = 0
    high = len(items) - 1
    comparisons = 0
    target = target_val.strip().lower()

    while low <= high:
        mid = (low + high) // 2
        comparisons += 1
        mid_val = str(items[mid].get(key, "")).strip().lower()

        if mid_val == target:
            return items[mid], comparisons
        elif mid_val < target:
            low = mid + 1
        else:
            high = mid - 1

    return None, comparisons


# ============================================================================
# Helper comparison function for sorting
# ============================================================================

def _compare(a_val: Any, b_val: Any) -> int:
    """Helper comparison: returns -1 if a < b, 0 if a == b, 1 if a > b."""
    a_str = str(a_val if a_val is not None else "").strip().lower()
    b_str = str(b_val if b_val is not None else "").strip().lower()
    if a_str < b_str:
        return -1
    elif a_str > b_str:
        return 1
    return 0


# ============================================================================
# Sorting Algorithms
# ============================================================================

# Time Complexity: O(n^2)
def bubble_sort(
    items: List[dict],
    key: str,
    reverse: bool = False
) -> Tuple[List[dict], float]:
    """
    Sorts a list of dictionaries in-place (on a copy) using Bubble Sort.
    Returns (sorted_items, elapsed_time_seconds).
    """
    start_time = time.perf_counter()
    arr = list(items)
    n = len(arr)

    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            cmp = _compare(arr[j].get(key), arr[j + 1].get(key))
            should_swap = (cmp > 0) if not reverse else (cmp < 0)
            if should_swap:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break

    elapsed = time.perf_counter() - start_time
    return arr, elapsed


# Time Complexity: O(n^2)
def insertion_sort(
    items: List[dict],
    key: str,
    reverse: bool = False
) -> Tuple[List[dict], float]:
    """
    Sorts a list of dictionaries using Insertion Sort.
    Returns (sorted_items, elapsed_time_seconds).
    """
    start_time = time.perf_counter()
    arr = list(items)
    n = len(arr)

    for i in range(1, n):
        key_item = arr[i]
        j = i - 1
        while j >= 0:
            cmp = _compare(arr[j].get(key), key_item.get(key))
            condition = (cmp > 0) if not reverse else (cmp < 0)
            if condition:
                arr[j + 1] = arr[j]
                j -= 1
            else:
                break
        arr[j + 1] = key_item

    elapsed = time.perf_counter() - start_time
    return arr, elapsed


# Time Complexity: O(n log n)
def merge_sort(
    items: List[dict],
    key: str,
    reverse: bool = False
) -> Tuple[List[dict], float]:
    """
    Sorts a list of dictionaries using Merge Sort (divide-and-conquer).
    Returns (sorted_items, elapsed_time_seconds).
    """
    start_time = time.perf_counter()

    def _merge(left: List[dict], right: List[dict]) -> List[dict]:
        merged = []
        i = j = 0
        while i < len(left) and j < len(right):
            cmp = _compare(left[i].get(key), right[j].get(key))
            condition = (cmp <= 0) if not reverse else (cmp >= 0)
            if condition:
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
        while i < len(left):
            merged.append(left[i])
            i += 1
        while j < len(right):
            merged.append(right[j])
            j += 1
        return merged

    def _sort(arr: List[dict]) -> List[dict]:
        if len(arr) <= 1:
            return arr
        mid = len(arr) // 2
        left = _sort(arr[:mid])
        right = _sort(arr[mid:])
        return _merge(left, right)

    sorted_arr = _sort(list(items))
    elapsed = time.perf_counter() - start_time
    return sorted_arr, elapsed


# Time Complexity: O(n log n) average, O(n^2) worst case
def quick_sort(
    items: List[dict],
    key: str,
    reverse: bool = False
) -> Tuple[List[dict], float]:
    """
    Sorts a list of dictionaries using Quick Sort.
    Returns (sorted_items, elapsed_time_seconds).
    """
    start_time = time.perf_counter()

    def _qsort(arr: List[dict]) -> List[dict]:
        if len(arr) <= 1:
            return arr
        pivot = arr[len(arr) // 2]
        left, equal, right = [], [], []

        for item in arr:
            cmp = _compare(item.get(key), pivot.get(key))
            if cmp == 0:
                equal.append(item)
            elif cmp < 0:
                left.append(item)
            else:
                right.append(item)

        if not reverse:
            return _qsort(left) + equal + _qsort(right)
        else:
            return _qsort(right) + equal + _qsort(left)

    sorted_arr = _qsort(list(items))
    elapsed = time.perf_counter() - start_time
    return sorted_arr, elapsed
