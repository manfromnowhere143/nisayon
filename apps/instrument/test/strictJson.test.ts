// @vitest-environment node
import { expect, it } from "vitest";
import { strictParseJson } from "../src/data/strictJson";

it.each([
  '{"row":0,"row":1}',
  '{"row":0,"\\u0072ow":1}',
  '{"outer":[{"x":1,"x":2}]}',
  '{"cost":1e400}',
  '{"cost":-1e400}',
  '{"id":9007199254740993}',
  "[".repeat(65) + "0" + "]".repeat(65),
])("rejects ambiguous or unbounded wire values: %s", (text) => {
  expect(() => strictParseJson(text)).toThrow(SyntaxError);
});
it.each([
  '{"a":1,"nested":{"a":2},"text":"{\\\"a\\\":3,1e400}"}',
  '{"path":"ends\\\\","quote":"a\\\"b","unicode":"\\u03bb"}',
  '[null,true,false,-0,-1.234e-40,1e20,9007199254740991]',
  '{"__proto__":{"x":1},"constructor":2}',
])("preserves native JSON semantics for valid data: %s", (text) => {
  expect(strictParseJson(text)).toEqual(JSON.parse(text));
});
it("retains native syntax rejection", () => {
  for (const text of ['{"a":1,}', '"unterminated', '{"a":01}', '[1 2]', '{"a":"bad\\x"}']) expect(() => strictParseJson(text)).toThrow(SyntaxError);
});
