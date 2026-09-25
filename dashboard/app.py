import os
import secrets
from datetime import datetime, timezone

import boto3
import pymysql
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)

ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")

app.config["ENVIRONMENT"] = ENVIRONMENT
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False

SECRET_FILE = "/opt/cloudmart-dashboard/.flask_secret"


def load_flask_secret():
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "r", encoding="utf-8") as file:
            return file.read().strip()

    secret = secrets.token_hex(32)
    os.makedirs(os.path.dirname(SECRET_FILE), exist_ok=True)

    with open(SECRET_FILE, "w", encoding="utf-8") as file:
        file.write(secret)

    os.chmod(SECRET_FILE, 0o600)
    return secret


app.secret_key = load_flask_secret()

ssm = boto3.client("ssm", region_name=AWS_REGION)
s3 = boto3.client("s3", region_name=AWS_REGION)


def get_ssm_parameter(name, secure=False):
    response = ssm.get_parameter(
        Name=name,
        WithDecryption=secure
    )
    return response["Parameter"]["Value"]


def get_db_connection():
    host = get_ssm_parameter(
        f"/cloudmart/{ENVIRONMENT}/database/host"
    )

    port = int(
        get_ssm_parameter(
            f"/cloudmart/{ENVIRONMENT}/database/port"
        )
    )

    database = get_ssm_parameter(
        f"/cloudmart/{ENVIRONMENT}/database/name"
    )

    username = get_ssm_parameter(
        f"/cloudmart/{ENVIRONMENT}/database/username"
    )

    password = get_ssm_parameter(
        f"/cloudmart/{ENVIRONMENT}/database/password",
        secure=True
    )

    return pymysql.connect(
        host=host,
        port=port,
        user=username,
        password=password,
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=10,
        write_timeout=10
    )


def authenticate_admin_token(provided_token):
    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    role,
                    is_active
                FROM tokens
                WHERE token_hash = %s
                  AND role = 'admin'
                  AND is_active = TRUE
                  AND (
                      expires_at IS NULL
                      OR expires_at > NOW()
                  )
                LIMIT 1
                """,
                (provided_token,)
            )

            return cursor.fetchone()

    except Exception as error:
        print(f"Authentication error: {error}")
        return None

    finally:
        if connection:
            connection.close()


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

    except Exception as error:
        print(f"Product query error: {error}")
        return []

    finally:
        if connection:
            connection.close()


def get_recent_orders(status_filter=None):
    connection = None

    try:
        connection = get_db_connection()

        query = """
            SELECT
                o.id AS order_id,
                o.customer_id,
                c.name AS customer_name,
                c.email AS customer_email,
                o.status,
                o.created_at,
                oi.product_id,
                p.name AS product_name,
                oi.quantity,
                oi.price,
                (oi.quantity * oi.price) AS line_total,
                o.failure_reason,
                o.failure_product_id,
                o.failure_quantity,
                o.failure_available_stock
            FROM orders o
            LEFT JOIN customers c
                ON o.customer_id = c.customer_id
                AND c.is_deleted = FALSE
            LEFT JOIN order_items oi
                ON o.id = oi.order_id
                AND oi.is_deleted = FALSE
            LEFT JOIN products p
                ON oi.product_id = p.id
            WHERE o.is_deleted = FALSE
        """

        parameters = []

        if status_filter:
            query += """
                AND LOWER(TRIM(o.status)) = %s
            """
            parameters.append(status_filter)

        query += """
            ORDER BY o.created_at DESC, oi.id DESC
            LIMIT 50
        """

        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            return cursor.fetchall()

    except Exception as error:
        print(f"Order query error: {error}")
        return []

    finally:
        if connection:
            connection.close()


def get_order_counts():
    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_orders,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN LOWER(TRIM(status)) = 'confirmed'
                                THEN 1 ELSE 0
                            END
                        ), 0
                    ) AS confirmed_orders,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN LOWER(TRIM(status)) = 'failed'
                                THEN 1 ELSE 0
                            END
                        ), 0
                    ) AS failed_orders,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN LOWER(TRIM(status)) = 'pending'
                                THEN 1 ELSE 0
                            END
                        ), 0
                    ) AS pending_orders,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN LOWER(TRIM(status)) = 'cancelled'
                                THEN 1 ELSE 0
                            END
                        ), 0
                    ) AS cancelled_orders
                FROM orders
                WHERE is_deleted = FALSE
                """
            )

            return cursor.fetchone()

    except Exception as error:
        print(f"Order count query error: {error}")

        return {
            "total_orders": 0,
            "confirmed_orders": 0,
            "failed_orders": 0,
            "pending_orders": 0,
            "cancelled_orders": 0
        }

    finally:
        if connection:
            connection.close()


def get_business_metrics():
    """
    Dashboard-level business metrics.

    Revenue is calculated from confirmed, non-deleted order items only.
    This prevents failed/pending/cancelled orders from being counted as sales.
    """
    connection = None

    result = {
        "total_revenue": 0,
        "confirmed_revenue": 0,
        "total_customers": 0,
        "active_customers": 0,
        "total_products": 0,
        "low_stock_products": 0,
        "average_order_value": 0,
        "units_sold": 0,
    }

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COALESCE(
                        SUM(
                            CASE
                                WHEN LOWER(TRIM(o.status)) = 'confirmed'
                                THEN oi.quantity * oi.price
                                ELSE 0
                            END
                        ),
                        0
                    ) AS confirmed_revenue,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN LOWER(TRIM(o.status)) = 'confirmed'
                                THEN oi.quantity
                                ELSE 0
                            END
                        ),
                        0
                    ) AS units_sold,

                    COUNT(
                        DISTINCT CASE
                            WHEN LOWER(TRIM(o.status)) = 'confirmed'
                            THEN o.id
                        END
                    ) AS confirmed_order_count

                FROM orders o
                LEFT JOIN order_items oi
                    ON o.id = oi.order_id
                    AND oi.is_deleted = FALSE
                WHERE o.is_deleted = FALSE
                """
            )

            revenue = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_customers,
                    SUM(
                        CASE
                            WHEN is_deleted = FALSE THEN 1
                            ELSE 0
                        END
                    ) AS active_customers
                FROM customers
                """
            )

            customers = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_products,
                    SUM(
                        CASE
                            WHEN stock_count <= 5 THEN 1
                            ELSE 0
                        END
                    ) AS low_stock_products
                FROM products
                WHERE is_deleted = FALSE
                """
            )

            products = cursor.fetchone()

            confirmed_revenue = float(revenue["confirmed_revenue"] or 0)
            confirmed_order_count = int(
                revenue["confirmed_order_count"] or 0
            )

            result.update(
                {
                    "total_revenue": confirmed_revenue,
                    "confirmed_revenue": confirmed_revenue,
                    "total_customers": int(
                        customers["total_customers"] or 0
                    ),
                    "active_customers": int(
                        customers["active_customers"] or 0
                    ),
                    "total_products": int(
                        products["total_products"] or 0
                    ),
                    "low_stock_products": int(
                        products["low_stock_products"] or 0
                    ),
                    "average_order_value": (
                        confirmed_revenue / confirmed_order_count
                        if confirmed_order_count
                        else 0
                    ),
                    "units_sold": int(revenue["units_sold"] or 0),
                }
            )

            return result

    except Exception as error:
        print(f"Business metrics error: {error}")
        return result

    finally:
        if connection:
            connection.close()


def get_customers():
    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.customer_id,
                    c.name,
                    c.email,
                    c.phone,
                    c.address,
                    c.created_at,

                    COUNT(
                        DISTINCT CASE
                            WHEN o.is_deleted = FALSE
                            THEN o.id
                        END
                    ) AS order_count,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN LOWER(TRIM(o.status)) = 'confirmed'
                                 AND o.is_deleted = FALSE
                                 AND oi.is_deleted = FALSE
                                THEN oi.quantity * oi.price
                                ELSE 0
                            END
                        ),
                        0
                    ) AS total_spent

                FROM customers c

                LEFT JOIN orders o
                    ON c.customer_id = o.customer_id

                LEFT JOIN order_items oi
                    ON o.id = oi.order_id

                WHERE c.is_deleted = FALSE

                GROUP BY
                    c.customer_id,
                    c.name,
                    c.email,
                    c.phone,
                    c.address,
                    c.created_at

                ORDER BY total_spent DESC, c.created_at DESC
                LIMIT 50
                """
            )

            return cursor.fetchall()

    except Exception as error:
        print(f"Customer query error: {error}")
        return []

    finally:
        if connection:
            connection.close()


def get_top_products():
    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.name,
                    p.category,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN LOWER(TRIM(o.status)) = 'confirmed'
                                THEN oi.quantity
                                ELSE 0
                            END
                        ),
                        0
                    ) AS units_sold,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN LOWER(TRIM(o.status)) = 'confirmed'
                                THEN oi.quantity * oi.price
                                ELSE 0
                            END
                        ),
                        0
                    ) AS revenue

                FROM products p

                LEFT JOIN order_items oi
                    ON p.id = oi.product_id
                    AND oi.is_deleted = FALSE

                LEFT JOIN orders o
                    ON oi.order_id = o.id
                    AND o.is_deleted = FALSE

                WHERE p.is_deleted = FALSE

                GROUP BY
                    p.id,
                    p.name,
                    p.category

                ORDER BY revenue DESC

                LIMIT 5
                """
            )

            return cursor.fetchall()

    except Exception as error:
        print(f"Top product query error: {error}")
        return []

    finally:
        if connection:
            connection.close()


def get_daily_revenue():
    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    DATE(o.created_at) AS sale_date,
                    COALESCE(
                        SUM(oi.quantity * oi.price),
                        0
                    ) AS revenue
                FROM orders o
                INNER JOIN order_items oi
                    ON o.id = oi.order_id
                    AND oi.is_deleted = FALSE
                WHERE o.is_deleted = FALSE
                  AND LOWER(TRIM(o.status)) = 'confirmed'
                  AND o.created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
                GROUP BY DATE(o.created_at)
                ORDER BY sale_date
                """
            )

            rows = cursor.fetchall()

            values = {
                str(row["sale_date"]): float(row["revenue"] or 0)
                for row in rows
            }

            # Always return seven calendar days, including zero-revenue days.
            result = []

            from datetime import date, timedelta

            today = date.today()

            for offset in range(6, -1, -1):
                current_day = today - timedelta(days=offset)
                key = str(current_day)

                result.append(
                    {
                        "label": current_day.strftime("%d %b"),
                        "revenue": values.get(key, 0)
                    }
                )

            return result

    except Exception as error:
        print(f"Daily revenue query error: {error}")
        return []

    finally:
        if connection:
            connection.close()


def get_latest_report():
    try:
        bucket = get_ssm_parameter(
            f"/cloudmart/{ENVIRONMENT}/storage/reports-bucket"
        )

        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix="reports/"
        )

        objects = response.get("Contents", [])

        if not objects:
            return None

        latest_object = max(
            objects,
            key=lambda item: item["LastModified"]
        )

        report_key = latest_object["Key"]

        report_url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": report_key
            },
            ExpiresIn=3600
        )

        return {
            "name": report_key.split("/")[-1],
            "last_modified": latest_object["LastModified"],
            "url": report_url
        }

    except Exception as error:
        print(f"Report query error: {error}")
        return None


@app.route("/health")
def health():
    return {
        "service": "cloudmart-dashboard",
        "status": "healthy"
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        token = request.form.get("token", "").strip()

        if not token:
            return render_template(
                "index.html",
                authenticated=False,
                environment=ENVIRONMENT,
                login_error="Please enter an admin token."
            )

        admin = authenticate_admin_token(token)

        if admin:
            session.clear()
            session["authenticated"] = True
            session["role"] = admin["role"]

            return redirect(url_for("dashboard"))

        return render_template(
            "index.html",
            authenticated=False,
            environment=ENVIRONMENT,
            login_error="Invalid admin token."
        )

    return render_template(
        "index.html",
        authenticated=False,
        environment=ENVIRONMENT,
        login_error=None
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def dashboard():
    if not session.get("authenticated"):
        return redirect(url_for("login"))

    status_filter = request.args.get("status", "").strip().lower()

    allowed_statuses = {
        "confirmed",
        "failed",
        "pending",
        "cancelled"
    }

    if status_filter not in allowed_statuses:
        status_filter = None

    products = get_products()
    recent_orders = get_recent_orders(status_filter)
    order_counts = get_order_counts()
    business_metrics = get_business_metrics()
    customers = get_customers()
    top_products = get_top_products()
    daily_revenue = get_daily_revenue()
    latest_report = get_latest_report()

    return render_template(
        "index.html",
        authenticated=True,
        environment=ENVIRONMENT,
        products=products,
        recent_orders=recent_orders,
        order_counts=order_counts,
        business_metrics=business_metrics,
        customers=customers,
        top_products=top_products,
        daily_revenue=daily_revenue,
        latest_report=latest_report,
        selected_status=status_filter,
        generated_at=datetime.now(timezone.utc)
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
