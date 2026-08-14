# ApolloSupport

A lightweight CRM for **ApolloGesCom**. Track customers, leads, and pipeline value
from a single dashboard.

The project is a TypeScript monorepo managed with npm workspaces:

| Package  | Stack                              | Dev port |
| -------- | ---------------------------------- | -------- |
| `server` | Express + better-sqlite3 REST API  | `4000`   |
| `client` | React + Vite single-page app       | `5173`   |

Data is stored in a local SQLite database (`server/data/apollosupport.db`), so no
external services or credentials are required to run the app.

## Prerequisites

- Node.js `>= 20` (developed against Node 22)
- npm `>= 10`

## Getting started

```bash
npm ci          # install all workspace dependencies
npm run dev     # start the API (4000) and the web app (5173) together
```

Then open http://localhost:5173. The API is available at http://localhost:4000/api
(the Vite dev server proxies `/api` to it automatically).

## Common commands

| Command             | Description                                        |
| ------------------- | -------------------------------------------------- |
| `npm run dev`       | Run the server and client dev servers concurrently |
| `npm run dev:server`| Run only the API (`tsx watch`)                     |
| `npm run dev:client`| Run only the web app (`vite`)                      |
| `npm test`          | Run the API test suite (`node:test` + supertest)   |
| `npm run typecheck` | Type-check both workspaces                          |
| `npm run lint`      | Lint the whole repo with ESLint                     |
| `npm run build`     | Build the server (`tsc`) and client (`vite build`)  |

## API

| Method   | Path                 | Description              |
| -------- | -------------------- | ------------------------ |
| `GET`    | `/api/health`        | Health check             |
| `GET`    | `/api/stats`         | Dashboard aggregates     |
| `GET`    | `/api/customers`     | List customers           |
| `POST`   | `/api/customers`     | Create a customer        |
| `GET`    | `/api/customers/:id` | Fetch one customer       |
| `PUT`    | `/api/customers/:id` | Update a customer        |
| `DELETE` | `/api/customers/:id` | Delete a customer        |

The database is seeded with sample customers on first run.
