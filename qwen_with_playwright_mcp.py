import os
import json
import subprocess
import time
import re
import logging
import threading
import http.server
import socketserver
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from openai import OpenAI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PlaywrightMCPClient:
    """通义千问 + Playwright MCP 集成客户端（增强版）"""
    
    def __init__(self, max_iterations: int = 10, timeout: int = 30):
        """
        初始化客户端
        
        Args:
            max_iterations: 最大工具调用轮数，防止无限循环
            timeout: 每次 MCP 调用的超时时间（秒）
        """
        self.max_iterations = max_iterations
        self.timeout = timeout
        self.mcp_process = None
        self.request_id = 0
        
        # 本地服务器相关
        self.local_server = None
        self.local_server_thread = None
        self.local_server_port = None
        self.local_server_dir = None
        
        # 初始化 OpenAI 客户端
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("未设置 DASHSCOPE_API_KEY 环境变量")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        # 启动 Playwright MCP Server
        self._start_mcp_server()
        self.tools = self.get_playwright_tools()
    
    def _start_mcp_server(self):
        """启动 MCP Server 并等待其就绪"""
        try:
            logger.info("正在启动 Playwright MCP Server...")
            self.mcp_process = subprocess.Popen(
            ["npx", "@playwright/mcp@latest"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # 行缓冲
            )
            
            # 等待一下让 server 启动
            time.sleep(2)
            
            if self.mcp_process.poll() is not None:
                raise RuntimeError("MCP Server 启动失败")
            
            logger.info("✅ MCP Server 启动成功")
        except Exception as e:
            logger.error(f"❌ 启动 MCP Server 失败: {e}")
            raise
    
    def __enter__(self):
        """支持 context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """自动清理资源"""
        self.cleanup()
    
    def get_playwright_tools(self):
        """获取 Playwright MCP 提供的工具列表"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "browser_navigate",
                    "description": "导航到指定 URL",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "要访问的 URL"
                            }
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_snapshot",
                    "description": "获取当前页面的可访问性快照",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_click",
                    "description": "点击页面元素",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selector": {
                                "type": "string",
                                "description": "元素选择器"
                            }
                        },
                        "required": ["selector"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_fill",
                    "description": "填充输入框",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selector": {
                                "type": "string",
                                "description": "输入框选择器"
                            },
                            "value": {
                                "type": "string",
                                "description": "要填充的值"
                            }
                        },
                        "required": ["selector", "value"]
                    }
                }
            }
        ]
    
    def call_mcp_tool(self, tool_name: str, arguments: dict) -> Dict[str, Any]:
        """
        调用 MCP 工具（增强版：支持错误处理和超时）
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        self.request_id += 1
        
        try:
            # 构造 MCP 请求
            mcp_request = {
            "jsonrpc": "2.0",
                "id": self.request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
            }
            
            logger.info(f"🔧 调用工具: {tool_name}({arguments})")
        
            # 发送到 MCP Server
            request_str = json.dumps(mcp_request) + "\n"
            self.mcp_process.stdin.write(request_str)
            self.mcp_process.stdin.flush()
        
            # 读取响应（可能有多行，需要找到正确的 JSON）
            start_time = time.time()
            response_lines = []
            
            while time.time() - start_time < self.timeout:
                line = self.mcp_process.stdout.readline()
                if not line:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                # 尝试解析 JSON
                try:
                    response_data = json.loads(line)
                    
                    # 检查是否是我们的响应
                    if response_data.get("id") == self.request_id:
                        if "result" in response_data:
                            logger.info(f"✅ 工具调用成功")
                            return response_data["result"]
                        elif "error" in response_data:
                            error_msg = response_data["error"]
                            logger.error(f"❌ MCP 工具错误: {error_msg}")
                            return {"error": error_msg}
                except json.JSONDecodeError:
                    # 不是 JSON，继续读取下一行
                    response_lines.append(line)
                    continue
            
            # 超时
            logger.warning(f"⚠️ MCP 调用超时 ({self.timeout}秒)")
            return {"error": "timeout", "raw_output": "\n".join(response_lines)}
            
        except Exception as e:
            logger.error(f"❌ 调用 MCP 工具失败: {e}")
            return {"error": str(e)}
    
    def _start_local_server(self, directory: str, port: int = 0) -> Tuple[int, str]:
        """
        启动本地 HTTP 服务器
        
        Args:
            directory: 要服务的目录路径
            port: 端口号（0 表示自动选择）
            
        Returns:
            (实际端口号, 服务器 URL)
        """
        # 转换为绝对路径
        abs_dir = os.path.abspath(directory)
        
        if not os.path.exists(abs_dir):
            raise ValueError(f"目录不存在: {abs_dir}")
        
        # 创建服务器
        class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
            """静默的 HTTP 处理器（减少日志输出）"""
            def log_message(self, format, *args):
                pass  # 不输出请求日志
            
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=abs_dir, **kwargs)
        
        # 查找可用端口
        if port == 0:
            # 从 8000 开始尝试
            for try_port in range(8000, 9000):
                try:
                    self.local_server = socketserver.TCPServer(
                        ("127.0.0.1", try_port), 
                        QuietHTTPRequestHandler
                    )
                    port = try_port
                    break
                except OSError:
                    continue
            
            if not self.local_server:
                raise RuntimeError("无法找到可用端口（8000-8999）")
        else:
            self.local_server = socketserver.TCPServer(
                ("127.0.0.1", port), 
                QuietHTTPRequestHandler
            )
        
        self.local_server_port = port
        self.local_server_dir = abs_dir
        
        # 在后台线程启动服务器
        def serve():
            logger.info(f"🌐 本地服务器启动: http://127.0.0.1:{port}/ (目录: {abs_dir})")
            self.local_server.serve_forever()
        
        self.local_server_thread = threading.Thread(target=serve, daemon=True)
        self.local_server_thread.start()
        
        # 等待服务器启动
        time.sleep(0.5)
        
        server_url = f"http://127.0.0.1:{port}"
        return port, server_url
    
    def _resolve_url(self, url_or_path: str) -> str:
        """
        智能解析 URL 或本地路径
        
        Args:
            url_or_path: 可以是 HTTP URL、file:// URL 或本地文件路径
            
        Returns:
            可访问的 URL
        """
        # 如果已经是完整 URL，直接返回
        if url_or_path.startswith(("http://", "https://", "file://")):
            logger.info(f"🔗 使用 URL: {url_or_path}")
            return url_or_path
        
        # 否则当作本地路径处理
        path = Path(url_or_path)
        
        # 如果是文件，获取其所在目录和相对路径
        if path.is_file():
            directory = path.parent
            filename = path.name
        elif path.is_dir():
            # 如果是目录，默认访问 index.html
            directory = path
            filename = "index.html"
        else:
            raise ValueError(f"路径不存在: {url_or_path}")
        
        # 启动本地服务器
        logger.info(f"📂 检测到本地路径，启动服务器...")
        port, server_url = self._start_local_server(str(directory))
        
        # 构造完整 URL
        full_url = f"{server_url}/{filename}"
        logger.info(f"✅ 本地文件映射为: {full_url}")
        
        return full_url
    
    def generate_test_from_url(self, url: str, scenario: str) -> str:
        """
        从 URL 或本地路径生成测试代码（增强版：支持多轮对话 + 本地文件）
        
        Args:
            url: 要测试的页面 URL 或本地文件路径
                - HTTP/HTTPS URL: http://localhost:3000/
                - 本地文件路径: dist/index.html 或 ./dist/index.html
                - 本地目录: dist/ (自动访问 index.html)
            scenario: 测试场景描述
            
        Returns:
            生成的 Playwright 测试代码
        """
        # 解析 URL（自动处理本地路径）
        resolved_url = self._resolve_url(url)
        
        messages = [
            {
                "role": "system",
                "content": """你是一个 Playwright 测试生成专家。

工作流程:
1. 使用 browser_navigate 访问页面
2. 使用 browser_snapshot 获取页面结构
3. 根据需要使用 browser_click、browser_fill 等工具交互
4. 生成符合 POM 模式的 Playwright 测试代码

要求:
- 使用 data-testid 或 role 选择器
- 包含充分的断言
- 代码清晰易维护
- 只返回纯 JavaScript 代码，不要包含 markdown 格式
- **必须使用 ES6 import 语法，不要使用 require**
- 示例：import { test, expect } from '@playwright/test';
"""
            },
            {
                "role": "user",
                "content": f"""请为以下场景生成测试:

URL: {resolved_url}
场景: {scenario}

步骤:
1. 先用 browser_navigate 访问页面
2. 用 browser_snapshot 分析页面结构
3. 根据需要进行交互探索
4. 生成完整的测试代码
"""
            }
        ]
        
        logger.info(f"🚀 开始生成测试: {scenario}")
        
        # 多轮对话，直到 AI 不再调用工具
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"📍 第 {iteration} 轮对话")
            
            try:
                # 调用通义千问
                response = self.client.chat.completions.create(
                model="qwen-plus-latest",
                messages=messages,
                tools=self.tools,
                temperature=0.3
                )
        
                message = response.choices[0].message
        
                # 检查是否有工具调用
                if not message.tool_calls:
                    # 没有工具调用，说明 AI 已经完成
                    logger.info("✅ AI 完成测试生成")
                    return self._extract_code(message.content)
                
                # 有工具调用，执行它们
                logger.info(f"🔧 AI 请求调用 {len(message.tool_calls)} 个工具")
                
                # 将 assistant 的回复添加到历史
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": message.tool_calls
                })
                
                # 执行每个工具调用
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ 解析工具参数失败: {e}")
                        arguments = {}
                    
                    # 执行 MCP 工具
                    result = self.call_mcp_tool(tool_name, arguments)
                    
                    # 将工具结果添加到对话历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False)
                    })
                
            except Exception as e:
                logger.error(f"❌ 对话出错: {e}")
                # 出错时，尝试让 AI 基于已有信息生成代码
                messages.append({
                    "role": "user",
                    "content": "请根据目前掌握的信息生成测试代码。"
                })
                
                try:
                    final_response = self.client.chat.completions.create(
                        model="qwen-plus-latest",
                        messages=messages,
                        temperature=0.3
                    )
                    return self._extract_code(final_response.choices[0].message.content)
                except:
                    return "// 生成测试代码失败\n// 错误: " + str(e)
        
        # 达到最大轮数，强制结束
        logger.warning(f"⚠️ 达到最大对话轮数 ({self.max_iterations})，强制生成代码")
        messages.append({
            "role": "user",
            "content": "请立即生成最终的测试代码，不要再调用工具。"
        })
        
        try:
            final_response = self.client.chat.completions.create(
                    model="qwen-plus-latest",
                    messages=messages,
                    temperature=0.3
            )
            return self._extract_code(final_response.choices[0].message.content)
        except Exception as e:
            logger.error(f"❌ 强制生成代码失败: {e}")
            return "// 生成测试代码失败\n// 错误: " + str(e)
    
    def _extract_code(self, content: str) -> str:
        """
        从 AI 回复中提取纯代码（去除 markdown 格式）
        
        Args:
            content: AI 的原始回复
            
        Returns:
            清理后的代码
        """
        if not content:
            return "// 未生成代码"
        
        # 尝试提取 markdown 代码块
        code_block_pattern = r"```(?:javascript|js)?\s*\n(.*?)\n```"
        matches = re.findall(code_block_pattern, content, re.DOTALL)
        
        if matches:
            # 返回第一个代码块
            logger.info("📝 提取了 markdown 格式的代码")
            code = matches[0].strip()
        else:
            # 没有代码块，返回原始内容
            logger.info("📝 直接使用原始内容")
            code = content.strip()
        
        # 将 require 语法转换为 import 语法
        code = self._convert_require_to_import(code)
        
        return code
    
    def _convert_require_to_import(self, code: str) -> str:
        """
        将 CommonJS require 语法转换为 ES6 import 语法
        
        Args:
            code: 原始代码
            
        Returns:
            转换后的代码
        """
        def replace_require_with_import(match):
            """替换函数，用于清理空格"""
            content = match.group(1).strip()  # 去掉前后空格
            module = match.group(2)
            semicolon = match.group(3) if match.lastindex >= 3 else ''
            return f"import {{ {content} }} from '{module}'{semicolon}"
        
        # 匹配 const { a, b } = require('module'); 或 const { a, b } = require('module')
        pattern1 = r"const\s+\{\s*([^}]+)\s*\}\s*=\s*require\(['\"]([^'\"]+)['\"]\)(;?)"
        code = re.sub(pattern1, replace_require_with_import, code)
        
        # 匹配 const name = require('module'); 或 const name = require('module')
        pattern2 = r"const\s+(\w+)\s*=\s*require\(['\"]([^'\"]+)['\"]\)(;?)"
        code = re.sub(pattern2, r"import \1 from '\2'\3", code)
        
        if 'import' in code and 'require' not in code:
            logger.info("✨ 已将 require 转换为 import 语法")
        
        return code
    
    def cleanup(self):
        """清理资源（更可靠的方式）"""
        # 关闭本地服务器
        if self.local_server:
            logger.info("🧹 正在关闭本地 HTTP 服务器...")
            try:
                self.local_server.shutdown()
                self.local_server.server_close()
                logger.info("✅ 本地服务器已关闭")
            except Exception as e:
                logger.warning(f"⚠️ 关闭本地服务器时出错: {e}")
            finally:
                self.local_server = None
                self.local_server_thread = None
        
        # 关闭 MCP Server
        if self.mcp_process and self.mcp_process.poll() is None:
            logger.info("🧹 正在关闭 MCP Server...")
            try:
                self.mcp_process.terminate()
                self.mcp_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ MCP Server 未及时关闭，强制终止")
                self.mcp_process.kill()
            logger.info("✅ MCP Server 已关闭")
    
    def __del__(self):
        """析构时清理"""
        self.cleanup()


# 使用示例
if __name__ == "__main__":
    # 使用 context manager 确保资源正确清理
    with PlaywrightMCPClient(max_iterations=15, timeout=30) as client:
        logger.info("=" * 60)
        logger.info("🎯 Playwright MCP 测试生成器（增强版 - 支持本地文件）")
        logger.info("=" * 60)
        
        # 方式 1：测试本地 dist 目录中的 HTML 文件
        test_code = client.generate_test_from_url(
            url="dist/index.html", 
            scenario="测试页面的基本功能"
        )
        
        # 方式 2：测试远程 URL（原有功能）
        # test_code = client.generate_test_from_url(
        #     url="http://localhost:3000/",
        #     scenario="测试 Markdown 编辑器的基本功能"
        # )
    
        logger.info("=" * 60)
        logger.info("📄 生成的测试代码:")
        logger.info("=" * 60)
        print(test_code)
    
        # 创建目录并保存到文件
        output_dir = "tests/generated"
        os.makedirs(output_dir, exist_ok=True)
    
        output_file = os.path.join(output_dir, "markdown_editor.spec.js")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(test_code)
    
        logger.info("=" * 60)
        logger.info(f"✅ 测试代码已保存到: {output_file}")
        logger.info("=" * 60)
        logger.info("🚀 运行测试: npx playwright test tests/generated/markdown_editor.spec.js")
        logger.info("=" * 60)