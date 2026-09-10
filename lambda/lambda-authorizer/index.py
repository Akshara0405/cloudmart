import os

import boto3
import pymysql


# ============================================================
# AWS CLIENTS
# ============================================================

ssm = boto3.client("ssm")


# ============================================================
# AUTH PARAMETERS
# ============================================================

CUSTOMER_TOKEN_PARAMETER = os.environ[
    "CUSTOMER_TOKEN_PARAMETER"
]

ADMIN_TOKEN_PARAMETER = os.environ[
    "ADMIN_TOKEN_PARAMETER"
]


# ============================================================
# DATABASE PARAMETERS
# ============================================================

DB_HOST_PARAMETER = os.environ[
    "DB_HOST_PARAMETER"
]

DB_PORT_PARAMETER = os.environ[
    "DB_PORT_PARAMETER"
]

DB_NAME_PARAMETER = os.environ[
    "DB_NAME_PARAMETER"
]

DB_USERNAME_PARAMETER = os.environ[
    "DB_USERNAME_PARAMETER"
]

DB_PASSWORD_PARAMETER = os.environ[
    "DB_PASSWORD_PARAMETER"
]


# ============================================================
# SSM PARAMETER
# ============================================================

def get_parameter(parameter_name):

    response = ssm.get_parameter(
        Name=parameter_name,
        WithDecryption=True
    )

    return response["Parameter"]["Value"]


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
# GENERATE AUTHORIZER POLICY
# ============================================================

def generate_policy(
    principal_id,
    effect,
    resource,
    context=None
):

    policy = {
        "principalId": principal_id,

        "policyDocument": {
            "Version": "2012-10-17",

            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource
                }
            ]
        }
    }

    if context:

        policy["context"] = context

    return policy


# ============================================================
# BUILD METHOD RESOURCE
# ============================================================

def build_method_resource(method_arn):

    return method_arn


# ============================================================
# BUILD STAGE RESOURCE
# ============================================================

def build_stage_resource(method_arn):

    arn_parts = method_arn.split(":")

    api_gateway_arn = arn_parts[5]

    parts = api_gateway_arn.split("/")

    api_id = parts[0]

    stage = parts[1]

    return (
        f"{':'.join(arn_parts[0:5])}:"
        f"{api_id}/{stage}/*/*"
    )


# ============================================================
# CUSTOMER API ACCESS
# ============================================================

def is_customer_allowed(method, path):

    # --------------------------------------------------------
    # GET /products
    # GET /products/{id}
    # --------------------------------------------------------

    if method == "GET" and path.startswith("/products"):
        return True

    # --------------------------------------------------------
    # POST /orders
    # --------------------------------------------------------

    if method == "POST" and path == "/orders":
        return True

    # --------------------------------------------------------
    # GET /orders
    # GET /orders/{id}
    # --------------------------------------------------------

    if method == "GET" and path.startswith("/orders"):
        return True

    # --------------------------------------------------------
    # PATCH /orders/{id}
    # Customer can cancel their own order.
    # Order Processor will verify ownership.
    # --------------------------------------------------------

    if method == "PATCH" and path.startswith("/orders/"):
        return True

    return False


# ============================================================
# CUSTOMER TOKEN LOOKUP
# ============================================================

def get_customer_from_token(provided_token):

    connection = None

    try:

        connection = get_db_connection()

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    customer_id,
                    role,
                    is_active
                FROM tokens
                WHERE token_hash = %s
                AND is_active = TRUE
                LIMIT 1
                """,
                (provided_token,)
            )

            token_record = cursor.fetchone()

        return token_record

    finally:

        if connection:
            connection.close()


# ============================================================
# LAMBDA AUTHORIZE
# ============================================================

def lambda_handler(event, context):

    # --------------------------------------------------------
    # GET AUTHORIZATION HEADER
    # --------------------------------------------------------

    authorization_header = event.get(
        "authorizationToken",
        ""
    )

    if not authorization_header.startswith("Bearer "):

        raise Exception("Unauthorized")

    provided_token = authorization_header[7:].strip()

    if not provided_token:

        raise Exception("Unauthorized")

    # --------------------------------------------------------
    # GET ADMIN TOKEN FROM SSM
    # --------------------------------------------------------

    admin_token = get_parameter(
        ADMIN_TOKEN_PARAMETER
    )

    # --------------------------------------------------------
    # GET METHOD ARN
    # --------------------------------------------------------

    method_arn = event["methodArn"]

    arn_parts = method_arn.split(":")

    api_gateway_arn = arn_parts[5]

    path_parts = api_gateway_arn.split("/")

    if len(path_parts) < 4:

        raise Exception("Unauthorized")

    method = path_parts[2]

    path = "/" + "/".join(path_parts[3:])

    # ========================================================
    # ADMIN TOKEN
    # ========================================================

    if provided_token == admin_token:

        resource = build_stage_resource(
            method_arn
        )

        return generate_policy(
            "cloudmart-admin",
            "Allow",
            resource,
            {
                "role": "admin"
            }
        )

    # ========================================================
    # CUSTOMER TOKEN
    # ========================================================

    customer_record = get_customer_from_token(
        provided_token
    )

    if not customer_record:

        raise Exception("Unauthorized")

    customer_id = customer_record["customer_id"]

    role = customer_record["role"]

    # --------------------------------------------------------
    # Only customer role can use customer permissions.
    # --------------------------------------------------------

    if role != "customer":

        raise Exception("Unauthorized")

    # --------------------------------------------------------
    # Check API permission.
    # --------------------------------------------------------

    if not is_customer_allowed(
        method,
        path
    ):

        raise Exception("Unauthorized")

    # --------------------------------------------------------
    # Allow customer request.
    # Pass authenticated customer information
    # to downstream Lambda through authorizer context.
    # --------------------------------------------------------

    resource = build_method_resource(
        method_arn
    )

    return generate_policy(
        f"cloudmart-customer-{customer_id}",
        "Allow",
        resource,
        {
            "customer_id": str(customer_id),
            "role": str(role)
        }
    )