# Session 10 — Authentication, authorization, identity and roles

**Repo support:** Partly. No teaching material, but the stage-18/20 CloudFormation template contains a good real example to read.

**Concept (20 min):** authentication vs authorization; identity, role, policy, least privilege; credentials vs roles.
**Demo (20 min):** show a forbidden AWS operation, grant an appropriate role, make it work without hard-coded credentials.

## 10 bullets to work from
1. Authentication = who are you? Authorization = what may you do? Use the SSH key from session 7 as the authentication example, and what `ec2-user` may do after login as authorization.
2. AWS vocabulary: account, user (a person), role (a hat a service or user puts on), policy (a JSON document listing allowed or denied actions on resources).
3. Read one real policy together. In `20-final-walkthrough/infra/template.yaml`, `LambdaRole` allows exactly two things: `sqs:SendMessage` on the pick-work queue and `events:PutEvents` on the order event bus, plus the standard Lambda logging policy. Everything else is denied by default.
4. Least privilege: the function can send to one queue; it cannot read it, delete it, or touch another queue. Ask students what an attacker who steals this function's credentials can do (very little).
5. Credentials vs roles: long-lived access keys that live in a file or code are a liability; a role hands out short-lived credentials automatically and nothing needs to be copied.
6. Demo setup: on the EC2 instance from session 7 with **no** role attached, run `aws s3 ls` or `aws sqs list-queues`. It fails (no credentials, or access denied). Show the exact error text and name which of authentication or authorization failed.
7. Create a minimal role (for example read-only to one queue or bucket), attach it to the instance as an instance profile, and rerun the command. It works, and `~/.aws` contains no keys. Show `aws sts get-caller-identity` before and after.
8. Prove least privilege both ways: the allowed command works, a neighbouring command (delete, or another resource) is denied.
9. Contrast with what the repo does for the database: the template passes the DB password to the Lambda as a plain environment variable (`DATABASE_URL`, built from a `NoEcho` CloudFormation parameter). A role cannot replace a database password here; the real-world answer is a secrets service. Say this honestly.
10. Related exposure to point out: the API Gateway methods in `infra/api-gateway.yaml` use `AuthorizationType: NONE`, so anyone with the URL can call them. Authentication for the API is a future decision, not something the course implements.
