"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

const ENTRY_KINDS = new Set(["task", "goal", "journal", "memory", "thought", "dream", "project", "habit"]);

async function signedInClient() {
  const supabase = await createClient();
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error || !user) redirect("/login");
  return { supabase, user };
}

export async function createLifeEntry(formData) {
  const { supabase, user } = await signedInClient();
  const kind = String(formData.get("kind") || "task");
  const title = String(formData.get("title") || "").trim();
  const content = String(formData.get("content") || "").trim();
  const priority = String(formData.get("priority") || "normal");
  const date = String(formData.get("due_at") || "");
  if (!ENTRY_KINDS.has(kind) || !title || title.length > 180 || content.length > 12000) redirect("/assistant?error=entry");

  const dueAt = date ? new Date(date + "T12:00:00.000Z") : null;
  if (dueAt && Number.isNaN(dueAt.valueOf())) redirect("/assistant?error=entry");

  const { error } = await supabase.from("life_entries").insert({
    user_id: user.id, kind, title, content,
    priority: ["low", "normal", "high"].includes(priority) ? priority : "normal",
    due_at: dueAt?.toISOString() || null,
  });
  if (error) redirect("/assistant?error=entry");
  revalidatePath("/assistant");
  revalidatePath("/assistant/plan");
  revalidatePath("/assistant/reflections");
  if (["journal", "memory", "thought", "dream"].includes(kind)) redirect("/assistant/reflections?saved=1");
  redirect("/assistant/plan?saved=1");
}

export async function setEntryStatus(formData) {
  const { supabase, user } = await signedInClient();
  const id = String(formData.get("id") || "");
  const current = String(formData.get("status") || "open");
  if (!id) redirect("/assistant/plan");
  const status = current === "done" ? "open" : "done";
  const { error } = await supabase.from("life_entries").update({ status, updated_at: new Date().toISOString() }).eq("id", id).eq("user_id", user.id);
  if (error) redirect("/assistant/plan?error=save");
  revalidatePath("/assistant");
  revalidatePath("/assistant/plan");
  revalidatePath("/assistant/reflections");
}

export async function deleteLifeEntry(formData) {
  const { supabase, user } = await signedInClient();
  const id = String(formData.get("id") || "");
  if (id) await supabase.from("life_entries").delete().eq("id", id).eq("user_id", user.id);
  revalidatePath("/assistant");
  revalidatePath("/assistant/plan");
  revalidatePath("/assistant/reflections");
}

export async function saveProfile(formData) {
  const { supabase, user } = await signedInClient();
  const displayName = String(formData.get("display_name") || "").trim().slice(0, 80);
  const assistantName = String(formData.get("assistant_name") || "Aster").trim().slice(0, 40) || "Aster";
  const aboutMe = String(formData.get("about_me") || "").trim().slice(0, 6000);
  const supportStyle = String(formData.get("support_style") || "").trim().slice(0, 2000);
  const lifeAreas = String(formData.get("life_areas") || "").split(/[\n,]/)
    .map((area) => area.trim()).filter(Boolean).slice(0, 20);
  const { error } = await supabase.from("user_profiles").upsert({
    id: user.id, display_name: displayName, assistant_name: assistantName,
    about_me: aboutMe, support_style: supportStyle, life_areas: lifeAreas,
    updated_at: new Date().toISOString(),
  }, { onConflict: "id" });
  if (error) redirect("/assistant/personalize?error=save");
  revalidatePath("/assistant");
  revalidatePath("/assistant/personalize");
  revalidatePath("/assistant/guide");
  redirect("/assistant/personalize?saved=1");
}

export async function createMoneyItem(formData) {
  const { supabase, user } = await signedInClient();
  const label = String(formData.get("label") || "").trim();
  const direction = String(formData.get("direction") || "expense");
  const amount = Number(formData.get("amount"));
  const frequency = String(formData.get("frequency") || "monthly");
  const category = String(formData.get("category") || "other").trim().slice(0, 60) || "other";
  if (!label || label.length > 160 || !Number.isFinite(amount) || amount <= 0) redirect("/assistant/money?error=entry");

  const { error } = await supabase.from("money_items").insert({
    user_id: user.id, label, direction, amount: Math.round(amount * 100) / 100,
    frequency: ["weekly", "biweekly", "monthly", "quarterly", "yearly", "once"].includes(frequency) ? frequency : "monthly",
    category,
  });
  if (error) redirect("/assistant/money?error=entry");
  revalidatePath("/assistant/money");
  redirect("/assistant/money?saved=1");
}

export async function deleteMoneyItem(formData) {
  const { supabase, user } = await signedInClient();
  const id = String(formData.get("id") || "");
  if (id) await supabase.from("money_items").delete().eq("id", id).eq("user_id", user.id);
  revalidatePath("/assistant/money");
}

export async function signOut() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}
