BASE="https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist"
      paths=(
        "Groups/AWSCloud.puml"
        "Groups/Region.puml"
        "Groups/VPC.puml"
        "Groups/PublicSubnet.puml"
        "Groups/PrivateSubnet.puml"
        "NetworkingContentDelivery/VPCInternetGateway.puml"
        "NetworkingContentDelivery/VPCNATGateway.puml"
        "NetworkingContentDelivery/ElasticLoadBalancingApplicationLoadBalancer.puml"
        "Containers/ElasticContainerService.puml"
        "Database/AuroraPostgreSQLInstance.puml"
        "Database/ElastiCacheRedis.puml"
        "ManagementGovernance/CloudWatch.puml"
        "NetworkingContentDelivery/CloudFront.puml"
        "SecurityIdentityCompliance/Cognito.puml"
        "NetworkingContentDelivery/APIGateway.puml"
        "Compute/Lambda.puml"
        "Database/DynamoDB.puml"
        "Storage/SimpleStorageService.puml"
      )
      for p in "${paths[@]}"; do
        code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/$p")
        echo "$code  $p"
      done)
