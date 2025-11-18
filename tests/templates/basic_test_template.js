// 基础测试模板 - 用于引导 AI 生成稳定的测试代码
// 这个模板展示了标准的 Playwright 测试结构

import { test, expect } from '@playwright/test';

// ===== Page Object Model 示例 =====
class ExamplePage {
    constructor(page) {
        this.page = page;
        // 使用稳定的选择器策略
        this.exampleButton = page.getByTestId('example-button');
        this.exampleInput = page.getByLabel('示例输入');
        this.exampleHeading = page.getByRole('heading', { name: '示例标题' });
    }

    async navigate() {
        await this.page.goto('/example-page');
    }

    async performAction(value) {
        await this.exampleInput.fill(value);
        await this.exampleButton.click();
    }

    async verifyResult(expectedText) {
        await expect(this.exampleHeading).toBeVisible();
        await expect(this.exampleHeading).toContainText(expectedText);
    }
}

// ===== 测试用例示例 =====

test.describe('示例功能测试', () => {
    let examplePage;

    test.beforeEach(async ({ page }) => {
        examplePage = new ExamplePage(page);
        await examplePage.navigate();
    });

    test('正向场景：正常流程测试', async () => {
        // 1. 执行操作
        await examplePage.performAction('测试数据');
        
        // 2. 验证结果
        await examplePage.verifyResult('预期结果');
    });

    test('反向场景：边界条件测试', async () => {
        // 测试空输入
        await examplePage.performAction('');
        
        // 验证错误提示
        const errorMessage = examplePage.page.getByText('输入不能为空');
        await expect(errorMessage).toBeVisible();
    });

    test('异常场景：网络错误处理', async ({ page }) => {
        // 模拟网络错误
        await page.route('**/api/**', route => route.abort());
        
        // 执行操作
        await examplePage.performAction('测试数据');
        
        // 验证错误提示
        const networkError = page.getByText('网络错误');
        await expect(networkError).toBeVisible();
    });
});

// ===== 选择器最佳实践 =====
// ✅ 推荐：使用 testId（最稳定）
// page.getByTestId('submit-button')

// ✅ 推荐：使用语义化角色
// page.getByRole('button', { name: '提交' })
// page.getByRole('heading', { name: '标题' })

// ✅ 推荐：使用 label
// page.getByLabel('用户名')

// ⚠️ 谨慎：使用文本（可能变化）
// page.getByText('提交')

// ❌ 避免：使用 class 或 id（可能变化）
// page.locator('.submit-btn')
// page.locator('#submit')

