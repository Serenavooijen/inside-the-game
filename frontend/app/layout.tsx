import type { Metadata } from 'next';
import '@fontsource/barlow-condensed/600.css';
import '@fontsource/barlow-condensed/700.css';
import '@fontsource/barlow-condensed/800.css';
import '@fontsource/instrument-serif/400.css';
import '@fontsource/geist/400.css';
import '@fontsource/geist/500.css';
import '@fontsource/geist/600.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
import './globals.css';

export const metadata: Metadata = {
  title: 'Inside the Game',
  description: 'Live match intelligence for synthetic football matches, checked against the data.',
};

// Sets the saved theme before paint, so there is no flash.
const themeScript = `try{var t=localStorage.getItem('itg-theme');if(t==='day'){document.documentElement.classList.remove('theme-night');document.documentElement.classList.add('theme-day');}}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="theme-night" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen bg-bg text-fg font-sans">{children}</body>
    </html>
  );
}
