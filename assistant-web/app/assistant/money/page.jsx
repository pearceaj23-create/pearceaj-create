import { createClient } from "@/lib/supabase/server";
import { createMoneyItem, deleteMoneyItem } from "../actions";

export const dynamic = "force-dynamic";

const monthlyFactor = { weekly: 52 / 12, biweekly: 26 / 12, monthly: 1, quarterly: 1 / 3, yearly: 1 / 12, once: 0 };
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export default async function MoneyPage({ searchParams }) {
  const params = await searchParams;
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  const { data } = await supabase.from("money_items").select("id,label,direction,amount,frequency,category,created_at")
    .eq("user_id", user.id).order("created_at", { ascending: false }).limit(100);
  const items = data || [];
  const monthly = (direction) => items.filter((item) => item.direction === direction)
    .reduce((sum, item) => sum + Number(item.amount) * monthlyFactor[item.frequency], 0);
  const income = monthly("income");
  const expenses = monthly("expense");
  return <>
    <header className="page-top"><div><p className="page-eyebrow">A clear view, at your pace</p><h1>Money, gently.</h1><p className="page-subtitle">A simple estimate from numbers you choose to enter. No bank connection and no judgment.</p></div></header>
    {params?.saved && <p className="notice">Saved. Your money list is private to your account.</p>}
    {params?.error && <p className="notice">Please enter a name and an amount greater than zero.</p>}
    <div className="money-summary">
      <div className="money-metric"><span>Estimated monthly income</span><strong>{money.format(income)}</strong></div>
      <div className="money-metric"><span>Estimated monthly expenses</span><strong>{money.format(expenses)}</strong></div>
      <div className="money-metric"><span>Difference from listed items</span><strong>{money.format(income - expenses)}</strong></div>
    </div>
    <div className="two-col">
      <section className="panel"><div className="panel-head"><div><h2>Add an item</h2><p className="panel-note">Recurring values are converted to monthly estimates.</p></div></div>
        <form className="form-grid" action={createMoneyItem}>
          <div className="field"><label htmlFor="money-label">Name</label><input id="money-label" name="label" required maxLength={160} placeholder="Rent, paycheck, groceries…" /></div>
          <div className="two-col"><div className="field"><label htmlFor="money-direction">Type</label><select id="money-direction" name="direction"><option value="expense">Expense</option><option value="income">Income</option></select></div>
            <div className="field"><label htmlFor="money-amount">Amount</label><input id="money-amount" name="amount" type="number" min="0.01" step="0.01" required /></div></div>
          <div className="two-col"><div className="field"><label htmlFor="money-frequency">How often?</label><select id="money-frequency" name="frequency"><option value="monthly">Monthly</option><option value="weekly">Weekly</option><option value="biweekly">Every two weeks</option><option value="quarterly">Quarterly</option><option value="yearly">Yearly</option><option value="once">One time</option></select></div>
            <div className="field"><label htmlFor="money-category">Category</label><input id="money-category" name="category" maxLength={60} placeholder="Home, work, food…" /></div></div>
          <button className="primary">Save item</button>
        </form>
      </section>
      <section className="panel"><div className="panel-head"><div><h2>Your list</h2><p className="panel-note">{items.length} saved items</p></div></div>
        {!items.length ? <div className="empty-state">Add only what is useful to see. This is not connected to your accounts.</div> : <div className="entry-list">{items.map((item) => <article className="entry-row" key={item.id}>
          <div className="entry-main"><p className="entry-title">{item.label}</p><p className="entry-detail">{money.format(Number(item.amount))} · {item.frequency} · {item.direction}{item.category ? " · " + item.category : ""}</p></div>
          <form action={deleteMoneyItem}><input type="hidden" name="id" value={item.id} /><button className="icon-button" aria-label={"Delete " + item.label}>Delete</button></form>
        </article>)}</div>}
      </section>
    </div>
    <p className="tiny" style={{ marginTop: "1rem" }}>This estimate includes only what you listed. It leaves out taxes, debts, savings, irregular bills, and anything you have not entered. It is not financial advice.</p>
  </>;
}
