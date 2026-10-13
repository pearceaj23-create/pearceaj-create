import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { createLifeEntry } from "./actions";
import EntryList from "@/components/entry-list";

export const dynamic = "force-dynamic";

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

export default async function TodayPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  const [{ data: profile }, { data: entries }] = await Promise.all([
    supabase.from("user_profiles").select("display_name,assistant_name,about_me,support_style,life_areas").eq("id", user.id).maybeSingle(),
    supabase.from("life_entries").select("id,kind,title,content,status,priority,due_at,created_at").eq("user_id", user.id).order("created_at", { ascending: false }).limit(100),
  ]);
  const all = entries || [];
  const openTasks = all.filter((entry) => entry.kind === "task" && entry.status !== "done" && entry.status !== "archived");
  const openGoals = all.filter((entry) => entry.kind === "goal" && entry.status !== "done" && entry.status !== "archived");
  const reflections = all.filter((entry) => ["journal", "thought", "dream", "memory"].includes(entry.kind));
  const today = new Date().toISOString().slice(0, 10);
  const dueToday = openTasks.filter((entry) => entry.due_at?.slice(0, 10) === today);
  const name = profile?.display_name?.trim() || "there";
  const assistantName = profile?.assistant_name || "Aster";
  const focusEntries = openTasks.filter((entry) => entry.priority === "high" || entry.due_at?.slice(0, 10) === today).slice(0, 4);

  return <>
    <header className="page-top"><div><p className="page-eyebrow">Your space · Today</p><h1>{greeting()}, {name}.</h1><p className="page-subtitle">Take a breath. You do not need to solve everything at once.</p></div>
      <div className="date-chip">{new Intl.DateTimeFormat("en", { weekday: "long", month: "long", day: "numeric" }).format(new Date())}</div>
    </header>
    <section className="hero-card"><div className="hero-copy"><p className="page-eyebrow">{assistantName} is here</p><h2>What would make today feel a little lighter?</h2>
      <p>Capture the thought, task, or small step that is taking up space. You can sort it out later.</p>
      <form className="capture-row" action={createLifeEntry}><input type="hidden" name="kind" value="task" />
        <input name="title" placeholder="A small thing I want to do…" aria-label="Quick add a task" maxLength={180} required /><button className="primary">Add to my plan</button>
      </form>
    </div><div className="hero-orbit" aria-hidden="true"><span>✦</span></div></section>
    <section className="stat-grid" aria-label="Your life at a glance">
      <div className="stat-card"><span className="stat-icon">◷</span><div><p className="stat-number">{openTasks.length}</p><p className="stat-label">open tasks</p></div></div>
      <div className="stat-card"><span className="stat-icon">✧</span><div><p className="stat-number">{openGoals.length}</p><p className="stat-label">goals in motion</p></div></div>
      <div className="stat-card"><span className="stat-icon">◌</span><div><p className="stat-number">{reflections.length}</p><p className="stat-label">saved reflections</p></div></div>
      <div className="stat-card"><span className="stat-icon">☼</span><div><p className="stat-number">{dueToday.length}</p><p className="stat-label">due today</p></div></div>
    </section>
    <div className="dashboard-grid">
      <section className="panel"><div className="panel-head"><div><h2>A few things to keep in view</h2><p className="panel-note">A short list is easier to carry.</p></div><Link className="text-link" href="/assistant/plan">Open plan →</Link></div>
        <EntryList entries={focusEntries} empty="No urgent items right now. You can add one to your plan or let the space stay clear." />
      </section>
      <div className="stack">
        <section className="panel"><div className="panel-head"><div><h2>When things feel tangled</h2><p className="panel-note">A gentle way back to the next step.</p></div><span className="pill">Guide</span></div>
          <p className="entry-detail">Name what feels hardest. Choose one thing you can influence. Make the next step small enough to begin.</p>
          <Link className="text-link" href="/assistant/guide">Spend a moment with Aster →</Link>
        </section>
        {!profile?.display_name && <section className="panel"><p className="page-eyebrow">Make this yours</p><h2>Tell Aster how to support you.</h2><p className="panel-note">Choose your name, focus areas, and the kind of help that feels right.</p><Link className="text-link" href="/assistant/personalize">Set up your space →</Link></section>}
      </div>
    </div>
  </>;
}
