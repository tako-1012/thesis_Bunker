"""Serve local assets and offload planning with a non-queueing single-plan guard."""

import argparse
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from tapp.config import RESOLUTION
from tapp.mission import list_maps, load_map, plan_mission, render_map_png

STATIC = Path(__file__).resolve().parent / "static"
app = FastAPI(title="砂浜の巡回計画")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
_PLANNING = threading.Lock()


class PlanRequest(BaseModel):
    map_id: str
    start: tuple[float, float]
    points: list[tuple[float, float]] = Field(min_length=1, max_length=12)
    method: str = "terrain"


def _map(map_id):
    try:
        return load_map(map_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/maps")
def maps():
    return list_maps()


# Register the image before the path catch-all: IDs contain slashes.
@app.get("/api/maps/{map_id:path}/image.png")
def image(map_id: str):
    return Response(render_map_png(_map(map_id)), media_type="image/png")


@app.get("/api/maps/{map_id:path}")
def map_info(map_id: str):
    sc = _map(map_id)
    return dict(
        id=map_id,
        side_m=sc["side_m"],
        resolution=RESOLUTION,
        shape=list(sc["tmap"].shape),
        start=[float(v) * RESOLUTION for v in sc["start"]],
        bounds=[
            [-RESOLUTION / 2, -RESOLUTION / 2],
            [
                (sc["tmap"].shape[1] - 0.5) * RESOLUTION,
                (sc["tmap"].shape[0] - 0.5) * RESOLUTION,
            ],
        ],
    )


@app.post("/api/plan")
async def plan(request: PlanRequest):
    if not _PLANNING.acquire(blocking=False):
        raise HTTPException(
            409, "別の経路を計算中です。完了後にもう一度実行してください"
        )

    def compute():
        # Release in the worker, even when the client disconnects/cancels its wait.
        try:
            sc = _map(request.map_id)
            return plan_mission(sc, request.start, request.points, request.method)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            _PLANNING.release()

    return await run_in_threadpool(compute)


def main():
    parser = argparse.ArgumentParser(description="砂浜の巡回計画 Web 画面")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
