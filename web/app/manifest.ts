import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Народный контроль · Дороги Семея",
    short_name: "Народный контроль",
    description: "Сообщить о дорожной проблеме и получить ответ инспектора",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#fbf8f2",
    theme_color: "#2f5b39",
    lang: "ru",
    icons: [
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
