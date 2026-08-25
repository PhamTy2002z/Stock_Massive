import { expect, test } from "@playwright/test"

import { newEmail, purge, signUp } from "./desk"

let email = ""

test.beforeEach(async ({ page }) => {
  email = newEmail()
  await signUp(page, email)
})

test.afterEach(async ({ request }) => {
  await purge(request, email)
})

test("market monitor deep links, filters and browser history stay in one workspace", async ({ page }) => {
  await page.goto("/?view=board&lens=sectors&exchange=HNX&horizon=5")

  await expect(page.getByRole("tab", { name: "Ngành" })).toHaveAttribute("aria-selected", "true")
  await expect(page.getByRole("button", { name: "HNX", exact: true })).toHaveAttribute("aria-pressed", "true")
  await expect(page.getByRole("button", { name: "5P" })).toHaveAttribute("aria-pressed", "true")
  await expect(page.getByRole("tabpanel", { name: "Ngành" })).toBeVisible()
  await expect(page.getByRole("tabpanel", { name: "Ngành" }).getByText(/Chưa có dữ liệu|Dữ liệu một phần|Dữ liệu cũ/).first()).toBeVisible()
  await page.screenshot({ path: "../../.impeccable/review/desktop.png", fullPage: true })

  await page.getByRole("tab", { name: "Dòng tiền" }).click()
  await expect(page).toHaveURL(/lens=flow/)
  await expect(page.getByRole("tabpanel", { name: "Dòng tiền" })).toBeVisible()

  await page.goBack()
  await expect(page.getByRole("tab", { name: "Ngành" })).toHaveAttribute("aria-selected", "true")
  await expect(page.getByRole("button", { name: "HNX", exact: true })).toHaveAttribute("aria-pressed", "true")

  for (const lens of ["Tổng quan", "Độ rộng", "Dòng tiền", "Ngành", "Cổ phiếu"]) {
    await page.getByRole("tab", { name: lens, exact: true }).click()
    await expect(page.getByRole("tabpanel", { name: lens, exact: true })).toBeVisible()
  }

  await page.getByRole("button", { name: "Thị trường", exact: true }).click()
  await expect(page.getByRole("complementary", { name: "Bảng thông tin thị trường" })).toBeVisible()
  await page.getByRole("button", { name: "Đóng bảng", exact: true }).click()
  await expect(page.getByRole("tab", { name: "Cổ phiếu" })).toHaveAttribute("aria-selected", "true")
})

test("mobile uses one labeled lens selector and keeps material data state visible", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/?view=board&lens=overview&exchange=ALL")

  const selector = page.getByRole("combobox", { name: "Góc nhìn thị trường" })
  await expect(selector).toBeVisible()
  await page.route("**/api/alpha-desk/stocks/market-monitor/breadth?*", (route) => route.abort())
  await selector.selectOption("breadth")
  await expect(page).toHaveURL(/lens=breadth/)
  const panel = page.getByRole("tabpanel", { name: "Độ rộng" })
  await expect(panel).toBeVisible()
  await expect(panel.getByRole("alert")).toContainText("Không đọc được Market Monitor")
  await page.unroute("**/api/alpha-desk/stocks/market-monitor/breadth?*")
  await panel.getByRole("button", { name: "Thử lại" }).click()
  await expect(panel.getByText(/Chưa có dữ liệu|Dữ liệu một phần|Dữ liệu cũ/).first()).toBeVisible()

  await page.getByRole("button", { name: "Thị trường", exact: true }).click()
  await expect(page.getByRole("dialog", { name: "Bảng thông tin thị trường" })).toBeVisible()
  await page.getByRole("button", { name: "Đóng bảng", exact: true }).click()
  await expect(selector).toHaveValue("breadth")
  await page.screenshot({ path: "../../.impeccable/review/mobile.png", fullPage: true })
})
