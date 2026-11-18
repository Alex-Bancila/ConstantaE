import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'wxt';

const apiUrl = new URL(import.meta.env.WXT_API_URL ?? 'http://localhost:8000');

// See https://wxt.dev/api/reference/wxt/interfaces/inlineconfig.html
export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'ConstantaE',
    default_locale: 'ro',
    description: '__MSG_extensionDescription__',
    permissions: ['activeTab'],
    // Lets the background worker call the backend.
    host_permissions: [`${apiUrl.protocol}//${apiUrl.hostname}/*`],
  },
  vite: () => ({
    plugins: [tailwindcss()],
    // Lets the extension import the shared mock data from ../shared.
    server: { fs: { allow: ['..'] } },
  }),
});
