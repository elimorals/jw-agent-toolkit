import { Server, createServer } from "node:http";
import { AddressInfo } from "node:net";

export interface RecordedRequest {
  url: string;
  method: string;
  origin?: string;
  body?: unknown;
}

export interface MockBackend {
  server: Server;
  port: number;
  requests: RecordedRequest[];
  stop: () => Promise<void>;
}

export async function startMockBackend(port = 8765): Promise<MockBackend> {
  const recorded: RecordedRequest[] = [];
  const server = createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on("data", (c) => chunks.push(Buffer.from(c)));
    req.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf-8");
      let body: unknown;
      try {
        body = raw ? JSON.parse(raw) : undefined;
      } catch {
        body = raw;
      }
      recorded.push({
        url: req.url ?? "",
        method: req.method ?? "",
        origin: req.headers.origin as string | undefined,
        body,
      });

      // CORS preflight
      if (req.method === "OPTIONS") {
        res.writeHead(204, {
          "Access-Control-Allow-Origin":
            (req.headers.origin as string) ?? "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        });
        res.end();
        return;
      }

      const cors = {
        "Access-Control-Allow-Origin": (req.headers.origin as string) ?? "*",
        "Content-Type": "application/json",
      };

      if (req.url === "/healthz") {
        res.writeHead(200, cors);
        res.end(JSON.stringify({ status: "ok" }));
        return;
      }
      if (req.url === "/api/v1/verse_markdown") {
        res.writeHead(200, cors);
        res.end(
          JSON.stringify({
            markdown:
              "> [!quote] Juan 3:16\n> Porque Dios amó tanto al mundo que dio a su Hijo unigénito.",
            reference: "Juan 3:16",
            language: "es",
            source_url: "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3",
          }),
        );
        return;
      }
      if (req.url === "/api/v1/cross_references") {
        res.writeHead(200, cors);
        res.end(
          JSON.stringify({
            refs: [
              {
                verse: "Juan 1:1",
                url: "https://wol.jw.org/es/x/1",
                excerpt: "En el principio",
              },
              {
                verse: "1 Juan 4:9",
                url: "https://wol.jw.org/es/x/2",
                excerpt: "Amor de Dios",
              },
            ],
          }),
        );
        return;
      }
      if (req.url === "/api/v1/vault/append") {
        res.writeHead(200, cors);
        res.end(
          JSON.stringify({
            ok: true,
            path: "/tmp/vault/Verses/Juan_3_16.md",
          }),
        );
        return;
      }
      res.writeHead(404, cors);
      res.end(JSON.stringify({ error: "not_found", url: req.url }));
    });
  });
  await new Promise<void>((resolve) =>
    server.listen(port, "127.0.0.1", () => resolve()),
  );
  const actualPort = (server.address() as AddressInfo).port;
  return {
    server,
    port: actualPort,
    requests: recorded,
    stop: () =>
      new Promise<void>((resolve, reject) =>
        server.close((err) => (err ? reject(err) : resolve())),
      ),
  };
}
