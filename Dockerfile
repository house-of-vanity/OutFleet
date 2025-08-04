FROM python:3-alpine

# Build arguments
ARG GIT_COMMIT="development"
ARG GIT_COMMIT_SHORT="dev"
ARG BUILD_DATE="unknown"
ARG BRANCH_NAME="unknown"

# Environment variables from build args
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_COMMIT_SHORT=${GIT_COMMIT_SHORT}
ENV BUILD_DATE=${BUILD_DATE}
ENV BRANCH_NAME=${BRANCH_NAME}

WORKDIR /app

# Install system dependencies first (this layer will be cached)
RUN apk update && apk add git curl unzip

# Copy and install Python dependencies (this layer will be cached when requirements.txt doesn't change)
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Xray-core
RUN XRAY_VERSION=$(curl -s https://api.github.com/repos/XTLS/Xray-core/releases/latest | sed -n 's/.*"tag_name": "\([^"]*\)".*/\1/p') && \
    curl -L -o /tmp/xray.zip "https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-64.zip" && \
    cd /tmp && unzip xray.zip && \
    ls -la /tmp/ && \
    find /tmp -name "xray" -type f && \
    cp xray /usr/local/bin/xray && \
    chmod +x /usr/local/bin/xray && \
    rm -rf /tmp/xray.zip /tmp/xray

# Copy the rest of the application code (this layer will change frequently)
COPY . .

# Run collectstatic
RUN python manage.py collectstatic --noinput

CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000" ]
