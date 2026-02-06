# Finehance — Frontend

React + TypeScript web interface for the AI-powered personal finance management platform.

## Tech Stack

| Package | Version | Purpose |
|---------|---------|---------|
| **React** | 19.2 | UI library |
| **TypeScript** | 5.9 | Type safety |
| **Vite** | rolldown-vite 7.2.5 | Build tool and dev server |
| **React Router** | 7.13 | Client-side routing |
| **TanStack Query** | 5.90 | Server state management and caching |
| **Axios** | 1.13 | HTTP client with interceptors |
| **Chart.js** | 4.5 | Data visualization (via react-chartjs-2) |
| **Lucide React** | 0.563 | Icon library |
| **Playwright** | 1.58 | End-to-end testing (dev dependency) |

## Project Structure

```
src/
├── api/                    # API client modules (8 files)
│   ├── client.ts           # Axios instance with auth interceptors
│   ├── auth.ts             # Authentication API (login, register, refresh)
│   ├── transactions.ts     # Transaction CRUD operations
│   ├── budgets.ts          # Budget management API
│   ├── goals.ts            # Financial goals API
│   ├── advice.ts           # AI-powered advice API
│   ├── reports.ts          # Reports generation/export API
│   └── dashboard.ts        # Dashboard summary API
├── components/             # Reusable UI components
│   ├── Layout.tsx          # Main app layout with sidebar navigation
│   ├── Layout.css
│   ├── ThemeToggle.tsx     # Light/dark theme switcher
│   └── ThemeToggle.css
├── contexts/               # React contexts
│   ├── AuthContext.tsx     # Authentication state (login, logout, token management)
│   └── ThemeContext.tsx    # Theme state (light/dark mode persistence)
├── pages/                  # Page components (7 pages)
│   ├── LoginPage.tsx       # User login form
│   ├── RegisterPage.tsx    # User registration form
│   ├── DashboardPage.tsx   # Financial overview with charts
│   ├── DashboardPage.css
│   ├── TransactionsPage.tsx # Transaction list, CRUD, filtering
│   ├── TransactionsPage.css
│   ├── BudgetsPage.tsx     # Budget management with progress bars
│   ├── BudgetsPage.css
│   ├── GoalsPage.tsx       # Goal tracking with progress indicators
│   ├── GoalsPage.css
│   ├── ReportsPage.tsx     # Financial reports with export options
│   ├── ReportsPage.css
│   └── AuthPages.css       # Shared auth page styles
├── types/
│   └── index.ts            # TypeScript type definitions
├── App.tsx                 # Main app component with React Router
├── App.css
├── main.tsx                # App entry point
└── index.css               # Global styles
```

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API running on http://localhost:8000

### Installation

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Start development server
npm run dev
```

The app will be available at **http://localhost:5173** (Vite default port).

### Build for Production

```bash
npm run build
```

Output goes to the `dist/` directory.

## Features

### Implemented
- **Authentication** — Login and register with JWT token management
- **Protected routes** — Unauthorized users redirected to login
- **Auto token refresh** — Axios interceptor handles 401 responses
- **Dashboard** — Financial overview with Chart.js visualizations (income vs expenses, category breakdown)
- **Transactions** — Full CRUD with type/category filtering, search, and pagination
- **Budgets** — Create/edit budgets with category allocations and progress tracking
- **Goals** — Set financial targets with progress indicators and deadline tracking
- **Reports** — Generate reports by date range with CSV/PDF export
- **Theme toggle** — Light/dark mode with localStorage persistence
- **Responsive layout** — Sidebar navigation with mobile support

### Not Yet Implemented
- Reusable component library (DataTable, Modal, FormField, etc.)
- Error boundaries for graceful error handling
- Toast notification system
- Custom hooks (useDebounce, useLocalStorage, usePagination)
- Design system with CSS variables
- Settings page, AI Chat page, Import/Export page
- Accessibility (ARIA labels, focus trapping, keyboard navigation)
- Playwright test files (framework is installed but no specs written)

## API Integration

The frontend communicates with the backend at `http://localhost:8000` (configurable via `VITE_API_BASE_URL`).

### Authentication Flow

1. User logs in with email/password
2. Backend returns access token and refresh token
3. Tokens stored in localStorage
4. Access token attached to all API requests via Axios interceptor
5. On 401, interceptor attempts token refresh automatically
6. If refresh fails, user is redirected to login

### API Modules

| Module | Endpoints |
|--------|-----------|
| `auth.ts` | Login, register, refresh, logout, get profile |
| `transactions.ts` | CRUD, list with filters |
| `budgets.ts` | CRUD, progress, optimization |
| `goals.ts` | CRUD, progress, risk alerts |
| `advice.ts` | Personalized advice, spending alerts |
| `reports.ts` | Generate, export CSV/PDF |
| `dashboard.ts` | Summary statistics |

## State Management

| Type | Solution |
|------|----------|
| **Authentication** | `AuthContext` — login state, user info, token management |
| **Theme** | `ThemeContext` — light/dark mode with localStorage |
| **Server data** | TanStack Query — automatic caching, refetching, loading states |
| **Local UI state** | React `useState` / `useReducer` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API base URL |

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server (port 5173) |
| `npm run build` | Type-check + production build |
| `npm run preview` | Preview production build locally |
| `npm run lint` | Run ESLint |
