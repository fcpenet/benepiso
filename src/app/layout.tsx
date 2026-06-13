import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Benepisyoko — Find the Filipino benefits you’re entitled to',
  description:
    'Discover Philippine government benefits — including lesser-known ones — based on your age, income, work and circumstances, with the law behind each and how to claim it.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
