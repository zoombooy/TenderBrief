import http from "node:http";

const publicFiles = new Map([
  ["/", "index.html"],
  ["/index.html", "index.html"],
  ["/app.js", "app.js"],
]);
const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};
const port = Number(process.env.PORT || 4173);

http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", "http://127.0.0.1");
  if (url.pathname.startsWith("/api/")) {
    res.writeHead(501, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ detail: "Agent 后端接口尚未实现；当前服务只提供前端预览。" }));
    return;
  }
  if (req.method !== "GET" && req.method !== "HEAD") {
    res.writeHead(405, { Allow: "GET, HEAD" });
    res.end();
    return;
  }
  const filename = publicFiles.get(url.pathname);
  if (!filename) {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Not found");
    return;
  }
  try {
    const { readFile } = await import("node:fs/promises");
    const body = await readFile(new URL("./" + filename, import.meta.url));
    res.writeHead(200, {
      "Content-Type": mime["." + filename.split(".").pop()] || "application/octet-stream",
      "Content-Length": body.length,
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "no-store",
    });
    res.end(req.method === "HEAD" ? undefined : body);
  } catch {
    res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Unable to read UI file");
  }
}).listen(port, "127.0.0.1", () => {
  console.log("TenderBrief UI: http://127.0.0.1:" + port);
  console.log("Frontend preview only; Agent APIs return HTTP 501 until implemented.");
});
