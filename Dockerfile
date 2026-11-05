FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    THREAD_REQUIRE_AUTH=1
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    python -m pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 threadstudio
COPY --chown=10001:10001 app.py design_analysis.py web_access.py digitizer.py learned_regions.py index.html analysis-ui.js ./
COPY --chown=10001:10001 models/region-guide.json ./models/region-guide.json
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
