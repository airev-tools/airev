FROM python:3.12-slim

LABEL maintainer="airev-tools"
LABEL org.opencontainers.image.source="https://github.com/airev-tools/airev"

# Install airev and verify
COPY . /build
RUN pip install --no-cache-dir /build && \
    python -c "import airev_core; import interfaces" && \
    # Copy entrypoint to a fixed location, then remove build dir
    cp /build/interfaces/github_action/entrypoint.py /usr/local/bin/entrypoint.py && \
    rm -rf /build

# Create non-root user
RUN useradd --create-home --shell /bin/bash scanner
USER scanner

ENTRYPOINT ["python", "/usr/local/bin/entrypoint.py"]
