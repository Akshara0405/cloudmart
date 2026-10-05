# CloudMart Deployment Runbook

**Repository:** `https://github.com/Akshara0405/cloudmart`  
**Region:** `ap-south-1`  
**Deployment:** GitHub Actions + AWS CloudFormation  
**Environments:** `dev` / `prod`

---

## 1. New Machine Setup

Install:

1. Git
2. Python 3
3. AWS CLI

Check installation:

```bash
git --version
python --version
aws --version
```

Clone the project:

```bash
git clone https://github.com/Akshara0405/cloudmart.git
cd cloudmart
```

Create a Python virtual environment if local testing is required:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Install dashboard/local dependencies when required:

```bash
pip install -r dashboard/requirements.txt
```

---

## 2. AWS Account Setup

Use an AWS account with permission to create the CloudMart infrastructure.

Set the AWS region to:

```text
ap-south-1
```

The deployment uses GitHub Actions OIDC, so AWS access keys do **not** need to be stored in GitHub.

### Create GitHub OIDC provider

In AWS:

1. Open **IAM**.
2. Open **Identity providers**.
3. Add an OpenID Connect provider.
4. Provider URL:

```text
https://token.actions.githubusercontent.com
```

5. Audience:

```text
sts.amazonaws.com
```

---

## 3. Create the GitHub Actions IAM Role

In AWS IAM:

1. Create a role for GitHub Actions.
2. Select **Web identity** as the trusted entity.
3. Select the GitHub OIDC provider.
4. Set the audience to `sts.amazonaws.com`.
5. Restrict the trust policy to the CloudMart GitHub repository and the branches used for deployment.
6. Give the role the permissions required by the CloudMart CloudFormation deployment.
7. Copy the role ARN.

The role ARN will be added to GitHub as:

```text
AWS_ROLE_ARN
```

---

## 4. Configure GitHub Repository Secrets

Open:

**GitHub → CloudMart repository → Settings → Secrets and variables → Actions**

Create these repository secrets:

| Secret | Value |
|---|---|
| `AWS_ROLE_ARN` | ARN of the GitHub Actions IAM role |
| `DB_USERNAME` | RDS database username |
| `DB_PASSWORD` | RDS database password |
| `CLOUDMART_AUTH_TOKEN` | Customer authentication token |
| `CLOUDMART_ADMIN_TOKEN` | Admin authentication token |
| `ALERT_EMAIL` | Email address for CloudMart alerts |

Do not commit passwords or tokens into the repository.

---

## 5. Select the Environment

Open:

```text
.github/workflows/deploy.yaml
```

Set:

```yaml
env:
  ENVIRONMENT: dev
  AWS_REGION: ap-south-1
```

For production:

```yaml
env:
  ENVIRONMENT: prod
  AWS_REGION: ap-south-1
```

The CloudFormation templates use the environment value when creating resource names and environment-specific resources.

---

## 6. Check the Repository Before Deployment

Confirm these exist:

```text
.github/workflows/deploy.yaml

cloudformation/
├── network-stack.yaml
├── data-stack.yaml
├── iam-stack.yaml
├── auth-stack.yaml
├── api-stack.yaml
├── rds-test-stack.yaml
├── monitoring-stack.yaml
├── report-stack.yaml
└── dashboard-stack.yaml

database/
└── schema.sql

lambda/
├── lambda-authorizer/
├── product-lambda/
├── order-processor/
└── report-lambda/

dashboard/
├── app.py
├── requirements.txt
└── templates/
    └── index.html
```

Commit and push the code:

```bash
git add .
git commit -m "CloudMart deployment"
git push origin main
```

---

## 7. Run the Deployment

Open:

**GitHub → CloudMart repository → Actions → CloudMart Infrastructure Deployment**

Select:

**Run workflow**

Select the required branch and start the workflow.

The workflow deploys the stacks in this order:

```text
1. Network
2. Data
3. IAM
4. Auth
5. API
6. RDS Test
7. Product Lambda schema initialization
8. Monitoring
9. Reporting
10. Dashboard
```

Wait for all jobs to complete successfully.

---

## 8. Database Schema Initialization

The deployment automatically invokes the existing Product Lambda with:

```json
{
  "body": "{"action":"init_schema"}"
}
```

This initializes the MySQL database using:

```text
database/schema.sql
```

No separate schema Lambda needs to be created manually.

---

## 9. Verify the Deployment

### CloudFormation

In AWS:

**CloudFormation → Stacks**

Check that the environment stacks show:

```text
CREATE_COMPLETE
```

or:

```text
UPDATE_COMPLETE
```

Expected stack names include:

```text
cloudmart-dev-network
cloudmart-dev-data-newversion
cloudmart-dev-iam
cloudmart-dev-auth
cloudmart-dev-api
cloudmart-dev-rds-test
cloudmart-dev-monitoring
cloudmart-dev-report
cloudmart-dev-dashboard
```

For production, replace `dev` with `prod`.

### API Gateway

Open the API stack outputs and copy the API URL.

Test:

```text
/products
```

and the order endpoints:

```text
/orders
/orders/{id}
```

Use the required authentication token.

### Database

Verify that the schema was initialized and the required tables exist:


categories
products
customers
order_status
orders
order_items
tokens

### Dashboard

Open the `DashboardURL` from the dashboard CloudFormation stack output.

Confirm that the dashboard loads and displays the CloudMart information.

### Reports

Check the report S3 bucket for:

```text
reports/daily-report-YYYY-MM-DD.csv
```

### Notifications

Confirm the configured alert email receives the CloudMart notification/monitoring emails.

---

## 10. If Deployment Fails

1. Open **GitHub → Actions**.
2. Open the failed workflow.
3. Open the failed job.
4. Read the error message.
5. If the error is from CloudFormation, open **AWS → CloudFormation → Stack → Events**.
6. Fix the source/configuration in Git.
7. Commit and push the fix.
8. Run the workflow again.

Do not manually create replacement CloudMart resources when the deployment fails.

---

## 11. Production Deployment

Before deploying production:

1. Make sure the required code is committed and tested.
2. Confirm the GitHub secrets are configured.
3. Change:

```yaml
ENVIRONMENT: prod
```

4. Push the change.
5. Run the GitHub Actions workflow.
6. Verify all production stacks.
7. Test the production API.
8. Verify the dashboard, reports, database, and notifications.

---
