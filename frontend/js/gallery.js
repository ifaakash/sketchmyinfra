/**
 * Gallery — renders curated example diagrams into the #gallery section.
 * Each card lazy-renders via apiRender() when scrolled into view.
 */

const GALLERY_ITEMS = [
  {
    prompt: "AWS serverless REST API with Cognito auth, API Gateway, Lambda, and DynamoDB",
    puml: `@startuml
!define AWSPuml https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist
!include AWSPuml/AWSCommon.puml
!include AWSPuml/SecurityIdentityCompliance/Cognito.puml
!include AWSPuml/NetworkingContentDelivery/APIGateway.puml
!include AWSPuml/Compute/Lambda.puml
!include AWSPuml/Database/DynamoDB.puml
allow_mixing

actor "User" as user
Cognito(auth, "Cognito", "Auth")
APIGateway(apigw, "API Gateway", "REST")
Lambda(fn, "Handler", "Function")
DynamoDB(db, "Items", "DynamoDB")

user --> auth : Login
user --> apigw : HTTPS
apigw --> fn : Invoke
fn --> db : Read/Write
@enduml`,
  },
  {
    prompt: "AWS three-tier app — ALB, ECS Fargate in private subnets, Aurora PostgreSQL, and S3 for static assets",
    puml: `@startuml
!define AWSPuml https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist
!include AWSPuml/AWSCommon.puml
!include AWSPuml/NetworkingContentDelivery/ElasticLoadBalancing.puml
!include AWSPuml/Containers/ElasticContainerService.puml
!include AWSPuml/Database/RDSPostgreSQLinstance.puml
!include AWSPuml/Storage/SimpleStorageService.puml
allow_mixing

actor "User" as user
ElasticLoadBalancing(alb, "ALB", "Load Balancer")
ElasticContainerService(ecs, "ECS Fargate", "App")
RDSPostgreSQLinstance(rds, "Aurora", "PostgreSQL")
SimpleStorageService(s3, "S3", "Assets")

user --> alb : HTTPS
alb --> ecs
ecs --> rds
ecs --> s3
@enduml`,
  },
  {
    prompt: "AWS event-driven order processing — SNS fan-out to SQS, Lambda consumer, DynamoDB storage",
    puml: `@startuml
!define AWSPuml https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist
!include AWSPuml/AWSCommon.puml
!include AWSPuml/ApplicationIntegration/SimpleNotificationService.puml
!include AWSPuml/ApplicationIntegration/SimpleQueueService.puml
!include AWSPuml/Compute/Lambda.puml
!include AWSPuml/Database/DynamoDB.puml
allow_mixing

actor "Producer" as prod
SimpleNotificationService(sns, "SNS", "Event Bus")
SimpleQueueService(sqs1, "Orders Queue", "SQS")
SimpleQueueService(sqs2, "Notify Queue", "SQS")
Lambda(fn1, "Order Processor", "Lambda")
Lambda(fn2, "Notifier", "Lambda")
DynamoDB(db, "Orders", "DynamoDB")

prod --> sns : Publish
sns --> sqs1
sns --> sqs2
sqs1 --> fn1 : Trigger
sqs2 --> fn2 : Trigger
fn1 --> db : Write
@enduml`,
  },
  {
    prompt: "AWS data lake — Kinesis ingestion, S3 raw and curated buckets, Glue ETL, Athena queries",
    puml: `@startuml
!define AWSPuml https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist
!include AWSPuml/AWSCommon.puml
!include AWSPuml/Analytics/KinesisDataStreams.puml
!include AWSPuml/Storage/SimpleStorageService.puml
!include AWSPuml/Analytics/Glue.puml
!include AWSPuml/Analytics/Athena.puml
allow_mixing

actor "App" as app
KinesisDataStreams(ks, "Kinesis", "Data Streams")
SimpleStorageService(s3raw, "S3 Raw", "Landing Zone")
Glue(glue, "AWS Glue", "ETL")
SimpleStorageService(s3cur, "S3 Curated", "Clean Data")
Athena(athena, "Athena", "SQL Queries")

app --> ks : Events
ks --> s3raw : Land
s3raw --> glue : Transform
glue --> s3cur
s3cur --> athena : Query
@enduml`,
  },
];

function initGallery() {
  const grid = document.getElementById('gallery-grid');
  if (!grid) return;

  GALLERY_ITEMS.forEach((item) => {
    const card = buildCard(item);
    grid.appendChild(card);
  });

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        renderCard(entry.target);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.05 });

  grid.querySelectorAll('.gallery-card').forEach((card) => observer.observe(card));
}

function buildCard(item) {
  const card = document.createElement('div');
  card.className = 'gallery-card border border-gray-200 dark:border-gray-800 rounded-2xl overflow-hidden bg-white/5 dark:bg-white/[0.02]';
  card.dataset.puml = item.puml;

  card.innerHTML = `
    <div class="gallery-img-wrapper relative bg-gray-100 dark:bg-gray-900" style="min-height:220px;">
      <div class="gallery-skeleton absolute inset-0 flex items-center justify-center">
        <div class="flex flex-col items-center gap-3">
          <div class="w-6 h-6 border-2 border-brand-400 border-t-transparent rounded-full animate-spin"></div>
          <span class="text-xs text-gray-400 dark:text-gray-600">Rendering…</span>
        </div>
      </div>
      <img class="gallery-img hidden w-full h-auto object-contain p-4" alt="${escapeHtml(item.prompt)}">
    </div>
    <div class="px-5 py-4 border-t border-gray-200 dark:border-gray-800">
      <p class="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
        <span class="font-mono text-brand-400 mr-1.5">&gt;</span>${escapeHtml(item.prompt)}
      </p>
      <a href="#generator"
         class="mt-3 inline-block text-xs font-medium text-brand-400 hover:text-brand-300 transition-colors"
         onclick="document.getElementById('prompt-input').value = ${JSON.stringify(item.prompt)}; document.getElementById('prompt-input').focus();">
        Try this prompt →
      </a>
    </div>
  `;
  return card;
}

async function renderCard(card) {
  const puml = card.dataset.puml;
  const img = card.querySelector('.gallery-img');
  const skeleton = card.querySelector('.gallery-skeleton');

  try {
    const result = await apiRender(puml, 'svg');
    img.src = result.image;
    img.classList.remove('hidden');
    skeleton.classList.add('hidden');
  } catch {
    skeleton.innerHTML = '<span class="text-xs text-gray-500 px-4 text-center">Preview unavailable</span>';
  }
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

document.addEventListener('DOMContentLoaded', initGallery);
