# AI Finance Platform - Frontend

React + TypeScript frontend for the AI-powered personal finance management platform.

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **React Router** - Client-side routing
- **TanStack Query** - Server state management
- **Axios** - HTTP client
- **Chart.js** - Data visualization

## Project Structure

```
src/
├── api/              # API client and service modules
│   ├── client.ts     # Axios instance with interceptors
│   ├── auth.ts       # Authentication API
│   └── transactions.ts # Transactions API
├── components/       # Reusable UI components
│   └── Layout.tsx    # Main app layout
├── contexts/         # React contexts
│   └── AuthContext.tsx # Authentication state
├── pages/            # Page components
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   ├── DashboardPage.tsx
│   ├── TransactionsPage.tsx
│   ├── BudgetsPage.tsx
│   ├── GoalsPage.tsx
│   └── ReportsPage.tsx
├── types/            # TypeScript type definitions
│   └── index.ts
├── App.tsx           # Main app component with routing
└── main.tsx          # App entry point
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

The app will be available at http://localhost:5173

### Build for Production

```bash
npm run build
```

The production build will be in the `dist/` directory.

## Features

### Implemented

- ✅ Authentication (Login/Register)
- ✅ Protected routes
- ✅ JWT token management with auto-refresh
- ✅ Responsive layout with sidebar navigation
- ✅ API client with interceptors

### In Progress

- 🚧 Dashboard with financial overview
- 🚧 Transaction management
- 🚧 Budget tracking
- 🚧 Goal tracking
- 🚧 Reports and analytics
- 🚧 Data visualization with charts

## API Integration

The frontend communicates with the backend API at `http://localhost:8000` (configurable via `VITE_API_BASE_URL`).

### Authentication Flow

1. User logs in with email/password
2. Backend returns access token and refresh token
3. Access token stored in localStorage
4. Access token added to all API requests via interceptor
5. On 401 error, automatically refresh token
6. If refresh fails, redirect to login

### API Services

- `authApi` - User authentication
- `transactionsApi` - Transaction CRUD operations
- More services to be added...

## Development

### Code Style

- Use TypeScript for type safety
- Follow React best practices
- Use functional components with hooks
- Keep components small and focused
- Use CSS modules or styled-components for styling

### State Management

- **Local state**: useState for component-specific state
- **Auth state**: AuthContext for authentication
- **Server state**: TanStack Query for API data
- **Form state**: Controlled components

## Environment Variables

- `VITE_API_BASE_URL` - Backend API base URL (default: http://localhost:8000)

## Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## License

MIT
