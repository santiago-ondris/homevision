FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000
WORKDIR /worker
COPY worker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home worker
COPY worker/app ./app
COPY worker/vision ./vision
USER worker
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host \"${HOST}\" --port \"${PORT}\""]
