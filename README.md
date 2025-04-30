# 服务器状态记录系统

这是一个C/S架构的服务器状态监控系统，用于收集和展示多台Linux服务器的系统状态信息。

## 功能特点

- 客户端定时采集并发送系统状态信息（CPU、GPU、内存、磁盘）
- 服务器端接收数据并以JSON格式存储
- 提供Web界面展示服务器状态：
  - 所有服务器的最新状态概览
  - 各服务器的历史状态记录
- 使用颜色编码（绿色、黄色、红色）标记服务器状态级别

## 系统架构

### 客户端 (Client)
- 使用纯Python标准库实现，无第三方依赖
- 通过HTTP协议发送数据到服务器
- 采集以下系统信息：
  - CPU使用率
  - GPU使用率（如果有NVIDIA GPU）
  - 内存使用情况
  - 磁盘使用情况

### 服务器端 (Server)
- 使用FastAPI框架构建
- 使用Jinja2模板引擎生成HTML页面
- 数据以JSON格式存储在`data/<hostname>/<datetime>.json`

## 安装与使用

### 服务器端安装

1. 克隆或下载代码
2. 安装依赖：
```bash
pip install fastapi uvicorn jinja2
```

3. 启动服务器：
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 客户端安装

1. 复制`client.py`到需要监控的服务器
2. 启动客户端：
```bash
python client.py "your_server_url"
```

## Web界面

服务器端提供以下页面：

- `/` - 主页，显示所有服务器的最新状态概览
- `/history` - 显示所有被监控服务器的列表
- `/server/{hostname}` - 显示特定服务器的历史状态记录

## 目录结构

```
.
├── client.py          # 客户端脚本
├── server.py          # 服务器端脚本
├── data/              # 数据存储目录
│   └── hostname/      # 按主机名分类的数据
│       ├── latest.json           # 最新状态数据
│       └── yyyy-mm-dd_HH-MM-SS.json  # 历史数据
└── templates/         # HTML模板
    ├── base.html
    ├── index.html
    ├── history.html
    └── server_detail.html
```

## 自定义和扩展

### 添加新的监控指标

要在客户端添加新的指标：
1. 在`SystemStatsCollector`类中添加新的采集方法
2. 在`collect_stats`方法中包含新指标
3. 更新服务器端模板以显示新指标
