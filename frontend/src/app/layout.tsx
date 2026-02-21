import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Music Mentor",
  description: "Practice tool that listens to you play and gives real-time feedback",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "'Inter', system-ui, sans-serif" }}>
        {children}
      </body>
    </html>
  );
}
