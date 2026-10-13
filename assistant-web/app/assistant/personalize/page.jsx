import { createClient } from "@/lib/supabase/server";
import { saveProfile } from "../actions";

export const dynamic = "force-dynamic";

export default async function PersonalizePage({ searchParams }) {
  const params = await searchParams;
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  const { data } = await supabase.from("user_profiles").select("display_name,assistant_name,about_me,support_style,life_areas").eq("id", user.id).maybeSingle();
  const profile = data || {};
  return <>
    <header className="page-top"><div><p className="page-eyebrow">Make it feel like yours</p><h1>Personalize Aster.</h1><p className="page-subtitle">Share only what feels useful. You can change or remove these notes whenever you want.</p></div></header>
    {params?.saved && <p className="notice">Your preferences are saved to your account.</p>}
    {params?.error && <p className="notice">Could not save your preferences. Please try again.</p>}
    <div className="two-col">
      <section className="panel"><div className="panel-head"><div><h2>How should this space feel?</h2><p className="panel-note">Your name, your companion's name, and the way you prefer to be supported.</p></div></div>
        <form className="form-grid" action={saveProfile}>
          <div className="field"><label htmlFor="display-name">What should I call you?</label><input id="display-name" name="display_name" defaultValue={profile.display_name || ""} maxLength={80} placeholder="Your preferred name" /></div>
          <div className="field"><label htmlFor="assistant-name">What would you like to call your assistant?</label><input id="assistant-name" name="assistant_name" defaultValue={profile.assistant_name || "Aster"} maxLength={40} required /></div>
          <div className="field"><label htmlFor="life-areas">What parts of life matter most right now?</label><textarea id="life-areas" name="life_areas" rows={3} defaultValue={(profile.life_areas || []).join("\n")} placeholder={"Family\nHealth\nWork\nHome"} /><small>One area per line, or separate them with commas.</small></div>
          <div className="field"><label htmlFor="support-style">What kind of support feels helpful?</label><textarea id="support-style" name="support_style" rows={4} maxLength={2000} defaultValue={profile.support_style || ""} placeholder="For example: Be gentle and direct. Help me slow down and find one doable next step." /></div>
          <div className="field"><label htmlFor="about-me">Anything you want this space to remember about you?</label><textarea id="about-me" name="about_me" rows={6} maxLength={6000} defaultValue={profile.about_me || ""} placeholder="Your strengths, responsibilities, hopes, challenges, or context you want to keep close." /><small>This is stored privately in your Supabase account. Aster does not send it to an AI service.</small></div>
          <button className="primary">Save my preferences</button>
        </form>
      </section>
      <aside className="stack">
        <section className="panel"><p className="page-eyebrow">A space that learns your rhythm</p><h2>Begin with what matters to you.</h2><p className="panel-note">You do not need to share everything at once. Add a little context when it helps, and keep sensitive details out if you would rather not save them online.</p></section>
        <section className="panel"><h2>Your privacy, in plain terms</h2><p className="panel-note">Your saved profile and entries are tied to your account. Database policies prevent other signed-in users from reading or changing them. No live AI provider is connected in this version.</p></section>
      </aside>
    </div>
  </>;
}
