# LMT System — Feature Report for Management

**Product:** Lead Management & Training (LMT) Backend  
**Stack:** FastAPI API + PostgreSQL  
**Purpose:** End-to-end management of student/prospect leads, admissions, payments, documents, team performance, and finance (expenses / payment requests).

---

## Cover summary

> LMT is a role-based lead-to-admission platform covering CRM, admission ops, fee payments with verification, document vault, team performance, incentives, and accountant expense/payment-request workflows, with dashboards, reports, exports, and optional Google Sheets sync.

---

## 1. User access & security

- Secure login with JWT access and refresh tokens
- Logout that invalidates old refresh tokens
- Password hashing (bcrypt); reset password for staff and for student/prospect login credentials
- Role-based access control (who can see/edit what)
- Inactive users cannot log in
- Default admin account seeded for first-time setup

### Roles in the system

| Role | Typical use |
|------|-------------|
| Admin | Full control of the system |
| Employee (sales) | Own leads only — create/edit, payments, docs |
| Manager | Own leads + team dashboard for reportees |
| Sales Head | Own leads + team dashboard for reportees |
| Accountant | All leads; payments verify; expenses & payment requests |
| Processing Team | All leads; restricted admission stages; payments add/update |

---

## 2. Lead / prospect management (CRM)

- Create, view, edit, delete leads
- Auto-generated lead IDs (e.g. `PRO00001`)
- Search and filter (name/email/phone, CRM stage, admission stage, course, assignee, dates)
- Assign leads to employees; reassign (admin)
- Lead timeline (activity + payments + documents)
- Student login credentials on lead (ID + password); copy-friendly reset
- Soft privacy: when a lead is **completed**, non-admin users see masked personal details
- Support for web form and file upload in one save (documents + payment receipts)

### Lead data captured

- Personal: name, email, phone, DOB, father/mother name
- Academic: course, specialization, university
- Address and delivery address/date
- Deal value, notes, source, follow-up date
- Exam flags: exam attended, exam certified

### CRM pipeline stages

`new` → `contacted` → `follow_up` → `interested` → `negotiation` → `won` / `lost`

---

## 3. Admission funnel (operations)

Separate from CRM sales stage — tracks academic/ops progress:

`registered` → `fifty_percent_paid` → `exam_attended` → `waiting_for_100_percent_payment` → `certificate_waiting` → `waiting_result` → `result_announced` → `completed` → `delivered`

- Manual stage updates from list/details (role-gated)
- Auto-advance rules (never moves backward):
  - ~50%+ of deal value paid → `fifty_percent_paid`
  - Exam marked attended → `exam_attended`
- Who can set what:
  - Sales + accountant: normal stages (accountant **cannot** set `completed`)
  - Processing team / admin: restricted stages (`waiting_result`, `result_announced`, `delivered`)
  - Admin / sales: `completed`

---

## 4. Payments (student fees)

- Add / update / delete payments on a lead (from edit page or list “more actions”)
- Receipt upload per payment
- Payment summary / KPIs (by type, status, date range)
- Auto IDs (`PAY00001` …)

### Payment types

Advance, Installment, Full Payment, Registration Fee, Before Exam Fee, After Result Fee

### Payment methods

Cash, UPI, Card, Bank transfer, Cheque

### Statuses

Pending, Completed, Failed

### Verification workflow (Accountant / Admin)

Each payment can be marked: Verified / Not verified / Not credited (with auditor recorded).

Accountant and Processing team can add/update payments; verification is Admin + Accountant.

---

## 5. Documents

- Upload multiple files per document type (e.g. Aadhaar front+back; degree marks + provisional + certificate)
- Types: Aadhaar, SSLC, Plus Two, Degree, Agreement, Passport, Photo, Receipt, Other
- List / update / delete documents per lead
- Auto IDs (`DOC00001` …)
- Stored locally or on S3/Cloudflare R2

---

## 6. Finance — Expenses

(Accountant + Admin; delete = Admin only)

- Track office / incentive expenses
- Fields: date, description, amount, paid to, transaction ID, installment number
- Upload receipt and invoice
- Actor tracking: who created, who requested, who approved, who verified
- Linked to payment requests when auto-created after verification

---

## 7. Finance — Payment requests

Workflow for accountants to request company payouts:

1. Accountant creates request  
2. Admin fulfills with transaction ID, receipt, and date  
3. Accountant verifies from statement  
4. System auto-creates an Expense  

- Statuses: `requested` → `payment_done` → `approved`
- Request fields: description, account/UPI details, amount, installment number
- Admin fulfill: transaction ID, payment date, receipt
- On verify: expense is created automatically
- All accountants and admins can view all requests; actors (requester / approver / verifier) are recorded
- Types: office / incentive (incentive can link to employee)

---

## 8. Masters & configuration

- **Courses** — CRUD + CSV/XLSX import (admin); list for all logged-in users
- **Specializations** — dropdown master + import (admin); free text stored on lead
- **Incentive slabs** — lead-count bands → fixed incentive amount (e.g. 10–15 leads → ₹500)
- **Sales / monthly targets** — organization default + optional per-employee override

---

## 9. Employees & team structure

- Employee CRUD (admin); list also for accountant
- Roles assignable: employee, accountant, processing team, manager, sales head
- Profile: phone, department, designation, monthly target
- Reporting lines: reports-to manager / sales head
- Activate / deactivate; reset password
- Auto IDs (`EMP00001` …)

### Team module (Admin / Manager / Sales Head)

- View team members under a supervisor
- Assign reporting relationships (admin)
- Team dashboards: overview, sales, performance, payments, analytics
- Team-scoped Excel exports

---

## 10. Dashboards & KPIs

### Employee dashboard

- Lead counts (total / week / month / custom range)
- Payments collected and status breakdown
- Leads by CRM stage and admission stage
- Progress vs monthly sales target
- Incentive slab status
- Exam statistics

### Admin dashboard

- Org-wide KPIs, employee filter
- Revenue, conversion, certificates
- Revenue by month, top performers, per-employee overviews

---

## 11. Reports & exports

### Reports

- Employee / admin filtered reports
- Revenue trends
- Employee performance comparison
- Leads by CRM stage / admission stage
- Incentive eligibility
- Incentive release (booked vs paid vs receivable for completed/delivered admissions)

### Exports

- Leads, employee performance, sales, dashboard
- Formats: Excel (XLSX), CSV, PDF
- Filters: date, employee, stage, source
- Full lead Excel export with documents and payment links

---

## 12. Notifications & audit

- In-app notifications: lead assigned, follow-up reminder, stage changed
- Mark one / all as read
- Admin can trigger follow-up reminders (for due/overdue follow-up dates)
- Activity log: who did what (lead updates, assignments, stage changes, payment verification, sheet sync, etc.)
- Admin sees full log; others see their own

---

## 13. Integrations & platform

- **Google Sheets** (optional): auto-sync leads on create/update; manual sync button; Lead ID–based upsert
- **File storage**: local disk or S3 / Cloudflare R2
- Sequential business IDs across modules (PRO, PAY, DOC, EMP, CRS, SPC, PRQ, EXP)
- PostgreSQL database with versioned schema migrations (Alembic)
- CORS-enabled API for the frontend app

---

## Feature groups at a glance

| # | Group | Highlights |
|---|--------|------------|
| 1 | Access & security | Login, JWT, roles, password reset |
| 2 | CRM leads | Full lead lifecycle, filters, timeline, privacy masking |
| 3 | Admission funnel | Ops stages, auto-advance, role-gated transitions |
| 4 | Student payments | Types, receipts, verification |
| 5 | Documents | Multi-file per type, cloud/local storage |
| 6 | Expenses | Office/incentive tracking with audit actors |
| 7 | Payment requests | Request → admin pay → verify → auto expense |
| 8 | Masters | Courses, specializations, incentives, targets |
| 9 | Employees & team | Staff CRUD, hierarchy, team dashboards |
| 10 | Dashboards | Employee and admin KPIs |
| 11 | Reports & exports | XLSX / CSV / PDF, incentive release |
| 12 | Notifications & audit | Alerts and activity log |
| 13 | Integrations | Google Sheets, S3/R2, sequential IDs |
