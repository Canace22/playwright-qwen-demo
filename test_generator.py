import os
import json
from openai import OpenAI

class TestGenerator:
    def __init__(self):
        # 通义千问 API 配置 (兼容 OpenAI SDK)
        self.client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    
    def generate_test(self, page_description: str) -> str:
        """根据页面描述生成 Playwright 测试代码"""
        
        prompt = f"""你是一个 Playwright 测试专家。请根据以下页面描述生成完整的测试代码。

页面描述:
{page_description}

要求:
1. 使用 Page Object Model (POM) 设计模式
2. 使用稳定的选择器: getByRole, getByTestId, getByLabel
3. 包含正向和反向测试用例
4. 添加必要的断言和等待
5. 使用 ES Module 语法（import/export），不要使用 require；代码要完整可运行

请直接输出 JavaScript 代码，不要添加任何解释。"""

        response = self.client.chat.completions.create(
            model="qwen-plus-latest",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # 降低温度保证输出稳定
        )
        
        content = response.choices[0].message.content
        # 去除可能的 markdown 代码块标记，确保可直接运行
        for fence in ("```javascript", "```js", "```ts", "```typescript", "```"):
            content = content.replace(fence, "")
        return content.strip()

    def analyze_page_html(self, html: str) -> dict:
        """分析页面 HTML，提取测试要点"""
        
        prompt = f"""分析以下 HTML 代码，提取测试要点:

{html}

请以 JSON 格式返回:
{{
  "elements": [
    {{"type": "input", "testId": "xxx", "label": "xxx", "selector": "xxx"}},
    ...
  ],
  "actions": ["点击登录按钮", "填写用户名", ...],
  "assertions": ["验证成功消息显示", ...]
}}

只返回 JSON，不要其他内容。"""

        response = self.client.chat.completions.create(
            model="qwen-plus-latest",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        
        content = response.choices[0].message.content
        # 去除可能的 markdown 代码块标记
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)