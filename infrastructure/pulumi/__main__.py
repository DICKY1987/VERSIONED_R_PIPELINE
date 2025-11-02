"""
Pulumi Infrastructure as Code
Version: 1.0.0
Date: 2025-11-02
Owner: Platform.Engineering
"""
from __future__ import annotations

import json
from pathlib import Path

import pulumi
import pulumi_aws as aws

CONFIG = pulumi.Config()
ENVIRONMENT = CONFIG.require("environment")
STACK_TAGS = {
    "Environment": ENVIRONMENT,
    "ManagedBy": "Pulumi",
    "Project": "acms",
}


def build_security_group() -> aws.ec2.SecurityGroup:
    ingress_rules = [
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=22,
            to_port=22,
            cidr_blocks=["10.0.0.0/8"] if ENVIRONMENT == "prod" else ["0.0.0.0/0"],
            description="SSH administration",
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=443,
            to_port=443,
            cidr_blocks=["0.0.0.0/0"],
            description="HTTPS API",
        ),
    ]
    egress_rules = [
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
            description="Allow outbound",
        )
    ]
    return aws.ec2.SecurityGroup(
        f"acms-sg-{ENVIRONMENT}",
        description=f"ACMS security group for {ENVIRONMENT}",
        ingress=ingress_rules,
        egress=egress_rules,
        tags=STACK_TAGS,
    )


def build_instance(security_group: aws.ec2.SecurityGroup) -> aws.ec2.Instance:
    user_data_path = Path(__file__).with_name("user_data.sh")
    if user_data_path.exists():
        user_data = user_data_path.read_text(encoding="utf-8")
    else:
        user_data = _default_user_data()
    return aws.ec2.Instance(
        f"acms-runner-{ENVIRONMENT}",
        instance_type="t3.medium" if ENVIRONMENT == "prod" else "t3.small",
        ami="ami-0abcdef1234567890",
        vpc_security_group_ids=[security_group.id],
        user_data=user_data,
        tags={**STACK_TAGS, "Name": f"acms-runner-{ENVIRONMENT}"},
    )


def export_metadata(instance: aws.ec2.Instance, security_group: aws.ec2.SecurityGroup) -> None:
    pulumi.export("instance_id", instance.id)
    pulumi.export("instance_public_ip", instance.public_ip)
    pulumi.export("security_group_id", security_group.id)
    pulumi.export("environment", ENVIRONMENT)


SECURITY_GROUP = build_security_group()
INSTANCE = build_instance(SECURITY_GROUP)
export_metadata(INSTANCE, SECURITY_GROUP)


def serialize_stack_plan() -> None:
    plan = {
        "environment": ENVIRONMENT,
        "resources": {
            "security_group": SECURITY_GROUP._name,  # pulumi resource name
            "instance": INSTANCE._name,
        },
        "tags": STACK_TAGS,
    }
    plan_path = Path("../stack_plan.json").resolve()
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")


serialize_stack_plan()


def _default_user_data() -> str:
    return "#!/bin/bash\necho 'ACMS runner bootstrap'\n"
