# Temporary GYOTO validation on AWS

Prepared on 2026-10-04.
No AWS resources were created during preparation.
No software was downloaded or installed on the Mac.

## Purpose

Run an independent geodesic check with GYOTO on one temporary CPU server.
Keep the existing dashboard and local learned-model experiment.
Compare 24 timelike trajectories at two numerical tolerances.
This bounded run does not check photon paths.
The physics adapter must match coordinates, units, launch velocity, and stopping surfaces.
This server does not prove spacecraft survival or validate a changing spacetime.

## Remote installation manifest

| Item | Purpose |
| --- | --- |
| Canonical Ubuntu Server 24.04 amd64 AMI | Existing operating-system image; publisher checked through EC2 |
| gyoto | Independent C++ geodesic engine |
| python3-gyoto | Packaged Python interface |
| python3-numpy, python3-scipy | Array operations and numerical comparisons |
| Required apt dependencies | Libraries selected by Ubuntu's package resolver |
| Explicit project source files | Physics adapter and its declared imports only |

Ubuntu noble publishes `python3-gyoto` version `2.0.2-1.1build3` for amd64 and arm64.
Its amd64 package is 945 kB and its installed size is 5,553 kB, excluding dependencies.
The total remote package size has not been measured.
The 12 GB root disk limits available installation space.
APT installation is restricted to the temporary server and uses `--no-install-recommends`.
[Official Ubuntu package](https://packages.ubuntu.com/noble/python3-gyoto).

## Resources and cost

Use one `t3.small` Linux instance in `us-east-1`.
It has 2 vCPUs and 2 GiB memory.
Standard CPU credits avoid additional unlimited-credit charges, but sustained work can be throttled.
Use a 12 GB encrypted gp3 root disk with deletion on termination.
Use the existing default VPC and a public subnet.
The instance has a public IPv4 address for outbound package and SSM traffic.
No inbound ports, SSH keys, NAT gateway, load balancer, container build, GPU, or storage bucket are added.

| Charge | Verified rate or planning basis |
| --- | --- |
| Linux t3.small | $0.0208 per hour, verified through AWS Price List API |
| Public IPv4 | $0.005 per hour |
| gp3 storage | $0.08 per GB-month planning rate; 12 GB for one hour is about $0.00132 |
| Combined one-hour compute, IP, disk estimate | $0.02712 before taxes, data transfer, or other account usage |
| Working allowance | Less than $1 for this one small run; $5 remains a conservative planning allowance |

These are cost estimates, not a hard billing cap or a promise that credits cover the service.
The $50 credit balance and service eligibility have not been inspected.
The runner refuses source archives larger than 45,000 base64 bytes.
It limits raw result JSON to 100,000 bytes and the gzip/base64 transport to 20,000 bytes.
[EC2 pricing](https://aws.amazon.com/ec2/pricing/on-demand/), [EBS pricing](https://aws.amazon.com/ebs/pricing/), [IPv4 pricing](https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights/).

## Access and cleanup

CloudFormation creates a temporary instance profile and role with `AmazonSSMManagedInstanceCore`.
The role provides SSM agent access and grants no Secrets Manager or general application-data permissions.
The managed policy normally permits Parameter Store reads, so an explicit deny removes those read actions for this instance.
The security group permits outbound TCP 80 and 443 only and has no ingress rules.
IMDSv2 is required.
SSM Run Command executes the Python adapter, retrieves its JSON, and records command status and diagnostics locally.

The instance schedules shutdown 45 minutes after user-data starts.
Instance-initiated shutdown terminates it and deletes its root disk.
The local runner deletes the full CloudFormation stack in `finally`, including on normal interruption and SIGTERM, and waits for deletion.
It saves the stack name and instance ID in a local state file before remote execution.
An OS boot failure or a killed local process can defeat one cleanup path; these controls do not create an absolute spending cap.
After every run, confirm `DELETE_COMPLETE` and the instance's termination.
If cleanup is blocked, use the saved stack name with `aws cloudformation delete-stack --region us-east-1 --stack-name <saved-stack-name>` and inspect the stack events.
[SSM instance permissions](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonSSMManagedInstanceCore.html).

## Commands

Read-only readiness check:

```sh
python3 cloud/run_gyoto.py
```

Execution after the adapter is ready and the concrete run has been reviewed:

```sh
python3 cloud/run_gyoto.py --run \
  --entry run_gyoto_check.py \
  --files run_gyoto_check.py physics.py \
  --output results/gyoto-cloud-run.json
```

The entry script must emit compact JSON to standard output and finish within 600 seconds.
It runs as `/usr/bin/python3` from `/opt/gyoto-check` on the remote instance.
The adapter is `run_gyoto_check.py`; its only uploaded project import is `physics.py`.
No local Python package installation is needed for the runner.

## Preparation evidence

Current AWS CLI authentication passed STS identity lookup.
The existing default VPC and public subnets were found in `us-east-1`.
Canonical's current Ubuntu 24.04 amd64 AMI was read from its public SSM parameter and its publisher and architecture were checked through EC2.
`python3 cloud/run_gyoto.py` passed in read-only mode.
`aws cloudformation validate-template` accepted `cloud/gyoto-stack.json`.
The runner passed Python compilation.
At preparation time, creation permissions, installation, SSM connectivity, the adapter, and cleanup execution were still untested.
AWS MCP documentation tools were used first.
AWS MCP script invocation did not accept the attempted wrapper arguments; authenticated AWS CLI calls supplied read-only account checks instead.

## Executed result

The complete command succeeded on 2026-10-04.
GYOTO and its Python package both report version `2.0.2-1.1build3`.
All 24 launches agree with the local solver and oracle at both tested tolerances.
All tighter runs pass the conservation thresholds.
The science program took 1.6796 seconds.
The runner completed provisioning, execution, and stack deletion in 367.1519 seconds.
Its cost model estimates $0.002766 before tax and transfer, not a final bill.
The saved runner state reports `DELETE_COMPLETE`.
[Scientific output](../results/gyoto-cloud-run.json) contains every flight and the sanitized execution summary.
