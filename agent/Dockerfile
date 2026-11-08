FROM python:3.12-slim

# git for clone/commit/push; gh only for `pr list` / `pr create`
ARG GH_VERSION=2.103.0
ARG TARGETARCH
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates curl && \
    ARCH="${TARGETARCH:-$(dpkg --print-architecture)}" && \
    TARBALL="gh_${GH_VERSION}_linux_${ARCH}.tar.gz" && \
    cd /tmp && \
    curl -fsSLO "https://github.com/cli/cli/releases/download/v${GH_VERSION}/${TARBALL}" && \
    curl -fsSLO "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_checksums.txt" && \
    grep " ${TARBALL}\$" "gh_${GH_VERSION}_checksums.txt" | sha256sum -c - && \
    tar -xzf "${TARBALL}" && \
    install -m 0755 "gh_${GH_VERSION}_linux_${ARCH}/bin/gh" /usr/local/bin/gh && \
    rm -rf /tmp/gh_* && \
    apt-get purge -y curl && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /agent

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# uid 1000 matches the Job's runAsUser. Root FS is read-only in the pod:
# HOME=/work (emptyDir) for git/gh config, no .pyc writes, no pip cache.
RUN useradd --uid 1000 --no-create-home agent
USER 1000
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GH_PROMPT_DISABLED=1 \
    GH_NO_UPDATE_NOTIFIER=1

CMD ["python", "-m", "app.main"]
