# GOOGLE sheet
1. Create a Google Cloud project
Go to Google Cloud Console
Sign in with your Google account
Click the project dropdown (top bar) → New Project
Name it (e.g. lmt-backend) → Create
2. Enable the Google Sheets API
In that project, open APIs & Services → Library
Search for Google Sheets API
Open it → Enable
3. Create a service account (for the JSON credentials)
Go to APIs & Services → Credentials
Create credentials → Service account
Name it (e.g. lmt-sheets) → Create and continue
Role: optional for this use case (you can skip or use Editor) → Done
Click the new service account → Keys tab
Add key → Create new key → JSON → Create
A JSON file downloads — that is your credential file
What to put in .env:

Variable	Value
GOOGLE_SERVICE_ACCOUNT_FILE
Path to that file, e.g. app/credentials/google-service-account.json
GOOGLE_SERVICE_ACCOUNT_JSON
(optional) Paste the full JSON as one line instead of using a file
Move the downloaded file into app/credentials/google-service-account.json (create the folder if needed). Do not commit this file.

Open the JSON and note client_email — something like:

lmt-sheets@your-project.iam.gserviceaccount.com

You’ll need that email in the next step.

4. Create the spreadsheet and get GOOGLE_SHEETS_SPREADSHEET_ID
Go to Google Sheets
Create a new spreadsheet (or open an existing one)
Look at the URL:
https://docs.google.com/spreadsheets/d/17ceEzPnfX_WybhkYOC_MCMslipOQZcoWE_PSr3Ji6Xk/edit
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                         this is GOOGLE_SHEETS_SPREADSHEET_ID
Copy the ID between /d/ and /edit
Share the sheet with the service account (required or writes will fail):

In the sheet: Share
Paste the service account client_email
Give it Editor access
Uncheck “Notify people” if you want → Share
5. Set GOOGLE_SHEETS_WORKSHEET_NAME
At the bottom of the spreadsheet, look at the tab name (default is often Sheet1)
Rename it to Leads (or keep your name and set the env to match)
In .env:
GOOGLE_SHEETS_WORKSHEET_NAME=Leads
The tab name must match exactly (case-sensitive).

6. Toggle and retry settings (not from Google)
These are app config, not Google Console values:

Variable	Meaning	Suggested
GOOGLE_SHEETS_ENABLED
Turn sync on/off
true when ready
GOOGLE_SHEETS_MAX_RETRIES
Retries on API failure
3
GOOGLE_SHEETS_RETRY_BACKOFF_SECONDS
Wait between retries
1.5
Also set APP_BASE_URL (e.g. http://localhost:8000) so document links in the sheet are absolute.


# File Upload (S3 / Cloudflare R2)

Implemented in `app/core/file_storage.py` (dual-mode: `local` | `s3`).

- Upload → R2/S3 → DB stores absolute URL (`S3_PUBLIC_BASE_URL/...`)
- Delete / replace via the app also calls S3 `delete_object` so storage is freed
- Existing call sites (`document_service`, `payment_service`, `prospect_service`) already use `FileStorage.delete_file` / `replace_file`

Target architecture:
Upload request → FastAPI → upload bytes to R2/S3
DB stores: https://files.yourdomain.com/prospects/DOC00001.pdf
Excel / Sheets / frontend all use that URL as-is

1. Pick a provider (recommend Cloudflare R2)
    Provider	Why
    Cloudflare R2
    S3-compatible, cheap, no egress fees — best default
    AWS S3
    Fine if you’re already on AWS
    Cloudinary / Uploadcare
    Easier UI, less control, different SDK
    Use R2 below; S3 is the same code with different env values.

2. Create bucket + public access
    Cloudflare R2

    Cloudflare Dashboard → R2 → Create bucket (e.g. lmt-uploads)
    Manage R2 API Tokens → Create token with Object Read & Write
    Save: Access Key ID, Secret Access Key, account endpoint
    Endpoint looks like: https://<ACCOUNT_ID>.r2.cloudflarestorage.com
    Make objects publicly readable (pick one):
    Custom domain (best): files.yourdomain.com → R2 bucket
    Or R2 public bucket URL if enabled
    Public base URL examples:

    https://files.yourdomain.com
    https://pub-xxxxx.r2.dev
3. Add env vars (Render)
# Storage
    STORAGE_BACKEND=s3
    S3_BUCKET=lmt-uploads
    S3_REGION=auto
    S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
    S3_ACCESS_KEY_ID=...
    S3_SECRET_ACCESS_KEY=...
    S3_PUBLIC_BASE_URL=https://files.yourdomain.com
    # Still useful for API itself / non-file links
    APP_BASE_URL=https://your-backend.onrender.com
    Locally you can keep STORAGE_BACKEND=local so nothing breaks in dev.

4. Dependencies
    boto3
    (botocore comes with it.)

5. Extend settings (app/core/config.py)
    Add roughly:

    STORAGE_BACKEND: str = Field(default="local")  # "local" | "s3"
    S3_BUCKET: str | None = None
    S3_REGION: str = "auto"
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_PUBLIC_BASE_URL: str | None = None  # https://files.yourdomain.com
6. Rewrite FileStorage (main change)
    Keep the same method signatures so services stay untouched:

    # save_file(...) -> (file_url, stored_filename, file_size)
    # delete_file(file_url)
    # replace_file(old_file, upload_file, folder, filename)
    Logic:

    Key (object path): {folder}/{filename}{ext}
    e.g. prospects/DOC00001.pdf, receipts/PAY00001.jpg
    Upload with boto3 put_object (set ContentType from upload)
    Return public URL: {S3_PUBLIC_BASE_URL}/{key}
    → this is what goes into file_url / receipt_url
    Delete: parse key from full URL (or from /uploads/... for old rows) and delete_object
    Local fallback: if STORAGE_BACKEND=local, keep current disk + /uploads/... behavior
    
    # Sketch:

        import boto3
        from botocore.client import Config
        from pathlib import Path
        from fastapi import UploadFile
        from app.core.config import settings
        class FileStorage:
            BASE_UPLOAD_DIR = Path("app/uploads")
            PUBLIC_PREFIX = "/uploads"
            @classmethod
            def _s3(cls):
                return boto3.client(
                    "s3",
                    endpoint_url=settings.S3_ENDPOINT_URL,
                    aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                    region_name=settings.S3_REGION,
                    config=Config(signature_version="s3v4"),
                )
            @classmethod
            def save_file(cls, upload_file: UploadFile, folder: str, filename: str):
                extension = Path(upload_file.filename or "").suffix
                stored_filename = f"{filename}{extension}"
                key = f"{folder.strip('/')}/{stored_filename}"
                if settings.STORAGE_BACKEND == "s3":
                    body = upload_file.file.read()  # or upload_file.file
                    cls._s3().put_object(
                        Bucket=settings.S3_BUCKET,
                        Key=key,
                        Body=body,
                        ContentType=upload_file.content_type or "application/octet-stream",
                    )
                    base = settings.S3_PUBLIC_BASE_URL.rstrip("/")
                    file_url = f"{base}/{key}"
                    return file_url, stored_filename, len(body)
            # existing local disk logic...
    Delete must handle both formats:

    New: https://files.yourdomain.com/prospects/DOC00001.pdf → key prospects/DOC00001.pdf
    Old: /uploads/prospects/DOC00001.pdf → local path or migrate later
7. What you do not need to change
    These already call FileStorage and will automatically get absolute URLs:

    app/services/document_service.py
    app/services/payment_service.py
    app/services/prospect_service.py
    Excel / Google Sheets absolute-url helpers (they already pass through http(s)://)
    You can leave the /uploads StaticFiles mount for local/dev; production S3 URLs won’t use it.

    No Alembic migration needed if you keep storing URLs in the same file_url / receipt_url string columns (just longer absolute URLs — column is String(500), which is usually enough; bump if you use very long signed URLs).

8. Frontend (Vercel)
    Once DB has full URLs:

    // fileUrl is already https://files...
    <a href={fileUrl} target="_blank" rel="noreferrer">View</a>
    Optional safety for mixed old/new data:

    function resolveFileUrl(fileUrl: string) {
    if (!fileUrl) return "";
    if (fileUrl.startsWith("http")) return fileUrl;
    return `${import.meta.env.VITE_API_BASE_URL}${fileUrl}`;
    }
9. Migrate existing local files (one-time)
    If you already have files in app/uploads and rows like /uploads/...:

    Upload each file to R2 under the same relative key (prospects/...)
    Update DB:
    UPDATE prospect_documents
    SET file_url = 'https://files.yourdomain.com/' || trim(leading '/' from replace(file_url, '/uploads/', ''))
    WHERE file_url LIKE '/uploads/%';
    -- same idea for payments.receipt_url
    Or a small Python script using boto3 + SQLAlchemy. New uploads after deploy don’t need this.

10. Security choices
    Mode	When
    Public bucket / public URLs
    Simplest; Excel/Sheets links “just work” (matches your current open /uploads)
    Private + signed URLs
    Safer, but Sheets/Excel links expire; you’d generate signed links at export/API time
    For lead docs/receipts that staff open from Sheets, public read + unguessable keys (DOC00001 + random suffix) is the usual tradeoff. Don’t use guessable sequential names alone if documents are sensitive — add a random UUID in the key:

    prospects/DOC00001_a3f9c2e1.pdf
11. Rollout order
    Create R2 bucket + public domain
    Add env on Render (keep STORAGE_BACKEND=local first if you want)
    Implement dual-mode FileStorage
    Deploy with STORAGE_BACKEND=s3
    Smoke-test: upload doc → check DB URL → open in browser / Sheets
    Migrate old /uploads rows
    Optionally remove reliance on Render disk
    Minimal file touch list
    File	Change
    requirements.txt
    add boto3
    app/core/config.py
    S3 settings
    app/core/file_storage.py
    S3 upload/delete + local fallback
    .env / Render env
    new vars
    Frontend
    resolve absolute vs relative fileUrl
    (optional) one-off migrate script
    old files → R2 + DB update


# S3 Bucket Change
    Behavior
    FileStorage.delete_file() resolves the object key from the stored URL and calls S3 delete_object
    replace_file() deletes the old object first, then uploads the new one
    Existing services already call these methods (document_service, payment_service, prospect_service), so no route changes were needed
    Missing remote objects are ignored (already gone)
    Config
    Dual-mode via STORAGE_BACKEND:

    local — current disk + /uploads (default in .env for now)
    s3 — upload/delete against R2/S3; DB stores absolute S3_PUBLIC_BASE_URL/... URLs
    To use in production
    Set on Render:

    STORAGE_BACKEND=s3
    S3_BUCKET=...
    S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
    S3_ACCESS_KEY_ID=...
    S3_SECRET_ACCESS_KEY=...
    S3_PUBLIC_BASE_URL=https://files.yourdomain.com
    Then pip install -r requirements.txt (includes boto3).


    Prerequisites
Create a free Cloudflare account
Open the Cloudflare Dashboard
1. Create a bucket → S3_BUCKET
Left menu → R2 Object Storage
Create bucket
Name it (e.g. lmt-uploads) — lowercase, no spaces
Choose a location (or automatic) → Create bucket
S3_BUCKET=lmt-uploads
2. Get Account ID → part of S3_ENDPOINT_URL
Still on R2 overview, look for Account ID (right side), or
Dashboard home → copy Account ID under your account name
Build the endpoint:
S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
Example: if Account ID is a1b2c3d4e5f6...:

S3_ENDPOINT_URL=https://a1b2c3d4e5f6.r2.cloudflarestorage.com
3. Create API token → S3_ACCESS_KEY_ID + S3_SECRET_ACCESS_KEY
R2 → Overview → Manage R2 API Tokens (or API Tokens)
Create API token
Settings:
Token name: e.g. lmt-backend
Permissions: Object Read & Write
Apply to: your bucket (lmt-uploads) or all buckets
Create API Token
Copy immediately (secret shown once):
Access Key ID → S3_ACCESS_KEY_ID
Secret Access Key → S3_SECRET_ACCESS_KEY
S3_ACCESS_KEY_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
S3_SECRET_ACCESS_KEY=yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
4. Make files publicly readable → S3_PUBLIC_BASE_URL
Your app stores clickable links, so objects must be public. Pick one:

Option A — R2.dev subdomain (fastest for testing)
Open bucket lmt-uploads
Settings → Public access / R2.dev subdomain
Allow Access / enable public URL
Copy the URL, e.g. https://pub-xxxxxxxxxxxx.r2.dev
S3_PUBLIC_BASE_URL=https://pub-xxxxxxxxxxxx.r2.dev
Option B — Custom domain (better for production)
Bucket → Settings → Custom Domains
Connect a domain you manage in Cloudflare (e.g. files.yourdomain.com)
Wait until status is active
S3_PUBLIC_BASE_URL=https://files.yourdomain.com
No trailing slash.

5. Fixed values (not from Google/Cloudflare secrets)
STORAGE_BACKEND=s3
S3_REGION=auto
STORAGE_BACKEND=s3 — turns on R2/S3 mode in your app
S3_REGION=auto — required for R2; keep as auto
Final .env / Render block
STORAGE_BACKEND=s3
S3_BUCKET=lmt-uploads
S3_REGION=auto
S3_ENDPOINT_URL=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=your_access_key_id
S3_SECRET_ACCESS_KEY=your_secret_access_key
S3_PUBLIC_BASE_URL=https://pub-xxxx.r2.dev
Also keep:

APP_BASE_URL=https://your-backend.onrender.com
Locally you can leave STORAGE_BACKEND=local until R2 is ready.

Quick checklist
Variable	Where you get it
STORAGE_BACKEND
Set to s3 yourself
S3_BUCKET
Bucket name you created
S3_REGION
Always auto for R2
S3_ENDPOINT_URL
https:// + Account ID + .r2.cloudflarestorage.com
S3_ACCESS_KEY_ID
R2 API token → Access Key ID
S3_SECRET_ACCESS_KEY
R2 API token → Secret Access Key
S3_PUBLIC_BASE_URL
pub-….r2.dev or custom domain
Smoke test after filling values
Restart the backend
Upload a document on a lead
Open the fileUrl from the API — it should be
https://your-public-base/.../file.pdf and open in the browser
If upload works but the link 404s, public access / S3_PUBLIC_BASE_URL is wrong. If upload fails with auth errors, check Access Key + Endpoint + Bucket name.



# Docker 
    Production on Render
    Dockerfile path

    docker/Dockerfile

    Build Command

    docker build -f docker/Dockerfile -t lmt-backend .

    Start Command

    uvicorn main:app --host 0.0.0.0 --port $PORT

# Enum change 
    SELECT *
    FROM pg_enum
    JOIN pg_type ON pg_enum.enumtypid = pg_type.oid

    ALTER TYPE paymenttype
    ADD VALUE IF NOT EXISTS 'registration_fee';


# sequence-reset logic
Automatically reset after importing/restoring data
If you're restoring a database dump or manually inserting IDs during development, run:

SELECT setval(
    pg_get_serial_sequence('users', 'id'),
    COALESCE(MAX(id), 1),
    true
)
FROM users;