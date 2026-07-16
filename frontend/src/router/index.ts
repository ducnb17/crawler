import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "login",
    component: () => import("@/pages/Login.vue"),
    meta: { layout: "auth", public: true },
  },
  {
    path: "/signup",
    name: "signup",
    component: () => import("@/pages/Signup.vue"),
    meta: { layout: "auth", public: true },
  },
  {
    path: "/",
    component: () => import("@/components/layout/AppShell.vue"),
    meta: { requiresAuth: true },
    children: [
      { path: "", redirect: { name: "dashboard" } },
      { path: "dashboard", name: "dashboard", component: () => import("@/pages/Dashboard.vue") },
      { path: "jobs", name: "jobs", component: () => import("@/pages/Jobs.vue") },
      {
        path: "jobs/:id",
        name: "job-detail",
        component: () => import("@/pages/JobDetail.vue"),
        props: true,
      },
      { path: "results", name: "results", component: () => import("@/pages/Results.vue") },
      { path: "users", name: "users", component: () => import("@/pages/Users.vue") },
      { path: "settings", name: "settings", component: () => import("@/pages/Settings.vue") },
      { path: "proxies", name: "proxies", component: () => import("@/pages/Proxies.vue") },
      { path: "webhooks", name: "webhooks", component: () => import("@/pages/Webhooks.vue") },
    ],
  },
  {
    path: "/:pathMatch(.*)*",
    redirect: { name: "dashboard" },
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  await auth.init();
  const isPublic = to.meta.public === true || !to.meta.requiresAuth;
  if (!isPublic && !auth.isLoggedIn) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (auth.isLoggedIn && (to.name === "login" || to.name === "signup")) {
    return { name: "dashboard" };
  }
  // Scope guards per-route (opzionale)
  if (to.name === "users" && !auth.hasScope("users:read")) {
    return { name: "dashboard" };
  }
  return undefined;
});
