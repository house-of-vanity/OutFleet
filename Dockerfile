# Use standard Rust image and install cargo-chef
FROM rust:1.82-bookworm AS chef
WORKDIR /app

# Install cargo-chef
RUN cargo install cargo-chef --version 0.1.67

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

# Recipe preparation stage
FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

# Dependency building stage  
FROM chef AS builder

# Build arguments
ARG GIT_COMMIT="development"
ARG GIT_COMMIT_SHORT="dev"
ARG BUILD_DATE="unknown"
ARG BRANCH_NAME="unknown"
ARG CARGO_VERSION="0.1.0"

# Environment variables from build args
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_COMMIT_SHORT=${GIT_COMMIT_SHORT}
ENV BUILD_DATE=${BUILD_DATE}
ENV BRANCH_NAME=${BRANCH_NAME}
ENV CARGO_VERSION=${CARGO_VERSION}

# Copy recipe and build dependencies (cached layer)
COPY --from=planner /app/recipe.json recipe.json
RUN cargo chef cook --release --recipe-path recipe.json

# Copy source and build application
COPY . .
RUN cargo build --release --locked

# Runtime stage - minimal Ubuntu image for glibc compatibility
FROM ubuntu:24.04 AS runtime

# Build arguments (needed for runtime stage)
ARG GIT_COMMIT="development"
ARG GIT_COMMIT_SHORT="dev"
ARG BUILD_DATE="unknown"
ARG BRANCH_NAME="unknown"
ARG CARGO_VERSION="0.1.0"

# Environment variables from build args
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_COMMIT_SHORT=${GIT_COMMIT_SHORT}
ENV BUILD_DATE=${BUILD_DATE}
ENV BRANCH_NAME=${BRANCH_NAME}
ENV CARGO_VERSION=${CARGO_VERSION}

WORKDIR /app

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    libprotobuf32 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy the binary from builder
COPY --from=builder /app/target/release/xray-admin /app/xray-admin

# Copy static files
COPY --from=builder /app/static ./static

# Copy config file
COPY config.docker.toml ./config.toml

# Create non-root user for security
RUN groupadd -r outfleet && useradd -r -g outfleet -s /bin/false outfleet
RUN chown -R outfleet:outfleet /app
USER outfleet

EXPOSE 8081

CMD ["/app/xray-admin", "--host", "0.0.0.0"]