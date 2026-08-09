import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://ticketd:ticketd@127.0.0.1:5432/ticketd"
)
