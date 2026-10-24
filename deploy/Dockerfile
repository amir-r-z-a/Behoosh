FROM python:3.12-slim

WORKDIR /app

# پیش‌فرض PyPI رسمی. برای آینه داخلی سرور:
#   docker build --build-arg PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple/ \
#                --build-arg PIP_TRUSTED=pypi.tuna.tsinghua.edu.cn ...
ARG PIP_INDEX=https://pypi.org/simple/
ARG PIP_TRUSTED=pypi.org

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 \
      -i ${PIP_INDEX} --trusted-host ${PIP_TRUSTED} \
      -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY dashboard ./dashboard

EXPOSE 8000 8001
# مایگریشن‌ها قبل از بالا آمدن API اجرا می‌شوند (idempotent و با قفل).
CMD ["sh", "-c", "python -m app.db.migrate && exec uvicorn app.api.main:app --host 0.0.0.0 --port 8000"]
