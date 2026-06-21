# PaddleOCR sidecar for the Sunday Catechism "Import from Photo" (OCR) feature.
#
# paddlepaddle has no wheels for very new Python versions (e.g. 3.14), so it
# cannot live in the Frappe bench env. This image runs the OFFICIAL PaddleX
# serving for the OCR pipeline on Python 3.12; the Frappe app reaches it over
# HTTP (POST /ocr). See https://paddlepaddle.github.io/PaddleX/ -> Serving.
FROM python:3.12-slim

# PaddleOCR/PaddleX pull in OpenCV, which needs these shared libraries at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080
# Official PaddleX OCR serving. Binds 0.0.0.0:8080 by default; models download on
# first request (cached in the mounted /root/.paddlex volume).
CMD ["paddlex", "--serve", "--pipeline", "OCR", "--port", "8080"]
