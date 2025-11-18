import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# 导入公共模块
from config import config
from utils.common import (
    create_openai_client,
    clean_generated_code,
    safe_json_loads,
    call_ai_with_retry,
    setup_logger
)
from utils.code_validator import (
    CodeValidator,
    TemplateManager,
    validate_test_code
)

# 配置日志
logger = setup_logger(__name__)


class TestGenerator:
    """测试代码生成器"""
    
    def __init__(self, use_templates: bool = True):
        """
        初始化生成器
        
        Args:
            use_templates: 是否使用模板引导生成
        """
        # 初始化 AI 客户端
        self.client = create_openai_client(config.api_key)
        
        # 初始化模板管理器
        self.use_templates = use_templates
        self.template_manager = TemplateManager(config.TEMPLATES_DIR)
        
        # 初始化验证器
        self.validator = CodeValidator()
        
        logger.info(f"✅ TestGenerator 初始化完成（模板: {use_templates}）")
    
    def generate_test(
        self,
        page_description: str,
        scenario: Optional[str] = None,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        根据页面描述生成 Playwright 测试代码
        
        Args:
            page_description: 页面描述
            scenario: 测试场景（可选，用于选择模板）
            validate: 是否验证生成的代码
            
        Returns:
            {
                "code": str,  # 生成的代码
                "validation": dict,  # 验证结果（如果 validate=True）
                "template_used": str  # 使用的模板名称
            }
        """
        logger.info(f"🚀 开始生成测试: {scenario or '默认场景'}")
        
        # 1. 构建 prompt（可能包含模板）
        prompt = self._build_prompt(page_description, scenario)
        
        # 2. 调用 AI 生成代码
        messages = [{"role": "user", "content": prompt}]
        raw_content = call_ai_with_retry(
            client=self.client,
            messages=messages,
            model=config.AI_MODEL,
            temperature=config.AI_TEMPERATURE_STABLE,  # 使用最稳定的温度
            max_retries=3
        )
        
        if not raw_content:
            logger.error("❌ AI 生成失败")
            return {
                "code": "// 生成失败",
                "validation": {"valid": False, "errors": ["AI 调用失败"]},
                "template_used": None
            }
        
        # 3. 清理代码
        code = clean_generated_code(raw_content)
        
        # 4. 验证代码（如果需要）
        validation_result = None
        if validate:
            validation_result = self.validator.validate(code)
            logger.info(f"📊 代码质量评分: {validation_result['score']}/100")
            
            # 如果质量太差，尝试重新生成一次
            if validation_result['score'] < 50:
                logger.warning("⚠️ 代码质量不佳，尝试重新生成...")
                retry_code = self._retry_generate(
                    prompt,
                    validation_result['errors']
                )
                if retry_code:
                    code = retry_code
                    validation_result = self.validator.validate(code)
                    logger.info(f"📊 重新生成后评分: {validation_result['score']}/100")
        
        template_used = self._get_template_name(scenario)
        
        return {
            "code": code,
            "validation": validation_result,
            "template_used": template_used
        }
    
    def analyze_page_html(self, html: str) -> Optional[Dict[str, Any]]:
        """
        分析页面 HTML，提取测试要点
        
        Args:
            html: HTML 代码
            
        Returns:
            结构化的分析结果，失败返回 None
        """
        logger.info("🔍 开始分析页面 HTML...")
        
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

        messages = [{"role": "user", "content": prompt}]
        raw_content = call_ai_with_retry(
            client=self.client,
            messages=messages,
            model=config.AI_MODEL,
            temperature=config.AI_TEMPERATURE_CREATIVE,  # 分析可以稍有创造性
            max_retries=3
        )
        
        if not raw_content:
            logger.error("❌ HTML 分析失败")
            return None
        
        # 解析 JSON
        result = safe_json_loads(raw_content)
        if result:
            logger.info("✅ HTML 分析完成")
        
        return result
    
    def _build_prompt(self, page_description: str, scenario: Optional[str]) -> str:
        """构建生成代码的 prompt"""
        base_prompt = f"""你是一个 Playwright 测试专家。请根据以下页面描述生成完整的测试代码。

页面描述:
{page_description}
"""
        
        # 如果使用模板，添加模板示例
        if self.use_templates and scenario:
            template = self.template_manager.get_best_template(scenario)
            if template:
                base_prompt += f"""

参考以下模板的结构和最佳实践:
{template}

注意: 这只是参考模板，请根据实际页面描述生成代码，不要照搬模板。
"""
        
        # 添加要求
        base_prompt += """

要求:
1. **必须使用 ES6 import 语法**，不要使用 require
2. 使用 Page Object Model (POM) 设计模式
3. 优先使用稳定的选择器: getByTestId > getByRole > getByLabel
4. 包含正向、反向和异常测试用例
5. 添加充分的断言（至少包含可见性断言）
6. 使用 test.describe 对测试分组
7. 使用 beforeEach 初始化页面对象
8. 添加必要的注释说明

请直接输出完整可运行的 JavaScript 代码，不要添加任何额外解释。"""
        
        return base_prompt
    
    def _retry_generate(
        self,
        original_prompt: str,
        errors: list
    ) -> Optional[str]:
        """重新生成代码（带错误提示）"""
        retry_prompt = original_prompt + f"""

注意: 上次生成的代码存在以下问题，请修正:
{chr(10).join(f'- {error}' for error in errors)}
"""
        
        messages = [{"role": "user", "content": retry_prompt}]
        raw_content = call_ai_with_retry(
            client=self.client,
            messages=messages,
            model=config.AI_MODEL,
            temperature=config.AI_TEMPERATURE_STABLE,
            max_retries=1
        )
        
        if raw_content:
            return clean_generated_code(raw_content)
        return None
    
    def _get_template_name(self, scenario: Optional[str]) -> Optional[str]:
        """获取使用的模板名称"""
        if not self.use_templates or not scenario:
            return None
        
        scenario_lower = scenario.lower()
        if any(word in scenario_lower for word in ['表单', 'form', '提交']):
            return 'form_test_template'
        elif any(word in scenario_lower for word in ['导航', 'navigation', '路由']):
            return 'navigation_test_template'
        else:
            return 'basic_test_template'


# 便捷函数
def generate_test_code(
    page_description: str,
    scenario: Optional[str] = None,
    validate: bool = True
) -> Dict[str, Any]:
    """
    便捷函数：生成测试代码
    
    Args:
        page_description: 页面描述
        scenario: 测试场景
        validate: 是否验证
        
    Returns:
        生成结果
    """
    generator = TestGenerator()
    return generator.generate_test(page_description, scenario, validate)