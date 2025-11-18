import { test, expect } from '@playwright/test';

test.describe('Markdown 编辑器功能测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('https://canace22.github.io/md-render/');
    await page.waitForLoadState('networkidle');
    
    // 等待页面关键元素加载完成
    await expect(page.getByRole('heading', { name: 'Markdown 渲染器' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('textbox', { name: '在这里输入 Markdown 文本...' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '渲染预览' })).toBeVisible();
  });

  test('验证初始页面结构和默认内容', async ({ page }) => {
    // 验证标题
    await expect(page.getByRole('heading', { name: '欢迎使用 Markdown 渲染器', level: 1 })).toBeVisible();
    
    // 验证功能特性列表
    const features = page.getByRole('list').first();
    await expect(features).toContainText('支持标题');
    await expect(features).toContainText('支持列表（有序和无序）');
    await expect(features).toContainText('支持代码块（语法高亮）');
    
    // 验证示例代码块
    await expect(page.getByRole('heading', { name: '示例代码' })).toBeVisible();
    const codeBlock = page.locator('figure pre code');
    await expect(codeBlock).toContainText('function hello() { console.log(\'Hello, Markdown!\'); }');
    
    // 验证链接
    const githubLink = page.getByRole('link', { name: 'GitHub' });
    await expect(githubLink).toBeVisible();
    await expect(githubLink).toHaveAttribute('href', 'https://github.com');
    
    // 验证格式化文本
    await expect(page.getByText('粗体文本')).toBeVisible();
    await expect(page.getByText('斜体文本')).toBeVisible();
    await expect(page.getByText('删除线')).toBeVisible();
    
    // 验证表格
    const table = page.getByRole('table');
    await expect(table).toBeVisible();
    await expect(table.getByRole('cell', { name: '标题' })).toBeVisible();
    await expect(table.getByRole('cell', { name: '✅' })).toHaveCount(5);
  });

  test('验证 Markdown 输入和实时预览功能', async ({ page }) => {
    const markdownInput = page.getByRole('textbox', { name: '在这里输入 Markdown 文本...' });
    const previewTitle = page.getByRole('heading', { name: '测试文档标题', level: 1 });
    
    // 输入 Markdown 内容
    await markdownInput.fill('# 测试文档标题\n\n## 测试子标题\n\n这是一个测试段落。\n\n- 列表项1\n- 列表项2\n\n**粗体文本** *斜体文本*');
    
    // 验证预览区域正确渲染
    await expect(previewTitle).toBeVisible();
    await expect(page.getByRole('heading', { name: '测试子标题', level: 2 })).toBeVisible();
    await expect(page.getByText('这是一个测试段落。')).toBeVisible();
    
    // 验证列表渲染
    const listItems = page.getByRole('listitem');
    await expect(listItems).toHaveCount(2);
    await expect(listItems.first()).toContainText('列表项1');
    
    // 验证文本格式化
    await expect(page.getByText('粗体文本')).toBeVisible();
    await expect(page.getByText('斜体文本')).toBeVisible();
  });

  test('验证目录操作按钮功能', async ({ page }) => {
    const newFileButton = page.getByRole('button', { name: '新建文件' });
    const newFolderButton = page.getByRole('button', { name: '新建文件夹' });
    const renameButton = page.getByRole('button', { name: '重命名' });
    const deleteButton = page.getByRole('button', { name: '删除' });
    const copyToWechatButton = page.getByRole('button', { name: '复制到微信公众号' });
    
    // 验证所有按钮可见
    await expect(newFileButton).toBeVisible();
    await expect(newFolderButton).toBeVisible();
    await expect(renameButton).toBeVisible();
    await expect(deleteButton).toBeVisible();
    await expect(copyToWechatButton).toBeVisible();
    
    // 验证工作区和示例文档存在
    await expect(page.getByRole('button', { name: '📁 工作区' })).toBeVisible();
    await expect(page.getByRole('button', { name: '📄 示例文档.md' })).toBeVisible();
  });

  test('验证代码块和复制功能', async ({ page }) => {
    // 验证代码块标题
    await expect(page.getByRole('heading', { name: '示例代码' })).toBeVisible();
    
    // 验证代码语言标识
    await expect(page.getByText('javascript')).toBeVisible();
    
    // 验证复制代码按钮
    const copyCodeButton = page.getByRole('button', { name: '复制代码' }).first();
    await expect(copyCodeButton).toBeVisible();
    
    // 验证代码内容
    const codeContent = page.locator('pre code');
    await expect(codeContent).toContainText('function hello()');
    await expect(codeContent).toContainText('console.log(\'Hello, Markdown!\');');
  });

  test('验证复杂 Markdown 元素渲染', async ({ page }) => {
    // 验证引用块
    await expect(page.getByRole('heading', { name: '多行引用示例' })).toBeVisible();
    const blockquote = page.getByRole('blockquote');
    await expect(blockquote).toContainText('第一行引用');
    await expect(blockquote).toContainText('第二行引用');
    await expect(blockquote.getByText('粗体')).toBeVisible();
    await expect(blockquote.getByText('斜体')).toBeVisible();
    
    // 验证表格渲染
    await expect(page.getByRole('heading', { name: '表格示例' })).toBeVisible();
    const table = page.getByRole('table');
    await expect(table).toBeVisible();
    
    // 验证表格头部
    const headers = table.getByRole('cell');
    await expect(headers.nth(0)).toHaveText('功能');
    await expect(headers.nth(1)).toHaveText('状态');
    await expect(headers.nth(2)).toHaveText('说明');
    
    // 验证表格内容
    await expect(table).toContainText('标题');
    await expect(table).toContainText('✅');
    await expect(table).toContainText('支持 H1-H6');
    
    // 验证嵌套列表
    await expect(page.getByRole('heading', { name: '嵌套列表示例' })).toBeVisible();
    const nestedList = page.getByRole('list').nth(1);
    await expect(nestedList.getByRole('listitem')).toHaveCount(3);
    
    // 验证三级嵌套
    const thirdLevelList = nestedList.getByRole('list').first().getByRole('list').first();
    await expect(thirdLevelList).toBeVisible();
    await expect(thirdLevelList.getByRole('listitem')).toHaveCount(2);
  });
});