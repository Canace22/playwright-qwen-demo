import os
from test_generator import TestGenerator

def find_html_files_in_dist():
    """扫描 dist 目录，查找所有 HTML 文件"""
    dist_dir = "dist"
    
    if not os.path.exists(dist_dir):
        return None, f"❌ dist 目录不存在，请先创建 dist 目录并放入要测试的 HTML 文件"
    
    if not os.path.isdir(dist_dir):
        return None, f"❌ dist 不是一个目录"
    
    html_files = [
        os.path.join(dist_dir, name) 
        for name in os.listdir(dist_dir) 
        if name.lower().endswith((".html", ".htm"))
    ]
    
    if not html_files:
        return None, f"❌ 在 dist 目录下未找到任何 HTML 文件，请添加要测试的页面文件"
    
    return html_files, None

def main():
    print("=" * 60)
    print("🤖 Playwright + 通义千问 自动化测试 Demo")
    print("=" * 60)
    print()
    
    # 检查 API Key
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ 错误: 请先设置环境变量 DASHSCOPE_API_KEY")
        print("   export DASHSCOPE_API_KEY='your-api-key'")
        print()
        print("获取 API Key: https://dashscope.aliyun.com/")
        return
    
    # 步骤 1: 扫描 dist 目录
    print("📂 步骤 1: 扫描 dist 目录中的 HTML 文件...")
    html_files, error = find_html_files_in_dist()
    
    if error:
        print(f"   {error}")
        print()
        print("💡 提示:")
        print("   1. 创建 dist 目录: mkdir dist")
        print("   2. 将要测试的 HTML 文件放入 dist 目录")
        print("   3. 重新运行此脚本")
        return
    
    print(f"   ✅ 找到 {len(html_files)} 个 HTML 文件:")
    for i, file_path in enumerate(html_files, 1):
        file_size = os.path.getsize(file_path)
        print(f"   {i}. {file_path} ({file_size} bytes)")
    print()
    
    # 选择第一个 HTML 文件进行分析
    target_html_path = html_files[0]
    print(f"   📌 将分析: {target_html_path}")
    print()
    
    # 步骤 2: 分析页面
    print("🔍 步骤 2: 使用 AI 分析页面结构...")
    generator = TestGenerator()
    
    try:
        with open(target_html_path, "r", encoding="utf-8") as f:
            html_for_analysis = f.read()
        
        analysis = generator.analyze_page_html(html_for_analysis)
        print("   ✅ 分析完成:")
        print(f"   - 发现 {len(analysis.get('elements', []))} 个可测试元素")
        print(f"   - 建议 {len(analysis.get('actions', []))} 个测试动作")
        print()
    except Exception as e:
        print(f"   ⚠️  分析失败: {e}")
        analysis = None
    
    # 步骤 3: 生成测试代码
    print("🎯 步骤 3: 生成 Playwright 测试代码...")
    
    # 基于分析结果自动构造页面描述，避免硬编码字符串
    elements_count = len((analysis or {}).get("elements", []))
    actions = (analysis or {}).get("actions", [])
    top_actions = actions[:5] if isinstance(actions, list) else []
    actions_line = "；".join(top_actions) if top_actions else "请识别关键交互并覆盖"
    page_desc = f"""
页面来源: {target_html_path}
自动分析: 检测到 {elements_count} 个可测试元素。
关键动作建议: {actions_line}

请基于以上页面与建议，生成包含以下测试用例的完整 Playwright 测试代码（使用 POM、稳定选择器、包含断言与等待）:
1. 成功路径（正向）场景
2. 失败路径（反向）场景
"""
    
    try:
        test_code = generator.generate_test(page_desc)
        
        # 保存生成的测试代码
        with open("generated_test.spec.js", "w", encoding="utf-8") as f:
            f.write(test_code)
        
        print("   ✅ 测试代码已生成并保存到 generated_test.spec.js")
        print()
        print("=" * 60)
        print("生成的测试代码预览:")
        print("=" * 60)
        print(test_code[:500] + "...")
        print()
    except Exception as e:
        print(f"   ❌ 生成失败: {e}")
        return
    
    # 步骤 4: 提示执行测试
    print("=" * 60)
    print("✅ Demo 准备完成！")
    print("=" * 60)
    print()
    print("📋 生成的文件:")
    print(f"   1. {target_html_path}       - 被分析的页面")
    print("   2. generated_test.spec.js   - AI 生成的测试代码")
    print("   3. playwright.config.js     - Playwright 配置文件")
    print()
    print("🚀 后续步骤:")
    print("   1. 安装 Playwright (如未安装):")
    print("      npm init -y")
    print("      npm install -D @playwright/test")
    print("      npx playwright install")
    print()
    print("   2. 运行测试:")
    print("      npx playwright test generated_test.spec.js")
    print()
    print("   3. 查看测试报告:")
    print("      npx playwright show-report")
    print()
    
    # 生成 playwright 配置（使用实际分析的 HTML 文件路径）
    html_filename = os.path.basename(target_html_path)
    config = f"""// playwright.config.js
import {{ defineConfig }} from '@playwright/test';

export default defineConfig({{
  testDir: './',
  use: {{
    baseURL: 'file://' + process.cwd() + '/{target_html_path}',
    headless: false,  // 显示浏览器方便演示
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  }},
}});"""
    
    with open("playwright.config.js", "w") as f:
        f.write(config)
    
    print("   ✅ 已自动生成 playwright.config.js")
    print()
    print("=" * 60)
    print("💡 提示: 这个 Demo 展示了:")
    print("   ✅ AI 能理解页面结构")
    print("   ✅ 自动生成符合规范的测试代码")
    print("   ✅ 使用稳定的选择器策略")
    print("   ✅ 包含 POM 设计模式")
    print("=" * 60)


if __name__ == "__main__":
    main()