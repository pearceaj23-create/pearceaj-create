import { createServerClient } from "@supabase/ssr";
import { NextResponse } from "next/server";

export async function updateSession(request) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet, headers) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
          Object.entries(headers).forEach(([key, value]) =>
            response.headers.set(key, value)
          );
        },
      },
    }
  );

  const { data } = await supabase.auth.getClaims();
  const isProtected = request.nextUrl.pathname === "/assistant"
    || request.nextUrl.pathname.startsWith("/assistant/");

  if (isProtected && !data?.claims) {
    const destination = request.nextUrl.clone();
    const next = request.nextUrl.pathname + request.nextUrl.search;
    destination.pathname = "/login";
    destination.search = "";
    destination.searchParams.set("next", next);
    return NextResponse.redirect(destination);
  }

  return response;
}
