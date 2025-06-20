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

COPY ./requirements.txt .
RUN apk update && apk add git && pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput

CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000" ]
