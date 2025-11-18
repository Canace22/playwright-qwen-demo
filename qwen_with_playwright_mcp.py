import os
import json
import subprocess
import time
import threading
import http.server
import socketserver
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# 导入公共模块
from config import config
from utils.common import (
    create_openai_client,
    clean_generated_code,
    setup_logger,
    save_test_file
)
from utils.code_validator import validate_test_code

# 配置日志
logger = setup_logger(__name__)

class PlaywrightMCPClient:
    """通义千问 + Playwright MCP 集成客户端（增强版）"""
    
    def __init__(
        self,
        max_iterations: Optional[int] = None,
        timeout: Optional[int] = None,
        validate_code: bool = True
    ):
        """
        初始化客户端
        
        Args:
            max_iterations: 最大工具调用轮数（None 使用配置默认值）
            timeout: 每次 MCP 调用的超时时间（秒，None 使用配置默认值）
            validate_code: 是否验证生成的代码
        """
        self.max_iterations = max_iterations or config.MCP_MAX_ITERATIONS
        self.timeout = timeout or config.MCP_TIMEOUT
        self.validate_code = validate_code
        self.mcp_process = None
        self.request_id = 0
        
        # Cookie 相关
        self.cookies = []  # 存储要设置的 cookie 列表
        
        # 本地服务器相关
        self.local_server = None
        self.local_server_thread = None
        self.local_server_port = None
        self.local_server_dir = None
        
        # 初始化 OpenAI 客户端
        try:
            self.client = create_openai_client(config.api_key)
        except ValueError as e:
            logger.error(f"❌ 初始化失败: {e}")
            raise
        
        # 启动 Playwright MCP Server
        self._start_mcp_server()
        self.tools = self.get_playwright_tools()
        
        logger.info(f"✅ PlaywrightMCPClient 初始化完成（迭代: {self.max_iterations}, 超时: {self.timeout}s）")
    
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
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_set_cookie",
                    "description": "设置浏览器 cookie",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Cookie 名称"
                            },
                            "value": {
                                "type": "string",
                                "description": "Cookie 值"
                            },
                            "domain": {
                                "type": "string",
                                "description": "Cookie 域名（可选）"
                            },
                            "path": {
                                "type": "string",
                                "description": "Cookie 路径（可选，默认为 /）"
                            }
                        },
                        "required": ["name", "value"]
                    }
                }
            }
        ]
    
    def call_mcp_tool(self, tool_name: str, arguments: dict) -> Dict[str, Any]:
        """
        调用 MCP 工具
        
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
            """静默的 HTTP 处理器（减少日志输出，禁用缓存）"""
            def log_message(self, format, *args):
                pass  # 不输出请求日志
            
            def end_headers(self):
                """添加禁用缓存的响应头"""
                # 禁用所有缓存，确保每次都获取最新文件
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                super().end_headers()
            
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=abs_dir, **kwargs)
        
        # 查找可用端口
        if port == 0:
            # 从配置的端口范围开始尝试
            for try_port in range(*config.LOCAL_SERVER_PORT_RANGE):
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
                port_range = config.LOCAL_SERVER_PORT_RANGE
                raise RuntimeError(f"无法找到可用端口（{port_range[0]}-{port_range[1]-1}）")
        else:
            self.local_server = socketserver.TCPServer(
                (config.LOCAL_SERVER_HOST, port), 
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
        
        server_url = f"http://{config.LOCAL_SERVER_HOST}:{port}"
        return port, server_url
    
    def set_cookies(self, cookies_str: str, domain: Optional[str] = None):
        """
        设置要使用的 cookie
        
        Args:
            cookies_str: Cookie 字符串，格式如 "name1=value1; name2=value2"
            domain: Cookie 域名（可选，如果不提供则从 URL 中提取）
        """
        # 解析 cookie 字符串
        cookie_pairs = [pair.strip() for pair in cookies_str.split(';')]
        self.cookies = []
        
        for pair in cookie_pairs:
            if '=' in pair:
                name, value = pair.split('=', 1)
                name = name.strip()
                value = value.strip()
                if name and value:
                    self.cookies.append({
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": "/"
                    })
        
        logger.info(f"🍪 已设置 {len(self.cookies)} 个 cookie")
        for cookie in self.cookies:
            logger.info(f"  - {cookie['name']}={cookie['value'][:50]}...")
    
    def _apply_cookies(self, url: str):
        """
        应用已设置的 cookie 到浏览器
        
        Args:
            url: 目标 URL（用于提取域名）
        """
        if not self.cookies:
            return
        
        # 从 URL 提取域名
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.hostname
        
        # 为每个 cookie 设置域名（如果未设置）
        for cookie in self.cookies:
            if not cookie.get("domain") and domain:
                cookie["domain"] = domain
            
            # 调用 MCP 工具设置 cookie
            try:
                result = self.call_mcp_tool("browser_set_cookie", {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie.get("domain"),
                    "path": cookie.get("path", "/")
                })
                if "error" not in result:
                    logger.info(f"✅ Cookie 设置成功: {cookie['name']}")
                else:
                    logger.warning(f"⚠️ Cookie 设置失败: {cookie['name']} - {result.get('error')}")
            except Exception as e:
                logger.warning(f"⚠️ 设置 Cookie 时出错: {cookie['name']} - {e}")
    
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
        
        # 转换为绝对路径用于比较
        abs_directory = str(Path(directory).resolve())
        
        # 检查是否已经为相同目录启动了服务器
        if self.local_server and self.local_server_dir == abs_directory:
            logger.info(f"♻️  复用已有服务器: http://{config.LOCAL_SERVER_HOST}:{self.local_server_port}")
            server_url = f"http://{config.LOCAL_SERVER_HOST}:{self.local_server_port}"
        else:
            # 如果已有服务器但目录不同，先关闭旧的
            if self.local_server:
                logger.info("🔄 关闭旧服务器，启动新服务器...")
                try:
                    self.local_server.shutdown()
                    self.local_server.server_close()
                except Exception as e:
                    logger.warning(f"⚠️ 关闭旧服务器时出错: {e}")
            
            # 启动新的本地服务器
            logger.info(f"📂 检测到本地路径，启动服务器...")
            port, server_url = self._start_local_server(abs_directory)
        
        # 构造完整 URL
        full_url = f"{server_url}/{filename}"
        logger.info(f"✅ 本地文件映射为: {full_url}")
        
        return full_url
    
    def generate_test_from_url(self, url: str, scenario: str) -> str:
        """
        从 URL 或本地路径生成测试代码
        
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
        
        # 如果有设置的 cookie，先应用它们
        if self.cookies:
            logger.info("🍪 正在应用已设置的 cookie...")
            self._apply_cookies(resolved_url)
        
        messages = [
            {
                "role": "system",
                "content":"""你是一个 Playwright 测试生成专家。

工作流程:
1. 使用 browser_navigate 访问页面
2. 使用 browser_snapshot 获取页面结构
3. 根据需要使用 browser_click、browser_fill 等工具交互
4. 生成符合 POM 模式的 Playwright 测试代码

**关键要求 - 元素查找优化:**

1. **选择器优先级（按稳定性和可靠性排序）:**
   
   **最优先 - 语义化定位器（推荐）:**
   - page.getByRole() - 最稳定，基于 ARIA 角色
     * 按钮: page.getByRole('button', { name: '提交' })
     * 链接: page.getByRole('link', { name: '首页' })
     * 文本框: page.getByRole('textbox', { name: '用户名' })
     * 标题: page.getByRole('heading', { name: '欢迎' })
   
   - page.getByLabel() - 表单元素最佳选择
     * 输入框: page.getByLabel('邮箱')
     * 复选框: page.getByLabel('记住我')
   
   - page.getByPlaceholder() - 当没有 label 时
     * page.getByPlaceholder('请输入邮箱')
   
   - page.getByTestId() - 如果页面有 data-testid
     * page.getByTestId('submit-button')
   
   **次优 - 文本定位器（需谨慎）:**
   - page.getByText() - 精确文本匹配
     * 精确匹配: page.getByText('登录', { exact: true })
     * 部分匹配: page.getByText(/登录|login/i)
     * **注意**: 如果文本在多个元素中出现，必须组合使用或添加 .first()
   
   - page.getByTitle() - 基于 title 属性
     * page.getByTitle('关闭')
   
   **最后选择 - CSS/XPath（不推荐）:**
   - page.locator('css') - 仅当上述方法都不可行时使用
   - page.locator('xpath') - 尽量避免

2. **处理多个匹配元素的策略:**
   
   **方法 A: 精确定位（推荐）**
   ```javascript
   // 组合定位器缩小范围
   const loginForm = page.locator('form[action="/login"]');
   const submitButton = loginForm.getByRole('button', { name: '提交' });
   
   // 使用父容器定位
   const header = page.locator('header');
   const navLink = header.getByRole('link', { name: '首页' });
   
   // 使用更具体的角色选项
   const primaryButton = page.getByRole('button', { name: '提交', pressed: false });
   ```
   
   **方法 B: 索引选择（不推荐，仅作备选）**
   ```javascript
   // 仅在无法精确定位时使用
   const firstButton = page.getByRole('button').first();
   const secondButton = page.getByRole('button').nth(1);
   const lastButton = page.getByRole('button').last();
   ```

3. **等待机制（强制要求）:**
   
   **页面加载等待:**
   ```javascript
   test.beforeEach(async ({ page }) => {
     await page.goto('url');
     // 选择合适的加载状态
     await page.waitForLoadState('domcontentloaded'); // DOM 加载完成（快）
     // 或
     await page.waitForLoadState('networkidle');      // 网络空闲（慢但更稳定）
     
     // 等待关键元素出现
     await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
   });
   ```
   
   **元素操作前的等待:**
   ```javascript
   // 方式 1: 使用 expect (推荐)
   const button = page.getByRole('button', { name: '提交' });
   await expect(button).toBeVisible({ timeout: 10000 });
   await button.click();
   
   // 方式 2: 使用 waitFor
   await button.waitFor({ state: 'visible', timeout: 10000 });
   await button.click();
   
   // 方式 3: Playwright 自动等待（默认）
   // Playwright 会自动等待元素可点击，但建议显式检查
   await button.click();
   ```
   
   **动态内容等待:**
   ```javascript
   // 等待文本变化
   await expect(page.getByText('加载中...')).toBeHidden();
   await expect(page.getByText('加载完成')).toBeVisible();
   
   // 等待元素状态变化
   await expect(submitButton).toBeEnabled();
   await expect(loadingSpinner).not.toBeVisible();
   ```

4. **稳定的断言策略:**
   
   ```javascript
   // 1. 检查可见性（必须）
   await expect(element).toBeVisible();
   
   // 2. 检查状态
   await expect(button).toBeEnabled();
   await expect(checkbox).toBeChecked();
   
   // 3. 检查内容（使用精确匹配）
   await expect(heading).toHaveText('欢迎使用', { timeout: 5000 });
   // 或部分匹配
   await expect(paragraph).toContainText('成功');
   
   // 4. 检查属性
   await expect(input).toHaveAttribute('type', 'email');
   await expect(link).toHaveAttribute('href', /\/dashboard/);
   
   // 5. 检查数量
   await expect(page.getByRole('listitem')).toHaveCount(5);
   ```

5. **超时配置最佳实践:**
   
   ```javascript
   import { test, expect } from '@playwright/test';
   
   // 全局超时
   test.use({
     actionTimeout: 10000,      // 单个操作超时
     navigationTimeout: 30000   // 页面导航超时
   });
   
   test.describe('测试套件', () => {
     // 单个测试超时
     test.setTimeout(60000);
     
     test('测试用例', async ({ page }) => {
       // 单个断言超时
       await expect(element).toBeVisible({ timeout: 15000 });
       
       // 单个操作超时
       await page.goto('url', { timeout: 30000 });
     });
   });
   ```

6. **常见错误模式和修复:**
   
   **❌ 错误示例:**
   ```javascript
   // 问题 1: 没有等待就操作
   await page.goto('url');
   await page.getByRole('button').click(); // 可能失败
   
   // 问题 2: 使用不稳定的选择器
   await page.locator('.btn-primary').click(); // CSS class 可能变化
   
   // 问题 3: 没有处理多个匹配
   await page.getByText('删除').click(); // 如果有多个"删除"会失败
   
   // 问题 4: 没有验证状态
   await button.click();
   // 没有验证点击效果
   ```
   
   **✅ 正确示例:**
   ```javascript
   // 修复 1: 完整的等待流程
   await page.goto('url');
   await page.waitForLoadState('domcontentloaded');
   const button = page.getByRole('button', { name: '提交' });
   await expect(button).toBeVisible();
   await button.click();
   
   // 修复 2: 使用语义化选择器
   await page.getByRole('button', { name: '提交' }).click();
   
   // 修复 3: 精确定位或使用父容器
   const deleteButton = page.locator('tr', { hasText: '用户1' })
     .getByRole('button', { name: '删除' });
   await deleteButton.click();
   
   // 修复 4: 验证操作结果
   await button.click();
   await expect(page.getByText('提交成功')).toBeVisible();
   ```

7. **Page Object Model (POM) 最佳实践:**
   
   ```javascript
   // 页面对象定义
   class LoginPage {
     constructor(page) {
       this.page = page;
       // 定义定位器（不实际查找元素）
       this.usernameInput = page.getByLabel('用户名');
       this.passwordInput = page.getByLabel('密码');
       this.submitButton = page.getByRole('button', { name: '登录' });
       this.errorMessage = page.getByRole('alert');
     }
     
     async goto() {
       await this.page.goto('/login');
       await this.page.waitForLoadState('domcontentloaded');
       await expect(this.submitButton).toBeVisible();
     }
     
     async login(username, password) {
       await expect(this.usernameInput).toBeVisible();
       await this.usernameInput.fill(username);
       await this.passwordInput.fill(password);
       await this.submitButton.click();
     }
     
     async getErrorMessage() {
       await expect(this.errorMessage).toBeVisible();
       return await this.errorMessage.textContent();
     }
   }
   
   // 使用页面对象
   test('登录测试', async ({ page }) => {
     const loginPage = new LoginPage(page);
     await loginPage.goto();
     await loginPage.login('user@example.com', 'password123');
     await expect(page).toHaveURL(/dashboard/);
   });
   ```

8. **生成代码的完整结构模板:**
   
   ```javascript
   import { test, expect } from '@playwright/test';
   
   // 配置
   test.use({
     actionTimeout: 10000,
     navigationTimeout: 30000
   });
   
   // 页面对象（如果适用）
   class PageName {
     constructor(page) {
       this.page = page;
       // 定义所有定位器
       this.element1 = page.getByRole('button', { name: 'xxx' });
       this.element2 = page.getByLabel('xxx');
     }
     
     async performAction() {
       await expect(this.element1).toBeVisible();
       await this.element1.click();
     }
   }
   
   test.describe('测试套件名称', () => {
     test.beforeEach(async ({ page }) => {
       await page.goto('URL');
       await page.waitForLoadState('domcontentloaded');
       // 等待关键元素
       await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
     });
     
     test('测试用例 1', async ({ page }) => {
       // 定位元素
       const element = page.getByRole('button', { name: '按钮文本' });
       
       // 等待并验证
       await expect(element).toBeVisible();
       
       // 执行操作
       await element.click();
       
       // 验证结果
       await expect(page.getByText('成功')).toBeVisible();
     });
     
     test('测试用例 2', async ({ page }) => {
       // 更多测试...
     });
   });
   ```

**关键原则总结:**
1. ✅ 优先使用 getByRole, getByLabel, getByPlaceholder 等语义化定位器
2. ✅ 始终等待元素可见后再操作
3. ✅ 使用 expect().toBeVisible() 验证元素状态
4. ✅ 避免使用 CSS 选择器和 XPath
5. ✅ 通过父容器或组合定位器解决多个匹配问题
6. ✅ 每个操作后验证结果
7. ✅ 使用 POM 模式组织代码
8. ✅ 必须使用 ES6 import 语法
9. ✅ 只返回纯 JavaScript 代码，不包含 markdown 格式
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
                model=config.AI_MODEL,
                messages=messages,
                tools=self.tools,
                temperature=config.AI_TEMPERATURE_STABLE  # 使用配置的温度
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
                        model=config.AI_MODEL,
                        messages=messages,
                        temperature=config.AI_TEMPERATURE_STABLE
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
                    model=config.AI_MODEL,
                    messages=messages,
                    temperature=config.AI_TEMPERATURE_STABLE
            )
            return self._extract_code(final_response.choices[0].message.content)
        except Exception as e:
            logger.error(f"❌ 强制生成代码失败: {e}")
            return "// 生成测试代码失败\n// 错误: " + str(e)
    
    def _extract_code(self, content: str) -> str:
        """
        从 AI 回复中提取并清理代码
        
        Args:
            content: AI 的原始回复
            
        Returns:
            清理后的代码
        """
        # 使用公共函数清理代码
        code = clean_generated_code(content)
        
        # 如果启用了验证，进行质量检查
        if self.validate_code:
            validation_result = validate_test_code(code)
            logger.info(f"📊 代码质量评分: {validation_result['score']}/100")
            
            if validation_result['errors']:
                logger.warning("⚠️ 代码存在错误:")
                for error in validation_result['errors']:
                    logger.warning(f"  - {error}")
            
            if validation_result['warnings']:
                logger.info("💡 代码改进建议:")
                for warning in validation_result['warnings']:
                    logger.info(f"  - {warning}")
        
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
        logger.info("🎯 Playwright MCP 测试生成器")
        logger.info("=" * 60)
        
        # 方式 1：测试本地 dist 目录中的 HTML 文件（使用配置路径）
        # test_url = config.DIST_DIR / "index.html"
        # test_code = client.generate_test_from_url(
        #     url=str(test_url), 
        #     scenario="测试页面的基本功能"
        # )
        
        # 设置 cookie
        # client.set_cookies(
        #     "CASTGC=TGT-0d5f62ed-1be9-40c7-87b5-c16a13e6f748; _cumk=6434a0459898465484747797b59df0ed"
        # )
        
        # 方式 2：测试远程 URL
        test_code = client.generate_test_from_url(
            url="https://canace22.github.io/md-render/",
            scenario="markdown 编辑器"
        )
    
        logger.info("=" * 60)
        logger.info("📄 生成的测试代码:")
        logger.info("=" * 60)
        # print(test_code)
    
        # 保存到文件（使用配置路径和公共函数）
        output_file = config.GENERATED_DIR / "markdown_editor.spec.js"
        save_test_file(test_code, output_file, config.TEST_FILE_ENCODING)
    
        logger.info("=" * 60)
        logger.info(f"✅ 测试代码已保存到: {output_file}")
        logger.info("=" * 60)
        logger.info(f"🚀 运行测试: npx playwright test {output_file}")
        logger.info("=" * 60)