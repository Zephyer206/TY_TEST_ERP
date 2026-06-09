"""
app/core/config.py
Database connection configuration shared across the application.
"""
import psycopg2

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "124.222.29.229",
    "port": "5432"
}
