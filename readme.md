# When adding new fields to Models do following steps
Best practices

✅ Every model change → create a migration.

✅ Every migration → review it before running.

✅ Commit migration files to Git.

✅ Everyone on the team runs:
# . Change your SQLAlchemy model
# . Generate a migration
alembic revision --autogenerate -m "Comment"
# . Apply it
alembic upgrade head 
# . Check
alembic current  // to check

# Run Backend 
    activate venv 
     .venv\Scripts\activate    or .\.venv\Scripts\Activate.ps1   
     run app 
    .\.venv\Scripts\python.exe -m uvicorn main:app --reload 

    or 

    uvicorn main:app --reload     

 # check python exection path
 C:\Users\Hemand\AppData\Local\Programs\Python\Python313\python.exe -c "import main; print('ok')"

# A common setup Production
 pip install -r requirements.txt
 alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT

# on EC2
 git pull

source .venv/bin/activate

pip install -r requirements.txt

alembic upgrade head

sudo systemctl restart fastapi


#  Run migrations

Execute:

alembic upgrade head

Alembic will:

create the alembic_version table
run the initial migration
create every table
create indexes
create enums
create foreign keys
run every subsequent migration

Your database is now fully initialized.