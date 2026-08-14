import Database from "better-sqlite3";
import { existsSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

export type CustomerStatus = "lead" | "active" | "churned";

export interface Customer {
  id: number;
  name: string;
  company: string | null;
  email: string | null;
  phone: string | null;
  status: CustomerStatus;
  value: number;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
}

const SEED_CUSTOMERS: Array<Omit<Customer, "id" | "createdAt" | "updatedAt">> = [
  {
    name: "Marie Dubois",
    company: "Boulangerie Dubois",
    email: "marie@dubois.fr",
    phone: "+33 1 23 45 67 89",
    status: "active",
    value: 4200,
    notes: "Renouvellement licence ApolloGesCom en mars.",
  },
  {
    name: "Carlos Mendez",
    company: "Ferretería Mendez",
    email: "carlos@mendez.ar",
    phone: "+54 11 5555 1234",
    status: "lead",
    value: 0,
    notes: "Demande de démo du module de stock.",
  },
  {
    name: "Aisha Khan",
    company: "Khan Textiles",
    email: "aisha@khantextiles.com",
    phone: "+44 20 7946 0958",
    status: "active",
    value: 9800,
    notes: "Client premium, support prioritaire.",
  },
];

/**
 * Create a database connection and ensure the schema exists.
 * Pass ":memory:" (default in tests) for an ephemeral database.
 */
export function createDb(location: string): Database.Database {
  if (location !== ":memory:") {
    const dir = dirname(location);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
  }

  const db = new Database(location);
  db.pragma("journal_mode = WAL");
  db.exec(`
    CREATE TABLE IF NOT EXISTS customers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      company TEXT,
      email TEXT,
      phone TEXT,
      status TEXT NOT NULL DEFAULT 'lead',
      value REAL NOT NULL DEFAULT 0,
      notes TEXT,
      createdAt TEXT NOT NULL DEFAULT (datetime('now')),
      updatedAt TEXT NOT NULL DEFAULT (datetime('now'))
    );
  `);

  return db;
}

/** Insert sample data when the customers table is empty. */
export function seedIfEmpty(db: Database.Database): void {
  const count = db.prepare("SELECT COUNT(*) AS n FROM customers").get() as { n: number };
  if (count.n > 0) return;

  const insert = db.prepare(
    `INSERT INTO customers (name, company, email, phone, status, value, notes)
     VALUES (@name, @company, @email, @phone, @status, @value, @notes)`,
  );
  const insertMany = db.transaction((rows: typeof SEED_CUSTOMERS) => {
    for (const row of rows) insert.run(row);
  });
  insertMany(SEED_CUSTOMERS);
}
