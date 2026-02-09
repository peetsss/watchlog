import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  usePathname: () => "/feed",
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import Navbar from "@/components/layout/Navbar";

describe("Navbar", () => {
  it("renders navbar container", () => {
    render(<Navbar />);
    expect(screen.getByTestId("navbar")).toBeInTheDocument();
  });

  it("renders brand logo with CINECIRCLE text", () => {
    render(<Navbar />);
    expect(screen.getByTestId("brand-logo")).toHaveTextContent("CINECIRCLE");
  });

  it("renders all navigation links", () => {
    render(<Navbar />);
    expect(screen.getByTestId("nav-feed")).toBeInTheDocument();
    expect(screen.getByTestId("nav-discover")).toBeInTheDocument();
    expect(screen.getByTestId("nav-groups")).toBeInTheDocument();
    expect(screen.getByTestId("nav-lists")).toBeInTheDocument();
  });

  it("renders notification bell", () => {
    render(<Navbar />);
    expect(screen.getByTestId("notification-bell")).toBeInTheDocument();
  });

  it("highlights active tab based on pathname", () => {
    render(<Navbar />);
    const feedLink = screen.getByTestId("nav-feed");
    expect(feedLink.className).toContain("text-accent-orange");
  });
});
