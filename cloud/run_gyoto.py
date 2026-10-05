#!/usr/bin/env python3
"""One bounded remote check. Default is read-only preparation; --run creates resources."""
import argparse
import base64
import gzip
import io
import json
from pathlib import Path
import shlex
import signal
import subprocess
import tarfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def interrupted(signum, frame):
    raise SystemExit(f"Interrupted by signal {signum}; attempting stack cleanup")


signal.signal(signal.SIGTERM, interrupted)


def aws(region, *args):
    command = ["aws", "--region", region, "--no-cli-pager", *args, "--output", "json"]
    result = subprocess.run(command, text=True, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout or "{}")


def prepare(args):
    identity = aws(args.region, "sts", "get-caller-identity")
    vpcs = aws(args.region, "ec2", "describe-vpcs", "--filters", "Name=is-default,Values=true")["Vpcs"]
    if not vpcs:
        raise RuntimeError("No default VPC. Stop; supply a separately reviewed network plan.")
    vpc = vpcs[0]["VpcId"]
    subnets = aws(args.region, "ec2", "describe-subnets", "--filters", f"Name=vpc-id,Values={vpc}", "Name=default-for-az,Values=true")["Subnets"]
    subnet = next((s for s in subnets if s.get("MapPublicIpOnLaunch")), None)
    if subnet is None:
        raise RuntimeError("No public default subnet for outbound SSM. Stop.")
    image = aws(args.region, "ssm", "get-parameter", "--name", "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id")["Parameter"]["Value"]
    ami = aws(args.region, "ec2", "describe-images", "--image-ids", image)["Images"][0]
    if ami["OwnerId"] != "099720109477" or ami["Architecture"] != "x86_64":
        raise RuntimeError("Ubuntu image publisher/architecture check failed.")
    return {"account": identity["Account"], "region": args.region, "vpc": vpc,
            "subnet": subnet["SubnetId"], "image": image, "image_name": ami["Name"]}


def payload(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name in files:
            path = (ROOT / name).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                raise ValueError(f"Not a project file: {name}")
            archive.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    if len(encoded) > 45000:
        raise ValueError("Payload exceeds bounded SSM transport size (45,000 base64 bytes).")
    return encoded


def wait_stack(region, stack, wanted, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            status = aws(region, "cloudformation", "describe-stacks", "--stack-name", stack)["Stacks"][0]["StackStatus"]
        except RuntimeError as error:
            if wanted == "DELETE_COMPLETE" and "does not exist" in str(error):
                return
            raise
        if status == wanted:
            return
        if "FAILED" in status or "ROLLBACK" in status:
            raise RuntimeError(f"Stack {stack}: {status}")
        time.sleep(10)
    raise TimeoutError(f"Stack {stack} did not reach {wanted}")


def remote_command(region, instance, command, timeout=1800):
    parameters = json.dumps({"commands": [command], "executionTimeout": [str(timeout)]})
    result = aws(region, "ssm", "send-command", "--instance-ids", instance,
                 "--document-name", "AWS-RunShellScript", "--parameters", parameters,
                 "--timeout-seconds", "60")
    command_id = result["Command"]["CommandId"]
    deadline = time.monotonic() + timeout + 90
    while time.monotonic() < deadline:
        try:
            result = aws(region, "ssm", "get-command-invocation", "--command-id", command_id, "--instance-id", instance)
        except RuntimeError as error:
            if "InvocationDoesNotExist" not in str(error):
                raise
            time.sleep(5)
            continue
        if result["Status"] not in {"Pending", "InProgress", "Delayed"}:
            return result
        time.sleep(10)
    raise TimeoutError(f"SSM command timed out: {command_id}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Create temporary paid resources, execute, download output, delete stack")
    parser.add_argument("--region", choices=["us-east-1"], default="us-east-1")
    parser.add_argument("--entry", help="Project-relative Python script; emits compact JSON to stdout")
    parser.add_argument("--files", nargs="+", help="Exact project-relative source file upload manifest")
    parser.add_argument("--output", default="results/gyoto-cloud-run.json")
    args = parser.parse_args()
    plan = prepare(args)
    print(json.dumps({key: plan[key] for key in ('region', 'image_name')}), flush=True)
    if not args.run:
        return
    if not args.entry or not args.files or args.entry not in args.files:
        parser.error("--run requires --entry included in --files")
    encoded = payload(args.files)
    entry = Path(args.entry)
    if entry.is_absolute() or ".." in entry.parts:
        parser.error("--entry must be a project-relative path without '..'")
    stack = f"gyoto-check-{uuid.uuid4().hex[:10]}"
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT):
        parser.error("--output must be inside project")
    output.parent.mkdir(parents=True, exist_ok=True)
    state = {"plan": plan, "stack": stack, "upload_manifest": args.files, "status": "starting"}
    state_path = ROOT / 'cloud' / f'{stack}.state.json'
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    started = time.monotonic()
    attempted = False
    scientific = None
    try:
        attempted = True
        aws(args.region, "cloudformation", "create-stack", "--stack-name", stack,
            "--template-body", f"file://{ROOT / 'cloud/gyoto-stack.json'}", "--capabilities", "CAPABILITY_IAM",
            "--parameters", json.dumps([{"ParameterKey": k, "ParameterValue": plan[v]} for k, v in [("VpcId", "vpc"), ("SubnetId", "subnet"), ("ImageId", "image")]]),
            "--timeout-in-minutes", "10")
        wait_stack(args.region, stack, "CREATE_COMPLETE", 660)
        resources = aws(args.region, "cloudformation", "describe-stack-resources", "--stack-name", stack)["StackResources"]
        instance = next(r["PhysicalResourceId"] for r in resources if r["LogicalResourceId"] == "Instance")
        state["instance"] = instance
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            nodes = aws(args.region, "ssm", "describe-instance-information", "--filters", json.dumps([{"Key": "InstanceIds", "Values": [instance]}]))["InstanceInformationList"]
            if nodes and nodes[0]["PingStatus"] == "Online":
                break
            time.sleep(10)
        else:
            raise TimeoutError("SSM instance did not become online")
        command = "set -eu\nfor i in $(seq 1 90); do test -f /opt/gyoto-ready && break; sleep 10; done\ntest -f /opt/gyoto-ready\ncd /opt/gyoto-check\n"
        command += f"printf '%s' {shlex.quote(encoded)} | base64 -d | tar xz\n"
        command += f"timeout 600 /usr/bin/python3 {shlex.quote(args.entry)} > /opt/gyoto-result.json\n"
        command += "test $(wc -c < /opt/gyoto-result.json) -lt 100000\ngzip -c /opt/gyoto-result.json | base64 -w0 > /opt/gyoto-result.base64\ntest $(wc -c < /opt/gyoto-result.base64) -lt 20000\ncat /opt/gyoto-result.base64\n"
        result = remote_command(args.region, instance, command)
        (ROOT / 'cloud' / f'{stack}.command.json').write_text(json.dumps(result, indent=2) + "\n")
        if result["Status"] != "Success":
            raise RuntimeError(f"Remote check failed: {result['Status']}. See cloud/{stack}.command.json")
        scientific = json.loads(gzip.decompress(base64.b64decode(result["StandardOutputContent"], validate=True)))
        state["status"] = "check-finished"
    finally:
        try:
            if attempted:
                state["cleanup"] = "deleting"
                print(f"Deleting temporary stack {stack}", flush=True)
                try:
                    aws(args.region, "cloudformation", "delete-stack", "--stack-name", stack)
                except RuntimeError as error:
                    if 'does not exist' not in str(error):
                        raise
                wait_stack(args.region, stack, "DELETE_COMPLETE", 600)
                state["cleanup"] = "DELETE_COMPLETE"
        finally:
            state['elapsed_seconds'] = time.monotonic() - started
            state_path.write_text(json.dumps(state, indent=2) + "\n")
            if scientific is not None:
                output.write_text(json.dumps({'result': scientific, 'region': args.region,
                    'instance_type': 't3.small', 'cleanup': state.get('cleanup'),
                    'elapsed_seconds': state['elapsed_seconds'],
                    'estimated_infrastructure_usd': state['elapsed_seconds'] / 3600 * .02712,
                    'cost_note': 'Estimate from elapsed wall time, not a final bill; excludes tax and transfer.'},
                    indent=2, allow_nan=False) + '\n')


if __name__ == "__main__":
    main()
