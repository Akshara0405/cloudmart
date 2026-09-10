import os
import boto3


ssm = boto3.client("ssm")


CUSTOMER_TOKEN_PARAMETER = os.environ[
    "CUSTOMER_TOKEN_PARAMETER"
]

ADMIN_TOKEN_PARAMETER = os.environ[
    "ADMIN_TOKEN_PARAMETER"
]


def get_token(parameter_name):

    response = ssm.get_parameter(
        Name=parameter_name,
        WithDecryption=True
    )

    return response["Parameter"]["Value"]


def generate_policy(principal_id, effect, resource):

    return {
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


def build_method_resource(method_arn):

    return method_arn


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


def is_customer_allowed(method, path):

    if method == "GET" and path.startswith("/products"):
        return True

    if method == "POST" and path == "/orders":
        return True

    if method == "GET" and path.startswith("/orders"):
        return True

    # Customer can cancel their own orders
    if method == "PATCH" and path.startswith("/orders/"):
        return True

    return False


def lambda_handler(event, context):

    authorization_header = event.get(
        "authorizationToken",
        ""
    )

    if not authorization_header.startswith("Bearer "):
        raise Exception("Unauthorized")

    provided_token = authorization_header[7:].strip()

    if not provided_token:
        raise Exception("Unauthorized")

    customer_token = get_token(
        CUSTOMER_TOKEN_PARAMETER
    )

    admin_token = get_token(
        ADMIN_TOKEN_PARAMETER
    )

    method_arn = event["methodArn"]

    arn_parts = method_arn.split(":")
    api_gateway_arn = arn_parts[5]
    path_parts = api_gateway_arn.split("/")

    if len(path_parts) < 4:
        raise Exception("Unauthorized")

    method = path_parts[2]
    path = "/" + "/".join(path_parts[3:])

    if provided_token == admin_token:

        resource = build_stage_resource(
            method_arn
        )

        return generate_policy(
            "cloudmart-admin",
            "Allow",
            resource
        )

    if provided_token == customer_token:

        if is_customer_allowed(
            method,
            path
        ):

            resource = build_method_resource(
                method_arn
            )

            return generate_policy(
                "cloudmart-customer",
                "Allow",
                resource
            )

        raise Exception("Unauthorized")

    raise Exception("Unauthorized")