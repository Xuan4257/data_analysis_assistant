async function request(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = "请求失败";
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }
  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response.text();
}

export const api = {
  config: () => request("/api/config"),
  saveConfig: (payload) =>
    request("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  testConfig: () => request("/api/config/test", { method: "POST" }),
  configStatus: () => request("/api/config/status"),
  tasks: () => request("/api/tasks"),
  task: (id) => request(`/api/tasks/${id}`),
  deleteTask: (id) => request(`/api/tasks/${id}`, { method: "DELETE" }),
  upload: (file) => {
    const data = new FormData();
    data.append("file", file);
    return request("/api/tasks/upload", { method: "POST", body: data });
  },
  analyze: (id, payload) =>
    request(`/api/tasks/${id}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  report: (id) => request(`/api/tasks/${id}/report`),
  reportDownloadUrl: (id) => `/api/tasks/${id}/report/download`,
  fileUrl: (id, path) => `/api/tasks/${id}/files/${path.split("/").map(encodeURIComponent).join("/")}`,
  downloadUrl: (id) => `/api/tasks/${id}/download`,
};
