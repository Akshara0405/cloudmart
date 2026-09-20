import logging
import os
from datetime import datetime

import boto3
import pymysql

from flask import Flask, render_template

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

ENVIRONMENT = os.environ["ENVIRONMENT"]

AWS_REGION = os.environ.get(
    "AWS_REGION",
    "ap-south-1"
)

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

# Explicitly specify AWS region.
# This prevents botocore.exceptions.NoRegionError.

ssm = boto3.client(
    "ssm",
    region_name=AWS_REGION
)

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION
)


def get_parameter(name):

    result = ssm.get_parameter(
        Name=name,
        WithDecryption=True
    )

    return result["Parameter"]["Value"]


def get_db_connection():

    host = get_parameter(DB_HOST_PARAMETER)

    port = int(
        get_parameter(DB_PORT_PARAMETER)
    )

    database = get_parameter(
        DB_NAME_PARAMETER
    )

    username = get_parameter(
        DB_USERNAME_PARAMETER
    )

    password = get_parameter(
        DB_PASSWORD_PARAMETER
    )

    return pymysql.connect(
        host=host,
        port=port,
        user=username,
        password=password,
        database=database,
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor
    )


def get_products():

    connection = None

    try:

        connection = get_db_connection()

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    description,
                    price,
                    category,
                    stock_count
                FROM products
                WHERE is_deleted = FALSE
                ORDER BY id
                """
            )

            return cursor.fetchall()

    finally:

        if connection:
            connection.close()


def get_recent_orders():

    connection = None

    try:

        connection = get_db_connection()

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    o.id AS order_id,
                    o.customer_id,
                    o.status,
                    o.created_at,
                    oi.product_id,
                    p.name AS product_name,
                    oi.quantity,
                    oi.price
                FROM orders o
                INNER JOIN order_items oi
                    ON o.id = oi.order_id
                INNER JOIN products p
                    ON oi.product_id = p.id
                WHERE o.is_deleted = FALSE
                AND oi.is_deleted = FALSE
                ORDER BY o.created_at DESC, oi.id DESC
                LIMIT 20
                """
            )

            return cursor.fetchall()

    finally:

        if connection:
            connection.close()


def get_latest_report():

    bucket_name = get_parameter(
        REPORTS_BUCKET_PARAMETER
    )

    result = s3.list_objects_v2(
        Bucket=bucket_name,
        Prefix="reports/"
    )

    contents = result.get("Contents", [])

    if not contents:

        return None

    latest = max(
        contents,
        key=lambda item: item["LastModified"]
    )

    object_key = latest["Key"]

    url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket_name,
            "Key": object_key
        },
        ExpiresIn=3600
    )

    return {
        "key": object_key,
        "url": url,
        "last_modified": latest["LastModified"]
    }


@app.route("/")
def dashboard():

    try:

        products = get_products()

        orders = get_recent_orders()

        latest_report = get_latest_report()

        return render_template(
            "index.html",
            products=products,
            orders=orders,
            latest_report=latest_report,
            generated_at=datetime.now()
        )

    except Exception as error:

        app.logger.exception(
            "Dashboard error"
        )

        return (
            f"""
            <h1>CloudMart Dashboard</h1>
            <h2>Dashboard Error</h2>
            <pre>{error}</pre>
            """,
            500
        )


@app.route("/health")
def health():

    return {
        "status": "healthy",
        "service": "cloudmart-dashboard"
    }


if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000
    )