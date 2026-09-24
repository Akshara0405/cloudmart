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

        with connection.cursor() as cursor:
            query = """
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
                                THEN 1
                                ELSE 0
                            END
                        ),
                        0
                    ) AS confirmed_orders,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN LOWER(TRIM(status)) = 'failed'
                                THEN 1
                                ELSE 0
                            END
                        ),
                        0
                    ) AS failed_orders
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
            "failed_orders": 0
        }

    finally:
        if connection:
            connection.close()


def get_dashboard_revenue():
    """Return revenue generated by confirmed, non-deleted orders."""
    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COALESCE(
                        SUM(oi.quantity * oi.price),
                        0
                    ) AS total_revenue
                FROM orders o
                INNER JOIN order_items oi
                    ON o.id = oi.order_id
                    AND oi.is_deleted = FALSE
                WHERE o.is_deleted = FALSE
                  AND LOWER(TRIM(o.status)) = 'confirmed'
                """
            )

            row = cursor.fetchone() or {}

            return row.get("total_revenue", 0)

    except Exception as error:
        print(f"Revenue query error: {error}")
        return 0

    finally:
        if connection:
            connection.close()


def get_customer_summary():
    """Return customer information and confirmed-order spending."""
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
                            WHEN LOWER(TRIM(o.status)) = 'confirmed'
                            THEN o.id
                        END
                    ) AS confirmed_orders,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN LOWER(TRIM(o.status)) = 'confirmed'
                                THEN oi.quantity * oi.price
                                ELSE 0
                            END
                        ),
                        0
                    ) AS total_spent
                FROM customers c
                LEFT JOIN orders o
                    ON c.customer_id = o.customer_id
                    AND o.is_deleted = FALSE
                LEFT JOIN order_items oi
                    ON o.id = oi.order_id
                    AND oi.is_deleted = FALSE
                WHERE c.is_deleted = FALSE
                GROUP BY
                    c.customer_id,
                    c.name,
                    c.email,
                    c.phone,
                    c.address,
                    c.created_at
                ORDER BY c.created_at DESC, c.customer_id
                LIMIT 100
                """
            )

            return cursor.fetchall()

    except Exception as error:
        print(f"Customer query error: {error}")
        return []

    finally:
        if connection:
            connection.close()


def get_customer_count():
    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS total_customers
                FROM customers
                WHERE is_deleted = FALSE
                """
            )

            row = cursor.fetchone() or {}
            return row.get("total_customers", 0)

    except Exception as error:
        print(f"Customer count query error: {error}")
        return 0

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
        "pending"
    }

    if status_filter not in allowed_statuses:
        status_filter = None

    products = get_products()
    recent_orders = get_recent_orders(status_filter)
    order_counts = get_order_counts()
    total_revenue = get_dashboard_revenue()
    customer_summary = get_customer_summary()
    total_customers = get_customer_count()
    latest_report = get_latest_report()

    return render_template(
        "index.html",
        authenticated=True,
        environment=ENVIRONMENT,
        products=products,
        recent_orders=recent_orders,
        order_counts=order_counts,
        total_revenue=total_revenue,
        customer_summary=customer_summary,
        total_customers=total_customers,
        latest_report=latest_report,
        selected_status=status_filter,
        generated_at=datetime.now(timezone.utc)
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
