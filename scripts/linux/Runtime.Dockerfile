# A clean target: no Python, compiler, or project development environment.
FROM ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends ca-certificates \
    && printf 'APT::Snapshot "20261029T000000Z";\n' > /etc/apt/apt.conf.d/50snapshot \
    && apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends xvfb xauth fontconfig fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /release
