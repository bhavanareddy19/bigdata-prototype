#!/bin/bash
# Create multiple PostgreSQL databases on initialization.
# Used by docker-compose to create both 'airflow' and 'marquez' databases.
# This script runs automatically when the postgres container starts for the first time.

set -e
set -u

function create_user_and_database() {
    local database=$1
    echo "  Creating database '$database' for user '$POSTGRES_USER'..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        SELECT 'CREATE DATABASE $database'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$database')\gexec
        GRANT ALL PRIVILEGES ON DATABASE $database TO $POSTGRES_USER;
EOSQL
}

if [ -n "${POSTGRES_MULTIPLE_DATABASES:-}" ]; then
    echo "==> Creating additional databases: $POSTGRES_MULTIPLE_DATABASES"
    for db in $(echo $POSTGRES_MULTIPLE_DATABASES | tr ',' ' '); do
        create_user_and_database "$db"
    done
    echo "==> All databases created successfully."
fi
