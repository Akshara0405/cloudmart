import json
import logging
import os

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
events = boto3.client("events")


# ============================================================
# ENVIRONMENT
# ============================================================

ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

DB_HOST_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/host"
DB_PORT_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/port"
DB_NAME_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/name"
DB_USERNAME_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/username"
DB_PASSWORD_PARAMETER = f"/cloudmart/{ENVIRONMENT}/database/password"


# ============================================================
# RESPONSE HELPER
# ============================================================

def response(status_code, body):

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body, default=str)
    }


# ============================================================
# SSM PARAMETER
# ============================================================

def get_parameter(name):

    try:

        result = ssm.get_parameter(
            Name=name,
            WithDecryption=True
        )

        return result["Parameter"]["Value"]

    except Exception as error:

        logger.error(json.dumps({
            "level": "ERROR",
            "service": "order-processor",
            "action": "ssm_parameter_read_failed",
            "parameter": name,
            "error": str(error)
        }))

        raise


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():

    try:

        host = get_parameter(DB_HOST_PARAMETER)
        port = int(get_parameter(DB_PORT_PARAMETER))
        database = get_parameter(DB_NAME_PARAMETER)
        username = get_parameter(DB_USERNAME_PARAMETER)
        password = get_parameter(DB_PASSWORD_PARAMETER)

        logger.info(json.dumps({
            "level": "INFO",
            "service": "order-processor",
            "action": "database_connection_started",
            "host_parameter": DB_HOST_PARAMETER,
            "port_parameter": DB_PORT_PARAMETER,
            "database_parameter": DB_NAME_PARAMETER,
            "username_parameter": DB_USERNAME_PARAMETER,
            "password_parameter": DB_PASSWORD_PARAMETER
        }))

        connection = pymysql.connect(
            host=host,
            port=port,
            user=username,
            password=password,
            database=database,
            connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )

        logger.info(json.dumps({
            "level": "INFO",
            "service": "order-processor",
            "action": "database_connection_success"
        }))

        return connection

    except Exception as error:

        logger.error(json.dumps({
            "level": "ERROR",
            "service": "order-processor",
            "action": "database_connection_failed",
            "error": str(error)
        }))

        raise


# ============================================================
# EVENTBRIDGE EVENT PUBLISHER
# ============================================================

def publish_order_event(detail_type, detail):

    try:

        result = events.put_events(
            Entries=[
                {
                    "Source": "cloudmart.order",
                    "DetailType": detail_type,
                    "Detail": json.dumps(detail),
                    "EventBusName": "default"
                }
            ]
        )

        failed_count = result.get("FailedEntryCount", 0)

        if failed_count > 0:

            logger.error(json.dumps({
                "level": "ERROR",
                "service": "order-processor",
                "action": "event_publish_failed",
                "detail_type": detail_type,
                "order_id": detail.get("order_id"),
                "response": result
            }))

            return False

        logger.info(json.dumps({
            "level": "INFO",
            "service": "order-processor",
            "action": "event_published",
            "detail_type": detail_type,
            "order_id": detail.get("order_id")
        }))

        return True

    except Exception as error:

        logger.error(json.dumps({
            "level": "ERROR",
            "service": "order-processor",
            "action": "event_publish_failed",
            "detail_type": detail_type,
            "order_id": detail.get("order_id"),
            "error": str(error)
        }))

        return False


# ============================================================
# REQUEST BODY PARSER
# ============================================================

def get_request_body(event):

    body = event.get("body")

    if body is None:
        return event

    if isinstance(body, str):

        if not body.strip():
            return {}

        return json.loads(body)

    if isinstance(body, dict):
        return body

    return {}


# ============================================================
# POST /orders
# ============================================================

def create_order(event):

    connection = None

    try:

        logger.info(json.dumps({
            "level": "INFO",
            "service": "order-processor",
            "action": "order_creation_started"
        }))

        # ----------------------------------------------------
        # READ REQUEST BODY
        # ----------------------------------------------------

        try:

            request = get_request_body(event)

        except json.JSONDecodeError:

            return response(
                400,
                {
                    "message": "Request body must contain valid JSON"
                }
            )

        customer_id = request.get("customer_id")
        items = request.get("items")

        # ----------------------------------------------------
        # VALIDATE CUSTOMER
        # ----------------------------------------------------

        if customer_id is None or str(customer_id).strip() == "":

            return response(
                400,
                {
                    "message": "customer_id is required"
                }
            )

        # ----------------------------------------------------
        # VALIDATE ITEMS
        # ----------------------------------------------------

        if items is None:

            return response(
                400,
                {
                    "message": "items is required"
                }
            )

        if not isinstance(items, list):

            return response(
                400,
                {
                    "message": "items must be an array"
                }
            )

        if len(items) == 0:

            return response(
                400,
                {
                    "message": "items must contain at least one product"
                }
            )

        # ----------------------------------------------------
        # VALIDATE EVERY ITEM
        # ----------------------------------------------------

        items_by_product = {}

        for index, item in enumerate(items):

            if not isinstance(item, dict):

                return response(
                    400,
                    {
                        "message": f"Item {index + 1} must be an object"
                    }
                )

            product_id = item.get("product_id")
            quantity = item.get("quantity")

            if product_id is None:

                return response(
                    400,
                    {
                        "message": (
                            f"product_id is required "
                            f"for item {index + 1}"
                        )
                    }
                )

            if quantity is None:

                return response(
                    400,
                    {
                        "message": (
                            f"quantity is required "
                            f"for item {index + 1}"
                        )
                    }
                )

            try:

                product_id = int(product_id)
                quantity = int(quantity)

            except (TypeError, ValueError):

                return response(
                    400,
                    {
                        "message": (
                            "product_id and quantity must be numbers "
                            f"for item {index + 1}"
                        )
                    }
                )

            if product_id <= 0:

                return response(
                    400,
                    {
                        "message": (
                            "product_id must be greater than zero "
                            f"for item {index + 1}"
                        )
                    }
                )

            if quantity <= 0:

                return response(
                    400,
                    {
                        "message": (
                            "quantity must be greater than zero "
                            f"for item {index + 1}"
                        )
                    }
                )

            # Combine duplicate products
            if product_id in items_by_product:

                items_by_product[product_id] += quantity

            else:

                items_by_product[product_id] = quantity

        # ----------------------------------------------------
        # CREATE VALIDATED ITEMS
        # ----------------------------------------------------

        validated_items = []

        for product_id, quantity in items_by_product.items():

            validated_items.append({
                "product_id": product_id,
                "quantity": quantity
            })

        # ----------------------------------------------------
        # CONNECT TO DATABASE
        # ----------------------------------------------------

        connection = get_db_connection()

        with connection.cursor() as cursor:

            # =================================================
            # CHECK CUSTOMER
            # =================================================

            cursor.execute(
                """
                SELECT
                    id,
                    customer_id,
                    name,
                    email
                FROM customers
                WHERE customer_id = %s
                AND is_deleted = FALSE
                """,
                (customer_id,)
            )

            customer = cursor.fetchone()

            if not customer:

                connection.rollback()

                logger.warning(json.dumps({
                    "level": "WARN",
                    "service": "order-processor",
                    "action": "order_failed",
                    "reason": "customer_not_found",
                    "customer_id": customer_id
                }))

                publish_order_event(
                    "OrderFailed",
                    {
                        "reason": "customer_not_found",
                        "customer_id": customer_id
                    }
                )

                return response(
                    404,
                    {
                        "message": "Customer not found"
                    }
                )

            # =================================================
            # CHECK ALL PRODUCTS AND STOCK
            # =================================================

            processed_items = []

            for item in validated_items:

                product_id = item["product_id"]
                quantity = item["quantity"]

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
                    WHERE id = %s
                    AND is_deleted = FALSE
                    FOR UPDATE
                    """,
                    (product_id,)
                )

                product = cursor.fetchone()

                if not product:

                    connection.rollback()

                    logger.warning(json.dumps({
                        "level": "WARN",
                        "service": "order-processor",
                        "action": "order_failed",
                        "reason": "product_not_found",
                        "customer_id": customer_id,
                        "product_id": product_id,
                        "quantity": quantity
                    }))

                    publish_order_event(
                        "OrderFailed",
                        {
                            "reason": "product_not_found",
                            "customer_id": customer_id,
                            "product_id": product_id,
                            "quantity": quantity
                        }
                    )

                    return response(
                        404,
                        {
                            "message": "Product not found",
                            "product_id": product_id
                        }
                    )

                current_stock = int(product["stock_count"])

                if current_stock < quantity:

                    connection.rollback()

                    logger.warning(json.dumps({
                        "level": "WARN",
                        "service": "order-processor",
                        "action": "order_failed",
                        "reason": "insufficient_stock",
                        "product_id": product_id,
                        "customer_id": customer_id,
                        "requested_quantity": quantity,
                        "available_stock": current_stock
                    }))

                    publish_order_event(
                        "OrderFailed",
                        {
                            "reason": "insufficient_stock",
                            "customer_id": customer_id,
                            "product_id": product_id,
                            "quantity": quantity,
                            "available_stock": current_stock
                        }
                    )

                    return response(
                        409,
                        {
                            "message": "Insufficient stock",
                            "product_id": product_id,
                            "available_stock": current_stock,
                            "requested_quantity": quantity
                        }
                    )

                new_stock = current_stock - quantity

                processed_items.append({
                    "product_id": product_id,
                    "product_name": product["name"],
                    "quantity": quantity,
                    "price": float(product["price"]),
                    "stock_remaining": new_stock
                })

            # =================================================
            # CREATE ONE ORDER
            # =================================================

            cursor.execute(
                """
                INSERT INTO orders
                (
                    customer_id,
                    status
                )
                VALUES
                (
                    %s,
                    'pending'
                )
                """,
                (customer_id,)
            )

            order_id = cursor.lastrowid

            # =================================================
            # CREATE ORDER ITEMS + DEDUCT INVENTORY
            # =================================================

            for item in processed_items:

                cursor.execute(
                    """
                    INSERT INTO order_items
                    (
                        order_id,
                        product_id,
                        quantity,
                        price
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        order_id,
                        item["product_id"],
                        item["quantity"],
                        item["price"]
                    )
                )

                cursor.execute(
                    """
                    UPDATE products
                    SET stock_count = %s
                    WHERE id = %s
                    AND is_deleted = FALSE
                    """,
                    (
                        item["stock_remaining"],
                        item["product_id"]
                    )
                )

            # =================================================
            # CONFIRM ORDER
            # =================================================

            cursor.execute(
                """
                UPDATE orders
                SET status = 'confirmed'
                WHERE id = %s
                AND is_deleted = FALSE
                """,
                (order_id,)
            )

        # ====================================================
        # COMMIT TRANSACTION
        # ====================================================

        connection.commit()

        logger.info(json.dumps({
            "level": "INFO",
            "service": "order-processor",
            "action": "order_confirmed",
            "order_id": order_id,
            "customer_id": customer_id,
            "item_count": len(processed_items)
        }))

        # ====================================================
        # PUBLISH ORDER CONFIRMED EVENT
        # ====================================================

        publish_order_event(
            "OrderConfirmed",
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "status": "confirmed",
                "items": processed_items
            }
        )

        # ====================================================
        # RESPONSE
        # ====================================================

        return response(
            201,
            {
                "message": "Order confirmed successfully",
                "order_id": order_id,
                "customer_id": customer_id,
                "status": "confirmed",
                "items": processed_items
            }
        )

    except Exception as error:

        if connection:

            try:
                connection.rollback()
            except Exception:
                pass

        logger.error(json.dumps({
            "level": "ERROR",
            "service": "order-processor",
            "action": "order_creation_failed",
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

            try:
                connection.close()
            except Exception:
                pass


# ============================================================
# PATCH /orders/{id} - CANCEL ORDER
# ============================================================

def cancel_order(event):

    connection = None

    try:

        path_parameters = event.get("pathParameters") or {}
        order_id = path_parameters.get("id")

        if order_id is None:
            return response(400, {
                "message": "Order id is required"
            })

        try:
            order_id = int(order_id)
        except (TypeError, ValueError):
            return response(400, {
                "message": "Order id must be a number"
            })

        if order_id <= 0:
            return response(400, {
                "message": "Order id must be greater than zero"
            })

        try:
            request = get_request_body(event)
        except json.JSONDecodeError:
            return response(400, {
                "message": "Request body must contain valid JSON"
            })

        customer_id = request.get("customer_id")
        status = request.get("status")

        if customer_id is None or str(customer_id).strip() == "":
            return response(400, {
                "message": "customer_id is required"
            })

        if status is None:
            return response(400, {
                "message": "status is required"
            })

        if str(status).strip().lower() != "cancelled":
            return response(400, {
                "message": "status must be cancelled"
            })

        connection = get_db_connection()

        restored_items = []

        with connection.cursor() as cursor:

            # ------------------------------------------------
            # GET AND LOCK ORDER
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT
                    id,
                    customer_id,
                    status
                FROM orders
                WHERE id = %s
                AND is_deleted = FALSE
                FOR UPDATE
                """,
                (order_id,)
            )

            order = cursor.fetchone()

            if not order:
                connection.rollback()
                return response(404, {
                    "message": "Order not found"
                })

            # ------------------------------------------------
            # VERIFY CUSTOMER OWNS ORDER
            # ------------------------------------------------

            if str(order["customer_id"]) != str(customer_id):
                connection.rollback()
                return response(403, {
                    "message": "You are not allowed to cancel this order"
                })

            # ------------------------------------------------
            # VALIDATE ORDER STATUS
            # ------------------------------------------------

            current_status = str(order["status"]).lower()

            if current_status == "cancelled":
                connection.rollback()
                return response(400, {
                    "message": "Order is already cancelled"
                })

            if current_status == "completed":
                connection.rollback()
                return response(400, {
                    "message": "Completed orders cannot be cancelled"
                })

            # ------------------------------------------------
            # GET AND LOCK ORDER ITEMS
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT
                    oi.id AS order_item_id,
                    oi.product_id,
                    oi.quantity,
                    p.name AS product_name,
                    p.stock_count
                FROM order_items oi
                INNER JOIN products p
                    ON oi.product_id = p.id
                WHERE oi.order_id = %s
                AND oi.is_deleted = FALSE
                AND p.is_deleted = FALSE
                FOR UPDATE
                """,
                (order_id,)
            )

            items = cursor.fetchall()

            if not items:
                connection.rollback()
                return response(400, {
                    "message": "Order has no active items to restore"
                })

            # ------------------------------------------------
            # RESTORE PRODUCT STOCK
            # ------------------------------------------------

            for item in items:

                new_stock = int(item["stock_count"]) + int(item["quantity"])

                cursor.execute(
                    """
                    UPDATE products
                    SET stock_count = %s
                    WHERE id = %s
                    AND is_deleted = FALSE
                    """,
                    (new_stock, item["product_id"])
                )

                restored_items.append({
                    "product_id": item["product_id"],
                    "product_name": item["product_name"],
                    "quantity_restored": int(item["quantity"]),
                    "stock_after_restore": new_stock
                })

            # ------------------------------------------------
            # CANCEL ORDER
            # ------------------------------------------------

            cursor.execute(
                """
                UPDATE orders
                SET status = 'cancelled',
                    updated_at = CURRENT_TIMESTAMP
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
            "action": "order_cancelled",
            "order_id": order_id,
            "customer_id": customer_id,
            "restored_items": restored_items
        }))

        publish_order_event(
            "OrderCancelled",
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "status": "cancelled",
                "items": restored_items
            }
        )

        return response(
            200,
            {
                "message": "Order cancelled successfully",
                "order_id": order_id,
                "customer_id": customer_id,
                "status": "cancelled",
                "items": restored_items
            }
        )

    except Exception as error:

        if connection:
            try:
                connection.rollback()
            except Exception:
                pass

        logger.error(json.dumps({
            "level": "ERROR",
            "service": "order-processor",
            "action": "order_cancellation_failed",
            "error": str(error)
        }))

        return response(
            500,
            {
                "message": "Order cancellation failed",
                "error": str(error)
            }
        )

    finally:

        if connection:
            try:
                connection.close()
            except Exception:
                pass


# ============================================================
# GET /orders/{id}
# ============================================================

def get_order_by_id(event):

    connection = None

    try:

        path_parameters = event.get("pathParameters") or {}

        order_id = path_parameters.get("id")

        if order_id is None:

            return response(
                400,
                {
                    "message": "Order id is required"
                }
            )

        try:

            order_id = int(order_id)

        except (TypeError, ValueError):

            return response(
                400,
                {
                    "message": "Order id must be a number"
                }
            )

        if order_id <= 0:

            return response(
                400,
                {
                    "message": "Order id must be greater than zero"
                }
            )

        connection = get_db_connection()

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    o.id AS order_id,
                    o.customer_id,
                    c.name AS customer_name,
                    c.email AS customer_email,
                    o.status,
                    o.created_at,
                    o.updated_at,
                    o.deleted_at,
                    o.is_deleted
                FROM orders o
                INNER JOIN customers c
                    ON o.customer_id = c.customer_id
                WHERE o.id = %s
                AND o.is_deleted = FALSE
                """,
                (order_id,)
            )

            order = cursor.fetchone()

            if not order:

                return response(
                    404,
                    {
                        "message": "Order not found"
                    }
                )

            cursor.execute(
                """
                SELECT
                    oi.id AS order_item_id,
                    oi.product_id,
                    p.name AS product_name,
                    oi.quantity,
                    oi.price,
                    oi.created_at
                FROM order_items oi
                INNER JOIN products p
                    ON oi.product_id = p.id
                WHERE oi.order_id = %s
                AND oi.is_deleted = FALSE
                ORDER BY oi.id
                """,
                (order_id,)
            )

            items = cursor.fetchall()

        order["items"] = items

        return response(
            200,
            order
        )

    except Exception as error:

        logger.error(json.dumps({
            "level": "ERROR",
            "service": "order-processor",
            "action": "get_order_failed",
            "error": str(error)
        }))

        return response(
            500,
            {
                "message": "Failed to retrieve order",
                "error": str(error)
            }
        )

    finally:

        if connection:

            try:
                connection.close()
            except Exception:
                pass


# ============================================================
# GET /orders?customerId=X
# ============================================================

def get_orders_by_customer(event):

    connection = None

    try:

        query_parameters = event.get("queryStringParameters") or {}

        customer_id = query_parameters.get("customerId")

        if customer_id is None or str(customer_id).strip() == "":

            return response(
                400,
                {
                    "message": "customerId query parameter is required"
                }
            )

        connection = get_db_connection()

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    customer_id,
                    name,
                    email
                FROM customers
                WHERE customer_id = %s
                AND is_deleted = FALSE
                """,
                (customer_id,)
            )

            customer = cursor.fetchone()

            if not customer:

                return response(
                    404,
                    {
                        "message": "Customer not found"
                    }
                )

            cursor.execute(
                """
                SELECT
                    o.id AS order_id,
                    o.customer_id,
                    o.status,
                    o.created_at,
                    o.updated_at,

                    oi.id AS order_item_id,
                    oi.product_id,
                    p.name AS product_name,
                    oi.quantity,
                    oi.price

                FROM orders o

                INNER JOIN order_items oi
                    ON o.id = oi.order_id

                INNER JOIN products p
                    ON oi.product_id = p.id

                WHERE o.customer_id = %s
                AND o.is_deleted = FALSE
                AND oi.is_deleted = FALSE

                ORDER BY o.created_at DESC, oi.id
                """,
                (customer_id,)
            )

            rows = cursor.fetchall()

        # ----------------------------------------------------
        # GROUP ITEMS UNDER EACH ORDER
        # ----------------------------------------------------

        orders = {}

        for row in rows:

            order_id = row["order_id"]

            if order_id not in orders:

                orders[order_id] = {
                    "order_id": row["order_id"],
                    "customer_id": row["customer_id"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "items": []
                }

            orders[order_id]["items"].append({
                "order_item_id": row["order_item_id"],
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "quantity": row["quantity"],
                "price": row["price"]
            })

        order_list = list(orders.values())

        return response(
            200,
            {
                "customer_id": customer_id,
                "orders": order_list,
                "count": len(order_list)
            }
        )

    except Exception as error:

        logger.error(json.dumps({
            "level": "ERROR",
            "service": "order-processor",
            "action": "get_customer_orders_failed",
            "error": str(error)
        }))

        return response(
            500,
            {
                "message": "Failed to retrieve customer orders",
                "error": str(error)
            }
        )

    finally:

        if connection:

            try:
                connection.close()
            except Exception:
                pass


# ============================================================
# MAIN LAMBDA HANDLER
# ============================================================

def lambda_handler(event, context):

    try:

        http_method = event.get("httpMethod", "").upper()

        resource = event.get("resource", "")

        path = event.get("path", "")

        logger.info(json.dumps({
            "level": "INFO",
            "service": "order-processor",
            "action": "request_received",
            "http_method": http_method,
            "resource": resource,
            "path": path
        }))

        # ====================================================
        # POST /orders
        # ====================================================

        if http_method == "POST" and resource == "/orders":

            return create_order(event)

        # ====================================================
        # GET /orders/{id}
        # ====================================================

        if http_method == "GET" and resource == "/orders/{id}":

            return get_order_by_id(event)

        # ====================================================
        # PATCH /orders/{id}
        # ====================================================

        if http_method == "PATCH" and resource == "/orders/{id}":

            return cancel_order(event)

        # ====================================================
        # GET /orders?customerId=X
        # ====================================================

        if http_method == "GET" and resource == "/orders":

            return get_orders_by_customer(event)

        # ====================================================
        # UNSUPPORTED ROUTE
        # ====================================================

        return response(
            404,
            {
                "message": "Order API route not found"
            }
        )

    except Exception as error:

        logger.error(json.dumps({
            "level": "ERROR",
            "service": "order-processor",
            "action": "request_failed",
            "error": str(error)
        }))

        return response(
            500,
            {
                "message": "Internal server error",
                "error": str(error)
            }
        )
