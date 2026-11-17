import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

// 3d-spec คือแหล่งข้อมูลเดียวของโมเดล อยู่นอก root ของ Vite จึงต้องเปิด fs.allow
const specDir = fileURLToPath(new URL('../3d-spec', import.meta.url));

export default defineConfig({
  // GitHub Pages เสิร์ฟที่ /<ชื่อ repo>/ จึงตั้ง BASE_PATH ตอน build (ดู .github/workflows/pages.yml) ; รันในเครื่องใช้ '/'
  base: process.env.BASE_PATH ?? '/',
  resolve: {
    alias: { '@spec': specDir },
  },
  server: {
    fs: { allow: ['..'] },
  },
});
