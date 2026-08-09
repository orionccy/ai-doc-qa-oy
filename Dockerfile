# ============ Dockerfile:把应用打包成镜像 ============
# 镜像 = 一个"带环境的完整可执行包",到哪都能跑

# 1) FROM:基础镜像(带 Python 3.11 的轻量 Linux)
FROM python:3.11-slim

# 2) WORKDIR:容器内的工作目录(后面所有命令都在这里执行)
WORKDIR /app

# 3) 先 COPY 依赖清单并安装(利用 Docker 层缓存:依赖没变就不重装)
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4) 再把应用代码复制进镜像(代码放最后,改动时缓存复用率最高)
COPY app ./app

# 5) 声明容器对外端口(仅文档用途,实际映射由 compose/run 决定)
EXPOSE 8000

# 6) CMD:容器启动时执行的命令(uvicorn 启动服务,监听所有网卡)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
