FROM python:3.12-slim

LABEL maintainer="airev-tools"
LABEL org.opencontainers.image.source="https://github.com/airev-tools/airev"

# Install airev, verify, and clean up build artifacts
COPY . /app
WORKDIR /app
RUN pip install --no-cache-dir . && \
    python -c "import airev_core; import interfaces" && \
    rm -rf /app/.git /app/tests /app/benchmarks /app/build

# Create non-root user
RUN useradd --create-home --shell /bin/bash scanner
USER scanner

ENTRYPOINT ["python", "/app/interfaces/github_action/entrypoint.py"]
