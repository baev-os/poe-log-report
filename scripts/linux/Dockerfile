# CPython source checksum is published in the official Python 3.14.4 image.
FROM ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends ca-certificates \
    && printf 'APT::Snapshot "20261029T000000Z";\n' > /etc/apt/apt.conf.d/50snapshot \
    && apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends \
       build-essential ca-certificates curl git libbz2-dev libffi-dev liblzma-dev \
       libreadline-dev libsqlite3-dev libssl-dev tk-dev uuid-dev zlib1g-dev \
       libzstd-dev xvfb xauth scrot \
    && rm -rf /var/lib/apt/lists/*

ARG PYTHON_VERSION=3.14.4
ARG PYTHON_SHA256=d923c51303e38e249136fc1bdf3568d56ecb03214efdef48516176d3d7faaef8
RUN curl --fail --location --retry 3 "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz" -o /tmp/python.tar.xz \
    && printf '%s  /tmp/python.tar.xz\n' "$PYTHON_SHA256" | sha256sum --check - \
    && mkdir /tmp/python \
    && tar -xJf /tmp/python.tar.xz --strip-components=1 -C /tmp/python \
    && cd /tmp/python \
    && ./configure --prefix=/opt/python --enable-shared --with-ensurepip=install LDFLAGS='-Wl,-rpath=/opt/python/lib' \
    && make -j2 \
    && make install \
    && cp LICENSE /opt/python/LICENSE.txt \
    && /opt/python/bin/python3.14 -m venv /opt/venv \
    && rm -rf /tmp/python /tmp/python.tar.xz

COPY requirements-rendering.txt requirements-desktop.txt requirements-build.txt requirements-dev.txt /opt/requirements/
RUN /opt/venv/bin/python -m pip install --no-cache-dir \
    -r /opt/requirements/requirements-build.txt -r /opt/requirements/requirements-dev.txt

ENV PATH="/opt/venv/bin:/opt/python/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8
WORKDIR /workspace
