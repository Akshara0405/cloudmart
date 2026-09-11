import csv
import io
import json
import logging
import os
from datetime import datetime, timezone

import boto3
import pymysql


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ============================================================
# AWS CLIENTS
# ============================================================

ssm = boto3.client("ssm")
s3 = boto3.client("s3")


# ============================================================
# ENVIRONMENT
# ============================================================

ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

DB_HOST_PARAMETER = (
    f"/cloudmart/{ENVIRONMENT}/database/host"
)

DB_PORT_PARAMETER = (
    f"/cloudmart/{ENVIRONMENT}/database/port"
)

DB_NAME_PARAMETER = (
    f"/cloudmart/{ENVIRONMENT}/database/name"
)

DB_USERNAME_PARAMETER = (
    f"/cloudmart/{ENVIRONMENT}/database/username"
)

DB_PASSWORD_PARAMETER = (
    f"/cloudmart/{ENVIRONMENT}/database/password"
)

REPORTS_BUCKET_PARAMETER = (
    f"/cloudmart/{ENVIRONMENT}/storage/reports-bucket"
)


# ============================================================
# SSM PARAMETER
# ============================================================

def get_parameter(name):

    result = ssm.get_parameter(
        Name=name,
        WithDecryption=True
    )

    return result["Parameter"]["Value"]


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():

    host = get_parameter(DB_HOST_PARAMETER)
    port = int(get_parameter(DB_PORT_PARAMETER))
    database = get_parameter(DB_NAME_PARAMETER)
    username = get_parameter(DB_USERNAME_PARAMETER)
    password = get_parameter(DB_PASSWORD_PARAMETER)

    return pymysql.connect(
        host=host,
        port=port,
        user=username,
        password=password,
        database=database,
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


# ============================================================
# GET REPORT DATA
# ============================================================

def get_report_data(connection):

    with connection.cursor() as cursor:

        # ====================================================
        # PRODUCTS / INVENTORY
        # ====================================================

        cursor.execute(
            """
            SELECT
                p.id AS product_id,
                p.name AS product_name,
                p.description,
                p.price,
                p.category,
                p.stock_count
            FROM products p
            WHERE p.is_deleted = FALSE
            ORDER BY p.id
            """
        )

        products = cursor.fetchall()

        # ====================================================
        # ORDERS
        # ====================================================

        cursor.execute(
            """
            SELECT
                o.id AS order_id,
                o.customer_id,
                o.status AS order_status,
                o.created_at AS order_created_at,
                o.updated_at AS order_updated_at,

                oi.id AS order_item_id,
                oi.product_id,
                p.name AS product_name,
                oi.quantity,
                oi.price AS order_item_price

            FROM orders o

            INNER JOIN order_items oi
                ON o.id = oi.order_id

            INNER JOIN products p
                ON oi.product_id = p.id

            WHERE o.is_deleted = FALSE
            AND oi.is_deleted = FALSE

            ORDER BY o.created_at DESC, oi.id
            """
        )

        orders = cursor.fetchall()

    return products, orders


# ============================================================
# CREATE CSV
# ============================================================

def create_csv(products, orders):

    output = io.StringIO()

    writer = csv.writer(output)

    # ========================================================
    # REPORT INFORMATION
    # ========================================================

    writer.writerow([
        "CloudMart Daily Report"
    ])

    writer.writerow([
        "Generated At",
        datetime.now(timezone.utc).isoformat()
    ])

    writer.writerow([])

    # ========================================================
    # INVENTORY SECTION
    # ========================================================

    writer.writerow([
        "INVENTORY"
    ])

    writer.writerow([
        "Product ID",
        "Product Name",
        "Description",
        "Price",
        "Category",
        "Stock Count"
    ])

    for product in products:

        writer.writerow([
            product["product_id"],
            product["product_name"],
            product["description"],
            product["price"],
            product["category"],
            product["stock_count"]
        ])

    writer.writerow([])

    # ========================================================
    # ORDERS SECTION
    # ========================================================

    writer.writerow([
        "ORDERS"
    ])

    writer.writerow([
        "Order ID",
        "Customer ID",
        "Order Status",
        "Order Created At",
        "Order Updated At",
        "Order Item ID",
        "Product ID",
        "Product Name",
        "Quantity",
        "Item Price"
    ])

    for order in orders:

        writer.writerow([
            order["order_id"],
            order["customer_id"],
            order["order_status"],
            order["order_created_at"],
            order["order_updated_at"],
            order["order_item_id"],
            order["product_id"],
            order["product_name"],
            order["quantity"],
            order["order_item_price"]
        ])

    return output.getvalue()


# ============================================================
# UPLOAD REPORT TO S3
# ============================================================

def upload_report(csv_content):

    bucket_name = get_parameter(
        REPORTS_BUCKET_PARAMETER
    )

    current_date = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    object_key = (
        f"reports/daily-report-{current_date}.csv"
    )

    s3.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=csv_content.encode("utf-8"),
        ContentType="text/csv"
    )

    logger.info(json.dumps({
        "level": "INFO",
        "service": "report-lambda",
        "action": "report_uploaded",
        "bucket": bucket_name,
        "key": object_key
    }))

    return bucket_name, object_key


# ============================================================
# LAMBDA HANDLER
# ============================================================

def lambda_handler(event, context):

    connection = None

    try:

        logger.info(json.dumps({
            "level": "INFO",
            "service": "report-lambda",
            "action": "report_generation_started",
            "environment": ENVIRONMENT
        }))

        # ----------------------------------------------------
        # DATABASE
        # ----------------------------------------------------

        connection = get_db_connection()

        products, orders = get_report_data(
            connection
        )

        # ----------------------------------------------------
        # CSV
        # ----------------------------------------------------

        csv_content = create_csv(
            products,
            orders
        )

        # ----------------------------------------------------
        # S3
        # ----------------------------------------------------

        bucket_name, object_key = upload_report(
            csv_content
        )

        logger.info(json.dumps({
            "level": "INFO",
            "service": "report-lambda",
            "action": "report_generation_completed",
            "product_count": len(products),
            "order_item_count": len(orders),
            "bucket": bucket_name,
            "key": object_key
        }))

        return {
            "statusCode": 200,
            "message": "Daily report generated successfully",
            "bucket": bucket_name,
            "key": object_key,
            "product_count": len(products),
            "order_item_count": len(orders)
        }

    except Exception as error:

        logger.error(json.dumps({
            "level": "ERROR",
            "service": "report-lambda",
            "action": "report_generation_failed",
            "error": str(error)
        }))

        raise

    finally:

        if connection:
            connection.close()
