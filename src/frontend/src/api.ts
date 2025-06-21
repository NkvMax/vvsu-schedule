export async function getHealth() {
    const res = await fetch("/api/health");
    return res.json();
}

export async function getConfigStatus() {
    const res = await fetch("/api/config/status");
    return res.json();
}

export async function postSetup(data: FormData) {
    const res = await fetch("/api/setup", {method: "POST", body: data});
    return res.json();
}

export async function getAccount() {
    const res = await fetch("/api/account");
    return res.json();
}

export async function postAccount(data: FormData) {
    const res = await fetch("/api/account", {method: "POST", body: data});
    return res.json();
}

export async function postSync() {
    const res = await fetch("/api/sync", {method: "POST"});
    return res.json();
}

export async function postScheduler(action: "start" | "stop") {
    const res = await fetch(`/api/scheduler/${action}`, {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: action === "start"
            ? new URLSearchParams({interval_minutes: "60"})
            : undefined,
    });
    return res.json();
}

export async function getSchedulerOverview() {
    const res = await fetch("/api/scheduler/overview");
    return res.json();
}

export async function getBotSettings(): Promise<{ bot_enabled: boolean }> {
    const res = await fetch("/api/bot/settings");
    if (!res.ok) throw new Error("getBotSettings failed");
    return res.json();
}

export async function postBotSettings(enabled: boolean) {
    return fetch("/api/bot/settings", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({bot_enabled: enabled}),
    });
}

export async function getBotConfig(): Promise<{ bot_token: string; admin_ids: string }> {
    const res = await fetch("/api/bot/config");
    if (!res.ok) throw new Error("getBotConfig failed");
    return res.json();
}

export async function patchBotConfig(payload: { bot_token?: string; admin_ids?: string }) {
    return fetch("/api/bot/config", {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
}
