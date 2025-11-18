// 表单测试模板 - 针对表单提交场景
import { test, expect } from '@playwright/test';

class FormPage {
    constructor(page) {
        this.page = page;
        // 表单元素
        this.usernameInput = page.getByLabel('用户名');
        this.emailInput = page.getByLabel('邮箱');
        this.passwordInput = page.getByLabel('密码');
        this.submitButton = page.getByRole('button', { name: '提交' });
        this.successMessage = page.getByTestId('success-message');
        this.errorMessage = page.getByTestId('error-message');
    }

    async navigate(url) {
        await this.page.goto(url);
    }

    async fillForm(data) {
        if (data.username) await this.usernameInput.fill(data.username);
        if (data.email) await this.emailInput.fill(data.email);
        if (data.password) await this.passwordInput.fill(data.password);
    }

    async submit() {
        await this.submitButton.click();
    }

    async verifySuccess(message) {
        await expect(this.successMessage).toBeVisible();
        if (message) {
            await expect(this.successMessage).toContainText(message);
        }
    }

    async verifyError(message) {
        await expect(this.errorMessage).toBeVisible();
        if (message) {
            await expect(this.errorMessage).toContainText(message);
        }
    }
}

test.describe('表单提交测试', () => {
    let formPage;

    test.beforeEach(async ({ page }) => {
        formPage = new FormPage(page);
        await formPage.navigate('/form-page');
    });

    test('正向：提交有效数据', async () => {
        await formPage.fillForm({
            username: 'testuser',
            email: 'test@example.com',
            password: 'Test123456'
        });
        await formPage.submit();
        await formPage.verifySuccess('提交成功');
    });

    test('反向：空表单提交', async () => {
        await formPage.submit();
        await formPage.verifyError('请填写所有必填项');
    });

    test('反向：无效邮箱格式', async () => {
        await formPage.fillForm({
            username: 'testuser',
            email: 'invalid-email',
            password: 'Test123456'
        });
        await formPage.submit();
        await formPage.verifyError('邮箱格式不正确');
    });

    test('反向：密码过短', async () => {
        await formPage.fillForm({
            username: 'testuser',
            email: 'test@example.com',
            password: '123'
        });
        await formPage.submit();
        await formPage.verifyError('密码长度至少6位');
    });
});

