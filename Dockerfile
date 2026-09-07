FROM python:2.7.18-stretch

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Debian stretch is EOL - use archive.debian.org
RUN echo 'deb http://archive.debian.org/debian stretch main' > /etc/apt/sources.list \
    && echo 'deb http://archive.debian.org/debian-security stretch/updates main' >> /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gcc \
        g++ \
        make \
        libldap2-dev \
        libsasl2-dev \
        libpq-dev \
        libcurl4-openssl-dev \
        libffi-dev \
        ca-certificates \
        gnupg \
    && curl -sL https://deb.nodesource.com/setup_16.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g coffee-script less@1.3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt 2>/dev/null || true

COPY requirements-plugins.txt ./
RUN pip install --no-cache-dir -r requirements-plugins.txt 2>/dev/null || true

# Copy full source tree
COPY . /code/

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]