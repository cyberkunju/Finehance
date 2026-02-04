
import { test, expect } from '@playwright/test';

// Use a unique email every time or handle "already exists"
const UNIQUE_ID = Date.now();
const EMAIL = `browser_test_${UNIQUE_ID}@example.com`;
const PASSWORD = 'Password123!';

test('End-to-End Registration and Transaction Flow', async ({ page }) => {
    // Console logs
    page.on('console', msg => console.log(`BROWSER LOG: ${msg.text()}`));
    page.on('pageerror', err => console.log(`BROWSER ERROR: ${err}`));

    // 1. Navigate to Home
    console.log(`Navigating to http://localhost:5173...`);
    await page.goto('http://localhost:5173');
    // Wait for network to be idle to ensure redirection happens
    try {
        await page.waitForLoadState('networkidle', { timeout: 3000 });
    } catch (e) {
        console.log('Network idle timeout, proceeding...');
    }

    // 2. Register
    // Look for a link to register, might need to adjust selector based on UI
    // Assuming there's a "Register" or "Sign Up" link
    const registerLink = page.getByRole('link', { name: /register|sign up/i });

    // If we are already logged in (Dashboard check), logout first just in case?
    // But likely clean state.
    // Check title (relaxed check)
    await expect(page).toHaveTitle(/frontend|Finance|AI/i);

    // Try to find Register button, if not, maybe we are on login page
    if (await registerLink.count() > 0) {
        await registerLink.click();
    } else {
        // Maybe we are on login, look for "Don't have an account?" text?
        await page.getByText(/don't have an account/i).click();
    }

    console.log(`Registering user: ${EMAIL}`);
    await page.fill('input[name="firstName"]', 'Browser');
    await page.fill('input[name="lastName"]', 'Tester');
    await page.fill('input[name="email"]', EMAIL);
    await page.fill('input[name="password"]', PASSWORD);
    await page.fill('input[name="confirmPassword"]', PASSWORD);

    await page.getByRole('button', { name: /create account|register|sign up/i }).click();

    // 3. Verify Dashboard
    // Wait for URL to change or Dashboard element
    await expect(page).toHaveURL(/.*dashboard/i);
    await expect(page.getByText(/financial overview/i)).toBeVisible();
    console.log('✅ Registration successful, Dashboard loaded.');

    // 4. Create Transaction
    console.log('Navigating to Transactions...');
    await page.getByRole('link', { name: /transactions/i }).click();

    await page.getByRole('button', { name: /add transaction/i }).click();

    console.log('Creating transaction...');
    await page.fill('input[name="description"]', 'Playwright Test Transaction');
    await page.fill('input[name="amount"]', '50.00');

    // Select Type if needed (often a dropdown or radio)
    // Check for radio or select
    // E.g. Label "Expense"
    // await page.getByLabel(/type/i).selectOption('EXPENSE'); 
    // OR
    // await page.getByText('Expense').click(); 

    await page.getByRole('button', { name: /save|add|submit/i }).click();

    // 5. Verify in list
    await expect(page.getByText('Playwright Test Transaction')).toBeVisible();
    console.log('✅ Transaction created and visible in list.');
});
