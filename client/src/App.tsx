import { useEffect, useMemo, useState } from "react";
import {
  api,
  type Customer,
  type CustomerDraft,
  type CustomerStatus,
  type Stats,
} from "./api.js";

const EMPTY_DRAFT: CustomerDraft = {
  name: "",
  company: "",
  email: "",
  phone: "",
  status: "lead",
  value: 0,
  notes: "",
};

const STATUS_LABELS: Record<CustomerStatus, string> = {
  lead: "Lead",
  active: "Active",
  churned: "Churned",
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function App() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [draft, setDraft] = useState<CustomerDraft>(EMPTY_DRAFT);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    const [list, s] = await Promise.all([api.listCustomers(), api.getStats()]);
    setCustomers(list);
    setStats(s);
  }

  useEffect(() => {
    refresh()
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  function resetForm() {
    setDraft(EMPTY_DRAFT);
    setEditingId(null);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      if (editingId === null) {
        await api.createCustomer(draft);
      } else {
        await api.updateCustomer(editingId, draft);
      }
      resetForm();
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  }

  function startEdit(customer: Customer) {
    setEditingId(customer.id);
    setDraft({
      name: customer.name,
      company: customer.company ?? "",
      email: customer.email ?? "",
      phone: customer.phone ?? "",
      status: customer.status,
      value: customer.value,
      notes: customer.notes ?? "",
    });
  }

  async function handleDelete(id: number) {
    setError(null);
    try {
      await api.deleteCustomer(id);
      if (editingId === id) resetForm();
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  const summaryCards = useMemo(
    () => [
      { label: "Customers", value: stats ? String(stats.total) : "—" },
      { label: "Active", value: stats ? String(stats.active) : "—" },
      { label: "Leads", value: stats ? String(stats.leads) : "—" },
      { label: "Pipeline", value: stats ? formatCurrency(stats.pipeline) : "—" },
    ],
    [stats],
  );

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">A</span>
          <div>
            <h1>ApolloSupport</h1>
            <p>CRM for ApolloGesCom</p>
          </div>
        </div>
      </header>

      <main className="layout">
        <section className="stats">
          {summaryCards.map((card) => (
            <div className="stat-card" key={card.label}>
              <span className="stat-value">{card.value}</span>
              <span className="stat-label">{card.label}</span>
            </div>
          ))}
        </section>

        {error && <div className="banner error">{error}</div>}

        <div className="content">
          <section className="panel">
            <h2>{editingId === null ? "New customer" : "Edit customer"}</h2>
            <form onSubmit={handleSubmit} className="form">
              <label>
                Name
                <input
                  required
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  placeholder="Contact name"
                />
              </label>
              <label>
                Company
                <input
                  value={draft.company}
                  onChange={(e) => setDraft({ ...draft, company: e.target.value })}
                  placeholder="Company"
                />
              </label>
              <label>
                Email
                <input
                  type="email"
                  value={draft.email}
                  onChange={(e) => setDraft({ ...draft, email: e.target.value })}
                  placeholder="name@example.com"
                />
              </label>
              <label>
                Phone
                <input
                  value={draft.phone}
                  onChange={(e) => setDraft({ ...draft, phone: e.target.value })}
                  placeholder="+33 ..."
                />
              </label>
              <div className="form-row">
                <label>
                  Status
                  <select
                    value={draft.status}
                    onChange={(e) =>
                      setDraft({ ...draft, status: e.target.value as CustomerStatus })
                    }
                  >
                    <option value="lead">Lead</option>
                    <option value="active">Active</option>
                    <option value="churned">Churned</option>
                  </select>
                </label>
                <label>
                  Deal value (€)
                  <input
                    type="number"
                    min={0}
                    value={draft.value}
                    onChange={(e) => setDraft({ ...draft, value: Number(e.target.value) })}
                  />
                </label>
              </div>
              <label>
                Notes
                <textarea
                  rows={3}
                  value={draft.notes}
                  onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
                  placeholder="Context, next steps..."
                />
              </label>
              <div className="form-actions">
                <button type="submit" className="primary">
                  {editingId === null ? "Add customer" : "Save changes"}
                </button>
                {editingId !== null && (
                  <button type="button" onClick={resetForm}>
                    Cancel
                  </button>
                )}
              </div>
            </form>
          </section>

          <section className="panel">
            <h2>Customers</h2>
            {loading ? (
              <p className="muted">Loading…</p>
            ) : customers.length === 0 ? (
              <p className="muted">No customers yet. Add your first one.</p>
            ) : (
              <ul className="customer-list">
                {customers.map((customer) => (
                  <li key={customer.id} className="customer">
                    <div className="customer-main">
                      <span className={`badge badge-${customer.status}`}>
                        {STATUS_LABELS[customer.status]}
                      </span>
                      <div>
                        <strong>{customer.name}</strong>
                        {customer.company && <span className="company">{customer.company}</span>}
                      </div>
                    </div>
                    <div className="customer-meta">
                      {customer.email && <span>{customer.email}</span>}
                      <span className="value">{formatCurrency(customer.value)}</span>
                    </div>
                    <div className="customer-actions">
                      <button type="button" onClick={() => startEdit(customer)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        className="danger"
                        onClick={() => handleDelete(customer.id)}
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
