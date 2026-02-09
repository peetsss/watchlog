export default function AtmosphericBackground() {
  return (
    <>
      <div
        className="pointer-events-none fixed top-[10%] right-[-10%] z-0 h-[600px] w-[600px] blur-[80px]"
        style={{
          background:
            "radial-gradient(circle, rgba(255,107,53,0.08) 0%, transparent 70%)",
        }}
        data-testid="orb-orange"
      />
      <div
        className="pointer-events-none fixed bottom-[10%] left-[-10%] z-0 h-[500px] w-[500px] blur-[80px]"
        style={{
          background:
            "radial-gradient(circle, rgba(78,205,196,0.06) 0%, transparent 70%)",
        }}
        data-testid="orb-teal"
      />
    </>
  );
}
