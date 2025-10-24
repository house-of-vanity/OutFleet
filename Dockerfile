# Cargo dependencies stage
FROM rust:1.75-slim as deps

WORKDIR /app

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency specification files
COPY Cargo.toml Cargo.lock ./

# Create dummy source to build dependencies
RUN mkdir -p src && \
    echo "fn main() {}" > src/main.rs && \
    echo "pub fn lib() {}" > src/lib.rs

# Build dependencies - this layer will be cached unless Cargo.toml changes
RUN cargo build --release && \
    rm -rf src target/release/deps/xray_admin* target/release/xray-admin*

# Build stage
FROM deps as builder

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

# Copy actual source code
COPY src ./src
COPY static ./static

# Build the application (dependencies are already compiled)
RUN cargo build --release

# Runtime stage - minimal Debian image
FROM debian:bookworm-slim as runtime

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
