import cors from "cors";
import express from "express";
import type Database from "better-sqlite3";
import { customersRouter } from "./routes/customers.js";

export function createApp(db: Database.Database): express.Express {
  const app = express();
  app.use(cors());
  app.use(express.json());

  app.get("/api/health", (_req, res) => {
    res.json({ status: "ok", service: "apollosupport-server" });
  });

  app.use("/api/customers", customersRouter(db));

  // Aggregate stats used by the dashboard.
  app.get("/api/stats", (_req, res) => {
    const total = (db.prepare("SELECT COUNT(*) AS n FROM customers").get() as { n: number }).n;
    const active = (
      db.prepare("SELECT COUNT(*) AS n FROM customers WHERE status = 'active'").get() as {
        n: number;
      }
    ).n;
    const leads = (
      db.prepare("SELECT COUNT(*) AS n FROM customers WHERE status = 'lead'").get() as {
        n: number;
      }
    ).n;
    const pipeline = (
      db.prepare("SELECT COALESCE(SUM(value), 0) AS v FROM customers").get() as { v: number }
    ).v;
    res.json({ total, active, leads, pipeline });
  });

  return app;
}
