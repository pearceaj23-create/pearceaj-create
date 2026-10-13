"use server";

import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

function safePath(value) {
  const path = String(value || "/assistant");
  return path.startsWith("/") && !path.startsWith("//") && !path.includes("\\")
    ? path
    : "/assistant";
}

function credentials(formData) {
  const email = String(formData.get("email") || "").trim();
  const password = String(formData.get("password") || "");
  if (!email || email.length > 320 || !password || password.length > 256) {
    redirect("/login?error=invalid_input");
  }
  return { email, password };
}

export async function signIn(formData) {
  const { email, password } = credentials(formData);
  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });

  if (error) redirect("/login?error=sign_in_failed");
  redirect(safePath(formData.get("next")));
}

export async function signUp(formData) {
  const { email, password } = credentials(formData);
  if (password.length < 8) redirect("/login?error=password_too_short");

  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL;
  if (!siteUrl) redirect("/login?error=configuration");

  const supabase = await createClient();
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      emailRedirectTo: new URL("/auth/callback?next=/assistant", siteUrl).toString(),
    },
  });

  if (error) redirect("/login?error=sign_up_failed");
  if (data.session) redirect("/assistant");
  redirect("/login?message=check_email");
}
