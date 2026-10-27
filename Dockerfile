FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/kerneldottoday/tiroir" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    TIROIR_DATA_DIR=/data TIROIR_HOST=0.0.0.0 TIROIR_PORT=5950
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --uid 10001 --no-create-home tiroir \
    && mkdir -p /data /agents && chown tiroir /data /agents
USER tiroir
VOLUME ["/data"]
EXPOSE 5950
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5950/', timeout=2)"
ENTRYPOINT ["tiroir"]
CMD ["serve"]
