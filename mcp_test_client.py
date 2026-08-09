"""MCP Client 测试脚本:通过 stdio 连接 Server,调用工具并打印结果

演示:参数不是写死的——分别用默认值、中国时区、纽约时区调用同一个工具
运行: python mcp_test_client.py
"""
import asyncio

from fastmcp import Client


async def main():
    # 1) 通过 stdio 启动并连接 MCP Server
    #    注意:用项目 venv 的 python 启动 server(那里装了 fastmcp)
    from fastmcp.client.transports import PythonStdioTransport

    transport = PythonStdioTransport(
        script_path="/home/orionchen/projects/ai-doc-qa-py/mcp_time_server.py",
        python_cmd="/home/orionchen/projects/ai-doc-qa-py/.venv/bin/python",
    )
    async with Client(transport) as client:
        # 2) 查看 Server 暴露了哪些工具
        tools = await client.list_tools()
        print("🔧 可用工具:", [t.name for t in tools])

        # 3) 用默认参数调用(不传 timezone → 用函数默认值 Asia/Shanghai)
        r1 = await client.call_tool("get_current_time", {})
        print("🕐 默认(上海):", r1.data)

        # 4) 传不同参数调用(验证参数是活的,不是写死的)
        r2 = await client.call_tool("get_current_time", {"timezone_name": "America/New_York"})
        print("🗽 纽约:", r2.data)

        r3 = await client.call_tool("get_current_time", {"timezone_name": "Asia/Tokyo"})
        print("🗼 东京:", r3.data)


asyncio.run(main())
