import { test, expect } from '@playwright/test';

class MarkdownEditorPage {
  constructor(page) {
    this.page = page;
    
    // 导航区域
    this.directoryHeading = page.getByRole('heading', { name: '目录', level: 2 });
    this.newFileButton = page.getByRole('button', { name: '新建文件' });
    this.newFolderButton = page.getByRole('button', { name: '新建文件夹' });
    this.renameButton = page.getByRole('button', { name: '重命名' });
    this.deleteButton = page.getByRole('button', { name: '删除' });
    this.workspaceButton = page.getByRole('button', { name: '📁 工作区' });
    this.exampleFileButton = page.getByRole('button', { name: '📄 示例文档.md' });

    // 编辑区域
    this.markdownInputHeading = page.getByRole('heading', { name: 'Markdown 输入', level: 2 });
    this.markdownTextarea = page.getByPlaceholder('在这里输入 Markdown 文本...');
    this.previewHeading = page.getByRole('heading', { name: '渲染预览', level: 2 });
    this.copyToWechatButton = page.getByRole('button', { name: '复制到微信公众号' });
  }

  async goto() {
    await this.page.goto('https://canace22.github.io/md-render/');
    await this.page.waitForLoadState('domcontentloaded');
    await expect(this.markdownInputHeading).toBeVisible();
    await expect(this.previewHeading).toBeVisible();
  }

  async createNewFile() {
    await expect(this.newFileButton).toBeVisible();
    await this.newFileButton.click();
  }

  async enterMarkdown(content) {
    await expect(this.markdownTextarea).toBeVisible();
    await this.markdownTextarea.fill(content);
  }

  async getRenderedContent() {
    const previewContainer = this.page.locator('.preview-container');
    await expect(previewContainer).toBeVisible();
    return previewContainer;
  }
}

test.describe('Markdown 编辑器功能测试', () => {
  test.beforeEach(async ({ page }) => {
    const editorPage = new MarkdownEditorPage(page);
    await editorPage.goto();
  });

  test('页面基本元素加载', async ({ page }) => {
    const editorPage = new MarkdownEditorPage(page);

    // 验证标题
    await expect(page).toHaveTitle('Markdown 渲染器');

    // 验证目录区域
    await expect(editorPage.directoryHeading).toBeVisible();
    await expect(editorPage.newFileButton).toBeVisible();
    await expect(editorPage.newFolderButton).toBeVisible();
    await expect(editorPage.renameButton).toBeVisible();
    await expect(editorPage.deleteButton).toBeVisible();
    await expect(editorPage.workspaceButton).toBeVisible();
    await expect(editorPage.exampleFileButton).toBeVisible();

    // 验证编辑区域
    await expect(editorPage.markdownInputHeading).toBeVisible();
    await expect(editorPage.markdownTextarea).toBeVisible();
    await expect(editorPage.previewHeading).toBeVisible();
    await expect(editorPage.copyToWechatButton).toBeVisible();
  });

  test('Markdown 基本语法渲染', async ({ page }) => {
    const editorPage = new MarkdownEditorPage(page);
    const testContent = `# 测试标题

这是一个测试段落。

## 子标题

- 无序列表项1
- 无序列表项2
  - 嵌套列表项

1. 有序列表项1
2. 有序列表项2`;

    await editorPage.enterMarkdown(testContent);

    // 验证标题渲染
    await expect(page.getByRole('heading', { name: '测试标题', level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { name: '子标题', level: 2 })).toBeVisible();

    // 验证段落
    await expect(page.getByText('这是一个测试段落。')).toBeVisible();

    // 验证列表
    const listItems = page.getByRole('listitem');
    await expect(listItems).toHaveCount(6); // 包含嵌套列表
    
    // 验证无序列表
    await expect(page.getByText('无序列表项1')).toBeVisible();
    await expect(page.getByText('无序列表项2')).toBeVisible();
    
    // 验证有序列表
    await expect(page.getByText('有序列表项1')).toBeVisible();
    await expect(page.getByText('有序列表项2')).toBeVisible();
  });

  test('Markdown 高级语法渲染', async ({ page }) => {
    const editorPage = new MarkdownEditorPage(page);
    const testContent = `**粗体文本**

*斜体文本*

~~删除线文本~~

\`行内代码\`

\`\`\`javascript
function test() {
  console.log('代码块');
}
\`\`\`

[链接文本](https://example.com)

![图片alt](https://via.placeholder.com/150)

| 表格 | 支持 |
|------|------|
| 单元格1 | 单元格2 |`;

    await editorPage.enterMarkdown(testContent);

    // 验证强调语法
    await expect(page.getByText('粗体文本')).toBeVisible();
    await expect(page.locator('strong').first()).toContainText('粗体文本');
    
    await expect(page.getByText('斜体文本')).toBeVisible();
    await expect(page.locator('em').first()).toContainText('斜体文本');
    
    await expect(page.getByText('删除线文本')).toBeVisible();
    await expect(page.locator('del').first()).toContainText('删除线文本');

    // 验证代码
    await expect(page.getByText('行内代码')).toBeVisible();
    await expect(page.locator('code').first()).toContainText('行内代码');
    
    await expect(page.getByText('function test() {')).toBeVisible();
    await expect(page.getByText('console.log(\'代码块\');')).toBeVisible();

    // 验证链接
    await expect(page.getByRole('link', { name: '链接文本' })).toBeVisible();

    // 验证图片
    await expect(page.locator('img[alt="图片alt"]')).toBeVisible();

    // 验证表格
    await expect(page.getByRole('table')).toBeVisible();
    await expect(page.getByText('表格')).toBeVisible();
    await expect(page.getByText('支持')).toBeVisible();
  });

  test('示例文档内容验证', async ({ page }) => {
    const editorPage = new MarkdownEditorPage(page);
    
    // 验证默认显示的示例文档内容
    await expect(page.getByRole('heading', { name: '欢迎使用 Markdown 渲染器', level: 1 })).toBeVisible();
    await expect(page.getByText('这是一个支持 CommonMark 规范的 Markdown 渲染器示例。')).toBeVisible();
    
    // 验证功能特性列表
    await expect(page.getByText('支持标题')).toBeVisible();
    await expect(page.getByText('支持列表（有序和无序）')).toBeVisible();
    await expect(page.getByText('支持嵌套列表')).toBeVisible();
    await expect(page.getByText('支持代码块（语法高亮）')).toBeVisible();
    
    // 验证代码块
    await expect(page.getByText('function hello() {')).toBeVisible();
    await expect(page.getByRole('button', { name: '复制代码' })).toBeVisible();
    
    // 验证链接
    await expect(page.getByRole('link', { name: 'GitHub' })).toBeVisible();
    
    // 验证图片
    await expect(page.locator('img[alt="22"]')).toBeVisible();
    
    // 验证表格
    await expect(page.getByRole('table')).toBeVisible();
    await expect(page.getByText('功能')).toBeVisible();
    await expect(page.getByText('状态')).toBeVisible();
    
    // 验证引用
    await expect(page.getByText('第一行引用')).toBeVisible();
    await expect(page.getByText('第二行引用')).toBeVisible();
  });
});