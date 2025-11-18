"""
代码验证工具
用于自动检查生成的测试代码质量
"""
import re
from typing import List, Dict, Any
from pathlib import Path


class CodeValidator:
    """测试代码验证器"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.score = 100  # 初始满分
    
    def validate(self, code: str) -> Dict[str, Any]:
        """
        验证测试代码质量
        
        Args:
            code: 测试代码字符串
            
        Returns:
            验证结果字典 {
                "valid": bool,
                "score": int (0-100),
                "errors": List[str],
                "warnings": List[str],
                "suggestions": List[str]
            }
        """
        self.errors = []
        self.warnings = []
        self.score = 100
        suggestions = []
        
        # 1. 检查基本语法
        self._check_syntax(code)
        
        # 2. 检查导入语句
        self._check_imports(code)
        
        # 3. 检查选择器策略
        self._check_selectors(code)
        
        # 4. 检查断言
        self._check_assertions(code)
        
        # 5. 检查 POM 模式
        self._check_pom_pattern(code)
        
        # 6. 检查测试结构
        self._check_test_structure(code)
        
        # 生成建议
        if self.score >= 90:
            suggestions.append("代码质量优秀！")
        elif self.score >= 70:
            suggestions.append("代码质量良好，建议优化选择器和断言")
        else:
            suggestions.append("代码需要重大改进，建议重新生成")
        
        return {
            "valid": len(self.errors) == 0,
            "score": max(0, self.score),
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": suggestions
        }
    
    def _check_syntax(self, code: str):
        """检查基本语法"""
        # 检查是否为空
        if not code or not code.strip():
            self.errors.append("代码为空")
            self.score -= 100
            return
        
        # 检查是否包含基本的测试结构
        if 'test(' not in code and 'test.describe(' not in code:
            self.errors.append("缺少测试用例定义（test 或 test.describe）")
            self.score -= 30
    
    def _check_imports(self, code: str):
        """检查导入语句"""
        # 检查是否使用 ES6 import
        if 'require(' in code and 'import' not in code:
            self.errors.append("使用了 CommonJS require，应使用 ES6 import")
            self.score -= 20
        
        # 检查是否导入了 Playwright
        if 'import' in code:
            if '@playwright/test' not in code:
                self.warnings.append("未检测到 @playwright/test 导入")
                self.score -= 10
            
            # 检查是否导入了 expect
            if 'expect' not in code:
                self.warnings.append("未导入 expect，可能缺少断言")
                self.score -= 5
    
    def _check_selectors(self, code: str):
        """检查选择器策略"""
        # 统计不同类型的选择器
        good_selectors = len(re.findall(r'getBy(TestId|Role|Label|Text)', code))
        bad_selectors = len(re.findall(r'\.locator\([\'"][\.\#]', code))  # . 或 # 开头
        
        if bad_selectors > 0:
            self.warnings.append(
                f"发现 {bad_selectors} 个不稳定选择器（class/id），"
                "建议使用 getByTestId 或 getByRole"
            )
            self.score -= min(bad_selectors * 5, 20)
        
        if good_selectors == 0:
            self.warnings.append("未发现推荐的选择器方法（getByTestId/Role/Label）")
            self.score -= 10
    
    def _check_assertions(self, code: str):
        """检查断言"""
        # 统计断言数量
        assertions = len(re.findall(r'expect\(.*?\)\.to', code))
        
        if assertions == 0:
            self.errors.append("缺少断言（expect），测试无法验证结果")
            self.score -= 30
        elif assertions < 2:
            self.warnings.append("断言较少，建议增加更多验证")
            self.score -= 5
        
        # 检查是否有充分的可见性验证
        if 'toBeVisible' not in code and 'toBeHidden' not in code:
            self.warnings.append("建议添加元素可见性断言（toBeVisible）")
            self.score -= 5
    
    def _check_pom_pattern(self, code: str):
        """检查 Page Object Model 模式"""
        # 检查是否定义了 Page 类
        class_pattern = r'class\s+\w+Page\s*\{'
        if not re.search(class_pattern, code):
            self.warnings.append(
                "未使用 Page Object Model 模式，建议封装页面对象"
            )
            self.score -= 15
        else:
            # 检查类中是否有构造函数
            if 'constructor(' not in code:
                self.warnings.append("Page 类缺少构造函数")
                self.score -= 5
    
    def _check_test_structure(self, code: str):
        """检查测试结构"""
        # 检查是否有 describe 分组
        if 'test.describe(' not in code and code.count('test(') > 3:
            self.warnings.append("建议使用 test.describe 对多个测试用例分组")
            self.score -= 5
        
        # 检查是否有 beforeEach
        if 'beforeEach' not in code and 'class' in code:
            self.warnings.append("建议使用 beforeEach 初始化 Page 对象")
            self.score -= 5
        
        # 检查是否有注释
        comment_lines = len(re.findall(r'^\s*\/\/', code, re.MULTILINE))
        if comment_lines == 0:
            self.warnings.append("建议添加适当的注释说明")
            self.score -= 3


class TemplateManager:
    """测试模板管理器"""
    
    def __init__(self, templates_dir: Path):
        """
        初始化模板管理器
        
        Args:
            templates_dir: 模板目录路径
        """
        self.templates_dir = templates_dir
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, str]:
        """加载所有模板"""
        templates = {}
        
        if not self.templates_dir.exists():
            return templates
        
        for template_file in self.templates_dir.glob("*.js"):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    template_name = template_file.stem
                    templates[template_name] = f.read()
            except Exception as e:
                print(f"警告: 加载模板 {template_file} 失败: {e}")
        
        return templates
    
    def get_template(self, template_name: str) -> str:
        """获取指定模板"""
        return self.templates.get(template_name, "")
    
    def list_templates(self) -> List[str]:
        """列出所有可用模板"""
        return list(self.templates.keys())
    
    def get_best_template(self, scenario: str) -> str:
        """
        根据场景描述选择最合适的模板
        
        Args:
            scenario: 测试场景描述
            
        Returns:
            模板内容
        """
        scenario_lower = scenario.lower()
        
        # 简单的关键词匹配
        if any(word in scenario_lower for word in ['表单', 'form', '提交', 'submit']):
            return self.get_template('form_test_template')
        elif any(word in scenario_lower for word in ['导航', 'navigation', '路由', 'route']):
            return self.get_template('navigation_test_template')
        else:
            # 默认返回基础模板
            return self.get_template('basic_test_template')


def validate_test_code(code: str) -> Dict[str, Any]:
    """
    便捷函数：验证测试代码
    
    Args:
        code: 测试代码
        
    Returns:
        验证结果
    """
    validator = CodeValidator()
    return validator.validate(code)


# 使用示例
if __name__ == "__main__":
    # 测试验证器
    sample_code = """
import { test, expect } from '@playwright/test';

class LoginPage {
    constructor(page) {
        this.page = page;
        this.usernameInput = page.getByTestId('username');
        this.submitButton = page.getByRole('button', { name: '登录' });
    }
}

test.describe('登录测试', () => {
    test('正常登录', async ({ page }) => {
        const loginPage = new LoginPage(page);
        await expect(loginPage.submitButton).toBeVisible();
    });
});
    """
    
    result = validate_test_code(sample_code)
    print("验证结果:", result)

