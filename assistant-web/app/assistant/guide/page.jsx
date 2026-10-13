import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { createLifeEntry } from "../actions";

export const dynamic = "force-dynamic";

export default async function GuidePage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  const [{ data: profile }, { data: openTasks }] = await Promise.all([
    supabase.from("user_profiles").select("display_name,assistant_name,about_me,support_style,life_areas").eq("id", user.id).maybeSingle(),
    supabase.from("life_entries").select("title,priority,due_at").eq("user_id", user.id).eq("kind", "task").neq("status", "done").order("due_at", { ascending: true, nullsFirst: false }).limit(5),
  ]);
  const assistantName = profile?.assistant_name || "Aster";
  const firstTask = openTasks?.[0];
  return <>
    <header className="page-top"><div><p className="page-eyebrow">A moment to find your footing</p><h1>Let's make this manageable.</h1><p className="page-subtitle">{assistantName} is a quiet place to think, notice what matters, and choose one next step.</p></div></header>
    <div className="two-col">
      <section className="panel"><p className="page-eyebrow">When everything feels like a lot</p><h2>Start here, at your own pace.</h2>
        <div className="entry-list">
          <article className="entry-row"><span className="stat-icon">1</span><div><p className="entry-title">Name what is hardest</p><p className="entry-detail">You do not have to make it sound neat. A few honest words are enough.</p></div></article>
          <article className="entry-row"><span className="stat-icon">2</span><div><p className="entry-title">Separate what you can influence</p><p className="entry-detail">Some things need care and patience; some things have one small action attached.</p></div></article>
          <article className="entry-row"><span className="stat-icon">3</span><div><p className="entry-title">Choose a step small enough to begin</p><p className="entry-detail">A message, a glass of water, five minutes, or asking someone to sit with you can be a start.</p></div></article>
        </div>
        <Link className="button soft" href="/assistant/reflections">Write a private reflection</Link>
      </section>
      <div className="stack">
        <section className="panel"><div className="panel-head"><div><h2>A next step from your plan</h2><p className="panel-note">Your saved items stay in your account.</p></div></div>
          {firstTask ? <><p className="entry-title">{firstTask.title}</p><p className="entry-detail">You do not need to do all of it right now. What is the first two-minute part?</p><Link className="text-link" href="/assistant/plan">Open your plan →</Link></> : <><p className="panel-note">There is nothing urgent on your list. You can leave the space clear, or choose one thing to put down.</p><Link className="text-link" href="/assistant/plan">Make a gentle plan →</Link></>}
        </section>
        <section className="panel"><h2>What feels true right now?</h2><p className="panel-note">Write one sentence about what is happening. You can keep it private and decide later whether it belongs in your journal.</p>
          <form className="form-grid" style={{ marginTop: "1rem" }} action={createLifeEntry}><input type="hidden" name="kind" value="journal" />
            <div className="field"><label htmlFor="guide-title">One thing I want to put down</label><input id="guide-title" name="title" maxLength={180} placeholder="I have been carrying…" required /></div>
            <button className="soft">Save a reflection</button>
          </form>
        </section>
        <p className="tiny">Aster offers organization and reflection prompts. It is not a substitute for professional, medical, or emergency support.</p>
      </div>
    </div>
  </>;
}
