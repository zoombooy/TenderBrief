import { createServer, request as proxyRequest } from "node:http";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.dirname(fileURLToPath(import.meta.url));
const apiPort = Number(process.env.API_PORT || 4174);
const uiPort = Number(process.env.UI_PORT || 4173);
const python = process.env.TENDERBRIEF_PYTHON;
const args = [
  ...(process.env.TENDERBRIEF_PYTHON_ARGS || "").split(" ").filter(Boolean),
  "api_server.py",
];
const command = python || (process.platform === "win32" ? "py" : "python3");
const commandArgs = python ? args : process.platform === "win32" ? ["-3", ...args] : args;
const api = spawn(command, commandArgs, {
  cwd: root,
  env: { ...process.env, HOST: "127.0.0.1", PORT: String(apiPort) },
  stdio: "inherit",
});
api.on("error", (error) => console.error("TenderBrief API did not start:", error.message));
api.on("exit", (code) => {
  if (code !== null && code !== 0) console.error("TenderBrief API exited with code", code);
});

const files = new Map([
  ["/", "index.html"],
  ["/index.html", "index.html"],
  ["/app.js", "app.js"],
]);
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8" };

const server = createServer((req, res) => {
  const url = new URL(req.url || "/", "http://127.0.0.1");
  if (url.pathname.startsWith("/api/")) {
    const upstream = proxyRequest({
      hostname: "127.0.0.1",
      port: apiPort,
      path: req.url,
      method: req.method,
      headers: { ...req.headers, host: "127.0.0.1:" + apiPort },
    }, (response) => {
      res.writeHead(response.statusCode || 502, response.headers);
      response.pipe(res);
    });
    upstream.on("error", () => {
      if (!res.headersSent) {
        res.writeHead(503, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ detail: "TenderBrief API 未启动；请检查 Python 依赖和服务日志。" }));
      }
    });
    req.pipe(upstream);
    return;
  }
  if (req.method !== "GET" && req.method !== "HEAD") {
    res.writeHead(405, { Allow: "GET, HEAD" });
    res.end();
    return;
  }
  const filename = files.get(url.pathname);
  if (!filename) {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Not found");
    return;
  }
  try {
    const body = requireFile(filename);
    res.writeHead(200, {
      "Content-Type": types[path.extname(filename)],
      "Content-Length": body.length,
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "no-store",
    });
    res.end(req.method === "HEAD" ? undefined : body);
  } catch {
    res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Unable to read UI file");
  }
});

function requireFile(filename) {
  return readFileSync(path.join(root, filename));
}
import { readFileSync } from "node:fs";

server.listen(uiPort, "127.0.0.1", () => {
  console.log("TenderBrief: http://127.0.0.1:" + uiPort);
});
process.on("SIGINT", () => {
  api.kill("SIGTERM");
  server.close(() => process.exit(0));
});
