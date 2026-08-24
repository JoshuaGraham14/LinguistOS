# Frontend (learning prototype)

Next.js (App Router) + TypeScript + Tailwind UI for the user-facing vocabulary / sentence-practice prototype. Talks to [`backend/`](../backend/); not wired to the [`research/`](../research/) experimental framework.

## Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL if backend is not on :8000
npm run dev
```

App runs at http://localhost:3000.

## Pages

- `/`          Dashboard — vocab list
- `/practice`  Practice page
- `/settings`  Settings
