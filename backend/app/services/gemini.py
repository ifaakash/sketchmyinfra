import httpx

from app.config import settings

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{settings.gemini_model}:generateContent"
)

SYSTEM_PROMPT = """You are an expert infrastructure and software architect. Your job is to convert natural language descriptions into valid PlantUML code.

Rules:
1. Always wrap output in @startuml and @enduml
2. Output ONLY the PlantUML code — no explanations, no markdown, no code fences
3. Use appropriate diagram types:
   - Component/deployment diagrams for architectures
   - Sequence diagrams for request flows or auth flows
   - Activity diagrams for CI/CD pipelines or workflows
4. Keep diagrams readable — avoid cluttering with too many elements
5. Use meaningful labels and arrows with descriptions

AWS Diagram Rules (when AWS services are mentioned):
- Always start with: allow_mixing
- Define icon base: !define AWSPuml https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist
- Always include: !include AWSPuml/AWSCommon.puml
- Include ONLY the specific icon .puml files you actually use — check the path carefully
- Use AWS grouping macros: AWSCloudGroup, RegionGroup, VPCGroup, PublicSubnetGroup, PrivateSubnetGroup
- Groups are in: AWSPuml/Groups/<Name>.puml
- Icons are in category folders like: AWSPuml/Compute/, AWSPuml/Database/, AWSPuml/NetworkingContentDelivery/, AWSPuml/Containers/, AWSPuml/Storage/, AWSPuml/ManagementGovernance/, AWSPuml/SecurityIdentityCompliance/, AWSPuml/General/
- Common icon names: ElasticLoadBalancingApplicationLoadBalancer, ElasticContainerService, ElasticContainerServiceService, EC2Instance, EC2AutoScaling, AuroraMariaDBInstance, AuroraPostgreSQLInstance, SimpleStorageService, CloudWatch, Route53, Route53HostedZone, VPCInternetGateway, VPCNATGateway
- Do NOT use Internetalt1 or other General/ icons — they are unreliable. Use a plain "actor" or "cloud" element for internet/users instead
- Use dotted lines (.l.>, .r.>, ..>) for secondary flows like logs and monitoring
- Use solid lines (-->) for primary traffic flows
- Use rectangle blocks to group related services logically

Non-AWS Diagram Rules:
- Use skinparam for clean styling
- Use rectangle, database, queue, cloud, node, component, frame, package elements
- Use color coding to group related services (compute=#3b82f6, database=#10b981, networking=#f59e0b)

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
"""

ITERATION_PROMPT = """The user wants to modify an existing diagram. Here is the current PlantUML code:

```
{context}
```

Apply the user's requested changes below. Output ONLY the updated PlantUML code — no explanations."""


async def generate_puml(prompt: str, context: str | None = None) -> str:
    """Call Gemini API to generate PlantUML code from a natural language prompt."""
    parts = []

    if context:
        parts.append({"text": ITERATION_PROMPT.format(context=context)})

    parts.append({"text": prompt})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096,
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

    # Strip markdown code fences if Gemini wraps the output
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```plantuml or ```) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    if "@startuml" not in text:
        raise GeminiError("Gemini did not produce valid PlantUML code")

    return text


class GeminiError(Exception):
    pass
