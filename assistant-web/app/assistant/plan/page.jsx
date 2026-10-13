import { createClient } from "@/lib/supabase/server";
import { createLifeEntry } from "../actions";
import EntryList from "@/components/entry-list";

export const dynamic = "force-dynamic";

export default async function PlanPage({ searchParams }) {
  const params = await searchParams;
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  const { data } = await supabase.from("life_entries").select("id,kind,title,content,status,priority,due_at,created_at")
    .eq("user_id", user.id).in("kind", ["task", "goal", "project", "habit"])
    .order("due_at", { ascending: true, nullsFirst: false }).limit(100);
  const entries = data || [];
  const tasks = entries.filter((entry) => entry.kind === "task" || entry.kind === "habit");
  const goals = entries.filter((entry) => entry.kind === "goal" || entry.kind === "project");
  return <>
    <header className="page-top"><div><p className="page-eyebrow">Make room for what matters</p><h1>Your plan.</h1><p className="page-subtitle">Turn the swirl into a list you can work with. Progress can be small and still count.</p></div></header>
    {params?.saved && <p className="notice">Saved to your private space.</p>}{params?.error && <p className="notice">That item could not be saved. Please check the details and try again.</p>}
    <div className="two-col">
      <section className="panel">
        <div className="panel-head"><div><h2>Tasks and habits</h2><p className="panel-note">One next action at a time.</p></div><span className="pill">{tasks.filter((item) => item.status !== "done").length} open</span></div>
        <form className="form-grid" action={createLifeEntry}><input type="hidden" name="kind" value="task" />
          <div className="field"><label htmlFor="task-title">What needs doing?</label><input id="task-title" name="title" maxLength={180} placeholder="Book an appointment" required /></div>
          <div className="two-col"><div className="field"><label htmlFor="task-date">When (optional)</label><input id="task-date" type="date" name="due_at" /></div>
            <div className="field"><label htmlFor="task-priority">Importance</label><select id="task-priority" name="priority"><option value="normal">Normal</option><option value="high">Important</option><option value="low">Low pressure</option></select></div></div>
          <button className="primary">Add task</button>
        </form>
        <div style={{ marginTop: "1.2rem" }}><EntryList entries={tasks} empty="Your list is clear. Add something when you are ready." /></div>
      </section>
      <div className="stack">
        <section className="panel"><div className="panel-head"><div><h2>Goals and projects</h2><p className="panel-note">Keep a direction in view, without rushing.</p></div></div>
          <form className="form-grid" action={createLifeEntry}><input type="hidden" name="kind" value="goal" />
            <div className="field"><label htmlFor="goal-title">What are you moving toward?</label><input id="goal-title" name="title" maxLength={180} placeholder="Feel steadier in my routine" required /></div>
            <div className="field"><label htmlFor="goal-detail">Why does this matter? (optional)</label><textarea id="goal-detail" name="content" maxLength={12000} rows={3} /></div><button className="soft">Save a goal</button>
          </form><div style={{ marginTop: "1.2rem" }}><EntryList entries={goals} empty="A goal can be a direction, not a deadline." /></div>
        </section>
        <section className="panel"><h2>A kinder measure of progress</h2><p className="panel-note">You do not have to finish everything to be moving forward. Choose what matters most today, and leave the rest visible for another day.</p></section>
      </div>
    </div>
  </>;
}
