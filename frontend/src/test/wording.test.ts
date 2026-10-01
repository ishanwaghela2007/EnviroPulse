// Guard: the UI must never present attribution as causation.
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const FORBIDDEN = [/caused by/i, /confirmed cause/i, /is the cause/i, /proven cause/i, /\bresponsible for the (spike|pollution)/i];

function files(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return e.name === "test" ? [] : files(p);
    return /\.(tsx?|css)$/.test(e.name) ? [p] : [];
  });
}

describe("wording", () => {
  it("no source file claims causation", () => {
    const hits = files(path.resolve(__dirname, "..")).flatMap((f) => {
      const text = fs.readFileSync(f, "utf8");
      return FORBIDDEN.filter((re) => re.test(text)).map((re) => `${f}: ${re}`);
    });
    expect(hits).toEqual([]);
  });
  it("attribution is labelled as an estimate", () => {
    const text = fs.readFileSync(path.resolve(__dirname, "../components/AttributionChart/AttributionChart.tsx"), "utf8");
    expect(text).toContain("ESTIMATE");
  });
});
