import Link from "next/link";

export default function HomePage() {
  return (
    <main className="public-shell">
      <header className="public-topbar">
        <Link className="public-brand" href="/"><span className="brand-mark">✦</span> ASTER</Link>
        <Link className="public-nav" href="/login">Sign in</Link>
      </header>
      <section className="public-hero">
        <div>
          <p className="page-eyebrow">A private space for your life</p>
          <h1>Find your next steady step.</h1>
          <p>
            Aster helps you hold the moving pieces: what matters, what is weighing on you,
            and what you might do next. Make the space your own, one note at a time.
          </p>
          <Link className="button" href="/login">Open your space <span aria-hidden="true">→</span></Link>
        </div>
        <div className="public-art" aria-hidden="true"><span>✦</span></div>
      </section>
    </main>
  );
}
