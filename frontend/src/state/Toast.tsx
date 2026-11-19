import { useCallback, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Check } from "lucide-react";
import { Toaster, toast } from "sonner";
import { Link } from "react-router-dom";

export type ToastAction = {
  label: string;
  href: string;
};

export function ToastProvider({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      {createPortal(
        <div role="status" aria-live="polite" aria-atomic="true">
          <Toaster
            position="bottom-center"
            theme="dark"
            gap={8}
            offset={24}
            mobileOffset={{
              bottom: "calc(120px + env(safe-area-inset-bottom))",
              right: "max(16px, env(safe-area-inset-right))",
              left: "max(16px, env(safe-area-inset-left))",
            }}
            toastOptions={{ unstyled: true, duration: 3800 }}
          />
        </div>,
        document.body,
      )}
    </>
  );
}

export function useToast() {
  const showToast = useCallback((message: string, action?: ToastAction) => {
    toast.custom(
      () => (
        <div className="toast">
          <span className="toast-icon" aria-hidden="true">
            <Check size={14} strokeWidth={2.6} />
          </span>
          <span>{message}</span>
          {action ? (
            <Link className="toast-action" to={action.href}>
              {action.label}
            </Link>
          ) : null}
        </div>
      ),
      { duration: 3800, unstyled: true },
    );
  }, []);

  return { showToast };
}
