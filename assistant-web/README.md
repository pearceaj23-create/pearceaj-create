# Phillap Assistant Web

A separate Next.js app for Supabase email/password authentication and a server-protected assistant workspace. It lives beside the existing local-first Windows app; it does not connect to Phillap's local SQLite data.

## Requirements

- Node.js 20.9 or newer
- A Supabase publishable key for the AVA/Phillap project

## Run locally

1. Copy `.env.example` to `.env.local`.
2. Set `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` to the project's publishable key. Never use a `service_role` or secret key in this app.
3. From this folder, run `npm install`, then `npm run dev`.
4. Open http://localhost:3000.

## Supabase Auth URL settings

In the Supabase dashboard for project `nqnjdslgrrtzxiwraouy`, open **Authentication → URL Configuration**:

- Set **Site URL** to `http://localhost:3000` for local development.
- Add `http://localhost:3000/auth/callback` to the redirect URLs.
- Before deployment, set `NEXT_PUBLIC_SITE_URL` to the deployed origin and add its `/auth/callback` URL to the allowed redirect URLs.

The app uses email/password sign-in and sign-up. If email confirmation is enabled, new users must follow Supabase's confirmation email before signing in. The callback exchanges the PKCE code and only redirects to a local path.

## Routes

- `/`: public landing page
- `/login`: sign in or create an account
- `/assistant`: protected workspace; unauthenticated visitors are sent to sign in

Auth sessions use Supabase SSR cookies. The request proxy refreshes sessions, and the protected page verifies the current user with Supabase before rendering. This starter adds no tables or database policies and does not change project Auth settings.
