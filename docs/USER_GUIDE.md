# Finehance — User Guide

## Welcome

Finehance is an AI-powered personal finance management platform. This guide covers all features available to end users.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Dashboard Overview](#dashboard-overview)
3. [Managing Transactions](#managing-transactions)
4. [Budget Management](#budget-management)
5. [Financial Goals](#financial-goals)
6. [AI-Powered Features](#ai-powered-features)
7. [Reports and Analytics](#reports-and-analytics)
8. [Import and Export](#import-and-export)
9. [Tips and Best Practices](#tips-and-best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Creating Your Account

1. Navigate to the registration page
2. Enter your email address
3. Create a strong password (minimum 12 characters with uppercase, lowercase, numbers, and special characters)
4. Fill in your first and last name
5. Click "Register"

### First Login

After registration, you'll be redirected to the login page:

1. Enter your email and password
2. Click "Login"
3. You'll be taken to your dashboard

### Initial Setup

When you first log in, your dashboard will be empty. Here's what to do:

1. **Add your first transaction** - Click "Transactions" in the sidebar
2. **Create a budget** - Click "Budgets" to set up your first monthly budget
3. **Set a financial goal** - Click "Goals" to define what you're saving for

---

## Dashboard Overview

Your dashboard is your financial command center. It displays:

### Key Metrics

- **Total Income**: Your income for the current month
- **Total Expenses**: Your spending for the current month
- **Net Savings**: Income minus expenses
- **Transaction Count**: Number of transactions this month

### Visual Charts

- **Expenses by Category**: Pie chart showing where your money goes
- **Income vs Expenses**: Bar chart comparing income and expenses

### Active Goals

- Progress bars for each of your financial goals
- Estimated completion dates
- Risk alerts if goals are off track

### Personalized Advice

- AI-generated recommendations based on your spending patterns
- Priority-ranked suggestions (High, Medium, Low)
- Actionable steps to improve your finances

---

## Managing Transactions

Transactions are the foundation of your financial tracking.

### Adding a Transaction

1. Click "Transactions" in the sidebar
2. Click the "+ Add Transaction" button
3. Fill in the details:
   - **Amount**: Enter the transaction amount
   - **Date**: Select the transaction date
   - **Description**: Describe the transaction (e.g., "Whole Foods Market")
   - **Type**: Choose "Income" or "Expense"
   - **Category**: Select a category or leave blank for auto-categorization
4. Click "Save"

**Pro Tip**: Leave the category blank and let our AI automatically categorize your transaction!

### Viewing Transactions

Your transaction list shows:
- Date
- Description
- Category
- Type (Income/Expense)
- Amount

Transactions are sorted by date (newest first).

### Filtering Transactions

Use the filter options to find specific transactions:

- **Search**: Type keywords to search descriptions
- **Category**: Filter by specific category
- **Type**: Show only income or expenses
- **Date Range**: Select start and end dates

Click "Clear Filters" to reset all filters.

### Editing a Transaction

1. Click the "Edit" button next to any transaction
2. Modify the fields you want to change
3. Click "Save"

**Note**: Editing a transaction will recalculate affected budgets and predictions.

### Deleting a Transaction

1. Click the "Delete" button next to any transaction
2. Confirm the deletion
3. The transaction will be removed and budgets/predictions will be updated

---

## Budget Management

Budgets help you plan and control your spending.

### Creating a Budget

1. Click "Budgets" in the sidebar
2. Click "+ Create Budget"
3. Fill in the details:
   - **Budget Name**: e.g., "January 2026 Budget"
   - **Period Start**: First day of the budget period
   - **Period End**: Last day of the budget period
4. Add category allocations:
   - Click "+ Add Category"
   - Select a category
   - Enter the budgeted amount
   - Repeat for all categories
5. Click "Create Budget"

### Viewing Budget Progress

Your budget page shows:

- **Progress Bars**: Visual representation of spending vs budget
- **Status Indicators**:
  - Green: Under budget
  - Yellow: Approaching limit (80-100%)
  - Red: Over budget
- **Remaining Amount**: How much you have left in each category
- **Percentage Used**: Spending as a percentage of budget

### Budget Alerts

You'll see alerts when:
- You're approaching your budget limit (80%)
- You've exceeded your budget (100%+)
- Spending patterns suggest you'll exceed your budget

### Budget Optimization

Our AI can suggest budget improvements:

1. Click "Get Optimization Suggestions"
2. Review the suggested reallocations
3. Each suggestion includes:
   - Current allocation
   - Suggested allocation
   - Reason for the change
   - Confidence score
4. Click "Apply Suggestions" to update your budget

**How it works**: The AI analyzes your spending patterns over the past 3-6 months and identifies categories where you consistently over or underspend.

---

## Financial Goals

Set and track your financial objectives.

### Creating a Goal

1. Click "Goals" in the sidebar
2. Click "+ Create Goal"
3. Fill in the details:
   - **Goal Name**: e.g., "Emergency Fund"
   - **Target Amount**: Your goal amount
   - **Current Amount**: How much you've saved so far
   - **Deadline**: When you want to achieve this goal
   - **Category**: Optional category to link transactions
4. Click "Create Goal"

### Tracking Progress

For each goal, you'll see:

- **Progress Bar**: Visual representation of progress
- **Percentage Complete**: Current amount / target amount
- **Days Remaining**: Time until deadline
- **Estimated Completion**: Projected completion date based on current progress

### Goal Status

Goals can have three statuses:

- **Active**: Currently working towards this goal
- **Achieved**: Goal has been reached
- **Archived**: Goal is no longer active

### Risk Alerts

You'll receive alerts when:
- Your progress is too slow to meet the deadline
- You're at risk of not achieving the goal
- Recommended actions to get back on track

### Updating Progress

Progress updates automatically when:
- You add transactions in the linked category
- You manually update the current amount

To manually update:
1. Click "Update Progress" on the goal
2. Enter the new current amount
3. Click "Save"

---

## AI-Powered Features

### Automatic Categorization

When you add a transaction without specifying a category:

1. Our AI analyzes the description
2. It assigns the most likely category
3. A confidence score is provided (0-100%)

**Learning from Corrections**:
- If you change a category, the AI learns from your correction
- Future similar transactions will be categorized more accurately
- After 50+ transactions, you'll have a personalized model

### Expense Predictions

View forecasts for your future spending:

1. Click "Predictions" in the sidebar (or view on dashboard)
2. See predictions for 30, 60, or 90 days
3. Each prediction includes:
   - Predicted amount
   - Confidence interval (range)
   - Trend (increasing/decreasing/stable)

**How it works**: The AI uses ARIMA time series analysis to forecast expenses based on your historical patterns.

### Personalized Advice

Get AI-generated financial recommendations:

1. View advice cards on your dashboard
2. Each advice includes:
   - Title and description
   - Priority level (High/Medium/Low)
   - Actionable steps
   - Potential savings

**Types of Advice**:
- Budget overspending warnings
- Savings opportunities
- Goal progress updates
- Spending pattern insights

---

## Reports and Analytics

Generate comprehensive financial reports.

### Generating a Report

1. Click "Reports" in the sidebar
2. Select the "Generate Reports" tab
3. Choose your date range:
   - Start date
   - End date
4. Click "Generate Report"

### Report Contents

Your report includes:

**Summary Section**:
- Total income
- Total expenses
- Net savings
- Savings rate

**Income Breakdown**:
- Income by category
- Percentage of total income

**Expense Breakdown**:
- Expenses by category
- Percentage of total expenses

**Budget Adherence**:
- Budgeted vs actual for each category
- Variance analysis

**Spending Patterns**:
- Trends over time
- Significant changes highlighted

### Exporting Reports

Export your report in multiple formats:

1. Click "Export to PDF" for a formatted document
2. Click "Export to CSV" for spreadsheet analysis

**Use Cases**:
- Tax preparation
- Financial planning
- Sharing with advisors
- Personal record keeping

---

## Import and Export

### Importing Transactions

Bulk import transactions from bank statements:

1. Click "Reports" in the sidebar
2. Select the "Import Transactions" tab
3. Click "Choose File" or drag and drop
4. Select your CSV or XLSX file
5. Click "Import"

**Supported Formats**:
- CSV (Comma-Separated Values)
- XLSX (Excel)

**Required Columns**:
- Date (MM/DD/YYYY, DD/MM/YYYY, or YYYY-MM-DD)
- Description
- Amount (positive for income, negative for expenses)

**Optional Columns**:
- Type (INCOME or EXPENSE)
- Category (will auto-categorize if omitted)

### Download Template

Not sure about the format? Download a template:

1. Click "Download CSV Template" or "Download XLSX Template"
2. Fill in your transactions
3. Import the completed file

### Exporting Transactions

Export your transaction data:

1. Click "Reports" in the sidebar
2. Select the "Export Transactions" tab
3. Choose filters (optional):
   - Date range
   - Category
   - Type
4. Click "Export to CSV"

**Use Cases**:
- Backup your data
- Analyze in Excel/Google Sheets
- Share with accountant
- Switch to another platform

---

## Tips and Best Practices

### Getting the Most from AI Features

1. **Add Detailed Descriptions**: The more descriptive your transaction descriptions, the better the AI categorization
2. **Correct Categories**: When the AI gets it wrong, correct it - this improves future predictions
3. **Regular Updates**: Add transactions regularly for more accurate predictions
4. **Sufficient History**: The AI works best with at least 3 months of transaction history

### Budget Management Tips

1. **Start Conservative**: Set realistic budgets based on past spending
2. **Review Monthly**: Check budget progress weekly
3. **Use Optimization**: Let the AI suggest improvements after 2-3 months
4. **Track Trends**: Look for patterns in overspending categories

### Goal Setting Best Practices

1. **Be Specific**: Set clear, measurable goals
2. **Set Deadlines**: Goals with deadlines are more likely to be achieved
3. **Start Small**: Begin with achievable goals to build momentum
4. **Link Categories**: Connect goals to spending categories for automatic tracking

### Data Entry Efficiency

1. **Use Import**: Bulk import bank statements instead of manual entry
2. **Mobile Access**: Add transactions on-the-go (when mobile app is available)
3. **Batch Entry**: Set aside time weekly to enter multiple transactions
4. **Auto-Categorization**: Let the AI handle categorization to save time

---

## Troubleshooting

### Login Issues

**Problem**: Can't log in
**Solutions**:
- Verify your email and password are correct
- Check if Caps Lock is on
- Try resetting your password
- Clear browser cache and cookies

### Transaction Not Appearing

**Problem**: Added transaction doesn't show up
**Solutions**:
- Refresh the page
- Check if filters are hiding the transaction
- Verify the transaction date is within the visible range

### Budget Not Updating

**Problem**: Budget progress not reflecting new transactions
**Solutions**:
- Refresh the page
- Verify transaction category matches budget category
- Check transaction date is within budget period

### Import Errors

**Problem**: File import fails
**Solutions**:
- Verify file format (CSV or XLSX)
- Check required columns are present
- Ensure dates are in correct format
- Download and use the template
- Check for special characters in descriptions

### Predictions Not Available

**Problem**: Can't see expense predictions
**Solutions**:
- Ensure you have at least 3 months of transaction history
- Verify you have transactions in multiple categories
- Check that transactions have dates in the past

### AI Categorization Inaccurate

**Problem**: Categories are frequently wrong
**Solutions**:
- Correct the categories when wrong (AI learns from this)
- Add more detailed transaction descriptions
- Wait for more transaction history (50+ transactions)
- Manually categorize ambiguous transactions

---

## Security and Privacy

### Your Data is Secure

- All passwords are hashed using bcrypt
- Sensitive data is encrypted at rest (AES-256)
- JWT authentication with token blacklisting
- We never share your data with third parties

### Best Practices

1. **Strong Password**: Use a unique, complex password
2. **Regular Logout**: Log out when using shared computers
3. **Monitor Activity**: Review your transactions regularly
4. **Report Issues**: Contact support if you notice suspicious activity

---

## Getting Help

### Support Resources

- **API Docs**: `http://localhost:8000/docs` (Swagger UI, when backend is running)
- **GitHub Issues**: [github.com/cyberkunju/Finehance/issues](https://github.com/cyberkunju/Finehance/issues)
- **Project Documentation**: See `docs/` directory in the repository

### Providing Feedback

We welcome contributions and feedback:

- Feature requests
- Bug reports
- Usability suggestions

Submit feedback via [GitHub Issues](https://github.com/cyberkunju/Finehance/issues).

---

## Conclusion

You're now ready to take control of your finances with Finehance. Remember:

- Start by adding transactions regularly
- Create budgets to plan your spending
- Set goals to work towards
- Let the AI help you make better financial decisions

---

**Version**: 1.0.0  
**Last Updated**: February 6, 2026
