import javascript from "@eslint/js";
import hooks from "eslint-plugin-react-hooks";
import refresh from "eslint-plugin-react-refresh";
import typescript from "typescript-eslint";

export default typescript.config(
  { ignores: ["dist/**", "node_modules/**"] },
  javascript.configs.recommended,
  ...typescript.configs.strict,
  {
    files: ["**/*.tsx"],
    plugins: { "react-hooks": hooks, "react-refresh": refresh },
    rules: {
      ...hooks.configs.recommended.rules,
      "react-refresh/only-export-components": "error",
    },
  },
);
