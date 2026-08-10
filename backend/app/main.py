import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings

# 앱 로거에 핸들러를 붙인다. 이걸 안 하면 루트에 핸들러가 없어서
# logger.info() 가 조용히 버려진다(uvicorn 은 자기 로거만 설정한다).
# 자동 응대 게이트가 무엇을 막았는지는 임계값 조정의 유일한 근거이므로
# 반드시 남아야 한다(services/ai/gate.py).
logging.basicConfig(
    level=logging.DEBUG if settings.env == "development" else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)

app = FastAPI(
    title="소통해요 API",
    description="교사 민원 보조 AI 시스템 백엔드",
    version="0.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "env": settings.env}
