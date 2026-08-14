# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# psycopg[binary]는 wheel로 오지만, 일부 의존성(빌드 툴체인)이 필요할 수 있어
# 최소한의 빌드 도구만 설치한다. curl은 헬스체크용.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 레이어를 코드보다 먼저 캐시 — requirements.txt가 안 바뀌면
# pip install을 다시 안 하도록.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 컨테이너 안에서는 non-root로 실행
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# --reload는 로컬 개발용 docker-compose에서 command로 덮어씀.
# 여기 기본값은 운영에 가까운 형태(워커 여러 개는 추후 --workers로 조정).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
