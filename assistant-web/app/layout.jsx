import "./globals.css";

export const metadata = {
  title: "Phillap Assistant",
  description: "A private assistant workspace",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
