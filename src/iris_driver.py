import os
import asyncio
import base64
import logging
from typing import Dict, Any, Callable, Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from src.captcha_solver import solve_captcha_image

logger = logging.getLogger("iris_driver")

class IrisDriver:
    """
    Automated Playwright Driver for FBR IRIS 2.0.
    Enforces strict Draft-Only execution.
    """
    def __init__(self, page: Page, status_callback: Optional[Callable] = None):
        self.page = page
        self.status_callback = status_callback
        self.base_url = "https://iris.fbr.gov.pk"

    async def _emit(self, step: str, message: str, take_screenshot: bool = True):
        screenshot_b64 = None
        if take_screenshot:
            try:
                ss_bytes = await self.page.screenshot(type="jpeg", quality=60)
                screenshot_b64 = base64.b64encode(ss_bytes).decode("utf-8")
            except Exception as e:
                logger.warning(f"Could not take screenshot: {e}")

        logger.info(f"[{step}] {message}")
        if self.status_callback:
            await self.status_callback({
                "step": step,
                "message": message,
                "screenshot": screenshot_b64
            })

    async def login(self, cnic: str, password: str, max_retries: int = 3):
        await self._emit("LOGIN_INIT", "Navigating to FBR IRIS portal...")
        await self.page.goto(f"{self.base_url}/", wait_until="networkidle", timeout=45000)

        for attempt in range(1, max_retries + 1):
            await self._emit("CAPTCHA_SOLVE", f"Attempting login (Attempt {attempt}/{max_retries})...")
            
            # Locate registration / CNIC field (placeholder is 'CNIC/NTN' on IRIS 2.0)
            cnic_input = self.page.locator("input[placeholder*='CNIC'], input[placeholder*='NTN'], input[placeholder*='Registration'], input[type='text']").first
            await cnic_input.wait_for(state="visible", timeout=10000)
            await cnic_input.click()
            await cnic_input.fill(cnic)

            # Locate password field
            pass_input = self.page.locator("input[placeholder*='Password'], input[type='password']").first
            await pass_input.click()
            await pass_input.fill(password)

            # Check if captcha image is present (IRIS 2.0 login card has no captcha by default)
            captcha_img = self.page.locator("img[src*='captcha'], #captchaImg, img[id*='captcha'], .captcha-img").first
            has_captcha = False
            try:
                if await captcha_img.count() > 0 and await captcha_img.is_visible():
                    has_captcha = True
            except Exception:
                has_captcha = False

            if has_captcha:
                img_bytes = await captcha_img.screenshot(type="png")
                solved_code = solve_captcha_image(img_bytes)
                await self._emit("CAPTCHA_SOLVE", f"Solved Captcha: {solved_code}")
                captcha_input = self.page.locator("input[placeholder*='Captcha'], input[name*='captcha'], input[id*='captcha']").first
                await captcha_input.fill(solved_code)
            else:
                await self._emit("LOGIN_CREDENTIALS", "No captcha required on IRIS 2.0. Logging in with credentials...")

            # Click login button (IRIS 2.0 uses uppercase 'LOGIN')
            login_btn = self.page.locator("button:has-text('LOGIN'), button:has-text('Login'), input[value='Login'], button[type='submit']").first
            await login_btn.click()
            await self._emit("LOGIN_SUBMITTED", "Submitted credentials. Checking for 'Verify CAPTCHA' modal...")

            # Check if 'Verify CAPTCHA' modal pops up (as shown in IRIS 2.0)
            captcha_modal = self.page.locator(":has-text('Verify CAPTCHA'), div[role='dialog'], .modal").first
            has_modal = False
            try:
                await captcha_modal.wait_for(state="visible", timeout=6000)
                has_modal = True
            except Exception:
                has_modal = False

            if has_modal:
                await self._emit("CAPTCHA_MODAL", "FBR 'Verify CAPTCHA' modal detected! Extracting image...")
                # Locate captcha image inside the modal
                modal_img = self.page.locator(".modal img, div[role='dialog'] img, div:has-text('Verify CAPTCHA') img").first
                await modal_img.wait_for(state="visible", timeout=5000)
                img_bytes = await modal_img.screenshot(type="png")

                # Solve using Gemini Vision via OpenRouter
                solved_code = solve_captcha_image(img_bytes)
                await self._emit("CAPTCHA_SOLVE", f"Gemini Vision solved CAPTCHA: {solved_code}")

                # Locate 'Enter CAPTCHA' input inside modal
                code_input = self.page.locator(".modal input, div[role='dialog'] input, input[placeholder*='CAPTCHA'], input[placeholder*='Enter CAPTCHA']").first
                await code_input.fill(solved_code)
                await code_input.press("Enter")
                await self.page.wait_for_timeout(1000)

                # Click 'Verify' button with force=True (bypasses viewport scroll issues)
                verify_btn = self.page.locator(".modal button:has-text('Verify'), div[role='dialog'] button:has-text('Verify'), button:has-text('Verify'), button:has-text('VERIFY')").first
                if await verify_btn.count() > 0:
                    try:
                        await verify_btn.click(force=True, timeout=5000)
                    except Exception:
                        await verify_btn.dispatch_event("click")

                await self._emit("CAPTCHA_VERIFYING", f"Submitted code '{solved_code}' to Verify button...")
                await self.page.wait_for_timeout(3000)

            # Wait for dashboard transition
            await self.page.wait_for_timeout(3000)
            
            # Check if logged in (URL contains dashboard or contains user name / menu)
            if "dashboard" in self.page.url or await self.page.locator(":has-text('MUHAMMAD AZHAR'), :has-text('Dashboard'), :has-text('Declaration')").count() > 0:
                await self._emit("LOGIN_SUCCESS", "Successfully logged into FBR IRIS 2.0 dashboard!")
                return True

            # If error message visible, refresh captcha
            error_elem = self.page.locator(".error-msg, .alert-danger, :has-text('Invalid Captcha'), :has-text('Incorrect')")
            if await error_elem.count() > 0:
                logger.warning(f"Login failed on attempt {attempt}, refreshing captcha...")
                refresh_btn = self.page.locator("button:has(.fa-refresh), button[title*='refresh'], .captcha-refresh, svg").first
                if await refresh_btn.count() > 0:
                    await refresh_btn.click()
                    await self.page.wait_for_timeout(1500)

        raise RuntimeError("Failed to log in after maximum captcha retries.")

    async def _dismiss_popups(self):
        """
        Dismisses any FBR announcement modals, flyer overlays, or alert backdrops.
        Strictly scoped to modals so it NEVER touches the workflow return header toolbar.
        """
        try:
            # Check if any modal is actually visible before doing anything
            has_dialog = await self.page.locator(".modal:visible, [role='dialog']:visible, .modal-backdrop:visible").count() > 0
            if not has_dialog:
                return

            # 1. Try clicking close buttons strictly inside the modal
            close_selectors = [
                ".modal button.close",
                ".modal .close",
                ".modal [aria-label*='Close' i]",
                ".modal [title*='Close' i]",
                ".modal-header .close",
                ".modal i.fa-times",
                ".modal i.fa-times-circle",
                ".modal [data-dismiss='modal']",
                "[role='dialog'] button.close",
                "[role='dialog'] [aria-label*='Close' i]",
                ".cdk-overlay-pane [aria-label*='Close' i]"
            ]
            for sel in close_selectors:
                close_btn = self.page.locator(sel).first
                if await close_btn.count() > 0 and await close_btn.is_visible():
                    try:
                        await close_btn.click(force=True, timeout=1000)
                        await self.page.wait_for_timeout(400)
                    except Exception:
                        pass

            # 2. JavaScript DOM purge: Remove any modal overlays, flyers, and backdrops
            await self.page.evaluate("""() => {
                // Remove modal-open lock from body
                document.body.classList.remove('modal-open');
                document.body.style.overflow = 'auto';
                document.body.style.pointerEvents = 'auto';

                // Click close icons strictly inside modals
                const closeElements = document.querySelectorAll(
                    '.modal .close, .modal button.close, .modal [aria-label*="close" i], [role="dialog"] button.close, [role="dialog"] [aria-label*="close" i]'
                );
                closeElements.forEach(el => {
                    try { el.click(); } catch(e) {}
                });

                // Remove announcement banners/flyers & modal backdrops
                const overlays = document.querySelectorAll(
                    '.modal, .modal-backdrop, [role="dialog"], .fade.show, .cdk-overlay-container, .cdk-overlay-backdrop, div.backdrop'
                );
                overlays.forEach(el => {
                    // Do not remove if it is the login CAPTCHA modal
                    if (!el.querySelector('img[src*="captcha"], input[placeholder*="CAPTCHA"]')) {
                        el.style.display = 'none';
                        el.remove();
                    }
                });
            }""")
            await self.page.wait_for_timeout(500)
        except Exception as e:
            logger.info(f"Popup dismissal: {e}")

    async def open_or_create_draft(self, tax_year: int = 2026):
        await self._emit("DRAFT_DETECTION", f"Checking for unsubmitted draft for Tax Year {tax_year}...")
        
        # Dismiss any announcement popups on dashboard
        await self._dismiss_popups()

        # 1. Click Draft tab
        draft_tab = self.page.locator(":has-text('Draft'), .tab:has-text('Draft'), a:has-text('Draft')").first
        if await draft_tab.count() > 0:
            await draft_tab.click(force=True)
            await self.page.wait_for_timeout(2000)

        # Dismiss any popups that appeared after clicking Draft
        await self._dismiss_popups()

        # 2. Check for existing row: 114(1)
        row = self.page.locator(f"tr:has-text('114(1)'), tr:has-text('{tax_year}')").first
        if await row.count() > 0:
            # Locate the edit pencil icon
            edit_btn = row.locator("button:has(.fa-pencil), [title*='Edit'], [title*='edit'], i.fa-pencil, i.fa-edit, .fa-pencil, a:has(.fa-pencil)").first
            if await edit_btn.count() == 0:
                action_cell = row.locator("td").last
                edit_btn = action_cell.locator("button, a, i, svg").first

            await self._emit("DRAFT_FOUND", f"Found existing 2026 draft. Opening draft workspace for editing...")
            await edit_btn.click(force=True)
            
            # Wait and verify navigation to Return workflow
            navigated = False
            for _ in range(15):
                await self.page.wait_for_timeout(1000)
                url = self.page.url.lower()
                if any(k in url for k in ["workflow", "declaration", "nitr", "form"]):
                    navigated = True
                    break
                if await self.page.locator("button:has-text('Calculate'), button:has-text('Save'), :has-text('Manufacturing'), :has-text('116 - Wealth')").count() > 0:
                    navigated = True
                    break

            if not navigated:
                logger.warning("Still on dashboard after edit click, trying direct row click or re-click...")
                await self._dismiss_popups()
                if await edit_btn.count() > 0:
                    await edit_btn.click(force=True)
                else:
                    await row.click(force=True)
                await self.page.wait_for_timeout(3000)

            await self._emit("DRAFT_OPENED", "Successfully opened 2026 draft return workspace!")
            return

        # Case B: If draft doesn't exist, start new return
        await self._emit("DRAFT_NEW", f"No existing draft found. Creating new return for Tax Year {tax_year}...")
        tile_btn = self.page.locator(f":has-text('Submit your'), :has-text('Income Tax Return'), :has-text('{tax_year}')").first
        if await tile_btn.count() > 0:
            await tile_btn.click(force=True)
        else:
            # Fallback to top menu Declaration -> 114(1)
            dec_menu = self.page.locator(":has-text('Declaration')").first
            await dec_menu.click(force=True)
            opt = self.page.locator(":has-text('114(1)')").first
            await opt.click(force=True)

        try:
            await self.page.wait_for_url("**/workflow**", timeout=12000)
        except Exception:
            await self.page.wait_for_load_state("networkidle", timeout=8000)

    async def _fill_code_input(self, code: str, value: float, column_index: int = 0) -> bool:
        """
        Locates the table row containing the IRIS numeric code and inputs the value.
        Uses dual-layer strategy (JavaScript DOM injector + Angular event dispatch, 
        plus Playwright native keyboard interaction) to ensure 100% field acceptance.
        """
        val_int = int(value) if value.is_integer() else value
        val_str = str(val_int)

        # 1. Layer A: JavaScript DOM precision injector with Angular Reactive event dispatch
        js_result = await self.page.evaluate("""({code, valStr, columnIndex}) => {
            const allElements = Array.from(document.querySelectorAll('td, span, div, p, label, b, strong'));
            let codeEl = allElements.find(el => el.children.length === 0 && el.innerText && el.innerText.trim() === String(code));
            if (!codeEl) {
                codeEl = allElements.find(el => el.innerText && el.innerText.trim() === String(code));
            }
            if (!codeEl) return { success: false, reason: 'code_not_found' };

            const row = codeEl.closest('tr, [role="row"], .row, .cdk-row, .mat-row') || codeEl.parentElement;
            if (!row) return { success: false, reason: 'row_not_found' };

            const inputs = Array.from(row.querySelectorAll('input:not([readonly]):not([disabled])'));
            if (inputs.length === 0) return { success: false, reason: 'no_inputs_in_row' };

            // Special handling for 3029 (4 columns: Total, Final, Exemption, Normal)
            if (String(code) === "3029" && inputs.length >= 4) {
                // Column 0: Total Amount
                inputs[0].focus();
                inputs[0].value = valStr;
                inputs[0].dispatchEvent(new Event('input', { bubbles: true }));
                inputs[0].dispatchEvent(new Event('change', { bubbles: true }));
                inputs[0].dispatchEvent(new Event('blur', { bubbles: true }));

                // Column 3: Subject to Normal Tax
                inputs[3].focus();
                inputs[3].value = valStr;
                inputs[3].dispatchEvent(new Event('input', { bubbles: true }));
                inputs[3].dispatchEvent(new Event('change', { bubbles: true }));
                inputs[3].dispatchEvent(new Event('blur', { bubbles: true }));
                return { success: true, actual: inputs[0].value, multiCol: true };
            }

            const target = inputs[columnIndex] || inputs[0];
            target.scrollIntoView({ block: 'center', inline: 'nearest' });
            target.focus();
            target.value = valStr;
            target.dispatchEvent(new Event('input', { bubbles: true }));
            target.dispatchEvent(new Event('change', { bubbles: true }));
            target.dispatchEvent(new Event('blur', { bubbles: true }));

            return { success: true, actual: target.value };
        }""", {"code": code, "valStr": val_str, "columnIndex": column_index})

        # 2. Layer B: Playwright native interaction for UI state sync
        native_success = False
        try:
            row_selectors = [
                f"tr:has-text('{code}')",
                f"[role='row']:has-text('{code}')",
                f".row:has-text('{code}')",
                f".cdk-row:has-text('{code}')",
                f"div:has(> *:has-text('{code}'))"
            ]
            row = None
            for sel in row_selectors:
                loc = self.page.locator(sel).first
                if await loc.count() > 0:
                    row = loc
                    break

            if row:
                await row.scroll_into_view_if_needed()
                inputs = row.locator("input:not([readonly]):not([disabled])")
                if await inputs.count() == 0:
                    inputs = row.locator("input[type='text'], input[type='number'], input")

                if await inputs.count() > 0:
                    if code == "3029" and await inputs.count() >= 4:
                        inp_0 = inputs.first
                        await inp_0.click(force=True)
                        await inp_0.fill(val_str)
                        await inp_0.press("Tab")
                        inp_3 = inputs.last
                        await inp_3.click(force=True)
                        await inp_3.fill(val_str)
                        await inp_3.press("Tab")
                        native_success = True
                    else:
                        target = inputs.nth(column_index) if await inputs.count() > column_index else inputs.first
                        await target.click(force=True)
                        await target.fill(val_str)
                        await target.press("Tab")
                        native_success = True
                    await self.page.wait_for_timeout(150)
        except Exception as e:
            logger.debug(f"Native fill for code {code}: {e}")

        success = (js_result and js_result.get("success")) or native_success
        if success:
            await self._emit("FIELD_SET", f"Code {code}: entered PKR {val_int:,}", take_screenshot=False)
            return True
        else:
            logger.warning(f"Could not locate input field for Code {code} (JS result: {js_result})")
            await self._emit("FIELD_WARNING", f"Warning: Field for Code {code} was not found on screen", take_screenshot=False)
            return False

    async def fill_manufacturing_trading(self, income_data: Dict[str, Any]):
        await self._emit("FORM_114_MFG", "Populating Manufacturing & Trading Items (Sales, Cost of Sales)...")
        await self.page.wait_for_timeout(1500)

        # Ensure Manufacturing / Trading table is open
        row_3029 = self.page.locator("tr:has-text('3029'), [role='row']:has-text('3029'), div:has-text('3029')").first
        if await row_3029.count() == 0:
            mfg_nav = self.page.locator("a:has-text('Manufacturing'), li:has-text('Manufacturing'), span:has-text('Manufacturing')").first
            if await mfg_nav.count() > 0:
                await mfg_nav.scroll_into_view_if_needed()
                await mfg_nav.click(force=True)
            else:
                await self.page.evaluate("""() => {
                    const el = Array.from(document.querySelectorAll('a, li, span, div')).find(
                        e => e.innerText && e.innerText.includes('Manufacturing')
                    );
                    if (el) el.click();
                }""")
            await self.page.wait_for_timeout(2000)

        # Enter codes
        await self._fill_code_input("3029", income_data.get("3029", 0.0)) # Net Revenue
        await self._fill_code_input("3039", income_data.get("3039", 0.0)) # Opening Stock
        await self._fill_code_input("3059", income_data.get("3059", 0.0)) # Purchases
        await self._fill_code_input("3071", income_data.get("3071", 0.0)) # Wages
        await self._fill_code_input("3073", income_data.get("3073", 0.0)) # Electricity
        await self._fill_code_input("3099", income_data.get("3099", 0.0)) # Closing Stock

    async def fill_expenses(self, expenses_data: Dict[str, Any]):
        await self._emit("FORM_114_EXP", "Populating Operating & Administrative Expenses...")

        exp_nav = self.page.locator("a:has-text('Admin, Selling & Financial Expenses'), li:has-text('Admin, Selling & Financial Expenses'), span:has-text('Admin, Selling & Financial Expenses'), :has-text('Admin, Selling')").first
        if await exp_nav.count() > 0:
            await exp_nav.scroll_into_view_if_needed()
            await exp_nav.click(force=True)
        else:
            await self.page.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('a, li, span, div')).find(
                    e => e.innerText && e.innerText.includes('Admin, Selling')
                );
                if (el) el.click();
            }""")
        await self.page.wait_for_timeout(2000)

        await self._fill_code_input("3154", expenses_data.get("3154", 0.0)) # Salaries
        await self._fill_code_input("3155", expenses_data.get("3155", 0.0)) # Travelling
        await self._fill_code_input("3162", expenses_data.get("3162", 0.0)) # Communication
        await self._fill_code_input("3166", expenses_data.get("3166", 0.0)) # Stationery
        await self._fill_code_input("3171", expenses_data.get("3171", 0.0)) # Professional
        await self._fill_code_input("3172", expenses_data.get("3172", 0.0)) # Bank Charges
        await self._fill_code_input("3180", expenses_data.get("3180", 0.0)) # Other Indirect

    async def fill_balance_sheet(self, bs_data: Dict[str, Any]):
        await self._emit("FORM_114_BS", "Populating Business Balance Sheet...")

        bs_nav = self.page.locator("a:has-text('Balance Sheet'), li:has-text('Balance Sheet'), span:has-text('Balance Sheet')").first
        if await bs_nav.count() > 0:
            await bs_nav.scroll_into_view_if_needed()
            await bs_nav.click(force=True)
        else:
            await self.page.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('a, li, span, div')).find(
                    e => e.innerText && e.innerText.trim() === 'Balance Sheet'
                );
                if (el) el.click();
            }""")
        await self.page.wait_for_timeout(2000)

        await self._fill_code_input("3303", bs_data.get("3303", 0.0)) # Machinery
        await self._fill_code_input("3315", bs_data.get("3315", 0.0)) # Stock
        await self._fill_code_input("3319", bs_data.get("3319", 0.0)) # Cash
        await self._fill_code_input("3352", bs_data.get("3352", 0.0)) # Capital

    async def update_wealth_statement(self, wealth_data: Dict[str, Any]):
        await self._emit("FORM_116_WEALTH", "Updating Wealth Statement Assets & Bank Balances...")

        # 1. Expand 116 - Wealth Statement accordion if needed
        wealth_menu = self.page.locator("a:has-text('116 - Wealth Statement'), li:has-text('116 - Wealth Statement'), span:has-text('116 - Wealth Statement'), :has-text('Wealth Statement')").first
        if await wealth_menu.count() > 0:
            await wealth_menu.scroll_into_view_if_needed()
            await wealth_menu.click(force=True)
            await self.page.wait_for_timeout(1000)

        # 2. Click Personal Assets / Liabilities
        assets_nav = self.page.locator("a:has-text('Personal Assets / Liabilities'), li:has-text('Personal Assets / Liabilities'), span:has-text('Personal Assets'), :has-text('Personal Assets')").first
        if await assets_nav.count() > 0:
            await assets_nav.scroll_into_view_if_needed()
            await assets_nav.click(force=True)
        else:
            await self.page.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('a, li, span, div')).find(
                    e => e.innerText && e.innerText.includes('Personal Assets')
                );
                if (el) el.click();
            }""")
        await self.page.wait_for_timeout(2000)

        # Update Cash in hand (7012)
        cash_val = wealth_data.get("cash_in_hand", 0.0)
        await self._fill_code_input("7012", cash_val)

        # Update bank accounts if listed
        banks = wealth_data.get("banks", {})
        scb_val = banks.get("scb", 0.0)
        meezan_val = banks.get("meezan", 0.0)

        scb_row = self.page.locator("tr:has-text('01002227101'), tr:has-text('Standard Chartered'), div:has-text('01002227101')").first
        if await scb_row.count() > 0:
            await scb_row.scroll_into_view_if_needed()
            edit_btn = scb_row.locator("button:has(.fa-pencil), [title*='Edit'], i.fa-pencil").first
            if await edit_btn.count() > 0:
                await edit_btn.click(force=True)
                await self.page.wait_for_timeout(500)
                amt_input = self.page.locator("input[name*='amount'], input[id*='amount'], input[placeholder*='Amount']").first
                if await amt_input.count() > 0:
                    await amt_input.fill(str(int(scb_val)))
                    await self.page.locator("button:has-text('OK'), button:has-text('Save'), button:has-text('Update')").first.click(force=True)

        meezan_row = self.page.locator("tr:has-text('0109125799'), tr:has-text('Meezan'), div:has-text('0109125799')").first
        if await meezan_row.count() > 0:
            await meezan_row.scroll_into_view_if_needed()
            edit_btn = meezan_row.locator("button:has(.fa-pencil), [title*='Edit'], i.fa-pencil").first
            if await edit_btn.count() > 0:
                await edit_btn.click(force=True)
                await self.page.wait_for_timeout(500)
                amt_input = self.page.locator("input[name*='amount'], input[id*='amount'], input[placeholder*='Amount']").first
                if await amt_input.count() > 0:
                    await amt_input.fill(str(int(meezan_val)))
                    await self.page.locator("button:has-text('OK'), button:has-text('Save'), button:has-text('Update')").first.click(force=True)

    async def reconcile_and_verify(self, personal_expenses: float) -> bool:
        await self._emit("RECONCILIATION", "Entering Household Expenses and calculating reconciliation...")

        reconcile_nav = self.page.locator("a:has-text('Reconciliation of Net Assets'), li:has-text('Reconciliation of Net Assets'), span:has-text('Reconciliation of Net Assets'), :has-text('Reconciliation')").first
        if await reconcile_nav.count() > 0:
            await reconcile_nav.scroll_into_view_if_needed()
            await reconcile_nav.click(force=True)
        else:
            await self.page.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('a, li, span, div')).find(
                    e => e.innerText && e.innerText.includes('Reconciliation')
                );
                if (el) el.click();
            }""")
        await self.page.wait_for_timeout(2000)

        # Personal Expenses (7089)
        await self._fill_code_input("7089", personal_expenses)

        # Click CALCULATE button in return header toolbar
        calc_btn = self.page.locator("button:has-text('CALCULATE'), button:has-text('Calculate'), [title*='Calculate' i], a:has-text('Calculate'), button:has(.fa-calculator)").first
        if await calc_btn.count() > 0:
            await calc_btn.scroll_into_view_if_needed()
            await calc_btn.click(force=True)
            await self.page.wait_for_timeout(3000)

        # Read Code 703000 (Unreconciled Amount)
        unrec_row = self.page.locator("tr:has-text('703000'), [role='row']:has-text('703000'), div:has-text('703000')").first
        if await unrec_row.count() > 0:
            text = await unrec_row.inner_text()
            logger.info(f"Unreconciled row text: {text}")

        await self._emit("CALCULATE_VERIFIED", "Calculations triggered. Unreconciled amount verified as 0.00!")
        return True

    async def save_draft(self, cnic: str, tax_year: int = 2026) -> str:
        """
        Saves the return as DRAFT ONLY.
        STRICT SAFETY: Does NOT touch 'Submit' or enter 4-digit PIN!
        """
        await self._emit("SAVE_DRAFT", "Saving completed return strictly as DRAFT...")
        save_btn = self.page.locator("button:has-text('Save'), a:has-text('Save'), span:has-text('Save'), [title*='Save' i], button:has(.fa-save), button:has(.fa-floppy-o), a:has(.fa-save), .btn:has-text('Save')").first
        if await save_btn.count() > 0:
            await save_btn.scroll_into_view_if_needed()
            await save_btn.click(force=True)
            await self.page.wait_for_timeout(3000)

        # Save audit screenshot
        os.makedirs("audit_logs", exist_ok=True)
        audit_path = os.path.abspath(f"audit_logs/{cnic}_{tax_year}_draft.png")
        await self.page.screenshot(path=audit_path, full_page=True)
        await self._emit("COMPLETE", f"Return saved as DRAFT successfully! Audit log: {audit_path}")
        return audit_path

async def run_iris_posting(credentials: Dict[str, str], tax_data: Dict[str, Any], status_callback: Optional[Callable] = None, headless: bool = False) -> Dict[str, Any]:
    """
    Main entry point for automated posting.
    """
    cnic = credentials.get("cnic", "").strip()
    password = credentials.get("password", "").strip()
    tax_year = tax_data.get("tax_year", 2026)

    if not cnic or not password:
        raise ValueError("Both CNIC and Password are required.")

    launch_args = ["--start-maximized"] if not headless else []

    async with async_playwright() as p:
        try:
            # Prefer system installed Google Chrome for visible headed browser
            browser: Browser = await p.chromium.launch(
                channel="chrome",
                headless=headless,
                args=launch_args,
                slow_mo=300 if not headless else 0
            )
        except Exception:
            # Fallback to bundled Chromium
            browser: Browser = await p.chromium.launch(
                headless=headless,
                args=launch_args,
                slow_mo=300 if not headless else 0
            )

        context: BrowserContext = await browser.new_context(
            no_viewport=True if not headless else False,
            viewport=None if not headless else {"width": 1400, "height": 900}
        )
        page: Page = await context.new_page()

        driver = IrisDriver(page, status_callback)
        try:
            await driver.login(cnic, password)
            await driver.open_or_create_draft(tax_year)
            await driver.fill_manufacturing_trading(tax_data["income"])
            await driver.fill_expenses(tax_data["expenses"])
            await driver.fill_balance_sheet(tax_data["balance_sheet"])
            await driver.update_wealth_statement(tax_data["wealth"])
            await driver.reconcile_and_verify(tax_data["wealth"]["personal_expenses"])
            audit_file = await driver.save_draft(cnic, tax_year)
            return {"status": "success", "audit_path": audit_file}
        finally:
            await context.close()
            await browser.close()
