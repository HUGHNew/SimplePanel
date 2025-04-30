# /// script
# requires-python = ">=3.10"
# dependencies = [fastapi, jinja2, uvicorn]
# ///
import json
from datetime import datetime
from typing import Any
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

app = FastAPI(title="Server Status Monitor")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

templates_dir = Path("template")
templates = Jinja2Templates(directory=str(templates_dir))


def get_avg_disk_usage(data):
    if "disk" not in data or "disks" not in data["disk"] or not data["disk"]["disks"]:
        return 0

    total = sum(disk["used_percent"] for disk in data["disk"]["disks"])
    return round(total / len(data["disk"]["disks"]), 2)


templates.env.filters["get_avg_disk_usage"] = get_avg_disk_usage


def determine_status(data: dict[str, Any]) -> str:
    try:
        cpu_usage = data.get("cpu", {}).get("usage", 0)
        memory_usage = data.get("memory", {}).get("used_percent", 0)

        max_disk_usage = 0
        if "disk" in data and "disks" in data["disk"]:
            disk_usages = [
                disk.get("used_percent", 0) for disk in data["disk"]["disks"]
            ]
            if disk_usages:
                max_disk_usage = max(disk_usages)

        max_gpu_usage = 0
        if data.get("gpu", {}).get("available", False):
            gpu_utilizations = [
                gpu.get("utilization", 0) for gpu in data.get("gpu", {}).get("gpus", [])
            ]
            if gpu_utilizations:
                max_gpu_usage = max(gpu_utilizations)

        if (
            cpu_usage > 90
            or memory_usage > 90
            or max_disk_usage > 90
            or max_gpu_usage > 90
        ):
            return "critical"
        elif (
            cpu_usage > 70
            or memory_usage > 70
            or max_disk_usage > 80
            or max_gpu_usage > 80
        ):
            return "warning"
        else:
            return "normal"
    except Exception as e:
        print(f"Error determining status: {e}")
        return "normal"


def save_server_data(hostname: str, data: dict[str, Any]):
    server_dir = DATA_DIR / hostname
    server_dir.mkdir(exist_ok=True)

    # data["status"] = determine_status(data)

    timestamp = datetime.fromisoformat(data["timestamp"])
    filename = timestamp.strftime("%Y%m%d%H.json")

    with open(server_dir / filename, "w") as f:
        json.dump(data, f, indent=2)

    with open(server_dir / "latest.json", "w") as f:
        json.dump(data, f, indent=2)


def get_all_servers() -> list[dict[str, Any]]:
    servers = []

    for hostname_dir in DATA_DIR.iterdir():
        if hostname_dir.is_dir():
            latest_file = hostname_dir / "latest.json"
            if latest_file.exists():
                try:
                    with open(latest_file, "r") as f:
                        data = json.load(f)
                        data["last_updated"] = datetime.fromisoformat(
                            data["timestamp"]
                        ).strftime("%Y-%m-%d %H:%M:%S")
                        servers.append(data)
                except Exception as e:
                    print(f"Error reading {latest_file}: {e}")

    return sorted(servers, key=lambda x: x["hostname"])


def get_server_history(hostname: str, limit: int = 20) -> list[dict[str, Any]]:
    server_dir = DATA_DIR / hostname
    if not server_dir.exists() or not server_dir.is_dir():
        return []

    history = []
    json_files = list(server_dir.glob("*.json"))
    json_files = [f for f in json_files if f.name != "latest.json"]

    json_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    json_files = json_files[:limit]

    for json_file in json_files:
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                data["timestamp"] = datetime.fromisoformat(data["timestamp"]).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                history.append(data)
        except Exception as e:
            print(f"Error reading {json_file}: {e}")

    return history


@app.post("/report")
async def report_status(request: Request):
    """main endpoint for clients"""
    try:
        data = await request.json()
        hostname = data.get("hostname")

        if not hostname:
            raise HTTPException(status_code=400, detail="Hostname is required")

        save_server_data(hostname, data)
        return {"status": "ok", "message": f"Data received for {hostname}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    servers = get_all_servers()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "servers": servers, "current_time": current_time},
    )


@app.get("/history", response_class=HTMLResponse)
async def server_list(request: Request):
    servers = get_all_servers()

    return templates.TemplateResponse(
        "history.html", {"request": request, "servers": servers}
    )


@app.get("/server/{hostname}", response_class=HTMLResponse)
async def server_detail(request: Request, hostname: str):
    history = get_server_history(hostname)

    if not history:
        raise HTTPException(
            status_code=404, detail=f"No data found for server {hostname}"
        )

    has_gpu = False
    for entry in history:
        if entry.get("gpu", {}).get("available", False):
            has_gpu = True
            break

    latest = history[0] if history else None

    return templates.TemplateResponse(
        "server_detail.html",
        {
            "request": request,
            "hostname": hostname,
            "history": history,
            "has_gpu": has_gpu,
            "latest": latest,
            "get_avg_disk_usage": get_avg_disk_usage,
        },
    )


if __name__ == "__main__":
    print("Server status monitor starting...")
    print(f"Data directory: {DATA_DIR.absolute()}")
    print(f"Templates directory: {templates_dir.absolute()}")
