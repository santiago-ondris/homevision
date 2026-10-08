import type { Sample } from "./SamplePicker";

export const publicForms: (Sample & { details: string })[] = [
  { filename: "irs_1040.png", label: "IRS Form 1040", details: "2550 × 3300 · PNG" },
  { filename: "irs_ss4.png", label: "IRS Form SS-4", details: "2550 × 3300 · PNG" },
  { filename: "irs_w9.png", label: "IRS Form W-9", details: "2550 × 3300 · PNG" },
  {
    filename: "urla_sec1.jpg",
    label: "Loan application, section 1",
    details: "1275 × 1650 · JPEG",
  },
  {
    filename: "urla_sec8.png",
    label: "Loan application, section 8",
    details: "2550 × 3300 · PNG",
  },
  { filename: "uscis_i9.png", label: "USCIS Form I-9", details: "2550 × 3300 · PNG" },
  { filename: "va_26_1880.png", label: "VA Form 26-1880", details: "2550 × 3300 · PNG" },
];
