import { copyFile, mkdir, readdir } from "node:fs/promises";
import { URL } from "node:url";

const source = new URL("../../samples/", import.meta.url);
const destination = new URL("../public/samples/", import.meta.url);
await mkdir(destination, { recursive: true });
for (const name of await readdir(source)) {
  await copyFile(new URL(name, source), new URL(name, destination));
}
