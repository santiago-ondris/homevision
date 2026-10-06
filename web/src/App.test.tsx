import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import App from "./App";

test("renders the page title", () => {
  render(<App />);

  expect(screen.getByRole("heading", { name: "Checkbox detection" }).textContent).toBe(
    "Checkbox detection",
  );
});
