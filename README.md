# DDSS - Dawood Data Science Society Members & Volunteer Registration System

**Department of Data Science**  
**Dawood University of Engineering and Technology (DUET), Karachi**  
*“Inspire - Analyze - Innovate”*

---

## 📌 Project Overview
**DDSS** is an enterprise-grade university registration and management platform built specifically for the **Department of Data Science at DUET**. It provides an end-to-end workflow for:
1. **Student Registration**: DUET Data Science students can register as **Event Volunteers (Form 1)** or **Event Attendees (Form 2)**.
2. **Executive Cabinet Operations**: 9 executive cabinet members process applications in **First-In, First-Out (FIFO) queue order**, mark attendance, assign tasks, and export reports.
3. **Administrative Control**: Full system authority, dynamic form scheduling, file-based record management, allowed roll-number uploads, audit logging, and **LIFO Stack Undo**.
4. **Data Structures & Algorithms (DSA) Practical Implementation**: Handcrafted implementations of **Singly Linked Lists**, **Sorted Arrays**, **Queues**, **Stacks**, **Member Participation History Linked Lists**, **Linear & Binary Search**, and **Bubble, Insertion, Merge, & Quick Sorts**.

---

## 🏗️ Architecture & Technology Stack
- **Language**: Python 3.10+
- **Backend API**: **FastAPI** (run via Uvicorn) on `http://127.0.0.1:8000`
  - Swagger UI Documentation: `http://127.0.0.1:8000/docs`
  - Encapsulates all business logic, DSA data structures, PBKDF2 password hashing, session tokens, and input validations.
- **Frontend Web UI**: **Streamlit** on `http://127.0.0.1:8501`
  - Pure presentation layer communicating exclusively via HTTP `requests`.
  - Responsive theme with DUET Navy (`#1A365D`) and White styling, dual logos (DUET left, DDSS right, title center) on every view and sidebar.
- **Data Storage**:
  - `records.xlsx`: OpenPyXL-managed master workbook with `Members`, `Volunteers`,
    `Attendees`, `Events`, `Forms` (registration forms), `Registrations`,
    `Assignments` (volunteer assignments), `Attendance`, `Cabinet` (cabinet
    accounts), `Queue`, and `Participation History` sheets protected by
    concurrency threading locks. Queue and participation sheets are derived
    reports rebuilt from the authoritative registration and attendance sheets.
  - `activity_log.txt`: Audit log recording every login, logout, submission, status change, and undo.
  - `allowed_roll_numbers.csv`: Enrolled student roll-number list.
  - `uploads/`: Secure directory storing student ID card pictures.

---

## ⚙️ Installation & Setup

### Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14 installed.

### 1. Clone or Open Workspace
```bash
cd h:\ddss_project
```

### 2. Create Virtual Environment & Install Requirements
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

---

## 🚀 How to Run the Application

### Deploy the Vercel Frontend

The production frontend is a static HTML/CSS/JavaScript app in [`web/`](web/). Deploy it as a separate Vercel project while keeping the FastAPI project and [`api/index.py`](api/index.py) unchanged:

1. In Vercel, import the same GitHub repository: `Alishan-890/ddss-project`.
2. Set **Root Directory** to `web`.
3. Set **Framework Preset** to **Other**.
4. Leave **Build Command** blank.
5. Leave **Output Directory** blank/default.
6. Deploy.

The frontend calls `https://ddss-project-etdk.vercel.app`. The backend accepts Vercel frontend origins through its `ALLOWED_ORIGINS` environment configuration and Vercel-origin CORS pattern.

### File Storage and Vercel Production Configuration

The application is completely file-based. `records.xlsx` is the authoritative workbook for structured application data, `allowed_roll_numbers.csv` is the authoritative roll-number allowlist, `activity_log.txt` contains audit/activity entries, and `uploads/` contains private ID-card images. JSON is reserved for appropriate temporary state or exports and is not used as a second authoritative database.

For local development, these files are stored under the repository root and remain fully file-based. Vercel serverless filesystem storage is temporary: new Excel, CSV, JSON, TXT, and uploaded-file changes made directly to the runtime filesystem may be lost after a deployment, restart, or serverless instance replacement.

For persistent Vercel runtime writes without introducing a database, connect a private Vercel Blob store to the **backend** Vercel project and configure one of these supported credential modes:

1. **Connected Vercel Blob store (recommended):** connect the store to the backend project and provide `BLOB_STORE_ID` together with the Vercel OIDC integration credentials.
2. **Backend-only token:** set `BLOB_READ_WRITE_TOKEN` (or the equivalent `VERCEL_BLOB_READ_WRITE_TOKEN`) in the backend project's Environment Variables for the required environments.

Do not put Blob credentials in `web/`, browser JavaScript, Git, or public documentation. The backend uses private Blob objects for `records.xlsx`, `allowed_roll_numbers.csv`, `activity_log.txt`, and uploaded ID-card images. It seeds a missing object from the repository baseline only when a write operation requires it, then updates the object after a validated local mutation. The backend returns a structured HTTP 503 storage error when persistent storage is unavailable or a runtime write fails.

Blob persistence does not change the authoritative file formats: the workbook remains Excel, the allowlist remains CSV, the audit trail remains TXT, and ID cards remain files under the logical `uploads/` prefix. Vercel's local filesystem warning still applies to any runtime file that is not backed by Blob, and no Vercel filesystem write is claimed to be permanent.

Authorized administrators can download the Excel records workbook, activity log, and secure ID-card archive. The backend and frontend retain the existing domains and deployment arrangement; the static frontend remains a separate Vercel project rooted at `web` with Framework Preset `Other`, a blank/default Build Command, and a blank/default Output Directory.

### Option A: One-Click Launcher (Starts Backend + Frontend Together)
Run the automated runner script:
```bash
python run_all.py
```
*Or simply double-click `run_all.bat` on Windows.*

### Option B: Running in Two Separate Terminals
If you prefer running services independently:

#### Terminal 1 — Backend (FastAPI on Port 8000)
```bash
# In h:\ddss_project with virtualenv activated:
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Terminal 2 — Frontend (Streamlit on Port 8501)
```bash
# In h:\ddss_project with virtualenv activated:
streamlit run frontend/app.py --server.port 8501
```

Once started, open your browser:
- 🌐 **Web Application Portal**: [http://127.0.0.1:8501](http://127.0.0.1:8501)
- ⚙️ **Backend API Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🎓 Test Data & Allowed Roll Numbers

Only enrolled students from the **Department of Data Science** matching regex `^\d{2}F-DS-\d{2,3}$` and listed in `allowed_roll_numbers.csv` may submit registration forms.

### Valid Test Roll Numbers:
- `25F-DS-052`
- `25F-DS-076`
- `25F-DS-085`
- `25F-DS-087`
- `25F-DS-093`
- `25F-DS-001` through `25F-DS-025`

### Pre-loaded Sample Data:
- **10 Registered Members**: In `records.xlsx` under `Members` sheet.
- **5 Events**: `EVT-001` through `EVT-005` (Bootcamp, AI Summit, Kaggle Hackathon, Career Clinic, Masterclass).
- **3 Forms**: 
  - `FORM-001` (Volunteer Form for Bootcamp — **OPEN**)
  - `FORM-002` (Attendee Form for AI Summit — **OPEN**)
  - `FORM-003` (Attendee Form for Masterclass — **CLOSED**)
- **5 Sample Volunteers**: In `Volunteers` sheet with pre-populated dummy ID cards.

---

## 🌟 Key Features

### 1. Public Student Portal
- Dynamic form selector showing event titles, form types, and descriptions.
- **Real-Time Availability Engine**: Checks manual open/close toggles, datetime deadlines (`open_time` & `close_time`), and maximum seat capacities. Displays clear badges (`OPEN`, `CLOSED`, `REGISTRATIONS FULL`).
- **Client & Server-side Validation**:
  - Name: Letters and spaces only, 3 to 60 characters.
  - Roll Number: Format validation, allowed-list check, and **duplicate submission prevention**.
  - Pakistani Mobile Number: Format like `03XXXXXXXXX` or `+923XXXXXXXXX`.
  - ID Card Image: Mandatory, maximum size 500 KB (512,000 bytes), verified as a real image via Pillow.
- **Submission Confirmation**: Generates a unique tracking reference number (e.g. `VOL-20261024-XXXX`).

### 2. Handcrafted Data Structures & Algorithms
- **Singly Linked List (`SinglyLinkedList`)**: Manages member and volunteer records. Supports `insert_at_end`, `delete_by_id`, `update`, `traverse`, and `find_by_id`.
- **Date-Sorted Array (`EventScheduleArray`)**: Keeps events and forms ordered by date. Supports `append`, `index_access`, and `binary_search_by_date`.
- **FIFO Queue (`Queue`)**: Form submissions wait in exact arrival order for cabinet/admin approval.
- **LIFO Stack (`Stack`)**: Supports **Undo last action** for additions, edits, deletions, and status reviews.
- **Member Linked List (`MemberParticipationHistory`)**: Tracks full event attendance history per member.
- **Searching**:
  - **Linear Search**: Case-insensitive partial/full matching. Displays comparison count.
  - **Binary Search**: $O(\log n)$ logarithmic search on sorted fields. Displays comparison count.
- **Sorting**:
  - **Bubble Sort & Insertion Sort**: $O(n^2)$ elementary sorts.
  - **Merge Sort & Quick Sort**: $O(n \log n)$ divide-and-conquer sorts.
  - Real-time performance clocking showing elapsed seconds.

### 3. Administrator Dashboard
- **Analytics & Graphs**: Real-time KPI metric cards and breakdown charts for registrations, attendance, and member counts.
- **Form Management**: Create forms, set dates and seat caps, toggle open/close with one click, or delete forms.
- **Master Data Management**: Live searching and sorting on all 9 sheets. Inspect student ID card photos privately.
- **Executive Cabinet Management**: Add positions, edit member names and titles, deactivate accounts, or reset passwords.
- **Allowed Roll Numbers Upload**: Upload fresh CSV files to update enrolled Data Science student roll numbers.
- **LIFO Stack Undo**: Revert accidental deletions, edits, or status changes with one click.
- **Audit & Export Center**: Inspect `activity_log.txt` live; download `records.xlsx`, `ddss_id_cards.zip`, and audit logs.

### 4. Executive Cabinet Dashboard
- **Personalized Greeting**: Displays the executive's name, title, and portfolio.
- **FIFO Queue Processor**: Review pending submissions with student ID card photos in arrival order.
- **Mark Event Attendance**: Record student attendance as Present/Absent for society events.
- **Task Assignments**: Assign duties (registration desk, ushering, stage management) to approved volunteers.
- **Export Reports**: Generate event CSV or Excel attendance summaries.
- **Strict Role Security**: Cabinet members are blocked ($403\text{ Forbidden}$) from deleting data, altering form open/close schedules, or modifying user accounts.

---

## 🧪 Automated Test Suite

A complete test suite is provided in `tests/test_dsa.py` testing all custom data structures, sorting, searching, and API security edge cases.

To execute tests:
```bash
# In project root with .venv activated:
pytest tests/test_dsa.py -v
```

### Verified Test Cases:
1. `test_singly_linked_list`: Insert, update, delete, traverse, find operations.
2. `test_member_participation_history`: Member event node linking and traversal.
3. `test_event_schedule_array`: Date-sorted insertion and binary search.
4. `test_fifo_queue`: Enqueue, dequeue, peek, size, FIFO order verification.
5. `test_lifo_stack`: Push, pop, peek, size, LIFO order verification.
6. `test_searching_algorithms`: Linear search and binary search comparison counts.
7. `test_sorting_algorithms`: Bubble, Insertion, Merge, and Quick sort verification.
8. `test_api_form_closed`: Rejection of submissions to closed forms.
9. `test_api_file_larger_than_500kb`: Rejection of images exceeding 500 KB.
10. `test_api_wrong_file_type`: Rejection of corrupted files and non-image extensions.
11. `test_api_invalid_roll_number`: Rejection of invalid syntax and unauthorized students.
12. `test_api_duplicate_submission`: Rejection of repeat submissions to the same form.
13. `test_cabinet_trying_admin_only_action`: Enforces $403\text{ Forbidden}$ when cabinet members attempt admin routes.

---

## 🌐 Production Deployment

The production setup uses two separate services:

- **Render Web Service** runs `backend.main:app`.
- **Streamlit Community Cloud** runs `frontend/app.py`.

`run_all.py` and `run_all.bat` remain local-development launchers only. Production
platforms provide one web process/port per service, so they must not be used as
the Render start command.

### A. Create and push the GitHub repository

From the project root, create a new empty GitHub repository and run:

```bash
git init
git add .
git commit -m "Prepare DDSS project for deployment"
git branch -M main
git remote add origin REPOSITORY_URL
git push -u origin main
```

Do not commit `.streamlit/secrets.toml`, `.env`, or other secret files.

### B. Deploy the backend on Render

1. Open Render and choose **New → Web Service**.
2. Connect the GitHub repository and select the `main` branch.
3. Use the repository root as the service root.
4. Select **Python** (the checked-in `render.yaml` can also configure this service).
5. Confirm the build command is `pip install -r requirements.txt`.
6. Confirm the start command is:

   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port $PORT
   ```

7. Deploy the service and wait for the first successful build.

### C. Obtain the Render backend URL

Copy the URL shown by Render, for example
`https://PROJECT-NAME.onrender.com`. Do not replace it with a made-up URL.

### D. Configure backend CORS on Render

In the Render service's **Environment** settings, add:

```text
ALLOWED_ORIGINS=https://APP-NAME.streamlit.app
```

Multiple origins are supported as a comma-separated value:

```text
ALLOWED_ORIGINS=https://APP-NAME.streamlit.app,https://www.example.com
```

The backend always retains `http://localhost:8501` and
`http://127.0.0.1:8501` for local development. Credentials, methods, and headers
are enabled for the configured origins; wildcard production CORS is not used.

### E. Deploy the frontend on Streamlit Community Cloud

1. Open Streamlit Community Cloud and choose **Deploy an app**.
2. Select the GitHub repository and the `main` branch.
3. Set **Main file path** to `frontend/app.py`.
4. Deploy the app using the repository root as its working directory.

### F. Set Streamlit Secrets

In the deployed Streamlit app's **Settings → Secrets**, add the real Render URL:

```toml
BACKEND_URL = "https://PROJECT-NAME.onrender.com"
```

The repository includes [.streamlit/secrets.toml.example](.streamlit/secrets.toml.example)
as a template. Never commit the real `.streamlit/secrets.toml`.
The frontend resolves the URL in this order: `st.secrets["BACKEND_URL"]`,
the `BACKEND_URL` environment variable, then `http://127.0.0.1:8000` locally.

### G. Test the final frontend URL

Open the deployed Streamlit URL and verify the public forms load. Then test a
registration with an allowed roll number and, separately, an administrator login.

### H. Test backend health and documentation

After replacing `PROJECT-NAME` with the actual Render service name, open:

```text
https://PROJECT-NAME.onrender.com/
https://PROJECT-NAME.onrender.com/health
https://PROJECT-NAME.onrender.com/docs
```

The root response is `{"status":"online","message":"DDSS API is running"}` and
the health response is `{"status":"healthy"}`.

### I. Automatic deployments after GitHub pushes

Render and Streamlit Community Cloud can both be connected to the same GitHub
repository and `main` branch with automatic deployments enabled. Every new
commit pushed to `main` triggers a rebuild/redeploy of the corresponding
service. Check each provider's deploy logs if a build fails.

### Expected production URL format

```text
Backend:        https://PROJECT-NAME.onrender.com
Backend docs:   https://PROJECT-NAME.onrender.com/docs
Backend health: https://PROJECT-NAME.onrender.com/health
Frontend:       https://APP-NAME.streamlit.app
```

## 💾 Storage and persistence limitation

The existing file-based storage behavior is intentionally preserved:
`records.xlsx`, `allowed_roll_numbers.csv`, `uploads/`, and `activity_log.txt`
are resolved from the project root with `pathlib.Path`. This keeps local
development and the current Excel/CSV workflow working.

Render and Streamlit Community Cloud instances do not provide reliable
permanent local storage. Data written at runtime can be lost on restart,
redeploy, service migration, or autoscaling; this includes new workbook rows,
uploaded ID cards, updated allowed-roll CSV data, and activity-log entries.
The files committed to GitHub are only the deployment baseline and are not a
multi-user production database. This project intentionally remains completely file-based and does not use an
external database. On Vercel, serverless filesystem writes are temporary and
may be lost after a deployment, restart, or serverless instance replacement.
Use the authorized Excel, CSV, JSON, activity-log, and ID-card archive download
endpoints to create backups before runtime storage is replaced.
#   c o m m u n i f  
 