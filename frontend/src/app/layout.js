import "./globals.css";

export const metadata = {
  title: "C-LABS Digital EVM",
  description: "Bhashyam High School Elections voting kiosk",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
