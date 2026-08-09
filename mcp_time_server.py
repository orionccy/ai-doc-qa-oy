"""MCP Server 教学示例:提供一个"获取当前时间"的工具

三步:
1. 创建 FastMCP 实例(名字是 Server 标识)
2. @mcp.tool() 把函数暴露成工具(签名+文档字符串=给模型的说明书)
3. mcp.run() 启动(默认 stdio 传输,和 Dify/Hermes 等 Host 通过标准输入输出通信)

运行: python mcp_time_server.py
"""
from datetime import datetime, timezone

from fastmcp import FastMCP

mcp = FastMCP("time-server")


@mcp.tool()
def get_current_time(timezone_name: str = "Asia/Shanghai") -> str:
    """获取指定时区的当前时间(ISO 格式)。

    Args:
        timezone_name: IANA 时区名,如 Asia/Shanghai、America/New_York
    """
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(timezone_name)).isoformat()


if __name__ == "__main__":
    mcp.run()
