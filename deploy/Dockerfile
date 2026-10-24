FROM python:3.12-slim

WORKDIR /app

# آینه داخلی برای سرعت و پایداری شبکه سرور
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple/
ARG PIP_TRUSTED=pypi.tuna.tsinghua.edu.cn

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 \
      -i ${PIP_INDEX} --trusted-host ${PIP_TRUSTED} \
      -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY dashboard ./dashboard

EXPOSE 8000 8001
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
