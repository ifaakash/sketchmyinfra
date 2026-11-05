# PlantUML server with cloud icon libraries baked in.
#
# The JVM inside the container cannot reliably reach raw.githubusercontent.com
# (connect timeouts -> "Cannot open URL"), and a render path that depends on
# GitHub at request time is fragile anyway. Libraries are fetched once at build
# time; the backend rewrites the GitHub include URLs to these local paths.

FROM alpine:3.20 AS libs

ARG AWS_ICONS_REF=v20.0
ARG AZURE_ICONS_REF=f360835f8794e18bed6520bb2eea56b482816d95
ARG GCP_ICONS_REF=fbd746f0d5c6382432adb7c1984fbb67eddb279f

RUN apk add --no-cache curl tar

# Only .puml files are read by PlantUML; png/svg previews are dropped
RUN set -euxo pipefail; \
    mkdir -p /opt/plantuml-libs; \
    fetch() { \
      tmp="$(mktemp -d)"; \
      curl -fsSL "https://codeload.github.com/$2/tar.gz/$3" | tar -xz -C "$tmp"; \
      mv "$tmp"/*/dist "/opt/plantuml-libs/$1"; \
      rm -rf "$tmp"; \
    }; \
    fetch aws   awslabs/aws-icons-for-plantuml "refs/tags/${AWS_ICONS_REF}"; \
    fetch azure plantuml-stdlib/Azure-PlantUML "${AZURE_ICONS_REF}"; \
    fetch gcp   Crashedmind/PlantUML-icons-GCP "${GCP_ICONS_REF}"; \
    find /opt/plantuml-libs -type f ! -name '*.puml' -delete; \
    test -f /opt/plantuml-libs/aws/AWSCommon.puml; \
    test -f /opt/plantuml-libs/azure/AzureCommon.puml; \
    test -f /opt/plantuml-libs/gcp/GCPCommon.puml

# Pinned: the floating :jetty tag changes underneath us
FROM plantuml/plantuml-server:jetty-v1.2026.2

COPY --from=libs /opt/plantuml-libs /opt/plantuml-libs

# ALLOWLIST: local reads only under /opt/plantuml-libs, no outbound URL fetches.
# /api/render accepts user-edited PUML, so UNSECURE would allow reading any
# file in the container and SSRF into the internal network.
ENV JAVA_TOOL_OPTIONS="-DPLANTUML_SECURITY_PROFILE=ALLOWLIST -Dplantuml.allowlist.path=/opt/plantuml-libs"
