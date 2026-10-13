import { redirect } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "./actions";

export const dynamic = "force-dynamic";

export default async function AssistantPage() {
  const supabase = await createClient();
  const { data: { user }, error } = await supabase.auth.getUser();

  if (error || !user) redirect("/login");

  return (
    <main className="shell">
      <header className="topbar">
        <Link className="brand" href="/">Phillap Assistant</Link>
        <form action={signOut}><button className="secondary">Sign out</button></form>
      </header>
      <section className="workspace">
        <div className="workspace-card">
          <p className="eyebrow">Private workspace</p>
          <h1>You’re signed in.</h1>
          <p>This page is protected by Supabase Auth and verifies your current account before rendering.</p>
          <p>Signed in as <strong>{user.email}</strong></p>
          <div className="workspace-actions">
            <span className="button" aria-disabled="true">Assistant setup next</span>
          </div>
        </div>
      </section>
    </main>
  );
}
