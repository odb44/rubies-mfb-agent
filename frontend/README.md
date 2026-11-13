# Rubies MFB Customer Support Agent — Frontend

The frontend provides the customer-facing interface for interacting with the Rubies MFB Customer Support Agent.

It is built with React, TypeScript and Vite.

## Technology

- React 19
- TypeScript
- Vite 8
- React Markdown
- Remark GFM

## Prerequisites

- Node.js and npm.
- The Rubies MFB backend services configured and running when using live application functionality.

## Installation

From the repository root:

```powershell
cd frontend
npm install
```

## Development

Start the Vite development server:

```powershell
npm run dev
```

Vite displays the local development URL in the terminal.

## Production Build

Run the TypeScript checks and create the production build:

```powershell
npm run build
```

The generated production files are placed in `dist/`.

## Linting

Run ESLint:

```powershell
npm run lint
```

## Preview Production Build

After building, preview the production output locally:

```powershell
npm run preview
```

## Available Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start the development server |
| `npm run build` | Run TypeScript build checks and create production assets |
| `npm run lint` | Run ESLint |
| `npm run preview` | Preview the production build |

## Backend Integration

The frontend communicates with the Rubies MFB backend services. Ensure the required backend APIs are running and that the frontend API configuration points to the correct backend address.

Do not commit credentials, access tokens, or other sensitive configuration to the repository.