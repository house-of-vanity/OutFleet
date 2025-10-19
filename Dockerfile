# Build stage
FROM rust:latest as builder

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

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY Cargo.toml Cargo.lock ./

# Copy source code
COPY src ./src
COPY static ./static

# Build the application
RUN cargo build --release

# Runtime stage
FROM ubuntu:24.04

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

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Copy the binary from builder
COPY --from=builder /app/target/release/xray-admin /app/xray-admin

# Copy static files
COPY --from=builder /app/static ./static

# Copy config file
COPY config.docker.toml ./config.toml

EXPOSE 8081

CMD ["/app/xray-admin", "--host", "0.0.0.0"]
