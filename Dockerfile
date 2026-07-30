FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    libpq-dev \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    util-linux \
    fonts-dejavu \
    gettext \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd --gid 10001 mytools \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin mytools

COPY --chown=mytools:mytools . .

RUN mkdir -p /app/staticfiles /app/media \
    && chown -R mytools:mytools /app/staticfiles /app/media

USER mytools

EXPOSE 8000

CMD ["gunicorn", "MyTools.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
