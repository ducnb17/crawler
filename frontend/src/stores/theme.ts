import { defineStore } from "pinia";
import { useColorMode } from "@vueuse/core";

export const useThemeStore = defineStore("theme", () => {
  const mode = useColorMode({
    attribute: "class",
    selector: "html",
    storageKey: "crawler.theme",
    modes: {
      light: "",
      dark: "dark",
    },
    initialValue: "dark",
  });

  function toggle(): void {
    mode.value = mode.value === "dark" ? "light" : "dark";
  }

  return { mode, toggle };
});