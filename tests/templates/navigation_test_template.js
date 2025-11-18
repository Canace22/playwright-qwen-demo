// 导航测试模板 - 针对页面导航和路由场景
import { test, expect } from '@playwright/test';

class NavigationPage {
    constructor(page) {
        this.page = page;
        // 导航元素
        this.homeLink = page.getByRole('link', { name: '首页' });
        this.aboutLink = page.getByRole('link', { name: '关于' });
        this.contactLink = page.getByRole('link', { name: '联系我们' });
        this.backButton = page.getByRole('button', { name: '返回' });
    }

    async navigate(url) {
        await this.page.goto(url);
    }

    async clickLink(linkName) {
        const link = this.page.getByRole('link', { name: linkName });
        await link.click();
    }

    async verifyUrl(expectedUrl) {
        await expect(this.page).toHaveURL(expectedUrl);
    }

    async verifyTitle(expectedTitle) {
        await expect(this.page).toHaveTitle(expectedTitle);
    }

    async goBack() {
        await this.backButton.click();
    }
}

test.describe('页面导航测试', () => {
    let navPage;

    test.beforeEach(async ({ page }) => {
        navPage = new NavigationPage(page);
        await navPage.navigate('/');
    });

    test('导航到关于页面', async () => {
        await navPage.clickLink('关于');
        await navPage.verifyUrl('/about');
        await navPage.verifyTitle('关于我们');
    });

    test('导航到联系页面', async () => {
        await navPage.clickLink('联系我们');
        await navPage.verifyUrl('/contact');
    });

    test('返回按钮功能', async () => {
        await navPage.clickLink('关于');
        await navPage.goBack();
        await navPage.verifyUrl('/');
    });

    test('面包屑导航', async ({ page }) => {
        await navPage.clickLink('关于');
        const breadcrumb = page.getByRole('navigation', { name: '面包屑' });
        await expect(breadcrumb).toContainText('首页');
        await expect(breadcrumb).toContainText('关于');
    });
});

