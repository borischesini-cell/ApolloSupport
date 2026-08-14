import { Router } from "express";
import type Database from "better-sqlite3";
import type { CustomerStatus } from "../db.js";

const VALID_STATUSES: CustomerStatus[] = ["lead", "active", "churned"];

interface CustomerInput {
  name?: unknown;
  company?: unknown;
  email?: unknown;
  phone?: unknown;
  status?: unknown;
  value?: unknown;
  notes?: unknown;
}

function normalize(body: CustomerInput) {
  const name = typeof body.name === "string" ? body.name.trim() : "";
  const status =
    typeof body.status === "string" && VALID_STATUSES.includes(body.status as CustomerStatus)
      ? (body.status as CustomerStatus)
      : "lead";
  const value = Number.isFinite(Number(body.value)) ? Number(body.value) : 0;
  return {
    name,
    company: typeof body.company === "string" ? body.company.trim() || null : null,
    email: typeof body.email === "string" ? body.email.trim() || null : null,
    phone: typeof body.phone === "string" ? body.phone.trim() || null : null,
    status,
    value,
    notes: typeof body.notes === "string" ? body.notes.trim() || null : null,
  };
}

export function customersRouter(db: Database.Database): Router {
  const router = Router();

  router.get("/", (_req, res) => {
    const rows = db.prepare("SELECT * FROM customers ORDER BY createdAt DESC, id DESC").all();
    res.json(rows);
  });

  router.get("/:id", (req, res) => {
    const row = db.prepare("SELECT * FROM customers WHERE id = ?").get(req.params.id);
    if (!row) {
      res.status(404).json({ error: "Customer not found" });
      return;
    }
    res.json(row);
  });

  router.post("/", (req, res) => {
    const data = normalize(req.body ?? {});
    if (!data.name) {
      res.status(400).json({ error: "name is required" });
      return;
    }
    const info = db
      .prepare(
        `INSERT INTO customers (name, company, email, phone, status, value, notes)
         VALUES (@name, @company, @email, @phone, @status, @value, @notes)`,
      )
      .run(data);
    const created = db.prepare("SELECT * FROM customers WHERE id = ?").get(info.lastInsertRowid);
    res.status(201).json(created);
  });

  router.put("/:id", (req, res) => {
    const existing = db.prepare("SELECT * FROM customers WHERE id = ?").get(req.params.id);
    if (!existing) {
      res.status(404).json({ error: "Customer not found" });
      return;
    }
    const data = normalize(req.body ?? {});
    if (!data.name) {
      res.status(400).json({ error: "name is required" });
      return;
    }
    db.prepare(
      `UPDATE customers
       SET name = @name, company = @company, email = @email, phone = @phone,
           status = @status, value = @value, notes = @notes, updatedAt = datetime('now')
       WHERE id = @id`,
    ).run({ ...data, id: Number(req.params.id) });
    const updated = db.prepare("SELECT * FROM customers WHERE id = ?").get(req.params.id);
    res.json(updated);
  });

  router.delete("/:id", (req, res) => {
    const info = db.prepare("DELETE FROM customers WHERE id = ?").run(req.params.id);
    if (info.changes === 0) {
      res.status(404).json({ error: "Customer not found" });
      return;
    }
    res.status(204).end();
  });

  return router;
}
