import json
import logging
import os

import boto3
import pymysql


logger = logging.getLogger()
logger.setLevel(logging.INFO)

ssm = boto3.client("ssm")
events = boto3.client("events")

ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

DB_HOST_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/host"
DB_PORT_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/port"
DB_NAME_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/name"
DB_USERNAME_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/username"

EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")


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


def execute_schema(connection):

    schema_path = os.path.join(
        os.path.dirname(__file__),
        "schema.sql"
    )

    with open(schema_path, "r", encoding="utf-8") as file:
        schema = file.read()

    statements = [
        statement.strip()
        for statement in schema.split(";")
        if statement.strip()
    ]

    with connection.cursor() as cursor:

        for statement in statements:
            cursor.execute(statement)

    connection.commit()


def publish_inventory_event(
    product_id,
    stock_count,
    event_type="InventoryChanged"
):
    """
    Publish inventory changes to EventBridge.
    EventBridge rules can use this event for low-stock alerts.
    """

    event_detail = {
        "product_id": int(product_id),
        "stock_count": int(stock_count),
        "low_stock": int(stock_count) <= 5,
        "environment": ENVIRONMENT
    }

    response = events.put_events(
        Entries=[
            {
                "EventBusName": EVENT_BUS_NAME,
                "Source": "cloudmart.product",
                "DetailType": event_type,
                "Detail": json.dumps(event_detail)
            }
        ]
    )

    if response.get("FailedEntryCount", 0) > 0:

        logger.error(json.dumps({
            "level": "ERROR",
            "service": "product-service",
            "action": "eventbridge_publish_failed",
            "product_id": product_id,
            "stock_count": stock_count,
            "response": response
        }))

        raise Exception("Failed to publish inventory event to EventBridge")

    logger.info(json.dumps({
        "level": "INFO",
        "service": "product-service",
        "action": "inventory_event_published",
        "product_id": product_id,
        "stock_count": stock_count,
        "event_type": event_type,
        "event_bus": EVENT_BUS_NAME
    }))


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

        connection = get_db_connection()

        method = event.get("httpMethod", "").upper()

        path_parameters = event.get("pathParameters") or {}
        product_id = path_parameters.get("id")

        body = {}

        if event.get("body"):

            if isinstance(event["body"], str):
                body = json.loads(event["body"])
            else:
                body = event["body"]

        # ----------------------------------------------------
        # TEMPORARY SCHEMA INITIALIZATION
        # ----------------------------------------------------

        if body.get("action") == "init_schema":

            execute_schema(connection)

            logger.info(json.dumps({
                "level": "INFO",
                "service": "product-service",
                "action": "schema_initialized",
                "status": "success"
            }))

            return response(
                200,
                {
                    "message": "schema.sql executed successfully"
                }
            )

        # ----------------------------------------------------
        # GET /products
        # ----------------------------------------------------

        if method == "GET" and not product_id:

            with connection.cursor() as cursor:

                cursor.execute("""
                    SELECT
                        id,
                        name,
                        description,
                        price,
                        category,
                        stock_count,
                        created_at,
                        is_deleted,
                        deleted_at
                    FROM products
                    WHERE is_deleted = FALSE
                    ORDER BY id
                """)

                products = cursor.fetchall()

            return response(
                200,
                {
                    "products": products
                }
            )

        # ----------------------------------------------------
        # GET /products/{id}
        # ----------------------------------------------------

        if method == "GET" and product_id:

            with connection.cursor() as cursor:

                cursor.execute("""
                    SELECT
                        id,
                        name,
                        description,
                        price,
                        category,
                        stock_count,
                        created_at,
                        is_deleted,
                        deleted_at
                    FROM products
                    WHERE id = %s
                    AND is_deleted = FALSE
                """, (product_id,))

                product = cursor.fetchone()

            if not product:

                return response(
                    404,
                    {
                        "message": "Product not found"
                    }
                )

            return response(
                200,
                product
            )

        # ----------------------------------------------------
        # POST /products
        # ----------------------------------------------------

        if method == "POST":

            name = body.get("name")
            description = body.get("description")
            price = body.get("price")
            category = body.get("category")
            stock_count = body.get("stock_count", 0)

            if not name or price is None:

                return response(
                    400,
                    {
                        "message": "name and price are required"
                    }
                )

            try:
                stock_count = int(stock_count)

                if stock_count < 0:

                    return response(
                        400,
                        {
                            "message": "stock_count cannot be negative"
                        }
                    )

            except (TypeError, ValueError):

                return response(
                    400,
                    {
                        "message": "stock_count must be a number"
                    }
                )

            with connection.cursor() as cursor:

                cursor.execute("""
                    INSERT INTO products
                    (
                        name,
                        description,
                        price,
                        category,
                        stock_count
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                """, (
                    name,
                    description,
                    price,
                    category,
                    stock_count
                ))

                new_product_id = cursor.lastrowid

            connection.commit()

            # Publish inventory event after successful database commit
            publish_inventory_event(
                product_id=new_product_id,
                stock_count=stock_count,
                event_type="InventoryChanged"
            )

            return response(
                201,
                {
                    "message": "Product created successfully",
                    "product_id": new_product_id
                }
            )

        # ----------------------------------------------------
        # PUT /products/{id}
        # ----------------------------------------------------

        if method == "PUT" and product_id:

            name = body.get("name")
            description = body.get("description")
            price = body.get("price")
            category = body.get("category")
            stock_count = body.get("stock_count")

            if stock_count is None:

                return response(
                    400,
                    {
                        "message": "stock_count is required"
                    }
                )

            try:
                stock_count = int(stock_count)

                if stock_count < 0:

                    return response(
                        400,
                        {
                            "message": "stock_count cannot be negative"
                        }
                    )

            except (TypeError, ValueError):

                return response(
                    400,
                    {
                        "message": "stock_count must be a number"
                    }
                )

            with connection.cursor() as cursor:

                cursor.execute("""
                    UPDATE products
                    SET
                        name = %s,
                        description = %s,
                        price = %s,
                        category = %s,
                        stock_count = %s
                    WHERE id = %s
                    AND is_deleted = FALSE
                """, (
                    name,
                    description,
                    price,
                    category,
                    stock_count,
                    product_id
                ))

                affected_rows = cursor.rowcount

            connection.commit()

            if affected_rows == 0:

                return response(
                    404,
                    {
                        "message": "Product not found"
                    }
                )

            # Publish inventory event after successful update
            publish_inventory_event(
                product_id=product_id,
                stock_count=stock_count,
                event_type="InventoryChanged"
            )

            return response(
                200,
                {
                    "message": "Product updated successfully",
                    "product_id": product_id
                }
            )

        # ----------------------------------------------------
        # DELETE /products/{id}
        # ----------------------------------------------------

        if method == "DELETE" and product_id:

            with connection.cursor() as cursor:

                cursor.execute("""
                    UPDATE products
                    SET
                        is_deleted = TRUE,
                        deleted_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    AND is_deleted = FALSE
                """, (product_id,))

                affected_rows = cursor.rowcount

            connection.commit()

            if affected_rows == 0:

                return response(
                    404,
                    {
                        "message": "Product not found"
                    }
                )

            return response(
                200,
                {
                    "message": "Product deleted successfully",
                    "product_id": product_id
                }
            )

        return response(
            405,
            {
                "message": "Method or path not supported"
            }
        )

    except Exception as error:

        if connection:

            connection.rollback()

        logger.error(json.dumps({
            "level": "ERROR",
            "service": "product-service",
            "action": "request_failed",
            "error": str(error)
        }))

        return response(
            500,
            {
                "message": "Database operation failed",
                "error": str(error)
            }
        )

    finally:

        if connection:

            connection.close()
