import os


db_user = None
db_pass = None
with open(os.environ["POSTGRES_USER_FILE"]) as f:
    db_user = f.read()

with open(os.environ["POSTGRES_PASSWORD_FILE"]) as f:
    db_pass = f.read()

db_name = os.getenv("POSTGRES_DB", None)

if db_name is None or db_user is None or db_pass is None:
    exit(500)


class BasicConfig(object):
    DEBUG = os.getenv("DEBUG", False)
    DB_NAME = db_name
    DB_USER = db_user
    DB_PASS = db_pass
    DB_PORT = os.getenv("DATABASE_PORT", 5432)

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASS}@postgres:{DB_PORT}/{DB_NAME}"
    )

    pass
