import "./globals.css";

export const metadata = {
  title: "Aster — your personal assistant",
  description: "A private place to make sense of life, choose a next step, and keep moving.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
