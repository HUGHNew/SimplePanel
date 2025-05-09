# /// script
# requires-python = ">=3.10"
# dependencies = [rich]
# ///

# -*- coding: utf-8 -*-

import argparse
import json
import os
from datetime import datetime, timedelta
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.text import Text

DANGER_LIMIT = 90
WARN_LIMIT = 70

def create_default_table() -> Table:
    return Table(show_header=True, expand=True)

def create_progress_bar(percentage: float, text_color=False, width=25):
    filled = int(width * percentage / 100)
    if percentage < WARN_LIMIT:
        color = "green"
    elif percentage < DANGER_LIMIT:
        color = "yellow"
    else:
        color = "red"

    bar = Text()
    bar.append("*" * filled, style=color)
    bar.append("." * (width - filled), style="dim")

    if text_color:
        bar.append(f" {percentage:.2f}%", style=color)
    else:
        bar.append(f" {percentage:.2f}%")

    return bar


def create_system_section(data: dict):
    update_time = datetime.fromisoformat(data["timestamp"])
    current_time = datetime.now()
    offline = current_time - update_time > timedelta(days=1)

    header_text = Text(justify="center")
    header_text.append(f"{data['os']}", style="yellow")
    header_text.append(" | ", style="dim")
    if offline:
        header_text.append("offline", style="red")
        header_text.append(" | ", style="dim")
        header_text.append(f"最近上线: {data['timestamp']}", style="dim")
    else:
        header_text.append("online", style="bold green")
        header_text.append(" | ", style="dim")
        header_text.append(f"运行时间: {data['uptime_days']:.2f} 天", style="blue")

    return header_text


def create_cpu_section(cpu_data: dict):
    cpu_table = create_default_table()
    cpu_table.add_column("CPU", style="cyan")
    cpu_table.add_column("核心数", style="green")
    cpu_table.add_column("使用率", style="magenta")

    cpu_usage = cpu_data["usage"]
    progress_bar = create_progress_bar(cpu_usage)

    cpu_table.add_row(cpu_data["model"], str(cpu_data["cores"]), progress_bar)

    return cpu_table


def create_memory_section(mem_data: dict):
    memory_table = create_default_table()
    memory_table.add_column("内存", style="cyan")
    memory_table.add_column("可用", style="green")
    memory_table.add_column("占用", style="green")
    memory_table.add_column("使用率", style="magenta")

    memory_usage = mem_data["used_percent"]
    memory_progress_bar = create_progress_bar(memory_usage)

    swap_usage = mem_data["swap"]["used_percent"]
    swap_progress_bar = create_progress_bar(swap_usage)

    memory_table.add_row(
        "Memory",
        f"{mem_data['available_mb'] / 1024:.2f} GB",
        f"{mem_data['used_mb'] / 1024:.2f} / {mem_data['total_mb'] / 1024:.2f} GB",
        memory_progress_bar,
    )

    memory_table.add_row(
        "Swap",
        f"{mem_data['swap']['total_mb'] / 1024 - mem_data['swap']['used_mb'] / 1024:.2f} GB",
        f"{mem_data['swap']['used_mb'] / 1024:.2f} / {mem_data['swap']['total_mb'] / 1024:.2f} GB",
        swap_progress_bar,
    )

    return memory_table


def create_gpu_section(gpu_data: dict):
    if not gpu_data["available"] or gpu_data["count"] == 0:
        return ""

    gpu_table = create_default_table()
    gpu_table.add_column("PCI_ID", style="cyan", justify="center")
    gpu_table.add_column("型号", style="green")
    gpu_table.add_column("VRAM", style="green")
    gpu_table.add_column("VRAM使用率", style="magenta")
    gpu_table.add_column("GPU利用率", style="magenta")

    for gpu in gpu_data["gpus"]:
        memory_usage = gpu["memory_used_percent"]
        memory_progress_bar = create_progress_bar(memory_usage)

        gpu_util = gpu["utilization"]
        util_progress_bar = create_progress_bar(gpu_util)

        gpu_table.add_row(
            f"{gpu['index']}",
            f"{gpu['name']}",
            f"{gpu['memory_used_mb'] / 1024:.2f} / {gpu['memory_total_mb'] / 1024:.2f} GB",
            memory_progress_bar,
            util_progress_bar,
        )

    return gpu_table


def create_disk_section(disk_data: dict):
    disk_table = create_default_table()
    disk_table.add_column("设备", style="cyan")
    disk_table.add_column("挂载点", style="green")
    disk_table.add_column("文件系统", style="blue")
    disk_table.add_column("可用", style="green")
    disk_table.add_column("占用", style="green")
    disk_table.add_column("使用率", style="magenta")

    for disk in disk_data["disks"]:
        disk_usage = disk["used_percent"]
        progress_bar = create_progress_bar(disk_usage, True)

        disk_table.add_row(
            f"{disk['device']}",
            f"{disk['mount_point']}",
            f"{disk['fs_type']}",
            f"{disk['free_gb']:.2f} GB",
            f"{disk['used_gb']:.2f} / {disk['total_gb']:.2f} GB",
            progress_bar,
        )


    return disk_table


def load_data(data_root):
    json_file_path = os.path.join(data_root, "latest.json")

    with open(json_file_path, "r") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    return data


def create_server_block(data_dir: str) -> tuple[Panel, dict[str, list[dict]]]:
    data = load_data(data_dir)
    table_extra_size = 3

    items = [
        Layout(create_system_section(data), name="header", size=1),
        Layout(create_cpu_section(data["cpu"]), name="cpu", size=2 + table_extra_size), # cpu + header
        Layout(create_memory_section(data["memory"]), name="memory", size=3 + table_extra_size), # memory + swap + header
        Layout(
            create_disk_section(data["disk"]),
            name="disk",
            size=len(data["disk"]["disks"]) + 1 + table_extra_size,
        ),
        Layout(
            create_gpu_section(data["gpu"]),
            name="gpu",
            size=data["gpu"]["count"] + 1 + table_extra_size,
        ),
    ]
    total_size = sum([item.size for item in items])
    layout = Layout(size=total_size)
    layout.split_column(*items)

    danger_disks = [
        disk for disk in data["disk"]["disks"] if disk["used_percent"] > DANGER_LIMIT
    ]
    return Panel(layout, title=data["hostname"], height=total_size + 2), {data["hostname"]: danger_disks}

def create_danger_block(disk_info: dict[str, list[dict]]) -> Panel:
    disk_table = create_default_table()
    disk_table.add_column("主机", style="cyan")
    disk_table.add_column("设备", style="green")
    disk_table.add_column("挂载点", style="green")
    disk_table.add_column("可用", style="yellow")
    disk_table.add_column("使用率", style="magenta")

    for host, disks in disk_info.items():
        for disk in disks:
            disk_table.add_row(
                f"{host}",
                f"{disk['device']}",
                f"{disk['mount_point']}",
                f"{disk['free_gb']:.2f} GB",
                create_progress_bar(disk["used_percent"], True),
            )
    return Panel(disk_table, title="Disks in danger")

def display_latest(data_root: str):
    console = Console()
    danger_disks = {}
    for host in os.listdir(data_root):
        block, disks = create_server_block(os.path.join(data_root, host))
        console.print(block)
        danger_disks.update(disks)
        console.print("\n")
    console.print(create_danger_block(danger_disks))


def get_args():
    parser = argparse.ArgumentParser(description="watcher")

    parser.add_argument(
        "-d",
        "--data",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "data"),
        help="The root directory of the data",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()
    display_latest(args.data)
