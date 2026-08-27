```sql
CREATE TABLE IF NOT EXISTS categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL
);

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
);

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
);

CREATE TABLE IF NOT EXISTS order_status (
    id INT PRIMARY KEY AUTO_INCREMENT,
    status_name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS tokens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    customer_id VARCHAR(100) NOT NULL,
    quantity INT NOT NULL,
    status VARCHAR(100) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,

    INDEX idx_orders_customer_id (customer_id),
    INDEX idx_orders_status (status),
    INDEX idx_orders_created_at (created_at),

    CONSTRAINT fk_orders_product
        FOREIGN KEY (product_id)
        REFERENCES products(id)
);

INSERT INTO categories (name, description)
SELECT 'Electronics', 'Electronic products'
WHERE NOT EXISTS (
    SELECT 1 FROM categories WHERE name = 'Electronics'
);

INSERT INTO order_status (status_name, description)
SELECT 'pending', 'Order is waiting for processing'
WHERE NOT EXISTS (
    SELECT 1 FROM order_status WHERE status_name = 'pending'
);

INSERT INTO order_status (status_name, description)
SELECT 'confirmed', 'Order has been confirmed'
WHERE NOT EXISTS (
    SELECT 1 FROM order_status WHERE status_name = 'confirmed'
);

INSERT INTO order_status (status_name, description)
SELECT 'failed', 'Order processing failed'
WHERE NOT EXISTS (
    SELECT 1 FROM order_status WHERE status_name = 'failed'
);

INSERT INTO products
    (name, description, price, category, stock_count)
SELECT
    'Wireless Headphones',
    'Bluetooth wireless headphones',
    2499.00,
    'Electronics',
    10
WHERE NOT EXISTS (
    SELECT 1 FROM products WHERE name = 'Wireless Headphones'
);

INSERT INTO products
    (name, description, price, category, stock_count)
SELECT
    'Wireless Mouse',
    'Ergonomic wireless mouse',
    899.00,
    'Electronics',
    5
WHERE NOT EXISTS (
    SELECT 1 FROM products WHERE name = 'Wireless Mouse'
);

INSERT INTO customers
    (customer_id, name, email, phone, address)
SELECT
    'CUST001',
    'Test Customer',
    'customer1@cloudmart.com',
    '9876543210',
    'Hyderabad'
WHERE NOT EXISTS (
    SELECT 1 FROM customers WHERE customer_id = 'CUST001'
);
```
