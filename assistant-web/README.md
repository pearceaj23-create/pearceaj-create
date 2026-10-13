# Aster

A separate personal-assistant web app beside Phillap. Aster is designed to help with planning, reflection, personal context, and everyday tasks. It uses Supabase Auth and private, user-owned records. It is not connected to Phillap's local desktop data.

## Run locally

- Use Node.js 20.9 or newer.
- Copy `.env.example` to `.env.local`.
- Add your Supabase publishable key to `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. Never use a service-role or secret Supabase key in the browser app.
- Add an OpenAI API key to `OPENAI_API_KEY` to enable live replies. Keep it server-only; never expose it with a `NEXT_PUBLIC_` variable. `OPENAI_MODEL` defaults to `gpt-6-luna`.
- From this folder, run `npm install`, then `npm run dev`, and open http://localhost:3000.

Without the OpenAI key, Aster's profile, planning, reflection, and money-tracking areas remain available, but live AI replies are disabled.

## Supabase Auth URLs

In the Supabase dashboard for project `nqnjdslgrrtzxiwraouy`, open **Authentication → URL Configuration**.

- Set **Site URL** to `http://localhost:3000` during local development.
- Add `http://localhost:3000/auth/callback` to allowed redirect URLs.
- Before deployment, set `NEXT_PUBLIC_SITE_URL` to your deployed origin and add its `/auth/callback` URL.

Email/password sign-in and sign-up are supported. If confirmation is enabled, follow the email confirmation link.

## Private data and AI requests

The migration files in `supabase/migrations` match the schema already applied to the connected project. They create user-owned profile, life-entry, conversation, message, and money-item tables with row-level security. Each conversation request requires an explicit checkbox to send the message to OpenAI. Saved profile context is excluded by default and has a separate opt-in checkbox. Responses API requests set `store: false`; conversations are saved in the user's Supabase account. Never store secrets in source control.

## Routes

- `/`: Aster landing page
- `/login`: sign-in and account creation
- `/assistant`: protected daily overview
- `/assistant/talk`: private conversation
- `/assistant/plan`: tasks, habits, goals, and projects
- `/assistant/reflections`: journal, thoughts, dreams, and memories
- `/assistant/money`: private manual money tracking
- `/assistant/personalize`: profile and support preferences
- `/assistant/guide`: gentle reflection prompts
