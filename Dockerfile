# Build stage
FROM rust:latest as builder

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
