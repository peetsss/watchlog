import { Dialog } from "@base-ui/react/dialog";
import { X } from "lucide-react";
import { useRef, type ReactNode } from "react";
import { cx } from "../lib/cx";

export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  className,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="dialog-overlay" />
        <Dialog.Popup className={cx("dialog-content", className)} initialFocus={closeRef}>
          <div className="dialog-head">
            <div>
              <Dialog.Title className="dialog-title">{title}</Dialog.Title>
              <Dialog.Description className="dialog-description">{description}</Dialog.Description>
            </div>
            <Dialog.Close
              ref={closeRef}
              type="button"
              className="icon-button"
              aria-label="Close dialog"
            >
              <X size={18} />
            </Dialog.Close>
          </div>
          <div className="dialog-body">{children}</div>
          {footer ? <div className="dialog-footer">{footer}</div> : null}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
