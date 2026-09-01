import json
import logging
import os

import boto3
import pymysql


logger = logging.getLogger()
logger.setLevel(logging.INFO)

ssm = boto3.client("ssm")

ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

DB_HOST_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/host"
DB_PORT_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/port"
DB_NAME_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/name"
DB_USERNAME_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/username"


def get_parameter(name):
    response = ssm.get_parameter(
        Name=name,
        WithDecryption=True
    )

    return response["Parameter"]["Value"]


def get_db_connection():

    host = get_parameter(DB_HOST_PARAMETER)
    port = int(get_parameter(DB_PORT_PARAMETER))
    database = get_parameter(DB_NAME_PARAMETER)
    username = get_parameter(DB_USERNAME_PARAMETER)

    password = os.environ["DB_PASSWORD"]

    return pymysql.connect(
        host=host,
        port=port,
        user=username,
        password=password,
        database=database,
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )


def response(status_code, body):

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body, default=str)
    }


def lambda_handler(event, context):

    connection = None

    try:

        logger.info(json.dumps({
            "level": "INFO",
            "service": "order-processor",
            "action": "order_processing_started"
        }))

        # ----------------------------------------------------
        # READ ORDER INPUT
        # ----------------------------------------------------

        if isinstance(event, str):
            event = json.loads(event)

        order_id = event.get("order_id")
        product_id = event.get("product_id")
        customer_id = event.get("customer_id")
        quantity = event.get("quantity")

        # ----------------------------------------------------
        # VALIDATE INPUT
        # ----------------------------------------------------

        if not product_id:
            return response(
                400,
                {
                    "message": "product_id is required"
                }
            )

        if not customer_id:
            return response(
                400,
                {
                    "message": "customer_id is required"
                }
            )

        if quantity is None:
            return response(
                400,
                {
                    "message": "quantity is required"
                }
            )

        try:
            product_id = int(product_id)
            quantity = int(quantity)
        except (TypeError, ValueError):

            return response(
                400,
                {
                    "message": "product_id and quantity must be numbers"
                }
            )

        if quantity <= 0:

            return response(
                400,
                {
                    "message": "quantity must be greater than zero"
                }
            )

        # ----------------------------------------------------
        # CONNECT TO RDS
        # ----------------------------------------------------

        connection = get_db_connection()

        with connection.cursor() as cursor:

            # ------------------------------------------------
            # CHECK CUSTOMER
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT
                    customer_id
                FROM customers
                WHERE customer_id = %s
                AND is_deleted = FALSE
                """,
                (customer_id,)
            )

            customer = cursor.fetchone()

            if not customer:

                connection.rollback()

                return response(
                    404,
                    {
                        "message": "Customer not found"
                    }
                )

            # ------------------------------------------------
            # LOCK AND CHECK PRODUCT
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    price,
                    stock_count
                FROM products
                WHERE id = %s
                AND is_deleted = FALSE
                FOR UPDATE
                """,
                (product_id,)
            )

            product = cursor.fetchone()

            if not product:

                connection.rollback()

                return response(
                    404,
                    {
                        "message": "Product not found"
                    }
                )

            current_stock = int(product["stock_count"])

            # ------------------------------------------------
            # CHECK STOCK
            # ------------------------------------------------

            if current_stock < quantity:

                logger.warning(json.dumps({
                    "level": "WARN",
                    "service": "order-processor",
                    "action": "order_failed",
                    "reason": "insufficient_stock",
                    "product_id": product_id,
                    "requested_quantity": quantity,
                    "available_stock": current_stock
                }))

                connection.rollback()

                return response(
                    409,
                    {
                        "message": "Insufficient stock",
                        "available_stock": current_stock,
                        "requested_quantity": quantity
                    }
                )

            # ------------------------------------------------
            # CREATE ORDER IF NOT ALREADY CREATED
            # ------------------------------------------------

            if not order_id:

                cursor.execute(
                    """
                    INSERT INTO orders
                    (
                        product_id,
                        customer_id,
                        quantity,
                        status
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        'pending'
                    )
                    """,
                    (
                        product_id,
                        customer_id,
                        quantity
                    )
                )

                order_id = cursor.lastrowid

            else:

                cursor.execute(
                    """
                    SELECT
                        id,
                        status
                    FROM orders
                    WHERE id = %s
                    AND is_deleted = FALSE
                    FOR UPDATE
                    """,
                    (order_id,)
                )

                existing_order = cursor.fetchone()

                if not existing_order:

                    connection.rollback()

                    return response(
                        404,
                        {
                            "message": "Order not found"
                        }
                    )

            # ------------------------------------------------
            # DEDUCT INVENTORY
            # ------------------------------------------------

            new_stock = current_stock - quantity

            cursor.execute(
                """
                UPDATE products
                SET stock_count = %s
                WHERE id = %s
                AND is_deleted = FALSE
                """,
                (
                    new_stock,
                    product_id
                )
            )

            # ------------------------------------------------
            # CONFIRM ORDER
            # ------------------------------------------------

            cursor.execute(
                """
                UPDATE orders
                SET status = 'confirmed'
                WHERE id = %s
                AND is_deleted = FALSE
                """,
                (order_id,)
            )

        # ----------------------------------------------------
        # COMMIT TRANSACTION
        # ----------------------------------------------------

        connection.commit()

        logger.info(json.dumps({
            "level": "INFO",
            "service": "order-processor",
            "action": "order_confirmed",
            "order_id": order_id,
            "product_id": product_id,
            "customer_id": customer_id,
            "quantity": quantity,
            "stock_remaining": new_stock
        }))

        return response(
            200,
            {
                "message": "Order confirmed successfully",
                "order_id": order_id,
                "product_id": product_id,
                "customer_id": customer_id,
                "quantity": quantity,
                "status": "confirmed",
                "stock_remaining": new_stock
            }
        )

    except Exception as error:

        if connection:
            connection.rollback()

        logger.error(json.dumps({
            "level": "ERROR",
            "service": "order-processor",
            "action": "order_processing_failed",
            "error": str(error)
        }))

        return response(
            500,
            {
                "message": "Order processing failed",
                "error": str(error)
            }
        )

    finally:

        if connection:
            connection.close()
