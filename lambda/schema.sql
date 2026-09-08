-- ============================================================
-- CloudMart Database Schema
-- ============================================================

CREATE DATABASE IF NOT EXISTS cloudmart;

USE cloudmart;


-- ============================================================
-- CATEGORIES
-- ============================================================

CREATE TABLE IF NOT EXISTS categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- PRODUCTS
-- ============================================================

CREATE TABLE IF NOT EXISTS products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    category_id INT,
    stock_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,

    INDEX idx_products_category_id (category_id),
    INDEX idx_products_name (name),
    INDEX idx_products_created_at (created_at),

    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id)
        REFERENCES categories(id)
);


-- ============================================================
-- CUSTOMERS
-- ============================================================

CREATE TABLE IF NOT EXISTS customers (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,

    INDEX idx_customers_email (email)
);


-- ============================================================
-- ORDER STATUS
-- ============================================================

CREATE TABLE IF NOT EXISTS order_status (
    id INT PRIMARY KEY AUTO_INCREMENT,
    status VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- ORDERS
--
-- One row represents one order.
-- Products are stored in order_items.
-- ============================================================

CREATE TABLE IF NOT EXISTS orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id VARCHAR(100) NOT NULL,
    status VARCHAR(100) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,

    INDEX idx_orders_customer_id (customer_id),
    INDEX idx_orders_status (status),
    INDEX idx_orders_created_at (created_at),

    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(id)
);


-- ============================================================
-- ORDER ITEMS
--
-- One order can contain multiple products.
-- ============================================================

CREATE TABLE IF NOT EXISTS order_items (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,

    INDEX idx_order_items_order_id (order_id),
    INDEX idx_order_items_product_id (product_id),

    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id)
        REFERENCES orders(id),

    CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id)
        REFERENCES products(id)
);


-- ============================================================
-- TOKENS
-- ============================================================

CREATE TABLE IF NOT EXISTS tokens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id VARCHAR(100) NOT NULL,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP NULL,

    INDEX idx_tokens_customer_id (customer_id),
    INDEX idx_tokens_expires_at (expires_at),

    CONSTRAINT fk_tokens_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(id)
);


-- ============================================================
-- SAMPLE DATA
-- ============================================================

-- Categories
INSERT INTO categories (name, description)
VALUES
    ('Electronics', 'Electronic products'),
    ('Accessories', 'Computer and mobile accessories'),
    ('Home', 'Home and household products')
ON DUPLICATE KEY UPDATE
    description = VALUES(description);


-- Customers
INSERT INTO customers (
    id,
    name,
    email,
    phone
)
VALUES
    (
        'CUST001',
        'Test Customer',
        'customer@example.com',
        '9999999999'
    )
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    email = VALUES(email),
    phone = VALUES(phone);


-- Products
INSERT INTO products (
    name,
    description,
    price,
    category_id,
    stock_count
)
SELECT
    'Laptop',
    'Test laptop',
    65000.00,
    id,
    5
FROM categories
WHERE name = 'Electronics'
AND NOT EXISTS (
    SELECT 1
    FROM products
    WHERE name = 'Laptop'
);


INSERT INTO products (
    name,
    description,
    price,
    category_id,
    stock_count
)
SELECT
    'Wireless Mouse',
    'Wireless computer mouse',
    1200.00,
    id,
    25
FROM categories
WHERE name = 'Accessories'
AND NOT EXISTS (
    SELECT 1
    FROM products
    WHERE name = 'Wireless Mouse'
);


INSERT INTO products (
    name,
    description,
    price,
    category_id,
    stock_count
)
SELECT
    'Keyboard',
    'Computer keyboard',
    3500.00,
    id,
    15
FROM categories
WHERE name = 'Accessories'
AND NOT EXISTS (
    SELECT 1
    FROM products
    WHERE name = 'Keyboard'
);


-- ============================================================
-- ORDER STATUS SEED DATA
-- ============================================================

INSERT INTO order_status (
    status,
    description
)
VALUES
    ('pending', 'Order has been placed and is being processed'),
    ('confirmed', 'Order has been confirmed'),
    ('failed', 'Order processing failed'),
    ('cancelled', 'Order has been cancelled')
ON DUPLICATE KEY UPDATE
    description = VALUES(description);


-- ============================================================
-- END OF SCHEMA
-- ============================================================