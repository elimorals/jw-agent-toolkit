import { defineConfig } from "vite";
import { resolve } from "path";

// Multi-page setup so Vite emits both the main dashboard window and the
// F57 presenter window into apps/desktop/dist/.
export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        presenter: resolve(__dirname, "presenter.html"),
      },
    },
  },
});
