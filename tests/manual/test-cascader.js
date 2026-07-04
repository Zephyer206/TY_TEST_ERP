const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  // 监听控制台消息
  page.on('console', msg => console.log('浏览器日志:', msg.text()));

  // 监听页面错误
  page.on('pageerror', error => console.error('页面错误:', error.message));

  try {
    console.log('访问前端页面: http://localhost:5174');
    await page.goto('http://localhost:5174/login');

    console.log('\n请手动执行以下步骤:');
    console.log('1. 登录系统（用户名: admin, 密码: admin123）');
    console.log('2. 进入报价管理页面');
    console.log('3. 点击"新建报价"按钮');
    console.log('4. 检查零件名称字段是否显示为级联选择器');
    console.log('5. 点击级联选择器，检查左侧是否显示"弹簧片类"和"报警器类"');
    console.log('6. 点击"弹簧片类"，检查右侧是否显示具体的零件名称');
    console.log('7. 点击零件名称旁边的"+"按钮，检查快捷新增对话框');
    console.log('8. 检查快捷新增表单是否包含：零件名称(必填)、一级分类(下拉选择)、客户零件名称');

    console.log('\n浏览器将保持打开60秒，请进行手动测试...');
    await page.waitForTimeout(60000);

  } catch (error) {
    console.error('出错:', error.message);
  } finally {
    await browser.close();
  }
})();
