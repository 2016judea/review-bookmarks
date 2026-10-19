// node --test test/*.test.js
// outputDirectory "." served api/_full/full.json.gz as /api/%5Ffull/... (200) until 2026-10-19:
// the whole paid bundle, to anyone. Only public/ is served statically now; the bundle reaches
// api/data.js through includeFiles and nothing else.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const { execFileSync } = require("node:child_process");

const ROOT = path.join(__dirname, "..");

test("only public/ is served statically and the bundle only reaches the function", () => {
  const out = execFileSync("python3", ["-c",
    "import importlib.util,sys;s=importlib.util.spec_from_file_location('d',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);print('\\n'.join(str(r) for r,_ in m.collect()))",
    path.join(ROOT, "scripts", "deploy.py")], { encoding: "utf8" });
  const rels = out.trim().split("\n");
  const vj = JSON.parse(fs.readFileSync(path.join(ROOT, "site", "vercel.json"), "utf8"));
  assert.equal(vj.outputDirectory, "public");
  const sources = vj.redirects.map((r) => r.source);
  for (const s of ["/api/_full/:path*", "/api/%5Ffull/:path*", "/api/%5ffull/:path*"]) assert.ok(sources.includes(s), s);
  assert.ok(rels.includes("public/index.html") && rels.includes("public/library.html"));
  assert.ok(rels.includes("api/_full/full.json.gz"));
  assert.deepEqual(rels.filter((r) => r.startsWith("public/") && (r.includes("_full") || r.startsWith("public/api"))), []);
  assert.deepEqual(rels.filter((r) => !(r.startsWith("public/") || r.startsWith("api/") || r === "vercel.json" || r === "offer.json")), []);
  assert.ok(fs.readFileSync(path.join(ROOT, "scripts", "deploy.py"), "utf8").includes('"outputDirectory": "public"'));
});
