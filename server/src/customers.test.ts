import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import request from "supertest";
import type { Express } from "express";
import { createApp } from "./app.js";
import { createDb, seedIfEmpty } from "./db.js";
import type Database from "better-sqlite3";

describe("customers API", () => {
  let app: Express;
  let db: Database.Database;

  before(() => {
    db = createDb(":memory:");
    seedIfEmpty(db);
    app = createApp(db);
  });

  after(() => {
    db.close();
  });

  it("reports health", async () => {
    const res = await request(app).get("/api/health");
    assert.equal(res.status, 200);
    assert.equal(res.body.status, "ok");
  });

  it("lists seeded customers", async () => {
    const res = await request(app).get("/api/customers");
    assert.equal(res.status, 200);
    assert.ok(Array.isArray(res.body));
    assert.equal(res.body.length, 3);
  });

  it("creates a customer", async () => {
    const res = await request(app)
      .post("/api/customers")
      .send({ name: "Test Corp Contact", company: "Test Corp", status: "lead", value: 1500 });
    assert.equal(res.status, 201);
    assert.equal(res.body.name, "Test Corp Contact");
    assert.equal(res.body.value, 1500);
    assert.ok(res.body.id);
  });

  it("rejects a customer without a name", async () => {
    const res = await request(app).post("/api/customers").send({ company: "No Name Inc" });
    assert.equal(res.status, 400);
  });

  it("updates a customer", async () => {
    const created = await request(app)
      .post("/api/customers")
      .send({ name: "Before Update", status: "lead" });
    const res = await request(app)
      .put(`/api/customers/${created.body.id}`)
      .send({ name: "After Update", status: "active", value: 500 });
    assert.equal(res.status, 200);
    assert.equal(res.body.name, "After Update");
    assert.equal(res.body.status, "active");
  });

  it("deletes a customer", async () => {
    const created = await request(app)
      .post("/api/customers")
      .send({ name: "To Delete" });
    const del = await request(app).delete(`/api/customers/${created.body.id}`);
    assert.equal(del.status, 204);
    const get = await request(app).get(`/api/customers/${created.body.id}`);
    assert.equal(get.status, 404);
  });

  it("returns aggregate stats", async () => {
    const res = await request(app).get("/api/stats");
    assert.equal(res.status, 200);
    assert.equal(typeof res.body.total, "number");
    assert.equal(typeof res.body.pipeline, "number");
  });
});
