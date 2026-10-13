import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { sendMessage } from "./actions";

export const dynamic = "force-dynamic";

const errors = {
  consent: "Please confirm before sending your message to the AI service.",
  setup: "Aster’s AI connection needs an API key in the app’s private environment settings.",
  provider: "Aster couldn’t reach the AI service. Your new message wasn’t saved; please try again.",
  empty: "The AI service returned an empty reply. Your new message wasn’t saved.",
  save: "Your conversation couldn’t be saved. Please try again.",
};

export default async function TalkPage({ searchParams }) {
  const params = await searchParams;
  const supabase = await createClient();
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error || !user) redirect("/login");

  const conversationId = typeof params?.id === "string" ? params.id : "";
  let messages = [];
  if (conversationId) {
    const { data: conversation } = await supabase
      .from("assistant_conversations")
      .select("id")
      .eq("id", conversationId)
      .eq("user_id", user.id)
      .maybeSingle();
    if (!conversation) redirect("/assistant/talk");
    const { data } = await supabase
      .from("assistant_messages")
      .select("id, role, content, created_at")
      .eq("conversation_id", conversationId)
      .eq("user_id", user.id)
      .order("created_at", { ascending: true });
    messages = data || [];
  }

  const { data: conversations } = await supabase
    .from("assistant_conversations")
    .select("id, title, updated_at")
    .eq("user_id", user.id)
    .order("updated_at", { ascending: false })
    .limit(12);

  return (
    <div className="page-stack">
      <section className="page-heading">
        <p className="eyebrow">A private conversation</p>
        <h1>Talk it through.</h1>
        <p>One step at a time. Your saved profile is never included unless you choose it below.</p>
      </section>
      {params?.error && errors[params.error] && <p className="notice error" role="alert">{errors[params.error]}</p>}
      {!process.env.OPENAI_API_KEY && <p className="notice">Aster is ready, but live replies need an OpenAI API key added to the app’s private environment settings.</p>}
      <div className="talk-layout">
        <aside className="panel conversation-list">
          <div className="panel-heading"><h2>Recent chats</h2><Link href="/assistant/talk">New</Link></div>
          {conversations?.length ? conversations.map((item) => (
            <Link className={item.id === conversationId ? "conversation-link active" : "conversation-link"} href={`/assistant/talk?id=${item.id}`} key={item.id}>
              {item.title || "A conversation"}
            </Link>
          )) : <p className="muted">Your conversations will appear here.</p>}
        </aside>
        <section className="panel talk-panel" aria-label="Conversation with Aster">
          <div className="message-list">
            {messages.length ? messages.map((item) => (
              <article className={item.role === "user" ? "message user-message" : "message assistant-message"} key={item.id}>
                <p className="message-role">{item.role === "user" ? "You" : "Aster"}</p>
                <p>{item.content}</p>
              </article>
            )) : <div className="empty-state"><span className="orb" aria-hidden="true">✳</span><h2>What’s on your mind?</h2><p>Start with whatever feels most important right now.</p></div>}
          </div>
          <form action={sendMessage} className="talk-form">
            {conversationId && <input type="hidden" name="conversation_id" value={conversationId} />}
            <label className="field"><span>Your message</span><textarea name="message" rows="3" maxLength="6000" required placeholder="Tell me what you’d like help with…" /></label>
            <label className="consent"><input type="checkbox" name="send_to_ai" required /><span>Send this message to OpenAI to get a reply. This may use paid API credits.</span></label>
            <label className="consent"><input type="checkbox" name="include_context" /><span>Also include my saved profile for more personal help.</span></label>
            <button type="submit" disabled={!process.env.OPENAI_API_KEY}>Send to Aster <span aria-hidden="true">↗</span></button>
          </form>
        </section>
      </div>
    </div>
  );
}
