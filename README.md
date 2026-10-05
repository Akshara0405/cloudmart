# CloudMart AWS Cloud Project

CloudMart is a serverless AWS-based e-commerce application that provides product management, customer order processing, authentication, operational monitoring, daily reporting, and an administrator dashboard.

The project is deployed in **AWS `ap-south-1` (Mumbai)** and uses **AWS CloudFormation** for infrastructure provisioning and **GitHub Actions** for automated deployment.

---

## 1. Project Goals

CloudMart is designed to demonstrate:

- Secure AWS cloud architecture
- REST API development using Amazon API Gateway
- Serverless application processing with AWS Lambda
- Authentication and authorization using a Lambda Authorizer
- Private connectivity to Amazon RDS MySQL
- Secure configuration management using AWS Systems Manager Parameter Store
- Event-driven processing with Amazon EventBridge
- Notifications using Amazon SNS
- Monitoring using Amazon CloudWatch
- Daily report generation and storage in Amazon S3
- An EC2-hosted administrator dashboard
- Infrastructure as Code using AWS CloudFormation
- CI/CD using GitHub Actions
- Environment-based resource naming and configuration

---

## 2. Architecture Overview


                           ┌──────────────────────┐
                           │      GitHub Actions  │
                           │      CI/CD Pipeline  │
                           └──────────┬───────────┘
                                      │
                                      ▼
                           ┌──────────────────────┐
                           │    CloudFormation    │
                           └──────────┬───────────┘
                                      │
       ┌──────────────────────────────┼─────────────────────────────┐
       │                              │                             │
       ▼                              ▼                             ▼
┌───────────────┐             ┌───────────────┐             ┌───────────────┐
│ API Gateway   │             │ EC2 Dashboard │             │ CloudWatch    │
│ REST API      │             │ Flask App     │             │ Monitoring    │
└───────┬───────┘             └───────┬───────┘             └───────┬───────┘
        │                              │                             │
        ▼                              │                             ▼
┌───────────────┐                      │                       ┌───────────────┐
│ Lambda        │                      │                       │ SNS           │
│ Authorizer    │                      │                       │ Notifications │
└───────┬───────┘                      │                       └───────────────┘
        │                              │
        ├──────────────────────┐       │
        ▼                      ▼       │
┌───────────────┐       ┌───────────────┐
│ Product       │       │ Order         │
│ Lambda        │       │ Processor     │
└───────┬───────┘       └───────┬───────┘
        │                       │
        └───────────┬───────────┘
                    ▼
             ┌───────────────┐
             │ RDS MySQL     │
             │ Private       │
             └───────────────┘

Product / Order events
          │
          ▼
┌──────────────────┐
│ Amazon EventBridge│
└─────────┬────────┘
          │
          ▼
       Amazon SNS

Daily reporting:
RDS → Report Lambda → S3 reports bucket
```

---

## 3. AWS Services Used

- **Amazon VPC** — Purpose: Provides the project network
- **Amazon API Gateway** — Purpose: Exposes the REST API
- **AWS Lambda** — Purpose: Runs application, authorization, order processing, and reporting logic
- **Amazon RDS MySQL** — Purpose: Stores CloudMart application data
- **AWS Systems Manager Parameter Store** — Purpose: Stores database, authentication, and storage configuration
- **Amazon S3** — Purpose: Stores Lambda deployment packages and generated reports
- **Amazon EC2** — Purpose: Hosts the administrator Flask dashboard
- **Amazon EventBridge** — Purpose: Handles application events and scheduled reporting
- **Amazon SNS** — Purpose: Sends order, low-stock, and alarm notifications
- **Amazon CloudWatch** — Purpose: Provides metrics, alarms, and an operations dashboard
- **AWS IAM** — Purpose: Controls permissions for AWS resources
- **AWS CloudFormation** — Purpose: Defines and provisions infrastructure
- **GitHub Actions** — Purpose: Automates deployment and infrastructure validation

No NAT Gateway is required. Private workloads use the configured VPC endpoints for required AWS service connectivity.

---

## 4. Network Architecture

The application is deployed in a VPC using the following CIDR ranges:

- **VPC** — CIDR / Location: `10.0.0.0/16`
- **Public subnet** — CIDR / Location: `10.0.1.0/24`
- **Private subnet** — CIDR / Location: `10.0.2.0/24`
- **Private subnet 2** — CIDR / Location: `10.0.3.0/24`
- **AWS Region** — CIDR / Location: `ap-south-1`

### Private connectivity

The private subnets contain the Lambda functions and RDS connectivity.

VPC endpoints are configured for the AWS services required by private workloads, including:

- Amazon S3
- Systems Manager
- EventBridge
- SNS
- CloudWatch monitoring

Security groups restrict communication between:

- Lambda and RDS
- Lambda and VPC endpoints
- EC2 dashboard and required application resources

RDS is not publicly accessible.

---

## 5. Application Components

### 5.1 API Gateway

The REST API provides product and order operations.

API base URL format:


https://{api-id}.execute-api.ap-south-1.amazonaws.com/{environment}


For the current `dev` environment:

```text
https://{api-id}.execute-api.ap-south-1.amazonaws.com/dev
```

The API stage is based on the environment name.

### Product endpoints

- **GET** — Endpoint: `/products`; Authentication: Public
- **GET** — Endpoint: `/products/{id}`; Authentication: Public
- **POST** — Endpoint: `/products`; Authentication: Admin
- **PUT** — Endpoint: `/products/{id}`; Authentication: Admin
- **DELETE** — Endpoint: `/products/{id}`; Authentication: Admin

### Order endpoints

- **POST** — Endpoint: `/orders`; Authentication: Customer/Admin
- **GET** — Endpoint: `/orders?customerId={id}`; Authentication: Customer/Admin
- **GET** — Endpoint: `/orders/{id}`; Authentication: Customer/Admin
- **PATCH** — Endpoint: `/orders/{id}`; Authentication: Customer/Admin

The customer authorization logic prevents a customer from accessing another customer's orders.

---

## 6. Authentication and Authorization

CloudMart uses an **API Gateway REQUEST Lambda Authorizer**.

Authentication is based on:


Authorization: Bearer <token>


Customer requests also provide:

```text
Customer-Id: CUST001
```

The authorizer validates the token against the token records stored in the database.

### Customer access

Customers can:

- View products
- View individual products
- Create orders
- View their own orders
- View their own individual order
- Cancel their own order

### Admin access

Administrators can access the administrative operations, including:

- Product creation
- Product updates
- Product deletion
- Order administration
- Order viewing

The admin token does not require a `Customer-Id` header.

Authentication tokens are supplied through RDS



## 7. Product Service

The Product Lambda provides CRUD operations for products.

Main responsibilities:

- Create products
- Read products
- Update products
- Soft-delete products
- Validate product data
- Publish inventory change events
- Connect securely to RDS

Product records contain information such as:

- Product ID
- Name
- Description
- Price
- Category
- Stock count
- Creation time
- Deletion state

Deleted records are retained in the database using the `is_deleted` and `deleted_at` fields instead of being physically removed.


## 8. Order Processing

The Order Processor Lambda handles the order lifecycle.

### Order creation

A customer creates an order by sending product IDs and quantities.

Example:


{
  "items": [
    {
      "product_id": 1,
      "quantity": 2
    },
    {
      "product_id": 2,
      "quantity": 1
    }
  ]
}


For a customer request, the customer identity comes from the Lambda Authorizer context.

An administrator can provide the customer ID in the request body when creating an order.

The order processor:

1. Validates the request.
2. Validates the customer.
3. Validates products and quantities.
4. Checks available inventory.
5. Creates the order and order items.
6. Updates inventory.
7. Publishes the appropriate application events.
8. Publishes CloudWatch custom metrics.
9. Returns the order result.

Orders use statuses such as:

- `pending`
- `confirmed`
- `failed`
- `cancelled`

Order cancellation

Orders can be cancelled using:


PATCH /orders/{id}


Example body:


{
  "status": "cancelled"
}


The order processor verifies ownership for customer requests and restores the appropriate product inventory when an order is cancelled.



9. Database

CloudMart uses **Amazon RDS for MySQL**.

The database is:

- MySQL
- Private
- Encrypted
- Non-publicly accessible
- Deployed using a DB subnet group spanning two private subnets
- Connected to Lambda through security-group rules

The project does not use RDS Multi-AZ.

## Main tables

- categories — Purpose: Product categories
- products — Purpose: Product catalogue and inventory
- customers — Purpose: Customer information
- orders — Purpose: Order records and status
- order_items — Purpose: Products belonging to orders
- order_status — Purpose: Supported order statuses
- tokens — Purpose: Customer and administrator authentication records

The main database schema is maintained in:

database/schema.sql

The Lambda deployment also packages the schema where required for initialization.


 10. Systems Manager Parameter Store

Sensitive and environment-specific configuration is stored in Parameter Store.

Database parameters follow the environment-based structure:

/cloudmart/{environment}/database/host
/cloudmart/{environment}/database/port
/cloudmart/{environment}/database/name
/cloudmart/{environment}/database/username
/cloudmart/{environment}/database/password


Authentication parameters include:


/cloudmart/{environment}/auth/customer-token
/cloudmart/{environment}/auth/admin-token

The reports bucket is stored as:

/cloudmart/{environment}/storage/reports-bucket


Database passwords and authentication values are handled as protected configuration and are not committed to the repository.



 11. Event-Driven Processing

CloudMart uses Amazon EventBridge for application events.

Important application events include:

- `InventoryChanged`
- `OrderConfirmed`
- `OrderFailed`
- `OrderCancelled`

# Low-stock processing

When inventory changes and the product reaches the configured low-stock threshold:


Product Lambda
      ↓
EventBridge
      ↓
Low-stock SNS topic
      ↓
Email notification


The monitoring stack also records a `LowStockEvents` CloudWatch metric and provides an alarm for low-stock events.



12. Notifications

Amazon SNS is used for operational email notifications.

Notification categories include:

- Order confirmed
- Order failed
- Order cancelled
- Low-stock alerts
- CloudWatch alarm notifications

The monitoring stack contains separate notification topics and email subscriptions.

The email address for alerts is provided as a deployment parameter/secret and is not hardcoded in application code.



13. Monitoring and CloudWatch

CloudMart includes an operations monitoring stack.

The CloudWatch dashboard is named:


cloudmart-operations


The project also publishes custom application metrics in the `cloudmart` namespace, including metrics for:

- Orders placed
- Orders failed
- Orders cancelled
- Low-stock events

## Configured alarms

The monitoring stack includes alarms for:

- Lambda error rate
- Failed orders
- RDS CPU utilization
- API Gateway 5xx error rate
- Cancelled orders
- Low-stock events
- RDS free storage
- Lambda throttles

Alarm notifications are delivered through SNS.



14. Daily Reporting

The Report Lambda generates a daily CSV report from the CloudMart database.

Flow:


EventBridge schedule
        ↓
Report Lambda
        ↓
RDS MySQL
        ↓
CSV generation
        ↓
S3 reports bucket

Reports are stored using a date-based key:


reports/daily-report-YYYY-MM-DD.csv


The daily EventBridge schedule is defined in the report CloudFormation stack.

The deployment pipeline also invokes the Report Lambda once after deployment to verify that report generation and S3 storage are working.



15. Administrator Dashboard

The administrator dashboard is a Flask application hosted on Amazon EC2.

The dashboard provides operational views such as:

- Product inventory
- Low-stock products
- Customer information
- Order counts
- Recent orders
- Confirmed orders
- Failed orders
- Cancelled orders
- Revenue/business metrics
- Latest daily report

Dashboard source files:


dashboard/app.py
dashboard/templates/index.html
dashboard/requirements.txt


The EC2 instance uses an IAM instance profile to access the required AWS resources.

The dashboard retrieves database configuration from Parameter Store and report objects from S3.

The Flask session uses secure cookie settings and a locally generated application secret.



16. CloudFormation Stacks

Infrastructure is separated into CloudFormation stacks.

- `cloudmart-{environment}-network` — Purpose: VPC, subnets, routes, security groups, VPC endpoints
- `cloudmart-{environment}-data-newversion` — Purpose: RDS, S3 reports bucket, database parameters
- `cloudmart-{environment}-iam` — Purpose: Lambda IAM roles and permissions
- `cloudmart-{environment}-auth` — Purpose: Authentication parameters and Lambda Authorizer
- `cloudmart-{environment}-api` — Purpose: API Gateway, Product Lambda, Order Processor Lambda
- `cloudmart-{environment}-monitoring` — Purpose: CloudWatch, SNS, EventBridge rules and alarms
- `cloudmart-{environment}-report` — Purpose: Report Lambda and daily EventBridge schedule
- `cloudmart-{environment}-dashboard` — Purpose: EC2 administrator dashboard

The repository also contains an RDS connectivity test stack used by the deployment workflow to validate database connectivity.

 17. Repository Structure


cloudmart/
├── .github/
│   └── workflows/
│       ├── deploy.yaml
│       └── infrastructure.yaml
│
├── cloudformation/
│   ├── network-stack.yaml
│   ├── data-stack.yaml
│   ├── iam-stack.yaml
│   ├── auth-stack.yaml
│   ├── api-stack.yaml
│   ├── monitoring-stack.yaml
│   ├── report-stack.yaml
│   ├── dashboard-stack.yaml
│   └── rds-test-stack.yaml
│
├── database/
│   └── schema.sql
│
├── lambda/
│   ├── lambda-authorizer/
│   │   ├── index.py
│   │   └── requirements.txt
│   │
│   ├── product-lambda/
│   │   ├── index.py
│   │   └── requirements.txt
│   │
│   ├── order-processor/
│   │   ├── index.py
│   │   └── requirements.txt
│   │
│   ├── report-lambda/
│   │   ├── index.py
│   │   └── requirements.txt
│   │
│   
│
├── dashboard/
│   ├── app.py
│   ├── requirements.txt
│   └── templates/
│       └── index.html
│
├── postman/
│   ├── collections/
│   └── globals/
│
└── README.md


Generated deployment ZIP files and bundled dependencies should be treated as deployment artifacts rather than primary source files.



18. CI/CD Pipeline

The main deployment workflow is:


GitHub Actions
      ↓
CloudFormation YAML validation
      ↓
Network
      ↓
Data / RDS
      ↓
IAM
      ↓
Authentication
      ↓
API
      ↓
RDS connectivity/schema validation
      ↓
Monitoring
      ↓
Reporting
      ↓
EC2 Dashboard


The workflow uses GitHub Actions OIDC to assume an AWS IAM role.

AWS credentials are not stored as long-lived access keys in the workflow.

## Required GitHub secrets

The deployment workflow expects these secrets:


AWS_ROLE_ARN
DB_USERNAME
DB_PASSWORD
CLOUDMART_AUTH_TOKEN
CLOUDMART_ADMIN_TOKEN
ALERT_EMAIL


Do not commit these values to the repository.

 19. Deployment

## Prerequisites

Before deployment, make sure you have:

- An AWS account
- AWS region configured as `ap-south-1`
- A GitHub repository
- GitHub Actions enabled
- An IAM role configured for GitHub Actions OIDC
- The required GitHub repository secrets
- Appropriate permissions to create the CloudMart resources

## Deploy through GitHub Actions

The main infrastructure workflow is:


.github/workflows/deploy.yaml


The workflow is manually triggered using:


GitHub → Actions → CloudMart Infrastructure → Run workflow


The current workflow environment is:


ENVIRONMENT=dev
AWS_REGION=ap-south-1

After deployment, review the CloudFormation stack outputs to obtain values such as the API URL and deployed resource information.



 20. API Testing

The repository contains Postman collection files under:


postman/


Typical testing should cover:

## Products

- List products
- Get a product
- Create a product as admin
- Update a product as admin
- Delete a product as admin

### Orders

- Create an order as a customer
- Retrieve customer orders
- Retrieve an individual order
- Cancel an order
- Verify inventory changes
- Verify failed-order behavior
- Verify low-stock notifications

### Monitoring

- Confirm custom CloudWatch metrics are published
- Confirm alarms transition correctly when their thresholds are reached
- Confirm SNS notifications are delivered

### Reporting

- Invoke the report Lambda
- Verify the CSV is generated
- Verify the report exists in the S3 reports bucket

---

21. Security Practices

The project follows these security practices:

- RDS is not publicly accessible.
- Lambda functions run in private subnets.
- Database access is controlled by security groups.
- AWS service access from private workloads uses VPC endpoints.
- IAM roles are used for AWS service access.
- Resource-specific IAM permissions are used instead of unnecessary broad permissions.
- Authentication tokens are stored outside application source code.
- Database passwords are stored in protected Parameter Store parameters.
- GitHub Actions uses OIDC instead of storing long-lived AWS access keys.
- EC2 uses an IAM instance profile instead of hardcoded AWS credentials.
- EC2 instance metadata tokens are required.
- S3 public access is blocked for the reports bucket.
- Environment names are parameterized in CloudFormation.



22. Environment Configuration

CloudFormation templates accept an environment parameter:


dev
prod


Resource names follow the environment naming pattern:


CloudMart-{Environment}-...


This allows the same CloudFormation templates to be reused for different environments without hardcoding environment-specific resource names.


23. Important Operational Notes

### Database initialization

The deployment workflow initializes the database schema through the Product Lambda using the `init_schema` action.

The workflow then verifies that the Product Lambda can connect to the database.

### Report generation

The deployment workflow generates an initial report after the report Lambda is deployed. This verifies:

- Database connectivity
- Report Lambda execution
- CSV generation
- S3 access
- Report object creation

### Dashboard deployment

The dashboard source files are uploaded to the reports bucket during deployment, and the EC2 dashboard stack is then deployed.

---

24. Main Source Files

The most important source files are:

- `cloudformation/network-stack.yaml` — Purpose: Network infrastructure
- `cloudformation/data-stack.yaml` — Purpose: RDS, S3 and database parameters
- `cloudformation/iam-stack.yaml` — Purpose: IAM roles and permissions
- `cloudformation/auth-stack.yaml` — Purpose: Authentication infrastructure
- `cloudformation/api-stack.yaml` — Purpose: API Gateway and application Lambdas
- `cloudformation/monitoring-stack.yaml` — Purpose: Monitoring, alarms and notifications
- `cloudformation/report-stack.yaml`— Purpose: Daily reporting
- `cloudformation/dashboard-stack.yaml` — Purpose: EC2 dashboard
- `lambda/lambda-authorizer/index.py` — Purpose: Authentication and authorization
- `lambda/product-lambda/index.py` — Purpose: Product CRUD service
- `lambda/order-processor/index.py` — Purpose: Order processing service
- `lambda/report-lambda/index.py` — Purpose: Daily report generation
- `dashboard/app.py` — Purpose: Administrator dashboard backend
- `dashboard/templates/index.html` — Purpose: Dashboard UI
- `database/schema.sql` — Purpose: Database schema



25. Project Outcome

CloudMart provides an end-to-end AWS cloud application covering:

- Infrastructure provisioning
- Networking
- IAM
- Authentication
- REST APIs
- Serverless application logic
- Relational database storage
- Event-driven processing
- Notifications
- Monitoring and alarms
- Scheduled reporting
- S3 report storage
- EC2 administration dashboard
- Automated CI/CD

The project is designed so that infrastructure and application components can be deployed consistently using the same environment-aware CloudFormation templates and GitHub Actions workflow.
