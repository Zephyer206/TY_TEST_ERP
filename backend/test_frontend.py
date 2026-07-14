import asyncio
from playwright.async_api import async_playwright

async def test_parts_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Navigate to frontend
        await page.goto('http://localhost:5173')
        await page.wait_for_load_state('networkidle')
        
        # Login
        await page.fill('input[placeholder*="用户名"]', 'admin')
        await page.fill('input[type="password"]', '123456')
        await page.click('button:has-text("登录")')
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)
        
        # Navigate to parts page
        await page.click('text=零件管理')
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)
        
        # Search for TYAA-Q0093
        search_input = page.locator('input[placeholder*="零件编号"]')
        await search_input.fill('TYAA-Q0093')
        await page.click('button:has-text("搜索")')
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)
        
        # Take screenshot
        await page.screenshot(path='screenshots/left-right-shared-spec/tyaa_q0093_search.png')
        
        # Check table content
        rows = await page.locator('.el-table__body tr').all()
        print(f'Found {len(rows)} rows')
        
        for i, row in enumerate(rows):
            name = await row.locator('td:nth-child(2)').inner_text()
            mold = await row.locator('td:nth-child(3)').inner_text()
            spec = await row.locator('td:nth-child(4)').inner_text()
            position = await row.locator('td:nth-child(7)').inner_text()
            print(f'Row {i+1}: {mold} - {name}')
            print(f'  Spec: {spec}')
            print(f'  Position: {position}')
        
        # Click detail on first row
        if len(rows) > 0:
            await rows[0].locator('button:has-text("详情")').click()
            await asyncio.sleep(2)
            await page.screenshot(path='screenshots/left-right-shared-spec/tyaa_q0093_detail_left.png')
            await page.click('.el-dialog__close')
            await asyncio.sleep(1)
        
        # Click detail on second row
        if len(rows) > 1:
            await rows[1].locator('button:has-text("详情")').click()
            await asyncio.sleep(2)
            await page.screenshot(path='screenshots/left-right-shared-spec/tyaa_q0093_detail_right.png')
            await page.click('.el-dialog__close')
            await asyncio.sleep(1)
        
        await browser.close()
        print('Test completed successfully')

asyncio.run(test_parts_page())
