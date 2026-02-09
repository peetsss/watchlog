import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AtmosphericBackground from "@/components/layout/AtmosphericBackground";

describe("AtmosphericBackground", () => {
  it("renders orange orb", () => {
    render(<AtmosphericBackground />);
    expect(screen.getByTestId("orb-orange")).toBeInTheDocument();
  });

  it("renders teal orb", () => {
    render(<AtmosphericBackground />);
    expect(screen.getByTestId("orb-teal")).toBeInTheDocument();
  });

  it("orbs have pointer-events-none", () => {
    render(<AtmosphericBackground />);
    expect(screen.getByTestId("orb-orange").className).toContain(
      "pointer-events-none"
    );
    expect(screen.getByTestId("orb-teal").className).toContain(
      "pointer-events-none"
    );
  });
});
