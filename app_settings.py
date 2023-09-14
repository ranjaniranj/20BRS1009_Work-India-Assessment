# Define the current environment
current_env = "LOCAL"

# Define database configurations for different environments
env = {
    "LOCAL": {
        "db_config": {
            "connectionLimit": 10,
            "host": "localhost",
            "port": 3307,
            "user": "root",
            "password": "Ranju$112",
            "database": "railway_db",
            "timezone": "UTC",
        },
    },
    # Add configurations for other environments (DEV, PROD) as needed
}
