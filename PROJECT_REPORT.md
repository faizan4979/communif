# Academic Project Report & Viva Guide: DDSS

**Project Title**: DDSS - Dawood Data Science Society Members & Volunteer Registration System  
**Institution**: Dawood University of Engineering and Technology (DUET), Karachi  
**Department**: Department of Data Science  
**Subject**: Data Structures and Algorithms (DSA) / Web Application Engineering  

---

## 1. Executive Summary & Problem Formulation
The **Dawood Data Science Society (DDSS)** requires a robust, secure, and user-friendly system to manage student membership, event organization, volunteer recruitments, and attendee registrations. In collegiate environments, systems frequently suffer from data corruption due to concurrent submissions, lack of auditability, and poor data organization. 

This project solves these challenges by combining a modern decoupled web architecture (**FastAPI + Streamlit**) with fundamental **Data Structures and Algorithms (DSA)** written by hand to demonstrate the practical application of theoretical computer science concepts.

---

## 2. Data Structure Selection & Design Rationales

In accordance with strict pedagogical requirements, no high-level collection wrappers (such as `collections.deque` or `queue.Queue`) or built-in list sorting (`list.sort()`, `sorted()`) were used for core structures. Each structure was selected to solve a specific domain problem:

| Data Structure | Feature / Purpose | Why Chosen? (Viva Justification) | Core Operations & Complexities |
| :--- | :--- | :--- | :--- |
| **Singly Linked List** (`SinglyLinkedList`) | Member and Volunteer records management | Linked lists provide dynamic memory allocation without requiring contiguous memory blocks. Inserting new members at the end or deleting members by ID does not require shifting elements like an array. It demonstrates fundamental pointer manipulation (`next` pointers). | • Insert at end: $O(n)$<br>• Delete by ID: $O(n)$<br>• Update by ID: $O(n)$<br>• Traverse: $O(n)$<br>• Find by ID: $O(n)$ |
| **Sorted Array** (`EventScheduleArray`) | Chronological Event and Form Schedule | Schedules have a fixed timeline and need fast random access by index ($O(1)$) to display upcoming events. Keeping the array sorted by date upon insertion enables fast **Binary Search** ($O(\log n)$) to quickly find events by date or ID. | • Index Access: $O(1)$<br>• Append in sorted order: $O(n)$<br>• Binary Search: $O(\log n)$ |
| **FIFO Queue** (`Queue`) | Form submissions waiting for review | **Fairness Principle**: Student registrations must be processed strictly in the order they were submitted ("First-Come, First-Served"). A FIFO queue guarantees that earlier applicants are reviewed before later ones. Implemented using linked nodes with `head` and `tail` pointers for constant-time enqueue and dequeue. | • Enqueue: $O(1)$<br>• Dequeue: $O(1)$<br>• Peek: $O(1)$<br>• Is Empty: $O(1)$<br>• Size: $O(1)$ |
| **LIFO Stack** (`Stack`) | Administrative "Undo Last Action" | **Recency Principle**: When an administrator makes a mistake (accidental deletion, wrongful update, or misclassified approval), the most recent action must be the first one reverted ("Last-In, First-Out"). A stack perfectly models this state reversal history. | • Push: $O(1)$<br>• Pop: $O(1)$<br>• Peek: $O(1)$<br>• Is Empty: $O(1)$<br>• Size: $O(1)$ |
| **Linked List per Member** (`MemberParticipationHistory`) | Member Event Participation History | Each society member has a variable number of events they participate in over their university tenure. Allocating a dedicated singly linked list per student avoids fixed-size array waste and allows indefinite append operations of event certificates and attendance records. | • Add Event: $O(n)$<br>• Traverse: $O(n)$ |

---

## 3. Algorithms and Complexity Analysis

### A. Searching Algorithms
1. **Linear Search ($O(n)$)**:
   - **Mechanism**: Sequentially compares the query string against each record from index 0 to $n-1$.
   - **Best Case**: $O(1)$ (target found at the first position).
   - **Worst Case**: $O(n)$ (target is at the very end or absent).
   - **Use Case**: Partial text searching (searching candidate names, department keywords, or roles) where data is unordered. The system outputs the exact number of comparisons performed.
2. **Binary Search ($O(\log n)$)**:
   - **Mechanism**: Operates on an array sorted by the search key. Repeatedly divides the search interval in half by comparing the query to the middle element.
   - **Best Case**: $O(1)$ (target matches the middle element immediately).
   - **Worst Case**: $O(\log_2 n)$ comparisons.
   - **Use Case**: Fast retrieval by exact roll number (e.g. `25F-DS-052`) or ID on pre-sorted data.

### B. Sorting Algorithms
1. **Bubble Sort**:
   - **Time Complexity**: $O(n^2)$ worst and average; $O(n)$ best case with early-termination swap flag.
   - **Space Complexity**: $O(1)$ auxiliary memory (in-place).
   - **Mechanism**: Repeatedly steps through the list, compares adjacent elements, and swaps them if they are in the wrong order.
2. **Insertion Sort**:
   - **Time Complexity**: $O(n^2)$ worst and average; $O(n)$ best case for nearly-sorted data.
   - **Space Complexity**: $O(1)$ auxiliary memory.
   - **Mechanism**: Builds the final sorted list one item at a time by inserting each element into its proper position among already-sorted items.
3. **Merge Sort**:
   - **Time Complexity**: $O(n \log n)$ across all cases (Best, Average, Worst).
   - **Space Complexity**: $O(n)$ auxiliary memory.
   - **Mechanism**: Divide-and-conquer paradigm. Recursively halves the array until base cases of size 1 are reached, then merges the halves in sorted order. Highly stable and predictable.
4. **Quick Sort**:
   - **Time Complexity**: $O(n \log n)$ average case; $O(n^2)$ worst case (e.g. when pivot selection is poor).
   - **Space Complexity**: $O(\log n)$ recursive call stack.
   - **Mechanism**: Selects a pivot element, partitions elements into subarrays less than and greater than the pivot, and recursively sorts the partitions.

---

## 4. System Architecture & Engineering Design

```
+--------------------------------------------------------------+
|                Streamlit Frontend (Port 8501)                |
|  - Student Registration Portal (Public)                      |
|  - Cabinet Executive Dashboard (FIFO Queue, Attendance)      |
|  - Administrator Dashboard (Overview, Form CRUD, Undo Stack) |
+--------------------------------------------------------------+
                              |
                     HTTP REST Requests (JSON)
                              |
+--------------------------------------------------------------+
|                 FastAPI Backend (Port 8000)                  |
|  - Authentication (PBKDF2 HMAC SHA-256 + Salt + Sessions)    |
|  - Handcrafted DSA Engine (backend/dsa.py)                   |
|  - Business Logic & Input Validation (Pillow image checks)   |
|  - Concurrency Lock (threading.Lock)                         |
+--------------------------------------------------------------+
                              |
         +--------------------+--------------------+
         |                                         |
+----------------------+                 +--------------------+
| records.xlsx (Excel) |                 |  File System Logs  |
| 9 Managed Sheets     |                 |  - activity_log.txt|
| OpenPyXL Persistence |                 |  - uploads/        |
+----------------------+                 +--------------------+
```

### Architectural Principles:
1. **Decoupled Client-Server**: Streamlit acts strictly as the display layer. It contains **no business logic** and issues REST API calls to FastAPI via the `requests` library.
2. **Concurrency Protection**: Because multiple students may submit registrations simultaneously, Excel writes in OpenPyXL are safeguarded by a re-entrant `threading.Lock()` (`EXCEL_LOCK`). This eliminates workbook corruption.
3. **Graceful File Lock Handling**: If an administrator has `records.xlsx` open in Microsoft Excel during a write, the system catches `PermissionError` and returns a clean error message rather than crashing the server.
4. **Cryptographic Password Security**: Passwords are never stored in plain text. Passwords are salted using 16-byte random salts and hashed using **PBKDF2 HMAC SHA-256 with 100,000 iterations**.
5. **Continuous Auditability**: `activity_log.txt` records every critical event with standardized timestamps, actor IDs, action verbs, and detail strings.

---

## 5. Limitations & Future Roadmap

### Current Limitations:
1. **File-Based Storage**: While `records.xlsx` provides an accessible, inspectable interface for university professors and evaluators, Excel storage has $O(N)$ row rewrite costs compared to page-buffered relational databases (PostgreSQL/MySQL) when data grows past 100,000 rows.
2. **In-Memory Cache Synchronization**: Multi-instance horizontal scaling would require a shared caching layer (such as Redis) rather than single-process in-memory DSA instances.

### Future Improvements:
1. **Relational Database Migration**: Add an abstraction layer to toggle between Excel mode and PostgreSQL.
2. **QR Code Digital Verification**: Generate dynamic QR codes for approved student passes that cabinet members can scan on mobile devices during event check-in.
3. **Automated Notification Gateway**: Integrate Twilio or WhatsApp Business API to deliver instant reference number SMS confirmations to students' mobile phones.

---

## 6. How to Explain in a Viva (Key Answers)

- **Q: Why didn't you use `list.sort()`?**  
  *A: Built-in `sort()` is Timsort. In this project, we implemented Bubble Sort, Insertion Sort, Merge Sort, and Quick Sort from scratch to demonstrate direct mastery of algorithmic sorting mechanics, space/time trade-offs, and stability.*
- **Q: How does the Undo feature work?**  
  *A: The Undo feature uses a LIFO Stack. Whenever an administrator adds, edits, or deletes an entity, the inverse operation (along with the prior snapshot of the record) is pushed onto the stack. When Undo is clicked, the top action is popped and executed in $O(1)$ time.*
- **Q: How does the system prevent two students from corrupting the Excel file if they submit at the exact same millisecond?**  
  *A: Every Excel write is encapsulated within a Python `threading.Lock()`. If thread B attempts to save while thread A is writing, thread B waits until thread A releases the lock, ensuring atomic writes.*
