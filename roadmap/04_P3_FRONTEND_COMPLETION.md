# Phase 3 — Frontend Completion

> **Can run in parallel with P2 and P4 after P0 is done**  
> **Estimated Effort:** 5-7 days  
> **Covers:** Reusable components, design system, error handling, form validation, UX polish, accessibility

---

## Current State

| What Exists | Status |
|-------------|--------|
| React 19 + TypeScript + Vite | Working |
| React Router 7 with protected routes | Working |
| Auth flow (login, register, token refresh) | Working |
| TanStack Query for data fetching | Working |
| 7 pages (Dashboard, Transactions, Budgets, Goals, Reports, Login, Register) | Working but monolithic |
| Chart.js integration | Working |
| **Only 2 components** (Layout, ThemeToggle) | Everything else is inline in pages |
| No error boundaries | App crashes on any uncaught error |
| No toast/notification system | No feedback for actions |
| No form validation library | Inline validation only |
| No loading skeletons | Empty screen while loading |
| No component library | Raw CSS per page |
| Playwright in devDeps | No actual test files |

---

## Task 3.1 — Create Reusable Component Library

### Problem
All UI is built monolithically inside page files. No reusable components exist for common patterns like data tables, forms, modals, cards, buttons, alerts.

### What To Do

Create the following components in `frontend/src/components/`:

#### 3.1.1 — `DataTable.tsx`
Reusable table with sorting, pagination, loading state:

```typescript
interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  loading?: boolean;
  pagination?: {
    page: number;
    pageSize: number;
    total: number;
    onPageChange: (page: number) => void;
  };
  onSort?: (column: string, direction: 'asc' | 'desc') => void;
  emptyMessage?: string;
  onRowClick?: (item: T) => void;
}

interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  sortable?: boolean;
  width?: string;
}
```

Use in: TransactionsPage, BudgetsPage, GoalsPage, ReportsPage

#### 3.1.2 — `FormField.tsx`
Reusable form field with label, validation, error display:

```typescript
interface FormFieldProps {
  label: string;
  name: string;
  type?: 'text' | 'email' | 'password' | 'number' | 'date' | 'select' | 'textarea';
  value: string | number;
  onChange: (value: string) => void;
  error?: string;
  required?: boolean;
  placeholder?: string;
  options?: { label: string; value: string }[];  // For select type
  disabled?: boolean;
  helpText?: string;
}
```

Use in: LoginPage, RegisterPage, all create/edit forms

#### 3.1.3 — `Modal.tsx`
Reusable modal dialog:

```typescript
interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
}
```

Use in: Confirmation dialogs, edit forms, detail views

#### 3.1.4 — `Card.tsx`
Content card with header, body, optional actions:

```typescript
interface CardProps {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  loading?: boolean;
}
```

Use in: DashboardPage (stats cards, chart cards), GoalsPage (goal cards)

#### 3.1.5 — `Button.tsx`
Consistent button with variants:

```typescript
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: React.ReactNode;
}
```

#### 3.1.6 — `Alert.tsx`
Status alerts:

```typescript
interface AlertProps {
  type: 'success' | 'error' | 'warning' | 'info';
  title?: string;
  message: string;
  dismissible?: boolean;
  onDismiss?: () => void;
}
```

#### 3.1.7 — `LoadingSkeleton.tsx`
Content placeholder while loading:

```typescript
interface SkeletonProps {
  variant?: 'text' | 'card' | 'table' | 'chart';
  rows?: number;
  width?: string;
  height?: string;
}
```

#### 3.1.8 — `EmptyState.tsx`
Empty state with icon and action:

```typescript
interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}
```

#### 3.1.9 — `Badge.tsx`
Status badges:

```typescript
interface BadgeProps {
  variant: 'success' | 'warning' | 'error' | 'info' | 'neutral';
  children: React.ReactNode;
  size?: 'sm' | 'md';
}
```

Use for: transaction categories, goal status, budget alerts

#### 3.1.10 — `ConfirmDialog.tsx`
Confirmation dialog wrapping Modal:

```typescript
interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'warning' | 'default';
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}
```

Use for: delete confirmations, apply optimizations

---

## Task 3.2 — Add Error Boundary

### Problem
No error boundary exists. Any uncaught error in any component crashes the entire app with a white screen.

### What To Do

**Create `frontend/src/components/ErrorBoundary.tsx`:**

```typescript
import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
    // TODO: Send to error tracking service (Sentry)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="error-boundary">
          <h2>Something went wrong</h2>
          <p>An unexpected error occurred. Please try refreshing the page.</p>
          <button onClick={() => this.setState({ hasError: false, error: null })}>
            Try Again
          </button>
          {import.meta.env.DEV && (
            <pre>{this.state.error?.message}</pre>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
```

**Wrap in `App.tsx`:**

```typescript
<ErrorBoundary>
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <ThemeProvider>
        <BrowserRouter>
          <Routes>...</Routes>
        </BrowserRouter>
      </ThemeProvider>
    </AuthProvider>
  </QueryClientProvider>
</ErrorBoundary>
```

Also wrap individual pages for granular error recovery:

```typescript
<Route path="/transactions" element={
  <ErrorBoundary fallback={<div>Failed to load transactions</div>}>
    <TransactionsPage />
  </ErrorBoundary>
} />
```

---

## Task 3.3 — Add Toast/Notification System

### Problem
No user feedback for actions (create, update, delete). Users don't know if actions succeeded or failed.

### What To Do

**Create `frontend/src/components/Toast.tsx` + `frontend/src/contexts/ToastContext.tsx`:**

```typescript
// ToastContext.tsx
interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number; // ms, default 5000
}

interface ToastContextType {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
}

// Usage in pages:
const { addToast } = useToast();

const handleDelete = async () => {
  try {
    await deleteTransaction(id);
    addToast({ type: 'success', title: 'Transaction deleted' });
  } catch {
    addToast({ type: 'error', title: 'Failed to delete transaction' });
  }
};
```

**Create `frontend/src/components/ToastContainer.tsx`:**
- Fixed position top-right
- Auto-dismiss after duration
- Slide-in animation
- Close button

---

## Task 3.4 — Add Form Validation

### Problem
No form validation library. Validation is done inline with ad-hoc state management.

### What To Do

**Create `frontend/src/hooks/useForm.ts`** — a lightweight form hook:

```typescript
interface UseFormOptions<T> {
  initialValues: T;
  validate: (values: T) => Partial<Record<keyof T, string>>;
  onSubmit: (values: T) => Promise<void>;
}

interface UseFormReturn<T> {
  values: T;
  errors: Partial<Record<keyof T, string>>;
  touched: Partial<Record<keyof T, boolean>>;
  isSubmitting: boolean;
  handleChange: (field: keyof T, value: any) => void;
  handleBlur: (field: keyof T) => void;
  handleSubmit: (e: React.FormEvent) => void;
  reset: () => void;
  isValid: boolean;
}

export function useForm<T extends Record<string, any>>(
  options: UseFormOptions<T>
): UseFormReturn<T> {
  // Implementation with validation on blur and submit
  // Track touched fields to only show errors after interaction
  // Disable submit during async submission
}
```

**Usage example:**

```typescript
const form = useForm({
  initialValues: { amount: '', description: '', category: '' },
  validate: (values) => {
    const errors: Record<string, string> = {};
    if (!values.amount || Number(values.amount) <= 0) errors.amount = 'Amount must be positive';
    if (!values.description) errors.description = 'Description is required';
    return errors;
  },
  onSubmit: async (values) => {
    await createTransaction(values);
    addToast({ type: 'success', title: 'Transaction created' });
  },
});

return (
  <form onSubmit={form.handleSubmit}>
    <FormField
      label="Amount"
      name="amount"
      type="number"
      value={form.values.amount}
      onChange={(v) => form.handleChange('amount', v)}
      onBlur={() => form.handleBlur('amount')}
      error={form.touched.amount ? form.errors.amount : undefined}
      required
    />
    <Button type="submit" loading={form.isSubmitting} disabled={!form.isValid}>
      Create
    </Button>
  </form>
);
```

---

## Task 3.5 — Create Design System / CSS Variables

### Problem
Each page has its own CSS file with duplicated styles. No consistency in colors, spacing, typography, borders.

### What To Do

**Create `frontend/src/styles/variables.css`:**

```css
:root {
  /* Colors */
  --color-primary: #4f46e5;
  --color-primary-hover: #4338ca;
  --color-primary-light: #eef2ff;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --color-info: #3b82f6;
  
  /* Neutrals */
  --color-bg: #ffffff;
  --color-bg-secondary: #f9fafb;
  --color-bg-tertiary: #f3f4f6;
  --color-text: #111827;
  --color-text-secondary: #6b7280;
  --color-text-muted: #9ca3af;
  --color-border: #e5e7eb;
  --color-border-focus: #4f46e5;
  
  /* Spacing */
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2rem;
  --space-2xl: 3rem;
  
  /* Typography */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-lg: 1.125rem;
  --text-xl: 1.25rem;
  --text-2xl: 1.5rem;
  --text-3xl: 1.875rem;
  
  /* Borders */
  --radius-sm: 0.25rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-full: 9999px;
  
  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  
  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;
}

[data-theme="dark"] {
  --color-bg: #111827;
  --color-bg-secondary: #1f2937;
  --color-bg-tertiary: #374151;
  --color-text: #f9fafb;
  --color-text-secondary: #d1d5db;
  --color-text-muted: #9ca3af;
  --color-border: #374151;
}
```

**Create `frontend/src/styles/global.css`:**
```css
@import './variables.css';

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: var(--font-sans);
  color: var(--color-text);
  background-color: var(--color-bg);
  line-height: 1.6;
}

/* Base focus styles for accessibility */
:focus-visible {
  outline: 2px solid var(--color-border-focus);
  outline-offset: 2px;
}
```

**Import in `main.tsx`:**

```typescript
import './styles/global.css';
```

**Refactor all existing CSS files** to use variables instead of hardcoded values.

---

## Task 3.6 — Enhance All Pages

### 3.6.1 — DashboardPage
**Current:** Monolithic page with inline charts.  
**Enhance:**
- Use `Card` component for each stat/chart section
- Add `LoadingSkeleton` while TanStack Query loads
- Add period selector (last 7 days, 30 days, 3 months, all time)
- Show spending alerts from `/api/advice/spending-alerts`
- Show goal progress summaries
- Add "Quick Actions" strip (Add Transaction, Create Budget, etc.)

### 3.6.2 — TransactionsPage
**Current:** Monolithic list.  
**Enhance:**
- Use `DataTable` with sorting and pagination
- Add `Modal` for create/edit forms using `FormField`
- Add `ConfirmDialog` for delete
- Add `Badge` for category display
- Add `EmptyState` when no transactions
- Add bulk actions (select multiple → delete/categorize)
- Add search/filter bar with category dropdown, date range, type toggle

### 3.6.3 — BudgetsPage
**Current:** Monolithic list.  
**Enhance:**
- Use `Card` for each budget with progress bar showing spent/allocated
- Color-code progress: green (<80%), yellow (80-100%), red (>100%)
- Use `Modal` for create/edit
- Show optimization suggestions inline with "Apply" button + `ConfirmDialog`
- Add `EmptyState` for no budgets

### 3.6.4 — GoalsPage
**Current:** Monolithic list.  
**Enhance:**
- Use `Card` for each goal with visual progress ring/bar
- Show days remaining, projected completion date
- Risk `Badge` (on track, at risk, behind, completed)
- Quick "Add Progress" button on each card
- Use timeline/history component for goal progress over time

### 3.6.5 — ReportsPage
**Current:** Monolithic page.  
**Enhance:**
- Date range picker for report period
- Tabbed view (Overview, Income/Expenses, Budget Adherence, Trends)
- Export buttons (CSV, PDF) with proper download handling
- Charts: spending by category (pie/donut), income vs expenses over time (line), budget adherence (bar)

### 3.6.6 — LoginPage / RegisterPage
**Current:** Basic forms.  
**Enhance:**
- Use `FormField` with validation
- Show password strength indicator on register
- Show/hide password toggle
- "Remember me" checkbox
- Error messages via `Alert` component
- Loading state on submit via `Button` loading prop

---

## Task 3.7 — Add Custom Hooks

**Create `frontend/src/hooks/`:**

### `useDebounce.ts`
```typescript
export function useDebounce<T>(value: T, delay: number): T {
  // Debounce search inputs, filter changes
}
```

### `useLocalStorage.ts`
```typescript
export function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T) => void] {
  // Persist UI preferences (page size, sort order)
}
```

### `usePagination.ts`
```typescript
export function usePagination(total: number, pageSize: number) {
  // Pagination logic for DataTable
  return { page, setPage, totalPages, hasNext, hasPrev, pageRange };
}
```

### `useMediaQuery.ts`
```typescript
export function useMediaQuery(query: string): boolean {
  // Responsive breakpoint detection
}
```

---

## Task 3.8 — Add Accessibility (a11y)

### What To Do
- All interactive elements must have `aria-label` when text isn't visible
- `Modal` must trap focus and be dismissible with `Escape`
- Color contrast ratios must meet WCAG AA (4.5:1 for text, 3:1 for large text)
- `DataTable` must use proper `<th scope="col">` markup
- `Alert` must use `role="alert"` and `aria-live="polite"`
- All form fields must have associated `<label>` elements
- Skip navigation link for keyboard users
- Focus management when modals open/close

### Testing
Install `axe-core` or use Chrome DevTools Lighthouse accessibility audit. Target: 90+ accessibility score.

---

## Task 3.9 — Add API Error Handling in Services

### Problem
API calls in `frontend/src/api/` catch errors inconsistently. Some return the error, some throw, some silently fail.

### What To Do

**Create `frontend/src/api/errors.ts`:**

```typescript
export class ApiError extends Error {
  constructor(
    public statusCode: number,
    public detail: string,
    public field?: string,
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

export function handleApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status ?? 500;
    const detail = error.response?.data?.detail ?? 'An unexpected error occurred';
    return new ApiError(status, detail);
  }
  return new ApiError(500, 'Network error. Please check your connection.');
}
```

**Use in all API functions:**

```typescript
export async function createTransaction(data: TransactionCreate): Promise<Transaction> {
  try {
    const response = await client.post('/api/transactions', data);
    return response.data;
  } catch (error) {
    throw handleApiError(error);
  }
}
```

**Use in pages with toasts:**

```typescript
const mutation = useMutation({
  mutationFn: createTransaction,
  onSuccess: () => {
    addToast({ type: 'success', title: 'Transaction created!' });
    queryClient.invalidateQueries({ queryKey: ['transactions'] });
  },
  onError: (error: ApiError) => {
    addToast({ type: 'error', title: 'Failed to create transaction', message: error.detail });
  },
});
```

---

## Task 3.10 — Add Missing Pages/Features

### 3.10.1 — Profile/Settings Page
```
Route: /settings
Features:
- View/edit profile (full name, email)
- Change password
- Theme preference (already exists via ThemeToggle, but needs a proper settings page)
- Notification preferences (future)
```

### 3.10.2 — AI Chat Page
```
Route: /ai-chat
Features:
- Chat interface with message bubbles
- Send financial questions to /api/ai/chat
- Display AI responses with formatting
- Show confidence indicators
- Display financial disclaimers
```

### 3.10.3 — Import/Export Page
```
Route: /import
Features:
- File upload dropzone (drag & drop)
- Preview imported data before confirming
- Download template button
- Export existing transactions with filters
```

---

## Granular Checklist — Task 3.1 (Component Library)

### 3.1.1 — DataTable
- [ ] Create `frontend/src/components/DataTable.tsx`
- [ ] Define `DataTableProps<T>` interface (data, columns, loading, pagination, onSort, emptyMessage, onRowClick)
- [ ] Define `Column<T>` interface (key, header, render, sortable, width)
- [ ] Implement column header rendering with sort indicators
- [ ] Implement row rendering with custom render functions
- [ ] Implement pagination controls (prev, next, page numbers)
- [ ] Implement loading state (show skeleton rows)
- [ ] Implement empty state (show `emptyMessage`)
- [ ] Add proper `<th scope="col">` for accessibility
- [ ] Style with CSS variables from design system

### 3.1.2 — FormField
- [ ] Create `frontend/src/components/FormField.tsx`
- [ ] Define `FormFieldProps` interface (label, name, type, value, onChange, error, required, placeholder, options, disabled, helpText)
- [ ] Support types: text, email, password, number, date, select, textarea
- [ ] Render label with `<label htmlFor>` association
- [ ] Render error message below field when present
- [ ] Render help text below field
- [ ] Render required asterisk on label
- [ ] Add `aria-invalid` when error present
- [ ] Add `aria-describedby` linking to error/help text
- [ ] Style error state with red border

### 3.1.3 — Modal
- [ ] Create `frontend/src/components/Modal.tsx`
- [ ] Define `ModalProps` interface (isOpen, onClose, title, children, footer, size)
- [ ] Implement backdrop overlay (click to close)
- [ ] Implement close button (X icon)
- [ ] Implement focus trapping (tab stays inside modal)
- [ ] Implement Escape key to close
- [ ] Implement body scroll lock when open
- [ ] Add `role="dialog"` and `aria-modal="true"`
- [ ] Add `aria-labelledby` pointing to title
- [ ] Support sizes: sm, md, lg
- [ ] Animate open/close (fade + slide)

### 3.1.4 — Card
- [ ] Create `frontend/src/components/Card.tsx`
- [ ] Define `CardProps` interface (title, subtitle, children, actions, className, loading)
- [ ] Render header section with title and subtitle
- [ ] Render body section with children
- [ ] Render actions section (top-right of header)
- [ ] Show loading skeleton when `loading=true`
- [ ] Style with shadow, border-radius, padding from design system

### 3.1.5 — Button
- [ ] Create `frontend/src/components/Button.tsx`
- [ ] Define `ButtonProps` interface (extends HTMLButtonAttributes + variant, size, loading, icon)
- [ ] Support variants: primary, secondary, danger, ghost
- [ ] Support sizes: sm, md, lg
- [ ] Show spinner when `loading=true`
- [ ] Disable button when loading
- [ ] Render icon before text if provided
- [ ] Add focus-visible styles for keyboard nav

### 3.1.6 — Alert
- [ ] Create `frontend/src/components/Alert.tsx`
- [ ] Define `AlertProps` interface (type, title, message, dismissible, onDismiss)
- [ ] Support types: success, error, warning, info
- [ ] Show icon per type (checkmark, X, warning, info)
- [ ] Show dismiss button when `dismissible=true`
- [ ] Add `role="alert"` and `aria-live="polite"`
- [ ] Style with appropriate background/border colors per type

### 3.1.7 — LoadingSkeleton
- [ ] Create `frontend/src/components/LoadingSkeleton.tsx`
- [ ] Define `SkeletonProps` interface (variant, rows, width, height)
- [ ] Support variants: text, card, table, chart
- [ ] Text variant: animated gray bars
- [ ] Card variant: header + body placeholders
- [ ] Table variant: multiple rows of bars
- [ ] Chart variant: rectangular placeholder
- [ ] Add shimmer animation (CSS keyframes)

### 3.1.8 — EmptyState
- [ ] Create `frontend/src/components/EmptyState.tsx`
- [ ] Define `EmptyStateProps` interface (icon, title, description, action)
- [ ] Render centered layout with icon, title, description
- [ ] Render action button if provided
- [ ] Style with muted colors and centered alignment

### 3.1.9 — Badge
- [ ] Create `frontend/src/components/Badge.tsx`
- [ ] Define `BadgeProps` interface (variant, children, size)
- [ ] Support variants: success, warning, error, info, neutral
- [ ] Support sizes: sm, md
- [ ] Style with pill shape and variant-specific colors

### 3.1.10 — ConfirmDialog
- [ ] Create `frontend/src/components/ConfirmDialog.tsx`
- [ ] Define `ConfirmDialogProps` interface (isOpen, title, message, confirmLabel, cancelLabel, variant, onConfirm, onCancel, loading)
- [ ] Use Modal component internally
- [ ] Render message text
- [ ] Render cancel and confirm buttons
- [ ] Support variant: danger (red confirm button), warning, default
- [ ] Show loading state on confirm button
- [ ] Focus confirm button on open

---

## Granular Checklist — Task 3.2 (Error Boundary)

- [ ] Create `frontend/src/components/ErrorBoundary.tsx`
- [ ] Implement as class component with `getDerivedStateFromError`
- [ ] Implement `componentDidCatch` — log error to console
- [ ] Render fallback UI with "Something went wrong" message
- [ ] Add "Try Again" button that resets error state
- [ ] Show error details in dev mode only (`import.meta.env.DEV`)
- [ ] Accept custom `fallback` prop
- [ ] Open `App.tsx`
- [ ] Wrap entire app with `<ErrorBoundary>`
- [ ] Wrap DashboardPage route with individual ErrorBoundary
- [ ] Wrap TransactionsPage route with individual ErrorBoundary
- [ ] Wrap BudgetsPage route with individual ErrorBoundary
- [ ] Wrap GoalsPage route with individual ErrorBoundary
- [ ] Wrap ReportsPage route with individual ErrorBoundary

---

## Granular Checklist — Task 3.3 (Toast System)

- [ ] Create `frontend/src/contexts/ToastContext.tsx`
- [ ] Define `Toast` interface (id, type, title, message, duration)
- [ ] Define `ToastContextType` (toasts, addToast, removeToast)
- [ ] Implement `ToastProvider` with state management
- [ ] Generate unique IDs for each toast
- [ ] Auto-dismiss toasts after duration (default 5000ms)
- [ ] Export `useToast()` hook
- [ ] Create `frontend/src/components/ToastContainer.tsx`
- [ ] Render toasts in fixed position (top-right)
- [ ] Add slide-in animation for new toasts
- [ ] Add close button on each toast
- [ ] Style with variant-specific colors (success=green, error=red, etc.)
- [ ] Wrap app with `<ToastProvider>` in `App.tsx`

---

## Granular Checklist — Task 3.4 (Form Validation Hook)

- [ ] Create `frontend/src/hooks/useForm.ts`
- [ ] Define `UseFormOptions<T>` interface (initialValues, validate, onSubmit)
- [ ] Define `UseFormReturn<T>` interface (values, errors, touched, isSubmitting, handleChange, handleBlur, handleSubmit, reset, isValid)
- [ ] Implement `values` state with `useState`
- [ ] Implement `errors` — run `validate()` on values
- [ ] Implement `touched` tracking — mark field as touched on blur
- [ ] Implement `handleChange` — update value for field
- [ ] Implement `handleBlur` — mark field as touched
- [ ] Implement `handleSubmit` — validate all, call `onSubmit` if no errors
- [ ] Implement `isSubmitting` flag — true during async submit
- [ ] Implement `reset` — restore to `initialValues`
- [ ] Implement `isValid` computed — `Object.keys(errors).length === 0`
- [ ] Only show errors for touched fields (UX improvement)

---

## Granular Checklist — Task 3.5 (Design System)

- [ ] Create `frontend/src/styles/variables.css`
- [ ] Define color palette — primary, success, warning, error, info
- [ ] Define neutral colors — bg, bg-secondary, text, text-secondary, border
- [ ] Define spacing scale — xs, sm, md, lg, xl, 2xl
- [ ] Define typography scale — text-xs through text-3xl
- [ ] Define font families — sans, mono
- [ ] Define border radius — sm, md, lg, full
- [ ] Define shadows — sm, md, lg
- [ ] Define transitions — fast (150ms), normal (250ms)
- [ ] Add `[data-theme="dark"]` overrides for all colors
- [ ] Create `frontend/src/styles/global.css`
- [ ] Add CSS reset (`box-sizing`, margin/padding reset)
- [ ] Set body font family, color, background
- [ ] Add `:focus-visible` outline styles for accessibility
- [ ] Import `variables.css` in `global.css`
- [ ] Import `global.css` in `main.tsx`
- [ ] Refactor `DashboardPage.css` to use CSS variables
- [ ] Refactor `TransactionsPage.css` to use CSS variables
- [ ] Refactor `BudgetsPage.css` to use CSS variables
- [ ] Refactor `GoalsPage.css` to use CSS variables
- [ ] Refactor `ReportsPage.css` to use CSS variables
- [ ] Refactor `LoginPage.css` to use CSS variables
- [ ] Refactor `RegisterPage.css` to use CSS variables

---

## Granular Checklist — Task 3.6 (Enhance Pages)

### 3.6.1 — DashboardPage
- [ ] Replace inline stats sections with `Card` component
- [ ] Replace inline chart sections with `Card` component
- [ ] Add `LoadingSkeleton` for loading state (TanStack Query)
- [ ] Add period selector (7 days, 30 days, 3 months, all time)
- [ ] Fetch and display spending alerts from `/api/advice/spending-alerts`
- [ ] Show goal progress summaries
- [ ] Add "Quick Actions" strip (Add Transaction, Create Budget, etc.)

### 3.6.2 — TransactionsPage
- [ ] Replace inline table with `DataTable` component
- [ ] Add sorting on columns (date, amount, category)
- [ ] Add pagination with `DataTable.pagination`
- [ ] Add create/edit form in `Modal` using `FormField` components
- [ ] Add delete confirmation with `ConfirmDialog`
- [ ] Display categories with `Badge` component
- [ ] Show `EmptyState` when no transactions
- [ ] Add search input with debounce
- [ ] Add category filter dropdown
- [ ] Add date range filter
- [ ] Add transaction type toggle (expense/income)
- [ ] Add bulk select checkboxes
- [ ] Add bulk actions (delete, re-categorize)

### 3.6.3 — BudgetsPage
- [ ] Display each budget as `Card` with progress bar
- [ ] Color-code progress: green (<80%), yellow (80-100%), red (>100%)
- [ ] Use `Modal` for create/edit budget form
- [ ] Show optimization suggestions inline with "Apply" button
- [ ] Add `ConfirmDialog` for applying optimizations
- [ ] Show `EmptyState` when no budgets
- [ ] Add allocation breakdown per category

### 3.6.4 — GoalsPage
- [ ] Display each goal as `Card` with visual progress bar/ring
- [ ] Show days remaining to deadline
- [ ] Show projected completion date
- [ ] Add risk `Badge` (on track, at risk, behind, completed)
- [ ] Add quick "Add Progress" button on each card
- [ ] Use `Modal` for create/edit goal form
- [ ] Show timeline/history of goal progress

### 3.6.5 — ReportsPage
- [ ] Add date range picker for report period
- [ ] Add tabbed view (Overview, Income/Expenses, Budget Adherence, Trends)
- [ ] Add export buttons — CSV download with proper handling
- [ ] Add export buttons — PDF download with proper handling
- [ ] Add chart: spending by category (pie/donut)
- [ ] Add chart: income vs expenses over time (line)
- [ ] Add chart: budget adherence (bar)

### 3.6.6 — LoginPage
- [ ] Replace inline inputs with `FormField` component
- [ ] Add client-side validation (email format, password required)
- [ ] Add show/hide password toggle
- [ ] Add "Remember me" checkbox
- [ ] Show error messages via `Alert` component
- [ ] Add loading state on submit via `Button` loading prop

### 3.6.7 — RegisterPage
- [ ] Replace inline inputs with `FormField` component
- [ ] Add client-side validation (name, email, password requirements)
- [ ] Add password strength indicator
- [ ] Add show/hide password toggle
- [ ] Add confirm password field
- [ ] Show error messages via `Alert` component
- [ ] Add loading state on submit via `Button` loading prop

---

## Granular Checklist — Task 3.7 (Custom Hooks)

- [ ] Create `frontend/src/hooks/` directory
- [ ] Create `useDebounce.ts` — debounce values with configurable delay
- [ ] Create `useLocalStorage.ts` — persist/read values from localStorage
- [ ] Create `usePagination.ts` — pagination logic (page, setPage, totalPages, hasNext, hasPrev)
- [ ] Create `useMediaQuery.ts` — responsive breakpoint detection
- [ ] Export all hooks from `hooks/index.ts`

---

## Granular Checklist — Task 3.8 (Accessibility)

- [ ] Add `aria-label` to all icon-only buttons
- [ ] Add `aria-label` to all interactive elements without visible text
- [ ] Modal: focus trapping (tab cycles within modal only)
- [ ] Modal: dismiss with Escape key
- [ ] Modal: return focus to trigger element on close
- [ ] DataTable: use `<th scope="col">` for column headers
- [ ] Alert: add `role="alert"` attribute
- [ ] Alert: add `aria-live="polite"` attribute
- [ ] FormField: associate `<label>` with `<input>` via `htmlFor`/`id`
- [ ] Add skip navigation link (`<a href="#main-content">Skip to content</a>`)
- [ ] Verify all color contrast ratios meet WCAG AA (4.5:1 text, 3:1 large text)
- [ ] Test keyboard navigation through all pages
- [ ] Install axe-core or run Lighthouse accessibility audit

---

## Granular Checklist — Task 3.9 (API Error Handling)

- [ ] Create `frontend/src/api/errors.ts`
- [ ] Define `ApiError` class (statusCode, detail, field)
- [ ] Define `handleApiError()` function — convert axios errors to `ApiError`
- [ ] Handle network errors with user-friendly message
- [ ] Handle 401 errors — trigger logout/redirect
- [ ] Handle 422 errors — extract validation details
- [ ] Update `frontend/src/api/transactions.ts` — use `handleApiError`
- [ ] Update `frontend/src/api/budgets.ts` — use `handleApiError`
- [ ] Update `frontend/src/api/goals.ts` — use `handleApiError`
- [ ] Update `frontend/src/api/reports.ts` — use `handleApiError`
- [ ] Update `frontend/src/api/auth.ts` — use `handleApiError`
- [ ] Wire TanStack Query `onError` callbacks to toast notifications
- [ ] Wire TanStack Mutation `onSuccess` callbacks to toast notifications

---

## Granular Checklist — Task 3.10 (New Pages)

### 3.10.1 — Settings Page
- [ ] Create `frontend/src/pages/SettingsPage.tsx`
- [ ] Add route `/settings` to router
- [ ] Add profile section — view/edit full name, email
- [ ] Add change password form
- [ ] Add theme preference toggle
- [ ] Add navigation link in Layout sidebar/header

### 3.10.2 — AI Chat Page
- [ ] Create `frontend/src/pages/AIChatPage.tsx`
- [ ] Add route `/ai-chat` to router
- [ ] Implement chat interface with message bubbles
- [ ] User messages on right, AI messages on left
- [ ] Send messages to `/api/ai/chat`
- [ ] Display AI responses with markdown formatting
- [ ] Show confidence indicator on AI responses
- [ ] Show financial disclaimer on AI responses
- [ ] Add loading indicator while AI responds
- [ ] Add navigation link in Layout sidebar/header

### 3.10.3 — Import/Export Page
- [ ] Create `frontend/src/pages/ImportPage.tsx`
- [ ] Add route `/import` to router
- [ ] Implement file upload dropzone (drag & drop)
- [ ] Accept CSV and XLSX files
- [ ] Show file preview before importing
- [ ] Show import progress/results
- [ ] Add "Download Template" button
- [ ] Add export section with format options (CSV, PDF)
- [ ] Add date range filter for export
- [ ] Add navigation link in Layout sidebar/header

---

## Final P3 Validation

- [ ] All 10 reusable components created and working
- [ ] ErrorBoundary catches errors without white screen crash
- [ ] Toast notifications appear for all create/update/delete actions
- [ ] All forms validate on blur and submit
- [ ] Design system CSS variables used consistently
- [ ] All 7 existing pages enhanced with new components
- [ ] 4 custom hooks created and working
- [ ] Settings, AI Chat, Import pages functional
- [ ] Light mode looks good
- [ ] Dark mode looks good
- [ ] Lighthouse accessibility score ≥ 90
- [ ] All interactive elements keyboard-navigable
