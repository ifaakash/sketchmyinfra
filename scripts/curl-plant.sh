BASE="https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist"
paths=(
    "Analytics/Glue.puml"
    "Analytics/Redshift.puml"
    "Analytics/QuickSight.puml"
    "Analytics/Athena.puml"
    "Analytics/KinesisDataStreams.puml"
    "Analytics/KinesisDataFirehose.puml"
    "Analytics/EMR.puml"
    "ApplicationIntegration/StepFunctions.puml"
    "ManagementGovernance/CloudWatchEvents.puml"
    "ManagementGovernance/CloudWatchEventsBus.puml"
    "BusinessApplications/QuickSight.puml"
)
for p in "${paths[@]}"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/$p")
    echo "$code  $p"
done
