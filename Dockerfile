# FAF Map AI Development Environment
# Java 17 + Python 3.11 + Gradle 8.x + ML dependencies

FROM eclipse-temurin:17-jdk-jammy

# Gradle version
ARG GRADLE_VERSION=8.12

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.11 and build dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3-pip \
    curl \
    unzip \
    git \
    && rm -rf /var/lib/apt/lists/*

# Make python3.11 the default python/python3
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Upgrade pip and install Python ML dependencies
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir \
    numpy \
    torch --index-url https://download.pytorch.org/whl/cpu \
    pillow

# Install Gradle
RUN curl -fsSL "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" -o /tmp/gradle.zip && \
    unzip -q /tmp/gradle.zip -d /opt && \
    rm /tmp/gradle.zip && \
    ln -s "/opt/gradle-${GRADLE_VERSION}" /opt/gradle

# Set environment variables
ENV GRADLE_HOME=/opt/gradle
ENV PATH="${GRADLE_HOME}/bin:${PATH}"

# Set working directory
WORKDIR /workspace

# Default command
CMD ["bash"]
