import re

import httpx

from app.config import settings

def _normalize_gemini_text(text: str) -> str:
    """Normalize Unicode and whitespace issues in raw Gemini output.

    Applied before line-level sanitization to fix characters that affect
    PlantUML parsing at the structural level (outside labels).
    """
    # Non-breaking spaces → regular spaces
    text = text.replace("\u00a0", " ")
    # Smart/curly quotes used as string delimiters → straight quotes
    # (must happen before _sanitize_puml so label regex can match them)
    text = text.replace("\u201c", '"').replace("\u201d", '"')  # "" → ""
    text = text.replace("\u2018", "'").replace("\u2019", "'")  # '' → ''
    # Zero-width chars that occasionally appear in LLM output
    text = text.replace("\u200b", "")  # zero-width space
    text = text.replace("\u200c", "")  # zero-width non-joiner
    text = text.replace("\u200d", "")  # zero-width joiner
    text = text.replace("\ufeff", "")  # BOM
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def _sanitize_label(label: str) -> str:
    """Sanitize text inside a quoted PlantUML label.

    PlantUML interprets several characters as syntax even inside quotes.
    This fixes them to prevent rendering failures.
    """
    # HTML entities Gemini sometimes outputs — decode before handling &
    label = label.replace("&amp;", "&")
    label = label.replace("&lt;", "<")
    label = label.replace("&gt;", ">")
    label = label.replace("&quot;", "'")
    label = label.replace("&#39;", "'")
    # & → "and" — PlantUML parallel execution operator (after HTML decode)
    label = label.replace("&", "and")
    # ~ is a creole escape character — replace with -
    label = label.replace("~", "-")
    # | is a swimlane separator in activity diagrams — replace with /
    label = label.replace("|", "/")
    # En/em dashes → regular hyphen
    label = label.replace("\u2013", "-").replace("\u2014", "-")
    return label


def _fix_nested_skinparam(text: str) -> str:
    """Flatten nested skinparam blocks into valid PlantUML syntax.

    Gemini sometimes generates:
        skinparam {
          shadowing false
          rectangle { BackgroundColor #fff }
        }
    Which is invalid. This flattens it to:
        skinparam shadowing false
        skinparam rectangle { BackgroundColor #fff }
    """
    result = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        # Detect bare "skinparam {" (global wrapper — invalid)
        if stripped == "skinparam {":
            i += 1
            # Collect everything inside until the matching closing brace
            depth = 1
            while i < len(lines) and depth > 0:
                inner = lines[i].strip()
                if inner == "}":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                elif inner.endswith("{"):
                    # Nested block like "rectangle {" → "skinparam rectangle {"
                    result.append(f"skinparam {inner}")
                    depth += 1
                elif depth == 1 and inner and not inner.startswith("}"):
                    # Top-level property like "shadowing false"
                    result.append(f"skinparam {inner}")
                else:
                    result.append(lines[i])
                i += 1
        else:
            result.append(lines[i])
            i += 1
    return "\n".join(result)


def _resolve_variables(text: str) -> str:
    """Resolve !$variable definitions and inline their values.

    Gemini generates PlantUML preprocessor variables like:
        !$pvc_fill = "#D3D3D3" ' Light Gray
        rectangle "Foo" as foo #$pvc_fill
    But variable interpolation in #color positions is unreliable.
    This inlines the values directly for reliable rendering.
    """
    # Collect variable definitions: !$name = "value" (with optional trailing comment)
    var_defs = re.findall(r'!\$(\w+)\s*=\s*"([^"]*)"', text)
    if not var_defs:
        return text
    variables = dict(var_defs)

    # Remove the definition lines
    text = re.sub(r'^\s*!\$\w+\s*=\s*"[^"]*".*$', '', text, flags=re.MULTILINE)

    # Replace all $variable references with their values
    for name, value in variables.items():
        text = text.replace(f"${name}", value)

    return text


def _remove_invalid_skinparams(text: str) -> str:
    """Remove skinparam blocks for targets that don't exist in PlantUML.

    Known invalid targets: line, arrow (as block), etc.
    """
    result = []
    lines = text.split("\n")
    i = 0
    invalid_targets = {"line", "arrow"}
    while i < len(lines):
        stripped = lines[i].strip()
        match = re.match(r'^skinparam\s+(\w+)\s*\{', stripped)
        if match and match.group(1).lower() in invalid_targets:
            # Skip the entire block
            depth = 1
            i += 1
            while i < len(lines) and depth > 0:
                if lines[i].strip() == "}":
                    depth -= 1
                elif lines[i].strip().endswith("{"):
                    depth += 1
                i += 1
        else:
            result.append(lines[i])
            i += 1
    return "\n".join(result)


def _sanitize_puml(text: str) -> str:
    """Pre-process PlantUML code to fix common Gemini output issues.

    Catches syntax problems that would cause PlantUML rendering failures:
    - Preprocessor variable interpolation issues
    - Invalid skinparam targets (line, arrow)
    - Nested skinparam blocks
    - Inline comments (// or ' after code)
    - Special characters inside labels
    - Trailing semicolons
    - Invalid ArrowColor in element skinparams
    """
    # Structural fixes (operate on full text)
    text = _resolve_variables(text)
    text = _fix_nested_skinparam(text)
    text = _remove_invalid_skinparams(text)

    # Line-level fixes
    lines = []
    inside_skinparam = False
    for line in text.split("\n"):
        stripped = line.strip()
        # Preserve full-line comments (line starts with ')
        if stripped.startswith("'"):
            lines.append(line)
            continue
        # Track if we're inside a skinparam block
        if re.match(r'^skinparam\s+\w+\s*\{', stripped):
            inside_skinparam = True
        if inside_skinparam:
            if stripped == "}":
                inside_skinparam = False
            # Strip ArrowColor inside element skinparam (only valid globally)
            elif re.match(r'^\s*ArrowColor\s', stripped):
                lines.append("")
                continue
        # Strip inline comments on preprocessor directives (!$var = "val" ' comment)
        if stripped.startswith("!"):
            line = re.sub(r"'\s+.*$", '', line)
        # Remove trailing // comments (not inside strings)
        line = re.sub(r'\s*//\s.*$', '', line)
        # Remove trailing ' comments after code — only when ' follows a { or }
        # to avoid stripping legitimate apostrophes in labels
        line = re.sub(r"([{}])\s+'[^']*$", r'\1', line)
        # Remove trailing semicolons — not valid PlantUML syntax,
        # Gemini sometimes adds them treating PUML like a programming language
        line = re.sub(r';\s*$', '', line)
        # Sanitize all quoted labels for PlantUML-reserved characters
        line = re.sub(r'"([^"]*)"', lambda m: '"' + _sanitize_label(m.group(1)) + '"', line)
        lines.append(line)
    return "\n".join(lines)


GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{settings.gemini_model}:generateContent"
)

SYSTEM_PROMPT = """You are an expert infrastructure and software architect. Your job is to convert natural language descriptions into architecture diagrams.

RENDERER SELECTION (CRITICAL — output this FIRST):
- Your VERY FIRST line of output MUST be a renderer tag: :::renderer=plantuml::: OR :::renderer=mermaid:::
- Use "plantuml" ONLY when the diagram involves cloud provider services (AWS, GCP, Azure) that benefit from official icon libraries
- Use "mermaid" for ALL other diagrams: flowcharts, sequence diagrams, class diagrams, ER diagrams, state machines, mind maps, general system designs, non-cloud architectures
- After the renderer tag, output the diagram code (no explanations, no markdown, no code fences)

MERMAID RULES (when renderer=mermaid):
1. Output valid Mermaid syntax — do NOT wrap in @startuml/@enduml
2. Use appropriate diagram types:
   - graph TD/LR for flowcharts and architectures
   - sequenceDiagram for request flows
   - classDiagram for class/entity relationships
   - stateDiagram-v2 for state machines
   - erDiagram for ER diagrams
   - gantt for timelines
3. Subgraph rules (CRITICAL — violations cause parse errors):
   - ALWAYS use an ID for subgraphs: `subgraph my_id["Display Name"]` — NEVER `subgraph "Display Name"` without an ID
   - The `style` directive requires a node/subgraph ID, NOT a quoted string: `style my_id fill:#eee` — NEVER `style "Display Name" fill:#eee`
   - Use snake_case IDs for subgraphs (e.g. `school_grounds`, `main_building`)
4. Arrow labels MUST use pipe syntax: `A -->|label| B` — NEVER use colon syntax `A --> B : label` (that is PlantUML, not Mermaid)
5. Apply modern styling with %%{init: {'theme': 'base', 'themeVariables': ...}}%% at the top
6. Recommended theme config for clean look:
   %%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#dbeafe', 'primaryTextColor': '#1e40af', 'primaryBorderColor': '#3b82f6', 'lineColor': '#64748b', 'secondaryColor': '#f0fdf4', 'tertiaryColor': '#fef3c7', 'fontFamily': 'Inter, system-ui, sans-serif'}}}%%
7. Use different node shapes for different component types:
   - [Text] for rectangles (services)
   - [(Text)] for cylinders (databases)
   - ((Text)) for circles (users/external)
   - {Text} for diamonds (decisions)
   - ([Text]) for stadiums (queues/buffers)
8. Style rules (CRITICAL — malformed styles break the entire diagram):
   - Use `classDef` and `:::className` for reusable styles — define classDef at the TOP of the diagram, OUTSIDE subgraphs
   - In `style` and `classDef` values, use NO spaces after colons: `fill:#eee,stroke:#333` NOT `fill: #eee`
   - NO semicolons anywhere — Mermaid does not use semicolons
   - NO trailing commas in style values
   - Example: `classDef blue fill:#dbeafe,stroke:#3b82f6,stroke-width:2px`
9. Node ID rules:
   - NEVER start node IDs with a digit — use a letter prefix: `n_1` not `1`, `step_2` not `2`
   - Use snake_case for all IDs: `air_chamber` not `air-chamber`
   - NEVER use Mermaid keywords as IDs: `end`, `graph`, `subgraph`, `click`, `style`, `classDef`
   - ALWAYS quote label content that contains parentheses: `node["Text (detail)"]` NOT `node[Text (detail)]` — unquoted `(` triggers shape parsing
10. NEVER use `&` in labels — use "and" instead
11. NEVER put `<br>` outside of node labels — only INSIDE brackets: `Node["Line 1<br/>Line 2"]`
12. NEVER use escaped quotes `\"` or raw `"` inside node labels — use `&quot;` or reword. For inches use `in` (e.g. `12 in`)
13. Keep diagrams clean — avoid overlapping labels

PLANTUML RULES (when renderer=plantuml):
1. Always wrap output in @startuml and @enduml
2. Output ONLY the PlantUML code after the renderer tag
3. Use appropriate diagram types:
   - Component/deployment diagrams for cloud architectures
   - Sequence diagrams for request flows or auth flows
   - Activity diagrams for CI/CD pipelines or workflows
4. Keep diagrams readable — avoid cluttering with too many elements
5. Use meaningful labels and arrows with descriptions
6. When using `actor` elements, always add `skinparam actorStyle awesome`
7. Element declaration rules (CRITICAL — violations cause render failures):
   - NEVER define elements inline inside arrows or relationship lines
   - ALWAYS declare every element before referencing it in any arrow
   - Use `note right of X` / `note left of X` / `note bottom of X` — NEVER `note on X`
   - `actor` and `user` elements MUST be declared OUTSIDE all group containers
   - NEVER use inline comments — no `//` or `'` comments after code on the same line
   - NEVER use `&` in labels — use "and" instead
   - NEVER nest skinparam blocks — use flat blocks
   - NEVER use `ArrowColor` inside `skinparam rectangle` or `skinparam component` — global only
   - NEVER use multi-line body syntax `[...]` on rectangle/component — use `\n` in labels
   - NEVER use `!$variable` preprocessor variables for colors — use literal hex
   - NEVER use `skinparam line { }` — not a valid target

Cloud Provider Detection:
- Infer the cloud provider from service names in the user's prompt
- AWS indicators: VPC, EC2, ECS, S3, RDS, Lambda, ALB, Route53, CloudFront, SQS, SNS, DynamoDB, Fargate, ECR, CloudWatch, IAM
- GCP indicators: Cloud Run, GKE, BigQuery, Cloud SQL, Pub/Sub, Cloud Functions, Cloud Storage, Compute Engine, Cloud CDN, Cloud Armor, Artifact Registry
- Azure indicators: App Service, AKS, Azure SQL, Cosmos DB, Azure Functions, Blob Storage, Azure VM, Application Gateway, Front Door, Azure DevOps, Container Registry, Azure Monitor
- If the user explicitly names a cloud (e.g., "on GCP", "using Azure", "for AWS"), use that cloud
- If services from multiple clouds appear, include !define and !include blocks for ALL relevant clouds in one diagram
- If no cloud provider is identifiable, use the Non-Cloud Diagram Rules (generic PlantUML)

AWS Diagram Rules (when AWS services are mentioned):
- Always start with: allow_mixing
- Define icon base: !define AWSPuml https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist
- Always include: !include AWSPuml/AWSCommon.puml
- Include ONLY the specific icon .puml files you actually use — check the path carefully
- Use AWS grouping macros: AWSCloudGroup, RegionGroup, VPCGroup, PublicSubnetGroup, PrivateSubnetGroup
- Groups are in: AWSPuml/Groups/<Name>.puml
- CRITICAL: Use ONLY these verified icon paths (wrong names cause 404 errors):
  * Compute/Lambda.puml → Lambda(...)  [NOT LambdaFunction]
  * Compute/EC2Instance.puml → EC2Instance(...)
  * Compute/EC2AutoScaling.puml → EC2AutoScaling(...)  [NOT AutoScaling]
  * Containers/ElasticContainerService.puml → ElasticContainerService(...)
  * Containers/ElasticContainerServiceService.puml → ElasticContainerServiceService(...)
  * Containers/Fargate.puml → Fargate(...)  [NOT Compute/Fargate]
  * Containers/ElasticContainerRegistry.puml → ElasticContainerRegistry(...)
  * Containers/ElasticKubernetesService.puml → ElasticKubernetesService(...)
  * NetworkingContentDelivery/ElasticLoadBalancingApplicationLoadBalancer.puml → ElasticLoadBalancingApplicationLoadBalancer(...)
  * NetworkingContentDelivery/VPCInternetGateway.puml → VPCInternetGateway(...)
  * NetworkingContentDelivery/VPCNATGateway.puml → VPCNATGateway(...)
  * NetworkingContentDelivery/CloudFront.puml → CloudFront(...)  [NOT CloudFrontDistribution]
  * NetworkingContentDelivery/Route53.puml → Route53(...)
  * NetworkingContentDelivery/Route53HostedZone.puml → Route53HostedZone(...)
  * Database/RDS.puml → RDS(...)  [NOT RDSInstance]
  * Database/AuroraMariaDBInstance.puml → AuroraMariaDBInstance(...)
  * Database/AuroraPostgreSQLInstance.puml → AuroraPostgreSQLInstance(...)
  * Database/DynamoDB.puml → DynamoDB(...)
  * Database/ElastiCache.puml → ElastiCache(...)  [generic, use when no specific engine needed]
  * Database/ElastiCacheElastiCacheforRedis.puml → ElastiCacheElastiCacheforRedis(...)  [Redis specifically — NOT ElastiCacheRedis]
  * Database/ElastiCacheElastiCacheforMemcached.puml → ElastiCacheElastiCacheforMemcached(...)  [Memcached specifically]
  * Storage/SimpleStorageService.puml → SimpleStorageService(...)  [NOT S3]
  * Storage/SimpleStorageServiceBucket.puml → SimpleStorageServiceBucket(...)
  * ApplicationIntegration/SimpleQueueService.puml → SimpleQueueService(...)  [NOT SQS]
  * ApplicationIntegration/SimpleNotificationService.puml → SimpleNotificationService(...)  [NOT SNS]
  * ApplicationIntegration/EventBridge.puml → EventBridge(...)
  * NetworkingContentDelivery/APIGateway.puml → APIGateway(...)  [NOT ApplicationIntegration/APIGateway]
  * ManagementGovernance/CloudWatch.puml → CloudWatch(...)
  * ManagementGovernance/CloudWatchAlarm.puml → CloudWatchAlarm(...)
  * ManagementGovernance/CloudWatchLogs.puml → CloudWatchLogs(...)
  * ManagementGovernance/CloudWatchRule.puml → CloudWatchRule(...)
  * ManagementGovernance/CloudWatchEventTimeBased.puml → CloudWatchEventTimeBased(...)  [scheduled/cron triggers — NOT CloudWatchEvents]
  * ManagementGovernance/CloudWatchEventEventBased.puml → CloudWatchEventEventBased(...)  [event-driven triggers — NOT CloudWatchEvents]
  * ManagementGovernance/CloudTrail.puml → CloudTrail(...)
  * ManagementGovernance/SystemsManager.puml → SystemsManager(...)
  * ManagementGovernance/CloudFormation.puml → CloudFormation(...)
  * ApplicationIntegration/StepFunctions.puml → StepFunctions(...)
  * ApplicationIntegration/EventBridgeScheduler.puml → EventBridgeScheduler(...)
  * Analytics/Glue.puml → Glue(...)
  * Analytics/Redshift.puml → Redshift(...)
  * Analytics/QuickSight.puml → QuickSight(...)
  * Analytics/Athena.puml → Athena(...)
  * Analytics/KinesisDataStreams.puml → KinesisDataStreams(...)
  * Analytics/EMR.puml → EMR(...)
  * SecurityIdentityCompliance/IdentityandAccessManagement.puml → IdentityandAccessManagement(...)  [NOT IAM]
  * SecurityIdentityCompliance/WAF.puml → WAF(...)
- KNOWN MISSING icons — these do NOT exist in the library, use a plain `rectangle` instead: SecurityGroup, TargetGroup, NATGateway (use VPCNATGateway), InternetGateway (use VPCInternetGateway)
- If a service has no verified icon above, use a plain rectangle or component element instead — never guess a path
- Do NOT use Internetalt1 or other General/ icons — they are unreliable. Use a plain `actor` element for users with `skinparam actorStyle awesome` for a person silhouette icon
- All AWS icon macros require exactly 3 arguments: `IconName(alias, "Label", "Technology")` — if technology is not applicable use `""` as the third argument
- Use dotted lines (.l.>, .r.>, ..>) for secondary flows like logs and monitoring
- Use solid lines (-->) for primary traffic flows
- Use rectangle blocks to group related services logically

GCP Diagram Rules (when GCP services are mentioned):
- Always start with: allow_mixing
- Define icon base: !define GCPPuml https://raw.githubusercontent.com/Crashedmind/PlantUML-icons-GCP/master/dist
- Always include: !include GCPPuml/GCPCommon.puml
- Include ONLY the specific icon .puml files you actually use
- Icons are in category folders: GCPPuml/Compute/, GCPPuml/Databases/, GCPPuml/Networking/, GCPPuml/Storage/, GCPPuml/Security/, GCPPuml/DevOps/, GCPPuml/Data_Analytics/
- IMPORTANT: GCP icon filenames and macros use underscores, not CamelCase
- Common icon file names: Cloud_Run, Kubernetes_Engine, Cloud_SQL, Cloud_Bigtable, Cloud_Storage, Cloud_Functions, Compute_Engine, Cloud_CDN, Cloud_Load_Balancing, Cloud_Armor, Cloud_Pub_Sub
- The macro name matches the filename: e.g., Cloud_Run(alias, "label", "tech")
- Use rectangle blocks with labels for GCP projects and regions (no built-in GCP group macros):
  rectangle "GCP Project" as gcp { rectangle "us-central1" as region { ... } }
- Use dotted lines for secondary flows, solid lines for primary traffic

Azure Diagram Rules (when Azure services are mentioned):
- Always start with: allow_mixing
- Define icon base: !define AzurePuml https://raw.githubusercontent.com/plantuml-stdlib/Azure-PlantUML/master/dist
- Always include: !include AzurePuml/AzureCommon.puml
- Include ONLY the specific icon .puml files you actually use
- Icons are in category folders: AzurePuml/Compute/, AzurePuml/Databases/, AzurePuml/Networking/, AzurePuml/Storage/, AzurePuml/Security/, AzurePuml/Containers/, AzurePuml/Web/
- IMPORTANT path gotchas: AzureAppService is in Compute/ (not Web/), and AzureSqlDatabase uses lowercase 'ql' (not 'SQL')
- Common icon names: AzureAppService (Compute/), AzureKubernetesService (Containers/), AzureSqlDatabase (Databases/), AzureCosmosDb (Databases/), AzureBlobStorage (Storage/), AzureFunctions (Compute/), AzureVirtualMachine (Compute/), AzureApplicationGateway (Networking/), AzureFrontDoor (Networking/), AzureContainerRegistry (Containers/)
- Use rectangle blocks with labels for resource groups and regions:
  rectangle "Azure" as azure { rectangle "East US" as region { rectangle "Resource Group" as rg { ... } } }
- Use dotted lines for secondary flows, solid lines for primary traffic

Non-Cloud Diagram Rules:
- Use skinparam for clean styling
- Use rectangle, database, queue, cloud, node, component, frame, package elements
- Use color coding to group related services (compute=#3b82f6, database=#10b981, networking=#f59e0b)

Dynamic Defaults:
- If the user specifies a region (e.g., "eu-west-1", "us-central1", "West Europe"), use that EXACT region in the diagram
- If no region is specified, use reasonable defaults: us-east-1 (AWS), us-central1 (GCP), eastus (Azure)
- If the user specifies a CIDR range, use it. Otherwise default to 10.0.0.0/16
- Always prefer user-provided values for instance types, scaling counts, naming, or any other specifics

Multi-Cloud Diagrams:
- When services from multiple clouds appear, include !define and !include blocks for ALL relevant clouds at the top of the diagram
- Use separate rectangle groups for each cloud provider
- Connect cross-cloud services with labeled arrows indicating the integration method (API, VPN, Pub/Sub, etc.)

Here is a reference example of a well-structured AWS diagram:

@startuml
allow_mixing
!define AWSPuml https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist
!include AWSPuml/AWSCommon.puml
!include AWSPuml/Groups/AWSCloud.puml
!include AWSPuml/Groups/Region.puml
!include AWSPuml/Groups/VPC.puml
!include AWSPuml/Groups/PublicSubnet.puml
!include AWSPuml/Groups/PrivateSubnet.puml
!include AWSPuml/NetworkingContentDelivery/ElasticLoadBalancingApplicationLoadBalancer.puml
!include AWSPuml/NetworkingContentDelivery/VPCInternetGateway.puml
!include AWSPuml/NetworkingContentDelivery/VPCNATGateway.puml
!include AWSPuml/Containers/ElasticContainerService.puml
!include AWSPuml/Database/AuroraMariaDBInstance.puml
!include AWSPuml/ManagementGovernance/CloudWatch.puml

skinparam actorStyle awesome
top to bottom direction

AWSCloudGroup(cloud) {
  RegionGroup(region, "us-east-1") {
    VPCGroup(vpc, "VPC (10.0.0.0/16)") {
      VPCInternetGateway(igw, "Internet Gateway", "")
      PublicSubnetGroup(pub, "Public Subnets") {
        ElasticLoadBalancingApplicationLoadBalancer(alb, "ALB", "Public Ingress")
        VPCNATGateway(nat, "NAT Gateway", "Outbound")
      }
      PrivateSubnetGroup(priv, "Private Subnets") {
        ElasticContainerService(ecs, "ECS Fargate", "App Service")
        AuroraMariaDBInstance(db, "RDS PostgreSQL", "Database")
      }
    }
    CloudWatch(cw, "CloudWatch", "Logs & Metrics")
  }
}

actor "User" as user
user --> alb : HTTPS
alb --> ecs : Routes Traffic
ecs --> db : SQL Queries
ecs .r.> cw : App Logs
nat ..> igw : Internet Access
@enduml

Here is a reference example of a well-structured GCP diagram:

@startuml
allow_mixing
!define GCPPuml https://raw.githubusercontent.com/Crashedmind/PlantUML-icons-GCP/master/dist
!include GCPPuml/GCPCommon.puml
!include GCPPuml/Compute/Cloud_Run.puml
!include GCPPuml/Databases/Cloud_SQL.puml
!include GCPPuml/Networking/Cloud_Load_Balancing.puml

skinparam actorStyle awesome
top to bottom direction

rectangle "GCP Project" as gcp {
  rectangle "us-central1" as region {
    Cloud_Load_Balancing(lb, "Cloud LB", "HTTPS")
    Cloud_Run(run, "Cloud Run", "App Service")
    Cloud_SQL(sql, "Cloud SQL", "PostgreSQL")
  }
}

actor "User" as user
user --> lb : HTTPS
lb --> run : Routes Traffic
run --> sql : Queries
@enduml

Here is a reference example of a well-structured Azure diagram:

@startuml
allow_mixing
!define AzurePuml https://raw.githubusercontent.com/plantuml-stdlib/Azure-PlantUML/master/dist
!include AzurePuml/AzureCommon.puml
!include AzurePuml/Compute/AzureAppService.puml
!include AzurePuml/Databases/AzureSqlDatabase.puml
!include AzurePuml/Networking/AzureApplicationGateway.puml

skinparam actorStyle awesome
top to bottom direction

rectangle "Azure" as azure {
  rectangle "East US" as region {
    AzureApplicationGateway(agw, "App Gateway", "HTTPS Ingress")
    AzureAppService(app, "App Service", "Web App")
    AzureSqlDatabase(db, "Azure SQL", "Database")
  }
}

actor "User" as user
user --> agw : HTTPS
agw --> app : Routes Traffic
app --> db : Queries
@enduml
"""

_FIX_PROMPT_HINTS = """\
Fix the syntax error. Common mistakes to check:
- Elements defined inline inside arrows — INVALID: `A --> Component(b, "label", "")` — VALID: declare Component(b, ...) first, then write `A --> b`
- `note on X` does not exist — use `note right of X`, `note left of X`, or `note bottom of X`
- `actor` or `user` declared inside group containers (AWSCloudGroup, VPCGroup, etc.) — must be declared outside all groups
- Elements referenced in arrows before being declared
- Inline comments (`//` or `'` after code on the same line) — PlantUML only supports full-line `'` comments
- `<<stereotype>>` combined with `#color` on package/rectangle declarations — use one or the other, or use a separate `skinparam` instead
- `&` in labels — PlantUML treats `&` as a parallel operator; use "and" instead
- Nested `skinparam { rectangle { ... } }` — INVALID. Flatten to `skinparam shadowing false` and `skinparam rectangle { ... }` as separate blocks
- `ArrowColor` inside `skinparam rectangle` or `skinparam component` — INVALID. Use `skinparam ArrowColor #color` at top level
- Multi-line body `[...]` on rectangle/component elements — that syntax is only for class fields. Use `\\n` in labels instead
- `skinparam element.stereotype` (e.g. `skinparam rectangle.pvc`) — INVALID. Use `<<stereotype>>` on individual elements and define styles with `skinparam` separately
- `!$variable` preprocessor variables for colors — unreliable in `#color` positions. Use literal hex colors directly
- `skinparam line { }` — `line` is not a valid skinparam target. Use `skinparam ArrowThickness` and `skinparam ArrowColor` instead

Output ONLY the corrected PlantUML code — no explanations, no markdown."""


def _build_fix_prompt(puml: str, error: str) -> str:
    """Build the fix prompt safely — avoids str.format() which chokes on { } in PUML."""
    return (
        "The following PlantUML code failed to render with this error:\n\n"
        f"Error: {error}\n\n"
        f"Broken code:\n```\n{puml}\n```\n\n"
        + _FIX_PROMPT_HINTS
    )


def _build_iteration_prompt(context: str, renderer: str = "plantuml") -> str:
    """Build the iteration prompt safely — avoids str.format() on diagram content."""
    fmt = "PlantUML" if renderer == "plantuml" else "Mermaid"
    return (
        f"The user wants to modify an existing diagram. Here is the current {fmt} code:\n\n"
        f"```\n{context}\n```\n\n"
        f"Apply the user's requested changes below. Output the renderer tag on the first line "
        f"(:::renderer={renderer}:::) followed by ONLY the updated {fmt} code — no explanations."
    )


CLOUD_KEYWORDS = {
    "aws", "ec2", "ecs", "s3", "rds", "lambda", "vpc", "alb", "route53",
    "cloudfront", "sqs", "sns", "dynamodb", "fargate", "ecr", "cloudwatch",
    "iam", "elastic beanstalk", "api gateway", "step functions", "kinesis",
    "gcp", "cloud run", "gke", "bigquery", "cloud sql", "pub/sub",
    "cloud functions", "cloud storage", "compute engine", "cloud cdn",
    "cloud armor", "artifact registry", "cloud spanner",
    "azure", "aks", "azure sql", "cosmos db", "azure functions",
    "blob storage", "app service", "front door", "azure devops",
    "container registry", "azure monitor", "azure vm",
}


def classify_prompt(prompt: str) -> str:
    """Classify a user prompt as needing plantuml or mermaid rendering."""
    lower = prompt.lower()
    if any(kw in lower for kw in CLOUD_KEYWORDS):
        return "plantuml"
    return "mermaid"


def _parse_renderer_tag(text: str) -> tuple[str, str]:
    """Parse the :::renderer=X::: tag from Gemini output.

    Returns (renderer, code) tuple. Falls back to content-based detection
    if the tag is missing.
    """
    # Look for the renderer tag on the first non-empty line
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        match = re.match(r'^:::renderer=(plantuml|mermaid):::\s*$', stripped)
        if match:
            renderer = match.group(1)
            code = "\n".join(lines[i + 1:]).strip()
            return renderer, code
        # Stop looking after first non-empty, non-tag line
        if stripped:
            break

    # Fallback: detect from content
    if "@startuml" in text:
        return "plantuml", text
    # Mermaid diagram types
    if any(kw in text for kw in ["graph ", "flowchart ", "sequenceDiagram", "classDiagram",
                                   "stateDiagram", "erDiagram", "gantt", "%%{"]):
        return "mermaid", text

    # Default to mermaid for non-cloud content
    return "mermaid", text


def _strip_fences(text: str) -> str:
    """Strip markdown code fences if Gemini wraps the output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


def _post_process_puml(text: str) -> str:
    """Apply all PlantUML-specific sanitization and validation."""
    text = _normalize_gemini_text(text)
    text = _sanitize_puml(text)

    if "@startuml" not in text:
        raise GeminiError("Gemini did not produce valid PlantUML code")
    if "@enduml" not in text:
        raise GeminiError("Diagram generation was truncated — try simplifying your prompt")
    return text


# Characters that trigger Mermaid shape/syntax parsing inside labels
_MERMAID_DANGER_CHARS = set('(){}|')


def _fix_mermaid_label_quotes(m):
    """Replace backslash-escaped quotes inside a bracket label."""
    prefix, content, suffix = m.group(1), m.group(2), m.group(3)
    content = content.replace('\\"', '&quot;')
    content = content.replace('"', '&quot;')
    return prefix + content + suffix


def _mermaid_make_safe_id(name: str, prefix: str = '') -> str:
    """Generate a safe Mermaid ID from a display name."""
    auto_id = re.sub(r'[^a-zA-Z0-9]', '_', name).strip('_').lower()
    if not auto_id:
        auto_id = 'node'
    if auto_id[0].isdigit():
        auto_id = (prefix or 'n') + '_' + auto_id
    return auto_id


def _sanitize_mermaid(text: str) -> str:
    """Fix common Mermaid syntax issues from Gemini output.

    Comprehensive sanitizer covering ALL known failure patterns:

    Structural:
    - Subgraph IDs, style references
    - Trailing semicolons, commas
    - Stray <br> outside labels
    - Node IDs starting with digits
    - `direction` keyword outside subgraphs
    - Style value spacing

    Labels (all contexts):
    - [...] square labels with ( ) { } | -- → auto-quote
    - (...) round/stadium labels with nested parens → quote inner
    - {...} diamond labels with nested parens → quote inner
    - ((...)) double-circle labels with nested parens
    - |...| pipe arrow labels — strip parens, replace &
    - Escaped quotes in quoted labels
    - PlantUML colon arrow syntax → pipe syntax
    """
    lines = []
    subgraph_ids = {}
    subgraph_depth = 0

    for line in text.split("\n"):
        stripped = line.strip()

        # --- Skip empty lines ---
        if not stripped:
            lines.append(line)
            continue

        # --- Trailing semicolons (not valid Mermaid) ---
        line = re.sub(r';\s*$', '', line)
        stripped = line.strip()

        # --- Track subgraph depth ---
        if re.match(r'^(\s*)subgraph\s', stripped):
            subgraph_depth += 1
        if stripped == 'end' and subgraph_depth > 0:
            subgraph_depth -= 1

        # --- `direction` at top level (only valid inside subgraph) ---
        if re.match(r'^\s*direction\s+(TB|BT|LR|RL|TD)\s*$', stripped) and subgraph_depth == 0:
            # Skip — direction outside subgraph causes parse errors
            continue

        # --- Subgraph without ID → add auto-generated ID ---
        match = re.match(r'^(\s*)subgraph\s+"([^"]+)"\s*$', line)
        if match:
            indent, name = match.groups()
            auto_id = _mermaid_make_safe_id(name, 's')
            subgraph_ids[name] = auto_id
            lines.append(f'{indent}subgraph {auto_id}["{name}"]')
            continue

        # --- style "Quoted Name" → style auto_id ---
        style_match = re.match(r'^(\s*)style\s+"([^"]+)"(.*)$', line)
        if style_match:
            indent, name, rest = style_match.groups()
            sid = subgraph_ids.get(name, _mermaid_make_safe_id(name))
            lines.append(f'{indent}style {sid}{rest}')
            continue

        # --- Stray <br> / <br/> outside node labels ---
        if stripped in ('<br>', '<br/>'):
            continue
        line = re.sub(r'<br/?>\s*$', '', line)

        # --- Style/classDef value fixes ---
        if re.match(r'^\s*(style|classDef|linkStyle)\s', stripped):
            # Remove spaces after colons in CSS values
            line = re.sub(r'(\w):\s+([#\d])', r'\1:\2', line)
            # Remove trailing commas
            line = re.sub(r',\s*$', '', line)

        # --- Square bracket labels [...] with dangerous chars → quote ---
        def _quote_square_label(m):
            content = m.group(1)
            if content.startswith('"') and content.endswith('"'):
                return '[' + content + ']'
            # Dangerous: ( ) { } | or -- inside unquoted label
            if _MERMAID_DANGER_CHARS.intersection(content) or '--' in content:
                content = content.replace('"', '&quot;')
                return '["' + content + '"]'
            return '[' + content + ']'

        line = re.sub(r'\[([^\]]+)\]', _quote_square_label, line)

        # --- Round labels (...) with nested parens → convert to ["..."] ---
        # Match: node_id(Text (detail)) but NOT node_id("already quoted")
        # Also skip (( )) double-circle — handled separately
        def _fix_round_label(m):
            node_id = m.group(1)
            content = m.group(2)
            if content.startswith('"') and content.endswith('"'):
                return f'{node_id}({content})'
            # If content has nested parens, switch to square-quoted
            if '(' in content or ')' in content:
                content = content.replace('"', '&quot;')
                return f'{node_id}["{content}"]'
            return f'{node_id}({content})'

        # Match id(content) where content may have nested parens
        # Skip id((...)) double-circle and style/classDef/graph lines
        if not re.match(r'^\s*(style|classDef|linkStyle|graph|flowchart|subgraph)\s', stripped):
            # Use a simple approach: find id( then balance parens to find matching )
            def _fix_round_labels_in_line(line):
                result = []
                i = 0
                while i < len(line):
                    # Look for pattern: word_chars(  but NOT word_chars((
                    match = re.match(r'(\w+)\((?!\()', line[i:])
                    if match:
                        node_id = match.group(1)
                        start = i + len(match.group(0))
                        # Find the matching closing paren
                        depth = 1
                        j = start
                        while j < len(line) and depth > 0:
                            if line[j] == '(':
                                depth += 1
                            elif line[j] == ')':
                                depth -= 1
                            j += 1
                        if depth == 0:
                            content = line[start:j - 1]
                            fixed = _fix_round_label_content(node_id, content)
                            result.append(fixed)
                            i = j
                            continue
                    result.append(line[i])
                    i += 1
                return ''.join(result)

            def _fix_round_label_content(node_id, content):
                if content.startswith('"') and content.endswith('"'):
                    return f'{node_id}({content})'
                if '(' in content or ')' in content:
                    content = content.replace('"', '&quot;')
                    return f'{node_id}["{content}"]'
                return f'{node_id}({content})'

            line = _fix_round_labels_in_line(line)

        # --- Double-circle labels ((...)) with nested parens ---
        def _fix_double_circle(m):
            node_id = m.group(1)
            content = m.group(2)
            if '(' in content or ')' in content:
                content = content.replace('(', '').replace(')', '')
            return f'{node_id}(({content}))'

        line = re.sub(r'(\w+)\(\(([^)]+)\)\)', _fix_double_circle, line)

        # --- Diamond labels {...} with nested parens ---
        def _fix_diamond_label(m):
            full = m.group(0)
            # Skip classDef/style blocks (which use { } for grouping)
            if re.match(r'^\s*(classDef|style|linkStyle)', stripped):
                return full
            node_id = m.group(1)
            content = m.group(2)
            if content.startswith('"') and content.endswith('"'):
                return full
            if '(' in content or ')' in content or '|' in content:
                content = content.replace('(', '').replace(')', '')
                content = content.replace('|', '/')
                content = content.replace('"', '&quot;')
                return f'{node_id}{{"{content}"}}'
            return full

        line = re.sub(r'(\w+)\{([^}]+)\}', _fix_diamond_label, line)

        # --- Escaped quotes inside quoted labels ---
        line = re.sub(r'(\[")(.*?)("\])', _fix_mermaid_label_quotes, line)
        line = re.sub(r'(\(")(.*?)("\))', _fix_mermaid_label_quotes, line)

        # --- PlantUML-style "A --> B : label" → Mermaid "A -->|label| B" ---
        line = re.sub(
            r'(\S+\s*)(-->|---->|-.->|-\.->|---|-\.-)(\s*)(\S+)\s*:\s*(.+)$',
            r'\1\2|\5|\3\4',
            line,
        )

        # --- Sanitize pipe arrow labels |...| ---
        def _sanitize_pipe_label(m):
            content = m.group(1)
            content = content.replace('(', '').replace(')', '')
            content = content.replace('&', 'and')
            content = content.replace('|', '/')
            content = content.replace('#', '')
            return '|' + content + '|'

        line = re.sub(r'\|([^|]+)\|', _sanitize_pipe_label, line)

        # --- Node IDs starting with digit → prefix with n_ ---
        node_match = re.match(r'^(\s*)(\d+\w*)([\[\(\{<])', line)
        if node_match:
            indent, node_id, bracket = node_match.groups()
            line = f'{indent}n_{node_id}{bracket}' + line[node_match.end():]

        # --- Digit nodes in arrows ---
        line = re.sub(
            r'(?<!\w)(\d+\w*)(\s*)(-->|---|-\.->|-.->)',
            lambda m: f'n_{m.group(1)}{m.group(2)}{m.group(3)}',
            line,
        )
        line = re.sub(
            r'(-->|---|-\.->|-.->)(\s*)(\d+\w*)(?!\w)',
            lambda m: f'{m.group(1)}{m.group(2)}n_{m.group(3)}',
            line,
        )

        lines.append(line)

    return "\n".join(lines)


def _post_process_mermaid(text: str) -> str:
    """Apply Mermaid-specific cleanup."""
    text = _normalize_gemini_text(text)
    # Strip any accidental @startuml/@enduml if Gemini got confused
    text = re.sub(r'@startuml\s*\n?', '', text)
    text = re.sub(r'@enduml\s*\n?', '', text)
    text = _sanitize_mermaid(text)
    if not text.strip():
        raise GeminiError("Gemini did not produce valid Mermaid code")
    return text


async def generate_diagram(prompt: str, context: str | None = None,
                           context_renderer: str | None = None) -> tuple[str, str]:
    """Generate a diagram — returns (renderer, code) tuple.

    Gemini classifies the prompt and outputs the appropriate format
    (PlantUML or Mermaid). Falls back to keyword-based classification
    if Gemini's renderer tag is missing.
    """
    parts = []

    if context:
        renderer_hint = context_renderer or "plantuml"
        parts.append({"text": _build_iteration_prompt(context, renderer_hint)})

    parts.append({"text": prompt})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GEMINI_URL,
            params={"key": settings.gemini_api_key},
            json=payload,
        )

    if response.status_code != 200:
        error = response.json().get("error", {}).get("message", "Unknown error")
        raise GeminiError(f"Gemini API error: {error}")

    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    text = _strip_fences(text)

    renderer, code = _parse_renderer_tag(text)

    # Safety net: if Gemini said mermaid but content has cloud keywords, override
    if renderer == "mermaid" and classify_prompt(prompt) == "plantuml":
        # Re-check — if code actually has @startuml, trust Gemini
        if "@startuml" not in code:
            renderer = "plantuml"

    if renderer == "plantuml":
        code = _post_process_puml(code)
    else:
        code = _post_process_mermaid(code)

    return renderer, code


async def generate_puml(prompt: str, context: str | None = None) -> str:
    """Legacy wrapper — generates PlantUML only. Kept for backward compat."""
    _, code = await generate_diagram(prompt, context, context_renderer="plantuml")
    return code


async def fix_puml(puml: str, error: str) -> str:
    """Ask Gemini to fix a PlantUML syntax error and return corrected code."""
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": _build_fix_prompt(puml, error)}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GEMINI_URL,
            params={"key": settings.gemini_api_key},
            json=payload,
        )

    if response.status_code != 200:
        err_msg = response.json().get("error", {}).get("message", "Unknown error")
        raise GeminiError(f"Gemini fix error: {err_msg}")

    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]

    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    text = _normalize_gemini_text(text)
    text = _sanitize_puml(text)

    if "@startuml" not in text:
        raise GeminiError("Gemini did not produce valid PlantUML after fix attempt")

    if "@enduml" not in text:
        raise GeminiError("Diagram fix was truncated — try simplifying your prompt")

    return text


async def fix_mermaid(code: str, error: str) -> str:
    """Ask Gemini to fix a Mermaid syntax error and return corrected code."""
    fix_prompt = (
        "The following Mermaid diagram code failed to render with this error:\n\n"
        f"Error: {error}\n\n"
        f"Broken code:\n```\n{code}\n```\n\n"
        "Fix the syntax error. Output :::renderer=mermaid::: on the first line, "
        "then ONLY the corrected Mermaid code — no explanations, no markdown."
    )

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": fix_prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GEMINI_URL,
            params={"key": settings.gemini_api_key},
            json=payload,
        )

    if response.status_code != 200:
        err_msg = response.json().get("error", {}).get("message", "Unknown error")
        raise GeminiError(f"Gemini fix error: {err_msg}")

    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    text = _strip_fences(text)

    _, fixed_code = _parse_renderer_tag(text)
    fixed_code = _post_process_mermaid(fixed_code)

    return fixed_code


class GeminiError(Exception):
    pass
