// playwright.config.js
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './',
  use: {
    baseURL: 'file://' + process.cwd() + '/dist/index.html',
    // Headless 模式配置：
    // - 默认启用 headless (true)
    // - 可通过环境变量 HEADLESS=false 关闭
    // - CI 环境自动启用 headless
    headless: process.env.HEADLESS === 'false' ? false : true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});