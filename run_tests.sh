#!/bin/bash

if [ "$GITHUB_ACTIONS" == "true" ]; then
    echo "☁️  GitHub Actions detected: Bypassing pyenv and using system Python!"
else
    echo "💻 Local environment detected: Setting up pyenv..."
    source create_venv_pyenv_dev.sh
fi

# 1. Read the first argument passed to the script, default to 'mysql'
DB_CHOICE=${1:-mysql}

# 2. Set the Infrastructure Variables based on the choice
echo "========================================"
echo " STARTING TEST SUITE FOR: $DB_CHOICE"
echo "========================================"

docker compose -f scripts/dev/docker-compose.yml up -d adminer mailhog redis minio minio-init
docker compose -f scripts/dev/docker-compose.yml up -d $DB_CHOICE

if [ "$DB_CHOICE" == "sqlite" ]; then
    # SQLite uses a fast, in-memory database for testing
    export DB_TYPE="sqlite"
    export DB_HOST="dev-sqlite.db"
    #export DB_HOST=":memory:"
    #export DATABASE_URL="sqlite:///dev-sqlite.db"

elif [ "$DB_CHOICE" == "mariadb" ]; then
    # Use your local Docker MariaDB/MySQL container
    export DB_TYPE="mariadb"
    export DB_HOST="localhost"
    export DB_PORT=3306
    export DB_USER="user"
    export DB_PW="pw"
    export DB_NAME="expenseapp"

elif [ "$DB_CHOICE" == "mysql" ]; then
    # Connects to MySQL on port 3307!
    export DB_TYPE="mysql"
    export DB_HOST="localhost"
    export DB_PORT=3307
    export DB_USER="user"
    export DB_PW="pw"
    export DB_NAME="expenseapp"
    
elif [ "$DB_CHOICE" == "postgres" ]; then
    # Connects to Postgres on port 5432
    export DB_TYPE="postgres"
    export DB_HOST="localhost"
    export DB_PORT=5432
    export DB_USER="user"
    export DB_PW="pw"
    export DB_NAME="expenseapp"

elif [ "$DB_CHOICE" == "oracle-adb" ]; then
    # Connects to Oracle on port 1521 using the FREE service name
    export DB_TYPE="oracle"
    export DB_HOST="localhost"
    export DB_PORT=1521
    export DB_USER="ADMIN"
    export DB_PW="SuperSecretPw123!"
    export DB_NAME="expenseapp"
    
else
    echo "❌ Unknown database choice: $DB_CHOICE"
    exit 1
fi

# We don't need to wait for Docker if we are using SQLite!
if [ "$DB_CHOICE" != "sqlite" ]; then
    echo "⏳ Waiting for $DB_CHOICE to become healthy..."
    
    # Loop until Docker Inspect specifically returns the string "healthy"
    # Use 'json' format + python to safely handle containers without a Health key
    until [ "$(docker inspect dev-$DB_CHOICE | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0].get('State',{}).get('Health',{}).get('Status',''))" 2>/dev/null)" == "healthy" ]; do
        sleep 2
        echo -n "." # Prints dots to show progress without making new lines
    done
    
    echo -e "\n✅ dev-$DB_CHOICE is fully booted and ready!"
fi

export FLASK_APP="./expenseapp.py"
export FLASK_DEBUG=1

export MAIL_SERVER="localhost"
export MAIL_PORT=1025
export MAIL_USERNAME="user"
export MAIL_PASSWORD="pw"

export S3_BUCKET_NAME="expenseapp-bucket"
export S3_REGION="eu-central-1"
export AWS_ACCESS_KEY_ID="minioadmin"
export AWS_SECRET_ACCESS_KEY="minioadminpw"
export S3_ENDPOINT_URL="http://localhost:9000"

# 3. Wipe and initialize the chosen database
echo "🧹 Wiping $DB_CHOICE database..."
if [ "$DB_CHOICE" == "sqlite" ]; then
    # SQLite is physical file, we already wiped it via 'rm -f' above!
    echo "SQLite test file reset."
    rm -f "instance/$DB_HOST"
else
    # Only run the complex CASCADE drop logic for real databases
    flask flush-db-force
fi

flask flush-s3
flask flush-media-cache
flask flush-jobs

echo "🏗️ Initializing $DB_CHOICE schema..."
if [ "$DB_CHOICE" == "sqlite" ]; then
    # Bypassing Alembic migrations for SQLite!
    # This Python 1-liner instantly builds the perfect schema directly from models.py
    python -c "from app import create_app, db; app=create_app(); app.app_context().push(); db.create_all()"
else
    # Run chronological Alembic migrations for all other heavy databases
    flask db upgrade
fi

flask dbinit admin --overwrite
#flask dbinit icons --no-overwrite --subfolder icons
flask dbinit currencies --overwrite
flask dbinit dummyusers --count 3
flask dbmaint add-missing-guid

# 4. Run Pytest!
echo "Running Pytest..."
python -m pytest --cov=app tests/

# 5. Debug
#echo "Starting Flask development server to inspect result..."
#flask run --host=0.0.0.0