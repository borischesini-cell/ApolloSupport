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

export interface Stats {
  total: number;
  active: number;
  leads: number;
  pipeline: number;
}

export type CustomerDraft = {
  name: string;
  company: string;
  email: string;
  phone: string;
  status: CustomerStatus;
  value: number;
  notes: string;
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error ?? `Request failed with ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listCustomers: () => fetch("/api/customers").then((r) => json<Customer[]>(r)),
  getStats: () => fetch("/api/stats").then((r) => json<Stats>(r)),
  createCustomer: (draft: CustomerDraft) =>
    fetch("/api/customers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    }).then((r) => json<Customer>(r)),
  updateCustomer: (id: number, draft: CustomerDraft) =>
    fetch(`/api/customers/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    }).then((r) => json<Customer>(r)),
  deleteCustomer: (id: number) =>
    fetch(`/api/customers/${id}`, { method: "DELETE" }).then((r) => {
      if (!r.ok) throw new Error(`Delete failed with ${r.status}`);
    }),
};
