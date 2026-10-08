import { copyFile, mkdir, readdir } from "node:fs/promises";
import { URL } from "node:url";

const sources = [
  new URL("../../samples/", import.meta.url),
  new URL("../../eval/holdout/images/", import.meta.url),
];
const destination = new URL("../public/samples/", import.meta.url);
await mkdir(destination, { recursive: true });
for (const source of sources) {
  for (const name of await readdir(source)) {
    await copyFile(new URL(name, source), new URL(name, destination));
  }
}
