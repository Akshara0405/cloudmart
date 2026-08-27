import json
import os
import boto3
import pymysql


ssm = boto3.client("ssm")


def get_parameter(name, decrypt=False):
    response = ssm.get_parameter(
        Name=name,
        WithDecryption=decrypt
    )
    return response["Parameter"]["Value"]


def lambda_handler(event, context):

    environment = os.environ["ENVIRONMENT"]

    host = get_parameter(
        f"/cloudmart/{environment}/database/host"
    )

    port = int(
        get_parameter(
            f"/cloudmart/{environment}/database/port"
        )
    )

    database = get_parameter(
        f"/cloudmart/{environment}/database/name"
    )

    username = get_parameter(
        f"/cloudmart/{environment}/database/username"
    )

    password = get_parameter(
        f"/cloudmart/{environment}/database/password",
        decrypt=True
    )

    connection = pymysql.connect(
        host=host,
        port=port,
        user=username,
        password=password,
        database=database,
        connect_timeout=10,
        autocommit=True
    )

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    description VARCHAR(255) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    deleted_at TIMESTAMP NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(255) NOT NULL,
                    description TEXT NULL,
                    price DECIMAL(10,2) NOT NULL,
                    category VARCHAR(100) NULL,
                    stock_count INT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    deleted_at TIMESTAMP NULL,
                    INDEX idx_products_category (category)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    customer_id VARCHAR(100) NOT NULL UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    phone VARCHAR(20) NULL,
                    address VARCHAR(500) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    deleted_at TIMESTAMP NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS order_status (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    status_name VARCHAR(50) NOT NULL UNIQUE,
                    description VARCHAR(255) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    deleted_at TIMESTAMP NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tokens (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    token_hash VARCHAR(255) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    product_id INT NOT NULL,
                    customer_id VARCHAR(100) NOT NULL,
                    quantity INT NOT NULL,
                    status VARCHAR(100) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMP NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    INDEX idx_orders_customer_id (customer_id),
                    INDEX idx_orders_status (status),
                    INDEX idx_orders_created_at (created_at),
                    CONSTRAINT fk_orders_product
                        FOREIGN KEY (product_id)
                        REFERENCES products(id)
                )
                """
            )

            cursor.execute(
                """
                INSERT INTO categories (name, description)
                SELECT 'Electronics', 'Electronic products'
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM categories
                    WHERE name = 'Electronics'
                )
                """
            )

            cursor.execute(
                """
                INSERT INTO categories (name, description)
                SELECT 'Accessories',
                       'Computer and mobile accessories'
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM categories
                    WHERE name = 'Accessories'
                )
                """
            )

            statuses = [
                ("pending", "Order is pending"),
                ("confirmed", "Order is confirmed"),
                ("failed", "Order has failed"),
            ]

            for status_name, description in statuses:
                cursor.execute(
                    """
                    INSERT INTO order_status
                        (status_name, description)
                    SELECT %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM order_status
                        WHERE status_name = %s
                    )
                    """,
                    (status_name, description, status_name)
                )

            products = [
                (
                    "Laptop",
                    "Business laptop",
                    65000.00,
                    "Electronics",
                    10,
                ),
                (
                    "Wireless Mouse",
                    "Wireless optical mouse",
                    1200.00,
                    "Accessories",
                    25,
                ),
                (
                    "Keyboard",
                    "Mechanical keyboard",
                    3500.00,
                    "Accessories",
                    15,
                ),
            ]

            for product in products:
                cursor.execute(
                    """
                    INSERT INTO products
                        (
                            name,
                            description,
                            price,
                            category,
                            stock_count
                        )
                    SELECT %s, %s, %s, %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM products
                        WHERE name = %s
                    )
                    """,
                    product + (product[0],)
                )

            cursor.execute(
                """
                INSERT INTO customers
                    (
                        customer_id,
                        name,
                        email,
                        phone,
                        address
                    )
                SELECT
                    'CUST001',
                    'Test Customer',
                    'customer1@cloudmart.com',
                    '9876543210',
                    'Hyderabad'
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM customers
                    WHERE customer_id = 'CUST001'
                )
                """
            )

            table_names = [
                "categories",
                "products",
                "customers",
                "order_status",
                "tokens",
                "orders",
            ]

            counts = {}

            for table in table_names:
                cursor.execute(
                    f"SELECT COUNT(*) FROM {table}"
                )
                counts[table] = cursor.fetchone()[0]

            print(
                json.dumps(
                    {
                        "message": "CloudMart schema applied",
                        "tables": counts,
                    }
                )
            )

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Schema applied successfully",
                        "tables": counts,
                    }
                ),
            }

    finally:
        connection.close()