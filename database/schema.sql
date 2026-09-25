CREATE DATABASE IF NOT EXISTS cloudmart;
USE cloudmart;

CREATE TABLE IF NOT EXISTS categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    deleted_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS customers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(20),
    address VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    deleted_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    category VARCHAR(100),
    stock_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    deleted_at TIMESTAMP NULL,
    INDEX idx_products_category (category)
);

CREATE TABLE IF NOT EXISTS order_status (
    id INT PRIMARY KEY AUTO_INCREMENT,
    status_name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    deleted_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id VARCHAR(100) NOT NULL,
    status VARCHAR(100) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    INDEX idx_orders_customer_id (customer_id),
    INDEX idx_orders_status (status),
    INDEX idx_orders_created_at (created_at)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    INDEX idx_order_items_order_id (order_id),
    INDEX idx_order_items_product_id (product_id)
);

CREATE TABLE IF NOT EXISTS tokens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    token_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    customer_id VARCHAR(100) NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'customer',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    admin_id VARCHAR(100) NULL,
    INDEX idx_tokens_customer_id (customer_id),
    INDEX idx_tokens_role (role)
);

INSERT INTO categories (name, description)
SELECT 'Electronics', 'Electronic products'
WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Electronics');
INSERT INTO categories (name, description)
SELECT 'Accessories', 'Computer and mobile accessories'
WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Accessories');
INSERT INTO categories (name, description)
SELECT 'Home', 'Home and household products'
WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Home');

INSERT INTO customers (customer_id, name, email, phone, address)
SELECT 'CUST001', 'Test Customer', 'customer1@cloudmart.com', '9876543210', 'Hyderabad'
WHERE NOT EXISTS (SELECT 1 FROM customers WHERE customer_id = 'CUST001');
INSERT INTO customers (customer_id, name, email, phone, address)
SELECT 'CUST002', 'Customer Two', 'customer2@cloudmart.com', '9876543211', 'Hyderabad'
WHERE NOT EXISTS (SELECT 1 FROM customers WHERE customer_id = 'CUST002');
INSERT INTO customers (customer_id, name, email, phone, address)
SELECT 'CUST003', 'Customer Three', 'customer3@cloudmart.com', '9876543212', 'Hyderabad'
WHERE NOT EXISTS (SELECT 1 FROM customers WHERE customer_id = 'CUST003');
INSERT INTO customers (customer_id, name, email, phone, address)
SELECT 'CUST004', 'Customer Four', 'customer4@cloudmart.com', '9876543213', 'Hyderabad'
WHERE NOT EXISTS (SELECT 1 FROM customers WHERE customer_id = 'CUST004');

INSERT INTO products (name, description, price, category, stock_count)
SELECT 'Laptop', 'Business laptop', 65000.00, 'Electronics', 0
WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'Laptop');
INSERT INTO products (name, description, price, category, stock_count)
SELECT 'Wireless Mouse', 'Wireless optical mouse', 1200.00, 'Accessories', 11
WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'Wireless Mouse');
INSERT INTO products (name, description, price, category, stock_count)
SELECT 'Keyboard', 'Mechanical keyboard', 3500.00, 'Accessories', 14
WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'Keyboard');
INSERT INTO products (name, description, price, category, stock_count)
SELECT 'Apple iPhone 15', 'Apple iPhone 15 128GB smartphone', 69999.00, 'Electronics', 25
WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'Apple iPhone 15');
INSERT INTO products (name, description, price, category, stock_count)
SELECT 'Samsung Galaxy S24', 'Samsung Galaxy S24 smartphone', 74999.00, 'Electronics', 18
WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'Samsung Galaxy S24');
INSERT INTO products (name, description, price, category, stock_count)
SELECT 'Dell 24 Monitor', '24 inch Full HD monitor', 14500.00, 'Electronics', 12
WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'Dell 24 Monitor');
INSERT INTO products (name, description, price, category, stock_count)
SELECT 'Sony Headphones', 'Wireless headphones', 8999.00, 'Accessories', 20
WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'Sony Headphones');
INSERT INTO products (name, description, price, category, stock_count)
SELECT 'USB-C Hub', 'Multi-port USB-C hub', 2499.00, 'Accessories', 30
WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'USB-C Hub');
INSERT INTO products (name, description, price, category, stock_count)
SELECT 'Smart LED TV', 'Smart LED television', 32999.00, 'Home', 8
WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = 'Smart LED TV');

INSERT INTO order_status (status_name, description)
SELECT 'pending', 'Order has been placed and is being processed'
WHERE NOT EXISTS (SELECT 1 FROM order_status WHERE status_name = 'pending');
INSERT INTO order_status (status_name, description)
SELECT 'confirmed', 'Order has been confirmed'
WHERE NOT EXISTS (SELECT 1 FROM order_status WHERE status_name = 'confirmed');
INSERT INTO order_status (status_name, description)
SELECT 'failed', 'Order processing failed'
WHERE NOT EXISTS (SELECT 1 FROM order_status WHERE status_name = 'failed');
INSERT INTO order_status (status_name, description)
SELECT 'cancelled', 'Order has been cancelled'
WHERE NOT EXISTS (SELECT 1 FROM order_status WHERE status_name = 'cancelled');

INSERT INTO tokens (token_hash, customer_id, role, is_active)
SELECT 'customer-token-001', 'CUST001', 'customer', 1
WHERE NOT EXISTS (SELECT 1 FROM tokens WHERE token_hash = 'customer-token-001' AND customer_id = 'CUST001');
INSERT INTO tokens (token_hash, customer_id, role, is_active)
SELECT 'customer-token-002', 'CUST002', 'customer', 1
WHERE NOT EXISTS (SELECT 1 FROM tokens WHERE token_hash = 'customer-token-002' AND customer_id = 'CUST002');
INSERT INTO tokens (token_hash, customer_id, role, is_active)
SELECT 'customer-token-003', 'CUST003', 'customer', 1
WHERE NOT EXISTS (SELECT 1 FROM tokens WHERE token_hash = 'customer-token-003' AND customer_id = 'CUST003');
INSERT INTO tokens (token_hash, customer_id, role, is_active)
SELECT 'customer-token-004', 'CUST004', 'customer', 1
WHERE NOT EXISTS (SELECT 1 FROM tokens WHERE token_hash = 'customer-token-004' AND customer_id = 'CUST004');
INSERT INTO tokens (token_hash, customer_id, role, is_active, admin_id)
SELECT 'admin-token-001', NULL, 'admin', 1, 'ADMIN001'
WHERE NOT EXISTS (SELECT 1 FROM tokens WHERE token_hash = 'admin-token-001' AND role = 'admin');
