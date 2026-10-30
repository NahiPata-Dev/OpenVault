# OpenVault

Hackathon project, built during CodeVerse India, 48 hours

Status: planning

## Setup

## Frontend

The React, TypeScript, Vite, and Tailwind application lives in `frontend/`.
Node.js 20.19+ or 22.12+ is recommended.

From the repository root, install dependencies and start the development server:

```powershell
Set-Location .\frontend
npm install
npm run dev
```

The Vite development server forwards `/api` requests to
`http://127.0.0.1:8000`. Start the backend separately; see
[`backend/README.md`](./backend/README.md). To use a different API origin, set
`VITE_API_URL` before starting or building the frontend (include the API base
path, such as `https://example.test/api`). Production deployments should
configure the Vercel `/api` rewrite to the backend so session cookies remain
same-origin.

Create and verify the production bundle with:

```powershell
npm run build
```

## Demo Accounts

## Tests

## Architecture

## Limitations

## AI Disclosure
