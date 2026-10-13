import { createClient } from "@/lib/supabase/server";
import { createLifeEntry } from "../actions";
import EntryList from "@/components/entry-list";

export const dynamic = "force-dynamic";

export default async function ReflectionsPage({ searchParams }) {
  const params = await searchParams;
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  const { data } = await supabase.from("life_entries").select("id,kind,title,content,status,priority,due_at,created_at")
    .eq("user_id", user.id).in("kind", ["journal", "thought", "dream", "memory"])
    .order("created_at", { ascending: false }).limit(60);
  const entries = data || [];
  return <>
    <header className="page-top"><div><p className="page-eyebrow">Make space to notice</p><h1>Your reflections.</h1><p className="page-subtitle">Thoughts, dreams, and things you want to remember. Keep what helps; leave the rest.</p></div></header>
    {params?.saved && <p className="notice">Your reflection is saved in your private space.</p>}
    <div className="three-col" style={{ marginBottom: "1rem" }}>
      <div className="prompt-card"><span className="pill">Check in</span><h3>What is taking up the most room in your mind?</h3><p>Write it down without needing to solve it yet.</p></div>
      <div className="prompt-card"><span className="pill">Notice</span><h3>What helped, even a little?</h3><p>A small bright spot still counts.</p></div>
      <div className="prompt-card"><span className="pill">Remember</span><h3>What would you like future-you to know?</h3><p>Save a memory, reminder, or lesson.</p></div>
    </div>
    <div className="two-col">
      <section className="panel"><div className="panel-head"><div><h2>Put it into words</h2><p className="panel-note">This entry is visible only to your signed-in account.</p></div></div>
        <form className="form-grid" action={createLifeEntry}>
          <div className="field"><label htmlFor="reflection-kind">Save as</label><select id="reflection-kind" name="kind"><option value="journal">Journal entry</option><option value="thought">Thought</option><option value="dream">Dream</option><option value="memory">Something to remember</option></select></div>
          <div className="field"><label htmlFor="reflection-title">A short title</label><input id="reflection-title" name="title" maxLength={180} placeholder="A moment worth keeping" required /></div>
          <div className="field"><label htmlFor="reflection-content">Your note</label><textarea id="reflection-content" name="content" rows={8} maxLength={12000} placeholder="Start wherever you are…" /></div>
          <button className="primary">Save reflection</button>
        </form>
      </section>
      <section className="panel"><div className="panel-head"><div><h2>Recently saved</h2><p className="panel-note">A private record of what you chose to keep.</p></div><span className="pill">{entries.length} notes</span></div>
        <EntryList entries={entries} empty="No reflections yet. There is no right way to begin." />
      </section>
    </div>
  </>;
}
