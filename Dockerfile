FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ghostscript nodejs npm && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt flask

COPY package.json .
RUN npm install --production

COPY altex/ altex/
COPY web/ web/
COPY scripts/ scripts/

ENV FLASK_APP=web.app
EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
