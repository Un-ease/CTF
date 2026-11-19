FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE=/app/instance/common.sqlite3
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0 \
    && useradd --uid 10001 --create-home common \
    && mkdir -p /app/instance && chown common:common /app/instance
COPY app.py db.py lab.py ./
COPY templates ./templates
COPY static ./static
USER common
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "app:create_app()"]
