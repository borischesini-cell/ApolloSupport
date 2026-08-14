import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { createApp } from "./app.js";
import { createDb, seedIfEmpty } from "./db.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

const PORT = Number(process.env.PORT ?? 4000);
const DB_PATH = process.env.DB_PATH ?? resolve(__dirname, "../data/apollosupport.db");

const db = createDb(DB_PATH);
seedIfEmpty(db);

const app = createApp(db);

app.listen(PORT, () => {
  console.log(`ApolloSupport API listening on http://localhost:${PORT}`);
});
