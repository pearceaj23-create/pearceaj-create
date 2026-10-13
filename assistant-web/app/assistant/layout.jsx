import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "./actions";
import Navigation from "@/components/navigation";

export const dynamic = "force-dynamic";

export default async function AssistantLayout({ children }) {
  const supabase = await createClient();
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error || !user) redirect("/login");

  const { data: profile } = await supabase.from("user_profiles")
    .select("display_name").eq("id", user.id).maybeSingle();
  const name = profile?.display_name?.trim() || user.email?.split("@")[0] || "friend";

  return (
    <div className="app-frame">
      <aside className="sidebar">
        <a className="brand" href="/assistant"><span className="brand-mark" aria-hidden="true">✦</span><span><span className="brand-name">ASTER</span><span className="brand-caption">personal space</span></span></a>
        <p className="nav-section">Your life</p>
        <Navigation />
        <div className="sidebar-spacer" />
        <div className="sidebar-bottom">
          <p className="private-note">A calm place to keep your plans and reflections. Your saved entries belong to your account.</p>
          <div className="user-row">
            <span className="avatar" aria-hidden="true">{name.slice(0, 1).toUpperCase()}</span>
            <div className="user-meta"><div className="user-name">{name}</div><div className="user-email">{user.email}</div></div>
            <form action={signOut}><button className="signout" aria-label="Sign out">↗</button></form>
          </div>
        </div>
      </aside>
      <main className="main-area"><div className="content-wrap">{children}</div></main>
    </div>
  );
}
