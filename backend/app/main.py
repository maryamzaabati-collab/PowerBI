"""API locale. Avec PORT (Replit), elle sert aussi le frontend construit."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import routeur
from backend.app.errors import ErreurMetier
from backend.app.limits import HOTE_LOCAL, PORT_LOCAL
from backend.app.sessions import annuaire

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("pbi-pack")


@asynccontextmanager
async def duree(_app: FastAPI):
    annuaire.reinitialiser()
    annuaire.demarrer_balayage()
    logger.info("api prête")
    yield


def creer_application() -> FastAPI:
    application = FastAPI(title="Pack Power BI", lifespan=duree)
    application.include_router(routeur)

    @application.exception_handler(ErreurMetier)
    async def rendre_erreur(_request, exc: ErreurMetier):
        logger.info("erreur code=%s", exc.code)
        return JSONResponse(status_code=400, content={"code": exc.code, "message": exc.message})

    if os.environ.get("PORT"):
        dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
        if dist.is_dir():
            application.mount("/", StaticFiles(directory=dist, html=True), name="interface")
    else:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=["http://127.0.0.1:8742", "http://localhost:8742"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    return application


app = creer_application()


if __name__ == "__main__":
    import uvicorn

    port = os.environ.get("PORT")
    if port:
        uvicorn.run("backend.app.main:app", host="0.0.0.0", port=int(port))
    else:
        uvicorn.run("backend.app.main:app", host=HOTE_LOCAL, port=PORT_LOCAL)
