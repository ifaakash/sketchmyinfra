/**
 * Mock API responses for local development.
 * Contains sample PUML code from existing repo diagrams.
 */

const MOCK_PUMLS = {
  vpc: `@startuml
!define AWSPuml https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v18.0/dist
!include AWSPuml/AWSCommon.puml
!include AWSPuml/Groups/AWSCloud.puml
!include AWSPuml/Groups/Region.puml
!include AWSPuml/Groups/VPC.puml
!include AWSPuml/Groups/PublicSubnet.puml
!include AWSPuml/Groups/PrivateSubnet.puml
!include AWSPuml/NetworkingContentDelivery/VPCNATGateway.puml
!include AWSPuml/NetworkingContentDelivery/VPCInternetGateway.puml
!include AWSPuml/Compute/EC2Instance.puml
!include AWSPuml/ManagementGovernance/SystemsManager.puml

skinparam linetype ortho
skinparam nodesep 60
skinparam ranksep 60

AWSCloudGroup(cloud) {
  RegionGroup(region, "us-east-1") {
    VPCGroup(vpc, "My Main VPC") {
      VPCInternetGateway(igw, "Internet Gateway", "")
      PublicSubnetGroup(pub, "Public Subnets (2)") {
        VPCNATGateway(nat, "NAT Gateway", "")
      }
      PrivateSubnetGroup(priv, "Private Subnets (2)") {
        EC2Instance(ec2, "App Server", "SSM Enabled")
        SystemsManager(ssm, "Systems Manager", "")
      }
    }
  }
}

ec2 -up-> nat : Outbound Traffic
nat -up-> igw : Internet Access
ec2 .right.> ssm : Managed by
@enduml`,

  microservice: `@startuml
skinparam backgroundColor #0f172a
skinparam defaultFontColor #e2e8f0
skinparam rectangleBorderColor #334155
skinparam rectangleBackgroundColor #1e293b
skinparam arrowColor #94a3b8
skinparam noteBorderColor #475569

title Microservices Architecture

rectangle "API Gateway" as gw #3b82f6
rectangle "Auth Service" as auth #8b5cf6
rectangle "Order Service" as orders #10b981
rectangle "Product Service" as products #f59e0b
queue "RabbitMQ" as mq #ef4444
database "PostgreSQL" as db #3b82f6
database "Redis Cache" as redis #dc2626

gw --> auth : Validate Token
gw --> orders : /api/orders
gw --> products : /api/products
orders --> mq : Publish Events
products --> mq : Publish Events
orders --> db : Read/Write
products --> db : Read/Write
auth --> redis : Session Cache
gw --> redis : Rate Limiting
@enduml`,

  cicd: `@startuml
skinparam backgroundColor #0f172a
skinparam defaultFontColor #e2e8f0
skinparam activityBorderColor #334155
skinparam activityBackgroundColor #1e293b
skinparam arrowColor #94a3b8

title CI/CD Pipeline

|Developer|
start
:Push to GitHub;

|GitHub Actions|
:Trigger Workflow;
:Run Linting;
:Run Unit Tests;
:Run Integration Tests;

if (Tests Pass?) then (yes)
  :Build Docker Image;
  :Push to ECR;

  |AWS|
  :Deploy to ECS Staging;
  :Run Smoke Tests;

  if (Smoke Tests Pass?) then (yes)
    :Deploy to ECS Production;
    :Notify Slack (Success);
  else (no)
    :Rollback;
    :Notify Slack (Failure);
  endif
else (no)
  |GitHub Actions|
  :Notify Slack (Build Failed);
endif

stop
@enduml`,

  sequence: `@startuml
skinparam backgroundColor #EEEBDC
skinparam handwritten true

actor User
participant "Web App" as Web
participant "Auth Service" as Auth
database "DB" as DB

User -> Web : Login Request
Web -> Auth : Validate Credentials
Auth -> DB : Query User
DB --> Auth : User Record
Auth --> Web : JWT Token
Web --> User : Login Success + Token

User -> Web : Access Resource
Web -> Auth : Verify Token
Auth --> Web : Token Valid
Web -> DB : Fetch Data
DB --> Web : Data
Web --> User : Resource Response
@enduml`
};

// Simple SVG placeholder for mock rendered diagrams
const MOCK_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
  <rect width="600" height="400" fill="#1e293b" rx="12"/>
  <rect x="40" y="30" width="160" height="60" rx="8" fill="#3b82f6" opacity="0.8"/>
  <text x="120" y="65" text-anchor="middle" fill="white" font-family="sans-serif" font-size="14">API Gateway</text>
  <rect x="220" y="120" width="160" height="60" rx="8" fill="#8b5cf6" opacity="0.8"/>
  <text x="300" y="155" text-anchor="middle" fill="white" font-family="sans-serif" font-size="14">Auth Service</text>
  <rect x="40" y="220" width="160" height="60" rx="8" fill="#10b981" opacity="0.8"/>
  <text x="120" y="255" text-anchor="middle" fill="white" font-family="sans-serif" font-size="14">Order Service</text>
  <rect x="400" y="220" width="160" height="60" rx="8" fill="#f59e0b" opacity="0.8"/>
  <text x="480" y="255" text-anchor="middle" fill="white" font-family="sans-serif" font-size="14">Product Service</text>
  <rect x="220" y="320" width="160" height="60" rx="8" fill="#ef4444" opacity="0.8"/>
  <text x="300" y="355" text-anchor="middle" fill="white" font-family="sans-serif" font-size="14">Database</text>
  <line x1="120" y1="90" x2="300" y2="120" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="120" y1="90" x2="120" y2="220" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="120" y1="90" x2="480" y2="220" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="120" y1="280" x2="300" y2="320" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="480" y1="280" x2="300" y2="320" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow)"/>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"/>
    </marker>
  </defs>
</svg>`;

/**
 * Match a user prompt to the best mock PUML template.
 */
function matchMockPuml(prompt) {
  const lower = prompt.toLowerCase();
  if (lower.includes('vpc') || lower.includes('subnet') || lower.includes('ec2') || lower.includes('aws')) {
    return MOCK_PUMLS.vpc;
  }
  if (lower.includes('microservice') || lower.includes('api gateway') || lower.includes('queue') || lower.includes('redis')) {
    return MOCK_PUMLS.microservice;
  }
  if (lower.includes('ci') || lower.includes('cd') || lower.includes('pipeline') || lower.includes('deploy') || lower.includes('jenkins')) {
    return MOCK_PUMLS.cicd;
  }
  if (lower.includes('sequence') || lower.includes('login') || lower.includes('auth') || lower.includes('flow')) {
    return MOCK_PUMLS.sequence;
  }
  // Default: return microservice
  return MOCK_PUMLS.microservice;
}

/**
 * Simulate /api/generate — returns PUML code after a delay.
 */
async function mockGenerate(prompt, context) {
  await new Promise(resolve => setTimeout(resolve, 1200 + Math.random() * 800));

  // 8% chance of mock error
  if (Math.random() < 0.08) {
    throw new Error('Gemini API rate limit exceeded. Please try again.');
  }

  const puml = matchMockPuml(prompt);
  return {
    puml: puml,
    prompt_used: prompt
  };
}

/**
 * Simulate /api/render — returns a mock SVG image after a delay.
 */
async function mockRender(puml, format) {
  await new Promise(resolve => setTimeout(resolve, 600 + Math.random() * 600));

  // 5% chance of mock render error
  if (Math.random() < 0.05) {
    throw new Error('PlantUML syntax error on line 12: unexpected token');
  }

  const svgBlob = new Blob([MOCK_SVG], { type: 'image/svg+xml' });
  const dataUri = await new Promise(resolve => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(svgBlob);
  });

  return {
    image: dataUri,
    format: 'svg'
  };
}
