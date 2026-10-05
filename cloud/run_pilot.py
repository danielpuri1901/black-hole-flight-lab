#!/usr/bin/env python3
"""Approved remote CPU training; --run creates one temporary stack and deletes it."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import PurePosixPath
import shlex
import shutil
import tarfile
import time
import uuid

from run_gyoto import ROOT, aws, prepare, remote_command, wait_stack

MAX_BYTES = 100 * 1024 * 1024
SOURCE_FILES = {"pilot_physics.py", "pilot_control.py", "pilot_model.py", "train_pilot.py",
                "test_pilot_physics.py", "test_pilot_model.py", "run_pilot_experiment.py"}

REMOTE_TRAIN = r'''
import hashlib, io, json, pathlib, subprocess, sys, tarfile, time
import boto3
bucket, expected_sha, training_options, extra_seeds = sys.argv[1:]
work = pathlib.Path('/opt/pilot-work')
output = work / 'output'
s3 = boto3.client('s3', region_name='us-east-1')
blob = s3.get_object(Bucket=bucket, Key='source/bundle.tar.gz')['Body'].read(104857601)
assert len(blob) <= 104857600 and hashlib.sha256(blob).hexdigest() == expected_sha
with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as archive:
    members = archive.getmembers()
    assert all(m.isfile() and not pathlib.PurePosixPath(m.name).is_absolute()
               and '..' not in pathlib.PurePosixPath(m.name).parts for m in members)
    assert sum(m.size for m in members) <= 104857600
    archive.extractall(work, members=members, filter='data')
python = '/opt/pilot-python/bin/python'
started = time.monotonic()
returncode = 1
try:
    tests = [name[:-3] for name in ('test_pilot_physics.py', 'test_pilot_model.py') if (work/name).exists()]
    if tests:
        with (output/'tests.log').open('w') as log:
            subprocess.run([python, '-m', 'unittest', *tests], cwd=work,
                           stdout=log, stderr=subprocess.STDOUT, timeout=300, check=True)
    deadline = time.monotonic() + 4500
    options = json.loads(training_options)
    runs = [(output, options)]
    for seed in json.loads(extra_seeds):
        seed_options = list(options)
        if '--seed' in seed_options:
            index = seed_options.index('--seed')
            del seed_options[index:index+2]
        runs.append((output/f'seed-{seed}', [*seed_options, '--seed', str(seed)]))
    with (output/'training.log').open('w') as log:
        for destination, seed_options in runs:
            returncode = 1
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Total training allowance exhausted')
            result = subprocess.run([python, 'train_pilot.py', '--data', str(work/'input/teacher.npz'),
                                     '--output', str(destination), *seed_options],
                                    cwd=work, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=remaining)
            returncode = result.returncode
            if returncode:
                break
finally:
    files = sorted(p for p in output.rglob('*') if p.is_file())
    assert not any(p.is_symlink() for p in files)
    assert sum(p.stat().st_size for p in files) <= 104857600
    manifest = {'training_returncode':returncode, 'runtime_seconds':time.monotonic()-started,
                'files':[{'name':str(p.relative_to(output)), 'bytes':p.stat().st_size,
                          'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for p in files:
            archive.add(p, arcname=str(p.relative_to(output)), recursive=False)
    artifact = buffer.getvalue()
    assert len(artifact) <= 104857600
    manifest['archive_bytes'] = len(artifact)
    manifest['archive_sha256'] = hashlib.sha256(artifact).hexdigest()
    s3.put_object(Bucket=bucket, Key='artifacts/bundle.tar.gz', Body=artifact)
    s3.put_object(Bucket=bucket, Key='artifacts/manifest.json', Body=json.dumps(manifest).encode())
    print(json.dumps({'training_returncode':returncode,'artifact_files':len(files),
                      'artifact_bytes':len(artifact)}), flush=True)
sys.exit(returncode)
'''


def file_path(name):
    selected = ROOT / name
    path = selected.resolve()
    if selected.is_symlink() or not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError(f"Not a regular project file: {name}")
    return path


def bundle_sources(args, destination):
    sources = args.source_file
    if not sources or not {"train_pilot.py", "pilot_model.py"}.issubset(sources):
        raise ValueError("Include train_pilot.py and pilot_model.py in the explicit source manifest")
    if len(set(sources)) != len(sources) or not set(sources).issubset(SOURCE_FILES):
        raise ValueError("Source manifest must contain distinct approved pilot source filenames")
    data = file_path(args.data)
    if data.name != "teacher.npz":
        raise ValueError("Approved data filename is teacher.npz")
    files = [(file_path(name), name) for name in sources] + [(data, "input/teacher.npz")]
    if sum(p.stat().st_size for p, _ in files) > MAX_BYTES:
        raise ValueError("Source and data exceed 100 MiB")
    with tarfile.open(destination, "w:gz") as archive:
        for path, name in files:
            archive.add(path, arcname=name, recursive=False)
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def download_artifacts(region, bucket, target):
    target.mkdir(parents=True, exist_ok=True)
    info = aws(region, "s3api", "head-object", "--bucket", bucket, "--key", "artifacts/manifest.json")
    if info["ContentLength"] > 512000:
        raise ValueError("Artifact manifest is too large")
    manifest_file = target / "manifest.json"
    aws(region, "s3api", "get-object", "--bucket", bucket, "--key", "artifacts/manifest.json", str(manifest_file))
    manifest = json.loads(manifest_file.read_text())
    if manifest["archive_bytes"] > MAX_BYTES or sum(f["bytes"] for f in manifest["files"]) > MAX_BYTES:
        raise ValueError("Remote artifacts exceed approved 100 MiB limit")
    archive_file = target / "bundle.tar.gz"
    info = aws(region, "s3api", "head-object", "--bucket", bucket, "--key", "artifacts/bundle.tar.gz")
    if info["ContentLength"] != manifest["archive_bytes"]:
        raise ValueError("Archive length differs from manifest")
    aws(region, "s3api", "get-object", "--bucket", bucket, "--key", "artifacts/bundle.tar.gz", str(archive_file))
    if hashlib.sha256(archive_file.read_bytes()).hexdigest() != manifest["archive_sha256"]:
        raise ValueError("Archive SHA-256 differs from manifest")
    expected = {f["name"]: f for f in manifest["files"]}
    if len(expected) != len(manifest["files"]):
        raise ValueError("Duplicate manifest paths")
    extracted = target / "files"
    extracted.mkdir(exist_ok=True)
    with tarfile.open(archive_file, "r:gz") as archive:
        members = archive.getmembers()
        if {m.name for m in members} != set(expected) or len(members) != len(expected):
            raise ValueError("Archive file manifest differs")
        for member in members:
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts or member.size != expected[member.name]["bytes"]:
                raise ValueError("Unsafe artifact path or size")
            content = archive.extractfile(member).read()
            if hashlib.sha256(content).hexdigest() != expected[member.name]["sha256"]:
                raise ValueError("Artifact file checksum differs")
            output = extracted / member.name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(content)
    return manifest, extracted


def empty_bucket(region, bucket):
    while True:
        objects = aws(region, "s3api", "list-objects-v2", "--bucket", bucket).get("Contents", [])
        if not objects:
            return
        request = json.dumps({"Objects": [{"Key": obj["Key"]} for obj in objects], "Quiet": True})
        result = aws(region, "s3api", "delete-objects", "--bucket", bucket, "--delete", request)
        if result.get("Errors"):
            raise RuntimeError("Temporary bucket object deletion failed")


def verify_cleanup(region, state):
    checks = {"stack_deleted": state.get("cleanup") == "DELETE_COMPLETE"}
    instance = state.get("instance")
    if instance:
        data = aws(region, "ec2", "describe-instances", "--instance-ids", instance)["Reservations"]
        instances = [i for r in data for i in r["Instances"]]
        checks["instance_terminated"] = all(i["State"]["Name"] == "terminated" for i in instances)
        checks["no_attached_root_volume"] = all(not i.get("BlockDeviceMappings") for i in instances)
    volumes = state.get("volumes", [])
    for volume in volumes:
        try:
            aws(region, "ec2", "describe-volumes", "--volume-ids", volume)
        except RuntimeError as error:
            if "InvalidVolume.NotFound" not in str(error):
                raise
        else:
            checks["root_volumes_deleted"] = False
            break
    else:
        checks["root_volumes_deleted"] = bool(volumes)
    resource_calls = {"Role": ("iam", "get-role", "--role-name"),
                      "Profile": ("iam", "get-instance-profile", "--instance-profile-name"),
                      "SecurityGroup": ("ec2", "describe-security-groups", "--group-ids"),
                      "Artifacts": ("s3api", "head-bucket", "--bucket")}
    for name, (service, operation, flag) in resource_calls.items():
        resource = state.get("resources", {}).get(name)
        if not resource:
            continue
        try:
            aws(region, service, operation, flag, resource)
        except RuntimeError as error:
            if not any(code in str(error) for code in ("NoSuchEntity", "InvalidGroup.NotFound", "404", "Not Found")):
                raise
            checks[f"{name.lower()}_deleted"] = True
        else:
            checks[f"{name.lower()}_deleted"] = False
    checks["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
    checks["passed"] = all(v for v in checks.values() if isinstance(v, bool))
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--region", choices=["us-east-1"], default="us-east-1")
    parser.add_argument("--instance-type", choices=["c7i.xlarge", "c6i.xlarge"], default="c7i.xlarge")
    parser.add_argument("--source-file", action="append", default=[])
    parser.add_argument("--data", default="results/pilot/teacher.npz")
    parser.add_argument("--output", default="results/pilot/model")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--extra-seed", type=int, action="append", default=[])
    parser.add_argument("--ae-epochs", type=int)
    parser.add_argument("--diffusion-steps", type=int)
    args = parser.parse_args()
    plan = prepare(args)
    print(json.dumps({"region": args.region, "image_name": plan["image_name"],
                      "instance_type": args.instance_type, "run": args.run}), flush=True)
    if not args.run:
        return
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT):
        parser.error("Output must remain inside the project")
    options = []
    if any(seed < 0 for seed in args.extra_seed) or len(set(args.extra_seed)) != len(args.extra_seed):
        parser.error("Extra seeds must be distinct nonnegative integers")
    if (args.seed if args.seed is not None else 1729) in args.extra_seed:
        parser.error("Extra seeds must differ from the main seed")
    for name in ("seed", "ae_epochs", "diffusion_steps"):
        value = getattr(args, name)
        if value is not None:
            if value < 0:
                parser.error("Training arguments must be nonnegative integers")
            options += ["--" + name.replace("_", "-"), str(value)]
    stack = "pilot-training-" + uuid.uuid4().hex[:10]
    private = ROOT / "cloud" / stack
    private.mkdir()
    bundle = private / "source.tar.gz"
    source_sha = bundle_sources(args, bundle)
    source_hashes = {name: hashlib.sha256(file_path(name).read_bytes()).hexdigest()
                     for name in args.source_file}
    data_sha = hashlib.sha256(file_path(args.data).read_bytes()).hexdigest()
    state = {"plan": plan, "stack": stack, "source_manifest": args.source_file,
             "data": args.data, "source_sha256": source_sha, "source_file_sha256": source_hashes,
             "data_file_sha256": data_sha, "training_options": options,
             "extra_seeds": args.extra_seed, "status": "prepared"}
    state_path = private / "state.json"
    save = lambda: state_path.write_text(json.dumps(state, indent=2) + "\n")
    save()
    attempted, bucket, manifest, files = False, None, None, None
    started = time.monotonic()
    try:
        attempted = True
        aws(args.region, "cloudformation", "create-stack", "--stack-name", stack,
            "--template-body", f"file://{ROOT/'cloud/pilot-stack.json'}", "--capabilities", "CAPABILITY_IAM",
            "--parameters", json.dumps([{"ParameterKey": k, "ParameterValue": v} for k, v in
                [("VpcId", plan["vpc"]), ("SubnetId", plan["subnet"]), ("ImageId", plan["image"]), ("InstanceType", args.instance_type)]]),
            "--timeout-in-minutes", "10")
        wait_stack(args.region, stack, "CREATE_COMPLETE", 660)
        resources = aws(args.region, "cloudformation", "describe-stack-resources", "--stack-name", stack)["StackResources"]
        state["resources"] = {r["LogicalResourceId"]: r["PhysicalResourceId"] for r in resources}
        state["instance"] = instance = state["resources"]["Instance"]
        bucket = state["resources"]["Artifacts"]
        data = aws(args.region, "ec2", "describe-instances", "--instance-ids", instance)
        state["volumes"] = [d["Ebs"]["VolumeId"] for r in data["Reservations"] for i in r["Instances"] for d in i.get("BlockDeviceMappings", []) if "Ebs" in d]
        save()
        aws(args.region, "s3api", "put-object", "--bucket", bucket, "--key", "source/bundle.tar.gz", "--body", str(bundle))
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            nodes = aws(args.region, "ssm", "describe-instance-information", "--filters", json.dumps([{"Key": "InstanceIds", "Values": [instance]}]))["InstanceInformationList"]
            if nodes and nodes[0]["PingStatus"] == "Online":
                break
            time.sleep(10)
        else:
            raise TimeoutError("Pilot server did not become SSM-online")
        command = "set -eu\nfor i in $(seq 1 120); do test -f /opt/pilot-ready && break; sleep 10; done\ntest -f /opt/pilot-ready\n"
        command += "export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4\n"
        command += "/opt/pilot-python/bin/python - " + " ".join(shlex.quote(x) for x in [bucket, source_sha, json.dumps(options), json.dumps(args.extra_seed)]) + " <<'PILOT_PYTHON'\n" + REMOTE_TRAIN + "\nPILOT_PYTHON\n"
        result = remote_command(args.region, instance, command, timeout=6000)
        (private/"command.json").write_text(json.dumps(result, indent=2) + "\n")
        if result["Status"] != "Success":
            try:
                diagnostic = remote_command(args.region, instance,
                    "tail -c 18000 /opt/pilot-work/output/install.log; tail -c 4000 /opt/pilot-work/output/training.log", timeout=30)
                (private/"failure-diagnostic.json").write_text(json.dumps(diagnostic, indent=2) + "\n")
            except (RuntimeError, TimeoutError) as error:
                (private/"failure-diagnostic.txt").write_text(str(error) + "\n")
        manifest, files = download_artifacts(args.region, bucket, private/"artifacts")
        state["status"] = "artifacts-verified"
        save()
        if result["Status"] != "Success" or manifest["training_returncode"] != 0:
            raise RuntimeError(f"Remote training failed; inspect private logs in {private/'artifacts/files'}")
        output.mkdir(parents=True, exist_ok=True)
        for entry in manifest["files"]:
            path = files / entry["name"]
            if path.suffix in {".npz", ".pt", ".json"}:
                destination = output / entry["name"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
    finally:
        try:
            if attempted:
                state["cleanup"] = "deleting"
                save()
                if bucket:
                    try:
                        if state.get("instance"):
                            aws(args.region, "ec2", "terminate-instances", "--instance-ids", state["instance"])
                            deadline = time.monotonic() + 300
                            while time.monotonic() < deadline:
                                data = aws(args.region, "ec2", "describe-instances", "--instance-ids", state["instance"])
                                if all(i["State"]["Name"] == "terminated" for r in data["Reservations"] for i in r["Instances"]):
                                    break
                                time.sleep(5)
                            else:
                                raise TimeoutError("Pilot instance did not terminate before bucket cleanup")
                        empty_bucket(args.region, bucket)
                    except (RuntimeError, TimeoutError) as error:
                        state["predelete_error"] = str(error)
                        save()
                        # Still ask CloudFormation to remove compute and other resources.
                try:
                    aws(args.region, "cloudformation", "delete-stack", "--stack-name", stack)
                except RuntimeError as error:
                    if "does not exist" not in str(error):
                        raise
                wait_stack(args.region, stack, "DELETE_COMPLETE", 660)
                state["cleanup"] = "DELETE_COMPLETE"
                state["cleanup_checks"] = verify_cleanup(args.region, state)
        finally:
            state["elapsed_seconds"] = time.monotonic() - started
            save()
            if manifest is not None:
                summary = {"region": args.region, "instance_type": args.instance_type,
                    "source_file_sha256": source_hashes, "data_file_sha256": data_sha,
                    "training_options": options,
                    "extra_seeds": args.extra_seed,
                    "training_returncode": manifest["training_returncode"], "artifact_files": manifest["files"],
                    "cleanup": state.get("cleanup"), "cleanup_checks": state.get("cleanup_checks"),
                    "elapsed_seconds": state["elapsed_seconds"],
                    "estimated_infrastructure_usd": state["elapsed_seconds"]/3600*(0.1785 if args.instance_type=="c7i.xlarge" else .17)+state["elapsed_seconds"]/3600*(.005+20*.08/730),
                    "cost_note": "Estimate from elapsed time; excludes S3, data transfer, and taxes."}
                output.mkdir(parents=True, exist_ok=True)
                (output/"cloud-run.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
