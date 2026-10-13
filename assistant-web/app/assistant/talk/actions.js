"use server";

import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

const assistantRules = `You are Aster, a thoughtful personal assistant. Help the user make life feel more manageable. Be warm, grounded, practical, and honest. Ask one useful question at a time. Offer small next steps without judgment. You are not a therapist, doctor, lawyer, or financial adviser; encourage qualified or trusted human support when the situation calls for it. Never claim to remember information that was not included in this conversation.`;

export async function sendMessage(formData) {
  const message = String(formData.get("message") || "").trim();
  const consent = formData.get("send_to_ai") === "on";
  const includePersonalContext = formData.get("include_context") === "on";
  const conversationId = String(formData.get("conversation_id") || "");

  if (!message || message.length > 6000 || !consent) {
    redirect("/assistant/talk?error=consent");
  }
  if (!process.env.OPENAI_API_KEY) redirect("/assistant/talk?error=setup");

  const supabase = await createClient();
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError || !user) redirect("/login");

  let conversation;
  if (conversationId) {
    const { data } = await supabase
      .from("assistant_conversations")
      .select("id")
      .eq("id", conversationId)
      .eq("user_id", user.id)
      .maybeSingle();
    conversation = data;
  }
  if (!conversation) {
    const { data, error } = await supabase
      .from("assistant_conversations")
      .insert({ user_id: user.id, title: message.slice(0, 80) })
      .select("id")
      .single();
    if (error || !data) redirect("/assistant/talk?error=save");
    conversation = data;
  }

  const { data: previous } = await supabase
    .from("assistant_messages")
    .select("role, content")
    .eq("conversation_id", conversation.id)
    .eq("user_id", user.id)
    .order("created_at", { ascending: true })
    .limit(20);

  const currentMessages = [...(previous || []).map(({ role, content }) => ({ role, content })), { role: "user", content: message }];
  const { data: profile } = includePersonalContext
    ? await supabase.from("user_profiles").select("display_name, assistant_name, about_me, life_areas, support_style").eq("id", user.id).maybeSingle()
    : { data: null };

  let instructions = assistantRules;
  if (profile) {
    instructions += "\n\nThe user explicitly chose to include their saved personal context for this message. Treat it as private context, not verified fact: " +
      JSON.stringify({ display_name: profile.display_name, assistant_name: profile.assistant_name, about_me: profile.about_me, life_areas: profile.life_areas, support_style: profile.support_style });
  }

  let response;
  try {
    response = await fetch("https://api.openai.com/v1/responses", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${process.env.OPENAI_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: process.env.OPENAI_MODEL || "gpt-6-luna",
        instructions,
        input: currentMessages,
        max_output_tokens: 1200,
        store: false,
      }),
      signal: AbortSignal.timeout(45000),
      cache: "no-store",
    });
  } catch {
    redirect("/assistant/talk?error=provider");
  }
  if (!response.ok) redirect("/assistant/talk?error=provider");

  const result = await response.json();
  const answer = typeof result.output_text === "string"
    ? result.output_text.trim()
    : (result.output || []).flatMap((item) => item.content || []).filter((item) => item.type === "output_text").map((item) => item.text).join("\n").trim();
  if (!answer) redirect("/assistant/talk?error=empty");

  const inserts = [
    { conversation_id: conversation.id, user_id: user.id, role: "user", content: message },
    { conversation_id: conversation.id, user_id: user.id, role: "assistant", content: answer },
  ];
  const { error: saveError } = await supabase.from("assistant_messages").insert(inserts);
  if (saveError) redirect("/assistant/talk?error=save");
  await supabase.from("assistant_conversations").update({ updated_at: new Date().toISOString() }).eq("id", conversation.id).eq("user_id", user.id);
  redirect(`/assistant/talk?id=${encodeURIComponent(conversation.id)}`);
}
