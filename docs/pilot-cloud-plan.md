# Temporary AI pilot training on AWS

Prepared on 2026-10-04.
The preparation created no resources; the subsequent authorized training run completed on the same date.
The user approved this remote manifest and download of the project's own trained artifacts before implementation.

## Scope

Train small project-owned autoencoder, transformer, and diffusion models from generated physics data on one temporary CPU server.
Download the trained artifacts and measured evaluation results.
Do not download pretrained weights, image datasets, CUDA libraries, notebooks, or Docker images.
Do not install PyTorch or another package manager on the Mac.
The powered dynamics, controls, training objectives, data splits, and evaluation criteria must be specified before execution.
The existing fixed-energy, fixed-angular-momentum certificate does not certify powered control or arbitrary generated paths.

## Remote installation manifest

Ubuntu 24.04 has no `python3-torch` package in its published noble package search.
Use Ubuntu packages for numerical libraries and a separate Python virtual environment for the official CPU-only PyTorch wheel.
[Official Ubuntu package search](https://packages.ubuntu.com/search?keywords=torch&searchon=names&suite=noble&section=all).

| Item | Purpose | Remote scope |
| --- | --- | --- |
| Canonical Ubuntu Server 24.04 amd64 AMI | Operating system | One disposable EC2 instance |
| python3-venv | Isolated PyTorch environment | Ubuntu apt package |
| python3-numpy, python3-scipy | Physics data and numerical evaluation | Ubuntu apt packages |
| python3-boto3 | Private artifact upload and source retrieval | Ubuntu apt package |
| torch 2.13.0+cpu | Train the three small neural models | Official PyTorch CPU wheel in a virtual environment |
| filelock, typing-extensions, setuptools, sympy, networkx, jinja2, fsspec | Declared PyTorch dependencies | Virtual environment |
| Required package dependencies | Required libraries and Python support packages | Apt and pip resolver output |
| Explicit project source manifest | Powered dynamics, data generation, training, evaluation | Private temporary source archive |
| Generated data and trained artifacts | Training examples, weights, and results | Temporary disk and private bucket |

The official Python 3.12 x86-64 CPU wheel is 191,817,609 bytes, about 183 MiB, as measured by its HTTP headers.
Its published SHA-256 is `4ca4a9394b0c771238a4f73590fdbbc4debad85ed0fa63d026ae1b085da7d6e2`.
The dependency names above came from that wheel's published metadata, rather than a local installation.
SymPy and Jinja2 add their own required dependencies.
Exact resolver-selected versions and total transfer remain unmeasured.
Allow roughly 0.3 to 1 GiB of remote package transfer and 1 to 3 GiB of installed packages as planning estimates.
Use a 20 GiB root disk and cap downloaded trained artifacts at 100 MiB in total.
Stop and revise the manifest if the measured resolver output exceeds these allowances.
[Official CPU wheel index](https://download.pytorch.org/whl/cpu/torch/), [official installation instructions](https://pytorch.org/get-started/previous-versions/), [wheel dependency metadata](https://download-r2.pytorch.org/whl/cpu/torch-2.13.0%2Bcpu-cp312-cp312-manylinux_2_28_x86_64.whl.metadata).

Proposed remote installation commands, after approval:

```sh
apt-get install -y --no-install-recommends python3-venv python3-numpy python3-scipy python3-boto3
python3 -m venv --system-site-packages /opt/pilot-python
/opt/pilot-python/bin/python -m pip install --no-cache-dir torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
```

The virtual environment can reuse Ubuntu's NumPy, SciPy, and Boto3 packages.
PyTorch and its remaining Python dependencies stay in that environment.
Record the installed package versions and import checks before training.

## Instance and cost

Prefer one On-Demand `c7i.xlarge` in `us-east-1`, with 4 vCPUs and 8 GiB memory.
Its CPU performance is not limited by burst-credit accounting.
Use a 20 GiB encrypted gp3 root disk, a public IPv4 address for outbound traffic, and no inbound ports.
Use the existing default VPC after checking it again at execution.
Do not add a NAT gateway, GPU, load balancer, persistent endpoint, or container build.
[Official C7i specifications](https://aws.amazon.com/ec2/instance-types/c7i/).

The authenticated AWS Price List API returned these Linux shared-tenancy On-Demand rates:

| Instance | CPU and memory | Verified USD per hour |
| --- | --- | --- |
| c7i.xlarge | 4 vCPUs, 8 GiB | 0.1785 |
| c7i.large | 2 vCPUs, 4 GiB | 0.08925 |
| c6i.xlarge | 4 vCPUs, 8 GiB | 0.17 |

All three types were listed as offered in `us-east-1` during the read-only check.
An offering does not guarantee immediate capacity in a particular Availability Zone.
Use `c6i.xlarge` as an explicit reviewed fallback if C7i capacity is unavailable.
The smaller instance saves little for this bounded experiment and has less memory for training.

Two hours of C7i compute, one IPv4 address at $0.005 per hour, and 20 GiB of gp3 at $0.08 per GiB-month have an estimated combined cost of $0.37138.
Small private-bucket storage, requests, and artifact transfer add charges.
Use a $5 working allowance within the user's $50 total credit budget.
This is a planning allowance, not a hard billing cap or a guarantee of credit eligibility.
The remaining credit balance and service eligibility have not been inspected.
The final cost must be measured or clearly reported as an estimate.
[EC2 pricing](https://aws.amazon.com/ec2/pricing/on-demand/), [EBS pricing](https://aws.amazon.com/ebs/pricing/), [IPv4 pricing](https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights/), [S3 pricing](https://aws.amazon.com/s3/pricing/).

## Artifact transport

Use one temporary private S3 bucket created in the same CloudFormation stack.
This is simpler for weight archives than hundreds of small SSM output requests.
Block all public access, disable ACLs with bucket-owner-enforced ownership, enable default server-side encryption, and require TLS.
Give the instance permission to read only the bucket's `source/` prefix and write only its `artifacts/` prefix.
Give it no general account-storage access.
Use the instance role for authentication; do not embed keys or create public or presigned artifact URLs.
[Official S3 security guidance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html).

Upload only the agreed project files to `source/`.
Write trained weights, compact rollout examples, and evaluation summaries to `artifacts/`.
Record file sizes and SHA-256 checksums and reject total artifacts larger than 100 MiB.
The local runner uses its existing AWS CLI to download and verify the explicit artifact manifest.
Keep raw command logs and account metadata under `cloud/`.
Publish only sanitized scientific results and dashboard-ready files under `results/`.

Empty the temporary bucket after verified download, then delete the stack and confirm that all resources are gone.
Add a one-day object-expiration lifecycle rule as a backup if local cleanup fails.
Object lifecycle expiration does not delete the bucket or impose an immediate cost cap.
Keep versioning disabled so cleanup does not leave hidden object versions.

## Execution bounds and cleanup

Reuse the reviewed GYOTO security pattern in new pilot-specific files.
Require IMDSv2, no SSH keys, no ingress, and outbound HTTP and HTTPS for apt, PyTorch, SSM, and S3.
Use SSM Run Command to execute the training entry point.
The temporary SSM role must deny Parameter Store reads, as in the previous run, while allowing only the temporary bucket's required prefix actions.
Schedule OS shutdown within 120 minutes of user-data start.
Instance-initiated shutdown must terminate the instance and delete its root volume.
Limit package setup to 20 minutes and training plus evaluation to 75 minutes, leaving time to retrieve artifacts before termination.
The runner must attempt stack deletion even if creation times out after AWS accepts the request.
Save resource IDs only in local private state for cleanup verification.
Verify instance termination, volume deletion, bucket deletion, and deletion of the temporary role, profile, and security group after every run.
An OS boot failure or killed local runner can defeat one cleanup path, so these controls do not replace verification.

## Readiness

An initial STS check found an expired token and all authenticated account work stopped.
After the user completed login, a fresh STS check passed.
No credentials or account IDs were printed by that resumed readiness check.
Current prices and regional offerings were then checked with read-only AWS APIs.
`cloud/pilot-stack.json` and `cloud/run_pilot.py` now implement this plan.
No package, wheel, model, or dataset has been downloaded to the Mac.
The AWS template passed `validate-template`, and local compilation checked the runner and embedded remote Python.
The cloud-init shell passed `bash -n`.
Actual installation, training, artifact transport, and cleanup passed during the authorized run.

## Completed run

The three fits used seeds 1729, 1730, and 1731 on one temporary `c7i.xlarge`.
Training used Python 3.12.3, NumPy 1.26.4, CPU PyTorch 2.13.0, two Torch threads, and deterministic algorithms.
Each fit applied the approved balanced active-burn sampling to 2,248 training decisions.
Natural validation retained 546 decisions.
All three decoder and denoiser export checks passed the absolute tolerance of `10⁻⁵`.
The largest measured decoder error was `1.57×10⁻⁷`; the largest denoiser error was `3.33×10⁻⁶`.
All three models returned finite bounded plans and identical first proposals across candidate counts.

The remote training sequence took 73.87 seconds, including export and artifact assembly.
The verified compressed return archive contained 17 files and 323,378 bytes.
The whole runner took 381.39 seconds through cleanup.
Its compute, IPv4, and root-volume estimate was `$0.01967`, excluding S3, transfer, and taxes.
This remains an elapsed-time estimate rather than a measured AWS bill.

CloudFormation deletion completed, and independent read-only checks confirmed instance termination and root-volume deletion.
They also confirmed removal of the private bucket, temporary role, instance profile, and security group.
No attached root volume remained.
The sanitized run report is `results/pilot/model/cloud-run.json`.
Raw installation output, resolver versions, archives, and account metadata remain in the ignored private cloud directory.
The trained models still require the sealed held-out controller evaluation before any performance claim.

## Runner

The runner defaults to a read-only readiness check.
Its paid execution requires `--run` and an explicit source list from the approved pilot filenames.
It reuses the verified GYOTO AWS CLI helpers without changing the GYOTO workflow.
The remote entry point is fixed to `train_pilot.py --data PATH --output DIR`.
Optional seed, autoencoder epoch count, and diffusion step count pass as integer arguments.
Repeated `--extra-seed` arguments train additional models on the same instance and dataset.
The main model stays at the output root; extra models use `seed-N` subdirectories.
All seeds share one 75-minute training deadline, and any failed seed stops the sequence with a nonzero result.
Listed pilot unit tests run first when their source files are included.

```sh
python3 cloud/run_pilot.py --run \
  --source-file train_pilot.py \
  --source-file pilot_model.py \
  --data results/pilot/teacher.npz \
  --output results/pilot/model \
  --seed 1729 --extra-seed 1730 --extra-seed 1731
```

The runner verifies source, archive, and individual artifact SHA-256 checksums.
Source plus data and returned artifacts each have a 100 MiB limit.
The remote setup downloads CPU wheels, checks the approved Torch hash, installs from those files, and saves actual package versions.
Raw archives, installation and training logs, full package lists, and account state stay under `cloud/`.
Model NPZ or PT files and scientific JSON copy to the requested results directory.
The final public run summary contains sanitized checks and estimated cost.
It records each uploaded source file's SHA-256 and the teacher data SHA-256 for reproducibility.
The runner records the root volume ID and verifies its deletion, along with instance termination and removal of the bucket, role, profile, and security group.
