"""Icon name → renderer-specific path mapping tables.

Namespaced icon ids (e.g. "aws:lambda") are used in the IR so Gemini
never needs to know file paths.  Code generators look up the correct
path/URL here.

PlantUML format: {icon_id: (relative_path, macro_name)}
D2 format:       {icon_id: url_string}
"""

# ---------------------------------------------------------------------------
# AWS — PlantUML icon stdlib v20.0
# Base: https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist
# ---------------------------------------------------------------------------

AWS_PLANTUML_BASE = "https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist"

# (relative_path_from_base, macro_name)
AWS_PLANTUML_ICONS: dict[str, tuple[str, str]] = {
    # Compute
    "aws:lambda":               ("Compute/Lambda.puml", "Lambda"),
    "aws:ec2":                  ("Compute/EC2Instance.puml", "EC2Instance"),
    "aws:ec2_auto_scaling":     ("Compute/EC2AutoScaling.puml", "EC2AutoScaling"),
    # Containers
    "aws:ecs":                  ("Containers/ElasticContainerService.puml", "ElasticContainerService"),
    "aws:ecs_service":          ("Containers/ElasticContainerServiceService.puml", "ElasticContainerServiceService"),
    "aws:fargate":              ("Containers/Fargate.puml", "Fargate"),
    "aws:ecr":                  ("Containers/ElasticContainerRegistry.puml", "ElasticContainerRegistry"),
    "aws:eks":                  ("Containers/ElasticKubernetesService.puml", "ElasticKubernetesService"),
    # Networking
    "aws:alb":                  ("NetworkingContentDelivery/ElasticLoadBalancingApplicationLoadBalancer.puml", "ElasticLoadBalancingApplicationLoadBalancer"),
    "aws:igw":                  ("NetworkingContentDelivery/VPCInternetGateway.puml", "VPCInternetGateway"),
    "aws:nat_gateway":          ("NetworkingContentDelivery/VPCNATGateway.puml", "VPCNATGateway"),
    "aws:cloudfront":           ("NetworkingContentDelivery/CloudFront.puml", "CloudFront"),
    "aws:route53":              ("NetworkingContentDelivery/Route53.puml", "Route53"),
    "aws:route53_hosted_zone":  ("NetworkingContentDelivery/Route53HostedZone.puml", "Route53HostedZone"),
    "aws:api_gateway":          ("NetworkingContentDelivery/APIGateway.puml", "APIGateway"),
    # Database
    "aws:rds":                  ("Database/RDS.puml", "RDS"),
    "aws:aurora_postgresql":    ("Database/AuroraPostgreSQLInstance.puml", "AuroraPostgreSQLInstance"),
    "aws:aurora_mariadb":       ("Database/AuroraMariaDBInstance.puml", "AuroraMariaDBInstance"),
    "aws:dynamodb":             ("Database/DynamoDB.puml", "DynamoDB"),
    "aws:elasticache":          ("Database/ElastiCache.puml", "ElastiCache"),
    "aws:elasticache_redis":    ("Database/ElastiCacheElastiCacheforRedis.puml", "ElastiCacheElastiCacheforRedis"),
    "aws:elasticache_memcached": ("Database/ElastiCacheElastiCacheforMemcached.puml", "ElastiCacheElastiCacheforMemcached"),
    # Storage
    "aws:s3":                   ("Storage/SimpleStorageService.puml", "SimpleStorageService"),
    "aws:s3_bucket":            ("Storage/SimpleStorageServiceBucket.puml", "SimpleStorageServiceBucket"),
    # Application Integration
    "aws:sqs":                  ("ApplicationIntegration/SimpleQueueService.puml", "SimpleQueueService"),
    "aws:sns":                  ("ApplicationIntegration/SimpleNotificationService.puml", "SimpleNotificationService"),
    "aws:eventbridge":          ("ApplicationIntegration/EventBridge.puml", "EventBridge"),
    "aws:eventbridge_scheduler": ("ApplicationIntegration/EventBridgeScheduler.puml", "EventBridgeScheduler"),
    "aws:step_functions":       ("ApplicationIntegration/StepFunctions.puml", "StepFunctions"),
    "aws:ses":                  ("BusinessApplications/SimpleEmailService.puml", "SimpleEmailService"),
    # Management & Governance
    "aws:cloudwatch":           ("ManagementGovernance/CloudWatch.puml", "CloudWatch"),
    "aws:cloudwatch_alarm":     ("ManagementGovernance/CloudWatchAlarm.puml", "CloudWatchAlarm"),
    "aws:cloudwatch_logs":      ("ManagementGovernance/CloudWatchLogs.puml", "CloudWatchLogs"),
    "aws:cloudwatch_rule":      ("ManagementGovernance/CloudWatchRule.puml", "CloudWatchRule"),
    "aws:cloudwatch_scheduled": ("ManagementGovernance/CloudWatchEventTimeBased.puml", "CloudWatchEventTimeBased"),
    "aws:cloudwatch_event":     ("ManagementGovernance/CloudWatchEventEventBased.puml", "CloudWatchEventEventBased"),
    "aws:cloudtrail":           ("ManagementGovernance/CloudTrail.puml", "CloudTrail"),
    "aws:systems_manager":      ("ManagementGovernance/SystemsManager.puml", "SystemsManager"),
    "aws:cloudformation":       ("ManagementGovernance/CloudFormation.puml", "CloudFormation"),
    # Analytics
    "aws:glue":                 ("Analytics/Glue.puml", "Glue"),
    "aws:redshift":             ("Analytics/Redshift.puml", "Redshift"),
    "aws:quicksight":           ("Analytics/QuickSight.puml", "QuickSight"),
    "aws:athena":               ("Analytics/Athena.puml", "Athena"),
    "aws:kinesis":              ("Analytics/KinesisDataStreams.puml", "KinesisDataStreams"),
    "aws:emr":                  ("Analytics/EMR.puml", "EMR"),
    # Security
    "aws:cognito":              ("SecurityIdentityCompliance/Cognito.puml", "Cognito"),
    "aws:iam":                  ("SecurityIdentityCompliance/IdentityandAccessManagement.puml", "IdentityandAccessManagement"),
    "aws:waf":                  ("SecurityIdentityCompliance/WAF.puml", "WAF"),
}

# AWS PlantUML group macros — (relative_path, macro_name)
AWS_PLANTUML_GROUPS: dict[str, tuple[str, str]] = {
    "aws_cloud":      ("Groups/AWSCloud.puml", "AWSCloudGroup"),
    "region":         ("Groups/Region.puml", "RegionGroup"),
    "vpc":            ("Groups/VPC.puml", "VPCGroup"),
    "public_subnet":  ("Groups/PublicSubnet.puml", "PublicSubnetGroup"),
    "private_subnet": ("Groups/PrivateSubnet.puml", "PrivateSubnetGroup"),
}


# ---------------------------------------------------------------------------
# Azure — PlantUML stdlib
# Base: https://raw.githubusercontent.com/plantuml-stdlib/Azure-PlantUML/master/dist
# ---------------------------------------------------------------------------

AZURE_PLANTUML_BASE = "https://raw.githubusercontent.com/plantuml-stdlib/Azure-PlantUML/master/dist"

AZURE_PLANTUML_ICONS: dict[str, tuple[str, str]] = {
    "azure:app_service":         ("Compute/AzureAppService.puml", "AzureAppService"),
    "azure:functions":           ("Compute/AzureFunctions.puml", "AzureFunctions"),
    "azure:vm":                  ("Compute/AzureVirtualMachine.puml", "AzureVirtualMachine"),
    "azure:aks":                 ("Containers/AzureKubernetesService.puml", "AzureKubernetesService"),
    "azure:container_registry":  ("Containers/AzureContainerRegistry.puml", "AzureContainerRegistry"),
    "azure:sql_database":        ("Databases/AzureSqlDatabase.puml", "AzureSqlDatabase"),
    "azure:cosmos_db":           ("Databases/AzureCosmosDb.puml", "AzureCosmosDb"),
    "azure:blob_storage":        ("Storage/AzureBlobStorage.puml", "AzureBlobStorage"),
    "azure:app_gateway":         ("Networking/AzureApplicationGateway.puml", "AzureApplicationGateway"),
    "azure:front_door":          ("Networking/AzureFrontDoor.puml", "AzureFrontDoor"),
}


# ---------------------------------------------------------------------------
# GCP — PlantUML (for reference, but GCP routes to D2)
# Base: https://raw.githubusercontent.com/Crashedmind/PlantUML-icons-GCP/master/dist
# ---------------------------------------------------------------------------

GCP_PLANTUML_BASE = "https://raw.githubusercontent.com/Crashedmind/PlantUML-icons-GCP/master/dist"

GCP_PLANTUML_ICONS: dict[str, tuple[str, str]] = {
    "gcp:cloud_run":           ("Compute/Cloud_Run.puml", "Cloud_Run"),
    "gcp:compute_engine":      ("Compute/Compute_Engine.puml", "Compute_Engine"),
    "gcp:cloud_functions":     ("Compute/Cloud_Functions.puml", "Cloud_Functions"),
    "gcp:gke":                 ("Compute/Kubernetes_Engine.puml", "Kubernetes_Engine"),
    "gcp:cloud_sql":           ("Databases/Cloud_SQL.puml", "Cloud_SQL"),
    "gcp:cloud_bigtable":      ("Databases/Cloud_Bigtable.puml", "Cloud_Bigtable"),
    "gcp:cloud_storage":       ("Storage/Cloud_Storage.puml", "Cloud_Storage"),
    "gcp:cloud_cdn":           ("Networking/Cloud_CDN.puml", "Cloud_CDN"),
    "gcp:cloud_load_balancing": ("Networking/Cloud_Load_Balancing.puml", "Cloud_Load_Balancing"),
    "gcp:cloud_armor":         ("Networking/Cloud_Armor.puml", "Cloud_Armor"),
    "gcp:pub_sub":             ("Data_Analytics/Cloud_Pub_Sub.puml", "Cloud_Pub_Sub"),
    "gcp:bigquery":            ("Data_Analytics/BigQuery.puml", "BigQuery"),
}


# ---------------------------------------------------------------------------
# D2 — Terrastruct icon URLs
# https://icons.terrastruct.com/
# ---------------------------------------------------------------------------

D2_ICONS: dict[str, str] = {
    # AWS — verified working on Terrastruct CDN
    "aws:lambda":           "https://icons.terrastruct.com/aws%2FCompute%2FAWS-Lambda.svg",
    "aws:ec2":              "https://icons.terrastruct.com/aws%2FCompute%2FAmazon-EC2.svg",
    "aws:s3":               "https://icons.terrastruct.com/aws%2FStorage%2FAmazon-Simple-Storage-Service-S3.svg",
    "aws:rds":              "https://icons.terrastruct.com/aws%2FDatabase%2FAmazon-RDS.svg",
    "aws:dynamodb":         "https://icons.terrastruct.com/aws%2FDatabase%2FAmazon-DynamoDB.svg",
    "aws:alb":              "https://icons.terrastruct.com/aws%2FNetworking%20%26%20Content%20Delivery%2FElastic-Load-Balancing.svg",
    "aws:cloudfront":       "https://icons.terrastruct.com/aws%2FNetworking%20%26%20Content%20Delivery%2FAmazon-CloudFront.svg",
    "aws:api_gateway":      "https://icons.terrastruct.com/aws%2FNetworking%20%26%20Content%20Delivery%2FAmazon-API-Gateway.svg",
    "aws:sqs":              "https://icons.terrastruct.com/aws%2FApplication%20Integration%2FAmazon-Simple-Queue-Service-SQS.svg",
    "aws:sns":              "https://icons.terrastruct.com/aws%2FApplication%20Integration%2FAmazon-Simple-Notification-Service-SNS.svg",
    # GCP — verified working on Terrastruct CDN
    "gcp:cloud_run":        "https://icons.terrastruct.com/gcp%2FProducts%20and%20services%2FCompute%2FCloud%20Run.svg",
    "gcp:compute_engine":   "https://icons.terrastruct.com/gcp%2FProducts%20and%20services%2FCompute%2FCompute%20Engine.svg",
    "gcp:cloud_functions":  "https://icons.terrastruct.com/gcp%2FProducts%20and%20services%2FCompute%2FCloud%20Functions.svg",
    "gcp:cloud_sql":        "https://icons.terrastruct.com/gcp%2FProducts%20and%20services%2FDatabases%2FCloud%20SQL.svg",
    "gcp:cloud_storage":    "https://icons.terrastruct.com/gcp%2FProducts%20and%20services%2FStorage%2FCloud%20Storage.svg",
    "gcp:pub_sub":          "https://icons.terrastruct.com/gcp%2FProducts%20and%20services%2FData%20Analytics%2FCloud%20PubSub.svg",
    "gcp:bigquery":         "https://icons.terrastruct.com/gcp%2FProducts%20and%20services%2FData%20Analytics%2FBigQuery.svg",
    "gcp:cloud_load_balancing": "https://icons.terrastruct.com/gcp%2FProducts%20and%20services%2FNetworking%2FCloud%20Load%20Balancing.svg",
    "gcp:cloud_cdn":        "https://icons.terrastruct.com/gcp%2FProducts%20and%20services%2FNetworking%2FCloud%20CDN.svg",
    "gcp:cloud_armor":      "https://icons.terrastruct.com/gcp%2FProducts%20and%20services%2FNetworking%2FCloud%20Armor.svg",
    # Azure and some AWS/GCP icons removed — Terrastruct CDN returns 403.
    # D2 generator gracefully skips missing icons (renders without icon).
}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

# Merge all PlantUML icon tables for easy lookup
ALL_PLANTUML_ICONS: dict[str, tuple[str, str]] = {
    **AWS_PLANTUML_ICONS,
    **AZURE_PLANTUML_ICONS,
    **GCP_PLANTUML_ICONS,
}


def get_plantuml_icon(icon_id: str) -> tuple[str, str] | None:
    """Return (relative_path, macro_name) for a PlantUML icon, or None."""
    return ALL_PLANTUML_ICONS.get(icon_id)


def get_plantuml_base(icon_id: str) -> str | None:
    """Return the CDN base URL for the given icon's cloud provider."""
    if icon_id.startswith("aws:"):
        return AWS_PLANTUML_BASE
    if icon_id.startswith("azure:"):
        return AZURE_PLANTUML_BASE
    if icon_id.startswith("gcp:"):
        return GCP_PLANTUML_BASE
    return None


def get_d2_icon(icon_id: str) -> str | None:
    """Return the D2 icon URL, or None."""
    return D2_ICONS.get(icon_id)
