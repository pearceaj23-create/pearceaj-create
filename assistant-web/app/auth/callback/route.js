import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

function safePath(value) {
  return value?.startsWith("/") && !value.startsWith("//") && !value.includes("\\")
    ? value
    : "/assistant";
}

export async function GET(request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const destination = new URL(safePath(url.searchParams.get("next")), url.origin);

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(destination);
  }

  return NextResponse.redirect(new URL("/login?error=auth_callback", url.origin));
}
