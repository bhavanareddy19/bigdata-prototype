#!/bin/bash
# Create multiple PostgreSQL databases on initialization.
# Used by docker-compose to create both 'airflow' and 'marquez' databases.
# This script runs automatically when the postgres container starts for the first time.
#
# IMPORTANT: marquezproject/marquez:latest uses its bundled dev config which
# connects as user 'marquez' / password 'marquez' — so we must create that user.

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

# Create dedicated 'marquez' user for the Marquez lineage service.
# marquezproject/marquez uses its bundled dev config which hardcodes user=marquez / password=marquez.
echo "==> Creating 'marquez' user for Marquez lineage service..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'marquez') THEN
            CREATE USER marquez WITH PASSWORD 'marquez';
        END IF;
    END
    \$\$;
    GRANT ALL PRIVILEGES ON DATABASE marquez TO marquez;
    ALTER DATABASE marquez OWNER TO marquez;
EOSQL
echo "==> Marquez user created."
