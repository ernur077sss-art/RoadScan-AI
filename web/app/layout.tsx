import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Shell } from "@/components/shell";
export const metadata: Metadata = {
  title: {
    default: "Народный контроль · Дороги Семея",
    template: "%s · Народный контроль",
  },
  description:
    "Сообщите о дорожной проблеме, отметьте место на карте и получите ответ инспектора.",
  applicationName: "Народный контроль",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Народный контроль",
  },
  icons: { icon: "/icon.svg", apple: "/icon-192.png" },
};
const inter = localFont({
  src: "../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
  variable: "--font-inter",
  display: "swap",
  weight: "100 900",
});
const interCyr = localFont({
  src: "../node_modules/@fontsource-variable/inter/files/inter-cyrillic-wght-normal.woff2",
  variable: "--font-inter-cyr",
  display: "swap",
  weight: "100 900",
});
const mono = localFont({
  src: "../node_modules/@fontsource-variable/jetbrains-mono/files/jetbrains-mono-latin-wght-normal.woff2",
  variable: "--font-jetbrains",
  display: "swap",
  weight: "100 800",
  preload: false,
});
const monoCyr = localFont({
  src: "../node_modules/@fontsource-variable/jetbrains-mono/files/jetbrains-mono-cyrillic-wght-normal.woff2",
  variable: "--font-jetbrains-cyr",
  display: "swap",
  weight: "100 800",
  preload: false,
});
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#2f5b39",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="ru"
      suppressHydrationWarning
      className={`${inter.variable} ${interCyr.variable} ${mono.variable} ${monoCyr.variable}`}
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('roadscan-theme');document.documentElement.classList.toggle('dark',t==='dark'||(!t&&matchMedia('(prefers-color-scheme: dark)').matches));}catch(e){}})();`,
          }}
        />
      </head>
      <body>
        <Providers>
          <Shell>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
