import { expect, test } from '@playwright/test'

test('health page reads readiness through the frontend proxy', async ({ page }) => {
  await page.goto('/health')
  await expect(page.getByRole('heading', { name: 'System health' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'All services ready' })).toBeVisible()
  await expect(page.locator('dl')).toContainText('postgresqlup')
  await expect(page.locator('dl')).toContainText('redisup')
  await page.getByRole('checkbox', { name: 'Refresh every 10 seconds' }).uncheck()
  const response = page.waitForResponse('/api/health/ready')
  await page.getByRole('button', { name: 'Check again' }).click()
  expect((await response).status()).toBe(200)
})

test('health page reports unavailable API', async ({ page }) => {
  await page.route('**/api/health/ready', (route) => route.abort())
  await page.goto('/health')
  await expect(page.getByRole('alert')).toContainText('The API could not be reached')
})
